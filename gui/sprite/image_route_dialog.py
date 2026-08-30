"""Render one action card through the image route (sheet or edit-chain) in a SpriteWorker."""
from __future__ import annotations

import copy
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit,
    QPushButton, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from core.sprite.generation.cost import record_actual
from core.sprite.generation.errors import ProviderError
from core.sprite.generation.image_route import (
    default_openai_edit_model, edit_chain, generate_pose_instructions, generate_sheet,
    slice_generated_sheet,
)
from core.sprite.models import FrameMeta
from core.sprite.pipeline import CancelToken, ProgressFn, run_pipeline, stage_dir
from core.sprite.project import ActionCard, SpriteProject
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button
from gui.llm_utils import DialogStatusConsole
from gui.sprite.workers import SpriteWorker

logger = logging.getLogger(__name__)

PROVIDERS = (("google", "Google Gemini"), ("openai", "OpenAI gpt-image"))
MODES = (("sheet", "Sheet (one image, sliced)"), ("edit_chain", "Edit chain (one edit per frame)"))
PoseFn = Callable[[ActionCard, int, Callable[[str], None]], List[str]]


def archive_existing_frames(extract_dir: Path) -> Optional[Path]:
    """Move a populated extract directory aside instead of deleting it; return the archive path."""
    extract_dir = Path(extract_dir)
    if not extract_dir.exists() or not any(extract_dir.iterdir()):
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = extract_dir.with_name(f"{extract_dir.name}.prev-{stamp}")
    extract_dir.rename(archive)
    logger.info("archived previous frames: %s -> %s", extract_dir, archive)
    return archive


