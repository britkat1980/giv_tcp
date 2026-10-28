"""EVC register decoding, cached controls and MQTT, without a charger or broker."""
import datetime
import json
import logging
import pickle
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def charger(monkeypatch, tmp_path):
    level = logging.getLogger().level
    try:
        import evc
    finally:
        logging.getLogger().setLevel(level)
    monkeypatch.setattr(evc.EVCLut, 'regcache', str(tmp_path / 'evc.pkl'))
    monkeypatch.setattr(evc.EVCLut, 'invregcache', str(tmp_path / 'inverter.pkl'))
    monkeypatch.setattr(evc.GiV_Settings, 'evc_ip_address', '192.0.2.1', raising=False)
    monkeypatch.setattr(evc.GiV_Settings, 'serial_number_evc', 'EVC00000000001', raising=False)
    client = Mock()
    monkeypatch.setattr(evc, 'ModbusTcpClient', Mock(return_value=client))
    return evc, client


def save_cache(evc, **overrides):
    data = dict(Evse_Max_Current=32, Evse_Min_Current=6, Charge_Limit=16,
                Charging_State='Charging', Charging_Mode='Grid', Charge_Control='Start',
                Import_Cap=0, Max_Session_Energy=0, Charge_Session_Energy=2,
                Active_Power_L1=1380, Current_L1=6)
    data.update(overrides)
    with open(evc.EVCLut.regcache, 'wb') as f:
        pickle.dump({'Charger': data}, f)
    return data


def test_read_registers_scales_values_and_reuses_cached_preferences(charger):
    evc, client = charger
    regs = [0] * 115
    regs[0], regs[2], regs[6], regs[13] = 4, 1, 75, 1725
    regs[32], regs[34], regs[36], regs[72], regs[79] = 320, 60, 160, 25, 3600
    regs[38:51] = [ord(c) for c in 'EVC0000000001']
    regs[97:103] = [2026, 6, 15, 12, 30, 0]
    regs[109] = 2300
    def read(address, count):
        return SimpleNamespace(registers=regs[address:address+count])
    client.read_holding_registers.side_effect = read
    data = evc.getEVC(client)
    assert data['Current_L1'] == 7.5
    assert data['Voltage_L1'] == 230
    assert data['Charge_Session_Energy'] == 2.5
    assert data['Charge_Session_Duration'] == '1:00:00'
    assert data['System_Time'] == '2026-06-15T12:30:00+00:00'
    assert data['Charging_State'] == 'Charging'
    assert data['Charge_Control'] == 'Start'
    assert data['Plug_and_Go'] == 'enable'
    evc.setImportCap(40)
    evc.setMaxSessionEnergy(12)
    regs[0], regs[72], regs[93] = 1, 0, 1
    data = evc.getEVC(client)
    assert data['Charge_Session_Energy'] == 2.5
    assert data['Import_Cap'] == 40
    assert data['Max_Session_Energy'] == 12
    assert data['Charge_Control'] == 'Stop'
    assert data['Plug_and_Go'] == 'disable'
    assert json.loads(evc.getEVCCache())['Charger'] == data


def test_missing_and_corrupt_caches_and_failed_register_reads(charger):
    evc, client = charger
    assert evc.EVCLut.get_regcache() is None
    assert json.loads(evc.getEVCCache()) == 'No EVC data found'
    assert 'Please get data' in json.loads(evc.pubFromPickle())['result']
    client.read_holding_registers.return_value = SimpleNamespace()
    assert evc.runAll(client) == {}
    client.read_holding_registers.side_effect = OSError('offline')
    assert evc.getEVC(client) == {}
    with open(evc.EVCLut.invregcache, 'wb') as f:
        f.write(b'bad pickle')
    assert evc.EVCLut.get_regcache() is None


@pytest.mark.parametrize('function,value,address,expected', [
    ('setChargeMode', 'enable', 93, [0]), ('setChargeMode', 'disable', 93, [1]),
    ('setChargeControl', 'Start', 95, [1]), ('setChargeControl', 'Stop', 95, [2]),
    ('setCurrentLimit', 1, 91, [60]), ('setCurrentLimit', 99, 91, [320]),
    ('setCurrentLimit', 16, 91, [160]),
    ('setDateTime', datetime.datetime(2026, 6, 15, 12, 30), 97, [2026, 6, 15, 12, 30, 0]),
])
def test_controls_write_expected_registers_and_clamp_current(charger, function, value, address, expected):
    evc, client = charger
    save_cache(evc)
    getattr(evc, function)(value)
    client.write_registers.assert_called_once_with(address, expected)


