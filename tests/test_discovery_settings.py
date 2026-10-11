"""Discovery options in settings: which Home Assistant entities are created for each timeslot"""
import pytest

import HA_Discovery
from harness.fakes import recorder

SN = "TS0000TEST"
SELECT = "homeassistant/select/GivEnergy/" + SN + "_Charge_start_time_slot_1/config"
TIME = "homeassistant/time/GivEnergy/" + SN + "_Charge_start_time_slot_1/config"
OTHER = "homeassistant/select/GivEnergy/" + SN + "_Battery_pause_mode/config"

@pytest.mark.parametrize("setting, published, removed", [
    ("both", {SELECT, TIME}, set()),
    (None, {SELECT, TIME}, set()),          # older settings files don't have it
    ("time", {TIME}, {SELECT}),
    ("dropdown", {SELECT}, {TIME}),
])
def test_timeslot_entities(monkeypatch, setting, published, removed):
    monkeypatch.setattr(HA_Discovery.GiV_Settings, "timeslot_entities", setting, raising=False)
    recorder.clear()
    array = {"Stats": {"Invertor_Type": "Hybrid_gen1"},
             "Control": {"Charge_start_time_slot_1": "01:00:00", "Battery_pause_mode": "Disabled"}}
    HA_Discovery.HAMQTT.publish_discovery2(array, SN)
    sent = {topic for topic, _ in recorder.discovery}
    assert sent & {SELECT, TIME} == published
    assert OTHER in sent                    # other drop-downs are unaffected
    assert set(recorder.removed) == removed
