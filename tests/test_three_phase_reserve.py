"""Reserve-control regression using GivTCP's official capture-backed mock plant.

Run inside the GivTCP released source tree, after applying the candidate patch.
No real inverter is contacted.
"""
import pytest
from givenergy_modbus.model.register import HR


@pytest.fixture(autouse=True)
def restore_settings_class(monkeypatch):
    import settings

    # Intentionally register the same value: writes reload settings during tests.
    monkeypatch.setattr(settings, "GiV_Settings", settings.GiV_Settings)


@pytest.mark.parametrize("entry", ["direct", "rest", "mqtt"])
@pytest.mark.parametrize("target", [6, 17, 100])
def test_three_phase_cutoff_writes_runtime_reserve(plants, api, entry, target):
    session = plants.get("hybrid_3ph")
    command = "/setBatteryCutoff" if entry == "rest" else "setBatteryCutoff"
    payload = str(target) if entry == "mqtt" else {"dischargeToPercent": str(target)}
    outcome = session.run_case(entry, [(command, payload)], api)[0]
    assert outcome["writes"] == [[0x11, 1078, target]]
    assert not outcome["logs"]


def test_three_phase_cutoff_rejects_above_100(plants):
    outcome = plants.get("hybrid_3ph").run_case(
        "direct", [("setBatteryCutoff", {"dischargeToPercent": "101"})]
    )[0]
    assert outcome["writes"] == []
    assert "failed" in outcome["result"]["result"].lower()


def test_three_phase_cutoff_readback_uses_runtime_register(plants):
    # The official MockPlant acknowledges writes without changing its capture.
    # This verifies the independent read mapping, not physical write persistence.
    session = plants.get("hybrid_3ph")
    session.activate(session.state)
    output = session.read_cycle()["output"]
    assert output["Control"]["Battery_Power_Cutoff"] == session.plant.register_caches[0x11][HR(1078)]
