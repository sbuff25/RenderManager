<p align="center">
  <img src="assets/wain_logo.png" alt="Wain Logo" width="120" height="120">
</p>

<h1 align="center">Wain</h1>

<p align="center">
  <strong>A professional render queue manager for 3D artists</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.15.16-blue.svg" alt="Version">
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
- **Pause & Resume** — Stop and continue renders at any frame
- **Scene Probing** — Auto-detects resolution, cameras, frame range, and render settings
- **Selective Multi-Pass** — Render only the passes you need (Marmoset)
- **Resolution Scaling** — Quick presets for 25%, 50%, 100%, 150%, 200%
- **Native Desktop App** — Custom title bar with smooth Windows animations
- **Auto Dependencies** — First run installs everything automatically

---

## 🆕 What's New in v2.15.16

### Vantage Scene Probing

**v2.15.16** now reads your actual Vantage HQ settings when loading a scene file:

**Auto-Detection:**
When you load a `.vantage` file, Wain reads `vantage.ini` and shows:
- Resolution (e.g., 3840×2160)
- Samples (e.g., 100)
- Denoiser (NVIDIA/OIDN/Off)

**Status Display:**
```
Vantage HQ: 3840x2160, 100 samples, NVIDIA
```

**Form Pre-Population:**
- Resolution fields auto-fill with your Vantage settings
- Vantage samples field shows your current value
- Denoiser dropdown pre-selects your active denoiser

This is a **READ-ONLY** operation — completely safe, no files are modified.

### Previous: v2.15.15 - Per-Job Custom Settings

**Toggle Custom Settings:**
- New "Use Custom Settings" checkbox in Add Job dialog
- When OFF: Uses your existing Vantage HQ settings (default)
- When ON: Override resolution, samples, and denoiser per job

**Safety Features:**
- Automatic backup of `vantage.ini` before ANY modification
- Validation of all values (resolution 64-16384, samples 1-65536)
- Preserves exact Qt serialization format (`@Size(w h)`)
- Backup files timestamped: `vantage_backup_YYYYMMDD_HHMMSS.ini`

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

**Current Status (v2.15.13):**
INI modification is **DISABLED** for safety. Wain uses whatever settings are configured in Vantage's HQ Render panel.

**When INI Writing is Re-enabled (future version):**
- Wain will be able to automatically configure Vantage HQ settings
- Resolution, samples, frame range, and output path will be set before launch
- Backups will be created before any modification

For now, configure your HQ render settings manually in Vantage:
1. Open Vantage with your scene
2. Press `Ctrl+R` to open HQ Render panel
3. Set resolution, samples, output path
4. Settings are remembered for future renders

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

## 📜 Version History

| Version | Highlights |
|---------|------------|
| **2.15.13** | DRY RUN mode, enhanced safety logging |
| **2.15.12** | Emergency INI write disable after corruption |
| **2.15.11** | Add Job button fix |
| **2.15.9** | Frame range read/write support |
| **2.15.0** | Full HQ settings control for Vantage |

---

## 📄 License

MIT License — Free for personal and commercial use.

---

## 🔗 Links

- **GitHub**: [https://github.com/Spencer-Sliffe/Wain](https://github.com/Spencer-Sliffe/Wain)

---

<p align="center">
  <em>Wain v2.15.13 — Multi-engine render queue manager</em>
</p>
