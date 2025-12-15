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
    current_frame: int = 0      # For Marmoset: total render count; For Blender: last completed frame
    rendering_frame: int = 0    # Current frame number being rendered
    original_start: int = 0
    res_width: int = 1920
    res_height: int = 1080
    camera: str = "Scene Default"
    overwrite_existing: bool = True  # Whether to overwrite existing rendered files
    engine_settings: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    elapsed_time: str = ""
    accumulated_seconds: int = 0
    error_message: str = ""
    current_sample: int = 0
    total_samples: int = 0
    # Tile rendering support (Blender splits high-res frames into tiles)
    current_tile: int = 0           # Current tile being rendered (0-indexed from Blender)
    total_tiles: int = 1            # Total number of tiles for this frame
    # Multi-pass rendering support
    current_pass: str = ""          # Name of the pass currently rendering
    current_pass_num: int = 0       # Current pass number (1-based)
    total_passes: int = 1           # Total number of passes to render
    pass_frame: int = 0             # Frame number within the current pass
    pass_total_frames: int = 0      # Total frames for the current pass
    
    @property
    def samples_display(self) -> str:
        """
        Display frame render progress as a percentage.
        
        This is the STANDARD progress indicator for all engines.
        Shows how far through rendering the CURRENT FRAME we are.
        
        For Blender (sample-based):
            - Tiled rendering: (completed_tiles × samples + current_sample) / (total_tiles × samples)
            - Single-tile: current_sample / total_samples
            
        For Marmoset (pass-based):
            - Each frame renders N passes sequentially
            - Progress = current_pass_num / total_passes
            
        Always displays as "Frame XX%" for consistency across all engines.
        """
        # Marmoset: progress based on passes completed within current frame
        if self.engine_type == "marmoset":
            if self.current_pass_num > 0 and self.total_passes > 0:
                # Pass just started = show percentage based on passes completed
                # e.g., pass 2 of 3 just started = 1/3 = 33% (pass 1 complete)
                completed_passes = self.current_pass_num - 1
                pct = min(int((completed_passes / self.total_passes) * 100), 99)
                return f"Frame {pct}%"
            return ""
        
        # Blender: progress based on samples/tiles
        if self.current_sample > 0 and self.total_samples > 0:
            if self.total_tiles > 1:
                # Tiled rendering - calculate overall frame progress
                total_work = self.total_tiles * self.total_samples
                completed_work = (self.current_tile * self.total_samples) + self.current_sample
                pct = min(int((completed_work / total_work) * 100), 99)
            else:
                # Single tile - calculate based on samples
                pct = min(int((self.current_sample / self.total_samples) * 100), 99)
            return f"Frame {pct}%"
        return ""
    
    @property
    def pass_display(self) -> str:
        """Display current pass info."""
        if self.current_pass:
            return self.current_pass
        if self.total_passes > 1:
            return f"Rendering {self.total_passes} passes"
        return ""
    
    @property
    def display_frame(self) -> int:
        """Get the frame to display (rendering or last completed)"""
        if self.rendering_frame > 0:
            return self.rendering_frame
        return self.current_frame
    
    @property
    def frames_display(self) -> str:
        """
        Display progress information.
        
        For Marmoset multi-pass: shows "X/Y renders" (total render operations)
        For Blender animations: shows "X/Y" (frames)
        For stills: shows frame number
        """
        if self.engine_type == "marmoset":
            # For Marmoset, show render count out of total renders
            if self.total_passes > 0 and self.pass_total_frames > 0:
                total_renders = self.pass_total_frames * self.total_passes
                if total_renders > 0 and self.current_frame > 0:
                    return f"{self.current_frame}/{total_renders}"
            # Show frame progress for turntable/animation
            if self.pass_frame > 0 and self.pass_total_frames > 0:
                return f"{self.pass_frame}/{self.pass_total_frames}"
            return ""
        
        # Blender: standard frame display
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
