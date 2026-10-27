"""Validate Home Assistant payloads and retained-message lifecycle for EVCs."""
import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from entity_lut import Entity_Type

# evc configures the root logger when imported by discovery. Keep collection from
# changing the logging configuration used by the inverter integration tests.
_root_level = logging.getLogger().level
try:
    import EVC_HA_Discovery as discovery
finally:
    logging.getLogger().setLevel(_root_level)


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(discovery.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(discovery.CheckDisco, 'msgs', {})


# This module builds shared entity payloads too. Exercise each supported sensor class
# and number control using the real catalogue, including EVC-specific selects.
ITEMS = [name for name, entity in Entity_Type.entity_type.items()
         if entity.devType in {'sensor', 'number', 'switch', 'button'}
         or name in {'Charging_Mode', 'Charge_Control'}]


@pytest.mark.parametrize('item', ITEMS)
def test_payload_has_valid_identity_availability_and_control(item, monkeypatch):
    monkeypatch.setattr(discovery.HAMQTT, 'getinvbatmax', lambda: 5000)
    sn = 'EVC00000000001'
    topic = f'GivEnergy/{sn}/Charger/{item}'
    payload = json.loads(discovery.HAMQTT.create_device_payload(topic, sn))
    entity = Entity_Type.entity_type[item]
    assert payload['stat_t'] == topic
    assert payload['unique_id'].endswith('_' + sn + '_' + item)
    assert payload['device']['manufacturer'] == 'GivEnergy'
    assert payload['device']['name'] == 'GivEVC'
    assert payload['avty_t'] == f'GivEnergy/{sn}/Stats/status'
    if entity.controlFunc:
        assert payload['command_topic'] == f'GivEnergy/control/{sn}/{entity.controlFunc}'
    if entity.devType == 'number' and 'min' in payload:
        assert payload['min'] < payload['max']
    if entity.sensorClass == 'energy':
        assert payload['unit_of_meas'] == 'kWh'
        assert payload['state_class'] == ('total_increasing' if entity.onlyIncrease else 'total')


@pytest.mark.parametrize('section', ['Battery_Details/BAT001', 'Inverters/INV001', 'Charger'])
def test_nested_device_payloads_have_stable_names(section):
    payload = json.loads(discovery.HAMQTT.create_device_payload(f'GivEnergy/INV000001/{section}/SOC', 'INV000001', None))
    assert payload['name'] == 'SOC'
    assert payload['device']['model'] == 'EVC'
    assert payload['device']['identifiers']


def test_discovery_publishes_sensor_switch_number_and_select(monkeypatch):
    sent = []
    monkeypatch.setattr(discovery.CheckDisco, 'removedisco', Mock())
    def send(messages, sn):
        sent.extend(messages)
        return []
    monkeypatch.setattr(discovery.HAMQTT, 'sendDiscoMsg', send)
    data = {'Charger': {'Current_L1': 6, 'Plug_and_Go': 'enable', 'Charge_Limit': 16,
                        'Charging_Mode': 'Solar', 'Charge_Control': 'Start'}, 'raw': {'ignore': 1}}
    discovery.HAMQTT.publish_discovery2(data, 'EVC00000000001')
    assert len(sent) == 6  # five values and the timeout sensor
    assert {t.split('/')[1] for t, _ in sent} == {'sensor', 'switch', 'number', 'select'}
    assert all(json.loads(payload)['device']['manufacturer'] == 'GivEnergy' for _, payload in sent)


def test_discovery_retries_missing_messages_four_times(monkeypatch):
    monkeypatch.setattr(discovery.CheckDisco, 'removedisco', Mock())
    send = Mock(side_effect=lambda messages, sn: messages)
    monkeypatch.setattr(discovery.HAMQTT, 'sendDiscoMsg', send)
    discovery.HAMQTT.publish_discovery2({'Charger': {'Current_L1': 6}}, 'EVC00000000001')
    assert send.call_count == 4


@pytest.fixture
def broker(monkeypatch):
    client = Mock(connected_flag=True)
    class Client:
        def __new__(cls, *args, **kwargs):
            return client
    monkeypatch.setattr(discovery.paho_mqtt, 'Client', Client)
    return client


def test_send_announces_online_and_returns_missing_configs(broker, monkeypatch):
    missing = [['topic/config', '{}']]
    check = Mock(return_value=missing)
    monkeypatch.setattr(discovery.CheckDisco, 'checkdisco', check)
    assert discovery.HAMQTT.sendDiscoMsg(missing, 'SN') == missing
    broker.will_set.assert_called_once_with('GivEnergy/SN/Stats/status', 'offline', retain=True)
    broker.publish.assert_any_call('GivEnergy/SN/Stats/status', 'online', retain=True)
    broker.publish.assert_any_call('topic/config', '{}', retain=True)
    broker.loop_stop.assert_called_once()
    broker.disconnect.assert_called_once()


def test_retained_check_returns_only_unreceived_messages(broker):
    discovery.CheckDisco.on_message(broker, None, SimpleNamespace(topic='seen', payload=b'{}'))
    assert discovery.CheckDisco.checkdisco([['seen', '{}'], ['missing', '{}']]) == [['missing', '{}']]
    discovery.CheckDisco.on_connect(broker, None, None, 0, None)
    broker.subscribe.assert_any_call('homeassistant/#')
    discovery.CheckDisco.on_disconnect(broker, None, None, 0, None)
    assert discovery.CheckDisco.msgs == {}


def test_upgrade_removes_only_this_devices_retained_messages(broker, monkeypatch):
    monkeypatch.setattr(discovery, 'exists', lambda path: True)
    retained = {'homeassistant/sensor/SN_SOC/config': '{}', 'homeassistant/sensor/other/config': '{}'}
    broker.loop_start.side_effect = lambda: discovery.CheckDisco.msgs.update(retained)
    discovery.CheckDisco.removedisco('SN', [])
    broker.publish.assert_called_once_with('homeassistant/sensor/SN_SOC/config', None, 0, True)
    assert discovery.CheckDisco.msgs == {'homeassistant/sensor/other/config': '{}'}
    broker.disconnect.assert_called_once()


@pytest.mark.parametrize('cache,expected', [(None, 5000),
    ([{'Invertor_Serial_Number': 'SN', 'SN': {}}], 5000),
    ([{'Invertor_Serial_Number': 'SN', 'SN': {'Invertor_Max_Bat_Rate': 3600}}], 3600)])
def test_battery_rate_uses_cache_or_safe_default(monkeypatch, cache, expected):
    monkeypatch.setattr(discovery.EVCLut, 'get_regcache', lambda: cache)
    assert discovery.HAMQTT.getinvbatmax() == expected
    assert discovery.HAMQTT.finditem({'outer': {'key': 1}}, 'key') == 1
    assert discovery.HAMQTT.finditem({}, 'missing') is None
