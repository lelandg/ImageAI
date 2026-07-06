"""
Shared dialog conventions: splitters, primary-action hotkeys, default buttons,
and exit-path cleanup.

Standards implemented here (see Plans/DialogUX-TLC-Plan.md):
- Every QSplitter is visible (styled), non-collapsible, and persisted under a
  named QSettings key — never looked up via findChildren(QSplitter)[0].
- The primary action of a dialog/tab is bound to BOTH Ctrl+Return and
  Ctrl+Enter (keypad) — always together, retargeted together.
- Exactly one default button per dialog; utility buttons never steal Enter.
- Cleanup (worker shutdown, settings/geometry saves) runs on EVERY exit path
  (OK, Cancel, Escape, title-bar X), not only in closeEvent.
"""

from PySide6.QtCore import QObject, QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QPushButton, QSplitter, QWidget

from .splitter_style import DEFAULT_HANDLE_WIDTH, apply_splitter_style


def standard_splitter(orientation, parent=None, *, handle_width=DEFAULT_HANDLE_WIDTH) -> QSplitter:
    """Create a QSplitter with the canonical style and non-collapsible panes."""
    splitter = QSplitter(orientation, parent)
    apply_splitter_style(splitter, handle_width)
    splitter.setChildrenCollapsible(False)
    return splitter


def persist_splitter(settings: QSettings, key: str, splitter: QSplitter) -> None:
    """Save a splitter's state under an explicit named key."""
    settings.setValue(key, splitter.saveState())


def restore_splitter(settings: QSettings, key: str, splitter: QSplitter) -> bool:
    """Restore a splitter's state; returns False if no saved state exists.

    Callers apply their hardcoded setSizes() default only when this returns
    False.
    """
    state = settings.value(key)
    if state is not None and splitter.restoreState(state):
        return True
    return False


class PrimaryAction(QObject):
    """Ctrl+Return and Ctrl+Enter bound to the same slot, always together.

    Qt reports numeric-keypad Enter as Qt.Key_Enter, which 'Ctrl+Return' does
    not match — binding only one sequence leaves keyboards inconsistent.
    """

    def __init__(self, widget: QWidget, slot, context=Qt.WindowShortcut):
        super().__init__(widget)
        self._slot = slot
        self._shortcuts = []
        for sequence in ("Ctrl+Return", "Ctrl+Enter"):
            shortcut = QShortcut(QKeySequence(sequence), widget)
            shortcut.setContext(context)
            shortcut.activated.connect(self._activated)
            self._shortcuts.append(shortcut)

    def _activated(self):
        if self._slot is not None:
            self._slot()

    def retarget(self, slot) -> None:
        """Point both shortcuts at a new slot (e.g. generate -> accept)."""
        self._slot = slot

    def set_enabled(self, enabled: bool) -> None:
        for shortcut in self._shortcuts:
            shortcut.setEnabled(enabled)


def bind_primary_action(widget: QWidget, slot, *, context=Qt.WindowShortcut) -> PrimaryAction:
    """Bind the dialog's primary action to Ctrl+Return AND Ctrl+Enter."""
    return PrimaryAction(widget, slot, context)


def set_default_button(dialog: QWidget, button: QPushButton, *, focus: bool = True) -> None:
    """Make `button` the single default button of `dialog`.

    Clears default/auto-default on every other QPushButton so Enter cannot
    land on a utility button, and (optionally) gives the default button
    initial focus. Dialogs whose primary input should take focus instead pass
    focus=False and call setFocus() on that input.
    """
    for other in dialog.findChildren(QPushButton):
        other.setAutoDefault(False)
        other.setDefault(False)
    button.setAutoDefault(True)
    button.setDefault(True)
    if focus:
        button.setFocus()


class DialogCleanupMixin:
    """Run cleanup on every dialog exit path, exactly once per showing.

    QDialog.accept()/reject() do NOT trigger closeEvent, so cleanup that only
    lives there is skipped on OK/Cancel/Escape. This mixin routes done() and
    closeEvent through an idempotent hook.

    Usage:
        class MyDialog(DialogCleanupMixin, QDialog):
            def on_dialog_close(self):
                self._stop_worker()
                self.save_settings()
    """

    def on_dialog_close(self):
        """Override: worker shutdown, QSettings/geometry/splitter saves, etc."""

    def _run_dialog_cleanup(self):
        if getattr(self, "_dialog_cleanup_done", False):
            return
        self._dialog_cleanup_done = True
        self.on_dialog_close()

    def showEvent(self, event):
        self._dialog_cleanup_done = False
        super().showEvent(event)

    def done(self, result):
        self._run_dialog_cleanup()
        super().done(result)

    def closeEvent(self, event):
        self._run_dialog_cleanup()
        super().closeEvent(event)
