"""Main Layout/Books tab for ImageAI."""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton,
    QToolBar, QLabel, QMessageBox, QFileDialog, QDialog, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon

from core.config import ConfigManager
from core.layout import TemplateManager, LayoutEngine
from core.layout.models import DocumentSpec, PageSpec
from core.llm_models import get_provider_models, get_all_provider_ids, get_provider_display_name
from gui.layout.template_selector import TemplateSelectorWidget
from gui.layout.canvas_widget import CanvasWidget
from gui.layout.inspector_widget import InspectorWidget

logger = logging.getLogger(__name__)


class LayoutTab(QWidget):
    """Layout/Books tab - create children's books, comics, and magazines."""

    # Signals
    documentChanged = Signal()  # Emitted when document is modified
    templateSelected = Signal(str)  # Emitted when template is selected (template path)

    def __init__(self, config: Optional[ConfigManager] = None, parent=None):
        super().__init__(parent)
        self.config = config or ConfigManager()
        self.template_manager = None
        self.layout_engine = None
        self.current_document: Optional[DocumentSpec] = None
        self.current_page_index = 0
        self.current_template_path: Optional[str] = None
        self.current_template_category: str = "children"
        self.current_template_name: str = ""

        self.init_ui()
        self.init_managers()
        self.load_settings()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Toolbar
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # Development warning banner
        dev_warning = QLabel("⚠️ <b>Development in Progress</b> — Not yet functional")
        dev_warning.setStyleSheet("""
            QLabel {
                background-color: #F3E5AB;
                color: #4A4A4A;
                padding: 3px 12px;
                border-radius: 3px;
                font-size: 9pt;
            }
        """)
        dev_warning.setAlignment(Qt.AlignCenter)
        dev_warning.setWordWrap(False)
        dev_warning.setMaximumHeight(24)  # Force single-line height
        dev_warning.setMinimumHeight(24)
        layout.addWidget(dev_warning)

        # Info banner
        info_banner = QLabel(
            "📖 Layout/Books - Create children's books, comics, and magazine articles with AI-powered content"
        )
        info_banner.setStyleSheet("""
            QLabel {
                background-color: #6366F1;
                color: white;
                padding: 8px 12px;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        info_banner.setWordWrap(True)
        layout.addWidget(info_banner)

        # Main splitter (three panels)
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Left panel - Template Selector
        self.template_selector_widget = TemplateSelectorWidget()
        self.template_selector_widget.templateSelected.connect(self.on_template_selected)
        self.main_splitter.addWidget(self.template_selector_widget)

        # Center panel - Canvas
        self.canvas_widget = CanvasWidget()
        self.canvas_widget.blockSelected.connect(self.on_block_selected)
        self.canvas_widget.pageChanged.connect(self.on_page_changed)
        self.main_splitter.addWidget(self.canvas_widget)

        # Right panel - Inspector
        self.inspector_widget = InspectorWidget()
        self.inspector_widget.blockModified.connect(self.on_block_modified)
        self.main_splitter.addWidget(self.inspector_widget)

        # Set initial splitter sizes (25% left, 50% center, 25% right)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setStretchFactor(2, 1)

        layout.addWidget(self.main_splitter)

        # Status bar at bottom
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("padding: 4px; color: #666;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.page_info_label = QLabel("")
        self.page_info_label.setStyleSheet("padding: 4px; color: #666;")
        status_layout.addWidget(self.page_info_label)

        layout.addLayout(status_layout)

    def create_toolbar(self) -> QToolBar:
        """Create the toolbar with actions."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # New Document
        new_action = QAction("New", self)
        new_action.setToolTip("Create a new layout document")
        new_action.triggered.connect(self.new_document)
        toolbar.addAction(new_action)

        # Open Project
        open_action = QAction("Open", self)
        open_action.setToolTip("Open a layout project file")
        open_action.triggered.connect(self.open_project)
        toolbar.addAction(open_action)

        # Save Project
        save_action = QAction("Save", self)
        save_action.setToolTip("Save the current layout project")
        save_action.triggered.connect(self.save_project)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        # Add Page
        add_page_action = QAction("+ Page", self)
        add_page_action.setToolTip("Add a new page to the document")
        add_page_action.triggered.connect(self.add_page)
        toolbar.addAction(add_page_action)

        # Remove Page
        remove_page_action = QAction("- Page", self)
        remove_page_action.setToolTip("Remove the current page")
        remove_page_action.triggered.connect(self.remove_page)
        toolbar.addAction(remove_page_action)

        toolbar.addSeparator()

        # Export
        export_action = QAction("Export", self)
        export_action.setToolTip("Export to PNG/PDF")
        export_action.triggered.connect(self.export_document)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        # Document Properties
        props_action = QAction("Properties", self)
        props_action.setToolTip("Edit document properties")
        props_action.triggered.connect(self.show_document_properties)
        toolbar.addAction(props_action)

        toolbar.addSeparator()

        # LLM Provider Selection
        toolbar.addWidget(QLabel("  LLM:"))
        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.setMinimumWidth(120)
        self.llm_provider_combo.setToolTip("Select LLM provider for text generation")
        self.llm_provider_combo.addItems(self._get_llm_providers())
        self.llm_provider_combo.currentTextChanged.connect(self._on_llm_provider_changed)
        toolbar.addWidget(self.llm_provider_combo)

        # LLM Model Selection
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setMinimumWidth(200)
        self.llm_model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.llm_model_combo.setToolTip("Select LLM model for text generation")
        self.llm_model_combo.setEnabled(False)
        toolbar.addWidget(self.llm_model_combo)

        # Initialize LLM selection
        self._initialize_llm_selection()

        return toolbar

    def on_template_selected(self, template_path: str, metadata):
        """Handle template selection."""
        logger.info(f"Template selected: {metadata.name} ({template_path})")
        self.current_template_path = template_path
        self.current_template_category = metadata.category
        self.current_template_name = metadata.name

        # Future: Load template and create document
        self.update_status(f"Template selected: {metadata.name}")

    def on_block_selected(self, block_id: str):
        """Handle block selection on canvas."""
        logger.info(f"Block selected: {block_id}")

        # Update inspector context
        total_pages = len(self.current_document.pages) if self.current_document else 1
        provider, model = self.get_current_llm_config()
        self.inspector_widget.set_context(
            config=self.config,
            document=self.current_document,
            template_category=self.current_template_category,
            template_name=self.current_template_name,
            page_number=self.current_page_index + 1,  # 1-based for display
            total_pages=total_pages,
            llm_provider=provider,
            llm_model=model
        )

        # Update inspector block
        current_page = self.canvas_widget.get_current_page()
        if current_page:
            self.inspector_widget.set_block(current_page, block_id)

    def on_block_modified(self):
        """Handle block property changes from inspector."""
        logger.info("Block modified - re-rendering page")

        # Re-render the current page
        self.canvas_widget.render_current_page()
        self.update_status("Block updated")

    def on_page_changed(self, page_index: int):
        """Handle page change."""
        self.current_page_index = page_index
        self.update_page_info()
        self.inspector_widget.clear_inspector()

    def init_managers(self):
        """Initialize template and layout managers."""
        try:
            # Get templates directory from config (already points to templates/layouts)
            layouts_dir = self.config.get_templates_dir()

            # Initialize template manager
            self.template_manager = TemplateManager(
                template_dirs=[str(layouts_dir)]
            )

            # Discover templates
            templates = self.template_manager.discover_templates()
            template_count = len(templates)
            logger.info(f"Discovered {template_count} templates")

            # Initialize layout engine
            self.layout_engine = LayoutEngine(self.config)

            # Set managers on widgets
            self.template_selector_widget.set_template_manager(self.template_manager)
            self.canvas_widget.set_layout_engine(self.layout_engine)

            self.update_status(f"Ready - {template_count} templates loaded")

        except Exception as e:
            logger.error(f"Failed to initialize managers: {e}", exc_info=True)
            self.update_status(f"Error: {e}")

    def load_settings(self):
        """Load saved settings."""
        # Future: restore splitter sizes, last project, etc.
        pass

    def save_settings(self):
        """Save current settings."""
        # Future: save splitter sizes, last project, etc.
        pass

    def new_document(self):
        """Create a new document from a template."""
        logger.info("New document requested")

        # Check if there's unsaved work
        if self.current_document:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Creating a new document will discard current changes. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Get currently selected template from selector
        selected_template_path = self.template_selector_widget.get_selected_template()
        if not selected_template_path:
            QMessageBox.information(
                self,
                "No Template Selected",
                "Please select a template from the left panel first."
            )
            return

        # Load template
        try:
            # Get template key (filename without extension)
            template_path = Path(selected_template_path)
            template_key = template_path.stem

            # Load template data
            template_data = self.template_manager.load_template_data(template_key)
            if not template_data:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to load template: {template_key}"
                )
                return

            # Create PageSpec from template
            page_spec = self._create_page_from_template(template_data)

            # Create DocumentSpec
            self.current_document = DocumentSpec(
                title="Untitled",
                author=None,
                pages=[page_spec],
                theme=template_data.get("variables", {}),
                metadata={"template": template_key}
            )

            # Update UI
            self.canvas_widget.set_pages(self.current_document.pages)
            self.current_page_index = 0
            self.update_page_info()
            self.update_status(f"New document created from template: {template_key}")

            logger.info(f"Created new document from template: {template_key}")

        except Exception as e:
            logger.error(f"Failed to create document: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to create document:\n{e}")

    def _create_page_from_template(self, template_data: Dict[str, Any]) -> PageSpec:
        """Create a PageSpec from template data."""
        from core.layout.models import TextBlock, ImageBlock, TextStyle, ImageStyle

        # Extract page properties
        page_size_px = tuple(template_data.get("page_size_px", [2480, 3508]))
        margin_px = template_data.get("margin_px", 64)
        bleed_px = template_data.get("bleed_px", 0)
        background = template_data.get("background", "#FFFFFF")
        variables = template_data.get("variables", {})

        # Create blocks
        blocks = []
        for block_data in template_data.get("blocks", []):
            block_type = block_data.get("type")
            block_id = block_data.get("id")
            rect = tuple(block_data.get("rect", [0, 0, 100, 100]))

            if block_type == "text":
                # Create TextStyle
                style_data = block_data.get("style", {})
                style = TextStyle(
                    family=style_data.get("family", ["Arial"]),
                    weight=style_data.get("weight", "regular"),
                    italic=style_data.get("italic", False),
                    size_px=style_data.get("size_px", 32),
                    line_height=style_data.get("line_height", 1.3),
                    color=style_data.get("color", "#111111"),
                    align=style_data.get("align", "left"),
                    wrap=style_data.get("wrap", "word"),
                    letter_spacing=style_data.get("letter_spacing", 0.0)
                )
                block = TextBlock(
                    id=block_id,
                    rect=rect,
                    text=block_data.get("text", ""),
                    style=style
                )
                blocks.append(block)

            elif block_type == "image":
                # Create ImageStyle
                style_data = block_data.get("style", {})
                style = ImageStyle(
                    fit=style_data.get("fit", "cover"),
                    border_radius_px=style_data.get("border_radius_px", 0),
                    stroke_px=style_data.get("stroke_px", 0),
                    stroke_color=style_data.get("stroke_color", "#000000")
                )
                block = ImageBlock(
                    id=block_id,
                    rect=rect,
                    image_path=block_data.get("image_path"),
                    style=style,
                    alt_text=block_data.get("alt_text")
                )
                blocks.append(block)

        return PageSpec(
            page_size_px=page_size_px,
            margin_px=margin_px,
            bleed_px=bleed_px,
            background=background,
            blocks=blocks,
            variables=variables
        )

    def open_project(self):
        """Open a saved project file."""
        logger.info("Open project requested")

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Layout Project",
            str(Path.home()),
            "Layout Project (*.layout.json);;All Files (*.*)"
        )

        if file_path:
            try:
                # Future: load project file
                logger.info(f"Loading project: {file_path}")
                QMessageBox.information(
                    self,
                    "Open Project",
                    f"Project loading will be implemented soon.\n\nFile: {file_path}"
                )
            except Exception as e:
                logger.error(f"Failed to open project: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def save_project(self):
        """Save the current project."""
        logger.info("Save project requested")

        if not self.current_document:
            QMessageBox.warning(self, "No Document", "No document to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Layout Project",
            str(Path.home() / "untitled.layout.json"),
            "Layout Project (*.layout.json);;All Files (*.*)"
        )

        if file_path:
            try:
                # Future: save project file
                logger.info(f"Saving project: {file_path}")
                QMessageBox.information(
                    self,
                    "Save Project",
                    f"Project saving will be implemented soon.\n\nFile: {file_path}"
                )
            except Exception as e:
                logger.error(f"Failed to save project: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    def add_page(self):
        """Add a new page to the document."""
        logger.info("Add page requested")

        if not self.current_document:
            QMessageBox.warning(self, "No Document", "Create a new document first.")
            return

        try:
            # Get template key from metadata
            template_key = self.current_document.metadata.get("template")
            if not template_key:
                QMessageBox.warning(
                    self,
                    "No Template",
                    "Cannot add page: document has no associated template."
                )
                return

            # Load template data
            template_data = self.template_manager.load_template_data(template_key)
            if not template_data:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to load template: {template_key}"
                )
                return

            # Create new page from template
            new_page = self._create_page_from_template(template_data)

            # Add page to document
            self.current_document.pages.append(new_page)

            # Update canvas
            self.canvas_widget.set_pages(self.current_document.pages)

            # Navigate to new page
            self.current_page_index = len(self.current_document.pages) - 1
            self.canvas_widget.goto_page(self.current_page_index)

            # Update UI
            self.update_page_info()
            self.update_status(f"Added page {self.current_page_index + 1}")

            logger.info(f"Added new page (total pages: {len(self.current_document.pages)})")

        except Exception as e:
            logger.error(f"Failed to add page: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to add page:\n{e}")

    def remove_page(self):
        """Remove the current page."""
        logger.info("Remove page requested")

        if not self.current_document:
            QMessageBox.warning(self, "No Document", "No document loaded.")
            return

        if not self.current_document.pages:
            QMessageBox.warning(self, "No Pages", "Document has no pages.")
            return

        # Don't allow removing the last page
        if len(self.current_document.pages) == 1:
            QMessageBox.warning(
                self,
                "Cannot Remove",
                "Cannot remove the last page. Document must have at least one page."
            )
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Remove Page",
            f"Remove page {self.current_page_index + 1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        try:
            # Remove page
            removed_index = self.current_page_index
            self.current_document.pages.pop(self.current_page_index)

            # Update canvas
            self.canvas_widget.set_pages(self.current_document.pages)

            # Navigate to appropriate page
            if self.current_page_index >= len(self.current_document.pages):
                self.current_page_index = len(self.current_document.pages) - 1

            self.canvas_widget.goto_page(self.current_page_index)

            # Update UI
            self.update_page_info()
            self.update_status(f"Removed page {removed_index + 1}")

            logger.info(f"Removed page {removed_index + 1} (total pages: {len(self.current_document.pages)})")

        except Exception as e:
            logger.error(f"Failed to remove page: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to remove page:\n{e}")

    def export_document(self):
        """Export the document to PNG/PDF."""
        logger.info("Export requested")

        if not self.current_document:
            QMessageBox.warning(self, "No Document", "No document to export.")
            return

        # Import here to avoid circular imports
        from gui.layout.export_dialog import ExportDialog

        # Show export dialog
        dialog = ExportDialog(self.current_document, self.config, self)
        dialog.exec()

    def show_document_properties(self):
        """Show the document properties dialog."""
        logger.info("Document properties requested")

        if not self.current_document:
            QMessageBox.warning(self, "No Document", "Create a new document first.")
            return

        try:
            from gui.layout.document_dialog import DocumentPropertiesDialog

            # Show dialog
            dialog = DocumentPropertiesDialog(self.current_document, self)
            result = dialog.exec()

            if result == QDialog.Accepted:
                # Properties were saved by the dialog
                # Refresh the canvas to show any page size changes
                self.canvas_widget.set_pages(self.current_document.pages)
                self.canvas_widget.goto_page(self.current_page_index)
                self.update_status("Document properties updated")
                logger.info("Document properties saved")

        except Exception as e:
            logger.error(f"Failed to show document properties: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to show properties dialog:\n{e}")

    def update_status(self, message: str):
        """Update the status label."""
        self.status_label.setText(message)
        logger.debug(f"Status: {message}")

    def update_page_info(self):
        """Update the page info label."""
        if self.current_document and self.current_document.pages:
            page_num = self.current_page_index + 1
            total_pages = len(self.current_document.pages)
            self.page_info_label.setText(f"Page {page_num} of {total_pages}")
        else:
            self.page_info_label.setText("")

    def _get_llm_providers(self) -> list:
        """Get list of available LLM providers (display names)."""
        # Get provider IDs and convert to display names (like main_window.py)
        provider_names = [get_provider_display_name(pid) for pid in get_all_provider_ids()]
        return provider_names  # No "None" option for layouts - we always use an LLM

    def _initialize_llm_selection(self):
        """Initialize LLM provider and model selection from config."""
        try:
            # Get saved provider preference
            saved_provider = self.config.get_layout_llm_provider()

            if saved_provider and saved_provider in self._get_llm_providers():
                index = self.llm_provider_combo.findText(saved_provider)
                if index >= 0:
                    self.llm_provider_combo.setCurrentIndex(index)

            # Trigger provider changed to populate models
            self._on_llm_provider_changed(self.llm_provider_combo.currentText())

        except Exception as e:
            logger.warning(f"Failed to initialize LLM selection: {e}")

    def _on_llm_provider_changed(self, provider_display_name: str):
        """Handle LLM provider selection change.

        Args:
            provider_display_name: Display name like "Google", "OpenAI", "Anthropic"
        """
        try:
            # Map display name to provider ID (same pattern as main_window.py)
            provider_map = {
                "google": "gemini",
                "anthropic": "anthropic",
                "openai": "openai",
                "ollama": "ollama",
                "lm studio": "lmstudio"
            }
            provider_id = provider_map.get(provider_display_name.lower(), provider_display_name.lower())

            self.llm_model_combo.blockSignals(True)
            self.llm_model_combo.clear()

            # Get models for this provider ID
            models = get_provider_models(provider_id)
            if models:
                self.llm_model_combo.setEnabled(True)
                self.llm_model_combo.addItems(models)
                # Select first (most capable) model by default
                self.llm_model_combo.setCurrentIndex(0)
            else:
                self.llm_model_combo.setEnabled(False)

            self.llm_model_combo.blockSignals(False)

            # Save provider preference (save display name for consistency)
            self.config.set_layout_llm_provider(provider_display_name)

            # Update inspector with new provider/model
            self._update_inspector_llm_context()

            logger.info(f"LLM provider changed to: {provider_display_name} (ID: {provider_id})")

        except Exception as e:
            logger.error(f"Failed to update LLM provider: {e}", exc_info=True)

    def _update_inspector_llm_context(self):
        """Update the inspector with current LLM provider/model selection."""
        try:
            provider = self.llm_provider_combo.currentText()
            model = self.llm_model_combo.currentText() if self.llm_model_combo.isEnabled() else None

            # Store in instance for access by inspector
            self.current_llm_provider = provider
            self.current_llm_model = model

            logger.debug(f"Inspector LLM context updated: {provider} / {model}")

        except Exception as e:
            logger.error(f"Failed to update inspector LLM context: {e}", exc_info=True)

    def get_current_llm_config(self) -> tuple:
        """Get the currently selected LLM provider and model."""
        provider = getattr(self, 'current_llm_provider', None) or self.llm_provider_combo.currentText()
        model = getattr(self, 'current_llm_model', None) or (
            self.llm_model_combo.currentText() if self.llm_model_combo.isEnabled() else None
        )
        return provider, model

    def closeEvent(self, event):
        """Handle widget close event."""
        self.save_settings()
        super().closeEvent(event)
