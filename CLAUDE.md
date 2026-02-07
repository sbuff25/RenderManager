# Wain — Multi-Engine Render Queue Manager

> **Repository:** https://github.com/sbuff25/RenderManager
> **Current Version:** v2.15.64 (check `config.py` for exact version)
> **Developer:** Spencer
> **License:** MIT

---

## Project Overview

Wain is a desktop render queue manager for 3D artists supporting **Blender**, **Marmoset Toolbag**, and **Chaos Vantage 3.1.0**. It provides a unified interface for submitting, monitoring, pausing/resuming, and managing render jobs across multiple engines. The long-term goal is to evolve Wain into a full render farm manager (an alternative to Deadline) with network rendering capabilities.

### Tech Stack

- **UI Framework:** NiceGUI with PyQt6 + pywebview for native window
- **Database:** SQLite (local), planned SQLite shared DB for network mode
- **Automation:** pywinauto (Vantage UI automation)
- **Language:** Python 3.10+
- **Platform:** Windows (primary target)

---

## Project Structure

```
wain/
├── Wain.bat                  # Launcher script
├── readme.md                 # GitHub readme (ALWAYS lowercase)
├── CLAUDE.md                 # This file
├── wain_launcher.pyw         # Splash screen launcher (pythonw)
├── wain_config.json          # Persisted user settings
├── assets/
│   ├── wain_logo.png
│   ├── blender_logo.png
│   └── marmoset_logo.png
└── wain/                     # Main package
    ├── __init__.py
    ├── __main__.py            # Entry point (python -m wain)
    ├── app.py                 # RenderApp class, job state management
    ├── config.py              # Theme, colors, constants, version
    ├── models.py              # RenderJob, AppSettings dataclasses
    ├── engines/
    │   ├── __init__.py
    │   ├── base.py            # RenderEngine abstract base class
    │   ├── interface.py       # EngineInterface protocol
    │   ├── blender.py         # Blender integration (CLI rendering)
    │   ├── marmoset.py        # Marmoset Toolbag integration (CLI + script)
    │   ├── vantage.py         # Chaos Vantage integration (UI automation)
    │   ├── vantage_comm.py    # Vantage communication module
    │   ├── vantage_settings.py # Vantage settings schema
    │   └── registry.py        # Engine registry/discovery
    ├── ui/
    │   ├── __init__.py
    │   ├── main.py            # Main page layout
    │   ├── components.py      # Stat cards, job cards, progress bars
    │   └── dialogs.py         # Add job, edit job, settings dialogs
    └── utils/
        ├── __init__.py
        ├── bootstrap.py       # Dependency auto-installer
        └── file_dialogs.py    # Native file/folder pickers
```

---

## Critical Rules — READ BEFORE MAKING ANY CHANGES

### 1. Hardware Safety

**NEVER** develop anything that could be potentially harmful to computer hardware. This includes:
- Never write code that disables thermal throttling or overrides GPU/CPU safety limits
- Never bypass power management or sleep states during rendering
- Always respect system resource limits
- Vantage renders are GPU-intensive — never spawn multiple simultaneous Vantage renders on the same machine

### 2. Naming Conventions

- The application name is **Wain** (not "Wane")
- All internal references, imports, log prefixes use `wain` (lowercase)
- Package folder is `wain/`, import as `from wain.xxx import ...`
- Temp files use `_wain_render_` prefix
- Log messages use `[Wain]`, `[Blender]`, `[Marmoset]`, `[Vantage]` prefixes

### 3. GitHub Standards

