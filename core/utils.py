"""
Utility functions for Open Media Manager
Shared utilities to avoid code duplication across modules.
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def get_resolution_category(
    width: int,
    height: int,
    quality_standards: dict
) -> Tuple[str, int, int]:
    """
    Determine resolution category and bitrate ranges based on dimensions.
    
    Uses width-first detection for consistent categorization across aspect ratios.
    Falls back to height for portrait/narrow content.
    
    Args:
        width: Video width in pixels
        height: Video height in pixels
        quality_standards: Dictionary containing bitrate settings
        
    Returns:
        Tuple of (category_name, min_bitrate_kbps, max_bitrate_kbps)
    """
    # Width-first detection (handles all landscape/standard content)
    if width >= 3840:
        res_category = "4k"
        min_bitrate = quality_standards.get("min_bitrate_4k", 6000)
        max_bitrate = quality_standards.get("max_bitrate_4k", 10000)
    elif width >= 2560:
        res_category = "1440p"
        min_bitrate = quality_standards.get("min_bitrate_1440p", 3000)
        max_bitrate = quality_standards.get("max_bitrate_1440p", 6000)
    elif width >= 1900:
        # 1080p class: 1920-wide content regardless of height
        res_category = "1080p"
        min_bitrate = quality_standards.get("min_bitrate_1080p", 1500)
        max_bitrate = quality_standards.get("max_bitrate_1080p", 4000)
    elif width >= 1200:
        # 720p class: 1280-wide content regardless of height
        res_category = "720p"
        min_bitrate = quality_standards.get("min_bitrate_720p", 1000)
        max_bitrate = quality_standards.get("max_bitrate_720p", 2000)
    # Height fallback for portrait/narrow content only
    elif height >= 2160:
        res_category = "4k"
        min_bitrate = quality_standards.get("min_bitrate_4k", 6000)
        max_bitrate = quality_standards.get("max_bitrate_4k", 10000)
    elif height >= 1440:
        res_category = "1440p"
        min_bitrate = quality_standards.get("min_bitrate_1440p", 3000)
        max_bitrate = quality_standards.get("max_bitrate_1440p", 6000)
    elif height >= 1080:
        res_category = "1080p"
        min_bitrate = quality_standards.get("min_bitrate_1080p", 1500)
        max_bitrate = quality_standards.get("max_bitrate_1080p", 4000)
    elif height >= 720:
        res_category = "720p"
        min_bitrate = quality_standards.get("min_bitrate_720p", 1000)
        max_bitrate = quality_standards.get("max_bitrate_720p", 2000)
    else:
        # Below 720p - use low_res bitrate settings
        res_category = "low_res"
        min_bitrate = quality_standards.get("min_bitrate_low_res", 500)
        max_bitrate = quality_standards.get("max_bitrate_low_res", 1000)
    
    return res_category, min_bitrate, max_bitrate


def format_file_size(size_bytes: int) -> Tuple[float, str]:
    """
    Format file size in appropriate unit.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Tuple of (size_value, unit_string)
        
    Examples:
        >>> format_file_size(1500)
        (1.46, 'KB')
        >>> format_file_size(1500000000)
        (1.40, 'GB')
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return size_bytes, unit
        size_bytes /= 1024.0
    return size_bytes, 'TB'


def format_size_with_unit(size_bytes: float) -> str:
    """
    Format file size with unit as a single string.
    
    Args:
        size_bytes: Size in bytes (can be float)
        
    Returns:
        Formatted string like "1.40 GB"
    """
    value, unit = format_file_size(int(size_bytes))
    return f"{value:.2f} {unit}"


def calculate_size_reduction(original_size: int, new_size: int) -> float:
    """
    Calculate percentage size reduction (positive = smaller, negative = larger).
    
    Args:
        original_size: Original file size in bytes
        new_size: New file size in bytes
        
    Returns:
        Percentage change (positive for reduction, negative for increase)
    """
    if original_size == 0:
        return 0.0
    return ((original_size - new_size) / original_size) * 100
