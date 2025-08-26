# version 2022.01.21
import paho.mqtt.client as mqtt
import time
from os.path import exists, basename
import pickle
import json
import write as wr
from GivLUT import GivLUT
from settings import GiV_Settings
import sys

logger = GivLUT.logger

with open("/config/GivTCP/allsettings.json", "r") as inp:
    setts=json.load(inp)
if setts["evc_enable"]==True:
    import evc

#connected_flag=False     
_mqttclient=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "GivEnergy_GivTCP_"+str(GiV_Settings.givtcp_instance))
_mqttclient.connected_flag=False

class GivMQTT():
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "GivEnergy_GivTCP_"+str(GiV_Settings.givtcp_instance))

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
    if GiV_Settings.MQTT_Retain:
        MQTT_Retain=True
    else:
        MQTT_Retain=False
    if GiV_Settings.MQTT_Topic=='':
        MQTT_Topic='GivEnergy'
    else:
        MQTT_Topic=GiV_Settings.MQTT_Topic

    def get_connection():
        try:
            global _mqttclient
            if not _mqttclient.connected_flag:
                logger.debug("MQTT Connection appears closed, re-opening")
                if GivMQTT.MQTTCredentials:
                    _mqttclient.username_pw_set(GivMQTT.MQTT_Username,GivMQTT.MQTT_Password)
                _mqttclient.on_connect=GivMQTT.on_connect     			#bind call back function
                _mqttclient.on_disconnect=GivMQTT.on_disconnect     	   #bind call back function
                _mqttclient.on_message=GivMQTT.on_message               #bind call back function
                logger.debug("Opening MQTT Connection to "+str(GivMQTT.MQTT_Address))
                _mqttclient.connect(GivMQTT.MQTT_Address,port=GivMQTT.MQTT_Port)
                _mqttclient.loop_start()
            return _mqttclient
        except:
            e=sys.exc_info()[0].__name__, basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("Error getting connection to MQTT Broker: " + str(e))

    def isfloat(num):
        try:
            float(num)
            return True
        except ValueError:
            return False

    def on_disconnect(_client, userdata, flags, reason_code, properties):
        _client.connected_flag=False #set flag
        _client.loop_stop()
        logger.debug("MQTT connection disconnected")

    def on_connect(_client, userdata, flags, reason_code, properties):
        if reason_code==0:
            _client.connected_flag=True #set flag
            logger.debug("connected OK Returned code="+str(reason_code))
            _client.subscribe(GivMQTT.MQTT_Topic+"/control/"+GiV_Settings.serial_number+"/#")
            logger.debug("Subscribing to "+GivMQTT.MQTT_Topic+"/control/"+GiV_Settings.serial_number+"/#")
        else:
            logger.error("Bad connection Returned code= "+str(reason_code))

    def single_MQTT_publish(Topic,value):   #Recieve multiple payloads with Topics and publish in a single MQTT connection
        client=GivMQTT.get_connection()
        try:
            while not _mqttclient.connected_flag:        			#wait in loop
                #GivMQTT.connect()
                logger.debug ("In wait loop (single_MQTT_publish)")
                time.sleep(0.2)
            client.publish(Topic,value)
        except:
            e=sys.exc_info()[0].__name__, basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("Error connecting to MQTT Broker: " + str(e))
            GivMQTT.client.disconnect()
