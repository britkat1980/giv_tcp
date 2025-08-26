'''Test Module for GivEVC'''
from pymodbus.client.sync import ModbusTcpClient
import paho.mqtt.client as mqtt
import logging
import importlib
import datetime
import time
import pickle
from os.path import exists, basename
import os
from threading import Lock
import json
import settings
from settings import GiV_Settings
import sys

#Logging config
import logging, os
import sys
from logging.handlers import TimedRotatingFileHandler
logging.basicConfig(format='%(asctime)s - EVC'+ \
                    ' - %(module)-11s -  [%(levelname)-8s] - %(message)s')
formatter = logging.Formatter(
    '%(asctime)s - %(module)s - [%(levelname)s] - %(message)s')
fh = TimedRotatingFileHandler(GiV_Settings.Debug_File_Location, when='midnight', backupCount=7)
fh.setFormatter(formatter)
logger = logging.getLogger('evc_logger')
logger.addHandler(fh)
if str(GiV_Settings.Log_Level).lower()=="debug":
    logger.setLevel(logging.DEBUG)
elif str(GiV_Settings.Log_Level).lower()=="write_debug":
    logger.setLevel(logging.INFO)
elif str(GiV_Settings.Log_Level).lower()=="info":
    logger.setLevel(logging.INFO)
elif str(GiV_Settings.Log_Level).lower()=="critical":
    logger.setLevel(logging.CRITICAL)
elif str(GiV_Settings.Log_Level).lower()=="warning":
    logger.setLevel(logging.WARNING)
else:
    logger.setLevel(logging.ERROR)

cacheLock = Lock()
logging.getLogger("pymodbus").setLevel(logging.CRITICAL) 

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

_client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "GivEnergy_GivEVC")

class EVCType:
    """Defines type for data objects"""
    def __init__(self,dT,sC,cF):
        self.devType = dT
        self.sensorClass=sC
        self.controlFunc=cF

class EVCLut:
    regcache=GiV_Settings.cache_location+"/evc_regCache.pkl"
    invregcache=GiV_Settings.cache_location+"/regCache_"+str(GiV_Settings.givtcp_instance)+".pkl"
    cachelockfile=GiV_Settings.cache_location+"/.regcache_lockfile_"+str(GiV_Settings.givtcp_instance)
    charge_control=['Ready','Start','Stop']
    charging_mode=['Grid','Hybrid','Solar']
    status=[
        'Unknown',
        'Idle',
        'Connected',
        'Starting',
        'Charging',
        'Startup Failure',
        'End of Charging',
        'System Failure',
        'Scheduled',
        'Updating',
        'Unstable CP'
    ]
    cable_status=[
        'Not Connected',
        'Connected',
    ]
    error_codes={
        0:'Clear',
        11:'CP voltage is abnormal',
        12:'Emergency stop',
        13:'Undervoltage',
        14:'Overvoltage',
        15:'Over temperature',
        16:'Meter failure',
        17:'Leakage fault',
        18:'Output short circuit',
        19:'Overcurrent',
        21:'Vehicle response timeout',
        22:'No diode at the vehicle end',
        23:'Relay sticking',
        24:'Leakage current device failure',
        25:'Ground fault',
        26:'Failed to start process',
    }

    evc_lut={
        0: ('Charging_State',status),
        2: ('Connection_Status',cable_status),
        4: ('Error_Code',error_codes),
        6: 'Current_L1',
        8: 'Current_L2',
        10: 'Current_L3',
        13: 'Active_Power',
        17: 'Active_Power_L1',
        20: 'Active_Power_L2',
        24: 'Active_Power_L3',
        29: 'Meter_Energy',
        32: 'Evse_Max_Current',
        34: 'Evse_Min_Current',
        36: 'Charge_Limit',
        72: 'Charge_Session_Energy',
        79: 'Charge_Session_Duration',
        93: 'Plug_and_Go',
        94: ('Charge_Control',charge_control),
        109: 'Voltage_L1',
        111: 'Voltage_L2',
        113: 'Voltage_L3'}
    
    def get_regcache():
        try:
            count=0
            if exists(EVCLut.cachelockfile):
                logger.debug("regcache in use, waiting...")
                with open(EVCLut.cachelockfile) as inp:
                    lock_age=inp.read()
                try:
                    file_age=datetime.datetime.strptime(lock_age, '%Y-%m-%dT%H:%M:%S%z')
                except:
                    file_age=datetime.datetime.now(datetime.timezone.utc)
                timesince=datetime.datetime.now(datetime.timezone.utc) - file_age
                if timesince.total_seconds>10:
                    logger.error("regCache Lockfile is too old, forcibly removing...")
                    os.remove(EVCLut.cachelockfile)
                while True:
                    count +=1
                    time.sleep(0.5)
                    if not exists(EVCLut.cachelockfile):
                        logger.debug("regcache now available")
                        break
                    if count==10:
                        # loop round for 5s waiting for it to become available
                        logger.error("Timed out waiting for regcache")
                        os.remove(EVCLut.cachelockfile)
                        return None
            with open(EVCLut.cachelockfile, 'w') as inp: #create lock file
                inp.write(datetime.datetime.now(datetime.timezone.utc).isoformat())
            if exists(EVCLut.invregcache):
                logger.debug("Opening regcache at: "+str(EVCLut.invregcache))
                with open(EVCLut.invregcache, 'rb') as inp:
                    regCacheStack = pickle.load(inp)
                os.remove(EVCLut.cachelockfile)
                return regCacheStack
            else:
                os.remove(EVCLut.cachelockfile)
                logger.debug("regcache doesn't exist...")
                return None
        except:
            e=sys.exc_info()
            if exists(EVCLut.cachelockfile):
                os.remove(EVCLut.cachelockfile)
            logger.error("Failed to get Cache: "+str(e))
            return None

