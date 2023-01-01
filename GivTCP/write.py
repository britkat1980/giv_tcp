# -*- coding: utf-8 -*-
# version 2022.01.31
import sys
import json
import logging
import datetime
from datetime import datetime, timedelta
from settings import GiV_Settings
import time
from os.path import exists
import pickle,os
from GivLUT import GivLUT, GivQueue
from givenergy_modbus.client import GivEnergyClient

#client= GivEnergyClient(host=GiV_Settings.invertorIP)

logging.getLogger("givenergy_modbus").setLevel(logging.CRITICAL)
client=GivEnergyClient(host=GiV_Settings.invertorIP)

logger = GivLUT.logger


def enableChargeTarget(payload):
    temp={}
    try:
        if payload['state']=="enable":
            client.enable_charge_target()
        elif payload['state']=="disable":
            client.disable_charge_target()
        temp['result']="Setting Charge Target was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def enableChargeSchedule(payload):
    temp={}
    try:
        if payload['state']=="enable":
            client.enable_charge()
        elif payload['state']=="disable":
            client.disable_charge()
        temp['result']="Setting Charge Enable was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Charge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def enableDischargeSchedule(payload):
    temp={}
    try:
        if payload['state']=="enable":
            client.enable_discharge()
        elif payload['state']=="disable":
            client.disable_discharge()
        temp['result']="Setting Charge Enable was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Charge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setShallowCharge(payload):
    temp={}
    try:
        client.set_shallow_charge(int(payload['val']))
        temp['result']="Setting Charge Enable was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Charge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def enableDischarge(payload):
    temp={}
    saved_battery_reserve = getSavedBatteryReservePercentage()
    try:
        if payload['state']=="enable":
            client.set_shallow_charge(saved_battery_reserve)
        elif payload['state']=="disable":
            client.set_shallow_charge(100)
        temp['result']="Setting Discharge Enable was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Discharge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeTarget(payload):
    logger.critical("Setting target SOC to: "+str(payload['chargeToPercent']))
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    target=int(payload['chargeToPercent'])
    try:
        result=client.enable_charge_target(target)
        temp['result']="Setting Charge Target was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setBatteryReserve(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    target=int(payload['reservePercent'])
    #Only allow minimum of 4%
    if target<4: target=4
    logger.info ("Setting battery reserve target to: " + str(target))
    try:
        #client.set_battery_power_reserve(target)
        client.set_shallow_charge(target)
        temp['result']="Setting Battery Reserve was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Battery Reserve failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setBatteryCutoff(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    target=int(payload['dischargeToPercent'])
    #Only allow minimum of 4%
    if target<4: target=4
    logger.info ("Setting battery cutoff target to: " + str(target))
    try:
        client.set_battery_power_reserve(target)
        temp['result']="Setting Battery Cutoff was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Battery Cutoff failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeRate(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    #Only allow max of 100% and if not 100% the scale to a third to get register value
    if int(payload['chargeRate'])>=100:
        target=50
    else:
        target=int(int(payload['chargeRate'])/3)
    logger.info ("Setting battery charge rate to: " + str(target))
    try:
        client.set_battery_charge_limit(target)
        temp['result']="Setting Charge Rate was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Charge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)


