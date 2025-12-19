<p align="center">
  <img src="assets/wain_logo.png" alt="Wain Logo" width="120" height="120">
</p>

<h1 align="center">Wain</h1>

<p align="center">
  <strong>A professional render queue manager for 3D artists</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.14.4-blue.svg" alt="Version">
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

## 🆕 What's New in v2.14.3

## 🆕 What's New in v2.14.4

### Maximum Speed Startup

**90% Faster Action Response**
- All delays reduced to absolute minimum
- Window polling: 0.1s (was 0.2s)
- Ctrl+R keypress: 0.08s total (was 0.25s)
- Ctrl+R retry: every 0.5s (was 2.0s in v2.13)
- Click-and-go: No verification loop - immediate monitoring

**Smart Retry in Background**
- Click Start immediately, start monitoring right away
- If no progress window after 3s, retry click automatically
- Up to 3 retry attempts while monitoring continues
- Fails gracefully after 30s with clear error

**Timing Summary**
| Action | v2.13 | v2.14.4 | Improvement |
|--------|-------|---------|-------------|
| Window polling | 0.5s | 0.1s | 5x faster |
| Ctrl+R total | 0.35s | 0.08s | 4x faster |
| Ctrl+R retry | 2.0s | 0.5s | 4x faster |
| Click verify | 0.5s+ | 0s | Eliminated |
| Progress poll | 0.5s | 0.3s | 40% faster |

### Previous v2.14.3 - Speed & Bug Fixes

**Faster UI Automation**
- Reduced all delays by 60-80%
- Button polling: 0.1s intervals (was 0.15s)
- Progress monitoring: 0.3s intervals (was 0.5s)

**Fixed Delete on Paused Jobs**
- Delete now works when Vantage render is paused
- Properly calls Abort and closes Vantage

### Previous v2.14.2 - Resume Support

**Smart Resume Detection**
- When starting a job, checks if progress window is already open
- Detects Resume button (Pause button changes to Resume when paused)
- Clicks Resume and goes straight to progress monitoring

**Seamless Workflow**
- Pause in Wain → Vantage pauses
- Play in Wain → Vantage resumes from where it left off
- No need to restart render from scratch

### Previous v2.14.1 - Native Pause/Abort Control

### Native Pause/Abort Control for Vantage

**Pause Button**
- Clicking Pause in Wain now clicks Vantage's native Pause button
- Keeps render window open - ready to resume
- Progress position is preserved

**Delete Job = Abort + Close**
- Deleting a job clicks Abort in Vantage
- Then automatically closes Vantage
- Handles "Save Changes?" dialogs automatically

**Fast Response**
- Direct button clicking via automation IDs
- No delays - action happens immediately

### Previous v2.14.0 - Accurate Progress Tracking

### Accurate Progress Tracking for Vantage 3.x

**Fixed Progress Dialog Detection**
- In Vantage 3.x, the progress dialog is a child window inside the main window
- Now properly searches within the Vantage window hierarchy
- Finds dialog by class name `LavinaRenderProgressDialog`

**Frame-Based Progress Parsing**
- Reads "HQ sequence frame X of Y" text to track render progress
- Captures elapsed and remaining time from Vantage
- Calculates total percentage from frame count

**Improved Status Display**
- Shows "Frame 5/301 (1%)" style progress
- Logs elapsed and remaining time when available
- Detects completion when all frames are rendered

### Previous v2.13.2 - Click Verification

Fixed issue where Start button click wasn't actually triggering the render:

**Verified Click**
- After clicking Start, checks if progress window appears
- If Start button still visible, click didn't work - retry automatically
- Falls back to `invoke()` method if `click_input()` fails
- Up to 3 click attempts before giving up

**Better Debugging**
- Logs button name and enabled state before clicking
- Reports which click method succeeded
- Clear error message if all attempts fail

### Previous v2.13.1 - Speed Optimizations

**Eliminated Fixed Delays**
- Removed 4-second scene load wait - no longer waits for scene to fully load
- Ctrl+R sent immediately when Vantage window appears
- Start button clicked as soon as it's detected

**Aggressive Polling**
- 0.2s polling intervals for window detection (was 0.5s)
- 0.15s polling intervals for Start button (was fixed delays)
- Automatic Ctrl+R retry every 2 seconds if button not found

**Result**: Renders start within seconds of Vantage window appearing, not 5-10 seconds later.

### Previous v2.13.0 Features

**Multi-Level Button Detection**
- Four-tier button search strategy (direct descendants, iterative depth, automation IDs, partial match)
- Debug output listing all available buttons when detection fails

**Dual Keyboard Input Methods**
- Primary: pywinauto keyboard module
- Fallback: Native Windows keybd_event API for Ctrl+R

**HTTP API Foundation**
- Live Link port detection (20701)
- JSON command framework for future API integration

### Architecture Notes

HQ render settings (output path, resolution, frame range) are **not stored in .vantage files**.
Users must configure these settings once in Vantage's HQ Render panel — Wain then reuses them.
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
| **2.10.3** | Bidirectional engine communication architecture |
| **2.9.6** | Vantage NoneType fix, robust window detection |
| **2.9.5** | Frame-by-frame progress tracking |
| **2.9.4** | Fixed progress bar jumping |
| **2.9.3** | Vantage UI automation complete |
| **2.8.x** | Resolution scaling, "Frame X%" display |

<details>
<summary>Full changelog</summary>

### v2.10.3 - Bidirectional Communication
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
  <em>Wain v2.13.2 — Multi-engine render queue manager with verified automation</em>
</p>
