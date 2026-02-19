"""
Maestro (ChameleonLabs) visual brand theme for the ImageAI Qt desktop application.

This module is the single source of truth for the Maestro dark theme. It provides:

- Named color constants matching the ChameleonLabs web brand palette
- Font family constants for body, heading, and monospace text
- MAESTRO_QSS: a comprehensive Qt Style Sheet covering all standard Qt widgets
- apply_maestro_theme(): a convenience function to apply the theme to a QApplication

Usage::

    from gui.theme import apply_maestro_theme
    app = QApplication(sys.argv)
    apply_maestro_theme(app)

All color constants are exported at module level for reuse in custom widget
styling (e.g., ``from gui.theme import CYAN, BORDER_CYAN``).
"""

# ---------------------------------------------------------------------------
# Background colors
# ---------------------------------------------------------------------------
NAVY = "#0A0E27"           # main background (brand-navy)
NAVY_LIGHT = "#1A1E3F"     # panels / cards (brand-navy-light)
NAVY_DARK = "#050711"      # deepest background (brand-navy-dark)
NAVY_INPUT = "#0D1130"     # input field backgrounds

# ---------------------------------------------------------------------------
# Accent colors
# ---------------------------------------------------------------------------
CYAN = "#00D4FF"           # primary accent (brand-cyan)
CYAN_LIGHT = "#00BCD4"     # hover state
CYAN_DARK = "#0099CC"      # pressed state

# ---------------------------------------------------------------------------
# Chameleon spectrum
# ---------------------------------------------------------------------------
GREEN = "#4CAF50"          # success / active
AMBER = "#FFC107"          # warning
RED = "#F44336"            # error / destructive
MAGENTA = "#FF1493"        # chameleon-magenta
PURPLE = "#9C27B0"         # chameleon-purple
BLUE = "#2196F3"           # chameleon-blue

# ---------------------------------------------------------------------------
# Text colors
# ---------------------------------------------------------------------------
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#9CA3AF"  # gray-400
TEXT_MUTED = "#6B7280"      # gray-500
TEXT_DISABLED = "#4B5563"   # gray-600

# ---------------------------------------------------------------------------
# Border colors
# ---------------------------------------------------------------------------
BORDER_SUBTLE = "#1E2449"   # very faint border
BORDER_CYAN = "#1A4060"     # ~20 % cyan opacity on dark background

# ---------------------------------------------------------------------------
# Font families
# ---------------------------------------------------------------------------
FONT_BODY = "Roboto, 'Segoe UI', sans-serif"
FONT_HEADING = "Limelight"
FONT_MONO = "Consolas, 'Courier New', monospace"

