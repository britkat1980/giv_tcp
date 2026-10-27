"""Influx serialization and failure cleanup using a fake client."""
from unittest.mock import Mock

import pytest
import influx


@pytest.mark.parametrize("fail", [False, True])
def test_publish_serializes_sections_and_closes_client(monkeypatch, fail):
    client = Mock()
    api = client.write_api.return_value
    if fail:
        api.write.side_effect = OSError("offline")
    constructor = Mock(return_value=client)
    monkeypatch.setattr(influx, "InfluxDBClient", constructor)
    monkeypatch.setattr(influx.GiV_Settings, "Log_Level", "Debug")
    data = {"Power": {"Power": {"PV Power": 120, "Missing": None},
                      "Flows": {"Grid To Load": 0}},
            "Energy": {"Today": {"Import": 1.5}, "Total": {"State": "ready"}}}
    influx.GivInflux.publish("TEST000001", data)
    api.write.assert_called_once_with(bucket=influx.GiV_Settings.influxBucket,
        record='TEST000001,tagKey=GivReal pv_power=120,grid_to_load=0,import=1.5,state="ready"')
    assert constructor.call_args.kwargs["timeout"] == 5000
    assert constructor.call_args.kwargs["retries"] is False
    assert constructor.call_args.kwargs["debug"] is True
    client.close.assert_called_once()
    if not fail:
        api.close.assert_called_once()
