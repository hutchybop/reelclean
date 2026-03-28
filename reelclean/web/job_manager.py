"""In-memory job manager for ReelClean web flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterable
from uuid import uuid4

from reelclean.core.cleanup_service import discover_cleanup_candidates
from reelclean.core.executor import execute_plan
from reelclean.core.models import (
    CleanupCandidate,
    Decision,
    ExecutionResult,
    MovieItem,
    QualityResult,
    RenameProposal,
)
from reelclean.core.quality_service import scan_directory_for_quality
from reelclean.core.rename_service import apply_decision, plan_renames, retry_proposal
from reelclean.core.scan import find_all_movies_and_subs
from reelclean.core.tmdb import TMDBClient


MODE_RENAME_ONLY = "rename_only"
MODE_QUALITY_ONLY = "quality_only"
MODE_RENAME_AND_QUALITY = "rename_and_quality"

VALID_MODES = {MODE_RENAME_ONLY, MODE_QUALITY_ONLY, MODE_RENAME_AND_QUALITY}


@dataclass
class JobState:
    """State bundle for a web workflow job."""

    job_id: str
    mode: str
    root_dir: Path
    created_at: datetime
    updated_at: datetime
    status: str
    movies_by_id: dict[str, MovieItem] = field(default_factory=dict)
    proposals: list[RenameProposal] = field(default_factory=list)
    cleanup_candidates: list[CleanupCandidate] = field(default_factory=list)
    rename_result: ExecutionResult | None = None
    cleanup_result: ExecutionResult | None = None
    quality_results: list[QualityResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def includes_renaming(self) -> bool:
        """True when mode includes rename workflow."""

        return self.mode in {MODE_RENAME_ONLY, MODE_RENAME_AND_QUALITY}

    @property
    def includes_quality(self) -> bool:
        """True when mode includes quality scan workflow."""

        return self.mode in {MODE_QUALITY_ONLY, MODE_RENAME_AND_QUALITY}

    @property
    def accepted_count(self) -> int:
        """Count accepted proposals."""

        return sum(1 for item in self.proposals if item.decision == Decision.ACCEPT)

    @property
    def skipped_count(self) -> int:
        """Count skipped proposals."""

        return sum(1 for item in self.proposals if item.decision == Decision.SKIP)


class JobNotFoundError(KeyError):
    """Raised when a job id does not exist in the manager."""


def utcnow() -> datetime:
    """Return timezone-aware current UTC timestamp."""

    return datetime.now(timezone.utc)


class JobManager:
    """Thread-safe in-memory job manager."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = Lock()

    def create_job(self, mode: str, root_dir: Path, tmdb_client: TMDBClient) -> JobState:
        """Create and initialize a new job for the selected mode."""

        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode: {mode}")

        now = utcnow()
        job_id = uuid4().hex[:12]
        job = JobState(
            job_id=job_id,
            mode=mode,
            root_dir=root_dir,
            created_at=now,
            updated_at=now,
            status="created",
        )

        if mode in {MODE_RENAME_ONLY, MODE_RENAME_AND_QUALITY}:
            movies = find_all_movies_and_subs(root_dir)
            job.movies_by_id = {movie.movie_id: movie for movie in movies}
            job.proposals = plan_renames(movies, root_dir=root_dir, tmdb_client=tmdb_client)
            job.status = "planned"
        else:
            job.status = "quality_ready"

        with self._lock:
            self._jobs[job.job_id] = job

        return job

    def get_job(self, job_id: str) -> JobState:
        """Get a job by id or raise when missing."""

        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def list_jobs(self) -> list[JobState]:
        """List all jobs by newest first."""

        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda item: item.updated_at, reverse=True)
        return jobs

    def set_decision(self, job_id: str, movie_id: str, decision: Decision) -> JobState:
        """Set decision for one movie proposal."""

        job = self.get_job(job_id)
        apply_decision(job.proposals, movie_id, decision)
        job.updated_at = utcnow()
        return job

    def retry_movie(
        self,
        job_id: str,
        movie_id: str,
        search_term: str,
        tmdb_client: TMDBClient,
    ) -> JobState:
        """Retry one movie proposal with a new search term."""

        job = self.get_job(job_id)
        retry_proposal(
            proposals=job.proposals,
            movies_by_id=job.movies_by_id,
            movie_id=movie_id,
            new_search_term=search_term,
            root_dir=job.root_dir,
            tmdb_client=tmdb_client,
        )
        job.updated_at = utcnow()
        return job

    def accept_all_ready(self, job_id: str) -> JobState:
        """Set all non-conflicted proposals to accepted."""

        job = self.get_job(job_id)
        for proposal in job.proposals:
            if proposal.target_movie_path and not proposal.conflict_reason:
                proposal.decision = Decision.ACCEPT
        job.updated_at = utcnow()
        return job

    def run_rename_stage(self, job_id: str) -> JobState:
        """Execute accepted renames and prepare cleanup candidates."""

        job = self.get_job(job_id)
        if not job.includes_renaming:
            raise ValueError("Rename stage is not available for this mode")

        job.rename_result = execute_plan(
            proposals=job.proposals,
            cleanup_candidates=[],
            allow_overwrite=False,
        )

        job.cleanup_candidates = discover_cleanup_candidates(job.root_dir)
        job.status = "awaiting_cleanup"
        job.updated_at = utcnow()
        return job

    def run_quality_stage(self, job_id: str, ffprobe_bin: str) -> JobState:
        """Run quality scan and store results."""

        job = self.get_job(job_id)
        job.quality_results = scan_directory_for_quality(job.root_dir, ffprobe_bin=ffprobe_bin)
        job.updated_at = utcnow()
        job.status = "completed"
        return job

    def run_cleanup_stage(
        self,
        job_id: str,
        selected_candidate_ids: Iterable[str],
        ffprobe_bin: str,
    ) -> JobState:
        """Execute selected cleanup deletions and optional quality scan."""

        job = self.get_job(job_id)
        selected_ids = set(selected_candidate_ids)
        for candidate in job.cleanup_candidates:
            candidate.selected = candidate.candidate_id in selected_ids

        selected_candidates = [item for item in job.cleanup_candidates if item.selected]
        job.cleanup_result = execute_plan(
            proposals=[],
            cleanup_candidates=selected_candidates,
            allow_overwrite=False,
        )

        if job.includes_quality:
            job.quality_results = scan_directory_for_quality(
                job.root_dir,
                ffprobe_bin=ffprobe_bin,
            )

        job.status = "completed"
        job.updated_at = utcnow()
        return job
