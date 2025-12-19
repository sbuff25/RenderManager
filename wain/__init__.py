"""
Wain - Multi-Engine Render Queue Manager
=========================================

A professional render queue manager for 3D artists.
Supports Blender, Marmoset Toolbag, and Chaos Vantage with pause/resume capabilities.

Built with NiceGUI + pywebview (Qt backend) for native desktop window.
Works on Python 3.10+ (including 3.13 and 3.14)
"""

__version__ = "2.14.0"
__author__ = "Spencer"
__app_name__ = "Wain"

from wain.config import (
    APP_NAME,
    APP_VERSION,
    DARK_THEME,
    ENGINE_COLORS,
    ENGINE_LOGOS,
    ENGINE_ICONS,
    AVAILABLE_LOGOS,
    STATUS_CONFIG,
    ASSET_VERSION,
    BLENDER_DENOISERS,
    BLENDER_DENOISER_FROM_INTERNAL,
    check_assets,
)

from wain.models import RenderJob, AppSettings

__all__ = [
    '__version__',
    '__app_name__',
    'APP_NAME',
    'APP_VERSION',
    'DARK_THEME',
    'ENGINE_COLORS',
    'ENGINE_LOGOS',
    'ENGINE_ICONS',
    'AVAILABLE_LOGOS',
    'STATUS_CONFIG',
    'ASSET_VERSION',
    'BLENDER_DENOISERS',
    'BLENDER_DENOISER_FROM_INTERNAL',
    'check_assets',
    'RenderJob',
    'AppSettings',
]
