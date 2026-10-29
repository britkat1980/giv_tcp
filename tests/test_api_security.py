"""Settings from the API can't become code in settings.py, the settings APIs refuse payloads that aren't settings,
and requests that another website makes through a visitor's browser are refused (except read-only data)"""
import json

import pytest
import REST
import settings_rest
import settings_values
from GivLUT import GivLUT

INJECTION = 'x"\nimport os; os.environ["GIVTCP_INJECTED"]="yes"\n#'


def literal(source):
    """The value of a written setting, read the way settings.py is"""
    namespace = {}
    exec("value=" + source, namespace)
    return namespace["value"]


@pytest.mark.parametrize("value", [INJECTION, "it's", 'a\\"b', "£ rate", "", 123])
def test_text_is_always_a_string_literal(value):
    assert literal(settings_values.text(value)) == str(value)


@pytest.mark.parametrize("value, expected", [(True, True), ("true", True), (" TRUE ", True), (False, False),
                                             ("false", False), ("yes", False), (None, False), (INJECTION, False)])
def test_flag_is_always_true_or_false(value, expected):
    assert literal(settings_values.flag(value)) is expected


@pytest.mark.parametrize("value, default, cast, expected", [
    (1883, 1883, None, 1883), ("1884", 1883, None, 1884), (0.395, 0.3, None, 0.395), (" 0.2 ", 0.3, None, 0.2),
    ("", 30, None, 30), (None, 0, float, 0.0), (5, 0, float, 5.0), ("nan", 2, None, 2), (float("inf"), 2, None, 2),
    (True, 2, None, 2), ("1883\nimport os", 1883, None, 1883), (INJECTION, 60, None, 60)])
def test_number_falls_back_to_the_default_unless_finite(value, default, cast, expected):
    result = literal(settings_values.number(value, default, cast))
    assert result == expected and type(result) is type(expected)


TEMPLATE = {"MQTT_Port": 1883, "day_rate": 0.395, "HA_Auto_D": True, "MQTT_Topic": "", "invertorIP_1": "",
            "inverter_enable_1": False}

@pytest.mark.parametrize("payload, error", [
    ([1, 2], "JSON object"), ("text", "JSON object"), (None, "JSON object"),
    ({"bad key": 1}, "Invalid setting name"), ({"x" * 65: 1}, "Invalid setting name"),
    ({"MQTT_Topic": {"a": 1}}, "single value"), ({"MQTT_Topic": [1]}, "single value"),
    ({"MQTT_Topic": "x" * 1001}, "too long"),
    ({"MQTT_Port": "1883; import os"}, "must be a number"), ({"day_rate": True}, "must be a number"),
    ({"HA_Auto_D": "maybe"}, "true or false"), ({"inverter_enable_7": 1}, "true or false")])
def test_check_refuses_what_isnt_a_setting(payload, error):
    assert error in settings_values.check(payload, TEMPLATE)


def test_check_accepts_the_config_pages_values():
    assert settings_values.check({"MQTT_Port": "1883", "day_rate": "", "HA_Auto_D": "true", "MQTT_Topic": "x\"y",
                                  "invertorIP_9": "192.0.2.9", "inverter_enable_9": False, "v3upgrade": None,
                                  "anything_new": 4.5}, TEMPLATE) is None
    assert settings_values.check({"MQTT_Port": "abc"}, {}) is None      # no template: only the structure is checked


def test_template_is_read_from_the_image_or_empty(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps(TEMPLATE))
    assert settings_values.load_template(str(tmp_path / "settings.json")) == TEMPLATE
    (tmp_path / "broken.json").write_text("{")
    assert settings_values.load_template(str(tmp_path / "broken.json")) == {}
    assert settings_values.load_template(str(tmp_path / "missing.json")) == {}


@pytest.fixture
def settings_api(monkeypatch, tmp_path):
    import builtins
    real_open = builtins.open
    monkeypatch.setattr(settings_rest, "open", lambda path, *a, **kw:
        real_open(tmp_path / path.rsplit('/', 1)[-1], *a, **kw), raising=False)
    monkeypatch.setattr(settings_rest, "exists", lambda path: (tmp_path / path.rsplit('/', 1)[-1]).exists())
    monkeypatch.setattr(settings_values, "load_template", lambda: TEMPLATE)
    (tmp_path / "allsettings.json").write_text(json.dumps({"MQTT_Port": 1883}))
    return settings_rest.giv_api.test_client(), tmp_path


