"""
Video Project Tab with sub-tabs for workspace and history.
Main interface for video project management in ImageAI.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QMessageBox, QTableWidgetItem
)
from PySide6.QtCore import QThread, Signal, Slot

from gui.common.dialog_manager import get_dialog_manager
from core.config import ConfigManager

from core.video.project import VideoProject
from core.video.project_manager import ProjectManager
from core.video.config import VideoConfig

# Import the workspace and history widgets
from .workspace_widget import WorkspaceWidget
from .history_tab import HistoryTab


class VideoGenerationThread(QThread):
    """Thread for video generation operations"""
    progress_update = Signal(int, str)  # progress percentage, message
    scene_complete = Signal(str, dict)  # scene_id, result
    generation_complete = Signal(bool, str)  # success, message
    
    def __init__(self, project: VideoProject, operation: str, **kwargs):
        super().__init__()
        self.project = project
        self.operation = operation
        self.kwargs = kwargs
        self.cancelled = False
    
    def run(self):
        """Run the generation operation"""
        try:
            if self.operation == "generate_storyboard":
                self._generate_storyboard()
            elif self.operation == "enhance_prompts":
                self._enhance_prompts()
            elif self.operation == "generate_images":
                self._generate_images()
            elif self.operation == "generate_video_clip":
                self._generate_video_clip()
            elif self.operation == "render_video":
                self._render_video()
            elif self.operation == "preview_video":
                self._preview_video()
        except Exception as e:
            self.generation_complete.emit(False, str(e))
    
    def _generate_storyboard(self):
        """Generate storyboard from text"""
        # Implementation moved from original file
        pass
    
    def _enhance_prompts(self):
        """Enhance prompts using LLM"""
        try:
            from core.video.prompt_engine import PromptEngine, UnifiedLLMProvider, PromptStyle
            
            # Get LLM configuration
            llm_provider = self.kwargs.get('llm_provider', 'none')
            llm_model = self.kwargs.get('llm_model', '')
            prompt_style = self.kwargs.get('prompt_style', 'Cinematic')
            
            if llm_provider == 'none':
                self.generation_complete.emit(False, "Please select an LLM provider")
                return
            
            # Initialize LLM provider
            llm_config = {
                'openai_api_key': self.kwargs.get('openai_api_key'),
                'anthropic_api_key': self.kwargs.get('anthropic_api_key'),
                'google_api_key': self.kwargs.get('google_api_key'),
            }
            
            llm = UnifiedLLMProvider(llm_config)
            engine = PromptEngine(llm_provider=llm)
            
            # Map style string to enum
            style_map = {
                'Cinematic': PromptStyle.CINEMATIC,
                'Artistic': PromptStyle.ARTISTIC,
                'Photorealistic': PromptStyle.PHOTOREALISTIC,
                'Animated': PromptStyle.ANIMATED,
                'Documentary': PromptStyle.DOCUMENTARY,
                'Abstract': PromptStyle.ABSTRACT,
                'Noir': PromptStyle.NOIR,
                'Fantasy': PromptStyle.FANTASY,
                'Sci-Fi': PromptStyle.SCIFI,
                'Vintage': PromptStyle.VINTAGE,
                'Minimalist': PromptStyle.MINIMALIST,
                'Dramatic': PromptStyle.DRAMATIC
            }
            style = style_map.get(prompt_style, PromptStyle.CINEMATIC)
            
            # Enhance prompts for each scene
            total_scenes = len(self.project.scenes)
            for i, scene in enumerate(self.project.scenes):
                if self.cancelled:
                    break

                progress = int((i / total_scenes) * 100)
                scene_preview = scene.source[:40] + "..." if len(scene.source) > 40 else scene.source
                self.progress_update.emit(progress, f"Scene {i+1}/{total_scenes}: '{scene_preview}' - Enhancing...")

                # Generate enhanced prompt using the engine (not llm directly)
                enhanced = engine.enhance_prompt(
                    scene.source,
                    provider=llm_provider,
                    model=llm_model,
                    style=style
                )

                scene.prompt = enhanced
                self.progress_update.emit(progress, f"Scene {i+1}/{total_scenes}: '{scene_preview}' - ✓ Complete")
            
            if not self.cancelled:
                self.generation_complete.emit(True, "Prompt enhancement complete")
                
        except Exception as e:
            self.generation_complete.emit(False, f"Prompt enhancement failed: {e}")
    
    def _generate_images(self):
        """Generate images for all scenes"""
        try:
            from core.config import ConfigManager
            from providers import get_provider
            from core.video.thumbnail_manager import ThumbnailManager
            from pathlib import Path
            from datetime import datetime
            import logging

            logger = logging.getLogger(__name__)
            thumbnail_mgr = ThumbnailManager()

            # Get generation parameters
            provider = self.kwargs.get('provider', 'google')
            model = self.kwargs.get('model', '')
            variants = self.kwargs.get('variants', 3)
            auth_mode = self.kwargs.get('auth_mode', 'api-key')

            # Get API key using ConfigManager (same as image tab)
            config = ConfigManager()
            api_key = config.get_api_key(provider) if auth_mode == "api-key" else None

            logger.info(f"Video generation - Provider: {provider}, Model: {model}, API key present: {api_key is not None}")

            # Create provider config (same as image tab)
            provider_config = {
                "api_key": api_key,
                "auth_mode": auth_mode,
            }

            # Get provider instance (disable cache to ensure fresh instance with API key)
            provider_instance = get_provider(provider, provider_config, use_cache=False)

            # Check if specific scenes were requested (single scene generation)
            scene_indices = self.kwargs.get('scene_indices', None)

            if scene_indices is not None:
                # Generate only for specific scenes
                scenes_to_generate = [self.project.scenes[i] for i in scene_indices if i < len(self.project.scenes)]
            else:
                # Filter scenes that need generation
                scenes_to_generate = [s for s in self.project.scenes if not s.images or len(s.images) < variants]

            total_scenes = len(scenes_to_generate)

            if total_scenes == 0:
                self.generation_complete.emit(True, "All scenes already have images")
                return

            # Get additional generation params
            aspect_ratio = self.kwargs.get('aspect_ratio', '16:9')
            resolution = self.kwargs.get('resolution', '1920x1080')

            # Generate images for each scene
            for i, scene in enumerate(scenes_to_generate):
                if self.cancelled:
                    break

                progress = int((i / total_scenes) * 100)
                self.progress_update.emit(progress, f"Generating images for scene {i+1}/{total_scenes}")

                # Generate images for this scene
                scene_images = []
                image_paths = []

                try:
                    for v in range(variants):
                        logger.info(f"Generating variant {v+1}/{variants} for scene {i+1}")

                        # Generate single image using provider (same as image tab)
                        texts, images = provider_instance.generate(
                            prompt=scene.prompt,
                            model=model,
                            aspect_ratio=aspect_ratio,
                            num_images=1
                        )

                        if images:
                            scene_images.extend(images)

                            # Save image to project directory
                            project_dir = Path.home() / ".imageai" / "video_projects" / self.project.name / "images"
                            project_dir.mkdir(parents=True, exist_ok=True)

                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            img_filename = f"scene_{i}_{timestamp}_v{v}.png"
                            img_path = project_dir / img_filename
                            img_path.write_bytes(images[0])
                            image_paths.append(img_path)

                    # Store images in scene as ImageVariant objects
                    from core.video.project import ImageVariant
                    scene.images = [
                        ImageVariant(
                            path=img_path,
                            provider=provider,
                            model=model,
                            cost=0.0
                        )
                        for img_path in image_paths
                    ]

                    # Create thumbnails
                    thumbnails = []
                    for img_data in scene_images[:4]:
                        thumb = thumbnail_mgr.create_thumbnail_with_cache(img_data)
                        thumbnails.append(thumb)

                    # Create composite thumbnail for scene (use source text, not title)
                    scene_thumb = thumbnail_mgr.create_scene_thumbnail(
                        scene_images,
                        scene.source[:50] if scene.source else f"Scene {i+1}"
                    )

                    result_data = {
                        "scene_id": scene.id,
                        "images": image_paths,
                        "thumbnails": thumbnails,
                        "scene_thumbnail": scene_thumb,
                        "cost": 0.0,  # TODO: Calculate cost
                        "status": "completed"
                    }

                except Exception as e:
                    logger.error(f"Failed to generate images for scene {i+1}: {e}")
                    result_data = {
                        "scene_id": scene.id,
                        "images": [],
                        "status": "failed",
                        "error": str(e)
                    }

                self.scene_complete.emit(scene.id, result_data)
            
            if not self.cancelled:
                self.generation_complete.emit(True, f"Generated images for {total_scenes} scenes")
                
        except Exception as e:
            self.generation_complete.emit(False, f"Image generation failed: {e}")

    def _generate_video_clip(self):
        """Generate video clip for a single scene using Veo"""
        try:
            from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
            from pathlib import Path
            import cv2

            # Get scene indices
            scene_indices = self.kwargs.get('scene_indices', None)
            if not scene_indices or len(scene_indices) == 0:
                self.generation_complete.emit(False, "No scene specified for video clip generation")
                return

            scene_index = scene_indices[0]
            if scene_index >= len(self.project.scenes):
                self.generation_complete.emit(False, f"Invalid scene index: {scene_index}")
                return

            scene = self.project.scenes[scene_index]

            # Get generation parameters
            seed_image_path = self.kwargs.get('seed_image')
            prompt = scene.prompt

            self.progress_update.emit(10, f"Generating video clip for scene {scene_index + 1}...")

            # Initialize Veo client
            google_api_key = self.kwargs.get('google_api_key')
            if not google_api_key:
                self.generation_complete.emit(False, "Google API key required for Veo video generation")
                return

            veo_client = VeoClient(api_key=google_api_key)

            # Configure generation
            config = VeoGenerationConfig(
                model=VeoModel.VEO_3_0,
                duration=int(scene.duration_sec),
                aspect_ratio=self.kwargs.get('aspect_ratio', '16:9')
            )

            self.progress_update.emit(20, "Submitting to Veo...")

            # Generate video with or without seed image
            if seed_image_path and Path(seed_image_path).exists():
                video_path = veo_client.generate_with_image(
                    prompt=prompt,
                    image_path=Path(seed_image_path),
                    config=config
                )
            else:
                video_path = veo_client.generate(
                    prompt=prompt,
                    config=config
                )

            self.progress_update.emit(80, "Extracting last frame...")

            # Extract last frame
            last_frame_path = self._extract_last_frame(video_path, scene_index)

            # Update scene with video clip and last frame
            scene.video_clip = video_path
            scene.last_frame = last_frame_path

            self.progress_update.emit(100, f"Video clip generated for scene {scene_index + 1}")

            # Emit scene complete with results
            result_data = {
                "scene_id": scene.id,
                "video_clip": str(video_path),
                "last_frame": str(last_frame_path),
                "status": "completed"
            }
            self.scene_complete.emit(scene.id, result_data)
            self.generation_complete.emit(True, f"Video clip generated for scene {scene_index + 1}")

        except Exception as e:
            self.generation_complete.emit(False, f"Video clip generation failed: {e}")

    def _extract_last_frame(self, video_path: Path, scene_index: int) -> Path:
        """Extract the last frame from a video clip"""
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise Exception(f"Failed to open video: {video_path}")

        # Get total frame count
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Jump to last frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)

        # Read the last frame
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise Exception("Failed to read last frame from video")

        # Save the frame
        project_dir = Path.home() / ".imageai" / "video_projects" / self.project.name
        frames_dir = project_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        frame_path = frames_dir / f"scene_{scene_index}_last_frame.png"
        cv2.imwrite(str(frame_path), frame)

        return frame_path

    def _render_video(self):
        """Render the final video"""
        try:
            from core.video.ffmpeg_renderer import FFmpegRenderer, RenderSettings
            from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
            from pathlib import Path
            
            # Determine render mode
            if self.kwargs.get('video_provider') == 'Gemini Veo':
                self._render_with_veo()
            else:
                self._render_with_ffmpeg()
                
        except Exception as e:
            self.generation_complete.emit(False, f"Video rendering failed: {e}")
    
    def _render_with_ffmpeg(self):
        """Render video using FFmpeg slideshow"""
        from core.video.ffmpeg_renderer import FFmpegRenderer, RenderSettings
        from pathlib import Path
        
        try:
            renderer = FFmpegRenderer()
            
            # Prepare render settings
            settings = RenderSettings(
                resolution="1920x1080",
                fps=24,
                aspect_ratio=self.kwargs.get('aspect_ratio', '16:9'),
                enable_ken_burns=self.kwargs.get('ken_burns', True),
                transition_duration=0.5 if self.kwargs.get('transitions', True) else 0
            )
            
            # Define output path
            project_dir = Path.home() / ".imageai" / "video_projects" / self.project.name
            project_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = project_dir / f"{self.project.name}_{timestamp}.mp4"
            
            # Progress callback
            def progress_callback(percent, status):
                self.progress_update.emit(int(percent), status)
            
            # Render the video
            self.progress_update.emit(0, "Starting video render...")
            rendered_path = renderer.render_slideshow(
                self.project,
                output_path,
                settings,
                progress_callback
            )
            
            self.generation_complete.emit(True, f"Video saved to: {rendered_path}")
            
        except Exception as e:
            self.generation_complete.emit(False, f"FFmpeg rendering failed: {e}")
    
    def _render_with_veo(self):
        """Render video using Veo API"""
        # Implementation from original file
        pass
    
    def _preview_video(self):
        """Generate preview video"""
        # Similar to render but with lower quality settings
        self._render_video()
    
    def cancel(self):
        """Cancel the operation"""
        self.cancelled = True


class VideoProjectTab(QWidget):
    """Main video project tab with sub-tabs for workspace and history"""

    # Signals
    image_provider_changed = Signal(str)  # provider name
    llm_provider_changed = Signal(str, str)  # provider name, model name
    add_to_history_signal = Signal(dict)  # history entry

    def __init__(self, config: ConfigManager, providers: Dict[str, Any]):
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
        """Initialize the user interface with sub-tabs"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Development notice
        from PySide6.QtWidgets import QLabel
        from PySide6.QtGui import QFont
        notice = QLabel("⚠️ Video features are in active development - Some features may be incomplete")
        notice.setStyleSheet("""
            QLabel {
                background-color: #fff3cd;
                color: #856404;
                padding: 5px;
                border: 1px solid #ffeeba;
                border-radius: 3px;
            }
        """)
        notice_font = QFont()
        notice_font.setPointSize(9)
        notice.setFont(notice_font)
        layout.addWidget(notice)
        
        # Create tab widget for sub-tabs
        self.tab_widget = QTabWidget()
        
        # Create workspace tab
        self.workspace_widget = WorkspaceWidget(self.config, self.providers)
        self.workspace_widget.project_changed.connect(self.on_project_changed)
        self.workspace_widget.generation_requested.connect(self.on_generation_requested)
        # Forward the image provider change signal
        if hasattr(self.workspace_widget, 'image_provider_changed'):
            self.workspace_widget.image_provider_changed.connect(lambda provider: self.on_image_provider_changed(provider))
        # Forward the LLM provider change signal
        if hasattr(self.workspace_widget, 'llm_provider_changed'):
            self.workspace_widget.llm_provider_changed.connect(lambda provider, model: self.on_llm_provider_changed(provider, model))
        self.tab_widget.addTab(self.workspace_widget, "Workspace")
        
        # Sync with any project that was already loaded during workspace init
        if self.workspace_widget.current_project:
            self.current_project = self.workspace_widget.current_project
        
        # Create history tab
        self.history_widget = HistoryTab()
        self.history_widget.restore_requested.connect(self.on_restore_requested)
        self.tab_widget.addTab(self.history_widget, "History")
        
        # Add tabs to layout
        layout.addWidget(self.tab_widget)
    
    def set_provider(self, provider_name: str):
        """Set the image provider and sync with workspace widget."""
        if hasattr(self, 'workspace_widget'):
            self.workspace_widget.set_image_provider(provider_name)

    def set_llm_provider(self, provider_name: str, model_name: str = None):
        """Set the LLM provider and sync with workspace widget."""
        if hasattr(self, 'workspace_widget'):
            self.workspace_widget.set_llm_provider(provider_name, model_name)

    def on_image_provider_changed(self, provider_name: str):
        """Handle image provider change from workspace widget."""
        # Forward the signal to the main window
        self.image_provider_changed.emit(provider_name)

    def on_llm_provider_changed(self, provider_name: str, model_name: str):
        """Handle LLM provider change from workspace widget."""
        # Forward the signal to the main window
        self.llm_provider_changed.emit(provider_name, model_name)

    def on_project_changed(self, project: VideoProject):
        """Handle project change from workspace"""
        self.current_project = project
        # Update history tab with new project
        if project and hasattr(project, 'id'):
            self.history_widget.set_project(project.id)
    
    def on_generation_requested(self, operation: str, kwargs: Dict[str, Any]):
        """Handle generation request from workspace"""
        # Get current project from workspace widget
        current_project = self.workspace_widget.current_project
        
        if not current_project and operation != "generate_storyboard":
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Project", "Please create or open a project first")
            return
        
        # For storyboard generation, create project if needed
        if operation == "generate_storyboard" and not current_project:
            self.workspace_widget.new_project()
            current_project = self.workspace_widget.current_project
        
        # Create and start generation thread
        self.generation_thread = VideoGenerationThread(
            current_project, operation, **kwargs
        )
        self.generation_thread.progress_update.connect(self.on_progress_update)
        self.generation_thread.generation_complete.connect(self.on_generation_complete)

        if operation in ["generate_images", "generate_video_clip"]:
            self.generation_thread.scene_complete.connect(self.on_scene_complete)

        self.generation_thread.start()
        
        # Update UI state
        self.workspace_widget.progress_bar.setVisible(True)
        self.workspace_widget.status_label.setText(f"Starting {operation.replace('_', ' ')}...")
    
    def on_restore_requested(self, project_id: str, timestamp: datetime):
        """Handle restore request from history tab"""
        try:
            # Rebuild project state from events
            from core.video.event_store import EventStore
            from pathlib import Path
            
            db_path = Path.home() / ".imageai" / "video_projects" / "events.db"
            event_store = EventStore(db_path)
            
            # Rebuild state up to the specified timestamp
            state = event_store.rebuild_state(project_id, until=timestamp)
            
            # Create project from state
            self.current_project = VideoProject.from_dict(state)
            
            # Update workspace
            self.workspace_widget.current_project = self.current_project
            self.workspace_widget.load_project_to_ui()
            self.workspace_widget.update_ui_state()
            
            # Switch to workspace tab
            self.tab_widget.setCurrentIndex(0)
            
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_success(
                "Restore Complete",
                f"Project restored to state at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
        except Exception as e:
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_error("Restore Failed", f"Failed to restore project: {e}")
    
    @Slot(int, str)
    def on_progress_update(self, progress: int, message: str):
        """Handle progress updates from generation thread"""
        self.workspace_widget.progress_bar.setValue(progress)
        self.workspace_widget.status_label.setText(message)
        # Also log to status console
        self.workspace_widget._log_to_console(message, "INFO")
    
    @Slot(str, dict)
    def on_scene_complete(self, scene_id: str, result: dict):
        """Handle scene completion"""
        # Update scene table with results
        if self.current_project:
            for i, scene in enumerate(self.current_project.scenes):
                if scene.id == scene_id:
                    if result.get('status') == 'completed':
                        # Handle image generation results
                        if 'images' in result:
                            scene.images = result.get('images', [])
                            # Display the first image in the image view
                            if scene.images and len(scene.images) > 0:
                                from pathlib import Path
                                from PySide6.QtGui import QPixmap
                                from core.utils import read_image_sidecar
                                img_path = scene.images[0]
                                # Handle both Path objects and string paths
                                if hasattr(img_path, 'path'):
                                    img_path = img_path.path
                                img_path = Path(img_path)
                                if img_path.exists():
                                    pixmap = QPixmap(str(img_path))
                                    if not pixmap.isNull():
                                        # Scale to fit the image view
                                        scaled = pixmap.scaled(
                                            self.workspace_widget.output_image_label.size(),
                                            Qt.KeepAspectRatio,
                                            Qt.SmoothTransformation
                                        )
                                        self.workspace_widget.output_image_label.setPixmap(scaled)

                                    # Add to history with tab tracking
                                    sidecar = read_image_sidecar(img_path)
                                    if sidecar:
                                        history_entry = {
                                            'path': img_path,
                                            'prompt': sidecar.get('prompt', scene.prompt),
                                            'timestamp': sidecar.get('timestamp', img_path.stat().st_mtime),
                                            'model': sidecar.get('model', ''),
                                            'provider': sidecar.get('provider', ''),
                                            'width': sidecar.get('width', ''),
                                            'height': sidecar.get('height', ''),
                                            'cost': sidecar.get('cost', 0.0),
                                            'source_tab': 'video'  # Mark as from video tab
                                        }
                                        # Emit signal to add to main history
                                        self.add_to_history_signal.emit(history_entry)

                        # Handle video clip generation results
                        if 'video_clip' in result:
                            from pathlib import Path
                            scene.video_clip = Path(result['video_clip'])
                        if 'last_frame' in result:
                            from pathlib import Path
                            scene.last_frame = Path(result['last_frame'])

                        # Update the preview column (column 4) to show video clip icon or image
                        preview_item = QTableWidgetItem("🎞️" if scene.video_clip else ("🖼️" if scene.images else "⬜"))
                        if scene.video_clip:
                            preview_item.setToolTip("Video clip generated - hover to preview last frame")
                        elif scene.images:
                            preview_item.setToolTip("Hover to preview full-size image")
                        else:
                            preview_item.setToolTip("No image generated yet")
                        self.workspace_widget.scene_table.setItem(i, 4, preview_item)
                    break
    
    @Slot(bool, str)
    def on_generation_complete(self, success: bool, message: str):
        """Handle generation completion"""
        self.workspace_widget.progress_bar.setVisible(False)
        self.workspace_widget.status_label.setText(message)
        # Log to status console
        self.workspace_widget._log_to_console(message, "SUCCESS" if success else "ERROR")

        if success:
            # Update UI state
            self.workspace_widget.update_ui_state()
            
            # Save project
            if self.current_project:
                try:
                    self.project_manager.save_project(self.current_project)
                except Exception as e:
                    self.logger.error(f"Failed to save project: {e}")
            
            # Log to event store
            try:
                from core.video.event_store import EventStore, ProjectEvent, EventType
                from pathlib import Path
                
                db_path = Path.home() / ".imageai" / "video_projects" / "events.db"
                event_store = EventStore(db_path)
                
                # Create appropriate event based on operation
                if self.generation_thread:
                    operation = self.generation_thread.operation
                    event_type_map = {
                        'enhance_prompts': EventType.PROMPT_BATCH_GENERATED,
                        'generate_images': EventType.IMAGE_GENERATED,
                        'render_video': EventType.VIDEO_RENDERED,
                    }
                    
                    event_type = event_type_map.get(operation, EventType.PROJECT_SAVED)
                    
                    event = ProjectEvent(
                        project_id=self.current_project.id if hasattr(self.current_project, 'id') else '',
                        event_type=event_type,
                        user="user",
                        data={'operation': operation, 'message': message}
                    )
                    event_store.append(event)
                    
            except Exception as e:
                self.logger.error(f"Failed to log event: {e}")
        else:
            dialog_manager = get_dialog_manager(self)
            # Use the specialized generation error method for better logging
            if self.generation_thread:
                operation = self.generation_thread.operation.replace('_', ' ').title()
                dialog_manager.show_generation_error(operation, message)
            else:
                dialog_manager.show_error("Generation Failed", message)