from datetime import datetime, timedelta, timezone, UTC
from os.path import exists
import os, pickle, subprocess, logging,shutil, shlex, schedule
from time import sleep
import json
import zoneinfo
import sys
import requests
import asyncio
from GivTCP.findInvertor import findInvertor
from GivTCP.findEVC import findEVC
from GivTCP.givenergy_modbus_async.client.client import Client
from pymodbus.client.sync import ModbusTcpClient

selfRun={}
mqttClient={}
gunicorn={}
webDash={}
rqWorker={}
redis={}
networks={}
SuperTimezone=""

logging.getLogger("givenergy_modbus_async").setLevel(logging.CRITICAL)

# Check if config directory exists and creates it if not

def palm_job():
    subprocess.Popen(["/usr/local/bin/python3","/app/GivTCP_1/palm_soc.py"])

def validateEVC(HOST):
    logger.debug("Validating "+str(HOST))
    SN=""
    try:
        client = ModbusTcpClient(HOST)
        registers = client.read_holding_registers(97,6)
        if hasattr(registers,"registers"):
            regs=registers.registers
            systime=datetime(regs[0],regs[1],regs[2],regs[3],regs[4],regs[5]).replace(tzinfo=timezone.utc).isoformat()
            #get serial number here now and put in the settings file
            sn_regs = client.read_holding_registers(38,31).registers
            for num in sn_regs:
                if not num==0:
                    SN=SN+chr(num)
            return SN
        else:
            return False
    except:
        e=sys.exc_info()
        logger.error(e)
        return False

async def getInvDeets(HOST):
    try:
        Stats={}
        client=Client(HOST,8899,3)
        await client.connect()
        await client.detect_plant(additional=False)
        await client.close()
        if not client.plant.inverter ==None:
            GEInv=client.plant.inverter
        elif not client.plant.ems ==None:
            GEInv=client.plant.ems
        elif not client.plant.gateway ==None:
            GEInv=client.plant.gateway

        SN= GEInv.serial_number
        gen=GEInv.generation
        model=GEInv.model
        fw=GEInv.arm_firmware_version
        numbats=client.plant.number_batteries

        Stats['Serial_Number']=SN
        Stats['Firmware']=fw
        Stats['Model']=model
        Stats['Generation']=gen
        Stats['Number_of_Batteries']=numbats
        Stats['IP_Address']=HOST
        logger.info(f'Inverter {str(SN)} which is a {str(gen.name.capitalize())} - {str(model.name.capitalize())} with {str(numbats)} batteries has been found at: {str(HOST)}')
        return Stats
    except:
        logger.debug("Gathering inverter details for " + str(HOST) + " failed.")
        return None

