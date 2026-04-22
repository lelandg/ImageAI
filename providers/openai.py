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


# Capability table for every OpenAI image model. The provider, GUI, and CLI
# all consult this; never add per-model `if model == ...` branches outside
# this dict — extend the dict instead.
MODEL_CAPS = {
    "gpt-image-2": {
        "display_name": "GPT Image 2 (Thinking, Best)",
        "snapshot": "gpt-image-2-2026-04-21",
        "endpoint": "images.generate",
        "quality_values": ("auto", "low", "medium", "high"),
        "default_quality": "auto",
        "valid_sizes": ("auto", "1024x1024", "1536x1024", "1024x1536",
                        "2048x2048", "2048x1152", "3840x2160", "2160x3840"),
        "supports_custom_size": True,
        "custom_size_edge_multiple": 16,
        "custom_size_max_edge": 3840,
        "custom_size_max_aspect": 3.0,
        "custom_size_min_pixels": 655_360,
        "custom_size_max_pixels": 8_294_400,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": True,
        "supports_mask": True,
        "supports_multi_reference": True,
        "supports_output_format": True,
        "supports_moderation": True,
        "supports_batch": True,
        "supports_style": False,
        "max_n": 10,
    },
    "gpt-image-1.5": {
        "display_name": "GPT Image 1.5 (Latest)",
        "endpoint": "images.generate",
        "quality_values": ("auto",),
        "default_quality": "auto",
        "valid_sizes": ("auto", "1024x1024", "1536x1024", "1024x1536"),
        "supports_custom_size": False,
        "supports_transparent_bg": True,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": False,
        "supports_mask": True,
        "supports_multi_reference": True,
        "supports_output_format": True,
        "supports_moderation": True,
        "supports_batch": True,
        "supports_style": False,
        "max_n": 10,
    },
    "gpt-image-1": {
        "display_name": "GPT Image 1",
        "endpoint": "images.generate",
        "quality_values": ("auto",),
        "default_quality": "auto",
        "valid_sizes": ("auto", "1024x1024", "1792x1024", "1024x1792"),
        "supports_custom_size": False,
        "supports_transparent_bg": True,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": False,
        "supports_mask": True,
        "supports_multi_reference": True,
        "supports_output_format": False,
        "supports_moderation": False,
        "supports_batch": False,
        "supports_style": False,
        "max_n": 1,
    },
    "gpt-image-1-mini": {
        "display_name": "GPT Image 1 Mini (Fast)",
        "endpoint": "images.generate",
        "quality_values": ("auto",),
        "default_quality": "auto",
        "valid_sizes": ("auto", "1024x1024", "1792x1024", "1024x1792"),
        "supports_custom_size": False,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": False,
        "supports_mask": False,
        "supports_multi_reference": False,
        "supports_output_format": False,
        "supports_moderation": False,
        "supports_batch": False,
        "supports_style": False,
        "max_n": 1,
    },
    "dall-e-3": {
        "display_name": "DALL·E 3",
        "endpoint": "images.generate",
        "quality_values": ("standard", "hd"),
        "default_quality": "standard",
        "valid_sizes": ("1024x1024", "1792x1024", "1024x1792"),
        "supports_custom_size": False,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": False,
        "supports_mask": False,
        "supports_multi_reference": False,
        "supports_output_format": False,
        "supports_moderation": False,
        "supports_batch": False,
        "supports_style": True,
        "max_n": 1,
    },
    "dall-e-2": {
        "display_name": "DALL·E 2",
        "endpoint": "images.generate",
        "quality_values": ("standard",),
        "default_quality": "standard",
        "valid_sizes": ("256x256", "512x512", "1024x1024"),
        "supports_custom_size": False,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": True,
        "supports_streaming": False,
        "supports_mask": True,
        "supports_multi_reference": False,
        "supports_output_format": False,
        "supports_moderation": False,
        "supports_batch": False,
        "supports_style": False,
        "max_n": 10,
    },
}


def _caps_for(model: str) -> dict:
    """Return MODEL_CAPS row, falling back to gpt-image-1 for unknown models."""
    return MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]