def setDischargeRate(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    #Only allow max of 100% and if not 100% the scale to a third to get register value
    if int(payload['dischargeRate'])>=100:
        target=50
    else:
        target=int(int(payload['dischargeRate'])/3)
    logger.info ("Setting battery discharge rate to: " + str(target))
    try:
        client.set_battery_discharge_limit(target)
        temp['result']="Setting Discharge Rate was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Discharge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)


def setChargeSlot1(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    if 'chargeToPercent' in payload.keys():
        targetresult=setChargeTarget(payload)
    try:
        client.set_charge_slot_1((datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Charge Slot 1 was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Charge Slot 1 failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeSlot2(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    if 'chargeToPercent' in payload.keys():
        targetresult=setChargeTarget(payload)
    try:
        client.set_charge_slot_2((datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Charge Slot 2 was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Charge Slot 2 failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDischargeSlot1(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    if 'dischargeToPercent' in payload.keys():
        targetresult=setBatteryReserve(payload)
        time.sleep(1)
    try:
        strt=datetime.strptime(payload['start'],"%H:%M")
        fnsh=datetime.strptime(payload['finish'],"%H:%M")
        client.set_discharge_slot_1((strt,fnsh))
        temp['result']="Setting Discharge Slot 1 was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Discharge Slot 1 failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDischargeSlot2(payload):
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    if 'dischargeToPercent' in payload.keys():
        targetresult=setBatteryReserve(payload)
        time.sleep(1)
    try:
        client.set_discharge_slot_2((datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Discharge Slot 2 was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Discharge Slot 2 failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def FEResume(revert):
    logger.critical("Reverting Force Export")
    payload={}
    logger.info("Reverting Force Export")
    logger.info("Reverting Discharge Rate")
    payload['dischargeRate']=revert["dischargeRate"]
    result=setDischargeRate(payload)
    logger.info("DischargeRate result is:" + str(result))
    time.sleep(1)
    payload={}
    payload['start']=revert["start_time"]
    payload['finish']=revert["end_time"]
    payload['dischargeToPercent']=revert["dischargeToPercent"]
    result=setDischargeSlot1(payload)
    logger.info("Timeslot result is:" + str(result))
    time.sleep(1)
    payload={}
    payload["mode"]=revert["mode"]
    logger.info("Reverting Mode")
    result=setBatteryMode(payload)
    logger.info("Mode result is:" + str(result))

    logger.critical("Settings restored to:")
    logger.critical("dischargeRate:"+str(revert["dischargeRate"]))
    logger.critical("mode:"+str(revert["mode"]))
    os.remove(".FERunning")

def forceExport(exportTime):
    temp={}
    logger.critical("Forcing Export for "+str(exportTime)+" minutes")
    try:
        exportTime=int(exportTime)
        result={}
        revert={}
        open(".FERunning", 'w').close()
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            revert["dischargeRate"]=regCacheStack[4]["Control"]["Battery_Discharge_Rate"]
            revert["start_time"]=regCacheStack[4]["Timeslots"]["Discharge_start_time_slot_1"][:5]
            revert["end_time"]=regCacheStack[4]["Timeslots"]["Discharge_end_time_slot_1"][:5]
            revert["dischargeToPercent"]=regCacheStack[4]["Control"]["Battery_Power_Reserve"]
            revert["mode"]=regCacheStack[4]["Control"]["Mode"]

        #set slot2 to calc times and keep slot 1 as is
        slot1=(datetime.strptime(regCacheStack[4]["Timeslots"]["Discharge_start_time_slot_1"][:5],"%H:%M"),datetime.strptime(regCacheStack[4]["Timeslots"]["Discharge_end_time_slot_1"][:5],"%H:%M"))
        slot2=(datetime.now(),datetime.now()+timedelta(minutes=exportTime))
        logger.info("Setting export slot to: "+ slot2[0].strftime("%H:%M")+" - "+slot2[1].strftime("%H:%M"))
        result=client.set_mode_storage(slot1,slot2,export=True)
        logger.info("Mode result is:" + str(result))

        time.sleep(1)

        payload={}
        payload['dischargeRate']=100
        result=setDischargeRate(payload)
        logger.info("DischargeRate result is:" + str(result))

        if "success" in result:
            GivQueue.q.enqueue_in(timedelta(minutes=exportTime),FEResume,revert)
            temp['result']="Export successfully forced "+str(exportTime)+" minutes"
        else:
            temp['result']="Force Export failed"
    except:
        e = sys.exc_info()
        temp['result']="Force Export failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def FCResume(revert):
    logger.critical("Reverting Force charge")
    payload={}
    payload['chargeRate']=revert["chargeRate"]
    result=setChargeRate(payload)
    time.sleep(1)
    payload={}
    payload['state']=revert["chargeScheduleEnable"]
    result=enableChargeSchedule(payload)
    time.sleep(1)
    payload={}
    payload['start']=revert["start_time"]
    payload['finish']=revert["end_time"]
    payload['chargeToPercent']=revert["targetSOC"]
    result=setChargeSlot1(payload)

    logger.critical("Charging Settings restored to:")
    logger.critical("chargeRate:"+str(revert["chargeRate"]))
    logger.critical("Discharge Schedule:"+str(revert["chargeScheduleEnable"]))
    logger.critical("Start:"+str(payload["start"]))
    logger.critical("finish:"+str(payload["finish"]))
    logger.critical("Target SOC:"+str(payload["chargeToPercent"]))
    os.remove(".FCRunning")

def forceCharge(chargeTime):
    temp={}
    logger.critical("Forcing Charge for "+str(chargeTime)+" minutes")
    try:
        chargeTime=int(chargeTime)
        payload={}
        result={}
        revert={}
        open(".FCRunning", 'w').close()
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            revert["start_time"]=regCacheStack[4]["Timeslots"]["Charge_start_time_slot_1"][:5]
            revert["end_time"]=regCacheStack[4]["Timeslots"]["Charge_end_time_slot_1"][:5]
            revert["chargeRate"]=regCacheStack[4]["Control"]["Battery_Charge_Rate"]
            revert["targetSOC"]=regCacheStack[4]["Control"]["Target_SOC"]
            revert["chargeScheduleEnable"]=regCacheStack[4]["Control"]["Enable_Charge_Schedule"]

        payload['chargeRate']=100
        result=setChargeRate(payload)

        payload={}
        payload['state']="enable"
        result=enableChargeSchedule(payload)

        payload={}
        payload['start']=GivLUT.getTime(datetime.now())
        payload['finish']=GivLUT.getTime(datetime.now()+timedelta(minutes=chargeTime))
        payload['chargeToPercent']=100
        result=setChargeSlot1(payload)

        if "success" in result:
            GivQueue.q.enqueue_in(timedelta(minutes=chargeTime),FCResume,revert)
            temp['result']="Charge successfully forced "+str(chargeTime)+" minutes"
        else:
            temp['result']="Force charge failed"
    except:
        e = sys.exc_info()
        temp['result']="Force charge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def tmpPDResume(payload):
    result=setDischargeRate(payload)
    logger.info("Discharge Rate restored to: "+str(payload["dischargeRate"]))
    if exists(".tpdRunning"): os.remove(".tpdRunning")

def tempPauseDischarge(pauseTime):
    temp={}
    try:
        pauseTime=int(pauseTime)
        payload={}
        result={}
        payload['dischargeRate']=0
        result=setDischargeRate(payload)
        logger.critical("Pausing Discharge for "+str(pauseTime)+" minutes")
        #Update read data via pickle
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            revertRate=regCacheStack[4]["Control"]["Battery_Discharge_Rate"]
        open(".tpdRunning","w").close()
        if "success" in result:
            payload['dischargeRate']=revertRate
            delay=float(pauseTime*60)
#            Th = threading.Timer(delay,tmpPDResume,args=[payload])        ########## Needs helper function to revert rate, log and update the device status
#            Th.start()
            GivQueue.q.enqueue_in(timedelta(delay),tmpPDResume,payload)
            temp['result']="Discharge paused for "+str(delay)+" seconds"
        else:
            temp['result']="Pausing Discharge failed"
    except:
        e = sys.exc_info()
        temp['result']="Pausing Discharge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def tmpPCResume(payload):
    result=setChargeRate(payload)
    logger.info("Charge Rate restored to: "+str(payload["chargeRate"]))
    if exists(".tpcRunning"): os.remove(".tpcRunning")

def tempPauseCharge(pauseTime):
    temp={}
    try:
        payload={}
        result={}
        payload['chargeRate']=0
        result=setChargeRate(payload)
        logger.info(result)
        #Update read data via pickle
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
        revertRate=regCacheStack[4]["Control"]["Battery_Charge_Rate"]
        open(".tpcRunning","w").close()
        if "success" in result:
            payload['chargeRate']=revertRate
            delay=float(pauseTime*60)
#            Th = threading.Timer(delay,tmpPCResume,args=[payload])
#            Th.start()
            GivQueue.q.enqueue_in(timedelta(delay),tmpPCResume,payload)
            temp['result']="Charge paused for "+str(delay)+" seconds"
        else:
            temp['result']="Pausing Charge failed: "
        logger.info("Result is: "+temp['result'])
    except:
        e = sys.exc_info()
        temp['result']="Pausing Charge failed: " + str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

def setBatteryMode(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        if payload['mode']=="Eco":
            client.set_mode_dynamic()
            time.sleep(1)
            client.set_shallow_charge(getSavedBatteryReservePercentage())
        elif payload['mode']=="Eco (Paused)":
            client.set_mode_dynamic()
            time.sleep(1)
            client.set_shallow_charge(100)
        elif payload['mode']=="Timed Demand":
            client.set_mode_storage()
            time.sleep(1)
            client.enable_discharge()
        elif payload['mode']=="Timed Export":
            client.set_mode_storage(export=True)
            time.sleep(1)
            client.enable_discharge()
        else:
            logger.info ("Invalid Mode requested: "+ payload['mode'])
            temp['result']="Invalid Mode requested"
            return json.dumps(temp)
        temp['result']="Setting Battery Mode was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Battery Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDateTime(payload):
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    #convert payload to dateTime components
    try:
        iDateTime=datetime.strptime(payload['dateTime'],"%d/%m/%Y %H:%M:%S")   #format '12/11/2021 09:15:32'
        #Set Date and Time on Invertor
        client.set_datetime(iDateTime)
        temp['result']="Invertor time setting was a success"

    except:
        e = sys.exc_info()
        temp['result']="Setting Battery Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def getSavedBatteryReservePercentage():
    saved_battery_reserve=4
    if exists(GivLUT.reservepkl):
        with open(GivLUT.reservepkl, 'rb') as inp:
            saved_battery_reserve= pickle.load(inp)
    return saved_battery_reserve



if __name__ == '__main__':
    if len(sys.argv)==2:
        globals()[sys.argv[1]]()
    elif len(sys.argv)==3:
        globals()[sys.argv[1]](sys.argv[2])
