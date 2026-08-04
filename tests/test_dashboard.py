import http.client
import inspect
import json
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from unittest import mock
from unittest.mock import patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard


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
        for text in ("/api/mods/upload", "/api/operations", "/api/mod-backups", "Upload for inspection", "client_instructions", "maintenance_confirmation"):
            self.assertIn(text, combined)


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
        headers = {"Cookie": cookie} if cookie else {}
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
        self.assertTrue(self.login())

    def test_authenticated_mod_list_detail_instructions_and_operations_routes(self):
        cookie = self.login()
        backend = mock.Mock()
        backend.list_mods.return_value = [{'id': 'sample', 'name': 'Sample', 'client_instructions': ['Install locally']}]
        backend.list_operations.return_value = [{'id': 'op-1'}]
        backend.list_mod_backups.return_value = [{'name': 'backup-1'}]
        with mock.patch.object(dashboard, 'mod_manager', backend):
            for path in ('/api/mods', '/api/mods/sample', '/api/mods/sample/instructions', '/api/operations', '/api/mod-backups'):
                status, _, body = self.request('GET', path, cookie=cookie)
                self.assertEqual(status, 200, path)
                payload = json.loads(body)
                self.assertNotIn('error', payload, path)
        backend.list_mods.assert_called()

    def test_mod_mutations_enable_disable_remove_require_confirmation_and_call_backend(self):
        cookie = self.login()
        backend = mock.Mock()
        backend.set_mod_state.return_value = {'id': 'sample', 'applied': True}
        with mock.patch.object(dashboard, 'mod_manager', backend), mock.patch.object(dashboard, 'PALWORLD_DIR', '/tmp/test-dashboard-state'):
            for action in ('enable', 'disable', 'remove'):
                status, _, body = self.request('POST', f'/api/mods/sample/{action}', {}, cookie)
                self.assertEqual(status, 409)
                token = json.loads(body)['confirmation_token']
                status, _, body = self.request('POST', f'/api/mods/sample/{action}', {'maintenance_confirmation': token}, cookie)
                self.assertEqual(status, 200)
        self.assertEqual([call.args[2] for call in backend.set_mod_state.call_args_list], ['enable', 'disable', 'remove'])

    def test_read_only_inspect_preview_and_apply_flow_calls_real_backend(self):
        cookie = self.login()
        backend = mock.Mock()
        backend.inspect_packages.return_value = {'pak': ['Mods/a.pak']}
        backend.preview_plan.return_value = {'files': [{'path': 'Mods/a.pak'}], 'mod_id': 'sample'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            palworld = root / 'palworld'; palworld.mkdir()
            staging = palworld / '.palworld-mods' / 'staging'; staging.mkdir(parents=True)
            with mock.patch.object(dashboard, 'mod_manager', backend), mock.patch.object(dashboard, 'PALWORLD_DIR', str(palworld)):
                status, _, body = self.request('POST', '/api/mods/inspect', {'staging_dir': str(staging)}, cookie)
                self.assertEqual(status, 200); self.assertTrue(json.loads(body)['success'])
                status, _, body = self.request('POST', '/api/mods/preview', {'staging_dir': str(staging), 'target_root': str(palworld), 'mod_id': 'sample'}, cookie)
                self.assertEqual(status, 200); self.assertEqual(json.loads(body)['result']['mod_id'], 'sample')
                status, _, body = self.request('POST', '/api/mods/apply', {'staging_dir': str(staging), 'plan': {'files': []}}, cookie)
                self.assertEqual(status, 409)
                token = json.loads(body)['confirmation_token']
                status, _, body = self.request('POST', '/api/mods/apply', {'staging_dir': str(staging), 'plan': {'files': []}, 'maintenance_confirmation': token}, cookie)
                self.assertEqual(status, 200); self.assertTrue(json.loads(body)['success'])
        backend.inspect_packages.assert_called_once()
        backend.preview_plan.assert_called_once()
        backend.apply_plan.assert_called_once()

    def test_backup_and_rollback_require_confirmation_and_call_backend(self):
        cookie = self.login()
        backend = mock.Mock()
        backend.create_backup.return_value = '/safe/backup'
        backend.rollback_backup.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); palworld = root / 'palworld'; palworld.mkdir()
            with mock.patch.object(dashboard, 'mod_manager', backend), mock.patch.object(dashboard, 'PALWORLD_DIR', str(palworld)):
                for path, payload in (('/api/mods/backup', {}), ('/api/mods/rollback', {'backup_path': str(palworld / '.palworld-mods' / 'backups' / 'b')})):
                    status, _, body = self.request('POST', path, payload, cookie)
                    self.assertEqual(status, 409)
                    token = json.loads(body)['confirmation_token']; payload['maintenance_confirmation'] = token
                    status, _, body = self.request('POST', path, payload, cookie)
                    self.assertEqual(status, 200); self.assertTrue(json.loads(body)['success'])
        backend.create_backup.assert_called_once()
        backend.rollback_backup.assert_called_once()

    def test_mod_routes_reject_paths_outside_configured_roots(self):
        cookie = self.login()
        with tempfile.TemporaryDirectory() as directory:
            palworld = Path(directory) / 'palworld'; palworld.mkdir()
            with mock.patch.object(dashboard, 'PALWORLD_DIR', str(palworld)), mock.patch.object(dashboard, 'mod_manager', mock.Mock()):
                for path, payload in (('/api/mods/inspect', {'staging_dir': '/tmp/outside'}), ('/api/mods/preview', {'staging_dir': '/tmp/outside', 'target_root': str(palworld), 'mod_id': 'sample'}), ('/api/mods/apply', {'staging_dir': '/tmp/outside', 'plan': {}}), ('/api/mods/rollback', {'backup_path': '/tmp/outside'})):
                    status, _, body = self.request('POST', path, payload, cookie)
                    self.assertEqual(status, 400, path)
                    self.assertIn('must be under', json.loads(body)['message'])

    def test_confirmed_multipart_upload_calls_stage_backend(self):
        cookie = self.login()
        boundary = 'test-boundary'
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="demo.zip"\r\n'
                   'Content-Type: application/zip\r\n\r\nzip-bytes\r\n'
                   f'--{boundary}--\r\n').encode()
        with mock.patch.object(dashboard, 'PALWORLD_DIR', '/tmp/test-dashboard-upload'), \
             mock.patch.object(dashboard, 'stage_upload', return_value={'staging_dir': Path('/tmp/staged'), 'archive': Path('/tmp/staged.zip')}) as stage:
            dashboard.maintenance_confirmations['upload-token'] = dashboard.time.time()
            status, _, body = self.request_multipart('/api/mods/upload', payload, boundary, cookie, 'upload-token')
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['success'])
        stage.assert_called_once()
    def request_multipart(self, path, body, boundary, cookie, confirmation):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=3)
        headers = {'Cookie': cookie, 'Content-Type': f'multipart/form-data; boundary={boundary}',
                   'X-Maintenance-Confirmation': confirmation, 'Content-Length': str(len(body))}
        connection.request('POST', path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_headers, payload


if __name__ == "__main__":
    unittest.main()
