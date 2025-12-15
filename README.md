<p align="center">
  <img src="assets/wain_logo.png" alt="Wain Logo" width="120" height="120">
</p>

<h1 align="center">Wain</h1>

<p align="center">
  <strong>A professional render queue manager for 3D artists</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.8.3-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
</p>

<p align="center">
  <em>Queue, render, and manage your Blender and Marmoset Toolbag projects with ease.</em>
</p>

---

## ✨ Features

- **Multi-Engine Support** — Blender and Marmoset Toolbag in one unified queue
- **Pause & Resume** — Stop and continue renders at any frame
- **Scene Probing** — Auto-detects resolution, cameras, frame range, and render settings
- **Selective Multi-Pass** — Render only the passes you need (Marmoset)
- **Resolution Scaling** — Quick presets for 25%, 50%, 100%, 150%, 200%
- **Native Desktop App** — Custom title bar with smooth Windows animations
- **Auto Dependencies** — First run installs everything automatically

---

## 🚀 Quick Start

### Windows

**Double-click `Wain.bat`** — that's it!

- First run installs dependencies automatically
- Subsequent runs launch instantly with a splash screen

### Manual Launch

```bash
python -m wain              # Install & launch
Wain.bat --debug            # Debug mode with console output
Wain.bat --install          # Force reinstall dependencies
```

---

## 📋 Requirements

- **Python 3.10+** (tested through 3.14)
  - Download: https://www.python.org/downloads/
  - ⚠️ Check **"Add Python to PATH"** during installation
- **Windows 10/11**

---

## 🎨 Supported Engines

<table>
<tr>
<td width="50%">

### Blender

- Auto-detects versions 3.6 – 4.5
- Cycles, Eevee, Workbench
- GPU: OptiX, CUDA, HIP
- Denoising: OpenImageDenoise, OptiX
- Tiled rendering progress tracking

</td>
<td width="50%">

### Marmoset Toolbag

- Toolbag 4 and 5
- Ray Tracing, Hybrid, Raster
- **26 render passes** (selective)
- Turntable & animation
- Auto file organization by pass

</td>
</tr>
</table>

---

## 📁 Project Structure

```
wain/
├── Wain.bat                # Windows launcher
├── wain_launcher.pyw       # Splash screen
├── readme.md
├── assets/                 # Logos and icons
└── wain/                   # Main package
    ├── __main__.py         # Entry point
    ├── app.py              # Queue management
    ├── config.py           # Theme & constants
    ├── models.py           # Data models
    ├── engines/            # Render engines
    │   ├── base.py         # Abstract base class
    │   ├── blender.py
    │   ├── marmoset.py
    │   └── registry.py
    ├── ui/                 # Interface
    │   ├── main.py
    │   ├── components.py
    │   └── dialogs.py
    └── utils/              # Helpers
        ├── bootstrap.py    # Auto-installer
        └── file_dialogs.py
```

---

## 🔧 Configuration

Settings persist to `wain_config.json` in the working directory, including:
- Render queue and job states
- Pause/resume progress
- Engine-specific settings

---

## 🛠️ Troubleshooting

<details>
<summary><strong>"Python is not installed"</strong></summary>

1. Download Python from https://www.python.org/downloads/
2. Run installer with ✅ **"Add Python to PATH"** checked
3. Restart terminal and try again

</details>

<details>
<summary><strong>Package Installation Fails</strong></summary>

Install manually:
```bash
pip install nicegui PyQt6 PyQt6-WebEngine qtpy Pillow
pip install pywebview --no-deps
pip install proxy-tools bottle
```

</details>

<details>
<summary><strong>App Won't Start</strong></summary>

Run in debug mode to see errors:
```bash
Wain.bat --debug
```

</details>

---

## 🧩 Adding New Engines

Each engine requires:

1. **Engine class** in `wain/engines/` implementing `RenderEngine`
2. **Accent color** in `config.py` → `ENGINE_COLORS`
3. **Logo** in `assets/` (optional, with icon fallback)
4. **CSS classes** in `ui/main.py` for progress bars

Example:
```python
# config.py
ENGINE_COLORS = {
    "blender": "#ea7600",    # Orange
    "marmoset": "#ef0343",   # Red
    "cinema4d": "#0066cc",   # Blue
}
```

---

## 📜 Version History

| Version | Highlights |
|---------|------------|
| **2.8.3** | Engine accent color standardization |
| **2.8.2** | Resolution scale presets (25%–200%) |
| **2.8.1** | Open output folder button |
| **2.8.0** | Unified "Frame X%" progress display |
| **2.7.x** | Unicode fixes, logo system, tiled rendering |
| **2.5.0** | Optimized Marmoset multi-pass rendering |

<details>
<summary>Full changelog</summary>

### v2.8.3
- Engine accent colors applied consistently across all UI elements
- Blender: Orange (#ea7600), Marmoset: Red (#ef0343)
- Default fallback changed to neutral gray

### v2.8.2
- Resolution scale presets: 25%, 50%, 100%, 150%, 200%
- Shows effective resolution in real-time

### v2.8.1
- Open output folder button on job cards

### v2.8.0
- All engines show "Frame X%" for current frame progress
- Marmoset tracks pass-within-frame completion

### v2.7.9
- Renamed project from "Wane" to "Wain"

### v2.7.0 – v2.7.8
- Fixed denoiser case mismatch crash
- Unicode encoding fixes for addon output
- Tiled rendering progress display
- Logo fallback system

### v2.5.0
- Optimized Marmoset rendering with `renderCamera()`
- Selective pass rendering (no wasted renders)

</details>

---

## 📄 License

MIT License — Free for personal and commercial use.

---

<p align="center">
  <em>Wain v2.8.3 — Something carry your renders</em>
</p>
