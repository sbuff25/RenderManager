"""
Wain Marmoset Engine - Optimized Frame-by-Frame Rendering
==========================================================

Uses renderCamera() for ALL render types to ensure only requested passes
are rendered. This is more efficient than renderVideos() which renders
ALL scene passes regardless of selection.

Strategy:
- Still: Single renderCamera() call per pass
- Turntable/Animation: Loop through frames, render each requested pass

This gives accurate progress tracking and no wasted renders.
Total renders = frames × passes (e.g., 30 frames × 3 passes = 90 renders)
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
    
    VIDEO_FORMATS = {"MP4": "MPEG4", "PNG Sequence": "PNG", "JPEG Sequence": "JPEG", "TGA Sequence": "TGA"}
    RENDERERS = ["Ray Tracing", "Hybrid", "Raster"]
    SHADOW_QUALITY = ["Low", "High", "Mega"]
    DENOISE_MODES = ["off", "cpu", "gpu"]
    DENOISE_QUALITY = ["low", "medium", "high"]
    RENDER_TYPES = {"still": "Still Image", "turntable": "Turntable (360 deg)", "animation": "Animation"}
    
    # Render passes - viewportPass parameter must be lowercase for renderCamera()
    RENDER_PASSES = [
        {"id": "beauty", "name": "Final Composite (Beauty)", "pass": "", "category": "Common"},
        {"id": "wireframe", "name": "Wireframe", "pass": "wireframe", "category": "Common"},
        {"id": "alpha_mask", "name": "Alpha Mask", "pass": "alpha mask", "category": "Geometry"},
        {"id": "depth", "name": "Depth", "pass": "depth", "category": "Geometry"},
        {"id": "incidence", "name": "Incidence", "pass": "incidence", "category": "Geometry"},
        {"id": "normals", "name": "Normals", "pass": "normals", "category": "Geometry"},
        {"id": "position", "name": "Position", "pass": "position", "category": "Geometry"},
        {"id": "material_id", "name": "Material ID", "pass": "material id", "category": "ID"},
        {"id": "object_id", "name": "Object ID", "pass": "object id", "category": "ID"},
        {"id": "ambient_occlusion", "name": "Ambient Occlusion", "pass": "ambient occlusion", "category": "Lighting"},
        {"id": "lighting_direct", "name": "Lighting (Direct)", "pass": "lighting (direct)", "category": "Lighting"},
        {"id": "lighting_indirect", "name": "Lighting (Indirect)", "pass": "lighting (indirect)", "category": "Lighting"},
        {"id": "diffuse_complete", "name": "Diffuse (Complete)", "pass": "diffuse (complete)", "category": "Lighting"},
        {"id": "diffuse_direct", "name": "Diffuse (Direct)", "pass": "diffuse (direct)", "category": "Lighting"},
        {"id": "diffuse_indirect", "name": "Diffuse (Indirect)", "pass": "diffuse (indirect)", "category": "Lighting"},
        {"id": "specular_complete", "name": "Specular (Complete)", "pass": "specular (complete)", "category": "Lighting"},
        {"id": "specular_direct", "name": "Specular (Direct)", "pass": "specular (direct)", "category": "Lighting"},
        {"id": "specular_indirect", "name": "Specular (Indirect)", "pass": "specular (indirect)", "category": "Lighting"},
        {"id": "albedo", "name": "Albedo", "pass": "albedo", "category": "Material"},
        {"id": "displacement", "name": "Displacement", "pass": "displacement", "category": "Material"},
        {"id": "emissive", "name": "Emissive", "pass": "emissive", "category": "Material"},
        {"id": "gloss", "name": "Gloss", "pass": "gloss", "category": "Material"},
        {"id": "metalness", "name": "Metalness", "pass": "metalness", "category": "Material"},
        {"id": "reflectivity", "name": "Reflectivity", "pass": "reflectivity", "category": "Material"},
        {"id": "roughness", "name": "Roughness", "pass": "roughness", "category": "Material"},
        {"id": "transparency", "name": "Transparency", "pass": "transparency", "category": "Material"},
    ]
    
    def __init__(self):
        super().__init__()
        self._temp_script_path: Optional[str] = None
        self._progress_file_path: Optional[str] = None
        self._progress_monitor_thread: Optional[threading.Thread] = None
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
        probe_script = os.path.join(script_dir, "_wain_probe.py")
        output_json = os.path.join(script_dir, "_wain_probe_result.json")
        
        probe_code = self._generate_probe_script(file_path, output_json)
        
        try:
            with open(probe_script, 'w', encoding='utf-8') as f:
                f.write(probe_code)
            
            startupinfo = subprocess.STARTUPINFO() if sys.platform == 'win32' else None
            creation_flags = 0
            if startupinfo:
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                creation_flags = 0x08000000
            
            print(f"[Wain] Probing scene: {file_path}")
            
            result = subprocess.run(
                [toolbag_exe, '-hide', probe_script], 
                capture_output=True, 
                timeout=20,
                startupinfo=startupinfo,
                creationflags=creation_flags
            )
            
            print(f"[Wain] Toolbag exited with code: {result.returncode}")
            
            if os.path.exists(output_json):
                with open(output_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"[Wain] Probe results: {data}")
                    return data
            return default_info
        except subprocess.TimeoutExpired:
            print(f"[Wain] Probe timed out")
            return default_info
        except Exception as e:
            print(f"[Wain] Probe error: {e}")
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

def probe_scene():
    result = {{"cameras": [], "active_camera": "Main Camera", "resolution_x": 1920, "resolution_y": 1080,
               "renderer": "Ray Tracing", "samples": 256, "frame_start": 1, "frame_end": 1,
               "total_frames": 1, "has_animation": False, "has_turntable": False, "turntable_frames": 120}}
    
    try:
        mset.loadScene(r"{scene_path_escaped}")
        
        cameras = []
        for obj in mset.getAllObjects():
            obj_name = obj.name if hasattr(obj, 'name') else str(obj)
            obj_type = type(obj).__name__
            if hasattr(obj, 'fov') or 'Camera' in obj_type:
                cameras.append(obj_name)
            if 'Turntable' in obj_type and hasattr(obj, 'enabled') and obj.enabled:
                result["has_turntable"] = True
        
        if cameras:
            result["cameras"] = cameras
            try:
                active_cam = mset.getCamera()
                if active_cam and hasattr(active_cam, 'name'):
                    result["active_camera"] = active_cam.name
            except:
                pass
        
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        if render_obj:
            if hasattr(render_obj, 'images'):
                img = render_obj.images
                if hasattr(img, 'width'): result["resolution_x"] = img.width
                if hasattr(img, 'height'): result["resolution_y"] = img.height
                if hasattr(img, 'samples'): result["samples"] = img.samples
        
        try:
            timeline = mset.getTimeline()
            if timeline:
                total = 1
                if hasattr(timeline, 'totalFrames'):
                    total = timeline.totalFrames
                elif hasattr(timeline, 'selectionEnd'):
                    total = timeline.selectionEnd
                
                if total > 1:
                    result["total_frames"] = total
                    result["frame_end"] = total
                    result["has_animation"] = True
                    if result["has_turntable"]:
                        result["turntable_frames"] = total
        except:
            pass
        
    except Exception as e:
        print(f"Probe error: {{e}}")
    
    with open(r"{output_path_escaped}", 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
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
        overwrite_existing = job.overwrite_existing
        
        script_dir = os.path.dirname(job.file_path) or tempfile.gettempdir()
        self._temp_script_path = os.path.join(script_dir, f"_wain_render_{job.id}.py")
        self._progress_file_path = os.path.join(script_dir, f"_wain_progress_{job.id}.json")
        
        requested_passes = job.get_setting("render_passes", ["beauty"])
        num_passes = len(requested_passes) if requested_passes else 1
        
        if on_log:
            on_log(f"Render type: {render_type}")
            on_log(f"Passes ({num_passes}): {requested_passes}")
            on_log(f"Output: {job.output_folder}")
            on_log(f"Overwrite existing: {overwrite_existing}")
        
        if render_type == "turntable":
            total_renders = job.frame_end * num_passes
            if on_log:
                on_log(f"Total renders: {total_renders} ({job.frame_end} frames × {num_passes} passes)")
            script_code = self._generate_turntable_script(job, start_frame)
        elif render_type == "animation":
            total_frames = job.frame_end - start_frame + 1
            total_renders = total_frames * num_passes
            if on_log:
                on_log(f"Total renders: {total_renders} ({total_frames} frames × {num_passes} passes)")
            script_code = self._generate_animation_script(job, start_frame)
        else:
            if on_log:
                on_log(f"Total renders: {num_passes} (1 frame × {num_passes} passes)")
            script_code = self._generate_still_script(job)
        
        try:
            with open(self._temp_script_path, 'w', encoding='utf-8') as f:
                f.write(script_code)
            
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
                        if line and on_log and '[Wain]' in line:
                            on_log(line.replace('[Wain] ', ''))
                    
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
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        output_format = job.output_format.upper()
        overwrite_existing = job.overwrite_existing
        
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
        num_passes = len(pass_config)
        
        return f'''import mset
import json
import os
import sys

OVERWRITE_EXISTING = {overwrite_existing}

def log(msg):
    print(f"[Wain] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, current=0, total=0, current_pass="", pass_in_frame=0, num_passes=0, error=""):
    try:
        with open(r"{progress_path}", 'w') as f:
            json.dump({{"status": status, "progress": progress, "current": current,
                       "total": total, "current_pass": current_pass, "error": error,
                       "frame": 1, "total_frames": 1, "pass_in_frame": pass_in_frame, "num_passes": num_passes}}, f)
    except:
        pass

def render_still():
    try:
        passes = {pass_config_str}
        num_passes = len(passes)
        
        log("=" * 60)
        log("STILL IMAGE RENDER - Selective Pass Rendering")
        log("=" * 60)
        log(f"Total renders: {{num_passes}} (1 frame x {{num_passes}} passes)")
        log(f"Overwrite existing: {{OVERWRITE_EXISTING}}")
        
        update_progress("loading", 0, 0, num_passes, "", 0, num_passes)
        
        mset.loadScene(r"{scene_path}")
        log("Scene loaded")
        
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        rendered_count = 0
        skipped_count = 0
        
        for idx, pass_info in enumerate(passes):
            pass_id = pass_info["id"]
            pass_name = pass_info["name"]
            viewport_pass = pass_info["pass"]
            
            render_num = idx + 1
            progress_pct = min(int((render_num / num_passes) * 100), 99)
            update_progress("rendering", progress_pct, render_num, num_passes, pass_name, render_num, num_passes)
            
            if num_passes > 1:
                output_path = os.path.join(output_dir, f"{job.output_name}{{pass_id}}.{ext}")
            else:
                output_path = os.path.join(output_dir, "{job.output_name}.{ext}")
            
            if not OVERWRITE_EXISTING and os.path.exists(output_path):
                log(f"  Skipping {{render_num}}/{{num_passes}}: {{pass_name}} (file exists)")
                skipped_count += 1
                continue
            
            log(f"  Rendering {{render_num}}/{{num_passes}}: {{pass_name}}")
            
            try:
                mset.renderCamera(
                    output_path,
                    {job.res_width},
                    {job.res_height},
                    {samples},
                    {str(use_transparency)},
                    "",
                    viewport_pass
                )
                
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    log(f"    Saved: {{os.path.basename(output_path)}} ({{file_size:,}} bytes)")
                    rendered_count += 1
            except Exception as pass_err:
                log(f"    ERROR: {{pass_err}}")
        
        log("")
        log("=" * 60)
        log(f"COMPLETE! Rendered {{rendered_count}} images, skipped {{skipped_count}}")
        log("=" * 60)
        update_progress("complete", 100, num_passes, num_passes, "", num_passes, num_passes)
        
    except Exception as e:
        log(f"FATAL ERROR: {{e}}")
        update_progress("error", 0, 0, 0, "", 0, 0, str(e))
    
    mset.quit()

render_still()
'''
    
    def _generate_turntable_script(self, job, start_frame: int) -> str:
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        total_frames = job.frame_end
        overwrite_existing = job.overwrite_existing
        
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
        
        num_passes = len(pass_config)
        total_renders = total_frames * num_passes
        renders_already_done = (start_frame - 1) * num_passes
        
        return f'''import mset
import json
import os
import sys

OVERWRITE_EXISTING = {overwrite_existing}
START_FRAME = {start_frame}
RENDERS_ALREADY_DONE = {renders_already_done}

def log(msg):
    print(f"[Wain] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, current=0, total=0, frame=0, total_frames=0, current_pass="", pass_in_frame=0, num_passes=0, error=""):
    try:
        with open(r"{progress_path}", 'w') as f:
            json.dump({{"status": status, "progress": progress, "current": current, "total": total,
                       "frame": frame, "total_frames": total_frames, "current_pass": current_pass,
                       "pass_in_frame": pass_in_frame, "num_passes": num_passes, "error": error}}, f)
    except:
        pass

def render_turntable():
    try:
        passes = {pass_config_str}
        total_frames = {total_frames}
        num_passes = len(passes)
        total_renders = {total_renders}
        start_frame = START_FRAME
        
        frames_to_render = total_frames - start_frame + 1
        
        log("=" * 60)
        log("TURNTABLE RENDER - Selective Pass Rendering")
        log("=" * 60)
        log(f"Total frames: {{total_frames}}")
        if start_frame > 1:
            log(f"Resuming from frame: {{start_frame}}")
        log(f"Passes: {{num_passes}}")
        log(f"Overwrite existing: {{OVERWRITE_EXISTING}}")
        
        update_progress("loading", 0, RENDERS_ALREADY_DONE, total_renders, start_frame - 1, total_frames, "", 0, num_passes)
        
        mset.loadScene(r"{scene_path}")
        log("Scene loaded")
        
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        if num_passes > 1:
            for pass_info in passes:
                pass_folder = os.path.join(output_dir, pass_info["id"])
                os.makedirs(pass_folder, exist_ok=True)
        
        timeline = mset.getTimeline()
        if not timeline:
            raise Exception("Could not get timeline")
        
        fps = timeline.getFrameRate() if hasattr(timeline, 'getFrameRate') else 30
        timeline.selectionStart = 1
        timeline.selectionEnd = total_frames
        
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        scene_passes = {{}}
        scene_pass_names = {{}}
        if render_obj and hasattr(render_obj, 'renderPasses'):
            for rp in render_obj.renderPasses:
                rp_name = rp.renderPass if hasattr(rp, 'renderPass') else 'unknown'
                rp_enabled = rp.enabled if hasattr(rp, 'enabled') else False
                scene_passes[rp_name.lower()] = rp
                scene_pass_names[rp_name.lower()] = rp_name
        
        render_count = RENDERS_ALREADY_DONE
        skipped_count = 0
        
        for frame in range(start_frame, total_frames + 1):
            try:
                if hasattr(timeline, 'currentFrame'):
                    timeline.currentFrame = frame
                elif hasattr(timeline, 'time'):
                    timeline.time = (frame - 1) / fps
            except Exception as te:
                log(f"Timeline error: {{te}}")
            
            for pass_idx, pass_info in enumerate(passes):
                pass_id = pass_info["id"]
                pass_name = pass_info["name"]
                viewport_pass = pass_info["pass"]
                pass_in_frame = pass_idx + 1  # 1-based pass number within frame
                
                render_count += 1
                progress_pct = min(int((render_count / total_renders) * 100), 99)
                update_progress("rendering", progress_pct, render_count, total_renders, frame, total_frames, pass_name, pass_in_frame, num_passes)
                
                if num_passes > 1:
                    output_path = os.path.join(output_dir, pass_id, f"frame_{{frame:05d}}.png")
                else:
                    output_path = os.path.join(output_dir, f"frame_{{frame:05d}}.png")
                
                if not OVERWRITE_EXISTING and os.path.exists(output_path):
                    skipped_count += 1
                    continue
                
                lookup_key = viewport_pass.lower() if viewport_pass else 'full quality'
                actual_pass_name = scene_pass_names.get(lookup_key, '')
                
                for rp_key, rp in scene_passes.items():
                    rp.enabled = (rp_key == lookup_key)
                
                try:
                    mset.renderCamera(
                        output_path,
                        {job.res_width},
                        {job.res_height},
                        {samples},
                        {str(use_transparency)},
                        "",
                        actual_pass_name
                    )
                except Exception as e:
                    log(f"ERROR frame {{frame}} pass '{{pass_id}}': {{e}}")
            
            if frame % 5 == 0 or frame == total_frames:
                log(f"Frame {{frame}}/{{total_frames}} ({{render_count}}/{{total_renders}} renders)")
        
        log("")
        log("=" * 60)
        actual_rendered = render_count - RENDERS_ALREADY_DONE - skipped_count
        log(f"COMPLETE! Rendered {{actual_rendered}} images, skipped {{skipped_count}}")
        log("=" * 60)
        update_progress("complete", 100, total_renders, total_renders, total_frames, total_frames, "", num_passes, num_passes)
        
    except Exception as e:
        log(f"FATAL ERROR: {{e}}")
        update_progress("error", 0, 0, 0, 0, 0, "", 0, 0, str(e))
        import traceback
        traceback.print_exc()
    
    mset.quit()

render_turntable()
'''
    
    def _generate_animation_script(self, job, start_frame: int) -> str:
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        overwrite_existing = job.overwrite_existing
        
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
        num_passes = len(pass_config)
        total_renders = total_frames * num_passes
        
        return f'''import mset
import json
import os
import sys

OVERWRITE_EXISTING = {overwrite_existing}

def log(msg):
    print(f"[Wain] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, current=0, total=0, frame=0, total_frames=0, current_pass="", pass_in_frame=0, num_passes=0, error=""):
    try:
        with open(r"{progress_path}", 'w') as f:
            json.dump({{"status": status, "progress": progress, "current": current, "total": total,
                       "frame": frame, "total_frames": total_frames, "current_pass": current_pass,
                       "pass_in_frame": pass_in_frame, "num_passes": num_passes, "error": error}}, f)
    except:
        pass

def render_animation():
    try:
        passes = {pass_config_str}
        start_frame = {start_frame}
        end_frame = {job.frame_end}
        total_frames = {total_frames}
        num_passes = len(passes)
        total_renders = {total_renders}
        
        log("=" * 60)
        log("ANIMATION RENDER - Selective Pass Rendering")
        log("=" * 60)
        log(f"Frame range: {{start_frame}}-{{end_frame}} ({{total_frames}} frames)")
        log(f"Passes: {{num_passes}}")
        log(f"Total renders: {{total_renders}}")
        log(f"Overwrite existing: {{OVERWRITE_EXISTING}}")
        
        update_progress("loading", 0, 0, total_renders, 0, total_frames, "", 0, num_passes)
        
        mset.loadScene(r"{scene_path}")
        log("Scene loaded")
        
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        if num_passes > 1:
            for pass_info in passes:
                pass_folder = os.path.join(output_dir, pass_info["id"])
                os.makedirs(pass_folder, exist_ok=True)
        
        timeline = mset.getTimeline()
        if not timeline:
            raise Exception("Could not get timeline")
        
        fps = timeline.getFrameRate() if hasattr(timeline, 'getFrameRate') else 30
        
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        scene_pass_names = {{}}
        if render_obj and hasattr(render_obj, 'renderPasses'):
            for rp in render_obj.renderPasses:
                rp_name = rp.renderPass if hasattr(rp, 'renderPass') else ''
                scene_pass_names[rp_name.lower()] = rp_name
        
        render_count = 0
        skipped_count = 0
        frame_idx = 0
        
        for frame in range(start_frame, end_frame + 1):
            frame_idx += 1
            
            try:
                if hasattr(timeline, 'currentFrame'):
                    timeline.currentFrame = frame
                elif hasattr(timeline, 'time'):
                    timeline.time = (frame - 1) / fps
            except:
                pass
            
            for pass_idx, pass_info in enumerate(passes):
                pass_id = pass_info["id"]
                pass_name = pass_info["name"]
                viewport_pass = pass_info["pass"]
                pass_in_frame = pass_idx + 1  # 1-based pass number within frame
                
                render_count += 1
                progress_pct = min(int((render_count / total_renders) * 100), 99)
                update_progress("rendering", progress_pct, render_count, total_renders, frame_idx, total_frames, pass_name, pass_in_frame, num_passes)
                
                if num_passes > 1:
                    output_path = os.path.join(output_dir, pass_id, f"frame_{{frame:05d}}.png")
                else:
                    output_path = os.path.join(output_dir, f"frame_{{frame:05d}}.png")
                
                if not OVERWRITE_EXISTING and os.path.exists(output_path):
                    skipped_count += 1
                    continue
                
                lookup_key = viewport_pass.lower() if viewport_pass else 'full quality'
                actual_pass_name = scene_pass_names.get(lookup_key, viewport_pass)
                
                try:
                    mset.renderCamera(
                        output_path,
                        {job.res_width},
                        {job.res_height},
                        {samples},
                        {str(use_transparency)},
                        "",
                        actual_pass_name
                    )
                except Exception as e:
                    log(f"ERROR frame {{frame}} pass '{{pass_id}}': {{e}}")
            
            if frame_idx % 5 == 0 or frame_idx == total_frames:
                log(f"Frame {{frame_idx}}/{{total_frames}} ({{render_count}}/{{total_renders}} renders)")
        
        log("")
        log("=" * 60)
        log(f"COMPLETE! Rendered {{render_count - skipped_count}} images, skipped {{skipped_count}}")
        log("=" * 60)
        update_progress("complete", 100, total_renders, total_renders, total_frames, total_frames, "", num_passes, num_passes)
        
    except Exception as e:
        log(f"FATAL ERROR: {{e}}")
        update_progress("error", 0, 0, 0, 0, 0, "", 0, 0, str(e))
        import traceback
        traceback.print_exc()
    
    mset.quit()

render_animation()
'''
    
    def _start_progress_monitor(self, job, on_progress, on_log=None):
        """
        Monitor progress file and update job state.
        
        The render script writes progress to a JSON file with:
        - current: current render number (1, 2, 3... up to total)
        - total: total number of renders (frames × passes)
        - frame: current frame number
        - total_frames: total frames
        - current_pass: name of pass being rendered
        - pass_in_frame: which pass number within current frame (1-based)
        - num_passes: total passes per frame
        - progress: percentage (0-100)
        """
        self._monitoring = True
        
        def monitor():
            import time
            
            render_passes = self._deduplicate_passes(job.get_setting("render_passes", ["beauty"]) or ["beauty"])
            num_passes = len(render_passes)
            total_frames = job.frame_end if job.is_animation else 1
            expected_total = total_frames * num_passes
            
            job.total_passes = num_passes
            job.pass_total_frames = total_frames
            
            last_current = -1
            
            while self._monitoring and not self.is_cancelling:
                progress_data = self._read_progress_file()
                
                if progress_data:
                    status = progress_data.get("status", "")
                    current = progress_data.get("current", 0)
                    total = progress_data.get("total", expected_total)
                    frame = progress_data.get("frame", 0)
                    total_frames_from_file = progress_data.get("total_frames", total_frames)
                    current_pass = progress_data.get("current_pass", "")
                    progress_pct = progress_data.get("progress", 0)
                    # Pass tracking for frame percentage
                    pass_in_frame = progress_data.get("pass_in_frame", 0)
                    num_passes_from_file = progress_data.get("num_passes", num_passes)
                    
                    if status == "complete":
                        job.progress = 100
                        job.current_frame = total
                        job.current_pass_num = num_passes_from_file
                        job.total_passes = num_passes_from_file
                        on_progress(total, "Complete")
                        break
                    elif status == "error":
                        break
                    elif status == "rendering" and current != last_current:
                        last_current = current
                        
                        job.current_frame = current
                        job.rendering_frame = frame
                        job.pass_frame = frame
                        job.current_pass = current_pass
                        job.pass_total_frames = total_frames_from_file
                        job.progress = min(progress_pct, 99)
                        # Set pass tracking for frame percentage calculation
                        job.current_pass_num = pass_in_frame
                        job.total_passes = num_passes_from_file
                        
                        on_progress(current, f"Rendering {current_pass}")
                
                time.sleep(0.2)
        
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
