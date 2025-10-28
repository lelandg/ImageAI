"""Template selector widget for Layout tab."""

import logging
from typing import Optional, List, Dict
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QComboBox, QLabel, QPushButton, QScrollArea, QGridLayout,
    QSizePolicy, QToolButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QIcon

from core.layout import TemplateManager, TemplateMetadata

logger = logging.getLogger(__name__)


class TemplateCard(QWidget):
    """A card widget for displaying a template with thumbnail and info."""

    clicked = Signal(str)  # Emits template path when clicked

    def __init__(self, metadata: TemplateMetadata, thumbnail_path: Optional[Path] = None, parent=None):
        super().__init__(parent)
        self.metadata = metadata
        self.thumbnail_path = thumbnail_path
        self.is_selected = False

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setFixedSize(128, 128)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ccc;
                border-radius: 4px;
                background-color: #f5f5f5;
            }
        """)

        # Load thumbnail if available
        if self.thumbnail_path and self.thumbnail_path.exists():
            pixmap = QPixmap(str(self.thumbnail_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    124, 124,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                self.thumbnail_label.setText("No Preview")
        else:
            self.thumbnail_label.setText("No Preview")

        layout.addWidget(self.thumbnail_label)

        # Name
        name_label = QLabel(self.metadata.name)
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)

        # Category
        category_label = QLabel(self.metadata.category.title())
        category_label.setAlignment(Qt.AlignCenter)
        category_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(category_label)

        # Make the whole card clickable
        self.setFixedWidth(144)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        # Set stylesheet for hover effect
        self.update_style()

    def update_style(self):
        """Update the card style based on selection state."""
        if self.is_selected:
            self.setStyleSheet("""
                TemplateCard {
                    background-color: #e0e7ff;
                    border: 2px solid #6366f1;
                    border-radius: 8px;
                }
                TemplateCard:hover {
                    background-color: #dbeafe;
                }
            """)
        else:
            self.setStyleSheet("""
                TemplateCard {
                    background-color: white;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                }
                TemplateCard:hover {
                    background-color: #f9fafb;
                    border: 1px solid #d1d5db;
                }
            """)

    def set_selected(self, selected: bool):
        """Set the selection state."""
        self.is_selected = selected
        self.update_style()

    def mousePressEvent(self, event):
        """Handle mouse press to select template."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(str(self.metadata.filepath))
        super().mousePressEvent(event)


