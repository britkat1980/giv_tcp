"""Battery Only (per inverter, eg. All-in-Ones behind a Gateway): leave out the power and energy the Gateway or EMS
also reports, and keep the batteries, controls, the device's own details and status (#591, #634)"""
from harness.fakes import recorder

import read

def test_published_groups(plants, monkeypatch):
    session = plants.get("all_in_one")
    output = session.cycles[1]["output"]
    sn = next(k for k, v in output.items() if isinstance(v, dict) and "Invertor_Time" in v)
    monkeypatch.setattr(read.GiV_Settings, "Battery_Only", True, raising=False)
    monkeypatch.setattr(read.GiV_Settings, "HA_Auto_D", False, raising=False)
    recorder.clear()
    read.publishOutput(output, sn)
    groups = {topic.split("/")[2] for topic, _ in recorder.mqtt}
    assert groups == {"Battery_Details", "Control", "Timeslots", "Stats", sn}
    assert "GivEnergy/" + sn + "/" + sn + "/Invertor_Time" in {topic for topic, _ in recorder.mqtt}
