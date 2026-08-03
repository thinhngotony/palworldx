import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigurationTests(unittest.TestCase):
    def test_catalog_is_versioned_and_entries_are_explicitly_server_safe(self):
        catalog = json.loads((ROOT / "mods" / "catalog.json").read_text())
        self.assertEqual(catalog["schema_version"], 2)
        self.assertIsInstance(catalog["mods"], list)
        for entry in catalog["mods"]:
            self.assertTrue(entry["id"])
            self.assertIn("scope", entry)
            self.assertIn("server_install_allowed", entry)
            self.assertIn("install_method", entry)

    def test_dashboard_configuration_uses_expected_bind_port_and_http_only_local_test_surface(self):
        source = (ROOT / "dashboard.py").read_text()
        self.assertIn("DASHBOARD_PORT = 8080", source)
        self.assertIn("ThreadedHTTPServer(('0.0.0.0', DASHBOARD_PORT)", source)
        self.assertIn("HttpOnly", source)
        self.assertNotIn("subprocess.Popen", source)

    def test_lifecycle_script_has_valid_shell_syntax_and_explicit_confirmation_guards(self):
        script = ROOT / "palworld.sh"
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        source = script.read_text()
        self.assertIn("acquire_lifecycle_lock", source)
        self.assertIn("confirm_lifecycle_interrupt", source)
        self.assertIn('confirmation_mode" = "--yes"', source)
        self.assertIn("Refusing to interrupt the running server non-interactively", source)
        self.assertIn('screen -S "$SCREEN_NAME" -X quit', source)

    def test_lifecycle_script_does_not_allow_arbitrary_command_dispatch(self):
        source = (ROOT / "palworld.sh").read_text()
        self.assertNotIn('eval "$@"', source)
        self.assertNotIn('bash -c "$@"', source)
        self.assertNotIn('rm -rf /', source)


if __name__ == "__main__":
    unittest.main()
