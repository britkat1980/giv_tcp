# -*- coding: utf-8 -*-
# version 2021.12.22
from os.path import exists
import sys
from flask import Flask, request, render_template, Response, send_file
from flask_cors import CORS
import read as rd       #grab passthrough functions from main read file
import write as wr      #grab passthrough functions from main write file
import pickle
from GivLUT import GivLUT
import os
import time
import datetime
import json
from settings import GiV_Settings
from inspect import getmembers, isfunction, getsource
from givenergy_modbus_async.model import TimeSlot

logger = GivLUT.logger
#set-up Flask details
giv_api = Flask(__name__)
CORS(giv_api)

with open("/config/GivTCP/allsettings.json", "r") as inp:
    setts=json.load(inp)
if setts["evc_enable"]==True:
    import evc
#Proxy Read Functions

def requestcommand(command,payload):
    try:
        requests=[]
        if exists(GivLUT.writerequests):
            with open(GivLUT.writerequests,'rb') as inp:
                requests=pickle.load(inp)
        requests.append([command,payload,True])
        with open(GivLUT.writerequests,'wb') as outp:
            pickle.dump(requests, outp, pickle.HIGHEST_PROTOCOL)
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error ("Error in requesting control command: "+str(e))

def response(id: str):
    responses=[]
    starttime=datetime.datetime.now()
    while True:
        time.sleep(0.1)
        if exists(GivLUT.restresponse):
            with GivLUT.restlock:
                with open(GivLUT.restresponse,'r') as inp:
                    responses=json.load(inp)
                for response in responses[:]:
                    logger.debug("Response in file is: "+str(response))
                    if response['id']==id:
                        logger.debug("found REST response")
                        # remove item from responses
                        responses.remove(response)
                        with open(GivLUT.restresponse,'w') as outp:
                            outp.write(json.dumps(responses))
                        return response['result']            
        waittime=datetime.datetime.now()-starttime
        if waittime.total_seconds()>15:
            return "{'result':'Error: REST response timeout. Unknown success'}"


@giv_api.route('/api', methods=['GET'])
def api():
    with open('api.json', 'r') as inp:
        return (json.load(inp))

@giv_api.route('/showdata', methods=['GET'])
def index():
    output=rd.getCache()
    return render_template('showdata.html', title="page", jsonfile=json.dumps(output))

@giv_api.route('/settings', methods=['POST'])
def savesetts():
    """Save settings into json file

    Payload: json object conforming to the settings_template
    """
    
    if exists("/config/GivTCP/allsettings.json"):
        SFILE="/config/GivTCP/allsettings.json"
    else:
        SFILE="/app/allsettings.json"
    setts = request.get_json()
    with open(SFILE, 'w') as f:
        f.write(json.dumps(setts,indent=4))
    return "Settings Updated"

@giv_api.route('/settings', methods=['GET'])
def returnsetts():
    """Return settings from json file
    """
    if exists("/config/GivTCP/allsettings.json"):
        SFILE="/config/GivTCP/allsettings.json"
    else:
        SFILE="/app/allsettings.json"
    with open(SFILE, 'r') as f1:
        setts=json.load(f1)
        return setts

@giv_api.route('/fullCache', methods=['GET'])
def fullcache():
    """Return full cache History as a json file
    """
    output=rd.fullCache()
    filename="regCacheStack_"+str(GiV_Settings.givtcp_instance)+".json"
    with open(filename,'w') as outp:
        outp.write(output)
    if output == None:
        return "{\"Result\":\"Error, no data available\"}"
    else:
        return send_file(filename, download_name=filename, as_attachment=True )
    

@giv_api.route('/runAll', methods=['GET'])
def getAll():
    """Retrieve Last known data from the pkl file cache
    """
    # We need a safe way to do this for REST... just sending cache for now
    #logger.critical("runAll called via REST")
    output=rd.getCache()
    if output == None:
        return "{\"Result\":\"Error, no data available\"}"
    else:
        return output

@giv_api.route('/reboot', methods=['GET','POST'])
def reboot():
    """Restart the Inverter
    """
    requestcommand("rebootinverter")
    return response("rebootinverter")

@giv_api.route('/restart', methods=['GET','POST'])
def restart():
    """Restart the Container/Addon
    """
    output=wr.rebootAddon()
    response=json.dumps({
        "data": {
            "result": "Container restarting..."
        }
    }),
    status=200,
    mimetype="application/json"
    return Response(response)

