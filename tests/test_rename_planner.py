"""Tests for rename planning, conflicts, and retries."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from reelclean.core.models import Decision, TmdbMatch
from reelclean.core.rename_service import apply_decision, plan_renames, retry_proposal
from reelclean.core.scan import find_all_movies_and_subs


class FakeTMDBClient:
    """Simple TMDB stub for deterministic tests."""

    def lookup(self, title: str, year_hint: str | None = None) -> TmdbMatch | None:
        normalized = title.lower().strip()
        if "retry" in normalized:
            return TmdbMatch(
                title="Retry Film",
                year="2001",
                display_name="Retry Film (2001)",
                source_query=title,
            )
        if "movie" in normalized:
            return TmdbMatch(
                title="Shared Name",
                year="2020",
                display_name="Shared Name (2020)",
                source_query=title,
            )
        return None


class RenamePlannerTests(unittest.TestCase):
    def test_conflict_detected_and_resolved_by_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Movie.One.2020.mkv").write_bytes(b"a")
            (root / "Movie.Two.2020.mkv").write_bytes(b"b")

            movies = find_all_movies_and_subs(root)
            proposals = plan_renames(movies, root, FakeTMDBClient())

            conflict_count = sum(1 for item in proposals if item.conflict_reason)
            self.assertEqual(conflict_count, 2)

            apply_decision(proposals, movies[0].movie_id, Decision.SKIP)
            remaining_conflicts = [
                item for item in proposals if item.movie_id == movies[1].movie_id
            ][0]
            self.assertIsNone(remaining_conflicts.conflict_reason)

    def test_retry_updates_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            movie_file = root / "Unknown.Title.2020.mkv"
            movie_file.write_bytes(b"a")

            movies = find_all_movies_and_subs(root)
            proposals = plan_renames(movies, root, FakeTMDBClient())
            self.assertIsNone(proposals[0].target_name)

            updated = retry_proposal(
                proposals=proposals,
                movies_by_id={movie.movie_id: movie for movie in movies},
                movie_id=movies[0].movie_id,
                new_search_term="retry title",
                root_dir=root,
                tmdb_client=FakeTMDBClient(),
            )

            self.assertEqual(updated.retry_count, 1)
            self.assertEqual(updated.target_name, "Retry Film (2001)")


if __name__ == "__main__":
    unittest.main()
