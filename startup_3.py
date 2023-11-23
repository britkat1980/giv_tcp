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
import json

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
logger.setLevel(logging.INFO)
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
        logger.error(e)
        return False
    
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
    return inverterStats, invList, evcList
    
def isitoldfw(invstats):
    '''Firmware Versions for each Model
    AC coupled 5xx old, 2xx new. 28x, 29x beta
    Gen1 4xx Old, 1xx New. 19x Beta
    Gen 2 909+ New. 99x Beta   Schedule Pause only for Gen2+
    Gen 3 303+ New 39x Beta    New has 10 slots
    AIO 6xx New 69x Beta       ALL has 10 slots'''
    if invstats['Model']=='AC' and int(invstats['Firmware'])>500:
        return True
    elif invstats['Model']=='AIO' and int(invstats['Firmware'])>600:
        return True
    elif invstats['Generation']=='Gen 1' and int(invstats['Firmware'])<400:
        return True
    elif invstats['Generation']=='Gen 2' and int(invstats['Firmware'])<908:
        return True
    elif invstats['Generation']=='Gen 3' and int(invstats['Firmware'])<302:
        return True
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

SuperTimezone={}        # 02-Aug-23  default it to None so that it is defined for saving in settngs.py for non-HA usage (otherwise exception)

try:
    logger.debug("SUPERVISOR_TOKEN is: "+ os.getenv("SUPERVISOR_TOKEN"))
    isAddon=True
    access_token = os.getenv("SUPERVISOR_TOKEN")
except:
    logger.debug("SUPERVISOR TOKEN does not exist")
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
        logger.debug("No HA MQTT service has been found")

    #Get Timezone    
    url="http://supervisor/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    info=result.json()
    SuperTimezone=info['data']['timezone']
    logger.debug("Supervisor Timezone: "+str(SuperTimezone))

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

sleep(2)        # Sleep to allow port scanning socket to close

finv=findinv(networks)
inverterStats=finv[0]
invList=finv[1]
evcList=finv[2]

logger.debug("GivTCP isAddon: "+str(isAddon))


#rqdash=subprocess.Popen(["/usr/local/bin/rq-dashboard","-u redis://127.0.0.1:6379"])
#logger.critical("Running RQ Dashboard on port 9181")

#vueConfig=subprocess.Popen(["npm", "run", "dev","-- --host --silent"],cwd="/app/config_frontend")
#logger.debug("Running Config Frontend")


#shutil.copytree("/app/config_frontend/dist", '/usr/share/nginx/html')
subprocess.Popen(["nginx","-g","daemon off;error_log /dev/stdout debug;"])

##########################################################################################################
#
#
#   Up to now everything is __init__ type prep, below is conifg setting (move to webpage and not ENV...) #
#   
#   is there a json settings file already?
#   if not then copy in new one and pre-populate the known info (IP, MQTT etc...)
#   check if mandatory info is in place 
#   if not dont load other services. wait for settings file to be updated...
#   if yes then load other services
#   
# 
##########################################################################################################

redis=subprocess.Popen(["/usr/bin/redis-server","/app/redis.conf"])
logger.debug("Running Redis")

if not os.path.exists("/config/GivTCP"):
    os.makedirs("/config/GivTCP")
    logger.debug("No config directory exists, so creating it...")
else:
    logger.debug("Config directory already exists")

