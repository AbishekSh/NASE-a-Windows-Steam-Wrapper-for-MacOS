from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")


def check_executable(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    if not os.access(path, os.X_OK):
        raise PermissionError(f"{label} is not executable: {path}")


def resolve_executable(path_or_name: str, label: str) -> Path:
    candidate = Path(path_or_name).expanduser()
    if candidate.is_absolute() or "/" in path_or_name:
        resolved = candidate.resolve()
    else:
        found = shutil.which(path_or_name)
        if not found:
            raise FileNotFoundError(f"{label} not found in PATH: {path_or_name}")
        resolved = Path(found).resolve()
    check_executable(resolved, label)
    return resolved


def resolve_with_fallback(path_or_name: str, label: str, fallback_names: tuple[str, ...]) -> Path:
    try:
        return resolve_executable(path_or_name, label)
    except FileNotFoundError:
        original = Path(path_or_name).expanduser()
        candidates: list[str] = []

        if original.name:
            for fallback in fallback_names:
                if original.is_absolute() or "/" in path_or_name:
                    candidates.append(str(original.with_name(fallback)))
                else:
                    candidates.append(fallback)

        for candidate in candidates:
            try:
                return resolve_executable(candidate, label)
            except FileNotFoundError:
                continue

        raise


def download(url: str, dest: Path) -> None:
    ensure_dirs(dest.parent)
    if dest.exists() and dest.stat().st_size > 0:
        return
    print(f"Downloading {url} -> {dest}")
    with urllib.request.urlopen(url) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def run_logged(
    *,
    cmd: Iterable[str],
    env: Optional[Dict[str, str]],
    log_file: Path,
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
) -> Tuple[int, str]:
    ensure_dirs(log_file.parent)

    command = [str(part) for part in cmd]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    tail_lines: list[str] = []
    tail_max = 200
    exit_code = 1

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("\n" + "=" * 80 + "\n")
        handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] RUN: {' '.join(command)}\n")
        if env and env.get("WINEPREFIX"):
            handle.write(f"ENV WINEPREFIX={env['WINEPREFIX']}\n")
        handle.flush()

        proc = subprocess.Popen(
            command,
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
                handle.write(line)
                handle.flush()

                tail_lines.append(line.rstrip("\n"))
                if len(tail_lines) > tail_max:
                    tail_lines.pop(0)

            exit_code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            exit_code = 124
            message = f"\n[Timeout] Process exceeded {timeout}s and was killed.\n"
            sys.stdout.write(message)
            handle.write(message)
        finally:
            handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] EXIT: {exit_code}\n")
            handle.flush()

    return exit_code, "\n".join(tail_lines[-50:])
