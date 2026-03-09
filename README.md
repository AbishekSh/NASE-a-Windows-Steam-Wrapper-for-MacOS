# Windows-Steam-Wrapper-for-macOS

`mysteamwine.py` is a Python CLI for managing a Wine bottle dedicated to Steam on macOS.

Current module layout:

- `mysteamwine/runtime.py`: shared process execution, downloads, executable resolution
- `mysteamwine/bottle.py`: bottle paths under `~/Library/Application Support/MySteamWine/`
- `mysteamwine/winetricks.py`: winetricks integration
- `mysteamwine/dxvk.py`: DXVK install from a local directory or `.tar.gz`
- `mysteamwine/steam.py`: Steam installer/runner and manifest parsing
- `mysteamwine/scanner.py`: game folder scanner
- `mysteamwine/advisor.py`: rule-based dependency recommendations

Basic usage:

```bash
# show environment and bottle paths
python3 mysteamwine.py info

# initialize a bottle
python3 mysteamwine.py --wine64 /opt/local/bin/wine init

# download and install Steam
python3 mysteamwine.py --wine64 /opt/local/bin/wine install-steam

# launch Steam
python3 mysteamwine.py --wine64 /opt/local/bin/wine run-steam

# list installed Steam games from manifests
python3 mysteamwine.py list-games

# launch a game by Steam AppID
python3 mysteamwine.py --wine64 /opt/local/bin/wine launch-game --appid 620
```

Dependency tools:

```bash
# install winetricks verbs into the bottle
python3 mysteamwine.py winetricks --verbs vcrun2019,d3dx9

# install DXVK from a local release archive or extracted folder
python3 mysteamwine.py install-dxvk --dxvk-source ~/Downloads/dxvk-2.3.tar.gz

# scan a game folder and get rule-based recommendations
python3 mysteamwine.py advise-game --appid 2056220
python3 mysteamwine.py scan-game --path "/path/to/game"
```

Host dependencies still need to exist on the Mac side, for example Wine, winetricks, and Vulkan loader/tools where required by the chosen Wine build.
