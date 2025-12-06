"""Google Gemini provider for image generation."""

import os
import subprocess
import platform
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from base64 import b64decode

logger = logging.getLogger(__name__)

# Check if google.genai is available but don't import yet
try:
    import importlib.util
    GENAI_AVAILABLE = importlib.util.find_spec("google.genai") is not None
except ImportError:
    GENAI_AVAILABLE = False

# These will be populated on first use
genai = None
types = None

from .base import ImageProvider

# Import rate_limiter with fallback for different import contexts
try:
    from ..core.security import rate_limiter
except ImportError:
    from core.security import rate_limiter

# Import image utilities
try:
    from ..core.image_utils import auto_crop_solid_borders, crop_to_aspect_ratio
except ImportError:
    try:
        from core.image_utils import auto_crop_solid_borders, crop_to_aspect_ratio
    except ImportError:
        # Fallback if image_utils doesn't exist yet
        auto_crop_solid_borders = None
        crop_to_aspect_ratio = None


def apply_transparent_canvas_fix(image_bytes: bytes, target_aspect_ratio: str, logger_instance=None, console_logger=None) -> bytes:
    """
    Apply transparent canvas fix to an image that doesn't match the target aspect ratio.

    Creates a transparent canvas with the correct aspect ratio and centers the original image on it.
    This ensures that Gemini receives images with the expected aspect ratio.

    Args:
        image_bytes: Original image data as bytes
        target_aspect_ratio: Target aspect ratio string (e.g., "16:9", "4:3", "1:1")
        logger_instance: Logger instance to use (defaults to module logger)
        console_logger: Optional callback for console messages (e.g., main_window._append_to_console)

    Returns:
        Processed image bytes with correct aspect ratio
    """
    from PIL import Image
    import io
    import time
    from pathlib import Path
    import platform
    import os

    log = logger_instance or logger

    try:
        # Open the image
        img = Image.open(io.BytesIO(image_bytes))
        ref_width, ref_height = img.size
        ref_aspect = ref_width / ref_height

        # Calculate expected aspect ratio
        expected_aspect = 1.0
        if target_aspect_ratio and ':' in target_aspect_ratio:
            ar_parts = target_aspect_ratio.split(':')
            expected_aspect = float(ar_parts[0]) / float(ar_parts[1])

        # Check if there's a significant mismatch (more than 10% difference)
        if abs(ref_aspect - expected_aspect) <= 0.1:
            # Aspect ratios match, no fix needed
            log.debug(f"Aspect ratio matches ({ref_aspect:.2f} ≈ {expected_aspect:.2f}), no canvas fix needed")
            return image_bytes

        log.info(f"Aspect ratio adjustment: Image is {ref_width}x{ref_height} "
                 f"(aspect {ref_aspect:.2f}) but requesting {target_aspect_ratio} "
                 f"(aspect {expected_aspect:.2f}). Applying canvas centering fix...")

        # Log to console if callback provided
        if console_logger:
            console_logger(
                f"📐 Reference image aspect ratio mismatch detected: {ref_width}x{ref_height} → {target_aspect_ratio}",
                "#FFA500"  # Orange
            )
            console_logger(
                f"   Centering image on transparent canvas to match target aspect ratio...",
                "#888888"  # Gray
            )

        # Create a transparent canvas with the target aspect ratio
        # Calculate canvas dimensions based on image max dimension
        max_ref_dim = max(ref_width, ref_height)

        # Calculate canvas dimensions maintaining target aspect ratio
        if expected_aspect >= 1.0:  # Landscape or square
            canvas_width = max_ref_dim
            canvas_height = int(max_ref_dim / expected_aspect)
        else:  # Portrait
            canvas_height = max_ref_dim
            canvas_width = int(max_ref_dim * expected_aspect)

        # Make sure canvas is large enough to contain the image
        if canvas_width < ref_width:
            canvas_width = ref_width
            canvas_height = int(ref_width / expected_aspect)
        if canvas_height < ref_height:
            canvas_height = ref_height
            canvas_width = int(ref_height * expected_aspect)

        log.info(f"Creating transparent canvas: {canvas_width}x{canvas_height} (aspect {expected_aspect:.2f})")
        log.info(f"Image will be centered: {ref_width}x{ref_height}")

        # Create transparent canvas
        canvas = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))

        # Calculate position to center the image
        x_offset = (canvas_width - ref_width) // 2
        y_offset = (canvas_height - ref_height) // 2

        # Convert image to RGBA if needed
        if img.mode != 'RGBA':
            img_rgba = img.convert('RGBA')
        else:
            img_rgba = img

        # Paste the image centered on the canvas
        canvas.paste(img_rgba, (x_offset, y_offset), img_rgba)

        # Convert canvas back to bytes
        output = io.BytesIO()
        canvas.save(output, format='PNG')
        processed_bytes = output.getvalue()

        log.info(f"Using composed canvas ({canvas_width}x{canvas_height}) instead of original image")

        # Log success to console
        if console_logger:
            console_logger(
                f"✓ Canvas created: {canvas_width}x{canvas_height}",
                "#00AA00"  # Green
            )

        return processed_bytes

    except Exception as e:
        log.error(f"Failed to apply transparent canvas fix: {e}")
        # Return original bytes on error
        return image_bytes


# Check if Google Cloud is available but don't import yet
try:
    import importlib.util
    GCLOUD_AVAILABLE = importlib.util.find_spec("google.cloud.aiplatform") is not None
except ImportError:
    GCLOUD_AVAILABLE = False

# These will be populated on first use
aiplatform = None
google_auth_default = None
DefaultCredentialsError = Exception


