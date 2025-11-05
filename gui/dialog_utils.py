"""
Utility functions for dialogs with automatic logging.
Ensures all errors shown to users are also logged for debugging.
"""

import logging
from functools import wraps
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject, QEvent, Qt

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


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


# ============================================================================
# Operation Guarding System for Dialogs
# ============================================================================

class InputBlockerEventFilter(QObject):
    """
    Event filter that blocks user input during async operations.

    Blocks:
    - Mouse clicks (press, release, double-click)
    - Keyboard input (key press, key release)
    - Shortcuts
    - Focus changes (optional)

    Allows:
    - Paint events (keep UI responsive)
    - Close events (allow cancellation)
    """

    def __init__(self, parent=None, block_focus_changes=False):
        super().__init__(parent)
        self.block_focus_changes = block_focus_changes
        self._blocked_event_types = {
            QEvent.MouseButtonPress,
            QEvent.MouseButtonRelease,
            QEvent.MouseButtonDblClick,
            QEvent.KeyPress,
            QEvent.KeyRelease,
            QEvent.Shortcut,
            QEvent.ShortcutOverride,
        }

        if block_focus_changes:
            self._blocked_event_types.update({
                QEvent.FocusIn,
                QEvent.FocusOut,
            })

    def eventFilter(self, obj, event):
        """Filter events to block user input."""
        if event.type() in self._blocked_event_types:
            # Log blocked input (for debugging)
            if event.type() == QEvent.KeyPress:
                logger.debug(f"Blocked key press during operation: {event.key()}")
            elif event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
                logger.debug(f"Blocked mouse click during operation")
            return True  # Block the event

        return False  # Allow other events


class OperationGuardMixin:
    """
    Mixin class for dialogs that perform async operations via QThread.

    Provides:
    - Operation state tracking (is_operation_running)
    - Decorator to guard methods (@guard_operation)
    - Input blocking during operations
    - Status console integration for warnings

    Usage:
        class MyDialog(QDialog, OperationGuardMixin):
            def __init__(self):
                super().__init__()
                self.init_operation_guard()

            @guard_operation
            def my_async_operation(self):
                self.start_operation("Processing...")
                # ... start thread ...

            def on_operation_complete(self):
                self.end_operation()
    """

    def init_operation_guard(self, block_all_input=True, block_focus_changes=False):
        """
        Initialize the operation guard system.

        Args:
            block_all_input: If True, blocks all user input during operations
            block_focus_changes: If True, also blocks focus changes
        """
        self._operation_running = False
        self._operation_name = ""
        self._input_blocker = None
        self._block_all_input = block_all_input
        self._block_focus_changes = block_focus_changes

        # Try to find status console (if available)
        self._status_console = None
        if hasattr(self, 'status_console'):
            self._status_console = self.status_console

    def is_operation_running(self):
        """Check if an operation is currently running."""
        return self._operation_running

    def start_operation(self, operation_name="Operation"):
        """
        Mark that an operation has started.

        Args:
            operation_name: Name of the operation (for logging/warnings)
        """
        if self._operation_running:
            logger.warning(f"Attempted to start '{operation_name}' while '{self._operation_name}' is running")
            return False

        self._operation_running = True
        self._operation_name = operation_name

        # Install input blocker if enabled
        if self._block_all_input:
            self._input_blocker = InputBlockerEventFilter(self, self._block_focus_changes)
            self.installEventFilter(self._input_blocker)
            logger.debug(f"Input blocker installed for operation: {operation_name}")

        logger.info(f"Operation started: {operation_name}")
        return True

    def end_operation(self):
        """Mark that the operation has ended."""
        if not self._operation_running:
            logger.warning("Attempted to end operation when none is running")
            return

        operation_name = self._operation_name
        self._operation_running = False
        self._operation_name = ""

        # Remove input blocker
        if self._input_blocker:
            self.removeEventFilter(self._input_blocker)
            self._input_blocker = None
            logger.debug(f"Input blocker removed after operation: {operation_name}")

        logger.info(f"Operation ended: {operation_name}")

    def check_operation_running(self, new_operation_name="Operation",
                                show_warning=True, log_warning=True):
        """
        Check if an operation is running and show warning if so.

        Args:
            new_operation_name: Name of the operation trying to start
            show_warning: If True, shows warning in status console (if available)
            log_warning: If True, logs the warning

        Returns:
            True if operation is running (blocked), False otherwise (allowed)
        """
        if not self._operation_running:
            return False

        # Operation is running - show warning
        warning_msg = f"{self._operation_name} in progress, please wait..."

        if log_warning:
            logger.warning(f"Blocked '{new_operation_name}': {warning_msg}")
            console.warning(warning_msg)

        if show_warning and self._status_console:
            self._status_console.log(warning_msg, "WARNING")

        return True


def guard_operation(operation_name=None, show_warning=True, log_warning=True):
    """
    Decorator that guards a method from being called while an operation is running.

    The decorated class must inherit from OperationGuardMixin and call init_operation_guard().

    Args:
        operation_name: Optional name for the operation (defaults to method name)
        show_warning: Show warning in status console if blocked
        log_warning: Log warning if blocked

    Usage:
        class MyDialog(QDialog, OperationGuardMixin):
            def __init__(self):
                super().__init__()
                self.init_operation_guard()

            @guard_operation("LLM Enhancement")
            def enhance_prompt(self):
                # This will be blocked if another operation is running
                pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get operation name
            op_name = operation_name or func.__name__.replace('_', ' ').title()

            # Check if operation is running
            if hasattr(self, 'check_operation_running'):
                if self.check_operation_running(op_name, show_warning, log_warning):
                    return None  # Blocked
            elif hasattr(self, 'thread') and self.thread and self.thread.isRunning():
                # Fallback: check thread directly
                warning_msg = f"Operation already in progress, please wait..."
                if log_warning:
                    logger.warning(f"Blocked '{op_name}': {warning_msg}")
                    console.warning(warning_msg)
                if show_warning and hasattr(self, 'status_console') and self.status_console:
                    self.status_console.log(warning_msg, "WARNING")
                return None

            # Allow operation
            return func(self, *args, **kwargs)

        return wrapper
    return decorator