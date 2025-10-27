"""Google Gemini provider for image generation."""

import os
import subprocess
import platform
import logging
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
            self.client = genai.Client(api_key=self.api_key)
    
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
        if not self.client:
            if self.auth_mode == "gcloud":
                # Try to initialize gcloud client, raise error if it fails
                self._init_gcloud_client(raise_on_error=True)
            else:
                raise ValueError("No API key configured for Google provider")

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

        # For Gemini, scale to optimal size (1024px) if dimensions are too large OR too small
        # per CLAUDE.md: "For gemini, if either resolution is greater than 1024, scale proportionally so max is 1024"
        # NEW: Also scale up if max dimension is less than 1024 for better quality
        if width and height:
            # Always store original target dimensions for post-processing
            kwargs['_target_width'] = original_width
            kwargs['_target_height'] = original_height

            max_dim = max(width, height)
            if max_dim != 1024:  # Scale if not already at optimal size
                # Scale proportionally so max dimension is 1024
                scale_factor = 1024 / max_dim
                scaled_width = int(width * scale_factor)
                scaled_height = int(height * scale_factor)

                if max_dim > 1024:
                    logger.info(f"Scaling down for Gemini: {width}x{height} -> {scaled_width}x{scaled_height} (factor: {scale_factor:.3f})")
                else:
                    logger.info(f"Scaling up for Gemini: {width}x{height} -> {scaled_width}x{scaled_height} (factor: {scale_factor:.3f})")

                width = scaled_width
                height = scaled_height
                # Store that we need to scale back later
                kwargs['_needs_upscale'] = True if max_dim > 1024 else False
                kwargs['_needs_downscale'] = True if max_dim < 1024 else False

        # Calculate aspect ratio from dimensions if not provided
        # Note: We no longer add dimensions to the prompt text as it gets rendered as literal text
        # Instead, we rely solely on the image_config parameter below
        if width and height and not aspect_ratio:
            # Calculate the actual aspect ratio for logging
            ratio = width / height
            if abs(ratio - 1.0) < 0.01:
                aspect_ratio = "1:1"
            elif abs(ratio - 16/9) < 0.05:
                aspect_ratio = "16:9"
            elif abs(ratio - 9/16) < 0.05:
                aspect_ratio = "9:16"
            elif abs(ratio - 4/3) < 0.05:
                aspect_ratio = "4:3"
            elif abs(ratio - 3/4) < 0.05:
                aspect_ratio = "3:4"
            elif abs(ratio - 2/1) < 0.1:
                aspect_ratio = "2:1"
            elif abs(ratio - 1/2) < 0.1:
                aspect_ratio = "1:2"
            else:
                # For non-standard ratios, create a descriptive string
                aspect_ratio = f"{width}:{height}"

        # Calculate default dimensions if we have aspect ratio but no dimensions
        if aspect_ratio and not (width and height):
            if aspect_ratio == '16:9':
                width, height = 1024, 576
            elif aspect_ratio == '9:16':
                width, height = 576, 1024
            elif aspect_ratio == '4:3':
                width, height = 1024, 768
            elif aspect_ratio == '3:4':
                width, height = 768, 1024
            elif aspect_ratio == '21:9':
                width, height = 1024, 439
            elif aspect_ratio == '1:1':
                width, height = 1024, 1024
            else:
                # Default fallback
                width, height = 1024, 1024

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

        # Create the proper config object using types
        # This is required for aspect_ratio to work with the new SDK
        if aspect_ratio:
            logger.info(f"Using Gemini aspect ratio: {aspect_ratio} (target dimensions: {width}x{height})")
            logger.info(f"Setting image_config with aspect_ratio={aspect_ratio}")

            config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                **config_params
            )
        else:
            # No aspect ratio specified, use basic config
            logger.info(f"No aspect ratio specified, using default")
            config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                **config_params
            ) if config_params else None

        # Handle reference image if provided
        reference_image = kwargs.get('reference_image')
        contents = prompt  # Default to just the text prompt

        if reference_image:
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
                        logger.warning(f"⚠️ ASPECT RATIO MISMATCH: Reference image is {ref_width}x{ref_height} "
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

                        # Save the composed canvas for debugging
                        import time
                        from pathlib import Path
                        import platform
                        import os
                        timestamp = int(time.time())
                        debug_filename = f"DEBUG_CANVAS_COMPOSED_{timestamp}.png"

                        # Get platform-specific generated directory
                        if 'output_dir' in self.config and self.config['output_dir']:
                            generated_dir = Path(self.config['output_dir'])
                        else:
                            # Use platform-specific config directory
                            system = platform.system()
                            home = Path.home()
                            if system == "Windows":
                                base = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
                                config_dir = base / "ImageAI"
                            elif system == "Darwin":  # macOS
                                config_dir = home / "Library" / "Application Support" / "ImageAI"
                            else:  # Linux/Unix
                                base = Path(os.getenv("XDG_CONFIG_HOME", home / ".config"))
                                config_dir = base / "ImageAI"
                            generated_dir = config_dir / "generated"

                        # Ensure directory exists
                        generated_dir.mkdir(parents=True, exist_ok=True)
                        debug_path = generated_dir / debug_filename
                        canvas.save(debug_path, 'PNG')
                        logger.info(f"Saved composed canvas for debugging: {debug_path}")

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

        try:
            # Log the full request being sent to Gemini
            logger.info("=" * 60)
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

                                            # Now scale to target dimensions
                                            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                            logger.info(f"Resized to target dimensions: {target_w}x{target_h}")

                                            # Apply sharpening if we downscaled
                                            if current_w > target_w or current_h > target_h:
                                                from PIL import ImageFilter
                                                img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=3))
                                                logger.info(f"Applied sharpness enhancement after downscaling")

                                            # Convert back to bytes in original format
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
        except Exception as e:
            # Log the error that triggered fallback
            logger.error(f"Primary generation failed with error: {e}")
            logger.error(f"Error type: {type(e).__name__}")

            # Check if it's a specific API error
            if hasattr(e, 'message'):
                logger.error(f"Error message: {e.message}")
            if hasattr(e, 'code'):
                logger.error(f"Error code: {e.code}")
            if hasattr(e, 'details'):
                logger.error(f"Error details: {e.details}")

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

                                            # Now scale to target dimensions
                                            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                            logger.info(f"Resized to target dimensions: {target_w}x{target_h}")

                                            # Apply sharpening if we downscaled
                                            if current_w > target_w or current_h > target_h:
                                                from PIL import ImageFilter
                                                img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=3))
                                                logger.info(f"Applied sharpness enhancement after downscaling")

                                            # Convert back to bytes in original format
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
                raise RuntimeError(f"Google generation failed: {e2}")

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
    
    def get_models(self) -> Dict[str, str]:
        """Get available Google models."""
        return {
            "gemini-2.5-flash-image": "Gemini 2.5 Flash Image (Production)",
            "gemini-2.5-flash-image-preview": "Gemini 2.5 Flash Image (Preview - Deprecated)",
            "gemini-2.5-flash": "Gemini 2.5 Flash",
            "gemini-2.5-pro": "Gemini 2.5 Pro",
            "gemini-1.5-flash": "Gemini 1.5 Flash",
            "gemini-1.5-pro": "Gemini 1.5 Pro",
        }
    
    def get_models_with_details(self) -> Dict[str, Dict[str, str]]:
        """Get available Google models with detailed display information.
        
        Returns:
            Dictionary mapping model IDs to display information including:
            - name: Short display name
            - nickname: Optional nickname/codename
            - description: Optional brief description
        """
        return {
            "gemini-2.5-flash-image": {
                "name": "Gemini 2.5 Flash Image",
                "nickname": "Nano Banana",
                "description": "Production image generation with aspect ratio support"
            },
            "gemini-2.5-flash-image-preview": {
                "name": "Gemini 2.5 Flash Image Preview",
                "nickname": "Nano Banana (Old)",
                "description": "Deprecated - Use production version instead"
            },
            "gemini-2.5-flash": {
                "name": "Gemini 2.5 Flash",
                "description": "Fast performance on everyday tasks"
            },
            "gemini-2.5-pro": {
                "name": "Gemini 2.5 Pro",
                "description": "Advanced reasoning and complex problems"
            },
            "gemini-1.5-flash": {
                "name": "Gemini 1.5 Flash",
                "description": "Balanced speed and capability"
            },
            "gemini-1.5-pro": {
                "name": "Gemini 1.5 Pro",
                "description": "Wide-range reasoning tasks"
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