"""
Workspace widget for video project - main working area.

This module contains the main workspace UI that was previously
in video_project_tab.py, now separated for tab organization.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QSplitter, QProgressBar,
    QCheckBox, QSlider, QHeaderView
)
from PySide6.QtCore import Qt, Signal, Slot

from core.video.project import VideoProject, Scene
from core.video.project_manager import ProjectManager
from core.video.storyboard import StoryboardGenerator
from core.video.config import VideoConfig


class WorkspaceWidget(QWidget):
    """Main workspace for video project editing"""
    
    # Signals
    project_changed = Signal(object)  # VideoProject
    generation_requested = Signal(str, dict)  # operation, kwargs
    
    def __init__(self, config: Dict[str, Any], providers: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.providers = providers
        self.video_config = VideoConfig()
        self.project_manager = ProjectManager(self.video_config.get_projects_dir())
        self.current_project = None
        self.logger = logging.getLogger(__name__)
        
        self.init_ui()
        
        # Auto-reload last project if enabled
        self.auto_load_last_project()
    
    def init_ui(self):
        """Initialize the workspace UI"""
        layout = QVBoxLayout(self)
        
        # Project header
        layout.addWidget(self.create_project_header())
        
        # Main content area with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Input and settings
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self.create_input_panel())
        left_layout.addWidget(self.create_settings_panel())
        left_layout.addWidget(self.create_audio_panel())
        left_layout.addStretch()
        splitter.addWidget(left_panel)
        
        # Right panel - Storyboard and export
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.create_storyboard_panel())
        right_layout.addWidget(self.create_export_panel())
        right_layout.addStretch()
        splitter.addWidget(right_panel)
        
        # Set initial splitter sizes
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        
        # Status bar
        layout.addWidget(self.create_status_bar())
    
    def create_project_header(self) -> QWidget:
        """Create project header with name and controls"""
        widget = QWidget()
        widget.setMaximumHeight(40)  # Make it compact
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)  # Reduce margins
        
        layout.addWidget(QLabel("Project:"))
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("My Video Project")
        self.project_name.setMaximumWidth(200)
        layout.addWidget(self.project_name)
        
        # Make buttons compact
        button_style = "QPushButton { padding: 2px 8px; }"
        
        self.new_btn = QPushButton("New")
        self.new_btn.setStyleSheet(button_style)
        self.new_btn.clicked.connect(self.new_project)
        layout.addWidget(self.new_btn)
        
        self.open_btn = QPushButton("Open")
        self.open_btn.setStyleSheet(button_style)
        self.open_btn.clicked.connect(self.open_project)
        layout.addWidget(self.open_btn)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setStyleSheet(button_style)
        self.browse_btn.clicked.connect(self.browse_projects)
        layout.addWidget(self.browse_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet(button_style)
        self.save_btn.clicked.connect(self.save_project)
        layout.addWidget(self.save_btn)
        
        layout.addStretch()
        return widget
    
    def create_input_panel(self) -> QWidget:
        """Create input panel for lyrics/text"""
        group = QGroupBox("Input")
        layout = QVBoxLayout()
        
        # Format selector
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Auto-detect", "Timestamped", "Structured", "Plain text"])
        format_layout.addWidget(self.format_combo)
        
        self.load_file_btn = QPushButton("Load File")
        self.load_file_btn.clicked.connect(self.load_input_file)
        format_layout.addWidget(self.load_file_btn)
        
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        # Text input
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Paste lyrics or text here...")
        self.input_text.setMaximumHeight(150)
        layout.addWidget(self.input_text)
        
        # Timing controls
        timing_layout = QHBoxLayout()
        timing_layout.addWidget(QLabel("Target Length:"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 600)
        self.duration_spin.setValue(120)
        self.duration_spin.setSuffix(" sec")
        timing_layout.addWidget(self.duration_spin)
        
        timing_layout.addWidget(QLabel("Pacing:"))
        self.pacing_combo = QComboBox()
        self.pacing_combo.addItems(["Fast", "Medium", "Slow"])
        self.pacing_combo.setCurrentIndex(1)
        timing_layout.addWidget(self.pacing_combo)
        
        self.generate_storyboard_btn = QPushButton("Generate Storyboard")
        self.generate_storyboard_btn.clicked.connect(self.generate_storyboard)
        timing_layout.addWidget(self.generate_storyboard_btn)
        
        timing_layout.addStretch()
        layout.addLayout(timing_layout)
        
        group.setLayout(layout)
        return group
    
    def create_settings_panel(self) -> QWidget:
        """Create settings panel for providers and style"""
        group = QGroupBox("Generation Settings")
        layout = QVBoxLayout()
        
        # LLM provider for prompts
        llm_layout = QHBoxLayout()
        llm_layout.addWidget(QLabel("LLM:"))
        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.addItems(["None", "OpenAI", "Claude", "Gemini", "Ollama", "LM Studio"])
        self.llm_provider_combo.currentTextChanged.connect(self.on_llm_provider_changed)
        llm_layout.addWidget(self.llm_provider_combo)
        
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setEnabled(False)
        # Set minimum width to ensure model names are fully visible
        self.llm_model_combo.setMinimumWidth(250)
        self.llm_model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        llm_layout.addWidget(self.llm_model_combo)
        
        self.prompt_style_combo = QComboBox()
        self.prompt_style_combo.addItems(["Cinematic", "Artistic", "Photorealistic", "Animated", "Documentary", "Abstract"])
        llm_layout.addWidget(self.prompt_style_combo)
        
        llm_layout.addStretch()
        layout.addLayout(llm_layout)
        
        # Image provider
        img_layout = QHBoxLayout()
        img_layout.addWidget(QLabel("Image Provider:"))
        self.img_provider_combo = QComboBox()
        self.img_provider_combo.addItems(["Gemini", "OpenAI", "Stability", "Local SD"])
        self.img_provider_combo.currentTextChanged.connect(self.on_img_provider_changed)
        img_layout.addWidget(self.img_provider_combo)
        
        self.img_model_combo = QComboBox()
        # Set minimum width for image model combo too
        self.img_model_combo.setMinimumWidth(250)
        self.img_model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        img_layout.addWidget(self.img_model_combo)
        
        img_layout.addWidget(QLabel("Variants:"))
        self.variants_spin = QSpinBox()
        self.variants_spin.setRange(1, 4)
        self.variants_spin.setValue(3)
        img_layout.addWidget(self.variants_spin)
        
        img_layout.addStretch()
        layout.addLayout(img_layout)
        
        # Style settings
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Aspect Ratio:"))
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["16:9", "9:16", "1:1", "4:3"])
        style_layout.addWidget(self.aspect_combo)
        
        style_layout.addWidget(QLabel("Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["720p", "1080p", "4K"])
        self.resolution_combo.setCurrentIndex(1)
        style_layout.addWidget(self.resolution_combo)
        
        style_layout.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(-1, 999999)
        self.seed_spin.setValue(-1)
        self.seed_spin.setSpecialValueText("Random")
        style_layout.addWidget(self.seed_spin)
        
        style_layout.addStretch()
        layout.addLayout(style_layout)
        
        # Negative prompt
        neg_layout = QHBoxLayout()
        neg_layout.addWidget(QLabel("Negative:"))
        self.negative_prompt = QLineEdit()
        self.negative_prompt.setPlaceholderText("Things to avoid in generation...")
        neg_layout.addWidget(self.negative_prompt)
        layout.addLayout(neg_layout)
        
        group.setLayout(layout)
        
        # Initialize the model combos with default selections
        self.on_img_provider_changed(self.img_provider_combo.currentText())
        
        return group
    
    def create_audio_panel(self) -> QWidget:
        """Create audio and MIDI settings panel"""
        group = QGroupBox("Audio & MIDI")
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        # Audio file selection
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(QLabel("Audio:"))
        self.audio_file_label = QLabel("No file")
        self.audio_file_label.setMinimumWidth(150)
        audio_layout.addWidget(self.audio_file_label)
        
        self.browse_audio_btn = QPushButton("Browse...")
        self.browse_audio_btn.clicked.connect(self.browse_audio_file)
        audio_layout.addWidget(self.browse_audio_btn)
        
        self.clear_audio_btn = QPushButton("Clear")
        self.clear_audio_btn.clicked.connect(self.clear_audio)
        self.clear_audio_btn.setEnabled(False)
        audio_layout.addWidget(self.clear_audio_btn)
        
        layout.addLayout(audio_layout)
        
        # MIDI file selection
        midi_layout = QHBoxLayout()
        midi_layout.addWidget(QLabel("MIDI:"))
        self.midi_file_label = QLabel("No file")
        self.midi_file_label.setMinimumWidth(150)
        midi_layout.addWidget(self.midi_file_label)
        
        self.browse_midi_btn = QPushButton("Browse...")
        self.browse_midi_btn.clicked.connect(self.browse_midi_file)
        midi_layout.addWidget(self.browse_midi_btn)
        
        self.clear_midi_btn = QPushButton("Clear")
        self.clear_midi_btn.clicked.connect(self.clear_midi)
        self.clear_midi_btn.setEnabled(False)
        midi_layout.addWidget(self.clear_midi_btn)
        
        self.midi_info_label = QLabel("")
        self.midi_info_label.setStyleSheet("color: #666; font-size: 10pt;")
        midi_layout.addWidget(self.midi_info_label)
        
        layout.addLayout(midi_layout)
        
        # MIDI Sync controls
        sync_layout = QHBoxLayout()
        sync_layout.addWidget(QLabel("Sync:"))
        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItems(["None", "Beat", "Measure", "Section"])
        self.sync_mode_combo.setEnabled(False)
        sync_layout.addWidget(self.sync_mode_combo)
        
        sync_layout.addWidget(QLabel("Snap:"))
        self.snap_strength_slider = QSlider(Qt.Horizontal)
        self.snap_strength_slider.setRange(0, 100)
        self.snap_strength_slider.setValue(80)
        self.snap_strength_slider.setMaximumWidth(100)
        self.snap_strength_slider.setEnabled(False)
        sync_layout.addWidget(self.snap_strength_slider)
        
        self.snap_label = QLabel("80%")
        self.snap_strength_slider.valueChanged.connect(lambda v: self.snap_label.setText(f"{v}%"))
        sync_layout.addWidget(self.snap_label)
        
        self.extract_lyrics_btn = QPushButton("Extract Lyrics")
        self.extract_lyrics_btn.clicked.connect(self.extract_midi_lyrics)
        self.extract_lyrics_btn.setEnabled(False)
        sync_layout.addWidget(self.extract_lyrics_btn)
        
        sync_layout.addStretch()
        layout.addLayout(sync_layout)
        
        # Audio controls
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setMaximumWidth(100)
        controls_layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("80%")
        self.volume_slider.valueChanged.connect(lambda v: self.volume_label.setText(f"{v}%"))
        controls_layout.addWidget(self.volume_label)
        
        controls_layout.addWidget(QLabel("Fade In:"))
        self.fade_in_spin = QDoubleSpinBox()
        self.fade_in_spin.setRange(0, 5)
        self.fade_in_spin.setValue(0)
        self.fade_in_spin.setSuffix(" s")
        controls_layout.addWidget(self.fade_in_spin)
        
        controls_layout.addWidget(QLabel("Fade Out:"))
        self.fade_out_spin = QDoubleSpinBox()
        self.fade_out_spin.setRange(0, 5)
        self.fade_out_spin.setValue(0)
        self.fade_out_spin.setSuffix(" s")
        controls_layout.addWidget(self.fade_out_spin)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Karaoke options (hidden by default)
        self.karaoke_group = QGroupBox("Karaoke Options")
        self.karaoke_group.setCheckable(True)
        self.karaoke_group.setChecked(False)
        self.karaoke_group.setVisible(False)
        karaoke_layout = QVBoxLayout()
        
        karaoke_style_layout = QHBoxLayout()
        karaoke_style_layout.addWidget(QLabel("Style:"))
        self.karaoke_style_combo = QComboBox()
        self.karaoke_style_combo.addItems(["Bouncing Ball", "Highlight", "Fade In"])
        karaoke_style_layout.addWidget(self.karaoke_style_combo)
        
        karaoke_style_layout.addWidget(QLabel("Position:"))
        self.karaoke_position_combo = QComboBox()
        self.karaoke_position_combo.addItems(["Bottom", "Top", "Center"])
        karaoke_style_layout.addWidget(self.karaoke_position_combo)
        
        karaoke_style_layout.addWidget(QLabel("Font Size:"))
        self.karaoke_font_spin = QSpinBox()
        self.karaoke_font_spin.setRange(16, 72)
        self.karaoke_font_spin.setValue(32)
        karaoke_style_layout.addWidget(self.karaoke_font_spin)
        
        karaoke_style_layout.addStretch()
        karaoke_layout.addLayout(karaoke_style_layout)
        
        # Export formats
        export_layout = QHBoxLayout()
        export_layout.addWidget(QLabel("Export:"))
        self.export_lrc_check = QCheckBox("LRC")
        self.export_lrc_check.setChecked(True)
        export_layout.addWidget(self.export_lrc_check)
        
        self.export_srt_check = QCheckBox("SRT")
        self.export_srt_check.setChecked(True)
        export_layout.addWidget(self.export_srt_check)
        
        self.export_ass_check = QCheckBox("ASS")
        export_layout.addWidget(self.export_ass_check)
        
        export_layout.addStretch()
        karaoke_layout.addLayout(export_layout)
        
        self.karaoke_group.setLayout(karaoke_layout)
        layout.addWidget(self.karaoke_group)
        
        group.setLayout(layout)
        return group
    
    def create_storyboard_panel(self) -> QWidget:
        """Create storyboard panel with scene table"""
        group = QGroupBox("Storyboard")
        layout = QVBoxLayout()
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.enhance_prompts_btn = QPushButton("Enhance All Prompts")
        self.enhance_prompts_btn.clicked.connect(self.enhance_all_prompts)
        self.enhance_prompts_btn.setEnabled(False)
        controls_layout.addWidget(self.enhance_prompts_btn)
        
        self.generate_images_btn = QPushButton("Generate Images")
        self.generate_images_btn.clicked.connect(self.generate_images)
        self.generate_images_btn.setEnabled(False)
        controls_layout.addWidget(self.generate_images_btn)
        
        controls_layout.addStretch()
        
        self.total_duration_label = QLabel("Total: 0:00")
        controls_layout.addWidget(self.total_duration_label)
        
        layout.addLayout(controls_layout)
        
        # Scene table
        self.scene_table = QTableWidget()
        self.scene_table.setColumnCount(6)
        self.scene_table.setHorizontalHeaderLabels([
            "Scene", "Source", "Duration", "Prompt", "Images", "Status"
        ])
        
        # Configure columns
        header = self.scene_table.horizontalHeader()
        header.resizeSection(0, 60)   # Scene
        header.resizeSection(1, 150)  # Source
        header.resizeSection(2, 80)   # Duration
        header.setStretchLastSection(False)
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Prompt stretches
        header.resizeSection(4, 80)   # Images
        header.resizeSection(5, 80)   # Status
        
        layout.addWidget(self.scene_table)
        
        group.setLayout(layout)
        return group
    
    def create_export_panel(self) -> QWidget:
        """Create export/render panel"""
        group = QGroupBox("Video Export")
        layout = QVBoxLayout()
        
        # Video provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Render Method:"))
        self.video_provider_combo = QComboBox()
        self.video_provider_combo.addItems(["FFmpeg Slideshow", "Gemini Veo"])
        self.video_provider_combo.currentTextChanged.connect(self.on_video_provider_changed)
        provider_layout.addWidget(self.video_provider_combo)
        
        self.veo_model_combo = QComboBox()
        self.veo_model_combo.addItems(["veo-3.0-generate-001", "veo-3.0-fast-generate-001", "veo-2.0-generate-001"])
        self.veo_model_combo.setVisible(False)
        # Set minimum width for Veo model combo
        self.veo_model_combo.setMinimumWidth(250)
        self.veo_model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        provider_layout.addWidget(self.veo_model_combo)
        
        provider_layout.addStretch()
        layout.addLayout(provider_layout)
        
        # Export settings
        export_layout = QHBoxLayout()
        
        self.ken_burns_check = QCheckBox("Ken Burns Effect")
        self.ken_burns_check.setChecked(True)
        export_layout.addWidget(self.ken_burns_check)
        
        self.transitions_check = QCheckBox("Transitions")
        self.transitions_check.setChecked(True)
        export_layout.addWidget(self.transitions_check)
        
        self.captions_check = QCheckBox("Captions")
        export_layout.addWidget(self.captions_check)
        
        export_layout.addStretch()
        layout.addLayout(export_layout)
        
        # Export buttons
        button_layout = QHBoxLayout()
        
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview_video)
        self.preview_btn.setEnabled(False)
        button_layout.addWidget(self.preview_btn)
        
        self.render_btn = QPushButton("Render Video")
        self.render_btn.clicked.connect(self.render_video)
        self.render_btn.setEnabled(False)
        button_layout.addWidget(self.render_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group
    
    def create_status_bar(self) -> QWidget:
        """Create status bar with progress"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        
        self.cost_label = QLabel("Cost: $0.00")
        layout.addWidget(self.cost_label)
        
        widget.setLayout(layout)
        return widget
    
    # Event handlers
    def new_project(self):
        """Create a new project"""
        if self.current_project and self.current_project.is_modified:
            reply = QMessageBox.question(
                self, "Save Project",
                "Save current project before creating new?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self.save_project()
            elif reply == QMessageBox.Cancel:
                return
        
        self.current_project = VideoProject(name=self.project_name.text() or "Untitled")
        self.project_name.setText(self.current_project.name)
        self.update_ui_state()
        self.project_changed.emit(self.current_project)
    
    def auto_load_last_project(self):
        """Auto-load the last opened project if enabled"""
        from gui.video.project_browser import get_last_project_path
        
        self.logger.info("Checking for last project to auto-load...")
        last_project = get_last_project_path()
        if last_project:
            self.logger.info(f"Auto-loading last project: {last_project}")
            try:
                self.load_project_from_path(last_project)
            except Exception as e:
                self.logger.warning(f"Could not auto-load last project: {e}")
        else:
            self.logger.info("No last project to auto-load")
    
    def browse_projects(self):
        """Browse and open projects using the project browser"""
        from gui.video.project_browser import ProjectBrowserDialog
        
        dialog = ProjectBrowserDialog(self.project_manager, self)
        dialog.project_selected.connect(self.load_project_from_path)
        dialog.exec()
    
    def load_project_from_path(self, project_path):
        """Load a project from a given path"""
        try:
            self.current_project = self.project_manager.load_project(project_path)
            self.load_project_to_ui()
            self.update_ui_state()
            self.project_changed.emit(self.current_project)
            self.status_label.setText(f"Loaded: {self.current_project.name}")
            
            # Save as last opened project
            from PySide6.QtCore import QSettings
            settings = QSettings("ImageAI", "VideoProjects")
            settings.setValue("last_project", str(project_path))
        except Exception as e:
            self.logger.error(f"Failed to load project from {project_path}: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to open project: {e}")
    
    def open_project(self):
        """Open existing project"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Project",
            str(self.video_config.get_projects_dir()),
            "ImageAI Projects (*.iaproj.json)"
        )
        if filename:
            try:
                self.current_project = self.project_manager.load_project(Path(filename))
                self.project_name.setText(self.current_project.name)
                self.load_project_to_ui()
                self.update_ui_state()
                self.project_changed.emit(self.current_project)
            except Exception as e:
                self.logger.error(f"Failed to open project: {e}", exc_info=True)
                QMessageBox.warning(self, "Error", f"Failed to open project: {e}")
    
    def save_project(self):
        """Save current project"""
        if not self.current_project:
            # Create a new project if none exists
            project_name = self.project_name.text().strip() or "Untitled"
            self.current_project = VideoProject(name=project_name)
            self.update_ui_state()
        
        try:
            self.update_project_from_ui()
            self.project_manager.save_project(self.current_project)
            self.status_label.setText(f"Project saved: {self.current_project.name}")
            self.project_changed.emit(self.current_project)
        except Exception as e:
            self.logger.error(f"Failed to save project: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to save project: {e}")
    
    def generate_storyboard(self):
        """Generate storyboard from input text"""
        text = self.input_text.toPlainText()
        if not text:
            self.logger.warning("Generate storyboard called with no input text")
            QMessageBox.warning(self, "No Input", "Please enter text or lyrics")
            return
        
        if not self.current_project:
            self.new_project()
        
        # Generate scenes
        from core.video.storyboard import StoryboardGenerator
        generator = StoryboardGenerator()
        
        # Get format type
        format_type = self.format_combo.currentText()
        if format_type == "Auto-detect":
            format_type = None
        
        # Get target duration
        target_duration = f"00:{self.duration_spin.value():02d}:00"
        preset = self.pacing_combo.currentText().lower()
        
        # Get MIDI sync settings
        midi_timing = None
        sync_mode = "none"
        snap_strength = 0.8
        
        if self.current_project and self.current_project.midi_timing_data:
            midi_timing = self.current_project.midi_timing_data
            sync_mode = self.sync_mode_combo.currentText().lower()
            snap_strength = self.snap_strength_slider.value() / 100.0
        
        # Generate scenes with MIDI sync if available
        scenes = generator.generate_scenes(
            text,
            target_duration=target_duration,
            preset=preset,
            format_hint=format_type,
            midi_timing_data=midi_timing,
            sync_mode=sync_mode,
            snap_strength=snap_strength
        )
        
        # Update project
        self.current_project.scenes = scenes
        self.current_project.input_text = text
        self.current_project.sync_mode = sync_mode
        self.current_project.snap_strength = snap_strength
        
        # Update karaoke settings if enabled
        if self.karaoke_group.isChecked():
            from core.video.karaoke_renderer import KaraokeConfig
            self.current_project.karaoke_config = KaraokeConfig(
                enabled=True,
                style=self.karaoke_style_combo.currentText().lower().replace(" ", "_"),
                position=self.karaoke_position_combo.currentText().lower(),
                font_size=self.karaoke_font_spin.value()
            )
            
            # Set export formats
            export_formats = []
            if self.export_lrc_check.isChecked():
                export_formats.append("lrc")
            if self.export_srt_check.isChecked():
                export_formats.append("srt")
            if self.export_ass_check.isChecked():
                export_formats.append("ass")
            self.current_project.karaoke_export_formats = export_formats
        
        self.populate_scene_table()
        self.update_ui_state()
        self.project_changed.emit(self.current_project)
    
    def populate_scene_table(self):
        """Populate scene table with project scenes"""
        if not self.current_project:
            return
        
        self.scene_table.setRowCount(len(self.current_project.scenes))
        
        total_duration = 0
        for i, scene in enumerate(self.current_project.scenes):
            self.scene_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.scene_table.setItem(i, 1, QTableWidgetItem(scene.source_text[:50]))
            self.scene_table.setItem(i, 2, QTableWidgetItem(f"{scene.duration:.1f}s"))
            self.scene_table.setItem(i, 3, QTableWidgetItem(scene.prompt or ""))
            self.scene_table.setItem(i, 4, QTableWidgetItem(str(len(scene.images))))
            self.scene_table.setItem(i, 5, QTableWidgetItem("Ready" if scene.images else "Pending"))
            
            total_duration += scene.duration
        
        # Update total duration
        minutes = int(total_duration // 60)
        seconds = int(total_duration % 60)
        self.total_duration_label.setText(f"Total: {minutes}:{seconds:02d}")
    
    def enhance_all_prompts(self):
        """Request prompt enhancement"""
        self.generation_requested.emit("enhance_prompts", self.gather_generation_params())
    
    def generate_images(self):
        """Request image generation"""
        self.generation_requested.emit("generate_images", self.gather_generation_params())
    
    def preview_video(self):
        """Request video preview"""
        self.generation_requested.emit("preview_video", self.gather_generation_params())
    
    def render_video(self):
        """Request video rendering"""
        self.generation_requested.emit("render_video", self.gather_generation_params())
    
    def gather_generation_params(self) -> Dict[str, Any]:
        """Gather all generation parameters"""
        return {
            'provider': self.img_provider_combo.currentText().lower(),
            'model': self.img_model_combo.currentText(),
            'llm_provider': self.llm_provider_combo.currentText().lower(),
            'llm_model': self.llm_model_combo.currentText(),
            'prompt_style': self.prompt_style_combo.currentText(),
            'variants': self.variants_spin.value(),
            'aspect_ratio': self.aspect_combo.currentText(),
            'resolution': self.resolution_combo.currentText(),
            'seed': self.seed_spin.value() if self.seed_spin.value() >= 0 else None,
            'negative_prompt': self.negative_prompt.text(),
            'video_provider': self.video_provider_combo.currentText(),
            'veo_model': self.veo_model_combo.currentText(),
            'ken_burns': self.ken_burns_check.isChecked(),
            'transitions': self.transitions_check.isChecked(),
            'captions': self.captions_check.isChecked(),
            'google_api_key': self.config.get('google_api_key'),
            'openai_api_key': self.config.get('openai_api_key'),
            'stability_api_key': self.config.get('stability_api_key'),
        }
    
    def on_llm_provider_changed(self, provider: str):
        """Handle LLM provider change"""
        # Always clear the combo first
        self.llm_model_combo.clear()
        
        if provider == "None":
            self.llm_model_combo.setEnabled(False)
        else:
            self.llm_model_combo.setEnabled(True)
            # Populate with actual models for provider
            if provider == "OpenAI":
                self.llm_model_combo.addItems(["gpt-5", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"])
            elif provider == "Claude":
                self.llm_model_combo.addItems(["claude-opus-4.1", "claude-opus-4", "claude-sonnet-4", "claude-3.7-sonnet", "claude-3.5-sonnet", "claude-3.5-haiku"])
            elif provider == "Gemini":
                self.llm_model_combo.addItems(["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-pro"])
    
    def on_img_provider_changed(self, provider: str):
        """Handle image provider change"""
        # Clear the model combo first
        self.img_model_combo.clear()
        
        # Populate with models based on provider
        if provider == "Gemini":
            self.img_model_combo.addItems([
                "gemini-2.5-flash-image-preview",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ])
        elif provider == "OpenAI":
            self.img_model_combo.addItems([
                "dall-e-3",
                "dall-e-2"
            ])
        elif provider == "Stability":
            self.img_model_combo.addItems([
                "stable-diffusion-xl-1024-v1-0",
                "stable-diffusion-xl-1024-v0-9",
                "stable-diffusion-512-v2-1",
                "stable-diffusion-768-v2-1"
            ])
        elif provider == "Local SD":
            self.img_model_combo.addItems([
                "stabilityai/stable-diffusion-xl-base-1.0",
                "stabilityai/stable-diffusion-2-1",
                "runwayml/stable-diffusion-v1-5"
            ])
    
    def on_video_provider_changed(self, provider: str):
        """Handle video provider change"""
        self.veo_model_combo.setVisible(provider == "Gemini Veo")
    
    def load_input_file(self):
        """Load input from file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Input File",
            "", "Text Files (*.txt *.md);;All Files (*.*)"
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.input_text.setPlainText(f.read())
            except Exception as e:
                self.logger.error(f"Failed to load file: {e}", exc_info=True)
                QMessageBox.warning(self, "Error", f"Failed to load file: {e}")
    
    def browse_audio_file(self):
        """Browse for audio file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File",
            "", "Audio Files (*.mp3 *.wav *.m4a *.ogg);;All Files (*.*)"
        )
        if filename:
            self.audio_file_label.setText(Path(filename).name)
            self.clear_audio_btn.setEnabled(True)
            if self.current_project:
                from core.video.models import AudioTrack
                self.current_project.audio_track = AudioTrack(
                    file_path=filename,
                    volume=self.volume_slider.value() / 100.0,
                    fade_in=self.fade_in_spin.value(),
                    fade_out=self.fade_out_spin.value()
                )
    
    def clear_audio(self):
        """Clear audio selection"""
        self.audio_file_label.setText("No file")
        self.clear_audio_btn.setEnabled(False)
        if self.current_project:
            self.current_project.audio_tracks = []
    
    def browse_midi_file(self):
        """Browse for MIDI file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select MIDI File",
            "", "MIDI Files (*.mid *.midi);;All Files (*.*)"
        )
        if filename:
            try:
                # Process MIDI file
                from core.video.midi_utils import get_midi_processor
                processor = get_midi_processor()
                timing_data = processor.extract_timing(Path(filename))
                
                # Update UI
                self.midi_file_label.setText(Path(filename).name)
                self.midi_info_label.setText(
                    f"{timing_data.tempo_bpm:.0f} BPM, {timing_data.time_signature}, "
                    f"{timing_data.duration_sec:.1f}s"
                )
                self.clear_midi_btn.setEnabled(True)
                self.sync_mode_combo.setEnabled(True)
                self.snap_strength_slider.setEnabled(True)
                self.extract_lyrics_btn.setEnabled(True)
                self.karaoke_group.setVisible(True)
                
                # Store in project
                if self.current_project:
                    self.current_project.midi_file_path = Path(filename)
                    self.current_project.midi_timing_data = timing_data
                    
            except Exception as e:
                self.logger.error(f"Failed to process MIDI file: {e}", exc_info=True)
                QMessageBox.warning(self, "MIDI Error", f"Failed to process MIDI file: {e}")
    
    def clear_midi(self):
        """Clear MIDI file"""
        self.midi_file_label.setText("No file")
        self.midi_info_label.setText("")
        self.clear_midi_btn.setEnabled(False)
        self.sync_mode_combo.setEnabled(False)
        self.snap_strength_slider.setEnabled(False)
        self.extract_lyrics_btn.setEnabled(False)
        self.karaoke_group.setVisible(False)
        
        if self.current_project:
            self.current_project.midi_file_path = None
            self.current_project.midi_timing_data = None
    
    def extract_midi_lyrics(self):
        """Extract lyrics from MIDI or align to timing"""
        if not self.current_project or not self.current_project.midi_timing_data:
            return
        
        # Get lyrics from MIDI timing data
        midi_lyrics = self.current_project.midi_timing_data.lyrics
        
        if midi_lyrics:
            # Format as text and insert into input
            lyrics_text = "\n".join([text for _, text in midi_lyrics])
            self.input_text.setPlainText(lyrics_text)
            QMessageBox.information(self, "Lyrics Extracted", 
                                  f"Extracted {len(midi_lyrics)} lyric events from MIDI")
        else:
            # Try to align existing text to MIDI timing
            text = self.input_text.toPlainText()
            if text:
                try:
                    from core.video.midi_utils import get_midi_processor
                    processor = get_midi_processor()
                    aligned = processor._align_lyrics_to_timing(
                        text, self.current_project.midi_timing_data
                    )
                    if aligned:
                        QMessageBox.information(self, "Lyrics Aligned",
                                          f"Aligned {len(aligned)} words to MIDI timing")
                except Exception as e:
                    self.logger.error(f"MIDI lyrics alignment error: {e}", exc_info=True)
                    QMessageBox.warning(self, "MIDI Error", str(e))
            else:
                QMessageBox.information(self, "No Lyrics",
                                      "No lyrics found in MIDI. Enter lyrics manually to align to beats.")
    
    def update_ui_state(self):
        """Update UI element states based on project"""
        has_project = self.current_project is not None
        has_scenes = has_project and len(self.current_project.scenes) > 0
        has_images = has_scenes and any(s.images for s in self.current_project.scenes)
        
        self.save_btn.setEnabled(has_project)
        self.generate_storyboard_btn.setEnabled(True)
        self.enhance_prompts_btn.setEnabled(has_scenes)
        self.generate_images_btn.setEnabled(has_scenes)
        self.preview_btn.setEnabled(has_images)
        self.render_btn.setEnabled(has_images)
    
    def update_project_from_ui(self):
        """Update project from UI values"""
        if not self.current_project:
            return
        
        self.current_project.name = self.project_name.text()
        self.current_project.input_text = self.input_text.toPlainText()
        self.current_project.input_format = self.format_combo.currentText()
        self.current_project.timing_preset = self.pacing_combo.currentText()
        
        # Update target duration from spin box
        duration_sec = self.duration_spin.value()
        hours = duration_sec // 3600
        minutes = (duration_sec % 3600) // 60
        seconds = duration_sec % 60
        self.current_project.target_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
    def load_project_to_ui(self):
        """Load project data to UI"""
        if not self.current_project:
            return
        
        try:
            # Load basic project info
            self.project_name.setText(self.current_project.name)
            self.input_text.setPlainText(self.current_project.input_text or "")
            
            # Load format and timing settings
            if hasattr(self.current_project, 'input_format'):
                index = self.format_combo.findText(self.current_project.input_format)
                if index >= 0:
                    self.format_combo.setCurrentIndex(index)
            
            if hasattr(self.current_project, 'timing_preset'):
                index = self.pacing_combo.findText(self.current_project.timing_preset)
                if index >= 0:
                    self.pacing_combo.setCurrentIndex(index)
            
            # Load target duration
            if self.current_project.target_duration:
                try:
                    parts = self.current_project.target_duration.split(':')
                    if len(parts) == 3:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        seconds = int(parts[2])
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        self.duration_spin.setValue(total_seconds)
                except Exception as e:
                    self.logger.warning(f"Could not parse target duration: {e}")
            
            # Load scene table
            self.populate_scene_table()
            
            # Update UI state
            self.update_ui_state()
            
        except Exception as e:
            self.logger.error(f"Error loading project to UI: {e}", exc_info=True)
            QMessageBox.warning(self, "Load Error", 
                              f"Some project data could not be loaded.\nCheck logs for details.\nError: {e}")