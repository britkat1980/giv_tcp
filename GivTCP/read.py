# -*- coding: utf-8 -*-
from giverrors import errDetail
from givenergy_modbus.model.inverter import Model,SinglePhaseInverter
from givenergy_modbus.model.inverter import WorkMode, Status
from givenergy_modbus.model.ems import EmsInverterStatus, MAX_MANAGED_INVERTERS
from givenergy_modbus.model.meter import MeterStatus
from givenergy_modbus.model.battery import State
from givenergy_modbus.model.plant import Plant, PlantCapabilities
from givenergy_modbus.model.register import HR, IR
from givenergy_modbus.exceptions import CommunicationError, RefreshPartiallySucceeded
from givenergy_modbus.model import TimeSlot
import sys
import json
import logging
import datetime
import pickle
import time
import write
import inspect
import requests
from GivLUT import GivLUT, maxvalues, InvType, GivClientAsync
from entity_lut import Entity_Type
from settings import GiV_Settings
from os.path import exists
import os
from datetime import timedelta
import asyncio
from typing import Callable, Optional
from mqtt import GivMQTT
from modbus_patches import pause_registers, PAUSE_MODE_REGISTER, PAUSE_SLOT_REGISTERS, bms_current_inverter
from givenergy_modbus.model.inverter import SinglePhaseInverterRegisterGetter
import copy

logging.getLogger("givenergy_modbus").setLevel(logging.ERROR) 

class _ConnectionWarnings(logging.Filter):
    # The modbus client's errors, plus its warnings about the connection itself (eg. "connection lost (reader at
    # EOF)"), which explain a dropped connection. Its other warnings (retries and the like) stay hidden
    def filter(self, record):
        return record.levelno>=logging.ERROR or "connect" in record.getMessage().lower()
_clientLogger=logging.getLogger("givenergy_modbus.client.client")
_clientLogger.setLevel(logging.WARNING)
_clientLogger.addFilter(_ConnectionWarnings())
logging.getLogger("rq.worker").setLevel(logging.CRITICAL)

sys.path.append(GiV_Settings.default_path)

givLUT = Entity_Type.entity_type
logger = GivLUT.logger

def commsFailure():
    fname="commsfailure_"+str(GiV_Settings.givtcp_instance)+".pkl"
    if exists(fname):
        with open(fname, 'rb') as inp:
            oldDataCount= pickle.load(inp)
        oldDataCount = oldDataCount + 1
    else:
        oldDataCount = 1
    with open(fname, 'wb') as outp:
        pickle.dump(oldDataCount, outp, pickle.HIGHEST_PROTOCOL)
    return oldDataCount

# The inverter resets its Today counters by its own clock, on some firmware a little after midnight
TODAY_RESET_GRACE_MINUTES=5

def newInverterDay(invTime, multi_output_old, grace=True):
    # True when the inverter's date has moved on since the previous output, so yesterday's Today values mustn't be
    # carried over. Comparing dates (rather than looking for a poll in the 00:00 minute) still works after a missed
    # poll, a restart over midnight or a container clock that differs from the inverter's.
    # With grace, it also stays True while the previous poll was within the grace period after midnight, in case
    # that poll still carried yesterday's counters.
    oldTime=finditem(multi_output_old,"Invertor_Time") if multi_output_old else None
    try:
        new=datetime.datetime.fromisoformat(str(invTime))
        old=datetime.datetime.fromisoformat(str(oldTime))
    except (TypeError, ValueError):
        return False
    if new.date()!=old.date():
        logger.debug("New inverter day ("+str(old.date())+" -> "+str(new.date())+"), Today stats reset")
        return True
    return grace and old.hour==0 and old.minute<TODAY_RESET_GRACE_MINUTES

# How far the inverter's clock can be from GivTCP's before it is worth a warning, and the day it was last given
CLOCK_DRIFT_MINUTES=5
_clockWarned=None

def checkInverterClock(invTime):
    # The inverter resets its Today counters at midnight by its own clock, so a clock that is out (often an hour,
    # when it hasn't changed for summer time) moves the reset away from midnight in HA. Warn once a day
    global _clockWarned
    try:
        inv=datetime.datetime.fromisoformat(str(invTime))
        now=datetime.datetime.now(GivLUT.timezone)
        offset=round((inv-now).total_seconds()/60)
    except (TypeError, ValueError):
        return
    if abs(offset)<CLOCK_DRIFT_MINUTES or _clockWarned==now.date():
        return
    _clockWarned=now.date()
    size=abs(offset)
    amount=str(size)+" minutes" if size<120 else str(round(size/60))+" hours" if size<2880 else str(round(size/1440))+" days"
    shown="%H:%M" if inv.date()==now.date() else "%d %b %H:%M"
    logger.warning("Inverter clock is "+amount+" "+("behind" if offset<0 else "ahead of")+" GivTCP's ("+inv.strftime(shown)+
                   " against "+now.strftime(shown)+"), so its Today energy counters reset at the wrong time. "
                   "Use the Sync Time button, or the GivEnergy portal, to correct it")

def batteryTotals(GEInv, battery):
    # Lifetime battery charge/discharge (kWh) for a single-phase LV inverter. Firmware keeps them in different places:
    # the first battery's BMS (IR105/106: Gen 2, AC and most Gen 1) or the inverter (IR180/181: some Gen 1, eg. fw 449,
    # where the BMS reads 0). Battery first, as 3.5 did, so the HA statistics carry on from the same counter
    charge,discharge=battery.e_battery_charge_total, battery.e_battery_discharge_total
    if not charge and not discharge:
        charge=GEInv.e_battery_charge_total if GEInv.e_battery_charge_total is not None else GEInv.e_battery_charge_total_alt1
        discharge=GEInv.e_battery_discharge_total if GEInv.e_battery_discharge_total is not None else GEInv.e_battery_discharge_total_alt1
    return charge,discharge

def rebootaddon():
    if GiV_Settings.isAddon:
        access_token = os.getenv("SUPERVISOR_TOKEN")
        url="http://supervisor/addons/self/restart"
        result = requests.post(url,
            headers={'Content-Type':'application/json',
                    'Authorization': 'Bearer {}'.format(access_token)})
        logger.info("Supervisor restart was: "+str(result))
    else:
        result="Please restart GivTCP Manually..."
        logger.info(result)

def capsFile():
    return GivLUT.config_dir+"/"+GiV_Settings.serial_number+"_caps.pkl"

def pauseModeUnsupported(caps):
    # Battery pause mode (HR 318): only where it can be written (see modbus_patches.pause_registers). Some
    # models read it but can't write it, and Force Charge/Export fail if they try to set it
    if caps is None:
        return False
    return PAUSE_MODE_REGISTER not in pause_registers(caps.device_type, caps.arm_firmware_version)

def pauseSlotsUnsupported(caps):
    # Battery pause slot (HR 319-320): not on AC, which has pause mode but no slot
    if caps is None:
        return False
    return not PAUSE_SLOT_REGISTERS <= pause_registers(caps.device_type, caps.arm_firmware_version)

def pauseSlotAvailable():
    # For callers without the plant (REST): False only if the saved capabilities say there's no pause slot
    try:
        with open(capsFile(), 'rb') as inp:
            return not pauseSlotsUnsupported(pickle.load(inp))
    except Exception:
        return True     # not known, so let the write decide

def pauseValue(plant, GEInv, key):
    # The Gateway model has no pause fields, so decode them from its registers as the inverter model does
    if hasattr(GEInv, key):
        return getattr(GEInv, key)
    cache=plant.register_caches.get(plant.capabilities.inverter_address)
    return SinglePhaseInverterRegisterGetter(cache).get(key) if cache else None
# Models whose PV string voltage/current registers aren't real string readings (they echo the AC side), which
# givenergy-modbus 2.13+ reports as None
PV_STRING_VI_UNSUPPORTED=[Model.AC, Model.ALL_IN_ONE]

# DC-coupled hybrids, whose PV goes through the inverter: Load = inverter output - AC charge - export + import.
# AC-coupled models also add the PV, which comes from a separate inverter
DC_HYBRID_MODELS=(Model.HYBRID_GEN1,Model.HYBRID_GEN2,Model.HYBRID_GEN3,Model.HYBRID_GEN4,Model.HYBRID_HV_GEN3)
# Max battery current (A) by device type code for HV Gen 3 hybrids; unlisted models assume 25A
HV_GEN3_BAT_CURRENT={"8102":25,"8103":30}
# Rated capacity of a GIV-BAT-3.4-HV stackable module (GivEnergy datasheet: 3 modules 10.2kWh ... 6 modules 20.4kWh)
HV_MODULE_KWH=3.4
# Volts a module for HV battery power: the inverter's battery current limit x this x modules a stack (#604)
HV_MODULE_VOLTS=80
# Bump when the Load calculation changes, so the hold that stops Load going down lets it drop once to the new value
LOAD_FORMULA_VERSION="2"

def loadFormulaChanged():
    # True the first time this is called with a new LOAD_FORMULA_VERSION (and on a first run, which changes nothing)
    marker=GiV_Settings.cache_location+"/.load_formula_"+str(GiV_Settings.givtcp_instance)
    try:
        with open(marker) as inp:
            if inp.read().strip()==LOAD_FORMULA_VERSION:
                return False
    except OSError:
        pass
    try:
        with open(marker,'w') as outp:
            outp.write(LOAD_FORMULA_VERSION)
        logger.info("Load energy calculation updated, so Load Energy Today/Total may drop once to the corrected value")
    except OSError as e:
        logger.warning("Unable to save the load formula version: "+str(e))
    return True

def unsupportedEntities():
    # Entities this inverter model can't have. Older GivTCP versions created some of these in HA,
    # and their retained discovery messages keep them there, so discovery removes them explicitly
    try:
        with open(capsFile(), 'rb') as inp:
            caps=pickle.load(inp)
        device_type=caps.device_type
    except Exception:
        return []
    unsupported=[]
    if pauseModeUnsupported(caps):
        unsupported+=['Battery_pause_mode']
    if pauseSlotsUnsupported(caps):
        unsupported+=['Battery_pause_start_time_slot','Battery_pause_end_time_slot']
    if device_type in PV_STRING_VI_UNSUPPORTED:
        unsupported+=['PV_Voltage_String_1','PV_Voltage_String_2','PV_Current_String_1','PV_Current_String_2']
    unsupported+=['Battery_BMS_Current']      # renamed Battery_Discharge_Current in 3.6 beta 5 (#605)
    if not bms_current_inverter(device_type, caps.arm_firmware_version):
        unsupported+=['Battery_Discharge_Current']      # this inverter never passes on pack current (#605)
    return unsupported

def wrongInverter(client):
    # The serial of the inverter that answered, if it isn't the one in the settings (eg. two inverters' IP
    # addresses have swapped), otherwise None
    try:
        found=client.plant.inverter.serial_number
    except Exception:
        return None
    if found and GiV_Settings.serial_number and found!=GiV_Settings.serial_number:
        return found
    return None

async def detectPlant(client, force=False):
    # Detect only when there is no capabilities file for this inverter (startup normally creates one).
    # Returns True if cached capabilities were used, so callers can re-detect if they turn out to be stale
    if not force and exists(capsFile()):
        try:
            with open(capsFile(), 'rb') as inp:
                client.plant.capabilities=pickle.load(inp)
            logger.info("Using cached capabilities from "+str(capsFile())+", skipping detect")
            return True
        except Exception as e:
            logger.warning("Unable to load cached capabilities, running full detect: "+str(e))
    logger.info("Detecting inverter characteristics...")
    await client.detect()
    found=wrongInverter(client)
    if found:
        # Saving another inverter's capabilities under this serial would give this inverter the wrong model from then on
        logger.error("Inverter at "+str(GiV_Settings.invertorIP)+" is "+str(found)+", not "+str(GiV_Settings.serial_number)+
                     " as in settings, so its capabilities are not being saved. Check the IP address in the settings")
        return False
    try:
        with open(capsFile(), 'wb') as outp:
            pickle.dump(client.plant.capabilities, outp, pickle.HIGHEST_PROTOCOL)
        logger.info("Saved capabilities to "+str(capsFile()))
    except Exception as e:
        logger.warning("Unable to save capabilities cache: "+str(e))
    return False

async def readPlant(client, fullRefresh):
    # Run the register reads. Partial failures still leave good data in the register cache so keep going,
    # only a total failure (RefreshFailed) or lost connection is raised
    # refresh_max_age skips IR banks the dongle has already relayed recently from another poller (cloud/app)
    max_age=getattr(GiV_Settings,'refresh_max_age',0) or None
    failures=[]
    reads=[lambda: client.refresh(max_age=max_age)]
    if fullRefresh:
        reads.append(client.load_config)    #Run full HR read on fullRefresh
    for read in reads:
        try:
            await read()
        except RefreshPartiallySucceeded as e:
            failures.extend(e.failures)
    if failures:
        logger.debug("%d register reads failed, using partial data: %s", len(failures), ", ".join(f"{f.request_type}(0x{f.device_address:02x},{f.base_register})" for f in failures))
    return failures

# Pause between queued write commands, so the dongle isn't flooded
WRITE_COMMAND_GAP=0.3

async def processWriteRequests(client):
    """Run any write commands queued in GivLUT.writerequests (by REST, MQTT or the RQ worker) against the plant.
    Returns True if more commands arrived while these were running, so the caller should call again straight away"""
    if not exists(GivLUT.writerequests):
        return False
    # v2's Gateway model only covers the IR 1600+ block and has no command methods -
    # Gateway writes are plain single-phase HR writes, so use the inverter view (as reads do)
    if client.plant.capabilities.is_ems:
        device=client.plant.ems
    else:
        device=client.plant.inverter
    try:
        logger.debug("Write Request recieved")
        with open(GivLUT.writerequests, 'rb') as inp:
            writecommands= pickle.load(inp)
        for command in writecommands:
            # call wr command and pass parameters
            logger.debug("Command: "+str(command[0])+" was recieved: "+str(command[1]))
            if hasattr(write, command[0]):
                func = getattr(write, command[0])
                if inspect.iscoroutinefunction(func):
                    result = await func(device,command[1],True)
                else:
                    result = func(device,command[1],True)
                #send result to touchfile for REST response
                if command[2]==True:
                    response={}
                    responses=[]
                    response['id']=command[0]
                    response['result']=result
                    if exists(GivLUT.restresponse):
                        with GivLUT.restlock:
                            with open(GivLUT.restresponse,'r') as inp:
                                responses=json.load(inp)
                        responses.append(response)
                        logger.debug("responses is: "+str(responses))
                    else:
                        responses.append(response)
                        logger.debug("responses is: "+str(responses))
                    with GivLUT.restlock:
                        with open(GivLUT.restresponse,'w') as outp:
                            outp.write(json.dumps(responses))
                await asyncio.sleep(WRITE_COMMAND_GAP)        #Pause between commands
            else:
                logger.error("Unknown write command: "+str(command[0])+" - ignoring")

    ## Check write file for anything more since opening and loop again
        with open(GivLUT.writerequests, 'rb') as inp:
            newwritecommands= pickle.load(inp)
        logger.debug("Write Commands lengths: "+str(len(writecommands))+" -> "+str(len(newwritecommands)))
        if len(newwritecommands)==len(writecommands):     #Only remove if no more commands recieved
            logger.debug("No new writes, removing writerequest file")
            os.remove(GivLUT.writerequests)
        else:
        #    #Loop straight back to proces smore write commands
            logger.debug("Looping back to mop up incoming write commands")
            ## remove old command before looping back
            for i in newwritecommands[:]:
                if i in writecommands:
                    newwritecommands.remove(i)
            GivLUT.save_writerequests(newwritecommands)
            return True
    except Exception as e:
        logger.error("Write request error: "+str(e.__class__.__name__)+": "+str(e)+" deleting all pending requests, please try again")
        if exists(GivLUT.writerequests):
            os.remove(GivLUT.writerequests)
    return False

class ConnectionDrops:
    """Logs each time the inverter closes the connection, with how long since the last traffic: the first time,
    then a summary every 5 minutes. Drops ~10s after traffic, every poll, are a dongle closing idle connections
    (#604); occasional drops at random times, followed by failed reconnects, are the dongle going offline briefly
    (a restart or lost Wi-Fi). Also logs how long it took to reconnect when the first attempts fail, at info level
    only if it took longer than a read cycle (refresh_period), as a quicker reconnect costs no data"""
    SUMMARY_SECONDS=300
    BUSY_SECONDS=2

    def __init__(self, refresh_period=None):
        self.refresh_period=refresh_period
        self.noted=False
        self.idle=[]
        self.lastsummary=None
        self.lostat=None        # when the connection was lost (or the first reconnect failed), until it reconnects
        self.failures=0

    def note(self, plant: Plant):
        if self.noted:      # once per drop: the loop sees it again every pass until it reconnects
            return
        self.noted=True
        self.lostat=datetime.datetime.now()
        stamps=plant.register_block_updated_at.values()
        idle=(datetime.datetime.now(datetime.timezone.utc)-max(stamps)).total_seconds() if stamps else None
        if self.lastsummary is None:
            self.lastsummary=datetime.datetime.now()
            logger.info("Inverter closed the Modbus connection (last traffic "+self.fmt(idle)+" before). GivTCP will reconnect when it next needs to")
            return
        self.idle.append(idle)
        logger.debug("Inverter closed the Modbus connection (last traffic "+self.fmt(idle)+" before)")
        if (datetime.datetime.now()-self.lastsummary).total_seconds()>=self.SUMMARY_SECONDS:
            known=[i for i in self.idle if i is not None]
            busy=sum(1 for i in known if i<self.BUSY_SECONDS)
            logger.info("Inverter closed the Modbus connection "+str(len(self.idle))+" times in the last "+str(round((datetime.datetime.now()-self.lastsummary).total_seconds()/60))+" minutes"
                +(", last traffic "+self.fmt(min(known))+" to "+self.fmt(max(known))+" before" if known else "")
                +(" ("+str(busy)+" within "+str(self.BUSY_SECONDS)+"s of traffic)" if busy else "")+". GivTCP will reconnect when it next needs to")
            self.idle=[]
            self.lastsummary=datetime.datetime.now()

    def failed(self):
        self.failures+=1
        if self.lostat is None:
            self.lostat=datetime.datetime.now()

    def reconnected(self):
        if self.failures:
            took=(datetime.datetime.now()-self.lostat).total_seconds()
            slow=self.refresh_period is None or took>self.refresh_period
            logger.log(logging.INFO if slow else logging.DEBUG,
                "Reconnected to the inverter after "+str(self.failures)+" failed attempt"+("s" if self.failures>1 else "")
                +" ("+self.fmt(took)+" after the connection was lost)")
        self.noted=False
        self.lostat=None
        self.failures=0

    @staticmethod
    def fmt(seconds):
        return "an unknown time" if seconds is None else str(round(seconds,1))+"s"

# After a full refresh that couldn't read some settings (holding registers), retry it on this many more polls (#608)
FULL_REFRESH_RETRIES=3
# Seconds to the first poll if the full refresh when connecting failed
FULL_REFRESH_RETRY_DELAY=10

def settingsRetry(failures, retries):
    """After a full refresh, whether to make the next poll a full one too, and the new retry count. Retries while
    some settings (holding registers) weren't read, rather than wait for the next full refresh (#608)"""
    settingsFailed=[f for f in failures if f.request_type=="ReadHoldingRegistersRequest"]
    if settingsFailed and retries<FULL_REFRESH_RETRIES:
        logger.debug("Inverter settings not all read (attempt "+str(retries+1)+"), next poll is a full refresh")
        return True, retries+1
    if settingsFailed:
        logger.warning("Some inverter settings could not be read after "+str(retries+1)+" attempts, trying again at the next full refresh: "+
                       ", ".join(f"HR(0x{f.device_address:02x},{f.base_register})" for f in settingsFailed))
    return False, 0

