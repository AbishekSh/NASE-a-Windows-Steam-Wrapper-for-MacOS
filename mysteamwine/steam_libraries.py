from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
import uuid

from .bottle import Bottle, app_support_root, bottle_paths, list_bottle_roots
from .steam import parse_vdf_file, steamapps_dirs


SCHEMA_VERSION = 1


def registry_path() -> Path:
    return app_support_root() / "steam-libraries.json"


def _library_id(path: Path) -> str:
    return "library_" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]


def _normalized(path: Path) -> Path:
    expanded = path.expanduser()
    try:
        return expanded.resolve(strict=False)
    except OSError:
        return expanded.absolute()


def _managed_bottles(current: Bottle) -> list[Bottle]:
    bottles = [bottle_paths(root.name) for root in list_bottle_roots()]
    if all(_normalized(item.root) != _normalized(current.root) for item in bottles):
        bottles.append(current)
    return sorted(bottles, key=lambda bottle: (bottle.name.lower(), str(bottle.prefix)))


def _manifest_location(manifest: Path, steamapps: Path, library_id: str, bottle_name: str) -> dict[str, Any] | None:
    try:
        parsed = parse_vdf_file(manifest)
    except (OSError, ValueError):
        return None
    app_state = parsed.get("AppState", parsed)
    if not isinstance(app_state, dict):
        return None
    appid = str(app_state.get("appid") or manifest.stem.replace("appmanifest_", ""))
    name = str(app_state.get("name") or appid)
    install_dir_name = str(app_state.get("installdir") or name)
    install_dir = _normalized(steamapps / "common" / install_dir_name)
    installed = install_dir.is_dir()
    return {
        "appid": appid,
        "name": name,
        "library_id": library_id,
        "install_dir": str(install_dir),
        "manifest_path": str(_normalized(manifest)),
        "state": "installed" if installed else "missing-files",
        "state_flags": str(app_state.get("StateFlags") or app_state.get("stateflags") or ""),
        "seen_from_bottle": bottle_name,
    }


def discover_steam_libraries(current: Bottle) -> dict[str, Any]:
    libraries: dict[str, dict[str, Any]] = {}
    locations_by_app: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []

    for bottle in _managed_bottles(current):
        try:
            directories = steamapps_dirs(bottle)
        except (OSError, ValueError) as exc:
            warnings.append(f"Could not read Steam libraries for {bottle.name}: {exc}")
            continue
        for steamapps in directories:
            normalized_steamapps = _normalized(steamapps)
            library_root = normalized_steamapps.parent
            library_id = _library_id(library_root)
            entry = libraries.setdefault(
                library_id,
                {
                    "library_id": library_id,
                    "path": str(library_root),
                    "steamapps_path": str(normalized_steamapps),
                    "exists": normalized_steamapps.is_dir(),
                    "writable": normalized_steamapps.is_dir() and os.access(normalized_steamapps, os.W_OK),
                    "referenced_by": [],
                },
            )
            reference = {
                "bottle": bottle.name,
                "prefix": str(_normalized(bottle.prefix)),
                "source": "libraryfolders.vdf" if normalized_steamapps != _normalized(bottle.drive_c / "Program Files (x86)" / "Steam" / "steamapps") else "primary",
            }
            if reference not in entry["referenced_by"]:
                entry["referenced_by"].append(reference)
            if not normalized_steamapps.is_dir():
                continue
            for manifest in sorted(normalized_steamapps.glob("appmanifest_*.acf")):
                location = _manifest_location(manifest, normalized_steamapps, library_id, bottle.name)
                if location is None:
                    warnings.append(f"Could not parse Steam manifest: {manifest}")
                    continue
                locations_by_app.setdefault(location["appid"], []).append(location)

    apps: list[dict[str, Any]] = []
    for appid, locations in locations_by_app.items():
        unique_locations = list({(item["manifest_path"], item["install_dir"]): item for item in locations}.values())
        unique_locations.sort(
            key=lambda item: (
                item["state"] != "installed",
                not libraries[item["library_id"]]["writable"],
                item["install_dir"].lower(),
            )
        )
        preferred = unique_locations[0]
        apps.append(
            {
                "appid": appid,
                "name": preferred["name"],
                "state": preferred["state"],
                "preferred_location": preferred,
                "locations": unique_locations,
            }
        )

    apps.sort(key=lambda app: (app["name"].lower(), app["appid"]))
    for library in libraries.values():
        library["referenced_by"].sort(key=lambda item: (item["bottle"].lower(), item["prefix"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": time.time(),
        "libraries": sorted(libraries.values(), key=lambda item: item["path"].lower()),
        "apps": apps,
        "warnings": warnings,
    }


def save_registry(registry: dict[str, Any]) -> Path:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def refresh_registry(current: Bottle) -> dict[str, Any]:
    registry = discover_steam_libraries(current)
    save_registry(registry)
    return registry


def installed_games(registry: dict[str, Any]) -> list[dict[str, str]]:
    games: list[dict[str, str]] = []
    for app in registry.get("apps", []):
        preferred = app.get("preferred_location", {})
        if preferred.get("state") != "installed":
            continue
        games.append(
            {
                "appid": str(app.get("appid") or ""),
                "name": str(app.get("name") or app.get("appid") or "Unknown"),
                "install_dir": str(preferred.get("install_dir") or ""),
                "library_id": str(preferred.get("library_id") or ""),
            }
        )
    return games
