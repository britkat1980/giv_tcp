"""HA_Discovery: """
# version 2022.01.21
import sys
import os
import time
import json
import paho.mqtt.client as paho_mqtt
from socket import gaierror
from settings import GiV_Settings
from entity_lut import Entity_Type
from os.path import exists
from evc import EVCLut, logger

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

    def finditem(obj, key):
        if key in obj: return obj[key]
        for k, v in obj.items():
            if isinstance(v,dict):
                item = HAMQTT.finditem(v, key)
                if item is not None:
                    return item
        return None

    def getinvbatmax():
        regCacheStack = EVCLut.get_regcache()
        if regCacheStack:
            multi_output_old = regCacheStack[-1]
            if 'Invertor_Max_Bat_Rate' in multi_output_old[HAMQTT.finditem(multi_output_old,'Invertor_Serial_Number')]:
                return int(multi_output_old[HAMQTT.finditem(multi_output_old,'Invertor_Serial_Number')]['Invertor_Max_Bat_Rate'])
            else:
                return 5000
        return 5000

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code==0:
            client.connected_flag=True #set flag
            logger.debug("connected OK Returned code="+str(reason_code))
            #client.subscribe(topic)
        else:
            logger.error("Bad connection Returned code= "+str(reason_code))

    def iterate_dict(array,topic):      #Create LUT of topics and datapoints
        MQTT_LUT={}
        if isinstance(array, dict):
            # Create a publish safe version of the output
            for p_load in array:
                output=array[p_load]
                if isinstance(output, dict):
                    MQTT_LUT.update(HAMQTT.iterate_dict(output,topic+"/"+p_load))
                    logger.debug('Prepping '+p_load+" for publishing")
                else:
                    MQTT_LUT[topic+"/"+p_load]=output
        else:
            MQTT_LUT[topic]=array
        return(MQTT_LUT)

    def publish_discovery2(array,SN):   #Recieve multiple payloads with Topics and publish in a single MQTT connection
        try:
            inv_type=HAMQTT.finditem(array,"Invertor_Type")
            if inv_type=="":
                inv_type="GivEnergy"
            rootTopic=str(GiV_Settings.MQTT_Topic+"/"+SN+"/")
            array['Stats/Timeout_Error']=0    # Set this always at start in case it doesn't exist
            publisher=[]
            ### For each topic create a discovery message
            for p_load in array:
                if p_load != "raw":
                    payload=array[p_load]
                    logger.debug('Publishing: '+rootTopic+p_load)
                    output=HAMQTT.iterate_dict(payload,rootTopic+p_load)   #create LUT for MQTT publishing
                    for topic in output:
                        entity_type2= Entity_Type.entity_type[str(topic).split("/")[-1]]
                        #Determine Entitiy type (switch/sensor/number) and publish the right message
                        if entity_type2.devType=="sensor":
                            if "Battery_Details" in topic:
                                publisher.append(["homeassistant/sensor/GivEnergy/"+SN+"_"+str(topic).split("/")[-2]+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN,inv_type)])
                            elif "Inverters" in topic:
                                publisher.append(["homeassistant/sensor/GivEnergy/"+SN+"_"+str(topic).split("/")[-2]+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN,inv_type)])
                            else:
                                publisher.append(["homeassistant/sensor/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN,inv_type)])
                        elif entity_type2.devType=="switch":
                            publisher.append(["homeassistant/switch/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN,inv_type)])
                        elif entity_type2.devType=="number":
                            publisher.append(["homeassistant/number/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN,inv_type)])
                    #    elif entity_type[0]=="binary_sensor":
                    #        client.publish("homeassistant2/binary_sensor/GivEnergy/"+str(topic).split("/")[-1]+"/config",HAMQTT.create_binary_sensor_payload(topic,SN),retain=True)
                        elif entity_type2.devType=="select":
                            publisher.append(["homeassistant/select/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN,inv_type)])
                        elif entity_type2.devType=="button":
                            publisher.append(["homeassistant/button/GivEnergy/"+SN+"_"+str(topic).split("/")[-1]+"/config",HAMQTT.create_device_payload(topic,SN,inv_type)])
            
            # Loop round HA publishing 4 times in case its not all there
            i=0
            complete=False
            CheckDisco.removedisco(SN,publisher)
            time.sleep(3)
            while not complete:
                publisher=HAMQTT.sendDiscoMsg(publisher,SN)     #send to broker and return any missing items after a check
                if len(publisher)<=0:
                    complete = True
                i=i+1
                if i==4:
                    logger.critical("Failed to publish all discovery data in 4 attempts. Check MQTT broker")
                    break
        except gaierror:
            logger.error("Error in to MQTT Address. Check config and update.")
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("Error connecting to MQTT Broker: " + str(e))

    def sendDiscoMsg(array,SN):
        paho_mqtt.Client.connected_flag=False        			#create flag in class
        client=paho_mqtt.Client(paho_mqtt.CallbackAPIVersion.VERSION2, "GivEnergy_GivTCP_senddisco_"+str(GiV_Settings.givtcp_instance))
        client.on_connect=HAMQTT.on_connect     			#bind call back function
        if HAMQTT.MQTTCredentials:
            client.username_pw_set(HAMQTT.MQTT_Username,HAMQTT.MQTT_Password)
        client.host=GiV_Settings.MQTT_Address
        client.port=GiV_Settings.MQTT_Port
        ## set the will message
        client.will_set(GiV_Settings.MQTT_Topic+"/"+SN+"/Stats/status","offline", retain=True)

        client.loop_start()
        logger.debug("Connecting to broker: "+ HAMQTT.MQTT_Address)
        while not client.connected_flag:        			#wait in loop
            logger.debug("In wait loop (sendDiscoMsg)")
            time.sleep(0.2)

        logger.debug("Publishing MQTT: " + HAMQTT.MQTT_Address)

        ##publish the status message
        client.publish(GiV_Settings.MQTT_Topic+"/"+SN+"/Stats/status","online", retain=True)
        i=0
        for pub in array:
            if isinstance(pub[1],(int, str, float, bytearray)):      #Only publish typesafe data
                client.publish(pub[0],pub[1],retain=True)
        client.loop_stop()                      			#Stop loop
        client.disconnect()
        time.sleep(1)
        unpub=CheckDisco.checkdisco(array)  #Check what is in broker vs what was sent and return missing items
        return unpub

    def create_device_payload(topic,SN,inv_type="EVC"):
        tempObj={}
        tempObj['stat_t']=str(topic).replace(" ","_")
        tempObj['avty_t'] = GiV_Settings.MQTT_Topic+"/"+SN+"/Stats/status"
        tempObj["pl_avail"]= "online"
        tempObj["pl_not_avail"]= "offline"
        tempObj['device']={}
        item=str(topic).split("/")[-1]
        GiVTCP_Device=str(topic).split("/")[2]
        device= str(topic).split("/")[3]

        if "Battery_Details" in topic or "Inverters" in topic:
            #tempObj["name"]=GiV_Settings.ha_device_prefix+" "+device.replace("_"," ")+" "+item.replace("_"," ") #Just final bit past the last "/"
            if len(str(topic).split("/"))>5:    #Its a battery
                tempObj["name"]=item.replace("_"," ") #Just final bit past the last "/"
                tempObj['uniq_id']=GiV_Settings.ha_device_prefix+"_"+str(topic).split("/")[4]+"_"+item
                tempObj['object_id']=GiV_Settings.ha_device_prefix+"_"+str(topic).split("/")[4]+"_"+item
                tempObj['device']['identifiers']=GiV_Settings.ha_device_prefix+" "+str(topic).split("/")[4]
                tempObj['device']['name']=GiV_Settings.ha_device_prefix+" "+str(topic).split("/")[4].replace("_"," ")
            else:
                tempObj["name"]=item.replace("_"," ") #Just final bit past the last "/"
                tempObj['uniq_id']=GiV_Settings.ha_device_prefix+"_"+device+"_"+item
                tempObj['object_id']=GiV_Settings.ha_device_prefix+"_"+device+"_"+item
                tempObj['device']['identifiers']=GiV_Settings.ha_device_prefix+" "+device
                tempObj['device']['name']=GiV_Settings.ha_device_prefix+" "+device.replace("_"," ")

            # tempObj['device']['name']=GiV_Settings.ha_device_prefix+" "+GiVTCP_Device.replace("_"," ")
        elif len(SN)>10:    #If EVC and not INV
            tempObj['uniq_id']=GiV_Settings.ha_device_prefix+"_"+SN+"_"+item
            tempObj['object_id']=GiV_Settings.ha_device_prefix+"_"+SN+"_"+item
            tempObj['device']['identifiers']=SN+"_"+GiVTCP_Device
            tempObj['device']['name']="GivEVC"#+str(GiVTCP_Device).replace("_"," ")
            tempObj["name"]=item.replace("_"," ") #Just final bit past the last "/"
        else:
            tempObj['uniq_id']=GiV_Settings.ha_device_prefix+"_"+SN+"_"+item
            tempObj['object_id']=GiV_Settings.ha_device_prefix+"_"+SN+"_"+item
            tempObj['device']['identifiers']=SN+"_"+GiVTCP_Device
            #tempObj['device']['name']=GiV_Settings.ha_device_prefix+" "+SN+" "+str(GiVTCP_Device).replace("_"," ")
            tempObj['device']['name']=GiV_Settings.ha_device_prefix+" "+str(GiVTCP_Device).replace("_"," ")
            tempObj["name"]=item.replace("_"," ") #Just final bit past the last "/"
            #tempObj["name"]=GiV_Settings.ha_device_prefix+" "+item.replace("_"," ") #Just final bit past the last "/"
        tempObj['device']['manufacturer']="GivEnergy"
        if inv_type==None:
            inv_type="EVC"
        tempObj['device']['model']=inv_type

        entity_type2= Entity_Type.entity_type[item]

        if not entity_type2.controlFunc == "":
            tempObj['command_topic']=GiV_Settings.MQTT_Topic+"/control/"+SN+"/"+entity_type2.controlFunc

#set device specific elements here:
        if entity_type2.devType=="sensor":
            tempObj['unit_of_meas']=""
            if entity_type2.sensorClass=="energy":
                tempObj['unit_of_meas']="kWh"
                tempObj['device_class']="Energy"
                if entity_type2.onlyIncrease:        #"soc" in str(topic.split("/")[-1]).lower() or "today" in str(topic.split("/")[-1]).lower():
                    tempObj['state_class']="total_increasing"
                else:
                    tempObj['state_class']="total"
            if entity_type2.sensorClass=="money":
                if "ppkwh" in str(topic).lower() or "rate" in str(topic).lower():
                    tempObj['unit_of_meas']="{GBP}/kWh"
                else:
                    tempObj['unit_of_meas']="{GBP}"
                tempObj['device_class']="Monetary"
                tempObj['icon_template']= "mdi:currency-gbp"
            if entity_type2.sensorClass=="power":
                tempObj['unit_of_meas']="W"
                tempObj['device_class']="Power"
                tempObj['state_class']="measurement"
            if entity_type2.sensorClass=="temperature":
                tempObj['unit_of_meas']="°C"
                tempObj['device_class']="Temperature"
                tempObj['state_class']="measurement"
            if entity_type2.sensorClass=="voltage":
                tempObj['unit_of_meas']="V"
                tempObj['device_class']="Voltage"
                tempObj['state_class']="measurement"
            if entity_type2.sensorClass=="frequency":
                tempObj['unit_of_meas']="Hz"
                tempObj['device_class']="frequency"
                tempObj['state_class']="measurement"
            if entity_type2.sensorClass=="current":
                tempObj['unit_of_meas']="A"
                tempObj['device_class']="Current"
                tempObj['state_class']="measurement"
            if entity_type2.sensorClass=="battery":
                tempObj['unit_of_meas']="%"
                tempObj['device_class']="Battery"
                tempObj['state_class']="measurement"
            if entity_type2.sensorClass=="timestamp":
                del tempObj['unit_of_meas']
                tempObj['device_class']="timestamp"
            if entity_type2.sensorClass=="datetime":
                del tempObj['unit_of_meas']
            if entity_type2.sensorClass=="string":
                del tempObj['unit_of_meas']
        elif entity_type2.devType=="switch":
            tempObj['payload_on']="enable"
            tempObj['payload_off']="disable"
    #    elif EVCLut.entity_type2[item.devType=="binary_sensor":
    #        client.publish("homeassistant/binary_sensor/GivEnergy/"+item+"/config",HAMQTT.create_binary_sensor_payload(topic,SN),retain=True)
        elif entity_type2.devType=="select":
            if "Charging_Mode" in item:
                options= EVCLut.charging_mode
            elif "Charge_Control" in item:
                options= EVCLut.charge_control
            tempObj['options']=options
        elif entity_type2.devType=="number":
            # If its a rate then change to Watts
            item=str(topic).split("/")[-1]
            if "soc" in str(item).lower():
                tempObj['unit_of_meas']="%"
                tempObj['min']=4
                tempObj['max']=100
                tempObj['mode']="slider"
            elif "limit" in str(item).lower():   #if EVC current
                tempObj['unit_of_meas']="A"
                tempObj['min']=6
                tempObj['max']=32
                tempObj['mode']="slider"            
            elif "compensation" in str(item).lower():   #if EMS compensation
                tempObj['unit_of_meas']="W"
                tempObj['min']=-5
                tempObj['max']=5
                tempObj['mode']="slider"
            elif "boost" in str(item).lower():   #if EVC current
                tempObj['unit_of_meas']="W"
                tempObj['min']=0
                tempObj['max']=22000
                tempObj['mode']="slider"
            elif "_cap" in str(item).lower():   #if EVC current
                tempObj['unit_of_meas']="A"
                tempObj['min']=0
                tempObj['max']=100
                tempObj['mode']="slider"
            elif "_num" in str(item).lower():   #if EVC current
                tempObj['min']=0
                tempObj['max']=240
                tempObj['mode']="slider"
            elif "energy" in str(item).lower():
                tempObj['unit_of_meas']="kWh"
                tempObj['min']=0
                tempObj['max']=100
                tempObj['mode']="slider"
            elif "charge_rate_ac" in str(item).lower():
                tempObj['unit_of_meas']="%"
                tempObj['min']=0
                tempObj['max']=100
                tempObj['mode']="slider"
            elif "charge" in str(item).lower():
                tempObj['unit_of_meas']="W"
                tempObj['min']=0
                tempObj['max']=HAMQTT.getinvbatmax()
                tempObj['mode']="slider"
            else:
                tempObj['unit_of_meas']="%"
        elif entity_type2.devType=="button":
            tempObj['device_class']=""
            tempObj['payload_press']="toggle"
        ## Convert this object to json string
        jsonOut=json.dumps(tempObj)
        return jsonOut

class CheckDisco():
    msgs={}
    def on_connect(client, userdata, flags, rc, properties):
        client.subscribe("homeassistant/#")
        client.subscribe("GivEnergy/#")
    
    def on_disconnect(client, userdata, flags, rc, properties):
        #clear cached messages on disconnect
        CheckDisco.msgs={}

    def on_message(client, userdata, msg):
        CheckDisco.msgs[str(msg.topic)]=str(msg.payload)

    def checkdisco(array: str):
        try:
            client = paho_mqtt.Client(paho_mqtt.CallbackAPIVersion.VERSION2,"GivEnergy_GivTCP_checkdisco_"+str(GiV_Settings.givtcp_instance))
            client.on_connect = CheckDisco.on_connect
            client.on_message = CheckDisco.on_message
            #client.on_disconnect = CheckDisco.on_disconnect
            if HAMQTT.MQTTCredentials:
                client.username_pw_set(HAMQTT.MQTT_Username,HAMQTT.MQTT_Password)
            client.connect(GiV_Settings.MQTT_Address, GiV_Settings.MQTT_Port, 60)

            client.loop_start()
            time.sleep(5)
            client.disconnect()
            temp={}
            logger.debug("Sent "+ str(len(array))+" discovery messages")
            logger.debug("Found "+ str(len(CheckDisco.msgs))+" discovery messages")
            unpub=[]
            for m in array:     #check each item that was sent
                if not m[0] in CheckDisco.msgs:    #if its not in what was received
                    unpub.append([m[0],m[1]])      #take the one that was sent but not received and add to unpub
            return unpub
        except gaierror:
            logger.error("Error in to MQTT Address. Check config and update.")
            client.disconnect()
        except:
            e=sys.exc_info()[0].__name__, sys.exc_info()[2].tb_lineno
            logger.error("Error connecting to MQTT Broker: " + str(e))
            client.disconnect()
    
    def removedisco(SN,messages):
        try:
            foundmessages=0
            moremessages=0
            client = paho_mqtt.Client(paho_mqtt.CallbackAPIVersion.VERSION2,"GivEnergy_GivTCP_removedisco_"+str(GiV_Settings.givtcp_instance))
            client.on_connect = CheckDisco.on_connect
            client.on_message = CheckDisco.on_message
            #client.on_disconnect = CheckDisco.on_disconnect
            if HAMQTT.MQTTCredentials:
                client.username_pw_set(HAMQTT.MQTT_Username,HAMQTT.MQTT_Password)
            client.connect(GiV_Settings.MQTT_Address, GiV_Settings.MQTT_Port, 60)

            client.loop_start()

            ## Can we check here to see when num of messages stops increasing?
            loop=1
            count=0
            while True:
                time.sleep(1)
                moremessages=len(CheckDisco.msgs)
                logger.debug("Foundmessages= "+str(foundmessages))
                logger.debug("Moremessages= "+str(moremessages))
                if moremessages == foundmessages:
                    count+=1
                if count==5 or loop==10:
                    break
                loop+=1
                foundmessages=moremessages
            #Loop through all msgs and remove if they are GivTCP ones
            newmsg={}
            for message in messages:
                newmsg[message[0]]=message[1]
            count=0
            for topic in CheckDisco.msgs:
                msg=CheckDisco.msgs[topic]
                if SN in topic or SN in msg: # ("GivEnergy" in msg or GiV_Settings.MQTT_Topic in msg):
                    if exists('/config/GivTCP/.v3upgrade_'+str(GiV_Settings.givtcp_instance)):
                        logger.debug("V3 Upgrade so dropping old Discovery Messages")
                        client.publish(topic,None,0,True)     #delete regardless of if it has changed
                    else:
                        if topic in newmsg:
                            old=newmsg[topic]
                            new=msg[2:-1]     #.split('}')[:0]
                            if not old == new:       #if payload is different delete old one
                                client.publish(topic,None,0,True)
                                count+=1
            logger.debug(str(count)+" discovery messages changed and removed")
            time.sleep(2)
            client.loop_stop()
            client.disconnect()
        except gaierror:
            logger.error("Error in to MQTT Address. Check config and update.")
            client.disconnect()
        except:
            e=sys.exc_info()[0].__name__, sys.exc_info()[2].tb_lineno
            logger.error("Error connecting to MQTT Broker: " + str(sys.exc_info()))
            client.disconnect()