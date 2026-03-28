"""Data models shared by ReelClean services."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Decision(str, Enum):
    """User decision for a rename proposal."""

    PENDING = "pending"
    ACCEPT = "accept"
    SKIP = "skip"


class ProposalStatus(str, Enum):
    """Planner status for a rename proposal."""

    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    CONFLICT = "conflict"
    SKIPPED = "skipped"


class CleanupKind(str, Enum):
    """Cleanup candidate type."""

    SAMPLE_FILE = "sample_file"
    NON_MEDIA_FILE = "non_media_file"
    EMPTY_FOLDER = "empty_folder"


@dataclass
class MovieItem:
    """A discovered movie file and related subtitles."""

    movie_id: str
    movie_path: Path
    subtitle_paths: list[Path]
    directory: Path
    movie_filename: str


@dataclass
class TmdbMatch:
    """Best-effort TMDB match for a movie search."""

    title: str
    year: str
    display_name: str
    source_query: str


@dataclass
class RenameProposal:
    """Dry-run rename proposal for a movie item."""

    movie_id: str
    source_movie_path: Path
    source_subtitle_paths: list[Path]
    guessed_title: str
    year_hint: Optional[str]
    search_term: str
    target_name: Optional[str]
    target_dir: Optional[Path]
    target_movie_path: Optional[Path]
    target_subtitle_paths: list[Path]
    tmdb_match: Optional[TmdbMatch]
    decision: Decision = Decision.PENDING
    status: ProposalStatus = ProposalStatus.NEEDS_REVIEW
    conflict_reason: Optional[str] = None
    notes: list[str] = field(default_factory=list)
    retry_count: int = 0


@dataclass
class CleanupCandidate:
    """A file or directory that may be deleted in cleanup."""

    candidate_id: str
    root_dir: Path
    path: Path
    relative_path: str
    kind: CleanupKind
    selected: bool = True


@dataclass
class QualityResult:
    """Quality scan outcome for one media file."""

    path: Path
    tier: str
    width: Optional[int]
    height: Optional[int]
    bitrate_kbps: Optional[int]
    low_quality_reasons: list[str] = field(default_factory=list)
    metadata_issues: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def is_low_quality(self) -> bool:
        """True when the file fails quality thresholds."""

        return bool(self.low_quality_reasons)


@dataclass
class OperationResult:
    """Outcome for a single filesystem operation."""

    kind: str
    source: Optional[Path]
    target: Optional[Path]
    status: str
    message: str


@dataclass
class ExecutionResult:
    """Aggregated execution result for rename and cleanup operations."""

    rename_operations: list[OperationResult] = field(default_factory=list)
    cleanup_operations: list[OperationResult] = field(default_factory=list)

    @property
    def successful_operations(self) -> int:
        """Count operations that completed successfully."""

        all_ops = self.rename_operations + self.cleanup_operations
        return sum(1 for op in all_ops if op.status == "success")

    @property
    def failed_operations(self) -> int:
        """Count operations that failed."""

        all_ops = self.rename_operations + self.cleanup_operations
        return sum(1 for op in all_ops if op.status == "failed")
