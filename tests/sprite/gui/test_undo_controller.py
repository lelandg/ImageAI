from pathlib import Path

from gui.sprite.undo_controller import UndoController
from gui_synthetic import make_frames


def test_snapshot_then_undo_returns_previous_list(qapp, tmp_path):
    frames = make_frames(tmp_path, 3)
    ctl = UndoController()
    states = []
    ctl.stateChanged.connect(lambda u, r: states.append((u, r)))

    ctl.snapshot("a", frames, "delete frame 2")
    assert ctl.can_undo("a") and not ctl.can_redo("a")
    assert states[-1] == (True, False)

    edited = frames[:2]
    restored = ctl.undo("a", edited)
    assert restored is not None
    assert [f.name for f in restored] == [f.name for f in frames]
    assert ctl.can_redo("a")


def test_undo_returns_deep_copies(qapp, tmp_path):
    frames = make_frames(tmp_path, 2)
    ctl = UndoController()
    ctl.snapshot("a", frames, "x")
    restored = ctl.undo("a", frames)
    restored[0].duration_ms = 999
    assert frames[0].duration_ms == 100  # the original list is untouched


def test_redo_restores_edited_list(qapp, tmp_path):
    frames = make_frames(tmp_path, 3)
    ctl = UndoController()
    ctl.snapshot("a", frames, "delete")
    edited = frames[:2]
    ctl.undo("a", edited)
    again = ctl.redo("a")
    assert again is not None
    assert [f.name for f in again] == [f.name for f in edited]


def test_stacks_are_per_action(qapp, tmp_path):
    frames = make_frames(tmp_path, 2)
    ctl = UndoController()
    ctl.snapshot("a", frames, "x")
    assert ctl.can_undo("a")
    assert not ctl.can_undo("b")
    assert ctl.undo("b", frames) is None


def test_set_active_emits_state_for_that_action(qapp, tmp_path):
    frames = make_frames(tmp_path, 2)
    ctl = UndoController()
    ctl.snapshot("a", frames, "x")
    states = []
    ctl.stateChanged.connect(lambda u, r: states.append((u, r)))
    ctl.set_active("b")
    assert states[-1] == (False, False)
    ctl.set_active("a")
    assert states[-1] == (True, False)
    assert ctl.active_action == "a"


def test_clear_drops_history(qapp, tmp_path):
    frames = make_frames(tmp_path, 2)
    ctl = UndoController()
    ctl.snapshot("a", frames, "x")
    ctl.clear("a")
    assert not ctl.can_undo("a") and not ctl.can_redo("a")
