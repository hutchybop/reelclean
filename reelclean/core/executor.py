"""Apply rename and cleanup operations."""

from __future__ import annotations

from pathlib import Path

from .models import (
    CleanupCandidate,
    CleanupKind,
    Decision,
    ExecutionResult,
    OperationResult,
    ProposalStatus,
    RenameProposal,
)


def _rename_path(
    source: Path,
    target: Path,
    kind: str,
    allow_overwrite: bool,
) -> OperationResult:
    if not source.exists():
        return OperationResult(
            kind=kind,
            source=source,
            target=target,
            status="failed",
            message="Source path does not exist",
        )

    if source == target:
        return OperationResult(
            kind=kind,
            source=source,
            target=target,
            status="skipped",
            message="Source already matches target",
        )

    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not allow_overwrite:
        return OperationResult(
            kind=kind,
            source=source,
            target=target,
            status="failed",
            message="Target path already exists",
        )

    try:
        source.rename(target)
    except OSError as exc:
        return OperationResult(
            kind=kind,
            source=source,
            target=target,
            status="failed",
            message=str(exc),
        )

    return OperationResult(
        kind=kind,
        source=source,
        target=target,
        status="success",
        message="Renamed successfully",
    )


def _delete_candidate(candidate: CleanupCandidate) -> OperationResult:
    path = candidate.path

    if not path.exists():
        return OperationResult(
            kind="cleanup",
            source=path,
            target=None,
            status="skipped",
            message="Path already removed",
        )

    try:
        if candidate.kind == CleanupKind.EMPTY_FOLDER:
            path.rmdir()
        else:
            path.unlink()
    except OSError as exc:
        return OperationResult(
            kind="cleanup",
            source=path,
            target=None,
            status="failed",
            message=str(exc),
        )

    return OperationResult(
        kind="cleanup",
        source=path,
        target=None,
        status="success",
        message="Deleted successfully",
    )


def execute_plan(
    proposals: list[RenameProposal],
    cleanup_candidates: list[CleanupCandidate],
    allow_overwrite: bool = False,
) -> ExecutionResult:
    """Apply accepted rename proposals and selected cleanup deletions."""

    result = ExecutionResult()

    for proposal in proposals:
        if proposal.decision != Decision.ACCEPT:
            continue

        if proposal.status in {ProposalStatus.CONFLICT, ProposalStatus.NEEDS_REVIEW}:
            result.rename_operations.append(
                OperationResult(
                    kind="rename_movie",
                    source=proposal.source_movie_path,
                    target=proposal.target_movie_path,
                    status="failed",
                    message=proposal.conflict_reason or "Proposal is not ready",
                )
            )
            continue

        if proposal.target_movie_path is None:
            result.rename_operations.append(
                OperationResult(
                    kind="rename_movie",
                    source=proposal.source_movie_path,
                    target=None,
                    status="failed",
                    message="Missing target movie path",
                )
            )
            continue

        movie_result = _rename_path(
            source=proposal.source_movie_path,
            target=proposal.target_movie_path,
            kind="rename_movie",
            allow_overwrite=allow_overwrite,
        )
        result.rename_operations.append(movie_result)

        if movie_result.status == "failed":
            continue

        for source_sub, target_sub in zip(
            proposal.source_subtitle_paths,
            proposal.target_subtitle_paths,
        ):
            subtitle_result = _rename_path(
                source=source_sub,
                target=target_sub,
                kind="rename_subtitle",
                allow_overwrite=allow_overwrite,
            )
            result.rename_operations.append(subtitle_result)

    for candidate in cleanup_candidates:
        if not candidate.selected:
            continue
        result.cleanup_operations.append(_delete_candidate(candidate))

    return result
