#!/usr/bin/env python3
"""
Render Manager - Multi-Engine Edition (ITT02)
Queue-based render management with pause/resume support
Supports: Blender, Marmoset Toolbag
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import os
import sys
import json
import re
import tempfile
import uuid
import gzip
from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any, Tuple

# Try to import PIL for image handling
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ============================================================================
# THEME
# ============================================================================
class Theme:
    BG_BASE = "#09090b"
    BG_CARD = "#18181b"
    BG_ELEVATED = "#27272a"
    BG_INPUT = "#27272a"
    BG_HOVER = "#3f3f46"
    BORDER = "#27272a"
    TEXT_PRIMARY = "#fafafa"
    TEXT_SECONDARY = "#a1a1aa"
    TEXT_MUTED = "#71717a"
    BLUE = "#2563eb"
    GREEN = "#22c55e"
    YELLOW = "#eab308"
    ORANGE = "#f97316"
    RED = "#ef4444"
    PURPLE = "#a855f7"
    CYAN = "#06b6d4"


# ============================================================================
# ENGINE COLOR SCHEME
# ============================================================================
ENGINE_COLORS = {
    "blender": Theme.ORANGE,
    "marmoset": Theme.CYAN,
}


# ============================================================================
# DATA MODELS
# ============================================================================
@dataclass
class RenderJob:
    """Universal render job that works with any engine"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    engine_type: str = "blender"  # "blender", "marmoset"
    file_path: str = ""
    output_folder: str = ""
    output_name: str = "render_"
    output_format: str = "PNG"
    status: str = "queued"
    progress: int = 0
    
    # Animation settings (universal)
    is_animation: bool = False
    frame_start: int = 1
    frame_end: int = 250
    current_frame: int = 0
    original_start: int = 0
    
    # Resolution (universal)
    res_width: int = 1920
    res_height: int = 1080
    
    # Camera (universal)
    camera: str = "Scene Default"
    
    # Engine-specific settings stored as dict
    engine_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
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
                    return f"{next_frame}-{self.frame_end} (paused at {self.current_frame})"
                return f"Complete ({self.frame_start}-{self.frame_end})"
            return f"{self.frame_start}-{self.frame_end}"
        return str(self.frame_start)
    
    @property 
    def resolution_display(self) -> str:
        return f"{self.res_width}x{self.res_height}"
    
    @property
    def file_name(self) -> str:
        return os.path.basename(self.file_path) if self.file_path else ""
    
    # Convenience getters for engine-specific settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.engine_settings.get(key, default)
    
    def set_setting(self, key: str, value: Any):
        self.engine_settings[key] = value


@dataclass
class AppSettings:
    """Application settings supporting multiple engines"""
    # Per-engine paths: {"blender": {"4.2.0": "path", ...}, "marmoset": {"5.0": "path"}}
    engine_paths: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    # Default versions per engine
    default_versions: Dict[str, str] = field(default_factory=dict)
    
    # Global defaults
    default_engine_type: str = "blender"
    default_resolution: str = "1920x1080"
    default_format: str = "PNG"
    
    # Blender-specific defaults
    blender_default_engine: str = "Cycles"
    blender_default_samples: int = 128
    blender_use_gpu: bool = True
    blender_compute_device: str = "Auto"
    
    # Marmoset-specific defaults
    marmoset_renderer: str = "Ray Tracing"
    marmoset_samples: int = 256
    marmoset_shadow_quality: str = "High"
    
    # Legacy compatibility
    @property
    def blender_paths(self) -> Dict[str, str]:
        return self.engine_paths.get("blender", {})


