# ReelClean Agent Guidelines

## Project Overview
ReelClean is a Flask web application for managing media library organization. It scans movie directories, queries TMDB for metadata, proposes renaming, and optionally checks video quality.

## Build/Test Commands

### Running the Application
```bash
# Install dependencies
pip3 install -r requirements.txt

# Run Flask app (development)
python3 app.py

# Run with gunicorn (production)
gunicorn -w 2 -b 0.0.0.0:8000 "app:create_app()"
```

### Running Tests
```bash
# Run all tests
python3 -m unittest discover -s tests

# Run a single test file
python3 -m unittest tests.test_config

# Run a specific test
python3 -m unittest tests.test_config.ConfigTests.test_from_env_parses_values
```

### Environment Variables
```bash
# Required for TMDB lookups
TMDB_API_KEY=your_api_key

# Optional configuration
TMDB_TIMEOUT_SECONDS=10
FFPROBE_BIN=ffprobe
FLASK_SECRET_KEY=your_secret
REELCLEAN_HOST=0.0.0.0
REELCLEAN_PORT=8000
REELCLEAN_ALLOWED_DIRS="Movies:/path/to/movies,Downloads:/path/to/downloads"
REELCLEAN_LIBRARY_ROOT=/path/to/media
```

## Code Style

### Python Version & Formatting
- Use Python 3.12+ (shebang: `#!/usr/bin/env python3`)
- Include `from __future__ import annotations` at the top of all files
- Follow PEP 8 style guidelines
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 88 characters (Black formatter standard)

### Import Organization
Order imports: stdlib → third-party → local modules
```python
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from flask import Flask, abort, redirect, render_template, request

from reelclean.core.config import ReelCleanConfig
from reelclean.core.models import Decision
from reelclean.core.tmdb import TMDBClient
from reelclean.web.job_manager import JobManager
```

### Naming Conventions
- **Constants**: `UPPER_SNAKE_CASE` at module level (e.g., `TMDB_URL`)
- **Classes**: `PascalCase` (e.g., `ReelCleanConfig`, `TMDBClient`)
- **Functions/variables**: `snake_case` with descriptive names
- **Private methods**: prefix with underscore (e.g., `_search`)
- **Dataclass fields**: `snake_case`

### Type Hints
- Use modern union syntax (Python 3.10+): `str | None` instead of `Optional[str]`
- Use `dict[str, Any]` for untyped dictionaries
- Include return types on all functions
```python
def lookup(self, title: str, year_hint: str | None = None) -> TmdbMatch | None:
```

### Dataclasses for Models
Use `@dataclass` for simple data containers:
```python
@dataclass
class TmdbMatch:
    title: str
    year: str
    display_name: str
    source_query: str
```

### Documentation
- Use docstrings for all public functions and classes
- Triple quotes `"""` for docstrings
- Include description, args, and return types
```python
def lookup(self, title: str, year_hint: str | None = None) -> TmdbMatch | None:
    """Lookup a movie title with fallback strategies.

    Args:
        title: Raw movie filename to search.
        year_hint: Optional year for better matching.

    Returns:
        Best match from TMDB or None if no results.
    """
```

## Error Handling

### API Calls
```python
try:
    response = requests.get(url, params=params, timeout=self.timeout_seconds)
    response.raise_for_status()
    payload = response.json()
except (requests.RequestException, ValueError):
    return []  # Return empty on failure, log if needed
```

### File Operations
```python
try:
    path = option.path.expanduser().resolve()
except OSError:
    continue  # Skip invalid paths
```

### Validation
- Use early returns for invalid inputs
- Raise descriptive errors for missing required config
```python
def require_tmdb_key(self) -> str:
    if not self.tmdb_api_key:
        raise ValueError("TMDB_API_KEY is not set")
    return self.tmdb_api_key
```

## Project Structure
```
reelclean/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── config.py       # Configuration from environment
│   ├── models.py       # Dataclasses (Decision, TmdbMatch, etc.)
│   ├── tmdb.py         # TMDB API client
│   ├── scan.py         # Directory scanning, title cleaning
│   ├── rename_service.py
│   ├── quality_service.py
│   ├── cleanup_service.py
│   └── executor.py
├── web/
│   ├── __init__.py
│   └── job_manager.py  # Job state machine
tests/
│   ├── test_config.py
│   ├── test_scan.py
│   ├── test_tmdb.py
│   └── ...
app.py                  # Flask routes and app factory
templates/              # Jinja2 templates
static/                 # CSS, JS, assets
```

## Testing Guidelines
- Use `unittest.TestCase` for all tests
- Use `tempfile.TemporaryDirectory()` for file operations
- Test dataclass serialization/deserialization
- Mock external APIs when needed
- Include edge cases: empty inputs, invalid values, network errors

## Security Considerations
- Never commit API keys or secrets to repository
- Use `.env.example` for required variables
- Validate user input paths to prevent directory traversal
- Use absolute paths for file operations
- Check file/directory existence before operations
