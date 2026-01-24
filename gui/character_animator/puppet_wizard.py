"""
Multi-step wizard for creating Character Animator puppets.

Provides a guided workflow:
1. Dependency check and installation
2. Image selection and preview
3. Body part detection with manual adjustment
4. Viseme generation progress
5. Export format selection and save
"""

import logging
from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QProgressBar, QGroupBox,
    QComboBox, QLineEdit, QFrame, QScrollArea, QWidget,
    QSplitter, QTextEdit, QCheckBox, QSpinBox, QMessageBox,
    QDialog,
)
from PySide6.QtCore import Qt, Signal, QThread, QSize, QSettings
from PySide6.QtGui import QPixmap, QImage, QFont, QPainter, QPen, QColor

from PIL import Image
import numpy as np

from core.character_animator.availability import (
    check_all_dependencies,
    get_install_status_message,
    can_create_puppet,
    is_full_installation,
)
from core.character_animator.models import (
    PuppetStructure, ExportFormat, VisemeSet, EyeBlinkSet,
)
from core.constants import get_user_data_dir
from .install_dialog import PuppetInstallConfirmDialog, PuppetInstallProgressDialog
from core.discord_rpc import discord_rpc, ActivityState

logger = logging.getLogger(__name__)


class DependencyCheckPage(QWizardPage):
    """
    Step 0: Check dependencies and offer installation.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Character Animator Puppet Creator")
        self.setSubTitle("Check AI component installation status")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Status display
        self.status_group = QGroupBox("Installation Status")
        status_layout = QVBoxLayout(self.status_group)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)

        # Component checklist
        self.component_frame = QFrame()
        component_layout = QVBoxLayout(self.component_frame)
        self.component_labels = {}

        components = [
            ("segmentation", "SAM 2 Segmentation"),
            ("pose_detection", "MediaPipe Pose/Face"),
            ("ai_editing", "Cloud AI Editing (Gemini/OpenAI)"),
            ("psd_export", "PSD Export"),
            ("svg_export", "SVG Export"),
        ]

        for key, name in components:
            lbl = QLabel(f"  [ ] {name}")
            lbl.setStyleSheet("font-family: monospace;")
            component_layout.addWidget(lbl)
            self.component_labels[key] = lbl

        status_layout.addWidget(self.component_frame)
        layout.addWidget(self.status_group)

        # Install button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.install_btn = QPushButton("Install AI Components")
        self.install_btn.clicked.connect(self.on_install_clicked)
        button_layout.addWidget(self.install_btn)

        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.clicked.connect(self.refresh_status)
        button_layout.addWidget(self.refresh_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Capability info
        self.capability_label = QLabel()
        self.capability_label.setWordWrap(True)
        self.capability_label.setStyleSheet("margin-top: 10px;")
        layout.addWidget(self.capability_label)

        layout.addStretch()

    def initializePage(self):
        """Called when page is shown."""
        self.refresh_status()

    def refresh_status(self):
        """Refresh dependency status."""
        status = check_all_dependencies()

        # Update component labels
        for key, label in self.component_labels.items():
            name = label.text().split("] ")[1]
            if status.get(key, False):
                label.setText(f"  [x] {name}")
                label.setStyleSheet("font-family: monospace; color: #00cc00;")
            else:
                label.setText(f"  [ ] {name}")
                label.setStyleSheet("font-family: monospace; color: #ff6666;")

        # Update status message
        self.status_label.setText(get_install_status_message())

        # Update capability
        can_proceed, reason = can_create_puppet()
        if can_proceed:
            self.capability_label.setText(f"Ready to create puppets. {reason}")
            self.capability_label.setStyleSheet("color: #00cc00;")
        else:
            self.capability_label.setText(f"Cannot create puppets: {reason}")
            self.capability_label.setStyleSheet("color: #ff6666;")

        # Update install button
        if is_full_installation():
            self.install_btn.setEnabled(False)
            self.install_btn.setText("All Components Installed")
        else:
            self.install_btn.setEnabled(True)
            self.install_btn.setText("Install AI Components")

        # Update complete status
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        """Check if we can proceed to next page."""
        can_proceed, _ = can_create_puppet()
        return can_proceed

    def on_install_clicked(self):
        """Handle install button click."""
        # Show confirmation dialog
        confirm = PuppetInstallConfirmDialog(self)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        # Show progress dialog
        progress = PuppetInstallProgressDialog(self)
        progress.installation_complete.connect(self.on_installation_complete)
        progress.start_installation()
        progress.exec()

    def on_installation_complete(self, success: bool, message: str):
        """Handle installation completion."""
        self.refresh_status()


class ImageSelectionPage(QWizardPage):
    """
    Step 1: Select source image and preview.
    """

    image_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Select Source Image")
        self.setSubTitle("Choose an image to convert into a Character Animator puppet")
        self.image_path: Optional[str] = None
        self.settings = QSettings("ImageAI", "CharacterAnimator")
        self.init_ui()

        # Load last used image path
        last_path = self.settings.value("last_image_path", "")
        if last_path and Path(last_path).exists():
            self.path_edit.setText(last_path)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # File selection
        file_layout = QHBoxLayout()

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select an image file...")
        self.path_edit.textChanged.connect(self.on_path_changed)
        file_layout.addWidget(self.path_edit, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_image)
        file_layout.addWidget(browse_btn)

        layout.addLayout(file_layout)

        # Preview area
        preview_group = QGroupBox("Image Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("No image selected")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet(
            "background-color: #2a2a2a; border: 1px solid #555;"
        )
        preview_layout.addWidget(self.preview_label)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #888;")
        preview_layout.addWidget(self.info_label)

        layout.addWidget(preview_group, 1)

        # Requirements info
        req_label = QLabel("""