for inv in range(1,int(os.getenv('NUMINVERTORS'))+1):
    logger.debug ("Setting up invertor: "+str(inv)+" of "+str(os.getenv('NUMINVERTORS')))
    PATH= "/app/GivTCP_"+str(inv)
    PATH2= "/app/GivEnergy-Smart-Home-Display-givtcp_"+str(inv)
    SFILE="/config/GivTCP/settings"+str(inv)+".json"

    # Create folder per instance
    if not exists(PATH):
        logger.debug("Local instance folder doesn't exist")
        shutil.copytree("/app/GivTCP", PATH)
        shutil.copytree("/app/GivEnergy-Smart-Home-Display-givtcp", PATH2)
    
    if not exists(SFILE):
        logger.debug("Copying in a template settings.json to: "+str(SFILE))
        shutil.copyfile("/app/settings.json",SFILE)
    else:
        # If theres already a settings file, make sure its got any new elements
        with open(SFILE, 'r') as f1:
            setts=json.load(f1)
        with open("/app/settings.json", 'r') as f2:
            templatesetts=json.load(f2)
        for setting in templatesetts:
            if not setting in setts:
                setts[setting]=templatesetts[setting]
        with open(SFILE, 'w') as f:
            f.write(json.dumps(setts,indent=4))
        
    
    # Remove old settings file
    if exists(PATH+"/settings.py"):
        os.remove(PATH+"/settings.py")

    # Update json object with found data
    logger.debug ("Recreating settings.py for invertor "+str(inv))
    with open(SFILE, 'r') as f:
        setts=json.load(f)
        if SuperTimezone: setts["TZ"]=str(SuperTimezone)
        if hasMQTT:
            logger.debug("Using found MQTT data to autosetup settings.json")
            setts["MQTT_Output"]=True
            # Only autosetup if there's not already a setting, to stop overriding manual setup
            if setts["MQTT_Address"]=="": setts["MQTT_Address"]=mqtt_host
            if setts["MQTT_Username"]=="": setts["MQTT_Username"]=mqtt_username
            if setts["MQTT_Password"]=="": setts["MQTT_Password"]=mqtt_password
            setts["MQTT_Port"]=mqtt_port
        if setts["MQTT_Address"]=="": setts['MQTT_Output']=False
        if len(invList)>0:
            logger.debug("Using found Inverter data to autosetup settings.json")
            if setts["invertorIP"]=="": setts["invertorIP"]=invList[inv]
            if setts["invertorIP"]=="": setts["serial_number"]=inverterStats[inv]['Serial_Number']
        if setts["invertorIP"]=="": setts['self_run']=False
        setts["Debug_File_Location"]=setts["cache_location"]+"/log_inv_"+str(inv)+".log"
        setts["givtcp_instance"]=inv
        setts["default_path"]=PATH
        setts["first_run"]=True
        setts["first_run_evc"]=True
        setts["inverter_num"]=inv
        if len(evclist)>0:
            setts["evc_ip_address"]=evclist[1]
            setts["evc_enable"]=True
        if len(inverterStats)>0:
            if inverterStats[inv]['Model']=="All in One":
                setts['isAIO']=True
            else:
                setts['isAIO']=False
            if isitoldfw(inverterStats[inv]):
                setts['isAC']=True
            else:
                setts['isAC']=False

    with open(SFILE, 'w') as f:
        f.write(json.dumps(setts,indent=4))

    # create settings file
    with open(PATH+"/settings.py", 'w') as outp:
        outp.write("class GiV_Settings:\n")
        for setting in setts:
            if type(setts[setting]) is str:
                outp.write("    "+setting+"=\""+setts[setting]+"\"\n")
            else:
                outp.write("    "+setting+"="+str(setts[setting])+"\n")
        

    ######
    #  Always delete lockfiles and FCRunning etc... but only delete pkl if too old?

    if exists(setts["cache_location"]+"/regCache_"+str(inv)+".pkl"):
        logger.debug("Removing old invertor data cache")
        os.remove(str(setts["cache_location"])+"/regCache_"+str(inv)+".pkl")
    if exists(PATH+"/.lockfile"):
        logger.debug("Removing old .lockfile")
        os.remove(PATH+"/.lockfile")
    if exists(PATH+"/.FCRunning"):
        logger.debug("Removing old .FCRunning")
        os.remove(PATH+"/.FCRunning")
    if exists(PATH+"/.FERunning"):
        logger.debug("Removing old .FERunning")
        os.remove(PATH+"/.FERunning")
    if exists(setts["cache_location"]+"/battery_"+str(inv)+".pkl"):
        logger.debug("Removing old battery data cache")
        os.remove(str(setts["cache_location"])+"/battery_"+str(inv)+".pkl")
    if exists(setts["cache_location"]+"/rateData_"+str(inv)+".pkl"):
        if "TZ" in setts:
            timezone=zoneinfo.ZoneInfo(key=setts["TZ"])
        else:
            timezone=zoneinfo.ZoneInfo(key="Europe/London")
        modDay= datetime.fromtimestamp(os.path.getmtime(setts["cache_location"]+"/rateData_"+str(inv)+".pkl")).date()
        if modDay<datetime.now(timezone).date():
            logger.debug("Old rate data cache not updated today, so deleting")
            os.remove(str(setts["cache_location"])+"/rateData_"+str(inv)+".pkl")
        else:
            logger.debug("Rate Data exisits but is from today so keeping it")


