"""Tests for quality classification helpers."""

from __future__ import annotations

import unittest

from reelclean.core.quality_service import classify_resolution, detect_quality_issues


class QualityServiceTests(unittest.TestCase):
    def test_classify_resolution(self) -> None:
        self.assertEqual(classify_resolution(3840), "4K")
        self.assertEqual(classify_resolution(1920), "1080p")
        self.assertEqual(classify_resolution(1280), "720p")
        self.assertEqual(classify_resolution(None), "Unknown")

    def test_detect_quality_issues(self) -> None:
        reasons, tier = detect_quality_issues(width=1920, bitrate_kbps=500)
        self.assertEqual(tier, "1080p")
        self.assertTrue(reasons)

        reasons_ok, tier_ok = detect_quality_issues(width=1920, bitrate_kbps=2500)
        self.assertEqual(tier_ok, "1080p")
        self.assertEqual(reasons_ok, [])


if __name__ == "__main__":
    unittest.main()
