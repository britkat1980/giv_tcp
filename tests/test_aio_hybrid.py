"""The All in One-HY (DTC 0x82xx) is read single-phase: the library lists it as three-phase, and its 1000-range
three-phase registers are rejected (#621)"""
import modbus_patches  # noqa: F401  (applies the patch)
from givenergy_modbus.client import client as client_module
from givenergy_modbus.model import manifest
from givenergy_modbus.model.inverter import Model, SinglePhaseInverter, resolve_model
from givenergy_modbus.model.inverter_threephase import select_inverter
from givenergy_modbus.model.plant import PlantCapabilities
from givenergy_modbus.model.register import HR
from givenergy_modbus.model.register_cache import RegisterCache

import read

def test_resolves_as_all_in_one_hybrid():
    assert resolve_model(0x8201, 600) is Model.ALL_IN_ONE_HYBRID

def test_single_phase():
    caps = PlantCapabilities(device_type=Model.ALL_IN_ONE_HYBRID, bcu_stacks=[(0, 4)])
    assert not caps.is_three_phase
    cache = RegisterCache()
    cache[HR(0)] = 0x8201
    assert isinstance(select_inverter(Model.ALL_IN_ONE_HYBRID, cache), SinglePhaseInverter)
    # no three-phase (1000-range) reads, which it rejects
    assert not [b for b in client_module._refresh_banks(caps) if 1000 <= b[1] < 1500]

def test_keeps_ten_slots_and_hybrid_load_formula():
    assert manifest.has_extended_slots(Model.ALL_IN_ONE_HYBRID, 600)
    assert Model.ALL_IN_ONE_HYBRID in read.DC_HYBRID_MODELS

def test_three_phase_still_three_phase():
    assert manifest.has_capability("is_three_phase", Model.HYBRID_3PH)
    assert manifest.has_capability("is_three_phase", Model.AIO_COMMERCIAL)

def test_missing_pv_values():
    assert read.sumPresent(None, None) is None
    assert read.sumPresent(1200.0, None) == 1200.0

def _plant(dtc, stacks):
    from types import SimpleNamespace
    caps = PlantCapabilities(device_type=Model.ALL_IN_ONE_HYBRID, bcu_stacks=stacks)
    inv = SimpleNamespace(inverter_max_power=12000, battery_max_power=None, battery_capacity_kwh=16.48,
                          device_type_code=dtc)
    return SimpleNamespace(capabilities=caps, inverter=inv)

def test_battery_rate():
    # The library has no battery rating for the All in One-HY, which failed every poll (#628): estimate it from the
    # HV stack, within the inverter's rating
    assert read.getInvModel(_plant("8204", [(0, 4)])).batmaxrate == 25 * 80 * 4
    assert read.getInvModel(_plant("8204", [(0, 8)])).batmaxrate == 12000
    # no stack detected: the inverter's rating
    assert read.getInvModel(_plant("8204", [])).batmaxrate == 12000
