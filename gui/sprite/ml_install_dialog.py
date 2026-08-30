"""Runtime install dialog for the sprite ML matting backends (mediapipe, rembg).

Mirrors gui/install_dialog.py (Real-ESRGAN): PackageInstaller thread, status
console in a persisted splitter, close blocked while pip runs. rembg needs
Python 3.11-3.13 (design decision 4); the dialog drops it on other versions
and says so.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from core.package_installer import PackageInstaller
from core.sprite.ml_install import python_supports_rembg, sprite_ml_packages
from gui.common.dialog_conventions import (DialogCleanupMixin, bind_primary_action,
                                           persist_splitter, restore_splitter,
                                           set_default_button, standard_splitter)
from gui.llm_utils import DialogStatusConsole

from . import prefs

logger = logging.getLogger(__name__)

SPLITTER_KEY = "sprite/ml_install/splitter"


class SpriteMLInstallDialog(DialogCleanupMixin, QDialog):
    """Install the optional ML background-removal packages into the running venv."""

    installFinished = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install sprite ML backends")
        self.setModal(True)
        self.setMinimumSize(560, 440)
        self.settings = prefs.sprite_settings()
        self._installer: Optional[PackageInstaller] = None
        self._packages, self._index_url = self._select_packages()
        self._build()

    # ----- package selection ----------------------------------------
    @staticmethod
    def _select_packages() -> Tuple[List[str], str]:
        packages, index_url = sprite_ml_packages()
        specs = [str(s) for s in packages]
        if not python_supports_rembg():
            specs = [s for s in specs if not s.lower().startswith("rembg")]
        return specs, str(index_url or "")

    def packages(self) -> List[str]:
        return list(self._packages)

    def index_url(self) -> str:
        return self._index_url

    def rembg_gated(self) -> bool:
        return not python_supports_rembg()

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Install optional ML background removal")
        title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        top_layout.addWidget(title)

        info = QLabel("These packages install into the running Python environment:\n"
                      + "\n".join(f"  • {spec}" for spec in self._packages)
                      + "\n\nmediapipe removes backgrounds with no model download. "
                        "rembg downloads its model (isnet-anime, 168 MB, MIT) on first use.")
        info.setWordWrap(True)
        top_layout.addWidget(info)

        self.gate_label = QLabel("rembg needs Python 3.11-3.13. This Python is outside that "
                                 "range, so only mediapipe will be installed.")
        self.gate_label.setWordWrap(True)
        self.gate_label.setStyleSheet("color: #cca700;")
        self.gate_label.setVisible(self.rembg_gated())
        top_layout.addWidget(self.gate_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        top_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Ready.")
        top_layout.addWidget(self.status_label)

        self.console = DialogStatusConsole("Installation output")
        self.splitter = standard_splitter(Qt.Vertical, self)
        self.splitter.addWidget(top)
        self.splitter.addWidget(self.console)
        self.splitter.setStretchFactor(1, 1)
        if not restore_splitter(self.settings, SPLITTER_KEY, self.splitter):
            self.splitter.setSizes([220, 240])
        layout.addWidget(self.splitter, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self.start_install)
        self.install_btn.setEnabled(bool(self._packages))
        buttons.addWidget(self.install_btn)
        layout.addLayout(buttons)

        set_default_button(self, self.install_btn, focus=bool(self._packages))
        self._primary = bind_primary_action(self, self.install_btn.click)

    # ----- install ----------------------------------------------------
    def is_running(self) -> bool:
        return self._installer is not None and self._installer.isRunning()

    def start_install(self) -> None:
        if self.is_running():
            return
        if not self._packages:
            self._warn("Nothing to install", "No packages are selected for this Python version.")
            return
        logger.info("Sprite ML install: %s", self._packages)
        self.console.log(f"Installing: {', '.join(self._packages)}")
        self.status_label.setText("Installing…")
        self.install_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self._primary.set_enabled(False)
        # update_requirements=False: the sprite extras live in requirements-sprite-ml.txt
        self._installer = PackageInstaller(self._packages, update_requirements=False,
                                           index_url=self._index_url or None)
        self._installer.progress.connect(self._on_progress)
        self._installer.percentage.connect(self.progress_bar.setValue)
        self._installer.finished.connect(self._on_finished)
        self._installer.start()

    def _on_progress(self, message: str) -> None:
        self.status_label.setText(message)
        self.console.log(message)

    def _on_finished(self, ok: bool, message: str) -> None:
        self.close_btn.setEnabled(True)
        self.install_btn.setEnabled(not ok)
        self._primary.set_enabled(not ok)
        if ok:
            logger.info("Sprite ML install finished: %s", message)
            self.status_label.setText("Installed. Restart ImageAI to load the new backends.")
            self.console.log(message, "SUCCESS")
        else:
            logger.error("Sprite ML install failed: %s", message)
            self.status_label.setText("Install failed.")
            self.console.log(message, "ERROR")
            QMessageBox.warning(self, "Install failed", message)
        self.installFinished.emit(ok)

    # ----- exit paths -------------------------------------------------
    def reject(self) -> None:
        if self.is_running():
            self._warn("Installation in progress",
                       "Wait for pip to finish. Closing now may leave packages half installed.")
            return
        super().reject()

    def on_dialog_close(self) -> None:
        persist_splitter(self.settings, SPLITTER_KEY, self.splitter)

    def _warn(self, title: str, message: str) -> None:
        logger.warning("%s: %s", title, message)
        self.console.log(f"{title}: {message}", "WARNING")
        QMessageBox.warning(self, title, message)
