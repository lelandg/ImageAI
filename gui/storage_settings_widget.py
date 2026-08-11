"""Settings-tab UI for relocating ImageAI's data groups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QObject, QStandardPaths, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
)

from core.data_migration import move_group, sources_for, tree_size, validate_destination
from core.paths import Group, get_data_paths, reset_data_paths

logger = logging.getLogger(__name__)

GROUP_LABELS = {
    Group.IMAGES: "Images",
    Group.VIDEO: "Video",
    Group.MODELS: "Models",
    Group.SETTINGS: "Settings",
}

GROUP_HINTS = {
    Group.IMAGES: "Generated images, composites, styles, Midjourney cache",
    Group.VIDEO: "Video projects, render caches, the events database",
    Group.MODELS: "MuseTalk, Character Animator weights, Stable Diffusion models",
    Group.SETTINGS: "Logs, history, layout templates (config.json always stays put)",
}

# Where the "Move…" folder picker starts for each group. Models and Settings
# start at the home directory, not the platform application-data directory. The
# user opens the picker to move data off the application-data directory, so that
# directory is the wrong place to start. It is also the directory the GUI is
# forbidden to name (tests/gui/test_gui_paths.py).
PICKER_ROOTS = {
    Group.IMAGES: QStandardPaths.PicturesLocation,
    Group.VIDEO: QStandardPaths.MoviesLocation,
    Group.MODELS: QStandardPaths.HomeLocation,
    Group.SETTINGS: QStandardPaths.HomeLocation,
}


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{int(value)} B" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


@dataclass
class StorageRow:
    name_label: QLabel
    path_label: QLabel
    size_label: QLabel
    status_label: QLabel
    move_button: QPushButton
    open_button: QPushButton


class _SizeWorker(QObject):
    """Walks the trees for one group off the UI thread."""

    # The byte total is qint64, not int. A plain ``int`` maps to a 4-byte C int,
    # and any group larger than 2 GB overflows it.
    finished = Signal(str, "qint64")  # group value, total bytes

    def __init__(self, group: Group) -> None:
        super().__init__()
        self._group = group

    def run(self) -> None:
        try:
            total = sum(tree_size(source)[1] for source, _name in sources_for(self._group))
        except Exception:  # noqa: BLE001 - a size probe must never crash the UI
            logger.exception("Could not measure the %s storage group", self._group.value)
            total = -1
        self.finished.emit(self._group.value, total)


class StorageSettingsWidget(QGroupBox):
    """Shows where each data group lives and lets the user move it."""

    move_completed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("Storage Locations", parent)
        self.rows: Dict[Group, StorageRow] = {}
        self._threads = []
        self._build_ui()
        self.refresh_sizes()

    def _build_ui(self) -> None:
        grid = QGridLayout(self)
        grid.setColumnStretch(1, 1)

        header = QLabel(
            "Move large data off your system drive. "
            "config.json always stays in the default location."
        )
        header.setWordWrap(True)
        grid.addWidget(header, 0, 0, 1, 5)

        paths = get_data_paths()
        for index, group in enumerate(Group, start=1):
            name_label = QLabel(GROUP_LABELS[group])
            name_label.setToolTip(GROUP_HINTS[group])

            path_label = QLabel(self._path_text(group))
            path_label.setToolTip(self._path_tooltip(group))
            path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            size_label = QLabel("Calculating…")
            size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            status_label = QLabel("")

            move_button = QPushButton("&Move…")
            move_button.setToolTip(f"Relocate {GROUP_LABELS[group]} data")
            move_button.clicked.connect(lambda _c=False, g=group: self._on_move(g))

            open_button = QPushButton("&Open")
            open_button.setToolTip("Show this folder in the file manager")
            open_button.clicked.connect(lambda _c=False, g=group: self._on_open(g))

            grid.addWidget(name_label, index, 0)
            grid.addWidget(path_label, index, 1)
            grid.addWidget(size_label, index, 2)
            grid.addWidget(move_button, index, 3)
            grid.addWidget(open_button, index, 4)

            self.rows[group] = StorageRow(
                name_label, path_label, size_label, status_label,
                move_button, open_button,
            )

            grid.addWidget(status_label, index, 1, 1, 4)
            status_label.setVisible(False)

        # Surface any root that could not be reached at startup.
        for message in paths.drain_warnings():
            logger.warning(message)
            for group in Group:
                if f"'{group.value}'" in message:
                    row = self.rows[group]
                    row.status_label.setText("⚠ Unavailable — using default location")
                    row.status_label.setVisible(True)

    def _path_text(self, group: Group) -> str:
        return str(get_data_paths().root(group))

    def _path_tooltip(self, group: Group) -> str:
        sources = sources_for(group)
        if not sources:
            return "No data yet."
        return "\n".join(str(source) for source, _name in sources)

    def refresh_sizes(self) -> None:
        """Measure every group off the UI thread."""
        for group in Group:
            thread = QThread(self)
            worker = _SizeWorker(group)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(self._on_size_ready)
            worker.finished.connect(thread.quit)
            thread.finished.connect(worker.deleteLater)
            self._threads.append((thread, worker))
            thread.start()

    def _on_size_ready(self, group_value: str, total: int) -> None:
        row = self.rows[Group(group_value)]
        row.size_label.setText("unknown" if total < 0 else human_size(total))

    def _on_open(self, group: Group) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        target = get_data_paths().root(group)
        target.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _suggested_dir(self, group: Group) -> str:
        base = QStandardPaths.writableLocation(PICKER_ROOTS[group])
        return str(Path(base) / "ImageAI" / GROUP_LABELS[group])

    def _confirm(self, group: Group, dest: Path, total: int) -> bool:
        import shutil

        probe = dest if dest.exists() else dest.parent
        try:
            free = shutil.disk_usage(probe).free
        except OSError:
            free = 0

        box = QMessageBox(self)
        box.setWindowTitle(f"Move {GROUP_LABELS[group]} data")
        box.setIcon(QMessageBox.Question)
        box.setText(f"Move {GROUP_LABELS[group]} data to a new location?")
        box.setInformativeText(
            f"From:  {get_data_paths().root(group)}\n"
            f"To:    {dest}\n\n"
            f"Size to move:      {human_size(total)}\n"
            f"Free at destination: {human_size(free)}\n\n"
            f"ImageAI copies the data, verifies it, then removes the original."
        )
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec() == QMessageBox.Ok

    def _run_with_progress(self, group: Group, dest: Path):
        dialog = QProgressDialog(
            f"Moving {GROUP_LABELS[group]} data…", "Cancel", 0, 100, self
        )
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setValue(0)

        def progress(files_done, files_total, bytes_done, bytes_total, current):
            percent = int(bytes_done * 100 / bytes_total) if bytes_total else 0
            dialog.setValue(min(percent, 100))
            dialog.setLabelText(
                f"Moving {GROUP_LABELS[group]} data…\n"
                f"{files_done} of {files_total} files "
                f"({human_size(bytes_done)} of {human_size(bytes_total)})\n"
                f"{Path(current).name}"
            )
            QApplication.processEvents()

        try:
            return move_group(
                group, dest,
                progress_cb=progress,
                cancel=dialog.wasCanceled,
                pre_move=self._close_open_resources,
            )
        finally:
            dialog.close()

    def _close_open_resources(self) -> None:
        """Ask the main window to release file handles before a move."""
        window = self.window()
        closer = getattr(window, "close_data_handles", None)
        if callable(closer):
            closer()

    def _offer_restart(self, group: Group, result) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Move complete")
        box.setIcon(QMessageBox.Information)
        box.setText(
            f"Moved {human_size(result.bytes_moved)} of "
            f"{GROUP_LABELS[group]} data."
        )
        box.setInformativeText(
            "Restart ImageAI to use the new location."
        )
        restart = box.addButton("Restart Now", QMessageBox.AcceptRole)
        box.addButton("Later", QMessageBox.RejectRole)
        box.exec()

        if box.clickedButton() is restart:
            self._restart_application()

    @staticmethod
    def _restart_application() -> None:
        import os
        import sys

        logger.info("Restarting ImageAI after a storage move")
        QApplication.quit()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _on_move(self, group: Group) -> None:
        start = self._suggested_dir(group)
        chosen = QFileDialog.getExistingDirectory(
            self, f"Choose a folder for {GROUP_LABELS[group]} data", start
        )
        if not chosen:
            return

        dest = Path(chosen)
        error = validate_destination(group, dest)
        if error:
            logger.error("Rejected destination %s for %s: %s", dest, group.value, error)
            QMessageBox.critical(self, "Cannot use that folder", error)
            return

        total = sum(tree_size(source)[1] for source, _name in sources_for(group))
        if not self._confirm(group, dest, total):
            return

        result = self._run_with_progress(group, dest)

        if not result.ok:
            logger.error("Move of %s failed: %s", group.value, result.error)
            QMessageBox.critical(self, "Move failed", result.error)
            self.refresh_sizes()
            return

        reset_data_paths()
        self.rows[group].path_label.setText(str(dest))
        self.rows[group].path_label.setToolTip(str(dest))
        self.refresh_sizes()
        self.move_completed.emit(group.value)
        self._offer_restart(group, result)
