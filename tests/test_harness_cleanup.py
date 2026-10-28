"""Real client tasks must finish before the harness's event loop is destroyed."""
import asyncio
import gc
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

import pytest
from givenergy_modbus.client.client import Client
from harness.plant import LoopThread, PlantSession, Plants, RecordingMockPlant


def test_loop_close_cancels_and_awaits_remaining_tasks():
    loop = LoopThread()
    finished = []
    async def start():
        entered = asyncio.Event()
        async def worker():
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                finished.append(True)
        task = asyncio.create_task(worker())
        await entered.wait()
        return task
    try:
        task = loop.run(start())
    finally:
        loop.close()
    assert task.done() and task.cancelled()
    assert finished == [True]
    assert loop.loop.is_closed()
    assert not loop.thread.is_alive()
    loop.close()  # fixture cleanup can safely run twice


def test_plants_close_real_clients_and_servers_without_pending_task_errors():
    plants = Plants()
    errors = []
    session = PlantSession.__new__(PlantSession)
    session.mock = RecordingMockPlant({})
    async def connect():
        asyncio.get_running_loop().set_exception_handler(lambda loop, context: errors.append(context))
        host, port = await session.mock.start()
        session.client = Client(host, port)
        await session.client.connect()
        return [session.client.network_consumer_task, session.client.network_producer_task]
    plants.sessions['test'] = session
    session.client = None
    try:
        tasks = plants.loop.run(connect())
        assert all(not task.done() for task in tasks)
    finally:
        plants.close()
    assert all(task.done() for task in tasks)
    assert session.client.connected is False
    assert session.mock._server is None
    assert plants.loop.loop.is_closed()
    assert not plants.loop.thread.is_alive()
    gc.collect()
    assert errors == []
    plants.close()


def test_failed_session_initialisation_closes_client_and_server(monkeypatch):
    import read
    from harness.devices import DEVICES
    loop = LoopThread()
    client = Mock(connect=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr('harness.plant.Client', Mock(return_value=client))
    monkeypatch.setattr(PlantSession, 'activate', Mock())
    monkeypatch.setattr('harness.env.clear_state', Mock())
    monkeypatch.setattr(read, 'detectPlant', AsyncMock(side_effect=RuntimeError('detect failed')))
    close_server = AsyncMock()
    monkeypatch.setattr(RecordingMockPlant, 'aclose', close_server)
    monkeypatch.setattr(RecordingMockPlant, 'start', AsyncMock(return_value=('127.0.0.1', 1)))
    try:
        with pytest.raises(RuntimeError, match='detect failed'):
            PlantSession('hybrid_gen2', DEVICES['hybrid_gen2'], loop)
        client.close.assert_awaited_once()
        close_server.assert_awaited_once()
    finally:
        loop.close()


def test_one_close_failure_does_not_leave_other_sessions_or_loop_running():
    plants = Plants()
    failed = AsyncMock(side_effect=OSError('socket close failed'))
    healthy = AsyncMock()
    plants.sessions = {'failed': SimpleNamespace(aclose=failed),
                       'healthy': SimpleNamespace(aclose=healthy)}
    with pytest.raises(OSError, match='socket close failed'):
        plants.close()
    failed.assert_awaited_once()
    healthy.assert_awaited_once()
    assert plants.loop.loop.is_closed()
    assert not plants.loop.thread.is_alive()
