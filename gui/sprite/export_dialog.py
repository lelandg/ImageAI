"""Sprite export dialog (design §4.5, §1.6).

Formats are plugins: `register_format(id, label, fn)` adds a checkbox and a
callable `fn(meta, out_dir) -> List[Path]`. The built-ins cover the sheet PNG,
Aseprite JSON, TexturePacker JSON, PNG sequence, and GIF; sub-project 6
registers Godot `.tres`, native `.aseprite`, and the engine presets. The
export runs in a SpriteWorker; when the sticky purge preference is on, the
intermediates go to the recycle bin afterwards through
`SpriteProject.purge_intermediates()`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from core.paths import get_data_paths
from core.sprite.exporters.aseprite_json import export_aseprite_json
from core.sprite.exporters.gif import export_gif
from core.sprite.exporters.grid import GridOptions, export_grid
from core.sprite.exporters.png_sequence import export_png_sequence
from core.sprite.exporters.texturepacker_json import export_texturepacker_json
from core.sprite.models import SheetMeta
from core.sprite.pipeline import CancelToken, ProgressFn
from core.sprite.project import SpriteProject
from core.utils import sidecar_path
from gui.common.dialog_conventions import (DialogCleanupMixin, bind_primary_action,
                                           persist_splitter, restore_splitter,
                                           set_default_button, standard_splitter)
from gui.llm_utils import DialogStatusConsole

from . import prefs
from .workers import WorkerHost

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "{title}_{tag}_{frame01}.png"
SETTINGS_PREFIX = "sprite/export/"
SPLITTER_KEY = SETTINGS_PREFIX + "splitter"
CLOSE_SHUTDOWN_TIMEOUT_MS = 5000  # on_dialog_close's bound before it falls back to join_orphans()

FormatFn = Callable[[SheetMeta, Path], List[Path]]


@dataclass
class ExportFormat:
    id: str
    label: str
    fn: FormatFn
    needs_sheet: bool = False        # runner writes the sheet PNG (frame rects filled) first
    takes_template: bool = False     # fn(meta, out_dir, template=...)


@dataclass
class ExportRequest:
    project: SpriteProject
    profiles: List[str]
    formats: List[str]
    out_dir: Path
    template: str
    grid: GridOptions
    pivot: Optional[Tuple[float, float]]
    purge: bool


def sheet_png_path(meta: SheetMeta, out_dir: Path) -> Path:
    return Path(out_dir) / f"{meta.title}_{meta.profile}.png"


def _grid_output_paths(png: Path, scales: Sequence[int]) -> List[Path]:
    """Every file `export_grid` writes, for the documented per-scale naming (grid.py).

    Each scale gets three files: the PNG itself (`<png>` at scale 1,
    `<stem>@Nx<suffix>` otherwise), its Aseprite JSON (`<target>.json`), and its
    ImageAI metadata sidecar (`sidecar_path(target)` = `<target>.png.json`).
    """
    paths: List[Path] = []
    for scale in scales:
        target = png if scale == 1 else png.with_name(f"{png.stem}@{scale}x{png.suffix}")
        paths.append(target)
        paths.append(target.with_suffix(".json"))
        paths.append(sidecar_path(target))
    return paths


def format_grid(meta: SheetMeta, out_dir: Path) -> List[Path]:
    """The sheet PNG plus its Aseprite JSON and ImageAI metadata sidecars (design gap 18).

    Registered `needs_sheet=True`, so `run_export`'s top-level block normally already wrote
    (and recorded) these files at every requested scale before this runs; the fallback export
    below only fires if this format is ever invoked standalone, and covers scale 1 only.
    """
    png = sheet_png_path(meta, out_dir)
    if tuple(meta.sheet_size) == (0, 0) or not png.exists():
        export_grid(meta, png, GridOptions())
    files = [png]
    aseprite = png.with_suffix(".json")
    if aseprite.exists():
        files.append(aseprite)
    meta_sidecar = sidecar_path(png)
    if meta_sidecar.exists():
        files.append(meta_sidecar)
    return files


def format_aseprite_json(meta: SheetMeta, out_dir: Path) -> List[Path]:
    png = sheet_png_path(meta, out_dir)
    out = png.with_suffix(".json")
    export_aseprite_json(meta, out, image_name=png.name)
    return [out]


def format_texturepacker_json(meta: SheetMeta, out_dir: Path) -> List[Path]:
    png = sheet_png_path(meta, out_dir)
    out = Path(out_dir) / f"{meta.title}_{meta.profile}.tp.json"
    export_texturepacker_json(meta, out, image_name=png.name)
    return [out]


def format_png_sequence(meta: SheetMeta, out_dir: Path, template: str = DEFAULT_TEMPLATE) -> List[Path]:
    frames_dir = Path(out_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    for png in (Path(p) for p in export_png_sequence(meta, frames_dir, template)):
        files.append(png)
        sidecar = sidecar_path(png)
        if sidecar.exists():
            files.append(sidecar)
    return files


def format_gif(meta: SheetMeta, out_dir: Path) -> List[Path]:
    if not meta.tags:
        logger.warning("GIF export (%s): the sheet has no tags; nothing written", meta.profile)
        return []
    files: List[Path] = []
    for tag in meta.tags:
        out = Path(out_dir) / f"{meta.title}_{tag.name}.gif"
        gif_path = Path(export_gif(meta, tag, out, loop=tag.repeat))
        files.append(gif_path)
        sidecar = sidecar_path(gif_path)
        if sidecar.exists():
            files.append(sidecar)
    return files


BUILTIN_FORMATS: Tuple[ExportFormat, ...] = (
    ExportFormat("grid", "Sprite sheet PNG (+ Aseprite JSON sidecar)", format_grid, needs_sheet=True),
    ExportFormat("aseprite_json", "Aseprite JSON", format_aseprite_json, needs_sheet=True),
    ExportFormat("texturepacker_json", "TexturePacker JSON", format_texturepacker_json, needs_sheet=True),
    ExportFormat("png_sequence", "PNG sequence (per tag)", format_png_sequence, takes_template=True),
    ExportFormat("gif", "Animated GIF (per tag)", format_gif),
)


def parse_scales(text: str) -> Tuple[int, ...]:
    """Parse a comma-separated scale list; always includes 1 (`export_grid` requires it)."""
    values: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            logger.warning("Export: ignored scale %r", part)
            return (1,)
        if value <= 0:
            return (1,)
        values.append(value)
    return tuple(sorted({1, *values}))


def default_export_dir(project: SpriteProject) -> Path:
    base = project.project_dir if project.project_dir is not None else get_data_paths().sprite_projects() / project.name
    return Path(base) / "exports"


def validate_grid_options(opts: GridOptions) -> List[str]:
    """Problems `export_grid` would reject, phrased for the dialog's validation list.

    Refuses with a shown+logged message rather than silently overriding the user's padding —
    `parse_scales` already guarantees `scales` includes 1, so that check here only guards a
    `GridOptions` built outside the dialog (e.g. by a sub-project-6 caller).
    """
    problems: List[str] = []
    if opts.extrude_px < 0 or opts.shape_px < 0 or opts.border_px < 0 or opts.inner_px < 0:
        problems.append("Grid padding values must not be negative.")
    if opts.extrude_px > 0 and (2 * opts.extrude_px > opts.shape_px or opts.extrude_px > opts.border_px):
        problems.append(
            f"Grid extrude ({opts.extrude_px}px) needs shape padding of at least "
            f"{2 * opts.extrude_px}px and border padding of at least {opts.extrude_px}px."
        )
    if any(s < 1 for s in opts.scales) or 1 not in opts.scales:
        problems.append("Grid scales must be positive and include 1.")
    return problems


def run_export(request: ExportRequest, formats: Sequence[ExportFormat], *,
               log: Callable[[str], None], progress: ProgressFn,
               token: CancelToken) -> List[Path]:
    """Export every selected profile with every selected format. No Qt; runs in the worker."""
    written: List[Path] = []
    total = len(request.profiles)
    needs_sheet = any(fmt.needs_sheet for fmt in formats)

    def record(path: Path) -> None:
        path = Path(path)
        if path not in written:
            written.append(path)
            log(f"Wrote {path}")

    for index, profile in enumerate(request.profiles):
        token.raise_if_cancelled()
        meta = request.project.sheet_meta(profile)
        if not meta.frames:
            log(f"Profile '{profile}': no frames; skipped")
            continue
        if request.pivot is not None:
            for frame in meta.frames:
                frame.pivot = (float(request.pivot[0]), float(request.pivot[1]))
        out_dir = request.out_dir / profile
        out_dir.mkdir(parents=True, exist_ok=True)
        if needs_sheet:
            png = sheet_png_path(meta, out_dir)
            progress("export", index, total, f"{profile}: sheet")
            meta = export_grid(meta, png, request.grid)
            for path in _grid_output_paths(png, request.grid.scales):
                if path.exists():
                    record(path)
        for fmt in formats:
            token.raise_if_cancelled()
            progress("export", index, total, f"{profile}: {fmt.label}")
            if fmt.takes_template:
                files = fmt.fn(meta, out_dir, template=request.template)
            else:
                files = fmt.fn(meta, out_dir)
            for path in files:
                record(Path(path))
    progress("export", total, total, "done")
    return written


class ExportDialog(WorkerHost, DialogCleanupMixin, QDialog):
    """Profiles × formats export with output dir, template, grid options, pivot, and purge."""

    exported = Signal(list)
    logMessage = Signal(str, str)

    def __init__(self, project: SpriteProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.settings = prefs.sprite_settings()
        self._formats: Dict[str, ExportFormat] = {}
        self.format_checks: Dict[str, QCheckBox] = {}
        self.profile_checks: Dict[str, QCheckBox] = {}
        self._pending_purge = False
        self.setWindowTitle(f"Export sprites — {project.name}")
        self.setModal(True)
        self.setMinimumSize(660, 680)
        self._build()
        for fmt in BUILTIN_FORMATS:
            self.register_format(fmt.id, fmt.label, fmt.fn, needs_sheet=fmt.needs_sheet,
                                 takes_template=fmt.takes_template, checked=fmt.id == "grid")
        self._load_settings()
        self.logMessage.connect(self.console.log)
        self.purge_check.setChecked(prefs.purge_after_export_enabled())
        self.purge_check.toggled.connect(self._on_purge_toggled)
        set_default_button(self, self.export_btn)
        self._primary = bind_primary_action(self, self.start_export)

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        top = QWidget()
        self.options_layout = QVBoxLayout(top)
        self.options_layout.setContentsMargins(0, 0, 0, 0)

        profiles_box = QGroupBox("Profiles")
        profiles_row = QHBoxLayout(profiles_box)
        for profile in self.project.profiles:
            box = QCheckBox(profile.name)
            box.setChecked(bool(profile.enabled))
            self.profile_checks[profile.name] = box
            profiles_row.addWidget(box)
        profiles_row.addStretch()
        self.options_layout.addWidget(profiles_box)

        self.formats_box = QGroupBox("Formats")
        self.formats_layout = QVBoxLayout(self.formats_box)
        self.options_layout.addWidget(self.formats_box)
        self.notes_label = QLabel("")            # engine-preset notes (sub-project 6 fills it)
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet("color: #888;")
        self.options_layout.addWidget(self.notes_label)

        output_box = QGroupBox("Output")
        output_form = QFormLayout(output_box)
        self.out_dir_edit = QLineEdit(str(default_export_dir(self.project)))
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setAutoDefault(False)
        self.browse_btn.clicked.connect(self._browse)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.out_dir_edit, 1)
        dir_row.addWidget(self.browse_btn)
        output_form.addRow("Directory:", dir_row)
        self.name_template_edit = QLineEdit(DEFAULT_TEMPLATE)
        self.name_template_edit.setToolTip("PNG sequence file name: {title} {tag} {frame} {frame01}")
        output_form.addRow("Frame template:", self.name_template_edit)
        self.pivot_x_spin = QDoubleSpinBox()
        self.pivot_x_spin.setRange(0.0, 1.0)
        self.pivot_x_spin.setSingleStep(0.05)
        self.pivot_x_spin.setDecimals(2)
        self.pivot_x_spin.setValue(0.5)
        self.pivot_y_spin = QDoubleSpinBox()
        self.pivot_y_spin.setRange(0.0, 1.0)
        self.pivot_y_spin.setSingleStep(0.05)
        self.pivot_y_spin.setDecimals(2)
        self.pivot_y_spin.setValue(1.0)
        pivot_row = QHBoxLayout()
        pivot_row.addWidget(QLabel("x"))
        pivot_row.addWidget(self.pivot_x_spin)
        pivot_row.addWidget(QLabel("y"))
        pivot_row.addWidget(self.pivot_y_spin)
        pivot_row.addStretch()
        output_form.addRow("Pivot (normalized):", pivot_row)
        self.options_layout.addWidget(output_box)

        grid_box = QGroupBox("Sheet grid")
        grid_form = QFormLayout(grid_box)
        self.columns = QSpinBox()
        self.columns.setRange(0, 256)
        self.columns.setSpecialValueText("one row per tag")
        grid_form.addRow("Columns:", self.columns)
        self.border = QSpinBox()
        self.border.setRange(0, 64)
        self.shape = QSpinBox()
        self.shape.setRange(0, 64)
        self.shape.setValue(1)
        self.inner = QSpinBox()
        self.inner.setRange(0, 64)
        self.extrude = QSpinBox()
        self.extrude.setRange(0, 16)
        pad_row = QHBoxLayout()
        for label, spin in (("border", self.border), ("shape", self.shape),
                            ("inner", self.inner), ("extrude", self.extrude)):
            pad_row.addWidget(QLabel(label))
            pad_row.addWidget(spin)
        grid_form.addRow("Padding (px):", pad_row)
        self.power_of_two = QCheckBox("Power-of-two sheet")
        grid_form.addRow(self.power_of_two)
        self.scales_edit = QLineEdit("1")
        self.scales_edit.setToolTip("Integer nearest-neighbor copies, e.g. 1,2,4 → @2x/@4x")
        grid_form.addRow("Scales:", self.scales_edit)
        self.options_layout.addWidget(grid_box)

        self.purge_check = QCheckBox("Purge intermediates after export (clips/ and stages/ → recycle bin)")
        self.options_layout.addWidget(self.purge_check)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.options_layout.addWidget(self.progress_bar)

        self.console = DialogStatusConsole("Export log")
        self.splitter = standard_splitter(Qt.Vertical, self)
        self.splitter.addWidget(top)
        self.splitter.addWidget(self.console)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        if not restore_splitter(self.settings, SPLITTER_KEY, self.splitter):
            self.splitter.setSizes([500, 180])
        layout.addWidget(self.splitter, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.start_export)
        buttons.addWidget(self.export_btn)
        layout.addLayout(buttons)

    # ----- format registry (sub-project 6 hook) -----------------------
    def register_format(self, id: str, label: str, fn: FormatFn, *, needs_sheet: bool = False,
                        takes_template: bool = False, checked: bool = False) -> QCheckBox:
        """Add an export format checkbox backed by `fn(meta, out_dir) -> List[Path]`.

        With `needs_sheet=True` the runner calls `export_grid` first: `fn` then receives
        `meta` with frame rects and `sheet_size` filled, and the sheet PNG already exists
        at `sheet_png_path(meta, out_dir)`. `takes_template=True` passes the PNG-sequence
        template as `fn(meta, out_dir, template=...)`.
        """
        if id in self._formats:
            raise ValueError(f"export format '{id}' is already registered")
        self._formats[id] = ExportFormat(id=id, label=label, fn=fn, needs_sheet=needs_sheet,
                                         takes_template=takes_template)
        box = QCheckBox(label)
        box.setChecked(checked)
        self.format_checks[id] = box
        self.formats_layout.addWidget(box)
        return box

    def formats(self) -> List[str]:
        return list(self._formats)

    def selected_formats(self) -> List[str]:
        return [fmt_id for fmt_id, box in self.format_checks.items() if box.isChecked()]

    def selected_profiles(self) -> List[str]:
        return [name for name, box in self.profile_checks.items() if box.isChecked()]

    def grid_options(self) -> GridOptions:
        return GridOptions(columns=self.columns.value(), border_px=self.border.value(),
                           shape_px=self.shape.value(), inner_px=self.inner.value(),
                           extrude_px=self.extrude.value(),
                           power_of_two=self.power_of_two.isChecked(),
                           scales=parse_scales(self.scales_edit.text()))

    def set_grid_options(self, opts: GridOptions) -> None:
        self.columns.setValue(int(opts.columns))
        self.border.setValue(int(opts.border_px))
        self.shape.setValue(int(opts.shape_px))
        self.inner.setValue(int(opts.inner_px))
        self.extrude.setValue(int(opts.extrude_px))
        self.power_of_two.setChecked(bool(opts.power_of_two))
        self.scales_edit.setText(",".join(str(s) for s in opts.scales))

    def current_meta(self) -> Optional[SheetMeta]:
        """SheetMeta of the first selected profile (frame rects not yet filled), or None."""
        profiles = self.selected_profiles()
        if not profiles:
            return None
        try:
            return self.project.sheet_meta(profiles[0])
        except Exception as exc:
            logger.error("sheet_meta(%s) failed: %s", profiles[0], exc, exc_info=True)
            self.console.log(f"Cannot build sheet for '{profiles[0]}': {exc}", "ERROR")
            return None

    def request(self) -> ExportRequest:
        return ExportRequest(project=self.project, profiles=self.selected_profiles(),
                             formats=self.selected_formats(),
                             out_dir=Path(self.out_dir_edit.text().strip()),
                             template=self.name_template_edit.text().strip() or DEFAULT_TEMPLATE,
                             grid=self.grid_options(),
                             pivot=(round(self.pivot_x_spin.value(), 4), round(self.pivot_y_spin.value(), 4)),
                             purge=self.purge_check.isChecked())

    # ----- purge preference -------------------------------------------
    def _on_purge_toggled(self, checked: bool) -> None:
        if checked:
            if not prefs.confirm_purge(self):
                self.purge_check.blockSignals(True)
                self.purge_check.setChecked(False)
                self.purge_check.blockSignals(False)
                return
            prefs.set_purge_after_export(True)
            logger.info("Sprite export: purge-after-export enabled")
        else:
            prefs.set_purge_after_export(False)
            logger.info("Sprite export: purge-after-export disabled")

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Export directory", self.out_dir_edit.text())
        if chosen:
            self.out_dir_edit.setText(chosen)

    # ----- export -----------------------------------------------------
    def is_running(self) -> bool:
        return self.is_busy()

    def start_export(self) -> None:
        if self.is_running():
            return
        request = self.request()
        formats = [self._formats[fmt_id] for fmt_id in request.formats]
        problems = []
        if not request.profiles:
            problems.append("Select at least one profile.")
        if not request.formats:
            problems.append("Select at least one format.")
        if not self.out_dir_edit.text().strip():
            problems.append("Choose an output directory.")
        if any(fmt.needs_sheet for fmt in formats):
            problems.extend(validate_grid_options(request.grid))
        if problems:
            message = "\n".join(problems)
            logger.warning("Sprite export blocked: %s", message)
            self.console.log(message, "WARNING")
            QMessageBox.warning(self, "Export", message)
            return
        self._save_settings()
        self._pending_purge = request.purge
        self.console.log(f"Export: profiles={request.profiles} formats={request.formats} → {request.out_dir}")
        logger.info("Sprite export start: %s", request)

        def log(message: str) -> None:
            self.logMessage.emit(message, "INFO")

        def job(progress, token):
            return run_export(request, formats, log=log, progress=progress, token=token)

        worker = self.start_job(job, label="export", on_finished=self._on_finished,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is None:
            return
        self._set_running(True)

    def _set_running(self, running: bool) -> None:
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setRange(0, 0)
        self.export_btn.setEnabled(not running)
        if hasattr(self, "_primary"):
            self._primary.set_enabled(not running)
        self.close_btn.setEnabled(not running)

    def _on_worker_idle(self) -> None:
        """A worker orphaned by a timed-out ``shutdown()`` finally stopped."""
        self._set_running(False)

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(done)
        self.console.log(f"[{stage}] {message}")

    def _on_finished(self, result: Any) -> None:
        self._set_running(False)
        files = [Path(p) for p in (result or [])]
        if files and self._pending_purge:
            try:
                count = self.project.purge_intermediates()
                self.console.log(f"Purged {count} intermediate item(s) to the recycle bin", "WARNING")
                logger.info("Sprite export: purged %s intermediates", count)
            except Exception as exc:
                logger.error("Purge after export failed: %s", exc, exc_info=True)
                self.console.log(f"Purge failed: {exc}", "ERROR")
                QMessageBox.warning(self, "Purge failed", str(exc))
        self.console.log(f"Export complete: {len(files)} file(s)", "SUCCESS")
        logger.info("Sprite export complete: %d files", len(files))
        self.exported.emit(files)

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        logger.error("Sprite export failed: %s", message)
        self.console.log(f"Export failed: {message}", "ERROR")
        QMessageBox.critical(self, "Export failed", message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        logger.info("Sprite export cancelled")
        self.console.log("Export cancelled", "WARNING")

    # ----- settings (prefs.get_pref / set_pref, keys under sprite/export/) ---
    def _load_settings(self) -> None:
        get = prefs.get_pref
        out_dir = get(SETTINGS_PREFIX + "out_dir", "")
        if out_dir:
            self.out_dir_edit.setText(str(out_dir))
        self.name_template_edit.setText(str(get(SETTINGS_PREFIX + "template", DEFAULT_TEMPLATE)))
        self.columns.setValue(int(get(SETTINGS_PREFIX + "grid/columns", 0)))
        self.border.setValue(int(get(SETTINGS_PREFIX + "grid/border", 0)))
        self.shape.setValue(int(get(SETTINGS_PREFIX + "grid/shape", 1)))
        self.inner.setValue(int(get(SETTINGS_PREFIX + "grid/inner", 0)))
        self.extrude.setValue(int(get(SETTINGS_PREFIX + "grid/extrude", 0)))
        self.power_of_two.setChecked(str(get(SETTINGS_PREFIX + "grid/power_of_two", "false")).lower() == "true")
        self.scales_edit.setText(str(get(SETTINGS_PREFIX + "grid/scales", "1")))
        self.pivot_x_spin.setValue(float(get(SETTINGS_PREFIX + "pivot_x", 0.5)))
        self.pivot_y_spin.setValue(float(get(SETTINGS_PREFIX + "pivot_y", 1.0)))
        formats = get(SETTINGS_PREFIX + "formats", None)
        if formats:
            wanted = set(str(formats).split(","))
            for fmt_id, box in self.format_checks.items():
                box.setChecked(fmt_id in wanted)

    def _save_settings(self) -> None:
        put = prefs.set_pref
        put(SETTINGS_PREFIX + "out_dir", self.out_dir_edit.text())
        put(SETTINGS_PREFIX + "template", self.name_template_edit.text())
        put(SETTINGS_PREFIX + "grid/columns", self.columns.value())
        put(SETTINGS_PREFIX + "grid/border", self.border.value())
        put(SETTINGS_PREFIX + "grid/shape", self.shape.value())
        put(SETTINGS_PREFIX + "grid/inner", self.inner.value())
        put(SETTINGS_PREFIX + "grid/extrude", self.extrude.value())
        put(SETTINGS_PREFIX + "grid/power_of_two", "true" if self.power_of_two.isChecked() else "false")
        put(SETTINGS_PREFIX + "grid/scales", self.scales_edit.text())
        put(SETTINGS_PREFIX + "pivot_x", self.pivot_x_spin.value())
        put(SETTINGS_PREFIX + "pivot_y", self.pivot_y_spin.value())
        put(SETTINGS_PREFIX + "formats", ",".join(self.selected_formats()))

    def on_dialog_close(self) -> None:
        # WorkerHost: cancel + join a running export. Escape/close mid-export must never drop a
        # running QThread (mirror sprite_tab.py's shutdown()/join_orphans() pattern) — the export
        # job polls the cancel token, so an unbounded join still returns.
        if not self.shutdown(timeout_ms=CLOSE_SHUTDOWN_TIMEOUT_MS):
            logger.warning("Sprite export worker did not stop within %d ms; joining before close",
                           CLOSE_SHUTDOWN_TIMEOUT_MS)
            self.join_orphans()
        self._save_settings()
        persist_splitter(self.settings, SPLITTER_KEY, self.splitter)
