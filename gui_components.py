"""
GUI Components for Open Media Manager
Main window, dialogs, and custom widgets.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QDialog, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QComboBox,
    QLabel, QProgressBar, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGroupBox, QDialogButtonBox, QTextEdit, QTabWidget, QMenu,
    QScrollArea
)
from collections import defaultdict
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush, QFont

from config_manager import ConfigManager
from media_scanner import MediaScanner, MediaInfo, MediaStatus, MediaCategory
from batch_encoder import BatchEncoder, EncodingThread, EncodingMode
from constants import RECOMMENDED_SETTINGS, HELP_TEXT


class OOTBDialog(QDialog):
    """Dialog for first-time setup."""
    
    def __init__(self, parent=None):
        """Initialize the first run dialog."""
        super().__init__(parent)
        self.setWindowTitle("Open Media Manager - First Run Setup")
        self.setMinimumWidth(600)
        self.settings = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout()
        
        # Welcome message
        welcome = QLabel(
            "<h2>Welcome to Open Media Manager!</h2>"
            "<p>Let's configure your initial settings.</p>"
        )
        layout.addWidget(welcome)
        
        # Form layout for settings
        form_layout = QFormLayout()
        
        # Media path
        path_layout = QHBoxLayout()
        self.media_path_edit = QLineEdit()
        self.media_path_edit.setPlaceholderText("Select your media folder...")
        path_browse_btn = QPushButton("Browse...")
        path_browse_btn.clicked.connect(self._browse_media_path)
        path_layout.addWidget(self.media_path_edit)
        path_layout.addWidget(path_browse_btn)
        form_layout.addRow("Media Path:", path_layout)
        
        # Add form layout to main layout
        layout.addLayout(form_layout)
        
        # Encoding settings
        encoding_group = QGroupBox("Encoding Settings")
        encoding_layout = QFormLayout()
        
        self.codec_combo = QComboBox()
        self.codec_combo.addItem("x265 (HEVC)", "x265")
        self.codec_combo.addItem("AV1", "av1")
        self.codec_combo.setToolTip("Choose the video codec for encoding")
        encoding_layout.addRow("Codec:", self.codec_combo)
        
        self.use_gpu_check = QCheckBox("Use GPU (NVENC)")
        self.use_gpu_check.stateChanged.connect(self._on_gpu_changed)
        encoding_layout.addRow("", self.use_gpu_check)
        
        self.tune_animation_check = QCheckBox("Tune for animation")
        encoding_layout.addRow("", self.tune_animation_check)
        
        self.ignore_extras_check = QCheckBox("Ignore extras/bonus features when encoding")
        self.ignore_extras_check.setChecked(True)
        self.ignore_extras_check.setToolTip("Skip bonus features, BTS content, trailers, etc. during batch encoding")
        encoding_layout.addRow("", self.ignore_extras_check)
        
        self.skip_video_check = QCheckBox("Skip video encoding (copy stream)")
        self.skip_video_check.setToolTip("Copy video stream without re-encoding (for format conversion only)")
        encoding_layout.addRow("", self.skip_video_check)
        
        self.skip_audio_check = QCheckBox("Skip audio encoding (copy stream)")
        self.skip_audio_check.setToolTip("Copy audio stream without re-encoding")
        encoding_layout.addRow("", self.skip_audio_check)
        
        self.skip_subtitle_check = QCheckBox("Skip subtitle encoding (copy stream)")
        self.skip_subtitle_check.setToolTip("Copy subtitle stream without re-encoding")
        encoding_layout.addRow("", self.skip_subtitle_check)
        
        self.lossless_mode_check = QCheckBox("Use lossless mode")
        self.lossless_mode_check.setToolTip("Use lossless encoding for heavily compressed sources (ignores CQ setting)")
        encoding_layout.addRow("", self.lossless_mode_check)
        
        self.cq_spin = QSpinBox()
        self.cq_spin.setRange(10, 35)
        self.cq_spin.setValue(22)
        self.cq_spin.setToolTip(HELP_TEXT["constant_quality"])
        encoding_layout.addRow("Constant Quality (CQ):", self.cq_spin)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["3.0", "3.1", "4.0", "4.1", "5.0", "5.1"])
        self.level_combo.setCurrentText("4.0")
        encoding_layout.addRow("Encoding Level:", self.level_combo)
        
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 32)
        self.threads_spin.setValue(4)
        self.threads_spin.setToolTip(HELP_TEXT["thread_count"])
        encoding_layout.addRow("Thread Count:", self.threads_spin)
        
        encoding_group.setLayout(encoding_layout)
        layout.addWidget(encoding_group)
        
        # Encoding bitrate settings
        enc_bitrate_group = QGroupBox("Encoding Bitrate Settings")
        enc_bitrate_layout = QFormLayout()
        
        # Header with help button
        enc_header_layout = QHBoxLayout()
        enc_header_label = QLabel("<b>Bitrate limits for encoding (optional):</b>")
        help_btn_enc = QPushButton("?")
        help_btn_enc.setMaximumWidth(30)
        help_btn_enc.clicked.connect(lambda: self._show_help("encoding_bitrate"))
        help_btn_enc.setToolTip("Click for more information")
        enc_header_layout.addWidget(enc_header_label)
        enc_header_layout.addWidget(help_btn_enc)
        enc_header_layout.addStretch()
        enc_bitrate_layout.addRow(enc_header_layout)
        
        self.use_encoding_bitrate_check = QCheckBox("Use bitrate limits during encoding")
        enc_bitrate_layout.addRow("", self.use_encoding_bitrate_check)
        
        # 720p encoding bitrate (min and max in same row)
        enc_720p_layout = QHBoxLayout()
        enc_720p_layout.addWidget(QLabel("Min:"))
        self.enc_bitrate_min_720p_spin = QSpinBox()
        self.enc_bitrate_min_720p_spin.setRange(500, 5000)
        self.enc_bitrate_min_720p_spin.setValue(RECOMMENDED_SETTINGS["720p"]["min_bitrate"])
        self.enc_bitrate_min_720p_spin.setSuffix(" kbps")
        enc_720p_layout.addWidget(self.enc_bitrate_min_720p_spin)
        enc_720p_layout.addWidget(QLabel("Max:"))
        self.enc_bitrate_max_720p_spin = QSpinBox()
        self.enc_bitrate_max_720p_spin.setRange(500, 5000)
        self.enc_bitrate_max_720p_spin.setValue(RECOMMENDED_SETTINGS["720p"]["max_bitrate"])
        self.enc_bitrate_max_720p_spin.setSuffix(" kbps")
        enc_720p_layout.addWidget(self.enc_bitrate_max_720p_spin)
        enc_bitrate_layout.addRow("Encoding (720p):", enc_720p_layout)
        
        # 1080p encoding bitrate (min and max in same row)
        enc_1080p_layout = QHBoxLayout()
        enc_1080p_layout.addWidget(QLabel("Min:"))
        self.enc_bitrate_min_1080p_spin = QSpinBox()
        self.enc_bitrate_min_1080p_spin.setRange(1000, 10000)
        self.enc_bitrate_min_1080p_spin.setValue(RECOMMENDED_SETTINGS["1080p"]["min_bitrate"])
        self.enc_bitrate_min_1080p_spin.setSuffix(" kbps")
        enc_1080p_layout.addWidget(self.enc_bitrate_min_1080p_spin)
        enc_1080p_layout.addWidget(QLabel("Max:"))
        self.enc_bitrate_max_1080p_spin = QSpinBox()
        self.enc_bitrate_max_1080p_spin.setRange(1000, 10000)
        self.enc_bitrate_max_1080p_spin.setValue(RECOMMENDED_SETTINGS["1080p"]["max_bitrate"])
        self.enc_bitrate_max_1080p_spin.setSuffix(" kbps")
        enc_1080p_layout.addWidget(self.enc_bitrate_max_1080p_spin)
        enc_bitrate_layout.addRow("Encoding (1080p):", enc_1080p_layout)
        
        enc_bitrate_group.setLayout(enc_bitrate_layout)
        layout.addWidget(enc_bitrate_group)
        
        # Quality standards
        quality_group = QGroupBox("Quality Standards")
        quality_layout = QFormLayout()
        
        # Header with help button
        header_layout = QHBoxLayout()
        header_label = QLabel("<b>Bitrate ranges for checking file compliance:</b>")
        help_btn_qs = QPushButton("?")
        help_btn_qs.setMaximumWidth(30)
        help_btn_qs.clicked.connect(lambda: self._show_help("quality_standards"))
        help_btn_qs.setToolTip("Click for more information")
        header_layout.addWidget(header_label)
        header_layout.addWidget(help_btn_qs)
        header_layout.addStretch()
        quality_layout.addRow(header_layout)
        
        # 720p quality standards (min and max in same row)
        qs_720p_layout = QHBoxLayout()
        qs_720p_layout.addWidget(QLabel("Min:"))
        self.min_bitrate_720p_spin = QSpinBox()
        self.min_bitrate_720p_spin.setRange(500, 5000)
        self.min_bitrate_720p_spin.setValue(RECOMMENDED_SETTINGS["720p"]["min_bitrate"])
        self.min_bitrate_720p_spin.setSuffix(" kbps")
        qs_720p_layout.addWidget(self.min_bitrate_720p_spin)
        qs_720p_layout.addWidget(QLabel("Max:"))
        self.max_bitrate_720p_spin = QSpinBox()
        self.max_bitrate_720p_spin.setRange(500, 5000)
        self.max_bitrate_720p_spin.setValue(RECOMMENDED_SETTINGS["720p"]["max_bitrate"])
        self.max_bitrate_720p_spin.setSuffix(" kbps")
        qs_720p_layout.addWidget(self.max_bitrate_720p_spin)
        quality_layout.addRow("Bitrate (720p):", qs_720p_layout)
        
        # 1080p quality standards (min and max in same row)
        qs_1080p_layout = QHBoxLayout()
        qs_1080p_layout.addWidget(QLabel("Min:"))
        self.min_bitrate_1080p_spin = QSpinBox()
        self.min_bitrate_1080p_spin.setRange(1000, 10000)
        self.min_bitrate_1080p_spin.setValue(RECOMMENDED_SETTINGS["1080p"]["min_bitrate"])
        self.min_bitrate_1080p_spin.setSuffix(" kbps")
        qs_1080p_layout.addWidget(self.min_bitrate_1080p_spin)
        qs_1080p_layout.addWidget(QLabel("Max:"))
        self.max_bitrate_1080p_spin = QSpinBox()
        self.max_bitrate_1080p_spin.setRange(1000, 10000)
        self.max_bitrate_1080p_spin.setValue(RECOMMENDED_SETTINGS["1080p"]["max_bitrate"])
        self.max_bitrate_1080p_spin.setSuffix(" kbps")
        qs_1080p_layout.addWidget(self.max_bitrate_1080p_spin)
        quality_layout.addRow("Bitrate (1080p):", qs_1080p_layout)
        
        # 4K quality standards (min and max in same row)
        qs_4k_layout = QHBoxLayout()
        qs_4k_layout.addWidget(QLabel("Min:"))
        self.min_bitrate_4k_spin = QSpinBox()
        self.min_bitrate_4k_spin.setRange(5000, 20000)
        self.min_bitrate_4k_spin.setValue(RECOMMENDED_SETTINGS["4k"]["min_bitrate"])
        self.min_bitrate_4k_spin.setSuffix(" kbps")
        qs_4k_layout.addWidget(self.min_bitrate_4k_spin)
        qs_4k_layout.addWidget(QLabel("Max:"))
        self.max_bitrate_4k_spin = QSpinBox()
        self.max_bitrate_4k_spin.setRange(5000, 20000)
        self.max_bitrate_4k_spin.setValue(RECOMMENDED_SETTINGS["4k"]["max_bitrate"])
        self.max_bitrate_4k_spin.setSuffix(" kbps")
        qs_4k_layout.addWidget(self.max_bitrate_4k_spin)
        quality_layout.addRow("Bitrate (4K):", qs_4k_layout)
        
        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def _on_gpu_changed(self, state):
        """Handle GPU checkbox state change."""
        # Disable thread count when GPU is enabled
        self.threads_spin.setEnabled(not self.use_gpu_check.isChecked())
    
    def _show_help(self, topic: str):
        """Show help dialog for a topic."""
        help_text = HELP_TEXT.get(topic, "No help available for this topic.")
        QMessageBox.information(self, f"Help: {topic.replace('_', ' ').title()}", help_text)
    
    def _browse_media_path(self):
        """Browse for media path."""
        path = QFileDialog.getExistingDirectory(self, "Select Media Folder")
        if path:
            self.media_path_edit.setText(path)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get settings from dialog."""
        return {
            "media_path": self.media_path_edit.text(),
            "scan_threads": 8,  # Default value for OOTB
            "encoding": {
                "codec_type": self.codec_combo.currentData(),
                "codec": "libx265",
                "use_gpu": self.use_gpu_check.isChecked(),
                "preset": "medium",
                "tune_animation": self.tune_animation_check.isChecked(),
                "ignore_extras": self.ignore_extras_check.isChecked(),
                "skip_video_encoding": self.skip_video_check.isChecked(),
                "skip_audio_encoding": self.skip_audio_check.isChecked(),
                "skip_subtitle_encoding": self.skip_subtitle_check.isChecked(),
                "lossless_mode": self.lossless_mode_check.isChecked(),
                "level": self.level_combo.currentText(),
                "cq": self.cq_spin.value(),
                "bitrate_min": "",
                "bitrate_max": "",
                "thread_count": self.threads_spin.value(),
                "use_bitrate_limits": self.use_encoding_bitrate_check.isChecked(),
                "encoding_bitrate_min_720p": self.enc_bitrate_min_720p_spin.value(),
                "encoding_bitrate_max_720p": self.enc_bitrate_max_720p_spin.value(),
                "encoding_bitrate_min_1080p": self.enc_bitrate_min_1080p_spin.value(),
                "encoding_bitrate_max_1080p": self.enc_bitrate_max_1080p_spin.value(),
                "encoding_bitrate_min_1440p": 3000,
                "encoding_bitrate_max_1440p": 6000,
                "encoding_bitrate_min_4k": 6000,
                "encoding_bitrate_max_4k": 10000
            },
            "audio": {
                "skip_audio_encoding": False,
                "default_language": "eng"
            },
            "subtitles": {
                "skip_subtitle_encoding": False,
                "default_language": "eng",
                "external_subtitles": True,
                "subtitle_encoding": "utf-8"
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
                "min_bitrate_720p": self.min_bitrate_720p_spin.value(),
                "max_bitrate_720p": self.max_bitrate_720p_spin.value(),
                "min_bitrate_1080p": self.min_bitrate_1080p_spin.value(),
                "max_bitrate_1080p": self.max_bitrate_1080p_spin.value(),
                "min_bitrate_1440p": 3000,
                "max_bitrate_1440p": 6000,
                "min_bitrate_4k": self.min_bitrate_4k_spin.value(),
                "max_bitrate_4k": self.max_bitrate_4k_spin.value(),
                "preferred_codec": "hevc",
                "require_10bit": True
            },
            "ui": {
                "show_pretty_output": True,
                "auto_compare_filesizes": True
            }
        }


