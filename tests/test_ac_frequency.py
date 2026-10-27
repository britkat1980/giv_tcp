"""Grid and output frequency (#675): some inverters report it 10 times too high, which the Modbus library's 40-70Hz
bounds turn into None. That failed every poll with "'>' not supported between instances of 'NoneType' and 'int'"""
import json

import pytest
from givenergy_modbus.model.register import IR

import read

def process(plants, device, registers):
    session = plants.get(device)
    session.activate(session.state)
    try:
        cache = session.plant.register_caches[session.plant.capabilities.inverter_address]
        for reg, value in registers.items():
            if value is None:
                cache.pop(IR(reg), None)
            else:
                cache.update({IR(reg): value})
        result = json.loads(read.processData(session.plant))
        assert result["result"] == "Success processing data"
        return result["multi_output"]["Power"]["Power"]
    finally:
        session.activate(session.state)      # put the registers back for later tests

@pytest.mark.parametrize("device", ["ac", "hybrid_gen2"])
def test_reported_10_times_too_high(plants, device):
    power = process(plants, device, {13: 50010, 54: 49990})        # 500.10 and 499.90 decoded, out of bounds
    assert power["Grid_Frequency"] == pytest.approx(50.01)
    assert power["Inverter_Output_Frequency"] == pytest.approx(49.99)

@pytest.mark.parametrize("device", ["ac", "hybrid_gen2"])
def test_normal(plants, device):
    power = process(plants, device, {13: 5002, 54: 4998})
    assert power["Grid_Frequency"] == pytest.approx(50.02)
    assert power["Inverter_Output_Frequency"] == pytest.approx(49.98)

def test_not_read_leaves_it_out(plants):
    power = process(plants, "ac", {13: None, 54: None})
    assert "Grid_Frequency" not in power and "Inverter_Output_Frequency" not in power
    assert "Load_Power" in power or len(power) > 5          # the rest of the poll is still published
