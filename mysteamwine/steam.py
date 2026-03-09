from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from . import DEFAULT_STEAM_WINDOWS_PATH, STEAM_SETUP_URL
from .bottle import Bottle, ensure_bottle_dirs
from .runtime import download, run_logged


@dataclass(frozen=True)
class SteamApp:
    appid: str
    name: str
    install_dir: Path
    manifest_path: Path
    library_path: Path


def steam_windows_path() -> str:
    return DEFAULT_STEAM_WINDOWS_PATH


def steam_prefix_root(bottle: Bottle) -> Path:
    return bottle.drive_c / "Program Files (x86)" / "Steam"


def steam_setup_exe(bottle: Bottle) -> Path:
    return bottle.downloads / "SteamSetup.exe"


def install_steam(*, bottle: Bottle, wine64_path: Path) -> tuple[int, str]:
    ensure_bottle_dirs(bottle)
    installer = steam_setup_exe(bottle)
    download(STEAM_SETUP_URL, installer)
    return run_logged(
        cmd=[str(wine64_path), str(installer)],
        env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
        log_file=bottle.logs / "02_install_steam.log",
    )


def run_steam(*, bottle: Bottle, wine64_path: Path, steam_path: str | None = None, extra_args: list[str] | None = None) -> tuple[int, str]:
    ensure_bottle_dirs(bottle)
    args = [str(wine64_path), steam_path or steam_windows_path()]
    if extra_args:
        args.extend(extra_args)
    return run_logged(
        cmd=args,
        env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
        log_file=bottle.logs / "03_run_steam.log",
    )


def launch_app(*, bottle: Bottle, wine64_path: Path, appid: str) -> tuple[int, str]:
    return run_steam(
        bottle=bottle,
        wine64_path=wine64_path,
        steam_path=steam_windows_path(),
        extra_args=["-applaunch", appid],
    )


def _tokenize_vdf(text: str) -> Iterator[str]:
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char.isspace():
            i += 1
            continue
        if char == "/" and i + 1 < length and text[i + 1] == "/":
            newline = text.find("\n", i)
            if newline == -1:
                break
            i = newline + 1
            continue
        if char in "{}":
            yield char
            i += 1
            continue
        if char == '"':
            i += 1
            value_chars: list[str] = []
            while i < length:
                current = text[i]
                if current == "\\" and i + 1 < length:
                    value_chars.append(text[i + 1])
                    i += 2
                    continue
                if current == '"':
                    i += 1
                    break
                value_chars.append(current)
                i += 1
            yield "".join(value_chars)
            continue
        start = i
        while i < length and not text[i].isspace() and text[i] not in "{}":
            i += 1
        yield text[start:i]


def parse_vdf_text(text: str) -> dict[str, Any]:
    tokens = list(_tokenize_vdf(text))
    position = 0

    def parse_object() -> dict[str, Any]:
        nonlocal position
        data: dict[str, Any] = {}
        while position < len(tokens):
            token = tokens[position]
            if token == "}":
                position += 1
                break
            key = token
            position += 1
            if position >= len(tokens):
                break
            value_token = tokens[position]
            if value_token == "{":
                position += 1
                data[key] = parse_object()
            else:
                data[key] = value_token
                position += 1
        return data

    return parse_object()


def parse_vdf_file(path: Path) -> dict[str, Any]:
    return parse_vdf_text(path.read_text(encoding="utf-8", errors="replace"))


def _wine_path_to_host(bottle: Bottle, raw_path: str) -> Path:
    normalized = raw_path.replace("\\\\", "\\")
    if len(normalized) >= 2 and normalized[1] == ":":
        drive = normalized[0].lower()
        suffix = normalized[2:].lstrip("\\/")
        parts = [part for part in suffix.replace("\\", "/").split("/") if part]
        if drive == "c":
            return bottle.drive_c.joinpath(*parts)
        if drive == "z":
            return Path("/").joinpath(*parts)
        return bottle.prefix / "dosdevices" / f"{drive}:" / Path(*parts)
    return Path(normalized.replace("\\", "/")).expanduser()


def steamapps_dirs(bottle: Bottle) -> list[Path]:
    primary = steam_prefix_root(bottle) / "steamapps"
    library_file = primary / "libraryfolders.vdf"
    libraries = [primary]
    if not library_file.exists():
        return libraries

    parsed = parse_vdf_file(library_file)
    root = parsed.get("libraryfolders", parsed)
    if not isinstance(root, dict):
        return libraries

    for value in root.values():
        if isinstance(value, dict):
            raw_path = value.get("path")
            if raw_path:
                path = _wine_path_to_host(bottle, str(raw_path))
                libraries.append(path / "steamapps")
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in libraries:
        normalized = path.resolve() if path.exists() else path
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(path)
    return unique


def list_installed_apps(bottle: Bottle) -> list[SteamApp]:
    apps: list[SteamApp] = []
    for steamapps in steamapps_dirs(bottle):
        if not steamapps.exists():
            continue
        for manifest in sorted(steamapps.glob("appmanifest_*.acf")):
            parsed = parse_vdf_file(manifest)
            app_state = parsed.get("AppState", parsed)
            appid = str(app_state.get("appid", manifest.stem.replace("appmanifest_", "")))
            name = str(app_state.get("name", appid))
            install_dir_name = str(app_state.get("installdir", name))
            apps.append(
                SteamApp(
                    appid=appid,
                    name=name,
                    install_dir=steamapps / "common" / install_dir_name,
                    manifest_path=manifest,
                    library_path=steamapps.parent,
                )
            )
    return apps


def find_app(bottle: Bottle, appid: str) -> SteamApp:
    for app in list_installed_apps(bottle):
        if app.appid == appid:
            return app
    raise FileNotFoundError(f"Steam app not found for AppID {appid}")
