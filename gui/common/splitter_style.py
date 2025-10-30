"""
Centralized splitter styling for consistent UI across the application.

This module provides a single source of truth for QSplitter styling
to make it easy to update the appearance of all splitters at once.
"""

from PySide6.QtWidgets import QSplitter


# Centralized splitter stylesheet
SPLITTER_STYLESHEET = """
    QSplitter::handle {
        background: #e8e8e8;
        border: none;
        margin: 1px 0;
    }
    QSplitter::handle:hover {
        background: #b0b0ff;
    }
    QSplitter::handle:vertical {
        height: 6px;
    }
    QSplitter::handle:horizontal {
        width: 6px;
    }
"""

# Default handle width for splitters
DEFAULT_HANDLE_WIDTH = 6


def apply_splitter_style(splitter: QSplitter, handle_width: int = DEFAULT_HANDLE_WIDTH):
    """
    Apply the standard splitter style to a QSplitter widget.

    Args:
        splitter: The QSplitter widget to style
        handle_width: Width of the splitter handle in pixels (default: 8)
    """
    splitter.setHandleWidth(handle_width)
    splitter.setStyleSheet(SPLITTER_STYLESHEET)
