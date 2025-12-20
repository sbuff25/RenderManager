"""
Wain Data Models
================

Core data structures for render jobs and application settings.
"""

import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class RenderJob:
    """Represents a single render job in the queue."""
    
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
    current_frame: int = 0
    rendering_frame: int = 0
    original_start: int = 0
    res_width: int = 1920
    res_height: int = 1080
    camera: str = "Scene Default"
    overwrite_existing: bool = True
    engine_settings: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    elapsed_time: str = ""
    accumulated_seconds: int = 0
    error_message: str = ""
    status_message: str = ""  # Current activity message (e.g., "Launching Vantage...")
    current_sample: int = 0
    total_samples: int = 0
    current_tile: int = 0
    total_tiles: int = 1
    current_pass: str = ""
    current_pass_num: int = 0
    total_passes: int = 1
    pass_frame: int = 0
    pass_total_frames: int = 0
    
    @property
    def samples_display(self) -> str:
        if self.engine_type == "marmoset":
            if self.current_pass_num > 0 and self.total_passes > 0:
                completed_passes = self.current_pass_num - 1
                pct = min(int((completed_passes / self.total_passes) * 100), 99)
                return f"Frame {pct}%"
            return ""
        
        if self.engine_type == "vantage":
            if self.current_sample > 0 and self.total_samples > 0:
                pct = min(int((self.current_sample / self.total_samples) * 100), 99)
                return f"Frame {pct}%"
            return ""
        
        if self.current_sample > 0 and self.total_samples > 0:
            if self.total_tiles > 1:
                total_work = self.total_tiles * self.total_samples
                completed_work = (self.current_tile * self.total_samples) + self.current_sample
                pct = min(int((completed_work / total_work) * 100), 99)
            else:
                pct = min(int((self.current_sample / self.total_samples) * 100), 99)
            return f"Frame {pct}%"
        return ""
    
    @property
    def pass_display(self) -> str:
        if self.current_pass:
            return self.current_pass
        if self.total_passes > 1:
            return f"Rendering {self.total_passes} passes"
        return ""
    
    @property
    def display_frame(self) -> int:
        if self.rendering_frame > 0:
            return self.rendering_frame
        return self.current_frame
    
    @property
    def frames_display(self) -> str:
        if self.engine_type == "marmoset":
            if self.total_passes > 0 and self.pass_total_frames > 0:
                total_renders = self.pass_total_frames * self.total_passes
                if total_renders > 0 and self.current_frame > 0:
                    return f"{self.current_frame}/{total_renders}"
            if self.pass_frame > 0 and self.pass_total_frames > 0:
                return f"{self.pass_frame}/{self.pass_total_frames}"
            return ""
        
        if self.engine_type == "vantage":
            if self.is_animation or self.frame_end > 1:
                frame = self.rendering_frame if self.rendering_frame > 0 else self.current_frame
                if frame > 0:
                    return f"{frame}/{self.frame_end}"
                return f"1/{self.frame_end}"
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
    """Application-wide settings."""
    engine_paths: Dict[str, Dict[str, str]] = field(default_factory=dict)
    default_versions: Dict[str, str] = field(default_factory=dict)
    default_engine_type: str = "blender"
