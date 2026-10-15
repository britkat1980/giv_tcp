"""GivTCP's state files: the register cache keeps only the latest output (every reader uses just that, and 31 meant
rewriting ~570KB a poll), and the battery stats are only saved when they change"""
import os
import pickle

from GivLUT import GivLUT

import read

def test_regcache_keeps_latest_only(plants):
    session = plants.get("hybrid_gen2")
    session.activate(session.state)
    session.read_cycle()
    session.read_cycle(refresh=True)
    stack = GivLUT.get_regcache()
    assert len(stack) == 1 and "Stats" in stack[-1]

def test_ratecalcs_gets_previous_output(plants, monkeypatch):
    # With one cached output, the Day/Night costs must still compare with the previous poll (their midnight reset)
    session = plants.get("hybrid_gen2")
    session.activate(session.state)
    previous = GivLUT.get_regcache()[-1]
    seen = []
    real = read.ratecalcs
    def spy(multi_output, multi_output_old, readAt=None):
        seen.append(multi_output_old is multi_output)
        return real(multi_output, multi_output_old, readAt)
    monkeypatch.setattr(read, "ratecalcs", spy)
    session.read_cycle()
    assert seen == [False] and previous

def test_battery_stats_saved_only_when_changed(plants, monkeypatch):
    session = plants.get("hybrid_gen2")
    session.activate(session.state)
    output = session.cycles[1]["output"]
    if os.path.exists(GivLUT.batterypkl):
        os.remove(GivLUT.batterypkl)
    open(GivLUT.firstrun, "w").close()       # not the first run, and the frozen clock (12:00) isn't :29 or :59
    saves = []
    real = pickle.dump
    monkeypatch.setattr(read.pickle, "dump", lambda obj, f, *a: (saves.append(getattr(f, "name", "")), real(obj, f, *a)))
    read.calcBatteryValue(output)            # no stats yet: saved
    read.calcBatteryValue(output)            # unchanged: not saved again
    assert [s for s in saves if s == GivLUT.batterypkl] == [GivLUT.batterypkl]
