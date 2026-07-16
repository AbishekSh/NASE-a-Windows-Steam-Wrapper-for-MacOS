from __future__ import annotations

import os
import hashlib
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .d3dmetal import inspect_d3dmetal_bundle
from .bottle import app_support_root


SUPPORTED_D3DMETAL_WINE_VERSIONS = ("wine-9.0 (SikarugirCX 24.0.7)",)


def _candidate_roots() -> list[Path]:
    roots = [
        Path("/Applications/Game Porting Toolkit.app/Contents/Resources"),
        Path("/opt/local/libexec/game-porting-toolkit"),
        Path("/usr/local/opt/game-porting-toolkit"),
        Path("/opt/homebrew/opt/game-porting-toolkit"),
    ]
    volumes = Path("/Volumes")
    try:
        roots.extend(path for path in volumes.glob("Game Porting Toolkit*") if path.is_dir())
    except OSError:
        pass
    return roots


def _wine_candidates(root: Path) -> list[Path]:
    return [
        root / "bin" / "wine64",
        root / "bin" / "wine",
        root / "wine" / "bin" / "wine64",
        root / "wine" / "bin" / "wine",
        root / "game-porting-toolkit" / "bin" / "wine64",
        root / "game-porting-toolkit" / "bin" / "wine",
    ]


def _installation_root(wine_path: Path, payload_root: Path) -> Path | None:
    wine = wine_path.expanduser().resolve(strict=False)
    payload = payload_root.expanduser().resolve(strict=False)
    try:
        common = Path(os.path.commonpath([wine, payload]))
    except ValueError:
        return None
    normalized_common = str(common).lower().replace("_", "-")
    if "game-porting-toolkit" not in normalized_common and "game porting toolkit" not in normalized_common:
        return None
    return common


def inspect_gptk_installation(wine_path: Path, d3dmetal_source: Path) -> dict[str, Any]:
    wine = wine_path.expanduser().resolve(strict=False)
    source = d3dmetal_source.expanduser().resolve(strict=False)
    if not wine.is_file() or not os.access(wine, os.X_OK):
        raise RuntimeError(f"GPTK Wine is not executable: {wine}")
    bundle = inspect_d3dmetal_bundle(source)
    try:
        result = subprocess.run([str(wine), "--version"], capture_output=True, text=True, timeout=10, check=False)
    except OSError as exc:
        raise RuntimeError(f"Could not run GPTK Wine at {wine}: {exc}") from exc
    version = (result.stdout or result.stderr).strip()
    if result.returncode != 0 or not version:
        raise RuntimeError(f"Could not identify GPTK Wine at {wine}.")
    if version not in SUPPORTED_D3DMETAL_WINE_VERSIONS:
        supported = ", ".join(SUPPORTED_D3DMETAL_WINE_VERSIONS)
        raise RuntimeError(f"D3DMetal requires a tested Wine engine ({supported}); found {version}.")
    root = _installation_root(wine, bundle.root) or bundle.root
    return {
        "installation_root": str(root),
        "wine_path": str(wine),
        "wine_version": version,
        "d3dmetal_source": str(bundle.root),
        "payload_path": str(bundle.windows_dir),
        "framework_path": str(bundle.framework_binary),
        "shared_library_path": str(bundle.shared_library),
    }


def discover_gptk_installations(
    *, configured_wine: Path | None = None, configured_source: Path | None = None
) -> list[dict[str, Any]]:
    pairs: list[tuple[Path, Path]] = []
    if configured_wine and configured_source:
        pairs.append((configured_wine, configured_source))
    for root in _candidate_roots():
        if not root.exists():
            continue
        for wine in _wine_candidates(root):
            if wine.is_file():
                pairs.append((wine, root))
    home = Path.home()
    wrapper_roots = list((home / "Applications" / "Sikarugir").glob("*.app/Contents"))
    wrapper_roots += list((home / "Library/Application Support/Sikarugir/Wrapper").glob("*.app/Contents"))
    for contents in wrapper_roots:
        wine = contents / "SharedSupport" / "wine" / "bin" / "wine"
        renderer = contents / "Frameworks" / "renderer" / "d3dmetal"
        if wine.is_file() and renderer.is_dir():
            pairs.append((wine, renderer))
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for wine, source in pairs:
        try:
            item = inspect_gptk_installation(wine, source)
        except (OSError, RuntimeError, FileNotFoundError):
            continue
        key = (item["wine_path"], item["d3dmetal_source"])
        if key not in seen:
            seen.add(key)
            found.append(item)
    return found


def import_managed_gptk(
    *, wine_path: Path, d3dmetal_source: Path, confirm_license: bool = False
) -> dict[str, Any]:
    if not confirm_license:
        raise RuntimeError("Importing Game Porting Toolkit requires explicit acceptance of Apple's license.")
    inspected = inspect_gptk_installation(wine_path, d3dmetal_source)
    source_wine = Path(inspected["wine_path"])
    source_wine_root = source_wine.parent.parent
    source_bundle = inspect_d3dmetal_bundle(Path(inspected["d3dmetal_source"]))
    identity = hashlib.sha256(
        f"{source_wine_root}|{inspected['wine_version']}|{source_bundle.root}".encode("utf-8")
    ).hexdigest()[:12]
    destination = app_support_root() / "runtimes" / "gptk" / f"game-porting-toolkit-{identity}"
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True)
        shutil.copytree(source_wine_root, temporary / "wine", symlinks=True)
        shutil.copytree(source_bundle.root, temporary / "d3dmetal", symlinks=True)
        temporary.replace(destination)
    managed_wine = destination / "wine" / "bin" / source_wine.name
    managed_bundle = destination / "d3dmetal"
    managed = inspect_gptk_installation(managed_wine, managed_bundle)
    managed["managed"] = True
    managed["source_root"] = str(Path(inspected["installation_root"]))
    return managed
