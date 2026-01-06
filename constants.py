"""
Constants and default values for Open Media Manager
Centralized configuration defaults based on recommended encoding standards.
"""

# Recommended Bitrate and Quality for x265 encoding (from CLI tool readme)
# Resolution: bitrate range, CQ value range
RECOMMENDED_SETTINGS = {
    "720p": {
        "bitrate_range": (1000, 2000),  # 1-2 Mbps
        "cq_range": (16, 20),
        "min_bitrate": 1000,
        "max_bitrate": 2000
    },
    "1080p_animation": {
        "bitrate_range": (1000, 3000),  # 1-3 Mbps
        "cq_range": (20, 25),
        "min_bitrate": 1000,
        "max_bitrate": 3000
    },
    "1080p": {
        "bitrate_range": (2000, 4000),  # 2-4 Mbps
        "cq_range": (18, 25),
        "min_bitrate": 2000,
        "max_bitrate": 4000
    },
    "1440p": {
        "bitrate_range": (4000, 6000),  # 4-6 Mbps
        "cq_range": (16, 23),
        "min_bitrate": 4000,
        "max_bitrate": 6000
    },
    "low_res": {
        "bitrate_range": (500, 1000),  # 500-1000 Kbps
        "cq_range": (22, 28),
        "min_bitrate": 500,
        "max_bitrate": 1000
    },
    "4k": {
        "bitrate_range": (6000, 10000),  # 6-10 Mbps
        "cq_range": (13, 18),
        "min_bitrate": 6000,
        "max_bitrate": 10000
    }
}

# Recommended Encoding Levels for x265 (from CLI tool readme)
ENCODING_LEVELS = {
    "720x480_40fps": "3.0",
    "1280x720_30fps": "3.1",
    "960x540_60fps": "3.1",
    "720x480_80fps": "3.1",
    "1280x720_60fps": "4.0",
    "1920x1080_30fps": "4.0",
    "1920x1080_60fps": "4.1",
    "3840x2160_30fps": "5.0",
    "3840x2160_60fps": "5.1"
}

# Codec options
CODEC_OPTIONS = {
    "x265": {
        "software": "libx265",
        "gpu": "hevc_nvenc",
        "display_name": "x265 (HEVC)"
    },
    "av1": {
        "software": "libsvtav1",
        "gpu": "av1_nvenc",
        "display_name": "AV1"
    }
}

# Default configuration structure
DEFAULT_CONFIG = {
    "media_path": "",
    "scan_threads": 8,  # Number of parallel threads for scanning media files
    "encoding": {
        "codec_type": "x265",
        "codec": "libx265",
        "use_gpu": False,
        "preset": "veryfast",
        "tune_animation": False,
        "level": "4.1",
        "cq": 22,
        "bitrate_min": "",
        "bitrate_max": "",
        "thread_count": 4,
        "use_bitrate_limits": False,
        "use_target_bitrate": False,  # Use target bitrate with CQ mode
        "target_bitrate_low_res": 800,  # Target bitrate for low res (<720p)
        "target_bitrate_720p": 1500,  # Target bitrate for 720p
        "target_bitrate_1080p": 3000,  # Target bitrate for 1080p
        "target_bitrate_1440p": 5000,  # Target bitrate for 1440p
        "target_bitrate_4k": 8000,  # Target bitrate for 4K
        "ignore_extras": True,  # Skip extras/bonus features during encoding
        "skip_video_encoding": False,  # Copy video without re-encoding
        "encoding_bitrate_min_low_res": RECOMMENDED_SETTINGS["low_res"]["min_bitrate"],
        "encoding_bitrate_max_low_res": RECOMMENDED_SETTINGS["low_res"]["max_bitrate"],
        "encoding_bitrate_min_720p": RECOMMENDED_SETTINGS["720p"]["min_bitrate"],
        "encoding_bitrate_max_720p": RECOMMENDED_SETTINGS["720p"]["max_bitrate"],
        "encoding_bitrate_min_1080p": RECOMMENDED_SETTINGS["1080p"]["min_bitrate"],
        "encoding_bitrate_max_1080p": RECOMMENDED_SETTINGS["1080p"]["max_bitrate"],
        "encoding_bitrate_min_1440p": RECOMMENDED_SETTINGS["1440p"]["min_bitrate"],
        "encoding_bitrate_max_1440p": RECOMMENDED_SETTINGS["1440p"]["max_bitrate"],
        "encoding_bitrate_min_4k": RECOMMENDED_SETTINGS["4k"]["min_bitrate"],
        "encoding_bitrate_max_4k": RECOMMENDED_SETTINGS["4k"]["max_bitrate"]
    },
    "audio": {
        "skip_audio_encoding": False,
        "default_language": "eng",
        "language_filter_enabled": False,
        "allowed_languages": ["eng"]
    },
    "subtitles": {
        "skip_subtitle_encoding": False,
        "default_language": "eng",
        "external_subtitles": True,
        "subtitle_encoding": "utf-8",
        "language_filter_enabled": False,
        "allowed_languages": ["eng"]
    },
    "metadata": {
        "add_cover_art": False,
        "cover_art_path": "",
        "add_external_subs": False,
        "external_subs_path": ""
    },
    "naming": {
        "rename_files": True,
        "replace_periods": True,
        "episode_index": 0,
        "title_start_index": 0,
        "title_end_index": 0
    },
    "quality_standards": {
        "min_resolution": "720p",
        "min_bitrate_low_res": RECOMMENDED_SETTINGS["low_res"]["min_bitrate"],
        "max_bitrate_low_res": RECOMMENDED_SETTINGS["low_res"]["max_bitrate"],
        "min_bitrate_720p": RECOMMENDED_SETTINGS["720p"]["min_bitrate"],
        "max_bitrate_720p": RECOMMENDED_SETTINGS["720p"]["max_bitrate"],
        "min_bitrate_1080p": RECOMMENDED_SETTINGS["1080p"]["min_bitrate"],
        "max_bitrate_1080p": RECOMMENDED_SETTINGS["1080p"]["max_bitrate"],
        "min_bitrate_1440p": RECOMMENDED_SETTINGS["1440p"]["min_bitrate"],
        "max_bitrate_1440p": RECOMMENDED_SETTINGS["1440p"]["max_bitrate"],
        "min_bitrate_4k": RECOMMENDED_SETTINGS["4k"]["min_bitrate"],
        "max_bitrate_4k": RECOMMENDED_SETTINGS["4k"]["max_bitrate"],
        "preferred_codec": "hevc",
        "bit_depth_preference": "source"  # Options: "source", "force_10bit", "force_8bit"
    },
    "ui": {
        "show_pretty_output": True,
        "auto_compare_filesizes": True
    },
    "manual_overrides": {}  # Store manual category/metadata overrides {file_path: {category, show_name, etc}}
}

