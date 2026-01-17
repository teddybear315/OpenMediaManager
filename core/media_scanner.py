"""
Media Scanner for Open Media Manager
Scans directories for media files and analyzes their properties using ffprobe.
"""

import hashlib
import json
import logging
import os
import pickle
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern

from .constants import MEDIA_EXTENSIONS
from .utils import get_resolution_category

logger = logging.getLogger(__name__)


class MediaStatus(Enum):
    """Status of media file compliance with quality standards."""
    COMPLIANT = "✅"  # Meets all standards
    NEEDS_REENCODING = "⚠️"  # Needs re-encoding
    BELOW_STANDARD = "ℹ️"  # Below minimum bitrate (skip)
    SCANNING = "🔍"  # Currently scanning
    ERROR = "⛔"  # Error during scan
    UNKNOWN = "❔"  # Not yet scanned


class MediaCategory(Enum):
    """Category of media file."""
    SHOW = "show"  # TV show episode
    MOVIE = "movie"  # Movie
    EXTRA = "extra"  # Bonus feature/extra/featurette


@dataclass
class MediaInfo:
    """Information about a media file."""
    path: Path
    filename: str
    status: MediaStatus = MediaStatus.UNKNOWN

    # Thread safety flag to prevent double analysis
    _analyzing: bool = field(default=False, repr=False, compare=False)
    _analysis_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # Video properties
    codec: str = ""
    resolution: str = ""
    width: int = 0
    height: int = 0
    bitrate: int = 0  # in kbps
    fps: float = 0.0
    bit_depth: int = 0
    duration: float = 0.0  # in seconds

    # Audio properties
    audio_codec: str = ""
    audio_channels: int = 0
    audio_language: str = ""

    # Subtitle properties
    subtitle_tracks: List[str] = field(default_factory=list)

    # Cover art / attached pictures
    has_cover_art: bool = False

    # File properties
    file_size: int = 0  # in bytes

    # Category detection
    category: MediaCategory = MediaCategory.MOVIE

    # Show/Season detection
    is_show: bool = False
    show_name: str = ""
    season: Optional[int] = None
    episode: Optional[int] = None

    # Parent folder for hierarchy
    parent_folder: str = ""

    # Full path components for extras detection
    full_path_lower: str = ""

    # Reasons for non-compliance
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MediaScanner:
    """Scans directories for media files and analyzes them."""

    MEDIA_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts'}

    # Patterns to identify extras/bonus features
    EXTRAS_PATTERNS = [
        r'extras?',
        r'bonus\s*features?',
        r'dvd\s*special\s*features?',
        r'featurettes?',
        r'behind\s*the\s*scenes?',
        r'bts',
        r'deleted\s*scenes?',
        #r'interviews?',
        r'making\s*of',
        r'blooper',
        r'gag\s*reel',
        r'commentary',
        #r'trailer',
        #r'shorts?',
    ]

    def __init__(self, quality_standards: Dict[str, Any], manual_overrides: Optional[Dict[str, Dict]] = None):
        """
        Initialize the media scanner.

        Args:
            quality_standards: Dictionary of quality standards for media files.
            manual_overrides: Dictionary of manual category overrides {file_path: {category, show_name, etc}}
        """
        self.quality_standards = quality_standards
        self.manual_overrides = manual_overrides or {}
        self.analysis_cache = {}  # Cache: {file_path: (mtime, size, analysis_data_dict)}
        self.cache_file = Path.home() / '.config' / 'openmediamanager' / '.openmediamanager_cache.pkl'
        self.min_file_size = 1024 * 1024  # 1MB minimum - skip very small files

        # Compile regex patterns once for performance
        self._extras_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.EXTRAS_PATTERNS]

        # Episode patterns (with season and episode)
        self._episode_patterns = [
            re.compile(r'[Ss](\d{1,2})[Ee](\d{1,2})'),  # S01E01
            re.compile(r'(\d{1,2})x(\d{1,2})'),  # 1x01
            re.compile(r'[Ss]eason\s*(\d{1,2}).*[Ee]pisode\s*(\d{1,2})', re.IGNORECASE),  # Season 1 Episode 1
        ]

        # Episode-only patterns (no season, defaults to season 1)
        self._episode_only_patterns = [
            re.compile(r'[Ee](\d{1,2})(?:[^\d]|$)'),  # E01, E12
            re.compile(r'[Ee]pisode\s*(\d{1,2})', re.IGNORECASE),  # Episode 01
            re.compile(r'^(\d{1,2})(?:[^\dx]|$)'),  # Starting with number
        ]

        # Season folder patterns
        self._season_start_pattern = re.compile(r'^(?:[Ss]eason\s*)?[Ss](\d{1,2})(?:\s|$)', re.IGNORECASE)
        self._season_end_pattern = re.compile(r'\s+(?:\d{3,4}p\s+)?[Ss](\d{1,2})(?:\s|$)', re.IGNORECASE)

        # Cleanup patterns
        self._year_pattern = re.compile(r'\s*\(\d{4}(?:-\d{2,4})?\)')
        self._quality_pattern = re.compile(r'\b(?:x264|x265|h\.?264|h\.?265|hevc|avc|10bit|8bit)\b', re.IGNORECASE)
        self._resolution_pattern = re.compile(r'\b(?:\d{3,4}p|4k|uhd|hd)\b', re.IGNORECASE)
        self._dots_underscores = re.compile(r'[._]+')
        self._multi_space = re.compile(r'\s+')

        # Folder type checks
        self._season_folder_pattern = re.compile(r'^[sS](eason)?\s*\d+')
        self._specials_shorts_pattern = re.compile(r'\b(?:specials?|shorts?)\b', re.IGNORECASE)
        self._extras_folder_pattern = re.compile(r'\b(shorts?|extras?|specials?|bonus|featurettes?)\b', re.IGNORECASE)

        # Generic folder names to skip
        self._generic_folders = {'tv', 'shows', 'tv shows', 'series', 'media', 'x264', 'x265', 'hevc', 'movies', 'encoded', 'reencode'}

        # Pre-compile lowercase extensions set for fast O(1) lookups
        self._media_extensions_lower = {ext.lower() for ext in self.MEDIA_EXTENSIONS}

        # Combined regex for show name cleaning (more efficient than separate regex operations)
        self._show_name_clean_pattern = re.compile(
            r'\s*\(\d{4}(?:-\d{2,4})?\)|'  # Year pattern
            r'\b(?:x264|x265|h\.?264|h\.?265|hevc|avc|10bit|8bit)\b|'  # Quality pattern
            r'\b(?:\d{3,4}p|4k|uhd|hd)\b|'  # Resolution pattern
            r'\b[Ss]eason\s*\d{1,2}\b|'  # Season pattern (Season 1, Season 01, etc.)
            r'\b[Ss]\d{1,2}\b',  # Short season pattern (S1, S01, etc.)
            re.IGNORECASE
        )

        # Parent media count cache for performance
        self._parent_media_count_cache = {}

        # In-memory cache of scanned media files (dict with path as key)
        self.media_files = {}

        self._load_cache()

    def _clean_show_name(self, name: str) -> str:
        """Clean and normalize a show name."""
        # Use combined pattern for faster cleaning (3 regex ops instead of 5)
        name = self._dots_underscores.sub(' ', name)
        name = self._multi_space.sub(' ', name)
        name = self._show_name_clean_pattern.sub('', name)
        return name.strip()

    def _is_season_folder(self, folder_name: str) -> bool:
        """Check if folder name indicates a season folder."""
        return bool(self._season_folder_pattern.match(folder_name))

    def _is_generic_folder(self, folder_name: str) -> bool:
        """Check if folder name is generic (TV, Shows, etc.)."""
        return folder_name.lower() in self._generic_folders

    def _extract_show_name_from_extras_path(self, file_path: Path) -> Optional[str]:
        """
        Extract show name from file path for extras grouping.
        Based on GUI implementation.

        Args:
            file_path: Path to the media file.

        Returns:
            Show name if detectable, None otherwise.
        """
        import re

        path_str = str(file_path)
        parts = file_path.parts

        # Look for show folder (typically grandparent or great-grandparent)
        # Pattern: /ShowName (Year)/Extras/... or /ShowName (Year)/Season X/Extras/...
        # Start from the end and search backwards for the show folder
        for i in range(len(parts) - 1, 0, -1):
            part = parts[i]
            p_low = part.lower()

            # Check if this part contains extras-related keywords (more exhaustive)
            # Include alternate/takes/lost interviews/on set variants to catch common out-of-place folder names
            if re.search(r"\b(extras?|bonus|featurettes?|deleted\s*scenes?|behind\s*the\s*scenes?|special\s*features?|interviews?|lost\s*interviews?|making\s*of|blooper|gag\s*reel|commentary|on[-\s]?set|dvd|alternate\s*takes?|takes?)\b", p_low):
                # Found an extras-related folder, now search upward for the show folder
                # Skip season folders, shorts folders, quality folders, and other non-show folders
                for j in range(i - 1, -1, -1):
                    potential_show = parts[j]
                    p_low = potential_show.lower()

                    # Skip obvious non-show folders and extras-like names
                    if re.search(r'^[Ss](eason)?\s*\d+', potential_show):
                        continue
                    if re.search(r"\b(shorts?|extras?|specials?|bonus|featurettes?|dvd|deleted\s*scenes|making\s*of|gag\s*reel|behind\s*the\s*scenes?|special\s*features?|alternate\s*takes?|takes?|lost\s*interviews?)\b", p_low):
                        continue
                    if re.search(r'\b(?:x264|x265|h\.264|h\.265|hevc|1080p|720p|2160p|4k|uhd|hd|web-dl|webrip|bluray|brrip)\b', p_low):
                        continue
                    if p_low in ['tv', 'shows', 'tv shows', 'series', 'media', 'movies', 'encoded', 'reencode']:
                        continue

                    # Clean up year patterns and dots/underscores
                    show_name = re.sub(r'\s*\(?\d{4}(?:-\d{2,4})?\)?', '', potential_show).strip()
                    show_name = re.sub(r'[._]+', ' ', show_name).strip()
                    show_name = re.sub(r'\s+', ' ', show_name).strip()

                    # Final sanity: do not return an extras-like name as a show
                    if re.search(r"\b(extras?|featurettes?|specials?|shorts?|bonus|alternate\s*takes?|lost\s*interviews?|takes?)\b", show_name.lower()):
                        continue

                    if show_name and len(show_name) > 1:
                        return show_name

        return None

    def _extract_show_name_from_ancestors(self, path: Path, skip_count: int = 1) -> Optional[str]:
        """Extract show name by walking up the directory tree."""
        ancestors = list(path.parents)
        for anc in ancestors[skip_count:min(skip_count + 5, len(ancestors))]:
            try:
                candidate = anc.name
                if not candidate:
                    continue

                # Skip folders we don't want
                if self._specials_shorts_pattern.search(candidate):
                    continue
                if self._is_season_folder(candidate):
                    continue
                if self._is_generic_folder(candidate):
                    continue

                # Clean and validate
                show_name = self._clean_show_name(candidate)
                if show_name and len(show_name) > 1:
                    return show_name
            except Exception:
                continue
        return None

    def _load_cache(self):
        """Load analysis cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'rb') as f:
                    self.analysis_cache = pickle.load(f)
                logger.info(f"Loaded {len(self.analysis_cache)} cached entries")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            self.analysis_cache = {}

    def _save_cache(self):
        """Save analysis cache to disk."""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.analysis_cache, f)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[MediaInfo]:
        """
        Scan a directory for media files.

        Args:
            directory: Path to the directory to scan.
            recursive: Whether to scan subdirectories.

        Returns:
            List of MediaInfo objects for found media files.
        """
        start_time = time.time()
        logger.debug(f"Starting directory scan: {directory}")

        media_files = []

        if not directory.exists() or not directory.is_dir():
            return media_files

        # Use os.walk for network volumes - most compatible approach
        walk_start = time.time()
        if recursive:
            try:
                for root, dirs, files in os.walk(str(directory), topdown=True, onerror=None, followlinks=False):
                    # Process files in current directory
                    for filename in files:
                        # Check if file has a media extension (fast O(1) lookup)
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in self._media_extensions_lower:
                            try:
                                # Build full file path using string operations first
                                file_path_str = os.path.join(root, filename)
                                file_path = Path(file_path_str)

                                # Basic check - don't verify existence as it may fail on network volumes
                                media_files.append(file_path)
                            except (OSError, PermissionError, ValueError) as e:
                                print(f"Warning: Skipping file {filename}: {e}")

                    # Filter out problematic directories before descending
                    # Skip: hidden dirs, encoded output dirs, and common temp/cache folders
                    skip_dirs = {'.', 'encoded', '__pycache__', '.git', '.venv', 'node_modules', '.cache'}
                    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

            except (OSError, PermissionError) as e:
                print(f"Warning: Error walking directory {directory}: {e}")
        else:
            # Non-recursive scan
            try:
                for item in directory.iterdir():
                    if item.is_file() and any(item.name.lower().endswith(ext) for ext in self.MEDIA_EXTENSIONS):
                        try:
                            media_files.append(item)
                        except (OSError, PermissionError) as e:
                            print(f"Warning: Skipping file {item}: {e}")
            except (OSError, PermissionError) as e:
                print(f"Warning: Error scanning directory {directory}: {e}")

        walk_time = time.time() - walk_start
        logger.debug(f"Directory walk completed in {walk_time:.2f}s - found {len(media_files)} files")

        # Create MediaInfo objects
        info_start = time.time()
        results = []
        cache_hits = 0
        filtered_small = 0

        # No need to sort - just iterate (sorting is expensive for large lists)
        for media_path in media_files:
            try:
                # Use os.stat for better network performance
                file_stat = os.stat(str(media_path))
                file_size = file_stat.st_size
                file_mtime = file_stat.st_mtime

                # Pre-filter: Skip very small files (likely not real media)
                if file_size < self.min_file_size:
                    filtered_small += 1
                    continue

                # Check cache for unchanged files
                cache_key = str(media_path)
                if cache_key in self.analysis_cache:
                    cached_mtime, cached_size, cached_data = self.analysis_cache[cache_key]
                    # If file hasn't changed (same mtime and size), use cached data
                    if cached_mtime == file_mtime and cached_size == file_size:
                        try:
                            # Reconstruct MediaInfo from cached dict
                            media_info = MediaInfo(
                                path=media_path,
                                filename=media_path.name,
                                parent_folder=media_path.parent.name,
                                file_size=file_size,
                                status=MediaStatus(cached_data['status']),
                                full_path_lower=str(media_path).lower(),
                                codec=cached_data.get('codec', ''),
                                width=cached_data.get('width', 0),
                                height=cached_data.get('height', 0),
                                resolution=cached_data.get('resolution', ''),
                                bitrate=cached_data.get('bitrate', 0),
                                fps=cached_data.get('fps', 0.0),
                                bit_depth=cached_data.get('bit_depth', 0),
                                duration=cached_data.get('duration', 0.0),
                                audio_codec=cached_data.get('audio_codec', ''),
                                audio_channels=cached_data.get('audio_channels', 0),
                                audio_language=cached_data.get('audio_language', ''),
                                subtitle_tracks=cached_data.get('subtitle_tracks', []),
                                has_cover_art=cached_data.get('has_cover_art', False),
                                issues=cached_data.get('issues', []),
                                category=MediaCategory(cached_data.get('category', 'movie')),
                                is_show=cached_data.get('is_show', False),
                                show_name=cached_data.get('show_name', ''),
                                season=cached_data.get('season'),
                                episode=cached_data.get('episode')
                            )
                            # Quick cache correction checks (optimized)
                            parent_name_lower = media_path.parent.name.lower()

                            # Shorts folder check (only if currently marked as movie)
                            if media_info.category == MediaCategory.MOVIE and 'short' in parent_name_lower:
                                if self._specials_shorts_pattern.search(parent_name_lower):
                                    media_info.category = MediaCategory.SHOW
                                    media_info.is_show = True
                                    media_info.season = 0
                                    try:
                                        grandparent = media_path.parent.parent.name
                                        show_name = self._clean_show_name(grandparent)
                                        if show_name and len(show_name) > 1 and show_name.lower() not in self._generic_folders:
                                            media_info.show_name = show_name
                                    except Exception:
                                        pass

                            # Single-file folder check (only if marked as SHOW/EXTRA)
                            # Use cached parent count instead of expensive iterdir()
                            elif media_info.category in (MediaCategory.SHOW, MediaCategory.EXTRA):
                                media_count_in_parent = self._parent_media_count_cache.get(str(media_path.parent), 0)
                                if media_count_in_parent == 1:
                                    parent_clean = self._clean_show_name(media_path.parent.name).lower()
                                    filename_clean = self._clean_show_name(Path(media_path.name).stem).lower()
                                    if parent_clean and parent_clean in filename_clean:
                                        media_info.category = MediaCategory.MOVIE
                                        media_info.is_show = False
                                        media_info.show_name = ''
                                        media_info.season = None
                                        media_info.episode = None

                            # IMPORTANT: Re-check compliance with current quality_standards
                            # The cached status might be based on old quality_standards values
                            media_info.issues.clear()
                            media_info.status = self._check_compliance(media_info)

                            results.append(media_info)
                            cache_hits += 1
                            continue
                        except (ValueError, KeyError) as e:
                            # Cache has invalid data (e.g., old enum values), skip cache for this file
                            print(f"[WARNING] Invalid cache data for {media_path.name}: {e}. Re-analyzing...")

                media_info = MediaInfo(
                    path=media_path,
                    filename=media_path.name,
                    parent_folder=media_path.parent.name,
                    file_size=file_size,
                    status=MediaStatus.SCANNING,
                    full_path_lower=str(media_path).lower()
                )

                # Check for manual override first
                override = self.manual_overrides.get(str(media_path))
                if override:
                    media_info.category = MediaCategory(override.get('category', 'movie'))
                    media_info.is_show = override.get('is_show', False)
                    media_info.show_name = override.get('show_name', '')
                    media_info.season = override.get('season')
                    media_info.episode = override.get('episode')
                else:
                    # Detect category (extras vs show vs movie)
                    self._detect_category(media_info)

                    # Detect show/season info from path (only if not extras)
                    # if media_info.category != MediaCategory.MOVIE:
                    self._detect_show_info(media_info)

                results.append(media_info)
            except (OSError, PermissionError) as e:
                # Skip files that can't be accessed
                print(f"Warning: Skipping {media_path} due to error: {e}")

        # Pre-compute parent directory media counts to avoid repeated iterdir() calls
        parent_count_start = time.time()
        self._parent_media_count_cache.clear()
        for media_path in media_files:
            parent_key = str(media_path.parent)
            self._parent_media_count_cache[parent_key] = self._parent_media_count_cache.get(parent_key, 0) + 1
        parent_count_time = time.time() - parent_count_start

        info_time = time.time() - info_start
        total_time = time.time() - start_time
        logger.debug(f"MediaInfo creation completed in {info_time:.2f}s (parent count: {parent_count_time:.2f}s)")
        logger.info(f"Cache hits: {cache_hits}/{len(media_files)} ({cache_hits*100//len(media_files) if media_files else 0}%)")
        if filtered_small > 0:
            logger.debug(f"Filtered {filtered_small} small files (< 1MB)")
        logger.info(f"Scan complete: {len(results)} files in {total_time:.2f}s")

        # Store results in instance variable for web API access
        self.media_files = {str(file.path): file for file in results}

        return results

    def analyze_media(self, media_info: MediaInfo) -> MediaInfo:
        """
        Analyze a media file using ffprobe.
        Thread-safe: prevents double analysis of the same file.

        Args:
            media_info: MediaInfo object to populate.

        Returns:
            Updated MediaInfo object.
        """
        # Quick check without lock first (optimization for already-analyzed files)
        if media_info.status != MediaStatus.UNKNOWN and media_info.status != MediaStatus.SCANNING:
            return media_info

        # Acquire lock briefly to set analyzing flag
        with media_info._analysis_lock:
            # Double-check after acquiring lock
            if media_info._analyzing:
                logger.warning(f"Skipping duplicate analysis of {media_info.filename}")
                return media_info

            if media_info.status != MediaStatus.UNKNOWN and media_info.status != MediaStatus.SCANNING:
                return media_info

            # Mark as analyzing
            media_info._analyzing = True
            media_info.status = MediaStatus.SCANNING
        # Lock released here - rest of analysis happens without holding lock

        file_start = time.time()

        try:
            # Run ffprobe to get media information from container headers only
            # Modern containers (mkv, mp4, mov) store duration in header without analysis
            # CRITICAL optimizations:
            # 1. No -analyzeduration (skip stream analysis)
            # 2. Minimal probesize for header read only
            # 3. Request only: bitrate-relevant data (duration), codec, resolution, pixel format, language
            # 4. No -select_streams (avoid forcing stream scan)
            cmd = [
                'ffprobe',
                '-v', 'error',
                # '-probesize', '256K',  # Minimal header read - just enough for basic stream info
                '-analyzeduration', '5M',  # 0 = skip all analysis
                '-print_format', 'json',
                '-show_entries',
                'stream=codec_name,codec_type,width,height,pix_fmt,channels,disposition:stream_tags=language:format=duration',
                str(media_info.path)
            ]

            probe_start = time.time()
            # Use explicit UTF-8 decoding with replacement to avoid UnicodeDecodeError on Windows cp1252
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            probe_time = time.time() - probe_start

            if result.returncode != 0:
                media_info.status = MediaStatus.ERROR
                media_info.issues.append("Failed to probe media file")
                return media_info

            parse_start = time.time()
            data = json.loads(result.stdout)
            parse_time = time.time() - parse_start

            # Extract video stream info
            extract_start = time.time()
            video_stream = next(
                (s for s in data.get('streams', []) if s['codec_type'] == 'video'),
                None
            )

            if video_stream:
                media_info.codec = video_stream.get('codec_name', '')
                media_info.width = int(video_stream.get('width', 0))
                media_info.height = int(video_stream.get('height', 0))
                media_info.resolution = f"{media_info.width}x{media_info.height}"

                # Get bit depth
                pix_fmt = video_stream.get('pix_fmt', '')
                media_info.bit_depth = 10 if '10' in pix_fmt else 8

                # Get FPS from stream header (r_frame_rate)
                fps_str = video_stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    media_info.fps = float(num) / float(den) if float(den) != 0 else 0

                # Extract duration from container header (not analyzed, just stored metadata)
                duration = 0.0
                if 'duration' in data.get('format', {}):
                    try:
                        duration = float(data['format']['duration'])
                        media_info.duration = duration
                    except (ValueError, TypeError):
                        pass

                # Calculate bitrate using container duration and actual file size
                # Formula: (file_size_bytes * 8) / duration_seconds / 1000 = kbps
                # This gives the true average bitrate across entire file
                if media_info.file_size > 0 and duration > 0:
                    media_info.bitrate = int((media_info.file_size * 8) / duration / 1000)
                else:
                    media_info.bitrate = 0

            # Extract audio stream info
            audio_stream = next(
                (s for s in data.get('streams', []) if s['codec_type'] == 'audio'),
                None
            )

            if audio_stream:
                media_info.audio_codec = audio_stream.get('codec_name', '')
                media_info.audio_channels = int(audio_stream.get('channels', 0))
                media_info.audio_language = audio_stream.get('tags', {}).get('language', '')

            # Extract subtitle info
            subtitle_streams = [
                s.get('tags', {}).get('language', 'unknown')
                for s in data.get('streams', [])
                if s.get('codec_type') == 'subtitle'
            ]
            media_info.subtitle_tracks = subtitle_streams

            # Detect cover art / attached pictures
            # Cover art is typically a video stream with codec mjpeg/png and disposition:attached_pic
            # or simply a second video stream that's an image codec
            video_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
            for vs in video_streams:
                codec = vs.get('codec_name', '').lower()
                disposition = vs.get('disposition', {})
                # Check for attached_pic disposition or image codecs
                if disposition.get('attached_pic', 0) == 1 or codec in ['mjpeg', 'png', 'bmp', 'gif', 'webp']:
                    media_info.has_cover_art = True
                    break

            extract_time = time.time() - extract_start

            # Analyze compliance with quality standards
            compliance_start = time.time()
            media_info.status = self._check_compliance(media_info)
            compliance_time = time.time() - compliance_start

            # Update cache with successful analysis
            try:
                file_stat = os.stat(str(media_info.path))
                cache_key = str(media_info.path)
                # Store as dict to avoid pickle issues with threading.Lock
                cache_data = {
                    'status': media_info.status.value,
                    'codec': media_info.codec,
                    'width': media_info.width,
                    'height': media_info.height,
                    'resolution': media_info.resolution,
                    'bitrate': media_info.bitrate,
                    'fps': media_info.fps,
                    'bit_depth': media_info.bit_depth,
                    'duration': media_info.duration,
                    'audio_codec': media_info.audio_codec,
                    'audio_channels': media_info.audio_channels,
                    'audio_language': media_info.audio_language,
                    'subtitle_tracks': media_info.subtitle_tracks,
                    'has_cover_art': media_info.has_cover_art,
                    'issues': media_info.issues,
                    'category': media_info.category.value,
                    'is_show': media_info.is_show,
                    'show_name': media_info.show_name,
                    'season': media_info.season,
                    'episode': media_info.episode
                }
                self.analysis_cache[cache_key] = (file_stat.st_mtime, file_stat.st_size, cache_data)
            except Exception:
                pass  # If cache update fails, continue without it

            total_time = time.time() - file_start

            # Log timing for files that take longer than 1 second
            if total_time > 1.0:
                logger.debug(f"Slow file analysis ({total_time:.2f}s): {media_info.filename}")
                logger.debug(f"  - ffprobe: {probe_time:.2f}s, parse: {parse_time:.3f}s, extract: {extract_time:.3f}s, compliance: {compliance_time:.3f}s")

        except subprocess.TimeoutExpired:
            media_info.status = MediaStatus.ERROR
            media_info.issues.append("Timeout while probing media")
            logger.warning(f"TIMEOUT after 10s: {media_info.filename}")
        except json.JSONDecodeError:
            media_info.status = MediaStatus.ERROR
            media_info.issues.append("Invalid ffprobe output")
        except Exception as e:
            media_info.status = MediaStatus.ERROR
            media_info.issues.append(f"Error: {str(e)}")
        finally:
            # Always reset the analyzing flag
            with media_info._analysis_lock:
                media_info._analyzing = False

        return media_info

    def update_compliance(self, media_info: MediaInfo) -> MediaInfo:
        """
        Re-check compliance for a media file without re-running ffprobe.
        Use this when quality standards change.

        Args:
            media_info: MediaInfo object to re-check.

        Returns:
            Updated MediaInfo object.
        """
        if media_info.status == MediaStatus.ERROR or media_info.status == MediaStatus.UNKNOWN:
            return media_info

        # Clear old issues
        media_info.issues.clear()

        # Re-run compliance check with current quality standards
        media_info.status = self._check_compliance(media_info)

        # Update cache with new status
        try:
            file_stat = os.stat(str(media_info.path))
            cache_key = str(media_info.path)
            if cache_key in self.analysis_cache:
                cached_mtime, cached_size, cached_data = self.analysis_cache[cache_key]
                # Update status and issues in cache
                cached_data['status'] = media_info.status.value
                cached_data['issues'] = media_info.issues
                self.analysis_cache[cache_key] = (cached_mtime, cached_size, cached_data)
        except Exception:
            pass

        return media_info

    def analyze_media_batch(self, media_list: List[MediaInfo], max_workers: int = 8,
                           progress_callback=None) -> List[MediaInfo]:
        """
        Analyze multiple media files in parallel using a thread pool.
        MUCH faster than sequential analysis - can reduce 5+ minute scans to ~60 seconds.

        Args:
            media_list: List of MediaInfo objects to analyze.
            max_workers: Maximum number of parallel ffprobe processes (default 8).
            progress_callback: Optional callback(current, total) for progress updates.

        Returns:
            List of analyzed MediaInfo objects.
        """
        # Filter to only files that need analysis
        to_analyze = [m for m in media_list if m.status in (MediaStatus.UNKNOWN, MediaStatus.SCANNING)]
        total = len(to_analyze)

        if total == 0:
            logger.debug("All files already analyzed from cache")
            return media_list

        logger.info(f"Starting parallel analysis of {total} files with {max_workers} workers")
        start_time = time.time()
        completed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all analysis jobs
            future_to_media = {executor.submit(self.analyze_media, m): m for m in to_analyze}

            # Process completed futures as they finish
            for future in as_completed(future_to_media):
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

                # Log progress every 100 files
                if completed % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (total - completed) / rate if rate > 0 else 0
                    logger.info(f"Progress: {completed}/{total} ({rate:.1f} files/sec, ~{remaining:.0f}s remaining)")

        elapsed = time.time() - start_time
        logger.info(f"Completed {total} files in {elapsed:.1f}s ({total/elapsed:.1f} files/sec)")

        # Save cache after batch analysis
        self._save_cache()

        return media_list

    def _check_compliance(self, media_info: MediaInfo) -> MediaStatus:
        """
        Check if media complies with quality standards.

        Args:
            media_info: MediaInfo object to check.

        Returns:
            MediaStatus indicating compliance.
        """
        issues = []
        warnings = []

        # Determine resolution category and bitrate ranges using utility function
        res_category, min_bitrate, max_bitrate = get_resolution_category(
            media_info.width,
            media_info.height,
            self.quality_standards
        )

        # Check codec
        preferred_codec = self.quality_standards.get("preferred_codec", "hevc")
        # Accept HEVC variants and AV1
        accepted_codecs = [preferred_codec, 'hevc', 'h265', 'av1']
        if media_info.codec not in accepted_codecs:
            issues.append(f"Codec is {media_info.codec}, not {preferred_codec}")

        # Check bit depth based on preference
        bit_depth_pref = self.quality_standards.get("bit_depth_preference", "source")
        if bit_depth_pref == "force_10bit":
            # Flag anything below 10-bit as below standard
            if media_info.bit_depth < 10:
                media_info.issues.append(f"Bit depth is {media_info.bit_depth}-bit, should be 10-bit")
                return MediaStatus.BELOW_STANDARD
        elif bit_depth_pref == "force_8bit":
            # Flag anything 10-bit or above as needs reencoding
            if media_info.bit_depth >= 10:
                issues.append(f"Bit depth is {media_info.bit_depth}-bit, should be 8-bit")
        # If "source", no bit depth checking

        # Check bitrate (if available)
        if media_info.bitrate > 0:
            if media_info.bitrate < min_bitrate:
                # Below minimum - mark as below standard
                media_info.issues.append(f"Bitrate {media_info.bitrate}kbps below minimum {min_bitrate}kbps for {res_category}")
                return MediaStatus.BELOW_STANDARD
            elif media_info.bitrate > max_bitrate:
                issues.append(f"Bitrate {media_info.bitrate}kbps exceeds max {max_bitrate}kbps for {res_category}")

        # Track warnings separately - these show in issues but don't change status
        warnings = []

        # Check subtitles based on preference
        subtitle_check = self.quality_standards.get("subtitle_check", "ignore")
        if subtitle_check != "ignore":
            preferred_langs = self.quality_standards.get("preferred_subtitle_languages", ["eng"])

            # Check if any preferred language subtitle exists
            has_preferred_subtitle = False
            if media_info.subtitle_tracks:
                # If only 1 subtitle and no language tag (or 'unknown'), assume compliant
                if len(media_info.subtitle_tracks) == 1 and media_info.subtitle_tracks[0] in ['unknown', '', None]:
                    has_preferred_subtitle = True
                else:
                    # Check if any subtitle matches preferred languages
                    for lang in media_info.subtitle_tracks:
                        if lang and lang.lower() in [pl.lower() for pl in preferred_langs]:
                            has_preferred_subtitle = True
                            break

            if not has_preferred_subtitle:
                missing_msg = f"Missing subtitles ({', '.join(preferred_langs)})"
                if subtitle_check == "below_standard":
                    media_info.issues.append(missing_msg)
                    return MediaStatus.BELOW_STANDARD
                elif subtitle_check == "needs_reencoding":
                    issues.append(missing_msg)
                elif subtitle_check == "warning":
                    warnings.append(missing_msg)

        # Check cover art based on preference
        cover_art_check = self.quality_standards.get("cover_art_check", "ignore")
        if cover_art_check != "ignore":
            if not media_info.has_cover_art:
                if cover_art_check == "below_standard":
                    media_info.issues.append("Missing cover art")
                    return MediaStatus.BELOW_STANDARD
                elif cover_art_check == "needs_reencoding":
                    issues.append("Missing cover art")
                elif cover_art_check == "warning":
                    warnings.append("Missing cover art")

        # Combine issues and warnings for display
        media_info.issues = issues
        media_info.warnings = warnings

        # Only issues (not warnings) affect the status
        # Status determination is based EXCLUSIVELY on the issues list
        if issues:
            return MediaStatus.NEEDS_REENCODING
        else:
            return MediaStatus.COMPLIANT

    def _detect_category(self, media_info: MediaInfo):
        """
        Detect if file is an extra/bonus feature based on path.

        Priority:
        1. Folder path contains extras patterns → EXTRA
        2. Filename has episode patterns (S01E01, 1x01) → SHOW
        3. Filename has extras-like words (but check if in season folder) → EXTRA or SHOW
        4. Default → MOVIE

        Args:
            media_info: MediaInfo object to update.
        """
        filename = media_info.filename
        folder_path_lower = str(media_info.path.parent).lower()

        # Priority 1: Check folder path for extras patterns
        for pattern in self._extras_compiled:
            if pattern.search(folder_path_lower):
                media_info.category = MediaCategory.EXTRA
                return

        # Priority 2: Check filename for episode patterns (takes priority over extras-like words)
        for pattern in self._episode_patterns:
            if pattern.search(filename):
                media_info.category = MediaCategory.SHOW
                return

        for pattern in self._episode_only_patterns:
            if pattern.search(filename):
                media_info.category = MediaCategory.SHOW
                return

        # Priority 3: Check filename for extras-like words (only if no episode pattern)
        for pattern in self._extras_compiled:
            if pattern.search(filename):
                # If in season folder, prefer SHOW
                if any(self._is_season_folder(p) for p in media_info.path.parent.parts):
                    media_info.category = MediaCategory.SHOW
                    return
                # Otherwise treat as extra
                media_info.category = MediaCategory.EXTRA
                return

        # Priority 4: Default to movie
        media_info.category = MediaCategory.MOVIE

    def _detect_show_info(self, media_info: MediaInfo):
        """
        Detect show/season/episode information from filename and path.

        Args:
            media_info: MediaInfo object to update.
        """
        filename = media_info.filename
        parent = media_info.parent_folder
        full_path = media_info.path

        # For extras, try to extract associated show name from path
        if media_info.category == MediaCategory.EXTRA:
            show_name = self._extract_show_name_from_extras_path(full_path)
            if show_name:
                media_info.show_name = show_name
            return

        # Heuristic: Single-file parent directory (treat as movie unless season/extras/shorts folder)
        # Skip this heuristic if the filename contains episode patterns (let later logic handle it)
        try:
            parent_dir = full_path.parent
            # Use cached count instead of expensive iterdir() - HUGE speedup on network volumes
            media_count_in_parent = self._parent_media_count_cache.get(str(parent_dir), 0)

            if media_count_in_parent <= 1:
                parent_name_clean = self._clean_show_name(parent_dir.name).lower()
                filename_stem = Path(filename).stem.replace('.', ' ').replace('_', ' ').strip().lower()

                # Check if filename has episode patterns - if so, skip movie heuristic
                has_episode_pattern = any(p.search(filename) for p in self._episode_patterns)
                has_episode_only_pattern = any(p.search(filename) for p in self._episode_only_patterns)

                if not has_episode_pattern and not has_episode_only_pattern:
                    if parent_name_clean and (parent_name_clean in filename_stem or filename_stem in parent_name_clean):
                        # Don't force movie if parent is season/extras/shorts folder
                        if self._is_season_folder(parent) or self._extras_folder_pattern.search(parent):
                            media_info.category = MediaCategory.SHOW
                            media_info.is_show = True
                            return

                        media_info.category = MediaCategory.MOVIE
                        media_info.is_show = False
                        return
        except Exception:
            pass

        # Check if parent folder is "Specials" or contains "Shorts" (treat as season 0)
        if self._specials_shorts_pattern.search(parent):
            media_info.is_show = True
            media_info.category = MediaCategory.SHOW
            media_info.season = 0

            # Get show name from ancestors
            show_name = self._extract_show_name_from_ancestors(full_path, skip_count=1)
            if not show_name:
                show_name = self._clean_show_name(filename.split('.')[0])

            media_info.show_name = show_name

            # Try to extract episode number
            for pattern in self._episode_patterns:
                match = pattern.search(filename)
                if match:
                    media_info.episode = int(match.group(2))
                    break

            return

        # Check if parent folder is a season folder
        season_match = self._season_start_pattern.search(parent) or self._season_end_pattern.search(parent)

        if season_match:
            media_info.is_show = True
            media_info.category = MediaCategory.SHOW
            media_info.season = int(season_match.group(1))

            # Extract show name from parent (remove season indicator)
            show_name_from_parent = self._season_end_pattern.sub('', parent).strip()
            show_name_from_parent = self._season_start_pattern.sub('', show_name_from_parent).strip()
            # Also remove "Season X" appearing anywhere in the string
            show_name_from_parent = re.sub(r'\s+[Ss]eason\s+\d+', '', show_name_from_parent).strip()
            show_name_from_parent = self._clean_show_name(show_name_from_parent)

            # Use parent-derived name if valid, otherwise try grandparent
            if show_name_from_parent and len(show_name_from_parent) > 1 and not self._is_generic_folder(show_name_from_parent):
                media_info.show_name = show_name_from_parent
            else:
                show_name = self._extract_show_name_from_ancestors(full_path, skip_count=1)
                if show_name:
                    media_info.show_name = show_name
                else:
                    media_info.show_name = self._clean_show_name(filename.split('.')[0])

            # Extract episode number from filename
            for pattern in self._episode_patterns:
                match = pattern.search(filename)
                if match:
                    media_info.episode = int(match.group(2))
                    break

            return

        # No season folder, check filename for episode patterns
        for pattern in self._episode_patterns:
            match = pattern.search(filename)
            if match:
                media_info.is_show = True
                media_info.category = MediaCategory.SHOW
                media_info.season = int(match.group(1))
                media_info.episode = int(match.group(2))

                # Try to get show name from ancestors
                show_name = self._extract_show_name_from_ancestors(full_path, skip_count=1)

                # If no valid ancestor, try parent folder
                if not show_name:
                    parent_clean = self._clean_show_name(parent)
                    parent_clean = re.sub(r'[Ss]eason\s*\d+', '', parent_clean).strip()
                    if parent_clean and len(parent_clean) > 1 and not self._is_generic_folder(parent_clean):
                        show_name = parent_clean

                # Last resort: extract from filename
                if not show_name:
                    show_name = self._clean_show_name(filename[:match.start()].strip())

                media_info.show_name = show_name if show_name else "Unknown"
                return

        # Check for episode-only patterns (no season number, default to season 1)
        for pattern in self._episode_only_patterns:
            match = pattern.search(filename)
            if match:
                media_info.is_show = True
                media_info.category = MediaCategory.SHOW
                media_info.season = 1
                media_info.episode = int(match.group(1))

                # Get show name using same logic
                show_name = self._extract_show_name_from_ancestors(full_path, skip_count=1)

                if not show_name:
                    parent_clean = self._clean_show_name(parent)
                    parent_clean = re.sub(r'[Ss]eason\s*\d+', '', parent_clean).strip()
                    if parent_clean and len(parent_clean) > 1 and not self._is_generic_folder(parent_clean):
                        show_name = parent_clean

                if not show_name:
                    show_name = self._clean_show_name(filename[:match.start()].strip())

                media_info.show_name = show_name if show_name else "Unknown"
                return
