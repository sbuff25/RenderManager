"""
Wain Engine Communication Interface
====================================

This module defines the standardized interface for communication between
Wain and render engines. Every engine must implement these interfaces
to ensure consistent behavior across Vantage, Blender, Marmoset, and
any future engines.

Architecture:
------------
1. EngineSettings - Schema defining what settings an engine exposes
2. RenderProgress - Standardized progress data structure
3. EngineInterface - Abstract methods each engine must implement

This ensures:
- Settings configured in Wain are applied to the engine
- Progress is accurately reported in real-time
- Pause/resume works correctly
- The system scales to any render engine
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union


# =============================================================================
# SETTING TYPES
# =============================================================================

class SettingType(Enum):
    """Types of settings that can be configured."""
    INTEGER = "integer"         # Whole number (samples, frames)
    FLOAT = "float"             # Decimal number (quality, strength)
    BOOLEAN = "boolean"         # True/False toggle
    STRING = "string"           # Text input
    CHOICE = "choice"           # Dropdown selection
    MULTI_CHOICE = "multi"      # Multiple selection (render passes)
    PATH = "path"               # File/folder path
    RESOLUTION = "resolution"   # Width x Height pair
    FRAME_RANGE = "frame_range" # Start - End frame pair


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
    """
    Defines a single configurable setting.
    
    This schema describes what settings an engine exposes to Wain,
    including how to display them in the UI and validate values.
    """
    id: str                     # Internal ID (e.g., "samples")
    name: str                   # Display name (e.g., "Render Samples")
    type: SettingType           # Type of setting
    category: SettingCategory   # UI category grouping
    default: Any                # Default value
    description: str = ""       # Tooltip/help text
    
    # Type-specific options
    min_value: Optional[float] = None    # For INTEGER/FLOAT
    max_value: Optional[float] = None    # For INTEGER/FLOAT
    step: Optional[float] = None         # For INTEGER/FLOAT increment
    choices: Optional[List[Dict]] = None # For CHOICE/MULTI_CHOICE: [{"id": "x", "name": "X"}, ...]
    
    # Validation
    required: bool = True
    depends_on: Optional[str] = None     # Show only if another setting is truthy
    
    # Engine-specific mapping
    engine_key: Optional[str] = None     # Key used by engine (if different from id)


@dataclass 
class EngineSettingsSchema:
    """
    Complete settings schema for an engine.
    
    Defines all configurable settings that Wain can control for this engine.
    """
    engine_type: str                    # e.g., "vantage", "blender"
    engine_name: str                    # e.g., "Chaos Vantage", "Blender"
    version: str                        # Schema version for migration
    settings: List[SettingDefinition]   # All available settings
    
    def get_setting(self, setting_id: str) -> Optional[SettingDefinition]:
        """Get a setting definition by ID."""
        for s in self.settings:
            if s.id == setting_id:
                return s
        return None
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get dictionary of all default values."""
        return {s.id: s.default for s in self.settings}
    
    def get_by_category(self, category: SettingCategory) -> List[SettingDefinition]:
        """Get all settings in a category."""
        return [s for s in self.settings if s.category == category]
    
    def validate(self, values: Dict[str, Any]) -> List[str]:
        """
        Validate a dictionary of setting values.
        Returns list of error messages (empty if valid).
        """
        errors = []
        for setting in self.settings:
            value = values.get(setting.id)
            
            # Check required
            if setting.required and value is None:
                errors.append(f"{setting.name} is required")
                continue
            
            if value is None:
                continue
            
            # Type-specific validation
            if setting.type == SettingType.INTEGER:
                if not isinstance(value, int):
                    errors.append(f"{setting.name} must be an integer")
                elif setting.min_value is not None and value < setting.min_value:
                    errors.append(f"{setting.name} must be at least {setting.min_value}")
                elif setting.max_value is not None and value > setting.max_value:
                    errors.append(f"{setting.name} must be at most {setting.max_value}")
            
            elif setting.type == SettingType.FLOAT:
                if not isinstance(value, (int, float)):
                    errors.append(f"{setting.name} must be a number")
                elif setting.min_value is not None and value < setting.min_value:
                    errors.append(f"{setting.name} must be at least {setting.min_value}")
                elif setting.max_value is not None and value > setting.max_value:
                    errors.append(f"{setting.name} must be at most {setting.max_value}")
            
            elif setting.type == SettingType.CHOICE:
                valid_ids = [c["id"] for c in (setting.choices or [])]
                if value not in valid_ids:
                    errors.append(f"{setting.name}: invalid choice '{value}'")
            
            elif setting.type == SettingType.MULTI_CHOICE:
                if not isinstance(value, list):
                    errors.append(f"{setting.name} must be a list")
                else:
                    valid_ids = [c["id"] for c in (setting.choices or [])]
                    for v in value:
                        if v not in valid_ids:
                            errors.append(f"{setting.name}: invalid choice '{v}'")
        
        return errors


