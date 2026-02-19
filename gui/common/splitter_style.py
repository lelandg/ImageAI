"""
Centralized splitter styling for consistent UI across the application.

This module provides a single source of truth for QSplitter styling.
Colors match the Maestro brand theme (gui/theme.py).
"""

from PySide6.QtWidgets import QSplitter
from ..theme import BORDER_CYAN, CYAN


SPLITTER_STYLESHEET = f"""
    QSplitter::handle {{
        background: {BORDER_CYAN};
        border: none;
        margin: 1px 0;
    }}
    QSplitter::handle:hover {{
        background: {CYAN};
    }}
    QSplitter::handle:vertical {{
        height: 6px;
    }}
    QSplitter::handle:horizontal {{
        width: 6px;
    }}
"""

DEFAULT_HANDLE_WIDTH = 6


def apply_splitter_style(splitter: QSplitter, handle_width: int = DEFAULT_HANDLE_WIDTH):
    """Apply the Maestro splitter style to a QSplitter widget."""
    splitter.setHandleWidth(handle_width)
    splitter.setStyleSheet(SPLITTER_STYLESHEET)
