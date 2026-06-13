"""Regression tests for summary temperature sensor smoothing.

Background: issue #557 -- Invertor_Temperature (and the summary Battery_Temperature
and BMS_Temperature sensors) were configured with allowZero=True, smooth=False, so a
transient 0C read from the inverter/dongle was published verbatim instead of being
caught by dataSmoother2().  These tests exercise dataSmoother2() against the *real*
entity_lut config to lock in the fixed behaviour (allowZero=False, smooth=True).

The wider GivTCP runtime pulls in a heavy dependency tree at import time
(givenergy_modbus_async -> crccheck, plus pymodbus/paho/redis/influxdb_client via
write/mqtt/etc).  None of that is needed to exercise dataSmoother2(), so we inject
lightweight stand-ins into sys.modules before importing `read`, while keeping the
*real* entity_lut (which is import-pure) so the config under test is the real one.
"""
import datetime
import logging
import os
import sys
import types


# --- sys.modules stubs: install before importing `read` ----------------------
def _make_pkg(dotted, attrs=None):
    """Create/look up a module (and any missing parent packages) in sys.modules."""
    parts = dotted.split(".")
    for i in range(1, len(parts) + 1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            mod = types.ModuleType(name)
            if i < len(parts):
                mod.__path__ = []  # mark as package
            sys.modules[name] = mod
    mod = sys.modules[dotted]
    for key, value in (attrs or {}).items():
        setattr(mod, key, value)
    return mod


# givenergy_modbus_async is only used elsewhere in read.py; stub the import surface.
_make_pkg("givenergy_modbus_async")
_make_pkg("givenergy_modbus_async.model", {"TimeSlot": object})
_make_pkg("givenergy_modbus_async.model.register",
          {"Model": object, "Enable": object, "HR": object})
_make_pkg("givenergy_modbus_async.model.plant", {"Plant": object, "Inverter": object})
_make_pkg("givenergy_modbus_async.client.client", {"commands": object})
_make_pkg("givenergy_modbus_async.exceptions", {"CommunicationError": Exception})

# write / mqtt / requests are imported by read.py but unused by dataSmoother2.
for _name in ("write", "requests"):
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)
if "mqtt" not in sys.modules:
    sys.modules["mqtt"] = types.ModuleType("mqtt")
sys.modules["mqtt"].GivMQTT = object

# settings.GiV_Settings -- dataSmoother2 reads data_smoother; read.py reads
# default_path at import time (sys.path.append).
_settings = types.ModuleType("settings")


class _GiV_Settings:
    data_smoother = "high"
    default_path = "/tmp"


_settings.GiV_Settings = _GiV_Settings
sys.modules["settings"] = _settings

# GivLUT -- dataSmoother2 reads maxvalues.single_phase[...] and GivLUT.logger.
# rawpkl/raw_to_pub are only used by checkRawcache() (power sensors), not reached
# for temperature entities.
_givlut = types.ModuleType("GivLUT")


class _maxvalues:
    single_phase = {"maxTemp": 100, "-maxTemp": -100}
    three_phase = {"maxTemp": 100, "-maxTemp": -100}


class _GivLUT:
    logger = logging.getLogger("givtcp.test")
    rawpkl = "/nonexistent_raw.pkl"  # checkRawcache() will treat as absent
    raw_to_pub = {}


_givlut.maxvalues = _maxvalues
_givlut.GivLUT = _GivLUT
_givlut.InvType = object
_givlut.GivClientAsync = object
sys.modules["GivLUT"] = _givlut


# --- now import the real code ------------------------------------------------
_GIVTCP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "GivTCP"))
if _GIVTCP not in sys.path:
    sys.path.insert(0, _GIVTCP)

import read  # noqa: E402  (real module, heavy deps stubbed above)
from entity_lut import Entity_Type  # noqa: E402  (real, import-pure config)

GIVLUT = Entity_Type.entity_type
_INV_TIME = datetime.datetime(2026, 1, 1, 12, 0, 0)  # naive, matches lastUpdate parse


def _smooth(name, new, old, seconds_delta=30):
    """Call the real dataSmoother2() with a clean outliers list."""
    last_update = (_INV_TIME - datetime.timedelta(seconds=seconds_delta)).isoformat()
    read.outliers.clear()
    return read.dataSmoother2([name, new], [name, old], last_update, "Hybrid", _INV_TIME)


# --- tests -------------------------------------------------------------------
def test_invertor_temperature_rejects_transient_zero():
    # Pre-fix (allowZero=True): returned 0.  Post-fix (allowZero=False): prior value.
    assert _smooth("Invertor_Temperature", 0, 32.5) == 32.5


def test_battery_temperature_rejects_transient_zero():
    assert _smooth("Battery_Temperature", 0, 32.5) == 32.5


def test_bms_temperature_rejects_transient_zero():
    assert _smooth("BMS_Temperature", 0, 32.5) == 32.5


def test_invertor_temperature_rejects_nonzero_spike():
    # smooth=True now engages the jump-delta test: a 32.5 -> 95 jump inside one
    # poll is suppressed.  Pre-fix (smooth=False) this returned 95.0.
    assert _smooth("Invertor_Temperature", 95.0, 32.5) == 32.5


def test_normal_small_change_is_not_suppressed():
    # Guard against over-smoothing: a genuine 0.1C change must still pass through.
    assert _smooth("Invertor_Temperature", 32.6, 32.5) == 32.6


def test_entity_config_flags_are_set():
    # Belt-and-braces: assert the config flags themselves, so a future revert is
    # caught even if dataSmoother2's internals change.
    for entity in ("Invertor_Temperature", "Battery_Temperature", "BMS_Temperature"):
        assert GIVLUT[entity].allowZero is False, entity + " should not allow zero"
        assert GIVLUT[entity].smooth is True, entity + " should be smoothed"
