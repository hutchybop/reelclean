"""Filesystem scanning and title normalization utilities."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from .models import MovieItem

try:
    from unidecode import unidecode

    HAS_UNIDECODE = True
except ImportError:
    HAS_UNIDECODE = False


VIDEO_EXTS = (".mkv", ".mp4", ".avi", ".mov", ".wmv")
SUB_EXT = ".srt"


def build_movie_id(movie_path: Path) -> str:
    """Build a stable ID for a movie file path."""

    digest = hashlib.sha1(str(movie_path).encode("utf-8")).hexdigest()
    return digest[:12]


def clean_title(name: str) -> str:
    """Clean a filename into a TMDB-friendly search title."""

    value = name
    if HAS_UNIDECODE:
        value = unidecode(value)

    value = os.path.splitext(value)[0]
    value = re.sub(r"\b(19|20)\d{2}\b", "", value)
    value = re.sub(r"\bddp5?\s*1\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bdd5\s*1\b", "", value, flags=re.IGNORECASE)
    value = re.sub(
        (
            r"\b(1080p|720p|2160p|4k|2k|hd|fullhd|uhd|bluray|brrip|webrip|"
            r"web[- ]?dl|hdr|sdr|10bit|8bit|x264|x265|h264|h265|hevc|avc|"
            r"aac|ac3|dts|ddp5?[-\s]?1|dd5[-\s]?1|2ch|5ch|6ch|7ch|8ch)\b"
        ),
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b(remastered|anniversary|edition|extended|uncut|theatrical|"
        r"director'?s? cut|proper|repack|internal|unrated|rated|ws|fs|hi)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b\d+\.\d+\s?(gb|mb)\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d+mb\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d+gb\b", "", value, flags=re.IGNORECASE)
    value = re.sub(
        (
            r"\b(galaxyrg|galaxy|tgx|ahashare|demonoid|yts\.[a-z]{2,3}|"
            r"korean|psa|vxt|yify|bokutox|bone|sujaid|rsg|galaxyrg265)\b"
        ),
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\[[^\]]*\]", " ", value)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[+]", " ", value)
    value = re.sub(r"[\._\-]+", " ", value)
    value = re.sub(r"\b\d+\b", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_year(text: str) -> str | None:
    """Extract a four-digit year from text."""

    match = re.search(r"\b(19|20)\d{2}\b", text)
    return match.group(0) if match else None


def find_all_movies_and_subs(
    directory: Path,
    video_exts: tuple[str, ...] = VIDEO_EXTS,
    subtitle_ext: str = SUB_EXT,
) -> list[MovieItem]:
    """Recursively find all movie files and matching subtitles."""

    root = directory.expanduser().resolve()
    movies_found: list[MovieItem] = []

    for current_root, _, files in os.walk(root):
        root_path = Path(current_root)
        file_names = list(files)

        for file_name in file_names:
            movie_path = root_path / file_name
            if movie_path.suffix.lower() not in video_exts:
                continue

            base_name = movie_path.stem.lower()
            subtitle_paths: list[Path] = []

            for candidate in file_names:
                sub_path = root_path / candidate
                if sub_path.suffix.lower() != subtitle_ext:
                    continue
                if sub_path.stem.lower() == base_name:
                    subtitle_paths.append(sub_path)

            movie_item = MovieItem(
                movie_id=build_movie_id(movie_path),
                movie_path=movie_path,
                subtitle_paths=sorted(subtitle_paths),
                directory=root_path,
                movie_filename=file_name,
            )
            movies_found.append(movie_item)

    movies_found.sort(key=lambda item: str(item.movie_path).lower())
    return movies_found
