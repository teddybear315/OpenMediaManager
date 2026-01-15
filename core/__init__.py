"""
Core module - centralized configuration, media scanning, and batch encoding
"""

from .batch_encoder import BatchEncoder, EncodingJob, EncodingThread
from .config_manager import ConfigManager
from .constants import (CODEC_OPTIONS, DEFAULT_CONFIG, ENCODING_LEVELS,
                        HELP_TEXT, MEDIA_EXTENSIONS, RECOMMENDED_SETTINGS,
                        STATUS_EMOJI)
from .media_scanner import MediaCategory, MediaInfo, MediaScanner, MediaStatus

__all__ = [
    'DEFAULT_CONFIG',
    'RECOMMENDED_SETTINGS',
    'ENCODING_LEVELS',
    'CODEC_OPTIONS',
    'HELP_TEXT',
    'MEDIA_EXTENSIONS',
    'STATUS_EMOJI',
    'ConfigManager',
    'MediaScanner',
    'MediaInfo',
    'MediaStatus',
    'MediaCategory',
    'BatchEncoder',
    'EncodingThread',
    'EncodingJob',
]
