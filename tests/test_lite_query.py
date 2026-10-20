"""Lite mode (lite_query): the HV battery stacks are asked as little as possible, as the inverter passes each read on to a
stack's BCU or module. Modules are only read until they have data, BCUs between full refreshes only until they have data"""
import asyncio
import json
import types

import pytest

import modbus_patches
import read

def skipped(session, monkeypatch, light, full):
    monkeypatch.setattr(read.GiV_Settings, "lite_query", light, raising=False)
    async def noop(**kwargs):
        pass
    client = types.SimpleNamespace(refresh=noop, load_config=noop, plant=session.plant)
    try:
        asyncio.run(read.readPlant(client, full))
        return set(modbus_patches.skip_banks)
    finally:
        modbus_patches.skip_banks = set()

@pytest.fixture
def stacks(plants):
    session = plants.get("hybrid_3ph")
    session.activate(session.state)
    plant = session.plant
    modules = set(modbus_patches.hv_module_banks(plant.capabilities))
    bcus = {(s.device_address, 60, 60) for s in plant.hv_stacks}
    assert modules and bcus and all(s.bcu.is_valid() for s in plant.hv_stacks)
    assert read.hvModulesRead(plant) == modules         # the modules have data after the harness's reads
    return session, modules, bcus

def test_off_as_before(stacks, monkeypatch):
    session, modules, bcus = stacks
    assert skipped(session, monkeypatch, False, False) == modules      # modules only on full refreshes (#614)
    assert skipped(session, monkeypatch, False, True) == set()

def test_on(stacks, monkeypatch):
    session, modules, bcus = stacks
    assert skipped(session, monkeypatch, True, False) == modules | bcus
    assert skipped(session, monkeypatch, True, True) == modules         # BCUs read on full refreshes, modules never

def test_read_until_they_have_data(stacks, monkeypatch):
    session, modules, bcus = stacks
    monkeypatch.setattr(read, "hvModulesRead", lambda plant: set())
    monkeypatch.setattr(read, "hvBcusRead", lambda plant: set())
    assert skipped(session, monkeypatch, True, False) == set()

def test_setting_read_as_written_by_startup(monkeypatch):
    for value, expected in ((True, True), ("True", True), (False, False), ("False", False), (None, False)):
        monkeypatch.setattr(read.GiV_Settings, "lite_query", value, raising=False)
        assert read.liteQuery() is expected

def test_soc_kwh_from_inverter_soc(stacks, monkeypatch):
    session, _, _ = stacks
    session.activate(session.state)
    monkeypatch.setattr(read.GiV_Settings, "lite_query", True, raising=False)
    try:
        result = json.loads(read.processData(session.plant))
    finally:
        session.activate(session.state)
    out = result["multi_output"]
    serial = session.plant.inverter.serial_number
    cap = out[serial]["Battery_Capacity_kWh"]
    soc = out["Power"]["Power"]["SOC"]
    assert cap and soc is not None
    assert out["Power"]["Power"]["SOC_kWh"] == round(soc * cap / 100, 2)