def createsettingsjson(inv):
    PATH= "/app/GivTCP_"+str(inv)
    SFILE="/config/GivTCP/allsettings.json"
    logger.debug("Recreating settings.py for invertor "+str(inv))
    with open(SFILE, 'r') as f1:
        setts=json.load(f1)
    if setts["Model_"+str(inv)]=="":
        inverter_type= asyncio.run(getInvDeets(str(setts["invertorIP_"+str(inv)])))
        setts["Model_"+str(inv)]= inverter_type['Model'].name.capitalize()
        with open(SFILE, 'w') as f:
            f.write(json.dumps(setts,indent=4))

    with open(PATH+"/settings.py", 'w') as outp:
        outp.write("class GiV_Settings:\n")
        outp.write("    invertorIP=\""+str(setts["invertorIP_"+str(inv)])+"\"\n")
        outp.write("    serial_number=\""+str(setts["serial_number_"+str(inv)])+"\"\n")
        outp.write("    inverter_type=\""+str(setts["Model_"+str(inv)])+"\"\n")
        outp.write("    MQTT_Address=\""+str(setts["MQTT_Address"])+"\"\n")
        outp.write("    MQTT_Username=\""+str(setts["MQTT_Username"])+"\"\n")
        outp.write("    MQTT_Password=\""+str(setts["MQTT_Password"])+"\"\n")
        outp.write("    MQTT_Port="+str(setts["MQTT_Port"])+"\n")
        outp.write("    MQTT_Retain="+str(setts["MQTT_Retain"]).capitalize()+"\n")
        outp.write("    MQTT_Topic=\""+str(setts["MQTT_Topic"])+"\"\n")
        if isAddon:
            outp.write("    HA_Auto_D=True\n")
            outp.write("    Print_Raw_Registers=True\n")
            outp.write("    MQTT_Output=True\n")
            outp.write("    isAddon=True\n")
        else:
            outp.write("    HA_Auto_D="+str(setts["HA_Auto_D"]).capitalize()+"\n")
            outp.write("    Print_Raw_Registers="+str(setts["Print_Raw_Registers"]).capitalize()+"\n")
            outp.write("    MQTT_Output="+str(setts["MQTT_Output"]).capitalize()+"\n")
            outp.write("    isAddon=False\n")
        outp.write("    ha_device_prefix=\""+str(setts["inverterName_"+str(inv)])+"\"\n")
        outp.write("    Log_Level=\""+str(setts["Log_Level"])+"\"\n")
        outp.write("    Influx_Output="+str(setts["Influx_Output"]).capitalize()+"\n")
        outp.write("    influxURL=\""+str(setts["influxURL"])+"\"\n")
        outp.write("    influxToken=\""+str(setts["influxToken"])+"\"\n")
        outp.write("    influxBucket=\""+str(setts["influxBucket"])+"\"\n")
        outp.write("    influxOrg=\""+str(setts["influxOrg"])+"\"\n")
        outp.write("    first_run_evc= True\n")
        outp.write("    self_run_timer="+str(setts["self_run_timer"])+"\n")
        outp.write("    self_run_timer_full="+str(setts["self_run_timer_full"])+"\n")
        outp.write("    queue_retries="+str(setts["queue_retries"])+"\n")
        outp.write("    givtcp_instance="+str(inv)+"\n")
        outp.write("    default_path=\""+str(PATH)+"\"\n")
        outp.write("    dynamic_tariff="+str(setts["dynamic_tariff"]).capitalize()+"\n")
        outp.write("    day_rate="+str(setts["day_rate"])+"\n")
        outp.write("    night_rate="+str(setts["night_rate"])+"\n")
        outp.write("    export_rate="+str(setts["export_rate"])+"\n")
        outp.write("    day_rate_start=\""+str(setts["day_rate_start"])+"\"\n")
        outp.write("    night_rate_start=\""+str(setts["night_rate_start"])+"\"\n")
        outp.write("    data_smoother=\""+str(setts["data_smoother"])+"\"\n")
        outp.write("    cache_location=\"/config/GivTCP\"\n")
        outp.write("    Debug_File_Location=\"/config/GivTCP/log_inv_"+str(inv)+".log\"\n")
        outp.write("    Debug_File_Location_Write=\"/config/GivTCP/write_log_inv_"+str(inv)+".log\"\n")
        outp.write("    inverter_num=\""+str(inv)+"\"\n")
        outp.write("    Smart_Target="+str(setts["dynamic_tariff"]).capitalize()+"\n")
        outp.write("    GE_API=\""+str(setts["GE_API"])+"\"\n")
        outp.write("    PALM_WINTER=\""+str(setts["PALM_WINTER"])+"\"\n")
        outp.write("    PALM_SHOULDER=\""+str(setts["PALM_SHOULDER"])+"\"\n")
        outp.write("    PALM_MIN_SOC_TARGET=\""+str(setts["PALM_MIN_SOC_TARGET"])+"\"\n")
        outp.write("    PALM_MAX_SOC_TARGET=\""+str(setts["PALM_MAX_SOC_TARGET"])+"\"\n")
        outp.write("    PALM_BATT_RESERVE=\""+str(setts["PALM_BATT_RESERVE"])+"\"\n")
        outp.write("    PALM_BATT_UTILISATION=\""+str(setts["PALM_BATT_UTILISATION"])+"\"\n")
        outp.write("    SOLCASTAPI=\""+str(setts["SOLCASTAPI"])+"\"\n")
        outp.write("    SOLCASTSITEID=\""+str(setts["SOLCASTSITEID"])+"\"\n")
        outp.write("    SOLCASTSITEID2=\""+str(setts["SOLCASTSITEID2"])+"\"\n")
        outp.write("    PALM_WEIGHT=\""+str(setts["PALM_WEIGHT"])+"\"\n")
        outp.write("    LOAD_HIST_WEIGHT=\""+str(setts["LOAD_HIST_WEIGHT"])+"\"\n")

        outp.write("    evc_enable="+str(setts["evc_enable"]).capitalize()+"\n")
        outp.write("    evc_ip_address=\""+str(setts["evc_ip_address"])+"\"\n")
        outp.write("    serial_number_evc=\""+str(setts["serial_number_evc"])+"\"\n")
        outp.write("    evc_self_run_timer="+str(setts["evc_self_run_timer"])+"\n")
        outp.write("    evc_import_max_current="+str(setts["evc_import_max_current"])+"\n")
        if SuperTimezone: outp.write("    timezone=\""+str(SuperTimezone)+"\"\n")

