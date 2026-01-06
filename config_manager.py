"""
Configuration Manager for Open Media Manager
Handles loading, saving, and managing application settings.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from constants import DEFAULT_CONFIG as CONST_DEFAULT_CONFIG


class ConfigManager:
    """Manages application configuration."""
    
    DEFAULT_CONFIG = CONST_DEFAULT_CONFIG
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the config file. If None, uses default location.
        """
        if config_path is None:
            # Use user's home directory for config
            config_dir = Path.home() / ".config" / "openmediamanager"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = config_dir / "config.json"
        else:
            self.config_path = config_path
    
    def config_exists(self) -> bool:
        """Check if configuration file exists."""
        return self.config_path.exists()
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Returns:
            Dictionary containing configuration settings.
        """
        if not self.config_exists():
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Merge with defaults to ensure all keys exist
            merged = self._merge_configs(self.DEFAULT_CONFIG, config)
            
            # Ensure quality_standards and encoding sections have all required bitrate keys
            # (in case config predates these keys)
            self._ensure_bitrate_keys(merged)
            
            return merged
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Dictionary containing configuration settings.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving config: {e}")
            return False
    
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge user config with default config, preserving structure.
        
        Args:
            default: Default configuration dictionary.
            user: User configuration dictionary.
            
        Returns:
            Merged configuration dictionary.
        """
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _ensure_bitrate_keys(self, config: Dict[str, Any]) -> None:
        """
        Ensure all resolution-specific bitrate keys exist in quality_standards section.
        This handles backwards compatibility with old config files.
        
        Args:
            config: Configuration dictionary to update in-place.
        """
        from constants import RECOMMENDED_SETTINGS
        
        # Ensure quality_standards has all bitrate keys
        if "quality_standards" not in config:
            config["quality_standards"] = {}
        
        qs = config["quality_standards"]
        for res in ["720p", "1080p", "1440p", "4k"]:
            min_key = f"min_bitrate_{res}"
            max_key = f"max_bitrate_{res}"
            
            if min_key not in qs:
                qs[min_key] = RECOMMENDED_SETTINGS[res]["min_bitrate"]
            if max_key not in qs:
                qs[max_key] = RECOMMENDED_SETTINGS[res]["max_bitrate"]
        
        # Ensure encoding section exists (but don't sync - it's independent)
        if "encoding" not in config:
            config["encoding"] = {}
        
        # Only add missing encoding bitrate keys if they don't exist
        enc = config["encoding"]
        for res in ["720p", "1080p", "1440p", "4k"]:
            enc_min_key = f"encoding_bitrate_min_{res}"
            enc_max_key = f"encoding_bitrate_max_{res}"
            
            if enc_min_key not in enc:
                enc[enc_min_key] = RECOMMENDED_SETTINGS[res]["min_bitrate"]
            if enc_max_key not in enc:
                enc[enc_max_key] = RECOMMENDED_SETTINGS[res]["max_bitrate"]
    
    def get_encoding_params(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract encoding parameters from config.
        
        Args:
            config: Configuration dictionary.
            
        Returns:
            Dictionary of encoding parameters.
        """
        enc = config.get("encoding", {})
        # Keep user-provided encoding settings but ensure all expected keys exist.
        # Start with defaults and overlay user values so callers can rely on keys.
        defaults = self.DEFAULT_CONFIG.get("encoding", {}).copy()

        # Merge user encoding settings onto defaults
        merged = defaults
        for k, v in enc.items():
            merged[k] = v

        # Determine codec based on codec_type and GPU setting
        codec_type = merged.get("codec_type", "x265")
        use_gpu = merged.get("use_gpu", False)

        if codec_type == "av1":
            codec = "av1_nvenc" if use_gpu else "libsvtav1"
        else:  # default to x265
            codec = "hevc_nvenc" if use_gpu else "libx265"

        # Expose both the raw merged settings and some convenience keys used by BatchEncoder
        merged_result = merged.copy()
        merged_result["codec"] = codec
        merged_result["use_gpu"] = use_gpu

        return merged_result
    
    def get_quality_standards(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract quality standards from config.
        
        Args:
            config: Configuration dictionary.
            
        Returns:
            Dictionary of quality standards.
        """
        return config.get("quality_standards", self.DEFAULT_CONFIG["quality_standards"])