def test_settings_api_refuses_bad_payloads_and_keeps_the_saved_settings(settings_api):
    api, path = settings_api
    response = api.post('/settings', json={"MQTT_Port": "1883\nimport os"})
    assert response.status_code == 400 and "must be a number" in response.json["result"]
    assert api.post('/settings', data="not json", content_type="application/json").status_code == 400
    assert json.loads((path / "allsettings.json").read_text()) == {"MQTT_Port": 1883}
    assert api.post('/settings', json={"MQTT_Port": 1884}).status_code == 200
    assert api.get('/settings').json == {"MQTT_Port": 1884}


@pytest.mark.parametrize("method, route", [("get", "/settings"), ("post", "/settings"), ("get", "/settings/found"),
                                           ("post", "/reboot")])
def test_settings_api_refuses_cross_site_requests_and_has_no_cors(settings_api, method, route):
    api, path = settings_api
    cross = getattr(api, method)(route, json={"MQTT_Port": 1}, headers={"Sec-Fetch-Site": "cross-site",
                                                                        "Origin": "https://example.com"})
    assert cross.status_code == 403
    assert json.loads((path / "allsettings.json").read_text()) == {"MQTT_Port": 1883}
    page = api.get('/settings', headers={"Sec-Fetch-Site": "same-origin", "Origin": "https://example.com"})
    assert page.status_code == 200 and "Access-Control-Allow-Origin" not in page.headers


@pytest.fixture
def rest_settings(monkeypatch, tmp_path):
    saved = tmp_path / "allsettings.json"
    saved.write_text(json.dumps({"MQTT_Port": 1883, "Model_1": "Hybrid"}))
    monkeypatch.setattr(GivLUT, "allsettings", str(saved))
    monkeypatch.setattr(settings_values, "load_template", lambda: TEMPLATE)
    return saved


def test_rest_settings_merge_and_refuse_bad_payloads(api, rest_settings):
    assert api.post('/settings', json={"MQTT_Topic": [INJECTION]}).status_code == 400
    assert api.post('/settings', json={"MQTT_Port": 1884}).status_code == 200
    assert json.loads(rest_settings.read_text()) == {"MQTT_Port": 1884, "Model_1": "Hybrid"}


@pytest.mark.parametrize("method, route", [("post", "/settings"), ("get", "/settings"), ("get", "/restart"),
                                           ("post", "/restart"), ("get", "/reboot"), ("post", "/forceCharge"),
                                           ("post", "/setChargeTarget"), ("post", "/captureDevice")])
