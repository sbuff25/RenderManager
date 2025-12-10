"""
Wain UI Components
==================

User interface components, dialogs, and styles.
"""

from wain.ui.components import create_stat_card, create_job_card
from wain.ui.dialogs import show_add_job_dialog, show_settings_dialog, show_edit_job_dialog
from wain.ui.main import main_page

__all__ = [
    'create_stat_card',
    'create_job_card',
    'show_add_job_dialog',
    'show_settings_dialog',
    'show_edit_job_dialog',
    'main_page',
]
