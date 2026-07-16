from __future__ import annotations

import platform
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from .catalog import list_installed_runtimes
from .gptk import inspect_gptk_installation


def _check(status: str, name: str, detail: str, *, required: bool, fix: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "name": name,
        "detail": detail,
        "required": required,
        "fix": fix,
    }


def _command_version(command: Path, argument: str = "--version") -> tuple[int, str]:
    try:
        result = subprocess.run(
            [str(command), argument], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return result.returncode, (result.stdout or result.stderr).strip()


def _rosetta_installed() -> bool:
    if Path("/Library/Apple/usr/libexec/oah/libRosettaRuntime").exists():
        return True
    result = subprocess.run(
        ["/usr/sbin/pkgutil", "--pkg-info", "com.apple.pkg.RosettaUpdateAuto"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return result.returncode == 0


def dependency_status(
    *,
    wine_path: Path,
    winetricks_path: str = "winetricks",
    gptk_wine_path: Path | None = None,
    d3dmetal_source: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    mac_version = platform.mac_ver()[0]
    try:
        major = int(mac_version.split(".", 1)[0])
    except (ValueError, IndexError):
        major = 0
    checks.append(
        _check(
            "ok" if major >= 14 else "fail",
            "macOS",
            f"macOS {mac_version or 'unknown'}; NASE requires macOS 14 or newer.",
            required=True,
            fix="Update macOS to version 14 or newer." if major < 14 else None,
        )
    )

    python_ok = sys.version_info >= (3, 10)
    checks.append(
        _check(
            "ok" if python_ok else "fail",
            "Python",
            f"Python {platform.python_version()} at {sys.executable}.",
            required=True,
            fix="Install Python 3.10 or newer and select it in Advanced Settings." if not python_ok else None,
        )
    )

    machine = subprocess.run(
        ["/usr/bin/uname", "-m"], capture_output=True, text=True, timeout=5, check=False
    ).stdout.strip()
    if machine == "arm64":
        rosetta = _rosetta_installed()
        checks.append(
            _check(
                "ok" if rosetta else "fail",
                "Rosetta 2",
                "Rosetta 2 is installed." if rosetta else "Rosetta 2 is required for Windows Steam and x86 Wine components.",
                required=True,
                fix="Install Rosetta 2 from NASE or with softwareupdate." if not rosetta else None,
            )
        )
    else:
        checks.append(_check("ok", "Rosetta 2", f"Not required on {machine or 'this Mac' }.", required=False))

    resolved_winetricks = shutil.which(winetricks_path) if "/" not in winetricks_path else winetricks_path
    winetricks_ok = bool(resolved_winetricks and Path(resolved_winetricks).is_file())
    checks.append(
        _check(
            "ok" if winetricks_ok else "fail",
            "Winetricks",
            f"Found at {resolved_winetricks}." if winetricks_ok else "Winetricks was not found.",
            required=True,
            fix="Install or import Winetricks." if not winetricks_ok else None,
        )
    )

    wine_code, wine_version = _command_version(wine_path)
    wine_ok = wine_code == 0 and wine_version.lower().startswith("wine-11.0")
    checks.append(
        _check(
            "ok" if wine_ok else "fail",
            "Wine Stable 11",
            f"{wine_version or 'No working Wine runtime'} at {wine_path}.",
            required=True,
            fix="Install or import Wine Stable 11.0." if not wine_ok else None,
        )
    )

    installed = {runtime.id: runtime for runtime in list_installed_runtimes()}
    dxmt = installed.get("dxmt-0.71")
    checks.append(
        _check(
            "ok" if dxmt else "fail",
            "DXMT 0.71",
            f"Installed at {dxmt.path}." if dxmt else "The recommended Metal renderer is not installed.",
            required=True,
            fix="Install DXMT 0.71 from Runtime Center." if not dxmt else None,
        )
    )

    gptk_detail = "Optional; required only for the D3DMetal profile."
    gptk_ok = False
    if gptk_wine_path and d3dmetal_source:
        try:
            inspected = inspect_gptk_installation(gptk_wine_path, d3dmetal_source)
            gptk_ok = True
            gptk_detail = f"Matched {inspected['wine_version']} with D3DMetal at {inspected['payload_path']}."
        except RuntimeError as exc:
            gptk_detail = str(exc)
    checks.append(
        _check(
            "ok" if gptk_ok else "warn",
            "Game Porting Toolkit",
            gptk_detail,
            required=False,
            fix="Find or select one Game Porting Toolkit installation containing both Wine and D3DMetal." if not gptk_ok else None,
        )
    )

    required_failures = [check for check in checks if check["required"] and check["status"] == "fail"]
    return {
        "checks": checks,
        "worst_status": "fail" if required_failures else ("warn" if any(check["status"] == "warn" for check in checks) else "ok"),
        "ready": not required_failures,
        "missing_required": [check["name"] for check in required_failures],
    }


def homebrew_path() -> Path | None:
    resolved = shutil.which("brew")
    if resolved:
        return Path(resolved)
    for candidate in (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew")):
        if candidate.is_file():
            return candidate
    return None


def dependency_install_command(dependency: str, *, confirm_rosetta_license: bool = False) -> list[str]:
    if dependency == "rosetta":
        if not confirm_rosetta_license:
            raise RuntimeError("Rosetta installation requires explicit acceptance of Apple's software license.")
        return ["/usr/sbin/softwareupdate", "--install-rosetta", "--agree-to-license"]

    brew = homebrew_path()
    if brew is None:
        raise RuntimeError("Homebrew is required for automatic installation. Install Homebrew or import the dependency manually.")
    if dependency == "wine-stable":
        return [str(brew), "install", "--cask", "wine-stable"]
    if dependency == "winetricks":
        return [str(brew), "install", "winetricks"]
    if dependency == "python":
        return [str(brew), "install", "python"]
    raise RuntimeError(f"Unsupported host dependency: {dependency}")
