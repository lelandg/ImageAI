"""
Centralized dialog management for consistent error logging and user messaging.
"""

import logging
from typing import Optional
from datetime import datetime
from PySide6.QtWidgets import QMessageBox, QWidget
from PySide6.QtCore import QObject, Signal


class DialogManager(QObject):
    """
    Centralized manager for all application dialogs with logging.
    Provides consistent error display and comprehensive logging of all user messages.
    """
    
    # Signal emitted when any dialog is shown
    dialog_shown = Signal(str, str, str)  # type, title, message
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__()
        self.parent = parent
        self.logger = logging.getLogger(__name__)
        
        # Connect to our own signal for logging
        self.dialog_shown.connect(self._log_dialog)
    
    def _log_dialog(self, dialog_type: str, title: str, message: str):
        """Log all dialogs shown to users"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"[DIALOG] {timestamp} | {dialog_type} | {title} | {message}")
    
    def show_error(self, title: str, message: str, parent: Optional[QWidget] = None) -> int:
        """
        Show error dialog with logging.
        
        Args:
            title: Dialog title
            message: Error message
            parent: Parent widget (uses default if None)
            
        Returns:
            Dialog result code
        """
        parent_widget = parent or self.parent
        self.dialog_shown.emit("ERROR", title, message)
        
        return QMessageBox.critical(
            parent_widget,
            title,
            message,
            QMessageBox.StandardButton.Ok
        )
    
    def show_warning(self, title: str, message: str, parent: Optional[QWidget] = None) -> int:
        """
        Show warning dialog with logging.
        
        Args:
            title: Dialog title
            message: Warning message
            parent: Parent widget (uses default if None)
            
        Returns:
            Dialog result code
        """
        parent_widget = parent or self.parent
        self.dialog_shown.emit("WARNING", title, message)
        
        return QMessageBox.warning(
            parent_widget,
            title,
            message,
            QMessageBox.StandardButton.Ok
        )
    
    def show_info(self, title: str, message: str, parent: Optional[QWidget] = None) -> int:
        """
        Show information dialog with logging.
        
        Args:
            title: Dialog title
            message: Information message
            parent: Parent widget (uses default if None)
            
        Returns:
            Dialog result code
        """
        parent_widget = parent or self.parent
        self.dialog_shown.emit("INFO", title, message)
        
        return QMessageBox.information(
            parent_widget,
            title,
            message,
            QMessageBox.StandardButton.Ok
        )
    
    def show_question(self, title: str, message: str, 
                     buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                     parent: Optional[QWidget] = None) -> int:
        """
        Show question dialog with logging.
        
        Args:
            title: Dialog title
            message: Question message
            buttons: Dialog buttons
            parent: Parent widget (uses default if None)
            
        Returns:
            Dialog result code
        """
        parent_widget = parent or self.parent
        self.dialog_shown.emit("QUESTION", title, message)
        
        return QMessageBox.question(
            parent_widget,
            title,
            message,
            buttons
        )
    
    def show_generation_error(self, operation: str, error_message: str, parent: Optional[QWidget] = None) -> int:
        """
        Show generation-specific error with enhanced logging.
        
        Args:
            operation: The operation that failed (e.g., "Prompt Enhancement")
            error_message: Detailed error message
            parent: Parent widget (uses default if None)
            
        Returns:
            Dialog result code
        """
        title = "Generation Failed"
        formatted_message = f"{operation} failed:\n\n{error_message}"
        
        parent_widget = parent or self.parent
        self.dialog_shown.emit("GENERATION_ERROR", title, formatted_message)
        
        # Also log the raw error for debugging
        self.logger.error(f"Generation failure - Operation: {operation}, Error: {error_message}")
        
        return QMessageBox.critical(
            parent_widget,
            title,
            formatted_message,
            QMessageBox.StandardButton.Ok
        )
    
    def show_success(self, title: str, message: str, parent: Optional[QWidget] = None) -> int:
        """
        Show success dialog with logging.
        
        Args:
            title: Dialog title
            message: Success message
            parent: Parent widget (uses default if None)
            
        Returns:
            Dialog result code
        """
        parent_widget = parent or self.parent
        self.dialog_shown.emit("SUCCESS", title, message)
        
        return QMessageBox.information(
            parent_widget,
            title,
            message,
            QMessageBox.StandardButton.Ok
        )


# Global instance for easy access throughout the application
_global_dialog_manager: Optional[DialogManager] = None


def get_dialog_manager(parent: Optional[QWidget] = None) -> DialogManager:
    """
    Get the global dialog manager instance, creating it if necessary.
    
    Args:
        parent: Parent widget for dialogs
        
    Returns:
        DialogManager instance
    """
    global _global_dialog_manager
    if _global_dialog_manager is None:
        _global_dialog_manager = DialogManager(parent)
    return _global_dialog_manager


def set_dialog_manager_parent(parent: QWidget):
    """
    Set the parent widget for the global dialog manager.
    
    Args:
        parent: Parent widget for dialogs
    """
    global _global_dialog_manager
    if _global_dialog_manager is not None:
        _global_dialog_manager.parent = parent