"""
Wain Marmoset Engine - v2.18.0
=========================================

Multi-pass render support with scene probing for camera and pass detection.
Uses RenderObject.renderImages() for reliable rendering of ALL pass types
(including geometry passes like Wireframe, Depth, Normals, Position that
renderCamera(viewportPass=...) cannot handle).

Falls back to renderCamera() only when no RenderObject is found in scene.
"""

import os
import sys
import json
import subprocess
import threading
import tempfile
import time
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

    # Pass names must match Toolbag's RenderPassOptions.renderPass strings.
    # "pass" field = the string set on RenderPassOptions.renderPass.
    # Beauty = "Full Quality". Rendered via RenderObject.renderImages()
    # one pass at a time for per-pass progress tracking.
    # See: https://www.marmoset.co/python/reference5.html
    RENDER_PASSES = [
        # Common
        {"id": "beauty", "name": "Beauty", "pass": "Full Quality", "category": "Common"},
        {"id": "wireframe", "name": "Wireframe", "pass": "Wireframe", "category": "Common"},
        {"id": "unlit", "name": "Unlit", "pass": "Unlit", "category": "Common"},
        # Geometry
        {"id": "alpha_mask", "name": "Alpha Mask", "pass": "Alpha Mask", "category": "Geometry"},
        {"id": "depth", "name": "Depth", "pass": "Depth", "category": "Geometry"},
        {"id": "normals", "name": "Normals", "pass": "Normals", "category": "Geometry"},
        {"id": "position", "name": "Position", "pass": "Position", "category": "Geometry"},
        {"id": "uv_islands", "name": "UV Islands", "pass": "UV Islands", "category": "Geometry"},
        # Lighting
        {"id": "ambient_occlusion", "name": "AO", "pass": "Ambient Occlusion", "category": "Lighting"},
        {"id": "lighting_direct", "name": "Direct Light", "pass": "Lighting (Direct)", "category": "Lighting"},
        {"id": "lighting_indirect", "name": "Indirect Light", "pass": "Lighting (Indirect)", "category": "Lighting"},
        {"id": "shadow", "name": "Shadow", "pass": "Shadow", "category": "Lighting"},
        {"id": "emissive", "name": "Emissive", "pass": "Emissive", "category": "Lighting"},
        {"id": "reflection", "name": "Reflection", "pass": "Reflection", "category": "Lighting"},
        # Material
        {"id": "albedo", "name": "Albedo", "pass": "Albedo", "category": "Material"},
        {"id": "metalness", "name": "Metalness", "pass": "Metalness", "category": "Material"},
        {"id": "roughness", "name": "Roughness", "pass": "Roughness", "category": "Material"},
        {"id": "cavity", "name": "Cavity", "pass": "Cavity", "category": "Material"},
        {"id": "curvature", "name": "Curvature", "pass": "Curvature", "category": "Material"},
        {"id": "thickness", "name": "Thickness", "pass": "Thickness", "category": "Material"},
        {"id": "transparency", "name": "Transparency", "pass": "Transparency", "category": "Material"},
        {"id": "subsurface", "name": "Subsurface", "pass": "Subsurface", "category": "Material"},
        # IDs
        {"id": "matte", "name": "Matte", "pass": "Matte", "category": "ID"},
        {"id": "object_id", "name": "Object ID", "pass": "Object ID", "category": "ID"},
        {"id": "group_id", "name": "Group ID", "pass": "Group ID", "category": "ID"},
        {"id": "material_id", "name": "Material ID", "pass": "Material ID", "category": "ID"},
    ]

    def __init__(self):
        super().__init__()
        self._temp_script_path: Optional[str] = None
        self._progress_file_path: Optional[str] = None
        self._monitoring = False
        self._on_log = None
        self.scan_installed_versions()

    def _log(self, msg: str):
        """Log a message."""
        if self._on_log:
            self._on_log(f"[Marmoset] {msg}")
        print(f"[Marmoset] {msg}")

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

    def _generate_probe_script(self, file_path: str, output_json_path: str) -> str:
        """Generate a Python script for Toolbag to probe scene info."""
        scene_path = file_path.replace('\\', '\\\\')
        output_path = output_json_path.replace('\\', '\\\\')

        return f'''# Wain Marmoset Probe Script
# Auto-generated - do not edit
import mset
import json
import os
import sys

SCENE_PATH = r"{scene_path}"
OUTPUT_PATH = r"{output_path}"

def log(msg):
    print(f"[Wain Probe] {{msg}}")
    sys.stdout.flush()

def main():
    result = {{
        "cameras": [],
        "active_camera": "",
        "resolution_x": 1920,
        "resolution_y": 1080,
        "samples": 256,
        "frame_start": 1,
        "frame_end": 1,
        "total_frames": 1,
        "has_animation": False,
        "has_turntable": False,
        "render_passes": [],
    }}

    try:
        log(f"Loading scene: {{SCENE_PATH}}")
        mset.loadScene(SCENE_PATH)
        log("Scene loaded")

        # === Camera Discovery ===
        try:
            all_objects = mset.getAllObjects()
            for obj in all_objects:
                try:
                    obj_type = type(obj).__name__
                    if "Camera" in obj_type:
                        cam_name = getattr(obj, "name", str(obj))
                        if cam_name and cam_name not in result["cameras"]:
                            result["cameras"].append(cam_name)
                            log(f"Found camera: {{cam_name}} ({{obj_type}})")
                except Exception:
                    pass
        except Exception as e:
            log(f"getAllObjects() failed: {{e}}")

        # Try to get the active/main camera
        try:
            cam = mset.getCamera()
            if cam:
                cam_name = getattr(cam, "name", "")
                if cam_name:
                    result["active_camera"] = cam_name
                    if cam_name not in result["cameras"]:
                        result["cameras"].insert(0, cam_name)
                    log(f"Active camera: {{cam_name}}")
        except Exception as e:
            log(f"getCamera() not available: {{e}}")

        if not result["cameras"]:
            result["cameras"] = ["Main Camera"]
        if not result["active_camera"]:
            result["active_camera"] = result["cameras"][0]

        # === Render Pass Discovery (via RenderObject) ===
        try:
            render_obj = None
            for obj in mset.getAllObjects():
                if type(obj).__name__ == "RenderObject":
                    render_obj = obj
                    break

            if render_obj is not None and hasattr(render_obj, 'renderPasses'):
                for rp in render_obj.renderPasses:
                    pass_name = getattr(rp, 'renderPass', '')
                    pass_enabled = getattr(rp, 'enabled', True)
                    if pass_name:
                        result["render_passes"].append({{
                            "name": pass_name,
                            "enabled": pass_enabled,
                        }})
                        log(f"Found render pass: {{pass_name}} (enabled={{pass_enabled}})")
                log(f"Total render passes found: {{len(result['render_passes'])}}")
            else:
                log("No RenderObject found in scene")
        except Exception as e:
            log(f"Render pass discovery: {{e}}")

        # === Timeline / Animation ===
        try:
            for obj in mset.getAllObjects():
                obj_type = type(obj).__name__
                if "Timeline" in obj_type or "timeline" in obj_type.lower():
                    length = getattr(obj, "length", 0)
                    fps = getattr(obj, "fps", 30)
                    if length and length > 0:
                        result["has_animation"] = True
                        result["frame_end"] = max(1, int(length * fps))
                        result["total_frames"] = result["frame_end"]
                        log(f"Animation: {{length}}s @ {{fps}}fps = {{result['frame_end']}} frames")
                    break
        except Exception as e:
            log(f"Timeline discovery failed: {{e}}")

    except Exception as e:
        log(f"Error during probe: {{e}}")
        import traceback
        traceback.print_exc()

    # Write results
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(result, f, indent=2)
        log(f"Probe results written to: {{OUTPUT_PATH}}")
    except Exception as e:
        log(f"Error writing results: {{e}}")

    log("Quitting Toolbag...")
    mset.quit()

main()
'''

    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """Probe a Marmoset scene for cameras, passes, resolution, and animation."""
        default_info = {
            "cameras": ["Main Camera"], "active_camera": "Main Camera",
            "resolution_x": 1920, "resolution_y": 1080, "renderer": "Ray Tracing",
            "samples": 256, "frame_start": 1, "frame_end": 1, "total_frames": 1,
            "has_animation": False, "has_turntable": False,
            "render_passes": [],
        }

        toolbag_exe = self.get_best_toolbag()
        if not toolbag_exe or not os.path.exists(file_path):
            return default_info

        # Set up temp files for probe
        probe_id = os.path.basename(file_path).replace('.', '_')
        script_dir = tempfile.gettempdir()
        probe_script_path = os.path.join(script_dir, f"_wain_probe_{probe_id}.py")
        probe_output_path = os.path.join(script_dir, f"_wain_probe_{probe_id}.json")

        # Clean up any existing output
        if os.path.exists(probe_output_path):
            try:
                os.unlink(probe_output_path)
            except Exception:
                pass

        # Generate and write probe script
        script_code = self._generate_probe_script(file_path, probe_output_path)
        try:
            with open(probe_script_path, 'w', encoding='utf-8') as f:
                f.write(script_code)
        except Exception as e:
            print(f"[Marmoset] Failed to write probe script: {e}")
            return default_info

        # Run Toolbag with probe script
        try:
            print(f"[Marmoset] Probing scene: {file_path}")

            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

            # Clean environment: remove Wain's Qt/Chromium vars
            clean_env = os.environ.copy()
            for key in ['QTWEBENGINE_CHROMIUM_FLAGS', 'QT_QUICK_BACKEND',
                        'QTWEBENGINE_DISABLE_SANDBOX', 'QT_API', 'PYWEBVIEW_GUI']:
                clean_env.pop(key, None)

            result = subprocess.run(
                [toolbag_exe, '-hide', probe_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                startupinfo=startupinfo,
                creationflags=0,
                timeout=30,
                env=clean_env
            )

            print(f"[Marmoset] Probe exit code: {result.returncode}")

            # Read probe results
            if os.path.exists(probe_output_path):
                with open(probe_output_path, 'r', encoding='utf-8') as f:
                    probe_data = json.load(f)

                info = default_info.copy()

                if probe_data.get('cameras'):
                    info['cameras'] = probe_data['cameras']
                if probe_data.get('active_camera'):
                    info['active_camera'] = probe_data['active_camera']
                if probe_data.get('resolution_x'):
                    info['resolution_x'] = probe_data['resolution_x']
                if probe_data.get('resolution_y'):
                    info['resolution_y'] = probe_data['resolution_y']
                if probe_data.get('samples'):
                    info['samples'] = probe_data['samples']
                if probe_data.get('frame_end', 1) > 1:
                    info['frame_end'] = probe_data['frame_end']
                    info['total_frames'] = probe_data.get('total_frames', probe_data['frame_end'])
                    info['has_animation'] = probe_data.get('has_animation', True)
                if probe_data.get('render_passes'):
                    info['render_passes'] = probe_data['render_passes']

                n_cams = len(info['cameras'])
                n_passes = len(info.get('render_passes', []))
                print(f"[Marmoset] Probe found: {n_cams} cameras, {n_passes} scene passes")
                return info
            else:
                print("[Marmoset] Probe output file not found")
                return default_info

        except subprocess.TimeoutExpired:
            print("[Marmoset] Probe timed out after 30s")
            return default_info
        except Exception as e:
            print(f"[Marmoset] Probe error: {e}")
            return default_info
        finally:
            for path in [probe_script_path, probe_output_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

    def start_render(self, job, start_frame: int, on_progress, on_complete, on_error, on_log=None):
        toolbag_exe = self.get_best_toolbag()
        if not toolbag_exe:
            on_error("No Marmoset Toolbag installation found")
            return

        if not os.path.exists(job.file_path):
            on_error(f"Scene file not found: {job.file_path}")
            return

        self.is_cancelling = False
        self._on_log = on_log
        os.makedirs(job.output_folder, exist_ok=True)

        # Use temp directory for script/progress files
        script_dir = tempfile.gettempdir()
        self._temp_script_path = os.path.join(script_dir, f"_wain_render_{job.id}.py")
        self._progress_file_path = os.path.join(script_dir, f"_wain_progress_{job.id}.json")

        self._log(f"Script path: {self._temp_script_path}")
        self._log(f"Progress file: {self._progress_file_path}")

        # Set total passes on the job for UI display
        render_passes = job.get_setting("render_passes", ["beauty"])
        job.total_passes = len(render_passes)
        self._log(f"Render passes ({len(render_passes)}): {render_passes}")

        # Generate render script
        script_code = self._generate_render_script(job, start_frame)

        try:
            with open(self._temp_script_path, 'w', encoding='utf-8') as f:
                f.write(script_code)
            self._log(f"Wrote render script ({len(script_code)} bytes)")

            def render_thread():
                try:
                    startupinfo = None
                    creation_flags = 0
                    if sys.platform == 'win32':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = 0
                        creation_flags = 0

                    cmd = [toolbag_exe, '-hide', self._temp_script_path]
                    self._log(f"Command: {' '.join(cmd)}")
                    self._log(f"Starting Toolbag...")

                    # Clean environment: remove Wain's Qt/Chromium vars
                    # so they don't interfere with Toolbag's own GPU usage
                    clean_env = os.environ.copy()
                    for key in ['QTWEBENGINE_CHROMIUM_FLAGS', 'QT_QUICK_BACKEND',
                                'QTWEBENGINE_DISABLE_SANDBOX', 'QT_API', 'PYWEBVIEW_GUI']:
                        clean_env.pop(key, None)

                    self.current_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        startupinfo=startupinfo,
                        creationflags=creation_flags,
                        env=clean_env
                    )

                    self._log(f"Started Toolbag PID: {self.current_process.pid}")

                    # Start a thread to read Toolbag's stdout for script log output
                    def _read_stdout():
                        try:
                            for line in iter(self.current_process.stdout.readline, b''):
                                text = line.decode('utf-8', errors='replace').rstrip()
                                if text:
                                    self._log(f"Script: {text}")
                        except Exception:
                            pass
                    stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
                    stdout_thread.start()

                    # Monitor progress via JSON file
                    self._monitoring = True
                    last_status = ""
                    last_pass_key = ""
                    pass_render_start = time.time()
                    startup_timeout = 60
                    startup_start = time.time()
                    got_first_progress = False
                    last_log_pass = ""

                    while self._monitoring and not self.is_cancelling:
                        poll_result = self.current_process.poll()
                        if poll_result is not None:
                            self._log(f"Toolbag exited with code: {poll_result}")
                            break

                        progress_data = self._read_progress_file()

                        if progress_data:
                            got_first_progress = True
                            status = progress_data.get("status", "")
                            progress_pct = progress_data.get("progress", 0)
                            current = progress_data.get("current", 0)
                            total = progress_data.get("total", 1)
                            error_msg = progress_data.get("error", "")

                            # Multi-pass tracking
                            pass_name = progress_data.get("pass_name", "")
                            pass_num = progress_data.get("pass_num", 0)
                            total_passes = progress_data.get("total_passes", 1)

                            if pass_name:
                                job.current_pass = pass_name
                            if pass_num > 0:
                                job.current_pass_num = pass_num
                            if total_passes > 0:
                                job.total_passes = total_passes

                            # Track when the current pass changed
                            pass_key = f"{pass_num}:{pass_name}"
                            if pass_key != last_pass_key:
                                last_pass_key = pass_key
                                pass_render_start = time.time()

                            pass_elapsed = int(time.time() - pass_render_start)

                            # Log status changes and periodic pass updates
                            if status != last_status:
                                if pass_name:
                                    self._log(f"Status: {status} - {pass_name} ({pass_num}/{total_passes})")
                                else:
                                    self._log(f"Status: {status} ({progress_pct}%)")
                                last_status = status
                            elif status == "rendering" and pass_name != last_log_pass:
                                self._log(f"Rendering: {pass_name} ({pass_num}/{total_passes})")
                                last_log_pass = pass_name

                            # Interpolate progress within the current pass range
                            # so the UI shows movement even while renderCamera() blocks
                            if status == "rendering" and total_passes > 0 and pass_num > 0:
                                base_pct = int(((pass_num - 1) / total_passes) * 100)
                                next_pct = int((pass_num / total_passes) * 100)
                                pass_range = next_pct - base_pct

                                # Asymptotic fill: approaches 95% of range over time
                                # t=0: 0%, t=15s: ~33%, t=30s: ~50%, t=60s: ~67%
                                fill_ratio = min(0.95, 1.0 - 1.0 / (1.0 + pass_elapsed / 30.0))
                                interpolated = base_pct + int(pass_range * fill_ratio)

                                # Use the higher of script-reported and interpolated
                                job.progress = min(max(progress_pct, interpolated), 99)
                            else:
                                job.progress = min(progress_pct, 99)

                            job.current_frame = current

                            if status == "loading":
                                on_progress(0, "Loading scene...")
                            elif status == "rendering":
                                if pass_name:
                                    on_progress(current, f"Rendering {pass_name} ({pass_num}/{total_passes}) [{pass_elapsed}s]")
                                else:
                                    on_progress(current, f"Rendering... {progress_pct}%")
                            elif status == "switching_camera":
                                on_progress(0, "Switching camera...")
                            elif status == "complete":
                                self._log("Render complete!")
                                break
                            elif status == "error":
                                self._log(f"Render error: {error_msg}")
                                on_error(error_msg or "Unknown error during render")
                                self._cleanup()
                                return
                        else:
                            if not got_first_progress:
                                elapsed = time.time() - startup_start
                                if elapsed > startup_timeout:
                                    self._log(f"Startup timeout after {elapsed:.1f}s")
                                    on_error(f"Toolbag did not start rendering within {startup_timeout}s")
                                    self._cleanup()
                                    return
                                elif int(elapsed) % 5 == 0:
                                    self._log(f"Waiting for Toolbag startup... ({elapsed:.0f}s)")

                        time.sleep(0.25)

                    return_code = self.current_process.wait(timeout=10)
                    self._log(f"Final exit code: {return_code}")

                    if self.is_cancelling:
                        self._log("Render cancelled by user")
                        self._cleanup()
                        return

                    # Read final progress and update job before completing
                    final_status = self._read_progress_file()
                    if final_status:
                        if final_status.get("total_passes"):
                            job.total_passes = final_status["total_passes"]
                        if final_status.get("pass_num"):
                            job.current_pass_num = final_status["pass_num"]

                    if final_status and final_status.get("status") == "complete":
                        on_complete()
                    elif final_status and final_status.get("status") == "error":
                        on_error(final_status.get("error", "Unknown error"))
                    elif return_code == 0:
                        on_complete()
                    else:
                        on_error(f"Toolbag exited with code {return_code}")

                except Exception as e:
                    self._log(f"Exception in render thread: {e}")
                    import traceback
                    traceback.print_exc()
                    if not self.is_cancelling:
                        on_error(str(e))
                finally:
                    self._cleanup()

            threading.Thread(target=render_thread, daemon=True).start()

        except Exception as e:
            self._cleanup()
            on_error(f"Failed to start render: {e}")

    def _generate_render_script(self, job, start_frame: int) -> str:
        """Generate the Python script that Toolbag will execute for multi-pass rendering.

        Uses RenderObject.renderImages() which goes through Toolbag's proper
        render pipeline and correctly handles ALL pass types (including geometry
        passes like Wireframe, Depth, Normals, Position that renderCamera's
        viewportPass parameter cannot render).
        """
        scene_path = job.file_path.replace('\\', '\\\\')
        output_folder = job.output_folder.replace('\\', '\\\\')
        progress_path = self._progress_file_path.replace('\\', '\\\\')

        samples = job.get_setting("samples", 256)
        use_transparency = job.get_setting("use_transparency", False)
        output_name = job.output_name or "render_"
        camera_name = job.camera if job.camera and job.camera not in ("Scene Default", "Main Camera") else ""

        # Get render pass data from engine settings
        render_pass_data = job.get_setting("render_pass_data", [])
        if not render_pass_data:
            # Fallback: build from pass IDs
            pass_ids = job.get_setting("render_passes", ["beauty"])
            pass_lookup = {p["id"]: p for p in self.RENDER_PASSES}
            render_pass_data = []
            for pid in pass_ids:
                if pid in pass_lookup:
                    p = pass_lookup[pid]
                    render_pass_data.append({"id": p["id"], "name": p["name"], "pass": p["pass"]})

        # Determine output extension
        fmt = job.output_format or "PNG"
        ext_map = {"PNG": "png", "JPEG": "jpg", "TGA": "tga", "PSD": "psd",
                   "PSD (16-bit)": "psd", "EXR (16-bit)": "exr", "EXR (32-bit)": "exr",
                   "TIFF": "tiff", "OpenEXR": "exr"}
        ext = ext_map.get(fmt, "png")

        # Serialize pass data for the script
        passes_json = json.dumps(render_pass_data)

        render_type = job.get_setting("render_type", "still")

        return f'''# Wain Marmoset Multi-Pass Render Script
# Auto-generated - do not edit
# Uses RenderObject.renderImages() for reliable multi-pass rendering.
# See: https://www.marmoset.co/python/reference5.html
import mset
import json
import os
import sys
import time
import threading
import shutil

SCENE_PATH = r"{scene_path}"
OUTPUT_FOLDER = r"{output_folder}"
PROGRESS_PATH = r"{progress_path}"
OUTPUT_NAME = "{output_name}"
FMT = "{fmt}"
EXT = "{ext}"
WIDTH = {job.res_width}
HEIGHT = {job.res_height}
SAMPLES = {samples}
TRANSPARENCY = {str(use_transparency)}
CAMERA_NAME = "{camera_name}"
PASSES = {passes_json}
RENDER_TYPE = "{render_type}"
LOG_PATH = os.path.join(OUTPUT_FOLDER, "_wain_render_log.txt")

# --- Threaded progress writer ---
_progress_lock = threading.Lock()
_progress_state = {{}}
_writer_running = True

def _progress_writer():
    """Write progress JSON to disk periodically."""
    while _writer_running:
        with _progress_lock:
            state = _progress_state.copy()
        if state:
            try:
                with open(PROGRESS_PATH, 'w') as f:
                    json.dump(state, f)
            except Exception:
                pass
        time.sleep(0.2)

_writer_thread = threading.Thread(target=_progress_writer, daemon=True)
_writer_thread.start()

def log(msg):
    print(f"[Wain] {{msg}}")
    sys.stdout.flush()
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{{time.strftime('%H:%M:%S')}}] {{msg}}\\n")
    except Exception:
        pass

def update_progress(status, progress=0, current=0, total=0, error="", pass_name="", pass_num=0, total_passes=0):
    with _progress_lock:
        _progress_state.update({{
            "status": status, "progress": progress,
            "current": current, "total": total, "error": error,
            "pass_name": pass_name, "pass_num": pass_num, "total_passes": total_passes,
            "timestamp": time.time(),
        }})

def main():
    global _writer_running
    try:
        log("=" * 50)
        log("Wain Marmoset Multi-Pass Render Script")
        log("=" * 50)

        total_passes = len(PASSES)
        log(f"Passes to render: {{total_passes}}")
        for i, p in enumerate(PASSES):
            log(f"  {{i+1}}. {{p['name']}} (pass='{{p['pass']}}')")
        log(f"Camera: '{{CAMERA_NAME}}' (empty = default)")
        log(f"Format: {{FMT}} -> .{{EXT}}")
        log(f"Resolution: {{WIDTH}}x{{HEIGHT}}, Sampling: {{SAMPLES}}")

        update_progress("loading", 0, 0, total_passes, total_passes=total_passes)
        log(f"Loading scene: {{SCENE_PATH}}")

        if not os.path.exists(SCENE_PATH):
            log("ERROR: Scene file not found!")
            update_progress("error", 0, 0, 0, "Scene file not found")
            _writer_running = False
            mset.quit()
            return

        mset.loadScene(SCENE_PATH)
        log("Scene loaded successfully")

        # Set camera if specified
        if CAMERA_NAME:
            log(f"Setting camera: {{CAMERA_NAME}}")
            try:
                cam = mset.findObject(CAMERA_NAME)
                if cam:
                    mset.setCamera(cam)
                    log(f"Camera set to: {{CAMERA_NAME}}")
                else:
                    log(f"WARNING: Camera '{{CAMERA_NAME}}' not found")
            except Exception as e:
                log(f"WARNING: Could not set camera: {{e}}")

        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        # Build pass name list (use "Full Quality" for beauty)
        pass_names = []
        for p in PASSES:
            if p["pass"] == "":
                pass_names.append("Full Quality")
            else:
                pass_names.append(p["pass"])

        # === Find the RenderObject ===
        render_obj = None
        for obj in mset.getAllObjects():
            if type(obj).__name__ == "RenderObject":
                render_obj = obj
                break

        if render_obj is not None:
            log("Found RenderObject — using renderImages() pipeline")
            _render_with_render_object(render_obj, pass_names, total_passes)
        else:
            log("WARNING: No RenderObject found — falling back to renderCamera()")
            log("Note: Geometry passes (Wireframe, Depth, etc.) may not render correctly")
            _render_with_camera(pass_names, total_passes)

    except Exception as e:
        log(f"FATAL ERROR: {{e}}")
        import traceback
        traceback.print_exc()
        update_progress("error", 0, 0, 0, str(e))

    _writer_running = False
    time.sleep(1.5)  # Let writer flush final state
    log("Quitting Toolbag...")
    mset.quit()


def _render_with_render_object(render_obj, pass_names, total_passes):
    """Hybrid render: renderImages() for scene passes, renderCamera() fallback.

    renderImages() correctly handles ALL pass types that are already
    configured in the scene's RenderObject (including geometry passes
    like Wireframe that renderCamera cannot handle).

    For passes NOT already in the scene, renderCamera(viewportPass=...)
    is used as a fallback (works for lighting/shading passes like AO,
    Lighting Direct/Indirect, etc.).
    """
    # Create temp directory for renderImages() output
    render_dir = os.path.join(OUTPUT_FOLDER, "_wain_temp")
    os.makedirs(render_dir, exist_ok=True)

    # Configure output settings on the RenderObject
    try:
        img = render_obj.images
        img.outputPath = render_dir
        img.format = FMT
        img.width = WIDTH
        img.height = HEIGHT
        img.samples = SAMPLES
        img.transparency = TRANSPARENCY
        img.overwrite = True
        log(f"Configured RenderObject: {{render_dir}}, {{FMT}}, {{WIDTH}}x{{HEIGHT}}, {{SAMPLES}} samples")
    except Exception as e:
        log(f"WARNING: Could not fully configure RenderObject output: {{e}}")

    # Build a lookup of passes already in the scene's RenderObject
    scene_passes = {{}}
    try:
        for rp in render_obj.renderPasses:
            name = getattr(rp, 'renderPass', '')
            if name:
                scene_passes[name] = rp
                rp.enabled = False  # Disable all initially
    except Exception as e:
        log(f"Error reading existing passes: {{e}}")

    log(f"Scene has {{len(scene_passes)}} pass(es): {{sorted(scene_passes.keys())}}")

    # Classify each requested pass
    ri_passes = []  # Passes to render via renderImages() (exist in scene)
    rc_passes = []  # Passes to render via renderCamera() (not in scene)
    for i, p_name in enumerate(pass_names):
        if p_name in scene_passes:
            ri_passes.append(i)
            log(f"  {{p_name}} -> renderImages() (in scene)")
        else:
            rc_passes.append(i)
            log(f"  {{p_name}} -> renderCamera() fallback (not in scene)")

    # === Render each pass ===
    render_start = time.time()
    success_count = 0

    for i, pass_info in enumerate(PASSES):
        pass_id = pass_info["id"]
        pass_name = pass_names[i]
        display_name = "Beauty" if pass_name == "Full Quality" else pass_name

        # Build output filename
        if total_passes == 1 and pass_id == "beauty":
            target_name = f"{{OUTPUT_NAME}}.{{EXT}}"
        else:
            target_name = f"{{OUTPUT_NAME}}{{pass_id}}.{{EXT}}"
        dst_path = os.path.join(OUTPUT_FOLDER, target_name)

        # Update progress
        update_progress(
            "rendering",
            progress=int((i / total_passes) * 100),
            current=i,
            total=total_passes,
            pass_name=display_name,
            pass_num=i + 1,
            total_passes=total_passes,
        )

        rendered = False

        if i in ri_passes:
            # --- renderImages() path (pass exists in scene) ---
            log(f"Pass {{i+1}}/{{total_passes}}: {{display_name}} [renderImages]")

            # Enable only this pass
            for rp in render_obj.renderPasses:
                try:
                    rp.enabled = (getattr(rp, 'renderPass', '') == pass_name)
                except Exception:
                    pass

            # Record files before
            try:
                pre_files = set(os.listdir(render_dir))
            except Exception:
                pre_files = set()

            try:
                render_obj.renderImages()
            except Exception as e:
                log(f"  renderImages() error: {{e}}")

            # Find new file(s)
            try:
                post_files = set(os.listdir(render_dir))
            except Exception:
                post_files = set()

            new_files = sorted(post_files - pre_files)

            if new_files:
                src_path = os.path.join(render_dir, new_files[0])
                try:
                    shutil.move(src_path, dst_path)
                    size = os.path.getsize(dst_path)
                    log(f"  OK: {{target_name}} ({{size:,}} bytes) [from {{new_files[0]}}]")
                    success_count += 1
                    rendered = True
                except Exception as e:
                    log(f"  Error moving file: {{e}}")

                if len(new_files) > 1:
                    log(f"  Note: {{len(new_files)}} extra files: {{new_files[1:]}}")

        if not rendered:
            # --- renderCamera() fallback (pass not in scene, or renderImages failed) ---
            if i in ri_passes:
                log(f"  renderImages() produced no output, trying renderCamera()...")
            else:
                log(f"Pass {{i+1}}/{{total_passes}}: {{display_name}} [renderCamera]")

            viewport_pass = "" if pass_name == "Full Quality" else pass_name

            try:
                mset.renderCamera(
                    path=dst_path,
                    width=WIDTH,
                    height=HEIGHT,
                    sampling=SAMPLES,
                    transparency=TRANSPARENCY,
                    camera=CAMERA_NAME if CAMERA_NAME else "",
                    viewportPass=viewport_pass,
                )

                if os.path.exists(dst_path):
                    size = os.path.getsize(dst_path)
                    log(f"  OK: {{target_name}} ({{size:,}} bytes) [renderCamera]")
                    success_count += 1
                else:
                    log(f"  FAILED: No output for '{{display_name}}' (neither method worked)")
            except Exception as e:
                log(f"  renderCamera() error: {{e}}")

    # Clean up temp directory
    try:
        shutil.rmtree(render_dir, ignore_errors=True)
    except Exception:
        pass

    render_time = time.time() - render_start
    log("")
    log("=" * 50)
    log(f"Render complete: {{success_count}}/{{total_passes}} passes in {{render_time:.1f}}s")
    log("=" * 50)

    if success_count > 0:
        update_progress("complete", 100, total_passes, total_passes,
                      pass_name="", pass_num=total_passes, total_passes=total_passes)
    else:
        update_progress("error", 0, 0, total_passes,
                      error="No output files created")


def _render_with_camera(pass_names, total_passes):
    """Fallback: render using renderCamera(viewportPass=...).

    Note: Geometry passes (Wireframe, Depth, Normals, Position) may not
    produce output with this approach — they require the RenderObject pipeline.
    """
    render_start = time.time()
    success_count = 0

    for i, pass_info in enumerate(PASSES):
        pass_id = pass_info["id"]
        pass_name = pass_names[i]
        display_name = "Beauty" if pass_name == "Full Quality" else pass_name

        if total_passes == 1 and pass_id == "beauty":
            output_path = os.path.join(OUTPUT_FOLDER, f"{{OUTPUT_NAME}}.{{EXT}}")
        else:
            output_path = os.path.join(OUTPUT_FOLDER, f"{{OUTPUT_NAME}}{{pass_id}}.{{EXT}}")

        update_progress(
            "rendering",
            progress=int((i / total_passes) * 100),
            current=i,
            total=total_passes,
            pass_name=display_name,
            pass_num=i + 1,
            total_passes=total_passes,
        )
        log(f"Pass {{i+1}}/{{total_passes}}: {{display_name}} -> {{os.path.basename(output_path)}}")

        viewport_pass = "" if pass_name == "Full Quality" else pass_name

        try:
            mset.renderCamera(
                path=output_path,
                width=WIDTH,
                height=HEIGHT,
                sampling=SAMPLES,
                transparency=TRANSPARENCY,
                camera=CAMERA_NAME if CAMERA_NAME else "",
                viewportPass=viewport_pass,
            )

            if os.path.exists(output_path):
                size = os.path.getsize(output_path)
                log(f"  Output: {{os.path.basename(output_path)}} ({{size:,}} bytes)")
                success_count += 1
            else:
                log(f"  WARNING: Output file not created for '{{display_name}}'")
        except Exception as e:
            log(f"  ERROR rendering '{{display_name}}': {{e}}")

    render_time = time.time() - render_start
    log("")
    log("=" * 50)
    log(f"Render complete: {{success_count}}/{{total_passes}} passes in {{render_time:.1f}}s")
    log("=" * 50)

    if success_count > 0:
        update_progress("complete", 100, total_passes, total_passes,
                      pass_name="", pass_num=total_passes, total_passes=total_passes)
    else:
        update_progress("error", 0, 0, total_passes,
                      error="No output files created")


# Run main
main()
'''

    def _read_progress_file(self) -> Dict[str, Any]:
        """Read progress information from JSON file."""
        if not self._progress_file_path or not os.path.exists(self._progress_file_path):
            return {}
        try:
            with open(self._progress_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def cancel_render(self):
        """Cancel the current render."""
        self._log("Cancelling render...")
        self.is_cancelling = True
        self._monitoring = False

        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except Exception:
                try:
                    self.current_process.kill()
                except Exception:
                    pass

        self._cleanup()

    def _cleanup(self):
        """Clean up temporary files."""
        for path in [self._temp_script_path, self._progress_file_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass
        self._temp_script_path = None
        self._progress_file_path = None
        self.current_process = None
        self._on_log = None
