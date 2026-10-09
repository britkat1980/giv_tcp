"""Giving an inverter that stops responding time to recover (recovery_pause), driven on a simulated clock"""
import asyncio
import datetime as _dt
import types

import pytest
from givenergy_modbus.exceptions import CommunicationError

import read

START = _dt.datetime(2026, 6, 15, 12, 0, 0)

class Stop(BaseException):
    """Ends watch_plant's endless loop (BaseException, so the loop's own handlers don't catch it)"""

class Sim:
    def __init__(self, monkeypatch, reads, connects=(), horizon=1500):
        self.t = START
        self.horizon = START + _dt.timedelta(seconds=horizon)
        self.reads = list(reads)          # outcome of each readPlant: True = ok, False = no response
        self.connects = list(connects)    # outcome of each reconnect, after the first connection
        self.read_times = []
        self.connect_times = []
        self.closes = 0
        sim = self

        class Clock(_dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return sim.t.replace(tzinfo=tz) if tz else sim.t
        clock = types.ModuleType("datetime")
        clock.__dict__.update(vars(_dt))
        clock.datetime = Clock
        monkeypatch.setattr(read, "datetime", clock)

        async def sleep(seconds, result=None):
            sim.t += _dt.timedelta(seconds=seconds)
            if sim.t > sim.horizon:
                raise Stop()
        monkeypatch.setattr(read, "asyncio", types.SimpleNamespace(sleep=sleep))

        class Client:
            connected = True
            plant = types.SimpleNamespace(register_block_updated_at={}, capabilities=types.SimpleNamespace(is_gateway=False))
            async def load_config(self):
                pass
            async def close(self):
                self.connected = False
                sim.closes += 1
        self.client = Client()

        async def get_connection(cold_start=False, reconnect=False):
            if reconnect:
                sim.connect_times.append(sim.elapsed())
                if sim.connects and not sim.connects.pop(0):
                    raise CommunicationError("no response")
            self.client.connected = True
            return self.client
        async def new_client():
            return self.client
        monkeypatch.setattr(read.GivClientAsync, "get_connection", get_connection)
        monkeypatch.setattr(read.GivClientAsync, "new_client", new_client)

        async def detect(client, force=False):
            return False
        async def read_plant(client, full):
            sim.read_times.append(sim.elapsed())
            ok = sim.reads.pop(0) if sim.reads else True
            if not ok:
                raise CommunicationError("no response")
            return []
        async def no_writes(client):
            return False
        monkeypatch.setattr(read, "detectPlant", detect)
        monkeypatch.setattr(read, "readPlant", read_plant)
        monkeypatch.setattr(read, "processWriteRequests", no_writes)
        monkeypatch.setattr(read, "commsFailure", lambda: 0)

    def elapsed(self):
        return round((self.t - START).total_seconds())

    def run(self, pause):
        with pytest.raises(Stop):
            asyncio.run(read.watch_plant(refresh_period=60, full_refresh_period=600, recovery=read.Recovery(pause)))

def test_off_by_default_retries_sooner_as_before(monkeypatch):
    sim = Sim(monkeypatch, reads=[True, True, False, False, True], horizon=200)
    sim.run(pause=0)
    # 120s fails, retried after 2s, fails, retried after 4s
    assert sim.read_times[:5] == [0, 60, 120, 122, 126]
    assert sim.closes == 0

def test_failed_poll_waits_a_normal_interval_then_pauses(monkeypatch, caplog):
    sim = Sim(monkeypatch, reads=[True, True, False, False, True, True])
    sim.run(pause=600)
    # 120s fails, retried at the normal 180s, fails again: nothing at all for 600s, then reconnect and poll at 780s
    assert sim.read_times[:6] == [0, 60, 120, 180, 780, 840]
    assert sim.closes == 1
    assert sim.connect_times[0] == 780
    messages = [r.getMessage() for r in caplog.records]
    assert any("sending it nothing for 600s" in m for m in messages)
    assert any("Recovery pause over" in m for m in messages)

def test_one_failure_between_good_polls_doesnt_pause(monkeypatch):
    sim = Sim(monkeypatch, reads=[True, False, True, False, True], horizon=300)
    sim.run(pause=600)
    assert sim.read_times[:5] == [0, 60, 120, 180, 240]
    assert sim.closes == 0

def test_failed_reconnects_wait_then_pause(monkeypatch):
    # The connection drops after the first poll, then two reconnects fail
    sim = Sim(monkeypatch, reads=[True], connects=[False, False, True])
    sim.client.connected = True
    async def drop_after_read(client, full):
        sim.read_times.append(sim.elapsed())
        client.connected = False
        return []
    monkeypatch.setattr(read, "readPlant", drop_after_read)
    sim.run(pause=600)
    # Reconnect at 60s fails, again a normal interval later (120s), then nothing until 720s
    assert sim.connect_times[:3] == [60, 120, 720]
    assert sim.read_times[:2] == [0, 720]

def test_recovery_counts_and_resets():
    r = read.Recovery(0)
    assert not r.enabled and not r.failed() and not r.failed()
    r = read.Recovery(300)
    assert not r.failed()
    r.ok()
    assert not r.failed()
    assert r.failed() and r.until is not None
    assert r.strikes == 0

def test_writes_during_pause(tmp_path, monkeypatch):
    """REST writes are answered straight away rather than left to time out (callers like Predbat retry, and the
    retries would all be sent when the pause ends). Other commands, eg. the end of a force charge, are kept for
    after the pause, without exact duplicates"""
    import json
    import pickle
    from GivLUT import GivLUT
    monkeypatch.setattr(GivLUT, "writerequests", str(tmp_path / "writerequests.pkl"))
    monkeypatch.setattr(GivLUT, "restresponse", str(tmp_path / "restresponse.json"))
    revert = ["FCResume", {"chargeRate": 3000}, False]
    GivLUT.save_writerequests([["setChargeRate", {"chargeRate": "6000"}, True], revert, revert,
                               ["setChargeRate", {"chargeRate": "6000"}, True], ["enableChargeSchedule", {"state": "enable"}, False]])
    read.holdWrites(420)
    with open(GivLUT.writerequests, "rb") as inp:
        assert pickle.load(inp) == [revert, ["enableChargeSchedule", {"state": "enable"}, False]]
    with open(GivLUT.restresponse) as inp:
        responses = json.load(inp)
    assert [r["id"] for r in responses] == ["setChargeRate", "setChargeRate"]
    assert "not sent" in responses[0]["result"] and "420s" in responses[0]["result"]

def test_pause_publishes_status_and_counts_once(monkeypatch):
    from harness import fakes
    counts = []
    sim = Sim(monkeypatch, reads=[True], connects=[False, False, True])
    monkeypatch.setattr(read, "commsFailure", lambda: counts.append(1) or len(counts))
    monkeypatch.setattr(read.GiV_Settings, "MQTT_Output", True, raising=False)
    async def drop_after_read(client, full):
        sim.read_times.append(sim.elapsed())
        client.connected = False
        return []
    monkeypatch.setattr(read, "readPlant", drop_after_read)
    fakes.recorder.clear()
    sim.run(pause=600)
    assert len(counts) == 1           # one pause, not one per failed reconnect
    assert [p for t, p in fakes.recorder.mqtt if t.endswith("/Stats/status")] == ["paused"]

def test_pause_happens_when_closing_the_dead_connection_fails(monkeypatch):
    # On a dead socket close() can raise (#613). That mustn't skip the pause and end the loop
    sim = Sim(monkeypatch, reads=[True, True, False, False, True, True])
    async def failing_close():
        sim.closes += 1
        raise TimeoutError(110, "Operation timed out")
    sim.client.close = failing_close
    sim.run(pause=600)
    assert sim.read_times[:5] == [0, 60, 120, 180, 780]
