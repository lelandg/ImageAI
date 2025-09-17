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
            
            # Create genai client that will use ADC
            self.client = genai.Client()
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
        
        # Only apply rate limiting for API key mode (Google Cloud has its own quotas)
        if self.auth_mode != "gcloud":
            rate_limiter.check_rate_limit('google', wait=True)
        
        texts: List[str] = []
        images: List[bytes] = []
        
        # Build generation config for Gemini models
        # IMPORTANT: Google Gemini only generates square (1:1) images
        # Aspect ratio parameters and prompt hints do NOT change the output dimensions
        config = {}

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

        # For Gemini, scale down if either dimension > 1024
        # per CLAUDE.md: "For gemini, if either resolution is greater than 1024, scale proportionally so max is 1024"
        if width and height:
            if width > 1024 or height > 1024:
                # Scale proportionally so max dimension is 1024
                scale_factor = 1024 / max(width, height)
                scaled_width = int(width * scale_factor)
                scaled_height = int(height * scale_factor)
                logger.info(f"Scaling down for Gemini: {width}x{height} -> {scaled_width}x{scaled_height} (factor: {scale_factor:.3f})")
                width = scaled_width
                height = scaled_height
                # Store that we need to upscale later
                kwargs['_needs_upscale'] = True
                kwargs['_target_width'] = original_width
                kwargs['_target_height'] = original_height

        # For Gemini, add dimensions in parentheses for non-square aspect ratios
        # per CLAUDE.md: "for all gemini image ratios besides 1:1, send ratio. E.g. LLM prompt like 'brief prompt description (1024x768)'"
        if aspect_ratio and aspect_ratio != "1:1" and width and height:
            # Add dimensions in parentheses at end of prompt
            prompt_with_dims = f"{prompt} ({width}x{height})"
            logger.info(f"Sending to Gemini with aspect ratio {aspect_ratio}: prompt ends with '({width}x{height})'")
            logger.info(f"Full prompt: {prompt_with_dims}")
            prompt = prompt_with_dims
        elif width and height:
            # Log even for square images
            logger.info(f"Sending to Gemini with square aspect (1:1): {width}x{height} - no dimensions added to prompt")
        else:
            logger.info(f"Sending to Gemini with default resolution (no dimensions specified)")

        if resolution_hint and aspect_ratio == "1:1":
            # For square images, we can still add quality hints
            prompt = f"{prompt}. {resolution_hint}."
        
        # Note: These generation_config parameters may not be supported by all Gemini models
        # Most are placeholders for potential future support
        
        # Number of images - may work with some models
        num_images = kwargs.get('num_images', 1)
        if num_images > 1:
            # Try to request multiple images (may not be supported)
            config['candidate_count'] = num_images
        
        # Safety settings (these generally work)
        if kwargs.get('safety_filter'):
            config['safety_settings'] = kwargs['safety_filter']
        
        # Seed for reproducibility (if supported)
        if kwargs.get('seed') is not None:
            config['seed'] = kwargs['seed']

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

            # Try to use generation_config parameter if supported
            if config:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    generation_config=config
                )
            else:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                )
            
            if response and response.candidates:
                # Process all candidates (for multiple images)
                for cand in response.candidates:
                    if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                        for part in cand.content.parts:
                            if getattr(part, "text", None):
                                texts.append(part.text)
                            elif getattr(part, "inline_data", None) is not None:
                                data = getattr(part.inline_data, "data", None)
                                if isinstance(data, (bytes, bytearray)):
                                    image_bytes = bytes(data)

                                    # Handle upscaling back to original dimensions if we scaled down for Gemini
                                    if kwargs.get('_needs_upscale'):
                                        target_w = kwargs.get('_target_width')
                                        target_h = kwargs.get('_target_height')
                                        if target_w and target_h:
                                            logger.info(f"Upscaling Gemini output back to target: {target_w}x{target_h}")
                                            from PIL import Image
                                            import io

                                            # Open the image
                                            img = Image.open(io.BytesIO(image_bytes))
                                            current_w, current_h = img.size
                                            logger.debug(f"Current Gemini output size: {current_w}x{current_h}")

                                            # First crop to aspect ratio if needed (Gemini outputs square)
                                            if width and height and width != height:
                                                # Crop the square output to the scaled aspect ratio
                                                aspect = width / height
                                                if aspect > 1:  # Landscape
                                                    new_h = int(current_w / aspect)
                                                    crop_top = (current_h - new_h) // 2
                                                    img = img.crop((0, crop_top, current_w, crop_top + new_h))
                                                else:  # Portrait
                                                    new_w = int(current_h * aspect)
                                                    crop_left = (current_w - new_w) // 2
                                                    img = img.crop((crop_left, 0, crop_left + new_w, current_h))
                                                logger.debug(f"Cropped to aspect ratio: {img.size}")

                                            # Now upscale to target dimensions
                                            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                            logger.info(f"Upscaled to final size: {target_w}x{target_h}")

                                            # Convert back to bytes
                                            output = io.BytesIO()
                                            img.save(output, format='PNG')
                                            image_bytes = output.getvalue()

                                    # Apply additional cropping if dimensions are specified and not square and explicitly requested
                                    elif crop_to_aspect and width and height and width != height and crop_to_aspect_ratio:
                                        logger.debug(f"Cropping Google image to {width}x{height}")
                                        image_bytes = crop_to_aspect_ratio(image_bytes, width, height)

                                    images.append(image_bytes)
        except Exception as e:
            # Fallback to basic generation if advanced config fails
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
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
                                    image_bytes = bytes(data)

                                    # Handle upscaling back to original dimensions if we scaled down for Gemini
                                    if kwargs.get('_needs_upscale'):
                                        target_w = kwargs.get('_target_width')
                                        target_h = kwargs.get('_target_height')
                                        if target_w and target_h:
                                            logger.info(f"Upscaling Gemini output back to target: {target_w}x{target_h}")
                                            from PIL import Image
                                            import io

                                            # Open the image
                                            img = Image.open(io.BytesIO(image_bytes))
                                            current_w, current_h = img.size
                                            logger.debug(f"Current Gemini output size: {current_w}x{current_h}")

                                            # First crop to aspect ratio if needed (Gemini outputs square)
                                            if width and height and width != height:
                                                # Crop the square output to the scaled aspect ratio
                                                aspect = width / height
                                                if aspect > 1:  # Landscape
                                                    new_h = int(current_w / aspect)
                                                    crop_top = (current_h - new_h) // 2
                                                    img = img.crop((0, crop_top, current_w, crop_top + new_h))
                                                else:  # Portrait
                                                    new_w = int(current_h * aspect)
                                                    crop_left = (current_w - new_w) // 2
                                                    img = img.crop((crop_left, 0, crop_left + new_w, current_h))
                                                logger.debug(f"Cropped to aspect ratio: {img.size}")

                                            # Now upscale to target dimensions
                                            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                            logger.info(f"Upscaled to final size: {target_w}x{target_h}")

                                            # Convert back to bytes
                                            output = io.BytesIO()
                                            img.save(output, format='PNG')
                                            image_bytes = output.getvalue()

                                    # Apply additional cropping if dimensions are specified and not square and explicitly requested
                                    elif crop_to_aspect and width and height and width != height and crop_to_aspect_ratio:
                                        logger.debug(f"Cropping Google image to {width}x{height}")
                                        image_bytes = crop_to_aspect_ratio(image_bytes, width, height)

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
            "gemini-2.5-flash-image-preview": "Gemini 2.5 Flash (Image Preview)",
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
            "gemini-2.5-flash-image-preview": {
                "name": "Gemini 2.5 Flash Image",
                "nickname": "Nano Banana",
                "description": "Advanced image generation and editing"
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
        return "gemini-2.5-flash-image-preview"
    
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