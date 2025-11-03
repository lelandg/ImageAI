"""
Project management dialogs for video projects.

Includes New Project, Open Project, and Project Settings dialogs.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QSpinBox, QCheckBox, QGroupBox, QListWidget,
    QListWidgetItem, QDialogButtonBox, QFileDialog,
    QMessageBox, QRadioButton, QButtonGroup, QGridLayout,
    QTabWidget, QWidget, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon

from ...core.video.project_enhancements import (
    ProjectSettings, VersioningMode, CropMode, AudioHandling,
    EnhancedProjectManager
)


class NewProjectDialog(QDialog):
    """Dialog for creating a new video project"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Video Project")
        self.setModal(True)
        self.resize(600, 500)
        
        self.settings = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Create tabs
        tabs = QTabWidget()
        
        # Basic settings tab
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        
        # Project name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter project name...")
        basic_layout.addRow("Project Name:", self.name_edit)
        
        # Versioning mode
        version_group = QGroupBox("Project Versioning")
        version_layout = QGridLayout()
        
        self.version_buttons = QButtonGroup()
        modes = [
            ("No versioning", VersioningMode.NONE, "MyProject"),
            ("Timestamp", VersioningMode.TIMESTAMP, "MyProject_20250109_143022"),
            ("Sequential", VersioningMode.SEQUENTIAL, "MyProject_v001"),
            ("Both", VersioningMode.BOTH, "MyProject_v001_20250109_143022")
        ]
        
        for i, (label, mode, example) in enumerate(modes):
            btn = QRadioButton(label)
            btn.setProperty("mode", mode)
            self.version_buttons.addButton(btn)
            version_layout.addWidget(btn, i, 0)
            version_layout.addWidget(QLabel(f"Example: {example}"), i, 1)
            if mode == VersioningMode.NONE:
                btn.setChecked(True)
        
        version_group.setLayout(version_layout)
        basic_layout.addRow(version_group)
        
        # Audio handling
        self.audio_combo = QComboBox()
        for mode in AudioHandling:
            self.audio_combo.addItem(mode.value.title(), mode)
        basic_layout.addRow("Audio Files:", self.audio_combo)
        
        tabs.addTab(basic_tab, "Basic")
        
        # Generation settings tab
        gen_tab = QWidget()
        gen_layout = QFormLayout(gen_tab)
        
        # Images per scene
        self.images_spin = QSpinBox()
        self.images_spin.setRange(1, 10)
        self.images_spin.setValue(3)
        gen_layout.addRow("Images per Scene:", self.images_spin)
        
        # Auto crop square images
        self.auto_crop_check = QCheckBox("Auto-crop square images for video aspect ratio")
        self.auto_crop_check.setChecked(True)
        gen_layout.addRow(self.auto_crop_check)
        
        # Default crop mode
        self.crop_combo = QComboBox()
        for mode in CropMode:
            self.crop_combo.addItem(mode.value.replace("_", " ").title(), mode)
        gen_layout.addRow("Default Crop Mode:", self.crop_combo)
        
        tabs.addTab(gen_tab, "Generation")
        
        # Ken Burns tab
        kb_tab = QWidget()
        kb_layout = QFormLayout(kb_tab)
        
        # Ken Burns enabled
        self.kb_check = QCheckBox("Enable Ken Burns effect by default")
        kb_layout.addRow(self.kb_check)
        
        # Ken Burns intensity
        self.kb_intensity = QDoubleSpinBox()
        self.kb_intensity.setRange(0.1, 1.0)
        self.kb_intensity.setSingleStep(0.1)
        self.kb_intensity.setValue(0.3)
        kb_layout.addRow("Effect Intensity:", self.kb_intensity)
        
        # Auto Ken Burns for square
        self.kb_auto_check = QCheckBox("Auto-enable for square images")
        kb_layout.addRow(self.kb_auto_check)
        
        tabs.addTab(kb_tab, "Ken Burns")
        
        # Rendering tab
        render_tab = QWidget()
        render_layout = QFormLayout(render_tab)
        
        # Auto-save renders
        self.auto_save_check = QCheckBox("Auto-save video renders")
        self.auto_save_check.setChecked(True)
        render_layout.addRow(self.auto_save_check)
        
        # Keep draft renders
        self.keep_drafts_spin = QSpinBox()
        self.keep_drafts_spin.setRange(0, 10)
        self.keep_drafts_spin.setValue(3)
        render_layout.addRow("Keep Draft Renders:", self.keep_drafts_spin)
        
        # Render quality
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["draft", "final", "custom"])
        render_layout.addRow("Default Quality:", self.quality_combo)
        
        tabs.addTab(render_tab, "Rendering")
        
        layout.addWidget(tabs)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def accept(self):
        """Validate and accept dialog"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Invalid Name", 
                               "Please enter a project name.")
            return
        
        # Create settings from UI
        version_mode = VersioningMode.NONE
        for btn in self.version_buttons.buttons():
            if btn.isChecked():
                version_mode = btn.property("mode")
                break
        
        self.settings = ProjectSettings(
            name=self.name_edit.text().strip(),
            versioning_mode=version_mode,
            ken_burns_enabled=self.kb_check.isChecked(),
            ken_burns_intensity=self.kb_intensity.value(),
            auto_ken_burns_for_square=self.kb_auto_check.isChecked(),
            default_crop_mode=self.crop_combo.currentData(),
            images_per_scene=self.images_spin.value(),
            auto_crop_square=self.auto_crop_check.isChecked(),
            auto_save_renders=self.auto_save_check.isChecked(),
            keep_draft_renders=self.keep_drafts_spin.value(),
            render_quality=self.quality_combo.currentText(),
            audio_handling=self.audio_combo.currentData()
        )
        
        super().accept()


class OpenProjectDialog(QDialog):
    """Dialog for opening existing video projects"""
    
    def __init__(self, project_manager: EnhancedProjectManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Video Project")
        self.setModal(True)
        self.resize(700, 500)
        
        self.project_manager = project_manager
        self.selected_project = None
        self.init_ui()
        self.load_projects()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Recent projects section
        layout.addWidget(QLabel("Recent Projects:"))
        
        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.project_list)
        
        # Project info
        info_group = QGroupBox("Project Information")
        info_layout = QFormLayout()
        
        self.info_name = QLabel("-")
        info_layout.addRow("Name:", self.info_name)
        
        self.info_created = QLabel("-")
        info_layout.addRow("Created:", self.info_created)
        
        self.info_modified = QLabel("-")
        info_layout.addRow("Modified:", self.info_modified)
        
        self.info_path = QLabel("-")
        self.info_path.setWordWrap(True)
        info_layout.addRow("Location:", self.info_path)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_for_project)
        button_layout.addWidget(self.browse_btn)
        
        button_layout.addStretch()
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.Open | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Open).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        
        layout.addLayout(button_layout)
        
        # Connect selection change
        self.project_list.currentItemChanged.connect(self.update_info)
    
    def load_projects(self):
        """Load recent projects"""
        self.project_list.clear()
        
        for project_info in self.project_manager.recent_projects:
            item = QListWidgetItem(project_info["name"])
            item.setData(Qt.UserRole, project_info)
            
            # Add icon based on age
            last_opened = datetime.fromisoformat(project_info["last_opened"])
            age_days = (datetime.now() - last_opened).days
            
            if age_days == 0:
                item.setText(f"{project_info['name']} (Today)")
            elif age_days == 1:
                item.setText(f"{project_info['name']} (Yesterday)")
            else:
                item.setText(f"{project_info['name']} ({age_days} days ago)")
            
            self.project_list.addItem(item)
    
    def update_info(self, item: QListWidgetItem):
        """Update project information display"""
        if not item:
            return
        
        project_info = item.data(Qt.UserRole)
        self.info_name.setText(project_info["name"])
        self.info_path.setText(project_info["path"])
        
        # Try to load more info from project
        project_path = Path(project_info["path"])
        if project_path.exists():
            settings_file = project_path / "project_settings.json"
            if settings_file.exists():
                import json
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    # Could display more settings here
            
            workspace_file = project_path / "workspace.json"
            if workspace_file.exists():
                import json
                with open(workspace_file, 'r') as f:
                    workspace = json.load(f)
                    self.info_created.setText(workspace.get("created", "-"))
                    self.info_modified.setText(workspace.get("last_modified", "-"))
    
    def browse_for_project(self):
        """Browse for project folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Folder",
            str(self.project_manager.base_dir),
            options=QFileDialog.Option.DontUseNativeDialog
        )
        
        if folder:
            self.selected_project = Path(folder)
            self.accept()
    
    def accept(self):
        """Accept selected project"""
        if not self.selected_project:
            current_item = self.project_list.currentItem()
            if current_item:
                project_info = current_item.data(Qt.UserRole)
                self.selected_project = Path(project_info["path"])
        
        if self.selected_project and self.selected_project.exists():
            super().accept()
        else:
            QMessageBox.warning(self, "Invalid Project",
                               "Please select a valid project.")


