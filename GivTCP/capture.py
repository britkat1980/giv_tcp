"""Device captures, so users can share their inverter's data to build GivTCP's library of devices for testing.

The Share Device page asks an inverter's REST API for a capture (request()), and its read loop runs it (pending()
and run()) on the connection it already has, alongside normal polling. givenergy-modbus's Client.capture_frames()
redacts every frame before GivTCP sees it (serial numbers, and IP addresses in the dongle's LAN config), and the
file is in the format givenergy-cli writes, which the test harness loads with MockPlant.from_capture(). The user
downloads the file and attaches it to a pre-filled GitHub issue: GivTCP can't upload to GitHub itself, as that
needs a token, and any token in GivTCP could be taken and misused.
"""
import datetime
import json
import os
import re
from urllib.parse import quote

from GivLUT import GivLUT
from settings import GiV_Settings

CAPTURE_DIR = os.path.join(GivLUT.config_dir, "captures")
MIN_SECONDS = 120       # long enough for a full refresh (settings, energy totals and batteries) and a few polls
MAX_SECONDS = 600
ISSUES_URL = "https://github.com/britkat1980/giv_tcp/issues/new"

# A second redaction pass over every frame, after the library's. The library only redacts frames it can decode, and one it
# can't (a dongle's 72-byte status frame, #668) went into the file with the dongle's serial number and its IP addresses
# in plain text. Serial numbers keep their prefix and date with the unit digits zeroed, as the library does, and IP
# addresses have every digit zeroed. Neither changes the frame's length, so it's still well formed
SERIAL_RE = re.compile(rb"([A-Z]{2}\d{4}[A-Z])\d{3}")
IPV4_RE = re.compile(rb"(?<![\d.])\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?![\d.])")

def scrub(frame):
    frame = SERIAL_RE.sub(lambda m: m.group(1) + b"000", bytes(frame))
    return IPV4_RE.sub(lambda m: re.sub(rb"\d", b"0", m.group(0)), frame)

def _instance():
    return str(GiV_Settings.givtcp_instance)

def request_file():
    return os.path.join(GiV_Settings.cache_location, "captureRequest_" + _instance() + ".json")

def status_file():
    return os.path.join(CAPTURE_DIR, "status_" + _instance() + ".json")

def default_seconds():
    # One full-refresh period plus a poll (150s on the default 30/120s timers). Starting a capture also asks for a
    # full refresh on the next poll, so every register block the inverter answers is in it
    timer = float(getattr(GiV_Settings, 'self_run_timer', 30) or 30)
    full = float(getattr(GiV_Settings, 'self_run_timer_full', 120) or 120)
    return int(min(max(MIN_SECONDS, full + timer), MAX_SECONDS))

def _write_status(status):
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    tmp = status_file() + ".tmp"
    with open(tmp, "w") as out:
        json.dump(status, out, indent=2)
    os.replace(tmp, status_file())

def status():
    """The current or last capture for this inverter: state is idle, requested, running, done or error"""
    try:
        with open(status_file()) as inp:
            st = json.load(inp)
    except (OSError, ValueError):
        return {"state": "idle"}
    if st.get("state") in ("requested", "running"):
        # Long overdue means it was interrupted, eg. GivTCP restarted (which also clears the request), so it
        # doesn't block a new capture
        since = st.get("started") or st.get("requested")
        try:
            age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(since)).total_seconds()
        except (TypeError, ValueError):
            age = None
        if age is None or age > int(st.get("seconds") or MAX_SECONDS) + 300:
            st = {"state": "error", "error": "the capture was interrupted (GivTCP may have restarted). Please try again"}
    return st

