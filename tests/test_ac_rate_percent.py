"""Percentage controls use the existing AC minimum, through real dispatch and Modbus.

Capture-backed MockPlant tests. No real inverter, broker or HA is contacted.
The cached rate is an accepted setting, never evidence of physical battery power.
"""
import pytest
from GivLUT import GivLUT
from write import finditem


@pytest.fixture(autouse=True)
def restore_settings_class(monkeypatch):
    import settings

    # Intentionally register the same value: writes reload settings during tests.
    monkeypatch.setattr(settings, "GiV_Settings", settings.GiV_Settings)


def percent_case(plants, api, entry, kind, requested):
    command = "set" + kind.title() + "RateAC"
    target = "/" + command if entry == "rest" else command
    payload = str(requested) if entry == "mqtt" else {kind + "Rate": str(requested)}
    return plants.get("hybrid_3ph").run_case(entry, [(target, payload)], api)[0]


@pytest.mark.parametrize("entry", ["direct", "rest", "mqtt"])
@pytest.mark.parametrize("kind,register", [("charge", 1110), ("discharge", 1108)])
@pytest.mark.parametrize("requested,accepted", [(0, 1), (1, 1), (37, 37), (100, 100)])
def test_percent_rate_minimum_and_normal_values(plants, api, entry, kind, register, requested, accepted):
    outcome = percent_case(plants, api, entry, kind, requested)
    assert outcome["writes"] == [[0x11, register, accepted]]
    assert not outcome["logs"]
    cached = GivLUT.get_regcache()[-1]
    assert cached["Control"]["Battery_" + kind.title() + "_Rate_AC"] == accepted
    assert cached["Control"]["Battery_" + kind.title() + "_Rate"] == int(
        accepted / 100 * finditem(cached, "Invertor_Max_Bat_Rate")
    )


@pytest.mark.parametrize("entry", ["direct", "rest", "mqtt"])
@pytest.mark.parametrize("kind", ["charge", "discharge"])
@pytest.mark.parametrize("requested", [-1, 101])
def test_percent_rate_invalid_bounds_still_rejected(plants, api, entry, kind, requested):
    outcome = percent_case(plants, api, entry, kind, requested)
    assert outcome["writes"] == []
    assert outcome["logs"]
