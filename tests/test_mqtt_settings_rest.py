import importlib
import unittest
from typing import Any, Callable


OnConnectCallback = Callable[[Any, Any, Any, int, Any], None]


class FakeSuccessfulClient:
    def __init__(self, *_args, **_kwargs):
        self.on_connect: OnConnectCallback | None = None
        self.on_disconnect: OnConnectCallback | None = None

    def username_pw_set(self, username, password):
        self.username = (username, password)

    def connect(self, host, port=1883, keepalive=10):
        self.host = host
        self.port = port
        self.keepalive = keepalive
        return 0

    def _call_on_connect(self, reason_code: int):
        callback = self.on_connect
        if callback is None:
            raise AssertionError("on_connect callback was not set")
        callback(self, None, None, reason_code, None)

    def loop_start(self):
        self._call_on_connect(0)

    def loop_stop(self):
        return None

    def disconnect(self):
        return None


class FakeAuthFailureClient(FakeSuccessfulClient):
    def loop_start(self):
        self._call_on_connect(4)


class FakeAuthFailureClientV5(FakeSuccessfulClient):
    def loop_start(self):
        self._call_on_connect(134)


class FakeUnauthorisedClientV5(FakeSuccessfulClient):
    def loop_start(self):
        self._call_on_connect(135)


class FakeConnectionRefusedClient(FakeSuccessfulClient):
    def connect(self, host, port=1883, keepalive=10):
        raise OSError(111, "Connection refused")


class SettingsRestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module("GivTCP.settings_rest")
        cls.app = cls.module.giv_api

    def setUp(self):
        self.original_client = self.module.mqtt.Client

    def tearDown(self):
        self.module.mqtt.Client = self.original_client

    def post_json(self, payload):
        with self.app.test_request_context(
            "/settings/mqtt/test",
            method="POST",
            json=payload,
        ):
            return self.module.testmqtt()

    def test_mqtt_test_rejects_missing_host(self):
        response = self.post_json({"MQTT_Port": 1883})
        self.assertEqual(
            response,
            {"ok": False, "message": "MQTT host is required"},
        )

    def test_mqtt_test_rejects_invalid_port(self):
        response = self.post_json({"MQTT_Address": "broker.local", "MQTT_Port": 70000})
        self.assertEqual(
            response,
            {"ok": False, "message": "MQTT port must be a number between 1 and 65535"},
        )

    def test_mqtt_test_reports_successful_connection(self):
        self.module.mqtt.Client = FakeSuccessfulClient
        response = self.post_json(
            {
                "MQTT_Address": "broker.local",
                "MQTT_Port": 1883,
                "MQTT_Username": "user",
                "MQTT_Password": "secret",
            }
        )
        self.assertEqual(
            response,
            {"ok": True, "message": "Connected to MQTT broker"},
        )

    def test_mqtt_test_reports_auth_failure(self):
        self.module.mqtt.Client = FakeAuthFailureClient
        response = self.post_json({"MQTT_Address": "broker.local", "MQTT_Port": 1883})
        self.assertEqual(
            response,
            {"ok": False, "message": "MQTT username/password was rejected"},
        )

    def test_mqtt_test_reports_auth_failure_for_mqtt5_reason_code(self):
        self.module.mqtt.Client = FakeAuthFailureClientV5
        response = self.post_json({"MQTT_Address": "broker.local", "MQTT_Port": 1883})
        self.assertEqual(
            response,
            {"ok": False, "message": "MQTT username/password was rejected"},
        )

    def test_mqtt_test_reports_unauthorised_failure_for_mqtt5_reason_code(self):
        self.module.mqtt.Client = FakeUnauthorisedClientV5
        response = self.post_json({"MQTT_Address": "broker.local", "MQTT_Port": 1883})
        self.assertEqual(
            response,
            {"ok": False, "message": "MQTT username/password was rejected"},
        )

    def test_mqtt_test_reports_user_facing_message_for_connection_refused(self):
        self.module.mqtt.Client = FakeConnectionRefusedClient
        response = self.post_json({"MQTT_Address": "broker.local", "MQTT_Port": 1883})
        self.assertEqual(
            response,
            {"ok": False, "message": "Could not connect to the MQTT broker at the requested host/port"},
        )


if __name__ == "__main__":
    unittest.main()
