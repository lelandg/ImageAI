"""
Google Veo API client for AI video generation.

This module handles video generation using Google's Veo models through
the Gemini API with support for various configurations and regional restrictions.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import hashlib
import requests
from io import BytesIO
from PIL import Image

# Check if google.genai is available
try:
    import google.genai as genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

# Check if Google Cloud is available
try:
    import importlib.util
    GCLOUD_AVAILABLE = importlib.util.find_spec("google.cloud.aiplatform") is not None
except ImportError:
    GCLOUD_AVAILABLE = False

# These will be populated on first use for gcloud auth
aiplatform = None
google_auth_default = None
DefaultCredentialsError = Exception


class VeoModel(Enum):
    """Available Veo models"""
    VEO_3_GENERATE = "veo-3.0-generate-001"
    VEO_3_1_GENERATE = "veo-3.1-generate-preview"  # Supports reference images, 1080p, 8s fixed
    VEO_3_1_FAST = "veo-3.1-fast-generate-preview"  # Fast generation (11-60s), 720p, 4-8s variable
    VEO_3_FAST = "veo-3.0-fast-generate-001"
    VEO_2_GENERATE = "veo-2.0-generate-001"


@dataclass
class VeoGenerationConfig:
    """Configuration for Veo video generation"""
    model: VeoModel = VeoModel.VEO_3_GENERATE
    prompt: str = ""
    aspect_ratio: str = "16:9"  # 16:9, 9:16, 1:1
    resolution: str = "1080p"  # 720p, 1080p
    duration: int = 8  # seconds (model-specific limits: 4, 6, or 8 for Veo 3)
    fps: int = 24  # frames per second
    include_audio: bool = True  # Veo 3 can generate audio
    person_generation: bool = False  # May be restricted by region
    seed: Optional[int] = None
    image: Optional[Path] = None  # Start frame for image-to-video generation
    last_frame: Optional[Path] = None  # End frame for Veo 3.1 frame-to-frame interpolation
    reference_images: Optional[List[Path]] = None  # Up to 3 reference images for style/character/environment consistency

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Validate duration for Veo 3 models
        # Veo 3.0 and 3.1 Standard: ONLY support 8 seconds
        if self.model in [VeoModel.VEO_3_GENERATE, VeoModel.VEO_3_1_GENERATE]:
            if self.duration != 8:
                raise ValueError(
                    f"Veo 3.0 and 3.1 Standard ONLY support 8-second clips, got {self.duration}. "
                    f"All scenes must be batched to exactly 8 seconds."
                )
        # Veo 3.0 Fast and 3.1 Fast: Support 4, 6, or 8 seconds
        elif self.model in [VeoModel.VEO_3_FAST, VeoModel.VEO_3_1_FAST]:
            if self.duration not in [4, 6, 8]:
                raise ValueError(
                    f"Veo 3 Fast duration must be 4, 6, or 8 seconds, got {self.duration}. "
                    f"Use snap_duration_to_veo() to convert float durations."
                )

        # Validate reference images (supported by Veo 3.1, 3.1 Fast, and Veo 2.0)
        if self.reference_images and len(self.reference_images) > 0:
            if self.model not in [VeoModel.VEO_3_1_GENERATE, VeoModel.VEO_3_1_FAST, VeoModel.VEO_2_GENERATE]:
                raise ValueError(
                    f"Reference images are only supported by Veo 3.1, Veo 3.1 Fast, and Veo 2.0, "
                    f"but model is {self.model.value}. Please use Veo 3.1 for reference image support."
                )
            if len(self.reference_images) > 3:
                raise ValueError(
                    f"Veo 3.1 supports maximum 3 reference images, got {len(self.reference_images)}. "
                    f"Please reduce to 3 or fewer reference images."
                )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls (excludes image, handled separately)"""
        config = {
            "prompt": self.prompt,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "duration": self.duration,
            "fps": self.fps,
        }

        if self.model == VeoModel.VEO_3_GENERATE:
            config["include_audio"] = self.include_audio

        if self.person_generation:
            config["person_generation"] = True

        if self.seed is not None:
            config["seed"] = self.seed

        # Note: image, last_frame, and reference_images are handled separately
        # in generate_video_async as they require special loading/preparation

        return config


