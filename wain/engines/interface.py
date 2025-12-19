"""
Wain Engine Communication Interface
====================================

Standardized interface for communication between Wain and render engines.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union


class SettingType(Enum):
    """Types of settings that can be configured."""
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CHOICE = "choice"
    MULTI_CHOICE = "multi"
    PATH = "path"
    RESOLUTION = "resolution"
    FRAME_RANGE = "frame_range"


class SettingCategory(Enum):
    """Categories for organizing settings in UI."""
    OUTPUT = "Output"
    QUALITY = "Quality"
    CAMERA = "Camera"
    ANIMATION = "Animation"
    LIGHTING = "Lighting"
    ADVANCED = "Advanced"


@dataclass
class SettingDefinition:
    """Defines a single configurable setting."""
    id: str
    name: str
    type: SettingType
    category: SettingCategory
    default: Any
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Dict]] = None
    required: bool = True
    depends_on: Optional[str] = None
    engine_key: Optional[str] = None


@dataclass 
class EngineSettingsSchema:
    """Complete settings schema for an engine."""
    engine_type: str
    engine_name: str
    version: str
    settings: List[SettingDefinition]
    
    def get_setting(self, setting_id: str) -> Optional[SettingDefinition]:
        for s in self.settings:
            if s.id == setting_id:
                return s
        return None
    
    def get_defaults(self) -> Dict[str, Any]:
        return {s.id: s.default for s in self.settings}
    
    def get_by_category(self, category: SettingCategory) -> List[SettingDefinition]:
        return [s for s in self.settings if s.category == category]
    
    def validate(self, values: Dict[str, Any]) -> List[str]:
        errors = []
        for setting in self.settings:
            value = values.get(setting.id)
            
            if setting.required and value is None:
                errors.append(f"{setting.name} is required")
                continue
            
            if value is None:
                continue
            
            if setting.type == SettingType.INTEGER:
                if not isinstance(value, int):
                    errors.append(f"{setting.name} must be an integer")
                elif setting.min_value is not None and value < setting.min_value:
                    errors.append(f"{setting.name} must be at least {setting.min_value}")
                elif setting.max_value is not None and value > setting.max_value:
                    errors.append(f"{setting.name} must be at most {setting.max_value}")
            
            elif setting.type == SettingType.CHOICE:
                valid_ids = [c["id"] for c in (setting.choices or [])]
                if value not in valid_ids:
                    errors.append(f"{setting.name}: invalid choice '{value}'")
        
        return errors


class RenderStatus(Enum):
    """Standardized render status across all engines."""
    IDLE = "idle"
    PREPARING = "preparing"
    RENDERING = "rendering"
    PAUSED = "paused"
    COMPLETING = "completing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RenderProgress:
    """Standardized progress information from any render engine."""
    status: RenderStatus = RenderStatus.IDLE
    total_progress: float = 0.0
    current_frame: int = 0
    total_frames: int = 1
    frame_progress: float = 0.0
    current_pass: str = ""
    current_pass_num: int = 0
    total_passes: int = 1
    elapsed_seconds: float = 0.0
    estimated_remaining: float = 0.0
    memory_used_mb: float = 0.0
    gpu_usage_percent: float = 0.0
    message: str = ""
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "total_progress": self.total_progress,
            "current_frame": self.current_frame,
            "total_frames": self.total_frames,
            "frame_progress": self.frame_progress,
            "current_pass": self.current_pass,
            "current_pass_num": self.current_pass_num,
            "total_passes": self.total_passes,
            "elapsed_seconds": self.elapsed_seconds,
            "estimated_remaining": self.estimated_remaining,
            "memory_used_mb": self.memory_used_mb,
            "gpu_usage_percent": self.gpu_usage_percent,
            "message": self.message,
            "error_message": self.error_message,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RenderProgress":
        return cls(
            status=RenderStatus(data.get("status", "idle")),
            total_progress=data.get("total_progress", 0.0),
            current_frame=data.get("current_frame", 0),
            total_frames=data.get("total_frames", 1),
            frame_progress=data.get("frame_progress", 0.0),
            current_pass=data.get("current_pass", ""),
            current_pass_num=data.get("current_pass_num", 0),
            total_passes=data.get("total_passes", 1),
            elapsed_seconds=data.get("elapsed_seconds", 0.0),
            estimated_remaining=data.get("estimated_remaining", 0.0),
            memory_used_mb=data.get("memory_used_mb", 0.0),
            gpu_usage_percent=data.get("gpu_usage_percent", 0.0),
            message=data.get("message", ""),
            error_message=data.get("error_message", ""),
        )


class EngineInterface(ABC):
    """Abstract interface that all render engines must implement."""
    
    @property
    @abstractmethod
    def settings_schema(self) -> EngineSettingsSchema:
        pass
    
    @abstractmethod
    def read_scene_settings(self, file_path: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def apply_settings(self, file_path: str, settings: Dict[str, Any]) -> bool:
        pass
    
    @abstractmethod
    def get_progress(self) -> RenderProgress:
        pass
    
    @abstractmethod
    def pause_render(self) -> bool:
        pass
    
    @abstractmethod
    def resume_render(self) -> bool:
        pass
    
    @abstractmethod
    def stop_render(self) -> bool:
        pass


ProgressCallback = Callable[[RenderProgress], None]
LogCallback = Callable[[str], None]
