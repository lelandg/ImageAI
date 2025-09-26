"""Shortcut hint widget with enhanced visibility."""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QEnterEvent


class ShortcutHintLabel(QLabel):
    """A QLabel that shows keyboard shortcuts with improved visibility on hover."""

    def __init__(self, text: str, parent=None):
        """Initialize the shortcut hint label.

        Args:
            text: The shortcut hint text to display
            parent: Parent widget
        """
        super().__init__(parent)

        # Store original text without HTML
        self._text = text

        # Set initial style (subtle gray)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self._set_default_style()

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)

        # Make it easier to hover by adding some padding
        self.setContentsMargins(0, 5, 0, 5)

    def _set_default_style(self):
        """Set the default (non-hovered) style."""
        # Lighter gray with slight transparency for subtlety
        self.setText(f"""
            <div style='
                color: #909090;
                font-size: 9px;
                padding: 2px;
                background-color: rgba(240, 240, 240, 0.2);
                border-radius: 2px;
            '>
                {self._text}
            </div>
        """)
        self.setStyleSheet("""
            QLabel {
                padding: 2px;
                margin: 2px;
            }
        """)

    def _set_hover_style(self):
        """Set the hover style with increased contrast."""
        # Darker text with highlighted background for better visibility
        self.setText(f"""
            <div style='
                color: #2c3e50;
                font-size: 9px;
                font-weight: 500;
                padding: 2px;
                background-color: #e8f4f8;
                border: 1px solid #b0c4de;
                border-radius: 2px;
            '>
                {self._text}
            </div>
        """)
        self.setStyleSheet("""
            QLabel {
                padding: 2px;
                margin: 2px;
                background-color: #f0f8ff;
                border-radius: 4px;
            }
        """)

    def enterEvent(self, event: QEnterEvent):
        """Handle mouse enter event."""
        self._set_hover_style()
        # Change cursor to indicate interactivity
        self.setCursor(Qt.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        """Handle mouse leave event."""
        self._set_default_style()
        # Reset cursor
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)


def create_shortcut_hint(text: str, parent=None) -> ShortcutHintLabel:
    """Create a shortcut hint label with the standard format.

    Args:
        text: The shortcuts text (e.g., "Ctrl+Enter to generate, Esc to cancel")
        parent: Parent widget

    Returns:
        A configured ShortcutHintLabel
    """
    # Add "Shortcuts: " prefix if not present
    if not text.startswith("Shortcuts:"):
        text = f"Shortcuts: {text}"

    return ShortcutHintLabel(text, parent)


# Alternative: Simple function to create enhanced HTML with better base contrast
def create_enhanced_shortcut_html(text: str) -> str:
    """Create enhanced HTML for shortcut hints with better contrast.

    This is a simpler alternative that doesn't require hover but has better base visibility.
    """
    return f"""
        <div style='
            color: #5a6c7d;
            font-size: 11px;
            font-weight: 450;
            padding: 4px 8px;
            background: linear-gradient(to right, #f8f9fa, #ffffff, #f8f9fa);
            border-left: 3px solid #4a90e2;
            margin: 3px 0;
            font-family: "Segoe UI", Arial, sans-serif;
        '>
            <span style='color: #4a90e2; font-weight: 500;'>⌨</span>
            <strong>Shortcuts:</strong> {text}
        </div>
    """