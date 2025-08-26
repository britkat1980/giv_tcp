# -*- coding: utf-8 -*-
# version 2022.01.31
import sys
import json
import logging
import datetime
from datetime import datetime, timedelta
from settings import GiV_Settings
import settings
import time
from os.path import exists
import pickle,os
import GivLUT
from GivLUT import GivLUT, GivQueue
from givenergy_modbus_async.client import commands
from givenergy_modbus_async.model import TimeSlot
from givenergy_modbus_async.pdu import WriteHoldingRegisterResponse, TransparentRequest
import requests
import importlib
import asyncio
from logging.handlers import TimedRotatingFileHandler

from GivLUT import GivClientAsync

logging.getLogger("givenergy_modbus_async").setLevel(logging.CRITICAL)

 
logging.basicConfig(format='%(asctime)s - Inv'+ str(GiV_Settings.givtcp_instance)+ \
                    ' - %(module)-11s -  [%(levelname)-8s] - %(message)s')
formatter = logging.Formatter(
    '%(asctime)s - %(module)s - [%(levelname)s] - %(message)s')
fhw = TimedRotatingFileHandler(GiV_Settings.Debug_File_Location_Write, when='midnight', backupCount=7)
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

async def sendAsyncCommand(reqs,readloop):
    output={}
    asyncclient=await GivClientAsync.get_connection()
    if not asyncclient.connected:
        logger.info("Write client not connected after import")
        await asyncclient.connect()

    result= await asyncclient.execute(reqs,timeout=3,retries=6, return_exceptions=True)
    for idx, req in enumerate(result):
        if not isinstance(req,WriteHoldingRegisterResponse):
            output['error']="Error in write command: HR("+str(reqs[idx].register)+")"
            output['error_type']=type(req).__name__
            break
    if not readloop:
        #if write command came from somewhere other than the read loop then close the connection at the end
        logger.info("Closing non readloop modbus connection")
        await asyncclient.close()
    log_num_writes(reqs)
    return output

