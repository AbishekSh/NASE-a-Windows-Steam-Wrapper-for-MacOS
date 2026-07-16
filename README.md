# SteamWineWrapper

SteamWineWrapper is a native macOS game launcher for Steam, Wine-managed Windows apps, and native macOS apps. The goal is a library-first experience closer to Lutris than a thin Wine wrapper: games stay front and center, while Wine setup, logs, dependencies, and per-game overrides live in focused tools.

The SwiftUI app is the product. The Python backend remains the implementation engine for Wine, Steam, graphics stack setup, diagnostics, and launch workflows.

## Current Focus

- Native SwiftUI macOS launcher
- Steam library detection and launch through managed Wine bottles
- Wine-managed Windows apps and installers
- Native macOS app imports
- Per-game settings, logs, health checks, and compatibility notes

Planned sources include Epic Games and GOG.

## Open The App

From the repo root:

```bash
open Package.swift
```

or:

```bash
xed .
```

Then run the `SteamWineApp` target from Xcode.

For a command-line build check:

```bash
swift build
```

## Host Requirements

Install these on the Mac side before first setup:

- `wine-stable 11.0` recommended
- `winetricks`
- Rosetta 2 on Apple Silicon
- GStreamer.framework when using managed Gcenx Wine builds
- D3DMetal payloads as needed by the graphics mode you choose

Settings → System Readiness checks these dependencies using structured backend results. Required DXMT components are separated from optional GPTK support, and every missing required component includes a suggested fix.

Missing dependencies now expose explicit **Fix** actions. Python, Wine Stable, and Winetricks installations show the exact Homebrew-backed operation before running; after installing Python, NASE automatically selects Homebrew's supported `python3` instead of continuing to use an outdated Xcode Python. Rosetta requires a separate confirmation that accepts Apple's software license, and DXMT continues through the checksum-verified Runtime Center installer. Readiness checks themselves remain read-only.

The **Recommended Gaming Environment** action completes the full bootstrap in dependency order. It installs only missing required components, automatically selects Wine Stable and the verified DXMT source, rescans before continuing, creates the dedicated `-DXMT` profile bottle, installs Steam, and opens Steam for sign-in. A failed run keeps completed work, shows the failing step, and can be retried after opening the profile-specific logs.

The app now includes an early Runtime Center in Settings for managed Wine, DXVK, and DXMT installs. The first catalog includes pinned upstream releases with checksums, so the launcher can download, verify, extract, and register/install them without manual linking.

Graphics choices are compatibility profiles rather than DLL toggles. DXMT uses Wine Stable 11 and DXMT 0.71 in a dedicated `-DXMT` bottle; D3DMetal uses GPTK Wine and its matching D3DMetal payload in a dedicated `-D3DMetal` bottle. DXVK-macOS remains visibly unavailable until NASE has a complete pinned Wine/winevulkan/MoltenVK/DXVK-macOS bundle. Each profile bottle stores `compatibility-profile.json` and refuses silent runtime or graphics-source drift.

D3DMetal setup is available from Settings → Compatibility Profiles. **Find GPTK** searches standard app, package-manager, and mounted-volume locations and only adopts Wine/D3DMetal paths proven to belong to the same Game Porting Toolkit installation. **Set Up** creates the dedicated bottle, installs Steam and the bundled D3DMetal payload, attaches shared libraries, and verifies the required DLLs, overrides, and Steam installation before marking the profile ready. Once ready, **Repair** reruns those idempotent installation and verification steps. Apple’s Toolkit must be installed or mounted first because its distribution and license acceptance remain outside NASE.

Profiles can be prepared from Settings → Compatibility Profiles. The backend equivalent is:

```bash
python3 mysteamwine.py --json discover-d3dmetal

python3 mysteamwine.py --bottle Default-DXMT --wine /opt/homebrew/bin/wine --jsonl \
  setup-compatibility-profile --profile dxmt-wine-stable-11-v1 \
  --dxmt-source "$HOME/Library/Application Support/MySteamWine/runtimes/dxmt/dxmt-0.71"

python3 mysteamwine.py --bottle Default-D3DMetal --wine /path/to/gptk/bin/wine --jsonl \
  setup-compatibility-profile --profile d3dmetal-gptk-v1 \
  --d3dmetal-source "/path/to/the/same/Game Porting Toolkit"
```

Setup initializes the dedicated prefix, selects Windows 10, installs Steam and the matching renderer, and marks the profile ready only after every step succeeds.

The default managed Wine prefix location is:

```text
~/Library/Application Support/MySteamWine
```

Managed bottles live under:

```text
~/Library/Application Support/MySteamWine/bottles/<BottleName>
```

External Wine prefixes are also supported. The prefix itself stays external, while SteamWineWrapper stores logs, downloads, and cache metadata under `MySteamWine/external-prefixes/`.

## What The App Does Today

The native SwiftUI app can:

