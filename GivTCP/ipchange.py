"""Finding an inverter whose IP address has changed (eg. a new DHCP lease) from its own read loop. Only that
inverter's read loop uses its address, so there's no need to restart GivTCP, which restarts every inverter"""
import asyncio
import ipaddress
import json
import os
import re
import sys

from givenergy_modbus.client.client import Client

import netscan
from GivLUT import GivLUT
from settings import GiV_Settings

logger = GivLUT.logger

async def serialAt(ip):
    # The serial number of the inverter answering at ip, or None
    client=Client(ip, netscan.INVERTER_PORT, 3)
    try:
        await client.connect()
        if not await client.probe_alive(timeout=3, retries=2):
            return None
        return client.plant.inverter.serial_number
    except Exception:
        return None
    finally:
        try:
            await client.close()
        except Exception:
            pass

def otherInverterIPs():
    # Addresses of the other configured inverters, which needn't be probed (and their read loops disturbed)
    try:
        with open(GivLUT.allsettings) as inp:
            setts=json.load(inp)
    except Exception:
        return set()
    inv=str(GiV_Settings.givtcp_instance)
    return {v for k,v in setts.items() if k.startswith("invertorIP_") and k!="invertorIP_"+inv and v}

async def findInverter():
    """Scan the inverter's /24 for its serial number, as startup does, and return its new IP address, or None if
    it isn't anywhere else (eg. it or its dongle is offline)"""
    subnet=str(ipaddress.ip_network(GiV_Settings.invertorIP+"/24", strict=False))
    found=await asyncio.to_thread(netscan.scan, subnet, (netscan.INVERTER_PORT,))
    skip=otherInverterIPs()|{GiV_Settings.invertorIP}
    for ip in found.get(netscan.INVERTER_PORT, []):
        if ip not in skip and await serialAt(ip)==GiV_Settings.serial_number:
            return ip
    return None

def saveInverterIP(ip):
    # So the next start and the config page use the new address, as startup's scan would have saved it
    inv=str(GiV_Settings.givtcp_instance)
    with open(GivLUT.allsettings) as inp:
        setts=json.load(inp)
    setts["invertorIP_"+inv]=ip
    tmp=GivLUT.allsettings+".tmp"
    with open(tmp,'w') as outp:
        outp.write(json.dumps(setts,indent=4))
    os.replace(tmp, GivLUT.allsettings)
    path=sys.modules[GiV_Settings.__module__].__file__
    with open(path) as inp:
        text=inp.read()
    with open(path,'w') as outp:
        outp.write(re.sub(r'^(\s*invertorIP=)(["\']).*\2$', lambda m: m.group(1)+'"'+ip+'"', text, count=1, flags=re.M))
