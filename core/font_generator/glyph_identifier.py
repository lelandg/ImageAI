"""
AI-based glyph identification for font generator.

Uses AI vision capabilities to identify small glyphs
(punctuation, special characters) that are difficult to detect
with traditional contour-based methods.

Supports multiple providers:
- Anthropic Claude (recommended for accuracy)
- Google Gemini (fallback)
"""

import logging
import io
import base64
import os
from typing import List, Optional, Tuple
from dataclasses import dataclass

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


@dataclass
class GlyphIdentificationResult:
    """Result of AI glyph identification."""
    identified_char: Optional[str]
    confidence: float
    alternatives: List[str]  # Other possible characters
    error: Optional[str] = None


@dataclass
class BatchIdentificationResult:
    """Result of batch glyph identification."""
    identifications: List[GlyphIdentificationResult]
    total_glyphs: int
    successful_count: int
    error: Optional[str] = None


def get_position_hint(glyph_y: int, glyph_height: int, row_height: int) -> str:
    """
    Determine vertical position hint for a glyph within its row.

    Args:
        glyph_y: Y position of glyph within the row (0 = top of row)
        glyph_height: Height of the glyph
        row_height: Total height of the text row

    Returns:
        Position hint: "top", "middle", "bottom", or "full"
    """
    if row_height <= 0:
        return "middle"

    # Calculate where the glyph sits in the row
    glyph_center = glyph_y + glyph_height / 2
    glyph_top_ratio = glyph_y / row_height
    glyph_bottom_ratio = (glyph_y + glyph_height) / row_height

    # Determine position based on where glyph sits
    if glyph_height > row_height * 0.7:
        return "full"  # Spans most of the row (like |, !, l)
    elif glyph_bottom_ratio < 0.5:
        return "top"  # Upper half only (like ', ")
    elif glyph_top_ratio > 0.5:
        return "bottom"  # Lower half only (like ,, .)
    else:
        return "middle"  # Center area (like -, ~)


