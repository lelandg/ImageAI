"""
Centralized splitter styling for consistent UI across the application.

This module provides a single source of truth for QSplitter styling
to make it easy to update the appearance of all splitters at once.
"""

from PySide6.QtWidgets import QSplitter


# Centralized splitter stylesheet
SPLITTER_STYLESHEET = """
    QSplitter::handle {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #e0e0e0, stop:0.5 #888888, stop:1 #e0e0e0);
        border: 1px solid #cccccc;
    }
    QSplitter::handle:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #a0a0ff, stop:0.5 #6060ff, stop:1 #a0a0ff);
    }
"""

# Default handle width for splitters
DEFAULT_HANDLE_WIDTH = 8


def apply_splitter_style(splitter: QSplitter, handle_width: int = DEFAULT_HANDLE_WIDTH):
    """
    Apply the standard splitter style to a QSplitter widget.

    Args:
        splitter: The QSplitter widget to style
        handle_width: Width of the splitter handle in pixels (default: 8)
    """
    splitter.setHandleWidth(handle_width)
    splitter.setStyleSheet(SPLITTER_STYLESHEET)