<b>Image Requirements:</b>
- Front-facing character (head and upper body visible)
- Clear facial features (eyes, mouth visible)
- Good lighting and contrast
- Recommended size: 1024x1024 or larger
        """)
        req_label.setWordWrap(True)
        req_label.setTextFormat(Qt.RichText)
        layout.addWidget(req_label)

        # Register field for wizard
        self.registerField("source_image*", self.path_edit)

    def browse_image(self):
        """Open file browser for image selection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Source Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
        )
        if file_path:
            self.path_edit.setText(file_path)

    def on_path_changed(self, path: str):
        """Handle path text change."""
        self.image_path = path if path else None
        self.update_preview()
        self.completeChanged.emit()

        # Save last used image path
        if self.image_path and Path(self.image_path).exists():
            self.settings.setValue("last_image_path", self.image_path)

    def update_preview(self):
        """Update the image preview."""
        if not self.image_path or not Path(self.image_path).exists():
            self.preview_label.setText("No image selected")
            self.preview_label.setPixmap(QPixmap())
            self.info_label.setText("")
            return

        try:
            # Load and display preview
            pixmap = QPixmap(self.image_path)
            if pixmap.isNull():
                self.preview_label.setText("Failed to load image")
                return

            # Scale to fit preview area
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)

            # Show info
            self.info_label.setText(
                f"Size: {pixmap.width()} x {pixmap.height()} pixels"
            )

        except Exception as e:
            logger.error(f"Failed to load preview: {e}")
            self.preview_label.setText(f"Error: {e}")

    def isComplete(self) -> bool:
        """Check if image is selected."""
        if not self.image_path:
            return False
        return Path(self.image_path).exists()


