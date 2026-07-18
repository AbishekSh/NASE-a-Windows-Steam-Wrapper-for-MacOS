# SteamWineWrapper Codebase Structure

This document describes the current repository organization and the boundaries that should stay clear as the app evolves.

## Product Shape

SteamWineWrapper is currently split into two layers:

- `Sources/SteamWineApp/`: the native SwiftUI macOS product.
- `mysteamwine/` plus `mysteamwine.py`: the Python backend that manages Wine, bottles, Steam, graphics layers, scanning, and diagnostics.

The SwiftUI app is the user-facing product. The Python backend is the implementation engine. The app/backend contract is moving toward structured JSON/JSONL so the UI can react to real state instead of parsing human terminal output.

## Top-Level Files

- `Package.swift`: Swift Package manifest for the macOS app target.
- `README.md`: user-facing setup and command overview.
- `AGENTS.md`: project intent, architecture direction, and operating constraints for AI-assisted development.
- `assets/`: source app icons and logo assets.
- `Sources/SteamWineApp/Resources/`: app-bundled image resources.
- `mysteamwine.py`: thin Python entrypoint that calls `mysteamwine.cli.main()`.

## SwiftUI App

The SwiftUI layer owns library UX, app state, settings, sheets, and backend command orchestration. It should not grow Wine-specific process logic directly; that belongs in Python unless there is a clear reason to move it.

### Entry And Shell

- `SteamWineApp.swift`: app entrypoint.
- `ContentView.swift`: main window layout, sidebar, toolbar, library surface, and high-level sheet presentation.
- `SharedViews.swift`: small reusable SwiftUI pieces.
- `LibraryComponents.swift`: reusable library grid/list/detail components.

### State And Domain Models

- `Models.swift`: shared Swift enums and value types:
  - runners and sources: `RunnerKind`, `LibrarySourceFilter`
  - graphics selection: `GraphicsBackendOption`
  - library metadata: `LibraryGame`, `GameCollection`
  - backend result summaries: `BackendJob`, `BackendStructuredResult`, `BackendStreamUpdate`
  - launch status and health state
- `AppViewModel.swift`: primary observable state container. It owns:
  - selected source/game/search/filter/sort state
  - native, Steam, Wine, and pinned library arrays
  - per-game settings and launch status
  - backend job tracking and structured result history
  - settings validation and persistence
  - library import, refresh, launch, debug launch, log viewing, and health refresh orchestration

`AppViewModel.swift` is currently the largest file and is the main pressure point. Future work should move cohesive domains out only when the new file has a clear boundary, for example:

- `LibraryStore`: load/persist/import library items and pin/order state.
- `LaunchCoordinator`: Steam/Wine/macOS launch decisions and launch status.
- `HealthCoordinator`: background doctor checks and source health.
- `RuntimeStore`: Wine runtime detection/import/persistence.

Do not split it just for file size; split when it lowers coupling.

### Backend Bridge

- `BackendBridge.swift`: the Swift/Python boundary.
  - `BackendContext` stores paths and target selection.
  - `BackendAction` enumerates commands the UI can ask Python to run.
  - `BackendBridge.arguments(...)` maps Swift actions to `mysteamwine.py` CLI arguments.
  - `executeStreaming(...)` runs Python via `/usr/bin/env`, consumes JSONL, and emits `BackendStreamUpdate` values.

The bridge should remain the only place that knows the exact CLI argument shape. UI files should ask for actions, not assemble command arrays.

### Sheets

- `SettingsSheet.swift`: backend paths, bottle/prefix selection, Runtime Center, runtime status, job history, doctor/setup summaries.
- `SetupWizardSheet.swift`: guided first-run setup.
- `UpdateService.swift`: signed update-manifest verification, version checks,
  streamed DMG download, checksum validation, and user-confirmed installation.
- `WinetricksSheet.swift`: Winetricks UI.
- `GameSheets.swift`: game details, settings, logs, metadata, and per-game controls.