def findinv(networks):
    inverterStats={}
    invList={}
    evclist={}
    if len(networks)>0:
    # For each interface scan for inverters
        logger.debug("Networks available for scanning are: "+str(networks))
        inverterStats={}
        list={}
        logger.info("Scanning network for GivEnergy Devices...")
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
                            sn=validateEVC(evclist[evc])
                            if sn:
                                logger.info("GivEVC "+str(sn)+" found at: "+str(evclist[evc]))
                                evclist[evc]=[evclist[evc],sn]
                            else:
                                logger.debug(evclist[evc]+" is not an EVC")
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
                                    deets=asyncio.run(getInvDeets(invList[inv]))
                                    if deets:
                                        inverterStats[inv]=deets
                                        break   #If we found the deets then don't try again
                                    count=count+1
                                else:
                                    break
                    if len(invList)==0:
                        logger.info("No inverters found...")
                    else:
                    # write data to pickle
                        with open('invippkl.pkl', 'wb') as outp:
                            pickle.dump(inverterStats, outp, pickle.HIGHEST_PROTOCOL)
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("Error scanning for Inverters- "+str(e))
    else:
        logger.error("Unable to get host details from Supervisor / Container")
    return inverterStats, invList, evclist

###############################
#                             #
#    Start of Startup Script  #
#                             #
###############################

# Create GivTCP config folder in case it doesn't exist
os.makedirs(os.path.dirname("/config/GivTCP/"),exist_ok=True)

from logging.handlers import TimedRotatingFileHandler
logging.basicConfig(format='%(asctime)s - Startup'+ \
                    ' - %(module)-11s -  [%(levelname)-8s] - %(message)s')
formatter = logging.Formatter(
    '%(asctime)s - %(module)s - [%(levelname)s] - %(message)s')
fh = TimedRotatingFileHandler("/config/GivTCP/startup.log", when='midnight', backupCount=7)
fh.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(fh)
logger.setLevel(logging.INFO)


SuperTimezone={}        # 02-Aug-23  default it to None so that it is defined for saving in settngs.py for non-HA usage (otherwise exception)
logger.info("==================== STARTING GivTCP==========================")
try:
    logger.debug("SUPERVISOR_TOKEN is: "+ os.getenv("SUPERVISOR_TOKEN"))
    isAddon=True
    access_token = os.getenv("SUPERVISOR_TOKEN")
except:
    logger.debug("SUPERVISOR TOKEN does not exist")
    isAddon=False
    hasMQTT=False
    SuperTimezone=False