def getEVC(client:ModbusTcpClient):
    regs=[]
    output={}
    multi_output={}
    try:
        #if client.connect():
        if client.is_socket_open():
            logger.debug("Socket is already open")
        else:
            logger.debug("Socket isn't yet open")
        result = client.read_holding_registers(0,60)
        if not client.is_socket_open():
            logger.debug("Socket is closed")
        else:
            logger.debug("Socket is still open")
        result2 = client.read_holding_registers(60,55)
        #else:
        #    return output

        if not hasattr(result,'registers') or not hasattr(result2,'registers'):
            return output
        regs=result.registers+result2.registers
        for reg in EVCLut.evc_lut.items():
            if isinstance(reg[1],tuple):
                output[reg[1][0]]=reg[1][1][regs[reg[0]]]
            else:
                if 'Current' in str(reg[1]):
                    val=regs[reg[0]]/10
                elif 'Voltage' in str(reg[1]):
                    val=regs[reg[0]]/10
                elif 'Energy' in str(reg[1]):
                    val=regs[reg[0]]/10
                elif 'Limit' in str(reg[1]):
                    val=regs[reg[0]]/10
                else:
                    val=regs[reg[0]]
                output[reg[1]]=val
        SN=''
        for num in regs[38:69]:
            if not num==0:
                SN=SN+chr(num)
        output['Serial_Number']=SN

        if exists(EVCLut.regcache):
            with open(EVCLut.regcache, 'rb') as inp:
                evcRegCache= pickle.load(inp)

            if output['Charge_Session_Energy']==0 and not output['Charging_State']=='Charging':     #If charging has finished, then hold the previous charge session energy
                output['Charge_Session_Energy']=evcRegCache['Charger']['Charge_Session_Energy']
            

            startTime=datetime.datetime.now().replace(hour=regs[74],minute=regs[75],second=regs[76],microsecond=0,tzinfo=datetime.timezone.utc).isoformat()
            endtime=datetime.datetime.now().replace(hour=regs[82],minute=regs[83],second=regs[84],microsecond=0,tzinfo=datetime.timezone.utc).isoformat()
            if startTime==evcRegCache['Charger']['Charge_Start_Time']:
                output['Charge_Start_Time']=evcRegCache['Charger']['Charge_Start_Time']
            else:
                output['Charge_Start_Time']=datetime.datetime.now().replace(hour=regs[74],minute=regs[75],second=regs[76],microsecond=0,tzinfo=datetime.timezone.utc).isoformat()

            if str(endtime)==evcRegCache['Charger']['Charge_End_Time']:
                output['Charge_End_Time']=evcRegCache['Charger']['Charge_End_Time']
            else:
                output['Charge_End_Time']=datetime.datetime.now().replace(hour=regs[82],minute=regs[83],second=regs[84],microsecond=0,tzinfo=datetime.timezone.utc).isoformat()
            
            if not "Import_Cap" in evcRegCache['Charger']:
                output['Import_Cap']=0
            else:
                output['Import_Cap']=evcRegCache['Charger']['Import_Cap']

            if not "Charging_Mode" in evcRegCache['Charger']:
                output['Charging_Mode']="Grid"
            else:
                output['Charging_Mode']=evcRegCache['Charger']['Charging_Mode']

            if not 'Max_Session_Energy' in evcRegCache['Charger']:
                output['Max_Session_Energy']=0
            else:
                output['Max_Session_Energy']=evcRegCache['Charger']['Max_Session_Energy']
        else:
            ts=datetime.datetime.now().replace(hour=regs[82],minute=regs[83],second=regs[84],microsecond=0)
            output['Charge_End_Time']=ts.replace(tzinfo=datetime.timezone.utc).isoformat()
            ts=datetime.datetime.now().replace(hour=regs[74],minute=regs[75],second=regs[76],microsecond=0)
            output['Charge_Start_Time']=ts.replace(tzinfo=datetime.timezone.utc).isoformat()
            output['Import_Cap']=0
            output['Charging_Mode']="Grid"
            output['Max_Session_Energy']=0
        if regs[0]==4:
            output['Charge_Control']='Start'
        else:
            output['Charge_Control']='Stop'
        
        if regs[93]==0:
            output['Plug_and_Go']='enable'
        else:
            output['Plug_and_Go']='disable'

        evcTime=datetime.datetime(regs[97],regs[98],regs[99],regs[100],regs[101],regs[102])

        output['System_Time']= evcTime.replace(tzinfo=datetime.timezone.utc).isoformat()

        td=datetime.timedelta(seconds=int(regs[79]))
        output['Charge_Session_Duration']=str(td)
        multi_output['Charger']=output
        # Save new data to Pickle

        with cacheLock:
            with open(EVCLut.regcache, 'wb') as outp:
                pickle.dump(multi_output, outp, pickle.HIGHEST_PROTOCOL)
    except Exception:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.debug("Error: "+ str(e))
    return output

