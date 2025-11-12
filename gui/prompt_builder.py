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
    QTextBrowser, QScrollArea, QSizePolicy, QLineEdit, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QSettings, QTimer
from PySide6.QtGui import QFont, QKeySequence

from core.prompt_data_loader import PromptDataLoader
from core.preset_loader import PresetLoader
from core.config import ConfigManager
from core.tag_searcher import TagSearcher

logger = logging.getLogger(__name__)


class SavePresetDialog(QDialog):
    """Dialog for saving a custom preset."""

    def __init__(self, preset_loader: PresetLoader, parent=None):
        """Initialize the save preset dialog.

        Args:
            preset_loader: PresetLoader instance for saving
            parent: Parent widget
        """
        super().__init__(parent)
        self.preset_loader = preset_loader
        self.preset_data: Optional[Dict] = None

        self.setWindowTitle("Save Custom Preset")
        self.setMinimumWidth(500)
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Instructions
        instructions = QLabel(
            "<b>Save your current Prompt Builder settings as a reusable preset.</b><br>"
            "Give it a memorable name and description so you can easily find it later."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Form
        form_layout = QFormLayout()

        # Name (required)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., 'My Custom Style'")
        form_layout.addRow("Preset Name *:", self.name_edit)

        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Brief description of this preset...")
        self.description_edit.setMaximumHeight(60)
        form_layout.addRow("Description:", self.description_edit)

        # Category
        self.category_combo = QComboBox()
        categories = [
            "Custom",
            "Comics",
            "Digital",
            "Fine Art",
            "Anime",
            "Photography",
            "Vintage",
            "Modern",
            "Fantasy",
            "Other"
        ]
        self.category_combo.addItems(categories)
        form_layout.addRow("Category:", self.category_combo)

        # Icon selector
        self.icon_combo = QComboBox()
        icons = [
            "⭐ Star",
            "🎨 Palette",
            "🎭 Drama",
            "🌃 Night City",
            "🖼️ Frame",
            "📜 Scroll",
            "⚔️ Sword",
            "🌅 Sunrise",
            "💫 Sparkle",
            "🎪 Circus",
            "🏛️ Classical",
            "🌈 Rainbow",
            "🔮 Crystal",
            "🎬 Film",
            "📸 Camera"
        ]
        self.icon_combo.addItems(icons)
        form_layout.addRow("Icon:", self.icon_combo)

        # Tags
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("e.g., 'cyberpunk, neon, futuristic' (comma-separated)")
        form_layout.addRow("Tags:", self.tags_edit)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Preset")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _on_save(self):
        """Handle save button click."""
        # Validate name
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a preset name.")
            self.name_edit.setFocus()
            return

        # Get other fields
        description = self.description_edit.toPlainText().strip()
        category = self.category_combo.currentText()

        # Extract icon (first character/emoji before the space)
        icon_text = self.icon_combo.currentText()
        icon = icon_text.split()[0] if icon_text else "⭐"

        # Parse tags
        tags_text = self.tags_edit.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []

        # Store preset data for retrieval
        self.preset_data = {
            "name": name,
            "description": description,
            "category": category,
            "icon": icon,
            "tags": tags
        }

        # Accept dialog
        self.accept()

    def get_preset_data(self) -> Optional[Dict]:
        """Get the preset data entered by the user.

        Returns:
            Dictionary with preset metadata or None if dialog was cancelled
        """
        return self.preset_data


class PromptBuilder(QDialog):
    """Dialog for building image generation prompts with character transformation support."""

    prompt_generated = Signal(str)  # Emits the generated prompt

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize data loaders but don't load data yet
        self.data_loader = None
        self.preset_loader = None
        self.config = ConfigManager()
        self.tag_searcher = None

        # Settings for window position
        self.settings = QSettings("ImageAI", "PromptBuilder")

        # History file
        self.history_file = self.config.config_dir / "prompt_builder_history.json"
        self.history: List[Dict] = []

        # Store original combo box items for filter restoration
        self.original_combo_items: Dict[str, List[str]] = {}

        # Search debounce timer
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._execute_search)

        # Track if data has been loaded
        self._data_loaded = False
        self.presets_list = []

        self.setWindowTitle("Prompt Builder")
        self.setMinimumSize(900, 700)
        self._init_ui()
        self._restore_geometry()

    def _load_all_data(self):
        """Load all data from files (called when dialog is shown)."""
        if self._data_loaded:
            return

        logger.info("Loading Prompt Builder data...")

        # Load data loaders
        self.data_loader = PromptDataLoader()
        self.preset_loader = PresetLoader()
        self.tag_searcher = TagSearcher()

        # Load history
        self._load_history()

        # Populate combo boxes with data
        self._populate_combo_boxes()

        # Populate presets
        self._populate_presets()

        # Load example prompt
        self._load_example()

        self._data_loaded = True
        logger.info("Prompt Builder data loaded successfully")

    def _populate_combo_boxes(self):
        """Populate combo boxes with loaded data."""
        # Style
        styles = [""] + self.data_loader.get_styles()
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        self.style_combo.addItems(styles)
        self.style_combo.blockSignals(False)

        # Medium
        mediums = [""] + self.data_loader.get_mediums()
        self.medium_combo.blockSignals(True)
        self.medium_combo.clear()
        self.medium_combo.addItems(mediums)
        self.medium_combo.blockSignals(False)

        # Artist
        artists = [""] + self.data_loader.get_artists()
        self.artist_combo.blockSignals(True)
        self.artist_combo.clear()
        self.artist_combo.addItems(artists)
        self.artist_combo.blockSignals(False)

        # Lighting
        lighting = [""] + self.data_loader.get_lighting()
        self.lighting_combo.blockSignals(True)
        self.lighting_combo.clear()
        self.lighting_combo.addItems(lighting)
        self.lighting_combo.blockSignals(False)

        # Mood
        moods = [""] + self.data_loader.get_moods()
        self.mood_combo.blockSignals(True)
        self.mood_combo.clear()
        self.mood_combo.addItems(moods)
        self.mood_combo.blockSignals(False)

        logger.debug("Populated combo boxes with data")

    def _populate_presets(self):
        """Populate presets combo box with loaded presets."""
        # Load presets
        self.presets_list = self.preset_loader.get_presets(sort_by_popularity=True)

        # Block signals while populating
        self.preset_combo.blockSignals(True)

        # Clear existing items (except the placeholder at index 0)
        while self.preset_combo.count() > 1:
            self.preset_combo.removeItem(1)

        # Add presets to combobox
        for i, preset in enumerate(self.presets_list, start=1):
            icon = preset.get("icon", "⭐")
            name = preset.get("name", "Unnamed")
            category = preset.get("category", "")

            # Display format: "icon name (category)"
            display_text = f"{icon} {name}"
            if category:
                display_text += f" ({category})"

            self.preset_combo.addItem(display_text)

            # Set tooltip to description
            description = preset.get("description", "")
            self.preset_combo.setItemData(i, description, Qt.ToolTipRole)

        self.preset_combo.blockSignals(False)
        logger.debug(f"Populated {len(self.presets_list)} presets")

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

        # Preset panel
        preset_panel = self._create_preset_panel()
        builder_layout.addWidget(preset_panel)

        # Search panel
        search_panel = self._create_search_panel()
        builder_layout.addWidget(search_panel)

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

        # Style (from styles.json) - will be populated on show
        self.style_combo = self._create_combo([""])
        form_layout.addRow("Art Style:", self.style_combo)

        # Medium (from mediums.json) - will be populated on show
        self.medium_combo = self._create_combo([""])
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

        # Artist (from artists.json) - will be populated on show
        self.artist_combo = self._create_combo([""])
        form_layout.addRow("Artist Style:", self.artist_combo)

        # Lighting (from lighting.json) - will be populated on show
        self.lighting_combo = self._create_combo([""])
        form_layout.addRow("Lighting:", self.lighting_combo)

        # Mood (from moods.json) - will be populated on show
        self.mood_combo = self._create_combo([""])
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

    def _create_preset_panel(self) -> QGroupBox:
        """Create the preset panel with quick-start style combinations.

        Returns:
            QGroupBox containing the preset selector
        """
        preset_group = QGroupBox("🎨 Style Presets")

        # Layout
        layout = QHBoxLayout()

        # Label
        label = QLabel("Quick Start:")
        layout.addWidget(label)

        # Preset combobox
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(300)

        # Add empty/default option (presets will be loaded on show)
        self.preset_combo.addItem("-- Select a Style Preset --")
        self.preset_combo.setItemData(0, "Choose a preset to quickly populate all fields", Qt.ToolTipRole)

        # Connect signal
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)

        layout.addWidget(self.preset_combo)

        # Add "Save Custom Preset" button
        save_btn = QPushButton("💾 Save as Preset")
        save_btn.setToolTip("Save current settings as a custom preset")
        save_btn.clicked.connect(self._on_save_custom_preset)
        save_btn.setAutoDefault(False)  # Not the default action
        save_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #4CAF50;
                border-radius: 4px;
                background-color: #F1F8F4;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #E8F5E9;
            }
        """)
        layout.addWidget(save_btn)

        layout.addStretch()

        preset_group.setLayout(layout)
        return preset_group

    def _create_search_panel(self) -> QGroupBox:
        """Create the semantic search panel.

        Returns:
            QGroupBox containing the search bar and controls
        """
        search_group = QGroupBox("🔍 Smart Search")

        # Main layout
        layout = QVBoxLayout()

        # Top row: search bar and buttons
        search_row = QHBoxLayout()

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search artists, styles, moods... (e.g., 'Mad Magazine', 'cyberpunk', '1960s') - Press Enter or enable Auto-filter")
        self.search_input.setMinimumWidth(450)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._on_search_enter_pressed)
        search_row.addWidget(self.search_input, stretch=3)

        # Auto-filter checkbox
        self.auto_filter_check = QCheckBox("Auto-filter")
        self.auto_filter_check.setToolTip("Automatically filter as you type (300ms delay)")
        self.auto_filter_check.setChecked(True)  # Default: enabled for instant feedback
        self.auto_filter_check.stateChanged.connect(self._on_auto_filter_changed)
        search_row.addWidget(self.auto_filter_check)

        # Search button (manual trigger)
        self.search_btn = QPushButton("Search")
        self.search_btn.setToolTip("Filter dropdowns based on search query (or press Enter)")
        self.search_btn.setAutoDefault(False)
        self.search_btn.clicked.connect(self._trigger_manual_search)
        self.search_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 16px;
                border: 2px solid #2196F3;
                border-radius: 4px;
                background-color: #E3F2FD;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #BBDEFB;
            }
        """)
        search_row.addWidget(self.search_btn)

        # Clear filters button
        self.clear_filters_btn = QPushButton("Clear")
        self.clear_filters_btn.setToolTip("Restore all items and clear search")
        self.clear_filters_btn.setAutoDefault(False)
        self.clear_filters_btn.clicked.connect(self._clear_search_filters)
        self.clear_filters_btn.setEnabled(False)  # Disabled until search is active
        self.clear_filters_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 2px solid #757575;
                border-radius: 4px;
                background-color: #F5F5F5;
            }
            QPushButton:hover {
                background-color: #E0E0E0;
            }
            QPushButton:disabled {
                border-color: #BDBDBD;
                color: #9E9E9E;
            }
        """)
        search_row.addWidget(self.clear_filters_btn)

        layout.addLayout(search_row)

        # Result indicator label
        self.search_results_label = QLabel("💡 Tip: Type a search term to automatically filter results")
        self.search_results_label.setStyleSheet("color: #666; font-style: italic; padding: 4px;")
        layout.addWidget(self.search_results_label)

        search_group.setLayout(layout)
        return search_group

    def _on_preset_selected(self, index: int):
        """Handle preset combobox selection.

        Args:
            index: Selected index in combobox
        """
        # Index 0 is the placeholder "-- Select a Style Preset --"
        if index == 0:
            return

        try:
            # Get preset from list (index - 1 because of placeholder at 0)
            preset_index = index - 1
            if 0 <= preset_index < len(self.presets_list):
                preset = self.presets_list[preset_index]

                # Load preset settings
                self._load_preset(preset)

                # Show notification
                preset_name = preset.get("name", "Preset")
                logger.info(f"Loaded preset: {preset_name}")

                # Update preview
                self._update_preview()

                # Reset combobox to placeholder after loading
                # Use blockSignals to prevent triggering the signal again
                self.preset_combo.blockSignals(True)
                self.preset_combo.setCurrentIndex(0)
                self.preset_combo.blockSignals(False)

        except Exception as e:
            logger.error(f"Error loading preset: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load preset:\n{e}")

    def _load_preset(self, preset: Dict):
        """Load a preset's settings into the prompt builder.

        Args:
            preset: The preset dictionary containing settings
        """
        settings = preset.get("settings", {})

        # Apply settings using the existing _apply_settings method
        self._apply_settings(settings)

        logger.info(f"Applied preset: {preset.get('name', 'Unknown')}")

    def _on_save_custom_preset(self):
        """Show dialog to save current settings as a custom preset."""
        try:
            # Ensure data is loaded
            if not self._data_loaded or not self.preset_loader:
                QMessageBox.warning(self, "Not Ready", "Data is still loading. Please wait a moment and try again.")
                return

            # Show save preset dialog
            dialog = SavePresetDialog(self.preset_loader, self)
            if dialog.exec() == QDialog.Accepted:
                preset_data = dialog.get_preset_data()

                if not preset_data:
                    return

                # Collect current settings from all combos
                current_settings = {
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

                # Remove empty settings to keep preset lean
                current_settings = {k: v for k, v in current_settings.items() if v}

                # Save the preset
                success = self.preset_loader.save_custom_preset(
                    name=preset_data["name"],
                    settings=current_settings,
                    description=preset_data.get("description", ""),
                    category=preset_data.get("category", "Custom"),
                    icon=preset_data.get("icon", "⭐"),
                    tags=preset_data.get("tags", []),
                    popularity=5
                )

                if success:
                    # Reload presets to show the new one immediately
                    self._populate_presets()

                    QMessageBox.information(
                        self,
                        "Preset Saved",
                        f"Custom preset '{preset_data['name']}' has been saved successfully!\n\n"
                        "Your new preset is now available in the dropdown."
                    )
                    logger.info(f"Saved custom preset: {preset_data['name']}")
                else:
                    QMessageBox.warning(
                        self,
                        "Save Failed",
                        "Failed to save custom preset. Check the log for details."
                    )

        except Exception as e:
            logger.error(f"Error saving custom preset: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while saving the preset:\n{e}"
            )

    def _apply_settings(self, settings: Dict):
        """Apply settings from history or preset.

        Args:
            settings: Dictionary of prompt builder settings
        """
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

    def _save_combo_items(self):
        """Save original combo box items for filter restoration."""
        if not self._data_loaded:
            return

        # Map category names to combo boxes
        combo_mapping = {
            'artists': self.artist_combo,
            'styles': self.style_combo,
            'mediums': self.medium_combo,
            'lighting': self.lighting_combo,
            'moods': self.mood_combo
        }

        for category, combo in combo_mapping.items():
            items = [combo.itemText(i) for i in range(combo.count())]
            self.original_combo_items[category] = items

        logger.debug("Saved original combo items for search filtering")

    def _on_search_text_changed(self, text: str):
        """Handle search text changes.

        Args:
            text: Current search text
        """
        # Clear search if text is empty
        if not text or not text.strip():
            self.search_timer.stop()
            if self.original_combo_items:  # Only clear if we've filtered before
                self._clear_search_filters()
            else:
                # Just update the tip label
                self.search_results_label.setText("💡 Tip: Type a search term to automatically filter results")
            return

        # If auto-filter is enabled, use debounced search
        if self.auto_filter_check.isChecked():
            self.search_timer.stop()
            self.search_timer.start(300)  # 300ms delay
            self.search_results_label.setText("⏱️ Typing...")
        else:
            # Manual mode - just show instruction
            self.search_results_label.setText(f"💡 Press Enter or click Search to filter results for '{text.strip()}'")

    def _on_auto_filter_changed(self, state: int):
        """Handle auto-filter checkbox state change.

        Args:
            state: Checkbox state
        """
        if state == Qt.Checked:
            # Auto-filter enabled - trigger search if there's text
            text = self.search_input.text().strip()
            if text:
                self.search_timer.stop()
                self.search_timer.start(300)
                self.search_results_label.setText("⏱️ Auto-filter enabled, searching...")
        else:
            # Auto-filter disabled - stop any pending search
            self.search_timer.stop()
            text = self.search_input.text().strip()
            if text:
                self.search_results_label.setText(f"💡 Enable Auto-filter or press Enter to search for '{text}'")
            else:
                self.search_results_label.setText("💡 Tip: Type a search term to automatically filter results")

    def _on_search_enter_pressed(self):
        """Handle Enter key pressed in search box."""
        self._trigger_manual_search()

    def _trigger_manual_search(self):
        """Manually trigger search (from button or Enter key)."""
        self.search_timer.stop()  # Cancel any pending auto-search
        text = self.search_input.text().strip()
        if text:
            self.search_results_label.setText("🔍 Searching...")
            self._execute_search()
        else:
            self.search_results_label.setText("⚠️ Please enter a search term")

    def _execute_search(self):
        """Execute the search (called by timer or manual trigger)."""
        text = self.search_input.text().strip()
        if text:
            self._perform_search(text)

    def _perform_search(self, query: str):
        """Perform semantic search and filter combo boxes.

        Args:
            query: Search query
        """
        try:
            # Ensure data is loaded
            if not self._data_loaded:
                logger.warning("Search attempted before data loaded")
                self.search_results_label.setText("⚠️ Loading data, please wait...")
                return

            # Save original items if not already saved
            if not self.original_combo_items:
                self._save_combo_items()
                logger.info("Saved original combo items before first search")

            if not self.tag_searcher or not self.tag_searcher.loaded:
                logger.warning("Tag searcher not loaded, cannot perform search")
                self.search_results_label.setText("⚠️ Search unavailable (metadata not loaded)")
                return

            # Search across all categories
            logger.debug(f"Performing search for: '{query}'")
            results_by_category = self.tag_searcher.search_by_category(
                query=query,
                max_per_category=50,  # Show up to 50 results per category
                min_score=5.0
            )

            # Map category names to combo boxes
            combo_mapping = {
                'artists': self.artist_combo,
                'styles': self.style_combo,
                'mediums': self.medium_combo,
                'lighting': self.lighting_combo,
                'moods': self.mood_combo
            }

            # Filter each combo box
            total_results = 0
            results_text_parts = []

            for category, combo in combo_mapping.items():
                if category in results_by_category:
                    results = results_by_category[category]
                    matched_items = [r.item for r in results]

                    # Add empty option if not present
                    if "" not in matched_items:
                        matched_items.insert(0, "")

                    # Update combo with filtered items
                    current_text = combo.currentText()
                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItems(matched_items)

                    # Restore selection if still available
                    if current_text in matched_items:
                        combo.setCurrentText(current_text)
                    else:
                        combo.setCurrentIndex(0)

                    combo.blockSignals(False)

                    # Track results
                    total_results += len(results)
                    category_display = category.capitalize()
                    results_text_parts.append(f"{category_display} ({len(results)})")
                    logger.debug(f"  {category}: {len(results)} results")

                else:
                    # No results for this category - show only empty option
                    current_text = combo.currentText()
                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItem("")
                    combo.blockSignals(False)
                    logger.debug(f"  {category}: 0 results")

            # Update results label
            if total_results > 0:
                results_summary = ", ".join(results_text_parts)
                self.search_results_label.setText(f"✓ Found {total_results} items: {results_summary}")
                self.clear_filters_btn.setEnabled(True)
                logger.info(f"Search '{query}' found {total_results} results across {len(results_text_parts)} categories")
            else:
                self.search_results_label.setText(f"❌ No results found for '{query}'")
                self.clear_filters_btn.setEnabled(True)
                logger.info(f"Search '{query}' returned no results")

            # Force UI update
            self.search_results_label.repaint()

        except Exception as e:
            logger.error(f"Error performing search: {e}", exc_info=True)
            self.search_results_label.setText(f"⚠️ Search error: {str(e)}")
            QMessageBox.warning(self, "Search Error", f"An error occurred during search:\n{e}")

    def _clear_search_filters(self):
        """Clear search filters and restore all combo box items."""
        try:
            if not self.original_combo_items:
                # Nothing to restore
                self.search_results_label.setText("💡 Tip: Type a search term and press Enter, or enable Auto-filter")
                self.clear_filters_btn.setEnabled(False)
                return

            # Map category names to combo boxes
            combo_mapping = {
                'artists': self.artist_combo,
                'styles': self.style_combo,
                'mediums': self.medium_combo,
                'lighting': self.lighting_combo,
                'moods': self.mood_combo
            }

            # Restore original items
            for category, combo in combo_mapping.items():
                if category in self.original_combo_items:
                    original_items = self.original_combo_items[category]
                    current_text = combo.currentText()

                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItems(original_items)

                    # Restore selection if still available
                    if current_text in original_items:
                        combo.setCurrentText(current_text)
                    else:
                        combo.setCurrentIndex(0)

                    combo.blockSignals(False)

            # Clear search input and results label
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)

            self.search_results_label.setText("💡 Tip: Type a search term to automatically filter results")
            self.clear_filters_btn.setEnabled(False)

            logger.info("Cleared search filters and restored all items")

        except Exception as e:
            logger.error(f"Error clearing filters: {e}", exc_info=True)
            self.search_results_label.setText(f"⚠️ Error clearing filters: {str(e)}")

    def showEvent(self, event):
        """Handle show event to load data on first display."""
        super().showEvent(event)
        # Load data on first show
        if not self._data_loaded:
            self._load_all_data()

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