hostIP=""
if isAddon:
    #Get MQTT Details
    url="http://supervisor/services/mqtt"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    mqttDetails=result.json()
    if mqttDetails['result']=="ok":
        logger.debug ("HA MQTT Service has been found at "+str(mqttDetails['data']['host']))
        mqtt_host=mqttDetails['data']['host']
        mqtt_username=mqttDetails['data']['username']
        mqtt_password=mqttDetails['data']['password']
        mqtt_port=mqttDetails['data']['port']
        hasMQTT=True
    else:
        hasMQTT=False
        logger.info("No HA MQTT service has been found. Install and run the Mosquitto addon, or manually configure your own MQTT broker.")

    #Get Timezone
    url="http://supervisor/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    info=result.json()
    SuperTimezone=info['data']['timezone']
    logger.debug("Supervisor Timezone: "+str(SuperTimezone))

    #Get addonslug/ingress url
    url="http://supervisor/addons/self/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    baseurl=result.json()['data']['ingress_url']
    logger.debug("Ingress URL is: "+str(baseurl))

    #Get Host Details
    url="http://supervisor/network/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    hostDetails=result.json()
    i=0
    for interface in hostDetails['data']['interfaces']:
        if not interface['ipv4']['address'] == []:
            logger.debug("ipv4 Interface= "+str(interface['ipv4']['address']))
            ip=str(interface['ipv4']['address']).split('/')[0][2:]
            mask=str(interface['ipv4']['address']).split('/')[1][:-2]
            hostIP=ip
            networks[i]=interface['ipv4']['gateway']+"/"+str(mask)
            logger.debug("Network Found: "+str(networks[i]))
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
        networks[0]=IP+"/24"
        hostIP=IP
        baseurl="/"
    except:
        e=sys.exc_info()
        logger.error("Could not get network info: "+ str(e))
logger.debug("Host IP Address is: "+str(hostIP))


sleep(2)        # Sleep to allow port scanning socket to close

#write ingress data to json file for config page to use
with open('/app/ingress/hostip.json', 'w') as f:
    f.write(json.dumps(hostIP,indent=4))
with open('/app/ingress/ingressurl.json', 'w') as f:
    f.write(json.dumps(baseurl,indent=4))

finv={}
i=0
while len(finv)==0:
    logger.info("Searching for Inverters")
    finv=findinv(networks)
    i=i+1
    if i==3:
        break
inverterStats=finv[0]
invList=finv[1]
evcList=finv[2]

if len(invList)==0:
    logger.error("=============================================================")
    logger.error("====               NO INVERTERS FOUND                    ====")
    logger.error("====      add manually using a file editor to modify     ====")
    logger.error("====          /config/GivTCP/allsettings.json            ====")
    logger.error("=============================================================")

logger.debug("GivTCP isAddon: "+str(isAddon))

redis=subprocess.Popen(["/usr/bin/redis-server","/app/redis.conf"])
logger.debug("Running Redis")

if not exists("/ssl/fullchain.pem"):
    shutil.copy("/app/ingress_no_ssl.conf","/etc/nginx/http.d/ingress.conf")

subprocess.Popen(["nginx","-g","daemon off;"])
logger.debug("Running nginx")


PATH= "/app/GivTCP_"
SFILE="/config/GivTCP/allsettings.json"
v3upgrade=False      #Check if its a new upgrade or already has new json config file
if not exists(SFILE):
    v3upgrade=True
    logger.debug("Copying in a template settings.json to: "+str(SFILE))
    shutil.copyfile("settings.json",SFILE)
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


# Update json object with found data
logger.debug ("Creating master allsettings.json for all inverters.")
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
if setts["Host_IP"]=="": setts["Host_IP"]=hostIP

