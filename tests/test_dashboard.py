<<<<<<< HEAD
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
=======
import http.client
import json
import threading
import unittest
from http.server import HTTPServer
from unittest import mock
from urllib.parse import urlencode

import sys
from pathlib import Path
>>>>>>> c850cfe

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard


<<<<<<< HEAD
class DashboardApiContractTests(unittest.TestCase):
    def setUp(self):
        dashboard.maintenance_confirmations.clear()

    def test_optional_backend_helpers_are_graceful(self):
        with patch.object(dashboard, "mod_manager", None):
            self.assertEqual(dashboard.get_mod_operations(), [])
            self.assertEqual(dashboard.get_mod_backups(), [])
            self.assertIsNone(dashboard.get_client_instructions("missing"))

    def test_backend_contract_adapters_json_safe_values(self):
        class Backend:
            def list_operations(self):
                return [{"id": 1, "details": {"ok": True}}]

            def list_mod_backups(self):
                return [{"name": "backup", "size": 2}]

            def list_mods(self):
                return [{"id": "demo", "client_instructions": ["Install locally"]}]

        with patch.object(dashboard, "mod_manager", Backend()):
            self.assertEqual(dashboard.get_mod_operations()[0]["id"], 1)
            self.assertEqual(dashboard.get_mod_backups()[0]["name"], "backup")
            self.assertEqual(dashboard.get_client_instructions("demo"), ["Install locally"])

    def test_maintenance_confirmation_is_single_use_and_header_supported(self):
        token = "one-use"
        dashboard.maintenance_confirmations[token] = dashboard.time.time()
        handler = object.__new__(dashboard.DashboardHandler)
        handler.headers = {}
        self.assertTrue(handler.maintenance_confirmed({"maintenance_confirmation": token}))
        self.assertFalse(handler.maintenance_confirmed({"maintenance_confirmation": token}))

        dashboard.maintenance_confirmations[token] = dashboard.time.time()
        handler.headers = {"X-Maintenance-Confirmation": token}
        self.assertTrue(handler.maintenance_confirmed({}))

    def test_dashboard_exposes_mod_workstream_ui_and_routes(self):
        combined = dashboard.DASHBOARD_HTML + inspect.getsource(dashboard.DashboardHandler)
        for text in ("/api/mods/upload", "/api/operations", "/api/mod-backups",
                     "Upload for inspection", "client_instructions", "maintenance_confirmation"):
            self.assertIn(text, combined)
=======
class DashboardHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), dashboard.DashboardHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host, cls.port = cls.server.server_address

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        dashboard.sessions.clear()
        dashboard.maintenance_confirmations.clear()

    def request(self, method, path, body=None, cookie=None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=3)
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        if body is not None:
            if isinstance(body, dict):
                body = json.dumps(body)
                headers["Content-Type"] = "application/json"
            else:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Content-Length"] = str(len(body.encode()))
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_headers, payload

    def login(self):
        status, headers, _ = self.request("POST", "/login", urlencode({"password": dashboard.DEFAULT_PASSWORD}))
        self.assertEqual(status, 302)
        self.assertIn("session_id=", headers["Set-Cookie"])
        return headers["Set-Cookie"].split(";", 1)[0]

    def test_protected_api_redirects_without_session(self):
        status, headers, _ = self.request("GET", "/api/mods")
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], "/login")

    def test_login_rejects_bad_password_and_accepts_good_password(self):
        status, _, body = self.request("POST", "/login", urlencode({"password": "wrong"}))
        self.assertEqual(status, 200)
        self.assertIn(b"Invalid password", body)
        self.assertNotIn("session_id", dashboard.sessions)
        self.assertTrue(self.login().startswith("session_id="))

    def test_authenticated_mod_list_and_detail_are_json_safe(self):
        cookie = self.login()
        fake_mod = {"id": "sample", "name": "Sample", "metadata": {"version": 1}}
        with mock.patch.object(dashboard, "mod_manager", object()), mock.patch.object(
            dashboard, "_mod_manager_call", return_value=[fake_mod]
        ):
            status, _, body = self.request("GET", "/api/mods", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["mods"][0]["id"], "sample")

    def test_control_mutation_requires_single_use_confirmation(self):
        cookie = self.login()
        with mock.patch.object(dashboard, "is_server_running", return_value=False):
            status, _, body = self.request("POST", "/api/control", {"action": "stop"}, cookie)
        self.assertEqual(status, 409)
        challenge = json.loads(body)
        token = challenge["confirmation_token"]
        self.assertTrue(challenge["requires_confirmation"])

        # A stale or missing confirmation cannot authorize the action.
        with mock.patch.object(dashboard, "is_server_running", return_value=False):
            status, _, _ = self.request("POST", "/api/control", {"action": "stop"}, cookie)
        self.assertEqual(status, 409)

        # The valid token is consumed and allows the handler to reach the action.
        with mock.patch.object(dashboard, "is_server_running", return_value=False):
            status, _, body = self.request(
                "POST", "/api/control", {"action": "stop", "maintenance_confirmation": token}, cookie
            )
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["success"])
        self.assertNotIn(token, dashboard.maintenance_confirmations)

    def test_mod_mutation_requires_confirmation_then_calls_backend(self):
        cookie = self.login()
        backend = mock.Mock()
        backend.apply_action.return_value = {"id": "sample", "action": "enable", "applied": True}
        with mock.patch.object(dashboard, "mod_manager", backend):
            status, _, body = self.request("POST", "/api/mods/sample/enable", {}, cookie)
        self.assertEqual(status, 409)
        token = json.loads(body)["confirmation_token"]

        with mock.patch.object(dashboard, "mod_manager", backend), mock.patch.object(
            dashboard, "PALWORLD_DIR", "/tmp/test-dashboard-no-production"
        ):
            status, _, body = self.request(
                "POST", "/api/mods/sample/enable", {"maintenance_confirmation": token}, cookie
            )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["success"])
        backend.apply_action.assert_called_once_with(
            "sample", "enable", "/tmp/test-dashboard-no-production/.palworld-mods/manifest.json"
        )

    def test_expired_confirmation_is_rejected(self):
        cookie = self.login()
        dashboard.maintenance_confirmations["expired"] = 0
        with mock.patch.object(dashboard, "MAINTENANCE_CONFIRMATION_TIMEOUT", 1), mock.patch.object(
            dashboard, "is_server_running", return_value=False
        ):
            status, _, body = self.request(
                "POST", "/api/control", {"action": "restart", "maintenance_confirmation": "expired"}, cookie
            )
        self.assertEqual(status, 409)
        self.assertNotEqual(json.loads(body).get("success"), True)

    @unittest.skip("Pending backend contract: upload/inspection/preview endpoints are not implemented yet")
    def test_mod_upload_inspection_and_preview_contract(self):
        pass
>>>>>>> c850cfe


if __name__ == "__main__":
    unittest.main()