## Python Backend

The backend is a CLI-first engine. It should remain usable from Terminal while also supporting structured output for the SwiftUI app.

### CLI And Contract

- `mysteamwine/cli.py`: command parser and command handlers.
  - Global target selection: `--bottle` or `--prefix`.
  - Global runtime selection: `--wine` / related Wine path flags.
  - Structured modes: `--json` and `--jsonl`.
  - Job events: start, step, progress, result.
  - Commands include setup, doctor, Steam launch, game launch, direct debug launch, Winetricks, graphics installers, scanning, and advice.

The CLI is the compatibility contract. Existing commands should keep working even when the app gains richer structured behavior.

### Runtime And Bottles

- `runtime.py`: executable resolution, Wine runtime detection, process execution, detached process spawning, downloads, and sanitized Metal-related environment handling.
- `steam_libraries.py`: read-only cross-bottle Steam library discovery, profile-independent AppID resolution, and the canonical atomic `steam-libraries.json` registry.
- `steam_identity.py`: a locked shared-auth boundary that extracts and merges only Steam login metadata and bounded account-auth subtrees. It refuses mutation while any managed Windows Steam process is running and never shares entire prefixes or configuration files.
- `library_activity.py`: locked persistent ownership for shared libraries. It permits one Windows Steam owner per library, supports multiple games under that owner, and replaces stale ownership only after the previous Steam process exits.
- `catalog.py`: managed runtime catalog for Wine, DXVK, and DXMT. It owns pinned download URLs/checksums, archive extraction, install records, and one-button install helpers that can apply graphics payloads to the selected bottle.
- `bottle.py`: managed and external-prefix path model.
  - Managed bottles live under `~/Library/Application Support/MySteamWine/bottles/<name>/`.
  - External prefixes get app-managed logs/download/cache folders under `external-prefixes/<hash>/` while preserving the external prefix path itself.

### Steam And Launching

- `steam.py`: Steam installer/runner, Wine launch environment, game launch helpers, direct executable launch, VDF parsing, `libraryfolders.vdf` discovery, and `appmanifest_*.acf` game listing.
  - `run_steam(...)` launches Windows Steam in the bottle.
  - `launch_app(...)` launches through Steam with `-applaunch`.
  - `run_game_executable(...)` launches a chosen `.exe` directly with Wine.
  - `list_installed_apps(...)` detects installed Steam games from manifests.

Current Steam launch modes are:

- `run-steam`: open Windows Steam with plain Wine by default.
- `launch-game`: launch a Steam AppID through Windows Steam.
- `smart-launch-game`: try direct executable launch first, then fall back to Steam.
- `debug-game`: direct executable launch with richer debug logging and overrides.

### Graphics Installers

- `dxmt.py`: DXMT install and registry override management.
- `dxvk.py`: DXVK install from upstream or DXVK-macOS layouts.
- `gptk.py`: bounded compatible-runtime discovery, explicit Wine/D3DMetal version pairing, and confirmed import into persistent NASE-managed runtime storage without flattening the renderer bundle.
- `d3dmetal.py`: complete D3DMetal bundle inspection, mutually exclusive overrides, per-launch native search-path injection, and post-install profile verification.
- `pe.py`: lightweight PE machine detection used to distinguish 32-bit x86 applications from 64-bit executables before launch.
- `legacy_directx.py`: validates user-provided dgVoodoo2 x86 payloads and builds removable per-game overlays without writing wrapper DLLs into shared Steam installations.

Graphics-specific modules own file-layout validation and registry override edits. D3DMetal keeps its `wine`, `external`, and framework directories intact; launch modules obtain the complete environment from `d3dmetal.py` and inject it for every Steam and direct-game process.

