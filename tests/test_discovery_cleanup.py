"""removedisco only clears discovery messages on a V3 upgrade, while the MQTT client's thread keeps adding to
CheckDisco.msgs (#609). Otherwise changed configs are updated in place, keeping entity IDs and customisations"""
import HA_Discovery
from harness import fakes

SN = "SA1234G567"
TOPIC = "homeassistant/sensor/GivEnergy/" + SN + "_PV_Power/config"

class RetainedBroker:
    """Stands in for the paho client: delivers the retained messages, and a new state topic on every publish"""
    def __init__(self, retained):
        self.retained = retained
        self.published = []
        self.on_connect = self.on_message = None
        self.stopped = False

    def username_pw_set(self, *a): pass
    def connect(self, *a): pass
    def disconnect(self): pass
    def loop_stop(self): self.stopped = True

    def loop_start(self):
        for topic, payload in self.retained.items():
            self.deliver(topic, payload)

    def deliver(self, topic, payload):
        self.on_message(self, None, type("Msg", (), {"topic": topic, "payload": payload.encode()})())

    def publish(self, topic, payload, qos, retain):
        self.published.append(topic)
        # GivTCP's own state messages keep arriving while removedisco works through the retained ones
        self.deliver("GivEnergy/" + SN + "/new_" + str(len(self.published)), "1")

def run(monkeypatch, retained, sent, v3upgrade):
    broker = RetainedBroker(retained)
    clients = []
    monkeypatch.setattr(HA_Discovery.paho_mqtt, "Client", lambda *a, **k: clients.append(1) or broker)
    monkeypatch.setattr(HA_Discovery, "exists", lambda path: v3upgrade and ".v3upgrade_" in path)
    logged = []
    monkeypatch.setattr(HA_Discovery.logger, "error", logged.append)
    HA_Discovery.CheckDisco.msgs = {}           # starts empty, as on a fresh start
    fakes.real["removedisco"](SN, sent)
    return broker, logged, clients

def test_changed_configs_not_deleted(monkeypatch):
    # Deleting a changed config made HA delete and recreate the entity, resetting a legacy or renamed entity ID (and
    # customisations). Every temperature sensor was hit on every restart, as its °C never compared equal
    retained = {TOPIC: '{"name": "old", "unit_of_meas": "\u00b0C"}'}
    broker, logged, clients = run(monkeypatch, retained, [[TOPIC, '{"name": "new", "unit_of_meas": "\u00b0C"}']], v3upgrade=False)
    assert logged == [] and broker.published == [] and clients == []      # doesn't even connect

def test_v3_upgrade_drops_old_messages_while_new_ones_arrive(monkeypatch):
    other = "homeassistant/sensor/GivEnergy/" + SN + "_Other/config"
    broker, logged, clients = run(monkeypatch, {TOPIC: '{"name": "old"}', other: '{"name": "same"}'}, [], v3upgrade=True)
    assert logged == []
    assert sorted(broker.published) == sorted([TOPIC, other])
    assert TOPIC not in HA_Discovery.CheckDisco.msgs      # so checkdisco waits for the new one
    assert broker.stopped

def test_unsupported_log_names_only_what_was_removed(monkeypatch):
    # #612: the log listed every entity this model can't have, with a count of what was actually removed
    retained = {"homeassistant/sensor/GivEnergy/" + SN + "_PV_Voltage_String_1/config": "{}",
                "GivEnergy/" + SN + "/Power/Power/PV_Voltage_String_1": "0",
                "homeassistant/sensor/GivEnergy/" + SN + "_Grid_Voltage/config": "{}"}
    broker = RetainedBroker(retained)
    broker.publish = lambda topic, payload, qos, retain: broker.published.append(topic)
    monkeypatch.setattr(HA_Discovery.paho_mqtt, "Client", lambda *a, **k: broker)
    info = []
    monkeypatch.setattr(HA_Discovery.logger, "info", info.append)
    fakes.real["removeunsupported"](SN, ["PV_Voltage_String_1", "PV_Current_String_1", "Battery_BMS_Current"])
    assert sorted(broker.published) == sorted(t for t in retained if "PV_Voltage" in t)
    assert info == ["Removed 2 retained MQTT messages for entities not supported by this inverter: PV_Voltage_String_1"]

def test_unsupported_entities_not_published_again():
    # #612: removeunsupported() cleared them, then discovery created them again, every restart
    fakes.recorder.clear()
    array = {"Power": {"Power": {"Grid_Voltage": 240.0, "PV_Voltage_String_1": 0.0}}, "Stats": {}}
    HA_Discovery.HAMQTT.publish_discovery2(array, SN, ["PV_Voltage_String_1"])
    topics = [t for t, _ in fakes.recorder.discovery]
    assert any(t.endswith("_Grid_Voltage/config") for t in topics)
    assert not any("PV_Voltage_String_1" in t for t in topics)
