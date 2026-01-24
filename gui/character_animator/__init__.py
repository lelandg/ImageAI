"""
GUI components for Character Animator puppet automation.

Provides:
- Installation dialogs for AI dependencies
- Puppet creation wizard
- Progress feedback during generation
"""

from .install_dialog import (
    PuppetInstallConfirmDialog,
    PuppetInstallProgressDialog,
)
from .puppet_wizard import PuppetWizard

__all__ = [
    "PuppetInstallConfirmDialog",
    "PuppetInstallProgressDialog",
    "PuppetWizard",
]