# =============================================================================
# PROGRESS DATA STRUCTURE
# =============================================================================

class RenderStatus(Enum):
    """Standardized render status across all engines."""
    IDLE = "idle"               # Not rendering
    PREPARING = "preparing"     # Loading scene, initializing
    RENDERING = "rendering"     # Actively rendering
    PAUSED = "paused"           # Paused by user
    COMPLETING = "completing"   # Finishing up (saving, cleanup)
    COMPLETE = "complete"       # Successfully finished
    FAILED = "failed"           # Error occurred
    CANCELLED = "cancelled"     # Cancelled by user


@dataclass
class RenderProgress:
    """
    Standardized progress information from any render engine.
    
    This is the data structure that engines populate and Wain displays.
    All engines must provide progress in this format for consistent UI.
    """
    # Overall status
    status: RenderStatus = RenderStatus.IDLE
    
    # Total job progress (0-100)
    total_progress: float = 0.0
    
    # Frame information
    current_frame: int = 0          # Frame currently being rendered
    total_frames: int = 1           # Total frames to render
    frame_progress: float = 0.0     # Progress of current frame (0-100)
    
    # Pass information (for multi-pass renders)
    current_pass: str = ""          # Name of current pass
    current_pass_num: int = 0       # Pass number (1-indexed)
    total_passes: int = 1           # Total passes to render
    
    # Time tracking
    elapsed_seconds: float = 0.0    # Time spent rendering
    estimated_remaining: float = 0.0 # Estimated time remaining
    
    # Memory/performance (optional)
    memory_used_mb: float = 0.0     # Memory usage
    gpu_usage_percent: float = 0.0  # GPU utilization
    
    # Status message
    message: str = ""               # Human-readable status
    
    # Error information
    error_message: str = ""         # Error details if status == FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
        """Create from dictionary."""
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


# =============================================================================
# ENGINE INTERFACE
# =============================================================================

class EngineInterface(ABC):
    """
    Abstract interface that all render engines must implement.
    
    This ensures consistent communication patterns across all engines.
    """
    
    @property
    @abstractmethod
    def settings_schema(self) -> EngineSettingsSchema:
        """
        Return the settings schema for this engine.
        
        This defines what settings Wain can configure and how they
        appear in the UI.
        """
        pass
    
    @abstractmethod
    def read_scene_settings(self, file_path: str) -> Dict[str, Any]:
        """
        Read current settings from a scene file.
        
        Args:
            file_path: Path to the scene file
            
        Returns:
            Dictionary of setting_id -> current_value
        """
        pass
    
    @abstractmethod
    def apply_settings(self, file_path: str, settings: Dict[str, Any]) -> bool:
        """
        Apply settings to the scene/engine before rendering.
        
        Args:
            file_path: Path to the scene file
            settings: Dictionary of setting_id -> value to apply
            
        Returns:
            True if settings were applied successfully
        """
        pass
    
    @abstractmethod
    def get_progress(self) -> RenderProgress:
        """
        Get current render progress.
        
        Returns:
            RenderProgress with current state
        """
        pass
    
    @abstractmethod
    def pause_render(self) -> bool:
        """
        Pause the current render.
        
        Returns:
            True if pause was successful
        """
        pass
    
    @abstractmethod
    def resume_render(self) -> bool:
        """
        Resume a paused render.
        
        Returns:
            True if resume was successful
        """
        pass
    
    @abstractmethod
    def stop_render(self) -> bool:
        """
        Stop/cancel the current render.
        
        Returns:
            True if stop was successful
        """
        pass


# =============================================================================
# PROGRESS CALLBACK TYPE
# =============================================================================

# Type for progress callback functions
ProgressCallback = Callable[[RenderProgress], None]
LogCallback = Callable[[str], None]
