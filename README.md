<p align="center">
  <img src="assets/wain_logo.png" alt="Wain Logo" width="120" height="120">
</p>

<h1 align="center">Wain</h1>

<p align="center">
  <strong>A professional render queue manager for 3D artists</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.20.0-blue.svg" alt="Version">
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
- **Per-Job Settings** — Configure resolution, samples, and denoiser for each Vantage job
- **Full Scene Probing** — Reads cameras, frame count, and settings from `.vantage` files
- **Pause & Resume** — Stop and continue renders at any frame
- **Selective Multi-Pass** — Render only the passes you need (Marmoset)
- **Resolution Scaling** — Quick presets for 25%, 50%, 100%, 150%, 200%
- **Native Desktop App** — Custom title bar with smooth Windows animations
- **Auto Dependencies** — First run installs everything automatically

---

## 🆕 What's New in v2.19

### Visual Redesign & GPU-Accelerated UI

- **New visual identity** — wagon logo, header brand group with version chip
- **Engine accent bars** — job cards carry their engine's color on the left edge (Blender orange, Marmoset red, Vantage green)
- **Gradient progress bars** — engine-colored gradients with subtle glows; status-colored when queued/paused/completed/failed
- **Stat icon chips** — color-coded queue stats (rendering/queued/completed/failed)
- **GPU compositing enabled by default** — smooth UI; pass `--software-ui` to fall back to CPU rendering
- **Fixes** — no more white flash when opening menus, splash screen shows the logo in true colors
- The UI is designed in a companion Figma file and iterated there first

### Previous v2.16.0 — Marmoset Multi-Pass Rendering & Camera Detection

- **26 Render Passes** — Select individual passes (Beauty, Normals, AO, Albedo, etc.) from categorized checkboxes
- **Scene Probing** — Automatically detects cameras, passes, and settings from `.tbscene` files
- **Camera Selection** — Choose which camera to render from detected scene cameras
- **Per-Pass Output** — Each pass saves as `prefix_passname.ext` (e.g., `render_normals.png`)
- **Progress Tracking** — Shows current pass name and number during multi-pass renders

### Previous v2.15.50

### UI Readiness Detection - Reliable Scene Loading

**The Problem:**
- On large scenes, Live Link TCP port (20701) connects before UI is fully responsive
- Wain was sending Ctrl+R commands that weren't being executed
- Caused unpredictable startup behavior

**The Solution: UI Readiness Detection**

Instead of checking TCP port, Wain now watches for actual UI elements:

1. **Panel Detection** - Watches for "Lights", "Scene", "Camera", "Environment" text labels
2. **Button Stability** - Tracks button count and waits for 3 seconds of stability
3. **Command Verification** - Confirms Start button appeared after Ctrl+R

**What Changed:**
- NO LONGER modifies `vantage.ini` - completely safe for your config
- Waits for Vantage UI to fully initialize before sending commands
- Verifies commands actually executed by checking for expected UI changes
- More reliable on large, complex scenes

**Expected Log Output:**
```
Waiting for Vantage to load: MyScene.vantage
Detecting UI readiness (watching for Lights panel)...
Vantage window appeared (2.1s)
========================================
=== UI READY (panels detected) ===
Panels found: {'Lights', 'Scene'}
Buttons stable: 47 for 3.2s
========================================
Vantage ready (8.3s)
HQ panel opened! (9.5s total)
```

### Previous v2.15.48 - Large Job Progress Tracking

- **No Timeout** - Renders can now take unlimited time (days if needed)
- **Progress Only Forward** - Frame count and percentage never regress
- **Resume Support** - Preserves progress when resuming paused jobs

### Previous v2.15.47 - Responsive Actions

- All pause/resume/delete actions run in background threads
- Vantage closes automatically on render completion
- No more "lost connection" messages

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
Wain.bat --software-ui      # Disable GPU compositing for the UI window
```

---

## 📦 Building the Installer (.exe)

Wain can be packaged as a standalone Windows app — no Python required on the
target machine. Both local rendering and network rendering (server + worker)
work from the installed build.

```bash
build_installer.bat
```

This produces:

| Output | Use |
|--------|-----|
| `dist\installer\Wain-Setup-<version>.exe` | Installer (Start menu, uninstaller, optional firewall rule + worker shortcut) |
| `dist\Wain-<version>-portable.zip` | Portable build — unzip on render nodes, no install needed |
| `dist\Wain\` | Raw PyInstaller bundle for local testing |

**Requirements:** Python 3.10+, and [Inno Setup 6](https://jrsoftware.org/isinfo.php) for the installer step (skipped if not installed).

**Installed-build behavior:**
- Settings, job database, auth token, and logs live in `%APPDATA%\Wain` (survives reinstalls)
- Console output is captured to `%APPDATA%\Wain\wain_console.log`
- **Worker setup:** launch the "Wain Worker" shortcut (or `Wain.exe --worker`) — a first-run dialog asks for the server address and API token and remembers them

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

## ⚠️ Vantage Settings Note

**Current Status (v2.20.0):**
Wain does **NOT** modify `vantage.ini` by default. Your Vantage configuration is completely safe.

Wain uses whatever settings are already configured in Vantage's HQ Render panel.

**To configure your render settings:**
1. Open Vantage with your scene
2. Press `Ctrl+R` to open HQ Render panel
3. Set resolution, samples, output path, frame range
4. Settings are remembered for future renders
5. Click Start in Wain - it will use your configured settings

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

<details>
<summary><strong>UI feels slow or laggy</strong></summary>

The UI uses GPU compositing by default. If you run with `--software-ui`
(CPU rendering), some visual effects are more expensive — try the default
GPU mode first.

</details>

---

## 📜 Version History

| Version | Highlights |
|---------|------------|
| **2.20.0** | Windows installer phase: PyInstaller + Inno Setup, %APPDATA% data dir, worker setup dialog |
| **2.19.5** | Splash screen logo colors, white-flash fix, GPU UI default |
| **2.19.0** | Visual redesign: accent bars, gradient progress, brand header, new logo |
| **2.18.0** | Network stability: token auth, auto-reconnect |
| **2.16.0** | Marmoset multi-pass rendering, camera detection |
| **2.15.50** | UI readiness detection, no INI modification |
| **2.15.48** | Large job progress tracking fix |
| **2.15.47** | Responsive actions, auto-close |
| **2.15.37** | State machine architecture, zombie detection |
| **2.15.15** | Per-job custom settings |

---

## 📄 License

MIT License — Free for personal and commercial use.

---

## 🔗 Links

- **GitHub**: [https://github.com/sbuff25/RenderManager](https://github.com/sbuff25/RenderManager)

---

<p align="center">
  <em>Wain v2.20.0 — Multi-engine render queue manager</em>
</p>
