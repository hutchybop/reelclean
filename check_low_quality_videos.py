#!/usr/bin/env python3

import subprocess
import json
import sys
from pathlib import Path

# ---------------- CONFIG ----------------

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv"}

# Resolution tiers (width-based, industry standard)
RESOLUTION_TIERS = {
    "SD": 0,
    "720p": 1280,
    "1080p": 1920,
    "4K": 3840,
}

# Minimum *watchable* bitrates per tier (kbps)
MIN_BITRATE_KBPS = {
    "SD": 500,
    "720p": 750,
    "1080p": 1200,
    "4K": 6000,
}

# ----------------------------------------


def run_ffprobe(file_path):
    """Run ffprobe and return parsed JSON data."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,bit_rate",
        "-show_entries", "format=bit_rate",
        "-of", "json",
        str(file_path)
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        return None


def extract_video_info(probe_data):
    """Extract width, height and bitrate from ffprobe output."""
    width = height = bitrate = None

    streams = probe_data.get("streams", [])
    if streams:
        width = streams[0].get("width")
        height = streams[0].get("height")
        bitrate = streams[0].get("bit_rate")

    # Fallback to container bitrate
    if not bitrate:
        bitrate = probe_data.get("format", {}).get("bit_rate")

    if bitrate:
        bitrate = int(bitrate) // 1000  # convert to kbps

    return width, height, bitrate


def classify_resolution(width):
    if not width:
        return "Unknown"

    for tier, min_width in sorted(
        RESOLUTION_TIERS.items(), key=lambda x: x[1], reverse=True
    ):
        if width >= min_width:
            return tier

    return "SD"


def is_low_quality(width, height, bitrate):
    reasons = []
    tier = classify_resolution(width)

    if bitrate and tier in MIN_BITRATE_KBPS:
        min_bitrate = MIN_BITRATE_KBPS[tier]
        if bitrate < min_bitrate:
            reasons.append(
                f"Low bitrate for {tier} ({bitrate} kbps < {min_bitrate} kbps)"
            )

    return reasons, tier


def scan_directory(target_dir):
    print(f"\nScanning: {target_dir}\n" + "-" * 60)

    for file_path in Path(target_dir).rglob("*"):
        if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        probe_data = run_ffprobe(file_path)
        if not probe_data:
            print(f"\n❌  {file_path}")
            print("   Error: ffprobe could not analyze this file")
            continue

        width, height, bitrate = extract_video_info(probe_data)

        # ---- Metadata warnings (do NOT treat as quality issues) ----
        if not width or not bitrate:
            print(f"\n❓  {file_path}")
            print("   Metadata issue:")
            if not width:
                print("   → Missing width / resolution info")
            if not bitrate:
                print("   → Missing bitrate info")
            continue
        # ------------------------------------------------------------

        reasons, tier = is_low_quality(width, height, bitrate)

        if not reasons:
            continue  # Clean files stay silent

        print(f"\n⚠️  {file_path}")
        print(f"   Tier       : {tier}")
        print(f"   Resolution : {width}x{height}")
        print(f"   Bitrate    : {bitrate} kbps")
        for reason in reasons:
            print(f"   → {reason}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_low_quality_videos.py <directory>")
        sys.exit(1)

    scan_directory(sys.argv[1])


if __name__ == "__main__":
    main()
