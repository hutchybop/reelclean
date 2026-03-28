"""Core ReelClean services and models."""

from .cleanup_service import discover_cleanup_candidates
from .config import (
    DirectoryOption,
    ReelCleanConfig,
    discover_directory_options,
    parse_allowed_dirs,
)
from .executor import execute_plan
from .models import (
    CleanupCandidate,
    CleanupKind,
    Decision,
    ExecutionResult,
    MovieItem,
    ProposalStatus,
    QualityResult,
    RenameProposal,
    TmdbMatch,
)
from .quality_service import scan_directory_for_quality
from .rename_service import apply_decision, plan_renames, retry_proposal
from .scan import clean_title, extract_year, find_all_movies_and_subs
from .tmdb import TMDBClient

__all__ = [
    "CleanupCandidate",
    "CleanupKind",
    "Decision",
    "DirectoryOption",
    "ExecutionResult",
    "MovieItem",
    "ProposalStatus",
    "QualityResult",
    "ReelCleanConfig",
    "RenameProposal",
    "TMDBClient",
    "TmdbMatch",
    "apply_decision",
    "clean_title",
    "discover_directory_options",
    "discover_cleanup_candidates",
    "execute_plan",
    "extract_year",
    "find_all_movies_and_subs",
    "parse_allowed_dirs",
    "plan_renames",
    "retry_proposal",
    "scan_directory_for_quality",
]
