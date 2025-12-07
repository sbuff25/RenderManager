#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render Manager - Multi-Engine Edition (ITT04-Native Desktop)
Queue-based render management with pause/resume support
Supports: Blender, Marmoset Toolbag

Built with NiceGUI + pywebview (Qt backend) for native desktop window
Works on Python 3.10+
"""

# ============================================================================
# AUTOMATIC DEPENDENCY INSTALLATION
# ============================================================================
# This section checks for and installs required packages on first run.
# Must run BEFORE any third-party imports!

def _check_and_install_dependencies():
    """Check for required packages and install if missing."""
    import subprocess
    import sys
    
    REQUIRED_PACKAGES = [
        ('nicegui', 'nicegui'),
        ('webview', 'pywebview'),
        ('PyQt6', 'PyQt6'),
    ]
    
    missing = []
    
    for import_name, pip_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    
    if missing:
        print("=" * 60)
        print("Render Manager - First Run Setup")
        print("=" * 60)
        print(f"\nInstalling required packages: {', '.join(missing)}")
        print("This only happens once...\n")
        
        for package in missing:
            print(f"  Installing {package}...")
            try:
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install', package],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT
                )
                print(f"  ✓ {package} installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"  ✗ Failed to install {package}")
                print(f"    Please run: pip install {package}")
                sys.exit(1)
        
        print("\n" + "=" * 60)
        print("Setup complete! Starting Render Manager...")
        print("=" * 60 + "\n")

# Run dependency check before any imports
_check_and_install_dependencies()

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================
# CRITICAL: Set these BEFORE any other imports!
import os
os.environ['QT_API'] = 'pyqt6'           # Tell qtpy to use PyQt6
os.environ['PYWEBVIEW_GUI'] = 'qt'       # Tell pywebview to use Qt backend

import subprocess
import threading
import sys
import json
import re
import tempfile
import uuid
import gzip
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from pathlib import Path

from nicegui import ui, app

# ============================================================================
# SUPPRESS ALL NOTIFICATIONS (Desktop app - no need for toasts)
# ============================================================================
# Store the original notify function and replace with no-op
_original_notify = ui.notify

def _silent_notify(*args, **kwargs):
    """Silent replacement for ui.notify - we're a desktop app."""
    pass

# Monkey-patch ui.notify to be silent
ui.notify = _silent_notify

# ============================================================================
# FILE DIALOGS - Run in background thread with subprocess isolation
# ============================================================================
# Native file dialogs conflict with Qt/pywebview in the same process,
# so we spawn a separate Python process for the tkinter dialog.
# We use a result container and polling to safely update the UI.

# Global storage for pending file dialog results
_pending_file_results = {}
_result_counter = 0
_result_lock = threading.Lock()

