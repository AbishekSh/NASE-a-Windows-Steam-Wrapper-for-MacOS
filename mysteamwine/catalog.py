from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import shutil
import subprocess
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .bottle import Bottle, app_support_root
from .dxmt import install_dxmt
from .dxvk import install_dxvk


@dataclass(frozen=True)
class RuntimeCatalogEntry:
    id: str
    name: str
    version: str
    kind: str
    source: str
    download_url: str
    sha256: str | None
    archive_type: str
    install_layout: str
    license: str
    notes: str


@dataclass(frozen=True)
class InstalledRuntime:
    id: str
    name: str
    version: str
    kind: str
    path: str
    executable: str | None
    installed_at: float


StepCallback = Callable[[str, str, str], None]


CATALOG: tuple[RuntimeCatalogEntry, ...] = (
    RuntimeCatalogEntry(
        id="legendary-python-0.20.34-macos",
        name="Legendary Epic Client",
        version="0.20.34",
        kind="source-client",
        source="legendary-gl/legendary",
        download_url="https://files.pythonhosted.org/packages/2d/bb/f392f3b114410c7cd411500af424867d1cdacb347d12e8696758372de8c3/legendary_gl-0.20.34-py3-none-any.whl",
        sha256="14f56c337f705346a4bfe27a14e56d60eecbe6508cc0a580ef18d1e44813136c",
        archive_type="wheel",
        install_layout="legendary-python-venv",
        license="GPL-3.0",
        notes="Pinned Legendary wheel installed into a native managed Python environment for Epic authentication, downloads, repair, and launch metadata.",
    ),
    RuntimeCatalogEntry(
        id="dxvk-macos-1.10.3-20230507-repack",
        name="DXVK-macOS Async",
        version="1.10.3-20230507 repack",
        kind="dxvk-macos",
        source="Gcenx/DXVK-macOS",
        download_url="https://github.com/Gcenx/DXVK-macOS/releases/download/v1.10.3-20230507-repack/dxvk-macOS-async-v1.10.3-20230507-repack.tar.gz",
        sha256="acd1520ad105d8ef124a09c8e11a259a5dc8bdc565ad18e0e52693f9807b2477",
        archive_type="tar.gz",
        install_layout="dxvk-macos",
        license="zlib",
        notes=(
            "Pinned macOS DXVK build for Sikarugir Wine 10 r6. The paired CodeWeavers MoltenVK 1.4.1 "
            "library must be imported from a compatible Sikarugir wrapper and is checksum verified."
        ),
    ),
    RuntimeCatalogEntry(
        id="wine-sikarugir-10.0-r6",
        name="Sikarugir Wine",
        version="10.0 revision 6",
        kind="wine",
        source="Sikarugir-App/Engines",
        download_url="https://github.com/Sikarugir-App/Engines/releases/download/v1.0/WS12WineSikarugir10.0_6.tar.xz",
        sha256="9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2",
        archive_type="tar.xz",
        install_layout="sikarugir-wine",
        license="LGPL-2.1",
        notes="Pinned Wine engine for the D3DMetal profile. Requires the paired Sikarugir D3DMetal framework bundle.",
    ),
    RuntimeCatalogEntry(
        id="dxvk-2.7.1",
        name="DXVK",
        version="2.7.1",
        kind="dxvk",
        source="doitsujin/dxvk",
        download_url="https://github.com/doitsujin/dxvk/releases/download/v2.7.1/dxvk-2.7.1.tar.gz",
        sha256="d85ce7c79f57ecd765aaa1b9e7007cb875e6fde9f6d331df799bce73d513ce87",
        archive_type="tar.gz",
        install_layout="dxvk",
        license="zlib",
        notes=(
            "Upstream DXVK only; this does not enable the DXVK-macOS compatibility profile. "
            "That profile requires a separately pinned matching Wine, winevulkan, MoltenVK, and DXVK-macOS stack."
        ),
    ),
    RuntimeCatalogEntry(
        id="dxmt-0.71",
        name="DXMT",
        version="0.71",
        kind="dxmt",
        source="3Shain/dxmt",
        download_url="https://github.com/3Shain/dxmt/releases/download/v0.71/dxmt-v0.71-builtin.tar.gz",
        sha256="72e00ce7bc28ff3980b7ad8efa7209e66fe2cfbba8aa4eb6c263d5c88ec16e3e",
        archive_type="tar.gz",
        install_layout="dxmt",
        license="MIT",
        notes="Recommended Metal-backed D3D11 path for macOS. Pinned to v0.71 for current compatibility.",
    ),
    RuntimeCatalogEntry(
        id="wine-devel-11.10-gcenx",
        name="Wine Devel",
        version="11.10",
        kind="wine",
        source="Gcenx/macOS_Wine_builds",
        download_url="https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.10/wine-devel-11.10-osx64.tar.xz",
        sha256="6d0637c3526fbe7051a5f8968dbde68fbc3ac417717648b9331c46642b52173b",
        archive_type="tar.xz",
        install_layout="gcenx-wine",
        license="LGPL",
        notes="Gcenx macOS Wine build. Requires GStreamer.framework installed for all users.",
    ),
    RuntimeCatalogEntry(
        id="wine-staging-11.10-gcenx",
        name="Wine Staging",
        version="11.10",
        kind="wine",
        source="Gcenx/macOS_Wine_builds",
        download_url="https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.10/wine-staging-11.10-osx64.tar.xz",
        sha256="940bdd1a177872020be01c5c33917cb8eecc1cc3193ad554914fb6efd90d7889",
        archive_type="tar.xz",
        install_layout="gcenx-wine",
        license="LGPL",
        notes="Gcenx Wine Staging build. Requires GStreamer.framework installed for all users.",
    ),
)


