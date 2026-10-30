"""The inverter's notifications (#529): active faults and warnings, logged as they appear and clear, with the most
recent kept after it clears."""
import logging

import read


def poll(old, status="Normal", details=()):
    inverter = {}
    read.notifications(inverter, {'SN': old} if old is not None else {}, status, list(details))
    return inverter


def test_nothing_active():
    assert poll({}) == {'Active_Notifications': "None"}


def test_a_fault_appears_and_is_logged(caplog):
    with caplog.at_level(logging.INFO):
        inverter = poll({'Active_Notifications': "None"}, "Fault", ["Grid voltage Fault"])
    assert inverter['Active_Notifications'] == "Grid voltage Fault"
    assert inverter['Last_Notification'] == "Grid voltage Fault"
    assert inverter['Last_Notification_Time']
    assert "Inverter notification: Grid voltage Fault" in caplog.text


def test_a_fault_still_active_is_not_logged_again(caplog):
    old = {'Active_Notifications': "Grid voltage Fault", 'Last_Notification': "Grid voltage Fault",
           'Last_Notification_Time': "2026-10-30T09:00:00+00:00"}
    with caplog.at_level(logging.INFO):
        inverter = poll(old, "Fault", ["Grid voltage Fault"])
    assert inverter['Last_Notification_Time'] == "2026-10-30T09:00:00+00:00"
    assert "Inverter notification" not in caplog.text


def test_the_last_notification_is_kept_after_it_clears(caplog):
    old = {'Active_Notifications': "Grid voltage Fault", 'Last_Notification': "Grid voltage Fault",
           'Last_Notification_Time': "2026-10-30T09:00:00+00:00"}
    with caplog.at_level(logging.INFO):
        inverter = poll(old)
    assert inverter == {'Active_Notifications': "None", 'Last_Notification': "Grid voltage Fault",
                        'Last_Notification_Time': "2026-10-30T09:00:00+00:00"}
    assert "Inverter notification cleared: Grid voltage Fault" in caplog.text


def test_only_the_new_one_becomes_the_last_notification():
    old = {'Active_Notifications': "Fault code 0004"}
    inverter = poll(old, "Fault", ["Fault code 0004", "Battery temperature fault"])
    assert inverter['Active_Notifications'] == "Fault code 0004; Battery temperature fault"
    assert inverter['Last_Notification'] == "Battery temperature fault"


def test_a_warning_status_without_any_bit_set_is_still_a_notification():
    assert poll({}, "Warning")['Active_Notifications'] == "Inverter warning"
    assert poll({}, "Waiting")['Active_Notifications'] == "None"
