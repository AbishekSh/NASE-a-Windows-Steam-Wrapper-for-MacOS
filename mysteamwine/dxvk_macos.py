from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

from .bottle import Bottle


PINNED_WINE_VERSION = "wine-10.0 (Sikarugir)"
PINNED_DXVK_RUNTIME_ID = "dxvk-macos-1.10.3-20230507-repack"
PINNED_DXVK_VERSION = "1.10.3-20230507-repack"
PINNED_MOLTENVK_VERSION = "1.2.10-cx"
PINNED_MOLTENVK_SHA256 = "e9de8aa6053e1347c82aff01c6d7964556f306b2f7c63db88eb54a05e4f8b980"


def discover_moltenvk_source() -> Path | None:
    roots = (Path.home() / "Applications" / "Sikarugir", Path("/Applications"))
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("libMoltenVK.dylib"):
            if "moltenvkcx" not in str(path).lower():
                continue
            try:
                if _sha256(path) == PINNED_MOLTENVK_SHA256:
                    return path
            except OSError:
                continue
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pe_machine(path: Path) -> int | None:
    try:
        with path.open("rb") as handle:
            if handle.read(2) != b"MZ":
                return None
            handle.seek(0x3C)
            pe_offset = struct.unpack("<I", handle.read(4))[0]
            handle.seek(pe_offset)
            if handle.read(4) != b"PE\0\0":
                return None
            return struct.unpack("<H", handle.read(2))[0]
    except (OSError, struct.error):
        return None


