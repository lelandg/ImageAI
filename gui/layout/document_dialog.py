"""Document Properties Dialog for Layout/Books module.

Allows editing document metadata, page settings, and theme configuration.
"""

import logging
from typing import Optional, Dict, Tuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QComboBox, QGroupBox, QFormLayout,
    QTabWidget, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QColorDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.layout.models import DocumentSpec

logger = logging.getLogger(__name__)


# Standard page sizes in pixels at 300 DPI
PAGE_SIZES = {
    "A4 Portrait (210×297mm)": (2480, 3508),
    "A4 Landscape (297×210mm)": (3508, 2480),
    "Letter Portrait (8.5×11in)": (2550, 3300),
    "Letter Landscape (11×8.5in)": (3300, 2550),
    "Legal Portrait (8.5×14in)": (2550, 4200),
    "A5 Portrait (148×210mm)": (1748, 2480),
    "A3 Portrait (297×420mm)": (3508, 4961),
    "Tabloid (11×17in)": (3300, 5100),
    "Square (2480×2480px)": (2480, 2480),
    "Custom": (0, 0)  # Placeholder for custom size
}


class DocumentPropertiesDialog(QDialog):
    """Dialog for editing document properties."""

    def __init__(self, document: DocumentSpec, parent=None):
        super().__init__(parent)
        self.document = document
        self.init_ui()

        # Load current document properties
        self.load_properties()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Document Properties")
        self.setMinimumSize(600, 500)

        # Main layout
        main_layout = QVBoxLayout(self)

        # Tab widget for different property categories
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Create tabs
        self.create_general_tab()
        self.create_page_settings_tab()
        self.create_theme_tab()
        self.create_metadata_tab()

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def create_general_tab(self):
        """Create the General tab with document title and author."""
        tab = QWidget()
        layout = QFormLayout(tab)

        # Title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Enter document title...")
        layout.addRow("Title:", self.title_edit)

        # Author
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Enter author name...")
        layout.addRow("Author:", self.author_edit)

        # Template (read-only)
        self.template_label = QLabel()
        layout.addRow("Template:", self.template_label)

        # Number of pages (read-only)
        self.pages_label = QLabel()
        layout.addRow("Pages:", self.pages_label)

        # Spacer
        layout.addRow("", QLabel())

        # Help text
        help_label = QLabel(
            "The title and author will be embedded in exported files "
            "and shown in the document header."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addRow(help_label)

        self.tabs.addTab(tab, "General")

    def create_page_settings_tab(self):
        """Create the Page Settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Page size group
        size_group = QGroupBox("Page Size")
        size_layout = QFormLayout(size_group)

        # Page size preset
        self.page_size_combo = QComboBox()
        for size_name in PAGE_SIZES.keys():
            self.page_size_combo.addItem(size_name)
        self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)
        size_layout.addRow("Preset:", self.page_size_combo)

        # Custom width
        self.custom_width_spin = QSpinBox()
        self.custom_width_spin.setRange(100, 10000)
        self.custom_width_spin.setSuffix(" px")
        self.custom_width_spin.setEnabled(False)
        size_layout.addRow("Width:", self.custom_width_spin)

        # Custom height
        self.custom_height_spin = QSpinBox()
        self.custom_height_spin.setRange(100, 10000)
        self.custom_height_spin.setSuffix(" px")
        self.custom_height_spin.setEnabled(False)
        size_layout.addRow("Height:", self.custom_height_spin)

        layout.addWidget(size_group)

        # Margins group
        margins_group = QGroupBox("Margins & Bleed")
        margins_layout = QFormLayout(margins_group)

        # Margin
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 500)
        self.margin_spin.setSuffix(" px")
        self.margin_spin.setValue(64)
        margins_layout.addRow("Margin:", self.margin_spin)

        # Bleed
        self.bleed_spin = QSpinBox()
        self.bleed_spin.setRange(0, 100)
        self.bleed_spin.setSuffix(" px")
        self.bleed_spin.setValue(0)
        margins_layout.addRow("Bleed:", self.bleed_spin)

        layout.addWidget(margins_group)

        # Help text
        help_label = QLabel(
            "Note: Changing page size will apply to all pages in the document. "
            "Margins define the safe area for content. Bleed extends content "
            "beyond the page edge for professional printing."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(help_label)

        layout.addStretch()

        self.tabs.addTab(tab, "Page Settings")

    def create_theme_tab(self):
        """Create the Theme tab for color palette configuration."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Theme group
        theme_group = QGroupBox("Color Palette")
        theme_layout = QFormLayout(theme_group)

        # Create color pickers for common theme colors
        self.theme_colors = {}

        color_names = [
            ("Primary Color", "primary"),
            ("Secondary Color", "secondary"),
            ("Accent Color", "accent"),
            ("Background Color", "background"),
            ("Text Color", "text_color")
        ]

        for label, key in color_names:
            color_button = QPushButton()
            color_button.setFixedSize(80, 30)
            color_button.clicked.connect(
                lambda checked, k=key: self.pick_theme_color(k)
            )
            self.theme_colors[key] = color_button
            theme_layout.addRow(f"{label}:", color_button)

        layout.addWidget(theme_group)

        # Variables table
        variables_group = QGroupBox("Theme Variables")
        variables_layout = QVBoxLayout(variables_group)

        self.variables_table = QTableWidget(0, 2)
        self.variables_table.setHorizontalHeaderLabels(["Variable Name", "Value"])
        self.variables_table.horizontalHeader().setStretchLastSection(True)
        variables_layout.addWidget(self.variables_table)

        # Add/Remove buttons
        button_layout = QHBoxLayout()
        add_var_button = QPushButton("Add Variable")
        add_var_button.clicked.connect(self.add_variable_row)
        remove_var_button = QPushButton("Remove Selected")
        remove_var_button.clicked.connect(self.remove_variable_row)
        button_layout.addWidget(add_var_button)
        button_layout.addWidget(remove_var_button)
        button_layout.addStretch()
        variables_layout.addLayout(button_layout)

        layout.addWidget(variables_group)

        # Help text
        help_label = QLabel(
            "Theme colors and variables are used throughout the document. "
            "You can reference variables in templates using {{variable_name}} syntax."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(help_label)

        layout.addStretch()

        self.tabs.addTab(tab, "Theme")

    def create_metadata_tab(self):
        """Create the Metadata tab for custom metadata."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Metadata table
        metadata_group = QGroupBox("Custom Metadata")
        metadata_layout = QVBoxLayout(metadata_group)

        self.metadata_table = QTableWidget(0, 2)
        self.metadata_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.metadata_table.horizontalHeader().setStretchLastSection(True)
        metadata_layout.addWidget(self.metadata_table)

        # Add/Remove buttons
        button_layout = QHBoxLayout()
        add_meta_button = QPushButton("Add Metadata")
        add_meta_button.clicked.connect(self.add_metadata_row)
        remove_meta_button = QPushButton("Remove Selected")
        remove_meta_button.clicked.connect(self.remove_metadata_row)
        button_layout.addWidget(add_meta_button)
        button_layout.addWidget(remove_meta_button)
        button_layout.addStretch()
        metadata_layout.addLayout(button_layout)

        layout.addWidget(metadata_group)

        # Help text
        help_label = QLabel(
            "Custom metadata can store additional information about your document "
            "such as creation date, project number, client name, etc."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(help_label)

        layout.addStretch()

        self.tabs.addTab(tab, "Metadata")

    def load_properties(self):
        """Load current document properties into the dialog."""
        # General tab
        self.title_edit.setText(self.document.title or "")
        self.author_edit.setText(self.document.author or "")

        template_name = self.document.metadata.get("template", "Unknown")
        self.template_label.setText(template_name)
        self.pages_label.setText(str(len(self.document.pages)))

        # Page settings tab
        if self.document.pages:
            first_page = self.document.pages[0]
            page_size = first_page.page_size_px

            # Try to match a preset
            preset_found = False
            for preset_name, preset_size in PAGE_SIZES.items():
                if preset_size == page_size and preset_name != "Custom":
                    self.page_size_combo.setCurrentText(preset_name)
                    preset_found = True
                    break

            if not preset_found:
                self.page_size_combo.setCurrentText("Custom")
                self.custom_width_spin.setValue(page_size[0])
                self.custom_height_spin.setValue(page_size[1])

            self.margin_spin.setValue(first_page.margin_px)
            self.bleed_spin.setValue(first_page.bleed_px)

        # Theme tab
        for key, button in self.theme_colors.items():
            color_hex = self.document.theme.get(key, "#FFFFFF")
            self.set_button_color(button, color_hex)

        # Load theme variables (non-color entries)
        self.variables_table.setRowCount(0)
        for var_name, var_value in self.document.theme.items():
            if var_name not in self.theme_colors:
                self.add_variable_row(var_name, var_value)

        # Metadata tab
        self.metadata_table.setRowCount(0)
        # Skip 'template' key as it's shown in General tab
        for key, value in self.document.metadata.items():
            if key != "template":
                self.add_metadata_row(key, value)

    def save_properties(self):
        """Save dialog properties back to the document."""
        # General tab
        self.document.title = self.title_edit.text()
        self.document.author = self.author_edit.text() or None

        # Page settings tab - apply to all pages
        if self.document.pages:
            page_size = self.get_selected_page_size()
            margin = self.margin_spin.value()
            bleed = self.bleed_spin.value()

            for page in self.document.pages:
                page.page_size_px = page_size
                page.margin_px = margin
                page.bleed_px = bleed

        # Theme tab - rebuild theme dictionary
        new_theme = {}

        # Add color values
        for key, button in self.theme_colors.items():
            color_hex = self.get_button_color(button)
            new_theme[key] = color_hex

        # Add custom variables
        for row in range(self.variables_table.rowCount()):
            var_name = self.variables_table.item(row, 0).text()
            var_value = self.variables_table.item(row, 1).text()
            if var_name:  # Only add non-empty names
                new_theme[var_name] = var_value

        self.document.theme = new_theme

        # Metadata tab - rebuild metadata dictionary
        new_metadata = {}

        # Preserve template key
        if "template" in self.document.metadata:
            new_metadata["template"] = self.document.metadata["template"]

        # Add custom metadata
        for row in range(self.metadata_table.rowCount()):
            key = self.metadata_table.item(row, 0).text()
            value = self.metadata_table.item(row, 1).text()
            if key:  # Only add non-empty keys
                new_metadata[key] = value

        self.document.metadata = new_metadata

        logger.info(f"Document properties updated: title='{self.document.title}', author='{self.document.author}'")

    def get_selected_page_size(self) -> Tuple[int, int]:
        """Get the currently selected page size."""
        preset_name = self.page_size_combo.currentText()

        if preset_name == "Custom":
            return (self.custom_width_spin.value(), self.custom_height_spin.value())
        else:
            return PAGE_SIZES[preset_name]

    def on_page_size_changed(self, preset_name: str):
        """Handle page size preset change."""
        is_custom = preset_name == "Custom"
        self.custom_width_spin.setEnabled(is_custom)
        self.custom_height_spin.setEnabled(is_custom)

        if not is_custom:
            # Update custom spinboxes to show preset values
            width, height = PAGE_SIZES[preset_name]
            if width > 0:  # Not the placeholder custom entry
                self.custom_width_spin.setValue(width)
                self.custom_height_spin.setValue(height)

    def pick_theme_color(self, color_key: str):
        """Open color picker for a theme color."""
        button = self.theme_colors[color_key]
        current_color_hex = self.get_button_color(button)
        current_color = QColor(current_color_hex)

        color = QColorDialog.getColor(current_color, self, f"Select {color_key.replace('_', ' ').title()}")
        if color.isValid():
            self.set_button_color(button, color.name())

    def set_button_color(self, button: QPushButton, color_hex: str):
        """Set a button's background color."""
        button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #999;")
        button.setProperty("color_value", color_hex)

    def get_button_color(self, button: QPushButton) -> str:
        """Get a button's stored color value."""
        return button.property("color_value") or "#FFFFFF"

    def add_variable_row(self, var_name: str = "", var_value: str = ""):
        """Add a row to the variables table."""
        row = self.variables_table.rowCount()
        self.variables_table.insertRow(row)
        self.variables_table.setItem(row, 0, QTableWidgetItem(var_name))
        self.variables_table.setItem(row, 1, QTableWidgetItem(var_value))

    def remove_variable_row(self):
        """Remove selected row from variables table."""
        current_row = self.variables_table.currentRow()
        if current_row >= 0:
            self.variables_table.removeRow(current_row)

    def add_metadata_row(self, key: str = "", value: str = ""):
        """Add a row to the metadata table."""
        row = self.metadata_table.rowCount()
        self.metadata_table.insertRow(row)
        self.metadata_table.setItem(row, 0, QTableWidgetItem(key))
        self.metadata_table.setItem(row, 1, QTableWidgetItem(value))

    def remove_metadata_row(self):
        """Remove selected row from metadata table."""
        current_row = self.metadata_table.currentRow()
        if current_row >= 0:
            self.metadata_table.removeRow(current_row)

    def accept(self):
        """Handle OK button - save properties and close."""
        self.save_properties()
        super().accept()
