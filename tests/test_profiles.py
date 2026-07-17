from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mysteamwine.bottle import Bottle
import mysteamwine.profiles as profiles


class CompatibilityProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="nase-profile-test-"))
        self.bottle = Bottle("Test-DXMT", root, root / "prefix", root / "logs", root / "downloads", root / "cache")
        self.source = root / "dxmt"
        self.source.mkdir()

    def test_dxvk_macos_profile_is_available_for_verified_setup(self) -> None:
        profile = profiles.profile_for("dxvk-macos-pinned-v1", "dxvk")
        self.assertTrue(profile.ready)

    def test_profile_manifest_rejects_runtime_drift(self) -> None:
        with (
            patch.object(profiles, "_wine_version", return_value="wine-11.0"),
            patch.object(profiles, "_source_fingerprint", return_value="source-a"),
            patch.object(profiles, "_runtime_id_for_source", return_value="dxmt-0.71"),
        ):
            profiles.bind_profile(
                bottle=self.bottle,
                profile_id="dxmt-wine-stable-11-v1",
                graphics_backend="dxmt",
                wine_path=Path("/runtime/wine"),
                graphics_source=self.source,
                require_ready=False,
            )

        with (
            patch.object(profiles, "_wine_version", return_value="wine-11.0"),
            patch.object(profiles, "_source_fingerprint", return_value="source-b"),
            patch.object(profiles, "_runtime_id_for_source", return_value="dxmt-0.71"),
            self.assertRaisesRegex(RuntimeError, "different compatibility stack"),
        ):
            profiles.bind_profile(
                bottle=self.bottle,
                profile_id="dxmt-wine-stable-11-v1",
                graphics_backend="dxmt",
                wine_path=Path("/runtime/wine"),
                graphics_source=self.source,
                require_ready=False,
            )

    def test_dxmt_profile_requires_wine_11(self) -> None:
        with (
            patch.object(profiles, "_wine_version", return_value="wine-10.0"),
            patch.object(profiles, "_runtime_id_for_source", return_value="dxmt-0.71"),
            self.assertRaisesRegex(RuntimeError, "Wine Stable 11"),
        ):
            profiles.bind_profile(
                bottle=self.bottle,
                profile_id="dxmt-wine-stable-11-v1",
                graphics_backend="dxmt",
                wine_path=Path("/runtime/wine"),
                graphics_source=self.source,
                require_ready=False,
            )

    def test_launch_requires_completed_profile_setup(self) -> None:
        with (
            patch.object(profiles, "_wine_version", return_value="wine-11.0"),
            patch.object(profiles, "_source_fingerprint", return_value="source-a"),
            patch.object(profiles, "_runtime_id_for_source", return_value="dxmt-0.71"),
        ):
            profiles.bind_profile(
                bottle=self.bottle,
                profile_id="dxmt-wine-stable-11-v1",
                graphics_backend="dxmt",
                wine_path=Path("/runtime/wine"),
                graphics_source=self.source,
                require_ready=False,
            )
            with self.assertRaisesRegex(RuntimeError, "needs profile setup"):
                profiles.bind_profile(
                    bottle=self.bottle,
                    profile_id="dxmt-wine-stable-11-v1",
                    graphics_backend="dxmt",
                    wine_path=Path("/runtime/wine"),
                    graphics_source=self.source,
                )
            profiles.mark_profile_ready(self.bottle)
            ready = profiles.bind_profile(
                bottle=self.bottle,
                profile_id="dxmt-wine-stable-11-v1",
                graphics_backend="dxmt",
                wine_path=Path("/runtime/wine"),
                graphics_source=self.source,
            )
            self.assertEqual(ready["setup_status"], "ready")


if __name__ == "__main__":
    unittest.main()