# ---------------------------------------------------------------------------
# Complete Maestro QSS
# ---------------------------------------------------------------------------
MAESTRO_QSS = f"""
/* ===================================================================
   Maestro (ChameleonLabs) Dark Theme — Auto-generated from gui/theme.py
   =================================================================== */

/* ----- Base widgets ------------------------------------------------- */

QWidget {{
    background-color: {NAVY};
    color: {TEXT_PRIMARY};
    font-size: 10pt;
}}

QMainWindow {{
    background-color: {NAVY_DARK};
}}

QDialog {{
    background-color: {NAVY};
}}

/* ----- Tabs --------------------------------------------------------- */

QTabWidget::pane {{
    background-color: {NAVY};
    border: 1px solid {BORDER_SUBTLE};
    border-top: 2px solid {CYAN};
    margin-top: -1px;
}}

QTabBar::tab {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_SUBTLE};
    border-bottom: none;
    padding: 4px 12px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background-color: {NAVY};
    color: {CYAN};
    border-color: {BORDER_SUBTLE};
    border-bottom: 2px solid {CYAN};
}}

QTabBar::tab:hover:!selected {{
    background-color: {NAVY_INPUT};
    color: {CYAN_LIGHT};
}}

/* ----- Push buttons ------------------------------------------------- */

QPushButton {{
    background-color: {CYAN};
    color: {NAVY_DARK};
    border: none;
    border-radius: 4px;
    padding: 3px 12px;
    font-weight: bold;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {CYAN_LIGHT};
}}

QPushButton:pressed {{
    background-color: {CYAN_DARK};
}}

QPushButton:disabled {{
    background-color: {BORDER_SUBTLE};
    color: {TEXT_DISABLED};
}}

QPushButton:flat {{
    background-color: transparent;
    color: {CYAN};
    border: 1px solid {BORDER_CYAN};
}}

QPushButton:flat:hover {{
    background-color: {NAVY_LIGHT};
    border-color: {CYAN};
}}

/* ----- Text inputs -------------------------------------------------- */

QLineEdit {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 2px 6px;
    selection-background-color: {CYAN_DARK};
    selection-color: {TEXT_PRIMARY};
}}

QLineEdit:focus {{
    border-color: {CYAN};
}}

QLineEdit:disabled {{
    background-color: {NAVY_DARK};
    color: {TEXT_DISABLED};
}}

QTextEdit {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 2px 4px;
    selection-background-color: {CYAN_DARK};
    selection-color: {TEXT_PRIMARY};
}}

QTextEdit:focus {{
    border-color: {CYAN};
}}

QTextEdit:disabled {{
    background-color: {NAVY_DARK};
    color: {TEXT_DISABLED};
}}

QPlainTextEdit {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 2px 4px;
    selection-background-color: {CYAN_DARK};
    selection-color: {TEXT_PRIMARY};
}}

QPlainTextEdit:focus {{
    border-color: {CYAN};
}}

QPlainTextEdit:disabled {{
    background-color: {NAVY_DARK};
    color: {TEXT_DISABLED};
}}

/* ----- Combo box ---------------------------------------------------- */

QComboBox {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 2px 6px;
    min-height: 18px;
}}

QComboBox:focus {{
    border-color: {CYAN};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {BORDER_SUBTLE};
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {TEXT_SECONDARY};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CYAN};
    selection-background-color: {CYAN_DARK};
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}

/* ----- Spin boxes --------------------------------------------------- */

QSpinBox,
QDoubleSpinBox,
QDateEdit {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 2px 4px;
    min-height: 18px;
}}

QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus {{
    border-color: {CYAN};
}}

QSpinBox::up-button,
QDoubleSpinBox::up-button,
QDateEdit::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {BORDER_SUBTLE};
    border-top-right-radius: 4px;
    background-color: {NAVY_LIGHT};
}}

QSpinBox::down-button,
QDoubleSpinBox::down-button,
QDateEdit::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid {BORDER_SUBTLE};
    border-bottom-right-radius: 4px;
    background-color: {NAVY_LIGHT};
}}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow,
QDateEdit::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {TEXT_SECONDARY};
    width: 0px;
    height: 0px;
}}

QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow,
QDateEdit::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    width: 0px;
    height: 0px;
}}

/* ----- Check box & radio button ------------------------------------- */

QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER_SUBTLE};
    border-radius: 3px;
    background-color: {NAVY_INPUT};
}}

QCheckBox::indicator:checked {{
    background-color: {CYAN};
    border-color: {CYAN};
    image: none;
}}

QCheckBox::indicator:hover {{
    border-color: {CYAN_LIGHT};
}}

QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER_SUBTLE};
    border-radius: 10px;
    background-color: {NAVY_INPUT};
}}

QRadioButton::indicator:checked {{
    background-color: {CYAN};
    border-color: {CYAN};
}}

QRadioButton::indicator:hover {{
    border-color: {CYAN_LIGHT};
}}

/* ----- Labels ------------------------------------------------------- */

QLabel {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
}}

/* ----- Group box ---------------------------------------------------- */

QGroupBox {{
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {CYAN};
}}

/* ----- Scroll bars -------------------------------------------------- */

QScrollBar:vertical {{
    background-color: {NAVY_DARK};
    width: 12px;
    margin: 0;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {BORDER_SUBTLE};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
    border: none;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: {NAVY_DARK};
    height: 12px;
    margin: 0;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {BORDER_SUBTLE};
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
    border: none;
}}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ----- Table views -------------------------------------------------- */

QTableView,
QTableWidget {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    gridline-color: {BORDER_SUBTLE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    selection-background-color: {CYAN_DARK};
    selection-color: {TEXT_PRIMARY};
    alternate-background-color: {NAVY_LIGHT};
}}

QHeaderView::section {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_SECONDARY};
    border: none;
    border-right: 1px solid {BORDER_SUBTLE};
    border-bottom: 1px solid {BORDER_SUBTLE};
    padding: 6px 10px;
    font-weight: bold;
}}

/* ----- List / tree views -------------------------------------------- */

QListView,
QListWidget {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    outline: none;
}}

QListView::item:selected,
QListWidget::item:selected {{
    background-color: {CYAN_DARK};
    color: {TEXT_PRIMARY};
}}

QListView::item:hover,
QListWidget::item:hover {{
    background-color: {NAVY_LIGHT};
}}

QTreeView,
QTreeWidget {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    outline: none;
}}

QTreeView::item:selected,
QTreeWidget::item:selected {{
    background-color: {CYAN_DARK};
    color: {TEXT_PRIMARY};
}}

QTreeView::item:hover,
QTreeWidget::item:hover {{
    background-color: {NAVY_LIGHT};
}}

QTreeView::branch {{
    background-color: transparent;
}}

/* ----- Splitter ----------------------------------------------------- */

QSplitter::handle {{
    background-color: {BORDER_CYAN};
    border: none;
}}

QSplitter::handle:hover {{
    background-color: {CYAN};
}}

QSplitter::handle:vertical {{
    height: 6px;
}}

QSplitter::handle:horizontal {{
    width: 6px;
}}

/* ----- Progress bar ------------------------------------------------- */

QProgressBar {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    text-align: center;
    min-height: 18px;
}}

QProgressBar::chunk {{
    background-color: {CYAN};
    border-radius: 3px;
}}

/* ----- Menu bar / menus --------------------------------------------- */

QMenuBar {{
    background-color: {NAVY_DARK};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER_SUBTLE};
    padding: 2px;
}}

QMenuBar::item:selected {{
    background-color: {NAVY_LIGHT};
    color: {CYAN};
}}

QMenu {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CYAN};
    padding: 4px 0;
}}

QMenu::item {{
    padding: 6px 28px 6px 20px;
}}

QMenu::item:selected {{
    background-color: {CYAN_DARK};
    color: {TEXT_PRIMARY};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER_SUBTLE};
    margin: 4px 8px;
}}

/* ----- Status bar --------------------------------------------------- */

QStatusBar {{
    background-color: {NAVY_DARK};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER_SUBTLE};
    padding: 2px;
}}

/* ----- Tool tip ----------------------------------------------------- */

QToolTip {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    border: 1px solid {CYAN};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 9pt;
}}

/* ----- Slider ------------------------------------------------------- */

QSlider::groove:horizontal {{
    background-color: {NAVY_INPUT};
    border: 1px solid {BORDER_SUBTLE};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {CYAN};
    border: none;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {CYAN_LIGHT};
}}

QSlider::sub-page:horizontal {{
    background-color: {CYAN_DARK};
    border-radius: 3px;
}}

/* ----- Frames ------------------------------------------------------- */

QFrame[frameShape="4"] {{
    /* HLine */
    color: {BORDER_SUBTLE};
    max-height: 1px;
}}

QFrame[frameShape="5"] {{
    /* VLine */
    color: {BORDER_SUBTLE};
    max-width: 1px;
}}

QFrame[frameShape="1"] {{
    /* Box */
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
}}

QFrame[frameShape="6"] {{
    /* StyledPanel */
    background-color: {NAVY_LIGHT};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
}}

/* ----- Dock widget -------------------------------------------------- */

QDockWidget {{
    color: {TEXT_PRIMARY};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background-color: {NAVY_LIGHT};
    color: {CYAN};
    border: 1px solid {BORDER_SUBTLE};
    padding: 6px;
    text-align: left;
}}
"""


def apply_maestro_theme(app) -> None:
    """Apply the Maestro dark theme to a QApplication instance.

    Args:
        app: A QApplication (or QGuiApplication) instance. The full
            Maestro QSS will be set via ``app.setStyleSheet()``.
    """
    app.setStyleSheet(MAESTRO_QSS)