def pubFromPickle():  # Publish last cached EVC Data
    multi_output = {}
    result = "Success"
    if not exists(EVCLut.regcache):  # if there is no cache, create it
        result = "Please get data from EVC first, either by calling runAll or waiting until the self-run has completed"
    if "Success" in result:
        with cacheLock:
            with open(EVCLut.regcache, 'rb') as inp:
                multi_output = pickle.load(inp)
        SN = multi_output['Charger']['Serial_Number']
        publishOutput(multi_output, SN)
    else:
        multi_output['result'] = result
    return json.dumps(multi_output, indent=4, sort_keys=True, default=str)

def start():
    self_run2()

def runAll(client):  # Read from EVC put in cache and publish
    # full_refresh=True
    result=getEVC(client)
    # implement timout on multiple failures
    if len(result)==0:
        multi_output={}
    else:
        # Step here to validate data against previous pickle?
        multi_output = pubFromPickle()
    return multi_output

def self_run2():
    client = ModbusTcpClient(GiV_Settings.evc_ip_address, auto_open=True, auto_close=True)
    TimeoutError=0
    while True:
        result=runAll(client)
        if len(result)==0:
            TimeoutError+=1
        else:
            TimeoutError=0
        if TimeoutError>10:
            logger.error("10 consecutive errors, pausing and waiting 5 mins for EVC modbus port to come back")
            client.close()
            time.sleep(300)
            TimeoutError=0
        else:
            time.sleep(GiV_Settings.evc_self_run_timer)
            

