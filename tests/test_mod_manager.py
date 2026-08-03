import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mod_manager


class ModManagerTests(unittest.TestCase):
    def test_catalog_has_twelve_entries_and_aliases_canonicalize(self):
        catalog = mod_manager.load_catalog()
        self.assertEqual(len(catalog), 12)
        self.assertEqual(mod_manager.canonical_mod_id("dungeon-boss-respawn-map-timer-duplicate", catalog), "dungeon-boss-respawn-map-timer")
        self.assertEqual(mod_manager.get_mod("dungeon-boss-respawn-map-timer-duplicate", catalog)["id"], "dungeon-boss-respawn-map-timer")

    def test_manifest_round_trip_and_enabled_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            self.assertEqual(mod_manager.read_manifest(path)["mods"], {})
            record = mod_manager.set_mod_enabled(path, "palpriority", True, version="1.0", source="local")
            self.assertTrue(record["enabled"])
            loaded = mod_manager.read_manifest(path)
            self.assertEqual(loaded["mods"]["palpriority"]["version"], "1.0")
            self.assertFalse(mod_manager.set_mod_enabled(path, "palpriority", False)["enabled"])

    def test_archive_traversal_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape.txt", "no")
            with self.assertRaises(mod_manager.UnsafeArchivePath):
                mod_manager.extract_archive_safely(archive, root / "out")
            self.assertFalse((root / "escape.txt").exists())

    def test_archive_extracts_safe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "good.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("PAK/example.txt", "ok")
            files = mod_manager.extract_archive_safely(archive, root / "out")
            self.assertEqual(files[0].read_text(), "ok")

    def test_lock_and_backup_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "server"
            source.mkdir()
            (source / "settings.ini").write_text("old")
            backup = mod_manager.create_backup(source, root / "backups", "mods")
            (source / "settings.ini").write_text("changed")
            mod_manager.rollback_backup(backup, source)
            self.assertEqual((source / "settings.ini").read_text(), "old")
            lock = root / "operation.lock"
            with mod_manager.operation_lock(lock):
                with self.assertRaises(mod_manager.OperationInProgress):
                    with mod_manager.operation_lock(lock):
                        pass


if __name__ == "__main__":
    unittest.main()