- Manage Steam, Wine, macOS, and pinned library views
- Configure Wine path, DXMT source, DXVK source, D3DMetal source, managed bottle, and external prefix
- Install managed Wine, DXVK, and DXMT runtime builds from Settings
- Run first-time Metal setup
- Run doctor checks and safe repair actions
- Open Windows Steam without waiting for it to exit
- Detect installed Steam games from Steam manifests
- Launch Steam games through Steam or direct debug/smart launch paths
- Import native macOS apps
- Import Wine installers and app folders
- Edit per-game launch arguments, working directory, environment variables, graphics backend, collection, bottle, and external prefix
- View bounded log tails in-app
- Run Winetricks from the UI
- Track game launch sessions, reconcile real process state, and stop one running game without shutting down shared Steam

Graphics runtimes are not interchangeable DLL packs. DXMT is the validated default with Wine Stable 11. D3DMetal uses a separate Game Porting Toolkit Wine context and bottle. DXVK remains experimental on macOS because it additionally requires a compatible Wine Vulkan and MoltenVK host stack; installing the upstream DXVK DLL archive alone is not sufficient.

The current Steam experience still uses Windows Steam as the reliable baseline. Direct launch and hidden-Steam style work should build on the existing backend boundaries described in the architecture docs.

Steam library refresh is now bottle-independent. The backend reads `libraryfolders.vdf` from every managed bottle plus the currently selected external prefix, normalizes and deduplicates library paths, validates manifests against `steamapps/common`, and atomically writes:

```text
~/Library/Application Support/MySteamWine/steam-libraries.json
```

The registry retains stale manifests and duplicate physical locations for diagnostics, while the normal game list exposes one preferred installed location per AppID. Registered paths continue to be scanned even when the active profile did not create them, and launch/debug resolution uses the canonical manifest and install path instead of re-scanning only the selected prefix. Discovery is read-only: it does not edit Steam's `libraryfolders.vdf` or move game files.

Ready compatibility profiles can attach those canonical libraries from Settings → Compatibility Profiles. NASE registers each host library as a Wine `Z:` path in only that profile's `libraryfolders.vdf`; game files remain in their original location while prefixes, renderer DLLs, shader caches, Steam configuration, and logs remain isolated. The target Steam client must be closed. NASE serializes concurrent attachment attempts, creates a timestamped backup, atomically replaces the VDF, and verifies every path afterward.

NASE also keeps a persistent activity owner for each shared library. Only one profile may run Windows Steam against a library at a time, preventing two clients from updating the same files concurrently. The owning profile may launch additional games without restarting Steam; other profiles may still use direct executable launches while the shared files are idle, and a stale owner is replaced automatically after its Steam process exits.

```bash
python3 mysteamwine.py --bottle Default-DXMT --json attach-steam-library --all
```

New profile setup performs this attachment automatically after Steam and the renderer are installed.

## Architecture

High-level split:

- `Sources/SteamWineApp/`: SwiftUI product, app state, views, settings, game library, and backend bridge.
- `mysteamwine/`: Python backend for Wine, Steam, bottles, graphics installers, diagnostics, scanning, and launch commands.
- `mysteamwine.py`: thin backend CLI entrypoint.

Key Swift files:

- `SteamWineApp.swift`: app entrypoint
- `ContentView.swift`: main app shell
- `AppViewModel.swift`: primary observable app state and orchestration
- `Models.swift`: shared UI/backend value types
- `BackendBridge.swift`: Swift-to-Python JSONL bridge
- `SettingsSheet.swift`, `SetupWizardSheet.swift`, `WinetricksSheet.swift`, `GameSheets.swift`: focused tools and sheets
- `LibraryComponents.swift`, `SharedViews.swift`: reusable UI pieces

Key Python modules:

- `mysteamwine/runtime.py`: process execution, downloads, executable resolution, Wine runtime detection
- `mysteamwine/steam_libraries.py`: cross-bottle Steam library discovery and the canonical read-only registry
- `mysteamwine/catalog.py`: managed runtime catalog, downloads, checksum verification, extraction, and install records
- `mysteamwine/bottle.py`: managed bottle and external-prefix paths
- `mysteamwine/steam.py`: Steam installer/runner, VDF parsing, manifest discovery, Steam/direct game launch helpers
- `mysteamwine/cli.py`: backend command contract, JSON/JSONL output, job events
- `mysteamwine/doctor.py`: health checks and safe repairs
- `mysteamwine/winetricks.py`: Winetricks integration
- `mysteamwine/dxmt.py`: DXMT install and overrides
- `mysteamwine/dxvk.py`: DXVK install and overrides
- `mysteamwine/d3dmetal.py`: D3DMetal install and overrides
- `mysteamwine/scanner.py`: game folder signal scanner
- `mysteamwine/advisor.py`: dependency recommendations
- `mysteamwine/webui.py`: older local browser frontend for backend debugging

More detail lives in:

- [`docs/CODEBASE_STRUCTURE.md`](docs/CODEBASE_STRUCTURE.md): current SwiftUI/Python module map, data flow, organization notes, and where hidden-Steam launch work should fit.

