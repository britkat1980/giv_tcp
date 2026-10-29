"""The most a battery can be charged or discharged at: the rate registers (HR 111/112) are a percentage of the battery's
capacity, at most 50%, so a small battery can't take the inverter's full rate (#679)"""
from types import SimpleNamespace

from givenergy_modbus.model.inverter import Model
from givenergy_modbus.model.plant import PlantCapabilities

import read
import write

def plant(model, kwh, batmax=3600, invmax=3600, **caps):
    inv = SimpleNamespace(inverter_max_power=invmax, battery_max_power=batmax, battery_capacity_kwh=kwh, device_type_code="2001")
    return SimpleNamespace(capabilities=PlantCapabilities(device_type=model, **caps), inverter=inv)

def test_small_battery_capped_at_half_its_capacity():
    # The reporter's Gen 3 3.6kW with a 5.22kWh battery: 2611W, as GivTCP 2.x reported, not 3600W
    assert read.getInvModel(plant(Model.HYBRID_GEN3, 5.222, lv_battery_addresses=[0x32])).batmaxrate == 2611

def test_large_battery_keeps_the_inverter_rating():
    assert read.getInvModel(plant(Model.HYBRID_GEN3, 9.5, lv_battery_addresses=[0x32])).batmaxrate == 3600

def test_reply_says_what_was_set():
    assert write.rateApplied(3600, 2611) == " (set to 2611W: the rate is a whole percentage of the battery's capacity, at most 50%)"
    assert write.rateApplied(2000, 2000) == "" and write.rateApplied(2000, None) == ""