#Publish last cached Invertor Data
@giv_api.route('/readData', methods=['GET'])
def rdData():
    """GET Last known data from the pkl file cache
    """
    #logger.critical("readData called via REST")
    output=rd.getCache()
    if output == None:
        return "{\"Result\":\"Error, no data available\"}"
    else:
        return output

#Publish last cached Invertor Data
@giv_api.route('/getCache', methods=['GET'])
def gtCache():
    """GET Last known data from the pkl file cache
    """
    #logger.critical("getCache called via REST")
    output=rd.getCache()
    if output == None:
        return "{\"Result\":\"Error, no data available\"}"
    else:
        return output


#Proxy Write Functions
@giv_api.route('/enableChargeTarget', methods=['POST'])
def enChargeTrgt():
    """Enable Target SOC

    Payload: {'state':'enable' or 'disable'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("enableChargeTarget",payload)
    return response("enableChargeTarget")


@giv_api.route('/enableChargeSchedule', methods=['POST'])
def enableChrgSchedule():
    """Enable Charge target schedule

    Payload: {'state':'enable' or 'disable'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("enableChargeSchedule",payload)
    return response("enableChargeSchedule")


@giv_api.route('/enableDischargeSchedule', methods=['POST'])
def enableDischrgSchedule():
    """Enable Discharge target schedule

    Payload: {'state':'enable' or 'disable'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("enableDischargeSchedule",payload)
    return response("enableDischargeSchedule")


@giv_api.route('/enableDischarge', methods=['POST'])
def enableBatDisharge():
    """Enable Battery Discharge

    Payload: {'state':'enable' or 'disable'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("enableDischarge",payload)
    return response("enableDischarge")


### Should this include a slot number and use setChargeTarget2 ###

@giv_api.route('/setChargeTarget', methods=['POST'])
def setChrgTarget():
    """Set Charge target SOC

    Payload: {'chargeToPercent':'45'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setChargeTarget",payload)
    return response("setChargeTarget")


@giv_api.route('/setExportTarget', methods=['POST'])
def setExpTarget():
    """Set Export target SOC by defining which target slot and SOC

    Payload: {'exportToPercent':'45', 'slot':'1'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setExportTarget",payload)
    return response("setExportTarget")


@giv_api.route('/setDischargeTarget', methods=['POST'])
def setDischrgTarget():
    """Set Discharge target SOC by defining which target slot and SOC.

    Payload: {'exportToPercent':'45', 'slot':'1'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setDischargeTarget",payload)
    return response("setDischargeTarget")


@giv_api.route('/setBatteryReserve', methods=['POST'])
def setBattReserve():
    """Set Battery reserve SOC percentage

    Payload: {'reservePercent':'4'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setBatteryReserve",payload)
    return response("setBatteryReserve")


@giv_api.route('/setBatteryCutoff', methods=['POST'])
def setBattCut():
    """Set Battery cut off SOC percentage

    Payload: {'dischargeToPercent':'4'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setBatteryCutoff",payload)
    return response("setBatteryCutoff")


@giv_api.route('/setChargeRateAC', methods=['POST'])
def setChrgeRateAC():
    """Set Battery charge rate in percentage

    Payload: {'chargeRate':'75'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setChargeRateAC",payload)
    return response("setChargeRateAC")

@giv_api.route('/setChargeRate', methods=['POST'])
def setChrgeRate():
    """Set Battery charge rate in watts

    Payload: {'chargeRate':'2500'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setChargeRate",payload)
    return response("setChargeRate")


@giv_api.route('/setCarChargeBoost', methods=['POST'])
def setCarBoost():
    """Set Car charge Boost value in watts

    Payload: {'boost':'2500'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setCarChargeBoost",payload)
    return response("setCarChargeBoost")


@giv_api.route('/setExportLimit', methods=['POST'])
def setExpLim():
    payload = request.get_json(silent=True, force=True)
    requestcommand("setExportLimit",payload)
    return response("setExportLimit")

@giv_api.route('/setDischargeRateAC', methods=['POST'])
def setDischrgeRateAC():
    """Set Battery discharge rate in percentage

    Payload: {'dischargeRate':'75'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setDischargeRateAC",payload)
    return response("setDischargeRateAC")

@giv_api.route('/setDischargeRate', methods=['POST'])
def setDischrgeRate():
    """Set Battery discharge rate in watts

    Payload: {'dischargeRate':'2500'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setDischargeRate",payload)
    return response("setDischargeRate")


@giv_api.route('/setPauseSlot', methods=['POST'])
def setPausSlot():
    """Set Battery pause control timeslot

    Payload: {'start':'16:00','finish':'19:00'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setPauseSlot",payload)
    return response("setPauseSlot")


### Should these now include a slot number as the input? ###

@giv_api.route('/setChargeSlot', methods=['POST'])
def setChrgSlot():
    """Set Charge schedule timeslots

    Payload: {'start':'16:00','finish':'19:00','slot':'1', 'chargeToPercent':'25' (optional)}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setChargeSlot",payload)
    return response("setChargeSlot")


@giv_api.route('/setChargeSlot1', methods=['POST'])
def setChrgSlot1():
    """Set Charge schedule timeslot 1

    Payload: {'start':'16:00','finish':'19:00', 'chargeToPercent':'25' (optional)}
    """
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    requestcommand("setChargeSlot",payload)
    return response("setChargeSlot")


@giv_api.route('/setChargeSlot2', methods=['POST'])
def setChrgSlot2():
    """Set Charge schedule timeslot 2

    Payload: {'start':'16:00','finish':'19:00', 'chargeToPercent':'25' (optional)}
    """
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    requestcommand("setChargeSlot",payload)
    return response("setChargeSlot")


@giv_api.route('/setChargeSlot3', methods=['POST'])
def setChrgSlot3():
    """Set Charge schedule timeslot 3

    Payload: {'start':'16:00','finish':'19:00', 'chargeToPercent':'25' (optional)}
    """
    payload = request.get_json(silent=True, force=True)
    payload['slot']=3
    requestcommand("setChargeSlot",payload)
    return response("setChargeSlot")


@giv_api.route('/setDischargeSlot', methods=['POST'])
def setDischrgSlot():
    """Set Discharge schedule timeslots

    Payload: {'start':'16:00','finish':'19:00','slot':'1", 'dischargeToPercent':'25' (optional)}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setDischargeSlot",payload)
    return response("setDischargeSlot")

@giv_api.route('/setDischargeSlot1', methods=['POST'])
def setDischrgSlot1():
    """Set Discharge schedule timeslot 1

    Payload: {'start':'16:00','finish':'19:00", 'dischargeToPercent':'25' (optional)}
    """
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    requestcommand("setDischargeSlot",payload)
    return response("setDischargeSlot")


@giv_api.route('/setDischargeSlot2', methods=['POST'])
def setDischrgSlot2():
    """Set Discharge schedule timeslot 2

    Payload: {'start':'16:00','finish':'19:00", 'dischargeToPercent':'25' (optional)}
    """
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    requestcommand("setDischargeSlot",payload)
    return response("setDischargeSlot")


@giv_api.route('/setDischargeSlot3', methods=['POST'])
def setDischrgSlot3():
    """Set Discharge schedule timeslot 1

    Payload: {'start':'16:00','finish':'19:00", 'dischargeToPercent':'25' (optional)}
    """

    payload = request.get_json(silent=True, force=True)
    payload['slot']=3
    requestcommand("setDischargeSlot",payload)
    return response("setDischargeSlot")


@giv_api.route('/setExportSlot1', methods=['POST'])
def setExpSlot1():
    """Set Export schedule timeslot 1

    Payload: {'start':'16:00','finish':'19:00'}
    """
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    requestcommand("setExportSlot",payload)
    return response("setExportSlot")

@giv_api.route('/setExportSlot2', methods=['POST'])
def setExpSlot2():
    """Set Export schedule timeslot 2

    Payload: {'start':'16:00','finish':'19:00'}
    """
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    requestcommand("setExportSlot",payload)
    return response("setExportSlot")

@giv_api.route('/setExportSlot3', methods=['POST'])
def setExpSlot3():
    """Set Export schedule timeslot 3

    Payload: {'start':'16:00','finish':'19:00'}
    """
    payload = request.get_json(silent=True, force=True)
    payload['slot']=3
    requestcommand("setExportSlot",payload)
    return response("setExportSlot")


@giv_api.route('/tempPauseDischarge', methods=['POST'])
def tmpPauseDischrg():
    """Pauses discharge from battery for the defined duration in Minutes or send Cancel command

    Payload: {'duration':'30' or 'Cancel'}
    """
    payload = request.get_json(silent=True, force=True)
    if payload['duration'] == "Cancel" or payload['duration'] == "0":
        if exists(".tpdRunning_"+str(GiV_Settings.givtcp_instance)):
            jobid= str(open(".tpdRunning','r").readline().strip('\n'))
            logger.debug("Retrieved jobID to cancel Temp Pause Discharge: "+ str(jobid))
            requestcommand("cancelJob",jobid)
            return response("cancelJob")
        else:
            logger.error("Temp Pause Discharge is not currently running")
            return "{'result':'Error: Temp Pause Discharge is not currently running'}"
    else:
        requestcommand("tempPauseDischarge",int(payload['duration']))
        return response("tempPauseDischarge")


@giv_api.route('/tempPauseCharge', methods=['POST'])
def tmpPauseChrg():
    """Pauses charge to battery for the defined duration in Minutes or send Cancel command

    Payload: {'duration':'30' or 'Cancel'}
    """
    payload = request.get_json(silent=True, force=True)
    if payload['duration'] == "Cancel" or payload['duration'] == "0":
        if exists(".tpcRunning_"+str(GiV_Settings.givtcp_instance)):
            jobid= str(open(".tpcRunning','r").readline().strip('\n'))
            logger.info("Retrieved jobID to cancel Temp Pause Charge: "+ str(jobid))
            requestcommand("cancelJob",jobid)
            return response("cancelJob")
        else:
            logger.error("Temp Pause Charge is not currently running")
            return "{'result':'Error: Temp Pause Charge is not currently running'}"
    else:
        requestcommand("tempPauseCharge",int(payload['duration']))
        return response("tempPauseCharge")


@giv_api.route('/forceCharge', methods=['POST'])
def frceChrg():
    """Forces battery to charge for the defined duration in Minutes or send Cancel command

    Payload: {'duration':'30' or 'Cancel'}
    """
    payload = request.get_json(silent=True, force=True)
    #Check if Cancel then return the right function
    if payload['duration'] == "Cancel" or payload['duration'] == "0":
        if exists(".FCRunning"+str(GiV_Settings.givtcp_instance)):
            jobid= str(open(".FCRunning"+str(GiV_Settings.givtcp_instance),"r").readline()).strip('\n')
            logger.debug("Retrieved jobID to cancel Force Charge: "+ str(jobid))
            requestcommand("cancelJob",jobid)
            return response("cancelJob")
        else:
            logger.error("Force Charge is not currently running")
            return "{'result':'Error: Force Charge is not currently running'}"
    else:
        requestcommand("forceCharge",int(payload['duration']))
        return response("forceCharge")


@giv_api.route('/forceExport', methods=['POST'])
def frceExprt():
    """Forces battery to discharge at max power for the defined duration in Minutes or send Cancel command

    Payload: {'duration':'30' or 'Cancel'}
    """

    payload = request.get_json(silent=True, force=True)
    if payload['duration'] == "Cancel" or payload['duration'] == "0":
        if exists(".FERunning"+str(GiV_Settings.givtcp_instance)):
            jobid= str(open(".FERunning"+str(GiV_Settings.givtcp_instance),"r").readline()).strip('\n')
            logger.debug("Retrieved jobID to cancel Force Export: "+ str(jobid))
            requestcommand("cancelJob",jobid)
            return response("cancelJob")
        else:
            logger.error("Force Export is not currently running")
            return "{'result':'Error: Force Export is not currently running'}"
    else:
        requestcommand("forceExport",int(payload['duration']))
        return response("forceExport")


@giv_api.route('/setBatteryMode', methods=['POST'])
def setBattMode():
    """Sets the inverter operation mode 

    Payload: {'mode':'Eco' or 'Eco (Paused)' or 'Timed Demand' or 'Timed Export'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setBatteryMode",payload)
    return response("setBatteryMode")


@giv_api.route('/setEcoMode', methods=['POST'])
def stEcoMde():
    """Toggles the battery 'Eco Mode' setting (otherwise known as 'winter mode')

    Payload: {'state':'enable' or 'disable'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setEcoMode",payload)
    return response("setEcoMode")


@giv_api.route('/setBatteryPauseMode', methods=['POST'])
def setBattPausMode():
    """Sets the battery pause mode setting, (requires pauseslot to be set)

    Payload: {'state':'enable' or 'disable'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setBatteryPauseMode",payload)
    return response("setBatteryPauseMode")


@giv_api.route('/setDateTime', methods=['POST'])
def setDate():
    """Sets the inverter system time and date

    Payload: {'dateTime':'%d/%m/%Y %H:%M:%S'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setDateTime",payload)
    return response("setDateTime")


@giv_api.route('/syncDateTime', methods=['POST'])
def syncDate():
    """Syncs the inverter system time and date with Container time

    Payload: {'dateTime':'%d/%m/%Y %H:%M:%S'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("syncDateTime",payload)
    return response("syncDateTime")


@giv_api.route('/switchRate', methods=['POST'])
def swRates():
    """Sets dynamic tariff rate

    Payload: {'rate':'day' or "night'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("switchRate",payload['rate'])
    return response("switchRate")


@giv_api.route('/setImportCap', methods=['POST'])
def impCap():
    """Sets gird import cap for EVC charging in [A]

    Payload: {'current':'60'}
    """
    payload = request.get_json(silent=True, force=True)
    return evc.setImportCap(payload['current'])

@giv_api.route('/setCurrentLimit', methods=['POST'])
def currLimit():
    """Sets MAX EVC current draw in [A]

    Payload: {'current':'32'}
    """
    payload = request.get_json(silent=True, force=True)
    return evc.setCurrentLimit(payload['current'])

@giv_api.route('/setForceDischarge', methods=['POST'])
def frceDischarge():
    """Enables Force Discharge on Three Phase Inverters

    Payload: {'state':'enabled' or "disabled'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setForceDischarge",payload['state'])
    return response("setForceDischarge")

@giv_api.route('/setForceCharge', methods=['POST'])
def frceCharge():
    """Enables Force Charge on Three Phase Inverters

    Payload: {'state':'enabled' or "disabled'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setForceCharge",payload['state'])
    return response("setForceCharge")

@giv_api.route('/setBatteryCalibration', methods=['POST'])
def setCalib():
    """Trigger or stop a Battery Calibration

    Payload: {'state':'off' or 'start'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setBatteryCalibration",payload)
    return response("setBatteryCalibration")

@giv_api.route('/setACCharge', methods=['POST'])
def setSCChrg():
    """Enables AC Charge on Three Phase Inverters

    Payload: {'state':'enabled' or "disabled'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setACCharge",payload['state'])
    return response("setACCharge")

@giv_api.route('/setEmsPlant', methods=['POST'])
def setEMSPlnt():
    """Enables AC Charge on Three Phase Inverters

    Payload: {'state':'enabled' or "disabled'}
    """
    payload = request.get_json(silent=True, force=True)
    requestcommand("setEmsPlant",payload['state'])
    return response("setEmsPlant")

@giv_api.route('/setChargeControl', methods=['POST'])
def chrgeControl():
    """starts or stops the EVC charger

    Payload: {'mode':'start' or "stop'}
    """
    payload = request.get_json(silent=True, force=True)
    return evc.setChargeControl(payload['mode'])

@giv_api.route('/setChargeMode', methods=['POST'])
def chrgMode():
    payload = request.get_json(silent=True, force=True)
    return evc.setChargeMode(payload)

@giv_api.route('/setChargingMode', methods=['POST'])
def chrgingMode():
    """Sets the Charging Mode for EVC

    Payload: {'state':'enable' or 'disable'}
    """
    payload = request.get_json(silent=True, force=True)
    return evc.setChargingMode(payload['state'])

@giv_api.route('/setMaxSessionEnergy', methods=['POST'])
def maxSession():
    """Sets MAX EVC energy per charge session [kWh]

    Payload: {'energy':'20.5'}
    """
    payload = request.get_json(silent=True, force=True)
    return evc.setMaxSessionEnergy(payload['energy'])

@giv_api.route('/getEVCCache', methods=['GET'])
def gtEVCChce():
    """Retrieve Last known data from the EVC file cache
    """
    payload = request.get_json(silent=True, force=True)
    return evc.getEVCCache()

def get_decorators(function):
    source = getsource(function)
    index = source.find("def ")
    for line in source[:index].strip().splitlines():
        if line.strip()[0] == "@":
            output=[line.strip().split()[0].split("'")[1],line.strip().split()[1].split("'")[1]]
            return output
    return None

def get_payload(docstring):
    for line in docstring.strip().splitlines():
        if "Payload:" in line:
            output="{"+line.split('{')[-1].split('}')[0]+"}"
            return output
    return None

def getapicalls():
    current_module = sys.modules[__name__]
    output={}
    output['api']="GivTCP REST API stack\nCalls made to each inverter seperately on port 8099 at /REST1, /REST2, /REST3, /REST4 or /REST5"
    commands={}
    functions=getmembers(current_module, isfunction)
    for name,function in functions:
        command={}
        dec= get_decorators(function)
        if dec:
            if not function.__doc__==None:
            #if hasattr(function,"__doc__"):
                command['url']=dec[0]
                command['method']=dec[1]
                command['usage']=function.__doc__.strip().splitlines()[0]
                if get_payload(function.__doc__):
                    command['payload']=get_payload(function.__doc__)
                commands[dec[0][1:]]=command
    output['commands']=commands
    with open('api.json', 'w') as f:
        f.write(json.dumps(output, indent=4))
    return output

def start():
    getapicalls()
    #getAll()

if __name__ == "__main__":
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
    else:
        giv_api.run()
