# Palworld Mod Manager Implementation Plan

## Goal

Extend the existing zero-dependency Palworld installer and dashboard with safe mod management while protecting the production server from unconfirmed interruption.

## Production rules

- Never stop, restart, or update the production server without explicit user confirmation in the current conversation.
- Mod changes that affect server files require an explicit maintenance approval immediately before the operation.
- Prefer online/read-only inspection, staging, validation, and backups before downtime.
- Never silently bypass a failed stop, restart, or rollback operation.

## Milestones

### M1 — Safety and tracking
- [x] Add repository plan and task tracking.
- [ ] Add server-side confirmation to CLI stop/restart/update paths.
- [ ] Add server-side confirmation to dashboard control paths.
- [ ] Add operation lock and audit logging.
- [ ] Add project Claude hook for production-interrupting Bash commands.

### M2 — Mod foundation
- [ ] Add a stdlib-only mod manager module.
- [ ] Add versioned JSON manifest and curated catalog.
- [ ] Add client/server/both/unknown compatibility metadata.
- [ ] Add dependency and installation-method metadata.
- [ ] Add safe archive extraction and path validation.

### M3 — Low-downtime operations
- [ ] Stage uploads and validate them while the server remains online.
- [ ] Create save/config/mod backups before applying changes.
- [ ] Apply only the minimum required file changes during a confirmed maintenance window.
- [ ] Add rollback and failed-operation recovery.
- [ ] Add lock files to prevent concurrent operations.

### M4 — Dashboard and API
- [ ] Add authenticated mod APIs.
- [ ] Add Mods page with compatibility badges and client instructions.
- [ ] Add dry-run/preview operation flow.
- [ ] Add explicit maintenance confirmation flow for mutating operations.
- [ ] Add operation history and backup visibility.

### M5 — Initial curated catalog
- [ ] Add verified entries for Dungeon Boss Respawn Map Timer.
- [ ] Add verified entries for Less Restrictive Building.
- [ ] Add verified entries for PalPriority and split client UI.
- [ ] Add Building Enhanced as client-only.
- [ ] Add unresolved entries as unknown and block automatic server installation.
- [ ] Keep duplicate Workshop/Nexus references linked to one canonical mod.

### M6 — Verification and release
- [ ] Add unit tests for manifest, paths, dependencies, backups, and rollback.
- [ ] Add dashboard/API smoke tests without touching production.
- [ ] Run shell syntax and Python compile checks.
- [ ] Update user documentation and client installation instructions.
- [ ] Commit each completed milestone.
- [ ] Push milestone commits to origin after local verification.

## File map

| Area | Files |
|---|---|
| Installer lifecycle | `palworld.sh` |
| Dashboard/API/UI | `dashboard.py` |
| Mod engine | `mod_manager.py` |
| Curated catalog | `mods/catalog.json` |
| Runtime manifest | `/home/steam/palworld-server/.palworld-mods/manifest.json` |
| Tests | `tests/` |
| Tracking | `IMPLEMENTATION_PLAN.md`, `TASK_TRACKING.md` |
| Claude project safety | `.claude/settings.json` |

## Mod classification baseline

| Mod | Scope | Status |
|---|---|---|
| AutomaticallySkipModCaution | Likely client-only | Do not install on dedicated server automatically |
| Smaller Plantations | Unknown; multiplayer unsupported | Manual review required |
| Currencies, Keys and More are Key Items | Unknown; dedicated-server unsupported | Block by default |
| Dungeon Boss Respawn Map Timer | Client-only | Client instructions only |
| Less Restrictive Building | Both, package-dependent | Require PAK/UE4SS selection |
| PalPriority | Both, split core/UI components | Server core plus optional client UI |
| Building Enhanced / Free Camera | Client-only | Client instructions only |
| Nexus 550, 3915, 214, 190 | Unknown pending verification | Block automatic installation |

## Agent workstreams

- Safety: lifecycle confirmation, locks, and audit trail.
- Backend: mod manifest, safe file operations, backups, rollback.
- Dashboard: API and UI integration.
- Security: archive and command safety review.
- Tests: unit, integration, and non-production smoke tests.
- Documentation: operator and client setup guidance.
