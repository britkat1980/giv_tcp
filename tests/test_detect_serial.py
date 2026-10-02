"""Capabilities are saved per serial, so a detect of the wrong inverter (eg. after two inverters' IP addresses
swap) mustn't be saved under this inverter's serial, or it gets the other one's model from then on"""
import asyncio
import os
import types

import read
from harness import env
from harness.fakes import real_wrong_inverter

def fake_client(serial):
    async def detect():
        return None
    plant = types.SimpleNamespace(inverter=types.SimpleNamespace(serial_number=serial), capabilities={"caps": serial})
    return types.SimpleNamespace(plant=plant, detect=detect)

def test_wrong_inverter():
    env.configure(serial_number="AA1111A111")
    assert real_wrong_inverter[0](fake_client("AA1111A111")) is None
    assert real_wrong_inverter[0](fake_client("BB2222B222")) == "BB2222B222"
    assert real_wrong_inverter[0](fake_client(None)) is None      # serial not read, so nothing to compare

def test_detect_not_saved_for_another_inverter(monkeypatch):
    env.configure(serial_number="AA1111A111")
    monkeypatch.setattr(read, "wrongInverter", real_wrong_inverter[0])
    if os.path.exists(read.capsFile()):
        os.remove(read.capsFile())
    asyncio.run(read.detectPlant(fake_client("BB2222B222"), force=True))
    assert not os.path.exists(read.capsFile())
    asyncio.run(read.detectPlant(fake_client("AA1111A111"), force=True))
    assert os.path.exists(read.capsFile())
    os.remove(read.capsFile())
