from core.layout.models import DocumentSpec, PageSpec, Region
from core.layout.history import History
from gui.layout.history_window import HistoryWindow


def _history_with(n):
    doc = DocumentSpec(title="D", pages=[PageSpec(page_size_px=(100, 100),
                       regions=[Region(id="r1", kind="text", text="v")])])
    h = History(doc)
    for i in range(n):
        h.append(f"step {i}", snapshot_id=f"s{i}", timestamp=f"t{i}")
    return h


def test_window_lists_snapshots(qapp):
    win = HistoryWindow(_history_with(3))
    assert win.list_widget.count() == 3


def test_restore_emits_snapshot_id(qapp):
    win = HistoryWindow(_history_with(2))
    got = []
    win.restoreRequested.connect(lambda sid: got.append(sid))
    win.list_widget.setCurrentRow(0)
    win._on_restore()  # internal slot
    assert got == ["s0"]
