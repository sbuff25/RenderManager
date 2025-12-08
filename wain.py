#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wain - Multi-Engine Render Queue Manager (ITT04-Native Desktop)
Queue-based render management with pause/resume support
Supports: Blender, Marmoset Toolbag

Built with NiceGUI + pywebview (Qt backend) for native desktop window
Works on Python 3.10+ (including 3.13 and 3.14)

Note: Use wain_launcher.pyw for splash screen and no console window.
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
    
    # (import_name, pip_name, required)
    # ORDER MATTERS: PyQt6 must install before pywebview so Qt backend is available
    REQUIRED_PACKAGES = [
        ('nicegui', 'nicegui', True),      # Required - the UI framework
        ('PyQt6', 'PyQt6', True),          # Required - Qt backend (install before pywebview!)
        ('PyQt6.QtWebEngineWidgets', 'PyQt6-WebEngine', True),  # Required for native window
        ('qtpy', 'qtpy', True),            # Required - Qt compatibility layer for pywebview
        ('webview', 'pywebview', True),    # Required - native window
        ('PIL', 'Pillow', True),           # Required - image processing for icons/splash
    ]
    
    missing_required = []
    missing_optional = []
    
    for import_name, pip_name, required in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            if required:
                missing_required.append(pip_name)
            else:
                missing_optional.append(pip_name)
    
    all_missing = missing_required + missing_optional
    
    if all_missing:
        print("=" * 60)
        print("Wain - First Run Setup")
        print("=" * 60)
        print(f"\nInstalling packages: {', '.join(all_missing)}")
        print("This only happens once...\n")
        
        failed_required = []
        failed_optional = []
        
        for package in all_missing:
            print(f"  Installing {package}...")
            try:
                # Special handling for pywebview on Python 3.13+
                # pythonnet dependency fails to compile, but we can use Qt backend
                if package == 'pywebview' and sys.version_info >= (3, 13):
                    print(f"  (Python 3.13+ - using Qt backend only)")
                    # Install without dependencies to skip pythonnet
                    subprocess.check_call(
                        [sys.executable, '-m', 'pip', 'install', package, '--no-deps'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT
                    )
                    # Install light dependencies pywebview needs
                    subprocess.check_call(
                        [sys.executable, '-m', 'pip', 'install', 'proxy-tools', 'bottle'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT
                    )
                else:
                    subprocess.check_call(
                        [sys.executable, '-m', 'pip', 'install', package],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT
                    )
                print(f"  [OK] {package} installed successfully")
            except subprocess.CalledProcessError as e:
                is_required = package in missing_required
                if is_required:
                    failed_required.append(package)
                    print(f"  [X] Failed to install {package} (required)")
                else:
                    failed_optional.append(package)
                    print(f"  [!] Failed to install {package} (optional)")
        
        if failed_required:
            print(f"\n[X] Failed to install required packages: {', '.join(failed_required)}")
            print(f"\nPlease try:")
            print(f"  {sys.executable} -m pip install {' '.join(failed_required)}")
            print(f"\nNote: Python 3.10-3.12 recommended for best compatibility")
            sys.exit(1)
        
        if failed_optional:
            print(f"\n[!] Optional packages not installed: {', '.join(failed_optional)}")
            print("  Wain will run in browser mode instead of native window")
        
        print("\n" + "=" * 60)
        print("Setup complete! Starting Wain...")
        print("=" * 60 + "\n")

# Run dependency check before any imports
_check_and_install_dependencies()

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================
# CRITICAL: Set these BEFORE any other imports!
import os
import sys

# Check if native mode is available (pywebview + PyQt6 + WebEngine + qtpy)
HAS_NATIVE_MODE = False
try:
    # Set environment variables FIRST
    os.environ['QT_API'] = 'pyqt6'
    os.environ['PYWEBVIEW_GUI'] = 'qt'
    
    import PyQt6
    from PyQt6 import QtWebEngineWidgets  # This is what pywebview Qt backend needs
    import qtpy  # Qt compatibility layer - required by pywebview
    import webview
    
    HAS_NATIVE_MODE = True
    print("Native mode: PyQt6 + WebEngine + qtpy available")
except ImportError as e:
    print(f"Native mode unavailable ({e}) - will use browser mode")

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
# CACHE BUSTING - Force browser to reload assets when version changes
# ============================================================================
ASSET_VERSION = "v2"  # Increment this to force cache refresh

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
        'primary': '#a1a1aa',      # Neutral gray for main app chrome
        'secondary': '#6b7280',
        'accent': '#71717a',        # Neutral accent
        'positive': '#22c55e',
        'negative': '#ef4444',
        'info': '#71717a',          # Neutral info
        'warning': '#f59e0b',
    }
}

ENGINE_COLORS = {"blender": "#ea7600", "marmoset": "#ef0343"}

