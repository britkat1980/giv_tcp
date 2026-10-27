"""Sync Time on a Gateway with a single All in One (#680): its other controls are only for parallel All in Ones, but its
clock needs setting either way"""
import json

from givenergy_modbus.model.register import IR

import read

def gateway_controls(plants, online):
    session = plants.get("gateway")
    session.activate(session.state)
    try:
        session.plant.register_caches[session.plant.capabilities.inverter_address].update({IR(1701): online})
        result = json.loads(read.processData(session.plant))
        assert result["result"] == "Success processing data"
        return result["multi_output"]["Control"]
    finally:
        session.activate(session.state)

def test_single_all_in_one_has_sync_time(plants):
    assert gateway_controls(plants, 1) == {"Sync_Time": "disable"}

def test_parallel_all_in_ones_keep_their_controls(plants):
    controls = gateway_controls(plants, 2)
    assert controls["Sync_Time"] == "disable" and len(controls) > 1
