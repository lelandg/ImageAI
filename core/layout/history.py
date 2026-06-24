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
        if parent_id is None and self.document.history:
            parent_id = self.document.history[-1].id
        snap = Snapshot(
            id=snapshot_id or uuid.uuid4().hex[:8],
            parent_id=parent_id,
            timestamp=timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            prompt=prompt,
            document=doc_dict,
        )
        self.document.history.append(snap)
        return snap

    def restore(self, snapshot_id: str) -> DocumentSpec:
        snap = self.get(snapshot_id)
        if snap is None:
            raise KeyError(f"No snapshot {snapshot_id!r}")
        restored = schema.document_from_dict(snap.document)
        restored.history = list(self.document.history)  # keep the timeline
        return restored
