#!/usr/bin/env python3

"""Interactive CLI wrapper for ReelClean core rename workflow."""

from __future__ import annotations

import sys
from pathlib import Path

from reelclean.core.cleanup_service import discover_cleanup_candidates
from reelclean.core.config import ReelCleanConfig
from reelclean.core.executor import execute_plan
from reelclean.core.models import CleanupKind, Decision, ProposalStatus
from reelclean.core.rename_service import (
    apply_decision,
    plan_renames,
    proposal_by_movie_id,
    retry_proposal,
)
from reelclean.core.scan import find_all_movies_and_subs
from reelclean.core.tmdb import TMDBClient


def _prompt_directory() -> Path:
    while True:
        value = input("Enter the directory path containing movie files: ").strip()
        if not value:
            print("❌ Directory path cannot be empty")
            continue

        path = Path(value).expanduser().resolve()
        if not path.exists():
            print(f"❌ Directory '{path}' does not exist")
            continue
        if not path.is_dir():
            print(f"❌ '{path}' is not a directory")
            continue
        return path


def _prompt_yes_no(message: str) -> bool:
    while True:
        choice = input(f"{message} (y/n): ").strip().lower()
        if choice in {"y", "n"}:
            return choice == "y"
        print("Please enter 'y' or 'n'")


def _show_proposal(movie_filename: str, proposal) -> None:
    print("\n" + "=" * 60)
    print(f"🎬 Processing: {movie_filename}")
    print(f"🔤 Guessed title: {proposal.guessed_title or '(none)'}")
    if proposal.year_hint:
        print(f"📅 Year hint: {proposal.year_hint}")

    if proposal.tmdb_match:
        print(f"📽️  Proposed match: {proposal.tmdb_match.display_name}")
    else:
        print("❌ No TMDB match found")

    if proposal.status == ProposalStatus.CONFLICT:
        print(f"⚠️  Conflict: {proposal.conflict_reason}")


def _review_proposals(
    proposals,
    movies_by_id,
    root_dir: Path,
    tmdb_client: TMDBClient,
):
    for movie_id, movie in movies_by_id.items():
        while True:
            proposal = proposal_by_movie_id(proposals, movie_id)
            if proposal is None:
                break

            _show_proposal(movie.movie_filename, proposal)
            prompt = "Accept, retry, or skip? (a/r/s): "
            choice = input(prompt).strip().lower()

            if choice == "a":
                apply_decision(proposals, movie_id, Decision.ACCEPT)
                break

            if choice == "s":
                apply_decision(proposals, movie_id, Decision.SKIP)
                break

            if choice == "r":
                search_term = input("Enter alternative search term: ").strip()
                if not search_term:
                    print("❌ Search term cannot be empty")
                    continue
                retry_proposal(
                    proposals=proposals,
                    movies_by_id=movies_by_id,
                    movie_id=movie_id,
                    new_search_term=search_term,
                    root_dir=root_dir,
                    tmdb_client=tmdb_client,
                )
                continue

            print("Please enter 'a', 'r', or 's'")


def _print_plan_summary(proposals) -> None:
    accepted = sum(1 for proposal in proposals if proposal.decision == Decision.ACCEPT)
    skipped = sum(1 for proposal in proposals if proposal.decision == Decision.SKIP)
    conflicts = sum(1 for proposal in proposals if proposal.status == ProposalStatus.CONFLICT)
    review = sum(
        1
        for proposal in proposals
        if proposal.status == ProposalStatus.NEEDS_REVIEW
        and proposal.decision == Decision.PENDING
    )

    print("\n" + "=" * 60)
    print("Dry-run summary")
    print(f"✅ Accepted: {accepted}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"⚠️  Conflicts: {conflicts}")
    print(f"❓ Needs review: {review}")


def _select_cleanup_candidates(candidates):
    if not candidates:
        return []

    sample_count = sum(1 for item in candidates if item.kind == CleanupKind.SAMPLE_FILE)
    non_media_count = sum(
        1 for item in candidates if item.kind == CleanupKind.NON_MEDIA_FILE
    )
    empty_count = sum(1 for item in candidates if item.kind == CleanupKind.EMPTY_FOLDER)

    print("\nCleanup candidates")
    print(f"🎬 Sample files: {sample_count}")
    print(f"📄 Non-media files: {non_media_count}")
    print(f"📁 Empty folders: {empty_count}")

    for candidate in candidates[:30]:
        print(f"   - {candidate.relative_path} ({candidate.kind.value})")
    if len(candidates) > 30:
        print(f"   ... and {len(candidates) - 30} more")

    delete_all = _prompt_yes_no(
        f"Delete all {len(candidates)} cleanup candidates after rename"
    )
    if not delete_all:
        for candidate in candidates:
            candidate.selected = False

    return candidates


def _print_execution_result(result) -> None:
    print("\n" + "=" * 60)
    print("Execution summary")
    print(f"✅ Successful operations: {result.successful_operations}")
    print(f"❌ Failed operations: {result.failed_operations}")

    failed_ops = [
        *[op for op in result.rename_operations if op.status == "failed"],
        *[op for op in result.cleanup_operations if op.status == "failed"],
    ]
    if failed_ops:
        print("\nFailed operations:")
        for op in failed_ops:
            source = str(op.source) if op.source else "-"
            target = str(op.target) if op.target else "-"
            print(f"   - {op.kind}: {source} -> {target} ({op.message})")


def main() -> int:
    print("🎬 Interactive Movie File Renamer (Core-backed)")
    print("=" * 50)

    config = ReelCleanConfig.from_env()
    tmdb_client = TMDBClient(
        api_key=config.tmdb_api_key,
        timeout_seconds=config.tmdb_timeout_seconds,
    )
    if not config.tmdb_api_key:
        print("⚠️  TMDB_API_KEY is not set. Lookup retries will likely fail.")

    root_dir = _prompt_directory()
    movies = find_all_movies_and_subs(root_dir)
    if not movies:
        print("❌ No movie files found")
        return 0

    print(f"\n📂 Found {len(movies)} movie file(s):")
    for index, movie in enumerate(movies, 1):
        print(f"   {index}. {movie.movie_filename}")

    if not _prompt_yes_no(f"Proceed with dry-run planning for {len(movies)} movies"):
        print("👋 Exiting")
        return 0

    proposals = plan_renames(movies, root_dir=root_dir, tmdb_client=tmdb_client)
    movies_by_id = {movie.movie_id: movie for movie in movies}

    _review_proposals(
        proposals=proposals,
        movies_by_id=movies_by_id,
        root_dir=root_dir,
        tmdb_client=tmdb_client,
    )
    _print_plan_summary(proposals)

    if not _prompt_yes_no("Apply accepted renames now"):
        print("Dry run complete. No files were changed.")
        return 0

    cleanup_candidates = discover_cleanup_candidates(root_dir)
    selected_cleanup = _select_cleanup_candidates(cleanup_candidates)

    result = execute_plan(
        proposals=proposals,
        cleanup_candidates=selected_cleanup,
        allow_overwrite=False,
    )
    _print_execution_result(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n\n👋 Script interrupted by user")
        raise SystemExit(0)
