# Wain - Render Queue Manager

A professional render queue manager for 3D artists. Supports Blender and Marmoset Toolbag with pause/resume capabilities.

## Quick Start

### Windows
1. **Double-click `Wain.bat`**
   - First run: Installs dependencies, then launches
   - After that: Shows splash screen → launches app (no console window!)

### Manual Launch
```bash
python launch_wain.py          # Install & launch
python launch_wain.py --check  # Check dependencies only
python wain.py                 # Run directly (if deps installed)
```

## Requirements

- **Python 3.10 or higher** (3.10 - 3.14 tested)
  - Download from: https://www.python.org/downloads/
  - ⚠️ Check "Add Python to PATH" during installation

- **Windows 10/11** (recommended)

## Files

Keep all these files in the same folder:

```
Wain/
├── Wain.bat              # Windows launcher (double-click to start)
├── wain_launcher.pyw     # Splash screen launcher (no console)
├── launch_wain.py        # Installer/launcher script
├── wain.py               # Main application
├── wain_config.json      # Settings (created on first run)
└── assets/
    ├── wain_logo.png     # App logo
    ├── wain_icon.ico     # Taskbar icon (optional)
    ├── blender_logo.png  # Blender engine icon
    └── marmoset_logo.png # Marmoset Toolbag icon
```

## Features

- **Multi-Engine Support**: Blender, Marmoset Toolbag
- **Pause/Resume**: Stop and continue renders at any frame
- **Queue Management**: Queue multiple jobs, auto-process
- **Scene Probing**: Auto-detects settings from scene files
- **Native Desktop App**: Runs as a proper Windows application with custom title bar
- **Splash Screen**: Professional loading screen while app initializes
- **Smooth Animations**: Native Windows animations for minimize/maximize/restore
- **Browser Fallback**: Works in browser if native packages unavailable

## Supported Render Engines

### Blender
- Auto-detects installed versions (3.6 - 4.5)
- Supports Cycles, Eevee, Workbench
- GPU acceleration (OptiX, CUDA, HIP)
- Animation and still rendering

### Marmoset Toolbag
- Supports Toolbag 4 and 5
- Ray Tracing, Hybrid, Raster renderers
- Image and video output

## Dependencies

Wain automatically installs these on first run:
- **NiceGUI** - Web-based UI framework
- **PyQt6** - Qt6 framework
- **PyQt6-WebEngine** - Browser engine for native window
- **qtpy** - Qt compatibility layer
- **pywebview** - Native desktop window wrapper
- **Pillow** - Image processing for icons and splash screen

## Configuration

Settings are saved to `wain_config.json` in the same folder.

## Troubleshooting

### "Python is not installed"
1. Download Python from https://www.python.org/downloads/
2. Run the installer
3. ✅ Check **"Add Python to PATH"**
4. Restart and try again

### Package Installation Fails
Try installing manually:
```bash
pip install nicegui PyQt6 PyQt6-WebEngine qtpy Pillow
pip install pywebview --no-deps
pip install proxy-tools bottle
```

### App Won't Start
Check that all required files are present:
```bash
python launch_wain.py --check
```

### Window Appears Blank
This can happen if PyQt6 isn't properly installed:
```bash
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip
pip install PyQt6
```

### Splash Screen Shows but App Doesn't Load
Run in debug mode to see errors:
```bash
Wain.bat --debug
```

## License

MIT License - Free for personal and commercial use.

---

*Wain v1.0.0 - A wagon that carries your renders*