class ImageRouteDialog(DialogCleanupMixin, QDialog):
    rendered = Signal(object)   # List[Path]
    logLine = Signal(str)

    def __init__(self, project: SpriteProject, action: ActionCard, *,
                 provider_factory: Callable[[str], object], pose_fn: PoseFn,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project = project
        self.action = action
        self._provider_factory = provider_factory
        self._pose_fn = pose_fn
        self._worker: Optional[SpriteWorker] = None
        self.frames_before: List[FrameMeta] = []     # pre-render frame list; restored before apply_frames snapshots
        self.setWindowTitle(f"Render (image) — {action.name}")
        self._build_ui()
        self.logLine.connect(self.console.log)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical, self)
        top = QWidget()
        form = QFormLayout(top)
        self.mode_combo = QComboBox()
        for mid, label in MODES:
            self.mode_combo.addItem(label, mid)
        form.addRow("Mode:", self.mode_combo)
        self.provider_combo = QComboBox()
        for pid, label in PROVIDERS:
            self.provider_combo.addItem(label, pid)
        form.addRow("Provider:", self.provider_combo)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("provider default")
        form.addRow("Model:", self.model_edit)
        self.frames_spin = QSpinBox()
        self.frames_spin.setRange(2, 24)
        self.frames_spin.setValue(max(2, min(24, self.action.target_frames)))
        form.addRow("Frames:", self.frames_spin)
        self.matte_check = QCheckBox("Render white + black plates and difference-matte (2x cost)")
        form.addRow("", self.matte_check)
        steps_row = QHBoxLayout()
        self.steps_edit = QPlainTextEdit()
        self.steps_edit.setPlaceholderText("One pose per line (edit-chain). Leave empty to ask the LLM.")
        self.steps_btn = QPushButton("Generate pose steps")
        self.steps_btn.clicked.connect(self.generate_steps)
        steps_row.addWidget(self.steps_edit, 1)
        steps_row.addWidget(self.steps_btn)
        form.addRow("Pose steps:", steps_row)
        splitter.addWidget(top)
        self.console = DialogStatusConsole("Status Console", self)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.render_btn = QPushButton("Render (Ctrl+Enter)")
        self.render_btn.clicked.connect(self.start_render)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_render)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        for button in (self.render_btn, self.cancel_btn, self.close_btn):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._on_mode_changed(0)
        self._primary = bind_primary_action(self, self.start_render)
        set_default_button(self, self.render_btn)
        self.resize(640, 560)

    def _on_mode_changed(self, _index: int) -> None:
        chain = self.mode_combo.currentData() == "edit_chain"
        self.matte_check.setEnabled(chain)
        self.steps_edit.setEnabled(chain)
        self.steps_btn.setEnabled(chain)

    # ----------------------------------------------------------------- jobs
    def _typed_steps(self) -> List[str]:
        return [line.strip() for line in self.steps_edit.toPlainText().splitlines() if line.strip()]

    def generate_steps(self) -> None:
        """Fill the pose-step editor from the LLM contract (runs in a worker)."""
        if self._worker is not None:
            self.console.log("A job is already running.", "WARNING")
            return
        action, frames, pose_fn, log = self.action, self.frames_spin.value(), self._pose_fn, self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> List[str]:
            progress("pose_steps", 0, 1, f"Asking the LLM for {frames} pose steps")
            token.raise_if_cancelled()
            return pose_fn(action, frames, log)

        self._worker = SpriteWorker(job, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_steps_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._set_running(True)
        self._worker.start()

    def _on_steps_ready(self, steps) -> None:
        self.steps_edit.setPlainText("\n".join(steps))
        self.console.log(f"{len(steps)} pose steps ready; edit them, then Render.", "SUCCESS")
        self._set_running(False)

    def build_job(self) -> Callable[[ProgressFn, CancelToken], List[Path]]:
        mode = self.mode_combo.currentData()
        provider_id = self.provider_combo.currentData()
        model = self.model_edit.text().strip() or None
        frames = self.frames_spin.value()
        matte = self.matte_check.isChecked() and mode == "edit_chain"
        typed_steps = self._typed_steps()
        project, action = self.project, self.action
        factory, pose_fn, log = self._provider_factory, self._pose_fn, self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> List[Path]:
            character = project.plate_path or project.character_source
            if character is None or not Path(character).exists():
                raise ProviderError("Import a character image first (Character panel).")
            provider = factory(provider_id)
            model_used = model or (default_openai_edit_model() if provider_id == "openai"
                                   else provider.get_default_model())
            extract_dir = stage_dir(project, action, "extract")
            archived = archive_existing_frames(extract_dir)
            if archived is not None:
                log(f"[image route] previous frames kept at {archived}")
            if mode == "sheet":
                progress("image_route", 0, 3, "Generating sheet")
                sheet_png = Path(project.project_dir) / "clips" / f"{action.id}_sheet.png"
                sheet = generate_sheet(provider, Path(character), action, sheet_png, frames=frames,
                                       plate_color=project.plate_color, model=model, log=log, token=token)
                progress("image_route", 1, 3, "Slicing sheet")
                paths = slice_generated_sheet(sheet, extract_dir, frames, project.plate_color, log=log)
            else:
                steps = typed_steps
                if len(steps) != frames:
                    progress("image_route", 0, 3, f"Generating {frames} pose steps")
                    steps = pose_fn(action, frames, log)
                progress("image_route", 1, 3, f"Edit chain: {frames} steps")
                paths = edit_chain(provider, Path(character), action, extract_dir, frames=frames,
                                   pose_instructions=steps, plate_color=project.plate_color, model=model,
                                   log=log, token=token, matte_pairs=matte)
            progress("image_route", 2, 3, "Running pipeline to stabilize")
            duration_ms = round(1000 / max(1, action.fps))
            action.frames = [
                FrameMeta(name=f"{project.name}_{action.name}_{i:02d}", source_path=p, frame=(0, 0, 0, 0),
                          duration_ms=duration_ms)
                for i, p in enumerate(paths, start=1)
            ]
            action.clip = None
            action.status = "rendered"
            action.error = None
            edits = len(paths) * (2 if matte else 1)
            record_actual(project, action, None,
                          note=f"image route {mode}: {len(paths)} frame(s), {edits} edit(s)",
                          provider=provider_id, model=model_used, seconds=float(edits))
            run_pipeline(project, action, upto="stabilize", progress=progress, token=token)
            action.status = "processed"
            project.save()
            progress("image_route", 3, 3, f"{len(paths)} frame(s) ready")
            return paths

        return job

    def start_render(self) -> None:
        if self._worker is not None:
            self.console.log("A job is already running.", "WARNING")
            return
        self.frames_before = copy.deepcopy(self.action.frames)
        self._worker = SpriteWorker(self.build_job(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_rendered)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._set_running(True)
        self.console.log(f"Image route started: {self.action.name} ({self.mode_combo.currentData()})")
        self._worker.start()

    def cancel_render(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.console.log("Cancel requested", "WARNING")

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        self.console.log(f"[{stage}] {done}/{total} {message}")

    def _on_rendered(self, paths) -> None:
        paths = list(paths)
        self.console.log(f"Rendered {len(paths)} frame(s) for {self.action.name}", "SUCCESS")
        self._set_running(False)
        self.rendered.emit(paths)

    def _on_failed(self, message: str) -> None:
        logger.error("image route failed: %s", message)
        self.console.log(f"Failed: {message}", "ERROR")
        self._set_running(False)

    def _on_cancelled(self) -> None:
        logger.info("image route cancelled: %s", self.action.name)
        self.console.log("Cancelled.", "WARNING")
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.render_btn.setEnabled(not running)
        self.steps_btn.setEnabled(not running and self.mode_combo.currentData() == "edit_chain")
        self.cancel_btn.setEnabled(running)
        if not running:
            self._worker = None

    def on_dialog_close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(2000)
            self._worker = None


# --------------------------------------------------------------------- tab wiring

def _make_pose_fn(tab) -> PoseFn:
    """Pose steps use the chat provider chosen in the action-cards panel; the model comes from the registry."""
    def pose_fn(action: ActionCard, frames: int, log: Callable[[str], None]) -> List[str]:
        provider = tab.action_cards_panel.llm_provider()
        auth_mode = tab.config.get_auth_mode(provider) if provider in ("google", "gemini") else None
        return generate_pose_instructions(action, frames, provider=provider, model=None,
                                          api_key=tab.config.get_api_key(provider), auth_mode=auth_mode, log=log)
    return pose_fn


def _on_rendered(tab, action: ActionCard, dialog: ImageRouteDialog) -> None:
    """Refresh the card status; reload strip + player when the rendered action is the current one.

    The job already wrote ``action.frames``. ``apply_frames`` snapshots the current list for
    undo before it installs the new one, so restore the pre-render list first and hand the
    rendered list over as the new one.
    """
    tab.action_cards_panel.refresh_status()
    current = tab.current_action()
    if current is not None and current.id == action.id:
        rendered = list(action.frames)
        action.frames = list(dialog.frames_before)
        tab.frames_workspace.apply_frames(action.id, rendered, "Render (image)")
    tab.console.log(f"Image route: '{action.name}' has {len(action.frames)} frame(s)", "SUCCESS")


def open_image_route_dialog(tab, action: ActionCard, *, exec_dialog: bool = True) -> Optional[ImageRouteDialog]:
    project = tab.current_project
    if project is None:
        logger.warning("image route: no project open")
        tab.console.log("Open or create a sprite project first.", "WARNING")
        return None
    dialog = ImageRouteDialog(project, action, provider_factory=tab.make_provider,
                              pose_fn=_make_pose_fn(tab), parent=tab)
    dialog.rendered.connect(lambda _paths, a=action, d=dialog: _on_rendered(tab, a, d))
    if exec_dialog:
        dialog.exec()
    return dialog


def install_image_route(tab) -> None:
    """Call once from SpriteTab.__init__: adds "Render (image)" to every action card row."""
    tab.action_cards_panel.add_card_action("Render (image)", lambda action: open_image_route_dialog(tab, action))
