"""
Wain Vantage Engine v2.9.2
==========================

Chaos Vantage render engine integration via UI automation.
Supports .vrscene files (V-Ray scene format) and .vantage config files.

Features:
- Auto-launches Vantage with scene file
- Sets output path, resolution, and frame range
- Real progress monitoring from Vantage progress window
- Pause/Cancel control via Vantage UI
"""

import os
import sys
import json
import subprocess
import threading
import tempfile
import time
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
    
    # Search paths for vantage executables
    SEARCH_PATHS = [
        r"C:\Program Files\Chaos\Vantage\vantage.exe",
        r"C:\Program Files\Chaos Group\Vantage\vantage.exe",
        r"C:\Program Files\Chaos\Vantage 3\vantage.exe",
        r"C:\Program Files\Chaos\Vantage 2\vantage.exe",
    ]
    
    CONSOLE_PATHS = [
        r"C:\Program Files\Chaos\Vantage\vantage_console.exe",
        r"C:\Program Files\Chaos Group\Vantage\vantage_console.exe",
    ]
    
    OUTPUT_FORMATS = {
        "PNG": "png",
        "JPEG": "jpg",
        "EXR": "exr",
        "TGA": "tga",
    }
    
    QUALITY_PRESETS = ["Low", "Medium", "High", "Ultra", "Custom"]
    DENOISERS = ["Off", "Native", "NVIDIA AI", "Intel OIDN"]
    CAMERA_TYPES = ["Perspective", "Spherical", "Cube 6x1", "Stereo Cube 6x1", "Stereo Spherical"]
    
    RENDER_ELEMENTS = [
        {"id": "beauty", "name": "Beauty", "category": "Common"},
        {"id": "diffuse", "name": "Diffuse Filter", "category": "Lighting"},
        {"id": "gi", "name": "Global Illumination", "category": "Lighting"},
        {"id": "lighting", "name": "Lighting", "category": "Lighting"},
        {"id": "reflection", "name": "Reflection", "category": "Lighting"},
        {"id": "refraction", "name": "Refraction", "category": "Lighting"},
        {"id": "specular", "name": "Specular", "category": "Lighting"},
        {"id": "normals", "name": "Bumped Normals", "category": "Geometry"},
        {"id": "z_depth", "name": "Z-Depth", "category": "Geometry"},
    ]
    
    def __init__(self):
        super().__init__()
        self._vantage_window = None
        self._desktop = None
        self._on_log = None
        self._job = None
        self.scan_installed_versions()
    
    def scan_installed_versions(self):
        """Scan for installed Chaos Vantage versions."""
        self.installed_versions = {}
        self._gui_exe_path = None
        
        # Find GUI executable
        for path in self.SEARCH_PATHS:
            if os.path.isfile(path):
                version = self._get_version_from_path(path)
                self.installed_versions[version] = path
                if not self._gui_exe_path:
                    self._gui_exe_path = path
        
        # Find console executable (for version detection)
        for path in self.CONSOLE_PATHS:
            if os.path.isfile(path):
                version = self._get_version_from_exe(path)
                if version and version not in self.installed_versions:
                    gui_path = path.replace('vantage_console.exe', 'vantage.exe')
                    if os.path.exists(gui_path):
                        self.installed_versions[version] = gui_path
    
    def _get_version_from_path(self, path: str) -> str:
        """Extract version from path or return Unknown."""
        if "Vantage 3" in path:
            return "3.x"
        elif "Vantage 2" in path:
            return "2.x"
        return "Unknown"
    
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
            
            output = result.stdout.decode('utf-8', errors='replace')
            output += result.stderr.decode('utf-8', errors='replace')
            
            version_match = re.search(r'(\d+\.\d+\.\d+)', output)
            if version_match:
                return version_match.group(1)
        except:
            pass
        return None
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """Add a custom Vantage executable path."""
        if os.path.isfile(path) and path.lower().endswith('.exe'):
            version = self._get_version_from_path(path) or "Custom"
            self.installed_versions[version] = path
            if not self._gui_exe_path:
                self._gui_exe_path = path
            return version
        return None
    
    def get_best_vantage(self) -> Optional[str]:
        """Get path to best available Vantage installation."""
        if self._gui_exe_path:
            return self._gui_exe_path
        if self.installed_versions:
            return list(self.installed_versions.values())[0]
        return None
    
    def get_output_formats(self) -> Dict[str, str]:
        return self.OUTPUT_FORMATS
    
    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "quality_preset": "High",
            "samples": 256,
            "denoiser": "NVIDIA AI",
            "render_elements": ["beauty"],
        }
    
    def get_file_dialog_filter(self) -> List[tuple]:
        return [
            ("V-Ray Scene Files", "*.vrscene"),
            ("Vantage Config Files", "*.vantage"),
        ]
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open a scene file in Vantage GUI."""
        exe_path = self.get_best_vantage()
        if exe_path and os.path.exists(file_path):
            try:
                subprocess.Popen(
                    [exe_path, file_path],
                    creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0
                )
            except Exception as e:
                print(f"[Wain] Failed to open in Vantage: {e}")
    
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """Get scene information from a .vrscene or .vantage file."""
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
        
        return default_info
    
    def _parse_vrscene(self, file_path: str, default_info: Dict) -> Dict[str, Any]:
        """Parse a .vrscene file to extract basic scene info."""
        info = default_info.copy()
        cameras = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(500000)
            
            camera_patterns = [
                r'CameraPhysical\s+(\w+)\s*\{',
                r'CameraDefault\s+(\w+)\s*\{',
                r'RenderView\s+(\w+)\s*\{',
            ]
            
            for pattern in camera_patterns:
                matches = re.findall(pattern, content)
                cameras.extend(matches)
            
            if cameras:
                info["cameras"] = list(set(cameras))
                info["active_camera"] = cameras[0]
            
            width_match = re.search(r'img_width\s*=\s*(\d+)', content)
            height_match = re.search(r'img_height\s*=\s*(\d+)', content)
            
            if width_match:
                info["resolution_x"] = int(width_match.group(1))
            if height_match:
                info["resolution_y"] = int(height_match.group(1))
            
            start_match = re.search(r'anim_start\s*=\s*(\d+)', content)
            end_match = re.search(r'anim_end\s*=\s*(\d+)', content)
            
            if start_match:
                info["frame_start"] = int(start_match.group(1))
            if end_match:
                info["frame_end"] = int(end_match.group(1))
                if info["frame_end"] > info["frame_start"]:
                    info["has_animation"] = True
                    info["total_frames"] = info["frame_end"] - info["frame_start"] + 1
            
        except Exception as e:
            print(f"[Wain] Error parsing .vrscene: {e}")
        
        return info
    
    # =========================================================================
    # UI AUTOMATION HELPERS
    # =========================================================================
    
    def _log(self, msg: str):
        """Log a message if callback is set."""
        if self._on_log:
            self._on_log(f"[Vantage] {msg}")
    
    def _find_vantage_window(self):
        """Find and return the Vantage main window."""
        from pywinauto import Desktop
        
        # Always create fresh desktop reference
        self._desktop = Desktop(backend="uia")
        
        # Try to find by class name first (most reliable)
        for win in self._desktop.windows():
            try:
                class_name = win.element_info.class_name or ""
                if "LavinaMainWindow" in class_name:
                    return win
            except:
                pass
        
        # Fallback: find by title containing "vantage"
        for win in self._desktop.windows():
            try:
                title = win.window_text().lower()
                if "vantage" in title:
                    return win
            except:
                pass
        
        return None
    
    def _find_button(self, window, name_contains: str, exact: bool = False, timeout: float = 5.0):
        """Find a button by name with timeout."""
        if window is None:
            return None
        
        import time as time_module
        start = time_module.time()
        
        try:
            # Try fast method first: child_window with timeout
            try:
                if exact:
                    btn = window.child_window(title=name_contains, control_type="Button", found_index=0)
                else:
                    btn = window.child_window(title_re=f"(?i).*{name_contains}.*", control_type="Button", found_index=0)
                btn.wait('exists', timeout=timeout)
                return btn
            except:
                pass
            
            # Fallback: iterate children only (not descendants - much faster)
            for child in window.children():
                try:
                    if time_module.time() - start > timeout:
                        return None
                    name = child.element_info.name or ""
                    ctrl_type = child.element_info.control_type
                    if ctrl_type == "Button":
                        if exact:
                            if name.lower() == name_contains.lower():
                                return child
                        else:
                            if name_contains.lower() in name.lower():
                                return child
                    # Also check grandchildren (one level deeper)
                    for grandchild in child.children():
                        try:
                            if time_module.time() - start > timeout:
                                return None
                            name = grandchild.element_info.name or ""
                            ctrl_type = grandchild.element_info.control_type
                            if ctrl_type == "Button":
                                if exact:
                                    if name.lower() == name_contains.lower():
                                        return grandchild
                                else:
                                    if name_contains.lower() in name.lower():
                                        return grandchild
                        except:
                            pass
                except:
                    pass
        except:
            pass
        return None
    
    def _find_button_fast(self, window, name_contains: str, exact: bool = False):
        """Ultra-fast button search - only checks direct children and their children."""
        if window is None:
            return None
        try:
            # Check direct children
            for child in window.children():
                try:
                    name = child.element_info.name or ""
                    ctrl_type = child.element_info.control_type
                    if ctrl_type == "Button":
                        if exact:
                            if name.lower() == name_contains.lower():
                                return child
                        else:
                            if name_contains.lower() in name.lower():
                                return child
                except:
                    pass
            
            # Check one level deeper
            for child in window.children():
                try:
                    for grandchild in child.children():
                        try:
                            name = grandchild.element_info.name or ""
                            ctrl_type = grandchild.element_info.control_type
                            if ctrl_type == "Button":
                                if exact:
                                    if name.lower() == name_contains.lower():
                                        return grandchild
                                else:
                                    if name_contains.lower() in name.lower():
                                        return grandchild
                        except:
                            pass
                except:
                    pass
            
            # Check one more level (3 deep total)
            for child in window.children():
                try:
                    for grandchild in child.children():
                        try:
                            for great in grandchild.children():
                                try:
                                    name = great.element_info.name or ""
                                    ctrl_type = great.element_info.control_type
                                    if ctrl_type == "Button":
                                        if exact:
                                            if name.lower() == name_contains.lower():
                                                return great
                                        else:
                                            if name_contains.lower() in name.lower():
                                                return great
                                except:
                                    pass
                        except:
                            pass
                except:
                    pass
        except:
            pass
        return None
    
    def _find_edits_fast(self, window):
        """Fast edit field search - only checks 3 levels deep."""
        edits = []
        if window is None:
            return edits
        try:
            # Level 1
            for child in window.children():
                try:
                    if child.element_info.control_type == "Edit":
                        edits.append(child)
                except:
                    pass
                # Level 2
                try:
                    for grandchild in child.children():
                        try:
                            if grandchild.element_info.control_type == "Edit":
                                edits.append(grandchild)
                        except:
                            pass
                        # Level 3
                        try:
                            for great in grandchild.children():
                                try:
                                    if great.element_info.control_type == "Edit":
                                        edits.append(great)
                                except:
                                    pass
                        except:
                            pass
                except:
                    pass
        except:
            pass
        return edits
    
    def _dump_all_controls(self, window, max_depth=3):
        """Dump all UI controls in a window for debugging."""
        if window is None:
            self._log("Cannot dump controls - window is None")
            return
        
        self._log("=" * 60)
        self._log("UI CONTROL DUMP")
        self._log("=" * 60)
        
        try:
            # Window info
            self._log(f"Window title: {window.window_text()}")
            self._log(f"Window class: {window.element_info.class_name}")
            self._log("")
            
            # Count by type
            control_types = {}
            for elem in window.descendants():
                try:
                    ct = elem.element_info.control_type
                    control_types[ct] = control_types.get(ct, 0) + 1
                except:
                    pass
            
            self._log("Control type counts:")
            for ct, count in sorted(control_types.items()):
                self._log(f"  {ct}: {count}")
            self._log("")
            
            # Menu items
            self._log("MENU ITEMS:")
            for elem in list(window.descendants(control_type="MenuItem"))[:20]:
                try:
                    name = elem.element_info.name or "(no name)"
                    self._log(f"  MenuItem: {name}")
                except:
                    pass
            self._log("")
            
            # Buttons
            self._log("BUTTONS:")
            for elem in list(window.descendants(control_type="Button"))[:30]:
                try:
                    name = elem.element_info.name or "(no name)"
                    auto_id = elem.element_info.automation_id or ""
                    if name.strip() or auto_id:
                        self._log(f"  Button: '{name}' (id: {auto_id})")
                except:
                    pass
            self._log("")
            
            # Edit fields
            self._log("EDIT FIELDS:")
            for elem in list(window.descendants(control_type="Edit"))[:20]:
                try:
                    name = elem.element_info.name or "(no name)"
                    auto_id = elem.element_info.automation_id or ""
                    value = ""
                    try:
                        value = elem.get_value()[:50] if hasattr(elem, 'get_value') else ""
                    except:
                        pass
                    self._log(f"  Edit: '{name}' (id: {auto_id}) value='{value}'")
                except:
                    pass
            self._log("")
            
            # Text labels
            self._log("TEXT LABELS:")
            for elem in list(window.descendants(control_type="Text"))[:30]:
                try:
                    name = elem.element_info.name or ""
                    if name.strip():
                        self._log(f"  Text: {name}")
                except:
                    pass
            self._log("")
            
            # Panes/Panels
            self._log("PANES/PANELS:")
            for elem in list(window.descendants(control_type="Pane"))[:15]:
                try:
                    name = elem.element_info.name or "(no name)"
                    auto_id = elem.element_info.automation_id or ""
                    if name.strip() or auto_id:
                        self._log(f"  Pane: '{name}' (id: {auto_id})")
                except:
                    pass
            
            self._log("=" * 60)
            
        except Exception as e:
            self._log(f"Error dumping controls: {e}")
    
    def _find_edit(self, window, name_contains: str):
        """Find an edit control by name or nearby label."""
        if window is None:
            return None
        try:
            for child in window.descendants(control_type="Edit"):
                try:
                    name = child.element_info.name or ""
                    if name_contains.lower() in name.lower():
                        return child
                except:
                    pass
        except Exception as e:
            self._log(f"Error finding edit: {e}")
        return None
    
    def _find_text(self, window, text_contains: str):
        """Find a text element containing specific text."""
        if window is None:
            return None
        try:
            for child in window.descendants(control_type="Text"):
                try:
                    name = child.element_info.name or ""
                    if text_contains.lower() in name.lower():
                        return child
                except:
                    pass
        except Exception as e:
            self._log(f"Error finding text: {e}")
        return None
    
    def _set_clipboard(self, text: str):
        """Set clipboard content using PowerShell."""
        ps_cmd = f'Set-Clipboard -Value "{text}"'
        subprocess.run(
            ['powershell', '-Command', ps_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW,
            capture_output=True
        )
        time.sleep(0.1)
    
    def _paste_to_focused(self):
        """Paste clipboard content to focused control."""
        from pywinauto import keyboard
        keyboard.send_keys("^a", pause=0.05)
        time.sleep(0.05)
        keyboard.send_keys("^v", pause=0.05)
        time.sleep(0.1)
    
    def _find_progress_window(self):
        """Find Vantage 'Rendering HQ Sequence' progress window."""
        if not self._desktop:
            from pywinauto import Desktop
            self._desktop = Desktop(backend="uia")
        
        # Look specifically for "Rendering HQ Sequence" window
        for win in self._desktop.windows():
            try:
                title = win.window_text()
                # Look for the specific rendering progress window
                if "rendering hq" in title.lower() or "rendering high quality" in title.lower():
                    return win
            except:
                pass
        
        # Fallback: any window with "rendering" in title
        for win in self._desktop.windows():
            try:
                title = win.window_text().lower()
                if "rendering" in title:
                    return win
            except:
                pass
        
        # Also check for progress dialogs within the main Vantage window
        vantage = self._find_vantage_window()
        if vantage:
            # Look for child windows that might be progress dialogs
            for child in vantage.children():
                try:
                    ctrl_type = child.element_info.control_type
                    name = child.element_info.name or ""
                    if ctrl_type == "Window" or "progress" in name.lower() or "render" in name.lower():
                        # Check if it has progress-like controls
                        progress_bars = list(child.descendants(control_type="ProgressBar"))
                        if progress_bars:
                            return child
                except:
                    pass
        
        return None
    
    def _enumerate_all_windows(self):
        """List all top-level windows for debugging."""
        if not self._desktop:
            from pywinauto import Desktop
            self._desktop = Desktop(backend="uia")
        
        self._log("Enumerating all windows:")
        for win in self._desktop.windows():
            try:
                title = win.window_text()
                class_name = win.element_info.class_name or ""
                ctrl_type = win.element_info.control_type or ""
                if title or class_name:
                    self._log(f"  Window: '{title}' class='{class_name}' type='{ctrl_type}'")
            except:
                pass
        
        return None
    
    def _get_progress_from_ui(self) -> Optional[int]:
        """Read total render progress percentage from Vantage."""
        info = self._get_detailed_progress()
        return info.get('total_progress') if info else None
    
    def _get_detailed_progress(self) -> Optional[Dict[str, Any]]:
        """Read detailed progress from Vantage progress window or main window.
        
        Returns dict with:
        - total_progress: Overall completion percentage (0-100)
        - current_frame: Current frame number being rendered
        - total_frames: Total frames to render
        - frame_progress: Progress of current frame (0-100)
        
        Vantage progress window typically shows:
        - "Frame" label with current/total (e.g., "1 / 10")
        - "Frame" progress bar or percentage
        - "Total" label with overall percentage
        """
        try:
            # Try dedicated progress window first
            window = self._find_progress_window()
            
            # If no progress window, try main Vantage window
            if not window:
                window = self._find_vantage_window()
            
            if not window:
                return None
            
            result = {
                'total_progress': None,
                'current_frame': None,
                'total_frames': None,
                'frame_progress': None,
            }
            
            # Collect all text elements with their content
            texts = []
            for child in window.descendants(control_type="Text"):
                try:
                    text = child.element_info.name or ""
                    if text.strip():
                        texts.append(text)
                except:
                    pass
            
            # Also check Static controls (sometimes progress is shown as static text)
            for child in window.descendants(control_type="Static"):
                try:
                    text = child.element_info.name or ""
                    if text.strip() and text not in texts:
                        texts.append(text)
                except:
                    pass
            
            # Look for progress text patterns anywhere in the window
            for text in texts:
                text_clean = text.strip()
                text_lower = text_clean.lower()
                
                # Pattern: "Rendering frame X of Y" or "Frame X / Y"
                frame_pattern = re.search(r'(?:frame|rendering)\s*(\d+)\s*(?:of|/)\s*(\d+)', text_lower)
                if frame_pattern:
                    result['current_frame'] = int(frame_pattern.group(1))
                    result['total_frames'] = int(frame_pattern.group(2))
                    
                    # Calculate total progress from frame count
                    if result['total_progress'] is None and result['total_frames'] > 0:
                        result['total_progress'] = int((result['current_frame'] / result['total_frames']) * 100)
                    continue
                
                # Pattern: "X / Y" for frame count (standalone)
                frame_slash = re.search(r'^(\d+)\s*/\s*(\d+)$', text_clean)
                if frame_slash:
                    result['current_frame'] = int(frame_slash.group(1))
                    result['total_frames'] = int(frame_slash.group(2))
                    continue
                
                # Pattern: "XX%" or "XX.X%"
                pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text_clean)
                if pct_match:
                    pct = int(float(pct_match.group(1)))
                    # If we see "total" nearby or it's a high number, it's likely total progress
                    if 'total' in text_lower or result['total_progress'] is None:
                        result['total_progress'] = pct
                    elif result['frame_progress'] is None:
                        result['frame_progress'] = pct
                    continue
            
            # Now do the original structured parsing
            found_frame_label = False
            found_total_label = False
            
            for i, text in enumerate(texts):
                text_lower = text.lower().strip()
                text_clean = text.strip()
                
                # Look for "Frame" section
                if text_lower == "frame" or text_lower.startswith("frame"):
                    found_frame_label = True
                    found_total_label = False
                    continue
                
                # Look for "Total" section
                if text_lower == "total" or text_lower.startswith("total"):
                    found_total_label = True
                    found_frame_label = False
                    continue
                
                # Parse frame info: "X / Y" pattern for frame count
                frame_match = re.search(r'(\d+)\s*/\s*(\d+)', text_clean)
                if frame_match and found_frame_label:
                    result['current_frame'] = int(frame_match.group(1))
                    result['total_frames'] = int(frame_match.group(2))
                    continue
                
                # Parse percentage
                pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text_clean)
                if pct_match:
                    pct = int(float(pct_match.group(1)))
                    if found_total_label:
                        result['total_progress'] = pct
                    elif found_frame_label:
                        result['frame_progress'] = pct
                    continue
                
                # Check for standalone number that could be percentage
                num_match = re.search(r'^(\d+(?:\.\d+)?)$', text_clean)
                if num_match:
                    val = float(num_match.group(1))
                    if 0 <= val <= 100:
                        if found_total_label and result['total_progress'] is None:
                            result['total_progress'] = int(val)
                        elif found_frame_label and result['frame_progress'] is None:
                            result['frame_progress'] = int(val)
            
            # Try to get progress from progress bars as fallback
            progress_bars = list(window.descendants(control_type="ProgressBar"))
            for i, pb in enumerate(progress_bars):
                try:
                    value = pb.get_value()
                    if value is not None:
                        pct = int(float(value))
                        # First progress bar is usually frame, second is total
                        if i == 0 and result['frame_progress'] is None:
                            result['frame_progress'] = pct
                        elif i == 1 and result['total_progress'] is None:
                            result['total_progress'] = pct
                        elif result['total_progress'] is None:
                            result['total_progress'] = pct
                except:
                    pass
            
            # Only return if we got at least total progress
            if result['total_progress'] is not None:
                return result
                    
        except Exception as e:
            pass
        
        return None
    
    def _is_rendering_window_open(self) -> bool:
        """Check if the Rendering HQ Sequence window is still open."""
        window = self._find_progress_window()
        return window is not None
    
    def _is_render_complete(self) -> bool:
        """Check if render is complete.
        
        Render is complete when:
        1. Progress reaches 100%
        2. The Rendering HQ Sequence window closes
        3. Output file exists and is stable
        """
        # Check if progress window is still open
        progress_window = self._find_progress_window()
        
        # If progress window was open before but now closed, render might be done
        if not progress_window:
            # Double check by looking for the main Vantage window
            main_window = self._find_vantage_window()
            if main_window:
                # Progress window closed but Vantage still running = render finished
                return True
        
        # Check for 100% in progress window
        if progress_window:
            try:
                for child in progress_window.descendants(control_type="Text"):
                    text = child.element_info.name or ""
                    if "100" in text and "%" in text:
                        return True
                    if "complete" in text.lower() or "finished" in text.lower():
                        return True
            except:
                pass
        
        return False
    
    def _click_pause_button(self) -> bool:
        """Find and click Stop/Pause button in Vantage rendering window."""
        try:
            from pywinauto import Desktop, keyboard
            
            self._log("Looking for Stop button...")
            
            # Refresh desktop to get current windows
            self._desktop = Desktop(backend="uia")
            
            # First try the progress window (Rendering HQ Sequence)
            window = self._find_progress_window()
            if window:
                self._log("Found progress window, looking for Stop button...")
                
                # List all buttons for debugging
                try:
                    self._log("Buttons in progress window:")
                    for btn in window.descendants(control_type="Button")[:15]:
                        name = btn.element_info.name or "(no name)"
                        self._log(f"  - '{name}'")
                except:
                    pass
                
                # Try to find and click stop/pause/cancel buttons
                for btn_name in ["stop", "pause", "cancel", "abort", "close", "x"]:
                    btn = self._find_button(window, btn_name)
                    if btn:
                        try:
                            self._log(f"Found '{btn_name}' button, clicking...")
                            window.set_focus()
                            time.sleep(0.1)
                            btn.click_input()
                            self._log(f"Clicked {btn_name} button in progress window")
                            time.sleep(0.5)
                            return True
                        except Exception as e:
                            self._log(f"Error clicking {btn_name}: {e}")
                
                # Try Escape key
                try:
                    window.set_focus()
                    time.sleep(0.1)
                    keyboard.send_keys("{ESC}")
                    self._log("Sent Escape to progress window")
                    time.sleep(0.5)
                    return True
                except:
                    pass
            else:
                self._log("No separate progress window found")
            
            # Try main Vantage window - look for Stop button in HQ panel
            window = self._find_vantage_window()
            if window:
                self._log("Trying main Vantage window...")
                
                # List all buttons for debugging
                try:
                    self._log("Buttons in main window:")
                    for btn in window.descendants(control_type="Button")[:20]:
                        name = btn.element_info.name or "(no name)"
                        if name.lower() in ["stop", "pause", "cancel", "start", "abort"]:
                            self._log(f"  >>> '{name}'")
                        elif "(no name)" not in name:
                            self._log(f"  - '{name}'")
                except:
                    pass
                
                # Try button names
                for btn_name in ["stop", "pause", "cancel", "abort"]:
                    btn = self._find_button(window, btn_name)
                    if btn:
                        try:
                            self._log(f"Found '{btn_name}' button in main window")
                            window.set_focus()
                            time.sleep(0.1)
                            btn.click_input()
                            self._log(f"Clicked {btn_name} button")
                            time.sleep(0.3)
                            return True
                        except Exception as e:
                            self._log(f"Error clicking {btn_name}: {e}")
                
                # Try Escape key multiple times
                try:
                    window.set_focus()
                    time.sleep(0.1)
                    self._log("Sending Escape keys...")
                    for i in range(3):
                        keyboard.send_keys("{ESC}")
                        time.sleep(0.2)
                    self._log("Sent Escape keys to main window")
                    return True
                except:
                    pass
            
            self._log("Could not find any stop/pause button")
            
        except Exception as e:
            self._log(f"Error stopping render: {e}")
        
        return False
    
    # =========================================================================
    # MAIN RENDER METHOD
    # =========================================================================
    
    def start_render(self, job, start_frame: int, on_progress, on_complete, on_error, on_log=None):
        """
        Start rendering a job with Chaos Vantage using UI automation.
        
        1. Launch Vantage with scene file (if not running)
        2. Wait for scene to load
        3. Open High Quality Render panel
        4. Set output path, resolution, frame range
        5. Click Start
        6. Monitor progress from Vantage UI
        7. Handle pause/cancel from Wain
        """
        if not os.path.exists(job.file_path):
            on_error(f"Scene file not found: {job.file_path}")
            return
        
        self.is_cancelling = False
        self._on_log = on_log
        self._job = job
        os.makedirs(job.output_folder, exist_ok=True)
        
        # Build output path with proper Windows formatting
        # Fix: Strip trailing underscore from output_name (common pattern for sequences)
        output_name = job.output_name.rstrip('_')
        if not output_name:
            output_name = "render"
        
        # Determine extension from format
        ext_map = {"PNG": "png", "JPEG": "jpg", "EXR": "exr", "TGA": "tga"}
        ext = ext_map.get(job.output_format, "png")
        
        # Build path and normalize to Windows backslashes
        output_path = os.path.join(job.output_folder, f"{output_name}.{ext}")
        output_path = os.path.normpath(output_path)  # Normalize slashes for Windows
        
        self._log("Starting UI automation render...")
        self._log(f"Scene: {job.file_path}")
        self._log(f"Output: {output_path}")
        self._log(f"Resolution: {job.res_width}x{job.res_height}")
        if job.is_animation:
            self._log(f"Frames: {job.frame_start} - {job.frame_end}")
        
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
                self._log("Checking if Vantage is running...")
                vantage = self._find_vantage_window()
                
                if not vantage:
                    self._log("Vantage not running, launching...")
                    
                    vantage_exe = self.get_best_vantage()
                    if not vantage_exe:
                        on_error("Could not find Vantage executable")
                        return
                    
                    self._log(f"Launching: {vantage_exe}")
                    self._log(f"With scene: {job.file_path}")
                    
                    subprocess.Popen(
                        [vantage_exe, job.file_path],
                        creationflags=subprocess.DETACHED_PROCESS
                    )
                    
                    # Wait for Vantage window
                    self._log("Waiting for Vantage to start...")
                    wait_start = time.time()
                    max_wait = 120
                    
                    while time.time() - wait_start < max_wait:
                        if self.is_cancelling:
                            return
                        
                        self._desktop = Desktop(backend="uia")
                        vantage = self._find_vantage_window()
                        
                        if vantage:
                            self._log("Vantage window detected!")
                            break
                        
                        time.sleep(1.0)
                        elapsed = int(time.time() - wait_start)
                        if elapsed % 15 == 0:
                            self._log(f"Still waiting... ({elapsed}s)")
                    
                    if not vantage:
                        on_error("Vantage did not start within 2 minutes")
                        return
                    
                    # Wait for scene to load (reduced from 10s)
                    self._log("Waiting for scene to load...")
                    time.sleep(3.0)  # Brief pause for initial load
                
                self._vantage_window = vantage
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STEP 2: Open High Quality Render panel (OPTIMIZED v2.10.3)
                # ============================================================
                self._log("Opening render panel with Ctrl+R...")
                
                vantage.set_focus()
                time.sleep(0.2)
                
                # Send Ctrl+R immediately - this is the fastest reliable method
                keyboard.send_keys("^r")
                time.sleep(0.8)  # Brief wait for panel to open
                
                hq_panel_opened = False
                
                # Quick verify - only check 2 levels deep (fast)
                start_btn = self._find_button_fast(vantage, "start", exact=True)
                if start_btn:
                    self._log("Panel opened!")
                    hq_panel_opened = True
                else:
                    # One retry with slightly longer wait
                    time.sleep(0.5)
                    start_btn = self._find_button_fast(vantage, "start", exact=True)
                    if start_btn:
                        self._log("Panel opened!")
                        hq_panel_opened = True
                
                # Only try fallbacks if Ctrl+R failed completely
                if not hq_panel_opened:
                    self._log("Could not open HQ Render panel via shortcuts")
                    on_error("Could not open High Quality Render panel. Please open it manually (Ctrl+R)")
                    return
                
                # ============================================================
                # STEP 3: Set resolution (OPTIMIZED v2.10.3)
                # ============================================================
                self._log(f"Setting resolution to {job.res_width}x{job.res_height}...")
                
                # Use faster edit field search - only check children of children
                all_edits = self._find_edits_fast(vantage)
                
                # Set resolution via keyboard navigation
                width_set = False
                height_set = False
                
                for edit in all_edits:
                    try:
                        name = (edit.element_info.name or "").lower()
                        if "width" in name and not width_set:
                            edit.click_input()
                            time.sleep(0.05)
                            self._set_clipboard(str(job.res_width))
                            self._paste_to_focused()
                            keyboard.send_keys("{TAB}")
                            width_set = True
                        elif "height" in name and not height_set:
                            edit.click_input()
                            time.sleep(0.05)
                            self._set_clipboard(str(job.res_height))
                            self._paste_to_focused()
                            keyboard.send_keys("{TAB}")
                            height_set = True
                    except:
                        pass
                
                time.sleep(0.1)
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STEP 4: Set output path (OPTIMIZED v2.10.3)
                # ============================================================
                self._log("Setting output path...")
                
                browse_btn = self._find_button_fast(vantage, "browse")
                if browse_btn:
                    browse_btn.click_input()
                    time.sleep(0.5)
                    
                    # Type path in file dialog
                    self._set_clipboard(output_path)
                    self._paste_to_focused()
                    time.sleep(0.1)
                    
                    keyboard.send_keys("{ENTER}")
                    time.sleep(0.3)
                    self._log(f"Output path set: {output_path}")
                else:
                    self._log("WARNING: Could not find Browse button")
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STEP 5: Set frame range (if animation)
                # ============================================================
                if job.is_animation:
                    self._log(f"Setting frame range: {job.frame_start} - {job.frame_end}")
                    
                    # Look for frame start/end fields
                    for edit in all_edits:
                        try:
                            name = (edit.element_info.name or "").lower()
                            if "start" in name and "frame" in name:
                                edit.click_input()
                                time.sleep(0.05)
                                self._set_clipboard(str(job.frame_start))
                                self._paste_to_focused()
                            elif "end" in name and "frame" in name:
                                edit.click_input()
                                time.sleep(0.05)
                                self._set_clipboard(str(job.frame_end))
                                self._paste_to_focused()
                                self._log(f"Set end frame: {job.frame_end}")
                        except:
                            pass
                    
                    time.sleep(0.3)
                
                if self.is_cancelling:
                    return
                
                # ============================================================
                # STEP 6: Click Start button (OPTIMIZED v2.10.3)
                # ============================================================
                self._log("Clicking Start button...")
                
                # Quick refresh and find Start button (we already know it exists from Step 2)
                vantage.set_focus()
                time.sleep(0.1)
                
                # Use fast button finder
                start_btn = self._find_button_fast(vantage, "start", exact=True)
                if not start_btn:
                    # One retry after brief wait
                    time.sleep(0.3)
                    start_btn = self._find_button_fast(vantage, "start", exact=True)
                
                if start_btn:
                    start_btn.click_input()
                    time.sleep(0.5)
                else:
                    on_error("Could not find Start button")
                    return
                
                self._log("Render started! Monitoring progress...")
                
                # ============================================================
                # STEP 7: Monitor progress
                # ============================================================
                job.progress = 0
                on_progress(0, "Render starting...")
                
                render_start = time.time()
                last_progress = -1
                progress_window_seen = False
                no_window_count = 0
                
                # Track last file count for file-based progress
                last_file_count = 0
                output_dir = job.output_folder
                output_ext = job.output_format.lower()
                if output_ext == "jpeg":
                    output_ext = "jpg"
                elif output_ext == "openexr":
                    output_ext = "exr"
                
                # Quick check for progress window (5 seconds max)
                self._log("Looking for progress window...")
                for i in range(10):
                    if self.is_cancelling:
                        return
                    
                    self._desktop = Desktop(backend="uia")
                    progress_win = self._find_progress_window()
                    if progress_win:
                        progress_window_seen = True
                        self._log("Found progress window!")
                        break
                    time.sleep(0.5)
                
                if not progress_window_seen:
                    self._log("No dedicated progress window found - will monitor files and main window")
                    # Enumerate windows to see what's available
                    self._enumerate_all_windows()
                
                last_log_time = time.time()
                
                # Main monitoring loop
                while not self.is_cancelling:
                    elapsed = time.time() - render_start
                    
                    # Refresh desktop for fresh window scan
                    self._desktop = Desktop(backend="uia")
                    
                    # Check if progress window exists
                    progress_win = self._find_progress_window()
                    
                    if progress_window_seen and not progress_win:
                        # Progress window was open but now closed = render complete
                        no_window_count += 1
                        if no_window_count >= 3:  # Confirm it's really gone
                            self._log("Progress window closed - render complete!")
                            job.progress = 100
                            on_complete()
                            return
                    else:
                        no_window_count = 0
                    
                    progress_updated = False
                    
                    # Try to read progress from UI (progress window or main window)
                    # _get_detailed_progress() checks both
                    progress_info = self._get_detailed_progress()
                    
                    if progress_win:
                        progress_window_seen = True
                    
                    if progress_info:
                            total_pct = progress_info.get('total_progress')
                            frame_pct = progress_info.get('frame_progress')
                            current_frame = progress_info.get('current_frame')
                            total_frames = progress_info.get('total_frames')
                            
                            # Update job with frame info for UI display
                            if current_frame is not None:
                                job.rendering_frame = current_frame
                                job.current_frame = current_frame
                            if total_frames is not None:
                                job.frame_end = total_frames
                                job.pass_total_frames = total_frames
                            
                            # Set frame progress for samples_display property
                            if frame_pct is not None:
                                job.current_sample = frame_pct
                                job.total_samples = 100
                            
                            # Update overall progress
                            if total_pct is not None:
                                progress_updated = True
                                if total_pct != last_progress:
                                    last_progress = total_pct
                                    job.progress = min(total_pct, 99)
                                    
                                    status = f"Rendering... {total_pct}%"
                                    if current_frame and total_frames:
                                        status = f"Frame {current_frame}/{total_frames} - {total_pct}%"
                                    
                                    on_progress(total_pct, status)
                                    
                                    log_msg = f"Progress: {total_pct}%"
                                    if current_frame:
                                        log_msg += f" (Frame {current_frame}"
                                        if total_frames:
                                            log_msg += f"/{total_frames}"
                                        if frame_pct is not None:
                                            log_msg += f" @ {frame_pct}%"
                                        log_msg += ")"
                                    self._log(log_msg)
                                
                                if total_pct >= 100:
                                    self._log("Progress reached 100%!")
                                    job.progress = 100
                                    on_complete()
                                    return
                    
                    # Fallback: File-based progress monitoring
                    if not progress_updated:
                        try:
                            if job.is_animation:
                                # Animation: Count rendered files
                                if os.path.exists(output_dir):
                                    files = [f for f in os.listdir(output_dir) 
                                            if f.lower().endswith(f".{output_ext}")]
                                    file_count = len(files)
                                    
                                    if file_count > last_file_count:
                                        last_file_count = file_count
                                        total_frames = job.frame_end - job.frame_start + 1
                                        pct = min(int((file_count / total_frames) * 100), 99)
                                        
                                        if pct != last_progress:
                                            last_progress = pct
                                            job.progress = pct
                                            job.current_frame = file_count
                                            job.rendering_frame = file_count
                                            
                                            status = f"Rendered {file_count}/{total_frames} files"
                                            on_progress(pct, status)
                                            self._log(f"File-based progress: {file_count}/{total_frames} ({pct}%)")
                                        
                                        # Check completion
                                        if file_count >= total_frames:
                                            self._log("All frames rendered!")
                                            job.progress = 100
                                            on_complete()
                                            return
                            else:
                                # Still image: Check if output file exists
                                output_file = os.path.join(output_dir, f"render.{output_ext}")
                                # Also check without extension appended
                                if job.output_name:
                                    output_file2 = os.path.join(output_dir, f"{job.output_name}")
                                    if not output_file2.endswith(f".{output_ext}"):
                                        output_file2 += f".{output_ext}"
                                else:
                                    output_file2 = output_file
                                
                                for check_file in [output_file, output_file2]:
                                    if os.path.exists(check_file):
                                        # File exists - check if it was recently modified
                                        mtime = os.path.getmtime(check_file)
                                        if mtime > render_start:
                                            # File was created/modified after render started
                                            file_size = os.path.getsize(check_file)
                                            if file_size > 1000:  # At least 1KB - probably complete
                                                self._log(f"Output file detected: {check_file} ({file_size} bytes)")
                                                job.progress = 100
                                                on_complete()
                                                return
                        except Exception as e:
                            pass
                    
                    # Periodic status log (every 10 seconds)
                    if time.time() - last_log_time > 10:
                        last_log_time = time.time()
                        self._log(f"Monitoring... elapsed: {int(elapsed)}s, progress: {job.progress}%")
                        if not progress_win and not progress_window_seen:
                            self._log("(No progress window - using file monitoring)")
                    
                    # Timeout after 2 hours
                    if elapsed > 7200:
                        self._log("Render timed out after 2 hours")
                        on_error("Render timed out")
                        return
                    
                    time.sleep(1.0)  # Check every second
                
                # If we get here, render was cancelled/paused
                self._log("Render monitoring stopped")
                
            except Exception as e:
                if not self.is_cancelling:
                    on_error(str(e))
        
        threading.Thread(target=render_thread, daemon=True).start()
    
    def cancel_render(self):
        """Cancel/pause the current render by clicking Stop in Vantage."""
        self._log("Stopping render...")
        self.is_cancelling = True
        
        # Try to click Stop/Pause button in Vantage
        if not self._click_pause_button():
            self._log("Could not find Stop button - render may continue in Vantage")
        
        # Clean up
        self._cleanup()
    
    def _cleanup(self):
        """Clean up resources."""
        self._vantage_window = None
        self._desktop = None
        self._on_log = None
        self._job = None
    
    def _stop_progress_monitor(self):
        """Stop progress monitoring."""
        self.is_cancelling = True
    
    def test_command_line_options(self, on_log=None) -> Dict[str, Any]:
        """Test which command-line options are available."""
        return {"note": "Vantage 3.x uses UI automation, not command-line"}