async def watch_plant(
        handler: Optional[Callable] = None,
        refresh_period: float = 15.0,
        full_refresh_period: float = 60,
        passive: bool = False,
    ):
        totalTimeoutErrors=0

        """Refresh data about the Plant."""
        try:
            client = await GivClientAsync.get_connection(cold_start=True)
            usedCache=await detectPlant(client)
            initialFull=False
            try:
                logger.debug ("Running full refresh")
                await client.load_config()
                initialFull=True
            except Exception as e:
                # Often the inverter is still recovering after a restart. Without these the inverter details can't
                # be processed, so retry soon rather than wait for the next full refresh (#608)
                logger.warning("Unable to read all the inverter settings after connecting, retrying shortly: "+str(e))
            try:
                await readPlant(client, False)
            except CommunicationError:
                if not usedCache or not client.connected:
                    raise
                # Connected but nothing came back: the cached capabilities may not match this inverter any more
                logger.warning("No data using cached capabilities, running full detect")
                await detectPlant(client, force=True)
                await readPlant(client, False)
            #await client.close()
            if client.plant.capabilities.is_gateway==True:
                if client.plant.gateway.parallel_aio_num < 2:
                    logger.critical("Gateway device has a single AIO attached. Consider disabling in config as mostly duplicate data is collected from Gateway")
            if exists("commsfailure_"+str(GiV_Settings.givtcp_instance)+".pkl"):
                # Remove any failed counts if connection runs OK
                os.remove("commsfailure_"+str(GiV_Settings.givtcp_instance)+".pkl")
            if handler:
                try:
                    handler(client.plant)
                except Exception as err:
                    e=errDetail()
                    logger.error ("Error in calling handler: "+str(err))

        except CommunicationError as e:
            cause=e.__cause__ or e
            logger.debug ("Unable to connect to inverter on: "+str(GiV_Settings.invertorIP)+" ("+type(cause).__name__+": "+str(cause)+")")
            failcount=commsFailure()
            if failcount>=10:
                logger.error("Lost communications with Inverter. Restarting container to detect IP change")
                rebootaddon()
            try:
                await client.close()
            except:
                pass
            return
        except Exception as e:
            logger.error("Error in inital detect/refresh: "+errDetail())
            try:
                await client.close()
            except:
                pass
            return
        # set last full_refresh time. If the first full refresh failed, the first poll (sooner than usual) is a full one
        lastfulltime=datetime.datetime.now() if initialFull else datetime.datetime.min
        nextpoll=datetime.datetime.now()+timedelta(seconds=refresh_period if initialFull else min(FULL_REFRESH_RETRY_DELAY,refresh_period))
        fullRetries=0
        timeoutErrors=0
        connectErrors=0
        partialPolls=0
        drops=ConnectionDrops(refresh_period)
        logger.info("Starting data refresh cycle")
        while True:
            try:
                if not client.connected:
                    if getattr(client,'_connection_lost',False):     # the inverter end closed it, not GivTCP
                        drops.note(client.plant)
                    # Many dongles close a connection after ~10s without traffic (#604), so only reconnect when
                    # there's something to send rather than straight away, which would just be closed again
                    if not exists(GivLUT.writerequests) and datetime.datetime.now()<nextpoll:
                        await asyncio.sleep(0.5)
                        continue
                    logger.debug("Re-opening Modbus Connecion to: "+str(GiV_Settings.invertorIP))
                    try:
                        if connectErrors>=2:
                            # The same client can keep failing to reconnect while a new one connects first time
                            await GivClientAsync.new_client()
                        client=await GivClientAsync.get_connection(reconnect=True)
                        connectErrors=0
                        drops.reconnected()
                    except CommunicationError as e:
                        connectErrors=connectErrors+1
                        drops.failed()
                        cause=e.__cause__ or e
                        # A dongle going offline briefly (restart, Wi-Fi) usually fails a couple of attempts, so only
                        # treat it as an error once it persists
                        logger.log(logging.WARNING if connectErrors<=2 else logging.ERROR,
                            "Unable to connect to inverter on: "+str(GiV_Settings.invertorIP)+" ("+type(cause).__name__+": "+str(cause)+")")
                        failcount=commsFailure()
                        if failcount>=10:
                            logger.error("Lost communications with Inverter. Restarting container to detect IP change")
                            rebootaddon()
                        await asyncio.sleep(min(5*connectErrors,60))    #Back off rather than hammering the dongle
                        continue
                # Write command and initiation to use the same client connection
                if await processWriteRequests(client):
                    continue    #Loop straight back to process more write commands

                now = datetime.datetime.now(tz=GivLUT.timezone)
                if datetime.datetime.now() < nextpoll:
                    await asyncio.sleep(0.5)
                    #if refresh period hasn't expired then just keep looping back up to write check
                    continue
                # Keep a steady cadence from the start of each poll
                nextpoll=datetime.datetime.now()+timedelta(seconds=refresh_period)
                if not passive:
                    #Check time since last full_refresh
                    timesincefull=datetime.datetime.now()-lastfulltime
                    if timesincefull.total_seconds() > full_refresh_period or exists(".fullrefresh") or GiV_Settings.inverter_type.lower()=="gateway":      #always run full refresh for Gateway
                        fullRefresh=True
                        logger.debug ("Running full refresh")
                    elif now.hour == 0 and now.minute == 0:
                        fullRefresh=True
                        logger.debug ("Midnight so grabbing full Energy data")
                    else:
                        fullRefresh=False
                        logger.debug ("Running partial refresh")
                    try:
                        failures=await readPlant(client, fullRefresh)
                        timeoutErrors=0     # Reset timeouts if all is good this run
                        # A device that fails every poll (eg. a battery removed since the capabilities were
                        # cached) means they are stale, so re-detect once it has persisted for a while
                        partialPolls=partialPolls+1 if failures else 0
                        if partialPolls>=10:
                            logger.warning("Some devices have not responded for 10 polls, re-detecting inverter characteristics")
                            partialPolls=0
                            previousCaps=client.plant.capabilities
                            try:
                                await detectPlant(client, force=True)
                            except Exception as e:
                                # detect() clears capabilities on failure, which would stop every later poll
                                client.plant.capabilities=previousCaps
                                logger.error("Re-detect failed, keeping current capabilities: "+str(e))
                        logger.debug("Data get was successful, now running handler if needed: ")
                        retry=False
                        if fullRefresh:
                            retry,fullRetries=settingsRetry(failures,fullRetries)
                        if fullRefresh and not retry:
                            # Only mark full refresh done once it succeeds, so a post-write readback isn't lost
                            lastfulltime=datetime.datetime.now()
                            if exists(".fullrefresh"):
                                os.remove(".fullrefresh")
                        if exists("commsfailure_"+str(GiV_Settings.givtcp_instance)+".pkl"):
                            # Remove any failed counts if connection runs OK
                            os.remove("commsfailure_"+str(GiV_Settings.givtcp_instance)+".pkl")
                    except Exception as err:
                        totalTimeoutErrors=totalTimeoutErrors+1
                        timeoutErrors=timeoutErrors+1
                        logger.debug("Error num "+str(timeoutErrors)+" in watch loop read: "+str(err.__class__.__name__)+": "+str(err))
                        logger.debug("Not running handler")
                        if timeoutErrors>5:
                            logger.error("5 consecutive read errors in watch loop. Restarting modbus connection")
                            await client.close()    # Reconnect happens at the top of the loop
                            timeoutErrors=0
                        # Retry sooner than a full period, backing off on repeated failures
                        nextpoll=datetime.datetime.now()+timedelta(seconds=min(2**timeoutErrors, refresh_period))
                        continue
                    if handler:
                        try:
                            handler(client.plant)
                        except Exception as e:
                            logger.error("Error in calling handler: "+errDetail())
            except Exception:
                logger.error ("Error in Watch Loop: "+errDetail())
                await client.close()
                await asyncio.sleep(1)      #Avoid a tight loop if the error repeats

def dataAge(plant: Plant):
    # Seconds since the newest live (IR) bank from the main device was committed, None if never.
    # A successful poll can still be serving held last-good data, so this is the real freshness measure
    addr=plant.capabilities.inverter_address
    stamps=[ts for (dev,regtype,_,_),ts in plant.register_block_updated_at.items() if dev==addr and regtype=="IR"]
    if not stamps:
        return None
    return (datetime.datetime.now(datetime.timezone.utc)-max(stamps)).total_seconds()

def batteryCount(plant: Plant):
    # givenergy-modbus v2's number_batteries only counts LV batteries. HV and three-phase stacks are
    # BCU modules (and AIO batteries separate modules), so take the largest count the plant reports
    count=plant.number_batteries
    caps=plant.capabilities
    if caps:
        count=max(count, sum(n for _,n in caps.bcu_stacks), len(caps.aio_battery_module_addresses), len(caps.hv_bmu_addresses))
    return count

def resolvedModel(plant: Plant, device=None):
    # The model detect resolved (Model.HYBRID_GEN1, HYBRID_HV_GEN3, ...). The device model's own .model is a coarse
    # decode of the device type code: Model.HYBRID for every Gen 1/2 hybrid, and Model.ALL_IN_ONE for HV Gen 3 (81xx)
    if plant.capabilities is not None:
        return plant.capabilities.device_type
    return getattr(device, 'model', None)

def getInvModel(plant: Plant):
##### Feels like this needs reviewing and maybe moving to the device models
    inverterModel = InvType
    # The capacity the battery rate (HR111/112, a C-rate) is a percentage of, where it isn't batterycapacity
    inverterModel.ratecapacity=None
    if plant.capabilities.is_ems:
        GEInv=plant.ems
    elif plant.capabilities.is_gateway:
        GEInv=plant.gateway
    else:
        GEInv=plant.inverter
    if plant.capabilities.is_gateway:
        # givenergy-modbus v2's Gateway model only covers the IR 1600+ block (no model/power/capacity),
        # so take the model from capabilities and max inverter power from the holding-register view
        inverterModel.model=Model.GATEWAY
        inverterModel.invmaxrate=plant.inverter.inverter_max_power
    else:
        inverterModel.model=resolvedModel(plant, GEInv)
        #inverterModel.generation=GEInv.generation
        #inverterModel.phase=GEInv.num_phases
        inverterModel.invmaxrate=GEInv.inverter_max_power
        inverterModel.batmaxrate=GEInv.battery_max_power
        inverterModel.batterycapacity=GEInv.battery_capacity_kwh        #for HV this is reported Ah times nom voltage (100%)
    # Calc max charge rate
    if plant.capabilities.is_three_phase:
        inverterModel.batmaxrate= 25 * 80 * batteryCount(plant)
    elif plant.capabilities.is_gateway:
        inverterModel.batmaxrate=6000*int(GEInv.parallel_aio_num or 0)
        inverterModel.batterycapacity=13.5*int(GEInv.parallel_aio_num or 0)
    elif inverterModel.model in [Model.HYBRID_GEN4,Model.ALL_IN_ONE]:
        inverterModel.batmaxrate=6000
    elif inverterModel.model==Model.HYBRID_HV_GEN3 and plant.capabilities.bcu_stacks:
        # Battery power is capped by the inverter's battery current at the stack voltage (~80V a module), so a
        # short stack can't reach the headline rate (#604). Stacks run in parallel, so voltage follows modules per stack
        modules=max(n for _,n in plant.capabilities.bcu_stacks)
        stackrate=HV_GEN3_BAT_CURRENT.get(str(GEInv.device_type_code),25) * HV_MODULE_VOLTS * modules
        if modules:
            inverterModel.batmaxrate=min(stackrate, inverterModel.batmaxrate or stackrate)
        # The library's capacity is HR55 Ah x the All-in-One's 307V, as it groups HV Gen 3 with the All-in-One, so
        # use the modules' rating instead. Unlike voltage, capacity adds up across parallel stacks (#604)
        total=sum(n for _,n in plant.capabilities.bcu_stacks)
        if total:
            inverterModel.batterycapacity=round(HV_MODULE_KWH*total,1)
        # The battery rate's C is each module's Ah rating, not its usable kWh: a rate of 50% (0.5C) charges and
        # discharges a 3-module stack at the inverter's ~6kW maximum, not 0.5 x 10.2kWh = 5.1kW (#604)
        ratecap=0
        for hvstack,(_,n) in zip(plant.hv_stacks,plant.capabilities.bcu_stacks):
            ah=hvstack.bcu.battery_nominal_capacity_ah if hvstack.bcu.is_valid() else None
            ratecap+=(ah or 0)*HV_MODULE_VOLTS*(n or 0)/1000
        if ratecap:
            inverterModel.ratecapacity=round(ratecap,2)
    return inverterModel

def getRaw(plant: Plant):
    if plant.capabilities.is_ems:
        GEInv=plant.ems
    elif plant.capabilities.is_gateway:
        GEInv=plant.gateway
    else:
        GEInv=plant.inverter
    if not plant.capabilities.is_hv:
        GEBat=plant.batteries
    
    #GEBCU=plant.bcu

    Meters=plant.meters
    isHV=plant.capabilities.is_hv
    raw = {}
    bat={}
    meters={}
###    inv=GEInv.getall()
    raw['invertor']=GEInv
    if isHV:
        stacks={}
        # givenergy-modbus v2: BCU values plus each valid BMU, as plain dicts so they serialise cleanly
        for i, hvstack in enumerate(plant.hv_stacks):
            stack=hvstack.bcu.model_dump()
            for b in hvstack.bmus:
                if b.is_valid():
                    stack[b.serial_number]=b.model_dump()
            stacks['Stack_'+str(i)]=stack
        raw['HV_Battery_Stacks']=stacks
    else:
        for b in GEBat:
            if b.is_valid():        # unconfirmed batteries (first poll after connecting) have no serial yet
                bat[b.serial_number]=b
        raw['batteries']=bat
    if Meters:
        for m in Meters:
            meters['Meter_ID_'+str(m)]=Meters[m].model_dump()
        raw['meters']=meters
    
    return raw

def getall(model):
    raw={}
    raw=model.to_dict()
    for attr in type(model).model_fields:
        raw[attr] = model.__getattribute__(attr)
    return raw


def getMeters(plant: Plant):
    meters={}
    for m in plant.meters:
        temp=plant.meters[m]
        meter={}
        meter['Phase_1_Voltage']=temp.v_phase_1
        meter['Phase_2_Voltage']=temp.v_phase_2
        meter['Phase_3_Voltage']=temp.v_phase_3
        meter['Phase_1_Current']=temp.i_phase_1
        meter['Phase_2_Current']=temp.i_phase_2
        meter['Phase_3_Current']=temp.i_phase_3
        meter['Phase_1_Power']=temp.p_active_phase_1
        meter['Phase_2_Power']=temp.p_active_phase_2
        meter['Phase_3_Power']=temp.p_active_phase_3
        meter['Frequency']=temp.frequency
        meter['Phase_1_Power_Factor']=temp.pf_phase_1
        meter['Phase_2_Power_Factor']=temp.pf_phase_2
        meter['Phase_3_Power_Factor']=temp.pf_phase_3
        meter['Import_Energy_kWh']=temp.e_import_active
        meter['Export_Energy_kWh']=temp.e_export_active
        meters['Meter_ID'+str(m)]=meter
    return meters

def enumText(value):
    # An enum field's name, eg. "Normal", or None until its register has been read (eg. a holding register after
    # the first read following a restart failed), so one missing value doesn't fail the whole poll (#608)
    return value.name.capitalize() if value is not None else None

_emptyBatteryPolls={}

def batteryNotReady(key):
    # The library withholds a battery's data until a second read confirms the first (cold-start guard),
    # so one or two empty polls after connecting are expected. Only report it as an error if it persists,
    # and only once, rather than every poll (#611)
    _emptyBatteryPolls[key]=_emptyBatteryPolls.get(key,0)+1
    if _emptyBatteryPolls[key]==3:
        logger.error("Battery "+str(key)+" has returned no valid data for 3 polls, skipping it until it does")
    elif _emptyBatteryPolls[key]>3:
        logger.debug("Battery "+str(key)+" has returned no valid data for "+str(_emptyBatteryPolls[key])+" polls, skipping")
    else:
        logger.debug("Battery "+str(key)+" data not confirmed yet (first reads after connecting), skipping this poll")

