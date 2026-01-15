# Web Server Documentation Index

Welcome! Here's your guide to the new Open Media Manager web server.

## 🚀 Getting Started (Start Here!)

**[QUICKSTART_WEB.md](QUICKSTART_WEB.md)** - Get the web server running in 5 minutes
- Installation
- Basic commands
- First-time setup
- Quick tips

## 📚 Complete Documentation

### User Guides
1. **[WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md)** - Comprehensive user guide
   - Feature overview
   - Detailed installation
   - Web interface walkthrough
   - API reference
   - Security considerations
   - Troubleshooting & FAQ

2. **[WEB_SERVER_COMPLETE_OVERVIEW.md](WEB_SERVER_COMPLETE_OVERVIEW.md)** - High-level summary
   - What was added
   - New capabilities
   - Quick reference
   - How to use

## 🏃 Quick Commands

### Start Web Server
```bash
python main.py
```

### Open in Browser
```
http://localhost:8000/
```

### Custom Port
```bash
python main.py --port 8080
```

### Development Mode (Auto-reload)
```bash
python main.py --reload
```

### Start Original GUI
```bash
python main.py
```

## 📁 Project Structure

```
OpenMediaManager/
├── README.md                           # Main project README
├── QUICKSTART_WEB.md                   # Quick start guide (START HERE!)
├── WEB_SERVER_GUIDE.md                 # Complete documentation
├── WEB_SERVER_IMPLEMENTATION.md        # Technical details
├── WEB_SERVER_COMPLETE_OVERVIEW.md     # High-level overview
├── WEB_SERVER_DOCUMENTATION_INDEX.md   # This file
│
├── main.py                             # Entry point (GUI or web server)
├── server.py                           # FastAPI web server ⭐ NEW
├── config_manager.py                   # Configuration management
├── media_scanner.py                    # Media scanning
├── batch_encoder.py                    # Batch encoding
├── constants.py                        # Default settings
├── gui_components.py                   # PyQt6 GUI components
│
├── requirements.txt                    # Python dependencies (UPDATED)
│
├── templates/
│   └── dashboard.html                  # Main web interface ⭐ NEW
│
└── static/
    ├── css/
    │   └── styles.css                  # Responsive styling ⭐ NEW
    └── js/
        ├── utils.js                    # Utility functions ⭐ NEW
        ├── dialogs.js                  # Dialog components ⭐ NEW
        └── main.js                     # App logic ⭐ NEW
```

## 🎯 Key Features

### ✨ What's New
- 🌐 Web-based interface (FastAPI + Uvicorn)
- 📱 Responsive design (mobile, tablet, desktop)
- 🔄 Real-time updates (WebSocket)
- 💬 Modal dialogs (no popups)
- 🎨 Modern, clean UI
- 🚀 Fast performance
- 🔒 Secure by default (localhost only)

### 🎬 Functionality
- Scan media directories remotely
- View detailed file information
- Filter and search files
- Select multiple files for encoding
- Real-time encoding progress
- Configure settings via web interface
- Start/stop encoding remotely

## 📋 Feature Comparison

| Feature           | GUI | Web Server |
| ----------------- | --- | ---------- |
| Local access      | ✅   | ✅          |
| Remote access     | ❌   | ✅          |
| Mobile friendly   | ❌   | ✅          |
| No dependencies   | ❌   | ✅          |
| PyQt6 required    | ✅   | ❌          |
| Responsive layout | ❌   | ✅          |

## 🔧 Technology Stack

**Backend:**
- FastAPI (modern async framework)
- Uvicorn (ASGI server)
- Jinja2 (templating)
- WebSocket (real-time updates)

**Frontend:**
- HTML5 (semantic markup)
- CSS3 (flexbox, grid, media queries)
- Vanilla JavaScript (no frameworks)
- WebSocket API (real-time updates)

## 📱 Responsive Design

The interface automatically adapts:
- **Desktop (≥1024px)**: Horizontal split (side-by-side)
- **Tablet (768-1024px)**: Horizontal split (adjusted)
- **Mobile (<768px)**: Vertical split (stacked)

## 🛡️ Security

**Default Configuration:**
- Listens on 127.0.0.1 (localhost only)
- No authentication (local access only)
- No HTTPS (add reverse proxy for network)

**For Network Access:**
- Use HTTPS (reverse proxy with SSL)
- Add authentication middleware
- Implement firewall rules

See [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md) for security details.

## ❓ Need Help?

### Quick Questions?
→ Check [QUICKSTART_WEB.md](QUICKSTART_WEB.md)

### Looking for Details?
→ See [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md)

### Need Technical Info?
→ Read [WEB_SERVER_IMPLEMENTATION.md](WEB_SERVER_IMPLEMENTATION.md)

### Troubleshooting?
→ See FAQ in [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md)

## 📝 File Guide

### To Learn About...
- **Getting started** → [QUICKSTART_WEB.md](QUICKSTART_WEB.md)
- **How to use the interface** → [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md)
- **Architecture & design** → [WEB_SERVER_IMPLEMENTATION.md](WEB_SERVER_IMPLEMENTATION.md)
- **Feature overview** → [WEB_SERVER_COMPLETE_OVERVIEW.md](WEB_SERVER_COMPLETE_OVERVIEW.md)
- **API documentation** → [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md#api-reference)
- **Troubleshooting** → [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md#troubleshooting)
- **Security setup** → [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md#security-considerations)
- **Deployment** → [WEB_SERVER_IMPLEMENTATION.md](WEB_SERVER_IMPLEMENTATION.md#deployment-options)

## 🎓 Learning Path

**For Users:**
1. [QUICKSTART_WEB.md](QUICKSTART_WEB.md) - Get it running
2. [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md) - Learn the interface
3. [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md#api-reference) - Explore the API

**For Developers:**
1. [WEB_SERVER_IMPLEMENTATION.md](WEB_SERVER_IMPLEMENTATION.md) - Understand architecture
2. [server.py](server.py) - Review backend code
3. [static/js/main.js](static/js/main.js) - Review frontend code

**For Operators:**
1. [QUICKSTART_WEB.md](QUICKSTART_WEB.md) - Get it running
2. [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md#security-considerations) - Security setup
3. [WEB_SERVER_IMPLEMENTATION.md](WEB_SERVER_IMPLEMENTATION.md#deployment-options) - Deployment

## 💡 Tips

- **First time?** Start with [QUICKSTART_WEB.md](QUICKSTART_WEB.md)
- **Need remote access?** Use `--host 0.0.0.0` and set up reverse proxy
- **Want auto-reload?** Use `--reload` flag for development
- **Having issues?** Check the Troubleshooting section in [WEB_SERVER_GUIDE.md](WEB_SERVER_GUIDE.md)

## 🚀 Next Steps

1. **Install**: `pip install -r requirements.txt`
2. **Start**: `python main.py`
3. **Open**: http://localhost:8000/
4. **Configure**: Click Settings and set your media path
5. **Scan**: Click Scan Media
6. **Enjoy**: Select and encode your media!

## 📞 Support

For detailed help, refer to the specific documentation file mentioned above.

---

**Happy encoding!** 🎬✨
