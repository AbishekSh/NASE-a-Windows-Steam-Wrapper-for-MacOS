from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from .bottle import Bottle, ensure_bottle_dirs
from .runtime import run_logged


UPSTREAM_DXVK_DLL_OVERRIDES = ("d3d9", "d3d10core", "d3d11", "dxgi")
MACOS_DXVK_DLL_OVERRIDES = ("d3d10core", "d3d11")


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


def _upsert_user_reg_section(user_reg: Path, section: str, entries: dict[str, str]) -> None:
    lines = user_reg.read_text(encoding="utf-8", errors="replace").splitlines()
    header = f"[{section}]"
    start = None
    end = None

    for index, line in enumerate(lines):
        if line == header:
            start = index
            end = len(lines)
            for cursor in range(index + 1, len(lines)):
                if lines[cursor].startswith("[") and lines[cursor].endswith("]"):
                    end = cursor
                    break
            break

    section_lines = [header]
    for key, value in entries.items():
        section_lines.append(f'"{key}"="{value}"')

    if start is None:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(section_lines)
    else:
        existing: dict[str, str] = {}
        preserved: list[str] = []
        for line in lines[start + 1 : end]:
            if line.startswith('"') and '"="' in line and line.endswith('"'):
                key = line.split('"', 2)[1]
                existing[key] = line
            else:
                preserved.append(line)

        merged = preserved + [f'"{key}"="{value}"' for key, value in entries.items()]
        lines[start:end] = [header, *merged]

    user_reg.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _select_overrides(dxvk_flavor: str, without_dxgi: bool) -> tuple[str, ...]:
    if dxvk_flavor == "macos":
        return MACOS_DXVK_DLL_OVERRIDES
    return tuple(name for name in UPSTREAM_DXVK_DLL_OVERRIDES if not (without_dxgi and name == "dxgi"))


def _enable_dxvk_overrides(bottle: Bottle, *, dxvk_flavor: str, without_dxgi: bool) -> None:
    overrides = {name: "native" for name in _select_overrides(dxvk_flavor, without_dxgi)}
    _upsert_user_reg_section(
        bottle.prefix / "user.reg",
        r"Software\\Wine\\DllOverrides",
        overrides,
    )


def _copy_dxvk_payload(*, dxvk_root: Path, bottle: Bottle, dxvk_flavor: str, without_dxgi: bool) -> tuple[int, str]:
    if (dxvk_root / "x64").is_dir() and (dxvk_root / "x32").is_dir():
        x64_dir = dxvk_root / "x64"
        x32_dir = dxvk_root / "x32"
    elif (dxvk_root / "x86_64-windows").is_dir() and (dxvk_root / "i386-windows").is_dir():
        x64_dir = dxvk_root / "x86_64-windows"
        x32_dir = dxvk_root / "i386-windows"
    else:
        x64_dir = dxvk_root / "x64"
        x32_dir = dxvk_root / "x32"
    if not x64_dir.is_dir() or not x32_dir.is_dir():
        raise FileNotFoundError(
            "DXVK directory must contain either setup_dxvk.sh, x32/ and x64/, "
            f"or i386-windows/ and x86_64-windows/: {dxvk_root}"
        )

    system32 = bottle.drive_c / "windows" / "system32"
    syswow64 = bottle.drive_c / "windows" / "syswow64"
    system32.mkdir(parents=True, exist_ok=True)
    syswow64.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for source_dir, target_dir in ((x64_dir, system32), (x32_dir, syswow64)):
        for dll in sorted(source_dir.glob("*.dll")):
            destination = target_dir / dll.name
            shutil.copy2(dll, destination)
            copied.append(str(destination))

    _enable_dxvk_overrides(bottle, dxvk_flavor=dxvk_flavor, without_dxgi=without_dxgi)
    return 0, "\n".join(copied)


def install_dxvk(
    *,
    bottle: Bottle,
    dxvk_source: Path,
    dxvk_flavor: str = "upstream",
    use_symlinks: bool = False,
    without_dxgi: bool = False,
) -> tuple[int, str]:
    ensure_bottle_dirs(bottle)
    dxvk_root = resolve_dxvk_root(dxvk_source, bottle.cache / "dxvk")
    try:
        setup_script = find_setup_script(dxvk_root)
    except FileNotFoundError:
        if use_symlinks:
            raise
        return _copy_dxvk_payload(
            dxvk_root=dxvk_root,
            bottle=bottle,
            dxvk_flavor=dxvk_flavor,
            without_dxgi=without_dxgi,
        )

    command = ["/bin/bash", str(setup_script), "install"]
    if use_symlinks:
        command.append("--symlink")
    if without_dxgi:
        command.append("--without-dxgi")

    code, tail = run_logged(
        cmd=command,
        env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
        log_file=bottle.logs / "dxvk_install.log",
        cwd=dxvk_root,
    )
    if code == 0:
        _enable_dxvk_overrides(bottle, dxvk_flavor=dxvk_flavor, without_dxgi=without_dxgi)
    return code, tail
