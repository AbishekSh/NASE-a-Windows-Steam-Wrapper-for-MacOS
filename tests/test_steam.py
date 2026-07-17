from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mysteamwine.bottle import Bottle
from mysteamwine.steam import run_steam, validate_executable_compatibility


class SteamLaunchTests(unittest.TestCase):
    def make_x86_executable(self, root: Path) -> Path:
        executable = root / "game.exe"
        payload = bytearray(256)
        payload[0:2] = b"MZ"
        payload[0x3C:0x40] = (128).to_bytes(4, "little")
        payload[128:132] = b"PE\0\0"
        payload[132:134] = (0x014C).to_bytes(2, "little")
        executable.write_bytes(payload)
        return executable

    def test_native_macos_steam_blocks_windows_steam_launch(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="nase-steam-test-"))
        bottle = Bottle(
            "Test",
            root,
            root / "prefix",
            root / "logs",
            root / "downloads",
            root / "cache",
        )

        with patch("mysteamwine.steam.native_macos_steam_is_running", return_value=True):
            code, message = run_steam(
                bottle=bottle,
                wine64_path=Path("/missing/wine"),
                wait=False,
            )

        self.assertEqual(code, 1)
        self.assertIn("Steam > Quit Steam", message)
        self.assertIn("Closing only the Steam window is not enough", message)

    def test_x86_executable_requires_wow64_runtime(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="nase-steam-test-"))
        executable = self.make_x86_executable(root)
        with (
            patch("mysteamwine.steam.supports_wow64", return_value=False),
            self.assertRaisesRegex(RuntimeError, "does not include WoW64"),
        ):
            validate_executable_compatibility(
                executable=executable,
                wine_path=root / "wine",
                graphics_backend="none",
            )

    def test_x86_executable_rejects_d3dmetal(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="nase-steam-test-"))
        executable = self.make_x86_executable(root)
        with (
            patch("mysteamwine.steam.supports_wow64", return_value=True),
            self.assertRaisesRegex(RuntimeError, "D3DMetal supports 64-bit"),
        ):
            validate_executable_compatibility(
                executable=executable,
                wine_path=root / "wine",
                graphics_backend="d3dmetal",
            )

    def test_x86_executable_accepts_dxmt_with_wow64(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="nase-steam-test-"))
        executable = self.make_x86_executable(root)
        with patch("mysteamwine.steam.supports_wow64", return_value=True):
            architecture = validate_executable_compatibility(
                executable=executable,
                wine_path=root / "wine",
                graphics_backend="dxmt",
            )
        self.assertEqual(architecture, "x86")


if __name__ == "__main__":
    unittest.main()
