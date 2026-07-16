from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

from .d3dmetal import locate_d3dmetal_payload


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
    payload = locate_d3dmetal_payload(source)
    root = _installation_root(wine, payload)
    if root is None:
        raise RuntimeError("GPTK Wine and D3DMetal do not appear to come from the same Toolkit installation.")
    try:
        result = subprocess.run([str(wine), "--version"], capture_output=True, text=True, timeout=10, check=False)
    except OSError as exc:
        raise RuntimeError(f"Could not run GPTK Wine at {wine}: {exc}") from exc
    version = (result.stdout or result.stderr).strip()
    if result.returncode != 0 or not version:
        raise RuntimeError(f"Could not identify GPTK Wine at {wine}.")
    return {
        "installation_root": str(root),
        "wine_path": str(wine),
        "wine_version": version,
        "d3dmetal_source": str(source),
        "payload_path": str(payload),
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
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for wine, source in pairs:
        try:
            item = inspect_gptk_installation(wine, source)
        except (OSError, RuntimeError, FileNotFoundError):
            continue
        key = (item["wine_path"], item["payload_path"])
        if key not in seen:
            seen.add(key)
            found.append(item)
    return found