def runtime_root() -> Path:
    return app_support_root() / "runtimes"


def downloads_root() -> Path:
    return app_support_root() / "runtime-downloads"


def installed_state_path() -> Path:
    return runtime_root() / "installed.json"


def list_runtime_catalog() -> list[dict]:
    installed = {runtime.id for runtime in list_installed_runtimes()}
    return [
        {
            **asdict(entry),
            "installed": entry.id in installed,
        }
        for entry in CATALOG
    ]


def list_installed_runtimes() -> list[InstalledRuntime]:
    path = installed_state_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    runtimes = []
    for item in payload.get("runtimes", []):
        try:
            runtimes.append(InstalledRuntime(**item))
        except TypeError:
            continue
    return runtimes


def _write_installed_runtimes(runtimes: list[InstalledRuntime]) -> None:
    path = installed_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"runtimes": [asdict(runtime) for runtime in runtimes]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _catalog_entry(runtime_id: str) -> RuntimeCatalogEntry:
    for entry in CATALOG:
        if entry.id == runtime_id:
            return entry
    raise KeyError(f"Unknown runtime id: {runtime_id}")


def _download(entry: RuntimeCatalogEntry, callback: StepCallback | None = None) -> Path:
    downloads_root().mkdir(parents=True, exist_ok=True)
    file_name = entry.download_url.rsplit("/", 1)[-1]
    destination = downloads_root() / file_name
    if destination.exists() and destination.stat().st_size > 0:
        if callback:
            callback("download", "ok", f"Using cached download {destination.name}.")
        return destination

    if callback:
        callback("download", "started", f"Downloading {entry.name} {entry.version}...")
    with urllib.request.urlopen(entry.download_url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    if callback:
        callback("download", "ok", f"Downloaded {destination.name}.")
    return destination


def _verify(path: Path, sha256: str | None, callback: StepCallback | None = None) -> None:
    if not sha256:
        if callback:
            callback("verify", "ok", "No checksum was provided; skipping verification.")
        return
    if callback:
        callback("verify", "started", "Verifying SHA-256 checksum...")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual.lower() != sha256.lower():
        raise ValueError(f"Checksum mismatch for {path.name}: expected {sha256}, got {actual}")
    if callback:
        callback("verify", "ok", "Checksum verified.")


def _strip_top_level(extract_dir: Path) -> Path:
    children = [child for child in extract_dir.iterdir() if child.name != ".DS_Store"]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extract_dir


def _ensure_safe_archive_path(target: Path, member_name: str) -> None:
    target_root = target.resolve()
    member_path = (target / member_name).resolve()
    if not member_path.is_relative_to(target_root):
        raise ValueError(f"Archive member escapes extraction directory: {member_name}")


def _ensure_safe_tar_link(target: Path, member: tarfile.TarInfo) -> None:
    if not (member.issym() or member.islnk()):
        return

    target_root = target.resolve()
    link_target = Path(member.linkname)
    if link_target.is_absolute():
        resolved_link = link_target.resolve()
    else:
        resolved_link = ((target / member.name).parent / link_target).resolve()
    if not resolved_link.is_relative_to(target_root):
        raise ValueError(f"Archive link escapes extraction directory: {member.name} -> {member.linkname}")


def _extract_tar_safely(handle: tarfile.TarFile, target: Path) -> None:
    for member in handle.getmembers():
        _ensure_safe_archive_path(target, member.name)
        _ensure_safe_tar_link(target, member)
    handle.extractall(target)


def _extract_zip_safely(handle: zipfile.ZipFile, target: Path) -> None:
    for member in handle.infolist():
        _ensure_safe_archive_path(target, member.filename)
    handle.extractall(target)


def _extract(archive: Path, entry: RuntimeCatalogEntry, callback: StepCallback | None = None) -> Path:
    destination = runtime_root() / entry.kind / entry.id
    if destination.exists():
        if callback:
            callback("extract", "ok", f"{entry.name} {entry.version} is already extracted.")
        return destination

    temp = destination.with_name(destination.name + ".tmp")
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True, exist_ok=True)
    if callback:
        callback("extract", "started", f"Extracting {archive.name}...")

    if entry.archive_type in {"tar.gz", "tar.xz"}:
        with tarfile.open(archive) as handle:
            _extract_tar_safely(handle, temp)
    elif entry.archive_type == "zip":
        with zipfile.ZipFile(archive) as handle:
            _extract_zip_safely(handle, temp)
    else:
        raise ValueError(f"Unsupported archive type: {entry.archive_type}")

    extracted_root = _strip_top_level(temp)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if extracted_root == temp:
        temp.rename(destination)
    else:
        extracted_root.rename(destination)
        shutil.rmtree(temp, ignore_errors=True)
    if callback:
        callback("extract", "ok", f"Extracted to {destination}.")
    return destination


