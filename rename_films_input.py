#!/usr/bin/env python3

"""
INTERACTIVE FILM RENAMING SCRIPT

This script helps users organize movie files by:
1. Scanning a user-specified directory for movie files and subtitles
2. Looking up movies on TMDB interactively
3. Creating properly named directories: "Movie_name (release_year)"
4. Renaming movie and subtitle files consistently
5. Offering cleanup of extra files

Features:
- Interactive TMDB lookup with confirmation
- Retry mechanism for incorrect matches
- Recursive scanning of subdirectories
- User confirmation for file deletions
"""

import os
import re
import sys
import requests

try:
    from unidecode import unidecode
    HAS_UNIDECODE = True
except ImportError:
    HAS_UNIDECODE = False
    print("⚠️  Warning: 'unidecode' module not found. Install with: pip install unidecode")
    print("   Will proceed without unicode normalization (may affect title cleaning)")

VIDEO_EXTS = (".mkv", ".mp4", ".avi", ".mov", ".wmv")
SUB_EXT = ".srt"

# Movie sample files that should be treated as unwanted
# Add patterns to identify sample/trailer files that should be deleted
MOVIE_SAMPLE_PATTERNS = [
    "sample",
    "rarbg.com",
    "etrg",
    "sample-",
    "-sample",
    "trailer"
]

TMDB_API_KEY = "bd3f5c8ddd07106add8b1b0261392048"
TMDB_URL = "https://api.themoviedb.org/3/search/movie"


# ------------------ reused helper functions ------------------

