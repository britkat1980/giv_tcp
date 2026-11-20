"""Skip Reads Fresher Than (refresh's max_age) also counts a larger reply that covers a block. The dongle's own polls
for the cloud, which it passes on to GivTCP, read the meters as 60 registers (the library 30) and three-phase IR 1360
as 60 (the library 54), so they never made those blocks count as fresh"""
from datetime import datetime, timedelta, timezone

import pytest
from givenergy_modbus.client import client as client_module

import modbus_patches

NOW = datetime(2026, 10, 30, 15, 51, 19, tzinfo=timezone.utc)
METER = (0x01, 60, 30)          # the library's meter bank
IR1360 = (0x11, 1360, 54)       # the library's last three-phase bank
IR1000 = (0x11, 1000, 60)

class Plant:
    def __init__(self, stamps):
        self.register_block_updated_at = {key: NOW - timedelta(seconds=age) for key, age in stamps.items()}
    def block_present(self, *args):
        return None
    def block_age(self, device_address, reg_type, base_register, register_count, *, now=None):
        ts = self.register_block_updated_at.get((device_address, reg_type, base_register, register_count))
        return None if ts is None else ((now or NOW) - ts).total_seconds()

@pytest.fixture
def banks(monkeypatch):
    monkeypatch.setattr(client_module, "_refresh_banks", lambda caps: [IR1000, IR1360, METER])

def requested(plant, max_age):
    return [(r.device_address, r.base_register, r.register_count)
            for r in client_module._refresh_ranges(None, max_age, plant, now=NOW)]

def test_larger_reply_from_the_dongle_counts(banks):
    # As in a three-phase capture: the dongle's batch read these 24 s before GivTCP's next poll
    plant = Plant({(0x01, "IR", 60, 60): 24, (0x11, "IR", 1360, 60): 24, (0x11, "IR", 1000, 60): 24})
    assert requested(plant, 45) == []

def test_smaller_reply_still_doesnt(banks):
    # The library's reason for keying on the size: a partial reply mustn't make the whole block fresh
    plant = Plant({(0x01, "IR", 60, 10): 5, (0x11, "IR", 1360, 20): 5, (0x11, "IR", 1010, 50): 5})
    assert requested(plant, 45) == [IR1000, IR1360, METER]

def test_too_old_is_read(banks):
    plant = Plant({(0x01, "IR", 60, 60): 50, (0x11, "IR", 1360, 60): 46, (0x11, "IR", 1000, 60): 10})
    assert requested(plant, 45) == [IR1360, METER]

def test_freshest_covering_reply_wins(banks):
    plant = Plant({(0x01, "IR", 60, 30): 300, (0x01, "IR", 60, 60): 20})
    assert METER not in requested(plant, 45)

def test_other_device_or_type_doesnt_count(banks):
    plant = Plant({(0x02, "IR", 60, 60): 5, (0x11, "HR", 1360, 60): 5})
    assert requested(plant, 45) == [IR1000, IR1360, METER]

def test_off_reads_everything(banks):
    plant = Plant({(0x01, "IR", 60, 60): 1, (0x11, "IR", 1360, 60): 1, (0x11, "IR", 1000, 60): 1})
    assert requested(plant, None) == [IR1000, IR1360, METER]

def test_covering_block_age():
    plant = Plant({(0x01, "IR", 60, 60): 24})
    assert modbus_patches.covering_block_age(plant, 0x01, "IR", 60, 30, now=NOW) == 24
    assert modbus_patches.covering_block_age(plant, 0x01, "IR", 90, 30, now=NOW) == 24       # also covered
    assert modbus_patches.covering_block_age(plant, 0x01, "IR", 100, 30, now=NOW) is None    # runs past the reply
