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
import subprocess
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


def apply_action(mod_id: str, action: str, manifest_path: os.PathLike[str] | str | None = None) -> dict[str, Any]:
    """Update catalog-backed state only; file installation remains an explicit future operation."""
    if action not in {"enable", "disable"}:
        raise ModManagerError(f"unsupported mod action: {action}")
    catalog = load_catalog()
    canonical = canonical_mod_id(mod_id, catalog)
    mod = get_mod(canonical, catalog)
    if manifest_path is None:
        return {"id": canonical, "action": action, "metadata": mod, "applied": False,
                "message": "No runtime manifest supplied; catalog state was not changed."}
    record = set_mod_enabled(manifest_path, canonical, action == "enable", catalog_version=mod.get("version"))
    return {"id": canonical, "action": action, "record": record, "applied": True}


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


# Upload/deployment primitives.  These functions intentionally accept local paths:
# acquiring a download is outside this module's trust boundary.
DEFAULT_MAX_UPLOAD_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_FILES = 2048


def _under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _controlled_root(root: os.PathLike[str] | str) -> Path:
    requested = Path(root).expanduser()
    if requested.exists() and requested.is_symlink():
        raise ModManagerError("staging root must not be a symlink")
    requested.mkdir(parents=True, exist_ok=True)
    value = requested.resolve()
    if value.is_symlink():
        raise ModManagerError("staging root must not be a symlink")
    return value


