"""Device captures for the test library (the Share Device page): requested over REST, run by the read loop"""
import asyncio
import json
import os
import re
from urllib.parse import parse_qs, urlparse

import pytest

import capture

@pytest.fixture
def capture_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "CAPTURE_DIR", str(tmp_path / "captures"))
    monkeypatch.setattr(capture.GiV_Settings, "cache_location", str(tmp_path), raising=False)
    return tmp_path

class FakeClient:
    """capture_frames() hands the sink a few (already redacted) frames, as the library does"""
    def __init__(self, frames):
        self.frames = frames
    async def capture_frames(self, sink, duration=60.0):
        for direction, frame in self.frames:
            sink(direction, frame)

def test_request_pending_status(capture_dirs):
    assert capture.status() == {"state": "idle"}
    st = capture.request(90)
    assert st["state"] == "requested" and st["seconds"] == 90
    assert capture.request(300)["seconds"] == 90           # one at a time: the first is still waiting
    assert capture.pending() == {"seconds": 90}
    assert capture.pending() is None                        # taken off the queue
    assert capture.request(5000) == capture.status()        # still requested until the read loop runs it

def test_request_limits(capture_dirs):
    assert capture.request(5)["seconds"] == 30
    capture.pending(); os.remove(capture.status_file())
    assert capture.request(5000)["seconds"] == capture.MAX_SECONDS

def test_run_writes_capture_and_issue_link(capture_dirs):
    frames = [("tx", bytes.fromhex("5959000100")), ("rx", bytes.fromhex("59590001009e01"))]
    summary = {"model": "HYBRID_GEN2", "device_type_code": "2001", "arm_firmware": "920", "lv_batteries": 1, "battery_stacks": []}
    asyncio.run(capture.run(FakeClient(frames), 30, lambda: summary))
    st = capture.status()
    assert st["state"] == "done" and st["frames"] == 2
    assert re.fullmatch(r"hybrid_gen2_arm920_\d{8}-\d{4}\.log", st["file"])
    lines = open(os.path.join(capture.CAPTURE_DIR, st["file"])).read().splitlines()
    # The format givenergy-cli writes and MockPlant.from_capture() reads: "<timestamp> <rx|tx> <hex>"
    assert [l.split(" ", 1)[1] for l in lines] == ["tx 5959000100", "rx 59590001009e01"]
    assert not os.path.exists(os.path.join(capture.CAPTURE_DIR, "capturing_" + str(capture.GiV_Settings.givtcp_instance) + ".log"))
    query = parse_qs(urlparse(st["issue_url"]).query)
    assert query["title"] == ["Device capture: HYBRID_GEN2 (ARM 920)"]
    assert st["file"] in query["body"][0] and "| Lv batteries | 1 |" in query["body"][0]

def test_run_failure_reported(capture_dirs):
    class Broken:
        async def capture_frames(self, sink, duration=60.0):
            raise RuntimeError("a frame capture is already running on this client")
    asyncio.run(capture.run(Broken(), 30, lambda: {}))
    st = capture.status()
    assert st["state"] == "error" and "already running" in st["error"]

def test_summary_has_no_serials(plants):
    session = plants.get("hybrid_gen2")
    summary = capture.device_summary(session.plant)
    assert summary["model"] == "HYBRID_GEN2" and summary["lv_batteries"] == 1
    assert "arm_firmware" in summary and "battery_firmware" in summary
    text = json.dumps(summary)
    assert session.plant.inverter.serial_number not in text
    assert not any(b.serial_number in text for b in session.plant.batteries if b.serial_number)

def test_rest_request(api, capture_dirs):
    reply = api.post("/captureDevice", json={"seconds": 120})
    assert reply.status_code == 200 and reply.get_json()["state"] == "requested"
    assert capture.pending() == {"seconds": 120}
    assert api.get("/captureStatus").get_json()["state"] == "requested"

def test_real_capture_is_redacted_and_loads(plants, capture_dirs):
    # givenergy-modbus's own capture_frames() on GivTCP's client, during a full read of the mock inverter
    import read
    from givenergy_modbus.testing import MockPlant
    session = plants.get("hybrid_gen2")
    session.activate(session.state)
    async def capture_during_read():
        task = asyncio.create_task(capture.run(session.client, 3, lambda: capture.device_summary(session.plant)))
        await asyncio.sleep(0.2)
        await read.readPlant(session.client, True)
        await task
    session.loop.run(capture_during_read())
    st = capture.status()
    assert st["state"] == "done" and st["frames"] > 0
    path = os.path.join(capture.CAPTURE_DIR, st["file"])
    # The library redacts serials before the file is written: the model prefix and manufacture date are kept
    # and the unit digits zeroed (EA2302G123 becomes EA2302G000)
    text = bytes.fromhex("".join(line.split()[2] for line in open(path))).decode("latin1")
    serials = re.findall(r"[A-Z]{2}\d{4}[A-Z]\d{3}", text)
    assert serials and all(s.endswith("000") for s in serials)
    mock = MockPlant.from_capture(path)                          # usable as a new test device
    assert mock is not None

def test_default_length(monkeypatch):
    # One full-refresh period plus a poll, within 120-600s
    for timer, full, expected in ((30, 120, 150), (90, 270, 360), (15, 60, 120), (300, 600, 600)):
        monkeypatch.setattr(capture.GiV_Settings, "self_run_timer", timer, raising=False)
        monkeypatch.setattr(capture.GiV_Settings, "self_run_timer_full", full, raising=False)
        assert capture.default_seconds() == expected

def test_interrupted_capture_doesnt_block(capture_dirs):
    # GivTCP restarted mid-capture: the status was left as running, and a new capture must still be possible
    capture._write_status({"state": "running", "seconds": 150, "started": "2026-01-01T00:00:00+00:00"})
    assert capture.status()["state"] == "error"
    assert capture.request(150)["state"] == "requested"

def test_startup_keeps_folders():
    # startup.py clears old cache files from /config/GivTCP, and failed on the captures folder (IsADirectoryError)
    import pathlib
    src = (pathlib.Path(__file__).parent.parent / "startup.py").read_text(encoding="utf-8")
    loop = src[src.index('for file in os.listdir(setts["cache_location"]):'):]
    assert loop.index("os.path.isdir") < loop.index("os.remove")

def test_frames_the_library_cant_decode_are_redacted(capture_dirs):
    # #668: a dongle frame the library couldn't decode reached the file with the dongle's serial number and its IP
    # addresses, as the library only redacts frames it understands. A made-up frame shaped like it:
    leaked = bytes.fromhex("5959000100420102") + b"WO1234G567" + b"\x00" * 8 + b"192.168.1.15\x00255.255.255.0\x00"
    clean = capture.scrub(leaked)
    assert len(clean) == len(leaked)                                # still well formed
    assert b"WO1234G000" in clean and b"WO1234G567" not in clean
    assert b"192.168" not in clean and b"255.255" not in clean and b"000.000.0.00" in clean
    assert capture.scrub(b"SA2047G000 50.0") == b"SA2047G000 50.0"   # already redacted, and no IP address
    asyncio.run(capture.run(FakeClient([("rx", leaked)]), 30, lambda: {"model": "AC"}))
    text = open(os.path.join(capture.CAPTURE_DIR, capture.status()["file"])).read()
    assert leaked.hex() not in text and clean.hex() in text