########### Run the various processes needed #############
#   Check if settings.py exists then start processes
#   Still need to run the below process per inverter
##########################################################
    os.chdir(PATH)

    rqWorker[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/worker.py"])
    logger.debug("Running RQ worker to queue and process givernergy-modbus calls")

    if not hasMQTT and setts['MQTT_Address']=="127.0.0.1" and setts['MQTT_Output']==True:
        logger.critical ("Starting Mosquitto on port "+str(setts['MQTT_Port']))
        mqttBroker=subprocess.Popen(["/usr/sbin/mosquitto", "-c",PATH+"/mqtt.conf"])

    if setts['self_run']==True or isAddon:
        if not setts['invertorIP']=="":
            logger.critical ("Running Invertor read loop every "+str(setts['self_run_timer'])+"s")
            selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "self_run2"])
        else:
            logger.error("Inverter IP is missing from config. Please update and restart GivTCP")

    if setts['evc_enable']==True and inv==1:  #only run it once
        if not setts['evc_ip_address']=="":
            logger.critical ("Running EVC read loop every "+str(setts['evc_self_run_timer'])+"s")
            evcSelfRun=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
            logger.debug ("Subscribing MQTT Broker for EVC control")
            mqttClientEVC=subprocess.Popen(["/usr/local/bin/python3",PATH+"/mqtt_client_evc.py"])
            evcChargeModeLoop=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "chargeMode"])
            logger.debug ("Setting chargeMode loop to manage different charge modes every 60s")
        else:
            logger.error("EVC IP is missing from config. Please update and restart GivTCP")

    if setts['MQTT_Output']==True or isAddon:
        if not setts['MQTT_Address']=="":
            logger.debug ("Subscribing MQTT Broker for control")
            mqttClient[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/mqtt_client.py"])
        else:
            logger.debug("MQTT broker IP address is missing from config. Please update and restart GivTCP")

    
    GUPORT=6344+inv
    logger.debug ("Starting Gunicorn on port "+str(GUPORT))
    command=shlex.split("/usr/local/bin/gunicorn -w 3 -b :"+str(GUPORT)+" REST:giv_api")
    gunicorn[inv]=subprocess.Popen(command)
    
    os.chdir(PATH2)
    if setts['Web_Dash']==True and not setts['Host_IP']=="":
        # Create app.json
        logger.debug ("Creating web dashboard config")
        with open(PATH2+"/app.json", 'w') as outp:
            outp.write("{\n")
            outp.write("\"givTcpHostname\": \""+setts['Host_IP']+":6345\",")
            outp.write("\"solarRate\": "+setts['day_rate']+",")
            outp.write("\"exportRate\": "+setts['export_rate']+"")
            outp.write("}")
        WDPORT=int(setts['Web_Dash_Port'])-1+inv
        logger.critical ("Serving Web Dashboard from port "+str(WDPORT))
        command=shlex.split("/usr/bin/node /usr/local/bin/serve -p "+ str(WDPORT))
        webDash[inv]=subprocess.Popen(command)

if setts['Smart_Target']==True:
    starttime= datetime.strftime(datetime.strptime(setts['night_rate_start'],'%H:%M') - timedelta(hours=0, minutes=10),'%H:%M')
    logger.critical("Setting daily charge target forecast job to run at: "+starttime)
    schedule.every().day.at(starttime).do(palm_job)

# Loop round checking all processes are running
while True:
    for inv in range(1,int(os.getenv('NUMINVERTORS'))+1):
        try:
            PATH= "/app/GivTCP_"+str(inv)
            if setts['self_run']==True and not selfRun[inv].poll()==None:
                logger.error("Self Run loop process died. restarting...")
                os.chdir(PATH)
                logger.error ("Restarting Invertor read loop every "+str(setts['self_run_timer'])+"s")
                selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "self_run2"])
            if setts['MQTT_Output']==True and not mqttClient[inv].poll()==None:
                logger.error("MQTT Client process died. Restarting...")
                os.chdir(PATH)
                logger.error ("Resubscribing Mosquitto for control on port "+str(setts['MQTT_Port']))
                mqttClient[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/mqtt_client.py"])
            if setts['Web_Dash']==True and not webDash[inv].poll()==None:
                logger.error("Web Dashboard process died. Restarting...")
                os.chdir(PATH2)
                WDPORT=int(setts['Web_Dash_Port'])+inv-1
                logger.error ("Serving Web Dashboard from port "+str(WDPORT))
                command=shlex.split("/usr/bin/node /usr/local/bin/serve -p "+ str(WDPORT))
                webDash[inv]=subprocess.Popen(command)
            if not gunicorn[inv].poll()==None:
                logger.error("REST API process died. Restarting...")
                os.chdir(PATH)
                GUPORT=6344+inv
                logger.error ("Starting Gunicorn on port "+str(GUPORT))
                command=shlex.split("/usr/local/bin/gunicorn -w 3 -b :"+str(GUPORT)+" REST:giv_api")
                gunicorn[inv]=subprocess.Popen(command)
        except:
            logger.error("Some error in the watchdog loop")
    if setts['MQTT_Address']=="127.0.0.1" and not mqttBroker.poll()==None:
        logger.error("MQTT Broker process died. Restarting...")
        os.chdir(PATH)
        logger.error ("Restarting Mosquitto on port "+str(setts['MQTT_Port']))
        mqttBroker=subprocess.Popen(["/usr/sbin/mosquitto", "-c",PATH+"/mqtt.conf"])
    if setts['evc_enable']==True and not evcSelfRun.poll()==None:
        logger.error("EVC Self Run loop process died. restarting...")
        os.chdir(PATH)
        logger.error ("Restarting EVC read loop every "+str(setts['evc_self_run_timer'])+"s")
        evcSelfRun=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
    if setts['evc_enable']==True and not evcChargeModeLoop.poll()==None:
        logger.error("EVC Self Run loop process died. restarting...")
        os.chdir(PATH)
        logger.error ("Restarting EVC chargeMode loop every 60s")
        evcChargeModeLoop=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "chargeMode"])


    #Run jobs for smart target
    schedule.run_pending()
    sleep (60)
