"""General-Purpose Prompt Builder Dialog."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QGroupBox, QFormLayout, QMessageBox,
    QListWidget, QListWidgetItem, QWidget, QTabWidget, QFileDialog,
    QTextBrowser
)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QFont, QKeySequence

from core.prompt_data_loader import PromptDataLoader
from core.config import ConfigManager

logger = logging.getLogger(__name__)


class PromptBuilder(QDialog):
    """Dialog for building image generation prompts with character transformation support."""

    prompt_generated = Signal(str)  # Emits the generated prompt

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_loader = PromptDataLoader()
        self.config = ConfigManager()

        # Settings for window position
        self.settings = QSettings("ImageAI", "PromptBuilder")

        # History file
        self.history_file = self.config.config_dir / "prompt_builder_history.json"
        self.history: List[Dict] = []
        self._load_history()

        self.setWindowTitle("Prompt Builder")
        self.setMinimumSize(900, 700)
        self._init_ui()
        self._restore_geometry()
        self._load_example()

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout()

        # Tab widget
        self.tabs = QTabWidget()

        # Builder tab
        builder_tab = self._create_builder_tab()
        self.tabs.addTab(builder_tab, "Builder")

        # History tab
        history_tab = self._create_history_tab()
        self.tabs.addTab(history_tab, "History")

        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

        # Initial preview
        self._update_preview()

    def _create_builder_tab(self) -> QWidget:
        """Create the builder tab."""
        builder_widget = QWidget()
        builder_layout = QVBoxLayout()

        # Instructions
        instructions = QLabel(
            "<b>Build a modular image generation prompt:</b><br>"
            "Use this tool to create complete prompts from scratch, or to transform "
            "attached reference images into different styles and formats.<br>"
            "All fields are optional. Leave blank to omit from prompt."
        )
        instructions.setWordWrap(True)
        builder_layout.addWidget(instructions)

        # Prompt components
        form_layout = QFormLayout()

        # Subject type
        self.subject_combo = self._create_combo([
            "",
            "Headshot of attached",
            "Full body of attached",
            "Portrait of attached",
            "Character sheet of attached",
            "Attached",
            "Image of attached"
        ])
        form_layout.addRow("Subject:", self.subject_combo)

        # Transformation style
        self.transformation_combo = self._create_combo([
            "",
            "as full color super-exaggerated caricature cartoon",
            "as caricature",
            "as cartoon character",
            "as comic book character",
            "as anime character",
            "as realistic portrait",
            "as abstract art",
            "as oil painting",
            "as watercolor painting",
            "as pencil sketch",
            "as digital art",
            "as 3D render"
        ])
        form_layout.addRow("Transform As:", self.transformation_combo)

        # Style (from styles.json)
        styles = [""] + self.data_loader.get_styles()
        self.style_combo = self._create_combo(styles)
        form_layout.addRow("Art Style:", self.style_combo)

        # Medium (from mediums.json)
        mediums = [""] + self.data_loader.get_mediums()
        self.medium_combo = self._create_combo(mediums)
        form_layout.addRow("Medium/Technique:", self.medium_combo)

        # Background
        self.background_combo = self._create_combo([
            "",
            "on a clean white background",
            "on a solid black background",
            "on a transparent background",
            "with studio lighting background",
            "with gradient background",
            "with abstract background",
            "in natural setting",
            "in urban setting"
        ])
        form_layout.addRow("Background:", self.background_combo)

        # Pose/Orientation
        self.pose_combo = self._create_combo([
            "",
            "facing forward",
            "three-quarter view",
            "side view",
            "profile view",
            "dynamic pose",
            "action pose",
            "sitting pose",
            "standing pose"
        ])
        form_layout.addRow("Pose/View:", self.pose_combo)

        # Purpose/Context
        self.purpose_combo = self._create_combo([
            "",
            "suitable as character design sheet",
            "for character concept art",
            "for avatar",
            "for game character",
            "for animation",
            "for illustration",
            "for poster design"
        ])
        form_layout.addRow("Purpose:", self.purpose_combo)

        # Technique details
        self.technique_combo = self._create_combo([
            "",
            "use line work and cross-hatching",
            "with bold outlines",
            "with soft shading",
            "with dramatic lighting",
            "with cel shading",
            "photorealistic",
            "stylized",
            "minimalist"
        ])
        form_layout.addRow("Technique:", self.technique_combo)

        # Artist (from artists.json)
        artists = [""] + self.data_loader.get_artists()
        self.artist_combo = self._create_combo(artists)
        form_layout.addRow("Artist Style:", self.artist_combo)

        # Lighting (from lighting.json)
        lighting = [""] + self.data_loader.get_lighting()
        self.lighting_combo = self._create_combo(lighting)
        form_layout.addRow("Lighting:", self.lighting_combo)

        # Mood (from moods.json)
        moods = [""] + self.data_loader.get_moods()
        self.mood_combo = self._create_combo(moods)
        form_layout.addRow("Mood:", self.mood_combo)

        # Exclusions - Updated to remove 'no' from choices
        self.exclusion_edit = QTextEdit()
        self.exclusion_edit.setMaximumHeight(50)
        self.exclusion_edit.setPlaceholderText(
            "Enter items to exclude, separated by commas (e.g., 'text, watermark, background')\n"
            "'no' will be automatically added to each item"
        )
        self.exclusion_edit.textChanged.connect(self._update_preview)
        form_layout.addRow("Exclude:", self.exclusion_edit)

        builder_layout.addLayout(form_layout)

        # Additional notes
        builder_layout.addWidget(QLabel("Additional Details (optional):"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setPlaceholderText("Add any custom details here...")
        builder_layout.addWidget(self.notes_edit)

        # Connect all combos to update preview
        for combo in self._get_all_combos():
            combo.currentTextChanged.connect(self._update_preview)
        self.notes_edit.textChanged.connect(self._update_preview)

        # Preview
        preview_group = QGroupBox("Prompt Preview")
        preview_layout = QVBoxLayout()

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        font = QFont("Courier New", 10)
        self.preview_text.setFont(font)
        self.preview_text.setMaximumHeight(120)
        preview_layout.addWidget(self.preview_text)

        preview_group.setLayout(preview_layout)
        builder_layout.addWidget(preview_group)

        # Buttons
        button_layout = QHBoxLayout()

        load_example_btn = QPushButton("Load Example")
        load_example_btn.clicked.connect(self._load_example)
        button_layout.addWidget(load_example_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        button_layout.addWidget(export_btn)

        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._import_prompt)
        button_layout.addWidget(import_btn)

        save_btn = QPushButton("Save to History")
        save_btn.clicked.connect(self._save_to_history)
        button_layout.addWidget(save_btn)

        use_btn = QPushButton("Use Prompt")
        use_btn.setDefault(True)
        use_btn.clicked.connect(self._use_prompt)
        button_layout.addWidget(use_btn)

        builder_layout.addLayout(button_layout)
        builder_widget.setLayout(builder_layout)

        return builder_widget

    def _create_history_tab(self) -> QWidget:
        """Create the history tab with detailed view."""
        history_widget = QWidget()
        history_layout = QVBoxLayout()

        # Instructions
        instructions = QLabel(
            "<b>Prompt History:</b> Double-click an entry to load it into the builder."
        )
        instructions.setWordWrap(True)
        history_layout.addWidget(instructions)

        # History list
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._show_history_details)
        self.history_list.itemDoubleClicked.connect(self._load_from_history)
        history_layout.addWidget(self.history_list)

        # Details view
        details_group = QGroupBox("Selected Prompt Details")
        details_layout = QVBoxLayout()

        self.details_browser = QTextBrowser()
        self.details_browser.setMaximumHeight(200)
        details_layout.addWidget(self.details_browser)

        details_group.setLayout(details_layout)
        history_layout.addWidget(details_group)

        # Buttons
        history_btn_layout = QHBoxLayout()

        load_hist_btn = QPushButton("Load Selected")
        load_hist_btn.clicked.connect(self._load_selected_history)
        history_btn_layout.addWidget(load_hist_btn)

        delete_hist_btn = QPushButton("Delete Selected")
        delete_hist_btn.clicked.connect(self._delete_history_item)
        history_btn_layout.addWidget(delete_hist_btn)

        history_btn_layout.addStretch()

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        history_btn_layout.addWidget(export_btn)

        clear_history_btn = QPushButton("Clear All History")
        clear_history_btn.clicked.connect(self._clear_all_history)
        history_btn_layout.addWidget(clear_history_btn)

        history_layout.addLayout(history_btn_layout)
        history_widget.setLayout(history_layout)

        self._update_history_list()

        return history_widget

    def _create_combo(self, items: List[str]) -> QComboBox:
        """Create an editable combo box with given items."""
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(items)
        combo.setCurrentIndex(0)
        return combo

    def _get_all_combos(self) -> List[QComboBox]:
        """Get all combo boxes."""
        return [
            self.subject_combo,
            self.transformation_combo,
            self.style_combo,
            self.medium_combo,
            self.background_combo,
            self.pose_combo,
            self.purpose_combo,
            self.technique_combo,
            self.artist_combo,
            self.lighting_combo,
            self.mood_combo
        ]

    def _process_exclusions(self, exclusion_text: str) -> str:
        """Process exclusion text to add 'no' to each item."""
        if not exclusion_text.strip():
            return ""

        # Split by comma and process each item
        items = [item.strip() for item in exclusion_text.split(',')]
        items = [item for item in items if item]  # Remove empty items

        # Add 'no' to each item that doesn't already start with 'no'
        processed_items = []
        for item in items:
            if not item.lower().startswith('no '):
                processed_items.append(f"no {item}")
            else:
                processed_items.append(item)

        return ", ".join(processed_items)

    def _update_preview(self):
        """Update the prompt preview."""
        prompt_parts = []

        # Gather all non-empty selections
        subject = self.subject_combo.currentText().strip()
        transformation = self.transformation_combo.currentText().strip()
        style = self.style_combo.currentText().strip()
        medium = self.medium_combo.currentText().strip()
        background = self.background_combo.currentText().strip()
        pose = self.pose_combo.currentText().strip()
        purpose = self.purpose_combo.currentText().strip()
        technique = self.technique_combo.currentText().strip()
        artist = self.artist_combo.currentText().strip()
        lighting = self.lighting_combo.currentText().strip()
        mood = self.mood_combo.currentText().strip()
        exclusion_raw = self.exclusion_edit.toPlainText().strip()
        exclusion = self._process_exclusions(exclusion_raw)
        notes = self.notes_edit.toPlainText().strip()

        # Build prompt (order matters!)
        if subject:
            prompt_parts.append(subject)

        if transformation:
            prompt_parts.append(transformation)

        if style:
            prompt_parts.append(f"in {style} style")

        if medium:
            prompt_parts.append(f"using {medium}")

        if background:
            prompt_parts.append(background)

        if pose:
            prompt_parts.append(pose)

        if purpose:
            prompt_parts.append(purpose)

        if technique:
            prompt_parts.append(technique)

        if artist:
            prompt_parts.append(f"in the style of {artist}")

        if lighting:
            prompt_parts.append(f"with {lighting}")

        if mood:
            prompt_parts.append(f"{mood} mood")

        if exclusion:
            prompt_parts.append(exclusion)

        if notes:
            prompt_parts.append(notes)

        # Join with commas
        prompt = ", ".join(prompt_parts) if prompt_parts else "[Empty prompt]"

        self.preview_text.setPlainText(prompt)

    def _load_example(self):
        """Load the example prompt."""
        self.subject_combo.setCurrentText("Headshot of attached")
        self.transformation_combo.setCurrentText("as full color super-exaggerated caricature cartoon")
        self.style_combo.setCurrentText("")
        self.medium_combo.setCurrentText("")
        self.background_combo.setCurrentText("on a clean white background")
        self.pose_combo.setCurrentText("facing forward")
        self.purpose_combo.setCurrentText("suitable as character design sheet")
        self.technique_combo.setCurrentText("use line work and cross-hatching")
        self.artist_combo.setCurrentText("")
        self.lighting_combo.setCurrentText("")
        self.mood_combo.setCurrentText("")
        self.exclusion_edit.setPlainText("text")  # Will become "no text"
        self.notes_edit.clear()

    def _clear_all(self):
        """Clear all selections."""
        for combo in self._get_all_combos():
            combo.setCurrentIndex(0)
        self.exclusion_edit.clear()
        self.notes_edit.clear()

    def _use_prompt(self):
        """Emit the prompt and close dialog."""
        prompt = self.preview_text.toPlainText()
        if prompt == "[Empty prompt]":
            QMessageBox.warning(self, "Empty Prompt", "Please build a prompt first.")
            return

        # Auto-save to history
        self._save_to_history_silent()

        self.prompt_generated.emit(prompt)
        self.accept()

    def _save_to_history(self):
        """Save current prompt to history."""
        prompt = self.preview_text.toPlainText()
        if prompt == "[Empty prompt]":
            QMessageBox.warning(self, "Empty Prompt", "Cannot save empty prompt.")
            return

        # Create history entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "settings": {
                "subject": self.subject_combo.currentText(),
                "transformation": self.transformation_combo.currentText(),
                "style": self.style_combo.currentText(),
                "medium": self.medium_combo.currentText(),
                "background": self.background_combo.currentText(),
                "pose": self.pose_combo.currentText(),
                "purpose": self.purpose_combo.currentText(),
                "technique": self.technique_combo.currentText(),
                "artist": self.artist_combo.currentText(),
                "lighting": self.lighting_combo.currentText(),
                "mood": self.mood_combo.currentText(),
                "exclusion": self.exclusion_edit.toPlainText(),  # Save raw text
                "notes": self.notes_edit.toPlainText()
            }
        }

        self.history.insert(0, entry)  # Add to beginning

        # Limit history size
        if len(self.history) > 100:
            self.history = self.history[:100]

        self._save_history()
        self._update_history_list()

        QMessageBox.information(self, "Saved", "Prompt saved to history.")

    def _save_to_history_silent(self):
        """Save current prompt to history without showing a message box."""
        prompt = self.preview_text.toPlainText()
        if prompt == "[Empty prompt]":
            return

        # Create history entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "settings": {
                "subject": self.subject_combo.currentText(),
                "transformation": self.transformation_combo.currentText(),
                "style": self.style_combo.currentText(),
                "medium": self.medium_combo.currentText(),
                "background": self.background_combo.currentText(),
                "pose": self.pose_combo.currentText(),
                "purpose": self.purpose_combo.currentText(),
                "technique": self.technique_combo.currentText(),
                "artist": self.artist_combo.currentText(),
                "lighting": self.lighting_combo.currentText(),
                "mood": self.mood_combo.currentText(),
                "exclusion": self.exclusion_edit.toPlainText(),  # Save raw text
                "notes": self.notes_edit.toPlainText()
            }
        }

        self.history.insert(0, entry)  # Add to beginning

        # Limit history size
        if len(self.history) > 100:
            self.history = self.history[:100]

        self._save_history()
        self._update_history_list()
        logger.info("Prompt auto-saved to history on use")

    def _show_history_details(self, item: QListWidgetItem):
        """Show detailed information about selected history item."""
        idx = self.history_list.row(item)
        if 0 <= idx < len(self.history):
            entry = self.history[idx]
            settings = entry.get("settings", {})

            # Format timestamp
            timestamp = entry.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                time_str = timestamp

            # Build detailed view
            details_html = f"<b>Date:</b> {time_str}<br><br>"
            details_html += f"<b>Generated Prompt:</b><br>{entry.get('prompt', '')}<br><br>"
            details_html += "<b>Settings:</b><br>"

            # Show all non-empty settings
            for key, value in settings.items():
                if value:
                    display_key = key.replace('_', ' ').title()
                    details_html += f"&nbsp;&nbsp;<b>{display_key}:</b> {value}<br>"

            self.details_browser.setHtml(details_html)

    def _load_from_history(self, item: QListWidgetItem):
        """Load a prompt from history."""
        idx = self.history_list.row(item)
        if 0 <= idx < len(self.history):
            entry = self.history[idx]
            self._apply_settings(entry["settings"])
            # Switch to builder tab
            self.tabs.setCurrentIndex(0)

    def _load_selected_history(self):
        """Load selected history item."""
        item = self.history_list.currentItem()
        if item:
            self._load_from_history(item)

    def _delete_history_item(self):
        """Delete selected history item."""
        item = self.history_list.currentItem()
        if not item:
            return

        reply = QMessageBox.question(
            self, "Delete Entry",
            "Are you sure you want to delete this history entry?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            idx = self.history_list.row(item)
            if 0 <= idx < len(self.history):
                del self.history[idx]
                self._save_history()
                self._update_history_list()
                self.details_browser.clear()

    def _clear_all_history(self):
        """Clear all history entries."""
        if not self.history:
            QMessageBox.information(self, "No History", "History is already empty.")
            return

        reply = QMessageBox.question(
            self, "Clear All History",
            f"Are you sure you want to delete all {len(self.history)} history entries?\n"
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.history = []
            self._save_history()
            self._update_history_list()
            self.details_browser.clear()
            QMessageBox.information(self, "Cleared", "All history has been cleared.")

    def _apply_settings(self, settings: Dict):
        """Apply settings from history."""
        self.subject_combo.setCurrentText(settings.get("subject", ""))
        self.transformation_combo.setCurrentText(settings.get("transformation", ""))
        self.style_combo.setCurrentText(settings.get("style", ""))
        self.medium_combo.setCurrentText(settings.get("medium", ""))
        self.background_combo.setCurrentText(settings.get("background", ""))
        self.pose_combo.setCurrentText(settings.get("pose", ""))
        self.purpose_combo.setCurrentText(settings.get("purpose", ""))
        self.technique_combo.setCurrentText(settings.get("technique", ""))
        self.artist_combo.setCurrentText(settings.get("artist", ""))
        self.lighting_combo.setCurrentText(settings.get("lighting", ""))
        self.mood_combo.setCurrentText(settings.get("mood", ""))
        self.exclusion_edit.setPlainText(settings.get("exclusion", ""))  # Raw text
        self.notes_edit.setPlainText(settings.get("notes", ""))

    def _update_history_list(self):
        """Update the history list widget."""
        self.history_list.clear()

        for entry in self.history:
            timestamp = entry["timestamp"]
            prompt = entry["prompt"]

            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = timestamp[:16]

            # Show full prompt in history list
            item_text = f"{time_str}: {prompt}"
            self.history_list.addItem(item_text)

    def _export(self):
        """Show dialog to choose between exporting current prompt or all history."""
        prompt = self.preview_text.toPlainText()
        has_current = prompt != "[Empty prompt]"
        has_history = len(self.history) > 0

        # Build message based on what's available
        if not has_current and not has_history:
            QMessageBox.information(
                self, "Nothing to Export",
                "There is no current prompt and no history to export."
            )
            return

        # Create custom message box
        msg = QMessageBox(self)
        msg.setWindowTitle("Export")
        msg.setIcon(QMessageBox.Question)

        if has_current and has_history:
            msg.setText("What would you like to export?")
            current_btn = msg.addButton("Current Prompt", QMessageBox.ActionRole)
            history_btn = msg.addButton(f"All History ({len(self.history)} entries)", QMessageBox.ActionRole)
            cancel_btn = msg.addButton(QMessageBox.Cancel)
            msg.exec()

            clicked = msg.clickedButton()
            if clicked == current_btn:
                self._export_current()
            elif clicked == history_btn:
                self._export_all_history()
        elif has_current:
            # Only current prompt available
            msg.setText("Export current prompt?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            if msg.exec() == QMessageBox.Yes:
                self._export_current()
        else:
            # Only history available
            msg.setText(f"Export all history ({len(self.history)} entries)?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            if msg.exec() == QMessageBox.Yes:
                self._export_all_history()

    def _export_current(self):
        """Export current prompt to JSON file."""
        prompt = self.preview_text.toPlainText()
        if prompt == "[Empty prompt]":
            QMessageBox.warning(self, "Empty Prompt", "Cannot export empty prompt.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Current Prompt",
            str(Path.home() / "prompt_export.json"),
            "JSON Files (*.json)"
        )

        if file_path:
            try:
                export_data = {
                    "timestamp": datetime.now().isoformat(),
                    "prompt": prompt,
                    "settings": {
                        "subject": self.subject_combo.currentText(),
                        "transformation": self.transformation_combo.currentText(),
                        "style": self.style_combo.currentText(),
                        "medium": self.medium_combo.currentText(),
                        "background": self.background_combo.currentText(),
                        "pose": self.pose_combo.currentText(),
                        "purpose": self.purpose_combo.currentText(),
                        "technique": self.technique_combo.currentText(),
                        "artist": self.artist_combo.currentText(),
                        "lighting": self.lighting_combo.currentText(),
                        "mood": self.mood_combo.currentText(),
                        "exclusion": self.exclusion_edit.toPlainText(),
                        "notes": self.notes_edit.toPlainText()
                    }
                }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2)

                QMessageBox.information(self, "Exported", f"Prompt exported to:\n{file_path}")
                logger.info(f"Exported current prompt to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export prompt:\n{e}")
                logger.error(f"Error exporting prompt: {e}")

    def _export_all_history(self):
        """Export all history to JSON file."""
        if not self.history:
            QMessageBox.information(self, "No History", "No history to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export All History",
            str(Path.home() / "prompt_history_export.json"),
            "JSON Files (*.json)"
        )

        if file_path:
            try:
                export_data = {
                    "exported_at": datetime.now().isoformat(),
                    "count": len(self.history),
                    "history": self.history
                }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2)

                QMessageBox.information(
                    self, "Exported",
                    f"Exported {len(self.history)} history entries to:\n{file_path}"
                )
                logger.info(f"Exported {len(self.history)} history entries to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export history:\n{e}")
                logger.error(f"Error exporting history: {e}")

    def _import_prompt(self):
        """Import prompt from JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Prompt",
            str(Path.home()),
            "JSON Files (*.json)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check if it's a single prompt or full history export
                if "history" in data:
                    # Full history export
                    reply = QMessageBox.question(
                        self, "Import History",
                        f"This file contains {len(data['history'])} history entries.\n"
                        "Do you want to import all of them?\n\n"
                        "Yes = Import all to history\n"
                        "No = Load only the most recent entry to builder",
                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                    )

                    if reply == QMessageBox.Yes:
                        # Import all to history
                        imported_count = 0
                        for entry in data['history']:
                            if "settings" in entry and "prompt" in entry:
                                self.history.insert(0, entry)
                                imported_count += 1

                        # Limit history size
                        if len(self.history) > 100:
                            self.history = self.history[:100]

                        self._save_history()
                        self._update_history_list()
                        QMessageBox.information(
                            self, "Imported",
                            f"Imported {imported_count} entries to history."
                        )
                        logger.info(f"Imported {imported_count} history entries from {file_path}")
                    elif reply == QMessageBox.No and data['history']:
                        # Load first entry to builder
                        self._apply_settings(data['history'][0]['settings'])
                        self.tabs.setCurrentIndex(0)
                        logger.info(f"Loaded first entry from {file_path} to builder")
                elif "settings" in data:
                    # Single prompt
                    self._apply_settings(data['settings'])
                    self.tabs.setCurrentIndex(0)
                    QMessageBox.information(self, "Imported", "Prompt loaded into builder.")
                    logger.info(f"Imported single prompt from {file_path}")
                else:
                    QMessageBox.warning(self, "Invalid File", "File does not contain valid prompt data.")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import prompt:\n{e}")
                logger.error(f"Error importing prompt: {e}")

    def _load_history(self):
        """Load history from file."""
        if not self.history_file.exists():
            return

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.history = json.load(f)
            logger.info(f"Loaded {len(self.history)} history entries")
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            self.history = []

    def _save_history(self):
        """Save history to file."""
        try:
            # Ensure directory exists
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2)

            logger.info(f"Saved {len(self.history)} history entries")
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def _restore_geometry(self):
        """Restore window position and size from settings."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Restore active tab
        last_tab = self.settings.value("activeTab", 0, type=int)
        if 0 <= last_tab < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab)

    def _save_geometry(self):
        """Save window position and size to settings."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("activeTab", self.tabs.currentIndex())

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        # Ctrl+Enter to use prompt
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            self._use_prompt()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle close event to save geometry."""
        self._save_geometry()
        super().closeEvent(event)

    def accept(self):
        """Handle accept (OK/Use Prompt) to save geometry."""
        self._save_geometry()
        super().accept()

    def reject(self):
        """Handle reject (Cancel/Close) to save geometry."""
        self._save_geometry()
        super().reject()