def clean_title(name):
    """Clean movie title for TMDB lookup"""
    if HAS_UNIDECODE:
        name = unidecode(name)
    name = os.path.splitext(name)[0]

    # Remove year first
    name = re.sub(r'\b(19|20)\d{2}\b', '', name)
    
    # Clean up audio patterns first (more aggressive)
    name = re.sub(r'\bddp5?\s*1\b', '', name, flags=re.I)
    name = re.sub(r'\bdd5\s*1\b', '', name, flags=re.I)
    name = re.sub(r'\b(ddp5|dd5)\s*1\b', '', name, flags=re.I)
    
    # Remove technical patterns that might interfere with title parsing
    name = re.sub(
        r'\b(1080p|720p|2160p|4k|2k|hd|fullhd|uhd|bluray|brrip|webrip|web[- ]?dl|'
        r'hdr|sdr|10bit|8bit|'
        r'x264|x265|h264|h265|hevc|avc|'
        r'aac|ac3|dts|ddp5?[-\s]?1|dd5[-\s]?1|2ch|5ch|6ch|7ch|8ch)\b',
        '',
        name,
        flags=re.I
    )
    
    # Clean up any remaining audio pattern parts
    name = re.sub(r'\bddp5\b', '', name, flags=re.I)
    name = re.sub(r'\bdd5\b', '', name, flags=re.I)
    name = re.sub(r'\b\d+\b', '', name)  # Remove standalone numbers
    
    # Remove quality labels and editions (but keep single letters like X)
    name = re.sub(
        r'\b(remastered|anniversary|edition|extended|uncut|theatrical|director\'?s? cut|proper|repack|internal|unrated|rated|ws|fs|hi)\b',
        '',
        name,
        flags=re.I
    )

    # Remove file sizes
    name = re.sub(r'\b\d+\.\d+\s?(gb|mb)\b', '', name, flags=re.I)
    name = re.sub(r'\b\d+mb\b', '', name, flags=re.I)
    name = re.sub(r'\b\d+gb\b', '', name, flags=re.I)

    # Remove release groups
    name = re.sub(r'\b(galaxyrg|galaxy|tgx|ahashare|demonoid|yts\.[a-z]{2,3}|yts\.[lt]|korean|psa|vxt|yify|bokutox|bone|sujaid|rsg)\b', '', name, flags=re.I)
    name = re.sub(r'\b(galaxyrg265)\b', '', name, flags=re.I)

    # Remove bracketed content that contains years or technical info
    name = re.sub(r'\[[^\]]*(?:bluray|1080p|720p|dts|aac|x264|x265|remastered|yify|bokutox|\d{4})[^\]]*\]', '', name, flags=re.I)
    name = re.sub(r'\([^)]*(?:bluray|1080p|720p|dts|aac|x264|x265|remastered|yify|bokutox|\d{4})[^)]*\)', '', name, flags=re.I)

    # Clean up special characters and separators
    name = re.sub(r'[+]', ' ', name)
    name = re.sub(r'[\._\-]+', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    
    # Remove leftover parentheses
    name = re.sub(r'\(\s*\)', '', name)
    name = re.sub(r'\[\s*\]', '', name)

    # Remove remaining single letters at end of titles (but not "X" from "American History X")
    words = name.split()
    cleaned_words = []
    for i, word in enumerate(words):
        if len(word) == 1 and word.isupper() and i == len(words) - 1:
            # Only remove single capital letters if they're not likely part of title
            if word not in ['X', 'V', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']:
                continue
        cleaned_words.append(word)
    
    name = ' '.join(cleaned_words)
    
    # Final cleanup of extra spaces
    name = re.sub(r'\s+', ' ', name)

    return name.strip()


def extract_year(text):
    """Extract year from text"""
    m = re.search(r'\b(19|20)\d{2}\b', text)
    return m.group(0) if m else None


def tmdb_lookup(title, year_hint=None):
    """Lookup movie on TMDB with multiple fallback strategies"""
    def search_tmdb(query, year=None):
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "include_adult": False,
        }
        if year:
            params["year"] = year
        
        try:
            r = requests.get(TMDB_URL, params=params, timeout=10)
            if r.status_code != 200:
                return None
            return r.json().get("results", [])
        except:
            return None

    def select_best_match(results, original_query, year_hint):
        if not results:
            return None
            
        # Prioritize exact title matches
        original_clean = original_query.lower().strip()
        
        for movie in results:
            title = movie.get('title', '').lower()
            release = movie.get("release_date", "")
            
            # Exact match with year hint
            if year_hint and release.startswith(year_hint) and original_clean == title:
                return f"{movie['title']} ({year_hint})"
            
            # Exact match without year consideration
            if original_clean == title:
                year = release.split('-')[0] if release else '????'
                return f"{movie['title']} ({year})"
        
        # If we have a year hint, prioritize matches from that year
        if year_hint:
            for movie in results:
                release = movie.get("release_date", "")
                movie_year = release.split('-')[0] if release else None
                if movie_year == year_hint:
                    return f"{movie['title']} ({year_hint})"
            
            # If no exact year match, try closest year
            year_diffs = []
            for movie in results:
                release = movie.get("release_date", "")
                movie_year = release.split('-')[0] if release else None
                if movie_year and movie_year.isdigit():
                    diff = abs(int(movie_year) - int(year_hint))
                    year_diffs.append((diff, movie, movie_year))
            
            if year_diffs:
                year_diffs.sort()  # Sort by year difference
                best_diff, best_movie, best_year = year_diffs[0]
                if best_diff <= 5:  # Only accept if within 5 years
                    return f"{best_movie['title']} ({best_year})"
        
        # Special cases
        if 'dark knight' in original_clean:
            for movie in results:
                title = movie.get('title', '').lower()
                if 'dark knight' in title and 'unmasked' not in title and 'psychology' not in title:
                    release = movie.get("release_date", "")
                    year = release.split('-')[0] if release else '????'
                    return f"{movie['title']} ({year})"
        
        if 'wall' in original_clean:
            for movie in results:
                title = movie.get('title', '').lower()
                if 'wall-e' in title:
                    release = movie.get("release_date", "")
                    year = release.split('-')[0] if release else '????'
                    return f"{movie['title']} ({year})"
        
        if 'interstellar' in original_clean:
            for movie in results:
                title = movie.get('title', '').lower()
                if 'interstellar' in title:
                    release = movie.get("release_date", "")
                    year = release.split('-')[0] if release else '????'
                    return f"{movie['title']} ({year})"
        
        # Fallback to first result
        movie = results[0]
        release = movie.get("release_date", "")
        if not release:
            return None
        
        year = release.split('-')[0]
        return f"{movie['title']} ({year})"

    # Strategy 1: Try with original cleaned title + year
    results = search_tmdb(title, year_hint)
    if results:
        match = select_best_match(results, title, year_hint)
        if match:
            return match
    
    # Strategy 2: Try without year if no results
    results = search_tmdb(title)
    if results:
        match = select_best_match(results, title, year_hint)
        if match:
            return match
    
    # Strategy 3: Try with first 2-3 words if title is long
    if len(title.split()) > 3:
        shorter_query = " ".join(title.split()[:3])
        results = search_tmdb(shorter_query, year_hint)
        if results:
            match = select_best_match(results, shorter_query, year_hint)
            if match:
                return match
        results = search_tmdb(shorter_query)
        if results:
            match = select_best_match(results, shorter_query, year_hint)
            if match:
                return match
    
    # Strategy 4: Try with first 2 words
    if len(title.split()) > 2:
        shorter_query = " ".join(title.split()[:2])
        results = search_tmdb(shorter_query, year_hint)
        if results:
            match = select_best_match(results, shorter_query, year_hint)
            if match:
                return match
        results = search_tmdb(shorter_query)
        if results:
            match = select_best_match(results, shorter_query, year_hint)
            if match:
                return match
    
    # Strategy 5: Try with year only (if available)
    if year_hint:
        results = search_tmdb(year_hint)
        if results:
            match = select_best_match(results, year_hint, year_hint)
            if match:
                return match
    
    return None


# ------------------ new interactive functions ------------------

def get_directory_from_user():
    """Get directory path from user"""
    while True:
        directory = input("Enter the directory path containing movie files: ").strip()
        
        if not directory:
            print("❌ Directory path cannot be empty.")
            continue
            
        if not os.path.exists(directory):
            print(f"❌ Directory '{directory}' does not exist.")
            continue
            
        if not os.path.isdir(directory):
            print(f"❌ '{directory}' is not a directory.")
            continue
            
        return os.path.abspath(directory)


def find_all_movies_and_subs(directory):
    """Recursively find all movie files and corresponding subtitles"""
    movies_found = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_lower = file.lower()
            full_path = os.path.join(root, file)
            
            if file_lower.endswith(VIDEO_EXTS):
                # Found a movie file, look for corresponding subtitle
                base_name = os.path.splitext(file)[0]
                subtitle_files = []
                
                # Look for subtitle files with similar names in the same directory
                for sub_file in files:
                    sub_lower = sub_file.lower()
                    if sub_lower.endswith(SUB_EXT):
                        sub_path = os.path.join(root, sub_file)
                        # Check if subtitle name matches movie name (ignoring extensions)
                        sub_base = os.path.splitext(sub_file)[0]
                        if sub_base.lower() == base_name.lower():
                            subtitle_files.append(sub_path)
                
                movies_found.append({
                    'movie_path': full_path,
                    'subtitle_paths': subtitle_files,
                    'directory': root,
                    'movie_filename': file
                })
    
    return movies_found


def get_tmdb_confirmation(title_guess, year_hint, movie_info=None):
    """Get TMDB lookup with user confirmation and retry logic"""
    attempts = 0
    max_attempts = 10  # Prevent infinite loops
    
    while attempts < max_attempts:
        attempts += 1
        
        if attempts == 1:
            # First attempt with guessed title
            search_query = title_guess
            print(f"\n🔍 Searching TMDB for: \"{title_guess}\"")
            if year_hint:
                print(f"📅 Year hint: {year_hint}")
        else:
            # Subsequent attempts with user input
            search_query = input("Enter alternative search term (or 'skip' to skip this movie): ").strip()
            if search_query.lower() == 'skip':
                return None
                
            print(f"\n🔍 Searching TMDB for: \"{search_query}\"")
        
        # Extract year from search query if present
        search_year = extract_year(search_query) or year_hint
        
        # Clean the search query
        clean_search = clean_title(search_query)
        
        # Perform TMDB lookup
        result = tmdb_lookup(clean_search, search_year)
        
        if result:
            print(f"📽️  Found: {result}")
            
            while True:
                confirm = input("Is this correct? (y/n/skip/delete): ").lower().strip()
                if confirm == 'y':
                    return result
                elif confirm == 'n':
                    break
                elif confirm == 'skip':
                    return None
                elif confirm == 'delete':
                    if movie_info and 'movie_path' in movie_info:
                        movie_path = movie_info['movie_path']
                        try:
                            os.remove(movie_path)
                            print(f"🗑️  Deleted: {os.path.basename(movie_path)}")
                            # Also delete associated subtitle files if they exist
                            for sub_path in movie_info.get('subtitle_paths', []):
                                try:
                                    os.remove(sub_path)
                                    print(f"🗑️  Deleted: {os.path.basename(sub_path)}")
                                except OSError as e:
                                    print(f"❌ Could not delete subtitle {os.path.basename(sub_path)}: {e}")
                            return 'deleted'
                        except OSError as e:
                            print(f"❌ Could not delete {os.path.basename(movie_path)}: {e}")
                            print("Continuing with movie processing...")
                    else:
                        print("❌ Cannot delete - no movie file information available")
                    break
                else:
                    print("Please enter 'y', 'n', 'skip', or 'delete'")
        else:
            print("❌ No results found on TMDB")
            
        if attempts >= max_attempts:
            print("⚠️  Maximum attempts reached. Skipping this movie.")
            return None
    
    return None


def create_or_rename_directory(movie_info, target_name, root_dir):
    """Create new directory or rename existing one"""
    source_dir = movie_info['directory']
    movie_filename = movie_info['movie_filename']
    
    # Check if movie is already in its own folder with correct name
    current_dir_name = os.path.basename(source_dir)
    movie_base_name = os.path.splitext(movie_filename)[0]
    
    # Always create new folders in the root directory for consistency
    target_dir = os.path.join(root_dir, target_name)
    
    # Case 1: Movie is already in its own folder (directory name matches movie file name)
    if current_dir_name.lower() == movie_base_name.lower():
        # Movie is in its own folder, check if folder name needs to be updated
        if current_dir_name != target_name:
            print(f"📁 Renaming directory: {source_dir} → {target_dir}")
            try:
                os.rename(source_dir, target_dir)
                return target_dir, True  # True = renamed existing folder
            except OSError as e:
                print(f"❌ Error renaming directory: {e}")
                return source_dir, False
        else:
            print(f"✅ Directory already has correct name: {source_dir}")
            return source_dir, False
    
    # Case 2: Movie is in a general directory with other files, create new subfolder
    else:
        print(f"📁 Creating new directory: {target_dir}")
        os.makedirs(target_dir, exist_ok=True)
        return target_dir, False  # False = not renaming existing folder


def rename_movie_files(movie_info, target_name, target_dir):
    """Rename movie and subtitle files"""
    movie_path = movie_info['movie_path']
    subtitle_paths = movie_info['subtitle_paths']
    
    # Get file extensions
    movie_ext = os.path.splitext(movie_path)[1]
    
    # Target file paths
    target_movie_path = os.path.join(target_dir, target_name + movie_ext)
    target_subtitle_path = os.path.join(target_dir, target_name + SUB_EXT)
    
    renamed_files = []
    
    # Rename movie file
    if movie_path != target_movie_path:
        print(f"🎬 Renaming movie: {os.path.basename(movie_path)} → {target_name}{movie_ext}")
        try:
            os.rename(movie_path, target_movie_path)
            renamed_files.append(('movie', movie_path, target_movie_path))
        except OSError as e:
            print(f"❌ Error renaming movie file: {e}")
            return []
    else:
        print(f"✅ Movie file already has correct name: {os.path.basename(movie_path)}")
    
    # Rename subtitle files
    for sub_path in subtitle_paths:
        if sub_path != target_subtitle_path:
            print(f"📄 Renaming subtitle: {os.path.basename(sub_path)} → {target_name}{SUB_EXT}")
            try:
                os.rename(sub_path, target_subtitle_path)
                renamed_files.append(('subtitle', sub_path, target_subtitle_path))
            except OSError as e:
                print(f"❌ Error renaming subtitle file: {e}")
        else:
            print(f"✅ Subtitle file already has correct name: {os.path.basename(sub_path)}")
    
    return renamed_files


def cleanup_extra_files(target_dir, movie_name, sub_ext):
    """List and clean up extra files in the movie directory"""
    try:
        files_in_dir = os.listdir(target_dir)
    except OSError as e:
        print(f"❌ Error listing directory contents: {e}")
        return
    
    # Filter for extra files (not movie or subtitle)
    extra_files = []
    for file in files_in_dir:
        file_path = os.path.join(target_dir, file)
        if os.path.isfile(file_path):
            if not (file == movie_name + sub_ext or file.lower().endswith(VIDEO_EXTS)):
                extra_files.append(file)
    
    if not extra_files:
        print("✅ No extra files to clean up")
        return
    
    print(f"\n🗑️  Found {len(extra_files)} extra file(s) in {movie_name}:")
    for file in extra_files:
        print(f"   - {file}")
    
    while True:
        confirm = input(f"Delete these {len(extra_files)} extra file(s)? (y/n): ").lower().strip()
        if confirm == 'y':
            deleted_count = 0
            for file in extra_files:
                file_path = os.path.join(target_dir, file)
                try:
                    os.remove(file_path)
                    print(f"   🗑️  Deleted: {file}")
                    deleted_count += 1
                except OSError as e:
                    print(f"   ❌ Could not delete {file}: {e}")
            print(f"✅ Deleted {deleted_count} extra file(s)")
            break
        elif confirm == 'n':
            print("📂 Keeping extra files")
            break
        else:
            print("Please enter 'y' or 'n'")


def cleanup_unwanted_files(directory):
    """Find and delete all files that are not movies or subtitles, plus movie sample files"""
    unwanted_files = []
    sample_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            file_lower = file.lower()
            file_no_ext = os.path.splitext(file_lower)[0]
            
            # Check if file is a movie sample
            is_sample = False
            for pattern in MOVIE_SAMPLE_PATTERNS:
                if pattern.lower() in file_no_ext:
                    is_sample = True
                    break
            
            if is_sample:
                sample_files.append(file_path)
            # Check if file is NOT a movie or subtitle
            elif not (file_lower.endswith(VIDEO_EXTS) or file_lower.endswith(SUB_EXT)):
                unwanted_files.append(file_path)
    
    # Combine both lists
    all_files_to_delete = unwanted_files + sample_files
    
    if not all_files_to_delete:
        print("✅ No unwanted files to clean up")
        return
    
    print(f"\n🗑️  Found {len(all_files_to_delete)} unwanted file(s) in directory:")
    
    # Show sample files separately if any
    if sample_files:
        print(f"   🎬 Movie sample files ({len(sample_files)}):")
        for file_path in sorted(sample_files):
            relative_path = os.path.relpath(file_path, directory)
            print(f"      - {relative_path}")
    
    # Show other unwanted files if any
    if unwanted_files:
        print(f"   📄 Other unwanted files ({len(unwanted_files)}):")
        for file_path in sorted(unwanted_files):
            relative_path = os.path.relpath(file_path, directory)
            print(f"      - {relative_path}")
    
    while True:
        confirm = input(f"Delete these {len(all_files_to_delete)} unwanted file(s)? (y/n): ").lower().strip()
        if confirm == 'y':
            deleted_count = 0
            for file_path in all_files_to_delete:
                try:
                    os.remove(file_path)
                    relative_path = os.path.relpath(file_path, directory)
                    print(f"   🗑️  Deleted: {relative_path}")
                    deleted_count += 1
                except OSError as e:
                    relative_path = os.path.relpath(file_path, directory)
                    print(f"   ❌ Could not delete {relative_path}: {e}")
            print(f"✅ Deleted {deleted_count} unwanted file(s)")
            break
        elif confirm == 'n':
            print("📂 Keeping unwanted files")
            break
        else:
            print("Please enter 'y' or 'n'")


def cleanup_empty_folders(directory):
    """Find and delete all empty folders"""
    empty_folders = []
    
    # Walk from bottom to top to catch nested empty folders
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                # Check if directory is empty (no files or subdirectories)
                if not os.listdir(dir_path):
                    empty_folders.append(dir_path)
            except OSError:
                # Skip directories we can't access
                continue
    
    if not empty_folders:
        print("✅ No empty folders to clean up")
        return
    
    print(f"\n📁 Found {len(empty_folders)} empty folder(s):")
    for folder_path in sorted(empty_folders):
        relative_path = os.path.relpath(folder_path, directory)
        print(f"   - {relative_path}")
    
    while True:
        confirm = input(f"Delete these {len(empty_folders)} empty folder(s)? (y/n): ").lower().strip()
        if confirm == 'y':
            deleted_count = 0
            for folder_path in empty_folders:
                try:
                    os.rmdir(folder_path)
                    relative_path = os.path.relpath(folder_path, directory)
                    print(f"   🗑️  Deleted: {relative_path}")
                    deleted_count += 1
                except OSError as e:
                    relative_path = os.path.relpath(folder_path, directory)
                    print(f"   ❌ Could not delete {relative_path}: {e}")
            print(f"✅ Deleted {deleted_count} empty folder(s)")
            break
        elif confirm == 'n':
            print("📂 Keeping empty folders")
            break
        else:
            print("Please enter 'y' or 'n'")


def process_movie(movie_info, root_dir):
    """Process a single movie with user interaction"""
    movie_path = movie_info['movie_path']
    movie_filename = movie_info['movie_filename']
    
    print(f"\n" + "="*60)
    print(f"🎬 Processing: {movie_filename}")
    print(f"📍 Location: {movie_info['directory']}")
    
    # Extract info from filename
    year_hint = extract_year(movie_filename)
    title_guess = clean_title(movie_filename)
    
    print(f"🔤 Guessed title: \"{title_guess}\"")
    if year_hint:
        print(f"📅 Guessed year: {year_hint}")
    
    # Get TMDB confirmation
    tmdb_result = get_tmdb_confirmation(title_guess, year_hint, movie_info)
    if tmdb_result == 'deleted':
        print(f"🗑️  Deleted: {movie_filename}")
        return True  # Count as processed since it was deleted
    if not tmdb_result:
        print(f"⏭️  Skipping: {movie_filename}")
        return False
    
    print(f"✅ Confirmed: {tmdb_result}")
    
    # Create or rename directory
    target_dir, was_renamed = create_or_rename_directory(movie_info, tmdb_result, root_dir)
    
    # Update movie info if directory was renamed
    if was_renamed:
        movie_info['directory'] = target_dir
        # Update paths in movie_info
        movie_info['movie_path'] = os.path.join(target_dir, os.path.basename(movie_info['movie_path']))
        movie_info['subtitle_paths'] = [
            os.path.join(target_dir, os.path.basename(sub_path)) 
            for sub_path in movie_info['subtitle_paths']
        ]
    
    # Rename files
    renamed_files = rename_movie_files(movie_info, tmdb_result, target_dir)
    
    print(f"✅ Successfully processed: {movie_filename} → {tmdb_result}")
    return True


def main():
    print("🎬 Interactive Movie File Renamer")
    print("=" * 40)
    
    # Get directory from user
    directory = get_directory_from_user()
    print(f"\n📂 Scanning directory: {directory}")
    
    # Find all movies and subtitles
    movies = find_all_movies_and_subs(directory)
    
    if not movies:
        print("❌ No movie files found in the specified directory and its subdirectories.")
        return
    
    print(f"🎬 Found {len(movies)} movie file(s) to process:")
    for i, movie in enumerate(movies, 1):
        print(f"   {i}. {movie['movie_filename']}")
    
    print()
    while True:
        confirm = input(f"Proceed with processing these {len(movies)} movies? (y/n): ").lower().strip()
        if confirm == 'y':
            break
        elif confirm == 'n':
            print("👋 Exiting script.")
            return
        else:
            print("Please enter 'y' or 'n'")
    
    # Process each movie
    processed_count = 0
    skipped_count = 0
    
    for movie in movies:
        if process_movie(movie, directory):
            processed_count += 1
        else:
            skipped_count += 1
    
    print("\n" + "="*60)
    print("🎉 Processing complete!")
    print(f"✅ Successfully processed: {processed_count} movie(s)")
    print(f"⏭️  Skipped: {skipped_count} movie(s)")
    
    # Global cleanup operations
    print(f"\n🧹 Starting global cleanup operations...")
    
    # Step 1: Clean up unwanted files (non-movie/.srt files)
    print(f"\n" + "-"*40)
    print(f"STEP 1: Cleaning up unwanted files")
    print("-"*40)
    cleanup_unwanted_files(directory)
    
    # Step 2: Clean up empty folders
    print(f"\n" + "-"*40)
    print(f"STEP 2: Cleaning up empty folders")
    print("-"*40)
    cleanup_empty_folders(directory)
    
    print("\n" + "="*60)
    print("🎉 All operations complete!")
    print("="*60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Script interrupted by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)