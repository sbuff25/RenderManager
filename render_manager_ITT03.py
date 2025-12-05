#!/usr/bin/env python3
"""
Render Manager - ITT03 (Figma Edition)
Queue-based render management with pause/resume support
UI styled to match Figma design exactly
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
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict

# Try to import PIL for image handling
try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ============================================================================
# THEME - Exact Figma/Tailwind Zinc Color Palette
# ============================================================================
class Theme:
    """
    Color palette extracted from Figma export (Tailwind Zinc scale)
    """
    # Backgrounds
    BG_BASE = "#09090b"       # zinc-950 - Main app background
    BG_CARD = "#18181b"       # zinc-900 - Card backgrounds
    BG_ELEVATED = "#27272a"   # zinc-800 - Elevated surfaces, inputs
    BG_HOVER = "#3f3f46"      # zinc-700 - Hover states
    BG_HEADER = "#18181b"     # zinc-900/50 with backdrop blur effect
    
    # Borders
    BORDER = "#27272a"        # zinc-800
    BORDER_LIGHT = "#3f3f46"  # zinc-700
    BORDER_FOCUS = "#2563eb"  # blue-500 for focus states
    
    # Text
    TEXT_PRIMARY = "#fafafa"   # zinc-100
    TEXT_SECONDARY = "#a1a1aa" # zinc-400
    TEXT_MUTED = "#71717a"     # zinc-500
    TEXT_DIM = "#52525b"       # zinc-600
    
    # Primary - Blue
    BLUE = "#2563eb"           # blue-600
    BLUE_HOVER = "#1d4ed8"     # blue-700
    BLUE_LIGHT = "#3b82f6"     # blue-500 (progress bars)
    BLUE_DIM = "#1e3a8a"       # blue-900/20 (icon backgrounds)
    BLUE_TEXT = "#60a5fa"      # blue-400 (icons, light accents)
    
    # Status Colors
    GREEN = "#22c55e"          # green-500
    GREEN_LIGHT = "#4ade80"    # green-400
    GREEN_DIM = "#052e16"      # green-900/20
    
    YELLOW = "#facc15"         # yellow-400
    YELLOW_DIM = "#422006"     # yellow-900/20
    
    ORANGE = "#f97316"         # orange-500
    ORANGE_DIM = "#431407"     # orange-900/20
    
    RED = "#ef4444"            # red-500
    RED_LIGHT = "#f87171"      # red-400
    RED_DIM = "#450a0a"        # red-900/20
    
    # Sizing
    RADIUS_SM = 4              # rounded-sm
    RADIUS = 6                 # rounded
    RADIUS_LG = 8              # rounded-lg
    RADIUS_XL = 12             # rounded-xl
    
    # Fonts
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_XS = 10
    FONT_SIZE_SM = 11
    FONT_SIZE_BASE = 12
    FONT_SIZE_LG = 14
    FONT_SIZE_XL = 16
    FONT_SIZE_2XL = 20
    FONT_SIZE_3XL = 28


# ============================================================================
# DATA MODELS
# ============================================================================
@dataclass
class RenderJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
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
    res_percentage: int = 100
    engine: str = "Cycles"
    samples: int = 128
    camera: str = "Scene Default"
    use_gpu: bool = True
    compute_device: str = "Auto"
    denoiser: str = "None"
    use_scene_settings: bool = True
    use_factory_startup: bool = False
    blender_version: str = "auto"
    file_blender_version: str = ""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    elapsed_time: str = ""
    accumulated_seconds: int = 0
    error_message: str = ""
    estimated_time: str = ""
    priority: int = 3
    
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


@dataclass
class AppSettings:
    blender_paths: Dict[str, str] = field(default_factory=dict)
    default_blender: str = ""
    default_engine: str = "Cycles"
    default_resolution: str = "1920x1080"
    default_format: str = "PNG"
    default_samples: int = 128
    use_gpu: bool = True
    compute_device: str = "Auto"
    max_concurrent_jobs: int = 1
    render_quality: str = "High"
    
    @property
    def blender_path(self) -> str:
        if self.default_blender and self.default_blender in self.blender_paths:
            return self.blender_paths[self.default_blender]
        if self.blender_paths:
            return list(self.blender_paths.values())[0]
        return ""


# ============================================================================
# BLENDER INTERFACE
# ============================================================================
class BlenderInterface:
    SEARCH_PATHS = [
        r"C:\Program Files\Blender Foundation\Blender 4.5",
        r"C:\Program Files\Blender Foundation\Blender 4.4",
        r"C:\Program Files\Blender Foundation\Blender 4.3",
        r"C:\Program Files\Blender Foundation\Blender 4.2",
        r"C:\Program Files\Blender Foundation\Blender 4.1",
        r"C:\Program Files\Blender Foundation\Blender 4.0",
        r"C:\Program Files\Blender Foundation\Blender 3.6",
        r"C:\Program Files\Blender Foundation\Blender 3.5",
        r"C:\Program Files\Blender Foundation\Blender 3.4",
        r"C:\Program Files\Blender Foundation\Blender 3.3",
    ]
    
    OUTPUT_FORMATS = {"PNG": "PNG", "JPEG": "JPEG", "OpenEXR": "OPEN_EXR", "TIFF": "TIFF"}
    COMPUTE_DEVICES = {"Auto": "AUTO", "OptiX": "OPTIX", "CUDA": "CUDA", "HIP": "HIP", "CPU": "CPU"}
    DENOISERS = {"None": "NONE", "OptiX": "OPTIX", "OpenImageDenoise": "OPENIMAGEDENOISE"}
    RENDER_ENGINES = {"Cycles": "CYCLES", "Eevee": "BLENDER_EEVEE_NEXT", "Workbench": "BLENDER_WORKBENCH"}
    
    def __init__(self):
        self.installed_versions: Dict[str, str] = {}
        self.current_process: Optional[subprocess.Popen] = None
        self.temp_script_path: Optional[str] = None
        self.is_cancelling = False
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        self.installed_versions = {}
        for base_path in self.SEARCH_PATHS:
            exe_path = os.path.join(base_path, "blender.exe")
            if os.path.exists(exe_path):
                version = self._get_version_from_exe(exe_path)
                if version:
                    self.installed_versions[version] = exe_path
    
    def add_custom_path(self, path: str) -> Optional[str]:
        if os.path.exists(path):
            version = self._get_version_from_exe(path)
            if version:
                self.installed_versions[version] = path
                return version
        return None
    
    def _get_version_from_exe(self, exe_path: str) -> Optional[str]:
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                [exe_path, "--version"],
                capture_output=True, timeout=10, startupinfo=startupinfo
            )
            
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
    
    def get_blend_file_version(self, blend_path: str) -> Optional[str]:
        try:
            with open(blend_path, 'rb') as f:
                header = f.read(12)
                if header[:2] == b'\x1f\x8b':
                    import gzip
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
    
    def get_path_for_version(self, version: str) -> Optional[str]:
        return self.installed_versions.get(version)
    
    @property
    def blender_path(self) -> str:
        if self.installed_versions:
            versions = sorted(self.installed_versions.keys(), reverse=True)
            return self.installed_versions[versions[0]]
        return ""
    
    @property
    def version(self) -> str:
        if self.installed_versions:
            return sorted(self.installed_versions.keys(), reverse=True)[0]
        return "Not detected"
    
    @property
    def version_display(self) -> str:
        if self.installed_versions:
            count = len(self.installed_versions)
            newest = sorted(self.installed_versions.keys(), reverse=True)[0]
            if count == 1:
                return f"Blender {newest}"
            return f"Blender {newest} (+{count-1} more)"
        return "Blender not detected"
    
    def get_render_engines(self, version: str = None) -> dict:
        if version:
            parts = [int(x) for x in version.split('.')]
            if parts[0] >= 4:
                return {"Cycles": "CYCLES", "Eevee": "BLENDER_EEVEE_NEXT", "Workbench": "BLENDER_WORKBENCH"}
        return {"Cycles": "CYCLES", "Eevee": "BLENDER_EEVEE", "Workbench": "BLENDER_WORKBENCH"}
    
    def get_scene_info(self, blend_file: str) -> dict:
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
        
        file_version = self.get_blend_file_version(blend_file)
        if file_version:
            default_info["file_version"] = file_version
        
        blender_exe = self.get_best_blender_for_file(blend_file)
        if not blender_exe or not os.path.exists(blend_file):
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
                [blender_exe, "-b", blend_file, "--python", temp_path],
                capture_output=True, timeout=60, startupinfo=startupinfo
            )
            os.unlink(temp_path)
            
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
    
    def generate_render_script(self, job: RenderJob, blender_version: str = None) -> str:
        fmt = self.OUTPUT_FORMATS.get(job.output_format, "PNG")
        script = ["import bpy", "import sys", ""]
        script.append(f"bpy.context.scene.render.image_settings.file_format = '{fmt}'")
        script.append("")
        
        if job.use_scene_settings:
            script.append("# Using scene's existing render settings")
            script.append("print(f'Engine: {bpy.context.scene.render.engine}')")
            script.append("print(f'Resolution: {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y}')")
            
            if job.camera and job.camera != "Scene Default":
                script.extend([
                    "", "# Set camera", "try:",
                    f"    bpy.context.scene.camera = bpy.data.objects['{job.camera}']",
                    "except Exception as e:",
                    f"    print(f'Warning: Could not set camera: {{e}}')",
                ])
            return "\n".join(script)
        
        engines = self.get_render_engines(blender_version)
        engine = engines.get(job.engine, "CYCLES")
        compute_type = self.COMPUTE_DEVICES.get(job.compute_device, "AUTO")
        denoiser = self.DENOISERS.get(job.denoiser, "NONE")
        
        if job.camera and job.camera != "Scene Default":
            script.extend([
                "# Set camera", "try:",
                f"    bpy.context.scene.camera = bpy.data.objects['{job.camera}']",
                "except Exception as e:",
                f"    print(f'Warning: Could not set camera: {{e}}')", ""
            ])
        
        script.append("# Resolution")
        script.append(f"bpy.context.scene.render.resolution_x = {job.res_width}")
        script.append(f"bpy.context.scene.render.resolution_y = {job.res_height}")
        script.append(f"bpy.context.scene.render.resolution_percentage = {job.res_percentage}")
        script.append("")
        script.append("# Render engine")
        script.append(f"bpy.context.scene.render.engine = '{engine}'")
        script.append("")
        
        if job.use_gpu and job.engine == "Cycles" and compute_type != "CPU":
            script.append("# GPU setup")
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
                    "                        print(f'GPU: {device.name}')",
                    "                if gpu_found:",
                    "                    print(f'Using {ctype}')",
                    "                    return True",
                    "            except Exception as e:",
                    "                print(f'GPU type {ctype} not available: {e}')",
                    "                continue",
                    "        return False",
                ])
            else:
                script.extend([
                    f"        cycles_prefs.compute_device_type = '{compute_type}'",
                    "        cycles_prefs.get_devices()",
                    "        for device in cycles_prefs.devices:",
                    "            if device.type != 'CPU':",
                    "                device.use = True",
                    "                print(f'GPU: {device.name}')",
                    "            else:",
                    "                device.use = False",
                    "        return True",
                ])
            
            script.extend([
                "    except Exception as e:",
                "        print(f'GPU setup failed: {e}')",
                "        return False", "",
                "if setup_gpu():",
                "    bpy.context.scene.cycles.device = 'GPU'",
                "    print('Rendering on GPU')",
                "else:",
                "    bpy.context.scene.cycles.device = 'CPU'",
                "    print('Falling back to CPU')", ""
            ])
        
        if job.engine == "Cycles":
            script.append("# Cycles settings")
            script.append("try:")
            script.append(f"    bpy.context.scene.cycles.samples = {job.samples}")
            if denoiser != "NONE":
                script.append("    bpy.context.scene.cycles.use_denoising = True")
                script.append(f"    bpy.context.scene.cycles.denoiser = '{denoiser}'")
            script.append("except Exception as e:")
            script.append("    print(f'Warning: Could not set Cycles settings: {e}')")
            script.append("")
        
        return "\n".join(script)
    
    def start_render(self, job: RenderJob, start_frame: int, on_progress: Callable,
                    on_complete: Callable, on_error: Callable, on_log: Callable = None):
        if job.blender_version == "auto":
            blender_exe = self.get_best_blender_for_file(job.file_path)
        else:
            blender_exe = self.get_path_for_version(job.blender_version)
        
        if not blender_exe:
            blender_exe = self.blender_path
        
        if not blender_exe:
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
        if job.use_factory_startup:
            cmd.append("--factory-startup")
        cmd.extend([job.file_path, "--python", self.temp_script_path,
                   "-o", output_path, "-F", fmt, "-x", "1"])
        
        if job.is_animation:
            cmd.extend(["-s", str(start_frame), "-e", str(job.frame_end), "-a"])
        else:
            cmd.extend(["-f", str(job.frame_start)])
        
        if on_log:
            version_info = render_version or "unknown"
            on_log(f"Using Blender {version_info}: {blender_exe}")
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
                self.cleanup()
                
                if self.is_cancelling:
                    pass
                elif return_code == 0:
                    on_complete()
                else:
                    on_error(f"Blender exited with code {return_code}")
            except Exception as e:
                self.cleanup()
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
            self.cleanup()
    
    def cleanup(self):
        if self.temp_script_path and os.path.exists(self.temp_script_path):
            try:
                os.unlink(self.temp_script_path)
            except:
                pass
        self.temp_script_path = None
        self.current_process = None


# ============================================================================
# UI COMPONENTS - Figma Styled
# ============================================================================

class StatsCard(tk.Frame):
    """Stats card matching Figma design exactly"""
    
    CONFIGS = {
        "rendering": {"icon": "▶", "color": Theme.BLUE_TEXT, "bg": Theme.BLUE_DIM},
        "queued": {"icon": "⏱", "color": Theme.YELLOW, "bg": Theme.YELLOW_DIM},
        "completed": {"icon": "✓", "color": Theme.GREEN_LIGHT, "bg": Theme.GREEN_DIM},
        "failed": {"icon": "✕", "color": Theme.RED_LIGHT, "bg": Theme.RED_DIM},
    }
    
    def __init__(self, parent, stat_type: str, title: str):
        super().__init__(parent, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER, 
                        highlightthickness=1)
        
        config = self.CONFIGS.get(stat_type, self.CONFIGS["queued"])
        
        # Main container with padding
        inner = tk.Frame(self, bg=Theme.BG_CARD, padx=20, pady=16)
        inner.pack(fill=tk.BOTH, expand=True)
        
        # Horizontal layout: icon + text
        row = tk.Frame(inner, bg=Theme.BG_CARD)
        row.pack(fill=tk.X)
        
        # Icon with colored background
        icon_frame = tk.Frame(row, bg=config["bg"], width=40, height=40)
        icon_frame.pack(side=tk.LEFT, padx=(0, 12))
        icon_frame.pack_propagate(False)
        
        tk.Label(icon_frame, text=config["icon"], font=(Theme.FONT_FAMILY, 16),
                fg=config["color"], bg=config["bg"]).place(relx=0.5, rely=0.5, anchor="center")
        
        # Text column
        text_col = tk.Frame(row, bg=Theme.BG_CARD)
        text_col.pack(side=tk.LEFT, fill=tk.X)
        
        tk.Label(text_col, text=title, font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w")
        
        self.value_label = tk.Label(text_col, text="0", 
                                    font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_3XL, "bold"),
                                    fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD)
        self.value_label.pack(anchor="w")
    
    def set_value(self, value: int):
        self.value_label.config(text=str(value))


class JobCard(tk.Frame):
    """Job card matching Figma RenderJobCard design"""
    
    STATUS_STYLES = {
        "rendering": {"fg": Theme.BLUE_TEXT, "bg": "#1e3a8a33", "border": "#2563eb4d"},
        "queued": {"fg": Theme.YELLOW, "bg": "#42200633", "border": "#eab3084d"},
        "completed": {"fg": Theme.GREEN_LIGHT, "bg": "#052e1633", "border": "#22c55e4d"},
        "failed": {"fg": Theme.RED_LIGHT, "bg": "#450a0a33", "border": "#ef44444d"},
        "paused": {"fg": Theme.TEXT_SECONDARY, "bg": "#3f3f4633", "border": "#71717a4d"},
    }
    
    def __init__(self, parent, job: RenderJob, on_action: Callable):
        super().__init__(parent, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER,
                        highlightthickness=1)
        
        self.job = job
        self.on_action = on_action
        self.expanded = False
        
        # Bind hover effect
        self.bind("<Enter>", lambda e: self.config(highlightbackground=Theme.BORDER_LIGHT))
        self.bind("<Leave>", lambda e: self.config(highlightbackground=Theme.BORDER))
        
        self.build_ui()
    
    def build_ui(self):
        # Main content padding
        self.content = tk.Frame(self, bg=Theme.BG_CARD, padx=16, pady=12)
        self.content.pack(fill=tk.X)
        
        # Top row: info + actions
        top = tk.Frame(self.content, bg=Theme.BG_CARD)
        top.pack(fill=tk.X)
        
        # Left: Job info
        info = tk.Frame(top, bg=Theme.BG_CARD)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Name + status badge row
        name_row = tk.Frame(info, bg=Theme.BG_CARD)
        name_row.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(name_row, text=self.job.name or "Untitled",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_LG, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        
        # Status badge
        style = self.STATUS_STYLES.get(self.job.status, self.STATUS_STYLES["queued"])
        self.status_frame = tk.Frame(name_row, bg=Theme.BG_ELEVATED, padx=8, pady=2)
        self.status_frame.pack(side=tk.LEFT, padx=(12, 0))
        self.status_label = tk.Label(self.status_frame, text=self.job.status.upper(),
                                     font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XS, "bold"),
                                     fg=style["fg"], bg=Theme.BG_ELEVATED)
        self.status_label.pack()
        
        # File name
        tk.Label(info, text=self.job.file_name,
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        
        # File paths (if available)
        if self.job.file_path or self.job.output_folder:
            paths = tk.Frame(info, bg=Theme.BG_CARD)
            paths.pack(anchor="w", pady=(0, 8))
            if self.job.file_path:
                path_display = self.job.file_path if len(self.job.file_path) < 60 else "..." + self.job.file_path[-57:]
                tk.Label(paths, text=f"Input: {path_display}",
                        font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XS),
                        fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w")
            if self.job.output_folder:
                out_display = self.job.output_folder if len(self.job.output_folder) < 60 else "..." + self.job.output_folder[-57:]
                tk.Label(paths, text=f"Output: {out_display}",
                        font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XS),
                        fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w")
        
        # Right: Action buttons
        self.actions = tk.Frame(top, bg=Theme.BG_CARD)
        self.actions.pack(side=tk.RIGHT)
        self._build_actions()
        
        # Progress bar (only shown when not queued)
        self.progress_frame = tk.Frame(self.content, bg=Theme.BG_CARD)
        if self.job.status != "queued" or self.job.progress > 0:
            self.progress_frame.pack(fill=tk.X, pady=(8, 0))
            self._build_progress()
        
        # Quick info row
        self.info_frame = tk.Frame(self.content, bg=Theme.BG_CARD)
        self.info_frame.pack(fill=tk.X, pady=(8, 0))
        self._build_info()
        
        # Expanded details (hidden by default)
        self.details_frame = tk.Frame(self.content, bg=Theme.BG_CARD)
    
    def _build_actions(self):
        for w in self.actions.winfo_children():
            w.destroy()
        
        btn_style = {
            "font": (Theme.FONT_FAMILY, 14),
            "width": 2,
            "bd": 0,
            "cursor": "hand2",
            "bg": Theme.BG_CARD,
            "activebackground": Theme.BG_HOVER,
        }
        
        # Status-dependent action button
        if self.job.status == "rendering":
            btn = tk.Button(self.actions, text="⏸", fg=Theme.YELLOW, **btn_style,
                           command=lambda: self.on_action("pause", self.job))
            btn.pack(side=tk.LEFT, padx=2)
        elif self.job.status in ["queued", "paused"]:
            btn = tk.Button(self.actions, text="▶", fg=Theme.GREEN_LIGHT, **btn_style,
                           command=lambda: self.on_action("start", self.job))
            btn.pack(side=tk.LEFT, padx=2)
        elif self.job.status == "failed":
            btn = tk.Button(self.actions, text="↻", fg=Theme.YELLOW, **btn_style,
                           command=lambda: self.on_action("retry", self.job))
            btn.pack(side=tk.LEFT, padx=2)
        
        # Expand button
        self.expand_btn = tk.Button(self.actions, text="▼" if not self.expanded else "▲",
                                    fg=Theme.TEXT_SECONDARY, **btn_style,
                                    command=self.toggle_expand)
        self.expand_btn.pack(side=tk.LEFT, padx=2)
        
        # Delete button
        delete_btn = tk.Button(self.actions, text="🗑", fg=Theme.RED_LIGHT, **btn_style,
                              command=lambda: self.on_action("delete", self.job))
        delete_btn.pack(side=tk.LEFT, padx=2)
    
    def _build_progress(self):
        for w in self.progress_frame.winfo_children():
            w.destroy()
        
        # Progress header
        header = tk.Frame(self.progress_frame, bg=Theme.BG_CARD)
        header.pack(fill=tk.X)
        
        tk.Label(header, text="Progress",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        
        self.progress_pct = tk.Label(header, text=f"{self.job.progress}%",
                                     font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                                     fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD)
        self.progress_pct.pack(side=tk.RIGHT)
        
        # Progress bar
        bar_bg = tk.Frame(self.progress_frame, bg=Theme.BG_ELEVATED, height=8)
        bar_bg.pack(fill=tk.X, pady=(4, 0))
        bar_bg.pack_propagate(False)
        
        # Progress bar color based on status
        if self.job.status == "completed":
            bar_color = Theme.GREEN
        elif self.job.status == "failed":
            bar_color = Theme.RED
        elif self.job.status == "paused":
            bar_color = Theme.ORANGE
        else:
            bar_color = Theme.BLUE_LIGHT
        
        self.progress_bar = tk.Frame(bar_bg, bg=bar_color, height=8)
        self.progress_bar.place(relx=0, rely=0, relheight=1, 
                               relwidth=max(0.01, self.job.progress/100))
    
    def _build_info(self):
        for w in self.info_frame.winfo_children():
            w.destroy()
        
        parts = [
            f"Frames: {self.job.frames_display}",
            self.job.resolution_display,
            self.job.engine
        ]
        if self.job.estimated_time:
            parts.append(f"~{self.job.estimated_time}")
        if self.job.elapsed_time:
            parts.append(f"⏱ {self.job.elapsed_time}")
        
        tk.Label(self.info_frame, text="  •  ".join(parts),
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w")
    
    def update_progress(self, progress: int, elapsed: str = ""):
        self.job.progress = progress
        if elapsed:
            self.job.elapsed_time = elapsed
        
        if not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill=tk.X, pady=(8, 0))
            self._build_progress()
        
        if hasattr(self, 'progress_pct') and self.progress_pct.winfo_exists():
            self.progress_pct.config(text=f"{progress}%")
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            self.progress_bar.place(relwidth=max(0.01, progress/100))
        
        self._build_info()
    
    def update_status(self, status: str):
        self.job.status = status
        style = self.STATUS_STYLES.get(status, self.STATUS_STYLES["queued"])
        
        self.status_label.config(text=status.upper(), fg=style["fg"])
        self._build_actions()
        
        # Update progress bar color
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            if status == "completed":
                self.progress_bar.config(bg=Theme.GREEN)
            elif status == "failed":
                self.progress_bar.config(bg=Theme.RED)
            elif status == "paused":
                self.progress_bar.config(bg=Theme.ORANGE)
            else:
                self.progress_bar.config(bg=Theme.BLUE_LIGHT)
        
        if status == "rendering" and not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill=tk.X, pady=(8, 0))
            self._build_progress()
        
        self._build_info()
    
    def toggle_expand(self):
        self.expanded = not self.expanded
        self.expand_btn.config(text="▲" if self.expanded else "▼")
        
        if self.expanded:
            self.details_frame.pack(fill=tk.X, pady=(12, 0))
            
            # Separator
            tk.Frame(self.details_frame, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(0, 12))
            
            # Details grid (2 columns)
            grid = tk.Frame(self.details_frame, bg=Theme.BG_CARD)
            grid.pack(fill=tk.X)
            
            details = [
                ("Priority", str(self.job.priority)),
                ("Camera", self.job.camera),
                ("Render Engine", self.job.engine),
                ("Resolution", f"{self.job.res_width}×{self.job.res_height}"),
                ("Frame Range", self.job.frames_display),
                ("Format", self.job.output_format),
            ]
            if self.job.start_time:
                details.append(("Start Time", self.job.start_time))
            if self.job.end_time:
                details.append(("End Time", self.job.end_time))
            if self.job.error_message:
                details.append(("Error", self.job.error_message[:50]))
            
            for i, (label, value) in enumerate(details):
                cell = tk.Frame(grid, bg=Theme.BG_CARD)
                cell.grid(row=i//2, column=i%2, sticky="w", padx=(0, 40), pady=4)
                
                tk.Label(cell, text=label,
                        font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                        fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w")
                tk.Label(cell, text=value,
                        font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                        fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w")
        else:
            self.details_frame.pack_forget()
            for w in self.details_frame.winfo_children():
                w.destroy()


# ============================================================================
# ADD JOB MODAL - Figma Styled
# ============================================================================
class AddJobModal(tk.Toplevel):
    def __init__(self, parent, blender: BlenderInterface, settings: AppSettings, on_add: Callable):
        super().__init__(parent)
        self.blender = blender
        self.settings = settings
        self.on_add = on_add
        self.scene_info = None
        self.file_version = None
        
        self.title("Submit Render Job")
        self.configure(bg=Theme.BG_CARD)
        self.geometry("600x750")
        self.transient(parent)
        self.grab_set()
        
        # Variables
        self.name_var = tk.StringVar()
        self.file_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.output_name_var = tk.StringVar(value="render_")
        self.format_var = tk.StringVar(value=settings.default_format)
        self.frames_var = tk.StringVar(value="1-250")
        self.resolution_var = tk.StringVar(value=settings.default_resolution)
        self.engine_var = tk.StringVar(value=settings.default_engine)
        self.priority_var = tk.StringVar(value="3")
        self.estimated_var = tk.StringVar()
        self.camera_var = tk.StringVar(value="Scene Default")
        self.is_anim_var = tk.BooleanVar(value=True)
        self.gpu_var = tk.BooleanVar(value=settings.use_gpu)
        self.paused_var = tk.BooleanVar(value=False)
        
        self.build_ui()
    
    def build_ui(self):
        # Scrollable content
        canvas = tk.Canvas(self, bg=Theme.BG_CARD, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=Theme.BG_CARD)
        
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw", width=580)
        canvas.configure(yscrollcommand=scroll.set)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Header
        header = tk.Frame(frame, bg=Theme.BG_CARD)
        header.pack(fill=tk.X, padx=24, pady=16)
        
        # Icon + Title
        header_left = tk.Frame(header, bg=Theme.BG_CARD)
        header_left.pack(side=tk.LEFT)
        
        icon_frame = tk.Frame(header_left, bg=Theme.BLUE_DIM, width=32, height=32)
        icon_frame.pack(side=tk.LEFT, padx=(0, 12))
        icon_frame.pack_propagate(False)
        tk.Label(icon_frame, text="📤", font=(Theme.FONT_FAMILY, 12),
                bg=Theme.BLUE_DIM).place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(header_left, text="Submit Render Job",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XL, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        
        tk.Button(header, text="✕", font=(Theme.FONT_FAMILY, 14),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_SECONDARY, bd=0,
                 activebackground=Theme.BG_HOVER, cursor="hand2",
                 command=self.destroy).pack(side=tk.RIGHT)
        
        # Separator
        tk.Frame(frame, bg=Theme.BORDER, height=1).pack(fill=tk.X)
        
        # Form
        form = tk.Frame(frame, bg=Theme.BG_CARD, padx=24, pady=20)
        form.pack(fill=tk.BOTH, expand=True)
        
        # Job Name
        self._field(form, "Job Name *", self.name_var, "Scene_01_FinalRender")
        
        # Scene File with Browse
        self._file_field(form, "Scene File *", self.file_var, self.browse_file, 
                        "/path/to/project_main.blend")
        
        # Output Directory with Browse
        self._file_field(form, "Output Directory *", self.output_var, self.browse_output,
                        "/path/to/output/")
        
        # Frame Range
        self._field(form, "Frame Range *", self.frames_var, "1-250")
        tk.Label(form, text="Example: 1-250 or 1,5,10-20",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XS),
                fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 10))
        
        # Settings Grid (2 columns)
        grid = tk.Frame(form, bg=Theme.BG_CARD)
        grid.pack(fill=tk.X, pady=(0, 16))
        
        # Row 1: Resolution, Priority
        row1 = tk.Frame(grid, bg=Theme.BG_CARD)
        row1.pack(fill=tk.X, pady=(0, 12))
        
        res_frame = tk.Frame(row1, bg=Theme.BG_CARD)
        res_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(res_frame, text="Resolution",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        res_combo = ttk.Combobox(res_frame, textvariable=self.resolution_var,
                                values=["1920x1080", "2560x1440", "3840x2160", "7680x4320"],
                                state="readonly")
        res_combo.pack(fill=tk.X)
        
        pri_frame = tk.Frame(row1, bg=Theme.BG_CARD)
        pri_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        tk.Label(pri_frame, text="Priority",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        pri_combo = ttk.Combobox(pri_frame, textvariable=self.priority_var,
                                values=["1 (Highest)", "2 (High)", "3 (Normal)", "4 (Low)", "5 (Lowest)"],
                                state="readonly")
        pri_combo.pack(fill=tk.X)
        
        # Row 2: Engine, Format
        row2 = tk.Frame(grid, bg=Theme.BG_CARD)
        row2.pack(fill=tk.X, pady=(0, 12))
        
        eng_frame = tk.Frame(row2, bg=Theme.BG_CARD)
        eng_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(eng_frame, text="Render Engine",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        eng_combo = ttk.Combobox(eng_frame, textvariable=self.engine_var,
                                values=["Cycles", "Eevee", "Workbench"],
                                state="readonly")
        eng_combo.pack(fill=tk.X)
        
        fmt_frame = tk.Frame(row2, bg=Theme.BG_CARD)
        fmt_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        tk.Label(fmt_frame, text="Output Format",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        fmt_combo = ttk.Combobox(fmt_frame, textvariable=self.format_var,
                                values=["PNG", "JPEG", "OpenEXR", "TIFF"],
                                state="readonly")
        fmt_combo.pack(fill=tk.X)
        
        # Row 3: Camera, Estimated Time
        row3 = tk.Frame(grid, bg=Theme.BG_CARD)
        row3.pack(fill=tk.X)
        
        cam_frame = tk.Frame(row3, bg=Theme.BG_CARD)
        cam_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(cam_frame, text="Camera",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        self.camera_combo = ttk.Combobox(cam_frame, textvariable=self.camera_var,
                                        values=["Scene Default"],
                                        state="readonly")
        self.camera_combo.pack(fill=tk.X)
        
        est_frame = tk.Frame(row3, bg=Theme.BG_CARD)
        est_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        tk.Label(est_frame, text="Estimated Time",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        tk.Entry(est_frame, textvariable=self.estimated_var,
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE),
                bg=Theme.BG_ELEVATED, fg=Theme.TEXT_PRIMARY, bd=0,
                insertbackground=Theme.TEXT_PRIMARY).pack(fill=tk.X, ipady=6, ipadx=8)
        
        # Checkboxes
        check_frame = tk.Frame(form, bg=Theme.BG_CARD)
        check_frame.pack(fill=tk.X, pady=(8, 16))
        
        tk.Checkbutton(check_frame, text="Enable GPU Rendering", variable=self.gpu_var,
                      font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                      fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD,
                      selectcolor=Theme.BG_ELEVATED, activebackground=Theme.BG_CARD,
                      activeforeground=Theme.TEXT_PRIMARY).pack(anchor="w", pady=2)
        
        tk.Checkbutton(check_frame, text="Submit as Paused", variable=self.paused_var,
                      font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                      fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD,
                      selectcolor=Theme.BG_ELEVATED, activebackground=Theme.BG_CARD,
                      activeforeground=Theme.TEXT_PRIMARY).pack(anchor="w", pady=2)
        
        # Separator
        tk.Frame(form, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(0, 16))
        
        # Buttons
        btns = tk.Frame(form, bg=Theme.BG_CARD)
        btns.pack(fill=tk.X)
        
        cancel_btn = tk.Button(btns, text="Cancel",
                              font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE),
                              bg=Theme.BG_ELEVATED, fg=Theme.TEXT_SECONDARY,
                              bd=0, padx=20, pady=12, cursor="hand2",
                              activebackground=Theme.BG_HOVER,
                              command=self.destroy)
        cancel_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        
        submit_btn = tk.Button(btns, text="📤  Submit Job",
                              font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE, "bold"),
                              bg=Theme.BLUE, fg="white",
                              bd=0, padx=20, pady=12, cursor="hand2",
                              activebackground=Theme.BLUE_HOVER,
                              command=self.submit)
        submit_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
    
    def _field(self, parent, label, var, placeholder=""):
        f = tk.Frame(parent, bg=Theme.BG_CARD)
        f.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(f, text=label,
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        
        entry = tk.Entry(f, textvariable=var,
                        font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE),
                        bg=Theme.BG_ELEVATED, fg=Theme.TEXT_PRIMARY, bd=0,
                        insertbackground=Theme.TEXT_PRIMARY)
        entry.pack(fill=tk.X, ipady=8, ipadx=10)
        
        # Placeholder behavior
        if placeholder and not var.get():
            entry.insert(0, placeholder)
            entry.config(fg=Theme.TEXT_MUTED)
            
            def on_focus_in(e):
                if entry.get() == placeholder:
                    entry.delete(0, tk.END)
                    entry.config(fg=Theme.TEXT_PRIMARY)
            
            def on_focus_out(e):
                if not entry.get():
                    entry.insert(0, placeholder)
                    entry.config(fg=Theme.TEXT_MUTED)
            
            entry.bind("<FocusIn>", on_focus_in)
            entry.bind("<FocusOut>", on_focus_out)
    
    def _file_field(self, parent, label, var, cmd, placeholder=""):
        f = tk.Frame(parent, bg=Theme.BG_CARD)
        f.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(f, text=label,
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        
        row = tk.Frame(f, bg=Theme.BG_CARD)
        row.pack(fill=tk.X)
        
        entry = tk.Entry(row, textvariable=var,
                        font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE),
                        bg=Theme.BG_ELEVATED, fg=Theme.TEXT_PRIMARY, bd=0,
                        insertbackground=Theme.TEXT_PRIMARY)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, ipadx=10)
        
        btn = tk.Button(row, text="📁 Browse",
                       font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                       bg=Theme.BG_ELEVATED, fg=Theme.TEXT_SECONDARY,
                       bd=0, padx=12, pady=6, cursor="hand2",
                       activebackground=Theme.BG_HOVER,
                       command=cmd)
        btn.pack(side=tk.LEFT, padx=(8, 0))
    
    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Blender Files", "*.blend")])
        if path:
            self.file_var.set(path)
            
            if not self.name_var.get() or self.name_var.get().startswith("Scene_"):
                self.name_var.set(os.path.splitext(os.path.basename(path))[0])
            
            if not self.output_var.get() or self.output_var.get().startswith("/path/"):
                self.output_var.set(os.path.dirname(path))
            
            # Load scene info
            self.scene_info = self.blender.get_scene_info(path)
            self._apply_scene_info()
    
    def _apply_scene_info(self):
        if not self.scene_info:
            return
        
        info = self.scene_info
        
        # Update resolution
        self.resolution_var.set(f"{info['resolution_x']}x{info['resolution_y']}")
        
        # Update engine
        self.engine_var.set(info["engine"])
        
        # Update format
        self.format_var.set(info["output_format"])
        
        # Update frames
        self.frames_var.set(f"{info['frame_start']}-{info['frame_end']}")
        
        # Update cameras dropdown
        if info["cameras"]:
            self.camera_combo['values'] = info["cameras"]
            if info["active_camera"] in info["cameras"]:
                self.camera_var.set(info["active_camera"])
    
    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_var.set(path)
    
    def submit(self):
        # Validate
        if not self.file_var.get() or self.file_var.get().startswith("/path/"):
            messagebox.showerror("Error", "Please select a scene file")
            return
        if not self.output_var.get() or self.output_var.get().startswith("/path/"):
            messagebox.showerror("Error", "Please select an output directory")
            return
        
        # Parse resolution
        res = self.resolution_var.get()
        w, h = 1920, 1080
        if 'x' in res:
            parts = res.split('x')
            w, h = int(parts[0]), int(parts[1])
        
        # Parse frames
        frames = self.frames_var.get()
        start, end = 1, 250
        if '-' in frames:
            parts = frames.split('-')
            start, end = int(parts[0]), int(parts[1])
        else:
            start = end = int(frames)
        
        # Parse priority
        priority = 3
        pri_str = self.priority_var.get()
        if pri_str:
            priority = int(pri_str[0])
        
        job = RenderJob(
            name=self.name_var.get() or "Untitled",
            file_path=self.file_var.get(),
            output_folder=self.output_var.get(),
            output_name=self.output_name_var.get() or "render_",
            output_format=self.format_var.get(),
            status="paused" if self.paused_var.get() else "queued",
            is_animation=start != end,
            frame_start=start,
            frame_end=end,
            original_start=start,
            res_width=w,
            res_height=h,
            engine=self.engine_var.get(),
            camera=self.camera_var.get(),
            use_gpu=self.gpu_var.get(),
            priority=priority,
            estimated_time=self.estimated_var.get(),
            use_scene_settings=True,
        )
        
        self.on_add(job)
        self.destroy()


# ============================================================================
# SETTINGS PANEL - Figma Styled
# ============================================================================
class SettingsPanel(tk.Toplevel):
    def __init__(self, parent, settings: AppSettings, blender: BlenderInterface, on_save: Callable):
        super().__init__(parent)
        self.settings = settings
        self.blender = blender
        self.on_save = on_save
        
        self.title("Render Settings")
        self.configure(bg=Theme.BG_CARD)
        self.geometry("550x650")
        self.transient(parent)
        self.grab_set()
        
        self.engine_var = tk.StringVar(value=settings.default_engine)
        self.res_var = tk.StringVar(value=settings.default_resolution)
        self.format_var = tk.StringVar(value=settings.default_format)
        self.samples_var = tk.StringVar(value=str(settings.default_samples))
        self.gpu_var = tk.BooleanVar(value=settings.use_gpu)
        self.device_var = tk.StringVar(value=settings.compute_device)
        self.quality_var = tk.StringVar(value=settings.render_quality)
        self.concurrent_var = tk.StringVar(value=str(settings.max_concurrent_jobs))
        
        self.build_ui()
    
    def build_ui(self):
        # Header
        header = tk.Frame(self, bg=Theme.BG_CARD)
        header.pack(fill=tk.X, padx=24, pady=16)
        
        tk.Label(header, text="Render Settings",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XL, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(side=tk.LEFT)
        
        tk.Button(header, text="✕", font=(Theme.FONT_FAMILY, 14),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_SECONDARY, bd=0,
                 activebackground=Theme.BG_HOVER, cursor="hand2",
                 command=self.destroy).pack(side=tk.RIGHT)
        
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill=tk.X)
        
        # Scrollable content
        canvas = tk.Canvas(self, bg=Theme.BG_CARD, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=Theme.BG_CARD, padx=24, pady=20)
        
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw", width=530)
        canvas.configure(yscrollcommand=scroll.set)
        
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Blender Versions section
        tk.Label(form, text="Blender Installations",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_LG, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 12))
        
        versions_frame = tk.Frame(form, bg=Theme.BG_CARD)
        versions_frame.pack(fill=tk.X, pady=(0, 12))
        
        if self.blender.installed_versions:
            for version in sorted(self.blender.installed_versions.keys(), reverse=True):
                row = tk.Frame(versions_frame, bg=Theme.BG_ELEVATED)
                row.pack(fill=tk.X, pady=2)
                
                badge = tk.Label(row, text=f" {version} ",
                               font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM, "bold"),
                               fg="white", bg=Theme.GREEN)
                badge.pack(side=tk.LEFT, padx=8, pady=6)
                
                path = self.blender.installed_versions[version]
                display = path if len(path) < 45 else "..." + path[-42:]
                tk.Label(row, text=display,
                        font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XS),
                        fg=Theme.TEXT_MUTED, bg=Theme.BG_ELEVATED).pack(side=tk.LEFT, pady=6)
        else:
            tk.Label(versions_frame, text="No Blender installations found",
                    font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                    fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w")
        
        # Buttons row
        btn_row = tk.Frame(form, bg=Theme.BG_CARD)
        btn_row.pack(fill=tk.X, pady=(0, 20))
        
        tk.Button(btn_row, text="+ Add Custom",
                 font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                 bg=Theme.BG_ELEVATED, fg=Theme.TEXT_PRIMARY,
                 bd=0, padx=12, pady=6, cursor="hand2",
                 command=self.add_custom).pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Button(btn_row, text="🔄 Rescan",
                 font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                 bg=Theme.BG_ELEVATED, fg=Theme.TEXT_SECONDARY,
                 bd=0, padx=12, pady=6, cursor="hand2",
                 command=self.rescan).pack(side=tk.LEFT)
        
        tk.Frame(form, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(0, 16))
        
        # Default settings
        tk.Label(form, text="Default Job Settings",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_LG, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 12))
        
        self._dropdown(form, "Default Render Engine", self.engine_var,
                      ["Cycles", "Eevee", "Workbench"],
                      "Default rendering engine for new jobs")
        
        self._dropdown(form, "Default Resolution", self.res_var,
                      ["1920x1080", "2560x1440", "3840x2160", "7680x4320"])
        
        self._dropdown(form, "Default Output Format", self.format_var,
                      ["PNG", "JPEG", "OpenEXR", "TIFF"])
        
        self._dropdown(form, "Default Render Quality", self.quality_var,
                      ["Low (Preview)", "Medium (Draft)", "High (Production)", "Ultra (Final)"])
        
        self._dropdown(form, "Max Concurrent Jobs", self.concurrent_var,
                      ["1", "2", "3", "4", "5"],
                      "Maximum number of jobs that can render simultaneously")
        
        self._dropdown(form, "Default Samples Count", self.samples_var,
                      ["32", "64", "128", "256", "512", "1024"],
                      "Higher samples = better quality but longer render times")
        
        tk.Checkbutton(form, text="Enable GPU by Default", variable=self.gpu_var,
                      font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                      fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD,
                      selectcolor=Theme.BG_ELEVATED).pack(anchor="w", pady=(8, 16))
        
        tk.Frame(form, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=(0, 16))
        
        # Buttons
        btns = tk.Frame(form, bg=Theme.BG_CARD)
        btns.pack(fill=tk.X)
        
        tk.Button(btns, text="Cancel",
                 font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE),
                 bg=Theme.BG_ELEVATED, fg=Theme.TEXT_SECONDARY,
                 bd=0, padx=20, pady=12, cursor="hand2",
                 command=self.destroy).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        
        tk.Button(btns, text="💾  Save Settings",
                 font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE, "bold"),
                 bg=Theme.BLUE, fg="white",
                 bd=0, padx=20, pady=12, cursor="hand2",
                 command=self.save).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
    
    def _dropdown(self, parent, label, var, values, hint=None):
        f = tk.Frame(parent, bg=Theme.BG_CARD)
        f.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(f, text=label,
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w", pady=(0, 4))
        
        combo = ttk.Combobox(f, textvariable=var, values=values, state="readonly")
        combo.pack(fill=tk.X)
        
        if hint:
            tk.Label(f, text=hint,
                    font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XS),
                    fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(anchor="w", pady=(4, 0))
    
    def add_custom(self):
        path = filedialog.askopenfilename(
            title="Select Blender Executable",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
        )
        if path:
            version = self.blender.add_custom_path(path)
            if version:
                messagebox.showinfo("Success", f"Added Blender {version}")
                self.destroy()
                SettingsPanel(self.master, self.settings, self.blender, self.on_save)
            else:
                messagebox.showerror("Error", "Could not detect Blender version")
    
    def rescan(self):
        self.blender.scan_installed_versions()
        count = len(self.blender.installed_versions)
        messagebox.showinfo("Scan Complete", f"Found {count} Blender installation(s)")
        self.destroy()
        SettingsPanel(self.master, self.settings, self.blender, self.on_save)
    
    def save(self):
        self.settings.blender_paths = dict(self.blender.installed_versions)
        self.settings.default_engine = self.engine_var.get()
        self.settings.default_resolution = self.res_var.get()
        self.settings.default_format = self.format_var.get()
        self.settings.default_samples = int(self.samples_var.get())
        self.settings.use_gpu = self.gpu_var.get()
        self.settings.render_quality = self.quality_var.get()
        self.settings.max_concurrent_jobs = int(self.concurrent_var.get())
        
        self.on_save(self.settings)
        self.destroy()


# ============================================================================
# MAIN APPLICATION - Figma Layout
# ============================================================================
class RenderManager(tk.Tk):
    CONFIG_FILE = "render_manager_config.json"
    
    def __init__(self):
        super().__init__()
        
        self.title("Render Manager")
        self.geometry("1100x800")
        self.minsize(900, 650)
        self.configure(bg=Theme.BG_BASE)
        
        # Load icon
        self._load_icons()
        
        self.blender = BlenderInterface()
        self.settings = AppSettings(blender_paths=dict(self.blender.installed_versions))
        self.jobs: List[RenderJob] = []
        self.job_cards: Dict[str, JobCard] = {}
        self.current_job: Optional[RenderJob] = None
        self.render_start_time: Optional[datetime] = None
        
        self.configure_styles()
        self.load_config()
        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.process_queue()
    
    def _load_icons(self):
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        for icon_path in [os.path.join(base_dir, "icon.ico"),
                          os.path.join(base_dir, "icon.png")]:
            if os.path.exists(icon_path):
                try:
                    if icon_path.endswith('.ico'):
                        self.iconbitmap(icon_path)
                    else:
                        icon = tk.PhotoImage(file=icon_path)
                        self.iconphoto(True, icon)
                    break
                except:
                    pass
    
    def configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Combobox
        style.configure("TCombobox",
                       fieldbackground=Theme.BG_ELEVATED,
                       background=Theme.BG_ELEVATED,
                       foreground=Theme.TEXT_PRIMARY,
                       arrowcolor=Theme.TEXT_PRIMARY,
                       bordercolor=Theme.BORDER,
                       lightcolor=Theme.BG_ELEVATED,
                       darkcolor=Theme.BG_ELEVATED)
        style.map("TCombobox",
                 fieldbackground=[("readonly", Theme.BG_ELEVATED)],
                 selectbackground=[("readonly", Theme.BG_ELEVATED)],
                 selectforeground=[("readonly", Theme.TEXT_PRIMARY)])
        
        self.option_add("*TCombobox*Listbox.background", Theme.BG_ELEVATED)
        self.option_add("*TCombobox*Listbox.foreground", Theme.TEXT_PRIMARY)
        self.option_add("*TCombobox*Listbox.selectBackground", Theme.BLUE)
        self.option_add("*TCombobox*Listbox.selectForeground", "white")
        
        # Scrollbar
        style.configure("Vertical.TScrollbar",
                       background=Theme.BG_ELEVATED,
                       troughcolor=Theme.BG_BASE,
                       bordercolor=Theme.BG_BASE,
                       arrowcolor=Theme.TEXT_MUTED)
        style.map("Vertical.TScrollbar",
                 background=[("active", Theme.TEXT_MUTED)])
    
    def build_ui(self):
        # ========== HEADER ==========
        header = tk.Frame(self, bg=Theme.BG_CARD)
        header.pack(fill=tk.X)
        
        # Header border
        tk.Frame(header, bg=Theme.BORDER, height=1).pack(side=tk.BOTTOM, fill=tk.X)
        
        header_content = tk.Frame(header, bg=Theme.BG_CARD, padx=24, pady=16)
        header_content.pack(fill=tk.X)
        
        # Left: Logo + Title
        left = tk.Frame(header_content, bg=Theme.BG_CARD)
        left.pack(side=tk.LEFT)
        
        # Logo (gradient blue-purple)
        logo = tk.Canvas(left, width=48, height=48, highlightthickness=0, bg=Theme.BG_CARD)
        logo.pack(side=tk.LEFT, padx=(0, 16))
        
        # Draw gradient logo
        logo.create_rectangle(0, 0, 48, 48, fill="#4f46e5", outline="")
        logo.create_polygon(0, 48, 48, 0, 48, 48, fill="#7c3aed", outline="")
        logo.create_text(24, 24, text="RM", font=(Theme.FONT_FAMILY, 14, "bold"), fill="white")
        
        titles = tk.Frame(left, bg=Theme.BG_CARD)
        titles.pack(side=tk.LEFT)
        
        tk.Label(titles, text="Render Manager",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_2XL, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_CARD).pack(anchor="w")
        
        tk.Label(titles, text="Manage and monitor your render queue",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(anchor="w")
        
        # Right: Buttons
        right = tk.Frame(header_content, bg=Theme.BG_CARD)
        right.pack(side=tk.RIGHT)
        
        settings_btn = tk.Button(right, text="⚙  Settings",
                                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE),
                                bg=Theme.BG_ELEVATED, fg=Theme.TEXT_PRIMARY,
                                bd=0, padx=16, pady=10, cursor="hand2",
                                activebackground=Theme.BG_HOVER,
                                command=self.show_settings)
        settings_btn.pack(side=tk.LEFT, padx=(0, 12))
        
        add_btn = tk.Button(right, text="+  Add Job",
                           font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_BASE, "bold"),
                           bg=Theme.BLUE, fg="white",
                           bd=0, padx=16, pady=10, cursor="hand2",
                           activebackground=Theme.BLUE_HOVER,
                           command=self.show_add_job)
        add_btn.pack(side=tk.LEFT)
        
        # ========== CONTENT ==========
        content = tk.Frame(self, bg=Theme.BG_BASE, padx=24, pady=24)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Stats row
        stats = tk.Frame(content, bg=Theme.BG_BASE)
        stats.pack(fill=tk.X, pady=(0, 24))
        
        self.stat_rendering = StatsCard(stats, "rendering", "Rendering")
        self.stat_rendering.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        
        self.stat_queued = StatsCard(stats, "queued", "Queued")
        self.stat_queued.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        
        self.stat_completed = StatsCard(stats, "completed", "Completed")
        self.stat_completed.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        
        self.stat_failed = StatsCard(stats, "failed", "Failed")
        self.stat_failed.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Queue header
        queue_header = tk.Frame(content, bg=Theme.BG_BASE)
        queue_header.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(queue_header, text="Render Queue",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XL, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_BASE).pack(side=tk.LEFT)
        
        self.queue_count = tk.Label(queue_header, text="0 total jobs",
                                   font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                                   fg=Theme.TEXT_SECONDARY, bg=Theme.BG_BASE)
        self.queue_count.pack(side=tk.RIGHT)
        
        # Queue list (scrollable)
        list_frame = tk.Frame(content, bg=Theme.BG_BASE)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(list_frame, bg=Theme.BG_BASE, highlightthickness=0)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        
        self.queue_frame = tk.Frame(self.canvas, bg=Theme.BG_BASE)
        self.queue_frame.bind("<Configure>", 
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.canvas_win = self.canvas.create_window((0, 0), window=self.queue_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.bind("<Configure>", 
                        lambda e: self.canvas.itemconfig(self.canvas_win, width=e.width))
        
        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # ========== LOG PANEL ==========
        log_panel = tk.Frame(self, bg=Theme.BG_CARD)
        log_panel.pack(fill=tk.X, side=tk.BOTTOM)
        
        log_header = tk.Frame(log_panel, bg=Theme.BG_ELEVATED, padx=12, pady=6)
        log_header.pack(fill=tk.X)
        
        tk.Label(log_header, text="Log",
                font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM, "bold"),
                fg=Theme.TEXT_PRIMARY, bg=Theme.BG_ELEVATED).pack(side=tk.LEFT)
        
        self.log_toggle = tk.Button(log_header, text="▲",
                                   font=(Theme.FONT_FAMILY, 10),
                                   bg=Theme.BG_ELEVATED, fg=Theme.TEXT_SECONDARY,
                                   bd=0, command=self.toggle_log)
        self.log_toggle.pack(side=tk.RIGHT)
        
        tk.Button(log_header, text="Clear",
                 font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_XS),
                 bg=Theme.BG_ELEVATED, fg=Theme.TEXT_MUTED,
                 bd=0, command=self.clear_log).pack(side=tk.RIGHT, padx=(0, 12))
        
        self.log_container = tk.Frame(log_panel, bg=Theme.BG_CARD)
        self.log_container.pack(fill=tk.X)
        
        self.log_text = tk.Text(self.log_container, height=5,
                               bg=Theme.BG_BASE, fg=Theme.TEXT_MUTED,
                               font=("Consolas", 10), bd=0, padx=12, pady=8,
                               state=tk.DISABLED)
        log_scroll = ttk.Scrollbar(self.log_container, orient="vertical",
                                  command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.log_visible = True
        
        # Initial refresh
        self.refresh_queue()
        
        # Log startup info
        if self.blender.installed_versions:
            versions = sorted(self.blender.installed_versions.keys(), reverse=True)
            self.log(f"✓ Found {len(versions)} Blender version(s): {', '.join(versions)}")
        else:
            self.log("⚠ No Blender installations found - open Settings to add")
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
            card = JobCard(self.queue_frame, job, self.handle_action)
            card.pack(fill=tk.X, pady=(0, 12))
            self.job_cards[job.id] = card
        
        if not self.jobs:
            empty = tk.Frame(self.queue_frame, bg=Theme.BG_CARD,
                           highlightbackground=Theme.BORDER, highlightthickness=1)
            empty.pack(fill=tk.X, pady=40)
            
            tk.Label(empty, text="No render jobs",
                    font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_LG),
                    fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD).pack(pady=(40, 8))
            tk.Label(empty, text='Click "Add Job" to start',
                    font=(Theme.FONT_FAMILY, Theme.FONT_SIZE_SM),
                    fg=Theme.TEXT_MUTED, bg=Theme.BG_CARD).pack(pady=(0, 40))
        
        self.update_stats()
    
    def update_stats(self):
        self.stat_rendering.set_value(sum(1 for j in self.jobs if j.status == "rendering"))
        self.stat_queued.set_value(sum(1 for j in self.jobs if j.status == "queued"))
        self.stat_completed.set_value(sum(1 for j in self.jobs if j.status == "completed"))
        self.stat_failed.set_value(sum(1 for j in self.jobs if j.status == "failed"))
        self.queue_count.config(text=f"{len(self.jobs)} total jobs")
    
    def show_add_job(self):
        AddJobModal(self, self.blender, self.settings, self.add_job)
    
    def show_settings(self):
        SettingsPanel(self, self.settings, self.blender, self.save_settings)
    
    def add_job(self, job: RenderJob):
        self.jobs.insert(0, job)
        self.refresh_queue()
        self.save_config()
        self.log(f"Added: {job.name}")
    
    def save_settings(self, settings: AppSettings):
        self.settings = settings
        self.save_config()
    
    def handle_action(self, action: str, job: RenderJob):
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
                self.blender.cancel_render()
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
                self.blender.cancel_render()
                self.current_job = None
            self.jobs = [j for j in self.jobs if j.id != job.id]
            self.refresh_queue()
            self.save_config()
        
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
        
        self.log(f"Starting: {job.name}")
        
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
                if "Saved:" in msg:
                    progress = 99
                elif "Sample" in msg:
                    m = re.search(r'Sample\s+(\d+)/(\d+)', msg)
                    if m:
                        progress = 20 + int((int(m.group(1)) / int(m.group(2))) * 70)
                    else:
                        progress = 50
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
        
        self.blender.start_render(job, start_frame, on_progress, on_complete, on_error, on_log)
    
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
                "blender_paths": self.settings.blender_paths,
                "default_blender": self.settings.default_blender,
                "default_engine": self.settings.default_engine,
                "default_resolution": self.settings.default_resolution,
                "default_format": self.settings.default_format,
                "default_samples": self.settings.default_samples,
                "use_gpu": self.settings.use_gpu,
                "compute_device": self.settings.compute_device,
                "max_concurrent_jobs": self.settings.max_concurrent_jobs,
                "render_quality": self.settings.render_quality,
            },
            "jobs": [{
                "id": j.id, "name": j.name, "file_path": j.file_path,
                "output_folder": j.output_folder, "output_name": j.output_name,
                "output_format": j.output_format,
                "status": j.status if j.status != "rendering" else "paused",
                "progress": j.progress, "is_animation": j.is_animation,
                "frame_start": j.frame_start, "frame_end": j.frame_end,
                "current_frame": j.current_frame, "original_start": j.original_start,
                "res_width": j.res_width, "res_height": j.res_height,
                "res_percentage": j.res_percentage, "engine": j.engine,
                "samples": j.samples, "camera": j.camera,
                "use_gpu": j.use_gpu, "compute_device": j.compute_device,
                "denoiser": j.denoiser, "start_time": j.start_time,
                "end_time": j.end_time, "elapsed_time": j.elapsed_time,
                "accumulated_seconds": j.accumulated_seconds,
                "error_message": j.error_message,
                "use_scene_settings": j.use_scene_settings,
                "use_factory_startup": j.use_factory_startup,
                "blender_version": j.blender_version,
                "file_blender_version": j.file_blender_version,
                "estimated_time": j.estimated_time,
                "priority": j.priority,
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
                
                blender_paths = s.get("blender_paths", {})
                if s.get("blender_path") and not blender_paths:
                    old_path = s.get("blender_path")
                    version = self.blender._get_version_from_exe(old_path)
                    if version:
                        blender_paths[version] = old_path
                
                for version, path in blender_paths.items():
                    if os.path.exists(path):
                        self.blender.installed_versions[version] = path
                
                self.settings = AppSettings(
                    blender_paths=dict(self.blender.installed_versions),
                    default_blender=s.get("default_blender", ""),
                    default_engine=s.get("default_engine", "Cycles"),
                    default_resolution=s.get("default_resolution", "1920x1080"),
                    default_format=s.get("default_format", "PNG"),
                    default_samples=s.get("default_samples", 128),
                    use_gpu=s.get("use_gpu", True),
                    compute_device=s.get("compute_device", "Auto"),
                    max_concurrent_jobs=s.get("max_concurrent_jobs", 1),
                    render_quality=s.get("render_quality", "High"),
                )
                
                for jd in data.get("jobs", []):
                    self.jobs.append(RenderJob(
                        id=jd.get("id", str(uuid.uuid4())[:8]),
                        name=jd.get("name", ""),
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
                        res_percentage=jd.get("res_percentage", 100),
                        engine=jd.get("engine", "Cycles"),
                        samples=jd.get("samples", 128),
                        camera=jd.get("camera", "Scene Default"),
                        use_gpu=jd.get("use_gpu", True),
                        compute_device=jd.get("compute_device", "Auto"),
                        denoiser=jd.get("denoiser", "None"),
                        use_scene_settings=jd.get("use_scene_settings", True),
                        use_factory_startup=jd.get("use_factory_startup", False),
                        blender_version=jd.get("blender_version", "auto"),
                        file_blender_version=jd.get("file_blender_version", ""),
                        start_time=jd.get("start_time"),
                        end_time=jd.get("end_time"),
                        elapsed_time=jd.get("elapsed_time", ""),
                        accumulated_seconds=jd.get("accumulated_seconds", 0),
                        error_message=jd.get("error_message", ""),
                        estimated_time=jd.get("estimated_time", ""),
                        priority=jd.get("priority", 3),
                    ))
            except:
                pass
    
    def on_close(self):
        if self.current_job:
            if messagebox.askyesno("Confirm", "Render in progress. Pause and exit?"):
                self.blender.cancel_render()
                self.current_job.status = "paused"
                self.save_config()
                self.destroy()
        else:
            self.save_config()
            self.destroy()


if __name__ == "__main__":
    app = RenderManager()
    app.mainloop()
