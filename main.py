#!/usr/bin/env python3
"""
Open Media Manager - Main Application Entry Point
Supports both PyQt6-based GUI application and FastAPI-based web interface
for managing and re-encoding media files.
"""

import argparse
import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from gui.gui_components import MainWindow, OOTBDialog

# Configure logging
log_dir = Path.home() / '.config' / 'openmediamanager'
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / 'app.log')
    ]
)
logger = logging.getLogger(__name__)


def run_gui():
    """Run the PyQt6 GUI application."""
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

    # Start webserver in background thread if enabled in config
    if config.get("server", {}).get("run_webserver", True):
        import threading
        server_config = config.get("server", {})
        server_thread = threading.Thread(
            target=run_web_server,
            args=(
                server_config.get("host", "127.0.0.1"),
                server_config.get("port", 8000),
                server_config.get("enable_reload", False)
            ),
            daemon=True
        )
        server_thread.start()

    return app.exec()


def run_web_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Run the FastAPI web server."""
    try:
        from web.server import run_server
        logger.info(f"Starting Open Media Manager web server on {host}:{port}")
        logger.info(f"Open your browser to http://{host}:{port}/")
        run_server(host=host, port=port, reload=reload)
    except ImportError as e:
        logger.error("Required server dependencies not installed")
        logger.error("Please install required packages: pip install -r requirements.txt")
        return 1
    except Exception as e:
        logger.error(f"Error starting web server: {e}", exc_info=True)
        return 1


def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="Open Media Manager - Media library management and batch encoding"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Web server host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Web server port (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for web server (development mode)"
    )

    args = parser.parse_args()

    # Run GUI (default)
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
