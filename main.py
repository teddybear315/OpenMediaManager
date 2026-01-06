#!/usr/bin/env python3
"""
Open Media Manager - Main Application Entry Point
A PyQt6-based GUI application for managing and re-encoding media files.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from config_manager import ConfigManager
from gui_components import MainWindow, OOTBDialog


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Open Media Manager")
    app.setOrganizationName("OpenMediaManager")
    
    # Initialize configuration
    config_manager = ConfigManager()
    
    # Check if this is first run
    if not config_manager.config_exists():
        # Show first run dialog to collect initial settings
        first_run_dialog = OOTBDialog()
        if first_run_dialog.exec() == OOTBDialog.DialogCode.Accepted:
            settings = first_run_dialog.get_settings()
            config_manager.save_config(settings)
        else:
            # User cancelled, exit application
            return 0
    
    # Load configuration
    config = config_manager.load_config()
    
    # Create and show main window
    window = MainWindow(config_manager)
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
