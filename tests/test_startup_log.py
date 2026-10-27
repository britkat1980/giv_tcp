"""Connection messages reach GivTCP's log file, and the connection settings that are on are logged at startup"""
import asyncio
import logging

import GivLUT as givlut_module
from GivLUT import GivClientAsync, GivLUT

import read

def test_connection_messages_use_the_main_log():
    # get_connection() and new_client() log with GivLUT.py's module logger. It was a separate "GivLUT" logger
    # without the log file handler, so their messages never reached the log file, debug lines not even the console
    assert givlut_module.logger is GivLUT.logger

def test_connect_delay_message_logged(monkeypatch, caplog):
    class FakeClient:
        connected = False
        async def connect(self):
            self.connected = True
    async def sleep(seconds, *args, **kwargs):
        pass
    monkeypatch.setattr(givlut_module.asyncio, "sleep", sleep)
    monkeypatch.setattr(givlut_module.GiV_Settings, "connect_delay", 10, raising=False)
    monkeypatch.setattr(givlut_module, "_client", FakeClient())
    with caplog.at_level(logging.DEBUG, logger=GivLUT.logger.name):
        asyncio.run(GivClientAsync.get_connection(reconnect=True))
    assert any("waiting 10" in r.getMessage() for r in caplog.records)

def settings_logged(monkeypatch, caplog, lite, delay, pause):
    monkeypatch.setattr(read.GiV_Settings, "lite_query", lite, raising=False)
    monkeypatch.setattr(read.GiV_Settings, "connect_delay", delay, raising=False)
    with caplog.at_level(logging.INFO, logger=read.logger.name):
        read.logSettings(read.Recovery(pause))
    return [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]

def test_settings_that_are_on_are_logged(monkeypatch, caplog):
    messages = settings_logged(monkeypatch, caplog, "True", 10, 600)
    assert len(messages) == 3
    assert messages[0].startswith("Lite mode on")
    assert "waiting 10s" in messages[1]
    assert "2 failed polls" in messages[2] and "600s" in messages[2]

def test_nothing_logged_when_off(monkeypatch, caplog):
    assert settings_logged(monkeypatch, caplog, False, 0, 0) == []
