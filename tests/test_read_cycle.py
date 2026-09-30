"""Detect and read cycles on each device model, compared with tests/golden/<model>.json"""
import pytest

from harness import golden
from harness.devices import DEVICES

# Output values that depend on the real clock rather than the plant
VARIES = {"Data_Age"}

@pytest.fixture(params=list(DEVICES), scope="module")
def session(request, plants):
    return plants.get(request.param)

def test_detect(session):
    caps = session.plant.capabilities
    assert caps.device_type == session.device.model
    golden.check(session.key, "detect", "capabilities", dict(
        device_type=caps.device_type.name,
        inverter_address=caps.inverter_address,
        is_three_phase=caps.is_three_phase,
        is_hv=caps.is_hv,
        is_ems=caps.is_ems,
        is_gateway=caps.is_gateway,
        batteries=session.settings["numBatteries"],
        failed_reads=sorted("%s(0x%02x,%d)" % (f.request_type, f.device_address, f.base_register)
                            for f in session.read_failures),
    ))

@pytest.mark.parametrize("cycle", [1, 2])
def test_read_output(session, cycle):
    """What GivTCP builds from the registers (the REST /getCache output). Cycle 2 has cycle 1 as its history"""
    output = golden.mask(session.cycles[cycle - 1]["output"], VARIES)
    golden.check(session.key, "read", "cycle %d output" % cycle, output)

@pytest.mark.parametrize("cycle", [1, 2])
def test_read_logs(session, cycle):
    """Warnings and errors GivTCP logs while reading"""
    golden.check(session.key, "read", "cycle %d logs" % cycle, session.cycles[cycle - 1]["logs"])

def test_mqtt_publish(session):
    golden.check(session.key, "read", "mqtt topics", sorted({t for t, _ in session.cycles[1]["mqtt"]}))

def test_ha_discovery(session):
    """The Home Assistant entities created on the first cycle, and any removed as unsupported"""
    cycle = session.cycles[0]
    golden.check(session.key, "read", "discovery topics", sorted(t for t, _ in cycle["discovery"]))
    golden.check(session.key, "read", "discovery removed", sorted(cycle["removed"]))