for inv in inverterStats:
    logger.debug("Using found Inverter data to autosetup settings.json")
    # Check if serial number is already here and only update if IP address has changed
    if not inverterStats[inv]['Serial_Number'] in [setts["serial_number_1"],setts["serial_number_2"],setts["serial_number_3"],setts["serial_number_4"],setts["serial_number_5"]]:
        # find next empty slot and populate with details
        logger.info("Inverter "+ str(inverterStats[inv]['Serial_Number'])+ " not in settings file")
        for num in range(1,6):
            if setts["invertorIP_"+str(num)]=="":
                logger.info("Adding Inverter "+ str(inverterStats[inv]['Serial_Number'])+ " to slot "+ str(num))
                setts["invertorIP_"+str(num)]=inverterStats[inv]['IP_Address']
                setts["serial_number_"+str(num)]=inverterStats[inv]['Serial_Number']
                setts["inverter_enable_"+str(num)]=True             #If found for the first time, auto enable (but not if already there incase user has disabled)
                break
    else:
        for num in range(1,6):
            if inverterStats[inv]['Serial_Number'] == setts["serial_number_"+str(num)]:
                logger.debug("Inverter "+ str(inverterStats[inv]['Serial_Number'])+ " already found in settings file (slot "+str(num)+"), checking IP address is unchanged...")
                if not setts["invertorIP_"+str(num)] == inverterStats[inv]['IP_Address']:
                    #If IP has changed, update it
                    logger.info("Inverter "+ str(inverterStats[inv]['Serial_Number'])+ " IP Address is different, updating: "+str(setts["invertorIP_"+str(num)])+" -> "+str(inverterStats[inv]['IP_Address']))
                    setts["invertorIP_"+str(num)]=inverterStats[inv]['IP_Address']
                break
    setts['Model_'+str(inv)]=inverterStats[inv]['Model'].name.capitalize()


if len(evcList)>0:
    logger.debug("evcList: "+str(evcList))
    if setts["evc_ip_address"]=="":
        setts["evc_ip_address"]=evcList[1][0]
    if setts["serial_number_evc"]=="":
        setts["serial_number_evc"]=evcList[1][1]

## Get legacy settings if they exist
if exists("/config/GivTCP/v2env.pkl") and v3upgrade:
    logger.info("v2 settings found, importing into v3...")
    with open('/config/GivTCP/v2env.pkl','rb') as inp:
        envs=pickle.load(inp)
    #logger.info("Version 2 settings found, importing into new settings")
    v2invertersettings=[]
    for inv in envs[1]:
        invertersett={}
        num=int(envs[0]['NUMINVERTORS'])
        for inv2 in range(1,num+1):
            if envs[0]['INVERTOR_IP_'+str(inv)]==envs[1][inv]['IP_Address']:
                invertersett['IP_Address']=envs[1][inv]['IP_Address']
                invertersett['Serial_Number']=envs[1][inv]['Serial_Number']
                if inv==1:
                    invertersett['Prefix']=envs[0]['HADEVICEPREFIX']
                else:
                    invertersett['Prefix']=envs[0]['HADEVICEPREFIX_'+str(inv)]
        v2invertersettings.append(invertersett)
    setts["GE_API"]=envs[0]["GEAPI"]
    setts["PALM_WINTER"]=envs[0]["PALM_WINTER"]
    setts["PALM_SHOULDER"]=envs[0]["PALM_SHOULDER"]
    setts["PALM_MIN_SOC_TARGET"]=envs[0]["PALM_MIN_SOC_TARGET"]
    setts["PALM_MAX_SOC_TARGET"]=envs[0]["PALM_MAX_SOC_TARGET"]
    setts["PALM_BATT_RESERVE"]=envs[0]["PALM_BATT_RESERVE"]
    setts["PALM_BATT_UTILISATION"]=envs[0]["PALM_BATT_UTILISATION"]
    setts["SOLCASTAPI"]=envs[0]["SOLCASTAPI"]
    setts["SOLCASTSITEID"]=envs[0]["SOLCASTSITEID"]
    setts["SOLCASTSITEID2"]=envs[0]["SOLCASTSITEID2"]
    setts["PALM_WEIGHT"]=envs[0]["PALM_WEIGHT"]
    setts["LOAD_HIST_WEIGHT"]=envs[0]["LOAD_HIST_WEIGHT"]
    setts["dynamic_tariff"]=envs[0]["DYNAMICTARIFF"]
    setts["day_rate"]=envs[0]["DAYRATE"]
    setts["night_rate"]=envs[0]["NIGHTRATE"]
    setts["export_rate"]=envs[0]["EXPORTRATE"]
    setts["day_rate_start"]=envs[0]["DAYRATESTART"]
    setts["night_rate_start"]=envs[0]["NIGHTRATESTART"]
    setts["influxURL"]=envs[0]["INFLUX_URL"]
    setts["influxToken"]=envs[0]["INFLUX_TOKEN"]
    setts["influxBucket"]=envs[0]["INFLUX_BUCKET"]
    setts["influxOrg"]=envs[0]["INFLUX_ORG"]
    setts["self_run"]=True
    setts['evc_enable']=bool(envs[0]["EVC_ENABLE"])
    setts['evc_self_run_timer']=envs[0]["EVC_SELF_RUN_TIMER"]

    ## Match HAPREFIX to inverterIP
    for num in range(1,6):
        for inv in range(0, len(v2invertersettings)):
            if setts["invertorIP_"+str(num)]==v2invertersettings[inv]['IP_Address']:
                setts["inverterName_"+str(num)]=v2invertersettings[inv]["Prefix"]


