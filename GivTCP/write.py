# -*- coding: utf-8 -*-
# version 2022.01.31
from giverrors import errDetail
import sys
import json
import logging
import datetime
import re
from datetime import datetime, timedelta
from settings import GiV_Settings
import settings
import time
from os.path import exists
import pickle,os
import math
import GivLUT
from GivLUT import GivLUT, GivQueue
from givenergy_modbus.model import TimeSlot
from givenergy_modbus.model.ems import Ems
from givenergy_modbus.client import commands as gecommands     # v2 exposes some writes only as module functions
import requests
import importlib
import asyncio
from logging.handlers import TimedRotatingFileHandler

from GivLUT import GivClientAsync, SharedTimedRotatingFileHandler
import modbus_patches       # writes givenergy-modbus doesn't provide yet

logging.getLogger("givenergy_modbus").setLevel(logging.CRITICAL)

 
logging.basicConfig(format='%(asctime)s - Inv'+ str(GiV_Settings.givtcp_instance)+ \
                    ' - %(module)-11s -  [%(levelname)-8s] - %(message)s')
formatter = logging.Formatter(
    '%(asctime)s - %(module)s - [%(levelname)s] - %(message)s')
fhw = SharedTimedRotatingFileHandler(GiV_Settings.Debug_File_Location_Write, when='midnight', backupCount=7)
fhw.setFormatter(formatter)
logger = logging.getLogger('write_logger')
logger.addHandler(fhw)
if str(GiV_Settings.Log_Level).lower()=="debug":
    logger.setLevel(logging.DEBUG)
elif str(GiV_Settings.Log_Level).lower()=="write_debug":
    logger.setLevel(logging.DEBUG)
elif str(GiV_Settings.Log_Level).lower()=="info":
    logger.setLevel(logging.INFO)
elif str(GiV_Settings.Log_Level).lower()=="critical":
    logger.setLevel(logging.CRITICAL)
elif str(GiV_Settings.Log_Level).lower()=="warning":
    logger.setLevel(logging.WARNING)
else:
    logger.setLevel(logging.ERROR)


def finditem(obj, key):
    if key in obj: return obj[key]
    for k, v in obj.items():
        if isinstance(v,dict):
            item = finditem(v, key)
            if item is not None:
                return item
    return None

def frtouch():
    if not exists(".fullrefresh"):
        with open(".fullrefresh",'w') as fp:
            pass

def updateControlCache(entity,value,isTime: bool=False):
    from mqtt import GivMQTT
    # immediately update broker on success of control áction
    importlib.reload(settings)
    from settings import GiV_Settings
    if GiV_Settings.MQTT_Topic == "":
        GiV_Settings.MQTT_Topic = "GivEnergy"
    if isTime:
        Topic=str(GiV_Settings.MQTT_Topic+"/"+GiV_Settings.serial_number+"/Timeslots/")+str(entity)
        value=value.split(" ")[1]
    else:
        Topic=str(GiV_Settings.MQTT_Topic+"/"+GiV_Settings.serial_number+"/Control/")+str(entity)
    logger.debug("Pushing control update to mqtt: "+Topic+" - "+str(value))
    GivMQTT.single_MQTT_publish(Topic,str(value))

    # now update the pkl cache file
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        regCacheStack = GivLUT.get_regcache()
    if "regCacheStack" in locals():
        #find right object
        if isTime:
            regCacheStack[-1]['Timeslots'][entity]=value
        else:
            regCacheStack[-1]['Control'][entity]=value
        with open(GivLUT.regcache, 'wb') as outp:
            pickle.dump(regCacheStack, outp, pickle.HIGHEST_PROTOCOL)
        logger.debug("Pushing control update to pkl cache: "+entity+" - "+str(value))
    return

def log_num_writes(reqs):
    count=0
    safecount=0

    # if RTC is on do this else just len of all
    if not exists(GivLUT.rtc_enabled):
        
        if exists(GivLUT.writecountpkl):
            with open(GivLUT.writecountpkl, 'rb') as inp:
                count = pickle.load(inp)
        count=count+len(reqs)
        with open(GivLUT.writecountpkl, 'wb') as outp:
            pickle.dump(count, outp, pickle.HIGHEST_PROTOCOL)

    else:
        if exists(GivLUT.writecountpkl):
            with open(GivLUT.writecountpkl, 'rb') as inp:
                count = pickle.load(inp)
        if exists(GivLUT.safewritecountpkl):
            with open(GivLUT.safewritecountpkl, 'rb') as inp:
                safecount = pickle.load(inp)
        for req in reqs:
            if req.register in GivLUT.safe_regs:
                safecount=safecount+1
            else:
                count=count+1

        # write data to pickle
        with open(GivLUT.writecountpkl, 'wb') as outp:
            pickle.dump(count, outp, pickle.HIGHEST_PROTOCOL)
        with open(GivLUT.safewritecountpkl, 'wb') as outp:
            pickle.dump(safecount, outp, pickle.HIGHEST_PROTOCOL)

def lastWritePerRegister(reqs):
    # A second write to the same register in one batch cancels the client's wait for the first one, failing
    # the command. The last write is the value the command means to leave, so keep only that one
    last={}
    for i,r in enumerate(reqs):
        last[(getattr(r,'device_address',None),getattr(r,'register',None))]=i
    kept=[r for i,r in enumerate(reqs) if getattr(r,'register',None) is None or last[(getattr(r,'device_address',None),r.register)]==i]
    if len(kept)<len(reqs):
        logger.debug("Dropped "+str(len(reqs)-len(kept))+" earlier write(s) to registers written again in the same command")
    return kept

async def sendAsyncCommand(reqs,readloop):
    output={}
    reqs=lastWritePerRegister(reqs)
    asyncclient=await GivClientAsync.get_connection()
    if not asyncclient.connected:
        logger.info("Write client not connected after import")
        await asyncclient.connect()
    try:
        # The library default (1.5s, no retries) is too tight for a busy dongle. Register writes are
        # idempotent and the library won't resend a frame whose response has already arrived
        await asyncclient.one_shot_command(reqs, timeout=3.0, retries=2)
    except Exception as e:
        output['error']="Error in write command: "+str(e.__class__.__name__)+" "+str(e)
        logger.error(output['error']+" (registers: "+", ".join(str(getattr(r,'register','?')) for r in reqs)+")")
    if not readloop:
        #if write command came from somewhere other than the read loop then close the connection at the end
        logger.info("Closing non readloop modbus connection")
        await asyncclient.close()
    log_num_writes(reqs)
    frtouch()
    return output

def acLimit(kind,val):
    # The AC charge/discharge limit: HR313/314 on models with the AC config block (AC and All-in-One) and on
    # the Gateway, and HR1110/1108 on three-phase (the Gateway and three-phase via modbus_patches until
    # givenergy-modbus supports them). HV Gen3 has no rate write it permits yet, so fail clearly
    if GiV_Settings.inverter_type.lower() in ("ac","all_in_one","gateway"):
        return getattr(gecommands,"set_battery_"+kind+"_limit_ac")(val)
    if "3ph" in GiV_Settings.inverter_type.lower():
        return modbus_patches.three_phase_ac_limit(kind,val)
    raise NotImplementedError("Setting the AC "+kind+" rate is not yet supported by givenergy-modbus for "+str(GiV_Settings.inverter_type)+" inverters")

