from datetime import datetime, timedelta, timezone
from genericpath import exists
import os, pickle, subprocess, logging,shutil, shlex, schedule
from time import sleep
#import rq_dashboard
import zoneinfo
import sys
import requests
from GivTCP.findInvertor import findInvertor
from GivTCP.findEVC import findEVC
import givenergy_modbus.model.inverter
from givenergy_modbus.client import GivEnergyClient
from pymodbus.client.sync import ModbusTcpClient

selfRun={}
mqttClient={}
gunicorn={}
webDash={}
rqWorker={}
redis={}
networks={}
SuperTimezone=""

logger = logging.getLogger("startup")
logging.basicConfig(format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
if str(os.getenv("LOG_LEVEL")).lower()=="debug":
    logger.setLevel(logging.DEBUG)
elif str(os.getenv("LOG_LEVEL")).lower()=="info":
    logger.setLevel(logging.INFO)
elif str(os.getenv("LOG_LEVEL")).lower()=="critical":
    logger.setLevel(logging.CRITICAL)
elif str(os.getenv("LOG_LEVEL")).lower()=="warning":
    logger.setLevel(logging.WARNING)
else:
    logger.setLevel(logging.ERROR)
logging.getLogger("givenergy_modbus").setLevel(logging.CRITICAL)

# Check if config directory exists and creates it if not

def palm_job():
    subprocess.Popen(["/usr/local/bin/python3","/app/GivTCP_1/palm_soc.py"])

def validateEVC(HOST):
    logger.debug("Validating "+str(HOST))
    try:
        client = ModbusTcpClient(HOST)
        regs = client.read_holding_registers(97,6).registers
        systime=datetime(regs[0],regs[1],regs[2],regs[3],regs[4],regs[5]).replace(tzinfo=timezone.utc).isoformat()
        return True
    except:
        e=sys.exc_info()
        logger.info(e)
        return False

def getInvDeets(HOST):
    try:
        client=GivEnergyClient(host=HOST)
        stats=client.get_inverter_stats()
        SN=stats[2]
        gen=givenergy_modbus.model.inverter.Generation.from_fw_version(stats[1])._value_
        model=givenergy_modbus.model.inverter.Model.from_device_type_code(stats[0])
        fw=stats[1]
        return SN,gen,model,fw
    except:
        logger.error("Gathering inverter details for " + str(HOST) + " failed.")
        return None

def findinv(networks):
    if len(networks)>0:
    # For each interface scan for inverters
        logger.debug("Networks available for scanning are: "+str(networks))
        Stats={}
        inverterStats={}
        invList={}
        list={}
        evclist={}
        logger.critical("Scanning network for GivEnergy Devices...")
        try:
            for subnet in networks:
                if networks[subnet]:
                    count=0
                    # Get EVC Details
                    while len(evclist)<=0:
                        if count<2:
                            logger.debug("EVC- Scanning network ("+str(count+1)+"):"+str(networks[subnet]))
                            evclist=findEVC(networks[subnet])
                            if len(evclist)>0: break
                            count=count+1
                        else:
                            break
                    if evclist:
                        poplist=[]
                        for evc in evclist:
                            if validateEVC(evclist[evc]):
                                logger.critical("GivEVC found at: "+str(evclist[evc]))
                            else:
                                logger.info(evclist[evc]+" is not an EVC")
                                poplist.append(evc)
                        for pop in poplist:
                            evclist.pop(pop)    #remove the unknown modbus device(s)
                    # Get Inverter Details
                    count=0
                    while len(list)<=0:
                        if count<2:
                            logger.debug("INV- Scanning network ("+str(count+1)+"):"+str(networks[subnet]))
                            list=findInvertor(networks[subnet])
                            if len(list)>0: break
                            count=count+1
                        else:
                            break
                    if list:
                        logger.debug(str(len(list))+" Inverters found on "+str(networks[subnet])+" - "+str(list))
                        invList.update(list)
                        for inv in invList:
                            deets={}
                            logger.debug("Getting inverter stats for: "+str(invList[inv]))
                            count=0
                            while not deets:
                                if count<2:
                                    deets=getInvDeets(invList[inv])
                                    if deets:
                                        logger.critical (f'Inverter {deets[0]} which is a {str(deets[1])} - {str(deets[2])} has been found at: {str(invList[inv])}')
                                        Stats['Serial_Number']=deets[0]
                                        Stats['Firmware']=deets[3]
                                        Stats['Model']=deets[2]
                                        Stats['Generation']=deets[1]
                                        inverterStats[inv]=Stats
                                    else:
                                        logger.error("Unable to interrogate inverter to get base details")
                                    count=count+1
                                else:
                                    break
                    if len(invList)==0:
                        logger.critical("No inverters found...")
                    else:
                    # write data to pickle
                        with open('invippkl.pkl', 'wb') as outp:
                            pickle.dump(inverterStats, outp, pickle.HIGHEST_PROTOCOL)
        except:
            e = sys.exc_info()
            logger.error("Error scanning for Inverters- "+str(e))
    else:
        logger.error("Unable to get host details from Supervisor\Container")
    return inverterStats


SuperTimezone={}        # 02-Aug-23  default it to None so that it is defined for saving in settngs.py for non-HA usage (otherwise exception)

try:
    logger.debug("SUPERVISOR_TOKEN is: "+ os.getenv("SUPERVISOR_TOKEN"))
    isAddon=True
    access_token = os.getenv("SUPERVISOR_TOKEN")
except:
    logger.critical("SUPERVISOR TOKEN does not exist")
    isAddon=False
    hasMQTT=False
    SuperTimezone=False

if isAddon:
    #Get MQTT Details    
    url="http://supervisor/services/mqtt"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    mqttDetails=result.json()
    if mqttDetails['result']=="ok":
        logger.critical ("HA MQTT Service has been found at "+str(mqttDetails['data']['host']))
        mqtt_host=mqttDetails['data']['host']
        mqtt_username=mqttDetails['data']['username']
        mqtt_password=mqttDetails['data']['password']
        mqtt_port=mqttDetails['data']['port']
        hasMQTT=True
    else:
        hasMQTT=False
        logger.critical("No HA MQTT service has been found")

    #Get Timezone    
    url="http://supervisor/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    info=result.json()
    SuperTimezone=info['data']['timezone']
    logger.info("Supervisor Timezone: "+str(SuperTimezone))

    #Get Host Details    
    url="http://supervisor/network/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    hostDetails=result.json()
    i=0
    for interface in hostDetails['data']['interfaces']:
        networks[i]=interface['ipv4']['gateway']
        i=i+1
else:
    # Get subnet from docker if not addon
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
        s.close()
        networks[0]=IP
    except:
        e=sys.exc_info()
        logger.error("Could not get network info: "+ str(e))

sleep(2)        # Sleep to allow port scanning se-ocket to close

inverterStats={}
i=0
while len(inverterStats)==0:
    inverterStats=findinv(networks)
    i=i+1
    if i==3: 
        break
    else:
        logger.info("Searching for Inverters again")

logger.debug("GivTCP isAddon: "+str(isAddon))

if not os.path.exists(str(os.getenv("CACHELOCATION"))):
    os.makedirs(str(os.getenv("CACHELOCATION")))
    logger.debug("No config directory exists, so creating it...")
else:
    logger.debug("Config directory already exists")

redis=subprocess.Popen(["/usr/bin/redis-server","/app/redis.conf"])
logger.critical("Running Redis")

#rqdash=subprocess.Popen(["/usr/local/bin/rq-dashboard","-u redis://127.0.0.1:6379"])
#logger.critical("Running RQ Dashboard on port 9181")

#vueConfig=subprocess.Popen(["npm", "run", "dev","-- --host"],cwd="/app/config_frontend")
#logger.critical("Running Config Frontend")

subprocess.Popen(["nginx","-g","daemon off;error_log /dev/stdout debug;"])

##########################################################################################################
#
#
#   Up to now everything is __init__ type prep, below is conifg setting (move to webpage and not ENV...) #
# 
# 
##########################################################################################################


for inv in range(1,int(os.getenv('NUMINVERTORS'))+1):
    logger.critical ("Setting up invertor: "+str(inv)+" of "+str(os.getenv('NUMINVERTORS')))
    PATH= "/app/GivTCP_"+str(inv)
    PATH2= "/app/GivEnergy-Smart-Home-Display-givtcp_"+str(inv)

    # Create folder per instance
    if not exists(PATH):
        shutil.copytree("/app/GivTCP", PATH)
        shutil.copytree("/app/GivEnergy-Smart-Home-Display-givtcp", PATH2)
    if not exists(PATH+"/settings.json"):
        logger.debug("Copying in a template settings.json")
        shutil.copyfile("/app/settings.json",PATH+"/settings.json")
    else:
        logger.debug("Settings.json already exists")
    # Remove old settings file
    if exists(PATH+"/settings.py"):
        os.remove(PATH+"/settings.py")
    FILENAME=""
    # create settings file
    logger.debug("Recreating settings.py for invertor "+str(inv))
    with open(PATH+"/settings.py", 'w') as outp:
        outp.write("class GiV_Settings:\n")
        outp.write("    invertorIP=\""+str(os.getenv("INVERTOR_IP_"+str(inv),""))+"\"\n")
        outp.write("    numBatteries="+str(os.getenv("NUMBATTERIES_"+str(inv),"")+"\n"))
        outp.write("    isAIO="+str(os.getenv("INVERTOR_AIO_"+str(inv),"")+"\n"))
        outp.write("    isAC="+str(os.getenv("INVERTOR_AC_"+str(inv),"")+"\n"))
        outp.write("    Print_Raw_Registers="+str(os.getenv("PRINT_RAW",""))+"\n")
        outp.write("    MQTT_Output="+str(os.getenv("MQTT_OUTPUT","")+"\n"))
        if hasMQTT:
            outp.write("    MQTT_Address=\""+str(mqtt_host)+"\"\n")
            outp.write("    MQTT_Username=\""+str(mqtt_username)+"\"\n")
            outp.write("    MQTT_Password=\""+str(mqtt_password)+"\"\n")
            outp.write("    MQTT_Port="+str(mqtt_port)+"\n")
        else:
            outp.write("    MQTT_Address=\""+str(os.getenv("MQTT_ADDRESS","")+"\"\n"))
            outp.write("    MQTT_Username=\""+str(os.getenv("MQTT_USERNAME","")+"\"\n"))
            outp.write("    MQTT_Password=\""+str(os.getenv("MQTT_PASSWORD","")+"\"\n"))
            outp.write("    MQTT_Port="+str(os.getenv("MQTT_PORT","")+"\n"))
        outp.write("    MQTT_Retain="+str(os.getenv("MQTT_RETAIN","")+"\n"))
        if isAddon:
            outp.write("    HA_Auto_D=True\n")
        else:
            outp.write("    HA_Auto_D="+str(os.getenv("HA_AUTO_D",""))+"\n")
        if inv==1:
            outp.write("    MQTT_Topic=\""+str(os.getenv("MQTT_TOPIC","")+"\"\n"))
        else:
            outp.write("    MQTT_Topic=\""+str(os.getenv("MQTT_TOPIC_"+str(inv),"")+"\"\n"))

        outp.write("    Log_Level=\""+str(os.getenv("LOG_LEVEL","")+"\"\n"))
        #setup debug filename for each inv
        outp.write("    Influx_Output="+str(os.getenv("INFLUX_OUTPUT",""))+"\n")
        outp.write("    influxURL=\""+str(os.getenv("INFLUX_URL","")+"\"\n"))
        outp.write("    influxToken=\""+str(os.getenv("INFLUX_TOKEN","")+"\"\n"))
        outp.write("    influxBucket=\""+str(os.getenv("INFLUX_BUCKET","")+"\"\n"))
        outp.write("    influxOrg=\""+str(os.getenv("INFLUX_ORG","")+"\"\n"))
        outp.write("    first_run= True\n")
        outp.write("    first_run_evc= True\n")
        outp.write("    self_run_timer="+str(os.getenv("SELF_RUN_LOOP_TIMER","5"))+"\n")
        outp.write("    queue_retries="+str(os.getenv("QUEUE_RETRIES","2"))+"\n")    
        outp.write("    givtcp_instance="+str(inv)+"\n")
        outp.write("    default_path=\""+str(os.getenv("PATH","")+"\"\n"))
        outp.write("    dynamic_tariff="+str(os.getenv("DYNAMICTARIFF","")+"\n"))
        outp.write("    day_rate="+str(os.getenv("DAYRATE","")+"\n"))
        outp.write("    night_rate="+str(os.getenv("NIGHTRATE","")+"\n"))
        outp.write("    export_rate="+str(os.getenv("EXPORTRATE","")+"\n"))
        outp.write("    day_rate_start=\""+str(os.getenv("DAYRATESTART","")+"\"\n"))
        outp.write("    night_rate_start=\""+str(os.getenv("NIGHTRATESTART","")+"\"\n"))
        if inv==1:
            outp.write("    ha_device_prefix=\""+str(os.getenv("HADEVICEPREFIX","")+"\"\n"))
        else:
            outp.write("    ha_device_prefix=\""+str(os.getenv("HADEVICEPREFIX_"+str(inv),"")+"\"\n"))
        outp.write("    data_smoother=\""+str(os.getenv("DATASMOOTHER","")+"\"\n"))
        if str(os.getenv("CACHELOCATION"))=="":
            outp.write("    cache_location=\"/config/GivTCP\"\n")
            outp.write("    Debug_File_Location=\"/config/GivTCP/log_inv_"+str(inv)+".log\"\n")
        else:
            outp.write("    cache_location=\""+str(os.getenv("CACHELOCATION")+"\"\n"))
            outp.write("    Debug_File_Location=\""+os.getenv("CACHELOCATION")+"/log_inv_"+str(inv)+".log\"\n")
        outp.write("    inverter_num=\""+str(inv)+"\"\n")

        outp.write("    GE_API=\""+str(os.getenv("GEAPI")+"\"\n"))
        outp.write("    PALM_WINTER=\""+str(os.getenv("PALM_WINTER")+"\"\n"))
        outp.write("    PALM_SHOULDER=\""+str(os.getenv("PALM_SHOULDER")+"\"\n"))
        outp.write("    PALM_MIN_SOC_TARGET=\""+str(os.getenv("PALM_MIN_SOC_TARGET")+"\"\n"))
        outp.write("    PALM_MAX_SOC_TARGET=\""+str(os.getenv("PALM_MAX_SOC_TARGET")+"\"\n"))
        outp.write("    PALM_BATT_RESERVE=\""+str(os.getenv("PALM_BATT_RESERVE")+"\"\n"))
        outp.write("    PALM_BATT_UTILISATION=\""+str(os.getenv("PALM_BATT_UTILISATION")+"\"\n"))
        outp.write("    SOLCASTAPI=\""+str(os.getenv("SOLCASTAPI")+"\"\n"))
        outp.write("    SOLCASTSITEID=\""+str(os.getenv("SOLCASTSITEID")+"\"\n"))
        outp.write("    SOLCASTSITEID2=\""+str(os.getenv("SOLCASTSITEID2")+"\"\n"))
        outp.write("    PALM_WEIGHT=\""+str(os.getenv("PALM_WEIGHT")+"\"\n"))
        outp.write("    LOAD_HIST_WEIGHT=\""+str(os.getenv("LOAD_HIST_WEIGHT")+"\"\n"))

        outp.write("    evc_enable=\""+os.getenv("EVC_ENABLE")+"\"\n")
        outp.write("    evc_ip_address=\""+os.getenv("EVC_IP_ADDRESS")+"\"\n")
        outp.write("    evc_self_run_timer="+os.getenv("EVC_SELF_RUN_TIMER")+"\n")
        if SuperTimezone: outp.write("    timezone=\""+str(SuperTimezone)+"\"\n")
        

    ######
    #  Always delete lockfiles and FCRunning etc... but only delete pkl if too old?

    if exists(os.getenv("CACHELOCATION")+"/regCache_"+str(inv)+".pkl"):
        logger.debug("Removing old invertor data cache")
        os.remove(str(os.getenv("CACHELOCATION"))+"/regCache_"+str(inv)+".pkl")
    if exists(PATH+"/.lockfile"):
        logger.debug("Removing old .lockfile")
        os.remove(PATH+"/.lockfile")
    if exists(PATH+"/.FCRunning"):
        logger.debug("Removing old .FCRunning")
        os.remove(PATH+"/.FCRunning")
    if exists(PATH+"/.FERunning"):
        logger.debug("Removing old .FERunning")
        os.remove(PATH+"/.FERunning")
    if exists(os.getenv("CACHELOCATION")+"/battery_"+str(inv)+".pkl"):
        logger.debug("Removing old battery data cache")
        os.remove(str(os.getenv("CACHELOCATION"))+"/battery_"+str(inv)+".pkl")
    if exists(os.getenv("CACHELOCATION")+"/rateData_"+str(inv)+".pkl"):
        if "TZ" in os.environ:
            timezone=zoneinfo.ZoneInfo(key=os.getenv("TZ"))
        else:
            timezone=zoneinfo.ZoneInfo(key="Europe/London")
        modDay= datetime.fromtimestamp(os.path.getmtime(os.getenv("CACHELOCATION")+"/rateData_"+str(inv)+".pkl")).date()
        if modDay<datetime.now(timezone).date():
            logger.debug("Old rate data cache not updated today, so deleting")
            os.remove(str(os.getenv("CACHELOCATION"))+"/rateData_"+str(inv)+".pkl")
        else:
            logger.debug("Rate Data exisits but is from today so keeping it")


########### Run the various processes needed #############
# Check if settings.py exists then start processes
# Still need to run the below process per inverter
#
#




    os.chdir(PATH)

    rqWorker[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/worker.py"])
    logger.critical("Running RQ worker to queue and process givernergy-modbus calls")

    if not hasMQTT and os.getenv('MQTT_ADDRESS')=="127.0.0.1" and os.getenv('MQTT_OUTPUT')=="True":
        logger.critical ("Starting Mosquitto on port "+str(os.getenv('MQTT_PORT')))
        mqttBroker=subprocess.Popen(["/usr/sbin/mosquitto", "-c",PATH+"/mqtt.conf"])

    if os.getenv('SELF_RUN')=="True" or isAddon:
        logger.critical ("Running Invertor ("+str(os.getenv("INVERTOR_IP_"+str(inv),""))+") read loop every "+str(os.getenv('SELF_RUN_LOOP_TIMER'))+"s")
        selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "self_run2"])

    if os.getenv('EVC_ENABLE')=="True" and inv==1:  #only run it once
        if not os.getenv('EVC_IP_ADDRESS')=="":
            logger.critical ("Running EVC read loop every "+str(os.getenv('EVC_SELF_RUN_TIMER'))+"s")
            evcSelfRun=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
            logger.critical ("Subscribing MQTT Broker for EVC control")
            mqttClientEVC=subprocess.Popen(["/usr/local/bin/python3",PATH+"/mqtt_client_evc.py"])
            evcChargeModeLoop=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "chargeMode"])
            logger.critical ("Setting chargeMode loop to manage different charge modes every 60s")
        else:
            logger.critical("EVC IP is missing from config. Please update and restart GivTCP")

    if os.getenv('MQTT_OUTPUT')=="True" or isAddon:
        logger.critical ("Subscribing MQTT Broker for control")
        mqttClient[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/mqtt_client.py"])
    
    GUPORT=6344+inv
    logger.critical ("Starting Gunicorn on port "+str(GUPORT))
    command=shlex.split("/usr/local/bin/gunicorn -w 3 -b :"+str(GUPORT)+" REST:giv_api")
    gunicorn[inv]=subprocess.Popen(command)
    
    os.chdir(PATH2)
    if os.getenv('WEB_DASH')=="True":
        # Create app.json
        logger.debug("Creating web dashboard config")
        with open(PATH2+"/app.json", 'w') as outp:
            outp.write("{\n")
            outp.write("\"givTcpHostname\": \""+os.getenv('HOSTIP')+":6345\",")
            outp.write("\"solarRate\": "+os.getenv('DAYRATE')+",")
            outp.write("\"exportRate\": "+os.getenv('EXPORTRATE')+"")
            outp.write("}")
        WDPORT=int(os.getenv('WEB_DASH_PORT'))-1+inv
        logger.critical ("Serving Web Dashboard from port "+str(WDPORT))
        command=shlex.split("/usr/bin/node /usr/local/bin/serve -p "+ str(WDPORT))
        webDash[inv]=subprocess.Popen(command)

if str(os.getenv('SMARTTARGET'))=="True":
    starttime= datetime.strftime(datetime.strptime(os.getenv('NIGHTRATESTART'),'%H:%M') - timedelta(hours=0, minutes=10),'%H:%M')
    logger.critical("Setting daily charge target forecast job to run at: "+starttime)
    schedule.every().day.at(starttime).do(palm_job)

# Loop round checking all processes are running
while True:
    for inv in range(1,int(os.getenv('NUMINVERTORS'))+1):
        PATH= "/app/GivTCP_"+str(inv)
        if os.getenv('SELF_RUN')==True and not selfRun[inv].poll()==None:
            logger.error("Self Run loop process died. restarting...")
            os.chdir(PATH)
            logger.critical ("Restarting Invertor read loop every "+str(os.getenv('SELF_RUN_LOOP_TIMER'))+"s")
            selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "self_run2"])
        if os.getenv('MQTT_OUTPUT')==True and not mqttClient[inv].poll()==None:
            logger.error("MQTT Client process died. Restarting...")
            os.chdir(PATH)
            logger.critical ("Resubscribing Mosquitto for control on port "+str(os.getenv('MQTT_PORT')))
            mqttClient[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/mqtt_client.py"])
        if os.getenv('WEB_DASH')==True and not webDash[inv].poll()==None:
            logger.error("Web Dashboard process died. Restarting...")
            os.chdir(PATH2)
            WDPORT=int(os.getenv('WEB_DASH_PORT'))+inv-1
            logger.critical ("Serving Web Dashboard from port "+str(WDPORT))
            command=shlex.split("/usr/bin/node /usr/local/bin/serve -p "+ str(WDPORT))
            webDash[inv]=subprocess.Popen(command)
        if not gunicorn[inv].poll()==None:
            logger.error("REST API process died. Restarting...")
            os.chdir(PATH)
            GUPORT=6344+inv
            logger.critical ("Starting Gunicorn on port "+str(GUPORT))
            command=shlex.split("/usr/local/bin/gunicorn -w 3 -b :"+str(GUPORT)+" REST:giv_api")
            gunicorn[inv]=subprocess.Popen(command)
    if os.getenv('MQTT_ADDRESS')=="127.0.0.1" and not mqttBroker.poll()==None:
        logger.error("MQTT Broker process died. Restarting...")
        os.chdir(PATH)
        logger.critical ("Starting Mosquitto on port "+str(os.getenv('MQTT_PORT')))
        mqttBroker=subprocess.Popen(["/usr/sbin/mosquitto", "-c",PATH+"/mqtt.conf"])
    if os.getenv('EVC_ENABLE')==True and not evcSelfRun.poll()==None:
        logger.error("EVC Self Run loop process died. restarting...")
        os.chdir(PATH)
        logger.critical ("Restarting EVC read loop every "+str(os.getenv('EVC_SELF_RUN_TIMER'))+"s")
        selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
    if os.getenv('EVC_ENABLE')==True and not evcSelfRun.poll()==None:
        logger.error("EVC Self Run loop process died. restarting...")
        os.chdir(PATH)
        logger.critical ("Restarting EVC read loop every "+str(os.getenv('EVC_SELF_RUN_TIMER'))+"s")
        evcSelfRun=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
    if os.getenv('EVC_ENABLE')==True and not evcChargeModeLoop.poll()==None:
        logger.error("EVC Self Run loop process died. restarting...")
        os.chdir(PATH)
        logger.critical ("Restarting EVC chargeMode loop every 60s")
        evcChargeModeLoop=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "chargeMode"])

    #Run jobs for smart target
    schedule.run_pending()
    if exists ("/app/.reboot"):
        logger.critical("Reboot requested... rebooting now")
        os.remove("/app/.reboot")
        exit()
    sleep (60)
