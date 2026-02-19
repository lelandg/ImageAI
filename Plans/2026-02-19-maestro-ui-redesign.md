# Maestro UI Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restyle ImageAI's entire GUI to match the Maestro (ChameleonLabs) visual design — same dark navy background, brand-cyan accent, Roboto/Limelight fonts, rounded panels, and glow effects.

**Architecture:** Create a single `gui/theme.py` source-of-truth for all Maestro colors and a complete QSS stylesheet applied at startup via `app.setStyleSheet()`. This covers ~90% of the work automatically. A small set of hardcoded light-mode inline stylesheets in `main_window.py` and `gui/common/splitter_style.py` will be updated to use the theme constants. Fonts are bundled as TTF files in `gui/resources/fonts/` and loaded via `QFontDatabase`.

**Tech Stack:** PySide6 (QApplication.setStyleSheet, QFontDatabase, QPalette), Python 3.12

**Design reference:** `/mnt/d/Documents/Code/GitHub/Web/ChameleonLabs/app/globals.css`, `tailwind.config.ts`
**Issue:** [#10](https://github.com/lelandg/ImageAI/issues/10)

---

## Agent Dispatch Map

These tasks can be parallelized. Spawn agents as follows:

| Agent | Tasks | Depends On |
|-------|-------|------------|
| A | Task 1 (theme.py) | — |
| B | Task 2 (fonts) | — |
| C | Task 3 (\_\_init\_\_.py) | A + B |
| D | Task 4 (splitter_style.py) | A |
| E | Task 5 (main_window.py) | A |
| F | Task 6 (syntax check) | C + D + E |

---

### Task 1: Create `gui/theme.py` — Maestro Color Constants + QSS

**Files:**
- Create: `gui/theme.py`

**Step 1: Create the theme file**

```python
"""
Maestro UI theme for ImageAI.

Single source of truth for all Maestro brand colors and the Qt stylesheet.
Matches the ChameleonLabs web design (globals.css + tailwind.config.ts).
"""

# ---------------------------------------------------------------------------
# Maestro Brand Colors
# ---------------------------------------------------------------------------

# Backgrounds
NAVY         = "#0A0E27"   # brand-navy — main background
NAVY_LIGHT   = "#1A1E3F"   # brand-navy-light — panels / cards
NAVY_DARK    = "#050711"   # brand-navy-dark — deepest bg
NAVY_INPUT   = "#0D1130"   # slightly lighter for input fields

# Accent
CYAN         = "#00D4FF"   # brand-cyan — primary accent
CYAN_LIGHT   = "#00BCD4"   # brand-cyan-light — hover
CYAN_DARK    = "#0099CC"   # brand-cyan-dark — pressed

# Chameleon spectrum
GREEN        = "#4CAF50"   # chameleon-green  — success / active
AMBER        = "#FFC107"   # chameleon-amber  — warning
RED          = "#F44336"   # chameleon-red    — error / destructive
MAGENTA      = "#FF1493"   # chameleon-magenta
PURPLE       = "#9C27B0"   # chameleon-purple
BLUE         = "#2196F3"   # chameleon-blue

# Text
TEXT_PRIMARY   = "#FFFFFF"
TEXT_SECONDARY = "#9CA3AF"   # gray-400
TEXT_MUTED     = "#6B7280"   # gray-500
TEXT_DISABLED  = "#4B5563"   # gray-600

# Borders
BORDER_SUBTLE  = "#1E2449"   # very faint border
BORDER_CYAN    = "#1A4060"   # ~20% cyan opacity on dark bg (cyan/20 approximation)

# ---------------------------------------------------------------------------
# Font Families
# ---------------------------------------------------------------------------

FONT_BODY    = "Roboto"
FONT_HEADING = "Limelight"
FONT_MONO    = "Consolas, 'Courier New', monospace"

# ---------------------------------------------------------------------------
# Full Maestro QSS Stylesheet
# ---------------------------------------------------------------------------

MAESTRO_QSS = f"""
/* ---- Base ---- */
QWidget {{
    background-color: {NAVY};
    color: {TEXT_PRIMARY};
    font-family: "Roboto", "Segoe UI", sans-serif;
    font-size: 10pt;
}}

QMainWindow, QDialog {{
    background-color: {NAVY};
}}

/* ---- Tabs ---- */
QTabWidget::pane {{
    border: 1px solid {BORDER_CYAN};
    background-color: {NAVY_LIGHT};
    border-radius: 6px;
}}
QTabBar::tab {{
    background-color: {NAVY_DARK};
    color: {TEXT_SECONDARY};
    padding: 6px 14px;
    border: 1px solid {BORDER_CYAN};
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {NAVY_LIGHT};
    color: {CYAN};
    border-bottom: 2px solid {CYAN};
}}
QTabBar::tab:hover:!selected {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
}}

/* ---- Buttons ---- */
QPushButton {{
    background-color: {CYAN};
    color: {NAVY};
    border: none;
    padding: 6px 16px;
    border-radius: 6px;
    font-weight: bold;
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: {CYAN_LIGHT};
}}
QPushButton:pressed {{
    background-color: {CYAN_DARK};
}}
QPushButton:disabled {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_DISABLED};
}}
QPushButton:flat {{
    background-color: transparent;
    color: {CYAN};
    border: 1px solid {CYAN};
    border-radius: 6px;
}}
QPushButton:flat:hover {{
    background-color: rgba(0, 212, 255, 0.10);
}}

/* ---- Line / Text Inputs ---- */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CYAN};
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: {CYAN};
    selection-color: {NAVY};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {CYAN};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {NAVY_DARK};
    color: {TEXT_DISABLED};
}}

/* ---- Combo / Spin ---- */
QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {NAVY_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CYAN};
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {CYAN};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {CYAN};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CYAN};
    selection-background-color: {CYAN};
    selection-color: {NAVY};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {NAVY_LIGHT};
    border: none;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {CYAN};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {CYAN};
}}

/* ---- CheckBox / RadioButton ---- */
QCheckBox, QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 6px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {BORDER_CYAN};
    background-color: {NAVY_INPUT};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background-color: {CYAN};
    border-color: {CYAN};
}}
QCheckBox::indicator:hover {{
    border-color: {CYAN};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QRadioButton::indicator:checked {{
    background-color: {CYAN};
    border-color: {CYAN};
}}

/* ---- Labels ---- */
QLabel {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
}}

/* ---- GroupBox ---- */
QGroupBox {{
    border: 1px solid {BORDER_CYAN};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: {CYAN};
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {CYAN};
}}

/* ---- Scrollbars ---- */
QScrollBar:vertical {{
    background: {NAVY_DARK};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {CYAN};
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {CYAN_LIGHT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {NAVY_DARK};
    height: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: {CYAN};
    border-radius: 5px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {CYAN_LIGHT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ---- Tables ---- */
QTableView, QTableWidget {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    gridline-color: {BORDER_SUBTLE};
    border: 1px solid {BORDER_CYAN};
    border-radius: 6px;
    selection-background-color: rgba(0, 212, 255, 0.20);
    selection-color: {TEXT_PRIMARY};
    alternate-background-color: {NAVY_DARK};
}}
QHeaderView::section {{
    background-color: {NAVY_DARK};
    color: {CYAN};
    border: none;
    border-right: 1px solid {BORDER_CYAN};
    border-bottom: 1px solid {BORDER_CYAN};
    padding: 4px 8px;
    font-weight: bold;
}}
QHeaderView::section:hover {{
    background-color: {NAVY_LIGHT};
}}

/* ---- Lists / Trees ---- */
QListView, QListWidget, QTreeView, QTreeWidget {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CYAN};
    border-radius: 6px;
    alternate-background-color: {NAVY_DARK};
    selection-background-color: rgba(0, 212, 255, 0.20);
    selection-color: {TEXT_PRIMARY};
}}
QListView::item:hover, QListWidget::item:hover,
QTreeView::item:hover, QTreeWidget::item:hover {{
    background-color: rgba(0, 212, 255, 0.10);
}}

/* ---- Splitter ---- */
QSplitter::handle {{
    background: {BORDER_CYAN};
    border: none;
}}
QSplitter::handle:hover {{
    background: {CYAN};
}}
QSplitter::handle:vertical {{ height: 6px; }}
QSplitter::handle:horizontal {{ width: 6px; }}

/* ---- Progress Bar ---- */
QProgressBar {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CYAN};
    border-radius: 5px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {CYAN};
    border-radius: 4px;
}}

/* ---- Menus ---- */
QMenuBar {{
    background-color: {NAVY_DARK};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER_CYAN};
}}
QMenuBar::item:selected {{
    background-color: {NAVY_LIGHT};
    color: {CYAN};
}}
QMenu {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_CYAN};
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: rgba(0, 212, 255, 0.20);
    color: {CYAN};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER_CYAN};
    margin: 4px 8px;
}}

/* ---- Status Bar ---- */
QStatusBar {{
    background-color: {NAVY_DARK};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER_CYAN};
}}

/* ---- Tool Tips ---- */
QToolTip {{
    background-color: {NAVY_LIGHT};
    color: {TEXT_PRIMARY};
    border: 1px solid {CYAN};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ---- Sliders ---- */
QSlider::groove:horizontal {{
    background: {BORDER_CYAN};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {CYAN};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {CYAN};
    border-radius: 2px;
}}

/* ---- Frame / Panel ---- */
QFrame[frameShape="1"],
QFrame[frameShape="2"],
QFrame[frameShape="3"] {{
    border: 1px solid {BORDER_CYAN};
    border-radius: 4px;
}}

/* ---- Dock / Tool Widgets ---- */
QDockWidget {{
    color: {TEXT_PRIMARY};
    titlebar-close-icon: none;
}}
QDockWidget::title {{
    background: {NAVY_DARK};
    padding: 4px;
    border-bottom: 1px solid {BORDER_CYAN};
}}
"""


def apply_maestro_theme(app) -> None:
    """Apply the Maestro dark theme to a QApplication.

    Call this once in launch_gui() after creating the app but before
    creating any windows.

    Args:
        app: The QApplication instance
    """
    app.setStyleSheet(MAESTRO_QSS)
```

**Step 2: Commit**

```
feat: add gui/theme.py with Maestro brand colors and full QSS stylesheet
```

---

### Task 2: Bundle Maestro Fonts

**Files:**
- Create dir: `gui/resources/fonts/`
- Download: `Roboto-Regular.ttf`, `Roboto-Bold.ttf`, `Limelight-Regular.ttf`

**Step 1: Create the fonts directory**

```bash
mkdir -p /mnt/d/Documents/Code/GitHub/ImageAI/gui/resources/fonts
```

**Step 2: Download the fonts from Google Fonts**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI/gui/resources/fonts

# Roboto (body font — same as Maestro web)
curl -L "https://fonts.gstatic.com/s/roboto/v47/KFOmCnqEu92Fr1Mu4mxK.woff2" -o Roboto-Regular.ttf
curl -L "https://fonts.gstatic.com/s/roboto/v47/KFOlCnqEu92Fr1MmWUlfBBc4.woff2" -o Roboto-Bold.ttf

# Limelight (heading font — same as Maestro font-heading)
curl -L "https://fonts.gstatic.com/s/limelight/v20/XoHn2YH6T7-t_8cNAR4Jt9Yxlw.woff2" -o Limelight-Regular.ttf
```

> **Note:** If the woff2 URLs don't produce valid TTF files, download the fonts manually from https://fonts.google.com (Roboto, Limelight) and place the TTF files in `gui/resources/fonts/`. Verify with: `file gui/resources/fonts/*.ttf`

**Step 3: Create `gui/resources/__init__.py`** (empty, makes it a package)

```bash
touch /mnt/d/Documents/Code/GitHub/ImageAI/gui/resources/__init__.py
```

**Step 4: Commit**

```
feat: bundle Roboto and Limelight fonts for Maestro theme
```

---

### Task 3: Apply Theme in `gui/__init__.py`

**Files:**
- Modify: `gui/__init__.py:58-71`

**Step 1: Update `launch_gui()` to load fonts and apply the Maestro theme**

After the line `app = QApplication.instance() or QApplication(sys.argv)` (line 58) and before the `window = MainWindow()` call, add font loading and theme application.

Replace the existing `app.setStyle("Fusion")` block (lines 64-76) with:

```python
    # Load Maestro fonts
    from PySide6.QtGui import QFontDatabase
    from pathlib import Path as _Path
    _fonts_dir = _Path(__file__).parent / "resources" / "fonts"
    for _font_file in ["Roboto-Regular.ttf", "Roboto-Bold.ttf", "Limelight-Regular.ttf"]:
        _font_path = _fonts_dir / _font_file
        if _font_path.exists():
            QFontDatabase.addApplicationFont(str(_font_path))

    # Apply Maestro theme (dark navy + brand cyan)
    from gui.theme import apply_maestro_theme
    apply_maestro_theme(app)

    # Fusion style for proper mnemonic underline rendering
    from PySide6.QtWidgets import QStyleFactory
    available_styles = QStyleFactory.keys()
    if "Fusion" in available_styles:
        app.setStyle("Fusion")
    # Re-apply theme after style change (Fusion resets palette)
    apply_maestro_theme(app)
```

**Step 2: Commit**

```
feat: apply Maestro theme and load bundled fonts at app startup
```

---

### Task 4: Update `gui/common/splitter_style.py`

**Files:**
- Modify: `gui/common/splitter_style.py`

**Step 1: Replace the hardcoded colors with Maestro theme colors**

The current splitter style uses light-mode grays. Replace the entire file content:

```python
"""
Centralized splitter styling for consistent UI across the application.

This module provides a single source of truth for QSplitter styling.
Colors match the Maestro brand theme (gui/theme.py).
"""

from PySide6.QtWidgets import QSplitter
from gui.theme import BORDER_CYAN, CYAN


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
```

**Step 2: Commit**

```
feat: update splitter_style.py with Maestro colors
```

---

### Task 5: Update Inline Stylesheets in `gui/main_window.py`

**Files:**
- Modify: `gui/main_window.py`

These inline styles use light-mode hardcoded colors that will conflict with the dark global theme. Update each one.

**Step 1: Add theme import at top of file**

Find the existing imports block near line 1. After any existing `from gui.*` imports, add:

```python
from gui.theme import (
    CYAN, NAVY, NAVY_LIGHT, NAVY_INPUT, NAVY_DARK,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DISABLED,
    BORDER_CYAN, GREEN, RED, AMBER
)
```

**Step 2: Fix output image label (line ~1275)**

Change:
```python
self.output_image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
```
To:
```python
self.output_image_label.setStyleSheet(
    f"border: 1px solid {BORDER_CYAN}; background-color: {NAVY_LIGHT};"
)
```

**Step 3: Fix output text console (line ~1334)**

The `output_text` QTextEdit has a light background. Change:
```python
self.output_text.setStyleSheet("""
    ...background-color: ...; color: #cccccc;...
""")
```
To:
```python
self.output_text.setStyleSheet(
    f"background-color: {NAVY_DARK}; color: {TEXT_SECONDARY}; "
    f"border: 1px solid {BORDER_CYAN}; border-radius: 4px;"
)
```

**Step 4: Fix quick_setup info label (line ~1643)**

Change:
```python
quick_setup.setStyleSheet("QLabel { padding: 10px; background-color: #f5f5f5; }")
```
To:
```python
quick_setup.setStyleSheet(f"QLabel {{ padding: 10px; background-color: {NAVY_LIGHT}; }}")
```

**Step 5: Fix secondary hint/info labels (~lines 780, 1303, 1323, 1773, 1801, 1892, 1907, 2121, 2486)**

Batch-replace all `color: #888`, `color: #666`, `color: gray` inline styles:

For each of these, use the theme constant:
- `"color: #888; ..."` → `f"color: {TEXT_SECONDARY}; ..."`
- `"color: #666; ..."` → `f"color: {TEXT_MUTED}; ..."`
- `"color: gray"` → `f"color: {TEXT_SECONDARY}"`

**Step 6: Fix `_append_to_console` method (line ~313)**

The console uses hardcoded color strings. Update the default color:

```python
def _append_to_console(self, message: str, color: str = TEXT_SECONDARY, is_separator: bool = False):
```

And update the error color check:
```python
if color == "#ff6666" or color == RED:  # Red - Error
```

**Step 7: Fix the toggle button stylesheets (~lines 877, 1086, 3080, 7649)**

These are image_settings_toggle and ref_image_toggle QPushButtons styled inline. Update any `background-color: #f0f0f0` / `#f5f5f5` references to use `NAVY_LIGHT`, and any border colors to use `BORDER_CYAN`. The general pattern:

```python
self.image_settings_toggle.setStyleSheet(f"""
    QPushButton {{
        background-color: {NAVY_LIGHT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_CYAN};
        border-radius: 4px;
        padding: 4px 8px;
        text-align: left;
    }}
    QPushButton:hover {{
        background-color: {NAVY};
        border-color: {CYAN};
    }}
    QPushButton:checked {{
        background-color: rgba(0, 212, 255, 0.15);
        border-color: {CYAN};
    }}
""")
```

Apply the same pattern to `ref_image_toggle`.

**Step 8: Fix midjourney_command_display (line ~1289)**

Change any `background: #...` light colors to `NAVY_INPUT` and text color to `TEXT_PRIMARY`.

**Step 9: Fix ref_hint_label color (line ~772)**

Change `"color: #2196F3; font-size: 9pt;"` to `f"color: {CYAN}; font-size: 9pt;"` (already close to Maestro blue, cyan is better brand match).

**Step 10: Commit**

```
feat: update main_window.py inline styles to Maestro dark theme
```

---

### Task 6: Syntax Check All Modified Files

**Step 1: Run Python syntax check**

```bash
source /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/activate && python3 -c "
import py_compile
files = [
    'gui/theme.py',
    'gui/__init__.py',
    'gui/common/splitter_style.py',
    'gui/main_window.py',
]
for f in files:
    py_compile.compile(f, doraise=True)
    print(f'OK: {f}')
print('All files compile OK')
"
```

Expected output: `All files compile OK`

**Step 2: Run import check**

```bash
source /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/activate && python3 -c "
from gui.theme import apply_maestro_theme, NAVY, CYAN, MAESTRO_QSS
from gui.common.splitter_style import apply_splitter_style, SPLITTER_STYLESHEET
print('Imports OK')
print(f'Theme QSS length: {len(MAESTRO_QSS)} chars')
"
```

Expected:
```
Imports OK
Theme QSS length: <number> chars
```

**Step 3: Fix any errors and commit**

```
fix: resolve syntax/import issues from Maestro theme integration
```

---

## Quick Visual Reference

| Element | Before | After |
|---------|--------|-------|
| Window background | Light gray (Fusion default) | `#0A0E27` navy |
| Panels / cards | Light gray `#f5f5f5` | `#1A1E3F` navy-light |
| Buttons | Gray rounded | Cyan `#00D4FF` / navy text |
| Input fields | White | `#0D1130` dark input |
| Borders | Gray `#ccc` | Faint cyan `#1A4060` |
| Accent / focus | Blue `#2196F3` | Cyan `#00D4FF` |
| Text primary | Near-black | White |
| Text secondary | `#666` / `#888` | `#9CA3AF` gray-400 |
| Scrollbars | OS default | Cyan thumb on navy track |
| Tab active | OS default | Cyan underline |
| Status bar | OS default | Navy-dark / cyan border |

## Summary

| Task | Agent | Description | Size |
|------|-------|-------------|------|
| 1 | A | Create `gui/theme.py` | Large — full QSS |
| 2 | B | Bundle Roboto + Limelight fonts | Small |
| 3 | C | Apply theme in `gui/__init__.py` | Small |
| 4 | D | Update `splitter_style.py` | Small |
| 5 | E | Update `main_window.py` inline styles | Medium |
| 6 | F | Syntax + import checks | Small |