def optionalAcLimit(kind,val):
    # As acLimit, but for commands where the rate is one step of several (Force Charge/Export): skip it
    # with a warning so the rest of the command still runs
    try:
        return acLimit(kind,val)
    except NotImplementedError as e:
        logger.warning(str(e)+" - leaving the current "+kind+" rate unchanged")
        return []

def revert3phFlags(device,revert,keys):
    # Restore 3PH force/AC charge enables saved before a Force Charge/Export. The saved values are the
    # published "enable"/"disable" strings; givenergy-modbus treats any non-empty string as True, so convert
    # them. Only restore what was saved (Force Charge doesn't save the force discharge state)
    setters={"forceDischargeEnable":device.set_force_discharge,"forceChargeEnable":device.set_force_charge,"forceACChargeEnable":device.set_ac_charge}
    reqs=[]
    for key in keys:
        if key in revert:
            reqs.extend(setters[key](revert[key] in (True,1,"1","enable","Enable")))
    return reqs

def batteryCapacityWh(multi_output):
    # The rate controls are worked out from the battery capacity, which EMS and some models don't report
    capacity=finditem(multi_output,'Battery_Capacity_kWh')
    if not capacity:
        raise NotImplementedError("the battery capacity isn't known for this inverter, so the rate can't be set")
    return float(capacity)*1000

def batteryLimitPercent(rate,batcap,invmaxrate):
    # HR111/112 hold the rate as a whole percent of battery capacity (the GivEnergy app caps it at 50), so most
    # rates fall between two steps. Use the nearest, except at or above the inverter maximum: rounding down there
    # can never reach the maximum (eg. 3000W on 9.6kWh is 31.25%, and 31% is 2976W), so go up a step. The
    # inverter limits it to its maximum anyway. Not straight to 50, which is far above it on large banks (#562)
    percent=rate/batcap*100
    if rate>=invmaxrate:
        percent=math.ceil(invmaxrate/batcap*100)
    return min(round(percent),50)

def maxBatteryRate(multi_output):
    rate=finditem(multi_output,'Invertor_Max_Bat_Rate')
    if not rate:
        raise NotImplementedError("the maximum battery rate isn't known for this inverter, so the rate can't be set")
    return int(rate)

def controlError():
    """errDetail() for a failed control, but saying plainly when the control doesn't exist on this model:
    givenergy-modbus raises AttributeError for a writer the device model doesn't have"""
    exc=sys.exc_info()[1]
    if isinstance(exc,AttributeError):
        missing=re.match(r"'(Ems|SinglePhaseInverter|ThreePhaseInverter|GatewayV\d)' object has no attribute '(\w+)'",str(exc))
        if missing:
            return "not available for "+str(GiV_Settings.inverter_type)+" inverters (givenergy-modbus has no "+missing.group(2)+" for this model)"
    return errDetail()

def threePhaseOnly(name):
    # Force Charge/Discharge and AC Charge enables (HR1111-1113) only exist on three-phase inverters
    if "3ph" not in GiV_Settings.inverter_type.lower():
        raise NotImplementedError(name+" is only available on three-phase inverters")

def isEMS(device):
    # givenergy-modbus v2's Ems model has its own EMS-named slot/target writers (set_ems_*), not the inverter ones
    return isinstance(device, Ems)

def chargeTargetSOC(device,target):
    # Set only the charge target SOC, leaving the enable bits alone (v2: set_charge_target_soc)
    if "3ph" in GiV_Settings.inverter_type.lower():
        return gecommands.set_charge_target_soc_3ph(int(target))
    return device.set_charge_target_soc(int(target))

def slotTargetSOC(device,kind,slot,target):
    # Per-slot target SOC. givenergy-modbus provides these for EMS; for inverters with 10 time slots the
    # charge/discharge targets (HR 242+ / 272+) are written via modbus_patches until it does
    if 'ems' in GiV_Settings.inverter_type.lower():
        return getattr(gecommands,"set_ems_"+kind+"_target_soc")(int(slot),int(target))
    if kind=="export":
        raise NotImplementedError("Export target SOC is only available on the EMS")
    if len(device.slot_map.charge_slots)<10:
        raise NotImplementedError(kind.capitalize()+" target SOC per slot is only available on inverters with 10 time slots")
    return modbus_patches.slot_target_soc(kind,slot,target)

