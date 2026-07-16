from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mysteamwine.bottle import Bottle
from mysteamwine.d3dmetal import enable_d3dmetal_overrides, verify_d3dmetal_profile
from mysteamwine.gptk import inspect_gptk_installation


class GPTKTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="nase-gptk-test-"))
        self.installation = self.root / "Game Porting Toolkit 2"
        self.wine = self.installation / "bin" / "wine"
        self.wine.parent.mkdir(parents=True)
        self.wine.write_text("#!/bin/sh\necho wine-9.0-gptk\n", encoding="utf-8")
        self.wine.chmod(0o755)
        self.payload = self.installation / "lib" / "wine" / "x86_64-windows"
        self.payload.mkdir(parents=True)
        for name in ("dxgi.dll", "d3d11.dll", "d3d12.dll"):
            (self.payload / name).write_text(name, encoding="utf-8")

    def test_inspection_pairs_wine_and_payload_from_one_installation(self) -> None:
        result = inspect_gptk_installation(self.wine, self.installation)

        self.assertEqual(result["wine_version"], "wine-9.0-gptk")
        self.assertEqual(Path(result["payload_path"]), self.payload.resolve())

    def test_inspection_rejects_unrelated_payload(self) -> None:
        unrelated = self.root / "Downloads" / "d3dmetal" / "x86_64-windows"
        unrelated.mkdir(parents=True)
        (unrelated / "dxgi.dll").write_text("", encoding="utf-8")
        (unrelated / "d3d11.dll").write_text("", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "same Toolkit installation"):
            inspect_gptk_installation(self.wine, unrelated.parent)

    def test_profile_verification_reports_dlls_overrides_and_steam(self) -> None:
        bottle_root = self.root / "bottle"
        bottle = Bottle("D3DMetal", bottle_root, bottle_root / "prefix", bottle_root / "logs", bottle_root / "downloads", bottle_root / "cache")
        system32 = bottle.drive_c / "windows" / "system32"
        system32.mkdir(parents=True)
        for name in ("dxgi.dll", "d3d11.dll", "d3d12.dll"):
            (system32 / name).write_text("", encoding="utf-8")
        steam = bottle.drive_c / "Program Files (x86)" / "Steam" / "Steam.exe"
        steam.parent.mkdir(parents=True)
        steam.write_text("", encoding="utf-8")
        enable_d3dmetal_overrides(bottle)

        checks = verify_d3dmetal_profile(bottle)

        self.assertTrue(all(check["status"] == "ok" for check in checks))


if __name__ == "__main__":
    unittest.main()