def test_invalid_modes_do_not_write_registers(charger):
    evc, client = charger
    evc.setChargeMode('invalid')
    evc.setChargeControl('invalid')
    evc.setChargingMode('invalid')
    client.write_registers.assert_not_called()
    assert 'failed' in json.loads(evc.setDateTime('invalid'))['result']


@pytest.mark.parametrize('mode', ['Grid', 'Hybrid', 'Solar'])
def test_charging_mode_persists_and_runs_control_check(charger, monkeypatch, mode):
    evc, _ = charger
    save_cache(evc)
    check = Mock()
    monkeypatch.setattr(evc, 'chargeMode', check)
    evc.setChargingMode(mode)
    assert json.loads(evc.getEVCCache())['Charger']['Charging_Mode'] == mode
    check.assert_called_once_with(True)


@pytest.mark.parametrize('mode,pv,expected', [('Hybrid', 3000, 19), ('Solar', 3000, 19), ('Hybrid', 0, 6), ('Solar', -3000, None)])
def test_solar_and_hybrid_modes_control_current(charger, monkeypatch, mode, pv, expected):
    evc, _ = charger
    save_cache(evc, Charging_Mode=mode)
    with open(evc.EVCLut.invregcache, 'wb') as f:
        pickle.dump([{'Power': {'Power': {'PV_Power': pv, 'Load_Power': 1380, 'Grid_Voltage': 230}}}], f)
    current, control = Mock(), Mock()
    monkeypatch.setattr(evc, 'setCurrentLimit', current)
    monkeypatch.setattr(evc, 'setChargeControl', control)
    evc.chargeMode(once=True)
    if expected is None:
        current.assert_not_called()
        control.assert_called_once_with('Stop')
    else:
        current.assert_called_once_with(expected)
        if mode == 'Solar':
            control.assert_called_once_with('Start')


@pytest.mark.parametrize('limit,expected', [(16, 9), (8, None)])
def test_import_cap_reduces_current_or_stops_at_minimum(charger, monkeypatch, limit, expected):
    evc, _ = charger
    save_cache(evc, Import_Cap=20, Charge_Limit=limit)
    with open(evc.EVCLut.invregcache, 'wb') as f:
        pickle.dump([{'Power': {'Power': {'Grid_Current': 25}}}], f)
    current, control = Mock(), Mock()
    monkeypatch.setattr(evc, 'setCurrentLimit', current)
    monkeypatch.setattr(evc, 'setChargeControl', control)
    evc.chargeMode(True)
    if expected is None:
        control.assert_called_once_with('Stop')
    else:
        current.assert_called_once_with(expected)


def test_session_energy_limit_stops_charging(charger, monkeypatch):
    evc, _ = charger
    save_cache(evc, Max_Session_Energy=2)
    control = Mock()
    monkeypatch.setattr(evc, 'setChargeControl', control)
    evc.chargeMode(True)
    control.assert_called_once_with('Stop')


def test_publication_converts_values_and_flattens_topics(charger, monkeypatch):
    evc, _ = charger
    client = Mock(connected_flag=True)
    monkeypatch.setattr(evc, 'get_connection', lambda: client)
    data = {'Charger': {'watts': 1.23456, 'time': datetime.time(1, 30),
                       'date': datetime.datetime(2026, 6, 15, 12),
                       'slot': (datetime.time(1), datetime.time(2)), 'pair': (1, 2)}}
    safe = evc.iterate_dict(data)
    assert safe['Charger'] == dict(watts=1.235, time='01:30', date='15-06-2026 12:00:00',
                                  slot_start='01:00', slot_end='02:00', pair_0='1', pair_1='2')
    evc.multi_MQTT_publish('GivEnergy/SN/', safe)
    assert client.publish.call_count == 7
    client.publish.assert_any_call('GivEnergy/SN/Charger/watts', 1.235, retain=evc.GiV_Settings.MQTT_Retain)
    assert evc.iterate_dict_mqtt(5, 'root') == {'root': 5}
    assert evc.isfloat('1.2') and not evc.isfloat('bad')


