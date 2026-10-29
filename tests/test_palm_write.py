"""PALM's charge target goes to the read loop's write queue, and the cloud is only used if that fails (#682)"""
import logging
import sys
import types

import pytest

from GivLUT import GivLUT

@pytest.fixture
def palm(monkeypatch, tmp_path):
    # palm_settings reads the add-on's settings at import, and palm_utils talks to Solcast and the cloud
    monkeypatch.setitem(sys.modules, "palm_settings", types.ModuleType("palm_settings"))
    utils = types.ModuleType("palm_utils")
    utils.GivEnergyObj = utils.SolcastObj = object
    utils.t_to_mins = lambda t: 0
    monkeypatch.setitem(sys.modules, "palm_utils", utils)
    monkeypatch.delitem(sys.modules, "palm_soc", raising=False)
    import palm_soc

    class Inverter:
        tgt_soc = 91
        cloud = []
        def set_mode(self, mode):
            self.cloud.append(mode)

    monkeypatch.setattr(GivLUT, "writerequests", str(tmp_path / "writerequests.pkl"))
    monkeypatch.setattr(palm_soc, "logger", logging.getLogger("read_logger"), raising=False)
    monkeypatch.setattr(palm_soc, "inverter", Inverter(), raising=False)
    return palm_soc

def test_target_is_queued_for_the_read_loop(palm):
    GivLUT.queue_write("setChargeRate", {'chargeRate': '2500'})     # an earlier request stays queued
    palm.GivTCP_write_soc("set_soc")
    palm.GivTCP_write_soc("set_soc_winter")
    assert GivLUT.load_pickle(GivLUT.writerequests) == [
        ["setChargeRate", {'chargeRate': '2500'}, False],
        ["setChargeTarget", {'chargeToPercent': 91}, False],
        ["setChargeTarget", {'chargeToPercent': 100}, False],
    ]
    assert palm.inverter.cloud == []

def test_cloud_only_if_it_cant_be_queued(palm, monkeypatch, caplog):
    def fail(command, payload):
        raise OSError("disk full")
    monkeypatch.setattr(GivLUT, "queue_write", fail)
    with caplog.at_level(logging.ERROR, logger="read_logger"):
        palm.GivTCP_write_soc("set_soc")
    assert palm.inverter.cloud == ["set_soc"]
    assert any("OSError: disk full" in r.getMessage() for r in caplog.records)
