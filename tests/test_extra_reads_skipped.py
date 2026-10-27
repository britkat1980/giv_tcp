"""The extra settings reads (modbus_patches EXTRA_READS) are left out when the settings read got no answer at all"""
import asyncio

import pytest
from givenergy_modbus.exceptions import ConnectionLost, RefreshFailed, RefreshPartiallySucceeded

import modbus_patches

def run_load_config(monkeypatch, outcome):
    extra = []
    async def library(self, *args, **kwargs):
        if outcome is not None:
            raise outcome
        return "plant"
    async def extra_reads(client):
        extra.append(client)
    monkeypatch.setattr(modbus_patches, "_library_load_config", library)
    monkeypatch.setattr(modbus_patches, "_extra_reads", extra_reads)
    client = object()
    if outcome is None:
        assert asyncio.run(modbus_patches._load_config(client)) == "plant"
    else:
        with pytest.raises(type(outcome)):
            asyncio.run(modbus_patches._load_config(client))
    return len(extra)

def test_after_settings_read(monkeypatch):
    assert run_load_config(monkeypatch, None) == 1

def test_after_some_settings_read(monkeypatch):
    partial = RefreshPartiallySucceeded("1 of 2 failed", plant=None, failures=[], cause=ExceptionGroup("x", [TimeoutError()]))
    assert run_load_config(monkeypatch, partial) == 1        # the inverter is answering, and the failure is still raised

def test_not_when_nothing_answered(monkeypatch):
    failed = RefreshFailed("all 2 register reads failed", failures=[], cause=ExceptionGroup("x", [TimeoutError()]))
    assert run_load_config(monkeypatch, failed) == 0

def test_not_after_lost_connection(monkeypatch):
    assert run_load_config(monkeypatch, ConnectionLost("connection lost")) == 0
