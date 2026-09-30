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
