# Open Media Manager

A PyQt6-based GUI application for managing and re-encoding media files with intelligent quality standards and batch processing.

## Features

- 📁 **Directory Scanning**: Recursively scan directories for media files
- 🔍 **Media Analysis**: Use ffprobe to analyze codec, resolution, bitrate, and bit depth
- 📺 **TV Show Detection**: Automatically detects TV shows vs movies and parses episode information
- 🌳 **Hierarchical View**: Collapsible tree structure organized by show → season → episode
- ✅ **Quality Standards**: Automatically check if files meet your quality standards
- 🎬 **Batch Encoding**: Re-encode multiple files with optimized settings
- 🎨 **Metadata Tool**: Separately add cover art and/or subtitles to existing videos
- 📊 **Status Indicators**: Visual emoji status for each file (✅ Compliant, ⚠️ Needs Re-encoding, ❌ Below Standard)
- 🎯 **Smart Detection**: Automatically detect TV shows, seasons, and episodes from filenames
- ⚙️ **Configurable Settings**: Store encoding preferences and quality standards in a config file
- 🎨 **Modern GUI**: Clean PyQt6 interface with tree view and progress tracking
- 🚀 **Two Encoding Modes**: 
  - **Reencode Selected**: Re-encode specific files you select
  - **Reencode HQ**: Only re-encode high-quality (1080p+) sources

## Requirements

### System Requirements
- Python 3.8 or higher
- FFmpeg (with libx265 support)
- FFprobe (usually comes with FFmpeg)

### Python Dependencies
- PyQt6

## Installation

1. **Clone or download this repository**

