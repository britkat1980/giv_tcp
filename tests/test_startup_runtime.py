"""Execute the original startup script in a simulated container.

Only startup's imports and file operations are replaced. Functions keep their original
filename/line numbers, so coverage measures the actual script, including its watchdog.
"""
import asyncio
import builtins
import datetime
import json
import logging
import os
import pickle
import shutil
import signal
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from givenergy_modbus.model.inverter import Model
from givenergy_modbus.model.plant import PlantCapabilities
from harness.env import ROOT


class EndWatchdog(BaseException):
    pass


@pytest.fixture
def container(tmp_path):
    processes = []
    cwd = ['/app']
    def mapped(path):
        path = os.fsdecode(path)
        if path.startswith(('/app', '/config', '/etc', '/ssl')):
            return tmp_path / path.lstrip('/')
        if not os.path.isabs(path):
            return tmp_path / cwd[0].lstrip('/') / path
        return Path(path)

    for folder in ['app/GivTCP', 'app/ingress', 'app/WebDashboard', 'etc/nginx/http.d', 'config/GivTCP/logs']:
        (tmp_path / folder).mkdir(parents=True)
    template = json.loads((ROOT / 'settings.json').read_text())
    template.update(number_of_inverters=1, auto_scan=False, Web_Dash=False, Smart_Target=False,
                    self_run=True, cache_location='/config/GivTCP', MQTT_Address='127.0.0.1')
    (tmp_path / 'app/settings.json').write_text(json.dumps(template))
    (tmp_path / 'app/ingress_no_ssl.conf').write_text('nginx')

    class Process:
        def __init__(self, args, **kwargs):
            self.args, self.kwargs = args, kwargs
            self.pid = 100 + len(processes)
            self.returncode = None
            self.kill, self.terminate, self.wait = Mock(), Mock(), Mock()
            processes.append(self)
        def poll(self):
            return self.returncode

    def open_file(path, mode='r', *args, **kwargs):
        return builtins.open(mapped(path), mode, *args, **kwargs)

    fake_os = SimpleNamespace(**vars(os))
    fake_os.path = SimpleNamespace(**vars(os.path))
    fake_os.path.exists = lambda path: mapped(path).exists()
    fake_os.path.isdir = lambda path: mapped(path).is_dir()
    fake_os.path.getmtime = lambda path: mapped(path).stat().st_mtime
    fake_os.makedirs = lambda path, **kwargs: mapped(path).mkdir(parents=True, **kwargs)
    fake_os.chdir = lambda path: cwd.__setitem__(0, path)
    fake_os.listdir = lambda path: os.listdir(mapped(path))
    fake_os.remove = lambda path: mapped(path).unlink()
    def symlink(src, dest):
        # Windows can deny symlinks without Developer Mode or elevated privileges.
        # The simulated container only needs the config to be readable at dest.
        try:
            mapped(dest).symlink_to(mapped(src))
        except OSError:
            shutil.copyfile(mapped(src), mapped(dest))
    fake_os.symlink = symlink
    fake_os.killpg = Mock()
    fake_os._exit = Mock(side_effect=EndWatchdog)
    fake_os.getenv = lambda key: {'SUPERVISOR_TOKEN': 'test-token'}.get(key)
    fake_os.environ = {}
    fake_shutil = SimpleNamespace(copyfile=lambda src, dst: shutil.copyfile(mapped(src), mapped(dst)),
        copy=lambda src, dst: shutil.copy(mapped(src), mapped(dst)),
        copytree=lambda src, dst: shutil.copytree(mapped(src), mapped(dst)))
    fake_subprocess = SimpleNamespace(**vars(subprocess))
    fake_subprocess.Popen = Process
    fake_signal = SimpleNamespace(**vars(signal))
    fake_signal.SIGKILL = getattr(signal, 'SIGKILL', 9)  # simulated Linux container
    fake_signal.signal = Mock()
    schedule = Mock()
    schedule.run_pending.side_effect = EndWatchdog
    get = Mock(side_effect=lambda url, **kwargs: SimpleNamespace(json=lambda: {
        'http://supervisor/services/mqtt': {'result': 'error'},
        'http://supervisor/info': {'data': {'timezone': 'Europe/London'}},
        'http://supervisor/addons/self/info': {'data': {'ingress_url': '/test'}},
        'http://supervisor/network/info': {'data': {'interfaces': [{'ipv4': {'address': ['192.0.2.1/24']}}]}},
    }[url]))
    caps = PlantCapabilities(device_type=Model.HYBRID, inverter_address=0x11,
                             arm_firmware_version=100, lv_battery_addresses=[0x32])
    client = Mock(connect=AsyncMock(), probe_alive=AsyncMock(return_value=True),
                  detect=AsyncMock(return_value=caps), close=AsyncMock())
    client.plant = SimpleNamespace(inverter=SimpleNamespace(serial_number='TEST000001',
        arm_firmware_version=100, device_type_code=2001), register_caches={})
    from GivTCP import netscan
    scan = Mock(return_value={8899: [], 502: []})
    imports = {
        'os': fake_os, 'os.path': fake_os.path, 'shutil': fake_shutil,
        'subprocess': fake_subprocess, 'signal': fake_signal, 'schedule': schedule,
        'time': SimpleNamespace(sleep=Mock()), 'requests': SimpleNamespace(get=get),
        'GivTCP.sharedlog': SimpleNamespace(SharedTimedRotatingFileHandler=lambda *a, **kw: logging.NullHandler()),
        'GivTCP.netscan': SimpleNamespace(scan=scan, as_list=netscan.as_list, INVERTER_PORT=8899, EVC_PORT=502),
        'givenergy_modbus.client.client': SimpleNamespace(Client=Mock(return_value=client)),
        'pymodbus.client': SimpleNamespace(ModbusTcpClient=Mock()),
    }
    real_import = builtins.__import__
    def importing(name, *args, **kwargs):
        return imports[name] if name in imports else real_import(name, *args, **kwargs)
    namespace = {'__name__': '__main__', '__file__': str(ROOT / 'startup.py'),
                 '__builtins__': {**vars(builtins), '__import__': importing, 'open': open_file}}
    def run(**overrides):
        template.update(overrides)
        (tmp_path / 'config/GivTCP/allsettings.json').write_text(json.dumps(template))
        logger = logging.getLogger()
        handlers, level = list(logger.handlers), logger.level
        library_logger = logging.getLogger('givenergy_modbus')
        library_level = library_logger.level
        try:
            with pytest.raises(EndWatchdog):
                exec(compile((ROOT / 'startup.py').read_text(), str(ROOT / 'startup.py'), 'exec'), namespace)
        finally:
            logger.handlers[:] = handlers
            logger.setLevel(level)
            library_logger.setLevel(library_level)
        return namespace
    return SimpleNamespace(run=run, path=tmp_path, mapped=mapped, processes=processes,
        os=fake_os, imports=imports, scan=scan, client=client, caps=caps, schedule=schedule)


