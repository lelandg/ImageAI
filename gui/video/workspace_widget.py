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
        group = QGroupBox("Project")
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("Name:"))
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("My Video Project")
        layout.addWidget(self.project_name)
        
        self.new_btn = QPushButton("New")
        self.new_btn.clicked.connect(self.new_project)
        layout.addWidget(self.new_btn)
        
        self.open_btn = QPushButton("Open")
        self.open_btn.clicked.connect(self.open_project)
        layout.addWidget(self.open_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_project)
        layout.addWidget(self.save_btn)
        
        group.setLayout(layout)
        return group
    
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
        """Create audio settings panel"""
        group = QGroupBox("Audio Track")
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        # File selection
        file_layout = QHBoxLayout()
        self.audio_file_label = QLabel("No audio file selected")
        file_layout.addWidget(self.audio_file_label)
        
        self.browse_audio_btn = QPushButton("Browse...")
        self.browse_audio_btn.clicked.connect(self.browse_audio_file)
        file_layout.addWidget(self.browse_audio_btn)
        
        self.clear_audio_btn = QPushButton("Clear")
        self.clear_audio_btn.clicked.connect(self.clear_audio)
        self.clear_audio_btn.setEnabled(False)
        file_layout.addWidget(self.clear_audio_btn)
        
        layout.addLayout(file_layout)
        
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
                QMessageBox.warning(self, "Error", f"Failed to open project: {e}")
    
    def save_project(self):
        """Save current project"""
        if not self.current_project:
            return
        
        try:
            self.update_project_from_ui()
            self.project_manager.save_project(self.current_project)
            self.status_label.setText(f"Project saved: {self.current_project.name}")
            self.project_changed.emit(self.current_project)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save project: {e}")
    
    def generate_storyboard(self):
        """Generate storyboard from input text"""
        text = self.input_text.toPlainText()
        if not text:
            QMessageBox.warning(self, "No Input", "Please enter text or lyrics")
            return
        
        if not self.current_project:
            self.new_project()
        
        # Generate scenes
        from core.video.storyboard import StoryboardGenerator
        generator = StoryboardGenerator()
        
        format_type = self.format_combo.currentText()
        if format_type == "Auto-detect":
            format_type = None
        
        scenes = generator.generate_storyboard(
            text,
            target_duration=self.duration_spin.value(),
            format_type=format_type
        )
        
        self.current_project.scenes = scenes
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
        self.audio_file_label.setText("No audio file selected")
        self.clear_audio_btn.setEnabled(False)
        if self.current_project:
            self.current_project.audio_track = None
    
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
        # Update other project settings from UI
        
    def load_project_to_ui(self):
        """Load project data to UI"""
        if not self.current_project:
            return
        
        self.populate_scene_table()
        # Load other project settings to UI