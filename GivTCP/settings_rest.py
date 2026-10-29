# -*- coding: utf-8 -*-
# version 2021.12.22
from os.path import exists
import os
import sys
import requests
from flask import Flask, request, Response
import json
import settings_values
from crosssite import refuse_cross_site

#set-up Flask details. Only GivTCP's own pages use this API (through nginx), so it has no CORS and refuses
#cross-site requests: the settings hold credentials, and become each instance's settings.py
giv_api = Flask(__name__)
refuse_cross_site(giv_api)


@giv_api.route('/reboot', methods=['POST'])
def reboot():
    """Save settings into json file

    Payload: json object conforming to the settings_template
    """
    try:
        access_token = os.getenv("SUPERVISOR_TOKEN")
        url="http://supervisor/addons/self/restart"
        result = requests.post(url,
            headers={'Content-Type':'application/json',
                    'Authorization': 'Bearer {}'.format(access_token)}, timeout=30)
    except:
        return "Error: Reboot Manually"

@giv_api.route('/settings', methods=['POST'])
def savesetts():
    """Save settings into json file

    Payload: json object conforming to the settings_template
    """
    
    if exists("/config/GivTCP/allsettings.json"):
        SFILE="/config/GivTCP/allsettings.json"
    else:
        SFILE="/app/allsettings.json"
    # Merge into the existing file rather than replacing it, so settings the config page doesn't manage
    # (Model_N, Host_IP, serial_number_evc, auto_scan...) aren't wiped back to template defaults on save
    payload=request.get_json(silent=True)
    error=settings_values.check(payload, settings_values.load_template())
    if error:
        return Response(json.dumps({"result":"Error: "+error}), status=400, mimetype='application/json')
    setts={}
    if exists(SFILE):
        with open(SFILE, 'r') as f1:
            setts=json.load(f1)
    setts.update(settings_values.keep_secrets(payload, setts))
    with open(SFILE, 'w') as f:
        f.write(json.dumps(setts,indent=4))
    return "Settings Updated"

@giv_api.route('/settings', methods=['GET'])
def returnsetts():
    """Return settings from json file, with credentials hidden
    """
    if exists("/config/GivTCP/allsettings.json"):
        SFILE="/config/GivTCP/allsettings.json"
    else:
        SFILE="/app/allsettings.json"
    with open(SFILE, 'r') as f1:
        setts=json.load(f1)
        return settings_values.hide_secrets(setts)

@giv_api.route('/settings/found', methods=['GET'])
def foundinverters():
    """Return the inverters found on the last network scan (written by startup.py), for the config page
    """
    found=[]
    if exists("/config/GivTCP/found_inverters.json"):
        with open("/config/GivTCP/found_inverters.json", 'r') as f1:
            found=json.load(f1)
    return Response(json.dumps(found), mimetype='application/json')

if __name__ == "__main__":
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
    else:
        giv_api.run()
