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

    def test_manifest_round_trip_and_enabled_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            mod_manager.set_mod_enabled(path, "palpriority", True, version="1.0", source="local")
            record = mod_manager.set_mod_state(path, "palpriority", "enable")
            self.assertTrue(record["enabled"])
            self.assertFalse(mod_manager.set_mod_state(path, "palpriority", "disable")["enabled"])

    def test_archive_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape.txt", "no")
            with self.assertRaises(mod_manager.UnsafeArchivePath):
                mod_manager.extract_archive_safely(archive, root / "out")
            for name in ("/absolute.txt", "C:/absolute.txt", "~user/file.txt", "folder\\file.txt"):
                with self.assertRaises(mod_manager.UnsafeArchivePath):
                    mod_manager.validate_archive_member(name)

    def test_archive_extracts_safe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "good.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("PAK/example.txt", "ok")
            self.assertEqual(mod_manager.extract_archive_safely(archive, root / "out")[0].read_text(), "ok")

    def test_apply_action_and_non_mutating_without_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            result = mod_manager.apply_action("dungeon-boss-respawn-map-timer-duplicate", "enable", manifest)
            self.assertTrue(result["applied"])
            self.assertTrue(mod_manager.read_manifest(manifest)["mods"][result["id"]]["enabled"])
        result = mod_manager.apply_action("palpriority", "disable")
        self.assertFalse(result["applied"])

    def test_staging_preview_apply_and_owned_file_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "approved.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("Mods/example.pak", b"pak")
                bundle.writestr("ue4ss/mod.dll", b"dll")
            staged = mod_manager.stage_upload(archive, root / "staging", max_bytes=1000, max_files=3)
            self.assertEqual(staged["sha256"], mod_manager.sha256_file(archive))
            self.assertIn("Mods/example.pak", mod_manager.inspect_packages(staged["staging_dir"])["pak"])
            catalog = {"approved": {"id": "approved", "scope": "server", "server_install_allowed": True}}
            plan = mod_manager.preview_plan(staged["staging_dir"], root / "server", "approved", catalog=catalog)
            manifest = root / "manifest.json"
            record = mod_manager.apply_plan(plan, staged["staging_dir"], manifest)
            owned = root / "server" / "Pal" / "Content" / "Paks" / "~mods" / "Mods" / "example.pak"
            self.assertTrue(owned.exists())
            self.assertIn(str(owned.resolve()), record["owned_files"])
            (root / "server" / "keep.txt").write_text("keep")
            mod_manager.set_mod_state(manifest, "approved", "disable")
            self.assertFalse(owned.exists())
            self.assertTrue((root / "server" / "keep.txt").exists())
            plan = mod_manager.preview_plan(staged["staging_dir"], root / "server", "unknown")
            self.assertEqual(plan["mod_id"], "unknown")

    def test_stage_single_pak_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); pak = root / "BNLrelease_P.pak"; pak.write_bytes(b"pak-data")
            staged = mod_manager.stage_upload(pak, root / "staging")
            self.assertEqual(staged["files"], ["BNLrelease_P.pak"])

    def test_backup_rollback_and_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "server"
            source.mkdir()
            (source / "settings.ini").write_text("old")
            backup = mod_manager.create_backup(source, root / "backups", "mods")
            (source / "settings.ini").write_text("changed")
            mod_manager.rollback_backup(backup, source)
            self.assertEqual((source / "settings.ini").read_text(), "old")
            with self.assertRaises(FileNotFoundError):
                mod_manager.rollback_backup(root / "missing", source)
            lock = root / "operation.lock"
            with mod_manager.operation_lock(lock):
                with self.assertRaises(mod_manager.OperationInProgress):
                    with mod_manager.operation_lock(lock):
                        pass

    def test_client_instruction_generation(self):
        self.assertIn("Copy Mods/ui.pak", mod_manager.client_instructions({"files": [{"path": "Mods/ui.pak", "destination": "/client/Mods/ui.pak"}]}))


if __name__ == "__main__":
    unittest.main()
