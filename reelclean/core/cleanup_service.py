"""Cleanup candidate discovery helpers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .models import CleanupCandidate, CleanupKind
from .scan import SUB_EXT, VIDEO_EXTS


MOVIE_SAMPLE_PATTERNS = [
    "sample",
    "rarbg.com",
    "etrg",
    "sample-",
    "-sample",
    "trailer",
]


def _candidate_id(kind: CleanupKind, path: Path) -> str:
    digest = hashlib.sha1(f"{kind.value}:{path}".encode("utf-8")).hexdigest()
    return digest[:12]


def _is_sample_file(file_name: str) -> bool:
    stem = Path(file_name).stem.lower()
    return any(pattern in stem for pattern in MOVIE_SAMPLE_PATTERNS)


def discover_cleanup_candidates(
    directory: Path,
    video_exts: tuple[str, ...] = VIDEO_EXTS,
    subtitle_ext: str = SUB_EXT,
) -> list[CleanupCandidate]:
    """Find sample files, non-media files, and empty folders."""

    root = directory.expanduser().resolve()
    candidates: list[CleanupCandidate] = []

    for current_root, _, files in os.walk(root):
        root_path = Path(current_root)
        for file_name in files:
            file_path = root_path / file_name
            file_suffix = file_path.suffix.lower()

            kind: CleanupKind | None = None
            if _is_sample_file(file_name):
                kind = CleanupKind.SAMPLE_FILE
            elif file_suffix not in video_exts and file_suffix != subtitle_ext:
                kind = CleanupKind.NON_MEDIA_FILE

            if kind is None:
                continue

            candidates.append(
                CleanupCandidate(
                    candidate_id=_candidate_id(kind, file_path),
                    root_dir=root,
                    path=file_path,
                    relative_path=str(file_path.relative_to(root)),
                    kind=kind,
                    selected=True,
                )
            )

    empty_folders: list[Path] = []
    for current_root, dirs, _ in os.walk(root, topdown=False):
        root_path = Path(current_root)
        for dir_name in dirs:
            dir_path = root_path / dir_name
            try:
                if not any(dir_path.iterdir()):
                    empty_folders.append(dir_path)
            except OSError:
                continue

    for dir_path in empty_folders:
        candidates.append(
            CleanupCandidate(
                candidate_id=_candidate_id(CleanupKind.EMPTY_FOLDER, dir_path),
                root_dir=root,
                path=dir_path,
                relative_path=str(dir_path.relative_to(root)),
                kind=CleanupKind.EMPTY_FOLDER,
                selected=True,
            )
        )

    candidates.sort(key=lambda item: (item.relative_path.lower(), item.kind.value))
    return candidates
