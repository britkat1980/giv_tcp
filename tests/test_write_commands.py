"""Every control on every device model, through each entry point, compared with tests/golden/<model>.json.

direct: the write.py function, called as the read loop calls it
rest:   POST to the REST API; the read loop runs the queued command and the response comes back to the caller
mqtt:   a message on the control topic; the read loop runs the queued command

Each result records GivTCP's reply, the registers written to the plant, any revert jobs scheduled and any
warnings or errors logged.
"""
import pytest

from harness import catalogue, golden
from harness.devices import DEVICES

MODELS = list(DEVICES)

@pytest.mark.parametrize("case", list(catalogue.DIRECT))
@pytest.mark.parametrize("model", MODELS)
def test_direct(plants, model, case):
    golden.check(model, "direct", case, plants.get(model).run_case("direct", catalogue.DIRECT[case]))

@pytest.mark.parametrize("case", list(catalogue.REST))
@pytest.mark.parametrize("model", MODELS)
def test_rest(plants, api, model, case):
    golden.check(model, "rest", case, plants.get(model).run_case("rest", catalogue.REST[case], api))

@pytest.mark.parametrize("case", list(catalogue.MQTT))
@pytest.mark.parametrize("model", MODELS)
def test_mqtt(plants, model, case):
    golden.check(model, "mqtt", case, plants.get(model).run_case("mqtt", catalogue.MQTT[case]))

CHARGE_TARGET_MODELS = [m for m in MODELS if m != "ems"]

def _target_register(model):
    return 1111 if model == "hybrid_3ph" else 116

@pytest.mark.parametrize("target", ["85", "100"])
@pytest.mark.parametrize("model", CHARGE_TARGET_MODELS)
def test_set_charge_target_writes_only_the_target(plants, model, target):
    """Setting the charge target writes the target and nothing else, as before v2. set_charge_target_enabled()
    would also turn on the charge schedule, and for 100% clear the charge target's enable flag (HR 20)"""
    outcome = plants.get(model).run_case("direct", [("setChargeTarget", {"chargeToPercent": target})])
    assert outcome[0]["writes"] == [[0x11, _target_register(model), int(target)]]

@pytest.mark.parametrize("model", CHARGE_TARGET_MODELS)
def test_enable_charge_target_writes_only_the_enable_flag(plants, model):
    """Enabling the charge target sets HR 20 and nothing else, whatever the current target. Most test captures
    have a 100% target, where set_charge_target_enabled() would clear HR 20 instead"""
    outcome = plants.get(model).run_case("direct", [("enableChargeTarget", {"state": "enable"})])
    assert outcome[0]["writes"] == [[0x11, 20, 1]]

@pytest.mark.parametrize("model", CHARGE_TARGET_MODELS)
def test_enable_charge_target_keeps_a_target_set_in_the_same_batch(plants, model):
    """Predbat sets a target, then enables the charge target, and the two can reach the read loop as one batch.
    The device is built once per batch, so the enable sees the target from before it. It must leave the new
    target and the enable flag in place, and publish the enabled state straight away"""
    outcome = plants.get(model).run_batch([("setChargeTarget", {"chargeToPercent": "98"}),
                                           ("enableChargeTarget", {"state": "enable"})])
    last = {register: value for _, register, value in outcome["writes"]}
    assert last[_target_register(model)] == 98      # set by setChargeTarget, and not put back afterwards
    assert last[20] == 1
    assert [t for t, p in outcome["mqtt"] if t.endswith("/Control/Enable_Charge_Target") and p == "enable"]
    assert not outcome["logs"]

@pytest.mark.parametrize("model", CHARGE_TARGET_MODELS)
def test_disable_charge_target_publishes_the_new_state(plants, model):
    """Disabling the charge target also sets the target to 100%, and publishes both straight away, so a consumer
    reading them back doesn't have to wait for the next full read"""
    outcome = plants.get(model).run_batch([("enableChargeTarget", {"state": "disable"})])
    assert outcome["writes"] == [[0x11, 20, 0], [0x11, _target_register(model), 100]]
    published = {t.rsplit("/Control/", 1)[1]: p for t, p in outcome["mqtt"] if "/Control/" in t}
    assert published.get("Enable_Charge_Target") == "disable"
    assert published.get("Target_SOC") == "100"
    assert not outcome["logs"]
