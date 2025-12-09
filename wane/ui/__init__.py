"""
Wane UI Components
==================

User interface components, dialogs, and styles.
"""

from wane.ui.components import create_stat_card, create_job_card
from wane.ui.dialogs import show_add_job_dialog, show_settings_dialog
from wane.ui.main import main_page

__all__ = [
    'create_stat_card',
    'create_job_card',
    'show_add_job_dialog',
    'show_settings_dialog',
    'main_page',
]
