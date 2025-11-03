"""Export Dialog for Layout/Books module.

Exports layout documents to various formats (PNG, PDF, JSON).
"""

import logging
from typing import Optional, List
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QFormLayout,
    QFileDialog, QProgressBar, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, QThread, Signal

from core.config import ConfigManager
from core.layout.models import DocumentSpec
from core.layout import LayoutEngine

logger = logging.getLogger(__name__)


class ExportWorker(QThread):
    """Worker thread for exporting documents."""

    progress = Signal(int, str)  # Progress (0-100), status message
    finished = Signal(bool, str)  # Success, message
    error = Signal(str)  # Error message

    def __init__(self, document: DocumentSpec, export_format: str,
                 output_path: str, dpi: int = 300,
                 page_range: Optional[tuple] = None):
        super().__init__()
        self.document = document
        self.export_format = export_format
        self.output_path = output_path
        self.dpi = dpi
        self.page_range = page_range  # (start, end) or None for all

    def run(self):
        """Perform the export."""
        try:
            output_path = Path(self.output_path)
            total_pages = len(self.document.pages)

            # Determine which pages to export
            if self.page_range:
                start_page, end_page = self.page_range
                pages_to_export = list(range(start_page - 1, end_page))  # Convert to 0-based
            else:
                pages_to_export = list(range(total_pages))

            num_pages = len(pages_to_export)

            if self.export_format == "png":
                self._export_png(output_path, pages_to_export, num_pages)
            elif self.export_format == "pdf":
                self._export_pdf(output_path, pages_to_export, num_pages)
            elif self.export_format == "json":
                self._export_json(output_path)
            else:
                self.error.emit(f"Unknown export format: {self.export_format}")
                return

            self.finished.emit(True, f"Exported successfully to {output_path}")

        except Exception as e:
            logger.error(f"Export error: {e}", exc_info=True)
            self.error.emit(f"Export failed: {e}")

    def _export_png(self, output_path: Path, pages_to_export: List[int], num_pages: int):
        """Export to PNG sequence."""
        # Create engine
        engine = LayoutEngine()

        for idx, page_num in enumerate(pages_to_export):
            page = self.document.pages[page_num]

            # Update progress
            progress_pct = int((idx / num_pages) * 100)
            self.progress.emit(progress_pct, f"Rendering page {page_num + 1}...")

            # Render page
            image = engine.render_page(page, dpi=self.dpi)

            # Save with page number if multiple pages
            if num_pages > 1:
                page_output = output_path.parent / f"{output_path.stem}_page{page_num + 1:03d}.png"
            else:
                page_output = output_path

            image.save(str(page_output), "PNG")
            logger.info(f"Exported page {page_num + 1} to {page_output}")

        self.progress.emit(100, "Complete!")

    def _export_pdf(self, output_path: Path, pages_to_export: List[int], num_pages: int):
        """Export to PDF."""
        try:
            from PIL import Image
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader
            import io

            # Create engine
            engine = LayoutEngine()

            # Create PDF
            c = canvas.Canvas(str(output_path))

            for idx, page_num in enumerate(pages_to_export):
                page = self.document.pages[page_num]

                # Update progress
                progress_pct = int((idx / num_pages) * 100)
                self.progress.emit(progress_pct, f"Rendering page {page_num + 1}...")

                # Render page
                image = engine.render_page(page, dpi=self.dpi)

                # Convert PIL image to reportlab format
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                img_reader = ImageReader(img_buffer)

                # Get page size from image
                width_px, height_px = image.size
                # Convert pixels to points (72 points = 1 inch)
                width_pt = (width_px / self.dpi) * 72
                height_pt = (height_px / self.dpi) * 72

                # Set page size and draw image
                c.setPageSize((width_pt, height_pt))
                c.drawImage(img_reader, 0, 0, width=width_pt, height=height_pt)

                # Add new page if not last
                if idx < num_pages - 1:
                    c.showPage()

                logger.info(f"Added page {page_num + 1} to PDF")

            # Save PDF
            c.save()
            self.progress.emit(100, "Complete!")

        except ImportError:
            self.error.emit("PDF export requires 'reportlab' package. Install with: pip install reportlab")
            return

    def _export_json(self, output_path: Path):
        """Export to JSON project file."""
        import json
        from dataclasses import asdict

        self.progress.emit(50, "Serializing document...")

        # Convert DocumentSpec to dict
        doc_dict = asdict(self.document)

        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(doc_dict, f, indent=2)

        logger.info(f"Exported document to JSON: {output_path}")
        self.progress.emit(100, "Complete!")


