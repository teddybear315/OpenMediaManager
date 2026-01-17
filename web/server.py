#!/usr/bin/env python3
"""
Web Server for Open Media Manager
FastAPI-based web interface for remote library management.
"""

import asyncio
import json
import logging
import queue
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import uvicorn
from fastapi import (FastAPI, File, Form, HTTPException, Request, UploadFile,
                     WebSocket, WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from core.batch_encoder import BatchEncoder, EncodingJob
from core.config_manager import ConfigManager
from core.media_scanner import (MediaCategory, MediaInfo, MediaScanner,
                                MediaStatus)

logger = logging.getLogger(__name__)


@dataclass
class FileStatistics:
    """Statistics for a single encoded file."""
    filename: str
    original_size: int = 0
    encoded_size: int = 0
    success: bool = False
    error_message: str = ""
    reduction_percent: float = 0.0


@dataclass
class EncodingState:
    """Server-side tracking of encoding state and statistics."""
    is_running: bool = False
    total_files: int = 0
    files_completed: int = 0
    total_original_size: int = 0
    total_encoded_size: int = 0
    file_statistics: List[FileStatistics] = field(default_factory=list)
    log_history: List[Dict] = field(default_factory=list)
    ffmpeg_process: Optional[subprocess.Popen] = None
    process_monitor_thread: Optional[threading.Thread] = None
    start_time: Optional[datetime] = None

    def reset(self):
        """Reset encoding state."""
        self.is_running = False
        self.total_files = 0
        self.files_completed = 0
        self.total_original_size = 0
        self.total_encoded_size = 0
        self.file_statistics = []
        self.log_history = []
        self.ffmpeg_process = None
        self.process_monitor_thread = None
        self.start_time = None

    def get_reduction_percent(self) -> float:
        """Get overall space reduction percentage."""
        if self.total_original_size == 0:
            return 0.0
        return ((self.total_original_size - self.total_encoded_size) / self.total_original_size) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_running": self.is_running,
            "total_files": self.total_files,
            "files_completed": self.files_completed,
            "total_original_size": self.total_original_size,
            "total_encoded_size": self.total_encoded_size,
            "reduction_percent": self.get_reduction_percent(),
            "file_statistics": [
                {
                    "filename": f.filename,
                    "original_size": f.original_size,
                    "encoded_size": f.encoded_size,
                    "success": f.success,
                    "error_message": f.error_message,
                    "reduction_percent": f.reduction_percent,
                }
                for f in self.file_statistics
            ]
        }


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.broadcast_queue = queue.Queue()
        self.broadcast_task = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    def queue_broadcast(self, message: Dict):
        """Queue a message for broadcasting (thread-safe)."""
        self.broadcast_queue.put(message)

    async def broadcast(self, message: Dict):
        """Broadcast message to all connected clients."""
        # Create a copy to avoid "Set changed size during iteration" error
        connections_copy = list(self.active_connections)
        disconnected = set()
        for connection in connections_copy:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def process_broadcast_queue(self):
        """Process queued broadcasts (runs as a background task)."""
        while True:
            try:
                # Get message from queue without blocking (timeout to allow shutdown)
                try:
                    message = self.broadcast_queue.get(timeout=0.1)
                    await self.broadcast(message)
                except queue.Empty:
                    await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error processing broadcast queue: {e}", exc_info=True)


# Global instances
config_manager: Optional[ConfigManager] = None
media_scanner: Optional[MediaScanner] = None
batch_encoder: Optional[BatchEncoder] = None
connection_manager = ConnectionManager()
encoding_state = EncodingState()  # Server-side encoding state tracking

# Post-encode cleanup settings (set when encoding starts)
cleanup_settings = {
    "auto_remove_broken": False,
    "auto_move_smaller": False
}

