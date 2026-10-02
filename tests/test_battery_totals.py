"""Lifetime battery charge/discharge come from the battery's BMS or the inverter, depending on firmware (#600)"""
import types

import read

def inv(routed=None, alt1=None):
    return types.SimpleNamespace(e_battery_charge_total=routed, e_battery_discharge_total=routed,
                                 e_battery_charge_total_alt1=alt1, e_battery_discharge_total_alt1=alt1)

def bat(total):
    return types.SimpleNamespace(e_battery_charge_total=total, e_battery_discharge_total=total)

def test_battery_first():
    # The #600 Gen 1: the inverter's IR180/181 read 0, the battery holds the totals (as 3.5 used)
    assert read.batteryTotals(inv(routed=0.0, alt1=0.0), bat(1800.0)) == (1800.0, 1800.0)

def test_inverter_when_battery_is_zero():
    # Gen 1 fw 449 (hybrid_gen1 capture): the BMS reads 0, the inverter holds them
    assert read.batteryTotals(inv(routed=1843.0, alt1=1843.0), bat(0.0)) == (1843.0, 1843.0)

def test_inverter_unrouted_model():
    # The library only routes the inverter totals for Gen 1, so other models fall back to IR180/181 directly
    assert read.batteryTotals(inv(routed=None, alt1=12.5), bat(0.0)) == (12.5, 12.5)

def test_nothing_anywhere():
    charge, discharge = read.batteryTotals(inv(routed=None, alt1=0.0), bat(0.0))
    assert not charge and not discharge      # processInverterInfo then leaves them out rather than publish 0
