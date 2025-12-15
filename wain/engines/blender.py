"""
Wain - Blender Engine
=====================

Render engine implementation for Blender.
v2.7.0 - Fixed denoiser value normalization (OPTIX -> OptiX)

Note on "double rendering": At high resolutions (e.g. 3840x2048), Blender
splits the frame into multiple tiles and renders them sequentially. This
is normal GPU rendering behavior, not a bug. The log will show:
  "Rendered 0/2 Tiles, Sample 1024/1024"
  "Rendered 1/2 Tiles, Sample 1/1024"
This means tile 1 is starting, not the frame re-rendering.
"""

import os
import sys
import re
import subprocess
import threading
import tempfile
from typing import Dict, Any, Optional, List

from wain.engines.base import RenderEngine
from wain.config import BLENDER_DENOISER_FROM_INTERNAL


class BlenderEngine(RenderEngine):
    """Blender render engine integration."""
    
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
            "use_denoising": True, "denoiser": "OptiX",  # Use UI-friendly name
            "use_compositing": True, "use_sequencer": False,  # Default sequencer OFF
            "has_compositor_denoise": False,
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
    print(f"USE_DENOISING:{scene.cycles.use_denoising}")
    print(f"DENOISER:{scene.cycles.denoiser}")
else:
    print("SAMPLES:128")
    print("USE_DENOISING:False")
    print("DENOISER:OPTIX")
print(f"FRAME_START:{scene.frame_start}")
print(f"FRAME_END:{scene.frame_end}")
print(f"USE_COMPOSITING:{render.use_compositing}")
print(f"USE_SEQUENCER:{render.use_sequencer}")

# Check for compositor denoise node
has_comp_denoise = False
if scene.node_tree and scene.node_tree.nodes:
    for node in scene.node_tree.nodes:
        if node.type == 'DENOISE' and not node.mute:
            has_comp_denoise = True
            break
print(f"HAS_COMPOSITOR_DENOISE:{has_comp_denoise}")
print("INFO_END")
'''
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                temp_path = f.name
            
            print(f"[Wain] Probing Blender scene: {file_path}")
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run([blender_exe, "-b", file_path, "--python", temp_path], capture_output=True, timeout=60, startupinfo=startupinfo)
            os.unlink(temp_path)
            
            print(f"[Wain] Blender exited with code: {result.returncode}")
            
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
                    elif line.startswith('USE_DENOISING:'): info["use_denoising"] = line.split(':')[1] == 'True'
                    elif line.startswith('DENOISER:'):
                        # CRITICAL FIX: Convert internal Blender value (OPTIX) to UI-friendly name (OptiX)
                        internal_value = line.split(':')[1].strip()
                        info["denoiser"] = BLENDER_DENOISER_FROM_INTERNAL.get(internal_value, 'OptiX')
                    elif line.startswith('FRAME_START:'): info["frame_start"] = int(line.split(':')[1])
                    elif line.startswith('FRAME_END:'): info["frame_end"] = int(line.split(':')[1])
                    elif line.startswith('USE_COMPOSITING:'): info["use_compositing"] = line.split(':')[1] == 'True'
                    elif line.startswith('USE_SEQUENCER:'): info["use_sequencer"] = line.split(':')[1] == 'True'
                    elif line.startswith('HAS_COMPOSITOR_DENOISE:'): info["has_compositor_denoise"] = line.split(':')[1] == 'True'
            
            if cameras: info["cameras"] = ["Scene Default"] + cameras
            print(f"[Wain] Blender probe results: {info}")
            return info
        except Exception as e:
            print(f"[Wain] Error probing Blender scene: {e}")
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
        
        if on_log:
            on_log(f"Resolution: {job.res_width}x{job.res_height}")
            on_log(f"Overwrite existing: {job.overwrite_existing}")
        
        # For single frame renders, check if output already exists
        if not job.is_animation and not job.overwrite_existing:
            ext_map = {"PNG": "png", "JPEG": "jpg", "OPEN_EXR": "exr", "TIFF": "tiff"}
            ext = ext_map.get(self.OUTPUT_FORMATS.get(job.output_format, "PNG"), "png")
            potential_output = os.path.join(job.output_folder, f"{job.output_name}{job.frame_start:04d}.{ext}")
            if os.path.exists(potential_output):
                if on_log:
                    on_log(f"Skipping render - file exists: {potential_output}")
                on_complete()
                return
        
        fmt = self.OUTPUT_FORMATS.get(job.output_format, "PNG")
        
        # Base script that sets format and resolution
        base_script = f'''import bpy