# Additional Publish options can be added here.
# A separate file in the folder can be added with a new publish "plugin"
# then referenced here with any settings required added into settings.py
def publishOutput(array, SN):
    tempoutput = {}
    tempoutput = iterate_dict(array)
    if GiV_Settings.MQTT_Output:
        if GiV_Settings.first_run_evc:
            updateFirstRun(SN)              # 09=July=23 - Always do this first irrespective of HA setting.
            if GiV_Settings.HA_Auto_D:        # Home Assistant MQTT Discovery
                logger.critical("Publishing Home Assistant Discovery messages")
                from EVC_HA_Discovery import HAMQTT
                HAMQTT.publish_discovery2(tempoutput, SN)
            GiV_Settings.first_run_evc = False  
        logger.debug("Publish all to MQTT")
        if GiV_Settings.MQTT_Topic == "":
            GiV_Settings.MQTT_Topic = "GivEnergy"
        multi_MQTT_publish(str(GiV_Settings.MQTT_Topic+"/"+SN+"/"), tempoutput)

def updateFirstRun(SN):
### Check if evc or inv and adjust the right line ###
    isSN = False
    script_dir = os.path.dirname(__file__)  # <-- absolute dir the script is in
    rel_path = "settings.py"
    abs_file_path = os.path.join(script_dir, rel_path)
    #check for settings lockfile before
    count=0
    while True:
        logger.debug("Opening settings for first run evc")
        if exists('.settings_lockfile'):
            logger.debug("Waiting for settings to be availble")
            time.sleep(1)
            count=count+1
            if count==50:
                logger.error("Could not access settings file to update EVC Serial Number")
                break
        else:
            logger.debug("Settings available evc")
            #Create setting lockfile
            open(".settings_lockfile",'a').close()

            with open(abs_file_path, "r") as f:
                lines = f.readlines()
            with open(abs_file_path, "w") as f:
                for line in lines:
                    if line.strip("\n") == "    first_run_evc= True":
                        f.write("    first_run_evc= False\n")
                    else:
                        f.write(line)
                    if "serial_number_evc" in line:
                        logger.debug("serial number aready exists: \""+line+"\"")
                        isSN = True

                if not isSN:
                    logger.debug("serial number not in file, adding now")
                    f.writelines("    serial_number_evc = \""+SN+"\"\n")  # only add SN if its not there
            # Delete settings_lockfile
            os.remove('.settings_lockfile')
            logger.debug("removing lockfile")
            break

def on_connect(_client, userdata, flags, reason_code, properties):
    if reason_code==0:
        _client.connected_flag=True #set flag
        logger.debug("connected OK Returned code="+str(reason_code))
        _client.subscribe(MQTT_Topic+"/control/#")
        logger.debug("Subscribing to "+MQTT_Topic+"/control/#")
    else:
        logger.error("Bad connection Returned code= "+str(reason_code))
    

def get_connection():
    global _client
    if not _client.connected_flag:
        logger.debug("MQTT Connection appears closed, re-opening")
        if MQTTCredentials:
            _client.username_pw_set(MQTT_Username,MQTT_Password)
        _client.on_connect=on_connect     			#bind call back function
        _client.on_message=on_message     			#bind call back function
        logger.debug("Opening MQTT Connection to "+str(MQTT_Address))
        _client.connect(MQTT_Address,port=MQTT_Port)
        _client.loop_start()
    return _client

def multi_MQTT_publish(rootTopic,array):                    #Recieve multiple payloads with Topics and publish in a single MQTT connection
    client=get_connection()
    try:
        while not client.connected_flag:        			#wait in loop
            logger.debug ("In wait loop (multi_MQTT_publish)")
            time.sleep(0.2)
        for p_load in array:
            payload=array[p_load]
            logger.debug('Publishing: '+rootTopic+p_load)
            output=iterate_dict_mqtt(payload,rootTopic+p_load)   #create LUT for MQTT publishing
            for value in output:
                if isinstance(output[value],(int, str, float, bytearray)):      #Only publish typesafe data
                    client.publish(value,output[value], retain=GiV_Settings.MQTT_Retain)
    except:
        e=sys.exc_info()[0].__name__, basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("Error connecting to MQTT Broker: " + str(e))
        client.loop_stop()                      			    #Stop loop
        client.disconnect()