with open(SFILE, 'w') as f:
    f.write(json.dumps(setts,indent=4))

# Now its written to config folder, symlink to ingress so web frontend can deal with it
src=SFILE
dest="/app/ingress/allsettings.json"
if not exists(dest):
    os.symlink(src, dest)

if not exists(str(setts["cache_location"])):
    os.makedirs(str(setts["cache_location"]))
    logger.debug("No config directory exists, so creating it...")
else:
    logger.debug("Config directory already exists")

runninginv=[]

# Change this to only use those inverters set to enabled in settings (INDENT)
for inv in range(1,6):
    if setts['inverter_enable_'+str(inv)]==True:
        #Set up v3upgrade file
        if v3upgrade:
            logger.info("v3 upgrade detected...")
            open('/config/GivTCP/.v3upgrade_'+str(inv), 'w').close()
        runninginv.append(inv)
        logger.info ("Setting up invertor: "+str(inv))
        PATH= "/app/GivTCP_"+str(inv)
    #    SFILE="/config/GivTCP/settings"+str(inv)+".json"
        firstrun="/config/GivTCP/.firstrun_"+str(inv)

        # Create folder per instance
        if not exists(PATH):
            shutil.copytree("/app/GivTCP", PATH)
        logger.debug("Copying in a template settings.json")
        shutil.copyfile("/app/settings.json",PATH+"/settings.json")
        # Remove old settings file
        if exists(PATH+"/settings.py"):
            os.remove(PATH+"/settings.py")
        if exists(firstrun):
            logger.debug("Removing firstrun")
            os.remove(firstrun)

        createsettingsjson(inv)

        ######
        #  Always delete lockfiles and FCRunning etc... but only delete pkl if too old?
        for file in os.listdir(setts["cache_location"]):
            filename = os.fsdecode(file)
            if not filename.__contains__("log") and not filename.startswith("rateData") and not filename.startswith(".dayRate") and not filename.startswith(".nightRate") and not filename.startswith("allsettings") and not filename.startswith("v2env") and not filename.startswith(".v3upgrade"):
                os.remove(setts['cache_location']+"/"+file)
        if exists(setts["cache_location"]+"/rateData_"+str(inv)+".pkl"):
            if "TZ" in os.environ:
                timezone=zoneinfo.ZoneInfo(key=setts["TZ"])
            else:
                timezone=zoneinfo.ZoneInfo(key="Europe/London")
            modDay= datetime.fromtimestamp(os.path.getmtime(setts["cache_location"]+"/rateData_"+str(inv)+".pkl")).date()
            if modDay<datetime.now(timezone).date():
                logger.debug("Old rate data cache not updated today, so deleting")
                os.remove(str(setts["cache_location"])+"/rateData_"+str(inv)+".pkl")
            else:
                logger.debug("Rate Data exists but is from today so keeping it")

        #####################################################
        #         Run the various processes needed          #
        # Check if settings.py exists then start processes  #
        # Still need to run the below process per inverter  #
        #####################################################
        logger.info("==============================================================")
        logger.info("====             Web Gui Config is at                     ====")
        logger.info("====     http://"+str(hostIP)+":8099/config.html             ====")
        if not setts['self_run']==True:
            logger.info("====  Self Run is off, so no data collection is happening ====")
            logger.info("====     Log into Web Gui and complete startup settings   ====")
        logger.info("==============================================================")

        os.chdir(PATH)

        rqWorker[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/worker.py"])
        logger.debug("Running RQ worker to queue and process resume calls")

        if not hasMQTT and setts['MQTT_Address']=="127.0.0.1" and setts['MQTT_Output']==True:
            logger.info ("Starting Mosquitto on port "+str(setts['MQTT_Port']))
            mqttBroker=subprocess.Popen(["/usr/sbin/mosquitto", "-c",PATH+"/mqtt.conf"])

        if setts['self_run']==True: # Don't autorun if isAddon to prevent autostart creating rubbish before its checked by a user
            logger.info ("Running Invertor "+str(inv)+" ("+str(setts["serial_number_"+str(inv)])+") read loop every "+str(setts['self_run_timer'])+"/"+str(setts['self_run_timer_full'])+"s")
            selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "start"])


        GUPORT=6344+inv
        logger.debug ("Starting Gunicorn on port "+str(GUPORT))
        command=shlex.split("/usr/local/bin/gunicorn -w 3 -b :"+str(GUPORT)+" REST:giv_api")
        gunicorn[inv]=subprocess.Popen(command)

