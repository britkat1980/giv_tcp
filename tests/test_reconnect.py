"""Recovering from a client that can't reconnect (see GivClientAsync.new_client)."""
import pytest
from givenergy_modbus.client.client import Client
from givenergy_modbus.exceptions import CommunicationError

import GivLUT as givlut_module
from GivLUT import GivClientAsync

def test_new_client_recovers_a_stuck_connection(plants):
    session = plants.get("hybrid_gen2")
    # A client against the same mock plant, sharing its detected plant, whose connection has dropped and whose
    # close() fails: every connect() then fails straight away, as seen on a live inverter
    stuck = Client(session.client.host, session.client.port, plant=session.plant)
    session.loop.run(stuck.connect())
    async def failing_close():
        raise OSError("simulated failure closing the old socket")
    stuck.close = failing_close
    stuck.connected = False
    givlut_module._client = stuck
    fresh = None
    try:
        with pytest.raises(CommunicationError) as failed:
            session.loop.run(GivClientAsync.get_connection())
        assert "simulated failure" in str(failed.value.__cause__)      # the cause GivTCP now logs

        fresh = session.loop.run(GivClientAsync.new_client())
        assert fresh is not stuck
        assert fresh.plant is session.plant          # capabilities and register data carry over
        assert session.loop.run(GivClientAsync.get_connection()) is fresh
        assert fresh.connected
        assert fresh.plant.capabilities.device_type == session.device_type
    finally:
        givlut_module._client = session.client
        session.loop.run(Client.close(stuck))
        if fresh is not None:
            session.loop.run(fresh.close())

def test_connection_drops_log_idle_time_then_summarise_at_debug(caplog):
    import datetime
    import logging
    from types import SimpleNamespace
    import read
    now = read.datetime.datetime.now(datetime.timezone.utc)      # the harness freezes read's clock
    def plant(idle):
        return SimpleNamespace(register_block_updated_at={("x", "IR", 0, 60): now - datetime.timedelta(seconds=idle)})
    drops = read.ConnectionDrops()
    with caplog.at_level(logging.DEBUG, logger=read.logger.name):
        drops.note(plant(10.2))
        drops.note(plant(10.2))       # the loop sees the same drop until it reconnects
        drops.reconnected()
        drops.note(plant(0.5))
        drops.reconnected()
        drops.lastsummary -= datetime.timedelta(minutes=5)
        drops.note(plant(9.8))
    lines = [r for r in caplog.records if "closed the Modbus connection" in r.getMessage()]
    assert len(lines) == 4            # once per drop, plus the summary
    assert all(r.levelno == logging.DEBUG for r in lines)
    assert "2 times in the last 5 minutes, last traffic 0.5s to 9.8s before (1 within 2s of traffic)" in lines[-1].getMessage()

def test_reconnect_after_failures_logs_at_debug(caplog):
    import logging
    import read
    drops = read.ConnectionDrops(refresh_period=60)
    with caplog.at_level(logging.DEBUG, logger=read.logger.name):
        drops.reconnected()                     # first time straight away: nothing to report
        drops.failed()
        drops.failed()
        drops.reconnected()
    lines = [r for r in caplog.records if "Reconnected" in r.getMessage()]
    assert len(lines) == 1 and lines[0].levelno == logging.DEBUG
    assert lines[0].getMessage().startswith("Reconnected to the inverter after 2 failed attempts (")
    assert drops.failures == 0 and drops.lostat is None

def test_info_only_when_a_drop_delayed_the_data_update(caplog):
    """A drop is only logged at info when Home Assistant wasn't updated in line with the usual timing: a dongle
    closing an idle connection between polls costs no data, as GivTCP reconnects for the next poll"""
    import datetime
    import logging
    from types import SimpleNamespace
    import read
    plant = SimpleNamespace(register_block_updated_at={})
    drops = read.ConnectionDrops(refresh_period=30)
    def poll_after(seconds):
        drops.lastpoll -= datetime.timedelta(seconds=seconds)
        drops.polled()
    with caplog.at_level(logging.DEBUG, logger=read.logger.name):
        drops.polled()
        drops.note(plant)                       # idle drop between polls, reconnected for the next one on time
        drops.reconnected()
        poll_after(31)
        poll_after(95)                          # a slow poll, but no drop: not about the connection
        drops.note(plant)                       # dropped, and two reconnects failed: the update came 95s later
        drops.failed()
        drops.failed()
        drops.reconnected()
        poll_after(95)
        poll_after(30)                          # back to normal
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert infos == ["Home Assistant wasn't updated for 95.0s (usually every 30s), as the inverter connection dropped and 2 reconnects failed"]

def test_closing_a_dead_client_leaves_no_unhandled_task_error():
    """#613: the library's close() stops at writer.wait_closed() on TimeoutError, leaving the reader task to fail
    later with nobody handling it, so asyncio logged "Task exception was never retrieved" """
    import asyncio
    import gc
    from GivLUT import closeClient

    unhandled = []

    async def run():
        asyncio.get_running_loop().set_exception_handler(lambda loop, context: unhandled.append(context))
        reader_failed = asyncio.Event()

        async def reader():
            await reader_failed.wait()
            raise TimeoutError(110, "Operation timed out")

        class DeadClient:
            network_consumer_task = asyncio.create_task(reader(), name="network_consumer")
            network_producer_task = None
            async def close(self):
                raise TimeoutError(110, "Operation timed out")     # before close() cancels the reader task

        client = DeadClient()
        with pytest.raises(TimeoutError):
            await closeClient(client)
        reader_failed.set()
        await asyncio.sleep(0.05)
        assert client.network_consumer_task.done()
        DeadClient.network_consumer_task = None
        del client

    asyncio.run(run())
    gc.collect()
    assert unhandled == []