def iterate_dict_mqtt(array,topic):      #Create LUT of topics and datapoints
    MQTT_LUT={}
    if isinstance(array, dict):
        # Create a publish safe version of the output
        for p_load in array:
            output=array[p_load]
            if isinstance(output, dict):
                MQTT_LUT.update(iterate_dict_mqtt(output,topic+"/"+p_load))
                logger.debug('Prepping '+p_load+" for publishing")
            else:
                MQTT_LUT[topic+"/"+p_load]=output
    else:
        MQTT_LUT[topic]=array
    return(MQTT_LUT)

def iterate_dict(array):        # Create a publish safe version of the output (convert non-string or int datapoints)
    safeoutput = {}
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
        elif isinstance(output, float):
            safeoutput[p_load] = round(output, 3)
        else:
            safeoutput[p_load] = output
    return(safeoutput)

def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False

def on_message(client, userdata, message):
    from settings import GiV_Settings
    proceed=False
    if not hasattr(GiV_Settings,'serial_number_evc'):
        importlib.reload(settings)
        from settings import GiV_Settings
        if hasattr(GiV_Settings,'serial_number_evc'):
            logger.debug("EVC serial num now found and is: "+str(GiV_Settings.serial_number_evc))
            proceed=True
    else:
        proceed=True

    if proceed:
        if not GiV_Settings.serial_number_evc in message.topic:
            return
        payload={}
        logger.debug("MQTT Message Recieved: "+str(message.topic)+"= "+str(message.payload.decode("utf-8")))
        writecommand={}
        try:
            command=str(message.topic).split("/")[-1]
            if command=="chargeMode":
                writecommand=message.payload.decode("utf-8")
                setChargeMode(writecommand)
            elif command=="controlCharge":
                writecommand=message.payload.decode("utf-8")
                setChargeControl(writecommand)
            elif command=="setCurrentLimit":
                writecommand=message.payload.decode("utf-8")
                setCurrentLimit(int(writecommand))
            elif command=="setImportCap":
                writecommand=message.payload.decode("utf-8")
                setImportCap(writecommand)
            elif command=="setChargingMode":
                writecommand=message.payload.decode("utf-8")
                setChargingMode(writecommand)
            elif command=="setMaxSessionEnergy":
                writecommand=message.payload.decode("utf-8")
                setMaxSessionEnergy(int(writecommand))
            elif command=="setSystemTime":
                writecommand=message.payload.decode("utf-8")
                setDateTime(writecommand)
        except:
            e = sys.exc_info()
            logger.error("MQTT.OnMessage Exception: "+str(e))
            return
    else:
        logger.info("No serial_number_evc found in MQTT queue. MQTT Control not yet available.")

def getEVCCache():
    if exists(EVCLut.regcache):
        with open(EVCLut.regcache, 'rb') as inp:
            evcRegCache= pickle.load(inp)
        return json.dumps(evcRegCache)
    else:
        return json.dumps("No EVC data found",indent=4)

def setChargeMode(mode):
    try:
        if mode=="enable":
            val=0
        elif mode=="disable":
            val=1
        else:
            logger.error("Invalid control mode called: "+str(mode))
            return
        logger.info("Setting Charge mode to: "+ mode)
        logger.debug("numeric value "+str(val)+ " sent to EVC")
        client=ModbusTcpClient(GiV_Settings.evc_ip_address)
        client.write_registers(93,val)
    except:
        e=sys.exc_info()
        logger.error("Error controlling EVC: "+str(e))

def setChargeControl(mode):
    try:
        if mode in EVCLut.charge_control:
            logger.info("Setting Charge control to: "+ mode)
            val=EVCLut.charge_control.index(mode)
            logger.debug("numeric value "+str(val)+ " sent to EVC")
            try:
                client=ModbusTcpClient(GiV_Settings.evc_ip_address)
                client.write_registers(95,val)
            except:
                e=sys.exc_info()
                logger.error("Error controlling EVC: "+str(e))
        else:
            logger.error("Invalid selection for Charge Control ("+str(mode)+")")
    except:
        e=sys.exc_info()
        logger.error("Error setting Charge Conrol: "+str(e))

