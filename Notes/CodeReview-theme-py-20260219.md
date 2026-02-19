# Code Review: gui/theme.py — Maestro Brand Theme Module

**Reviewed:** 2026-02-19 09:22
**Reviewer:** Claude Code (code-reviewer agent)
**File:** `/mnt/d/Documents/Code/GitHub/ImageAI/gui/theme.py`
**Plan:** `Plans/2026-02-19-maestro-ui-redesign.md` — Task 1
**Base SHA:** dd3b725 (file not yet committed)

---

## Summary

The implementation is solid, syntactically correct, and meaningfully improves on the plan's template in several areas. All 24 public symbols import cleanly. The QSS is 12,049 characters covering 87 CSS rule blocks with 152 hex color values — all well-formed. No PySide6 imports at module level (correct). The file is ready to integrate.

There are no critical issues. Two important issues and four suggestions are documented below.

---

## What Was Done Well

- **Clean organization.** Color constants are grouped into five labeled sections (Background, Accent, Spectrum, Text, Border) with inline hex comments. Very easy to scan.
- **Expanded input widget rules.** The plan combined `QLineEdit`, `QTextEdit`, and `QPlainTextEdit` into one rule block. The implementation correctly splits them, allowing `QPlainTextEdit` to receive `FONT_MONO` — an improvement the plan did not specify.
- **Complete scrollbar track styling.** The plan omitted `add-page`/`sub-page` pseudo-elements. The implementation includes them, preventing OS-native track colors from bleeding through.
- **Better `QComboBox::drop-down` rule.** The implementation adds `subcontrol-origin`, `subcontrol-position`, and per-corner `border-radius` values, which are required for reliable cross-platform rendering.
- **`QTreeView::branch` rule added.** Prevents the default branch indicator background from leaking through in dark mode.
- **`QFrame` frame shapes.** Correct integer values used (1=Box, 4=HLine, 5=VLine, 6=StyledPanel). The plan used shapes 1–3; the implementation uses 1, 4, 5, 6, which are the shapes that actually appear in this application.
- **Module docstring.** Comprehensive, includes usage example, lists all exports by category.
- **Zero module-level PySide6 imports.** The theme file can be imported without Qt installed, which enables use in tests and CLI contexts.

---

## Issues

### IMPORTANT — Font fallback chain missing

**File:** `/mnt/d/Documents/Code/GitHub/ImageAI/gui/theme.py`, line 80
**File:** `/mnt/d/Documents/Code/GitHub/ImageAI/gui/theme.py`, line 63

The plan's `QWidget` base rule specified:
```css
font-family: "Roboto", "Segoe UI", sans-serif;
```

The implementation uses only the `FONT_BODY` constant:
```css
font-family: Roboto;
```

If the Roboto font file is not loaded (Task 2 fonts are missing, corrupted, or on a platform where font loading fails), Qt falls back to the system default — which on Linux is often DejaVu or Ubuntu, and on Windows is Arial. The result looks notably different from the intended design. The constant itself should embed the fallback chain:

```python
FONT_BODY = "Roboto, 'Segoe UI', sans-serif"
```

This is a one-line fix to the constant. No changes to the QSS body are needed.

---

### IMPORTANT — Font size units (px vs pt) break high-DPI scaling

**File:** `/mnt/d/Documents/Code/GitHub/ImageAI/gui/theme.py`, lines 82 and 616

The plan specified `font-size: 10pt`. The implementation uses `font-size: 13px` (base) and `font-size: 12px` (tooltip).

Pixel sizes (`px`) are physical screen pixels and do not scale with Qt's device-pixel-ratio (DPI) setting. Point sizes (`pt`) scale automatically. On a 4K display with `QT_SCALE_FACTOR=2` or a HiDPI laptop running at 150%, the `13px` body font renders at half the intended visual size.

`10pt` at 96 DPI equals approximately 13.3px — so the intent is correct, but the unit is wrong for a cross-platform desktop app.

Recommendation: use `pt` units.

```python
# In QWidget base rule:
font-size: 10pt;

# In QToolTip:
font-size: 9pt;
```

---

### Suggestion — Scrollbar handle uses subdued color (design deviation)

**File:** `/mnt/d/Documents/Code/GitHub/ImageAI/gui/theme.py`, lines 406–414

