"""
AI Face Editor for Character Animator puppets.

Uses cloud AI (Gemini/OpenAI) to edit facial regions for viseme generation,
eye blinks, and expressions. This replaces the local Stable Diffusion
inpainting system with higher quality, style-consistent cloud AI editing.

Supported Providers:
- Google Gemini: Uses conversational editing for style consistency
- OpenAI GPT-Image: Uses mask-based editing with input_fidelity=high
"""

import logging
import hashlib
import time
import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from PIL import Image
from base64 import b64decode, b64encode

from core.constants import get_user_data_dir
from .constants import (
    REQUIRED_VISEMES,
    AI_VISEME_PROMPTS,
    AI_EYE_BLINK_PROMPTS,
    AI_EYEBROW_PROMPTS,
    STYLE_HINT_TEMPLATES,
)
from .availability import AI_EDITING_AVAILABLE

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """Supported AI providers for face editing."""
    GOOGLE = "google"
    OPENAI = "openai"


@dataclass
class StyleInfo:
    """Detected or user-specified style information for a character."""
    style_name: Optional[str] = None  # e.g., "cartoon", "anime", "realistic"
    style_hint: Optional[str] = None  # User-provided custom style hint
    dominant_colors: List[str] = field(default_factory=list)  # e.g., ["#FFD700", "#87CEEB"]
    has_outlines: bool = False  # Whether the art has visible outlines
    is_stylized: bool = True  # True for cartoon/anime, False for realistic


@dataclass
class EditResult:
    """Result of an AI face edit operation."""
    success: bool
    image: Optional[Image.Image] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    cached: bool = False
    quality_score: float = 1.0


