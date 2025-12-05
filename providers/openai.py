"""OpenAI provider for image generation."""

from typing import Dict, Any, Optional, Tuple, List
from base64 import b64decode

from .base import ImageProvider

# Import rate_limiter with fallback for different import contexts
try:
    from ..core.security import rate_limiter
except ImportError:
    from core.security import rate_limiter

# Check if openai is available but don't import yet
try:
    import importlib.util
    OPENAI_AVAILABLE = importlib.util.find_spec("openai") is not None
except ImportError:
    OPENAI_AVAILABLE = False

# This will be populated on first use
OpenAIClient = None


class OpenAIProvider(ImageProvider):
    """OpenAI DALL-E provider for AI image generation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize OpenAI provider."""
        super().__init__(config)
        self.client = None
        
        # Don't initialize client here - do it lazily when needed
    
    def _ensure_client(self):
        """Ensure OpenAI client is available."""
        global OpenAIClient

        if not OPENAI_AVAILABLE:
            raise ImportError(
                "The 'openai' package is not installed. "
                "Please run: pip install openai"
            )

        # Lazy import on first use
        if OpenAIClient is None:
            print("Loading OpenAI provider...")
            from openai import OpenAI as OpenAIClient

        if not self.client:
            if not self.api_key:
                raise ValueError("OpenAI requires an API key")
            self.client = OpenAIClient(api_key=self.api_key)
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Generate images using OpenAI DALL-E with enhanced settings."""
        self._ensure_client()

        model = model or self.get_default_model()
        texts: List[str] = []
        images: List[bytes] = []

        # Apply rate limiting
        rate_limiter.check_rate_limit('openai', wait=True)
        
        # Handle new settings from UI
        # Size/resolution mapping for DALL-E 3 and GPT Image 1
        if model in ["dall-e-3", "gpt-image-1"]:
            # Map resolution or aspect ratio to supported sizes
            resolution = kwargs.get('resolution', kwargs.get('width', size))
            aspect_ratio = kwargs.get('aspect_ratio', '1:1')

            if isinstance(resolution, str) and 'x' in resolution:
                # Direct resolution provided
                width, height = map(int, resolution.split('x'))
                if width > height:
                    size = "1792x1024"  # Landscape
                elif height > width:
                    size = "1024x1792"  # Portrait
                else:
                    size = "1024x1024"  # Square
            elif aspect_ratio:
                # Map aspect ratio to supported sizes
                if aspect_ratio in ['16:9', '4:3']:
                    size = "1792x1024"  # Landscape
                elif aspect_ratio in ['9:16', '3:4']:
                    size = "1024x1792"  # Portrait
                else:
                    size = "1024x1024"  # Square (default)
        
        # Quality setting (standard or hd)
        quality = kwargs.get('quality', quality)
        if quality not in ['standard', 'hd']:
            quality = 'standard'
        
        # Style setting (vivid or natural) - DALL-E 3 only
        style = kwargs.get('style', 'vivid')
        if style not in ['vivid', 'natural']:
            style = 'vivid'
        
        # Number of images (DALL-E 3 only supports n=1)
        num_images = kwargs.get('num_images', n)
        if model == "dall-e-3":
            num_images = 1  # DALL-E 3 limitation
        
        # Response format
        response_format = kwargs.get('response_format', 'b64_json')
        if response_format == 'base64_json':
            response_format = 'b64_json'
        elif response_format == 'url':
            response_format = 'url'
        
        try:
            # Build generation parameters based on model
            import logging
            logger = logging.getLogger(__name__)

            if model == "gpt-image-1":
                # GPT Image 1: supports background parameter, does NOT support style/quality
                gen_params = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "n": num_images,
                    "response_format": response_format,
                }
                # Add background parameter for transparency support
                background = kwargs.get('background')
                if background in {"transparent", "white", "black"}:
                    gen_params["background"] = background

                # Log the request
                logger.info("=" * 60)
                logger.info(f"SENDING TO OPENAI API (GPT Image 1)")
                logger.info(f"Model: {model}")
                logger.info(f"Prompt: {prompt}")
                logger.info(f"Size: {size}")
                if background:
                    logger.info(f"Background: {background}")
                logger.info(f"Number of images: {num_images}")
                logger.info("=" * 60)
            elif model == "dall-e-3":
                # DALL-E 3: supports style and quality
                gen_params = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "quality": quality,
                    "n": num_images,
                    "response_format": response_format,
                    "style": style,
                }

                # Log the request
                logger.info("=" * 60)
                logger.info(f"SENDING TO OPENAI API (DALL-E 3)")
                logger.info(f"Model: {model}")
                logger.info(f"Prompt: {prompt}")
                logger.info(f"Size: {size}")
                logger.info(f"Quality: {quality}")
                logger.info(f"Style: {style}")
                logger.info(f"Number of images: {num_images}")
                logger.info("=" * 60)
            else:
                # DALL-E 2 and others: basic parameters
                gen_params = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "n": num_images,
                    "response_format": response_format,
                }

                # Log the request
                logger.info("=" * 60)
                logger.info(f"SENDING TO OPENAI API ({model})")
                logger.info(f"Model: {model}")
                logger.info(f"Prompt: {prompt}")
                logger.info(f"Size: {size}")
                logger.info(f"Number of images: {num_images}")
                logger.info("=" * 60)

            # Generate images
            response = self.client.images.generate(**gen_params)
            
            data_items = getattr(response, "data", []) or []
            for item in data_items:
                if response_format == "b64_json":
                    b64 = getattr(item, "b64_json", None)
                    if b64:
                        try:
                            images.append(b64decode(b64))
                        except (ValueError, TypeError):
                            pass
                elif response_format == "url":
                    # For URL response, we need to download the image
                    url = getattr(item, "url", None)
                    if url:
                        try:
                            import requests
                            resp = requests.get(url, timeout=30)
                            if resp.status_code == 200:
                                images.append(resp.content)
                        except (OSError, IOError, AttributeError):
                            pass
            
            # Handle multiple images for models with n=1 limitation (DALL-E 3, GPT Image 1)
            # These models only support n=1, so we generate multiple times sequentially
            if model in ["dall-e-3", "gpt-image-1"] and kwargs.get('num_images', 1) > 1:
                for _ in range(kwargs.get('num_images', 1) - 1):
                    try:
                        response = self.client.images.generate(**gen_params)
                        data_items = getattr(response, "data", []) or []
                        for item in data_items:
                            if response_format == "b64_json":
                                b64 = getattr(item, "b64_json", None)
                                if b64:
                                    images.append(b64decode(b64))
                            elif response_format == "url":
                                url = getattr(item, "url", None)
                                if url:
                                    import requests
                                    resp = requests.get(url, timeout=30)
                                    if resp.status_code == 200:
                                        images.append(resp.content)
                    except (ValueError, RuntimeError, AttributeError, OSError, IOError):
                        pass  # Continue even if one generation fails
            
            if not images:
                raise RuntimeError(
                    "OpenAI returned no images. "
                    "Check model name, content policy, or quota."
                )
                
        except (ValueError, RuntimeError, AttributeError) as e:
            raise RuntimeError(f"OpenAI generation failed: {e}")
        
        return texts, images
    
    def validate_auth(self) -> Tuple[bool, str]:
        """Validate OpenAI API key."""
        if not self.api_key:
            return False, "No API key configured"
        
        try:
            self._ensure_client()
            
            # Try to list models as a validation check
            models = self.client.models.list()
            return True, "API key is valid"
        except (ValueError, RuntimeError, AttributeError) as e:
            return False, f"API key validation failed: {e}"
    
    def get_models(self) -> Dict[str, str]:
        """Get available OpenAI models."""
        return {
            "gpt-image-1": "GPT Image 1",
            "dall-e-3": "DALL·E 3",
            "dall-e-2": "DALL·E 2",
        }
    
    def get_models_with_details(self) -> Dict[str, Dict[str, str]]:
        """Get available OpenAI models with detailed display information.

        Returns:
            Dictionary mapping model IDs to display information including:
            - name: Short display name
            - nickname: Optional nickname/codename (None for OpenAI models)
            - description: Optional brief description
        """
        return {
            "gpt-image-1": {
                "name": "GPT Image 1",
                "description": "High quality, supports transparent backgrounds"
            },
            "dall-e-3": {
                "name": "DALL·E 3",
                "description": "Most advanced, highest quality images"
            },
            "dall-e-2": {
                "name": "DALL·E 2",
                "description": "Previous generation, lower cost"
            },
        }
    
    def get_default_model(self) -> str:
        """Get default OpenAI model."""
        return "dall-e-3"
    
    def get_api_key_url(self) -> str:
        """Get OpenAI API key URL."""
        return "https://platform.openai.com/api-keys"
    
    def get_supported_features(self) -> List[str]:
        """Get supported features."""
        return ["generate", "edit", "variations"]
    
    def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: Optional[str] = None,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
        n: int = 1,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Edit image with OpenAI DALL-E."""
        self._ensure_client()
        
        # Note: DALL-E 2 supports editing, DALL-E 3 does not yet
        model = "dall-e-2"  # Force DALL-E 2 for editing
        texts: List[str] = []
        images: List[bytes] = []
        
        # Apply rate limiting
        rate_limiter.check_rate_limit('openai', wait=True)
        
        try:
            # OpenAI expects file-like objects
            from io import BytesIO
            image_file = BytesIO(image)
            image_file.name = "image.png"
            
            edit_kwargs = {
                "image": image_file,
                "prompt": prompt,
                "size": size,
                "n": n,
                "response_format": "b64_json",
            }
            
            if mask:
                mask_file = BytesIO(mask)
                mask_file.name = "mask.png"
                edit_kwargs["mask"] = mask_file
            
            response = self.client.images.edit(**edit_kwargs)
            
            data_items = getattr(response, "data", []) or []
            for item in data_items:
                b64 = getattr(item, "b64_json", None)
                if b64:
                    try:
                        images.append(b64decode(b64))
                    except (ValueError, TypeError):
                        pass
            
            if not images:
                raise RuntimeError("OpenAI returned no edited images.")
                
        except (ValueError, RuntimeError, AttributeError) as e:
            raise RuntimeError(f"OpenAI image editing failed: {e}")
        
        return texts, images
    
    def create_variations(
        self,
        image: bytes,
        model: Optional[str] = None,
        n: int = 1,
        size: str = "1024x1024",
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Create variations of an image."""
        self._ensure_client()
        
        model = "dall-e-2"  # Only DALL-E 2 supports variations
        texts: List[str] = []
        images: List[bytes] = []
        
        # Apply rate limiting
        rate_limiter.check_rate_limit('openai', wait=True)
        
        try:
            from io import BytesIO
            image_file = BytesIO(image)
            image_file.name = "image.png"
            
            response = self.client.images.create_variation(
                image=image_file,
                n=n,
                size=size,
                response_format="b64_json",
            )
            
            data_items = getattr(response, "data", []) or []
            for item in data_items:
                b64 = getattr(item, "b64_json", None)
                if b64:
                    try:
                        images.append(b64decode(b64))
                    except (ValueError, TypeError):
                        pass
            
            if not images:
                raise RuntimeError("OpenAI returned no image variations.")
                
        except (ValueError, RuntimeError, AttributeError) as e:
            raise RuntimeError(f"OpenAI variations failed: {e}")
        
        return texts, images