def _find_winevulkan(wine_path: Path) -> dict[str, Path]:
    root = wine_path.expanduser().resolve().parent.parent
    matches: dict[str, Path] = {}
    for path in root.rglob("winevulkan*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        relative = str(path.relative_to(root)).lower()
        if name == "winevulkan.drv.so" or (name == "winevulkan.so" and "unix" in relative):
            matches.setdefault("unix", path)
        elif name in {"winevulkan.dll", "winevulkan.drv"} and "x86_64" in relative:
            matches.setdefault("windows_x64", path)
        elif name in {"winevulkan.dll", "winevulkan.drv"} and ("i386" in relative or "x86-windows" in relative):
            matches.setdefault("windows_x86", path)
    return matches


def resolve_moltenvk_library(source: Path) -> Path:
    candidate = source.expanduser().resolve()
    if candidate.is_file() and candidate.name in {"libMoltenVK.dylib", "libMoltenVK-CX.dylib"}:
        return candidate
    if candidate.is_dir():
        preferred = (
            candidate / "Contents" / "Frameworks" / "moltenvkcx" / "libMoltenVK.dylib",
            candidate / "moltenvkcx" / "libMoltenVK.dylib",
            candidate / "libMoltenVK.dylib",
        )
        for path in preferred:
            if path.is_file():
                return path
        for path in candidate.rglob("libMoltenVK.dylib"):
            if "moltenvkcx" in str(path).lower():
                return path
    raise RuntimeError(
        "Could not find the pinned CodeWeavers MoltenVK library. Select a compatible Sikarugir wrapper "
        "or its Contents/Frameworks/moltenvkcx directory."
    )


def inspect_dxvk_macos_stack(wine_path: Path, dxvk_source: Path, moltenvk_source: Path) -> dict:
    version_result = subprocess.run(
        [str(wine_path), "--version"], capture_output=True, text=True, timeout=10, check=False
    )
    wine_version = (version_result.stdout or version_result.stderr).strip()
    if version_result.returncode != 0 or wine_version != PINNED_WINE_VERSION:
        raise RuntimeError(f"DXVK-macOS requires {PINNED_WINE_VERSION}; found {wine_version or 'unknown'}.")

    root = dxvk_source.expanduser().resolve()
    x64 = root / "x64"
    x32 = root / "x32"
    required = (x64 / "d3d11.dll", x64 / "d3d10core.dll", x32 / "d3d11.dll", x32 / "d3d10core.dll")
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("DXVK-macOS archive is incomplete: " + ", ".join(missing))
    architecture = {
        "x64_d3d11": _pe_machine(x64 / "d3d11.dll"),
        "x86_d3d11": _pe_machine(x32 / "d3d11.dll"),
    }
    if architecture != {"x64_d3d11": 0x8664, "x86_d3d11": 0x014C}:
        raise RuntimeError(f"DXVK DLL architecture mismatch: {architecture}")

    winevulkan = _find_winevulkan(wine_path)
    if "unix" not in winevulkan or "windows_x64" not in winevulkan:
        raise RuntimeError("Pinned Wine engine is missing its matching Unix and x86_64 Windows winevulkan modules.")

    moltenvk = resolve_moltenvk_library(moltenvk_source)
    moltenvk_sha = _sha256(moltenvk)
    if moltenvk_sha != PINNED_MOLTENVK_SHA256:
        raise RuntimeError(
            "MoltenVK does not match the pinned CodeWeavers 1.2.10 build "
            f"(expected {PINNED_MOLTENVK_SHA256}, got {moltenvk_sha})."
        )
    file_result = subprocess.run(["/usr/bin/file", str(moltenvk)], capture_output=True, text=True, check=False)
    if file_result.returncode != 0 or "Mach-O" not in file_result.stdout:
        raise RuntimeError("Pinned MoltenVK library is not a valid Mach-O dylib.")
    deps_result = subprocess.run(["/usr/bin/otool", "-L", str(moltenvk)], capture_output=True, text=True, check=False)
    if deps_result.returncode != 0:
        raise RuntimeError("Could not inspect MoltenVK native dylib dependencies.")

    return {
        "schema_version": 1,
        "wine_version": wine_version,
        "wine_path": str(wine_path.expanduser().resolve()),
        "winevulkan": {key: str(path) for key, path in sorted(winevulkan.items())},
        "dxvk_version": PINNED_DXVK_VERSION,
        "dxvk_source": str(root),
        "dll_architecture": architecture,
        "moltenvk_version": PINNED_MOLTENVK_VERSION,
        "moltenvk_source": str(moltenvk),
        "moltenvk_sha256": moltenvk_sha,
        "moltenvk_dependencies": deps_result.stdout.splitlines()[1:],
    }


def install_dxvk_macos_native_runtime(bottle: Bottle, inspection: dict) -> Path:
    native = bottle.root / "runtime" / "dxvk-macos" / "native"
    native.mkdir(parents=True, exist_ok=True)
    source = Path(inspection["moltenvk_source"])
    destination = native / "libMoltenVK.dylib"
    shutil.copy2(source, destination)
    manifest = bottle.root / "runtime" / "dxvk-macos" / "stack.json"
    manifest.write_text(json.dumps(inspection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return native


def dxvk_macos_launch_environment(bottle: Bottle) -> dict[str, str]:
    native = bottle.root / "runtime" / "dxvk-macos" / "native"
    moltenvk = native / "libMoltenVK.dylib"
    if not moltenvk.is_file() or _sha256(moltenvk) != PINNED_MOLTENVK_SHA256:
        raise RuntimeError("DXVK-macOS native runtime is missing or damaged. Repair the profile first.")
    fallback = str(native)
    existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH")
    if existing:
        fallback += ":" + existing
    return {
        "DYLD_FALLBACK_LIBRARY_PATH": fallback,
        "MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS": "0",
        "DXVK_LOG_LEVEL": "info",
    }


def verify_dxvk_macos_profile(bottle: Bottle) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    expected = {
        bottle.drive_c / "windows" / "system32" / "d3d11.dll": 0x8664,
        bottle.drive_c / "windows" / "system32" / "d3d10core.dll": 0x8664,
        bottle.drive_c / "windows" / "syswow64" / "d3d11.dll": 0x014C,
        bottle.drive_c / "windows" / "syswow64" / "d3d10core.dll": 0x014C,
    }
    for path, machine in expected.items():
        actual = _pe_machine(path) if path.is_file() else None
        checks.append({
            "name": f"dll-{path.parent.name}-{path.stem}",
            "status": "ok" if actual == machine else "error",
            "detail": f"{path} has PE machine 0x{actual:04x}." if actual is not None else f"Missing or invalid {path}.",
        })
    user_reg = bottle.prefix / "user.reg"
    registry = user_reg.read_text(encoding="utf-8", errors="replace") if user_reg.is_file() else ""
    required = ('"d3d10core"="native"', '"d3d11"="native"')
    conflicts = ('"dxgi"="native"', '"winemetal"="native"', '"d3d12"="native"')
    overrides_ok = all(value in registry for value in required) and not any(value in registry for value in conflicts)
    checks.append({
        "name": "renderer-overrides",
        "status": "ok" if overrides_ok else "error",
        "detail": "Only the DXVK-macOS D3D10/11 native overrides are enabled." if overrides_ok else "Renderer overrides are missing or conflict with DXMT/D3DMetal.",
    })
    try:
        environment = dxvk_macos_launch_environment(bottle)
        checks.append({"name": "native-moltenvk", "status": "ok", "detail": environment["DYLD_FALLBACK_LIBRARY_PATH"]})
    except RuntimeError as exc:
        checks.append({"name": "native-moltenvk", "status": "error", "detail": str(exc)})
    return checks
