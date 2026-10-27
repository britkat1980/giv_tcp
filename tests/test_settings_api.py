"""Settings HTTP endpoints, with every absolute config path redirected to tmp_path."""
import builtins
import json
from unittest.mock import Mock

import pytest
import settings_rest


@pytest.fixture
def config_api(monkeypatch, tmp_path):
    real_open = builtins.open
    monkeypatch.setattr(settings_rest, "open", lambda path, *a, **kw:
        real_open(tmp_path / path.rsplit('/', 1)[-1], *a, **kw), raising=False)
    monkeypatch.setattr(settings_rest, "exists", lambda path:
        (tmp_path / path.rsplit('/', 1)[-1]).exists())
    return settings_rest.giv_api.test_client(), tmp_path


def test_save_merges_existing_settings_and_preserves_unknown_keys(config_api):
    api, path = config_api
    (path / "allsettings.json").write_text(json.dumps({"Model_1": "Hybrid", "day_rate": 0.3}))
    assert api.post('/settings', json={"day_rate": 0.4}).data == b"Settings Updated"
    assert api.get('/settings').json == {"Model_1": "Hybrid", "day_rate": 0.4}


def test_save_creates_settings_and_found_devices_default_to_empty(config_api):
    api, path = config_api
    assert api.post('/settings', json={"auto_scan": True}).status_code == 200
    assert api.get('/settings').json == {"auto_scan": True}
    assert api.get('/settings/found').json == []
    found = [{"Serial_Number": "TEST", "IP_Address": "192.0.2.1"}]
    (path / "found_inverters.json").write_text(json.dumps(found))
    assert api.get('/settings/found').json == found


def test_reboot_reports_supervisor_failure(monkeypatch):
    post = Mock(side_effect=OSError("offline"))
    monkeypatch.setattr(settings_rest.requests, "post", post)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
    assert settings_rest.giv_api.test_client().post('/reboot').data == b"Error: Reboot Manually"
    assert post.call_args.kwargs['headers']['Authorization'] == 'Bearer test-token'