if setts['evc_enable']==True:
    if not setts['evc_ip_address']=="":
        logger.info ("Running EVC read loop every "+str(setts['evc_self_run_timer'])+"s")
        evcSelfRun=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
        evcChargeModeLoop=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "chargeMode"])
        logger.debug ("Setting chargeMode loop to manage different charge modes every 60s")
    else:
        logger.info("EVC IP is missing from config. Please update and restart GivTCP")


if setts['Web_Dash']==True:
    # Create app.json
    logger.debug("Creating web dashboard config")
    os.chdir("/app/WebDashboard")
    with open("app.json", 'w') as outp:
        outp.write("{\n")
        outp.write("  \"givTcpHosts\": [\n")

        for inv in runninginv:
            GUPORT = 6344 + inv
            if inv > 1:
                outp.write("  ,{\n")
            else:
                outp.write("  {\n")
            outp.write("    \"name\": \""+setts['inverterName_'+str(inv)]+"\",\n")
            outp.write("    \"port\": \""+str(GUPORT)+"\"\n")
            outp.write("  }\n")

        outp.write("  ],\n")
        outp.write("  \"solarRate\": "+str(setts['day_rate'])+",\n")
        outp.write("  \"exportRate\": "+str(setts['export_rate'])+"\n")
        outp.write("}")

    WDPORT=int(setts['Web_Dash_Port'])
    logger.info (f"Serving Web Dashboard from port {WDPORT}")
    with open("/etc/nginx/http.d/webdashboard.conf", 'w') as wd:
        wd.write("server {\n")
        wd.write(f"\tlisten {WDPORT};\n")
        wd.write("\tlocation / {\n")
        wd.write("\t\troot /app/WebDashboard;\n")
        wd.write("\t\tindex index.html;\n\n")
        wd.write("\t\ttry_files $uri $uri/ =404;\n")
        wd.write("\t}\n")
        wd.write("}\n")

    # reload nginx to pick up the new conf
    subprocess.Popen(["nginx","-s","reload", "-c", "/etc/nginx/nginx.conf"])


