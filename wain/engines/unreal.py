"""
Wain - Unreal Engine
====================

Render engine implementation for Unreal Engine (Movie Render Queue).
v2.21.0 - Initial Unreal Engine support

https://github.com/sbuff25/RenderManager

Architecture: Headless out-of-process rendering via UnrealEditor-Cmd.exe.
The Movie Render Queue (MRQ) is driven entirely from the command line:

    UnrealEditor-Cmd.exe "<project>.uproject" <MapPath> -game
        -LevelSequence="<SequencePath>" -MoviePipelineConfig="<PresetPath>"
        -windowed -resx=1280 -resy=720 -log -stdout -unattended
        [-RenderOffscreen when the job's "Show preview window" is off]

Key design decisions:

1. OUT-OF-PROCESS ONLY. Wain never talks to a running editor - it spawns a
   fresh headless UnrealEditor-Cmd.exe per job. This sidesteps the well-known
   in-editor MRQ teardown crash (D3D12 refcount ensure on completion) and
   means a GPU device-hung frame kills the child process, not an editor.

2. FILE-COUNT PROGRESS (primary). MRQ's stdout does not reliably announce
   per-frame completion across UE versions, so Wain watches the output folder
   (recursively) and counts image files created after render start. This is
   the Royal Render philosophy: a frame is done when it's on disk. It also
   works transparently over VPN/UNC paths where a worker renders remotely.
   Stdout is still parsed for status/errors and streamed to the log (secondary).

3. RESOLUTION / FORMAT / FRAME RANGE come from the MRQ preset asset, not from
   Wain. The job's Output Folder must match the preset's Output Directory for
   progress tracking to work. Frame start/end on the job are used only for
   progress math (current/total), not to override the sequence.

Known log markers (UE 5.x):
    LogMovieRenderPipeline: MoviePipelineLinearExecutorBase starting N jobs.
    LogMovieRenderPipeline: ... (per-shot / warm-up / export lines)
    LogImageWriteQueue: ... (frame writes on some versions)
"""

import os
import json
import re
import subprocess
import threading
import time
from typing import Dict, Any, Optional, List

from wain.engines.base import RenderEngine


# Epic Games Launcher install manifest - the canonical list of UE installs
LAUNCHER_INSTALLED_DAT = r"C:\ProgramData\Epic\UnrealEngineLauncher\LauncherInstalled.dat"

# Image extensions MRQ can emit (used for output-folder frame counting)
FRAME_EXTENSIONS = {".exr", ".png", ".jpg", ".jpeg", ".bmp"}

# Stdout lines worth forwarding to the Wain log (UE output is extremely
# chatty - thousands of shader-compile lines - so we filter hard)
LOG_FORWARD_RE = re.compile(
    r"(LogMovieRenderPipeline|LogMoviePipeline|LogImageWriteQueue"
    r"|LogInit: Display: (Engine|Game) is initialized"
    r"|LogShaderCompilers:.*\d+ shaders left"
    r"|Fatal error|Assertion failed|GPU Crash|DEVICE_HUNG|DEVICE_REMOVED"
    r"|Error:)",
    re.IGNORECASE,
)

# Status-message extraction (shown on the job card, not just the log)
STATUS_PATTERNS = [
    (re.compile(r"LogShaderCompilers:.*?(\d+) shaders left"), "Compiling shaders ({0} left)"),
    (re.compile(r"MoviePipelineLinearExecutorBase starting (\d+) job"), "Starting render job..."),
    (re.compile(r"LogMovieRenderPipeline:.*Warm[- ]?[Uu]p"), "Warming up..."),
    (re.compile(r"LogMovieRenderPipeline:.*[Ff]inaliz"), "Finalizing output..."),
]

