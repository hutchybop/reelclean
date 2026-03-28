"""Video quality analysis based on ffprobe metadata."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from .models import QualityResult


VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv"}

RESOLUTION_TIERS = {
    "SD": 0,
    "720p": 1280,
    "1080p": 1920,
    "4K": 3840,
}

MIN_BITRATE_KBPS = {
    "SD": 500,
    "720p": 750,
    "1080p": 1200,
    "4K": 6000,
}


def run_ffprobe(file_path: Path, ffprobe_bin: str = "ffprobe") -> dict | None:
    """Run ffprobe and return parsed JSON data."""

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,bit_rate",
        "-show_entries",
        "format=bit_rate",
        "-of",
        "json",
        str(file_path),
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def extract_video_info(probe_data: dict) -> tuple[int | None, int | None, int | None]:
    """Extract width, height, and bitrate from ffprobe output."""

    width: int | None = None
    height: int | None = None
    bitrate: int | None = None

    streams = probe_data.get("streams", [])
    if streams:
        first_stream = streams[0]
        width = first_stream.get("width")
        height = first_stream.get("height")
        bitrate = first_stream.get("bit_rate")

    if not bitrate:
        bitrate = probe_data.get("format", {}).get("bit_rate")

    try:
        bitrate_kbps = int(bitrate) // 1000 if bitrate else None
    except (TypeError, ValueError):
        bitrate_kbps = None

    return width, height, bitrate_kbps


def classify_resolution(width: int | None) -> str:
    """Classify the resolution tier by width."""

    if not width:
        return "Unknown"

    for tier, min_width in sorted(
        RESOLUTION_TIERS.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        if width >= min_width:
            return tier

    return "SD"


def detect_quality_issues(
    width: int | None,
    bitrate_kbps: int | None,
) -> tuple[list[str], str]:
    """Return low-quality reasons and detected tier."""

    reasons: list[str] = []
    tier = classify_resolution(width)

    if bitrate_kbps and tier in MIN_BITRATE_KBPS:
        minimum = MIN_BITRATE_KBPS[tier]
        if bitrate_kbps < minimum:
            reasons.append(
                f"Low bitrate for {tier} ({bitrate_kbps} kbps < {minimum} kbps)"
            )

    return reasons, tier


def scan_directory_for_quality(
    target_dir: Path,
    ffprobe_bin: str = "ffprobe",
) -> list[QualityResult]:
    """Scan directory recursively and return quality results for all videos."""

    results: list[QualityResult] = []
    for file_path in sorted(target_dir.rglob("*")):
        if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        probe_data = run_ffprobe(file_path, ffprobe_bin=ffprobe_bin)
        if not probe_data:
            results.append(
                QualityResult(
                    path=file_path,
                    tier="Unknown",
                    width=None,
                    height=None,
                    bitrate_kbps=None,
                    error="ffprobe could not analyze this file",
                )
            )
            continue

        width, height, bitrate_kbps = extract_video_info(probe_data)
        metadata_issues: list[str] = []
        if not width:
            metadata_issues.append("Missing width / resolution info")
        if not bitrate_kbps:
            metadata_issues.append("Missing bitrate info")

        reasons, tier = detect_quality_issues(width, bitrate_kbps)
        results.append(
            QualityResult(
                path=file_path,
                tier=tier,
                width=width,
                height=height,
                bitrate_kbps=bitrate_kbps,
                low_quality_reasons=reasons,
                metadata_issues=metadata_issues,
            )
        )

    return results
