"""
Web module - FastAPI web server and web interface
"""

from .server import ConnectionManager, app, run_server

__all__ = [
    'app',
    'run_server',
    'ConnectionManager',
]
