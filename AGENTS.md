# Agents Guidelines

## Build/Test Commands
- Run main interactive script: `python3 rename_films_input.py`
- Check video quality: `python3 check_low_quality_videos.py /path/to/videos`
- Install dependencies: `python3 -m pip install requests unidecode cinemagoer`
- Virtual environment activation: `source rename_env/bin/activate` (if available)

## Code Style

### Python Version & Formatting
- Use Python 3.12+ (shebang: `#!/usr/bin/env python3`)
- Follow PEP 8 style guidelines
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 88 characters (Black formatter standard)

### Import Organization
Import order: stdlib → third-party → local modules
```python
# Standard library
import os
import re
import sys
from pathlib import Path

# Third-party
import requests
from unidecode import unidecode

# Local modules
```

### Naming Conventions
- **Constants**: `UPPER_SNAKE_CASE` at module level
- **Functions**: `snake_case` with clear, descriptive names
- **Variables**: `snake_case`, avoid abbreviations except common ones (e.g., `dir`, `sub`)
- **Private functions**: prefix with underscore if not part of public API

### Type Hints
- Use type hints where beneficial for clarity and IDE support
- Not strictly required but encouraged for function signatures
- Use `Optional[str]` for parameters that can be None
- Use `List[str]` for lists, `Dict[str, str]` for dictionaries

### Documentation
- Use docstrings for all functions and modules
- Triple quotes `"""` for docstrings
- Include parameter descriptions and return types in docstrings
- Use inline comments sparingly, only for complex logic

### Error Handling
- Use try/except for API calls, file operations, and external commands
- Return None or early exit for failures, print descriptive error messages
- Include timeouts for network requests (10 seconds default)
- Check file/directory existence before operations
- Use specific exception types when possible (e.g., `OSError`, `subprocess.CalledProcessError`)

## Dependencies

### Core Dependencies
- **requests**: HTTP calls to TMDB API
- **unidecode**: Unicode to ASCII conversion for title cleaning
- **cinemagoer**: IMDb lookup alternative (optional)

### External Tools
- **ffprobe**: Required by `check_low_quality_videos.py` for video analysis
- **ffmpeg**: Typically installed alongside ffprobe

## Project Structure
- `rename_films_input.py`: Main interactive movie renaming script
- `check_low_quality_videos.py`: Video quality checker
- `rename_env/`: Python virtual environment (Python 3.12.3)
- `AGENTS.md`: This file - guidelines for coding agents

## API Usage Guidelines

### TMDB Integration
- Use the provided TMDB API key (for non-production use)
- Implement fallback strategies for title lookups
- Include proper error handling for network failures
- Cache results when appropriate to avoid rate limiting

### Video Processing
- Support common video formats: .mkv, .mp4, .avi, .mov, .wmv
- Handle subtitle files: .srt
- Use pathlib for cross-platform file operations
- Preserve file extensions during renaming

## Testing & Debugging
- Test with small directories first
- Verify API connectivity before bulk operations
- Use print statements for debugging (structured with emojis for clarity)
- Include user confirmation for destructive operations
- Handle KeyboardInterrupt gracefully

## Security Considerations
- Never commit API keys or credentials to repository
- Validate user input paths to prevent directory traversal
- Use absolute paths for file operations
- Check permissions before file operations

## Code Patterns

### File Operations
```python
# Preferred pattern for file operations
try:
    os.rename(source_path, target_path)
    print(f"✅ Moved: {os.path.basename(source_path)}")
except OSError as e:
    print(f"❌ Error moving {source_path}: {e}")
```

### API Calls
```python
# Preferred pattern for API calls
try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()
except requests.RequestException as e:
    print(f"❌ API request failed: {e}")
    return None
```

### User Input
```python
# Preferred pattern for user confirmation
while True:
    confirm = input("Continue? (y/n): ").lower().strip()
    if confirm in ('y', 'n'):
        break
    print("Please enter 'y' or 'n'")
```