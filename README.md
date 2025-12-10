# Wain - Render Queue Manager

A professional render queue manager for 3D artists. Supports Blender and Marmoset Toolbag with pause/resume capabilities.

## Quick Start

### Windows
1. **Double-click `Wain.bat`**
   - First run: Installs dependencies, then launches
   - After that: Launches the native desktop app

### Manual Launch
```bash
python -m wain              # Install & launch
Wain.bat --debug            # Run with console output for debugging
Wain.bat --install          # Force reinstall dependencies
```

## Requirements

- **Python 3.10 or higher** (3.10 - 3.14 tested)
  - Download from: https://www.python.org/downloads/
  - ⚠️ Check "Add Python to PATH" during installation

- **Windows 10/11** (recommended)

## Project Structure

```
wain/
├── Wain.bat                  # Windows launcher (double-click to start)
├── readme.md                 # This file
├── assets/                   # Logo and icon files
│   ├── wain_logo.png
│   ├── wain_icon.ico
│   ├── blender_logo.png
│   └── marmoset_logo.png
├── wain_launcher.pyw         # Splash screen launcher
└── wain/                     # Main package
    ├── __init__.py           # Package exports
    ├── __main__.py           # Entry point (python -m wain)
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
    │   └── dialogs.py        # Add job, settings dialogs
    └── utils/                # Utilities
        ├── __init__.py
        ├── bootstrap.py      # Dependency auto-installer
        └── file_dialogs.py   # Native file dialogs
```

## Features

- **Professional Splash Screen**: Animated loading screen with progress bar on startup
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
- **Selective Multi-Pass Rendering** (26 pass types)
  - Only renders the passes you select
  - Uses `renderCamera()` for precise pass control
  - No wasted renders or post-processing
- Turntable and animation sequences
- Automatic file organization by pass

## Multi-Pass Rendering (Marmoset)

Wain v2.4+ uses an optimized frame-by-frame approach:

1. **Select your passes** in the Add Job dialog
2. **Wain renders only what you need**: `Total renders = Frames × Passes`
   - Example: 30 frames × 3 passes = **90 renders** (not 875!)
3. **Progress shows exactly** what's happening: `Render 45/90 | Normals | Frame 15/30`
4. **Files organized automatically** into pass folders

This is as fast as rendering manually in Marmoset - no extra passes, no cleanup needed.

## Dependencies

Wain automatically installs these on first run:
- **NiceGUI** - Web-based UI framework
- **PyQt6** - Qt6 framework
- **PyQt6-WebEngine** - Browser engine for native window
- **qtpy** - Qt compatibility layer
- **pywebview** - Native desktop window wrapper
- **Pillow** - Image processing for icons

## Configuration

Settings are saved to `wain_config.json` in the working directory.

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
Wain.bat --debug
```

### Marmoset Passes Not Working
- Ensure pass names are lowercase in the API (Wain handles this automatically)
- Check the render log for specific error messages
- Some passes require specific scene setup (e.g., Material ID needs materials assigned)

## Development

To work on Wain:

```bash
# Clone/extract the package
cd wain

# Run in debug mode
python -m wain
```

The modular structure makes it easy to:
- Add new render engines (implement `engines/base.py` interface)
- Customize UI components (modify `ui/components.py`)
- Extend functionality (add to appropriate module)

## Version History

### v2.4.0 (Current)
- **Optimized Marmoset rendering**: Uses `renderCamera()` frame-by-frame
- **Accurate progress tracking**: Shows exact render count (frames × passes)
- **No wasted renders**: Only renders selected passes
- **Improved progress display**: Shows pass name, render count, and frame number

### v2.3.0
- Timeline-based frame control for Marmoset
- Fixed `frameCount` attribute error

### v2.2.0
- Modular package structure
- Multi-pass rendering support

## License

MIT License - Free for personal and commercial use.

---

*Wain v2.4.0 - A wagon that carries your renders*