# Help text for UI tooltips and dialogs
HELP_TEXT = {
    "quality_standards": (
        "Quality Standards define the acceptable bitrate ranges for your media files.\n\n"
        "Files with bitrates BELOW the minimum will be marked as 'Below Standard' and "
        "skipped during encoding (cannot enhance low-quality sources).\n\n"
        "Files with bitrates ABOVE the maximum will be marked as 'Needs Re-encoding' "
        "and can be re-encoded to reduce file size while maintaining quality."
    ),
    "encoding_bitrate": (
        "Encoding Bitrate settings control the actual bitrate limits used during re-encoding.\n\n"
        "These are separate from Quality Standards and only apply when 'Use Bitrate Limits' "
        "is enabled.\n\n"
        "Min bitrate ensures the output has sufficient quality.\n"
        "Max bitrate prevents files from becoming too large.\n\n"
        "If disabled, encoding will use only the Constant Quality (CQ) setting."
    ),
    "gpu_encoding": (
        "GPU encoding (NVENC) uses your NVIDIA graphics card for faster encoding.\n\n"
        "Benefits: Much faster encoding speed\n"
        "Tradeoffs: Slightly lower quality at same bitrate, fewer tuning options\n\n"
        "When GPU is enabled, thread count is not used (GPU handles parallelization)."
    ),
    "thread_count": (
        "Number of CPU threads to use for encoding.\n\n"
        "More threads = faster encoding, but more CPU usage.\n"
        "Recommended: Number of physical CPU cores (not hyperthreads).\n\n"
        "Note: This setting is disabled when GPU encoding is enabled."
    ),
    "constant_quality": (
        "Constant Quality (CQ/CRF) is the primary quality control.\n\n"
        "Lower values = higher quality, larger files\n"
        "Higher values = lower quality, smaller files\n\n"
        "Recommended ranges:\n"
        "• 720p: 16-20\n"
        "• 1080p: 18-25 (20-25 for animation)\n"
        "• 1440p: 16-23\n"
        "• 4K: 13-18"
    ),
    "target_bitrate": (
        "Target Bitrate works with Constant Quality mode to guide encoding.\n\n"
        "When enabled, ffmpeg will try to achieve the target bitrate while "
        "maintaining the CQ setting. This provides more predictable file sizes.\n\n"
        "Target bitrate can be used independently or together with min/max limits.\n\n"
        "Use this when you want consistent file sizes across your media library."
    )
}

# Media file extensions to scan
MEDIA_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts'}

# Status emoji indicators
STATUS_EMOJI = {
    "compliant": "✅",
    "needs_encoding": "⚠️",
    "below_standard": "❌",
    "scanning": "🔍",
    "error": "⛔",
    "unknown": "❔"
}
