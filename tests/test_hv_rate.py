"""HV Gen 3 battery rate: HR111/112 are a percentage of the modules' Ah rating, not their usable kWh (#604)"""
import types

import read
import write
from givenergy_modbus.model.inverter import Model

def hv_plant(stacks, ah=52):
    # stacks: modules in each stack. The 8kW model (8102), whose battery current limit is 25A
    bcu = types.SimpleNamespace(is_valid=lambda: True, battery_nominal_capacity_ah=ah)
    return types.SimpleNamespace(
        capabilities=types.SimpleNamespace(is_ems=False, is_gateway=False, is_three_phase=False,
                                           device_type=Model.HYBRID_HV_GEN3,
                                           bcu_stacks=[(i, n) for i, n in enumerate(stacks)]),
        inverter=types.SimpleNamespace(inverter_max_power=8000, battery_max_power=8000, battery_capacity_kwh=15.96,
                                       device_type_code="8102"),
        hv_stacks=[types.SimpleNamespace(bcu=bcu) for _ in stacks])

def test_three_module_stack():
    # The #604 system: 50% (0.5C) measured at ~5.8kW discharging and ~6.1kW charging, so not 0.5 x 10.2kWh = 5.1kW
    model = read.getInvModel(hv_plant([3]))
    assert model.batmaxrate == 6000
    assert model.batterycapacity == 10.2            # still used for SOC kWh and time remaining
    assert model.ratecapacity == 12.48              # 52Ah x 80V x 3 modules
    assert min(0.50 * model.ratecapacity * 1000, model.batmaxrate) == 6000

def test_6000w_reads_back_as_6000w():
    # Predbat writes 6000W and checks the value read back
    batcap = 12480
    target = write.batteryLimitPercent(6000, batcap, 6000)
    assert target == 49
    assert int(min(target / 100 * batcap, 6000)) == 6000

def test_parallel_stacks_add_up():
    assert read.getInvModel(hv_plant([4, 4])).ratecapacity == 33.28

def test_no_module_ah_falls_back():
    assert read.getInvModel(hv_plant([3], ah=None)).ratecapacity is None

def test_other_models_unchanged():
    lv = types.SimpleNamespace(
        capabilities=types.SimpleNamespace(is_ems=False, is_gateway=False, is_three_phase=False,
                                           device_type=Model.HYBRID_GEN3, bcu_stacks=[]),
        inverter=types.SimpleNamespace(inverter_max_power=5000, battery_max_power=3600, battery_capacity_kwh=9.5))
    model = read.getInvModel(lv)
    assert model.ratecapacity is None and model.batterycapacity == 9.5

def test_write_prefers_the_rate_capacity():
    assert write.batteryCapacityWh({"X": {"Battery_Capacity_kWh": 10.2, "Battery_Rate_Capacity_kWh": 12.48}}) == 12480
    assert write.batteryCapacityWh({"X": {"Battery_Capacity_kWh": 9.5}}) == 9500
