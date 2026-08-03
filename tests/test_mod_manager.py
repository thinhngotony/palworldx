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

    def test_apply_action_updates_only_temporary_manifest_and_canonicalizes_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            result = mod_manager.apply_action(
                "dungeon-boss-respawn-map-timer-duplicate", "enable", manifest
            )
            self.assertTrue(result["applied"])
            self.assertEqual(result["id"], "dungeon-boss-respawn-map-timer")
            record = mod_manager.read_manifest(manifest)["mods"][result["id"]]
            self.assertTrue(record["enabled"])
            self.assertEqual(record["catalog_version"], None)

            with self.assertRaises(mod_manager.ModManagerError):
                mod_manager.apply_action("palpriority", "remove", manifest)

    def test_apply_action_without_manifest_is_explicitly_non_mutating(self):
        result = mod_manager.apply_action("palpriority", "disable")
        self.assertFalse(result["applied"])
        self.assertIn("not changed", result["message"])

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

<<<<<<< HEAD
    def test_staging_limits_hash_and_package_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "mod.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("Mods/example.pak", b"pak")
                bundle.writestr("ue4ss/mod.dll", b"dll")
            staged = mod_manager.stage_upload(archive, root / "staging", max_bytes=1000, max_files=3)
            self.assertEqual(staged["sha256"], mod_manager.sha256_file(archive))
            self.assertEqual(mod_manager.inspect_packages(staged["staging_dir"])["pak"], ["Mods/example.pak"])
            self.assertIn("ue4ss/mod.dll", mod_manager.inspect_packages(staged["staging_dir"])["ue4ss"])

    def test_archive_rejects_backslash_absolute_duplicate_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [("backslash.zip", [("..\\escape", b"x")]),
                     ("absolute.zip", [("/escape", b"x")]),
                     ("duplicate.zip", [("a.pak", b"x"), ("a.pak", b"y")])]
            for filename, members in cases:
                archive = root / filename
                with zipfile.ZipFile(archive, "w") as bundle:
                    for name, content in members:
                        bundle.writestr(name, content)
                with self.assertRaises(mod_manager.UnsafeArchivePath):
                    mod_manager.stage_upload(archive, root / "staging")
            archive = root / "symlink.zip"
            info = zipfile.ZipInfo("link.pak")
            info.create_system = 3
            info.external_attr = (0o120777 << 16)
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(info, "target")
            with self.assertRaises(mod_manager.UnsafeArchivePath):
                mod_manager.stage_upload(archive, root / "staging")

    def test_preview_gate_apply_and_owned_file_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "approved.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("Mods/example.pak", b"pak")
            catalog = {"approved": {"id": "approved", "scope": "server",
                                     "server_install_allowed": True}}
            staged = mod_manager.stage_upload(archive, root / "staging")
            plan = mod_manager.preview_plan(staged["staging_dir"], root / "server", "approved", catalog=catalog)
            manifest = root / "manifest.json"
            record = mod_manager.apply_plan(plan, staged["staging_dir"], manifest)
            owned = root / "server" / "Mods/example.pak"
            self.assertTrue(owned.exists())
            self.assertIn(str(owned), record["owned_files"])
            unrelated = root / "server" / "keep.txt"
            unrelated.write_text("keep")
            mod_manager.set_mod_state(manifest, "approved", "disable")
            self.assertFalse(owned.exists())
            self.assertTrue(unrelated.exists())
            with self.assertRaises(mod_manager.ModManagerError):
                mod_manager.preview_plan(staged["staging_dir"], root / "server", "unknown")

    def test_client_instruction_generation_does_not_execute(self):
        plan = {"files": [{"path": "Mods/ui.pak", "destination": "/client/Mods/ui.pak"}]}
        self.assertIn("Copy Mods/ui.pak", mod_manager.client_instructions(plan))
=======
    def test_rollback_missing_backup_does_not_remove_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "server"
            target.mkdir()
            (target / "important.txt").write_text("keep")
            with self.assertRaises(FileNotFoundError):
                mod_manager.rollback_backup(root / "missing", target)
            self.assertEqual((target / "important.txt").read_text(), "keep")

    def test_archive_validation_rejects_absolute_windows_and_backslash_paths(self):
        for name in ("/absolute.txt", "C:/absolute.txt", "~user/file.txt", "folder\\file.txt"):
            with self.subTest(name=name):
                with self.assertRaises(mod_manager.UnsafeArchivePath):
                    mod_manager.validate_archive_member(name)
>>>>>>> c850cfe


if __name__ == "__main__":
    unittest.main()
