"""OpenAI provider for image generation."""

from typing import Dict, Any, Optional, Tuple, List
from base64 import b64decode
from io import BytesIO
from pathlib import Path

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

        import logging
        logger = logging.getLogger(__name__)

        # Handle new settings from UI
        # Size/resolution mapping for DALL-E 3 and GPT Image models
        target_width = kwargs.get('width')
        target_height = kwargs.get('height')
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')

        if model in ["dall-e-3", "gpt-image-1", "gpt-image-1.5"]:
            # Map resolution or aspect ratio to supported sizes
            resolution = kwargs.get('resolution', kwargs.get('width', size))

            # GPT Image 1.5 has different supported sizes than DALL-E 3
            if model == "gpt-image-1.5":
                # GPT Image 1.5: 1024x1024, 1536x1024 (landscape), 1024x1536 (portrait), or auto
                if isinstance(resolution, str) and 'x' in resolution:
                    width, height = map(int, resolution.split('x'))
                    if width > height:
                        size = "1536x1024"  # Landscape
                    elif height > width:
                        size = "1024x1536"  # Portrait
                    else:
                        size = "1024x1024"  # Square
                elif aspect_ratio:
                    if aspect_ratio in ['16:9', '4:3']:
                        size = "1536x1024"  # Landscape
                    elif aspect_ratio in ['9:16', '3:4']:
                        size = "1024x1536"  # Portrait
                    else:
                        size = "1024x1024"  # Square (default)
            else:
                # DALL-E 3 and GPT Image 1: 1024x1024, 1792x1024 (landscape), 1024x1792 (portrait)
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

        # For GPT Image models: Add target dimensions to prompt as composition hint
        # This helps the model compose the image for the target aspect ratio
        # The output will still be a fixed size, but post-processing will crop/scale
        if model in ["gpt-image-1", "gpt-image-1.5"] and target_width and target_height:
            # Only add hint if target differs from API output size
            api_width, api_height = map(int, size.split('x'))
            target_ratio = target_width / target_height
            api_ratio = api_width / api_height

            # If aspect ratios differ significantly, add composition hint
            if abs(target_ratio - api_ratio) > 0.05:
                prompt = f"{prompt} (compose for {target_width}x{target_height} aspect ratio)"
                logger.info(f"Added composition hint for {target_width}x{target_height} (API size: {size})")
        
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

        # Handle reference images (GPT Image models only - uses images.edit())
        reference_image = kwargs.get('reference_image')  # Single image (bytes or path)
        reference_images = kwargs.get('reference_images')  # Multiple images (list of bytes)
        use_edit_api = False
        prepared_images = []

        # GPT Image models support reference images via images.edit()
        if model in ["gpt-image-1", "gpt-image-1.5"] and (reference_image or reference_images):
            use_edit_api = True

            # Prepare reference images as file-like objects
            if reference_images:
                # Multiple reference images (up to 10)
                for i, ref_bytes in enumerate(reference_images[:10]):  # Max 10 images
                    if isinstance(ref_bytes, bytes):
                        img_file = BytesIO(ref_bytes)
                        img_file.name = f"reference_{i}.png"
                        prepared_images.append(img_file)
                    elif isinstance(ref_bytes, (str, Path)):
                        # Load from path
                        ref_path = Path(ref_bytes)
                        if ref_path.exists():
                            with open(ref_path, 'rb') as f:
                                img_file = BytesIO(f.read())
                                img_file.name = f"reference_{i}.png"
                                prepared_images.append(img_file)
            elif reference_image:
                # Single reference image
                if isinstance(reference_image, bytes):
                    img_file = BytesIO(reference_image)
                    img_file.name = "reference.png"
                    prepared_images.append(img_file)
                elif isinstance(reference_image, (str, Path)):
                    ref_path = Path(reference_image)
                    if ref_path.exists():
                        with open(ref_path, 'rb') as f:
                            img_file = BytesIO(f.read())
                            img_file.name = "reference.png"
                            prepared_images.append(img_file)

            if not prepared_images:
                use_edit_api = False  # Fall back to generate if no valid images

        try:
            # Build generation parameters based on model
            if model == "gpt-image-1.5":
                # GPT Image 1.5: New parameters - output_format, compression, moderation
                # Supports n=1-10 (unlike DALL-E 3 which only supports n=1)
                gen_params = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "n": num_images,  # GPT Image 1.5 supports n=1-10
                }

                # Output format (png, jpeg, webp) - different from response_format
                output_format = kwargs.get('output_format', 'png')
                if output_format in {'png', 'jpeg', 'webp'}:
                    gen_params["output_format"] = output_format
                else:
                    gen_params["output_format"] = "png"

                # Compression (0-100%) for jpeg/webp
                if output_format in {'jpeg', 'webp'}:
                    compression = kwargs.get('compression', 100)
                    if isinstance(compression, (int, float)) and 0 <= compression <= 100:
                        gen_params["compression"] = int(compression)

                # Background: transparent, opaque, or auto
                background = kwargs.get('background', 'auto')
                if background in {"transparent", "opaque", "auto"}:
                    gen_params["background"] = background

                # Moderation: low or auto
                moderation = kwargs.get('moderation', 'auto')
                if moderation in {"low", "auto"}:
                    gen_params["moderation"] = moderation

                # Log the request
                logger.info("=" * 60)
                logger.info(f"SENDING TO OPENAI API (GPT Image 1.5)")
                logger.info(f"Model: {model}")
                logger.info(f"Prompt: {prompt}")
                logger.info(f"Size: {size}")
                logger.info(f"Output format: {gen_params.get('output_format', 'png')}")
                if 'compression' in gen_params:
                    logger.info(f"Compression: {gen_params['compression']}%")
                logger.info(f"Background: {gen_params.get('background', 'auto')}")
                logger.info(f"Moderation: {gen_params.get('moderation', 'auto')}")
                logger.info(f"Number of images: {num_images}")
                logger.info("=" * 60)
            elif model == "gpt-image-1":
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

            # Generate or edit images (edit when reference images provided)
            if use_edit_api and prepared_images:
                # Use images.edit() for reference image support
                logger.info(f"Using images.edit() with {len(prepared_images)} reference image(s)")

                # Build edit parameters
                edit_params = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "n": min(num_images, 10),  # Edit API supports n=1-10
                }

                # Pass images - single image or list
                if len(prepared_images) == 1:
                    edit_params["image"] = prepared_images[0]
                else:
                    edit_params["image"] = prepared_images

                # Add model-specific parameters
                if model == "gpt-image-1.5":
                    output_format = kwargs.get('output_format', 'png')
                    if output_format in {'png', 'jpeg', 'webp'}:
                        edit_params["output_format"] = output_format
                    if output_format in {'jpeg', 'webp'}:
                        compression = kwargs.get('compression', 100)
                        if isinstance(compression, (int, float)) and 0 <= compression <= 100:
                            edit_params["output_compression"] = int(compression)

                response = self.client.images.edit(**edit_params)
            else:
                # Standard generation without reference images
                response = self.client.images.generate(**gen_params)

            data_items = getattr(response, "data", []) or []
            for item in data_items:
                # GPT Image 1.5 uses output_format, returns b64_json
                if model == "gpt-image-1.5":
                    b64 = getattr(item, "b64_json", None)
                    if b64:
                        try:
                            images.append(b64decode(b64))
                        except (ValueError, TypeError):
                            pass
                elif use_edit_api or response_format == "b64_json":
                    # Edit API always returns b64_json
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

            # Post-processing: crop/scale to target dimensions if specified
            if target_width and target_height and model in ["gpt-image-1", "gpt-image-1.5"]:
                try:
                    from PIL import Image
                    import io

                    processed_images = []
                    for img_bytes in images:
                        img = Image.open(io.BytesIO(img_bytes))
                        current_w, current_h = img.size
                        target_ratio = target_width / target_height
                        current_ratio = current_w / current_h

                        # Check if aspect ratios differ
                        if abs(target_ratio - current_ratio) > 0.01:
                            # Need to crop to match target aspect ratio
                            if current_ratio > target_ratio:
                                # Image is wider - crop sides
                                new_w = int(current_h * target_ratio)
                                crop_left = (current_w - new_w) // 2
                                img = img.crop((crop_left, 0, crop_left + new_w, current_h))
                                logger.info(f"Cropped width: {current_w}x{current_h} -> {img.size}")
                            else:
                                # Image is taller - crop top/bottom
                                new_h = int(current_w / target_ratio)
                                crop_top = (current_h - new_h) // 2
                                img = img.crop((0, crop_top, current_w, crop_top + new_h))
                                logger.info(f"Cropped height: {current_w}x{current_h} -> {img.size}")

                        # Scale to target size
                        if img.size != (target_width, target_height):
                            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                            logger.info(f"Scaled to target: {target_width}x{target_height}")

                        # Convert back to bytes
                        output = io.BytesIO()
                        img.save(output, format='PNG')
                        processed_images.append(output.getvalue())

                    images = processed_images
                    logger.info(f"Post-processed {len(images)} image(s) to {target_width}x{target_height}")
                except Exception as e:
                    logger.warning(f"Post-processing failed, using original images: {e}")

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
            "gpt-image-1.5": "GPT Image 1.5",
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
            "gpt-image-1.5": {
                "name": "GPT Image 1.5",
                "description": "Latest model, 4x faster, better instruction following"
            },
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
        return ["generate", "edit", "variations", "reference_images"]
    
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