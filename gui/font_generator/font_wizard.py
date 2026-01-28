"""
Multi-step wizard for creating fonts from alphabet images.

Provides a guided workflow:
1. Image upload and preview
2. Segmentation preview with manual adjustment
3. Character mapping verification
4. Font metrics and naming
5. Preview text rendering and export
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QProgressBar, QGroupBox,
    QComboBox, QLineEdit, QFrame, QScrollArea, QWidget,
    QSplitter, QCheckBox, QSpinBox, QMessageBox,
    QGridLayout, QSlider, QSizePolicy, QTextEdit, QApplication,
)
from PySide6.QtCore import Qt, Signal, QThread, QSize, QSettings, QTimer
from PySide6.QtGui import QPixmap, QImage, QFont, QPainter, QPen, QColor, QPainterPath, QFontDatabase, QFontMetrics

from PIL import Image
import numpy as np

from core.font_generator import (
    AlphabetSegmenter,
    SegmentationResult,
    SegmentationMethod,
    GlyphVectorizer,
    VectorGlyph,
    PathCommand,
    SmoothingLevel,
    FontBuilder,
    FontInfo,
    UPPERCASE,
    LOWERCASE,
    DIGITS,
    PUNCTUATION,
    FONTTOOLS_AVAILABLE,
)
from core.constants import get_user_data_dir

logger = logging.getLogger(__name__)

# Settings key prefix for QSettings
SETTINGS_PREFIX = "font_generator"


class ImageUploadPage(QWizardPage):
    """
    Step 1: Upload and preview alphabet image.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Upload Alphabet Image")
        self.setSubTitle("Select an image containing your alphabet characters")
        self.image_path: Optional[Path] = None
        self._original_pixmap: Optional[QPixmap] = None  # Store original for resize scaling
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Upload an image of your alphabet. Characters should be arranged in rows, "
            "with clear spacing between each character. Dark characters on a light "
            "background work best."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(instructions)

        # Image preview area
        preview_group = QGroupBox("Image Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("No image selected")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet(
            "border: 2px dashed #666; border-radius: 8px; padding: 20px;"
        )
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(preview_group)

        # File selection buttons
        button_layout = QHBoxLayout()

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_image)
        button_layout.addWidget(self.browse_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_image)
        self.clear_btn.setEnabled(False)
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()

        # File path display
        self.path_label = QLabel("")
        self.path_label.setStyleSheet("color: #888;")
        button_layout.addWidget(self.path_label)

        layout.addLayout(button_layout)

        # Character set selection
        charset_group = QGroupBox("Expected Characters")
        charset_layout = QHBoxLayout(charset_group)

        charset_layout.addWidget(QLabel("Character Set:"))

        self.charset_combo = QComboBox()
        # Order: most comprehensive first (default=0 detects most characters)
        self.charset_combo.addItems([
            "Full (A-Z, a-z, 0-9)",      # 0 - most comprehensive
            "Uppercase + Lowercase",     # 1
            "Uppercase + Digits",        # 2
            "Uppercase (A-Z)",           # 3
            "Lowercase (a-z)",           # 4
            "Custom...",                 # 5
        ])
        self.charset_combo.currentIndexChanged.connect(self.on_charset_changed)
        charset_layout.addWidget(self.charset_combo)

        self.custom_chars_edit = QLineEdit()
        self.custom_chars_edit.setPlaceholderText("Enter custom characters...")
        self.custom_chars_edit.setVisible(False)
        charset_layout.addWidget(self.custom_chars_edit)

        charset_layout.addStretch()
        layout.addWidget(charset_group)

        layout.addStretch()

        # Register fields for wizard
        self.registerField("image_path*", self.path_label, "text")
        self.registerField("charset", self.charset_combo, "currentText")

    def browse_image(self):
        """Open file dialog to select an image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Alphabet Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)",
        )

        if file_path:
            self.load_image(Path(file_path))

    def load_image(self, path: Path):
        """Load and display the selected image."""
        try:
            # Load with PIL to verify it's valid
            img = Image.open(path)
            img.verify()

            # Reload for display
            img = Image.open(path)

            # Convert to QPixmap
            if img.mode == "RGBA":
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
            else:
                img = img.convert("RGB")
                data = img.tobytes("raw", "RGB")
                qimg = QImage(data, img.width, img.height, QImage.Format_RGB888)

            pixmap = QPixmap.fromImage(qimg)
            self._original_pixmap = pixmap  # Store for resize scaling

            # Scale to fit preview (use delayed scaling for proper sizing)
            self._scale_preview_to_fit()

            self.image_path = path
            self.path_label.setText(str(path))
            self.clear_btn.setEnabled(True)

            logger.info(f"Loaded alphabet image: {path} ({img.width}x{img.height})")
            self.completeChanged.emit()

        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load image:\n{e}")

    def _scale_preview_to_fit(self):
        """Scale the preview image to fit the available space."""
        if self._original_pixmap is None:
            return

        # Get available size (with some margin)
        available_size = self.preview_label.size()
        if available_size.width() < 50 or available_size.height() < 50:
            # Widget not yet laid out, try again later
            QTimer.singleShot(100, self._scale_preview_to_fit)
            return

        scaled = self._original_pixmap.scaled(
            available_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event):
        """Handle resize to scale image appropriately."""
        super().resizeEvent(event)
        if self._original_pixmap is not None:
            self._scale_preview_to_fit()

    def clear_image(self):
        """Clear the selected image."""
        self.image_path = None
        self._original_pixmap = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("No image selected")
        self.path_label.setText("")
        self.clear_btn.setEnabled(False)
        self.completeChanged.emit()

    def on_charset_changed(self, index):
        """Handle character set selection change."""
        self.custom_chars_edit.setVisible(index == 5)  # "Custom..."

    def get_expected_chars(self) -> str:
        """Get the expected character set based on selection.

        Indices match combo order (most comprehensive first):
        0: Full (A-Z, a-z, 0-9)
        1: Uppercase + Lowercase
        2: Uppercase + Digits
        3: Uppercase (A-Z)
        4: Lowercase (a-z)
        5: Custom...
        """
        index = self.charset_combo.currentIndex()
        if index == 0:
            return UPPERCASE + LOWERCASE + DIGITS  # Full
        elif index == 1:
            return UPPERCASE + LOWERCASE
        elif index == 2:
            return UPPERCASE + DIGITS
        elif index == 3:
            return UPPERCASE
        elif index == 4:
            return LOWERCASE
        else:
            return self.custom_chars_edit.text() or UPPERCASE

    def isComplete(self) -> bool:
        return self.image_path is not None and self.image_path.exists()

    def initializePage(self):
        """Load saved settings when page is shown."""
        settings = QSettings()

        # Load last image path
        last_path = settings.value(f"{SETTINGS_PREFIX}/last_image_path", "")
        if last_path and Path(last_path).exists():
            self.load_image(Path(last_path))

        # Load charset selection
        charset_idx = settings.value(f"{SETTINGS_PREFIX}/charset_index", 0, type=int)
        self.charset_combo.setCurrentIndex(charset_idx)

        # Load custom chars
        custom_chars = settings.value(f"{SETTINGS_PREFIX}/custom_chars", "")
        self.custom_chars_edit.setText(custom_chars)

    def save_settings(self):
        """Save current settings."""
        settings = QSettings()

        if self.image_path:
            settings.setValue(f"{SETTINGS_PREFIX}/last_image_path", str(self.image_path))

        settings.setValue(f"{SETTINGS_PREFIX}/charset_index", self.charset_combo.currentIndex())
        settings.setValue(f"{SETTINGS_PREFIX}/custom_chars", self.custom_chars_edit.text())

    def validatePage(self) -> bool:
        """Called when user clicks Next. Save settings before leaving."""
        self.save_settings()
        return super().validatePage()


class SegmentationPage(QWizardPage):
    """
    Step 2: Preview and adjust character segmentation.
    """

    segmentation_complete = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Character Segmentation")
        self.setSubTitle("Review detected characters and adjust settings if needed")
        self.result: Optional[SegmentationResult] = None
        self._preview_pixmap: Optional[QPixmap] = None  # Store original for resize scaling
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top: Controls in a compact horizontal bar
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        # Method selection
        controls_layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Row-Column", "Contour-based", "Grid-based", "Auto Detect"])
        self.method_combo.currentIndexChanged.connect(self.on_settings_changed)
        self.method_combo.setMinimumWidth(120)
        controls_layout.addWidget(self.method_combo)

        # Grid settings (inline, hidden by default)
        self.grid_frame = QFrame()
        grid_layout = QHBoxLayout(self.grid_frame)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(4)
        grid_layout.addWidget(QLabel("Rows:"))
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 20)
        self.rows_spin.setValue(4)
        self.rows_spin.valueChanged.connect(self.on_settings_changed)
        grid_layout.addWidget(self.rows_spin)
        grid_layout.addWidget(QLabel("Cols:"))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 30)
        self.cols_spin.setValue(7)
        self.cols_spin.valueChanged.connect(self.on_settings_changed)
        grid_layout.addWidget(self.cols_spin)
        self.grid_frame.setVisible(False)
        controls_layout.addWidget(self.grid_frame)

        controls_layout.addWidget(QLabel("|"))  # Separator

        # Invert checkbox
        self.invert_check = QCheckBox("Invert")
        self.invert_check.setToolTip("Invert colors (light text on dark background)")
        self.invert_check.stateChanged.connect(self.on_settings_changed)
        controls_layout.addWidget(self.invert_check)

        # Small glyphs checkbox (for punctuation detection)
        self.small_glyphs_check = QCheckBox("+ Punctuation")
        self.small_glyphs_check.setToolTip(
            "Add punctuation marks to the character set.\n"
            "When enabled, adds: !@#$%^&*()_+-=[]{}|;':\",./<>?`~\\\n"
            "Enable this if your handwriting sample includes punctuation."
        )
        self.small_glyphs_check.stateChanged.connect(self.on_settings_changed)
        controls_layout.addWidget(self.small_glyphs_check)

        # AI-assisted segmentation button
        self.ai_assist_btn = QPushButton("AI Assist")
        self.ai_assist_btn.setToolTip(
            "Use Gemini AI to help with ambiguous character detection.\n"
            "Helps split touching characters and identify small glyphs.\n"
            "Requires Google API key."
        )
        self.ai_assist_btn.clicked.connect(self.run_segmentation_with_ai)
        controls_layout.addWidget(self.ai_assist_btn)

        # Padding
        controls_layout.addWidget(QLabel("Pad:"))
        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(0, 20)
        self.padding_spin.setValue(2)
        self.padding_spin.setMaximumWidth(50)
        self.padding_spin.valueChanged.connect(self.on_settings_changed)
        controls_layout.addWidget(self.padding_spin)

        # Re-analyze button
        self.run_btn = QPushButton("Re-analyze")
        self.run_btn.clicked.connect(self.run_segmentation)
        controls_layout.addWidget(self.run_btn)

        controls_layout.addStretch()
        layout.addWidget(controls_widget)

        # Preview image - takes most of remaining space, scales to fit without stretching
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_image.setMinimumSize(300, 200)
        self.preview_image.setStyleSheet("border: 1px solid #ccc; background: #f8f8f8;")
        self.preview_image.setScaledContents(False)  # Don't stretch - we scale manually
        layout.addWidget(self.preview_image, 3)  # stretch factor 3 for image

        # Status textbox below image - shows detection results and missing characters
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(120)
        self.status_text.setMinimumHeight(60)
        self.status_text.setStyleSheet("background: #f5f5f5; border: 1px solid #ddd;")
        self.status_text.setPlaceholderText("Segmentation results will appear here...")
        layout.addWidget(self.status_text, 1)  # stretch factor 1 for status

    def initializePage(self):
        """Called when page becomes visible."""
        # Load saved settings
        settings = QSettings()

        method_idx = settings.value(f"{SETTINGS_PREFIX}/seg_method", 0, type=int)
        self.method_combo.setCurrentIndex(method_idx)

        rows = settings.value(f"{SETTINGS_PREFIX}/grid_rows", 4, type=int)
        self.rows_spin.setValue(rows)

        cols = settings.value(f"{SETTINGS_PREFIX}/grid_cols", 7, type=int)
        self.cols_spin.setValue(cols)

        padding = settings.value(f"{SETTINGS_PREFIX}/padding", 2, type=int)
        self.padding_spin.setValue(padding)

        # Load small glyphs (punctuation) setting
        include_small_glyphs = settings.value(f"{SETTINGS_PREFIX}/include_small_glyphs", False, type=bool)
        self.small_glyphs_check.setChecked(include_small_glyphs)


        # Auto-detect inversion for this image
        wizard = self.wizard()
        page1: ImageUploadPage = wizard.page(0)
        if page1.image_path:
            needs_invert = AlphabetSegmenter.detect_needs_inversion(page1.image_path)
            self.invert_check.setChecked(needs_invert)
            if needs_invert:
                logger.info("Auto-detected: image needs inversion (light text on dark)")
        else:
            # Fall back to saved setting
            invert = settings.value(f"{SETTINGS_PREFIX}/invert", False, type=bool)
            self.invert_check.setChecked(invert)

        # Update UI visibility
        self.on_settings_changed()

        # Run segmentation with auto character set detection
        self.run_segmentation_auto()

        # Delayed rescale to ensure layout is complete
        QTimer.singleShot(100, self._scale_preview_to_fit)

    def save_settings(self):
        """Save current settings."""
        settings = QSettings()
        settings.setValue(f"{SETTINGS_PREFIX}/seg_method", self.method_combo.currentIndex())
        settings.setValue(f"{SETTINGS_PREFIX}/grid_rows", self.rows_spin.value())
        settings.setValue(f"{SETTINGS_PREFIX}/grid_cols", self.cols_spin.value())
        settings.setValue(f"{SETTINGS_PREFIX}/invert", self.invert_check.isChecked())
        settings.setValue(f"{SETTINGS_PREFIX}/padding", self.padding_spin.value())
        settings.setValue(f"{SETTINGS_PREFIX}/include_small_glyphs", self.small_glyphs_check.isChecked())

    def on_settings_changed(self):
        """Handle settings changes."""
        # Show/hide grid settings based on method
        # Order: 0=Row-Column, 1=Contour-based, 2=Grid-based, 3=Auto Detect
        method_idx = self.method_combo.currentIndex()
        self.grid_frame.setVisible(method_idx == 2)  # Grid-based

    def run_segmentation_auto(self, use_ai: bool = False):
        """Run segmentation with auto character set detection."""
        wizard = self.wizard()
        page1: ImageUploadPage = wizard.page(0)

        if not page1.image_path:
            return

        try:
            # Get settings
            # Order: 0=Row-Column, 1=Contour-based, 2=Grid-based, 3=Auto Detect
            method_idx = self.method_combo.currentIndex()
            methods = [SegmentationMethod.ROW_COLUMN, SegmentationMethod.CONTOUR, SegmentationMethod.GRID, SegmentationMethod.AUTO]
            method = methods[method_idx]

            # Get user's charset selection from page 1
            user_charset = page1.get_expected_chars()
            user_charset_idx = page1.charset_combo.currentIndex()

            # Grid settings
            grid_rows = self.rows_spin.value() if method == SegmentationMethod.GRID else None
            grid_cols = self.cols_spin.value() if method == SegmentationMethod.GRID else None

            # Check if user explicitly selected a charset (not Custom with empty text)
            use_user_charset = user_charset_idx < 5 or (user_charset_idx == 5 and user_charset)

            if use_user_charset and user_charset:
                # User selected a specific charset - respect it
                # If punctuation checkbox is enabled, add punctuation to charset
                actual_charset = user_charset
                if self.small_glyphs_check.isChecked():
                    # Add punctuation characters that aren't already in the charset
                    for char in PUNCTUATION:
                        if char not in actual_charset:
                            actual_charset += char
                    if len(actual_charset) != len(user_charset):
                        logger.info(f"Added punctuation to charset: {len(user_charset)} -> {len(actual_charset)} characters")

                logger.info(f"Using user-selected charset: {len(actual_charset)} characters")
                segmenter = AlphabetSegmenter(
                    method=method,
                    expected_chars=actual_charset,
                    padding=self.padding_spin.value(),
                    invert=self.invert_check.isChecked(),
                    include_small_glyphs=self.small_glyphs_check.isChecked(),
                    use_ai=use_ai,
                )

                self.result = segmenter.segment(
                    page1.image_path,
                    grid_rows=grid_rows,
                    grid_cols=grid_cols,
                )
                detected_charset = actual_charset
                charset_desc = page1.charset_combo.currentText()
                if self.small_glyphs_check.isChecked() and len(actual_charset) != len(user_charset):
                    charset_desc += " + Punctuation"
            else:
                # Auto-detect charset based on detected character count
                segmenter = AlphabetSegmenter(
                    method=method,
                    expected_chars="",  # Will be set by auto-detection
                    padding=self.padding_spin.value(),
                    invert=self.invert_check.isChecked(),
                    include_small_glyphs=self.small_glyphs_check.isChecked(),
                    use_ai=use_ai,
                )

                self.result, detected_charset, charset_desc = segmenter.segment_auto_detect(
                    page1.image_path,
                    grid_rows=grid_rows,
                    grid_cols=grid_cols,
                )

                # Update the character set selection in page 1 based on detection
                self._update_charset_selection(detected_charset, charset_desc)

            # Generate preview
            preview = segmenter.preview_segmentation(page1.image_path, self.result)
            self.display_preview(preview)

            # Update status with missing character info
            found = len(self.result.characters)
            expected = len(detected_charset)
            found_labels = {c.label for c in self.result.characters}
            missing_chars = [c for c in detected_charset if c not in found_labels]

            if use_user_charset and user_charset:
                status = f"Found {found} of {expected} characters.\nUsing selected set: {charset_desc}"
            else:
                status = f"Found {found} characters.\nAuto-detected set: {charset_desc}"

            # Show missing characters if any
            if missing_chars:
                missing_display = ' '.join(missing_chars)
                status += f"\n\n❌ Missing characters ({len(missing_chars)}): {missing_display}"

            # Check for character count warnings (these are critical)
            has_count_warning = any("EXTRA" in w or "MISSING" in w for w in self.result.warnings)

            if self.result.warnings:
                status += "\n\n⚠️ WARNINGS:\n" + "\n".join(self.result.warnings)

            self.status_text.setPlainText(status)

            # Style warnings in red if there's a count mismatch
            if has_count_warning or missing_chars:
                self.status_text.setStyleSheet("background: #fff0f0; border: 1px solid #ffcccc;")
                logger.warning(f"Character count mismatch detected - user should verify mappings")
            else:
                self.status_text.setStyleSheet("background: #f0fff0; border: 1px solid #ccffcc;")
            self.completeChanged.emit()

            mode = "user-selected" if (use_user_charset and user_charset) else "auto-detected"
            logger.info(f"Segmentation complete ({mode}): {found}/{expected} characters, set: {charset_desc}")

        except Exception as e:
            logger.error(f"Auto-segmentation failed: {e}")
            self.status_text.setPlainText(f"Error: {e}")
            self.status_text.setStyleSheet("background: #fff0f0; border: 1px solid #ffcccc;")
            # Fall back to manual segmentation
            self.run_segmentation()

    def _update_charset_selection(self, charset: str, description: str):
        """Update the charset selection in ImageUploadPage based on detection.

        Indices match combo order (most comprehensive first):
        0: Full (A-Z, a-z, 0-9)
        1: Uppercase + Lowercase
        2: Uppercase + Digits
        3: Uppercase (A-Z)
        4: Lowercase (a-z)
        5: Custom...
        """
        wizard = self.wizard()
        page1: ImageUploadPage = wizard.page(0)

        charset_len = len(charset)
        if charset_len == 26:
            if charset == UPPERCASE:
                page1.charset_combo.setCurrentIndex(3)  # Uppercase
            else:
                page1.charset_combo.setCurrentIndex(4)  # Lowercase
        elif charset_len == 36:
            page1.charset_combo.setCurrentIndex(2)  # Uppercase + Digits
        elif charset_len == 52:
            page1.charset_combo.setCurrentIndex(1)  # Uppercase + Lowercase
        elif charset_len >= 62:
            page1.charset_combo.setCurrentIndex(0)  # Full
        else:
            # Use custom
            page1.charset_combo.setCurrentIndex(5)
            page1.custom_chars_edit.setText(charset)

    def run_segmentation(self, use_ai: bool = False):
        """Run segmentation with current settings (manual mode)."""
        wizard = self.wizard()
        page1: ImageUploadPage = wizard.page(0)

        if not page1.image_path:
            return

        try:
            # Get settings
            # Order: 0=Row-Column, 1=Contour-based, 2=Grid-based, 3=Auto Detect
            method_idx = self.method_combo.currentIndex()
            methods = [SegmentationMethod.ROW_COLUMN, SegmentationMethod.CONTOUR, SegmentationMethod.GRID, SegmentationMethod.AUTO]
            method = methods[method_idx]

            expected_chars = page1.get_expected_chars()

            # If punctuation checkbox is enabled, add punctuation to charset
            if self.small_glyphs_check.isChecked():
                for char in PUNCTUATION:
                    if char not in expected_chars:
                        expected_chars += char

            # Create segmenter
            segmenter = AlphabetSegmenter(
                method=method,
                expected_chars=expected_chars,
                padding=self.padding_spin.value(),
                invert=self.invert_check.isChecked(),
                include_small_glyphs=self.small_glyphs_check.isChecked(),
                use_ai=use_ai,
            )

            # Run segmentation
            grid_rows = self.rows_spin.value() if method == SegmentationMethod.GRID else None
            grid_cols = self.cols_spin.value() if method == SegmentationMethod.GRID else None

            self.result = segmenter.segment(
                page1.image_path,
                grid_rows=grid_rows,
                grid_cols=grid_cols,
            )

            # Generate preview
            preview = segmenter.preview_segmentation(page1.image_path, self.result)
            self.display_preview(preview)

            # Update status with missing character info
            found = len(self.result.characters)
            expected = len(expected_chars)
            found_labels = {c.label for c in self.result.characters}
            missing_chars = [c for c in expected_chars if c not in found_labels]

            status = f"Found {found} of {expected} characters."

            # Show missing characters if any
            if missing_chars:
                missing_display = ' '.join(missing_chars)
                status += f"\n\n❌ Missing characters ({len(missing_chars)}): {missing_display}"

            # Check for character count warnings (these are critical)
            has_count_warning = any("EXTRA" in w or "MISSING" in w for w in self.result.warnings)

            if self.result.warnings:
                status += "\n\n⚠️ WARNINGS:\n" + "\n".join(self.result.warnings)

            self.status_text.setPlainText(status)

            # Style warnings in red if there's a count mismatch
            if has_count_warning or missing_chars:
                self.status_text.setStyleSheet("background: #fff0f0; border: 1px solid #ffcccc;")
                logger.warning(f"Character count mismatch detected - user should verify mappings")
            else:
                self.status_text.setStyleSheet("background: #f0fff0; border: 1px solid #ccffcc;")

            self.completeChanged.emit()

            logger.info(f"Segmentation complete: {found}/{expected} characters")

        except Exception as e:
            logger.error(f"Segmentation failed: {e}")
            self.status_text.setPlainText(f"Error: {e}")
            self.status_text.setStyleSheet("background: #fff0f0; border: 1px solid #ffcccc;")

    def run_segmentation_with_ai(self):
        """Run segmentation with AI assistance enabled."""
        self.run_segmentation(use_ai=True)

    def display_preview(self, preview: np.ndarray):
        """Display the preview image scaled to fit available space."""
        h, w = preview.shape[:2]
        bytes_per_line = 3 * w

        qimg = QImage(preview.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._preview_pixmap = QPixmap.fromImage(qimg)

        self._scale_preview_to_fit()

    def _scale_preview_to_fit(self):
        """Scale the preview pixmap to use full available space."""
        if self._preview_pixmap is None:
            return

        # Get available size directly from the preview label
        available_width = max(300, self.preview_image.width() - 4)
        available_height = max(200, self.preview_image.height() - 4)

        # Scale to fit while maintaining aspect ratio
        scaled = self._preview_pixmap.scaled(
            available_width, available_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_image.setPixmap(scaled)

    def resizeEvent(self, event):
        """Handle resize to rescale preview image."""
        super().resizeEvent(event)
        if self._preview_pixmap is not None:
            # Use a slight delay to ensure layout is complete
            QTimer.singleShot(10, self._scale_preview_to_fit)

    def isComplete(self) -> bool:
        return self.result is not None and len(self.result.characters) > 0


class GlyphGenerationWorker(QThread):
    """Worker thread for generating missing glyphs."""

    progress = Signal(int, int, str)  # current, total, char
    finished = Signal(list)  # List of GlyphGenerationResult
    error = Signal(str)

    def __init__(
        self,
        generator,
        chars: List[str],
        reference_glyphs: List,
        target_height: int,
        parent=None
    ):
        super().__init__(parent)
        self.generator = generator
        self.chars = chars
        self.reference_glyphs = reference_glyphs
        self.target_height = target_height

    def run(self):
        try:
            results = self.generator.generate_multiple(
                self.chars,
                self.reference_glyphs,
                self.target_height,
                progress_callback=lambda cur, tot, ch: self.progress.emit(cur, tot, ch),
            )
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"Glyph generation worker error: {e}", exc_info=True)
            self.error.emit(str(e))


class CharacterMappingPage(QWizardPage):
    """
    Step 3: Verify and edit character mappings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Verify Character Mapping")
        self.setSubTitle("Review and correct character labels if needed")
        self.char_widgets: Dict[str, QWidget] = {}
        self.missing_chars: List[str] = []
        self.missing_widgets: Dict[str, QWidget] = {}
        self.selected_chars: set = set()  # Characters selected for AI identification
        self._generation_worker: Optional[GlyphGenerationWorker] = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Top bar with instructions and AI button
        top_bar = QHBoxLayout()

        instructions = QLabel(
            "Each detected character is shown with its assigned label. "
            "Click on a character to change its label if the detection was incorrect."
        )
        instructions.setWordWrap(True)
        top_bar.addWidget(instructions, 1)

        # AI provider selection
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItem("Claude (Opus 4.5)", "anthropic")
        self.ai_provider_combo.addItem("Gemini (Pro)", "gemini")
        self.ai_provider_combo.setToolTip("Select AI provider for character identification")
        self.ai_provider_combo.setMaximumWidth(130)
        top_bar.addWidget(self.ai_provider_combo)

        # AI identification button
        self.ai_identify_btn = QPushButton("Identify with AI")
        self.ai_identify_btn.setToolTip(
            "Use AI to identify selected characters.\n"
            "Click characters to select them first, then click this button.\n"
            "Claude Opus 4.5 recommended for best accuracy."
        )
        self.ai_identify_btn.clicked.connect(self.identify_with_ai)
        self.ai_identify_btn.setMaximumWidth(120)
        top_bar.addWidget(self.ai_identify_btn)

        # Select all/none buttons for AI identification
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setToolTip("Select all characters for AI identification")
        self.select_all_btn.clicked.connect(self.select_all_chars)
        self.select_all_btn.setMaximumWidth(80)
        top_bar.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.setToolTip("Clear character selection")
        self.select_none_btn.clicked.connect(self.select_no_chars)
        self.select_none_btn.setMaximumWidth(80)
        top_bar.addWidget(self.select_none_btn)

        # Generate missing glyphs button
        self.generate_missing_btn = QPushButton("Generate Missing")
        self.generate_missing_btn.setToolTip(
            "Generate missing characters using AI image generation.\n"
            "Uses the image model selected in the main window."
        )
        self.generate_missing_btn.clicked.connect(self.generate_missing_glyphs)
        self.generate_missing_btn.setMaximumWidth(120)
        self.generate_missing_btn.setEnabled(False)  # Disabled until missing chars detected
        top_bar.addWidget(self.generate_missing_btn)

        layout.addLayout(top_bar)

        # Missing characters section (shown only when there are missing chars)
        self.missing_section = QGroupBox("Missing Characters")
        self.missing_section.setStyleSheet(
            "QGroupBox { border: 2px dashed #ff9900; border-radius: 6px; margin-top: 6px; padding-top: 10px; }"
            "QGroupBox::title { color: #ff9900; }"
        )
        self.missing_section.setVisible(False)
        missing_layout = QHBoxLayout(self.missing_section)
        missing_layout.setSpacing(10)
        self.missing_grid = QHBoxLayout()
        missing_layout.addLayout(self.missing_grid)
        missing_layout.addStretch()
        layout.addWidget(self.missing_section)

        # Scrollable character grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)

        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll)

        # Summary
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("margin-top: 10px;")
        layout.addWidget(self.summary_label)

    def initializePage(self):
        """Called when page becomes visible."""
        # Clear existing widgets
        for widget in self.char_widgets.values():
            widget.deleteLater()
        self.char_widgets.clear()

        # Clear missing widgets
        for widget in self.missing_widgets.values():
            widget.deleteLater()
        self.missing_widgets.clear()
        self.missing_chars.clear()

        # Clear missing grid layout
        while self.missing_grid.count():
            item = self.missing_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get segmentation result from previous page
        wizard = self.wizard()
        page1: ImageUploadPage = wizard.page(0)
        page2: SegmentationPage = wizard.page(1)

        if not page2.result:
            return

        # Create character preview widgets
        chars = page2.result.characters
        cols = 8
        for i, char in enumerate(chars):
            row = i // cols
            col = i % cols

            widget = self.create_char_widget(char)
            self.grid_layout.addWidget(widget, row, col)
            self.char_widgets[char.label] = widget

        # Detect missing characters
        expected_chars = page1.get_expected_chars()
        # Add punctuation if enabled on segmentation page
        if page2.small_glyphs_check.isChecked():
            for char in PUNCTUATION:
                if char not in expected_chars:
                    expected_chars += char

        found_labels = {c.label for c in chars}
        self.missing_chars = [c for c in expected_chars if c not in found_labels]

        # Auto-mirror characters that can be created from existing glyphs
        self._auto_mirror_glyphs(page2.result, found_labels)

        # Show missing characters section if any are missing
        if self.missing_chars:
            self.missing_section.setVisible(True)
            self.generate_missing_btn.setEnabled(True)

            # Create placeholder widgets for missing chars
            for char in self.missing_chars:
                widget = self._create_missing_char_widget(char)
                self.missing_grid.addWidget(widget)
                self.missing_widgets[char] = widget

            self.missing_section.setTitle(f"Missing Characters ({len(self.missing_chars)})")
            logger.info(f"Missing characters detected: {self.missing_chars}")
        else:
            self.missing_section.setVisible(False)
            self.generate_missing_btn.setEnabled(False)

        # Update summary
        total = len(chars)
        missing = len(self.missing_chars)
        if missing > 0:
            self.summary_label.setText(f"Detected: {total} | Missing: {missing}")
        else:
            self.summary_label.setText(f"Total characters: {total}")
        self.completeChanged.emit()

    def _create_missing_char_widget(self, char: str) -> QWidget:
        """Create a placeholder widget for a missing character."""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Box)
        widget.setStyleSheet(
            "QFrame { border: 2px dashed #ff9900; border-radius: 4px; padding: 4px; background: #fff8f0; }"
            "QFrame:hover { border-color: #ff6600; background: #fff0e0; }"
        )
        widget.setFixedSize(80, 90)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Placeholder area
        placeholder = QLabel("?")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setFixedSize(60, 50)
        placeholder.setStyleSheet(
            "font-size: 24px; color: #999; border: 1px dashed #ccc; border-radius: 4px;"
        )
        layout.addWidget(placeholder, alignment=Qt.AlignCenter)

        # Character label
        label = QLabel(char)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ff6600;")
        layout.addWidget(label, alignment=Qt.AlignCenter)

        return widget

    def _auto_mirror_glyphs(self, segmentation_result, found_labels: set):
        """
        Automatically create missing glyphs by mirroring existing ones.

        For example, if backslash is missing but forward slash exists,
        create backslash by mirroring the forward slash.
        """
        # Mirror pairs: (missing_char, source_char, mirror_type)
        mirror_pairs = [
            ('\\', '/', 'horizontal'),  # backslash from forward slash
        ]

        for missing_char, source_char, mirror_type in mirror_pairs:
            # Check if we need this character and have the source
            if missing_char not in self.missing_chars:
                continue
            if source_char not in found_labels:
                continue

            # Find the source glyph
            source_glyph = None
            for glyph in segmentation_result.characters:
                if glyph.label == source_char:
                    source_glyph = glyph
                    break

            if source_glyph is None or source_glyph.image is None:
                continue

            logger.info(f"Auto-mirroring '{source_char}' to create '{missing_char}'")

            try:
                # Mirror the image
                pil_img = source_glyph.to_pil()

                if mirror_type == 'horizontal':
                    mirrored = pil_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                elif mirror_type == 'vertical':
                    mirrored = pil_img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                else:
                    continue

                # Convert back to numpy array
                mirrored_array = np.array(mirrored)

                # Handle grayscale conversion if needed
                if len(mirrored_array.shape) == 3 and mirrored_array.shape[2] == 4:
                    # RGBA - convert to grayscale
                    from PIL import ImageOps
                    mirrored_gray = mirrored.convert('L')
                    mirrored_array = np.array(mirrored_gray)

                # Create the CharacterCell
                from core.font_generator import CharacterCell
                h, w = mirrored_array.shape[:2]
                new_cell = CharacterCell(
                    label=missing_char,
                    bbox=(0, 0, w, h),
                    image=mirrored_array,
                    confidence=1.0,  # Perfect match - exact mirror
                    row=-1,
                    col=-1,
                )

                # Add to segmentation result
                segmentation_result.characters.append(new_cell)

                # Remove from missing list
                self.missing_chars.remove(missing_char)

                logger.info(f"Successfully created '{missing_char}' by mirroring '{source_char}'")

            except Exception as e:
                logger.error(f"Failed to auto-mirror '{source_char}' to '{missing_char}': {e}")

    def create_char_widget(self, char) -> QWidget:
        """Create a widget for a single character with selection support."""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Box)
        widget.setProperty("char_label", char.label)  # Store label for selection lookup
        widget.setProperty("char_obj", char)  # Store char object for AI identification
        self._update_widget_style(widget, char.label in self.selected_chars)
        widget.setCursor(Qt.PointingHandCursor)

        # Make widget clickable for selection
        widget.mousePressEvent = lambda event, c=char, w=widget: self.toggle_char_selection(c, w)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Character image
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(60, 60)
        img_label.setScaledContents(False)

        if char.image is not None:
            pil_img = char.to_pil()
            pil_img = pil_img.convert("RGB")

            # Convert to QPixmap - must specify bytes_per_line to avoid misalignment
            data = pil_img.tobytes("raw", "RGB")
            bytes_per_line = pil_img.width * 3  # 3 bytes per pixel for RGB
            qimg = QImage(data, pil_img.width, pil_img.height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            # Scale to fit within label with margin (50x50 in 60x60 label)
            scaled = pixmap.scaled(
                50, 50,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            img_label.setPixmap(scaled)

        layout.addWidget(img_label)

        # Label
        label_edit = QLineEdit(char.label)
        label_edit.setMaxLength(1)
        label_edit.setAlignment(Qt.AlignCenter)
        label_edit.setFixedWidth(40)
        label_edit.setStyleSheet("font-weight: bold; font-size: 14px;")
        label_edit.textChanged.connect(lambda text, c=char: self.on_label_changed(c, text))
        layout.addWidget(label_edit, alignment=Qt.AlignCenter)

        return widget

    def _update_widget_style(self, widget: QFrame, selected: bool):
        """Update widget style based on selection state."""
        if selected:
            widget.setStyleSheet(
                "QFrame { border: 3px solid #00aa00; border-radius: 4px; padding: 4px; background: #e0ffe0; }"
                "QFrame:hover { border-color: #00cc00; }"
            )
        else:
            widget.setStyleSheet(
                "QFrame { border: 1px solid #666; border-radius: 4px; padding: 4px; }"
                "QFrame:hover { border-color: #00aaff; }"
            )

    def toggle_char_selection(self, char, widget: QFrame):
        """Toggle selection state of a character for AI identification."""
        label = char.label
        if label in self.selected_chars:
            self.selected_chars.discard(label)
            self._update_widget_style(widget, False)
        else:
            self.selected_chars.add(label)
            self._update_widget_style(widget, True)
        # Update button text to show selection count
        count = len(self.selected_chars)
        if count > 0:
            self.ai_identify_btn.setText(f"Identify ({count})")
        else:
            self.ai_identify_btn.setText("Identify with AI")

    def select_all_chars(self):
        """Select all characters for AI identification."""
        wizard = self.wizard()
        page2: SegmentationPage = wizard.page(1)
        if not page2.result:
            return
        for char in page2.result.characters:
            self.selected_chars.add(char.label)
            if char.label in self.char_widgets:
                self._update_widget_style(self.char_widgets[char.label], True)
        count = len(self.selected_chars)
        self.ai_identify_btn.setText(f"Identify ({count})")

    def select_no_chars(self):
        """Clear all character selections."""
        for label in list(self.selected_chars):
            if label in self.char_widgets:
                self._update_widget_style(self.char_widgets[label], False)
        self.selected_chars.clear()
        self.ai_identify_btn.setText("Identify with AI")

    def on_label_changed(self, char, new_label: str):
        """Handle character label change."""
        if new_label:
            old_label = char.label
            char.label = new_label
            logger.debug(f"Changed label: '{old_label}' -> '{new_label}'")

            # Update char_widgets dict key if changed
            if old_label != new_label and old_label in self.char_widgets:
                widget = self.char_widgets.pop(old_label)
                widget.setProperty("char_label", new_label)
                self.char_widgets[new_label] = widget

                # Update selection tracking
                if old_label in self.selected_chars:
                    self.selected_chars.discard(old_label)
                    self.selected_chars.add(new_label)

            # Refresh missing characters list
            self._refresh_missing_chars()

    def _refresh_missing_chars(self):
        """Recalculate and update the missing characters display."""
        wizard = self.wizard()
        page1: ImageUploadPage = wizard.page(0)
        page2: SegmentationPage = wizard.page(1)

        if not page2.result:
            return

        # Get expected characters
        expected_chars = page1.get_expected_chars()
        if page2.small_glyphs_check.isChecked():
            for char in PUNCTUATION:
                if char not in expected_chars:
                    expected_chars += char

        # Find which characters are now present
        found_labels = {c.label for c in page2.result.characters}

        # Calculate new missing chars
        new_missing = [c for c in expected_chars if c not in found_labels]

        # Check if missing chars changed
        if set(new_missing) == set(self.missing_chars):
            return  # No change

        self.missing_chars = new_missing

        # Clear existing missing widgets
        for widget in self.missing_widgets.values():
            widget.deleteLater()
        self.missing_widgets.clear()

        # Clear missing grid layout
        while self.missing_grid.count():
            item = self.missing_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Rebuild missing section
        if self.missing_chars:
            self.missing_section.setVisible(True)
            self.generate_missing_btn.setEnabled(True)

            for char in self.missing_chars:
                widget = self._create_missing_char_widget(char)
                self.missing_grid.addWidget(widget)
                self.missing_widgets[char] = widget

            self.missing_section.setTitle(f"Missing Characters ({len(self.missing_chars)})")
            logger.info(f"Refreshed missing characters: {self.missing_chars}")
        else:
            self.missing_section.setVisible(False)
            self.generate_missing_btn.setEnabled(False)
            logger.info("All expected characters now present")

        # Update summary
        total = len(page2.result.characters)
        missing = len(self.missing_chars)
        if missing > 0:
            self.summary_label.setText(f"Detected: {total} | Missing: {missing}")
        else:
            self.summary_label.setText(f"Total characters: {total}")

        self.completeChanged.emit()

    def generate_missing_glyphs(self):
        """Generate missing glyphs using AI image generation."""
        if not self.missing_chars:
            QMessageBox.information(
                self, "No Missing Characters",
                "All expected characters have been detected."
            )
            return

        # Get main window to access provider/model settings
        wizard = self.wizard()
        main_window = wizard.parent()

        if main_window is None:
            QMessageBox.warning(
                self, "Error",
                "Could not access main window settings."
            )
            return

        # Get provider and model from main window
        provider = getattr(main_window, 'current_provider', None)
        model = getattr(main_window, 'current_model', None)
        config = getattr(main_window, 'config', None)

        if not provider or not model:
            QMessageBox.warning(
                self, "No Image Model Selected",
                "Please select an image generation provider and model in the main window."
            )
            return

        # Get API key
        api_key = None
        auth_mode = "api-key"
        if config:
            api_key = config.get_api_key(provider)
            auth_mode = getattr(main_window, 'current_auth_mode', 'api-key') or 'api-key'

        if not api_key and auth_mode != "gcloud":
            QMessageBox.warning(
                self, "No API Key",
                f"No API key configured for {provider}.\n"
                "Please configure an API key in the Settings tab."
            )
            return

        logger.info(f"Starting glyph generation: provider={provider}, model={model}, auth_mode={auth_mode}")
        logger.info(f"Missing characters to generate: {self.missing_chars}")

        # Get reference glyphs from segmentation
        page2: SegmentationPage = wizard.page(1)
        if not page2.result or not page2.result.characters:
            QMessageBox.warning(
                self, "No Reference Characters",
                "No detected characters available as style reference."
            )
            return

        reference_glyphs = list(page2.result.characters)

        # Calculate target height from existing glyphs
        heights = [c.image.shape[0] for c in reference_glyphs if c.image is not None and len(c.image.shape) >= 1]
        target_height = int(np.median(heights)) if heights else 64
        logger.info(f"Target glyph height: {target_height}px (median of {len(heights)} glyphs)")

        # Create generator
        from core.font_generator import GlyphGenerator
        generator = GlyphGenerator(
            provider=provider,
            model=model,
            api_key=api_key or "",
            auth_mode=auth_mode,
        )

        # Disable button during generation
        self.generate_missing_btn.setEnabled(False)
        self.generate_missing_btn.setText("Generating...")

        # Start worker thread
        self._generation_worker = GlyphGenerationWorker(
            generator=generator,
            chars=list(self.missing_chars),
            reference_glyphs=reference_glyphs,
            target_height=target_height,
            parent=self,
        )
        self._generation_worker.progress.connect(self._on_generation_progress)
        self._generation_worker.finished.connect(self._on_generation_finished)
        self._generation_worker.error.connect(self._on_generation_error)
        self._generation_worker.start()

    def _on_generation_progress(self, current: int, total: int, char: str):
        """Handle generation progress updates."""
        if total > 0:
            self.generate_missing_btn.setText(f"Generating {current+1}/{total}...")

            # Update the placeholder widget for the current character
            if char and char in self.missing_widgets:
                widget = self.missing_widgets[char]
                # Find the placeholder label and update it
                for child in widget.findChildren(QLabel):
                    if child.text() == "?":
                        child.setText("...")
                        child.setStyleSheet(
                            "font-size: 18px; color: #ff9900; border: 1px dashed #ff9900; border-radius: 4px;"
                        )
                        break

    def _on_generation_finished(self, results):
        """Handle generation completion."""
        self.generate_missing_btn.setEnabled(True)
        self.generate_missing_btn.setText("Generate Missing")

        wizard = self.wizard()
        page2: SegmentationPage = wizard.page(1)

        success_count = 0
        failed_chars = []

        for result in results:
            if result.success and result.cell:
                # Add the generated character to the segmentation result
                page2.result.characters.append(result.cell)
                success_count += 1
                logger.info(f"Added generated glyph '{result.character}' to character set")
            else:
                failed_chars.append(result.character)
                logger.warning(f"Failed to generate '{result.character}': {result.error}")

        # Refresh the page to show new characters
        self.initializePage()

        # Show summary
        if success_count > 0:
            msg = f"Successfully generated {success_count} character(s)."
            if failed_chars:
                msg += f"\n\nFailed to generate: {', '.join(failed_chars)}"
            QMessageBox.information(self, "Generation Complete", msg)
        else:
            QMessageBox.warning(
                self, "Generation Failed",
                f"Failed to generate any characters.\n\nFailed: {', '.join(failed_chars)}"
            )

    def _on_generation_error(self, error_msg: str):
        """Handle generation error."""
        self.generate_missing_btn.setEnabled(True)
        self.generate_missing_btn.setText("Generate Missing")

        logger.error(f"Glyph generation error: {error_msg}")
        QMessageBox.warning(
            self, "Generation Error",
            f"An error occurred during glyph generation:\n\n{error_msg}"
        )

    def identify_with_ai(self):
        """Use AI to identify selected or small/ambiguous glyphs."""
        wizard = self.wizard()
        page2: SegmentationPage = wizard.page(1)

        if not page2.result or not page2.result.characters:
            QMessageBox.warning(
                self, "No Characters",
                "No characters detected to identify."
            )
            return

        from core.font_generator import AIGlyphIdentifier, PUNCTUATION, get_position_hint

        # Get selected provider from dropdown
        provider = self.ai_provider_combo.currentData()
        provider_name = self.ai_provider_combo.currentText()

        try:
            identifier = AIGlyphIdentifier(provider=provider)
            logger.info(f"AI identifier initialized with provider: {provider}")
        except Exception as e:
            if provider == "anthropic":
                key_msg = "Make sure you have an Anthropic API key configured in Settings."
            else:
                key_msg = "Make sure you have a Google API key configured in Settings."
            QMessageBox.warning(
                self, "AI Not Available",
                f"Could not initialize AI identifier: {e}\n\n{key_msg}"
            )
            return

        # Calculate row heights for position hints
        # Group characters by row and find max height per row
        row_heights = {}
        for char in page2.result.characters:
            if char.row is not None and char.row >= 0:
                _, _, _, h = char.bbox
                if char.row not in row_heights:
                    row_heights[char.row] = h
                else:
                    row_heights[char.row] = max(row_heights[char.row], h)

        # Determine which characters to identify
        chars_to_identify = []

        if self.selected_chars:
            # Use selected characters
            for char in page2.result.characters:
                if char.label in self.selected_chars and char.image is not None:
                    chars_to_identify.append(char)
            logger.info(f"Identifying {len(chars_to_identify)} selected characters with {provider_name}")
        else:
            # No selection - fall back to small/punctuation characters
            for char in page2.result.characters:
                if char.image is not None:
                    w, h = char.image.shape[1], char.image.shape[0] if len(char.image.shape) > 1 else 1
                    if max(w, h) < 30 or char.label in PUNCTUATION:
                        chars_to_identify.append(char)

            if not chars_to_identify:
                # If no small chars, offer to identify all
                reply = QMessageBox.question(
                    self, "No Characters Selected",
                    "No characters selected and no small characters found.\n\n"
                    "Click on characters to select them, or click Yes to identify ALL characters.",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    chars_to_identify = [c for c in page2.result.characters if c.image is not None]
                else:
                    return

        if not chars_to_identify:
            QMessageBox.information(self, "Nothing to Identify", "No characters selected for identification.")
            return

        # Show progress
        self.ai_identify_btn.setEnabled(False)
        self.ai_identify_btn.setText("Identifying...")
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)

        try:
            # Identify each character
            updated_count = 0
            total = len(chars_to_identify)
            for i, char in enumerate(chars_to_identify):
                self.ai_identify_btn.setText(f"Identifying {i+1}/{total}...")
                QApplication.processEvents()  # Update UI

                # Calculate position hint for baseline disambiguation
                position_hint = None
                if char.row is not None and char.row >= 0 and char.row in row_heights:
                    row_height = row_heights[char.row]
                    # Get glyph's relative position within its row
                    _, glyph_y, _, glyph_h = char.bbox
                    # For small glyphs, position hint helps distinguish ' vs , etc.
                    if glyph_h < row_height * 0.5:
                        position_hint = get_position_hint(0, glyph_h, row_height)
                        logger.debug(f"Position hint for '{char.label}': {position_hint}")

                result = identifier.identify_glyph(char.image, position_hint=position_hint)
                if result.identified_char and result.confidence > 0.5:
                    if result.identified_char != char.label:
                        logger.info(
                            f"AI identified '{char.label}' as '{result.identified_char}' "
                            f"(confidence: {result.confidence:.0%})"
                        )
                        char.label = result.identified_char
                        updated_count += 1

            # Clear selections and refresh the display
            self.selected_chars.clear()
            self.initializePage()

            # Show summary
            if updated_count > 0:
                QMessageBox.information(
                    self, "AI Identification Complete",
                    f"Updated {updated_count} of {total} character labels using {provider_name}.\n\n"
                    "Please review the changes and correct any errors."
                )
            else:
                QMessageBox.information(
                    self, "AI Identification Complete",
                    f"AI ({provider_name}) confirmed all {total} character labels. No changes needed."
                )

        except Exception as e:
            logger.error(f"AI identification failed: {e}")
            QMessageBox.warning(
                self, "Identification Failed",
                f"AI identification encountered an error:\n{e}"
            )
        finally:
            self.ai_identify_btn.setEnabled(True)
            self.ai_identify_btn.setText("Identify with AI")
            self.select_all_btn.setEnabled(True)
            self.select_none_btn.setEnabled(True)

    def isComplete(self) -> bool:
        wizard = self.wizard()
        page2: SegmentationPage = wizard.page(1)
        return page2.result is not None and len(page2.result.characters) > 0


class FontSettingsPage(QWizardPage):
    """
    Step 4: Configure font metadata and settings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Font Settings")
        self.setSubTitle("Configure font name, style, and export options")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Font info group
        info_group = QGroupBox("Font Information")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("Font Family:"), 0, 0)
        self.family_edit = QLineEdit("MyFont")
        self.family_edit.setPlaceholderText("Enter font family name")
        info_layout.addWidget(self.family_edit, 0, 1)

        info_layout.addWidget(QLabel("Style:"), 1, 0)
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Regular", "Bold", "Italic", "Light"])
        info_layout.addWidget(self.style_combo, 1, 1)

        info_layout.addWidget(QLabel("Version:"), 2, 0)
        self.version_edit = QLineEdit("1.0")
        info_layout.addWidget(self.version_edit, 2, 1)

        info_layout.addWidget(QLabel("Designer:"), 3, 0)
        self.designer_edit = QLineEdit()
        self.designer_edit.setPlaceholderText("Your name (optional)")
        info_layout.addWidget(self.designer_edit, 3, 1)

        info_layout.addWidget(QLabel("Copyright:"), 4, 0)
        self.copyright_edit = QLineEdit()
        self.copyright_edit.setPlaceholderText("Copyright notice (optional)")
        info_layout.addWidget(self.copyright_edit, 4, 1)

        layout.addWidget(info_group)

        # Vectorization settings
        vec_group = QGroupBox("Vectorization Quality")
        vec_layout = QVBoxLayout(vec_group)

        smooth_layout = QHBoxLayout()
        smooth_layout.addWidget(QLabel("Smoothing:"))

        self.smoothing_slider = QSlider(Qt.Horizontal)
        self.smoothing_slider.setRange(0, 4)
        self.smoothing_slider.setValue(1)  # Default to LOW for better detail preservation
        self.smoothing_slider.setTickPosition(QSlider.TicksBelow)
        self.smoothing_slider.setTickInterval(1)
        smooth_layout.addWidget(self.smoothing_slider)

        self.smoothing_label = QLabel("Low")
        self.smoothing_slider.valueChanged.connect(self.on_smoothing_changed)
        smooth_layout.addWidget(self.smoothing_label)

        vec_layout.addLayout(smooth_layout)

        quality_note = QLabel(
            "None/Low: Preserves maximum detail from source image (recommended for smooth source images). "
            "Medium/High: Applies smoothing to clean up rough edges but may lose fine details."
        )
        quality_note.setWordWrap(True)
        quality_note.setStyleSheet("color: #888; font-size: 11px;")
        vec_layout.addWidget(quality_note)

        layout.addWidget(vec_group)

        # Export format
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout(format_group)

        self.ttf_radio = QCheckBox("TrueType (.ttf)")
        self.ttf_radio.setChecked(True)
        format_layout.addWidget(self.ttf_radio)

        self.otf_radio = QCheckBox("OpenType (.otf)")
        format_layout.addWidget(self.otf_radio)

        if not FONTTOOLS_AVAILABLE:
            warning = QLabel(
                "fonttools not installed. Install with: pip install fonttools"
            )
            warning.setStyleSheet("color: #ff6666;")
            format_layout.addWidget(warning)
            self.ttf_radio.setEnabled(False)
            self.otf_radio.setEnabled(False)

        layout.addWidget(format_group)

        layout.addStretch()

        # Register fields
        self.registerField("font_family*", self.family_edit)
        self.registerField("font_style", self.style_combo, "currentText")
        self.registerField("font_version", self.version_edit)

    def on_smoothing_changed(self, value):
        """Update smoothing label."""
        labels = ["None", "Low", "Medium", "High", "Maximum"]
        self.smoothing_label.setText(labels[value])

    def get_smoothing_level(self) -> SmoothingLevel:
        """Get the selected smoothing level."""
        levels = [
            SmoothingLevel.NONE,
            SmoothingLevel.LOW,
            SmoothingLevel.MEDIUM,
            SmoothingLevel.HIGH,
            SmoothingLevel.MAXIMUM,
        ]
        return levels[self.smoothing_slider.value()]

    def get_font_info(self) -> FontInfo:
        """Create FontInfo from current settings."""
        return FontInfo(
            family_name=self.family_edit.text() or "CustomFont",
            style_name=self.style_combo.currentText(),
            version=self.version_edit.text() or "1.0",
            designer=self.designer_edit.text(),
            copyright=self.copyright_edit.text(),
        )

    def isComplete(self) -> bool:
        return bool(self.family_edit.text().strip()) and FONTTOOLS_AVAILABLE

    def initializePage(self):
        """Load saved settings when page is shown."""
        settings = QSettings()

        family = settings.value(f"{SETTINGS_PREFIX}/font_family", "MyFont")
        self.family_edit.setText(family)

        style_idx = settings.value(f"{SETTINGS_PREFIX}/font_style", 0, type=int)
        self.style_combo.setCurrentIndex(style_idx)

        version = settings.value(f"{SETTINGS_PREFIX}/font_version", "1.0")
        self.version_edit.setText(version)

        designer = settings.value(f"{SETTINGS_PREFIX}/designer", "")
        self.designer_edit.setText(designer)

        copyright_text = settings.value(f"{SETTINGS_PREFIX}/copyright", "")
        self.copyright_edit.setText(copyright_text)

        smoothing = settings.value(f"{SETTINGS_PREFIX}/smoothing", 1, type=int)  # Default LOW
        self.smoothing_slider.setValue(smoothing)

        ttf = settings.value(f"{SETTINGS_PREFIX}/export_ttf", True, type=bool)
        self.ttf_radio.setChecked(ttf)

        otf = settings.value(f"{SETTINGS_PREFIX}/export_otf", False, type=bool)
        self.otf_radio.setChecked(otf)

    def save_settings(self):
        """Save current settings."""
        settings = QSettings()
        settings.setValue(f"{SETTINGS_PREFIX}/font_family", self.family_edit.text())
        settings.setValue(f"{SETTINGS_PREFIX}/font_style", self.style_combo.currentIndex())
        settings.setValue(f"{SETTINGS_PREFIX}/font_version", self.version_edit.text())
        settings.setValue(f"{SETTINGS_PREFIX}/designer", self.designer_edit.text())
        settings.setValue(f"{SETTINGS_PREFIX}/copyright", self.copyright_edit.text())
        settings.setValue(f"{SETTINGS_PREFIX}/smoothing", self.smoothing_slider.value())
        settings.setValue(f"{SETTINGS_PREFIX}/export_ttf", self.ttf_radio.isChecked())
        settings.setValue(f"{SETTINGS_PREFIX}/export_otf", self.otf_radio.isChecked())


class ExportPage(QWizardPage):
    """
    Step 5: Preview and export the font.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Preview & Export")
        self.setSubTitle("Preview your font and export to file")
        self.glyphs = []
        self.char_cells = []  # Store original character images for preview
        self.exported_path: Optional[Path] = None
        self._temp_font_path: Optional[Path] = None
        self._temp_font_id: int = -1  # Qt font database ID
        self._preview_font_family: Optional[str] = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Preview group - expandable
        preview_group = QGroupBox("Font Preview")
        preview_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout = QVBoxLayout(preview_group)

        # Sample text input - multi-line
        preview_layout.addWidget(QLabel("Sample Text:"))
        self.sample_edit = QTextEdit()
        self.sample_edit.setPlaceholderText("Enter text to preview...")
        self.sample_edit.setMaximumHeight(80)
        self.sample_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.sample_edit.textChanged.connect(self.update_preview)
        preview_layout.addWidget(self.sample_edit)

        # Preview display in a scroll area for long/wrapped text
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setStyleSheet("background: white; border: 1px solid #ccc;")
        self.preview_scroll.setMinimumHeight(150)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview_label.setStyleSheet("padding: 10px; background: white;")
        self.preview_label.setWordWrap(False)  # We handle wrapping in rendering
        self.preview_scroll.setWidget(self.preview_label)

        preview_layout.addWidget(self.preview_scroll, 1)  # Stretch factor 1

        layout.addWidget(preview_group, 1)  # Give preview group stretch priority

        # Progress - compact
        self.progress_group = QGroupBox("Processing")
        progress_layout = QVBoxLayout(self.progress_group)
        progress_layout.setContentsMargins(6, 6, 6, 6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMaximumHeight(20)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to export")
        progress_layout.addWidget(self.status_label)

        layout.addWidget(self.progress_group)

        # Export buttons
        button_layout = QHBoxLayout()

        self.export_btn = QPushButton("Export Font...")
        self.export_btn.clicked.connect(self.export_font)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color: #00cc00;")
        button_layout.addWidget(self.result_label)

        layout.addLayout(button_layout)

    def initializePage(self):
        """Called when page becomes visible."""
        # Process glyphs first to get available characters
        self.process_glyphs()

        # Build sample text showing all available characters
        wizard = self.wizard()
        page2: SegmentationPage = wizard.page(1)
        if page2.result and page2.result.characters:
            # Get all character labels sorted
            chars = [c.label for c in page2.result.characters if c.label]
            # Sort: uppercase, lowercase, digits, then punctuation
            upper = sorted([c for c in chars if c.isupper()])
            lower = sorted([c for c in chars if c.islower()])
            digits = sorted([c for c in chars if c.isdigit()])
            punct = [c for c in chars if not c.isalnum()]
            # Build display text with each category on its own line
            lines = []
            if upper:
                lines.append(''.join(upper))
            if lower:
                lines.append(''.join(lower))
            if digits:
                lines.append(''.join(digits))
            if punct:
                lines.append(''.join(punct))
            lines.append("The quick brown fox jumps over the lazy dog.")
            sample_text = '\n'.join(lines)
        else:
            sample_text = "The quick brown fox jumps over the lazy dog."

        self.sample_edit.setPlainText(sample_text)
        self.update_preview()

    def process_glyphs(self):
        """Vectorize all characters and build a temporary font for preview."""
        wizard = self.wizard()
        page2: SegmentationPage = wizard.page(1)
        page4: FontSettingsPage = wizard.page(3)

        if not page2.result:
            return

        try:
            self.status_label.setText("Vectorizing characters...")
            self.progress_bar.setValue(0)

            # Get smoothing level
            smoothing = page4.get_smoothing_level()

            # Create vectorizer
            vectorizer = GlyphVectorizer(smoothing=smoothing)

            # Vectorize each character
            chars = page2.result.characters
            self.glyphs = []
            self.char_cells = list(chars)  # Store original character cells for preview

            for i, char in enumerate(chars):
                glyph = vectorizer.vectorize(char.image, char.label)
                self.glyphs.append(glyph)

                progress = int((i + 1) / len(chars) * 80)  # 0-80% for vectorization
                self.progress_bar.setValue(progress)

            self.status_label.setText(f"Vectorized {len(self.glyphs)} characters")
            logger.info(f"Vectorized {len(self.glyphs)} glyphs")

            # Build temporary font for preview
            self._build_preview_font(page4)

        except Exception as e:
            logger.error(f"Vectorization failed: {e}")
            self.status_label.setText(f"Error: {e}")

    def _build_preview_font(self, page4: FontSettingsPage):
        """Build a temporary font file and load it into Qt for preview."""
        if not self.glyphs:
            return

        try:
            self.status_label.setText("Building preview font...")
            self.progress_bar.setValue(85)

            # Clean up previous temp font if any
            if self._temp_font_id >= 0:
                QFontDatabase.removeApplicationFont(self._temp_font_id)
                self._temp_font_id = -1

            # Get font info from settings page
            font_info = page4.get_font_info()

            # Create temp file
            temp_dir = Path(tempfile.gettempdir()) / "imageai_fonts"
            temp_dir.mkdir(parents=True, exist_ok=True)
            self._temp_font_path = temp_dir / f"{font_info.postscript_name}_preview.ttf"

            # Build the font
            builder = FontBuilder(info=font_info)
            builder.add_glyphs(self.glyphs)
            builder.build(self._temp_font_path)

            self.progress_bar.setValue(95)

            # Load into Qt font database
            self._temp_font_id = QFontDatabase.addApplicationFont(str(self._temp_font_path))

            if self._temp_font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(self._temp_font_id)
                if families:
                    self._preview_font_family = families[0]
                    logger.info(f"Loaded preview font: {self._preview_font_family}")
                    self.status_label.setText(f"Ready - Font: {self._preview_font_family}")
                else:
                    logger.warning("Font loaded but no families found")
                    self._preview_font_family = None
                    self.status_label.setText("Vectorized (preview font unavailable)")
            else:
                logger.warning(f"Failed to load font from {self._temp_font_path}")
                self._preview_font_family = None
                self.status_label.setText("Vectorized (preview font failed to load)")

            self.progress_bar.setValue(100)

        except Exception as e:
            logger.error(f"Failed to build preview font: {e}")
            self._preview_font_family = None
            self.status_label.setText(f"Vectorized {len(self.glyphs)} chars (preview error: {e})")

    def update_preview(self):
        """Update the font preview using the loaded font or fallback to bitmaps."""
        sample = self.sample_edit.toPlainText()
        if not sample:
            self.preview_label.setText("No preview available")
            return

        # If we have a loaded font, use it directly
        if self._preview_font_family:
            self._render_with_font(sample)
        elif self.char_cells:
            # Fallback to bitmap rendering
            self._render_with_bitmaps(sample)
        else:
            self.preview_label.setText("No preview available")

    def _render_with_font(self, sample: str):
        """Render preview using the loaded font with text wrapping."""
        font_size = 48
        padding = 15
        line_spacing = 1.2

        # Get available width from scroll area viewport
        available_width = self.preview_scroll.viewport().width() - 2 * padding
        if available_width < 100:
            available_width = 400  # Fallback

        # Create font
        font = QFont(self._preview_font_family, font_size)
        metrics = QFontMetrics(font)

        # Handle explicit newlines first, then word wrap each paragraph
        lines = []
        paragraphs = sample.split('\n')

        for paragraph in paragraphs:
            if not paragraph:
                lines.append("")  # Preserve blank lines
                continue

            # Word wrap within each paragraph
            words = paragraph.split(' ')
            current_line = ""

            for word in words:
                test_line = f"{current_line} {word}".strip() if current_line else word
                if metrics.horizontalAdvance(test_line) <= available_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word

            if current_line:
                lines.append(current_line)

        if not lines:
            lines = [sample]  # Fallback if no wrapping possible

        # Calculate canvas size
        line_height = int(metrics.height() * line_spacing)
        canvas_width = available_width + 2 * padding
        canvas_height = max(100, len(lines) * line_height + 2 * padding)

        image = QImage(canvas_width, canvas_height, QImage.Format_ARGB32)
        image.fill(QColor(255, 255, 255))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))

        # Draw each line
        y = padding + metrics.ascent()
        for line in lines:
            painter.drawText(padding, y, line)
            y += line_height

        painter.end()

        # Display
        pixmap = QPixmap.fromImage(image)
        self.preview_label.setPixmap(pixmap)

    def _render_with_bitmaps(self, sample: str):
        """Fallback: render preview using original bitmap images with wrapping."""
        # Build lookup from label to character cell
        cell_map = {cell.label: cell for cell in self.char_cells}

        target_height = 60
        padding = 10
        space_width = target_height // 3
        char_spacing = 2
        line_spacing = 8

        # Get available width from scroll area viewport
        available_width = self.preview_scroll.viewport().width() - 2 * padding
        if available_width < 100:
            available_width = 400  # Fallback

        # Helper to get character width
        def get_char_width(char):
            if char == " " or char == "\n":
                return space_width
            elif char in cell_map:
                cell = cell_map[char]
                h, w = cell.image.shape[:2] if len(cell.image.shape) >= 2 else (0, 0)
                if h > 0:
                    return int(w * (target_height / h)) + char_spacing
            return space_width

        # Split into lines, respecting newlines and wrapping
        lines = []
        for paragraph in sample.split('\n'):
            if not paragraph:
                lines.append([])  # Preserve blank lines
                continue

            current_line = []
            current_width = 0

            for char in paragraph:
                char_width = get_char_width(char)
                if current_width + char_width > available_width and current_line:
                    lines.append(current_line)
                    current_line = []
                    current_width = 0
                current_line.append(char)
                current_width += char_width

            if current_line:
                lines.append(current_line)

        if not lines:
            lines = [[c for c in sample]]

        # Calculate canvas size
        line_height = target_height + line_spacing
        canvas_height = max(100, len(lines) * line_height + 2 * padding)
        canvas_width = available_width + 2 * padding

        image = QImage(canvas_width, canvas_height, QImage.Format_ARGB32)
        image.fill(QColor(255, 255, 255))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        y_pos = padding
        for line_chars in lines:
            x_pos = padding
            for char in line_chars:
                if char == " ":
                    x_pos += space_width
                    continue

                if char not in cell_map:
                    painter.setPen(QPen(QColor(200, 200, 200), 1))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(x_pos, y_pos, space_width - 2, target_height)
                    x_pos += space_width
                    continue

                cell = cell_map[char]
                char_img = cell.image
                h, w = char_img.shape[:2] if len(char_img.shape) >= 2 else (0, 0)

                if h == 0:
                    continue

                scale = target_height / h
                scaled_w = int(w * scale)

                qimg = self._numpy_to_qimage(char_img)
                if qimg is None:
                    x_pos += space_width
                    continue

                scaled_pixmap = QPixmap.fromImage(qimg).scaled(
                    scaled_w, target_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                y_offset = y_pos + (target_height - scaled_pixmap.height()) // 2
                painter.drawPixmap(x_pos, y_offset, scaled_pixmap)
                x_pos += scaled_pixmap.width() + char_spacing

            y_pos += line_height

        painter.end()
        self.preview_label.setPixmap(QPixmap.fromImage(image))

    def _numpy_to_qimage(self, img: np.ndarray) -> Optional[QImage]:
        """Convert a numpy array (grayscale or RGBA) to QImage."""
        if img is None or img.size == 0:
            return None

        if len(img.shape) == 2:
            h, w = img.shape
            rgb = np.stack([img, img, img], axis=-1)
            return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()

        elif len(img.shape) == 3:
            h, w, c = img.shape
            if c == 4:
                return QImage(img.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
            elif c == 3:
                return QImage(img.data, w, h, 3 * w, QImage.Format_RGB888).copy()

        return None

    def _render_glyph(self, painter: QPainter, glyph: VectorGlyph, x: int, baseline_y: int, scale: float):
        """Render a single glyph using its vector paths.

        Args:
            painter: QPainter to draw with
            glyph: VectorGlyph to render
            x: X position for glyph origin
            baseline_y: Y position of the baseline (bottom of glyph area)
            scale: Scale factor to apply
        """
        for path in glyph.paths:
            qpath = QPainterPath()

            for segment in path.segments:
                cmd = segment.command
                pts = segment.points

                if cmd == PathCommand.MOVE and pts:
                    # Move to point - transform coordinates
                    # Glyph coords: Y increases upward from baseline
                    # Screen coords: Y increases downward
                    px = x + pts[0][0] * scale
                    py = baseline_y - pts[0][1] * scale
                    qpath.moveTo(px, py)

                elif cmd == PathCommand.LINE and pts:
                    px = x + pts[0][0] * scale
                    py = baseline_y - pts[0][1] * scale
                    qpath.lineTo(px, py)

                elif cmd == PathCommand.QUAD and len(pts) >= 2:
                    # Quadratic Bezier: control point, end point
                    cp = pts[0]
                    ep = pts[1]
                    qpath.quadTo(
                        x + cp[0] * scale, baseline_y - cp[1] * scale,
                        x + ep[0] * scale, baseline_y - ep[1] * scale
                    )

                elif cmd == PathCommand.CURVE and len(pts) >= 3:
                    # Cubic Bezier: control1, control2, end point
                    cp1 = pts[0]
                    cp2 = pts[1]
                    ep = pts[2]
                    qpath.cubicTo(
                        x + cp1[0] * scale, baseline_y - cp1[1] * scale,
                        x + cp2[0] * scale, baseline_y - cp2[1] * scale,
                        x + ep[0] * scale, baseline_y - ep[1] * scale
                    )

                elif cmd == PathCommand.CLOSE:
                    qpath.closeSubpath()

            # Draw the path with even-odd fill rule for proper hole handling
            qpath.setFillRule(Qt.OddEvenFill)
            painter.drawPath(qpath)

    def export_font(self):
        """Export the font to file."""
        wizard = self.wizard()
        page4: FontSettingsPage = wizard.page(3)

        # Get export settings
        font_info = page4.get_font_info()
        export_ttf = page4.ttf_radio.isChecked()
        export_otf = page4.otf_radio.isChecked()

        if not export_ttf and not export_otf:
            QMessageBox.warning(self, "No Format Selected",
                              "Please select at least one export format (TTF or OTF).")
            return

        # Get last export directory from settings
        settings = QSettings()
        last_dir = settings.value(f"{SETTINGS_PREFIX}/last_export_dir", "")

        # Build default path with restored directory or user data dir
        default_ext = ".ttf" if export_ttf else ".otf"
        default_name = f"{font_info.postscript_name}{default_ext}"
        if last_dir:
            default_path = str(Path(last_dir) / default_name)
        else:
            # Default to Fonts subdirectory in user data folder
            fonts_dir = get_user_data_dir() / "Fonts"
            fonts_dir.mkdir(parents=True, exist_ok=True)
            default_path = str(fonts_dir / default_name)

        # Determine file filter based on selected formats
        if export_ttf and export_otf:
            file_filter = "TrueType Font (*.ttf);;OpenType Font (*.otf);;All Files (*)"
        elif export_ttf:
            file_filter = "TrueType Font (*.ttf);;All Files (*)"
        else:
            file_filter = "OpenType Font (*.otf);;All Files (*)"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Font",
            default_path,
            file_filter,
        )

        if not file_path:
            return

        try:
            self.status_label.setText("Building font...")
            self.progress_bar.setValue(25)

            # Build font
            builder = FontBuilder(info=font_info)
            builder.add_glyphs(self.glyphs)

            exported_paths = []
            file_path = Path(file_path)

            # Export TTF if selected
            if export_ttf:
                ttf_path = file_path.with_suffix(".ttf")
                self.status_label.setText("Building TTF...")
                builder.build(ttf_path)
                exported_paths.append(ttf_path)
                logger.info(f"Exported TTF to {ttf_path}")

            self.progress_bar.setValue(60)

            # Export OTF if selected
            if export_otf:
                otf_path = file_path.with_suffix(".otf")
                self.status_label.setText("Building OTF...")
                builder.build(otf_path)
                exported_paths.append(otf_path)
                logger.info(f"Exported OTF to {otf_path}")

            self.progress_bar.setValue(100)
            self.status_label.setText("Export complete!")

            # Store the first exported path for reference
            self.exported_path = exported_paths[0]

            # Build result message
            if len(exported_paths) == 1:
                self.result_label.setText(f"Saved to: {exported_paths[0].name}")
                msg = f"Font successfully exported to:\n{exported_paths[0]}"
            else:
                names = ", ".join(p.name for p in exported_paths)
                self.result_label.setText(f"Saved: {names}")
                msg = "Font successfully exported to:\n" + "\n".join(str(p) for p in exported_paths)

            QMessageBox.information(self, "Export Complete", msg)

        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.status_label.setText(f"Export failed: {e}")
            QMessageBox.warning(self, "Export Failed", f"Failed to export font:\n{e}")

    def save_settings(self):
        """Save current settings."""
        settings = QSettings()
        settings.setValue(f"{SETTINGS_PREFIX}/sample_text", self.sample_edit.toPlainText())
        if self.exported_path:
            settings.setValue(f"{SETTINGS_PREFIX}/last_export_dir", str(self.exported_path.parent))


class FontGeneratorWizard(QWizard):
    """
    Main wizard for font generation from alphabet images.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Font Generator")
        self.setMinimumSize(800, 600)
        self.setWizardStyle(QWizard.ModernStyle)

        # Add pages
        self.addPage(ImageUploadPage(self))       # Page 0
        self.addPage(SegmentationPage(self))      # Page 1
        self.addPage(CharacterMappingPage(self))  # Page 2
        self.addPage(FontSettingsPage(self))      # Page 3
        self.addPage(ExportPage(self))            # Page 4

        # Set button text
        self.setButtonText(QWizard.NextButton, "Next >")
        self.setButtonText(QWizard.BackButton, "< Back")
        self.setButtonText(QWizard.FinishButton, "Done")
        self.setButtonText(QWizard.CancelButton, "Cancel")

        # Connect signals
        self.finished.connect(self.on_finished)

        logger.info("Font Generator wizard initialized")

    def on_finished(self, result):
        """Handle wizard completion."""
        # Always save settings, regardless of how wizard ended
        self.save_all_settings()

        if result == QWizard.Accepted:
            logger.info("Font Generator wizard completed successfully")
        else:
            logger.info("Font Generator wizard cancelled")

    def save_all_settings(self):
        """Save settings from all pages."""
        # Page 0: Image Upload
        page0 = self.page(0)
        if hasattr(page0, 'save_settings'):
            page0.save_settings()

        # Page 1: Segmentation
        page1 = self.page(1)
        if hasattr(page1, 'save_settings'):
            page1.save_settings()

        # Page 2: Character Mapping
        page2 = self.page(2)
        if hasattr(page2, 'save_settings'):
            page2.save_settings()

        # Page 3: Font Settings
        page3 = self.page(3)
        if hasattr(page3, 'save_settings'):
            page3.save_settings()

        # Page 4: Export
        page4 = self.page(4)
        if hasattr(page4, 'save_settings'):
            page4.save_settings()

        # Force sync to disk to ensure settings persist
        settings = QSettings()
        settings.sync()

        logger.debug("Font Generator settings saved and synced to disk")
