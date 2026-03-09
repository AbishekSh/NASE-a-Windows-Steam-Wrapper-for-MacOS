from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import APP_NAME


@dataclass(frozen=True)
class Bottle:
    name: str
    root: Path
    prefix: Path
    logs: Path
    downloads: Path
    cache: Path

    @property
    def drive_c(self) -> Path:
        return self.prefix / "drive_c"


def app_support_root() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def bottle_paths(name: str) -> Bottle:
    root = app_support_root() / "bottles" / name
    return Bottle(
        name=name,
        root=root,
        prefix=root / "prefix",
        logs=root / "logs",
        downloads=root / "downloads",
        cache=root / "cache",
    )


def ensure_bottle_dirs(bottle: Bottle) -> None:
    for path in (bottle.root, bottle.prefix, bottle.logs, bottle.downloads, bottle.cache):
        path.mkdir(parents=True, exist_ok=True)
