# Wain — Multi-Engine Render Queue Manager

> **Repository:** https://github.com/sbuff25/RenderManager
> **Current Version:** v2.21.0 (check `config.py` for exact version)
> **Developer:** Spencer
> **License:** MIT

---

## ⚠ CRITICAL RULES — MUST READ FIRST

These rules are **non-negotiable**. Violating any of them will break the project, corrupt data, or damage hardware.

### 1. Hardware Safety — TOP PRIORITY

**NEVER** develop anything that could be potentially harmful to computer hardware:

- Never write code that disables thermal throttling or overrides GPU/CPU safety limits
- Never bypass power management or sleep states during rendering
- Always respect system resource limits
- Vantage renders are GPU-intensive — never spawn multiple simultaneous Vantage renders on the same machine
- When implementing GPU temperature monitoring (see Feature Roadmap), use read-only queries only — never attempt to modify GPU clocks, fan curves, or power limits
- All timeout and retry logic must have hard upper bounds to prevent infinite loops that could overheat hardware

### 2. Application Naming

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

### 5. Iterative Development

This project is developed iteratively across multiple chat sessions (ITT01 → ITT04-Native and beyond). **Always search past project context before making changes to maintain continuity.** Do not modify code without understanding what currently works — breaking a functioning engine while fixing another is unacceptable.

---

## Project Overview

Wain is a desktop render queue manager for 3D artists supporting **Blender**, **Marmoset Toolbag**, and **Chaos Vantage 3.1.0**. It provides a unified interface for submitting, monitoring, pausing/resuming, and managing render jobs across multiple engines. The long-term goal is to evolve Wain into a full render farm manager (an indie alternative to AWS Deadline) with network rendering capabilities.

### Tech Stack

- **UI Framework:** NiceGUI with PyQt6 + pywebview for native window
- **Database:** SQLite (local), planned SQLite shared DB for network mode
- **Automation:** pywinauto (Vantage UI automation)
- **Language:** Python 3.10+
- **Platform:** Windows (primary target)

### Engine Accent Colors

Each render engine has a distinct themed accent color used throughout the UI:

| Engine    | Color     | Hex       |
|-----------|-----------|-----------|
| Blender   | Orange    | `#ea7600` |
| Marmoset  | Red       | `#ef0343` |
| Vantage   | Green     | `#77b22a` |
| Unreal    | Blue      | `#0d8de3` |

These colors appear on: status badges, action buttons, progress bars, submit buttons, version badges, and all engine-specific UI elements. **Any new engine must get its own distinct accent color.**

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

## Engine Technical Reference

### Blender

**Architecture:** Command-line rendering via `blender.exe -b <scene> --python <script>`

**Official Documentation:**
- CLI arguments: https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html

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

**Known Issues:**
- Denoiser names must be normalized between Wain's display names and Blender's internal names
- `use_compositing` and `use_sequencer` settings can affect render output
- Frame range must be set correctly for animation vs. still renders

---

### Marmoset Toolbag

**Architecture:** CLI rendering via `toolbag.exe -hide <script.py>` with Marmoset's Python API

**Official Documentation:**
- Python API reference: https://marmoset.co/python/reference.html
- Python scripting tutorial: https://marmoset.co/posts/python-scripting-toolbag/

**⚠ CRITICAL — Known API Limitations:**

1. **`rp.enabled` is IGNORED** — Marmoset's API cannot selectively enable/disable individual render passes. Setting `rp.enabled = False` has no effect.
2. **`viewportPass` parameter behavior:** `renderCamera()` requires **LOWERCASE** pass names (e.g., `'normals'` not `'Normals'`), even though the scene stores them in title case.
3. **Beauty pass workaround:** For beauty, use empty string `""` as the viewportPass.
4. **Multi-pass strategy:** Call `renderImages()` which outputs ALL passes, then **filter/delete unwanted files** after rendering. This is the only reliable method.
5. **`renderCamera()` for turntable:** Even with lowercase pass names, turntable renders may silently output beauty pass instead of the requested pass. The render-all-then-filter strategy is more reliable.

**⚠ Subprocess Flags — CRITICAL:**
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

---

### Chaos Vantage (v3.1.0)

**Architecture:** UI automation via pywinauto (Vantage 3.x has NO command-line rendering)

