"""Safe, filesystem-only foundations for managing Palworld mods.

This module deliberately does not download, install, start, or stop a server.  The
higher-level dashboard can use these primitives after its own authorization and
maintenance-window checks.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping

SCHEMA_VERSION = 1
DEFAULT_CATALOG = Path(__file__).resolve().parent / "mods" / "catalog.json"


class ModManagerError(Exception):
    """Base exception for safe mod-manager failures."""


class UnsafeArchivePath(ModManagerError):
    pass


class OperationInProgress(ModManagerError):
    pass


def load_catalog(path: os.PathLike[str] | str = DEFAULT_CATALOG) -> dict[str, dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict) or not isinstance(payload.get("mods"), list):
        raise ModManagerError("catalog must contain a mods list")
    result = {}
    for entry in payload["mods"]:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise ModManagerError("catalog entries require an id")
        result[str(entry["id"])] = entry
    return result


def canonical_mod_id(mod_id: str, catalog: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    catalog = catalog or load_catalog()
    current = str(mod_id)
    seen: set[str] = set()
    while current in catalog and catalog[current].get("canonical_id"):
        if current in seen:
            raise ModManagerError("catalog contains a canonicalization cycle")
        seen.add(current)
        current = str(catalog[current]["canonical_id"])
    return current


def get_mod(mod_id: str, catalog: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    canonical = canonical_mod_id(mod_id, catalog)
    try:
        return copy.deepcopy(dict(catalog[canonical]))
    except KeyError as exc:
        raise KeyError(f"unknown mod: {mod_id}") from exc


def list_mods(catalog: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    catalog = catalog or load_catalog()
    return [copy.deepcopy(dict(entry)) for mod_id, entry in catalog.items() if canonical_mod_id(mod_id, catalog) == mod_id]


def get_mods(catalog: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    return list_mods(catalog)


def validate_archive_member(name: str) -> str:
    """Return a normalized archive member or reject traversal/absolute paths."""
    if not isinstance(name, str) or not name or "\\" in name:
        raise UnsafeArchivePath(name)
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise UnsafeArchivePath(name)
    # Windows drive-like names are unsafe even on Linux.
    if ":" in path.parts[0] or path.parts[0].startswith("~"):
        raise UnsafeArchivePath(name)
    return "/".join(path.parts)


def validate_archive(archive: os.PathLike[str] | str) -> list[str]:
    with zipfile.ZipFile(archive) as bundle:
        return [validate_archive_member(info.filename) for info in bundle.infolist()]


def extract_archive_safely(archive: os.PathLike[str] | str, destination: os.PathLike[str] | str) -> list[Path]:
    """Extract a ZIP after validating every member and enforcing destination containment."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive) as bundle:
        names = [validate_archive_member(info.filename) for info in bundle.infolist()]
        for info, name in zip(bundle.infolist(), names):
            target = (destination / name).resolve()
            if os.path.commonpath((str(destination), str(target))) != str(destination):
                raise UnsafeArchivePath(info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                extracted.append(target)
    return extracted


def _empty_manifest() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "updated_at": None, "mods": {}}


def read_manifest(path: os.PathLike[str] | str) -> dict[str, Any]:
    manifest = Path(path)
    if not manifest.exists():
        return _empty_manifest()
    with manifest.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION or not isinstance(value.get("mods"), dict):
        raise ModManagerError("unsupported or malformed manifest")
    return value


def write_manifest(path: os.PathLike[str] | str, manifest: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(manifest))
    value["schema_version"] = SCHEMA_VERSION
    value["updated_at"] = int(time.time())
    if not isinstance(value.get("mods"), dict):
        raise ModManagerError("manifest mods must be an object")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def set_mod_enabled(path: os.PathLike[str] | str, mod_id: str, enabled: bool, **metadata: Any) -> dict[str, Any]:
    manifest = read_manifest(path)
    record = dict(manifest["mods"].get(mod_id, {}))
    record.update(metadata)
    record["enabled"] = bool(enabled)
    manifest["mods"][mod_id] = record
    write_manifest(path, manifest)
    return record


@contextmanager
def operation_lock(lock_path: os.PathLike[str] | str) -> Iterator[None]:
    """Acquire an exclusive, non-blocking process lock for a mutating operation."""
    lock = Path(lock_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OperationInProgress(str(lock)) from exc
        try:
            stream.seek(0)
            stream.truncate()
            stream.write(f"pid={os.getpid()}\n")
            stream.flush()
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def create_backup(source: os.PathLike[str] | str, backup_root: os.PathLike[str] | str, label: str = "backup") -> Path:
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(source)
    root = Path(backup_root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    destination = root / f"{label}-{stamp}-{os.getpid()}"
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.mkdir()
        shutil.copy2(source, destination / source.name)
    return destination


def rollback_backup(backup: os.PathLike[str] | str, target: os.PathLike[str] | str) -> None:
    """Replace target with a backup snapshot; target is only removed after validation."""
    backup, target = Path(backup), Path(target)
    if not backup.exists():
        raise FileNotFoundError(backup)
    temporary = target.with_name(f".{target.name}.rollback-{os.getpid()}")
    if temporary.exists():
        shutil.rmtree(temporary) if temporary.is_dir() else temporary.unlink()
    if backup.is_dir():
        shutil.copytree(backup, temporary)
    else:
        temporary.mkdir(parents=True)
        shutil.copy2(backup, temporary / backup.name)
    if target.exists():
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    os.replace(temporary, target)
