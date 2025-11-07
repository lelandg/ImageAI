"""Character/Object Transformation Prompt Builder Dialog."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QGroupBox, QFormLayout, QMessageBox,
    QSplitter, QListWidget, QListWidgetItem, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.prompt_data_loader import PromptDataLoader
from core.config import ConfigManager

logger = logging.getLogger(__name__)


class CharacterPromptBuilder(QDialog):
    """Dialog for building character/object transformation prompts."""

    prompt_generated = Signal(str)  # Emits the generated prompt

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_loader = PromptDataLoader()
        self.config = ConfigManager()

        # History file
        self.history_file = self.config.config_dir / "character_prompt_history.json"
        self.history: List[Dict] = []
        self._load_history()

        self.setWindowTitle("Character Transformation Prompt Builder")
        self.setMinimumSize(900, 700)
        self._init_ui()
        self._load_example()

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QHBoxLayout()

        # Left side: Builder
        builder_layout = QVBoxLayout()

        # Instructions
        instructions = QLabel(
            "<b>Build a modular character transformation prompt:</b><br>"
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

        # Exclusions
        self.exclusion_combo = self._create_combo([
            "",
            "no text",
            "no background",
            "no watermark",
            "no text or watermark"
        ])
        form_layout.addRow("Exclude:", self.exclusion_combo)

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
        self.preview_text.setMaximumHeight(100)
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

        save_btn = QPushButton("Save to History")
        save_btn.clicked.connect(self._save_to_history)
        button_layout.addWidget(save_btn)

        use_btn = QPushButton("Use Prompt")
        use_btn.clicked.connect(self._use_prompt)
        button_layout.addWidget(use_btn)

        builder_layout.addLayout(button_layout)

        # Right side: History
        history_layout = QVBoxLayout()
        history_layout.addWidget(QLabel("<b>History:</b>"))

        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._load_from_history)
        history_layout.addWidget(self.history_list)

        history_btn_layout = QHBoxLayout()
        load_hist_btn = QPushButton("Load")
        load_hist_btn.clicked.connect(self._load_selected_history)
        history_btn_layout.addWidget(load_hist_btn)

        delete_hist_btn = QPushButton("Delete")
        delete_hist_btn.clicked.connect(self._delete_history_item)
        history_btn_layout.addWidget(delete_hist_btn)

        history_layout.addLayout(history_btn_layout)

        # Combine layouts
        splitter = QSplitter(Qt.Horizontal)

        builder_widget = QWidget()
        builder_widget.setLayout(builder_layout)
        splitter.addWidget(builder_widget)

        history_widget = QWidget()
        history_widget.setLayout(history_layout)
        splitter.addWidget(history_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # Initial preview
        self._update_preview()
        self._update_history_list()

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
            self.mood_combo,
            self.exclusion_combo
        ]

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
        exclusion = self.exclusion_combo.currentText().strip()
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
        self.exclusion_combo.setCurrentText("no text")
        self.notes_edit.clear()

    def _clear_all(self):
        """Clear all selections."""
        for combo in self._get_all_combos():
            combo.setCurrentIndex(0)
        self.notes_edit.clear()

    def _use_prompt(self):
        """Emit the prompt and close dialog."""
        prompt = self.preview_text.toPlainText()
        if prompt == "[Empty prompt]":
            QMessageBox.warning(self, "Empty Prompt", "Please build a prompt first.")
            return

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
                "exclusion": self.exclusion_combo.currentText(),
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

    def _load_from_history(self, item: QListWidgetItem):
        """Load a prompt from history."""
        idx = self.history_list.row(item)
        if 0 <= idx < len(self.history):
            entry = self.history[idx]
            self._apply_settings(entry["settings"])

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

        idx = self.history_list.row(item)
        if 0 <= idx < len(self.history):
            del self.history[idx]
            self._save_history()
            self._update_history_list()

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
        self.exclusion_combo.setCurrentText(settings.get("exclusion", ""))
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

            # Truncate prompt for display
            display_prompt = prompt if len(prompt) < 60 else prompt[:57] + "..."

            item_text = f"{time_str}: {display_prompt}"
            self.history_list.addItem(item_text)

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