**Official Documentation:**
- No public automation API — Chaos has not published automation docs for Vantage 3.x
- This is the reason pywinauto UI automation is required

**⚠ CRITICAL — Vantage 3.1.0 Specifics:**

1. **No CLI rendering** — Modern Vantage (3.x) completely removed command-line rendering capabilities
2. **Must use UI automation** — pywinauto connects to the running Vantage window
3. **Scene files:** `.vantage` (JSON-based) and `.vrscene` formats
4. **Qt-based UI** — Use `backend="uia"` with pywinauto
5. **Window class:** `LavinaMainWindow`
6. **HQ Render panel:** Opened via Tools menu or Ctrl+R shortcut
7. **Live Link port:** 20701 (HTTP API, used by 3ds Max/Maya integration)
8. **Command port:** 20702

**Settings Storage (vantage.ini):**
- Located in user AppData directory
- Key INI settings:
  - `snapshotResDefault=@Size(3840 2160)` — Resolution
  - `snapshotSamplesDefault=100` — Sample count
  - `snapshotDenoiserTypeDefault=0` — Denoiser type (0=Intel OIDN, 6=NVIDIA OptiX, etc.)
  - `snapshotDenoiseDefault=true` — Denoiser enabled
  - `snapshotDenoiseIntermediateDefault=true` — Denoise during render
  - `snapshotTemporalDefault=true` — Temporal accumulation
  - `snapshotLightCacheDefault=true` — Light cache
  - `snapshotMoblurDefault=false` — Motion blur
  - `sequenceOutputTypesDefault=1` — Output type
  - `snapshotMultiFileElementSaveDefault=false` — Multi-file element save
  - `snapshotRenderElementsDefault=0` — Render elements
  - `liveLinkPort=20701` — Live Link port
  - `commandPort=20702` — Command port
  - `startLiveLinkServerWithApp=true` — Auto-start Live Link
- Frame range is NOT in INI — it's in the `.vantage` scene file or set via UI
- INI uses Qt serialization format: `@Size(w h)`, `@Point(x y)`, `@Variant(...)` for colors

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

**Known Issues:**
- Progress percentage being interpreted as frame number (causes "Frame 1/300" display)
- Large jobs showing incorrect frame counts due to parsing failures
- 2-hour timeout killing valid long renders (remove arbitrary timeouts)

---

### Unreal Engine (v2.21.0)

**Architecture:** Headless out-of-process Movie Render Queue via `UnrealEditor-Cmd.exe`

**Command line:**
```
UnrealEditor-Cmd.exe "<project>.uproject" <MapPath> -game
    -LevelSequence="<SequencePath>" -MoviePipelineConfig="<PresetPath>"
    -windowed -resx=1280 -resy=720 -log -stdout -FullStdOutLogOutput
    -unattended -RenderOffscreen -NoSplash -NoLoadingScreen
```

**⚠ CRITICAL — Design decisions (do not "simplify" these away):**

1. **Out-of-process ONLY.** Never render inside a running editor — in-editor MRQ
   has a known completion-teardown crash (D3D12 `BackingResource->GetRefCount()==1`
   ensure). A fresh headless process per job also isolates GPU device-hung frames.
2. **Progress = files on disk, not stdout.** MRQ stdout does not reliably announce
   per-frame completion across UE versions. The engine polls the job's Output Folder
   (recursively, every 2s) and counts image files created after render start.
   This also works over VPN/UNC for network workers. Stdout is only parsed for
   status text and errors (filtered hard — UE logs thousands of shader lines).
3. **Resolution/format/frame-range come from the MRQ preset asset**, not from Wain.
   The job's Output Folder must match the preset's Output Directory. Job
   frame_start/frame_end are for progress math only.
4. **Nonzero exit + all frames on disk = success.** UE sometimes exits nonzero on
   teardown after a complete render; if the expected frame count is present,
   complete with a logged warning instead of failing the job.

**Version discovery:** `C:\ProgramData\Epic\UnrealEngineLauncher\LauncherInstalled.dat`
(canonical) + fallback scan of `<drive>:\[Program Files\]Epic Games\UE_*` on all
drives. Per-project version pick uses the `.uproject`'s `EngineAssociation`.