class TemplateSelectorWidget(QWidget):
    """Widget for browsing and selecting templates."""

    templateSelected = Signal(str, object)  # Emits (path, metadata)

    def __init__(self, template_manager: Optional[TemplateManager] = None, parent=None):
        super().__init__(parent)
        self.template_manager = template_manager
        self.current_templates: List[TemplateMetadata] = []
        self.template_cards: Dict[str, TemplateCard] = {}  # path -> card
        self.selected_template_path: Optional[str] = None

        self.init_ui()

        if self.template_manager:
            self.refresh_templates()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header_label = QLabel("Templates")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 8px;")
        layout.addWidget(header_label)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search templates...")
        self.search_input.textChanged.connect(self.filter_templates)
        layout.addWidget(self.search_input)

        # Category filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Category:"))

        self.category_combo = QComboBox()
        self.category_combo.addItem("All", "")
        self.category_combo.addItem("Children's Books", "children")
        self.category_combo.addItem("Comics", "comic")
        self.category_combo.addItem("Magazines", "magazine")
        self.category_combo.addItem("Custom", "custom")
        self.category_combo.currentIndexChanged.connect(self.filter_templates)
        filter_layout.addWidget(self.category_combo, 1)

        layout.addLayout(filter_layout)

        # View mode toggle (grid/list)
        view_layout = QHBoxLayout()
        view_layout.addWidget(QLabel("View:"))

        self.grid_view_btn = QToolButton()
        self.grid_view_btn.setText("Grid")
        self.grid_view_btn.setCheckable(True)
        self.grid_view_btn.setChecked(True)
        self.grid_view_btn.clicked.connect(lambda: self.set_view_mode("grid"))
        view_layout.addWidget(self.grid_view_btn)

        self.list_view_btn = QToolButton()
        self.list_view_btn.setText("List")
        self.list_view_btn.setCheckable(True)
        self.list_view_btn.clicked.connect(lambda: self.set_view_mode("list"))
        view_layout.addWidget(self.list_view_btn)

        view_layout.addStretch()
        layout.addLayout(view_layout)

        # Templates scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container for templates (grid layout)
        self.templates_container = QWidget()
        self.templates_layout = QGridLayout(self.templates_container)
        self.templates_layout.setSpacing(12)
        self.templates_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_area.setWidget(self.templates_container)
        layout.addWidget(self.scroll_area, 1)

        # Info label at bottom
        self.info_label = QLabel("No templates loaded")
        self.info_label.setStyleSheet("color: #666; padding: 4px; font-size: 11px;")
        layout.addWidget(self.info_label)

    def set_template_manager(self, manager: TemplateManager):
        """Set the template manager and refresh."""
        self.template_manager = manager
        self.refresh_templates()

    def refresh_templates(self):
        """Refresh the template list from the manager."""
        if not self.template_manager:
            logger.warning("No template manager set")
            return

        try:
            # Get all templates
            self.current_templates = self.template_manager.discover_templates()

            logger.info(f"Refreshed templates: {len(self.current_templates)} found")

            # Update UI
            self.filter_templates()

        except Exception as e:
            logger.error(f"Failed to refresh templates: {e}", exc_info=True)
            self.info_label.setText(f"Error: {e}")

    def filter_templates(self):
        """Filter templates based on search and category."""
        if not self.template_manager:
            return

        search_query = self.search_input.text().strip()
        category_filter = self.category_combo.currentData()

        # Apply filters
        filtered = self.template_manager.search_templates(
            query=search_query if search_query else None,
            category=category_filter if category_filter else None
        )

        # Update display
        self.display_templates(filtered)

        # Update info
        self.info_label.setText(f"{len(filtered)} template(s)")

    def display_templates(self, templates: List[TemplateMetadata]):
        """Display the filtered templates."""
        # Clear existing cards
        for card in self.template_cards.values():
            card.deleteLater()
        self.template_cards.clear()

        # Create new cards
        row, col = 0, 0
        max_cols = 2  # 2 columns in grid view

        for template in templates:
            # Get preview thumbnail
            thumbnail_path = None
            if self.template_manager:
                preview_gen = self.template_manager.preview_generator
                if preview_gen:
                    # Get cached preview path
                    cache_path = preview_gen.get_cache_path(template.filepath)
                    # Only use if it exists (previews are generated on demand)
                    if cache_path.exists():
                        thumbnail_path = cache_path

            # Create card
            card = TemplateCard(template, thumbnail_path)
            card.clicked.connect(self.on_template_clicked)

            # Update selection state
            template_path_str = str(template.filepath)
            if template_path_str == self.selected_template_path:
                card.set_selected(True)

            # Add to layout
            self.templates_layout.addWidget(card, row, col)
            self.template_cards[template_path_str] = card

            # Update grid position
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def on_template_clicked(self, template_path: str):
        """Handle template card click."""
        logger.info(f"Template selected: {template_path}")

        # Update selection
        old_path = self.selected_template_path
        self.selected_template_path = template_path

        # Update card styles
        if old_path and old_path in self.template_cards:
            self.template_cards[old_path].set_selected(False)

        if template_path in self.template_cards:
            self.template_cards[template_path].set_selected(True)

        # Get metadata
        if self.template_manager:
            # Find the metadata for this template
            metadata = None
            for t in self.current_templates:
                if str(t.filepath) == template_path:
                    metadata = t
                    break

            if metadata:
                self.templateSelected.emit(template_path, metadata)

    def set_view_mode(self, mode: str):
        """Set the view mode (grid or list)."""
        # Future: implement list view
        if mode == "grid":
            self.grid_view_btn.setChecked(True)
            self.list_view_btn.setChecked(False)
        else:
            self.grid_view_btn.setChecked(False)
            self.list_view_btn.setChecked(True)

    def get_selected_template(self) -> Optional[str]:
        """Get the currently selected template path."""
        return self.selected_template_path
