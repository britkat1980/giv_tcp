"""An inverter that stops answering only affects its own read loop, so that loop looks for it at a new IP address
itself. It used to restart GivTCP, which restarted every other inverter's read loop and lost their timed reverts"""
import asyncio
import json
import os

import pytest

import GivLUT as givlut_module
import ipchange
import netscan
import read
from GivLUT import GivLUT
from harness import env

SERIAL = "AA1111A111"
OLD, NEW, OTHER = "192.168.0.136", "192.168.0.140", "192.168.0.131"

@pytest.fixture
def lost(monkeypatch):
    env.configure(invertorIP=OLD, serial_number=SERIAL, givtcp_instance=2)
    with open(GivLUT.allsettings, "w") as outp:
        json.dump({"evc_enable": False, "invertorIP_1": OTHER, "invertorIP_2": OLD}, outp)
    probed = []
    async def serial_at(ip):
        probed.append(ip)
        return SERIAL if ip == NEW else "BB2222B222"
    monkeypatch.setattr(ipchange, "serialAt", serial_at)
    def no_restart():
        raise AssertionError("GivTCP was restarted")
    monkeypatch.setattr(read, "rebootaddon", no_restart)
    replaced = []
    async def new_client(reason="", quiet=False, host=None):
        replaced.append(host)
    monkeypatch.setattr(givlut_module.GivClientAsync, "new_client", new_client)
    yield probed, replaced
    env.configure()     # back to the default settings, and settings.py, for later tests
    with open(GivLUT.allsettings, "w") as outp:
        json.dump({"evc_enable": False}, outp)

def scanning(monkeypatch, ips):
    monkeypatch.setattr(netscan, "scan", lambda subnet, ports, timeout=None: {netscan.INVERTER_PORT: list(ips)})

def test_moved_inverter_is_followed(lost, monkeypatch):
    probed, replaced = lost
    scanning(monkeypatch, [OLD, OTHER, "192.168.0.139", NEW])
    open("commsfailure_2.pkl", "w").close()
    asyncio.run(read.lostInverter())
    assert read.GiV_Settings.invertorIP == NEW
    assert replaced == [NEW]
    assert OTHER not in probed and OLD not in probed      # another inverter's read loop isn't disturbed
    with open(GivLUT.allsettings) as inp:
        setts = json.load(inp)
    assert setts["invertorIP_2"] == NEW and setts["invertorIP_1"] == OTHER
    with open(env.WORK / "settings.py") as inp:
        assert 'invertorIP="' + NEW + '"' in inp.read()
    assert not os.path.exists("commsfailure_2.pkl")

def test_offline_inverter_keeps_retrying_without_restart(lost, monkeypatch):
    probed, replaced = lost
    scanning(monkeypatch, [OLD, OTHER])
    open("commsfailure_2.pkl", "w").close()
    asyncio.run(read.lostInverter())
    assert read.GiV_Settings.invertorIP == OLD and not replaced
    assert not os.path.exists("commsfailure_2.pkl")      # checks again after another 10 failures

def test_scan_failure_keeps_retrying(lost, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("network unreachable")
    monkeypatch.setattr(netscan, "scan", broken)
    asyncio.run(read.lostInverter())
    assert read.GiV_Settings.invertorIP == OLD

def test_scan_is_the_inverters_own_subnet(lost, monkeypatch):
    subnets = []
    def scan(subnet, ports, timeout=None):
        subnets.append((subnet, ports))
        return {netscan.INVERTER_PORT: []}
    monkeypatch.setattr(netscan, "scan", scan)
    asyncio.run(ipchange.findInverter())
    assert subnets == [("192.168.0.0/24", (netscan.INVERTER_PORT,))]
