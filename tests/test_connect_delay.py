"""Wait After Connecting (connect_delay): some dongles don't answer requests sent straight after a connection opens"""
import asyncio

import pytest

import GivLUT as givlut_module
from GivLUT import GivClientAsync

class FakeClient:
    def __init__(self, connected=False):
        self.connected = connected
        self.connects = 0
    async def connect(self):
        self.connects += 1
        self.connected = True

@pytest.fixture
def waits(monkeypatch):
    slept = []
    real_sleep = asyncio.sleep
    async def sleep(seconds, *args, **kwargs):
        slept.append(seconds)
        await real_sleep(0)
    monkeypatch.setattr(givlut_module.asyncio, "sleep", sleep)
    return slept

def connect(monkeypatch, delay, client, **kwargs):
    monkeypatch.setattr(givlut_module.GiV_Settings, "connect_delay", delay, raising=False)
    monkeypatch.setattr(givlut_module, "_client", client)
    return asyncio.run(GivClientAsync.get_connection(**kwargs))

def test_off_by_default(monkeypatch, waits):
    client = FakeClient()
    assert connect(monkeypatch, 0, client, reconnect=True) is client
    assert client.connects == 1 and 15 not in waits and waits == []

def test_waits_after_connecting(monkeypatch, waits):
    client = FakeClient()
    connect(monkeypatch, 15, client, reconnect=True)
    assert client.connects == 1 and waits == [15.0]

def test_waits_at_startup_too(monkeypatch, waits):
    client = FakeClient()
    connect(monkeypatch, 15, client, cold_start=True)
    assert waits == [15.0]

def test_no_wait_when_already_connected(monkeypatch, waits):
    client = FakeClient(connected=True)
    connect(monkeypatch, 15, client, reconnect=True)
    assert client.connects == 0 and waits == []
