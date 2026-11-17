"""#708: an LV battery's values froze until GivTCP restarted. The Modbus library's battery check (its "splice guard")
rejected every reply after a sudden step, with its heal off and its warnings hidden from GivTCP's log."""
import logging
import types

import GivLUT
import read


def test_the_library_heal_is_on():
    # A genuine step (eg. a sudden discharge) is adopted once it has carried on smoothly, rather than held for good,
    # on the first client and on one that replaces it (which keeps the plant)
    first = GivLUT.newClient("192.0.2.2")
    assert first.plant.splice_reject_heal_seconds == GivLUT.SPLICE_HEAL_SECONDS == 300
    first.plant.splice_reject_heal_seconds = None
    assert GivLUT.newClient("192.0.2.2", plant=first.plant).plant.splice_reject_heal_seconds == 300


def test_battery_check_messages_reach_the_log(caplog):
    plant_logger = logging.getLogger("givenergy_modbus.model.plant")
    with caplog.at_level(logging.DEBUG):
        plant_logger.warning("Rejected battery bank for device 0x33 - sub-bus splice; keeping last-good. Trips: x.")
        plant_logger.info("Battery bank for device 0x33: sustained step evolved smoothly - adopting as new baseline")
        plant_logger.warning("Something else the library says")
    messages = [r.getMessage() for r in caplog.records if r.name == "givenergy_modbus.model.plant"]
    assert len(messages) == 2 and all("battery bank" in m.lower() for m in messages)


def plant(ages):
    # Two LV batteries, with the seconds since each one's data was last accepted
    caps = types.SimpleNamespace(lv_battery_addresses=[0x32, 0x33])
    return types.SimpleNamespace(capabilities=caps, splice_reject_count={0x33: 42},
                                 block_age=lambda addr, kind, base, count, now=None: ages[addr])


def test_a_stale_battery_is_reported_once_then_when_it_recovers(caplog, monkeypatch):
    monkeypatch.setattr(read, "_staleBatteries", set())
    with caplog.at_level(logging.INFO):
        read.checkStaleBatteries(plant({0x32: 20, 0x33: 1000}))
        read.checkStaleBatteries(plant({0x32: 20, 0x33: 1030}))
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["Battery 2 (0x33) hasn't updated for 16 minutes, so its values are the last good ones. "
                        "The Modbus library rejected 42 of its replies. Restarting GivTCP clears it"]
    caplog.clear()
    with caplog.at_level(logging.INFO):
        read.checkStaleBatteries(plant({0x32: 20, 0x33: 15}))
    assert [r.getMessage() for r in caplog.records] == ["Battery 2 (0x33) is updating again"]


def test_fresh_or_unread_batteries_are_not_reported(caplog, monkeypatch):
    monkeypatch.setattr(read, "_staleBatteries", set())
    with caplog.at_level(logging.INFO):
        read.checkStaleBatteries(plant({0x32: 30, 0x33: None}))
    assert not caplog.records
