import importlib
import unittest


class FakeSuccessfulClient:
    def __init__(self, *_args, **_kwargs):
        self.on_connect = None
        self.on_disconnect = None

    def username_pw_set(self, username, password):
        self.username = (username, password)

    def connect(self, host, port=1883, keepalive=10):
        self.host = host
        self.port = port
        self.keepalive = keepalive
        return 0

    def loop_start(self):
        self.on_connect(self, None, None, 0, None)

    def loop_stop(self):
        return None

    def disconnect(self):
        return None


class FakeAuthFailureClient(FakeSuccessfulClient):
    def loop_start(self):
        self.on_connect(self, None, None, 4, None)


class FakeAuthFailureClientV5(FakeSuccessfulClient):
    def loop_start(self):
        self.on_connect(self, None, None, 134, None)


class FakeUnauthorisedClientV5(FakeSuccessfulClient):
    def loop_start(self):
        self.on_connect(self, None, None, 135, None)


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
            {"ok": True, "message": "Connected to broker"},
        )

    def test_mqtt_test_reports_auth_failure(self):
        self.module.mqtt.Client = FakeAuthFailureClient
        response = self.post_json({"MQTT_Address": "broker.local", "MQTT_Port": 1883})
        self.assertEqual(
            response,
            {"ok": False, "message": "Broker rejected the username or password"},
        )

    def test_mqtt_test_reports_auth_failure_for_mqtt5_reason_code(self):
        self.module.mqtt.Client = FakeAuthFailureClientV5
        response = self.post_json({"MQTT_Address": "broker.local", "MQTT_Port": 1883})
        self.assertEqual(
            response,
            {"ok": False, "message": "Broker rejected the username or password"},
        )

    def test_mqtt_test_reports_unauthorised_failure_for_mqtt5_reason_code(self):
        self.module.mqtt.Client = FakeUnauthorisedClientV5
        response = self.post_json({"MQTT_Address": "broker.local", "MQTT_Port": 1883})
        self.assertEqual(
            response,
            {"ok": False, "message": "Broker rejected the connection as unauthorised"},
        )


if __name__ == "__main__":
    unittest.main()
