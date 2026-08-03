import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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
        for text in ("/api/mods/upload", "/api/operations", "/api/mod-backups",
                     "Upload for inspection", "client_instructions", "maintenance_confirmation"):
            self.assertIn(text, combined)


if __name__ == "__main__":
    unittest.main()