async def sbcla(target,readloop=False):
    temp={}
    try:
        reqs=commands.set_battery_charge_limit_ac(target, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Charge_Rate_AC",target)
        temp['result']="Setting battery charge rate AC to "+str(target)+"% was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery charge rate "+str(target)+" failed"
        logger.error(temp['result'])
    return temp

async def sbdla(target,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_battery_discharge_limit_ac(target, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Discharge_Rate_AC",target)
        temp['result']="Setting battery discharge rate AC to "+str(target)+"% was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery discharge rate "+str(target)+" failed"
        logger.error(temp['result'])
    return temp

async def setForceCharge(payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling Force Charge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        reqs=commands.set_force_charge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Force Charge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setForceDischarge(payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling Force Discharge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        reqs=commands.set_force_discharge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Force Discharge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setACCharge(payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling AC Charge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        reqs=commands.set_ac_charge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting AC Charge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def enableDischargeSchedule(payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Disharge Schedule")
            #temp= await ed(readloop)
            reqs=commands.set_enable_discharge(True,GiV_Settings.inverter_type.lower())
        elif payload['state']=="disable":
            logger.debug("Disabling Discharge Schedule")
            #temp= await dd(readloop)
            reqs=commands.set_enable_discharge(False,GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception   
        updateControlCache("Enable_Discharge_Schedule",payload['state'])
        temp['result']="Setting Discharge Schedule to "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Schedule failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def enableChargeSchedule(payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Charge Schedule")
            #temp= await ec(readloop)
            reqs=commands.set_enable_charge(True,GiV_Settings.inverter_type.lower())
        elif payload['state']=="disable":
            logger.debug("Disabling Charge Schedule")
            #temp= await dc(readloop)
            reqs=commands.set_enable_charge(False,GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception        
        updateControlCache("Enable_Charge_Schedule",payload['state'])
        temp['result']="Setting Charge Schedule to "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting charge schedule "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)



async def enableRTC(payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Real Time Control")
            #temp= await ect(readloop)
            reqs=commands.set_enable_rtc(True,GiV_Settings.inverter_type.lower())
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception
            temp['result']="Enabling Real Time Control was a success"
        elif payload['state']=="disable":
            logger.debug("Disabling Real Time Control")
            #temp= await dct(readloop)
            reqs=commands.set_enable_rtc(False,GiV_Settings.inverter_type.lower())
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception           
            temp['result']="Disabling Real Time Control was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Real Time Control failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)


async def enableChargeTarget(payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Charge Target")
            #temp= await ect(readloop)
            reqs=commands.enable_charge_target()
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception           
            temp['result']="Enabling Charge Target was a success"
        elif payload['state']=="disable":
            logger.debug("Disabling Charge Target")
            #temp= await dct(readloop)
            reqs=commands.disable_charge_target()
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception           
            temp['result']="Disabling Charge Target was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeTarget(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeToPercent'])
        logger.debug("Setting Charge Target to: "+str(target))
        #temp=await sct(target,readloop)
        reqs=commands.set_charge_target_only(int(target), inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Target_SOC",target)
        temp['result']="Setting Charge Target "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeTarget2(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Charge Target "+str(slot) + " to: "+str(target))
        reqs=commands.set_soc_target(False,slot,int(target),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_Target_SOC_"+str(slot),target)
        else:
            updateControlCache("Charge_Target_SOC_"+str(slot),target)
        #temp= await sst(target,slot,readloop)
        temp['result']="Setting Charge Target "+str(slot) + " was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportTarget(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['exportToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Export Target "+str(slot) + " to: "+str(target))
        #temp= await sest(target,slot,readloop)
        reqs=commands.set_export_soc_target(slot,int(target))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        temp['result']="Setting Export Target "+str(slot) + " was a success"
        updateControlCache("Export_Target_SOC_"+str(slot),target)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeTarget(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Discharge Target "+str(slot) + " to: "+str(target))
        #temp= await sdct(target,slot,readloop)
        reqs=commands.set_soc_target(True,slot,int(target),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_Target_SOC_"+str(slot),target)
        else:
            updateControlCache("Discharge_Target_SOC_"+str(slot),target)
        temp['result']="Setting Discharge Target "+str(slot) + " was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setEmsPlant(payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling EMS Plant Operation")
            #temp= await ect(readloop)
            reqs=commands.set_ems_plant(True)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception           
            temp['result']="Enabling EMS Plant Operation was a success"
        elif payload['state']=="disable":
            logger.debug("Disabling EMS Plant Operation")
            #temp= await dct(readloop)
            reqs=commands.set_ems_plant(False)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception           
            temp['result']="Disabling EMS Plant Operation was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting EMS Plant Operation failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryReserve(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['reservePercent'])
        #Only allow minimum of 4%
        if target<4: target=4
        logger.debug ("Setting battery reserve target to: " + str(target))
        #temp= await ssc(target,readloop)
        reqs=commands.set_battery_soc_reserve(target, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Power_Reserve",target)
        temp['result']="Setting battery reserve "+str(target)+" was a success"        
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Reserve failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryCutoff(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeToPercent'])
        #Only allow minimum of 4%
        if target<4: target=4
        logger.debug ("Setting battery cutoff target to: " + str(target))
        #temp= await sbpr(target,readloop)
        reqs=commands.set_battery_power_reserve(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Power_Cutoff",target)
        temp['result']="Setting battery power reserve to "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Cutoff failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def rebootinverter(payload,readloop=False):
    temp={}
    try:
        logger.debug("Rebooting inverter...")
        #temp= await ri(readloop)
        reqs=commands.set_inverter_reboot()
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        temp['result']="Rebooting Inverter was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Reboot inverter failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setActivePowerRate(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['activePowerRate'])
        logger.debug("Setting Active Power Rate to "+str(target))
        #temp= await sapr(target,readloop)
        reqs=commands.set_active_power_rate(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Active_Power_Rate",target)
        temp['result']="Setting active power rate "+str(target)+" was a success"        
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Active Power Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeRate(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    
    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        regCacheStack=GivLUT.get_regcache()
        multi_output_old = regCacheStack[-1]
        invmaxrate=finditem(multi_output_old,'Invertor_Max_Bat_Rate')
        batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
        try:
            if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
                target= round((int(payload['chargeRate'])/invmaxrate)*100,0)
                logger.debug ("Setting battery charge rate ac to: " + str(payload['chargeRate'])+" ("+str(target)+")")
                reqs=commands.set_battery_charge_limit_ac(target, inv_type=GiV_Settings.inverter_type.lower())
            else:
                if int(payload['chargeRate']) < int(invmaxrate):
                    target=int(min((int(payload['chargeRate'])/(batcap/2))*50,50))
                else:
                    target=50
                logger.debug ("Setting battery charge rate to: " + str(payload['chargeRate'])+" ("+str(target)+")")
                #temp= await sbcl(target,readloop)
                reqs=commands.set_battery_charge_limit(target)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception
            if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
                updateControlCache("Battery_Charge_Rate_AC",target)
                updateControlCache("Battery_Charge_Rate",int(payload['chargeRate']))
            else:
                val=int(min((target/100)*(batcap), invmaxrate))
                updateControlCache("Battery_Charge_Rate",val)
            temp['result']="Setting battery charge rate "+str(payload['chargeRate'])+" was a success"
            logger.info(temp['result'])
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            temp['result']="Setting Charge Rate failed: " + str(e)
            logger.error (temp['result'])
    else:
        temp['result']="Setting Charge Rate failed: No charge rate limit available"
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeRateAC(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeRate'])
        logger.debug ("Setting AC battery charge rate to: " + str(target))
        temp= await sbcla(target,readloop)
        if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
            # Recreate Battery Watt rate and push to MQTT
            regCacheStack=GivLUT.get_regcache()
            multi_output_old = regCacheStack[-1]
            invmaxrate=finditem(multi_output_old,'Invertor_Max_Bat_Rate')
            val=int((target/100)*invmaxrate)
            updateControlCache("Battery_Charge_Rate",val)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting AC Battery Charge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeRate(payload,readloop=False):

## Make this work for 3PH using ratio for limit_ac
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        regCacheStack=GivLUT.get_regcache()
        multi_output_old = regCacheStack[-1]
        invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
        batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
        try:
            if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
                target= round((int(payload['dischargeRate'])/invmaxrate)*100,0)
                reqs=commands.set_battery_discharge_limit_ac(target, inv_type=GiV_Settings.inverter_type.lower())
            else:
                if int(payload['dischargeRate']) < int(invmaxrate):
                    target=int(min((int(payload['dischargeRate'])/(batcap/2))*50,50))
                else:
                    target=50
                #temp= await sbdl(target,readloop)
                reqs=commands.set_battery_discharge_limit(target)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception
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
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            temp['result']="Setting Discharge Rate failed: " + str(e)
            logger.error (temp['result'])
    else:
        temp['result']="Setting Discharge Rate failed: No discharge rate limit available"
        logger.error (temp['result'])        
    return json.dumps(temp)

async def setDischargeRateAC(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeRate'])
        logger.debug ("Setting AC battery discharge rate to: " + str(target))
        temp= await sbdla(target,readloop)
        if "3ph" in GiV_Settings.inverter_type.lower() or "gateway" in GiV_Settings.inverter_type.lower():
            # Recreate Battery Watt rate and push to MQTT
            regCacheStack=GivLUT.get_regcache()
            multi_output_old = regCacheStack[-1]
            invmaxrate=finditem(multi_output_old,'Invertor_Max_Bat_Rate')
            val=int((target/100)*invmaxrate)
            updateControlCache("Battery_Discharge_Rate",val)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting AC battery discharge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlot(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Charge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        #temp= await scs(payload,readloop)
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        reqs=commands._set_charge_slot(False,int(payload['slot']),slot,GiV_Settings.inverter_type.lower())
        if 'chargeToPercent' in payload.keys():
            reqs.extend(commands.set_charge_target_only(int(payload['chargeToPercent']), inv_type=GiV_Settings.inverter_type.lower()))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("EMS_Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseSlot(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Battery Pause slot to: "+str(payload['start'])+" - "+str(payload['finish']))
        #temp= await sps(payload,readloop)
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        reqs=commands.set_pause_slot(slot)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_pause_start_time_slot",str(datetime.strptime(payload['start'],"%H:%M")))
        updateControlCache("Battery_pause_end_time_slot",str(datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Pause Slot to: "+str(payload['start'])+" - "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Pause Slot failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlotStart(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Charge Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        #temp= await scss(payload,readloop)
        reqs=commands.set_charge_slot_start(False,int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        else:
            updateControlCache("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" Start to: "+str(payload['start'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlotEnd(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Charge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        #temp= await scse(payload,readloop)
        reqs=commands.set_charge_slot_end(False,int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Charge Slot End "+str(payload['slot'])+" to: "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlotStart(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        #temp= await sess(payload,readloop)
        reqs=commands.set_export_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception        
        updateControlCache("Export_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Export Slot "+str(payload['slot'])+" Start to: "+str(payload['start'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlotEnd(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        #temp= await sese(payload,readloop)
        reqs=commands.set_export_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception         
        updateControlCache("Export_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Export Slot End "+str(payload['slot'])+" to: "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlot(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    # Should this include DischargePercent, or drop?
    if 'dischargeToPercent' in payload.keys():
        pload={}
        pload['reservePercent']=payload['dischargeToPercent']
        result=await setBatteryReserve(pload,readloop)
    try:

        logger.debug("Setting Discharge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        #temp= await sds(payload,readloop)
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        reqs=commands._set_charge_slot(True,int(payload['slot']),slot,GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("EMS_Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlot(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        #temp= await ses(payload,readloop)
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        reqs=commands.set_export_slot(int(payload['slot']),slot)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Export_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        updateControlCache("Export_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Export Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlotStart(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Discharge Slot start "+str(payload['slot'])+" Start to: "+str(payload['start']))
        #temp= await sdss(payload,readloop)
        reqs=commands.set_charge_slot_start(True,int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot start "+str(payload['slot'])+" Start to: "+str(payload['start'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot start "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlotEnd(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Discharge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        #temp= await sdse(payload,readloop)
        reqs=commands.set_charge_slot_end(True,int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" to: "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseStart(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Pause Slot Start to: "+str(payload['start']))
        #temp= await spss(payload,readloop)
        reqs=commands.set_pause_slot_start(datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result)
        updateControlCache("Battery_pause_start_time_slot",str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Pause Slot Start to: "+str(payload['start'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot Start failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseEnd(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Pause Slot End to: "+str(payload['finish']))
        #temp= await spse(payload,readloop)
        reqs=commands.set_pause_slot_end(datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result)
        updateControlCache("Battery_pause_end_time_slot",str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Pause Slot End to: "+str(payload['finish'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot End failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def FEResume(revert, readloop=False):
    temp={}
    try:
        logger.info("Reverting Force Export settings:")
        payload={}
        payload["mode"]=revert["mode"]
        result=await setBatteryMode(payload,readloop)
        reqs=commands.set_battery_soc_reserve(revert["reservePercent"],GiV_Settings.inverter_type.lower())
        slot=TimeSlot
        slot.start=datetime.strptime(revert['start_time'],"%H:%M")
        slot.end=datetime.strptime(revert['end_time'],"%H:%M")
        reqs.extend(commands._set_charge_slot(True,1,slot,GiV_Settings.inverter_type.lower()))
        if revert["discharge_schedule"]=="enable":
            enabled=True
        else:
            enabled=False
        reqs.extend(commands.set_enable_discharge(enabled,GiV_Settings.inverter_type.lower()))
        if "dischargeRate" in revert:
            target=50
            if exists(GivLUT.regcache):      # if there is a cache then grab it
                regCacheStack=GivLUT.get_regcache()
                multi_output_old = regCacheStack[-1]
                invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
                batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
                if int(revert['dischargeRate']) < int(invmaxrate):
                    target=int(min((int(revert['dischargeRate'])/(batcap/2))*50,50))
            reqs.extend(commands.set_battery_discharge_limit(target))
        elif "dischargeRateAC" in revert:
            reqs.extend(commands.set_battery_discharge_limit_ac(revert["dischargeRateAC"]),GiV_Settings.inverter_type)
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(commands.set_force_discharge(revert["forceDischargeEnable"]))  # turn on Force Export in 3PH
            reqs.extend(commands.set_force_charge(revert["forceChargeEnable"]))  # turn off Force Charge in 3PH
        if "batteryPauseMode" in revert:
            reqs.extend(commands.set_battery_pause_mode(GivLUT.battery_pause_mode.index(revert["batteryPauseMode"])))
        
        result = await sendAsyncCommand(reqs,readloop)
        if result:
            logger.error("Errors in control commands: "+str(result))
            raise Exception(result)
        frtouch()
        os.remove(".FERunning"+str(GiV_Settings.givtcp_instance))
        updateControlCache("Force_Export","Normal")
        temp['result']="Force Export Reverted successfully"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Force Export Revert failed: " + str(e)
        os.remove(".FERunning"+str(GiV_Settings.givtcp_instance))
        logger.error (temp['result'])
    return json.dumps(temp)

async def forceExport(exportTime,readloop=False):
    temp={}
    logger.info("Forcing Export for "+str(exportTime)+" minutes")
    try:
        result={}
        revert={}
        hasBPM=False
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            regCacheStack=GivLUT.get_regcache()
            revert["start_time"]=regCacheStack[-1]["Timeslots"]["Discharge_start_time_slot_1"][:5]
            revert["end_time"]=regCacheStack[-1]["Timeslots"]["Discharge_end_time_slot_1"][:5]
            revert["reservePercent"]=regCacheStack[-1]["Control"]["Battery_Power_Reserve"]
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

        reqs=commands.set_battery_soc_reserve(4,GiV_Settings.inverter_type.lower())
        finish=GivLUT.getTime(datetime.now()+timedelta(minutes=exportTime))
        slot=TimeSlot
        slot.start=datetime.strptime(GivLUT.getTime(datetime.now()),"%H:%M")
        slot.end=datetime.strptime(finish,"%H:%M")

        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(commands.set_force_discharge(True))  # turn on Force Export in 3PH
            reqs.extend(commands.set_force_charge(False))  # turn off Force Charge in 3PH
            reqs.extend(commands.set_battery_discharge_limit_ac(100,GiV_Settings.inverter_type.lower()))
        else:
            reqs.extend(commands.set_battery_discharge_limit(50))
        reqs.extend(commands.set_mode_storage(discharge_slot_1=slot,discharge_for_export=True, inv_type=GiV_Settings.inverter_type.lower()))
        if hasBPM:
            reqs.extend(commands.set_battery_pause_mode(0))
        result = await sendAsyncCommand(reqs,readloop)
        frtouch()   #Force full refresh on next run to update control status
        if result:
            logger.error("Errors in control commands: "+str(result))
            raise Exception(result)
        if exists(".FERunning"+str(GiV_Settings.givtcp_instance)):    # If a forcecharge is already running, change time of revert job to new end time.
            logger.info("Force Export already running, changing end time")
            revert=getFEArgs()[0]   # set new revert object and cancel old revert job
            logger.debug("new revert= "+ str(revert))
        fejob=GivQueue.q.enqueue_in(timedelta(minutes=exportTime),FEResume,revert)
        with open(".FERunning"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(fejob.id),str(finish)]))
        logger.debug("Force Export revert jobid is: "+fejob.id)
        temp['result']="Export successfully forced for "+str(exportTime)+" minutes"
        updateControlCache("Force_Export","Running")
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Force Export failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def FCResume(revert,readloop=False):
    payload={}
    temp={}
    try:
        logger.info("Reverting Force Charge Settings:")
        if "chargeRate" in revert:
            if exists(GivLUT.regcache):      # if there is a cache then grab it
                regCacheStack=GivLUT.get_regcache()
                multi_output_old = regCacheStack[-1]
                invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
                batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
                if "3ph" in GiV_Settings.inverter_type.lower():
                    target= round(int(revert['chargeRate'])/invmaxrate,0)
                    temp = await sbcla(target, readloop)
                else:
                    if int(revert['chargeRate']) < int(invmaxrate):
                        target=int(min((int(revert['chargeRate'])/(batcap/2))*50,50))
                    else:
                        target=50
            reqs=commands.set_battery_charge_limit(target)
        elif "chargeRateAC" in revert:
            reqs=commands.set_battery_charge_limit_ac(revert["chargeRateAC"])
        if revert["chargeScheduleEnable"]=="enable":
            enable=True
        else:
            enable=False
        reqs.extend(commands.set_enable_charge(enable))
        slot=TimeSlot
        slot.start=datetime.strptime(revert['start_time'],"%H:%M")
        slot.end=datetime.strptime(revert['end_time'],"%H:%M")
        reqs.extend(commands._set_charge_slot(False,1,slot,GiV_Settings.inverter_type))
        reqs.extend(commands.set_charge_target_only(int(revert["targetSOC"]), inv_type=GiV_Settings.inverter_type.lower()))
        if "batteryPauseMode" in revert:
            reqs.extend(commands.set_battery_pause_mode(GivLUT.battery_pause_mode.index(revert["batteryPauseMode"])))
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(commands.set_force_discharge(revert["forceDischargeEnable"]))  # turn back Force Export in 3PH
            reqs.extend(commands.set_force_charge(revert["forceChargeEnable"]))  # turn back Force Charge in 3PH
            reqs.extend(commands.set_ac_charge(revert["forceACChargeEnable"]))  # turn back AC Charge enable in 3PH

        result = await sendAsyncCommand(reqs,readloop)
        if result:
            logger.error("Errors in control commands: "+str(result))
            raise Exception(result)
        frtouch()        
        os.remove(".FCRunning"+str(GiV_Settings.givtcp_instance))
        updateControlCache("Force_Charge","Normal")
        temp['result']="Force Charge Reverted successfully"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("Force Charge revert failed: "+str(e))
        temp['result']="Force Charge revert failed: "+str(e)
        os.remove(".FCRunning"+str(GiV_Settings.givtcp_instance))
        logger.error(temp['result'])
    return json.dumps(temp)

def cancelJob(jobid, readloop=False):
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
    details=job.args
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
    details=job.args
    logger.debug("Previous args= "+str(details))
    GivQueue.q.scheduled_job_registry.remove(jobid) # Remove the job from the schedule
    return (details)

async def forceCharge(chargeTime, readloop=False):
    temp={}
    logger.info("Forcing Charge for "+str(chargeTime)+" minutes")
    try:
        revert={}
        regCacheStack = GivLUT.get_regcache()
        hasBPM=False
        if "regCacheStack" in locals():
            revert["start_time"]=regCacheStack[-1]["Timeslots"]["Charge_start_time_slot_1"][:5]
            revert["end_time"]=regCacheStack[-1]["Timeslots"]["Charge_end_time_slot_1"][:5]
            if "Battery_Charge_Rate" in regCacheStack[-1]["Control"]:
                revert["chargeRate"]=regCacheStack[-1]["Control"]["Battery_Charge_Rate"]
            elif "Battery_Charge_Rate_AC" in regCacheStack[-1]["Control"]:
                revert["chargeRateAC"]=regCacheStack[-1]["Control"]["Battery_Charge_Rate_AC"]
            revert["targetSOC"]=regCacheStack[-1]["Control"]["Target_SOC"]
            revert["chargeScheduleEnable"]=regCacheStack[-1]["Control"]["Enable_Charge_Schedule"]
            if "Battery_pause_mode" in regCacheStack[-1]["Control"]:
                revert["batteryPauseMode"]=regCacheStack[-1]["Control"]["Battery_pause_mode"]
                hasBPM=True
            if "Force_Charge_Enable" in regCacheStack[-1]["Control"]:
                revert['forceChargeEnable']= regCacheStack[-1]["Control"]["Force_Charge_Enable"]
            if "Force_AC_Charge_Enable" in regCacheStack[-1]["Control"]:
                revert['forceACChargeEnable']= regCacheStack[-1]["Control"]["Force_AC_Charge_Enable"]

        finish=GivLUT.getTime(datetime.now()+timedelta(minutes=chargeTime))
        reqs=commands.set_charge_target_only(100,GiV_Settings.inverter_type.lower())
        slot=TimeSlot
        slot.start=datetime.strptime(GivLUT.getTime(datetime.now()),"%H:%M")
        slot.end=datetime.strptime(finish,"%H:%M")
        reqs.extend(commands._set_charge_slot(False,1,slot, inv_type=GiV_Settings.inverter_type.lower()))
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(commands.set_battery_charge_limit_ac(100,GiV_Settings.inverter_type.lower()))
            reqs.extend(commands.set_force_charge(True))
            reqs.extend(commands.set_ac_charge(True))
        else:
            reqs.extend(commands.set_enable_charge(True))
            reqs.extend(commands.set_battery_charge_limit(50))

        # Set Battery Pause Mode only if it exists
        if hasBPM:
            reqs.extend(commands.set_battery_pause_mode(0))
        result= await sendAsyncCommand(reqs,readloop)
        frtouch()   #Force full refresh on next run to update control status
        if result:
            logger.error("Errors in control commands: "+str(result))
            raise Exception(result)
        if exists(".FCRunning"+str(GiV_Settings.givtcp_instance)):    # If a forcecharge is already running, change time of revert job to new end time
            logger.info("Force Charge already running, changing end time")
            revert=getFCArgs()[0]   # set new revert object and cancel old revert job
            logger.critical("new revert= "+ str(revert))
        fcjob=GivQueue.q.enqueue_in(timedelta(minutes=chargeTime),FCResume,revert)
        with open(".FCRunning"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(fcjob.id),str(finish)]))
        logger.debug("Force Charge revert jobid is: "+fcjob.id)
        temp['result']="Charge successfully forced for "+str(chargeTime)+" minutes"
        updateControlCache("Force_Charge","Running")

        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Force charge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tmpPDResume(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Reverting Temp Pause Discharge")
        result=await setDischargeRate(payload,readloop)
        if exists(".tpdRunning_"+str(GiV_Settings.givtcp_instance)): os.remove(".tpdRunning_"+str(GiV_Settings.givtcp_instance))
        temp['result']="Temp Pause Discharge Reverted"
        updateControlCache("Temp_Pause_Discharge","Normal")
        updateControlCache("Battery_Discharge_Rate",payload["dischargeRate"])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Temp Pause Discharge Resume failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tempPauseDischarge(pauseTime,readloop=False):
    """Pauses discharge from battery for the defined duration in minutes

    Payload: 2
    """
    temp={}
    try:
        logger.debug("Pausing Discharge for "+str(pauseTime)+" minutes")
        #Update read data via pickle
        regCacheStack = GivLUT.get_regcache()
        if "regCacheStack" in locals():
            multi_output_old = regCacheStack[-1]
            revertRate=regCacheStack[-1]["Control"]["Battery_Discharge_Rate"]
        else:
            revertRate=2600
            
        payload={}
        payload['dischargeRate']=0
        result=await setDischargeRate(payload,readloop)
        payload['dischargeRate']=revertRate
        delay=float(pauseTime*60)
        tpdjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),tmpPDResume,payload)
        finishtime=GivLUT.getTime(datetime.now()+timedelta(minutes=pauseTime))
        with open(".tpdRunning_"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(tpdjob.id),str(finishtime)]))
        
        logger.debug("Temp Pause Discharge revert jobid is: "+tpdjob.id)
        temp['result']="Discharge paused for "+str(delay)+" seconds"
        updateControlCache("Temp_Pause_Discharge","Running")
        updateControlCache("Battery_Discharge_Rate",payload["dischargeRate"])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Pausing Discharge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tmpPCResume(payload,readloop=False):
    """Reverts inverter settings after TempPauseCharge.

    Payload: {}
    """
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Reverting Temp Pause Charge...")
        result=await setChargeRate(payload,readloop)
        if exists(".tpcRunning_"+str(GiV_Settings.givtcp_instance)): os.remove(".tpcRunning_"+str(GiV_Settings.givtcp_instance))
        temp['result']="Temp Pause Charge Reverted"
        updateControlCache("Temp_Pause_Charge","Normal")
        updateControlCache("Battery_Charge_Rate",payload["chargeRate"])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Temp Pause Charge Resume failed: " + str(e)
        logger.error (temp['result'])
    return json.dump(temp)

async def tempPauseCharge(pauseTime, readloop=False):
    """Pauses charge to battery for the defined duration in minutes

    Payload: 2
    """
    temp={}
    try:
        logger.debug("Pausing Charge for "+str(pauseTime)+" minutes")
        regCacheStack = GivLUT.get_regcache()
        if "regCacheStack" in locals():
            revertRate=regCacheStack[-1]["Control"]["Battery_Charge_Rate"]
        else:
            revertRate=2600
        payload={}
        payload['chargeRate']=0
        result=await setChargeRate(payload,readloop)
        payload['chargeRate']=revertRate
        delay=float(pauseTime*60)
        finishtime=GivLUT.getTime(datetime.now()+timedelta(minutes=pauseTime))
        tpcjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),tmpPCResume,payload)
        with open(".tpcRunning_"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(tpcjob.id),str(finishtime)]))
        logger.debug("Temp Pause Charge revert jobid is: "+tpcjob.id)
        temp['result']="Charge paused for "+str(delay)+" seconds"
        updateControlCache("Temp_Pause_Charge","Running")
        updateControlCache("Battery_Charge_Rate",payload["chargeRate"])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Pausing Charge failed: " + str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setEcoMode(payload,readloop=False):
    """Toggles the battery 'Eco Mode' setting (otherwise known as 'winter mode')

    Payload: {'state':'enable' or 'disable'}
    """
    temp={}
    try:
        logger.debug("Setting Eco Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state']=="enable":
            #temp=await sem(True,readloop)
            reqs=commands.set_eco_mode(True)
            result= await sendAsyncCommand(reqs,readloop)
        else:
            #temp=await sem(False,readloop)
            reqs=commands.set_eco_mode(False)
            result= await sendAsyncCommand(reqs,readloop)
        if result:
            raise Exception
        else:
            updateControlCache("Eco_Mode",payload['state'])
            temp['result']="Setting Eco Mode "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()
        temp['Result']="Error in setting Eco mode: "+result['error_type']
        logger.error(temp['result'])
    return json.dumps(temp)

async def setBatteryPauseMode(payload,readloop=False):
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
            reqs=commands.set_battery_pause_mode(val)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception 
            updateControlCache("Battery_pause_mode",str(GivLUT.battery_pause_mode[int(val)]))
            temp['result']="Setting Battery Pause Mode to " +str(GivLUT.battery_pause_mode[val])+" was a success"
            logger.info(temp['result'])
        else:
            temp['result']="Invalid Mode requested: "+ payload['state']
            logger.error(temp['result'])
    except:
        e=sys.exc_info()
        temp['Result']="Error in setting Battery pause mode: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setLocalControlMode(payload,readloop=False):
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
        e=sys.exc_info()
        temp['Result']="Error in setting local control mode: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setBatteryMode(payload,readloop=False):
    """Sets the inverter operation mode 

    Payload: {'mode':'Eco' or 'Eco (Paused)' or 'Timed Demand' or 'Timed Export'}
    """
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Battery Mode to: "+str(payload['mode']))
        if payload['mode']=="Eco":
            #temp= await smd(False,readloop)
            saved_battery_reserve = getSavedBatteryReservePercentage()
            #temp= await ssc(saved_battery_reserve,readloop)
            reqs=commands.set_mode_dynamic(False)
            reqs.extend(commands.set_battery_soc_reserve(saved_battery_reserve, inv_type=GiV_Settings.inverter_type.lower()))
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception
            updateControlCache("Battery_Power_Reserve",saved_battery_reserve)
            temp['result']="Setting Eco mode was a success"
        elif payload['mode']=="Eco (Paused)":
            reqs=commands.set_mode_dynamic(True)
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception
            temp['result']="Setting dynamic mode was a success"
        elif payload['mode']=="Timed Demand":
            #temp= await sbdmd(readloop)
            reqs=commands.set_mode_storage(discharge_for_export=False, inv_type=GiV_Settings.inverter_type.lower())
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception
            temp['result']="Setting Timed Demand mode was a success"            
            #temp= await ed(readloop)
        elif payload['mode']=="Timed Export":
            #temp= await sbdmmp(readloop)
            reqs=commands.set_mode_storage(discharge_for_export=True, inv_type=GiV_Settings.inverter_type.lower())
            result= await sendAsyncCommand(reqs,readloop)
            if 'error' in result:
                raise Exception
            temp['result']="Setting Timed Export mode was a success"
            #temp= await ed(readloop)
        else:
            temp['result']="Invalid Mode requested"+ payload['mode']
            logger.error (temp['result'])
            return json.dumps(temp)
        updateControlCache("Mode",payload['mode'])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def syncDateTime(payload,readloop=False):
    """Sync's the Inverter Date and Time to "now"

    Payload: None
    """
    temp={}
    targetresult="Success"
    #convert payload to dateTime components
    try:
        iDateTime=datetime.now()   #format '12/11/2021 09:15:32'
        logger.debug("Syncing inverter time to: "+str(iDateTime))
        #Set Date and Time on inverter
        #temp= await sdt(iDateTime,readloop)
        reqs=commands.set_system_date_time(iDateTime)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        temp['result']="Setting inverter time was a success"
        updateControlCache("Invertor_Time",iDateTime.strftime("%d-%m-%Y %H:%M:%S.%f"))
        logger.info(temp['result'])
        await asyncio.sleep(2)
        updateControlCache("Sync_Time","disable")
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Syncing inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDateTime(payload,readloop=False):
    """Sets the Inverter Date and Time in format: "%d/%m/%Y %H:%M:%S"

    Payload: {"dateTime":"'12/11/2021 09:15:32'"}
    """
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    #convert payload to dateTime components
    try:
        iDateTime=datetime.strptime(payload['dateTime'],"%d/%m/%Y %H:%M:%S")   #format '12/11/2021 09:15:32'
        logger.debug("Setting inverter time to: "+iDateTime)
        #Set Date and Time on inverter
        #temp= await sdt(iDateTime,readloop)
        reqs=commands.set_system_date_time(iDateTime)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        temp['result']="Setting inverter time was a success"
        updateControlCache("Invertor_Time",iDateTime.strftime("%d-%m-%Y %H:%M:%S.%f"))
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryCalibration(payload,readloop=False):
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
        reqs=commands.set_calibrate_battery_soc(int(val))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if val==0:
            updateControlCache("Battery_Calibration","disable")
        else:
            updateControlCache("Battery_Calibration","enable")
        temp['result']="Setting Battery Calibration "+str(payload['state'])+" was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Calibration failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def switchRate(payload,readloop=False):
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
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Rate failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def rebootAddon():
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
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Failed to reboot GivTCP: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(result)

def getSavedBatteryReservePercentage():
    saved_battery_reserve=4
    if exists(GivLUT.reservepkl):
        with open(GivLUT.reservepkl, 'rb') as inp:
            saved_battery_reserve= pickle.load(inp)
    return saved_battery_reserve

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
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
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
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
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
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
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
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
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
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Limit failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)
'''

if __name__ == '__main__':
    if len(sys.argv)==2:
        globals()[sys.argv[1]]()
    elif len(sys.argv)==3:
        globals()[sys.argv[1]](sys.argv[2])
