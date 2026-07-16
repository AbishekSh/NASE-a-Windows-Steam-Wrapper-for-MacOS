from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mysteamwine.bottle import Bottle
import mysteamwine.steam_libraries as steam_libraries


def write_manifest(steamapps: Path, appid: str, name: str, install_dir: str) -> Path:
    steamapps.mkdir(parents=True, exist_ok=True)
    manifest = steamapps / f"appmanifest_{appid}.acf"
    manifest.write_text(
        f'''"AppState"
{{
    "appid" "{appid}"
    "name" "{name}"
    "installdir" "{install_dir}"
    "StateFlags" "4"
}}
''',
        encoding="utf-8",
    )
    return manifest


class SteamLibraryRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="nase-library-test-"))
        bottle_root = self.root / "bottles" / "Default"
        self.bottle = Bottle(
            "Default",
            bottle_root,
            bottle_root / "prefix",
            bottle_root / "logs",
            bottle_root / "downloads",
            bottle_root / "cache",
        )
        self.primary = self.bottle.prefix / "drive_c" / "Program Files (x86)" / "Steam" / "steamapps"
        self.external = self.root / "SharedSteam" / "steamapps"

    def test_discovers_deduplicates_and_prefers_installed_location(self) -> None:
        write_manifest(self.primary, "100", "Example Game", "Example Game")
        write_manifest(self.external, "100", "Example Game", "Example Game")
        (self.external / "common" / "Example Game").mkdir(parents=True)
        self.primary.mkdir(parents=True, exist_ok=True)
        (self.primary / "libraryfolders.vdf").write_text(
            f'''"libraryfolders"
{{
    "1"
    {{
        "path" "{self.external.parent}"
    }}
}}
''',
            encoding="utf-8",
        )

        with patch.object(steam_libraries, "list_bottle_roots", return_value=[]):
            registry = steam_libraries.discover_steam_libraries(self.bottle)

        self.assertEqual(len(registry["libraries"]), 2)
        self.assertEqual(len(registry["apps"]), 1)
        app = registry["apps"][0]
        self.assertEqual(len(app["locations"]), 2)
        self.assertEqual(app["preferred_location"]["state"], "installed")
        self.assertEqual(app["preferred_location"]["install_dir"], str((self.external / "common" / "Example Game").resolve()))

    def test_stale_manifest_remains_in_registry_but_not_installed_games(self) -> None:
        write_manifest(self.primary, "200", "Missing Game", "Missing Game")
        with patch.object(steam_libraries, "list_bottle_roots", return_value=[]):
            registry = steam_libraries.discover_steam_libraries(self.bottle)

        self.assertEqual(registry["apps"][0]["state"], "missing-files")
        self.assertEqual(steam_libraries.installed_games(registry), [])

    def test_registry_write_is_atomic_and_reloadable(self) -> None:
        write_manifest(self.primary, "300", "Saved Game", "Saved Game")
        (self.primary / "common" / "Saved Game").mkdir(parents=True)
        destination = self.root / "steam-libraries.json"
        with (
            patch.object(steam_libraries, "list_bottle_roots", return_value=[]),
            patch.object(steam_libraries, "registry_path", return_value=destination),
        ):
            registry = steam_libraries.refresh_registry(self.bottle)

        self.assertTrue(destination.is_file())
        self.assertFalse(destination.with_suffix(".tmp").exists())
        self.assertEqual(steam_libraries.installed_games(registry)[0]["appid"], "300")


if __name__ == "__main__":
    unittest.main()
