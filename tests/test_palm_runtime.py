"""PALM forecasts, load history and register commands with deterministic API replies."""
import ast
import copy
import importlib
import json
import runpy
from unittest.mock import Mock

import pytest
from harness.env import ROOT


@pytest.fixture(autouse=True)
def palm_state(monkeypatch):
    global palm
    from GivLUT import GivLUT
    with monkeypatch.context() as importing:
        importing.setattr(GivLUT, 'get_regcache', lambda: [])
        palm = importlib.import_module('palm_utils')
    # The module's mutable lists normally live for the lifetime of its standalone process.
    monkeypatch.setattr(palm.stgs.GE, 'base_load', list(palm.stgs.GE.base_load))
    monkeypatch.setattr(palm.stgs.pg, 'month', '06')
    monkeypatch.setattr(palm.time, 'sleep', lambda seconds: None)


def response(data, status=200):
    return Mock(content=json.dumps({'data': data}).encode(), status_code=status)


@pytest.mark.parametrize('text,minutes', [('00:00', 0), ('23:59', 1439), ('07:30:00', 450), ('bad', 0)])
def test_time_conversion(text, minutes):
    assert palm.t_to_mins(text) == minutes
    assert palm.t_to_hrs(minutes) == ('00:00' if text == 'bad' else text[:5])
    assert palm.t_to_hrs(None) == '00:00'


def test_latest_data_updates_measurements_and_throttles_api(monkeypatch):
    inverter = palm.GivEnergyObj()
    system = copy.deepcopy(inverter.sys_status[0])
    system.update(time='2026-06-15T12:00:00Z', consumption=300)
    system['grid'].update(voltage=230, power=100)
    system['solar']['power'] = 1500
    system['battery'].update(power=-200, percent=75)
    meter = copy.deepcopy(inverter.meter_status[0])
    meter['today'].update(solar=2.5, consumption=1.2)
    request = Mock(side_effect=[response(system), response(meter)])
    monkeypatch.setattr(palm.requests, 'request', request)
    monkeypatch.setattr(palm.time, 'strftime', lambda *args: '12:00:00')
    inverter.get_latest_data()
    assert (inverter.line_voltage, inverter.grid_power, inverter.pv_power, inverter.batt_power,
            inverter.consumption, inverter.soc) == (230, -100, 1500, -200, 300, 75)
    assert (inverter.pv_energy, inverter.grid_energy) == (2500, 1200)
    assert all(row == system for row in inverter.sys_status)
    inverter.get_latest_data()
    assert request.call_count == 2


def test_latest_data_network_failure_keeps_previous_readings(monkeypatch):
    inverter = palm.GivEnergyObj()
    monkeypatch.setattr(palm.requests, 'request', Mock(side_effect=palm.requests.exceptions.ConnectionError('offline')))
    inverter.get_latest_data()
    assert inverter.read_time_mins == -100
    assert inverter.soc == 0


def test_load_history_uses_daily_weights_and_half_hour_differences(monkeypatch):
    monkeypatch.setattr(palm.stgs.GE, 'load_hist_weight', [1, 0, 3])
    histories = [[{'today': {'consumption': i * rate}} for i in range(290)] for rate in (0.1, 0.3)]
    request = Mock(side_effect=[response(rows) for rows in histories])
    monkeypatch.setattr(palm.requests, 'request', request)
    inverter = palm.GivEnergyObj()
    inverter.get_load_hist()
    assert inverter.base_load == [1.5] * 48
    assert request.call_count == 2


@pytest.mark.parametrize('kind', ['no_weights', 'http_error', 'connection_error'])
def test_load_history_unavailable_returns_zero_load(monkeypatch, kind):
    monkeypatch.setattr(palm.stgs.GE, 'load_hist_weight', [0] if kind == 'no_weights' else [1])
    request = Mock(return_value=response({}, 503))
    if kind == 'connection_error':
        request.side_effect = palm.requests.exceptions.ConnectionError('offline')
    monkeypatch.setattr(palm.requests, 'request', request)
    inverter = palm.GivEnergyObj()
    inverter.get_load_hist()
    assert inverter.base_load == [0] * 48


@pytest.mark.parametrize('command,expected', [
    ('set_soc', [('77', '60'), ('64', '00:30'), ('65', '07:30')]),
    ('set_soc_winter', [('77', '100'), ('64', '00:30'), ('65', '08:00')]),
    ('charge_now', [('77', '100'), ('64', '00:01'), ('65', '23:59')]),
    ('charge_now_soc', [('77', '60'), ('64', '00:01'), ('65', '23:59')]),
    ('pause', [('72', '0'), ('73', '0')]), ('pause_charge', [('72', '0')]),
    ('pause_discharge', [('73', '0')]),
    ('resume', [('72', '3000'), ('73', '3000'), ('77', '60'), ('64', '00:30'), ('65', '07:30')]),
    ('test', []), ('unknown', []),
])
def test_mode_commands_write_and_verify_expected_registers(monkeypatch, command, expected):
    monkeypatch.setattr(palm.stgs.GE, 'start_time', '00:30')
    monkeypatch.setattr(palm.stgs.GE, 'end_time', '07:30')
    monkeypatch.setattr(palm.stgs.GE, 'end_time_winter', '08:00', raising=False)
    inverter = palm.GivEnergyObj()
    inverter.cmd_list = palm.stgs.GE_Command_list['data']
    inverter.tgt_soc = 60
    replies = []
    for _, value in expected:
        replies.extend([response({}, 201), response({'value': value}, 201)])
    request = Mock(side_effect=replies)
    monkeypatch.setattr(palm.requests, 'request', request)
    inverter.set_mode(command)
    writes = [(c.args[1].split('/')[-2], c.kwargs['json']['value'])
              for c in request.call_args_list if c.args[1].endswith('/write')]
    assert writes == expected
    assert request.call_count == 2 * len(expected)


