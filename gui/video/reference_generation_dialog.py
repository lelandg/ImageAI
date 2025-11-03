"""
Reference Generation Wizard Dialog.
Generates character reference images (3 angles) for video project consistency.
Standalone dialog with its own provider/model selection and settings persistence.
"""

import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QProgressBar, QGroupBox, QComboBox, QSpinBox,
    QGridLayout, QScrollArea, QWidget, QFrame, QSplitter, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap

from core.video.project import ReferenceImage, VideoProject
from core.video.reference_manager import ReferenceImageType, ReferenceImageValidator
from core.config import ConfigManager
from providers import list_providers

logger = logging.getLogger(__name__)


class ReferenceGenerationWorker(QThread):
    """Worker thread for generating reference images - matches GenWorker pattern"""

    progress = Signal(int, str)  # progress_percent, status_message
    reference_generated = Signal(int, str)  # index (1-3), file_path
    generation_complete = Signal(bool, str)  # success, message

    def __init__(self,
                 description: str,
                 style: str,
                 output_dir: Path,
                 provider_name: str,
                 model: str,
                 auth_mode: str = "api-key",
                 aspect_ratio: str = "1:1",
                 reference_image: Optional[Path] = None):
        super().__init__()
        self.description = description
        self.style = style
        self.output_dir = output_dir
        self.provider_name = provider_name
        self.model = model
        self.auth_mode = auth_mode
        self.aspect_ratio = aspect_ratio
        self.reference_image = reference_image
        self.generated_paths = []

    def run(self):
        """Generate 3 reference images - matches GenWorker pattern"""
        try:
            self.progress.emit(0, "Starting reference generation...")

            # Get configuration and instantiate provider (like GenWorker does)
            from core.config import ConfigManager
            from providers import get_provider

            config = ConfigManager()
            api_key = config.get_api_key(self.provider_name) if self.auth_mode == "api-key" else None

            # Create provider config
            provider_config = {
                "api_key": api_key,
                "auth_mode": self.auth_mode,
            }

            # Instantiate the provider
            provider = get_provider(self.provider_name, provider_config)

            if not provider:
                self.generation_complete.emit(False, f"Failed to initialize provider: {self.provider_name}")
                return

            logger.info(f"✓ Initialized provider: {self.provider_name} (auth_mode: {self.auth_mode})")

            # Create prompts for 3 angles
            prompts = [
                f"{self.description}, front view portrait, neutral background, {self.style}",
                f"{self.description}, 3/4 side view, neutral background, {self.style}",
                f"{self.description}, full body standing, neutral background, {self.style}"
            ]

            angle_names = ["front", "side", "fullbody"]

            for i, (prompt, angle) in enumerate(zip(prompts, angle_names), 1):
                self.progress.emit(int((i-1)/3 * 100), f"Generating reference {i}/3 ({angle} view)...")

                try:
                    # Generate image using provider directly
                    logger.info(f"Generating reference {i}/3: {prompt[:80]}...")

                    # Prepare generation kwargs (matching GenWorker pattern)
                    # NOTE: model is passed separately as a parameter to generate(), not in kwargs
                    gen_kwargs = {
                        "aspect_ratio": self.aspect_ratio,
                    }

                    # Add reference image if provided
                    if self.reference_image and self.reference_image.exists():
                        from PIL import Image
                        ref_img = Image.open(self.reference_image)
                        gen_kwargs["reference_image"] = ref_img
                        logger.info(f"Using reference image: {self.reference_image.name}")

                    # Generate the image using provider.generate() with proper parameter signature
                    # generate(prompt, model, **kwargs) - model is separate from kwargs
                    texts, images = provider.generate(
                        prompt=prompt,
                        model=self.model,
                        **gen_kwargs
                    )

                    # Save the first image (providers typically return 1 image)
                    if images and len(images) > 0:
                        # Create output path with timestamp and index to avoid collisions
                        timestamp = int(time.time())
                        filename = f"char_ref_{angle}_{timestamp}_{i}.png"
                        output_path = self.output_dir / filename

                        # Save image bytes to file
                        with open(output_path, 'wb') as f:
                            f.write(images[0])

                        if output_path.exists():
                            # Validate
                            validator = ReferenceImageValidator()
                            info = validator.validate_reference_image(output_path)

                            if info.is_valid:
                                self.generated_paths.append(output_path)
                                self.reference_generated.emit(i, str(output_path))
                                logger.info(f"✓ Generated reference {i}/3: {output_path.name}")
                            else:
                                error_msg = "; ".join(info.validation_errors)
                                logger.warning(f"✗ Reference {i}/3 failed validation: {error_msg}")
                                self.progress.emit(int(i/3 * 100), f"⚠️ Reference {i} validation failed: {error_msg}")
                        else:
                            logger.error(f"✗ Failed to save image to: {output_path}")
                            self.progress.emit(int(i/3 * 100), f"⚠️ Reference {i} save failed")
                    else:
                        logger.error(f"✗ No image data returned for reference {i}/3")
                        self.progress.emit(int(i/3 * 100), f"⚠️ Reference {i} generation failed - no data")

                except Exception as e:
                    logger.error(f"Error generating reference {i}/3: {e}", exc_info=True)
                    self.progress.emit(int(i/3 * 100), f"⚠️ Error on reference {i}: {str(e)}")

            # Complete
            success = len(self.generated_paths) > 0
            if success:
                self.progress.emit(100, f"✓ Generated {len(self.generated_paths)}/3 references successfully")
                self.generation_complete.emit(True, f"Generated {len(self.generated_paths)}/3 reference images")
            else:
                self.progress.emit(100, "✗ All reference generations failed")
                self.generation_complete.emit(False, "Failed to generate any reference images")

        except Exception as e:
            logger.error(f"Reference generation failed: {e}", exc_info=True)
            self.generation_complete.emit(False, f"Generation failed: {str(e)}")


