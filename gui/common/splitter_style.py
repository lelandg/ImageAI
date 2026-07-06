"""
Centralized splitter styling for consistent UI across the application.

This module provides a single source of truth for QSplitter styling.
Colors match the Maestro brand theme (gui/theme.py).
"""

from PySide6.QtWidgets import QSplitter
from ..theme import BORDER_CYAN, CYAN, CYAN_DARK


# Handles must be visible at rest — a subtle body with a bright center grip
# line — not only on hover; users can't grab what they can't see. Handle size
# comes from setHandleWidth() (not the stylesheet), so callers can widen an
# individual splitter without the stylesheet fighting them.
SPLITTER_STYLESHEET = f"""
    QSplitter::handle {{
        border: none;
    }}
    QSplitter::handle:vertical {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {BORDER_CYAN}, stop:0.32 {BORDER_CYAN},
            stop:0.38 {CYAN_DARK}, stop:0.62 {CYAN_DARK},
            stop:0.68 {BORDER_CYAN}, stop:1 {BORDER_CYAN});
    }}
    QSplitter::handle:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {BORDER_CYAN}, stop:0.32 {BORDER_CYAN},
            stop:0.38 {CYAN_DARK}, stop:0.62 {CYAN_DARK},
            stop:0.68 {BORDER_CYAN}, stop:1 {BORDER_CYAN});
    }}
    QSplitter::handle:vertical:hover,
    QSplitter::handle:horizontal:hover {{
        background: {CYAN};
    }}
"""

DEFAULT_HANDLE_WIDTH = 8


def apply_splitter_style(splitter: QSplitter, handle_width: int = DEFAULT_HANDLE_WIDTH):
    """Apply the Maestro splitter style to a QSplitter widget."""
    splitter.setHandleWidth(handle_width)
    splitter.setStyleSheet(SPLITTER_STYLESHEET)
