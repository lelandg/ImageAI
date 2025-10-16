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
from PySide6.QtCore import QThread, Signal, Slot, Qt
from PySide6.QtGui import QPixmap

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
            elif self.operation == "enhance_for_video":
                self._enhance_for_video()
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

            # Map style string to enum (support both predefined and custom styles)
            style_map = {
                'cinematic': PromptStyle.CINEMATIC,
                'artistic': PromptStyle.ARTISTIC,
                'photorealistic': PromptStyle.PHOTOREALISTIC,
                'animated': PromptStyle.ANIMATED,
                'documentary': PromptStyle.DOCUMENTARY,
                'abstract': PromptStyle.ABSTRACT,
                'noir': PromptStyle.NOIR,
                'fantasy': PromptStyle.FANTASY,
                'sci-fi': PromptStyle.SCIFI,
                'scifi': PromptStyle.SCIFI,
                'vintage': PromptStyle.VINTAGE,
                'minimalist': PromptStyle.MINIMALIST,
                'dramatic': PromptStyle.DRAMATIC
            }
            style = style_map.get(prompt_style.lower(), PromptStyle.CINEMATIC)

            # BATCH ENHANCE: Process all scenes in ONE API call
            total_scenes = len(self.project.scenes)

            if self.cancelled:
                return

            # Collect all scene sources for batch processing
            original_texts = [scene.source for scene in self.project.scenes]

            self.progress_update.emit(10, f"🚀 BATCH processing {total_scenes} scenes in 1 API call...")

            # Use batch_enhance for efficiency (ONE API call for all scenes)
            try:
                enhanced_prompts = llm.batch_enhance(
                    original_texts,
                    provider=llm_provider,
                    model=llm_model,
                    style=style,
                    temperature=0.7
                )

                # Apply enhanced prompts to scenes
                if not self.cancelled:
                    for i, (scene, enhanced) in enumerate(zip(self.project.scenes, enhanced_prompts)):
                        progress = int(((i + 1) / total_scenes) * 90) + 10  # 10-100%
                        scene_preview = scene.source[:40] + "..." if len(scene.source) > 40 else scene.source
                        scene.prompt = enhanced
                        self.progress_update.emit(progress, f"Scene {i+1}/{total_scenes}: '{scene_preview}' - ✓")

                if not self.cancelled:
                    self.progress_update.emit(100, f"✅ Batch enhanced {total_scenes} scenes")
                    self.generation_complete.emit(True, "Prompt enhancement complete")

            except Exception as batch_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ Batch enhancement failed: {batch_error}")
                self.progress_update.emit(0, f"❌ Batch enhancement failed: {str(batch_error)}")
                self.generation_complete.emit(False, f"Batch enhancement failed: {str(batch_error)}")
                return  # Stop processing - don't fall back to individual calls
                
        except Exception as e:
            self.generation_complete.emit(False, f"Prompt enhancement failed: {e}")

    def _enhance_for_video(self):
        """Enhance prompts for video generation with camera movement and continuity"""
        try:
            from core.video.prompt_engine import PromptEngine, UnifiedLLMProvider, PromptStyle
            import logging

            logger = logging.getLogger(__name__)

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

            # Map style string to enum (support both predefined and custom styles)
            style_map = {
                'cinematic': PromptStyle.CINEMATIC,
                'artistic': PromptStyle.ARTISTIC,
                'photorealistic': PromptStyle.PHOTOREALISTIC,
                'animated': PromptStyle.ANIMATED,
                'documentary': PromptStyle.DOCUMENTARY,
                'abstract': PromptStyle.ABSTRACT,
                'noir': PromptStyle.NOIR,
                'fantasy': PromptStyle.FANTASY,
                'sci-fi': PromptStyle.SCIFI,
                'scifi': PromptStyle.SCIFI,
                'vintage': PromptStyle.VINTAGE,
                'minimalist': PromptStyle.MINIMALIST,
                'dramatic': PromptStyle.DRAMATIC
            }
            style = style_map.get(prompt_style.lower(), PromptStyle.CINEMATIC)

            # BATCH ENHANCE FOR VIDEO: Process all scenes in ONE API call
            total_scenes = len(self.project.scenes)

            if self.cancelled:
                return

            # Collect all base texts for batch processing
            # Use image prompt as base if available, otherwise use source
            base_texts = [scene.prompt if scene.prompt else scene.source
                         for scene in self.project.scenes]

            self.progress_update.emit(10, f"🎬 BATCH processing {total_scenes} scenes for video in 1 API call...")

            # Use batch_enhance_for_video for efficiency (ONE API call for all scenes)
            try:
                video_prompts = llm.batch_enhance_for_video(
                    base_texts,
                    provider=llm_provider,
                    model=llm_model,
                    style=style,
                    temperature=0.7,
                    console_callback=None  # Progress updates handled by parent
                )

                # Apply video prompts to scenes
                if not self.cancelled:
                    for i, (scene, video_prompt) in enumerate(zip(self.project.scenes, video_prompts)):
                        progress = int(((i + 1) / total_scenes) * 90) + 10  # 10-100%
                        scene_preview = scene.source[:40] + "..." if len(scene.source) > 40 else scene.source
                        scene.video_prompt = video_prompt
                        self.progress_update.emit(progress, f"Scene {i+1}/{total_scenes}: '{scene_preview}' - ✓")

                if not self.cancelled:
                    self.progress_update.emit(100, f"✅ Batch enhanced {total_scenes} scenes for video")
                    self.generation_complete.emit(True, "Video prompt enhancement complete")

            except Exception as batch_error:
                logger.error(f"❌ Batch video enhancement failed: {batch_error}")
                self.progress_update.emit(0, f"❌ Batch video enhancement failed: {str(batch_error)}")
                self.generation_complete.emit(False, f"Batch video enhancement failed: {str(batch_error)}")
                return  # Stop processing - don't fall back to individual calls

        except Exception as e:
            logger.error(f"Video prompt enhancement failed: {e}")
            self.generation_complete.emit(False, f"Video prompt enhancement failed: {e}")

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
            prompt_style = self.kwargs.get('prompt_style', 'Cinematic')

            # Parse resolution string to width/height
            width = height = None
            if resolution and 'x' in resolution:
                parts = resolution.split('x')
                width, height = int(parts[0]), int(parts[1])
            elif resolution:
                # Handle "720p", "1080p" format
                if '720' in resolution:
                    if aspect_ratio == '16:9':
                        width, height = 1280, 720
                    elif aspect_ratio == '9:16':
                        width, height = 720, 1280
                    elif aspect_ratio == '1:1':
                        width, height = 720, 720
                elif '1080' in resolution:
                    if aspect_ratio == '16:9':
                        width, height = 1920, 1080
                    elif aspect_ratio == '9:16':
                        width, height = 1080, 1920
                    elif aspect_ratio == '1:1':
                        width, height = 1080, 1080

            # For Gemini provider: scale to max 1024 and track target for post-processing
            gemini_scaled_width = width
            gemini_scaled_height = height
            original_width = width
            original_height = height
            needs_upscale = False

            if provider == 'google' and width and height:
                max_dim = max(width, height)
                if max_dim > 1024:
                    # Scale proportionally so max dimension is 1024
                    scale_factor = 1024 / max_dim
                    gemini_scaled_width = int(width * scale_factor)
                    gemini_scaled_height = int(height * scale_factor)
                    needs_upscale = True
                    logger.info(f"Scaling down for Gemini: {width}x{height} -> {gemini_scaled_width}x{gemini_scaled_height} (factor: {scale_factor:.3f})")
                    self.progress_update.emit(0, f"Note: Scaling request to {gemini_scaled_width}x{gemini_scaled_height} for Gemini, will upscale to {width}x{height}")

            # Generate images for each scene
            for i, scene in enumerate(scenes_to_generate):
                if self.cancelled:
                    break

                progress = int((i / total_scenes) * 100)
                self.progress_update.emit(progress, f"Generating images for scene {i+1}/{total_scenes}")

                # Generate images for this scene
                scene_images = []
                image_paths = []

                # Prepend style to prompt for first scene only (others use continuity)
                prompt_with_style = scene.prompt
                scene_actual_index = self.project.scenes.index(scene)
                if scene_actual_index == 0 and prompt_style:
                    prompt_with_style = f"{prompt_style} style: {scene.prompt}"
                    logger.info(f"Scene {scene_actual_index}: Prepending style '{prompt_style}' to prompt")

                try:
                    for v in range(variants):
                        logger.info(f"Generating variant {v+1}/{variants} for scene {i+1}")

                        # Prepare generation kwargs
                        gen_kwargs = {
                            'aspect_ratio': aspect_ratio,
                            'num_images': 1
                        }

                        # For Gemini: use scaled dimensions and enable cropping
                        if provider == 'google':
                            gen_kwargs['width'] = gemini_scaled_width
                            gen_kwargs['height'] = gemini_scaled_height
                            gen_kwargs['crop_to_aspect'] = True
                            gen_kwargs['_target_width'] = original_width
                            gen_kwargs['_target_height'] = original_height
                            gen_kwargs['_needs_upscale'] = needs_upscale

                            # Log what we're sending
                            if aspect_ratio != '1:1':
                                logger.info(f"Sending to Gemini with aspect ratio {aspect_ratio}: dimensions ({gemini_scaled_width}x{gemini_scaled_height})")
                        else:
                            # For other providers, use original dimensions
                            if width and height:
                                gen_kwargs['width'] = width
                                gen_kwargs['height'] = height

                        # Generate single image using provider (same as image tab)
                        texts, images = provider_instance.generate(
                            prompt=prompt_with_style,
                            model=model,
                            **gen_kwargs
                        )

                        if images:
                            scene_images.extend(images)

                            # Save image to project directory
                            images_dir = self.project.project_dir / "images"
                            images_dir.mkdir(parents=True, exist_ok=True)

                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            img_filename = f"scene_{i}_{timestamp}_v{v}.png"
                            img_path = images_dir / img_filename
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
            from core.video.midi_processor import snap_duration_to_veo
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
            # Check for 'start_frame' (new parameter name) or fall back to 'seed_image' (old name)
            seed_image_path = self.kwargs.get('start_frame') or self.kwargs.get('seed_image')
            # Use video_prompt if available, otherwise fall back to regular prompt
            prompt = scene.video_prompt if scene.video_prompt else scene.prompt
            aspect_ratio = self.kwargs.get('aspect_ratio', '16:9')

            # Log which prompt is being used
            import logging
            logger = logging.getLogger(__name__)
            if scene.video_prompt:
                logger.info(f"Using video_prompt for scene {scene_index}: {prompt[:100]}...")
            else:
                logger.info(f"Using regular prompt for scene {scene_index} (no video_prompt): {prompt[:100]}...")

            self.progress_update.emit(10, f"Generating video clip for scene {scene_index + 1}...")

            # Initialize Veo client
            google_api_key = self.kwargs.get('google_api_key')
            if not google_api_key:
                self.generation_complete.emit(False, "Google API key required for Veo video generation")
                return

            veo_client = VeoClient(api_key=google_api_key)

            # If using seed image, check aspect ratio match and apply transparent canvas fix if needed
            processed_seed_path = None
            if seed_image_path and Path(seed_image_path).exists():
                from PIL import Image
                import logging
                logger = logging.getLogger(__name__)

                try:
                    img = Image.open(seed_image_path)
                    ref_width, ref_height = img.size
                    ref_aspect = ref_width / ref_height

                    # Calculate expected aspect ratio
                    expected_aspect = 1.0
                    if aspect_ratio and ':' in aspect_ratio:
                        ar_parts = aspect_ratio.split(':')
                        expected_aspect = float(ar_parts[0]) / float(ar_parts[1])

                    # Check if there's a significant mismatch (more than 10% difference)
                    if abs(ref_aspect - expected_aspect) > 0.1:
                        logger.warning(f"⚠️ ASPECT RATIO MISMATCH: Reference image is {ref_width}x{ref_height} "
                                     f"(aspect {ref_aspect:.2f}) but requesting {aspect_ratio} "
                                     f"(aspect {expected_aspect:.2f}). Applying canvas centering fix...")

                        # Create a transparent canvas with the target aspect ratio
                        # Calculate canvas dimensions based on reference image max dimension
                        max_ref_dim = max(ref_width, ref_height)

                        # Calculate canvas dimensions maintaining target aspect ratio
                        if expected_aspect >= 1.0:  # Landscape or square
                            canvas_width = max_ref_dim
                            canvas_height = int(max_ref_dim / expected_aspect)
                        else:  # Portrait
                            canvas_height = max_ref_dim
                            canvas_width = int(max_ref_dim * expected_aspect)

                        # Make sure canvas is large enough to contain the reference image
                        if canvas_width < ref_width:
                            canvas_width = ref_width
                            canvas_height = int(ref_width / expected_aspect)
                        if canvas_height < ref_height:
                            canvas_height = ref_height
                            canvas_width = int(ref_height * expected_aspect)

                        logger.info(f"Creating transparent canvas: {canvas_width}x{canvas_height} (aspect {expected_aspect:.2f})")
                        logger.info(f"Reference image will be centered: {ref_width}x{ref_height}")
                        self.progress_update.emit(15, f"Applying canvas centering fix for aspect ratio...")

                        # Create transparent canvas
                        canvas = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))

                        # Calculate position to center the reference image
                        x_offset = (canvas_width - ref_width) // 2
                        y_offset = (canvas_height - ref_height) // 2

                        # Convert reference image to RGBA if needed
                        if img.mode != 'RGBA':
                            img_rgba = img.convert('RGBA')
                        else:
                            img_rgba = img

                        # Paste the reference image centered on the canvas
                        canvas.paste(img_rgba, (x_offset, y_offset), img_rgba)

                        # Save the composed canvas
                        temp_dir = self.project.project_dir / "temp"
                        temp_dir.mkdir(parents=True, exist_ok=True)
                        processed_seed_path = temp_dir / f"canvas_seed_scene_{scene_index}.png"
                        canvas.save(processed_seed_path, 'PNG')
                        logger.info(f"Saved composed canvas: {processed_seed_path}")

                        seed_image_path = processed_seed_path
                except Exception as e:
                    logger.warning(f"Failed to process reference image: {e}")
                    # Fall back to original seed image

            # Snap duration to Veo-compatible value (4, 6, or 8 seconds)
            veo_duration = snap_duration_to_veo(scene.duration_sec)
            if veo_duration != scene.duration_sec:
                logger.info(f"Snapped duration from {scene.duration_sec}s to {veo_duration}s for Veo 3 compatibility")
                self.progress_update.emit(12, f"Adjusted duration from {scene.duration_sec}s to {veo_duration}s (Veo 3 requires 4/6/8s)")

            # Configure generation with prompt and optional seed image
            config = VeoGenerationConfig(
                model=VeoModel.VEO_3_GENERATE,
                prompt=prompt,
                duration=veo_duration,
                aspect_ratio=aspect_ratio,
                image=Path(seed_image_path) if seed_image_path and Path(seed_image_path).exists() else None
            )

            if config.image:
                logger.info(f"Using seed image for image-to-video generation: {config.image}")
                self.progress_update.emit(20, "Submitting to Veo with seed image...")
            else:
                self.progress_update.emit(20, "Submitting to Veo...")

            # Generate video (with or without seed image)
            result = veo_client.generate_video(config)

            if not result.success:
                raise Exception(f"Veo generation failed: {result.error}")

            cached_video_path = result.video_path
            if not cached_video_path or not cached_video_path.exists():
                raise Exception("Video generation succeeded but no video file was created")

            self.progress_update.emit(70, "Copying video to project folder...")

            # Copy video from cache to project directory
            import shutil
            clips_dir = self.project.project_dir / "clips"
            clips_dir.mkdir(parents=True, exist_ok=True)

            # Create a proper filename in the project directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"scene_{scene_index}_{timestamp}.mp4"
            video_path = clips_dir / video_filename

            # Copy the video file to the project directory
            shutil.copy2(cached_video_path, video_path)
            logger.info(f"Copied video from cache to project: {video_path}")

            self.progress_update.emit(80, "Extracting last frame...")

            # Extract last frame
            last_frame_path = self._extract_last_frame(video_path, scene_index)

            # Extract first frame
            self.progress_update.emit(85, "Extracting first frame...")
            first_frame_path = self._extract_first_frame(video_path, scene_index)

            # Update scene with video clip and frames (using project path)
            scene.video_clip = video_path
            scene.first_frame = first_frame_path
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
        frames_dir = self.project.project_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        frame_path = frames_dir / f"scene_{scene_index}_last_frame.png"
        cv2.imwrite(str(frame_path), frame)

        return frame_path

    def _extract_first_frame(self, video_path: Path, scene_index: int) -> Path:
        """Extract the first frame from a video clip"""
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise Exception(f"Failed to open video: {video_path}")

        # Read the first frame
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise Exception("Failed to read first frame from video")

        # Save the frame
        first_frames_dir = self.project.project_dir / "first_frames"
        first_frames_dir.mkdir(parents=True, exist_ok=True)

        frame_path = first_frames_dir / f"scene_{scene_index + 1:03d}_first_frame.png"
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
            # Project directory already exists, just ensure it's available
            self.project.project_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.project.project_dir / f"{self.project.name}_{timestamp}.mp4"
            
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
        self.logger.info("=== VideoProjectTab.__init__ CALLED ===")

        self.init_ui()
        self.logger.info("=== VideoProjectTab.__init__ COMPLETE ===")
    
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
        self.logger.info("Creating WorkspaceWidget...")
        self.workspace_widget = WorkspaceWidget(self.config, self.providers)
        self.logger.info("WorkspaceWidget created successfully")
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
                        # Note: scene.images is already set with ImageVariant objects in _generate_images
                        # Don't overwrite it here, just use the paths for UI display
                        if 'images' in result:
                            image_paths = result.get('images', [])
                            # Display the first image in the image view
                            if scene.images and len(scene.images) > 0:
                                from pathlib import Path
                                from PySide6.QtGui import QPixmap
                                from core.utils import read_image_sidecar
                                from core.video.project import ImageVariant

                                # Get the path from the first image (could be ImageVariant or Path)
                                first_img = scene.images[0]
                                if isinstance(first_img, ImageVariant):
                                    img_path = first_img.path
                                else:
                                    img_path = Path(first_img)
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

                            # Auto-load video after generation to show first frame
                            if scene.first_frame and scene.first_frame.exists():
                                self.workspace_widget._load_video_first_frame_in_panel(i)
                                # Reset the video button toggle state so first click plays video
                                video_btn = self.workspace_widget.scene_table.cellWidget(i, 3)
                                if video_btn and hasattr(video_btn, 'reset_toggle_state'):
                                    video_btn.reset_toggle_state()

                        if 'last_frame' in result:
                            from pathlib import Path
                            scene.last_frame = Path(result['last_frame'])

                            # If "use last frame for continuous video" is checked,
                            # set last frame as image for NEXT scene (not current scene)
                            use_last_frame_for_next = self.generation_thread.kwargs.get('use_last_frame_for_next', False)
                            if use_last_frame_for_next and i < len(self.current_project.scenes) - 1:
                                next_scene = self.current_project.scenes[i + 1]
                                # Add last frame as an image for the next scene
                                from core.video.project import ImageVariant
                                last_frame_variant = ImageVariant(
                                    path=scene.last_frame,
                                    provider='veo_last_frame',
                                    model='continuous',
                                    cost=0.0
                                )
                                # Prepend to images list so it's the first image
                                if not next_scene.images:
                                    next_scene.images = [last_frame_variant]
                                else:
                                    next_scene.images.insert(0, last_frame_variant)

                        # Update the preview column (column 4) - always show image icon if image exists
                        if scene.images:
                            preview_item = QTableWidgetItem("🖼️")
                            if scene.video_clip:
                                preview_item.setToolTip("Image and video available - Click row to view, click again to toggle between them")
                            else:
                                preview_item.setToolTip("Image available - Click row to view (hover for preview)")
                        elif scene.video_clip:
                            preview_item = QTableWidgetItem("🎞️")
                            preview_item.setToolTip("Video clip generated - Click row to view first frame")
                        else:
                            preview_item = QTableWidgetItem("⬜")
                            preview_item.setToolTip("No image or video generated yet")
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

            # Refresh scene table to show updated prompts/video_prompts
            self.workspace_widget.populate_scene_table()

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