class SettingsDialog(QDialog):
    """Dialog for modifying settings."""
    
    def __init__(self, config: Dict[str, Any], parent=None):
        """
        Initialize settings dialog.
        
        Args:
            config: Current configuration dictionary.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(700)
        self.config = config.copy()
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout()
        
        # Tab widget for different settings categories
        tabs = QTabWidget()
        
        # General tab
        general_tab = QWidget()
        general_layout = QFormLayout()
        
        path_layout = QHBoxLayout()
        self.media_path_edit = QLineEdit(self.config.get("media_path", ""))
        path_browse_btn = QPushButton("Browse...")
        path_browse_btn.clicked.connect(self._browse_media_path)
        path_layout.addWidget(self.media_path_edit)
        path_layout.addWidget(path_browse_btn)
        general_layout.addRow("Media Path:", path_layout)
        
        self.scan_threads_spin = QSpinBox()
        self.scan_threads_spin.setRange(1, 16)
        self.scan_threads_spin.setValue(self.config.get("scan_threads", 8))
        self.scan_threads_spin.setToolTip("Number of parallel threads for scanning media files (1-16)")
        general_layout.addRow("Scan Threads:", self.scan_threads_spin)
        
        general_tab.setLayout(general_layout)
        tabs.addTab(general_tab, "General")
        
        # Quality Standards tab
        quality_tab = QWidget()
        quality_layout = QFormLayout()
        
        quality_config = self.config.get("quality_standards", {})
        
        # Header with help button
        qs_header_layout = QHBoxLayout()
        qs_header_label = QLabel("<b>Quality Standards (File Checking):</b>")
        qs_desc = QLabel("<p><i>These settings determine which files need re-encoding based on their current quality.</i></p>")
        qs_desc.setWordWrap(True)
        help_btn_qs = QPushButton("?")
        help_btn_qs.setMaximumWidth(30)
        help_btn_qs.clicked.connect(lambda: self._show_help("quality_standards"))
        help_btn_qs.setToolTip("Click for more information")
        qs_header_layout.addWidget(qs_header_label)
        qs_header_layout.addWidget(help_btn_qs)
        qs_header_layout.addStretch()
        quality_layout.addRow(qs_header_layout)
        quality_layout.addRow(qs_desc)
        
        quality_layout.addRow(QLabel(""), QLabel(""))
        quality_layout.addRow(QLabel("<b>Low-Res Bitrate Range:</b>"), QLabel(""))
        self.min_bitrate_low_res_spin = QSpinBox()
        self.min_bitrate_low_res_spin.setRange(300, 2000)
        self.min_bitrate_low_res_spin.setValue(quality_config.get("min_bitrate_low_res", 500))
        self.min_bitrate_low_res_spin.setSuffix(" kbps")
        quality_layout.addRow("Min Bitrate (Low-Res):", self.min_bitrate_low_res_spin)
        
        self.max_bitrate_low_res_spin = QSpinBox()
        self.max_bitrate_low_res_spin.setRange(300, 2000)
        self.max_bitrate_low_res_spin.setValue(quality_config.get("max_bitrate_low_res", 1000))
        self.max_bitrate_low_res_spin.setSuffix(" kbps")
        quality_layout.addRow("Max Bitrate (Low-Res):", self.max_bitrate_low_res_spin)
        
        quality_layout.addRow(QLabel("<b>720p Bitrate Range:</b>"), QLabel(""))
        self.min_bitrate_720p_spin = QSpinBox()
        self.min_bitrate_720p_spin.setRange(500, 5000)
        self.min_bitrate_720p_spin.setValue(quality_config.get("min_bitrate_720p", 1000))
        self.min_bitrate_720p_spin.setSuffix(" kbps")
        quality_layout.addRow("Min Bitrate (720p):", self.min_bitrate_720p_spin)
        
        self.max_bitrate_720p_spin = QSpinBox()
        self.max_bitrate_720p_spin.setRange(500, 5000)
        self.max_bitrate_720p_spin.setValue(quality_config.get("max_bitrate_720p", 2000))
        self.max_bitrate_720p_spin.setSuffix(" kbps")
        quality_layout.addRow("Max Bitrate (720p):", self.max_bitrate_720p_spin)
        
        quality_layout.addRow(QLabel("<b>1080p Bitrate Range:</b>"), QLabel(""))
        self.min_bitrate_1080p_spin = QSpinBox()
        self.min_bitrate_1080p_spin.setRange(1000, 10000)
        self.min_bitrate_1080p_spin.setValue(quality_config.get("min_bitrate_1080p", 1500))
        self.min_bitrate_1080p_spin.setSuffix(" kbps")
        quality_layout.addRow("Min Bitrate (1080p):", self.min_bitrate_1080p_spin)
        
        self.max_bitrate_1080p_spin = QSpinBox()
        self.max_bitrate_1080p_spin.setRange(1000, 10000)
        self.max_bitrate_1080p_spin.setValue(quality_config.get("max_bitrate_1080p", 4000))
        self.max_bitrate_1080p_spin.setSuffix(" kbps")
        quality_layout.addRow("Max Bitrate (1080p):", self.max_bitrate_1080p_spin)
        
        quality_layout.addRow(QLabel("<b>1440p Bitrate Range:</b>"), QLabel(""))
        self.min_bitrate_1440p_spin = QSpinBox()
        self.min_bitrate_1440p_spin.setRange(2000, 15000)
        self.min_bitrate_1440p_spin.setValue(quality_config.get("min_bitrate_1440p", 3000))
        self.min_bitrate_1440p_spin.setSuffix(" kbps")
        quality_layout.addRow("Min Bitrate (1440p):", self.min_bitrate_1440p_spin)
        
        self.max_bitrate_1440p_spin = QSpinBox()
        self.max_bitrate_1440p_spin.setRange(2000, 15000)
        self.max_bitrate_1440p_spin.setValue(quality_config.get("max_bitrate_1440p", 6000))
        self.max_bitrate_1440p_spin.setSuffix(" kbps")
        quality_layout.addRow("Max Bitrate (1440p):", self.max_bitrate_1440p_spin)
        
        quality_layout.addRow(QLabel("<b>4K Bitrate Range:</b>"), QLabel(""))
        self.min_bitrate_4k_spin = QSpinBox()
        self.min_bitrate_4k_spin.setRange(5000, 20000)
        self.min_bitrate_4k_spin.setValue(quality_config.get("min_bitrate_4k", 6000))
        self.min_bitrate_4k_spin.setSuffix(" kbps")
        quality_layout.addRow("Min Bitrate (4K):", self.min_bitrate_4k_spin)
        
        self.max_bitrate_4k_spin = QSpinBox()
        self.max_bitrate_4k_spin.setRange(5000, 20000)
        self.max_bitrate_4k_spin.setValue(quality_config.get("max_bitrate_4k", 10000))
        self.max_bitrate_4k_spin.setSuffix(" kbps")
        quality_layout.addRow("Max Bitrate (4K):", self.max_bitrate_4k_spin)
        
        quality_layout.addRow(QLabel(""), QLabel(""))
        
        # Bit depth preference
        self.bit_depth_combo = QComboBox()
        self.bit_depth_combo.addItem("Use Source Bit Depth", "source")
        self.bit_depth_combo.addItem("Force 10-bit", "force_10bit")
        self.bit_depth_combo.addItem("Force 8-bit", "force_8bit")
        bit_depth_pref = quality_config.get("bit_depth_preference", "source")
        index = self.bit_depth_combo.findData(bit_depth_pref)
        if index >= 0:
            self.bit_depth_combo.setCurrentIndex(index)
        quality_layout.addRow("Bit Depth Preference:", self.bit_depth_combo)
        
        quality_tab.setLayout(quality_layout)
        tabs.addTab(quality_tab, "Quality Standards")
        
        layout.addWidget(tabs)
        
        # Note about encoding settings
        note_label = QLabel(
            "<p><b>Note:</b> Encoding settings (codec, GPU, bitrate, etc.) are configured in the pre-encode dialog "
            "that appears when you start an encoding job.</p>"
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("QLabel { background-color: #ffffcc; color: black; padding: 8px; border: 1px solid #ccccaa; }")
        layout.addWidget(note_label)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def _show_help(self, topic: str):
        """Show help dialog for a topic."""
        help_text = HELP_TEXT.get(topic, "No help available for this topic.")
        QMessageBox.information(self, f"Help: {topic.replace('_', ' ').title()}", help_text)
    
    def _browse_media_path(self):
        """Browse for media path."""
        path = QFileDialog.getExistingDirectory(self, "Select Media Folder")
        if path:
            self.media_path_edit.setText(path)
    
    def get_config(self) -> Dict[str, Any]:
        """Get updated configuration."""
        self.config["media_path"] = self.media_path_edit.text()
        self.config["scan_threads"] = self.scan_threads_spin.value()
        
        # Update quality_standards section (used by scanner for compliance checking)
        self.config["quality_standards"]["min_bitrate_low_res"] = self.min_bitrate_low_res_spin.value()
        self.config["quality_standards"]["max_bitrate_low_res"] = self.max_bitrate_low_res_spin.value()
        self.config["quality_standards"]["min_bitrate_720p"] = self.min_bitrate_720p_spin.value()
        self.config["quality_standards"]["max_bitrate_720p"] = self.max_bitrate_720p_spin.value()
        self.config["quality_standards"]["min_bitrate_1080p"] = self.min_bitrate_1080p_spin.value()
        self.config["quality_standards"]["max_bitrate_1080p"] = self.max_bitrate_1080p_spin.value()
        self.config["quality_standards"]["min_bitrate_1440p"] = self.min_bitrate_1440p_spin.value()
        self.config["quality_standards"]["max_bitrate_1440p"] = self.max_bitrate_1440p_spin.value()
        self.config["quality_standards"]["min_bitrate_4k"] = self.min_bitrate_4k_spin.value()
        self.config["quality_standards"]["max_bitrate_4k"] = self.max_bitrate_4k_spin.value()
        self.config["quality_standards"]["bit_depth_preference"] = self.bit_depth_combo.currentData()
        
        return self.config


class ScanThread(QThread):
    """Thread for scanning media files."""
    
    progress = pyqtSignal(int, int, str)  # current, total, filename
    scan_complete = pyqtSignal(list)  # List of MediaInfo
    
    def __init__(self, directory: Path, scanner: MediaScanner, config: Dict[str, Any]):
        """
        Initialize scan thread.
        
        Args:
            directory: Directory to scan.
            scanner: MediaScanner instance.
            config: Configuration dictionary.
        """
        super().__init__()
        self.directory = directory
        self.scanner = scanner
        self.config = config
        self.should_stop = False
    
    def stop(self):
        """Request the scan to stop."""
        self.should_stop = True
    
    def run(self):
        """Run the scan with parallel file analysis."""
        import time
        import os
        
        overall_start = time.time()
        
        # First, find all media files
        scan_start = time.time()
        media_files = self.scanner.scan_directory(self.directory)
        scan_time = time.time() - scan_start
        
        print(f"[TIMING] File discovery completed in {scan_time:.2f}s")
        
        total = len(media_files)
        if total == 0:
            self.scan_complete.emit(media_files)
            return
        
        # Determine optimal worker count (CPU cores, but cap for I/O bound tasks)
        scan_threads = self.config.get("scan_threads", 8)
        max_workers = min(os.cpu_count() or 4, scan_threads, total)
        print(f"[TIMING] Using {max_workers} parallel workers for analysis")
        
        analyze_start = time.time()
        completed_count = 0
        
        # Use ThreadPoolExecutor for parallel ffprobe calls
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all analysis tasks - each media_info is unique
            # The dictionary ensures no duplicates as each future maps to one media_info
            future_to_media = {}
            for media_info in media_files:
                # Skip if already analyzed (safety check)
                if media_info.status not in [MediaStatus.UNKNOWN, MediaStatus.SCANNING]:
                    completed_count += 1
                    continue
                
                # Submit for analysis
                future = executor.submit(self.scanner.analyze_media, media_info)
                future_to_media[future] = media_info
            
            # Process results as they complete
            for future in as_completed(future_to_media):
                # Check if stop was requested
                if self.should_stop:
                    # Cancel remaining futures
                    for f in future_to_media:
                        f.cancel()
                    print("[INFO] Scan cancelled by user")
                    break
                
                media_info = future_to_media[future]
                try:
                    # Get the result (updates media_info in place)
                    future.result()
                    completed_count += 1
                    self.progress.emit(completed_count, total, media_info.filename)
                except Exception as e:
                    print(f"[ERROR] Failed to analyze {media_info.filename}: {e}")
                    media_info.status = MediaStatus.ERROR
                    media_info.issues.append(f"Analysis error: {str(e)}")
                    completed_count += 1
        
        analyze_time = time.time() - analyze_start
        overall_time = time.time() - overall_start
                
        print(f"\n[TIMING] === SCAN SUMMARY ===")
        print(f"[TIMING] Total files: {total}")
        print(f"[TIMING] File discovery: {scan_time:.2f}s")
        if analyze_time > 0: print(f"[TIMING] Analysis phase: {analyze_time:.2f}s ({max_workers} workers)")
        if total > 0: print(f"[TIMING] Average per file: {round(analyze_time/total,3)}s")
        print(f"[TIMING] Total scan time: {overall_time:.2f}s\n")
        
        # Save cache after scan completes
        self.scanner._save_cache()
        
        self.scan_complete.emit(media_files)


class EncodingCompleteDialog(QDialog):
    """Dialog shown when encoding completes with comparison report and cleanup option."""
    
    def __init__(self, comparison_text: str, successful: int, failed: int, jobs: List, parent=None):
        """
        Initialize the encoding complete dialog.
        
        Args:
            comparison_text: Comparison report text.
            successful: Number of successful encodings.
            failed: Number of failed encodings.
            jobs: List of encoding jobs.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.jobs = jobs
        self.cleanup_performed = False  # Track if cleanup was executed
        self.setWindowTitle("Encoding Complete")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        self._setup_ui(comparison_text, successful, failed)
    
    def _setup_ui(self, comparison_text: str, successful: int, failed: int):
        """Set up the UI components."""
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel(f"<h2>Encoding Complete!</h2>")
        layout.addWidget(title_label)
        
        # Summary
        summary_label = QLabel(f"<p><b>Successful:</b> {successful} | <b>Failed:</b> {failed}</p>")
        layout.addWidget(summary_label)
        
        # Comparison report in text area
        report_area = QTextEdit()
        report_area.setReadOnly(True)
        report_area.setPlainText(comparison_text)
        report_area.setFont(QFont("Courier", 10))
        layout.addWidget(report_area)
        
        # Cleanup section
        if successful > 0:
            cleanup_group = QGroupBox("Cleanup Options")
            cleanup_layout = QVBoxLayout()
            
            cleanup_desc = QLabel(
                "<p><b>Warning:</b> Cleanup will permanently delete original files and move encoded files to replace them.</p>"
                "<p>This action cannot be undone!</p>"
            )
            cleanup_desc.setWordWrap(True)
            cleanup_layout.addWidget(cleanup_desc)
            
            self.cleanup_checkbox = QCheckBox("I understand and want to proceed with cleanup")
            cleanup_layout.addWidget(self.cleanup_checkbox)
            
            cleanup_group.setLayout(cleanup_layout)
            layout.addWidget(cleanup_group)
        else:
            self.cleanup_checkbox = None
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        if successful > 0:
            self.cleanup_btn = QPushButton("Cleanup & Replace")
            self.cleanup_btn.setEnabled(False)
            self.cleanup_btn.clicked.connect(self._perform_cleanup)
            self.cleanup_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; }")
            if self.cleanup_checkbox:
                self.cleanup_checkbox.stateChanged.connect(
                    lambda: self.cleanup_btn.setEnabled(self.cleanup_checkbox.isChecked())
                )
            button_layout.addWidget(self.cleanup_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _perform_cleanup(self):
        """Perform cleanup: delete originals and move encoded files."""
        # Final confirmation
        reply = QMessageBox.question(
            self, "Final Confirmation",
            f"This will:\n\n"
            f"1. Delete {sum(1 for j in self.jobs if j.status == 'complete')} original files\n"
            f"2. Move encoded files to replace them\n\n"
            f"Are you absolutely sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        successful_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []
        
        for job in self.jobs:
            if job.status != "complete" or not job.output_path.exists():
                continue
            
            try:
                original_path = job.media_info.path
                encoded_path = job.output_path
                
                # Check file sizes - if encoded is larger, keep original and delete encoded
                if original_path.exists() and encoded_path.exists():
                    original_size = original_path.stat().st_size
                    encoded_size = encoded_path.stat().st_size
                    
                    if encoded_size >= original_size:
                        # Encoding made file larger - keep original, delete encoded
                        encoded_path.unlink()
                        skipped_count += 1
                        print(f"[CLEANUP] Kept original {original_path.name} (encoded was larger: {encoded_size:,} vs {original_size:,} bytes)")
                        continue
                
                # Determine final path (same location as original, with encoded name)
                final_path = original_path.parent / encoded_path.name
                
                # Delete original file
                if original_path.exists():
                    original_path.unlink()
                
                # Move encoded file to final location
                encoded_path.rename(final_path)
                
                successful_count += 1
                print(f"[CLEANUP] Replaced {original_path.name} with {encoded_path.name}")
                
            except Exception as e:
                failed_count += 1
                error_msg = f"{job.media_info.filename}: {str(e)}"
                errors.append(error_msg)
                print(f"[ERROR] Cleanup failed for {job.media_info.filename}: {e}")
        
        # Show results
        if failed_count == 0:
            msg = f"Successfully cleaned up {successful_count} file(s)!\n\n"
            if skipped_count > 0:
                msg += f"Kept {skipped_count} original file(s) where encoding increased size.\n\n"
            msg += "Encoded files have replaced the originals."
            QMessageBox.information(
                self, "Cleanup Complete", msg
            )
            self.cleanup_performed = True  # Mark cleanup as performed
            self.accept()
        else:
            error_text = "\\n".join(errors[:10])  # Show first 10 errors
            if len(errors) > 10:
                error_text += f"\\n... and {len(errors) - 10} more errors"
            
            QMessageBox.warning(
                self, "Cleanup Partially Failed",
                f"Successful: {successful_count}\\nFailed: {failed_count}\\n\\n"
                f"Errors:\\n{error_text}"
            )




class PreEncodeSettingsDialog(QDialog):
    """Dialog shown before encoding starts to confirm and adjust settings."""
    
    def __init__(self, config: Dict[str, Any], files: List[MediaInfo], parent=None):
        """
        Initialize the pre-encode settings dialog.
        
        Args:
            config: Current configuration dictionary.
            files: List of MediaInfo files to be encoded.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.config = config.copy()
        self.files = files
        self.file_count = len(files)
        
        # Detect resolutions present in files
        self.detected_resolutions = self._detect_resolutions()
        
        self.setWindowTitle("Encoding Settings")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self._setup_ui()
    
    def _detect_resolutions(self) -> set:
        """
        Detect which resolutions are present in the files to be encoded.
        Uses the same logic as compliance detection in MediaScanner._check_compliance.
        
        Returns:
            Set of resolution identifiers: 'low_res', '720p', '1080p', '1440p', '4k'
        """
        resolutions = set()
        for media_info in self.files:
            height = media_info.height
            width = media_info.width
            max_dimension = max(height, width)

            if (max_dimension >= 1024 and max_dimension < 1900) or ((height >= 700 and height < 1000) or (width >= 1024 and width < 1900)):
                # Flexible 720p range
                resolutions.add("720p")
            elif (max_dimension >= 1900 and max_dimension < 2560) or ((height >= 1000 and height < 1440) or (width >= 1900 and width < 2560)):
                # Flexible 1080p range: handles 1076, 1040, 800 heights with 1920+ widths
                resolutions.add("1080p")
            elif (max_dimension >= 2560 and max_dimension < 3840) or ((height >= 1440 and height < 2160) or (width >= 2560 and width < 3840)):
                resolutions.add("1440p")
            elif max_dimension >= 3840 or (height >= 2160 or width >= 3840):
                resolutions.add("4k")
            else: resolutions.add("low_res")
            
        return resolutions
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel(f"<h2>Confirm Encoding Settings</h2>")
        layout.addWidget(title_label)
        
        # File count
        count_label = QLabel(f"<p>Ready to encode <b>{self.file_count}</b> file(s)</p>")
        layout.addWidget(count_label)
        
        # Create scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Encoding Settings Group
        encoding_group = QGroupBox("Video Encoding Settings")
        encoding_layout = QFormLayout()
        
        enc = self.config.get("encoding", {})
        
        # Codec selection
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["x265 (HEVC)", "AV1"])
        self.codec_combo.setCurrentText("x265 (HEVC)" if enc.get("codec_type", "x265") == "x265" else "AV1")
        encoding_layout.addRow("Codec:", self.codec_combo)
        
        # GPU toggle
        self.gpu_check = QCheckBox("Use GPU acceleration (NVENC)")
        self.gpu_check.setChecked(enc.get("use_gpu", False))
        encoding_layout.addRow("", self.gpu_check)
        
        # Preset
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.preset_combo.setCurrentText(enc.get("preset", "veryfast"))
        encoding_layout.addRow("Preset:", self.preset_combo)
        
        # Animation tuning
        self.animation_check = QCheckBox("Tune for animation")
        self.animation_check.setChecked(enc.get("tune_animation", False))
        encoding_layout.addRow("", self.animation_check)
        
        # Constant Quality (CQ)
        self.cq_spin = QSpinBox()
        self.cq_spin.setRange(0, 51)
        self.cq_spin.setValue(enc.get("cq", 22))
        self.cq_spin.setToolTip("Lower = higher quality. Recommended: 18-25 for 1080p. Disabled when using target bitrate.")
        self.cq_spin.setEnabled(not enc.get("use_target_bitrate", False))
        encoding_layout.addRow("Constant Quality (CQ):", self.cq_spin)
        
        # Thread count (CPU only)
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 32)
        self.thread_spin.setValue(enc.get("thread_count", 4))
        self.thread_spin.setEnabled(not enc.get("use_gpu", False))
        encoding_layout.addRow("Thread Count:", self.thread_spin)
        
        # Level
        self.level_combo = QComboBox()
        self.level_combo.addItems(["Auto (ignore)", "3.0", "3.1", "4.0", "4.1", "5.0", "5.1", "5.2", "6.0", "6.1", "6.2"])
        current_level = enc.get("level", "4.1")
        if current_level and current_level.lower() != "auto":
            self.level_combo.setCurrentText(current_level)
        else:
            self.level_combo.setCurrentText("Auto (ignore)")
        self.level_combo.setToolTip("Encoding level. Use 5.1+ for 4K content. 4.1 is safe for most 1080p content. Auto skips level parameter.")
        encoding_layout.addRow("Level:", self.level_combo)
        
        # Bit depth preference
        self.bit_depth_combo = QComboBox()
        self.bit_depth_combo.addItems(["Match source", "Force 8-bit", "Force 10-bit"])
        bit_depth_pref = enc.get("bit_depth_preference", "source")
        if bit_depth_pref == "force_8bit":
            self.bit_depth_combo.setCurrentText("Force 8-bit")
        elif bit_depth_pref == "force_10bit":
            self.bit_depth_combo.setCurrentText("Force 10-bit")
        else:
            self.bit_depth_combo.setCurrentText("Match source")
        self.bit_depth_combo.setToolTip("10-bit provides better gradients and less banding, but larger files.")
        encoding_layout.addRow("Bit Depth:", self.bit_depth_combo)
        
        # Skip options
        self.skip_video_check = QCheckBox("Skip video encoding (copy stream)")
        self.skip_video_check.setChecked(enc.get("skip_video_encoding", False))
        self.skip_video_check.setToolTip("Copy video stream without re-encoding (for audio/subtitle changes only)")
        encoding_layout.addRow("", self.skip_video_check)
        
        self.skip_audio_check = QCheckBox("Skip audio encoding (copy stream)")
        self.skip_audio_check.setChecked(enc.get("skip_audio_encoding", False))
        encoding_layout.addRow("", self.skip_audio_check)
        
        self.skip_subtitle_check = QCheckBox("Skip subtitle encoding (copy stream)")
        self.skip_subtitle_check.setChecked(enc.get("skip_subtitle_encoding", False))
        encoding_layout.addRow("", self.skip_subtitle_check)
        
        self.skip_cover_art_check = QCheckBox("Skip cover art / attached pictures")
        self.skip_cover_art_check.setChecked(enc.get("skip_cover_art", True))
        self.skip_cover_art_check.setToolTip("Only encode the first video stream. Prevents errors from embedded cover images.")
        encoding_layout.addRow("", self.skip_cover_art_check)
        
        # Connect GPU checkbox to enable/disable thread count
        self.gpu_check.stateChanged.connect(lambda: self.thread_spin.setEnabled(not self.gpu_check.isChecked()))
        
        encoding_group.setLayout(encoding_layout)
        scroll_layout.addWidget(encoding_group)
        
        # Bitrate Settings Group
        bitrate_group = QGroupBox("Bitrate Settings")
        bitrate_main_layout = QVBoxLayout()
        
        # Use bitrate limits checkbox
        self.use_limits_check = QCheckBox("Use min/max bitrate limits")
        self.use_limits_check.setChecked(enc.get("use_bitrate_limits", False))
        bitrate_main_layout.addWidget(self.use_limits_check)
        
        # Use target bitrate checkbox
        self.use_target_check = QCheckBox("Use target bitrate (replaces CQ mode)")
        self.use_target_check.setChecked(enc.get("use_target_bitrate", False))
        self.use_target_check.setToolTip("Target bitrate provides predictable file sizes. Disables CQ mode when enabled.")
        bitrate_main_layout.addWidget(self.use_target_check)
        
        # Connect checkboxes to enable/disable bitrate controls
        self.use_limits_check.stateChanged.connect(self._toggle_bitrate_controls)
        self.use_target_check.stateChanged.connect(self._toggle_bitrate_controls)
        
        # Resolution-specific bitrate settings (only show detected resolutions)
        self.resolution_groups = {}
        self.bitrate_spinboxes = {}
        
        # Get quality_standards to populate min/max defaults (these are the library standards)
        qs = self.config.get("quality_standards", {})
        
        # Low resolution settings (below 720p)
        if 'low_res' in self.detected_resolutions:
            group_low = self._create_resolution_bitrate_group(
                "Below 720p",
                qs.get("min_bitrate_low_res", 500),
                qs.get("max_bitrate_low_res", 1000),
                enc.get("target_bitrate_low_res", 800),
                200, 2000,
                storage_key="low_res"
            )
            bitrate_main_layout.addWidget(group_low)
            self.resolution_groups['low_res'] = group_low
        
        # 720p settings
        if '720p' in self.detected_resolutions:
            group_720p = self._create_resolution_bitrate_group(
                "720p", 
                qs.get("min_bitrate_720p", 1000),
                qs.get("max_bitrate_720p", 2000),
                enc.get("target_bitrate_720p", 1500),
                500, 5000,
                storage_key="720p"
            )
            bitrate_main_layout.addWidget(group_720p)
            self.resolution_groups['720p'] = group_720p
        
        # 1080p settings
        if '1080p' in self.detected_resolutions:
            group_1080p = self._create_resolution_bitrate_group(
                "1080p",
                qs.get("min_bitrate_1080p", 2000),
                qs.get("max_bitrate_1080p", 4000),
                enc.get("target_bitrate_1080p", 3000),
                1000, 10000,
                storage_key="1080p"
            )
            bitrate_main_layout.addWidget(group_1080p)
            self.resolution_groups['1080p'] = group_1080p
        
        # 1440p settings
        if '1440p' in self.detected_resolutions:
            group_1440p = self._create_resolution_bitrate_group(
                "1440p",
                qs.get("min_bitrate_1440p", 4000),
                qs.get("max_bitrate_1440p", 6000),
                enc.get("target_bitrate_1440p", 5000),
                2000, 15000,
                storage_key="1440p"
            )
            bitrate_main_layout.addWidget(group_1440p)
            self.resolution_groups['1440p'] = group_1440p
        
        # 4K settings
        if '4k' in self.detected_resolutions:
            group_4k = self._create_resolution_bitrate_group(
                "4K",
                qs.get("min_bitrate_4k", 6000),
                qs.get("max_bitrate_4k", 10000),
                enc.get("target_bitrate_4k", 8000),
                4000, 30000,
                storage_key="4k"
            )
            bitrate_main_layout.addWidget(group_4k)
            self.resolution_groups['4k'] = group_4k
        
        bitrate_group.setLayout(bitrate_main_layout)
        scroll_layout.addWidget(bitrate_group)
        
        # Language Filtering Group
        lang_group = QGroupBox("Language Filtering")
        lang_layout = QFormLayout()
        
        audio_settings = self.config.get("audio", {})
        subtitle_settings = self.config.get("subtitles", {})
        
        # Audio language filtering
        self.audio_filter_check = QCheckBox("Filter audio tracks by language")
        self.audio_filter_check.setChecked(audio_settings.get("language_filter_enabled", False))
        lang_layout.addRow("", self.audio_filter_check)
        
        self.audio_lang_edit = QLineEdit()
        self.audio_lang_edit.setText(", ".join(audio_settings.get("allowed_languages", ["eng"])))
        self.audio_lang_edit.setPlaceholderText("e.g., eng, jpn, spa")
        self.audio_lang_edit.setEnabled(self.audio_filter_check.isChecked())
        lang_layout.addRow("Audio Languages:", self.audio_lang_edit)
        
        # Subtitle language filtering
        self.subtitle_filter_check = QCheckBox("Filter subtitle tracks by language")
        self.subtitle_filter_check.setChecked(subtitle_settings.get("language_filter_enabled", False))
        lang_layout.addRow("", self.subtitle_filter_check)
        
        self.subtitle_lang_edit = QLineEdit()
        self.subtitle_lang_edit.setText(", ".join(subtitle_settings.get("allowed_languages", ["eng"])))
        self.subtitle_lang_edit.setPlaceholderText("e.g., eng, jpn, spa")
        self.subtitle_lang_edit.setEnabled(self.subtitle_filter_check.isChecked())
        lang_layout.addRow("Subtitle Languages:", self.subtitle_lang_edit)
        
        # Connect checkboxes to enable/disable language inputs
        self.audio_filter_check.stateChanged.connect(lambda: self.audio_lang_edit.setEnabled(self.audio_filter_check.isChecked()))
        self.subtitle_filter_check.stateChanged.connect(lambda: self.subtitle_lang_edit.setEnabled(self.subtitle_filter_check.isChecked()))
        
        lang_group.setLayout(lang_layout)
        scroll_layout.addWidget(lang_group)
        
        # Other Options Group
        other_group = QGroupBox("Other Options")
        other_layout = QVBoxLayout()
        
        self.ignore_extras_check = QCheckBox("Skip extras/bonus features")
        self.ignore_extras_check.setChecked(enc.get("ignore_extras", True))
        other_layout.addWidget(self.ignore_extras_check)
        
        other_group.setLayout(other_layout)
        scroll_layout.addWidget(other_group)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        start_btn = QPushButton("Start Encoding")
        start_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; padding: 8px 16px; }")
        start_btn.clicked.connect(self.accept)
        button_layout.addWidget(start_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _create_resolution_bitrate_group(self, resolution: str, min_default: int, max_default: int, 
                                         target_default: int, range_min: int, range_max: int,
                                         storage_key: str = None) -> QGroupBox:
        """
        Create a bitrate settings group for a specific resolution.
        
        Args:
            resolution: Resolution display name (e.g., "720p", "1080p", "Below 720p")
            min_default: Default minimum bitrate
            max_default: Default maximum bitrate
            target_default: Default target bitrate
            range_min: Minimum allowed value for spinboxes
            range_max: Maximum allowed value for spinboxes
            storage_key: Key for storing spinbox references (defaults to resolution.lower())
            
        Returns:
            QGroupBox containing the bitrate controls
        """
        group = QGroupBox(f"{resolution} Bitrate Settings")
        layout = QFormLayout()
        
        # Determine storage key
        if storage_key is None:
            storage_key = resolution.lower()
        
        # Minimum bitrate
        min_spin = QSpinBox()
        min_spin.setRange(range_min, range_max)
        min_spin.setValue(min_default)
        min_spin.setSuffix(" kbps")
        min_spin.setEnabled(self.use_limits_check.isChecked())
        layout.addRow("Minimum:", min_spin)
        
        # Maximum bitrate
        max_spin = QSpinBox()
        max_spin.setRange(range_min, range_max)
        max_spin.setValue(max_default)
        max_spin.setSuffix(" kbps")
        max_spin.setEnabled(self.use_limits_check.isChecked())
        layout.addRow("Maximum:", max_spin)
        
        # Target bitrate
        target_spin = QSpinBox()
        target_spin.setRange(range_min, range_max)
        target_spin.setValue(target_default)
        target_spin.setSuffix(" kbps")
        target_spin.setEnabled(self.use_target_check.isChecked())
        layout.addRow("Target:", target_spin)
        
        group.setLayout(layout)
        
        # Store references to spinboxes using provided key
        self.bitrate_spinboxes[storage_key] = {
            'min': min_spin,
            'max': max_spin,
            'target': target_spin
        }
        
        return group
    
    def _toggle_bitrate_controls(self):
        """Toggle bitrate spinboxes based on checkboxes."""
        limits_enabled = self.use_limits_check.isChecked()
        target_enabled = self.use_target_check.isChecked()
        
        # Target bitrate and CQ are mutually exclusive
        self.cq_spin.setEnabled(not target_enabled)
        
        for res_spinboxes in self.bitrate_spinboxes.values():
            res_spinboxes['min'].setEnabled(limits_enabled)
            res_spinboxes['max'].setEnabled(limits_enabled)
            res_spinboxes['target'].setEnabled(target_enabled)
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the updated configuration from the dialog.
        
        Returns:
            Updated configuration dictionary.
        """
        # Update encoding settings
        enc = self.config.get("encoding", {})
        enc["codec_type"] = "x265" if "x265" in self.codec_combo.currentText() else "av1"
        enc["use_gpu"] = self.gpu_check.isChecked()
        enc["preset"] = self.preset_combo.currentText()
        enc["tune_animation"] = self.animation_check.isChecked()
        enc["cq"] = self.cq_spin.value()
        enc["thread_count"] = self.thread_spin.value()
        
        # Level - save as 'auto' if Auto is selected
        level_text = self.level_combo.currentText()
        if "Auto" in level_text or "ignore" in level_text:
            enc["level"] = "auto"
        else:
            enc["level"] = level_text
        
        # Bit depth preference
        bit_depth_text = self.bit_depth_combo.currentText()
        if bit_depth_text == "Force 8-bit":
            enc["bit_depth_preference"] = "force_8bit"
        elif bit_depth_text == "Force 10-bit":
            enc["bit_depth_preference"] = "force_10bit"
        else:
            enc["bit_depth_preference"] = "source"
        
        # Skip options
        enc["skip_video_encoding"] = self.skip_video_check.isChecked()
        enc["skip_audio_encoding"] = self.skip_audio_check.isChecked()
        enc["skip_subtitle_encoding"] = self.skip_subtitle_check.isChecked()
        enc["skip_cover_art"] = self.skip_cover_art_check.isChecked()
        
        enc["use_bitrate_limits"] = self.use_limits_check.isChecked()
        enc["use_target_bitrate"] = self.use_target_check.isChecked()
        enc["ignore_extras"] = self.ignore_extras_check.isChecked()
        
        # Collect bitrate values from resolution-specific spinboxes
        for res_key, spinboxes in self.bitrate_spinboxes.items():
            enc[f"encoding_bitrate_min_{res_key}"] = spinboxes['min'].value()
            enc[f"encoding_bitrate_max_{res_key}"] = spinboxes['max'].value()
            enc[f"target_bitrate_{res_key}"] = spinboxes['target'].value()
        self.config["encoding"] = enc
        
        # Update language settings
        audio_settings = self.config.get("audio", {})
        audio_settings["language_filter_enabled"] = self.audio_filter_check.isChecked()
        audio_settings["allowed_languages"] = [lang.strip() for lang in self.audio_lang_edit.text().split(",") if lang.strip()]
        self.config["audio"] = audio_settings
        
        subtitle_settings = self.config.get("subtitles", {})
        subtitle_settings["language_filter_enabled"] = self.subtitle_filter_check.isChecked()
        subtitle_settings["allowed_languages"] = [lang.strip() for lang in self.subtitle_lang_edit.text().split(",") if lang.strip()]
        self.config["subtitles"] = subtitle_settings
        
        return self.config


class EncodingLogDialog(QDialog):
    """Real-time encoding log dialog showing file operations and statistics."""
    
    stop_requested = pyqtSignal()  # Signal emitted when stop button is clicked
    
    def __init__(self, parent=None, total_files: int = 1, jobs=None):
        """Initialize the encoding log dialog.
        
        Args:
            parent: Parent widget.
            total_files: Total number of files to encode (for progress display).
            jobs: List of encoding jobs (for batch ETA calculation).
        """
        super().__init__(parent)
        self.setWindowTitle("Encoding Log")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        
        self.total_original_size = 0
        self.total_encoded_size = 0
        self.file_stats = []
        self.total_files = total_files
        self.current_file_index = 0
        self.current_file_progress = 0.0
        self.current_file_eta = "--:--"
        
        # Batch ETA tracking
        if jobs and len(jobs) > 1:
            self.total_batch_frames = sum(job.media_info.duration * job.media_info.fps for job in jobs if job.media_info.duration and job.media_info.fps)
            self.jobs = jobs
        else:
            self.total_batch_frames = 0
            self.jobs = []
        self.completed_frames = 0
        self.current_job_total_frames = 0
        self.batch_eta = "--:--"
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout()
        
        # Title and progress section
        header_layout = QVBoxLayout()
        title_label = QLabel("<h2>Encoding Operations Log</h2>")
        header_layout.addWidget(title_label)
        
        layout.addLayout(header_layout)
        
        # Log text area (read-only console)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
            }
        """)
        layout.addWidget(self.log_text)

        # File progress label (with ETA)
        self.file_progress_label = QLabel("Ready to start...")
        self.file_progress_label.setFont(QFont("Courier", 10))
        layout.addWidget(self.file_progress_label)
        
        # Statistics area
        stats_group = QGroupBox("Overall Statistics")
        stats_layout = QVBoxLayout()
        
        self.stats_label = QLabel("No files processed yet")
        self.stats_label.setFont(QFont("Courier", 10))
        stats_layout.addWidget(self.stats_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; }")
        button_layout.addWidget(self.stop_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def log_message(self, message: str, color: str = "#d4d4d4"):
        """
        Add a message to the log.
        
        Args:
            message: Message to log.
            color: HTML color code for the message.
        """
        self.log_text.append(f'<span style="color: {color};">{message}</span>')
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def log_file_start(self, source_path: str, dest_path: str):
        """
        Log the start of a file encoding operation.
        
        Args:
            source_path: Source file path.
            dest_path: Destination file path.
        """
        self.current_file_index += 1
        self.current_file_progress = 0.0
        self.current_file_eta = "--:--"
        
        # Set current job total frames for batch ETA
        if self.jobs and self.current_file_index <= len(self.jobs):
            job = self.jobs[self.current_file_index - 1]
            if job.media_info.duration and job.media_info.fps:
                self.current_job_total_frames = job.media_info.duration * job.media_info.fps

        self.log_message("=" * 80, "#4a9eff")
        self.log_message(f"File Start: {source_path}", "#4a9eff")
        self.log_message(f"Destination: {dest_path}", "#4a9eff")
        self.log_message("=" * 80, "#4a9eff")
    
    def log_command(self, command: str):
        """
        Log the FFmpeg command being executed.
        
        Args:
            command: FFmpeg command string.
        """
        self.log_message(f"Command: {command}", "#ffcc00")
    
    def update_file_progress(self, progress: float, encoding_fps: float, eta: str, filename: str = ""):
        """
        Update the current file's progress display (not logged to console).
        
        Args:
            progress: Progress percentage.
            encoding_fps: Current encoding speed in frames per second.
            eta: Estimated time remaining for current file.
            filename: Current filename (if available).
        """
        self.current_file_progress = progress
        self.current_file_eta = eta
        
        # Update file progress label
        if filename:
            display_name = Path(filename).name
            # Truncate if longer than 60 characters
            if len(display_name) > 60:
                display_name = display_name[:57] + "..."
        else:
            display_name = "File"
        
        # Build progress text with file info
        progress_text = f"Encoding: {display_name} | {progress:.1f}% | FPS: {encoding_fps:.0f} | ETA: {eta}"
        
        # Calculate and append batch ETA if multi-file encode
        if self.total_files > 1 and encoding_fps > 0 and self.total_batch_frames > 0:
            # Calculate frames completed in current file
            current_file_frames = (progress / 100.0) * self.current_job_total_frames
            # Total frames completed so far
            total_completed = self.completed_frames + current_file_frames
            # Remaining frames in batch
            remaining_frames = max(0, self.total_batch_frames - total_completed)
            # Calculate ETA
            remaining_seconds = remaining_frames / encoding_fps
            if remaining_seconds < 3600:  # Less than 1 hour
                eta_minutes = int(remaining_seconds // 60)
                eta_seconds = int(remaining_seconds % 60)
                self.batch_eta = f"{eta_minutes:02d}:{eta_seconds:02d}"
            else:  # 1 hour or more
                eta_hours = int(remaining_seconds // 3600)
                eta_minutes = int((remaining_seconds % 3600) // 60)
                self.batch_eta = f"{eta_hours}h {eta_minutes:02d}m"
            
            progress_text += f" | Batch ETA: {self.batch_eta} ({self.current_file_index}/{self.total_files})"
        
        self.file_progress_label.setText(progress_text)
    
    def log_file_complete(self, source_path: str, dest_path: str, original_size: int, encoded_size: int, success: bool = True):
        """
        Log file encoding completion with size comparison.
        
        Args:
            source_path: Source file path.
            dest_path: Destination file path.
            original_size: Original file size in bytes.
            encoded_size: Encoded file size in bytes.
            success: Whether encoding was successful.
        """
        # Update completed frames for batch ETA
        self.completed_frames += self.current_job_total_frames
        
        if not success:
            self.log_message(f"✗ FAILED: {source_path}", "#ff4444")
            return
        
        # Calculate sizes in appropriate units
        orig_mb = original_size / (1024 * 1024)
        enc_mb = encoded_size / (1024 * 1024)
        
        orig_size_str, orig_unit = self._format_size(original_size)
        enc_size_str, enc_unit = self._format_size(encoded_size)
        
        # Calculate reduction percentage
        if original_size > 0:
            reduction = ((original_size - encoded_size) / original_size) * 100
        else:
            reduction = 0.0
        
        # Choose color based on reduction
        if reduction > 0:
            color = "#4caf50"  # Green for reduction (file got smaller)
            sign = "-"
        elif reduction < 0:
            color = "#ff9800"  # Orange for growth (file got bigger)
            sign = "+"
            reduction = abs(reduction)
        else:
            color = "#888888"  # Gray for no change
            sign = ""
        
        self.log_message(f"✓ COMPLETE: {source_path}", "#4caf50")
        self.log_message(
            f"File Size - Original: {orig_size_str:.2f} {orig_unit}, "
            f"Encoded: {enc_size_str:.2f} {enc_unit}, "
            f"Change: {sign}{reduction:.2f}%",
            color
        )
        
        # Update totals
        self.total_original_size += original_size
        self.total_encoded_size += encoded_size
        self.file_stats.append({
            'original': original_size,
            'encoded': encoded_size,
            'reduction': reduction if encoded_size < original_size else -reduction
        })
        
        self._update_statistics()
    
    def log_error(self, message: str):
        """
        Log an error message.
        
        Args:
            message: Error message.
        """
        self.log_message(f"ERROR: {message}", "#ff4444")
    
    def _format_size(self, size_bytes: int) -> tuple:
        """
        Format size in appropriate unit (MB or GB).
        
        Args:
            size_bytes: Size in bytes.
            
        Returns:
            Tuple of (size_value, unit_string).
        """
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > 974:  # 95% of 1 GB
            return (size_mb / 1024, "GB")
        else:
            return (size_mb, "MB")
    
    def _update_statistics(self):
        """Update the overall statistics display."""
        if not self.file_stats:
            self.stats_label.setText("No files processed yet")
            return
        
        num_files = len(self.file_stats)
        
        # Format total sizes
        orig_size, orig_unit = self._format_size(self.total_original_size)
        enc_size, enc_unit = self._format_size(self.total_encoded_size)
        
        # Calculate overall reduction
        if self.total_original_size > 0:
            overall_reduction = ((self.total_original_size - self.total_encoded_size) / self.total_original_size) * 100
        else:
            overall_reduction = 0.0
        
        # Calculate average reduction
        avg_reduction = sum(s['reduction'] for s in self.file_stats) / num_files
        
        overall_sign = "-" if overall_reduction > 0 else ("+" if overall_reduction < 0 else "")
        avg_sign = "-" if avg_reduction > 0 else ("+" if avg_reduction < 0 else "")
        
        # Use absolute values for display when showing + (growth)
        overall_display = abs(overall_reduction) if overall_reduction < 0 else overall_reduction
        avg_display = abs(avg_reduction) if avg_reduction < 0 else avg_reduction
        
        stats_text = f"""<b>Files Processed:</b> {num_files} | 
<b>Total Original:</b> {orig_size:.2f} {orig_unit} | <b>Encoded:</b> {enc_size:.2f} {enc_unit}<br>
<b>Overall Space Change:</b> {overall_sign}{overall_display:.2f}% | 
<b>Average per File:</b> {avg_sign}{avg_display:.2f}%"""
        
        self.stats_label.setText(stats_text)
        self.stats_label.setWordWrap(True)
    
    def _on_stop_clicked(self):
        """Handle stop button click."""
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("Stopping...")
        self.stop_requested.emit()
        self.log_message("\nStop requested - cancelling encoding...", "#ff9800")
    
    def encoding_complete(self):
        """Mark encoding as complete, disable stop button."""
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("Encoding Complete")
        self.file_progress_label.setText("Encoding complete!")


class MetadataDialog(QDialog):
    """Dialog for adding metadata (cover art and subtitles) to video files."""
    
    def __init__(self, parent=None):
        """Initialize the metadata dialog."""
        super().__init__(parent)
        self.setWindowTitle("Add Metadata to Videos")
        self.setMinimumWidth(600)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout()
        
        # Description
        description = QLabel(
            "<h3>Add Metadata to Video Files</h3>"
            "<p>This tool allows you to add cover art and/or subtitles to your video files.</p>"
        )
        layout.addWidget(description)
        
        form_layout = QFormLayout()
        
        # Target folder selection
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Select folder containing videos to modify...")
        folder_browse_btn = QPushButton("Browse...")
        folder_browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(folder_browse_btn)
        form_layout.addRow("Target Folder:", folder_layout)
        
        # Cover art section
        form_layout.addRow(QLabel(""), QLabel(""))
        form_layout.addRow(QLabel("<b>Cover Art:</b>"), QLabel(""))
        
        self.add_cover_art_check = QCheckBox("Add cover art to videos")
        form_layout.addRow("", self.add_cover_art_check)
        
        cover_art_layout = QHBoxLayout()
        self.cover_art_edit = QLineEdit()
        self.cover_art_edit.setPlaceholderText("Select cover art image...")
        cover_art_browse_btn = QPushButton("Browse...")
        cover_art_browse_btn.clicked.connect(self._browse_cover_art)
        cover_art_layout.addWidget(self.cover_art_edit)
        cover_art_layout.addWidget(cover_art_browse_btn)
        form_layout.addRow("Cover Art File:", cover_art_layout)
        
        # Subtitle section
        form_layout.addRow(QLabel(""), QLabel(""))
        form_layout.addRow(QLabel("<b>Subtitles:</b>"), QLabel(""))
        
        self.add_subtitles_check = QCheckBox("Add subtitles to videos")
        form_layout.addRow("", self.add_subtitles_check)
        
        # Subtitle mode selection
        subtitle_mode_layout = QHBoxLayout()
        self.subtitle_mode_folder = QCheckBox("Search folder for matching subtitle files")
        self.subtitle_mode_folder.setChecked(True)
        self.subtitle_mode_folder.toggled.connect(self._update_subtitle_mode)
        subtitle_mode_layout.addWidget(self.subtitle_mode_folder)
        form_layout.addRow("", subtitle_mode_layout)
        
        # Language code input
        self.language_code_edit = QLineEdit("eng")
        self.language_code_edit.setMaxLength(3)
        self.language_code_edit.setPlaceholderText("e.g., eng, jpn, spa")
        self.language_code_edit.setMaximumWidth(100)
        form_layout.addRow("Language Code:", self.language_code_edit)
        
        # Subtitle folder/file selection
        self.subtitle_folder_layout = QHBoxLayout()
        self.subtitle_path_edit = QLineEdit()
        self.subtitle_path_edit.setPlaceholderText("Select folder to search for subtitle files...")
        self.subtitle_browse_btn = QPushButton("Browse Folder...")
        self.subtitle_browse_btn.clicked.connect(self._browse_subtitle_folder)
        self.subtitle_folder_layout.addWidget(self.subtitle_path_edit)
        self.subtitle_folder_layout.addWidget(self.subtitle_browse_btn)
        form_layout.addRow("Subtitle Source:", self.subtitle_folder_layout)
        
        layout.addLayout(form_layout)
        
        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.process_btn = QPushButton("Process Videos")
        self.process_btn.clicked.connect(self._process_videos)
        button_layout.addWidget(self.process_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _browse_folder(self):
        """Browse for target folder."""
        path = QFileDialog.getExistingDirectory(self, "Select Target Folder")
        if path:
            self.folder_edit.setText(path)
    
    def _browse_cover_art(self):
        """Browse for cover art image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Art Image", "",
            "Image Files (*.jpg *.jpeg *.png);;All Files (*)"
        )
        if file_path:
            self.cover_art_edit.setText(file_path)
    
    def _browse_subtitle_folder(self):
        """Browse for subtitle folder."""
        path = QFileDialog.getExistingDirectory(self, "Select Subtitle Folder")
        if path:
            self.subtitle_path_edit.setText(path)
    
    def _update_subtitle_mode(self, checked):
        """Update subtitle selection mode."""
        if checked:
            self.subtitle_path_edit.setPlaceholderText("Select folder to search for .lang.srt files...")
            self.subtitle_browse_btn.setText("Browse Folder...")
            self.subtitle_browse_btn.clicked.disconnect()
            self.subtitle_browse_btn.clicked.connect(self._browse_subtitle_folder)
        else:
            self.subtitle_path_edit.setPlaceholderText("Select subtitle file for each video...")
            self.subtitle_browse_btn.setText("Per-Video Selection")
            self.subtitle_browse_btn.clicked.disconnect()
            self.subtitle_browse_btn.clicked.connect(self._per_video_subtitle_selection)
    
    def _per_video_subtitle_selection(self):
        """Set per-video subtitle selection mode."""
        self.subtitle_path_edit.setText("[Per-Video Selection Mode]")
    
    def _process_videos(self):
        """Process videos with metadata additions."""
        import subprocess
        from pathlib import Path
        
        # Validate inputs
        target_folder = self.folder_edit.text()
        if not target_folder or not Path(target_folder).exists():
            QMessageBox.warning(self, "Error", "Please select a valid target folder.")
            return
        
        add_cover = self.add_cover_art_check.isChecked()
        add_subs = self.add_subtitles_check.isChecked()
        
        if not add_cover and not add_subs:
            QMessageBox.warning(self, "Error", "Please select at least one metadata type to add.")
            return
        
        cover_art_path = self.cover_art_edit.text() if add_cover else None
        if add_cover and (not cover_art_path or not Path(cover_art_path).exists()):
            QMessageBox.warning(self, "Error", "Please select a valid cover art file.")
            return
        
        subtitle_path = self.subtitle_path_edit.text() if add_subs else None
        per_video_mode = not self.subtitle_mode_folder.isChecked()
        
        if add_subs and not per_video_mode:
            if not subtitle_path or not Path(subtitle_path).exists():
                QMessageBox.warning(self, "Error", "Please select a valid subtitle folder.")
                return
        
        # Find all video files
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.m4v'}
        video_files = []
        for ext in video_extensions:
            video_files.extend(list(Path(target_folder).rglob(f'*{ext}')))
        
        if not video_files:
            QMessageBox.warning(self, "Error", "No video files found in the target folder.")
            return
        
        # Confirm processing
        response = QMessageBox.question(
            self, "Confirm Processing",
            f"Found {len(video_files)} video file(s).\n\n"
            f"Add cover art: {add_cover}\n"
            f"Add subtitles: {add_subs}\n\n"
            f"This will create new files with '_metadata' suffix.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if response != QMessageBox.StandardButton.Yes:
            return
        
        # Process videos
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(video_files))
        self.progress_bar.setValue(0)
        self.process_btn.setEnabled(False)
        
        successful = 0
        failed = 0
        
        for idx, video_file in enumerate(video_files):
            self.status_label.setText(f"Processing: {video_file.name}")
            self.progress_bar.setValue(idx)
            
            try:
                # Determine output path
                output_file = video_file.parent / f"{video_file.stem}_metadata{video_file.suffix}"
                
                # Build ffmpeg command
                cmd = ["ffmpeg", "-i", str(video_file)]
                
                map_idx = 0
                # Add cover art
                if add_cover:
                    cmd.extend(["-i", cover_art_path])
                    map_idx += 1
                
                # Add subtitle
                subtitle_file = None
                if add_subs:
                    if per_video_mode:
                        # Per-video selection
                        file_path, _ = QFileDialog.getOpenFileName(
                            self, f"Select Subtitle for {video_file.name}", "",
                            "Subtitle Files (*.srt *.ass *.ssa *.vtt);;All Files (*)"
                        )
                        if file_path:
                            subtitle_file = file_path
                    else:
                        # Search for matching subtitle
                        subtitle_folder = Path(subtitle_path)
                        lang_code = self.language_code_edit.text().strip() or "eng"
                        # Look for files matching pattern: videoname.{lang_code}.srt
                        base_name = video_file.stem
                        potential_subs = list(subtitle_folder.glob(f"{base_name}.{lang_code}.srt"))
                        if potential_subs:
                            subtitle_file = str(potential_subs[0])
                
                if subtitle_file:
                    cmd.extend(["-i", subtitle_file])
                    map_idx += 1
                
                # Map all streams
                cmd.extend(["-map", "0"])  # All streams from video
                
                if add_cover:
                    cmd.extend(["-map", "1", "-disposition:v:1", "attached_pic"])
                
                if subtitle_file:
                    cmd.extend(["-map", str(map_idx), "-c:s", "mov_text"])
                
                # Copy codecs
                cmd.extend(["-c:v", "copy", "-c:a", "copy"])
                
                # Output file
                cmd.append(str(output_file))
                
                # Run ffmpeg
                result = subprocess.run(
                    cmd, capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    successful += 1
                else:
                    failed += 1
                    print(f"Failed to process {video_file.name}: {result.stderr}")
            
            except Exception as e:
                failed += 1
                print(f"Error processing {video_file.name}: {e}")
        
        # Complete
        self.progress_bar.setValue(len(video_files))
        self.status_label.setText(f"Complete: {successful} successful, {failed} failed")
        self.process_btn.setEnabled(True)
        
        QMessageBox.information(
            self, "Processing Complete",
            f"Metadata processing complete!\n\n"
            f"Successful: {successful}\n"
            f"Failed: {failed}"
        )


class RecategorizeDialog(QDialog):
    """Dialog for manually recategorizing a media file."""
    
    def __init__(self, media_info: MediaInfo, parent=None):
        """Initialize the recategorization dialog."""
        super().__init__(parent)
        self.media_info = media_info
        self.setWindowTitle("Recategorize Media File")
        self.setMinimumWidth(500)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout()
        
        # File info
        info_label = QLabel(f"<b>File:</b> {self.media_info.filename}<br>"
                           f"<b>Current Path:</b> {self.media_info.path}")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        form_layout = QFormLayout()
        
        # Category selection
        self.category_combo = QComboBox()
        self.category_combo.addItem("TV Show", MediaCategory.SHOW)
        self.category_combo.addItem("Movie", MediaCategory.MOVIE)
        self.category_combo.addItem("Extra/Bonus Feature", MediaCategory.EXTRA)
        
        # Set current category
        current_cat = self.media_info.category if hasattr(self.media_info, 'category') else MediaCategory.MOVIE
        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == current_cat:
                self.category_combo.setCurrentIndex(i)
                break
        
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        form_layout.addRow("Category:", self.category_combo)
        
        # Show name (only for TV shows)
        self.show_name_edit = QLineEdit()
        self.show_name_edit.setText(self.media_info.show_name if self.media_info.show_name else "")
        self.show_name_label = QLabel("Show Name:")
        form_layout.addRow(self.show_name_label, self.show_name_edit)
        
        # Season (only for TV shows)
        self.season_spin = QSpinBox()
        self.season_spin.setRange(0, 99)
        self.season_spin.setValue(self.media_info.season if self.media_info.season else 1)
        self.season_label = QLabel("Season:")
        form_layout.addRow(self.season_label, self.season_spin)
        
        # Episode (only for TV shows)
        self.episode_spin = QSpinBox()
        self.episode_spin.setRange(0, 999)
        self.episode_spin.setValue(self.media_info.episode if self.media_info.episode else 1)
        self.episode_label = QLabel("Episode:")
        form_layout.addRow(self.episode_label, self.episode_spin)
        
        layout.addLayout(form_layout)
        
        # Update field visibility based on initial category
        self._on_category_changed()
        
        # Help text
        help_text = QLabel(
            "<i>Note: Changes will be saved to your config and applied on the next scan.</i>"
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def _on_category_changed(self):
        """Handle category change - show/hide TV show fields."""
        is_show = self.category_combo.currentData() == MediaCategory.SHOW
        
        self.show_name_label.setVisible(is_show)
        self.show_name_edit.setVisible(is_show)
        self.season_label.setVisible(is_show)
        self.season_spin.setVisible(is_show)
        self.episode_label.setVisible(is_show)
        self.episode_spin.setVisible(is_show)
    
    def get_categorization(self):
        """Get the categorization from the dialog."""
        category = self.category_combo.currentData()
        show_name = self.show_name_edit.text() if category == MediaCategory.SHOW else None
        season = self.season_spin.value() if category == MediaCategory.SHOW else None
        episode = self.episode_spin.value() if category == MediaCategory.SHOW else None
        
        return category, show_name, season, episode


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the main window.
        
        Args:
            config_manager: ConfigManager instance.
        """
        super().__init__()
        self.config_manager = config_manager
        self.config = config_manager.load_config()
        self.media_files: List[MediaInfo] = []
        self.scanner: Optional[MediaScanner] = None
        self.scan_thread: Optional[ScanThread] = None
        self.encoder: Optional[BatchEncoder] = None
        self.encoding_thread: Optional[EncodingThread] = None
        
        self.setWindowTitle("Open Media Manager")
        self.setMinimumSize(1200, 700)
        
        self._setup_ui()
        self._init_scanner()
        
        # Trigger scan on startup if media path is configured
        QTimer.singleShot(100, self._startup_scan)
    
    def _startup_scan(self):
        """Trigger initial scan if media path is configured."""
        media_path = self.config.get("media_path", "")
        if media_path:
            self._rescan()
    
    def _setup_ui(self):
        """Set up the UI components."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Top toolbar
        toolbar = QHBoxLayout()
        
        self.rescan_btn = QPushButton("Rescan")
        self.rescan_btn.clicked.connect(self._rescan)
        toolbar.addWidget(self.rescan_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._stop_operation)
        self.stop_btn.hide()  # Hidden by default
        self.stop_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; }")
        toolbar.addWidget(self.stop_btn)
        
        self.metadata_btn = QPushButton("Add Metadata")
        self.metadata_btn.clicked.connect(self._open_metadata_tool)
        toolbar.addWidget(self.metadata_btn)
        
        toolbar.addStretch()
        
        self.reencode_selected_btn = QPushButton("Reencode Selected")
        self.reencode_selected_btn.clicked.connect(self._reencode_selected)
        self.reencode_selected_btn.setEnabled(False)
        toolbar.addWidget(self.reencode_selected_btn)
        
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(settings_btn)
        
        layout.addLayout(toolbar)
        
        # Status label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        # Progress bar
        # Batch progress (file X of Y)
        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.hide()
        self.batch_progress_bar.setFormat("File %v of %m")
        layout.addWidget(self.batch_progress_bar)
        
        # Current file progress (0-100%)
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.hide()
        self.file_progress_bar.setFormat("%p%")
        self.file_progress_bar.setTextVisible(True)
        layout.addWidget(self.file_progress_bar)
        
        # Media tree (hierarchical view)
        self.media_tree = QTreeWidget()
        self.media_tree.setColumnCount(9)
        self.media_tree.setHeaderLabels([
            "Name", "Status", "Resolution", "Codec", "Bitrate", 
            "Bit Depth", "FPS", "Size", "Issues"
        ])
        
        # Set column resize modes
        header = self.media_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Resolution
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Codec
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Bitrate
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Bit Depth
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # FPS
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Size
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)  # Issues
        
        self.media_tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        self.media_tree.setAlternatingRowColors(True)
        self.media_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.media_tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.media_tree)
        
        # Summary info
        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)
    
    def _init_scanner(self):
        """Initialize the media scanner."""
        quality_standards = self.config_manager.get_quality_standards(self.config)
        manual_overrides = self.config.get("manual_overrides", {})
        self.scanner = MediaScanner(quality_standards, manual_overrides)
        
        # If we have existing media files, re-check compliance with new standards
        if self.media_files:
            for media_info in self.media_files:
                self.scanner.update_compliance(media_info)
            # Update the display
            self._populate_table()
            self._update_summary()
        
        # If we have existing media files, re-check compliance with new standards
        if self.media_files:
            for media_info in self.media_files:
                self.scanner.update_compliance(media_info)
            # Update the display
            self._populate_table()
            self._update_summary()
    
    def _stop_operation(self):
        """Stop current scan or encoding operation."""
        # Stop scanning if active
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.status_label.setText("Stopping scan...")
        
        # Stop encoding if active
        if self.encoder and self.encoder.is_running:
            self.encoder.stop_encoding()
            self.status_label.setText("Stopping encoding...")
    
    def _rescan(self):
        """Rescan the media path from settings."""
        media_path = self.config.get("media_path", "")
        if media_path:
            self._start_scan(Path(media_path))
        else:
            QMessageBox.warning(self, "No Media Path", "Please set a media path in Settings first.")
    
    def _show_context_menu(self, position):
        """Show context menu for tree items."""
        item = self.media_tree.itemAt(position)
        if not item:
            return
        
        # Get the media info from the item
        media_info = item.data(0, Qt.ItemDataRole.UserRole)
        
        # Check if this is a group node (show/season) or a file node
        if not media_info or not isinstance(media_info, MediaInfo):
            # This is a group node (show/season) - show group menu
            self._show_group_context_menu(item, position)
            return
        
        # This is a file node - show file menu
        menu = QMenu(self)
        
        # Reanalyze action
        reanalyze_action = menu.addAction("🔄 Reanalyze File")
        reanalyze_action.triggered.connect(lambda: self._reanalyze_file(media_info, item))
        
        # Open parent folder action
        open_folder_action = menu.addAction("📁 Open Parent Folder")
        open_folder_action.triggered.connect(lambda: self._open_parent_folder(media_info))
        
        menu.addSeparator()
        
        # Copy path action
        copy_path_action = menu.addAction("📋 Copy File Path")
        copy_path_action.triggered.connect(lambda: self._copy_path(media_info))
        
        # Show file info action
        info_action = menu.addAction("ℹ️ Show File Info")
        info_action.triggered.connect(lambda: self._show_file_info(media_info))
        
        menu.addSeparator()
        
        # Encode this file action (if it needs encoding)
        if media_info.status == MediaStatus.NEEDS_REENCODING:
            encode_action = menu.addAction("⚙️ Encode This File")
            encode_action.triggered.connect(lambda: self._encode_single_file(media_info))
        
        # Recategorize action
        recategorize_action = menu.addAction("🏷️ Recategorize...")
        recategorize_action.triggered.connect(lambda: self._recategorize_file(media_info))
        
        # Show the menu at the cursor position
        menu.exec(self.media_tree.viewport().mapToGlobal(position))
    
    def _show_group_context_menu(self, item: QTreeWidgetItem, position):
        """Show context menu for show/season group nodes."""
        # Collect all media files under this node
        media_files = self._collect_media_files_from_node(item)
        
        if not media_files:
            return
        
        # Count files that need encoding
        needs_encoding = [m for m in media_files if m.status == MediaStatus.NEEDS_REENCODING]
        
        menu = QMenu(self)
        group_name = item.text(0)
        
        # Encode all files in this group that need encoding
        if needs_encoding:
            encode_action = menu.addAction(f"⚙️ Encode All in '{group_name}' ({len(needs_encoding)} file(s))")
            encode_action.triggered.connect(lambda: self._start_encoding(needs_encoding, EncodingMode.SELECTED))
        
        # Reanalyze all files in this group
        reanalyze_action = menu.addAction(f"🔄 Reanalyze All in '{group_name}' ({len(media_files)} file(s))")
        reanalyze_action.triggered.connect(lambda: self._reanalyze_group(media_files))
        
        # Show info about the group
        menu.addSeparator()
        info_action = menu.addAction(f"ℹ️ Show Group Info")
        info_action.triggered.connect(lambda: self._show_group_info(group_name, media_files))
        
        # Show the menu at the cursor position
        menu.exec(self.media_tree.viewport().mapToGlobal(position))
    
    def _collect_media_files_from_node(self, node: QTreeWidgetItem) -> List[MediaInfo]:
        """Recursively collect MediaInfo objects that need reencoding from a node and its children."""
        media_files = []
        
        # Check if this node itself has media info
        media_info = node.data(0, Qt.ItemDataRole.UserRole)
        if media_info and isinstance(media_info, MediaInfo):
            # Only include files that need reencoding
            if media_info.status == MediaStatus.NEEDS_REENCODING:
                media_files.append(media_info)
        
        # Recursively check all children
        for i in range(node.childCount()):
            child = node.child(i)
            media_files.extend(self._collect_media_files_from_node(child))
        
        return media_files
    
    def _reanalyze_group(self, media_files: List[MediaInfo]):
        """Reanalyze all files in a group."""
        if not media_files:
            return
        
        reply = QMessageBox.question(
            self, "Reanalyze Group",
            f"Reanalyze {len(media_files)} file(s)?\n\nThis may take a while.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.status_label.setText(f"Reanalyzing {len(media_files)} files...")
        self.batch_progress_bar.show()
        self.batch_progress_bar.setMaximum(len(media_files))
        self.batch_progress_bar.setValue(0)
        
        for i, media_info in enumerate(media_files):
            media_info.status = MediaStatus.SCANNING
            media_info.issues.clear()
            self.scanner.analyze_media(media_info)
            self.batch_progress_bar.setValue(i + 1)
        
        self.batch_progress_bar.hide()
        self.status_label.setText(f"Reanalyzed {len(media_files)} files")
        self._populate_table()
        self._update_summary()
    
    def _show_group_info(self, group_name: str, media_files: List[MediaInfo]):
        """Show information about a group of files."""
        total_size = sum(m.file_size for m in media_files)
        total_duration = sum(m.duration for m in media_files)
        
        compliant = sum(1 for m in media_files if m.status == MediaStatus.COMPLIANT)
        needs_encoding = sum(1 for m in media_files if m.status == MediaStatus.NEEDS_REENCODING)
        below_standard = sum(1 for m in media_files if m.status == MediaStatus.BELOW_STANDARD)
        errors = sum(1 for m in media_files if m.status == MediaStatus.ERROR)
        
        info_text = f"""<h3>{group_name}</h3>
        <p><b>Total Files:</b> {len(media_files)}</p>
        <p><b>Total Size:</b> {total_size / (1024**3):.2f} GB</p>
        <p><b>Total Duration:</b> {total_duration / 3600:.2f} hours</p>
        
        <h4>Status Summary:</h4>
        <p>✅ Compliant: {compliant}</p>
        <p>⚠️ Needs Reencoding: {needs_encoding}</p>
        <p>❌ Below Standard: {below_standard}</p>
        <p>⛔ Errors: {errors}</p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Group Information")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(info_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def _reanalyze_file(self, media_info: MediaInfo, item: QTreeWidgetItem):
        """Reanalyze a single file."""
        self.status_label.setText(f"Reanalyzing {media_info.filename}...")
        
        # Reset status
        media_info.status = MediaStatus.SCANNING
        media_info.issues.clear()
        
        # Reanalyze
        self.scanner.analyze_media(media_info)
        
        # Update the tree item
        self._update_tree_item(item, media_info)
        
        self.status_label.setText(f"Reanalyzed: {media_info.filename}")
        self._update_summary()
    
    def _update_tree_item(self, item: QTreeWidgetItem, media_info: MediaInfo):
        """Update a tree item with new media info."""
        # Update all columns
        item.setText(1, media_info.status.value)
        item.setText(2, media_info.resolution)
        item.setText(3, media_info.codec)
        item.setText(4, f"{media_info.bitrate} kbps" if media_info.bitrate > 0 else "N/A")
        item.setText(5, f"{media_info.bit_depth}-bit" if media_info.bit_depth > 0 else "N/A")
        item.setText(6, f"{media_info.fps:.2f}" if media_info.fps > 0 else "N/A")
        
        size_mb = media_info.file_size / (1024 * 1024)
        if size_mb >= 1024:
            size_gb = size_mb / 1024
            item.setText(7, f"{size_gb:.2f} GB")
        else:
            item.setText(7, f"{size_mb:.2f} MB")
        
        issues_str = ", ".join(media_info.issues) if media_info.issues else ""
        item.setText(8, issues_str)
        item.setToolTip(8, issues_str)
        
        # Update color coding
        if media_info.status == MediaStatus.NEEDS_REENCODING:
            color = QColor(228, 177, 3)
            for col in range(9):
                item.setBackground(col, QBrush(color))
                item.setForeground(col, QBrush(QColor(0, 0, 0)))
        else:
            # Clear color
            for col in range(9):
                item.setBackground(col, QBrush())
                item.setForeground(col, QBrush())
    
    def _open_parent_folder(self, media_info: MediaInfo):
        """Open the parent folder of a file."""
        import subprocess
        import sys
        
        parent_path = media_info.path.parent
        
        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', str(parent_path)])
            elif sys.platform == 'win32':  # Windows
                subprocess.run(['explorer', str(parent_path)])
            else:  # Linux
                subprocess.run(['xdg-open', str(parent_path)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {e}")
    
    def _copy_path(self, media_info: MediaInfo):
        """Copy file path to clipboard."""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(str(media_info.path))
        self.status_label.setText(f"Copied path: {media_info.path}")
    
    def _show_file_info(self, media_info: MediaInfo):
        """Show detailed file information dialog."""
        info_text = f"""<h3>{media_info.filename}</h3>
        <p><b>Path:</b> {media_info.path}</p>
        <p><b>Size:</b> {media_info.file_size / (1024**2):.2f} MB</p>
        <p><b>Status:</b> {media_info.status.value} {media_info.status.name}</p>
        
        <h4>Video Properties:</h4>
        <p><b>Codec:</b> {media_info.codec}</p>
        <p><b>Resolution:</b> {media_info.resolution} ({media_info.width}x{media_info.height})</p>
        <p><b>Bitrate:</b> {media_info.bitrate} kbps</p>
        <p><b>Bit Depth:</b> {media_info.bit_depth}-bit</p>
        <p><b>FPS:</b> {media_info.fps:.2f}</p>
        <p><b>Duration:</b> {media_info.duration / 60:.2f} minutes</p>
        
        <h4>Audio:</h4>
        <p><b>Codec:</b> {media_info.audio_codec}</p>
        <p><b>Channels:</b> {media_info.audio_channels}</p>
        <p><b>Language:</b> {media_info.audio_language or 'Unknown'}</p>
        
        <h4>Subtitles:</h4>
        <p>{', '.join(media_info.subtitle_tracks) if media_info.subtitle_tracks else 'None'}</p>
        
        {f'<h4>Issues:</h4><p style="color: red;">{"<br>".join(media_info.issues)}</p>' if media_info.issues else ''}
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("File Information")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(info_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def _encode_single_file(self, media_info: MediaInfo):
        """Encode a single file."""
        self._start_encoding([media_info], EncodingMode.SELECTED)
    
    def _recategorize_file(self, media_info: MediaInfo):
        """Open dialog to recategorize a file."""
        dialog = RecategorizeDialog(media_info, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get the new categorization
            new_category, show_name, season, episode = dialog.get_categorization()
            
            # Update manual_overrides in config
            if "manual_overrides" not in self.config:
                self.config["manual_overrides"] = {}
            
            self.config["manual_overrides"][str(media_info.path)] = {
                "category": new_category.value,
                "show_name": show_name,
                "season": season,
                "episode": episode
            }
            
            # Save config
            self.config_manager.save_config(self.config)
            
            # Reinitialize scanner with updated overrides and rescan
            self._init_scanner()
            QMessageBox.information(
                self, "Recategorization Saved",
                f"File has been recategorized. Rescanning to apply changes..."
            )
            self._rescan()
    
    def _start_scan(self, directory: Path):
        """
        Start scanning a directory.
        
        Args:
            directory: Directory to scan.
        """
        self.status_label.setText(f"Scanning {directory}...")
        self.batch_progress_bar.show()
        self.batch_progress_bar.setMaximum(0)  # Indeterminate
        self.rescan_btn.setEnabled(False)
        self.stop_btn.show()
        self.reencode_selected_btn.setEnabled(False)
        
        # Create and start scan thread
        self.scan_thread = ScanThread(directory, self.scanner, self.config)
        self.scan_thread.progress.connect(self._update_scan_progress)
        self.scan_thread.scan_complete.connect(self._scan_complete)
        self.scan_thread.start()
    
    def _update_scan_progress(self, current: int, total: int, filename: str):
        """Update scan progress."""
        self.batch_progress_bar.setMaximum(total)
        self.batch_progress_bar.setValue(current)
        self.status_label.setText(f"Scanning {current}/{total}: {filename}")
    
    def _scan_complete(self, media_files: List[MediaInfo]):
        """
        Handle scan completion.
        
        Args:
            media_files: List of scanned MediaInfo objects.
        """
        self.media_files = media_files
        self.batch_progress_bar.hide()
        self.stop_btn.hide()
        self.rescan_btn.setEnabled(True)
        self.reencode_selected_btn.setEnabled(True)
        
        # Update table
        self._populate_table()
        
        # Update summary
        compliant = sum(1 for m in media_files if m.status == MediaStatus.COMPLIANT)
        needs_encoding = sum(1 for m in media_files if m.status == MediaStatus.NEEDS_REENCODING)
        below_standard = sum(1 for m in media_files if m.status == MediaStatus.BELOW_STANDARD)
        
        self.status_label.setText(
            f"Scan complete: {len(media_files)} files found"
        )
        self.summary_label.setText(
            f"✅ Compliant: {compliant} | ⚠️ Needs Re-encoding: {needs_encoding} | "
            f"❌ Below Standard: {below_standard}"
        )
    
    def _extract_show_name_from_path(self, file_path: Path) -> Optional[str]:
        """
        Extract show name from file path for extras grouping.
        
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
    
    def _populate_table(self):
        """Populate the media tree with scanned files in hierarchical format."""
        self.media_tree.clear()
        
        # Separate TV shows, movies, and extras
        shows = defaultdict(lambda: defaultdict(list))  # {show_name: {season: [episodes]}}
        movies = []
        extras_by_show = defaultdict(list)  # {show_name: [extras]}
        extras_ungrouped = []
        
        for media_info in self.media_files:
            if media_info.category == MediaCategory.EXTRA:
                # Try to extract show name from path for grouping extras
                show_name = self._extract_show_name_from_path(media_info.path)
                if show_name:
                    extras_by_show[show_name].append(media_info)
                else:
                    extras_ungrouped.append(media_info)
            elif media_info.is_show and media_info.show_name:
                season_key = media_info.season if media_info.season is not None else 0
                shows[media_info.show_name][season_key].append(media_info)
            else:
                movies.append(media_info)
        
        # Compute counts for headings
        num_shows = len(shows)
        num_episodes = sum(len(season_eps) for show in shows.values() for season_eps in show.values())
        num_movies = len(movies)
        num_extras_shows = len(extras_by_show)
        num_extras = sum(len(v) for v in extras_by_show.values()) + len(extras_ungrouped)

        # Add TV Shows section
        if shows:
            tv_label = f"📺 TV Shows - {num_shows} show{'s' if num_shows != 1 else ''}, {num_episodes} episode{'s' if num_episodes != 1 else ''}"
            tv_shows_root = QTreeWidgetItem(self.media_tree, [tv_label])
            tv_shows_root.setExpanded(False)
            font = tv_shows_root.font(0)
            font.setBold(True)
            tv_shows_root.setFont(0, font)
            
            for show_name in sorted(shows.keys()):
                # Calculate status counts for this show
                all_episodes = [ep for season_eps in shows[show_name].values() for ep in season_eps]
                show_compliant = sum(1 for ep in all_episodes if ep.status in [MediaStatus.COMPLIANT, MediaStatus.BELOW_STANDARD])
                show_needs_encoding = sum(1 for ep in all_episodes if ep.status == MediaStatus.NEEDS_REENCODING)

                # Create show item with status indicator
                status_text = f" - ⚠️ {show_needs_encoding}" if all_episodes else ""
                if all_episodes:
                    if show_compliant == 0 and show_needs_encoding == 0: status_text = ""
                    elif show_needs_encoding == 0: status_text = f" - ✅"
                    else: status_text = f" - ⚠️ {show_needs_encoding}"

                show_item = QTreeWidgetItem(tv_shows_root, [f"{show_name}{status_text}"])
                show_item.setExpanded(False)
                
                for season_num in sorted(shows[show_name].keys()):
                    if season_num == 0:
                        season_name = "Specials"
                    elif season_num > 0:
                        season_name = f"Season {season_num}"
                    else:
                        season_name = "Unknown Season"
                    
                    # Calculate status counts for this season
                    episodes = shows[show_name][season_num]
                    season_compliant = sum(1 for ep in episodes if ep.status in [MediaStatus.COMPLIANT, MediaStatus.BELOW_STANDARD])
                    season_needs_encoding = sum(1 for ep in episodes if ep.status == MediaStatus.NEEDS_REENCODING)

                    # Create season item with status indicator
                    status_text = f" - ⚠️ {season_needs_encoding}" if all_episodes else ""
                    if all_episodes:
                        if season_compliant == 0 and season_needs_encoding == 0: status_text = ""
                        elif season_needs_encoding == 0: status_text = f" - ✅"
                        else: status_text = f" - ⚠️ {season_needs_encoding}"
                    season_item = QTreeWidgetItem(show_item, [f"{season_name}{status_text}"])
                    season_item.setExpanded(False)
                    
                    # Sort episodes by episode number
                    episodes_sorted = sorted(episodes, 
                                    key=lambda x: (x.episode if x.episode else 999, x.filename))
                    
                    for media_info in episodes_sorted:
                        self._create_media_item(season_item, media_info)
        
        # Add Movies section
        if movies:
            movies_label = f"🎬 Movies - {num_movies}"
            movies_root = QTreeWidgetItem(self.media_tree, [movies_label])
            movies_root.setExpanded(False)
            font = movies_root.font(0)
            font.setBold(True)
            movies_root.setFont(0, font)
            
            for media_info in sorted(movies, key=lambda x: x.filename):
                self._create_media_item(movies_root, media_info)
        
        # Add Extras section (grouped by show when possible)
        if extras_by_show or extras_ungrouped:
            extras_label = f"📀 Extras - {num_extras_shows} show{'s' if num_extras_shows != 1 else ''}, {num_extras} extra{'s' if num_extras != 1 else ''}"
            extras_root = QTreeWidgetItem(self.media_tree, [extras_label])
            extras_root.setExpanded(False)
            font = extras_root.font(0)
            font.setBold(True)
            extras_root.setFont(0, font)
            
            # Add grouped extras by show
            for show_name in sorted(extras_by_show.keys()):
                show_item = QTreeWidgetItem(extras_root, [show_name])
                show_item.setExpanded(False)
                
                for media_info in sorted(extras_by_show[show_name], key=lambda x: x.filename):
                    self._create_media_item(show_item, media_info)
            
            # Add ungrouped extras
            for media_info in sorted(extras_ungrouped, key=lambda x: x.filename):
                self._create_media_item(extras_root, media_info)
    
    def _create_media_item(self, parent: QTreeWidgetItem, media_info: MediaInfo) -> QTreeWidgetItem:
        """Create a tree item for a media file."""
        # Build display name
        if media_info.is_show and media_info.episode is not None:
            display_name = f"E{media_info.episode:02d} - {media_info.filename}"
        else:
            display_name = media_info.filename
        
        item = QTreeWidgetItem(parent)
        item.setData(0, Qt.ItemDataRole.UserRole, media_info)  # Store media_info reference
        
        # Name
        item.setText(0, display_name)
        item.setToolTip(0, media_info.filename)
        
        # Status
        item.setText(1, media_info.status.value)
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
        
        # Resolution
        item.setText(2, media_info.resolution)
        
        # Codec
        item.setText(3, media_info.codec)
        
        # Bitrate
        bitrate_str = f"{media_info.bitrate} kbps" if media_info.bitrate > 0 else "N/A"
        item.setText(4, bitrate_str)
        
        # Bit depth
        bit_depth_str = f"{media_info.bit_depth}-bit" if media_info.bit_depth > 0 else "N/A"
        item.setText(5, bit_depth_str)
        
        # FPS
        fps_str = f"{media_info.fps:.2f}" if media_info.fps > 0 else "N/A"
        item.setText(6, fps_str)
        
        # File size
        size_mb = media_info.file_size / (1024 * 1024)
        if size_mb >= 1024:
            size_gb = size_mb / 1024
            item.setText(7, f"{size_gb:.2f} GB")
        else:
            item.setText(7, f"{size_mb:.2f} MB")
        
        # Issues
        issues_str = ", ".join(media_info.issues) if media_info.issues else ""
        item.setText(8, issues_str)
        item.setToolTip(8, issues_str)
        
        # Color code based on status
        if media_info.status == MediaStatus.NEEDS_REENCODING:
            color = QColor(228, 177, 3)  # Dark yellow
            for col in range(9):
                item.setBackground(col, QBrush(color))
                item.setForeground(col, QBrush(QColor(0, 0, 0)))  # Black text
        
        return item
    
    def _reencode_selected(self):
        """Re-encode selected files and all files in selected groups."""
        selected_items = self.media_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select files or groups to re-encode.")
            return
        
        # Collect all MediaInfo objects from selected items and their children
        all_media_files = []
        for item in selected_items:
            # Recursively collect media files from this item and its children
            media_files = self._collect_media_files_from_node(item)
            all_media_files.extend(media_files)
        
        # Deduplicate by using a set based on file path
        seen_paths = set()
        selected_files = []
        for media_info in all_media_files:
            if str(media_info.path) not in seen_paths:
                seen_paths.add(str(media_info.path))
                selected_files.append(media_info)
        
        if not selected_files:
            QMessageBox.warning(self, "No Files", "No valid media files found in selection.")
            return
        
        self._start_encoding(selected_files, EncodingMode.SELECTED)
    
    def _start_encoding(self, files: List[MediaInfo], mode: EncodingMode):
        """
        Start encoding process.
        
        Args:
            files: List of MediaInfo to encode.
            mode: Encoding mode.
        """
        # Show pre-encode settings dialog
        settings_dialog = PreEncodeSettingsDialog(self.config, files, self)
        if settings_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        # Get updated config from dialog
        updated_config = settings_dialog.get_config()
        
        # Initialize encoder with updated settings
        encoding_params = self.config_manager.get_encoding_params(updated_config)
        naming_params = updated_config.get("naming", {})
        self.encoder = BatchEncoder(encoding_params, naming_params)
        
        # Prepare jobs
        jobs = self.encoder.prepare_jobs(files, mode)
        
        if not jobs:
            QMessageBox.information(
                self, "No Jobs", 
                "No files need encoding based on current criteria."
            )
            return
        
        # Create and show encoding log dialog
        self.encoding_log_dialog = EncodingLogDialog(self, total_files=len(jobs), jobs=jobs)
        self.encoding_log_dialog.stop_requested.connect(self.encoder.stop)
        self.encoding_log_dialog.show()
        self.encoding_log_dialog.log_message("Starting encoding process...", "#4a9eff")
        self.encoding_log_dialog.log_message(f"Total files to encode: {len(jobs)}", "#4a9eff")
        self.encoding_log_dialog.log_message("", "#d4d4d4")
        
        # Initialize batch ETA tracking for main window
        if len(jobs) > 1:
            self.total_batch_frames = sum(job.media_info.duration * job.media_info.fps for job in jobs if job.media_info.duration and job.media_info.fps)
            self.jobs_for_batch = jobs
        else:
            self.total_batch_frames = 0
            self.jobs_for_batch = []
        self.completed_frames = 0
        self.current_job_total_frames = 0
        
        # Start encoding thread
        self.encoding_thread = EncodingThread(self.encoder)
        self.encoding_thread.progress_signal.connect(self._update_encoding_progress)
        self.encoding_thread.job_complete.connect(self._encoding_job_complete)
        self.encoding_thread.all_complete.connect(self._encoding_all_complete)
        
        # Connect encoder log signals to log dialog
        self.encoder.log_signal.connect(self._handle_encoder_log)
        
        self.status_label.setText(f"Encoding {len(jobs)} file(s)...")
        
        # Show both progress bars
        self.batch_progress_bar.show()
        self.batch_progress_bar.setMaximum(len(jobs))
        self.batch_progress_bar.setValue(0)
        
        self.file_progress_bar.show()
        self.file_progress_bar.setMaximum(100)
        self.file_progress_bar.setValue(0)
        self.file_progress_bar.setFormat("%p%")
        
        self.rescan_btn.setEnabled(False)
        self.reencode_selected_btn.setEnabled(False)
        self.stop_btn.show()
        
        self.encoding_thread.start()
    
    def _update_encoding_progress(self, job_index: int, progress: float, status: str, encoding_fps: float = 0.0, eta: str = "--:--"):
        """Update encoding progress."""
        # Update batch progress
        self.batch_progress_bar.setValue(job_index)
        
        # Set current job total frames for batch ETA (at start of new job)
        if hasattr(self, 'jobs_for_batch') and self.jobs_for_batch and job_index < len(self.jobs_for_batch):
            job = self.jobs_for_batch[job_index]
            if job.media_info.duration and job.media_info.fps:
                self.current_job_total_frames = job.media_info.duration * job.media_info.fps
        
        # Calculate batch ETA if multi-file encode
        batch_eta_text = ""
        total_jobs = len(self.encoder.jobs)
        if total_jobs > 1 and hasattr(self, 'total_batch_frames') and self.total_batch_frames > 0 and encoding_fps > 0:
            # Calculate frames completed in current file
            current_file_frames = (progress / 100.0) * self.current_job_total_frames
            # Total frames completed so far
            total_completed = self.completed_frames + current_file_frames
            # Remaining frames in batch
            remaining_frames = max(0, self.total_batch_frames - total_completed)
            # Calculate ETA
            remaining_seconds = remaining_frames / encoding_fps
            if remaining_seconds < 3600:  # Less than 1 hour
                eta_minutes = int(remaining_seconds // 60)
                eta_seconds = int(remaining_seconds % 60)
                batch_eta = f"{eta_minutes:02d}:{eta_seconds:02d}"
            else:  # 1 hour or more
                eta_hours = int(remaining_seconds // 3600)
                eta_minutes = int((remaining_seconds % 3600) // 60)
                batch_eta = f"{eta_hours}h {eta_minutes:02d}m"
            batch_eta_text = f" | ETA: {batch_eta}"
        
        # Update file progress with ETA and batch ETA
        self.batch_progress_bar.setFormat(f"File %v of %m{batch_eta_text}")
        self.file_progress_bar.setValue(int(progress))
        if eta != "--:--":
            self.file_progress_bar.setFormat(f"%p% | ETA: {eta}")
        else:
            self.file_progress_bar.setFormat("%p%")
        
        # Truncate filename if longer than 60 characters
        filename = self.encoder.jobs[job_index].media_info.filename
        if len(filename) > 60:
            filename = filename[:57] + "..."
        self.status_label.setText(f"[{job_index + 1}/{total_jobs}] Encoding: {filename}")
        
        # Update progress in log dialog (no console logging), pass encoding_fps for batch ETA
        if hasattr(self, 'encoding_log_dialog') and self.encoding_log_dialog:
            self.encoding_log_dialog.update_file_progress(progress, encoding_fps, eta, filename)
    
    def _encoding_job_complete(self, job_index: int, success: bool, message: str):
        """Handle completion of an encoding job."""
        # Update completed frames for batch ETA
        if hasattr(self, 'current_job_total_frames'):
            self.completed_frames += self.current_job_total_frames
        
        # Update batch progress to show completed file
        self.batch_progress_bar.setValue(job_index + 1)
        
        job = self.encoder.jobs[job_index]
        
        if success:
            # Show completion message briefly
            self.status_label.setText(f"✓ Completed: {job.media_info.filename} | {message}")
            
            # Log to log dialog with size comparison
            if hasattr(self, 'encoding_log_dialog') and self.encoding_log_dialog:
                try:
                    original_size = job.media_info.path.stat().st_size
                    encoded_size = job.output_path.stat().st_size if job.output_path.exists() else 0
                    
                    self.encoding_log_dialog.log_file_complete(
                        str(job.media_info.path),
                        str(job.output_path),
                        original_size,
                        encoded_size,
                        success=True
                    )
                except Exception as e:
                    self.encoding_log_dialog.log_error(f"Could not get file sizes: {e}")
        else:
            print(f"Job {job_index} failed: {message}")
            self.status_label.setText(f"✗ Failed: {job.media_info.filename}")
            
            # Log failure to log dialog
            if hasattr(self, 'encoding_log_dialog') and self.encoding_log_dialog:
                self.encoding_log_dialog.log_file_complete(
                    str(job.media_info.path),
                    str(job.output_path),
                    0,
                    0,
                    success=False
                )
                self.encoding_log_dialog.log_error(message)
    
    def _handle_encoder_log(self, log_type: str, message: str, color: str):
        """
        Handle log messages from the encoder.
        
        Args:
            log_type: Type of log message ('file_start', 'command', 'error', etc.)
            message: Log message content.
            color: Color code (optional, may be empty string).
        """
        if not hasattr(self, 'encoding_log_dialog') or not self.encoding_log_dialog:
            return
        
        if log_type == "file_start":
            # Message format: "source_path|dest_path"
            parts = message.split('|')
            if len(parts) == 2:
                self.encoding_log_dialog.log_file_start(parts[0], parts[1])
        elif log_type == "command":
            self.encoding_log_dialog.log_command(message)
        elif log_type == "error":
            self.encoding_log_dialog.log_error(message)
        elif log_type == "ffmpeg_error":
            # FFmpeg error/warning output - show in red/orange
            self.encoding_log_dialog.log_message(f"⚠️ {message}", color if color else "#ff6b6b")
        else:
            # Generic message
            self.encoding_log_dialog.log_message(message, color if color else "#d4d4d4")
    
    def _encoding_all_complete(self):
        """Handle completion of all encoding jobs."""
        self.batch_progress_bar.hide()
        self.file_progress_bar.hide()
        self.stop_btn.hide()
        self.rescan_btn.setEnabled(True)
        self.reencode_selected_btn.setEnabled(True)
        
        successful = sum(1 for job in self.encoder.jobs if job.status == "complete")
        failed = sum(1 for job in self.encoder.jobs if job.status == "failed")
        cancelled = sum(1 for job in self.encoder.jobs if job.status == "cancelled")
        
        # Add completion summary to log dialog
        if hasattr(self, 'encoding_log_dialog') and self.encoding_log_dialog:
            self.encoding_log_dialog.encoding_complete()
            self.encoding_log_dialog.log_message("", "#d4d4d4")
            self.encoding_log_dialog.log_message("=" * 80, "#4a9eff")
            self.encoding_log_dialog.log_message("ENCODING COMPLETE", "#4a9eff")
            self.encoding_log_dialog.log_message("=" * 80, "#4a9eff")
            self.encoding_log_dialog.log_message(f"Successfully encoded: {successful} files", "#4caf50")
            if failed > 0:
                self.encoding_log_dialog.log_message(f"Failed: {failed} files", "#ff4444")
            if cancelled > 0:
                self.encoding_log_dialog.log_message(f"Cancelled: {cancelled} files", "#ffa500")
        
        # If encoding was stopped/cancelled, offer to delete partial encoded files
        if cancelled > 0:
            # Count partial encoded files that exist
            partial_files = [job for job in self.encoder.jobs if job.status == "cancelled" and job.output_path.exists()]
            
            if partial_files:
                reply = QMessageBox.question(
                    self, "Encoding Stopped",
                    f"Encoding was stopped.\n\n"
                    f"Successful: {successful}\n"
                    f"Cancelled: {cancelled}\n"
                    f"Failed: {failed}\n\n"
                    f"Delete {len(partial_files)} partial encoded file(s)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    deleted_count = 0
                    for job in partial_files:
                        try:
                            job.output_path.unlink()
                            deleted_count += 1
                            print(f"[CLEANUP] Deleted partial file: {job.output_path}")
                        except Exception as e:
                            print(f"[ERROR] Failed to delete {job.output_path}: {e}")
                    
                    QMessageBox.information(
                        self, "Cleanup Complete",
                        f"Deleted {deleted_count} of {len(partial_files)} partial file(s)."
                    )
            
            self.status_label.setText(f"Encoding stopped: {successful} successful, {cancelled} cancelled, {failed} failed")
            return
        
        if successful == 0:
            QMessageBox.information(
                self, "Encoding Complete",
                f"Encoding complete!\n\nSuccessful: {successful}\nFailed: {failed}"
            )
            self.status_label.setText(f"Encoding complete: {successful} successful, {failed} failed")
            return
        
        # Generate and save comparison report
        try:
            # Get output directory from first successful job
            output_dir = None
            for job in self.encoder.jobs:
                if job.status == "complete" and job.output_path.exists():
                    output_dir = job.output_path.parent
                    break
            
            if output_dir:
                report_file = self.encoder.save_comparison_report(output_dir)
                print(f"[INFO] Comparison report saved to: {report_file}")
        except Exception as e:
            print(f"[WARNING] Could not save comparison report: {e}")
        
        # Show comparison summary and offer cleanup
        comparison_text = self.encoder.generate_comparison_report()
        
        # Show dialog with comparison and cleanup option
        dialog = EncodingCompleteDialog(comparison_text, successful, failed, self.encoder.jobs, self)
        dialog.exec()

        # Trigger rescan only if cleanup was performed (so it picks up the actual changes)
        if dialog.cleanup_performed:
            try:
                self._rescan()
            except Exception as e:
                print(f"[WARNING] Rescan after cleanup failed: {e}")

        # When the reduction/comparison dialog is closed, also close the encoding log dialog
        if hasattr(self, 'encoding_log_dialog') and self.encoding_log_dialog:
            try:
                self.encoding_log_dialog.close()
            except Exception:
                pass

        self.status_label.setText(f"Encoding complete: {successful} successful, {failed} failed")
    
    def _open_settings(self):
        """Open settings dialog."""
        old_media_path = self.config.get("media_path", "")
        old_quality_standards = self.config.get("quality_standards", {})
        
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_config()
            self.config_manager.save_config(self.config)
            self._init_scanner()
            
            # Check if media path changed
            new_media_path = self.config.get("media_path", "")
            if new_media_path != old_media_path and new_media_path:
                # Trigger rescan if path changed
                QMessageBox.information(self, "Settings Saved", "Settings saved. Rescanning media directory...")
                self._rescan()
            elif old_quality_standards != self.config.get("quality_standards", {}) and self.media_files:
                # Re-check compliance for existing files if quality settings changed
                self._recheck_compliance()
                QMessageBox.information(self, "Settings Saved", "Settings saved. File compliance status updated.")
            else:
                QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")
    
    def _open_metadata_tool(self):
        """Open metadata addition tool."""
        dialog = MetadataDialog(self)
        dialog.exec()
    
    def _recheck_compliance(self):
        """Re-check compliance for all existing media files and update the table."""
        for media_info in self.media_files:
            # Re-analyze compliance with new quality standards
            media_info.status = self.scanner._check_compliance(media_info)
        
        # Update the tree display
        self._populate_table()
        self._update_summary()
    
    def _update_summary(self):
        """Update the summary label with file counts."""
        # Treat below_standard as compliant since encoding skips them
        compliant = sum(1 for m in self.media_files if m.status in [MediaStatus.COMPLIANT, MediaStatus.BELOW_STANDARD])
        needs_encoding = sum(1 for m in self.media_files if m.status == MediaStatus.NEEDS_REENCODING)
        below_standard = sum(1 for m in self.media_files if m.status == MediaStatus.BELOW_STANDARD)
        
        # Count shows vs movies
        shows = sum(1 for m in self.media_files if m.is_show)
        movies = len(self.media_files) - shows
        
        self.summary_label.setText(
            f"📊 Total: {len(self.media_files)} files ({shows} episodes, {movies} movies) | "
            f"✅ Compliant: {compliant} | ⚠️ Needs Re-encoding: {needs_encoding}"
            + (f" | ℹ️ Below Standard: {below_standard}" if below_standard > 0 else "")
        )
