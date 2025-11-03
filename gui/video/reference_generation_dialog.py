"""
Reference Generation Wizard Dialog.
Generates character reference images (3 angles) for video project consistency.
"""

import logging
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QProgressBar, QGroupBox, QComboBox, QSpinBox,
    QGridLayout, QScrollArea, QWidget, QFrame, QSplitter, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap

from core.video.project import ReferenceImage
from core.video.reference_manager import ReferenceImageType, ReferenceImageValidator

logger = logging.getLogger(__name__)


class ReferenceGenerationWorker(QThread):
    """Worker thread for generating reference images"""

    progress = Signal(int, str)  # progress_percent, status_message
    reference_generated = Signal(int, str)  # index (1-3), file_path
    generation_complete = Signal(bool, str)  # success, message

    def __init__(self, description: str, style: str, output_dir: Path, image_generator, reference_image: Optional[Path] = None):
        super().__init__()
        self.description = description
        self.style = style
        self.output_dir = output_dir
        self.image_generator = image_generator
        self.reference_image = reference_image
        self.generated_paths = []

    def run(self):
        """Generate 3 reference images"""
        try:
            self.progress.emit(0, "Starting reference generation...")

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
                    # Generate image
                    logger.info(f"Generating reference {i}/3: {prompt[:80]}...")

                    # Pass reference image if provided
                    if self.reference_image:
                        image_path = self.image_generator(prompt, self.output_dir, f"char_ref_{angle}", self.reference_image)
                    else:
                        image_path = self.image_generator(prompt, self.output_dir, f"char_ref_{angle}")

                    if image_path and image_path.exists():
                        # Validate
                        validator = ReferenceImageValidator()
                        info = validator.validate_reference_image(image_path)

                        if info.is_valid:
                            self.generated_paths.append(image_path)
                            self.reference_generated.emit(i, str(image_path))
                            logger.info(f"✓ Generated reference {i}/3: {image_path.name}")
                        else:
                            error_msg = "; ".join(info.validation_errors)
                            logger.warning(f"✗ Reference {i}/3 failed validation: {error_msg}")
                            self.progress.emit(int(i/3 * 100), f"⚠️ Reference {i} validation failed: {error_msg}")
                    else:
                        logger.error(f"✗ Failed to generate reference {i}/3")
                        self.progress.emit(int(i/3 * 100), f"⚠️ Reference {i} generation failed")

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
    """Dialog for generating character reference images"""

    references_generated = Signal(list)  # List[Path] of generated reference paths

    def __init__(self, parent=None, project=None, image_generator=None):
        super().__init__(parent)
        self.project = project
        self.image_generator = image_generator
        self.generated_paths = []
        self.worker = None

        self.setWindowTitle("Generate Character References")
        self.setModal(True)
        self.resize(800, 900)

        self.setup_ui()

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
        style_layout.addWidget(self.style_combo, 0, 1)

        # Quality
        style_layout.addWidget(QLabel("Quality:"), 1, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["high", "medium", "low"])
        self.quality_combo.setCurrentText("high")
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

        # Store reference image path
        self.reference_image_path = None

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
            if hasattr(self, 'add_btn'):
                self.add_btn.setEnabled(True)

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

            # Enable add to project button
            if hasattr(self, 'add_btn'):
                self.add_btn.setEnabled(True)

    def start_generation(self):
        """Start reference generation"""
        description = self.description_edit.toPlainText().strip()
        if not description:
            self.status_label.setText("⚠️ Please enter a character description")
            self.status_label.setStyleSheet("color: orange;")
            return

        if not self.image_generator:
            self.status_label.setText("⚠️ No image generator available")
            self.status_label.setStyleSheet("color: red;")
            return

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
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Reset previews
        self.generated_paths = []
        for preview_label, status_label in self.preview_labels:
            preview_label.setPixmap(QPixmap())
            preview_label.setText("(Generating...)")
            status_label.setText("Generating...")
            status_label.setStyleSheet("color: blue; font-style: italic;")

        # Start worker
        self.worker = ReferenceGenerationWorker(description, style, output_dir, self.image_generator, self.reference_image_path)
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
        """Handle close event - ensure worker thread is stopped."""
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
