"""
Wain Render Engines
===================

Render engine implementations and registry.

v2.15.15 - Safe Vantage settings with INI backup/restore
"""

from wain.engines.base import RenderEngine
from wain.engines.blender import BlenderEngine
from wain.engines.marmoset import MarmosetEngine
from wain.engines.vantage import VantageEngine
from wain.engines.registry import EngineRegistry

# Vantage settings management
from wain.engines.vantage_settings import (
    VantageINIManager,
    VantageHQSettings,
    read_vantage_settings,
    apply_vantage_settings,
)

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
    # Vantage settings
    'VantageINIManager',
    'VantageHQSettings',
    'read_vantage_settings',
    'apply_vantage_settings',
    # Interface classes
    'EngineInterface',
    'EngineSettingsSchema',
    'SettingDefinition',
    'SettingType',
    'SettingCategory',
    'RenderProgress',
    'RenderStatus',
]
