# Repository Guidelines

## Project Overview

PalworldX is a Linux Palworld dedicated-server manager. `palworld.sh` is the operational entrypoint for installation, lifecycle control, firewall setup, status, logs, console access, and dashboard launch. `dashboard.py` adds a zero-dependency Python web dashboard; `mod_manager.py` provides filesystem-safe mod catalog, staging, manifest, backup, and rollback primitives.

## Architecture & Data Flow

- **Lifecycle layer:** `palworld.sh` validates deployment configuration, runs SteamCMD/server operations as the `steam` user, manages the Palworld process in a `screen` session, and serializes lifecycle mutations with `flock`.
- **Dashboard layer:** `dashboard.py` uses Python’s `http.server`/`BaseHTTPRequestHandler` and an inline HTML/CSS/JS UI. It exposes authenticated status, logs, configuration, control, and mod APIs on port `8080`.
- **Mod layer:** `mod_manager.py` is imported optionally by the dashboard. It loads `mods/catalog.json`, canonicalizes IDs, validates ZIP paths, stages and inspects archives, writes manifests atomically, tracks owned files, and supports backups/rollback. It does not download mods or directly start/stop the server.
- **Runtime flow:** CLI or dashboard request → validated command/filesystem operation → `steam`-owned server paths under `/home/steam/`. Mutating lifecycle and maintenance operations require explicit confirmation; do not bypass those guards.

## Key Directories

- `.` — Bash entrypoint, Python modules, JSON catalog, and project documentation.
- `tests/` — `unittest` contract and behavior tests.
- `mods/` — Curated mod metadata in `catalog.json`; catalog policy is blocked unless explicitly approved.
- `.claude/` — Claude Code safety hook configuration.
- `/home/steam/` (deployment runtime) — SteamCMD, Palworld server, generated management scripts, dashboard deployment, and lifecycle lock.

## Development Commands

Run commands from the repository root:

```bash
# Install/manage the server (requires root on a deployment host)
sudo bash palworld.sh install
sudo bash palworld.sh start|stop|restart|status|update|logs|console|discover|config

# Interactive menu
sudo bash palworld.sh menu

# Run all tests
python3 -m unittest discover -s tests

# Run one test module
python3 tests/test_mod_manager.py
python3 tests/test_dashboard.py
python3 tests/test_deployment_and_lifecycle.py

# Syntax checks
python3 -m py_compile dashboard.py mod_manager.py
bash -n palworld.sh
```

`stop`, `restart`, and `update` interrupt a running server. Use interactive confirmation or `--yes` only after independently verifying that interruption is safe.

## Code Conventions & Common Patterns

- Prefer the standard library; the project intentionally has no Python framework or dependency manifest.
- Python uses `snake_case`, `unittest.TestCase`, and small functions with explicit error results/exceptions. Use `pathlib.Path`, context managers, and `tempfile` for filesystem work.
- Shell uses Bash functions, `set -e`, quoted variables, allow-listed configuration keys, explicit validation, and fixed command dispatch. Do not use `eval` or arbitrary `bash -c` dispatch.
- Validate trust-boundary inputs: deployment paths/ports, archive member paths, catalog entries, and authenticated maintenance tokens.
- Use fixed-argv `subprocess.run(..., shell=False)` for commands where possible. Existing intentional shell pipelines are isolated in `run_command`.
- Dashboard state is module-level in-memory state: sessions expire after one hour; maintenance confirmations are single-use and expire after five minutes.
- Mutating filesystem operations should preserve atomicity and rollback behavior. Manifests are written through temporary files plus `os.replace`; operation locks use non-blocking `fcntl.flock`.
- Keep production safety explicit: lifecycle locks, confirmation guards, backups, and audit/operation records are part of the design—not optional conveniences.

## Important Files

- `palworld.sh` — authoritative CLI, installer, lifecycle controller, firewall setup, and dashboard launcher.
- `dashboard.py` — HTTP server, authentication, APIs, and inline UI.
- `mod_manager.py` — safe mod-management backend and filesystem primitives.
- `mods/catalog.json` — versioned curated mod metadata and server-install policy.
- `tests/test_deployment_and_lifecycle.py` — shell/config/security contract checks.
- `tests/test_dashboard.py` — HTTP and dashboard API behavior checks.
- `tests/test_mod_manager.py` — archive, manifest, staging, backup, rollback, and lock checks.
- `.claude/settings.json` — PreToolUse safety hook for production-interrupting Bash commands.
- `README.md` — primary user-facing command reference.
- `IMPLEMENTATION_PLAN.md`, `TASK_TRACKING.md` — implementation scope and milestone status.

## Runtime/Tooling Preferences

- Deployment target: Debian/Ubuntu-compatible Linux VPS; SteamCMD requires x86_64 and 32-bit libraries.
- Server operations run as the dedicated non-root `steam` user. Installation/setup generally requires `sudo`/root.
- Use `bash` and `python3`; the dashboard and mod manager use only Python’s standard library. No npm, pip, Flask, pytest, or other package manager is required.
- Palworld runtime defaults: `/home/steam/palworld-server`; SteamCMD: `/home/steam/steamcmd`; process session: `screen` named `palworld`.
- Configuration is read from `/etc/palworld/palworld.conf` and can be overridden with `PALWORLD_*` environment variables. Dashboard credentials use `PALWORLD_DASHBOARD_PASSWORD` or `PALWORLD_DASHBOARD_PASSWORD_FILE`; never deploy with the development fallback password.
- Default dashboard port is `8080`; game/query/RCON ports are `8211/UDP`, `27015/TCP+UDP`, and `25575/TCP`.

## Testing & QA

Tests use Python’s standard-library `unittest`; there is no pytest, tox, coverage, or project packaging configuration. Run the full discovery command before delivery. Tests are deterministic and avoid production paths by using temporary directories, in-memory ZIP archives, mocks, and an ephemeral local HTTP server.

Coverage is contract-focused rather than percentage-driven. Preserve tests for:

- catalog schema and canonical mod aliases;
- ZIP traversal/absolute-path rejection and safe extraction;
- atomic manifests, staging limits, owned-file cleanup, backups, rollback, and lock contention;
- dashboard authentication, session expiry, JSON-safe backend adapters, and single-use maintenance confirmation;
- Bash syntax, lifecycle locks/confirmation, and rejection of arbitrary command dispatch.

Do not run lifecycle commands against a production server as part of tests. Use `bash -n`, Python compile checks, mocks, temporary paths, and local HTTP fixtures instead.
