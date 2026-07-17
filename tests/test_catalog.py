from __future__ import annotations

import unittest

from mysteamwine.catalog import CATALOG


class RuntimeCatalogTests(unittest.TestCase):
    def test_sikarugir_wine_10_is_checksum_pinned(self) -> None:
        runtime = next(entry for entry in CATALOG if entry.id == "wine-sikarugir-10.0-r6")

        self.assertEqual(runtime.version, "10.0 revision 6")
        self.assertEqual(runtime.archive_type, "tar.xz")
        self.assertEqual(runtime.sha256, "9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2")
        self.assertTrue(runtime.download_url.endswith("WS12WineSikarugir10.0_6.tar.xz"))


if __name__ == "__main__":
    unittest.main()
