from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Iterator

from ..bottle import app_support_root
from .base import SourceGame, SourceStatus


CommandRunner = Callable[[list[str], dict[str, str], int], subprocess.CompletedProcess[str]]


def _default_runner(command: list[str], environment: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


class EpicSource:
    id = "epic"

    def __init__(self, client: str = "legendary", *, runner: CommandRunner = _default_runner) -> None:
        self.requested_client = client
        self.runner = runner

    @property
    def root(self) -> Path:
        return app_support_root() / "sources" / "epic"

    @property
    def config_root(self) -> Path:
        return self.root / "config"

    def _client_path(self) -> str | None:
        candidate = Path(self.requested_client).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
        resolved = shutil.which(self.requested_client)
        if resolved:
            return resolved
        managed = app_support_root() / "runtimes" / "source-client" / "legendary-0.20.34-macos" / "legendary"
        if managed.is_file() and os.access(managed, os.X_OK):
            return str(managed)
        return None

    def _environment(self) -> dict[str, str]:
        self.config_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        os.chmod(self.config_root, 0o700)
        environment = os.environ.copy()
        environment["XDG_CONFIG_HOME"] = str(self.config_root)
        environment["PYTHONUTF8"] = "1"
        return environment

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        lock = self.root / ".lock"
        with lock.open("a", encoding="utf-8") as handle:
            os.chmod(lock, 0o600)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _run(self, arguments: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        client = self._client_path()
        if not client:
            raise RuntimeError("Epic support requires Legendary. Epic setup can install it in the next workflow step; advanced users may select an existing executable.")
        with self._lock():
            result = self.runner([client, *arguments], self._environment(), timeout)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            tail = detail[-1] if detail else "Legendary failed without an error message."
            raise RuntimeError(f"Epic service action failed: {tail}")
        return result

    @staticmethod
    def _json_output(result: subprocess.CompletedProcess[str]) -> Any:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Epic service returned an unreadable response. Update or repair Legendary.") from exc

    def status(self) -> SourceStatus:
        client = self._client_path()
        if not client:
            return SourceStatus(
                source=self.id,
                available=False,
                authenticated=False,
                client=None,
                version=None,
                message="Legendary is not installed yet. Complete Epic setup to enable this source.",
            )
        version_result = self.runner([client, "--version"], self._environment(), 15)
        version = (version_result.stdout or version_result.stderr).strip().splitlines()
        version_text = version[-1] if version else None
        try:
            payload = self._json_output(self._run(["status", "--json"], timeout=45))
            authenticated = _authenticated_from_status(payload)
            message = "Epic account is connected." if authenticated else "Sign in to Epic Games to load your library."
        except RuntimeError:
            authenticated = False
            message = "Epic sign-in is required or has expired."
        return SourceStatus(self.id, True, authenticated, client, version_text, message)

    def list_games(self, *, force_refresh: bool = False) -> list[SourceGame]:
        owned_args = ["list", "--json", "--platform", "Windows"]
        if force_refresh:
            owned_args.append("--force-refresh")
        owned_payload = self._json_output(self._run(owned_args, timeout=300))
        installed_payload = self._json_output(
            self._run(["list-installed", "--json", "--show-dirs"], timeout=120)
        )
        return normalize_epic_games(owned_payload, installed_payload)

    def authenticate(self, *, authorization_code: str) -> SourceStatus:
        code = authorization_code.strip()
        if code.startswith("{"):
            try:
                payload = json.loads(code)
                code = str(payload.get("authorizationCode") or "").strip()
            except json.JSONDecodeError as exc:
                raise ValueError("Epic returned unreadable authorization data. Copy the response again.") from exc
        code = code.strip('"')
        if not code or any(character.isspace() for character in code):
            raise ValueError("Paste the authorization code from Epic without spaces.")
        self._run(["auth", "--code", code, "--disable-webview"], timeout=120)
        return self.status()

    def sign_out(self) -> SourceStatus:
        self._run(["auth", "--delete"], timeout=30)
        return self.status()

    def install(self, game_id: str, *, base_path: Path) -> None:
        base_path = base_path.expanduser().resolve()
        base_path.mkdir(parents=True, exist_ok=True)
        self._run(
            ["-y", "install", _game_id(game_id), "--base-path", str(base_path), "--platform", "Windows", "--skip-sdl", "--skip-dlcs"],
            timeout=24 * 60 * 60,
        )

    def update(self, game_id: str) -> None:
        self._run(["-y", "install", _game_id(game_id), "--update-only", "--platform", "Windows", "--skip-sdl", "--skip-dlcs"], timeout=24 * 60 * 60)

    def verify(self, game_id: str) -> None:
        self._run(["verify", _game_id(game_id)], timeout=4 * 60 * 60)

    def repair(self, game_id: str) -> None:
        self._run(["-y", "install", _game_id(game_id), "--repair-and-update", "--platform", "Windows", "--skip-sdl", "--skip-dlcs"], timeout=24 * 60 * 60)

    def uninstall(self, game_id: str, *, keep_files: bool = False) -> None:
        arguments = ["-y", "uninstall", _game_id(game_id)]
        if keep_files:
            arguments.append("--keep-files")
        self._run(arguments, timeout=60 * 60)

    def launch(self, game_id: str, *, wine_path: Path, wine_prefix: Path, environment: dict[str, str]) -> None:
        client = self._client_path()
        if not client:
            raise RuntimeError("Epic support requires the managed Legendary client.")
        command = [
            client,
            "launch",
            _game_id(game_id),
            "--wine",
            str(wine_path.expanduser().resolve()),
            "--wine-prefix",
            str(wine_prefix.expanduser().resolve()),
        ]
        launch_environment = self._environment()
        launch_environment.update(environment)
        with self._lock():
            result = self.runner(command, launch_environment, 300)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise RuntimeError(f"Epic game launch failed: {detail[-1] if detail else 'unknown error'}")


def _game_id(value: str) -> str:
    game_id = value.strip()
    if not game_id or any(character.isspace() for character in game_id):
        raise ValueError("Epic game id is invalid.")
    return game_id


def _authenticated_from_status(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in ("account", "account_id", "display_name", "username"):
        if payload.get(key):
            return True
    user = payload.get("user")
    return isinstance(user, dict) and bool(user)


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("games", "items", "installed"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_epic_games(owned_payload: Any, installed_payload: Any) -> list[SourceGame]:
    installed: dict[str, dict[str, Any]] = {}
    for item in _items(installed_payload):
        app_name = str(_value(item, "app_name", "appName", "app", "id") or "")
        if app_name:
            installed[app_name] = item

    games: list[SourceGame] = []
    for item in _items(owned_payload):
        app_name = str(_value(item, "app_name", "appName", "app", "id") or "")
        title = str(_value(item, "app_title", "title", "name") or app_name)
        if not app_name or not title:
            continue
        local = installed.get(app_name)
        install_path = None
        if local:
            install_path = _value(local, "install_path", "installPath", "path")
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        art_url = _value(item, "art_url", "artUrl") or _value(metadata, "art_url", "artUrl")
        games.append(
            SourceGame(
                source="epic",
                store_id=app_name,
                library_id=f"epic:{app_name}",
                title=title,
                installed=local is not None,
                install_path=str(install_path) if install_path else None,
                version=str(_value(local or {}, "version", "app_version") or "") or None,
                update_available=bool(_value(local or {}, "update_available", "updateAvailable") or False),
                art_url=str(art_url) if art_url else None,
            )
        )
    return sorted(games, key=lambda game: (game.title.casefold(), game.store_id))
