# -*- coding: utf-8 -*-
# version 2021.12.22
from os.path import exists
import os
import sys
import requests
from flask import Flask, request
from flask_cors import CORS
import json
import threading
import uuid
import paho.mqtt.client as mqtt

#set-up Flask details
giv_api = Flask(__name__)
CORS(giv_api)


def _mqtt_reason_code(reason_code):
    try:
        return int(reason_code)
    except (TypeError, ValueError):
        try:
            return int(reason_code.value)
        except (AttributeError, TypeError, ValueError):
            return None


def _mqtt_reason_message(reason_code):
    code = _mqtt_reason_code(reason_code)
    if code == 0:
        return "Connected to broker"
    if code == 4:
        return "Broker rejected the username or password"
    if code == 5:
        return "Broker rejected the connection as unauthorised"
    if code is None:
        return "Broker rejected the connection"
    return "Broker rejected the connection (code " + str(code) + ")"


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


@giv_api.route('/settings/mqtt/test', methods=['POST'])
def testmqtt():
    """Validate MQTT connection settings without persisting them."""
    payload = request.get_json(silent=True) or {}
    address = str(payload.get("MQTT_Address", "")).strip()
    username = str(payload.get("MQTT_Username", "") or "")
    password = str(payload.get("MQTT_Password", "") or "")

    if address == "":
        return {"ok": False, "message": "MQTT host is required"}

    try:
        port = int(payload.get("MQTT_Port", 1883))
        if port < 1 or port > 65535:
            raise ValueError
    except (TypeError, ValueError):
        return {"ok": False, "message": "MQTT port must be a number between 1 and 65535"}

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        "GivTCP_MQTT_Test_" + uuid.uuid4().hex[:8],
    )
    if username != "":
        client.username_pw_set(username, password)

    result = {
        "ok": False,
        "message": "Connection attempt timed out",
    }
    finished = threading.Event()

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        result["ok"] = _mqtt_reason_code(reason_code) == 0
        result["message"] = _mqtt_reason_message(reason_code)
        finished.set()

    def on_disconnect(_client, _userdata, _flags, reason_code, _properties):
        if finished.is_set():
            return
        if _mqtt_reason_code(reason_code) == 0:
            result["message"] = "Disconnected before connection completed"
        else:
            result["message"] = _mqtt_reason_message(reason_code)
        finished.set()

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(address, port=port, keepalive=10)
        client.loop_start()
        finished.wait(5)
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        try:
            client.loop_stop()
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass

    return result

if __name__ == "__main__":
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
    else:
        giv_api.run()