# ============================================================================
# ABSTRACT RENDER ENGINE
# ============================================================================
class RenderEngine(ABC):
    """Abstract base class for all render engines"""
    
    name: str = "Unknown"
    engine_type: str = "unknown"
    file_extensions: List[str] = []
    icon: str = "⬡"
    color: str = Theme.TEXT_MUTED
    
    def __init__(self):
        self.installed_versions: Dict[str, str] = {}  # version -> path
        self.current_process: Optional[subprocess.Popen] = None
        self.is_cancelling = False
    
    @abstractmethod
    def scan_installed_versions(self):
        """Find all installed versions of this application"""
        pass
    
    @abstractmethod
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """Extract scene information (cameras, resolution, settings, etc.)"""
        pass
    
    @abstractmethod
    def start_render(self, job: RenderJob, start_frame: int,
                    on_progress: Callable, on_complete: Callable,
                    on_error: Callable, on_log: Callable = None):
        """Start rendering a job"""
        pass
    
    @abstractmethod
    def cancel_render(self):
        """Cancel the current render"""
        pass
    
    @abstractmethod
    def get_output_formats(self) -> Dict[str, str]:
        """Get available output formats"""
        pass
    
    @abstractmethod
    def get_default_settings(self) -> Dict[str, Any]:
        """Get default engine-specific settings"""
        pass
    
    @abstractmethod
    def build_settings_ui(self, parent: tk.Frame, job_vars: Dict[str, tk.Variable]) -> tk.Frame:
        """Build the engine-specific settings UI panel"""
        pass
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """Add a custom installation path, returns version or None"""
        return None
    
    @property
    def is_available(self) -> bool:
        return len(self.installed_versions) > 0
    
    @property
    def version_display(self) -> str:
        if self.installed_versions:
            count = len(self.installed_versions)
            newest = sorted(self.installed_versions.keys(), reverse=True)[0]
            if count == 1:
                return f"{self.name} {newest}"
            return f"{self.name} {newest} (+{count-1} more)"
        return f"{self.name} not detected"
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open a file in the application (not background mode)"""
        pass


# ============================================================================
# BLENDER ENGINE
# ============================================================================
class BlenderEngine(RenderEngine):
    """Blender render engine implementation"""
    
    name = "Blender"
    engine_type = "blender"
    file_extensions = [".blend"]
    icon = "⬡"
    color = Theme.ORANGE
    
    SEARCH_PATHS = [
        r"C:\Program Files\Blender Foundation\Blender 4.5",
        r"C:\Program Files\Blender Foundation\Blender 4.4",
        r"C:\Program Files\Blender Foundation\Blender 4.3",
        r"C:\Program Files\Blender Foundation\Blender 4.2",
        r"C:\Program Files\Blender Foundation\Blender 4.1",
        r"C:\Program Files\Blender Foundation\Blender 4.0",
        r"C:\Program Files\Blender Foundation\Blender 3.6",
        r"C:\Program Files\Blender Foundation\Blender 3.5",
    ]
    
    OUTPUT_FORMATS = {"PNG": "PNG", "JPEG": "JPEG", "OpenEXR": "OPEN_EXR", "TIFF": "TIFF"}
    RENDER_ENGINES = {"Cycles": "CYCLES", "Eevee": "BLENDER_EEVEE_NEXT", "Workbench": "BLENDER_WORKBENCH"}
    COMPUTE_DEVICES = {"Auto": "AUTO", "OptiX": "OPTIX", "CUDA": "CUDA", "HIP": "HIP", "CPU": "CPU"}
    DENOISERS = {"None": "NONE", "OptiX": "OPTIX", "OpenImageDenoise": "OPENIMAGEDENOISE"}
    
    def __init__(self):
        super().__init__()
        self.temp_script_path: Optional[str] = None
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        """Find all installed Blender versions"""
        self.installed_versions = {}
        
        for base_path in self.SEARCH_PATHS:
            exe_path = os.path.join(base_path, "blender.exe")
            if os.path.exists(exe_path):
                version = self._get_version_from_exe(exe_path)
                if version:
                    self.installed_versions[version] = exe_path
    
    def _get_version_from_exe(self, exe_path: str) -> Optional[str]:
        """Get version string from Blender executable"""
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                [exe_path, "--version"],
                capture_output=True, timeout=10,
                startupinfo=startupinfo
            )
            
            # Decode with error handling
            try:
                stdout = result.stdout.decode('utf-8', errors='replace')
            except:
                stdout = result.stdout.decode('latin-1', errors='replace')
            
            for line in stdout.split('\n'):
                line = line.strip()
                if line.startswith('Blender '):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
        except:
            pass
        return None
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """Add a custom Blender path"""
        if os.path.exists(path):
            version = self._get_version_from_exe(path)
            if version:
                self.installed_versions[version] = path
                return version
        return None
    
    def get_blend_file_version(self, blend_path: str) -> Optional[str]:
        """Read Blender version from .blend file header"""
        try:
            with open(blend_path, 'rb') as f:
                header = f.read(12)
                
                if header[:2] == b'\x1f\x8b':
                    with gzip.open(blend_path, 'rb') as gz:
                        header = gz.read(12)
                
                if header[:7] != b'BLENDER':
                    return None
                
                version_bytes = header[9:12]
                try:
                    version_str = version_bytes.decode('ascii')
                    major = int(version_str[0])
                    minor = int(version_str[1:3])
                    return f"{major}.{minor}.0"
                except:
                    return None
        except:
            return None
    
    def get_best_blender_for_file(self, blend_path: str) -> Optional[str]:
        """Get the best installed Blender version for a .blend file"""
        file_version = self.get_blend_file_version(blend_path)
        if not file_version:
            if self.installed_versions:
                versions = sorted(self.installed_versions.keys(), reverse=True)
                return self.installed_versions[versions[0]]
            return None
        
        file_parts = [int(x) for x in file_version.split('.')]
        file_major, file_minor = file_parts[0], file_parts[1]
        
        best_version = None
        best_path = None
        
        for version, path in self.installed_versions.items():
            parts = [int(x) for x in version.split('.')]
            major, minor = parts[0], parts[1]
            
            if major == file_major and minor == file_minor:
                return path
            
            if major >= file_major:
                if best_version is None:
                    best_version = version
                    best_path = path
                else:
                    best_parts = [int(x) for x in best_version.split('.')]
                    if abs(major - file_major) < abs(best_parts[0] - file_major):
                        best_version = version
                        best_path = path
                    elif major == best_parts[0] and abs(minor - file_minor) < abs(best_parts[1] - file_minor):
                        best_version = version
                        best_path = path
        
        return best_path
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """Extract scene info from blend file"""
        default_info = {
            "cameras": ["Scene Default"],
            "active_camera": "Scene Default",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "resolution_percentage": 100,
            "engine": "Cycles",
            "samples": 128,
            "output_format": "PNG",
            "frame_start": 1,
            "frame_end": 250,
            "output_path": "",
            "file_version": "",
        }
        
        file_version = self.get_blend_file_version(file_path)
        if file_version:
            default_info["file_version"] = file_version
        
        blender_exe = self.get_best_blender_for_file(file_path)
        if not blender_exe or not os.path.exists(file_path):
            return default_info
        
        script = '''import bpy
import os

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
print(f"RES_PCT:{render.resolution_percentage}")

engine_map = {"CYCLES": "Cycles", "BLENDER_EEVEE_NEXT": "Eevee", "BLENDER_EEVEE": "Eevee", "BLENDER_WORKBENCH": "Workbench"}
engine_name = engine_map.get(render.engine, "Cycles")
print(f"ENGINE:{engine_name}")

if render.engine == "CYCLES":
    print(f"SAMPLES:{scene.cycles.samples}")
else:
    print("SAMPLES:128")

print(f"FORMAT:{render.image_settings.file_format}")
print(f"FRAME_START:{scene.frame_start}")
print(f"FRAME_END:{scene.frame_end}")
print(f"OUTPUT_PATH:{render.filepath}")
print("INFO_END")
'''
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                temp_path = f.name
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                [blender_exe, "-b", file_path, "--python", temp_path],
                capture_output=True, timeout=60, startupinfo=startupinfo
            )
            os.unlink(temp_path)
            
            # Decode output with error handling for Windows encoding issues
            try:
                stdout = result.stdout.decode('utf-8', errors='replace')
            except:
                stdout = result.stdout.decode('latin-1', errors='replace')
            
            info = default_info.copy()
            in_info = False
            in_cameras = False
            cameras = []
            
            for line in stdout.split('\n'):
                line = line.strip()
                if 'INFO_START' in line:
                    in_info = True
                elif 'INFO_END' in line:
                    in_info = False
                elif in_info:
                    if 'CAMERAS_START' in line:
                        in_cameras = True
                    elif 'CAMERAS_END' in line:
                        in_cameras = False
                    elif in_cameras and line.startswith('CAM:'):
                        cameras.append(line[4:])
                    elif line.startswith('ACTIVE_CAMERA:'):
                        info["active_camera"] = line.split(':', 1)[1]
                    elif line.startswith('RES_X:'):
                        info["resolution_x"] = int(line.split(':')[1])
                    elif line.startswith('RES_Y:'):
                        info["resolution_y"] = int(line.split(':')[1])
                    elif line.startswith('RES_PCT:'):
                        info["resolution_percentage"] = int(line.split(':')[1])
                    elif line.startswith('ENGINE:'):
                        info["engine"] = line.split(':')[1]
                    elif line.startswith('SAMPLES:'):
                        info["samples"] = int(line.split(':')[1])
                    elif line.startswith('FORMAT:'):
                        fmt = line.split(':')[1]
                        fmt_map = {"PNG": "PNG", "JPEG": "JPEG", "OPEN_EXR": "OpenEXR", "TIFF": "TIFF"}
                        info["output_format"] = fmt_map.get(fmt, "PNG")
                    elif line.startswith('FRAME_START:'):
                        info["frame_start"] = int(line.split(':')[1])
                    elif line.startswith('FRAME_END:'):
                        info["frame_end"] = int(line.split(':')[1])
                    elif line.startswith('OUTPUT_PATH:'):
                        info["output_path"] = line.split(':', 1)[1] if ':' in line else ""
            
            if cameras:
                info["cameras"] = ["Scene Default"] + cameras
            
            return info
        except Exception as e:
            print(f"Error getting scene info: {e}")
            return default_info
    
    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "render_engine": "Cycles",
            "samples": 128,
            "use_gpu": True,
            "compute_device": "Auto",
            "denoiser": "None",
            "res_percentage": 100,
            "use_scene_settings": True,
            "use_factory_startup": False,
            "blender_version": "auto",
            "file_blender_version": "",
        }
    
    def generate_render_script(self, job: RenderJob, blender_version: str = None) -> str:
        """Generate Python script for Blender render setup"""
        fmt = self.OUTPUT_FORMATS.get(job.output_format, "PNG")
        script = ["import bpy", "import sys", ""]
        
        script.append(f"bpy.context.scene.render.image_settings.file_format = '{fmt}'")
        script.append("")
        
        use_scene_settings = job.get_setting("use_scene_settings", True)
        
        if use_scene_settings:
            script.append("# Using scene's existing render settings")
            if job.camera and job.camera != "Scene Default":
                script.extend([
                    "", "try:",
                    f"    bpy.context.scene.camera = bpy.data.objects['{job.camera}']",
                    "except Exception as e:",
                    f"    print(f'Warning: Could not set camera: {{e}}')",
                ])
            return "\n".join(script)
        
        # Full configuration
        render_engine = job.get_setting("render_engine", "Cycles")
        engines = {"Cycles": "CYCLES", "Eevee": "BLENDER_EEVEE_NEXT", "Workbench": "BLENDER_WORKBENCH"}
        engine = engines.get(render_engine, "CYCLES")
        
        use_gpu = job.get_setting("use_gpu", True)
        compute_device = job.get_setting("compute_device", "Auto")
        compute_type = self.COMPUTE_DEVICES.get(compute_device, "AUTO")
        denoiser = job.get_setting("denoiser", "None")
        denoiser_val = self.DENOISERS.get(denoiser, "NONE")
        samples = job.get_setting("samples", 128)
        res_percentage = job.get_setting("res_percentage", 100)
        
        if job.camera and job.camera != "Scene Default":
            script.extend([
                "try:",
                f"    bpy.context.scene.camera = bpy.data.objects['{job.camera}']",
                "except Exception as e:",
                f"    print(f'Warning: Could not set camera: {{e}}')",
                ""
            ])
        
        script.append(f"bpy.context.scene.render.resolution_x = {job.res_width}")
        script.append(f"bpy.context.scene.render.resolution_y = {job.res_height}")
        script.append(f"bpy.context.scene.render.resolution_percentage = {res_percentage}")
        script.append("")
        script.append(f"bpy.context.scene.render.engine = '{engine}'")
        script.append("")
        
        if use_gpu and render_engine == "Cycles" and compute_type != "CPU":
            script.append("def setup_gpu():")
            script.append("    try:")
            script.append("        prefs = bpy.context.preferences")
            script.append("        cycles_prefs = prefs.addons['cycles'].preferences")
            
            if compute_type == "AUTO":
                script.extend([
                    "        for ctype in ['OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL']:",
                    "            try:",
                    "                cycles_prefs.compute_device_type = ctype",
                    "                cycles_prefs.get_devices()",
                    "                gpu_found = False",
                    "                for device in cycles_prefs.devices:",
                    "                    if device.type == 'CPU':",
                    "                        device.use = False",
                    "                    else:",
                    "                        device.use = True",
                    "                        gpu_found = True",
                    "                if gpu_found:",
                    "                    return True",
                    "            except: continue",
                    "        return False",
                ])
            else:
                script.extend([
                    f"        cycles_prefs.compute_device_type = '{compute_type}'",
                    "        cycles_prefs.get_devices()",
                    "        for device in cycles_prefs.devices:",
                    "            device.use = device.type != 'CPU'",
                    "        return True",
                ])
            
            script.extend([
                "    except Exception as e:",
                "        print(f'GPU setup failed: {e}')",
                "        return False",
                "",
                "if setup_gpu():",
                "    bpy.context.scene.cycles.device = 'GPU'",
                "else:",
                "    bpy.context.scene.cycles.device = 'CPU'",
                ""
            ])
        
        if render_engine == "Cycles":
            script.append("try:")
            script.append(f"    bpy.context.scene.cycles.samples = {samples}")
            if denoiser_val != "NONE":
                script.append("    bpy.context.scene.cycles.use_denoising = True")
                script.append(f"    bpy.context.scene.cycles.denoiser = '{denoiser_val}'")
            script.append("except: pass")
            script.append("")
        
        return "\n".join(script)
    
    def start_render(self, job: RenderJob, start_frame: int,
                    on_progress: Callable, on_complete: Callable,
                    on_error: Callable, on_log: Callable = None):
        """Start Blender render"""
        blender_version = job.get_setting("blender_version", "auto")
        
        if blender_version == "auto":
            blender_exe = self.get_best_blender_for_file(job.file_path)
        else:
            blender_exe = self.installed_versions.get(blender_version)
        
        if not blender_exe:
            if self.installed_versions:
                blender_exe = list(self.installed_versions.values())[0]
            else:
                on_error("No Blender installation found")
                return
        
        render_version = None
        for v, p in self.installed_versions.items():
            if p == blender_exe:
                render_version = v
                break
        
        self.is_cancelling = False
        
        if not os.path.exists(job.output_folder):
            os.makedirs(job.output_folder)
        
        script = self.generate_render_script(job, render_version)
        script_dir = os.path.dirname(job.file_path) or os.getcwd()
        self.temp_script_path = os.path.join(script_dir, f"_render_{job.id}.py")
        
        try:
            with open(self.temp_script_path, 'w') as f:
                f.write(script)
        except Exception as e:
            on_error(f"Failed to write script: {e}")
            return
        
        output_path = os.path.join(job.output_folder, job.output_name)
        fmt = self.OUTPUT_FORMATS.get(job.output_format, "PNG")
        
        cmd = [blender_exe, "-b"]
        
        if job.get_setting("use_factory_startup", False):
            cmd.append("--factory-startup")
        
        cmd.extend([job.file_path, "--python", self.temp_script_path,
                   "-o", output_path, "-F", fmt, "-x", "1"])
        
        if job.is_animation:
            cmd.extend(["-s", str(start_frame), "-e", str(job.frame_end), "-a"])
        else:
            cmd.extend(["-f", str(job.frame_start)])
        
        if on_log:
            on_log(f"Using Blender {render_version or 'unknown'}: {blender_exe}")
            on_log(f"Command: {' '.join(cmd)}")
        
        def render_thread():
            try:
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                self.current_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    bufsize=1, startupinfo=startupinfo
                )
                
                for line_bytes in self.current_process.stdout:
                    if self.is_cancelling:
                        break
                    
                    try: 
                        line = line_bytes.decode('utf-8', errors='replace').strip()
                    except: 
                        line = line_bytes.decode('latin-1', errors='replace').strip()
                    
                    if not line:
                        continue
                    
                    if on_log:
                        on_log(line)
                    
                    frame_match = re.search(r'Fra:(\d+)', line)
                    if frame_match:
                        on_progress(int(frame_match.group(1)), line)
                    elif "Saved:" in line:
                        on_progress(-1, line)
                    elif "Sample" in line or "Path Tracing" in line:
                        on_progress(0, line)
                
                return_code = self.current_process.wait()
                self._cleanup()
                
                if self.is_cancelling:
                    pass
                elif return_code == 0:
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
            try:
                self.current_process.terminate()
            except:
                pass
            self._cleanup()
    
    def _cleanup(self):
        if self.temp_script_path and os.path.exists(self.temp_script_path):
            try: os.unlink(self.temp_script_path)
            except: pass
        self.temp_script_path = None
        self.current_process = None
    
    def build_settings_ui(self, parent: tk.Frame, job_vars: Dict[str, tk.Variable]) -> tk.Frame:
        """Build Blender-specific settings UI"""
        frame = tk.Frame(parent, bg=Theme.BG_CARD)
        
        # Render Engine
        row = tk.Frame(frame, bg=Theme.BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="Render Engine", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        ttk.Combobox(row, textvariable=job_vars.get("render_engine"), 
                    values=list(self.RENDER_ENGINES.keys()), state="readonly").pack(fill=tk.X)
        
        # Samples
        row = tk.Frame(frame, bg=Theme.BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="Samples", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        tk.Entry(row, textvariable=job_vars.get("samples"), font=("Segoe UI", 9), 
                bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(fill=tk.X, ipady=6)
        
        # GPU
        gpu_frame = tk.Frame(frame, bg=Theme.BG_CARD)
        gpu_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Checkbutton(gpu_frame, text="Enable GPU Rendering", variable=job_vars.get("use_gpu"),
                      font=("Segoe UI", 9), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD,
                      selectcolor=Theme.BG_INPUT).pack(anchor="w")
        
        device_row = tk.Frame(gpu_frame, bg=Theme.BG_CARD)
        device_row.pack(fill=tk.X, pady=(4, 0))
        tk.Label(device_row, text="Device:", font=("Segoe UI", 9), 
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        ttk.Combobox(device_row, textvariable=job_vars.get("compute_device"), 
                    values=list(self.COMPUTE_DEVICES.keys()), state="readonly", width=12).pack(side=tk.LEFT, padx=(8, 0))
        
        # Denoiser
        row = tk.Frame(frame, bg=Theme.BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="Denoiser", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        ttk.Combobox(row, textvariable=job_vars.get("denoiser"), 
                    values=list(self.DENOISERS.keys()), state="readonly").pack(fill=tk.X)
        
        # Use Scene Settings
        tk.Checkbutton(frame, text="Use Scene Settings (ignore overrides above)", 
                      variable=job_vars.get("use_scene_settings"),
                      font=("Segoe UI", 9), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD,
                      selectcolor=Theme.BG_INPUT).pack(anchor="w", pady=(0, 8))
        
        # Factory Startup
        tk.Checkbutton(frame, text="Factory Startup Mode (fixes some crashes)", 
                      variable=job_vars.get("use_factory_startup"),
                      font=("Segoe UI", 9), fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD,
                      selectcolor=Theme.BG_INPUT).pack(anchor="w")
        
        return frame
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open blend file in Blender"""
        if version == "auto" or not version:
            blender_exe = self.get_best_blender_for_file(file_path)
        else:
            blender_exe = self.installed_versions.get(version)
        
        if not blender_exe and self.installed_versions:
            blender_exe = list(self.installed_versions.values())[0]
        
        if blender_exe:
            if os.name == 'nt':
                subprocess.Popen([blender_exe, file_path], creationflags=subprocess.DETACHED_PROCESS)
            else:
                subprocess.Popen([blender_exe, file_path], start_new_session=True)