def setCurrentLimit(val):
    try:
        #Check limit is between 6 and MAX SAFE LIMIT
        if exists(EVCLut.regcache):
            with cacheLock:
                with open(EVCLut.regcache, 'rb') as inp:
                    evcRegCache= pickle.load(inp)
            safeMax=int(evcRegCache['Charger']['Evse_Max_Current'])
            safeMin=int(evcRegCache['Charger']['Evse_Min_Current'])
            val=max(val,safeMin)  #Force to 6 if less than
            val=min(val,safeMax) # Get safe MAX value from pkl
            client=ModbusTcpClient(GiV_Settings.evc_ip_address)
            res=client.write_registers(91,(val*10))
            logger.info("Charge current limit set to: "+ str(val))

    except:
        e=sys.exc_info()
        logger.error("Error controlling EVC: "+str(e))

def chargeMode(once=False):
    while True:
        #Run a regular check and manage load based on current mode and session energy
        try:
            if exists(EVCLut.regcache):
                with cacheLock:
                    with open(EVCLut.regcache, 'rb') as inp:
                        evcRegCache= pickle.load(inp)                
                if evcRegCache['Charger']['Charging_State']=="Charging" or evcRegCache['Charger']['Charging_State']=="Connected":
                    if evcRegCache['Charger']['Charging_Mode']=="Hybrid":
                        hybridmode()
                    elif evcRegCache['Charger']['Charging_Mode']=="Solar":
                        solarmode()
                if not evcRegCache['Charger']['Max_Session_Energy']==0 and evcRegCache['Charger']['Charge_Session_Energy']>=evcRegCache['Charger']['Max_Session_Energy'] and evcRegCache['Charger']['Charge_Control']=="Start":
                    logger.info("Session energy limit reached: "+str(evcRegCache['Charger']['Charge_Session_Energy'])+"kWh stopping charge")
                    setChargeControl("Stop")
                if not int(evcRegCache['Charger']['Import_Cap'])==0 and evcRegCache['Charger']['Charging_State']=="Charging":
                    invRegCache = EVCLut.get_regcache()
                    if invRegCache:
                        if float(invRegCache[-1]['Power']['Power']['Grid_Current'])>(float(evcRegCache['Charger']['Import_Cap'])*0.95):
                            target=float(evcRegCache['Charger']['Import_Cap'])*0.9
                            reduction=(float(invRegCache[-1]['Power']['Power']['Grid_Current']))-target
                            newlimit=int(float(evcRegCache['Charger']['Charge_Limit'])-reduction)
                            logger.info("Car charge current too high reducing... ("+str(evcRegCache['Charger']['Charge_Limit'])+"A - "+str(reduction)+"A = "+str(newlimit)+")")
                            #if not int(evcRegCache['Charger']['Charge_Limit'])==4:
                            if int(newlimit)>=6:
                                logger.info("Grid import threshold within 5%, reducing EVC charge current to: "+str(newlimit))
                                setCurrentLimit(newlimit)
                            else:
                                logger.info("Grid import threshold within 5%, cannot reduce Charge limit below 6A. Stopping Charge")
                                setChargeControl("Stop")
        except:
            e=sys.exc_info()
            logger.error("Error in EVC charge mode loop: "+str(e))
        if once:
            break
        time.sleep(30)
    

def hybridmode():
    try:
        if exists(EVCLut.regcache) and exists(EVCLut.invregcache):
            # Set charging current to min 6A plus the level of excess solar
            with cacheLock:
                with open(EVCLut.regcache, 'rb') as inp:
                    evcRegCache= pickle.load(inp)
            invRegCache = EVCLut.get_regcache()
            if invRegCache:
                sparePower=invRegCache[-1]['Power']['Power']['PV_Power']-invRegCache[-1]['Power']['Power']['Load_Power']+evcRegCache['Charger']['Active_Power_L1']
                spareCurrent=int(max((sparePower/invRegCache[-1]['Power']['Power']['Grid_Voltage']),0)+6)   #Spare current cannot be negative
                if not spareCurrent==evcRegCache['Charger']['Charge_Limit']:
                    logger.info("Topping up min charge with Solar curent ("+str(spareCurrent-6)+"A), setting EVC charge to: "+str(spareCurrent)+"A")
                    setCurrentLimit(spareCurrent)
    except:
        e=sys.exc_info()
        logger.error("Error in EVC hybrid mode: "+str(e))