2. **Set up Python virtual environment** (recommended):
   ```bash
   cd "/Volumes/Holocron 2/OpenMediaManager"
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install FFmpeg** (if not already installed):
   
   **macOS**:
   ```bash
   brew install ffmpeg
   ```
   
   **Ubuntu/Debian**:
   ```bash
   sudo apt-get install ffmpeg
   ```
   
   **Windows**:
   Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

5. **Verify FFmpeg installation**:
   ```bash
   ffmpeg -version
   ffprobe -version
   ```

## Usage

### First Run

1. **Start the application**:
   ```bash
   python main.py
   ```

2. **First Run Setup**: On first launch, you'll be prompted to configure:
   - **Media Path**: Default directory for your media files (with browse button)
   - **Encoding Settings**: 
     - GPU acceleration (NVENC) - *disables thread count when enabled*
     - 10-bit encoding
     - Animation tuning
     - Constant Quality (CQ) value (with recommended ranges tooltip)
     - Encoding level
     - Thread count (disabled when GPU is enabled)
   - **Quality Standards**: Minimum and maximum bitrates for checking file compliance
     - Click the **?** button for detailed explanation
     - Files below minimum bitrate are marked "Below Standard" and skipped
     - Files above maximum bitrate are marked "Needs Re-encoding"
   - **Encoding Bitrate Settings**: Optional bitrate limits used during actual encoding
     - Click the **?** button for detailed explanation
     - Separate from quality standards for flexibility
     - Can be enabled/disabled independently

3. Configuration is saved to `~/.config/openmediamanager/config.json`

### Configuration Details

The application uses recommended bitrates from the original CLI tool:

| Resolution | Min Bitrate | Max Bitrate | Recommended CQ |
|-----------|-------------|-------------|----------------|
| 720p      | 1000 kbps   | 2000 kbps   | 16-20         |
| 1080p     | 2000 kbps   | 4000 kbps   | 18-25         |
| 1440p     | 4000 kbps   | 6000 kbps   | 16-23         |
| 4K        | 6000 kbps   | 10000 kbps  | 13-18         |

These defaults are defined in [constants.py](constants.py) for easy modification.

### Main Interface

#### Scanning Media

1. Click **"Rescan"** (or application auto-scans on startup if path configured)
2. The application will:
   - Find all media files (mkv, mp4, avi, mov, m4v, ts)
   - Run ffprobe on each file to analyze properties
   - Detect TV shows vs movies and parse episode information
   - Compare against your quality standards
   - Display results in a hierarchical tree organized by show/season

The tree structure organizes content as:
- 📺 **TV Shows** section (collapsed by default)
  - Show names parsed from filenames/folders
  - Seasons grouped together
  - Episodes sorted numerically (E01, E02, etc.)
- 🎬 **Movies** section (collapsed by default)
  - All non-TV show files listed alphabetically

**Supported TV Show Patterns:**
- `Show Name S01E01.mkv` (S##E## format)
- `Show Name 1x01.mkv` (season x episode format)
- `/Show Name/Season 1/Episode Title.mkv` (folder structure)

Click the arrows to expand/collapse sections and browse your library efficiently.

#### Understanding Status Indicators

- ✅ **Compliant**: File meets all quality standards (correct codec, bit depth, bitrate)
- ⚠️ **Needs Re-encoding**: File doesn't meet standards but is good enough to re-encode
- ❌ **Below Standard**: File resolution too low; will be skipped during batch encoding
- 🔍 **Scanning**: Currently analyzing file
- ⛔ **Error**: Error occurred during analysis
- ❔ **Unknown**: Not yet scanned

#### Re-encoding Files

**Option 1: Reencode Selected**
1. Select one or more files in the tree (Ctrl+Click or Cmd+Click)
   - You can select individual episodes, entire seasons, or shows
   - Only actual media files (not group nodes) will be encoded
2. Click **"Reencode Selected"**
3. Confirm the operation
4. Monitor progress in real-time

**Option 2: Reencode HQ**
1. Click **"Reencode HQ"**
2. Only files with 1080p or higher resolution that need re-encoding will be processed
3. Files below 1080p and files below quality standards are skipped
4. Ideal for ensuring high-quality sources are optimally encoded

#### Add Metadata Tool

The **"Add Metadata"** button opens a separate tool for adding cover art and/or subtitles to existing video files without re-encoding them. This is independent of the main encoding workflow.

**Features:**
1. **Target Folder Selection**: Choose a specific folder containing videos to modify
2. **Cover Art**: 
   - Select a single image file (JPG, PNG) to add to all videos
   - Cover art will be embedded as an attached picture
3. **Subtitles**:
   - **Language Code**: Specify 3-letter language code (e.g., "eng", "jpn", "spa")
   - **Folder Search Mode**: Automatically searches for matching files with pattern `videoname.{lang}.srt`
   - **Per-Video Mode**: Manually select subtitle file for each video individually
4. **Output**: Creates new files with `_metadata` suffix, preserving originals

**Usage:**
1. Click **"Add Metadata"** button
2. Select target folder containing videos
3. Check "Add cover art" and/or "Add subtitles"
4. Configure options:
   - For cover art: Browse and select an image file
   - For subtitles: 
     - Enter 3-letter language code (e.g., "eng", "jpn", "spa")
     - Choose folder search (finds `videoname.eng.srt` files) or per-video selection
5. Click **"Process Videos"**
6. Review progress and results

This tool uses FFmpeg's stream copy (no re-encoding), making it fast for adding metadata.

#### Settings

Click **"Settings"** to modify:
- **General**: Media path (with browse button)
- **Encoding**: Codec, GPU usage, bit depth, CQ, level, preset, threads
  - Thread count is automatically disabled when GPU encoding is enabled
  - Tooltips provide contextual help for each setting
- **Quality Standards**: Minimum and maximum bitrates for each resolution tier
  - Help button (?) explains how these affect file scanning
- **Encoding Bitrate**: Optional bitrate limits for the encoding process
  - Help button (?) explains the difference from quality standards
  - Can be toggled on/off independently
- **Language Filtering**: Configure which audio and subtitle languages to keep during encoding

Settings are immediately saved and applied to future scans.

### Help System

Throughout the application, you'll find:
- **? buttons**: Click for detailed explanations of bitrate settings
- **Tooltips**: Hover over fields like CQ and Thread Count for guidance
- **Contextual information**: Understand the difference between quality checking and encoding settings

## Configuration File

Configuration is stored in JSON format at:
- **macOS/Linux**: `~/.config/openmediamanager/config.json`
- **Windows**: `C:\Users\<username>\.config\openmediamanager\config.json`

### Example Configuration

```json
{
  "media_path": "/path/to/media",
  "encoding": {
    "codec": "libx265",
    "use_gpu": false,
    "preset": "medium",
    "tune_animation": false,
    "ten_bit": true,
    "level": "4.0",
    "cq": 22,
    "bitrate_min": "",
    "bitrate_max": "",
    "thread_count": 4
  },
  "quality_standards": {
    "min_resolution": "720p",
    "max_bitrate_720p": 2000,
    "max_bitrate_1080p": 4000,
    "max_bitrate_1440p": 6000,
    "max_bitrate_4k": 10000,
    "preferred_codec": "hevc",
    "require_10bit": true
  }
}
```

## Quality Standards Reference

Based on your CLI tool readme, here are the recommended settings:

### Bitrate and Quality for x265

| Resolution       | Bitrate  | CQ Value |
|-----------------|----------|----------|
| 720p            | 1-2 Mbps | 16-20    |
| 1080p Animation | 1-3 Mbps | 20-25    |
| 1080p           | 2-4 Mbps | 18-25    |
| 1440p           | 4-6 Mbps | 16-23    |
| 4K              | 6-10 Mbps| 13-18    |

### Encoding Levels

| Resolution  | FPS | Level |
|------------|-----|-------|
| 720×480    | 40  | 3.0   |
| 1280×720   | 30  | 3.1   |
| 1280×720   | 60  | 4.0   |
| 1920×1080  | 30  | 4.0   |
| 1920×1080  | 60  | 4.1   |
| 3840×2160  | 30  | 5.0   |
| 3840×2160  | 60  | 5.1   |

## Features Inherited from CLI Tool

This GUI application incorporates functionality from your CLI tool:

- ✅ **Metadata handling**: Show detection, season/episode parsing
- ✅ **Encoding parameters**: CQ, level, bitrate control, 10-bit, threads
- ✅ **GPU acceleration**: NVENC support
- ✅ **Quality presets**: Based on resolution and content type
- ✅ **Smart filtering**: Skip files below quality standards
- ✅ **Batch processing**: Process multiple files efficiently

## Output Files

Encoded files are saved to an `encoded` subdirectory within the source folder:
- Original: `/path/to/media/Show.S01E01.mkv`
- Encoded: `/path/to/media/encoded/Show S01E01.mkv`

Files are automatically renamed to clean format if naming is enabled in settings.

## Troubleshooting

### "FFmpeg not found" error
- Ensure FFmpeg is installed and in your system PATH
- Test with: `ffmpeg -version`

### "0 byte output files"
- Check FFmpeg output for errors
- Try adjusting encoding settings (lower CQ, different preset)
- Verify source file is valid

### Slow encoding
- Use GPU acceleration if available (NVENC)
- Increase thread count
- Use faster preset (e.g., "fast" instead of "slow")

### Application won't start
- Verify Python version: `python --version` (should be 3.8+)
- Reinstall dependencies: `pip install -r requirements.txt`
- Check for PyQt6 installation issues

## Advanced Usage

### Customizing Default Settings

All default bitrate values and recommended settings are centralized in [constants.py](constants.py):
- `RECOMMENDED_SETTINGS`: Bitrate ranges and CQ values for each resolution
- `DEFAULT_CONFIG`: Complete default configuration structure
- `HELP_TEXT`: Help messages shown in dialogs
- `ENCODING_LEVELS`: Recommended encoding levels by resolution and FPS

To change defaults application-wide, edit [constants.py](constants.py) instead of modifying multiple locations.

### Custom Encoding Parameters

Edit `config.json` directly to access additional parameters:
- `use_bitrate_limits`: Enable/disable encoding bitrate constraints
- `encoding_bitrate_min_*` and `encoding_bitrate_max_*`: Resolution-specific encoding limits
- `preset`: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
- `naming` section: Control file renaming behavior

### Show/Season Detection

The application automatically detects:
- `S01E01` format
- `1x01` format
- `Season 1 Episode 1` format
- Season folders in directory structure

## Development

### Project Structure

```
OpenMediaManager/
├── main.py              # Application entry point
├── config_manager.py    # Configuration management
├── constants.py         # Centralized defaults and recommended settings
├── media_scanner.py     # Directory scanning and ffprobe analysis
├── batch_encoder.py     # FFmpeg encoding operations
├── gui_components.py    # PyQt6 GUI components
├── test_constants.py    # Test script for configuration
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

### Key Design Decisions

**Centralized Constants**: All default values are in `constants.py` to avoid duplication and make customization easier.

**Separate Quality Standards vs Encoding Settings**: 
- Quality Standards check if files are compliant (min/max bitrates)
- Encoding Bitrate Settings control the actual encoding process
- This separation provides flexibility in how you manage your library

**GPU-Aware UI**: Thread count is automatically disabled when GPU encoding is enabled since GPU handles its own parallelization.

### Contributing

Contributions welcome! Areas for improvement:
- Tree view for hierarchical show/season display
- Real-time encoding preview
- Comparison of file sizes before/after
- More encoding presets
- Support for additional codecs (AV1, VP9)

## License

This project is open source. Feel free to use and modify as needed.

## Credits

Based on the CLI media encoding tool workflow, adapted to a modern GUI interface with enhanced features and usability.