## Backend Contract

The app talks to Python through `BackendBridge.swift`. The backend commands support structured output:

- `--json`: one machine-readable result
- `--jsonl`: streaming job events plus final result

Representative response shape:

```json
{
  "ok": true,
  "action": "doctor",
  "message": "Doctor finished.",
  "data": {},
  "warnings": [],
  "errors": [],
  "logs": []
}
```

The SwiftUI app should continue to prefer JSON/JSONL over parsing human terminal output.

## Backend CLI

The CLI is secondary now. It exists for debugging, scripting, and keeping backend workflows easy to test outside the app.

Common backend commands:

```bash
# show environment and bottle paths
python3 mysteamwine.py info

# create or initialize the default managed bottle
python3 mysteamwine.py --wine /opt/homebrew/bin/wine init

# run the managed setup flow
python3 mysteamwine.py --wine /opt/homebrew/bin/wine setup-metal --dxmt-source ~/Downloads/dxmt

# inspect the current Wine/Steam/graphics setup
python3 mysteamwine.py --wine /opt/homebrew/bin/wine doctor

# apply safe repairs, then rerun checks
python3 mysteamwine.py --wine /opt/homebrew/bin/wine doctor --fix --dxmt-source ~/Downloads/dxmt

# open Windows Steam
python3 mysteamwine.py --wine /opt/homebrew/bin/wine run-steam --no-wait

# list installed Steam games from manifests
python3 mysteamwine.py list-games

# launch a Steam game by AppID through Steam
python3 mysteamwine.py --wine /opt/homebrew/bin/wine launch-game --appid 620 --no-wait

# try direct executable launch first, then fall back to Steam
python3 mysteamwine.py --wine /opt/homebrew/bin/wine smart-launch-game --appid 620 --no-wait

# launch a chosen executable directly with debug logging
python3 mysteamwine.py --wine /opt/homebrew/bin/wine debug-game --exe "/path/to/Game.exe" --no-wait
```

Dependency and graphics helpers:

```bash
# list managed runtime catalog entries
python3 mysteamwine.py --json list-runtime-catalog

# list runtimes already installed by the launcher
python3 mysteamwine.py --json list-installed-runtimes

# download, verify, extract, and register/install a runtime
python3 mysteamwine.py --wine /opt/homebrew/bin/wine install-runtime --runtime dxmt-0.71

# install Winetricks verbs
python3 mysteamwine.py winetricks --verbs vcrun2019,d3dx9

# install DXMT
python3 mysteamwine.py --wine /opt/homebrew/bin/wine install-dxmt --dxmt-source ~/Downloads/dxmt

# install DXVK
python3 mysteamwine.py install-dxvk --dxvk-source ~/Downloads/dxvk-2.3.tar.gz

# install DXVK-macOS
python3 mysteamwine.py install-dxvk --dxvk-source ~/Downloads/DXVK-macOS --dxvk-flavor macos

# install D3DMetal
python3 mysteamwine.py --wine /opt/homebrew/bin/wine install-d3dmetal --d3dmetal-source ~/Downloads/d3dmetal

# inspect active game sessions and stop one game cleanly
python3 mysteamwine.py --json list-sessions
python3 mysteamwine.py --json stop-game --session-id launch_123

# scan a game folder and get rule-based recommendations
python3 mysteamwine.py scan-game --path "/path/to/game"
python3 mysteamwine.py advise-game --appid 2056220
```

NASE tracks whether Steam was already open when a game launched. When NASE owns
that Steam launch, it gracefully closes Steam after the last game exits and a
short sync grace period. Steam stays open when another game is active, a
download or update is in progress, or the user explicitly opened Steam. **Kill
All Wine Processes** remains the recovery option for a stuck bottle.

External prefix examples:

```bash
python3 mysteamwine.py --prefix ~/.wine-bluearchive info
python3 mysteamwine.py --prefix ~/.wine-bluearchive list-games
python3 mysteamwine.py --prefix ~/.wine-bluearchive --wine /opt/homebrew/bin/wine doctor --fix
```

The older local browser UI is still available for quick backend testing:

```bash
python3 mysteamwine.py gui
python3 mysteamwine.py gui --no-browser
```

## Graphics Defaults

Graphics backend defaults are intentionally split:

- `run-steam`: plain Wine by default. `--graphics-backend auto` resolves to `none`.
- `launch-game`, `smart-launch-game`, and `debug-game`: DXMT by default. `--graphics-backend auto` resolves to `dxmt`.

Games may use DXMT, DXVK, D3DMetal, or no override depending on compatibility.

## Development Direction

Near-term priorities:

- Keep the SwiftUI app as the primary user experience.
- Keep Python backend commands stable and terminal-friendly.
- Continue strengthening JSON/JSONL responses.
- Add hidden/cleaner Steam launch work as explicit backend launch modes, not UI hacks.
- Keep direct launch, through-Steam launch, and any future Steam API shim mode distinct and reversible.
