"""Iteration-history manager for the layout designer."""
import uuid
from datetime import datetime
from typing import List, Optional

from core.layout.models import DocumentSpec, Snapshot
from core.layout import schema


class History:
    """Append/browse/restore layout snapshots stored on a DocumentSpec."""

    def __init__(self, document: DocumentSpec):
        self.document = document
        # The snapshot the next append should parent to. None → fall back to the
        # latest snapshot (linear history). Set by branch_from() after a restore
        # so a design that continues from a restored point records the real
        # branch topology rather than re-parenting to the timeline's tail.
        self._current_id: Optional[str] = None

    def snapshots(self) -> List[Snapshot]:
        return self.document.history

    def get(self, snapshot_id: str) -> Optional[Snapshot]:
        for s in self.document.history:
            if s.id == snapshot_id:
                return s
        return None

    def append(self, prompt: str, *, snapshot_id: Optional[str] = None,
               timestamp: Optional[str] = None, parent_id: Optional[str] = None) -> Snapshot:
        doc_dict = schema.document_to_dict(self.document)
        doc_dict.pop("history", None)  # never nest history inside a snapshot
        if parent_id is None:
            if self._current_id is not None:
                parent_id = self._current_id
            elif self.document.history:
                parent_id = self.document.history[-1].id
        snap = Snapshot(
            id=snapshot_id or uuid.uuid4().hex[:8],
            parent_id=parent_id,
            timestamp=timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            prompt=prompt,
            document=doc_dict,
        )
        self.document.history.append(snap)
        self._current_id = snap.id  # subsequent appends chain from this snapshot
        return snap

    def branch_from(self, snapshot_id: str) -> None:
        """Record the snapshot a restore branched from, so the next append
        parents to it (faithful branch topology, not the timeline's tail)."""
        self._current_id = snapshot_id

    def restore(self, snapshot_id: str) -> DocumentSpec:
        snap = self.get(snapshot_id)
        if snap is None:
            raise KeyError(f"No snapshot {snapshot_id!r}")
        restored = schema.document_from_dict(snap.document)
        restored.history = list(self.document.history)  # keep the timeline
        return restored
