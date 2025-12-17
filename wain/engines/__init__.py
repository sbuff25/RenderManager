"""
Wain Render Engines
===================

Render engine implementations and registry.

Architecture v2.10:
- interface.py: Defines EngineInterface and RenderProgress structures
- Each engine implements the interface for consistent communication
- Settings are schema-driven for UI generation
"""

from wain.engines.base import RenderEngine
from wain.engines.blender import BlenderEngine
from wain.engines.marmoset import MarmosetEngine
from wain.engines.vantage import VantageEngine
from wain.engines.registry import EngineRegistry

# New communication interface
from wain.engines.interface import (
    EngineInterface,
    EngineSettingsSchema,
    SettingDefinition,
    SettingType,
    SettingCategory,
    RenderProgress,
    RenderStatus,
)

__all__ = [
    'RenderEngine',
    'BlenderEngine',
    'MarmosetEngine',
    'VantageEngine',
    'EngineRegistry',
    # Interface classes
    'EngineInterface',
    'EngineSettingsSchema',
    'SettingDefinition',
    'SettingType',
    'SettingCategory',
    'RenderProgress',
    'RenderStatus',
]
