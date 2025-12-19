"""
Wain Configuration
==================

Theme colors, engine configurations, and application constants.
"""

import os

# Cache busting - increment to force browser asset refresh
ASSET_VERSION = "v10"

# Application info
APP_NAME = "Wain"
APP_VERSION = "2.14.0"
CONFIG_FILE = "wain_config.json"

# Required Python version
MIN_PYTHON_VERSION = (3, 10)
MAX_PYTHON_VERSION = (3, 14)
RECOMMENDED_PYTHON = "3.10, 3.11, 3.12, or 3.13"

# Dark theme for NiceGUI/Quasar
DARK_THEME = {
    'dark': True,
    'colors': {
        'primary': '#a1a1aa',      # Neutral gray for main app chrome
        'secondary': '#6b7280',
        'accent': '#71717a',        # Neutral accent
        'positive': '#22c55e',
        'negative': '#ef4444',
        'info': '#71717a',          # Neutral info
        'warning': '#f59e0b',
    }
}

# Engine-specific accent colors
# STANDARD: Each render engine gets its own distinct accent color.
# These colors are used for: status badges, action buttons, progress bars,
# submit buttons, version badges, and any engine-specific UI elements.
# When adding a new engine, assign a unique, visually distinct color.
ENGINE_COLORS = {
    "blender": "#ea7600",    # Orange
    "marmoset": "#ef0343",   # Red
    "vantage": "#77b22a",    # Green (Chaos Vantage brand color)
}

# Engine logo files (in assets/ subfolder) - will be validated at runtime
ENGINE_LOGOS = {
    "blender": "blender_logo.png",
    "marmoset": "marmoset_logo.png",
    "vantage": "vantage_logo.png",
}

# Fallback Material icons for engines (used when logo files missing)
ENGINE_ICONS = {
    "blender": "view_in_ar",
    "marmoset": "diamond",
    "vantage": "landscape",
}

# Status display configuration
STATUS_CONFIG = {
    "rendering": {"color": "blue", "icon": "play_circle", "bg": "blue-900"},
    "queued": {"color": "yellow", "icon": "schedule", "bg": "yellow-900"},
    "paused": {"color": "orange", "icon": "pause_circle", "bg": "orange-900"},
    "completed": {"color": "green", "icon": "check_circle", "bg": "green-900"},
    "failed": {"color": "red", "icon": "error", "bg": "red-900"},
}

# Assets folder name
ASSETS_FOLDER = "assets"

# Required asset files (wain_logo.png or wain_logo.png both accepted)
REQUIRED_ASSETS = [
    'wain_logo.png',  # or wain_logo.png
    'blender_logo.png',
    'marmoset_logo.png',
    'vantage_logo.png',
]

# Runtime-validated logos (populated by check_assets)
AVAILABLE_LOGOS = {}

def check_assets(assets_dir: str):
    """Check which asset files exist and update AVAILABLE_LOGOS."""
    # Clear and update in place (don't reassign - other modules have references)
    AVAILABLE_LOGOS.clear()
    
    if not assets_dir or not os.path.isdir(assets_dir):
        return
    
    # Check engine logos
    for engine, logo_file in ENGINE_LOGOS.items():
        logo_path = os.path.join(assets_dir, logo_file)
        if os.path.isfile(logo_path):
            AVAILABLE_LOGOS[engine] = logo_file
            print(f"  Found: {logo_file}")
        else:
            print(f"  Missing: {logo_file}")
    
    # Check wain/wain logo (support both spellings)
    for logo_name in ['wain_logo.png', 'wain_logo.png']:
        logo_path = os.path.join(assets_dir, logo_name)
        if os.path.isfile(logo_path):
            AVAILABLE_LOGOS['wain'] = logo_name
            print(f"  Found: {logo_name}")
            break
    else:
        print(f"  Missing: wain_logo.png (or wain_logo.png)")

# Blender denoiser options - maps display name to internal Blender value
BLENDER_DENOISERS = {
    'OpenImageDenoise': 'OPENIMAGEDENOISE',
    'OptiX': 'OPTIX',
}

# Reverse mapping for loading from scene (handles case variations)
BLENDER_DENOISER_FROM_INTERNAL = {
    'OPENIMAGEDENOISE': 'OpenImageDenoise',
    'OPTIX': 'OptiX',
}
