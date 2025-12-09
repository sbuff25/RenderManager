"""
Wane Render Engine Base
=======================

Abstract base class for all render engines.
"""

import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class RenderEngine(ABC):
    """
    Abstract base class for render engines.
    
    All render engines (Blender, Marmoset, etc.) must inherit from this
    class and implement the abstract methods.
    """
    
    # Class attributes - override in subclasses
    name: str = "Unknown"
    engine_type: str = "unknown"
    file_extensions: List[str] = []
    icon: str = "help"
    color: str = "#888888"
    
    def __init__(self):
        self.installed_versions: Dict[str, str] = {}
        self.current_process: Optional[subprocess.Popen] = None
        self.is_cancelling = False
    
    @abstractmethod
    def scan_installed_versions(self):
        """Scan system for installed versions of this engine."""
        pass
    
    @abstractmethod
    def get_scene_info(self, file_path: str) -> Dict[str, Any]:
        """
        Probe a scene file and return information about it.
        
        Returns dict with keys like: cameras, active_camera, resolution_x,
        resolution_y, frame_start, frame_end, etc.
        """
        pass
    
    @abstractmethod
    def start_render(self, job, start_frame, on_progress, on_complete, on_error, on_log=None):
        """
        Start rendering a job.
        
        Args:
            job: RenderJob instance
            start_frame: Frame to start rendering from (for resume support)
            on_progress: Callback(frame, message) for progress updates
            on_complete: Callback() when render finishes successfully
            on_error: Callback(error_message) when render fails
            on_log: Optional callback(message) for log output
        """
        pass
    
    @abstractmethod
    def cancel_render(self):
        """Cancel the currently running render."""
        pass
    
    @abstractmethod
    def get_output_formats(self) -> Dict[str, str]:
        """Return dict of {display_name: internal_format} for output formats."""
        pass
    
    @abstractmethod
    def get_default_settings(self) -> Dict[str, Any]:
        """Return default engine-specific settings for new jobs."""
        pass
    
    def add_custom_path(self, path: str) -> Optional[str]:
        """
        Add a custom executable path for this engine.
        
        Returns the version string if successful, None otherwise.
        """
        return None
    
    @property
    def is_available(self) -> bool:
        """Check if this engine is available (has at least one installed version)."""
        return len(self.installed_versions) > 0
    
    @property
    def version_display(self) -> str:
        """Get display string for installed version(s)."""
        if self.installed_versions:
            newest = sorted(self.installed_versions.keys(), reverse=True)[0]
            return f"{self.name} {newest}"
        return f"{self.name} not detected"
    
    def open_file_in_app(self, file_path: str, version: str = None):
        """Open a scene file in the application (for editing)."""
        pass
    
    def get_file_dialog_filter(self) -> List[tuple]:
        """Get file dialog filter tuples for this engine's file types."""
        ext_str = " ".join(f"*{ext}" for ext in self.file_extensions)
        return [(f"{self.name} Files", ext_str)]
