from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mysteamwine.bottle import Bottle
from mysteamwine.steam import run_steam


class SteamLaunchTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
