"""
Project Browser Dialog for Video Projects
Allows users to browse, preview, and open existing projects
"""

from pathlib import Path
from datetime import datetime
import json
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QHeaderView, QAbstractItemView,
    QMessageBox, QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


class ProjectBrowserDialog(QDialog):
    """Dialog for browsing and opening video projects"""
    
    project_selected = Signal(Path)  # Emitted when a project is selected
    
    def __init__(self, project_manager, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.selected_project_path = None
        self.settings = QSettings("ImageAI", "VideoProjects")
        
        self.setWindowTitle("Open Video Project")
        self.setMinimumSize(800, 500)
        
        self.setup_ui()
        self.load_projects()
    
    def setup_ui(self):
        """Set up the UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Video Projects")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Project table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Created", "Modified", "Duration", "Path"])
        
        # Configure table
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # Adjust column widths
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        # Connect double-click
        self.table.doubleClicked.connect(self.on_double_click)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        
        layout.addWidget(self.table)
        
        # Project info box
        info_group = QGroupBox("Project Details")
        info_layout = QVBoxLayout(info_group)
        self.info_label = QLabel("Select a project to see details")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        layout.addWidget(info_group)
        
        # Settings
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        self.auto_reload_check = QCheckBox("Automatically reload last project on startup")
        self.auto_reload_check.setChecked(self.settings.value("auto_reload_last", True, type=bool))
        self.auto_reload_check.toggled.connect(self.on_auto_reload_toggled)
        settings_layout.addWidget(self.auto_reload_check)
        
        layout.addWidget(settings_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_projects)
        button_layout.addWidget(self.refresh_btn)
        
        button_layout.addStretch()
        
        self.open_btn = QPushButton("Open")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_selected)
        button_layout.addWidget(self.open_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def load_projects(self):
        """Load all available projects"""
        self.table.setRowCount(0)
        
        try:
            projects = self.project_manager.list_projects()
            
            for project_info in projects:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                # Name
                name_item = QTableWidgetItem(project_info.get('name', 'Unnamed'))
                name_item.setData(Qt.UserRole, project_info['path'])  # Store path
                self.table.setItem(row, 0, name_item)
                
                # Created
                created = project_info.get('created', '')
                if created:
                    try:
                        dt = datetime.fromisoformat(created)
                        created = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                self.table.setItem(row, 1, QTableWidgetItem(created))
                
                # Modified
                modified = project_info.get('modified', '')
                if modified:
                    try:
                        dt = datetime.fromisoformat(modified)
                        modified = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                self.table.setItem(row, 2, QTableWidgetItem(modified))
                
                # Duration
                duration = project_info.get('target_duration', '')
                self.table.setItem(row, 3, QTableWidgetItem(duration or '-'))
                
                # Path (shortened)
                path = Path(project_info['path'])
                path_display = path.parent.name
                path_item = QTableWidgetItem(path_display)
                path_item.setToolTip(str(path))
                self.table.setItem(row, 4, path_item)
            
            # Sort by modified date (newest first)
            self.table.sortItems(2, Qt.DescendingOrder)
            
            # Select the most recent if exists
            if self.table.rowCount() > 0:
                self.table.selectRow(0)
                
        except Exception as e:
            logger.error(f"Failed to load projects: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to load projects: {e}")
    
    def on_selection_changed(self):
        """Handle selection change"""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            name_item = self.table.item(row, 0)
            if name_item:
                self.selected_project_path = Path(name_item.data(Qt.UserRole))
                self.open_btn.setEnabled(True)
                self.update_info()
            else:
                self.selected_project_path = None
                self.open_btn.setEnabled(False)
        else:
            self.selected_project_path = None
            self.open_btn.setEnabled(False)
            self.info_label.setText("Select a project to see details")
    
    def update_info(self):
        """Update the info display for selected project"""
        if not self.selected_project_path:
            return
        
        try:
            with open(self.selected_project_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            info_text = []
            
            # Basic info
            info_text.append(f"<b>Name:</b> {project_data.get('name', 'Unnamed')}")
            info_text.append(f"<b>ID:</b> {project_data.get('project_id', 'Unknown')}")
            
            # Input text preview
            input_text = project_data.get('input', {}).get('raw', '')
            if input_text:
                preview = input_text[:200] + ('...' if len(input_text) > 200 else '')
                preview = preview.replace('\n', ' ')
                info_text.append(f"<b>Content:</b> {preview}")
            
            # MIDI info
            midi_data = project_data.get('midi')
            if midi_data and midi_data.get('file_path'):
                midi_path = Path(midi_data['file_path'])
                info_text.append(f"<b>MIDI:</b> {midi_path.name}")
                if midi_data.get('timing_data'):
                    timing = midi_data['timing_data']
                    info_text.append(f"  {timing.get('tempo_bpm', 0):.0f} BPM, {timing.get('time_signature', '?')}")
            
            # Scene count
            scenes = project_data.get('scenes', [])
            if scenes:
                info_text.append(f"<b>Scenes:</b> {len(scenes)}")
            
            self.info_label.setText("<br>".join(info_text))
            
        except Exception as e:
            logger.warning(f"Could not load project info: {e}")
            self.info_label.setText("Could not load project details")
    
    def on_double_click(self):
        """Handle double-click on project"""
        if self.selected_project_path:
            self.open_selected()
    
    def open_selected(self):
        """Open the selected project"""
        if self.selected_project_path:
            # Save as last opened project
            self.settings.setValue("last_project", str(self.selected_project_path))
            self.project_selected.emit(self.selected_project_path)
            self.accept()
    
    def on_auto_reload_toggled(self, checked):
        """Handle auto-reload setting change"""
        self.settings.setValue("auto_reload_last", checked)
        logger.info(f"Auto-reload last project: {checked}")


def get_last_project_path():
    """Get the path to the last opened project if auto-reload is enabled"""
    settings = QSettings("ImageAI", "VideoProjects")
    
    auto_reload = settings.value("auto_reload_last", True, type=bool)
    logger.debug(f"Auto-reload setting: {auto_reload}")
    
    if not auto_reload:
        logger.debug("Auto-reload disabled")
        return None
    
    last_project = settings.value("last_project")
    logger.debug(f"Last project setting: {last_project}")
    
    if last_project:
        path = Path(last_project)
        if path.exists():
            logger.debug(f"Last project exists: {path}")
            return path
        else:
            logger.debug(f"Last project does not exist: {path}")
    else:
        logger.debug("No last project saved")
    
    return None