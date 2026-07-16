from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import mysteamwine.dependencies as dependencies


class DependencyStatusTests(unittest.TestCase):
    def test_recommended_dxmt_stack_is_ready_without_optional_gptk(self) -> None:
        runtime = SimpleNamespace(id="dxmt-0.71", path="/managed/dxmt-0.71")
        with (
            patch.object(dependencies.platform, "mac_ver", return_value=("14.7", ("", "", ""), "")),
            patch.object(dependencies.platform, "python_version", return_value="3.12.0"),
            patch.object(dependencies.sys, "version_info", (3, 12)),
            patch.object(dependencies, "_rosetta_installed", return_value=True),
            patch.object(dependencies, "_command_version", return_value=(0, "wine-11.0")),
            patch.object(dependencies, "list_installed_runtimes", return_value=[runtime]),
            patch.object(dependencies.shutil, "which", return_value="/opt/homebrew/bin/winetricks"),
            patch.object(Path, "is_file", return_value=True),
            patch.object(dependencies.subprocess, "run", return_value=SimpleNamespace(stdout="arm64", returncode=0)),
        ):
            result = dependencies.dependency_status(wine_path=Path("/opt/homebrew/bin/wine"))

        self.assertTrue(result["ready"])
        self.assertEqual(result["worst_status"], "warn")
        self.assertEqual(result["missing_required"], [])

    def test_missing_core_dependencies_are_actionable(self) -> None:
        with (
            patch.object(dependencies.platform, "mac_ver", return_value=("14.0", ("", "", ""), "")),
            patch.object(dependencies.platform, "python_version", return_value="3.12.0"),
            patch.object(dependencies.sys, "version_info", (3, 12)),
            patch.object(dependencies, "_rosetta_installed", return_value=False),
            patch.object(dependencies, "_command_version", return_value=(0, "wine-10.0")),
            patch.object(dependencies, "list_installed_runtimes", return_value=[]),
            patch.object(dependencies.shutil, "which", return_value=None),
            patch.object(dependencies.subprocess, "run", return_value=SimpleNamespace(stdout="arm64", returncode=0)),
        ):
            result = dependencies.dependency_status(wine_path=Path("/missing/wine"))

        self.assertFalse(result["ready"])
        self.assertEqual(
            result["missing_required"],
            ["Rosetta 2", "Winetricks", "Wine Stable 11", "DXMT 0.71"],
        )
        failed = [check for check in result["checks"] if check["status"] == "fail"]
        self.assertTrue(all(check["fix"] for check in failed))

    def test_rosetta_requires_explicit_license_confirmation(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "explicit acceptance"):
            dependencies.dependency_install_command("rosetta")
        self.assertEqual(
            dependencies.dependency_install_command("rosetta", confirm_rosetta_license=True),
            ["/usr/sbin/softwareupdate", "--install-rosetta", "--agree-to-license"],
        )

    def test_homebrew_install_commands_do_not_use_a_shell(self) -> None:
        with patch.object(dependencies, "homebrew_path", return_value=Path("/opt/homebrew/bin/brew")):
            self.assertEqual(
                dependencies.dependency_install_command("wine-stable"),
                ["/opt/homebrew/bin/brew", "install", "--cask", "wine-stable"],
            )
            self.assertEqual(
                dependencies.dependency_install_command("winetricks"),
                ["/opt/homebrew/bin/brew", "install", "winetricks"],
            )
            self.assertEqual(
                dependencies.dependency_install_command("python"),
                ["/opt/homebrew/bin/brew", "install", "python"],
            )


if __name__ == "__main__":
    unittest.main()
