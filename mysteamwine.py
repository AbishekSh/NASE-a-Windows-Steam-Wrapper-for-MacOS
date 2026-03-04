#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple


APP_NAME = "MySteamWine"
STEAM_SETUP_URL = "https://media.steampowered.com/client/installer/SteamSetup.exe"


@dataclass
class Bottle:
    name: str
    root: Path
    prefix: Path
    logs: Path
    downloads: Path


def app_support_root() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def bottle_paths(name: str) -> Bottle:
    root = app_support_root() / "bottles" / name
    prefix = root / "prefix"
    logs = root / "logs"
    downloads = root / "downloads"
    return Bottle(name=name, root=root, prefix=prefix, logs=logs, downloads=downloads)


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")


def check_wine_binary(wine64_path: Path) -> None:
    if not wine64_path.exists():
        raise FileNotFoundError(f"wine64 not found: {wine64_path}")
    if not os.access(wine64_path, os.X_OK):
        raise PermissionError(f"wine64 is not executable: {wine64_path}")


def run(
    *,
    wine64_path: Path,
    args: List[str],
    env: Dict[str, str],
    log_file: Path,
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
) -> Tuple[int, str]:
    """
    Run a command, stream output to both console and a log file.
    Returns (exit_code, combined_output_tail).
    """
    ensure_dirs(log_file.parent)

    cmd = [str(wine64_path), *args]
    merged_env = os.environ.copy()
    merged_env.update(env)

    # Store a small tail in memory for quick error messages.
    tail_lines: List[str] = []
    tail_max = 200

    with log_file.open("a", encoding="utf-8") as lf:
        lf.write("\n" + "=" * 80 + "\n")
        lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] RUN: {' '.join(cmd)}\n")
        lf.write(f"ENV WINEPREFIX={env.get('WINEPREFIX','')}\n")
        lf.flush()

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=merged_env,
            cwd=str(cwd) if cwd else None,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                sys.stdout.write(line)
                lf.write(line)
                lf.flush()

                tail_lines.append(line.rstrip("\n"))
                if len(tail_lines) > tail_max:
                    tail_lines.pop(0)

            exit_code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            exit_code = 124
            msg = f"\n[Timeout] Process exceeded {timeout}s and was killed.\n"
            sys.stdout.write(msg)
            lf.write(msg)
        finally:
            lf.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] EXIT: {exit_code}\n")
            lf.flush()

    tail = "\n".join(tail_lines[-50:])
    return exit_code, tail


def download(url: str, dest: Path) -> None:
    ensure_dirs(dest.parent)
    if dest.exists() and dest.stat().st_size > 0:
        return
    print(f"Downloading {url} -> {dest}")
    with urllib.request.urlopen(url) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)


def common_env(bottle: Bottle) -> Dict[str, str]:
    # WINEDEBUG=-all keeps logs smaller; switch to "fixme-all,err-all" during debugging.
    return {
        "WINEPREFIX": str(bottle.prefix),
        "WINEDEBUG": "-all",
    }


def cmd_init(args: argparse.Namespace) -> None:
    wine64 = Path(args.wine64).expanduser().resolve()
    check_wine_binary(wine64)

    bottle = bottle_paths(args.bottle)
    ensure_dirs(bottle.root, bottle.prefix, bottle.logs, bottle.downloads)

    # Create/initialize prefix
    log = bottle.logs / "01_wineboot.log"
    env = common_env(bottle)

    print(f"Initializing bottle '{bottle.name}' at: {bottle.prefix}")
    code, tail = run(
        wine64_path=wine64,
        args=["wineboot", "-u"],
        env=env,
        log_file=log,
    )
    if code != 0:
        raise SystemExit(f"wineboot failed (exit {code}). Tail:\n{tail}")

    print("Done.")


def cmd_install_steam(args: argparse.Namespace) -> None:
    wine64 = Path(args.wine64).expanduser().resolve()
    check_wine_binary(wine64)

    bottle = bottle_paths(args.bottle)
    ensure_dirs(bottle.root, bottle.prefix, bottle.logs, bottle.downloads)

    steam_exe = bottle.downloads / "SteamSetup.exe"
    download(STEAM_SETUP_URL, steam_exe)

    log = bottle.logs / "02_install_steam.log"
    env = common_env(bottle)

    print(f"Installing Steam into bottle '{bottle.name}'...")
    code, tail = run(
        wine64_path=wine64,
        args=[str(steam_exe)],
        env=env,
        log_file=log,
    )
    if code != 0:
        raise SystemExit(f"Steam installer failed (exit {code}). Tail:\n{tail}")

    print("Steam install finished (or installer exited).")


def cmd_run_steam(args: argparse.Namespace) -> None:
    wine64 = Path(args.wine64).expanduser().resolve()
    check_wine_binary(wine64)

    bottle = bottle_paths(args.bottle)
    ensure_dirs(bottle.root, bottle.prefix, bottle.logs, bottle.downloads)

    # Default Steam path after install (Windows path inside prefix)
    steam_path = args.steam_path or r"C:\Program Files (x86)\Steam\Steam.exe"

    log = bottle.logs / "03_run_steam.log"
    env = common_env(bottle)

    print(f"Launching Steam in bottle '{bottle.name}'...")
    code, tail = run(
        wine64_path=wine64,
        args=[steam_path],
        env=env,
        log_file=log,
    )
    if code != 0:
        raise SystemExit(f"Steam launch failed (exit {code}). Tail:\n{tail}")

    print("Steam exited.")


def cmd_info(args: argparse.Namespace) -> None:
    root = app_support_root()
    bottle = bottle_paths(args.bottle)

    print(f"APP SUPPORT ROOT: {root}")
    print(f"BOTTLE ROOT:      {bottle.root}")
    print(f"PREFIX:           {bottle.prefix}")
    print(f"LOGS:             {bottle.logs}")
    print(f"DOWNLOADS:        {bottle.downloads}")
    print(f"Apple Silicon:    {is_apple_silicon()}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mysteamwine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            f"""\
            {APP_NAME}: Python-first Wine bottle manager for Steam on macOS.

            Typical flow:
              1) init
              2) install-steam
              3) run-steam
            """
        ),
    )
    p.add_argument("--bottle", default="Default", help="Bottle name (default: Default)")
    p.add_argument(
        "--wine64",
        required=True,
        help="Path to wine64 executable (example: /path/to/wine/bin/wine64)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Show paths used for this bottle").set_defaults(func=cmd_info)
    sub.add_parser("init", help="Create/initialize the Wine prefix").set_defaults(func=cmd_init)
    sub.add_parser("install-steam", help="Download & run SteamSetup.exe").set_defaults(func=cmd_install_steam)

    r = sub.add_parser("run-steam", help="Launch Steam.exe inside the bottle")
    r.add_argument(
        "--steam-path",
        default=None,
        help=r'Windows path to Steam.exe (default: "C:\Program Files (x86)\Steam\Steam.exe")',
    )
    r.set_defaults(func=cmd_run_steam)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Friendly note for M2 users:
    if is_apple_silicon():
        # Not a hard fail; depends on which Wine build.
        print("[Note] You’re on Apple Silicon. Many Wine/Steam setups run under Rosetta 2.")

    args.func(args)


if __name__ == "__main__":
    main()