def request(seconds=None):
    """Ask this inverter's read loop for a capture. Returns the status, or one already in progress"""
    current = status()
    if current.get("state") in ("requested", "running"):
        return current
    seconds = int(min(max(int(seconds or default_seconds()), 30), MAX_SECONDS))
    with open(request_file(), "w") as out:
        json.dump({"seconds": seconds}, out)
    current = {"state": "requested", "seconds": seconds,
               "requested": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    _write_status(current)
    return current

def pending():
    """A capture request for the read loop to run (taken off the queue), or None"""
    try:
        with open(request_file()) as inp:
            req = json.load(inp)
    except (OSError, ValueError):
        return None
    try:
        os.remove(request_file())
    except OSError:
        pass
    return req

def file_name(summary, when):
    model = re.sub(r"[^a-z0-9]+", "_", str(summary.get("model") or "unknown").lower()).strip("_")
    arm = re.sub(r"[^0-9A-Za-z]+", "", str(summary.get("arm_firmware") or ""))
    return model + ("_arm" + arm if arm else "") + "_" + when.strftime("%Y%m%d-%H%M") + ".log"

def device_summary(plant):
    """What the capture is of, with no serial numbers: model, firmware and the devices detect found"""
    caps = plant.capabilities
    summary = {"model": caps.device_type.name if caps and caps.device_type else None}
    inv = None
    try:
        inv = plant.inverter
    except Exception:
        pass
    for key, attr in (("device_type_code", "device_type_code"), ("arm_firmware", "arm_firmware_version"),
                      ("dsp_firmware", "dsp_firmware_version"), ("firmware", "firmware_version")):
        value = getattr(inv, attr, None) if inv is not None else None
        if value is not None:
            summary[key] = str(value)
    if caps:
        summary["lv_batteries"] = len(caps.lv_battery_addresses)
        summary["battery_stacks"] = [modules for _, modules in caps.bcu_stacks]
        summary["aio_battery_modules"] = len(caps.aio_battery_module_addresses)
        summary["meters"] = len(caps.meter_addresses)
    try:
        firmware = sorted({str(b.bms_firmware_version) for b in plant.batteries if b.is_valid() and b.bms_firmware_version})
        if firmware:
            summary["battery_firmware"] = firmware
    except Exception:
        pass
    return summary

def issue_url(summary, name):
    """A pre-filled GitHub "new issue" form for sharing the capture, which the user attaches the file to"""
    rows = "\n".join("| " + key.replace("_", " ").capitalize() + " | " + (", ".join(map(str, value)) if isinstance(value, list) else str(value)) + " |"
                     for key, value in summary.items())
    body = ("I'd like to share a capture of my device for GivTCP's test library.\n\n"
            "**Please drag the downloaded file `" + name + "` into this box before submitting.**\n\n"
            "| | |\n|---|---|\n" + rows + "\n\n"
            "The capture was made by GivTCP's Share Device page. Serial numbers and IP addresses are removed by the "
            "givenergy-modbus library before the file is written.\n")
    title = "Device capture: " + str(summary.get("model") or "unknown model") + \
            (" (ARM " + str(summary["arm_firmware"]) + ")" if summary.get("arm_firmware") else "")
    return ISSUES_URL + "?title=" + quote(title) + "&labels=device-capture&body=" + quote(body)

async def run(client, seconds, summarise, log=None):
    """Capture this inverter's (redacted) wire frames for `seconds` alongside normal polling, then write the file
    and status. summarise() gives the device summary, taken at the end so the full refresh has been read"""
    started = datetime.datetime.now(datetime.timezone.utc)
    _write_status({"state": "running", "seconds": seconds, "started": started.isoformat(timespec="seconds")})
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    work = os.path.join(CAPTURE_DIR, "capturing_" + _instance() + ".log")
    frames = 0
    try:
        with open(work, "w") as out:
            def sink(direction, frame):
                nonlocal frames
                out.write(datetime.datetime.now().astimezone().isoformat() + " " + direction + " " + scrub(frame).hex() + "\n")
                frames += 1
            await client.capture_frames(sink, duration=seconds)
        summary = summarise()
        name = file_name(summary, started)
        os.replace(work, os.path.join(CAPTURE_DIR, name))
        _write_status({"state": "done", "seconds": seconds, "started": started.isoformat(timespec="seconds"),
                       "file": name, "frames": frames, "summary": summary, "issue_url": issue_url(summary, name)})
        if log:
            log.info("Device capture saved as " + name + " (" + str(frames) + " frames)")
    except Exception as e:
        _write_status({"state": "error", "error": type(e).__name__ + ": " + str(e)})
        if log:
            log.error("Device capture failed: " + type(e).__name__ + ": " + str(e))
        try:
            os.remove(work)
        except OSError:
            pass