@pytest.mark.parametrize('command,function,payload,value', [
    ('chargeMode', 'setChargeMode', 'enable', 'enable'),
    ('controlCharge', 'setChargeControl', 'Start', 'Start'),
    ('setCurrentLimit', 'setCurrentLimit', '12', 12),
    ('setImportCap', 'setImportCap', '20', '20'),
    ('setChargingMode', 'setChargingMode', 'Solar', 'Solar'),
    ('setMaxSessionEnergy', 'setMaxSessionEnergy', '10', 10),
    ('setSystemTime', 'setDateTime', 'now', 'now'),
])
def test_mqtt_dispatch(charger, monkeypatch, command, function, payload, value):
    evc, _ = charger
    handler = Mock()
    monkeypatch.setattr(evc, function, handler)
    msg = SimpleNamespace(topic=f'GivEnergy/control/EVC00000000001/{command}', payload=payload.encode())
    evc.on_message(None, None, msg)
    handler.assert_called_once_with(value)
    msg.topic = f'GivEnergy/control/other/{command}'
    evc.on_message(None, None, msg)
    assert handler.call_count == 1


def test_publish_cached_output_and_connect_callbacks(charger, monkeypatch):
    evc, _ = charger
    save_cache(evc, Serial_Number='EVC00000000001')
    publish = Mock()
    monkeypatch.setattr(evc, 'publishOutput', publish)
    assert json.loads(evc.pubFromPickle())['Charger']['Serial_Number'] == 'EVC00000000001'
    publish.assert_called_once()
    client = Mock(connected_flag=False)
    evc.on_connect(client, None, None, 0, None)
    assert client.connected_flag is True
    client.subscribe.assert_called_once_with(evc.MQTT_Topic + '/control/#')


def test_first_publication_discovers_once_and_records_serial(charger, monkeypatch, tmp_path):
    evc, _ = charger
    import EVC_HA_Discovery
    monkeypatch.setattr(evc, '__file__', str(tmp_path / 'evc.py'))
    settings_file = tmp_path / 'settings.py'
    settings_file.write_text('class GiV_Settings:\n    first_run_evc= True\n')
    monkeypatch.setattr(evc.GiV_Settings, 'first_run_evc', True, raising=False)
    monkeypatch.setattr(evc.GiV_Settings, 'MQTT_Output', True)
    monkeypatch.setattr(evc.GiV_Settings, 'HA_Auto_D', True)
    discovery, publish = Mock(), Mock()
    monkeypatch.setattr(EVC_HA_Discovery.HAMQTT, 'publish_discovery2', discovery)
    monkeypatch.setattr(evc, 'multi_MQTT_publish', publish)
    data = {'Charger': {'Current_L1': 6}}
    for _ in range(2):
        evc.publishOutput(data, 'EVC00000000001')
    discovery.assert_called_once_with(data, 'EVC00000000001')
    assert publish.call_count == 2
    contents = settings_file.read_text()
    assert 'first_run_evc= False' in contents
    assert contents.count('serial_number_evc') == 1
    evc.updateFirstRun('EVC00000000001')
    assert settings_file.read_text() == contents


def test_connection_reconnects_and_publish_failure_disconnects(charger, monkeypatch):
    evc, _ = charger
    client = Mock(connected_flag=False)
    client.loop_start.side_effect = lambda: setattr(client, 'connected_flag', True)
    monkeypatch.setattr(evc, '_client', client)
    monkeypatch.setattr(evc, 'MQTTCredentials', True)
    monkeypatch.setattr(evc, 'MQTT_Username', 'user', raising=False)
    monkeypatch.setattr(evc, 'MQTT_Password', 'password', raising=False)
    assert evc.get_connection() is client
    client.username_pw_set.assert_called_once_with('user', 'password')
    evc.get_connection()
    assert client.connect.call_count == 1
    client.publish.side_effect = OSError('offline')
    evc.multi_MQTT_publish('root/', {'Charger': {'Current_L1': 6}})
    client.loop_stop.assert_called_once()
    client.disconnect.assert_called_once()


def test_poll_loop_pauses_after_eleven_failed_reads(charger, monkeypatch):
    evc, client = charger
    monkeypatch.setattr(evc.GiV_Settings, 'evc_self_run_timer', 15, raising=False)
    read = Mock(return_value={})
    monkeypatch.setattr(evc, 'runAll', read)
    class EndLoop(BaseException):
        pass
    delays = []
    def sleep(seconds):
        delays.append(seconds)
        if seconds == 300:
            raise EndLoop
    monkeypatch.setattr(evc.time, 'sleep', sleep)
    with pytest.raises(EndLoop):
        evc.self_run2()
    assert read.call_count == 11
    assert delays == [15] * 10 + [300]
    client.close.assert_called_once()