def _run_file_dialog_subprocess(title: str, filetypes: list, initial_dir: str) -> Optional[str]:
    """Run file dialog in subprocess - called from background thread."""
    import subprocess
    import sys
    import json as json_module
    
    script = '''
import tkinter as tk
from tkinter import filedialog
import sys
import json

args = json.loads(sys.argv[1])
title = args.get('title', 'Select File')
filetypes = args.get('filetypes', [])
initial_dir = args.get('initial_dir', '')

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
root.lift()
root.update()

tk_filetypes = []
for name, pattern in filetypes:
    tk_filetypes.append((name, pattern))
tk_filetypes.append(('All Files', '*.*'))

result = filedialog.askopenfilename(
    title=title,
    filetypes=tk_filetypes,
    initialdir=initial_dir if initial_dir else None
)

print(result if result else '')
root.destroy()
'''
    
    args = {
        'title': title,
        'filetypes': filetypes or [],
        'initial_dir': initial_dir or ''
    }
    
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        proc = subprocess.Popen(
            [sys.executable, '-c', script, json_module.dumps(args)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags
        )
        stdout, stderr = proc.communicate(timeout=300)
        path = stdout.decode('utf-8').strip()
        if path and os.path.exists(path):
            return path
    except Exception as e:
        print(f"File dialog error: {e}")
    return None


def _run_folder_dialog_subprocess(title: str, initial_dir: str) -> Optional[str]:
    """Run folder dialog in subprocess - called from background thread."""
    import subprocess
    import sys
    import json as json_module
    
    script = '''
import tkinter as tk
from tkinter import filedialog
import sys
import json

args = json.loads(sys.argv[1])
title = args.get('title', 'Select Folder')
initial_dir = args.get('initial_dir', '')

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
root.lift()
root.update()

result = filedialog.askdirectory(
    title=title,
    initialdir=initial_dir if initial_dir else None
)

print(result if result else '')
root.destroy()
'''
    
    args = {
        'title': title,
        'initial_dir': initial_dir or ''
    }
    
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        proc = subprocess.Popen(
            [sys.executable, '-c', script, json_module.dumps(args)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags
        )
        stdout, stderr = proc.communicate(timeout=300)
        path = stdout.decode('utf-8').strip()
        if path and os.path.isdir(path):
            return path
    except Exception as e:
        print(f"Folder dialog error: {e}")
    return None


def open_file_dialog_async(title: str, filetypes: List[tuple], initial_dir: str, callback: Callable[[Optional[str]], None]):
    """Open file dialog in background thread, call callback with result via polling."""
    global _result_counter
    
    with _result_lock:
        _result_counter += 1
        result_id = _result_counter
        _pending_file_results[result_id] = {'done': False, 'result': None, 'callback': callback}
    
    def run():
        result = _run_file_dialog_subprocess(title, filetypes, initial_dir)
        with _result_lock:
            if result_id in _pending_file_results:
                _pending_file_results[result_id]['result'] = result
                _pending_file_results[result_id]['done'] = True
    
    threading.Thread(target=run, daemon=True).start()
    
    # Start polling timer (created on main thread)
    def check_result():
        with _result_lock:
            if result_id in _pending_file_results:
                entry = _pending_file_results[result_id]
                if entry['done']:
                    result = entry['result']
                    cb = entry['callback']
                    del _pending_file_results[result_id]
                    cb(result)
                    return  # Stop polling
        # Keep polling
        ui.timer(0.1, check_result, once=True)
    
    ui.timer(0.1, check_result, once=True)


def open_folder_dialog_async(title: str, initial_dir: str, callback: Callable[[Optional[str]], None]):
    """Open folder dialog in background thread, call callback with result via polling."""
    global _result_counter
    
    with _result_lock:
        _result_counter += 1
        result_id = _result_counter
        _pending_file_results[result_id] = {'done': False, 'result': None, 'callback': callback}
    
    def run():
        result = _run_folder_dialog_subprocess(title, initial_dir)
        with _result_lock:
            if result_id in _pending_file_results:
                _pending_file_results[result_id]['result'] = result
                _pending_file_results[result_id]['done'] = True
    
    threading.Thread(target=run, daemon=True).start()
    
    # Start polling timer (created on main thread)
    def check_result():
        with _result_lock:
            if result_id in _pending_file_results:
                entry = _pending_file_results[result_id]
                if entry['done']:
                    result = entry['result']
                    cb = entry['callback']
                    del _pending_file_results[result_id]
                    cb(result)
                    return  # Stop polling
        # Keep polling
        ui.timer(0.1, check_result, once=True)
    
    ui.timer(0.1, check_result, once=True)


# ============================================================================
# THEME CONFIGURATION
# ============================================================================
DARK_THEME = {
    'dark': True,
    'colors': {
        'primary': '#3b82f6',
        'secondary': '#6b7280',
        'accent': '#8b5cf6',
        'positive': '#22c55e',
        'negative': '#ef4444',
        'info': '#3b82f6',
        'warning': '#f59e0b',
    }
}

ENGINE_COLORS = {"blender": "#ea7600", "marmoset": "#06b6d4"}

STATUS_CONFIG = {
    "rendering": {"color": "blue", "icon": "play_circle", "bg": "blue-900"},
    "queued": {"color": "yellow", "icon": "schedule", "bg": "yellow-900"},
    "paused": {"color": "orange", "icon": "pause_circle", "bg": "orange-900"},
    "completed": {"color": "green", "icon": "check_circle", "bg": "green-900"},
    "failed": {"color": "red", "icon": "error", "bg": "red-900"},
}


# ============================================================================
# DATA MODELS
# ============================================================================
@dataclass
class RenderJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    engine_type: str = "blender"
    file_path: str = ""
    output_folder: str = ""
    output_name: str = "render_"
    output_format: str = "PNG"
    status: str = "queued"
    progress: int = 0
    is_animation: bool = False
    frame_start: int = 1
    frame_end: int = 250
    current_frame: int = 0
    original_start: int = 0
    res_width: int = 1920
    res_height: int = 1080
    camera: str = "Scene Default"
    engine_settings: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    elapsed_time: str = ""
    accumulated_seconds: int = 0
    error_message: str = ""
    
    @property
    def frames_display(self) -> str:
        if self.is_animation:
            if self.current_frame > 0 and self.current_frame >= self.frame_start:
                next_frame = self.current_frame + 1
                if next_frame <= self.frame_end:
                    # Only show "paused at" when actually paused, not when rendering
                    if self.status == "paused":
                        return f"{next_frame}-{self.frame_end} (paused at {self.current_frame})"
                    else:
                        # When rendering, show current progress
                        return f"{self.current_frame}/{self.frame_end}"
                return f"Complete ({self.frame_start}-{self.frame_end})"
            return f"{self.frame_start}-{self.frame_end}"
        return str(self.frame_start)
    
    @property 
    def resolution_display(self) -> str:
        return f"{self.res_width}x{self.res_height}"
    
    @property
    def file_name(self) -> str:
        return os.path.basename(self.file_path) if self.file_path else ""
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.engine_settings.get(key, default)


@dataclass
class AppSettings:
    engine_paths: Dict[str, Dict[str, str]] = field(default_factory=dict)
    default_versions: Dict[str, str] = field(default_factory=dict)
    default_engine_type: str = "blender"


# ============================================================================
# RENDER ENGINE BASE
# ============================================================================
class RenderEngine(ABC):
    name: str = "Unknown"
    engine_type: str = "unknown"
    file_extensions: List[str] = []
    icon: str = "help"
    color: str = "#888888"
    
    def __init__(self):
        self.installed_versions: Dict[str, str] = {}
        self.current_process: Optional[subprocess.Popen] = None
        self.is_cancelling = False
    
    @abstractmethod
    def scan_installed_versions(self): pass
    
    @abstractmethod
    def get_scene_info(self, file_path: str) -> Dict[str, Any]: pass
    
    @abstractmethod
    def start_render(self, job, start_frame, on_progress, on_complete, on_error, on_log=None): pass
    
    @abstractmethod
    def cancel_render(self): pass
    
    @abstractmethod
    def get_output_formats(self) -> Dict[str, str]: pass
    
    @abstractmethod
    def get_default_settings(self) -> Dict[str, Any]: pass
    
    def add_custom_path(self, path: str) -> Optional[str]:
        return None
    
    @property
    def is_available(self) -> bool:
        return len(self.installed_versions) > 0
    
    @property
    def version_display(self) -> str:
        if self.installed_versions:
            newest = sorted(self.installed_versions.keys(), reverse=True)[0]
            return f"{self.name} {newest}"
        return f"{self.name} not detected"
    
    def open_file_in_app(self, file_path: str, version: str = None):
        pass
    
    def get_file_dialog_filter(self) -> List[tuple]:
        ext_str = " ".join(f"*{ext}" for ext in self.file_extensions)
        return [(f"{self.name} Files", ext_str)]


# ============================================================================
# BLENDER ENGINE
# ============================================================================
class BlenderEngine(RenderEngine):
    name = "Blender"
    engine_type = "blender"
    file_extensions = [".blend"]
    icon = "view_in_ar"
    color = "#ea7600"
    
    SEARCH_PATHS = [
        r"C:\Program Files\Blender Foundation\Blender 4.5",
        r"C:\Program Files\Blender Foundation\Blender 4.4",
        r"C:\Program Files\Blender Foundation\Blender 4.3",
        r"C:\Program Files\Blender Foundation\Blender 4.2",
        r"C:\Program Files\Blender Foundation\Blender 4.1",
        r"C:\Program Files\Blender Foundation\Blender 4.0",
        r"C:\Program Files\Blender Foundation\Blender 3.6",
    ]
    
    OUTPUT_FORMATS = {"PNG": "PNG", "JPEG": "JPEG", "OpenEXR": "OPEN_EXR", "TIFF": "TIFF"}
    COMPUTE_DEVICES = {"Auto": "AUTO", "OptiX": "OPTIX", "CUDA": "CUDA", "HIP": "HIP", "CPU": "CPU"}
    
    def __init__(self):
        super().__init__()
        self.temp_script_path: Optional[str] = None
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        self.installed_versions = {}
        for base_path in self.SEARCH_PATHS:
            exe_path = os.path.join(base_path, "blender.exe")
            if os.path.exists(exe_path):
                version = self._get_version_from_exe(exe_path)
                if version:
                    self.installed_versions[version] = exe_path
    
    def _get_version_from_exe(self, exe_path: str) -> Optional[str]:
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run([exe_path, "--version"], capture_output=True, timeout=10, startupinfo=startupinfo)
            stdout = result.stdout.decode('utf-8', errors='replace')
            for line in stdout.split('\n'):
                if line.strip().startswith('Blender '):
                    return line.split()[1]
        except:
            pass
        return None
    
    def add_custom_path(self, path: str) -> Optional[str]:
        if os.path.exists(path):
            version = self._get_version_from_exe(path)
            if version:
                self.installed_versions[version] = path
                return version
        return None
    
    def get_blend_file_version(self, blend_path: str) -> Optional[str]:
        try:
            with open(blend_path, 'rb') as f:
                header = f.read(12)
                if header[:2] == b'\x1f\x8b':
                    with gzip.open(blend_path, 'rb') as gz:
                        header = gz.read(12)
                if header[:7] != b'BLENDER':
                    return None
                version_bytes = header[9:12]
                version_str = version_bytes.decode('ascii')
                return f"{int(version_str[0])}.{int(version_str[1:3])}.0"
        except:
            return None
    
    def get_best_blender_for_file(self, blend_path: str) -> Optional[str]:
        if self.installed_versions:
            versions = sorted(self.installed_versions.keys(), reverse=True)
            return self.installed_versions[versions[0]]
        return None
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        default_info = {
            "cameras": ["Scene Default"], "active_camera": "Scene Default",
            "resolution_x": 1920, "resolution_y": 1080, "engine": "Cycles",
            "samples": 128, "frame_start": 1, "frame_end": 250,
        }
        
        blender_exe = self.get_best_blender_for_file(file_path)
        if not blender_exe or not os.path.exists(file_path):
            return default_info
        
        script = '''import bpy
scene = bpy.context.scene
render = scene.render
print("INFO_START")
print("CAMERAS_START")
for obj in bpy.data.objects:
    if obj.type == "CAMERA":
        print(f"CAM:{obj.name}")
print("CAMERAS_END")
if scene.camera:
    print(f"ACTIVE_CAMERA:{scene.camera.name}")
else:
    print("ACTIVE_CAMERA:Scene Default")
print(f"RES_X:{render.resolution_x}")
print(f"RES_Y:{render.resolution_y}")
engine_map = {"CYCLES": "Cycles", "BLENDER_EEVEE_NEXT": "Eevee", "BLENDER_WORKBENCH": "Workbench"}
print(f"ENGINE:{engine_map.get(render.engine, 'Cycles')}")
if render.engine == "CYCLES":
    print(f"SAMPLES:{scene.cycles.samples}")
else:
    print("SAMPLES:128")
print(f"FRAME_START:{scene.frame_start}")
print(f"FRAME_END:{scene.frame_end}")
print("INFO_END")
'''
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                temp_path = f.name
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run([blender_exe, "-b", file_path, "--python", temp_path],
                                  capture_output=True, timeout=60, startupinfo=startupinfo)
            os.unlink(temp_path)
            
            stdout = result.stdout.decode('utf-8', errors='replace')
            info = default_info.copy()
            in_info = in_cameras = False
            cameras = []
            
            for line in stdout.split('\n'):
                line = line.strip()
                if 'INFO_START' in line: in_info = True
                elif 'INFO_END' in line: in_info = False
                elif in_info:
                    if 'CAMERAS_START' in line: in_cameras = True
                    elif 'CAMERAS_END' in line: in_cameras = False
                    elif in_cameras and line.startswith('CAM:'): cameras.append(line[4:])
                    elif line.startswith('ACTIVE_CAMERA:'): info["active_camera"] = line.split(':', 1)[1]
                    elif line.startswith('RES_X:'): info["resolution_x"] = int(line.split(':')[1])
                    elif line.startswith('RES_Y:'): info["resolution_y"] = int(line.split(':')[1])
                    elif line.startswith('ENGINE:'): info["engine"] = line.split(':')[1]
                    elif line.startswith('SAMPLES:'): info["samples"] = int(line.split(':')[1])
                    elif line.startswith('FRAME_START:'): info["frame_start"] = int(line.split(':')[1])
                    elif line.startswith('FRAME_END:'): info["frame_end"] = int(line.split(':')[1])
            
            if cameras:
                info["cameras"] = ["Scene Default"] + cameras
            return info
        except Exception as e:
            print(f"Error: {e}")
            return default_info
    
    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        return {"render_engine": "Cycles", "samples": 128, "use_gpu": True, "use_scene_settings": True}
    
    def start_render(self, job, start_frame, on_progress, on_complete, on_error, on_log=None):
        blender_exe = self.get_best_blender_for_file(job.file_path)
        if not blender_exe:
            on_error("No Blender found")
            return
        
        self.is_cancelling = False
        os.makedirs(job.output_folder, exist_ok=True)
        
        fmt = self.OUTPUT_FORMATS.get(job.output_format, "PNG")
        script = f"import bpy\nbpy.context.scene.render.image_settings.file_format = '{fmt}'"
        
        script_dir = os.path.dirname(job.file_path) or os.getcwd()
        self.temp_script_path = os.path.join(script_dir, f"_render_{job.id}.py")
        with open(self.temp_script_path, 'w') as f:
            f.write(script)
        
        output_path = os.path.join(job.output_folder, job.output_name)
        cmd = [blender_exe, "-b", job.file_path, "--python", self.temp_script_path,
               "-o", output_path, "-F", fmt, "-x", "1"]
        
        if job.is_animation:
            cmd.extend(["-s", str(start_frame), "-e", str(job.frame_end), "-a"])
        else:
            cmd.extend(["-f", str(job.frame_start)])
        
        if on_log:
            on_log(f"Command: {' '.join(cmd)}")
        
        def render_thread():
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                self.current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=startupinfo)
                
                for line_bytes in self.current_process.stdout:
                    if self.is_cancelling: break
                    line = line_bytes.decode('utf-8', errors='replace').strip()
                    if on_log and line: on_log(line)
                    frame_match = re.search(r'Fra:(\d+)', line)
                    if frame_match:
                        on_progress(int(frame_match.group(1)), line)
                    elif "Saved:" in line:
                        on_progress(-1, line)
                
                return_code = self.current_process.wait()
                self._cleanup()
                
                if not self.is_cancelling:
                    if return_code == 0:
                        on_complete()
                    else:
                        on_error(f"Blender exited with code {return_code}")
            except Exception as e:
                self._cleanup()
                if not self.is_cancelling:
                    on_error(str(e))
        
        threading.Thread(target=render_thread, daemon=True).start()
    
    def cancel_render(self):
        self.is_cancelling = True
        if self.current_process:
            try: self.current_process.terminate()
            except: pass
            self._cleanup()
    
    def _cleanup(self):
        if self.temp_script_path and os.path.exists(self.temp_script_path):
            try: os.unlink(self.temp_script_path)
            except: pass
        self.temp_script_path = None
        self.current_process = None
    
    def open_file_in_app(self, file_path: str, version: str = None):
        blender_exe = self.get_best_blender_for_file(file_path)
        if blender_exe:
            subprocess.Popen([blender_exe, file_path], creationflags=subprocess.DETACHED_PROCESS)


# ============================================================================
# MARMOSET ENGINE (Stub)
# ============================================================================
class MarmosetEngine(RenderEngine):
    name = "Marmoset Toolbag"
    engine_type = "marmoset"
    file_extensions = [".tbscene"]
    icon = "diamond"
    color = "#06b6d4"
    
    def __init__(self):
        super().__init__()
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        self.installed_versions = {}
        paths = [r"C:\Program Files\Marmoset\Toolbag 5\toolbag.exe", r"C:\Program Files\Marmoset\Toolbag 4\toolbag.exe"]
        for p in paths:
            if os.path.exists(p):
                version = "5.0" if "5" in p else "4.0"
                self.installed_versions[version] = p
    
    def add_custom_path(self, path): return None
    def get_scene_info(self, file_path): return {"cameras": ["Main Camera"], "resolution_x": 1920, "resolution_y": 1080, "frame_start": 1, "frame_end": 1}
    def get_output_formats(self): return {"PNG": "PNG", "JPEG": "JPEG"}
    def get_default_settings(self): return {"renderer": "Ray Tracing", "samples": 256}
    def start_render(self, job, start_frame, on_progress, on_complete, on_error, on_log=None): on_error("Marmoset not implemented")
    def cancel_render(self): self.is_cancelling = True
    def open_file_in_app(self, file_path, version=None):
        if self.installed_versions:
            subprocess.Popen([list(self.installed_versions.values())[0], file_path], creationflags=subprocess.DETACHED_PROCESS)


# ============================================================================
# ENGINE REGISTRY
# ============================================================================
class EngineRegistry:
    def __init__(self):
        self.engines: Dict[str, RenderEngine] = {}
        self.register(BlenderEngine())
        self.register(MarmosetEngine())
    
    def register(self, engine): self.engines[engine.engine_type] = engine
    def get(self, engine_type): return self.engines.get(engine_type)
    def get_all(self): return list(self.engines.values())
    def get_available(self): return [e for e in self.engines.values() if e.is_available]
    
    def detect_engine_for_file(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        for engine in self.engines.values():
            if ext in engine.file_extensions:
                return engine
        return None
    
    def get_all_file_filters(self):
        filters = []
        all_exts = []
        for engine in self.engines.values():
            for ext in engine.file_extensions:
                all_exts.append(f"*{ext}")
            filters.extend(engine.get_file_dialog_filter())
        filters.insert(0, ("All Supported Files", " ".join(all_exts)))
        filters.append(("All Files", "*.*"))
        return filters


# ============================================================================
# APPLICATION STATE
# ============================================================================
class RenderApp:
    CONFIG_FILE = "render_manager_config.json"
    
    def __init__(self):
        self.engine_registry = EngineRegistry()
        self.settings = AppSettings()
        self.jobs: List[RenderJob] = []
        self.current_job = None
        self.render_start_time = None
        self.log_messages: List[str] = []
        self.queue_container = None
        self.log_container = None
        self.stats_container = None
        # Flags for thread-safe UI updates
        self._ui_needs_update = False
        self._render_finished = False
        self._log_needs_update = False
        self._progress_updates = []  # Queue of (job_id, progress, elapsed, frame, frames_display) for JS updates
        self.load_config()
    
    def log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{ts}] {message}")
        if len(self.log_messages) > 100:
            self.log_messages = self.log_messages[-100:]
        # Set flag instead of calling refresh from potentially background thread
        self._log_needs_update = True
    
    def add_job(self, job):
        self.jobs.insert(0, job)
        self.save_config()
        self.log(f"Added: {job.name}")
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
    
    def handle_action(self, action: str, job):
        self.log(f"{action.capitalize()}: {job.name}")
        
        if action == "start":
            job.status = "queued"
        elif action == "pause":
            if self.current_job and self.current_job.id == job.id:
                if self.render_start_time:
                    job.accumulated_seconds += int((datetime.now() - self.render_start_time).total_seconds())
                engine = self.engine_registry.get(job.engine_type)
                if engine: engine.cancel_render()
                self.current_job = None
                self.render_start_time = None
            job.status = "paused"
        elif action == "retry":
            job.status = "queued"
            job.progress = 0
            job.current_frame = 0
            job.error_message = ""
            job.accumulated_seconds = 0
        elif action == "delete":
            if self.current_job and self.current_job.id == job.id:
                engine = self.engine_registry.get(job.engine_type)
                if engine: engine.cancel_render()
                self.current_job = None
            self.jobs = [j for j in self.jobs if j.id != job.id]
        
        self.save_config()
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
    
    def process_queue(self):
        """Called by timer - handles queue processing and UI updates"""
        now = datetime.now()
        
        # Handle progress updates via JavaScript (no full UI refresh - smooth!)
        if self._progress_updates:
            updates = self._progress_updates.copy()
            self._progress_updates.clear()
            
            for job_id, progress, elapsed, frame, frames_display in updates:
                # Update progress bar and label via JS - much smoother than full refresh
                try:
                    # Escape any quotes in frames_display
                    safe_frames = frames_display.replace('"', '\\"').replace("'", "\\'")
                    ui.run_javascript(f'''
                        window.updateJobProgress && window.updateJobProgress("{job_id}", {progress}, "{elapsed}", "{safe_frames}");
                    ''')
                except:
                    pass
        
        # Only do full UI refresh when status changes (render finished/failed)
        if self._ui_needs_update:
            if self._render_finished:
                # Always update immediately when render finishes
                self._ui_needs_update = False
                self._render_finished = False
                if self.queue_container:
                    try: self.queue_container.refresh()
                    except: pass
                if self.stats_container:
                    try: self.stats_container.refresh()
                    except: pass
        
        # Log updates - skip during active render to prevent UI flicker
        # Only update log when no render is active, or every 5 seconds during render
        if self._log_needs_update:
            log_interval = 5.0 if self.current_job else 2.0
            if not hasattr(self, '_last_log_update') or \
               (now - self._last_log_update).total_seconds() >= log_interval:
                self._log_needs_update = False
                self._last_log_update = now
                if self.log_container:
                    try: self.log_container.refresh()
                    except: pass
        
        # Process queue - start next job if none running
        if self.current_job is None:
            for job in self.jobs:
                if job.status == "queued":
                    self.start_render(job)
                    break
    
    def start_render(self, job):
        engine = self.engine_registry.get(job.engine_type)
        if not engine:
            job.status = "failed"
            job.error_message = "Engine not found"
            if self.queue_container: self.queue_container.refresh()
            return
        
        self.current_job = job
        job.status = "rendering"
        self.render_start_time = datetime.now()
        
        start_frame = job.frame_start
        if job.is_animation and job.current_frame > 0:
            start_frame = job.current_frame + 1
        
        if job.original_start == 0:
            job.original_start = job.frame_start
        
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        self.log(f"Starting: {job.name}")
        
        # Flag to signal UI needs update (checked by timer)
        self._ui_needs_update = False
        self._last_ui_update = datetime.now()
        
        def on_progress(frame, msg):
            # Calculate progress based on frame completion for the entire job
            if job.is_animation:
                if frame > 0:
                    job.current_frame = frame
                    total = job.frame_end - job.original_start + 1
                    done = frame - job.original_start + 1
                    job.progress = min(int((done / total) * 100), 99)
            else:
                # Single frame render - progress based on samples/status
                if frame == -1:  # Saved/complete signal
                    job.progress = 99
                elif "Sample" in msg or "Path Tracing" in msg:
                    # Try to parse sample progress from Blender output
                    sample_match = re.search(r'Sample (\d+)/(\d+)', msg)
                    if sample_match:
                        current_sample = int(sample_match.group(1))
                        total_samples = int(sample_match.group(2))
                        job.progress = min(int((current_sample / total_samples) * 100), 99)
                    else:
                        # Increment gradually if we can't parse
                        job.progress = min(job.progress + 1, 95)
                elif frame > 0:
                    job.progress = min(job.progress + 5, 95)
            
            total_secs = job.accumulated_seconds
            if self.render_start_time:
                total_secs += int((datetime.now() - self.render_start_time).total_seconds())
            h, rem = divmod(total_secs, 3600)
            m, s = divmod(rem, 60)
            job.elapsed_time = f"{h}:{m:02d}:{s:02d}"
            
            # Queue JS update instead of full UI refresh (much smoother)
            self._progress_updates.append((job.id, job.progress, job.elapsed_time, job.current_frame, job.frames_display))
        
        def on_complete():
            job.status = "completed"
            job.progress = 100
            self.current_job = None
            self.log(f"Complete: {job.name}")
            self.save_config()
            self._ui_needs_update = True
            self._render_finished = True
        
        def on_error(err):
            job.status = "failed"
            job.error_message = err
            self.current_job = None
            self.log(f"Failed: {job.name} - {err}")
            self.save_config()
            self._ui_needs_update = True
            self._render_finished = True
        
        self._render_finished = False
        engine.start_render(job, start_frame, on_progress, on_complete, on_error, self.log)
    
    def save_config(self):
        data = {"jobs": [{
            "id": j.id, "name": j.name, "engine_type": j.engine_type,
            "file_path": j.file_path, "output_folder": j.output_folder,
            "output_name": j.output_name, "output_format": j.output_format,
            "status": j.status if j.status != "rendering" else "paused",
            "progress": j.progress, "is_animation": j.is_animation,
            "frame_start": j.frame_start, "frame_end": j.frame_end,
            "current_frame": j.current_frame, "original_start": j.original_start,
            "res_width": j.res_width, "res_height": j.res_height,
            "camera": j.camera, "engine_settings": j.engine_settings,
            "elapsed_time": j.elapsed_time, "accumulated_seconds": j.accumulated_seconds,
            "error_message": j.error_message,
        } for j in self.jobs]}
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except: pass
    
    def load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                for jd in data.get("jobs", []):
                    self.jobs.append(RenderJob(
                        id=jd.get("id", str(uuid.uuid4())[:8]),
                        name=jd.get("name", ""), engine_type=jd.get("engine_type", "blender"),
                        file_path=jd.get("file_path", ""), output_folder=jd.get("output_folder", ""),
                        output_name=jd.get("output_name", "render_"), output_format=jd.get("output_format", "PNG"),
                        status=jd.get("status", "queued"), progress=jd.get("progress", 0),
                        is_animation=jd.get("is_animation", False),
                        frame_start=jd.get("frame_start", 1), frame_end=jd.get("frame_end", 250),
                        current_frame=jd.get("current_frame", 0), original_start=jd.get("original_start", 0),
                        res_width=jd.get("res_width", 1920), res_height=jd.get("res_height", 1080),
                        camera=jd.get("camera", "Scene Default"), engine_settings=jd.get("engine_settings", {}),
                        elapsed_time=jd.get("elapsed_time", ""), accumulated_seconds=jd.get("accumulated_seconds", 0),
                        error_message=jd.get("error_message", ""),
                    ))
            except: pass


render_app = RenderApp()


# ============================================================================
# UI COMPONENTS
# ============================================================================
def create_stat_card(title, status, icon, color):
    count = sum(1 for j in render_app.jobs if j.status == status)
    with ui.row().classes('items-center gap-3'):
        ui.icon(icon).classes(f'text-3xl text-{color}-500')
        with ui.column().classes('gap-0'):
            ui.label(title).classes('text-sm text-gray-400')
            ui.label(str(count)).classes('text-2xl font-bold')


def create_job_card(job):
    config = STATUS_CONFIG.get(job.status, STATUS_CONFIG["queued"])
    engine = render_app.engine_registry.get(job.engine_type)
    engine_color = ENGINE_COLORS.get(job.engine_type, "#888")
    
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center gap-3'):
            ui.icon(engine.icon if engine else 'help').classes('text-2xl').style(f'color: {engine_color}')
            with ui.column().classes('flex-grow gap-0'):
                ui.label(job.name or "Untitled").classes('font-bold')
                ui.label(job.file_name).classes('text-sm text-gray-400')
            
            with ui.element('div').classes(f'px-2 py-1 rounded bg-{config["bg"]} text-{config["color"]}-400 text-xs font-bold'):
                ui.label(job.status.upper())
            
            if job.status == "rendering":
                ui.button(icon='pause', on_click=lambda j=job: render_app.handle_action('pause', j)).props('flat round dense').classes('text-yellow-500')
            elif job.status in ["queued", "paused"]:
                ui.button(icon='play_arrow', on_click=lambda j=job: render_app.handle_action('start', j)).props('flat round dense').classes('text-green-500')
            elif job.status == "failed":
                ui.button(icon='refresh', on_click=lambda j=job: render_app.handle_action('retry', j)).props('flat round dense').classes('text-yellow-500')
            
            ui.button(icon='delete', on_click=lambda j=job: render_app.handle_action('delete', j)).props('flat round dense').classes('text-red-500')
        
        if job.progress > 0 or job.status in ["rendering", "paused", "completed", "failed"]:
            # Custom HTML progress bar - full control, no unwanted text
            status_class = f'custom-progress-{job.status}'
            progress_width = max(1, job.progress)  # At least 1% width so it's visible
            
            # Set initial width inline AND data-target for JS animation
            # This prevents flash on refresh - bar starts at correct width
            ui.html(f'''
                <div class="custom-progress-container {status_class}">
                    <div class="custom-progress-track">
                        <div class="custom-progress-fill" 
                             id="progress-fill-{job.id}" 
                             data-target="{progress_width}"
                             style="width: {progress_width}%;"></div>
                    </div>
                    <div class="custom-progress-label" id="progress-label-{job.id}">{job.progress}%</div>
                </div>
            ''', sanitize=False).classes('w-full mt-2')
        
        engine_name = engine.name if engine else job.engine_type
        info_parts = [engine_name, f"Frames: {job.frames_display}", job.resolution_display]
        if job.elapsed_time:
            info_parts.append(f"Time: {job.elapsed_time}")
        # Use HTML with ID so we can update via JS
        ui.html(f'''
            <div id="job-info-{job.id}" class="text-sm text-gray-500 mt-2">
                {" | ".join(info_parts)}
            </div>
        ''', sanitize=False)


# ============================================================================
# DIALOGS
# ============================================================================
async def show_add_job_dialog():
    """Simple Add Job dialog with all fields visible."""
    
    # Form state
    form = {
        'engine_type': 'blender',
        'name': '',
        'file_path': '',
        'output_folder': '',
        'output_name': 'render_',
        'output_format': 'PNG',
        'camera': 'Scene Default',
        'is_animation': False,
        'frame_start': 1,
        'frame_end': 250,
        'res_width': 1920,
        'res_height': 1080,
        'submit_paused': False,
    }
    
    # UI references for scene info updates
    camera_select = None
    res_w_input = None
    res_h_input = None
    frame_start_input = None
    frame_end_input = None
    anim_checkbox = None
    status_label = None
    output_input = None
    name_input = None
    engine_toggle = None
    
    with ui.dialog() as dialog, ui.card().style(
        'width: 600px; max-width: 95vw; padding: 0;'
    ):
        # Header
        with ui.row().classes('w-full items-center justify-between p-4 border-b border-zinc-700'):
            ui.label('Add Render Job').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm')
        
        # Form content
        with ui.column().classes('w-full p-4 gap-3'):
            
            # Engine selector
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('Engine:').classes('text-gray-400 w-20')
                engine_toggle = ui.toggle(
                    {e.engine_type: e.name for e in render_app.engine_registry.get_available()},
                    value='blender'
                ).props('dense no-caps size=sm')
                engine_toggle.bind_value(form, 'engine_type')
            
            # Job name
            name_input = ui.input('Job Name', placeholder='Enter job name').classes('w-full')
            name_input.bind_value(form, 'name')
            
            # Scene file with browse button
            ui.label('Scene File:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                file_input = ui.input(placeholder=r'C:\path\to\scene.blend').classes('flex-grow')
                file_input.bind_value(form, 'file_path')
                ui.button('Browse', icon='folder_open', on_click=lambda: browse_file()).props('flat dense')
            
            # Scene info status and manual reload button
            with ui.row().classes('w-full items-center gap-2'):
                status_label = ui.label('').classes('text-xs text-gray-500')
                ui.button('Reload Scene Info', icon='refresh', on_click=lambda: load_scene_data(form['file_path'])).props('flat dense size=sm')
            
            # Function to load scene data (used by browse_file, on_file_blur, and manual button)
            def load_scene_data(path: str):
                """Load scene info from file and populate form fields."""
                if not path or not os.path.exists(path):
                    status_label.set_text('File not found')
                    return
                
                engine = render_app.engine_registry.get(form['engine_type'])
                if not engine:
                    status_label.set_text('No engine')
                    return
                
                status_label.set_text('Loading...')
                
                # Run in background thread to avoid blocking UI
                def do_load():
                    try:
                        return engine.get_scene_info(path)
                    except Exception as e:
                        print(f"Scene info error: {e}")
                        return None
                
                def apply_scene_info(info):
                    if info:
                        try:
                            cameras = info.get('cameras', ['Scene Default'])
                            camera_select.options = cameras
                            camera_select.value = info.get('active_camera', cameras[0] if cameras else 'Scene Default')
                            res_w_input.value = info.get('resolution_x', 1920)
                            res_h_input.value = info.get('resolution_y', 1080)
                            frame_start_input.value = info.get('frame_start', 1)
                            frame_end_input.value = info.get('frame_end', 250)
                            if info.get('frame_end', 1) > info.get('frame_start', 1):
                                anim_checkbox.value = True
                            status_label.set_text('✓ Loaded')
                        except Exception as e:
                            print(f"Apply scene info error: {e}")
                            status_label.set_text('Error')
                    else:
                        status_label.set_text('Failed')
                
                # Use the same polling pattern as file dialogs
                result_holder = {'done': False, 'info': None}
                
                def background_load():
                    result_holder['info'] = do_load()
                    result_holder['done'] = True
                
                threading.Thread(target=background_load, daemon=True).start()
                
                def check_load_result():
                    if result_holder['done']:
                        apply_scene_info(result_holder['info'])
                    else:
                        ui.timer(0.1, check_load_result, once=True)
                
                ui.timer(0.1, check_load_result, once=True)
            
            # Browse file handler
            def browse_file():
                def on_file_selected(result):
                    if result:
                        file_input.value = result
                        # Auto-fill other fields
                        if not form['name']:
                            name_input.value = os.path.splitext(os.path.basename(result))[0]
                        detected = render_app.engine_registry.detect_engine_for_file(result)
                        if detected:
                            engine_toggle.value = detected.engine_type
                        if not form['output_folder']:
                            output_input.value = os.path.dirname(result)
                        # Auto-load scene data
                        load_scene_data(result)
                
                filters = render_app.engine_registry.get_all_file_filters()
                initial = os.path.dirname(form['file_path']) if form['file_path'] else None
                open_file_dialog_async("Select Scene File", filters, initial, on_file_selected)
            
            # Auto-fill and auto-load on blur (when user pastes path)
            def on_file_blur():
                path = form['file_path']
                if path and os.path.exists(path):
                    if not form['name']:
                        name_input.value = os.path.splitext(os.path.basename(path))[0]
                    detected = render_app.engine_registry.detect_engine_for_file(path)
                    if detected:
                        engine_toggle.value = detected.engine_type
                    if not form['output_folder']:
                        output_input.value = os.path.dirname(path)
                    # Auto-load scene data
                    load_scene_data(path)
            
            file_input.on('blur', on_file_blur)
            
            ui.separator()
            
            # Output folder with browse button
            ui.label('Output Folder:').classes('text-sm text-gray-400')
            with ui.row().classes('w-full gap-2 items-center'):
                output_input = ui.input(placeholder=r'C:\path\to\output').classes('flex-grow')
                output_input.bind_value(form, 'output_folder')
                
                def browse_output():
                    def on_folder_selected(result):
                        if result:
                            output_input.value = result
                    
                    initial = form['output_folder'] if form['output_folder'] else os.path.dirname(form['file_path']) if form['file_path'] else None
                    open_folder_dialog_async("Select Output Folder", initial, on_folder_selected)
                
                ui.button('Browse', icon='folder_open', on_click=browse_output).props('flat dense')
            
            # Prefix and format
            with ui.row().classes('w-full gap-2'):
                ui.input('Prefix', value='render_').bind_value(form, 'output_name').classes('flex-grow')
                ui.select(['PNG', 'JPEG', 'OpenEXR', 'TIFF'], value='PNG', label='Format').bind_value(form, 'output_format').classes('w-28')
            
            # Resolution
            with ui.row().classes('w-full items-center gap-2'):
                res_w_input = ui.number('Width', value=1920, min=1).classes('w-24')
                res_w_input.bind_value(form, 'res_width')
                ui.label('×').classes('text-gray-400')
                res_h_input = ui.number('Height', value=1080, min=1).classes('w-24')
                res_h_input.bind_value(form, 'res_height')
            
            # Camera
            camera_select = ui.select(['Scene Default'], value='Scene Default', label='Camera').classes('w-full')
            camera_select.bind_value(form, 'camera')
            
            # Animation
            with ui.row().classes('w-full items-center gap-3'):
                anim_checkbox = ui.checkbox('Animation')
                anim_checkbox.bind_value(form, 'is_animation')
                frame_start_input = ui.number('Start', value=1, min=1).classes('w-20')
                frame_start_input.bind_value(form, 'frame_start')
                ui.label('to').classes('text-gray-400')
                frame_end_input = ui.number('End', value=250, min=1).classes('w-20')
                frame_end_input.bind_value(form, 'frame_end')
            
            ui.separator()
            
            # Submit paused
            ui.checkbox('Submit as Paused').bind_value(form, 'submit_paused')
        
        # Footer
        with ui.row().classes('w-full justify-end gap-2 p-4 border-t border-zinc-700'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            
            def submit():
                if not form['file_path']:
                    print("Missing file path")
                    return
                if not form['output_folder']:
                    print("Missing output folder")
                    return
                
                job = RenderJob(
                    name=form['name'] or "Untitled",
                    engine_type=form['engine_type'],
                    file_path=form['file_path'],
                    output_folder=form['output_folder'],
                    output_name=form['output_name'],
                    output_format=form['output_format'],
                    camera=form['camera'],
                    is_animation=form['is_animation'],
                    frame_start=int(form['frame_start']),
                    frame_end=int(form['frame_end']),
                    original_start=int(form['frame_start']),
                    res_width=int(form['res_width']),
                    res_height=int(form['res_height']),
                    status='paused' if form['submit_paused'] else 'queued',
                    engine_settings={"use_scene_settings": True, "samples": 128},
                )
                render_app.add_job(job)
                dialog.close()
            
            ui.button('Submit Job', on_click=submit).props('color=primary')
    
    dialog.open()


async def show_settings_dialog():
    with ui.dialog() as dialog, ui.card().style('width: 550px; max-width: 95vw; padding: 0;'):
        # Header
        with ui.row().classes('w-full items-center justify-between p-4 border-b border-zinc-700'):
            ui.label('Settings').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm')
        
        # Content
        with ui.column().classes('w-full p-4 gap-4'):
            for engine in render_app.engine_registry.get_all():
                with ui.card().classes('w-full p-3'):
                    with ui.row().classes('items-center gap-2 mb-2'):
                        ui.label(f'{engine.icon} {engine.name}').classes('font-bold')
                        status = "✓ Available" if engine.is_available else "✗ Not Found"
                        color = "text-green-500" if engine.is_available else "text-red-500"
                        ui.label(status).classes(f'{color} text-sm')
                    
                    if engine.installed_versions:
                        for v, p in sorted(engine.installed_versions.items(), reverse=True):
                            with ui.row().classes('items-center gap-2 mb-1'):
                                ui.badge(v, color='primary')
                                ui.label(p).classes('text-xs text-gray-500 truncate').style('max-width: 350px')
                    else:
                        ui.label('No installations detected').classes('text-sm text-gray-500 mb-2')
                    
                    # Add custom path with browse button
                    with ui.row().classes('w-full gap-2 items-center'):
                        path_input = ui.input(placeholder='Path to executable...').classes('flex-grow text-xs')
                        
                        def browse_exe(eng=engine, inp=path_input):
                            def on_exe_selected(result):
                                if result:
                                    inp.value = result
                            
                            open_file_dialog_async(
                                f"Select {eng.name} Executable",
                                [('Executable', '*.exe'), ('All Files', '*.*')],
                                None,
                                on_exe_selected
                            )
                        
                        def add_custom(eng=engine, inp=path_input):
                            path = inp.value
                            if path and os.path.exists(path):
                                version = eng.add_custom_path(path)
                                if version:
                                    print(f"Added {eng.name} {version}")
                                    inp.value = ''
                            else:
                                print(f"Path not found: {path}")
                        
                        ui.button('Browse', icon='folder_open', on_click=lambda e=engine, i=path_input: browse_exe(e, i)).props('flat dense size=sm')
                        ui.button('Add', icon='add', on_click=lambda e=engine, i=path_input: add_custom(e, i)).props('flat dense size=sm')
        
        # Footer
        with ui.row().classes('w-full justify-end p-4 border-t border-zinc-700'):
            ui.button('Close', on_click=dialog.close).props('flat')
    
    dialog.open()


# ============================================================================
# MAIN PAGE
# ============================================================================
@ui.page('/')
def main_page():
    ui.dark_mode().enable()
    ui.colors(**DARK_THEME['colors'])
    
    # Add custom CSS for responsive layout, scrollbars, and fixes
    # Comprehensive CSS for dark theme, scrollbars, and animation fixes
    ui.add_head_html('''
    <style>
        /* Responsive container */
        .responsive-container {
            width: 100%;
            max-width: 100%;
            padding: 1rem;
        }
        @media (min-width: 1024px) {
            .responsive-container {
                padding: 1.5rem;
            }
        }
        .stat-card {
            min-width: 150px;
            flex: 1 1 200px;
        }
        .job-card {
            width: 100%;
        }
        
        /* ========== SCROLLBAR STYLING ========== */
        /* Global scrollbar - applies everywhere including dialogs */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #18181b;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb {
            background: #3f3f46;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #52525b;
        }
        
        /* Quasar scroll area scrollbar */
        .q-scrollarea__thumb {
            background: #3f3f46 !important;
            border-radius: 4px !important;
            width: 8px !important;
            right: 2px !important;
        }
        .q-scrollarea__thumb:hover {
            background: #52525b !important;
        }
        .q-scrollarea__bar {
            background: #18181b !important;
            border-radius: 4px !important;
            width: 8px !important;
            right: 2px !important;
            opacity: 1 !important;
        }
        
        /* Layout stability - prevent content shifts during updates */
        .q-expansion-item__content {
            contain: layout;
        }
        
        /* Job cards should maintain stable layout */
        .q-card {
            contain: layout style;
            transform: translateZ(0); /* Force GPU layer for smoother updates */
        }
        
        /* Dialog styling */
        .q-dialog .q-card {
            max-height: 90vh;
        }
        
        /* Resizable dialog card */
        .q-card[style*="resize"] {
            resize: both !important;
            overflow: hidden !important;
            display: flex !important;
            flex-direction: column !important;
        }
        .q-card[style*="resize"]::-webkit-resizer {
            background: linear-gradient(135deg, transparent 50%, #3f3f46 50%);
            border-radius: 0 0 4px 0;
            width: 16px;
            height: 16px;
        }
        
        /* Ensure scroll area grows within resizable dialog */
        .q-card .q-scrollarea {
            flex: 1 1 auto !important;
            min-height: 100px;
        }
        
        /* Keep header and footer fixed size */
        .q-card > .row:first-child,
        .q-card > .row:last-child {
            flex-shrink: 0 !important;
        }
        
        /* ========== HIDE ALL NOTIFICATIONS ========== */
        /* This is a desktop app - no need for connection notifications */
        .q-notification,
        .q-notification--standard,
        .q-notifications,
        .q-notifications__list {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        
        /* ========== CHECKBOX/RADIO/TOGGLE FIXES ========== */
        /* Prevent animation freezing by using instant state changes */
        .q-checkbox__bg,
        .q-radio__bg,
        .q-toggle__inner {
            transition: none !important;
        }
        
        /* Checkmark/dot appearance - instant */
        .q-checkbox__svg,
        .q-radio__check,
        .q-toggle__track,
        .q-toggle__thumb {
            transition: none !important;
        }
        
        /* Color changes can be smooth since they don't affect layout */
        .q-checkbox__inner,
        .q-radio__inner,
        .q-toggle__inner--truthy,
        .q-toggle__inner--falsy {
            transition: color 0.1s ease, background-color 0.1s ease !important;
        }
        
        /* Button toggle group */
        .q-btn-toggle .q-btn {
            transition: background-color 0.1s ease, color 0.1s ease !important;
        }
        
        /* Ripple effect - disable to prevent stuck animations */
        .q-ripple {
            display: none !important;
        }
        
        /* ========== CUSTOM PROGRESS BAR ========== */
        .custom-progress-container {
            width: 100%;
            display: flex;
            flex-direction: column;
            gap: 4px;
            /* Prevent layout shift */
            min-height: 28px;
        }
        
        .custom-progress-track {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.15);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
            /* Ensure track is always visible */
            min-height: 8px;
        }
        
        .custom-progress-fill {
            height: 100%;
            border-radius: 4px;
            position: relative;
            /* Default color if status class doesn't apply */
            background: #3b82f6;
            /* Smooth width changes */
            will-change: width;
        }
        
        .custom-progress-label {
            text-align: center;
            font-size: 14px;
            color: #a1a1aa;
        }
        
        /* ===== RENDERING - Blue with shimmer ===== */
        .custom-progress-rendering .custom-progress-fill {
            background: #3b82f6;
        }
        
        .custom-progress-rendering .custom-progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.4) 50%,
                transparent 100%
            );
            animation: shimmer 1.5s ease-in-out infinite;
        }
        
        .custom-progress-rendering .custom-progress-track {
            box-shadow: 0 0 8px rgba(59, 130, 246, 0.4);
            animation: render-glow 2s ease-in-out infinite;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(200%); }
        }
        
        @keyframes render-glow {
            0%, 100% { box-shadow: 0 0 4px rgba(59, 130, 246, 0.3); }
            50% { box-shadow: 0 0 12px rgba(59, 130, 246, 0.6); }
        }
        
        /* ===== QUEUED - Yellow ===== */
        .custom-progress-queued .custom-progress-fill {
            background: #eab308;
        }
        
        /* ===== PAUSED - Orange with glow ===== */
        .custom-progress-paused .custom-progress-fill {
            background: #f97316;
        }
        
        .custom-progress-paused .custom-progress-track {
            box-shadow: 0 0 8px rgba(249, 115, 22, 0.4);
            animation: paused-glow 2s ease-in-out infinite;
        }
        
        @keyframes paused-glow {
            0%, 100% { box-shadow: 0 0 4px rgba(249, 115, 22, 0.3); }
            50% { box-shadow: 0 0 12px rgba(249, 115, 22, 0.6); }
        }
        
        /* ===== COMPLETED - Green with shine ===== */
        .custom-progress-completed .custom-progress-fill {
            background: #22c55e;
        }
        
        .custom-progress-completed .custom-progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.3) 50%,
                transparent 100%
            );
            animation: success-shine 3s ease-in-out infinite;
        }
        
        @keyframes success-shine {
            0%, 70%, 100% { transform: translateX(-100%); }
            35% { transform: translateX(200%); }
        }
        
        /* ===== FAILED - Red ===== */
        .custom-progress-failed .custom-progress-fill {
            background: #ef4444;
        }
        
        .custom-progress-failed .custom-progress-track {
            animation: failed-pulse 2s ease-in-out infinite;
        }
        
        @keyframes failed-pulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
        }
        
        /* ========== OLD PROGRESS BAR (hidden/disabled) ========== */
        .q-linear-progress__track,
        .q-linear-progress__model {
            transition: none !important;
        }
        
        /* Hide ALL text/labels inside and around progress bar - very aggressive */
        .q-linear-progress *:not(.q-linear-progress__track):not(.q-linear-progress__model),
        .q-linear-progress__string,
        .q-linear-progress > div:not(.q-linear-progress__track):not(.q-linear-progress__model),
        .q-linear-progress span,
        .q-linear-progress div[class*="string"],
        .q-linear-progress div[class*="label"],
        .q-linear-progress__track span,
        .q-linear-progress__model span,
        .progress-bar-no-label span,
        .q-linear-progress > span,
        .nicegui-linear-progress span,
        /* Target value display elements */
        .q-linear-progress__value,
        .q-linear-progress [class*="value"],
        .q-linear-progress [class*="Value"],
        .q-linear-progress__stripe + span,
        .q-linear-progress + span,
        /* Any floating/absolute positioned text near progress */
        .q-linear-progress [style*="position: absolute"],
        .q-linear-progress [style*="position:absolute"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            font-size: 0 !important;
            color: transparent !important;
            width: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
        }
        
        /* Make progress bar taller and always visible */
        .q-linear-progress {
            height: 8px !important;
            min-height: 8px !important;
            border-radius: 4px !important;
            overflow: hidden !important;
            background: rgba(255, 255, 255, 0.15) !important;
            font-size: 0 !important;
            color: transparent !important;
        }
        
        .q-linear-progress__track {
            border-radius: 4px !important;
            opacity: 1 !important;
            background: rgba(255, 255, 255, 0.15) !important;
            height: 100% !important;
        }
        
        .q-linear-progress__model {
            border-radius: 4px !important;
            opacity: 1 !important;
            min-width: 0 !important;
            height: 100% !important;
        }
        
        /* Ensure track is always visible even at 0% */
        .q-linear-progress__track--dark {
            background: rgba(255, 255, 255, 0.15) !important;
        }
        
    </style>
    ''')
    
    # JavaScript to completely suppress NiceGUI/Quasar notifications
    ui.add_head_html('''
    <script>
        // Completely disable Quasar notifications for desktop app
        (function() {
            // Immediately hide any notification container
            const style = document.createElement('style');
            style.textContent = `
                .q-notification,
                .q-notification--standard,
                .q-notifications,
                .q-notifications__list,
                .q-notification__wrapper,
                [class*="q-notification"] {
                    display: none !important;
                    visibility: hidden !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                    position: absolute !important;
                    left: -9999px !important;
                }
            `;
            document.head.appendChild(style);
        })();
        
        document.addEventListener('DOMContentLoaded', function() {
            // Override Quasar Notify plugin
            if (window.Quasar && window.Quasar.Notify) {
                window.Quasar.Notify.create = function() { return { dismiss: function() {} }; };
                window.Quasar.Notify.setDefaults = function() {};
            }
            
            // Also try to override it on the Vue instance
            setTimeout(function() {
                if (window.Quasar && window.Quasar.Notify) {
                    window.Quasar.Notify.create = function() { return { dismiss: function() {} }; };
                }
            }, 100);
            
            // MutationObserver to immediately remove any notifications
            const observer = new MutationObserver(function(mutations) {
                const notifications = document.querySelectorAll(
                    '.q-notification, .q-notifications, [class*="q-notification"]'
                );
                notifications.forEach(n => {
                    n.style.display = 'none';
                    n.remove();
                });
            });
            
            observer.observe(document.body, { childList: true, subtree: true });
            
            // ========== SMOOTH PROGRESS BAR ANIMATION ==========
            // Track current animated widths for each progress bar
            const progressState = {};
            const ANIMATION_SPEED = 0.06; // Easing factor (0-1, lower = smoother)
            const MIN_STEP = 0.15; // Minimum step per frame for visible movement
            
            // Global function to update progress without UI refresh
            window.updateJobProgress = function(jobId, progress, elapsed, framesDisplay) {
                const fill = document.getElementById('progress-fill-' + jobId);
                const label = document.getElementById('progress-label-' + jobId);
                const info = document.getElementById('job-info-' + jobId);
                
                if (fill) {
                    fill.dataset.target = progress;
                }
                if (label) {
                    label.textContent = progress + '%';
                }
                if (info && elapsed) {
                    // Update elapsed time in info label
                    var text = info.textContent;
                    // Replace or add time
                    if (text.includes('Time:')) {
                        text = text.replace(/Time: [0-9:]+/, 'Time: ' + elapsed);
                    } else {
                        text = text + ' | Time: ' + elapsed;
                    }
                    // Update frames display if provided
                    if (framesDisplay) {
                        text = text.replace(/Frames: [^|]+/, 'Frames: ' + framesDisplay + ' ');
                    }
                    info.textContent = text;
                }
            };
            
            function animateProgressBars() {
                document.querySelectorAll('.custom-progress-fill[data-target]').forEach(function(fill) {
                    const id = fill.id;
                    if (!id) return;
                    
                    const target = parseFloat(fill.dataset.target) || 0;
                    
                    // If element is new (not in state), set it directly without animation
                    // This prevents the "animate from 0" flash on UI refresh
                    if (!(id in progressState)) {
                        // Check if element has inline width already set
                        const inlineWidth = parseFloat(fill.style.width) || 0;
                        if (inlineWidth > 0) {
                            // Element was created with correct width, sync state to it
                            progressState[id] = inlineWidth;
                        } else {
                            // No inline width, set directly to target (no animation)
                            progressState[id] = target;
                            fill.style.width = target + '%';
                        }
                        return; // Skip animation this frame
                    }
                    
                    const current = progressState[id];
                    const diff = target - current;
                    
                    // Only animate if there's a meaningful difference
                    if (Math.abs(diff) > 0.1) {
                        // Calculate step with easing
                        let step = diff * ANIMATION_SPEED;
                        if (Math.abs(step) < MIN_STEP && Math.abs(diff) > MIN_STEP) {
                            step = diff > 0 ? MIN_STEP : -MIN_STEP;
                        }
                        progressState[id] = current + step;
                        fill.style.width = progressState[id] + '%';
                    } else if (Math.abs(diff) > 0.01) {
                        // Snap to target when very close
                        progressState[id] = target;
                        fill.style.width = target + '%';
                    }
                });
                
                requestAnimationFrame(animateProgressBars);
            }
            
            // Start animation loop
            requestAnimationFrame(animateProgressBars);
        });
        
        // Suppress console errors about connection
        const originalError = console.error;
        const originalWarn = console.warn;
        console.error = function(...args) {
            const msg = args.join(' ');
            if (msg.includes('WebSocket') || msg.includes('connection') || 
                msg.includes('reconnect') || msg.includes('socket')) {
                return;
            }
            originalError.apply(console, args);
        };
        console.warn = function(...args) {
            const msg = args.join(' ');
            if (msg.includes('WebSocket') || msg.includes('connection') || 
                msg.includes('reconnect') || msg.includes('socket')) {
                return;
            }
            originalWarn.apply(console, args);
        };
    </script>
    ''')
    
    with ui.header().classes('items-center justify-between px-4 md:px-6 py-3 bg-zinc-900'):
        with ui.row().classes('items-center gap-4'):
            ui.icon('movie').classes('text-3xl text-blue-500')
            with ui.column().classes('gap-0'):
                ui.label('Render Manager').classes('text-xl font-bold')
                ui.label('NiceGUI Desktop').classes('text-sm text-gray-400')
        
        with ui.row().classes('gap-2'):
            ui.button('Settings', icon='settings', on_click=show_settings_dialog).props('flat')
            ui.button('Add Job', icon='add', on_click=show_add_job_dialog, color='primary')
    
    with ui.column().classes('responsive-container gap-4'):
        @ui.refreshable
        def stats_section():
            with ui.row().classes('w-full gap-4 flex-wrap'):
                with ui.card().classes('stat-card'): create_stat_card('Rendering', 'rendering', 'play_circle', 'blue')
                with ui.card().classes('stat-card'): create_stat_card('Queued', 'queued', 'schedule', 'yellow')
                with ui.card().classes('stat-card'): create_stat_card('Completed', 'completed', 'check_circle', 'green')
                with ui.card().classes('stat-card'): create_stat_card('Failed', 'failed', 'error', 'red')
        
        render_app.stats_container = stats_section
        stats_section()
        
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Render Queue').classes('text-xl font-bold')
            @ui.refreshable
            def job_count():
                ui.label(f'{len(render_app.jobs)} jobs').classes('text-gray-400')
            job_count()
        
        @ui.refreshable
        def queue_list():
            if not render_app.jobs:
                with ui.card().classes('w-full'):
                    with ui.column().classes('w-full items-center py-8'):
                        ui.icon('inbox').classes('text-6xl text-gray-600')
                        ui.label('No render jobs').classes('text-xl text-gray-400 mt-4')
                        ui.label('Click "Add Job" to get started').classes('text-gray-500')
            else:
                for job in render_app.jobs:
                    create_job_card(job)
        
        render_app.queue_container = queue_list
        queue_list()
        
        with ui.expansion('Log', icon='terminal').classes('w-full'):
            @ui.refreshable
            def log_display():
                # Use scroll_area with scroll-to-bottom behavior
                with ui.scroll_area().classes('w-full h-48 bg-zinc-900 rounded').props('id="log-scroll"') as scroll:
                    with ui.column().classes('p-2 gap-0 font-mono text-xs'):
                        # Show messages in chronological order (oldest first, newest at bottom)
                        for msg in render_app.log_messages[-50:]:
                            ui.label(msg).classes('text-gray-400')
                # Auto-scroll to bottom after rendering
                ui.run_javascript('''
                    setTimeout(() => {
                        const el = document.getElementById('log-scroll');
                        if (el) {
                            const container = el.querySelector('.q-scrollarea__container');
                            if (container) container.scrollTop = container.scrollHeight;
                        }
                    }, 100);
                ''')
            
            render_app.log_container = log_display
            log_display()
    
    # Timer for queue processing and UI updates (every 500ms for smoother progress)
    ui.timer(0.5, render_app.process_queue)
    
    for engine in render_app.engine_registry.get_all():
        if engine.is_available:
            render_app.log(f"Found: {engine.version_display}")
        else:
            render_app.log(f"Not found: {engine.name}")
    render_app.log(f"Loaded {len(render_app.jobs)} jobs")


# ============================================================================
# RUN
# ============================================================================
if __name__ in {"__main__", "__mp_main__"}:
    print("Starting Render Manager (Desktop Mode)...")
    print("Using NiceGUI with PyQt6/pywebview backend")
    ui.run(
        title='Render Manager',
        dark=True,
        reload=False,
        native=True,              # Desktop window instead of browser
        window_size=(1200, 850),
        fullscreen=False,
        reconnect_timeout=0,      # Disable reconnection attempts (desktop app)
        show=True,                # Show window immediately
    )
