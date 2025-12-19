<p align="center">
  <img src="assets/wain_logo.png" alt="Wain Logo" width="120" height="120">
</p>

<h1 align="center">Wain</h1>

<p align="center">
  <strong>A professional render queue manager for 3D artists</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.15.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
</p>

<p align="center">
  <em>Queue, render, and manage your Blender, Marmoset Toolbag, and Chaos Vantage projects with ease.</em>
</p>

---

## ✨ Features

- **Multi-Engine Support** — Blender, Marmoset Toolbag, and Chaos Vantage in one unified queue
- **Full Settings Control** — Wain configures resolution, samples, output path automatically
- **Pause & Resume** — Stop and continue renders at any frame
- **Scene Probing** — Auto-detects resolution, cameras, frame range, and render settings
- **Selective Multi-Pass** — Render only the passes you need (Marmoset)
- **Resolution Scaling** — Quick presets for 25%, 50%, 100%, 150%, 200%
- **Native Desktop App** — Custom title bar with smooth Windows animations
- **Auto Dependencies** — First run installs everything automatically

---

## 🆕 What's New in v2.15.0

### Full HQ Settings Control for Vantage! 🎉

**BREAKTHROUGH: Wain now programmatically controls Vantage HQ render settings!**

Previously, users had to manually configure HQ settings in Vantage. Now Wain automatically applies job settings before launching Vantage:

| Setting | INI Key | Controlled by Wain |
|---------|---------|-------------------|
| **Resolution** | `snapshotResDefault=@Size(W H)` | ✅ Width & Height |
| **Samples** | `snapshotSamplesDefault=N` | ✅ Sample count |
| **Output Path** | `SaveImage=PATH` | ✅ Output folder |
| **Denoiser** | `snapshotDenoiseDefault` | ✅ On/Off |
| **Denoiser Type** | `snapshotDenoiserTypeDefault` | ✅ NVIDIA/OIDN |

**How it works:**
1. Wain reads your job settings (resolution, samples, output folder)
2. Writes them to `%APPDATA%\Chaos\Vantage\vantage.ini`
3. Creates a backup before any changes
4. Launches Vantage with your scene
5. Triggers render via UI automation
6. Monitors progress until completion

**New Module: `vantage_settings.py`**
```python
from wain.engines.vantage_settings import apply_render_settings

# Apply settings before launching Vantage
apply_render_settings(
    width=3840,
    height=2160,
    samples=512,
    output_path="C:/Renders/MyProject"
)
```

### Previous v2.14.x Features

**v2.14.4 - Maximum Speed**
- 90% faster action response
- Window polling: 0.1s (was 0.2s)
- Ctrl+R: 0.08s total
- Smart retry in background

**v2.14.3 - Fixed Delete on Paused Jobs**

**v2.14.2 - Resume Support**
- Detects existing progress window
- Clicks Resume for paused renders

**v2.14.1 - Native Pause/Abort**
- Pause clicks Vantage's native Pause button
- Delete = Abort + Close Vantage

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

### Additional for Vantage UI Automation
```bash
pip install pywinauto
```

---

## 🎨 Supported Engines

<table>
<tr>
<td width="33%">

### Blender

- Auto-detects versions 3.6 – 4.5
- Cycles, Eevee, Workbench
- GPU: OptiX, CUDA, HIP
- Denoising: OpenImageDenoise, OptiX
- Tiled rendering progress tracking

</td>
<td width="33%">

### Marmoset Toolbag

- Toolbag 4 and 5
- Ray Tracing, Hybrid, Raster
- **26 render passes** (selective)
- Turntable & animation
- Auto file organization by pass

</td>
<td width="33%">

### Chaos Vantage

- Vantage 2.x and 3.x
- **Full HQ settings control (v2.15.0!)**
- INI-based configuration
- UI automation + progress tracking
- V-Ray scene support (.vrscene)

</td>
</tr>
</table>

---

## 🏗️ Architecture (v2.15.0)

### Vantage Settings Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Wain Job      │────▶│  vantage.ini     │────▶│  Vantage App    │
│  (resolution,   │     │  (INI update)    │     │  (reads INI on  │
│   samples,      │     │                  │     │   startup)      │
│   output path)  │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Key INI Settings (vantage.ini)

