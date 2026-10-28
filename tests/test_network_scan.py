"""Device discovery without probing the developer's network."""
import asyncio
import ipaddress
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from GivTCP import netscan, findEVC, findInvertor


@pytest.mark.parametrize("subnet,local_count,rest_count", [
    ("192.168.1.10/30", 2, 0),
    ("192.168.1.10/23", 254, 255),
    ("10.2.3.4/8", 254, 65278),
])
def test_targets_prioritise_local_subnet_and_cap_large_networks(subnet, local_count, rest_count):
    local, rest = netscan._targets(subnet)
    rest = list(rest)
    assert len(local) == local_count
    assert len(rest) == rest_count
    assert not set(local) & set(rest)
    assert ipaddress.IPv4Address(subnet.split('/')[0]) in local


@pytest.mark.parametrize("error", [None, OSError("refused"), asyncio.TimeoutError()])
def test_probe_closes_successful_connections(monkeypatch, error):
    writer = SimpleNamespace(close=Mock(), wait_closed=AsyncMock())
    connect = AsyncMock(return_value=(None, writer), side_effect=error)
    monkeypatch.setattr(netscan.asyncio, "open_connection", connect)
    assert asyncio.run(netscan._probe("192.0.2.1", 502, 0.1)) is (error is None)
    if error is None:
        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()


def test_scan_workers_sort_numerically_and_probe_each_port(monkeypatch):
    probe = AsyncMock(side_effect=lambda ip, port, timeout: port == 502)
    monkeypatch.setattr(netscan, "_probe", probe)
    monkeypatch.setattr(netscan, "_concurrency", lambda: 2)
    found = asyncio.run(netscan._scan(["192.0.2.10", "192.0.2.2"], (502, 8899), 0.1))
    assert found == {502: ["192.0.2.2", "192.0.2.10"], 8899: []}
    assert probe.await_count == 4


@pytest.mark.parametrize("ports,local,expand", [
    ((502, 8899), {502: ["192.0.2.1"], 8899: []}, True),
    ((502, 8899), {502: [], 8899: ["192.0.2.1"]}, False),
    ((502,), {502: ["192.0.2.1"]}, False),
    ((502,), {502: []}, True),
])
def test_scan_expands_only_when_wanted_device_is_missing(monkeypatch, ports, local, expand):
    monkeypatch.setattr(netscan, "_targets", lambda subnet: (["192.0.2.1"], ["192.0.3.1"]))
    more = {p: ["192.0.3.1"] for p in ports}
    scan = AsyncMock(side_effect=[{p: list(v) for p, v in local.items()}, more])
    monkeypatch.setattr(netscan, "_scan", scan)
    result = netscan.scan("192.0.2.1/23", ports=ports)
    assert scan.await_count == 1 + expand
    assert result == {p: local[p] + (more[p] if expand else []) for p in ports}


def test_discovery_wrappers_keep_legacy_numbered_result(monkeypatch, capsys):
    for module, function, port in [(findEVC, findEVC.findEVC, 502),
                                   (findInvertor, findInvertor.findInvertor, 8899)]:
        scan = Mock(return_value={port: ["192.0.2.2", "192.0.2.10"]})
        monkeypatch.setattr(module, "scan", scan)
        assert function("192.0.2.0/24") == {1: "192.0.2.2", 2: "192.0.2.10"}
        scan.assert_called_once_with("192.0.2.0/24", ports=(port,))
    findEVC.start()
    assert "EVC List:" in capsys.readouterr().out
    assert netscan.as_list([]) == {}
