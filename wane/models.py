"""
Wane Data Models
================

Core data structures for render jobs and application settings.
"""

import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class RenderJob:
    """
    Represents a single render job in the queue.
    
    Supports both single-frame and animation renders, with pause/resume
    capability and multi-pass rendering for engines like Marmoset.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    engine_type: str = "blender"
    file_path: str = ""
    output_folder: str = ""
    output_name: str = "render_"
    output_format: str = "PNG"
    status: str = "queued"
    progress: int = 0
    is_animation: bool = False
    frame_start: int = 1
    frame_end: int = 250
    current_frame: int = 0      # Last COMPLETED frame (used for resume)
    rendering_frame: int = 0    # Frame currently being rendered (for display)
    original_start: int = 0
    res_width: int = 1920
    res_height: int = 1080
    camera: str = "Scene Default"
    engine_settings: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    elapsed_time: str = ""
    accumulated_seconds: int = 0
    error_message: str = ""
    current_sample: int = 0
    total_samples: int = 0
    # Multi-pass rendering support (for engines like Marmoset that render passes separately)
    current_pass: str = ""          # Name of the pass currently rendering
    current_pass_num: int = 0       # Current pass number (1-based)
    total_passes: int = 1           # Total number of passes to render
    pass_frame: int = 0             # Frame number within the current pass
    pass_total_frames: int = 0      # Total frames for the current pass
    
    @property
    def samples_display(self) -> str:
        """Display sample progress for single frame renders"""
        if self.current_sample > 0 and self.total_samples > 0:
            return f"{self.current_sample}/{self.total_samples}"
        return ""
    
    @property
    def pass_display(self) -> str:
        """Display current pass info."""
        if self.current_pass == "Organizing":
            return "Organizing files..."
        if self.total_passes > 1:
            if self.current_pass:
                return f"{self.current_pass}"
            return f"Rendering {self.total_passes} passes"
        elif self.current_pass:
            return self.current_pass
        return ""
    
    @property
    def pass_frames_display(self) -> str:
        """Display frame progress within current pass"""
        if self.pass_total_frames > 0:
            return f"{self.pass_frame}/{self.pass_total_frames}"
        return ""
    
    @property
    def display_frame(self) -> int:
        """Get the frame to display (rendering or last completed)"""
        if self.rendering_frame > 0:
            return self.rendering_frame
        return self.current_frame
    
    @property
    def frames_display(self) -> str:
        """Display frames - for multi-pass simultaneous shows files count, otherwise frames"""
        if self.total_passes > 1 and self.engine_type == "marmoset":
            total_files = self.pass_total_frames * self.total_passes
            if total_files > 0:
                return f"{self.current_frame}/{total_files} files"
            return ""
        if self.is_animation:
            frame = self.display_frame
            if frame > 0 and frame >= self.frame_start:
                return f"{frame}/{self.frame_end}"
            return f"0/{self.frame_end}"
        return str(self.frame_start)
    
    @property 
    def resolution_display(self) -> str:
        return f"{self.res_width}x{self.res_height}"
    
    @property
    def file_name(self) -> str:
        return os.path.basename(self.file_path) if self.file_path else ""
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.engine_settings.get(key, default)


@dataclass
class AppSettings:
    """
    Application-wide settings.
    
    Stores engine paths, default versions, and user preferences.
    """
    engine_paths: Dict[str, Dict[str, str]] = field(default_factory=dict)
    default_versions: Dict[str, str] = field(default_factory=dict)
    default_engine_type: str = "blender"
