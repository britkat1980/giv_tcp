"""Files GivTCP's processes share: the register cache (saved in one step, changed under a lock), the revert jobs of
Force Charge/Export and the temporary pauses, and the battery value calculation's twice-hourly run"""
import datetime
import glob
import os
import pickle

import pytest

import harness.fakes as fakes
from GivLUT import GivLUT

import read

@pytest.fixture
def cache_files(tmp_path, monkeypatch):
    monkeypatch.setattr(GivLUT, "regcache", str(tmp_path / "regCache_1.pkl"))
    monkeypatch.setattr(GivLUT, "cachelockfile", str(tmp_path / ".regcache_lockfile_1"))
    return tmp_path

def test_regcache_saved_whole_and_updated_under_lock(cache_files):
    assert GivLUT.get_regcache() is None
    GivLUT.put_regcache([{"Control": {"Force_Charge": "Normal"}, "Stats": {"status": "online"}}])
    assert not glob.glob(str(cache_files / "*.tmp"))            # written to a temporary file, then renamed into place
    assert GivLUT.get_regcache()[-1]["Control"]["Force_Charge"] == "Normal"
    GivLUT.update_regcache(lambda output: output["Control"].update(Force_Charge="Running"))
    assert GivLUT.get_regcache()[-1]["Control"]["Force_Charge"] == "Running"
    with GivLUT.fileLock(GivLUT.cachelockfile):                 # the lock file is only a handle: it's left in place
        pass
    assert os.path.exists(GivLUT.cachelockfile)

def test_regcache_unreadable(cache_files):
    with open(GivLUT.regcache, "wb") as f:
        f.write(b"not a pickle")
    assert GivLUT.get_regcache() is None                        # moved aside, so it's rebuilt

@pytest.fixture
def jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

def test_running_job(jobs):
    assert GivLUT.runningJob("forceCharge") is None and GivLUT.jobMinutesLeft("forceCharge") == 0
    finish = datetime.datetime.now() + datetime.timedelta(minutes=30)
    GivLUT.saveRunningJob("forceCharge", "job1", finish)
    assert GivLUT.runningJob("forceCharge") == ("job1", finish.replace(microsecond=0))
    assert GivLUT.jobMinutesLeft("forceCharge") in (30, 31)
    assert GivLUT.runningJob("forceExport") is None
    GivLUT.clearRunningJob("forceCharge")
    GivLUT.clearRunningJob("forceCharge")                       # already gone: no error
    assert GivLUT.runningJob("forceCharge") is None

def test_job_running_past_midnight(jobs):
    # The finish time was saved as HH:MM, which showed 0 minutes left for a job running past midnight
    finish = datetime.datetime.now() + datetime.timedelta(hours=23, minutes=50)    # tomorrow, whatever the time now
    GivLUT.saveRunningJob("tempPauseCharge", "job2", finish)
    assert GivLUT.jobMinutesLeft("tempPauseCharge") >= 23 * 60
    # A job saved by 3.6.6 or earlier (HH:MM) that's already finished today is taken as finishing tomorrow
    earlier = (datetime.datetime.now() - datetime.timedelta(minutes=10)).strftime("%H:%M")
    with open(GivLUT.jobFile("tempPauseDischarge"), "w") as f:
        f.write("job3\n" + earlier)
    jobid, legacy = GivLUT.runningJob("tempPauseDischarge")
    assert jobid == "job3" and legacy > datetime.datetime.now()

def test_battery_value_once_a_half_hour(plants, monkeypatch):
    session = plants.get("hybrid_gen2")
    session.activate(session.state)
    output = session.cycles[1]["output"]
    output["Energy"].setdefault("Rates", {})["Current_Rate"] = 0.25
    with open(GivLUT.batterypkl, "wb") as f:
        pickle.dump({"AC Charge last": 0.0, "Battery_Value": 1.0, "Battery_ppkwh": 0.2, "Battery_kWh_old": 1.0}, f)
    open(GivLUT.firstrun, "w").close()
    monkeypatch.setattr(fakes, "FROZEN_NOW", datetime.datetime(2026, 6, 15, 12, 29, 5))
    read.calcBatteryValue(output)
    first = pickle.load(open(GivLUT.batterypkl, "rb"))
    assert first["Last_Calculated"] == "2026-06-15 12:29"
    monkeypatch.setattr(fakes, "FROZEN_NOW", datetime.datetime(2026, 6, 15, 12, 29, 35))    # another poll in the minute
    read.calcBatteryValue(output)
    assert pickle.load(open(GivLUT.batterypkl, "rb")) == first
