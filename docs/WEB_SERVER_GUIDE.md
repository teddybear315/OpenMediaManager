# Open Media Manager - Web Server Guide

## Overview

Open Media Manager now includes a FastAPI-based web server that allows you to manage your media library remotely. The web interface provides the same functionality as the PyQt6 GUI with a responsive design that works on desktop, tablet, and mobile devices.

## Features

### Core Features
- **Remote Library Management**: Access your media library from any device on your network
- **Real-time Updates**: WebSocket-based live log streaming for encoding progress
- **Responsive Design**: Optimized layouts for desktop, tablet, and mobile devices
- **Input Dialogs**: In-page modal dialogs for settings and confirmations (no external popups)
- **Responsive Log Splitting**:
  - **Desktop**: Horizontal split (side-by-side layout)
  - **Mobile/Tablet**: Vertical split (stacked layout)

### Media Management
- Scan media directories for encoding compliance
- View detailed file information (resolution, codec, bitrate, duration, file size)
- Filter by status or search by filename
- Select multiple files for batch encoding
- Monitor encoding progress in real-time

### Configuration
- Web-based settings dialog (no Python knowledge required)
- Configure encoding parameters (codec, GPU, animation tuning)
- Set quality standards for different resolutions
- Configure encoding bitrate limits

## Installation

### Install Dependencies
```bash
pip install -r requirements.txt
```

This installs the following new packages:
- `fastapi>=0.104.0`
- `uvicorn>=0.24.0`
- `jinja2>=3.1.0`
- `python-multipart>=0.0.6`
- `websockets>=11.0.0`

## Usage

### Running the Web Server

**Default (localhost):**
```bash
python main.py
```

**Custom Host and Port:**
```bash
python main.py --host 0.0.0.0 --port 8080
```

**Development Mode (with auto-reload):**
```bash
python main.py --reload
```

### Accessing the Interface

Once the server is running, open your browser and navigate to:
```
http://localhost:8000/
```

If you specified a custom host/port:
```
http://<host>:<port>/
```

### Command-line Options

```
--web              Run web server instead of GUI (default: False)
--host HOST        Web server host (default: 127.0.0.1)
--port PORT        Web server port (default: 8000)
--reload           Enable auto-reload for development (default: False)
```

## Web Interface Guide

### Main Dashboard

The web interface is divided into two main sections:

#### Media Library Section
- **Scan Button**: Scan your media directory for files
- **Search**: Filter files by filename
- **Status Filter**: Show only files with specific status:
  - ✅ Compliant (meets quality standards)
  - ⚠️ Needs Re-encoding (below standard or wrong codec)
  - ℹ️ Below Standard (bitrate too low)
  - 🔍 Scanning (currently being analyzed)
  - ⛔ Error (failed to analyze)
- **Select/Deselect**: Choose files for encoding
- **Media Table**: Shows detailed information about each file

#### Encoding Log Section
- **Live Updates**: Real-time encoding progress via WebSocket
- **Clear Log**: Clear the log history
- **Stop Encoding**: Cancel current encoding process

### Settings Dialog

Access settings via the "Settings" button in the header.

**Sections:**
- **Media Path**: Location of your media library
- **Encoding Settings**:
  - Codec (x265/AV1)
  - GPU acceleration (NVENC)
  - Animation tuning
  - Constant Quality (CQ) value
  - Encoding level
  - Thread count
- **Quality Standards**: Bitrate ranges for compliance checking
- **Encoding Bitrate Limits**: Optional bitrate constraints during encoding

### Responsive Layout

The web interface automatically adapts to different screen sizes:

**Desktop (≥ 1024px)**
- Horizontal split with media table on top, log below
- Full-width controls and detailed view

**Tablet (768px - 1024px)**
- Horizontal split with reduced font sizes
- Touch-friendly button sizing

**Mobile (< 768px)**
- Vertical split (media table, then log)
- Single-column layout
- Stack all controls
- Auto-hiding columns in table for readability

## API Reference

The web server exposes RESTful endpoints for programmatic access:

### Media Endpoints

**Get Configuration**
```
GET /api/config
```

**Update Configuration**
```
POST /api/config
Body: JSON configuration object
```

**Get Cached Media List**
```
GET /api/media
```
Response:
```json
{
  "status": "success",
  "files": [...],
  "count": 42
}
```

