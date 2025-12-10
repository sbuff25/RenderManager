"""
Wane Configuration
==================

Theme colors, engine configurations, and application constants.
"""

# Cache busting - increment to force browser asset refresh
ASSET_VERSION = "v3"

# Application info
APP_NAME = "Wane"
APP_VERSION = "2.4.0"
CONFIG_FILE = "wane_config.json"

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
ENGINE_COLORS = {
    "blender": "#ea7600",
    "marmoset": "#ef0343",
}

# Engine logo files (in assets/ subfolder)
ENGINE_LOGOS = {
    "blender": "blender_logo.png",
    "marmoset": "marmoset_logo.png",
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

# Required asset files
REQUIRED_ASSETS = [
    'wain_logo.png',
    'blender_logo.png',
    'marmoset_logo.png',
]