def test_rest_refuses_cross_site_control_and_settings(api, rest_settings, monkeypatch, method, route):
    called = []
    monkeypatch.setattr(REST, "requestcommand", lambda *a: called.append(a))
    monkeypatch.setattr(REST.wr, "rebootAddon", lambda *a, **kw: called.append(a))
    response = getattr(api, method)(route, data='{"chargeToPercent":"10","duration":"30"}',
                                    content_type="text/plain", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403 and called == []
    assert json.loads(rest_settings.read_text())["MQTT_Port"] == 1883


def test_rest_preflight_for_control_commands_gets_no_cors(api):
    response = api.options('/forceCharge', headers={"Origin": "https://example.com",
                                                    "Access-Control-Request-Method": "POST"})
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.parametrize("site", ["cross-site", "same-site", None])
def test_rest_read_only_data_is_still_shared(api, monkeypatch, site):
    monkeypatch.setattr(REST.rd, "getCache", lambda: {"Power": 1})
    headers = {"Origin": "http://192.0.2.1:3000", **({"Sec-Fetch-Site": site} if site else {})}
    response = api.get('/getCache', headers=headers)
    assert response.status_code == 200 and response.json == {"Power": 1}
    assert response.headers["Access-Control-Allow-Origin"] in ("*", "http://192.0.2.1:3000")


def test_rest_same_origin_and_direct_calls_still_work(api, rest_settings):
    for headers in ({"Sec-Fetch-Site": "same-origin"}, {"Sec-Fetch-Site": "none"}, {}):
        assert api.post('/settings', json={"MQTT_Port": 1890}, headers=headers).status_code == 200


SECRETS = {"MQTT_Password": "mqttpw", "influxToken": "tok", "GE_API": "ge", "SOLCASTAPI": "sol",
           "REST_API_Key": "k" * 20}

def test_secrets_are_hidden_and_kept_when_sent_back():
    shown = settings_values.hide_secrets({**SECRETS, "MQTT_Username": "user", "influxToken": ""})
    assert shown == {"MQTT_Password": "********", "influxToken": "", "GE_API": "********", "SOLCASTAPI": "********",
                     "REST_API_Key": "********", "MQTT_Username": "user"}
    saved = {"MQTT_Password": "mqttpw", "GE_API": "ge"}
    assert settings_values.keep_secrets({"MQTT_Password": "********", "GE_API": "new", "SOLCASTAPI": "********",
                                         "MQTT_Port": 1883}, saved) == {"MQTT_Password": "mqttpw", "GE_API": "new",
                                                                         "MQTT_Port": 1883}


@pytest.mark.parametrize("key, ok", [("", True), (None, True), ("********", True), ("a" * 16, True),
                                     ("Abc-123_" * 16, True), ("short", False), ("a" * 129, False),
                                     ('aaaaaaaaaaaaaaaa"; deny all', False), ("a" * 15 + "\n", False)])
def test_api_key_is_checked_before_its_saved(key, ok):
    assert (settings_values.check({"REST_API_Key": key}, {}) is None) is ok
    assert settings_values.api_key({"REST_API_Key": key}) == (key if ok and key and key != "********" else "")


def test_settings_api_hides_secrets_and_keeps_them_on_save(settings_api):
    api, path = settings_api
    (path / "allsettings.json").write_text(json.dumps(SECRETS))
    shown = api.get('/settings').json
    assert "mqttpw" not in json.dumps(shown) and shown["MQTT_Password"] == "********"
    assert api.post('/settings', json={**shown, "GE_API": "newge"}).status_code == 200
    assert json.loads((path / "allsettings.json").read_text()) == {**SECRETS, "GE_API": "newge"}


def test_rest_settings_hide_secrets_and_keep_them_on_save(api, rest_settings):
    rest_settings.write_text(json.dumps(SECRETS))
    shown = api.get('/settings').json
    assert set(shown.values()) == {"********"}
    assert api.post('/settings', json=shown).status_code == 200
    assert json.loads(rest_settings.read_text()) == SECRETS


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setattr(REST.GiV_Settings, "REST_API_Key", "s" * 20, raising=False)
    called = []
    monkeypatch.setattr(REST, "requestcommand", lambda *a: called.append(a))
    monkeypatch.setattr(REST, "response", lambda id: '{"result":"ok"}')
    monkeypatch.setattr(REST.rd, "getCache", lambda: {"Power": 1})
    return called


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}, {"Authorization": "Bearer wrong"},
                                     {"Authorization": "Basic " + "s" * 20}])
def test_rest_api_key_is_needed_for_control_when_set(api, keyed, headers):
    response = api.post('/setChargeTarget', json={"chargeToPercent": "80"}, headers=headers)
    assert response.status_code == 401 and keyed == []
    assert api.get('/settings', headers=headers).status_code == 401


@pytest.mark.parametrize("headers", [{"X-API-Key": "s" * 20}, {"Authorization": "Bearer " + "s" * 20},
                                     {"Authorization": "bearer  " + "s" * 20}])
def test_rest_api_key_lets_control_through(api, keyed, headers):
    assert api.post('/setChargeTarget', json={"chargeToPercent": "80"}, headers=headers).status_code == 200
    assert keyed == [("setChargeTarget", {"chargeToPercent": "80"})]


def test_rest_read_only_data_and_preflight_dont_need_the_key(api, keyed):
    assert api.get('/getCache').json == {"Power": 1}
    assert api.options('/forceCharge').status_code != 401


def test_rest_without_a_valid_key_stays_open(api, monkeypatch):
    called = []
    monkeypatch.setattr(REST, "requestcommand", lambda *a: called.append(a))
    monkeypatch.setattr(REST, "response", lambda id: '{"result":"ok"}')
    for key in ("", "short"):
        monkeypatch.setattr(REST.GiV_Settings, "REST_API_Key", key, raising=False)
        assert api.post('/setChargeTarget', json={"chargeToPercent": "80"}).status_code == 200
    assert len(called) == 2