class ExportDialog(QDialog):
    """Dialog for exporting layout documents."""

    def __init__(self, document: DocumentSpec, config: Optional[ConfigManager] = None, parent=None):
        super().__init__(parent)
        self.document = document
        self.config = config or ConfigManager()
        self.worker: Optional[ExportWorker] = None

        self.setWindowTitle("Export Layout")
        self.resize(500, 400)

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Export presets
        preset_group = QGroupBox("Quick Presets")
        preset_layout = QHBoxLayout()

        preset_label = QLabel("Preset:")
        preset_layout.addWidget(preset_label)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Custom",
            "Web (PNG 72 DPI)",
            "Draft Print (PDF 150 DPI)",
            "High Quality Print (PDF 300 DPI)",
            "Ultra High Res (PNG 600 DPI)"
        ])
        self.preset_combo.setToolTip("Choose a preset or select Custom for manual settings")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo)

        preset_layout.addStretch()

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout()

        self.format_group = QButtonGroup(self)

        self.png_radio = QRadioButton("PNG Image Sequence")
        self.png_radio.setToolTip("Export each page as a separate PNG image")
        self.png_radio.setChecked(True)
        self.format_group.addButton(self.png_radio, 0)
        format_layout.addWidget(self.png_radio)

        self.pdf_radio = QRadioButton("PDF Document")
        self.pdf_radio.setToolTip("Export as a single PDF file (requires reportlab)")
        self.format_group.addButton(self.pdf_radio, 1)
        format_layout.addWidget(self.pdf_radio)

        self.json_radio = QRadioButton("JSON Project File")
        self.json_radio.setToolTip("Save document as editable JSON project file")
        self.format_group.addButton(self.json_radio, 2)
        format_layout.addWidget(self.json_radio)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # Quality settings
        quality_group = QGroupBox("Quality Settings")
        quality_layout = QFormLayout()

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setSingleStep(50)
        self.dpi_spin.setValue(self.config.get_layout_export_dpi())
        self.dpi_spin.setToolTip("DPI (dots per inch): 72=screen, 150=draft, 300=print")
        quality_layout.addRow("DPI:", self.dpi_spin)

        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)

        # Page range
        range_group = QGroupBox("Page Range")
        range_layout = QVBoxLayout()

        self.all_pages_radio = QRadioButton("All Pages")
        self.all_pages_radio.setChecked(True)
        range_layout.addWidget(self.all_pages_radio)

        range_specific_layout = QHBoxLayout()
        self.range_radio = QRadioButton("Pages:")
        range_specific_layout.addWidget(self.range_radio)

        self.start_page_spin = QSpinBox()
        self.start_page_spin.setRange(1, len(self.document.pages))
        self.start_page_spin.setValue(1)
        self.start_page_spin.setEnabled(False)
        range_specific_layout.addWidget(self.start_page_spin)

        range_specific_layout.addWidget(QLabel("to"))

        self.end_page_spin = QSpinBox()
        self.end_page_spin.setRange(1, len(self.document.pages))
        self.end_page_spin.setValue(len(self.document.pages))
        self.end_page_spin.setEnabled(False)
        range_specific_layout.addWidget(self.end_page_spin)

        range_specific_layout.addStretch()

        range_layout.addLayout(range_specific_layout)

        # Connect radio button
        self.range_radio.toggled.connect(self._on_range_toggled)

        range_group.setLayout(range_layout)
        layout.addWidget(range_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet("color: #666; padding: 4px;")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.export_btn = QPushButton("Export...")
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self.start_export)
        button_layout.addWidget(self.export_btn)

        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _on_range_toggled(self, checked: bool):
        """Handle range radio button toggle."""
        self.start_page_spin.setEnabled(checked)
        self.end_page_spin.setEnabled(checked)

    def _on_preset_changed(self, index: int):
        """Handle preset selection change."""
        preset_name = self.preset_combo.currentText()

        # Define presets
        presets = {
            "Web (PNG 72 DPI)": {
                "format": "png",
                "dpi": 72
            },
            "Draft Print (PDF 150 DPI)": {
                "format": "pdf",
                "dpi": 150
            },
            "High Quality Print (PDF 300 DPI)": {
                "format": "pdf",
                "dpi": 300
            },
            "Ultra High Res (PNG 600 DPI)": {
                "format": "png",
                "dpi": 600
            }
        }

        if preset_name in presets:
            preset = presets[preset_name]

            # Apply preset settings
            if preset["format"] == "png":
                self.png_radio.setChecked(True)
            elif preset["format"] == "pdf":
                self.pdf_radio.setChecked(True)

            self.dpi_spin.setValue(preset["dpi"])

    def load_settings(self):
        """Load settings from config."""
        # DPI is already loaded in init_ui
        pass

    def save_settings(self):
        """Save settings to config."""
        self.config.set_layout_export_dpi(self.dpi_spin.value())

    def start_export(self):
        """Start the export process."""
        if self.worker and self.worker.isRunning():
            logger.warning("Export already in progress")
            return

        # Determine format
        if self.png_radio.isChecked():
            export_format = "png"
            filter_str = "PNG Images (*.png)"
            default_ext = ".png"
        elif self.pdf_radio.isChecked():
            export_format = "pdf"
            filter_str = "PDF Documents (*.pdf)"
            default_ext = ".pdf"
        else:  # JSON
            export_format = "json"
            filter_str = "JSON Project (*.layout.json)"
            default_ext = ".layout.json"

        # Get output path
        default_filename = f"{self.document.title or 'untitled'}{default_ext}"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Layout",
            str(Path.home() / default_filename),
            filter_str,
            options=QFileDialog.Option.DontUseNativeDialog
        )

        if not output_path:
            return  # User cancelled

        # Get page range
        page_range = None
        if self.range_radio.isChecked():
            start = self.start_page_spin.value()
            end = self.end_page_spin.value()
            if start > end:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Invalid Range", "Start page must be <= end page")
                return
            page_range = (start, end)

        # Show progress UI
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Starting export...")
        self.export_btn.setEnabled(False)

        # Save settings
        self.save_settings()

        # Create and start worker
        self.worker = ExportWorker(
            document=self.document,
            export_format=export_format,
            output_path=output_path,
            dpi=self.dpi_spin.value(),
            page_range=page_range
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        logger.info(f"Started export to {export_format}: {output_path}")

    def _on_progress(self, progress: int, message: str):
        """Handle progress updates."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)

    def _on_finished(self, success: bool, message: str):
        """Handle export completion."""
        from PySide6.QtWidgets import QMessageBox

        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        self.export_btn.setEnabled(True)

        if success:
            QMessageBox.information(self, "Export Complete", message)
            self.accept()  # Close dialog on success
        else:
            QMessageBox.warning(self, "Export Warning", message)

    def _on_error(self, error: str):
        """Handle export error."""
        from PySide6.QtWidgets import QMessageBox

        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        self.export_btn.setEnabled(True)

        QMessageBox.critical(self, "Export Error", error)

    def closeEvent(self, event):
        """Handle close event - ensure worker thread is stopped."""
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            # Disconnect signals to prevent crashes during cleanup
            try:
                self.worker.progress.disconnect()
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except:
                pass  # Signals may already be disconnected

            # Try to quit the thread gracefully
            self.worker.quit()

            # Wait up to 2 seconds for thread to finish
            if not self.worker.wait(2000):
                logger.warning("Worker thread did not finish in time, forcing termination")
                # Thread is still running, but we've disconnected signals
                # QThread's destructor will wait for it

        super().closeEvent(event)
