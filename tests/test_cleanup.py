"""Tests for cleanup candidate discovery."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from reelclean.core.cleanup_service import discover_cleanup_candidates
from reelclean.core.models import CleanupKind


class CleanupTests(unittest.TestCase):
    def test_discovers_sample_non_media_and_empty_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "movie.sample.mkv").write_bytes(b"video")
            (root / "movie.mkv").write_bytes(b"video")
            (root / "readme.nfo").write_text("metadata", encoding="utf-8")

            empty_dir = root / "empty_folder"
            empty_dir.mkdir()

            candidates = discover_cleanup_candidates(root)
            kinds = {item.kind for item in candidates}

            self.assertIn(CleanupKind.SAMPLE_FILE, kinds)
            self.assertIn(CleanupKind.NON_MEDIA_FILE, kinds)
            self.assertIn(CleanupKind.EMPTY_FOLDER, kinds)


if __name__ == "__main__":
    unittest.main()
