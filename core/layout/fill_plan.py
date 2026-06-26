"""Ordered plan for filling layout image regions via the Image tab (Phase 5b).

Pure sequencing state so the MainWindow handoff/queue logic is testable without
a GUI: a list of region payloads with a cursor. Single "Send to Image" is just a
one-element plan; "Fill all regions" is a many-element plan — both advance the
same way after each generation places its result.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class FillPlan:
    payloads: List[Dict] = field(default_factory=list)
    index: int = 0  # cursor: the region currently being generated

    def current(self) -> Optional[Dict]:
        if 0 <= self.index < len(self.payloads):
            return self.payloads[self.index]
        return None

    def current_region_id(self) -> Optional[str]:
        cur = self.current()
        return cur.get("region_id") if cur else None

    def advance(self) -> Optional[Dict]:
        """Move to the next region; return it, or None when the plan is done."""
        self.index += 1
        return self.current()

    def done(self) -> bool:
        return self.index >= len(self.payloads)

    def progress(self) -> Tuple[int, int]:
        """(1-based position of the current region, total). (0, 0) if empty."""
        total = len(self.payloads)
        if total == 0:
            return (0, 0)
        return (min(self.index + 1, total), total)
