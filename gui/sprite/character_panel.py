"""Character intake panel: drop/browse → normalize → chroma plate → turnaround.

All PIL and provider work runs inside a SpriteWorker; the GUI thread only
paints one thumbnail. Output layout (design §1.6):
``<project_dir>/source/character.png``, ``source/plate.png``,
``source/turnaround/<view>.png``.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QVBoxLayout,
)

from core.sprite.generation.plate import make_chroma_plate
from core.sprite.generation.turnaround import generate_turnaround
from core.sprite.source import analyze_source, normalize_source
from gui.dialog_utils import show_error
from gui.sprite.workers import WorkerHost
from providers import get_provider

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
THUMB_SIZE = 200
DROP_HINT = "Drop a character image here\nor click Browse…"


def paths_from_mime(mime: QMimeData) -> List[Path]:
    """Local image files carried by a drag; other files are ignored."""
    paths: List[Path] = []
    if not mime.hasUrls():
        return paths
    for url in mime.urls():
        local = url.toLocalFile()
        if local and Path(local).suffix.lower() in IMAGE_SUFFIXES:
            paths.append(Path(local))
    return paths


class CharacterPanel(WorkerHost, QGroupBox):
    sourceChanged = Signal(object)      # Path — normalized character PNG
    plateReady = Signal(object)         # Path
    turnaroundReady = Signal(object)    # Dict[str, Path]
    plateColorChanged = Signal(str)
    historyEntry = Signal(dict)
    logMessage = Signal(str, str)

    def __init__(self, config, parent=None):
        super().__init__("Character", parent)
        self.config = config
        self.project = None
        self._plate_color = "#00FF00"
        self._build()
        self.setAcceptDrops(True)
        self._sync_enabled()

    # -- UI ----------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)

        self.drop_label = QLabel(DROP_HINT)
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setMinimumHeight(THUMB_SIZE)
        self.drop_label.setStyleSheet("border: 2px dashed #888; padding: 8px;")
        root.addWidget(self.drop_label)

        row = QHBoxLayout()
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._browse)
        row.addWidget(self.browse_btn)
        self.analysis_label = QLabel("No character loaded.")
        self.analysis_label.setWordWrap(True)
        row.addWidget(self.analysis_label, 1)
        root.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Plate color:"))
        self.plate_color_btn = QPushButton()
        self.plate_color_btn.setToolTip("Chroma key color used for the plate and every clip")
        self.plate_color_btn.clicked.connect(self._pick_plate_color)
        row2.addWidget(self.plate_color_btn)
        self.plate_btn = QPushButton("Make chroma plate")
        self.plate_btn.clicked.connect(self.make_plate)
        row2.addWidget(self.plate_btn)
        self.turnaround_btn = QPushButton("Generate turnaround")
        self.turnaround_btn.clicked.connect(self.generate_turnaround)
        row2.addWidget(self.turnaround_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        row2.addWidget(self.cancel_btn)
        root.addLayout(row2)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.status_label = QLabel("")
        root.addWidget(self.status_label)
        self._set_plate_color_ui(self._plate_color)

    def _sync_enabled(self) -> None:
        busy = self.is_busy()
        has_project = self.project is not None
        has_source = has_project and bool(getattr(self.project, "character_source", None))
        self.browse_btn.setEnabled(has_project and not busy)
        self.plate_btn.setEnabled(has_source and not busy)
        self.turnaround_btn.setEnabled(has_source and not busy)
        self.cancel_btn.setEnabled(busy)
        self.setAcceptDrops(has_project and not busy)

    def _set_plate_color_ui(self, hex_color: str) -> None:
        self._plate_color = hex_color.upper()
        self.plate_color_btn.setText(self._plate_color)
        self.plate_color_btn.setStyleSheet(f"background-color: {self._plate_color};")

    def _show_thumbnail(self, path: Optional[Path]) -> None:
        if path and Path(path).exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.drop_label.setPixmap(pixmap.scaled(
                    THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.drop_label.setPixmap(QPixmap())
        self.drop_label.setText(DROP_HINT)

    def _describe(self, analysis) -> str:
        w, h = analysis.size
        parts = [f"{w}×{h}", "has alpha" if analysis.has_alpha else "no alpha"]
        if analysis.border_color:
            uniform = "uniform" if analysis.border_uniform else "mixed"
            parts.append(f"border {analysis.border_color} ({uniform})")
        return ", ".join(parts)

    # -- public API --------------------------------------------------------

    @property
    def plate_color(self) -> str:
        return self._plate_color

    def set_project(self, project) -> None:
        self.project = project
        if project is not None:
            self._set_plate_color_ui(getattr(project, "plate_color", None) or "#00FF00")
            self._show_thumbnail(getattr(project, "character_source", None))
            source = getattr(project, "character_source", None)
            if source and Path(source).exists():
                try:
                    self.analysis_label.setText(self._describe(analyze_source(Path(source))))
                except Exception as exc:  # noqa: BLE001 - readout only
                    logger.warning("Source analysis failed: %s", exc)
                    self.analysis_label.setText(Path(source).name)
            else:
                self.analysis_label.setText("No character loaded.")
        else:
            self._show_thumbnail(None)
            self.analysis_label.setText("No character loaded.")
        self._sync_enabled()

    def set_source(self, path: Path) -> None:
        """Normalize ``path`` into the project (worker) and record it as the character."""
        path = Path(path)
        if self.project is None:
            show_error(self, "Sprite", "Create or open a sprite project before adding a character.")
            return
        if not path.exists() or path.suffix.lower() not in IMAGE_SUFFIXES:
            show_error(self, "Sprite", f"Not an image file: {path.name}")
            return
        out_png = Path(self.project.project_dir) / "source" / "character.png"
        aspect = getattr(self.project.generation, "aspect_ratio", "16:9")

        def job(progress, token):
            progress("source", 0, 0, f"Normalizing {path.name}")
            out_png.parent.mkdir(parents=True, exist_ok=True)
            out = normalize_source(path, out_png, aspect_ratio=aspect)
            token.raise_if_cancelled()
            return Path(out), analyze_source(Path(out))

        self.logMessage.emit(f"Importing character from {path}", "INFO")
        self._begin("normalize", job, self._on_source_done)

    def make_plate(self) -> None:
        if not self._ready_for_provider("chroma plate"):
            return
        character = Path(self.project.character_source)
        out_png = Path(self.project.project_dir) / "source" / "plate.png"
        color = self._plate_color
        provider_cfg = self._provider_config()
        if provider_cfg is None:
            return

        def job(progress, token):
            progress("plate", 0, 0, f"Placing character on {color} plate")
            out_png.parent.mkdir(parents=True, exist_ok=True)
            provider = get_provider("google", provider_cfg)
            return Path(make_chroma_plate(provider, character, out_png, color,
                                          log=lambda m: progress("plate", 0, 0, m)))

        self.logMessage.emit(f"Chroma plate requested ({color}) for {character.name}", "INFO")
        self._begin("plate", job, self._on_plate_done)

    def generate_turnaround(self) -> None:
        if not self._ready_for_provider("turnaround"):
            return
        character = Path(self.project.character_source)
        out_dir = Path(self.project.project_dir) / "source" / "turnaround"
        color = self._plate_color
        provider_cfg = self._provider_config()
        if provider_cfg is None:
            return

        def job(progress, token):
            progress("turnaround", 0, 0, "Generating front / side / back / ¾ views")
            provider = get_provider("google", provider_cfg)
            views = generate_turnaround(provider, character, out_dir, plate_color=color,
                                        log=lambda m: progress("turnaround", 0, 0, m),
                                        token=token)
            return {str(k): Path(v) for k, v in dict(views).items()}

        self.logMessage.emit(f"Turnaround pack requested for {character.name}", "INFO")
        self._begin("turnaround", job, self._on_turnaround_done)

    def cancel(self) -> None:
        if self.is_busy():
            self.logMessage.emit("Cancelling…", "WARNING")
            self.cancel_running()

    # -- worker plumbing ---------------------------------------------------

    def _ready_for_provider(self, what: str) -> bool:
        if self.project is None:
            show_error(self, "Sprite", f"Open a sprite project before making a {what}.")
            return False
        source = getattr(self.project, "character_source", None)
        if not source or not Path(source).exists():
            show_error(self, "Sprite", f"Load a character image before making a {what}.")
            return False
        return True

    def _provider_config(self) -> Optional[dict]:
        api_key = self.config.get_api_key("google")
        auth_mode = self.config.get_auth_mode("google")
        if not api_key:
            show_error(self, "Sprite", "No Google API key is configured. Add one in Settings.")
            return None
        return {"api_key": api_key, "auth_mode": auth_mode}

    def _begin(self, label: str, job, on_finished) -> None:
        worker = self.start_job(job, label=label, on_finished=on_finished,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is None:
            self.logMessage.emit("Another character job is still running.", "WARNING")
            return
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self._sync_enabled()

    def _finish(self) -> None:
        self.progress.setVisible(False)
        self.status_label.setText("")
        self._sync_enabled()

    def _history_entry(self, path: Path, prompt: str) -> dict:
        return {"path": path, "prompt": prompt, "provider": "google", "model": "",
                "timestamp": time.time(), "cost": 0.0, "source_tab": "sprite"}

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        else:
            self.progress.setRange(0, 0)
        self.status_label.setText(f"{stage}: {message}")
        self.logMessage.emit(f"[{stage}] {message}", "INFO")

    def _on_failed(self, message: str) -> None:
        self._finish()
        self.logMessage.emit(message, "ERROR")
        show_error(self, "Sprite", message)

    def _on_cancelled(self) -> None:
        self._finish()
        self.logMessage.emit("Cancelled.", "WARNING")

    def _on_source_done(self, result) -> None:
        out, analysis = result
        self.project.character_source = out
        self._show_thumbnail(out)
        self.analysis_label.setText(self._describe(analysis))
        self._finish()
        self.logMessage.emit(f"Character normalized → {out}", "SUCCESS")
        self.sourceChanged.emit(out)

    def _on_plate_done(self, out) -> None:
        out = Path(out)
        self.project.plate_path = out
        self.project.plate_color = self._plate_color
        self._finish()
        self.logMessage.emit(f"Chroma plate saved → {out}", "SUCCESS")
        self.historyEntry.emit(self._history_entry(out, f"chroma plate {self._plate_color}"))
        self.plateReady.emit(out)

    def _on_turnaround_done(self, views: Dict[str, Path]) -> None:
        self.project.turnaround = dict(views)
        self._finish()
        self.logMessage.emit(f"Turnaround pack saved: {', '.join(sorted(views))}", "SUCCESS")
        for view, path in views.items():
            self.historyEntry.emit(self._history_entry(path, f"turnaround {view}"))
        self.turnaroundReady.emit(dict(views))

    # -- user actions ------------------------------------------------------

    def _browse(self) -> None:
        filters = "Images (" + " ".join(f"*{s}" for s in IMAGE_SUFFIXES) + ")"
        path, _ = QFileDialog.getOpenFileName(self, "Choose a character image", "", filters)
        if path:
            self.set_source(Path(path))

    def _pick_plate_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._plate_color), self, "Chroma plate color")
        if not color.isValid():
            return
        self._set_plate_color_ui(color.name())
        if self.project is not None:
            self.project.plate_color = self._plate_color
        self.logMessage.emit(f"Plate color set to {self._plate_color}", "INFO")
        self.plateColorChanged.emit(self._plate_color)

    # -- drag & drop -------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = paths_from_mime(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.set_source(paths[0])
