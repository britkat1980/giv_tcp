"""Fails when GivTCP gains a control that harness/catalogue.py doesn't test, so new controls get covered."""
import inspect
import re

import mqtt
import REST
import write

from harness import catalogue

def test_every_write_function_is_covered():
    # The functions the read loop can dispatch to: func(device, payload, readloop)
    functions = {name for name, f in vars(write).items()
                 if inspect.isfunction(f) and f.__module__ == "write"
                 and list(inspect.signature(f).parameters)[:1] == ["device"]
                 and "readloop" in inspect.signature(f).parameters}
    covered = {step[0] for steps in catalogue.DIRECT.values() for step in steps}
    assert sorted(functions - covered - set(catalogue.DIRECT_SKIP)) == []

def test_every_rest_route_is_covered():
    routes = {r.rule for r in REST.giv_api.url_map.iter_rules() if "POST" in (r.methods or ())}
    covered = {step[0] for steps in catalogue.REST.values() for step in steps}
    assert sorted(routes - covered - set(catalogue.REST_SKIP)) == []

def test_every_mqtt_topic_is_covered():
    topics = set(re.findall(r'command=="(\w+)"', inspect.getsource(mqtt.GivMQTT.on_message)))
    covered = {step[0] for steps in catalogue.MQTT.values() for step in steps}
    assert sorted(topics - covered - set(catalogue.MQTT_SKIP)) == []
