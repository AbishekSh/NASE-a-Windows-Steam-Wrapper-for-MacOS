from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .bottle import Bottle, ensure_bottle_dirs
from .runtime import check_executable, run_logged


def run_winetricks(
    *,
    bottle: Bottle,
    winetricks_path: Path,
    verbs: Sequence[str],
    log_name: str = "winetricks.log",
    unattended: bool = True,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str]:
    ensure_bottle_dirs(bottle)
    check_executable(winetricks_path, "winetricks")

    command = [str(winetricks_path)]
    if unattended:
        command.append("-q")
    command.extend(verbs)

    environment = {"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"}
    if extra_env:
        environment.update(extra_env)
    return run_logged(
        cmd=command,
        env=environment,
        log_file=bottle.logs / log_name,
    )