def sha256_file(path: os.PathLike[str] | str, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_limits(infos: list[zipfile.ZipInfo], max_files: int, max_bytes: int) -> None:
    if len(infos) > max_files:
        raise ModManagerError("archive file-count limit exceeded")
    total = 0
    for info in infos:
        if info.file_size < 0 or info.file_size > max_bytes - total:
            raise ModManagerError("archive size limit exceeded")
        total += info.file_size
        # Unix mode 0120000 is a symlink.  ZIP extraction must never materialize it.
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise UnsafeArchivePath(info.filename)


def _stage_rar(source: Path, directory: Path, max_bytes: int, max_files: int) -> list[Path]:
    """Validate bare RAR member names before extracting with bsdtar."""
    try:
        listing = subprocess.run(("bsdtar", "-tf", str(source)), check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ModManagerError("RAR support requires libarchive-tools (bsdtar)") from error
    members = [validate_archive_member(line) for line in listing.stdout.splitlines() if line]
    if not members or len(members) > max_files or len(set(members)) != len(members):
        raise ModManagerError("invalid RAR member list")
    try:
        subprocess.run(("bsdtar", "-x", "-f", str(source), "-C", str(directory), "--no-same-owner", "--no-same-permissions"), check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ModManagerError("RAR extraction failed") from error
    files = [p for p in directory.rglob("*") if p.is_file() and not p.is_symlink()]
    root = directory.resolve()
    if len(files) > max_files or any(not _under(p.resolve(), root) for p in files):
        raise UnsafeArchivePath("RAR extraction escaped staging directory")
    total = sum(p.stat().st_size for p in files)
    if total > max_bytes:
        raise ModManagerError("archive size limit exceeded")
    extracted_names = {p.relative_to(root).as_posix() for p in files}
    expected_files = {name.rstrip("/") for name in members if not name.endswith("/")}
    if extracted_names != expected_files:
        raise UnsafeArchivePath("RAR extraction changed member set")
    return files


def stage_upload(archive: os.PathLike[str] | str, staging_root: os.PathLike[str] | str,
                 *, max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
                 max_files: int = DEFAULT_MAX_FILES) -> dict[str, Any]:
    """Validate and stage a ZIP, RAR, or single PAK file safely."""
    root = _controlled_root(staging_root)
    source = Path(archive).expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise ModManagerError("upload must be a regular local file")
    if source.stat().st_size > max_bytes:
        raise ModManagerError("upload size limit exceeded")
    directory = Path(tempfile.mkdtemp(prefix="upload-", dir=root))
    try:
        if source.suffix.lower() == ".pak":
            target = directory / source.name
            shutil.copy2(source, target)
            files = [target]
        elif source.suffix.lower() == ".rar":
            files = _stage_rar(source, directory, max_bytes, max_files)
        else:
            with zipfile.ZipFile(source) as bundle:
                infos = bundle.infolist()
                _archive_limits(infos, max_files, max_bytes)
                names = [validate_archive_member(info.filename) for info in infos]
                if len(set(names)) != len(names):
                    raise UnsafeArchivePath("duplicate archive member")
            files = extract_archive_safely(source, directory)
            if len({p.relative_to(directory).as_posix() for p in files}) != len(files):
                raise UnsafeArchivePath("duplicate archive member")
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return {"staging_dir": directory, "archive": source, "sha256": sha256_file(source),
            "file_count": len(files), "bytes": sum(p.stat().st_size for p in files),
            "files": [p.relative_to(directory).as_posix() for p in files]}

def inspect_packages(staging_dir: os.PathLike[str] | str) -> dict[str, Any]:
    """Identify supported PAK and UE4SS payloads without executing anything."""
    root = Path(staging_dir).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ModManagerError("invalid staging directory")
    files = [p for p in root.rglob("*") if p.is_file() and not p.is_symlink()]
    pak = [p.relative_to(root).as_posix() for p in files if p.suffix.lower() == ".pak"]
    ue4ss = [p.relative_to(root).as_posix() for p in files
             if p.suffix.lower() in {".dll", ".ini", ".uplugin"} or "ue4ss" in p.parts]
    unsupported = [p.relative_to(root).as_posix() for p in files
                   if p.relative_to(root).as_posix() not in set(pak + ue4ss)]
    return {"pak": sorted(set(pak)), "ue4ss": sorted(set(ue4ss)),
            "unsupported": sorted(unsupported), "supported": bool(pak or ue4ss)}


def _gate(mod_id: str, package: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], target: str) -> dict[str, Any]:
    try:
        mod = get_mod(mod_id, catalog)
    except KeyError as exc:
        raise ModManagerError("unknown mods are blocked by default") from exc
    if target == "server" and not mod.get("server_install_allowed", False):
        raise ModManagerError(f"server installation is not approved for {mod_id}")
    scope = mod.get("scope", "unknown")
    if scope not in {target, "both"}:
        raise ModManagerError(f"mod is not compatible with {target}")
    if not package.get("supported") or package.get("unsupported"):
        raise ModManagerError("package contains unsupported or unrecognized files")
    return mod


def preview_plan(staging_dir: os.PathLike[str] | str, target_root: os.PathLike[str] | str,
                 mod_id: str, *, target: str = "server",
                 catalog: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Return a deterministic plan; this performs no writes and rejects unsafe targets."""
    if target not in {"server", "client"}:
        raise ModManagerError("target must be server or client")
    root = Path(target_root).expanduser().resolve()
    package = inspect_packages(staging_dir)
    mod = _gate(mod_id, package, catalog or load_catalog(), target)
    files = sorted(p for p in Path(staging_dir).resolve().rglob("*") if p.is_file() and not p.is_symlink())
    entries = []
    for source in files:
        relative = source.relative_to(Path(staging_dir).resolve()).as_posix()
        destination = (root / relative).resolve()
        if not _under(destination, root):
            raise UnsafeArchivePath(relative)
        entries.append({"path": relative, "sha256": sha256_file(source),
                        "destination": str(destination), "owned": True})
    return {"mod_id": canonical_mod_id(mod["id"], catalog or load_catalog()), "target": target,
            "files": entries, "package": package}


def apply_plan(plan: Mapping[str, Any], staging_dir: os.PathLike[str] | str,
               manifest_path: os.PathLike[str] | str) -> dict[str, Any]:
    """Apply one plan, replacing only its owned paths and recording hashes."""
    if not plan.get("files"):
        raise ModManagerError("deployment plan has no files")
    root = Path(plan["files"][0]["destination"]).resolve().parent
    for item in plan["files"][1:]:
        destination = Path(item["destination"]).resolve().parent
        root = Path(os.path.commonpath((str(root), str(destination))))
    root.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(manifest_path)
    mod_id = str(plan["mod_id"])
    old = manifest["mods"].get(mod_id, {})
    owned = set(old.get("owned_files", []))
    for item in plan["files"]:
        destination = Path(item["destination"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = Path(staging_dir).resolve() / item["path"]
        shutil.copy2(source, destination)
        owned.add(str(destination))
    record = {"enabled": True, "owned_files": sorted(owned),
              "files": {item["path"]: item["sha256"] for item in plan["files"]},
              "target": plan["target"]}
    manifest["mods"][mod_id] = record
    write_manifest(manifest_path, manifest)
    return record


def batch_apply(operations: list[Mapping[str, Any]], manifest_path: os.PathLike[str] | str,
                backup_root: os.PathLike[str] | str) -> list[dict[str, Any]]:
    """Apply operations atomically from the caller's perspective, restoring on failure."""
    manifest = Path(manifest_path)
    snapshot = create_backup(manifest, backup_root, "manifest") if manifest.exists() else None
    targets = {Path(item["destination"]).resolve().parent for op in operations for item in op["plan"]["files"]}
    backups = [(target, create_backup(target, backup_root, "target")) for target in targets if target.exists()]
    try:
        return [apply_plan(op["plan"], op["staging_dir"], manifest) for op in operations]
    except Exception:
        if snapshot:
            rollback_backup(snapshot, manifest)
        for target, backup in backups:
            rollback_backup(backup, target)
        raise


def set_mod_state(manifest_path: os.PathLike[str] | str, mod_id: str, action: str) -> dict[str, Any]:
    """Enable/disable/remove only files owned by this mod's manifest record."""
    if action not in {"enable", "disable", "remove"}:
        raise ModManagerError(f"unsupported mod action: {action}")
    manifest = read_manifest(manifest_path)
    record = manifest["mods"].get(mod_id)
    if record is None:
        raise KeyError(mod_id)
    if action in {"disable", "remove"}:
        for raw in record.get("owned_files", []):
            path = Path(raw)
            if path.is_file() and not path.is_symlink():
                path.unlink()
        # Remove now-empty directories only; never remove a directory containing
        # unowned content.
        for raw in sorted(record.get("owned_files", []), key=lambda value: len(Path(value).parts), reverse=True):
            parent = Path(raw).parent
            while parent != parent.parent:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
    if action == "remove":
        del manifest["mods"][mod_id]
    else:
        record["enabled"] = action == "enable"
    write_manifest(manifest_path, manifest)
    return record if action != "remove" else {"id": mod_id, "removed": True}


def client_instructions(plan: Mapping[str, Any]) -> str:
    """Generate inert, human-readable instructions rather than executing client work."""
    return "Install the approved client package manually.\n" + "\n".join(
        f"- Copy {item['path']} to {item['destination']}" for item in plan.get("files", []))

# Explicit aliases make the backend contract discoverable to callers.
stage_archive = stage_upload
inspect_package = inspect_packages
plan_deployment = preview_plan
apply_batch = batch_apply
