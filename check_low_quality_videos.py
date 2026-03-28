#!/usr/bin/env python3

"""CLI wrapper for ReelClean quality scanning service."""

from __future__ import annotations

import sys
from pathlib import Path

from reelclean.core.config import ReelCleanConfig
from reelclean.core.quality_service import scan_directory_for_quality


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 check_low_quality_videos.py <directory>")
        return 1

    target_dir = Path(sys.argv[1]).expanduser().resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"❌ Invalid directory: {target_dir}")
        return 1

    config = ReelCleanConfig.from_env()
    results = scan_directory_for_quality(target_dir, ffprobe_bin=config.ffprobe_bin)

    print(f"\nScanning: {target_dir}\n" + "-" * 60)

    flagged = 0
    for item in results:
        if item.error:
            flagged += 1
            print(f"\n❌  {item.path}")
            print(f"   Error: {item.error}")
            continue

        if item.metadata_issues:
            flagged += 1
            print(f"\n❓  {item.path}")
            print("   Metadata issue:")
            for issue in item.metadata_issues:
                print(f"   → {issue}")
            continue

        if item.low_quality_reasons:
            flagged += 1
            print(f"\n⚠️  {item.path}")
            print(f"   Tier       : {item.tier}")
            print(f"   Resolution : {item.width}x{item.height}")
            print(f"   Bitrate    : {item.bitrate_kbps} kbps")
            for reason in item.low_quality_reasons:
                print(f"   → {reason}")

    if flagged == 0:
        print("✅ No metadata or quality issues found")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
