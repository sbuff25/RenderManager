"""
Wain Vantage Engine
===================

Chaos Vantage render engine integration.
Supports .vrscene files (V-Ray scene format) and .vantage config files.

Command-line rendering via vantage_console.exe.
"""

import os
import sys
import json
import subprocess
import threading
import tempfile
import re
from typing import Dict, List, Optional, Any

from wain.engines.base import RenderEngine


class VantageEngine(RenderEngine):
    """Chaos Vantage render engine integration."""
    
    name = "Chaos Vantage"
    engine_type = "vantage"
    file_extensions = [".vrscene", ".vantage"]
    icon = "landscape"  # Material icon fallback
    color = "#77b22a"   # Vantage green
    
    # Search paths for vantage_console.exe
    # Note: vantage_console.exe is required for command-line args, not vantage.exe
    SEARCH_PATHS = [
        # Vantage 2.5+ location
        r"C:\Program Files\Chaos\Vantage\vantage_console.exe",
        # Older versions
        r"C:\Program Files\Chaos Group\Vantage\vantage_console.exe",
        # Alternative paths
        r"C:\Program Files\Chaos\Vantage 3\vantage_console.exe",
        r"C:\Program Files\Chaos\Vantage 2\vantage_console.exe",
    ]
    
    # Output formats supported by Vantage
    OUTPUT_FORMATS = {
        "PNG": "png",
        "JPEG": "jpg",
        "EXR": "exr",
        "TGA": "tga",
    }
    
    # Quality presets
    QUALITY_PRESETS = ["Low", "Medium", "High", "Ultra", "Custom"]
    
    # Denoiser options
    DENOISERS = ["Off", "Native", "NVIDIA AI", "Intel OIDN"]
    
    # Camera types
    CAMERA_TYPES = ["Perspective", "Spherical", "Cube 6x1", "Stereo Cube 6x1", "Stereo Spherical"]
    
    # Render elements available in Vantage
    RENDER_ELEMENTS = [
        {"id": "beauty", "name": "Beauty", "category": "Common"},
        {"id": "diffuse", "name": "Diffuse Filter", "category": "Lighting"},
        {"id": "gi", "name": "Global Illumination", "category": "Lighting"},
        {"id": "lighting", "name": "Lighting", "category": "Lighting"},
        {"id": "reflection", "name": "Reflection", "category": "Lighting"},
        {"id": "refraction", "name": "Refraction", "category": "Lighting"},
        {"id": "specular", "name": "Specular", "category": "Lighting"},
        {"id": "self_illumination", "name": "Self-Illumination", "category": "Lighting"},
        {"id": "atmosphere", "name": "Atmosphere", "category": "Effects"},
        {"id": "background", "name": "Background", "category": "Effects"},
        {"id": "normals", "name": "Bumped Normals", "category": "Geometry"},
        {"id": "z_depth", "name": "Z-Depth", "category": "Geometry"},
        {"id": "material_mask", "name": "Material Mask", "category": "ID"},
        {"id": "object_mask", "name": "Object Mask", "category": "ID"},
    ]
    
    def __init__(self):
        super().__init__()
        self._temp_script_path: Optional[str] = None
        self._progress_file_path: Optional[str] = None
        self._progress_monitor_thread: Optional[threading.Thread] = None
        self._monitoring = False
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        """Scan for installed Chaos Vantage versions."""
        self.installed_versions = {}
        
        for path in self.SEARCH_PATHS:
            if os.path.isfile(path):
                version = self._get_version_from_exe(path)
                if version:
                    self.installed_versions[version] = path
        
        # Also check if vantage.exe exists (for opening files)
        # but we need vantage_console.exe for command-line rendering
        self._gui_exe_path = None
        gui_paths = [
            r"C:\Program Files\Chaos\Vantage\vantage.exe",
            r"C:\Program Files\Chaos Group\Vantage\vantage.exe",
        ]
        for path in gui_paths:
            if os.path.isfile(path):
                self._gui_exe_path = path
                break
    
    def _get_version_from_exe(self, exe_path: str) -> Optional[str]:
        """Get Vantage version from executable."""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            
            result = subprocess.run(
                [exe_path, "-version"],
                capture_output=True,
                timeout=15,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            stdout = result.stdout.decode('utf-8', errors='replace')
            stderr = result.stderr.decode('utf-8', errors='replace')
            output = stdout + stderr
            
            # Look for version pattern (e.g., "3.0.2", "2.6.1")
            version_match = re.search(r'(\d+\.\d+\.\d+)', output)
            if version_match:
                return version_match.group(1)
            
            # Fallback: try to extract from path
            if "Vantage 3" in exe_path:
                return "3.x"
            elif "Vantage 2" in exe_path:
                return "2.x"
            
            return "Unknown"
            
        except subprocess.TimeoutExpired:
            print(f"[Wain] Vantage version check timed out")
            return None
        except Exception as e:
            print(f"[Wain] Error getting Vantage version: {e}")
            return None
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """Add a custom Vantage executable path."""
        if os.path.isfile(path) and path.lower().endswith('.exe'):
            # Prefer vantage_console.exe
            if 'console' not in path.lower():
                # Try to find vantage_console.exe in same directory
                console_path = os.path.join(os.path.dirname(path), 'vantage_console.exe')
                if os.path.isfile(console_path):
                    path = console_path
            
            version = self._get_version_from_exe(path)
            if version:
                self.installed_versions[version] = path
                return version
        return None
    
    def get_best_vantage(self) -> Optional[str]:
        """Get path to best available Vantage installation."""
        if not self.installed_versions:
            return None
        # Return newest version
        versions = sorted(self.installed_versions.keys(), reverse=True)
        return self.installed_versions[versions[0]]
    
    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "quality_preset": "High",
            "samples": 256,
            "denoiser": "NVIDIA AI",
            "use_gi": True,
            "gi_bounces": 3,
            "render_elements": ["beauty"],
        }
    
    def get_file_dialog_filter(self) -> List[tuple]:
        return [
            ("V-Ray Scene Files", "*.vrscene"),
            ("Vantage Config Files", "*.vantage"),
        ]
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open a scene file in Vantage GUI."""
        # Prefer GUI exe for opening files
        exe_path = self._gui_exe_path or self.get_best_vantage()
        if exe_path:
            # Use vantage.exe (not console) for GUI
            gui_exe = exe_path.replace('vantage_console.exe', 'vantage.exe')
            if os.path.exists(gui_exe):
                exe_path = gui_exe
        
        if exe_path and os.path.exists(file_path):
            try:
                subprocess.Popen(
                    [exe_path, f"-sceneFile={file_path}"],
                    creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0
                )
            except Exception as e:
                print(f"[Wain] Failed to open in Vantage: {e}")
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get scene information from a .vrscene or .vantage file.
        
        Note: .vrscene files are text-based and can be partially parsed.
        .vantage files are Vantage project files with saved settings.
        """
        default_info = {
            "cameras": ["Default Camera"],
            "active_camera": "Default Camera",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "frame_start": 1,
            "frame_end": 1,
            "total_frames": 1,
            "has_animation": False,
            "quality_preset": "High",
            "samples": 256,
        }
        
        if not os.path.exists(file_path):
            return default_info
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".vrscene":
            return self._parse_vrscene(file_path, default_info)
        elif ext == ".vantage":
            return self._parse_vantage_file(file_path, default_info)
        
        return default_info
    
    def _parse_vrscene(self, file_path: str, default_info: Dict) -> Dict[str, Any]:
        """
        Parse a .vrscene file to extract basic scene info.
        
        .vrscene is a text-based format with V-Ray scene data.
        We can extract camera names, resolution, frame range, etc.
        """
        info = default_info.copy()
        cameras = []
        
        try:
            # .vrscene files can be large, read in chunks
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(500000)  # Read first 500KB for basic info
            
            # Look for camera definitions
            # Pattern: CameraPhysical camera_name { ... } or RenderView view_name { ... }
            camera_patterns = [
                r'CameraPhysical\s+(\w+)\s*\{',
                r'CameraDefault\s+(\w+)\s*\{',
                r'RenderView\s+(\w+)\s*\{',
            ]
            
            for pattern in camera_patterns:
                matches = re.findall(pattern, content)
                cameras.extend(matches)
            
            if cameras:
                info["cameras"] = list(set(cameras))  # Remove duplicates
                info["active_camera"] = cameras[0]
            
            # Look for resolution settings
            # SettingsOutput { img_width=1920; img_height=1080; ... }
            width_match = re.search(r'img_width\s*=\s*(\d+)', content)
            height_match = re.search(r'img_height\s*=\s*(\d+)', content)
            
            if width_match:
                info["resolution_x"] = int(width_match.group(1))
            if height_match:
                info["resolution_y"] = int(height_match.group(1))
            
            # Look for frame range
            # SettingsOutput { ... anim_start=1; anim_end=100; ... }
            start_match = re.search(r'anim_start\s*=\s*(\d+)', content)
            end_match = re.search(r'anim_end\s*=\s*(\d+)', content)
            
            if start_match:
                info["frame_start"] = int(start_match.group(1))
            if end_match:
                info["frame_end"] = int(end_match.group(1))
                if info["frame_end"] > info["frame_start"]:
                    info["has_animation"] = True
                    info["total_frames"] = info["frame_end"] - info["frame_start"] + 1
            
            print(f"[Wain] Parsed .vrscene: {len(cameras)} cameras, {info['resolution_x']}x{info['resolution_y']}")
            
        except Exception as e:
            print(f"[Wain] Error parsing .vrscene: {e}")
        
        return info
    
    def _parse_vantage_file(self, file_path: str, default_info: Dict) -> Dict[str, Any]:
        """
        Parse a .vantage file for scene info.
        
        .vantage files store Vantage project settings including render queue,
        camera setups, scene states, etc.
        """
        info = default_info.copy()
        
        try:
            # .vantage files may be binary or JSON-based depending on version
            # Try reading as text first
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(100000)
            
            # Try to parse as JSON (newer format)
            try:
                data = json.loads(content)
                if 'resolution' in data:
                    info["resolution_x"] = data['resolution'].get('width', 1920)
                    info["resolution_y"] = data['resolution'].get('height', 1080)
                if 'cameras' in data:
                    info["cameras"] = data['cameras']
            except json.JSONDecodeError:
                # Not JSON, try regex patterns
                pass
            
        except Exception as e:
            print(f"[Wain] Error parsing .vantage file: {e}")
        
        return info
    
    def start_render(self, job, start_frame: int, on_progress, on_complete, on_error, on_log=None):
        """
        Start rendering a job with Chaos Vantage.
        
        This attempts to use command-line rendering via vantage_console.exe.
        Note: Command-line output options may be limited in recent versions.
        """
        vantage_exe = self.get_best_vantage()
        if not vantage_exe:
            on_error("No Chaos Vantage installation found")
            return
        
        if not os.path.exists(job.file_path):
            on_error(f"Scene file not found: {job.file_path}")
            return
        
        self.is_cancelling = False
        os.makedirs(job.output_folder, exist_ok=True)
        
        if on_log:
            on_log(f"[Vantage] Starting render...")
            on_log(f"[Vantage] Executable: {vantage_exe}")
            on_log(f"[Vantage] Scene: {job.file_path}")
            on_log(f"[Vantage] Output: {job.output_folder}")
            on_log(f"[Vantage] Resolution: {job.res_width}x{job.res_height}")
        
        # Build command line
        cmd = [vantage_exe]
        
        # Add scene file
        cmd.append(f"-sceneFile={job.file_path}")
        
        # Add camera if specified
        if job.camera and job.camera != "Default Camera":
            cmd.append(f"-camera={job.camera}")
        
        # Note: Additional output parameters may not be available in v3.0+
        # We'll test what works and log the results
        
        if on_log:
            on_log(f"[Vantage] Command: {' '.join(cmd)}")
            on_log(f"[Vantage] NOTE: Testing command-line rendering capabilities...")
        
        def render_thread():
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    startupinfo=startupinfo,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                if on_log:
                    on_log(f"[Vantage] Process started, PID: {self.current_process.pid}")
                
                # Read output
                for line_bytes in self.current_process.stdout:
                    if self.is_cancelling:
                        break
                    
                    try:
                        line = line_bytes.decode('utf-8', errors='replace').strip()
                        if line and on_log:
                            on_log(f"[Vantage] {line}")
                        
                        # Try to parse progress from output
                        # Patterns may vary by Vantage version
                        progress_match = re.search(r'(\d+)%', line)
                        if progress_match:
                            progress = int(progress_match.group(1))
                            job.progress = min(progress, 99)
                            on_progress(progress, line)
                        
                        frame_match = re.search(r'[Ff]rame\s*(\d+)', line)
                        if frame_match:
                            frame = int(frame_match.group(1))
                            job.current_frame = frame
                            on_progress(frame, line)
                            
                    except Exception as e:
                        if on_log:
                            on_log(f"[Vantage] Parse error: {e}")
                
                return_code = self.current_process.wait()
                
                if self.is_cancelling:
                    if on_log:
                        on_log("[Vantage] Render cancelled by user")
                    return
                
                if return_code == 0:
                    job.progress = 100
                    on_complete()
                else:
                    on_error(f"Vantage exited with code {return_code}")
                    
            except Exception as e:
                if not self.is_cancelling:
                    on_error(str(e))
            finally:
                self._cleanup()
        
        threading.Thread(target=render_thread, daemon=True).start()
    
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
    
    def _stop_progress_monitor(self):
        """Stop the progress monitoring thread."""
        self._monitoring = False
        if self._progress_monitor_thread:
            self._progress_monitor_thread.join(timeout=2)
            self._progress_monitor_thread = None
    
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
    
    def test_command_line_options(self, on_log=None) -> Dict[str, Any]:
        """
        Test which command-line options are available in this Vantage version.
        
        Returns a dict with available options and version info.
        """
        vantage_exe = self.get_best_vantage()
        if not vantage_exe:
            return {"error": "No Vantage installation found"}
        
        result = {
            "version": None,
            "help_output": "",
            "available_options": [],
        }
        
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # Get help output
            proc = subprocess.run(
                [vantage_exe, "-help"],
                capture_output=True,
                timeout=30,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            output = proc.stdout.decode('utf-8', errors='replace')
            output += proc.stderr.decode('utf-8', errors='replace')
            
            result["help_output"] = output
            
            if on_log:
                on_log(f"[Vantage] Help output:\n{output}")
            
            # Parse available options
            option_patterns = [
                r'-(\w+)',
                r'--(\w+)',
            ]
            
            for pattern in option_patterns:
                matches = re.findall(pattern, output)
                result["available_options"].extend(matches)
            
            result["available_options"] = list(set(result["available_options"]))
            
        except Exception as e:
            result["error"] = str(e)
            if on_log:
                on_log(f"[Vantage] Error testing options: {e}")
        
        return result