**Scan Media Directory**
```
GET /api/media/scan
```
Performs a full directory scan and returns results.

### Encoding Endpoints

**Start Encoding**
```
POST /api/encode/start
Body: JSON with optional "files" array of paths
```

**Stop Encoding**
```
POST /api/encode/stop
```

**Get Encoding Status**
```
GET /api/encode/status
```
Response:
```json
{
  "is_running": true,
  "job_count": 5,
  "jobs": [
    {
      "media": "filename.mkv",
      "status": "encoding",
      "progress": 45.5,
      "error": ""
    }
  ]
}
```

### WebSocket

**Connect to Log Stream**
```
WebSocket /ws/logs
```

Real-time log messages include:
- `type`: "log", "encoding_start", "encoding_complete", "encoding_stopped", "scan_complete"
- `message`: Log message text
- `log_type`: "info", "success", "warning", "error"
- `color`: Hex color code
- `timestamp`: ISO timestamp

## Architecture

### Directory Structure
```
OpenMediaManager/
├── main.py                 # Entry point (GUI or web server)
├── server.py              # FastAPI application
├── config_manager.py      # Configuration management
├── media_scanner.py       # Media file scanning
├── batch_encoder.py       # Batch encoding logic
├── constants.py           # Application constants
├── requirements.txt       # Python dependencies
├── templates/
│   └── dashboard.html     # Main web interface template
└── static/
    ├── css/
    │   └── styles.css     # Responsive styling
    └── js/
        ├── utils.js       # Utility functions and API client
        ├── dialogs.js     # Dialog components
        └── main.js        # Application logic
```

### Technology Stack
- **Backend**: FastAPI + Uvicorn
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Templating**: Jinja2
- **Real-time Communication**: WebSocket

## Security Considerations

⚠️ **WARNING**: The default configuration binds to `127.0.0.1` (localhost only).

If exposing to a network:
1. **Use HTTPS**: Place behind a reverse proxy (nginx, Apache) with SSL
2. **Authentication**: Add authentication middleware
3. **Network Security**: Use firewall rules to restrict access
4. **Validation**: All inputs are validated server-side

Example nginx reverse proxy configuration:
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Troubleshooting

### Server Won't Start
```
Error: Address already in use
```
Solution: Use a different port with `--port` argument

### WebSocket Connection Failed
- Check firewall settings
- Verify server is running and accessible
- Check browser console for CORS errors
- Ensure WebSocket is not being blocked by proxy

### Settings Not Saving
- Verify configuration directory exists: `~/.config/openmediamanager/`
- Check file permissions
- Review server logs for errors

### Media Scan Takes Too Long
- Check `scan_threads` setting in config
- Large directories may take time
- Server continues working; log updates show progress

## Development

### Running in Development Mode
```bash
python main.py --reload
```

This enables:
- Auto-reload on file changes
- Debug mode
- Verbose logging

### Browser DevTools
1. Open DevTools (F12)
2. Check Console for JavaScript errors
3. Check Network tab for API calls
4. Monitor WebSocket in Network tab

### Modifying Templates and Styles
1. Edit files in `templates/` and `static/`
2. Changes are reflected immediately in browser
3. Hard refresh (Ctrl+Shift+R) if caching issues occur

## Comparison: GUI vs Web Server

| Feature                       | GUI | Web Server    |
| ----------------------------- | --- | ------------- |
| Local machine access          | ✅   | ✅             |
| Remote access                 | ❌   | ✅             |
| Responsive mobile layout      | ❌   | ✅             |
| Modal dialogs                 | ✅   | ✅             |
| Real-time updates             | ✅   | ✅ (WebSocket) |
| System integration            | ✅   | ❌             |
| Requires Python GUI libs      | ✅   | ❌             |
| Multi-device simultaneous use | ❌   | ✅             |

## FAQ

**Q: Can I run both GUI and web server simultaneously?**
A: Yes, but they will share the same configuration and encode queue. Not recommended for concurrent use.

**Q: Does the web server require X11/display?**
A: No, it runs headless and works over SSH.

**Q: Can I access the web server from another computer?**
A: Yes, use `--host 0.0.0.0` but implement security measures (HTTPS, authentication, firewall).

**Q: How do I make the web server persistent?**
A: Use a process manager like systemd, supervisor, or Docker.

## Contributing

For bug reports, feature requests, or contributions, please refer to the main project repository.

## License

See LICENSE file in the project root.
