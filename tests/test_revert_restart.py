"""Timed reverts (Force Export/Charge, Temp Pause) are scheduled in Redis, which a restart clears, so a restart before
one is due (eg. another inverter's lost connection restarting the container) left the forced settings in place.
A copy is kept outside Redis, and the read loop runs any revert that came due while it was down, or reschedules it"""
import datetime as _dt
import os

import GivLUT as givlut_module
import read
import write
from GivLUT import GivLUT
from harness.fakes import FakeQueue, recorder

def restart():
    # Redis, and the jobs scheduled in it, don't survive a restart
    givlut_module.GivQueue.q = FakeQueue()

def set_due(command, due):
    pending = write.loadPendingReverts()
    pending[command]["due"] = due
    write.savePendingReverts(pending)

def force_export(session):
    if os.path.exists(write.pendingRevertsFile()):
        os.remove(write.pendingRevertsFile())
    outcome = session.run_case("direct", [("forceExport", 10)])[0]
    assert "successfully" in outcome["result"]["result"]
    return write.loadPendingReverts()["FEResume"]

def test_force_export_keeps_its_revert(plants):
    pending = force_export(plants.get("hybrid_gen2"))
    assert pending["due"] == write.datetime.now() + _dt.timedelta(minutes=10)
    assert pending["payload"]["start_time"]     # the slot to put back

def test_revert_due_during_restart_runs_on_start(plants):
    session = plants.get("hybrid_gen2")
    force_export(session)
    restart()
    set_due("FEResume", write.datetime.now() - _dt.timedelta(minutes=1))
    recorder.clear()
    write.recoverReverts()
    session.loop.run(read.processWriteRequests(session.client))
    logs = [l[2] for l in recorder.logs]
    assert any("restarted before it ran" in l for l in logs)
    assert not any("Revert failed" in l for l in logs)
    assert "FEResume" not in write.loadPendingReverts()
    assert GivLUT.runningJob("forceExport") is None

def test_revert_not_yet_due_is_rescheduled(plants):
    session = plants.get("hybrid_gen2")
    force_export(session)
    restart()
    set_due("FEResume", write.datetime.now() + _dt.timedelta(minutes=4))
    recorder.clear()
    write.recoverReverts()
    assert recorder.jobs and recorder.jobs[-1][0] == 240 and recorder.jobs[-1][2][0] == "FEResume"
    pending = write.loadPendingReverts()["FEResume"]
    assert pending["job"] in givlut_module.GivQueue.q.scheduled_job_registry
    assert not os.path.exists(GivLUT.writerequests)      # nothing run early

def test_revert_still_in_redis_is_left_alone(plants):
    force_export(plants.get("hybrid_gen2"))
    recorder.clear()
    write.recoverReverts()       # no restart, so the scheduled job still runs as normal
    assert not recorder.jobs and not os.path.exists(GivLUT.writerequests)

def test_second_force_export_after_restart_keeps_original_settings(plants):
    # Forcing again while one runs reverts to the settings from before the first, which came from the Redis job
    session = plants.get("hybrid_gen2")
    first = force_export(session)
    restart()
    outcome = session.run_case("direct", [("forceExport", 20)])[0]
    assert "successfully" in outcome["result"]["result"]
    assert write.loadPendingReverts()["FEResume"]["payload"] == first["payload"]

def test_startup_keeps_pending_reverts():
    # Startup clears the cache folder, which is also where the pending reverts are kept
    from startfiles import keptOnStart
    assert keptOnStart(os.path.basename(write.pendingRevertsFile()))
    assert keptOnStart("CH2309G018_caps.pkl") and keptOnStart("allsettings.json") and keptOnStart("rateData_1.pkl")
    assert not keptOnStart("regCache_1.pkl") and not keptOnStart("lastUpdate_1.pkl") and not keptOnStart("battery_1.pkl")