The plan specified the scrollbar handle should be `CYAN` (#00D4FF) with `CYAN_LIGHT` on hover, consistent with a high-visibility Maestro accent. The implementation uses `BORDER_SUBTLE` (#1E2449) as the rest state and `TEXT_MUTED` (#6B7280) on hover — a much more subdued style:

```python
# Plan
background-color: {CYAN};  # handle
background-color: {CYAN_LIGHT};  # hover

# Implementation
background-color: {BORDER_SUBTLE};  # handle — very dark, barely visible
background-color: {TEXT_MUTED};  # hover — gray
```

This is a deliberate design choice (subtler scrollbars are a valid preference) but it deviates from the brand spec. It is worth a conscious decision from the team. Flagging for awareness.

---

### Suggestion — `QCheckBox::indicator:checked` has no checkmark

**File:** `/mnt/d/Documents/Code/GitHub/ImageAI/gui/theme.py`, lines 339–343

```css
QCheckBox::indicator:checked {
    background-color: #00D4FF;
    border-color: #00D4FF;
    image: none;
}
```

`image: none` explicitly clears Qt's default checkmark glyph. The checked state is a solid cyan square with no visual indicator of the check itself. Users may not be able to distinguish checked from a selected (focused) unchecked indicator without color alone. Consider using a Unicode checkmark via an SVG `image: url(...)` or removing the `image: none` line to let Qt render its built-in tick on the cyan background.

---

### Suggestion — `__all__` not declared

**File:** `/mnt/d/Documents/Code/GitHub/ImageAI/gui/theme.py`

The module has no `__all__` list. `from gui.theme import *` would export all 24 public names including the `apply_maestro_theme` function. Declaring `__all__` makes the public API explicit and prevents accidental re-export of implementation details if helper functions are added later.

```python
__all__ = [
    # Colors — backgrounds
    "NAVY", "NAVY_LIGHT", "NAVY_DARK", "NAVY_INPUT",
    # Colors — accent
    "CYAN", "CYAN_LIGHT", "CYAN_DARK",
    # Colors — spectrum
    "GREEN", "AMBER", "RED", "MAGENTA", "PURPLE", "BLUE",
    # Colors — text
    "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED", "TEXT_DISABLED",
    # Colors — borders
    "BORDER_SUBTLE", "BORDER_CYAN",
    # Fonts
    "FONT_BODY", "FONT_HEADING", "FONT_MONO",
    # Stylesheet
    "MAESTRO_QSS",
    # Function
    "apply_maestro_theme",
]
```

---

### Suggestion — `QMainWindow` background uses `NAVY_DARK` instead of `NAVY`

**File:** `/mnt/d/Documents/Code/GitHub/ImageAI/gui/theme.py`, lines 84–86

The plan specified `QMainWindow` background as `NAVY` (#0A0E27). The implementation uses `NAVY_DARK` (#050711), which is the deepest background. The effect is a very slightly darker chrome around the window edge. This is a minor visual deviation and may actually look better (provides depth contrast between the window chrome and the content area), but it differs from the plan. Document the intent or revert to match.

---

## Plan Alignment Summary

| Plan Requirement | Status |
|---|---|
| 19 color constants | Implemented — 19 colors + 3 font constants = 22 (plus `MAESTRO_QSS` and `apply_maestro_theme`) |
| All standard Qt widgets styled | Implemented — 87 CSS rule blocks |
| No PySide6 module-level imports | Implemented correctly |
| `apply_maestro_theme(app)` function | Implemented correctly |
| Font size `10pt` in base | Deviated — uses `13px` (IMPORTANT) |
| Font fallback chain | Deviated — `FONT_BODY` has no fallbacks (IMPORTANT) |
| Scrollbar handle = CYAN | Deviated — uses `BORDER_SUBTLE` (Suggestion) |
| `QMainWindow` bg = `NAVY` | Deviated — uses `NAVY_DARK` (Suggestion) |
| QSS ~12K chars | Matches — 12,049 chars |

---

## Overall Verdict

**Ready to integrate with two fixes recommended before committing.**

The font fallback and px-vs-pt issues are worth addressing now since they affect all downstream tasks (Tasks 3–6 all build on this file). Both are single-line fixes. The scrollbar and checkbox suggestions can be deferred to a polish pass.
