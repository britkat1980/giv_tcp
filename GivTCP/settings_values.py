"""Settings arrive from the settings API as JSON and are written into each instance's settings.py, so nothing in them
may ever become code. Values are written as Python literals, and the API refuses a payload whose keys or values don't
look like settings before it's saved"""
import json
import math
import re
from os.path import exists

# The settings.json shipped in the image: the defaults, and so the type each setting should have
TEMPLATE="/app/settings.json"
KEY=re.compile(r"^[A-Za-z0-9_]{1,64}$")
MAX_TEXT=1000
# Settings that are credentials: never sent back by the settings APIs, which give HIDDEN in their place (when set).
# A save that sends HIDDEN back keeps the saved value
SECRETS=("MQTT_Password","influxToken","GE_API","SOLCASTAPI","REST_API_Key")
HIDDEN="********"
# The REST API key goes into nginx's config (so GivTCP's own pages can send it), so it's limited to these characters
API_KEY=re.compile(r"^[A-Za-z0-9_-]{16,128}$")

def hide_secrets(setts):
    """A copy of the settings to send back, with every credential that's set replaced by HIDDEN"""
    shown=dict(setts)
    for key in SECRETS:
        if shown.get(key):
            shown[key]=HIDDEN
    return shown

def keep_secrets(payload, saved):
    """The payload to save, with each credential sent back as HIDDEN replaced by its saved value"""
    kept=dict(payload)
    for key in SECRETS:
        if kept.get(key)==HIDDEN:
            if key in saved:
                kept[key]=saved[key]
            else:
                del kept[key]
    return kept

def text(value):
    """A setting as a Python string literal"""
    return repr(str(value))

def flag(value):
    """A setting as True or False. JSON gives true/false, older settings files "true"/"false" """
    return str(value is True or str(value).strip().lower()=="true")

def number(value, default, cast=None):
    """A setting as a number literal: the default if it isn't a finite number. cast (int or float) forces the type"""
    parsed=_parse_number(value)
    if parsed is None:
        parsed=default
    if cast is not None:
        parsed=cast(parsed)
    return repr(parsed)

def _parse_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        value=value.strip()
        try:
            return int(value)
        except ValueError:
            pass
        try:
            parsed=float(value)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None

def template_type(key, template):
    """The default for a key in the template, taking inverter N's keys (eg. invertorIP_7) as inverter 1's"""
    if key in template:
        return template[key]
    match=re.match(r"^(.*_)\d+$", key)
    return template.get(match.group(1)+"1") if match else None

def check(payload, template):
    """Why a settings payload can't be saved, or None if it can"""
    if not isinstance(payload, dict):
        return "Settings must be a JSON object"
    for key, value in payload.items():
        if not KEY.match(str(key)):
            return "Invalid setting name: "+repr(key)[:70]
        if value is not None and not isinstance(value, (str, int, float, bool)):
            return key+" must be a single value"
        if isinstance(value, float) and not math.isfinite(value):
            return key+" must be a finite number"
        if isinstance(value, str) and len(value)>MAX_TEXT:
            return key+" is too long"
        default=template_type(key, template)
        if isinstance(default, bool):
            if not (isinstance(value, bool) or str(value).strip().lower() in ("true", "false")):
                return key+" must be true or false"
        elif isinstance(default, (int, float)):
            if value not in (None, "") and _parse_number(value) is None:
                return key+" must be a number"
    rest_key=payload.get("REST_API_Key")
    if rest_key not in (None, "", HIDDEN) and not API_KEY.match(str(rest_key)):
        return "REST_API_Key must be 16-128 letters, digits, - or _"
    return None

def api_key(setts):
    """The REST API key, or "" when there isn't a valid one (so the REST API is open, as it always was)"""
    key=str(setts.get("REST_API_Key") or "")
    return key if API_KEY.match(key) else ""

def load_template(path=TEMPLATE):
    try:
        if exists(path):
            with open(path, 'r') as inp:
                return json.load(inp)
    except (OSError, ValueError):
        pass
    return {}
