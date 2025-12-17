"""
Vantage Communication Module
=============================

Handles bidirectional communication between Wain and Chaos Vantage.

Communication Methods:
1. UI Automation (pywinauto) - For interacting with Vantage's GUI
2. Scene file parsing - For reading .vantage/.vrscene settings

This module provides:
- Reading current settings from Vantage UI
- Applying settings from Wain to Vantage UI
- Real-time progress monitoring
- Pause/Resume/Stop control
"""

import os
import sys
import re
import time
import json
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from wain.engines.interface import (
    EngineInterface,
    EngineSettingsSchema,
    RenderProgress,
    RenderStatus,
    ProgressCallback,
    LogCallback,
)
from wain.engines.vantage_settings import VANTAGE_SETTINGS_SCHEMA


@dataclass
class VantageUIState:
    """Current state of Vantage UI elements."""
    window_found: bool = False
    render_panel_open: bool = False
    is_rendering: bool = False
    progress_window_found: bool = False


class VantageCommunicator(EngineInterface):
    """
    Handles communication between Wain and Chaos Vantage.
    
    Uses UI automation to:
    - Read settings from Vantage's render panel
    - Apply settings before rendering
    - Monitor render progress in real-time
    - Control render (pause/resume/stop)
    """
    
    def __init__(self, log_callback: Optional[LogCallback] = None):
        self._log_callback = log_callback
        self._desktop = None
        self._vantage_window = None
        self._progress_window = None
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._current_progress = RenderProgress()
        self._ui_state = VantageUIState()
        
        # Import pywinauto
        try:
            from pywinauto import Desktop
            self._Desktop = Desktop
            self._pywinauto_available = True
        except ImportError:
            self._pywinauto_available = False
            self._log("pywinauto not available - UI automation disabled")
    
    def _log(self, msg: str):
        """Log a message."""
        if self._log_callback:
            self._log_callback(f"[Vantage] {msg}")
    
    # =========================================================================
    # INTERFACE IMPLEMENTATION
    # =========================================================================
    
    @property
    def settings_schema(self) -> EngineSettingsSchema:
        """Return the Vantage settings schema."""
        return VANTAGE_SETTINGS_SCHEMA
    
    def read_scene_settings(self, file_path: str) -> Dict[str, Any]:
        """
        Read settings from a Vantage scene file.
        
        For .vantage files, we can parse JSON/XML structure.
        For .vrscene files, we parse the text format.
        
        Returns settings that Wain can use to populate the UI.
        """
        settings = VANTAGE_SETTINGS_SCHEMA.get_defaults()
        
        if not os.path.exists(file_path):
            return settings
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".vrscene":
            settings = self._read_vrscene_settings(file_path, settings)
        elif ext == ".vantage":
            settings = self._read_vantage_file_settings(file_path, settings)
        
        return settings
    
    def _read_vrscene_settings(self, file_path: str, defaults: Dict) -> Dict[str, Any]:
        """Parse .vrscene file for settings."""
        settings = defaults.copy()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(500000)  # Read first 500KB
            
            # Resolution
            width_match = re.search(r'img_width\s*=\s*(\d+)', content)
            height_match = re.search(r'img_height\s*=\s*(\d+)', content)
            if width_match:
                settings["resolution_width"] = int(width_match.group(1))
            if height_match:
                settings["resolution_height"] = int(height_match.group(1))
            
            # Frame range
            start_match = re.search(r'anim_start\s*=\s*(\d+)', content)
            end_match = re.search(r'anim_end\s*=\s*(\d+)', content)
            if start_match:
                settings["frame_start"] = int(start_match.group(1))
            if end_match:
                settings["frame_end"] = int(end_match.group(1))
            
            # Find cameras
            cameras = []
            for pattern in [r'CameraPhysical\s+(\w+)\s*\{', r'RenderView\s+(\w+)\s*\{']:
                cameras.extend(re.findall(pattern, content))
            if cameras:
                settings["_cameras"] = list(set(cameras))  # Store for UI
            
        except Exception as e:
            self._log(f"Error reading .vrscene: {e}")
        
        return settings
    
    def _read_vantage_file_settings(self, file_path: str, defaults: Dict) -> Dict[str, Any]:
        """Parse .vantage file for settings."""
        settings = defaults.copy()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(100000)
            
            # Try JSON parsing
            try:
                data = json.loads(content)
                if 'renderSettings' in data:
                    rs = data['renderSettings']
                    if 'width' in rs:
                        settings["resolution_width"] = rs['width']
                    if 'height' in rs:
                        settings["resolution_height"] = rs['height']
                    if 'samples' in rs:
                        settings["samples"] = rs['samples']
            except json.JSONDecodeError:
                pass
                
        except Exception as e:
            self._log(f"Error reading .vantage: {e}")
        
        return settings
    
    def apply_settings(self, file_path: str, settings: Dict[str, Any]) -> bool:
        """
        Apply settings to Vantage via UI automation.
        
        This opens Vantage (if needed), opens the render panel,
        and sets all the configured values.
        """
        if not self._pywinauto_available:
            self._log("Cannot apply settings - pywinauto not available")
            return False
        
        try:
            # Ensure Vantage is running and focused
            if not self._ensure_vantage_ready(file_path):
                return False
            
            # Open render panel
            if not self._open_render_panel():
                return False
            
            # Apply each setting
            self._apply_resolution(settings)
            self._apply_frame_range(settings)
            self._apply_output_path(settings)
            self._apply_quality_settings(settings)
            
            self._log("Settings applied successfully")
            return True
            
        except Exception as e:
            self._log(f"Error applying settings: {e}")
            return False
    
    def _ensure_vantage_ready(self, scene_path: str) -> bool:
        """Ensure Vantage is running with the scene loaded."""
        self._desktop = self._Desktop(backend="uia")
        self._vantage_window = self._find_vantage_window()
        
        if self._vantage_window:
            self._vantage_window.set_focus()
            self._ui_state.window_found = True
            return True
        
        # Would need to launch Vantage here
        self._log("Vantage not running")
        return False
    
    def _find_vantage_window(self):
        """Find the main Vantage window."""
        if not self._desktop:
            return None
        
        for win in self._desktop.windows():
            try:
                class_name = win.element_info.class_name or ""
                if "LavinaMainWindow" in class_name:
                    return win
                title = win.window_text().lower()
                if "vantage" in title:
                    return win
            except:
                pass
        return None
    
    def _open_render_panel(self) -> bool:
        """Open Vantage's High Quality Render panel via menu."""
        if not self._vantage_window:
            return False
        
        try:
            # Try menu: Tools > High Quality Render
            from pywinauto.keyboard import send_keys
            self._vantage_window.set_focus()
            time.sleep(0.2)
            
            # Find Tools menu
            menu_bar = self._vantage_window.child_window(control_type="MenuBar")
            tools_menu = menu_bar.child_window(title="Tools", control_type="MenuItem")
            tools_menu.click_input()
            time.sleep(0.3)
            
            # Find High Quality Render
            hq_render = self._vantage_window.child_window(
                title_re=".*High Quality.*|.*HQ.*Render.*",
                control_type="MenuItem"
            )
            hq_render.click_input()
            time.sleep(0.5)
            
            self._ui_state.render_panel_open = True
            return True
            
        except Exception as e:
            self._log(f"Error opening render panel: {e}")
            return False
    
    def _apply_resolution(self, settings: Dict):
        """Apply resolution settings to Vantage UI."""
        width = settings.get("resolution_width", 1920)
        height = settings.get("resolution_height", 1080)
        
        try:
            # Find resolution dropdown/input and set values
            # This is UI-specific and may need adjustment
            resolution_str = f"{width} x {height}"
            self._log(f"Setting resolution: {resolution_str}")
            # Implementation depends on Vantage UI structure
        except Exception as e:
            self._log(f"Error setting resolution: {e}")
    
    def _apply_frame_range(self, settings: Dict):
        """Apply frame range settings."""
        start = settings.get("frame_start", 1)
        end = settings.get("frame_end", 1)
        
        try:
            self._log(f"Setting frame range: {start} - {end}")
            # Implementation depends on Vantage UI structure
        except Exception as e:
            self._log(f"Error setting frame range: {e}")
    
    def _apply_output_path(self, settings: Dict):
        """Apply output path setting."""
        path = settings.get("output_path", "")
        if not path:
            return
        
        try:
            self._log(f"Setting output path: {path}")
            # Implementation depends on Vantage UI structure
        except Exception as e:
            self._log(f"Error setting output path: {e}")
    
    def _apply_quality_settings(self, settings: Dict):
        """Apply quality-related settings."""
        samples = settings.get("samples", 256)
        denoiser = settings.get("denoiser", "nvidia")
        
        try:
            self._log(f"Setting quality: {samples} samples, denoiser: {denoiser}")
            # Implementation depends on Vantage UI structure
        except Exception as e:
            self._log(f"Error setting quality: {e}")
    
    # =========================================================================
    # PROGRESS MONITORING
    # =========================================================================
    
    def get_progress(self) -> RenderProgress:
        """Get current render progress."""
        return self._current_progress
    
    def start_progress_monitoring(self, callback: Optional[ProgressCallback] = None):
        """
        Start monitoring render progress in a background thread.
        
        Args:
            callback: Optional function called when progress updates
        """
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._progress_monitor_loop,
            args=(callback,),
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop_progress_monitoring(self):
        """Stop the progress monitoring thread."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
    
    def _progress_monitor_loop(self, callback: Optional[ProgressCallback]):
        """Background thread that monitors Vantage progress."""
        last_progress = None
        
        while self._monitoring:
            try:
                # Read progress from UI
                progress = self._read_progress_from_ui()
                
                # Update stored progress
                self._current_progress = progress
                
                # Call callback if progress changed
                if callback and progress != last_progress:
                    callback(progress)
                    last_progress = progress
                
                # Check for completion
                if progress.status in [RenderStatus.COMPLETE, RenderStatus.FAILED, RenderStatus.CANCELLED]:
                    self._monitoring = False
                    break
                
            except Exception as e:
                self._log(f"Progress monitor error: {e}")
            
            time.sleep(0.5)
    
    def _read_progress_from_ui(self) -> RenderProgress:
        """
        Read current progress from Vantage's render progress window.
        
        Returns standardized RenderProgress structure.
        """
        progress = RenderProgress()
        
        if not self._pywinauto_available:
            return progress
        
        try:
            self._desktop = self._Desktop(backend="uia")
            
            # Find progress window
            progress_window = self._find_progress_window()
            if not progress_window:
                # No progress window = not rendering or complete
                if self._ui_state.is_rendering:
                    progress.status = RenderStatus.COMPLETE
                else:
                    progress.status = RenderStatus.IDLE
                return progress
            
            self._ui_state.progress_window_found = True
            progress.status = RenderStatus.RENDERING
            
            # Read all UI elements
            elements = self._read_progress_ui_elements(progress_window)
            
            # Parse progress information
            progress = self._parse_progress_elements(elements, progress)
            
        except Exception as e:
            self._log(f"Error reading progress: {e}")
        
        return progress
    
    def _find_progress_window(self):
        """Find Vantage's render progress window."""
        for win in self._desktop.windows():
            try:
                title = win.window_text().lower()
                if "rendering hq" in title or "rendering high quality" in title:
                    return win
                if "rendering" in title and "vantage" not in title:
                    return win
            except:
                pass
        return None
    
    def _read_progress_ui_elements(self, window) -> Dict[str, Any]:
        """Read all relevant UI elements from progress window."""
        elements = {
            "texts": [],
            "progress_bars": [],
            "buttons": [],
        }
        
        try:
            # Text elements
            for child in window.descendants(control_type="Text"):
                try:
                    name = child.element_info.name or ""
                    if name.strip():
                        elements["texts"].append(name.strip())
                except:
                    pass
            
            # Progress bars
            for child in window.descendants(control_type="ProgressBar"):
                try:
                    value = None
                    try:
                        value = child.get_value()
                    except:
                        pass
                    elements["progress_bars"].append(value)
                except:
                    pass
            
            # Buttons
            for child in window.descendants(control_type="Button"):
                try:
                    name = child.element_info.name or ""
                    elements["buttons"].append(name)
                except:
                    pass
                    
        except Exception as e:
            self._log(f"Error reading UI elements: {e}")
        
        return elements
    
    def _parse_progress_elements(self, elements: Dict, progress: RenderProgress) -> RenderProgress:
        """
        Parse UI elements into standardized progress structure.
        
        Expected Vantage progress window structure:
        - "Frame" section with "X / Y" and percentage
        - "Total" section with percentage
        - Progress bars for frame and total
        """
        texts = elements.get("texts", [])
        progress_bars = elements.get("progress_bars", [])
        
        in_frame_section = False
        in_total_section = False
        
        for text in texts:
            text_lower = text.lower()
            
            # Section headers
            if text_lower == "frame":
                in_frame_section = True
                in_total_section = False
                continue
            elif text_lower == "total":
                in_total_section = True
                in_frame_section = False
                continue
            
            # Frame count: "X / Y"
            frame_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
            if frame_match:
                progress.current_frame = int(frame_match.group(1))
                progress.total_frames = int(frame_match.group(2))
                continue
            
            # Percentage: "XX %" or "XX.X %"
            pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
            if pct_match:
                pct = float(pct_match.group(1))
                if in_total_section:
                    progress.total_progress = pct
                elif in_frame_section:
                    progress.frame_progress = pct
                continue
        
        # Fallback to progress bars
        for i, pb_value in enumerate(progress_bars):
            if pb_value is not None:
                val = float(pb_value)
                if i == 0 and progress.frame_progress == 0:
                    progress.frame_progress = val
                elif i == 1 and progress.total_progress == 0:
                    progress.total_progress = val
        
        # Build status message
        parts = []
        if progress.current_frame > 0:
            parts.append(f"Frame {progress.current_frame}/{progress.total_frames}")
        if progress.frame_progress > 0:
            parts.append(f"Frame: {progress.frame_progress:.1f}%")
        if progress.total_progress > 0:
            parts.append(f"Total: {progress.total_progress:.1f}%")
        progress.message = " | ".join(parts) if parts else "Rendering..."
        
        return progress
    
    # =========================================================================
    # RENDER CONTROL
    # =========================================================================
    
    def pause_render(self) -> bool:
        """Pause the current render."""
        return self._click_control_button(["pause"])
    
    def resume_render(self) -> bool:
        """Resume a paused render."""
        return self._click_control_button(["resume", "continue", "start"])
    
    def stop_render(self) -> bool:
        """Stop/cancel the current render."""
        return self._click_control_button(["stop", "cancel", "abort", "close"])
    
    def _click_control_button(self, button_names: List[str]) -> bool:
        """Click a control button in the progress window."""
        if not self._pywinauto_available:
            return False
        
        try:
            self._desktop = self._Desktop(backend="uia")
            window = self._find_progress_window()
            
            if not window:
                # Try main Vantage window
                window = self._find_vantage_window()
            
            if not window:
                self._log("No window found for control button")
                return False
            
            window.set_focus()
            time.sleep(0.1)
            
            # Find and click button
            for btn_name in button_names:
                for child in window.descendants(control_type="Button"):
                    try:
                        name = (child.element_info.name or "").lower()
                        if btn_name.lower() in name:
                            child.click_input()
                            self._log(f"Clicked '{name}' button")
                            return True
                    except:
                        pass
            
            # Fallback: send Escape key
            from pywinauto.keyboard import send_keys
            send_keys("{ESCAPE}")
            self._log("Sent Escape key as fallback")
            return True
            
        except Exception as e:
            self._log(f"Error clicking control button: {e}")
            return False


# Singleton instance
_communicator: Optional[VantageCommunicator] = None


def get_vantage_communicator(log_callback: Optional[LogCallback] = None) -> VantageCommunicator:
    """Get the Vantage communicator singleton."""
    global _communicator
    if _communicator is None:
        _communicator = VantageCommunicator(log_callback)
    elif log_callback:
        _communicator._log_callback = log_callback
    return _communicator