class _UnsupportedParam(ValueError):
    """Raised when a request includes a parameter the model does not support."""


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
        caps = _caps_for(model)

        # Validate quality against capability table. Caller may pass legacy
        # values; map any string outside caps['quality_values'] to default.
        requested_quality = kwargs.get("quality", quality)
        if requested_quality not in caps["quality_values"]:
            quality = caps["default_quality"]
        else:
            quality = requested_quality
        kwargs["quality"] = quality  # keep kwargs and local in sync

        # Reject unsupported parameter combinations with actionable messages.
        if kwargs.get("background") in {"transparent"} and not caps["supports_transparent_bg"]:
            raise _UnsupportedParam(
                f"Transparent background is not supported on {model}. "
                f"Use gpt-image-1.5 or gpt-image-1 for alpha PNG output."
            )
        if kwargs.get("input_fidelity") and not caps["supports_input_fidelity"]:
            raise _UnsupportedParam(
                f"input_fidelity is not supported on {model}."
            )
        n_requested = int(kwargs.get("num_images", n) or 1)
        if n_requested > caps["max_n"]:
            raise _UnsupportedParam(
                f"{model} supports n=1..{caps['max_n']}, got n={n_requested}."
            )

        # Custom size pre-flight (gpt-image-2 only). custom_size beats `size`.
        custom_size = kwargs.get("custom_size")
        if custom_size:
            if not caps["supports_custom_size"]:
                raise _UnsupportedParam(f"Custom size is not supported on {model}.")
            from core.image_size import validate_custom_size, parse_size_string
            try:
                cw, ch = parse_size_string(custom_size)
            except ValueError as e:
                raise _UnsupportedParam(str(e))
            ok, why = validate_custom_size(cw, ch, caps)
            if not ok:
                raise _UnsupportedParam(f"Invalid custom_size {custom_size}: {why}")
            size = f"{cw}x{ch}"

        import logging
        logger = logging.getLogger(__name__)

        # Streaming path (gpt-image-2 only). Routes through Responses API and
        # invokes the on_partial callback for each partial frame. Falls back
        # to sync if the SDK lacks Responses-API streaming support.
        if kwargs.get("stream") and caps["supports_streaming"]:
            partial_count = max(0, min(int(kwargs.get("partial_images", 0)), 3))
            on_partial = kwargs.get("on_partial")
            if partial_count > 0 and callable(on_partial):
                streamed = self._generate_streaming(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=int(kwargs.get("num_images", n) or 1),
                    partial_images=partial_count,
                    on_partial=on_partial,
                    output_format=kwargs.get("output_format", "png"),
                    moderation=kwargs.get("moderation", "auto"),
                )
                if streamed is not None:
                    return [], streamed
                # else: SDK doesn't support Responses streaming — fall through to sync
                logger.warning("Responses-API streaming unavailable; falling back to sync generation")

        texts: List[str] = []
        images: List[bytes] = []

        # Apply rate limiting
        rate_limiter.check_rate_limit('openai', wait=True)

        # Handle new settings from UI
        # Size/resolution mapping for DALL-E 3 and GPT Image models
        target_width = kwargs.get('width')
        target_height = kwargs.get('height')
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')

        # Skip the legacy size-mapping when the caller already supplied a
        # validated custom_size — that path set size = "{cw}x{ch}" above and
        # the gpt-image-2 valid_sizes presets must be preserved verbatim.
        if model in ["dall-e-3", "gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini", "gpt-image-2"] and not kwargs.get("custom_size"):
            # Map resolution or aspect ratio to supported sizes
            resolution = kwargs.get('resolution', kwargs.get('width', size))

            # gpt-image-2: aspect-driven mapping into the safe 1024 / 1536 presets.
            # (Use --custom-size for 2K/4K; this branch is the no-custom-size default.)
            if model == "gpt-image-2":
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
                        size = "1536x1024"
                    elif aspect_ratio in ['9:16', '3:4']:
                        size = "1024x1536"
                    else:
                        size = "1024x1024"
            # GPT Image 1.5 has different supported sizes than DALL-E 3
            elif model == "gpt-image-1.5":
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
        if model in ["gpt-image-2", "gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini"] and target_width and target_height:
            # Only add hint if target differs from API output size
            api_width, api_height = map(int, size.split('x'))
            target_ratio = target_width / target_height
            api_ratio = api_width / api_height

            # If aspect ratios differ significantly, add composition hint
            if abs(target_ratio - api_ratio) > 0.05:
                prompt = f"{prompt} (compose for {target_width}x{target_height} aspect ratio)"
                logger.info(f"Added composition hint for {target_width}x{target_height} (API size: {size})")
        
        # Legacy quality coercion: only applies to models that use standard/hd
        # (dall-e-3 / dall-e-2). gpt-image-* models keep the value validated by
        # the capability block above (auto | low | medium | high).
        if "standard" in caps["quality_values"] or "hd" in caps["quality_values"]:
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
        if model in ["gpt-image-2", "gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini"] and (reference_image or reference_images):
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
            if model == "gpt-image-2":
                gen_params = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "n": min(num_images, caps["max_n"]),
                    "quality": quality,  # auto|low|medium|high — drives reasoning
                }

                output_format = kwargs.get("output_format", "png")
                if output_format in {"png", "jpeg", "webp"}:
                    gen_params["output_format"] = output_format
                if output_format in {"jpeg", "webp"}:
                    compression = kwargs.get("output_compression", kwargs.get("compression", 90))
                    if isinstance(compression, (int, float)) and 0 <= compression <= 100:
                        gen_params["output_compression"] = int(compression)

                moderation = kwargs.get("moderation", "auto")
                if moderation in {"auto", "low"}:
                    gen_params["moderation"] = moderation

                logger.info("=" * 60)
                logger.info("SENDING TO OPENAI API (GPT Image 2)")
                logger.info(f"Model: {model}  (snapshot: {caps.get('snapshot')})")
                logger.info(f"Prompt: {prompt}")
                logger.info(f"Size: {size}")
                logger.info(f"Quality (thinking): {quality}")
                logger.info(f"Output format: {gen_params.get('output_format', 'png')}")
                if "output_compression" in gen_params:
                    logger.info(f"Compression: {gen_params['output_compression']}")
                logger.info(f"Moderation: {gen_params.get('moderation', 'auto')}")
                logger.info(f"Number of images: {gen_params['n']}")
                logger.info("=" * 60)
            elif model == "gpt-image-1.5":
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
            elif model in ["gpt-image-1", "gpt-image-1-mini"]:
                # GPT Image 1 / 1-Mini: supports background parameter, does NOT support style/quality
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
                model_name = "GPT Image 1 Mini" if model == "gpt-image-1-mini" else "GPT Image 1"
                logger.info("=" * 60)
                logger.info(f"SENDING TO OPENAI API ({model_name})")
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
                if model in ("gpt-image-2", "gpt-image-1.5"):
                    output_format = kwargs.get('output_format', 'png')
                    if output_format in {'png', 'jpeg', 'webp'}:
                        edit_params["output_format"] = output_format
                    if output_format in {'jpeg', 'webp'}:
                        compression = kwargs.get('output_compression', kwargs.get('compression', 100))
                        if isinstance(compression, (int, float)) and 0 <= compression <= 100:
                            edit_params["output_compression"] = int(compression)
                if model == "gpt-image-2":
                    # Pass through the new gpt-image-2 knobs to the edit endpoint too.
                    if quality in caps["quality_values"]:
                        edit_params["quality"] = quality
                    moderation = kwargs.get('moderation', 'auto')
                    if moderation in {"auto", "low"}:
                        edit_params["moderation"] = moderation

                response = self.client.images.edit(**edit_params)
            else:
                # Standard generation without reference images
                response = self.client.images.generate(**gen_params)

            data_items = getattr(response, "data", []) or []
            for item in data_items:
                # GPT Image 1.5 uses output_format, returns b64_json
                if model in ("gpt-image-2", "gpt-image-1.5"):
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
            # gpt-image-2 and gpt-image-1.5 handle n>1 in a single call; only legacy single-image models need this loop.
            if model in ["dall-e-3", "gpt-image-1", "gpt-image-1-mini"] and kwargs.get('num_images', 1) > 1:
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
            if target_width and target_height and model in ["gpt-image-2", "gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini"]:
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
        """Validate OpenAI API key. Detects the gpt-image-2 org-verification gate."""
        if not self.api_key:
            return False, "No API key configured"

        try:
            self._ensure_client()
            self.client.models.list()
            return True, "API key is valid"
        except Exception as e:  # noqa: BLE001 — surface every backend failure to the user
            msg = str(e)
            lower = msg.lower()
            if "verification" in lower or "must be verified" in lower or "403" in msg:
                return False, (
                    "OpenAI Organization Verification required for gpt-image-2 / "
                    "newest models. Visit https://platform.openai.com/settings/organization/general "
                    "to verify your org, then retry."
                )
            return False, f"API key validation failed: {e}"
    
    def get_models(self) -> Dict[str, str]:
        """Get available OpenAI image generation models (id -> display name)."""
        return {model_id: caps["display_name"] for model_id, caps in MODEL_CAPS.items()}

    def get_models_with_details(self) -> Dict[str, Dict[str, str]]:
        """Get available OpenAI image generation models with details for the UI."""
        descriptions = {
            "gpt-image-2": "Reasoning model — best quality, custom sizes up to 3840x2160, multi-reference, mask, streaming",
            "gpt-image-1.5": "Latest 1.x — 4x faster, transparent bg, up to 10 images",
            "gpt-image-1": "High quality, transparent backgrounds, reference images",
            "gpt-image-1-mini": "Fast generation, lower cost, good quality",
            "dall-e-3": "Most advanced legacy model, vivid/natural style, n=1 only",
            "dall-e-2": "Previous generation, lower cost, supports edits and variations",
        }
        return {
            model_id: {"name": caps["display_name"], "description": descriptions.get(model_id, "")}
            for model_id, caps in MODEL_CAPS.items()
        }

    def get_default_model(self) -> str:
        """Default OpenAI model — gpt-image-2 since 2026-04-22."""
        return "gpt-image-2"
    
    def get_api_key_url(self) -> str:
        """Get OpenAI API key URL."""
        return "https://platform.openai.com/api-keys"
    
    def get_supported_features(self) -> List[str]:
        """Get supported features."""
        return ["generate", "edit", "variations", "reference_images"]
    
    def edit_image(
        self,
        image,  # bytes | path | list of bytes | list of paths
        prompt: str,
        model: Optional[str] = None,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
        n: int = 1,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Edit an image (or compose from multiple references) via OpenAI /v1/images/edits.

        ``image`` may be:
          * bytes (single PNG)
          * a str/Path to a single PNG
          * a list of either, for multi-reference composition (gpt-image-1.x and gpt-image-2)

        ``mask`` is an optional alpha PNG for inpainting; only sent when the model
        supports it (``MODEL_CAPS[model]['supports_mask']``).
        """
        self._ensure_client()

        # Default to the best edit-capable model, not gpt-image-2's snapshot,
        # so callers that forget to pass `model` get sensible behavior.
        model = model or "gpt-image-2"
        caps = _caps_for(model)
        texts: List[str] = []
        images: List[bytes] = []

        rate_limiter.check_rate_limit('openai', wait=True)

        import logging
        logger = logging.getLogger(__name__)

        # Normalize image input into a list of file-like objects.
        items = image if isinstance(image, list) else [image]
        if len(items) > 1 and not caps["supports_multi_reference"]:
            raise _UnsupportedParam(
                f"{model} does not support multi-reference edits. "
                f"Use gpt-image-2, gpt-image-1.5, or gpt-image-1."
            )

        prepared = []
        for i, item in enumerate(items):
            if isinstance(item, (bytes, bytearray)):
                buf = BytesIO(bytes(item))
                buf.name = f"image_{i}.png"
                prepared.append(buf)
            elif isinstance(item, (str, Path)):
                p = Path(item)
                if not p.exists():
                    raise FileNotFoundError(f"Reference image not found: {p}")
                buf = BytesIO(p.read_bytes())
                buf.name = p.name
                prepared.append(buf)
            else:
                raise TypeError(f"Unsupported image input type: {type(item).__name__}")

        if not prepared:
            raise ValueError("edit_image requires at least one input image")

        edit_kwargs = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": min(int(n), caps["max_n"]),
            "image": prepared if len(prepared) > 1 else prepared[0],
        }

        # Mask
        if mask is not None:
            if not caps["supports_mask"]:
                raise _UnsupportedParam(f"{model} does not support mask inpainting.")
            mask_buf = BytesIO(mask if isinstance(mask, (bytes, bytearray)) else Path(mask).read_bytes())
            mask_buf.name = "mask.png"
            edit_kwargs["mask"] = mask_buf

        # Output format / compression for models that support it
        if caps["supports_output_format"]:
            output_format = kwargs.get("output_format", "png")
            if output_format in {"png", "jpeg", "webp"}:
                edit_kwargs["output_format"] = output_format
            if output_format in {"jpeg", "webp"}:
                compression = kwargs.get("output_compression", kwargs.get("compression", 90))
                if isinstance(compression, (int, float)) and 0 <= compression <= 100:
                    edit_kwargs["output_compression"] = int(compression)

        # Quality (gpt-image-2 reasoning knob)
        quality = kwargs.get("quality")
        if quality and quality in caps["quality_values"]:
            edit_kwargs["quality"] = quality

        # Moderation
        moderation = kwargs.get("moderation")
        if moderation and caps["supports_moderation"] and moderation in {"auto", "low"}:
            edit_kwargs["moderation"] = moderation

        # gpt-image-2 / gpt-image-1.5 return b64; dall-e-2 used to take response_format.
        if model == "dall-e-2":
            edit_kwargs["response_format"] = "b64_json"

        logger.info(
            "OpenAI images.edit model=%s images=%d mask=%s size=%s n=%d",
            model, len(prepared), bool(mask), size, edit_kwargs["n"],
        )

        try:
            response = self.client.images.edit(**edit_kwargs)
            for item in (getattr(response, "data", []) or []):
                b64 = getattr(item, "b64_json", None)
                if b64:
                    images.append(b64decode(b64))
            if not images:
                raise RuntimeError("OpenAI returned no edited images.")
        except _UnsupportedParam:
            raise
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

    def _generate_streaming(
        self,
        model: str,
        prompt: str,
        size: str,
        quality: str,
        n: int,
        partial_images: int,
        on_partial,
        output_format: str = "png",
        moderation: str = "auto",
    ) -> Optional[List[bytes]]:
        """Stream image generation via the Responses API.

        Invokes ``on_partial(index: int, png_bytes: bytes)`` for each partial
        frame as it arrives. Returns the final image bytes list, or None if
        the installed openai SDK does not expose a streaming Responses API.
        """
        import logging
        logger = logging.getLogger(__name__)

        if not hasattr(self.client, "responses") or not hasattr(self.client.responses, "stream"):
            return None

        tool = {
            "type": "image_generation",
            "size": size,
            "quality": quality,
            "moderation": moderation,
            "output_format": output_format,
            "partial_images": partial_images,
        }

        partials_seen = 0
        final_b64s: List[str] = []

        try:
            with self.client.responses.stream(
                model=model,
                input=prompt,
                tools=[tool],
                tool_choice={"type": "image_generation"},
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")
                    if etype.endswith("partial_image"):
                        b64 = (
                            getattr(event, "partial_image_b64", None)
                            or getattr(getattr(event, "partial_image", None), "b64_json", None)
                        )
                        if b64:
                            partials_seen += 1
                            try:
                                on_partial(partials_seen - 1, b64decode(b64))
                            except Exception as cb_err:  # noqa: BLE001
                                logger.warning(f"on_partial callback raised: {cb_err}")
                    elif etype.endswith("image_generation_call.completed"):
                        b64 = getattr(event, "b64_json", None) or getattr(
                            getattr(event, "result", None), "b64_json", None
                        )
                        if b64:
                            final_b64s.append(b64)
                response = stream.get_final_response()
                # If the event loop didn't yield a completed b64, dig it out of the response.
                if not final_b64s and response is not None:
                    for output in (getattr(response, "output", []) or []):
                        b64 = getattr(output, "b64_json", None) or getattr(
                            getattr(output, "result", None), "b64_json", None
                        )
                        if b64:
                            final_b64s.append(b64)
        except (AttributeError, TypeError) as e:
            logger.warning(f"Responses-API streaming failed structurally: {e}")
            return None

        if not final_b64s:
            return None
        return [b64decode(b) for b in final_b64s[:n]]

    def _create_alpha_mask(
        self,
        image_size: Tuple[int, int],
        region_bbox: Tuple[int, int, int, int],
        feather: int = 5,
    ) -> bytes:
        """
        Create a PNG mask with alpha channel for region-based editing.

        The mask has:
        - Transparent area (alpha=0) where editing should occur
        - Opaque area (alpha=255) where the original should be preserved

        Args:
            image_size: (width, height) of the image
            region_bbox: (x, y, width, height) of region to edit
            feather: Pixels to feather the mask edge for smoother blending

        Returns:
            PNG bytes with alpha mask
        """
        from PIL import Image
        import numpy as np

        # Create mask image (RGBA)
        mask = Image.new("RGBA", image_size, (0, 0, 0, 255))  # Fully opaque
        mask_array = np.array(mask)

        x, y, w, h = region_bbox

        # Make the edit region transparent (alpha=0)
        # Apply feathering for smoother edges
        for fy in range(max(0, y - feather), min(image_size[1], y + h + feather)):
            for fx in range(max(0, x - feather), min(image_size[0], x + w + feather)):
                # Calculate distance from region
                dx = max(0, x - fx, fx - (x + w - 1))
                dy = max(0, y - fy, fy - (y + h - 1))

                if dx == 0 and dy == 0:
                    # Inside region - fully transparent
                    mask_array[fy, fx, 3] = 0
                elif dx <= feather and dy <= feather:
                    # Feather zone - gradient
                    dist = np.sqrt(dx**2 + dy**2)
                    alpha = int(min(255, (dist / feather) * 255))
                    mask_array[fy, fx, 3] = alpha

        mask = Image.fromarray(mask_array)

        # Convert to bytes
        buffer = BytesIO()
        mask.save(buffer, format="PNG")
        return buffer.getvalue()

    def edit_image_region(
        self,
        image: bytes,
        region_bbox: Tuple[int, int, int, int],
        prompt: str,
        model: Optional[str] = None,
        style_context: Optional[str] = None,
        feather: int = 5,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Edit a specific region of an image using mask-based editing.

        Uses GPT-Image models with alpha mask to edit only the specified region
        while preserving the rest of the image.

        Args:
            image: Image bytes (PNG format)
            region_bbox: (x, y, width, height) of region to edit
            prompt: Editing prompt describing desired change
            model: Model to use (defaults to gpt-image-1)
            style_context: Optional style hint (e.g., "cartoon", "anime")
            feather: Pixels to feather mask edge (default 5)
            **kwargs: Additional parameters

        Returns:
            Tuple of (texts, image_bytes_list)
        """
        import logging
        logger = logging.getLogger(__name__)

        self._ensure_client()

        model = model or "gpt-image-1"
        texts: List[str] = []
        images: List[bytes] = []

        # Apply rate limiting
        rate_limiter.check_rate_limit('openai', wait=True)

        # Get image dimensions
        from PIL import Image as PILImage
        import io

        img = PILImage.open(io.BytesIO(image))
        img_width, img_height = img.size

        # Create alpha mask for the region
        mask_bytes = self._create_alpha_mask(
            image_size=(img_width, img_height),
            region_bbox=region_bbox,
            feather=feather,
        )

        # Build the full editing prompt
        full_prompt_parts = [
            prompt,
            "Keep the rest of the image exactly the same.",
            "Maintain the original art style and character appearance."
        ]

        if style_context:
            full_prompt_parts.insert(1, f"Style: {style_context}")

        full_prompt = " ".join(full_prompt_parts)

        x, y, w, h = region_bbox
        logger.info(f"Editing region ({x},{y},{w}x{h}) with prompt: {prompt[:50]}...")

        try:
            # Prepare file-like objects
            image_file = BytesIO(image)
            image_file.name = "image.png"
            mask_file = BytesIO(mask_bytes)
            mask_file.name = "mask.png"

            # Determine appropriate size for API
            # OpenAI only supports specific sizes
            valid_sizes = {
                "gpt-image-1.5": ["1024x1024", "1536x1024", "1024x1536"],
                "gpt-image-1": ["1024x1024", "1792x1024", "1024x1792"],
                "dall-e-2": ["1024x1024", "512x512", "256x256"],
            }

            # Find best matching size
            model_sizes = valid_sizes.get(model, ["1024x1024"])
            size = "1024x1024"

            # Match aspect ratio
            if img_width > img_height:
                if "1792x1024" in model_sizes:
                    size = "1792x1024"
                elif "1536x1024" in model_sizes:
                    size = "1536x1024"
            elif img_height > img_width:
                if "1024x1792" in model_sizes:
                    size = "1024x1792"
                elif "1024x1536" in model_sizes:
                    size = "1024x1536"

            # Build edit parameters
            edit_params = {
                "model": model,
                "image": image_file,
                "mask": mask_file,
                "prompt": full_prompt,
                "size": size,
                "n": 1,
                "response_format": "b64_json",
            }

            logger.info(f"Calling OpenAI images.edit with model={model}, size={size}")
            response = self.client.images.edit(**edit_params)

            # Extract image from response
            data_items = getattr(response, "data", []) or []
            for item in data_items:
                b64 = getattr(item, "b64_json", None)
                if b64:
                    try:
                        result_bytes = b64decode(b64)
                        result_img = PILImage.open(io.BytesIO(result_bytes))

                        # Resize back to original dimensions if needed
                        if result_img.size != (img_width, img_height):
                            result_img = result_img.resize(
                                (img_width, img_height),
                                PILImage.Resampling.LANCZOS
                            )
                            # Convert back to bytes
                            output = io.BytesIO()
                            result_img.save(output, format="PNG")
                            result_bytes = output.getvalue()
                            logger.info(f"Resized from {result_img.size} to ({img_width}, {img_height})")

                        images.append(result_bytes)
                        logger.info(f"Region edit returned {len(result_bytes)} bytes")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to decode image: {e}")

            if not images:
                logger.warning("No image returned from region edit")

        except Exception as e:
            logger.error(f"Region edit failed: {e}")
            raise RuntimeError(f"OpenAI region editing failed: {e}")

        return texts, images

    def generate_viseme_batch(
        self,
        image: bytes,
        mouth_bbox: Tuple[int, int, int, int],
        viseme_prompts: Dict[str, str],
        model: Optional[str] = None,
        style_context: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        **kwargs
    ) -> Dict[str, Tuple[List[str], List[bytes]]]:
        """
        Generate all visemes for a character in batch.

        Args:
            image: Base character image bytes (PNG)
            mouth_bbox: (x, y, width, height) of mouth region
            viseme_prompts: Dictionary mapping viseme names to prompts
            model: Model to use (defaults to gpt-image-1)
            style_context: Optional style description
            progress_callback: Optional callback(viseme_name, index, total)
            **kwargs: Additional parameters

        Returns:
            Dictionary mapping viseme names to (texts, images) tuples
        """
        import logging
        logger = logging.getLogger(__name__)

        results = {}
        total = len(viseme_prompts)

        for i, (viseme_name, prompt) in enumerate(viseme_prompts.items()):
            if progress_callback:
                progress_callback(viseme_name, i, total)

            logger.info(f"Generating viseme {i+1}/{total}: {viseme_name}")

            try:
                texts, images = self.edit_image_region(
                    image=image,
                    region_bbox=mouth_bbox,
                    prompt=prompt,
                    model=model,
                    style_context=style_context,
                    **kwargs
                )
                results[viseme_name] = (texts, images)

                if not images:
                    logger.warning(f"Failed to generate viseme {viseme_name}: no image returned")
            except Exception as e:
                logger.error(f"Failed to generate viseme {viseme_name}: {e}")
                results[viseme_name] = ([], [])

        return results

    def submit_batch_job(
        self,
        requests: List[dict],
        endpoint: str = "/v1/images/generations",
        completion_window: str = "24h",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Submit a Batch API job and persist a record to BATCH_JOBS_PATH.

        Args:
            requests: List of request bodies, each conforming to the chosen endpoint.
                      Each entry must include "model" and the body keys for that endpoint.
            endpoint: Batch endpoint, default ``/v1/images/generations``.
            completion_window: OpenAI completion window string ("24h" supported).
            metadata: Optional metadata to attach to the batch job.

        Returns:
            The OpenAI batch job ID (e.g. "batch_abc123...").
        """
        import json, time, uuid, logging
        from datetime import datetime, timezone
        from core.constants import BATCH_JOBS_PATH

        self._ensure_client()
        logger = logging.getLogger(__name__)

        # Build the JSONL payload in memory.
        lines = []
        for i, req in enumerate(requests):
            line = {
                "custom_id": req.pop("custom_id", f"req-{i}-{uuid.uuid4().hex[:8]}"),
                "method": "POST",
                "url": endpoint,
                "body": req,
            }
            lines.append(json.dumps(line))
        payload_bytes = ("\n".join(lines) + "\n").encode("utf-8")

        # Upload as a Files object with purpose=batch.
        from io import BytesIO
        upload = BytesIO(payload_bytes)
        upload.name = f"imageai_batch_{int(time.time())}.jsonl"
        file_obj = self.client.files.create(file=upload, purpose="batch")

        batch = self.client.batches.create(
            input_file_id=file_obj.id,
            endpoint=endpoint,
            completion_window=completion_window,
            metadata=metadata or {"source": "imageai"},
        )

        job_id = getattr(batch, "id", None) or batch["id"]

        # Persist a small record so the GUI/CLI can list and resume jobs.
        record = {
            "job_id": job_id,
            "input_file_id": file_obj.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "request_count": len(requests),
            "model": (requests[0].get("model") if requests else None),
            "prompt_preview": (
                str(requests[0].get("prompt", ""))[:120] if requests else ""
            ),
            "status": "submitted",
        }
        try:
            BATCH_JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if BATCH_JOBS_PATH.exists():
                try:
                    existing = json.loads(BATCH_JOBS_PATH.read_text(encoding="utf-8"))
                    if not isinstance(existing, list):
                        existing = []
                except (OSError, IOError, ValueError):
                    existing = []
            existing.append(record)
            BATCH_JOBS_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except (OSError, IOError) as e:
            logger.warning(f"Could not persist batch record to {BATCH_JOBS_PATH}: {e}")

        logger.info(f"Submitted batch job {job_id} ({len(requests)} requests, endpoint={endpoint})")
        return job_id

    def check_batch_job(self, job_id: str, output_dir: Optional[Path] = None) -> dict:
        """Poll a batch job; if complete, download images + sidecars to ``output_dir``.

        Returns a dict: {job_id, status, request_counts, output_files, downloaded}.
        ``downloaded`` lists the absolute paths of any files written.
        """
        import json, logging
        logger = logging.getLogger(__name__)

        self._ensure_client()
        batch = self.client.batches.retrieve(job_id)
        status = getattr(batch, "status", None) or batch.get("status")

        result = {
            "job_id": job_id,
            "status": status,
            "request_counts": getattr(batch, "request_counts", None),
            "output_files": [],
            "downloaded": [],
        }

        if status == "completed":
            output_file_id = getattr(batch, "output_file_id", None) or batch.get("output_file_id")
            if output_file_id:
                result["output_files"].append(output_file_id)
                content = self.client.files.content(output_file_id)
                # SDK returns a streaming-friendly object; read() yields bytes.
                raw = content.read() if hasattr(content, "read") else bytes(content)
                if output_dir is not None:
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    # Each line of the output file is a JSON object with "response.body.data[*].b64_json".
                    for i, line in enumerate(raw.decode("utf-8").splitlines()):
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                        except ValueError:
                            continue
                        body = ((entry.get("response") or {}).get("body") or {})
                        for j, item in enumerate(body.get("data", [])):
                            b64 = item.get("b64_json")
                            if not b64:
                                continue
                            out_path = output_dir / f"{job_id}_{i}_{j}.png"
                            out_path.write_bytes(b64decode(b64))
                            result["downloaded"].append(str(out_path))
                            sidecar = out_path.with_suffix(".png.json")
                            sidecar.write_text(
                                json.dumps({
                                    "batch_job_id": job_id,
                                    "custom_id": entry.get("custom_id"),
                                    "model": body.get("model"),
                                }, indent=2),
                                encoding="utf-8",
                            )
        elif status == "failed":
            logger.warning(f"Batch job {job_id} failed: {getattr(batch, 'errors', None)}")

        return result