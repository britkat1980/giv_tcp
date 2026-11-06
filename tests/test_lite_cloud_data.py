"""Lite mode on a three-phase hybrid: the slow-changing live-data blocks and the battery stacks are left to the dongle's
own polls for the cloud, which it passes on to GivTCP, and only read when no reply has covered them for
CLOUD_DATA_FALLBACK seconds. The power flows, SOC and meters are read every poll"""
import asyncio
import logging
import types
from datetime import datetime, timedelta, timezone

import pytest
from givenergy_modbus.model.inverter import Model

import modbus_patches
import read

FALLBACK = read.CLOUD_DATA_FALLBACK

@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(read, "cloudPauseEnded", None)

def clock():
    # read's clock, which the harness can hold at a fixed time
    return read.datetime.datetime.now(timezone.utc)

def skipped(session, monkeypatch, light, full):
    monkeypatch.setattr(read.GiV_Settings, "lite_query", light, raising=False)
    async def noop(**kwargs):
        pass
    client = types.SimpleNamespace(refresh=noop, load_config=noop, plant=session.plant)
    try:
        asyncio.run(read.readPlant(client, full))
        return set(modbus_patches.skip_banks)
    finally:
        modbus_patches.skip_banks = set()

def stamp(monkeypatch, plant, banks, age, now=None):
    """Replies covering these banks, age seconds ago, as the dongle sends them (the meters and IR 1360 as 60 registers)"""
    now = now or clock()
    stamps = {(a, "IR", b, 60): now - timedelta(seconds=age) for a, b, c in banks}
    monkeypatch.setattr(plant, "register_block_updated_at", stamps)

@pytest.fixture
def tph(plants, monkeypatch):
    session = plants.get("hybrid_3ph")
    session.activate(session.state)
    monkeypatch.setattr(read.GiV_Settings, "lite_query", True, raising=False)
    plant = session.plant
    caps = plant.capabilities
    inv = caps.inverter_address
    banks = modbus_patches._library_refresh_banks(caps)
    slow = {b for b in banks if b[0] == inv and b[1] in (0, 180, 1180, 1300, 1360)}
    fast = {b for b in banks if b[0] == inv and b[1] in (1000, 1060, 1120, 1240)} | {(m, 60, 30) for m in caps.meter_addresses}
    modules = set(modbus_patches.hv_module_banks(caps))
    bcus = {(s.device_address, 60, 60) for s in plant.hv_stacks}
    assert caps.device_type == Model.HYBRID_3PH and len(slow) == 5 and len(fast) >= 4 and bcus
    return session, slow, fast, modules, bcus

def test_fallback_is_twice_the_measured_interval():
    assert read.CLOUD_DATA_FALLBACK == 660

def test_delivered_recently_is_left_to_the_dongle(tph, monkeypatch):
    session, slow, fast, modules, bcus = tph
    stamp(monkeypatch, session.plant, slow | fast | bcus, 300)
    assert skipped(session, monkeypatch, True, False) == slow | modules | bcus
    assert skipped(session, monkeypatch, True, True) == slow | modules | bcus      # the stacks on full refreshes too

def test_fast_blocks_always_read(tph, monkeypatch):
    session, slow, fast, modules, bcus = tph
    stamp(monkeypatch, session.plant, slow | fast | bcus, 1)
    assert not skipped(session, monkeypatch, True, False) & fast

def test_not_delivered_for_too_long_is_read(tph, monkeypatch):
    session, slow, fast, modules, bcus = tph
    stamp(monkeypatch, session.plant, slow | fast | bcus, FALLBACK + 1)
    assert skipped(session, monkeypatch, True, False) == modules | bcus           # lite mode as before
    assert skipped(session, monkeypatch, True, True) == modules

def test_never_received_is_read(tph, monkeypatch):
    session, slow, fast, modules, bcus = tph
    monkeypatch.setattr(session.plant, "register_block_updated_at", {})
    assert not skipped(session, monkeypatch, True, False) & slow

def test_does_nothing_without_lite_mode(tph, monkeypatch):
    session, slow, fast, modules, bcus = tph
    stamp(monkeypatch, session.plant, slow | fast | bcus, 300)
    assert skipped(session, monkeypatch, False, False) == modules
    assert skipped(session, monkeypatch, False, True) == set()

def test_hv_gen3_unaffected(plants, monkeypatch):
    session = plants.get("hybrid_hv_gen3")
    session.activate(session.state)
    caps = session.plant.capabilities
    stamp(monkeypatch, session.plant, modbus_patches._library_refresh_banks(caps), 300)
    monkeypatch.setattr(read.GiV_Settings, "lite_query", True, raising=False)
    assert read.cloudFallback(session.plant) == 0
    assert read.cloudDelivered(session.plant) == set()

