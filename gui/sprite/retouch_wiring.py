"""Connect FrameStrip.retouchRequested to the RetouchDialog and apply the result with undo."""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Optional

from core.sprite.project import ActionCard
from gui.sprite.retouch_dialog import RetouchDialog

logger = logging.getLogger(__name__)


def apply_retouch(tab, action: ActionCard, index: int, new_path: Path) -> None:
    """Repoint one frame in a copied list through FramesWorkspace.apply_frames (snapshot + set + refresh).

    The copy matters: apply_frames snapshots the current list for undo before it installs the
    new one. apply_frames already saves the project (SpriteTab.save_current_project()) and logs
    the frame-count change, so this does not save or log a second time.

    The index is re-validated here. QDialog.exec() blocks user input but still delivers queued
    events, so a pipeline worker can replace action.frames with a shorter list while the modal
    retouch dialog is up. A stale index must never raise IndexError out of a Qt slot
    (final review, Important 8).
    """
    if not (0 <= index < len(action.frames)):
        logger.warning("retouch: frame %d is gone from '%s' (%d frame(s) now)",
                       index + 1, action.name, len(action.frames))
        tab.console.log(f"Retouch not applied: frame {index + 1} no longer exists on "
                        f"'{action.name}'.", "WARNING")
        return
    frames = copy.deepcopy(action.frames)
    frames[index].source_path = Path(new_path)
    tab.frames_workspace.apply_frames(action.id, frames, f"retouch {index + 1}")
    tab.console.log(f"Frame {index + 1} retouched -> {Path(new_path).name}", "SUCCESS")
    logger.info("retouch applied: action=%s frame=%d -> %s", action.name, index + 1, new_path)


def open_retouch_dialog(tab, index: int, *, exec_dialog: bool = True) -> Optional[RetouchDialog]:
    # The retouch is refused while the processing panel runs. The pipeline replaces
    # action.frames while the modal dialog holds one index, and the retouch result is then
    # applied to a list the pipeline overwrites (final review, Important 8). The busy test
    # runs first, so a frame the pipeline already dropped reports the real reason.
    panel = tab.frames_workspace.panel
    if panel.is_busy():
        label = panel.busy_label or "processing"
        logger.warning("Retouch refused: the %r job is still running", label)
        tab.console.log(f"Wait for the running {label} job to finish before retouching", "WARNING")
        return None
    action = tab.current_action()
    if action is None or not (0 <= index < len(action.frames)) or action.frames[index].source_path is None:
        logger.warning("retouch: no frame at index %s", index)
        tab.console.log("Retouch: select a frame first.", "WARNING")
        return None
    frames = action.frames
    neighbors = [frames[i].source_path for i in (index - 1, index + 1)
                 if 0 <= i < len(frames) and frames[i].source_path is not None]
    region = tab.pixel_view.selection_rect()
    dialog = RetouchDialog(frames[index].source_path, neighbors, provider_factory=tab.make_provider,
                           region=region, parent=tab)
    dialog.retouched.connect(lambda path, a=action, i=index: apply_retouch(tab, a, i, Path(path)))
    if exec_dialog:
        dialog.exec()
    return dialog


def install_retouch(tab) -> None:
    """Call once from SpriteTab.__init__."""
    tab.frame_strip.retouchRequested.connect(lambda index: open_retouch_dialog(tab, index))
