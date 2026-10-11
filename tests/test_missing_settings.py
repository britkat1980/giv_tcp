"""A poll is still processed when the inverter settings (holding registers) haven't been read yet (#608)"""
import json
import types

import pytest

import read
from givenergy_modbus.model.register import HR

def test_enum_text():
    assert read.enumText(None) is None
    assert read.enumText(types.SimpleNamespace(name="NORMAL")) == "Normal"

def process_without(plants, device, missing):
    session = plants.get(device)
    session.activate(session.state)
    try:
        cache = session.plant.register_caches[session.plant.capabilities.inverter_address]
        for r in missing:
            cache.pop(HR(r), None)
        return json.loads(read.processData(session.plant)), session.plant.inverter.serial_number
    finally:
        session.activate(session.state)      # put the registers back for later tests

def test_3ph_without_battery_type(plants):
    # As #608 after the first poll: HR 1060-1119 (battery type at HR 1080) not read yet
    result, serial = process_without(plants, "hybrid_3ph", range(1060, 1120))
    assert result["result"] == "Success processing data"
    assert result["multi_output"][serial].get("Battery_Type") is None
    assert result["multi_output"]["Power"]          # the live data is still published

def test_without_device_type(plants):
    # HR 0-59 not read yet: processing needs that block, so it says so rather than fail on hex(None)
    result, _ = process_without(plants, "hybrid_gen2", range(0, 60))
    assert result["result"] == "processData Error processing registers: Inverter settings not read yet"

def test_full_refresh_retried_while_settings_missing():
    from givenergy_modbus.exceptions import ReadFailure
    hr = [ReadFailure(0x11, "ReadHoldingRegistersRequest", 1060, 60)]
    ir = [ReadFailure(0x11, "ReadInputRegistersRequest", 0, 60)]
    assert read.settingsRetry([], 0) == (False, 0)
    assert read.settingsRetry(ir, 0) == (False, 0)         # live data failures don't hold up the full refresh
    retries = 0
    for _ in range(read.FULL_REFRESH_RETRIES):
        retry, retries = read.settingsRetry(hr, retries)
        assert retry
    assert read.settingsRetry(hr, retries) == (False, 0)   # give up until the next full refresh
