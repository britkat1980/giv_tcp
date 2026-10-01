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
