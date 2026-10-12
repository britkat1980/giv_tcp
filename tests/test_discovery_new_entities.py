"""Discovery for data that appears after the first output: LV battery modules, which the library only gives once a
second read confirms them, so they weren't in the output discovery ran on (#629)"""
import copy
import os

from harness.fakes import recorder

import GivLUT
import read

def battery_topics():
    return {t for t, _ in recorder.discovery if "_Battery_Cell_1_Voltage/" in t}

def test_battery_modules_discovered_when_they_appear(plants):
    session = plants.get("hybrid_gen1")
    full = session.cycles[1]["output"]
    sn = next(k for k, v in full.items() if isinstance(v, dict) and "Invertor_Type" in v)
    modules = [k for k, v in full["Battery_Details"]["Battery_Stack_1"].items() if isinstance(v, dict)]
    assert len(modules) == 2
    first = copy.deepcopy(full)
    for module in modules:
        del first["Battery_Details"]["Battery_Stack_1"][module]
    session.activate(session.state)
    if os.path.exists(GivLUT.GivLUT.firstrun):
        os.remove(GivLUT.GivLUT.firstrun)
    read.discoveredPaths.pop(sn, None)

    read.publishOutput(first, sn)          # first output: discovery without the modules
    assert recorder.discovery and not battery_topics()

    recorder.clear()
    read.publishOutput(full, sn)           # the modules have been read: discovery for just them
    assert {t.split("/")[3].split("_Battery_Cell")[0] for t in battery_topics()} == {sn + "_" + m for m in modules}
    assert not [t for t, _ in recorder.discovery if t.endswith("_Grid_Power/config")]

    recorder.clear()
    read.publishOutput(full, sn)           # nothing new
    assert not recorder.discovery
