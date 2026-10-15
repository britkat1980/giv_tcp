"""Invertor_Time is only read on full refreshes, so Load Energy Today stayed on yesterday's value until the next one (#639)"""
import datetime

import read
from GivLUT import GivLUT
from harness.fakes import FROZEN_NOW

def inv(h, m):
    return datetime.datetime(2026, 6, 15, h, m, tzinfo=GivLUT.timezone).isoformat(timespec='seconds')

def old(invTime):
    return {"Invertor_Details": {"Invertor_Time": invTime}}

def read_at(seconds_ago):
    return FROZEN_NOW.replace(tzinfo=datetime.timezone.utc) - datetime.timedelta(seconds=seconds_ago)

def test_stale_clock_over_midnight_is_a_new_day():
    # Last full refresh read 23:59, and the Today counters have already reset by the poll 90s later
    stale = inv(23, 59)
    assert not read.newInverterDay(stale, old(stale))
    assert read.newInverterDay(stale, old(stale), readAt=read_at(90))

def test_same_day_still_held():
    stale = inv(12, 0)
    assert not read.newInverterDay(stale, old(stale), readAt=read_at(90))

def test_only_rounding_dips_held():
    # Calculated Load and Self Consumption hold a dip of a counter tick or two, but nothing bigger: holding every drop
    # latched yesterday's Today values for the day when a reset was missed (#639)
    assert read.holdRoundingDip(12.3, 12.5) == 12.5
    assert read.holdRoundingDip(0.1, 12.5) == 0.1          # the counters reset
    assert read.holdRoundingDip(11.0, 12.5) == 11.0        # a real drop, not latched
    assert read.holdRoundingDip(12.3, 12.5, hold=False) == 12.3
    assert read.holdRoundingDip(12.6, 12.5) == 12.6
    assert read.holdRoundingDip(12.6, None) == 12.6

def today(**values):
    return {"Energy": {"Today": dict(values)}}

def at(h, m):
    return datetime.datetime(2026, 6, 15, h, m, tzinfo=GivLUT.timezone)

def run(monkeypatch, steps):
    # Each step: (inverter time, Today values); returns what's published for each
    monkeypatch.setattr(read, "_todayResets", {})
    published, previous = [], None
    for when, values in steps:
        output = today(**values)
        if previous is not None:
            output = read.guardTodayResets(output, previous, when)
        published.append(output["Energy"]["Today"])
        previous = output
    return published

def test_reset_bouncing_back_is_ignored(monkeypatch):
    # After midnight's reset, a reply still carrying yesterday's figure would make HA count it again
    out = run(monkeypatch, [(at(23, 59), {"Load_Energy_Today_kWh": 20.4, "PV_Energy_Today_kWh": 0}),
                            (at(0, 1), {"Load_Energy_Today_kWh": 0.1, "PV_Energy_Today_kWh": 0}),
                            (at(0, 2), {"Load_Energy_Today_kWh": 20.4, "PV_Energy_Today_kWh": 0}),
                            (at(0, 3), {"Load_Energy_Today_kWh": 0.3, "PV_Energy_Today_kWh": 0})])
    assert [o["Load_Energy_Today_kWh"] for o in out] == [20.4, 0.1, 0.1, 0.3]

def test_not_triggered_by_real_energy_or_midday_glitches(monkeypatch):
    # Exporting just after midnight, past yesterday's small total
    out = run(monkeypatch, [(at(23, 59), {"Export_Energy_Today_kWh": 0.8}),
                            (at(0, 1), {"Export_Energy_Today_kWh": 0.0}),
                            (at(0, 10), {"Export_Energy_Today_kWh": 1.0})])
    assert [o["Export_Energy_Today_kWh"] for o in out] == [0.8, 0.0, 1.0]
    # A drop and recovery in the day isn't a reset, so it's published as read
    out = run(monkeypatch, [(at(12, 0), {"Import_Energy_Today_kWh": 5.0}),
                            (at(12, 1), {"Import_Energy_Today_kWh": 0.0}),
                            (at(12, 2), {"Import_Energy_Today_kWh": 5.0})])
    assert [o["Import_Energy_Today_kWh"] for o in out] == [5.0, 0.0, 5.0]
    # Long after the reset, yesterday's figure is no longer a bounce
    out = run(monkeypatch, [(at(23, 59), {"Load_Energy_Today_kWh": 20.4}),
                            (at(0, 1), {"Load_Energy_Today_kWh": 0.1}),
                            (at(0, 20), {"Load_Energy_Today_kWh": 20.4})])
    assert out[-1]["Load_Energy_Today_kWh"] == 20.4

def test_load_dips_after_midnight_held():
    # #654: the reporter's Load Energy Today just after midnight. Load's hold stays on through the grace period, and
    # yesterday's total still resets, as it's always more than a dip
    published, old = [], None
    for value in (50.0, 0, 0.1, 0.2, 0.3, 0.4, 0.3, 0.4, 0.5, 0.4, 0.5, 0.6, 0.7, 0.6, 0.7):
        old = read.holdRoundingDip(value, old)
        published.append(old)
    assert published == [50.0, 0, 0.1, 0.2, 0.3, 0.4, 0.4, 0.4, 0.5, 0.5, 0.5, 0.6, 0.7, 0.7, 0.7]
