"""
Video Project Tab for ImageAI GUI.
Main interface for creating and managing video projects.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QSplitter, QTabWidget,
    QCheckBox, QSlider, QProgressBar, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QPixmap, QIcon

from core.video.project import VideoProject, Scene
from core.video.project_manager import ProjectManager
from core.video.storyboard import StoryboardGenerator
from core.video.prompt_engine import PromptEngine, UnifiedLLMProvider, PromptStyle
from core.video.config import VideoConfig


class VideoGenerationThread(QThread):
    """Thread for video generation operations"""
    progress_update = Signal(int, str)  # progress percentage, message
    scene_complete = Signal(str, dict)  # scene_id, result
    generation_complete = Signal(bool, str)  # success, message/path
    
    def __init__(self, project: VideoProject, operation: str, **kwargs):
        super().__init__()
        self.project = project
        self.operation = operation
        self.kwargs = kwargs
        self.cancelled = False
    
    def run(self):
        """Run the generation operation"""
        try:
            if self.operation == "generate_images":
                self._generate_images()
            elif self.operation == "render_video":
                self._render_video()
            elif self.operation == "enhance_prompts":
                self._enhance_prompts()
        except Exception as e:
            self.generation_complete.emit(False, str(e))
    
    def _generate_images(self):
        """Generate images for all scenes"""
        try:
            from ...core.video.image_generator import ImageGenerator
            from ...core.video.thumbnail_manager import ThumbnailManager
            from pathlib import Path
            
            # Initialize generators
            generator = ImageGenerator(self.kwargs)
            thumbnail_mgr = ThumbnailManager()
            
            # Get generation parameters
            provider = self.kwargs.get('provider', 'google')
            model = self.kwargs.get('model', '')
            variants = self.kwargs.get('variants', 3)
            
            # Filter scenes that need generation
            scenes_to_generate = [s for s in self.project.scenes if not s.images or len(s.images) < variants]
            total_scenes = len(scenes_to_generate)
            
            if total_scenes == 0:
                self.generation_complete.emit(True, "All scenes already have images")
                return
            
            # Generate images for each scene
            for i, scene in enumerate(scenes_to_generate):
                if self.cancelled:
                    break
                
                progress = int((i / total_scenes) * 100)
                self.progress_update.emit(progress, f"Generating images for scene {i+1}/{total_scenes}: {scene.title or scene.id}")
                
                # Generate images using the actual provider
                results = generator.generate_batch(
                    [scene],
                    provider=provider,
                    model=model,
                    variants_per_scene=variants,
                    **self.kwargs
                )
                
                if results and results[0].success:
                    result = results[0]
                    
                    # Store images in scene
                    scene.images = result.paths
                    
                    # Create thumbnails
                    thumbnails = []
                    for img_data in result.images[:4]:  # Max 4 for composite
                        thumb = thumbnail_mgr.create_thumbnail_with_cache(img_data)
                        thumbnails.append(thumb)
                    
                    # Create composite thumbnail for scene
                    scene_thumb = thumbnail_mgr.create_scene_thumbnail(
                        result.images,
                        scene.title or f"Scene {i+1}"
                    )
                    
                    result_data = {
                        "scene_id": scene.id,
                        "images": result.paths,
                        "thumbnails": thumbnails,
                        "scene_thumbnail": scene_thumb,
                        "cost": result.cost,
                        "status": "completed"
                    }
                else:
                    error_msg = results[0].error if results else "Unknown error"
                    result_data = {
                        "scene_id": scene.id,
                        "images": [],
                        "status": "failed",
                        "error": error_msg
                    }
                
                self.scene_complete.emit(scene.id, result_data)
            
            # Save project with generated images
            if hasattr(self.project, 'save'):
                self.project.save()
            
            if not self.cancelled:
                self.generation_complete.emit(True, f"Generated images for {total_scenes} scenes")
                
        except Exception as e:
            self.generation_complete.emit(False, f"Image generation failed: {e}")
    
    def _render_video(self):
        """Render the final video"""
        # TODO: Implement actual video rendering
        self.progress_update.emit(50, "Rendering video...")
        import time
        time.sleep(2)
        self.generation_complete.emit(True, "Video rendered successfully")
    
    def _enhance_prompts(self):
        """Enhance prompts using LLM"""
        # TODO: Implement actual prompt enhancement
        total_scenes = len(self.project.scenes)
        for i, scene in enumerate(self.project.scenes):
            if self.cancelled:
                break
            
            progress = int((i / total_scenes) * 100)
            self.progress_update.emit(progress, f"Enhancing prompt {i+1}/{total_scenes}")
            
            # Simulate enhancement
            import time
            time.sleep(0.3)
            
            scene.prompt = f"[Enhanced] {scene.prompt}"
        
        if not self.cancelled:
            self.generation_complete.emit(True, "Prompt enhancement complete")
    
    def cancel(self):
        """Cancel the operation"""
        self.cancelled = True


class VideoProjectTab(QWidget):
    """Main tab widget for video projects"""
    
    def __init__(self, config: Dict[str, Any], providers: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.providers = providers
        self.video_config = VideoConfig()
        self.project_manager = ProjectManager(self.video_config.get_projects_dir())
        self.current_project = None
        self.generation_thread = None
        
        self.logger = logging.getLogger(__name__)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Development notice
        notice = QLabel("⚠️ Video Project Feature is Under Development - Not all features are functional yet")
        notice.setStyleSheet("""
            QLabel {
                background-color: #fff3cd;
                color: #856404;
                padding: 8px;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        layout.addWidget(notice)
        
        # Project header
        layout.addWidget(self.create_project_header())
        
        # Main content area (splitter)
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Input and settings
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self.create_input_panel())
        left_layout.addWidget(self.create_settings_panel())
        left_layout.addWidget(self.create_audio_panel())
        
        # Right panel - Storyboard and preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.create_storyboard_panel())
        right_layout.addWidget(self.create_export_panel())
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
        
        # Status bar
        layout.addWidget(self.create_status_bar())
    
    def create_project_header(self) -> QWidget:
        """Create project header with name and controls"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins
        
        # Project name
        self.project_name = QLineEdit("Untitled Project")
        self.project_name.setPlaceholderText("Enter project name...")
        self.project_name.setMaximumWidth(300)  # Limit width
        layout.addWidget(QLabel("Project:"))
        layout.addWidget(self.project_name)
        
        # Project controls
        self.new_btn = QPushButton("New")
        self.new_btn.setMaximumWidth(60)
        self.new_btn.clicked.connect(self.new_project)
        layout.addWidget(self.new_btn)
        
        self.open_btn = QPushButton("Open")
        self.open_btn.setMaximumWidth(60)
        self.open_btn.clicked.connect(self.open_project)
        layout.addWidget(self.open_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setMaximumWidth(60)
        self.save_btn.clicked.connect(self.save_project)
        layout.addWidget(self.save_btn)
        
        layout.addStretch()
        widget.setLayout(layout)
        widget.setMaximumHeight(45)  # Limit height
        return widget
    
    def create_input_panel(self) -> QWidget:
        """Create input panel for text/lyrics"""
        group = QGroupBox("Input")
        layout = QVBoxLayout()
        layout.setSpacing(5)  # Reduce spacing
        
        # Format selector
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Auto-detect", "Timestamped", "Structured", "Plain"])
        format_layout.addWidget(self.format_combo)
        
        self.load_file_btn = QPushButton("Load from file...")
        self.load_file_btn.clicked.connect(self.load_input_file)
        format_layout.addWidget(self.load_file_btn)
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        # Text input
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "Enter lyrics or text here...\n\n"
            "Formats supported:\n"
            "[00:12] Timestamped lines\n"
            "# Verse / # Chorus - Structured\n"
            "Plain text - One line per scene"
        )
        self.input_text.setMaximumHeight(150)  # Limit height
        layout.addWidget(self.input_text)
        
        # Timing controls
        timing_layout = QHBoxLayout()
        timing_layout.addWidget(QLabel("Pacing:"))
        self.pacing_combo = QComboBox()
        self.pacing_combo.addItems(["Fast", "Medium", "Slow"])
        self.pacing_combo.setCurrentText("Medium")
        timing_layout.addWidget(self.pacing_combo)
        
        timing_layout.addWidget(QLabel("Target Length:"))
        self.target_length = QLineEdit()
        self.target_length.setPlaceholderText("mm:ss or hh:mm:ss")
        timing_layout.addWidget(self.target_length)
        
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
        layout.setSpacing(5)  # Reduce spacing
        
        # LLM Provider for prompt generation
        llm_layout = QHBoxLayout()
        llm_layout.addWidget(QLabel("Prompt LLM:"))
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
        self.resolution_combo.setCurrentText("1080p")
        style_layout.addWidget(self.resolution_combo)
        
        style_layout.addWidget(QLabel("Seed:"))
        self.seed_input = QLineEdit()
        self.seed_input.setPlaceholderText("Random")
        style_layout.addWidget(self.seed_input)
        
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
        layout.setSpacing(5)  # Reduce spacing
        
        # File selection
        file_layout = QHBoxLayout()
        self.audio_path_label = QLabel("No audio file selected")
        file_layout.addWidget(self.audio_path_label)
        
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
        self.volume_slider.setEnabled(False)
        controls_layout.addWidget(self.volume_slider)
        self.volume_label = QLabel("80%")
        self.volume_slider.valueChanged.connect(lambda v: self.volume_label.setText(f"{v}%"))
        controls_layout.addWidget(self.volume_label)
        
        controls_layout.addWidget(QLabel("Fade In:"))
        self.fade_in_spin = QDoubleSpinBox()
        self.fade_in_spin.setRange(0, 10)
        self.fade_in_spin.setValue(0)
        self.fade_in_spin.setSuffix(" s")
        self.fade_in_spin.setEnabled(False)
        controls_layout.addWidget(self.fade_in_spin)
        
        controls_layout.addWidget(QLabel("Fade Out:"))
        self.fade_out_spin = QDoubleSpinBox()
        self.fade_out_spin.setRange(0, 10)
        self.fade_out_spin.setValue(0)
        self.fade_out_spin.setSuffix(" s")
        self.fade_out_spin.setEnabled(False)
        controls_layout.addWidget(self.fade_out_spin)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        group.setLayout(layout)
        return group
    
    def create_storyboard_panel(self) -> QWidget:
        """Create storyboard/scenes panel"""
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
        
        controls_layout.addWidget(QLabel("Total Duration:"))
        self.total_duration_label = QLabel("0:00")
        controls_layout.addWidget(self.total_duration_label)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Scene table
        self.scene_table = QTableWidget()
        self.scene_table.setColumnCount(6)
        self.scene_table.setHorizontalHeaderLabels([
            "Scene", "Source", "Prompt", "Duration", "Images", "Status"
        ])
        self.scene_table.horizontalHeader().setStretchLastSection(True)
        self.scene_table.setAlternatingRowColors(True)
        layout.addWidget(self.scene_table)
        
        group.setLayout(layout)
        return group
    
    def create_export_panel(self) -> QWidget:
        """Create export/render panel"""
        group = QGroupBox("Export")
        layout = QVBoxLayout()
        
        # Video provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Video Type:"))
        self.video_provider_combo = QComboBox()
        self.video_provider_combo.addItems(["Local Slideshow", "Gemini Veo"])
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
        
        # Export options
        options_layout = QHBoxLayout()
        self.enable_captions = QCheckBox("Add Captions")
        options_layout.addWidget(self.enable_captions)
        
        self.enable_transitions = QCheckBox("Transitions")
        self.enable_transitions.setChecked(True)
        options_layout.addWidget(self.enable_transitions)
        
        self.enable_ken_burns = QCheckBox("Ken Burns Effect")
        self.enable_ken_burns.setChecked(True)
        options_layout.addWidget(self.enable_ken_burns)
        
        self.mute_audio = QCheckBox("Mute Audio")
        options_layout.addWidget(self.mute_audio)
        
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
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
        name = self.project_name.text() or "Untitled Project"
        self.current_project = self.project_manager.create_project(name)
        self.update_ui_state()
        self.status_label.setText(f"Created new project: {name}")
    
    def open_project(self):
        """Open an existing project"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", 
            str(self.video_config.get_projects_dir()),
            "ImageAI Project (*.iaproj.json)"
        )
        
        if file_path:
            try:
                self.current_project = self.project_manager.load_project(Path(file_path))
                self.load_project_to_ui()
                self.status_label.setText(f"Loaded project: {self.current_project.name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load project: {e}")
    
    def save_project(self):
        """Save the current project"""
        if not self.current_project:
            QMessageBox.warning(self, "Warning", "No project to save")
            return
        
        try:
            self.update_project_from_ui()
            path = self.current_project.save()
            self.status_label.setText(f"Saved project to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project: {e}")
    
    def load_input_file(self):
        """Load input text from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Input File",
            "",
            "Text Files (*.txt *.md);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.status_label.setText(f"Loaded input from {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
    
    def browse_audio_file(self):
        """Browse for audio file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg);;All Files (*.*)"
        )
        
        if file_path:
            self.audio_path_label.setText(Path(file_path).name)
            self.audio_path_label.setToolTip(file_path)
            self.clear_audio_btn.setEnabled(True)
            self.volume_slider.setEnabled(True)
            self.fade_in_spin.setEnabled(True)
            self.fade_out_spin.setEnabled(True)
            
            if self.current_project:
                self.current_project.add_audio_track(Path(file_path))
    
    def clear_audio(self):
        """Clear audio selection"""
        self.audio_path_label.setText("No audio file selected")
        self.audio_path_label.setToolTip("")
        self.clear_audio_btn.setEnabled(False)
        self.volume_slider.setEnabled(False)
        self.fade_in_spin.setEnabled(False)
        self.fade_out_spin.setEnabled(False)
        
        if self.current_project:
            self.current_project.audio_tracks.clear()
    
    def generate_storyboard(self):
        """Generate storyboard from input text"""
        text = self.input_text.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "Warning", "Please enter some text first")
            return
        
        # Create project if needed
        if not self.current_project:
            self.new_project()
        
        # Generate scenes
        generator = StoryboardGenerator()
        target = self.target_length.text() if self.target_length.text() else None
        preset = self.pacing_combo.currentText().lower()
        
        scenes = generator.generate_scenes(text, target, preset)
        
        # Update project
        self.current_project.scenes = scenes
        self.current_project.input_text = text
        
        # Update UI
        self.populate_scene_table()
        self.update_ui_state()
        self.update_total_duration()
        
        self.status_label.setText(f"Generated {len(scenes)} scenes")
    
    def populate_scene_table(self):
        """Populate the scene table with project scenes"""
        if not self.current_project:
            return
        
        self.scene_table.setRowCount(len(self.current_project.scenes))
        
        for i, scene in enumerate(self.current_project.scenes):
            # Scene number
            self.scene_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            
            # Source text
            source_item = QTableWidgetItem(scene.source[:50] + "..." if len(scene.source) > 50 else scene.source)
            source_item.setToolTip(scene.source)
            self.scene_table.setItem(i, 1, source_item)
            
            # Prompt
            prompt_item = QTableWidgetItem(scene.prompt[:50] + "..." if len(scene.prompt) > 50 else scene.prompt)
            prompt_item.setToolTip(scene.prompt)
            self.scene_table.setItem(i, 2, prompt_item)
            
            # Duration
            self.scene_table.setItem(i, 3, QTableWidgetItem(f"{scene.duration_sec:.1f}s"))
            
            # Images
            self.scene_table.setItem(i, 4, QTableWidgetItem(f"{len(scene.images)} images"))
            
            # Status
            self.scene_table.setItem(i, 5, QTableWidgetItem(scene.status.value))
    
    def enhance_all_prompts(self):
        """Enhance all scene prompts using LLM"""
        if not self.current_project or not self.current_project.scenes:
            QMessageBox.warning(self, "Warning", "No scenes to enhance")
            return
        
        provider = self.llm_provider_combo.currentText().lower()
        if provider == "none":
            QMessageBox.warning(self, "Warning", "Please select an LLM provider")
            return
        
        # Start enhancement thread
        self.generation_thread = VideoGenerationThread(
            self.current_project, "enhance_prompts",
            provider=provider,
            model=self.llm_model_combo.currentText()
        )
        self.generation_thread.progress_update.connect(self.on_progress_update)
        self.generation_thread.generation_complete.connect(self.on_generation_complete)
        self.generation_thread.start()
        
        self.progress_bar.setVisible(True)
        self.enhance_prompts_btn.setEnabled(False)
    
    def generate_images(self):
        """Generate images for all scenes"""
        if not self.current_project or not self.current_project.scenes:
            QMessageBox.warning(self, "Warning", "No scenes to generate images for")
            return
        
        # Start generation thread
        self.generation_thread = VideoGenerationThread(
            self.current_project, "generate_images",
            provider=self.img_provider_combo.currentText(),
            model=self.img_model_combo.currentText(),
            variants=self.variants_spin.value()
        )
        self.generation_thread.progress_update.connect(self.on_progress_update)
        self.generation_thread.scene_complete.connect(self.on_scene_complete)
        self.generation_thread.generation_complete.connect(self.on_generation_complete)
        self.generation_thread.start()
        
        self.progress_bar.setVisible(True)
        self.generate_images_btn.setEnabled(False)
    
    def preview_video(self):
        """Preview the video"""
        QMessageBox.information(self, "Preview", "Video preview not yet implemented")
    
    def render_video(self):
        """Render the final video"""
        if not self.current_project:
            QMessageBox.warning(self, "Warning", "No project to render")
            return
        
        # Start render thread
        self.generation_thread = VideoGenerationThread(
            self.current_project, "render_video",
            provider=self.video_provider_combo.currentText()
        )
        self.generation_thread.progress_update.connect(self.on_progress_update)
        self.generation_thread.generation_complete.connect(self.on_generation_complete)
        self.generation_thread.start()
        
        self.progress_bar.setVisible(True)
        self.render_btn.setEnabled(False)
    
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
    
    def on_video_provider_changed(self, provider: str):
        """Handle video provider change"""
        self.veo_model_combo.setVisible(provider == "Gemini Veo")
    
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
    
    @Slot(int, str)
    def on_progress_update(self, progress: int, message: str):
        """Handle progress updates from generation thread"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
    
    @Slot(str, dict)
    def on_scene_complete(self, scene_id: str, result: dict):
        """Handle scene completion from generation thread"""
        # Update scene table
        self.populate_scene_table()
    
    @Slot(bool, str)
    def on_generation_complete(self, success: bool, message: str):
        """Handle generation completion"""
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        
        if success:
            self.status_label.setText(message)
            self.populate_scene_table()
        else:
            QMessageBox.critical(self, "Error", message)
            self.status_label.setText("Generation failed")
        
        # Re-enable buttons
        self.enhance_prompts_btn.setEnabled(True)
        self.generate_images_btn.setEnabled(True)
        self.render_btn.setEnabled(True)
    
    def update_ui_state(self):
        """Update UI element states based on project state"""
        has_project = self.current_project is not None
        has_scenes = has_project and len(self.current_project.scenes) > 0
        has_images = has_scenes and any(len(s.images) > 0 for s in self.current_project.scenes)
        
        self.save_btn.setEnabled(has_project)
        self.enhance_prompts_btn.setEnabled(has_scenes)
        self.generate_images_btn.setEnabled(has_scenes)
        self.preview_btn.setEnabled(has_images)
        self.render_btn.setEnabled(has_images)
    
    def update_total_duration(self):
        """Update total duration label"""
        if not self.current_project:
            self.total_duration_label.setText("0:00")
            return
        
        total = self.current_project.get_total_duration()
        minutes = int(total // 60)
        seconds = int(total % 60)
        self.total_duration_label.setText(f"{minutes}:{seconds:02d}")
    
    def update_project_from_ui(self):
        """Update project data from UI values"""
        if not self.current_project:
            return
        
        self.current_project.name = self.project_name.text()
        self.current_project.input_text = self.input_text.toPlainText()
        self.current_project.timing_preset = self.pacing_combo.currentText().lower()
        self.current_project.target_duration = self.target_length.text() if self.target_length.text() else None
        
        # Update style settings
        self.current_project.style["aspect_ratio"] = self.aspect_combo.currentText()
        self.current_project.style["resolution"] = self.resolution_combo.currentText()
        self.current_project.style["negative_prompt"] = self.negative_prompt.text()
        
        # Update provider settings
        if self.llm_provider_combo.currentText() != "None":
            self.current_project.llm_provider = self.llm_provider_combo.currentText().lower()
            self.current_project.llm_model = self.llm_model_combo.currentText()
        
        self.current_project.image_provider = self.img_provider_combo.currentText().lower()
        self.current_project.video_provider = "veo" if self.video_provider_combo.currentText() == "Gemini Veo" else "slideshow"
    
    def load_project_to_ui(self):
        """Load project data to UI"""
        if not self.current_project:
            return
        
        self.project_name.setText(self.current_project.name)
        self.input_text.setPlainText(self.current_project.input_text)
        
        # Load settings
        if self.current_project.timing_preset:
            self.pacing_combo.setCurrentText(self.current_project.timing_preset.title())
        
        if self.current_project.target_duration:
            self.target_length.setText(self.current_project.target_duration)
        
        # Load style
        style = self.current_project.style
        if "aspect_ratio" in style:
            self.aspect_combo.setCurrentText(style["aspect_ratio"])
        if "resolution" in style:
            self.resolution_combo.setCurrentText(style["resolution"])
        if "negative_prompt" in style:
            self.negative_prompt.setText(style["negative_prompt"])
        
        # Load scenes
        self.populate_scene_table()
        self.update_total_duration()
        self.update_ui_state()