#            GivMQTT.client.loop_stop()                      			    #Stop loop

    def multi_MQTT_publish(rootTopic,array):                    #Recieve multiple payloads with Topics and publish in a single MQTT connection
        client=GivMQTT.get_connection()
        try:
            while not _mqttclient.connected_flag:        			#wait in loop
                logger.debug ("In wait loop (multi_MQTT_publish)")
                time.sleep(0.2)
            for p_load in array:
                payload=array[p_load]
                logger.debug('Publishing: '+rootTopic+p_load)
                output=GivMQTT.iterate_dict(payload,rootTopic+p_load)   #create LUT for MQTT publishing
                for value in output:
                    if isinstance(output[value],(int, str, float, bytearray)):      #Only publish typesafe data
                        client.publish(value,output[value], retain=GivMQTT.MQTT_Retain)
        except:
            e=sys.exc_info()[0].__name__, basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("Error connecting to MQTT Broker: " + str(e))
            client.disconnect()
            client.loop_stop()                      			    #Stop loop

    def iterate_dict(array,topic):      #Create LUT of topics and datapoints
        MQTT_LUT={}
        if isinstance(array, dict):
            # Create a publish safe version of the output
            for p_load in array:
                output=array[p_load]
                if isinstance(output, dict):
                    MQTT_LUT.update(GivMQTT.iterate_dict(output,topic+"/"+p_load))
                    logger.debug('Prepping '+p_load+" for publishing")
                else:
                    MQTT_LUT[topic+"/"+p_load]=output
        else:
            MQTT_LUT[topic]=array
        return(MQTT_LUT)
    
    def on_message(client, userdata, message):
        payload={}
        logger.debug("MQTT Message Recieved: "+str(message.topic)+"= "+str(message.payload.decode("utf-8")))
        payload={}
        try:
            command=str(message.topic).split("/")[-1]
            if command=="setDischargeRate":
                payload['dischargeRate']=str(message.payload.decode("utf-8"))
                #wr.setDischargeRate(payload)
                requestcommand(command,payload)
            elif command=="testCommand":
                payload['testdata']="test"
                requestcommand(command,payload)
            elif command=="setChargeRate":
                payload['chargeRate']=str(message.payload.decode("utf-8"))
                #wr.setChargeRate(payload)
                requestcommand(command,payload)
            elif command=="setDischargeRateAC":
                payload['dischargeRate']=str(message.payload.decode("utf-8"))
                #wr.setDischargeRateAC(payload)
                requestcommand(command,payload)
            elif command=="enableRTC":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.setChargeRateAC(payload)
                requestcommand(command,payload)
            elif command=="setChargeRateAC":
                payload['chargeRate']=str(message.payload.decode("utf-8"))
                #wr.setChargeRateAC(payload)
                requestcommand(command,payload)
            elif command=="setEmsPlant":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableChargeSchedule(payload)
                requestcommand(command,payload)
            elif command=="syncDateTime":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableChargeSchedule(payload)
                requestcommand(command,payload)
            elif command=="setForceCharge":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableChargeSchedule(payload)
                requestcommand(command,payload)
            elif command=="setForceDischarge":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableChargeSchedule(payload)
                requestcommand(command,payload)
            elif command=="setACCharge":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableChargeSchedule(payload)
                requestcommand(command,payload)
            elif command=="rebootInverter":
                #wr.rebootinverter()
                requestcommand(command,payload)
            elif command=="rebootAddon":
                #wr.rebootAddon()
                requestcommand(command,payload)
            elif command=="setActivePowerRate":
                payload['activePowerRate']=str(message.payload.decode("utf-8"))
                #wr.setActivePowerRate(payload)
                requestcommand(command,payload)
            elif command=="enableChargeTarget":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableChargeTarget(payload)
                requestcommand(command,payload)
            elif command=="enableChargeSchedule":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableChargeSchedule(payload)
                requestcommand(command,payload)
            elif command=="enableDischargeSchedule":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableDischargeSchedule(payload)
                requestcommand(command,payload)
            elif command=="setEcoMode":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.setEcoMode(payload)
                requestcommand(command,payload)
            elif command=="setBatteryPauseMode":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.setBatteryPauseMode(payload)
                requestcommand(command,payload)
            elif command=="setLocalControlMode":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.setLocalControlMode(payload)
                requestcommand(command,payload)
            elif command=="setPVInputMode":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.setPVInputMode(payload)
                requestcommand(command,payload)
            elif command=="setCarChargeBoost":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.setCarChargeBoost(payload)
                requestcommand(command,payload)
            elif command=="setBatteryCalibration":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.setBatteryCalibration(payload)
                requestcommand(command,payload)
            elif command=="setExportLimit":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.setExportLimit(payload)
                requestcommand(command,payload)
            elif command=="enableDischarge":
                payload['state']=str(message.payload.decode("utf-8"))
                #wr.enableDischarge(payload)
                requestcommand(command,payload)
            elif command=="setChargeTarget":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                ##wr.setChargeTarget(payload)
                requestcommand(command,payload)
            elif command=="setChargeTarget1":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=1
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget2":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=2
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget3":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=3
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget4":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=4
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget5":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=5
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget6":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=6
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget7":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=7
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget8":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=8
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget9":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=9
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setChargeTarget10":
                payload['chargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=10
                #wr.setChargeTarget2(payload)
                requestcommand("setChargeTarget2",payload)
            elif command=="setBatteryReserve":
                payload['reservePercent']=str(message.payload.decode("utf-8"))
                #wr.setBatteryReserve(payload)
                requestcommand(command,payload)
            elif command=="setBatteryCutoff":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                #wr.setBatteryCutoff(payload)
                requestcommand(command,payload)
            elif command=="setBatteryMode":
                payload['mode']=str(message.payload.decode("utf-8"))
                #wr.setBatteryMode(payload)
                requestcommand(command,payload)
            elif command=="setDateTime":
                payload['dateTime']=str(message.payload.decode("utf-8"))
                #wr.setDateTime(payload)
                requestcommand(command,payload)
            elif command=="setChargeStart1":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd1":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart2":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd2":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart3":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd3":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart4":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=4
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd4":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=4
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart5":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=5
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd5":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=5
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart6":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=6
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd6":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=6
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart7":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=7
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd7":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=7
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart8":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=8
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd8":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=8
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart9":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=9
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd9":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=9
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setChargeStart10":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=10
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setChargeEnd10":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=10
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setEMSChargeTarget1":
                payload['chargeToPercent'] = str(message.payload.decode("utf-8"))
                payload['slot'] = 1
                payload['EMS'] = True
                requestcommand("setChargeTarget2", payload)
            elif command=="setEMSChargeTarget2":
                payload['chargeToPercent'] = str(message.payload.decode("utf-8"))
                payload['slot'] = 2
                payload['EMS'] = True
                requestcommand("setChargeTarget2", payload)
            elif command=="setEMSChargeTarget3":
                payload['chargeToPercent'] = str(message.payload.decode("utf-8"))
                payload['slot'] = 3
                payload['EMS'] = True
                requestcommand("setChargeTarget2", payload)
            elif command=="setEMSChargeStart1":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
                payload['EMS']=True
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setEMSChargeEnd1":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
                payload['EMS']=True
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setEMSChargeStart2":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
                payload['EMS']=True
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setEMSChargeEnd2":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
                payload['EMS']=True
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setEMSChargeStart3":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
                payload['EMS']=True
                #wr.setChargeSlotStart(payload)
                requestcommand("setChargeSlotStart",payload)
            elif command=="setEMSChargeEnd3":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
                payload['EMS']=True
                #wr.setChargeSlotEnd(payload)
                requestcommand("setChargeSlotEnd",payload)
            elif command=="setDischargeStart1":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd1":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart2":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd2":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart3":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd3":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart4":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=4
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd4":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=4
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart5":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=5
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd5":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=5
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart6":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=6
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd6":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=6
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart7":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=7
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd7":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=7
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart8":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=8
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd8":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=8
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart9":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=9
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd9":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=9
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setDischargeStart10":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=10
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setDischargeEnd10":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=10
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setEMSDischargeStart1":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
                payload['EMS']=True
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setEMSDischargeEnd1":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
                payload['EMS']=True
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setEMSDischargeStart2":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
                payload['EMS']=True
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setEMSDischargeEnd2":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
                payload['EMS']=True
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setEMSDischargeStart3":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
                payload['EMS']=True
                #wr.setDischargeSlotStart(payload)
                requestcommand("setDischargeSlotStart",payload)
            elif command=="setEMSDischargeEnd3":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
                payload['EMS']=True
                #wr.setDischargeSlotEnd(payload)
                requestcommand("setDischargeSlotEnd",payload)
            elif command=="setExportStart1":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
            #wr.setExportSlotStart(payload)
                requestcommand("setExportSlotStart",payload)
            elif command=="setExportEnd1":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=1
            #wr.setExportSlotEnd(payload)
                requestcommand("setExportSlotEnd",payload)
            elif command=="setExportStart2":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
            #wr.setExportSlotStart(payload)
                requestcommand("setExportSlotStart",payload)
            elif command=="setExportEnd2":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=2
            #wr.setExportSlotEnd(payload)
                requestcommand("setExportSlotEnd",payload)
            elif command=="setExportStart3":
                payload['start']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
            #wr.setExportSlotStart(payload)
                requestcommand("setExportSlotStart",payload)
            elif command=="setExportEnd3":
                payload['finish']=message.payload.decode("utf-8")[:5]
                payload['slot']=3
            #wr.setExportSlotEnd(payload)
                requestcommand("setExportSlotEnd",payload)
            elif command=="setExportTarget1":
                payload['exportToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=1
            #wr.setExportTarget(payload)
                requestcommand("setExportTarget",payload)
            elif command=="setExportTarget2":
                payload['exportToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=2
            #wr.setExportTarget(payload)
                requestcommand("setExportTarget",payload)
            elif command=="setExportTarget3":
                payload['exportToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=3
            #wr.setExportTarget(payload)
                requestcommand("setExportTarget",payload)
            elif command=="setDischargeTarget1":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=1
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget2":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=2
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget3":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=3
            #wr.setExportTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget4":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=4
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget5":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=5
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget6":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=6
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget7":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=7
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget8":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=8
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget9":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=9
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setDischargeTarget10":
                payload['dischargeToPercent']=str(message.payload.decode("utf-8"))
                payload['slot']=10
            #wr.setDischargeTarget(payload)
                requestcommand("setDischargeTarget",payload)
            elif command=="setPauseStart":
                payload['start']=message.payload.decode("utf-8")[:5]
            #wr.setPauseStart(payload)
                requestcommand(command,payload)
            elif command=="setPauseEnd":
                payload['finish']=message.payload.decode("utf-8")[:5]
            #wr.setPauseEnd(payload)
                requestcommand(command,payload)
            elif command=="tempPauseDischarge":
                if message.payload.decode("utf-8") == "Cancel" or message.payload.decode("utf-8") == "Normal" or float(message.payload.decode("utf-8"))==0:
                    # Get the Job ID from the touchfile
                    if exists(".tpdRunning_"+str(GiV_Settings.givtcp_instance)):
                        jobid= str(open(".tpdRunning_"+str(GiV_Settings.givtcp_instance),"r").readline().strip('\n'))
                        logger.debug("Retrieved jobID to cancel Temp Pause Discharge: "+ str(jobid))
                        result=wr.cancelJob(jobid)
                    else:
                        logger.error("Temp Pause Charge is not currently running")
                elif isfloat(message.payload.decode("utf-8")):
                    duration=float(message.payload.decode("utf-8"))
                #wr.tempPauseDischarge(payload)
                    requestcommand(command,duration)
            elif command=="tempPauseCharge":
                if message.payload.decode("utf-8") == "Cancel" or message.payload.decode("utf-8") == "Normal" or float(message.payload.decode("utf-8"))==0:
                    # Get the Job ID from the touchfile
                    if exists(".tpcRunning_"+str(GiV_Settings.givtcp_instance)):
                        jobid= str(open(".tpcRunning_"+str(GiV_Settings.givtcp_instance),"r").readline().strip('\n'))
                        logger.debug("Retrieved jobID to cancel Temp Pause Charge: "+ str(jobid))
                        result=wr.cancelJob(jobid)
                    else:
                        logger.error("Temp Pause Charge is not currently running")
                elif isfloat(message.payload.decode("utf-8")):
                    duration=float(message.payload.decode("utf-8"))
                #wr.tempPauseCharge(payload)
                    requestcommand(command,duration)
            elif command=="forceCharge":
                if message.payload.decode("utf-8") == "Cancel" or message.payload.decode("utf-8") == "Normal" or float(message.payload.decode("utf-8"))==0:
                    # Get the Job ID from the touchfile
                    if exists(".FCRunning"+str(GiV_Settings.givtcp_instance)):
                        jobid= str(open(".FCRunning"+str(GiV_Settings.givtcp_instance),"r").readline().strip('\n'))
                        logger.debug("Retrieved jobID to cancel Force Charge: "+ str(jobid))
                        requestcommand("cancelJob",jobid)
                    else:
                        logger.error("Force Charge is not currently running")
                elif isfloat(message.payload.decode("utf-8")):
                    duration=float(message.payload.decode("utf-8"))
                #wr.forceCharge(payload)
                    requestcommand(command,duration)
            elif command=="forceExport":
                if message.payload.decode("utf-8") == "Cancel" or message.payload.decode("utf-8") == "Normal" or float(message.payload.decode("utf-8"))==0:
                    # Get the Job ID from the touchfile
                    if exists(".FERunning"+str(GiV_Settings.givtcp_instance)):
                        jobid= str(open(".FERunning"+str(GiV_Settings.givtcp_instance),"r").readline().strip('\n'))
                        logger.debug("Retrieved jobID to cancel Force Export: "+ str(jobid))
                        requestcommand("cancelJob",jobid)
                    else:
                        logger.error("Force Export is not currently running")
                elif isfloat(message.payload.decode("utf-8")):
                    duration=float(message.payload.decode("utf-8"))
                #wr.forceExport(payload)
                    requestcommand(command,duration)
            elif command=="switchRate":
                payload=message.payload.decode("utf-8")
            #wr.switchRate(payload)
                requestcommand(command,payload)
            elif command=="chargeMode":
                payload=message.payload.decode("utf-8")
                evc.setChargeMode(payload)
                requestcommand("setChargeMode",payload)
            elif command=="controlCharge":
                payload=message.payload.decode("utf-8")
                evc.setChargeControl(payload)
                requestcommand("setChargeControl",payload)
        except:
            e=sys.exc_info()[0].__name__, basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("MQTT.OnMessage Exception: "+str(e))
            return
    
def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False

def requestcommand(command,payload):
    requests=[]
    logger.debug("Requesting Control Action: "+str(command)+" - "+str(payload))
    if exists(GivLUT.writerequests):
        with open(GivLUT.writerequests,'rb') as inp:
            requests=pickle.load(inp)
    requests.append([command,payload,False])
    with open(GivLUT.writerequests,'wb') as outp:
        pickle.dump(requests, outp, pickle.HIGHEST_PROTOCOL)