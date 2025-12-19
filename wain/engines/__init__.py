"""
Wain Render Engines
===================

Render engine implementations and registry.

v2.15.0 - Added VantageINIManager for full HQ settings control
"""

from wain.engines.base import RenderEngine
from wain.engines.blender import BlenderEngine
from wain.engines.marmoset import MarmosetEngine
from wain.engines.vantage import VantageEngine
from wain.engines.registry import EngineRegistry

from wain.engines.interface import (
    EngineInterface,
    EngineSettingsSchema,
    SettingDefinition,
    SettingType,
    SettingCategory,
    RenderProgress,
    RenderStatus,
)

# Vantage INI settings manager (v2.15.0)
from wain.engines.vantage_settings import (
    VantageINIManager,
    VantageHQSettings,
    read_vantage_settings,
    apply_render_settings,
)

__all__ = [
    'RenderEngine',
    'BlenderEngine',
    'MarmosetEngine',
    'VantageEngine',
    'EngineRegistry',
    'EngineInterface',
    'EngineSettingsSchema',
    'SettingDefinition',
    'SettingType',
    'SettingCategory',
    'RenderProgress',
    'RenderStatus',
    # Vantage settings (v2.15.0)
    'VantageINIManager',
    'VantageHQSettings',
    'read_vantage_settings',
    'apply_render_settings',
]
