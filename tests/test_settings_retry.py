"""A settings block the inverter never answers (eg. HR 300 on some AC inverters, #675) only gets the #608 retries once,
rather than turning most polls into full refreshes"""
import logging

import pytest
from givenergy_modbus.exceptions import ReadFailure

import read

HR300 = ReadFailure(0x11, "ReadHoldingRegistersRequest", 300, 60)

class Plant:
    def __init__(self, answered=False):
        self.answered = answered
    def block_age(self, device_address, reg_type, base_register, register_count):
        return 5.0 if self.answered else None

@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(read, "_settingsGivenUp", set())

def cycle(plant):
    """One full refresh and its retries: how many polls were full refreshes"""
    polls, retries = 1, 0
    while True:
        retry, retries = read.settingsRetry([HR300], retries, plant)
        if not retry:
            return polls
        polls += 1

def test_never_answered_retried_once(caplog):
    plant = Plant()
    with caplog.at_level(logging.INFO, logger=read.logger.name):
        assert cycle(plant) == read.FULL_REFRESH_RETRIES + 1     # the first time, as #608
        assert cycle(plant) == 1                                  # then only the scheduled full refresh
        assert cycle(plant) == 1
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert any("no longer retried" in r.getMessage() for r in caplog.records)

def test_block_that_answers_keeps_its_retries():
    plant = Plant(answered=True)
    assert cycle(plant) == read.FULL_REFRESH_RETRIES + 1
    assert cycle(plant) == read.FULL_REFRESH_RETRIES + 1

def test_retries_again_once_it_has_answered():
    plant = Plant()
    cycle(plant)
    plant.answered = True                    # answered on a later full refresh, then failed again
    assert cycle(plant) == read.FULL_REFRESH_RETRIES + 1

def test_without_the_plant_as_before():
    assert cycle(None) == read.FULL_REFRESH_RETRIES + 1
    assert cycle(None) == read.FULL_REFRESH_RETRIES + 1
