"""
Wane - Multi-Engine Render Queue Manager
=========================================

A professional render queue manager for 3D artists.
Supports Blender and Marmoset Toolbag with pause/resume capabilities.

Built with NiceGUI + pywebview (Qt backend) for native desktop window.
Works on Python 3.10+ (including 3.13 and 3.14)
"""

__version__ = "1.0.0"
__author__ = "Spencer"
__app_name__ = "Wane"

from wane.config import (
    APP_NAME,
    APP_VERSION,
    DARK_THEME,
    ENGINE_COLORS,
    ENGINE_LOGOS,
    STATUS_CONFIG,
    ASSET_VERSION,
)

from wane.models import RenderJob, AppSettings
from wane.engines import RenderEngine, BlenderEngine, MarmosetEngine, EngineRegistry
from wane.app import RenderApp

__all__ = [
    '__version__',
    '__app_name__',
    'APP_NAME',
    'APP_VERSION',
    'DARK_THEME',
    'ENGINE_COLORS',
    'ENGINE_LOGOS',
    'STATUS_CONFIG',
    'ASSET_VERSION',
    'RenderJob',
    'AppSettings',
    'RenderEngine',
    'BlenderEngine',
    'MarmosetEngine',
    'EngineRegistry',
    'RenderApp',
]