# Engine logo files (relative to script directory)
ENGINE_LOGOS = {
    "blender": "blender_logo.png",
    "marmoset": "marmoset_logo.png",
}

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
    current_frame: int = 0      # Last COMPLETED frame (used for resume)
    rendering_frame: int = 0    # Frame currently being rendered (for display)
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
    current_sample: int = 0
    total_samples: int = 0
    
    @property
    def samples_display(self) -> str:
        """Display sample progress for single frame renders"""
        if self.current_sample > 0 and self.total_samples > 0:
            return f"{self.current_sample}/{self.total_samples}"
        return ""
    
    @property
    def display_frame(self) -> int:
        """Get the frame to display (rendering or last completed)"""
        if self.rendering_frame > 0:
            return self.rendering_frame
        return self.current_frame
    
    @property
    def frames_display(self) -> str:
        if self.is_animation:
            frame = self.display_frame
            if frame > 0 and frame >= self.frame_start:
                # Show current/total format for both rendering and paused
                return f"{frame}/{self.frame_end}"
            return f"0/{self.frame_end}"
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
# MARMOSET ENGINE - Full Implementation
# ============================================================================
class MarmosetEngine(RenderEngine):
    """
    Marmoset Toolbag render engine integration.
    
    Supports:
    - Still image renders (beauty shots)
    - Turntable (360 deg rotation) renders
    - Animation sequence renders
    - Full render settings control (renderer, samples, shadows, denoising)
    - File-based progress tracking
    """
    
    name = "Marmoset Toolbag"
    engine_type = "marmoset"
    file_extensions = [".tbscene"]
    icon = "diamond"
    color = "#ef0343"  # Marmoset red
    
    # Installation paths to search
    SEARCH_PATHS = [
        r"C:\Program Files\Marmoset\Toolbag 5\toolbag.exe",
        r"C:\Program Files\Marmoset\Toolbag 4\toolbag.exe",
        r"C:\Program Files (x86)\Marmoset\Toolbag 5\toolbag.exe",
        r"C:\Program Files (x86)\Marmoset\Toolbag 4\toolbag.exe",
    ]
    
    # Output formats for still images
    OUTPUT_FORMATS = {
        "PNG": "PNG",
        "JPEG": "JPEG",
        "TGA": "TGA",
        "PSD": "PSD",
        "PSD (16-bit)": "PSD (16-bit)",
        "EXR (16-bit)": "EXR (16-bit)",
        "EXR (32-bit)": "EXR (32-bit)",
    }
    
    # Video/sequence formats
    VIDEO_FORMATS = {
        "MP4": "MPEG4",
        "PNG Sequence": "PNG",
        "JPEG Sequence": "JPEG",
        "TGA Sequence": "TGA",
    }
    
    # Renderer modes
    RENDERERS = ["Ray Tracing", "Hybrid", "Raster"]
    
    # Shadow quality options
    SHADOW_QUALITY = ["Low", "High", "Mega"]
    
    # Denoising options
    DENOISE_MODES = ["off", "cpu", "gpu"]
    DENOISE_QUALITY = ["low", "medium", "high"]
    
    # Render types for the UI
    RENDER_TYPES = {
        "still": "Still Image",
        "turntable": "Turntable (360 deg)",
        "animation": "Animation",
    }
    
    # Available render passes (key: display_name, value: mset pass name)
    # These correspond to the viewport passes in Toolbag's Component View / Render Passes
    RENDER_PASSES = {
        "beauty": {"name": "Beauty", "pass": "", "desc": "Full quality render (default)"},
        "albedo": {"name": "Albedo", "pass": "Albedo", "desc": "Base color/diffuse texture"},
        "normals": {"name": "Normals", "pass": "Normals", "desc": "Surface normal directions"},
        "depth": {"name": "Depth", "pass": "Depth", "desc": "Distance from camera"},
        "ao": {"name": "Ambient Occlusion", "pass": "AO", "desc": "Contact shadows/cavity"},
        "roughness": {"name": "Roughness", "pass": "Roughness", "desc": "Surface roughness values"},
        "metalness": {"name": "Metalness", "pass": "Metalness", "desc": "Metallic areas"},
        "emissive": {"name": "Emissive", "pass": "Emissive", "desc": "Self-illumination"},
        "reflection": {"name": "Reflection", "pass": "Reflection", "desc": "Specular reflections"},
        "diffuse_light": {"name": "Diffuse Light", "pass": "Diffuse Light", "desc": "Diffuse lighting only"},
        "specular_light": {"name": "Specular Light", "pass": "Specular Light", "desc": "Specular lighting only"},
        "position": {"name": "Position", "pass": "Position", "desc": "World position data"},
        "object_id": {"name": "Object ID", "pass": "Object ID", "desc": "Unique colors per object"},
        "material_id": {"name": "Material ID", "pass": "Material ID", "desc": "Unique colors per material"},
    }
    
    def __init__(self):
        super().__init__()
        self._temp_script_path: Optional[str] = None
        self._progress_file_path: Optional[str] = None
        self._progress_monitor_thread: Optional[threading.Thread] = None
        self._monitoring = False
        self._last_message = ""
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        """Scan for Toolbag installations."""
        self.installed_versions = {}
        for path in self.SEARCH_PATHS:
            if os.path.isfile(path):
                if "Toolbag 5" in path:
                    version = "5.0"
                elif "Toolbag 4" in path:
                    version = "4.0"
                else:
                    version = "Unknown"
                self.installed_versions[version] = path
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """Add a custom Toolbag executable path."""
        if os.path.isfile(path) and path.lower().endswith('.exe'):
            if "5" in os.path.basename(os.path.dirname(path)):
                version = "5.x (Custom)"
            elif "4" in os.path.basename(os.path.dirname(path)):
                version = "4.x (Custom)"
            else:
                version = "Custom"
            self.installed_versions[version] = path
            return version
        return None
    
    def get_best_toolbag(self) -> Optional[str]:
        """Get the best available Toolbag executable (prefer newest)."""
        if not self.installed_versions:
            return None
        newest = sorted(self.installed_versions.keys(), reverse=True)[0]
        return self.installed_versions[newest]
    
    def get_output_formats(self) -> Dict[str, str]:
        """Return available output formats."""
        return self.OUTPUT_FORMATS
    
    def get_video_formats(self) -> Dict[str, str]:
        """Return available video/sequence formats."""
        return self.VIDEO_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        """Return default engine settings for Marmoset jobs."""
        return {
            "render_type": "still",           # still, turntable, animation
            "renderer": "Ray Tracing",        # Ray Tracing, Hybrid, Raster
            "samples": 256,                   # Render samples
            "shadow_quality": "High",         # Low, High, Mega
            "use_transparency": False,        # Transparent background
            "denoise_mode": "gpu",            # off, cpu, gpu
            "denoise_quality": "high",        # low, medium, high
            "denoise_strength": 1.0,          # 0.0 - 1.0
            "ray_trace_bounces": 4,           # 1-16
            # Turntable specific
            "turntable_frames": 120,          # Number of frames for 360 deg
            "turntable_clockwise": True,      # Rotation direction
            # Video format (for turntable/animation)
            "video_format": "PNG Sequence",   # Output format for sequences
            # Render passes - dict of pass_key: enabled
            "render_passes": {
                "beauty": True,               # Always render beauty by default
                "albedo": False,
                "normals": False,
                "depth": False,
                "ao": False,
                "roughness": False,
                "metalness": False,
                "emissive": False,
                "reflection": False,
                "diffuse_light": False,
                "specular_light": False,
                "position": False,
                "object_id": False,
                "material_id": False,
            },
        }
    
    def get_file_dialog_filter(self) -> List[tuple]:
        """Return file dialog filter for Toolbag scenes."""
        return [("Marmoset Toolbag Scenes", "*.tbscene")]
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open a scene file in Toolbag."""
        toolbag_exe = self.get_best_toolbag()
        if toolbag_exe and os.path.exists(file_path):
            try:
                creation_flags = subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0
                subprocess.Popen([toolbag_exe, file_path], creationflags=creation_flags)
            except Exception as e:
                print(f"Failed to open in Toolbag: {e}")
    
    # ========================================================================
    # SCENE PROBING
    # ========================================================================
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """
        Probe a Toolbag scene file to extract information.
        Runs Toolbag with a probe script that writes JSON output.
        """
        default_info = {
            "cameras": ["Main Camera"],
            "active_camera": "Main Camera",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "renderer": "Ray Tracing",
            "samples": 256,
            "frame_start": 1,
            "frame_end": 1,
            "total_frames": 1,
            "has_animation": False,
            "has_turntable": False,
        }
        
        toolbag_exe = self.get_best_toolbag()
        if not toolbag_exe or not os.path.exists(file_path):
            return default_info
        
        # Create temp files for probe script and output
        script_dir = os.path.dirname(file_path) or tempfile.gettempdir()
        probe_script = os.path.join(script_dir, "_wane_probe.py")
        output_json = os.path.join(script_dir, "_wane_probe_result.json")
        
        # Generate probe script
        probe_code = self._generate_probe_script(file_path, output_json)
        
        try:
            with open(probe_script, 'w', encoding='utf-8') as f:
                f.write(probe_code)
            
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                [toolbag_exe, probe_script],
                capture_output=True,
                timeout=60,
                startupinfo=startupinfo
            )
            
            if os.path.exists(output_json):
                with open(output_json, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                return info
            else:
                print(f"Probe output not found")
                return default_info
                
        except subprocess.TimeoutExpired:
            print("Toolbag probe timed out")
            return default_info
        except Exception as e:
            print(f"Scene probe error: {e}")
            return default_info
        finally:
            for f in [probe_script, output_json]:
                if os.path.exists(f):
                    try:
                        os.unlink(f)
                    except:
                        pass
    
    def _generate_probe_script(self, scene_path: str, output_path: str) -> str:
        """Generate Python script that probes scene and writes JSON."""
        scene_path_escaped = scene_path.replace('\\', '\\\\')
        output_path_escaped = output_path.replace('\\', '\\\\')
        
        return f'''# Wane Scene Probe Script for Marmoset Toolbag
import mset
import json

def probe_scene():
    result = {{
        "cameras": [],
        "active_camera": "Main Camera",
        "resolution_x": 1920,
        "resolution_y": 1080,
        "renderer": "Ray Tracing",
        "samples": 256,
        "frame_start": 1,
        "frame_end": 1,
        "total_frames": 1,
        "has_animation": False,
        "has_turntable": False,
    }}
    
    try:
        mset.loadScene(r"{scene_path_escaped}")
        
        # Get all cameras and turntable info
        cameras = []
        turntable_obj = None
        for obj in mset.getAllObjects():
            obj_name = obj.name if hasattr(obj, 'name') else str(obj)
            obj_type = type(obj).__name__
            if hasattr(obj, 'fov') or 'Camera' in obj_type:
                cameras.append(obj_name)
            if 'Turntable' in obj_type:
                turntable_obj = obj
                if hasattr(obj, 'enabled') and obj.enabled:
                    result["has_turntable"] = True
                # Get turntable spin rate for frame calculation
                if hasattr(obj, 'spinRate'):
                    result["turntable_spin_rate"] = abs(obj.spinRate)
        
        if cameras:
            result["cameras"] = cameras
            try:
                active_cam = mset.getCamera()
                if active_cam and hasattr(active_cam, 'name'):
                    result["active_camera"] = active_cam.name
                elif cameras:
                    result["active_camera"] = cameras[0]
            except:
                if cameras:
                    result["active_camera"] = cameras[0]
        
        # Get render settings from Render object
        try:
            render_obj = None
            for obj in mset.getAllObjects():
                if type(obj).__name__ == 'RenderObject':
                    render_obj = obj
                    break
            
            if render_obj:
                # Get image output settings (for still renders)
                if hasattr(render_obj, 'images'):
                    img = render_obj.images
                    if hasattr(img, 'width'):
                        result["resolution_x"] = img.width
                    if hasattr(img, 'height'):
                        result["resolution_y"] = img.height
                    if hasattr(img, 'samples'):
                        result["samples"] = img.samples
                
                # Get VIDEO output settings (for turntable/animation)
                # This is where Toolbag 5.02+ stores the frame count
                if hasattr(render_obj, 'videos'):
                    vid = render_obj.videos
                    if hasattr(vid, 'width') and vid.width > 0:
                        result["video_width"] = vid.width
                    if hasattr(vid, 'height') and vid.height > 0:
                        result["video_height"] = vid.height
                    if hasattr(vid, 'samples'):
                        result["video_samples"] = vid.samples
                    if hasattr(vid, 'format'):
                        result["video_format"] = vid.format
                    # Get frame count from video settings
                    if hasattr(vid, 'frameCount') and vid.frameCount > 0:
                        result["turntable_frames"] = vid.frameCount
                        result["frame_end"] = vid.frameCount
                        result["total_frames"] = vid.frameCount
                
                if hasattr(render_obj, 'options'):
                    opts = render_obj.options
                    if hasattr(opts, 'renderer'):
                        result["renderer"] = opts.renderer
        except Exception as e:
            print(f"Render settings error: {{e}}")
        
        # Get timeline info (for animations with keyframes)
        try:
            timeline = mset.getTimeline()
            if timeline:
                if hasattr(timeline, 'totalFrames'):
                    tl_frames = timeline.totalFrames
                    if tl_frames > 1:
                        result["timeline_frames"] = tl_frames
                        # Only use timeline frames if not already set by video settings
                        if result.get("total_frames", 1) <= 1:
                            result["total_frames"] = tl_frames
                            result["frame_end"] = tl_frames
                if hasattr(timeline, 'selectionStart'):
                    result["frame_start"] = max(1, timeline.selectionStart)
                if hasattr(timeline, 'selectionEnd') and timeline.selectionEnd > 0:
                    result["timeline_selection_end"] = timeline.selectionEnd
                if hasattr(timeline, 'frameRate'):
                    result["frame_rate"] = timeline.frameRate
                if result.get("timeline_frames", 1) > 1:
                    result["has_animation"] = True
        except Exception as e:
            print(f"Timeline error: {{e}}")
        
    except Exception as e:
        print(f"Scene probe error: {{e}}")
    
    with open(r"{output_path_escaped}", 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    mset.quit()

probe_scene()
'''
    
    # ========================================================================
    # RENDERING
    # ========================================================================
    
    def start_render(self, job, start_frame: int, on_progress, on_complete, on_error, on_log=None):
        """Start a Marmoset Toolbag render job."""
        toolbag_exe = self.get_best_toolbag()
        if not toolbag_exe:
            on_error("No Marmoset Toolbag installation found")
            return
        
        if not os.path.exists(job.file_path):
            on_error(f"Scene file not found: {job.file_path}")
            return
        
        self.is_cancelling = False
        os.makedirs(job.output_folder, exist_ok=True)
        
        render_type = job.get_setting("render_type", "still")
        
        script_dir = os.path.dirname(job.file_path) or tempfile.gettempdir()
        self._temp_script_path = os.path.join(script_dir, f"_wane_render_{job.id}.py")
        self._progress_file_path = os.path.join(script_dir, f"_wane_progress_{job.id}.json")
        
        if render_type == "turntable":
            script_code = self._generate_turntable_script(job, start_frame)
        elif render_type == "animation":
            script_code = self._generate_animation_script(job, start_frame)
        else:
            script_code = self._generate_still_script(job)
        
        try:
            with open(self._temp_script_path, 'w', encoding='utf-8') as f:
                f.write(script_code)
            
            if on_log:
                on_log(f"Marmoset render type: {render_type}")
                on_log(f"Script path: {self._temp_script_path}")
                on_log(f"Output: {job.output_folder}")
            
            def render_thread():
                try:
                    startupinfo = None
                    creation_flags = 0
                    if sys.platform == 'win32':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        # Start Toolbag minimized to reduce UI interference
                        startupinfo.wShowWindow = 6  # SW_MINIMIZE
                        # Prevent Toolbag from stealing focus
                        creation_flags = 0x08000000  # CREATE_NO_WINDOW doesn't work for GUI apps
                    
                    # Add -hide flag to hide Toolbag's main menu (Toolbag 3.07+)
                    cmd = [toolbag_exe, '-hide', self._temp_script_path]
                    if on_log:
                        on_log(f"Command: {' '.join(cmd)}")
                    
                    self.current_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        startupinfo=startupinfo,
                        creationflags=creation_flags
                    )
                    
                    if on_log:
                        on_log(f"Started Toolbag (PID: {self.current_process.pid})")
                    
                    # Start progress monitor
                    self._start_progress_monitor(job, on_progress, on_log)
                    
                    # Read stdout in real-time
                    for line_bytes in self.current_process.stdout:
                        if self.is_cancelling:
                            break
                        line = line_bytes.decode('utf-8', errors='replace').strip()
                        if line and on_log:
                            # Only log lines that contain [Wane] or important info
                            if '[Wane]' in line or 'error' in line.lower() or 'exception' in line.lower():
                                on_log(f"Toolbag: {line}")
                    
                    return_code = self.current_process.wait()
                    self._stop_progress_monitor()
                    
                    if on_log:
                        on_log(f"Toolbag exited with code: {return_code}")
                    
                    if self.is_cancelling:
                        if on_log:
                            on_log("Render cancelled")
                        return
                    
                    final_status = self._read_progress_file()
                    if on_log:
                        on_log(f"Final status: {final_status}")
                    
                    if final_status.get("status") == "complete":
                        on_complete()
                    elif final_status.get("status") == "error":
                        on_error(final_status.get("error", "Unknown error"))
                    elif return_code == 0:
                        on_complete()
                    else:
                        on_error(f"Toolbag exited with code {return_code}")
                    
                except Exception as e:
                    self._stop_progress_monitor()
                    if not self.is_cancelling:
                        if on_log:
                            on_log(f"Render thread error: {e}")
                        on_error(str(e))
                finally:
                    self._cleanup()
            
            threading.Thread(target=render_thread, daemon=True).start()
            
        except Exception as e:
            self._cleanup()
            on_error(f"Failed to start render: {e}")
    
    def _generate_still_script(self, job) -> str:
        """Generate script for still image render with render pass support."""
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        output_format = job.output_format.upper()
        
        # Build output filename base
        ext_map = {"PNG": "png", "JPEG": "jpg", "TGA": "tga", "PSD": "psd", "EXR (16-BIT)": "exr", "EXR (32-BIT)": "exr"}
        ext = ext_map.get(output_format, "png")
        output_base = job.output_name
        
        # Get enabled render passes
        render_passes = job.get_setting("render_passes", {"beauty": True})
        enabled_passes = [key for key, enabled in render_passes.items() if enabled]
        
        # If no passes selected, default to beauty
        if not enabled_passes:
            enabled_passes = ["beauty"]
        
        # Build passes list for the script - map our keys to Toolbag pass names
        passes_config = []
        for pass_key in enabled_passes:
            if pass_key in self.RENDER_PASSES:
                pass_info = self.RENDER_PASSES[pass_key]
                toolbag_pass = pass_info['pass']  # Empty string for beauty (Full Quality)
                suffix = f"_{pass_key}" if len(enabled_passes) > 1 or pass_key != "beauty" else ""
                passes_config.append({
                    'key': pass_key,
                    'name': pass_info['name'],
                    'toolbag_pass': toolbag_pass,
                    'suffix': suffix,
                })
        
        # Convert to Python literal for embedding in script
        import json as json_module
        passes_json = json_module.dumps(passes_config)
        
        return f'''# Wane Render Script - Still Image with Render Passes
import mset
import json
import os
import sys

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error="", current_pass=""):
    try:
        data = {{"status": status, "progress": progress, "message": message, "error": error, "frame": 0, "total_frames": 1, "current_pass": current_pass}}
        with open(r"{progress_path}", 'w') as f:
            json.dump(data, f)
        log(f"Progress: {{status}} {{progress}}% - {{message}}")
    except Exception as e:
        log(f"Progress update error: {{e}}")

def render_still():
    try:
        log("Starting still render with render passes...")
        update_progress("loading", 0, "Loading scene...")
        
        log(f"Loading scene: {scene_path}")
        mset.loadScene(r"{scene_path}")
        log("Scene loaded successfully")
        
        # Ensure output directory exists
        output_dir = r"{output_folder}"
        log(f"Output directory: {{output_dir}}")
        os.makedirs(output_dir, exist_ok=True)
        
        # Render passes configuration
        passes = {passes_json}
        total_passes = len(passes)
        log(f"Rendering {{total_passes}} pass(es): {{[p['name'] for p in passes]}}")
        
        rendered_files = []
        
        for i, pass_config in enumerate(passes):
            pass_key = pass_config['key']
            pass_name = pass_config['name']
            toolbag_pass = pass_config['toolbag_pass']
            suffix = pass_config['suffix']
            
            # Calculate progress (spread across all passes)
            base_progress = int((i / total_passes) * 80) + 10
            update_progress("rendering", base_progress, f"Rendering {{pass_name}}...", current_pass=pass_name)
            
            # Build output path with suffix
            output_path = os.path.join(output_dir, f"{output_base}{{suffix}}.{ext}")
            log(f"Rendering pass '{{pass_name}}' ({{toolbag_pass or 'Full Quality'}}) to: {{output_path}}")
            
            # Use renderCamera with viewportPass parameter
            # Signature: renderCamera(path, width, height, samples, transparency, camera, viewportPass)
            try:
                if toolbag_pass:
                    # Render specific pass
                    mset.renderCamera(
                        output_path,
                        {job.res_width},
                        {job.res_height},
                        {samples},
                        {str(use_transparency)},
                        '',  # camera (empty = current camera)
                        toolbag_pass  # viewportPass
                    )
                else:
                    # Beauty pass (Full Quality) - no viewportPass needed
                    mset.renderCamera(
                        output_path,
                        {job.res_width},
                        {job.res_height},
                        {samples},
                        {str(use_transparency)}
                    )
                
                if os.path.exists(output_path):
                    log(f"Pass '{{pass_name}}' rendered: {{output_path}}")
                    rendered_files.append(output_path)
                else:
                    log(f"WARNING: Pass '{{pass_name}}' output not found!")
                    
            except Exception as pass_error:
                log(f"Error rendering pass '{{pass_name}}': {{pass_error}}")
                # Continue with other passes
        
        log(f"Render complete! {{len(rendered_files)}}/{{total_passes}} passes rendered.")
        
        if rendered_files:
            update_progress("complete", 100, f"Rendered {{len(rendered_files)}} pass(es)")
        else:
            update_progress("error", 0, "", "No passes were rendered successfully")
        
    except Exception as e:
        log(f"Render error: {{e}}")
        update_progress("error", 0, "", str(e))
        import traceback
        traceback.print_exc()
    
    log("Quitting Toolbag...")
    mset.quit()

render_still()
'''
    
    def _generate_turntable_script(self, job, start_frame: int) -> str:
        """Generate script for turntable render."""
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        video_format = job.get_setting("video_format", "PNG Sequence")
        total_frames = job.frame_end
        clockwise = job.get_setting("turntable_clockwise", True)
        
        is_mp4 = "MP4" in video_format.upper()
        spin_sign = "" if clockwise else "-"
        
        return f'''# Wane Render Script - Turntable
import mset
import json
import os
import sys

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error="", frame=0, total={total_frames}):
    try:
        data = {{"status": status, "progress": progress, "message": message, "error": error, "frame": frame, "total_frames": total}}
        with open(r"{progress_path}", 'w') as f:
            json.dump(data, f)
        log(f"Progress: {{status}} {{progress}}% frame={{frame}}/{{total}}")
    except Exception as e:
        log(f"Progress update error: {{e}}")

def render_turntable():
    try:
        log("Starting turntable render...")
        update_progress("loading", 0, "Loading scene...")
        
        log(f"Loading scene: {scene_path}")
        mset.loadScene(r"{scene_path}")
        log("Scene loaded successfully")
        
        update_progress("configuring", 5, "Configuring turntable...")
        
        # Check for existing frames in output folder (for resume)
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        import glob
        existing_files = glob.glob(os.path.join(output_dir, "*.png"))
        existing_count = len(existing_files)
        resume_from_frame = max(1, existing_count + 1) if existing_count > 0 else 1
        log(f"Existing frames in output: {{existing_count}}")
        log(f"Will render from frame {{resume_from_frame}} to {total_frames}")
        
        # If all frames are already rendered, skip
        if existing_count >= {total_frames}:
            log("All frames already rendered!")
            update_progress("complete", 100, "Already complete", frame={total_frames})
            mset.quit()
            return
        
        # Find and enable turntable
        turntable = None
        for obj in mset.getAllObjects():
            obj_type = type(obj).__name__
            obj_name = obj.name.lower() if hasattr(obj, 'name') else ''
            if 'Turntable' in obj_type or 'turntable' in obj_name:
                turntable = obj
                log(f"Found turntable: {{obj.name}}")
                break
        
        if turntable:
            turntable.enabled = True
            # Spin rate: degrees per second (at scene frame rate, typically 30fps)
            turntable.spinRate = {spin_sign}(360.0 / {total_frames}) * 30.0
            log(f"Turntable enabled, spin rate: {{turntable.spinRate}}")
        else:
            log("WARNING: No turntable found in scene!")
        
        log(f"Output directory: {{output_dir}}")
        
        # Set timeline selection for resume
        # This tells Toolbag which frame range to render
        timeline = mset.getTimeline()
        if timeline and resume_from_frame > 1:
            try:
                timeline.selectionStart = resume_from_frame
                timeline.selectionEnd = {total_frames}
                log(f"Timeline selection set: {{resume_from_frame}} to {total_frames}")
            except Exception as e:
                log(f"Could not set timeline selection: {{e}}")
        
        # Find and configure the Render object's VIDEO output settings
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                log(f"Found render object: {{obj.name}}")
                break
        
        if render_obj and hasattr(render_obj, 'videos'):
            videos = render_obj.videos
            log("Configuring video output settings...")
            
            # Set output path (REQUIRED - this is where the video goes)
            try:
                videos.outputPath = output_dir
                log(f"Set video outputPath: {{videos.outputPath}}")
            except Exception as e:
                log(f"Could not set outputPath: {{e}}")
            
            # Set resolution
            try:
                videos.width = {job.res_width}
                videos.height = {job.res_height}
                log(f"Set video resolution: {{videos.width}}x{{videos.height}}")
            except Exception as e:
                log(f"Could not set resolution: {{e}}")
            
            # Set samples
            try:
                videos.samples = {samples}
                log(f"Set video samples: {{videos.samples}}")
            except Exception as e:
                log(f"Could not set samples: {{e}}")
            
            # Set transparency
            try:
                videos.transparency = {str(use_transparency)}
                log(f"Set video transparency: {{videos.transparency}}")
            except Exception as e:
                log(f"Could not set transparency: {{e}}")
            
            # Set format (PNG Sequence for image sequence)
            try:
                videos.format = "PNG"
                log(f"Set video format: {{videos.format}}")
            except Exception as e:
                log(f"Could not set format: {{e}}")
        else:
            log("WARNING: No Render object or videos output found!")
        
        update_progress("rendering", 10, "Rendering turntable...", frame={start_frame})
        log("Starting mset.renderVideos()...")
        
        # Render video/sequence - uses the configured RenderObject.videos settings
        mset.renderVideos()
        
        log("Turntable render complete!")
        update_progress("complete", 100, "Turntable complete", frame={total_frames})
        
    except Exception as e:
        log(f"Render error: {{e}}")
        update_progress("error", 0, "", str(e))
        import traceback
        traceback.print_exc()
    
    log("Quitting Toolbag...")
    mset.quit()

render_turntable()
'''
    
    def _generate_animation_script(self, job, start_frame: int) -> str:
        """Generate script for animation sequence render."""
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        
        return f'''# Wane Render Script - Animation
import mset
import json
import os
import sys

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error="", frame=0, total={job.frame_end}):
    try:
        data = {{"status": status, "progress": progress, "message": message, "error": error, "frame": frame, "total_frames": total}}
        with open(r"{progress_path}", 'w') as f:
            json.dump(data, f)
        log(f"Progress: {{status}} {{progress}}% frame={{frame}}/{{total}}")
    except Exception as e:
        log(f"Progress update error: {{e}}")

def render_animation():
    try:
        log("Starting animation render...")
        update_progress("loading", 0, "Loading scene...")
        
        log(f"Loading scene: {scene_path}")
        mset.loadScene(r"{scene_path}")
        log("Scene loaded successfully")
        
        update_progress("configuring", 5, "Configuring animation...")
        
        # Check for existing frames in output folder (for resume)
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        import glob
        existing_files = glob.glob(os.path.join(output_dir, "*.png"))
        existing_count = len(existing_files)
        
        # Use start_frame from job or count from existing files, whichever is greater
        resume_from_frame = max({start_frame}, existing_count + 1)
        log(f"Existing frames in output: {{existing_count}}")
        log(f"Will render from frame {{resume_from_frame}} to {job.frame_end}")
        
        # If all frames are already rendered, skip
        if existing_count >= {job.frame_end}:
            log("All frames already rendered!")
            update_progress("complete", 100, "Already complete", frame={job.frame_end})
            mset.quit()
            return
        
        # Set timeline range for animation (with resume support)
        timeline = mset.getTimeline()
        if timeline:
            timeline.selectionStart = resume_from_frame
            timeline.selectionEnd = {job.frame_end}
            log(f"Timeline set: {{timeline.selectionStart}} to {{timeline.selectionEnd}}")
        else:
            log("WARNING: Could not access timeline!")
        
        log(f"Output directory: {{output_dir}}")
        
        # Find and configure the Render object's VIDEO output settings
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                log(f"Found render object: {{obj.name}}")
                break
        
        if render_obj and hasattr(render_obj, 'videos'):
            videos = render_obj.videos
            log("Configuring video output settings...")
            
            # Set output path (REQUIRED - this is where the video goes)
            try:
                videos.outputPath = output_dir
                log(f"Set video outputPath: {{videos.outputPath}}")
            except Exception as e:
                log(f"Could not set outputPath: {{e}}")
            
            # Set resolution
            try:
                videos.width = {job.res_width}
                videos.height = {job.res_height}
                log(f"Set video resolution: {{videos.width}}x{{videos.height}}")
            except Exception as e:
                log(f"Could not set resolution: {{e}}")
            
            # Set samples
            try:
                videos.samples = {samples}
                log(f"Set video samples: {{videos.samples}}")
            except Exception as e:
                log(f"Could not set samples: {{e}}")
            
            # Set transparency
            try:
                videos.transparency = {str(use_transparency)}
                log(f"Set video transparency: {{videos.transparency}}")
            except Exception as e:
                log(f"Could not set transparency: {{e}}")
            
            # Set format (PNG Sequence for image sequence)
            try:
                videos.format = "PNG"
                log(f"Set video format: {{videos.format}}")
            except Exception as e:
                log(f"Could not set format: {{e}}")
        else:
            log("WARNING: No Render object or videos output found!")
        
        update_progress("rendering", 10, "Rendering animation...", frame={start_frame})
        log("Starting mset.renderVideos()...")
        
        # Render video/sequence - uses the configured RenderObject.videos settings
        mset.renderVideos()
        
        log("Animation render complete!")
        update_progress("complete", 100, "Animation complete", frame={job.frame_end})
        
    except Exception as e:
        log(f"Render error: {{e}}")
        update_progress("error", 0, "", str(e))
        import traceback
        traceback.print_exc()
    
    log("Quitting Toolbag...")
    mset.quit()

render_animation()
'''
    
    def _start_progress_monitor(self, job, on_progress, on_log=None):
        """Start background thread to monitor progress by watching output files."""
        self._monitoring = True
        
        def monitor():
            import glob
            import time
            
            last_frame_count = 0
            total_frames = job.frame_end if job.is_animation else 1
            
            # Get initial file count (for resume support)
            output_pattern = os.path.join(job.output_folder, "*.png")
            try:
                initial_files = glob.glob(output_pattern)
                last_frame_count = len(initial_files)
                if on_log and last_frame_count > 0:
                    on_log(f"Found {last_frame_count} existing frames in output folder")
            except:
                pass
            
            while self._monitoring and not self.is_cancelling:
                # Also check progress file for status messages
                progress = self._read_progress_file()
                
                if progress:
                    status = progress.get("status", "")
                    message = progress.get("message", "")
                    
                    if on_log and message and message != self._last_message:
                        on_log(message)
                        self._last_message = message
                    
                    if status == "complete":
                        # Final frame count from output folder
                        try:
                            final_files = glob.glob(output_pattern)
                            final_count = len(final_files)
                            on_progress(final_count, f"Render complete: {final_count} frames")
                        except:
                            on_progress(total_frames, "Render complete")
                        break
                    elif status == "error":
                        break
                
                # Watch output folder for new PNG files (more accurate than progress file)
                try:
                    current_files = glob.glob(output_pattern)
                    current_count = len(current_files)
                    
                    if current_count > last_frame_count:
                        # New frames have been rendered
                        last_frame_count = current_count
                        
                        if on_log:
                            on_log(f"Rendered frame {current_count}/{total_frames}")
                        
                        # Update job's current_frame for pause/resume
                        job.current_frame = current_count
                        job.rendering_frame = current_count
                        
                        on_progress(current_count, f"Rendering frame {current_count}/{total_frames}")
                except Exception as e:
                    if on_log:
                        on_log(f"Progress check error: {e}")
                
                time.sleep(0.5)
        
        self._progress_monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._progress_monitor_thread.start()
    
    def _stop_progress_monitor(self):
        """Stop the progress monitor thread."""
        self._monitoring = False
        if self._progress_monitor_thread:
            self._progress_monitor_thread.join(timeout=2)
            self._progress_monitor_thread = None
    
    def _read_progress_file(self) -> Dict[str, Any]:
        """Read the current progress from the progress file."""
        if not self._progress_file_path or not os.path.exists(self._progress_file_path):
            return {}
        
        try:
            with open(self._progress_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def cancel_render(self):
        """Cancel the current render."""
        self.is_cancelling = True
        self._stop_progress_monitor()
        
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except:
                try:
                    self.current_process.kill()
                except:
                    pass
        
        self._cleanup()
    
    def _cleanup(self):
        """Clean up temporary files."""
        for path in [self._temp_script_path, self._progress_file_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except:
                    pass
        
        self._temp_script_path = None
        self._progress_file_path = None
        self.current_process = None


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
    CONFIG_FILE = "wain_config.json"
    
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
        self.job_count_container = None  # Job count display
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
        if self.job_count_container: self.job_count_container.refresh()
    
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
            job.current_frame = 0
            job.rendering_frame = 0
            job.error_message = ""
            job.accumulated_seconds = 0
            job.elapsed_time = ""
            job.current_sample = 0
            job.total_samples = 0
            # Reset progress to initial position based on where job starts in timeline
            if job.is_animation and job.frame_end > 0 and job.original_start > 1:
                job.progress = int(((job.original_start - 1) / job.frame_end) * 100)
            else:
                job.progress = 0
        elif action == "delete":
            if self.current_job and self.current_job.id == job.id:
                engine = self.engine_registry.get(job.engine_type)
                if engine: engine.cancel_render()
                self.current_job = None
            self.jobs = [j for j in self.jobs if j.id != job.id]
        
        self.save_config()
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        if self.job_count_container: self.job_count_container.refresh()
    
    def process_queue(self):
        """Called by timer - handles queue processing and UI updates"""
        now = datetime.now()
        
        # Always update elapsed time for current rendering job (real-time timer)
        if self.current_job and self.current_job.status == "rendering" and self.render_start_time:
            total_secs = self.current_job.accumulated_seconds
            total_secs += int((now - self.render_start_time).total_seconds())
            h, rem = divmod(total_secs, 3600)
            m, s = divmod(rem, 60)
            elapsed = f"{h}:{m:02d}:{s:02d}"
            self.current_job.elapsed_time = elapsed
            
            # Push time update via JS (always, for real-time display)
            try:
                safe_frames = self.current_job.frames_display.replace('"', '\\"').replace("'", "\\'")
                safe_samples = self.current_job.samples_display.replace('"', '\\"').replace("'", "\\'")
                ui.run_javascript(f'''
                    window.updateJobProgress && window.updateJobProgress("{self.current_job.id}", {self.current_job.progress}, "{elapsed}", "{safe_frames}", "{safe_samples}");
                ''')
            except:
                pass
        
        # Handle additional progress updates via JavaScript (no full UI refresh - smooth!)
        if self._progress_updates:
            updates = self._progress_updates.copy()
            self._progress_updates.clear()
            
            for job_id, progress, elapsed, frame, frames_display, samples_display in updates:
                # Update progress bar and label via JS - much smoother than full refresh
                try:
                    # Escape any quotes in displays
                    safe_frames = frames_display.replace('"', '\\"').replace("'", "\\'")
                    safe_samples = samples_display.replace('"', '\\"').replace("'", "\\'")
                    ui.run_javascript(f'''
                        window.updateJobProgress && window.updateJobProgress("{job_id}", {progress}, "{elapsed}", "{safe_frames}", "{safe_samples}");
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
                if self.job_count_container:
                    try: self.job_count_container.refresh()
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
            if self.job_count_container: self.job_count_container.refresh()
            return
        
        self.current_job = job
        job.status = "rendering"
        self.render_start_time = datetime.now()
        
        start_frame = job.frame_start
        if job.is_animation and job.current_frame > 0:
            start_frame = job.current_frame + 1
        
        if job.original_start == 0:
            job.original_start = job.frame_start
        
        # Set initial progress based on where we're starting in the timeline
        if job.is_animation and job.frame_end > 0:
            # Progress = (start_frame - 1) / total_frames
            # e.g., starting at frame 526 of 1500 = 525/1500 = 35%
            initial_frame = start_frame - 1 if start_frame > 1 else 0
            job.progress = int((initial_frame / job.frame_end) * 100)
        
        if self.queue_container: self.queue_container.refresh()
        if self.stats_container: self.stats_container.refresh()
        self.log(f"Starting: {job.name}")
        
        # Flag to signal UI needs update (checked by timer)
        self._ui_needs_update = False
        self._last_ui_update = datetime.now()
        
        def on_progress(frame, msg):
            # Always try to parse sample progress from output (for both animation and single frame)
            sample_match = re.search(r'Sample (\d+)/(\d+)', msg)
            if sample_match:
                job.current_sample = int(sample_match.group(1))
                job.total_samples = int(sample_match.group(2))
            
            # Calculate progress based on frame position in ENTIRE timeline
            if job.is_animation:
                if frame > 0:
                    # Frame started - track it for display, but don't mark as complete yet
                    job.rendering_frame = frame
                
                if frame == -1:
                    # Frame saved/complete - NOW mark the rendering_frame as completed
                    if job.rendering_frame > 0:
                        job.current_frame = job.rendering_frame
                        # Reset sample counter for next frame
                        job.current_sample = 0
                    # Progress = completed frame / total frames in timeline
                    job.progress = min(int((job.current_frame / job.frame_end) * 100), 99)
                elif job.rendering_frame > 0:
                    # Update progress based on rendering_frame + sample progress
                    # Use (rendering_frame - 1) as base since current frame isn't done yet
                    frame_progress = 0
                    if job.current_sample > 0 and job.total_samples > 0:
                        frame_progress = job.current_sample / job.total_samples
                    # Progress based on (frames_before_current + partial_current) / total_frames
                    effective_frame = (job.rendering_frame - 1) + frame_progress
                    job.progress = min(int((effective_frame / job.frame_end) * 100), 99)
            else:
                # Single frame render - progress based on samples/status
                if frame == -1:  # Saved/complete signal
                    job.progress = 99
                elif sample_match:
                    # Use sample progress for single frames
                    job.progress = min(int((job.current_sample / job.total_samples) * 100), 99)
                elif "Sample" in msg or "Path Tracing" in msg:
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
            self._progress_updates.append((job.id, job.progress, job.elapsed_time, job.current_frame, job.frames_display, job.samples_display))
        
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
            "current_frame": j.current_frame, "rendering_frame": j.rendering_frame,
            "original_start": j.original_start,
            "res_width": j.res_width, "res_height": j.res_height,
            "camera": j.camera, "engine_settings": j.engine_settings,
            "elapsed_time": j.elapsed_time, "accumulated_seconds": j.accumulated_seconds,
            "error_message": j.error_message,
            "current_sample": j.current_sample, "total_samples": j.total_samples,
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
                        current_frame=jd.get("current_frame", 0), rendering_frame=jd.get("rendering_frame", 0),
                        original_start=jd.get("original_start", 0),
                        res_width=jd.get("res_width", 1920), res_height=jd.get("res_height", 1080),
                        camera=jd.get("camera", "Scene Default"), engine_settings=jd.get("engine_settings", {}),
                        elapsed_time=jd.get("elapsed_time", ""), accumulated_seconds=jd.get("accumulated_seconds", 0),
                        error_message=jd.get("error_message", ""),
                        current_sample=jd.get("current_sample", 0), total_samples=jd.get("total_samples", 0),
                    ))
            except: pass


render_app = RenderApp()


# ============================================================================
# UI COMPONENTS
# ============================================================================
def create_stat_card(title, status, icon, color):
    count = sum(1 for j in render_app.jobs if j.status == status)
    with ui.row().classes('items-center gap-3'):
        # Use white/gray icons for desaturated 2-tone look
        ui.icon(icon).classes('text-3xl text-zinc-400')
        with ui.column().classes('gap-0'):
            ui.label(title).classes('text-sm text-gray-500')
            ui.label(str(count)).classes('text-2xl font-bold text-white')


def create_job_card(job):
    config = STATUS_CONFIG.get(job.status, STATUS_CONFIG["queued"])
    engine = render_app.engine_registry.get(job.engine_type)
    engine_color = ENGINE_COLORS.get(job.engine_type, "#888")
    engine_logo = ENGINE_LOGOS.get(job.engine_type)
    
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center gap-3'):
            # Engine logo
            if engine_logo:
                ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-8 h-8 object-contain')
            else:
                ui.icon(engine.icon if engine else 'help').classes('text-2xl').style(f'color: {engine_color}')
            with ui.column().classes('flex-grow gap-0'):
                ui.label(job.name or "Untitled").classes('font-bold')
                ui.label(job.file_name).classes('text-sm text-gray-400')
            
            # Status badge - engine color when rendering, neutral when paused, standard otherwise
            if job.status == "rendering":
                # Use engine-specific color for rendering status
                with ui.element('div').classes(f'px-2 py-1 rounded text-xs font-bold status-badge status-badge-engine-{job.engine_type}').style(f'background-color: rgba(255,255,255,0.1); color: {engine_color};'):
                    ui.label(job.status.upper())
            elif job.status == "paused":
                # Neutral gray for paused
                with ui.element('div').classes('px-2 py-1 rounded text-xs font-bold status-badge').style('background-color: rgba(161,161,170,0.15); color: #a1a1aa;'):
                    ui.label(job.status.upper())
            else:
                # Standard colors for queued, completed, failed
                with ui.element('div').classes(f'px-2 py-1 rounded bg-{config["bg"]} text-{config["color"]}-400 text-xs font-bold status-badge'):
                    ui.label(job.status.upper())
            
            # Action buttons - engine themed when rendering, neutral otherwise
            if job.status == "rendering":
                ui.button(icon='pause', on_click=lambda j=job: render_app.handle_action('pause', j)).props('flat round dense').classes(f'job-action-btn-engine job-action-btn-engine-{job.engine_type}')
            elif job.status in ["queued", "paused"]:
                ui.button(icon='play_arrow', on_click=lambda j=job: render_app.handle_action('start', j)).props('flat round dense').classes('job-action-btn text-zinc-400')
            elif job.status == "failed":
                ui.button(icon='refresh', on_click=lambda j=job: render_app.handle_action('retry', j)).props('flat round dense').classes('job-action-btn text-zinc-400')
            
            # Delete button - engine themed when rendering, neutral otherwise
            if job.status == "rendering":
                ui.button(icon='delete', on_click=lambda j=job: render_app.handle_action('delete', j)).props('flat round dense').classes(f'job-action-btn-engine job-action-btn-engine-{job.engine_type}')
            else:
                ui.button(icon='delete', on_click=lambda j=job: render_app.handle_action('delete', j)).props('flat round dense').classes('job-action-btn-danger text-zinc-500')
        
        if job.progress > 0 or job.status in ["rendering", "paused", "completed", "failed"]:
            # Custom HTML progress bar - full control, no unwanted text
            status_class = f'custom-progress-{job.status}'
            engine_class = f'custom-progress-engine-{job.engine_type}'
            progress_width = max(1, job.progress)  # At least 1% width so it's visible
            
            # Set initial width inline AND data-target for JS animation
            # This prevents flash on refresh - bar starts at correct width
            ui.html(f'''
                <div class="custom-progress-container {status_class} {engine_class}">
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
        info_parts = [engine_name, job.resolution_display]
        if job.elapsed_time:
            info_parts.append(f"Time: {job.elapsed_time}")
        
        # Build render progress info (frame/samples) - show when rendering OR paused with data
        progress_parts = []
        if job.is_animation and job.display_frame > 0:
            progress_parts.append(f"Frame {job.display_frame}/{job.frame_end}")
        if job.samples_display:
            progress_parts.append(f"Sample {job.samples_display}")
        render_progress = " | ".join(progress_parts)
        
        # Use HTML with ID so we can update via JS
        ui.html(f'''
            <div id="job-info-{job.id}" class="text-sm text-gray-500 mt-2">
                {" | ".join(info_parts)}<span id="job-render-progress-{job.id}">{(" | " + render_progress) if render_progress else ""}</span>
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
        # Marmoset-specific settings
        'render_type': 'still',           # still, turntable, animation
        'renderer': 'Ray Tracing',        # Ray Tracing, Hybrid, Raster
        'samples': 256,
        'shadow_quality': 'High',         # Low, High, Mega
        'use_transparency': False,
        'denoise_mode': 'gpu',            # off, cpu, gpu
        'video_format': 'PNG Sequence',
        'turntable_frames': 120,
        # Render passes - dict of pass_key: enabled
        'render_passes': {
            'beauty': True,
            'albedo': False,
            'normals': False,
            'depth': False,
            'ao': False,
            'roughness': False,
            'metalness': False,
            'emissive': False,
            'reflection': False,
            'diffuse_light': False,
            'specular_light': False,
            'position': False,
            'object_id': False,
            'material_id': False,
        },
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
    engine_buttons = {}
    accent_elements = {}  # Elements that change color with engine selection
    marmoset_settings_container = None  # Reference to Marmoset settings panel for refresh
    
    # Engine-specific colors
    ENGINE_ACCENT_COLORS = {
        "blender": "#ea7600",
        "marmoset": "#ef0343",
    }
    
    def select_engine(eng_type):
        """Update the engine selection, button styles, and accent colors with animation"""
        form['engine_type'] = eng_type
        accent_color = ENGINE_ACCENT_COLORS.get(eng_type, "#3b82f6")
        
        # Update engine selector buttons
        for et, btn in engine_buttons.items():
            if et == eng_type:
                btn.classes(replace='px-3 py-2 rounded engine-btn-selected')
                btn.style(f'''
                    background-color: {ENGINE_ACCENT_COLORS.get(et, "#3b82f6")} !important;
                    color: white !important;
                    transition: all 0.3s ease;
                ''')
            else:
                btn.classes(replace='px-3 py-2 rounded engine-btn-unselected')
                btn.style(f'''
                    background-color: transparent !important;
                    color: #52525b !important;
                    transition: all 0.3s ease;
                ''')
        
        # Update header gradient bar
        if 'header_bar' in accent_elements:
            accent_elements['header_bar'].style(f'''
                height: 3px;
                background: linear-gradient(90deg, transparent 0%, {accent_color} 50%, transparent 100%);
                transition: background 0.4s ease-in-out;
            ''')
        
        # Update submit button with animated color transition
        if 'submit_btn' in accent_elements:
            accent_elements['submit_btn'].style(f'''
                background-color: {accent_color} !important;
                transition: all 0.4s ease-in-out !important;
            ''')
        
        # Refresh Marmoset settings section (show/hide based on engine)
        if 'marmoset_settings' in accent_elements:
            accent_elements['marmoset_settings'].refresh()
        
        # Update CSS variable for all form elements (inputs, checkboxes, selects, etc.)
        ui.run_javascript(f'''
            const dialog = document.querySelector('.accent-dialog');
            if (dialog) {{
                dialog.style.setProperty('--q-primary', '{accent_color}');
                
                // Force repaint for transition
                dialog.classList.add('accent-transition');
                setTimeout(() => dialog.classList.remove('accent-transition'), 400);
            }}
        ''')
    
    with ui.dialog() as dialog, ui.card().style(
        'width: 600px; max-width: 95vw; padding: 0;'
    ).classes('accent-dialog'):
        # Add CSS for dynamic accent colors on all form elements
        ui.html(f'''
            <style>
                .accent-dialog {{
                    --q-primary: {ENGINE_ACCENT_COLORS.get(form["engine_type"], "#ea7600")};
                }}
                
                /* Engine selector button styles */
                .accent-dialog .engine-btn-unselected {{
                    background-color: transparent !important;
                    transition: all 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-unselected .q-btn__content,
                .accent-dialog .engine-btn-unselected .q-btn__content * {{
                    color: #52525b !important;
                    background-color: transparent !important;
                    transition: color 0.3s ease, opacity 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-unselected img {{
                    opacity: 0.4;
                    transition: opacity 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-unselected:hover {{
                    background-color: rgba(255, 255, 255, 0.08) !important;
                }}
                
                .accent-dialog .engine-btn-unselected:hover .q-btn__content,
                .accent-dialog .engine-btn-unselected:hover .q-btn__content * {{
                    color: #a1a1aa !important;
                }}
                
                .accent-dialog .engine-btn-unselected:hover img {{
                    opacity: 0.7;
                }}
                
                .accent-dialog .engine-btn-selected {{
                    transition: all 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-selected .q-btn__content,
                .accent-dialog .engine-btn-selected .q-btn__content * {{
                    color: white !important;
                    background-color: transparent !important;
                    transition: color 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-selected img {{
                    opacity: 1;
                    transition: opacity 0.3s ease;
                }}
                
                .accent-dialog .engine-btn-selected:hover {{
                    filter: brightness(1.15);
                }}
                
                /* Submit button hover */
                .accent-dialog .engine-accent {{
                    transition: all 0.3s ease;
                }}
                
                .accent-dialog .engine-accent:hover {{
                    filter: brightness(1.15);
                    transform: translateY(-1px);
                }}
                
                .accent-dialog .engine-accent:active {{
                    filter: brightness(0.95);
                    transform: translateY(0);
                }}
                
                /* Input field styles */
                .accent-dialog .q-field--focused .q-field__control:after {{
                    border-color: var(--q-primary) !important;
                }}
                
                .accent-dialog .q-field:hover:not(.q-field--focused) .q-field__control:before {{
                    border-color: rgba(255, 255, 255, 0.3) !important;
                }}
                
                .accent-dialog .q-field--focused .q-field__label {{
                    color: var(--q-primary) !important;
                    transition: color 0.4s ease-in-out;
                }}
                
                /* Checkbox styles */
                .accent-dialog .q-checkbox:hover .q-checkbox__bg {{
                    border-color: var(--q-primary) !important;
                }}
                
                .accent-dialog .q-checkbox__inner--truthy .q-checkbox__bg {{
                    background-color: var(--q-primary) !important;
                    border-color: var(--q-primary) !important;
                    transition: background-color 0.4s ease-in-out, border-color 0.4s ease-in-out;
                }}
                
                .accent-dialog .q-checkbox__bg {{
                    transition: background-color 0.4s ease-in-out, border-color 0.4s ease-in-out;
                }}
                
                /* Toggle styles */
                .accent-dialog .q-toggle:hover .q-toggle__track {{
                    opacity: 0.7;
                }}
                
                .accent-dialog .q-toggle__inner--truthy .q-toggle__track {{
                    background-color: var(--q-primary) !important;
                    opacity: 0.5;
                    transition: background-color 0.4s ease-in-out;
                }}
                
                .accent-dialog .q-toggle__inner--truthy .q-toggle__thumb {{
                    background-color: var(--q-primary) !important;
                    transition: background-color 0.4s ease-in-out;
                }}
                
                /* Select styles */
                .accent-dialog .q-select:hover:not(.q-field--focused) .q-field__control:before {{
                    border-color: rgba(255, 255, 255, 0.3) !important;
                }}
                
                .accent-dialog .q-select--focused .q-field__control:after {{
                    border-color: var(--q-primary) !important;
                    transition: border-color 0.4s ease-in-out;
                }}
                
                .accent-dialog .q-field__control:after {{
                    transition: border-color 0.4s ease-in-out;
                }}
                
                /* Flat button styles (Browse, icons) */
                .accent-dialog .q-btn--flat {{
                    color: var(--q-primary) !important;
                    transition: all 0.3s ease-in-out;
                }}
                
                .accent-dialog .q-btn--flat:hover {{
                    background-color: rgba(255, 255, 255, 0.1) !important;
                    filter: brightness(1.2);
                }}
                
                /* Separator styles */
                .accent-dialog .accent-separator {{
                    background: linear-gradient(90deg, transparent, var(--q-primary), transparent);
                    height: 1px;
                    transition: background 0.4s ease-in-out;
                }}
            </style>
        ''', sanitize=False)
        
        # Header with accent gradient bar
        with ui.column().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between p-4'):
                ui.label('Add Render Job').classes('text-lg font-bold')
                ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm')
            # Accent gradient line under header
            initial_color = ENGINE_ACCENT_COLORS.get(form["engine_type"], "#ea7600")
            header_bar = ui.element('div').classes('w-full').style(f'''
                height: 3px;
                background: linear-gradient(90deg, transparent 0%, {initial_color} 50%, transparent 100%);
                transition: background 0.4s ease-in-out;
            ''')
            accent_elements['header_bar'] = header_bar
        
        # Store dialog reference for CSS updates
        accent_elements['dialog'] = dialog
        
        # Form content - let dialog handle scrolling naturally
        with ui.column().classes('w-full p-4 gap-3').style('max-height: 70vh; overflow-y: auto;'):
            
            # Engine selector with logos
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('Engine:').classes('text-gray-400 w-20')
                
                with ui.row().classes('gap-2'):
                    for engine in render_app.engine_registry.get_available():
                        engine_logo = ENGINE_LOGOS.get(engine.engine_type)
                        
                        is_selected = engine.engine_type == form['engine_type']
                        
                        # Capture engine type in closure
                        eng_type = engine.engine_type
                        accent_color = ENGINE_ACCENT_COLORS.get(eng_type, "#3b82f6")
                        
                        if is_selected:
                            btn_class = 'px-3 py-2 rounded engine-btn-selected'
                            btn_style = f'background-color: {accent_color} !important; color: white !important; transition: all 0.3s ease;'
                        else:
                            btn_class = 'px-3 py-2 rounded engine-btn-unselected'
                            btn_style = 'background-color: transparent !important; color: #52525b !important; transition: all 0.3s ease;'
                        
                        with ui.button(on_click=lambda et=eng_type: select_engine(et)).props('flat dense').classes(btn_class).style(btn_style) as btn:
                            with ui.row().classes('items-center gap-2'):
                                if engine_logo:
                                    ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-5 h-5 object-contain')
                                ui.label(engine.name).classes('text-sm')
                        engine_buttons[engine.engine_type] = btn
            
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
                            
                            # Update Marmoset-specific settings from scene
                            if form['engine_type'] == 'marmoset':
                                # Set turntable frames from scene if available
                                if info.get('turntable_frames'):
                                    form['turntable_frames'] = info['turntable_frames']
                                elif info.get('total_frames', 1) > 1:
                                    form['turntable_frames'] = info['total_frames']
                                
                                # Set samples from scene
                                if info.get('video_samples'):
                                    form['samples'] = info['video_samples']
                                elif info.get('samples'):
                                    form['samples'] = info['samples']
                                
                                # Check for turntable or animation
                                if info.get('has_turntable'):
                                    form['render_type'] = 'turntable'
                                elif info.get('has_animation'):
                                    form['render_type'] = 'animation'
                                
                                # Refresh Marmoset settings panel to show updated values
                                if marmoset_settings_container:
                                    try:
                                        marmoset_settings_container.refresh()
                                    except:
                                        pass
                            
                            status_label.set_text('[OK] Loaded')
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
                            select_engine(detected.engine_type)
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
                        select_engine(detected.engine_type)
                    if not form['output_folder']:
                        output_input.value = os.path.dirname(path)
                    # Auto-load scene data
                    load_scene_data(path)
            
            file_input.on('blur', on_file_blur)
            
            # Accent separator
            ui.element('div').classes('accent-separator w-full my-2')
            
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
                ui.label('x').classes('text-gray-400')
                res_h_input = ui.number('Height', value=1080, min=1).classes('w-24')
                res_h_input.bind_value(form, 'res_height')
            
            # Camera
            camera_select = ui.select(['Scene Default'], value='Scene Default', label='Camera').classes('w-full')
            camera_select.bind_value(form, 'camera')
            
            # Animation
            with ui.row().classes('w-full items-center gap-3'):
                anim_checkbox = ui.checkbox('Animation').props('dense')
                anim_checkbox.bind_value(form, 'is_animation')
                frame_start_input = ui.number('Start', value=1, min=1).classes('w-20')
                frame_start_input.bind_value(form, 'frame_start')
                ui.label('to').classes('text-gray-400')
                frame_end_input = ui.number('End', value=250, min=1).classes('w-20')
                frame_end_input.bind_value(form, 'frame_end')
            
            # ============================================================
            # MARMOSET-SPECIFIC SETTINGS (shown only for Marmoset engine)
            # ============================================================
            
            @ui.refreshable
            def marmoset_settings():
                if form['engine_type'] == 'marmoset':
                    ui.element('div').classes('accent-separator w-full my-2')
                    ui.label('Marmoset Settings').classes('text-sm font-bold text-gray-400')
                    
                    # Render type selector
                    with ui.row().classes('w-full items-center gap-2'):
                        def on_render_type_change(e):
                            if 'marmoset_settings' in accent_elements:
                                accent_elements['marmoset_settings'].refresh()
                        
                        render_type_select = ui.select(
                            options=['still', 'turntable', 'animation'],
                            value=form.get('render_type', 'still'),
                            label='Render Type',
                            on_change=on_render_type_change
                        ).classes('w-36')
                        render_type_select.bind_value(form, 'render_type')
                        
                        renderer_select = ui.select(
                            options=['Ray Tracing', 'Hybrid', 'Raster'],
                            value=form.get('renderer', 'Ray Tracing'),
                            label='Renderer'
                        ).classes('w-32')
                        renderer_select.bind_value(form, 'renderer')
                    
                    # Quality settings
                    with ui.row().classes('w-full items-center gap-2'):
                        samples_input = ui.number('Samples', value=form.get('samples', 256), min=1, max=4096).classes('w-24')
                        samples_input.bind_value(form, 'samples')
                        
                        shadow_select = ui.select(
                            options=['Low', 'High', 'Mega'],
                            value=form.get('shadow_quality', 'High'),
                            label='Shadows'
                        ).classes('w-24')
                        shadow_select.bind_value(form, 'shadow_quality')
                        
                        denoise_select = ui.select(
                            options=['off', 'cpu', 'gpu'],
                            value=form.get('denoise_mode', 'gpu'),
                            label='Denoise'
                        ).classes('w-24')
                        denoise_select.bind_value(form, 'denoise_mode')
                    
                    # Transparency checkbox
                    ui.checkbox('Transparent Background').props('dense').bind_value(form, 'use_transparency')
                    
                    # Turntable-specific settings (show when turntable selected)
                    if form.get('render_type') == 'turntable':
                        with ui.row().classes('w-full items-center gap-2 mt-1'):
                            turntable_frames = ui.number('Turntable Frames', value=form.get('turntable_frames', 120), min=1).classes('w-36')
                            turntable_frames.bind_value(form, 'turntable_frames')
                            
                            video_format_select = ui.select(
                                options=['PNG Sequence', 'JPEG Sequence', 'TGA Sequence', 'MP4'],
                                value=form.get('video_format', 'PNG Sequence'),
                                label='Output Format'
                            ).classes('w-36')
                            video_format_select.bind_value(form, 'video_format')
                    
                    # Animation-specific video format (show when animation selected)
                    elif form.get('render_type') == 'animation':
                        with ui.row().classes('w-full items-center gap-2 mt-1'):
                            video_format_select = ui.select(
                                options=['PNG Sequence', 'JPEG Sequence', 'TGA Sequence', 'MP4'],
                                value=form.get('video_format', 'PNG Sequence'),
                                label='Output Format'
                            ).classes('w-36')
                            video_format_select.bind_value(form, 'video_format')
                    
                    # ============================================================
                    # RENDER PASSES SECTION (for still renders)
                    # ============================================================
                    if form.get('render_type') == 'still':
                        with ui.expansion('Render Passes', icon='layers').classes('w-full mt-2 render-passes-expansion'):
                            ui.label('Select additional render passes to output:').classes('text-xs text-gray-500 mb-2')
                            
                            # Get render passes from MarmosetEngine
                            marmoset_engine = render_app.engine_registry.get('marmoset')
                            if marmoset_engine:
                                # Group passes into categories for better organization
                                pass_groups = {
                                    'Essential': ['beauty', 'albedo', 'normals', 'depth', 'ao'],
                                    'Material': ['roughness', 'metalness', 'emissive', 'reflection'],
                                    'Lighting': ['diffuse_light', 'specular_light'],
                                    'Utility': ['position', 'object_id', 'material_id'],
                                }
                                
                                for group_name, pass_keys in pass_groups.items():
                                    ui.label(group_name).classes('text-xs font-bold text-gray-400 mt-2 mb-1')
                                    with ui.row().classes('w-full flex-wrap gap-x-4 gap-y-1'):
                                        for pass_key in pass_keys:
                                            if pass_key in marmoset_engine.RENDER_PASSES:
                                                pass_info = marmoset_engine.RENDER_PASSES[pass_key]
                                                
                                                # Create checkbox for each pass
                                                def make_toggle(key):
                                                    def toggle_pass(e):
                                                        form['render_passes'][key] = e.value
                                                    return toggle_pass
                                                
                                                cb = ui.checkbox(
                                                    pass_info['name'],
                                                    value=form['render_passes'].get(pass_key, False),
                                                    on_change=make_toggle(pass_key)
                                                ).props('dense size=sm').classes('render-pass-checkbox')
                                                cb.tooltip(pass_info['desc'])
            
            marmoset_settings_container = marmoset_settings
            accent_elements['marmoset_settings'] = marmoset_settings
            marmoset_settings()
            
            # Accent separator
            ui.element('div').classes('accent-separator w-full my-2')
            
            # Submit paused
            ui.checkbox('Submit as Paused').props('dense').bind_value(form, 'submit_paused')
        
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
                
                # Build engine settings based on engine type
                if form['engine_type'] == 'marmoset':
                    engine_settings = {
                        "render_type": form.get('render_type', 'still'),
                        "renderer": form.get('renderer', 'Ray Tracing'),
                        "samples": int(form.get('samples', 256)),
                        "shadow_quality": form.get('shadow_quality', 'High'),
                        "use_transparency": form.get('use_transparency', False),
                        "denoise_mode": form.get('denoise_mode', 'gpu'),
                        "denoise_quality": "high",
                        "denoise_strength": 1.0,
                        "video_format": form.get('video_format', 'PNG Sequence'),
                        "turntable_frames": int(form.get('turntable_frames', 120)),
                        "turntable_clockwise": True,
                        # Copy render passes selection
                        "render_passes": form.get('render_passes', {'beauty': True}).copy(),
                    }
                    
                    # Adjust frame settings for turntable
                    is_anim = form['is_animation']
                    frame_start = int(form['frame_start'])
                    frame_end = int(form['frame_end'])
                    
                    if form.get('render_type') == 'turntable':
                        is_anim = True
                        frame_end = int(form.get('turntable_frames', 120))
                        frame_start = 1
                    elif form.get('render_type') == 'animation':
                        is_anim = True
                else:
                    engine_settings = {"use_scene_settings": True, "samples": 128}
                    is_anim = form['is_animation']
                    frame_start = int(form['frame_start'])
                    frame_end = int(form['frame_end'])
                
                job = RenderJob(
                    name=form['name'] or "Untitled",
                    engine_type=form['engine_type'],
                    file_path=form['file_path'],
                    output_folder=form['output_folder'],
                    output_name=form['output_name'],
                    output_format=form['output_format'],
                    camera=form['camera'],
                    is_animation=is_anim,
                    frame_start=frame_start,
                    frame_end=frame_end,
                    original_start=frame_start,
                    res_width=int(form['res_width']),
                    res_height=int(form['res_height']),
                    status='paused' if form['submit_paused'] else 'queued',
                    engine_settings=engine_settings,
                )
                # Set initial progress based on frame range position in timeline
                if job.is_animation and job.frame_end > 0 and job.frame_start > 1:
                    job.progress = int(((job.frame_start - 1) / job.frame_end) * 100)
                render_app.add_job(job)
                dialog.close()
            
            initial_accent = ENGINE_ACCENT_COLORS.get(form['engine_type'], "#ea7600")
            submit_btn = ui.button('Submit Job', on_click=submit).classes('engine-accent').style(f'''
                background-color: {initial_accent} !important;
                transition: background-color 0.4s ease-in-out, transform 0.2s ease !important;
            ''')
            accent_elements['submit_btn'] = submit_btn
    
    dialog.open()


async def show_settings_dialog():
    with ui.dialog() as dialog, ui.card().style('width: 550px; max-width: 95vw; padding: 0;').classes('settings-dialog'):
        # Header
        with ui.row().classes('w-full items-center justify-between p-4 border-b border-zinc-700'):
            ui.label('Settings').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense size=sm').classes('text-zinc-400 settings-close-btn')
        
        # Content
        with ui.column().classes('w-full p-4 gap-4'):
            for engine in render_app.engine_registry.get_all():
                engine_logo = ENGINE_LOGOS.get(engine.engine_type)
                with ui.card().classes('w-full p-3 settings-engine-card'):
                    with ui.row().classes('items-center gap-2 mb-2'):
                        if engine_logo:
                            ui.image(f'/logos/{engine_logo}?{ASSET_VERSION}').classes('w-6 h-6 object-contain')
                        ui.label(engine.name).classes('font-bold')
                        status = "[OK] Available" if engine.is_available else "[X] Not Found"
                        color = "text-zinc-400" if engine.is_available else "text-zinc-600"
                        ui.label(status).classes(f'{color} text-sm')
                    
                    if engine.installed_versions:
                        for v, p in sorted(engine.installed_versions.items(), reverse=True):
                            with ui.row().classes('items-center gap-2 mb-1'):
                                ui.badge(v).classes('version-badge').style('background-color: #3f3f46 !important; color: #e4e4e7 !important;')
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
                        
                        ui.button('Browse', icon='folder_open', on_click=lambda e=engine, i=path_input: browse_exe(e, i)).props('flat dense size=sm').classes('settings-action-btn')
                        ui.button('Add', icon='add', on_click=lambda e=engine, i=path_input: add_custom(e, i)).props('flat dense size=sm').classes('settings-action-btn')
        
        # Footer
        with ui.row().classes('w-full justify-end p-4 border-t border-zinc-700'):
            ui.button('Close', on_click=dialog.close).props('flat').classes('settings-close-btn-footer')
    
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
        /* Global box-sizing for proper layout */
        *, *::before, *::after {
            box-sizing: border-box;
        }
        
        /* Responsive container */
        .responsive-container {
            width: 100%;
            max-width: 100%;
            padding: 1rem;
            box-sizing: border-box;
            overflow-x: hidden;
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
        
        /* ========== CUSTOM TITLE BAR (Frameless Window) ========== */
        
        .custom-titlebar {
            height: 32px;
            background: #0a0a0a;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 8px;
            -webkit-app-region: drag;  /* Make titlebar draggable */
            user-select: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 9999;
            border-bottom: 1px solid #27272a;  /* Subtle separator */
        }
        
        .titlebar-left {
            display: flex;
            align-items: center;
            gap: 8px;
            -webkit-app-region: drag;
        }
        
        .titlebar-icon {
            width: 16px;
            height: 16px;
            object-fit: contain;
            filter: invert(1);  /* Invert for dark theme */
            border-radius: 3px;
        }
        
        .titlebar-title {
            font-size: 12px;
            font-weight: 500;
            color: #a1a1aa;
            letter-spacing: 0.02em;
        }
        
        .titlebar-controls {
            display: flex;
            align-items: center;
            -webkit-app-region: no-drag;  /* Buttons not draggable */
        }
        
        .titlebar-btn {
            width: 46px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
            border: none;
            cursor: pointer;
            transition: background-color 0.15s ease;
            color: #a1a1aa;  /* For stroke="currentColor" */
        }
        
        .titlebar-btn svg {
            width: 10px;
            height: 10px;
            fill: #a1a1aa;
            stroke: #a1a1aa;
            transition: fill 0.15s ease, stroke 0.15s ease;
        }
        
        .titlebar-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
        }
        
        .titlebar-btn:hover svg {
            fill: #ffffff;
            stroke: #ffffff;
        }
        
        .titlebar-btn:active {
            background: rgba(255, 255, 255, 0.05);
        }
        
        /* Close button - red on hover */
        .titlebar-btn-close:hover {
            background: #e81123;
        }
        
        .titlebar-btn-close:hover svg {
            fill: #ffffff;
        }
        
        .titlebar-btn-close:active {
            background: #c42b1c;
        }
        
        /* Adjust layout for custom titlebar - only when titlebar is visible */
        /* The titlebar is 32px fixed at top, so we need to push everything down */
        html, body {
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            overflow-x: hidden !important;
        }
        
        body.has-custom-titlebar {
            padding-top: 0 !important;
        }
        
        /* Push the NiceGUI header down by titlebar height */
        body.has-custom-titlebar .q-header {
            top: 32px !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
        }
        
        /* The q-layout needs margin-top for the titlebar, not padding */
        /* NiceGUI's q-page-container already has padding for the q-header */
        body.has-custom-titlebar .q-layout {
            margin-top: 32px !important;
            padding-top: 0 !important;
            min-height: calc(100vh - 32px) !important;
            width: 100% !important;
            max-width: 100% !important;
            overflow-x: hidden !important;
        }
        
        /* Main content area - this is where scrollbar should appear */
        body.has-custom-titlebar .q-page-container {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* Ensure scrollbar appears inside the content area, not at window edge */
        body.has-custom-titlebar .q-page {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* ========== MAIN WINDOW DESATURATED THEME ========== */
        /* Header buttons - white/gray desaturated style */
        .header-btn,
        .header-btn.q-btn {
            color: #a1a1aa !important;
            background-color: transparent !important;
            transition: all 0.2s ease !important;
        }
        .header-btn .q-icon,
        .header-btn.q-btn .q-icon {
            color: #a1a1aa !important;
        }
        .header-btn:hover,
        .header-btn.q-btn:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        .header-btn:hover .q-icon,
        .header-btn.q-btn:hover .q-icon {
            color: #ffffff !important;
        }
        
        .header-btn-primary,
        .header-btn-primary.q-btn {
            background-color: #3f3f46 !important;
            color: #ffffff !important;
            transition: all 0.2s ease !important;
        }
        .header-btn-primary .q-icon,
        .header-btn-primary.q-btn .q-icon {
            color: #ffffff !important;
        }
        .header-btn-primary:hover,
        .header-btn-primary.q-btn:hover {
            background-color: #52525b !important;
        }
        .header-btn-primary:active {
            background-color: #3f3f46 !important;
        }
        
        /* Job action buttons - desaturated with hover effects */
        .job-action-btn {
            transition: all 0.2s ease !important;
        }
        .job-action-btn:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        .job-action-btn-danger {
            transition: all 0.2s ease !important;
        }
        .job-action-btn-danger:hover {
            color: #f87171 !important;
            background-color: rgba(239, 68, 68, 0.15) !important;
        }
        
        /* Engine-specific action buttons (when rendering) */
        .job-action-btn-engine {
            color: #a1a1aa !important;
            transition: all 0.2s ease !important;
        }
        
        /* Blender themed buttons */
        .job-action-btn-engine-blender {
            color: #ea7600 !important;
        }
        .job-action-btn-engine-blender:hover {
            color: #ffffff !important;
            background-color: rgba(234, 118, 0, 0.2) !important;
        }
        
        /* Marmoset themed buttons */
        .job-action-btn-engine-marmoset {
            color: #ef0343 !important;
        }
        .job-action-btn-engine-marmoset:hover {
            color: #ffffff !important;
            background-color: rgba(239, 3, 67, 0.2) !important;
        }
        
        /* Status badge - no hover */
        .status-badge {
            /* Static - no hover effect */
        }
        
        /* Job cards - no hover effect on the card itself */
        /* Hover effects are only on action buttons within */
        
        /* Settings dialog cards (engine sections) */
        .settings-engine-card,
        .settings-engine-card.q-card {
            transition: all 0.2s ease;
            background-color: #18181b !important;
        }
        .settings-engine-card:hover,
        .settings-engine-card.q-card:hover {
            background-color: #27272a !important;
        }
        
        /* Settings dialog - fully desaturated */
        .settings-dialog,
        .settings-dialog .q-card {
            background-color: #18181b !important;
        }
        
        /* Settings dialog buttons */
        .settings-action-btn,
        .settings-action-btn.q-btn {
            color: #a1a1aa !important;
            background-color: transparent !important;
            transition: all 0.2s ease !important;
        }
        .settings-action-btn:hover,
        .settings-action-btn.q-btn:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        .settings-close-btn,
        .settings-close-btn.q-btn {
            color: #71717a !important;
            transition: all 0.2s ease !important;
        }
        .settings-close-btn:hover,
        .settings-close-btn.q-btn:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        .settings-close-btn-footer,
        .settings-close-btn-footer.q-btn {
            color: #a1a1aa !important;
            background-color: #3f3f46 !important;
            transition: all 0.2s ease !important;
        }
        .settings-close-btn-footer:hover,
        .settings-close-btn-footer.q-btn:hover {
            color: #ffffff !important;
            background-color: #52525b !important;
        }
        
        /* Settings dialog input fields - gray focus */
        .settings-dialog .q-field--focused .q-field__control:after {
            border-color: #71717a !important;
        }
        .settings-dialog .q-field:hover .q-field__control:before {
            border-color: #52525b !important;
        }
        
        /* Version badge styling */
        .version-badge .q-badge,
        .settings-dialog .q-badge {
            background-color: #3f3f46 !important;
            color: #e4e4e7 !important;
        }
        
        /* ========== EXPANSION PANELS ========== */
        .log-expansion .q-expansion-item__container {
            background-color: #18181b !important;
            transition: all 0.2s ease;
        }
        .log-expansion .q-item {
            color: #a1a1aa !important;
            transition: all 0.2s ease;
        }
        .log-expansion .q-item:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.05) !important;
        }
        .log-expansion .q-item__section--avatar {
            color: #71717a !important;
        }
        
        /* ========== GLOBAL INTERACTIVE HOVER ========== */
        /* All flat buttons in main window */
        .q-btn--flat:not(.accent-dialog .q-btn--flat):not(.header-btn):not(.header-btn-primary):not(.job-action-btn):not(.job-action-btn-danger):not(.settings-action-btn):not(.settings-close-btn):not(.settings-close-btn-footer) {
            color: #a1a1aa !important;
            transition: all 0.2s ease !important;
        }
        .q-btn--flat:not(.accent-dialog .q-btn--flat):not(.header-btn):not(.header-btn-primary):not(.job-action-btn):not(.job-action-btn-danger):not(.settings-action-btn):not(.settings-close-btn):not(.settings-close-btn-footer):hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        /* Input fields in main window - desaturated focus */
        .q-field:not(.accent-dialog .q-field) .q-field__control:after {
            border-color: #52525b !important;
        }
        .q-field:not(.accent-dialog .q-field):hover .q-field__control:before {
            border-color: #71717a !important;
        }
        .q-field--focused:not(.accent-dialog .q-field--focused) .q-field__control:after {
            border-color: #a1a1aa !important;
        }
        
        /* ========== ENGINE LOGO STYLING ========== */
        /* Invert dark logos for visibility on dark theme */
        /* Note: marmoset_logo is already white, only invert wain_logo if needed */
        img[src*="wain_logo"] {
            filter: invert(1);
        }
        
        /* Marmoset logo is white - no invert needed */
        img[src*="marmoset_logo"] {
            /* Already white on dark background */
        }
        
        /* Rounded corners for wain logo in header */
        .header img[src*="wain_logo"],
        img[src*="wain_logo"].rounded-lg {
            border-radius: 8px;
            overflow: hidden;
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
        ::-webkit-scrollbar-corner {
            background: #18181b;
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
        /* Completely disable ripple/focus circle that gets stuck */
        .q-checkbox .q-checkbox__inner::before,
        .q-radio .q-radio__inner::before,
        .q-toggle .q-toggle__inner::before,
        .q-checkbox__bg::before,
        .q-radio__bg::before,
        .q-focus-helper,
        .q-checkbox .q-focus-helper,
        .q-radio .q-focus-helper,
        .q-toggle .q-focus-helper,
        .q-checkbox__focus-helper,
        .q-radio__focus-helper,
        .q-toggle__focus-helper {
            display: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
            background: transparent !important;
            box-shadow: none !important;
            transform: scale(0) !important;
            width: 0 !important;
            height: 0 !important;
        }
        
        /* Remove the circular highlight/ripple on all states */
        .q-checkbox__inner,
        .q-radio__inner,
        .q-toggle__inner {
            background: transparent !important;
        }
        
        /* Kill all pseudo-elements that could show the circle */
        .q-checkbox__inner::before,
        .q-checkbox__inner::after,
        .q-radio__inner::before,
        .q-radio__inner::after,
        .q-toggle__inner::before,
        .q-toggle__inner::after,
        .q-checkbox__bg::after,
        .q-radio__bg::after {
            display: none !important;
            content: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
            background: transparent !important;
            transform: scale(0) !important;
        }
        
        /* Disable all transitions to prevent stuck states */
        .q-checkbox__bg,
        .q-radio__bg,
        .q-toggle__inner,
        .q-checkbox__svg,
        .q-radio__check,
        .q-toggle__track,
        .q-toggle__thumb {
            transition: none !important;
        }
        
        /* Style the checkbox box itself */
        .q-checkbox__bg {
            border-radius: 4px !important;
            border: 2px solid #71717a !important;
            background: transparent !important;
        }
        
        /* Checked state */
        .q-checkbox--truthy .q-checkbox__bg {
            border-color: #3b82f6 !important;
            background: #3b82f6 !important;
        }
        
        /* Hover effect on checkbox */
        .q-checkbox:hover .q-checkbox__bg {
            border-color: #a1a1aa !important;
        }
        
        .q-checkbox--truthy:hover .q-checkbox__bg {
            border-color: #60a5fa !important;
            background: #60a5fa !important;
        }
        
        /* Checkmark color */
        .q-checkbox__svg {
            color: white !important;
        }
        
        /* Button toggle group */
        .q-btn-toggle .q-btn {
            transition: background-color 0.1s ease, color 0.1s ease !important;
        }
        
        /* Ripple effect - completely disable everywhere */
        .q-ripple,
        [class*="q-ripple"],
        .q-btn .q-ripple,
        .q-checkbox .q-ripple,
        .q-radio .q-ripple,
        .q-toggle .q-ripple {
            display: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }
        
        /* ===== NUKE THE FOCUS CIRCLE COMPLETELY ===== */
        /* This is the semi-transparent circle that gets stuck */
        .q-checkbox__inner--truthy::before,
        .q-checkbox__inner--falsy::before,
        .q-checkbox__inner::before,
        .q-checkbox .q-checkbox__inner::before,
        .q-radio__inner--truthy::before,
        .q-radio__inner--falsy::before,
        .q-radio__inner::before,
        .q-toggle__inner--truthy::before,
        .q-toggle__inner--falsy::before,
        .q-toggle__inner::before {
            display: none !important;
            content: '' !important;
            opacity: 0 !important;
            visibility: hidden !important;
            background: transparent !important;
            background-color: transparent !important;
            transform: scale(0) !important;
            width: 0 !important;
            height: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
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
        /* ===== RENDERING - Engine-specific colors ===== */
        .custom-progress-rendering .custom-progress-fill {
            background: #a1a1aa;  /* Default gray if no engine match */
            transition: background 0.3s ease;
        }
        
        /* Blender - Orange */
        .custom-progress-rendering.custom-progress-engine-blender .custom-progress-fill {
            background: #ea7600;
        }
        .custom-progress-rendering.custom-progress-engine-blender .custom-progress-track {
            box-shadow: 0 0 8px rgba(234, 118, 0, 0.4);
            animation: render-glow-blender 2s ease-in-out infinite;
        }
        @keyframes render-glow-blender {
            0%, 100% { box-shadow: 0 0 4px rgba(234, 118, 0, 0.3); }
            50% { box-shadow: 0 0 12px rgba(234, 118, 0, 0.6); }
        }
        
        /* Marmoset - Red/Pink */
        .custom-progress-rendering.custom-progress-engine-marmoset .custom-progress-fill {
            background: #ef0343;
        }
        .custom-progress-rendering.custom-progress-engine-marmoset .custom-progress-track {
            box-shadow: 0 0 8px rgba(239, 3, 67, 0.4);
            animation: render-glow-marmoset 2s ease-in-out infinite;
        }
        @keyframes render-glow-marmoset {
            0%, 100% { box-shadow: 0 0 4px rgba(239, 3, 67, 0.3); }
            50% { box-shadow: 0 0 12px rgba(239, 3, 67, 0.6); }
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
            animation: shimmer 2s ease-in-out infinite;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%); opacity: 0; }
            50% { opacity: 1; }
            100% { transform: translateX(200%); opacity: 0; }
        }
        
        /* ===== QUEUED - Neutral gray ===== */
        .custom-progress-queued .custom-progress-fill {
            background: #52525b;
        }
        
        /* ===== PAUSED - Neutral white/gray with subtle glow ===== */
        .custom-progress-paused .custom-progress-fill {
            background: #a1a1aa;
        }
        
        .custom-progress-paused .custom-progress-track {
            box-shadow: 0 0 8px rgba(161, 161, 170, 0.3);
            animation: paused-glow 2s ease-in-out infinite;
        }
        
        @keyframes paused-glow {
            0%, 100% { box-shadow: 0 0 4px rgba(161, 161, 170, 0.2); }
            50% { box-shadow: 0 0 10px rgba(161, 161, 170, 0.4); }
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
            
            // MutationObserver to immediately remove any notifications and stuck checkbox effects
            const observer = new MutationObserver(function(mutations) {
                // Remove notifications
                const notifications = document.querySelectorAll(
                    '.q-notification, .q-notifications, [class*="q-notification"]'
                );
                notifications.forEach(n => {
                    n.style.display = 'none';
                    n.remove();
                });
                
                // Clean up stuck checkbox/radio/toggle ripple and focus effects
                document.querySelectorAll('.q-focus-helper, .q-ripple, [class*="focus-helper"]').forEach(el => {
                    el.style.cssText = 'display:none!important;opacity:0!important;visibility:hidden!important;transform:scale(0)!important;';
                    try { el.remove(); } catch(e) {}
                });
            });
            
            observer.observe(document.body, { childList: true, subtree: true });
            
            // Clean up checkbox/toggle stuck states on any click
            document.addEventListener('click', function(e) {
                // Immediate cleanup
                cleanupCheckboxEffects();
                // Also cleanup after Quasar animations
                setTimeout(cleanupCheckboxEffects, 50);
                setTimeout(cleanupCheckboxEffects, 150);
                setTimeout(cleanupCheckboxEffects, 300);
            }, true);
            
            // Clean up on mouseup too (catches drag releases)
            document.addEventListener('mouseup', function(e) {
                setTimeout(cleanupCheckboxEffects, 50);
            }, true);
            
            // Aggressive cleanup function
            function cleanupCheckboxEffects() {
                // Hide all focus helpers and ripples
                document.querySelectorAll('.q-focus-helper, .q-ripple, [class*="focus-helper"]').forEach(el => {
                    el.style.cssText = 'display:none!important;opacity:0!important;visibility:hidden!important;transform:scale(0)!important;';
                });
                // Reset inner element backgrounds
                document.querySelectorAll('.q-checkbox__inner, .q-radio__inner, .q-toggle__inner').forEach(el => {
                    el.style.background = 'transparent';
                });
                // Force hide any pseudo-element circles by setting the parent overflow
                document.querySelectorAll('.q-checkbox, .q-radio, .q-toggle').forEach(el => {
                    el.style.overflow = 'visible';
                });
            }
            
            // Run cleanup periodically as a safety net
            setInterval(cleanupCheckboxEffects, 500);
            
            // ========== SMOOTH PROGRESS BAR ANIMATION ==========
            // Track current animated widths for each progress bar
            const progressState = {};
            const ANIMATION_SPEED = 0.06; // Easing factor (0-1, lower = smoother)
            const MIN_STEP = 0.15; // Minimum step per frame for visible movement
            
            // Global function to update progress without UI refresh
            window.updateJobProgress = function(jobId, progress, elapsed, framesDisplay, samplesDisplay) {
                const fill = document.getElementById('progress-fill-' + jobId);
                const label = document.getElementById('progress-label-' + jobId);
                const info = document.getElementById('job-info-' + jobId);
                const renderProgress = document.getElementById('job-render-progress-' + jobId);
                
                if (fill) {
                    fill.dataset.target = progress;
                }
                if (label) {
                    label.textContent = progress + '%';
                }
                if (info && elapsed) {
                    // Get the base text without the render progress span
                    var baseText = info.textContent;
                    if (renderProgress) {
                        baseText = baseText.replace(renderProgress.textContent, '').trim();
                    }
                    
                    // Update elapsed time
                    if (baseText.includes('Time:')) {
                        baseText = baseText.replace(/Time: [0-9:]+/, 'Time: ' + elapsed);
                    } else {
                        baseText = baseText + ' | Time: ' + elapsed;
                    }
                    
                    // Build render progress string (frame/samples)
                    var progressParts = [];
                    // For animations, show current/total frame
                    if (framesDisplay && framesDisplay.includes('/')) {
                        progressParts.push('Frame ' + framesDisplay);
                    }
                    if (samplesDisplay) {
                        progressParts.push('Sample ' + samplesDisplay);
                    }
                    var progressText = progressParts.length > 0 ? ' | ' + progressParts.join(' | ') : '';
                    
                    // Reconstruct the HTML (same gray color, no special styling)
                    info.innerHTML = baseText + '<span id="job-render-progress-' + jobId + '">' + progressText + '</span>';
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
    
    # Custom title bar for frameless window (only visible in native mode)
    # Uses pywebview's JavaScript API for window controls
    ui.add_body_html('''
    <div id="custom-titlebar" class="custom-titlebar" style="display: none;">
        <div class="titlebar-left">
            <img src="/logos/wain_logo.png" class="titlebar-icon" alt="">
            <span class="titlebar-title">Wain</span>
        </div>
        <div class="titlebar-controls">
            <!-- Minimize button -->
            <button class="titlebar-btn" id="titlebar-minimize" title="Minimize">
                <svg viewBox="0 0 10 10">
                    <rect x="0" y="4.5" width="10" height="1"/>
                </svg>
            </button>
            <!-- Maximize/Restore button -->
            <button class="titlebar-btn" id="titlebar-maximize" title="Maximize">
                <svg viewBox="0 0 10 10" id="maximize-icon">
                    <rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1"/>
                </svg>
                <svg viewBox="0 0 10 10" id="restore-icon" style="display: none;">
                    <!-- Restore icon (two overlapping windows) -->
                    <path d="M2,0.5 L9.5,0.5 L9.5,7" fill="none" stroke="currentColor" stroke-width="1"/>
                    <rect x="0.5" y="2.5" width="7" height="7" fill="none" stroke="currentColor" stroke-width="1"/>
                </svg>
            </button>
            <!-- Close button -->
            <button class="titlebar-btn titlebar-btn-close" id="titlebar-close" title="Close">
                <svg viewBox="0 0 10 10">
                    <line x1="0" y1="0" x2="10" y2="10" stroke="currentColor" stroke-width="1.2"/>
                    <line x1="10" y1="0" x2="0" y2="10" stroke="currentColor" stroke-width="1.2"/>
                </svg>
            </button>
        </div>
    </div>
    <script>
        // Show title bar only in native pywebview mode
        document.addEventListener('DOMContentLoaded', function() {
            // Check if we're in pywebview (native mode)
            function checkPywebview() {
                if (window.pywebview && window.pywebview.api) {
                    // Add body class for CSS layout adjustments
                    document.body.classList.add('has-custom-titlebar');
                    
                    // Show the custom title bar
                    const titlebar = document.getElementById('custom-titlebar');
                    if (titlebar) {
                        titlebar.style.display = 'flex';
                    }
                    
                    // Wire up the window control buttons
                    document.getElementById('titlebar-minimize').addEventListener('click', function() {
                        window.pywebview.api.minimize();
                    });
                    
                    const maxBtn = document.getElementById('titlebar-maximize');
                    const maxIcon = document.getElementById('maximize-icon');
                    const restoreIcon = document.getElementById('restore-icon');
                    let isMaximized = false;
                    
                    function setMaximizedState(maximized) {
                        isMaximized = maximized;
                        if (maximized) {
                            maxIcon.style.display = 'none';
                            restoreIcon.style.display = 'block';
                            maxBtn.title = 'Restore';
                        } else {
                            maxIcon.style.display = 'block';
                            restoreIcon.style.display = 'none';
                            maxBtn.title = 'Maximize';
                        }
                    }
                    
                    maxBtn.addEventListener('click', function() {
                        if (isMaximized) {
                            window.pywebview.api.restore();
                            setMaximizedState(false);
                        } else {
                            window.pywebview.api.maximize();
                            setMaximizedState(true);
                        }
                    });
                    
                    // Double-click title bar to maximize (standard Windows behavior)
                    document.querySelector('.titlebar-left').addEventListener('dblclick', function() {
                        if (isMaximized) {
                            window.pywebview.api.restore();
                            setMaximizedState(false);
                        } else {
                            window.pywebview.api.maximize();
                            setMaximizedState(true);
                        }
                    });
                    
                    document.getElementById('titlebar-close').addEventListener('click', function() {
                        window.pywebview.api.close();
                    });
                    
                    console.log('Custom title bar initialized for native mode');
                } else {
                    // Not in pywebview, hide title bar
                    document.body.classList.remove('has-custom-titlebar');
                    const titlebar = document.getElementById('custom-titlebar');
                    if (titlebar) titlebar.style.display = 'none';
                }
            }
            
            // pywebview API might not be ready immediately
            if (window.pywebview && window.pywebview.api) {
                checkPywebview();
            } else {
                // Wait for pywebview to be ready
                window.addEventListener('pywebviewready', checkPywebview);
                // Also try after a short delay as fallback
                setTimeout(checkPywebview, 500);
            }
        });
    </script>
    ''')
    
    with ui.header().classes('items-center justify-between px-4 md:px-6 py-3 bg-zinc-900 header-main'):
        with ui.row().classes('items-center gap-4'):
            ui.image(f'/logos/wain_logo.png?{ASSET_VERSION}').classes('w-10 h-10 object-contain rounded-lg')
        
        with ui.row().classes('gap-2'):
            ui.button('Settings', icon='settings', on_click=show_settings_dialog).props('flat').classes('header-btn text-zinc-400')
            ui.button('Add Job', icon='add', on_click=show_add_job_dialog).props('flat').classes('header-btn-primary')
    
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
            render_app.job_count_container = job_count
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
        
        with ui.expansion('Log', icon='terminal').classes('w-full log-expansion'):
            # Header row with copy button
            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('Render Log').classes('text-sm text-gray-400')
                with ui.row().classes('gap-2'):
                    def save_log_to_file():
                        # Save log to a temp file and open it
                        import tempfile
                        import subprocess
                        log_text = '\n'.join(render_app.log_messages[-100:])
                        log_path = os.path.join(tempfile.gettempdir(), 'wane_log.txt')
                        try:
                            with open(log_path, 'w', encoding='utf-8') as f:
                                f.write(log_text)
                            # Open in default text editor
                            if sys.platform == 'win32':
                                os.startfile(log_path)
                            elif sys.platform == 'darwin':
                                subprocess.run(['open', log_path])
                            else:
                                subprocess.run(['xdg-open', log_path])
                            render_app.log(f"Log saved to: {log_path}")
                        except Exception as e:
                            render_app.log(f"Failed to save log: {e}")
                    
                    def clear_log():
                        render_app.log_messages.clear()
                        render_app.log("Log cleared")
                        if render_app.log_container:
                            render_app.log_container.refresh()
                    
                    ui.button(icon='open_in_new', on_click=save_log_to_file).props('flat dense size=sm').classes('text-zinc-400 hover:text-white').tooltip('Open log in text editor')
                    ui.button(icon='delete_sweep', on_click=clear_log).props('flat dense size=sm').classes('text-zinc-400 hover:text-white').tooltip('Clear log')
            
            @ui.refreshable
            def log_display():
                # Use scroll_area with scroll-to-bottom behavior
                with ui.scroll_area().classes('w-full h-48 bg-zinc-900 rounded').props('id="log-scroll"') as scroll:
                    with ui.column().classes('p-2 gap-0 font-mono text-xs'):
                        # Show messages in chronological order (oldest first, newest at bottom)
                        for msg in render_app.log_messages[-50:]:
                            ui.label(msg).classes('text-gray-400 select-text')
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
    
    # Timer for queue processing and UI updates (every 250ms for real-time progress)
    ui.timer(0.25, render_app.process_queue)
    
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
    mode = "Desktop (Native)" if HAS_NATIVE_MODE else "Browser"
    print(f"Starting Wain ({mode} Mode)...")
    print(f"Python: {sys.version}")
    
    if HAS_NATIVE_MODE:
        print("Using NiceGUI with PyQt6/pywebview backend")
    else:
        print("Running in browser mode")
        print("Open http://localhost:8080 if browser doesn't open automatically")
    
    # Serve logo/asset files from assets subfolder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, 'assets')
    
    # Create assets folder if it doesn't exist
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
    
    # Clear Qt WebEngine cache to ensure fresh assets load (native mode only)
    # This fixes issues where old images are cached by the webview
    if HAS_NATIVE_MODE:
        def clear_webview_cache():
            """Clear Qt WebEngine cache directories."""
            import shutil
            cache_dirs = []
            
            # Windows cache locations
            if os.name == 'nt':
                local_appdata = os.environ.get('LOCALAPPDATA', '')
                appdata = os.environ.get('APPDATA', '')
                if local_appdata:
                    cache_dirs.append(os.path.join(local_appdata, 'nicegui'))
                    cache_dirs.append(os.path.join(local_appdata, 'pywebview'))
                if appdata:
                    cache_dirs.append(os.path.join(appdata, 'nicegui'))
                    cache_dirs.append(os.path.join(appdata, 'pywebview'))
            else:
                # Linux/Mac
                home = os.path.expanduser('~')
                cache_dirs.append(os.path.join(home, '.local', 'share', 'nicegui'))
                cache_dirs.append(os.path.join(home, '.cache', 'nicegui'))
            
            for cache_dir in cache_dirs:
                if os.path.exists(cache_dir):
                    try:
                        shutil.rmtree(cache_dir)
                        print(f"Cleared cache: {cache_dir}")
                    except Exception as e:
                        print(f"Could not clear cache {cache_dir}: {e}")
        
        # Clear cache on startup to ensure fresh assets
        clear_webview_cache()
    
    app.add_static_files('/logos', assets_dir)
    
    # Set window icon path - prefer .ico for Windows compatibility
    icon_ico = os.path.join(assets_dir, 'wain_icon.ico')
    icon_png = os.path.join(assets_dir, 'wain_logo.png')
    
    # On Windows, try to create .ico from .png if it doesn't exist
    # Windows taskbar strongly prefers .ico format
    if sys.platform == 'win32' and not os.path.exists(icon_ico) and os.path.exists(icon_png):
        try:
            from PIL import Image
            print(f"Creating ICO from PNG: {icon_png}")
            img = Image.open(icon_png)
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            # Create ICO with multiple sizes for best display
            img.save(icon_ico, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            print(f"Created ICO file: {icon_ico}")
        except ImportError:
            print("PIL not available - cannot create ICO from PNG")
            print("For best taskbar icon, install Pillow: pip install Pillow")
        except Exception as e:
            print(f"Could not create ICO file: {e}")
    
    # Use ICO for native window icon (Windows), PNG as fallback for favicon
    if os.path.exists(icon_ico):
        favicon_path = icon_ico
    elif os.path.exists(icon_png):
        favicon_path = icon_png
    else:
        favicon_path = None
    
    if HAS_NATIVE_MODE:
        # Configure native window settings for pywebview
        print("Configuring native window...")
        app.native.window_args['title'] = 'Wain'
        app.native.window_args['frameless'] = True  # Remove native title bar for custom UI
        app.native.window_args['easy_drag'] = False  # We handle dragging in CSS
        
        # Create JS API for window controls (minimize, maximize, close)
        class WindowAPI:
            """JavaScript API for window controls in frameless mode.
            Uses Windows API directly for smooth animations.
            """
            
            def _get_hwnd(self):
                """Get the window handle."""
                try:
                    import ctypes
                    return ctypes.windll.user32.FindWindowW(None, 'Wain')
                except:
                    return None
            
            def minimize(self):
                """Minimize the window with animation."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            # SW_MINIMIZE = 6 triggers standard Windows minimize animation
                            ctypes.windll.user32.ShowWindow(hwnd, 6)
                            return True
                    else:
                        # Fallback for non-Windows
                        import webview
                        if webview.windows:
                            webview.windows[0].minimize()
                            return True
                except Exception as e:
                    print(f"Minimize error: {e}")
                return False
            
            def maximize(self):
                """Maximize the window with animation."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            # SW_MAXIMIZE = 3 triggers standard Windows maximize animation
                            ctypes.windll.user32.ShowWindow(hwnd, 3)
                            return True
                    else:
                        import webview
                        if webview.windows:
                            webview.windows[0].maximize()
                            return True
                except Exception as e:
                    print(f"Maximize error: {e}")
                return False
            
            def restore(self):
                """Restore the window with animation."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            # SW_RESTORE = 9 triggers standard Windows restore animation
                            ctypes.windll.user32.ShowWindow(hwnd, 9)
                            return True
                    else:
                        import webview
                        if webview.windows:
                            webview.windows[0].restore()
                            return True
                except Exception as e:
                    print(f"Restore error: {e}")
                return False
            
            def is_maximized(self):
                """Check if window is maximized."""
                try:
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = self._get_hwnd()
                        if hwnd:
                            return bool(ctypes.windll.user32.IsZoomed(hwnd))
                except Exception as e:
                    print(f"IsMaximized error: {e}")
                return False
            
            def toggle_maximize(self):
                """Toggle between maximized and restored state."""
                if self.is_maximized():
                    return self.restore()
                else:
                    return self.maximize()
            
            def close(self):
                """Close the window."""
                try:
                    import webview
                    if webview.windows:
                        webview.windows[0].destroy()
                        return True
                except Exception as e:
                    print(f"Close error: {e}")
                return False
        
        # Expose the API to JavaScript
        app.native.window_args['js_api'] = WindowAPI()
        
        # Set taskbar icon on Windows using native API
        if sys.platform == 'win32':
            import ctypes
            
            # CRITICAL: Set AppUserModelID BEFORE window is created
            # This tells Windows to treat Wane as its own application (not grouped with Python)
            # Without this, Windows shows the Python icon in the taskbar
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Wane.RenderManager.1')
                print("Set AppUserModelID for taskbar")
            except Exception as e:
                print(f"Could not set AppUserModelID: {e}")
            
            def set_taskbar_icon_windows():
                """Set the taskbar icon using Windows API after window is created."""
                import time
                
                # Wait for window to be created
                time.sleep(2.0)
                
                try:
                    user32 = ctypes.windll.user32
                    
                    # Find the Wain window by title
                    hwnd = user32.FindWindowW(None, 'Wain')
                    if hwnd == 0:
                        print("Could not find Wain window for icon")
                        return
                    
                    # Constants for Win32 API
                    ICON_SMALL = 0
                    ICON_BIG = 1
                    WM_SETICON = 0x0080
                    IMAGE_ICON = 1
                    LR_LOADFROMFILE = 0x0010
                    LR_DEFAULTSIZE = 0x0040
                    
                    # Try loading ICO file first (required for taskbar), fall back to PNG
                    icon_to_load = icon_ico if os.path.exists(icon_ico) else icon_png
                    
                    if not icon_to_load or not os.path.exists(icon_to_load):
                        print("No icon file found")
                        return
                    
                    print(f"Loading icon from: {icon_to_load}")
                    
                    # Load the icon - use specific sizes for taskbar
                    # Load large icon (32x32 or 48x48 for taskbar)
                    hIconBig = user32.LoadImageW(
                        None,
                        icon_to_load,
                        IMAGE_ICON,
                        48, 48,  # Large icon size for taskbar
                        LR_LOADFROMFILE
                    )
                    
                    # Load small icon (16x16 for title bar)
                    hIconSmall = user32.LoadImageW(
                        None,
                        icon_to_load,
                        IMAGE_ICON,
                        16, 16,  # Small icon size for title bar
                        LR_LOADFROMFILE
                    )
                    
                    if hIconBig:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hIconBig)
                        print("Set large taskbar icon")
                    else:
                        print("Could not load large icon")
                        
                    if hIconSmall:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hIconSmall)
                        print("Set small title bar icon")
                    else:
                        print("Could not load small icon")
                        
                except Exception as e:
                    print(f"Failed to set taskbar icon: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Run icon setter in background thread (only if we have an icon file)
            if (icon_ico and os.path.exists(icon_ico)) or (icon_png and os.path.exists(icon_png)):
                threading.Thread(target=set_taskbar_icon_windows, daemon=True).start()
        
        print("Starting UI (native mode)...")
        ui.run(
            title='Wain',
            favicon=favicon_path,     # Window/tab icon
            dark=True,
            reload=False,
            native=True,              # Desktop window instead of browser
            window_size=(1200, 850),
            fullscreen=False,
            reconnect_timeout=0,      # Disable reconnection attempts (desktop app)
            show=True,                # Show window immediately
        )
    else:
        # Browser mode - open in default browser
        print("Starting UI (browser mode)...")
        ui.run(
            title='Wain',
            favicon=favicon_path,     # Tab icon
            dark=True,
            reload=False,
            native=False,             # Run in browser
            port=8080,                # Fixed port for browser mode
            show=True,                # Auto-open browser
        )