@pytest.mark.parametrize("model", [Model.AC_3PH, Model.AIO_COMMERCIAL, Model.HYBRID_HV_GEN3, Model.HYBRID_GEN3,
                                   Model.ALL_IN_ONE, Model.AC])
def test_other_models_unaffected(tph, model, monkeypatch):
    # Only the three-phase hybrid, whose dongle polls have been measured, not everything the library calls three-phase
    session, slow, fast, modules, bcus = tph
    stamp(monkeypatch, session.plant, slow | fast | bcus, 300)
    plant = types.SimpleNamespace(capabilities=types.SimpleNamespace(device_type=model, inverter_address=0x11,
                                                                     is_three_phase=True, is_hv=True),
                                  register_block_updated_at=session.plant.register_block_updated_at, hv_stacks=[])
    assert read.cloudDelivered(plant) == set()

def test_stacks_only_considered_on_full_refreshes(tph, monkeypatch, caplog):
    # Between full refreshes lite mode leaves the stacks out anyway, so don't log that they're being read
    session, slow, fast, modules, bcus = tph
    stamp(monkeypatch, session.plant, slow | fast | bcus, FALLBACK + 1)
    stack = "IR(0x%02x,60)" % min(b[0] for b in bcus)
    with caplog.at_level(logging.DEBUG, logger=read.logger.name):
        read.cloudDelivered(session.plant, False)
    assert not [r for r in caplog.records if r.getMessage().startswith(stack)]
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=read.logger.name):
        read.cloudDelivered(session.plant, True)
    assert [r for r in caplog.records if r.getMessage().startswith(stack) and "so reading it" in r.getMessage()]

def test_after_a_pause_left_to_the_dongle_for_one_period(tph, monkeypatch):
    # The dongle stopped polling during the silence too, so the slow blocks are old when the pause ends. They're left
    # to its next poll for one fallback period, rather than all read from a dongle that has only just recovered
    session, slow, fast, modules, bcus = tph
    now = clock()
    stamp(monkeypatch, session.plant, slow | fast | bcus, 975, now)
    monkeypatch.setattr(read, "cloudPauseEnded", now - timedelta(seconds=10))
    assert read.cloudDelivered(session.plant, True, now) == slow | bcus
    monkeypatch.setattr(read, "cloudPauseEnded", now - timedelta(seconds=FALLBACK + 1))
    assert read.cloudDelivered(session.plant, True, now) == set()

def test_after_a_pause_never_received_is_still_read(tph, monkeypatch):
    session, slow, fast, modules, bcus = tph
    now = clock()
    monkeypatch.setattr(session.plant, "register_block_updated_at", {})
    monkeypatch.setattr(read, "cloudPauseEnded", now - timedelta(seconds=10))
    assert read.cloudDelivered(session.plant, True, now) == set()

def test_end_of_a_pause_is_recorded(monkeypatch):
    monkeypatch.setattr(read, "publishStatus", lambda *a: None)
    recovery = read.Recovery(600)
    recovery.until = read.datetime.datetime.now() - timedelta(seconds=1)
    before = clock()
    assert not recovery.waiting()
    assert read.cloudPauseEnded is not None and read.cloudPauseEnded >= before

def test_timeline(tph, monkeypatch):
    """GivTCP polls every 60s and the dongle's batch comes every 306s (as in a three-phase capture with the cloud
    blocked), and stops after 3 batches. Which slow blocks GivTCP reads itself"""
    session, slow, fast, modules, bcus = tph
    plant = session.plant
    start = datetime(2026, 10, 30, 15, 48, tzinfo=timezone.utc)
    stamps = {}
    monkeypatch.setattr(plant, "register_block_updated_at", stamps)
    batch = (slow - {b for b in slow if b[1] == 0}) | fast | bcus      # the dongle doesn't read IR 0
    reads = {b: [] for b in slow | bcus}
    batches = [30 + 306 * k for k in range(3)]                           # 30s after GivTCP starts, then every 306s
    last = batches[-1]
    for t in range(0, 3600, 60):
        for d in batches:
            if t - 60 < d <= t:
                for a, b, c in batch:
                    stamps[(a, "IR", b, 60)] = start + timedelta(seconds=d)
        now = start + timedelta(seconds=t)
        left = read.cloudDelivered(plant, True, now)
        for bank in reads:
            if bank not in left:
                reads[bank].append(t)
                stamps[(bank[0], "IR", bank[1], bank[2])] = now           # GivTCP's own read
    ir0 = next(b for b in slow if b[1] == 0)
    for bank in [b for b in reads if b != ir0]:
        assert reads[bank][0] == 0                                        # read at startup, before any batch
        assert not [t for t in reads[bank] if 0 < t <= last + FALLBACK]   # left to the batches while they come
        assert [t for t in reads[bank] if t > last + FALLBACK]            # read again once they've stopped
    gaps = [b - a for a, b in zip(reads[ir0], reads[ir0][1:])]
    assert gaps and all(FALLBACK <= g <= FALLBACK + 60 for g in gaps)       # IR 0 every fallback period, not every poll

