"""Settings-tab UI for relocating ImageAI's data groups."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set

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

        for index, group in enumerate(Group):
            # Two grid rows per group. The status line needs a row of its own:
            # a status line placed in the path row renders on top of the path,
            # the size, and both buttons.
            main_row = index * 2 + 1
            status_row = main_row + 1
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

            grid.addWidget(name_label, main_row, 0)
            grid.addWidget(path_label, main_row, 1)
            grid.addWidget(size_label, main_row, 2)
            grid.addWidget(move_button, main_row, 3)
            grid.addWidget(open_button, main_row, 4)

            self.rows[group] = StorageRow(
                name_label, path_label, size_label, status_label,
                move_button, open_button,
            )

            grid.addWidget(status_label, status_row, 1, 1, 4)
            status_label.setVisible(False)

        self.refresh_status()

    # -- unreachable roots -------------------------------------------------

    def _configured_roots(self, paths) -> Dict[str, str]:
        """Return the ``data_roots`` mapping written in config.json.

        The widget reads the file itself. ``DataPaths`` keeps its copy
        private, and the live ConfigManager may hold a root this process set
        after the resolver cached its answer.
        """
        config_file = paths.config_file()
        try:
            if not config_file.exists():
                return {}
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.exception(
                "Could not read %s, so the Storage rows cannot show which "
                "roots are unreachable", config_file,
            )
            return {}
        roots = data.get("data_roots")
        if not isinstance(roots, dict):
            return {}
        return {key: value for key, value in roots.items() if isinstance(value, str)}

    def _unavailable_groups(self, paths) -> Set[Group]:
        """Return the groups whose configured root could not be reached.

        The resolver's warning buffer cannot answer this. The Settings root
        resolves inside ``setup_logging``, and that drain empties the buffer
        long before this widget is built, so the Settings row would never show
        its marker. Compare the configured root against the resolved root
        instead. The two differ only when the resolver fell back to the
        default location.
        """
        configured = self._configured_roots(paths)
        unavailable: Set[Group] = set()
        for group in Group:
            raw = configured.get(group.value)
            if not raw:
                continue
            try:
                if Path(raw).resolve() != paths.root(group).resolve():
                    unavailable.add(group)
            except OSError:
                logger.exception(
                    "Could not compare the configured %s root %s with the "
                    "resolved root; marking the row unavailable",
                    group.value, raw,
                )
                unavailable.add(group)
        return unavailable

    def _report_warnings(self, paths) -> None:
        """Drain the resolver's buffer without logging a message twice.

        ``core.paths`` keeps every message in its buffer after it hands the
        message to the logging sink, so this widget can still mark the row.
        The sink already wrote that message to the log file and to stderr.
        Log here only when no sink is installed, because the widget is then
        the one reader the message has.
        """
        import core.paths as paths_module

        sink_installed = getattr(paths_module, "_WARNING_SINK", None) is not None
        for message in paths.drain_warnings():
            if sink_installed:
                logger.debug("Storage warning already reported by the sink: %s", message)
            else:
                logger.warning(message)

    def refresh_status(self) -> None:
        """Mark every row whose configured root is unreachable."""
        paths = get_data_paths()
        # Resolve every root first. The resolution itself buffers the
        # warnings, so the drain below must run after it.
        unavailable = self._unavailable_groups(paths)
        self._report_warnings(paths)

        for group, row in self.rows.items():
            if group in unavailable:
                row.status_label.setText("⚠ Unavailable — using default location")
                row.status_label.setVisible(True)
            else:
                row.status_label.setText("")
                row.status_label.setVisible(False)

    def _path_text(self, group: Group) -> str:
        return str(get_data_paths().root(group))

    def _path_tooltip(self, group: Group) -> str:
        sources = sources_for(group)
        if not sources:
            return "No data yet."
        return "\n".join(str(source) for source, _name in sources)

    def _prune_threads(self) -> None:
        """Drop the workers that already finished.

        Every refresh starts four threads. Without this the list grows for the
        life of the window and keeps every finished QThread alive.
        """
        still_running = []
        for thread, worker in self._threads:
            if thread.isFinished():
                thread.deleteLater()
            else:
                still_running.append((thread, worker))
        self._threads = still_running

    def refresh_sizes(self) -> None:
        """Measure every group off the UI thread."""
        self._prune_threads()
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
                pre_move=lambda: self._close_open_resources(group),
            )
        finally:
            dialog.close()

    def _close_open_resources(self, group: Group) -> None:
        """Ask the main window to release file handles before a move.

        A missing hook is a defect, not a normal state. Windows refuses to
        rename or delete a file that this process still holds open, so the
        move fails later with an unclear error. Log the missing hook here.
        """
        window = self.window()
        closer = getattr(window, "close_data_handles", None)
        if not callable(closer):
            logger.warning(
                "No close_data_handles hook on %s; open %s files stay open "
                "during the move",
                type(window).__name__, group.value,
            )
            return
        closer(group)

    def _restore_open_resources(self, group: Group) -> None:
        """Ask the main window to take back the handles it released.

        ``pre_move`` releases handles before the copy starts. The copy can
        fail, the user can cancel, and the user can keep working after a
        successful move. Each of those paths leaves this process running, so
        the handles must come back. Without the restore the Midjourney watcher
        stays off and the video History tab loads nothing for the rest of the
        session.
        """
        window = self.window()
        restorer = getattr(window, "restore_data_handles", None)
        if not callable(restorer):
            logger.warning(
                "No restore_data_handles hook on %s; the %s handles this "
                "process released stay released until ImageAI restarts",
                type(window).__name__, group.value,
            )
            return
        try:
            restorer(group)
        except Exception:  # noqa: BLE001 - the app must stay usable
            logger.exception(
                "Could not restore the %s handles; restart ImageAI to recover",
                group.value,
            )

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
            return

        # The user keeps working in this process. Every handle the move
        # released must come back, or the session stays degraded.
        logger.info(
            "The user chose Later after the %s move; restoring the released "
            "handles", group.value,
        )
        self._restore_open_resources(group)

    @staticmethod
    def _relaunch_command():
        """Return ``(program, arguments)`` that start this application again."""
        import os
        import sys

        if getattr(sys, "frozen", False):
            return sys.executable, list(sys.argv[1:])
        script = os.path.abspath(sys.argv[0]) if sys.argv else ""
        arguments = ([script] if script else []) + list(sys.argv[1:])
        return sys.executable, arguments

    def _restart_application(self) -> None:
        """Shut down normally, then start a new instance.

        The relaunch runs from an atexit handler so the close event and the
        other atexit handlers run first. The close event saves the video
        project and the UI state, and an atexit handler copies the log file.
        ``subprocess`` quotes each argument, so a path that contains a space
        survives on Windows.
        """
        import atexit
        import os
        import subprocess
        import sys

        program, arguments = self._relaunch_command()
        command = [program] + arguments
        logger.info("Restarting ImageAI after a storage move: %s", command)

        def relaunch() -> None:
            try:
                kwargs = {"cwd": os.getcwd(), "close_fds": True}
                if os.name == "nt":
                    kwargs["creationflags"] = (
                        getattr(subprocess, "DETACHED_PROCESS", 0)
                        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    )
                else:
                    kwargs["start_new_session"] = True
                subprocess.Popen(command, **kwargs)
            except Exception:  # noqa: BLE001 - the old process is exiting
                logger.exception("Could not restart ImageAI: %s", command)
                print(
                    f"Could not restart ImageAI. Start it again with: {command}",
                    file=sys.stderr,
                )

        atexit.register(relaunch)

        window = self.window()
        closer = getattr(window, "close", None)
        if callable(closer):
            # close() runs closeEvent: the video autosave and the UI state.
            closer()
        QApplication.quit()

    def _update_live_config(self, group: Group, dest: Path) -> None:
        """Teach the running ConfigManager where the group now lives.

        ``move_group`` already wrote ``data_roots`` to config.json. The main
        window still holds the dictionary it loaded at startup, and it saves
        that dictionary when the window closes. Without this update the save
        drops the new root and the moved data becomes unreachable.
        """
        window = self.window()
        config = getattr(window, "config", None)
        if config is None:
            logger.warning(
                "No live configuration on %s; the new %s root exists only in "
                "config.json", type(window).__name__, group.value,
            )
            return

        try:
            current = config.get("data_roots", {})
            roots = dict(current) if isinstance(current, dict) else {}
            roots[group.value] = str(dest)
            config.set("data_roots", roots)
            logger.info("Live configuration now points %s at %s", group.value, dest)
        except Exception:  # noqa: BLE001 - the data is already moved
            logger.exception(
                "Could not update the live configuration for %s; a later save "
                "may drop the new root %s", group.value, dest,
            )

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
            # Restore before the modal box. The box blocks until the user
            # dismisses it, and the app must be usable the moment it closes.
            self._restore_open_resources(group)
            QMessageBox.critical(self, "Move failed", result.error)
            self.refresh_sizes()
            self.refresh_status()
            return

        self._update_live_config(group, dest)
        reset_data_paths()
        self.rows[group].path_label.setText(str(dest))
        self.rows[group].path_label.setToolTip(str(dest))
        self.refresh_sizes()
        self.refresh_status()
        self.move_completed.emit(group.value)
        self._offer_restart(group, result)