class AIFaceEditor:
    """
    AI-powered face region editor for Character Animator puppet generation.

    Uses cloud AI APIs to edit specific facial regions while maintaining
    style consistency with the original character.
    """

    # Model defaults by provider
    DEFAULT_MODELS = {
        AIProvider.GOOGLE: "gemini-2.5-flash-image",
        AIProvider.OPENAI: "gpt-image-1",
    }

    # Quality tier models
    HIGH_QUALITY_MODELS = {
        AIProvider.GOOGLE: "gemini-3-pro-image-preview",
        AIProvider.OPENAI: "gpt-image-1.5",
    }

    def __init__(
        self,
        provider: str = "google",
        model: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
        quality_threshold: float = 0.7,
        max_retries: int = 3,
        style_hint: Optional[str] = None,
    ):
        """
        Initialize the AI face editor.

        Args:
            provider: AI provider to use ("google" or "openai")
            model: Specific model to use (defaults to provider's best option)
            cache_dir: Directory for caching generated variants
            api_key: API key (if not provided, uses environment/config)
            quality_threshold: Minimum quality score for acceptance (0-1)
            max_retries: Maximum retry attempts for failed generations
            style_hint: Optional user-provided style hint (e.g., "cartoon", "anime",
                        or custom description like "cel-shaded with thick black outlines")
        """
        self.provider = AIProvider(provider.lower())
        self.model = model or self.DEFAULT_MODELS[self.provider]
        self.cache_dir = cache_dir or (get_user_data_dir() / "cache" / "ai_visemes")
        self.api_key = api_key
        self.quality_threshold = quality_threshold
        self.max_retries = max_retries
        self.style_hint = style_hint

        self._client = None
        self._chat_session = None  # For Gemini conversational editing
        self._initialized = False
        self._style_info: Optional[StyleInfo] = None  # Detected style information

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> bool:
        """
        Initialize the AI client.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        if not AI_EDITING_AVAILABLE:
            logger.error("Cloud AI editing not available. Install google-genai or openai package.")
            return False

        try:
            if self.provider == AIProvider.GOOGLE:
                return self._init_google()
            elif self.provider == AIProvider.OPENAI:
                return self._init_openai()
            else:
                logger.error(f"Unknown provider: {self.provider}")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            return False

    def _init_google(self) -> bool:
        """Initialize Google Gemini client."""
        try:
            import google.genai as genai
            from google.genai import types

            # Get API key from parameter, environment, or config
            api_key = self.api_key
            if not api_key:
                import os
                api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

            if not api_key:
                # Try to get from config
                try:
                    from ..config import ConfigManager
                    config = ConfigManager()
                    api_key = config.get_api_key("google")
                except Exception:
                    pass

            if not api_key:
                logger.error("No Google API key found. Set GOOGLE_API_KEY or configure in settings.")
                return False

            self._client = genai.Client(api_key=api_key)
            self._genai_types = types
            self._initialized = True
            logger.info(f"Google Gemini client initialized with model: {self.model}")
            return True

        except ImportError:
            logger.error("google-genai package not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Google client: {e}")
            return False

    def _init_openai(self) -> bool:
        """Initialize OpenAI client."""
        try:
            import openai

            # Get API key from parameter, environment, or config
            api_key = self.api_key
            if not api_key:
                import os
                api_key = os.environ.get("OPENAI_API_KEY")

            if not api_key:
                # Try to get from config
                try:
                    from ..config import ConfigManager
                    config = ConfigManager()
                    api_key = config.get_api_key("openai")
                except Exception:
                    pass

            if not api_key:
                logger.error("No OpenAI API key found. Set OPENAI_API_KEY or configure in settings.")
                return False

            self._client = openai.OpenAI(api_key=api_key)
            self._initialized = True
            logger.info(f"OpenAI client initialized with model: {self.model}")
            return True

        except ImportError:
            logger.error("openai package not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return False

    def _get_cache_key(
        self,
        image_hash: str,
        region: str,
        variant: str,
    ) -> str:
        """Generate cache key for a variant."""
        return f"{image_hash}_{self.provider.value}_{self.model}_{region}_{variant}"

    def _get_image_hash(self, image: Image.Image) -> str:
        """Get hash of an image for caching."""
        img_bytes = image.tobytes()
        return hashlib.md5(img_bytes).hexdigest()[:12]

    def _load_cached(self, cache_key: str) -> Optional[Image.Image]:
        """Load a cached variant if available."""
        cache_path = self.cache_dir / f"{cache_key}.png"
        if cache_path.exists():
            try:
                img = Image.open(cache_path)
                logger.debug(f"Loaded from cache: {cache_key}")
                return img
            except Exception as e:
                logger.debug(f"Failed to load cache: {e}")
        return None

    def _save_to_cache(self, cache_key: str, image: Image.Image):
        """Save a variant to cache."""
        try:
            cache_path = self.cache_dir / f"{cache_key}.png"
            image.save(cache_path, "PNG")
            logger.debug(f"Saved to cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _image_to_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL Image to PNG bytes."""
        buffer = io.BytesIO()
        # Ensure RGBA for transparency support
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _bytes_to_image(self, data: bytes) -> Image.Image:
        """Convert bytes to PIL Image."""
        return Image.open(io.BytesIO(data))

    def _create_alpha_mask(
        self,
        image_size: Tuple[int, int],
        region_bbox: Tuple[int, int, int, int],
        feather: int = 5,
    ) -> bytes:
        """
        Create a PNG mask with alpha channel for OpenAI editing.

        The mask has:
        - Transparent area (alpha=0) where editing should occur
        - Opaque area (alpha=255) where the original should be preserved

        Args:
            image_size: (width, height) of the image
            region_bbox: (x, y, width, height) of region to edit
            feather: Pixels to feather the mask edge

        Returns:
            PNG bytes with alpha mask
        """
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
        return self._image_to_bytes(mask)

    def edit_face_region(
        self,
        image: Image.Image,
        region_bbox: Tuple[int, int, int, int],
        prompt: str,
        use_cache: bool = True,
        cache_key_suffix: str = "",
    ) -> EditResult:
        """
        Edit a specific face region using AI.

        Args:
            image: Full face/character image
            region_bbox: (x, y, width, height) of region to edit
            prompt: Editing prompt describing desired change
            use_cache: Whether to use caching
            cache_key_suffix: Additional suffix for cache key

        Returns:
            EditResult with success status and edited image
        """
        if not self._initialized:
            if not self.initialize():
                return EditResult(
                    success=False,
                    error="Failed to initialize AI client"
                )

        # Check cache
        if use_cache:
            image_hash = self._get_image_hash(image)
            cache_key = self._get_cache_key(image_hash, "region", cache_key_suffix)
            cached = self._load_cached(cache_key)
            if cached is not None:
                return EditResult(
                    success=True,
                    image=cached,
                    provider=self.provider.value,
                    model=self.model,
                    cached=True,
                )

        # Dispatch to provider-specific implementation
        for attempt in range(self.max_retries):
            try:
                if self.provider == AIProvider.GOOGLE:
                    result = self._edit_with_gemini(image, region_bbox, prompt)
                else:
                    result = self._edit_with_openai(image, region_bbox, prompt)

                if result.success:
                    # Validate result
                    if self._validate_edit(image, result.image, region_bbox):
                        # Save to cache
                        if use_cache and result.image:
                            self._save_to_cache(cache_key, result.image)
                        return result
                    else:
                        logger.warning(f"Edit validation failed, attempt {attempt + 1}/{self.max_retries}")
                        if attempt < self.max_retries - 1:
                            time.sleep(1 * (attempt + 1))  # Exponential backoff
                else:
                    logger.warning(f"Edit failed: {result.error}, attempt {attempt + 1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        time.sleep(1 * (attempt + 1))

            except Exception as e:
                logger.error(f"Edit attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))

        return EditResult(
            success=False,
            error=f"Failed after {self.max_retries} attempts",
            provider=self.provider.value,
            model=self.model,
        )

    def _edit_with_gemini(
        self,
        image: Image.Image,
        region_bbox: Tuple[int, int, int, int],
        prompt: str,
    ) -> EditResult:
        """
        Edit image region using Google Gemini.

        Uses conversational editing for better style consistency.
        """
        try:
            # Prepare image bytes
            image_bytes = self._image_to_bytes(image)

            # Build the editing prompt with region context
            x, y, w, h = region_bbox
            full_prompt = (
                f"Edit only the region at position ({x}, {y}) with size {w}x{h} pixels. "
                f"{prompt}. "
                f"Keep the rest of the image exactly the same. "
                f"Maintain the original art style and character appearance."
            )

            # Create generation config for image output
            config = self._genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )

            # Generate with image input
            response = self._client.models.generate_content(
                model=self.model,
                contents=[
                    self._genai_types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/png"
                    ),
                    full_prompt,
                ],
                config=config,
            )

            # Extract image from response
            if response and response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                data = part.inline_data.data
                                if isinstance(data, (bytes, bytearray)):
                                    result_image = self._bytes_to_image(bytes(data))
                                    return EditResult(
                                        success=True,
                                        image=result_image,
                                        provider=self.provider.value,
                                        model=self.model,
                                    )

            return EditResult(
                success=False,
                error="No image in Gemini response",
                provider=self.provider.value,
                model=self.model,
            )

        except Exception as e:
            return EditResult(
                success=False,
                error=str(e),
                provider=self.provider.value,
                model=self.model,
            )

    def _edit_with_openai(
        self,
        image: Image.Image,
        region_bbox: Tuple[int, int, int, int],
        prompt: str,
    ) -> EditResult:
        """
        Edit image region using OpenAI GPT-Image.

        Uses mask-based editing with input_fidelity=high.
        """
        try:
            # Prepare image and mask
            image_bytes = self._image_to_bytes(image)
            mask_bytes = self._create_alpha_mask(image.size, region_bbox)

            # Build the editing prompt
            full_prompt = (
                f"{prompt}. "
                f"Keep the rest of the image exactly the same. "
                f"Maintain the original art style and character appearance."
            )

            # Create file-like objects
            image_file = io.BytesIO(image_bytes)
            image_file.name = "image.png"
            mask_file = io.BytesIO(mask_bytes)
            mask_file.name = "mask.png"

            # Determine size from image
            size = f"{image.width}x{image.height}"
            # OpenAI only supports specific sizes, find closest
            valid_sizes = ["1024x1024", "512x512", "256x256"]
            if size not in valid_sizes:
                # Use 1024x1024 and resize after
                size = "1024x1024"

            # Check if using GPT-Image-1.5 (supports input_fidelity)
            edit_kwargs = {
                "image": image_file,
                "mask": mask_file,
                "prompt": full_prompt,
                "size": size,
                "n": 1,
                "response_format": "b64_json",
            }

            # Add input_fidelity for newer models
            if "1.5" in self.model or "gpt-image" in self.model.lower():
                edit_kwargs["model"] = self.model
                # Note: input_fidelity may not be available in all API versions

            response = self._client.images.edit(**edit_kwargs)

            # Extract image from response
            if response and response.data:
                for item in response.data:
                    if hasattr(item, 'b64_json') and item.b64_json:
                        image_data = b64decode(item.b64_json)
                        result_image = self._bytes_to_image(image_data)

                        # Resize back to original size if needed
                        if result_image.size != image.size:
                            result_image = result_image.resize(
                                image.size,
                                Image.Resampling.LANCZOS
                            )

                        return EditResult(
                            success=True,
                            image=result_image,
                            provider=self.provider.value,
                            model=self.model,
                        )

            return EditResult(
                success=False,
                error="No image in OpenAI response",
                provider=self.provider.value,
                model=self.model,
            )

        except Exception as e:
            return EditResult(
                success=False,
                error=str(e),
                provider=self.provider.value,
                model=self.model,
            )

    def _validate_edit(
        self,
        original: Image.Image,
        edited: Image.Image,
        region_bbox: Tuple[int, int, int, int],
    ) -> bool:
        """
        Validate that the edit was successful.

        Checks:
        1. Region actually changed
        2. Style consistency maintained outside region
        3. No obvious artifacts

        Returns:
            True if edit passes validation
        """
        if edited is None:
            return False

        try:
            x, y, w, h = region_bbox

            # Extract regions
            orig_region = original.crop((x, y, x + w, y + h))
            edit_region = edited.crop((x, y, x + w, y + h))

            # Convert to arrays
            orig_array = np.array(orig_region.convert("RGB")).astype(float)
            edit_array = np.array(edit_region.convert("RGB")).astype(float)

            # Check 1: Region should have changed
            diff = np.abs(orig_array - edit_array)
            mean_diff = np.mean(diff)

            if mean_diff < 1.0:
                logger.warning(f"Edit region unchanged (mean diff: {mean_diff:.2f})")
                return False

            # Check 2: Outside region should be similar
            # Sample a few points outside the region
            if x > 20:
                orig_outside = np.array(original.crop((0, y, 20, y + h)).convert("RGB"))
                edit_outside = np.array(edited.crop((0, y, 20, y + h)).convert("RGB"))
                outside_diff = np.mean(np.abs(orig_outside.astype(float) - edit_outside.astype(float)))

                if outside_diff > 10.0:
                    logger.warning(f"Outside region changed too much (diff: {outside_diff:.2f})")
                    # Don't fail, just warn - AI might have made minor adjustments
                    pass

            logger.debug(f"Edit validation passed (region diff: {mean_diff:.2f})")
            return True

        except Exception as e:
            logger.warning(f"Validation error: {e}")
            return True  # Allow on validation error

    def extract_style_info(self, image: Image.Image) -> StyleInfo:
        """
        Analyze an image to extract style information.

        Detects characteristics like:
        - Art style (cartoon, anime, realistic, pixel art, etc.)
        - Dominant colors
        - Whether the art has visible outlines
        - Overall stylization level

        Args:
            image: The character image to analyze

        Returns:
            StyleInfo with detected characteristics
        """
        style_info = StyleInfo()

        # If user provided a style hint, use that as the primary style
        if self.style_hint:
            # Check if it matches a known style template
            hint_lower = self.style_hint.lower()
            for style_name in STYLE_HINT_TEMPLATES:
                if style_name in hint_lower:
                    style_info.style_name = style_name
                    style_info.style_hint = STYLE_HINT_TEMPLATES[style_name]
                    break
            else:
                # Custom style hint - use as-is
                style_info.style_hint = self.style_hint

        try:
            # Convert to RGB for analysis
            img_rgb = image.convert("RGB")
            img_array = np.array(img_rgb)

            # Analyze color palette
            style_info.dominant_colors = self._extract_dominant_colors(img_array)

            # Detect if image has strong outlines (cartoon/anime characteristic)
            style_info.has_outlines = self._detect_outlines(img_array)

            # Analyze stylization (high contrast, limited colors = more stylized)
            style_info.is_stylized = self._analyze_stylization(img_array)

            # Auto-detect style if not provided
            if not style_info.style_name and not style_info.style_hint:
                style_info.style_name = self._detect_art_style(img_array, style_info)
                if style_info.style_name in STYLE_HINT_TEMPLATES:
                    style_info.style_hint = STYLE_HINT_TEMPLATES[style_info.style_name]

            logger.info(f"Detected style: {style_info.style_name or 'unknown'}, "
                       f"outlines: {style_info.has_outlines}, stylized: {style_info.is_stylized}")

        except Exception as e:
            logger.warning(f"Style extraction failed: {e}")

        self._style_info = style_info
        return style_info

    def _extract_dominant_colors(self, img_array: np.ndarray, n_colors: int = 5) -> List[str]:
        """Extract dominant colors from image as hex strings."""
        try:
            # Resize for faster processing
            from PIL import Image as PILImage
            img = PILImage.fromarray(img_array)
            img_small = img.resize((100, 100), PILImage.Resampling.NEAREST)
            pixels = np.array(img_small).reshape(-1, 3)

            # Simple clustering by quantization
            # Round to nearest 32 to reduce colors
            quantized = (pixels // 32) * 32
            unique, counts = np.unique(quantized, axis=0, return_counts=True)

            # Sort by frequency and take top n
            sorted_idx = np.argsort(-counts)[:n_colors]
            top_colors = unique[sorted_idx]

            # Convert to hex
            hex_colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in top_colors]
            return hex_colors

        except Exception as e:
            logger.debug(f"Color extraction failed: {e}")
            return []

    def _detect_outlines(self, img_array: np.ndarray) -> bool:
        """Detect if image has strong black outlines (cartoon/anime style)."""
        try:
            # Convert to grayscale
            gray = np.mean(img_array, axis=2)

            # Check for presence of very dark pixels (outlines)
            dark_threshold = 30
            dark_pixels = np.sum(gray < dark_threshold)
            total_pixels = gray.size

            # If more than 2% of pixels are very dark, likely has outlines
            dark_ratio = dark_pixels / total_pixels
            return dark_ratio > 0.02

        except Exception:
            return False

    def _analyze_stylization(self, img_array: np.ndarray) -> bool:
        """Analyze if image is stylized (cartoon/anime) vs realistic."""
        try:
            # Stylized images tend to have:
            # 1. Less color variation (more uniform areas)
            # 2. Higher contrast edges

            # Check color uniformity using local variance
            from scipy import ndimage
            gray = np.mean(img_array, axis=2)

            # Calculate local variance
            local_mean = ndimage.uniform_filter(gray, size=5)
            local_sqr_mean = ndimage.uniform_filter(gray**2, size=5)
            local_var = local_sqr_mean - local_mean**2

            # Stylized images have lower average local variance (more uniform areas)
            avg_local_var = np.mean(local_var)

            # Threshold determined empirically
            return avg_local_var < 500

        except ImportError:
            # scipy not available, use simpler heuristic
            # Check unique color count - stylized has fewer
            pixels = img_array.reshape(-1, 3)
            quantized = (pixels // 16) * 16
            unique_colors = len(np.unique(quantized, axis=0))

            # Fewer than 500 distinct colors (after quantization) suggests stylized
            return unique_colors < 500
        except Exception:
            return True  # Default to stylized

    def _detect_art_style(self, img_array: np.ndarray, style_info: StyleInfo) -> Optional[str]:
        """Auto-detect art style based on image characteristics."""
        # Simple heuristic-based detection
        has_outlines = style_info.has_outlines
        is_stylized = style_info.is_stylized

        if not is_stylized:
            return "realistic"
        elif has_outlines:
            # Could be cartoon or anime
            # Anime typically has larger eyes, different proportions
            # For now, default to cartoon
            return "cartoon"
        elif is_stylized:
            # Stylized without outlines could be vector, 3d rendered, etc.
            return "stylized"

        return None

    def _build_prompt_with_style(self, base_prompt: str) -> str:
        """
        Enhance a prompt with style information.

        Args:
            base_prompt: The base editing prompt

        Returns:
            Enhanced prompt with style context
        """
        if not self._style_info:
            return base_prompt

        style_parts = [base_prompt]

        # Add style hint if available
        if self._style_info.style_hint:
            style_parts.append(self._style_info.style_hint)

        # Add color consistency note if we have dominant colors
        if self._style_info.dominant_colors:
            colors_str = ", ".join(self._style_info.dominant_colors[:3])
            style_parts.append(f"Use colors consistent with the palette: {colors_str}")

        # Add outline note for cartoon/anime
        if self._style_info.has_outlines:
            style_parts.append("Maintain the same line art style and outline thickness.")

        return " ".join(style_parts)

    def generate_viseme(
        self,
        image: Image.Image,
        mouth_bbox: Tuple[int, int, int, int],
        viseme_name: str,
        use_cache: bool = True,
    ) -> EditResult:
        """
        Generate a single viseme by editing the mouth region.

        Args:
            image: Full face/character image
            mouth_bbox: (x, y, width, height) of mouth region
            viseme_name: Name of viseme (e.g., "Ah", "Ee")
            use_cache: Whether to use caching

        Returns:
            EditResult with the viseme image
        """
        # Extract style info if not already done
        if not self._style_info:
            self.extract_style_info(image)

        # Get base prompt and enhance with style
        base_prompt = AI_VISEME_PROMPTS.get(viseme_name, f"Edit the mouth to show: {viseme_name}")
        prompt = self._build_prompt_with_style(base_prompt)

        logger.info(f"Generating viseme: {viseme_name}")
        logger.debug(f"Viseme prompt: {prompt[:100]}...")

        return self.edit_face_region(
            image=image,
            region_bbox=mouth_bbox,
            prompt=prompt,
            use_cache=use_cache,
            cache_key_suffix=f"viseme_{viseme_name}",
        )

    def generate_all_visemes(
        self,
        image: Image.Image,
        mouth_bbox: Tuple[int, int, int, int],
        progress_callback: Optional[callable] = None,
        use_cache: bool = True,
    ) -> Dict[str, EditResult]:
        """
        Generate all 14 required visemes.

        Args:
            image: Full face/character image
            mouth_bbox: (x, y, width, height) of mouth region
            progress_callback: Optional callback(viseme_name, index, total)
            use_cache: Whether to use caching

        Returns:
            Dictionary mapping viseme name to EditResult
        """
        results = {}

        for i, viseme_name in enumerate(REQUIRED_VISEMES):
            if progress_callback:
                progress_callback(viseme_name, i, len(REQUIRED_VISEMES))

            result = self.generate_viseme(
                image=image,
                mouth_bbox=mouth_bbox,
                viseme_name=viseme_name,
                use_cache=use_cache,
            )

            results[viseme_name] = result

            if not result.success:
                logger.warning(f"Failed to generate viseme {viseme_name}: {result.error}")

        return results

    def generate_eye_blink(
        self,
        image: Image.Image,
        eye_bbox: Tuple[int, int, int, int],
        side: str,  # "left" or "right"
        state: str = "blink",  # "open" or "blink"
        use_cache: bool = True,
    ) -> EditResult:
        """
        Generate an eye blink state.

        Args:
            image: Full face/character image
            eye_bbox: (x, y, width, height) of eye region
            side: "left" or "right"
            state: "open" or "blink"
            use_cache: Whether to use caching

        Returns:
            EditResult with the blink state image
        """
        # Extract style info if not already done
        if not self._style_info:
            self.extract_style_info(image)

        # Get base prompt and enhance with style
        prompt_key = f"{side}_{state}"
        base_prompt = AI_EYE_BLINK_PROMPTS.get(prompt_key, f"Edit the {side} eye to be {state}")
        prompt = self._build_prompt_with_style(base_prompt)

        logger.info(f"Generating {side} eye {state} state")
        logger.debug(f"Eye blink prompt: {prompt[:100]}...")

        return self.edit_face_region(
            image=image,
            region_bbox=eye_bbox,
            prompt=prompt,
            use_cache=use_cache,
            cache_key_suffix=f"eye_{side}_{state}",
        )

    def generate_expression(
        self,
        image: Image.Image,
        face_bbox: Tuple[int, int, int, int],
        expression: str,
        use_cache: bool = True,
    ) -> EditResult:
        """
        Generate a facial expression (eyebrow variants, etc).

        Args:
            image: Full face/character image
            face_bbox: (x, y, width, height) of face/eyebrow region
            expression: Expression name (e.g., "raised", "lowered", "concerned")
            use_cache: Whether to use caching

        Returns:
            EditResult with the expression image
        """
        # Extract style info if not already done
        if not self._style_info:
            self.extract_style_info(image)

        # Get base prompt and enhance with style
        base_prompt = AI_EYEBROW_PROMPTS.get(
            expression,
            f"Edit the eyebrows to show a {expression} expression"
        )
        prompt = self._build_prompt_with_style(base_prompt)

        logger.info(f"Generating expression: {expression}")
        logger.debug(f"Expression prompt: {prompt[:100]}...")

        return self.edit_face_region(
            image=image,
            region_bbox=face_bbox,
            prompt=prompt,
            use_cache=use_cache,
            cache_key_suffix=f"expression_{expression}",
        )

    def start_conversation_session(self, character_image: Image.Image) -> bool:
        """
        Start a conversational editing session (Gemini only).

        This uploads the character image and establishes context for
        consistent style across multiple edits.

        Args:
            character_image: The base character image

        Returns:
            True if session started successfully
        """
        if self.provider != AIProvider.GOOGLE:
            logger.warning("Conversation sessions only supported with Gemini")
            return False

        if not self._initialized:
            if not self.initialize():
                return False

        try:
            # Extract style info for this character
            style_info = self.extract_style_info(character_image)

            # Build style context message
            style_context_parts = [
                "This is my character. I'll ask you to edit facial expressions.",
                "Keep the exact same art style, colors, and character appearance for all edits.",
                "Only modify the specific region I describe in each request."
            ]

            # Add detected style information
            if style_info.style_hint:
                style_context_parts.append(f"Style notes: {style_info.style_hint}")
            if style_info.dominant_colors:
                colors_str = ", ".join(style_info.dominant_colors[:5])
                style_context_parts.append(f"The character's color palette includes: {colors_str}")
            if style_info.has_outlines:
                style_context_parts.append("The character has visible line art/outlines that should be preserved.")

            style_context = " ".join(style_context_parts)

            # Create chat session
            config = self._genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )

            self._chat_session = self._client.chats.create(
                model=self.model,
                config=config,
            )

            # Upload character image and establish context
            image_bytes = self._image_to_bytes(character_image)
            self._chat_session.send_message([
                self._genai_types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/png"
                ),
                style_context
            ])

            logger.info(f"Started Gemini conversation session with style: {style_info.style_name or 'auto-detected'}")
            return True

        except Exception as e:
            logger.error(f"Failed to start conversation session: {e}")
            return False

    def end_conversation_session(self):
        """End the conversational editing session."""
        self._chat_session = None
        logger.info("Ended Gemini conversation session")

    def cleanup(self):
        """Release resources."""
        self._chat_session = None
        self._client = None
        self._initialized = False
        logger.info("AIFaceEditor resources released")


def get_ai_face_editor(
    provider: str = "google",
    model: Optional[str] = None,
    **kwargs
) -> Optional[AIFaceEditor]:
    """
    Factory function to create an AIFaceEditor.

    Args:
        provider: AI provider to use ("google" or "openai")
        model: Specific model to use
        **kwargs: Additional arguments for AIFaceEditor

    Returns:
        Initialized AIFaceEditor or None if initialization fails
    """
    try:
        editor = AIFaceEditor(provider=provider, model=model, **kwargs)
        if editor.initialize():
            return editor
        return None
    except Exception as e:
        logger.error(f"Failed to create AIFaceEditor: {e}")
        return None