@dataclass
class VeoGenerationResult:
    """Result of a Veo generation operation"""
    success: bool = True
    video_url: Optional[str] = None
    video_path: Optional[Path] = None
    operation_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    generation_time: float = 0.0
    has_synthid: bool = True  # Veo videos include SynthID watermark
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VeoClient:
    """Client for Google Veo API video generation"""
    
    # Model constraints (updated October 2025)
    MODEL_CONSTRAINTS = {
        VeoModel.VEO_3_GENERATE: {
            "max_duration": 8,
            "fixed_duration": 8,  # Veo 3.0 ONLY supports 8-second clips
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16", "1:1"],
            "supports_audio": True,
            "supports_reference_images": False,  # Veo 3.0 does NOT support reference images
            "generation_time": (60, 360)  # 1-6 minutes
        },
        VeoModel.VEO_3_1_GENERATE: {
            "max_duration": 8,
            "fixed_duration": 8,  # Veo 3.1 Standard ONLY supports 8-second clips
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16", "1:1"],
            "supports_audio": True,
            "supports_reference_images": True,  # Veo 3.1 supports reference images (up to 3)
            "supports_scene_extension": True,  # Veo 3.1 supports scene extension
            "supports_frame_interpolation": True,  # Veo 3.1 supports frame-to-frame interpolation
            "generation_time": (60, 360)  # 1-6 minutes
        },
        VeoModel.VEO_3_1_FAST: {
            "max_duration": 8,
            "fixed_duration": None,  # Can be 4, 6, or 8 seconds (variable)
            "resolutions": ["720p"],  # Fast variant is 720p only
            "aspect_ratios": ["16:9", "9:16"],
            "supports_audio": True,  # Veo 3.1 Fast supports audio
            "supports_reference_images": True,  # Veo 3.1 Fast supports reference images (up to 3)
            "supports_scene_extension": True,  # Veo 3.1 Fast supports scene extension
            "supports_frame_interpolation": True,  # Veo 3.1 Fast supports frame-to-frame interpolation
            "generation_time": (11, 60)  # 11-60 seconds (FAST!)
        },
        VeoModel.VEO_3_FAST: {
            "max_duration": 8,
            "fixed_duration": None,  # Can be 4, 6, or 8 seconds
            "resolutions": ["720p"],
            "aspect_ratios": ["16:9", "9:16"],
            "supports_audio": False,
            "supports_reference_images": False,
            "generation_time": (11, 60)  # 11-60 seconds
        },
        VeoModel.VEO_2_GENERATE: {
            "max_duration": 8,
            "resolutions": ["720p"],
            "aspect_ratios": ["16:9"],
            "supports_audio": False,
            "supports_reference_images": True,  # Veo 2.0 supports reference images
            "generation_time": (60, 180)  # 1-3 minutes
        }
    }
    
    def __init__(self, api_key: Optional[str] = None, region: Optional[str] = None, auth_mode: str = "api-key", project_id: Optional[str] = None):
        """
        Initialize Veo client.

        Args:
            api_key: Google API key (for api-key auth mode)
            region: User's region for restriction checking
            auth_mode: Authentication mode - "api-key" or "gcloud"
            project_id: Google Cloud project ID (for gcloud auth mode)
        """
        if not GENAI_AVAILABLE:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")

        self.api_key = api_key
        self.auth_mode = auth_mode
        self.project_id = project_id
        self.region = region or self._detect_region()
        self.logger = logging.getLogger(__name__)
        self.client = None

        # Initialize client based on auth mode
        if auth_mode == "gcloud":
            self._init_gcloud_client()
        elif api_key:
            # Use the new google.genai Client API instead of configure
            self.client = genai.Client(api_key=api_key)

        # Check regional restrictions
        self.person_generation_allowed = self._check_person_generation()

    def _init_gcloud_client(self):
        """Initialize client with Google Cloud authentication (Application Default Credentials)."""
        global aiplatform, google_auth_default, DefaultCredentialsError

        if not GCLOUD_AVAILABLE:
            raise ImportError(
                "Google Cloud AI Platform not installed. "
                "Run: pip install google-cloud-aiplatform"
            )

        # Lazy import Google Cloud on first use
        if aiplatform is None:
            self.logger.info("Loading Google Cloud AI Platform for gcloud auth...")
            from google.cloud import aiplatform
            from google.auth import default as google_auth_default
            from google.auth.exceptions import DefaultCredentialsError

        try:
            # Get Application Default Credentials
            credentials, project = google_auth_default()
            if not project:
                project = self.project_id
            if not project:
                raise ValueError(
                    "No Google Cloud project found. "
                    "Set a project with: gcloud config set project YOUR_PROJECT_ID"
                )

            self.project_id = project
            # Initialize aiplatform
            aiplatform.init(project=project, location="us-central1")

            # Create genai client that will use Vertex AI (vertexai=True + ADC)
            # IMPORTANT: Must pass vertexai=True to use Vertex AI endpoint instead of Gemini API
            self.client = genai.Client(
                vertexai=True,
                project=project,
                location="us-central1"
            )
            self.logger.info(f"✓ Using gcloud authentication with Vertex AI project: {project}")

        except DefaultCredentialsError as e:
            raise RuntimeError(
                f"Google Cloud authentication failed.\n\n"
                f"Please complete the setup:\n"
                f"1. Install Google Cloud CLI from:\n"
                f"   https://cloud.google.com/sdk/docs/install\n"
                f"2. Run in terminal/PowerShell:\n"
                f"   gcloud auth application-default login\n"
                f"3. Set your project:\n"
                f"   gcloud config set project YOUR_PROJECT_ID\n"
                f"4. Enable required APIs at:\n"
                f"   https://console.cloud.google.com/apis/library\n"
                f"   - Vertex AI API\n"
                f"   - Cloud Resource Manager API\n\n"
                f"Error details: {e}"
            )

    def _detect_region(self) -> str:
        """Detect user's region from IP"""
        try:
            response = requests.get("https://ipapi.co/json/", timeout=5)
            data = response.json()
            return data.get("country_code", "US")
        except:
            return "US"  # Default to US
    
    def _check_person_generation(self) -> bool:
        """Check if person generation is allowed in region"""
        # MENA and some EU countries have restrictions
        restricted_regions = [
            "AE", "SA", "EG", "JO", "KW", "QA", "BH", "OM", "LB", "IQ",  # MENA
            "DE", "FR", "IT", "ES"  # Some EU countries
        ]
        return self.region not in restricted_regions
    
    def validate_config(self, config: VeoGenerationConfig) -> Tuple[bool, Optional[str]]:
        """
        Validate generation configuration against model constraints.
        
        Args:
            config: Generation configuration
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        constraints = self.MODEL_CONSTRAINTS.get(config.model)
        if not constraints:
            return False, f"Unknown model: {config.model.value}"
        
        # Check duration
        if config.duration > constraints["max_duration"]:
            return False, f"Duration {config.duration}s exceeds max {constraints['max_duration']}s for {config.model.value}"
        
        # Check resolution
        if config.resolution not in constraints["resolutions"]:
            return False, f"Resolution {config.resolution} not supported. Use: {constraints['resolutions']}"
        
        # Check aspect ratio
        if config.aspect_ratio not in constraints["aspect_ratios"]:
            return False, f"Aspect ratio {config.aspect_ratio} not supported. Use: {constraints['aspect_ratios']}"
        
        # Check audio support
        if config.include_audio and not constraints["supports_audio"]:
            return False, f"Model {config.model.value} does not support audio generation"
        
        # Check person generation
        if config.person_generation and not self.person_generation_allowed:
            return False, f"Person generation is not available in your region ({self.region})"
        
        return True, None
    
    async def generate_video_async(self, config: VeoGenerationConfig) -> VeoGenerationResult:
        """
        Generate video asynchronously using Veo API.
        
        Args:
            config: Generation configuration
            
        Returns:
            Generation result
        """
        result = VeoGenerationResult()
        
        # Validate configuration
        is_valid, error = self.validate_config(config)
        if not is_valid:
            result.success = False
            result.error = error
            return result
        
        try:
            start_time = time.time()

            if not self.client:
                raise ValueError("No client configured. API key required for video generation.")

            # Load start frame (seed image) if provided
            seed_image = None
            if config.image and config.image.exists():
                try:
                    # Load image bytes
                    with open(config.image, 'rb') as f:
                        image_bytes = f.read()

                    # Create Image object for Veo API
                    # Must be a dict with imageBytes and mimeType
                    seed_image = {
                        'imageBytes': image_bytes,
                        'mimeType': 'image/png'
                    }
                    self.logger.info(f"Loaded start frame (seed image): {config.image} ({len(image_bytes)} bytes)")
                except Exception as e:
                    self.logger.warning(f"Failed to load start frame: {e}, proceeding without it")

            # Load end frame (last_frame) if provided for Veo 3.1 interpolation
            last_frame_image = None
            if config.last_frame and config.last_frame.exists():
                try:
                    # Load image bytes
                    with open(config.last_frame, 'rb') as f:
                        last_frame_bytes = f.read()

                    # Create Image object for Veo API
                    last_frame_image = {
                        'imageBytes': last_frame_bytes,
                        'mimeType': 'image/png'
                    }
                    self.logger.info(f"Loaded end frame (last_frame): {config.last_frame} ({len(last_frame_bytes)} bytes)")
                    self.logger.info("Using Veo 3.1 frame-to-frame interpolation mode")
                except Exception as e:
                    self.logger.warning(f"Failed to load end frame: {e}, proceeding without it")

            # Load reference images if provided for Veo 3 style/character/environment consistency (max 3)
            reference_image_list = []
            if config.reference_images:
                for idx, ref_path in enumerate(config.reference_images[:3]):  # Max 3
                    if ref_path and ref_path.exists():
                        try:
                            # Load image bytes manually (same approach as start frame)
                            with open(ref_path, 'rb') as f:
                                ref_image_bytes = f.read()

                            # Load image with PIL to check and fix aspect ratio if needed
                            img = Image.open(BytesIO(ref_image_bytes))
                            ref_width, ref_height = img.size
                            ref_aspect = ref_width / ref_height

                            # Parse target aspect ratio (e.g., "16:9" -> 16/9 = 1.777...)
                            if ':' in config.aspect_ratio:
                                ar_parts = config.aspect_ratio.split(':')
                                expected_aspect = int(ar_parts[0]) / int(ar_parts[1])
                            else:
                                # Fallback to 16:9 if invalid format
                                self.logger.warning(f"Invalid aspect ratio format: {config.aspect_ratio}, using 16:9")
                                expected_aspect = 16/9

                            # Check if aspect ratios match (within tolerance)
                            if abs(ref_aspect - expected_aspect) > 0.1:
                                self.logger.info(f"Aspect ratio adjustment: Reference image {idx+1} is {ref_width}x{ref_height} "
                                               f"(aspect {ref_aspect:.2f}) but requesting {config.aspect_ratio} "
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

                                self.logger.info(f"Creating transparent canvas: {canvas_width}x{canvas_height} (aspect {expected_aspect:.2f})")
                                self.logger.info(f"Reference image will be centered: {ref_width}x{ref_height}")

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

                                # Save the composed canvas for debugging
                                timestamp = int(time.time())
                                debug_filename = f"DEBUG_VEO_REF_CANVAS_{idx+1}_{timestamp}.png"
                                # Get output directory from config
                                from core.config import ConfigManager
                                config_mgr = ConfigManager()
                                output_dir = Path(config_mgr.get('output_dir', Path.home() / 'AppData' / 'Roaming' / 'ImageAI' / 'generated'))
                                debug_path = output_dir / debug_filename
                                canvas.save(debug_path, 'PNG')
                                self.logger.info(f"Saved composed canvas for debugging: {debug_path}")

                                # Convert canvas to bytes
                                img = canvas
                                self.logger.info(f"Using composed canvas ({canvas_width}x{canvas_height}) instead of original reference image")

                            # Convert image to bytes
                            output_buffer = BytesIO()
                            img.save(output_buffer, format='PNG')
                            ref_image_bytes = output_buffer.getvalue()

                            # Create reference image dict with bytes and MIME type
                            ref_image_dict = {
                                'imageBytes': ref_image_bytes,
                                'mimeType': 'image/png'
                            }

                            # Create VideoGenerationReferenceImage with the image dict
                            ref_image = types.VideoGenerationReferenceImage(
                                image=ref_image_dict,
                                reference_type="asset"  # "asset" for character/object consistency
                            )
                            reference_image_list.append(ref_image)
                            self.logger.info(f"Loaded reference image {idx+1}: {ref_path} ({len(ref_image_bytes)} bytes)")
                        except Exception as e:
                            self.logger.warning(f"Failed to load reference image {idx+1} ({ref_path}): {e}, skipping")

                if reference_image_list:
                    self.logger.info(f"Using {len(reference_image_list)} reference image(s) for visual consistency")

            # Create GenerateVideosConfig for additional parameters
            # Note: Resolution is determined automatically by the model based on aspect_ratio
            # Veo 3 supports duration_seconds parameter (4, 6, or 8 seconds)
            video_config_params = {
                "aspect_ratio": config.aspect_ratio,
                "duration_seconds": config.duration,  # int, not string
            }

            # Add optional parameters if set
            # Note: Only send person_generation if explicitly enabled
            # The API doesn't support "dont_allow" - omit parameter to disable
            if config.person_generation:
                video_config_params["person_generation"] = "allow_adult"

            if config.seed is not None:
                video_config_params["seed"] = config.seed

            # Add last_frame for Veo 3.1 interpolation (must be used with image/start frame)
            if last_frame_image:
                video_config_params["last_frame"] = last_frame_image
                self.logger.info("Added last_frame to GenerateVideosConfig for frame-to-frame interpolation")

            # Add reference images for Veo 3 visual consistency (max 3)
            if reference_image_list:
                video_config_params["reference_images"] = reference_image_list
                self.logger.info(f"Added {len(reference_image_list)} reference image(s) to GenerateVideosConfig for visual consistency")

            video_config = types.GenerateVideosConfig(**video_config_params)

            # Start generation (returns operation ID for polling)
            self.logger.info(f"Starting Veo generation with {config.model.value}")
            self.logger.info(f"Config: {config.aspect_ratio}, duration={config.duration}s")
            self.logger.info(f"Note: Resolution determined automatically by model (typically 720p)")

            # Log generation mode
            if seed_image and last_frame_image:
                self.logger.info("Mode: Frame-to-Frame Interpolation (Veo 3.1)")
                self.logger.info("  - Start frame provided")
                self.logger.info("  - End frame provided")
                self.logger.info("  - Veo will generate smooth transition between frames")
            elif seed_image:
                self.logger.info("Mode: Image-to-Video")
                self.logger.info("  - Start frame provided")
            else:
                self.logger.info("Mode: Text-to-Video")

            # Log reference images if provided
            if reference_image_list:
                self.logger.info(f"Visual Consistency: {len(reference_image_list)} reference image(s) for style/character/environment guidance")

            self.logger.info(f"Full Prompt:\n{config.prompt}")

            if seed_image:
                response = self.client.models.generate_videos(
                    model=config.model.value,
                    prompt=config.prompt,
                    config=video_config,
                    image=seed_image
                )
            else:
                response = self.client.models.generate_videos(
                    model=config.model.value,
                    prompt=config.prompt,
                    config=video_config
                )
            
            # Store operation ID for polling
            result.operation_id = response.name
            result.metadata["model"] = config.model.value
            result.metadata["prompt"] = config.prompt
            result.metadata["started_at"] = datetime.now().isoformat()
            
            # Poll for completion
            # Documentation states 1-6 minutes typical, using 8 minutes for buffer
            constraints = self.MODEL_CONSTRAINTS[config.model]
            max_wait = 480  # 8 minutes

            video_result = await self._poll_for_completion(response, max_wait)

            if video_result:
                # Handle both URL (str) and raw bytes (bytes) responses
                if isinstance(video_result, bytes):
                    # Raw video bytes returned directly
                    self.logger.info(f"Received raw video bytes, saving to local storage...")
                    result.video_path = await self._save_video_bytes(video_result)
                    result.success = True
                    result.metadata["source"] = "raw_bytes"
                elif isinstance(video_result, str):
                    # URL returned, download it
                    result.video_url = video_result
                    result.success = True

                    # Download video to local storage
                    result.video_path = await self._download_video(video_result)

                    # Note about retention
                    result.metadata["retention_warning"] = "Video URLs expire after 2 days. Local copy saved."
                    result.metadata["expires_at"] = (datetime.now() + timedelta(days=2)).isoformat()
                    result.metadata["source"] = "url_download"
                else:
                    self.logger.error(f"Unexpected video result type: {type(video_result)}")
                    result.success = False
                    result.error = f"Unexpected result type: {type(video_result)}"
            else:
                result.success = False
                result.error = "Generation timed out or failed"
            
            result.generation_time = time.time() - start_time
            self.logger.info(f"Generation completed in {result.generation_time:.1f} seconds")
            
        except Exception as e:
            self.logger.error(f"Veo generation failed: {e}")
            result.success = False
            result.error = str(e)
        
        return result
    
    def generate_video(self, config: VeoGenerationConfig) -> VeoGenerationResult:
        """
        Generate video synchronously (blocking).

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.generate_video_async(config))
        finally:
            loop.close()

    async def extend_video_async(
        self,
        previous_video_path: Path,
        prompt: str,
        config: VeoGenerationConfig
    ) -> VeoGenerationResult:
        """
        Extend a previous video by generating a new clip that continues from it.

        Uses the final portion of the previous video as seed for visual continuity.
        Supports up to 20 extensions (~148 seconds total video length).

        IMPORTANT: Extended segments run at 720p even if original was 1080p.

        Args:
            previous_video_path: Path to the video to extend
            prompt: Prompt for the new segment (describe continuation)
            config: Generation configuration

        Returns:
            VeoGenerationResult with the extended clip

        Example:
            # Generate first clip
            result1 = await client.generate_video_async(config)

            # Extend the video
            result2 = await client.extend_video_async(
                previous_video_path=result1.video_path,
                prompt="The car turns off onto a dirt road",
                config=config
            )
        """
        result = VeoGenerationResult()

        # Validate that model supports scene extension
        constraints = self.MODEL_CONSTRAINTS.get(config.model, {})
        if not constraints.get("supports_scene_extension", False):
            result.success = False
            result.error = (
                f"Model {config.model.value} does not support scene extension. "
                f"Use Veo 3.1 or Veo 3.1 Fast for scene extension."
            )
            return result

        # Validate previous video exists
        if not previous_video_path or not previous_video_path.exists():
            result.success = False
            result.error = f"Previous video not found: {previous_video_path}"
            return result

        try:
            start_time = time.time()

            if not self.client:
                raise ValueError("No client configured. API key required for video generation.")

            # Load previous video bytes
            self.logger.info(f"Loading previous video for extension: {previous_video_path}")
            with open(previous_video_path, 'rb') as f:
                video_bytes = f.read()

            self.logger.info(f"Loaded previous video: {len(video_bytes) / (1024*1024):.2f} MB")

            # Create video dict for API (uses final 1 second as seed)
            video_dict = {
                'videoBytes': video_bytes,
                'mimeType': 'video/mp4'
            }

            # Create generation config
            video_config_params = {
                "aspect_ratio": config.aspect_ratio,
                "duration_seconds": config.duration,
            }

            if config.seed is not None:
                video_config_params["seed"] = config.seed

            video_config = types.GenerateVideosConfig(**video_config_params)

            # Log extension request
            self.logger.info(f"Starting scene extension with {config.model.value}")
            self.logger.info(f"Config: {config.aspect_ratio}, duration={config.duration}s")
            self.logger.info(f"Note: Extended clips run at 720p regardless of original resolution")
            self.logger.info(f"Extension Prompt: {prompt}")

            # Generate extension using video parameter (passes previous clip for continuity)
            response = self.client.models.generate_videos(
                model=config.model.value,
                prompt=prompt,
                config=video_config,
                video=video_dict  # Previous video for continuity
            )

            # Store operation metadata
            result.operation_id = response.name
            result.metadata["model"] = config.model.value
            result.metadata["prompt"] = prompt
            result.metadata["started_at"] = datetime.now().isoformat()
            result.metadata["extension_of"] = str(previous_video_path)
            result.metadata["mode"] = "scene_extension"

            # Poll for completion
            max_wait = 480  # 8 minutes
            video_result = await self._poll_for_completion(response, max_wait)

            if video_result:
                if isinstance(video_result, bytes):
                    self.logger.info(f"Received extended video bytes, saving to local storage...")
                    result.video_path = await self._save_video_bytes(video_result)
                    result.success = True
                    result.metadata["source"] = "raw_bytes"
                elif isinstance(video_result, str):
                    result.video_url = video_result
                    result.success = True
                    result.video_path = await self._download_video(video_result)
                    result.metadata["retention_warning"] = "Video URLs expire after 2 days. Local copy saved."
                    result.metadata["expires_at"] = (datetime.now() + timedelta(days=2)).isoformat()
                    result.metadata["source"] = "url_download"
                else:
                    result.success = False
                    result.error = f"Unexpected result type: {type(video_result)}"
            else:
                result.success = False
                result.error = "Extension generation timed out or failed"

            result.generation_time = time.time() - start_time
            self.logger.info(f"Scene extension completed in {result.generation_time:.1f} seconds")

        except Exception as e:
            self.logger.error(f"Scene extension failed: {e}")
            result.success = False
            result.error = str(e)

        return result

    def extend_video(
        self,
        previous_video_path: Path,
        prompt: str,
        config: VeoGenerationConfig
    ) -> VeoGenerationResult:
        """
        Extend a previous video synchronously (blocking).

        Args:
            previous_video_path: Path to the video to extend
            prompt: Prompt for the new segment
            config: Generation configuration

        Returns:
            VeoGenerationResult with the extended clip
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.extend_video_async(previous_video_path, prompt, config)
            )
        finally:
            loop.close()

    async def _poll_for_completion(self, operation: Any, max_wait: int) -> Optional[Union[str, bytes]]:
        """
        Poll for video generation completion using official Google API pattern.

        Args:
            operation: Generation operation (LRO - Long Running Operation)
            max_wait: Maximum wait time in seconds

        Returns:
            Video URL if successful, None otherwise
        """
        start_time = time.time()
        poll_interval = 10  # Google docs recommend 10 second intervals
        poll_count = 0

        self.logger.info(f"Starting to poll for completion (max wait: {max_wait}s)")
        self.logger.info(f"Operation ID: {operation.name}")

        while time.time() - start_time < max_wait:
            try:
                elapsed = time.time() - start_time
                poll_count += 1

                # Log every poll attempt for first 5, then every 4th attempt
                if poll_count <= 5 or poll_count % 4 == 0:
                    self.logger.info(f"Poll #{poll_count}: Checking operation.done... ({elapsed:.0f}s elapsed, {max_wait - elapsed:.0f}s remaining)")

                # Check if operation is done (official Google pattern)
                if operation.done:
                    # Operation completed
                    elapsed_total = time.time() - start_time
                    self.logger.info(f"✅ Operation completed after {elapsed_total:.1f} seconds ({poll_count} polls)")

                    # Check for errors first
                    if hasattr(operation, 'error') and operation.error:
                        self.logger.error(f"❌ Operation failed with error: {operation.error}")
                        return None

                    # Extract video from response (official structure from docs)
                    try:
                        if hasattr(operation, 'response') and hasattr(operation.response, 'generated_videos'):
                            generated_videos = operation.response.generated_videos
                            if generated_videos and len(generated_videos) > 0:
                                video = generated_videos[0].video

                                # Try URI first (cloud storage URL)
                                if hasattr(video, 'uri') and video.uri:
                                    video_url = video.uri
                                    self.logger.info(f"Retrieved video URL: {video_url[:80] if len(video_url) > 80 else video_url}")

                                    # Parse and log video metadata if available
                                    if hasattr(video, 'metadata'):
                                        metadata = video.metadata
                                        self.logger.info(f"Video metadata: {metadata}")

                                    return video_url

                                # If no URI, check for video_bytes (raw video data)
                                elif hasattr(video, 'video_bytes') and video.video_bytes:
                                    video_bytes = video.video_bytes
                                    self.logger.info(f"Retrieved video as raw bytes ({len(video_bytes)} bytes)")

                                    # Parse and log video metadata if available
                                    if hasattr(video, 'metadata'):
                                        metadata = video.metadata
                                        self.logger.info(f"Video metadata: {metadata}")

                                    # Return the raw bytes - caller will need to save them
                                    return video_bytes

                                else:
                                    # Neither URI nor bytes available
                                    self.logger.error(f"Video object has neither 'uri' nor 'video_bytes'.")
                                    self.logger.error(f"  - has 'uri' attr: {hasattr(video, 'uri')}, value: {getattr(video, 'uri', '<no attr>')}")
                                    self.logger.error(f"  - has 'video_bytes' attr: {hasattr(video, 'video_bytes')}, value length: {len(getattr(video, 'video_bytes', b'')) if hasattr(video, 'video_bytes') else 0}")
                                    self.logger.error(f"  - video type: {type(video)}")
                                    return None
                            else:
                                self.logger.error("No generated_videos in response")
                                return None
                        else:
                            # Log detailed diagnostic information
                            self.logger.error(f"Unexpected response structure. Operation attributes: {dir(operation)}")
                            if hasattr(operation, 'response'):
                                self.logger.error(f"Response attributes: {dir(operation.response)}")
                                # Try to log the actual response value
                                try:
                                    self.logger.error(f"Response value: {operation.response}")
                                    self.logger.error(f"Response type: {type(operation.response)}")
                                except Exception as log_err:
                                    self.logger.error(f"Could not log response value: {log_err}")
                            if hasattr(operation, 'metadata'):
                                self.logger.error(f"Operation metadata: {operation.metadata}")
                            return None
                    except Exception as e:
                        self.logger.error(f"Error extracting video URL from completed operation: {e}", exc_info=True)
                        return None

                # Not done yet - wait and refresh operation status
                self.logger.debug(f"Poll #{poll_count}: Operation not done yet, waiting {poll_interval}s...")
                await asyncio.sleep(poll_interval)

                # Refresh operation status (official Google pattern)
                operation = self.client.operations.get(operation)

            except Exception as e:
                self.logger.error(f"Error polling for completion: {e}", exc_info=True)
                return None

        total_elapsed = time.time() - start_time
        self.logger.warning(f"❌ Generation timed out after {total_elapsed:.1f} seconds ({poll_count} polls, max: {max_wait}s)")
        return None
    
    async def _download_video(self, video_url: str) -> Optional[Path]:
        """
        Download video from URL to local storage with authentication.

        Args:
            video_url: URL of generated video

        Returns:
            Local path to downloaded video
        """
        try:
            # Create cache directory
            cache_dir = Path.home() / ".imageai" / "cache" / "veo_videos"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from URL hash
            url_hash = hashlib.sha256(video_url.encode()).hexdigest()[:16]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"veo_{timestamp}_{url_hash}.mp4"
            video_path = cache_dir / filename

            # Download video with API key authentication
            # For Google API keys (not OAuth), use key parameter instead of Bearer token
            # Remove any existing query parameters from URL and add our own
            base_url = video_url.split('?')[0]
            params = {
                "key": self.api_key,
                "alt": "media"  # Request media content
            }

            self.logger.info(f"Downloading video from {base_url[:80]}...")
            self.logger.info(f"Using API key authentication with key parameter")
            response = requests.get(base_url, params=params, stream=True, timeout=30, allow_redirects=True)
            response.raise_for_status()

            # Save to file
            file_size = 0
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    file_size += len(chunk)

            # Validate downloaded file (VEO3_FIXES enhancement)
            if file_size == 0:
                self.logger.error(f"Downloaded file is empty (0 bytes)")
                video_path.unlink(missing_ok=True)  # Delete empty file
                return None

            if not video_path.exists():
                self.logger.error(f"Video file was not created at {video_path}")
                return None

            actual_size = video_path.stat().st_size
            if actual_size != file_size:
                self.logger.warning(f"File size mismatch: wrote {file_size} bytes, file is {actual_size} bytes")

            self.logger.info(f"Video downloaded successfully to {video_path} ({file_size / (1024*1024):.2f} MB)")
            return video_path

        except requests.HTTPError as e:
            # Enhanced error logging for HTTP errors
            status_code = e.response.status_code if e.response else "unknown"
            error_body = e.response.text[:500] if e.response else "no response body"
            self.logger.error(f"HTTP error {status_code} downloading video: {error_body}")
            self.logger.error(f"Full exception: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Failed to download video: {e}", exc_info=True)
            return None

    async def _save_video_bytes(self, video_bytes: bytes) -> Optional[Path]:
        """
        Save raw video bytes to local storage.

        Args:
            video_bytes: Raw video data as bytes

        Returns:
            Local path to saved video
        """
        try:
            # Create cache directory
            cache_dir = Path.home() / ".imageai" / "cache" / "veo_videos"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from hash of video bytes
            video_hash = hashlib.sha256(video_bytes).hexdigest()[:16]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"veo_{timestamp}_{video_hash}.mp4"
            video_path = cache_dir / filename

            # Save bytes to file
            self.logger.info(f"Saving video bytes to {video_path}...")
            with open(video_path, 'wb') as f:
                f.write(video_bytes)

            # Validate saved file
            if not video_path.exists():
                self.logger.error(f"Video file was not created at {video_path}")
                return None

            actual_size = video_path.stat().st_size
            expected_size = len(video_bytes)

            if actual_size != expected_size:
                self.logger.error(f"File size mismatch: expected {expected_size} bytes, file is {actual_size} bytes")
                return None

            self.logger.info(f"Video saved successfully to {video_path} ({actual_size / (1024*1024):.2f} MB)")
            return video_path

        except Exception as e:
            self.logger.error(f"Failed to save video bytes: {e}", exc_info=True)
            return None

    def generate_batch(self,
                      configs: List[VeoGenerationConfig],
                      max_concurrent: int = 3) -> List[VeoGenerationResult]:
        """
        Generate multiple videos in batch with concurrency control.
        
        Args:
            configs: List of generation configurations
            max_concurrent: Maximum concurrent generations
            
        Returns:
            List of generation results
        """
        results = []
        
        # Process in batches to respect concurrency limit
        for i in range(0, len(configs), max_concurrent):
            batch = configs[i:i + max_concurrent]
            
            # Create async tasks for batch
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                tasks = [self.generate_video_async(config) for config in batch]
                batch_results = loop.run_until_complete(asyncio.gather(*tasks))
                results.extend(batch_results)
            finally:
                loop.close()
        
        return results
    
    def concatenate_clips(self,
                         video_paths: List[Path],
                         output_path: Path,
                         remove_audio: bool = True) -> bool:
        """
        Concatenate multiple Veo clips into a single video.
        
        Args:
            video_paths: List of video file paths
            output_path: Output video path
            remove_audio: Remove audio from Veo 3 clips
            
        Returns:
            Success status
        """
        try:
            # This would use FFmpeg to concatenate
            # Implementation would import ffmpeg_renderer
            from .ffmpeg_renderer import FFmpegRenderer
            
            renderer = FFmpegRenderer()
            
            # Create concat file
            concat_file = output_path.parent / "veo_concat.txt"
            with open(concat_file, 'w') as f:
                for path in video_paths:
                    f.write(f"file '{path.absolute()}'\n")
            
            # Build FFmpeg command
            import subprocess
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-fflags", "+genpts",  # Regenerate presentation timestamps for smooth playback
            ]

            if remove_audio:
                cmd.extend(["-an"])  # Remove audio stream

            cmd.extend(["-y", str(output_path)])
            
            subprocess.run(cmd, capture_output=True, check=True)
            concat_file.unlink()  # Clean up
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to concatenate videos: {e}")
            return False
    
    def estimate_cost(self, config: VeoGenerationConfig) -> float:
        """
        Estimate generation cost in USD based on October 2025 pricing.

        Pricing is per second of video generated.
        Audio generation doubles the cost for Veo 3.x models.

        Args:
            config: Generation configuration

        Returns:
            Estimated cost in USD
        """
        # October 2025 pricing - with audio (per second)
        pricing_with_audio = {
            VeoModel.VEO_3_1_GENERATE: 0.40,  # $0.40/sec with audio
            VeoModel.VEO_3_1_FAST: 0.15,      # $0.15/sec with audio
            VeoModel.VEO_3_GENERATE: 0.40,    # $0.40/sec with audio
            VeoModel.VEO_3_FAST: 0.15,        # $0.15/sec with audio
            VeoModel.VEO_2_GENERATE: 0.35,    # $0.35/sec (no audio support)
        }

        # October 2025 pricing - video only (per second)
        pricing_video_only = {
            VeoModel.VEO_3_1_GENERATE: 0.20,  # $0.20/sec video only
            VeoModel.VEO_3_1_FAST: 0.10,      # $0.10/sec video only
            VeoModel.VEO_3_GENERATE: 0.20,    # $0.20/sec video only
            VeoModel.VEO_3_FAST: 0.10,        # $0.10/sec video only
            VeoModel.VEO_2_GENERATE: 0.35,    # $0.35/sec (same with or without audio param)
        }

        # Select pricing based on audio setting
        if config.include_audio:
            cost_per_second = pricing_with_audio.get(config.model, 0.40)
        else:
            cost_per_second = pricing_video_only.get(config.model, 0.20)

        return config.duration * cost_per_second

    def estimate_cost_formatted(self, config: VeoGenerationConfig) -> str:
        """
        Get formatted cost estimate string.

        Args:
            config: Generation configuration

        Returns:
            Formatted cost string (e.g., "$3.20")
        """
        cost = self.estimate_cost(config)
        return f"${cost:.2f}"
    
    def get_model_info(self, model: VeoModel) -> Dict[str, Any]:
        """Get information about a Veo model"""
        constraints = self.MODEL_CONSTRAINTS.get(model, {})
        return {
            "name": model.value,
            "max_duration": constraints.get("max_duration", 8),
            "resolutions": constraints.get("resolutions", []),
            "aspect_ratios": constraints.get("aspect_ratios", []),
            "supports_audio": constraints.get("supports_audio", False),
            "generation_time": constraints.get("generation_time", (60, 360)),
            "person_generation_allowed": self.person_generation_allowed
        }