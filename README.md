# Windows-Steam-Wrapper-for-macOS

`mysteamwine.py` is a Python CLI for managing a Wine bottle dedicated to Steam on macOS.

The repo now also contains an initial native macOS frontend scaffold in SwiftUI under `Sources/SteamWineApp/`.

Current module layout:

- `mysteamwine/runtime.py`: shared process execution, downloads, executable resolution
- `mysteamwine/bottle.py`: bottle paths under `~/Library/Application Support/MySteamWine/`
- `mysteamwine/winetricks.py`: winetricks integration
- `mysteamwine/dxmt.py`: DXMT install from a local directory or `.tar.gz`
- `mysteamwine/dxvk.py`: DXVK install from a local directory or `.tar.gz`, including `DXVK-macOS`
- `mysteamwine/steam.py`: Steam installer/runner and manifest parsing
- `mysteamwine/scanner.py`: game folder scanner
- `mysteamwine/advisor.py`: rule-based dependency recommendations

Basic usage:

```bash
# open the local browser frontend
python3 mysteamwine.py gui
python3 mysteamwine.py gui --no-browser

# show environment and bottle paths
python3 mysteamwine.py info

# initialize a managed bottle
python3 mysteamwine.py --wine64 /opt/homebrew/bin/wine init

# download and install Steam
python3 mysteamwine.py --wine64 /opt/homebrew/bin/wine install-steam

# launch Steam
python3 mysteamwine.py --wine64 /opt/homebrew/bin/wine run-steam

# open winecfg for the current bottle or prefix
python3 mysteamwine.py --wine64 /opt/homebrew/bin/wine winecfg

# check runtime/prefix/DXMT/Steam health
python3 mysteamwine.py --wine /opt/homebrew/bin/wine doctor

# apply safe fixes like DXMT overrides, then rerun checks
python3 mysteamwine.py --wine /opt/homebrew/bin/wine doctor --fix
python3 mysteamwine.py --wine /opt/homebrew/bin/wine doctor --fix --dxmt-source ~/Downloads/dxmt

# list installed Steam games from manifests
python3 mysteamwine.py list-games

# use an existing Wine prefix directly instead of a managed bottle
python3 mysteamwine.py --prefix ~/.wine-bluearchive info
python3 mysteamwine.py --prefix ~/.wine-bluearchive list-games

# launch a game by Steam AppID
python3 mysteamwine.py --wine64 /opt/homebrew/bin/wine launch-game --appid 620
```

Dependency tools:

```bash
# install winetricks verbs into the bottle
python3 mysteamwine.py winetricks --verbs vcrun2019,d3dx9

# install DXVK from a local release archive or extracted folder
python3 mysteamwine.py install-dxvk --dxvk-source ~/Downloads/dxvk-2.3.tar.gz

# install Gcenx/DXVK-macOS from a local checkout or extracted folder
python3 mysteamwine.py install-dxvk --dxvk-source ~/Downloads/DXVK-macOS --dxvk-flavor macos

# install DXMT from a local checkout or extracted folder
python3 mysteamwine.py --wine /opt/homebrew/bin/wine install-dxmt --dxmt-source ~/Downloads/dxmt

# one-shot Metal setup for a managed bottle: wineboot + winetricks steam + DXMT + open Steam
python3 mysteamwine.py --wine /opt/homebrew/bin/wine setup-metal --dxmt-source ~/Downloads/dxmt

# advanced path: reuse an existing external Wine prefix instead of a managed bottle
python3 mysteamwine.py --prefix ~/.wine-bluearchive --wine /opt/homebrew/bin/wine setup-metal --dxmt-source ~/Downloads/dxmt

# wipe every bottle under MySteamWine app support
python3 mysteamwine.py wipe-bottles --yes

# inspect whether Wine, winetricks, DXMT, Steam, and manifests are in the expected state
python3 mysteamwine.py --wine /opt/homebrew/bin/wine doctor
python3 mysteamwine.py --prefix ~/.wine-bluearchive --wine /opt/homebrew/bin/wine doctor
python3 mysteamwine.py --prefix ~/.wine-bluearchive --wine /opt/homebrew/bin/wine doctor --fix

# scan a game folder and get rule-based recommendations
python3 mysteamwine.py advise-game --appid 2056220
python3 mysteamwine.py scan-game --path "/path/to/game"
```

Host dependencies still need to exist on the Mac side, for example Wine, winetricks, and Vulkan loader/tools where required by the chosen Wine build.

`setup-metal` now treats a managed bottle under `~/Library/Application Support/MySteamWine/bottles/` as the default product path. `--prefix` remains available as an advanced override for importing or reusing an external prefix.

`setup-metal` is tuned for `Wine Stable 11.0`. The CLI will detect the Wine app/version you pass and warn if it does not look like that stack.

Graphics backend defaults are now split intentionally:
- `run-steam` defaults to plain Wine (`--graphics-backend auto` resolves to `none`)
- `launch-game` and `debug-game` default to DXMT (`--graphics-backend auto` resolves to `dxmt`)

The `gui` command opens a simple local browser frontend for:
- choosing a managed bottle or external prefix
- running `setup-metal`
- running `doctor` / `doctor --fix`
- opening Steam
- refreshing the Steam game list
- launching a selected game

## SwiftUI frontend

There is now a native SwiftUI app scaffold focused on:
- `macOS`
- `Steam`
- `Wine`

with sidebar placeholders for:
- `Epic Games`
- `GOG`

Files:
- `Package.swift`
- `Sources/SteamWineApp/SteamWineApp.swift`
- `Sources/SteamWineApp/ContentView.swift`
- `Sources/SteamWineApp/AppViewModel.swift`
- `Sources/SteamWineApp/Models.swift`
- `Sources/SteamWineApp/BackendBridge.swift`

Open it in Xcode from the repo root with either:

```bash
open Package.swift
```

or:

```bash
xed .
```

The current SwiftUI app now starts that backend bridge work. The native frontend is wired to the Python CLI for:
- `setup-metal`
- `doctor`
- `doctor --fix`
- `run-steam --no-wait`
- `list-games`
- `launch-game --no-wait`

The Steam library view no longer depends on sample Steam cards. It now uses `list-games` to detect installed Steam titles from manifests and shows an empty state when nothing is detected yet.

It now also includes a SwiftUI settings sheet for:
- Wine path
- DXMT source path
- managed bottle vs external prefix
- native file pickers for Wine, DXMT, and external prefix selection
- a lightweight "Test Settings" pass before saving
- persistence through `UserDefaults`

The next step is polishing that settings flow with richer validation and then exposing more of the Python backend state directly in the SwiftUI app.
