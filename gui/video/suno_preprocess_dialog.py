"""
Suno Package Preprocessing Dialog

Allows users to select which stems/MIDI files to include when merging
a Suno multi-file package into the project.
"""

import logging
from pathlib import Path
from typing import Set, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QGroupBox, QScrollArea, QWidget, QMessageBox,
    QProgressDialog, QApplication
)
from PySide6.QtCore import Qt, QTimer

from core.video.suno_package import SunoPackage, get_package_info

logger = logging.getLogger(__name__)


class SunoPreprocessDialog(QDialog):
    """
    Dialog for preprocessing Suno packages.

    Shows available stems and MIDI files with checkboxes to select
    which ones to include in the merge. All items are selected by default.

    When a stem has both MIDI and WAV files, they are automatically linked
    so selecting/deselecting one updates the other.

    Note: Volume mixing should be done in Suno before export. This dialog
    does not provide volume controls - all selected stems are merged at
    equal volume.
    """

    def __init__(self, package: SunoPackage, parent=None):
        super().__init__(parent)
        self.package = package
        self.audio_checkboxes = {}  # stem_name -> QCheckBox
        self.midi_checkboxes = {}   # stem_name -> QCheckBox
        self.linked_stems = set()   # stem names that have both MIDI and WAV

        # Find stems that have both MIDI and WAV
        audio_stems = set(package.audio_stems.keys())
        midi_stems = set(package.midi_files.keys())
        self.linked_stems = audio_stems & midi_stems  # Intersection

        logger.info(f"Found {len(self.linked_stems)} stems with both MIDI and WAV: {sorted(self.linked_stems)}")

        self.setWindowTitle("Suno Package Detected")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)

        # Header info
        info = get_package_info(self.package)
        header_text = (
            f"Found Suno package: <b>{info['source_file']}</b><br>"
            f"Audio stems: {info['num_audio_stems']} | MIDI files: {info['num_midi_files']}"
        )
        header_label = QLabel(header_text)
        header_label.setWordWrap(True)
        layout.addWidget(header_label)

        # Instructions
        if self.linked_stems:
            link_info = f"<br><b>🔗 Linked stems:</b> {len(self.linked_stems)} stems have both MIDI and WAV files. " \
                       f"Selecting one format will automatically select the other."
        else:
            link_info = ""

        instructions = QLabel(
            "<i>Select which stems and MIDI files to include in the merge. "
            "All items are selected by default.<br><br>"
            "<b>Note:</b> For custom volume mixing, adjust stem volumes in Suno before exporting. "
            f"All selected stems are merged at equal volume.{link_info}</i>"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; margin: 10px 0;")
        layout.addWidget(instructions)

        # Scroll area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Audio stems section
        if self.package.audio_stems:
            audio_group = QGroupBox("Audio Stems")
            audio_layout = QVBoxLayout(audio_group)

            for stem_name in sorted(self.package.audio_stems.keys()):
                # Add link indicator if this stem has both MIDI and WAV
                display_name = f"🔗 {stem_name}" if stem_name in self.linked_stems else stem_name
                checkbox = QCheckBox(display_name)
                checkbox.setChecked(True)  # All selected by default

                tooltip = f"File: {self.package.audio_stems[stem_name].name}"
                if stem_name in self.linked_stems:
                    tooltip += "\n🔗 Linked with MIDI file - both will be selected together"
                checkbox.setToolTip(tooltip)

                # Connect signal for linked checkboxes
                if stem_name in self.linked_stems:
                    checkbox.stateChanged.connect(lambda state, name=stem_name: self._on_audio_checkbox_changed(name, state))

                audio_layout.addWidget(checkbox)
                self.audio_checkboxes[stem_name] = checkbox

            scroll_layout.addWidget(audio_group)

        # MIDI files section
        if self.package.midi_files:
            midi_group = QGroupBox("MIDI Files")
            midi_layout = QVBoxLayout(midi_group)

            for stem_name in sorted(self.package.midi_files.keys()):
                # Add link indicator if this stem has both MIDI and WAV
                display_name = f"🔗 {stem_name}" if stem_name in self.linked_stems else stem_name
                checkbox = QCheckBox(display_name)
                checkbox.setChecked(True)  # All selected by default

                tooltip = f"File: {self.package.midi_files[stem_name].name}"
                if stem_name in self.linked_stems:
                    tooltip += "\n🔗 Linked with audio file - both will be selected together"
                checkbox.setToolTip(tooltip)

                # Connect signal for linked checkboxes
                if stem_name in self.linked_stems:
                    checkbox.stateChanged.connect(lambda state, name=stem_name: self._on_midi_checkbox_changed(name, state))

                midi_layout.addWidget(checkbox)
                self.midi_checkboxes[stem_name] = checkbox

            scroll_layout.addWidget(midi_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Select/Deselect all buttons
        select_buttons_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        select_buttons_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all)
        select_buttons_layout.addWidget(deselect_all_btn)

        select_buttons_layout.addStretch()
        layout.addLayout(select_buttons_layout)

        # Action buttons
        button_layout = QHBoxLayout()

        preprocess_btn = QPushButton("Preprocess && Merge")
        preprocess_btn.setDefault(True)
        preprocess_btn.clicked.connect(self._validate_and_accept)
        preprocess_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(preprocess_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _on_audio_checkbox_changed(self, stem_name: str, state: int):
        """
        Handle audio checkbox state change for linked stems.
        Automatically updates the corresponding MIDI checkbox.
        """
        if stem_name in self.linked_stems and stem_name in self.midi_checkboxes:
            # Temporarily block signals to prevent infinite loop
            midi_checkbox = self.midi_checkboxes[stem_name]
            midi_checkbox.blockSignals(True)
            midi_checkbox.setChecked(bool(state))
            midi_checkbox.blockSignals(False)
            logger.debug(f"Linked: Audio '{stem_name}' -> MIDI '{stem_name}' = {bool(state)}")

    def _on_midi_checkbox_changed(self, stem_name: str, state: int):
        """
        Handle MIDI checkbox state change for linked stems.
        Automatically updates the corresponding audio checkbox.
        """
        if stem_name in self.linked_stems and stem_name in self.audio_checkboxes:
            # Temporarily block signals to prevent infinite loop
            audio_checkbox = self.audio_checkboxes[stem_name]
            audio_checkbox.blockSignals(True)
            audio_checkbox.setChecked(bool(state))
            audio_checkbox.blockSignals(False)
            logger.debug(f"Linked: MIDI '{stem_name}' -> Audio '{stem_name}' = {bool(state)}")

    def _select_all(self):
        """Select all audio and MIDI checkboxes"""
        for checkbox in self.audio_checkboxes.values():
            checkbox.setChecked(True)
        for checkbox in self.midi_checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all(self):
        """Deselect all audio and MIDI checkboxes"""
        for checkbox in self.audio_checkboxes.values():
            checkbox.setChecked(False)
        for checkbox in self.midi_checkboxes.values():
            checkbox.setChecked(False)

    def _validate_and_accept(self):
        """Validate selection and accept dialog"""
        # Check if at least something is selected
        audio_selected = any(cb.isChecked() for cb in self.audio_checkboxes.values())
        midi_selected = any(cb.isChecked() for cb in self.midi_checkboxes.values())

        if not audio_selected and not midi_selected:
            QMessageBox.warning(
                self,
                "Nothing Selected",
                "Please select at least one audio stem or MIDI file to merge."
            )
            return

        self.accept()

    def get_selected_audio_stems(self) -> Set[str]:
        """
        Get set of selected audio stem names.

        Returns:
            Set of stem names (e.g., {"Vocals", "Drums", "Bass"})
        """
        return {
            stem_name for stem_name, checkbox in self.audio_checkboxes.items()
            if checkbox.isChecked()
        }

    def get_selected_midi_files(self) -> Set[str]:
        """
        Get set of selected MIDI file names.

        Returns:
            Set of stem names (e.g., {"Vocals", "Drums", "Bass"})
        """
        return {
            stem_name for stem_name, checkbox in self.midi_checkboxes.items()
            if checkbox.isChecked()
        }

    def has_audio_selection(self) -> bool:
        """Check if any audio stems are selected"""
        return bool(self.get_selected_audio_stems())

    def has_midi_selection(self) -> bool:
        """Check if any MIDI files are selected"""
        return bool(self.get_selected_midi_files())


def show_merge_progress_dialog(parent: QWidget,
                               merging_audio: bool,
                               merging_midi: bool) -> QProgressDialog:
    """
    Show a progress dialog while merging files.

    Args:
        parent: Parent widget
        merging_audio: True if merging audio stems
        merging_midi: True if merging MIDI files

    Returns:
        QProgressDialog configured for the merge operation
    """
    tasks = []
    if merging_audio:
        tasks.append("audio stems")
    if merging_midi:
        tasks.append("MIDI files")

    task_str = " and ".join(tasks)

    progress = QProgressDialog(
        f"Merging {task_str}...\n\nThis may take a moment.",
        None,  # No cancel button
        0, 0,  # Indeterminate progress
        parent
    )
    progress.setWindowTitle("Processing Suno Package")
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)  # Show immediately
    progress.setCancelButton(None)  # No cancel
    progress.setAutoClose(True)
    progress.setAutoReset(True)

    return progress
