"""Configuration helpers for ReelClean."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


@dataclass
class DirectoryOption:
    """Configured directory option for UI/CLI selection."""

    label: str
    path: Path


@dataclass
class ReelCleanConfig:
    """Runtime configuration loaded from environment variables."""

    tmdb_api_key: str | None
    tmdb_timeout_seconds: int = 10
    ffprobe_bin: str = "ffprobe"
    flask_secret_key: str = "reelclean-dev-secret"
    reelclean_host: str = "0.0.0.0"
    reelclean_port: int = 8000
    reelclean_allowed_dirs_raw: str | None = None
    reelclean_library_root: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ReelCleanConfig":
        """Build config from environment mapping."""

        source = env or os.environ
        timeout_raw = source.get("TMDB_TIMEOUT_SECONDS", "10")
        try:
            timeout = int(timeout_raw)
        except ValueError:
            timeout = 10

        if timeout <= 0:
            timeout = 10

        tmdb_api_key = source.get("TMDB_API_KEY")
        if tmdb_api_key:
            tmdb_api_key = tmdb_api_key.strip()
        if not tmdb_api_key:
            tmdb_api_key = None

        ffprobe_bin = source.get("FFPROBE_BIN", "ffprobe").strip() or "ffprobe"

        flask_secret_key = (
            source.get("FLASK_SECRET_KEY", "reelclean-dev-secret").strip()
            or "reelclean-dev-secret"
        )
        host = source.get("REELCLEAN_HOST", "0.0.0.0").strip() or "0.0.0.0"

        port_raw = source.get("REELCLEAN_PORT", "8000")
        try:
            port = int(port_raw)
        except ValueError:
            port = 8000
        if port <= 0:
            port = 8000

        reelclean_allowed_dirs_raw = source.get("REELCLEAN_ALLOWED_DIRS")
        library_root_raw = source.get("REELCLEAN_LIBRARY_ROOT")
        reelclean_library_root: Path | None = None
        if library_root_raw and library_root_raw.strip():
            reelclean_library_root = Path(library_root_raw.strip()).expanduser()

        return cls(
            tmdb_api_key=tmdb_api_key,
            tmdb_timeout_seconds=timeout,
            ffprobe_bin=ffprobe_bin,
            flask_secret_key=flask_secret_key,
            reelclean_host=host,
            reelclean_port=port,
            reelclean_allowed_dirs_raw=reelclean_allowed_dirs_raw,
            reelclean_library_root=reelclean_library_root,
        )

    def require_tmdb_key(self) -> str:
        """Return TMDB key or raise clear error when missing."""

        if not self.tmdb_api_key:
            raise ValueError("TMDB_API_KEY is not set")
        return self.tmdb_api_key


def parse_allowed_dirs(raw: str | None) -> list[DirectoryOption]:
    """Parse comma-separated `label:path` entries from env var."""

    if not raw:
        return []

    options: list[DirectoryOption] = []
    entries = [item.strip() for item in raw.split(",") if item.strip()]

    for entry in entries:
        label: str
        path_value: str
        if ":" in entry:
            label, path_value = entry.split(":", 1)
            label = label.strip() or Path(path_value.strip()).name
        else:
            path_value = entry
            label = Path(path_value.strip()).name or path_value.strip()

        path = Path(path_value.strip()).expanduser()
        options.append(DirectoryOption(label=label, path=path))

    return options


def discover_directory_options(config: ReelCleanConfig) -> list[DirectoryOption]:
    """Resolve configured directory options from environment settings."""

    options = parse_allowed_dirs(config.reelclean_allowed_dirs_raw)
    if options:
        return options

    root = config.reelclean_library_root
    if not root:
        return []

    root = root.expanduser()
    if not root.exists() or not root.is_dir():
        return []

    discovered: list[DirectoryOption] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if child.is_dir():
            discovered.append(DirectoryOption(label=child.name, path=child))
    return discovered
