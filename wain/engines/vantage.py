"""
Wain Vantage Engine v2.14.0
===========================

Chaos Vantage render engine integration - SPEED OPTIMIZED with ACCURATE PROGRESS.

Architecture:
- Primary: UI automation with robust button detection
- Secondary: HTTP API via Live Link protocol (port 20701)
- Fallback: Direct keyboard shortcuts

Progress Reading (v2.14.0):
- Progress dialog is a CHILD window inside main Vantage window
- Parses 'HQ sequence frame X of Y' for frame count
- Reads elapsed/remaining time from dialog
- Calculates total % from frame progress

Click Verification (v2.13.2):
- Verifies render actually started by checking for progress window
- Retries click up to 3 times if render doesn't start
- Falls back to invoke() method if click_input() fails
- Logs button state (name, enabled) for debugging

HQ render settings (output path, resolution, frame range) are NOT stored
in .vantage files. User must configure these in Vantage's HQ panel.

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
    """Chaos Vantage render engine integration."""
    
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
    
    # Live Link HTTP API port (used by 3ds Max/Maya integration)
    LIVE_LINK_PORT = 20701
    
    def __init__(self):
        super().__init__()
        self._on_log = None
        self._job = None
        self._vantage_window = None
        self._desktop = None
        self._http_available = None
        self.scan_installed_versions()
    
    def _log(self, msg: str):
        """Log a message."""
        if self._on_log:
            self._on_log(f"[Vantage] {msg}")
    
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
        return {"quality_preset": "High"}
    
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
        """Get basic scene info. Note: HQ render settings are NOT stored in files."""
        return {
            "cameras": ["Default Camera"],
            "active_camera": "Default Camera",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "frame_start": 1,
            "frame_end": 1,
            "total_frames": 1,
            "has_animation": False,
        }
    
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
        """
        Find a button using multiple search strategies.
        
        Strategies:
        1. Direct children only (fastest)
        2. Descendants up to max_depth levels
        3. By automation_id
        4. By partial name match
        """
        if not window:
            return None
        
        name_lower = name.lower()
        
        # Strategy 1: Direct descendants (fastest)
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
        
        # Strategy 2: Check children iteratively
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
                        
                        # Recurse
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
        """Find the Start/Render button using multiple methods."""
        if not window:
            return None
        
        # Method 1: Exact match "Start"
        btn = self._find_button_multilevel(window, "Start", exact=True)
        if btn:
            return btn
        
        # Method 2: Case-insensitive "start"
        btn = self._find_button_multilevel(window, "start", exact=False)
        if btn:
            return btn
        
        # Method 3: Look for "Render" button
        btn = self._find_button_multilevel(window, "render", exact=False)
        if btn:
            return btn
        
        # Method 4: Search all buttons and find best match
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
        """
        Find the Vantage render progress window.
        
        In Vantage 3.x, the progress dialog is a CHILD window inside the main
        Vantage window, not a separate top-level window. We need to search
        within the main window's children.
        """
        # First find the main Vantage window
        vantage = self._find_vantage_window()
        if not vantage:
            return None
        
        # Look for the progress dialog as a child window
        try:
            for child in vantage.children():
                try:
                    name = child.element_info.name or ""
                    class_name = child.element_info.class_name or ""
                    
                    # Look for the specific progress dialog class
                    if "LavinaRenderProgressDialog" in class_name:
                        return child
                    
                    # Or by name
                    if "rendering hq" in name.lower() or "rendering" in name.lower():
                        return child
                except:
                    pass
            
            # Also check Window-type descendants
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
        """
        Read progress information from the Vantage 3.x progress dialog.
        
        Parses text elements like:
        - 'HQ sequence frame 3 of 301' -> frame count
        - 'Elapsed: 00:00:46' -> elapsed time
        - 'Remaining: 01:35:46' -> remaining time
        
        Returns dict with: frame, total_frames, total (%), elapsed, remaining
        """
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
                    # Calculate total percentage from frame progress
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
                
                # Parse standalone percentage (e.g., "31%")
                pct_match = re.search(r'^(\d+(?:\.\d+)?)\s*%$', text.strip())
                if pct_match:
                    pct = int(float(pct_match.group(1)))
                    # If we haven't set frame_pct yet, use this
                    if result['frame_pct'] == 0:
                        result['frame_pct'] = pct
                    continue
            
            # Return result if we found frame info (our main progress indicator)
            if result['frame'] > 0 or result['total_frames'] > 1:
                return result
            
            # Otherwise return if we found any percentage
            return result if result['total'] > 0 or result['frame_pct'] > 0 else None
            
        except Exception as e:
            return None
    
    def _send_ctrl_r(self, window):
        """Send Ctrl+R using multiple methods for reliability."""
        from pywinauto import keyboard
        import ctypes
        
        try:
            window.set_focus()
            time.sleep(0.15)
        except:
            pass
        
        # Method 1: pywinauto keyboard
        try:
            keyboard.send_keys("^r", pause=0.05)
            time.sleep(0.3)
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
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(VK_R, 0, KEYEVENTF_KEYUP, 0)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.3)
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
        return buttons[:30]  # Limit output
    
    # =========================================================================
    # MAIN RENDER METHOD
    # =========================================================================
    
    def start_render(self, job, start_frame: int, on_progress, on_complete, on_error, on_log=None):
        """
        Start rendering a Vantage job - SPEED OPTIMIZED.
        
        Uses aggressive polling to start render as fast as possible.
        User must pre-configure HQ settings in Vantage (output path, resolution, etc.)
        """
        if not os.path.exists(job.file_path):
            on_error(f"Scene file not found: {job.file_path}")
            return
        
        self.is_cancelling = False
        self._on_log = on_log
        self._job = job
        
        self._log("=" * 50)
        self._log("Wain Vantage Engine v2.13.2 - Click Verification")
        self._log(f"Scene: {job.file_path}")
        self._log("Note: Using HQ settings configured in Vantage")
        self._log("=" * 50)
        
        def render_thread():
            try:
                from pywinauto import Desktop, keyboard
            except ImportError:
                on_error("pywinauto not installed. Run: pip install pywinauto")
                return
            
            try:
                self._desktop = Desktop(backend="uia")
                
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
                    
                    # Aggressive polling for window (0.2s intervals)
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
                        time.sleep(0.2)  # Fast polling
                    
                    if not vantage:
                        on_error("Vantage did not start within 1 minute")
                        return
                else:
                    self._log("Vantage already running - connecting...")
                
                self._vantage_window = vantage
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STEP 2: Immediately send Ctrl+R and poll for Start button
                # ============================================================
                self._log("Step 2: Opening HQ panel and finding Start button...")
                
                # If Vantage was already running, Start might already be visible
                if was_running:
                    start_btn = self._find_start_button(vantage)
                    if start_btn:
                        self._log("Start button already visible!")
                    else:
                        # Send Ctrl+R immediately
                        self._send_ctrl_r(vantage)
                else:
                    # For fresh launch, send Ctrl+R immediately - don't wait for scene
                    self._send_ctrl_r(vantage)
                    start_btn = None
                
                # Aggressive polling for Start button (0.15s intervals, max 30s)
                poll_start = time.time()
                ctrl_r_sent_times = 1
                last_ctrl_r = time.time()
                
                while not start_btn and time.time() - poll_start < 30:
                    if self.is_cancelling:
                        return
                    
                    # Refresh and search
                    self._desktop = Desktop(backend="uia")
                    vantage = self._find_vantage_window()
                    
                    if not vantage:
                        time.sleep(0.15)
                        continue
                    
                    self._vantage_window = vantage
                    start_btn = self._find_start_button(vantage)
                    
                    if start_btn:
                        self._log(f"Start button found! ({time.time() - poll_start:.1f}s)")
                        break
                    
                    # Resend Ctrl+R every 2 seconds if button not found
                    if time.time() - last_ctrl_r > 2.0 and ctrl_r_sent_times < 5:
                        self._log(f"Resending Ctrl+R (attempt {ctrl_r_sent_times + 1})...")
                        self._send_ctrl_r(vantage)
                        last_ctrl_r = time.time()
                        ctrl_r_sent_times += 1
                    
                    time.sleep(0.15)  # Fast polling
                
                if not start_btn:
                    # Debug: list all available buttons
                    buttons = self._list_all_buttons(vantage)
                    self._log(f"Available buttons: {buttons[:15]}")
                    on_error("Could not find Start button after 30s. Please ensure HQ Render panel is accessible via Ctrl+R.")
                    return
                
                # ============================================================
                # STEP 3: Click Start button with verification
                # ============================================================
                self._log("Step 3: Clicking Start...")
                
                # Brief pause to ensure panel is fully interactive
                time.sleep(0.2)
                
                render_actually_started = False
                click_attempts = 0
                max_click_attempts = 3
                
                while not render_actually_started and click_attempts < max_click_attempts:
                    click_attempts += 1
                    
                    try:
                        # Refresh window reference
                        self._desktop = Desktop(backend="uia")
                        vantage = self._find_vantage_window()
                        if not vantage:
                            self._log("Lost Vantage window!")
                            time.sleep(0.3)
                            continue
                        
                        # Re-find the Start button (it may have changed)
                        start_btn = self._find_start_button(vantage)
                        if not start_btn:
                            self._log(f"Start button not found (attempt {click_attempts})")
                            time.sleep(0.3)
                            continue
                        
                        # Get button info for logging
                        try:
                            btn_name = start_btn.element_info.name or "unnamed"
                            btn_enabled = start_btn.is_enabled() if hasattr(start_btn, 'is_enabled') else "unknown"
                            self._log(f"Clicking button '{btn_name}' (enabled: {btn_enabled})")
                        except:
                            pass
                        
                        # Focus window and click
                        vantage.set_focus()
                        time.sleep(0.1)
                        
                        # Try click_input first (more reliable)
                        start_btn.click_input()
                        self._log(f"Click sent (attempt {click_attempts})")
                        
                        # Wait and check if progress window appears
                        time.sleep(0.5)
                        self._desktop = Desktop(backend="uia")
                        progress_win = self._find_progress_window()
                        
                        if progress_win:
                            self._log("Progress window detected - render started!")
                            render_actually_started = True
                        else:
                            # Check if Start button is still there (if gone, render probably started)
                            vantage = self._find_vantage_window()
                            if vantage:
                                start_btn_check = self._find_start_button(vantage)
                                if not start_btn_check:
                                    self._log("Start button gone - render likely started!")
                                    render_actually_started = True
                                else:
                                    self._log(f"Start button still visible - click may not have worked")
                                    # Try invoke() as fallback
                                    if click_attempts < max_click_attempts:
                                        try:
                                            self._log("Trying invoke() method...")
                                            start_btn_check.invoke()
                                            time.sleep(0.5)
                                            self._desktop = Desktop(backend="uia")
                                            if self._find_progress_window():
                                                self._log("Progress window detected after invoke!")
                                                render_actually_started = True
                                        except Exception as e:
                                            self._log(f"Invoke failed: {e}")
                            else:
                                # Window gone - might be a crash or render started
                                self._log("Vantage window not found after click")
                                time.sleep(1.0)
                        
                    except Exception as e:
                        self._log(f"Click attempt {click_attempts} failed: {e}")
                        time.sleep(0.3)
                
                if not render_actually_started:
                    # One final check for progress window
                    time.sleep(1.0)
                    self._desktop = Desktop(backend="uia")
                    if self._find_progress_window():
                        self._log("Progress window found on final check!")
                        render_actually_started = True
                    else:
                        on_error("Failed to start render - Start button click did not work after 3 attempts")
                        return
                
                # ============================================================
                # STEP 4: Monitor progress
                # ============================================================
                self._log("Step 4: Monitoring render progress...")
                
                job.progress = 0
                on_progress(0, "Render starting...")
                
                render_start = time.time()
                last_progress = -1
                progress_window_seen = False
                no_window_count = 0
                last_log_time = time.time()
                
                while not self.is_cancelling:
                    elapsed = time.time() - render_start
                    
                    # Refresh desktop periodically
                    self._desktop = Desktop(backend="uia")
                    
                    # Find progress window
                    progress_win = self._find_progress_window()
                    
                    if progress_win:
                        progress_window_seen = True
                        no_window_count = 0
                        
                        # Read progress
                        progress_info = self._read_progress(progress_win)
                        
                        if progress_info:
                            total_pct = progress_info.get('total', 0)
                            frame_pct = progress_info.get('frame_pct', 0)
                            current_frame = progress_info.get('frame', 0)
                            total_frames = progress_info.get('total_frames', 1)
                            elapsed_str = progress_info.get('elapsed', '')
                            remaining_str = progress_info.get('remaining', '')
                            
                            # Calculate total from frame progress if not set
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
                                
                                # Update frame progress for display
                                if frame_pct > 0:
                                    job.current_sample = frame_pct
                                    job.total_samples = 100
                                
                                # Build status message
                                if current_frame > 0 and total_frames > 1:
                                    status = f"Frame {current_frame}/{total_frames} ({total_pct}%)"
                                else:
                                    status = f"Rendering... {total_pct}%"
                                
                                on_progress(total_pct, status)
                                
                                # Log with time info if available
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
                        # Progress window was open but now closed
                        no_window_count += 1
                        if no_window_count >= 5:
                            self._log("Progress window closed - render complete!")
                            job.progress = 100
                            on_complete()
                            return
                    else:
                        # No progress window yet - might still be starting
                        if elapsed > 30 and not progress_window_seen:
                            self._log("Warning: No progress window detected after 30s")
                            # Continue waiting - render might still work
                    
                    # Timeout after 2 hours
                    if elapsed > 7200:
                        on_error("Render timed out after 2 hours")
                        return
                    
                    time.sleep(0.5)
                
                self._log("Render cancelled by user")
                
            except Exception as e:
                if not self.is_cancelling:
                    self._log(f"Error: {e}")
                    on_error(str(e))
        
        threading.Thread(target=render_thread, daemon=True).start()
    
    def cancel_render(self):
        """Cancel the current render."""
        self._log("Cancelling render...")
        self.is_cancelling = True
        
        # Try to click Stop button in progress window
        try:
            if self._desktop:
                progress_win = self._find_progress_window()
                if progress_win:
                    # Look for stop/cancel button
                    for btn_name in ["stop", "cancel", "abort", "close"]:
                        btn = self._find_button_multilevel(progress_win, btn_name)
                        if btn:
                            try:
                                btn.click_input()
                                self._log(f"Clicked {btn_name} button")
                                break
                            except:
                                pass
                    
                    # Fallback: send Escape
                    try:
                        from pywinauto import keyboard
                        progress_win.set_focus()
                        keyboard.send_keys("{ESCAPE}")
                    except:
                        pass
        except:
            pass
        
        # Cleanup
        self._vantage_window = None
        self._desktop = None
        self._on_log = None
        self._job = None
