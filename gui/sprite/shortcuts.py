"""Keyboard shortcuts for the Sprite tab (design §1.5).

Every shortcut is scoped to the tab (`WidgetWithChildrenShortcut`), so other
tabs keep their own keys and text fields inside the tab still receive plain
characters (Qt gives the focused editor the ShortcutOverride first).
Ctrl+Enter is bound per panel/dialog with `bind_primary_action`, not here.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

OWNER_ATTRS = {
    "strip": "frame_strip",
    "player": "preview_player",
    "view": "pixel_view",
    "workspace": "frames_workspace",
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
        slot = resolve_target(tab, dotted)
        shortcut = QShortcut(QKeySequence(key), tab)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.setWhatsThis(description)
        shortcut.activated.connect(slot)
        shortcuts[key] = shortcut
    tab._sprite_shortcuts = shortcuts
    logger.debug("Sprite shortcuts installed: %s", ", ".join(shortcuts))
    return shortcuts
