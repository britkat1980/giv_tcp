"""Sandboxed runtime for GivTCP's modules.

GivTCP reads its settings from a generated ``settings.py`` module and keeps its state in files (the settings
directory, the cache location and the working directory). ``bootstrap()`` points all of these at a temporary
directory before any GivTCP module is imported, so the tests never touch a real install or the developer's own
``GivTCP/settings.py``.
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GIVTCP_DIR = ROOT / "GivTCP"

WORK = None     # set by bootstrap()

def _paths(work):
    return dict(
        cache_location=str(work / "cache"),
        Debug_File_Location=str(work / "logs" / "log_inv_1.log"),
        Debug_File_Location_Write=str(work / "logs" / "write_log_inv_1.log"),
        Debug_File_Location_REST=str(work / "logs" / "rest_log_inv_1.log"),
        default_path=str(GIVTCP_DIR),
    )

# Everything GivTCP reads from GiV_Settings, with values that keep it self-contained (no Influx, no self-run loop)
DEFAULT_SETTINGS = dict(
    invertorIP="127.0.0.1",
    serial_number="TEST000000",
    inverter_type="Hybrid",
    numBatteries=1,
    inverter_num=1,
    givtcp_instance=1,
    Battery_Only=False,
    isAddon=False,
    first_run=False,
    Log_Level="Info",
    Print_Raw_Registers=True,
    MQTT_Output=True,           # published messages are recorded by harness.fakes, nothing leaves the process
    MQTT_Address="127.0.0.1",
    MQTT_Username="",
    MQTT_Password="",
    MQTT_Topic="GivEnergy",
    MQTT_Port=1883,
    MQTT_Retain=False,
    HA_Auto_D=True,             # discovery is recorded too, so the HA entities each model creates are covered
    ha_device_prefix="GivTCP",
    Influx_Output=False,
    influxURL="", influxToken="", influxBucket="", influxOrg="",
    self_run=False,
    self_run_timer=15,
    self_run_timer_full=60,
    refresh_max_age=0,
    queue_retries=2,
    data_smoother="None",
    timeslot_entities="both",
    dynamic_tariff=False,
    day_rate=0.30,
    day_rate_start="07:30",
    night_rate=0.07,
    night_rate_start="00:30",
    export_rate=0.15,
    timezone="Europe/London",
    Smart_Target=False,
    GE_API="", SOLCASTAPI="", SOLCASTSITEID="", SOLCASTSITEID2="",
    PALM_WINTER="01,02,11,12", PALM_SHOULDER="03,04,09,10", PALM_MIN_SOC_TARGET="25", PALM_MAX_SOC_TARGET="45",
    PALM_BATT_RESERVE="4", PALM_BATT_UTILISATION="0.85", PALM_WEIGHT="35", LOAD_HIST_WEIGHT="1,1,1,1,1,1,1",
    evc_enable=False,
)

def _write_settings(values):
    lines = ["class GiV_Settings:\n"] + ["    %s=%r\n" % (k, v) for k, v in values.items()]
    (WORK / "settings.py").write_text("".join(lines), encoding="utf-8")

def bootstrap(work):
    """Create the sandbox and put it first on sys.path. Must run before any GivTCP module is imported"""
    global WORK
    WORK = Path(work)
    for d in ("config", "cache", "logs"):
        (WORK / d).mkdir(parents=True, exist_ok=True)
    os.environ["GIVTCP_CONFIG_DIR"] = str(WORK / "config")
    (WORK / "config" / "allsettings.json").write_text(json.dumps({"evc_enable": False}), encoding="utf-8")
    _write_settings({**DEFAULT_SETTINGS, **_paths(WORK)})
    sys.path[:0] = [str(WORK), str(GIVTCP_DIR)]

def enter():
    """Make the sandbox the working directory, where GivTCP keeps some state files. Not done by bootstrap(),
    as pytest still needs the real working directory to find the tests"""
    os.chdir(WORK)

def configure(**overrides):
    """Apply settings for the device under test. GivTCP holds GiV_Settings in many modules, and
    write.updateControlCache() reloads it from disk, so update the file and every loaded copy of the class"""
    values = {**DEFAULT_SETTINGS, **_paths(WORK), **overrides}
    _write_settings(values)
    for mod in list(sys.modules.values()):
        cls = getattr(mod, "GiV_Settings", None)
        if isinstance(cls, type):
            for k, v in values.items():
                setattr(cls, k, v)

def clear_state():
    """Remove GivTCP's cache and working-directory state files (keeping settings, config and logs)"""
    keep = {"settings.py", "config", "logs", "cache", "__pycache__"}
    for p in WORK.iterdir():
        if p.name not in keep:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    for p in (WORK / "cache").iterdir():
        shutil.rmtree(p) if p.is_dir() else p.unlink()

def snapshot_state():
    """Copy of every state file, to put back with restore_state() so each test starts from the same point"""
    files = {}
    for base in (WORK, WORK / "cache"):
        for p in base.iterdir():
            if p.is_file() and p.name != "settings.py":
                files[p] = p.read_bytes()
    return files

def restore_state(files):
    clear_state()
    for p, data in files.items():
        p.write_bytes(data)