def _find_wine_executable(root: Path) -> str | None:
    candidates = [
        root / "bin" / "wine",
        root / "wine-devel" / "bin" / "wine",
        root / "wine-staging" / "bin" / "wine",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    for candidate in sorted(root.rglob("wine")):
        if candidate.is_file() and candidate.parent.name == "bin":
            return str(candidate)
    return None


def _install_legendary_venv(archive: Path, entry: RuntimeCatalogEntry, callback: StepCallback | None) -> tuple[Path, str]:
    destination = runtime_root() / entry.kind / entry.id
    executable = destination / "bin" / "legendary"
    if executable.is_file() and executable.stat().st_mode & 0o111:
        check = subprocess.run([str(executable), "--version"], capture_output=True, text=True, check=False, timeout=30)
        if check.returncode == 0 and "0.20.34" in (check.stdout or check.stderr):
            return destination, str(executable)
        shutil.rmtree(destination)
    python = next(
        (path for name in ("python3.13", "python3.12", "python3.11", "python3.10") if (path := shutil.which(name))),
        None,
    )
    if not python:
        raise RuntimeError("Legendary requires Homebrew Python 3.10–3.13. Install Python from NASE setup, then retry.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if callback:
        callback("extract", "started", "Creating a native managed Legendary environment...")
    subprocess.run([python, "-m", "venv", str(destination)], check=True, capture_output=True, text=True, timeout=120)
    pip = destination / "bin" / "pip"
    result = subprocess.run(
        [str(pip), "install", "--disable-pip-version-check", str(archive)],
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    candidate = destination / "bin" / "legendary"
    if result.returncode != 0 or not candidate.is_file():
        shutil.rmtree(destination, ignore_errors=True)
        tail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(f"Managed Legendary installation failed: {tail[-1] if tail else 'unknown error'}")
    version = subprocess.run([str(candidate), "--version"], capture_output=True, text=True, check=False, timeout=30)
    version_text = (version.stdout or version.stderr).strip()
    if version.returncode != 0 or "0.20.34" not in version_text:
        shutil.rmtree(destination, ignore_errors=True)
        raise RuntimeError(f"Unexpected Legendary version: {version_text or 'unknown'}")
    if callback:
        callback("extract", "ok", "Created the native managed Legendary environment.")
    return destination, str(executable)


def _record_install(entry: RuntimeCatalogEntry, path: Path, executable: str | None) -> InstalledRuntime:
    runtimes = [runtime for runtime in list_installed_runtimes() if runtime.id != entry.id]
    installed = InstalledRuntime(
        id=entry.id,
        name=entry.name,
        version=entry.version,
        kind=entry.kind,
        path=str(path),
        executable=executable,
        installed_at=time.time(),
    )
    runtimes.append(installed)
    runtimes.sort(key=lambda runtime: (runtime.kind, runtime.name, runtime.version))
    _write_installed_runtimes(runtimes)
    return installed


def install_runtime(
    *,
    runtime_id: str,
    bottle: Bottle | None = None,
    wine_path: Path | None = None,
    install_into_bottle: bool = True,
    callback: StepCallback | None = None,
) -> tuple[InstalledRuntime, list[str]]:
    entry = _catalog_entry(runtime_id)
    archive = _download(entry, callback)
    _verify(archive, entry.sha256, callback)
    if entry.install_layout == "legendary-python-venv":
        extracted, executable = _install_legendary_venv(archive, entry, callback)
    else:
        extracted = _extract(archive, entry, callback)
        executable = _find_wine_executable(extracted) if entry.kind == "wine" else None

    notes: list[str] = []
    if entry.id == "wine-sikarugir-10.0-r6":
        if executable is None or not (extracted / "bin" / "wineserver").is_file():
            raise RuntimeError("Sikarugir Wine archive is missing bin/wine or bin/wineserver.")
        result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10, check=False)
        version = (result.stdout or result.stderr).strip()
        if result.returncode != 0 or version != "wine-10.0 (Sikarugir)":
            raise RuntimeError(f"Unexpected Sikarugir Wine engine version: {version or 'unknown'}")
        if not (extracted / "lib" / "wine").is_dir() or not (extracted / "share" / "wine").is_dir():
            raise RuntimeError("Sikarugir Wine archive is missing its lib/wine or share/wine runtime layout.")
    installed = _record_install(entry, extracted, executable)

    if install_into_bottle and entry.kind in {"dxvk", "dxmt"}:
        if bottle is None:
            raise ValueError(f"{entry.name} install requires a target bottle or prefix.")
        if callback:
            callback("install-bottle", "started", f"Installing {entry.name} into the selected bottle...")
        if entry.kind == "dxvk":
            code, tail = install_dxvk(bottle=bottle, dxvk_source=extracted)
        else:
            code, tail = install_dxmt(bottle=bottle, dxmt_source=extracted, wine64_path=wine_path)
        if code != 0:
            raise RuntimeError(f"{entry.name} bottle install failed (exit {code}). Tail:\n{tail}")
        if tail:
            notes.append(tail)
        if callback:
            callback("install-bottle", "ok", f"Installed {entry.name} into the selected bottle.")
    elif entry.kind == "wine" and executable:
        notes.append(f"Wine executable: {executable}")
    elif entry.kind == "wine":
        notes.append("Wine archive installed, but no bin/wine executable was detected.")
    elif entry.kind == "source-client" and executable:
        notes.append(f"Source client executable: {executable}")

    return installed, notes
