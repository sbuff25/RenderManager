"""
Wain Vantage Engine v2.15.4
===========================

Chaos Vantage render engine integration with HQ SETTINGS CONTROL.

v2.15.4 - Enabled INI writing (safe atomic implementation)
v2.15.3 - Added "Use Scene Settings" option (default ON)
v2.15.2 - Fixed Desktop import scope bug in _monitor_render
v2.15.1 - Fixed INI corruption, atomic writes with backup

When "Use Scene Settings" is enabled (default):
- Wain does NOT modify vantage.ini
- Uses resolution, samples, output path configured in Vantage HQ panel

When "Use Scene Settings" is disabled:
- Wain applies job settings to vantage.ini before launching
- Creates backup at vantage.ini.wain_backup_TIMESTAMP
- Uses atomic writes with verification

https://github.com/Spencer-Sliffe/Wain
"""

import os
import sys
import subprocess
import threading
import time
import re
import json
from typing import Dict, List, Optional, Any
from urllib.request import urlopen, Request
from urllib.error import URLError

from wain.engines.base import RenderEngine


class VantageEngine(RenderEngine):
    """Chaos Vantage render engine integration with INI settings control."""
    
    name = "Chaos Vantage"
    engine_type = "vantage"
    file_extensions = [".vantage", ".vrscene"]
    icon = "landscape"
    color = "#77b22a"  # Vantage green
    
    SEARCH_PATHS = [
        r"C:\Program Files\Chaos\Vantage\vantage.exe",
        r"C:\Program Files\Chaos Group\Vantage\vantage.exe",
        r"C:\Program Files\Chaos\Vantage 3\vantage.exe",
        r"C:\Program Files\Chaos\Vantage 2\vantage.exe",
    ]
    
    OUTPUT_FORMATS = {
        "PNG": "png",
        "JPEG": "jpg",
        "EXR": "exr",
        "TGA": "tga",
    }
    
    # Live Link HTTP API port
    LIVE_LINK_PORT = 20701
    
    # Denoiser type mapping
    DENOISER_TYPES = {
        'nvidia': 0,
        'oidn': 1,
        'off': -1,  # Will set snapshotDenoiseDefault=false
    }
    
    # SAFETY FLAG: Set to True to enable INI modification
    # Keep False until INI writing is verified to work correctly
    ENABLE_INI_WRITE = True  # Safe atomic writes with backup
    
    def __init__(self):
        super().__init__()
        self._on_log = None
        self._job = None
        self._vantage_window = None
        self._desktop = None
        self._http_available = None
        self._ini_manager = None
        self.scan_installed_versions()
    
    def _log(self, msg: str):
        """Log a message."""
        if self._on_log:
            self._on_log(f"[Vantage] {msg}")
    
    def _get_ini_manager(self):
        """Get or create the INI manager."""
        if self._ini_manager is None:
            try:
                from wain.engines.vantage_settings import VantageINIManager
                self._ini_manager = VantageINIManager()
            except ImportError:
                self._log("Warning: vantage_settings module not found")
                return None
        return self._ini_manager
    
    def scan_installed_versions(self):
        """Scan for installed Vantage versions."""
        self.installed_versions = {}
        for path in self.SEARCH_PATHS:
            if os.path.isfile(path):
                version = "3.x" if "Vantage 3" in path else "2.x" if "Vantage 2" in path else "Unknown"
                self.installed_versions[version] = path
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """Add a custom Vantage path."""
        if os.path.isfile(path) and path.lower().endswith('.exe'):
            self.installed_versions["Custom"] = path
            return "Custom"
        return None
    
    def get_vantage_exe(self) -> Optional[str]:
        """Get the best available Vantage executable."""
        if self.installed_versions:
            return list(self.installed_versions.values())[0]
        return None
    
    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "quality_preset": "high",
            "samples": 256,
            "denoiser": "nvidia",
        }
    
    def get_file_dialog_filter(self) -> List[tuple]:
        return [
            ("Vantage Projects", "*.vantage"),
            ("V-Ray Scenes", "*.vrscene"),
        ]
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open a scene file in Vantage."""
        exe = self.get_vantage_exe()
        if exe and os.path.exists(file_path):
            subprocess.Popen([exe, file_path], creationflags=subprocess.DETACHED_PROCESS)
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """Get scene info. Now also reads current HQ settings from INI."""
        info = {
            "cameras": ["Default Camera"],
            "active_camera": "Default Camera",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "frame_start": 1,
            "frame_end": 1,
            "total_frames": 1,
            "has_animation": False,
            "samples": 256,
        }
        
        # Try to read current settings from vantage.ini
        ini = self._get_ini_manager()
        if ini and ini.exists():
            try:
                settings = ini.read_hq_settings()
                info["resolution_x"] = settings.width
                info["resolution_y"] = settings.height
                info["samples"] = settings.samples
                info["denoise"] = settings.denoise_enabled
                info["denoiser_type"] = settings.denoiser_type
            except Exception as e:
                print(f"[Vantage] Could not read INI settings: {e}")
        
        return info
    
    def _apply_job_settings(self, job) -> bool:
        """
        Apply job settings to vantage.ini BEFORE launching Vantage.
        
        If use_scene_settings is True (default), skips all modification
        and uses whatever is configured in Vantage's HQ Render panel.
        
        When use_scene_settings is False, applies job settings using
        safe atomic writes with automatic backup.
        """
        # Check if user wants to use existing Vantage settings
        use_scene_settings = job.get_setting("use_scene_settings", True)
        if use_scene_settings:
            self._log("Using scene settings (configured in Vantage HQ panel)")
            return True  # Success - just use existing settings
        
        ini = self._get_ini_manager()
        if not ini or not ini.exists():
            self._log("Note: vantage.ini not found, using existing Vantage settings")
            return False
        
        # Map job settings to INI values
        width = job.res_width
        height = job.res_height
        output_path = job.output_folder
        samples = job.get_setting("samples", 256)
        
        self._log(f"Job settings: {width}x{height}, {samples} samples")
        self._log(f"Output path: {output_path}")
        
        # SAFETY CHECK - only write if enabled
        if not self.ENABLE_INI_WRITE:
            self._log("INI write DISABLED (safety mode) - using existing Vantage settings")
            self._log("To enable INI write, set VantageEngine.ENABLE_INI_WRITE = True")
            return False
        
        # Validate INI before modifying
        is_valid, msg = ini.validate_ini()
        if not is_valid:
            self._log(f"INI validation failed: {msg}")
            return False
        
        self._log("Applying job settings to vantage.ini...")
        
        try:
            success = ini.apply_job_settings(
                width=width,
                height=height,
                samples=samples,
                output_path=output_path,
                backup=True  # Always backup
            )
            
            if success:
                # Validate INI after write
                is_valid, msg = ini.validate_ini()
                if not is_valid:
                    self._log(f"WARNING: INI validation failed AFTER write: {msg}")
                    self._log("Vantage may not start correctly!")
                    return False
                
                self._log(f"Successfully applied settings to vantage.ini")
                return True
            else:
                self._log("Warning: Failed to write INI settings")
                return False
                
        except Exception as e:
            self._log(f"Error applying settings: {e}")
            return False
    
    # =========================================================================
    # HTTP API (Live Link Protocol)
    # =========================================================================
    
    def _check_http_api(self) -> bool:
        """Check if Vantage HTTP API is available."""
        try:
            url = f"http://localhost:{self.LIVE_LINK_PORT}/"
            req = Request(url, method='GET')
            with urlopen(req, timeout=2) as response:
                return response.status < 500
        except:
            pass
        return False
    
    def _send_http_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a command via HTTP API."""
        try:
            url = f"http://localhost:{self.LIVE_LINK_PORT}/"
            data = json.dumps(command).encode('utf-8')
            req = Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            with urlopen(req, timeout=30) as response:
                result = response.read().decode('utf-8')
                return json.loads(result) if result else {}
        except Exception as e:
            self._log(f"HTTP API error: {e}")
        return None
    
    # =========================================================================
    # UI AUTOMATION HELPERS
    # =========================================================================
    
    def _find_vantage_window(self):
        """Find the main Vantage window."""
        if not self._desktop:
            return None
        
        for win in self._desktop.windows():
            try:
                class_name = win.element_info.class_name or ""
                if "LavinaMainWindow" in class_name:
                    return win
            except:
                pass
        
        # Fallback: search by title
        for win in self._desktop.windows():
            try:
                title = win.window_text().lower()
                if "vantage" in title and "chaos" in title:
                    return win
            except:
                pass
        
        return None
    
    def _find_button_multilevel(self, window, name: str, exact: bool = False, max_depth: int = 4):
        """Find a button using multiple search strategies."""
        if not window:
            return None
        
        name_lower = name.lower()
        
        # Strategy 1: Direct descendants
        try:
            for btn in window.descendants(control_type="Button"):
                try:
                    btn_name = (btn.element_info.name or "").lower().strip()
                    auto_id = (btn.element_info.automation_id or "").lower()
                    
                    if exact:
                        if btn_name == name_lower:
                            return btn
                    else:
                        if name_lower in btn_name or name_lower in auto_id:
                            return btn
                except:
                    pass
        except:
            pass
        
        # Strategy 2: Iterative children search
        def search_children(parent, depth=0):
            if depth > max_depth:
                return None
            try:
                for child in parent.children():
                    try:
                        ctrl_type = child.element_info.control_type
                        child_name = (child.element_info.name or "").lower().strip()
                        auto_id = (child.element_info.automation_id or "").lower()
                        
                        if ctrl_type == "Button":
                            if exact:
                                if child_name == name_lower:
                                    return child
                            else:
                                if name_lower in child_name or name_lower in auto_id:
                                    return child
                        
                        result = search_children(child, depth + 1)
                        if result:
                            return result
                    except:
                        pass
            except:
                pass
            return None
        
        result = search_children(window)
        if result:
            return result
        
        return None
    
    def _find_start_button(self, window):
        """Find the Start/Render button."""
        if not window:
            return None
        
        # Try exact match first
        btn = self._find_button_multilevel(window, "Start", exact=True)
        if btn:
            return btn
        
        # Case-insensitive
        btn = self._find_button_multilevel(window, "start", exact=False)
        if btn:
            return btn
        
        # Try "Render"
        btn = self._find_button_multilevel(window, "render", exact=False)
        if btn:
            return btn
        
        # Search all buttons
        try:
            best_match = None
            for elem in window.descendants(control_type="Button"):
                try:
                    name = (elem.element_info.name or "").lower()
                    if name in ["start", "render", "begin", "go"]:
                        return elem
                    if "start" in name and best_match is None:
                        best_match = elem
                except:
                    pass
            if best_match:
                return best_match
        except:
            pass
        
        return None
    
    def _find_progress_window(self):
        """Find the Vantage render progress window (child of main window)."""
        vantage = self._find_vantage_window()
        if not vantage:
            return None
        
        try:
            for child in vantage.children():
                try:
                    name = child.element_info.name or ""
                    class_name = child.element_info.class_name or ""
                    
                    if "LavinaRenderProgressDialog" in class_name:
                        return child
                    if "rendering hq" in name.lower() or "rendering" in name.lower():
                        return child
                except:
                    pass
            
            for child in vantage.descendants(control_type="Window"):
                try:
                    name = child.element_info.name or ""
                    class_name = child.element_info.class_name or ""
                    
                    if "LavinaRenderProgressDialog" in class_name:
                        return child
                    if "rendering hq" in name.lower():
                        return child
                except:
                    pass
        except:
            pass
        
        return None
    
    def _read_progress(self, window) -> Optional[Dict[str, Any]]:
        """Read progress from the Vantage 3.x progress dialog."""
        result = {
            'total': 0,
            'frame': 0,
            'total_frames': 1,
            'frame_pct': 0,
            'elapsed': '',
            'remaining': ''
        }
        
        try:
            texts = []
            for child in window.descendants(control_type="Text"):
                try:
                    name = child.element_info.name or ""
                    if name.strip():
                        texts.append(name.strip())
                except:
                    pass
            
            for text in texts:
                text_lower = text.lower()
                
                # Parse "HQ sequence frame X of Y"
                frame_match = re.search(r'(?:hq\s+)?(?:sequence\s+)?frame\s+(\d+)\s+of\s+(\d+)', text_lower)
                if frame_match:
                    result['frame'] = int(frame_match.group(1))
                    result['total_frames'] = int(frame_match.group(2))
                    if result['total_frames'] > 0:
                        result['total'] = int((result['frame'] / result['total_frames']) * 100)
                    continue
                
                # Parse "Elapsed: HH:MM:SS"
                elapsed_match = re.search(r'elapsed[:\s]+(\d+:\d+:\d+)', text_lower)
                if elapsed_match:
                    result['elapsed'] = elapsed_match.group(1)
                    continue
                
                # Parse "Remaining: HH:MM:SS"
                remaining_match = re.search(r'remain(?:ing)?[:\s]+(\d+:\d+:\d+)', text_lower)
                if remaining_match:
                    result['remaining'] = remaining_match.group(1)
                    continue
                
                # Parse standalone percentage
                pct_match = re.search(r'^(\d+(?:\.\d+)?)\s*%$', text.strip())
                if pct_match:
                    pct = int(float(pct_match.group(1)))
                    if result['frame_pct'] == 0:
                        result['frame_pct'] = pct
                    continue
            
            if result['frame'] > 0 or result['total_frames'] > 1:
                return result
            
            return result if result['total'] > 0 or result['frame_pct'] > 0 else None
            
        except Exception as e:
            return None
    
    def _send_ctrl_r(self, window):
        """Send Ctrl+R to open HQ render panel."""
        from pywinauto import keyboard
        import ctypes
        
        try:
            window.set_focus()
            time.sleep(0.02)
        except:
            pass
        
        # Method 1: pywinauto
        try:
            keyboard.send_keys("^r", pause=0.01)
            time.sleep(0.05)
            return True
        except:
            pass
        
        # Method 2: Native Windows API
        try:
            VK_CONTROL = 0x11
            VK_R = 0x52
            KEYEVENTF_KEYUP = 0x0002
            
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_R, 0, 0, 0)
            time.sleep(0.01)
            ctypes.windll.user32.keybd_event(VK_R, 0, KEYEVENTF_KEYUP, 0)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
            return True
        except:
            pass
        
        return False
    
    def _list_all_buttons(self, window) -> List[str]:
        """List all button names for debugging."""
        buttons = []
        try:
            for btn in window.descendants(control_type="Button"):
                try:
                    name = btn.element_info.name or "(no name)"
                    auto_id = btn.element_info.automation_id or ""
                    buttons.append(f"{name} [id:{auto_id}]")
                except:
                    pass
        except:
            pass
        return buttons[:30]
    
    # =========================================================================
    # MAIN RENDER METHOD
    # =========================================================================
    
    def start_render(self, job, start_frame: int, on_progress, on_complete, on_error, on_log=None):
        """
        Start rendering a Vantage job with FULL SETTINGS CONTROL.
        
        NEW: Applies job settings (resolution, samples, output) to vantage.ini
        before launching Vantage. No more manual configuration needed!
        """
        if not os.path.exists(job.file_path):
            on_error(f"Scene file not found: {job.file_path}")
            return
        
        self.is_cancelling = False
        self._on_log = on_log
        self._job = job
        
        self._log("=" * 50)
        self._log("Wain Vantage Engine v2.15.0 - Full Settings Control")
        self._log(f"Scene: {job.file_path}")
        self._log("=" * 50)
        
        # Ensure output directory exists
        os.makedirs(job.output_folder, exist_ok=True)
        
        def render_thread():
            try:
                from pywinauto import Desktop, keyboard
            except ImportError:
                on_error("pywinauto not installed. Run: pip install pywinauto")
                return
            
            try:
                self._desktop = Desktop(backend="uia")
                
                # ============================================================
                # STEP 0: Apply job settings to vantage.ini (NEW!)
                # ============================================================
                self._log("Step 0: Applying job settings to vantage.ini...")
                settings_applied = self._apply_job_settings(job)
                if settings_applied:
                    self._log("Settings applied successfully!")
                else:
                    self._log("Using existing Vantage settings (INI update skipped)")
                
                # ============================================================
                # STEP 1: Find or launch Vantage
                # ============================================================
                self._log("Step 1: Finding/launching Vantage...")
                
                vantage = self._find_vantage_window()
                was_running = vantage is not None
                
                if not vantage:
                    vantage_exe = self.get_vantage_exe()
                    if not vantage_exe:
                        on_error("Vantage executable not found")
                        return
                    
                    self._log(f"Launching Vantage...")
                    subprocess.Popen(
                        [vantage_exe, job.file_path],
                        creationflags=subprocess.DETACHED_PROCESS
                    )
                    
                    # Wait for window
                    self._log("Waiting for Vantage window...")
                    wait_start = time.time()
                    while time.time() - wait_start < 60:
                        if self.is_cancelling:
                            return
                        
                        self._desktop = Desktop(backend="uia")
                        vantage = self._find_vantage_window()
                        if vantage:
                            self._log(f"Vantage window found! ({time.time() - wait_start:.1f}s)")
                            break
                        time.sleep(0.1)
                    
                    if not vantage:
                        on_error("Vantage did not start within 1 minute")
                        return
                else:
                    self._log("Vantage already running - connecting...")
                
                self._vantage_window = vantage
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STEP 1.5: Check for existing progress window (resume)
                # ============================================================
                progress_win = self._find_progress_window()
                if progress_win:
                    self._log("Found existing progress window - checking for Resume...")
                    
                    resume_btn = self._find_button_multilevel(progress_win, "resume")
                    if resume_btn:
                        self._log("Clicking Resume to continue paused render...")
                        try:
                            resume_btn.click_input()
                            self._log("Clicked Resume button!")
                        except Exception as e:
                            try:
                                resume_btn.invoke()
                            except:
                                pass
                        
                        # Skip to monitoring
                        self._monitor_render(job, on_progress, on_complete, on_error)
                        return
                
                # ============================================================
                # STEP 2: Open HQ panel and find Start button
                # ============================================================
                self._log("Step 2: Opening HQ panel and finding Start button...")
                
                start_btn = None
                if was_running:
                    start_btn = self._find_start_button(vantage)
                    if not start_btn:
                        self._send_ctrl_r(vantage)
                else:
                    self._send_ctrl_r(vantage)
                
                # Poll for Start button
                poll_start = time.time()
                ctrl_r_sent_times = 1
                last_ctrl_r = time.time()
                
                while not start_btn and time.time() - poll_start < 30:
                    if self.is_cancelling:
                        return
                    
                    self._desktop = Desktop(backend="uia")
                    vantage = self._find_vantage_window()
                    
                    if not vantage:
                        time.sleep(0.1)
                        continue
                    
                    self._vantage_window = vantage
                    start_btn = self._find_start_button(vantage)
                    
                    if start_btn:
                        self._log(f"Start button found! ({time.time() - poll_start:.1f}s)")
                        break
                    
                    # Resend Ctrl+R
                    if time.time() - last_ctrl_r > 0.5 and ctrl_r_sent_times < 8:
                        self._log(f"Resending Ctrl+R (attempt {ctrl_r_sent_times + 1})...")
                        self._send_ctrl_r(vantage)
                        last_ctrl_r = time.time()
                        ctrl_r_sent_times += 1
                    
                    time.sleep(0.1)
                
                if not start_btn:
                    buttons = self._list_all_buttons(vantage)
                    self._log(f"Available buttons: {buttons[:15]}")
                    on_error("Could not find Start button after 30s")
                    return
                
                # ============================================================
                # STEP 3: Click Start
                # ============================================================
                self._log("Step 3: Clicking Start...")
                
                try:
                    start_btn.click_input()
                    self._log("Click sent!")
                except Exception as e:
                    try:
                        start_btn.invoke()
                        self._log("Invoked Start button")
                    except:
                        self._log(f"Click failed: {e}")
                        on_error("Failed to click Start button")
                        return
                
                # ============================================================
                # STEP 4: Monitor progress
                # ============================================================
                self._monitor_render(job, on_progress, on_complete, on_error)
                
            except Exception as e:
                if not self.is_cancelling:
                    self._log(f"Error: {e}")
                    on_error(str(e))
        
        threading.Thread(target=render_thread, daemon=True).start()
    
    def _monitor_render(self, job, on_progress, on_complete, on_error):
        """Monitor render progress until completion."""
        from pywinauto import Desktop  # Import here for method scope
        
        self._log("Step 4: Monitoring render progress...")
        
        job.progress = 0
        on_progress(0, "Render starting...")
        
        render_start = time.time()
        last_progress = -1
        progress_window_seen = False
        no_window_count = 0
        last_log_time = time.time()
        click_retry_count = 0
        last_click_retry = time.time()
        
        while not self.is_cancelling:
            elapsed = time.time() - render_start
            
            self._desktop = Desktop(backend="uia")
            progress_win = self._find_progress_window()
            
            if progress_win:
                progress_window_seen = True
                no_window_count = 0
                
                progress_info = self._read_progress(progress_win)
                
                if progress_info:
                    total_pct = progress_info.get('total', 0)
                    frame_pct = progress_info.get('frame_pct', 0)
                    current_frame = progress_info.get('frame', 0)
                    total_frames = progress_info.get('total_frames', 1)
                    elapsed_str = progress_info.get('elapsed', '')
                    remaining_str = progress_info.get('remaining', '')
                    
                    if total_pct == 0 and current_frame > 0 and total_frames > 0:
                        total_pct = int((current_frame / total_frames) * 100)
                    
                    progress_changed = (total_pct != last_progress or current_frame != job.current_frame)
                    time_to_log = (time.time() - last_log_time) > 10
                    
                    if progress_changed or time_to_log:
                        last_progress = total_pct
                        last_log_time = time.time()
                        job.progress = min(total_pct, 99)
                        
                        if current_frame > 0:
                            job.current_frame = current_frame
                            job.rendering_frame = current_frame
                        
                        if total_frames > 1:
                            job.frame_end = total_frames
                        
                        if frame_pct > 0:
                            job.current_sample = frame_pct
                            job.total_samples = 100
                        
                        if current_frame > 0 and total_frames > 1:
                            status = f"Frame {current_frame}/{total_frames} ({total_pct}%)"
                        else:
                            status = f"Rendering... {total_pct}%"
                        
                        on_progress(total_pct, status)
                        
                        log_msg = status
                        if elapsed_str:
                            log_msg += f" - Elapsed: {elapsed_str}"
                        if remaining_str:
                            log_msg += f" - Remaining: {remaining_str}"
                        self._log(log_msg)
                    
                    # Check completion
                    if current_frame >= total_frames and total_frames > 1:
                        self._log("All frames complete!")
                        job.progress = 100
                        on_complete()
                        return
                    
                    if total_pct >= 100:
                        self._log("Render complete!")
                        job.progress = 100
                        on_complete()
                        return
            
            elif progress_window_seen:
                no_window_count += 1
                if no_window_count >= 5:
                    self._log("Progress window closed - render complete!")
                    job.progress = 100
                    on_complete()
                    return
            else:
                # No progress window yet - retry clicking Start if needed
                if elapsed > 3 and click_retry_count < 3 and (time.time() - last_click_retry) > 2:
                    click_retry_count += 1
                    last_click_retry = time.time()
                    self._log(f"No progress window - retrying Start click ({click_retry_count}/3)...")
                    
                    vantage = self._find_vantage_window()
                    if vantage:
                        start_btn = self._find_start_button(vantage)
                        if start_btn:
                            try:
                                start_btn.click_input()
                                self._log("Retry click sent")
                            except:
                                try:
                                    start_btn.invoke()
                                except:
                                    pass
                
                if elapsed > 30 and not progress_window_seen:
                    on_error("Render did not start - no progress window after 30s")
                    return
            
            # Timeout
            if elapsed > 7200:
                on_error("Render timed out after 2 hours")
                return
            
            time.sleep(0.3)
        
        self._log("Render cancelled by user")
    
    def pause_render(self):
        """Pause the current render by clicking Pause in Vantage."""
        self._log("Pausing render...")
        self.is_cancelling = True
        
        try:
            from pywinauto import Desktop
            self._desktop = Desktop(backend="uia")
            
            progress_win = self._find_progress_window()
            if progress_win:
                pause_btn = self._find_button_multilevel(progress_win, "pause")
                if pause_btn:
                    try:
                        pause_btn.click_input()
                        self._log("Clicked Pause button")
                        return True
                    except Exception as e:
                        try:
                            pause_btn.invoke()
                            self._log("Pause invoked")
                            return True
                        except:
                            pass
                else:
                    self._log("Pause button not found")
            else:
                self._log("Progress window not found")
        except Exception as e:
            self._log(f"Error pausing: {e}")
        
        return False
    
    def cancel_render(self, close_vantage: bool = True):
        """Cancel/abort the current render."""
        self.is_cancelling = True
        
        try:
            from pywinauto import Desktop
            self._desktop = Desktop(backend="uia")
            
            progress_win = self._find_progress_window()
            if progress_win:
                abort_btn = self._find_button_multilevel(progress_win, "abort")
                if abort_btn:
                    try:
                        abort_btn.click_input()
                    except:
                        try:
                            abort_btn.invoke()
                        except:
                            pass
                else:
                    for btn_name in ["cancel", "stop", "close"]:
                        btn = self._find_button_multilevel(progress_win, btn_name)
                        if btn:
                            try:
                                btn.click_input()
                                break
                            except:
                                pass
            
            if close_vantage:
                import time
                time.sleep(0.05)
                self._close_vantage()
                
        except Exception as e:
            pass
        
        self._vantage_window = None
        self._desktop = None
        self._on_log = None
        self._job = None
    
    def _close_vantage(self):
        """Close the Vantage application."""
        try:
            from pywinauto import Desktop, keyboard
            import time
            
            self._desktop = Desktop(backend="uia")
            
            vantage = self._find_vantage_window()
            if vantage:
                try:
                    vantage.set_focus()
                    time.sleep(0.02)
                    keyboard.send_keys("%{F4}")
                    
                    time.sleep(0.1)
                    
                    # Handle save dialog
                    self._desktop = Desktop(backend="uia")
                    for win in self._desktop.windows():
                        try:
                            title = win.window_text().lower()
                            if "save" in title or "vantage" in title:
                                for btn_name in ["don't save", "dont save", "no", "discard"]:
                                    btn = self._find_button_multilevel(win, btn_name)
                                    if btn:
                                        btn.click_input()
                                        return
                        except:
                            pass
                    
                    return
                except:
                    pass
                
                try:
                    close_btn = vantage.child_window(title="Close", control_type="Button")
                    close_btn.click_input()
                    return
                except:
                    pass
                
                try:
                    vantage.close()
                except:
                    pass
                    
        except Exception as e:
            self._log(f"Error closing Vantage: {e}")