Treat each graphics choice as a runtime profile, not only a DLL selection. DXMT uses the validated Wine Stable context. D3DMetal pins checksum-verified Sikarugir Wine 10 revision 6 to a complete renderer bundle plus an isolated `-D3DMetal` bottle. DXVK requires a separately validated Wine Vulkan/MoltenVK host stack. These renderer modes are mutually exclusive, and a successful DLL copy alone does not prove that the host graphics runtime can launch a game.

### Health, Dependencies, And Advice

- `doctor.py`: environment and prefix checks plus safe repairs.
- `jobs.py`: atomic durable job records, interrupted-job reconciliation, and
  verified backend-process cancellation.

### Packaged application layout

`scripts/build-app.sh` turns the SwiftPM executable into `NASE.app`. The release
bundle embeds the Python backend and probe tools at
`Contents/Resources/Backend`; `BackendContext.default()` prefers that location
and falls back to the repository only for development builds.

Signing/notarization assets live under `release/`, release automation under
`scripts/`, and the complete credential, update-feed, and clean-machine process
is documented in `docs/RELEASING.md`.
- `sessions.py`: persistent launch-session registry, real process reconciliation, targeted per-game termination, and ownership-aware Steam cleanup. Session records already carry a compatibility-profile id so runtime fingerprints can be added without replacing the lifecycle contract.
- `profiles.py`: compatibility-profile definitions and immutable per-bottle runtime/source fingerprints. A profile binds Wine, the graphics stack, and a dedicated bottle as one launch unit.
  - `setup-compatibility-profile` performs the observable setup workflow and only marks the profile manifest ready after Wine, Steam, and renderer setup succeed.
- `dependencies.py`: read-only host readiness checks for macOS, Python, Rosetta, Winetricks, Wine Stable 11, managed DXMT 0.71, and optional GPTK components.
  - Confirmed installation commands are generated as argument arrays without a shell. Rosetta license acceptance is mandatory, Homebrew installs Python/Wine Stable/Winetricks, and DXMT remains handled by the verified runtime catalog. A successful Python repair adopts and persists Homebrew's `python3` path before readiness is checked again.
  - `AppViewModel.startRecommendedBootstrap` is the guided state machine: check, confirm, install missing requirements, adopt paths, verify again, set up the DXMT profile, and open Steam. Retry starts from a fresh readiness scan, so successful work is not repeated.
- `winetricks.py`: Winetricks invocation.
- `scanner.py`: local game folder signal detection.
- `advisor.py`: rule-based dependency recommendations from scanner signals.

### Secondary UI

- `webui.py`: simple local browser frontend. This predates the richer SwiftUI product but remains useful for quick manual operation and backend debugging.
- `gui.py`: thin GUI/browser launcher glue.

## Current Data Flow

### Steam Library Discovery

1. `list-games` enumerates all managed bottles and includes the currently selected external prefix.
2. Each bottle's primary `steamapps` directory and `libraryfolders.vdf` references are normalized to host paths.
3. Physical libraries are deduplicated by resolved path and assigned a stable hashed ID.
4. `appmanifest_*.acf` records are validated against `steamapps/common`; stale and duplicate locations remain diagnostic registry entries.
5. The registry is atomically replaced at `~/Library/Application Support/MySteamWine/steam-libraries.json`.
6. SwiftUI receives one preferred installed location per AppID. This phase never edits Steam configuration.

### Steam Library Attachment

1. A ready managed profile requests one or more stable library IDs, or all canonical libraries.
2. The backend refuses external targets, missing Steam installations, and profile bottles whose Steam process is running.
3. A per-bottle file lock serializes attachment jobs.
4. Existing VDF entries are preserved; new host libraries are added as Wine `Z:` paths without copying game content.
5. The original `libraryfolders.vdf` receives a timestamped backup, the replacement is atomic, and parsed host paths are verified after writing.
6. Only the target profile's Steam configuration changes. Its prefix, graphics payload, shader cache, and logs remain independent from every other profile.

### Setup Flow