def inverter_at(monkeypatch, hour, minute):
    """The inverter's clock at the poll"""
    monkeypatch.setattr(read, "inverterClock", lambda plant, now: datetime(2026, 11, 7, hour, minute))

def ir1360(slow):
    return next(b for b in slow if b[1] == 1360)

def test_reply_from_before_midnight_is_read_on_the_first_poll_of_the_day(tph, monkeypatch):
    # The Today counters (IR 1360) reset at the inverter's midnight. A reply at 23:58 is yesterday's, so the poll at
    # 00:01 reads it, rather than waiting up to ~5 minutes for the dongle's next poll
    session, slow, fast, modules, bcus = tph
    now = clock()
    stamp(monkeypatch, session.plant, slow | fast | bcus, 180, now)              # 23:58
    inverter_at(monkeypatch, 0, 1)
    delivered = read.cloudDelivered(session.plant, True, now)
    assert ir1360(slow) not in delivered and not delivered & slow
    assert delivered == bcus                                                      # the stacks have no Today counters

def test_reply_from_before_midnight_is_read_after_the_reset_window(tph, monkeypatch):
    # 00:07, no reply from the dongle since 23:58: still yesterday's, although well within the fallback
    session, slow, fast, modules, bcus = tph
    now = clock()
    stamp(monkeypatch, session.plant, slow | fast | bcus, 540, now)              # 23:58
    inverter_at(monkeypatch, 0, 7)
    assert not read.cloudDelivered(session.plant, True, now) & slow

def test_reply_from_after_midnight_is_left_to_the_dongle(tph, monkeypatch):
    # 00:07, the dongle's poll at 00:03 already carried the new day's counters
    session, slow, fast, modules, bcus = tph
    now = clock()
    stamp(monkeypatch, session.plant, slow | fast | bcus, 240, now)              # 00:03
    inverter_at(monkeypatch, 0, 7)
    assert read.cloudDelivered(session.plant, True, now) == slow | bcus

def test_read_every_poll_in_the_reset_window(tph, monkeypatch):
    # Some firmware resets a few minutes after midnight, so a reply at 00:01 may still carry yesterday's counters:
    # until 00:05 the slow inverter blocks are read every poll
    session, slow, fast, modules, bcus = tph
    now = clock()
    stamp(monkeypatch, session.plant, slow | fast | bcus, 120, now)              # 00:01
    inverter_at(monkeypatch, 0, 3)
    assert not read.cloudDelivered(session.plant, True, now) & slow
    inverter_at(monkeypatch, 0, 5)                                                # window over, reply from today
    stamp(monkeypatch, session.plant, slow | fast | bcus, 60, now)               # 00:04
    assert read.cloudDelivered(session.plant, True, now) == slow | bcus

def test_unknown_inverter_clock_as_before(tph, monkeypatch):
    session, slow, fast, modules, bcus = tph
    now = clock()
    stamp(monkeypatch, session.plant, slow | fast | bcus, 300, now)
    monkeypatch.setattr(read, "inverterClock", lambda plant, now: None)
    assert read.cloudDelivered(session.plant, True, now) == slow | bcus

def test_inverter_clock():
    # Read with the settings on full refreshes, so the time since they were read is added
    now = datetime(2026, 11, 6, 23, 10, tzinfo=timezone.utc)
    def plant(system_time, read_ago):
        stamps = {(0x11, "HR", 0, 60): now - timedelta(seconds=read_ago)} if read_ago is not None else {}
        return types.SimpleNamespace(inverter=types.SimpleNamespace(system_time=system_time),
                                     capabilities=types.SimpleNamespace(inverter_address=0x11),
                                     register_block_updated_at=stamps)
    assert read.inverterClock(plant(datetime(2026, 11, 6, 23, 50), 600), now) == datetime(2026, 11, 7, 0, 0)
    assert read.inverterClock(plant(datetime(2026, 11, 6, 23, 50), None), now) == datetime(2026, 11, 6, 23, 50)
    assert read.inverterClock(plant(datetime(2000, 1, 1, 0, 0), 600), now) is None      # default date
    assert read.inverterClock(plant(None, 600), now) is None
