#!/usr/bin/env python3
"""
Web Server for Open Media Manager
FastAPI-based web interface for remote library management.
"""

import asyncio
import json
import queue
from contextlib import asynccontextmanager
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
        disconnected = set()
        for connection in self.active_connections:
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
                print(f"Error processing broadcast queue: {e}")


# Global instances
config_manager: Optional[ConfigManager] = None
media_scanner: Optional[MediaScanner] = None
batch_encoder: Optional[BatchEncoder] = None
connection_manager = ConnectionManager()

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

        # Parse file_start to emit separate event
        if log_type == "file_start":
            parts = msg.split("|")
            if len(parts) == 2:
                data["type"] = "file_start"
                data["filename"] = Path(parts[0]).name
        
        connection_manager.queue_broadcast(data)

    def handle_progress(job_index, progress, status, speed, eta):
        if batch_encoder.jobs and job_index < len(batch_encoder.jobs):
            job = batch_encoder.jobs[job_index]
            connection_manager.queue_broadcast({
                "type": "file_progress",
                "job_index": job_index,
                "progress": progress,
                "fps": speed,
                "eta": eta,
                "filename": job.media_info.path.name
            })

    def handle_job_complete(job_index, success, message):
        if batch_encoder.jobs and job_index < len(batch_encoder.jobs):
            job = batch_encoder.jobs[job_index]
            original_size = job.media_info.file_size
            encoded_size = job.output_path.stat().st_size if job.output_path.exists() else 0

            connection_manager.queue_broadcast({
                "type": "file_complete",
                "job_index": job_index,
                "filename": job.media_info.path.name,
                "success": success,
                "original_size": original_size,
                "encoded_size": encoded_size,
                "message": message
            })

    # Set callbacks on batch encoder (these will be called from the encoding thread)
    batch_encoder.on_log = handle_log
    batch_encoder.on_progress = handle_progress
    batch_encoder.on_job_complete = handle_job_complete

    yield

    # Shutdown
    if batch_encoder and batch_encoder.is_running:
        batch_encoder.should_stop = True

    # Cancel broadcast task
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass


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
        print(f"[ERROR] Failed to parse request JSON: {e}")
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

    # Prepare and start encoding
    batch_encoder.prepare_jobs(media_to_encode)

    # Run encoding in background thread
    asyncio.create_task(run_encoding_async())

    connection_manager.queue_broadcast({
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
        connection_manager.queue_broadcast({
            "type": "encoding_complete"
        })


@app.post("/api/encode/stop", response_class=JSONResponse)
async def stop_encoding():
    """Stop current encoding process."""
    if not batch_encoder:
        raise HTTPException(status_code=500, detail="Server not initialized")

    batch_encoder.should_stop = True

    connection_manager.queue_broadcast({
        "type": "encoding_stopped"
    })

    return {"status": "success", "message": "Encoding stopped"}


@app.get("/api/encode/status", response_class=JSONResponse)
async def get_encoding_status():
    """Get current encoding status."""
    if not batch_encoder:
        raise HTTPException(status_code=500, detail="Server not initialized")

    return {
        "is_running": batch_encoder.is_running,
        "job_count": len(batch_encoder.jobs),
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
    
    # If encoding is already running, send current state to new client for reconnection
    if batch_encoder and batch_encoder.is_running:
        await websocket.send_json({
            "type": "encoding_start",
            "job_count": len(batch_encoder.jobs)
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