**Scene probing (no engine launch — launching a headless editor costs minutes):**
parse `.uproject` JSON; scan `Content/` for `.umap` (maps); sniff first 64KB of
`.uasset` files for `LevelSequence` / `MoviePipelinePrimaryConfig` class-import
strings (sequences / MRQ presets). File → soft path: `Content/Foo/Bar.umap` →
`/Game/Foo/Bar`. Expect some sequence false positives (marketplace anim packs) —
the lists are autocomplete candidates, not authoritative.

**Engine settings keys:** `map_path`, `sequence_path`, `preset_path`, `extra_args`.
All three paths required; submit blocks without them.

**GPU crash note (from the Koch project):** long 4K Lumen frames can exceed the
Windows TDR timeout (default 2s, commonly raised to 20-60s via
`HKLM\...\GraphicsDrivers\TdrDelay`). A `DEVICE_HUNG` in the log tail means the
frame was too heavy, not that the scene is broken — the fix is TdrDelay + lighter
per-frame settings in the preset, and it only kills the child process, never Wain.

---

## UI Architecture

### NiceGUI + PyQt6

The UI is built with NiceGUI (web framework) displayed in a native window via pywebview/PyQt6:

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

## Feature Roadmap

Based on competitive analysis of Deadline, Royal Render, Muster, Flamenco, OpenCue, CGRU/Afanasy, and others. Features are ordered by implementation priority.

### Phase 1 — High Priority (Next Implementation Cycle)

#### 1.1 GPU/CPU Temperature Monitoring + Auto-Pause
*Inspired by: Hardware safety requirement (unique differentiator — no indie render manager does this well)*

- Monitor GPU temperature via `nvidia-smi` queries (NVIDIA) or WMI (AMD/Intel)
- Query is **read-only** — never attempt to modify GPU settings
- Warning alert at configurable threshold (default ~80°C)
- Auto-pause render queue at critical threshold (default ~90°C)
- Auto-resume when temperature drops below safe threshold
- Monitor: core temp, memory junction temp, hotspot temp where available
- Display in UI: real-time temp badge, color-coded (green/yellow/red)
- Log temperature events for diagnostics
- **Hardware safety note:** Consumer GPU thermal throttling typically begins 90-95°C. Use conservative defaults.

#### 1.2 Render Preview Thumbnails
*Inspired by: Royal Render's signature feature*

- Render a sample frame first (frame 1 or user-selected) before committing to full sequence
- Display preview thumbnail in job card UI
- Catches composition/lighting errors before wasting hours
- Implementation: render preview frame → save to temp → display in UI → prompt user to continue or cancel
- Supports all three engines

#### 1.3 Job Dependencies / Chaining
*Inspired by: Deadline's most-used feature*

- Job B waits for Job A to complete before starting
- Enable multi-step workflows: Blender animation → Marmoset turntable → video compilation
- Store dependency as `depends_on_job_id` in job model
- Queue processor checks dependency status before starting dependent jobs
- UI: dropdown to select parent job when adding a new job

#### 1.4 Notifications (Discord Webhook / Desktop Toast)
*Inspired by: Muster notification system, Blender "Render Notifications" extension*

- **Discord webhook:** POST to user-configured webhook URL with JSON payload
  - Include: job name, engine, status, duration, preview image (if available)
  - Discord webhook format is compatible with Slack webhooks
- **Desktop toast:** Windows toast notification via `win10toast` or `plyer`
- **Sound alert:** Configurable audio cue on completion/failure
- Trigger events: render complete, render failed, first frame complete, queue empty
- Settings: per-event toggles, webhook URL configuration

#### 1.5 Estimated Time Remaining
*Inspired by: GarageFarm, Deadline cost estimation*

- Track average frame render time after first 2-3 frames complete
- Calculate and display ETA for full job completion
- Show in job card: "~2h 15m remaining" or "ETA: 11:45 PM"
- Historical data stored in SQLite for cross-job estimates
- Per-engine time tracking (Vantage frames are typically much slower than Blender)

### Phase 2 — Network Rendering

#### 2.1 Server Mode + REST API
- Expose NiceGUI on `0.0.0.0:8080` for network access
- REST API endpoints for job CRUD, worker registration, status queries
- SQLite shared database (REST API approach, not file-based sharing)
- Authentication for network access