async def sbcla(device,target,readloop=False):
    temp={}
    try:
        reqs=acLimit("charge",target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Battery_Charge_Rate_AC",target)
        temp['result']="Setting battery charge rate AC to "+str(target)+"% was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery charge rate "+str(target)+" failed: "+errDetail()
        logger.error(temp['result'])
    return temp

async def sbdla(device,target,readloop=False):
    temp={}
    try:
        
        reqs=acLimit("discharge",target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Battery_Discharge_Rate_AC",target)
        temp['result']="Setting battery discharge rate AC to "+str(target)+"% was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery discharge rate "+str(target)+" failed: "+errDetail()
        logger.error(temp['result'])
    return temp

async def setForceCharge(device,payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling Force Charge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        threePhaseOnly("Force Charge")
        reqs=device.set_force_charge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Force Charge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setForceDischarge(device,payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling Force Discharge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        threePhaseOnly("Force Discharge")
        reqs=device.set_force_discharge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Force Discharge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setACCharge(device,payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling AC Charge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        threePhaseOnly("AC Charge")
        reqs=device.set_ac_charge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting AC Charge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def enableDischargeSchedule(device,payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Disharge Schedule")
            #temp= await ed(readloop)
            reqs=device.set_enable_discharge(True)
        elif payload['state']=="disable":
            logger.debug("Disabling Discharge Schedule")
            #temp= await dd(readloop)
            reqs=device.set_enable_discharge(False)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Enable_Discharge_Schedule",payload['state'])
        temp['result']="Setting Discharge Schedule to "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Discharge Schedule failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def enableChargeSchedule(device,payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Charge Schedule")
            #temp= await ec(readloop)
            reqs=device.set_enable_charge(True)
        elif payload['state']=="disable":
            logger.debug("Disabling Charge Schedule")
            #temp= await dc(readloop)
            reqs=device.set_enable_charge(False)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Enable_Charge_Schedule",payload['state'])
        temp['result']="Setting Charge Schedule to "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting charge schedule "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)



async def enableRTC(device,payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Real Time Control")
            #temp= await ect(readloop)
            reqs=device.set_enable_rtc(True)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Enabling Real Time Control was a success"
        elif payload['state']=="disable":
            logger.debug("Disabling Real Time Control")
            #temp= await dct(readloop)
            reqs=device.set_enable_rtc(False)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Disabling Real Time Control was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Real Time Control failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)


async def enableChargeTarget(device,payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Charge Target")
            #temp= await ect(readloop)
            reqs=device.set_charge_target_enabled(device.charge_target_soc or 100)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Enabling Charge Target was a success"
        elif payload['state']=="disable":
            logger.debug("Disabling Charge Target")
            #temp= await dct(readloop)
            reqs=device.disable_charge_target()
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Disabling Charge Target was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeTarget(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeToPercent'])
        logger.debug("Setting Charge Target to: "+str(target))
        #temp=await sct(target,readloop)
        reqs=device.set_charge_target_enabled(int(target))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Target_SOC",target)
        temp['result']="Setting Charge Target "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeTarget2(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Charge Target "+str(slot) + " to: "+str(target))
        reqs=slotTargetSOC(device,"charge",slot,target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_Target_SOC_"+str(slot),target)
        else:
            updateControlCache("Charge_Target_SOC_"+str(slot),target)
        #temp= await sst(target,slot,readloop)
        temp['result']="Setting Charge Target "+str(slot) + " was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Charge Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportTarget(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['exportToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Export Target "+str(slot) + " to: "+str(target))
        #temp= await sest(target,slot,readloop)
        reqs=slotTargetSOC(device,"export",slot,target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        temp['result']="Setting Export Target "+str(slot) + " was a success"
        updateControlCache("Export_Target_SOC_"+str(slot),target)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Export Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeTarget(device,payload,readloop=False):
    temp={}
######## EMS aware ######
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Discharge Target "+str(slot) + " to: "+str(target))
        #temp= await sdct(target,slot,readloop)
        reqs=slotTargetSOC(device,"discharge",slot,target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_Target_SOC_"+str(slot),target)
        else:
            updateControlCache("Discharge_Target_SOC_"+str(slot),target)
        temp['result']="Setting Discharge Target "+str(slot) + " was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Discharge Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setEmsPlant(device,payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling EMS Plant Operation")
            #temp= await ect(readloop)
            reqs=device.set_ems_plant(True)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Enabling EMS Plant Operation was a success"
        elif payload['state']=="disable":
            logger.debug("Disabling EMS Plant Operation")
            #temp= await dct(readloop)
            reqs=device.set_ems_plant(False)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Disabling EMS Plant Operation was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting EMS Plant Operation failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportLimit(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        # givenergy-modbus only provides an export power limit write for the EMS plant (HR 2071)
        if not isEMS(device):
            raise NotImplementedError("Setting the Export Limit is not yet supported by givenergy-modbus for "+str(GiV_Settings.inverter_type)+" inverters")
        limit=int(float(payload['state']))
        logger.debug("Setting Export Limit to: "+str(limit)+"w")
        reqs=device.set_ems_export_power_limit(limit)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Export_Power_Limit",limit)
        temp['result']="Setting Export Limit to "+str(limit)+"w was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Export Limit failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setCarChargeBoost(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        if not isEMS(device):
            raise NotImplementedError("Car Charge Boost is only available on the EMS")
        # EMS HR 2073, written via modbus_patches until givenergy-modbus supports it
        reqs=modbus_patches.car_charge_boost(payload['boost'])
        watts=reqs[0].value
        logger.debug("Setting Car Charge Boost to: "+str(watts)+"W")
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Car_Charge_Boost",watts)
        temp['result']="Setting Car Charge Boost to "+str(watts)+"W was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Car Charge Boost failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryReserve(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['reservePercent'])
        #Only allow minimum of 4%
        if target<4: target=4
        logger.debug ("Setting battery reserve target to: " + str(target))
        #temp= await ssc(target,readloop)
        reqs=device.set_battery_soc_reserve(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Battery_Power_Reserve",target)
        temp['result']="Setting battery reserve "+str(target)+" was a success"        
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Battery Reserve failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryCutoff(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeToPercent'])
        #Only allow minimum of 4%
        if target<4: target=4
        logger.debug ("Setting battery cutoff target to: " + str(target))
        #temp= await sbpr(target,readloop)
        reqs=device.set_battery_power_reserve(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Battery_Power_Cutoff",target)
        temp['result']="Setting battery power reserve to "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Battery Cutoff failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def rebootinverter(device,payload,readloop=False):
    temp={}
    try:
        logger.debug("Rebooting inverter...")
        #temp= await ri(readloop)
        reqs=device.set_inverter_reboot()
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        temp['result']="Rebooting Inverter was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Reboot inverter failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setActivePowerRate(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['activePowerRate'])
        logger.debug("Setting Active Power Rate to "+str(target))
        #temp= await sapr(target,readloop)
        reqs=device.set_active_power_rate(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Active_Power_Rate",target)
        temp['result']="Setting active power rate "+str(target)+" was a success"        
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Active Power Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeRate(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    
    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        try:
            regCacheStack=GivLUT.get_regcache()
            multi_output_old = regCacheStack[-1]
            invmaxrate=maxBatteryRate(multi_output_old)
            batcap=batteryCapacityWh(multi_output_old)
            if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
                target= min(100,round((int(payload['chargeRate'])/invmaxrate)*100,0))     # above the maximum means full rate
                if target<1:
                    # The AC limit register rejects 0% (library enforces 1-100), so the closest to a pause is 1%
                    logger.info("AC charge limit can't be 0%, setting 1% instead")
                    target=1
                logger.debug ("Setting battery charge rate ac to: " + str(payload['chargeRate'])+" ("+str(target)+")")
                reqs=acLimit("charge",target)
            else:
                # Percent of battery capacity, capped at 50 - the same value the GivEnergy app writes.
                # Don't jump straight to 50 at the inverter max: on large battery banks that's far above max (#562)
                target=batteryLimitPercent(int(payload['chargeRate']),batcap,invmaxrate)
                logger.debug ("Setting battery charge rate to: " + str(payload['chargeRate'])+" ("+str(target)+")")
                #temp= await sbcl(target,readloop)
                reqs=device.set_battery_charge_limit(target)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
                updateControlCache("Battery_Charge_Rate_AC",target)
                updateControlCache("Battery_Charge_Rate",int(payload['chargeRate']))
            else:
                val=int(min((target/100)*(batcap), invmaxrate))
                updateControlCache("Battery_Charge_Rate",val)
            temp['result']="Setting battery charge rate "+str(payload['chargeRate'])+" was a success"
            logger.info(temp['result'])
        except:
            e=controlError()
            temp['result']="Setting Charge Rate failed: " + str(e)
            logger.error (temp['result'])
    else:
        temp['result']="Setting Charge Rate failed: No charge rate limit available"
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeRateAC(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeRate'])
        logger.debug ("Setting AC battery charge rate to: " + str(target))
        temp= await sbcla(device,target,readloop)
        if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
            # Recreate Battery Watt rate and push to MQTT
            regCacheStack=GivLUT.get_regcache()
            multi_output_old = regCacheStack[-1]
            invmaxrate=finditem(multi_output_old,'Invertor_Max_Bat_Rate')
            val=int((target/100)*invmaxrate)
            updateControlCache("Battery_Charge_Rate",val)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting AC Battery Charge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeRate(device,payload,readloop=False):

## Make this work for 3PH using ratio for limit_ac
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        try:
            regCacheStack=GivLUT.get_regcache()
            multi_output_old = regCacheStack[-1]
            invmaxrate=maxBatteryRate(multi_output_old)
            batcap=batteryCapacityWh(multi_output_old)
            if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
                target= min(100,round((int(payload['dischargeRate'])/invmaxrate)*100,0))     # above the maximum means full rate
                if target<1:
                    # The AC limit register rejects 0% (library enforces 1-100), so the closest to a pause is 1%
                    logger.info("AC discharge limit can't be 0%, setting 1% instead")
                    target=1
                reqs=acLimit("discharge",target)
            else:
                # Percent of battery capacity, capped at 50 - the same value the GivEnergy app writes.
                # Don't jump straight to 50 at the inverter max: on large battery banks that's far above max (#562)
                target=batteryLimitPercent(int(payload['dischargeRate']),batcap,invmaxrate)
                #temp= await sbdl(target,readloop)
                reqs=device.set_battery_discharge_limit(target)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            val=int(min((target/100)*(batcap), invmaxrate))
            updateControlCache("Battery_Discharge_Rate",val)
            if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
                updateControlCache("Battery_Discharge_Rate_AC",target)
                updateControlCache("Battery_Discharge_Rate",int(payload['dischargeRate']))
            else:
                val=int(min((target/100)*(batcap), invmaxrate))
                updateControlCache("Battery_Discharge_Rate",val)
            temp['result']="Setting battery discharge limit "+str(payload['dischargeRate'])+" was a success"
            logger.debug ("Setting battery discharge rate to: " + str(payload['dischargeRate'])+" ("+str(target)+")")
            
            logger.info(temp['result'])
        except:
            e=controlError()
            temp['result']="Setting Discharge Rate failed: " + str(e)
            logger.error (temp['result'])
    else:
        temp['result']="Setting Discharge Rate failed: No discharge rate limit available"
        logger.error (temp['result'])        
    return json.dumps(temp)

async def setDischargeRateAC(device,payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeRate'])
        logger.debug ("Setting AC battery discharge rate to: " + str(target))
        temp= await sbdla(device,target,readloop)
        if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
            # Recreate Battery Watt rate and push to MQTT
            regCacheStack=GivLUT.get_regcache()
            multi_output_old = regCacheStack[-1]
            invmaxrate=finditem(multi_output_old,'Invertor_Max_Bat_Rate')
            val=int((target/100)*invmaxrate)
            updateControlCache("Battery_Discharge_Rate",val)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting AC battery discharge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlot(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
######## EMS aware ######
    try:
        logger.debug("Setting Charge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        #temp= await scs(payload,readloop)
        slot=TimeSlot(datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M"))
##############
        if isEMS(device):
            reqs=device.set_ems_charge_slot(int(payload['slot']),slot)
            if 'chargeToPercent' in payload.keys():
                reqs.extend(device.set_ems_charge_target_soc(int(payload['slot']),int(payload['chargeToPercent'])))
        else:
            reqs=device.set_charge_slot(int(payload['slot']),slot)
            if 'chargeToPercent' in payload.keys():
                reqs.extend(chargeTargetSOC(device,int(payload['chargeToPercent'])))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("EMS_Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseSlot(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Battery Pause slot to: "+str(payload['start'])+" - "+str(payload['finish']))
        #temp= await sps(payload,readloop)
        slot=TimeSlot(datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M"))
        reqs=gecommands.set_pause_slot(slot)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Battery_pause_start_time_slot",str(datetime.strptime(payload['start'],"%H:%M")),True)
        updateControlCache("Battery_pause_end_time_slot",str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Pause Slot to: "+str(payload['start'])+" - "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Battery Pause Slot failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlotStart(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
######## EMS aware ######
    try:
        logger.debug("Setting Charge Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        #temp= await scss(payload,readloop)
        if isEMS(device):
            reqs=device.set_ems_charge_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        else:
            reqs=device.set_charge_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        else:
            updateControlCache("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" Start to: "+str(payload['start'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlotEnd(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
######## EMS aware ######
    try:
        logger.debug("Setting Charge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        #temp= await scse(payload,readloop)
        if isEMS(device):
            reqs=device.set_ems_charge_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        else:
            reqs=device.set_charge_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Charge Slot End "+str(payload['slot'])+" to: "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlotStart(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        #temp= await sess(payload,readloop)
        reqs=device.set_export_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Export_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Export Slot "+str(payload['slot'])+" Start to: "+str(payload['start'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlotEnd(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        #temp= await sese(payload,readloop)
        reqs=device.set_export_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Export_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Export Slot End "+str(payload['slot'])+" to: "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlot(device,payload,readloop=False):
    temp={}
######## EMS aware ######
    if type(payload) is not dict: payload=json.loads(payload)
    # Should this include DischargePercent, or drop?
    # EMS has a per-slot discharge target instead of the inverter's battery reserve, so it's sent with the slot below
    if 'dischargeToPercent' in payload.keys() and not isEMS(device):
        pload={}
        pload['reservePercent']=payload['dischargeToPercent']
        result=await setBatteryReserve(device,pload,readloop)
    try:

        logger.debug("Setting Discharge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        #temp= await sds(payload,readloop)
        slot=TimeSlot(datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M"))
        if isEMS(device):
            reqs=device.set_ems_discharge_slot(int(payload['slot']),slot)
            if 'dischargeToPercent' in payload.keys():
                reqs.extend(device.set_ems_discharge_target_soc(int(payload['slot']),int(payload['dischargeToPercent'])))
        else:
            reqs=device.set_discharge_slot(int(payload['slot']),slot)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("EMS_Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlot(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        #temp= await ses(payload,readloop)
        slot=TimeSlot(datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M"))
        reqs=device.set_export_slot(int(payload['slot']),slot)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Export_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        updateControlCache("Export_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Export Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlotStart(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
######## EMS aware ######
    try:
        logger.debug("Setting Discharge Slot start "+str(payload['slot'])+" Start to: "+str(payload['start']))
        #temp= await sdss(payload,readloop)
        if isEMS(device):
            reqs=device.set_ems_discharge_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        else:
            reqs=device.set_discharge_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot start "+str(payload['slot'])+" Start to: "+str(payload['start'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Discharge Slot start "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlotEnd(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
######## EMS aware ######
    try:
        logger.debug("Setting Discharge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        #temp= await sdse(payload,readloop)
        if isEMS(device):
            reqs=device.set_ems_discharge_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        else:
            reqs=device.set_discharge_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" to: "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseStart(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Pause Slot Start to: "+str(payload['start']))
        #temp= await spss(payload,readloop)
        reqs=gecommands.set_pause_slot_start(datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result)
        updateControlCache("Battery_pause_start_time_slot",str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Pause Slot Start to: "+str(payload['start'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Pause Slot Start failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseEnd(device,payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Pause Slot End to: "+str(payload['finish']))
        #temp= await spse(payload,readloop)
        reqs=gecommands.set_pause_slot_end(datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result)
        updateControlCache("Battery_pause_end_time_slot",str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Pause Slot End to: "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Pause Slot End failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def FEResume(device,revert, readloop=False):
    temp={}
    try:
        logger.info("Reverting Force Export settings:")
        if "mode" in revert:
            result=await setBatteryMode(device,{"mode":revert["mode"]},readloop)
            if "failed" in json.loads(result)['result'] or "Invalid" in json.loads(result)['result']:
                raise Exception(json.loads(result)['result'])
        reqs=[]
        if "reservePercent" in revert:
            reqs.extend(device.set_battery_soc_reserve(revert["reservePercent"]))
        if "start_time" in revert and "end_time" in revert:
            # Force Export used discharge slot 1, so put that back
            slot=TimeSlot(datetime.strptime(revert['start_time'],"%H:%M"),datetime.strptime(revert['end_time'],"%H:%M"))
            reqs.extend(device.set_discharge_slot(1,slot))
        if "discharge_schedule" in revert:
            reqs.extend(device.set_enable_discharge(revert["discharge_schedule"]=="enable"))
        if "dischargeRate" in revert:
            target=50
            if exists(GivLUT.regcache):      # if there is a cache then grab it
                regCacheStack=GivLUT.get_regcache()
                multi_output_old = regCacheStack[-1]
                invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
                batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
                target=round(min((int(revert['dischargeRate'])/(batcap/2))*50,50))
            reqs.extend(device.set_battery_discharge_limit(target))
        elif "dischargeRateAC" in revert:
            reqs.extend(optionalAcLimit("discharge",revert["dischargeRateAC"]))
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(revert3phFlags(device,revert,["forceDischargeEnable","forceChargeEnable"]))  # turn back Force Export/Charge in 3PH
        if "batteryPauseMode" in revert:
            reqs.extend(gecommands.set_battery_pause_mode(GivLUT.battery_pause_mode.index(revert["batteryPauseMode"])))
        
        result = await sendAsyncCommand(reqs,readloop)
        if result:
            logger.error("Errors in control device: "+str(result))
            raise Exception(result)
        frtouch()
        os.remove(".FERunning"+str(GiV_Settings.givtcp_instance))
        updateControlCache("Force_Export","Normal")
        temp['result']="Force Export Reverted successfully"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Force Export Revert failed: " + str(e)
        if exists(".FERunning"+str(GiV_Settings.givtcp_instance)): os.remove(".FERunning"+str(GiV_Settings.givtcp_instance))
        logger.error (temp['result'])
    return json.dumps(temp)

async def forceExport(device, exportTime,readloop=False):
    temp={}
    logger.info("Forcing Export for "+str(exportTime)+" minutes")
    try:
        if isEMS(device):
            raise NotImplementedError("Force Export is not available for EMS")
        result={}
        revert={}
        hasBPM=False
        regCacheStack=GivLUT.get_regcache()
        if not regCacheStack:
            raise Exception("no inverter data yet, so the current settings can't be saved to revert to")
        if regCacheStack:
            revert["start_time"]=regCacheStack[-1]["Timeslots"]["Discharge_start_time_slot_1"][:5]
            revert["end_time"]=regCacheStack[-1]["Timeslots"]["Discharge_end_time_slot_1"][:5]
            # 3PH doesn't publish the reserve (HR1109), so take it from the device model
            revert["reservePercent"]=regCacheStack[-1]["Control"].get("Battery_Power_Reserve",device.battery_soc_reserve)
            revert["mode"]=regCacheStack[-1]["Control"]["Mode"]
            revert['discharge_schedule']=regCacheStack[-1]["Control"]["Enable_Discharge_Schedule"]
            if "Battery_Discharge_Rate" in regCacheStack[-1]["Control"]:
                revert["dischargeRate"]=regCacheStack[-1]["Control"]["Battery_Discharge_Rate"]
            elif "Battery_Discharge_Rate_AC" in regCacheStack[-1]["Control"]:
                revert["dischargeRateAC"]=regCacheStack[-1]["Control"]["Battery_Discharge_Rate_AC"]
            if "Battery_pause_mode" in regCacheStack[-1]["Control"]:
                revert["batteryPauseMode"]=regCacheStack[-1]["Control"]["Battery_pause_mode"]
                hasBPM=True
            if "Force_Discharge_Enable" in regCacheStack[-1]["Control"]:
                revert["forceDischargeEnable"]=regCacheStack[-1]["Control"]["Force_Discharge_Enable"]
            if "Force_Charge_Enable" in regCacheStack[-1]["Control"]:
                revert["forceChargeEnable"]=regCacheStack[-1]["Control"]["Force_Charge_Enable"]

        revert={k:v for k,v in revert.items() if v is not None}     # only revert what was read
        reqs=device.set_battery_soc_reserve(4)      # the device model picks the single/three-phase register itself
        finish=GivLUT.getTime(datetime.now()+timedelta(minutes=exportTime))
        slot=TimeSlot(datetime.strptime(GivLUT.getTime(datetime.now()),"%H:%M"),datetime.strptime(finish,"%H:%M"))

        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(device.set_force_discharge(True))  # turn on Force Export in 3PH
            reqs.extend(device.set_force_charge(False))  # turn off Force Charge in 3PH
            reqs.extend(optionalAcLimit("discharge",100))
        else:
            reqs.extend(device.set_battery_discharge_limit(50))
        reqs.extend(device.set_mode_storage(discharge_slot_1=slot,discharge_for_export=True))
        if hasBPM:
            reqs.extend(gecommands.set_battery_pause_mode(0))
        result = await sendAsyncCommand(reqs,readloop)
        frtouch()   #Force full refresh on next run to update control status
        if result:
            logger.error("Errors in control device: "+str(result))
            raise Exception(result)
        if exists(".FERunning"+str(GiV_Settings.givtcp_instance)):    # If a forcecharge is already running, change time of revert job to new end time.
            logger.info("Force Export already running, changing end time")
            revert=getFEArgs()[0]   # set new revert object and cancel old revert job
            logger.debug("new revert= "+ str(revert))
        fejob=GivQueue.q.enqueue_in(timedelta(minutes=exportTime),queueWrite,"FEResume",revert)
        with open(".FERunning"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(fejob.id),str(finish)]))
        logger.debug("Force Export revert jobid is: "+fejob.id)
        temp['result']="Export successfully forced for "+str(exportTime)+" minutes"
        updateControlCache("Force_Export","Running")
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Force Export failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def FCResume(device,revert,readloop=False):
    payload={}
    temp={}

    try:
        logger.info("Reverting Force Charge Settings:")
        reqs=[]
        if "chargeRate" in revert:
            is3ph="3ph" in GiV_Settings.inverter_type.lower()
            target=100 if is3ph else 50     # full rate if there's no cache to work from
            if exists(GivLUT.regcache):      # if there is a cache then grab it
                regCacheStack=GivLUT.get_regcache()
                multi_output_old = regCacheStack[-1]
                invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
                batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
                if is3ph:
                    target=max(1,min(100,round(int(revert['chargeRate'])/invmaxrate*100)))
                else:
                    target=round(min((int(revert['chargeRate'])/(batcap/2))*50,50))
            if is3ph:
                reqs.extend(optionalAcLimit("charge",target))
            else:
                reqs.extend(device.set_battery_charge_limit(target))
        elif "chargeRateAC" in revert:
            reqs.extend(optionalAcLimit("charge",revert["chargeRateAC"]))
        if "chargeScheduleEnable" in revert:
            reqs.extend(device.set_enable_charge(revert["chargeScheduleEnable"]=="enable"))
        if "start_time" in revert and "end_time" in revert:
            slot=TimeSlot(datetime.strptime(revert['start_time'],"%H:%M"),datetime.strptime(revert['end_time'],"%H:%M"))
            reqs.extend(device.set_charge_slot(1,slot))
        if "targetSOC" in revert:
            reqs.extend(chargeTargetSOC(device,int(revert["targetSOC"])))
        if "slot1TargetSOC" in revert:
            reqs.extend(slotTargetSOC(device,"charge",1,int(revert["slot1TargetSOC"])))
        if "batteryPauseMode" in revert:
            reqs.extend(gecommands.set_battery_pause_mode(GivLUT.battery_pause_mode.index(revert["batteryPauseMode"])))
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(revert3phFlags(device,revert,["forceDischargeEnable","forceChargeEnable","forceACChargeEnable"]))  # turn back Force Export/Charge/AC Charge in 3PH

        result = await sendAsyncCommand(reqs,readloop)
        if result:
            logger.error("Errors in control device: "+str(result))
            raise Exception(result)
        frtouch()        
        os.remove(".FCRunning"+str(GiV_Settings.givtcp_instance))
        updateControlCache("Force_Charge","Normal")
        temp['result']="Force Charge Reverted successfully"
        logger.info(temp['result'])
    except:
        e=controlError()
        logger.error("Force Charge revert failed: "+str(e))
        temp['result']="Force Charge revert failed: "+str(e)
        if exists(".FCRunning"+str(GiV_Settings.givtcp_instance)): os.remove(".FCRunning"+str(GiV_Settings.givtcp_instance))
        logger.error(temp['result'])
    return json.dumps(temp)

def queueWrite(command, payload):
    """Run by the RQ worker when a timed revert is due. The worker has no inverter connection, so hand the
    revert to the read loop via the write request queue, where it runs as command(device, payload, True)."""
    requests=[]
    if exists(GivLUT.writerequests):
        with open(GivLUT.writerequests,'rb') as inp:
            requests=pickle.load(inp)
    requests.append([command,payload,False])
    GivLUT.save_writerequests(requests)
    logger.info("Queued "+str(command)+" for the read loop")

def cancelJob(device, jobid, readloop=False):
    temp={}
    if jobid in GivQueue.q.scheduled_job_registry:
        GivQueue.q.scheduled_job_registry.requeue(jobid, at_front=True)
        temp['result']="Cancelling scheduled task as requested"
        logger.info(temp['result'])
    else:
        temp['result']="Job ID: " + str(jobid) + " not found in redis queue"
        logger.error(temp['result'])
    return json.dumps(temp)

def getFCArgs():
    from rq.job import Job
    # getjobid
    f=open(".FCRunning"+str(GiV_Settings.givtcp_instance), 'r')
    jobid=f.readline().strip('\n')
    f.close()
    # get the revert details from the old job
    job=Job.fetch(jobid,GivQueue.redis_connection)
    details=job.args[1:] if job.args and isinstance(job.args[0],str) else job.args    # args are (command, revert)
    logger.debug("Previous args= "+str(details))
    GivQueue.q.scheduled_job_registry.remove(jobid) # Remove the job from the schedule
    return (details)

def getFEArgs():
    from rq.job import Job
    # getjobid
    f=open(".FERunning"+str(GiV_Settings.givtcp_instance), 'r')
    jobid=f.readline().strip('\n')
    f.close()
    # get the revert details from the old job
    job=Job.fetch(jobid,GivQueue.redis_connection)
    details=job.args[1:] if job.args and isinstance(job.args[0],str) else job.args    # args are (command, revert)
    logger.debug("Previous args= "+str(details))
    GivQueue.q.scheduled_job_registry.remove(jobid) # Remove the job from the schedule
    return (details)

async def forceCharge(device, chargeTime, readloop=False):
    temp={}
    logger.info("Forcing Charge for "+str(chargeTime)+" minutes")

    try:
        if isEMS(device):
            raise NotImplementedError("Force Charge is not available for EMS")
        revert={}
        regCacheStack = GivLUT.get_regcache()
        hasBPM=False
        if not regCacheStack:
            raise Exception("no inverter data yet, so the current settings can't be saved to revert to")
        if regCacheStack:
            revert["start_time"]=regCacheStack[-1]["Timeslots"]["Charge_start_time_slot_1"][:5]
            revert["end_time"]=regCacheStack[-1]["Timeslots"]["Charge_end_time_slot_1"][:5]
            if "Battery_Charge_Rate" in regCacheStack[-1]["Control"]:
                revert["chargeRate"]=regCacheStack[-1]["Control"]["Battery_Charge_Rate"]
            elif "Battery_Charge_Rate_AC" in regCacheStack[-1]["Control"]:
                revert["chargeRateAC"]=regCacheStack[-1]["Control"]["Battery_Charge_Rate_AC"]
            revert["targetSOC"]=regCacheStack[-1]["Control"]["Target_SOC"]
            # On inverters with 10 slots, slot 1 also has its own target (HR242), and the inverter stops charging
            # at the lower of the two: left as it is, Force Charge does nothing once the SOC is above it (#576)
            revert["slot1TargetSOC"]=regCacheStack[-1]["Control"].get("Charge_Target_SOC_1")
            revert["chargeScheduleEnable"]=regCacheStack[-1]["Control"]["Enable_Charge_Schedule"]
            if "Battery_pause_mode" in regCacheStack[-1]["Control"]:
                revert["batteryPauseMode"]=regCacheStack[-1]["Control"]["Battery_pause_mode"]
                hasBPM=True
            if "Force_Charge_Enable" in regCacheStack[-1]["Control"]:
                revert['forceChargeEnable']= regCacheStack[-1]["Control"]["Force_Charge_Enable"]
            if "Force_AC_Charge_Enable" in regCacheStack[-1]["Control"]:
                revert['forceACChargeEnable']= regCacheStack[-1]["Control"]["Force_AC_Charge_Enable"]

        revert={k:v for k,v in revert.items() if v is not None}     # only revert what was read
        finish=GivLUT.getTime(datetime.now()+timedelta(minutes=chargeTime))
        reqs=chargeTargetSOC(device,100)
        if "slot1TargetSOC" in revert:
            try:
                reqs.extend(slotTargetSOC(device,"charge",1,100))
            except NotImplementedError:
                del revert["slot1TargetSOC"]    # read but can't be written here yet (eg. Gateway), so leave it
        slot=TimeSlot(datetime.strptime(GivLUT.getTime(datetime.now()),"%H:%M"),datetime.strptime(finish,"%H:%M"))
        reqs.extend(device.set_charge_slot(1,slot))
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(optionalAcLimit("charge",100))
            reqs.extend(device.set_force_charge(True))
            reqs.extend(device.set_ac_charge(True))
        else:
            reqs.extend(device.set_enable_charge(True))
            reqs.extend(device.set_battery_charge_limit(50))

        # Set Battery Pause Mode only if it exists
        if hasBPM:
            reqs.extend(gecommands.set_battery_pause_mode(0))
        result= await sendAsyncCommand(reqs,readloop)
        frtouch()   #Force full refresh on next run to update control status
        if result:
            logger.error("Errors in control device: "+str(result))
            raise Exception(result)
        if exists(".FCRunning"+str(GiV_Settings.givtcp_instance)):    # If a forcecharge is already running, change time of revert job to new end time
            logger.info("Force Charge already running, changing end time")
            revert=getFCArgs()[0]   # set new revert object and cancel old revert job
            logger.info("new revert= "+ str(revert))
        fcjob=GivQueue.q.enqueue_in(timedelta(minutes=chargeTime),queueWrite,"FCResume",revert)
        with open(".FCRunning"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(fcjob.id),str(finish)]))
        logger.debug("Force Charge revert jobid is: "+fcjob.id)
        temp['result']="Charge successfully forced for "+str(chargeTime)+" minutes"
        updateControlCache("Force_Charge","Running")

        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Force charge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tmpPDResume(device, payload, readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Reverting Temp Pause Discharge")
        result=await setDischargeRate(device,payload,readloop)
        if exists(".tpdRunning_"+str(GiV_Settings.givtcp_instance)): os.remove(".tpdRunning_"+str(GiV_Settings.givtcp_instance))
        temp['result']="Temp Pause Discharge Reverted"
        updateControlCache("Temp_Pause_Discharge","Normal")
        updateControlCache("Battery_Discharge_Rate",payload["dischargeRate"])
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Temp Pause Discharge Resume failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tempPauseDischarge(device, pauseTime, readloop=False):
    """Pauses discharge from battery for the defined duration in minutes

    Payload: 2
    """
    temp={}
    try:
        logger.debug("Pausing Discharge for "+str(pauseTime)+" minutes")
        #Update read data via pickle
        regCacheStack = GivLUT.get_regcache()
        if regCacheStack:
            revertRate=regCacheStack[-1]["Control"].get("Battery_Discharge_Rate",2600)
        else:
            revertRate=2600

        payload={}
        payload['dischargeRate']=0
        result=await setDischargeRate(device,payload,readloop)
        if "failed" in json.loads(result)['result']:
            raise Exception(json.loads(result)['result'])
        payload['dischargeRate']=revertRate
        delay=float(pauseTime*60)
        tpdjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),queueWrite,"tmpPDResume",payload)
        finishtime=GivLUT.getTime(datetime.now()+timedelta(minutes=pauseTime))
        with open(".tpdRunning_"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(tpdjob.id),str(finishtime)]))
        
        logger.debug("Temp Pause Discharge revert jobid is: "+tpdjob.id)
        temp['result']="Discharge paused for "+str(delay)+" seconds"
        updateControlCache("Temp_Pause_Discharge","Running")
        updateControlCache("Battery_Discharge_Rate",payload["dischargeRate"])
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Pausing Discharge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tmpPCResume(device, payload, readloop=False):
    """Reverts inverter settings after TempPauseCharge.

    Payload: {}
    """
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Reverting Temp Pause Charge...")
        result=await setChargeRate(device,payload,readloop)
        if exists(".tpcRunning_"+str(GiV_Settings.givtcp_instance)): os.remove(".tpcRunning_"+str(GiV_Settings.givtcp_instance))
        temp['result']="Temp Pause Charge Reverted"
        updateControlCache("Temp_Pause_Charge","Normal")
        updateControlCache("Battery_Charge_Rate",payload["chargeRate"])
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Temp Pause Charge Resume failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tempPauseCharge(device, pauseTime, readloop=False):
    """Pauses charge to battery for the defined duration in minutes

    Payload: 2
    """
    temp={}
    try:
        logger.debug("Pausing Charge for "+str(pauseTime)+" minutes")
        regCacheStack = GivLUT.get_regcache()
        if regCacheStack:
            revertRate=regCacheStack[-1]["Control"].get("Battery_Charge_Rate",2600)
        else:
            revertRate=2600
        payload={}
        payload['chargeRate']=0
        result=await setChargeRate(device,payload,readloop)
        if "failed" in json.loads(result)['result']:
            raise Exception(json.loads(result)['result'])
        payload['chargeRate']=revertRate
        delay=float(pauseTime*60)
        finishtime=GivLUT.getTime(datetime.now()+timedelta(minutes=pauseTime))
        tpcjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),queueWrite,"tmpPCResume",payload)
        with open(".tpcRunning_"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(tpcjob.id),str(finishtime)]))
        logger.debug("Temp Pause Charge revert jobid is: "+tpcjob.id)
        temp['result']="Charge paused for "+str(delay)+" seconds"
        updateControlCache("Temp_Pause_Charge","Running")
        updateControlCache("Battery_Charge_Rate",payload["chargeRate"])
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Pausing Charge failed: " + str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setEcoMode(device, payload, readloop=False):
    """Toggles the battery 'Eco Mode' setting (otherwise known as 'winter mode')

    Payload: {'state':'enable' or 'disable'}
    """
    temp={}
    try:
        logger.debug("Setting Eco Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state']=="enable":
            #temp=await sem(True,readloop)
            reqs=device.set_discharge_mode_to_match_demand()
            result= await sendAsyncCommand(reqs,readloop)
        else:
            #temp=await sem(False,readloop)
            reqs=device.set_discharge_mode_max_power()
            result= await sendAsyncCommand(reqs,readloop)
        if result:
            raise Exception(result['error'])
        else:
            updateControlCache("Eco_Mode",payload['state'])
            temp['result']="Setting Eco Mode "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Eco Mode failed: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setBatteryPauseMode(device, payload, readloop=False):
    """Sets the battery pause mode setting, (requires pauseslot to be set)

    Payload: {'state':'enable' or 'disable'}
    """
    temp={}
    try:
        logger.debug("Setting Battery Pause Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state'] in GivLUT.battery_pause_mode:
            val=GivLUT.battery_pause_mode.index(payload['state'])
            #temp= await sbpm(val,readloop)
            reqs=gecommands.set_battery_pause_mode(val)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            updateControlCache("Battery_pause_mode",str(GivLUT.battery_pause_mode[int(val)]))
            temp['result']="Setting Battery Pause Mode to " +str(GivLUT.battery_pause_mode[val])+" was a success"
            logger.info(temp['result'])
        else:
            temp['result']="Invalid Mode requested: "+ payload['state']
            logger.error(temp['result'])
    except:
        e=controlError()
        temp['result']="Error in setting Battery pause mode: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setLocalControlMode(device, payload, readloop=False):
    temp={}
    try:
        logger.debug("Setting Local Control Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state'] in GivLUT.local_control_mode:
            val=GivLUT.local_control_mode.index(payload['state'])
            #temp= await slcm(val,readloop)
        else:
            temp['result']="Invalid Mode requested: "+ payload['state']
            logger.error(temp['result'])
    except:
        e=controlError()
        temp['result']="Error in setting local control mode: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setBatteryMode(device, payload, readloop=False):
    """Sets the inverter operation mode 

    Payload: {'mode':'Eco' or 'Eco (Paused)' or 'Timed Demand' or 'Timed Export' or 'Export (Paused)'}
    """
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Battery Mode to: "+str(payload['mode']))
        if payload['mode']=="Eco":
            saved_battery_reserve = getSavedBatteryReservePercentage()
            reqs=device.set_mode_dynamic()
            #reqs.extend(device.set_battery_soc_reserve(saved_battery_reserve))
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            updateControlCache("Battery_Power_Reserve",saved_battery_reserve)
            temp['result']="Setting Eco mode was a success"
        elif payload['mode']=="Eco (Paused)":
            # set_mode_dynamic() also sets the reserve (HR110): replace that write rather than adding a second one,
            # as the second write to the same register in one batch cancels the first's response
            reserve=device.set_battery_soc_reserve(100)
            reserveRegs={getattr(r,'register',None) for r in reserve}
            reqs=[r for r in device.set_mode_dynamic() if getattr(r,'register',None) not in reserveRegs]+reserve
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Setting Eco (Paused) mode was a success"
        elif payload['mode']=="Timed Demand":
            #temp= await sbdmd(readloop)
            reqs=device.set_discharge_mode_to_match_demand()
            reqs.extend(device.set_enable_discharge(True))
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Setting Timed Demand mode was a success"            
            #temp= await ed(readloop)
        elif payload['mode']=="Timed Export":
            #temp= await sbdmmp(readloop)
            reqs=device.set_discharge_mode_max_power()
            reqs.extend(device.set_enable_discharge(True))
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Setting Timed Export mode was a success"
            #temp= await ed(readloop)
        elif payload['mode']=="Export (Paused)":
            # As read.getControls decodes it: max power (export) discharge mode, with discharge disabled
            reqs=device.set_discharge_mode_max_power()
            reqs.extend(device.set_enable_discharge(False))
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception(result['error'])
            temp['result']="Setting Export (Paused) mode was a success"
        else:
            temp['result']="Invalid Mode requested: "+ str(payload['mode'])
            logger.error (temp['result'])
            return json.dumps(temp)
        updateControlCache("Mode",payload['mode'])
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Battery Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def syncDateTime(device, payload, readloop=False):
    """Sync's the Inverter Date and Time to "now"

    Payload: None
    """
    temp={}
    targetresult="Success"
    #convert payload to dateTime components
    try:
        # Local time in GivTCP's timezone: the container's own clock can be UTC (eg. Docker without TZ), which would
        # leave the inverter an hour out in summer, and its Today counters resetting at 01:00
        iDateTime=datetime.now(GivLUT.timezone).replace(tzinfo=None)
        logger.debug("Syncing inverter time to: "+str(iDateTime))
        #Set Date and Time on inverter
        #temp= await sdt(iDateTime,readloop)
        reqs=device.set_system_date_time(iDateTime)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        temp['result']="Setting inverter time was a success"
        updateControlCache("Invertor_Time",iDateTime.strftime("%d-%m-%Y %H:%M:%S.%f"))
        logger.info(temp['result'])
        await asyncio.sleep(2)
        updateControlCache("Sync_Time","disable")
    except:
        e=controlError()
        temp['result']="Syncing inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDateTime(device, payload, readloop=False):
    """Sets the Inverter Date and Time in format: "%d/%m/%Y %H:%M:%S"

    Payload: {"dateTime":"'12/11/2021 09:15:32'"}
    """
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    #convert payload to dateTime components
    try:
        iDateTime=datetime.strptime(payload['dateTime'],"%d/%m/%Y %H:%M:%S")   #format '12/11/2021 09:15:32'
        logger.debug("Setting inverter time to: "+str(iDateTime))
        #Set Date and Time on inverter
        #temp= await sdt(iDateTime,readloop)
        reqs=device.set_system_date_time(iDateTime)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        temp['result']="Setting inverter time was a success"
        updateControlCache("Invertor_Time",iDateTime.strftime("%d-%m-%Y %H:%M:%S.%f"))
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryCalibration(device, payload, readloop=False):
    """Kicks off or Stops Battery Calibration

    Payload: {'state':'Off', 'Start' or "Charge Only"}
    """
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    if payload['state'] == "Off":
        val=0
    elif payload['state'] == "Start":
        val=1
    elif payload['state'] == "Charge Only":
        val=3
    else:
        logger.error(payload['state'] + " is not a valid control for Battery Calibration.")
        temp['result']="Setting Battery Calibration failed. Invaild control request."
        return json.dumps(temp)
    try:
        logger.debug("Setting Battery Calibration to: "+str(payload['state']))
        #temp= await sbc(val,readloop)
        reqs=device.set_calibrate_battery_soc(int(val))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        if val==0:
            updateControlCache("Battery_Calibration","disable")
        else:
            updateControlCache("Battery_Calibration","enable")
        temp['result']="Setting Battery Calibration "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Battery Calibration failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def switchRate(device, payload, readloop=False):
    """Reboots the Home Assistant Addon via Supervisor

    Payload: "day" or "night"
    """
    temp={}
    if GiV_Settings.dynamic_tariff == False:     # Only allow this control if Dynamic control is enabled
        temp['result']="External rate setting not allowed. Enable Dynamic Tariff in settings"
        logger.error(temp['result'])
        return json.dumps(temp)
    try:
        if payload.lower()=="day":
            open(GivLUT.dayRateRequest, 'w').close()
            logger.info ("Setting dayRate via external trigger")
        else:
            open(GivLUT.nightRateRequest, 'w').close()
            logger.info ("Setting nightRate via external trigger")
    except:
        e=controlError()
        temp['result']="Setting Rate failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def rebootAddon(device=None,payload=None,readloop=False):     # matches the read loop's func(device,payload,True) call
    """Reboots the Home Assistant Addon via Supervisor

    Inputs: None
    """
    temp={}
    try:
        logger.critical("Restarting the GivTCP Addon in 2s...")
        time.sleep(2)
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
    except:
        e=controlError()
        temp['result']="Failed to reboot GivTCP: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(result)

def getSavedBatteryReservePercentage():
    saved_battery_reserve=4
    if exists(GivLUT.reservepkl):
        with open(GivLUT.reservepkl, 'rb') as inp:
            saved_battery_reserve= pickle.load(inp)
    return saved_battery_reserve

async def enableDischarge(device,payload,readloop=False):
    """Enable or disable battery discharge, by setting the battery reserve to the saved reserve
    percentage (enable) or 100% (disable)

    Payload: {'state':'enable' or 'disable'}
    """
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state']=="enable":
            target=getSavedBatteryReservePercentage()
        else:
            target=100
        logger.debug("Setting discharge "+str(payload['state'])+" (battery reserve "+str(target)+"%)")
        reqs=device.set_battery_soc_reserve(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result['error'])
        updateControlCache("Battery_Power_Reserve",target)
        temp['result']="Setting Discharge "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Discharge "+str(payload.get('state') if isinstance(payload,dict) else payload)+" failed: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setPVInputMode(device,payload,readloop=False):
    """Set the PV input mode (three-phase)

    Payload: {'state':'Independent' or '1x2'}
    """
    temp={}
    try:
        # givenergy-modbus reads pv_input_mode (3PH HR1077) but has no writer for it yet
        raise NotImplementedError("Setting the PV Input Mode is not yet supported by givenergy-modbus")
    except:
        e=controlError()
        temp['result']="Setting PV Input Mode failed: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

##### ARCHIVED FUNCTIONS FOR REVIEW OR REMOVAL ######
'''
async def enableDischarge(payload,readloop=False):
    temp={}
    saved_battery_reserve = getSavedBatteryReservePercentage()
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Discharge")
            temp= await ssc(saved_battery_reserve,readloop)
            updateControlCache("Enable_Discharge","enable")
        elif payload['state']=="disable":
            logger.debug("Disabling Discharge")
            temp= await ssc(100,readloop)
            updateControlCache("Enable_Discharge","disable")
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Discharge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setShallowCharge(payload,readloop=False):
    temp={}
    try:
        logger.debug("Setting Shallow Charge to: "+ str(payload['val']))
        temp= await ssc(int(payload['val']),readloop)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting shallow charge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPVInputMode(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting PV Input mode to: "+ str(payload['state']))
        if payload['state'] in GivLUT.pv_input_mode:
            temp= await spvim(GivLUT.pv_input_mode.index(payload['state']),readloop)
            temp['result']="Setting PV Input Mode was a success"
        else:
            logger.error ("Invalid Mode requested: "+ payload['state'])
            temp['result']="Invalid Mode requested"
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting PV Input Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setCarChargeBoost(payload, readloop=False):
    temp={}
    targetresult="Success"
    val=payload['boost']
    try:
        logger.debug("Setting Car Charge Boost to: "+str(val)+"w")
        temp= await sccb(val,readloop)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Car Charge Boost failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportLimit(val, readloop=False):
    temp={}
    targetresult="Success"
    try:
        logger.debug("Setting Export Limit to: "+str(val)+"w")
        #Set Date and Time on inverter
        temp= await sel(val,readloop)
        logger.info(temp['result'])
    except:
        e=controlError()
        temp['result']="Setting Export Limit failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)
'''

if __name__ == '__main__':
    if len(sys.argv)==2:
        globals()[sys.argv[1]]()
    elif len(sys.argv)==3:
        globals()[sys.argv[1]](sys.argv[2])