def gridmode():
    # Just don't do anything in Grid Mode and leave charging current as it was
    return

def solarmode():
    # Set charging current to the level of excess solar
    try:
        if exists(EVCLut.regcache) and exists(EVCLut.invregcache):
            with cacheLock:
                with open(EVCLut.regcache, 'rb') as inp:
                    evcRegCache= pickle.load(inp)
            invRegCache = EVCLut.get_regcache()
            if invRegCache:
                sparePower=invRegCache[-1]['Power']['Power']['PV_Power']-invRegCache[-1]['Power']['Power']['Load_Power']+evcRegCache['Charger']['Active_Power_L1']
                spareCurrent=int(max((sparePower/invRegCache[-1]['Power']['Power']['Grid_Voltage']),0)+6)   #Spare current cannot be negative
                if sparePower>6:    #only if there's excess above min evse level
                    if not spareCurrent==evcRegCache['Charger']['Current_L1']:
                        logger.info("Spare Solar curent ("+str(spareCurrent)+"), setting EVC charge to: "+str(spareCurrent)+"A")
                        setChargeControl("Start")
                        setCurrentLimit(spareCurrent)
                else:
                    if not evcRegCache['Charger']['Charge_Control']=="Stop":
                        logger.info("Solar excess dropped to below 6A, stopping charge")
                        setChargeControl("Stop")
    except:
        e=sys.exc_info()
        logger.error("Error setting EVC solar mode: "+str(e))

def setMaxSessionEnergy(val):
    try:
        if exists(EVCLut.regcache):
            logger.info("Setting Max Session energy to: "+str(val))
            with open(EVCLut.regcache, 'rb') as inp:
                evcRegCache= pickle.load(inp)
            evcRegCache['Charger']['Max_Session_Energy']=val
            with cacheLock:
                with open(EVCLut.regcache, 'wb') as outp:
                    pickle.dump(evcRegCache, outp, pickle.HIGHEST_PROTOCOL)
    except:
        e=sys.exc_info()
        logger.error("Error in setting Max Session energy: "+str(e))


def setImportCap(val):
    try:
        if exists(EVCLut.regcache):
            logger.info("Setting Import Cap to: "+str(val))
            with cacheLock:
                with open(EVCLut.regcache, 'rb') as inp:
                    evcRegCache= pickle.load(inp)
            evcRegCache['Charger']['Import_Cap']=val
            with cacheLock:
                with open(EVCLut.regcache, 'wb') as outp:
                    pickle.dump(evcRegCache, outp, pickle.HIGHEST_PROTOCOL)
    except:
        e=sys.exc_info()
        logger.error("Error setting EVC Import Cap: "+str(e))

def setChargingMode(mode):
    try:
        if mode in EVCLut.charging_mode:
            if exists(EVCLut.regcache):
                logger.info("Setting Charging Mode to: "+str(mode))
                with open(EVCLut.regcache, 'rb') as inp:
                    evcRegCache= pickle.load(inp)
                evcRegCache['Charger']['Charging_Mode']=mode
                with cacheLock:
                    with open(EVCLut.regcache, 'wb') as outp:
                        pickle.dump(evcRegCache, outp, pickle.HIGHEST_PROTOCOL)
                chargeMode(True)    # Run an initial call when changing modes
        else:
            logger.error("Invalid selection for Charge Mode ("+str(mode)+")")
    except:
        e=sys.exc_info()
        logger.error("Error setting EVC Charge Mode: "+str(e))


def setDateTime(sysTime):
    temp={}
    try:
        if not isinstance(sysTime,datetime.datetime):
            sysTime=datetime.strptime(sysTime,"%d/%m/%Y %H:%M:%S")   #format '12/11/2021 09:15:32'
        logger.info("Setting EVC time to: "+sysTime.isoformat())
        #Set Date and Time on inverter
        try:
            client=ModbusTcpClient(GiV_Settings.evc_ip_address)
            res=client.write_registers(97,[sysTime.year,sysTime.month,sysTime.day,sysTime.hour,sysTime.minute,sysTime.second])
            logger.info("Time Set")
        except:
            e=sys.exc_info()
            logger.error("Error Setting EVC Time: "+str(e))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])