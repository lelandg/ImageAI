"""
Enhanced workspace widget for video projects.

Includes image variant selection, crop controls, and Ken Burns settings.
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QComboBox, QSlider, QGroupBox,
    QGridLayout, QFrame, QScrollArea, QButtonGroup, QRadioButton,
    QCheckBox, QFileDialog, QMessageBox, QTabWidget, QListWidget,
    QListWidgetItem, QSplitter, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSize
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QBrush

from ...core.video.project_enhancements import (
    ProjectSettings, ImageVariant, SceneVariants, 
    CropMode, CropSettings, KenBurnsSettings, KenBurnsPresets,
    VersioningMode, AudioHandling, EnhancedProjectManager
)
from ...core.video.image_processing import ImageProcessor


class ImageVariantSelector(QWidget):
    """Widget for selecting between multiple image variants"""
    
    variant_selected = Signal(int)  # Emits selected variant index
    generate_more = Signal()  # Request more variants
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_variants: Optional[SceneVariants] = None
        self.current_index = 0
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Scene label
        self.scene_label = QLabel("No scene selected")
        self.scene_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.scene_label)
        
        # Navigation and controls
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setMaximumWidth(30)
        self.prev_btn.clicked.connect(self.show_previous)
        nav_layout.addWidget(self.prev_btn)
        
        self.variant_label = QLabel("No variants")
        self.variant_label.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(self.variant_label, 1)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setMaximumWidth(30)
        self.next_btn.clicked.connect(self.show_next)
        nav_layout.addWidget(self.next_btn)
        
        self.generate_btn = QPushButton("Generate More")
        self.generate_btn.clicked.connect(self.generate_more.emit)
        nav_layout.addWidget(self.generate_btn)
        
        layout.addLayout(nav_layout)
        
        # Image preview
        self.image_label = QLabel()
        self.image_label.setMinimumHeight(300)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
        self.image_label.setScaledContents(False)
        layout.addWidget(self.image_label, 1)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.select_btn = QPushButton("✓ Use This Image")
        self.select_btn.clicked.connect(self.select_current)
        action_layout.addWidget(self.select_btn)
        
        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.clicked.connect(self.delete_current)
        action_layout.addWidget(self.delete_btn)
        
        self.regenerate_btn = QPushButton("↻ Regenerate")
        self.regenerate_btn.clicked.connect(self.regenerate_current)
        action_layout.addWidget(self.regenerate_btn)
        
        layout.addLayout(action_layout)
        
        # Thumbnail strip
        self.thumbnail_scroll = QScrollArea()
        self.thumbnail_scroll.setMaximumHeight(80)
        self.thumbnail_scroll.setWidgetResizable(True)
        self.thumbnail_widget = QWidget()
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_widget)
        self.thumbnail_layout.setSpacing(5)
        self.thumbnail_scroll.setWidget(self.thumbnail_widget)
        layout.addWidget(self.thumbnail_scroll)
        
        self.update_ui()
    
    def set_scene_variants(self, variants: SceneVariants, scene_name: str = ""):
        """Set the variants for a scene"""
        self.current_variants = variants
        self.current_index = variants.selected_index if variants else 0
        self.scene_label.setText(f"Scene {variants.scene_index + 1}: {scene_name}" if variants else "No scene")
        self.update_ui()
        self.update_thumbnails()
    
    def update_ui(self):
        """Update UI based on current state"""
        has_variants = self.current_variants and len(self.current_variants.variants) > 0
        
        self.prev_btn.setEnabled(has_variants and self.current_index > 0)
        self.next_btn.setEnabled(has_variants and self.current_index < len(self.current_variants.variants) - 1)
        
        if has_variants:
            self.variant_label.setText(f"Image {self.current_index + 1} of {len(self.current_variants.variants)}")
            self.show_variant(self.current_index)
        else:
            self.variant_label.setText("No variants")
            self.image_label.clear()
            self.image_label.setText("No image variants\nClick 'Generate Images' to create variants")
        
        # Update button states
        self.select_btn.setEnabled(has_variants)
        self.delete_btn.setEnabled(has_variants and len(self.current_variants.variants) > 1)
        self.regenerate_btn.setEnabled(has_variants)
    
    def show_variant(self, index: int):
        """Display a specific variant"""
        if not self.current_variants or index >= len(self.current_variants.variants):
            return
        
        variant = self.current_variants.variants[index]
        
        # Load and display image
        if Path(variant.filename).exists():
            pixmap = QPixmap(variant.filename)
            # Scale to fit while maintaining aspect ratio
            scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText(f"Image not found:\n{variant.filename}")
        
        # Update selection indicator
        if variant.is_selected:
            self.select_btn.setText("✓ Selected")
            self.select_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        else:
            self.select_btn.setText("✓ Use This Image")
            self.select_btn.setStyleSheet("")
    
    def update_thumbnails(self):
        """Update thumbnail strip"""
        # Clear existing thumbnails
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.current_variants:
            return
        
        # Add thumbnails for each variant
        for i, variant in enumerate(self.current_variants.variants):
            thumb_label = QLabel()
            thumb_label.setFixedSize(60, 60)
            thumb_label.setScaledContents(True)
            thumb_label.setStyleSheet("border: 2px solid #ccc;")
            
            if Path(variant.filename).exists():
                pixmap = QPixmap(variant.filename)
                thumb_label.setPixmap(pixmap)
            else:
                thumb_label.setText("N/A")
                thumb_label.setAlignment(Qt.AlignCenter)
            
            # Highlight selected
            if variant.is_selected:
                thumb_label.setStyleSheet("border: 3px solid #4CAF50;")
            
            # Make clickable
            thumb_label.mousePressEvent = lambda e, idx=i: self.thumbnail_clicked(idx)
            
            self.thumbnail_layout.addWidget(thumb_label)
    
    def thumbnail_clicked(self, index: int):
        """Handle thumbnail click"""
        self.current_index = index
        self.update_ui()
    
    def show_previous(self):
        """Show previous variant"""
        if self.current_index > 0:
            self.current_index -= 1
            self.update_ui()
    
    def show_next(self):
        """Show next variant"""
        if self.current_variants and self.current_index < len(self.current_variants.variants) - 1:
            self.current_index += 1
            self.update_ui()
    
    def select_current(self):
        """Select current variant"""
        if self.current_variants:
            self.current_variants.select_variant(self.current_index)
            self.variant_selected.emit(self.current_index)
            self.update_ui()
            self.update_thumbnails()
    
    def delete_current(self):
        """Delete current variant"""
        if not self.current_variants or len(self.current_variants.variants) <= 1:
            return
        
        reply = QMessageBox.question(
            self, "Delete Variant",
            "Are you sure you want to delete this image variant?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Delete file
            variant = self.current_variants.variants[self.current_index]
            if Path(variant.filename).exists():
                Path(variant.filename).unlink()
            
            # Remove from list
            self.current_variants.variants.pop(self.current_index)
            
            # Adjust index
            if self.current_index >= len(self.current_variants.variants):
                self.current_index = len(self.current_variants.variants) - 1
            
            # Select new current if it was selected
            if variant.is_selected and self.current_variants.variants:
                self.current_variants.select_variant(self.current_index)
            
            self.update_ui()
            self.update_thumbnails()
    
    def regenerate_current(self):
        """Regenerate current variant"""
        # This would trigger regeneration of the current image
        # Emit signal or call parent method
        pass


class CropControlWidget(QWidget):
    """Widget for controlling image cropping"""
    
    crop_changed = Signal(CropSettings)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_settings = CropSettings()
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Crop mode selection
        mode_group = QGroupBox("Crop Position")
        mode_layout = QGridLayout()
        
        self.mode_buttons = QButtonGroup()
        modes = [
            ("Center", CropMode.CENTER, 0, 0),
            ("Top", CropMode.TOP, 0, 1),
            ("Bottom", CropMode.BOTTOM, 0, 2),
            ("Rule of Thirds", CropMode.RULE_OF_THIRDS, 1, 0),
            ("Manual", CropMode.MANUAL, 1, 1),
            ("Smart", CropMode.SMART, 1, 2)
        ]
        
        for name, mode, row, col in modes:
            btn = QRadioButton(name)
            btn.toggled.connect(lambda checked, m=mode: self.set_mode(m) if checked else None)
            self.mode_buttons.addButton(btn)
            mode_layout.addWidget(btn, row, col)
            if mode == CropMode.CENTER:
                btn.setChecked(True)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Manual position controls
        self.position_group = QGroupBox("Manual Position")
        pos_layout = QGridLayout()
        
        pos_layout.addWidget(QLabel("X:"), 0, 0)
        self.x_slider = QSlider(Qt.Horizontal)
        self.x_slider.setRange(0, 100)
        self.x_slider.setValue(50)
        self.x_slider.valueChanged.connect(self.update_position)
        pos_layout.addWidget(self.x_slider, 0, 1)
        self.x_label = QLabel("0.50")
        pos_layout.addWidget(self.x_label, 0, 2)
        
        pos_layout.addWidget(QLabel("Y:"), 1, 0)
        self.y_slider = QSlider(Qt.Horizontal)
        self.y_slider.setRange(0, 100)
        self.y_slider.setValue(50)
        self.y_slider.valueChanged.connect(self.update_position)
        pos_layout.addWidget(self.y_slider, 1, 1)
        self.y_label = QLabel("0.50")
        pos_layout.addWidget(self.y_label, 1, 2)
        
        self.position_group.setLayout(pos_layout)
        self.position_group.setEnabled(False)
        layout.addWidget(self.position_group)
        
        # Preview area
        self.preview_label = QLabel()
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid #ccc; background: #f8f8f8;")
        layout.addWidget(self.preview_label)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        action_layout.addWidget(self.reset_btn)
        
        self.apply_all_btn = QPushButton("Apply to All Similar")
        self.apply_all_btn.clicked.connect(self.apply_to_all)
        action_layout.addWidget(self.apply_all_btn)
        
        layout.addLayout(action_layout)
    
    def set_mode(self, mode: CropMode):
        """Set crop mode"""
        self.current_settings.mode = mode
        self.position_group.setEnabled(mode == CropMode.MANUAL)
        self.crop_changed.emit(self.current_settings)
        self.update_preview()
    
    def update_position(self):
        """Update manual position from sliders"""
        self.current_settings.position = {
            "x": self.x_slider.value() / 100.0,
            "y": self.y_slider.value() / 100.0
        }
        self.x_label.setText(f"{self.current_settings.position['x']:.2f}")
        self.y_label.setText(f"{self.current_settings.position['y']:.2f}")
        self.crop_changed.emit(self.current_settings)
        self.update_preview()
    
    def set_settings(self, settings: CropSettings):
        """Set crop settings"""
        self.current_settings = settings
        
        # Update UI
        for btn in self.mode_buttons.buttons():
            if btn.text().lower().replace(" ", "_") == settings.mode.value:
                btn.setChecked(True)
                break
        
        self.x_slider.setValue(int(settings.position["x"] * 100))
        self.y_slider.setValue(int(settings.position["y"] * 100))
        
        self.update_preview()
    
    def update_preview(self):
        """Update crop preview"""
        # This would show a preview of the crop
        # For now, just show text
        mode_text = self.current_settings.mode.value.replace("_", " ").title()
        if self.current_settings.mode == CropMode.MANUAL:
            pos_text = f"Position: ({self.current_settings.position['x']:.2f}, {self.current_settings.position['y']:.2f})"
            self.preview_label.setText(f"Crop Mode: {mode_text}\n{pos_text}")
        else:
            self.preview_label.setText(f"Crop Mode: {mode_text}")
    
    def reset_to_defaults(self):
        """Reset to default settings"""
        self.set_settings(CropSettings())
    
    def apply_to_all(self):
        """Apply settings to all similar images"""
        # This would be handled by parent
        pass


class KenBurnsControlWidget(QWidget):
    """Widget for controlling Ken Burns effects"""
    
    ken_burns_changed = Signal(KenBurnsSettings)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_settings = KenBurnsSettings()
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Enable checkbox
        self.enable_check = QCheckBox("Enable Ken Burns Effect")
        self.enable_check.toggled.connect(self.toggle_enabled)
        layout.addWidget(self.enable_check)
        
        # Preset selection
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(KenBurnsPresets.list_presets())
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        preset_layout.addWidget(self.preset_combo, 1)
        
        layout.addLayout(preset_layout)
        
        # Start/End position controls
        self.controls_widget = QWidget()
        controls_layout = QGridLayout(self.controls_widget)
        
        # Start position
        controls_layout.addWidget(QLabel("Start:"), 0, 0)
        self.start_x = QDoubleSpinBox()
        self.start_x.setRange(0, 1)
        self.start_x.setSingleStep(0.1)
        self.start_x.setValue(0.5)
        self.start_x.valueChanged.connect(self.update_settings)
        controls_layout.addWidget(QLabel("X:"), 0, 1)
        controls_layout.addWidget(self.start_x, 0, 2)
        
        self.start_y = QDoubleSpinBox()
        self.start_y.setRange(0, 1)
        self.start_y.setSingleStep(0.1)
        self.start_y.setValue(0.5)
        self.start_y.valueChanged.connect(self.update_settings)
        controls_layout.addWidget(QLabel("Y:"), 0, 3)
        controls_layout.addWidget(self.start_y, 0, 4)
        
        self.start_scale = QDoubleSpinBox()
        self.start_scale.setRange(0.5, 2.0)
        self.start_scale.setSingleStep(0.1)
        self.start_scale.setValue(1.0)
        self.start_scale.valueChanged.connect(self.update_settings)
        controls_layout.addWidget(QLabel("Scale:"), 0, 5)
        controls_layout.addWidget(self.start_scale, 0, 6)
        
        # End position
        controls_layout.addWidget(QLabel("End:"), 1, 0)
        self.end_x = QDoubleSpinBox()
        self.end_x.setRange(0, 1)
        self.end_x.setSingleStep(0.1)
        self.end_x.setValue(0.5)
        self.end_x.valueChanged.connect(self.update_settings)
        controls_layout.addWidget(QLabel("X:"), 1, 1)
        controls_layout.addWidget(self.end_x, 1, 2)
        
        self.end_y = QDoubleSpinBox()
        self.end_y.setRange(0, 1)
        self.end_y.setSingleStep(0.1)
        self.end_y.setValue(0.5)
        self.end_y.valueChanged.connect(self.update_settings)
        controls_layout.addWidget(QLabel("Y:"), 1, 3)
        controls_layout.addWidget(self.end_y, 1, 4)
        
        self.end_scale = QDoubleSpinBox()
        self.end_scale.setRange(0.5, 2.0)
        self.end_scale.setSingleStep(0.1)
        self.end_scale.setValue(1.1)
        self.end_scale.valueChanged.connect(self.update_settings)
        controls_layout.addWidget(QLabel("Scale:"), 1, 5)
        controls_layout.addWidget(self.end_scale, 1, 6)
        
        # Easing
        controls_layout.addWidget(QLabel("Easing:"), 2, 0)
        self.easing_combo = QComboBox()
        self.easing_combo.addItems(["linear", "ease-in", "ease-out", "ease-in-out"])
        self.easing_combo.currentTextChanged.connect(self.update_settings)
        controls_layout.addWidget(self.easing_combo, 2, 1, 1, 3)
        
        self.controls_widget.setEnabled(False)
        layout.addWidget(self.controls_widget)
        
        # Preview button
        self.preview_btn = QPushButton("▶ Preview Animation")
        self.preview_btn.setEnabled(False)
        layout.addWidget(self.preview_btn)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.set_start_btn = QPushButton("Set Current as Start")
        self.set_start_btn.setEnabled(False)
        action_layout.addWidget(self.set_start_btn)
        
        self.set_end_btn = QPushButton("Set Current as End")
        self.set_end_btn.setEnabled(False)
        action_layout.addWidget(self.set_end_btn)
        
        layout.addLayout(action_layout)
    
    def toggle_enabled(self, checked: bool):
        """Toggle Ken Burns effect"""
        self.current_settings.enabled = checked
        self.controls_widget.setEnabled(checked)
        self.preview_btn.setEnabled(checked)
        self.set_start_btn.setEnabled(checked)
        self.set_end_btn.setEnabled(checked)
        self.ken_burns_changed.emit(self.current_settings)
    
    def apply_preset(self, preset_name: str):
        """Apply a preset"""
        preset = KenBurnsPresets.get_preset(preset_name)
        self.set_settings(preset)
    
    def update_settings(self):
        """Update settings from UI"""
        self.current_settings.start = {
            "x": self.start_x.value(),
            "y": self.start_y.value(),
            "scale": self.start_scale.value()
        }
        self.current_settings.end = {
            "x": self.end_x.value(),
            "y": self.end_y.value(),
            "scale": self.end_scale.value()
        }
        self.current_settings.easing = self.easing_combo.currentText()
        self.ken_burns_changed.emit(self.current_settings)
    
    def set_settings(self, settings: KenBurnsSettings):
        """Set Ken Burns settings"""
        self.current_settings = settings
        
        # Update UI
        self.enable_check.setChecked(settings.enabled)
        
        self.start_x.setValue(settings.start["x"])
        self.start_y.setValue(settings.start["y"])
        self.start_scale.setValue(settings.start["scale"])
        
        self.end_x.setValue(settings.end["x"])
        self.end_y.setValue(settings.end["y"])
        self.end_scale.setValue(settings.end["scale"])
        
        self.easing_combo.setCurrentText(settings.easing)