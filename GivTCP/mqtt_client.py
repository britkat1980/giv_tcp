import paho.mqtt.client as mqtt
import time, sys, importlib, time
from os.path import exists
from settings import GiV_Settings
import write as wr
import pickle, settings
from GivLUT import GivQueue, GivLUT
from pickletools import read_uint1

sys.path.append(GiV_Settings.default_path)

logger = GivLUT.logger

if GiV_Settings.MQTT_Port=='':
    MQTT_Port=1883
else:
    MQTT_Port=int(GiV_Settings.MQTT_Port)
MQTT_Address=GiV_Settings.MQTT_Address
if GiV_Settings.MQTT_Username=='':
    MQTTCredentials=False
else:
    MQTTCredentials=True
    MQTT_Username=GiV_Settings.MQTT_Username
    MQTT_Password=GiV_Settings.MQTT_Password
if GiV_Settings.MQTT_Topic=='':
    MQTT_Topic='GivEnergy'
else:
    MQTT_Topic=GiV_Settings.MQTT_Topic

#loop till serial number has been found
while not hasattr(GiV_Settings,'serial_number'):
    time.sleep(5)
    #del sys.modules['settings.GiV_Settings']
    importlib.reload(settings)
    from settings import GiV_Settings
    count=+1
    if count==20:
        logger.error("No serial_number found in MQTT queue. MQTT Control not available.")
        break

logger.info("Serial Number retrieved: "+GiV_Settings.serial_number)

def on_message(client, userdata, message):
    payload={}
    logger.info("MQTT Message Recieved: "+str(message.topic)+"= "+str(message.payload.decode("utf-8")))
    writecommand={}
    command=str(message.topic).split("/")[-1]
    if command=="setDischargeRate":
        writecommand['dischargeRate']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.setDischargeRate,writecommand)
    elif command=="setChargeRate":
        writecommand['chargeRate']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.setChargeRate,writecommand)
    elif command=="enableChargeTarget":
        writecommand['state']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.enableChargeTarget,writecommand)
    elif command=="enableChargeSchedule":
        writecommand['state']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.enableChargeSchedule,writecommand)
    elif command=="enableDishargeSchedule":
        writecommand['state']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.enableDischargeSchedule,writecommand)
    elif command=="enableDischarge":
        writecommand['state']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.enableDischarge,writecommand)
    elif command=="setChargeTarget":
        writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.setChargeTarget,writecommand)
    elif command=="setBatteryReserve":
        #writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
        writecommand['reservePercent']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.setBatteryReserve,writecommand)
    elif command=="setBatteryCutoff":
        writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.setBatteryCutoff,writecommand)
    elif command=="setBatteryMode":
        writecommand['mode']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.setBatteryMode,writecommand)
    elif command=="setDateTime":
        writecommand['dateTime']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.setDateTime,writecommand)
    elif command=="setShallowCharge":
        writecommand['val']=str(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.setShallowCharge,writecommand)
    elif command=="setChargeStart1":
        if exists(GivLUT.regcache):
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            multi_output=regCacheStack[4]
            finish=multi_output['Timeslots']['Charge_end_time_slot_1']
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['finish']=finish[:5]
            result=GivQueue.q.enqueue(wr.setChargeSlot1,payload)
    elif command=="setChargeEnd1":
        if exists(GivLUT.regcache):
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            multi_output=regCacheStack[4]
            start=multi_output['Timeslots']['Charge_start_time_slot_1']
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['start']=start[:5]
            result=GivQueue.q.enqueue(wr.setChargeSlot1,payload)
    elif command=="setDischargeStart1":
        if exists(GivLUT.regcache):
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            multi_output=regCacheStack[4]
            finish=multi_output['Timeslots']['Discharge_end_time_slot_1']
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['finish']=finish[:5]
            result=GivQueue.q.enqueue(wr.setDischargeSlot1,payload)
    elif command=="setDischargeEnd1":
        if exists(GivLUT.regcache):
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            multi_output=regCacheStack[4]
            start=multi_output['Timeslots']['Discharge_start_time_slot_1']
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['start']=start[:5]
            result=GivQueue.q.enqueue(wr.setDischargeSlot1,payload)
    elif command=="setDischargeStart2":
        if exists(GivLUT.regcache):
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            multi_output=regCacheStack[4]
            finish=multi_output['Timeslots']['Discharge_end_time_slot_2']
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['finish']=finish[:5]
            result=GivQueue.q.enqueue(wr.setDischargeSlot2,payload)
    elif command=="setDischargeEnd2":
        if exists(GivLUT.regcache):
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            multi_output=regCacheStack[4]
            start=multi_output['Timeslots']['Discharge_start_time_slot_2']
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['start']=start[:5]
            result=GivQueue.q.enqueue(wr.setDischargeSlot2,payload)
#            result=wr.setDischargeSlot2(payload)
    elif command=="tempPauseDischarge":
        writecommand=float(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.tempPauseDischarge,writecommand)
    elif command=="tempPauseCharge":
        writecommand=float(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.tempPauseCharge,writecommand)
    elif command=="forceCharge":
        writecommand=float(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.forceCharge,writecommand)
    elif command=="forceExport":
        writecommand=float(message.payload.decode("utf-8"))
        result=GivQueue.q.enqueue(wr.forceExport,writecommand)
#        result=wr.forceExport(writecommand)
    #Do something with the result??

def on_connect(client, userdata, flags, rc):
    if rc==0:
        client.connected_flag=True #set flag
        logger.info("connected OK Returned code="+str(rc))
        #Subscribe to the control topic for this invertor - relies on serial_number being present
        client.subscribe(MQTT_Topic+"/control/"+GiV_Settings.serial_number+"/#")
        logger.info("Subscribing to "+MQTT_Topic+"/control/"+GiV_Settings.serial_number+"/#")
    else:
        logger.error("Bad connection Returned code= "+str(rc))


client=mqtt.Client("GivEnergy_GivTCP_"+str(GiV_Settings.givtcp_instance)+"_Control")
mqtt.Client.connected_flag=False        			#create flag in class
if MQTTCredentials:
    client.username_pw_set(MQTT_Username,MQTT_Password)
client.on_connect=on_connect     			        #bind call back function
client.on_message=on_message                        #bind call back function
#client.loop_start()

logger.info ("Connecting to broker(sub): "+ MQTT_Address)
client.connect(MQTT_Address,port=MQTT_Port)
client.loop_forever()
