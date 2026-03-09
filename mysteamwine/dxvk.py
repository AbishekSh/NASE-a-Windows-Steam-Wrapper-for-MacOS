from __future__ import annotations

import tarfile
from pathlib import Path

from .bottle import Bottle, ensure_bottle_dirs
from .runtime import run_logged


def _extract_archive(archive: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as handle:
        members = handle.getmembers()
        top_levels = {member.name.split("/", 1)[0] for member in members if member.name}
        handle.extractall(target_dir)
    if len(top_levels) == 1:
        return target_dir / next(iter(top_levels))
    return target_dir


def resolve_dxvk_root(source: Path, cache_dir: Path) -> Path:
    candidate = source.expanduser().resolve()
    if candidate.is_dir():
        return candidate
    if candidate.is_file() and candidate.suffixes[-2:] == [".tar", ".gz"]:
        return _extract_archive(candidate, cache_dir / candidate.stem.replace(".tar", ""))
    raise FileNotFoundError(f"DXVK source must be a directory or .tar.gz archive: {candidate}")


def find_setup_script(dxvk_root: Path) -> Path:
    for candidate in (dxvk_root / "setup_dxvk.sh", dxvk_root / "setup-dxvk.sh"):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not find setup_dxvk.sh under: {dxvk_root}")


def install_dxvk(
    *,
    bottle: Bottle,
    dxvk_source: Path,
    use_symlinks: bool = False,
    without_dxgi: bool = False,
) -> tuple[int, str]:
    ensure_bottle_dirs(bottle)
    dxvk_root = resolve_dxvk_root(dxvk_source, bottle.cache / "dxvk")
    setup_script = find_setup_script(dxvk_root)

    command = ["/bin/bash", str(setup_script), "install"]
    if use_symlinks:
        command.append("--symlink")
    if without_dxgi:
        command.append("--without-dxgi")

    return run_logged(
        cmd=command,
        env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
        log_file=bottle.logs / "dxvk_install.log",
        cwd=dxvk_root,
    )
