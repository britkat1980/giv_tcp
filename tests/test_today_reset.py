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