@pytest.mark.parametrize('month,generation,expected', [('01', 5, 'set_soc_winter'), ('06', 0, 'set_soc')])
def test_target_falls_back_to_full_charge_in_winter_or_without_forecast(monkeypatch, month, generation, expected):
    monkeypatch.setattr(palm.stgs.pg, 'month', month)
    forecast = palm.SolcastObj()
    forecast.pv_est50_day[0] = generation
    inverter = palm.GivEnergyObj()
    assert inverter.compute_tgt_soc(forecast, 35, True) == expected
    assert inverter.tgt_soc == 100


@pytest.mark.parametrize('month,weight,generation,commit', [
    ('06', 10, 0.001, True), ('06', 50, 5, True), ('03', 90, 5, True), ('06', 120, 5, False),
])
def test_target_respects_bounds_and_emits_two_day_plot(monkeypatch, month, weight, generation, commit):
    monkeypatch.setattr(palm.stgs.pg, 'month', month)
    forecast = palm.SolcastObj()
    forecast.pv_est50_day[0] = generation * 48
    forecast.pv_est10_30 = [generation * 0.5] * 96
    forecast.pv_est50_30 = [generation] * 96
    forecast.pv_est90_30 = [generation * 1.5] * 96
    inverter = palm.GivEnergyObj()
    assert inverter.compute_tgt_soc(forecast, weight, commit) == ('set_soc' if commit else 'test')
    minimum = 45 if month == '03' else 25
    assert minimum <= inverter.tgt_soc <= 100
    if commit and generation == 5:
        assert inverter.tgt_soc == minimum
    assert all(len(ast.literal_eval(row)) == 97 for row in inverter.plot)
    assert max(ast.literal_eval(inverter.plot[2])[1:]) <= 100


@pytest.mark.parametrize('second_array', [False, True])
def test_solcast_combines_arrays_into_daily_and_half_hour_energy(monkeypatch, second_array):
    monkeypatch.setattr(palm.stgs.Solcast, 'url_sw', 'https://example.invalid/second' if second_array else '')
    monkeypatch.setattr(palm.time, 'strftime', lambda fmt, *args: '+0000' if fmt == '%z' else 'test')
    lines = [{'period': 'PT30M', 'period_end': '2026-06-15T01:30:00Z',
              'pv_estimate10': 1, 'pv_estimate': 2, 'pv_estimate90': 3} for _ in range(100)]
    reply = Mock(status_code=200, content=json.dumps({'forecasts': lines}).encode())
    get = Mock(return_value=reply)
    monkeypatch.setattr(palm.requests, 'get', get)
    forecast = palm.SolcastObj()
    forecast.update()
    factor = 2 if second_array else 1
    assert forecast.pv_est50_30[2] == round(2 * factor * 29 / 60, 3)
    assert forecast.pv_est10_day[0] < forecast.pv_est50_day[0] < forecast.pv_est90_day[0]
    assert get.call_count == factor


@pytest.mark.parametrize('kind', ['short', 'http', 'offline'])
def test_solcast_failure_retains_last_forecast(monkeypatch, kind):
    reply = Mock(status_code=503 if kind == 'http' else 200, content=b'{}')
    get = Mock(return_value=reply)
    if kind == 'offline':
        get.side_effect = palm.requests.exceptions.ConnectionError('offline')
    monkeypatch.setattr(palm.requests, 'get', get)
    forecast = palm.SolcastObj()
    forecast.pv_est50_day[0] = 12
    forecast.update()
    assert forecast.pv_est50_day[0] == 12


def test_soc_script_fetches_history_forecast_and_writes_target(monkeypatch):
    inverter = Mock(tgt_soc=60, plot=['plot'] * 5)
    inverter.compute_tgt_soc.return_value = 'set_soc'
    monkeypatch.setattr(palm, 'GivEnergyObj', Mock(return_value=inverter))
    forecast = Mock()
    monkeypatch.setattr(palm, 'SolcastObj', Mock(return_value=forecast))
    from GivLUT import GivLUT
    target = Mock()
    monkeypatch.setattr(GivLUT, 'queue_write', target)
    result = runpy.run_path(str(ROOT / 'GivTCP/palm_soc.py'), run_name='__main__')
    inverter.get_load_hist.assert_called_once()
    forecast.update.assert_called_once()
    target.assert_called_once_with('setChargeTarget', {'chargeToPercent': 60})
    inverter.set_mode.assert_not_called()
    result['GivTCP_write_soc']('set_soc_winter')
    target.assert_called_with('setChargeTarget', {'chargeToPercent': 100})
    target.side_effect = OSError('offline')
    result['GivTCP_write_soc']('set_soc')
    inverter.set_mode.assert_called_once_with('set_soc')
    result['GivTCP_write_soc']('set_soc_winter')
    inverter.set_mode.assert_called_with('set_soc_winter')


def test_palm_settings_defaults_and_optional_second_array(monkeypatch):
    from GivLUT import GivLUT
    from settings import GiV_Settings
    monkeypatch.setattr(GivLUT, 'get_regcache', lambda: [])
    monkeypatch.setattr(GiV_Settings, 'SOLCASTSITEID2', 'second')
    settings = runpy.run_path(str(ROOT / 'GivTCP/palm_settings.py'))
    assert settings['GE'].batt_capacity == 10.4
    assert settings['GE'].batt_max_charge == pytest.approx(8.84)
    assert settings['Solcast'].url_sw.endswith('/second')
    assert settings['Solcast'].isBlank('  ')
