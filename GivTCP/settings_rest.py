# -*- coding: utf-8 -*-
# version 2021.12.22
from os.path import exists
import os
import sys
import requests
from flask import Flask, request
from flask_cors import CORS
import json

#set-up Flask details
giv_api = Flask(__name__)
CORS(giv_api)


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
                    'Authorization': 'Bearer {}'.format(access_token)})
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

if __name__ == "__main__":
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
    else:
        giv_api.run()