class ProjectSettingsDialog(QDialog):
    """Dialog for editing project settings"""
    
    def __init__(self, settings: ProjectSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.setModal(True)
        self.resize(500, 400)
        
        self.settings = settings
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Create form
        form_layout = QFormLayout()
        
        # Project name (read-only)
        name_label = QLabel(self.settings.name)
        name_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow("Project:", name_label)
        
        # Ken Burns settings
        kb_group = QGroupBox("Ken Burns Defaults")
        kb_layout = QFormLayout()
        
        self.kb_check = QCheckBox("Enable by default")
        self.kb_check.setChecked(self.settings.ken_burns_enabled)
        kb_layout.addRow(self.kb_check)
        
        self.kb_intensity = QDoubleSpinBox()
        self.kb_intensity.setRange(0.1, 1.0)
        self.kb_intensity.setSingleStep(0.1)
        self.kb_intensity.setValue(self.settings.ken_burns_intensity)
        kb_layout.addRow("Intensity:", self.kb_intensity)
        
        self.kb_auto = QCheckBox("Auto-enable for square images")
        self.kb_auto.setChecked(self.settings.auto_ken_burns_for_square)
        kb_layout.addRow(self.kb_auto)
        
        kb_group.setLayout(kb_layout)
        form_layout.addRow(kb_group)
        
        # Crop settings
        crop_group = QGroupBox("Crop Defaults")
        crop_layout = QFormLayout()
        
        self.crop_mode = QComboBox()
        for mode in CropMode:
            self.crop_mode.addItem(mode.value.replace("_", " ").title(), mode)
        self.crop_mode.setCurrentText(
            self.settings.default_crop_mode.value.replace("_", " ").title()
        )
        crop_layout.addRow("Mode:", self.crop_mode)
        
        self.auto_crop = QCheckBox("Auto-crop square images")
        self.auto_crop.setChecked(self.settings.auto_crop_square)
        crop_layout.addRow(self.auto_crop)
        
        crop_group.setLayout(crop_layout)
        form_layout.addRow(crop_group)
        
        # Generation settings
        gen_group = QGroupBox("Generation")
        gen_layout = QFormLayout()
        
        self.images_spin = QSpinBox()
        self.images_spin.setRange(1, 10)
        self.images_spin.setValue(self.settings.images_per_scene)
        gen_layout.addRow("Images per Scene:", self.images_spin)
        
        gen_group.setLayout(gen_layout)
        form_layout.addRow(gen_group)
        
        # Rendering settings
        render_group = QGroupBox("Rendering")
        render_layout = QFormLayout()
        
        self.auto_save = QCheckBox("Auto-save renders")
        self.auto_save.setChecked(self.settings.auto_save_renders)
        render_layout.addRow(self.auto_save)
        
        self.keep_drafts = QSpinBox()
        self.keep_drafts.setRange(0, 10)
        self.keep_drafts.setValue(self.settings.keep_draft_renders)
        render_layout.addRow("Keep Drafts:", self.keep_drafts)
        
        render_group.setLayout(render_layout)
        form_layout.addRow(render_group)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def accept(self):
        """Save settings and accept"""
        # Update settings from UI
        self.settings.ken_burns_enabled = self.kb_check.isChecked()
        self.settings.ken_burns_intensity = self.kb_intensity.value()
        self.settings.auto_ken_burns_for_square = self.kb_auto.isChecked()
        self.settings.default_crop_mode = self.crop_mode.currentData()
        self.settings.auto_crop_square = self.auto_crop.isChecked()
        self.settings.images_per_scene = self.images_spin.value()
        self.settings.auto_save_renders = self.auto_save.isChecked()
        self.settings.keep_draft_renders = self.keep_drafts.value()
        
        super().accept()