"""
Wain Marmoset Engine
====================

Marmoset Toolbag render engine integration.
"""

import os
import sys
import json
import subprocess
import threading
import tempfile
from typing import Dict, List, Optional, Any

from wain.engines.base import RenderEngine


class MarmosetEngine(RenderEngine):
    """Marmoset Toolbag render engine integration."""
    
    name = "Marmoset Toolbag"
    engine_type = "marmoset"
    file_extensions = [".tbscene"]
    icon = "diamond"
    color = "#ef0343"
    
    SEARCH_PATHS = [
        r"C:\Program Files\Marmoset\Toolbag 5\toolbag.exe",
        r"C:\Program Files\Marmoset\Toolbag 4\toolbag.exe",
        r"C:\Program Files (x86)\Marmoset\Toolbag 5\toolbag.exe",
        r"C:\Program Files (x86)\Marmoset\Toolbag 4\toolbag.exe",
    ]
    
    OUTPUT_FORMATS = {
        "PNG": "PNG", "JPEG": "JPEG", "TGA": "TGA", "PSD": "PSD",
        "PSD (16-bit)": "PSD (16-bit)", "EXR (16-bit)": "EXR (16-bit)", "EXR (32-bit)": "EXR (32-bit)",
    }
    
    def __init__(self):
        super().__init__()
        self._temp_script_path: Optional[str] = None
        self._progress_file_path: Optional[str] = None
        self._monitoring = False
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        self.installed_versions = {}
        for path in self.SEARCH_PATHS:
            if os.path.isfile(path):
                version = "5.0" if "Toolbag 5" in path else "4.0" if "Toolbag 4" in path else "Unknown"
                self.installed_versions[version] = path
    
    def add_custom_path(self, path: str) -> Optional[str]:
        if os.path.isfile(path) and path.lower().endswith('.exe'):
            version = "Custom"
            self.installed_versions[version] = path
            return version
        return None
    
    def get_best_toolbag(self) -> Optional[str]:
        if not self.installed_versions:
            return None
        return self.installed_versions[sorted(self.installed_versions.keys(), reverse=True)[0]]
    
    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "render_type": "still", "renderer": "Ray Tracing", "samples": 256,
            "shadow_quality": "High", "use_transparency": False, "denoise_mode": "gpu",
            "turntable_frames": 120, "render_passes": ["beauty"],
        }
    
    def get_file_dialog_filter(self) -> List[tuple]:
        return [("Marmoset Toolbag Scenes", "*.tbscene")]
    
    def open_file_in_app(self, file_path: str, version: str = None):
        toolbag_exe = self.get_best_toolbag()
        if toolbag_exe and os.path.exists(file_path):
            try:
                subprocess.Popen([toolbag_exe, file_path], creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0)
            except Exception as e:
                print(f"Failed to open in Toolbag: {e}")
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        return {
            "cameras": ["Main Camera"], "active_camera": "Main Camera",
            "resolution_x": 1920, "resolution_y": 1080, "renderer": "Ray Tracing",
            "samples": 256, "frame_start": 1, "frame_end": 1, "total_frames": 1,
            "has_animation": False, "has_turntable": False,
        }
    
    def start_render(self, job, start_frame: int, on_progress, on_complete, on_error, on_log=None):
        toolbag_exe = self.get_best_toolbag()
        if not toolbag_exe:
            on_error("No Marmoset Toolbag installation found")
            return
        
        if not os.path.exists(job.file_path):
            on_error(f"Scene file not found: {job.file_path}")
            return
        
        self.is_cancelling = False
        os.makedirs(job.output_folder, exist_ok=True)
        
        script_dir = os.path.dirname(job.file_path) or tempfile.gettempdir()
        self._temp_script_path = os.path.join(script_dir, f"_wain_render_{job.id}.py")
        self._progress_file_path = os.path.join(script_dir, f"_wain_progress_{job.id}.json")
        
        script_code = self._generate_render_script(job, start_frame)
        
        try:
            with open(self._temp_script_path, 'w', encoding='utf-8') as f:
                f.write(script_code)
            
            def render_thread():
                try:
                    startupinfo = subprocess.STARTUPINFO() if sys.platform == 'win32' else None
                    creation_flags = 0x08000000 if sys.platform == 'win32' else 0
                    if startupinfo:
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = 6
                    
                    cmd = [toolbag_exe, '-hide', self._temp_script_path]
                    
                    self.current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                           startupinfo=startupinfo, creationflags=creation_flags)
                    
                    if on_log:
                        on_log(f"Started Toolbag PID: {self.current_process.pid}")
                    
                    self._monitoring = True
                    while self._monitoring and not self.is_cancelling:
                        if self.current_process.poll() is not None:
                            break
                        
                        progress_data = self._read_progress_file()
                        if progress_data:
                            status = progress_data.get("status", "")
                            progress_pct = progress_data.get("progress", 0)
                            current = progress_data.get("current", 0)
                            
                            job.progress = min(progress_pct, 99)
                            job.current_frame = current
                            on_progress(current, f"Rendering...")
                            
                            if status == "complete":
                                break
                        
                        import time
                        time.sleep(0.3)
                    
                    return_code = self.current_process.wait()
                    
                    if self.is_cancelling:
                        return
                    
                    final_status = self._read_progress_file()
                    if final_status.get("status") == "complete" or return_code == 0:
                        on_complete()
                    else:
                        on_error(final_status.get("error", f"Toolbag exited with code {return_code}"))
                    
                except Exception as e:
                    if not self.is_cancelling:
                        on_error(str(e))
                finally:
                    self._cleanup()
            
            threading.Thread(target=render_thread, daemon=True).start()
            
        except Exception as e:
            self._cleanup()
            on_error(f"Failed to start render: {e}")
    
    def _generate_render_script(self, job, start_frame: int) -> str:
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        
        return f'''import mset
import json
import os

def update_progress(status, progress=0, current=0, total=0, error=""):
    try:
        with open(r"{progress_path}", 'w') as f:
            json.dump({{"status": status, "progress": progress, "current": current, "total": total, "error": error}}, f)
    except:
        pass

def render():
    try:
        update_progress("loading", 0, 0, 1)
        mset.loadScene(r"{scene_path}")
        
        output_path = os.path.join(r"{output_folder}", "{job.output_name}.png")
        os.makedirs(r"{output_folder}", exist_ok=True)
        
        update_progress("rendering", 50, 1, 1)
        mset.renderCamera(output_path, {job.res_width}, {job.res_height}, {samples}, {str(use_transparency)})
        
        update_progress("complete", 100, 1, 1)
    except Exception as e:
        update_progress("error", 0, 0, 0, str(e))
    
    mset.quit()

render()
'''
    
    def _read_progress_file(self) -> Dict[str, Any]:
        if not self._progress_file_path or not os.path.exists(self._progress_file_path):
            return {}
        try:
            with open(self._progress_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def cancel_render(self):
        self.is_cancelling = True
        self._monitoring = False
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except:
                try: self.current_process.kill()
                except: pass
        self._cleanup()
    
    def _cleanup(self):
        for path in [self._temp_script_path, self._progress_file_path]:
            if path and os.path.exists(path):
                try: os.unlink(path)
                except: pass
        self._temp_script_path = None
        self._progress_file_path = None
        self.current_process = None