# Template environment
templates_dir = Path(__file__).parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    autoescape=True
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    global config_manager, media_scanner, batch_encoder
    config_manager = ConfigManager()

    # Load or create config
    if not config_manager.config_exists():
        raise RuntimeError("Configuration not found. Please configure the application first.")

    config = config_manager.load_config()
    # MediaScanner uses quality_standards for compliance checking, NOT encoding settings
    media_scanner = MediaScanner(config.get("quality_standards", {}))
    batch_encoder = BatchEncoder(
        config.get("encoding", {}),
        config.get("naming", {})
    )

    # Start background broadcast queue processor
    async def broadcast_queue_processor():
        await connection_manager.process_broadcast_queue()

    broadcast_task = asyncio.create_task(broadcast_queue_processor())

    # Set up callbacks instead of relying on Qt signals (which don't work in non-Qt threads)
    def handle_log(log_type, msg, color):
        # Map log types to colors (matching Python GUI EncodingLogDialog)
        color_map = {
            "file_start": "#4a9eff",    # Blue
            "command": "#ffcc00",        # Yellow
            "ffmpeg_error": "#ff6b6b",   # Red
            "error": "#ff6b6b",          # Red
            "warning": "#ffa500",        # Orange
            "info": "#d4d4d4",           # Light gray
            "reduction_info": "#4caf50", # Green
        }

        # Use provided color if not empty, otherwise use map
        final_color = color if color.strip() else color_map.get(log_type, "#d4d4d4")

        data = {
            "type": "log",
            "log_type": log_type,
            "message": msg,
            "color": final_color,
            "timestamp": datetime.now().isoformat()
        }

        # Keep log history for reconnection sync
        encoding_state.log_history.append(data)

        # Parse file_start to emit separate event
        if log_type == "file_start":
            parts = msg.split("|")
            if len(parts) == 2:
                data["type"] = "file_start"
                data["filename"] = Path(parts[0]).name

        # Broadcast immediately without queuing (runs in thread)
        asyncio.run(connection_manager.broadcast(data))

    def handle_progress(job_index, progress, status, speed, eta):
        if batch_encoder.jobs and job_index < len(batch_encoder.jobs):
            job = batch_encoder.jobs[job_index]
            data = {
                "type": "file_progress",
                "job_index": job_index,
                "progress": progress,
                "fps": speed,
                "eta": eta,
                "filename": job.media_info.path.name
            }

            # Include batch progress if multiple files
            if encoding_state.total_files > 1:
                batch_progress = (encoding_state.files_completed * 100 + progress) / encoding_state.total_files
                data["batch_progress"] = batch_progress
                data["batch_eta"] = calculate_batch_eta(encoding_state, progress)

            # Broadcast immediately without queuing (runs in thread)
            asyncio.run(connection_manager.broadcast(data))

    def handle_job_complete(job_index, success, message):
        if batch_encoder.jobs and job_index < len(batch_encoder.jobs):
            job = batch_encoder.jobs[job_index]
            original_size = job.media_info.file_size
            encoded_size = job.output_path.stat().st_size if job.output_path.exists() else 0

            # Update statistics
            encoding_state.files_completed += 1
            encoding_state.total_original_size += original_size
            encoding_state.total_encoded_size += encoded_size

            reduction = ((original_size - encoded_size) / original_size * 100) if original_size > 0 else 0

            file_stat = FileStatistics(
                filename=job.media_info.path.name,
                original_size=original_size,
                encoded_size=encoded_size,
                success=success,
                error_message="" if success else message,
                reduction_percent=reduction
            )
            encoding_state.file_statistics.append(file_stat)

            # Broadcast immediately without queuing (runs in thread)
            asyncio.run(connection_manager.broadcast({
                "type": "file_complete",
                "job_index": job_index,
                "filename": job.media_info.path.name,
                "success": success,
                "original_size": original_size,
                "encoded_size": encoded_size,
                "message": message
            }))

    # Set callbacks on batch encoder (these will be called from the encoding thread)
    batch_encoder.on_log = handle_log
    batch_encoder.on_progress = handle_progress
    batch_encoder.on_job_complete = handle_job_complete

    yield

    # Shutdown
    if batch_encoder and batch_encoder.is_running:
        batch_encoder.should_stop = True

    # Clean up encoding state
    encoding_state.reset()

    # Cancel broadcast task
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass


def calculate_batch_eta(state: EncodingState, current_file_progress: float = 0) -> str:
    """Calculate batch ETA based on files completed and current file progress."""
    if not state.start_time:
        return "--:--"

    elapsed = (datetime.now() - state.start_time).total_seconds()

    # Calculate effective files completed (treating current file progress as fractional completion)
    effective_files_completed = state.files_completed + (current_file_progress / 100)

    if effective_files_completed == 0:
        return "--:--"

    avg_time_per_file = elapsed / effective_files_completed
    remaining_files = state.total_files - state.files_completed - (current_file_progress / 100)

    if avg_time_per_file == 0 or remaining_files <= 0:
        return "--:--"

    eta_seconds = int(avg_time_per_file * remaining_files)
    hours = eta_seconds // 3600
    minutes = (eta_seconds % 3600) // 60
    seconds = eta_seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


# Create FastAPI application
app = FastAPI(
    title="Open Media Manager",
    description="Remote web interface for managing media library",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard."""
    template = jinja_env.get_template("dashboard.html")
    return template.render()


@app.get("/api/config", response_class=JSONResponse)
async def get_config():
    """Get current configuration."""
    if not config_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    config = config_manager.load_config()
    return config


@app.post("/api/config", response_class=JSONResponse)
async def update_config(config: Dict):
    """Update configuration."""
    if not config_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    config_manager.save_config(config)
    return {"status": "success", "message": "Configuration updated"}


@app.get("/api/encoding-profiles", response_class=JSONResponse)
async def get_encoding_profiles():
    """Get all saved encoding profiles."""
    if not config_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    profiles = config_manager.get_encoding_profiles()
    return {"status": "success", "profiles": profiles}


@app.post("/api/encoding-profiles/{profile_name}", response_class=JSONResponse)
async def save_encoding_profile(profile_name: str, settings: Dict):
    """Save an encoding profile."""
    if not config_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    success = config_manager.save_encoding_profile(profile_name, settings)
    return {
        "status": "success" if success else "error",
        "message": f"Profile '{profile_name}' saved" if success else "Failed to save profile"
    }


@app.delete("/api/encoding-profiles/{profile_name}", response_class=JSONResponse)
async def delete_encoding_profile(profile_name: str):
    """Delete an encoding profile."""
    if not config_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    success = config_manager.delete_encoding_profile(profile_name)
    return {
        "status": "success" if success else "error",
        "message": f"Profile '{profile_name}' deleted" if success else "Profile not found"
    }


@app.post("/api/server/restart", response_class=JSONResponse)
async def restart_server():
    """Request server restart (for development/settings changes)."""
    # In a production environment, this would signal the process manager
    # For now, we just acknowledge the request
    # The actual restart is handled by the process manager or by reloading the browser
    return {"status": "success", "message": "Server restart requested"}


@app.get("/api/media/scan", response_class=JSONResponse)
async def scan_media():
    """Scan media directory and analyze all files."""
    if not media_scanner or not config_manager:
        raise HTTPException(status_code=500, detail="Server not initialized")

    config = config_manager.load_config()
    media_path = Path(config.get("media_path", ""))

    if not media_path.exists():
        raise HTTPException(status_code=400, detail="Media path does not exist")

    # Perform scan (returns files with SCANNING status)
    media_files = await asyncio.to_thread(
        media_scanner.scan_directory,
        media_path
    )

    # CRITICAL: Analyze all files to populate metadata and set correct status
    # Without this, all files remain in SCANNING status
    max_workers = config.get("scan_threads", 8)
    await asyncio.to_thread(
        media_scanner.analyze_media_batch,
        media_files,
        max_workers=max_workers
    )

    # Convert to JSON-serializable format
    media_list = [
        {
            "path": str(file.path),
            "filename": file.filename,
            "status": file.status.value,
            "codec": file.codec,
            "resolution": file.resolution,
            "bitrate": file.bitrate,
            "fps": file.fps,
            "duration": file.duration,
            "file_size": file.file_size,
            "category": file.category.value,
            "is_show": file.is_show,
            "show_name": file.show_name,
            "season": file.season,
            "episode": file.episode,
            "issues": file.issues if hasattr(file, 'issues') else [],
            "warnings": file.warnings if hasattr(file, 'warnings') else [],
        }
        for file in media_files
    ]

    await connection_manager.broadcast({
        "type": "scan_complete",
        "count": len(media_list)
    })

    return {
        "status": "success",
        "files": media_list,
        "count": len(media_list)
    }


@app.get("/api/media", response_class=JSONResponse)
async def get_media_list():
    """Get cached media list."""
    if not media_scanner:
        raise HTTPException(status_code=500, detail="Server not initialized")

    media_files = media_scanner.media_files

    media_list = [
        {
            "path": str(file.path),
            "filename": file.filename,
            "status": file.status.value,
            "codec": file.codec,
            "resolution": file.resolution,
            "bitrate": file.bitrate,
            "fps": file.fps,
            "duration": file.duration,
            "file_size": file.file_size,
            "category": file.category.value,
            "is_show": file.is_show,
            "show_name": file.show_name,
            "season": file.season,
            "episode": file.episode,
            "issues": file.issues if hasattr(file, 'issues') else [],
            "warnings": file.warnings if hasattr(file, 'warnings') else [],
        }
        for file in media_files.values()
    ]

    return {
        "status": "success",
        "files": media_list,
        "count": len(media_list)
    }


@app.post("/api/encode/start", response_class=JSONResponse)
async def start_encoding(request: Request):
    """Start encoding selected files."""
    if not batch_encoder or not media_scanner:
        raise HTTPException(status_code=500, detail="Server not initialized")

    if batch_encoder.is_running:
        raise HTTPException(status_code=400, detail="Encoding already in progress")

    # Get files and settings from request body
    try:
        request_body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse request JSON: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON request: {str(e)}")

    # Get files and settings from request body
    files = request_body.get("files")
    encoding_settings = request_body.get("encoding_settings")

    # Get media files to encode
    media_to_encode = []
    if files:
        for file_path in files:
            if file_path in media_scanner.media_files:
                media_to_encode.append(media_scanner.media_files[file_path])
    else:
        # Encode all files that need encoding
        media_to_encode = [
            f for f in media_scanner.media_files.values()
            if f.status == MediaStatus.NEEDS_REENCODING
        ]

    if not media_to_encode:
        raise HTTPException(status_code=400, detail="No files to encode")

    # If encoding settings provided, update batch encoder's encoding_params
    # Also update the config sections for audio/subtitle settings
    if encoding_settings and isinstance(encoding_settings, dict):
        # Make a copy to avoid modifying the original
        settings_copy = encoding_settings.copy()

        # Extract audio and subtitle language settings to update config
        audio_filter_enabled = settings_copy.pop("audio_filter_enabled", False)
        audio_languages = settings_copy.pop("audio_languages", [])
        subtitle_filter_enabled = settings_copy.pop("subtitle_filter_enabled", False)
        subtitle_languages = settings_copy.pop("subtitle_languages", [])

        # Extract and store cleanup settings
        cleanup_settings["auto_remove_broken"] = settings_copy.pop("auto_remove_broken", False)
        cleanup_settings["auto_move_smaller"] = settings_copy.pop("auto_move_smaller", False)

        # Load current config, update audio/subtitle sections, then save
        config = config_manager.load_config()

        # Update audio config
        audio_config = config.get("audio", {})
        audio_config["language_filter_enabled"] = audio_filter_enabled
        audio_config["allowed_languages"] = audio_languages
        config["audio"] = audio_config

        # Update subtitle config
        subtitle_config = config.get("subtitles", {})
        subtitle_config["language_filter_enabled"] = subtitle_filter_enabled
        subtitle_config["allowed_languages"] = subtitle_languages
        config["subtitles"] = subtitle_config

        # Save the updated config
        config_manager.save_config(config)

        # Update batch encoder params with remaining encoding settings
        batch_encoder.encoding_params.update(settings_copy)

    # Check if encoding is already running
    if batch_encoder.is_running or encoding_state.is_running:
        raise HTTPException(status_code=409, detail="Encoding job already in progress")

    # Prepare and start encoding
    batch_encoder.prepare_jobs(media_to_encode)

    # Initialize server-side encoding state
    encoding_state.reset()
    encoding_state.is_running = True
    encoding_state.total_files = len(batch_encoder.jobs)
    encoding_state.start_time = datetime.now()

    # Run encoding in background thread
    asyncio.create_task(run_encoding_async())

    await connection_manager.broadcast({
        "type": "encoding_start",
        "job_count": len(batch_encoder.jobs)
    })

    return {
        "status": "success",
        "message": f"Started encoding {len(batch_encoder.jobs)} files"
    }


async def run_encoding_async():
    """Run encoding in async context."""
    if batch_encoder:
        await asyncio.to_thread(batch_encoder.start_encoding)
        encoding_state.is_running = False

        # Collect job statistics
        successful = sum(1 for job in batch_encoder.jobs if job.status == "complete")
        failed = sum(1 for job in batch_encoder.jobs if job.status == "failed")
        cancelled = sum(1 for job in batch_encoder.jobs if job.status == "cancelled")

        # Perform automatic cleanup based on settings
        cleanup_results = {
            "removed_broken": 0,
            "removed_expanded": 0,
            "moved_files": 0,
            "skipped": 0,
            "errors": []
        }

        if cleanup_settings.get("auto_remove_broken") or cleanup_settings.get("auto_move_smaller"):
            for job in batch_encoder.jobs:
                if job.status != "complete" or not job.output_path.exists():
                    continue

                try:
                    original_path = Path(job.media_info.path)
                    encoded_path = job.output_path

                    if not original_path.exists() or not encoded_path.exists():
                        continue

                    original_size = original_path.stat().st_size
                    encoded_size = encoded_path.stat().st_size

                    # Check if encoded file is larger (expanded) or same size
                    if encoded_size >= original_size:
                        if cleanup_settings.get("auto_remove_broken"):
                            # Remove expanded/broken encoded file
                            encoded_path.unlink()
                            cleanup_results["removed_expanded"] += 1
                            logger.info(f"Removed expanded file: {encoded_path.name} ({encoded_size:,} >= {original_size:,} bytes)")
                        else:
                            cleanup_results["skipped"] += 1
                    elif cleanup_settings.get("auto_move_smaller"):
                        # Encoded file is smaller - move to replace original
                        final_path = original_path.parent / encoded_path.name

                        # Delete original
                        original_path.unlink()

                        # Move encoded to final location
                        encoded_path.rename(final_path)

                        cleanup_results["moved_files"] += 1
                        logger.info(f"Replaced {original_path.name} with {encoded_path.name} (saved {original_size - encoded_size:,} bytes)")

                except Exception as e:
                    error_msg = f"{job.media_info.filename}: {str(e)}"
                    cleanup_results["errors"].append(error_msg)
                    logger.error(f"Auto-cleanup failed for {job.media_info.filename}: {e}", exc_info=True)

        # Collect job details for frontend
        jobs_data = []
        for job in batch_encoder.jobs:
            jobs_data.append({
                "status": job.status,
                "original_path": str(job.media_info.path),
                "output_path": str(job.output_path),
                "output_exists": job.output_path.exists(),
                "filename": job.media_info.filename
            })

        await connection_manager.broadcast({
            "type": "encoding_complete",
            "statistics": encoding_state.to_dict(),
            "successful": successful,
            "failed": failed,
            "cancelled": cancelled,
            "jobs": jobs_data,
            "cleanup_results": cleanup_results,
            "cleanup_settings": cleanup_settings
        })


@app.post("/api/encode/stop", response_class=JSONResponse)
async def stop_encoding():
    """Stop current encoding process."""
    if not batch_encoder:
        raise HTTPException(status_code=500, detail="Server not initialized")

    batch_encoder.should_stop = True
    encoding_state.is_running = False

    # Collect partial files and statistics
    partial_files = []
    for job in batch_encoder.jobs:
        if job.status == "cancelled" and job.output_path.exists():
            partial_files.append({
                "path": str(job.output_path),
                "filename": job.output_path.name
            })

    successful = sum(1 for job in batch_encoder.jobs if job.status == "complete")
    failed = sum(1 for job in batch_encoder.jobs if job.status == "failed")
    cancelled = sum(1 for job in batch_encoder.jobs if job.status == "cancelled")

    await connection_manager.broadcast({
        "type": "encoding_stopped",
        "statistics": encoding_state.to_dict(),
        "successful": successful,
        "failed": failed,
        "cancelled": cancelled,
        "partial_files": partial_files
    })

    return {"status": "success", "message": "Encoding stopped"}


@app.post("/api/encode/cleanup", response_class=JSONResponse)
async def cleanup_encoding():
    """
    Cleanup after encoding: delete originals and move encoded files to replace them.
    Only processes successfully completed jobs.
    """
    if not batch_encoder:
        raise HTTPException(status_code=500, detail="Server not initialized")

    successful_count = 0
    failed_count = 0
    skipped_count = 0
    errors = []

    for job in batch_encoder.jobs:
        if job.status != "complete" or not job.output_path.exists():
            continue

        try:
            original_path = Path(job.media_info.path)
            encoded_path = job.output_path

            # Check file sizes - if encoded is larger, keep original and delete encoded
            if original_path.exists() and encoded_path.exists():
                original_size = original_path.stat().st_size
                encoded_size = encoded_path.stat().st_size

                if encoded_size >= original_size:
                    # Encoding made file larger - keep original, delete encoded
                    encoded_path.unlink()
                    skipped_count += 1
                    logger.info(f"Kept original {original_path.name} (encoded was larger: {encoded_size:,} vs {original_size:,} bytes)")
                    continue

            # Determine final path (same location as original, with encoded name)
            final_path = original_path.parent / encoded_path.name

            # Delete original file
            if original_path.exists():
                original_path.unlink()

            # Move encoded file to final location
            encoded_path.rename(final_path)

            successful_count += 1
            logger.info(f"Replaced {original_path.name} with {encoded_path.name}")

        except Exception as e:
            failed_count += 1
            error_msg = f"{job.media_info.filename}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Cleanup failed for {job.media_info.filename}: {e}", exc_info=True)

    return {
        "status": "success" if failed_count == 0 else "partial",
        "successful": successful_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "errors": errors[:10]  # Return first 10 errors
    }


@app.post("/api/encode/cleanup-partial", response_class=JSONResponse)
async def cleanup_partial_files():
    """Delete partial files from cancelled encoding jobs."""
    if not batch_encoder:
        raise HTTPException(status_code=500, detail="Server not initialized")

    deleted_count = 0
    failed_count = 0
    errors = []

    for job in batch_encoder.jobs:
        if job.status == "cancelled" and job.output_path.exists():
            try:
                job.output_path.unlink()
                deleted_count += 1
                logger.info(f"Deleted partial file: {job.output_path}")
            except Exception as e:
                failed_count += 1
                errors.append(f"{job.output_path.name}: {str(e)}")
                logger.error(f"Failed to delete {job.output_path}: {e}")

    return {
        "status": "success" if failed_count == 0 else "partial",
        "deleted": deleted_count,
        "failed": failed_count,
        "errors": errors
    }


@app.get("/api/encode/status", response_class=JSONResponse)
async def get_encoding_status():
    """Get current encoding status with statistics."""
    if not batch_encoder:
        raise HTTPException(status_code=500, detail="Server not initialized")

    return {
        "is_running": batch_encoder.is_running or encoding_state.is_running,
        "job_count": len(batch_encoder.jobs),
        "statistics": encoding_state.to_dict(),
        "jobs": [
            {
                "media": job.media_info.filename,
                "status": job.status,
                "progress": job.progress,
                "error": job.error_message
            }
            for job in batch_encoder.jobs
        ]
    }


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for real-time log streaming."""
    await connection_manager.connect(websocket)

    # If encoding is already running, sync current state to new client for reconnection
    if batch_encoder and (batch_encoder.is_running or encoding_state.is_running):
        # Send encoding_start event
        await websocket.send_json({
            "type": "encoding_start",
            "job_count": encoding_state.total_files
        })

        # Send all previous log messages from this session
        for log_msg in encoding_state.log_history:
            await websocket.send_json(log_msg)

        # Send current statistics
        if encoding_state.file_statistics:
            await websocket.send_json({
                "type": "statistics_update",
                "statistics": encoding_state.to_dict()
            })

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back any received data
            await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)


def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Run the FastAPI server."""
    uvicorn.run(
        "web.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()