# Sequence-length auto-detection (v2.23.0). MRQ logs each shot's tick range
# at init, then announces every camera cut. Ticks-per-frame isn't logged, so:
#   1. When shot 1 starts, estimate total = ticks / 800 (24000 tick resolution
#      at 30 fps - the common case - so the bar is sensible immediately).
#   2. At every later shot boundary, recalibrate exactly from frames-on-disk:
#      ticks_per_frame = completed_ticks / frames_written.
SHOT_RANGE_RE = re.compile(r"Registering range: \[(\d+),(\d+)\) \(InnerName: (.+?) OuterName")
CAMERA_CUT_RE = re.compile(r"Initializing Camera Cut \[(\d+)/(\d+)\] in \[.*?\] (.+?)\.\s*$")
DEFAULT_TICKS_PER_FRAME = 800


class UnrealEngine(RenderEngine):
    """Unreal Engine (Movie Render Queue) integration."""

    name = "Unreal Engine"
    engine_type = "unreal"
    file_extensions = [".uproject"]
    icon = "movie"
    color = "#0d8de3"

    # Fallback search roots when LauncherInstalled.dat is missing.
    # Epic installs default to "<drive>:\Program Files\Epic Games\UE_X.Y" but
    # users commonly relocate to "<drive>:\Epic Games\UE_X.Y".
    SEARCH_DRIVE_SUFFIXES = [
        r"Program Files\Epic Games",
        r"Epic Games",
    ]

    # Output format is governed by the MRQ preset; "Preset" is the honest
    # default. The rest are informational labels only.
    OUTPUT_FORMATS = {"Preset": "PRESET", "EXR": "EXR", "PNG": "PNG", "JPEG": "JPG"}

    # Cap for .uasset class-sniffing during probe (keeps probing fast on
    # multi-thousand-asset projects; 64KB covers the import table region)
    PROBE_MAX_ASSETS = 20000
    PROBE_READ_BYTES = 65536

    # Output-folder poll cadence while rendering
    POLL_INTERVAL_SECONDS = 2.0

    def __init__(self):
        super().__init__()
        self.scan_installed_versions()

    # ------------------------------------------------------------------
    # Version discovery
    # ------------------------------------------------------------------

    def scan_installed_versions(self):
        self.installed_versions = {}

        # 1) Canonical: Epic Launcher's install manifest
        try:
            if os.path.exists(LAUNCHER_INSTALLED_DAT):
                with open(LAUNCHER_INSTALLED_DAT, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                for entry in data.get("InstallationList", []):
                    app = entry.get("AppName", "")
                    loc = entry.get("InstallLocation", "")
                    if not app.startswith("UE_") or not loc:
                        continue
                    exe = os.path.join(loc, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")
                    if os.path.exists(exe):
                        self.installed_versions[app[3:]] = exe  # "UE_5.8" -> "5.8"
        except Exception:
            pass

        # 2) Fallback: scan common folders on all fixed drives
        try:
            import string
            for letter in string.ascii_uppercase:
                for suffix in self.SEARCH_DRIVE_SUFFIXES:
                    base = f"{letter}:\\{suffix}"
                    if not os.path.isdir(base):
                        continue
                    for entry in os.listdir(base):
                        if not entry.startswith("UE_"):
                            continue
                        exe = os.path.join(base, entry, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")
                        version = entry[3:]
                        if version not in self.installed_versions and os.path.exists(exe):
                            self.installed_versions[version] = exe
        except Exception:
            pass

        return self.installed_versions

    def add_custom_path(self, path: str) -> Optional[str]:
        """Accept a path to UnrealEditor-Cmd.exe (or an engine root folder)."""
        if os.path.isdir(path):
            candidate = os.path.join(path, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")
            if os.path.exists(candidate):
                path = candidate
        if os.path.exists(path) and path.lower().endswith("unrealeditor-cmd.exe"):
            # Derive version from the folder name if it matches UE_X.Y
            version = "custom"
            m = re.search(r"UE_(\d+\.\d+)", path)
            if m:
                version = m.group(1)
            self.installed_versions[version] = path
            return version
        return None

    def get_exe_for_project(self, uproject_path: str) -> Optional[str]:
        """Pick the best UnrealEditor-Cmd.exe for a .uproject.

        Uses the project's EngineAssociation (e.g. "5.8") when it matches an
        installed version; otherwise falls back to the newest install.
        """
        if not self.installed_versions:
            return None
        assoc = ""
        try:
            with open(uproject_path, "r", encoding="utf-8-sig") as f:
                assoc = str(json.load(f).get("EngineAssociation", ""))
        except Exception:
            pass
        if assoc:
            for version, exe in self.installed_versions.items():
                if version == assoc or version.startswith(assoc):
                    return exe
        newest = sorted(self.installed_versions.keys(), reverse=True)[0]
        return self.installed_versions[newest]

    # ------------------------------------------------------------------
    # Scene probing
    # ------------------------------------------------------------------

    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """Probe a .uproject without launching the engine.

        Launching a headless editor to introspect assets costs minutes, so
        instead we:
          - parse the .uproject JSON for the engine version
          - scan Content/ for .umap files (maps)
          - sniff .uasset headers for LevelSequence / MoviePipelinePrimaryConfig
            class imports (sequences and MRQ presets)
        File paths are converted to UE soft object paths:
          <Project>/Content/Foo/Bar.umap -> /Game/Foo/Bar
        """
        info: Dict[str, Any] = {
            "cameras": [], "active_camera": "",
            # 0x0 = "the MRQ preset decides" - keeps stale defaults out of the UI
            "resolution_x": 0, "resolution_y": 0,
            "frame_start": 1, "frame_end": 1, "has_animation": True,
            "engine_version": "", "maps": [], "sequences": [], "presets": [],
        }
        if not os.path.exists(file_path):
            return info

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                info["engine_version"] = str(json.load(f).get("EngineAssociation", ""))
        except Exception:
            pass

        content_dir = os.path.join(os.path.dirname(file_path), "Content")
        if not os.path.isdir(content_dir):
            return info

        def to_game_path(full: str) -> str:
            rel = os.path.relpath(full, content_dir)
            rel = os.path.splitext(rel)[0].replace("\\", "/")
            return f"/Game/{rel}"

        maps: List[str] = []
        sequences: List[str] = []
        presets: List[str] = []
        scanned = 0

        for root, dirs, files in os.walk(content_dir):
            # Skip UE-internal folders that never hold user render assets
            dirs[:] = [d for d in dirs if d not in ("__ExternalActors__", "__ExternalObjects__", "Developers")]
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                full = os.path.join(root, fn)
                if ext == ".umap":
                    maps.append(to_game_path(full))
                elif ext == ".uasset":
                    scanned += 1
                    if scanned > self.PROBE_MAX_ASSETS:
                        continue
                    try:
                        with open(full, "rb") as f:
                            head = f.read(self.PROBE_READ_BYTES)
                        if b"MoviePipelinePrimaryConfig" in head or b"MoviePipelineMasterConfig" in head:
                            presets.append(to_game_path(full))
                        elif b"LevelSequence" in head:
                            sequences.append(to_game_path(full))
                    except Exception:
                        continue

        info["maps"] = sorted(maps)
        info["sequences"] = sorted(sequences)
        info["presets"] = sorted(presets)
        return info

    def get_preset_output_dir(self, uproject_path: str, preset_path: str):
        """Best-effort: read the MRQ preset's Output Directory from its .uasset.

        The preset asset stores the directory as a plain string (usually
        '{project_dir}/Saved/MovieRenders/...'). We scan for it, resolve
        {project_dir} against the .uproject location, and drop any trailing
        segments containing unresolved tokens like {date} - a static parent
        folder is fine because frame counting walks recursively.
        Returns an absolute path or None.
        """
        try:
            project_dir = os.path.dirname(os.path.abspath(uproject_path))
            rel = preset_path.replace("/Game/", "", 1)
            asset = os.path.join(project_dir, "Content", rel + ".uasset")
            if not os.path.exists(asset):
                return None
            with open(asset, "rb") as f:
                data = f.read()
            candidates = []
            for m in re.finditer(rb"[ -~]{6,}", data):
                s = m.group().decode("ascii", "ignore")
                if ("{project_dir}" in s or "MovieRenders" in s
                        or re.match(r"^[A-Za-z]:[\\/].{3,}", s)):
                    candidates.append(s)
            if not candidates:
                # OutputDirectory left at MRQ's default - UE doesn't serialize
                # default values, so the string simply isn't in the asset
                return os.path.join(project_dir, "Saved", "MovieRenders")
            # Prefer the {project_dir} token form - it's MRQ's default and
            # machine-portable (resolves correctly on any worker)
            best = next((s for s in candidates if "{project_dir}" in s), candidates[0])
            segments = re.split(r"[\\/]+", best)
            clean = []
            for seg in segments:
                if "{" in seg and seg != "{project_dir}":
                    break  # unresolved token ({date}, {sequence_name}, ...)
                clean.append(seg)
            if not clean:
                return None
            path = "/".join(clean).replace("{project_dir}", project_dir)
            return os.path.normpath(path)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS

    def get_default_settings(self) -> Dict[str, Any]:
        return {"map_path": "", "sequence_path": "", "preset_path": "",
                "extra_args": "", "show_preview": True,
                # v2.25.0 - Wain-side overrides via the Python executor
                "use_overrides": True,
                "file_name_format": "{sequence_name}.{frame_number}",
                "frame_start_override": None,
                "frame_end_override": None}

    # Directory holding init_unreal.py (the Wain MRQ executor). Delivered to
    # UE via the UE_PYTHONPATH env var - never copied into the project, so a
    # mirrored project sync can't delete it.
    @staticmethod
    def _ue_scripts_dir() -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ue_scripts")

    @staticmethod
    def _image_dims(path: str):
        """Read pixel dimensions from a rendered frame (EXR/PNG/JPG/BMP).

        EXR is parsed by hand (PIL doesn't read it): scan the header for the
        dataWindow box2i attribute. Returns (width, height) or None.
        """
        try:
            if path.lower().endswith(".exr"):
                import struct
                with open(path, "rb") as f:
                    head = f.read(16384)
                # displayWindow = the delivered frame (overscan cropped);
                # dataWindow may be padded with camera overscan pixels
                i = head.find(b"displayWindow")
                if i < 0:
                    i = head.find(b"dataWindow")
                if i < 0:
                    return None
                i = head.find(b"box2i", i)
                if i < 0:
                    return None
                x0, y0, x1, y1 = struct.unpack("<4i", head[i + 10:i + 26])
                return (x1 - x0 + 1, y1 - y0 + 1)
            from PIL import Image
            with Image.open(path) as img:
                return img.size
        except Exception:
            return None

    def _snapshot_output(self, folder: str) -> set:
        """Set of image files currently in the output folder (recursive)."""
        found = set()
        try:
            for root, _dirs, files in os.walk(folder):
                for fn in files:
                    if os.path.splitext(fn)[1].lower() in FRAME_EXTENSIONS:
                        found.add(os.path.join(root, fn))
        except Exception:
            pass
        return found

    def start_render(self, job, start_frame, on_progress, on_complete, on_error, on_log=None):
        exe = self.get_exe_for_project(job.file_path)
        if not exe:
            on_error("No Unreal Engine installation found (looked for UnrealEditor-Cmd.exe)")
            return
        if not os.path.exists(job.file_path):
            on_error(f"Project not found: {job.file_path}")
            return

        settings = job.engine_settings or {}
        map_path = (settings.get("map_path") or "").strip()
        sequence_path = (settings.get("sequence_path") or "").strip()
        preset_path = (settings.get("preset_path") or "").strip()
        if not map_path or not sequence_path or not preset_path:
            on_error("Unreal jobs need a Map, Level Sequence, and MRQ Preset (see job settings)")
            return

        self.is_cancelling = False
        os.makedirs(job.output_folder, exist_ok=True)

        # show_preview: render in a visible game window (MRQ progress overlay,
        # frames appear as they're drawn). Off = -RenderOffscreen, fully headless.
        show_preview = bool(settings.get("show_preview", True))

        # v2.25.0: with use_overrides, launch through the Wain Python executor
        # (MoviePipelinePythonHostExecutor) so the job's Output Folder, file
        # naming, and optional frame range actually control the render. The
        # preset still supplies every quality setting. Falls back to the
        # legacy stock command if the script directory is missing.
        def _to_int(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        f_start = _to_int(settings.get("frame_start_override"))
        f_end = _to_int(settings.get("frame_end_override"))
        have_range = f_start is not None and f_end is not None and f_end >= f_start
        file_name_format = (settings.get("file_name_format") or "").strip()
        scripts_dir = self._ue_scripts_dir()
        use_overrides = (bool(settings.get("use_overrides", True))
                         and os.path.exists(os.path.join(scripts_dir, "init_unreal.py")))

        common = [
            "-windowed", "-resx=1280", "-resy=720",
            "-log", "-stdout", "-FullStdOutLogOutput",
            "-unattended",
            "-NoSplash", "-NoLoadingScreen",
        ]
        if use_overrides:
            # Load the map under MoviePipelineGameMode (what the stock MRQ
            # command line does implicitly) - the project's normal game mode
            # would run gameplay systems during the render
            mrq_map = f"{map_path}?game=/Script/MovieRenderPipelineCore.MoviePipelineGameMode"
            cmd = [
                exe, job.file_path, mrq_map, "-game",
                "-MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor",
                "-ExecutorPythonClass=/Engine/PythonTypes.WainMRQExecutor",
                *common,
                f"-WainMap={map_path}",
                f"-WainSequence={sequence_path}",
                f"-WainPreset={preset_path}",
                f"-WainJobName={job.name or 'Wain Render'}",
                f"-WainOutputDir={job.output_folder.replace(chr(92), '/')}",
            ]
            if file_name_format:
                cmd.append(f"-WainFileName={file_name_format}")
            if have_range:
                cmd.append(f"-WainStartFrame={f_start}")
                cmd.append(f"-WainEndFrame={f_end}")
        else:
            cmd = [
                exe, job.file_path, map_path, "-game",
                f"-LevelSequence={sequence_path}",
                f"-MoviePipelineConfig={preset_path}",
                *common,
            ]
        if not show_preview:
            cmd.append("-RenderOffscreen")
        extra = (settings.get("extra_args") or "").strip()
        if extra:
            cmd.extend(extra.split())

        if on_log:
            on_log(f"[Unreal] Engine: {exe}")
            on_log(f"[Unreal] Command: {' '.join(cmd)}")
            if use_overrides:
                on_log("[Unreal] Wain executor: output dir/naming"
                       + (f" and frame range {f_start}-{f_end}" if have_range else "")
                       + " override the preset; quality settings come from the preset.")
            else:
                on_log("[Unreal] Legacy launch: resolution/format/frame-range come from "
                       "the MRQ preset; progress is tracked by files in the output folder.")

        # Frames present before we start don't count toward progress
        preexisting = self._snapshot_output(job.output_folder)
        total_frames = max(1, job.frame_end - job.frame_start + 1) if job.is_animation else 1
        shot_spans: List[tuple] = []  # (start_tick, end_tick, name) per shot, from MRQ log
        # Live shot context for the job card: which camera cut is rendering,
        # and the tick->frame conversion once calibrated
        shot_state = {"idx": 0, "total": 0, "name": "", "tpf": DEFAULT_TICKS_PER_FRAME}

        def apply_total(n: int, source: str):
            """Adopt a detected sequence length: fixes the progress denominator
            and rewrites the job's frame range so the UI shows real numbers."""
            nonlocal total_frames
            n = max(1, int(round(n)))
            if n == total_frames:
                return
            total_frames = n
            job.is_animation = True
            job.frame_start = 1
            job.frame_end = n
            if on_log:
                on_log(f"[Unreal] Sequence length {source}: {n} frames")

        # A Wain-specified range fixes the total upfront; otherwise the log
        # calibration below detects it during the render
        if use_overrides and have_range:
            apply_total(f_end - f_start + 1, "specified")

        def render_thread():
            nonlocal total_frames
            try:
                # Hide the child's window only for offscreen renders -
                # STARTF_USESHOWWINDOW defaults wShowWindow to SW_HIDE, which
                # would swallow the preview window the user asked for
                startupinfo = subprocess.STARTUPINFO()
                if not show_preview:
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                for key in ["QTWEBENGINE_CHROMIUM_FLAGS", "QT_QUICK_BACKEND",
                            "QTWEBENGINE_DISABLE_SANDBOX", "QT_API", "PYWEBVIEW_GUI"]:
                    env.pop(key, None)

                # Deliver the Wain MRQ executor to UE's Python plugin
                if use_overrides:
                    prior = env.get("UE_PYTHONPATH", "")
                    env["UE_PYTHONPATH"] = scripts_dir + (os.pathsep + prior if prior else "")

                self.current_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    startupinfo=startupinfo, env=env,
                )

                seen_frames = 0
                fatal_lines: List[str] = []
                stop_polling = threading.Event()

                def poll_output_folder():
                    """Count delivered frames on disk - the primary progress signal."""
                    nonlocal seen_frames
                    while not stop_polling.wait(self.POLL_INTERVAL_SECONDS):
                        if self.is_cancelling:
                            return
                        current = self._snapshot_output(job.output_folder) - preexisting
                        n = len(current)
                        if n > seen_frames:
                            # First delivered frame: read the real output size
                            # (the MRQ preset governs it; the job starts at 0x0)
                            if seen_frames == 0 and not job.res_width:
                                dims = self._image_dims(sorted(current)[0])
                                if dims:
                                    job.res_width, job.res_height = dims
                                    if on_log:
                                        on_log(f"[Unreal] Output resolution detected: {dims[0]}x{dims[1]}")
                            seen_frames = n
                            msg = f"Frame {n}/{total_frames} written"
                            # Enrich with live shot context when we have it:
                            # "Shot 3/12 Garage-WingSpin-01 - frame 32/150 (21%)"
                            idx = shot_state["idx"]
                            if idx >= 1 and idx <= len(shot_spans):
                                tpf = shot_state["tpf"] or DEFAULT_TICKS_PER_FRAME
                                before = sum(e - s for s, e, _n2 in shot_spans[:idx - 1])
                                s, e, _n2 = shot_spans[idx - 1]
                                shot_len = max(1, round((e - s) / tpf))
                                in_shot = max(0, min(shot_len, n - round(before / tpf)))
                                pct = int(in_shot / shot_len * 100)
                                msg = (f"Shot {idx}/{shot_state['total']} "
                                       f"{shot_state['name']} - frame {in_shot}/{shot_len} ({pct}%) "
                                       f"- total {n}/{total_frames}")
                            if job.is_animation:
                                # app.py convention: report the frame number,
                                # then -1 to commit it as "saved"
                                on_progress(job.frame_start + n - 1, msg)
                                on_progress(-1, msg)
                            else:
                                on_progress(-1, msg)

                poller = threading.Thread(target=poll_output_folder, daemon=True)
                poller.start()

                while True:
                    if self.is_cancelling:
                        break
                    try:
                        line_bytes = self.current_process.stdout.readline()
                        if not line_bytes:
                            break
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        safe_line = "".join(c if 32 <= ord(c) < 127 else "?" for c in line)

                        if re.search(r"Fatal error|Assertion failed|GPU Crash|DEVICE_HUNG|DEVICE_REMOVED", line, re.IGNORECASE):
                            fatal_lines.append(safe_line)

                        # Sequence-length auto-detection from MRQ's shot bookkeeping
                        m = SHOT_RANGE_RE.search(line)
                        if m:
                            span = (int(m.group(1)), int(m.group(2)), m.group(3).strip())
                            # The Python-executor path can log each shot's
                            # range twice - counting duplicates doubles the
                            # estimated total (observed: 3902 vs 1951)
                            if all(span[:2] != s[:2] for s in shot_spans):
                                shot_spans.append(span)
                        m = CAMERA_CUT_RE.search(line)
                        if m and shot_spans:
                            cut_idx = int(m.group(1))  # 1-based
                            shot_state["idx"] = cut_idx
                            shot_state["total"] = int(m.group(2))
                            shot_state["name"] = m.group(3).strip()
                            total_ticks = sum(e - s for s, e, _n in shot_spans)
                            if cut_idx == 1:
                                # Provisional estimate so the bar is sane from frame 1
                                apply_total(total_ticks / DEFAULT_TICKS_PER_FRAME, "estimated")
                            elif cut_idx - 1 <= len(shot_spans):
                                # Exact recalibration: ticks completed vs frames on disk
                                done_ticks = sum(e - s for s, e, _n in shot_spans[:cut_idx - 1])
                                frames_done = len(self._snapshot_output(job.output_folder) - preexisting)
                                if done_ticks > 0 and frames_done > 0:
                                    ticks_per_frame = done_ticks / frames_done
                                    shot_state["tpf"] = ticks_per_frame
                                    apply_total(total_ticks / ticks_per_frame, "detected")

                        if on_log and LOG_FORWARD_RE.search(line):
                            on_log(safe_line)

                        # Surface friendly status text on the job card
                        for pattern, template in STATUS_PATTERNS:
                            m = pattern.search(line)
                            if m:
                                status = template.format(*m.groups()) if m.groups() else template
                                on_progress(0, status)
                                break
                    except Exception:
                        continue

                return_code = self.current_process.wait()
                stop_polling.set()

                # Final frame count (poller may not have caught the last write)
                final_frames = len(self._snapshot_output(job.output_folder) - preexisting)
                self.current_process = None

                if self.is_cancelling:
                    return

                if return_code == 0:
                    if on_log:
                        on_log(f"[Unreal] Finished - {final_frames} frame(s) written, exit code 0")
                    on_complete()
                elif final_frames >= total_frames and total_frames > 1:
                    # All expected frames are on disk; a nonzero exit here is a
                    # teardown quirk, not a failed render. Complete with a note.
                    if on_log:
                        on_log(f"[Unreal] WARNING: exit code {return_code} but all "
                               f"{final_frames}/{total_frames} frames are on disk - treating as complete")
                    on_complete()
                else:
                    detail = f"; {fatal_lines[-1]}" if fatal_lines else ""
                    on_error(f"Unreal exited with code {return_code} "
                             f"({final_frames}/{total_frames} frames written){detail}")

            except Exception as e:
                self.current_process = None
                if not self.is_cancelling:
                    on_error(str(e))

        threading.Thread(target=render_thread, daemon=True).start()

    def cancel_render(self):
        self.is_cancelling = True
        proc = self.current_process
        self.current_process = None
        if proc:
            # terminate() asks politely and UE can take many seconds to comply
            # (or ignore it mid-D3D work). Kill hard, then sweep the whole
            # process tree so ShaderCompileWorker children die too (v2.25.2).
            try:
                proc.kill()
            except Exception:
                pass
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass

    def open_file_in_app(self, file_path: str, version: str = None):
        """Open the project in the full (GUI) editor."""
        exe = self.get_exe_for_project(file_path)
        if exe:
            gui_exe = exe.replace("UnrealEditor-Cmd.exe", "UnrealEditor.exe")
            if os.path.exists(gui_exe):
                subprocess.Popen([gui_exe, file_path], creationflags=subprocess.DETACHED_PROCESS)