#### 2.2 Worker Mode + Job Claiming
- Headless worker mode for render nodes
- Workers poll server for available jobs
- Atomic job claiming to prevent double-assignment
- Heartbeat system (30-second intervals, 2-minute stale timeout)
- Scene files accessed via UNC network paths (`\\server\projects\`)

#### 2.3 Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│         MAIN WORKSTATION (Server + Worker)       │
│         Wain UI + SQLite job database            │
│         http://your-pc:8080                      │
└────────────────┬────────────────────────────────┘
                 │
      ┌──────────┼──────────┐
      ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌────────┐
  │Worker 2│ │Worker 3│ │Worker 4│  ... (5+ nodes)
  │headless│ │headless│ │headless│
  └────────┘ └────────┘ └────────┘
```

#### 2.4 Network Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 2.1 | Server mode + REST API + SQLite | Planned |
| Phase 2.2 | Worker mode + job claiming | Planned |
| Phase 2.3 | Frame splitting + engine routing | Planned |
| Phase 2.4 | Windows service + auto-reconnection | Planned |

### Phase 3 — Medium Priority Features

#### 3.1 Priority Levels with Weighted Scheduling
*Inspired by: Deadline weighted scheduling*

- Simple tier system: Low / Normal / High / Critical
- Higher priority preempts lower at next frame boundary (never mid-frame)
- For network mode: priority affects which worker claims which job first

#### 3.2 Auto-Retry on Failure with Error Detection
*Inspired by: Royal Render philosophy — "A job isn't done when frames are sent, it's done when all frames are on your hard drive"*

- Auto-retry failed frames (configurable 1-3 attempts)
- Detect common error patterns: OOM, missing texture, GPU crash, disk full
- Flag auto-retried jobs differently than user-cancelled jobs
- Track retry count per frame

#### 3.3 Post-Render Actions / Scripts
*Inspired by: Deadline post-job scripts*

- Run configurable actions after job completion
- Built-in actions: open output folder, EXR→MP4 conversion, copy to network share
- Custom script hook: run any `.py` or `.bat` after job finishes
- Actions configured per-job or as global defaults

#### 3.4 Scene Validation / Pre-flight Check
*Inspired by: RebusFarm RANCHecker*

- Verify before rendering: scene file exists, output path writable, engine executable found, sufficient disk space
- Engine-specific checks: Blender scene probing, Marmoset scene parsing, Vantage window detection
- Block job submission if validation fails (with clear error message)
- Prevents queue-clogging errors

#### 3.5 Job History / Statistics
*Inspired by: All commercial render managers*

- Track: average frame time per engine, total render hours, jobs completed/failed
- Store in SQLite (already available)
- Display in UI: stats dashboard or summary panel
- Used for ETA calculations (feeds into Feature 1.5)

### Phase 4 — Lower Priority / Network Phase Features

#### 4.1 Frame Slicing / Tile Rendering
*Inspired by: Muster*

- Split single high-res still across multiple machines (network mode)
- Auto-composite tiles after all complete
- Relevant for 8K+ architectural visualization renders

#### 4.2 "Nimby" Mode (Not In My BackYard)
*Inspired by: CGRU/Afanasy*

- Render only when artist is idle (detect mouse/keyboard inactivity)
- Pause gracefully when artist returns to workstation
- Perfect for workstations doubling as render nodes in network mode

#### 4.3 Wake-on-LAN
*Inspired by: Royal Render, CGRU*

- Wake sleeping render nodes when jobs are queued
- Shut down nodes when idle (configurable timeout)
- Power savings for network render farm

#### 4.4 Integrated Output Viewer
*Inspired by: Muster*

- Built-in thumbnail browser for rendered output
- Lightweight: click-to-open per frame in system default viewer
- Show render pass strips for multi-pass jobs

### Features to AVOID (Out of Scope)

These features add enterprise complexity without benefiting Wain's target market:

- Multi-facility cloud bridging (Deadline + Hammerspace)
- LDAP / Active Directory integration
- Complex pool/group management (overkill for indie scale)
- Multi-region rendering (AWS Deadline Cloud)
- Kubernetes/container orchestration

---

## Competitive Positioning

### Target Market

Wain targets indie 3D artists, visualization studios, architectural firms, game asset creators, and product visualization companies as an alternative to expensive enterprise solutions.

### Pricing Strategy

| Tier | Price | Target |
|------|-------|--------|
| Indie | $59-79 | Freelancers |
| Studio | $149-199 | Small studios (2-10 seats) |
| Enterprise | $499+ | Large teams |

### Key Differentiators vs. Competition

| Feature | Wain | Deadline | Royal Render | Flamenco |
|---------|------|----------|--------------|----------|
| Setup complexity | Minutes | Hours/Days | Hours | Medium |
| GPU temp monitoring | ✅ Planned | ❌ | ❌ | ❌ |
| Engine-aware UI | ✅ Native | Plugin-based | Plugin-based | Blender only |
| Indie pricing | ✅ $59+ | Free (AWS lock-in) | ~$125/node | Free (OSS) |
| Pipeline TD required | ❌ No | ✅ Yes | Minimal | Minimal |
| Vantage support | ✅ Native | ❌ | ❌ | ❌ |

---

## Development Workflow

### Before Making Changes

1. **Read the Critical Rules section** at the top of this file
2. **Search past project chats** for context on what you're modifying
3. **Check the current version** in `config.py`
4. **Understand what's working** — don't break functioning engines while fixing another
5. **Test all three engines** after any cross-cutting changes

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
| Hardware damage risk | Never modify GPU settings, always use read-only monitoring |

### Debugging Tips

- **Marmoset:** Check `%TEMP%` for `_wain_render_*.py` scripts and `_wain_marmoset_progress_*.json` files
- **Blender:** Run Wain.bat with `--debug` flag to see stdout in console
- **Vantage:** Check if pywinauto can find the window — run standalone test script first
- **All engines:** Check `wain_render_log.txt` for error details

### File Format Standards

- Config file: `wain_config.json`
- Output formats vary by engine (PNG, JPEG, EXR, TIFF, TGA)
- Temp scripts go to `%TEMP%` directory to avoid permission issues
- Progress tracking uses JSON files in `%TEMP%`

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
APP_VERSION = "2.19.5"  # Check actual value
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

Key milestones from iterative development across multiple chat sessions:

- **v1.0** — Monolithic single-file render manager
- **v1.1** — Modular architecture refactor (package structure)
- **v1.8** — Marmoset lowercase pass name fix
- **v2.1** — Discovered Marmoset API limitations (render-all-then-filter strategy)
- **v2.3** — Marmoset frameCount fix (use Timeline instead)
- **v2.9** — Vantage UI automation integration
- **v2.14** — Marmoset subprocess flag fix (CREATE_NO_WINDOW → SW_HIDE)
- **v2.15** — Vantage progress tracking fixes (high water mark, frame vs percentage)
- **v2.15.64** — Competitive research + feature roadmap
- **v2.16** — Marmoset multi-pass rendering + camera detection
- **v2.18** — Network stability: token auth, auto-reconnect, connection status UI
- **v2.19.0** — Visual redesign from companion Figma file (engine accent bars, gradient progress bars, brand header, wagon logo)
- **v2.19.3** — QtWebEngine GPU compositing enabled by default (`--software-ui` to opt out); software rendering was the root cause of UI sluggishness with richer styling
- **v2.19.5** — White-flash fix (dark webview base color), splash logo shown in true colors
- **v2.20.0** — Windows installer phase. PyInstaller bundle (`wain.spec`, entry `wain_app.py`) + Inno Setup installer (`installer.iss`) via `build_installer.bat`. Frozen builds: data in `%APPDATA%\Wain` (`wain/config.py get_data_dir()`), bootstrap skipped, stdout→`wain_console.log`, worker first-run setup dialog (`wain/network/worker_setup.py`), `multiprocessing.freeze_support()` required at entry
- **v2.21.0** — Current version: Unreal Engine support (4th engine, blue `#0d8de3`). Headless MRQ via `UnrealEditor-Cmd.exe` (out-of-process only — avoids in-editor teardown crash), output-folder file-count progress (VPN/worker friendly), `.uproject` probing (LauncherInstalled.dat discovery, `.uasset` header sniffing for sequences/presets), worker capability reporting (`unreal_versions`)

**Design source:** The static UI is designed and iterated in a companion Figma file ("Wain UI") before being ported to code. Keep app CSS and the Figma file in sync when changing visuals.

**Always search past project context before making changes to maintain continuity.**
