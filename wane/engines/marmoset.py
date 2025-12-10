"""
Wane Marmoset Engine - AGGRESSIVE PASS CONTROL
==============================================

This version tries multiple aggressive approaches to control render passes:
1. Disable passes via .enabled property
2. Try to DELETE unwanted passes from the scene
3. Try mset.deleteObject() on pass objects
4. Fall back to rendering frame-by-frame with renderCamera() if needed
"""

import os
import sys
import json
import subprocess
import threading
import tempfile
from typing import Dict, List, Optional, Any

from wane.engines.base import RenderEngine


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
    
    VIDEO_FORMATS = {"MP4": "MPEG4", "PNG Sequence": "PNG", "JPEG Sequence": "JPEG", "TGA Sequence": "TGA"}
    RENDERERS = ["Ray Tracing", "Hybrid", "Raster"]
    SHADOW_QUALITY = ["Low", "High", "Mega"]
    DENOISE_MODES = ["off", "cpu", "gpu"]
    DENOISE_QUALITY = ["low", "medium", "high"]
    RENDER_TYPES = {"still": "Still Image", "turntable": "Turntable (360 deg)", "animation": "Animation"}
    
    RENDER_PASSES = [
        {"id": "beauty", "name": "Final Composite (Beauty)", "pass": "", "category": "Common"},
        {"id": "wireframe", "name": "Wireframe", "pass": "Wireframe", "category": "Common"},
        {"id": "alpha_mask", "name": "Alpha Mask", "pass": "Alpha Mask", "category": "Geometry"},
        {"id": "depth", "name": "Depth", "pass": "Depth", "category": "Geometry"},
        {"id": "incidence", "name": "Incidence", "pass": "Incidence", "category": "Geometry"},
        {"id": "normals", "name": "Normals", "pass": "Normals", "category": "Geometry"},
        {"id": "position", "name": "Position", "pass": "Position", "category": "Geometry"},
        {"id": "material_id", "name": "Material ID", "pass": "Material ID", "category": "ID"},
        {"id": "object_id", "name": "Object ID", "pass": "Object ID", "category": "ID"},
        {"id": "ambient_occlusion", "name": "Ambient Occlusion", "pass": "Ambient Occlusion", "category": "Lighting"},
        {"id": "lighting_direct", "name": "Lighting (Direct)", "pass": "Lighting (Direct)", "category": "Lighting"},
        {"id": "lighting_indirect", "name": "Lighting (Indirect)", "pass": "Lighting (Indirect)", "category": "Lighting"},
        {"id": "diffuse_complete", "name": "Diffuse (Complete)", "pass": "Diffuse (Complete)", "category": "Lighting"},
        {"id": "diffuse_direct", "name": "Diffuse (Direct)", "pass": "Diffuse (Direct)", "category": "Lighting"},
        {"id": "diffuse_indirect", "name": "Diffuse (Indirect)", "pass": "Diffuse (Indirect)", "category": "Lighting"},
        {"id": "specular_complete", "name": "Specular (Complete)", "pass": "Specular (Complete)", "category": "Lighting"},
        {"id": "specular_direct", "name": "Specular (Direct)", "pass": "Specular (Direct)", "category": "Lighting"},
        {"id": "specular_indirect", "name": "Specular (Indirect)", "pass": "Specular (Indirect)", "category": "Lighting"},
        {"id": "albedo", "name": "Albedo", "pass": "Albedo", "category": "Material"},
        {"id": "displacement", "name": "Displacement", "pass": "Displacement", "category": "Material"},
        {"id": "emissive", "name": "Emissive", "pass": "Emissive", "category": "Material"},
        {"id": "gloss", "name": "Gloss", "pass": "Gloss", "category": "Material"},
        {"id": "metalness", "name": "Metalness", "pass": "Metalness", "category": "Material"},
        {"id": "reflectivity", "name": "Reflectivity", "pass": "Reflectivity", "category": "Material"},
        {"id": "roughness", "name": "Roughness", "pass": "Roughness", "category": "Material"},
        {"id": "transparency", "name": "Transparency", "pass": "Transparency", "category": "Material"},
    ]
    
    def __init__(self):
        super().__init__()
        self._temp_script_path: Optional[str] = None
        self._progress_file_path: Optional[str] = None
        self._progress_monitor_thread: Optional[threading.Thread] = None
        self._monitoring = False
        self._last_message = ""
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        self.installed_versions = {}
        for path in self.SEARCH_PATHS:
            if os.path.isfile(path):
                version = "5.0" if "Toolbag 5" in path else "4.0" if "Toolbag 4" in path else "Unknown"
                self.installed_versions[version] = path
    
    def add_custom_path(self, path: str) -> Optional[str]:
        if os.path.isfile(path) and path.lower().endswith('.exe'):
            version = "5.x (Custom)" if "5" in os.path.basename(os.path.dirname(path)) else "4.x (Custom)" if "4" in os.path.basename(os.path.dirname(path)) else "Custom"
            self.installed_versions[version] = path
            return version
        return None
    
    def get_best_toolbag(self) -> Optional[str]:
        if not self.installed_versions:
            return None
        return self.installed_versions[sorted(self.installed_versions.keys(), reverse=True)[0]]
    
    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS
    
    def get_video_formats(self) -> Dict[str, str]:
        return self.VIDEO_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "render_type": "still", "renderer": "Ray Tracing", "samples": 256,
            "shadow_quality": "High", "use_transparency": False, "denoise_mode": "gpu",
            "denoise_quality": "high", "denoise_strength": 1.0, "ray_trace_bounces": 4,
            "turntable_frames": 120, "turntable_clockwise": True, "video_format": "PNG Sequence",
            "render_passes": ["beauty"],
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
        default_info = {
            "cameras": ["Main Camera"], "active_camera": "Main Camera",
            "resolution_x": 1920, "resolution_y": 1080, "renderer": "Ray Tracing",
            "samples": 256, "frame_start": 1, "frame_end": 1, "total_frames": 1,
            "has_animation": False, "has_turntable": False,
        }
        
        toolbag_exe = self.get_best_toolbag()
        if not toolbag_exe or not os.path.exists(file_path):
            return default_info
        
        script_dir = os.path.dirname(file_path) or tempfile.gettempdir()
        probe_script = os.path.join(script_dir, "_wane_probe.py")
        output_json = os.path.join(script_dir, "_wane_probe_result.json")
        
        probe_code = self._generate_probe_script(file_path, output_json)
        
        try:
            with open(probe_script, 'w', encoding='utf-8') as f:
                f.write(probe_code)
            
            startupinfo = subprocess.STARTUPINFO() if sys.platform == 'win32' else None
            if startupinfo:
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            subprocess.run([toolbag_exe, probe_script], capture_output=True, timeout=60, startupinfo=startupinfo)
            
            if os.path.exists(output_json):
                with open(output_json, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return default_info
        except:
            return default_info
        finally:
            for f in [probe_script, output_json]:
                if os.path.exists(f):
                    try: os.unlink(f)
                    except: pass
    
    def _generate_probe_script(self, scene_path: str, output_path: str) -> str:
        scene_path_escaped = scene_path.replace('\\', '\\\\')
        output_path_escaped = output_path.replace('\\', '\\\\')
        
        return f'''import mset
import json
import sys

def log(msg):
    print(f"[Probe] {{msg}}")
    sys.stdout.flush()

def probe_scene():
    result = {{"cameras": [], "active_camera": "Main Camera", "resolution_x": 1920, "resolution_y": 1080,
               "renderer": "Ray Tracing", "samples": 256, "frame_start": 1, "frame_end": 1,
               "total_frames": 1, "has_animation": False, "has_turntable": False,
               "available_render_passes": ["Full Quality"]}}
    
    try:
        log("Loading scene...")
        mset.loadScene(r"{scene_path_escaped}")
        log("Scene loaded")
        
        cameras = []
        for obj in mset.getAllObjects():
            obj_name = obj.name if hasattr(obj, 'name') else str(obj)
            obj_type = type(obj).__name__
            if hasattr(obj, 'fov') or 'Camera' in obj_type:
                cameras.append(obj_name)
            if 'Turntable' in obj_type and hasattr(obj, 'enabled') and obj.enabled:
                result["has_turntable"] = True
                if hasattr(obj, 'spinRate'):
                    result["turntable_spin_rate"] = abs(obj.spinRate)
        
        if cameras:
            result["cameras"] = cameras
            try:
                active_cam = mset.getCamera()
                if active_cam and hasattr(active_cam, 'name'):
                    result["active_camera"] = active_cam.name
            except:
                pass
        
        # Find render object
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        if render_obj:
            log("Found RenderObject")
            
            # Get image settings
            if hasattr(render_obj, 'images'):
                img = render_obj.images
                if hasattr(img, 'width'): result["resolution_x"] = img.width
                if hasattr(img, 'height'): result["resolution_y"] = img.height
                if hasattr(img, 'samples'): result["samples"] = img.samples
            
            # Get video settings
            if hasattr(render_obj, 'videos'):
                vid = render_obj.videos
                if hasattr(vid, 'frameCount') and vid.frameCount > 0:
                    result["turntable_frames"] = vid.frameCount
                    result["frame_end"] = vid.frameCount
                    result["total_frames"] = vid.frameCount
                if hasattr(vid, 'samples'):
                    result["video_samples"] = vid.samples
            
            # Get render passes - THIS IS THE KEY PART
            if hasattr(render_obj, 'renderPasses'):
                passes = []
                log(f"Found {{len(render_obj.renderPasses)}} render pass objects")
                for rp in render_obj.renderPasses:
                    try:
                        pass_name = rp.renderPass if hasattr(rp, 'renderPass') else None
                        if pass_name:
                            passes.append(pass_name)
                            enabled = rp.enabled if hasattr(rp, 'enabled') else False
                            log(f"  Pass: '{{pass_name}}' (enabled={{enabled}})")
                    except Exception as pe:
                        log(f"  Error reading pass: {{pe}}")
                
                # Always include Full Quality (beauty) as available
                if "Full Quality" not in passes:
                    passes.insert(0, "Full Quality")
                
                result["available_render_passes"] = passes
                log(f"Total passes: {{len(passes)}}")
        else:
            log("No RenderObject found")
        
        # Get timeline info
        try:
            timeline = mset.getTimeline()
            if timeline:
                if hasattr(timeline, 'totalFrames') and timeline.totalFrames > 1:
                    result["timeline_frames"] = timeline.totalFrames
                    result["has_animation"] = True
                if hasattr(timeline, 'frameRate'):
                    result["frame_rate"] = timeline.frameRate
        except:
            pass
        
    except Exception as e:
        log(f"Error: {{e}}")
        import traceback
        traceback.print_exc()
    
    # Write result
    log(f"Writing result to {{r"{output_path_escaped}"}}")
    with open(r"{output_path_escaped}", 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    log("Done")
    
    mset.quit()

probe_scene()
'''
    
    def _deduplicate_passes(self, render_passes: List[str]) -> List[str]:
        seen = set()
        unique = []
        for pass_id in render_passes:
            if pass_id not in seen:
                seen.add(pass_id)
                unique.append(pass_id)
        return unique
    
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
        
        render_type = job.get_setting("render_type", "still")
        
        script_dir = os.path.dirname(job.file_path) or tempfile.gettempdir()
        self._temp_script_path = os.path.join(script_dir, f"_wane_render_{job.id}.py")
        self._progress_file_path = os.path.join(script_dir, f"_wane_progress_{job.id}.json")
        
        requested_passes = job.get_setting("render_passes", ["beauty"])
        if on_log:
            on_log(f"Requested passes: {requested_passes}")
        
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
                on_log(f"Render type: {render_type}")
                on_log(f"Output: {job.output_folder}")
            
            def render_thread():
                try:
                    startupinfo = None
                    creation_flags = 0
                    if sys.platform == 'win32':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = 6
                        creation_flags = 0x08000000
                    
                    cmd = [toolbag_exe, '-hide', self._temp_script_path]
                    
                    self.current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                           startupinfo=startupinfo, creationflags=creation_flags)
                    
                    if on_log:
                        on_log(f"Started Toolbag PID: {self.current_process.pid}")
                    
                    self._start_progress_monitor(job, on_progress, on_log)
                    
                    for line_bytes in self.current_process.stdout:
                        if self.is_cancelling:
                            break
                        line = line_bytes.decode('utf-8', errors='replace').strip()
                        if line and on_log and '[Wane]' in line:
                            on_log(line.replace('[Wane] ', ''))
                    
                    return_code = self.current_process.wait()
                    self._stop_progress_monitor()
                    
                    if self.is_cancelling:
                        return
                    
                    final_status = self._read_progress_file()
                    
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
                        on_error(str(e))
                finally:
                    self._cleanup()
            
            threading.Thread(target=render_thread, daemon=True).start()
            
        except Exception as e:
            self._cleanup()
            on_error(f"Failed to start render: {e}")
    
    def _generate_still_script(self, job) -> str:
        """Still images use renderCamera() which accepts a pass parameter directly."""
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        output_format = job.output_format.upper()
        denoise_mode = job.get_setting("denoise_mode", "gpu")
        denoise_quality = job.get_setting("denoise_quality", "high")
        denoise_strength = job.get_setting("denoise_strength", 1.0)
        
        render_passes = self._deduplicate_passes(job.get_setting("render_passes", ["beauty"]) or ["beauty"])
        
        pass_config = []
        for pass_id in render_passes:
            for p in self.RENDER_PASSES:
                if p["id"] == pass_id:
                    pass_config.append({"id": pass_id, "name": p["name"], "pass": p["pass"]})
                    break
        
        if not pass_config:
            pass_config = [{"id": "beauty", "name": "Final Composite (Beauty)", "pass": ""}]
        
        ext_map = {"PNG": "png", "JPEG": "jpg", "TGA": "tga", "PSD": "psd", "EXR (16-BIT)": "exr", "EXR (32-BIT)": "exr"}
        ext = ext_map.get(output_format, "png")
        
        import json as json_module
        pass_config_str = json_module.dumps(pass_config)
        
        return f'''import mset
import json
import os
import sys

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error=""):
    try:
        with open(r"{progress_path}", 'w') as f:
            json.dump({{"status": status, "progress": progress, "message": message, "error": error}}, f)
    except:
        pass

def render_still():
    try:
        passes = {pass_config_str}
        total_passes = len(passes)
        
        log(f"Still render: {{total_passes}} pass(es)")
        update_progress("loading", 0, "Loading scene...")
        
        mset.loadScene(r"{scene_path}")
        log("Scene loaded")
        
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        if render_obj and hasattr(render_obj, 'images'):
            try:
                render_obj.images.rayTraceDenoiseMode = "{denoise_mode}"
                render_obj.images.rayTraceDenoiseQuality = "{denoise_quality}"
                render_obj.images.rayTraceDenoiseStrength = {denoise_strength}
            except:
                pass
        
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Build pass mapping: Marmoset filename pattern -> our output name
        # Marmoset outputs: tbrender_CameraName_PassName_00001.png
        # PassName has spaces removed: "Full Quality" -> "FullQuality"
        pass_mapping = {{}}
        for pass_info in passes:
            viewport_pass = pass_info["pass"]
            pass_id = pass_info["id"]
            if viewport_pass:
                filename_pattern = viewport_pass.replace(" ", "")
            else:
                filename_pattern = "FullQuality"
            pass_mapping[filename_pattern] = pass_id
        
        log(f"Requested passes: {{[p['name'] for p in passes]}}")
        log(f"Pass mapping: {{pass_mapping}}")
        log("Note: Marmoset renders all scene passes; we'll keep only requested ones.")
        
        # Configure output settings
        if render_obj and hasattr(render_obj, 'images'):
            render_obj.images.outputPath = output_dir
            render_obj.images.width = {job.res_width}
            render_obj.images.height = {job.res_height}
            render_obj.images.samples = {samples}
            render_obj.images.transparency = {str(use_transparency)}
        
        update_progress("rendering", 10, "Rendering...")
        
        # Call renderImages() ONCE - outputs all scene passes
        try:
            mset.renderImages()
            log("renderImages() complete")
        except Exception as e:
            log(f"ERROR in renderImages(): {{e}}")
            raise e
        
        update_progress("organizing", 80, "Organizing files...")
        
        # Find and organize output files
        import glob
        import shutil
        
        # Try PNG first, then other formats
        output_files = glob.glob(os.path.join(output_dir, "tbrender_*.png"))
        if not output_files:
            output_files = glob.glob(os.path.join(output_dir, "tbrender_*.{ext}"))
        if not output_files:
            output_files = glob.glob(os.path.join(output_dir, "tbrender_*.*"))
        
        log(f"Found {{len(output_files)}} output files")
        
        files_kept = 0
        for filepath in output_files:
            filename = os.path.basename(filepath)
            
            # Check if this file matches a requested pass
            matched = False
            for pattern, pass_id in pass_mapping.items():
                if f"_{{pattern}}_" in filename:
                    # Build destination path
                    file_ext = os.path.splitext(filename)[1]
                    if total_passes > 1:
                        dest_path = os.path.join(output_dir, f"{job.output_name}_{{pass_id}}{{file_ext}}")
                    else:
                        dest_path = os.path.join(output_dir, "{job.output_name}{{file_ext}}")
                    
                    try:
                        shutil.move(filepath, dest_path)
                        file_size = os.path.getsize(dest_path)
                        log(f"Kept: {{os.path.basename(dest_path)}} ({{file_size:,}} bytes)")
                        files_kept += 1
                        matched = True
                    except Exception as e:
                        log(f"Move error: {{e}}")
                    break
            
            # Delete unwanted passes
            if not matched:
                try:
                    os.remove(filepath)
                    log(f"Deleted unwanted: {{filename}}")
                except:
                    pass
        
        log(f"Complete! Kept {{files_kept}}/{{total_passes}} requested passes")
        update_progress("complete", 100, "Render complete")
        
    except Exception as e:
        log(f"Error: {{e}}")
        update_progress("error", 0, "", str(e))
        import traceback
        traceback.print_exc()
    
    mset.quit()

render_still()
'''
    
    def _generate_turntable_script(self, job, start_frame: int) -> str:
        """
        Turntable render - simple approach:
        1. Call renderVideos() ONCE - Marmoset handles all frames
        2. After complete, sort files into folders for requested passes
        3. Delete unwanted pass files
        """
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        total_frames = job.frame_end
        clockwise = job.get_setting("turntable_clockwise", True)
        denoise_mode = job.get_setting("denoise_mode", "gpu")
        denoise_quality = job.get_setting("denoise_quality", "high")
        denoise_strength = job.get_setting("denoise_strength", 1.0)
        
        render_passes = self._deduplicate_passes(job.get_setting("render_passes", ["beauty"]) or ["beauty"])
        
        pass_config = []
        for pass_id in render_passes:
            for p in self.RENDER_PASSES:
                if p["id"] == pass_id:
                    pass_config.append({"id": pass_id, "name": p["name"], "pass": p["pass"]})
                    break
        
        if not pass_config:
            pass_config = [{"id": "beauty", "name": "Final Composite (Beauty)", "pass": ""}]
        
        import json as json_module
        pass_config_str = json_module.dumps(pass_config)
        
        spin_sign = "" if clockwise else "-"
        
        return f'''import mset
import json
import os
import sys
import glob
import shutil

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error="", frame=0):
    try:
        with open(r"{progress_path}", 'w') as f:
            json.dump({{"status": status, "progress": progress, "message": message, "error": error, "frame": frame, "total_frames": {total_frames}}}, f)
    except:
        pass

def render_turntable():
    try:
        requested_passes = {pass_config_str}
        total_frames = {total_frames}
        
        log("=" * 60)
        log("TURNTABLE RENDER")
        log("=" * 60)
        log(f"Requested {{len(requested_passes)}} pass(es):")
        for p in requested_passes:
            log(f"  - {{p['id']}}: '{{p['pass'] if p['pass'] else '(beauty)'}}'")
        
        update_progress("loading", 0, "Loading scene...")
        mset.loadScene(r"{scene_path}")
        log("Scene loaded")
        
        # Find render object
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Configure video output settings
        if render_obj and hasattr(render_obj, 'videos'):
            render_obj.videos.outputPath = output_dir
            render_obj.videos.width = {job.res_width}
            render_obj.videos.height = {job.res_height}
            render_obj.videos.samples = {samples}
            render_obj.videos.transparency = {str(use_transparency)}
            render_obj.videos.format = "PNG"
            try:
                render_obj.videos.rayTraceDenoiseMode = "{denoise_mode}"
                render_obj.videos.rayTraceDenoiseQuality = "{denoise_quality}"
                render_obj.videos.rayTraceDenoiseStrength = {denoise_strength}
            except:
                pass
            log(f"Output: {{output_dir}}")
            log(f"Resolution: {job.res_width}x{job.res_height}, Samples: {samples}")
        
        # Build pass mapping: Marmoset filename pattern -> our folder ID
        # Marmoset outputs: tbrender_CameraName_PassName_00001.png
        # PassName has spaces removed: "Full Quality" -> "FullQuality"
        pass_mapping = {{}}
        for pass_info in requested_passes:
            viewport_pass = pass_info["pass"]
            pass_id = pass_info["id"]
            if viewport_pass:
                filename_pattern = viewport_pass.replace(" ", "")
            else:
                filename_pattern = "FullQuality"
            pass_mapping[filename_pattern] = pass_id
        
        log(f"Will keep passes: {{list(pass_mapping.keys())}}")
        
        # Create folders for requested passes
        for pass_id in pass_mapping.values():
            os.makedirs(os.path.join(output_dir, pass_id), exist_ok=True)
        
        # Set timeline for frame count
        timeline = mset.getTimeline()
        if timeline:
            timeline.selectionStart = 1
            timeline.selectionEnd = total_frames
            log(f"Timeline set: 1-{{total_frames}} frames")
        
        log("")
        log("Rendering... (Marmoset will output all scene passes)")
        update_progress("rendering", 10, "Rendering...")
        
        # ONE render call - Marmoset handles everything
        mset.renderVideos()
        
        log("Render complete, organizing files...")
        update_progress("organizing", 90, "Organizing files...")
        
        # Sort files into folders
        all_files = glob.glob(os.path.join(output_dir, "tbrender_*.png"))
        log(f"Found {{len(all_files)}} output files")
        
        files_kept = 0
        files_deleted = 0
        
        for filepath in all_files:
            filename = os.path.basename(filepath)
            
            # Check if this file matches a requested pass
            matched = False
            for pattern, folder_id in pass_mapping.items():
                if f"_{{pattern}}_" in filename:
                    # Move to pass folder
                    dest_folder = os.path.join(output_dir, folder_id)
                    dest_path = os.path.join(dest_folder, filename)
                    shutil.move(filepath, dest_path)
                    files_kept += 1
                    matched = True
                    break
            
            # Delete unwanted passes
            if not matched:
                os.remove(filepath)
                files_deleted += 1
        
        log(f"Kept {{files_kept}} files, deleted {{files_deleted}} unwanted")
        log("COMPLETE!")
        update_progress("complete", 100, "Complete", frame=files_kept)
        
    except Exception as e:
        log(f"ERROR: {{e}}")
        update_progress("error", 0, "", str(e))
        import traceback
        traceback.print_exc()
    
    mset.quit()

render_turntable()
'''
    
    def _generate_animation_script(self, job, start_frame: int) -> str:
        """
        Animation render - simple approach:
        1. Call renderVideos() ONCE - Marmoset handles all frames
        2. After complete, sort files into folders for requested passes
        3. Delete unwanted pass files
        """
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        denoise_mode = job.get_setting("denoise_mode", "gpu")
        denoise_quality = job.get_setting("denoise_quality", "high")
        denoise_strength = job.get_setting("denoise_strength", 1.0)
        
        render_passes = self._deduplicate_passes(job.get_setting("render_passes", ["beauty"]) or ["beauty"])
        
        pass_config = []
        for pass_id in render_passes:
            for p in self.RENDER_PASSES:
                if p["id"] == pass_id:
                    pass_config.append({"id": pass_id, "name": p["name"], "pass": p["pass"]})
                    break
        
        if not pass_config:
            pass_config = [{"id": "beauty", "name": "Final Composite (Beauty)", "pass": ""}]
        
        import json as json_module
        pass_config_str = json_module.dumps(pass_config)
        
        total_frames = job.frame_end - start_frame + 1
        
        return f'''import mset
import json
import os
import sys
import glob
import shutil

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error="", frame=0):
    try:
        with open(r"{progress_path}", 'w') as f:
            json.dump({{"status": status, "progress": progress, "message": message, "error": error, "frame": frame, "total_frames": {total_frames}}}, f)
    except:
        pass

def render_animation():
    try:
        requested_passes = {pass_config_str}
        start_frame = {start_frame}
        end_frame = {job.frame_end}
        total_frames = {total_frames}
        
        log("=" * 60)
        log("ANIMATION RENDER")
        log("=" * 60)
        log(f"Requested {{len(requested_passes)}} pass(es):")
        for p in requested_passes:
            log(f"  - {{p['id']}}: '{{p['pass'] if p['pass'] else '(beauty)'}}'")
        log(f"Frames: {{start_frame}}-{{end_frame}} ({{total_frames}} total)")
        
        update_progress("loading", 0, "Loading scene...")
        mset.loadScene(r"{scene_path}")
        log("Scene loaded")
        
        # Find render object
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Set timeline range
        timeline = mset.getTimeline()
        if timeline:
            timeline.selectionStart = start_frame
            timeline.selectionEnd = end_frame
            log(f"Timeline set: {{start_frame}}-{{end_frame}}")
        
        # Configure video output settings
        if render_obj and hasattr(render_obj, 'videos'):
            render_obj.videos.outputPath = output_dir
            render_obj.videos.width = {job.res_width}
            render_obj.videos.height = {job.res_height}
            render_obj.videos.samples = {samples}
            render_obj.videos.transparency = {str(use_transparency)}
            render_obj.videos.format = "PNG"
            try:
                render_obj.videos.rayTraceDenoiseMode = "{denoise_mode}"
                render_obj.videos.rayTraceDenoiseQuality = "{denoise_quality}"
                render_obj.videos.rayTraceDenoiseStrength = {denoise_strength}
            except:
                pass
            log(f"Output: {{output_dir}}")
            log(f"Resolution: {job.res_width}x{job.res_height}, Samples: {samples}")
        
        # Build pass mapping: Marmoset filename pattern -> our folder ID
        pass_mapping = {{}}
        for pass_info in requested_passes:
            viewport_pass = pass_info["pass"]
            pass_id = pass_info["id"]
            if viewport_pass:
                filename_pattern = viewport_pass.replace(" ", "")
            else:
                filename_pattern = "FullQuality"
            pass_mapping[filename_pattern] = pass_id
        
        log(f"Will keep passes: {{list(pass_mapping.keys())}}")
        
        # Create folders for requested passes
        for pass_id in pass_mapping.values():
            os.makedirs(os.path.join(output_dir, pass_id), exist_ok=True)
        
        log("")
        log("Rendering... (Marmoset will output all scene passes)")
        update_progress("rendering", 10, "Rendering...")
        
        # ONE render call - Marmoset handles everything
        mset.renderVideos()
        
        log("Render complete, organizing files...")
        update_progress("organizing", 90, "Organizing files...")
        
        # Sort files into folders
        all_files = glob.glob(os.path.join(output_dir, "tbrender_*.png"))
        log(f"Found {{len(all_files)}} output files")
        
        files_kept = 0
        files_deleted = 0
        
        for filepath in all_files:
            filename = os.path.basename(filepath)
            
            # Check if this file matches a requested pass
            matched = False
            for pattern, folder_id in pass_mapping.items():
                if f"_{{pattern}}_" in filename:
                    # Move to pass folder
                    dest_folder = os.path.join(output_dir, folder_id)
                    dest_path = os.path.join(dest_folder, filename)
                    shutil.move(filepath, dest_path)
                    files_kept += 1
                    matched = True
                    break
            
            # Delete unwanted passes
            if not matched:
                os.remove(filepath)
                files_deleted += 1
        
        log(f"Kept {{files_kept}} files, deleted {{files_deleted}} unwanted")
        log("COMPLETE!")
        update_progress("complete", 100, "Complete", frame=files_kept)
        
    except Exception as e:
        log(f"ERROR: {{e}}")
        update_progress("error", 0, "", str(e))
        import traceback
        traceback.print_exc()
    
    mset.quit()

render_animation()
'''
    
    def _start_progress_monitor(self, job, on_progress, on_log=None):
        self._monitoring = True
        
        def monitor():
            import glob
            import time
            
            last_file_count = 0
            frames_per_pass = job.frame_end if job.is_animation else 1
            
            render_passes = self._deduplicate_passes(job.get_setting("render_passes", ["beauty"]) or ["beauty"])
            
            wants_beauty = any(p == "beauty" for p in render_passes)
            other_pass_count = sum(1 for p in render_passes if p != "beauty")
            
            total_passes = (1 if wants_beauty else 0) + other_pass_count
            total_files_expected = frames_per_pass * total_passes
            
            job.total_passes = total_passes
            job.pass_total_frames = frames_per_pass
            
            base_output = job.output_folder
            
            while self._monitoring and not self.is_cancelling:
                progress = self._read_progress_file()
                
                if progress:
                    status = progress.get("status", "")
                    if status == "complete":
                        on_progress(total_files_expected, "Complete")
                        break
                    elif status == "error":
                        break
                
                try:
                    main_files = glob.glob(os.path.join(base_output, "tbrender_*.png"))
                    main_count = len(main_files)
                    
                    subfolder_count = 0
                    for pass_id in render_passes:
                        pass_folder = os.path.join(base_output, pass_id)
                        if os.path.exists(pass_folder):
                            subfolder_count += len(glob.glob(os.path.join(pass_folder, "*.png")))
                    
                    total_file_count = main_count + subfolder_count
                    
                    if total_file_count > last_file_count:
                        last_file_count = total_file_count
                        
                        progress_pct = min(int((total_file_count / max(total_files_expected, 1)) * 100), 99)
                        
                        job.current_frame = total_file_count
                        job.progress = progress_pct
                        
                        if total_passes > 0:
                            job.rendering_frame = total_file_count // total_passes
                            job.pass_frame = job.rendering_frame
                        
                        on_progress(total_file_count, "Rendering")
                        
                except:
                    pass
                
                time.sleep(0.5)
        
        self._progress_monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._progress_monitor_thread.start()
    
    def _stop_progress_monitor(self):
        self._monitoring = False
        if self._progress_monitor_thread:
            self._progress_monitor_thread.join(timeout=2)
            self._progress_monitor_thread = None
    
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
        self._stop_progress_monitor()
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