def test_startup_generates_instance_settings_routes_and_launches_services(container):
    c = container
    ns = c.run(inverter_enable_1=True, invertorIP_1='192.0.2.2', serial_number_1='TEST000001',
               Model_1='Hybrid', evc_enable=True, evc_ip_address='192.0.2.3', serial_number_evc='EVC0000000001',
               Web_Dash=True, Smart_Target=True)
    settings = {}
    exec(c.mapped('/app/GivTCP_1/settings.py').read_text(), settings)
    assert settings['GiV_Settings'].invertorIP == '192.0.2.2'
    assert settings['GiV_Settings'].HA_Auto_D is True
    assert settings['GiV_Settings'].timezone == 'Europe/London'
    assert '127.0.0.1:6345' in c.mapped('/etc/nginx/givtcp_rest/rest.conf').read_text()
    dashboard = json.loads(c.mapped('/app/WebDashboard/app.json').read_text())
    assert dashboard['givTcpHosts'] == [{'name': 'GivTCP', 'port': '6345'}]
    commands = [p.args for p in c.processes]
    assert ['/usr/local/bin/python3', '/app/GivTCP_1/read.py', 'start'] in commands
    assert ['/usr/local/bin/python3', '/app/GivTCP/evc.py', 'chargeMode'] in commands
    assert ns['runninginv'] == [1]
    c.schedule.every.assert_called_once()


