"""Charge slot 2 is at HR 243/244 on 10-slot firmware, not the legacy HR 31/32 (#619)"""
from datetime import time

from givenergy_modbus.model import manifest
from givenergy_modbus.model.inverter import Model, SinglePhaseInverter
from givenergy_modbus.model.register import HR
from givenergy_modbus.model.register_cache import RegisterCache

import modbus_patches  # noqa: F401

GEN3 = 0x2001

def inverter(arm_fw):
    cache = RegisterCache()
    cache[HR(0)] = GEN3
    cache[HR(21)] = arm_fw
    return SinglePhaseInverter.from_register_cache(cache)

def registers(requests):
    return [(r.register, r.value) for r in requests]

def test_ten_slot_firmware():
    inv = inverter(303)
    assert registers(inv.set_charge_slot_start(2, time(1, 30))) == [(243, 130)]
    assert registers(inv.set_charge_slot_end(2, time(0, 1))) == [(244, 1)]
    assert {243, 244} <= manifest.write_safe_registers(Model.HYBRID_GEN3, 303)

def test_two_slot_firmware():
    inv = inverter(302)
    assert registers(inv.set_charge_slot_end(2, time(0, 1))) == [(32, 1)]
    assert not {243, 244} & manifest.write_safe_registers(Model.HYBRID_GEN3, 302)