class AIGlyphIdentifier:
    """
    Uses AI vision models to identify individual glyph images.

    Supports:
    - Anthropic Claude (claude-opus-4-5-20251101) - Best accuracy for character recognition
    - Google Gemini (gemini-2.5-flash/pro) - Fast fallback option
    """

    # Characters that are commonly confused
    SIMILAR_CHARS = {
        '.': [',', "'", '`'],
        ',': ['.', "'", ';'],
        "'": ['"', '`', '.', ','],
        '"': ["'", '``'],
        ':': [';', '..'],
        ';': [':', ','],
        '!': ['|', 'l', '1', 'i'],
        '?': ['¿'],
        '-': ['_', '–', '—'],
        '_': ['-', '–'],
        '|': ['l', '1', 'I', '!'],
        '/': ['\\', '|'],
        '\\': ['/', '|'],
        '(': ['[', '{', 'C'],
        ')': [']', '}'],
        '[': ['(', '{'],
        ']': [')', '}'],
        '{': ['(', '['],
        '}': [')', ']'],
        '<': ['(', '[', '«'],
        '>': [')', ']', '»'],
    }

    # Provider constants
    PROVIDER_ANTHROPIC = "anthropic"
    PROVIDER_GEMINI = "gemini"

    # Default models by provider
    DEFAULT_MODELS = {
        PROVIDER_ANTHROPIC: "claude-opus-4-5-20251101",
        PROVIDER_GEMINI: "gemini-2.5-pro",  # Pro for better accuracy than flash
    }

    def __init__(
        self,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_cloud_auth: bool = True,
    ):
        """
        Initialize the glyph identifier.

        Args:
            provider: AI provider - "anthropic" (recommended) or "gemini"
            api_key: API key (optional, will try config/environment)
            model: Model to use (optional, uses provider default if not specified)
            use_cloud_auth: If True, try Application Default Credentials for Gemini
        """
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODELS.get(self.provider, self.DEFAULT_MODELS[self.PROVIDER_ANTHROPIC])
        self.use_cloud_auth = use_cloud_auth
        self._client = None
        self._anthropic_client = None
        self._auth_method = None  # Track which auth method was used

    def _ensure_client(self) -> bool:
        """Ensure the AI client is initialized for the configured provider."""
        if self.provider == self.PROVIDER_ANTHROPIC:
            return self._ensure_anthropic_client()
        else:
            return self._ensure_gemini_client()

    def _ensure_anthropic_client(self) -> bool:
        """Ensure the Anthropic client is initialized."""
        if self._anthropic_client is not None:
            return True

        try:
            import anthropic

            # Get API key
            api_key = self.api_key
            if not api_key:
                # Try environment variable first
                api_key = os.environ.get("ANTHROPIC_API_KEY")

            if not api_key:
                # Try config manager
                try:
                    from core.config import ConfigManager
                    config = ConfigManager()
                    api_key = config.get_api_key("anthropic")
                except Exception as e:
                    logger.debug(f"Could not get API key from config: {e}")

            if not api_key:
                logger.error("No Anthropic API key available for glyph identification")
                console.error("No Anthropic API key found. Configure in Settings or set ANTHROPIC_API_KEY environment variable.")
                return False

            self._anthropic_client = anthropic.Anthropic(api_key=api_key)
            self._auth_method = "Anthropic API Key"
            logger.info(f"Initialized Anthropic client (model: {self.model})")
            console.info(f"Using Claude {self.model} for glyph identification")
            return True

        except ImportError as e:
            logger.error(f"Failed to import anthropic: {e}")
            console.error("Anthropic SDK not installed. Run: pip install anthropic")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            return False

    def _ensure_gemini_client(self) -> bool:
        """Ensure the Gemini client is initialized."""
        if self._client is not None:
            return True

        try:
            from google import genai

            # Try cloud auth first if enabled
            if self.use_cloud_auth and not self.api_key:
                try:
                    from google.auth import default as google_auth_default

                    credentials, project = google_auth_default()
                    if not project:
                        # Try to get from gcloud config
                        import subprocess
                        result = subprocess.run(
                            ["gcloud", "config", "get-value", "project"],
                            capture_output=True, text=True, timeout=5
                        )
                        project = result.stdout.strip()

                    if project:
                        self._client = genai.Client(
                            vertexai=True,
                            project=project,
                            location="us-central1"
                        )
                        self._auth_method = f"Cloud Auth (project: {project})"
                        logger.info(f"Initialized Gemini client with Cloud Auth (project: {project}, model: {self.model})")
                        return True
                except Exception as e:
                    logger.debug(f"Cloud auth failed, falling back to API key: {e}")

            # Fall back to API key
            api_key = self.api_key
            if not api_key:
                from core.config import ConfigManager
                config = ConfigManager()
                api_key = config.get_api_key("google")

            if not api_key:
                logger.error("No Google API key available for glyph identification")
                return False

            self._client = genai.Client(api_key=api_key)
            self._auth_method = "Gemini API Key"
            logger.info(f"Initialized Gemini client with API Key (model: {self.model})")
            return True

        except ImportError as e:
            logger.error(f"Failed to import google-genai: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            return False

    def identify_glyph(
        self,
        glyph_image: np.ndarray | Image.Image,
        context_chars: Optional[str] = None,
        position_hint: Optional[str] = None,
    ) -> GlyphIdentificationResult:
        """
        Identify a single glyph image using AI vision.

        Args:
            glyph_image: The glyph image (numpy array or PIL Image)
            context_chars: Characters expected in the font (helps AI narrow down)
            position_hint: Vertical position hint ("top", "middle", "bottom", "baseline")
                          to help distinguish similar chars like ' vs ,

        Returns:
            GlyphIdentificationResult with identified character
        """
        if not self._ensure_client():
            return GlyphIdentificationResult(
                identified_char=None,
                confidence=0.0,
                alternatives=[],
                error=f"{self.provider.title()} client not available"
            )

        # Convert to PIL Image if needed
        if isinstance(glyph_image, np.ndarray):
            pil_image = Image.fromarray(glyph_image)
        else:
            pil_image = glyph_image

        # Ensure RGB mode
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        # Build prompt with position hint
        prompt = self._build_identification_prompt(context_chars, position_hint)

        # Dispatch to appropriate provider
        if self.provider == self.PROVIDER_ANTHROPIC:
            return self._identify_glyph_anthropic(pil_image, prompt)
        else:
            return self._identify_glyph_gemini(pil_image, prompt)

    def _identify_glyph_anthropic(
        self,
        pil_image: Image.Image,
        prompt: str,
    ) -> GlyphIdentificationResult:
        """Identify a glyph using Anthropic Claude."""
        try:
            # Convert image to base64
            buffer = io.BytesIO()
            pil_image.save(buffer, format='PNG')
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # Log the AI request
            logger.info("=" * 60)
            logger.info("AI GLYPH IDENTIFICATION REQUEST (Claude)")
            logger.info(f"  Auth: {self._auth_method}")
            logger.info(f"  Model: {self.model}")
            logger.info(f"  Image size: {pil_image.size}")
            logger.info(f"  Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"  Prompt: {prompt}")
            logger.info("=" * 60)

            # Send to Claude
            response = self._anthropic_client.messages.create(
                model=self.model,
                max_tokens=50,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
            )

            # Log the response
            logger.info("AI GLYPH IDENTIFICATION RESPONSE (Claude)")
            if response and response.content:
                response_text = response.content[0].text
                logger.info(f"  Response: {response_text.strip()}")
                result = self._parse_response(response_text)
                logger.info(f"  Identified: '{result.identified_char}' (confidence: {result.confidence:.0%})")
                logger.info("=" * 60)
                return result
            else:
                logger.warning("  Response: EMPTY")
                logger.info("=" * 60)
                return GlyphIdentificationResult(
                    identified_char=None,
                    confidence=0.0,
                    alternatives=[],
                    error="Empty response from Claude"
                )

        except Exception as e:
            logger.error(f"Claude glyph identification failed: {e}")
            return GlyphIdentificationResult(
                identified_char=None,
                confidence=0.0,
                alternatives=[],
                error=str(e)
            )

    def _identify_glyph_gemini(
        self,
        pil_image: Image.Image,
        prompt: str,
    ) -> GlyphIdentificationResult:
        """Identify a glyph using Google Gemini."""
        try:
            from google.genai import types

            # Log the AI request
            logger.info("=" * 60)
            logger.info("AI GLYPH IDENTIFICATION REQUEST")
            logger.info(f"  Auth: {self._auth_method}")
            logger.info(f"  Model: {self.model}")
            logger.info(f"  Image size: {pil_image.size}")
            logger.info(f"  Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"  Prompt: {prompt}")
            logger.info("=" * 60)

            # Send to Gemini
            response = self._client.models.generate_content(
                model=self.model,
                contents=[pil_image, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for accurate identification
                    max_output_tokens=50
                )
            )

            # Log the response
            logger.info("AI GLYPH IDENTIFICATION RESPONSE")
            if response and response.text:
                logger.info(f"  Response: {response.text.strip()}")
                result = self._parse_response(response.text)
                logger.info(f"  Identified: '{result.identified_char}' (confidence: {result.confidence:.0%})")
                logger.info("=" * 60)
                return result
            else:
                logger.warning("  Response: EMPTY")
                logger.info("=" * 60)
                return GlyphIdentificationResult(
                    identified_char=None,
                    confidence=0.0,
                    alternatives=[],
                    error="Empty response from Gemini"
                )

        except Exception as e:
            logger.error(f"Glyph identification failed: {e}")
            return GlyphIdentificationResult(
                identified_char=None,
                confidence=0.0,
                alternatives=[],
                error=str(e)
            )

    def identify_multiple_glyphs(
        self,
        glyph_images: List,
        context_chars: Optional[str] = None,
    ) -> List[Tuple[str, GlyphIdentificationResult]]:
        """
        Identify multiple glyph images.

        Args:
            glyph_images: List of tuples. Each tuple can be:
                          - (image, current_label) - 2-tuple without position hint
                          - (image, current_label, position_hint) - 3-tuple with position hint
                          position_hint can be "top", "middle", "bottom", "full".
            context_chars: Characters expected in the font

        Returns:
            List of (current_label, result) tuples
        """
        results = []
        for item in glyph_images:
            # Handle both (image, label) and (image, label, position_hint) tuples
            if len(item) >= 3:
                glyph_img, current_label, position_hint = item[0], item[1], item[2]
            else:
                glyph_img, current_label = item[0], item[1]
                position_hint = None

            result = self.identify_glyph(glyph_img, context_chars, position_hint)
            results.append((current_label, result))
            logger.info(
                f"Glyph '{current_label}' identified as '{result.identified_char}' "
                f"(confidence: {result.confidence:.0%})"
            )
        return results

    def _build_identification_prompt(
        self,
        context_chars: Optional[str],
        position_hint: Optional[str] = None,
    ) -> str:
        """Build the prompt for glyph identification.

        Args:
            context_chars: Characters expected in the font
            position_hint: Vertical position hint like "top", "middle", "bottom", "baseline"
        """
        base_prompt = """You are analyzing a handwritten or typed character for font creation.
Look at this image of a single character glyph and identify what character it is.

IMPORTANT:
- Look carefully at the shape, considering it might be a punctuation mark or symbol
- Common small characters include: . , ; : ! ? ' " - _ ( ) [ ] { } < > / \\ @ # $ % ^ & * + = ~ `
- The image may be small or low-resolution
- Consider the context of handwriting samples"""

        # Add position-based disambiguation hints
        if position_hint:
            base_prompt += f"""

POSITION HINT: This character was found at the {position_hint} of the text line.
Use this to help distinguish similar characters:
- Apostrophe (') and comma (,) look similar but: apostrophe is at TOP, comma is at BOTTOM/baseline
- Period (.) is at the BOTTOM/baseline
- Quote marks (" ') are at the TOP
- Hyphen (-) and underscore (_): hyphen is MIDDLE, underscore is BOTTOM
- Colon (:) spans from TOP to BOTTOM, semicolon (;) has dot at BOTTOM"""

        base_prompt += """

Respond with ONLY the character you see, nothing else.
If you cannot identify it, respond with "?"."""

        if context_chars:
            # Include context about what characters are expected
            base_prompt += f"""

The font being created includes these characters: {context_chars}
The character in the image should be one of these or a common punctuation mark."""

        return base_prompt

    def _parse_response(self, response_text: str) -> GlyphIdentificationResult:
        """Parse Gemini's response into a result."""
        # Clean up response
        char = response_text.strip()

        # Handle special cases
        if not char or char == "?":
            return GlyphIdentificationResult(
                identified_char=None,
                confidence=0.0,
                alternatives=[],
                error="Could not identify character"
            )

        # If response is longer than expected, try to extract the character
        if len(char) > 3:
            # Look for quoted character
            import re
            quoted = re.search(r"['\"](.)['\"]", char)
            if quoted:
                char = quoted.group(1)
            else:
                # Take first non-whitespace character
                char = char.strip()[0] if char.strip() else "?"

        # Get first character only
        identified = char[0] if char else None

        # Determine confidence based on response clarity
        confidence = 0.9 if len(response_text.strip()) <= 3 else 0.7

        # Get similar characters as alternatives
        alternatives = self.SIMILAR_CHARS.get(identified, [])

        return GlyphIdentificationResult(
            identified_char=identified,
            confidence=confidence,
            alternatives=alternatives[:3]  # Max 3 alternatives
        )

    def analyze_region_for_splitting(
        self,
        region_image: np.ndarray | Image.Image,
        expected_width: float,
    ) -> Tuple[int, List[float]]:
        """
        Analyze a region to determine if it contains multiple characters.

        Uses AI to count characters and suggest split positions.

        Args:
            region_image: Image of the region to analyze
            expected_width: Expected width of a single character

        Returns:
            Tuple of (character_count, split_ratios)
            split_ratios are values between 0-1 indicating where to split
        """
        if not self._ensure_client():
            return (1, [])  # Assume single character if AI unavailable

        try:
            from google.genai import types

            # Convert to PIL Image if needed
            if isinstance(region_image, np.ndarray):
                pil_image = Image.fromarray(region_image)
            else:
                pil_image = region_image

            # Ensure RGB mode
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            prompt = """Analyze this image from a handwriting sample for font creation.

COUNT how many distinct characters are in this image.
Characters may be touching or very close together.

IMPORTANT:
- Look for natural boundaries between characters
- Consider that brackets [], braces {}, parentheses () are PAIRS (2 characters)
- Quotes "" or '' are PAIRS (2 characters)
- Each letter, number, or punctuation mark is ONE character

Respond in this EXACT format:
COUNT: <number>
SPLITS: <comma-separated percentages where to split, or "none" if single character>

Examples:
- Single letter 'A': "COUNT: 1\\nSPLITS: none"
- Two touching letters 'AB': "COUNT: 2\\nSPLITS: 50"
- Three characters: "COUNT: 3\\nSPLITS: 33, 66"
- Brackets '[]': "COUNT: 2\\nSPLITS: 50"
"""

            # Log the AI request
            logger.info("=" * 60)
            logger.info("AI REGION SPLIT ANALYSIS REQUEST")
            logger.info(f"  Auth: {self._auth_method}")
            logger.info(f"  Model: {self.model}")
            logger.info(f"  Region size: {pil_image.size}")
            logger.info(f"  Prompt: Analyzing region for character count and split points")
            logger.info("=" * 60)

            response = self._client.models.generate_content(
                model=self.model,
                contents=[pil_image, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=100
                )
            )

            # Log the response
            logger.info("AI REGION SPLIT ANALYSIS RESPONSE")
            if response and response.text:
                logger.info(f"  Response: {response.text.strip()}")
                count, splits = self._parse_split_response(response.text)
                logger.info(f"  Parsed: count={count}, splits={splits}")
                logger.info("=" * 60)
                return (count, splits)
            else:
                logger.warning("  Response: EMPTY")
                logger.info("=" * 60)
                return (1, [])

        except Exception as e:
            logger.error(f"AI region analysis failed: {e}")
            logger.info("=" * 60)
            return (1, [])

    def _parse_split_response(self, response_text: str) -> Tuple[int, List[float]]:
        """Parse the split analysis response."""
        try:
            lines = response_text.strip().split('\n')
            count = 1
            splits = []

            for line in lines:
                line = line.strip().upper()
                if line.startswith('COUNT:'):
                    count_str = line.replace('COUNT:', '').strip()
                    # Extract first number
                    import re
                    match = re.search(r'\d+', count_str)
                    if match:
                        count = int(match.group())

                elif line.startswith('SPLITS:'):
                    splits_str = line.replace('SPLITS:', '').strip().lower()
                    if splits_str != 'none' and splits_str:
                        # Parse comma-separated percentages
                        import re
                        numbers = re.findall(r'\d+(?:\.\d+)?', splits_str)
                        splits = [float(n) / 100.0 for n in numbers if float(n) <= 100]

            logger.debug(f"AI split analysis: count={count}, splits={splits}")
            return (count, splits)

        except Exception as e:
            logger.error(f"Failed to parse split response: {e}")
            return (1, [])

    def count_characters_in_image(
        self,
        image: np.ndarray | Image.Image,
    ) -> int:
        """
        Count total characters in a full handwriting sample image.

        Args:
            image: Full handwriting sample image

        Returns:
            Estimated character count
        """
        if not self._ensure_client():
            return 0

        try:
            from google.genai import types

            # Convert to PIL Image if needed
            if isinstance(image, np.ndarray):
                pil_image = Image.fromarray(image)
            else:
                pil_image = image

            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            prompt = """Count ALL characters in this handwriting sample image.

This is a font character sheet containing:
- Uppercase letters (A-Z)
- Lowercase letters (a-z)
- Numbers (0-9)
- Punctuation marks (like . , ; : ! ? ' " - _ etc.)

Count EVERY individual character you can see.
Respond with ONLY a number, nothing else."""

            response = self._client.models.generate_content(
                model=self.model,
                contents=[pil_image, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=20
                )
            )

            if response and response.text:
                import re
                match = re.search(r'\d+', response.text.strip())
                if match:
                    count = int(match.group())
                    logger.info(f"AI counted {count} characters in image")
                    return count

            return 0

        except Exception as e:
            logger.error(f"AI character counting failed: {e}")
            return 0

    def batch_identify(
        self,
        glyph_images: List[np.ndarray | Image.Image],
        expected_chars: Optional[str] = None,
        max_per_request: int = 20,
    ) -> List[GlyphIdentificationResult]:
        """Identify multiple glyphs in batch using a single AI request."""
        if not glyph_images:
            return []

        if not self._ensure_client():
            return [
                GlyphIdentificationResult(
                    identified_char=None, confidence=0.0, alternatives=[],
                    error="Gemini client not available"
                )
                for _ in glyph_images
            ]

        try:
            from google.genai import types

            pil_images = []
            for img in glyph_images:
                if isinstance(img, np.ndarray):
                    pil_img = Image.fromarray(img)
                else:
                    pil_img = img
                if pil_img.mode != 'RGB':
                    pil_img = pil_img.convert('RGB')
                pil_images.append(pil_img)

            all_results = []
            for batch_start in range(0, len(pil_images), max_per_request):
                batch_images = pil_images[batch_start:batch_start + max_per_request]
                batch_results = self._identify_batch(batch_images, expected_chars)
                all_results.extend(batch_results)

            return all_results

        except Exception as e:
            logger.error(f"Batch identification failed: {e}")
            return [
                GlyphIdentificationResult(
                    identified_char=None, confidence=0.0, alternatives=[], error=str(e)
                )
                for _ in glyph_images
            ]

    def _identify_batch(
        self,
        pil_images: List[Image.Image],
        expected_chars: Optional[str],
    ) -> List[GlyphIdentificationResult]:
        """Identify a batch of images in a single API call."""
        from google.genai import types

        composite, positions = self._create_numbered_composite(pil_images)
        prompt = self._build_batch_prompt(len(pil_images), expected_chars)

        logger.info("=" * 60)
        logger.info("AI BATCH IDENTIFICATION REQUEST")
        logger.info(f"  Auth: {self._auth_method}")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  Glyph count: {len(pil_images)}")
        logger.info("=" * 60)

        response = self._client.models.generate_content(
            model=self.model,
            contents=[composite, prompt],
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=500)
        )

        logger.info("AI BATCH IDENTIFICATION RESPONSE")
        if response and response.text:
            logger.info(f"  Response: {response.text[:200]}...")
            results = self._parse_batch_response(response.text, len(pil_images))
            logger.info(f"  Parsed {len(results)} identifications")
            logger.info("=" * 60)
            return results
        else:
            logger.warning("  Response: EMPTY")
            logger.info("=" * 60)
            return [
                GlyphIdentificationResult(
                    identified_char=None, confidence=0.0, alternatives=[], error="Empty response"
                )
                for _ in pil_images
            ]

    def _create_numbered_composite(
        self,
        images: List[Image.Image],
    ) -> Tuple[Image.Image, List[Tuple[int, int]]]:
        """Create a composite image with numbered glyphs arranged in a grid."""
        from PIL import ImageDraw

        n = len(images)
        cols = min(10, n)
        rows = (n + cols - 1) // cols

        max_w = max(img.width for img in images)
        max_h = max(img.height for img in images)

        cell_w = max_w + 20
        cell_h = max_h + 30

        composite_w = cols * cell_w
        composite_h = rows * cell_h
        composite = Image.new('RGB', (composite_w, composite_h), 'white')
        draw = ImageDraw.Draw(composite)

        positions = []
        for i, img in enumerate(images):
            row = i // cols
            col = i % cols

            x = col * cell_w + (cell_w - img.width) // 2
            y = row * cell_h + 20

            composite.paste(img, (x, y))
            positions.append((x, y))

            number_x = col * cell_w + cell_w // 2
            number_y = row * cell_h + 5
            draw.text((number_x, number_y), str(i + 1), fill='black', anchor='mt')

        return composite, positions

    def _build_batch_prompt(self, count: int, expected_chars: Optional[str]) -> str:
        """Build prompt for batch identification."""
        prompt = f"""You are analyzing {count} numbered character glyphs for font creation.
Each glyph is numbered 1 through {count} in the image.

For EACH numbered glyph, identify the character it represents.

IMPORTANT:
- Look at each glyph carefully
- Consider both letters (uppercase/lowercase) and symbols/punctuation
- Some may be partial or unclear

Respond with EXACTLY {count} lines in this format:
1. <character> (<confidence>%)
2. <character> (<confidence>%)
...

Use "?" if you cannot identify a glyph.
"""

        if expected_chars:
            prompt += f"""
The expected characters in this font are: {expected_chars}
Each glyph should be one of these characters."""

        return prompt

    def _parse_batch_response(
        self,
        response_text: str,
        expected_count: int,
    ) -> List[GlyphIdentificationResult]:
        """Parse the batch identification response."""
        import re

        results = []
        lines = response_text.strip().split('\n')

        for i in range(expected_count):
            if i < len(lines):
                line = lines[i].strip()
                match = re.match(r'\d+\.\s*(.+?)(?:\s*\((\d+)%?\))?$', line)
                if match:
                    char = match.group(1).strip()
                    confidence_str = match.group(2)
                    confidence = int(confidence_str) / 100 if confidence_str else 0.7

                    if len(char) > 1:
                        char = char[0]

                    if char == '?':
                        results.append(GlyphIdentificationResult(
                            identified_char=None, confidence=0.0, alternatives=[],
                            error="Could not identify"
                        ))
                    else:
                        results.append(GlyphIdentificationResult(
                            identified_char=char,
                            confidence=confidence,
                            alternatives=self.SIMILAR_CHARS.get(char, [])[:3]
                        ))
                else:
                    results.append(GlyphIdentificationResult(
                        identified_char=None, confidence=0.0, alternatives=[],
                        error=f"Could not parse line: {line}"
                    ))
            else:
                results.append(GlyphIdentificationResult(
                    identified_char=None, confidence=0.0, alternatives=[],
                    error="Missing in response"
                ))

        return results
