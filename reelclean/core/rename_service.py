"""Rename planning and decision workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .models import Decision, MovieItem, ProposalStatus, RenameProposal
from .scan import clean_title, extract_year
from .tmdb import TMDBClient


def _build_targets(
    movie: MovieItem,
    root_dir: Path,
    target_name: str,
) -> tuple[Path, Path, list[Path]]:
    target_dir = root_dir / target_name
    movie_ext = movie.movie_path.suffix
    target_movie_path = target_dir / f"{target_name}{movie_ext}"
    target_subtitle_paths = [
        target_dir / f"{target_name}{subtitle_path.suffix}"
        for subtitle_path in movie.subtitle_paths
    ]
    return target_dir, target_movie_path, target_subtitle_paths


def plan_rename_for_movie(
    movie: MovieItem,
    root_dir: Path,
    tmdb_client: TMDBClient | None,
    search_term: str | None = None,
    retry_count: int = 0,
) -> RenameProposal:
    """Build a dry-run proposal for one movie item."""

    year_hint = extract_year(search_term or movie.movie_filename)
    guessed_title = clean_title(movie.movie_filename)

    effective_term = search_term if search_term is not None else guessed_title
    cleaned_search = clean_title(effective_term)

    if cleaned_search and tmdb_client:
        tmdb_match = tmdb_client.lookup(cleaned_search, year_hint)
    else:
        tmdb_match = None

    proposal = RenameProposal(
        movie_id=movie.movie_id,
        source_movie_path=movie.movie_path,
        source_subtitle_paths=list(movie.subtitle_paths),
        guessed_title=guessed_title,
        year_hint=year_hint,
        search_term=effective_term,
        target_name=None,
        target_dir=None,
        target_movie_path=None,
        target_subtitle_paths=[],
        tmdb_match=tmdb_match,
        retry_count=retry_count,
    )

    if not tmdb_match:
        proposal.status = ProposalStatus.NEEDS_REVIEW
        proposal.notes.append("No TMDB match found")
        return proposal

    target_name = tmdb_match.display_name
    target_dir, target_movie_path, target_subtitle_paths = _build_targets(
        movie,
        root_dir,
        target_name,
    )

    proposal.target_name = target_name
    proposal.target_dir = target_dir
    proposal.target_movie_path = target_movie_path
    proposal.target_subtitle_paths = target_subtitle_paths
    proposal.status = ProposalStatus.READY
    return proposal


def _active_for_conflict_check(proposal: RenameProposal) -> bool:
    return (
        proposal.decision != Decision.SKIP
        and proposal.target_movie_path is not None
        and proposal.status != ProposalStatus.NEEDS_REVIEW
    )


def recalculate_conflicts(proposals: list[RenameProposal]) -> list[RenameProposal]:
    """Recompute conflict flags after planning or decision changes."""

    for proposal in proposals:
        proposal.conflict_reason = None
        if proposal.decision == Decision.SKIP:
            proposal.status = ProposalStatus.SKIPPED
        elif proposal.target_movie_path is None:
            proposal.status = ProposalStatus.NEEDS_REVIEW
        else:
            proposal.status = ProposalStatus.READY

    target_index: dict[str, list[RenameProposal]] = {}
    for proposal in proposals:
        if not _active_for_conflict_check(proposal):
            continue
        target_key = str(proposal.target_movie_path)
        target_index.setdefault(target_key, []).append(proposal)

    for duplicates in target_index.values():
        if len(duplicates) <= 1:
            continue
        for proposal in duplicates:
            proposal.status = ProposalStatus.CONFLICT
            proposal.conflict_reason = "Duplicate target path proposed"

    for proposal in proposals:
        if not _active_for_conflict_check(proposal):
            continue

        if proposal.target_movie_path and proposal.target_movie_path.exists():
            if proposal.target_movie_path != proposal.source_movie_path:
                proposal.status = ProposalStatus.CONFLICT
                proposal.conflict_reason = "Target movie file already exists"
                continue

        for source_path, target_path in zip(
            proposal.source_subtitle_paths,
            proposal.target_subtitle_paths,
        ):
            if target_path.exists() and target_path != source_path:
                proposal.status = ProposalStatus.CONFLICT
                proposal.conflict_reason = "Target subtitle file already exists"
                break

    return proposals


def plan_renames(
    movies: list[MovieItem],
    root_dir: Path,
    tmdb_client: TMDBClient | None,
) -> list[RenameProposal]:
    """Build dry-run proposals for all movies in the directory."""

    proposals = [
        plan_rename_for_movie(movie=movie, root_dir=root_dir, tmdb_client=tmdb_client)
        for movie in movies
    ]
    return recalculate_conflicts(proposals)


def apply_decision(
    proposals: list[RenameProposal],
    movie_id: str,
    decision: Decision,
) -> list[RenameProposal]:
    """Apply accept/skip decision for one proposal and re-evaluate conflicts."""

    for proposal in proposals:
        if proposal.movie_id == movie_id:
            proposal.decision = decision
            break
    return recalculate_conflicts(proposals)


def proposal_by_movie_id(
    proposals: list[RenameProposal],
    movie_id: str,
) -> RenameProposal | None:
    """Find proposal by movie ID."""

    for proposal in proposals:
        if proposal.movie_id == movie_id:
            return proposal
    return None


def retry_proposal(
    proposals: list[RenameProposal],
    movies_by_id: Mapping[str, MovieItem],
    movie_id: str,
    new_search_term: str,
    root_dir: Path,
    tmdb_client: TMDBClient | None,
) -> RenameProposal:
    """Rebuild proposal for a movie using a user-provided search term."""

    movie = movies_by_id.get(movie_id)
    if movie is None:
        raise KeyError(f"Unknown movie_id: {movie_id}")

    current = proposal_by_movie_id(proposals, movie_id)
    retry_count = current.retry_count + 1 if current else 1

    new_proposal = plan_rename_for_movie(
        movie=movie,
        root_dir=root_dir,
        tmdb_client=tmdb_client,
        search_term=new_search_term,
        retry_count=retry_count,
    )
    new_proposal.decision = Decision.PENDING

    replaced = False
    for index, proposal in enumerate(proposals):
        if proposal.movie_id == movie_id:
            proposals[index] = new_proposal
            replaced = True
            break

    if not replaced:
        proposals.append(new_proposal)

    recalculate_conflicts(proposals)
    return new_proposal
