"""Inspector panel for editing block properties."""

import logging
from typing import Optional, Union
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QComboBox, QSpinBox,
    QGroupBox, QScrollArea, QFileDialog, QColorDialog, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from core.config import ConfigManager
from core.layout.models import PageSpec, TextBlock, ImageBlock, TextStyle, ImageStyle, DocumentSpec

logger = logging.getLogger(__name__)


class InspectorWidget(QWidget):
    """Widget for inspecting and editing block properties."""

    blockModified = Signal()  # Emitted when block properties are modified

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_page: Optional[PageSpec] = None
        self.current_block_id: Optional[str] = None
        self.current_block: Optional[Union[TextBlock, ImageBlock]] = None

        # Context for LLM generation
        self.config: Optional[ConfigManager] = None
        self.document: Optional[DocumentSpec] = None
        self.template_category: str = "children"
        self.template_name: str = ""
        self.page_number: int = 1
        self.total_pages: int = 1
        self.llm_provider: Optional[str] = None
        self.llm_model: Optional[str] = None

        self.init_ui()
        self.clear_inspector()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header_label = QLabel("Inspector")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 8px;")
        layout.addWidget(header_label)

        # Scroll area for properties
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container for properties
        self.properties_container = QWidget()
        self.properties_layout = QVBoxLayout(self.properties_container)
        self.properties_layout.setAlignment(Qt.AlignTop)

        scroll_area.setWidget(self.properties_container)
        layout.addWidget(scroll_area, 1)

        # Apply button at bottom
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.apply_changes)
        self.apply_btn.setEnabled(False)
        layout.addWidget(self.apply_btn)

    def set_context(self, config: ConfigManager, document: Optional[DocumentSpec],
                   template_category: str, template_name: str,
                   page_number: int, total_pages: int,
                   llm_provider: Optional[str] = None, llm_model: Optional[str] = None):
        """Set the context for LLM generation."""
        self.config = config
        self.document = document
        self.template_category = template_category
        self.template_name = template_name
        self.page_number = page_number
        self.total_pages = total_pages
        self.llm_provider = llm_provider
        self.llm_model = llm_model

    def set_block(self, page: PageSpec, block_id: str):
        """Set the block to inspect."""
        self.current_page = page
        self.current_block_id = block_id

        # Find the block
        self.current_block = None
        for block in page.blocks:
            if block.id == block_id:
                self.current_block = block
                break

        if self.current_block:
            logger.info(f"Inspecting block: {block_id} ({type(self.current_block).__name__})")
            self.display_block_properties()
        else:
            logger.warning(f"Block not found: {block_id}")
            self.clear_inspector()

    def clear_inspector(self):
        """Clear the inspector (no block selected)."""
        self.current_page = None
        self.current_block_id = None
        self.current_block = None

        # Clear properties layout
        while self.properties_layout.count():
            item = self.properties_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Show "no selection" message
        no_selection_label = QLabel("No block selected\n\nClick a block on the canvas to inspect it.")
        no_selection_label.setAlignment(Qt.AlignCenter)
        no_selection_label.setStyleSheet("color: #999; padding: 40px 20px;")
        no_selection_label.setWordWrap(True)
        self.properties_layout.addWidget(no_selection_label)

        self.apply_btn.setEnabled(False)

    def display_block_properties(self):
        """Display properties for the current block."""
        # Clear existing widgets
        while self.properties_layout.count():
            item = self.properties_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.current_block:
            return

        # Block info
        info_group = QGroupBox("Block Info")
        info_layout = QFormLayout()

        info_layout.addRow("ID:", QLabel(self.current_block.id))
        info_layout.addRow("Type:", QLabel(type(self.current_block).__name__))

        info_group.setLayout(info_layout)
        self.properties_layout.addWidget(info_group)

        # Position and size
        position_group = QGroupBox("Position & Size")
        position_layout = QFormLayout()

        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 10000)
        self.x_spin.setValue(self.current_block.rect[0])  # rect is tuple: (x, y, width, height)
        position_layout.addRow("X:", self.x_spin)

        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 10000)
        self.y_spin.setValue(self.current_block.rect[1])
        position_layout.addRow("Y:", self.y_spin)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10000)
        self.width_spin.setValue(self.current_block.rect[2])
        position_layout.addRow("Width:", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 10000)
        self.height_spin.setValue(self.current_block.rect[3])
        position_layout.addRow("Height:", self.height_spin)

        position_group.setLayout(position_layout)
        self.properties_layout.addWidget(position_group)

        # Type-specific properties
        if isinstance(self.current_block, TextBlock):
            self.display_text_block_properties()
        elif isinstance(self.current_block, ImageBlock):
            self.display_image_block_properties()

        self.apply_btn.setEnabled(True)

    def display_text_block_properties(self):
        """Display properties specific to text blocks."""
        if not isinstance(self.current_block, TextBlock):
            return

        # Content
        content_group = QGroupBox("Text Content")
        content_layout = QVBoxLayout()

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.current_block.text)
        self.text_edit.setMaximumHeight(150)
        content_layout.addWidget(self.text_edit)

        # Generate text button (future)
        generate_btn = QPushButton("Generate with LLM")
        generate_btn.setToolTip("Use LLM to generate text for this block")
        generate_btn.clicked.connect(self.generate_text)
        content_layout.addWidget(generate_btn)

        content_group.setLayout(content_layout)
        self.properties_layout.addWidget(content_group)

        # Style
        style_group = QGroupBox("Text Style")
        style_layout = QFormLayout()

        # Font family
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems([
            "Arial", "Helvetica", "Times New Roman", "Georgia",
            "Courier New", "Verdana", "Comic Sans MS", "Impact"
        ])
        if self.current_block.style.family:
            font_name = self.current_block.style.family[0] if self.current_block.style.family else "Arial"
            index = self.font_family_combo.findText(font_name, Qt.MatchContains)
            if index >= 0:
                self.font_family_combo.setCurrentIndex(index)
        style_layout.addRow("Font:", self.font_family_combo)

        # Font size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 200)
        self.font_size_spin.setValue(self.current_block.style.size_px)
        style_layout.addRow("Size (px):", self.font_size_spin)

        # Font weight
        self.font_weight_combo = QComboBox()
        self.font_weight_combo.addItems(["light", "regular", "medium", "bold", "black"])
        self.font_weight_combo.setCurrentText(self.current_block.style.weight)
        style_layout.addRow("Weight:", self.font_weight_combo)

        # Italic
        self.italic_check = QCheckBox("Italic")
        self.italic_check.setChecked(self.current_block.style.italic)
        style_layout.addRow("", self.italic_check)

        # Color
        color_layout = QHBoxLayout()
        self.color_input = QLineEdit(self.current_block.style.color)
        self.color_input.setMaximumWidth(100)
        color_layout.addWidget(self.color_input)

        color_btn = QPushButton("Choose...")
        color_btn.clicked.connect(self.choose_text_color)
        color_layout.addWidget(color_btn)
        color_layout.addStretch()

        style_layout.addRow("Color:", color_layout)

        # Alignment
        self.align_combo = QComboBox()
        self.align_combo.addItems(["left", "center", "right", "justify"])
        self.align_combo.setCurrentText(self.current_block.style.align)
        style_layout.addRow("Align:", self.align_combo)

        style_group.setLayout(style_layout)
        self.properties_layout.addWidget(style_group)

    def display_image_block_properties(self):
        """Display properties specific to image blocks."""
        if not isinstance(self.current_block, ImageBlock):
            return

        # Image source
        source_group = QGroupBox("Image Source")
        source_layout = QVBoxLayout()

        self.image_path_input = QLineEdit(self.current_block.image_path or "")
        self.image_path_input.setPlaceholderText("No image selected")
        source_layout.addWidget(self.image_path_input)

        # Source buttons
        btn_layout = QHBoxLayout()

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_image)
        btn_layout.addWidget(browse_btn)

        history_btn = QPushButton("From History")
        history_btn.setToolTip("Select from generated images")
        history_btn.clicked.connect(self.select_from_history)
        btn_layout.addWidget(history_btn)

        generate_btn = QPushButton("Generate New")
        generate_btn.setToolTip("Generate a new image")
        generate_btn.clicked.connect(self.generate_image)
        btn_layout.addWidget(generate_btn)

        source_layout.addLayout(btn_layout)

        source_group.setLayout(source_layout)
        self.properties_layout.addWidget(source_group)

        # Style
        style_group = QGroupBox("Image Style")
        style_layout = QFormLayout()

        # Fit mode
        self.fit_combo = QComboBox()
        self.fit_combo.addItems(["cover", "contain", "fill", "fit_width", "fit_height"])
        self.fit_combo.setCurrentText(self.current_block.style.fit)
        style_layout.addRow("Fit:", self.fit_combo)

        # Border radius
        self.border_radius_spin = QSpinBox()
        self.border_radius_spin.setRange(0, 500)
        self.border_radius_spin.setValue(self.current_block.style.border_radius_px)
        style_layout.addRow("Radius (px):", self.border_radius_spin)

        # Stroke
        self.stroke_width_spin = QSpinBox()
        self.stroke_width_spin.setRange(0, 100)
        self.stroke_width_spin.setValue(self.current_block.style.stroke_px)
        style_layout.addRow("Stroke (px):", self.stroke_width_spin)

        # Stroke color
        stroke_color_layout = QHBoxLayout()
        self.stroke_color_input = QLineEdit(self.current_block.style.stroke_color)
        self.stroke_color_input.setMaximumWidth(100)
        stroke_color_layout.addWidget(self.stroke_color_input)

        stroke_color_btn = QPushButton("Choose...")
        stroke_color_btn.clicked.connect(self.choose_stroke_color)
        stroke_color_layout.addWidget(stroke_color_btn)
        stroke_color_layout.addStretch()

        style_layout.addRow("Stroke Color:", stroke_color_layout)

        style_group.setLayout(style_layout)
        self.properties_layout.addWidget(style_group)

    def apply_changes(self):
        """Apply changes to the current block."""
        if not self.current_block:
            return

        try:
            # Update position and size (rect is immutable tuple, so create new one)
            self.current_block.rect = (
                self.x_spin.value(),
                self.y_spin.value(),
                self.width_spin.value(),
                self.height_spin.value()
            )

            # Update type-specific properties
            if isinstance(self.current_block, TextBlock):
                self.apply_text_block_changes()
            elif isinstance(self.current_block, ImageBlock):
                self.apply_image_block_changes()

            logger.info(f"Applied changes to block: {self.current_block.id}")
            self.blockModified.emit()

        except Exception as e:
            logger.error(f"Failed to apply changes: {e}", exc_info=True)

    def apply_text_block_changes(self):
        """Apply changes to text block."""
        if not isinstance(self.current_block, TextBlock):
            return

        self.current_block.text = self.text_edit.toPlainText()
        self.current_block.style.family = [self.font_family_combo.currentText()]
        self.current_block.style.size_px = self.font_size_spin.value()
        self.current_block.style.weight = self.font_weight_combo.currentText()
        self.current_block.style.italic = self.italic_check.isChecked()
        self.current_block.style.color = self.color_input.text()
        self.current_block.style.align = self.align_combo.currentText()

    def apply_image_block_changes(self):
        """Apply changes to image block."""
        if not isinstance(self.current_block, ImageBlock):
            return

        self.current_block.image_path = self.image_path_input.text() or None
        self.current_block.style.fit = self.fit_combo.currentText()
        self.current_block.style.border_radius_px = self.border_radius_spin.value()
        self.current_block.style.stroke_px = self.stroke_width_spin.value()
        self.current_block.style.stroke_color = self.stroke_color_input.text()

    def choose_text_color(self):
        """Open color picker for text color."""
        current_color = QColor(self.color_input.text())
        color = QColorDialog.getColor(current_color, self, "Choose Text Color")
        if color.isValid():
            self.color_input.setText(color.name())

    def choose_stroke_color(self):
        """Open color picker for stroke color."""
        current_color = QColor(self.stroke_color_input.text())
        color = QColorDialog.getColor(current_color, self, "Choose Stroke Color")
        if color.isValid():
            self.stroke_color_input.setText(color.name())

    def browse_image(self):
        """Browse for an image file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.gif);;All Files (*.*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        if file_path:
            self.image_path_input.setText(file_path)

    def select_from_history(self):
        """Select image from generation history."""
        if not self.config:
            logger.warning("Cannot open history: ConfigManager not set")
            return

        from gui.layout.image_history_dialog import ImageHistoryDialog

        dialog = ImageHistoryDialog(self.config, self)
        if dialog.exec() == dialog.Accepted:
            selected_path = dialog.get_selected_image()
            if selected_path:
                self.image_path_input.setText(selected_path)
                logger.info(f"Selected image from history: {selected_path}")

    def generate_image(self):
        """Generate a new image by switching to the Generate tab."""
        # Signal to parent (layout_tab) to switch to Generate tab
        # Find the main window and switch tabs
        from gui.main_window import MainWindow

        parent = self.parent()
        while parent:
            if isinstance(parent, MainWindow):
                # Switch to Generate tab (index 0)
                parent.tab_widget.setCurrentIndex(0)
                logger.info("Switched to Generate tab for image generation")
                return
            parent = parent.parent()

        logger.warning("Could not find MainWindow to switch tabs")

    def generate_text(self):
        """Generate text with LLM."""
        if not isinstance(self.current_block, TextBlock):
            logger.warning("Cannot generate text: current block is not a TextBlock")
            return

        if not self.config:
            logger.warning("Cannot generate text: ConfigManager not set")
            return

        logger.info("Opening text generation dialog...")

        # Import here to avoid circular imports
        from gui.layout.text_gen_dialog import TextGenerationDialog

        # Create and show dialog
        dialog = TextGenerationDialog(
            config=self.config,
            block=self.current_block,
            document=self.document,
            template_category=self.template_category,
            template_name=self.template_name,
            page_number=self.page_number,
            total_pages=self.total_pages,
            provider=self.llm_provider,
            model=self.llm_model,
            parent=self
        )

        if dialog.exec():
            # User accepted - apply generated text
            generated_text = dialog.get_generated_text()
            if generated_text:
                logger.info(f"Applying generated text ({len(generated_text)} chars)")
                self.text_edit.setPlainText(generated_text)
                self.apply_btn.setEnabled(True)
            else:
                logger.warning("No text generated")
        else:
            logger.info("Text generation cancelled")
