from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil

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


def external_prefix_paths(prefix: Path) -> Bottle:
    resolved = prefix.expanduser().resolve()
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]
    root = app_support_root() / "external-prefixes" / digest
    return Bottle(
        name=resolved.name or digest,
        root=root,
        prefix=resolved,
        logs=root / "logs",
        downloads=root / "downloads",
        cache=root / "cache",
    )


def ensure_bottle_dirs(bottle: Bottle) -> None:
    for path in (bottle.root, bottle.prefix, bottle.logs, bottle.downloads, bottle.cache):
        path.mkdir(parents=True, exist_ok=True)


def bottles_root() -> Path:
    return app_support_root() / "bottles"


def list_bottle_roots() -> list[Path]:
    root = bottles_root()
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def wipe_all_bottles() -> list[Path]:
    removed: list[Path] = []
    for bottle_root in list_bottle_roots():
        shutil.rmtree(bottle_root)
        removed.append(bottle_root)
    return removed
