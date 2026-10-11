"""Gen 3 PV-only (string) inverters, processed by processPVInfo: there's no capture of one, so a single-phase
plant's registers are used with a PV inverter's device type code (0x23xx) (#618)"""
import json

import read
from givenergy_modbus.model.register import HR

def test_pv_inverter_processed(plants):
    session = plants.get("hybrid_gen2")
    session.activate(session.state)
    caps = session.plant.capabilities
    try:
        # A PV inverter has no batteries (processData skips the battery rate calculations then)
        session.plant.capabilities = caps.model_copy(update={"lv_battery_addresses": [], "lv_bcu_address": None})
        cache = session.plant.register_caches[caps.inverter_address]
        cache[HR(0)] = 0x2301
        inv = session.plant.inverter
        # givenergy-modbus gives IR45/46 as e_pv_generation_total here, and e_inverter_out_total is None, which
        # failed every poll with "unsupported operand type(s) for +: 'float' and 'NoneType'"
        assert inv.e_inverter_out_total is None and inv.e_pv_generation_total is not None
        result = json.loads(read.processData(session.plant))
        assert result["result"] == "Success processing data"
        energy = result["multi_output"]["Energy"]
        assert energy["Total"]["Invertor_Energy_Total_kWh"] == inv.e_pv_generation_total
        assert energy["Today"]["PV_Energy_Today_kWh"] is not None
    finally:
        session.plant.capabilities = caps
        session.activate(session.state)      # put the registers back for later tests
