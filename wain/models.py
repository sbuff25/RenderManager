"""
Wain Data Models
================

Core data structures for render jobs and application settings.
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional


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

    # Network rendering fields
    assigned_to: Optional[str] = None       # worker_id that claimed this job
    claimed_at: Optional[str] = None        # ISO timestamp when claimed
    target_worker: str = ""                 # "" = any, "local" = server only, or worker_id
    priority: int = 0                       # higher = rendered first
    created_at: Optional[str] = None        # ISO timestamp
    updated_at: Optional[str] = None        # ISO timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API/database use."""
        return {
            "id": self.id, "name": self.name, "engine_type": self.engine_type,
            "file_path": self.file_path, "output_folder": self.output_folder,
            "output_name": self.output_name, "output_format": self.output_format,
            "status": self.status, "progress": self.progress,
            "is_animation": self.is_animation, "frame_start": self.frame_start,
            "frame_end": self.frame_end, "current_frame": self.current_frame,
            "rendering_frame": self.rendering_frame, "original_start": self.original_start,
            "res_width": self.res_width, "res_height": self.res_height,
            "camera": self.camera, "overwrite_existing": self.overwrite_existing,
            "engine_settings": self.engine_settings,
            "start_time": self.start_time, "end_time": self.end_time,
            "elapsed_time": self.elapsed_time, "accumulated_seconds": self.accumulated_seconds,
            "error_message": self.error_message, "status_message": self.status_message,
            "current_sample": self.current_sample, "total_samples": self.total_samples,
            "current_tile": self.current_tile, "total_tiles": self.total_tiles,
            "current_pass": self.current_pass, "current_pass_num": self.current_pass_num,
            "total_passes": self.total_passes, "pass_frame": self.pass_frame,
            "pass_total_frames": self.pass_total_frames,
            "assigned_to": self.assigned_to, "claimed_at": self.claimed_at,
            "target_worker": self.target_worker,
            "priority": self.priority, "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RenderJob":
        """Deserialize from API/database dict."""
        # Parse engine_settings from JSON string if needed
        es = data.get("engine_settings", {})
        if isinstance(es, str):
            try:
                es = json.loads(es)
            except (json.JSONDecodeError, TypeError):
                es = {}

        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            engine_type=data.get("engine_type", "blender"),
            file_path=data.get("file_path", ""),
            output_folder=data.get("output_folder", ""),
            output_name=data.get("output_name", "render_"),
            output_format=data.get("output_format", "PNG"),
            status=data.get("status", "queued"),
            progress=int(data.get("progress", 0)),
            is_animation=bool(data.get("is_animation", False)),
            frame_start=int(data.get("frame_start", 1)),
            frame_end=int(data.get("frame_end", 250)),
            current_frame=int(data.get("current_frame", 0)),
            rendering_frame=int(data.get("rendering_frame", 0)),
            original_start=int(data.get("original_start", 0)),
            res_width=int(data.get("res_width", 1920)),
            res_height=int(data.get("res_height", 1080)),
            camera=data.get("camera", "Scene Default"),
            overwrite_existing=bool(data.get("overwrite_existing", True)),
            engine_settings=es,
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            elapsed_time=data.get("elapsed_time", ""),
            accumulated_seconds=int(data.get("accumulated_seconds", 0)),
            error_message=data.get("error_message", ""),
            status_message=data.get("status_message", ""),
            current_sample=int(data.get("current_sample", 0)),
            total_samples=int(data.get("total_samples", 0)),
            current_tile=int(data.get("current_tile", 0)),
            total_tiles=int(data.get("total_tiles", 1)),
            current_pass=data.get("current_pass", ""),
            current_pass_num=int(data.get("current_pass_num", 0)),
            total_passes=int(data.get("total_passes", 1)),
            pass_frame=int(data.get("pass_frame", 0)),
            pass_total_frames=int(data.get("pass_total_frames", 0)),
            assigned_to=data.get("assigned_to"),
            claimed_at=data.get("claimed_at"),
            target_worker=data.get("target_worker", ""),
            priority=int(data.get("priority", 0)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

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
