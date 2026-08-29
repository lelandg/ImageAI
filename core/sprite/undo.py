"""Snapshot undo for destructive frame-list edits (design section 1.4).

Pipeline re-runs never enter this stack: they are non-destructive by the
stage cache. Only frame-list edits (delete, reorder, duplicate, insert,
duration edit, retouch, override edit) push a snapshot before they act.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .models import FrameMeta


@dataclass(frozen=True)
class FrameListSnapshot:
    action_id: str
    frames: Tuple[FrameMeta, ...]
    label: str

    @classmethod
    def capture(cls, action_id: str, frames, label: str) -> "FrameListSnapshot":
        """Deep-copy ``frames`` so later edits cannot reach into the snapshot."""
        return cls(action_id=action_id, frames=tuple(copy.deepcopy(list(frames))), label=label)


class SnapshotStack:
    """A bounded undo/redo stack of frame-list snapshots."""

    def __init__(self, depth: int = 50) -> None:
        if depth < 1:
            raise ValueError("depth must be at least 1")
        self._depth = depth
        self._undo: List[FrameListSnapshot] = []
        self._redo: List[FrameListSnapshot] = []

    def push(self, snap: FrameListSnapshot) -> None:
        """Record the state *before* a destructive edit. Clears redo."""
        self._undo.append(snap)
        if len(self._undo) > self._depth:
            del self._undo[0]
        self._redo.clear()

    def undo(self, current: FrameListSnapshot) -> Optional[FrameListSnapshot]:
        """Return the state to restore, and park ``current`` for redo."""
        if not self._undo:
            return None
        self._redo.append(current)
        return self._undo.pop()

    def redo(self) -> Optional[FrameListSnapshot]:
        """Return the state to restore, and move it back onto the undo stack."""
        if not self._redo:
            return None
        snap = self._redo.pop()
        self._undo.append(snap)
        return snap

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