class ReferenceGenerationDialog(QDialog):
    """
    Standalone dialog for generating character reference images.
    Has its own provider/model selection and settings persistence.
    """

    references_generated = Signal(list)  # List[Path] of generated reference paths

    def __init__(self, parent=None, project: Optional[VideoProject] = None,
                 config: Optional[ConfigManager] = None, providers: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.project = project
        self.config = config
        self.providers = providers or {}
        self.generated_paths = []
        self.worker = None

        self.setWindowTitle("Generate Character References")
        self.setModal(True)
        self.resize(800, 900)

        # Load saved settings
        self.load_settings()

        self.setup_ui()

    def load_settings(self):
        """Load saved settings from config"""
        if self.config:
            self.saved_provider = self.config.get('char_ref_provider', 'google')
            self.saved_model = self.config.get('char_ref_model', 'gemini-2.5-flash-image')
            self.saved_style = self.config.get('char_ref_style', 'cinematic lighting, high detail, photorealistic')
            self.saved_quality = self.config.get('char_ref_quality', 'high')
            self.saved_description = self.config.get('char_ref_description', '')
            self.saved_reference_image = self.config.get('char_ref_reference_image', '')
        else:
            self.saved_provider = 'google'
            self.saved_model = 'gemini-2.5-flash-image'
            self.saved_style = 'cinematic lighting, high detail, photorealistic'
            self.saved_quality = 'high'
            self.saved_description = ''
            self.saved_reference_image = ''

    def save_settings(self):
        """Save current settings to config"""
        if self.config and hasattr(self, 'provider_combo'):
            self.config.set('char_ref_provider', self.provider_combo.currentText())
            self.config.set('char_ref_model', self.model_combo.currentText())
            self.config.set('char_ref_style', self.style_combo.currentText())
            self.config.set('char_ref_quality', self.quality_combo.currentText())

            # Save description text
            if hasattr(self, 'description_edit'):
                self.config.set('char_ref_description', self.description_edit.toPlainText().strip())

            # Save reference image path
            if hasattr(self, 'reference_image_path') and self.reference_image_path:
                self.config.set('char_ref_reference_image', str(self.reference_image_path))
            else:
                self.config.set('char_ref_reference_image', '')

            self.config.save()
            logger.info("Saved character reference dialog settings")

    def setup_ui(self):
        """Setup dialog UI"""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Generate 3 reference images for character consistency across scenes.\n"
            "The system will create front, side, and full-body views using your description."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # === PROVIDER/MODEL SELECTION ===
        provider_group = QGroupBox("Image Generation Settings")
        provider_layout = QGridLayout(provider_group)

        # Provider dropdown
        provider_layout.addWidget(QLabel("Provider:"), 0, 0)
        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(150)

        # Get available providers
        try:
            available_providers = list_providers()
            available_providers = [p for p in available_providers if p != "imagen_customization"]
        except Exception as e:
            logger.error(f"Failed to list providers: {e}")
            available_providers = ["google", "openai", "stability"]

        self.provider_combo.addItems(available_providers)

        # Set saved provider
        if self.saved_provider in available_providers:
            self.provider_combo.setCurrentText(self.saved_provider)

        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(self.provider_combo, 0, 1)

        # Model dropdown
        provider_layout.addWidget(QLabel("Model:"), 1, 0)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(300)
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        provider_layout.addWidget(self.model_combo, 1, 1)

        # Update model list based on initial provider
        self.on_provider_changed(self.provider_combo.currentText())

        layout.addWidget(provider_group)

        # Splitter for input and preview
        from gui.common.splitter_style import apply_splitter_style
        splitter = QSplitter(Qt.Vertical)
        apply_splitter_style(splitter)
        layout.addWidget(splitter, stretch=1)

        # === INPUT SECTION ===
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)

        # Character Description
        desc_group = QGroupBox("Character Description")
        desc_layout = QVBoxLayout(desc_group)

        desc_label = QLabel(
            "Describe the character (e.g., \"Sarah - young woman, 25, long dark hair, green eyes, blue jacket\"):"
        )
        desc_label.setWordWrap(True)
        desc_layout.addWidget(desc_label)

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Enter character description...")
        self.description_edit.setMaximumHeight(100)

        # Restore saved description
        if hasattr(self, 'saved_description') and self.saved_description:
            self.description_edit.setPlainText(self.saved_description)

        desc_layout.addWidget(self.description_edit)

        input_layout.addWidget(desc_group)

        # Style Settings
        style_group = QGroupBox("Style Settings")
        style_layout = QGridLayout(style_group)

        # Style preset
        style_layout.addWidget(QLabel("Visual Style:"), 0, 0)
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "cinematic lighting, high detail, photorealistic",
            "hi-res cartoon style, vibrant colors, clean lines",
            "anime style, detailed shading, expressive",
            "3D rendered, ray traced, volumetric lighting",
            "oil painting style, artistic, textured",
            "watercolor style, soft edges, artistic"
        ])
        self.style_combo.setEditable(True)
        self.style_combo.setCurrentText(self.saved_style)
        style_layout.addWidget(self.style_combo, 0, 1)

        # Quality
        style_layout.addWidget(QLabel("Quality:"), 1, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["high", "medium", "low"])
        self.quality_combo.setCurrentText(self.saved_quality)
        style_layout.addWidget(self.quality_combo, 1, 1)

        # Resolution hint
        style_layout.addWidget(QLabel("Target Resolution:"), 2, 0)
        resolution_label = QLabel("1024×1024 (recommended for references)")
        resolution_label.setStyleSheet("color: gray; font-style: italic;")
        style_layout.addWidget(resolution_label, 2, 1)

        input_layout.addWidget(style_group)

        # Reference image (optional - for generating views from existing image)
        ref_image_group = QGroupBox("Reference Image (Optional)")
        ref_image_layout = QVBoxLayout(ref_image_group)

        ref_help_label = QLabel(
            "Upload an optional reference image to guide the 3-view generation.\n"
            "The system will use this image as a reference to create front, side, and full-body views."
        )
        ref_help_label.setWordWrap(True)
        ref_help_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        ref_image_layout.addWidget(ref_help_label)

        ref_controls_layout = QHBoxLayout()
        self.ref_image_upload_btn = QPushButton("📁 Upload Reference Image")
        self.ref_image_upload_btn.clicked.connect(self.upload_reference_image)
        ref_controls_layout.addWidget(self.ref_image_upload_btn)

        self.ref_image_label = QLabel("No reference image")
        self.ref_image_label.setStyleSheet("color: #999; font-style: italic;")
        ref_controls_layout.addWidget(self.ref_image_label, 1)

        self.ref_image_clear_btn = QPushButton("✕")
        self.ref_image_clear_btn.setToolTip("Clear reference image")
        self.ref_image_clear_btn.setMaximumWidth(30)
        self.ref_image_clear_btn.setVisible(False)
        self.ref_image_clear_btn.clicked.connect(self.clear_reference_image)
        ref_controls_layout.addWidget(self.ref_image_clear_btn)

        ref_image_layout.addLayout(ref_controls_layout)
        input_layout.addWidget(ref_image_group)

        # Store reference image path - restore from saved settings
        self.reference_image_path = None
        if hasattr(self, 'saved_reference_image') and self.saved_reference_image:
            saved_path = Path(self.saved_reference_image)
            if saved_path.exists():
                self.reference_image_path = saved_path
                self.ref_image_label.setText(saved_path.name)
                self.ref_image_label.setStyleSheet("color: #00cc66; font-weight: bold;")
                self.ref_image_clear_btn.setVisible(True)
                logger.info(f"Restored reference image: {saved_path.name}")

        # Import from library button
        self.import_library_btn = QPushButton("📚 Import from Reference Library")
        self.import_library_btn.setStyleSheet("padding: 8px;")
        self.import_library_btn.setToolTip("Use existing references from the project library")
        self.import_library_btn.clicked.connect(self.import_from_library)
        input_layout.addWidget(self.import_library_btn)

        # Import from files button
        self.import_files_btn = QPushButton("📁 Import from Files")
        self.import_files_btn.setStyleSheet("padding: 8px;")
        self.import_files_btn.setToolTip("Select images from disk to use as references")
        self.import_files_btn.clicked.connect(self.import_from_files)
        input_layout.addWidget(self.import_files_btn)

        # OR separator
        or_label = QLabel("— OR —")
        or_label.setAlignment(Qt.AlignCenter)
        or_label.setStyleSheet("color: #999; font-style: italic; margin: 5px;")
        input_layout.addWidget(or_label)

        # Generate button
        self.generate_btn = QPushButton("🎨 Generate 3 Reference Images")
        self.generate_btn.setStyleSheet("font-weight: bold; padding: 10px;")
        self.generate_btn.clicked.connect(self.start_generation)
        input_layout.addWidget(self.generate_btn)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        input_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        input_layout.addWidget(self.status_label)

        splitter.addWidget(input_widget)

        # === PREVIEW SECTION ===
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)

        preview_label = QLabel("Generated References (Preview):")
        preview_label.setStyleSheet("font-weight: bold;")
        preview_layout.addWidget(preview_label)

        # Scroll area for previews
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)

        scroll_widget = QWidget()
        self.preview_layout = QGridLayout(scroll_widget)
        self.preview_layout.setSpacing(10)

        # Create 3 preview slots
        self.preview_frames = []
        self.preview_labels = []

        for i in range(3):
            frame = QFrame()
            frame.setFrameShape(QFrame.Box)
            frame.setMinimumSize(200, 250)
            frame.setMaximumWidth(250)

            frame_layout = QVBoxLayout(frame)

            # Title
            title = QLabel(["Front View", "Side View", "Full Body"][i])
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-weight: bold;")
            frame_layout.addWidget(title)

            # Image preview
            preview_label = QLabel("(Not generated)")
            preview_label.setAlignment(Qt.AlignCenter)
            preview_label.setMinimumSize(180, 180)
            preview_label.setStyleSheet("background: #f0f0f0; border: 1px dashed #ccc;")
            frame_layout.addWidget(preview_label)

            # Status
            status = QLabel("Pending")
            status.setAlignment(Qt.AlignCenter)
            status.setStyleSheet("color: gray; font-style: italic;")
            frame_layout.addWidget(status)

            self.preview_frames.append(frame)
            self.preview_labels.append((preview_label, status))
            self.preview_layout.addWidget(frame, 0, i)

        scroll.setWidget(scroll_widget)
        preview_layout.addWidget(scroll)

        splitter.addWidget(preview_widget)

        # Set splitter sizes
        splitter.setSizes([400, 500])

        # === BUTTONS ===
        button_layout = QHBoxLayout()

        self.add_to_project_btn = QPushButton("✓ Add to Project as Global References")
        self.add_to_project_btn.setEnabled(False)
        self.add_to_project_btn.setStyleSheet("font-weight: bold;")
        self.add_to_project_btn.clicked.connect(self.add_to_project)
        button_layout.addWidget(self.add_to_project_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def on_provider_changed(self, provider: str):
        """Handle provider change - update model list"""
        self.model_combo.clear()

        provider_lower = provider.lower()

        if provider_lower in ["google", "gemini"]:
            self.model_combo.addItems([
                "gemini-2.5-flash-image",
                "gemini-2.5-flash-image-preview",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ])
        elif provider_lower == "openai":
            self.model_combo.addItems([
                "dall-e-3",
                "dall-e-2"
            ])
        elif provider_lower == "stability":
            self.model_combo.addItems([
                "stable-diffusion-xl-1024-v1-0",
                "stable-diffusion-xl-1024-v0-9",
                "stable-diffusion-512-v2-1"
            ])
        else:
            # Generic fallback
            self.model_combo.addItems(["default"])

        # Try to restore saved model
        if hasattr(self, 'saved_model') and self.saved_model:
            index = self.model_combo.findText(self.saved_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)

    def upload_reference_image(self):
        """Upload a reference image to guide 3-view generation"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        if not file_path:
            return

        try:
            source_path = Path(file_path)

            # Store reference image path
            self.reference_image_path = source_path

            # Update label
            self.ref_image_label.setText(source_path.name)
            self.ref_image_label.setStyleSheet("color: #00cc66; font-weight: bold;")
            self.ref_image_clear_btn.setVisible(True)

            logger.info(f"Loaded reference image: {source_path.name}")

        except Exception as e:
            logger.error(f"Failed to load reference image: {e}")
            QMessageBox.warning(self, "Load Error", f"Failed to load reference image:\n{str(e)}")

    def clear_reference_image(self):
        """Clear the loaded reference image"""
        self.reference_image_path = None
        self.ref_image_label.setText("No reference image")
        self.ref_image_label.setStyleSheet("color: #999; font-style: italic;")
        self.ref_image_clear_btn.setVisible(False)
        logger.info("Cleared reference image")

    def import_from_library(self):
        """Import existing references from the project library"""
        if not self.project:
            QMessageBox.warning(self, "No Project", "No project is loaded.")
            return

        # Get global references from project
        global_refs = [ref for ref in self.project.global_reference_images if ref.is_global]

        if not global_refs:
            QMessageBox.information(
                self,
                "No References",
                "No global references found in the library.\n\nUse the Reference Library tab to add references first."
            )
            return

        # Show selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Select References from Library")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(dialog)

        info_label = QLabel("Select up to 3 references to use as character references:")
        layout.addWidget(info_label)

        # List widget with checkboxes
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.MultiSelection)

        for ref in global_refs:
            item_text = ref.name or ref.path.stem
            if ref.description:
                item_text += f" - {ref.description}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, ref)
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Use Selected")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        if dialog.exec() == QDialog.Accepted:
            selected_items = list_widget.selectedItems()
            if not selected_items:
                return

            if len(selected_items) > 3:
                QMessageBox.warning(
                    self,
                    "Too Many Selected",
                    f"You selected {len(selected_items)} references.\nPlease select no more than 3."
                )
                return

            # Copy selected references
            self.generated_paths = []
            for i, item in enumerate(selected_items[:3]):
                ref = item.data(Qt.UserRole)
                if ref.path.exists():
                    self.generated_paths.append(ref.path)

                    # Show preview
                    pixmap = QPixmap(str(ref.path))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.preview_labels[i][0].setPixmap(scaled)
                        self.preview_labels[i][1].setText("✓ Imported")
                        self.preview_labels[i][1].setStyleSheet("color: green; font-weight: bold;")

            self.status_label.setText(f"✓ Imported {len(self.generated_paths)} reference(s) from library")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")

            # Enable add to project button
            self.add_to_project_btn.setEnabled(True)

    def import_from_files(self):
        """Import references from disk files"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Reference Images (up to 3)",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        if not file_paths:
            return

        if len(file_paths) > 3:
            QMessageBox.warning(
                self,
                "Too Many Files",
                f"You selected {len(file_paths)} files.\nOnly the first 3 will be used."
            )
            file_paths = file_paths[:3]

        # Copy files to project references directory
        if self.project and self.project.project_dir:
            output_dir = self.project.project_dir / "references"
        else:
            output_dir = Path("references")

        output_dir.mkdir(parents=True, exist_ok=True)

        self.generated_paths = []
        import shutil

        for i, file_path in enumerate(file_paths):
            try:
                source_path = Path(file_path)
                dest_path = output_dir / f"imported_{i+1}_{source_path.name}"

                # Copy file
                shutil.copy2(source_path, dest_path)
                self.generated_paths.append(dest_path)

                # Show preview
                pixmap = QPixmap(str(dest_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.preview_labels[i][0].setPixmap(scaled)
                    self.preview_labels[i][1].setText("✓ Imported")
                    self.preview_labels[i][1].setStyleSheet("color: green; font-weight: bold;")

            except Exception as e:
                logger.error(f"Failed to import {file_path}: {e}")
                QMessageBox.warning(self, "Import Error", f"Failed to import {source_path.name}:\n{str(e)}")

        if self.generated_paths:
            self.status_label.setText(f"✓ Imported {len(self.generated_paths)} reference(s) from files")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.add_to_project_btn.setEnabled(True)

    def start_generation(self):
        """Start reference generation using selected provider/model - matches image tab pattern"""
        description = self.description_edit.toPlainText().strip()
        if not description:
            self.status_label.setText("⚠️ Please enter a character description")
            self.status_label.setStyleSheet("color: orange;")
            return

        # Get selected provider name
        provider_name = self.provider_combo.currentText().lower()
        provider_key = provider_name if provider_name != 'gemini' else 'google'

        # Get selected model
        model = self.model_combo.currentText()
        if not model:
            self.status_label.setText("⚠️ Please select a model")
            self.status_label.setStyleSheet("color: orange;")
            return

        # Determine auth mode (like main_window.py does for GenWorker)
        auth_mode = "api-key"  # default
        if provider_key == "google":
            # Check if using cloud auth - match main_window.py auth mode handling
            if self.config:
                auth_mode_value = self.config.get("auth_mode", "api-key")
                # Handle legacy/display values (same as main_window.py lines 293-297)
                if auth_mode_value in ["api_key", "API Key"]:
                    auth_mode = "api-key"
                elif auth_mode_value == "Google Cloud Account" or auth_mode_value == "gcloud":
                    auth_mode = "gcloud"
                    logger.info("Using Google Cloud authentication for reference generation")
                else:
                    auth_mode = auth_mode_value  # Use as-is if not a known value

        # Save settings for next time
        self.save_settings()

        # Show auth mode in status
        auth_info = f"Using {provider_key} provider"
        if provider_key == "google":
            auth_info += f" with {auth_mode} authentication"
        self.status_label.setText(f"Starting generation... ({auth_info})")
        self.status_label.setStyleSheet("color: blue; font-style: italic;")
        logger.info(f"Starting reference generation: {auth_info}")

        # Get style
        style = self.style_combo.currentText()

        # Create output directory
        output_dir = self.project.project_dir / "references" if self.project and self.project.project_dir else Path("references")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Disable controls
        self.generate_btn.setEnabled(False)
        self.description_edit.setEnabled(False)
        self.style_combo.setEnabled(False)
        self.quality_combo.setEnabled(False)
        self.provider_combo.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Reset previews
        self.generated_paths = []
        for preview_label, status_label in self.preview_labels:
            preview_label.setPixmap(QPixmap())
            preview_label.setText("(Generating...)")
            status_label.setText("Generating...")
            status_label.setStyleSheet("color: blue; font-style: italic;")

        # Start worker (pass provider_name and auth_mode like GenWorker)
        self.worker = ReferenceGenerationWorker(
            description=description,
            style=style,
            output_dir=output_dir,
            provider_name=provider_key,
            model=model,
            auth_mode=auth_mode,
            aspect_ratio="1:1",
            reference_image=self.reference_image_path
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.reference_generated.connect(self.on_reference_generated)
        self.worker.generation_complete.connect(self.on_generation_complete)
        self.worker.start()

    def on_progress(self, percent: int, message: str):
        """Handle progress update"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def on_reference_generated(self, index: int, file_path: str):
        """Handle single reference generation complete"""
        path = Path(file_path)
        self.generated_paths.append(path)

        # Update preview
        preview_label, status_label = self.preview_labels[index - 1]

        # Load and scale image
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            preview_label.setPixmap(scaled_pixmap)
            preview_label.setText("")
            status_label.setText("✓ Generated")
            status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            preview_label.setText("(Load failed)")
            status_label.setText("✗ Failed")
            status_label.setStyleSheet("color: red;")

    def on_generation_complete(self, success: bool, message: str):
        """Handle generation complete"""
        # Re-enable controls
        self.generate_btn.setEnabled(True)
        self.description_edit.setEnabled(True)
        self.style_combo.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self.provider_combo.setEnabled(True)
        self.model_combo.setEnabled(True)

        # Update status
        self.status_label.setText(message)
        if success:
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.add_to_project_btn.setEnabled(True)
        else:
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

        # Mark failed slots
        for i in range(3):
            if i >= len(self.generated_paths):
                _, status_label = self.preview_labels[i]
                if status_label.text() == "Generating...":
                    status_label.setText("✗ Not generated")
                    status_label.setStyleSheet("color: red;")

    def add_to_project(self):
        """Add generated references to project"""
        if not self.project:
            self.status_label.setText("⚠️ No project loaded")
            self.status_label.setStyleSheet("color: orange;")
            return

        if not self.generated_paths:
            self.status_label.setText("⚠️ No references to add")
            self.status_label.setStyleSheet("color: orange;")
            return

        try:
            # Get character name from description (first word or phrase before comma/dash)
            description = self.description_edit.toPlainText().strip()
            name = description.split(',')[0].split('-')[0].strip()
            if not name:
                name = "Character"

            # Add references to project
            added = 0
            for i, ref_path in enumerate(self.generated_paths, 1):
                ref_image = ReferenceImage(
                    path=ref_path,
                    ref_type=ReferenceImageType.CHARACTER,
                    name=name,
                    description=f"Auto-generated reference {i}/{len(self.generated_paths)}",
                    is_global=True  # Auto-generated refs are global by default
                )

                if self.project.add_global_reference(ref_image):
                    added += 1
                    logger.info(f"Added global reference to project: {ref_path.name}")
                else:
                    logger.warning(f"Failed to add reference: {ref_path.name}")

            # Save project
            if added > 0:
                self.project.save()
                self.status_label.setText(f"✓ Added {added} reference(s) to project!")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")

                # Emit signal
                self.references_generated.emit(self.generated_paths)

                # Close dialog after brief delay
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1500, self.accept)
            else:
                self.status_label.setText("⚠️ No references added (max 3 global references)")
                self.status_label.setStyleSheet("color: orange;")

        except Exception as e:
            logger.error(f"Failed to add references to project: {e}", exc_info=True)
            self.status_label.setText(f"✗ Failed to add: {str(e)}")
            self.status_label.setStyleSheet("color: red;")

    def closeEvent(self, event):
        """Handle close event - ensure worker thread is stopped and settings are saved."""
        # Save settings before closing
        self.save_settings()

        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            # Disconnect signals to prevent crashes during cleanup
            try:
                self.worker.progress.disconnect()
                self.worker.reference_generated.disconnect()
                self.worker.generation_complete.disconnect()
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