# ============================================================================
# MARMOSET TOOLBAG ENGINE
# ============================================================================
class MarmosetEngine(RenderEngine):
    """Marmoset Toolbag render engine implementation"""
    
    name = "Marmoset Toolbag"
    engine_type = "marmoset"
    file_extensions = [".tbscene"]
    icon = "◆"
    color = Theme.CYAN
    
    SEARCH_PATHS = [
        r"C:\Program Files\Marmoset\Toolbag 5\toolbag.exe",
        r"C:\Program Files\Marmoset\Toolbag 4\toolbag.exe",
        r"C:\Program Files (x86)\Marmoset\Toolbag 5\toolbag.exe",
        r"C:\Program Files (x86)\Marmoset\Toolbag 4\toolbag.exe",
    ]
    
    OUTPUT_FORMATS = {
        "PNG": "PNG", 
        "JPEG": "JPEG", 
        "TGA": "TGA",
        "PSD": "PSD",
        "EXR (16-bit)": "EXR (16-bit)",
        "EXR (32-bit)": "EXR (32-bit)",
    }
    
    RENDERERS = {"Raster": "raster", "Hybrid": "hybrid", "Ray Tracing": "raytracing"}
    SHADOW_QUALITY = ["Low", "High", "Mega"]
    DENOISE_MODES = {"Off": "off", "CPU": "cpu", "GPU": "gpu"}
    DENOISE_QUALITY = ["low", "medium", "high"]
    
    def __init__(self):
        super().__init__()
        self.temp_script_path: Optional[str] = None
        self.progress_file_path: Optional[str] = None
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        """Find installed Toolbag versions"""
        self.installed_versions = {}
        
        for exe_path in self.SEARCH_PATHS:
            if os.path.exists(exe_path):
                version = self._get_version_from_path(exe_path)
                if version:
                    self.installed_versions[version] = exe_path
    
    def _get_version_from_path(self, exe_path: str) -> Optional[str]:
        """Extract version from path"""
        if "Toolbag 5" in exe_path:
            return "5.0"
        elif "Toolbag 4" in exe_path:
            return "4.0"
        return None
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """Add a custom Toolbag path"""
        if os.path.exists(path) and path.endswith('.exe'):
            # Try to determine version
            if "5" in path:
                version = "5.0"
            elif "4" in path:
                version = "4.0"
            else:
                version = "custom"
            self.installed_versions[version] = path
            return version
        return None
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """Extract scene info from .tbscene file using Toolbag Python API"""
        default_info = {
            "cameras": ["Main Camera"],
            "active_camera": "Main Camera",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "renderer": "Ray Tracing",
            "samples": 256,
            "output_format": "PNG",
            "frame_start": 1,
            "frame_end": 1,
            "has_animation": False,
            "has_turntable": False,
        }
        
        if not self.installed_versions or not os.path.exists(file_path):
            return default_info
        
        toolbag_exe = list(self.installed_versions.values())[0]
        
        # Create probe script
        probe_script = f'''import mset
import json
import sys

try:
    mset.loadScene(r"{file_path}")
    
    result = {{
        'cameras': [],
        'active_camera': 'Main Camera',
        'resolution_x': 1920,
        'resolution_y': 1080,
        'renderer': 'Ray Tracing',
        'samples': 256,
        'frame_start': 1,
        'frame_end': 1,
        'has_animation': False,
        'has_turntable': False,
    }}
    
    # Get cameras
    for obj in mset.getAllObjects():
        if hasattr(obj, 'fov'):  # Camera objects have fov
            result['cameras'].append(obj.name)
    
    # Get current camera
    cam = mset.getCamera()
    if cam:
        result['active_camera'] = cam.name
    
    # Get render settings
    render_obj = mset.findObject('Render')
    if render_obj:
        if hasattr(render_obj, 'images'):
            result['resolution_x'] = render_obj.images.width
            result['resolution_y'] = render_obj.images.height
            result['samples'] = render_obj.images.samples
        if hasattr(render_obj, 'options'):
            renderer_map = {{'raster': 'Raster', 'hybrid': 'Hybrid', 'raytracing': 'Ray Tracing'}}
            result['renderer'] = renderer_map.get(render_obj.options.renderer, 'Ray Tracing')
    
    # Get timeline info
    timeline = mset.getTimeline()
    if timeline:
        result['frame_start'] = 1
        result['frame_end'] = timeline.totalFrames
        result['has_animation'] = timeline.totalFrames > 1
    
    # Check for turntable
    for obj in mset.getAllObjects():
        if 'turntable' in obj.name.lower() or (hasattr(obj, 'spinRate') and obj.spinRate != 0):
            result['has_turntable'] = True
            break
    
    print("SCENE_INFO_START")
    print(json.dumps(result))
    print("SCENE_INFO_END")
    
except Exception as e:
    print(f"ERROR: {{e}}")

mset.quit()
'''
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(probe_script)
                script_path = f.name
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                [toolbag_exe, script_path],
                capture_output=True, timeout=60, startupinfo=startupinfo
            )
            
            os.unlink(script_path)
            
            # Decode with error handling
            try:
                stdout = result.stdout.decode('utf-8', errors='replace')
            except:
                stdout = result.stdout.decode('latin-1', errors='replace')
            
            # Parse output
            for line in stdout.split('\n'):
                if line.strip().startswith('{'):
                    try:
                        info = json.loads(line.strip())
                        if not info.get('cameras'):
                            info['cameras'] = ['Main Camera']
                        return info
                    except:
                        pass
            
            return default_info
            
        except Exception as e:
            print(f"Error getting Toolbag scene info: {e}")
            return default_info
    
    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "renderer": "Ray Tracing",
            "samples": 256,
            "shadow_quality": "High",
            "ray_trace_bounces": 4,
            "denoise_mode": "GPU",
            "denoise_quality": "medium",
            "denoise_strength": 0.5,
            "transparency": False,
            "render_type": "image",  # "image", "video", "turntable"
            "turntable_frames": 60,
            "turntable_fps": 30,
            "video_format": "MP4",
        }
    
    def generate_render_script(self, job: RenderJob) -> str:
        """Generate Python script for Toolbag rendering"""
        renderer = job.get_setting("renderer", "Ray Tracing")
        renderer_val = self.RENDERERS.get(renderer, "raytracing")
        samples = job.get_setting("samples", 256)
        shadow_quality = job.get_setting("shadow_quality", "High")
        bounces = job.get_setting("ray_trace_bounces", 4)
        denoise_mode = job.get_setting("denoise_mode", "GPU")
        denoise_mode_val = self.DENOISE_MODES.get(denoise_mode, "gpu")
        denoise_quality = job.get_setting("denoise_quality", "medium")
        denoise_strength = job.get_setting("denoise_strength", 0.5)
        transparency = job.get_setting("transparency", False)
        render_type = job.get_setting("render_type", "image")
        
        output_path = os.path.join(job.output_folder, job.output_name)
        fmt = job.output_format
        
        script = f'''import mset
import os

# Load scene
mset.loadScene(r"{job.file_path}")

# Get render object
render_obj = mset.findObject('Render')
if not render_obj:
    mset.err("No Render object found")
    mset.quit()

# Configure render settings
render_obj.options.renderer = "{renderer_val}"
render_obj.options.shadowQuality = "{shadow_quality}"

# Ray trace settings
if "{renderer_val}" in ["raytracing", "hybrid"]:
    render_obj.options.rayTraceBounces = {bounces}
    render_obj.options.rayTraceDenoiseMode = "{denoise_mode_val}"
    render_obj.options.rayTraceDenoiseQuality = "{denoise_quality}"
    render_obj.options.rayTraceDenoiseStrength = {denoise_strength}

# Set camera
'''
        if job.camera and job.camera != "Main Camera" and job.camera != "Scene Default":
            script += f'''
cam = mset.findObject("{job.camera}")
if cam:
    mset.setCamera(cam)
'''
        
        script += f'''
# Configure output
render_obj.images.width = {job.res_width}
render_obj.images.height = {job.res_height}
render_obj.images.samples = {samples}
render_obj.images.transparency = {str(transparency)}
render_obj.images.format = "{fmt}"
render_obj.images.outputPath = r"{output_path}"
render_obj.images.overwrite = True

'''
        
        if render_type == "image":
            script += '''
# Render single image
print("RENDER_START")
mset.renderImages()
print("RENDER_COMPLETE")
'''
        elif render_type == "video" or render_type == "turntable":
            video_format = job.get_setting("video_format", "MP4")
            if render_type == "turntable":
                turntable_frames = job.get_setting("turntable_frames", 60)
                script += f'''
# Setup turntable
timeline = mset.getTimeline()
timeline.totalFrames = {turntable_frames}
'''
            script += f'''
# Configure video output
render_obj.videos.width = {job.res_width}
render_obj.videos.height = {job.res_height}
render_obj.videos.samples = {samples}
render_obj.videos.transparency = {str(transparency)}
render_obj.videos.format = "{video_format}"
render_obj.videos.outputPath = r"{output_path}"
render_obj.videos.overwrite = True

# Render video
print("RENDER_START")
mset.renderVideos()
print("RENDER_COMPLETE")
'''
        
        script += '''
mset.quit()
'''
        return script
    
    def start_render(self, job: RenderJob, start_frame: int,
                    on_progress: Callable, on_complete: Callable,
                    on_error: Callable, on_log: Callable = None):
        """Start Toolbag render"""
        if not self.installed_versions:
            on_error("Marmoset Toolbag not found")
            return
        
        toolbag_exe = list(self.installed_versions.values())[0]
        self.is_cancelling = False
        
        if not os.path.exists(job.output_folder):
            os.makedirs(job.output_folder)
        
        script = self.generate_render_script(job)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            self.temp_script_path = f.name
        
        if on_log:
            on_log(f"Using Toolbag: {toolbag_exe}")
            on_log(f"Running render script...")
        
        def render_thread():
            try:
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                self.current_process = subprocess.Popen(
                    [toolbag_exe, self.temp_script_path],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    bufsize=1, startupinfo=startupinfo
                )
                
                render_started = False
                
                for line_bytes in self.current_process.stdout:
                    if self.is_cancelling:
                        break
                    
                    try:
                        line = line_bytes.decode('utf-8', errors='replace').strip()
                    except:
                        line = line_bytes.decode('latin-1', errors='replace').strip()
                    
                    if not line:
                        continue
                    
                    if on_log:
                        on_log(line)
                    
                    if "RENDER_START" in line:
                        render_started = True
                        on_progress(10, "Rendering...")
                    elif "RENDER_COMPLETE" in line:
                        on_progress(99, "Finalizing...")
                    elif render_started:
                        # Try to parse progress from Toolbag output
                        if "sample" in line.lower() or "frame" in line.lower():
                            on_progress(50, line)
                
                return_code = self.current_process.wait()
                self._cleanup()
                
                if self.is_cancelling:
                    pass
                elif return_code == 0:
                    on_complete()
                else:
                    on_error(f"Toolbag exited with code {return_code}")
            except Exception as e:
                self._cleanup()
                if not self.is_cancelling:
                    on_error(str(e))
        
        threading.Thread(target=render_thread, daemon=True).start()
    
    def cancel_render(self):
        self.is_cancelling = True
        if self.current_process:
            try:
                self.current_process.terminate()
            except:
                pass
            self._cleanup()
    
    def _cleanup(self):
        if self.temp_script_path and os.path.exists(self.temp_script_path):
            try: os.unlink(self.temp_script_path)
            except: pass
        self.temp_script_path = None
        self.current_process = None
    
    def build_settings_ui(self, parent: tk.Frame, job_vars: Dict[str, tk.Variable]) -> tk.Frame:
        """Build Marmoset-specific settings UI"""
        frame = tk.Frame(parent, bg=Theme.BG_CARD)
        
        # Render Type
        row = tk.Frame(frame, bg=Theme.BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="Render Type", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        ttk.Combobox(row, textvariable=job_vars.get("render_type"), 
                    values=["image", "video", "turntable"], state="readonly").pack(fill=tk.X)
        
        # Renderer
        row = tk.Frame(frame, bg=Theme.BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="Renderer", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        ttk.Combobox(row, textvariable=job_vars.get("renderer"), 
                    values=list(self.RENDERERS.keys()), state="readonly").pack(fill=tk.X)
        
        # Samples
        row = tk.Frame(frame, bg=Theme.BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="Samples", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        tk.Entry(row, textvariable=job_vars.get("samples"), font=("Segoe UI", 9), 
                bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(fill=tk.X, ipady=6)
        
        # Shadow Quality
        row = tk.Frame(frame, bg=Theme.BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="Shadow Quality", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        ttk.Combobox(row, textvariable=job_vars.get("shadow_quality"), 
                    values=self.SHADOW_QUALITY, state="readonly").pack(fill=tk.X)
        
        # Ray Trace Bounces
        row = tk.Frame(frame, bg=Theme.BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="Ray Trace Bounces", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        tk.Entry(row, textvariable=job_vars.get("ray_trace_bounces"), font=("Segoe UI", 9), 
                bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(fill=tk.X, ipady=6)
        
        # Denoising section
        tk.Label(frame, text="Denoising", font=("Segoe UI", 9, "bold"), 
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(8, 4))
        
        denoise_row = tk.Frame(frame, bg=Theme.BG_CARD)
        denoise_row.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(denoise_row, text="Mode:", font=("Segoe UI", 9), 
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        ttk.Combobox(denoise_row, textvariable=job_vars.get("denoise_mode"), 
                    values=list(self.DENOISE_MODES.keys()), state="readonly", width=8).pack(side=tk.LEFT, padx=(4, 12))
        
        tk.Label(denoise_row, text="Quality:", font=("Segoe UI", 9), 
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        ttk.Combobox(denoise_row, textvariable=job_vars.get("denoise_quality"), 
                    values=self.DENOISE_QUALITY, state="readonly", width=10).pack(side=tk.LEFT, padx=(4, 0))
        
        # Transparency
        tk.Checkbutton(frame, text="Transparent Background", variable=job_vars.get("transparency"),
                      font=("Segoe UI", 9), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD,
                      selectcolor=Theme.BG_INPUT).pack(anchor="w", pady=(0, 8))
        
        # Turntable settings (conditional)
        turntable_frame = tk.Frame(frame, bg=Theme.BG_CARD)
        turntable_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(turntable_frame, text="Turntable Frames:", font=("Segoe UI", 9), 
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        tk.Entry(turntable_frame, textvariable=job_vars.get("turntable_frames"), 
                font=("Segoe UI", 9), bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, 
                bd=0, width=6).pack(side=tk.LEFT, padx=(4, 0), ipady=4)
        
        return frame
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open tbscene file in Toolbag"""
        if self.installed_versions:
            toolbag_exe = list(self.installed_versions.values())[0]
            if os.name == 'nt':
                subprocess.Popen([toolbag_exe, file_path], creationflags=subprocess.DETACHED_PROCESS)
            else:
                subprocess.Popen([toolbag_exe, file_path], start_new_session=True)


# ============================================================================
# ENGINE REGISTRY
# ============================================================================
class EngineRegistry:
    """Registry for all available render engines"""
    
    def __init__(self):
        self.engines: Dict[str, RenderEngine] = {}
        self._register_default_engines()
    
    def _register_default_engines(self):
        """Register built-in engines"""
        self.register(BlenderEngine())
        self.register(MarmosetEngine())
    
    def register(self, engine: RenderEngine):
        """Register a render engine"""
        self.engines[engine.engine_type] = engine
    
    def get(self, engine_type: str) -> Optional[RenderEngine]:
        """Get engine by type"""
        return self.engines.get(engine_type)
    
    def get_all(self) -> List[RenderEngine]:
        """Get all registered engines"""
        return list(self.engines.values())
    
    def get_available(self) -> List[RenderEngine]:
        """Get engines that have at least one installation"""
        return [e for e in self.engines.values() if e.is_available]
    
    def detect_engine_for_file(self, file_path: str) -> Optional[RenderEngine]:
        """Detect which engine should handle a file based on extension"""
        ext = os.path.splitext(file_path)[1].lower()
        for engine in self.engines.values():
            if ext in engine.file_extensions:
                return engine
        return None
    
    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions"""
        extensions = []
        for engine in self.engines.values():
            extensions.extend(engine.file_extensions)
        return extensions


# ============================================================================
# UI COMPONENTS
# ============================================================================
class StatsCard(tk.Frame):
    def __init__(self, parent, title: str, icon: str, color: str, bg_tint: str):
        super().__init__(parent, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER, highlightthickness=1)
        
        inner = tk.Frame(self, bg=Theme.BG_CARD, padx=16, pady=12)
        inner.pack(fill=tk.BOTH, expand=True)
        
        icon_frame = tk.Frame(inner, bg=bg_tint, width=40, height=40)
        icon_frame.pack(side=tk.LEFT, padx=(0, 12))
        icon_frame.pack_propagate(False)
        tk.Label(icon_frame, text=icon, font=("Segoe UI", 14), fg=color, bg=bg_tint).place(relx=0.5, rely=0.5, anchor="center")
        
        text = tk.Frame(inner, bg=Theme.BG_CARD)
        text.pack(side=tk.LEFT)
        tk.Label(text, text=title, font=("Segoe UI", 10), fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w")
        self.value_label = tk.Label(text, text="0", font=("Segoe UI", 20, "bold"), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD)
        self.value_label.pack(anchor="w")
    
    def set_value(self, value: int):
        self.value_label.config(text=str(value))


class JobCard(tk.Frame):
    STATUS_STYLES = {
        "rendering": (Theme.BLUE, "#1e3a8a"),
        "queued": (Theme.YELLOW, "#422006"),
        "completed": (Theme.GREEN, "#052e16"),
        "failed": (Theme.RED, "#450a0a"),
        "paused": (Theme.ORANGE, "#431407"),
    }
    
    def __init__(self, parent, job: RenderJob, engine_registry: EngineRegistry, on_action: Callable):
        super().__init__(parent, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER, highlightthickness=1)
        self.job = job
        self.engine_registry = engine_registry
        self.on_action = on_action
        self.expanded = False
        self.build_ui()
    
    def build_ui(self):
        self.content = tk.Frame(self, bg=Theme.BG_CARD, padx=16, pady=12)
        self.content.pack(fill=tk.X)
        
        top = tk.Frame(self.content, bg=Theme.BG_CARD)
        top.pack(fill=tk.X)
        
        info = tk.Frame(top, bg=Theme.BG_CARD)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        name_row = tk.Frame(info, bg=Theme.BG_CARD)
        name_row.pack(fill=tk.X)
        
        # Engine badge
        engine = self.engine_registry.get(self.job.engine_type)
        engine_color = ENGINE_COLORS.get(self.job.engine_type, Theme.TEXT_MUTED)
        
        engine_badge = tk.Label(name_row, text=f" {engine.icon if engine else '?'} ", 
                               font=("Segoe UI", 10), fg="white", bg=engine_color)
        engine_badge.pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Label(name_row, text=self.job.name or "Untitled", font=("Segoe UI", 12, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        
        fg, bg = self.STATUS_STYLES.get(self.job.status, (Theme.TEXT_MUTED, Theme.BG_ELEVATED))
        self.status_frame = tk.Frame(name_row, bg=bg, padx=8, pady=2)
        self.status_frame.pack(side=tk.LEFT, padx=(10, 0))
        self.status_label = tk.Label(self.status_frame, text=self.job.status.upper(), 
                                     font=("Segoe UI", 9, "bold"), fg=fg, bg=bg)
        self.status_label.pack()
        
        tk.Label(info, text=self.job.file_name, font=("Segoe UI", 10),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(2, 0))
        
        self.actions = tk.Frame(top, bg=Theme.BG_CARD)
        self.actions.pack(side=tk.RIGHT)
        self._build_buttons()
        
        self.progress_frame = tk.Frame(self.content, bg=Theme.BG_CARD)
        if self.job.status in ["rendering", "paused", "completed", "failed"] or self.job.progress > 0:
            self.progress_frame.pack(fill=tk.X, pady=(10, 0))
            self._build_progress()
        
        self.info_frame = tk.Frame(self.content, bg=Theme.BG_CARD)
        self.info_frame.pack(fill=tk.X, pady=(8, 0))
        self._build_info()
        
        self.details_frame = tk.Frame(self.content, bg=Theme.BG_CARD)
    
    def _build_buttons(self):
        for w in self.actions.winfo_children():
            w.destroy()
        
        btn = {"font": ("Segoe UI", 11), "width": 3, "bd": 0, "cursor": "hand2",
               "bg": Theme.BG_CARD, "activebackground": Theme.BG_ELEVATED}
        
        if self.job.status == "rendering":
            tk.Button(self.actions, text="⏸", fg=Theme.YELLOW, **btn,
                     command=lambda: self.on_action("pause", self.job)).pack(side=tk.LEFT)
        elif self.job.status in ["queued", "paused"]:
            tk.Button(self.actions, text="▶", fg=Theme.GREEN, **btn,
                     command=lambda: self.on_action("start", self.job)).pack(side=tk.LEFT)
        elif self.job.status == "failed":
            tk.Button(self.actions, text="↻", fg=Theme.YELLOW, **btn,
                     command=lambda: self.on_action("retry", self.job)).pack(side=tk.LEFT)
        
        self.expand_btn = tk.Button(self.actions, text="▼" if not self.expanded else "▲", 
                                    fg=Theme.TEXT_SECONDARY, **btn, command=self.toggle_expand)
        self.expand_btn.pack(side=tk.LEFT)
        
        tk.Button(self.actions, text="🗑", fg=Theme.RED, **btn,
                 command=lambda: self.on_action("delete", self.job)).pack(side=tk.LEFT)
    
    def _build_progress(self):
        for w in self.progress_frame.winfo_children():
            w.destroy()
        
        header = tk.Frame(self.progress_frame, bg=Theme.BG_CARD)
        header.pack(fill=tk.X)
        tk.Label(header, text="Progress", font=("Segoe UI", 9), fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        self.progress_pct = tk.Label(header, text=f"{self.job.progress}%", font=("Segoe UI", 9), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD)
        self.progress_pct.pack(side=tk.RIGHT)
        
        self.bar_bg = tk.Frame(self.progress_frame, bg=Theme.BG_ELEVATED, height=6)
        self.bar_bg.pack(fill=tk.X, pady=(4, 0))
        self.bar_bg.pack_propagate(False)
        
        color = Theme.GREEN if self.job.status == "completed" else Theme.RED if self.job.status == "failed" else Theme.ORANGE if self.job.status == "paused" else Theme.BLUE
        self.progress_bar = tk.Frame(self.bar_bg, bg=color, height=6)
        self.progress_bar.place(relx=0, rely=0, relheight=1, relwidth=max(0.01, self.job.progress/100))
    
    def _build_info(self):
        for w in self.info_frame.winfo_children():
            w.destroy()
        
        engine = self.engine_registry.get(self.job.engine_type)
        engine_name = engine.name if engine else self.job.engine_type
        
        parts = [engine_name, f"Frames: {self.job.frames_display}", self.job.resolution_display]
        if self.job.elapsed_time:
            parts.append(f"⏱ {self.job.elapsed_time}")
        
        tk.Label(self.info_frame, text="  •  ".join(parts), font=("Segoe UI", 10),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w")
    
    def update_progress(self, progress: int, elapsed: str = ""):
        self.job.progress = progress
        if elapsed:
            self.job.elapsed_time = elapsed
        
        if not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill=tk.X, pady=(10, 0))
            self._build_progress()
        
        if hasattr(self, 'progress_pct') and self.progress_pct.winfo_exists():
            self.progress_pct.config(text=f"{progress}%")
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            self.progress_bar.place(relwidth=max(0.01, progress/100))
        
        self._build_info()
    
    def update_status(self, status: str):
        self.job.status = status
        fg, bg = self.STATUS_STYLES.get(status, (Theme.TEXT_MUTED, Theme.BG_ELEVATED))
        self.status_frame.config(bg=bg)
        self.status_label.config(text=status.upper(), fg=fg, bg=bg)
        self._build_buttons()
        
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            color = Theme.GREEN if status == "completed" else Theme.RED if status == "failed" else Theme.ORANGE if status == "paused" else Theme.BLUE
            self.progress_bar.config(bg=color)
        
        if status == "rendering" and not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill=tk.X, pady=(10, 0))
            self._build_progress()
        
        self._build_info()
    
    def toggle_expand(self):
        self.expanded = not self.expanded
        self.expand_btn.config(text="▲" if self.expanded else "▼")
        
        if self.expanded:
            self.details_frame.pack(fill=tk.X, pady=(10, 0))
            tk.Frame(self.details_frame, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(0, 10))
            
            # Output section
            output_section = tk.Frame(self.details_frame, bg=Theme.BG_CARD)
            output_section.pack(fill=tk.X, pady=(0, 10))
            
            tk.Label(output_section, text="Output Path", font=("Segoe UI", 9), 
                    fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w")
            
            output_row = tk.Frame(output_section, bg=Theme.BG_CARD)
            output_row.pack(fill=tk.X, pady=(2, 0))
            
            display_path = self.job.output_folder
            if len(display_path) > 50:
                display_path = "..." + display_path[-47:]
            
            self.output_label = tk.Label(output_row, text=display_path, font=("Segoe UI", 9), 
                                        fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD, anchor="w")
            self.output_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            tk.Button(output_row, text="📁", font=("Segoe UI", 9), bg=Theme.BG_ELEVATED, 
                     fg=Theme.TEXT_SECONDARY, bd=0, padx=6, pady=2,
                     command=self._edit_output).pack(side=tk.LEFT, padx=(6, 0))
            
            # Action buttons
            btn_row = tk.Frame(self.details_frame, bg=Theme.BG_CARD)
            btn_row.pack(fill=tk.X, pady=(0, 10))
            
            engine = self.engine_registry.get(self.job.engine_type)
            app_name = engine.name if engine else "App"
            
            tk.Button(btn_row, text=f"📂 Open in {app_name}", font=("Segoe UI", 9), 
                     bg=Theme.BG_ELEVATED, fg=Theme.TEXT_PRIMARY, bd=0, padx=12, pady=6,
                     command=self._open_in_app).pack(side=tk.LEFT, padx=(0, 8))
            
            tk.Button(btn_row, text="📁 Open Output Folder", font=("Segoe UI", 9), 
                     bg=Theme.BG_ELEVATED, fg=Theme.TEXT_PRIMARY, bd=0, padx=12, pady=6,
                     command=self._open_output_folder).pack(side=tk.LEFT)
            
            # Details grid
            grid = tk.Frame(self.details_frame, bg=Theme.BG_CARD)
            grid.pack(fill=tk.X)
            
            details = [
                ("Engine", engine.name if engine else self.job.engine_type),
                ("Camera", self.job.camera),
                ("Format", self.job.output_format),
                ("Resolution", f"{self.job.res_width}×{self.job.res_height}"),
            ]
            
            # Add engine-specific details
            if self.job.engine_type == "blender":
                details.append(("Render", self.job.get_setting("render_engine", "Cycles")))
                details.append(("Samples", str(self.job.get_setting("samples", 128))))
            elif self.job.engine_type == "marmoset":
                details.append(("Renderer", self.job.get_setting("renderer", "Ray Tracing")))
                details.append(("Samples", str(self.job.get_setting("samples", 256))))
            
            if self.job.current_frame > 0:
                details.append(("Last Frame", str(self.job.current_frame)))
            if self.job.error_message:
                details.append(("Error", self.job.error_message[:40]))
            
            for i, (label, value) in enumerate(details):
                cell = tk.Frame(grid, bg=Theme.BG_CARD)
                cell.grid(row=i//3, column=i%3, sticky="w", padx=(0, 20), pady=3)
                tk.Label(cell, text=label, font=("Segoe UI", 9), fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w")
                tk.Label(cell, text=str(value), font=("Segoe UI", 10), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        else:
            self.details_frame.pack_forget()
            for w in self.details_frame.winfo_children():
                w.destroy()
    
    def _edit_output(self):
        new_path = filedialog.askdirectory(initialdir=self.job.output_folder, title="Select Output Folder")
        if new_path:
            self.job.output_folder = new_path
            display_path = new_path if len(new_path) <= 50 else "..." + new_path[-47:]
            if hasattr(self, 'output_label'):
                self.output_label.config(text=display_path)
            self.on_action("save", self.job)
    
    def _open_in_app(self):
        self.on_action("open_app", self.job)
    
    def _open_output_folder(self):
        if os.path.exists(self.job.output_folder):
            if os.name == 'nt':
                os.startfile(self.job.output_folder)
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.job.output_folder])
            else:
                subprocess.run(['xdg-open', self.job.output_folder])


# ============================================================================
# ADD JOB MODAL
# ============================================================================
class AddJobModal(tk.Toplevel):
    def __init__(self, parent, engine_registry: EngineRegistry, settings: AppSettings, on_add: Callable):
        super().__init__(parent)
        self.engine_registry = engine_registry
        self.settings = settings
        self.on_add = on_add
        self.scene_info = None
        self.current_engine: Optional[RenderEngine] = None
        self.engine_settings_frame: Optional[tk.Frame] = None
        
        self.title("Add Render Job")
        self.configure(bg=Theme.BG_CARD)
        self.geometry("560x780")
        self.transient(parent)
        self.grab_set()
        
        # Common variables
        self.name_var = tk.StringVar()
        self.file_var = tk.StringVar()
        self.engine_type_var = tk.StringVar(value=settings.default_engine_type)
        self.output_var = tk.StringVar()
        self.output_name_var = tk.StringVar(value="render_")
        self.format_var = tk.StringVar(value=settings.default_format)
        self.camera_var = tk.StringVar(value="Scene Default")
        self.is_anim_var = tk.BooleanVar(value=False)
        self.start_var = tk.StringVar(value="1")
        self.end_var = tk.StringVar(value="250")
        self.res_width_var = tk.StringVar(value="1920")
        self.res_height_var = tk.StringVar(value="1080")
        self.paused_var = tk.BooleanVar(value=False)
        
        # Engine-specific variables (will be populated per engine)
        self.engine_vars: Dict[str, tk.Variable] = {}
        
        self.build_ui()
        self._on_engine_change()
    
    def build_ui(self):
        canvas = tk.Canvas(self, bg=Theme.BG_CARD, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview, style="Dark.Vertical.TScrollbar")
        self.form_frame = tk.Frame(canvas, bg=Theme.BG_CARD)
        
        self.form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.form_frame, anchor="nw", width=540)
        canvas.configure(yscrollcommand=scroll.set)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Header
        header = tk.Frame(self.form_frame, bg=Theme.BG_CARD)
        header.pack(fill=tk.X, padx=20, pady=16)
        tk.Label(header, text="Add Render Job", font=("Segoe UI", 14, "bold"), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        tk.Button(header, text="✕", font=("Segoe UI", 12), bg=Theme.BG_CARD, 
                 fg=Theme.TEXT_SECONDARY, bd=0, command=self.destroy).pack(side=tk.RIGHT)
        
        tk.Frame(self.form_frame, bg=Theme.BORDER, height=1).pack(fill=tk.X)
        
        form = tk.Frame(self.form_frame, bg=Theme.BG_CARD, padx=20, pady=16)
        form.pack(fill=tk.BOTH, expand=True)
        
        # Engine selector
        engine_frame = tk.Frame(form, bg=Theme.BG_CARD)
        engine_frame.pack(fill=tk.X, pady=(0, 12))
        tk.Label(engine_frame, text="Render Application", font=("Segoe UI", 10, "bold"), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 6))
        
        engines_row = tk.Frame(engine_frame, bg=Theme.BG_CARD)
        engines_row.pack(fill=tk.X)
        
        for engine in self.engine_registry.get_all():
            color = ENGINE_COLORS.get(engine.engine_type, Theme.TEXT_MUTED)
            status = "✓" if engine.is_available else "✗"
            status_color = Theme.GREEN if engine.is_available else Theme.RED
            
            btn_frame = tk.Frame(engines_row, bg=Theme.BG_ELEVATED, padx=12, pady=8)
            btn_frame.pack(side=tk.LEFT, padx=(0, 8))
            
            rb = tk.Radiobutton(btn_frame, text=f"{engine.icon} {engine.name}", 
                               variable=self.engine_type_var, value=engine.engine_type,
                               font=("Segoe UI", 10), fg=color, bg=Theme.BG_ELEVATED,
                               selectcolor=Theme.BG_INPUT, activebackground=Theme.BG_ELEVATED,
                               command=self._on_engine_change,
                               state=tk.NORMAL if engine.is_available else tk.DISABLED)
            rb.pack(side=tk.LEFT)
            
            tk.Label(btn_frame, text=status, font=("Segoe UI", 8), fg=status_color, 
                    bg=Theme.BG_ELEVATED).pack(side=tk.LEFT, padx=(4, 0))
        
        tk.Frame(form, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(0, 12))
        
        # Job name and file
        self._field(form, "Job Name", self.name_var)
        self.file_field_frame = self._file_field(form, "Scene File", self.file_var, self.browse_file)
        
        # Scene info display - initially hidden, will show after file field when file is loaded
        self.scene_display_frame = tk.Frame(form, bg=Theme.BG_ELEVATED)
        # Don't pack yet - will be packed in correct position when showing
        
        scene_header = tk.Frame(self.scene_display_frame, bg=Theme.BG_ELEVATED)
        scene_header.pack(fill=tk.X, padx=12, pady=(10, 6))
        tk.Label(scene_header, text="Scene Settings", font=("Segoe UI", 10, "bold"), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_ELEVATED).pack(side=tk.LEFT)
        self.scene_status_label = tk.Label(scene_header, text="", font=("Segoe UI", 9), 
                                          fg=Theme.GREEN, bg=Theme.BG_ELEVATED)
        self.scene_status_label.pack(side=tk.RIGHT)
        
        self.scene_info_label = tk.Label(self.scene_display_frame, text="", font=("Segoe UI", 9), 
                                        fg=Theme.TEXT_SECONDARY, bg=Theme.BG_ELEVATED, justify=tk.LEFT)
        self.scene_info_label.pack(fill=tk.X, padx=12, pady=(0, 10))
        
        # Output settings separator - store reference for positioning
        self.output_separator = tk.Frame(form, bg=Theme.BORDER, height=1)
        self.output_separator.pack(fill=tk.X, pady=(10, 10))
        tk.Label(form, text="Output Settings", font=("Segoe UI", 10, "bold"), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 8))
        
        self._file_field(form, "Output Directory", self.output_var, self.browse_output)
        
        output_row = tk.Frame(form, bg=Theme.BG_CARD)
        output_row.pack(fill=tk.X, pady=(0, 10))
        
        name_frame = tk.Frame(output_row, bg=Theme.BG_CARD)
        name_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(name_frame, text="Output Name Prefix", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        tk.Entry(name_frame, textvariable=self.output_name_var, font=("Segoe UI", 9), 
                bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(fill=tk.X, ipady=6)
        
        format_frame = tk.Frame(output_row, bg=Theme.BG_CARD)
        format_frame.pack(side=tk.LEFT)
        tk.Label(format_frame, text="Format", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        self.format_combo = ttk.Combobox(format_frame, textvariable=self.format_var, 
                                        values=["PNG", "JPEG"], state="readonly", width=12)
        self.format_combo.pack()
        
        # Resolution
        res_frame = tk.Frame(form, bg=Theme.BG_CARD)
        res_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(res_frame, text="Resolution", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        
        res_row = tk.Frame(res_frame, bg=Theme.BG_CARD)
        res_row.pack(fill=tk.X)
        tk.Entry(res_row, textvariable=self.res_width_var, width=8, font=("Segoe UI", 9), 
                bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(side=tk.LEFT, ipady=6)
        tk.Label(res_row, text="×", font=("Segoe UI", 10), fg=Theme.TEXT_SECONDARY, 
                bg=Theme.BG_CARD).pack(side=tk.LEFT, padx=6)
        tk.Entry(res_row, textvariable=self.res_height_var, width=8, font=("Segoe UI", 9), 
                bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(side=tk.LEFT, ipady=6)
        
        # Preset buttons
        for preset in ["1920×1080", "2560×1440", "3840×2160"]:
            w, h = preset.split("×")
            tk.Button(res_row, text=preset, font=("Segoe UI", 8), bg=Theme.BG_ELEVATED, 
                     fg=Theme.TEXT_SECONDARY, bd=0, padx=6, pady=2,
                     command=lambda w=w, h=h: (self.res_width_var.set(w), self.res_height_var.set(h))
                     ).pack(side=tk.LEFT, padx=(8, 0))
        
        # Camera
        camera_frame = tk.Frame(form, bg=Theme.BG_CARD)
        camera_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(camera_frame, text="Camera", font=("Segoe UI", 9), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        self.camera_combo = ttk.Combobox(camera_frame, textvariable=self.camera_var, 
                                        values=["Scene Default"], state="readonly")
        self.camera_combo.pack(fill=tk.X)
        
        # Animation
        frame_section = tk.Frame(form, bg=Theme.BG_CARD)
        frame_section.pack(fill=tk.X, pady=(0, 10))
        
        tk.Checkbutton(frame_section, text="Render as Animation", variable=self.is_anim_var, 
                      font=("Segoe UI", 9), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD, 
                      selectcolor=Theme.BG_INPUT).pack(anchor="w")
        
        frame_row = tk.Frame(frame_section, bg=Theme.BG_CARD)
        frame_row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(frame_row, text="Frames:", font=("Segoe UI", 9), 
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        tk.Entry(frame_row, textvariable=self.start_var, width=6, font=("Segoe UI", 9), 
                bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(side=tk.LEFT, padx=(8, 0), ipady=4)
        tk.Label(frame_row, text="to", font=("Segoe UI", 9), 
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(side=tk.LEFT, padx=8)
        tk.Entry(frame_row, textvariable=self.end_var, width=6, font=("Segoe UI", 9), 
                bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(side=tk.LEFT, ipady=4)
        
        # Engine-specific settings container
        tk.Frame(form, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(10, 10))
        self.engine_settings_header = tk.Label(form, text="Engine Settings", font=("Segoe UI", 10, "bold"), 
                                               fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD)
        self.engine_settings_header.pack(anchor="w", pady=(0, 8))
        
        self.engine_settings_container = tk.Frame(form, bg=Theme.BG_CARD)
        self.engine_settings_container.pack(fill=tk.X, pady=(0, 10))
        
        # Submit paused
        tk.Checkbutton(form, text="Submit as Paused", variable=self.paused_var, font=("Segoe UI", 9),
                      fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD, selectcolor=Theme.BG_INPUT).pack(anchor="w", pady=(4, 10))
        
        tk.Frame(form, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(6, 14))
        
        # Buttons
        btns = tk.Frame(form, bg=Theme.BG_CARD)
        btns.pack(fill=tk.X)
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg=Theme.BG_ELEVATED, 
                 fg=Theme.TEXT_PRIMARY, bd=0, padx=16, pady=10, command=self.destroy).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Button(btns, text="Submit Job", font=("Segoe UI", 10, "bold"), bg=Theme.BLUE, 
                 fg="white", bd=0, padx=16, pady=10, command=self.submit).pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def _field(self, parent, label, var):
        f = tk.Frame(parent, bg=Theme.BG_CARD)
        f.pack(fill=tk.X, pady=(0, 10))
        tk.Label(f, text=label, font=("Segoe UI", 10), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        tk.Entry(f, textvariable=var, font=("Segoe UI", 9), bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(fill=tk.X, ipady=6, ipadx=8)
    
    def _file_field(self, parent, label, var, cmd):
        f = tk.Frame(parent, bg=Theme.BG_CARD)
        f.pack(fill=tk.X, pady=(0, 10))
        tk.Label(f, text=label, font=("Segoe UI", 10), fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        row = tk.Frame(f, bg=Theme.BG_CARD)
        row.pack(fill=tk.X)
        tk.Entry(row, textvariable=var, font=("Segoe UI", 9), bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY, bd=0).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, ipadx=8)
        tk.Button(row, text="Browse", font=("Segoe UI", 8), bg=Theme.BG_ELEVATED, fg=Theme.TEXT_SECONDARY, bd=0, padx=10, command=cmd).pack(side=tk.LEFT, padx=(6, 0))
        return f
    
    def _on_engine_change(self):
        """Handle engine type change"""
        engine_type = self.engine_type_var.get()
        self.current_engine = self.engine_registry.get(engine_type)
        
        if not self.current_engine:
            return
        
        # Update format options
        formats = list(self.current_engine.get_output_formats().keys())
        self.format_combo['values'] = formats
        if self.format_var.get() not in formats:
            self.format_var.set(formats[0] if formats else "PNG")
        
        # Update engine settings header
        self.engine_settings_header.config(text=f"{self.current_engine.name} Settings")
        
        # Clear and rebuild engine settings UI
        for w in self.engine_settings_container.winfo_children():
            w.destroy()
        
        # Create engine-specific variables
        defaults = self.current_engine.get_default_settings()
        self.engine_vars = {}
        
        for key, value in defaults.items():
            if isinstance(value, bool):
                self.engine_vars[key] = tk.BooleanVar(value=value)
            elif isinstance(value, int):
                self.engine_vars[key] = tk.StringVar(value=str(value))
            elif isinstance(value, float):
                self.engine_vars[key] = tk.StringVar(value=str(value))
            else:
                self.engine_vars[key] = tk.StringVar(value=str(value))
        
        # Build engine-specific UI
        self.engine_settings_frame = self.current_engine.build_settings_ui(
            self.engine_settings_container, self.engine_vars
        )
        self.engine_settings_frame.pack(fill=tk.X)
        
        # Clear scene info
        self.scene_display_frame.pack_forget()
        self.scene_info = None
    
    def browse_file(self):
        # Build file type filter
        filetypes = []
        
        engine = self.current_engine
        if engine:
            ext_str = " ".join(f"*{ext}" for ext in engine.file_extensions)
            filetypes.append((f"{engine.name} Files", ext_str))
        
        # All supported
        all_ext = " ".join(f"*{ext}" for ext in self.engine_registry.get_supported_extensions())
        filetypes.insert(0, ("All Supported", all_ext))
        filetypes.append(("All Files", "*.*"))
        
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.file_var.set(path)
            
            # Auto-detect engine from file
            detected_engine = self.engine_registry.detect_engine_for_file(path)
            if detected_engine and detected_engine.engine_type != self.engine_type_var.get():
                self.engine_type_var.set(detected_engine.engine_type)
                self._on_engine_change()
            
            # Set name from filename
            if not self.name_var.get():
                self.name_var.set(os.path.splitext(os.path.basename(path))[0])
            
            # Set output directory
            if not self.output_var.get():
                self.output_var.set(os.path.dirname(path))
            
            # Load scene info
            self._load_scene_info(path)
    
    def _load_scene_info(self, path: str):
        """Load scene information asynchronously"""
        if not self.current_engine:
            return
        
        self.scene_status_label.config(text="Loading...", fg=Theme.TEXT_MUTED)
        # Pack before the output separator to maintain correct position
        self.scene_display_frame.pack(fill=tk.X, pady=(0, 10), before=self.output_separator)
        self.update()
        
        def load():
            info = self.current_engine.get_scene_info(path)
            self.after(0, lambda: self._apply_scene_info(info))
        
        threading.Thread(target=load, daemon=True).start()
    
    def _apply_scene_info(self, info: Dict[str, Any]):
        """Apply loaded scene info to UI"""
        self.scene_info = info
        self.scene_status_label.config(text="✓ Loaded", fg=Theme.GREEN)
        
        # Update cameras dropdown
        cameras = info.get("cameras", ["Scene Default"])
        self.camera_combo['values'] = cameras
        active = info.get("active_camera", cameras[0] if cameras else "Scene Default")
        self.camera_var.set(active)
        
        # Update resolution
        self.res_width_var.set(str(info.get("resolution_x", 1920)))
        self.res_height_var.set(str(info.get("resolution_y", 1080)))
        
        # Update frame range
        self.start_var.set(str(info.get("frame_start", 1)))
        self.end_var.set(str(info.get("frame_end", 250)))
        
        # Update output directory from scene's output path
        output_path = info.get("output_path", "")
        if output_path:
            # Blender uses // for relative paths - convert to absolute
            if output_path.startswith("//"):
                blend_dir = os.path.dirname(self.file_var.get())
                output_path = os.path.normpath(os.path.join(blend_dir, output_path[2:]))
            
            # Extract directory (Blender path might include filename prefix)
            if os.path.isdir(output_path):
                output_dir = output_path
            else:
                output_dir = os.path.dirname(output_path)
            
            # Only set if it's a valid directory or we can extract one
            if output_dir and (os.path.isdir(output_dir) or not self.output_var.get()):
                self.output_var.set(output_dir)
                
            # Try to extract output name prefix from the path
            basename = os.path.basename(output_path)
            if basename and not os.path.isdir(output_path):
                # Remove frame number placeholders like #### or 0001
                import re
                prefix = re.sub(r'#+$|_*\d+$', '', basename)
                if prefix:
                    self.output_name_var.set(prefix)
        
        # Check for animation
        if info.get("frame_end", 1) > info.get("frame_start", 1):
            self.is_anim_var.set(True)
        
        # Update info display
        info_text = f"Resolution: {info.get('resolution_x', 1920)}×{info.get('resolution_y', 1080)}"
        info_text += f"  |  Frames: {info.get('frame_start', 1)}-{info.get('frame_end', 250)}"
        
        if self.current_engine.engine_type == "blender":
            info_text += f"\nEngine: {info.get('engine', 'Cycles')}  |  Samples: {info.get('samples', 128)}"
        elif self.current_engine.engine_type == "marmoset":
            info_text += f"\nRenderer: {info.get('renderer', 'Ray Tracing')}"
        
        self.scene_info_label.config(text=info_text)
    
    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_var.set(path)
    
    def submit(self):
        if not self.file_var.get() or not self.output_var.get():
            messagebox.showerror("Error", "Please fill required fields")
            return
        
        if not self.current_engine:
            messagebox.showerror("Error", "No render engine selected")
            return
        
        # Collect engine settings
        engine_settings = {}
        for key, var in self.engine_vars.items():
            value = var.get()
            # Convert types
            if isinstance(var, tk.BooleanVar):
                engine_settings[key] = value
            elif value.isdigit():
                engine_settings[key] = int(value)
            elif value.replace('.', '').isdigit():
                engine_settings[key] = float(value)
            else:
                engine_settings[key] = value
        
        job = RenderJob(
            name=self.name_var.get() or "Untitled",
            engine_type=self.engine_type_var.get(),
            file_path=self.file_var.get(),
            output_folder=self.output_var.get(),
            output_name=self.output_name_var.get(),
            output_format=self.format_var.get(),
            status="paused" if self.paused_var.get() else "queued",
            camera=self.camera_var.get(),
            is_animation=self.is_anim_var.get(),
            frame_start=int(self.start_var.get() or 1),
            frame_end=int(self.end_var.get() or 250),
            original_start=int(self.start_var.get() or 1),
            res_width=int(self.res_width_var.get() or 1920),
            res_height=int(self.res_height_var.get() or 1080),
            engine_settings=engine_settings,
        )
        
        self.on_add(job)
        self.destroy()


# ============================================================================
# SETTINGS PANEL
# ============================================================================
class SettingsPanel(tk.Toplevel):
    def __init__(self, parent, settings: AppSettings, engine_registry: EngineRegistry, on_save: Callable):
        super().__init__(parent)
        self.settings = settings
        self.engine_registry = engine_registry
        self.on_save = on_save
        
        self.title("Settings")
        self.configure(bg=Theme.BG_CARD)
        self.geometry("560x650")
        self.transient(parent)
        self.grab_set()
        
        self.build_ui()
    
    def build_ui(self):
        header = tk.Frame(self, bg=Theme.BG_CARD)
        header.pack(fill=tk.X, padx=20, pady=14)
        tk.Label(header, text="Settings", font=("Segoe UI", 14, "bold"), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        tk.Button(header, text="✕", font=("Segoe UI", 12), bg=Theme.BG_CARD, 
                 fg=Theme.TEXT_SECONDARY, bd=0, command=self.destroy).pack(side=tk.RIGHT)
        
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill=tk.X)
        
        # Scrollable content
        canvas = tk.Canvas(self, bg=Theme.BG_CARD, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview, style="Dark.Vertical.TScrollbar")
        form = tk.Frame(canvas, bg=Theme.BG_CARD, padx=20, pady=14)
        
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw", width=540)
        canvas.configure(yscrollcommand=scroll.set)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Engine sections
        for engine in self.engine_registry.get_all():
            self._build_engine_section(form, engine)
        
        tk.Frame(form, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(14, 14))
        
        # Buttons
        btns = tk.Frame(form, bg=Theme.BG_CARD)
        btns.pack(fill=tk.X)
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10), bg=Theme.BG_ELEVATED, 
                 fg=Theme.TEXT_PRIMARY, bd=0, padx=16, pady=10, command=self.destroy).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Button(btns, text="Save", font=("Segoe UI", 10, "bold"), bg=Theme.BLUE, 
                 fg="white", bd=0, padx=16, pady=10, command=self.save).pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def _build_engine_section(self, parent, engine: RenderEngine):
        """Build settings section for an engine"""
        color = ENGINE_COLORS.get(engine.engine_type, Theme.TEXT_MUTED)
        
        header = tk.Frame(parent, bg=Theme.BG_CARD)
        header.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(header, text=f"{engine.icon} {engine.name}", font=("Segoe UI", 11, "bold"), 
                fg=color, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        
        status = "✓ Available" if engine.is_available else "✗ Not Found"
        status_color = Theme.GREEN if engine.is_available else Theme.RED
        tk.Label(header, text=status, font=("Segoe UI", 9), fg=status_color, 
                bg=Theme.BG_CARD).pack(side=tk.RIGHT)
        
        # Installed versions
        if engine.installed_versions:
            versions_frame = tk.Frame(parent, bg=Theme.BG_ELEVATED)
            versions_frame.pack(fill=tk.X, pady=(0, 8))
            
            for version in sorted(engine.installed_versions.keys(), reverse=True):
                path = engine.installed_versions[version]
                row = tk.Frame(versions_frame, bg=Theme.BG_ELEVATED)
                row.pack(fill=tk.X, padx=8, pady=4)
                
                tk.Label(row, text=f" {version} ", font=("Segoe UI", 9, "bold"),
                        fg="white", bg=color).pack(side=tk.LEFT)
                
                display_path = path if len(path) < 40 else "..." + path[-37:]
                tk.Label(row, text=display_path, font=("Segoe UI", 8), 
                        fg=Theme.TEXT_SECONDARY, bg=Theme.BG_ELEVATED).pack(side=tk.LEFT, padx=(8, 0))
        else:
            tk.Label(parent, text="No installations found", font=("Segoe UI", 9), 
                    fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 8))
        
        # Add custom path button
        btn_frame = tk.Frame(parent, bg=Theme.BG_CARD)
        btn_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Button(btn_frame, text=f"+ Add Custom {engine.name}", font=("Segoe UI", 9), 
                 bg=Theme.BG_ELEVATED, fg=Theme.TEXT_PRIMARY, bd=0, padx=12, pady=6,
                 command=lambda e=engine: self._add_custom_path(e)).pack(side=tk.LEFT)
        
        tk.Button(btn_frame, text="🔄 Rescan", font=("Segoe UI", 9), 
                 bg=Theme.BG_ELEVATED, fg=Theme.TEXT_SECONDARY, bd=0, padx=12, pady=6,
                 command=lambda e=engine: self._rescan_engine(e)).pack(side=tk.LEFT, padx=(8, 0))
        
        tk.Frame(parent, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(8, 12))
    
    def _add_custom_path(self, engine: RenderEngine):
        path = filedialog.askopenfilename(
            title=f"Select {engine.name} Executable",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
        )
        if path:
            version = engine.add_custom_path(path)
            if version:
                messagebox.showinfo("Success", f"Added {engine.name} {version}")
                self.destroy()
                SettingsPanel(self.master, self.settings, self.engine_registry, self.on_save)
            else:
                messagebox.showerror("Error", f"Could not detect {engine.name} version")
    
    def _rescan_engine(self, engine: RenderEngine):
        engine.scan_installed_versions()
        messagebox.showinfo("Scan Complete", 
                          f"Found {len(engine.installed_versions)} {engine.name} installation(s)")
        self.destroy()
        SettingsPanel(self.master, self.settings, self.engine_registry, self.on_save)
    
    def save(self):
        # Update settings with current engine paths
        self.settings.engine_paths = {}
        for engine in self.engine_registry.get_all():
            self.settings.engine_paths[engine.engine_type] = dict(engine.installed_versions)
        
        self.on_save(self.settings)
        self.destroy()


# ============================================================================
# MAIN APPLICATION
# ============================================================================
class RenderManager(tk.Tk):
    CONFIG_FILE = "render_manager_config.json"
    
    def __init__(self):
        super().__init__()
        self.title("Render Manager")
        self.geometry("1000x800")
        self.minsize(900, 650)
        self.configure(bg=Theme.BG_BASE)
        
        self.logo_image = None
        self.icon_image = None
        self._load_app_icons()
        
        self.engine_registry = EngineRegistry()
        self.settings = AppSettings()
        self.jobs: List[RenderJob] = []
        self.job_cards: Dict[str, JobCard] = {}
        self.current_job: Optional[RenderJob] = None
        self.render_start_time: Optional[datetime] = None
        
        self.configure_styles()
        self.load_config()
        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.process_queue()
    
    def _load_app_icons(self):
        """Load application icons"""
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        icon_paths = [
            os.path.join(base_dir, "icon.ico"),
            os.path.join(base_dir, "icon.png"),
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    if icon_path.endswith('.ico'):
                        self.iconbitmap(icon_path)
                    else:
                        icon = tk.PhotoImage(file=icon_path)
                        self.iconphoto(True, icon)
                        self.icon_image = icon
                    break
                except:
                    pass
        
        if HAS_PIL:
            logo_paths = [os.path.join(base_dir, "logo.png")]
            for logo_path in logo_paths:
                if os.path.exists(logo_path):
                    try:
                        img = Image.open(logo_path)
                        img = img.resize((44, 44), Image.LANCZOS)
                        self.logo_image = ImageTk.PhotoImage(img)
                        break
                    except:
                        pass
    
    def configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("TCombobox", fieldbackground=Theme.BG_INPUT, background=Theme.BG_ELEVATED,
                       foreground=Theme.TEXT_PRIMARY, arrowcolor=Theme.TEXT_PRIMARY)
        style.map("TCombobox", fieldbackground=[("readonly", Theme.BG_INPUT)])
        self.option_add("*TCombobox*Listbox.background", Theme.BG_ELEVATED)
        self.option_add("*TCombobox*Listbox.foreground", Theme.TEXT_PRIMARY)
        
        style.configure("Dark.Vertical.TScrollbar",
                       background=Theme.BG_ELEVATED, troughcolor=Theme.BG_BASE,
                       bordercolor=Theme.BG_BASE, arrowcolor=Theme.TEXT_MUTED, relief="flat")
        style.map("Dark.Vertical.TScrollbar",
                 background=[("active", Theme.TEXT_MUTED), ("pressed", Theme.TEXT_SECONDARY)])
    
    def build_ui(self):
        # Header
        header = tk.Frame(self, bg=Theme.BG_CARD)
        header.pack(fill=tk.X)
        
        hcontent = tk.Frame(header, bg=Theme.BG_CARD, padx=20, pady=12)
        hcontent.pack(fill=tk.X)
        
        left = tk.Frame(hcontent, bg=Theme.BG_CARD)
        left.pack(side=tk.LEFT)
        
        if self.logo_image:
            logo_label = tk.Label(left, image=self.logo_image, bg=Theme.BG_CARD)
            logo_label.pack(side=tk.LEFT, padx=(0, 12))
        else:
            logo = tk.Canvas(left, width=44, height=44, highlightthickness=0, bg=Theme.BG_CARD)
            logo.pack(side=tk.LEFT, padx=(0, 12))
            logo.create_rectangle(0, 0, 44, 44, fill="#4f46e5", outline="")
            logo.create_text(22, 22, text="RM", font=("Segoe UI", 13, "bold"), fill="white")
        
        titles = tk.Frame(left, bg=Theme.BG_CARD)
        titles.pack(side=tk.LEFT)
        tk.Label(titles, text="Render Manager", font=("Segoe UI", 16, "bold"), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        
        # Engine status
        engine_status = []
        for engine in self.engine_registry.get_all():
            if engine.is_available:
                engine_status.append(f"{engine.icon} {engine.name}")
        status_text = " | ".join(engine_status) if engine_status else "No engines found"
        tk.Label(titles, text=status_text, font=("Segoe UI", 10), 
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w")
        
        right = tk.Frame(hcontent, bg=Theme.BG_CARD)
        right.pack(side=tk.RIGHT)
        tk.Button(right, text="⚙ Settings", font=("Segoe UI", 9), bg=Theme.BG_ELEVATED, 
                 fg=Theme.TEXT_PRIMARY, bd=0, padx=14, pady=8, command=self.show_settings).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(right, text="+ Add Job", font=("Segoe UI", 9, "bold"), bg=Theme.BLUE, 
                 fg="white", bd=0, padx=14, pady=8, command=self.show_add_job).pack(side=tk.LEFT)
        
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill=tk.X)
        
        # Content
        content = tk.Frame(self, bg=Theme.BG_BASE, padx=20, pady=16)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Stats
        stats = tk.Frame(content, bg=Theme.BG_BASE)
        stats.pack(fill=tk.X, pady=(0, 16))
        
        self.stat_rendering = StatsCard(stats, "Rendering", "▶", Theme.BLUE, "#1e3a8a")
        self.stat_rendering.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.stat_queued = StatsCard(stats, "Queued", "⏱", Theme.YELLOW, "#422006")
        self.stat_queued.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.stat_completed = StatsCard(stats, "Completed", "✓", Theme.GREEN, "#052e16")
        self.stat_completed.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.stat_failed = StatsCard(stats, "Failed", "✕", Theme.RED, "#450a0a")
        self.stat_failed.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Queue header
        qheader = tk.Frame(content, bg=Theme.BG_BASE)
        qheader.pack(fill=tk.X, pady=(0, 10))
        tk.Label(qheader, text="Render Queue", font=("Segoe UI", 14, "bold"), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_BASE).pack(side=tk.LEFT)
        self.queue_count = tk.Label(qheader, text="0 jobs", font=("Segoe UI", 10), 
                                   fg=Theme.TEXT_SECONDARY, bg=Theme.BG_BASE)
        self.queue_count.pack(side=tk.RIGHT)
        
        # Queue list
        list_frame = tk.Frame(content, bg=Theme.BG_BASE)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(list_frame, bg=Theme.BG_BASE, highlightthickness=0)
        queue_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview, 
                                    style="Dark.Vertical.TScrollbar")
        
        self.queue_frame = tk.Frame(self.canvas, bg=Theme.BG_BASE)
        self.queue_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.canvas_win = self.canvas.create_window((0, 0), window=self.queue_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=queue_scroll.set)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_win, width=e.width))
        
        def on_queue_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", on_queue_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        
        queue_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Log panel
        log_frame = tk.Frame(self, bg=Theme.BG_CARD)
        log_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        log_header = tk.Frame(log_frame, bg=Theme.BG_ELEVATED, padx=10, pady=5)
        log_header.pack(fill=tk.X)
        tk.Label(log_header, text="Log", font=("Segoe UI", 9, "bold"), 
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_ELEVATED).pack(side=tk.LEFT)
        self.log_toggle = tk.Button(log_header, text="▲", font=("Segoe UI", 8), 
                                   bg=Theme.BG_ELEVATED, fg=Theme.TEXT_SECONDARY, bd=0, 
                                   command=self.toggle_log)
        self.log_toggle.pack(side=tk.RIGHT)
        tk.Button(log_header, text="Clear", font=("Segoe UI", 8), bg=Theme.BG_ELEVATED, 
                 fg=Theme.TEXT_SECONDARY, bd=0, command=self.clear_log).pack(side=tk.RIGHT, padx=(0, 10))
        
        self.log_container = tk.Frame(log_frame, bg=Theme.BG_CARD)
        self.log_container.pack(fill=tk.X)
        
        self.log_text = tk.Text(self.log_container, height=5, bg=Theme.BG_BASE, fg=Theme.TEXT_SECONDARY,
                               font=("Consolas", 9), bd=0, padx=10, pady=6, state=tk.DISABLED)
        log_scroll = ttk.Scrollbar(self.log_container, orient="vertical", command=self.log_text.yview, 
                                  style="Dark.Vertical.TScrollbar")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
        def on_log_mousewheel(event):
            self.log_text.yview_scroll(int(-1*(event.delta/120)), "units")
        self.log_text.bind("<Enter>", lambda e: self.log_text.bind_all("<MouseWheel>", on_log_mousewheel))
        self.log_text.bind("<Leave>", lambda e: self.log_text.unbind_all("<MouseWheel>"))
        
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.log_visible = True
        
        self.refresh_queue()
        
        # Log engine status
        for engine in self.engine_registry.get_all():
            if engine.is_available:
                self.log(f"✓ {engine.version_display}")
            else:
                self.log(f"⚠ {engine.name} not found")
        
        self.log(f"Loaded {len(self.jobs)} jobs")
    
    def toggle_log(self):
        if self.log_visible:
            self.log_container.pack_forget()
            self.log_toggle.config(text="▼")
        else:
            self.log_container.pack(fill=tk.X)
            self.log_toggle.config(text="▲")
        self.log_visible = not self.log_visible
    
    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def log(self, msg: str):
        self.log_text.config(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def refresh_queue(self):
        for w in self.queue_frame.winfo_children():
            w.destroy()
        self.job_cards.clear()
        
        for job in self.jobs:
            card = JobCard(self.queue_frame, job, self.engine_registry, self.handle_action)
            card.pack(fill=tk.X, pady=(0, 8))
            self.job_cards[job.id] = card
        
        if not self.jobs:
            empty = tk.Frame(self.queue_frame, bg=Theme.BG_CARD, 
                           highlightbackground=Theme.BORDER, highlightthickness=1)
            empty.pack(fill=tk.X, pady=30)
            tk.Label(empty, text="No render jobs", font=("Segoe UI", 12), 
                    fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(pady=(30, 6))
            tk.Label(empty, text='Click "Add Job" to start', font=("Segoe UI", 10), 
                    fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(pady=(0, 30))
        
        self.update_stats()
    
    def update_stats(self):
        self.stat_rendering.set_value(sum(1 for j in self.jobs if j.status == "rendering"))
        self.stat_queued.set_value(sum(1 for j in self.jobs if j.status == "queued"))
        self.stat_completed.set_value(sum(1 for j in self.jobs if j.status == "completed"))
        self.stat_failed.set_value(sum(1 for j in self.jobs if j.status == "failed"))
        self.queue_count.config(text=f"{len(self.jobs)} jobs")
    
    def show_add_job(self):
        AddJobModal(self, self.engine_registry, self.settings, self.add_job)
    
    def show_settings(self):
        SettingsPanel(self, self.settings, self.engine_registry, self.save_settings)
    
    def add_job(self, job: RenderJob):
        self.jobs.insert(0, job)
        self.refresh_queue()
        self.save_config()
        self.log(f"Added: {job.name} ({job.engine_type})")
    
    def save_settings(self, settings: AppSettings):
        self.settings = settings
        self.save_config()
    
    def handle_action(self, action: str, job: RenderJob):
        if action not in ["save"]:
            self.log(f"{action.capitalize()}: {job.name}")
        
        if action == "start":
            job.status = "queued"
            if job.id in self.job_cards:
                self.job_cards[job.id].update_status("queued")
            
        elif action == "pause":
            if self.current_job and self.current_job.id == job.id:
                if self.render_start_time:
                    elapsed = int((datetime.now() - self.render_start_time).total_seconds())
                    job.accumulated_seconds += elapsed
                
                engine = self.engine_registry.get(job.engine_type)
                if engine:
                    engine.cancel_render()
                
                self.current_job = None
                self.render_start_time = None
                
                if job.is_animation and job.current_frame > 0:
                    self.log(f"Paused at frame {job.current_frame}")
            
            job.status = "paused"
            if job.id in self.job_cards:
                self.job_cards[job.id].update_status("paused")
            
        elif action == "retry":
            job.status = "queued"
            job.progress = 0
            job.current_frame = 0
            job.error_message = ""
            job.accumulated_seconds = 0
            if job.id in self.job_cards:
                self.job_cards[job.id].update_status("queued")
                self.job_cards[job.id].update_progress(0, "")
            
        elif action == "delete":
            if self.current_job and self.current_job.id == job.id:
                engine = self.engine_registry.get(job.engine_type)
                if engine:
                    engine.cancel_render()
                self.current_job = None
            self.jobs = [j for j in self.jobs if j.id != job.id]
            self.refresh_queue()
            self.save_config()
        
        elif action == "save":
            pass
        
        elif action == "open_app":
            engine = self.engine_registry.get(job.engine_type)
            if engine:
                engine.open_file_in_app(job.file_path)
            return
        
        self.update_stats()
        self.save_config()
    
    def process_queue(self):
        if self.current_job is None:
            for job in self.jobs:
                if job.status == "queued":
                    self.start_job(job)
                    break
        self.after(1000, self.process_queue)
    
    def start_job(self, job: RenderJob):
        engine = self.engine_registry.get(job.engine_type)
        if not engine:
            job.status = "failed"
            job.error_message = f"Engine '{job.engine_type}' not found"
            self.refresh_queue()
            return
        
        self.current_job = job
        job.status = "rendering"
        job.start_time = datetime.now().strftime("%I:%M %p")
        self.render_start_time = datetime.now()
        
        start_frame = job.frame_start
        if job.is_animation and job.current_frame > 0 and job.current_frame >= job.frame_start:
            start_frame = job.current_frame + 1
            if start_frame > job.frame_end:
                job.status = "completed"
                job.progress = 100
                self.current_job = None
                self.refresh_queue()
                self.log(f"✓ Already complete: {job.name}")
                return
            self.log(f"Resuming from frame {start_frame}")
        
        if job.original_start == 0:
            job.original_start = job.frame_start
        
        if job.id in self.job_cards:
            self.job_cards[job.id].update_status("rendering")
        self.update_stats()
        
        self.log(f"Starting: {job.name} ({engine.name})")
        
        def on_log(msg):
            self.after(0, lambda: self.log(msg))
        
        def on_progress(frame: int, msg: str):
            if job.is_animation:
                if frame > 0:
                    job.current_frame = frame
                    total = job.frame_end - job.original_start + 1
                    done = frame - job.original_start + 1
                    progress = min(int((done / total) * 100), 99)
                else:
                    progress = job.progress
            else:
                if frame == -1:  # Saved
                    progress = 99
                elif frame > 0:
                    progress = min(frame, 99)
                else:
                    progress = max(job.progress, 10)
            
            total_secs = job.accumulated_seconds
            if self.render_start_time:
                total_secs += int((datetime.now() - self.render_start_time).total_seconds())
            h, rem = divmod(total_secs, 3600)
            m, s = divmod(rem, 60)
            elapsed = f"{h}:{m:02d}:{s:02d}"
            
            job.progress = progress
            job.elapsed_time = elapsed
            self.after(0, lambda: self._update_progress(job.id, progress, elapsed))
        
        def on_complete():
            job.status = "completed"
            job.progress = 100
            job.end_time = datetime.now().strftime("%I:%M %p")
            self.current_job = None
            self.after(0, lambda: self.log(f"✓ Complete: {job.name}"))
            self.after(0, lambda: self._finalize(job.id, "completed", 100))
        
        def on_error(err: str):
            job.status = "failed"
            job.error_message = err
            self.current_job = None
            self.after(0, lambda: self.log(f"✗ Failed: {job.name} - {err}"))
            self.after(0, lambda: self._finalize(job.id, "failed", job.progress))
        
        engine.start_render(job, start_frame, on_progress, on_complete, on_error, on_log)
    
    def _update_progress(self, job_id: str, progress: int, elapsed: str):
        if job_id in self.job_cards:
            self.job_cards[job_id].update_progress(progress, elapsed)
    
    def _finalize(self, job_id: str, status: str, progress: int):
        if job_id in self.job_cards:
            self.job_cards[job_id].update_status(status)
            self.job_cards[job_id].update_progress(progress, "")
        self.update_stats()
        self.save_config()
    
    def save_config(self):
        data = {
            "settings": {
                "engine_paths": self.settings.engine_paths,
                "default_versions": self.settings.default_versions,
                "default_engine_type": self.settings.default_engine_type,
                "default_resolution": self.settings.default_resolution,
                "default_format": self.settings.default_format,
                "blender_default_engine": self.settings.blender_default_engine,
                "blender_default_samples": self.settings.blender_default_samples,
                "blender_use_gpu": self.settings.blender_use_gpu,
                "blender_compute_device": self.settings.blender_compute_device,
                "marmoset_renderer": self.settings.marmoset_renderer,
                "marmoset_samples": self.settings.marmoset_samples,
                "marmoset_shadow_quality": self.settings.marmoset_shadow_quality,
            },
            "jobs": [{
                "id": j.id,
                "name": j.name,
                "engine_type": j.engine_type,
                "file_path": j.file_path,
                "output_folder": j.output_folder,
                "output_name": j.output_name,
                "output_format": j.output_format,
                "status": j.status if j.status != "rendering" else "paused",
                "progress": j.progress,
                "is_animation": j.is_animation,
                "frame_start": j.frame_start,
                "frame_end": j.frame_end,
                "current_frame": j.current_frame,
                "original_start": j.original_start,
                "res_width": j.res_width,
                "res_height": j.res_height,
                "camera": j.camera,
                "engine_settings": j.engine_settings,
                "start_time": j.start_time,
                "end_time": j.end_time,
                "elapsed_time": j.elapsed_time,
                "accumulated_seconds": j.accumulated_seconds,
                "error_message": j.error_message,
            } for j in self.jobs]
        }
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except:
            pass
    
    def load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                
                s = data.get("settings", {})
                
                # Load engine paths
                engine_paths = s.get("engine_paths", {})
                for engine_type, paths in engine_paths.items():
                    engine = self.engine_registry.get(engine_type)
                    if engine:
                        for version, path in paths.items():
                            if os.path.exists(path):
                                engine.installed_versions[version] = path
                
                self.settings = AppSettings(
                    engine_paths=engine_paths,
                    default_versions=s.get("default_versions", {}),
                    default_engine_type=s.get("default_engine_type", "blender"),
                    default_resolution=s.get("default_resolution", "1920x1080"),
                    default_format=s.get("default_format", "PNG"),
                    blender_default_engine=s.get("blender_default_engine", "Cycles"),
                    blender_default_samples=s.get("blender_default_samples", 128),
                    blender_use_gpu=s.get("blender_use_gpu", True),
                    blender_compute_device=s.get("blender_compute_device", "Auto"),
                    marmoset_renderer=s.get("marmoset_renderer", "Ray Tracing"),
                    marmoset_samples=s.get("marmoset_samples", 256),
                    marmoset_shadow_quality=s.get("marmoset_shadow_quality", "High"),
                )
                
                # Load jobs
                for jd in data.get("jobs", []):
                    self.jobs.append(RenderJob(
                        id=jd.get("id", str(uuid.uuid4())[:8]),
                        name=jd.get("name", ""),
                        engine_type=jd.get("engine_type", "blender"),
                        file_path=jd.get("file_path", ""),
                        output_folder=jd.get("output_folder", ""),
                        output_name=jd.get("output_name", "render_"),
                        output_format=jd.get("output_format", "PNG"),
                        status=jd.get("status", "queued"),
                        progress=jd.get("progress", 0),
                        is_animation=jd.get("is_animation", False),
                        frame_start=jd.get("frame_start", 1),
                        frame_end=jd.get("frame_end", 250),
                        current_frame=jd.get("current_frame", 0),
                        original_start=jd.get("original_start", 0),
                        res_width=jd.get("res_width", 1920),
                        res_height=jd.get("res_height", 1080),
                        camera=jd.get("camera", "Scene Default"),
                        engine_settings=jd.get("engine_settings", {}),
                        start_time=jd.get("start_time"),
                        end_time=jd.get("end_time"),
                        elapsed_time=jd.get("elapsed_time", ""),
                        accumulated_seconds=jd.get("accumulated_seconds", 0),
                        error_message=jd.get("error_message", ""),
                    ))
            except Exception as e:
                print(f"Error loading config: {e}")
    
    def on_close(self):
        if self.current_job:
            if messagebox.askyesno("Confirm", "Render in progress. Pause and exit?"):
                engine = self.engine_registry.get(self.current_job.engine_type)
                if engine:
                    engine.cancel_render()
                self.current_job.status = "paused"
                self.save_config()
                self.destroy()
        else:
            self.save_config()
            self.destroy()


if __name__ == "__main__":
    app = RenderManager()
    app.mainloop()
