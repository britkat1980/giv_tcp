"""Battery Pack Current (IR 95): which inverters pass it on, and which pack firmware reports it (#605, #616)"""
from givenergy_modbus.model.inverter import Model

import modbus_patches as mp

def test_inverters():
    # #616: an AC on ARM 214 reports it (GivEnergy had said above 214)
    assert mp.bms_current_inverter(Model.AC, 214)
    assert mp.bms_current_inverter(Model.HYBRID_GEN3, 214)
    assert not mp.bms_current_inverter(Model.AC, 213)
    assert not mp.bms_current_inverter(Model.HYBRID_GEN1, 449)
    assert not mp.bms_current_inverter(Model.AC, None)

def test_pack_firmware():
    # #616: packs on BMS 3020 report it (GivEnergy had said 3022)
    assert mp.bms_current_firmware(3020)
    assert mp.bms_current_firmware(3022)
    assert not mp.bms_current_firmware(3019)
    assert not mp.bms_current_firmware(4008)
    assert mp.bms_current_firmware(4009)
    assert not mp.bms_current_firmware(None)
