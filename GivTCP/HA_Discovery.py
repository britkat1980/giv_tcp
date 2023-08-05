# version 2022.01.21
import sys, time, json
import paho.mqtt.client as mqtt 
from settings import GiV_Settings
from givenergy_modbus.model.inverter import Model
from mqtt import GivMQTT
from GivLUT import GivLUT
from os.path import exists
import pickle

logger=GivLUT.logger

class HAMQTT():
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
    if GiV_Settings.MQTT_Topic=="":
        GiV_Settings.MQTT_Topic="GivEnergy"

    def getinvbatmax():
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output_old = regCacheStack[4]
            return int(multi_output_old['Invertor_Details']['Invertor_Max_Bat_Rate'])
        return 5000

    def on_connect(client, userdata, flags, rc):
        if rc==0:
            client.connected_flag=True #set flag
            logger.debug("connected OK Returned code="+str(rc))
            #client.subscribe(topic)
        else:
            logger.error("Bad connection Returned code= "+str(rc))
    
    def publish_discovery(array,SN):   #Recieve multiple payloads with Topics and publish in a single MQTT connection
        mqtt.Client.connected_flag=False        			#create flag in class
        client=mqtt.Client("GivEnergy_GivTCP_"+str(GiV_Settings.givtcp_instance))
        rootTopic=str(GiV_Settings.MQTT_Topic+"/"+SN+"/")
        if HAMQTT.MQTTCredentials:
            client.username_pw_set(HAMQTT.MQTT_Username,HAMQTT.MQTT_Password)
        try:
            client.on_connect=HAMQTT.on_connect     			#bind call back function
            client.loop_start()
            logger.debug("Connecting to broker: "+ HAMQTT.MQTT_Address)
            client.connect(HAMQTT.MQTT_Address,port=HAMQTT.MQTT_Port)
            while not client.connected_flag:        			#wait in loop
                logger.debug("In wait loop")
                time.sleep(0.2)

            logger.debug("Publishing MQTT: " + HAMQTT.MQTT_Address)

            ##publish the status message
            client.publish(GiV_Settings.MQTT_Topic+"/"+SN+"/status","online", retain=True)

            ### For each topic create a discovery message
            for p_load in array:
                if p_load != "raw":
                    payload=array[p_load]
                    logger.debug('Publishing: '+rootTopic+p_load)
                    output=GivMQTT.iterate_dict(payload,rootTopic+p_load)   #create LUT for MQTT publishing
                    for topic in output:
                        #Determine Entitiy type (switch/sensor/number) and publish the right message
                        if GivLUT.entity_type[str(topic).split("/")[-1]].devType=="sensor":
                            if "Battery_Details" in topic:
                                client.publish("homeassistant/sensor/GivEnergy/"+str(topic).split("/")[-2]+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN),retain=True)
                            else:
                                client.publish("homeassistant/sensor/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN),retain=True)
                        elif GivLUT.entity_type[str(topic).split("/")[-1]].devType=="switch":
                            client.publish("homeassistant/switch/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN),retain=True)
                        elif GivLUT.entity_type[str(topic).split("/")[-1]].devType=="number":
                            client.publish("homeassistant/number/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN),retain=True)
                    #    elif GivLUT.entity_type[str(topic).split("/")[-1]][0]=="binary_sensor":
                    #        client.publish("homeassistant2/binary_sensor/GivEnergy/"+str(topic).split("/")[-1]+"/config",HAMQTT.create_binary_sensor_payload(topic,SN),retain=True)
                        elif GivLUT.entity_type[str(topic).split("/")[-1]].devType=="select":
                            client.publish("homeassistant/select/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN),retain=True)
                
            client.loop_stop()                      			#Stop loop
            client.disconnect()
            
        except:
            e = sys.exc_info()
            logger.error("Error connecting to MQTT Broker: " + str(e))
    
        return
    

    def create_device_payload(topic,SN):
        tempObj={}
        tempObj['stat_t']=str(topic).replace(" ","_")
        tempObj['avty_t'] = GiV_Settings.MQTT_Topic+"/"+SN+"/status"
        tempObj["pl_avail"]= "online"
        tempObj["pl_not_avail"]= "offline"
        tempObj['device']={}
        
        GiVTCP_Device=str(topic).split("/")[2]
        if "Battery_Details" in topic:
            tempObj["name"]=GiV_Settings.ha_device_prefix+" "+str(topic).split("/")[3].replace("_"," ")+" "+str(topic).split("/")[-1].replace("_"," ") #Just final bit past the last "/"
            tempObj['uniq_id']=GiV_Settings.ha_device_prefix+"_"+str(topic).split("/")[3]+"_"+str(topic).split("/")[-1]
            tempObj['object_id']=GiV_Settings.ha_device_prefix+"_"+str(topic).split("/")[3]+"_"+str(topic).split("/")[-1]
            tempObj['device']['identifiers']=str(topic).split("/")[3]+"_"+GiVTCP_Device
            tempObj['device']['name']=GiV_Settings.ha_device_prefix+" "+str(topic).split("/")[3].replace("_"," ")+" "+GiVTCP_Device.replace("_"," ")
        else:
            tempObj['uniq_id']=GiV_Settings.ha_device_prefix+"_"+SN+"_"+str(topic).split("/")[-1]
            tempObj['object_id']=GiV_Settings.ha_device_prefix+"_"+SN+"_"+str(topic).split("/")[-1]
            tempObj['device']['identifiers']=SN+"_"+GiVTCP_Device
            tempObj['device']['name']=GiV_Settings.ha_device_prefix+" "+SN+" "+str(GiVTCP_Device).replace("_"," ")
            tempObj["name"]=GiV_Settings.ha_device_prefix+" "+str(topic).split("/")[-1].replace("_"," ") #Just final bit past the last "/"
        tempObj['device']['manufacturer']="GivEnergy"

        if not GivLUT.entity_type[str(topic).split("/")[-1]].controlFunc == "":
            tempObj['command_topic']=GiV_Settings.MQTT_Topic+"/control/"+SN+"/"+GivLUT.entity_type[str(topic).split("/")[-1]].controlFunc

#set device specific elements here:
        if GivLUT.entity_type[str(topic).split("/")[-1]].devType=="sensor":
            tempObj['unit_of_meas']=""
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="energy":
                tempObj['unit_of_meas']="kWh"
                tempObj['device_class']="Energy"
                if "soc" in str(topic.split("/")[-2]).lower():
                    tempObj['state_class']="measurement"
                else:
                    tempObj['state_class']="total_increasing"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="money":
                if "ppkwh" in str(topic).lower() or "rate" in str(topic).lower():
                    tempObj['unit_of_meas']="{GBP}/kWh"
                else:
                    tempObj['unit_of_meas']="{GBP}"
                tempObj['device_class']="Monetary"
                tempObj['icon_template']= "mdi:currency-gbp"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="power":
                tempObj['unit_of_meas']="W"
                tempObj['device_class']="Power"
                tempObj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="temperature":
                tempObj['unit_of_meas']="°C"
                tempObj['device_class']="Temperature"
                tempObj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="voltage":
                tempObj['unit_of_meas']="V"
                tempObj['device_class']="Voltage"
                tempObj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="frequency":
                tempObj['unit_of_meas']="Hz"
                tempObj['device_class']="frequency"
                tempObj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="current":
                tempObj['unit_of_meas']="A"
                tempObj['device_class']="Current"
                tempObj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="battery":
                tempObj['unit_of_meas']="%"
                tempObj['device_class']="Battery"
                tempObj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="timestamp":
                del(tempObj['unit_of_meas'])
                tempObj['device_class']="timestamp"
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="datetime":
                del(tempObj['unit_of_meas'])
            if GivLUT.entity_type[str(topic).split("/")[-1]].sensorClass=="string":
                del(tempObj['unit_of_meas'])
        elif GivLUT.entity_type[str(topic).split("/")[-1]].devType=="switch":
            tempObj['payload_on']="enable"
            tempObj['payload_off']="disable"
    #    elif GivLUT.entity_type[str(topic).split("/")[-1].devType=="binary_sensor":
    #        client.publish("homeassistant/binary_sensor/GivEnergy/"+str(topic).split("/")[-1]+"/config",HAMQTT.create_binary_sensor_payload(topic,SN),retain=True)
        elif GivLUT.entity_type[str(topic).split("/")[-1]].devType=="select":
            item=str(topic).split("/")[-1]
            if item == "Battery_pause_mode":
                options=GivLUT.battery_pause_mode
            elif item == "Local_control_mode":
                options=GivLUT.local_control_mode
            elif item == "PV_input_mode":
                options=GivLUT.pv_input_mode
            elif "Mode" in item:
                options=GivLUT.modes
            elif "slot" in item:
                options=GivLUT.time_slots
            elif "Temp" in item:
                options=GivLUT.delay_times
            elif "Force" in item:
                options=GivLUT.delay_times
            elif "Rate" in item:
                options=GivLUT.rates
            tempObj['options']=options
        elif GivLUT.entity_type[str(topic).split("/")[-1]].devType=="number":
            # If its a rate then change to Watts
            if "SOC" in str(topic).lower():
                tempObj['unit_of_meas']="%"
            elif "charge" in str(topic).lower():
                tempObj['unit_of_meas']="W"
                tempObj['min']=0
                tempObj['max']=HAMQTT.getinvbatmax()
                tempObj['mode']="slider"
            else:
                tempObj['unit_of_meas']="%"
        elif GivLUT.entity_type[str(topic).split("/")[-1]].devType=="button":
            tempObj['device_class']="restart"
            tempObj['payload_press']="restart"
        ## Convert this object to json string
        jsonOut=json.dumps(tempObj)
        return(jsonOut)
