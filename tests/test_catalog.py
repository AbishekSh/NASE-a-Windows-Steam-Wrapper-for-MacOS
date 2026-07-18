from __future__ import annotations

import unittest

from mysteamwine.catalog import CATALOG


class RuntimeCatalogTests(unittest.TestCase):
    def test_legendary_epic_client_is_checksum_pinned(self) -> None:
        entry = next(item for item in CATALOG if item.id == "legendary-python-0.20.34-macos")
        self.assertEqual(entry.kind, "source-client")
        self.assertEqual(entry.archive_type, "wheel")
        self.assertEqual(entry.sha256, "14f56c337f705346a4bfe27a14e56d60eecbe6508cc0a580ef18d1e44813136c")

    def test_sikarugir_wine_10_is_checksum_pinned(self) -> None:
        runtime = next(entry for entry in CATALOG if entry.id == "wine-sikarugir-10.0-r6")

        self.assertEqual(runtime.version, "10.0 revision 6")
        self.assertEqual(runtime.archive_type, "tar.xz")
        self.assertEqual(runtime.sha256, "9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2")
        self.assertTrue(runtime.download_url.endswith("WS12WineSikarugir10.0_6.tar.xz"))


if __name__ == "__main__":
    unittest.main()