# Set output format
bpy.context.scene.render.image_settings.file_format = '{fmt}'

# Set resolution from Wain job settings
bpy.context.scene.render.resolution_x = {job.res_width}
bpy.context.scene.render.resolution_y = {job.res_height}
bpy.context.scene.render.resolution_percentage = 100

print(f"[Wain] Resolution set to {{bpy.context.scene.render.resolution_x}}x{{bpy.context.scene.render.resolution_y}}")
'''
        
        # Generate script that optionally skips existing frames
        if job.is_animation and not job.overwrite_existing:
            ext_map = {"PNG": "png", "JPEG": "jpg", "OPEN_EXR": "exr", "TIFF": "tiff"}
            ext = ext_map.get(fmt, "png")
            output_base = os.path.join(job.output_folder, job.output_name).replace('\\', '\\\\')
            
            script = base_script + f'''
import os

# Skip existing frames handler
def skip_existing_handler(scene, depsgraph):
    frame = scene.frame_current
    output_path = f"{output_base}{{frame:04d}}.{ext}"
    if os.path.exists(output_path):
        print(f"[Wain] Skipping frame {{frame}} - already exists")
        bpy.context.scene.render.use_lock_interface = False
        raise Exception("SKIP_FRAME")
'''
        else:
            script = base_script
        
        script_dir = os.path.dirname(job.file_path) or os.getcwd()
        self.temp_script_path = os.path.join(script_dir, f"_wain_render_{job.id}.py")
        with open(self.temp_script_path, 'w') as f:
            f.write(script)
        
        output_path = os.path.join(job.output_folder, job.output_name)
        cmd = [blender_exe, "-b", job.file_path, "--python", self.temp_script_path, "-o", output_path, "-F", fmt, "-x", "1"]
        
        if job.is_animation:
            cmd.extend(["-s", str(start_frame), "-e", str(job.frame_end), "-a"])
        else:
            cmd.extend(["-f", str(job.frame_start)])
        
        if on_log: on_log(f"[v2.8.3] Command: {' '.join(cmd)}")
        
        def render_thread():
            """Render in background thread with robust encoding handling."""
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                # Force UTF-8 encoding to handle Unicode output from addons
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                env['PYTHONLEGACYWINDOWSSTDIO'] = '0'
                
                self.current_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    startupinfo=startupinfo,
                    env=env
                )
                
                # Read stdout as binary and decode ourselves to avoid encoding issues
                while True:
                    if self.is_cancelling:
                        break
                    
                    try:
                        line_bytes = self.current_process.stdout.readline()
                        if not line_bytes:
                            break
                        
                        # Decode bytes to string - use errors='replace' to handle any encoding
                        try:
                            line = line_bytes.decode('utf-8', errors='replace')
                        except Exception:
                            try:
                                line = line_bytes.decode('latin-1', errors='replace')
                            except Exception:
                                line = str(line_bytes)
                        
                        line = line.strip()
                        
                        # AGGRESSIVELY sanitize to ASCII - this is critical for Windows
                        # Convert ALL non-printable-ASCII characters to '?'
                        safe_chars = []
                        for c in line:
                            try:
                                code = ord(c)
                                if 32 <= code < 127:
                                    safe_chars.append(c)
                                else:
                                    safe_chars.append('?')
                            except Exception:
                                safe_chars.append('?')
                        safe_line = ''.join(safe_chars)
                        
                        # Log the sanitized line
                        if on_log and safe_line:
                            try:
                                on_log(safe_line)
                            except Exception:
                                pass  # Skip if logging fails
                        
                        # Parse progress info from original line (may contain unicode)
                        try:
                            frame_match = re.search(r'Fra:(\d+)', line)
                            if frame_match:
                                on_progress(int(frame_match.group(1)), safe_line)
                            elif "Saved:" in line:
                                on_progress(-1, safe_line)
                        except Exception:
                            pass  # Skip progress parsing errors
                            
                    except Exception:
                        # Skip ANY problematic lines - never fail the render
                        continue
                
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
                    # Sanitize error message to ASCII
                    try:
                        err_msg = str(e)
                        safe_err = ''.join(c if 32 <= ord(c) < 127 else '?' for c in err_msg)
                    except Exception:
                        safe_err = "Unknown error"
                    on_error(safe_err)
        
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
