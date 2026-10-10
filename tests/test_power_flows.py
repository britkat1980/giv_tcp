"""Power flow entities: each source shared out in turn, never negative, house flows never above the load"""
import read

def flows(pv=0, load=0, imp=0, exp=0, chg=0, dis=0):
    return read.powerFlows(pv, load, imp, exp, chg, dis)

def test_solar_covers_house_and_battery_grid_tops_up():
    # The hybrid_gen1 capture: same result as before
    f = flows(pv=4921, load=4092, imp=721, chg=937)
    assert (f['Solar_to_House'], f['Solar_to_Battery'], f['Grid_to_Battery'], f['Grid_to_House']) == (4092, 829, 108, 0)

def test_house_flows_never_exceed_load():
    # The all_in_one capture: before, 862 + 54 + 3 = 919W to a 864W house
    f = flows(pv=862, load=864, imp=3, dis=54)
    assert f['Solar_to_House'] + f['Battery_to_House'] + f['Grid_to_House'] <= 864
    assert f['Battery_to_House'] == 2 and f['Grid_to_House'] == 0

def test_grid_to_battery_never_negative():
    # A little import (meter noise) while solar covers more than the battery takes: before, -1000W
    f = flows(pv=3000, load=1000, imp=50, chg=1000)
    assert f['Grid_to_Battery'] == 0 and f['Solar_to_Battery'] == 1000

def test_solar_to_battery_limited_by_charge():
    # Losses or curtailment aren't counted as solar charging a battery that isn't charging
    f = flows(pv=5205, load=378, exp=4458)
    assert f['Solar_to_Battery'] == 0 and f['Solar_to_Grid'] == 4458

def test_force_export_from_battery_and_solar():
    f = flows(pv=1000, load=500, exp=1500, dis=1000)
    assert (f['Solar_to_House'], f['Solar_to_Grid'], f['Battery_to_House'], f['Battery_to_Grid']) == (500, 500, 0, 1000)

def test_battery_covers_house_rest_exported():
    f = flows(pv=200, load=1500, exp=200, dis=1500)
    assert (f['Battery_to_House'], f['Battery_to_Grid']) == (1300, 200)

def test_grid_charging_overnight():
    f = flows(load=500, imp=3500, chg=3000)
    assert (f['Grid_to_House'], f['Grid_to_Battery']) == (500, 3000)

def test_missing_values_count_as_zero():
    assert all(v == 0 for v in read.powerFlows(None, None, None, None, None, None).values())

def test_pv_only_solar_to_house():
    # PV-only inverters: Solar to House was min(PV - export, 0), so never positive
    f = flows(pv=3000, load=1200, exp=1800)
    assert (f['Solar_to_House'], f['Solar_to_Grid']) == (1200, 1800)
