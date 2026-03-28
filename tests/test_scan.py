"""Tests for scanning and title cleanup helpers."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from reelclean.core.scan import clean_title, extract_year, find_all_movies_and_subs


class ScanTests(unittest.TestCase):
    def test_extract_year(self) -> None:
        self.assertEqual(extract_year("Movie.2010.1080p.mkv"), "2010")
        self.assertIsNone(extract_year("NoYearMovie.mkv"))

    def test_clean_title(self) -> None:
        cleaned = clean_title("The.Matrix.1999.1080p.BluRay.x264-GalaxyRG.mkv")
        self.assertEqual(cleaned.lower(), "the matrix")

    def test_find_movies_and_subtitles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            movie = root / "My.Movie.2020.mkv"
            subtitle = root / "My.Movie.2020.srt"
            extra = root / "notes.txt"

            movie.write_bytes(b"video")
            subtitle.write_text("subtitle", encoding="utf-8")
            extra.write_text("junk", encoding="utf-8")

            items = find_all_movies_and_subs(root)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].movie_path, movie.resolve())
            self.assertEqual(items[0].subtitle_paths, [subtitle.resolve()])


if __name__ == "__main__":
    unittest.main()