- The readme file MUST always be `readme.md` (lowercase)
- GitHub link (https://github.com/sbuff25/RenderManager) should be referenced in relevant source files
- Include version reference in readme.md
- Commit messages should reference version numbers

### 4. Version Management

- Version is defined in `wain/config.py` as `APP_VERSION`
- Also referenced in `wain/__init__.py` and `wain_launcher.pyw`
- **Always update ALL THREE locations** when bumping version
- Use semantic versioning: MAJOR.MINOR.PATCH

### 5. Engine Accent Colors

Each render engine has a distinct themed accent color used throughout the UI:

| Engine    | Color     | Hex       |
|-----------|-----------|-----------|
| Blender   | Orange    | `#ea7600` |
| Marmoset  | Red       | `#ef0343` |
| Vantage   | Green     | `#77b22a` |

These colors appear on: status badges, action buttons, progress bars, submit buttons, version badges, and all engine-specific UI elements. **Any new engine must get its own distinct accent color.**

### 6. File Format Standards

- Config file: `wain_config.json`
- Output formats vary by engine (PNG, JPEG, EXR, TIFF, TGA)
- Temp scripts go to `%TEMP%` directory to avoid permission issues
- Progress tracking uses JSON files in `%TEMP%`

---

## Engine-Specific Technical Details

### Blender Engine

**Architecture:** Command-line rendering via `blender.exe -b <scene> --python <script>`

**Key Details:**
- Searches for Blender in `C:\Program Files\Blender Foundation\Blender X.X\`
- Supports custom executable paths
- Scene probing extracts: cameras, resolution, render engine, samples, denoiser settings, frame range
- Denoiser mapping uses `BLENDER_DENOISER_FROM_INTERNAL` dict in config.py
- Progress parsed from stdout via regex: `Fra:(\d+)` for frame numbers, `"Saved:"` for completion
- Subprocess uses `STARTF_USESHOWWINDOW` startupinfo (no special creation flags)

**Render Script Generation:**
- Generates a temporary Python script that Blender executes
- Script configures: output path, format, resolution, samples, denoiser, GPU device
- Script handles both single frame and animation renders

**Common Issues:**
- Denoiser names must be normalized between Wain's display names and Blender's internal names
- `use_compositing` and `use_sequencer` settings can affect render output
- Frame range must be set correctly for animation vs. still renders

### Marmoset Toolbag Engine

**Architecture:** CLI rendering via `toolbag.exe -hide <script.py>` with Marmoset's Python API

**Python API Reference:** https://www.marmoset.co/python/reference5.html

**CRITICAL — renderCamera() API (TB4/TB5):**
```python
mset.renderCamera(path='', width=-1, height=-1, sampling=-1,
                  transparency=False, camera='', viewportPass='')
```
- Parameter is `sampling` (NOT `samples`)
- `camera` accepts camera name string directly (no need for separate `setCamera()`)
- `viewportPass` uses **Title Case** names from Toolbag's Component View dropdown (e.g., `'Normals'`, `'Wireframe'`, `'Depth'`)
- Beauty pass = empty string `""` (renders "Full Quality")
- Unrecognized pass names silently fall back to Full Quality

**Render Pass Management:**
- `mset.RenderPassOptions()` is instantiable — can create new pass configs
- `RenderPassOptions.renderPass` (str) — pass name, `RenderPassOptions.enabled` (bool)
- `RenderObject.renderPasses` is a mutable list — supports `append()` and direct assignment
- **Passes must be registered** in the RenderObject before `renderCamera(viewportPass=...)` will recognize them
- Pass names: "Full Quality" (beauty), "Normals", "Depth", "Wireframe", "Ambient Occlusion", "Lighting (Direct)", etc.

**Known API Limitations:**
1. **`renderCamera()` for turntable:** May silently output beauty pass instead of the requested pass. Use `renderImages()` then filter for reliability.
2. **Unrecognized viewportPass names** silently fall back to "Full Quality" (beauty) — no error raised.

**Subprocess Flags — CRITICAL:**
```python
# CORRECT — for GUI apps like Toolbag:
startupinfo.wShowWindow = 0  # SW_HIDE
creation_flags = 0           # No special flags, let -hide handle it

# WRONG — breaks Toolbag startup:
creation_flags = 0x08000000  # CREATE_NO_WINDOW — this is for CONSOLE apps only!
creation_flags = subprocess.DETACHED_PROCESS  # Can also cause issues
```
The `-hide` flag tells Toolbag to run headlessly. Don't add extra subprocess flags that interfere with this.

**Progress Tracking:**
- Render script writes progress to a JSON file in `%TEMP%`
- JSON format: `{"status": "rendering", "progress": 45, "current": 5, "total": 10}`
- Main thread polls this file while Toolbag process runs
- Script must call `mset.quit()` at the end to close Toolbag

**Scene Probing:**
- Uses a separate probe script that opens the scene, extracts info, writes JSON, quits
- Extracts: cameras, render passes, resolution, samples, timeline length
- Probe also uses `-hide` flag

### Chaos Vantage Engine

**Architecture:** UI automation via pywinauto (Vantage 3.x has NO command-line rendering)

**CRITICAL — Vantage 3.1.0 Specifics:**
1. **No CLI rendering** — Modern Vantage (3.x) completely removed command-line rendering capabilities
2. **Must use UI automation** — pywinauto connects to the running Vantage window
3. **Scene files:** `.vantage` (JSON-based) and `.vrscene` formats
4. **Qt-based UI** — Use `backend="uia"` with pywinauto
5. **Window class:** `LavinaMainWindow`
6. **HQ Render panel:** Opened via Tools menu or Ctrl+R shortcut
7. **Live Link port:** 20701 (HTTP API, used by 3ds Max/Maya integration)

**Settings Storage:**
- Global settings in `vantage.ini` (located in user AppData)
- Key INI settings:
  - `snapshotResDefault=@Size(3840 2160)` — Resolution
  - `snapshotSamplesDefault=100` — Sample count
  - `snapshotDenoiserTypeDefault=0` — Denoiser type
  - `sequenceOutputTypesDefault=1` — Output type
- Frame range is NOT in INI — it's in the `.vantage` scene file or set via UI

**Progress Tracking:**
- Read from Vantage's progress dialog window via UI automation
- Parse progress text for percentage and frame numbers
- **High water mark protection:** Frame counts must only increase, never decrease
- `on_progress()` must pass frame numbers (not percentages) to match app.py convention
- Don't set arbitrary timeouts that kill long renders — some frames take 10+ minutes

**Launching Vantage:**
- Wain must launch Vantage with the scene file if not already running
- Wait for window to appear before attempting automation
- Use `subprocess.Popen([vantage_exe, scene_path])` to launch

**Common Issues:**
- Progress percentage being interpreted as frame number (causes "Frame 1/300" display)
- Large jobs showing incorrect frame counts due to parsing failures
- 2-hour timeout killing valid long renders (remove arbitrary timeouts)

---

## UI Architecture

### NiceGUI + PyQt6

The UI is built with NiceGUI (web framework) displayed in a native window via pywebview/PyQt6. This means:
- The UI is HTML/CSS/JS under the hood (Quasar framework)
- Styling uses Quasar classes and inline CSS
- Dark theme is configured in `config.py` DARK_THEME dict
- Engine colors are applied dynamically via `.style()` calls

### Key UI Components

- **Stat Cards:** Show queue stats (total, rendering, completed, failed)
- **Job Cards:** Display individual job status, progress bars, engine badges
- **Add Job Dialog:** Engine-specific form fields that update when engine type changes
- **Settings Dialog:** Configure engine paths, preferences
- **Progress Bars:** Color-coded by engine, show frame/percentage progress

### Important UI Patterns

- Use `ui.notify()` for user feedback
- File/folder pickers use native dialogs from `utils/file_dialogs.py`
- Engine switching in dialogs must update accent colors on all elements
- Progress updates come via callbacks from engine threads

---

## Development Workflow

### Before Making Changes

1. **Read this entire CLAUDE.md first**
2. **Check the current version** in `config.py`
3. **Understand what's working** — don't break functioning engines while fixing another
4. **Test all three engines** after any cross-cutting changes

### Making Changes

1. Increment version in `config.py`, `__init__.py`, and `wain_launcher.pyw`
2. Add clear docstrings referencing the version and what changed
3. Include the GitHub URL in file headers where appropriate
4. Test the specific engine you modified
5. Verify other engines still work (especially after shared code changes)

### Common Pitfalls

| Pitfall | Prevention |
|---------|------------|
| Marmoset won't start | Check subprocess creation_flags — must NOT use CREATE_NO_WINDOW |
| Vantage progress resets | Ensure high water mark protection in progress tracking |
| Wrong frame count display | Verify on_progress() passes frame number, not percentage |
| Engine colors missing | Check ENGINE_COLORS dict in config.py |
| Render script permissions | Write temp scripts to `%TEMP%`, not project directory |
| Denoiser mismatch | Use normalization dicts in config.py |
| Version mismatch | Update ALL THREE version locations |

### Debugging Tips

- **Marmoset:** Check `%TEMP%` for `_wain_render_*.py` scripts and `_wain_marmoset_progress_*.json` files
- **Blender:** Run Wain.bat with `--debug` flag to see stdout in console
- **Vantage:** Check if pywinauto can find the window — run standalone test script first
- **All engines:** Check `wain_render_log.txt` for error details

---

## Network Rendering (Future — Phase 2+)

### Planned Architecture

```
┌─────────────────────────────────────────────┐
│         MAIN WORKSTATION (Server + Worker)   │
│         Wain UI + SQLite job database        │
│         http://your-pc:8080                  │
└────────────────┬────────────────────────────┘
                 │
      ┌──────────┼──────────┐
      ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌────────┐
  │Worker 2│ │Worker 3│ │Worker 4│  ... (5+ nodes)
  │headless│ │headless│ │headless│
  └────────┘ └────────┘ └────────┘
```

### Key Design Decisions

- Single user, same engines on all machines
- Shared SQLite database (REST API approach, not file-based)
- Workers poll server for available jobs
- Atomic job claiming to prevent double-assignment
- Heartbeat system (30-second intervals, 2-minute stale timeout)
- Scene files accessed via UNC network paths (`\\server\projects\`)
- NiceGUI already web-based — expose on `0.0.0.0:8080` for network access

### Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Server mode + REST API + SQLite | Planned |
| Phase 2 | Worker mode + job claiming | Planned |
| Phase 3 | Frame splitting + engine routing | Planned |
| Phase 4 | Windows service + auto-reconnection | Planned |
| Phase 5 | Job dependencies + notifications | Planned |

---

## Market Context

Wain targets indie 3D artists, visualization studios, architectural firms, game asset creators, and product visualization companies. Pricing strategy:

| Tier | Price | Target |
|------|-------|--------|
| Indie | $59-79 | Freelancers |
| Studio | $149-199 | Small studios (2-10 seats) |
| Enterprise | $499+ | Large teams |

Competitive advantages over Deadline: modern UI, simpler setup, lightweight, engine-aware, indie pricing.

---

## Quick Reference

### Run Wain
```bash
python -m wain          # Direct launch
Wain.bat                # Windows launcher
Wain.bat --debug        # Debug mode (console visible)
Wain.bat --install      # Install dependencies
```

### Key Config Values (config.py)
```python
APP_NAME = "Wain"
APP_VERSION = "2.15.64"  # Check actual value
ENGINE_COLORS = {
    "blender": "#ea7600",
    "marmoset": "#ef0343",
    "vantage": "#77b22a",
}
```

### Dependencies
```
nicegui, PyQt6, PyQt6-WebEngine, qtpy, Pillow, pywebview, pywinauto
```

---

## Iteration History

This project has been developed iteratively across multiple chat sessions (ITT01 → ITT04-Native and beyond). Key milestones:

- **v1.0** — Monolithic single-file render manager
- **v1.1** — Modular architecture refactor (package structure)
- **v1.8** — Marmoset lowercase pass name fix
- **v2.1** — Discovered Marmoset API limitations (render-all-then-filter strategy)
- **v2.3** — Marmoset frameCount fix (use Timeline instead)
- **v2.9** — Vantage UI automation integration
- **v2.14** — Marmoset subprocess flag fix (CREATE_NO_WINDOW → SW_HIDE)
- **v2.15** — Vantage progress tracking fixes (high water mark, frame vs percentage)
- **v2.15.64** — Current version

**Always search past project context before making changes to maintain continuity.**
