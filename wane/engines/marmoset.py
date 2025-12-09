"""
Wane Marmoset Engine
====================

Marmoset Toolbag render engine integration.

Supports:
- Still image renders (beauty shots)
- Turntable (360 deg rotation) renders
- Animation sequence renders
- Full render settings control (renderer, samples, shadows, denoising)
- Multi-pass rendering with automatic file organization
- File-based progress tracking
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
    
    # Available render passes for Marmoset Toolbag
    # The 'pass' value MUST match EXACTLY what's in Toolbag's Component View / Render Passes dropdown
    # Names sourced from: https://docs.marmoset.co/docs/render-object/#render-passes
    # Empty string or unrecognized values render "Full Quality" (beauty pass)
    RENDER_PASSES = [
        # Common
        {"id": "beauty", "name": "Final Composite (Beauty)", "pass": "", "category": "Common"},
        {"id": "wireframe", "name": "Wireframe", "pass": "Wireframe", "category": "Common"},
        # Geometry Passes
        {"id": "alpha_mask", "name": "Alpha Mask", "pass": "Alpha Mask", "category": "Geometry"},
        {"id": "depth", "name": "Depth", "pass": "Depth", "category": "Geometry"},
        {"id": "incidence", "name": "Incidence", "pass": "Incidence", "category": "Geometry"},
        {"id": "normals", "name": "Normals", "pass": "Normals", "category": "Geometry"},
        {"id": "position", "name": "Position", "pass": "Position", "category": "Geometry"},
        # ID Passes
        {"id": "material_id", "name": "Material ID", "pass": "Material ID", "category": "ID"},
        {"id": "object_id", "name": "Object ID", "pass": "Object ID", "category": "ID"},
        # Lighting Passes
        {"id": "ambient_occlusion", "name": "Ambient Occlusion", "pass": "Ambient Occlusion", "category": "Lighting"},
        {"id": "lighting_direct", "name": "Lighting (Direct)", "pass": "Lighting (Direct)", "category": "Lighting"},
        {"id": "lighting_indirect", "name": "Lighting (Indirect)", "pass": "Lighting (Indirect)", "category": "Lighting"},
        {"id": "diffuse_complete", "name": "Diffuse (Complete)", "pass": "Diffuse (Complete)", "category": "Lighting"},
        {"id": "diffuse_direct", "name": "Diffuse (Direct)", "pass": "Diffuse (Direct)", "category": "Lighting"},
        {"id": "diffuse_indirect", "name": "Diffuse (Indirect)", "pass": "Diffuse (Indirect)", "category": "Lighting"},
        {"id": "specular_complete", "name": "Specular (Complete)", "pass": "Specular (Complete)", "category": "Lighting"},
        {"id": "specular_direct", "name": "Specular (Direct)", "pass": "Specular (Direct)", "category": "Lighting"},
        {"id": "specular_indirect", "name": "Specular (Indirect)", "pass": "Specular (Indirect)", "category": "Lighting"},
        # Material Value Passes
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
            # Render passes - list of pass IDs to render (empty = beauty only)
            # Valid IDs: beauty, albedo, ambient_occlusion, depth, diffuse_lighting,
            #            emissive, normals, object_id, position, reflection, roughness,
            #            specular, specular_lighting
            "render_passes": ["beauty"],      # Default: just beauty pass
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
                
                # Get available render passes from the scene
                if hasattr(render_obj, 'renderPasses'):
                    available_passes = []
                    for rp in render_obj.renderPasses:
                        try:
                            pass_name = rp.renderPass if hasattr(rp, 'renderPass') else str(rp)
                            available_passes.append(pass_name)
                        except:
                            pass
                    result["available_render_passes"] = available_passes
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
        """Generate script for still image render with multi-pass and denoising support."""
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        output_format = job.output_format.upper()
        
        # Denoising settings
        denoise_mode = job.get_setting("denoise_mode", "gpu")
        denoise_quality = job.get_setting("denoise_quality", "high")
        denoise_strength = job.get_setting("denoise_strength", 1.0)
        
        # Get render passes to render
        render_passes = job.get_setting("render_passes", ["beauty"])
        if not render_passes:
            render_passes = ["beauty"]
        
        # Build pass configuration - map pass IDs to Toolbag viewportPass strings
        pass_config = []
        for pass_id in render_passes:
            for p in self.RENDER_PASSES:
                if p["id"] == pass_id:
                    pass_config.append({"id": pass_id, "name": p["name"], "pass": p["pass"]})
                    break
        
        if not pass_config:
            pass_config = [{"id": "beauty", "name": "Final Composite (Beauty)", "pass": ""}]
        
        # Build output filename
        ext_map = {"PNG": "png", "JPEG": "jpg", "TGA": "tga", "PSD": "psd", "EXR (16-BIT)": "exr", "EXR (32-BIT)": "exr"}
        ext = ext_map.get(output_format, "png")
        
        # Convert pass_config to string for embedding in script
        import json as json_module
        pass_config_str = json_module.dumps(pass_config)
        
        return f'''# Wane Render Script - Still Image (Multi-Pass with Denoising)
import mset
import json
import os
import sys

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error="", current_pass="", current_pass_num=0, total_passes=1):
    try:
        data = {{
            "status": status, 
            "progress": progress, 
            "message": message, 
            "error": error, 
            "frame": 0, 
            "total_frames": 1,
            "current_pass": current_pass,
            "current_pass_num": current_pass_num,
            "total_passes": total_passes,
            "pass_frame": 0,
            "pass_total_frames": 1
        }}
        with open(r"{progress_path}", 'w') as f:
            json.dump(data, f)
        if current_pass:
            log(f"Progress: {{status}} {{progress}}% - {{message}} [Pass: {{current_pass}} ({{current_pass_num}}/{{total_passes}})]")
        else:
            log(f"Progress: {{status}} {{progress}}% - {{message}}")
    except Exception as e:
        log(f"Progress update error: {{e}}")

def render_still():
    try:
        # Pass configuration
        passes = {pass_config_str}
        total_passes = len(passes)
        
        log(f"Starting still render with {{total_passes}} pass(es)...")
        log(f"Pass configuration:")
        for i, p in enumerate(passes):
            log(f"  {{i+1}}. id='{{p['id']}}' name='{{p['name']}}' viewport='{{p['pass']}}'")
        update_progress("loading", 0, "Loading scene...", total_passes=total_passes)
        
        log(f"Loading scene: {scene_path}")
        mset.loadScene(r"{scene_path}")
        log("Scene loaded successfully")
        
        # Configure denoising on the render output settings
        log("Configuring denoising...")
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        if render_obj and hasattr(render_obj, 'images'):
            images = render_obj.images
            try:
                images.rayTraceDenoiseMode = "{denoise_mode}"
                log(f"Set denoise mode: {{images.rayTraceDenoiseMode}}")
            except Exception as e:
                log(f"Could not set denoise mode: {{e}}")
            try:
                images.rayTraceDenoiseQuality = "{denoise_quality}"
                log(f"Set denoise quality: {{images.rayTraceDenoiseQuality}}")
            except Exception as e:
                log(f"Could not set denoise quality: {{e}}")
            try:
                images.rayTraceDenoiseStrength = {denoise_strength}
                log(f"Set denoise strength: {{images.rayTraceDenoiseStrength}}")
            except Exception as e:
                log(f"Could not set denoise strength: {{e}}")
        else:
            log("WARNING: Could not find RenderObject for denoising config")
        
        # Ensure output directory exists
        output_dir = r"{output_folder}"
        log(f"Output directory: {{output_dir}}")
        os.makedirs(output_dir, exist_ok=True)
        
        # Render each pass
        for i, pass_info in enumerate(passes):
            pass_num = i + 1
            pass_id = pass_info["id"]
            pass_name = pass_info["name"]
            viewport_pass = pass_info["pass"]  # This goes to renderCamera's viewportPass parameter
            
            log(f"Rendering pass {{pass_num}}/{{total_passes}}: {{pass_name}}")
            update_progress("rendering", int((i / total_passes) * 100), f"Rendering {{pass_name}}...", 
                          current_pass=pass_name, current_pass_num=pass_num, total_passes=total_passes)
            
            # Build output path - add pass suffix if multiple passes
            if total_passes > 1:
                output_path = os.path.join(output_dir, f"{job.output_name}_{{pass_id}}.{ext}")
            else:
                output_path = os.path.join(output_dir, "{job.output_name}.{ext}")
            
            log(f"Output file: {{output_path}}")
            
            # Use renderCamera with viewportPass parameter
            # Signature: mset.renderCamera(path, width, height, samples, transparency, camera, viewportPass)
            # viewportPass must match EXACTLY the string in Component View / Render Passes dropdown
            # Empty string = Full Quality (beauty pass)
            log(f"=== RENDER PASS {{pass_num}}/{{total_passes}} ===")
            log(f"  pass_id: '{{pass_id}}'")
            log(f"  pass_name: '{{pass_name}}'")
            log(f"  viewport_pass: '{{viewport_pass}}'")
            log(f"  output_path: '{{output_path}}'")
            log(f"  resolution: {job.res_width}x{job.res_height}")
            log(f"  samples: {samples}")
            log(f"Calling mset.renderCamera()...")
            mset.renderCamera(
                output_path,
                {job.res_width},
                {job.res_height},
                {samples},
                {str(use_transparency)},
                "",  # camera - empty string uses main camera
                viewport_pass  # viewportPass - the render pass to use
            )
            
            # Check file was created and log size for verification
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                log(f"  SUCCESS: {{output_path}} ({{file_size:,}} bytes)")
            
            else:
                log(f"  WARNING: Output file not found!")
        
        log("All passes complete!")
        update_progress("complete", 100, "Render complete", 
                       current_pass=passes[-1]["name"], current_pass_num=total_passes, total_passes=total_passes)
        
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
        """Generate script for turntable render with multi-pass support.
        
        Marmoset renders ALL enabled passes simultaneously in one renderVideos() call.
        Files are named: tbrender_{Camera}_{PassName}_{FrameNum}.png
        After render, we organize files into pass-specific subfolders.
        """
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        video_format = job.get_setting("video_format", "PNG Sequence")
        total_frames = job.frame_end
        clockwise = job.get_setting("turntable_clockwise", True)
        
        # Denoising settings
        denoise_mode = job.get_setting("denoise_mode", "gpu")
        denoise_quality = job.get_setting("denoise_quality", "high")
        denoise_strength = job.get_setting("denoise_strength", 1.0)
        
        # Get render passes to render
        render_passes = job.get_setting("render_passes", ["beauty"])
        if not render_passes:
            render_passes = ["beauty"]
        
        # Build pass configuration
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
        
        return f'''# Wane Render Script - Turntable (Multi-Pass)
# Renders all passes simultaneously, then organizes into folders
import mset
import json
import os
import sys
import glob
import shutil
import re

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error="", frame=0, total={total_frames}, 
                   current_pass="", current_pass_num=0, total_passes=1, pass_frame=0, pass_total_frames={total_frames}):
    try:
        data = {{
            "status": status, 
            "progress": progress, 
            "message": message, 
            "error": error, 
            "frame": frame, 
            "total_frames": total,
            "current_pass": current_pass,
            "current_pass_num": current_pass_num,
            "total_passes": total_passes,
            "pass_frame": pass_frame,
            "pass_total_frames": pass_total_frames
        }}
        with open(r"{progress_path}", 'w') as f:
            json.dump(data, f)
    except Exception as e:
        log(f"Progress update error: {{e}}")

def render_turntable():
    try:
        # Pass configuration
        passes = {pass_config_str}
        total_passes = len(passes)
        frames_per_pass = {total_frames}
        total_files_expected = frames_per_pass * total_passes
        
        log(f"Starting turntable render: {{total_passes}} pass(es), {{frames_per_pass}} frames each")
        log(f"Total files expected: {{total_files_expected}}")
        update_progress("loading", 0, "Loading scene...")
        
        log(f"Loading scene: {scene_path}")
        mset.loadScene(r"{scene_path}")
        log("Scene loaded successfully")
        
        update_progress("configuring", 2, "Configuring render...")
        
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
            turntable.spinRate = {spin_sign}(360.0 / {total_frames}) * 30.0
            log(f"Turntable spin rate: {{turntable.spinRate}}")
        else:
            log("WARNING: No turntable found in scene!")
        
        # Find render object
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        if not render_obj:
            raise Exception("No RenderObject found in scene!")
        
        # Initialize pass tracking variables (will be populated when enabling passes)
        enabled_names = []
        enabled_pass_to_folder = {{}}
        
        # Configure video output
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        if hasattr(render_obj, 'videos'):
            videos = render_obj.videos
            videos.outputPath = output_dir
            videos.width = {job.res_width}
            videos.height = {job.res_height}
            videos.samples = {samples}
            videos.transparency = {str(use_transparency)}
            videos.format = "PNG"
            
            # Denoising
            try:
                videos.rayTraceDenoiseMode = "{denoise_mode}"
                videos.rayTraceDenoiseQuality = "{denoise_quality}"
                videos.rayTraceDenoiseStrength = {denoise_strength}
            except:
                pass
            
            log(f"Output: {{output_dir}}")
            log(f"Resolution: {{videos.width}}x{{videos.height}}, Samples: {{videos.samples}}")
        
        # Enable ALL selected passes at once
        # Marmoset renders all enabled passes simultaneously
        if hasattr(render_obj, 'renderPasses'):
            render_passes_list = render_obj.renderPasses
            available_passes = [rp.renderPass for rp in render_passes_list]
            log(f"")
            log(f"=== RENDER PASS CONFIGURATION ===")
            log(f"Available passes in scene ({{len(available_passes)}}):")
            for ap in available_passes:
                log(f"  - '{{ap}}'")
            
            # Build list of target pass names
            target_passes = []
            for p in passes:
                target = p["pass"] if p["pass"] else "Full Quality"
                target_passes.append(target)
            
            log(f"")
            log(f"Requested passes ({{len(target_passes)}}):")
            for tp in target_passes:
                log(f"  - '{{tp}}'")
            
            # Helper function for fuzzy matching
            def normalize_pass_name(name):
                """Normalize pass name for comparison: lowercase, remove spaces"""
                return name.lower().replace(" ", "").replace("(", "").replace(")", "")
            
            def find_matching_pass(target, available_list):
                """Find a matching pass using exact match first, then fuzzy match"""
                # Exact match first
                if target in available_list:
                    return target
                
                # Fuzzy match: normalize both and compare
                target_norm = normalize_pass_name(target)
                for avail in available_list:
                    if normalize_pass_name(avail) == target_norm:
                        return avail
                
                # Try partial matching for common abbreviations
                abbreviations = {{
                    "ao": ["ambient occlusion", "ambientocclusion"],
                    "ambient occlusion": ["ao"],
                    "full quality": ["beauty", "fullquality"],
                    "beauty": ["full quality", "fullquality"],
                }}
                
                for avail in available_list:
                    avail_lower = avail.lower()
                    target_lower = target.lower()
                    # Check if abbreviation maps to this target
                    if target_lower in abbreviations:
                        for abbrev in abbreviations[target_lower]:
                            if abbrev in avail_lower or avail_lower in abbrev:
                                return avail
                
                return None
            
            log(f"")
            log(f"Enabling passes...")
            
            # First, disable ALL passes
            for rp in render_passes_list:
                rp.enabled = False
            
            # Then enable only the requested passes (with fuzzy matching)
            # Keep track of mapping: marmoset_name -> folder_id for file organization
            enabled_count = 0
            enabled_names = []
            enabled_pass_to_folder = {{}}  # Maps actual enabled pass name -> our folder ID
            
            for i, target in enumerate(target_passes):
                folder_id = passes[i]["id"] if i < len(passes) else f"pass_{{i}}"
                matched = find_matching_pass(target, available_passes)
                if matched:
                    # Find and enable this pass
                    for rp in render_passes_list:
                        if rp.renderPass == matched:
                            rp.enabled = True
                            enabled_count += 1
                            enabled_names.append(matched)
                            enabled_pass_to_folder[matched] = folder_id
                            if matched == target:
                                log(f"  [OK] ENABLED: '{{matched}}' -> {{folder_id}}/")
                            else:
                                log(f"  [OK] ENABLED: '{{matched}}' (matched from '{{target}}') -> {{folder_id}}/")
                            break
                else:
                    log(f"  [X] NOT FOUND: '{{target}}' - no matching pass in scene")
            
            log(f"")
            log(f"Summary: Enabled {{enabled_count}} of {{len(target_passes)}} requested passes")
            if enabled_count != len(target_passes):
                log(f"WARNING: Some passes were not found! Check that they exist in your scene.")
            log(f"Enabled passes: {{enabled_names}}")
            log(f"=================================")
            log(f"")
        
        # Set timeline
        timeline = mset.getTimeline()
        if timeline:
            timeline.selectionStart = 1
            timeline.selectionEnd = {total_frames}
            log(f"Timeline: frames 1-{total_frames}")
        
        update_progress("rendering", 5, "Rendering all passes...")
        
        log("=" * 50)
        log("Starting renderVideos() - all passes render simultaneously")
        log("=" * 50)
        mset.renderVideos()
        log("renderVideos() complete!")
        
        # Organize files into pass-specific subfolders
        update_progress("organizing", 95, "Organizing files into folders...")
        log("")
        log("Organizing output files into pass folders...")
        
        # Marmoset naming: tbrender_{{Camera}}_{{PassName}}_{{FrameNum}}.png
        # PassName has spaces removed: "Full Quality" -> "FullQuality"
        
        # Build filename -> folder mapping from enabled_pass_to_folder
        # (which was populated during pass enabling)
        pass_folder_map = {{}}
        for enabled_name, folder_id in enabled_pass_to_folder.items():
            # Convert to filename format (remove spaces)
            filename_pass = enabled_name.replace(" ", "")
            pass_folder_map[filename_pass] = folder_id
            log(f"  '{{filename_pass}}' -> {{folder_id}}/")
        
        log(f"Pass name mapping: {{pass_folder_map}}")
        
        # Find all rendered files
        all_files = glob.glob(os.path.join(output_dir, "tbrender_*.png"))
        log(f"Found {{len(all_files)}} rendered files")
        
        # Move files to appropriate subfolders
        moved_count = 0
        unmatched_files = []
        for filepath in all_files:
            filename = os.path.basename(filepath)
            
            # Parse filename: tbrender_CameraName_PassName_FrameNum.png
            # Example: tbrender_Main Camera_FullQuality_00001.png
            # Note: Camera name can have spaces!
            
            # Find which pass this file belongs to
            dest_folder = None
            for filename_pass, folder_id in pass_folder_map.items():
                if f"_{{filename_pass}}_" in filename:
                    dest_folder = folder_id
                    break
            
            if dest_folder:
                # Create subfolder if needed
                subfolder = os.path.join(output_dir, dest_folder)
                os.makedirs(subfolder, exist_ok=True)
                
                # Move file
                dest_path = os.path.join(subfolder, filename)
                shutil.move(filepath, dest_path)
                moved_count += 1
            else:
                unmatched_files.append(filename)
        
        if unmatched_files:
            log(f"Could not determine pass for {{len(unmatched_files)}} files:")
            for uf in unmatched_files[:5]:  # Show first 5
                log(f"  - {{uf}}")
            if len(unmatched_files) > 5:
                log(f"  ... and {{len(unmatched_files) - 5}} more")
        
        log(f"Moved {{moved_count}} files into {{len(pass_folder_map)}} folders")
        
        log("")
        log("Turntable render complete!")
        update_progress("complete", 100, "Render complete", frame=total_files_expected)
        
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
        """Generate script for animation sequence render with multi-pass support.
        
        Marmoset renders ALL enabled passes simultaneously in one renderVideos() call.
        Files are named: tbrender_{Camera}_{PassName}_{FrameNum}.png
        After render, we organize files into pass-specific subfolders.
        """
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')
        
        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        
        # Denoising settings
        denoise_mode = job.get_setting("denoise_mode", "gpu")
        denoise_quality = job.get_setting("denoise_quality", "high")
        denoise_strength = job.get_setting("denoise_strength", 1.0)
        
        # Get render passes to render
        render_passes = job.get_setting("render_passes", ["beauty"])
        if not render_passes:
            render_passes = ["beauty"]
        
        # Build pass configuration
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
        
        return f'''# Wane Render Script - Animation (Multi-Pass)
# Renders all passes simultaneously, then organizes into folders
import mset
import json
import os
import sys
import glob
import shutil

def log(msg):
    print(f"[Wane] {{msg}}")
    sys.stdout.flush()

def update_progress(status, progress=0, message="", error="", frame=0, total={job.frame_end},
                   current_pass="", current_pass_num=0, total_passes=1, pass_frame=0, pass_total_frames={job.frame_end}):
    try:
        data = {{
            "status": status, 
            "progress": progress, 
            "message": message, 
            "error": error, 
            "frame": frame, 
            "total_frames": total,
            "current_pass": current_pass,
            "current_pass_num": current_pass_num,
            "total_passes": total_passes,
            "pass_frame": pass_frame,
            "pass_total_frames": pass_total_frames
        }}
        with open(r"{progress_path}", 'w') as f:
            json.dump(data, f)
    except Exception as e:
        log(f"Progress update error: {{e}}")

def render_animation():
    try:
        # Pass configuration
        passes = {pass_config_str}
        total_passes = len(passes)
        frames_per_pass = {job.frame_end}
        total_files_expected = frames_per_pass * total_passes
        
        log(f"Starting animation render: {{total_passes}} pass(es), {{frames_per_pass}} frames each")
        log(f"Total files expected: {{total_files_expected}}")
        update_progress("loading", 0, "Loading scene...")
        
        log(f"Loading scene: {scene_path}")
        mset.loadScene(r"{scene_path}")
        log("Scene loaded successfully")
        
        update_progress("configuring", 2, "Configuring render...")
        
        # Find render object
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == 'RenderObject':
                render_obj = obj
                break
        
        if not render_obj:
            raise Exception("No RenderObject found in scene!")
        
        # Initialize pass tracking variables (will be populated when enabling passes)
        enabled_names = []
        enabled_pass_to_folder = {{}}
        
        # Configure video output
        output_dir = r"{output_folder}"
        os.makedirs(output_dir, exist_ok=True)
        
        if hasattr(render_obj, 'videos'):
            videos = render_obj.videos
            videos.outputPath = output_dir
            videos.width = {job.res_width}
            videos.height = {job.res_height}
            videos.samples = {samples}
            videos.transparency = {str(use_transparency)}
            videos.format = "PNG"
            
            # Denoising
            try:
                videos.rayTraceDenoiseMode = "{denoise_mode}"
                videos.rayTraceDenoiseQuality = "{denoise_quality}"
                videos.rayTraceDenoiseStrength = {denoise_strength}
            except:
                pass
            
            log(f"Output: {{output_dir}}")
            log(f"Resolution: {{videos.width}}x{{videos.height}}, Samples: {{videos.samples}}")
        
        # Set timeline for animation frames
        timeline = mset.getTimeline()
        if timeline:
            timeline.selectionStart = {start_frame}
            timeline.selectionEnd = {job.frame_end}
            log(f"Timeline: frames {start_frame}-{job.frame_end}")
        
        # Enable ALL selected passes at once
        # Marmoset renders all enabled passes simultaneously
        if hasattr(render_obj, 'renderPasses'):
            render_passes_list = render_obj.renderPasses
            available_passes = [rp.renderPass for rp in render_passes_list]
            log(f"")
            log(f"=== RENDER PASS CONFIGURATION ===")
            log(f"Available passes in scene ({{len(available_passes)}}):")
            for ap in available_passes:
                log(f"  - '{{ap}}'")
            
            # Build list of target pass names
            target_passes = []
            for p in passes:
                target = p["pass"] if p["pass"] else "Full Quality"
                target_passes.append(target)
            
            log(f"")
            log(f"Requested passes ({{len(target_passes)}}):")
            for tp in target_passes:
                log(f"  - '{{tp}}'")
            
            # Helper function for fuzzy matching
            def normalize_pass_name(name):
                """Normalize pass name for comparison: lowercase, remove spaces"""
                return name.lower().replace(" ", "").replace("(", "").replace(")", "")
            
            def find_matching_pass(target, available_list):
                """Find a matching pass using exact match first, then fuzzy match"""
                # Exact match first
                if target in available_list:
                    return target
                
                # Fuzzy match: normalize both and compare
                target_norm = normalize_pass_name(target)
                for avail in available_list:
                    if normalize_pass_name(avail) == target_norm:
                        return avail
                
                # Try partial matching for common abbreviations
                abbreviations = {{
                    "ao": ["ambient occlusion", "ambientocclusion"],
                    "ambient occlusion": ["ao"],
                    "full quality": ["beauty", "fullquality"],
                    "beauty": ["full quality", "fullquality"],
                }}
                
                for avail in available_list:
                    avail_lower = avail.lower()
                    target_lower = target.lower()
                    # Check if abbreviation maps to this target
                    if target_lower in abbreviations:
                        for abbrev in abbreviations[target_lower]:
                            if abbrev in avail_lower or avail_lower in abbrev:
                                return avail
                
                return None
            
            log(f"")
            log(f"Enabling passes...")
            
            # First, disable ALL passes
            for rp in render_passes_list:
                rp.enabled = False
            
            # Then enable only the requested passes (with fuzzy matching)
            # Keep track of mapping: marmoset_name -> folder_id for file organization
            enabled_count = 0
            enabled_names = []
            enabled_pass_to_folder = {{}}  # Maps actual enabled pass name -> our folder ID
            
            for i, target in enumerate(target_passes):
                folder_id = passes[i]["id"] if i < len(passes) else f"pass_{{i}}"
                matched = find_matching_pass(target, available_passes)
                if matched:
                    # Find and enable this pass
                    for rp in render_passes_list:
                        if rp.renderPass == matched:
                            rp.enabled = True
                            enabled_count += 1
                            enabled_names.append(matched)
                            enabled_pass_to_folder[matched] = folder_id
                            if matched == target:
                                log(f"  [OK] ENABLED: '{{matched}}' -> {{folder_id}}/")
                            else:
                                log(f"  [OK] ENABLED: '{{matched}}' (matched from '{{target}}') -> {{folder_id}}/")
                            break
                else:
                    log(f"  [X] NOT FOUND: '{{target}}' - no matching pass in scene")
            
            log(f"")
            log(f"Summary: Enabled {{enabled_count}} of {{len(target_passes)}} requested passes")
            if enabled_count != len(target_passes):
                log(f"WARNING: Some passes were not found! Check that they exist in your scene.")
            log(f"Enabled passes: {{enabled_names}}")
            log(f"=================================")
            log(f"")
        
        update_progress("rendering", 5, "Rendering all passes...")
        
        log("=" * 50)
        log("Starting renderVideos() - all passes render simultaneously")
        log("=" * 50)
        mset.renderVideos()
        log("renderVideos() complete!")
        
        # Organize files into pass-specific subfolders
        update_progress("organizing", 95, "Organizing files into folders...")
        log("")
        log("Organizing output files into pass folders...")
        
        # Build filename -> folder mapping from enabled_pass_to_folder
        # (which was populated during pass enabling)
        pass_folder_map = {{}}
        for enabled_name, folder_id in enabled_pass_to_folder.items():
            # Convert to filename format (remove spaces)
            filename_pass = enabled_name.replace(" ", "")
            pass_folder_map[filename_pass] = folder_id
            log(f"  '{{filename_pass}}' -> {{folder_id}}/")
        
        log(f"Pass name mapping: {{pass_folder_map}}")
        
        # Find all rendered files
        all_files = glob.glob(os.path.join(output_dir, "tbrender_*.png"))
        log(f"Found {{len(all_files)}} rendered files")
        
        # Move files to appropriate subfolders
        moved_count = 0
        unmatched_files = []
        for filepath in all_files:
            filename = os.path.basename(filepath)
            
            # Find which pass this file belongs to
            dest_folder = None
            for filename_pass, folder_id in pass_folder_map.items():
                if f"_{{filename_pass}}_" in filename:
                    dest_folder = folder_id
                    break
            
            if dest_folder:
                subfolder = os.path.join(output_dir, dest_folder)
                os.makedirs(subfolder, exist_ok=True)
                dest_path = os.path.join(subfolder, filename)
                shutil.move(filepath, dest_path)
                moved_count += 1
            else:
                unmatched_files.append(filename)
        
        if unmatched_files:
            log(f"Could not determine pass for {{len(unmatched_files)}} files:")
            for uf in unmatched_files[:5]:  # Show first 5
                log(f"  - {{uf}}")
            if len(unmatched_files) > 5:
                log(f"  ... and {{len(unmatched_files) - 5}} more")
        
        log(f"Moved {{moved_count}} files into {{len(pass_folder_map)}} folders")
        
        log("")
        log("Animation render complete!")
        update_progress("complete", 100, "Render complete", frame=total_files_expected)
        
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
        """Start background thread to monitor progress by watching output files and progress file.
        
        For Marmoset multi-pass turntable/animation:
        - All passes render simultaneously in one renderVideos() call
        - Files named: tbrender_{Camera}_{PassName}_{FrameNum}.png
        - During render: all files in main output folder
        - After render: files organized into pass subfolders
        """
        self._monitoring = True
        
        def monitor():
            import glob
            import time
            
            last_file_count = 0
            frames_per_pass = job.frame_end if job.is_animation else 1
            
            # Get render passes info from job settings
            render_passes = job.get_setting("render_passes", ["beauty"])
            total_passes = len(render_passes) if render_passes else 1
            total_files_expected = frames_per_pass * total_passes
            
            # Update job with total passes info
            job.total_passes = total_passes
            job.pass_total_frames = frames_per_pass
            
            base_output = job.output_folder
            
            while self._monitoring and not self.is_cancelling:
                # Read progress file for status
                progress = self._read_progress_file()
                
                if progress:
                    status = progress.get("status", "")
                    message = progress.get("message", "")
                    
                    if on_log and message and message != self._last_message:
                        on_log(message)
                        self._last_message = message
                    
                    if status == "complete":
                        on_progress(total_files_expected, "Render complete")
                        break
                    elif status == "error":
                        break
                    elif status == "organizing":
                        # Files being moved to subfolders - show organizing status
                        job.current_pass = "Organizing"
                        on_progress(total_files_expected, "Organizing files...")
                        continue
                
                # Count files - Marmoset renders all passes simultaneously
                # Files are named: tbrender_{Camera}_{PassName}_{FrameNum}.png
                try:
                    # During rendering: files are in main output folder
                    main_files = glob.glob(os.path.join(base_output, "tbrender_*.png"))
                    main_count = len(main_files)
                    
                    # After organizing: files are in subfolders
                    subfolder_count = 0
                    for pass_id in render_passes:
                        pass_folder = os.path.join(base_output, pass_id)
                        if os.path.exists(pass_folder):
                            subfolder_count += len(glob.glob(os.path.join(pass_folder, "*.png")))
                    
                    # Total is whichever has files (during render = main, after = subfolders)
                    total_file_count = main_count + subfolder_count
                    
                    if total_file_count > last_file_count:
                        last_file_count = total_file_count
                        
                        # Calculate progress percentage
                        if total_files_expected > 0:
                            progress_pct = min(int((total_file_count / total_files_expected) * 100), 99)
                        else:
                            progress_pct = 0
                        
                        # Update job tracking
                        job.current_frame = total_file_count
                        job.progress = progress_pct
                        
                        # Calculate which "frame" we're on (files / passes = frame number)
                        if total_passes > 0:
                            effective_frame = total_file_count // total_passes
                            job.rendering_frame = effective_frame
                            job.pass_frame = effective_frame
                        
                        if on_log:
                            on_log(f"Rendered {total_file_count}/{total_files_expected} files ({total_passes} passes x {frames_per_pass} frames)")
                        
                        on_progress(total_file_count, "Rendering")
                        
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

