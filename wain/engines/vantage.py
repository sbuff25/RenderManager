"""
Wain Vantage Engine v2.15.48
============================

Chaos Vantage render engine integration with STATE MACHINE control.

v2.15.48 - Large Job Progress Tracking Fix:
-------------------------------------------
- REMOVED 2-hour timeout - renders can now take unlimited time (days if needed)
- Progress tracking now only goes FORWARD - never backwards
- Tracks highest_frame_seen and highest_progress_seen
- Frame count won't reset to 1 after logging completion of higher frames
- Preserves progress when resuming paused jobs (doesn't reset to 0)
- Vantage handles its own completion/error states

v2.15.47 - Responsive Actions & Auto-Close:
-------------------------------------------
- All actions (pause/resume/delete) run in background threads - no UI blocking
- No more "lost connection" messages when pausing/resuming/deleting
- Vantage closes automatically on render completion
- Vantage closes when deleting a job (active or paused)

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

from wain.engines.base import RenderEngine
from wain.engines.vantage_settings import (
    VantageINIManager,
    VantageHQSettings,
    apply_vantage_settings,
    read_vantage_settings,
    DRY_RUN,
)


class VantageEngine(RenderEngine):
    """Chaos Vantage render engine - load scene and render with scene settings."""
    
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
    
    # Live Link HTTP API port (Vantage starts this server when fully loaded)
    # This is the definitive signal that Vantage is ready to accept commands
    LIVE_LINK_PORT = 20701
    
    # State machine constants
    STATE_INIT = "Initializing"
    STATE_LAUNCHING = "Launching Vantage"
    STATE_SCENE_LOADING = "Loading Scene"
    STATE_OPENING_PANEL = "Opening HQ Panel"
    STATE_CLICKING_START = "Starting Render"
    STATE_RENDERING = "Rendering"
    STATE_COMPLETE = "Complete"
    STATE_ERROR = "Error"
    
    def __init__(self):
        super().__init__()
        self._on_log = None
        self._job = None
        self._vantage_window = None
        self._desktop = None
        self._current_state = None  # Current state machine state
        self._state_data = {}       # State-specific data (booleans, etc.)
        self._debug_mode = os.environ.get('WAIN_DEBUG', '').lower() in ('1', 'true', 'yes')
        self._debug_log_file = None
        self._startup_time = None
        self.scan_installed_versions()
    
    def _debug_log(self, msg: str, also_normal: bool = False):
        """
        Write detailed debug log entry with precise timestamp.
        Only writes if debug mode is enabled.
        """
        if not self._debug_mode and not also_normal:
            return
        
        # Calculate elapsed time from startup
        elapsed = ""
        if self._startup_time:
            elapsed = f"+{time.time() - self._startup_time:.3f}s"
        
        timestamp = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"
        log_line = f"[{timestamp}] [{elapsed:>10}] {msg}"
        
        # Write to debug log file
        if self._debug_log_file:
            try:
                with open(self._debug_log_file, 'a', encoding='utf-8') as f:
                    f.write(log_line + "\n")
            except:
                pass
        
        # Also print to console in debug mode
        if self._debug_mode:
            print(f"[VANTAGE DEBUG] {log_line}")
        
        # Optionally also log to normal Wain log
        if also_normal and self._on_log:
            self._on_log(f"[Vantage] {msg}")
    
    def _dump_window_state(self, window, label: str = ""):
        """Dump complete window state for debugging."""
        if not self._debug_mode:
            return
        
        self._debug_log(f"=== WINDOW STATE DUMP: {label} ===")
        
        if not window:
            self._debug_log("  Window: NULL")
            return
        
        try:
            # Window info
            title = window.window_text() or "(no title)"
            class_name = window.element_info.class_name or "(no class)"
            self._debug_log(f"  Title: '{title}'")
            self._debug_log(f"  Class: {class_name}")
            
            try:
                rect = window.element_info.rectangle
                self._debug_log(f"  Size: {rect.width()}x{rect.height()} at ({rect.left},{rect.top})")
            except:
                pass
            
            # Count all control types
            control_counts = {}
            try:
                for elem in window.descendants():
                    try:
                        ct = elem.element_info.control_type or "Unknown"
                        control_counts[ct] = control_counts.get(ct, 0) + 1
                    except:
                        pass
            except:
                pass
            
            self._debug_log(f"  Control counts: {control_counts}")
            
            # All buttons with names
            buttons = []
            try:
                for btn in window.descendants(control_type="Button"):
                    try:
                        name = btn.element_info.name or ""
                        auto_id = btn.element_info.automation_id or ""
                        enabled = btn.is_enabled()
                        if name or auto_id:
                            buttons.append(f"'{name}' id={auto_id} enabled={enabled}")
                    except:
                        pass
            except:
                pass
            
            self._debug_log(f"  Buttons ({len(buttons)}):")
            for b in buttons[:30]:
                self._debug_log(f"    {b}")
            
            # All text elements
            texts = []
            try:
                for txt in window.descendants(control_type="Text"):
                    try:
                        name = txt.element_info.name or ""
                        if name.strip():
                            texts.append(name.strip())
                    except:
                        pass
            except:
                pass
            
            self._debug_log(f"  Text elements ({len(texts)}):")
            for t in texts[:30]:
                self._debug_log(f"    '{t}'")
            
            # Progress bars
            try:
                pbs = list(window.descendants(control_type="ProgressBar"))
                if pbs:
                    self._debug_log(f"  Progress bars ({len(pbs)}):")
                    for pb in pbs:
                        try:
                            name = pb.element_info.name or ""
                            val = pb.get_value() if hasattr(pb, 'get_value') else "?"
                            self._debug_log(f"    '{name}' value={val}")
                        except:
                            pass
            except:
                pass
            
            # Menu bar
            try:
                for child in window.children():
                    if child.element_info.control_type == "MenuBar":
                        menus = [m.element_info.name for m in child.children() if m.element_info.name]
                        self._debug_log(f"  Menu bar: {menus}")
                        break
            except:
                pass
            
        except Exception as e:
            self._debug_log(f"  Error dumping window: {e}")
        
        self._debug_log("=== END WINDOW STATE ===")
    
    def _start_debug_session(self, job_name: str):
        """Initialize debug logging for a render session."""
        self._startup_time = time.time()
        
        if self._debug_mode:
            # Create debug log file
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self._debug_log_file = f"vantage_debug_{timestamp}.log"
            
            self._debug_log("=" * 70)
            self._debug_log("WAIN VANTAGE DEBUG LOG")
            self._debug_log(f"Job: {job_name}")
            self._debug_log(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            self._debug_log(f"Debug mode: ENABLED")
            self._debug_log("=" * 70)
            
            print(f"[WAIN DEBUG] Debug log: {self._debug_log_file}")
    
    def _end_debug_session(self):
        """End debug logging session."""
        if self._debug_mode and self._debug_log_file:
            elapsed = time.time() - self._startup_time if self._startup_time else 0
            self._debug_log(f"Session ended. Total time: {elapsed:.1f}s")
            self._debug_log("=" * 70)
            print(f"[WAIN DEBUG] Debug log saved: {self._debug_log_file}")
        
        self._debug_log_file = None
        self._startup_time = None
    
    def _log(self, msg: str):
        """Log a message."""
        if self._on_log:
            self._on_log(f"[Vantage] {msg}")
        # Also write to debug log
        self._debug_log(msg, also_normal=False)
    
    def _check_live_link(self) -> bool:
        """
        Check if Vantage Live Link server is responding.
        
        This is the DEFINITIVE signal that Vantage is fully loaded and ready.
        The Live Link server only starts after the scene is fully loaded and
        all initialization is complete.
        
        Returns:
            True if Live Link is responding, False otherwise
        """
        import socket
        
        try:
            # Quick TCP connection test - faster than HTTP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)  # 500ms timeout
            result = sock.connect_ex(('127.0.0.1', self.LIVE_LINK_PORT))
            sock.close()
            return result == 0
        except:
            return False
    
    def _check_live_link_http(self) -> bool:
        """
        Check if Vantage Live Link HTTP API is responding.
        
        This is a more thorough check that verifies the HTTP server is working.
        """
        from urllib.request import urlopen, Request
        from urllib.error import URLError
        
        try:
            url = f"http://127.0.0.1:{self.LIVE_LINK_PORT}/"
            req = Request(url, method='GET')
            with urlopen(req, timeout=1) as response:
                return response.status < 500
        except:
            return False
    
    def _check_live_link_status_bar(self, window) -> tuple:
        """
        Check Vantage's status bar for Live Link status.
        
        Vantage shows "Waiting for live link on port 20701 and 20703" in the
        status bar while initializing. When this message disappears, Live Link
        is established and Vantage is ready.
        
        Returns:
            (is_ready, status_text) - is_ready=True when Live Link is established
        """
        if not window:
            return (False, "")
        
        try:
            # Look through all text elements for status bar messages
            for text_elem in window.descendants(control_type="Text"):
                try:
                    text = text_elem.element_info.name or ""
                    text_lower = text.lower()
                    
                    # Check for "Waiting for live link" message
                    if "waiting for live link" in text_lower:
                        return (False, text.strip())
                    
                    # Check for "live link" being mentioned (could be other states)
                    if "live link" in text_lower and "waiting" not in text_lower:
                        # Live Link mentioned but not "waiting" - might be connected
                        return (True, text.strip())
                except:
                    pass
        except:
            pass
        
        # If we didn't find any "waiting for live link" text, assume it's ready
        # (the message only appears during initialization)
        return (True, "")
    
    def _set_state(self, state: str, on_progress=None, progress_msg: str = None):
        """
        Transition to a new state. Logs the transition and updates UI.
        
        Args:
            state: One of the STATE_* constants
            on_progress: Optional progress callback
            progress_msg: Optional message for UI (defaults to state name)
        """
        old_state = self._current_state
        self._current_state = state
        
        # Log state transition
        if old_state:
            self._log(f"State: {old_state} → {state}")
        else:
            self._log(f"State: {state}")
        
        # Update UI with current state
        if on_progress:
            msg = progress_msg or state
            on_progress(0, msg)
    
    def _is_state(self, state: str) -> bool:
        """Check if we're in a specific state."""
        return self._current_state == state
    
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
        """Vantage uses scene settings - no custom settings needed."""
        return {}
    
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
        """
        Read scene info from both vantage.ini AND the .vantage scene file.
        
        This is a READ-ONLY operation - completely safe.
        
        From vantage.ini:
            - Resolution, samples, denoiser (HQ Render defaults)
        
        From .vantage file:
            - Camera list with per-camera resolutions
            - Animation FPS and duration → frame count
        """
        # Default values
        info = {
            "cameras": [],
            "active_camera": "",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "frame_start": 1,
            "frame_end": 1,
            "total_frames": 1,
            "has_animation": False,
            "animation_fps": 30.0,
            # Vantage-specific settings (read from INI)
            "samples": 100,
            "denoise_enabled": True,
            "denoiser_type": 0,  # 0=NVIDIA, 1=OIDN, 2=Off
            "denoiser_name": "nvidia",
            # Per-camera resolutions from scene file
            "camera_resolutions": {},
        }
        
        # =====================================================================
        # PART 1: Read HQ settings from vantage.ini
        # =====================================================================
        try:
            settings = read_vantage_settings()
            if settings:
                info["resolution_x"] = settings.width
                info["resolution_y"] = settings.height
                info["samples"] = settings.samples
                info["denoise_enabled"] = settings.denoise_enabled
                info["denoiser_type"] = settings.denoiser_type
                
                # Map denoiser type to name
                denoiser_names = {0: "nvidia", 1: "oidn", 2: "off"}
                info["denoiser_name"] = denoiser_names.get(settings.denoiser_type, "nvidia")
                
                print(f"[Wain] INI settings: {settings.width}x{settings.height}, {settings.samples} samples, denoiser={info['denoiser_name']}")
        except Exception as e:
            print(f"[Wain] Could not read vantage.ini: {e}")
        
        # =====================================================================
        # PART 2: Read cameras and animation from .vantage scene file
        # =====================================================================
        if file_path and file_path.lower().endswith('.vantage') and os.path.exists(file_path):
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    scene_data = json.load(f)
                
                # --- Cameras ---
                cameras = scene_data.get('cameras', [])
                camera_names = []
                camera_resolutions = {}
                
                for i, cam in enumerate(cameras):
                    name = cam.get('name', f'Camera {i}')
                    camera_names.append(name)
                    
                    # Store per-camera resolution
                    res_x = cam.get('resolution_x', 0)
                    res_y = cam.get('resolution_y', 0)
                    if res_x > 0 and res_y > 0:
                        camera_resolutions[name] = (res_x, res_y)
                
                if camera_names:
                    info["cameras"] = camera_names
                    info["active_camera"] = camera_names[0]
                    info["camera_resolutions"] = camera_resolutions
                    print(f"[Wain] Scene cameras: {len(camera_names)} found")
                
                # --- Animation / Frame Count ---
                fps = scene_data.get('animation_fps', 30.0)
                info["animation_fps"] = fps
                
                # Calculate total duration from animation tracks
                tracks = scene_data.get('animation_tracks', [])
                max_duration = 0.0
                for track in tracks:
                    for item in track.get('track_items', []):
                        dur = item.get('duration', 0.0)
                        max_duration = max(max_duration, dur)
                
                # Also check trim values
                trim_start = scene_data.get('animation_trim_start', 0.0)
                trim_end = scene_data.get('animation_trim_end', 0.0)
                
                # Calculate frame count
                if max_duration > 0:
                    total_frames = int(max_duration * fps)
                    info["frame_start"] = 1
                    info["frame_end"] = max(1, total_frames)
                    info["total_frames"] = total_frames
                    info["has_animation"] = total_frames > 1
                    print(f"[Wain] Animation: {max_duration}s @ {fps}fps = {total_frames} frames")
                
            except json.JSONDecodeError as e:
                print(f"[Wain] Could not parse .vantage file: {e}")
            except Exception as e:
                print(f"[Wain] Error reading .vantage file: {e}")
        
        return info
    
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
    
    def _find_button_with_timeout(self, window, auto_id: str = None, title: str = None, timeout: float = 1.0):
        """
        Find a button with an ENFORCED timeout using ThreadPoolExecutor.
        
        pywinauto's child_window() and descendants() block indefinitely
        and ignore timeout parameters. This wrapper forces a real timeout.
        """
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        
        if not window:
            return None
        
        def search():
            try:
                if auto_id:
                    btn = window.child_window(auto_id=auto_id, control_type="Button")
                elif title:
                    btn = window.child_window(title=title, control_type="Button")
                else:
                    return None
                
                # Verify button exists by accessing a property
                _ = btn.element_info.name
                return btn
            except Exception:
                return None
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(search)
                return future.result(timeout=timeout)
        except FuturesTimeoutError:
            self._log(f"  Button search timed out ({timeout}s)")
            return None
        except Exception:
            return None
    
    def _find_start_button(self, window):
        """
        Find the Start button with multiple strategies.
        
        Tries:
        1. auto_id="primaryButton"
        2. title="Start"
        3. title contains "Start"
        4. Any button with "start" in name (case-insensitive)
        """
        if not window:
            return None
        
        t0 = time.time()
        
        # Method 1: Direct ID lookup (common pattern)
        btn = self._find_button_with_timeout(window, auto_id="primaryButton", timeout=0.5)
        if btn:
            self._log(f"  Found by ID 'primaryButton' ({time.time()-t0:.2f}s)")
            return btn
        
        # Method 2: By exact title "Start"
        btn = self._find_button_with_timeout(window, title="Start", timeout=0.5)
        if btn:
            self._log(f"  Found by title 'Start' ({time.time()-t0:.2f}s)")
            return btn
        
        # Method 3: Manual search through all buttons for any with "start" in name
        try:
            for b in window.descendants(control_type="Button"):
                try:
                    name = (b.element_info.name or "").lower()
                    auto_id = (b.element_info.automation_id or "").lower()
                    
                    if "start" in name or "start" in auto_id:
                        self._log(f"  Found by manual search: name='{b.element_info.name}' id='{b.element_info.automation_id}' ({time.time()-t0:.2f}s)")
                        return b
                except:
                    pass
        except:
            pass
        
        # Method 4: Look for common render/begin button patterns
        try:
            for b in window.descendants(control_type="Button"):
                try:
                    name = (b.element_info.name or "").lower()
                    auto_id = (b.element_info.automation_id or "").lower()
                    
                    # Look for render-related buttons
                    if any(kw in name for kw in ["render", "begin", "go"]):
                        self._log(f"  Found render button: name='{b.element_info.name}' id='{b.element_info.automation_id}' ({time.time()-t0:.2f}s)")
                        return b
                    if any(kw in auto_id for kw in ["render", "begin", "primary"]):
                        self._log(f"  Found by ID pattern: name='{b.element_info.name}' id='{b.element_info.automation_id}' ({time.time()-t0:.2f}s)")
                        return b
                except:
                    pass
        except:
            pass
        
        return None
    
    def _find_button_multilevel(self, window, name: str, timeout: float = 1.0):
        """Find a button by name with enforced timeout (for pause/abort/etc)."""
        if not window:
            return None
        
        # Try capitalized first
        btn = self._find_button_with_timeout(window, title=name.capitalize(), timeout=timeout/2)
        if btn:
            return btn
        
        # Try as-is
        btn = self._find_button_with_timeout(window, title=name, timeout=timeout/2)
        return btn
    
    def _find_progress_window(self):
        """
        Find the Vantage render progress window.
        In Vantage 3.x, the progress dialog is a child window inside main window.
        """
        vantage = self._find_vantage_window()
        if not vantage:
            return None
        
        try:
            # Look for progress dialog as child
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
            
            # Check Window-type descendants
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
        Read progress from Vantage 3.x progress dialog.
        Parses 'HQ sequence frame X of Y' for frame count.
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
            
        except Exception:
            return None
    
    def _send_ctrl_r(self, window):
        """Send Ctrl+R with robust focus handling."""
        from pywinauto import keyboard
        import ctypes
        
        t0 = time.time()
        
        # Aggressive focus - try multiple methods
        try:
            # Method 1: pywinauto set_focus
            window.set_focus()
            time.sleep(0.05)
        except:
            pass
        
        t1 = time.time()
        if t1 - t0 > 1.0:
            self._log(f"  set_focus took {t1-t0:.1f}s")
        
        try:
            # Method 2: Win32 SetForegroundWindow
            hwnd = window.handle
            if hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.05)
        except:
            pass
        
        # Send Ctrl+R via pywinauto
        try:
            keyboard.send_keys("^r", pause=0.02)
            time.sleep(0.1)
            return True
        except:
            pass
        
        # Fallback: Native Windows API
        try:
            VK_CONTROL = 0x11
            VK_R = 0x52
            KEYEVENTF_KEYUP = 0x0002
            
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_R, 0, 0, 0)
            time.sleep(0.02)
            ctypes.windll.user32.keybd_event(VK_R, 0, KEYEVENTF_KEYUP, 0)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)
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
    
    def _find_edit_field(self, window, name_contains: str):
        """
        Find an edit field by partial name match.
        
        Note: This is a fallback method. For Vantage frame fields,
        use _find_frame_spinners() which matches by position.
        """
        if not window:
            return None
        
        name_lower = name_contains.lower()
        
        # Strategy 1: Search Edit controls
        try:
            for edit in window.descendants(control_type="Edit"):
                try:
                    edit_name = (edit.element_info.name or "").lower()
                    auto_id = (edit.element_info.automation_id or "").lower()
                    
                    if name_lower in edit_name or name_lower in auto_id:
                        return edit
                except:
                    pass
        except:
            pass
        
        return None
    
    def _get_element_rect(self, elem):
        """Get element rectangle as dict."""
        try:
            r = elem.element_info.rectangle
            return {"left": r.left, "top": r.top, "right": r.right, "bottom": r.bottom}
        except:
            return None
    
    def _find_frame_spinners(self, window):
        """
        Find First frame and Last frame spinners by position.
        
        Vantage's spinners don't have useful names/IDs, so we:
        1. Find the "First frame" and "Last frame" text labels
        2. Find spinners that are on the same row (by top position)
        3. Match each label to the spinner immediately to its right
        
        Returns: (first_frame_spinner, last_frame_spinner) or (None, None)
        """
        if not window:
            return None, None
        
        first_frame_rect = None
        last_frame_rect = None
        
        # Find the text labels
        try:
            for text in window.descendants(control_type="Text"):
                try:
                    name = (text.element_info.name or "").lower().strip()
                    if name == "first frame":
                        first_frame_rect = self._get_element_rect(text)
                        self._log(f"Found 'First frame' label at top={first_frame_rect['top']}")
                    elif name == "last frame":
                        last_frame_rect = self._get_element_rect(text)
                        self._log(f"Found 'Last frame' label at top={last_frame_rect['top']}")
                except:
                    pass
        except:
            pass
        
        if not first_frame_rect or not last_frame_rect:
            self._log("Could not find frame labels")
            return None, None
        
        # Collect all spinners with positions
        spinners = []
        try:
            for spinner in window.descendants(control_type="Spinner"):
                try:
                    rect = self._get_element_rect(spinner)
                    if rect:
                        spinners.append({"element": spinner, "rect": rect})
                except:
                    pass
        except:
            pass
        
        self._log(f"Found {len(spinners)} spinners")
        
        # Find spinner on same row as each label
        def find_spinner_on_row(label_rect, tolerance=30):
            label_top = label_rect['top']
            label_right = label_rect['right']
            
            candidates = []
            for sp in spinners:
                sp_rect = sp['rect']
                # Check if on same row (within tolerance)
                if abs(sp_rect['top'] - label_top) < tolerance:
                    # Check if to the right of label
                    if sp_rect['left'] > label_right - 50:
                        distance = sp_rect['left'] - label_right
                        candidates.append((distance, sp['element']))
            
            # Return closest spinner to the right
            if candidates:
                candidates.sort(key=lambda x: x[0])
                return candidates[0][1]
            return None
        
        first_spinner = find_spinner_on_row(first_frame_rect)
        last_spinner = find_spinner_on_row(last_frame_rect)
        
        if first_spinner:
            self._log("Matched First frame spinner")
        if last_spinner:
            self._log("Matched Last frame spinner")
        
        return first_spinner, last_spinner
    
    def _set_frame_range(self, window, first_frame: int, last_frame: int) -> bool:
        """
        Set the First Frame and Last Frame values in the HQ Render panel.
        
        Uses position-based matching to find the correct spinners,
        then clicks and types the values.
        
        Returns True if both fields were set successfully.
        """
        from pywinauto import keyboard
        
        # Find spinners by position relative to labels
        first_spinner, last_spinner = self._find_frame_spinners(window)
        
        success = True
        
        # --- First Frame ---
        if first_spinner:
            try:
                first_spinner.click_input()
                time.sleep(0.1)
                keyboard.send_keys("^a")  # Select all
                time.sleep(0.05)
                keyboard.send_keys(str(first_frame))
                time.sleep(0.1)
                self._log(f"Set First Frame: {first_frame}")
            except Exception as e:
                self._log(f"Failed to set First Frame: {e}")
                success = False
        else:
            self._log("Could not find First Frame spinner")
            success = False
        
        # --- Last Frame ---
        if last_spinner:
            try:
                last_spinner.click_input()
                time.sleep(0.1)
                keyboard.send_keys("^a")  # Select all
                time.sleep(0.05)
                keyboard.send_keys(str(last_frame))
                time.sleep(0.1)
                self._log(f"Set Last Frame: {last_frame}")
            except Exception as e:
                self._log(f"Failed to set Last Frame: {e}")
                success = False
        else:
            self._log("Could not find Last Frame spinner")
            success = False
        
        return success
    
    def _set_output_path(self, window, output_folder: str, output_name: str, output_format: str = "png") -> bool:
        """
        Set the output path in the HQ Render panel by pasting into the Edit field.
        
        Uses clipboard paste instead of typing to prevent character scrambling.
        
        Args:
            window: The Vantage window
            output_folder: Folder path for output (e.g., "H:/Renders/Project")
            output_name: Base filename prefix (e.g., "render_")
            output_format: File extension (e.g., "png", "jpg", "exr")
        
        Returns True if output path was set successfully.
        """
        from pywinauto import keyboard
        import subprocess
        
        # Build full output path (folder + filename prefix + extension)
        # Normalize to forward slashes and ensure folder ends with /
        folder = output_folder.replace('\\', '/').rstrip('/')
        
        # Map format names to extensions
        ext_map = {
            "PNG": "png",
            "JPEG": "jpg",
            "JPG": "jpg",
            "EXR": "exr",
            "TGA": "tga",
            "TIFF": "tiff",
            "TIF": "tiff",
        }
        ext = ext_map.get(output_format.upper(), output_format.lower())
        
        # Build path: folder/prefix.ext (Vantage will insert frame numbers)
        # e.g., "H:/Renders/render_.png" -> "H:/Renders/render_0001.png"
        full_path = f"{folder}/{output_name}.{ext}"
        
        self._log(f"Setting output path: {full_path}")
        
        # Find the output path Edit field
        # It should contain path-like content (has : or / characters)
        output_edit = None
        try:
            for edit in window.descendants(control_type="Edit"):
                try:
                    # Try to get current value
                    value = ""
                    try:
                        value = edit.get_value() or ""
                    except:
                        try:
                            value = edit.window_text() or ""
                        except:
                            pass
                    
                    # Check if this looks like a path field (contains : or /)
                    if ':' in value or '/' in value or '\\' in value:
                        output_edit = edit
                        self._log(f"Found output path field with value: {value[:50]}...")
                        break
                except:
                    pass
            
            # If not found by content, look for Edit field near "Output" label
            if not output_edit:
                output_label_rect = None
                for text in window.descendants(control_type="Text"):
                    try:
                        name = (text.element_info.name or "").lower()
                        # Look for "Output file type" or similar label
                        if "output" in name and "file" in name:
                            rect = self._get_element_rect(text)
                            if rect:
                                output_label_rect = rect
                                break
                    except:
                        pass
                
                if output_label_rect:
                    # Find Edit field below or near this label
                    for edit in window.descendants(control_type="Edit"):
                        try:
                            edit_rect = self._get_element_rect(edit)
                            if edit_rect:
                                # Check if edit is below and close to the output label
                                if (edit_rect['top'] > output_label_rect['top'] and 
                                    edit_rect['top'] < output_label_rect['top'] + 60):
                                    output_edit = edit
                                    self._log("Found output path field by position")
                                    break
                        except:
                            pass
        except Exception as e:
            self._log(f"Error finding output Edit field: {e}")
        
        if not output_edit:
            self._log("Could not find output path Edit field")
            return False
        
        try:
            # Copy path to clipboard using PowerShell (most reliable on Windows)
            ps_cmd = f'Set-Clipboard -Value "{full_path}"'
            subprocess.run(['powershell', '-Command', ps_cmd], 
                          creationflags=subprocess.CREATE_NO_WINDOW,
                          timeout=5)
            time.sleep(0.1)
            
            # Click on the Edit field to focus it
            output_edit.click_input()
            time.sleep(0.15)
            
            # Select all existing content
            keyboard.send_keys("^a", pause=0.05)
            time.sleep(0.1)
            
            # Paste from clipboard (much more reliable than typing)
            keyboard.send_keys("^v", pause=0.05)
            time.sleep(0.15)
            
            # Press Tab to move focus away (confirms the value)
            keyboard.send_keys("{TAB}")
            time.sleep(0.1)
            
            self._log(f"Output path set to: {full_path}")
            return True
            
        except Exception as e:
            self._log(f"Failed to set output path: {e}")
            return False
    
    def _set_output_format(self, window, format_name: str) -> bool:
        """
        Set the output format in the HQ Render panel.
        
        Args:
            window: The Vantage window
            format_name: Format name like "PNG", "JPEG", "EXR", "TGA"
        
        Returns True if format was set successfully.
        """
        from pywinauto import keyboard
        
        self._log(f"Setting output format: {format_name}")
        
        # Map Wain format names to Vantage format names
        format_map = {
            "PNG": "png",
            "JPEG": "jpg",
            "JPG": "jpg",
            "EXR": "exr",
            "TGA": "tga",
        }
        
        vantage_format = format_map.get(format_name.upper(), "png")
        
        # Find the format ComboBox - it should be near "Output file type" label
        format_combo = None
        try:
            # Method 1: Find ComboBox containing format-like values
            for combo in window.descendants(control_type="ComboBox"):
                try:
                    value = ""
                    try:
                        value = combo.get_value() or ""
                    except:
                        try:
                            value = combo.window_text() or ""
                        except:
                            pass
                    
                    value_lower = value.lower()
                    # Check if current value looks like a format
                    if any(fmt in value_lower for fmt in ["png", "jpg", "jpeg", "exr", "tga", "tiff"]):
                        format_combo = combo
                        self._log(f"Found format ComboBox with value: {value}")
                        break
                except:
                    pass
            
            # Method 2: Find by position near "Output file type" label
            if not format_combo:
                for text in window.descendants(control_type="Text"):
                    try:
                        name = (text.element_info.name or "").lower()
                        if "output" in name and ("file" in name or "type" in name or "format" in name):
                            text_rect = self._get_element_rect(text)
                            if text_rect:
                                # Find ComboBox near this label
                                for combo in window.descendants(control_type="ComboBox"):
                                    try:
                                        combo_rect = self._get_element_rect(combo)
                                        if combo_rect:
                                            # Check if combo is on same row or just below
                                            if abs(combo_rect['top'] - text_rect['top']) < 40:
                                                format_combo = combo
                                                self._log("Found format ComboBox by position")
                                                break
                                    except:
                                        pass
                            if format_combo:
                                break
                    except:
                        pass
        except Exception as e:
            self._log(f"Error finding format ComboBox: {e}")
        
        if not format_combo:
            self._log("Could not find format ComboBox - format may need manual selection")
            return False
        
        try:
            # Click to open dropdown
            format_combo.click_input()
            time.sleep(0.2)
            
            # Type the format name to select it (most ComboBoxes support type-to-search)
            keyboard.send_keys(vantage_format, pause=0.05)
            time.sleep(0.1)
            
            # Press Enter to confirm selection
            keyboard.send_keys("{ENTER}")
            time.sleep(0.1)
            
            self._log(f"Output format set to: {vantage_format}")
            return True
            
        except Exception as e:
            self._log(f"Failed to set output format: {e}")
            # Try pressing Escape to close any open dropdown
            try:
                keyboard.send_keys("{ESC}")
            except:
                pass
            return False
    
    # =========================================================================
    # MAIN RENDER METHOD
    # =========================================================================
    
    def start_render(self, job, start_frame: int, on_progress, on_complete, on_error, on_log=None):
        """
        Start rendering a Vantage job.
        
        Flow:
        1. If job has custom settings → Apply to INI file
        2. Launch Vantage with the scene
        3. Open HQ Render panel (Ctrl+R)
        4. Click Start
        5. Monitor progress until complete
        """
        if not os.path.exists(job.file_path):
            on_error(f"Scene file not found: {job.file_path}")
            return
        
        self.is_cancelling = False
        self._on_log = on_log
        self._job = job
        
        # Start debug session if enabled
        self._start_debug_session(job.name)
        
        self._log("=" * 50)
        self._log("Wain Vantage Engine v2.15.33 - Debug Logging")
        self._log(f"Scene: {job.file_path}")
        if self._debug_mode:
            self._log(f"DEBUG MODE: Detailed log → {self._debug_log_file}")
        
        # ============================================================
        # STEP 0: Apply custom settings if configured
        # ============================================================
        use_custom_settings = job.engine_settings.get('use_custom_settings', False)
        
        if use_custom_settings:
            self._log("Applying custom HQ settings...")
            
            width = job.engine_settings.get('width', job.res_width)
            height = job.engine_settings.get('height', job.res_height)
            samples = job.engine_settings.get('samples')
            denoiser = job.engine_settings.get('denoiser')
            
            # Build output path from job settings
            # Note: Output path with filename prefix must be set via UI automation
            # (INI SaveImage only stores folder, not filename prefix)
            output_folder = job.output_folder
            output_name = job.output_name
            
            # Apply settings to INI (resolution, samples, denoiser only - NOT output path)
            try:
                success = apply_vantage_settings(
                    width=width,
                    height=height,
                    samples=samples,
                    denoiser=denoiser,
                    output_path=None,  # Don't set via INI - use UI automation instead
                    log_func=self._log
                )
                
                if success:
                    self._log(f"INI settings applied: {width}x{height}, {samples} samples, denoiser={denoiser}")
                else:
                    self._log("WARNING: Could not apply INI settings - will use Vantage defaults")
            except Exception as e:
                self._log(f"WARNING: INI settings error: {e} - will use Vantage defaults")
        else:
            self._log("Using existing Vantage HQ settings")
        
        self._log("=" * 50)
        
        def render_thread():
            try:
                from pywinauto import Desktop, keyboard
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
            except ImportError:
                on_error("pywinauto not installed. Run: pip install pywinauto")
                return
            
            # ================================================================
            # STATE MACHINE SETUP
            # ================================================================
            # State data - booleans tracking what we've completed
            state = {
                'vantage_checked': False,      # Checked for existing instance
                'vantage_launched': False,     # Launched Vantage process
                'window_found': False,         # Found Vantage window
                'scene_ready': False,          # Scene is loaded and responsive
                'ctrl_r_sent': False,          # Ctrl+R has been sent (ONLY ONCE!)
                'panel_open': False,           # HQ panel is open (Start button visible)
                'start_clicked': False,        # Start button was clicked
                'render_started': False,       # Progress window appeared
            }
            
            vantage = None
            start_btn = None
            
            try:
                self._desktop = Desktop(backend="uia")
                
                # ============================================================
                # STATE: INIT - Check for existing Vantage instance
                # ============================================================
                self._set_state(self.STATE_INIT, on_progress, "Checking Vantage...")
                
                # SAFETY CHECK 1: Check for Vantage PROCESSES (catches zombie processes)
                vantage_process_running = False
                try:
                    result = subprocess.run(
                        ['tasklist', '/FI', 'IMAGENAME eq vantage.exe', '/NH'],
                        capture_output=True, text=True, timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if 'vantage.exe' in result.stdout.lower():
                        vantage_process_running = True
                        self._log("Found vantage.exe process running")
                except Exception as e:
                    self._log(f"Process check error: {e}")
                
                # SAFETY CHECK 2: Check for Vantage WINDOWS
                vantage = self._find_vantage_window()
                state['vantage_checked'] = True
                
                if vantage_process_running or vantage:
                    # ============================================================
                    # RESUME CHECK: If Vantage is running, check for Resume button
                    # This happens when user pauses then resumes a render
                    # ============================================================
                    self._log("Vantage is already running - checking for Resume button...")
                    
                    # Make sure Desktop is initialized for progress window search
                    if not self._desktop:
                        self._desktop = Desktop(backend="uia")
                    
                    progress_win = self._find_progress_window()
                    if progress_win:
                        self._log("Found progress window - looking for Resume button...")
                        
                        # List all buttons for debugging
                        all_buttons = []
                        for btn in progress_win.descendants(control_type="Button"):
                            try:
                                name = btn.element_info.name or ""
                                auto_id = btn.element_info.automation_id or ""
                                if name or auto_id:
                                    all_buttons.append(f"{name}[{auto_id}]")
                            except:
                                pass
                        self._log(f"Progress window buttons: {all_buttons[:10]}")
                        
                        # Look for Resume button - try multiple variations
                        # The button might be named "Resume", "Play", or have specific automation ID
                        resume_btn = None
                        for btn in progress_win.descendants(control_type="Button"):
                            try:
                                name = (btn.element_info.name or "").lower()
                                auto_id = (btn.element_info.automation_id or "").lower()
                                # Check for resume/play button (Pause toggles to Resume when paused)
                                if "resume" in name or "resume" in auto_id:
                                    resume_btn = btn
                                    self._log(f"Found Resume button: '{btn.element_info.name}' [{auto_id}]")
                                    break
                                # Also check for play button or secondary button
                                if "play" in name or "continue" in name:
                                    resume_btn = btn
                                    self._log(f"Found Play/Continue button: '{btn.element_info.name}' [{auto_id}]")
                                    break
                            except:
                                pass
                        
                        # If no explicit Resume button, check if Pause button is now a toggle
                        if not resume_btn:
                            for btn in progress_win.descendants(control_type="Button"):
                                try:
                                    name = (btn.element_info.name or "").lower()
                                    auto_id = (btn.element_info.automation_id or "").lower()
                                    # The secondary button might toggle between Pause/Resume
                                    if "secondary" in auto_id or "pause" in auto_id:
                                        resume_btn = btn
                                        self._log(f"Found toggle button: '{btn.element_info.name}' [{auto_id}]")
                                        break
                                except:
                                    pass
                        
                        if resume_btn:
                            # Click Resume and go straight to monitoring
                            self._log("Clicking Resume to continue paused render...")
                            try:
                                resume_btn.click_input()
                                self._log("Clicked Resume button!")
                            except Exception as e:
                                self._log(f"click_input failed: {e}, trying invoke()")
                                try:
                                    resume_btn.invoke()
                                    self._log("Resume invoked!")
                                except:
                                    pass
                            
                            # Small delay then go to monitoring
                            time.sleep(0.3)
                            
                            # Skip to monitoring phase
                            self._set_state(self.STATE_RENDERING, on_progress, "Resuming render...")
                            self._vantage_window = vantage
                            
                            # Jump to monitoring loop
                            self._log("Resumed! Now monitoring progress...")
                            self._monitor_render(job, on_progress, on_complete, on_error)
                            return
                        else:
                            self._log("No Resume button found - render may not be paused")
                    
                    # No resumable state found - treat as error
                    self._log("=" * 50)
                    self._log("ERROR: Vantage is already running!")
                    self._log("=" * 50)
                    
                    if vantage_process_running and not vantage:
                        self._log("A Vantage process is running without a visible window.")
                        self._log("This can happen after a crash or improper shutdown.")
                        self._log("")
                        self._log("Steps to fix:")
                        self._log("  1. Open Task Manager (Ctrl+Shift+Esc)")
                        self._log("  2. Find 'vantage.exe' in processes")
                        self._log("  3. End the task")
                        self._log("  4. Retry the job in Wain")
                        on_error("Zombie Vantage process detected. Please end vantage.exe in Task Manager, then retry.")
                    else:
                        self._log("For safety, please close Vantage before starting a render job.")
                        self._log("Running Wain while Vantage is open can cause GPU resource conflicts.")
                        self._log("")
                        self._log("Steps to fix:")
                        self._log("  1. Close Vantage (save your work first)")
                        self._log("  2. Click 'Retry' or re-queue the job in Wain")
                        self._log("  3. Wain will launch Vantage automatically")
                        on_error("Vantage is already running. Please close Vantage first, then retry the job.")
                    return
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STATE: LAUNCHING - Launch Vantage process
                # ============================================================
                self._set_state(self.STATE_LAUNCHING, on_progress, "Launching Vantage...")
                
                vantage_exe = self.get_vantage_exe()
                if not vantage_exe:
                    on_error("Vantage executable not found")
                    return
                
                self._log(f"Launching: {vantage_exe}")
                subprocess.Popen(
                    [vantage_exe, job.file_path],
                    creationflags=subprocess.DETACHED_PROCESS
                )
                state['vantage_launched'] = True
                
                # Wait for window to appear
                self._log("Waiting for Vantage window...")
                wait_start = time.time()
                while time.time() - wait_start < 60:
                    if self.is_cancelling:
                        return
                    
                    self._desktop = Desktop(backend="uia")
                    vantage = self._find_vantage_window()
                    if vantage:
                        elapsed = time.time() - wait_start
                        self._log(f"Window found! ({elapsed:.1f}s)")
                        state['window_found'] = True
                        break
                    time.sleep(0.2)
                
                if not state['window_found']:
                    on_error("Vantage did not start within 1 minute")
                    return
                
                self._vantage_window = vantage
                
                # ============================================================
                # STATE: SCENE_LOADING - Wait for scene to be FULLY ready
                # ============================================================
                self._set_state(self.STATE_SCENE_LOADING, on_progress, "Loading scene...")
                
                # Large scenes can take several minutes to load
                # We need to detect when Vantage is truly ready, not just when UI appears
                SCENE_LOAD_TIMEOUT = 300  # 5 minutes max for scene loading
                
                scene_name = os.path.basename(job.file_path)
                self._log(f"Waiting for Vantage to load: {scene_name}")
                self._log(f"Checking for Live Link server (port 20701)...")
                
                load_start = time.time()
                phase = "waiting_for_window"  # waiting_for_window -> waiting_for_live_link -> ready
                last_log_time = 0
                last_debug_dump = 0
                scene_ready = False
                
                self._debug_log(">>> Entering scene loading state machine (v2.15.36 - Live Link first)")
                
                while time.time() - load_start < SCENE_LOAD_TIMEOUT:
                    if self.is_cancelling:
                        self._debug_log(">>> Cancelled during scene loading")
                        return
                    
                    elapsed = time.time() - load_start
                    
                    # Refresh window reference
                    self._desktop = Desktop(backend="uia")
                    vantage = self._find_vantage_window()
                    
                    # Debug: periodic window state dump (every 5 seconds)
                    if self._debug_mode and elapsed - last_debug_dump >= 5:
                        last_debug_dump = elapsed
                        self._dump_window_state(vantage, f"Phase: {phase} @ {elapsed:.1f}s")
                    
                    # PHASE 1: Wait for Vantage window to exist
                    if phase == "waiting_for_window":
                        self._debug_log(f"Phase 1: Looking for window... ({elapsed:.2f}s)")
                        
                        if not vantage:
                            if elapsed - last_log_time >= 10:
                                last_log_time = elapsed
                                self._log(f"Waiting for Vantage window... ({elapsed:.0f}s)")
                            time.sleep(0.5)
                            continue
                        
                        self._vantage_window = vantage
                        self._log(f"Vantage window appeared ({elapsed:.1f}s)")
                        self._debug_log(f">>> PHASE 1 → PHASE 2: Window found at {elapsed:.2f}s")
                        self._dump_window_state(vantage, "Window just appeared")
                        
                        # Skip button counting - go straight to Live Link check!
                        phase = "waiting_for_live_link"
                        self._phase2_start = time.time()
                        continue
                    
                    if not vantage:
                        # Window disappeared - wait for it again
                        self._debug_log(f">>> Window lost! Reverting to Phase 1")
                        phase = "waiting_for_window"
                        time.sleep(0.5)
                        continue
                    
                    self._vantage_window = vantage
                    
                    # PHASE 2: Wait for Live Link server IMMEDIATELY (skip button counting!)
                    # Live Link TCP port 20701 opens ~8-10 seconds after Vantage launches
                    # The UI "Waiting for live link" message is about VIEWPORT render, not the server!
                    # We just need the TCP port to be open - viewport render state is irrelevant
                    if phase == "waiting_for_live_link":
                        # Track time within Phase 2
                        phase2_elapsed = time.time() - self._phase2_start
                        
                        # Check TCP port 20701 - this is the ONLY signal we need
                        # When this port opens, Vantage's Live Link server is running
                        tcp_port_open = self._check_live_link()
                        
                        self._debug_log(f"Phase 2: phase2_elapsed={phase2_elapsed:.2f}s TCP={tcp_port_open}")
                        
                        if tcp_port_open:
                            # Clean up tracking attributes
                            if hasattr(self, '_phase2_start'):
                                delattr(self, '_phase2_start')
                            
                            # THIS IS THE DEFINITIVE SIGNAL - Live Link server is running!
                            self._log("========================================")
                            self._log("=== LIVE LINK ESTABLISHED (port 20701) ===")
                            self._log("========================================")
                            self._log(f"Vantage ready ({elapsed:.1f}s)")
                            self._debug_log(f">>> LIVE LINK READY at {elapsed:.2f}s - TCP port open!")
                            
                            # Vantage is now DEFINITELY ready - send Ctrl+R immediately
                            # Viewport render state doesn't matter - HQ panel can open anytime
                            self._debug_log(">>> Sending Ctrl+R now that Live Link is ready...")
                            self._send_ctrl_r(vantage)
                            time.sleep(0.5)  # Brief wait for panel to open
                            
                            # Check if Start button appeared
                            self._desktop = Desktop(backend="uia")
                            vantage = self._find_vantage_window()
                            if vantage:
                                self._dump_window_state(vantage, "After Ctrl+R (Live Link ready)")
                                start_btn = self._find_start_button(vantage)
                                if start_btn:
                                    self._log(f"HQ panel opened! ({elapsed:.1f}s total)")
                                    self._debug_log(f">>> PHASE 2 COMPLETE: Panel opened at {elapsed:.2f}s")
                                    state['scene_ready'] = True
                                    state['panel_open'] = True
                                    state['ctrl_r_sent'] = True
                                    scene_ready = True
                                    break
                                else:
                                    # Panel didn't open - try again
                                    self._debug_log(">>> Start button not found, retrying Ctrl+R...")
                                    self._send_ctrl_r(vantage)
                                    time.sleep(0.5)
                                    
                                    self._desktop = Desktop(backend="uia")
                                    vantage = self._find_vantage_window()
                                    if vantage:
                                        start_btn = self._find_start_button(vantage)
                                        if start_btn:
                                            self._log(f"HQ panel opened on retry! ({elapsed:.1f}s)")
                                            state['scene_ready'] = True
                                            state['panel_open'] = True
                                            state['ctrl_r_sent'] = True
                                            scene_ready = True
                                            break
                            
                            # Even if panel didn't open, Live Link ready means scene is loaded
                            # Continue to panel opening step
                            state['scene_ready'] = True
                            scene_ready = True
                            break
                        
                        # Log progress every 5 seconds
                        if int(phase2_elapsed) % 5 == 0 and phase2_elapsed >= 5:
                            self._log(f"Waiting for Live Link... ({elapsed:.0f}s)")
                        
                        time.sleep(0.2)  # Fast polling for Live Link
                        continue
                    
                    time.sleep(0.3)
                
                if not scene_ready and not state.get('scene_ready'):
                    elapsed = time.time() - load_start
                    self._log(f"Scene did not load within {SCENE_LOAD_TIMEOUT}s ({elapsed:.0f}s elapsed)")
                    self._debug_log(f">>> TIMEOUT: Scene loading failed after {elapsed:.1f}s")
                    buttons = self._list_all_buttons(vantage) if vantage else []
                    self._log(f"Final button state: {buttons[:15]}")
                    self._dump_window_state(vantage, "TIMEOUT - Final state")
                    self._end_debug_session()
                    if hasattr(self, '_phase2_start'):
                        delattr(self, '_phase2_start')
                    on_error(f"Scene did not fully load within {SCENE_LOAD_TIMEOUT//60} minutes. Check if Vantage is responding.")
                    return
                
                # Clean up phase tracking
                if hasattr(self, '_phase2_start'):
                    delattr(self, '_phase2_start')
                
                state['scene_ready'] = True
                
                # Scene is now ready - small settle time for UI stability
                time.sleep(0.5)
                
                if self.is_cancelling:
                    return
                
                # Skip to start if panel already open
                if state['panel_open']:
                    self._set_state(self.STATE_OPENING_PANEL, on_progress, "Panel already open...")
                    # Jump ahead - panel is already open
                else:
                    # ============================================================
                    # STATE: OPENING_PANEL - Send Ctrl+R, wait for Start button
                    # ============================================================
                    self._set_state(self.STATE_OPENING_PANEL, on_progress, "Opening HQ panel...")
                    
                    # Send Ctrl+R (first attempt)
                    self._send_ctrl_r(vantage)
                    state['ctrl_r_sent'] = True
                    self._log("Sent Ctrl+R")
                    
                    # Wait a moment for panel to appear, then dump all buttons for diagnostics
                    time.sleep(2.0)
                    self._desktop = Desktop(backend="uia")
                    vantage = self._find_vantage_window()
                    if vantage:
                        buttons = self._list_all_buttons(vantage)
                        self._log(f"Buttons visible after Ctrl+R: {buttons[:20]}")
                    
                    # Wait for Start button to appear
                    self._log("Searching for Start button...")
                    
                    poll_start = time.time()
                    first_attempt_time = 15  # Wait 15 seconds before retry
                    max_wait = 30  # Total maximum wait
                    retry_done = False
                    last_button_dump = 0
                    
                    while time.time() - poll_start < max_wait:
                        if self.is_cancelling:
                            return
                        
                        # Refresh and search
                        self._desktop = Desktop(backend="uia")
                        vantage = self._find_vantage_window()
                        if vantage:
                            self._vantage_window = vantage
                            start_btn = self._find_start_button(vantage)
                            
                            if start_btn:
                                elapsed = time.time() - poll_start
                                self._log(f"Start button found! ({elapsed:.1f}s)")
                                state['panel_open'] = True
                                break
                        
                        elapsed = time.time() - poll_start
                        
                        # Dump buttons every 5 seconds for diagnostics
                        if int(elapsed) >= last_button_dump + 5:
                            last_button_dump = int(elapsed)
                            if vantage:
                                buttons = self._list_all_buttons(vantage)
                                self._log(f"Buttons at {elapsed:.0f}s: {buttons[:15]}")
                        
                        # ONE retry allowed at 15 seconds if panel didn't open
                        if elapsed >= first_attempt_time and not retry_done:
                            retry_done = True
                            self._log("Panel not visible - sending Ctrl+R again (one retry)")
                            if vantage:
                                self._send_ctrl_r(vantage)
                                time.sleep(1.0)
                                buttons = self._list_all_buttons(vantage)
                                self._log(f"Buttons after retry Ctrl+R: {buttons[:15]}")
                        
                        time.sleep(0.5)
                    
                    if not state['panel_open']:
                        # Debug info
                        buttons = self._list_all_buttons(vantage) if vantage else []
                        self._log(f"FAILED - Final button list: {buttons}")
                        on_error("Start button not found. Check log for available buttons.")
                        return
                
                # ============================================================
                # Apply custom frame range and output path (if configured)
                # INI settings (resolution, samples, denoiser) were already applied before launch
                # Frame range and output path require UI automation
                # ============================================================
                use_custom_settings = job.engine_settings.get('use_custom_settings', False)
                
                if use_custom_settings:
                    self._log("Applying custom settings via UI...")
                    
                    # Refresh window reference
                    self._desktop = Desktop(backend="uia")
                    vantage = self._find_vantage_window()
                    
                    if vantage:
                        # Set output path (folder + filename prefix)
                        if job.output_folder:
                            self._log(f"Setting output path: {job.output_folder}/{job.output_name}")
                            path_success = self._set_output_path(vantage, job.output_folder, job.output_name, job.output_format)
                            if not path_success:
                                self._log("Warning: Could not set output path via UI - check manually")
                        
                        # Set frame range if animation or custom range specified
                        if job.is_animation or job.frame_end > job.frame_start:
                            self._log(f"Setting frame range: {job.frame_start} - {job.frame_end}")
                            frame_success = self._set_frame_range(vantage, job.frame_start, job.frame_end)
                            if not frame_success:
                                self._log("Warning: Could not set frame range via UI")
                        
                        # Small delay to let UI settle after changes
                        time.sleep(0.3)
                    else:
                        self._log("Warning: Lost Vantage window while applying settings")
                else:
                    # Log frame range info when using existing settings
                    if job.is_animation or job.frame_end > job.frame_start:
                        self._log(f"Frame range: {job.frame_start} - {job.frame_end} (using Vantage panel settings)")
                
                # Find Start button for clicking
                start_btn = self._find_start_button(vantage)
                if not start_btn:
                    # One more search attempt
                    self._desktop = Desktop(backend="uia")
                    vantage = self._find_vantage_window()
                    if vantage:
                        start_btn = self._find_start_button(vantage)
                
                if not start_btn:
                    on_error("Start button not found after panel opened")
                    return
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STATE: CLICKING_START - Click the Start button
                # ============================================================
                self._set_state(self.STATE_CLICKING_START, on_progress, "Starting render...")
                
                try:
                    start_btn.click_input()
                    state['start_clicked'] = True
                    self._log("Clicked Start button")
                except Exception as e:
                    self._log(f"click_input failed: {e}, trying invoke()")
                    try:
                        start_btn.invoke()
                        state['start_clicked'] = True
                        self._log("Invoked Start button")
                    except Exception as e2:
                        on_error(f"Failed to click Start button: {e2}")
                        return
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STATE: RENDERING - Monitor progress
                # ============================================================
                self._set_state(self.STATE_RENDERING, on_progress, "Rendering...")
                state['render_started'] = True
                
                self._monitor_render(job, on_progress, on_complete, on_error)
                
            except Exception as e:
                if not self.is_cancelling:
                    self._log(f"Error: {e}")
                    import traceback
                    self._log(traceback.format_exc())
                    on_error(str(e))
        
        threading.Thread(target=render_thread, daemon=True).start()
    
    def _monitor_render(self, job, on_progress, on_complete, on_error):
        """Monitor render progress until completion."""
        from pywinauto import Desktop
        
        self._log("Step 5: Monitoring render progress...")
        
        # Don't reset progress if resuming - keep existing progress
        if job.progress == 0:
            on_progress(0, "Render starting...")
        
        render_start = time.time()
        last_progress = -1
        progress_window_seen = False
        no_window_count = 0
        last_log_time = time.time()
        click_retry_count = 0
        last_click_retry = time.time()
        
        # Track highest values seen - never go backwards
        highest_frame_seen = job.current_frame if job.current_frame > 0 else 0
        highest_progress_seen = job.progress if job.progress > 0 else 0
        
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
                    
                    # CRITICAL: Only update if we're making FORWARD progress
                    # Never let frame count or progress go backwards
                    if current_frame > highest_frame_seen:
                        highest_frame_seen = current_frame
                        job.current_frame = current_frame
                        job.rendering_frame = current_frame
                    
                    if total_pct > highest_progress_seen:
                        highest_progress_seen = total_pct
                    
                    # Always use highest values for display
                    display_frame = highest_frame_seen
                    display_pct = min(highest_progress_seen, 99)
                    
                    progress_changed = (display_pct != last_progress or display_frame != job.current_frame)
                    time_to_log = (time.time() - last_log_time) > 10
                    
                    if progress_changed or time_to_log:
                        last_progress = display_pct
                        last_log_time = time.time()
                        job.progress = display_pct
                        job.current_frame = display_frame
                        job.rendering_frame = display_frame
                        
                        if total_frames > 1:
                            job.frame_end = total_frames
                        
                        if frame_pct > 0:
                            job.current_sample = frame_pct
                            job.total_samples = 100
                        
                        status = "Rendering"
                        # CRITICAL: Pass frame number, not percentage!
                        # app.py on_progress expects (frame, msg) not (pct, msg)
                        on_progress(display_frame, status)
                        
                        # Log gets full details
                        if display_frame > 0 and total_frames > 1:
                            log_msg = f"Frame {display_frame}/{total_frames} ({display_pct}%)"
                        else:
                            log_msg = f"Rendering... {display_pct}%"
                        if elapsed_str:
                            log_msg += f" - Elapsed: {elapsed_str}"
                        if remaining_str:
                            log_msg += f" - Remaining: {remaining_str}"
                        self._log(log_msg)
                    
                    # Check completion - use highest frame seen
                    if highest_frame_seen >= total_frames and total_frames > 1:
                        self._log("All frames complete!")
                        self._debug_log(">>> RENDER COMPLETE: All frames finished")
                        self._end_debug_session()
                        job.progress = 100
                        self._close_vantage()
                        on_complete()
                        return
                    
                    if highest_progress_seen >= 100:
                        self._log("Render complete!")
                        self._debug_log(">>> RENDER COMPLETE: 100% reached")
                        self._end_debug_session()
                        job.progress = 100
                        self._close_vantage()
                        on_complete()
                        return
            
            elif progress_window_seen:
                no_window_count += 1
                if no_window_count >= 5:
                    self._log("Progress window closed - render complete!")
                    self._debug_log(">>> RENDER COMPLETE: Progress window closed")
                    self._end_debug_session()
                    job.progress = 100
                    self._close_vantage()
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
            
            # NO TIMEOUT - renders can take days for large jobs
            # Vantage handles its own completion/error states
            
            time.sleep(0.3)
        
        self._log("Render cancelled by user")
    
    def pause_render(self):
        """Pause the current render by clicking Pause in Vantage. Fast and non-blocking."""
        import threading
        
        def do_pause():
            self._log("Pausing render...")
            self.is_cancelling = True
            
            try:
                from pywinauto import Desktop
                self._desktop = Desktop(backend="uia")
                
                progress_win = self._find_progress_window()
                if progress_win:
                    # Quick search for Pause button by automation ID (fastest)
                    pause_btn = None
                    for btn in progress_win.descendants(control_type="Button"):
                        try:
                            auto_id = (btn.element_info.automation_id or "").lower()
                            name = (btn.element_info.name or "").lower()
                            if "pause" in name or "secondary" in auto_id:
                                pause_btn = btn
                                break
                        except:
                            pass
                    
                    if pause_btn:
                        try:
                            pause_btn.click_input()
                            self._log("Paused!")
                        except:
                            try:
                                pause_btn.invoke()
                            except:
                                pass
                    else:
                        self._log("Pause button not found")
                else:
                    self._log("Progress window not found")
            except Exception as e:
                self._log(f"Pause error: {e}")
        
        # Run in background thread to not block UI
        threading.Thread(target=do_pause, daemon=True).start()
        return True
    
    def cancel_render(self, close_vantage: bool = True):
        """Cancel/abort the current render. Fast and non-blocking."""
        import threading
        
        def do_cancel():
            self._log("Cancelling render...")
            self._debug_log(">>> CANCEL_RENDER called")
            
            try:
                from pywinauto import Desktop
                self._desktop = Desktop(backend="uia")
                
                progress_win = self._find_progress_window()
                if progress_win:
                    # Quick search for Abort button
                    abort_btn = None
                    for btn in progress_win.descendants(control_type="Button"):
                        try:
                            auto_id = (btn.element_info.automation_id or "").lower()
                            name = (btn.element_info.name or "").lower()
                            if "abort" in name or "primaryred" in auto_id:
                                abort_btn = btn
                                break
                        except:
                            pass
                    
                    if abort_btn:
                        try:
                            abort_btn.click_input()
                            self._log("Aborted!")
                        except:
                            try:
                                abort_btn.invoke()
                            except:
                                pass
                
                # Close Vantage if requested
                if close_vantage:
                    self._close_vantage()
                    
            except Exception as e:
                self._log(f"Cancel error: {e}")
            
            # End debug session
            self._end_debug_session()
            
            # Cleanup
            self._vantage_window = None
            self._desktop = None
        
        # Set flag immediately
        self.is_cancelling = True
        
        # Run in background thread to not block UI
        threading.Thread(target=do_cancel, daemon=True).start()
    
    def _close_vantage(self):
        """Close the Vantage application. Fast with minimal delays."""
        try:
            from pywinauto import keyboard, Desktop
            
            if not self._desktop:
                self._desktop = Desktop(backend="uia")
            
            vantage = self._find_vantage_window()
            
            if vantage:
                self._log("Closing Vantage...")
                
                try:
                    vantage.set_focus()
                    keyboard.send_keys("%{F4}")
                    
                    # Quick check for save dialog (minimal delay)
                    time.sleep(0.05)
                    self._desktop = Desktop(backend="uia")
                    
                    for win in self._desktop.windows():
                        try:
                            title = win.window_text().lower()
                            if "save" in title:
                                for btn in win.descendants(control_type="Button"):
                                    try:
                                        name = (btn.element_info.name or "").lower()
                                        if "don" in name or "no" == name or "discard" in name:
                                            btn.click_input()
                                            self._log("Dismissed save dialog")
                                            return
                                    except:
                                        pass
                        except:
                            pass
                    
                    self._log("Vantage closed")
                except Exception as e:
                    self._log(f"Close error: {e}")
                    
        except Exception as e:
            self._log(f"Error closing Vantage: {e}")
