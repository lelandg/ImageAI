from pathlib import Path

from core.sprite.models import FrameMeta
from core.sprite.undo import FrameListSnapshot, SnapshotStack


def _frames(n):
    return [FrameMeta(name=f"f{i}", source_path=Path(f"/f/{i}.png"), frame=(0, 0, 8, 8)) for i in range(n)]


def test_capture_deep_copies_the_frames():
    frames = _frames(2)
    snap = FrameListSnapshot.capture("a1", frames, "delete frame 1")
    frames[0].duration_ms = 999
    assert snap.frames[0].duration_ms == 100
    assert snap.label == "delete frame 1"
    assert isinstance(snap.frames, tuple)


def test_undo_returns_previous_state_and_parks_current_for_redo():
    stack = SnapshotStack()
    before = FrameListSnapshot.capture("a1", _frames(3), "before delete")
    stack.push(before)
    assert stack.can_undo and not stack.can_redo
    current = FrameListSnapshot.capture("a1", _frames(2), "after delete")
    restored = stack.undo(current)
    assert restored is before
    assert not stack.can_undo and stack.can_redo
    assert stack.redo() is current
    assert stack.can_undo and not stack.can_redo


def test_redo_then_undo_restores_the_state_before_the_first_undo():
    """I2 regression: a second undo after a redo must not oscillate on the
    redo target -- it has to restore the state the redo left behind."""
    stack = SnapshotStack()
    state_a = FrameListSnapshot.capture("a1", _frames(1), "a")
    stack.push(state_a)
    state_b = FrameListSnapshot.capture("a1", _frames(2), "b")
    restored = stack.undo(state_b)
    assert restored is state_a
    redone = stack.redo()
    assert redone is state_b
    restored_again = stack.undo(redone)
    assert restored_again is state_a


def test_push_clears_redo():
    stack = SnapshotStack()
    stack.push(FrameListSnapshot.capture("a", _frames(1), "one"))
    stack.undo(FrameListSnapshot.capture("a", _frames(0), "now"))
    assert stack.can_redo
    stack.push(FrameListSnapshot.capture("a", _frames(2), "two"))
    assert not stack.can_redo


def test_depth_drops_the_oldest_snapshot():
    stack = SnapshotStack(depth=2)
    snaps = [FrameListSnapshot.capture("a", _frames(i), str(i)) for i in range(3)]
    for snap in snaps:
        stack.push(snap)
    current = FrameListSnapshot.capture("a", _frames(9), "cur")
    assert stack.undo(current) is snaps[2]
    assert stack.undo(snaps[2]) is snaps[1]
    assert stack.undo(snaps[1]) is None


def test_empty_stack_returns_none():
    stack = SnapshotStack()
    assert stack.undo(FrameListSnapshot.capture("a", [], "x")) is None
    assert stack.redo() is None
