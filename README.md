# Wane - Render Queue Manager

A professional render queue manager for 3D artists. Supports Blender and Marmoset Toolbag with pause/resume capabilities.

## Quick Start

### Windows
1. **Double-click `Wane.bat`**
   - First run: Installs dependencies, then launches
   - After that: Launches the native desktop app

### Manual Launch
```bash
python -m wane              # Install & launch
Wane.bat --debug            # Run with console output for debugging
Wane.bat --install          # Force reinstall dependencies
```

## Requirements

- **Python 3.10 or higher** (3.10 - 3.14 tested)
  - Download from: https://www.python.org/downloads/
  - ⚠️ Check "Add Python to PATH" during installation

- **Windows 10/11** (recommended)

## Project Structure

This is the modular version of Wane, split into organized packages:

```
wane_modular/
├── Wane.bat                  # Windows launcher (double-click to start)
├── assets/                   # Logo and icon files
│   ├── wane_logo.png
│   ├── wane_icon.ico
│   ├── blender_logo.png
│   └── marmoset_logo.png
└── wane/                     # Main package
    ├── __init__.py           # Package exports
    ├── __main__.py           # Entry point (python -m wane)
    ├── app.py                # RenderApp class and state management
    ├── config.py             # Theme, colors, constants
    ├── models.py             # RenderJob, AppSettings dataclasses
    ├── engines/              # Render engine implementations
    │   ├── __init__.py
    │   ├── base.py           # RenderEngine abstract base class
    │   ├── blender.py        # Blender integration
    │   ├── marmoset.py       # Marmoset Toolbag integration
    │   └── registry.py       # Engine registry
    ├── ui/                   # User interface
    │   ├── __init__.py
    │   ├── main.py           # Main page layout
    │   ├── components.py     # Stat cards, job cards
    │   ├── dialogs.py        # Add job, settings dialogs
    │   └── styles.py         # CSS/JS styles (reference)
    └── utils/                # Utilities
        ├── __init__.py
        ├── bootstrap.py      # Dependency auto-installer
        └── file_dialogs.py   # Native file dialogs
```

## Features

- **Multi-Engine Support**: Blender, Marmoset Toolbag
- **Pause/Resume**: Stop and continue renders at any frame
- **Queue Management**: Queue multiple jobs, auto-process
- **Scene Probing**: Auto-detects settings from scene files
- **Native Desktop App**: Runs as a proper Windows application with custom title bar
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
- Multi-pass rendering (26 pass types)
- Turntable and animation sequences
- Automatic file organization

## Dependencies

Wane automatically installs these on first run:
- **NiceGUI** - Web-based UI framework
- **PyQt6** - Qt6 framework
- **PyQt6-WebEngine** - Browser engine for native window
- **qtpy** - Qt compatibility layer
- **pywebview** - Native desktop window wrapper
- **Pillow** - Image processing for icons and splash screen

## Configuration

Settings are saved to `wane_config.json` in the working directory.

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
Run in debug mode to see errors:
```bash
Wane.bat --debug
```

## Development

To work on Wane:

```bash
# Clone/extract the package
cd wane_modular

# Run in debug mode
python -m wane
```

The modular structure makes it easy to:
- Add new render engines (implement `engines/base.py` interface)
- Customize UI components (modify `ui/components.py`)
- Extend functionality (add to appropriate module)

## License

MIT License - Free for personal and commercial use.

---

*Wane v1.0.0 - A wagon that carries your renders*
