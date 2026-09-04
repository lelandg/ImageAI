"""Per-action undo/redo for the sprite frame list (design section 1.4).

The pipeline is non-destructive, so only list edits enter the stack: delete,
reorder, duplicate, insert, duration edit, override edit, retouch. Each edit
pushes a deep copy of the list *before* the change.
"""
from __future__ import annotations

import copy
import logging
from typing import Dict, List, Optional, Sequence

from PySide6.QtCore import QObject, Signal

from core.sprite.models import FrameMeta
from core.sprite.undo import FrameListSnapshot, SnapshotStack

logger = logging.getLogger(__name__)


class UndoController(QObject):
    """One `SnapshotStack` per action id; emits `stateChanged(can_undo, can_redo)`."""

    stateChanged = Signal(bool, bool)

    def __init__(self, depth: int = 50, parent=None):
        super().__init__(parent)
        self._depth = depth
        self._stacks: Dict[str, SnapshotStack] = {}
        self._active: Optional[str] = None

    # ----- stacks -----------------------------------------------------
    def stack(self, action_id: str) -> SnapshotStack:
        stack = self._stacks.get(action_id)
        if stack is None:
            stack = SnapshotStack(depth=self._depth)
            self._stacks[action_id] = stack
        return stack

    @property
    def active_action(self) -> Optional[str]:
        return self._active

    def set_active(self, action_id: Optional[str]) -> None:
        self._active = action_id
        self._emit_state(action_id)

    def can_undo(self, action_id: Optional[str] = None) -> bool:
        action_id = action_id or self._active
        return bool(action_id) and self.stack(action_id).can_undo

    def can_redo(self, action_id: Optional[str] = None) -> bool:
        action_id = action_id or self._active
        return bool(action_id) and self.stack(action_id).can_redo

    def clear(self, action_id: str) -> None:
        self._stacks[action_id] = SnapshotStack(depth=self._depth)
        self._emit_state(action_id)

    # ----- operations -------------------------------------------------
    def snapshot(self, action_id: str, frames: Sequence[FrameMeta], label: str) -> FrameListSnapshot:
        snap = FrameListSnapshot.capture(action_id, frames, label)
        self.stack(action_id).push(snap)
        logger.debug("Sprite undo: snapshot '%s' for action %s (%d frames)",
                     label, action_id, len(snap.frames))
        self._emit_state(action_id)
        return snap

    def undo(self, action_id: str, current: Sequence[FrameMeta]) -> Optional[List[FrameMeta]]:
        stack = self.stack(action_id)
        if not stack.can_undo:
            return None
        now = FrameListSnapshot.capture(action_id, current, "current")
        snap = stack.undo(now)
        self._emit_state(action_id)
        if snap is None:
            return None
        logger.info("Sprite undo: '%s' (action %s)", snap.label, action_id)
        return self._copy(snap.frames)

    def redo(self, action_id: str) -> Optional[List[FrameMeta]]:
        stack = self.stack(action_id)
        if not stack.can_redo:
            return None
        snap = stack.redo()
        self._emit_state(action_id)
        if snap is None:
            return None
        logger.info("Sprite redo: '%s' (action %s)", snap.label, action_id)
        return self._copy(snap.frames)

    # ----- internals --------------------------------------------------
    @staticmethod
    def _copy(frames: Sequence[FrameMeta]) -> List[FrameMeta]:
        """Deep-copy frames read out of a stored snapshot for the caller to own."""
        return copy.deepcopy(list(frames))

    def _emit_state(self, action_id: Optional[str]) -> None:
        if not action_id:
            self.stateChanged.emit(False, False)
            return
        stack = self.stack(action_id)
        self.stateChanged.emit(stack.can_undo, stack.can_redo)
