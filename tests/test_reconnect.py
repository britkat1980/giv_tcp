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

def test_connection_drops_logs_idle_time_once_then_summarises(caplog):
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
    lines = [r.getMessage() for r in caplog.records if "closed the Modbus connection" in r.getMessage()]
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO and "closed the Modbus connection" in r.getMessage()]
    assert len(lines) == 4            # once per drop: first, one debug, last debug plus its summary
    assert infos[0].startswith("Inverter closed the Modbus connection after 10.2s without traffic")
    assert "2 times in the last 5 minutes, after 0.5s to 9.8s without traffic (1 within 2s of traffic)" in infos[1]
