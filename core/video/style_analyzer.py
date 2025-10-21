"""
Style analyzer for extracting visual continuity information from video frames.

This module uses LLM vision APIs to analyze end frames from previous video clips
and extract style information (lighting, colors, composition, mood) or full
content descriptions for creating seamless visual transitions.
"""

import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ContinuityMode(Enum):
    """Continuity modes for video frame generation"""
    NONE = "none"  # No continuity - generate from source text only
    STYLE_ONLY = "style_only"  # Extract and apply visual style only
    TRANSITION = "transition"  # Full transition - continue from previous frame


class StyleAnalyzer:
    """Analyzes video frames to extract style and content information for continuity."""

    def __init__(self, api_key: str, llm_provider: str = "google", llm_model: str = None):
        """
        Initialize style analyzer.

        Args:
            api_key: API key for the LLM provider
            llm_provider: LLM provider name (google, openai, anthropic)
            llm_model: Specific model to use (optional)
        """
        self.api_key = api_key
        self.llm_provider = llm_provider.lower()
        self.llm_model = llm_model or self._get_default_model()

    def _get_default_model(self) -> str:
        """Get default vision model for the provider."""
        defaults = {
            "google": "gemini-2.5-pro",
            "gemini": "gemini-2.5-pro",
            "openai": "gpt-4o",  # GPT-4 with vision
            "anthropic": "claude-3-5-sonnet-20241022",
            "claude": "claude-3-5-sonnet-20241022"
        }
        return defaults.get(self.llm_provider, "gemini-2.5-pro")

    def analyze_for_style(self, image_path: Path) -> Optional[str]:
        """
        Analyze an image to extract visual style information.

        Extracts: lighting, color palette, composition, camera angle,
        artistic style, mood, and visual aesthetic.

        Args:
            image_path: Path to the image file

        Returns:
            Style description string, or None if analysis fails
        """
        if not image_path or not image_path.exists():
            logger.warning(f"Image path does not exist: {image_path}")
            return None

        prompt = """Analyze this image and extract ONLY the visual style elements for replicating in a new scene.

CRITICAL - Identify the rendering/artistic style FIRST:
- Is it: photorealistic, 3D render, cartoon/animated, anime, hand-drawn, painterly, sketch, etc.?
- If animated/cartoon: what animation style? (Disney, anime, flat colors, cel-shaded, etc.)

Then describe these style elements:
- Lighting: direction, quality, color temperature, shadows
- Color palette: dominant colors, saturation level, contrast
- Composition: framing, camera angle, perspective
- Texture/detail level: smooth, detailed, stylized, etc.
- Line work: bold outlines, soft edges, clean lines, sketchy, etc.
- Mood and atmosphere

Provide 2-3 sentences that start with the RENDERING STYLE, then describe how to replicate the visual aesthetic.
Do NOT describe the content/subjects, only the style that should be applied to a different scene.

Example good output: "3D cartoon style with bold cel-shading and clean black outlines. Vibrant saturated colors with flat shading and minimal texture detail. Warm golden lighting from above creates dramatic shadows, maintaining the playful animated aesthetic."
"""

        try:
            result = self._analyze_image(image_path, prompt)
            if result:
                logger.info(f"Style analysis result (FULL, {len(result)} chars):")
                logger.info(result)
            return result
        except Exception as e:
            logger.error(f"Style analysis failed: {e}")
            return None

    def analyze_for_transition(self, image_path: Path, next_scene_text: str) -> Optional[str]:
        """
        Analyze an image for creating a smooth transition to the next scene.

        Extracts both style and content to create a continuation prompt that
        maintains visual coherence while transitioning to new scene.

        Args:
            image_path: Path to the end frame of previous clip
            next_scene_text: Text description of the next scene

        Returns:
            Transition description combining previous frame and next scene, or None if fails
        """
        if not image_path or not image_path.exists():
            logger.warning(f"Image path does not exist: {image_path}")
            return None

        prompt = f"""Analyze this image as the END of a video clip, then create a smooth transition to the next scene.

NEXT SCENE TEXT: "{next_scene_text}"

Your task:
1. Describe what's currently visible in this final frame (subjects, setting, composition)
2. Identify the visual style (lighting, colors, mood, camera angle)
3. Create a description for the NEXT frame that:
   - Maintains the same visual style (lighting, colors, mood)
   - Shows a natural continuation or evolution
   - Smoothly incorporates the next scene text
   - Feels like the next moment in the same video

Provide a complete image prompt (2-3 sentences) for generating the next frame that will create a seamless visual transition.
Focus on CONTINUITY - the viewer should feel this is one continuous video."""

        try:
            result = self._analyze_image(image_path, prompt)
            if result:
                logger.info(f"Transition analysis result (FULL, {len(result)} chars):")
                logger.info(result)
            return result
        except Exception as e:
            logger.error(f"Transition analysis failed: {e}")
            return None

    def _analyze_image(self, image_path: Path, prompt: str) -> Optional[str]:
        """
        Internal method to send image to LLM with prompt.

        Args:
            image_path: Path to image file
            prompt: Analysis prompt

        Returns:
            LLM response text, or None if fails
        """
        try:
            # Read image data
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Get MIME type
            mime_type = self._get_mime_type(image_path)

            # Route to appropriate provider
            if self.llm_provider in ["google", "gemini"]:
                return self._analyze_with_google(image_data, mime_type, prompt)
            elif self.llm_provider == "openai":
                return self._analyze_with_openai(image_data, mime_type, prompt)
            elif self.llm_provider in ["anthropic", "claude"]:
                return self._analyze_with_anthropic(image_data, mime_type, prompt)
            else:
                raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return None

    def _analyze_with_google(self, image_data: bytes, mime_type: str, prompt: str) -> str:
        """Analyze image using Google Gemini vision API."""
        try:
            import google.genai as genai
            from google.genai import types

            # Create client
            client = genai.Client(api_key=self.api_key)

            # Create content with image
            content = types.Content(
                parts=[
                    types.Part(text=prompt),
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=image_data
                        )
                    )
                ]
            )

            # Generate response
            response = client.models.generate_content(
                model=self.llm_model,
                contents=content,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=1000
                )
            )

            if response and response.text:
                return response.text.strip()
            else:
                raise ValueError("Empty response from Google Gemini")

        except Exception as e:
            logger.error(f"Google Gemini analysis failed: {e}")
            raise

    def _analyze_with_openai(self, image_data: bytes, mime_type: str, prompt: str) -> str:
        """Analyze image using OpenAI vision API."""
        try:
            # Encode to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Try litellm first for better compatibility
            try:
                import litellm
                litellm.drop_params = True

                response = litellm.completion(
                    model=self.llm_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    temperature=0.7,
                    api_key=self.api_key
                )

                return response.choices[0].message.content.strip()

            except ImportError:
                # Fall back to direct OpenAI SDK
                import openai
                client = openai.OpenAI(api_key=self.api_key)

                response = client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    temperature=0.7
                )

                return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}")
            raise

    def _analyze_with_anthropic(self, image_data: bytes, mime_type: str, prompt: str) -> str:
        """Analyze image using Anthropic Claude vision API."""
        try:
            # Encode to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Extract media type from MIME (e.g., "image/png" -> "png")
            media_type = mime_type.split('/')[-1]
            if media_type == "jpg":
                media_type = "jpeg"  # Claude uses "jpeg" not "jpg"

            # Try litellm first
            try:
                import litellm
                litellm.drop_params = True

                response = litellm.completion(
                    model=self.llm_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": mime_type,
                                        "data": image_base64
                                    }
                                },
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ],
                    temperature=0.7,
                    api_key=self.api_key
                )

                return response.choices[0].message.content.strip()

            except ImportError:
                # Fall back to direct Anthropic SDK
                import anthropic
                client = anthropic.Anthropic(api_key=self.api_key)

                response = client.messages.create(
                    model=self.llm_model,
                    max_tokens=1000,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": mime_type,
                                        "data": image_base64
                                    }
                                },
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ]
                )

                return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Anthropic analysis failed: {e}")
            raise

    def _get_mime_type(self, image_path: Path) -> str:
        """Get MIME type from image file extension."""
        import mimetypes

        if not mimetypes.inited:
            mimetypes.init()

        mime_type, _ = mimetypes.guess_type(str(image_path))

        if not mime_type:
            ext = image_path.suffix.lower()
            mime_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp',
                '.tiff': 'image/tiff',
                '.tif': 'image/tiff',
            }
            mime_type = mime_map.get(ext, 'image/jpeg')

        return mime_type


def get_previous_scene_info(project, scene_index: int) -> Tuple[Optional[Path], Optional[str]]:
    """
    Get previous scene's end frame and source text for continuity.

    Args:
        project: VideoProject instance
        scene_index: Current scene index

    Returns:
        Tuple of (previous_end_frame_path, previous_source_text)
        Returns (None, None) if no previous scene or no end frame available
    """
    if scene_index == 0:
        return None, None

    try:
        prev_scene = project.scenes[scene_index - 1]

        # Check if previous scene has an end frame (last frame from video)
        if prev_scene.last_frame and prev_scene.last_frame.exists():
            return prev_scene.last_frame, prev_scene.source

        return None, prev_scene.source

    except (IndexError, AttributeError) as e:
        logger.warning(f"Could not get previous scene info: {e}")
        return None, None
