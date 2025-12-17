<p align="center">
  <img src="assets/wain_logo.png" alt="Wain Logo" width="120" height="120">
</p>

<h1 align="center">Wain</h1>

<p align="center">
  <strong>A professional render queue manager for 3D artists</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.10.0-blue.svg" alt="Version">
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
- **Bidirectional Communication** — Configure settings in Wain, apply to engine, get accurate progress
- **Pause & Resume** — Stop and continue renders at any frame
- **Scene Probing** — Auto-detects resolution, cameras, frame range, and render settings
- **Selective Multi-Pass** — Render only the passes you need (Marmoset)
- **Resolution Scaling** — Quick presets for 25%, 50%, 100%, 150%, 200%
- **Native Desktop App** — Custom title bar with smooth Windows animations
- **Auto Dependencies** — First run installs everything automatically

---

## 🆕 What's New in v2.10.0

### Bidirectional Engine Communication Architecture

This release introduces a **completely redesigned communication system** between Wain and render engines:

**Settings Synchronization**
- Configure render settings in Wain → automatically applied to engine before render starts
- Edit settings and resubmit jobs with one click
- Schema-driven settings with validation

**Accurate Progress Tracking**
- Real-time progress that perfectly mirrors what the engine shows
- Frame-by-frame tracking with pass information
- Standardized `RenderProgress` structure across all engines

**Scalable Architecture**
- New `EngineInterface` abstract class defines communication contract
- `SettingDefinition` schema for UI generation
- Works identically across Vantage, Blender, and Marmoset

### Chaos Vantage Integration (v2.9.x → v2.10)

- **UI Automation** — Full control via pywinauto when CLI unavailable
- **Auto-launch Vantage** — Opens scene files automatically
- **Settings Application** — Resolution, frame range, output path via UI
- **Progress Monitoring** — Reads from "Rendering HQ Sequence" window
- **Frame Tracking** — Parses "Frame X/Y" and percentage indicators

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
- UI automation (CLI-free)
- HQ sequence rendering
- Real-time progress tracking
- V-Ray scene support (.vrscene)

</td>
</tr>
</table>

---

## 🏗️ Architecture (v2.10)

### Engine Interface

All engines implement the `EngineInterface` contract:

```python
class EngineInterface(ABC):
    @property
    def settings_schema(self) -> EngineSettingsSchema:
        """Define configurable settings with types, defaults, validation."""
    
    def read_scene_settings(self, file_path: str) -> Dict[str, Any]:
        """Read current settings from scene file."""
    
    def apply_settings(self, file_path: str, settings: Dict[str, Any]) -> bool:
        """Apply Wain settings to engine before render."""
    
    def get_progress(self) -> RenderProgress:
        """Get standardized progress information."""
    
    def pause_render(self) -> bool: ...
    def resume_render(self) -> bool: ...
    def stop_render(self) -> bool: ...
```

### Settings Schema

Settings are defined declaratively:

```python
SettingDefinition(
    id="samples",
    name="Render Samples",
    type=SettingType.INTEGER,
    category=SettingCategory.QUALITY,
    default=256,
    min_value=1,
    max_value=65536,
    description="Number of samples per pixel"
)
```

### Progress Structure

Unified progress across all engines:

```python
@dataclass
class RenderProgress:
    status: RenderStatus          # IDLE, RENDERING, PAUSED, COMPLETE, FAILED
    total_progress: float         # 0-100
    current_frame: int
    total_frames: int
    frame_progress: float         # Progress within current frame
    current_pass: str             # For multi-pass renders
    elapsed_seconds: float
    estimated_remaining: float
    message: str                  # Human-readable status
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
    │   ├── interface.py        # ★ Communication interface
    │   ├── blender.py
    │   ├── marmoset.py
    │   ├── vantage.py
    │   ├── vantage_comm.py     # ★ Vantage communicator
    │   ├── vantage_settings.py # ★ Vantage settings schema
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
<summary><strong>Vantage not responding to automation</strong></summary>

1. Ensure Vantage is installed in default location
2. Try running Wain as Administrator
3. Check if Vantage window title matches expected pattern
4. Install pywinauto: `pip install pywinauto`

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
| **2.10.0** | Bidirectional engine communication architecture |
| **2.9.6** | Vantage NoneType fix, robust window detection |
| **2.9.5** | Frame-by-frame progress tracking |
| **2.9.4** | Fixed progress bar jumping |
| **2.9.3** | Vantage UI automation complete |
| **2.8.x** | Resolution scaling, "Frame X%" display |

<details>
<summary>Full changelog</summary>

### v2.10.0 - Bidirectional Communication
- New `EngineInterface` abstract class for all engines
- `SettingDefinition` schema for UI generation
- `RenderProgress` standardized structure
- `VantageCommunicator` for settings/progress
- Settings validation and type checking

### v2.9.6
- Fixed NoneType crash after file dialog
- None-safety checks throughout
- Robust window detection
- Start button retry logic

### v2.9.5
- Frame-by-frame progress tracking
- `_get_detailed_progress()` parsing
- "Frame X/Y" and "Frame %" indicators

### v2.9.4
- Fixed progress bar jumping
- Detect "Rendering HQ Sequence" window
- Read "Total" percentage accurately

### v2.9.3
- Complete Vantage UI automation
- Auto-launch, menu navigation
- Resolution/frame range/output path setting
- Progress monitoring, cancel control

### v2.8.x
- Engine accent color standardization
- Resolution scale presets (25%–200%)
- Open output folder button
- Unified "Frame X%" progress display

</details>

---

## 📄 License

MIT License — Free for personal and commercial use.

---

## 🔗 Links

- **GitHub**: [https://github.com/Spencer-Sliffe/Wain](https://github.com/Spencer-Sliffe/Wain)

---

<p align="center">
  <em>Wain v2.10.0 — Bidirectional engine communication for professional rendering</em>
</p>