Located at: `%APPDATA%\Chaos\Vantage\vantage.ini`

```ini
[Preferences]
snapshotResDefault=@Size(3840 2160)
snapshotSamplesDefault=512
snapshotDenoiseDefault=true
snapshotDenoiserTypeDefault=0
snapshotMoblurDefault=true
snapshotLightCacheDefault=true

[DialogLocations]
SaveImage=C:/Renders/Output
```

### VantageINIManager Class

```python
from wain.engines.vantage_settings import VantageINIManager

ini = VantageINIManager()

# Read current settings
settings = ini.read_hq_settings()
print(f"Current: {settings.width}x{settings.height}, {settings.samples} samples")

# Apply new settings (creates backup automatically)
ini.apply_job_settings(
    width=1920,
    height=1080,
    samples=256,
    output_path="D:/Renders"
)
```

---

## 📁 Project Structure

```
wain/
├── Wain.bat                    # Windows launcher
├── wain_launcher.pyw           # Splash screen
├── readme.md
├── assets/                     # Logos and icons
└── wain/                       # Main package
    ├── __main__.py             # Entry point
    ├── app.py                  # Queue management
    ├── config.py               # Theme & constants
    ├── models.py               # Data models
    ├── engines/                # Render engines
    │   ├── base.py             # Abstract base class
    │   ├── interface.py        # Communication interface
    │   ├── blender.py
    │   ├── marmoset.py
    │   ├── vantage.py          # ★ v2.15.0 INI integration
    │   ├── vantage_settings.py # ★ NEW: INI read/write
    │   └── registry.py
    ├── ui/                     # Interface
    │   ├── main.py
    │   ├── components.py
    │   └── dialogs.py
    └── utils/                  # Helpers
        ├── bootstrap.py
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
<summary><strong>Vantage settings not applying</strong></summary>

1. Check that `%APPDATA%\Chaos\Vantage\vantage.ini` exists
2. Close Vantage completely before running Wain
3. Run `Wain.bat --debug` to see if INI write succeeds
4. Check for backup files: `vantage.ini.wain_backup_*`

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
2. **Communicator class** implementing `EngineInterface` (optional but recommended)
3. **Settings schema** defining configurable options
4. **Accent color** in `config.py` → `ENGINE_COLORS`
5. **Logo** in `assets/` (optional, with icon fallback)

Example:
```python
# config.py
ENGINE_COLORS = {
    "blender": "#ea7600",    # Orange
    "marmoset": "#ef0343",   # Red
    "vantage": "#77b22a",    # Green
    "newengine": "#0066cc",  # Blue
}
```

---

## 📜 Version History

| Version | Highlights |
|---------|------------|
| **2.15.0** | **Full HQ settings control via vantage.ini!** |
| **2.14.4** | Maximum speed startup, smart retry |
| **2.14.3** | Fixed delete on paused jobs |
| **2.14.2** | Resume support for paused renders |
| **2.14.1** | Native pause/abort control |

<details>
<summary>Full changelog</summary>

### v2.15.0 - Full HQ Settings Control
- NEW: `VantageINIManager` class for reading/writing vantage.ini
- NEW: `VantageHQSettings` dataclass for settings structure
- Wain now applies resolution, samples, output path before launch
- Automatic backup creation before INI modifications
- Discovery: HQ settings stored in `[Preferences]` section
- Discovery: Output path in `[DialogLocations].SaveImage`

### v2.14.4 - Maximum Speed
- 90% faster action response
- Window polling: 0.1s intervals
- Ctrl+R: 0.08s total
- Smart retry in background

### v2.14.3
- Fixed delete on paused Vantage jobs
- Properly calls Abort and closes Vantage

### v2.14.2
- Resume support for paused renders
- Detects existing progress window
- Clicks Resume button automatically

### v2.14.1
- Native pause/abort control
- Pause keeps render window open
- Delete = Abort + Close

</details>

---

## 📄 License

MIT License — Free for personal and commercial use.

---

## 🔗 Links

- **GitHub**: [https://github.com/Spencer-Sliffe/Wain](https://github.com/Spencer-Sliffe/Wain)

---

<p align="center">
  <em>Wain v2.15.0 — Multi-engine render queue manager with full Vantage settings control</em>
</p>
