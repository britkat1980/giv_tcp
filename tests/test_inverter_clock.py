"""The inverter resets its Today counters by its own clock, so GivTCP warns (once a day) when that clock is out"""
import pytest

import read
from GivLUT import GivLUT
from harness.fakes import FROZEN_NOW, recorder

def at(minutes):
    """The inverter time `minutes` from GivTCP's (frozen) clock, as read.py puts it in Invertor_Time"""
    import datetime
    return (FROZEN_NOW + datetime.timedelta(minutes=minutes)).replace(tzinfo=GivLUT.timezone).isoformat()

def warnings():
    return [m for _, level, m in recorder.logs if level == "WARNING" and "Inverter clock" in m]

@pytest.fixture(autouse=True)
def fresh():
    read._clockWarned = None
    recorder.clear()
    yield
    read._clockWarned = None

def test_close_enough():
    read.checkInverterClock(at(-9))
    read.checkInverterClock(at(9))
    assert warnings() == []

def test_an_hour_behind_warns_once():
    read.checkInverterClock(at(-60))
    read.checkInverterClock(at(-60))
    assert warnings() == ["Inverter clock is 60 minutes behind GivTCP's (11:00 against 12:00), so its Today energy "
                          "counters reset at the wrong time. Use the Sync Time button, or the GivEnergy portal, to correct it"]

def test_ahead():
    read.checkInverterClock(at(15))
    assert "15 minutes ahead of" in warnings()[0]

def test_days_out():
    read.checkInverterClock(at(-14380))
    assert warnings()[0].startswith("Inverter clock is 10 days behind GivTCP's (05 Jun 12:20 against 15 Jun 12:00)")

def test_unreadable_time():
    read.checkInverterClock(None)
    assert warnings() == []