def test_startup_without_symlink_privileges_copies_config(container, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError(1314, 'A required privilege is not held by the client')
    monkeypatch.setattr(Path, 'symlink_to', denied)
    ns = container.run()
    published = container.mapped('/app/ingress/allsettings.json')
    assert not published.is_symlink()
    assert json.loads(published.read_text()) == ns['setts']


def test_scan_adds_new_slot_and_reuses_cached_capabilities(container):
    c = container
    c.scan.return_value = {8899: ['192.0.2.2'], 502: []}
    ns = c.run(auto_scan=True, invertorIP_1='192.0.2.9', serial_number_1='OTHER', Model_1='Hybrid')
    assert ns['setts']['number_of_inverters'] == 2
    assert ns['setts']['serial_number_2'] == 'TEST000001'
    assert ns['setts']['inverter_enable_2'] is True
    assert c.mapped('/config/GivTCP/TEST000001_caps.pkl').exists()
    # Startup clears previous-run files when it launches the read loop. Scan again
    # to inspect the config-page result independently of that cleanup.
    ns['findinv']({0: '192.0.2.0/24'})
    found = json.loads(c.mapped('/config/GivTCP/found_inverters.json').read_text())
    assert found[0]['Number_of_Batteries'] == 1
    c.client.detect.reset_mock()
    assert asyncio.run(ns['getInvDeets']('192.0.2.2'))['Serial_Number'] == 'TEST000001'
    c.client.detect.assert_not_awaited()


def test_scan_updates_existing_slot_ip_and_retries_empty_network(container):
    c = container
    ns = c.run(auto_scan=True)
    assert c.scan.call_count == 2
    assert ns['findinv']({}) == ({}, {}, [])
    c.scan.return_value = {8899: ['192.0.2.2'], 502: []}
    details, ips, evcs = ns['findinv']({0: '192.0.2.0/24'})
    assert ips == {1: '192.0.2.2'}
    assert details[1]['IP_Address'] == '192.0.2.2'
    assert evcs == []


def test_detect_failures_close_client_and_do_not_save_bad_cache(container):
    c = container
    ns = c.run()
    c.client.probe_alive.return_value = False
    assert asyncio.run(ns['getInvDeets']('192.0.2.2')) is None
    c.client.close.assert_awaited_once()
    c.client.probe_alive.return_value = True
    c.client.connect.side_effect = OSError('offline')
    assert asyncio.run(ns['getInvDeets']('192.0.2.2')) is None
    assert c.client.close.await_count == 2


def test_startup_helpers_and_shutdown_stop_managed_processes(container):
    c = container
    ns = c.run()
    assert [ns['invPort'](i) for i in (1, 5, 6)] == [6345, 6349, 6356]
    assert ns['exitReason'](-9) == 'killed by signal 9'
    assert ns['exitReason'](1) == 'exit code 1'
    settings = ns['ensureInverterSlots']({'number_of_inverters': 2, 'inverterName_1': 'Custom'})
    assert settings['inverterName_1'] == 'Custom'
    assert settings['inverterName_2'] == 'GivTCP2'
    ns['palm_job']()
    assert c.processes[-1].args[-1].endswith('/palm_soc.py')
    clients, services = ns['childProcesses']()
    assert clients == []
    assert len(services) == 2
    services[0].wait.side_effect = subprocess.TimeoutExpired('redis', 1)
    ns['stopProcesses'](services, 0)
    services[0].terminate.assert_called_once()
    services[0].kill.assert_called_once()
    ns['stopGunicorn'](ns['setting_rest'])
    c.os.killpg.assert_called_once()
    # logging.shutdown affects the whole test runner; replace it in this namespace only.
    ns['logging'] = SimpleNamespace(getLogger=logging.getLogger, shutdown=Mock())
    with pytest.raises(EndWatchdog):
        ns['shutdown'](signal.SIGTERM, None)
    c.os._exit.assert_called_once_with(0)


def test_evc_validation_rejects_short_reads_and_decodes_serial(container):
    ns = container.run()
    client = Mock()
    ns['ModbusTcpClient'] = Mock(return_value=client)
    client.read_holding_registers.return_value = SimpleNamespace(registers=[2026])
    assert ns['validateEVC']('192.0.2.3') is False
    client.read_holding_registers.side_effect = [SimpleNamespace(registers=[2026, 6, 15, 12, 0, 0]),
        SimpleNamespace(registers=[69, 86, 67, 0])]
    assert ns['validateEVC']('192.0.2.3') == 'EVC'


@pytest.mark.parametrize('stuck', [False, True])
def test_watchdog_restarts_failed_or_stale_readers_and_services(container, stuck):
    c = container
    calls = []
    def tick():
        if calls:
            raise EndWatchdog
        calls.append(1)
        timestamp = datetime.datetime.now(datetime.timezone.utc)
        if stuck:
            timestamp -= datetime.timedelta(hours=1)
        with c.mapped('/config/GivTCP/lastUpdate_1.pkl').open('wb') as f:
            pickle.dump(timestamp.isoformat(), f)
        for process in c.processes:
            if 'read.py' in str(process.args) and stuck:
                continue
            process.returncode = 1
    c.schedule.run_pending.side_effect = tick
    ns = c.run(inverter_enable_1=True, invertorIP_1='192.0.2.2', serial_number_1='TEST000001',
               Model_1='Hybrid', evc_enable=True, evc_ip_address='192.0.2.3')
    readers = [p for p in c.processes if p.args[-2:] == ['/app/GivTCP_1/read.py', 'start']]
    assert len(readers) == 2
    readers[0].kill.assert_called_once()
    rest = [p for p in c.processes if p.args[-1] == 'REST:giv_api']
    assert len(rest) == 2
    assert ns['mqttBroker'] is not None


def test_non_addon_settings_preserve_user_options_and_timezone(container):
    c = container
    # Return None for SUPERVISOR_TOKEN, as on a standalone Docker installation.
    c.os.getenv = lambda key: None
    sock = Mock()
    sock.getsockname.return_value = ('192.0.2.10', 1234)
    import socket
    c.imports['socket'] = SimpleNamespace(AF_INET=socket.AF_INET, SOCK_DGRAM=socket.SOCK_DGRAM,
                                         socket=Mock(return_value=sock))
    ns = c.run(inverter_enable_1=True, invertorIP_1='192.0.2.2', serial_number_1='TEST000001',
               Model_1='Hybrid', self_run=False, HA_Auto_D=False, Print_Raw_Registers=False,
               evc_enable=True, evc_ip_address='192.0.2.3')
    assert ns['isAddon'] is False
    settings = {}
    exec(c.mapped('/app/GivTCP_1/settings.py').read_text(), settings)
    assert settings['GiV_Settings'].HA_Auto_D is False
    assert settings['GiV_Settings'].Print_Raw_Registers is False
    assert settings['GiV_Settings'].timezone == 'Europe/London'
    assert ns['selfRun'] == {}


def test_settings_are_written_as_literals_never_as_code(container):
    # Each value would end its string or line and add code if written into settings.py as it was
    c = container
    code = '"\n    INJECTED=True\n    x="'
    c.run(inverter_enable_1=True, invertorIP_1='192.0.2.2', serial_number_1='TEST000001', Model_1='Hybrid',
          MQTT_Topic='topic' + code, MQTT_Password="it's" + code, inverterName_1='Name' + code,
          MQTT_Port='1883\n    INJECTED=True', day_rate='0.3\n    INJECTED=True', recovery_pause_1='inf',
          MQTT_Retain='True\n    INJECTED=True', evc_enable=True, evc_ip_address='192.0.2.3' + code, Web_Dash=True)
    for path in ('/app/GivTCP_1/settings.py', '/app/GivTCP/settings.py'):
        settings = {}
        exec(c.mapped(path).read_text(), settings)
        assert not hasattr(settings['GiV_Settings'], 'INJECTED')
    inverter = {}
    exec(c.mapped('/app/GivTCP_1/settings.py').read_text(), inverter)
    s = inverter['GiV_Settings']
    assert (s.MQTT_Topic, s.MQTT_Password, s.ha_device_prefix) == ('topic' + code, "it's" + code, 'Name' + code)
    assert (s.MQTT_Port, s.day_rate, s.recovery_pause, s.MQTT_Retain) == (1883, 0.395, 0.0, False)
    dashboard = json.loads(c.mapped('/app/WebDashboard/app.json').read_text())
    assert dashboard['givTcpHosts'] == [{'name': 'Name' + code, 'port': '6345'}]
    assert dashboard['solarRate'] == 0.395


def test_settings_api_only_listens_on_this_machine(container):
    c = container
    c.run(inverter_enable_1=True, invertorIP_1='192.0.2.2', serial_number_1='TEST000001', Model_1='Hybrid')
    binds = {p.args[-1]: p.args[p.args.index('-b') + 1] for p in c.processes if 'gunicorn' in p.args[0]}
    assert binds == {'settings_rest:giv_api': '127.0.0.1:6350', 'REST:giv_api': ':6345'}


INVERTER = dict(inverter_enable_1=True, invertorIP_1='192.0.2.2', serial_number_1='TEST000001', Model_1='Hybrid')

def access(c):
    return c.mapped('/etc/nginx/givtcp_access.conf').read_text().splitlines()

def test_addon_web_ui_is_ingress_only_unless_lan_access_is_on(container):
    c = container
    c.run(**INVERTER)
    assert access(c) == ['allow 127.0.0.1;', 'allow 172.30.32.2;', 'deny all;']
    c.run(**INVERTER, Web_LAN_Access=True)
    assert access(c) == ['allow 127.0.0.1;', 'allow 172.30.32.2;', 'allow 10.0.0.0/8;', 'allow 172.16.0.0/12;',
                         'allow 192.168.0.0/16;', 'deny all;']


def test_docker_web_ui_stays_on_the_local_network(container):
    c = container
    c.os.getenv = lambda key: None
    import socket
    sock = Mock()
    sock.getsockname.return_value = ('192.0.2.10', 1234)
    c.imports['socket'] = SimpleNamespace(AF_INET=socket.AF_INET, SOCK_DGRAM=socket.SOCK_DGRAM,
                                         socket=Mock(return_value=sock))
    c.run(**INVERTER)
    assert 'allow 192.168.0.0/16;' in access(c) and access(c)[-1] == 'deny all;'


def broker(c):
    return [p for p in c.processes if p.args[0] == '/usr/sbin/mosquitto']

def test_broker_without_credentials_stays_open_and_says_so(container, caplog):
    c = container
    with caplog.at_level(logging.WARNING):
        c.run(**INVERTER, MQTT_Username='', MQTT_Password='')
    assert c.mapped('/etc/mosquitto/givtcp.conf').read_text() == 'listener 1883 0.0.0.0\nallow_anonymous true\n'
    assert [p.args for p in broker(c)] == [['/usr/sbin/mosquitto', '-c', '/etc/mosquitto/givtcp.conf']]
    assert "accepts anyone on your network" in caplog.text


def test_broker_with_credentials_requires_them(container):
    c = container
    run = Mock()
    c.imports['subprocess'].run = run
    c.run(**INVERTER, MQTT_Username='givtcp', MQTT_Password='s3cret pass')
    assert c.mapped('/etc/mosquitto/givtcp.conf').read_text() == (
        'listener 1883 0.0.0.0\nallow_anonymous false\npassword_file /etc/mosquitto/givtcp_passwords\n')
    assert c.mapped('/etc/mosquitto/givtcp_passwords').read_text() == 'givtcp:s3cret pass\n'   # hashed by mosquitto_passwd
    assert run.call_args.args[0] == ['/usr/bin/mosquitto_passwd', '-U', '/etc/mosquitto/givtcp_passwords']
    assert len(broker(c)) == 1


@pytest.mark.parametrize("user, password, hashing", [('givtcp', 'pw', OSError('no mosquitto_passwd')),
                                                     ('giv:tcp', 'pw', None), ('givtcp', '', None),
                                                     ('givtcp', 'pw\nallow_anonymous true', None)])
def test_broker_login_that_cant_be_set_up_only_listens_locally(container, user, password, hashing):
    c = container
    c.imports['subprocess'].run = Mock(side_effect=hashing)
    c.run(**INVERTER, MQTT_Username=user, MQTT_Password=password)
    assert c.mapped('/etc/mosquitto/givtcp.conf').read_text() == 'listener 1883 127.0.0.1\nallow_anonymous true\n'


def test_rest_api_key_goes_to_settings_and_nginx(container):
    c = container
    c.run(**INVERTER, REST_API_Key='k' * 20)
    settings = {}
    exec(c.mapped('/app/GivTCP_1/settings.py').read_text(), settings)
    assert settings['GiV_Settings'].REST_API_Key == 'k' * 20
    assert 'proxy_set_header X-API-Key "' + 'k' * 20 + '";' in c.mapped('/etc/nginx/givtcp_rest/rest.conf').read_text()
    c.run(**INVERTER, REST_API_Key='bad"; key')
    exec(c.mapped('/app/GivTCP_1/settings.py').read_text(), settings)
    assert settings['GiV_Settings'].REST_API_Key == ''
    assert 'X-API-Key' not in c.mapped('/etc/nginx/givtcp_rest/rest.conf').read_text()
