from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from .bottle import Bottle, ensure_bottle_dirs


DXMT_DLL_OVERRIDES = {
    "dxgi": "native,builtin",
    "d3d11": "native,builtin",
    "d3d10core": "native,builtin",
}


def _extract_archive(archive: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as handle:
        members = handle.getmembers()
        top_levels = {member.name.split("/", 1)[0] for member in members if member.name}
        handle.extractall(target_dir)
    if len(top_levels) == 1:
        return target_dir / next(iter(top_levels))
    return target_dir


def resolve_dxmt_root(source: Path, cache_dir: Path) -> Path:
    candidate = source.expanduser().resolve()
    if candidate.is_dir():
        return candidate
    if candidate.is_file() and candidate.suffixes[-2:] == [".tar", ".gz"]:
        return _extract_archive(candidate, cache_dir / candidate.stem.replace(".tar", ""))
    raise FileNotFoundError(f"DXMT source must be a directory or .tar.gz archive: {candidate}")


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
        existing: list[str] = []
        for line in lines[start + 1 : end]:
            if not (line.startswith('"') and '"="' in line and line.endswith('"')):
                existing.append(line)
        lines[start:end] = [header, *existing, *section_lines[1:]]

    user_reg.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _locate_payload_dirs(dxmt_root: Path) -> tuple[Path, Path]:
    candidates = (
        (dxmt_root / "x64", dxmt_root / "x32"),
        (dxmt_root / "x86_64-windows", dxmt_root / "i386-windows"),
    )
    for x64_dir, x32_dir in candidates:
        if x64_dir.is_dir() and x32_dir.is_dir():
            return x64_dir, x32_dir
    raise FileNotFoundError(
        "DXMT directory must contain x32/ and x64/, or i386-windows/ and x86_64-windows/: "
        f"{dxmt_root}"
    )


def _locate_unix_payload_dir(dxmt_root: Path) -> Path | None:
    for candidate in (dxmt_root / "x86_64-unix", dxmt_root / "lib" / "wine" / "x86_64-unix"):
        if candidate.is_dir():
            return candidate
    return None


def _active_wine_module_root() -> Path | None:
    wine_path = shutil.which("wine")
    if not wine_path:
        return None
    wine_bin = Path(wine_path).resolve()
    for ancestor in wine_bin.parents:
        candidate = ancestor / "lib" / "wine"
        if candidate.is_dir():
            return candidate
    return None


def _enable_dxmt_overrides(bottle: Bottle) -> None:
    _upsert_user_reg_section(
        bottle.prefix / "user.reg",
        r"Software\\Wine\\DllOverrides",
        DXMT_DLL_OVERRIDES,
    )


def install_dxmt(*, bottle: Bottle, dxmt_source: Path) -> tuple[int, str]:
    ensure_bottle_dirs(bottle)
    dxmt_root = resolve_dxmt_root(dxmt_source, bottle.cache / "dxmt")
    x64_dir, x32_dir = _locate_payload_dirs(dxmt_root)
    unix_dir = _locate_unix_payload_dir(dxmt_root)

    system32 = bottle.drive_c / "windows" / "system32"
    syswow64 = bottle.drive_c / "windows" / "syswow64"
    system32.mkdir(parents=True, exist_ok=True)
    syswow64.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for source_dir, target_dir in ((x64_dir, system32), (x32_dir, syswow64)):
        for dll_name in ("dxgi.dll", "d3d10core.dll", "d3d11.dll", "winemetal.dll", "nvapi64.dll", "nvngx.dll"):
            source = source_dir / dll_name
            if source.exists():
                destination = target_dir / dll_name
                shutil.copy2(source, destination)
                copied.append(str(destination))

    module_root = _active_wine_module_root()
    if module_root:
        runtime_targets = (
            (x64_dir / "winemetal.dll", module_root / "x86_64-windows" / "winemetal.dll"),
            (x32_dir / "winemetal.dll", module_root / "i386-windows" / "winemetal.dll"),
        )
        if unix_dir:
            runtime_targets += ((unix_dir / "winemetal.so", module_root / "x86_64-unix" / "winemetal.so"),)
        for source, destination in runtime_targets:
            if source.exists() and destination.parent.is_dir():
                shutil.copy2(source, destination)
                copied.append(str(destination))

    if not copied:
        raise FileNotFoundError(f"No DXMT DLLs found under: {dxmt_root}")

    _enable_dxmt_overrides(bottle)
    return 0, "\n".join(copied)
