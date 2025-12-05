# Render Manager

A **desktop application** for managing Blender render queues with pause/resume support.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![GUI](https://img.shields.io/badge/GUI-tkinter-green)

---

## What This Is

Render Manager is a **local desktop application** that acts as a render queue manager for Blender. It allows you to:

- Queue multiple Blender scenes for sequential rendering
- **Pause and resume** animation renders mid-sequence
- Monitor render progress in real-time
- Manage multiple Blender versions
- Configure render settings without opening Blender

This is **not** a web application. It is a native Windows desktop tool that runs locally on your workstation or render node.

---

## Why This Exists

### The Problem

When rendering long animations in Blender:
- You can't easily pause and resume renders
- Managing multiple render jobs requires manual babysitting
- Switching between Blender versions for different projects is tedious
- There's no built-in queue system for batch rendering

### The Solution

Render Manager provides:
- A persistent job queue that survives restarts
- True pause/resume for animations (picks up at the next frame)
- Automatic Blender version detection and matching
- Background rendering via Blender's command-line interface
- Real-time progress monitoring and logging

---

## Why Desktop, Not Web

This tool **must** be a desktop application because it needs:

| Requirement | Why Web Won't Work |
|-------------|-------------------|
| **Local file access** | Reads .blend files and writes rendered frames directly to disk |
| **Blender CLI execution** | Spawns `blender.exe` as a subprocess with full command-line control |
| **GPU access** | Configures CUDA/OptiX/HIP for GPU-accelerated rendering |
| **Process management** | Monitors, pauses, and terminates Blender processes |
| **System integration** | Detects installed Blender versions from Program Files |
| **No latency** | Real-time progress parsing from Blender's stdout |

A web interface would require a separate backend service, add unnecessary complexity, and couldn't directly control local rendering hardware.

---

## Target Users

- **3D Artists** rendering animations overnight
- **Small Studios** managing render workloads across workstations
- **Freelancers** who need to pause renders for client calls
- **Anyone** tired of manually babysitting Blender renders

---

## Features

### Core Functionality
- ✅ Queue-based render management
- ✅ Pause/resume animation renders (frame-accurate)
- ✅ Real-time progress tracking
- ✅ Elapsed time and ETA display
- ✅ Automatic job processing

### Blender Integration
- ✅ Auto-detects installed Blender versions (3.x, 4.x)
- ✅ Matches .blend files to appropriate Blender version
- ✅ Reads scene settings (resolution, engine, cameras, frame range)
- ✅ Supports Cycles, Eevee, and Workbench engines
- ✅ GPU rendering with CUDA, OptiX, HIP, or auto-detection

### Job Configuration
- ✅ Custom output paths and naming
- ✅ Frame range override
- ✅ Resolution override
- ✅ Camera selection
- ✅ Output format (PNG, JPEG, OpenEXR, TIFF)
- ✅ Submit jobs as paused (for later batch start)

### User Experience
- ✅ Dark theme UI (Tailwind Zinc palette)
- ✅ Persistent job queue (survives app restart)
- ✅ Expandable job cards with full details
- ✅ Real-time Blender log output
- ✅ One-click "Open in Blender" for debugging

---

## System Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Windows 10/11 (macOS/Linux possible with modifications) |
| **Python** | 3.8 or higher |
| **Blender** | 3.3+ (auto-detected from standard install locations) |
| **RAM** | 8GB+ recommended (depends on scene complexity) |
| **GPU** | Optional but recommended for Cycles rendering |

---

## Installation

### Quick Start

1. **Download** the latest release or clone this repository
2. **Double-click** `RenderManager.bat`
3. The launcher will:
   - Check for Python installation
   - Install Pillow (optional, for logo display)
   - Launch the application

### Manual Setup

```bash
# Clone the repository
git clone https://github.com/sbuff25/RenderManager.git
cd RenderManager

# Install dependencies
pip install Pillow

# Run the application
python render_manager_ITT03.py
```

### First Run

On first launch, Render Manager will:
1. Scan for Blender installations in standard locations
2. Create a config file (`render_manager_config.json`)
3. Display any detected Blender versions in the log

If no Blender is found, go to **Settings** and add a custom path.

---

## Usage

### Adding a Render Job

1. Click **"+ Add Job"**
2. Browse to your `.blend` file
3. Select output directory
4. Adjust settings (or use scene defaults)
5. Click **"Submit Job"**

### Managing Jobs

| Action | How |
|--------|-----|
| Start queued job | Click ▶ (play) or wait for auto-processing |
| Pause rendering | Click ⏸ (pause) - resumes from next frame |
| Retry failed job | Click ↻ (retry) |
| Delete job | Click 🗑 (trash) |
| View details | Click ▼ (expand) |

### Job Status Flow

```
QUEUED → RENDERING → COMPLETED
           ↓
        PAUSED → RENDERING (resumed)
           ↓
        FAILED → QUEUED (retry)
```

---

## How It Works

### Render Pipeline

```
1. User submits job via GUI
          ↓
2. Job saved to config (persistent queue)
          ↓
3. Queue processor picks up next "queued" job
          ↓
4. Generates Python setup script for Blender
          ↓
5. Launches: blender.exe -b scene.blend --python setup.py -a
          ↓
6. Parses stdout for "Fra:X" progress updates
          ↓
7. On completion/error, updates job status
          ↓
8. Processes next job in queue
```

### Pause/Resume Mechanism

When you pause a render:
1. Current frame number is saved to the job
2. Blender process is terminated
3. Job status changes to "paused"

When you resume:
1. Render restarts from `current_frame + 1`
2. Already-rendered frames are preserved on disk
3. Progress bar reflects total completion

---

## Configuration

### Saved Settings

All settings persist in `render_manager_config.json`:

```json
{
  "settings": {
    "blender_paths": {
      "4.2.0": "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",
      "4.1.0": "C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe"
    },
    "default_engine": "Cycles",
    "default_resolution": "1920x1080",
    "use_gpu": true
  },
  "jobs": [...]
}
```

### Blender Detection

Automatically scans these locations:
- `C:\Program Files\Blender Foundation\Blender X.X\`

Custom paths can be added via Settings.

---

## Project Structure

```
RenderManager/
├── render_manager_ITT03.py   # Main application
├── RenderManager.bat         # Windows launcher
├── requirements.txt          # Python dependencies
├── icon.ico                  # Application icon
├── icon.png                  # Alternate icon
├── logo.png                  # Header logo (48x48)
├── COMPONENTS.md             # UI component documentation
├── UI_STRUCTURE.md           # Component hierarchy
└── README.md                 # This file
```

---

## Technical Architecture

### Built With

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| GUI Framework | tkinter (standard library) |
| Styling | Custom dark theme (Tailwind Zinc colors) |
| Process Management | subprocess module |
| Data Persistence | JSON file storage |
| Image Handling | Pillow (optional) |

### Why tkinter?

- **Zero dependencies**: Included with Python standard library
- **Native OS integration**: Real window, taskbar icon, system dialogs
- **Subprocess control**: Direct access to spawn and manage Blender processes
- **File system access**: Native file/folder browser dialogs
- **No server required**: Runs entirely locally
- **Simple deployment**: Single .py file + batch launcher

### Key Classes

| Class | Purpose |
|-------|---------|
| `RenderManager` | Main application window and orchestration |
| `BlenderInterface` | Blender CLI communication and version management |
| `RenderJob` | Data model for individual render jobs |
| `AppSettings` | Application configuration storage |
| `JobCard` | UI component for job display |
| `AddJobModal` | Job submission form dialog |
| `SettingsPanel` | Application settings dialog |

---

## Design Guidelines

### UI Framework Constraints

Since this is a **tkinter application**, UI designs must be implementable with:

- `tk.Frame`, `tk.Label`, `tk.Button`, `tk.Entry`, `tk.Canvas`
- `ttk.Combobox`, `ttk.Scrollbar`, `ttk.Checkbutton`
- `tk.Toplevel` for modal dialogs
- Pack/Grid/Place geometry managers
- Event bindings for hover/click states

### What's NOT Available in tkinter

- CSS animations or transitions
- SVG icons (use Unicode symbols or PNG images)
- Flexbox/CSS Grid (use pack/grid managers)
- Web fonts (use system fonts: Segoe UI, Consolas)
- Border radius on frames (simulated with canvas or flat design)
- Drop shadows (not natively supported)

### Current Theme (Tailwind Zinc)

```python
BG_BASE = "#09090b"      # zinc-950 - Main background
BG_CARD = "#18181b"      # zinc-900 - Card backgrounds
BG_ELEVATED = "#27272a"  # zinc-800 - Inputs, elevated surfaces
BORDER = "#27272a"       # zinc-800 - Default borders
TEXT_PRIMARY = "#fafafa" # zinc-100 - Primary text
TEXT_SECONDARY = "#a1a1aa" # zinc-400 - Secondary text
TEXT_MUTED = "#71717a"   # zinc-500 - Muted text
BLUE = "#2563eb"         # blue-600 - Primary actions
GREEN = "#22c55e"        # green-500 - Success
YELLOW = "#eab308"       # yellow-500 - Warning/queued
RED = "#ef4444"          # red-500 - Error/delete
```

---

## Limitations

- **Windows-focused**: Paths and subprocess handling assume Windows (can be adapted)
- **Sequential rendering**: One job at a time (no distributed rendering)
- **Blender only**: Designed specifically for Blender's CLI interface
- **Local storage**: Config saved to local JSON file (no cloud sync)
- **tkinter constraints**: Limited styling compared to web technologies

---

## Future Possibilities

- [ ] Multi-job parallel rendering (resource permitting)
- [ ] Network render node support (watch folder system)
- [ ] Email/Discord notifications on completion
- [ ] Render time estimation based on history
- [ ] Thumbnail previews of completed frames
- [ ] Additional render engine support (Marmoset Toolbag, etc.)

---

## Version History

| Version | Description |
|---------|-------------|
| **ITT01** | Initial release with core Blender render queue functionality |
| **ITT02** | Added multi-engine architecture (prepared for Marmoset Toolbag support) |
| **ITT03** | Redesigned UI with Figma-based Tailwind Zinc dark theme |

---

## Contributing

This is an internal tool being actively developed. If you'd like to contribute:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## License

This project is provided as-is for personal and professional use.

---

## Acknowledgments

- Built for use with [Blender](https://www.blender.org/)
- UI colors from [Tailwind CSS](https://tailwindcss.com/) Zinc palette
- Developed with assistance from Claude (Anthropic)
