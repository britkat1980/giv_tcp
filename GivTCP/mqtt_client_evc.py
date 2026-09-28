import paho.mqtt.client as mqtt
import time, sys, importlib, time
from settings import GiV_Settings
import evc as evc
import settings
from GivLUT import GivLUT

sys.path.append(GiV_Settings.default_path)

logger = GivLUT.logger

def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False

def on_message(client, userdata, message):
    payload={}
    logger.debug("MQTT Message Recieved: "+str(message.topic)+"= "+str(message.payload.decode("utf-8")))
    writecommand={}
    try:
        command=str(message.topic).split("/")[-1]
        if command=="chargeMode":
            writecommand=message.payload.decode("utf-8")
            evc.setChargeMode(writecommand)
        elif command=="controlCharge":
            writecommand=message.payload.decode("utf-8")
            evc.setChargeControl(writecommand)
        elif command=="setCurrentLimit":
            writecommand=message.payload.decode("utf-8")
            evc.setCurrentLimit(int(writecommand))
        elif command=="setImportCap":
            writecommand=message.payload.decode("utf-8")
            evc.setImportCap(writecommand)
        elif command=="setChargingMode":
            writecommand=message.payload.decode("utf-8")
            evc.setChargingMode(writecommand)
        elif command=="setMaxSessionEnergy":
            writecommand=message.payload.decode("utf-8")
            evc.setMaxSessionEnergy(int(writecommand))
        elif command=="setSystemTime":
            writecommand=message.payload.decode("utf-8")
            evc.setDateTime(writecommand)
    except:
        e = sys.exc_info()
        logger.error("MQTT.OnMessage Exception: "+str(e))
        return
    
    #Do something with the result??

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code==0:
        client.connected_flag=True #set flag
        logger.debug("connected OK Returned code="+str(reason_code))
        #Subscribe to the control topic for this inverter - relies on serial_number being present
        client.subscribe(MQTT_Topic+"/control/"+GiV_Settings.serial_number_evc+"/#")
        logger.debug("Subscribing to "+MQTT_Topic+"/control/"+GiV_Settings.serial_number_evc+"/#")
    else:
        logger.error("Bad connection Returned code= "+str(reason_code))

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

logger.critical("Connecting to MQTT broker for EVC control- "+str(GiV_Settings.MQTT_Address))
#loop till serial number has been found
count=0          # 09-July-2023  set start point

while not hasattr(GiV_Settings,'serial_number_evc'):
    time.sleep(5)
    #del sys.modules['settings.GiV_Settings']
    importlib.reload(settings)
    from settings import GiV_Settings
    count=count + 1      # 09-July-2023  previous +1 only simply reset value to 1 so loop was infinite
    if count==20:
        logger.error("No serial_number_evc found in MQTT queue. MQTT Control not available.")
        exit

if hasattr(GiV_Settings,'serial_number_evc'):
    logger.debug("Serial Number retrieved: "+GiV_Settings.serial_number_evc)
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "GivEnergy_GivTCP_EVC_Control")
    mqtt.Client.connected_flag=False        			#create flag in class
    if MQTTCredentials:
        client.username_pw_set(MQTT_Username,MQTT_Password)
    client.on_connect=on_connect     			        #bind call back function
    client.on_message=on_message                        #bind call back function
    #client.loop_start()

    logger.debug ("Connecting to broker(sub): "+ MQTT_Address)
    client.connect(MQTT_Address,port=MQTT_Port)
    client.loop_forever()

