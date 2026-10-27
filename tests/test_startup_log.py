"""Connection messages reach GivTCP's log file, and the connection settings that are on are logged at startup"""
import asyncio
import logging

import GivLUT as givlut_module
from GivLUT import GivClientAsync, GivLUT

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