if setts['Smart_Target']==True:
    starttime= datetime.strftime(datetime.strptime(setts['night_rate_start'],'%H:%M') - timedelta(hours=0, minutes=10),'%H:%M')
    logger.info("Setting daily charge target forecast job to run at: "+starttime)
    schedule.every().day.at(starttime).do(palm_job)

# Loop round checking all processes are running
while True:
    try:
        for inv in runninginv:
            #regCacheStack=get_regcache(setts['cache_location']+"/regCache_"+str(inv)+".pkl",inv)
            if exists(setts['cache_location']+"/lastUpdate_"+str(inv)+".pkl"):
                with open(setts['cache_location']+"/lastUpdate_"+str(inv)+".pkl", 'rb') as inp:
                    previousUpdate = pickle.load(inp)
                    timediff = datetime.now(UTC) - datetime.fromisoformat(previousUpdate)
                    timesince=(((timediff.seconds*1000000)+timediff.microseconds)/1000000)
                    logger.debug("timesince last read= "+str(timesince))
            else:
                sleep(10)       #wait for first regcache then go back round loop
                continue
            PATH= "/app/GivTCP_"+str(inv)
            if setts['self_run']==True:
                if not selfRun[inv].poll()==None:
                    selfRun[inv].kill()
                    logger.error("Self Run loop process died. restarting...")
                    os.chdir(PATH)
                    logger.info ("Restarting Invertor read loop every "+str(setts['self_run_timer'])+"s")
                    selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "start"])
                elif timesince>(float(setts['self_run_timer'])*5):
                    logger.error("Self Run loop process stuck. Killing and restarting...")
                    os.chdir(PATH)
                    selfRun[inv].kill()
                    logger.info ("Restarting Invertor read loop every "+str(setts['self_run_timer'])+"s")
                    selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "start"])
            if not gunicorn[inv].poll()==None:
                gunicorn[inv].kill()
                logger.error("REST API process died. Restarting...")
                os.chdir(PATH)
                GUPORT=6344+inv
                logger.info ("Starting Gunicorn on port "+str(GUPORT))
                command=shlex.split("/usr/local/bin/gunicorn -w 3 -b :"+str(GUPORT)+" REST:giv_api")
                gunicorn[inv]=subprocess.Popen(command)

        if setts['MQTT_Address']=="127.0.0.1":
            if not mqttBroker.poll()==None:
                mqttBroker.kill()
                logger.error("MQTT Broker process died. Restarting...")
                os.chdir(PATH)
                logger.info ("Starting Mosquitto on port "+str(setts['MQTT_Port']))
                mqttBroker=subprocess.Popen(["/usr/sbin/mosquitto", "-c",PATH+"/mqtt.conf"])

        if setts['evc_enable']==True:
            if not evcSelfRun.poll()==None:
                evcSelfRun.kill()
                logger.error("EVC Self Run loop process died. restarting...")
                os.chdir(PATH)
                logger.info ("Restarting EVC read loop every "+str(setts['evc_self_run_timer'])+"s")
                selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
            if not evcChargeModeLoop.poll()==None:
                evcChargeModeLoop.kill()
                logger.error("EVC Self Run loop process died. restarting...")
                os.chdir(PATH)
                logger.info ("Restarting EVC chargeMode loop every 60s")
                evcChargeModeLoop=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "chargeMode"])

        ## Could we run a periodic Time Sync check? Maybe a config item??
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("Error in watchdog loop: "+str(e))

    #Run jobs for smart target
    schedule.run_pending()
    sleep (60)
