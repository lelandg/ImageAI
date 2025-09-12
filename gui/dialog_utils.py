"""
Utility functions for dialogs with automatic logging.
Ensures all errors shown to users are also logged for debugging.
"""

import logging
from PySide6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


def show_error(parent, title, message, exception=None):
    """
    Show error dialog and log the error.
    
    Args:
        parent: Parent widget
        title: Dialog title
        message: Error message to show
        exception: Optional exception object for detailed logging
    """
    if exception:
        logger.error(f"{title}: {message}", exc_info=exception)
    else:
        logger.error(f"{title}: {message}")
    QMessageBox.critical(parent, title, message)


def show_warning(parent, title, message, log_level=logging.WARNING):
    """
    Show warning dialog and log the warning.
    
    Args:
        parent: Parent widget
        title: Dialog title  
        message: Warning message to show
        log_level: Logging level (default: WARNING)
    """
    logger.log(log_level, f"{title}: {message}")
    QMessageBox.warning(parent, title, message)


def show_info(parent, title, message, log=True):
    """
    Show information dialog and optionally log it.
    
    Args:
        parent: Parent widget
        title: Dialog title
        message: Info message to show
        log: Whether to log this info (default: True)
    """
    if log:
        logger.info(f"{title}: {message}")
    QMessageBox.information(parent, title, message)


def show_question(parent, title, message, buttons=QMessageBox.Yes | QMessageBox.No):
    """
    Show question dialog and log the interaction.
    
    Args:
        parent: Parent widget
        title: Dialog title
        message: Question to ask
        buttons: Button combination to show
        
    Returns:
        User's response (QMessageBox.Yes, QMessageBox.No, etc.)
    """
    logger.info(f"Question dialog: {title}: {message}")
    result = QMessageBox.question(parent, title, message, buttons)
    logger.info(f"User response: {result}")
    return result