1. SwiftUI calls `BackendBridge.executeStreaming(.setupMetal, context: ...)`.
2. The bridge runs `python3 mysteamwine.py ... --jsonl setup-metal --dxmt-source ... --no-wait`.

### Jobs, rollback, and repair

- JSONL remains the live event transport, while `jobs.py` persists long-running
  operations independently of the SwiftUI process.
- Read-only refresh commands remain transient and do not fill job history.
- Profile setup records step progress and treats the bottle as a transaction.
  Newly created incomplete bottles are rolled back; existing bottles are kept
  and marked `needs-repair`.
- `repair-compatibility-profile` resumes the pinned setup, reruns verification,
  and only marks the manifest ready after all required probes pass.
- SwiftUI reloads durable jobs on startup and exposes cancellation and repair
  without requiring users to inspect terminal output.
3. `cli.py` emits JSONL job/step/result events.
4. Python creates or reuses the bottle, runs Wine setup, installs Steam via Winetricks, installs DXMT, and opens Steam.
5. SwiftUI merges structured steps into the setup result and updates active/recent jobs.

### Steam Library Refresh

1. SwiftUI calls `.listGames`.
2. Python reads Steam `libraryfolders.vdf` and `appmanifest_*.acf` files under the selected prefix.
3. Python returns `data.games`.
4. Swift maps those games into `LibraryGame` values and enriches them with local Steam metadata when available.

### Launch Flow

1. SwiftUI chooses macOS, Wine, or Steam launch behavior based on `LibraryGame.runner`.
2. Steam games use per-game settings to choose either:
   - `smart-launch-game` for direct executable launch attempts, or
   - `launch-game` through Windows Steam.
3. Wine games use `debug-game --exe`.
4. Python writes logs to the selected bottle/external-prefix log folder.
5. SwiftUI shows bounded log tails in the log viewer.

## Organization Assessment

The current structure is healthy enough for the next feature phase:

- Python backend responsibilities are separated by domain.
- Swift/Python communication is centralized in `BackendBridge`.
- Managed bottle and external-prefix paths have a single source of truth in Python and a matching path model in Swift.
- Structured JSON/JSONL already exists and should be extended instead of replaced.

The largest organization risk is `AppViewModel.swift`; it currently mixes library persistence, backend orchestration, runtime detection, launch policy, health checks, and log viewing. That is acceptable for early iteration, but any hidden-Steam work should avoid adding large protocol/auth/shim state there.

## Where Hidden Windows Steam Fits

The cleaner Steam experience should be introduced as backend capabilities with small Swift controls:

1. Add a `SteamLaunchMode` setting in Swift:
   - `throughSteam`
   - `directIfSafe`
   - later: `steamShimExperimental`
2. Keep direct executable detection and launch in Python.
3. Add any Steam protocol/depot/cloud helper as a separate backend module or helper process, not inside SwiftUI.
4. Keep the first version conservative:
   - direct launch installed games
   - fallback to Windows Steam
   - clear UI status when a game appears to require Steam
5. Treat Steam API shim work as a later experimental backend subsystem with explicit docs, restore paths, and per-game opt-in.

Recommended future Python modules if this grows:

- `steam_metadata.py`: appinfo, launch config, manifest/depot metadata.
- `steam_direct.py`: direct launch eligibility and executable selection.
- `steam_protocol.py`: Steam login/session/depot helper integration.
- `steam_cloud.py`: cloud save pull/push lifecycle.
- `steam_shim.py`: Steam API shim preparation, config generation, backup/restore.

## Development Rules Of Thumb

- Keep `mysteamwine.py` terminal workflows working.
- Prefer adding structured JSON fields over parsing new human text in Swift.
- Keep Wine process execution in `runtime.py`.
- Keep per-graphics file and override logic in the graphics modules.
- Keep launch policy explicit: direct launch, Steam launch, and future shim launch should be distinct modes.
- Add safety rails before mutating installed game folders, especially for any future Steam API DLL replacement or shim experiment.
