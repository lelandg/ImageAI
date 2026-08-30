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
    """
    frames = copy.deepcopy(action.frames)
    frames[index].source_path = Path(new_path)
    tab.frames_workspace.apply_frames(action.id, frames, f"retouch {index + 1}")
    tab.console.log(f"Frame {index + 1} retouched -> {Path(new_path).name}", "SUCCESS")
    logger.info("retouch applied: action=%s frame=%d -> %s", action.name, index + 1, new_path)


def open_retouch_dialog(tab, index: int, *, exec_dialog: bool = True) -> Optional[RetouchDialog]:
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
