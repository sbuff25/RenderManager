"""
Wane - Blender Engine
=====================

Render engine implementation for Blender.

Supports:
- Cycles, Eevee, and Workbench render engines
- GPU acceleration (OptiX, CUDA, HIP)
- Animation and still frame rendering
- Scene probing for cameras, resolution, frame range
- Pause/resume at any frame
"""

import os
import sys
import re
import gzip
import subprocess
import threading
import tempfile
from typing import Dict, Any, Optional, List

from wane.engines.base import RenderEngine


class BlenderEngine(RenderEngine):
    """
    Blender render engine integration.
    
    Auto-detects installed Blender versions (3.6 - 4.5) and provides
    command-line rendering with progress tracking.
    """
    
    name = "Blender"
    engine_type = "blender"
    file_extensions = [".blend"]
    icon = "view_in_ar"
    color = "#ea7600"
    
    # Standard installation paths to search
    SEARCH_PATHS = [
        r"C:\Program Files\Blender Foundation\Blender 4.5",
        r"C:\Program Files\Blender Foundation\Blender 4.4",
        r"C:\Program Files\Blender Foundation\Blender 4.3",
        r"C:\Program Files\Blender Foundation\Blender 4.2",
        r"C:\Program Files\Blender Foundation\Blender 4.1",
        r"C:\Program Files\Blender Foundation\Blender 4.0",
        r"C:\Program Files\Blender Foundation\Blender 3.6",
    ]
    
    # Output format mapping (display name -> Blender internal name)
    OUTPUT_FORMATS = {
        "PNG": "PNG",
        "JPEG": "JPEG",
        "OpenEXR": "OPEN_EXR",
        "TIFF": "TIFF"
    }
    
    # Compute device options
    COMPUTE_DEVICES = {
        "Auto": "AUTO",
        "OptiX": "OPTIX",
        "CUDA": "CUDA",
        "HIP": "HIP",
        "CPU": "CPU"
    }
    
    def __init__(self):
        super().__init__()
        self.temp_script_path: Optional[str] = None
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        """Scan for installed Blender versions."""
        self.installed_versions = {}
        for base_path in self.SEARCH_PATHS:
            exe_path = os.path.join(base_path, "blender.exe")
            if os.path.exists(exe_path):
                version = self._get_version_from_exe(exe_path)
                if version:
                    self.installed_versions[version] = exe_path
    
    def _get_version_from_exe(self, exe_path: str) -> Optional[str]:
        """Get Blender version by running --version."""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                [exe_path, "--version"],
                capture_output=True,
                timeout=10,
                startupinfo=startupinfo
            )
            stdout = result.stdout.decode('utf-8', errors='replace')
            for line in stdout.split('\n'):
                if line.strip().startswith('Blender '):
                    return line.split()[1]
        except:
            pass
        return None
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """Add a custom Blender executable path."""
        if os.path.exists(path):
            version = self._get_version_from_exe(path)
            if version:
                self.installed_versions[version] = path
                return version
        return None
    
    def get_blend_file_version(self, blend_path: str) -> Optional[str]:
        """Read the Blender version from a .blend file header."""
        try:
            with open(blend_path, 'rb') as f:
                header = f.read(12)
                # Check if gzip compressed
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
        """Get the best Blender executable for a file (uses newest installed)."""
        if self.installed_versions:
            versions = sorted(self.installed_versions.keys(), reverse=True)
            return self.installed_versions[versions[0]]
        return None
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """Probe a .blend file to extract scene information."""
        default_info = {
            "cameras": ["Scene Default"],
            "active_camera": "Scene Default",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "engine": "Cycles",
            "samples": 128,
            "frame_start": 1,
            "frame_end": 250,
        }
        
        blender_exe = self.get_best_blender_for_file(file_path)
        if not blender_exe or not os.path.exists(file_path):
            return default_info
        
        # Python script to run inside Blender to extract scene info
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
            result = subprocess.run(
                [blender_exe, "-b", file_path, "--python", temp_path],
                capture_output=True,
                timeout=60,
                startupinfo=startupinfo
            )
            os.unlink(temp_path)
            
            stdout = result.stdout.decode('utf-8', errors='replace')
            info = default_info.copy()
            in_info = in_cameras = False
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
                    elif line.startswith('ENGINE:'):
                        info["engine"] = line.split(':')[1]
                    elif line.startswith('SAMPLES:'):
                        info["samples"] = int(line.split(':')[1])
                    elif line.startswith('FRAME_START:'):
                        info["frame_start"] = int(line.split(':')[1])
                    elif line.startswith('FRAME_END:'):
                        info["frame_end"] = int(line.split(':')[1])
            
            if cameras:
                info["cameras"] = ["Scene Default"] + cameras
            return info
        except Exception as e:
            print(f"Error probing scene: {e}")
            return default_info
    
    def get_output_formats(self) -> Dict[str, str]:
        """Return available output formats."""
        return self.OUTPUT_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        """Return default render settings."""
        return {
            "render_engine": "Cycles",
            "samples": 128,
            "use_gpu": True,
            "use_scene_settings": True
        }
    
    def start_render(self, job, start_frame, on_progress, on_complete, on_error, on_log=None):
        """Start a Blender render job."""
        blender_exe = self.get_best_blender_for_file(job.file_path)
        if not blender_exe:
            on_error("No Blender found")
            return
        
        self.is_cancelling = False
        os.makedirs(job.output_folder, exist_ok=True)
        
        # Create temp script to set output format
        fmt = self.OUTPUT_FORMATS.get(job.output_format, "PNG")
        script = f"import bpy\nbpy.context.scene.render.image_settings.file_format = '{fmt}'"
        
        script_dir = os.path.dirname(job.file_path) or os.getcwd()
        self.temp_script_path = os.path.join(script_dir, f"_render_{job.id}.py")
        with open(self.temp_script_path, 'w') as f:
            f.write(script)
        
        # Build command
        output_path = os.path.join(job.output_folder, job.output_name)
        cmd = [
            blender_exe, "-b", job.file_path,
            "--python", self.temp_script_path,
            "-o", output_path,
            "-F", fmt,
            "-x", "1"  # Add file extension
        ]
        
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
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    startupinfo=startupinfo
                )
                
                for line_bytes in self.current_process.stdout:
                    if self.is_cancelling:
                        break
                    line = line_bytes.decode('utf-8', errors='replace').strip()
                    if on_log and line:
                        on_log(line)
                    
                    # Parse frame progress
                    frame_match = re.search(r'Fra:(\d+)', line)
                    if frame_match:
                        on_progress(int(frame_match.group(1)), line)
                    elif "Saved:" in line:
                        on_progress(-1, line)  # Signal frame saved
                
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
        """Cancel the current render."""
        self.is_cancelling = True
        if self.current_process:
            try:
                self.current_process.terminate()
            except:
                pass
            self._cleanup()
    
    def _cleanup(self):
        """Clean up temporary files."""
        if self.temp_script_path and os.path.exists(self.temp_script_path):
            try:
                os.unlink(self.temp_script_path)
            except:
                pass
        self.temp_script_path = None
        self.current_process = None
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open a .blend file in Blender."""
        blender_exe = self.get_best_blender_for_file(file_path)
        if blender_exe:
            subprocess.Popen(
                [blender_exe, file_path],
                creationflags=subprocess.DETACHED_PROCESS
            )
