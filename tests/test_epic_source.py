from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mysteamwine.sources.epic import EpicSource, normalize_epic_games


class EpicSourceTests(unittest.TestCase):
    def test_normalizes_owned_and_installed_games(self) -> None:
        owned = [
            {"app_name": "Anemone", "app_title": "World of Goo"},
            {"app_name": "Cattail", "app_title": "A Game"},
        ]
        installed = [
            {"app_name": "Anemone", "install_path": "/Games/WorldOfGoo", "version": "1.2"}
        ]
        games = normalize_epic_games(owned, installed)
        self.assertEqual([game.library_id for game in games], ["epic:Cattail", "epic:Anemone"])
        world = games[1]
        self.assertTrue(world.installed)
        self.assertEqual(world.install_path, "/Games/WorldOfGoo")
        self.assertEqual(world.version, "1.2")

    def test_missing_client_has_friendly_status(self) -> None:
        with patch("mysteamwine.sources.epic.shutil.which", return_value=None):
            status = EpicSource("missing-legendary").status()
        self.assertFalse(status.available)
        self.assertFalse(status.authenticated)
        self.assertNotIn(str(Path.home()), status.message)

    def test_library_commands_use_windows_platform_and_private_config(self) -> None:
        calls: list[tuple[list[str], dict[str, str], int]] = []

        def runner(command, environment, timeout):
            calls.append((command, environment, timeout))
            payload = (
                [{"app_name": "Anemone", "app_title": "World of Goo"}]
                if command[1] == "list"
                else [{"app_name": "Anemone", "install_path": "/Games/WorldOfGoo"}]
            )
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            client = home / "legendary"
            client.write_text("", encoding="utf-8")
            client.chmod(0o755)
            with patch("pathlib.Path.home", return_value=home):
                source = EpicSource(str(client), runner=runner)
                games = source.list_games(force_refresh=True)
                self.assertEqual(len(games), 1)
                self.assertIn("Windows", calls[0][0])
                self.assertIn("--force-refresh", calls[0][0])
                config = Path(calls[0][1]["XDG_CONFIG_HOME"])
                self.assertEqual(config, source.config_root)
                self.assertEqual(os.stat(source.root).st_mode & 0o777, 0o700)
                self.assertEqual(os.stat(source.config_root).st_mode & 0o777, 0o700)

    def test_auth_code_is_not_logged_or_placed_in_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            client = Path(temporary) / "legendary"
            client.write_text("", encoding="utf-8")
            client.chmod(0o755)

            def runner(command, environment, timeout):
                if "auth" in command:
                    return subprocess.CompletedProcess(command, 1, "", "authentication rejected")
                return subprocess.CompletedProcess(command, 0, "{}", "")

            source = EpicSource(str(client), runner=runner)
            with self.assertRaisesRegex(RuntimeError, "authentication rejected") as raised:
                source.authenticate(authorization_code="super-secret-code")
            self.assertNotIn("super-secret-code", str(raised.exception))

    def test_auth_accepts_complete_epic_json_response(self) -> None:
        commands: list[list[str]] = []
        with tempfile.TemporaryDirectory() as temporary:
            client = Path(temporary) / "legendary"
            client.write_text("", encoding="utf-8")
            client.chmod(0o755)

            def runner(command, environment, timeout):
                commands.append(command)
                if command[1] == "status":
                    return subprocess.CompletedProcess(command, 0, '{"account_id":"123"}', "")
                return subprocess.CompletedProcess(command, 0, "", "")

            status = EpicSource(str(client), runner=runner).authenticate(
                authorization_code='{"authorizationCode": "short-code"}'
            )
        self.assertTrue(status.authenticated)
        self.assertIn("short-code", commands[0])

    def test_game_operations_are_non_shell_commands(self) -> None:
        commands: list[list[str]] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            client = root / "legendary"
            client.write_text("", encoding="utf-8")
            client.chmod(0o755)

            def runner(command, environment, timeout):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            source = EpicSource(str(client), runner=runner)
            source.install("Anemone", base_path=root / "games")
            source.update("Anemone")
            source.verify("Anemone")
            source.repair("Anemone")
            source.uninstall("Anemone")
        self.assertIn("--platform", commands[0])
        self.assertIn("Windows", commands[0])
        self.assertIn("--update-only", commands[1])
        self.assertEqual(commands[2][1:3], ["verify", "Anemone"])
        self.assertIn("--repair-and-update", commands[3])
        self.assertEqual(commands[4][1:4], ["-y", "uninstall", "Anemone"])

    def test_launch_receives_profile_environment(self) -> None:
        captured: dict[str, object] = {}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            client = root / "legendary"
            client.write_text("", encoding="utf-8")
            client.chmod(0o755)

            def runner(command, environment, timeout):
                captured["command"] = command
                captured["environment"] = environment
                return subprocess.CompletedProcess(command, 0, "", "")

            EpicSource(str(client), runner=runner).launch(
                "Anemone",
                wine_path=root / "wine",
                wine_prefix=root / "prefix",
                environment={"WINEDLLOVERRIDES": "d3d11=n,b"},
            )
        self.assertIn("--wine-prefix", captured["command"])
        self.assertEqual(captured["environment"]["WINEDLLOVERRIDES"], "d3d11=n,b")


if __name__ == "__main__":
    unittest.main()
