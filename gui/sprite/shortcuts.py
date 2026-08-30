"""Keyboard shortcuts for the Sprite tab (design §1.5).

Design §1.5's "Where" column scopes most rows to one working area, not the
whole tab: Space, `,`, `.`, Home, End and L to the preview player; Delete
and Ctrl+D to the frame strip; `+`/`-`/`=`/Ctrl+0/G to the pixel view. The
pixel view lives inside the preview player (deviation 2), so its rows are
scoped to the player widget too. Only Ctrl+Z/Ctrl+Y (and the additive
Ctrl+Shift+Z) are tab-wide, matching undo/redo's tab-level meaning. Every
`QShortcut` uses `WidgetWithChildrenShortcut`, scoped to its owner widget, so
a shortcut fires only when the focus is inside its own working area and a
focused button or text field elsewhere in the tab still receives its own
keys (Qt gives the focused widget the ShortcutOverride first). Ctrl+Enter is
bound per panel/dialog with `bind_primary_action`, not here.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Attribute on `tab` that owns the callable named by a row's "owner.method" target.
OWNER_ATTRS = {
    "strip": "frame_strip",
    "player": "preview_player",
    "view": "pixel_view",
    "workspace": "frames_workspace",
}

# Attribute on `tab` that owns the QShortcut itself (its scoping widget, design
# §1.5's "Where" column). `view` shares the player's widget because PixelView
# lives inside PreviewPlayer (deviation 2). `workspace` (undo/redo) has no
# entry: `install_shortcuts` parents those directly on the tab, tab-wide.
SHORTCUT_WIDGET_ATTRS: Dict[str, Optional[str]] = {
    "strip": "frame_strip",
    "player": "preview_player",
    "view": "preview_player",
    "workspace": None,
}

SHORTCUT_TABLE: Tuple[Tuple[str, str, str], ...] = (
    ("Space", "player.toggle_play", "Play / pause"),
    (",", "player.step_back", "Previous frame"),
    (".", "player.step_forward", "Next frame"),
    ("Home", "player.first", "First frame"),
    ("End", "player.last", "Last frame"),
    ("Delete", "strip.delete_selected", "Delete selected frame(s)"),
    ("Ctrl+D", "strip.duplicate_selected", "Duplicate frame"),
    ("Ctrl+Z", "workspace.undo", "Undo"),
    ("Ctrl+Y", "workspace.redo", "Redo"),
    ("Ctrl+Shift+Z", "workspace.redo", "Redo"),
    ("+", "view.zoom_in", "Zoom in"),
    ("=", "view.zoom_in", "Zoom in (unshifted +)"),
    ("-", "view.zoom_out", "Zoom out"),
    ("Ctrl+0", "view.zoom_reset", "Zoom 100 %"),
    ("G", "view.toggle_grid", "Toggle pixel grid"),
    ("L", "player.cycle_mode", "Cycle loop mode"),
)


def resolve_target(tab: Any, dotted: str) -> Callable[[], Any]:
    owner, _, method = dotted.partition(".")
    attr = OWNER_ATTRS[owner]           # KeyError on an unknown owner is a programming error
    return getattr(getattr(tab, attr), method)


def _shortcut_parent(tab: QWidget, owner: str) -> QWidget:
    """The widget that scopes an owner's shortcuts (design §1.5's "Where" column)."""
    attr = SHORTCUT_WIDGET_ATTRS[owner]  # KeyError on an unknown owner is a programming error
    return getattr(tab, attr) if attr else tab


def install_shortcuts(tab: QWidget) -> Dict[str, QShortcut]:
    """Bind the §1.5 table on `tab`; a second call disables the previous set."""
    previous = getattr(tab, "_sprite_shortcuts", None)
    if previous:
        for shortcut in previous.values():
            shortcut.setEnabled(False)
            shortcut.setParent(None)
            shortcut.deleteLater()
    shortcuts: Dict[str, QShortcut] = {}
    for key, dotted, description in SHORTCUT_TABLE:
        owner, _, _ = dotted.partition(".")
        slot = resolve_target(tab, dotted)
        parent = _shortcut_parent(tab, owner)
        shortcut = QShortcut(QKeySequence(key), parent)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.setWhatsThis(description)
        shortcut.activated.connect(slot)
        shortcuts[key] = shortcut
    tab._sprite_shortcuts = shortcuts
    logger.debug("Sprite shortcuts installed: %s", ", ".join(shortcuts))
    return shortcuts