class SegmentationPage(QWizardPage):
    """
    Step 2: Body part detection preview with adjustment.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Body Part Detection")
        self.setSubTitle("Review detected body parts and facial features")
        self.segmentation_result = None
        self.detection_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left: Image with overlays
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.image_label = QLabel("Processing...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 400)
        left_layout.addWidget(self.image_label)

        splitter.addWidget(left_widget)

        # Right: Detection results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumWidth(250)
        right_layout.addWidget(self.results_text)

        # Refresh button
        refresh_btn = QPushButton("Re-detect")
        refresh_btn.clicked.connect(self.run_detection)
        right_layout.addWidget(refresh_btn)

        splitter.addWidget(right_widget)
        layout.addWidget(splitter, 1)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def initializePage(self):
        """Called when page is shown."""
        self.run_detection()

    def run_detection(self):
        """Run body part detection."""
        image_path = self.field("source_image")
        if not image_path:
            self.status_label.setText("No image selected")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Detecting body parts and facial features...")
        self.results_text.clear()

        # Run detection in thread
        self.detection_thread = DetectionThread(image_path)
        self.detection_thread.progress.connect(self.on_progress)
        self.detection_thread.finished.connect(self.on_detection_finished)
        self.detection_thread.start()

    def on_progress(self, message: str, percentage: int):
        """Handle progress updates."""
        self.status_label.setText(message)
        self.progress_bar.setValue(percentage)

    def on_detection_finished(self, success: bool, result):
        """Handle detection completion."""
        self.progress_bar.setVisible(False)

        if success and result:
            self.segmentation_result = result
            self.display_results()
            self.status_label.setText("Detection complete")
        else:
            self.status_label.setText("Detection failed - check if image has visible face")
            self.results_text.setText("Detection failed. Please ensure:\n"
                                     "- Face is clearly visible\n"
                                     "- Character is front-facing\n"
                                     "- Image has good lighting")

        self.completeChanged.emit()

    def display_results(self):
        """Display detection results."""
        if not self.segmentation_result:
            return

        result = self.segmentation_result

        # Show annotated image
        image_path = self.field("source_image")
        self.display_annotated_image(image_path, result)

        # Show text results
        text = "Detected Components:\n\n"

        # Body parts
        body_parts = result.get_body_parts()
        text += "Body Parts:\n"
        for name, (mask, bbox) in body_parts.items():
            if bbox:
                text += f"  [x] {name.replace('_', ' ').title()}: {bbox[2]}x{bbox[3]} px\n"
            else:
                text += f"  [ ] {name.replace('_', ' ').title()}: Not detected\n"

        # Facial regions
        text += "\nFacial Features:\n"
        facial = result.get_facial_regions()
        for name, region in facial.items():
            if region:
                text += f"  [x] {name.replace('_', ' ').title()}\n"
            else:
                text += f"  [ ] {name.replace('_', ' ').title()}: Not detected\n"

        # Depth info
        if result.depth_map is not None:
            text += "\n[x] Depth map available for z-ordering"
        else:
            text += "\n[ ] Depth map not available"

        self.results_text.setText(text)

    def display_annotated_image(self, image_path: str, result):
        """Display image with bounding box overlays."""
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                return

            # Draw bounding boxes
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            colors = {
                "head": QColor(0, 255, 0),
                "torso": QColor(0, 0, 255),
                "left_arm": QColor(255, 255, 0),
                "right_arm": QColor(255, 0, 255),
            }

            # Draw body part boxes
            body_parts = result.get_body_parts()
            for name, (mask, bbox) in body_parts.items():
                if bbox:
                    x, y, w, h = bbox
                    color = colors.get(name, QColor(255, 255, 255))
                    pen = QPen(color, 2)
                    painter.setPen(pen)
                    painter.drawRect(x, y, w, h)

                    # Label
                    painter.drawText(x + 5, y + 15, name.replace('_', ' ').title())

            # Draw facial feature points
            if result.mouth_region:
                bbox = result.mouth_region.bbox
                pen = QPen(QColor(255, 128, 0), 2)
                painter.setPen(pen)
                painter.drawRect(bbox[0], bbox[1], bbox[2], bbox[3])

            painter.end()

            # Scale and display
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

        except Exception as e:
            logger.error(f"Failed to display annotated image: {e}")

    def isComplete(self) -> bool:
        """Check if detection was successful."""
        return self.segmentation_result is not None


class VisemeGenerationPage(QWizardPage):
    """
    Step 3: Generate mouth visemes and eye blinks using cloud AI.
    """

    # Cost per image by model (estimated USD)
    MODEL_COSTS = {
        "gemini-2.5-flash-image": 0.039,
        "gemini-3-pro-image-preview": 0.10,
        "gpt-image-1": 0.08,
        "gpt-image-1.5": 0.12,
    }

    # Model display names
    MODEL_NAMES = {
        "gemini-2.5-flash-image": "Gemini 2.5 Flash Image (Fast, $0.039/img)",
        "gemini-3-pro-image-preview": "Gemini 3 Pro (Quality, $0.10/img)",
        "gpt-image-1": "GPT Image 1 (Standard, $0.08/img)",
        "gpt-image-1.5": "GPT Image 1.5 (Quality, $0.12/img)",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Generate Facial Variants")
        self.setSubTitle("Creating mouth shapes and eye blink states using Cloud AI")
        self.visemes: Optional[VisemeSet] = None
        self.blinks: Optional[EyeBlinkSet] = None
        self.generation_thread = None
        self.settings = QSettings("ImageAI", "CharacterAnimator")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # AI Provider/Model selection
        ai_group = QGroupBox("AI Provider & Model")
        ai_layout = QVBoxLayout(ai_group)

        # Provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Google (Gemini)", "OpenAI (GPT-Image)"])
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo, 1)
        ai_layout.addLayout(provider_layout)

        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self._update_cost_estimate)
        model_layout.addWidget(self.model_combo, 1)
        ai_layout.addLayout(model_layout)

        # Cost estimate
        self.cost_label = QLabel("Estimated cost: $0.00")
        self.cost_label.setStyleSheet("color: #88cc88; font-weight: bold;")
        ai_layout.addWidget(self.cost_label)

        # Time estimate
        self.time_label = QLabel("Estimated time: ~2-5 minutes")
        self.time_label.setStyleSheet("color: #8888cc;")
        ai_layout.addWidget(self.time_label)

        layout.addWidget(ai_group)

        # Options
        options_group = QGroupBox("Generation Options")
        options_layout = QVBoxLayout(options_group)

        self.generate_visemes_cb = QCheckBox("Generate 14 mouth visemes")
        self.generate_visemes_cb.setChecked(True)
        self.generate_visemes_cb.stateChanged.connect(self._update_cost_estimate)
        options_layout.addWidget(self.generate_visemes_cb)

        self.generate_blinks_cb = QCheckBox("Generate eye blink states (2 images)")
        self.generate_blinks_cb.setChecked(True)
        self.generate_blinks_cb.stateChanged.connect(self._update_cost_estimate)
        options_layout.addWidget(self.generate_blinks_cb)

        self.generate_eyebrows_cb = QCheckBox("Generate eyebrow variants (6 images, optional)")
        self.generate_eyebrows_cb.setChecked(False)
        self.generate_eyebrows_cb.stateChanged.connect(self._update_cost_estimate)
        options_layout.addWidget(self.generate_eyebrows_cb)

        # Separator
        options_layout.addSpacing(10)

        # Force regenerate option
        self.force_regenerate_cb = QCheckBox("Force regenerate (bypass cache)")
        self.force_regenerate_cb.setChecked(False)
        self.force_regenerate_cb.setToolTip(
            "If checked, will regenerate all variants even if cached versions exist.\n"
            "Useful when you want fresh AI-generated results."
        )
        options_layout.addWidget(self.force_regenerate_cb)

        layout.addWidget(options_group)

        # Initialize model list (must be after checkboxes are created)
        self._on_provider_changed(0)

        # Progress section
        progress_group = QGroupBox("Generation Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.current_task_label = QLabel("Ready to generate")
        progress_layout.addWidget(self.current_task_label)

        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(150)
        progress_layout.addWidget(self.output_text)

        layout.addWidget(progress_group, 1)

        # Start button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.start_btn = QPushButton("Start Generation")
        self.start_btn.clicked.connect(self.start_generation)
        button_layout.addWidget(self.start_btn)

        layout.addLayout(button_layout)

        # Status
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _on_provider_changed(self, index: int):
        """Handle provider selection change."""
        self.model_combo.clear()

        if index == 0:  # Google
            self.model_combo.addItem(
                self.MODEL_NAMES["gemini-2.5-flash-image"],
                "gemini-2.5-flash-image"
            )
            self.model_combo.addItem(
                self.MODEL_NAMES["gemini-3-pro-image-preview"],
                "gemini-3-pro-image-preview"
            )
        else:  # OpenAI
            self.model_combo.addItem(
                self.MODEL_NAMES["gpt-image-1"],
                "gpt-image-1"
            )
            self.model_combo.addItem(
                self.MODEL_NAMES["gpt-image-1.5"],
                "gpt-image-1.5"
            )

        self._update_cost_estimate()

    def _update_cost_estimate(self):
        """Update the cost and time estimates based on current selection."""
        model_id = self.model_combo.currentData()
        if not model_id:
            return

        cost_per_image = self.MODEL_COSTS.get(model_id, 0.05)

        # Calculate total images
        total_images = 0
        if self.generate_visemes_cb.isChecked():
            total_images += 14
        if self.generate_blinks_cb.isChecked():
            total_images += 2
        if self.generate_eyebrows_cb.isChecked():
            total_images += 6

        total_cost = total_images * cost_per_image

        # Update labels
        self.cost_label.setText(f"Estimated cost: ${total_cost:.2f} ({total_images} images × ${cost_per_image:.3f})")

        # Time estimate: ~3-5 seconds per image for Gemini, ~5-8 for OpenAI
        if "gemini" in model_id:
            time_per_image = 4  # seconds
        else:
            time_per_image = 6

        total_seconds = total_images * time_per_image
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        if minutes > 0:
            self.time_label.setText(f"Estimated time: ~{minutes} min {seconds} sec")
        else:
            self.time_label.setText(f"Estimated time: ~{seconds} seconds")

    def _get_selected_provider(self) -> str:
        """Get the selected provider name."""
        return "google" if self.provider_combo.currentIndex() == 0 else "openai"

    def _get_selected_model(self) -> str:
        """Get the selected model ID."""
        return self.model_combo.currentData() or "gemini-2.5-flash-image"

    def initializePage(self):
        """Called when page is shown."""
        self.visemes = None
        self.blinks = None
        self.progress_bar.setValue(0)
        self.output_text.clear()

        # Load saved preferences
        saved_provider = self.settings.value("generation_provider", 0, type=int)
        self.provider_combo.setCurrentIndex(saved_provider)

        self._update_cost_estimate()
        self.completeChanged.emit()

    def start_generation(self):
        """Start viseme and blink generation using cloud AI."""
        wizard = self.wizard()
        seg_page = wizard.page(2)  # SegmentationPage

        if not seg_page.segmentation_result:
            self.status_label.setText("Error: No segmentation data")
            return

        # Get provider and model
        provider = self._get_selected_provider()
        model = self._get_selected_model()

        # Save preferences
        self.settings.setValue("generation_provider", self.provider_combo.currentIndex())

        self.start_btn.setEnabled(False)
        self.provider_combo.setEnabled(False)
        self.model_combo.setEnabled(False)

        self.output_text.append(f"Starting cloud AI generation...")
        self.output_text.append(f"Provider: {provider.upper()}, Model: {model}")
        self.output_text.append("")

        # Get options
        gen_visemes = self.generate_visemes_cb.isChecked()
        gen_blinks = self.generate_blinks_cb.isChecked()
        gen_eyebrows = self.generate_eyebrows_cb.isChecked()
        force_regenerate = self.force_regenerate_cb.isChecked()

        # Start generation thread
        image_path = self.field("source_image")
        self.generation_thread = GenerationThread(
            image_path,
            seg_page.segmentation_result,
            gen_visemes,
            gen_blinks,
            provider=provider,
            model=model,
            gen_eyebrows=gen_eyebrows,
            use_cache=not force_regenerate,
        )
        self.generation_thread.progress.connect(self.on_progress)
        self.generation_thread.viseme_complete.connect(self.on_viseme_complete)
        self.generation_thread.finished.connect(self.on_generation_finished)
        self.generation_thread.error.connect(self.on_generation_error)
        self.generation_thread.start()

    def on_progress(self, message: str, percentage: int):
        """Handle progress updates."""
        self.current_task_label.setText(message)
        self.progress_bar.setValue(percentage)
        self.output_text.append(message)

    def on_viseme_complete(self, viseme_name: str):
        """Handle individual viseme completion."""
        self.output_text.append(f"  Generated: {viseme_name}")

    def on_generation_finished(self, success: bool, visemes, blinks):
        """Handle generation completion."""
        self.start_btn.setEnabled(True)
        self.provider_combo.setEnabled(True)
        self.model_combo.setEnabled(True)

        if success:
            self.visemes = visemes
            self.blinks = blinks
            self.status_label.setText("Generation complete!")
            self.status_label.setStyleSheet("color: #00cc00;")
            self.output_text.append("\n✓ All variants generated successfully!")
        else:
            self.status_label.setText("Generation partially completed")
            self.status_label.setStyleSheet("color: #ffcc00;")
            self.output_text.append("\n⚠ Warning: Some variants may not have generated correctly")

        self.completeChanged.emit()

    def on_generation_error(self, error_type: str, error_msg: str):
        """Handle generation errors (API issues, rate limits, etc.)."""
        self.output_text.append(f"\n❌ Error: {error_type}")
        self.output_text.append(f"   {error_msg}")

        if "rate limit" in error_msg.lower():
            self.output_text.append("   → Waiting 30 seconds before retry...")
        elif "api key" in error_msg.lower():
            self.output_text.append(f"   → Please check your {self._get_selected_provider().upper()} API key in Settings")
            self.status_label.setText(f"Missing or invalid API key for {self._get_selected_provider().upper()}")
            self.status_label.setStyleSheet("color: #ff6666;")
        elif "quota" in error_msg.lower():
            self.output_text.append("   → API quota exceeded. Try again later or switch provider.")
            # Offer to switch provider
            other_provider = "OpenAI" if self._get_selected_provider() == "google" else "Google"
            self.output_text.append(f"   → Consider switching to {other_provider}")

    def isComplete(self) -> bool:
        """Check if generation is complete."""
        # Allow proceeding even without full generation (manual override)
        return self.visemes is not None or not self.generate_visemes_cb.isChecked()


class ExportPage(QWizardPage):
    """
    Step 4: Export format selection and save.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Export Puppet")
        self.setSubTitle("Choose export format and save location")
        self.settings = QSettings("ImageAI", "CharacterAnimator")
        self.init_ui()
        self._load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Puppet name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Puppet Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("MyCharacter")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Export format
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout(format_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "PSD (Photoshop) - Best for photorealistic",
            "SVG (Vector) - Best for cartoons",
            "Both formats",
        ])
        format_layout.addWidget(self.format_combo)

        format_info = QLabel(
            "PSD format works best with detailed images.\n"
            "SVG format works best with flat/cartoon styles."
        )
        format_info.setStyleSheet("color: #888;")
        format_layout.addWidget(format_info)

        layout.addWidget(format_group)

        # Output location
        output_group = QGroupBox("Output Location")
        output_layout = QHBoxLayout(output_group)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Select output folder...")
        output_layout.addWidget(self.output_edit, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Export button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.export_btn = QPushButton("Export Puppet")
        self.export_btn.clicked.connect(self.export_puppet)
        button_layout.addWidget(self.export_btn)

        layout.addLayout(button_layout)

        # Status
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Auto-export hint
        hint_label = QLabel(
            "💡 Tip: Clicking 'Finish' will automatically export if you haven't yet."
        )
        hint_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(hint_label)

        layout.addStretch()

        # Register fields
        self.registerField("puppet_name", self.name_edit)
        self.registerField("output_path", self.output_edit)

        # Connect to save settings on change
        self.name_edit.textChanged.connect(self._save_settings)
        self.format_combo.currentIndexChanged.connect(self._save_settings)
        self.output_edit.textChanged.connect(self._save_settings)

    def _load_settings(self):
        """Load saved export settings."""
        # Load puppet name
        saved_name = self.settings.value("export_puppet_name", "")
        if saved_name:
            self.name_edit.setText(saved_name)

        # Load export format (0=PSD, 1=SVG, 2=Both)
        saved_format = self.settings.value("export_format", 0, type=int)
        if 0 <= saved_format <= 2:
            self.format_combo.setCurrentIndex(saved_format)

        # Load output path (default to user data dir if no saved path)
        saved_output = self.settings.value("export_output_path", "")
        if saved_output and Path(saved_output).exists():
            self.output_edit.setText(saved_output)
        else:
            # Default to Characters subdirectory in user data folder
            default_output = get_user_data_dir() / "Characters"
            default_output.mkdir(parents=True, exist_ok=True)
            self.output_edit.setText(str(default_output))

    def _save_settings(self):
        """Save current export settings."""
        self.settings.setValue("export_puppet_name", self.name_edit.text())
        self.settings.setValue("export_format", self.format_combo.currentIndex())
        self.settings.setValue("export_output_path", self.output_edit.text())

    def browse_output(self):
        """Select output folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder"
        )
        if folder:
            self.output_edit.setText(folder)

    def export_puppet(self):
        """Export the puppet."""
        logger.info("=== EXPORT PUPPET STARTED ===")

        # Validate inputs
        name = self.name_edit.text().strip()
        if not name:
            name = "MyCharacter"
        logger.info(f"Puppet name: {name}")

        output_dir = self.output_edit.text()
        if not output_dir:
            QMessageBox.warning(self, "Missing Output", "Please select an output folder")
            return
        logger.info(f"Output directory: {output_dir}")

        # Get format
        format_idx = self.format_combo.currentIndex()
        export_psd = format_idx in [0, 2]
        export_svg = format_idx in [1, 2]
        logger.info(f"Export formats - PSD: {export_psd}, SVG: {export_svg}")

        # Get data from previous pages
        wizard = self.wizard()
        seg_page = wizard.page(2)
        gen_page = wizard.page(3)

        logger.info(f"gen_page.visemes: {gen_page.visemes is not None}")
        logger.info(f"gen_page.blinks: {gen_page.blinks is not None}")
        if gen_page.visemes:
            viseme_dict = gen_page.visemes.to_dict()
            non_none = sum(1 for v in viseme_dict.values() if v is not None)
            logger.info(f"Visemes with images: {non_none}/{len(viseme_dict)}")

        self.status_label.setText("Exporting puppet...")
        self.export_btn.setEnabled(False)

        try:
            # Create puppet structure
            image_path = self.field("source_image")
            logger.info(f"Source image: {image_path}")
            image = Image.open(image_path)
            logger.info(f"Image size: {image.width}x{image.height}")

            puppet = PuppetStructure.create_empty(
                name=name,
                width=image.width,
                height=image.height,
            )

            # Add visemes if generated
            if gen_page.visemes:
                puppet.visemes = gen_page.visemes

            if gen_page.blinks:
                puppet.eye_blinks = gen_page.blinks

            # Populate puppet structure ONCE (shared by both exporters)
            # Import both exporters - they share common populate interface
            from core.character_animator.psd_exporter import PSDExporter
            from core.character_animator.svg_exporter import SVGExporter

            # Use PSD exporter to populate (could use either, they modify same puppet)
            temp_exporter = PSDExporter(puppet)
            if gen_page.visemes:
                logger.info("Populating visemes into puppet structure...")
                temp_exporter.populate_from_visemes(gen_page.visemes)
            if gen_page.blinks:
                logger.info("Populating blinks into puppet structure...")
                temp_exporter.populate_from_blinks(gen_page.blinks)

            # Export
            output_path = Path(output_dir)
            success_messages = []

            if export_psd:
                logger.info("Starting PSD export...")
                exporter = PSDExporter(puppet)
                psd_path = output_path / f"{name}.psd"
                logger.info(f"Exporting PSD to: {psd_path}")
                if exporter.export(psd_path):
                    logger.info("PSD export successful!")
                    success_messages.append(f"PSD: {psd_path}")
                else:
                    logger.error("PSD export returned False")

            if export_svg:
                logger.info("Starting SVG export...")
                svg_exporter = SVGExporter(puppet)
                svg_path = output_path / f"{name}.svg"
                logger.info(f"Exporting SVG to: {svg_path}")
                if svg_exporter.export(svg_path):
                    logger.info("SVG export successful!")
                    success_messages.append(f"SVG: {svg_path}")
                else:
                    logger.error("SVG export returned False")

            if success_messages:
                self.status_label.setText("Export successful!\n" + "\n".join(success_messages))
                self.status_label.setStyleSheet("color: #00cc00;")
                logger.info(f"Export completed: {success_messages}")
                # Mark as exported so wizard won't warn on close
                self.wizard()._exported = True
            else:
                self.status_label.setText("Export failed - no files created")
                self.status_label.setStyleSheet("color: #ff6666;")
                logger.error("Export failed - no success messages")

        except Exception as e:
            import traceback
            logger.error(f"Export failed with exception: {e}")
            logger.error(traceback.format_exc())
            self.status_label.setText(f"Export failed: {e}")
            self.status_label.setStyleSheet("color: #ff6666;")

        finally:
            self.export_btn.setEnabled(True)
            logger.info("=== EXPORT PUPPET FINISHED ===")


class DetectionThread(QThread):
    """Thread for running body part detection."""

    progress = Signal(str, int)
    finished = Signal(bool, object)

    def __init__(self, image_path: str):
        super().__init__()
        self.image_path = image_path

    def run(self):
        try:
            from core.character_animator.segmenter import BodyPartSegmenter

            self.progress.emit("Initializing segmenter...", 10)

            segmenter = BodyPartSegmenter()
            if not segmenter.initialize():
                self.finished.emit(False, None)
                return

            self.progress.emit("Loading image...", 20)
            image = Image.open(self.image_path)

            self.progress.emit("Detecting pose...", 40)
            self.progress.emit("Detecting face mesh...", 60)
            self.progress.emit("Estimating depth...", 80)

            result = segmenter.segment_body_parts(image)

            self.progress.emit("Detection complete", 100)
            segmenter.cleanup()

            self.finished.emit(True, result)

        except Exception as e:
            logger.error(f"Detection failed: {e}")
            self.finished.emit(False, None)


class GenerationThread(QThread):
    """Thread for generating facial variants using cloud AI."""

    progress = Signal(str, int)
    viseme_complete = Signal(str)
    error = Signal(str, str)  # error_type, error_message
    finished = Signal(bool, object, object)

    def __init__(
        self,
        image_path: str,
        segmentation,
        gen_visemes: bool,
        gen_blinks: bool,
        provider: str = "google",
        model: str = "gemini-2.5-flash-image",
        gen_eyebrows: bool = False,
        use_cache: bool = True,
    ):
        super().__init__()
        self.image_path = image_path
        self.segmentation = segmentation
        self.gen_visemes = gen_visemes
        self.gen_blinks = gen_blinks
        self.provider = provider
        self.model = model
        self.gen_eyebrows = gen_eyebrows
        self.use_cache = use_cache

    def run(self):
        try:
            from core.character_animator.face_generator import FaceVariantGenerator

            self.progress.emit("Initializing cloud AI generator...", 5)
            self.progress.emit(f"Using {self.provider.upper()} / {self.model}", 5)

            generator = FaceVariantGenerator(
                provider=self.provider,
                model=self.model,
            )

            if not generator.initialize():
                self.error.emit("Initialization Failed", f"Could not initialize {self.provider.upper()} API. Check your API key.")
                self.finished.emit(False, None, None)
                return

            image = Image.open(self.image_path)
            visemes = None
            blinks = None

            if self.gen_visemes:
                cache_msg = " (cache enabled)" if self.use_cache else " (FORCE REGENERATE)"
                self.progress.emit(f"Generating 14 mouth visemes via cloud AI...{cache_msg}", 10)

                def on_viseme_progress(name, idx, total):
                    pct = 10 + int((idx / total) * 70)
                    self.progress.emit(f"Viseme {idx+1}/{total}: {name}", pct)
                    self.viseme_complete.emit(name)

                try:
                    visemes = generator.generate_all_visemes(
                        image, self.segmentation, on_viseme_progress,
                        use_cache=self.use_cache,
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "rate" in error_msg.lower() or "429" in error_msg:
                        self.error.emit("Rate Limit", error_msg)
                    elif "key" in error_msg.lower() or "auth" in error_msg.lower():
                        self.error.emit("API Key Error", error_msg)
                    elif "quota" in error_msg.lower():
                        self.error.emit("Quota Exceeded", error_msg)
                    else:
                        self.error.emit("Generation Error", error_msg)
                    raise

            if self.gen_blinks:
                self.progress.emit("Generating eye blink states...", 85)
                try:
                    blinks = generator.generate_blink_states(
                        image, self.segmentation,
                        use_cache=self.use_cache,
                    )
                except Exception as e:
                    self.error.emit("Blink Generation Error", str(e))
                    # Continue with partial results

            if self.gen_eyebrows:
                self.progress.emit("Generating eyebrow variants...", 92)
                try:
                    # Eyebrow generation (optional feature)
                    generator.generate_eyebrow_variants(
                        image, self.segmentation,
                        use_cache=self.use_cache,
                    )
                except Exception as e:
                    self.error.emit("Eyebrow Generation Error", str(e))
                    # Continue with partial results

            self.progress.emit("Cloud AI generation complete!", 100)
            generator.cleanup()

            self.finished.emit(True, visemes, blinks)

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.finished.emit(False, None, None)


class PuppetWizard(QWizard):
    """
    Multi-step wizard for creating Character Animator puppets.
    """

    # Page IDs
    PAGE_DEPENDENCY = 0
    PAGE_IMAGE = 1
    PAGE_SEGMENTATION = 2
    PAGE_VISEME = 3
    PAGE_EXPORT = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Character Animator Puppet Creator")
        self.setMinimumSize(700, 600)

        # Track export status
        self._exported = False

        # Check if fully installed to skip dependency page
        self._fully_installed = is_full_installation()

        # Add pages
        self.setPage(self.PAGE_DEPENDENCY, DependencyCheckPage(self))
        self.setPage(self.PAGE_IMAGE, ImageSelectionPage(self))
        self.setPage(self.PAGE_SEGMENTATION, SegmentationPage(self))
        self.setPage(self.PAGE_VISEME, VisemeGenerationPage(self))
        self.setPage(self.PAGE_EXPORT, ExportPage(self))

        # Skip dependency page if fully installed
        if self._fully_installed:
            self.setStartId(self.PAGE_IMAGE)
            logger.info("All dependencies installed - skipping installation page")

        # Set button text
        self.setButtonText(QWizard.NextButton, "Next >")
        self.setButtonText(QWizard.BackButton, "< Back")
        self.setButtonText(QWizard.FinishButton, "Export && Finish")
        self.setButtonText(QWizard.CancelButton, "Cancel")

        # Options
        self.setOption(QWizard.NoBackButtonOnStartPage, True)

    def has_unsaved_generation(self) -> bool:
        """Check if there's generated content that hasn't been exported."""
        if self._exported:
            return False

        # Check if visemes or blinks were generated
        viseme_page = self.page(self.PAGE_VISEME)
        if viseme_page and (viseme_page.visemes is not None or viseme_page.blinks is not None):
            return True

        return False

    def accept(self):
        """Override accept to auto-export when Finish is clicked."""
        if self.has_unsaved_generation():
            # Auto-trigger export
            export_page = self.page(self.PAGE_EXPORT)
            if export_page:
                # Check if output directory is set
                output_dir = export_page.output_edit.text()
                if not output_dir:
                    QMessageBox.warning(
                        self,
                        "Export Required",
                        "Please select an output folder and click 'Export Puppet' "
                        "before finishing, or the generated content will be lost.",
                        QMessageBox.StandardButton.Ok,
                    )
                    return  # Don't close, let user set output

                # Trigger export
                logger.info("Auto-triggering export on Finish")
                export_page.export_puppet()

                # Check if export succeeded
                if not self._exported:
                    reply = QMessageBox.warning(
                        self,
                        "Export Failed",
                        "Export may have failed. Do you want to close anyway?\n\n"
                        "If you close now, you'll need to regenerate the content.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return  # Don't close

        super().accept()

    def reject(self):
        """Override reject to warn about unsaved generation."""
        if self.has_unsaved_generation():
            reply = QMessageBox.warning(
                self,
                "Unsaved Puppet",
                "You have generated visemes and/or eye blinks that haven't been exported.\n\n"
                "If you close now, you'll need to regenerate them.\n\n"
                "Do you want to close without exporting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return  # Don't close

        super().reject()

    def showEvent(self, event):
        """Handle show event - update Discord presence."""
        super().showEvent(event)
        logger.info("Puppet Wizard showEvent - updating Discord presence to CHARACTER_GENERATOR")
        discord_rpc.update_presence(
            ActivityState.CHARACTER_GENERATOR,
            details="Puppet Wizard"
        )

    def closeEvent(self, event):
        """Handle window close button."""
        # Reset Discord presence to IDLE
        discord_rpc.update_presence(ActivityState.IDLE)

        if self.has_unsaved_generation():
            reply = QMessageBox.warning(
                self,
                "Unsaved Puppet",
                "You have generated visemes and/or eye blinks that haven't been exported.\n\n"
                "If you close now, you'll need to regenerate them.\n\n"
                "Do you want to close without exporting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        event.accept()


def launch_puppet_wizard(parent=None) -> Optional[PuppetWizard]:
    """
    Launch the puppet creation wizard.

    Args:
        parent: Parent widget

    Returns:
        PuppetWizard instance if accepted, None otherwise
    """
    wizard = PuppetWizard(parent)
    if wizard.exec() == QWizard.DialogCode.Accepted:
        return wizard
    return None