def getBatteries(plant: Plant, multi_output_old):
    try:
        if not plant.inverter ==None:
            GEInv=plant.inverter
        elif not plant.ems ==None:
            GEInv=plant.ems
        elif not plant.gateway ==None:
            GEInv=plant.gateway
        
        is3PH=plant.capabilities.is_three_phase
        isHV=plant.capabilities.is_hv
        batteries2={}
        stack={}
        logger.debug("Getting Battery Details")
        if not isHV:
            GEBat=plant.batteries
            for num,b in enumerate(GEBat):
                if b.is_valid():          # Check for empty battery object responses and only process if they are complete (have a serial number)
                    _emptyBatteryPolls.pop(num+1,None)
                    logger.debug("Building battery output: ")
                    battery = {}
                    battery['Battery_Serial_Number'] = b.serial_number
                    if b.soc != 0:
                        battery['Battery_SOC'] = b.soc
                    elif b.soc == 0:
                        oldSOC=(multi_output_old or {}).get('Battery_Details',{}).get('Battery_Stack_1',{}).get(b.serial_number,{}).get('Battery_SOC')
                        battery['Battery_SOC'] = oldSOC if oldSOC is not None else 1
                    else:
                        battery['Battery_SOC'] = 1
                    battery['Battery_Capacity'] = b.cap_calibrated
                    battery['Battery_Design_Capacity'] = b.cap_design
                    battery['Battery_Remaining_Capacity'] = b.cap_remaining
                    battery['Battery_Firmware_Version'] = b.bms_firmware_version
                    battery['Battery_Cells'] = b.num_cells
                    battery['Battery_Cycles'] = b.num_cycles
                    battery['Battery_USB_present'] = b.usb_device_inserted
                    battery['Battery_Temperature'] = b.t_bms_mosfet
                    battery['Battery_Voltage'] = b.v_cells_sum
                    if b.i_battery is not None:     # None where the inverter or pack firmware doesn't report it (#605)
                        battery['Battery_Discharge_Current'] = b.i_battery      # GivEnergy: discharge only, so not Battery_Current
                    # IR(91) high byte = Status 3 (protocol v4.4.1 s4.4.1.1): bit1=charge MOS, bit2=discharge MOS, 1=closed
                    if b.status_3 is not None:
                        battery['Battery_Charge_MOS_State'] = "Closed" if b.status_3 & 0x02 else "Open"
                        battery['Battery_Discharge_MOS_State'] = "Closed" if b.status_3 & 0x04 else "Open"
                    for i in range(16):
                        battery['Battery_Cell_'+str(i+1)+'_Voltage'] = b.__getattribute__('v_cell_'+str(i+1).zfill(2))
                    battery['Battery_Cell_1_Temperature'] = b.t_cells_01_04
                    battery['Battery_Cell_2_Temperature'] = b.t_cells_05_08
                    battery['Battery_Cell_3_Temperature'] = b.t_cells_09_12
                    battery['Battery_Cell_4_Temperature'] = b.t_cells_13_16
                    stack[b.serial_number] = battery
                    logger.debug("Battery "+str(b.serial_number)+" added")
                else:
                    batteryNotReady(num+1)

                stack['BMS_Temperature']=GEInv.t_battery
                stack['BMS_Voltage']=GEInv.v_battery
                # Make this always Battery_Stack_1
                batteries2['Battery_Stack_1']=stack
        else:
            # givenergy-modbus v2: each HvStack has a BCU (stack level) and a list of BMUs (per module)
            for num,hvstack in enumerate(plant.hv_stacks):
                bcu=hvstack.bcu
                if not bcu.is_valid():
                    batteryNotReady("stack "+str(num+1))
                    continue
                _emptyBatteryPolls.pop("stack "+str(num+1),None)
                modules=bcu.number_of_modules or len(hvstack.bmus)
                bcudata={}
                bcudata['Stack_Voltage']=bcu.battery_voltage
                bcudata['Stack_Current']=bcu.battery_current
                bcudata['Stack_Power']=bcu.battery_power
                bcudata['Stack_SOH']=bcu.battery_soh
                bcudata['Stack_Load_Voltage']=bcu.load_voltage
                bcudata['Stack_Cycles']=bcu.number_of_cycles
                if bcu.battery_soc_max is not None and bcu.battery_soc_min is not None:
                    bcudata['Stack_SOC_Difference']=bcu.battery_soc_max-bcu.battery_soc_min
                bcudata['Stack_SOC_High']=bcu.battery_soc_max
                bcudata['Stack_SOC_Low']=bcu.battery_soc_min
                bcudata['Stack_Firmware']=bcu.pack_software_version
                # IR(101) Packn_DisChgState (protocol v4.4.1 s4.4.2.3), not modelled by givenergy-modbus: bit0=charge, bit1=discharge, 1=closed
                dischgState=plant.register_caches.get(hvstack.device_address,{}).get(IR(101))
                if dischgState is not None:
                    bcudata['Stack_Charge_MOS_State']="Closed" if dischgState & 0x01 else "Open"
                    bcudata['Stack_Discharge_MOS_State']="Closed" if dischgState & 0x02 else "Open"
                # v2 reports capacity in Ah per module: kWh = Ah x 76.8V module voltage, and usable kWh is 10% less
                if bcu.battery_nominal_capacity_ah is not None:
                    bcudata['Stack_Design_Capacity']=round(bcu.battery_nominal_capacity_ah*76.8/1000*modules*0.9,2)
                if bcu.remaining_battery_capacity_ah is not None:
                    bcudata['Stack_SOC_kWh']=round(bcu.remaining_battery_capacity_ah*76.8/1000*modules*0.9,2)
                bcudata['Stack_Discharge_Energy_Today_kWh']=bcu.discharge_energy_today
                bcudata['Stack_Charge_Energy_Today_kWh']=bcu.charge_energy_today
                bcudata['Stack_Discharge_Energy_Total_kWh']=bcu.discharge_energy_total
                bcudata['Stack_Charge_Energy_Total_kWh']=bcu.charge_energy_total
                # HV modules have 24 cells but 12 temperature sensors (the BCU reports the total sensor count)
                numTemps=12
                if bcu.total_temperature_sensor_count and modules:
                    numTemps=max(1,min(24,bcu.total_temperature_sensor_count//modules))
                stackTemps=[]
                for b in hvstack.bmus:
                    if not b.is_valid():          # BMU has no serial yet (not polled, or awaiting a confirming read)
                        batteryNotReady("stack "+str(num+1)+" module "+str((b.bmu_index or 0)+1))
                        continue
                    _emptyBatteryPolls.pop("stack "+str(num+1)+" module "+str((b.bmu_index or 0)+1),None)
                    sn=b.serial_number
                    logger.debug("Building battery output: ")
                    battery = {}
                    battery['Battery_Serial_Number'] = sn
                    for i in range(24):
                        battery['Battery_Cell_'+str(i+1)+'_Voltage'] = getattr(b,'v_cell_'+str(i+1).zfill(2))
                    for i in range(numTemps):
                        temp=getattr(b,'t_cell_'+str(i+1).zfill(2))
                        battery['Battery_Cell_'+str(i+1)+'_Temperature'] = temp
                        if temp is not None:
                            stackTemps.append(temp)
                    bcudata[sn] = battery
                    logger.debug("Battery "+str(sn)+" added")
                # Average of the module sensors (the library's three-phase inverter model, also used for
                # HV Gen3, has no single battery temperature)
                if stackTemps:
                    bcudata['BMS_Temperature']=round(sum(stackTemps)/len(stackTemps),2)
                batteries2['Battery_Stack_'+str(num+1)]=bcudata
        return batteries2
    except KeyError as e:
        missing_key = e.args[0] if e.args else None
        logger.error("Key Error getting Battery Data: missing key "+repr(missing_key)+" - "+errDetail())
    except Exception as e:
        logger.error("Error getting Battery Data: "+errDetail())
        return None

def validateTimeslot(slot,key,multi_output_old):
    if slot:
        output = slot.isoformat()
    elif multi_output_old:
        logger.debug("Suprious Timeslot data: using last good data")
        output=multi_output_old.get('Timeslots',{}).get(key,"00:00:00")
    else:
        logger.debug("Suprious Timeslot data: setting to Midnight")
        output="00:00:00"
    return output

def getTimeslots(plant: Plant, multi_output_old=None):
    timeslots={}
    controlmode={}
    if not plant.inverter ==None:
        GEInv=plant.inverter
    elif not plant.ems ==None:
        GEInv=plant.ems
    elif not plant.gateway ==None:
        GEInv=plant.gateway
    logger.debug("Getting TimeSlot data")
    timeslots['Discharge_start_time_slot_1'] = validateTimeslot(getattr(GEInv.discharge_slot_1,'start',None),"Discharge_start_time_slot_1",multi_output_old)
    timeslots['Discharge_start_time_slot_2'] = validateTimeslot(getattr(GEInv.discharge_slot_2,'start',None),"Discharge_start_time_slot_2",multi_output_old)
    timeslots['Discharge_end_time_slot_1'] = validateTimeslot(getattr(GEInv.discharge_slot_1,'end',None),"Discharge_end_time_slot_1",multi_output_old)
    timeslots['Discharge_end_time_slot_2'] = validateTimeslot(getattr(GEInv.discharge_slot_2,'end',None),"Discharge_end_time_slot_2",multi_output_old)
    timeslots['Charge_start_time_slot_1'] = validateTimeslot(getattr(GEInv.charge_slot_1,'start',None),"Charge_start_time_slot_1",multi_output_old)
    timeslots['Charge_end_time_slot_1'] = validateTimeslot(getattr(GEInv.charge_slot_1,'end',None),"Charge_end_time_slot_1",multi_output_old)

    try:
        model=resolvedModel(plant, GEInv)
        if model in [Model.ALL_IN_ONE, Model.AC_3PH, Model.HYBRID_3PH, Model.GATEWAY, Model.HYBRID_GEN4, Model.HYBRID_HV_GEN3] or (model == Model.HYBRID_GEN3 and int(GEInv.arm_firmware_version)>302):   #10 slots don't apply to AC/Hybrid except new fw on Gen 3
            timeslots['Charge_start_time_slot_2'] = validateTimeslot(getattr(GEInv.charge_slot_2,'start',None),"Charge_start_time_slot_2",multi_output_old)
            timeslots['Charge_end_time_slot_2'] = validateTimeslot(getattr(GEInv.charge_slot_2,'end',None),"Charge_end_time_slot_2",multi_output_old)
            timeslots['Charge_start_time_slot_3'] = validateTimeslot(getattr(GEInv.charge_slot_3,'start',None),"Charge_start_time_slot_3",multi_output_old)
            timeslots['Charge_end_time_slot_3'] = validateTimeslot(getattr(GEInv.charge_slot_3,'end',None),"Charge_end_time_slot_3",multi_output_old)
            timeslots['Charge_start_time_slot_4'] = validateTimeslot(getattr(GEInv.charge_slot_4,'start',None),"Charge_start_time_slot_4",multi_output_old)
            timeslots['Charge_end_time_slot_4'] = validateTimeslot(getattr(GEInv.charge_slot_4,'end',None),"Charge_end_time_slot_4",multi_output_old)
            timeslots['Charge_start_time_slot_5'] = validateTimeslot(getattr(GEInv.charge_slot_5,'start',None),"Charge_start_time_slot_5",multi_output_old)
            timeslots['Charge_end_time_slot_5'] = validateTimeslot(getattr(GEInv.charge_slot_5,'end',None),"Charge_end_time_slot_5",multi_output_old)
            timeslots['Charge_start_time_slot_6'] = validateTimeslot(getattr(GEInv.charge_slot_6,'start',None),"Charge_start_time_slot_6",multi_output_old)
            timeslots['Charge_end_time_slot_6'] = validateTimeslot(getattr(GEInv.charge_slot_6,'end',None),"Charge_end_time_slot_6",multi_output_old)
            timeslots['Charge_start_time_slot_7'] = validateTimeslot(getattr(GEInv.charge_slot_7,'start',None),"Charge_start_time_slot_7",multi_output_old)
            timeslots['Charge_end_time_slot_7'] = validateTimeslot(getattr(GEInv.charge_slot_7,'end',None),"Charge_end_time_slot_7",multi_output_old)
            timeslots['Charge_start_time_slot_8'] = validateTimeslot(getattr(GEInv.charge_slot_8,'start',None),"Charge_start_time_slot_8",multi_output_old)
            timeslots['Charge_end_time_slot_8'] = validateTimeslot(getattr(GEInv.charge_slot_8,'end',None),"Charge_end_time_slot_8",multi_output_old)
            timeslots['Charge_start_time_slot_9'] = validateTimeslot(getattr(GEInv.charge_slot_9,'start',None),"Charge_start_time_slot_9",multi_output_old)
            timeslots['Charge_end_time_slot_9'] = validateTimeslot(getattr(GEInv.charge_slot_9,'end',None),"Charge_end_time_slot_9",multi_output_old)
            timeslots['Charge_start_time_slot_10'] = validateTimeslot(getattr(GEInv.charge_slot_10,'start',None),"Charge_start_time_slot_10",multi_output_old)
            timeslots['Charge_end_time_slot_10'] = validateTimeslot(getattr(GEInv.charge_slot_10,'end',None),"Charge_end_time_slot_10",multi_output_old)
            timeslots['Discharge_start_time_slot_3'] = validateTimeslot(getattr(GEInv.discharge_slot_3,'start',None),"Discharge_start_time_slot_3",multi_output_old)
            timeslots['Discharge_end_time_slot_3'] = validateTimeslot(getattr(GEInv.discharge_slot_3,'end',None),"Discharge_end_time_slot_3",multi_output_old)
            timeslots['Discharge_start_time_slot_4'] = validateTimeslot(getattr(GEInv.discharge_slot_4,'start',None),"Discharge_start_time_slot_4",multi_output_old)
            timeslots['Discharge_end_time_slot_4'] = validateTimeslot(getattr(GEInv.discharge_slot_4,'end',None),"Discharge_end_time_slot_4",multi_output_old)
            timeslots['Discharge_start_time_slot_5'] = validateTimeslot(getattr(GEInv.discharge_slot_5,'start',None),"Discharge_start_time_slot_5",multi_output_old)
            timeslots['Discharge_end_time_slot_5'] = validateTimeslot(getattr(GEInv.discharge_slot_5,'end',None),"Discharge_end_time_slot_5",multi_output_old)
            timeslots['Discharge_start_time_slot_6'] = validateTimeslot(getattr(GEInv.discharge_slot_6,'start',None),"Discharge_start_time_slot_6",multi_output_old)
            timeslots['Discharge_end_time_slot_6'] = validateTimeslot(getattr(GEInv.discharge_slot_6,'end',None),"Discharge_end_time_slot_6",multi_output_old)
            timeslots['Discharge_start_time_slot_7'] = validateTimeslot(getattr(GEInv.discharge_slot_7,'start',None),"Discharge_start_time_slot_7",multi_output_old)
            timeslots['Discharge_end_time_slot_7'] = validateTimeslot(getattr(GEInv.discharge_slot_7,'end',None),"Discharge_end_time_slot_7",multi_output_old)
            timeslots['Discharge_start_time_slot_8'] = validateTimeslot(getattr(GEInv.discharge_slot_8,'start',None),"Discharge_start_time_slot_8",multi_output_old)
            timeslots['Discharge_end_time_slot_8'] = validateTimeslot(getattr(GEInv.discharge_slot_8,'end',None),"Discharge_end_time_slot_8",multi_output_old)
            timeslots['Discharge_start_time_slot_9'] = validateTimeslot(getattr(GEInv.discharge_slot_9,'start',None),"Discharge_start_time_slot_9",multi_output_old)
            timeslots['Discharge_end_time_slot_9'] = validateTimeslot(getattr(GEInv.discharge_slot_9,'end',None),"Discharge_end_time_slot_9",multi_output_old)
            timeslots['Discharge_start_time_slot_10'] = validateTimeslot(getattr(GEInv.discharge_slot_10,'start',None),"Discharge_start_time_slot_10",multi_output_old)
            timeslots['Discharge_end_time_slot_10'] = validateTimeslot(getattr(GEInv.discharge_slot_10,'end',None),"Discharge_end_time_slot_10",multi_output_old)

            controlmode['Charge_Target_SOC_1'] = GEInv.charge_target_soc_1
            controlmode['Charge_Target_SOC_2'] = GEInv.charge_target_soc_2
            controlmode['Charge_Target_SOC_3'] = GEInv.charge_target_soc_3
            controlmode['Charge_Target_SOC_4'] = GEInv.charge_target_soc_4
            controlmode['Charge_Target_SOC_5'] = GEInv.charge_target_soc_5
            controlmode['Charge_Target_SOC_6'] = GEInv.charge_target_soc_6
            controlmode['Charge_Target_SOC_7'] = GEInv.charge_target_soc_7
            controlmode['Charge_Target_SOC_8'] = GEInv.charge_target_soc_8
            controlmode['Charge_Target_SOC_9'] = GEInv.charge_target_soc_9
            controlmode['Charge_Target_SOC_10'] = GEInv.charge_target_soc_10
            controlmode['Discharge_Target_SOC_1'] = GEInv.discharge_target_soc_1
            controlmode['Discharge_Target_SOC_2'] = GEInv.discharge_target_soc_2
            controlmode['Discharge_Target_SOC_3'] = GEInv.discharge_target_soc_3
            controlmode['Discharge_Target_SOC_4'] = GEInv.discharge_target_soc_4
            controlmode['Discharge_Target_SOC_5'] = GEInv.discharge_target_soc_5
            controlmode['Discharge_Target_SOC_6'] = GEInv.discharge_target_soc_6
            controlmode['Discharge_Target_SOC_7'] = GEInv.discharge_target_soc_7
            controlmode['Discharge_Target_SOC_8'] = GEInv.discharge_target_soc_8
            controlmode['Discharge_Target_SOC_9'] = GEInv.discharge_target_soc_9
            controlmode['Discharge_Target_SOC_10'] = GEInv.discharge_target_soc_10
    except:
        logger.debug("New Charge/Discharge timeslots don't exist for this model")

    pauseSlot=None if pauseSlotsUnsupported(plant.capabilities) else pauseValue(plant,GEInv,'battery_pause_slot_1')
    if pauseSlot is not None:   #Battery Pause slots not on AC, older Gen 1, 3PH or EMS
        timeslots['Battery_pause_start_time_slot'] = validateTimeslot(getattr(pauseSlot,'start',None),"Battery_pause_start_time_slot",multi_output_old)
        timeslots['Battery_pause_end_time_slot'] = validateTimeslot(getattr(pauseSlot,'end',None),"Battery_pause_end_time_slot",multi_output_old)
    # Unused slots report a 0% target, which HA rejects (min 4%) on every poll - don't publish them
    controlmode={k:v for k,v in controlmode.items() if not ("Target_SOC_" in k and isinstance(v,(int,float)) and v<4)}
    return timeslots,controlmode


def getControls(plant,regCacheStack, inverterModel,multi_output_old=None):
    controlmode={}
    temp={}
    is3PH=False
    is3PH=plant.capabilities.is_three_phase
    if not plant.inverter ==None:
        GEInv=plant.inverter
    elif not plant.ems ==None:
        GEInv=plant.ems
    elif not plant.gateway ==None:
        GEInv=plant.gateway

    logger.debug("Getting mode control figures")
    # On 3PH the discharge enable is HR1122 (force_discharge_enable in givenergy-modbus v2); v2's
    # enable_discharge is the single-phase HR59, which the old library remapped to HR1122 for 3PH
    enable_discharge = GEInv.force_discharge_enable if is3PH else GEInv.enable_discharge
    # Get Control Mode registers
    if is3PH:
        if GEInv.force_charge_enable==True and GEInv.ac_charge_enable==True:
            charge_schedule = "enable"
        else:
            charge_schedule = "disable"
    else:
        if not GEInv.enable_charge == None:
            if GEInv.enable_charge == True:
                charge_schedule = "enable"
            else:
                charge_schedule = "disable"
        elif multi_output_old:
            charge_schedule=multi_output_old['Control']['Enable_Charge_Schedule']
        else:
            charge_schedule="disable"    #Default to off
        
        if not GEInv.battery_power_mode == None:
            if GEInv.battery_power_mode == True:
                batPowerMode="enable"
            else:                
                batPowerMode="disable"
        elif multi_output_old:
            batPowerMode=multi_output_old['Control']['Eco_Mode']
        else:
            batPowerMode="disable"    #Default to off
        controlmode['Eco_Mode'] = batPowerMode

    if not enable_discharge == None:
        if enable_discharge == True:
            discharge_schedule = "enable"
        else:
            discharge_schedule = "disable"
    elif multi_output_old:
        discharge_schedule=multi_output_old['Control']['Enable_Discharge_Schedule']
    else:
        discharge_schedule="disable"    #Default to off

    if not GEInv.enable_charge_target == None:
        if GEInv.enable_charge_target == True:
            controlmode['Enable_Charge_Target']="enable"
        else:
            controlmode['Enable_Charge_Target']="disable"
    elif multi_output_old:
        controlmode['Enable_Charge_Target']=multi_output_old['Control']['Enable_Charge_Target']
    else:
        controlmode['Enable_Charge_Target']="disable"    #Default to off

    battery_reserve = GEInv.battery_soc_reserve

    # Save a non-100 battery_reserve value for use later in restoring after resuming Eco/Dynamic mode
    # Check to see if we have a saved value already...
    saved_battery_reserve = 0
    if exists(GivLUT.reservepkl):
        with open(GivLUT.reservepkl, 'rb') as inp:
            saved_battery_reserve = pickle.load(inp)

    # Has the saved value changed from the current value? Only carry on if it is different (and was read)
    if battery_reserve is not None and saved_battery_reserve != battery_reserve:
        if battery_reserve < 100:
            try:
                # Pickle the value to use later...
                with open(GivLUT.reservepkl, 'wb') as outp:
                    pickle.dump(battery_reserve, outp, pickle.HIGHEST_PROTOCOL)
                logger.debug ("Saving the battery reserve percentage for later: " + str(battery_reserve))
            except:
                e=errDetail()
                temp['result'] = "Saving the battery reserve for later failed: " + str(e)
                logger.error (temp['result'])
        else:
            # Value is 100, we don't want to save 100 because we need to restore to a value FROM 100...
            logger.debug ("Saving the battery reserve percentage for later: no need, it's currently at 100 and we don't want to save that.")

    battery_cutoff = GEInv.battery_discharge_min_power_reserve
    target_soc = GEInv.charge_target_soc

    # NON 3PH controls go here
    if not plant.capabilities.device_type in (Model.AC_3PH, Model.HYBRID_3PH, Model.GATEWAY):        #Not on 3Ph OR GATEWAY
        # HR111/112 can be unread (None) if the HR(60-119) block failed - fall back to the previous values
        ratecapacity=getattr(inverterModel,'ratecapacity',None) or inverterModel.batterycapacity
        for key, limit in (('Battery_Discharge_Rate', GEInv.battery_discharge_limit), ('Battery_Charge_Rate', GEInv.battery_charge_limit)):
            if limit is not None and ratecapacity:
                controlmode[key]=int(min((limit/100)*ratecapacity*1000, inverterModel.batmaxrate))
            elif multi_output_old and key in multi_output_old.get('Control',{}):
                controlmode[key]=multi_output_old['Control'][key]
    else:
        # HR313/314 can be unread (None), e.g. on Gateway - fall back to the previous values
        for key, limit in (('Battery_Discharge_Rate', GEInv.battery_discharge_limit_ac), ('Battery_Charge_Rate', GEInv.battery_charge_limit_ac)):
            if limit is not None:
                controlmode[key]=int(inverterModel.batmaxrate*(limit/100))
            elif multi_output_old and key in multi_output_old.get('Control',{}):
                controlmode[key]=multi_output_old['Control'][key]
        
    
    controlmode['Enable_Charge_Schedule'] = charge_schedule
    controlmode['Enable_Discharge_Schedule'] = discharge_schedule

    
    
    if GEInv.battery_discharge_limit_ac:
        discharge_rate_ac = int(GEInv.battery_discharge_limit_ac)          #not on old firmware
        controlmode['Battery_Discharge_Rate_AC'] = discharge_rate_ac
    if GEInv.battery_charge_limit_ac:
        charge_rate_ac = int(GEInv.battery_charge_limit_ac)                #not on old firmware
        controlmode['Battery_Charge_Rate_AC'] = charge_rate_ac
    

    # Calculate Mode
    logger.debug("Calculating Mode...")
    # Calc Mode

    if GEInv.battery_power_mode == 1 and enable_discharge == False and GEInv.battery_soc_reserve != 100:
        # Dynamic r27=1 r110=4 r59=0
        mode = "Eco"
    elif GEInv.battery_power_mode == 1 and enable_discharge == False and GEInv.battery_soc_reserve == 100:
        # Dynamic r27=1 r110=4 r59=0
        mode = "Eco (Paused)"
    elif GEInv.battery_power_mode == 1 and enable_discharge == True:
        # Storage (demand) r27=1 r110=100 r59=1
        mode = "Timed Demand"
    elif GEInv.battery_power_mode == 0 and enable_discharge == True:
        # Storage (export) r27=0 r59=1
        mode = "Timed Export"
    elif GEInv.battery_power_mode == 0 and enable_discharge == False:
        # Dynamic r27=1 r110=4 r59=0
        mode = "Export (Paused)"
    else:
        mode = "Unknown"

    logger.debug("Mode is: " + str(mode))

    controlmode['Mode'] = mode
    
    if plant.capabilities.is_three_phase:
        controlmode['Battery_Power_Cutoff'] = GEInv.battery_reserve_soc      # v2 name for HR1078 (battery_power_cutoff is deprecated)
    else:
        controlmode['Battery_Power_Cutoff'] = battery_cutoff
        controlmode['Battery_Power_Reserve'] = battery_reserve
        
    controlmode['Target_SOC'] = target_soc
    controlmode['Sync_Time'] = "disable"

    if not GEInv.enable_rtc == None:
        if GEInv.enable_rtc == True:
            controlmode['Real_Time_Control'] = "enable"
            open(GivLUT.rtc_enabled,'w').close()
        else:
            controlmode['Real_Time_Control'] = "disable"
            if exists(GivLUT.rtc_enabled):
                os.remove(GivLUT.rtc_enabled)
    else:
        controlmode['Real_Time_Control'] = (multi_output_old or {}).get("Control",{}).get("Real_Time_Control","disable")
        logger.debug("RTC returned Unknown status, keeping last state: "+str(controlmode['Real_Time_Control']))


    pauseMode=None if pauseModeUnsupported(plant.capabilities) else pauseValue(plant,GEInv,'battery_pause_mode')
    if pauseMode is not None:
        controlmode['Battery_pause_mode'] = GivLUT.battery_pause_mode[int(pauseMode)]
    calibration=enumText(GEInv.battery_calibration_stage)
    if calibration in GivLUT.battery_calibration:
        controlmode['Battery_Calibration'] = calibration
    elif calibration is not None:
        controlmode['Battery_Calibration'] = "Running"
    controlmode['Active_Power_Rate']= GEInv.active_power_rate
    controlmode['Reboot_Invertor']="disable"
    controlmode['Reboot_Addon']="disable"
    # Keep the running state of temp pauses from the last poll (the keys live under Control)
    oldControl=(multi_output_old or {}).get("Control",{})
    controlmode['Temp_Pause_Discharge'] = oldControl.get("Temp_Pause_Discharge","Normal")
    controlmode['Temp_Pause_Charge'] = oldControl.get("Temp_Pause_Charge","Normal")

    if exists(".FCRunning"+str(GiV_Settings.givtcp_instance)):
        logger.debug("Force Charge is Running")
        controlmode['Force_Charge'] = "Running"
        #Get time left to run in mins and publish to number
        minsremain=getJobFinish(".FCRunning"+str(GiV_Settings.givtcp_instance))
        logger.debug("Time remaining is" + str(minsremain))
        controlmode['Force_Charge_Num']=max(0,int(minsremain))
    else:
        controlmode['Force_Charge'] = "Normal"
        controlmode['Force_Charge_Num']=0
    if exists(".FERunning"+str(GiV_Settings.givtcp_instance)):
        logger.debug("Force_Export is Running")
        controlmode['Force_Export'] = "Running"
        minsremain=getJobFinish(".FERunning"+str(GiV_Settings.givtcp_instance))
        logger.debug("Time remaining is" + str(minsremain))
        controlmode['Force_Export_Num']=max(0,int(minsremain))
    else:
        logger.debug("Force Export is not Running")
        controlmode['Force_Export'] = "Normal"
        controlmode['Force_Export_Num']=0
    if exists(".tpcRunning_"+str(GiV_Settings.givtcp_instance)):
        logger.debug("Temp Pause Charge is Running")
        controlmode['Temp_Pause_Charge'] = "Running"
        minsremain=getJobFinish(".tpcRunning_"+str(GiV_Settings.givtcp_instance))
        logger.debug("Time remaining is" + str(minsremain))
        controlmode['Temp_Pause_Charge_Num']=max(0,int(minsremain))
    else:
        controlmode['Temp_Pause_Charge'] = "Normal"
        controlmode['Temp_Pause_Charge_Num']=0
    if exists(".tpdRunning_"+str(GiV_Settings.givtcp_instance)):
        logger.debug("Temp_Pause_Discharge is Running")
        controlmode['Temp_Pause_Discharge'] = "Running"
        minsremain=getJobFinish(".tpdRunning_"+str(GiV_Settings.givtcp_instance))
        logger.debug("Time remaining is" + str(minsremain))
        controlmode['Temp_Pause_Discharge_Num']=max(0,int(minsremain))
    else:
        controlmode['Temp_Pause_Discharge'] = "Normal"
        controlmode['Temp_Pause_Discharge_Num']=0
    return controlmode


def processPVInfo(plant: Plant):
    energy_total_output = {}
    energy_today_output = {}
    power_output = {}
    power_flow_output = {}
    inverter = {}
    inverterModel= InvType
    multi_output={}
    try:
        GEInv=plant.inverter
        inverterModel=getInvModel(plant)

        
        # Grab previous data from Pickle and use it validate any outrageous changes
        regCacheStack = GivLUT.get_regcache()
        if regCacheStack:
            multi_output_old = regCacheStack[-1]
        else:
            regCacheStack = []      # no cache yet (first poll) - previous values default to empty
            multi_output_old = {}

        # Check a couple of obvious data points to reject bad reads
        if float(GEInv.modbus_version)>2 or GEInv.modbus_address>100 or GEInv.user_code>100 or GEInv.t_inverter_heatsink>100:
            logger.debug("Dodgy Data so using last cache...")
            return multi_output_old

        # If System Time is wrong (default date) use last good time or local time if all else fails
        if GEInv.system_time is None or GEInv.system_time.year == 2000:     # unreadable or default date
            #Use old Sys_Time
            logger.debug("Inverter Time is default... fixing it")
            inverter['Invertor_Time'] = finditem(multi_output_old,"Invertor_Time")
            if inverter['Invertor_Time']==None:
            # Unless its missing then use now()
                inverter['Invertor_Time']=datetime.datetime.now(GivLUT.timezone).isoformat()
        else:
            # Use latest data if its not default date
            inverter['Invertor_Time'] = GEInv.system_time.replace(tzinfo=GivLUT.timezone).isoformat()

    ############  Energy Stats    ############
        # Total Energy Figures
        logger.debug("Getting Total Energy Data")

        energy_total_output['Export_Energy_Total_kWh'] = GEInv.e_grid_out_total

        energy_total_output['Invertor_Energy_Total_kWh'] = GEInv.e_inverter_out_total
        energy_total_output['PV_Energy_Total_kWh'] = GEInv.e_pv_total

        # Energy Today Figures
        logger.debug("Getting Today Energy Data")
        energy_today_output['PV_Energy_Today_kWh'] = GEInv.e_pv1_day+GEInv.e_pv2_day
        energy_today_output['Export_Energy_Today_kWh'] = GEInv.e_grid_out_day
        energy_today_output['Invertor_Energy_Today_kWh'] = GEInv.e_pv_generation_today

    ############  Core Power Stats    ############

        # PV Power
        logger.debug("Getting PV Power")
        PV_power_1 = GEInv.p_pv1
        PV_power_2 = GEInv.p_pv2
        PV_power = PV_power_1+PV_power_2
        if PV_power < 15000:
            power_output['PV_Power_String_1'] = PV_power_1
            power_output['PV_Power_String_2'] = PV_power_2
            power_output['PV_Power'] = PV_power
        power_output['PV_Voltage_String_1'] = GEInv.v_pv1
        power_output['PV_Voltage_String_2'] = GEInv.v_pv2
        power_output['PV_Current_String_1'] = GEInv.i_pv1
        power_output['PV_Current_String_2'] = GEInv.i_pv2
        power_output['Grid_Voltage'] = GEInv.v_ac1
        power_output['Grid_Current'] = GEInv.i_grid_port 

        # Grid Power
        logger.debug("Getting Grid Power")
        grid_power = GEInv.p_grid_out
        if grid_power < 0:
            import_power = abs(grid_power)
            export_power = 0
        elif grid_power > 0:
            import_power = 0
            export_power = abs(grid_power)
        else:
            import_power = 0
            export_power = 0
        power_output['Grid_Power'] = grid_power
        power_output['Import_Power'] = import_power
        power_output['Export_Power'] = export_power


        # Inverter Power
        logger.debug("Getting PInv Power")
        inverter_power = GEInv.p_grid_out_ph1
        if -inverterModel.invmaxrate <= inverter_power <=inverterModel.invmaxrate:
            power_output['Invertor_Power'] = inverter_power

    ############  Power Flow Stats    ############

        # Solar to H/B/G
        logger.debug("Getting Solar to H/B/G Power Flows")
        if PV_power > 0:
            S2H = min(PV_power - export_power,0)
            power_flow_output['Solar_to_House'] = S2H
            power_flow_output['Solar_to_Grid'] = export_power

        else:
            power_flow_output['Solar_to_House'] = 0
            power_flow_output['Solar_to_Grid'] = 0

        if GEInv.f_ac1>100:
            freq=GEInv.f_ac1/10
        else:
            freq=GEInv.f_ac1
        power_output['Grid_Frequency'] = freq
        if GEInv.f_ac1_output>100:
            freq=GEInv.f_ac1_output/10
        else:
            freq=GEInv.f_ac1_output
        power_output['Inverter_Output_Frequency'] = freq

        # Check for all zeros
        checksum = 0
        for item in energy_total_output:
            checksum = checksum+energy_total_output[item]
        if checksum == 0:
            raise ValueError("All zeros returned by inverter, skipping update")

        ######## Get Inverter Details ########
        logger.debug("Getting inverter Details")
        inverter['Invertor_Serial_Number'] = plant.inverter_serial_number
        inverter['Modbus_Version'] = GEInv.modbus_version
        inverter['Invertor_Firmware'] = GEInv.firmware_version
        inverter['Meter_Type'] = enumText(GEInv.meter_type)
        inverter['Invertor_Type'] = resolvedModel(plant, GEInv).name.capitalize()
        inverter['Invertor_Max_Inv_Rate'] = inverterModel.invmaxrate
        inverter['Invertor_Temperature'] = GEInv.t_inverter_heatsink
        inverter['Export_Limit']=GEInv.grid_port_max_power_output

        ######## Get Meter Details ########

        meters={}
        meters.update(getMeters(plant))

        ######## Get Battery Details ########

            ######## Create multioutput and publish #########
        energy = {}
        energy["Today"] = energy_today_output
        energy["Total"] = energy_total_output
        power = {}
        power["Power"] = power_output
        power["Flows"] = power_flow_output
        multi_output["Power"] = power
        multi_output[GEInv.serial_number] = inverter
        multi_output["Energy"] = energy
        multi_output["Meter_Details"] = meters
        if GiV_Settings.Print_Raw_Registers:
            multi_output['raw'] = getRaw(plant)
    except KeyError as e:
        missing_key = e.args[0] if e.args else None
        logger.error("Key Error getting Battery Data: missing key "+repr(missing_key)+" - "+errDetail())
    except Exception:
        logger.error("Error processing Inverter data: " + errDetail())
        return None
    return multi_output

def processInverterInfo(plant: Plant):
    energy_total_output = {}
    energy_today_output = {}
    power_output = {}
    controlmode = {}
    power_flow_output = {}
    inverter = {}
    inverterModel= InvType
    multi_output={}

    try:
        GEInv=plant.inverter
        GEBat=plant.batteries
        isHV=plant.capabilities.is_hv
        inverterModel=getInvModel(plant)
        
        # Grab previous data from Pickle and use it validate any outrageous changes
        regCacheStack = GivLUT.get_regcache()
        if regCacheStack:
            multi_output_old = regCacheStack[-1]
        else:
            regCacheStack = []      # no cache yet (first poll) - previous values default to empty
            multi_output_old = {}

        # If System Time is wrong (default date) use last good time or local time if all else fails
        if GEInv.system_time is None or GEInv.system_time.year == 2000:     # unreadable or default date
            #Use old Sys_Time
            logger.warning("Inverter Time is default... fixing it")
            inverter['Invertor_Time'] = finditem(multi_output_old,"Invertor_Time")
            if inverter['Invertor_Time']==None:
            # Unless its missing then use now()
                inverter['Invertor_Time']=datetime.datetime.now(GivLUT.timezone).isoformat(timespec='seconds')
        else:
            # Use latest data if its not default date
            inverter['Invertor_Time'] = GEInv.system_time.replace(tzinfo=GivLUT.timezone).isoformat(timespec='seconds')
        inv_time=datetime.datetime.strptime(inverter['Invertor_Time'], '%Y-%m-%dT%H:%M:%S%z')

    ############  Energy Stats    ############
        # Total Energy Figures
        logger.debug("Getting Total Energy Data")
        if not isHV:
            #if GEInv.e_battery_charge_total == 0 and GEInv.e_battery_discharge_total == 0 and not GiV_Settings.numBatteries==0:  # If no values in "nomal" registers then grab from back up registers - for some f/w versions
            if len(GEBat)>0:
                charge,discharge=batteryTotals(GEInv,GEBat[0])
                if charge or discharge:
                    energy_total_output['Battery_Charge_Energy_Total_kWh'] = charge
                    energy_total_output['Battery_Discharge_Energy_Total_kWh'] = discharge
                else:
                    # Nothing holds them on this firmware. Leave them out rather than publish 0: HA treats a total
                    # dropping to 0 as a meter reset, and counts the whole total again when it comes back
                    logger.debug("No battery charge/discharge totals available, so not publishing them")

        energy_total_output['Export_Energy_Total_kWh'] = GEInv.e_grid_out_total
        energy_total_output['Import_Energy_Total_kWh'] = GEInv.e_grid_in_total
        # givenergy-modbus v2 routes IR45/46 to e_inverter_out_total on AC/AIO (e_pv_generation_total is None there)
        energy_total_output['Invertor_Energy_Total_kWh'] = GEInv.e_pv_generation_total if GEInv.e_pv_generation_total is not None else GEInv.e_inverter_out_total
        energy_total_output['PV_Energy_Total_kWh'] = GEInv.e_pv_total
        energy_total_output['AC_Charge_Energy_Total_kWh'] = GEInv.e_inverter_in_total

        # Calculate total Load to avoid rounding errors. On a DC hybrid the PV is already in the inverter's output,
        # so only AC-coupled models add it. Needs the resolved model: the library's own .model is only the family
        # (HYBRID), which sent hybrids down the AC formula and counted their PV twice from the v2 library on
        dcHybrid=resolvedModel(plant, GEInv) in DC_HYBRID_MODELS
        formulaChanged=loadFormulaChanged()
        if dcHybrid:
            total_load = max(0,round((energy_total_output['Invertor_Energy_Total_kWh']-energy_total_output['AC_Charge_Energy_Total_kWh']) -
                                                                    (energy_total_output['Export_Energy_Total_kWh']-energy_total_output['Import_Energy_Total_kWh']), 2))
        else:
            total_load= max(0,round((energy_total_output['Invertor_Energy_Total_kWh']-energy_total_output['AC_Charge_Energy_Total_kWh']) -
                                                                    (energy_total_output['Export_Energy_Total_kWh']-energy_total_output['Import_Energy_Total_kWh'])+energy_total_output['PV_Energy_Total_kWh'], 2))
        
        if multi_output_old and not formulaChanged:     # once, after the formula fix, let it drop to the right value
            if total_load < multi_output_old["Energy"]["Total"]['Load_Energy_Total_kWh']:       #Stop any rounding calculation from making load reduce in Today stats
                energy_total_output['Load_Energy_Total_kWh']=multi_output_old["Energy"]["Total"]['Load_Energy_Total_kWh']
            else:
                energy_total_output['Load_Energy_Total_kWh']=total_load
        else:
            energy_total_output['Load_Energy_Total_kWh']=total_load
            

        # Calculate Self Consumption total to avoid rounding errors
        self_total = max(0,round(energy_total_output['PV_Energy_Total_kWh']-energy_total_output['Export_Energy_Total_kWh'], 2))
        if multi_output_old:
            if self_total< multi_output_old["Energy"]["Total"]['Self_Consumption_Energy_Total_kWh']:       #Stop any rounding calculation from making load reduce in Today stats
                energy_total_output['Self_Consumption_Energy_Total_kWh']=multi_output_old["Energy"]["Total"]['Self_Consumption_Energy_Total_kWh']
            else:
                energy_total_output['Self_Consumption_Energy_Total_kWh']=self_total        
        else:
            energy_total_output['Self_Consumption_Energy_Total_kWh']=self_total

        # Energy Today Figures
        logger.debug("Getting Today Energy Data")
        energy_today_output['PV_Energy_Today_kWh'] = GEInv.e_pv1_day+GEInv.e_pv2_day
        energy_today_output['Import_Energy_Today_kWh'] = GEInv.e_grid_in_day
        energy_today_output['Export_Energy_Today_kWh'] = GEInv.e_grid_out_day

### Does this neeed to be renamed from e_load_day to e_interter_in_day??
        energy_today_output['AC_Charge_Energy_Today_kWh'] = GEInv.e_ac_charge_today
        energy_today_output['Invertor_Energy_Today_kWh'] = GEInv.e_pv_generation_today if GEInv.e_pv_generation_today is not None else GEInv.e_inverter_out_today

        # Calculate Self Consumption and Load to avoid rounding errors
        today_self = max(0,round(energy_today_output['PV_Energy_Today_kWh'], 2)-round(energy_today_output['Export_Energy_Today_kWh'], 2))
        # Calculate Load to avoid rounding errors
        if dcHybrid:
            today_load = max(0,round((energy_today_output['Invertor_Energy_Today_kWh']-energy_today_output['AC_Charge_Energy_Today_kWh']) -
                        (energy_today_output['Export_Energy_Today_kWh']-energy_today_output['Import_Energy_Today_kWh']), 2))
        else:
            today_load= max(0,round((energy_today_output['Invertor_Energy_Today_kWh']-energy_today_output['AC_Charge_Energy_Today_kWh']) -
                        (energy_today_output['Export_Energy_Today_kWh']-energy_today_output['Import_Energy_Today_kWh'])+energy_today_output['PV_Energy_Today_kWh'], 2))
            
        # Load and Self Consumption are calculated, so hold them rather than let rounding make them go down -
        # except on a new inverter day, when the counters have reset and holding would keep yesterday's totals
        if multi_output_old and not newInverterDay(inverter['Invertor_Time'],multi_output_old):
            if today_self < multi_output_old["Energy"]["Today"]['Self_Consumption_Energy_Today_kWh']:
                energy_today_output['Self_Consumption_Energy_Today_kWh']=multi_output_old["Energy"]["Today"]['Self_Consumption_Energy_Today_kWh']
            else:
                energy_today_output['Self_Consumption_Energy_Today_kWh']=today_self
            if today_load < multi_output_old["Energy"]["Today"]['Load_Energy_Today_kWh'] and not formulaChanged:
                energy_today_output['Load_Energy_Today_kWh']=multi_output_old["Energy"]["Today"]['Load_Energy_Today_kWh']
            else:
                energy_today_output['Load_Energy_Today_kWh']=today_load
        else:
            energy_today_output['Load_Energy_Today_kWh']=today_load
            energy_today_output['Self_Consumption_Energy_Today_kWh']=today_self

    ############  Core Power Stats    ############

        # PV Power
        logger.debug("Getting PV Power")
        PV_power_1 = GEInv.p_pv1
        PV_power_2 = GEInv.p_pv2
        PV_power = PV_power_1+PV_power_2
        if PV_power < 15000:
            power_output['PV_Power_String_1'] = PV_power_1
            power_output['PV_Power_String_2'] = PV_power_2
            power_output['PV_Power'] = PV_power
        power_output['PV_Voltage_String_1'] = GEInv.v_pv1
        power_output['PV_Voltage_String_2'] = GEInv.v_pv2
        power_output['PV_Current_String_1'] = GEInv.i_pv1
        power_output['PV_Current_String_2'] = GEInv.i_pv2
        power_output['Grid_Voltage'] = GEInv.v_ac1
        power_output['Grid_Current'] = GEInv.i_grid_port 

        # Grid Power
        logger.debug("Getting Grid Power")
        grid_power = GEInv.p_grid_out
        if grid_power < 0:
            import_power = abs(grid_power)
            export_power = 0
        elif grid_power > 0:
            import_power = 0
            export_power = abs(grid_power)
        else:
            import_power = 0
            export_power = 0
        power_output['Grid_Power'] = grid_power
        power_output['Import_Power'] = import_power
        power_output['Export_Power'] = export_power

        # EPS Power
        logger.debug("Getting EPS Power")
        power_output['EPS_Power'] = GEInv.p_backup

        # Inverter Power
        logger.debug("Getting PInv Power")

### Double check register naming
        inverter_power = GEInv.p_grid_out_ph1
        #inverter_power = GEInv.p_inverter_out
        if -inverterModel.invmaxrate <= inverter_power <=inverterModel.invmaxrate:
            power_output['Invertor_Power'] = inverter_power
        if inverter_power < 0:
            power_output['AC_Charge_Power'] = abs(inverter_power)
        else:
            power_output['AC_Charge_Power'] = 0

        # Load Power
        logger.debug("Getting Load Power")
        Load_power = GEInv.p_load_demand
        #if Load_power < 15500:
        power_output['Load_Power'] = Load_power

        # Self Consumption
        logger.debug("Getting Self Consumption Power")
        power_output['Self_Consumption_Power'] = max(Load_power - import_power, 0)


    ############  Power Flow Stats    ############

        # Solar to H/B/G
        logger.debug("Getting Solar to H/B/G Power Flows")
        if PV_power > 0:
            S2H = min(PV_power, Load_power)
            power_flow_output['Solar_to_House'] = S2H
            power_flow_output['Solar_to_Grid'] = export_power

        else:
            power_flow_output['Solar_to_House'] = 0
            power_flow_output['Solar_to_Grid'] = 0

        # Grid to Battery/House Power
        logger.debug("Getting Grid to Battery/House Power Flow")
        if import_power > 0:
            power_flow_output['Grid_to_House'] = import_power
        else:
            power_flow_output['Grid_to_House'] = 0

    ######## Get Control Data ########

        controlmode={}
        controlmode.update(getControls(plant,regCacheStack,inverterModel,multi_output_old))

        ######## Battery Stats only if there are batteries...  ########

        if batteryCount(plant) > 0:  # only do this if there are batteries

            logger.debug("Getting SOC")
            if GEInv.battery_soc != 0 or GEInv.battery_calibration_stage !=0:        #if we're in calibration mode accept any value
                power_output['SOC'] = GEInv.battery_soc
            elif GEInv.battery_soc == 0 and multi_output_old.get('Power',{}).get('Power',{}).get('SOC') is not None:
                power_output['SOC'] = multi_output_old['Power']['Power']['SOC']
                logger.debug("\"Battery SOC\" reported as: "+str(GEInv.battery_soc)+"% so using previous value")
            elif GEInv.battery_soc == 0:
                power_output['SOC'] = 1
                logger.debug("\"Battery SOC\" reported as: "+str(GEInv.battery_soc)+"% and no previous value so setting to 1%")  
            else:
                power_output['SOC'] = GEInv.battery_soc
            power_output['SOC_kWh'] = round((int(power_output['SOC'])*(inverterModel.batterycapacity))/100,2)

            # Energy Stats
            logger.debug("Getting Battery Energy Data")
            energy_today_output['Battery_Charge_Energy_Today_kWh'] = GEInv.e_battery_charge_today_alt1
            energy_today_output['Battery_Discharge_Energy_Today_kWh'] = GEInv.e_battery_discharge_today_alt1
            energy_today_output['Battery_Throughput_Today_kWh'] = GEInv.e_battery_charge_today_alt1+GEInv.e_battery_discharge_today_alt1
            energy_total_output['Battery_Throughput_Total_kWh'] = GEInv.e_battery_throughput
            
            ############  Battery Power Stats    ############
            logger.debug ("Getting Battery Power data")
            Battery_power = GEInv.p_battery
            if not exists(GivLUT.firstrun):    #GiV_Settings.first_run:          # Make sure that we publish the HA message for both Charge and Discharge times
                power_output['Charge_Time_Remaining'] = 0
                power_output['Charge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
                power_output['Discharge_Time_Remaining'] = 0
                power_output['Discharge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
            if Battery_power >= 0:
                discharge_power = abs(Battery_power)
                charge_power = 0
                power_output['Charge_Time_Remaining'] = 0
                if discharge_power!=0 and controlmode.get('Battery_Power_Reserve') is not None:
                    # Time to get from current SOC to battery Reserve at the current rate
                    power_output['Discharge_Time_Remaining'] = max(int(inverterModel.batterycapacity*((power_output['SOC'] - controlmode['Battery_Power_Reserve'])/100) / (discharge_power/1000) * 60),0)
                    finaltime=datetime.datetime.now() + timedelta(minutes=power_output['Discharge_Time_Remaining'])
                    power_output['Discharge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
                else:
                    power_output['Discharge_Time_Remaining'] = 0
            elif Battery_power <= 0:
                discharge_power = 0
                charge_power = abs(Battery_power)
                power_output['Discharge_Time_Remaining'] = 0
                if charge_power!=0 and controlmode.get('Target_SOC') is not None:
                    # Time to get from current SOC to target SOC at the current rate (Target SOC-Current SOC)xBattery Capacity
                    power_output['Charge_Time_Remaining'] = max(int(inverterModel.batterycapacity*((controlmode['Target_SOC'] - power_output['SOC'])/100) / (charge_power/1000) * 60),0)
                    finaltime=datetime.datetime.now() + timedelta(minutes=power_output['Charge_Time_Remaining'])
                    power_output['Charge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
                else:
                    power_output['Charge_Time_Remaining'] = 0
            power_output['Battery_Power'] = Battery_power
            power_output['Battery_Voltage'] = GEInv.v_battery
            power_output['Battery_Current'] = GEInv.i_battery
            power_output['Charge_Power'] = charge_power
            power_output['Discharge_Power'] = discharge_power
        else:
            Battery_power=0
            charge_power=0
            discharge_power=0


        if GEInv.f_ac1>100:
            freq=GEInv.f_ac1/10
        else:
            freq=GEInv.f_ac1
        power_output['Grid_Frequency'] = freq
        if GEInv.f_ac1_output>100:
            freq=GEInv.f_ac1_output/10
        else:
            freq=GEInv.f_ac1_output
        power_output['Inverter_Output_Frequency'] = freq
        # Not every model in the list has IR 247-248 read (eg. HV Gen 3), so only add it when there is a value
        if resolvedModel(plant, GEInv) in (Model.HYBRID_GEN3, Model.HYBRID_GEN4, Model.HYBRID_HV_GEN3, Model.HYBRID_3PH, Model.ALL_IN_ONE_HYBRID, Model.AIO_COMMERCIAL) \
                and GEInv.p_combined_generation is not None:
            power_output['Combined_Generation_Power'] = GEInv.p_combined_generation

        # Power flows
        logger.debug("Getting Solar to H/B/G Power Flows")
        if PV_power > 0:
            S2H = min(PV_power, Load_power)
            power_flow_output['Solar_to_House'] = S2H
            S2B = max((PV_power-S2H)-export_power, 0)
            power_flow_output['Solar_to_Battery'] = S2B
            power_flow_output['Solar_to_Grid'] = max(PV_power - S2H - S2B, 0)

        else:
            power_flow_output['Solar_to_House'] = 0
            power_flow_output['Solar_to_Battery'] = 0
            power_flow_output['Solar_to_Grid'] = 0

        # Battery to House
        logger.debug("Getting Battery to House Power Flow")
        B2H = max(discharge_power-export_power, 0)
        power_flow_output['Battery_to_House'] = B2H

        # Grid to Battery/House Power
        logger.debug("Getting Grid to Battery/House Power Flow")
        if import_power > 0:
            power_flow_output['Grid_to_Battery'] = charge_power-max(PV_power-Load_power, 0)
            power_flow_output['Grid_to_House'] = max(import_power-charge_power, 0)

        else:
            power_flow_output['Grid_to_Battery'] = 0
            power_flow_output['Grid_to_House'] = 0

        # Battery to Grid Power
        logger.debug("Getting Battery to Grid Power Flow")
        if export_power > 0:
            power_flow_output['Battery_to_Grid'] = max(discharge_power-B2H, 0)
        else:
            power_flow_output['Battery_to_Grid'] = 0

        # Check for all zeros
        checksum = 0
        for item in energy_total_output:
            if not energy_total_output[item] == None:
                checksum = checksum+energy_total_output[item]
        if checksum == 0:
            raise ValueError("All zeros returned by inverter, skipping update")

        ######## Grab Timeslots ########
        res = {}
        res=getTimeslots(plant, multi_output_old)
        timeslots={}
        timeslots.update(res[0])
        controlmode.update(res[1])

        ######## Get Inverter Details ########
        logger.debug("Getting inverter Details")
        inverter['Battery_Type'] = enumText(GEInv.battery_type)
        inverter['Battery_Capacity_kWh'] = inverterModel.batterycapacity        #Ah x nom voltage @ 90%
        if getattr(inverterModel,'ratecapacity',None):
            # So write.py converts a rate in W to the same percentage (HV Gen 3, #604)
            inverter['Battery_Rate_Capacity_kWh'] = inverterModel.ratecapacity
        inverter['Invertor_Serial_Number'] = plant.inverter_serial_number
        inverter['Modbus_Version'] = GEInv.modbus_version
        inverter['Invertor_Firmware'] = GEInv.firmware_version
        inverter['Meter_Type'] = enumText(GEInv.meter_type)
        inverter['Invertor_Type'] = resolvedModel(plant, GEInv).name.capitalize()
        inverter['Invertor_Max_Inv_Rate'] = inverterModel.invmaxrate
        inverter['Invertor_Max_Bat_Rate'] = inverterModel.batmaxrate
        inverter['Invertor_Temperature'] = GEInv.t_inverter_heatsink
        inverter['Export_Limit']=GEInv.grid_port_max_power_output
        inverter['Battery_Calibration_Status'] = enumText(GEInv.battery_calibration_stage)

        ######## Get Meter Details ########

        meters={}
        meters.update(getMeters(plant))

        ######## Get Battery Details ########

        batteries2 = {}
        batteries2.update(getBatteries(plant,multi_output_old) or {})
        if isHV:
            # Calc HV stack capacity as function of stacks
            cap=0
            for stack in batteries2:
                cap=cap+(batteries2[stack].get('Stack_Design_Capacity') or 0)      #Ah x nom voltage @ 90%
            inverter['Battery_Capacity_kWh_calc'] = cap

            ######## Create multioutput and publish #########
        energy = {}
        energy["Today"] = energy_today_output
        energy["Total"] = energy_total_output
        power = {}
        power["Power"] = power_output
        power["Flows"] = power_flow_output
        multi_output["Power"] = power
        multi_output[GEInv.serial_number] = inverter
        multi_output["Energy"] = energy
        multi_output["Timeslots"] = timeslots
        multi_output["Control"] = controlmode
        multi_output["Battery_Details"] = batteries2
        multi_output["Meter_Details"] = meters
        if GiV_Settings.Print_Raw_Registers:
            multi_output['raw'] = getRaw(plant)
    except KeyError as e:
        missing_key = e.args[0] if e.args else None
        logger.error("Key Error getting Data: missing key "+repr(missing_key)+" - "+errDetail())
    except Exception as e:
        logger.error("Error processing Inverter data: "+errDetail())
        return None
    return multi_output

def processEMSInfo(plant: Plant):
    # givenergy-modbus v2: plant.ems holds the EMS block (HR/IR 2040+). Identity values (serial, firmware,
    # time, export limit) come from the HR(0-60) bank, which v2 polls for EMS, via the inverter view over
    # the same register cache. IR(0-60) is not polled for EMS, so there are no inverter-style energy totals
    try:
        multi_output={}
        GEInv=plant.ems
        GEHR=plant.inverter

        regCacheStack=GivLUT.get_regcache()
        multi_output_old=regCacheStack[-1] if regCacheStack else {}

        def enumName(enum,value):
            # v2 EMS model stores enums as raw values (use_enum_values=True)
            if value is None:
                return None
            try:
                return enum(value).name.capitalize()
            except ValueError:
                return str(value)

        ems={}
        ems['status']=enumName(Status,GEInv.ems_status)
        ems['Plant_Status']=enumName(Status,GEInv.plant_status)
        ems['Inverter_Count']=GEInv.inverter_count
        ems['Meter_Count']=GEInv.meter_count
        ems['Car_Charge_Count']=GEInv.expected_car_charger_count
        ems['Serial_Number']=plant.inverter_serial_number
        ems['Invertor_Type'] = plant.capabilities.device_type.name.capitalize()
        ems['Invertor_Firmware']=GEHR.firmware_version
        if GEHR.system_time:
            ems['Invertor_Time']=GEHR.system_time.replace(tzinfo=GivLUT.timezone).isoformat()
        ems['Remaining_Battery_Wh']=GEInv.remaining_battery_wh
        ems['Invertor_Serial_Number']=plant.inverter_serial_number
        ems['Export_Limit']=GEHR.grid_port_max_power_output

        inverters={}
        for i in range(1,MAX_MANAGED_INVERTERS+1):
            serial=getattr(GEInv,'inverter_'+str(i)+'_serial_number')
            serial=serial.strip("\x00 ") if serial else None
            if not serial:
                continue
            inv={}
            inv['Power']=getattr(GEInv,'inverter_'+str(i)+'_power')
            inv['SOC']=getattr(GEInv,'inverter_'+str(i)+'_soc')
            inv['Temperature']=getattr(GEInv,'inverter_'+str(i)+'_temp')
            inv['Serial_Number']=serial
            # Raw EMS slot status code is undocumented; publish the lib's suspected label where it knows it
            suspected=getattr(GEInv,'inverter_'+str(i)+'_suspected_status')
            inv['status']=enumName(EmsInverterStatus,suspected) if suspected is not None else getattr(GEInv,'inverter_'+str(i)+'_status')
            inverters[serial]=inv

        power_output={}
        power_output['Grid_Power']=GEInv.grid_meter_power
        power_output['Calculated_Load_Power']=GEInv.calc_load_power
        power_output['Measured_Load_Power']=GEInv.measured_load_power
        power_output['Generation_Load_Power']=GEInv.total_generation_load_power
        power_output['Battery_Power']=GEInv.total_battery_power
        power_output['Other_Battery_Power']=GEInv.other_battery_power

        energy={}
        energy_total_output = {}
        energy_today_output = {}
        if GEInv.e_active_generation_total is not None:
            energy_total_output['Generation_Energy_Total_kWh']=GEInv.e_active_generation_total

        meter={}
        for i in range(1,9):
            meter['Meter_'+str(i)+'_Power']=getattr(GEInv,'meter_'+str(i)+'_power')
        for i in range(1,9):
            meter['Meter_'+str(i)+'_Status']=enumName(MeterStatus,getattr(GEInv,'meter_'+str(i)+'_status'))

        controlmode = {}
        controlmode['Plant_Control']="enable" if GEInv.plant_enabled else "disable"
        controlmode['EMS_Discharge_Target_SOC_1']=GEInv.discharge_target_1
        controlmode['EMS_Discharge_Target_SOC_2']=GEInv.discharge_target_2
        controlmode['EMS_Discharge_Target_SOC_3']=GEInv.discharge_target_3
        controlmode['EMS_Charge_Target_SOC_1']=GEInv.charge_target_1
        controlmode['EMS_Charge_Target_SOC_2']=GEInv.charge_target_2
        controlmode['EMS_Charge_Target_SOC_3']=GEInv.charge_target_3
        controlmode['Export_Target_SOC_1']=GEInv.export_target_1
        controlmode['Export_Target_SOC_2']=GEInv.export_target_2
        controlmode['Export_Target_SOC_3']=GEInv.export_target_3
        controlmode['Export_Power_Limit']=GEInv.export_power_limit
        mode=GEInv.car_charge_mode
        controlmode['Car_Charge_Mode']=GivLUT.car_charge_mode[mode] if mode is not None and 0<=mode<len(GivLUT.car_charge_mode) else mode
        controlmode['Car_Charge_Boost']=GEInv.car_charge_boost
        controlmode['Plant_Charge_Compensation']=GEInv.plant_charge_compensation
        controlmode['Plant_Discharge_Compensation']=GEInv.plant_discharge_compensation

        timeslots = {}
        logger.debug("Getting TimeSlot data")
        for prefix,attr in (('EMS_Discharge','discharge_slot_'),('EMS_Charge','charge_slot_'),('Export','export_slot_')):
            for i in range(1,4):
                slot=getattr(GEInv,attr+str(i))
                for end in ('start','end'):
                    key=prefix+'_'+end+'_time_slot_'+str(i)
                    timeslots[key]=validateTimeslot(getattr(slot,end) if slot else None,key,multi_output_old)

        if GiV_Settings.Print_Raw_Registers:
            multi_output['raw'] = getRaw(plant)

        multi_output['Power']=power_output
        multi_output['Power']['Meters']=meter
        multi_output['Inverters']=inverters
        multi_output['Control']=controlmode
        multi_output['Timeslots']=timeslots
        multi_output[plant.inverter_serial_number]=ems
        energy['Today']=energy_today_output
        energy['Total']=energy_total_output
        multi_output['Energy']=energy
    except KeyError as e:
        missing_key = e.args[0] if e.args else None
        logger.error("Key Error getting EMS Data: missing key "+repr(missing_key)+" - "+errDetail())
        return None
    except Exception:
        logger.error("Error processing EMS data: " + errDetail())
        return None
    return multi_output

def processGatewayInfo(plant: Plant):
    try:
        GEInv=plant.gateway
        # givenergy-modbus v2's Gateway model only covers the IR 1600+ block. Holding-register values
        # (time, limits, export limit) come from the inverter view over the same register cache
        GEHR=plant.inverter
        inverterModel=InvType
        inverterModel=getInvModel(plant)

        regCacheStack=GivLUT.get_regcache()
        if not regCacheStack:
            regCacheStack = []      # no cache yet (first poll) - previous values default to empty
            multi_output_old = {}
        else:
            multi_output_old=regCacheStack[-1]

        multi_output={}
        gateway={}
        gateway['Invertor_Type'] = Model.GATEWAY.name.capitalize()
        gateway['Invertor_Serial_Number']=plant.inverter_serial_number
        #gateway['Invertor_Firmware']=GEInv.firmware_version
        gateway['Gateway_Software_Version']=GEInv.software_version
        gateway['Parallel_Total_AIO_Number']=GEInv.parallel_aio_num
        gateway['Parallel_Total_AIO_Online_Number']=GEInv.parallel_aio_online_num
        # v2 Gateway model stores enums as raw values (use_enum_values=True)
        gateway['Gateway_State']=State(GEInv.aio_state).name.capitalize()
        gateway['Gateway_Mode']=WorkMode(GEInv.work_mode).name.replace("_"," ").capitalize()
        gateway['Export_Limit']=GEHR.grid_port_max_power_output
        gateway['Battery_Capacity_kWh'] = inverterModel.batterycapacity
        gateway['Invertor_Time']=GEHR.system_time.replace(tzinfo=GivLUT.timezone).isoformat()
        gateway['Invertor_Max_Inv_Rate'] = inverterModel.invmaxrate
        gateway['Invertor_Max_Bat_Rate'] = inverterModel.batmaxrate


        #gateway['DO_State']=GEInv.do_state
        #gateway['DI_State']=GEInv.di_state

        power_output={}
        power_output['Grid_Voltage']=GEInv.v_grid
        power_output['Grid_Current']=GEInv.i_grid
        power_output['Load_Voltage']=GEInv.v_load
        power_output['Load_Current']=GEInv.i_load
        power_output['PV_Current']=GEInv.i_pv
        power_output['Grid_Power']=GEInv.p_ac1
        power_output['PV_Power']=GEInv.p_pv
        power_output['Load_Power']=GEInv.p_load
        #power_output['Parallel_Load_Power']=GEInv.parallel_aio_load_power
        # givenergy-modbus 2.x already reports the Gateway's AIO powers (p_aio_total, p_liberty, p_aio<n>_inverter)
        # positive for discharge (givenergy-modbus#372), so they aren't inverted here as they were for the old library
        power_output['Battery_Power']=GEInv.p_aio_total      # For Gateway we proxy battery by invertor power minus PV
        power_output['Liberty_Power']=GEInv.p_liberty
        power_output['Grid_Relay_Voltage']=GEInv.v_grid_relay
        power_output['Inverter_Relay_Voltage']=GEInv.v_inverter_relay
        power_output['Invertor_Power']=GEInv.p_aio_total
        
        controlmode={}    
        timeslots={}
        #Only implement these, if Parallel mode is in use
        if GEInv.parallel_aio_online_num>1:
            controlmode=getControls(plant,regCacheStack,inverterModel,multi_output_old)
            #(Dis)charge Rate controls are generated in getControls, same approach as 3PH
            logger.debug("Getting TimeSlot data")
            res = {}
            res=getTimeslots(plant, multi_output_old)
            timeslots.update(res[0])
            controlmode.update(res[1])
        power={}
        
    ### Is this bit right? If not parallel then are there multiple aios to check? Can you have multiple AIOs not in parallel mode?
        if GEInv.parallel_aio_num>1:
        #    power_output['SOC']=GEInv.parallel_aio_soc
        #    power_output['SOC_kWh'] = round((int(power_output['SOC'])*(inverterModel.batterycapacity))/100,2)
        #else:
            # Calc based on individual SOCs
            count=0
            total=0
            if GEInv.aio1_soc:
                total=total+GEInv.aio1_soc
                count=count+1
            if GEInv.aio2_soc:
                total=total+GEInv.aio2_soc
                count=count+1
            if GEInv.aio3_soc:
                total=total+GEInv.aio3_soc
                count=count+1
            if not count==0:
                average=int(total/count)
                power_output['SOC']=average
                power_output['SOC_kWh'] = round((int(power_output['SOC'])*(inverterModel.batterycapacity))/100,2)

                Battery_power=GEInv.p_aio_total
                if Battery_power >= 0:
                    discharge_power = abs(Battery_power)
                    charge_power = 0
                    power_output['Charge_Time_Remaining'] = 0
                    #power_output['Charge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
                    if discharge_power!=0 and controlmode.get('Battery_Power_Reserve') is not None:
                        # Time to get from current SOC to battery Reserve at the current rate
                        power_output['Discharge_Time_Remaining'] = max(int(inverterModel.batterycapacity*((power_output['SOC'] - controlmode['Battery_Power_Reserve'])/100) / (discharge_power/1000) * 60),0)
                        finaltime=datetime.datetime.now() + timedelta(minutes=power_output['Discharge_Time_Remaining'])
                        power_output['Discharge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
                    else:
                        power_output['Discharge_Time_Remaining'] = 0
                        #power_output['Discharge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
                elif Battery_power <= 0:
                    discharge_power = 0
                    charge_power = abs(Battery_power)
                    power_output['Discharge_Time_Remaining'] = 0
                    #power_output['Discharge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
                    if charge_power!=0 and controlmode.get('Target_SOC') is not None:
                        # Time to get from current SOC to target SOC at the current rate (Target SOC-Current SOC)xBattery Capacity
                        power_output['Charge_Time_Remaining'] = max(int(inverterModel.batterycapacity*((controlmode['Target_SOC'] - power_output['SOC'])/100) / (charge_power/1000) * 60),0)
                        finaltime=datetime.datetime.now() + timedelta(minutes=power_output['Charge_Time_Remaining'])
                        power_output['Charge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
                    else:
                        power_output['Charge_Time_Remaining'] = 0

                grid_power = GEInv.p_ac1
                if grid_power < 0:
                    import_power = abs(grid_power)
                    export_power = 0
                elif grid_power > 0:
                    import_power = 0
                    export_power = abs(grid_power)
                else:
                    import_power = 0
                    export_power = 0

                # Power flows
                power_flow_output={}
                logger.debug("Getting Solar to H/B/G Power Flows")
                if GEInv.p_pv > 0:
                    S2H = min(GEInv.p_pv, GEInv.p_load)
                    power_flow_output['Solar_to_House'] = S2H
                    S2B = max((GEInv.p_pv-S2H)-export_power, 0)
                    power_flow_output['Solar_to_Battery'] = S2B
                    power_flow_output['Solar_to_Grid'] = max(GEInv.p_pv - S2H - S2B, 0)

                else:
                    power_flow_output['Solar_to_House'] = 0
                    power_flow_output['Solar_to_Battery'] = 0
                    power_flow_output['Solar_to_Grid'] = 0

                # Battery to House
                logger.debug("Getting Battery to House Power Flow")
                B2H = max(discharge_power-export_power, 0)
                power_flow_output['Battery_to_House'] = B2H

                # Grid to Battery/House Power
                logger.debug("Getting Grid to Battery/House Power Flow")
                if import_power > 0:
                    power_flow_output['Grid_to_Battery'] = charge_power-max(GEInv.p_pv-GEInv.p_load, 0)
                    power_flow_output['Grid_to_House'] = max(import_power-charge_power, 0)

                else:
                    power_flow_output['Grid_to_Battery'] = 0
                    power_flow_output['Grid_to_House'] = 0

                # Battery to Grid Power
                logger.debug("Getting Battery to Grid Power Flow")
                if export_power > 0:
                    power_flow_output['Battery_to_Grid'] = max(discharge_power-B2H, 0)
                else:
                    power_flow_output['Battery_to_Grid'] = 0
            power["Flows"] = power_flow_output

        inverters={}
        swv=int(GEInv.software_version[-2:])
        if GEInv.e_aio1_charge_today:
            inv1={}
            inv1['AC_Charge_Energy_Today_kWh']=GEInv.e_aio1_charge_today
            inv1['AC_Charge_Energy_Total_kWh']=round(GEInv.e_aio1_charge_total/1000,2)
            inv1['AC_Discharge_Energy_Today_kWh']=GEInv.e_aio1_discharge_today
            inv1['AC_Discharge_Energy_Total_kWh']=round(GEInv.e_aio1_discharge_total/1000,2)
            inv1['SOC']=GEInv.aio1_soc
            inv1['Invertor_Power']=GEInv.p_aio1_inverter
            inv1['AIO_1_Serial_Number']=GEInv.aio1_serial_number
            #inverters[GEInv.aio1_serial_number]=inv1
            inverters["AIO_1"]=inv1
        if GEInv.e_aio2_charge_today:
            inv2={}
            inv2['AC_Charge_Energy_Today_kWh']=GEInv.e_aio2_charge_today
            inv2['AC_Charge_Energy_Total_kWh']=round(GEInv.e_aio2_charge_total/1000,2)
            inv2['AC_Discharge_Energy_Today_kWh']=GEInv.e_aio2_discharge_today
            inv2['AC_Discharge_Energy_Total_kWh']=round(GEInv.e_aio2_discharge_total/1000,2)
            inv2['SOC']=GEInv.aio2_soc
            inv2['Invertor_Power']=GEInv.p_aio2_inverter
            inv2['AIO_2_Serial_Number']=GEInv.aio2_serial_number
            #inverters[GEInv.aio2_serial_number]=inv2
            inverters["AIO_2"]=inv2
        if GEInv.e_aio3_charge_today:
            inv3={}
            inv3['AC_Charge_Energy_Today_kWh']=GEInv.e_aio3_charge_today
            inv3['AC_Charge_Energy_Total_kWh']=round(GEInv.e_aio3_charge_total/1000,2)
            inv3['AC_Discharge_Energy_Today_kWh']=GEInv.e_aio3_discharge_today
            inv3['AC_Discharge_Energy_Total_kWh']=round(GEInv.e_aio3_discharge_total/1000,2)
            inv3['SOC']=GEInv.aio3_soc
            inv3['Invertor_Power']=GEInv.p_aio3_inverter
            inv3['AIO_3_Serial_Number']=GEInv.aio3_serial_number
            #inverters[GEInv.aio3_serial_number]=inv3
            inverters["AIO_3"]=inv3
        
        energy = {}
        energy_today_output={}
        energy_today_output['Export_Energy_Today_kWh']=GEInv.e_grid_export_today
        energy_today_output['PV_Energy_Today_kWh']=GEInv.e_pv_today
        energy_today_output['Import_Energy_Today_kWh']=GEInv.e_grid_import_today
        energy_today_output['Load_Energy_Today_kWh']=GEInv.e_load_today
        energy_today_output['Battery_Charge_Energy_Today_kWh']=GEInv.e_battery_charge_today
        energy_today_output['Battery_Discharge_Energy_Today_kWh']=GEInv.e_battery_discharge_today
        energy_today_output['Parallel_Total_Charge_Energy_Today_kWh']=GEInv.e_aio_charge_today
        energy_today_output['Parallel_Total_Discharge_Energy_Today_kWh']=GEInv.e_aio_discharge_today

        energy_total_output={}
        energy_total_output['Import_Energy_Total_kWh']=round(GEInv.e_grid_import_total/1000,2)
        energy_total_output['PV_Energy_Total_kWh']=round(GEInv.e_pv_total/1000,2)
        energy_total_output['Export_Energy_Total_kWh']=round(GEInv.e_grid_export_total/1000,2)
        energy_total_output['Load_Energy_Total_kWh']=round(GEInv.e_load_total/1000,2)
        energy_total_output['Battery_Charge_Energy_Total_kWh']=round(GEInv.e_battery_charge_total/1000,2)
        energy_total_output['Battery_Discharge_Energy_Total_kWh']=round(GEInv.e_battery_discharge_total/1000,2)
        energy_total_output['Parallel_Total_Charge_Energy_Total_kWh']=round(GEInv.e_aio_charge_total/1000,2)
        energy_total_output['Parallel_Total_Discharge_Energy_Total_kWh']=round(GEInv.e_aio_discharge_total/1000,2)
        

        ######## Get Meter Details ########

        meters={}
        meters.update(getMeters(plant))

        if GiV_Settings.Print_Raw_Registers:
            multi_output['raw'] = getRaw(plant)

        energy["Today"] = energy_today_output
        energy["Total"] = energy_total_output
        power['Power']=power_output
        multi_output['Inverters']=inverters
        multi_output["Power"]  = power
        multi_output["Energy"] = energy
        if timeslots:
            multi_output["Timeslots"] = timeslots
        if controlmode:
            multi_output["Control"] = controlmode
        multi_output[plant.inverter_serial_number]=gateway
        multi_output["Meter_Details"] = meters
    except KeyError as e:
        missing_key = e.args[0] if e.args else None
        logger.error("Key Error getting Battery Data: missing key "+repr(missing_key)+" - "+errDetail())
    except Exception as e:
        logger.error("Error processing Gateway data: "+errDetail())
        return None

    return multi_output

def processThreePhaseInfo(plant: Plant):
    try:
        GEInv=plant.inverter
        inverterModel = InvType
        multi_output={}
        inverter={}
        regCacheStack=GivLUT.get_regcache()
        if not regCacheStack:
            regCacheStack = []      # no cache yet (first poll) - previous values default to empty
            multi_output_old = {}
        else:
            multi_output_old=regCacheStack[-1]

        # Check a couple of obvious data points to reject bad reads
        if float(GEInv.modbus_version)>2 or GEInv.modbus_address>100 or GEInv.user_code>100 or GEInv.t_inverter_heatsink>100:
            logger.debug("Dodgy Data so using last cache...")
            return multi_output_old

        # If System Time is wrong (default date) use last good time or local time if all else fails
        if GEInv.system_time is None or GEInv.system_time.year == 2000:     # unreadable or default date
            #Use old Sys_Time
            logger.debug("Inverter Time is default... fixing it")
            inverter['Invertor_Time'] = finditem(multi_output_old,"Invertor_Time")
            if inverter['Invertor_Time']==None:
            # Unless its missing then use now()
                inverter['Invertor_Time']=datetime.datetime.now(GivLUT.timezone).isoformat(timespec='seconds')
        else:
            # Use latest data if its not default date
            inverter['Invertor_Time'] = GEInv.system_time.replace(tzinfo=GivLUT.timezone).isoformat(timespec='seconds')
        inv_time=datetime.datetime.strptime(inverter['Invertor_Time'], '%Y-%m-%dT%H:%M:%S%z')

        if GiV_Settings.Print_Raw_Registers:
            multi_output['raw'] = getRaw(plant)

        inverterModel=getInvModel(plant)

        energy_today_output={}
        energy_today_output['Inverter_Out_Energy_Today_kWh']=GEInv.e_inverter_out_today
        energy_today_output['PV1_Energy_Today_kWh']=GEInv.e_pv1_today
        energy_today_output['PV_Energy_Today_kWh']=GEInv.e_pv2_today
        energy_today_output['AC_Charge_Energy_Today_kWh']=GEInv.e_ac_charge_today
        energy_today_output['Import_Energy_Today_kWh']=GEInv.e_import_today
        energy_today_output['Export_Energy_Today_kWh']=GEInv.e_export_today
        # Three-phase battery energy today (IR1388/9, IR1392/3), matching the totals below (IR1390/1, IR1394/5)
        # rather than the single-phase layout alt1 registers (IR36/37)
        energy_today_output['Battery_Discharge_Energy_Today_kWh']=GEInv.e_battery_discharge_today
        energy_today_output['Battery_Charge_Energy_Today_kWh']=GEInv.e_battery_charge_today
        energy_today_output['Load_Energy_Today_kWh']=GEInv.e_load_today
        energy_today_output['Export2_Energy_Today_kWh']=GEInv.e_export2_today
        energy_today_output['PV_Energy_Today_kWh']=GEInv.e_pv_today
        energy_total_output={}
        energy_total_output['Inverter_Out_Energy_Total_kWh']=GEInv.e_inverter_out_total
        energy_total_output['PV1_Energy_Total_kWh']=GEInv.e_pv1_total
        energy_total_output['PV2_Energy_Total_kWh']=GEInv.e_pv2_total
        energy_total_output['AC_Charge_Energy_Total_kWh']=GEInv.e_ac_charge_total
        energy_total_output['Import_Energy_Total_kWh']=GEInv.e_import_total
        energy_total_output['Export_Energy_Total_kWh']=GEInv.e_export_total
        energy_total_output['Battery_Discharge_Energy_Total_kWh']=GEInv.e_battery_discharge_total
        energy_total_output['Battery_Charge_Energy_Total_kWh']=GEInv.e_battery_charge_total
        energy_total_output['Load_Energy_Total_kWh']=GEInv.e_load_total
        energy_total_output['Export2_Energy_Total_kWh']=GEInv.e_export2_total
        energy_total_output['PV_Energy_Total_kWh']=GEInv.e_pv_total

        power_output={}
        power_output['Export_Power']=GEInv.p_export
        power_output['Meter2_Power']=GEInv.p_meter2
        power_output['EPS_Phase1_Power']=GEInv.p_eps_ac1
        power_output['EPS_Phase2_Power']=GEInv.p_eps_ac2
        power_output['EPS_Phase3_Power']=GEInv.p_eps_ac3
        power_output['Battery_Charge_Power']=GEInv.p_battery_charge
        power_output['Battery_Discharge_Power']=GEInv.p_battery_discharge
        power_output['Inverter_Power_Out']=GEInv.p_grid_out_ph1
        power_output['AC_Charge_Power']=GEInv.p_inverter_ac_charge
        power_output['Grid_Apparent_Power']=GEInv.p_grid_apparent
        power_output['Meter_Import_Power']=GEInv.p_meter_import
        power_output['Meter_Export_Power']=GEInv.p_meter_export
        power_output['Load_Phase1_Power']=GEInv.p_meter_active_ac1
        power_output['Load_Phase2_Power']=GEInv.p_meter_active_ac2
        power_output['Load_Phase3_Power']=GEInv.p_meter_active_ac3
        power_output['Load_Power']=GEInv.p_load_all
        power_output['Export_Phase1_Power']=GEInv.p_inverter_active_ac1
        power_output['Export_Phase2_Power']=GEInv.p_inverter_active_ac2
        power_output['Export_Phase3_Power']=GEInv.p_inverter_active_ac3
        power_output['PV_Voltage_String_1']=GEInv.v_pv1
        power_output['PV_Voltage_String_2']=GEInv.v_pv2
        power_output['PV_Current_String_1']=GEInv.i_pv1
        power_output['PV_Current_String_2']=GEInv.i_pv2
        power_output['PV_Power_String_1']=GEInv.p_pv1
        power_output['PV_Power_String_2']=GEInv.p_pv2
        power_output['PV_Power']=GEInv.p_pv1+GEInv.p_pv2
        power_output['PV_Current']=GEInv.i_pv1+GEInv.i_pv2
        power_output['Grid_Phase1_Voltage']=GEInv.v_ac1
        power_output['Grid_Phase2_Voltage']=GEInv.v_ac2
        power_output['Grid_Phase3_Voltage']=GEInv.v_ac3
        power_output['Output_Phase1_Voltage']=GEInv.v_out_ac1
        power_output['Output_Phase2_Voltage']=GEInv.v_out_ac2
        power_output['Output_Phase3_Voltage']=GEInv.v_out_ac3
        power_output['Grid_Phase1_Current']=GEInv.i_ac1
        power_output['Grid_Phase2_Current']=GEInv.i_ac2
        power_output['Grid_Phase3_Current']=GEInv.i_ac3
        power_output['Grid_Frequency']=GEInv.f_ac1
        power_output['SOC']=GEInv.battery_soc
        power_output['Battery_Current']=GEInv.i_battery
        power_output['PCS_Voltage']=GEInv.v_battery_pcs
        power_output['BMS_Voltage']=GEInv.v_battery_bms
        power_output['EPS_Nominal_Frequency']=GEInv.f_nominal_eps

        ######## Get Battery Details ########

        batteries2 = {}
        batteries2 = getBatteries(plant, multi_output_old)
        sockwh = 0
        count = 0
        if batteries2:
            for stack in batteries2:
                stack_data = batteries2[stack]
                if isinstance(stack_data, dict) and 'Stack_SOC_kWh' in stack_data:
                    sockwh = sockwh + stack_data['Stack_SOC_kWh']
                    count += 1
        power_output['SOC_kWh'] = sockwh / count if count > 0 else 0                                      # Average SOC of all stacks...

        inverter['status']=enumText(GEInv.status)
        # givenergy-modbus v2 decodes system_mode and battery_priority as plain ints (the old lib used enums)
        inverter['System_Mode']=GivLUT.tph_system_mode.get(GEInv.system_mode,str(GEInv.system_mode))
        inverter['Start_Delay_Time']=GEInv.start_delay_time
        inverter['Power_Factor']=GEInv.power_factor
        inverter['Battery_Type'] = enumText(GEInv.battery_type)
        inverter['Invertor_Type'] = "Gen 3 - " + resolvedModel(plant, GEInv).name.capitalize()
        inverter['Invertor_Max_Bat_Rate'] = inverterModel.batmaxrate
        inverter['Invertor_Max_Inv_Rate'] = GEInv.inverter_max_power
        inverter['Battery_Priority']=GivLUT.tph_battery_priority.get(GEInv.battery_priority,str(GEInv.battery_priority))

    # Calc HV stack capacity as function of stacks
        cap=0
        if batteries2:
            for stack in batteries2:
                stack_data = batteries2[stack]
                if isinstance(stack_data, dict) and 'Stack_Design_Capacity' in stack_data:
                    cap = cap + stack_data['Stack_Design_Capacity']
        inverter['Battery_Capacity_kWh'] = cap

        inverter['Inverter_Temperature']=GEInv.t_inverter
        inverter['Boost_Temperature']=GEInv.t_boost
        inverter['Buck_Boost_Temperature']=GEInv.t_buck_boost
        inverter['DC_Status']=enumText(GEInv.dc_status)
        inverter['Invertor_Serial_Number']=plant.inverter_serial_number
        inverter['Invertor_Software']=GEInv.tph_software_version
        inverter['Invertor_Firmware']=GEInv.tph_firmware_version
        inverter['Battery_Calibration_Status'] = enumText(GEInv.battery_calibration_stage)
        firmware=GEInv.firmware_version

        controlmode={}
        # do the standard control apply to 3ph?

        controlmode.update(getControls(plant,regCacheStack,inverterModel,multi_output_old))

        # v2 decodes these as bools (HR1122 is force_discharge_enable; enable_discharge is now the
        # single-phase HR59), but the HA switches and the Force Charge/Export revert expect "enable"/"disable"
        if not GEInv.force_discharge_enable==None:
            controlmode['Force_Discharge_Enable']="enable" if GEInv.force_discharge_enable else "disable"
        elif multi_output_old:
            controlmode['Force_Discharge_Enable']=multi_output_old['Control']['Force_Discharge_Enable']
        else:
            controlmode['Force_Discharge_Enable']="disable"    #Default to off

        if not GEInv.force_charge_enable==None:
            controlmode['Force_Charge_Enable']="enable" if GEInv.force_charge_enable else "disable"
        elif multi_output_old:
            controlmode['Force_Charge_Enable']=multi_output_old['Control']['Force_Charge_Enable']
        else:
            controlmode['Force_Charge_Enable']="disable"    #Default to off

        if not GEInv.ac_charge_enable==None:
            controlmode['Force_AC_Charge_Enable']="enable" if GEInv.ac_charge_enable else "disable"
        elif multi_output_old:
            controlmode['Force_AC_Charge_Enable']=multi_output_old['Control']['Force_AC_Charge_Enable']
        else:
            controlmode['Force_AC_Charge_Enable']="disable"    #Default to off

        ######## Get Meter Details ########

        meters={}
        meters.update(getMeters(plant))

        timeslots={}
        logger.debug("Getting TimeSlot data")
        res = {}
        res=getTimeslots(plant)
        timeslots.update(res[0])
        controlmode.update(res[1])

        energy = {}
        energy["Today"] = energy_today_output
        energy["Total"] = energy_total_output
        power = {}
        power["Power"] = power_output
        multi_output["Battery_Details"]=batteries2
        multi_output["Power"] = power
        multi_output[GEInv.serial_number] = inverter
        multi_output["Meter_Details"] = meters
        multi_output["Energy"] = energy
        multi_output["Timeslots"] = timeslots
        multi_output["Control"] = controlmode
    except KeyError as e:
        missing_key = e.args[0] if e.args else None
        logger.error("Key Error getting Battery Data: missing key "+repr(missing_key)+" - "+errDetail())
    except Exception as e:
        logger.error("Error processing Three Phase data: "+errDetail())
        return None
    return multi_output

def processData(plant: Plant):
    multi_output = {}
    result = {}
    cleanRegCache = {}
    try:
        logger.debug("Beginning parsing of Inverter data")
        # HR(0), the device type, is missing until the holding registers have been read, eg. if the first read after
        # a restart failed (#608). Processing needs that block (model, firmware, rates), so say so plainly
        devicetype=plant.register_caches.get(plant.capabilities.inverter_address,{}).get(HR(0))
        if devicetype is None:
            raise Exception("Inverter settings not read yet")
        modeltype=hex(devicetype)[2:4]
        if modeltype=="23":
            multi_output=processPVInfo(plant)
        elif plant.capabilities.is_ems:
            multi_output=processEMSInfo(plant)
        elif plant.capabilities.is_gateway:
            multi_output=processGatewayInfo(plant)
        elif plant.capabilities.is_three_phase:
            multi_output=processThreePhaseInfo(plant)
        else:
            multi_output=processInverterInfo(plant)

        if not multi_output:
            raise Exception ("Process Data Failure")

        givtcpdata={}
        givtcpdata['Last_Updated_Time'] = datetime.datetime.now(GivLUT.timezone).isoformat()
        givtcpdata['status'] = "online"
        givtcpdata['Time_Since_Last_Update'] = 0
        givtcpdata['GivTCP_Version']= "3.5"
        age=dataAge(plant)
        givtcpdata['Data_Age']= round(age,1) if age is not None else -1
        if age is None or age > max(3*GiV_Settings.self_run_timer, 60):
            logger.warning("Inverter data is stale (%s s old), values may be held from last good read", givtcpdata['Data_Age'])

        count=0
        if exists(GivLUT.writecountpkl):
            with open(GivLUT.writecountpkl, 'rb') as inp:
                count = pickle.load(inp)
        givtcpdata['Write_Count']= count
        safecount=0
        if exists(GivLUT.safewritecountpkl):
            with open(GivLUT.safewritecountpkl, 'rb') as inp:
                safecount = pickle.load(inp)
        givtcpdata['Safe_Write_Count']= safecount

        multi_output['Stats']=givtcpdata
        checkInverterClock(finditem(multi_output,"Invertor_Time"))
        regCacheStack = GivLUT.get_regcache()
        if regCacheStack is None and exists(GivLUT.regcache):  # Transient failure - retry once (no file yet is normal on first run)
            logger.warning("regCache read failed, retrying...")
            time.sleep(1)
            regCacheStack = GivLUT.get_regcache()
        if not regCacheStack:
            regCacheStack = []
        logger.debug("cache len= "+str(len(regCacheStack)))

### Temp remove for givmod v2+
        # Min/Max pre-cleanse
#        if len(regCacheStack)>0:
#            multi_output=dataCleansing(multi_output,regCacheStack[-1])


### Outlier removal for multi_output
#        if len(regCacheStack)>20:
#            logger.debug("Running outlier removal")
#            multi_output,regCacheStack  = outlierRemoval(multi_output,regCacheStack)
#            logger.debug("outlier removal Complete")
#        else:
#            logger.debug("outlier removal not carried out: cache too small")

        # run ppkwh stats on firstrun and every half hour
        if batteryCount(plant)>0:    #Don't run ratecalcs if no batteries
            if len(regCacheStack)>1:
                multi_output = ratecalcs(multi_output, regCacheStack[-1])
            else:
                multi_output = ratecalcs(multi_output, multi_output)
            multi_output = calcBatteryValue(multi_output)
            logger.debug("Battery rate calcs complete")


        # Get lastupdate from pickle if it exists
        if exists(GivLUT.lastupdate):
            with open(GivLUT.lastupdate, 'rb') as inp:
                previousUpdate = pickle.load(inp)
            timediff = datetime.datetime.fromisoformat(multi_output['Stats']['Last_Updated_Time'])-datetime.datetime.fromisoformat(previousUpdate)
            multi_output['Stats']['Time_Since_Last_Update'] = (((timediff.seconds*1000000)+timediff.microseconds)/1000000)

        # Save new time to pickle
        with open(GivLUT.lastupdate, 'wb') as outp:
            pickle.dump(multi_output['Stats']['Last_Updated_Time'], outp, pickle.HIGHEST_PROTOCOL)

        
        # Add new data to the stack (cap at 1hr history) and save
        #if len(regCacheStack)>1000:
        if len(regCacheStack)>0:
            #earliest_cache_age=(datetime.datetime.now(GivLUT.timezone)-datetime.datetime.strptime(finditem(regCacheStack[0],"Invertor_Time"), '%Y-%m-%dT%H:%M:%S%z'))
            #if earliest_cache_age.seconds>3600:
            if len(regCacheStack)>30:  # keep ~10 hours of history for outlier detection
                regCacheStack.pop(0)
        multi_output=noneKeys(multi_output)     # clean before caching, so every later dump of the cache works too
        regCacheStack.append(multi_output)
        GivLUT.put_regcache(regCacheStack)
            
        logger.debug("Successfully processed data from: " + GiV_Settings.invertorIP)

        result['result'] = "Success processing data"
        result['multi_output']=multi_output

        # Success, so delete oldDataCount
        if exists(GivLUT.oldDataCount):
            os.remove(GivLUT.oldDataCount)

    except KeyError as e:
        missing_key = e.args[0] if e.args else None
        logger.error("Key Error getting Battery Data: missing key "+repr(missing_key)+" - "+errDetail())
    except Exception as e:
        err=errDetail()
        consecFails(e)
        logger.error("inverter Update failed so using last known good data from cache: (%s: %s - %s)", e.__class__.__name__, str(e) , e.__traceback__.tb_lineno)
        result['result'] = "processData Error processing registers: " + str(e)
        return json.dumps(result)
    return json.dumps(noneKeys(result), indent=4, sort_keys=True, default=str)

def noneKeys(data, path=""):
    # json.dumps(sort_keys=True) fails on a None key (eg. a device whose serial isn't known yet), which would
    # lose the whole poll. Rename any such key and log where it was so the source can be fixed
    if isinstance(data, dict):
        fixed={}
        for k,v in data.items():
            if k is None:
                logger.warning("Output has a None key at '"+(path or "/")+"', publishing it as 'unknown'")
                k="unknown"
            fixed[k]=noneKeys(v, path+"/"+str(k))
        return fixed
    return data

def flat_iterate_dict(array):        # Create a publish safe version of the output (convert non string or int datapoints)
    safeoutput = {}
    #dump
    for p_load in array:
        output = array[p_load]
        if isinstance(output, dict):
            temp = flat_iterate_dict(output)
            safeoutput.update(temp)
            #safeoutput[p_load] = output
        else:
            safeoutput[p_load] = output
    return(safeoutput)

def makeFlatStack(CacheStack):
    data=[]
    dp=[]
    for cache in CacheStack:
        data.append(flat_iterate_dict(cache))
    flatstack={}
    for cache in data:
        for item in cache:
            if item in flatstack:
                dp=flatstack[item]
                dp.append(cache[item])
                flatstack[item]=dp
            else:
                flatstack[item]=[cache[item]]
    return flatstack

def fullCache():
    result=GivLUT.get_regcache()
    flatstack=makeFlatStack(result)
    ### Make JSON safe ###
    return json.dumps(flatstack, default=str)

def flattenRaw(cache,rawCacheStack):
    invertor={}
    dp=[]
    #check length and pop if needed
    for item in cache['invertor']:
        if item in rawCacheStack:
            dp=rawCacheStack[item]
            if len(dp)>500:
                dp.pop(0)
            dp.append(cache['invertor'][item])
            rawCacheStack[item]=dp
        else:
            rawCacheStack[item]=[cache['invertor'][item]]
    for battery in cache['batteries']:
        for item in cache['batteries'][battery]:
            id=battery+"_"+item
            if id in rawCacheStack:
                dp=rawCacheStack[id]
                if len(dp)>500:
                    dp.pop(0)
                dp.append(cache['batteries'][battery][item])
                rawCacheStack[id]=dp
            else:
                rawCacheStack[id]=[cache['batteries'][battery][item]]
    return rawCacheStack

def consecFails(e):
    with GivLUT.cachelock:
        if exists(GivLUT.oldDataCount):
            with open(GivLUT.oldDataCount, 'rb') as inp:
                oldDataCount= pickle.load(inp)
            oldDataCount = oldDataCount + 1
        else:
            oldDataCount = 1
        if oldDataCount>10:
            #10 error in a row so delete regCache data
            logger.error("10 failed inverter reads in a row so removing Cache (pkl) files to force update...")
            if exists(GivLUT.regcache):
                os.remove(GivLUT.regcache)
            if exists(GivLUT.rawpkl):
                os.remove(GivLUT.rawpkl)
            if exists(GivLUT.batterypkl):
                os.remove(GivLUT.batterypkl)
            if exists(GivLUT.oldDataCount):
                os.remove(GivLUT.oldDataCount)
            if exists(GivLUT.ratedata):
                os.remove(GivLUT.ratedata)
        else:
            with open(GivLUT.oldDataCount, 'wb') as outp:
                pickle.dump(oldDataCount, outp, pickle.HIGHEST_PROTOCOL)

def runAll2(plant: Plant):  # Read from Inverter put in cache and publish
    logger.debug("Running processData")
    try:
        result=json.loads(processData(plant))
        logger.debug("processData result: "+str(result['result']))
        if not 'multi_output' in result:
            # Processing failed (already logged by processData), so republish the last good data
            # rather than publishing nothing and letting entities go unavailable
            logger.error("Inverter data could not be processed, republishing last good data from cache")
            return pubFromPickle()
        # Only publish if its new data?
        logger.debug("Running pubFromPickle")
        multi_output = pubFromPickle(result['multi_output'])
    except KeyError as e:
        missing_key = e.args[0] if e.args else None
        logger.error("runAll2 Key Error: " + (f"Missing key {missing_key!r}") )
        return ("runAll2 Key Error: Missing key "+str(missing_key))
    except Exception:
        e=errDetail()
        logger.error("runAll2 Error processing registers: " + str(e))
        return ("runAll2 Error processing registers: " + str(e))
    return multi_output

def pubFromPickle(multi_output=None):  # Publish last cached Inverter Data
    if multi_output is None:
        multi_output = {}
    result = "Success"
    if not exists(GivLUT.regcache) and multi_output=={}:  # if there is no cache, create it
        result = "Please get data from Inverter first, either by calling runAll or waiting until the self-run has completed"
    try:
        if "Success" in result:
            if multi_output=={}:
                regCacheStack = GivLUT.get_regcache()
                if regCacheStack:
                    multi_output = regCacheStack[-1]
            SN = finditem(multi_output,'Invertor_Serial_Number')
            if not SN:
                # No good data has been processed yet, so there's nothing valid to publish
                logger.warning("No good inverter data in cache yet, skipping publish")
                multi_output['result'] = "No good inverter data in cache yet"
                return json.dumps(multi_output, indent=4, sort_keys=True, default=str)
            publishOutput(multi_output, SN)
        else:
            multi_output['result'] = result
        return json.dumps(multi_output, indent=4, sort_keys=True, default=str)
    except:
        e=errDetail()
        logger.error("Error publishing data from pickle: "+str(e))
        multi_output['result']="Error publishing data from pickle"
        return json.dumps(multi_output, indent=4, sort_keys=True, default=str)

def getCache():     # Get latest cache data and return it (for use in REST)
    multi_output={}
    inv=SinglePhaseInverter
    try:
        regCacheStack = GivLUT.get_regcache()
        if regCacheStack:
            multi_output = regCacheStack[-1]
            inv=multi_output.get('raw',{}).get('invertor',{})
            temp={}
            # raw['invertor'] is the library's device model (pydantic), which iterates as (field, value) pairs
            for key,reg in (inv.items() if isinstance(inv,dict) else inv):
                if isinstance(reg,TimeSlot):
                    temp[key]= str(reg)
                #elif not isinstance(inv[reg],(str,int,float)):
                elif isinstance(reg,list):
                    temp[key]=reg
                elif hasattr(reg,"name"):
                    temp[key]=reg.name.capitalize()
                else:
                    temp[key]= str(reg)
            if 'raw' in multi_output:
                # The EMS and Gateway models have no serial_number field, which consumers such as Predbat use
                # to find this device's block in the output, so take it from that block
                if not temp.get('serial_number'):
                    temp['serial_number']=next((v['Invertor_Serial_Number'] for v in multi_output.values()
                        if isinstance(v,dict) and 'Invertor_Serial_Number' in v), None)
                multi_output['raw']['invertor']=temp
            return json.dumps(multi_output, indent=4, sort_keys=True, default=str)
        else:
            multi_output['result']="No register data cache exists, try again later"
        return json.dumps(multi_output, indent=4, sort_keys=True, default=str)
#### Moight not be needed now I've traced it
    except AttributeError as err:
        #e=sys.exc_info()
        logger.error("Attribute Error getting data from cache: "+str(err))
        multi_output['result']="Attribute error getting data from cache: "+str(err)
        return json.dumps(multi_output, indent=4, sort_keys=True, default=str)
#### Perhaps remove cache file here if cache is corrupt?
    except:
        e=errDetail()
        logger.error("Error getting data from cache: "+str(e))
        multi_output['result']="Error getting data from cache"+str(e)
        return json.dumps(multi_output, indent=4, sort_keys=True, default=str)

async def self_run():
    # re-run everytime watch_plant Dies
    while True:
        try:
            logger.info("Starting watch_plant loop...")
            await watch_plant(handler=runAll2, refresh_period=GiV_Settings.self_run_timer,full_refresh_period=GiV_Settings.self_run_timer_full)
            # watch_plant only returns if initial connect/detect failed, so pause before retrying
            await asyncio.sleep(10)
        except:
            e=errDetail()
            logger.error("Error in self_run. Re-running watch_plant: "+str(e))
            await asyncio.sleep(2)

def start():
    asyncio.run(self_run())


def publishOutput(array, SN):

    # Additional Publish options can be added here.
    # A separate file in the folder can be added with a new publish "plugin"
    # then referenced here with any settings required added into settings.py

    if GiV_Settings.Battery_Only==True:
        # Only filters what's published (the inverter is still fully polled). Keep the controls, so per-inverter
        # automations (eg. pause discharge during an EV charge) still work behind an EMS (#591)
        array={key:array[key] for key in ('Battery_Details','Control','Timeslots') if key in array}
    tempoutput = {}
    tempoutput = iterate_dict(array)

    if GiV_Settings.MQTT_Output:
        if not exists(GivLUT.firstrun):
            logger.debug("Running updateFirstRun with SN= "+str(SN))
            updateFirstRun(SN)
            if GiV_Settings.HA_Auto_D:               
                logger.info("Publishing Home Assistant Discovery messages")
                from HA_Discovery import HAMQTT
                HAMQTT.publish_discovery2(tempoutput, SN, unsupportedEntities())
            open(GivLUT.firstrun, 'w').close()
            if exists(GivLUT.config_dir+'/.v3upgrade_'+str(GiV_Settings.givtcp_instance)):
                os.remove(GivLUT.config_dir+'/.v3upgrade_'+str(GiV_Settings.givtcp_instance))
        else:
            logger.debug("firstrun exists, so this should already have been run")
        logger.debug("Publish all to MQTT")
        if GiV_Settings.MQTT_Topic == "":
            GiV_Settings.MQTT_Topic = "GivEnergy"
        GivMQTT.multi_MQTT_publish(str(GiV_Settings.MQTT_Topic+"/"+SN+"/"), tempoutput)
    if GiV_Settings.Influx_Output:
        from influx import GivInflux
        logger.debug("Pushing output to Influx")
        GivInflux.publish(SN, tempoutput)

def updateFirstRun(SN):
    isSN = False
    script_dir = os.path.dirname(__file__)
    rel_path = "settings.py"
    abs_file_path = os.path.join(script_dir, rel_path)
    #check for settings lockfile before
    count=0
    while True:
        logger.debug("Opening settings for first run")
        if exists('.settings_lockfile'):
            logger.debug("Waiting for settings to be available")
            time.sleep(1)
            count=count+1
            if count==50:
                logger.error("Could not access settings file to update EVC Serial Number")
                break
        else:
            logger.debug("Settings available")
            #Create setting lockfile
            open(".settings_lockfile",'a').close()

            with open(abs_file_path, "r") as f:
                lines = f.readlines()
            with open(abs_file_path, "w") as f:
                for line in lines:
                    if line.strip("\n") == "    first_run= True":
                        f.write("    first_run= False\n")
                    else:
                        f.write(line)
                    if "serial_number=" in line:
                        logger.debug("serial number aready exists: \""+line+"\"")
                        isSN = True

                if not isSN:
                    logger.debug("serial number not in file, adding now")
                    f.writelines("    serial_number= \""+SN+"\"\n")  # only add SN if its not there
            # Delete settings_lockfile
            os.remove('.settings_lockfile')
            logger.debug("removing lockfile")
            break


def iterate_dict(array):        # Create a publish safe version of the output (convert non string or int datapoints)
    safeoutput = {}
    #dump
    for p_load in array:
        output = array[p_load]
        if isinstance(output, dict):
            temp = iterate_dict(output)
            safeoutput[p_load] = temp
            logger.debug('Dealt with '+p_load)
        elif isinstance(output, tuple):
            if "slot" in str(p_load):
                logger.debug('Converting Timeslots to publish safe string')
                safeoutput[p_load+"_start"] = output[0].strftime("%H:%M")
                safeoutput[p_load+"_end"] = output[1].strftime("%H:%M")
            else:
                # Deal with other tuples _ Print each value
                for index, key in enumerate(output):
                    logger.debug('Converting Tuple to multiple publish safe strings')
                    safeoutput[p_load+"_"+str(index)] = str(key)
        elif isinstance(output, datetime.datetime):
            logger.debug('Converting datetime to publish safe string')
            safeoutput[p_load] = output.strftime("%d-%m-%Y %H:%M:%S")
        elif isinstance(output, datetime.time):
            logger.debug('Converting time to publish safe string')
            safeoutput[p_load] = output.strftime("%H:%M")
        elif isinstance(output, Model):
            logger.debug('Converting Model to publish safe string')
            safeoutput[p_load] = output.name.capitalize()
        elif isinstance(output, float):
            safeoutput[p_load] = round(output, 3)
        else:
            safeoutput[p_load] = output
    return(safeoutput)


def ratecalcs(multi_output, multi_output_old):
    rate_data = {}
    logger.debug("Starting ratecalcs...")
    dayRateStart = datetime.datetime.strptime(GiV_Settings.day_rate_start, '%H:%M')
    nightRateStart = datetime.datetime.strptime(GiV_Settings.night_rate_start, '%H:%M')
    night_start = datetime.datetime.combine(datetime.datetime.now(GivLUT.timezone).date(),nightRateStart.time()).replace(tzinfo=GivLUT.timezone)
    logger.debug("Night Start= "+datetime.datetime.strftime(night_start, '%c'))
    day_start = datetime.datetime.combine(datetime.datetime.now(GivLUT.timezone).date(),dayRateStart.time()).replace(tzinfo=GivLUT.timezone)
    logger.debug("Day Start= "+datetime.datetime.strftime(day_start, '%c'))
    import_energy = multi_output['Energy']['Total']['Import_Energy_Total_kWh']
    import_energy_old = multi_output_old['Energy']['Total']['Import_Energy_Total_kWh']

    # check if pickle data exists:
    if exists(GivLUT.ratedata):
        with open(GivLUT.ratedata, 'rb') as inp:
            rate_data = pickle.load(inp)
    else:
        logger.debug("No rate_data exists, so creating new baseline")

    #       If no data then just save current import as base data
    if not('Night_Start_Energy_kWh' in rate_data):
        logger.debug("No Night Start Energy so setting it to: "+str(import_energy))
        rate_data['Night_Start_Energy_kWh'] = import_energy
    if not('Day_Start_Energy_kWh' in rate_data):
        logger.debug("No Day Start Energy so setting it to: "+str(import_energy))
        rate_data['Day_Start_Energy_kWh'] = import_energy
    if not('Night_Energy_kWh' in rate_data):
        rate_data['Night_Energy_kWh'] = 0.00
    if not('Day_Energy_kWh' in rate_data):
        rate_data['Day_Energy_kWh'] = 0.00
    if not('Night_Cost' in rate_data):
        rate_data['Night_Cost'] = 0.00
    if not('Day_Cost' in rate_data):
        rate_data['Day_Cost'] = 0.00
    if not('Night_Energy_Total_kWh' in rate_data):
        rate_data['Night_Energy_Total_kWh'] = 0
    if not('Day_Energy_Total_kWh' in rate_data):
        rate_data['Day_Energy_Total_kWh'] = 0
    if not('Import_ppkwh_Today' in rate_data):
        rate_data['Import_ppkwh_Today'] = 0

# Always update rates from new setting
    rate_data['Export_Rate'] = GiV_Settings.export_rate
    rate_data['Day_Rate'] = GiV_Settings.day_rate
    rate_data['Night_Rate'] = GiV_Settings.night_rate

    # New inverter day, so reset costs. No grace period needed: this is based on the import total, which doesn't reset
    if newInverterDay(finditem(multi_output,"Invertor_Time"), multi_output_old, grace=False):
        logger.debug("New inverter day, so resetting Day/Night stats...")
        rate_data['Night_Cost'] = 0.00
        rate_data['Day_Cost'] = 0.00
        rate_data['Night_Energy_kWh'] = 0.00
        rate_data['Day_Energy_kWh'] = 0.00
        rate_data['Day_Start_Energy_kWh'] = import_energy
        rate_data['Night_Start_Energy_kWh'] = import_energy
        rate_data['Day_Energy_Total_kWh'] = 0
        rate_data['Night_Energy_Total_kWh'] = 0

## If we use externally triggered rates then don't do the time check but assume the rate files are set elsewhere (default to Day if not set)
    if GiV_Settings.dynamic_tariff == False:
        # Work out the rate from the current time rather than only in the start minute, so a missed poll
        # (restart or loop timer >60s) can't leave the wrong rate set. Handles windows crossing midnight.
        nowTime=datetime.datetime.now(GivLUT.timezone).time()
        if nightRateStart.time() < dayRateStart.time():
            inNight = nightRateStart.time() <= nowTime < dayRateStart.time()
        else:
            inNight = nowTime >= nightRateStart.time() or nowTime < dayRateStart.time()
        if inNight and not exists(GivLUT.nightRate):
            open(GivLUT.nightRateRequest, 'w').close()
        elif not inNight and not exists(GivLUT.dayRate):
            open(GivLUT.dayRateRequest, 'w').close()

    if exists(GivLUT.nightRateRequest):
        os.remove(GivLUT.nightRateRequest)
        if not exists(GivLUT.nightRate):
            #Save last total from todays dayrate so far
            rate_data['Day_Energy_Total_kWh']=rate_data['Day_Energy_kWh']       # save current day energy at the end of the slot
            logger.info("Saving current energy stats at start of night rate tariff (Dynamic)")
            rate_data['Night_Start_Energy_kWh'] = import_energy-rate_data['Night_Energy_Total_kWh']     #offset current night energy from current energy to combine into a single slot
            open(GivLUT.nightRate, 'w').close()
            if exists(GivLUT.dayRate):
                logger.debug(".dayRate exists so deleting it")
                os.remove(GivLUT.dayRate)
    elif exists(GivLUT.dayRateRequest):
        os.remove(GivLUT.dayRateRequest)
        if not exists(GivLUT.dayRate):
            rate_data['Night_Energy_Total_kWh']=rate_data['Night_Energy_kWh']   # save current night energy at the end of the slot
            logger.info("Saving current energy stats at start of day rate tariff (Dynamic)")
            rate_data['Day_Start_Energy_kWh'] = import_energy-rate_data['Day_Energy_Total_kWh']     # offset current day energy from current energy to combine into a single slot
            open(GivLUT.dayRate, 'w').close()
            if exists(GivLUT.nightRate):
                logger.debug(".nightRate exists so deleting it")
                os.remove(GivLUT.nightRate)

    if not exists(GivLUT.nightRate) and not exists(GivLUT.dayRate): #Default to Day if not previously set
        logger.info("Dynamic Tariff enabled so defaulting to Day Rate and waiting external control")
        open(GivLUT.dayRate, 'w').close()

    if exists(GivLUT.dayRate):
        rate_data['Current_Rate_Type'] = "Day"
        rate_data['Current_Rate'] = GiV_Settings.day_rate
        logger.debug("Setting Rate to Day")
    else:
        rate_data['Current_Rate_Type'] = "Night"
        rate_data['Current_Rate'] = GiV_Settings.night_rate
        logger.debug("Setting Rate to Night")


    # now calc the difference for each value between the correct start pickle and now
    if import_energy>import_energy_old: # Only run if there has been more import
        logger.debug("Imported more energy so calculating current tariff costs: "+str(import_energy_old)+" -> "+str(import_energy))

        if exists(GivLUT.nightRate):
            logger.debug("Current Tariff is Night, calculating stats...")
            # Add change in energy this slot to previous rate_data
            rate_data['Night_Energy_kWh'] = import_energy-rate_data['Night_Start_Energy_kWh']
            logger.debug("Night_Energy_kWh=" +str(import_energy)+" - "+str(rate_data['Night_Start_Energy_kWh']))
            rate_data['Night_Cost'] = round(float(rate_data['Night_Energy_kWh'])*float(GiV_Settings.night_rate),2)
            logger.debug("Night_Cost= "+str(rate_data['Night_Energy_kWh'])+"kWh x £"+str(float(GiV_Settings.night_rate))+"/kWh = £"+str(rate_data['Night_Cost']))
            rate_data['Current_Rate'] = GiV_Settings.night_rate
        else:
            logger.debug("Current Tariff is Day, calculating stats...")
            rate_data['Day_Energy_kWh'] = import_energy-rate_data['Day_Start_Energy_kWh']
            logger.debug("Day_Energy_kWh=" + str(import_energy)+" - "+str(rate_data['Day_Start_Energy_kWh']))
            rate_data['Day_Cost'] = round(float(rate_data['Day_Energy_kWh'])*float(GiV_Settings.day_rate),2)
            logger.debug("Day_Cost= "+str(rate_data['Day_Energy_kWh'])+"kWh x £"+str(float(GiV_Settings.day_rate))+"/kWh = £"+str(rate_data['Day_Cost']))
            rate_data['Current_Rate'] = GiV_Settings.day_rate

        if multi_output['Energy']['Today']['Import_Energy_Today_kWh'] != 0:
            logger.debug("Import_ppkwh_Today= (£"+str(rate_data['Day_Cost'])+" + £"+str(rate_data['Night_Cost'])+") / "+str(multi_output['Energy']['Today']['Import_Energy_Today_kWh'])+"kWh = £"+str(rate_data['Import_ppkwh_Today'])+"/kWh")
            rate_data['Import_ppkwh_Today'] = round((rate_data['Day_Cost']+rate_data['Night_Cost'])/(multi_output['Energy']['Today']['Import_Energy_Today_kWh']), 3)

    multi_output['Energy']['Rates'] = rate_data

    # dump current data to Pickle
    with open(GivLUT.ratedata, 'wb') as outp:
        pickle.dump(rate_data, outp, pickle.HIGHEST_PROTOCOL)

    return (multi_output)


def dataCleansing(data, regCacheStack):
    logger.debug("Running the data cleansing process")
    # iterate multi_output to get each end result dict.
    # Loop that dict to validate against
    inv_time=datetime.datetime.strptime(finditem(data,"Invertor_Time"), '%Y-%m-%dT%H:%M:%S%z')
    new_multi_output = loop_dict(data, regCacheStack, data['Stats']["Last_Updated_Time"],str(finditem(regCacheStack,"Invertor_Type")).lower(),inv_time)
    return(new_multi_output)


def dicttoList(array):
    safeoutput = []
    # finaloutput={}
    # arrayout={}
    for p_load in array:
        output = array[p_load]
        safeoutput.append(p_load)
        if isinstance(output, dict):
            safeoutput = safeoutput+dicttoList(output)
    return(safeoutput)


def loop_dict(array, regCacheStack, lastUpdate, invtype,inv_time):
    safeoutput = {}
    # finaloutput={}
    # arrayout={}
    for p_load in array:
        output = array[p_load]
        if p_load == "raw":  # skip data cleansing for raw data
            safeoutput[p_load] = output
            continue
        if isinstance(output, dict):
            if p_load in regCacheStack:
                temp = loop_dict(output, regCacheStack[p_load], lastUpdate,invtype,inv_time)
                safeoutput[p_load] = temp
                logger.debug('Data cleansed for: '+str(p_load))
            else:
                logger.debug(str(p_load)+" has no data in the cache so using new value.")
                safeoutput[p_load] = output
        else:
            # run datasmoother on the data item
            # only run if old data exists otherwise return the existing value
            if p_load in regCacheStack:
                safeoutput[p_load] = dataSmoother2([p_load, output], [p_load, regCacheStack[p_load]], lastUpdate, invtype, inv_time)
            else:
                logger.debug(p_load+" has no data in the cache so using new value.")
                safeoutput[p_load] = output
    return(safeoutput)

def dataSmoother2(dataNew, dataOld, lastUpdate, invtype,inv_time):
    # perform test to validate data and smooth out spikes
    try:
        newData = dataNew[1]
        oldData = dataOld[1]
        name = dataNew[0]
        lookup = givLUT[name]
        if newData is not None and oldData is not None:
            if GiV_Settings.data_smoother.lower() == "high":
                smoothRate = 0.25
                abssmooth=1000
            elif GiV_Settings.data_smoother.lower() == "medium":
                smoothRate = 0.35
                abssmooth=5000
            else:
                smoothRate = 0.50
                abssmooth=7000
            if isinstance(newData, (int, float)):
                if not '3ph' in invtype:
                    if isinstance(lookup.min,str):
                        min=maxvalues.single_phase[lookup.min]
                    else:
                        min=lookup.min
                    if isinstance(lookup.max,str):
                        max=maxvalues.single_phase[lookup.max]
                    else:
                        max=lookup.max
                else:
                    if isinstance(lookup.min,str):
                        min=maxvalues.three_phase[lookup.min]
                    else:
                        min=lookup.min
                    if isinstance(lookup.max,str):
                        max=maxvalues.three_phase[lookup.max]
                    else:
                        max=lookup.max
                now = inv_time
                then = datetime.datetime.fromisoformat(lastUpdate)

        ## Check Midnight Today as special case before checking for Zero
                if now.hour == 0 and now.minute < 5 and "Today" in name:  # Treat Today stats as a special case - allow 5 min window for inverter clock drift
                    logger.debug("Midnight and "+str(name)+" so accepting value as is: "+str(newData))
                    return (newData)
        ## Now discard non-allowed Zero datapoints
                if newData == 0 and not lookup.allowZero:  # if zero and not allowed to be
                    logger.debug(str(name)+" is Zero so using old value")
                    return(oldData)
        ## Now check Min-Max
                if newData < float(min) or newData > float(max):  # If outside min and max ranges
                    logger.debug(str(name)+" is outside of allowable bounds so using old value. Out of bounds value is: "+str(newData) + ". Min limit: " + str(min) + ". Max limit: " + str(max))
                    return(oldData)
        ## Now check if its increasing
                if lookup.onlyIncrease:  # if data can only increase then check
                    if name in ("Battery_Charge_Energy_Total_kWh","Battery_Discharge_Energy_Total_kWh") and oldData > 6500 and newData < 100:
                        # These totals are 16-bit registers (max 6553.5kWh) and wrap back to zero (#448)
                        logger.info(str(name)+" has wrapped round from "+str(oldData)+" to "+str(newData))
                        return newData
                    if (oldData-newData) > 0.11:
                        logger.debug(str(name)+" has decreased so using old value")
                        return oldData
                    if oldData > 1 and newData > oldData:
                        dataDelta = (newData - oldData) / oldData
                        if dataDelta > smoothRate:
                            logger.debug(str(name)+" increased too rapidly: "+str(oldData)+"->"+str(newData)+" so using previous value")
                            return oldData

        ## Now smooth data
##### Remove this if using outlier????
                if lookup.smooth and not GiV_Settings.data_smoother.lower() == "none":     # apply smoothing if required
                    if newData != oldData:  # Only if its not the same
                        if any(word in name.lower() for word in ["power","_to_"]):
                            if abs(newData-oldData)>abssmooth:                                
                                if checkRawcache(newData,name,abssmooth): #If new data is persistently outside bounds then use new value
                                    return(newData)
                                else:
                                    logger.debug(str(name)+" jumped too far in a single read: "+str(oldData)+"->"+str(newData)+" so using previous value")
                                    return (oldData)
                        else:
                            ## Only smooth data if its not already Zero (avoid div by Zero)
                            if oldData != 0:
                                if abs(newData-oldData) < 1: # ignore very small changes (eg. today energy stats at start of day)
                                    return (newData)
                                timeDelta = (now-then).total_seconds()
                                dataDelta = abs(newData-oldData)/oldData    #Should it be a ratio or an abs value as low values easily meet the threshold
                                if dataDelta > smoothRate and timeDelta < 60:
                                    logger.debug(str(name)+" jumped too far in a single read: "+str(oldData)+"->"+str(newData)+" so using previous value")
                                    return (oldData)
        else:
            logger.debug("Nonetype in old or new data for "+str(name)+" so using new value")
    except Exception as e:
        logger.error("dataSmoother2 Error processing "+str(dataNew[0])+": "+errDetail())
        return(newData)    
    return(newData)

def checkRawcache(newData,name,abssmooth):
    #Get rawdata cache to check if unallowed changes are persistent and should be allowed
    bigjump=False
    rawCacheStack = GivLUT.load_pickle(GivLUT.rawpkl) if exists(GivLUT.rawpkl) else None
    if rawCacheStack:
        oldData=rawCacheStack[1]['invertor'][GivLUT.raw_to_pub[name]]
        if abs(newData-oldData)>abssmooth:
            bigjump=True
        logger.debug("NewData is: "+str(newData)+" and cached raw value was: "+str(oldData))
    return bigjump


def calcBatteryValue(multi_output):
    # get current data from read pickle
    batterystats = {}
    if exists(GivLUT.batterypkl):
        with open(GivLUT.batterypkl, 'rb') as inp:
            batterystats = pickle.load(inp)
    else:       # if no old AC charge, then set it to now and zero out value and ppkwh
        logger.debug("First time running so saving AC Charge status")
        batterystats['AC Charge last'] = float(multi_output['Energy']['Total']['AC_Charge_Energy_Total_kWh'])
        batterystats['Battery_Value'] = 0
        batterystats['Battery_ppkwh'] = 0
        batterystats['Battery_kWh_old'] = multi_output['Power']['Power']['SOC_kWh']

    if not exists(GivLUT.firstrun) or datetime.datetime.now(GivLUT.timezone).minute == 59 or datetime.datetime.now(GivLUT.timezone).minute == 29:
        if not exists(GivLUT.ppkwhtouch) and exists(GivLUT.batterypkl):      # only run this if there is no touchfile but there is a battery stat
            battery_kwh = multi_output['Power']['Power']['SOC_kWh']
            ac_charge = float(multi_output['Energy']['Total']['AC_Charge_Energy_Total_kWh'])-float(batterystats['AC Charge last'])
            logger.debug("Battery_kWh has gone from: "+str(batterystats['Battery_kWh_old'])+" -> "+str(battery_kwh))
            if float(battery_kwh) > float(batterystats['Battery_kWh_old']):
                logger.debug("Battery has been charged in the last 30mins so recalculating battery value and ppkwh: ")
                batVal = batterystats['Battery_Value']
                money_in = round(ac_charge*float(multi_output['Energy']['Rates']['Current_Rate']), 2)
                logger.debug("Money_in= "+str(round(ac_charge, 2))+"kWh * £"+str(float(multi_output['Energy']['Rates']['Current_Rate']))+"/kWh = £"+str(money_in))
                batterystats['Battery_Value'] = round(float(batterystats['Battery_Value']) + money_in, 3)
                logger.debug("Battery_Value= £"+str(float(batVal))+" + £"+str(money_in)+" = £"+str(batterystats['Battery_Value']))
                batterystats['Battery_ppkwh'] = round(batterystats['Battery_Value']/battery_kwh, 3)
                logger.debug("Battery_ppkWh= £"+str(batterystats['Battery_Value'])+" / "+str(battery_kwh)+"kWh = £"+str(batterystats['Battery_ppkwh'])+"/kWh")
            else:
                logger.debug("No battery charge in the last 30 mins so adjusting Battery Value")
                batterystats['Battery_Value'] = round(float(batterystats['Battery_ppkwh'])*battery_kwh, 3)
                logger.debug("Battery_Value= £"+str(round(float(batterystats['Battery_ppkwh']), 2))+"/kWh * "+str(round(battery_kwh, 2))+"kWh = £"+str(batterystats['Battery_Value']))
            # set the new "old" AC Charge stat to current AC Charge kwh
            batterystats['AC Charge last'] = float(multi_output['Energy']['Total']['AC_Charge_Energy_Total_kWh'])
            logger.debug("Updating battery_kWh_old to: "+str(battery_kwh))
            batterystats['Battery_kWh_old'] = battery_kwh
            open(GivLUT.ppkwhtouch, 'w').close()       # set touch file  to stop repeated triggers in the single minute

    else:       # remove the touchfile if it exists
        if exists(GivLUT.ppkwhtouch):
            os.remove(GivLUT.ppkwhtouch)

    # write data to pickle
    with open(GivLUT.batterypkl, 'wb') as outp:
        pickle.dump(batterystats, outp, pickle.HIGHEST_PROTOCOL)

    # remove non publishable stats
    del batterystats['AC Charge last']
    # add stats to multi_output
    multi_output['Energy']['Rates']['Battery_Value'] = batterystats['Battery_Value']
    multi_output['Energy']['Rates']['Battery_ppkwh'] = batterystats['Battery_ppkwh']
    return (multi_output)

def getJobFinish(type: str):
    with open(type, 'r') as f:
        lines=f.readlines()
    endtime=lines[1]
    logger.debug("Finish hour= "+str(endtime[:2]))
    logger.debug("Finish minute= "+str(endtime[-2:]))
    finishdate= datetime.datetime.now().replace(hour=int(endtime[:2]),minute=int(endtime[-2:]))
    logger.debug("Finishtime is: "+str(finishdate))
    timeleft=int((finishdate - datetime.datetime.now()).total_seconds()/60)+1
    logger.debug("Time remaining is" + str(timeleft))
    return (timeleft)

def finditem(obj, key):
    if key in obj: return obj[key]
    for k, v in obj.items():
        if isinstance(v,dict):
            item = finditem(v, key)
            if item is not None:
                return item
    return None

if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
