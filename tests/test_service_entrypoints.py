"""Run standalone entry points with fake network clients and workers."""
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from harness.env import ROOT


@pytest.mark.parametrize('script,function,port', [('findEVC.py', 'findEVC', 502), ('findInvertor.py', 'findInvertor', 8899)])
def test_discovery_cli_calls_scan(monkeypatch, script, function, port):
    from GivTCP import netscan
    scan = Mock(return_value={port: ['192.0.2.1']})
    monkeypatch.setattr(netscan, 'scan', scan)
    monkeypatch.setattr(sys, 'argv', [script, function, '192.0.2.0/24'])
    runpy.run_path(str(ROOT / 'GivTCP' / script), run_name='__main__')
    scan.assert_called_once_with('192.0.2.0/24', ports=(port,))


def test_worker_starts_instance_queue_with_scheduler(monkeypatch):
    import redis
    import rq
    connection = Mock()
    monkeypatch.setattr(redis, 'from_url', Mock(return_value=connection))
    worker = Mock()
    constructor = Mock(return_value=worker)
    monkeypatch.setattr(rq, 'Worker', constructor)
    result = runpy.run_path(str(ROOT / 'GivTCP/worker.py'), run_name='__main__')
    constructor.assert_called_once_with(result['listen'], connection=connection)
    worker.work.assert_called_once_with(with_scheduler=True, logging_level=50)


@pytest.mark.parametrize('found', [False, True])
def test_manual_discovery_retries_and_reports_device_details(monkeypatch, found):
    from GivTCP import findInvertor
    import givenergy_modbus.client.client as modbus
    scan = Mock(return_value={1: '192.0.2.1'} if found else {})
    monkeypatch.setattr(findInvertor, 'findInvertor', scan)
    caps = SimpleNamespace(device_type=SimpleNamespace(name='HYBRID'), lv_battery_addresses=[0x32],
                           bcu_stacks=[], aio_battery_module_addresses=[], hv_bmu_addresses=[])
    client = Mock(connect=AsyncMock(), detect=AsyncMock(return_value=caps), close=AsyncMock())
    client.plant.inverter = SimpleNamespace(serial_number='TEST00001', arm_firmware_version=100)
    monkeypatch.setattr(modbus, 'Client', Mock(return_value=client))
    result = runpy.run_path(str(ROOT / 'findinvdev.py'))
    if found:
        assert result['inverterStats'][1] == dict(Serial_Number='TEST00001', Firmware=100,
            Model=caps.device_type, Number_of_Batteries=1, IP_Address='192.0.2.1')
        client.close.assert_awaited_once()
    else:
        assert result['inverterStats'] == {}
        assert scan.call_count == 2


@pytest.fixture
def evc_control(monkeypatch):
    import evc
    import paho.mqtt.client as mqtt
    from settings import GiV_Settings
    monkeypatch.setattr(GiV_Settings, 'serial_number_evc', 'EVC00000000001', raising=False)
    client = Mock()
    # Use a class: the script also sets a class attribute on Client.
    class Client:
        def __new__(cls, *args, **kwargs):
            return client
    monkeypatch.setattr(mqtt, 'Client', Client)
    result = runpy.run_path(str(ROOT / 'GivTCP/mqtt_client_evc.py'))
    client.connect.assert_called_once_with(GiV_Settings.MQTT_Address, port=int(GiV_Settings.MQTT_Port))
    client.loop_forever.assert_called_once()
    return result, client, evc


@pytest.mark.parametrize('command,function,payload,value', [
    ('chargeMode', 'setChargeMode', 'enable', 'enable'),
    ('controlCharge', 'setChargeControl', 'Start', 'Start'),
    ('setCurrentLimit', 'setCurrentLimit', '12', 12),
    ('setImportCap', 'setImportCap', '20', '20'),
    ('setChargingMode', 'setChargingMode', 'Solar', 'Solar'),
    ('setMaxSessionEnergy', 'setMaxSessionEnergy', '10', 10),
    ('setSystemTime', 'setDateTime', 'now', 'now'),
])
def test_evc_control_subscriber_dispatches_messages(evc_control, monkeypatch, command, function, payload, value):
    result, client, evc = evc_control
    handler = Mock()
    monkeypatch.setattr(evc, function, handler)
    result['on_message'](client, None, SimpleNamespace(topic='control/' + command, payload=payload.encode()))
    handler.assert_called_once_with(value)
    result['on_connect'](client, None, None, 0, None)
    client.subscribe.assert_called_once_with('GivEnergy/control/EVC00000000001/#')
    assert client.connected_flag is True
    assert result['isfloat']('1.2') and not result['isfloat']('bad')


def test_settings_template_keeps_runtime_defaults():
    result = runpy.run_path(str(ROOT / 'GivTCP/settings_template.py'))
    settings = result['GiV_Settings']
    assert settings.MQTT_Port == 1883
    assert settings.givtcp_instance == 1
    assert settings.self_run is True