class GoogleProvider(ImageProvider):
    """Google Gemini provider for AI image generation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Google provider."""
        super().__init__(config)
        self.client = None
        self.project_id = None
        self._client_mode = None  # Track how client was initialized: "api_key" or "gcloud"

        # Multi-turn editing support (Nano Banana Pro)
        # Stores the last chat session for iterative refinement
        self._last_chat_session = None

        # Get config manager for auth state
        try:
            from ..core.config import ConfigManager
        except ImportError:
            from core.config import ConfigManager
        self.config_manager = ConfigManager()

        # Initialize client based on auth mode
        if self.auth_mode == "gcloud":
            # Check if we have cached auth validation
            if self.config_manager.get_auth_validated("google"):
                self.project_id = self.config_manager.get_gcloud_project_id()
            # Don't initialize gcloud client here - do it lazily in generate()
            # This allows auth checking without failing
        elif self.api_key:
            self._init_api_key_client()

    def get_last_chat_session(self):
        """
        Get the last chat session for multi-turn editing.

        Returns:
            The chat session object if available, None otherwise.
        """
        return self._last_chat_session

    def create_chat_session(self, model: str, aspect_ratio: str = None,
                            image_size: str = None, search_grounding: bool = False):
        """
        Create a new chat session for multi-turn image generation/editing.

        This is used by Nano Banana Pro for iterative refinement.
        The SDK handles thought signatures automatically when using chat.

        Args:
            model: Model ID (should be gemini-3-pro-image-preview for NBP)
            aspect_ratio: Optional aspect ratio for generated images
            image_size: Optional image size (1K, 2K, 4K)
            search_grounding: Whether to enable Google Search grounding

        Returns:
            Chat session object
        """
        global genai, types

        if not self.client:
            raise ValueError("Client not initialized")

        # Lazy import types
        if types is None:
            from google.genai import types

        # Build config for chat session
        config_kwargs = {
            'response_modalities': ['TEXT', 'IMAGE']
        }

        # Add image config if aspect ratio specified
        if aspect_ratio:
            try:
                config_kwargs['image_config'] = types.ImageConfig(aspect_ratio=aspect_ratio)
            except AttributeError:
                config_kwargs['image_config'] = {'aspect_ratio': aspect_ratio}

        # Add search grounding tool if enabled
        if search_grounding:
            try:
                grounding_tool = types.Tool(google_search=types.GoogleSearch())
                config_kwargs['tools'] = [grounding_tool]
            except AttributeError:
                logger.warning("Search grounding not available in this SDK version")

        # Create chat session
        config = types.GenerateContentConfig(**config_kwargs)

        chat = self.client.chats.create(model=model, config=config)
        self._last_chat_session = chat

        logger.info(f"Created chat session for multi-turn editing with model {model}")
        return chat
    
    def _init_api_key_client(self):
        """Initialize client with API key."""
        global genai, types
        
        if not GENAI_AVAILABLE:
            raise ImportError(
                "Google GenAI library not installed. "
                "Run: pip install google-generativeai"
            )
        
        # Lazy import on first use
        if genai is None:
            print("Loading Google AI provider...")
            from google import genai
            from google.genai import types
        
        if self.api_key:
            # Log masked API key for debugging
            key_len = len(self.api_key)
            masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if key_len > 8 else "***"
            logger.info(f"Initializing Google client with API key: length={key_len}, key={masked_key}")
            self.client = genai.Client(api_key=self.api_key)
            self._client_mode = "api_key"
        else:
            logger.warning("_init_api_key_client called but no API key set!")
    
    def _init_gcloud_client(self, raise_on_error=True):
        """Initialize client with Google Cloud authentication.
        
        Args:
            raise_on_error: If True, raise exception on auth failure. If False, return False.
        """
        global aiplatform, google_auth_default, DefaultCredentialsError, genai, types
        
        if not GCLOUD_AVAILABLE:
            if raise_on_error:
                raise ImportError(
                    "Google Cloud AI Platform not installed. "
                    "Run: pip install google-cloud-aiplatform"
                )
            return False
        
        # Lazy import Google Cloud on first use
        if aiplatform is None:
            print("Loading Google Cloud AI provider...")
            from google.cloud import aiplatform
            from google.auth import default as google_auth_default
            from google.auth.exceptions import DefaultCredentialsError
        
        # Also ensure genai is imported for gcloud mode
        if genai is None:
            from google import genai
            from google.genai import types
        
        try:
            # Get Application Default Credentials
            credentials, project = google_auth_default()
            if not project:
                project = self._get_gcloud_project_id()
            if not project:
                if raise_on_error:
                    raise ValueError(
                        "No Google Cloud project found. "
                        "Set a project with: gcloud config set project YOUR_PROJECT_ID"
                    )
                return False
            
            self.project_id = project
            # Initialize aiplatform
            aiplatform.init(project=project, location="us-central1")

            # Create genai client in Vertex AI mode
            # Must specify vertexai=True to use ADC and Google Cloud project
            self.client = genai.Client(
                vertexai=True,
                project=project,
                location="us-central1"
            )
            self._client_mode = "gcloud"
            return True
            
        except DefaultCredentialsError as e:
            if raise_on_error:
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
            return False
    
    def _get_gcloud_project_id(self) -> Optional[str]:
        """Get the current Google Cloud project ID."""
        try:
            # Fast path: Read directly from gcloud config file
            from pathlib import Path
            import configparser

            # Check gcloud config locations
            config_paths = [
                Path.home() / ".config" / "gcloud" / "configurations" / "config_default",  # Linux/WSL
                Path.home() / "snap" / "google-cloud-cli" / "common" / ".config" / "gcloud" / "configurations" / "config_default",  # Linux snap install
                Path.home() / "AppData" / "Roaming" / "gcloud" / "configurations" / "config_default",  # Windows
            ]
            
            for config_path in config_paths:
                if config_path.exists():
                    try:
                        config = configparser.ConfigParser()
                        config.read(config_path)
                        if 'core' in config and 'project' in config['core']:
                            return config['core']['project']
                    except Exception:
                        continue
            
            # Fallback: Try subprocess if config file not found
            gcloud_cmd = "gcloud.cmd" if platform.system() == "Windows" else "gcloud"
            result = subprocess.run(
                [gcloud_cmd, "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=2,  # Reduced timeout
                shell=False
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        except Exception:
            # Broader exception handling for various subprocess issues
            pass
        return None
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Generate images using Google Gemini models."""
        # Check if client needs re-initialization due to auth mode change
        # This handles the case where user switches between gcloud and API key at runtime
        expected_mode = "gcloud" if self.auth_mode == "gcloud" else "api_key"
        if self.client and self._client_mode != expected_mode:
            logger.info(f"Auth mode changed from {self._client_mode} to {expected_mode}, reinitializing client")
            self.client = None
            self._client_mode = None

        if not self.client:
            if self.auth_mode == "gcloud":
                # Try to initialize gcloud client, raise error if it fails
                self._init_gcloud_client(raise_on_error=True)
            else:
                # Initialize API key client
                if not self.api_key:
                    raise ValueError("No API key configured for Google provider")
                self._init_api_key_client()

        model = model or self.get_default_model()

        # Log authentication method being used
        if self.auth_mode == "gcloud":
            logger.info("=" * 60)
            logger.info("GOOGLE AUTHENTICATION: Using Google Cloud (gcloud) credentials")
            if self.project_id:
                logger.info(f"Google Cloud Project ID: {self.project_id}")
            logger.info("=" * 60)
        else:
            logger.info("=" * 60)
            logger.info("GOOGLE AUTHENTICATION: Using API Key")
            logger.info("=" * 60)

        # Only apply rate limiting for API key mode (Google Cloud has its own quotas)
        if self.auth_mode != "gcloud":
            rate_limiter.check_rate_limit('google', wait=True)
        
        texts: List[str] = []
        images: List[bytes] = []

        # Retry configuration for NO_IMAGE errors (transient API issues)
        max_retries = 3
        retry_delay = 2  # seconds between retries

        # Build generation config for Gemini models
        # Updated: Google Gemini now supports aspect_ratio via image_config parameter
        # Must use types.GenerateContentConfig for the new SDK
        from google.genai import types

        config_params = {}

        # Get dimensions for resolution quality hints and cropping
        width = kwargs.get('width')
        height = kwargs.get('height')
        aspect_ratio = kwargs.get('aspect_ratio')
        crop_to_aspect = kwargs.get('crop_to_aspect', False)  # Only crop if explicitly requested

        # If aspect_ratio is provided without dimensions, calculate them
        if aspect_ratio and not (width and height):
            # Use 1024 as base size
            base_size = 1024
            if aspect_ratio == '16:9':
                width, height = 1024, 576  # Maintain 1024 width
            elif aspect_ratio == '9:16':
                width, height = 576, 1024  # Maintain 1024 height
            elif aspect_ratio == '4:3':
                width, height = 1024, 768
            elif aspect_ratio == '3:4':
                width, height = 768, 1024
            elif aspect_ratio == '21:9':
                width, height = 1024, 439
            elif aspect_ratio == '1:1':
                width, height = 1024, 1024

        # Gemini outputs 1024x1024 by default (always square)
        # We can add quality hints based on requested resolution
        resolution_hint = ""
        if width or height:
            # If width or height specified, use them to hint at resolution
            target_size = max(width or 1024, height or 1024)
            if target_size > 1536:
                resolution_hint = "high resolution, 4K quality"
            elif target_size > 1024:
                resolution_hint = "high quality, detailed"
            else:
                resolution_hint = "crisp and clear"

        # Store original dimensions for later upscaling/cropping
        original_width = width
        original_height = height

        # Determine max resolution based on model
        # Nano Banana Pro (gemini-3-pro-image-preview) supports up to 4K output
        # Regular Nano Banana (gemini-2.5-flash-image) is capped at 1024px
        is_nano_banana_pro = model and "gemini-3" in model

        if is_nano_banana_pro:
            # Auto-determine output_quality from requested dimensions
            # This allows users to just set dimensions and get the right quality tier
            max_dim = max(width or 1024, height or 1024)
            if max_dim <= 1024:
                output_quality = '1k'
                max_output_dim = 1024
            elif max_dim <= 2048:
                output_quality = '2k'
                max_output_dim = 2048
            else:
                output_quality = '4k'
                max_output_dim = 4096

            # Allow explicit override if provided
            explicit_quality = kwargs.get('output_quality')
            if explicit_quality:
                output_quality = explicit_quality.lower()
                quality_max_dims = {'1k': 1024, '2k': 2048, '4k': 4096}
                max_output_dim = quality_max_dims.get(output_quality, max_output_dim)

            logger.info(f"Nano Banana Pro: {output_quality.upper()} quality tier (max {max_output_dim}px) for {width}x{height}")
        else:
            # Standard Nano Banana is capped at 1024
            max_output_dim = 1024
            output_quality = '1k'

        # For Gemini, only scale if dimensions exceed model's native capability
        # No longer force scaling to 1024 - let the model handle its native resolution
        if width and height:
            # Always store original target dimensions for post-processing
            kwargs['_target_width'] = original_width
            kwargs['_target_height'] = original_height

            max_dim = max(width, height)

            # Only scale if dimensions exceed model's native capability
            if max_dim > max_output_dim:
                # Scale proportionally so max dimension fits model capability
                scale_factor = max_output_dim / max_dim
                scaled_width = int(width * scale_factor)
                scaled_height = int(height * scale_factor)

                logger.info(f"Scaling for Gemini: {width}x{height} -> {scaled_width}x{scaled_height} (exceeds {max_output_dim}px max)")

                width = scaled_width
                height = scaled_height
                # Store that we need to upscale the result back to requested size
                kwargs['_needs_upscale'] = True
                kwargs['_needs_downscale'] = False
            else:
                # Model can handle this resolution natively - no scaling needed
                kwargs['_needs_upscale'] = False
                kwargs['_needs_downscale'] = False
                logger.info(f"Using native resolution: {width}x{height} (within {max_output_dim}px max)")

        # Calculate aspect ratio from dimensions if not provided
        # Note: We no longer add dimensions to the prompt text as it gets rendered as literal text
        # Instead, we rely solely on the image_config parameter below
        # IMPORTANT: Gemini only supports these aspect ratios:
        # '1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'
        if width and height and not aspect_ratio:
            ratio = width / height
            # Valid Gemini aspect ratios with their decimal values
            valid_ratios = [
                ("1:1", 1.0),
                ("21:9", 21/9),    # 2.33 - ultrawide
                ("16:9", 16/9),    # 1.78 - widescreen
                ("3:2", 3/2),      # 1.5
                ("4:3", 4/3),      # 1.33
                ("5:4", 5/4),      # 1.25
                ("4:5", 4/5),      # 0.8
                ("3:4", 3/4),      # 0.75
                ("2:3", 2/3),      # 0.67
                ("9:16", 9/16),    # 0.5625 - portrait widescreen
            ]
            # Find the closest valid aspect ratio
            closest_ratio = min(valid_ratios, key=lambda x: abs(ratio - x[1]))
            aspect_ratio = closest_ratio[0]
            logger.info(f"Mapped {width}x{height} (ratio {ratio:.3f}) to closest valid Gemini aspect ratio: {aspect_ratio} ({closest_ratio[1]:.3f})")

        # Calculate default dimensions if we have aspect ratio but no dimensions
        # All valid Gemini aspect ratios with max dimension of 1024px
        if aspect_ratio and not (width and height):
            aspect_ratio_dimensions = {
                '1:1': (1024, 1024),
                '21:9': (1024, 439),   # 1024 / (21/9) = 439
                '16:9': (1024, 576),
                '3:2': (1024, 683),    # 1024 / 1.5 = 683
                '4:3': (1024, 768),
                '5:4': (1024, 819),    # 1024 / 1.25 = 819
                '4:5': (819, 1024),    # 1024 * 0.8 = 819
                '3:4': (768, 1024),
                '2:3': (683, 1024),
                '9:16': (576, 1024),
            }
            width, height = aspect_ratio_dimensions.get(aspect_ratio, (1024, 1024))

        # Log what we're sending (but don't add dimensions to prompt)
        if aspect_ratio:
            logger.info(f"Sending to Gemini with aspect ratio {aspect_ratio} via image_config (target: {width}x{height})")
        else:
            logger.info(f"Sending to Gemini with default resolution (no aspect ratio specified)")

        if resolution_hint and aspect_ratio == "1:1":
            # For square images, we can still add quality hints
            prompt = f"{prompt}. {resolution_hint}."

        # Build config using new SDK types
        # Safety settings - convert string to proper SafetySetting list
        if kwargs.get('safety_filter'):
            safety_filter = kwargs['safety_filter']

            # Map UI strings to HarmBlockThreshold enums
            threshold_map = {
                'Block most': types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                'Block some': types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                'Block few': types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                'Block fewest': types.HarmBlockThreshold.BLOCK_NONE,
                # Also support lowercase with underscores from settings
                'block_most': types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                'block_some': types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                'block_few': types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                'block_fewest': types.HarmBlockThreshold.BLOCK_NONE,
            }

            # If it's a string (from UI), convert to SafetySetting list
            if isinstance(safety_filter, str):
                threshold = threshold_map.get(safety_filter, types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)

                # Apply to all harm categories
                config_params['safety_settings'] = [
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=threshold
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=threshold
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=threshold
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=threshold
                    ),
                ]
            else:
                # Assume it's already a list of SafetySettings
                config_params['safety_settings'] = safety_filter

        # Seed for reproducibility
        # Only pass positive seeds - Gemini may reject negative values
        seed = kwargs.get('seed')
        if seed is not None and seed >= 0:
            config_params['seed'] = seed
        elif seed is not None and seed < 0:
            logger.debug(f"Ignoring negative seed value: {seed}")

        # Number of images - may work with some models
        num_images = kwargs.get('num_images', 1)
        if num_images > 1:
            config_params['candidate_count'] = num_images

        # Search Grounding - enables real-time Google Search for factual accuracy
        # Useful for prompts about current events, real places, or recent data
        search_grounding = kwargs.get('search_grounding', False)
        if search_grounding:
            try:
                grounding_tool = types.Tool(google_search=types.GoogleSearch())
                config_params['tools'] = [grounding_tool]
                logger.info("Search Grounding enabled: Real-time Google Search will inform image generation")
            except AttributeError as e:
                logger.warning(f"Search Grounding not available in this SDK version: {e}")

        # Store NBP image_size for use in ImageConfig below
        # NOTE: image_size controls OUTPUT resolution (1K, 2K, 4K) and works with both API key and gcloud
        # This is different from media_resolution which controls INPUT image processing tokens
        nbp_image_size = None
        if is_nano_banana_pro:
            # Map our internal quality tier to API image_size values (must be uppercase)
            nbp_image_size = output_quality.upper()  # '1K', '2K', or '4K'
            logger.info(f"Nano Banana Pro: Will set image_size={nbp_image_size} for {output_quality.upper()} quality output")

        # Create the proper config object using types
        # This is required for aspect_ratio to work with the new SDK
        # Try to use ImageConfig if available, otherwise fall back to dict
        if aspect_ratio:
            logger.info(f"Using Gemini aspect ratio: {aspect_ratio} (target dimensions: {width}x{height})")
            logger.info(f"Setting image_config with aspect_ratio={aspect_ratio}")

            # Try to use types.ImageConfig if it exists, otherwise use dict format
            config = None
            config_created = False

            # First attempt: Try using ImageConfig class if it exists
            if hasattr(types, 'ImageConfig'):
                try:
                    logger.info("Attempting to use types.ImageConfig class")
                    # Build ImageConfig with aspect_ratio and optional image_size for NBP
                    image_config_kwargs = {'aspect_ratio': aspect_ratio}
                    if nbp_image_size:
                        image_config_kwargs['image_size'] = nbp_image_size
                        logger.info(f"Adding image_size={nbp_image_size} to ImageConfig for NBP output resolution")
                    config = types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(**image_config_kwargs),
                        **config_params
                    )
                    config_created = True
                    logger.info(f"Successfully created config with ImageConfig (image_size={nbp_image_size})")
                except Exception as e:
                    logger.warning(f"Failed to use ImageConfig class: {e}")

            # Second attempt: Try dict format
            if not config_created:
                try:
                    logger.info("Attempting dict format for image_config")
                    # Build image_config dict with aspect_ratio and optional image_size for NBP
                    image_config_dict = {"aspect_ratio": aspect_ratio}
                    if nbp_image_size:
                        image_config_dict["image_size"] = nbp_image_size
                        logger.info(f"Adding image_size={nbp_image_size} to dict config for NBP output resolution")
                    config = types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=image_config_dict,
                        **config_params
                    )
                    config_created = True
                    logger.info(f"Successfully created config with dict format (image_size={nbp_image_size})")
                except Exception as e:
                    logger.warning(f"Failed to use dict format: {e}")

            # Final fallback: Config without image_config, add dimensions to prompt
            if not config_created:
                logger.warning(f"Could not configure aspect ratio in config. Will add dimensions to prompt as fallback.")
                config = types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    **config_params
                )
                # Add dimensions to prompt for models that don't support image_config
                if width and height and aspect_ratio != "1:1":
                    prompt = f"{prompt} ({width}x{height})"
                    logger.info(f"Added dimensions to prompt: {prompt}")
        else:
            # No aspect ratio specified, use basic config
            logger.info(f"No aspect ratio specified, using default")
            # Still add image_size for NBP if available
            if nbp_image_size:
                try:
                    image_config_dict = {"image_size": nbp_image_size}
                    logger.info(f"Adding image_size={nbp_image_size} for NBP (no aspect ratio)")
                    config = types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=image_config_dict,
                        **config_params
                    )
                except Exception as e:
                    logger.warning(f"Failed to set image_size without aspect_ratio: {e}")
                    config = types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        **config_params
                    ) if config_params else None
            else:
                config = types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    **config_params
                ) if config_params else None

        # Handle reference image(s) if provided
        reference_image = kwargs.get('reference_image')  # Single image (existing)
        reference_images = kwargs.get('reference_images')  # Multiple images (new - list)
        contents = prompt  # Default to just the text prompt

        if reference_images:
            # Multiple reference images - add each to contents list
            try:
                from PIL import Image
                import io

                contents = []
                for i, ref_bytes in enumerate(reference_images):
                    if isinstance(ref_bytes, bytes):
                        img = Image.open(io.BytesIO(ref_bytes))
                    else:
                        img = ref_bytes
                    contents.append(img)
                    logger.info(f"Added reference image {i + 1}/{len(reference_images)}: {img.size if hasattr(img, 'size') else 'unknown size'}")

                contents.append(prompt)  # Prompt at the end
                logger.info(f"Using {len(reference_images)} reference images for generation (direct mode)")
            except Exception as e:
                logger.warning(f"Failed to process reference images: {e}")
                # Fall back to text-only prompt
                contents = prompt
        elif reference_image:
            # Create multimodal content with reference image
            try:
                from PIL import Image
                import io

                # Convert bytes to PIL Image if needed
                if isinstance(reference_image, bytes):
                    img = Image.open(io.BytesIO(reference_image))
                else:
                    img = reference_image

                # Check for aspect ratio mismatch with reference image
                if hasattr(img, 'size'):
                    ref_width, ref_height = img.size
                    ref_aspect = ref_width / ref_height

                    # Calculate expected aspect ratio
                    expected_aspect = 1.0
                    if aspect_ratio and ':' in aspect_ratio:
                        ar_parts = aspect_ratio.split(':')
                        expected_aspect = float(ar_parts[0]) / float(ar_parts[1])
                    elif width and height:
                        expected_aspect = width / height

                    # Check if there's a significant mismatch (more than 10% difference)
                    if abs(ref_aspect - expected_aspect) > 0.1:
                        ar_display = aspect_ratio if aspect_ratio else f"{width}:{height}"
                        logger.info(f"Aspect ratio adjustment: Reference image is {ref_width}x{ref_height} "
                                    f"(aspect {ref_aspect:.2f}) but requesting {ar_display} "
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

                        # Use the composed canvas instead of original image
                        img = canvas
                        logger.info(f"Using composed canvas ({canvas_width}x{canvas_height}) instead of original reference image")

                # Create content list with image and prompt
                contents = [img, prompt]
                logger.info("Using reference image for generation")
            except Exception as e:
                logger.warning(f"Failed to process reference image: {e}")
                # Fall back to text-only prompt
                contents = prompt

        # Retry loop for handling transient NO_IMAGE errors
        attempt = 0
        no_image_error = False

        try:
            while attempt < max_retries:
                attempt += 1

                # Log the full request being sent to Gemini
                logger.info("=" * 60)
                if attempt > 1:
                    logger.info(f"RETRYING GOOGLE GEMINI API (attempt {attempt}/{max_retries})")
                else:
                    logger.info(f"SENDING TO GOOGLE GEMINI API")
                logger.info(f"Model: {model}")
                if isinstance(contents, str):
                    logger.info(f"Prompt: {contents}")
                elif isinstance(contents, list):
                    for item in contents:
                        if isinstance(item, str):
                            logger.info(f"Prompt: {item}")
                        else:
                            logger.info(f"Additional content: {type(item)}")
                if config:
                    logger.info(f"Generation config: {config}")
                logger.info("=" * 60)

                # Call API with proper config parameter for new SDK
                if config:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config
                    )
                else:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                    )

                # Check for NO_IMAGE error before processing candidates
                no_image_error = False
                if response and response.candidates:
                    for cand in response.candidates:
                        if hasattr(cand, 'finish_reason'):
                            finish_reason_str = str(cand.finish_reason)
                            if 'NO_IMAGE' in finish_reason_str:
                                no_image_error = True
                                logger.warning(f"⚠ Attempt {attempt}/{max_retries}: Gemini returned NO_IMAGE (transient error)")
                                break

                # If NO_IMAGE error and we have retries left, wait and retry
                if no_image_error and attempt < max_retries:
                    logger.info(f"⏳ Waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
                    continue

                # If we got here without NO_IMAGE error, or we're out of retries, break the loop
                break

            if response and response.candidates:
                # Process all candidates (for multiple images)
                logger.info(f"DEBUG: Response has {len(response.candidates)} candidates")
                for cand_idx, cand in enumerate(response.candidates):
                    if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                        logger.info(f"DEBUG: Candidate {cand_idx} has {len(cand.content.parts)} parts")
                        for part_idx, part in enumerate(cand.content.parts):
                            if getattr(part, "text", None):
                                logger.info(f"DEBUG: Part {part_idx} is text: {part.text[:100]}...")
                                texts.append(part.text)
                            elif getattr(part, "inline_data", None) is not None:
                                logger.info(f"DEBUG: Part {part_idx} is inline_data (image)")
                                data = getattr(part.inline_data, "data", None)
                                if isinstance(data, (bytes, bytearray)):
                                    image_bytes = bytes(data)
                                    logger.info(f"DEBUG: Got image data of {len(image_bytes)} bytes")

                                    # Debug: Check what we actually got from Gemini
                                    from PIL import Image
                                    import io
                                    import time
                                    from pathlib import Path
                                    import platform

                                    # Detect original image format
                                    img_stream = io.BytesIO(image_bytes)
                                    debug_img = Image.open(img_stream)
                                    original_format = debug_img.format or 'PNG'  # Default to PNG if format not detected
                                    logger.info(f"DEBUG: Gemini returned {original_format} image with dimensions: {debug_img.size}")

                                    # Save raw Gemini output for debugging
                                    if platform.system() == "Windows":
                                        debug_dir = Path("C:/Users/aboog/AppData/Roaming/ImageAI/generated")
                                    else:
                                        debug_dir = Path.home() / ".config" / "ImageAI" / "generated"

                                    # Save in original format
                                    ext = original_format.lower()
                                    if ext == 'jpeg':
                                        ext = 'jpg'
                                    debug_path = debug_dir / f"DEBUG_RAW_GEMINI_{int(time.time())}.{ext}"
                                    debug_dir.mkdir(parents=True, exist_ok=True)
                                    debug_img.save(str(debug_path), format=original_format)
                                    logger.info(f"DEBUG: Saved raw Gemini output to: {debug_path}")
                                    debug_img = None  # Clear to avoid confusion

                                    # Handle scaling back to original dimensions if we have target dimensions
                                    target_w = kwargs.get('_target_width')
                                    target_h = kwargs.get('_target_height')
                                    if target_w and target_h:
                                        # Check if we need to post-process (different dimensions than target)
                                        img = Image.open(io.BytesIO(image_bytes))
                                        current_w, current_h = img.size

                                        # Don't crop if Gemini returned larger than 1024px (e.g., 1500x700)
                                        # Per updated guide, Gemini can sometimes return larger images
                                        max_current = max(current_w, current_h)
                                        max_target = max(target_w, target_h)

                                        if max_current > 1024 and max_current > max_target:
                                            # Gemini returned larger than 1024 and larger than target - use as-is
                                            logger.info(f"Gemini returned larger image ({current_w}x{current_h}), using as-is without cropping")
                                            # Don't modify image_bytes, use the original
                                        elif current_w != target_w or current_h != target_h:
                                            logger.info(f"Post-processing Gemini output: {current_w}x{current_h} -> {target_w}x{target_h}")

                                            # Check aspect ratio of returned image vs target
                                            current_aspect = current_w / current_h
                                            target_aspect = target_w / target_h
                                            aspect_tolerance = 0.01  # 1% tolerance

                                            image_modified = False  # Track if we need to save
                                            if abs(current_aspect - target_aspect) > aspect_tolerance:
                                                # Aspect ratios don't match - need to crop first
                                                logger.info(f"Aspect ratio mismatch: Gemini returned {current_aspect:.3f}, user wants {target_aspect:.3f}")

                                                # Crop to match target aspect ratio
                                                if target_aspect > current_aspect:  # Target is wider
                                                    # Crop height to match aspect
                                                    new_h = int(current_w / target_aspect)
                                                    crop_top = (current_h - new_h) // 2
                                                    img = img.crop((0, crop_top, current_w, crop_top + new_h))
                                                else:  # Target is taller
                                                    # Crop width to match aspect
                                                    new_w = int(current_h * target_aspect)
                                                    crop_left = (current_w - new_w) // 2
                                                    img = img.crop((crop_left, 0, crop_left + new_w, current_h))
                                                logger.info(f"Cropped to aspect ratio: {img.size}")
                                                # Update dimensions after aspect crop
                                                current_w, current_h = img.size
                                                # After aspect crop, we must scale to target (aspect ratio was different)
                                                img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                                image_modified = True
                                                if current_w > target_w or current_h > target_h:
                                                    logger.info(f"Downscaled to target dimensions: {target_w}x{target_h}")
                                                else:
                                                    logger.info(f"Upscaled to target dimensions: {target_w}x{target_h}")
                                            else:
                                                # Same aspect ratio - scale to target dimensions
                                                if current_w != target_w or current_h != target_h:
                                                    # Always scale to exact target size
                                                    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                                    if current_w > target_w:
                                                        logger.info(f"Downscaled to target dimensions: {target_w}x{target_h}")
                                                    else:
                                                        logger.info(f"Upscaled to target dimensions: {target_w}x{target_h}")
                                                    image_modified = True
                                                else:
                                                    # Exact match - no modification needed
                                                    image_modified = False

                                            # Convert back to bytes in original format (only if image was modified)
                                            if image_modified:
                                                output = io.BytesIO()
                                                # Preserve original format if available
                                                save_format = original_format if 'original_format' in locals() else 'PNG'
                                                # Use appropriate options for format
                                                if save_format in ['JPEG', 'JPG']:
                                                    img.save(output, format='JPEG', quality=95, optimize=True)
                                                else:
                                                    img.save(output, format=save_format)
                                                image_bytes = output.getvalue()
                                                logger.info(f"Saved processed image in {save_format} format")

                                    # Apply additional cropping only if aspect ratio doesn't match
                                    elif crop_to_aspect and width and height and width != height and crop_to_aspect_ratio:
                                        # Check if returned image already matches the desired aspect ratio
                                        img = Image.open(io.BytesIO(image_bytes))
                                        current_w, current_h = img.size
                                        current_aspect = current_w / current_h
                                        target_aspect = width / height

                                        # Allow 1% tolerance for aspect ratio comparison
                                        aspect_tolerance = 0.01
                                        if abs(current_aspect - target_aspect) > aspect_tolerance:
                                            logger.debug(f"Image aspect ratio {current_aspect:.3f} doesn't match target {target_aspect:.3f}, cropping to {width}x{height}")
                                            image_bytes = crop_to_aspect_ratio(image_bytes, width, height)
                                        else:
                                            logger.info(f"Image aspect ratio {current_aspect:.3f} matches target {target_aspect:.3f}, skipping crop")

                                    images.append(image_bytes)
                    else:
                        # Log why candidate was skipped
                        logger.warning(f"DEBUG: Candidate {cand_idx} skipped - missing content or parts")
                        if hasattr(cand, 'finish_reason'):
                            logger.warning(f"DEBUG: Candidate {cand_idx} finish_reason: {cand.finish_reason}")
                        if hasattr(cand, 'safety_ratings'):
                            logger.warning(f"DEBUG: Candidate {cand_idx} safety_ratings: {cand.safety_ratings}")
                        if not getattr(cand, "content", None):
                            logger.warning(f"DEBUG: Candidate {cand_idx} has no content (likely blocked by safety filter)")
                        elif not getattr(cand.content, "parts", None):
                            logger.warning(f"DEBUG: Candidate {cand_idx} has content but no parts")
        except Exception as e:
            # Log the error that triggered fallback
            logger.error(f"Primary generation failed with error: {e}")
            logger.error(f"Error type: {type(e).__name__}")

            # Extract the best error message available
            error_message = None
            if hasattr(e, 'message') and e.message:
                error_message = e.message
                logger.error(f"Error message: {e.message}")
            if hasattr(e, 'code'):
                logger.error(f"Error code: {e.code}")
            if hasattr(e, 'details') and e.details:
                logger.error(f"Error details: {e.details}")
                if not error_message:
                    error_message = str(e.details)

            # Use the extracted message or fall back to str(e)
            if not error_message:
                error_message = str(e)

            # Check for network/connection errors that should fail immediately (no retry)
            # These errors indicate server-side issues that won't be fixed by retrying
            error_type = type(e).__name__
            error_str = str(e).lower()

            # Network errors that should fail fast
            network_errors = [
                'RemoteProtocolError',
                'ConnectError',
                'ConnectTimeout',
                'ReadTimeout',
                'WriteTimeout',
                'PoolTimeout',
                'NetworkError',
                'ConnectionError',
            ]

            if error_type in network_errors or 'disconnected' in error_str or 'connection' in error_str:
                logger.error(f"Network error detected ({error_type}) - failing immediately without retry")
                raise RuntimeError(f"{error_message}")

            logger.warning(f"Attempting fallback with config included...")

            # Fallback: try again with config (maybe first attempt had transient issue)
            try:
                if config:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config
                    )
                else:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                    )
                
                if response and response.candidates:
                    logger.info(f"DEBUG (fallback): Response has {len(response.candidates)} candidates")
                    cand = response.candidates[0]
                    if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                        logger.info(f"DEBUG (fallback): Candidate 0 has {len(cand.content.parts)} parts")
                        for part_idx, part in enumerate(cand.content.parts):
                            if getattr(part, "text", None):
                                logger.info(f"DEBUG (fallback): Part {part_idx} is text: {part.text[:100]}...")
                                texts.append(part.text)
                            elif getattr(part, "inline_data", None) is not None:
                                logger.info(f"DEBUG (fallback): Part {part_idx} is inline_data (image)")
                                data = getattr(part.inline_data, "data", None)
                                if isinstance(data, (bytes, bytearray)):
                                    image_bytes = bytes(data)
                                    logger.info(f"DEBUG (fallback): Got image data of {len(image_bytes)} bytes")

                                    # Debug: Check what we actually got from Gemini
                                    from PIL import Image
                                    import io
                                    import time
                                    from pathlib import Path
                                    import platform

                                    # Detect original image format
                                    img_stream = io.BytesIO(image_bytes)
                                    debug_img = Image.open(img_stream)
                                    original_format = debug_img.format or 'PNG'  # Default to PNG if format not detected
                                    logger.info(f"DEBUG: Gemini returned {original_format} image with dimensions: {debug_img.size}")

                                    # Save raw Gemini output for debugging
                                    if platform.system() == "Windows":
                                        debug_dir = Path("C:/Users/aboog/AppData/Roaming/ImageAI/generated")
                                    else:
                                        debug_dir = Path.home() / ".config" / "ImageAI" / "generated"

                                    # Save in original format
                                    ext = original_format.lower()
                                    if ext == 'jpeg':
                                        ext = 'jpg'
                                    debug_path = debug_dir / f"DEBUG_RAW_GEMINI_{int(time.time())}.{ext}"
                                    debug_dir.mkdir(parents=True, exist_ok=True)
                                    debug_img.save(str(debug_path), format=original_format)
                                    logger.info(f"DEBUG: Saved raw Gemini output to: {debug_path}")
                                    debug_img = None  # Clear to avoid confusion

                                    # Handle scaling back to original dimensions if we have target dimensions
                                    target_w = kwargs.get('_target_width')
                                    target_h = kwargs.get('_target_height')
                                    if target_w and target_h:
                                        # Check if we need to post-process (different dimensions than target)
                                        img = Image.open(io.BytesIO(image_bytes))
                                        current_w, current_h = img.size

                                        # Don't crop if Gemini returned larger than 1024px (e.g., 1500x700)
                                        # Per updated guide, Gemini can sometimes return larger images
                                        max_current = max(current_w, current_h)
                                        max_target = max(target_w, target_h)

                                        if max_current > 1024 and max_current > max_target:
                                            # Gemini returned larger than 1024 and larger than target - use as-is
                                            logger.info(f"Gemini returned larger image ({current_w}x{current_h}), using as-is without cropping")
                                            # Don't modify image_bytes, use the original
                                        elif current_w != target_w or current_h != target_h:
                                            logger.info(f"Post-processing Gemini output: {current_w}x{current_h} -> {target_w}x{target_h}")

                                            # Check aspect ratio of returned image vs target
                                            current_aspect = current_w / current_h
                                            target_aspect = target_w / target_h
                                            aspect_tolerance = 0.01  # 1% tolerance

                                            image_modified = False  # Track if we need to save
                                            if abs(current_aspect - target_aspect) > aspect_tolerance:
                                                # Aspect ratios don't match - need to crop first
                                                logger.info(f"Aspect ratio mismatch: Gemini returned {current_aspect:.3f}, user wants {target_aspect:.3f}")

                                                # Crop to match target aspect ratio
                                                if target_aspect > current_aspect:  # Target is wider
                                                    # Crop height to match aspect
                                                    new_h = int(current_w / target_aspect)
                                                    crop_top = (current_h - new_h) // 2
                                                    img = img.crop((0, crop_top, current_w, crop_top + new_h))
                                                else:  # Target is taller
                                                    # Crop width to match aspect
                                                    new_w = int(current_h * target_aspect)
                                                    crop_left = (current_w - new_w) // 2
                                                    img = img.crop((crop_left, 0, crop_left + new_w, current_h))
                                                logger.info(f"Cropped to aspect ratio: {img.size}")
                                                # Update dimensions after aspect crop
                                                current_w, current_h = img.size
                                                # After aspect crop, we must scale to target (aspect ratio was different)
                                                img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                                image_modified = True
                                                if current_w > target_w or current_h > target_h:
                                                    logger.info(f"Downscaled to target dimensions: {target_w}x{target_h}")
                                                else:
                                                    logger.info(f"Upscaled to target dimensions: {target_w}x{target_h}")
                                            else:
                                                # Same aspect ratio - scale to target dimensions
                                                if current_w != target_w or current_h != target_h:
                                                    # Always scale to exact target size
                                                    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                                    if current_w > target_w:
                                                        logger.info(f"Downscaled to target dimensions: {target_w}x{target_h}")
                                                    else:
                                                        logger.info(f"Upscaled to target dimensions: {target_w}x{target_h}")
                                                    image_modified = True
                                                else:
                                                    # Exact match - no modification needed
                                                    image_modified = False

                                            # Convert back to bytes in original format (only if image was modified)
                                            if image_modified:
                                                output = io.BytesIO()
                                                # Preserve original format if available
                                                save_format = original_format if 'original_format' in locals() else 'PNG'
                                                # Use appropriate options for format
                                                if save_format in ['JPEG', 'JPG']:
                                                    img.save(output, format='JPEG', quality=95, optimize=True)
                                                else:
                                                    img.save(output, format=save_format)
                                                image_bytes = output.getvalue()
                                                logger.info(f"Saved processed image in {save_format} format")

                                    # Apply additional cropping only if aspect ratio doesn't match
                                    elif crop_to_aspect and width and height and width != height and crop_to_aspect_ratio:
                                        # Check if returned image already matches the desired aspect ratio
                                        img = Image.open(io.BytesIO(image_bytes))
                                        current_w, current_h = img.size
                                        current_aspect = current_w / current_h
                                        target_aspect = width / height

                                        # Allow 1% tolerance for aspect ratio comparison
                                        aspect_tolerance = 0.01
                                        if abs(current_aspect - target_aspect) > aspect_tolerance:
                                            logger.debug(f"Image aspect ratio {current_aspect:.3f} doesn't match target {target_aspect:.3f}, cropping to {width}x{height}")
                                            image_bytes = crop_to_aspect_ratio(image_bytes, width, height)
                                        else:
                                            logger.info(f"Image aspect ratio {current_aspect:.3f} matches target {target_aspect:.3f}, skipping crop")

                                    images.append(image_bytes)
            except Exception as e2:
                # Extract best error message
                error_message = None
                if hasattr(e2, 'message') and e2.message:
                    error_message = e2.message
                elif hasattr(e2, 'details') and e2.details:
                    error_message = str(e2.details)
                else:
                    error_message = str(e2)

                # Check if fallback also hit a network error
                error_type = type(e2).__name__
                error_str = str(e2).lower()
                if error_type in ['RemoteProtocolError', 'ConnectError', 'ConnectTimeout', 'ReadTimeout'] or 'disconnected' in error_str:
                    raise RuntimeError(f"{error_message}")
                raise RuntimeError(f"Google generation failed: {error_message}")

        # Warn if no images were generated and provide detailed reason
        if not images:
            error_details = []
            if no_image_error:
                logger.error(f"❌ No images were generated after {max_retries} attempts!")
                logger.error("Gemini returned NO_IMAGE error (transient API issue).")
                error_details.append("ERROR: NO_IMAGE - Transient API issue. Please try again.")
            else:
                logger.error("No images were generated! Check if candidates were blocked by safety filters or had errors.")
                # Try to extract detailed error info from response
                if response and response.candidates:
                    for cand_idx, cand in enumerate(response.candidates):
                        finish_reason = getattr(cand, 'finish_reason', None)
                        safety_ratings = getattr(cand, 'safety_ratings', None)
                        if finish_reason:
                            finish_str = str(finish_reason)
                            logger.error(f"Candidate {cand_idx} finish_reason: {finish_str}")
                            error_details.append(f"ERROR: finish_reason={finish_str}")
                        if safety_ratings:
                            logger.error(f"Candidate {cand_idx} safety_ratings: {safety_ratings}")
                            # Parse safety ratings for blocked categories
                            for rating in safety_ratings:
                                cat = getattr(rating, 'category', 'unknown')
                                prob = getattr(rating, 'probability', 'unknown')
                                blocked = getattr(rating, 'blocked', False)
                                if blocked or 'HIGH' in str(prob):
                                    error_details.append(f"BLOCKED: {cat} (probability: {prob})")
                        if not getattr(cand, 'content', None):
                            error_details.append("ERROR: No content in response (likely blocked by safety filter)")
                elif response:
                    # No candidates at all
                    error_details.append("ERROR: API returned no candidates")
                    # Check for prompt feedback
                    if hasattr(response, 'prompt_feedback'):
                        feedback = response.prompt_feedback
                        logger.error(f"Prompt feedback: {feedback}")
                        if hasattr(feedback, 'block_reason') and feedback.block_reason:
                            error_details.append(f"BLOCKED: {feedback.block_reason}")
                        safety_ratings = getattr(feedback, 'safety_ratings', None)
                        if safety_ratings:  # Check for None before iterating
                            for rating in safety_ratings:
                                cat = getattr(rating, 'category', 'unknown')
                                prob = getattr(rating, 'probability', 'unknown')
                                if 'HIGH' in str(prob) or 'MEDIUM' in str(prob):
                                    error_details.append(f"Safety issue: {cat} ({prob})")

            # Add error details to texts so they're passed to the UI
            if error_details:
                texts.extend(error_details)
            else:
                texts.append("ERROR: No image generated - unknown reason")

        return texts, images
    
    def validate_auth(self) -> Tuple[bool, str]:
        """Validate Google authentication."""
        if self.auth_mode == "gcloud":
            return self._check_gcloud_auth()
        else:
            # Test API key
            if not self.api_key:
                return False, "No API key configured"
            
            try:
                # Try a minimal generation
                if not self.client:
                    self._init_api_key_client()
                
                response = self.client.models.generate_content(
                    model=self.get_default_model(),
                    contents="Test",
                )
                return True, "API key is valid"
            except Exception as e:
                return False, f"API key validation failed: {e}"
    
    def _check_gcloud_auth(self) -> Tuple[bool, str]:
        """Check Google Cloud authentication status."""
        # First check if we have cached validation
        if self.config_manager.get_auth_validated("google"):
            project_id = self.config_manager.get_gcloud_project_id()
            if project_id:
                return True, f"Authenticated (Project: {project_id}) [cached]"
            return True, "Authenticated [cached]"
        
        try:
            # Fast path: Check if credentials file exists first
            from pathlib import Path
            import json
            
            # Check standard ADC locations
            adc_paths = [
                Path.home() / ".config" / "gcloud" / "application_default_credentials.json",  # Linux/WSL
                Path.home() / "AppData" / "Roaming" / "gcloud" / "application_default_credentials.json",  # Windows
            ]
            
            creds_file = None
            for path in adc_paths:
                if path.exists():
                    creds_file = path
                    break
            
            if not creds_file:
                # Clear cached auth if no credentials file
                self.config_manager.set_auth_validated("google", False)
                self.config_manager.save()
                return False, "Not authenticated. Run: gcloud auth application-default login"
            
            # Quick validation: check if file is valid JSON and not expired
            try:
                with open(creds_file, 'r') as f:
                    creds_data = json.load(f)
                
                # Basic validation - check if it has expected fields
                if 'client_id' in creds_data or 'type' in creds_data:
                    # Get project ID quickly
                    project = self._get_gcloud_project_id()
                    
                    # Cache the successful auth validation
                    self.config_manager.set_auth_validated("google", True)
                    if project:
                        self.config_manager.set_gcloud_project_id(project)
                    self.config_manager.save()
                    
                    if project:
                        return True, f"Authenticated (Project: {project})"
                    else:
                        return True, "Authenticated (No project set)"
                else:
                    return False, "Invalid credentials file"
                    
            except (json.JSONDecodeError, KeyError):
                return False, "Corrupted credentials file. Re-authenticate with: gcloud auth application-default login"
                
        except Exception as e:
            return False, f"Error checking authentication: {e}"

    def _check_crop_edges_uniform(self, img, crop_left: int, crop_top: int,
                                   crop_right: int, crop_bottom: int,
                                   variance_threshold: float = 5.0) -> bool:
        """Check if the edges being cropped away are uniform (background-like).

        Examines the regions that would be cropped and checks color variance.
        If variance is low (uniform color), returns True for auto-crop.
        If variance is high (varied content), returns False for manual crop.

        Args:
            img: PIL Image to check
            crop_left: Left edge of crop region
            crop_top: Top edge of crop region
            crop_right: Right edge of crop region
            crop_bottom: Bottom edge of crop region
            variance_threshold: Maximum std dev to consider "uniform" (default 30)

        Returns:
            True if edges are uniform (safe to auto-crop)
            False if edges have varied content (show crop dialog)
        """
        import numpy as np

        width, height = img.size

        # Define the edge regions that will be cropped away
        edge_regions = []

        # Top edge (full width, from 0 to crop_top)
        if crop_top > 0:
            edge_regions.append(img.crop((0, 0, width, crop_top)))

        # Bottom edge (full width, from crop_bottom to height)
        if crop_bottom < height:
            edge_regions.append(img.crop((0, crop_bottom, width, height)))

        # Left edge (from crop_top to crop_bottom, 0 to crop_left)
        if crop_left > 0:
            edge_regions.append(img.crop((0, crop_top, crop_left, crop_bottom)))

        # Right edge (from crop_top to crop_bottom, crop_right to width)
        if crop_right < width:
            edge_regions.append(img.crop((crop_right, crop_top, width, crop_bottom)))

        if not edge_regions:
            # No edges to crop - shouldn't happen but safe to auto-crop
            return True

        # Check variance in each edge region
        for region in edge_regions:
            # Convert to numpy array
            region_array = np.array(region)

            # Skip very small regions
            if region_array.size < 100:
                continue

            # Calculate standard deviation across all color channels
            # High std dev = varied content, Low std dev = uniform
            std_dev = np.std(region_array)

            logger.info(f"Edge region {region.size} std_dev: {std_dev:.1f} (threshold: {variance_threshold})")

            if std_dev > variance_threshold:
                # This edge has varied content - need manual crop
                logger.info(f"Edge has varied content (std_dev={std_dev:.1f} > {variance_threshold})")
                return False

        # All edges are uniform
        logger.info(f"All crop edges are uniform (below threshold {variance_threshold})")
        return True

    def get_models(self) -> Dict[str, str]:
        """Get available Google image generation models.

        Note: This only includes image generation models, not text/chat LLM models.
        """
        return {
            "gemini-2.5-flash-image": "Gemini 2.5 Flash Image (Nano Banana)",
            "gemini-3-pro-image-preview": "Gemini 3 Pro Image (Nano Banana Pro) - 4K",
        }
    
    def get_models_with_details(self) -> Dict[str, Dict[str, str]]:
        """Get available Google image generation models with detailed display information.

        Returns:
            Dictionary mapping model IDs to display information including:
            - name: Short display name
            - nickname: Optional nickname/codename
            - description: Optional brief description

        Note: This only includes image generation models, not text/chat LLM models.
        """
        return {
            "gemini-2.5-flash-image": {
                "name": "Gemini 2.5 Flash Image",
                "nickname": "Nano Banana",
                "description": "Production image generation with aspect ratio support"
            },
            "gemini-3-pro-image-preview": {
                "name": "Gemini 3 Pro Image",
                "nickname": "Nano Banana Pro",
                "description": "4K output, superior text rendering, up to 14 reference images"
            },
        }
    
    def get_default_model(self) -> str:
        """Get default Google model."""
        return "gemini-2.5-flash-image"
    
    def get_api_key_url(self) -> str:
        """Get Google API key URL."""
        return "https://aistudio.google.com/apikey"
    
    def get_supported_features(self) -> List[str]:
        """Get supported features."""
        return ["generate", "edit", "compose"]
    
    def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Edit image with Google Gemini."""
        if not self.client:
            raise ValueError("No client configured")
        
        model = model or self.get_default_model()
        texts: List[str] = []
        images: List[bytes] = []
        
        try:
            # Gemini can process images as input
            response = self.client.models.generate_content(
                model=model,
                contents=[prompt, {"inline_data": {"data": image, "mime_type": "image/png"}}],
            )
            
            if response and response.candidates:
                cand = response.candidates[0]
                if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                    for part in cand.content.parts:
                        if getattr(part, "text", None):
                            texts.append(part.text)
                        elif getattr(part, "inline_data", None) is not None:
                            data = getattr(part.inline_data, "data", None)
                            if isinstance(data, (bytes, bytearray)):
                                images.append(bytes(data))
        except Exception as e:
            raise RuntimeError(f"Google image editing failed: {e}")

        return texts, images

    def generate_video(
        self,
        prompt: str,
        start_frame: Path,
        duration: float,
        model: str = "veo-3",
        end_frame: Optional[Path] = None,
        aspect_ratio: str = "9:16",
        **kwargs
    ) -> Tuple[Optional[Path], Dict[str, Any]]:
        """Generate video using Google Veo 3 or Veo 3.1.

        Args:
            prompt: Text description for video generation
            start_frame: Path to starting frame image (required)
            duration: Video duration in seconds (will be snapped to valid values)
            model: "veo-3" for single-frame or "veo-3.1" for start+end frame
            end_frame: Optional path to ending frame (triggers Veo 3.1 mode)
            aspect_ratio: Video aspect ratio (9:16, 16:9, etc.)
            **kwargs: Additional parameters

        Returns:
            Tuple of (video_path, metadata_dict) or (None, error_dict) on failure
        """
        # Validate inputs
        if not start_frame or not start_frame.exists():
            return None, {"error": "Start frame image is required and must exist"}

        # Determine which Veo version to use
        use_veo_31 = end_frame is not None and end_frame.exists()
        actual_model = "veo-3.1" if use_veo_31 else "veo-3"

        logger.info(f"Starting video generation with {actual_model}")
        logger.info(f"  Prompt: {prompt}")
        logger.info(f"  Start frame: {start_frame}")
        logger.info(f"  End frame: {end_frame if use_veo_31 else 'None (single-frame mode)'}")
        logger.info(f"  Duration: {duration}s")
        logger.info(f"  Aspect ratio: {aspect_ratio}")

        # Snap duration to valid Veo values (6s or 12s for Veo 3/3.1)
        # Per Google docs: Veo supports 6s and 12s durations
        if duration <= 6:
            snapped_duration = 6.0
        else:
            snapped_duration = 12.0

        if snapped_duration != duration:
            logger.info(f"Duration snapped: {duration}s -> {snapped_duration}s")

        try:
            # Initialize Google Cloud client if not already done
            if self.auth_mode == "gcloud" and not self.client:
                self._init_gcloud_client(raise_on_error=True)
            elif not self.client:
                raise ValueError("No client configured for video generation")

            # Prepare video generation request
            # NOTE: This is a placeholder - actual Vertex AI Video API integration needed
            # The real implementation would use:
            # from google.cloud import aiplatform
            # from google.cloud.aiplatform import VideoGenerationModel

            logger.warning("⚠️ STUB IMPLEMENTATION: Actual Veo API integration not yet complete")
            logger.info("To complete this implementation:")
            logger.info("1. Add google-cloud-aiplatform Video API imports")
            logger.info("2. Create video generation request with proper parameters")
            logger.info(f"3. Upload start_frame (and end_frame if using {actual_model})")
            logger.info("4. Submit generation job and poll for completion")
            logger.info("5. Download generated video and save to project directory")

            # Placeholder response
            metadata = {
                "model": actual_model,
                "prompt": prompt,
                "duration": snapped_duration,
                "aspect_ratio": aspect_ratio,
                "start_frame": str(start_frame),
                "end_frame": str(end_frame) if use_veo_31 else None,
                "status": "stub_implementation",
                "message": "Veo API integration pending - see logs for implementation steps"
            }

            return None, metadata

            # TODO: Real implementation would look like this:
            #
            # # Upload frames to GCS bucket
            # start_frame_uri = self._upload_to_gcs(start_frame)
            # end_frame_uri = self._upload_to_gcs(end_frame) if use_veo_31 else None
            #
            # # Create video generation request
            # if use_veo_31:
            #     request = {
            #         "model": "veo-3.1",
            #         "prompt": prompt,
            #         "start_image_uri": start_frame_uri,
            #         "end_image_uri": end_frame_uri,
            #         "duration_seconds": snapped_duration,
            #         "aspect_ratio": aspect_ratio,
            #     }
            # else:
            #     request = {
            #         "model": "veo-3",
            #         "prompt": prompt,
            #         "seed_image_uri": start_frame_uri,
            #         "duration_seconds": snapped_duration,
            #         "aspect_ratio": aspect_ratio,
            #     }
            #
            # # Submit generation job
            # operation = video_model.generate_video(**request)
            #
            # # Poll for completion
            # result = operation.result(timeout=600)  # 10 min timeout
            #
            # # Download video
            # video_bytes = result.video_data
            # video_path = self._save_video(video_bytes, prompt)
            #
            # return video_path, metadata

        except Exception as e:
            logger.error(f"Video generation failed: {e}", exc_info=True)
            return None, {"error": str(e)}