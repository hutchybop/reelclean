"""Tests for environment configuration parsing."""

from __future__ import annotations

import unittest

from reelclean.core.config import ReelCleanConfig, parse_allowed_dirs


class ConfigTests(unittest.TestCase):
    def test_from_env_parses_values(self) -> None:
        config = ReelCleanConfig.from_env(
            {
                "TMDB_API_KEY": "abc123",
                "TMDB_TIMEOUT_SECONDS": "15",
                "FFPROBE_BIN": "custom-ffprobe",
            }
        )

        self.assertEqual(config.tmdb_api_key, "abc123")
        self.assertEqual(config.tmdb_timeout_seconds, 15)
        self.assertEqual(config.ffprobe_bin, "custom-ffprobe")

    def test_from_env_uses_defaults_for_invalid_timeout(self) -> None:
        config = ReelCleanConfig.from_env(
            {
                "TMDB_TIMEOUT_SECONDS": "bad",
            }
        )
        self.assertEqual(config.tmdb_timeout_seconds, 10)

    def test_parse_allowed_dirs(self) -> None:
        options = parse_allowed_dirs("Movies:/media/movies,/tmp/downloads")
        self.assertEqual(len(options), 2)
        self.assertEqual(options[0].label, "Movies")
        self.assertEqual(str(options[0].path), "/media/movies")
        self.assertEqual(options[1].label, "downloads")


if __name__ == "__main__":
    unittest.main()
