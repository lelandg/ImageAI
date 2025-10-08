"""
Lyrics-to-Image Prompts Generator

Converts song lyrics into descriptive image generation prompts using LLMs.
Based on the Lyrics-to-Image-Prompt-Guide.md specification.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


@dataclass
class LyricPrompt:
    """A single lyric line with its generated image prompt"""
    line: str  # Original lyric line
    image_prompt: str  # Generated descriptive image prompt

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {"line": self.line, "imagePrompt": self.image_prompt}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LyricPrompt":
        """Create from dictionary"""
        return cls(
            line=data.get("line", ""),
            image_prompt=data.get("imagePrompt", "")
        )


@dataclass
class LyricsToPromptsResult:
    """Result of lyrics-to-prompts generation"""
    prompts: List[LyricPrompt]
    raw_response: str
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching the guide's JSON schema"""
        return {
            "prompts": [p.to_dict() for p in self.prompts]
        }


class LyricsToPromptsGenerator:
    """
    Generates image prompts from lyrics using LLMs.

    Supports multiple LLM providers through LiteLLM:
    - OpenAI (GPT-5, GPT-4)
    - Google (Gemini)
    - Anthropic (Claude)
    - Ollama (local models)
    - LM Studio (local models)
    """

    # System prompt template from the guide
    SYSTEM_PROMPT = """You are a text-to-image prompt generator.
The user will provide song lyrics (one or more lines).
For each lyric line, output one descriptive image prompt suitable for an image generation model.
Do not include commentary or additional text.

Format the response in valid JSON with the following schema:
{
  "prompts": [
    {"line": "original lyric line", "imagePrompt": "detailed descriptive image prompt"}
  ]
}

Rules:
- Keep "line" identical to the input lyric.
- Make "imagePrompt" visually descriptive, cinematic, or stylistically matched to the lyric's tone.
- Avoid repeating phrases or song structure terms.
- Do not include the word "prompt" or reference to AI or art tools."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the generator.

        Args:
            config: Configuration dictionary with API keys
        """
        self.config = config or {}
        self.litellm = None
        self._setup_litellm()
        self._setup_providers()

    def _setup_litellm(self):
        """Set up LiteLLM if available"""
        try:
            import litellm
            self.litellm = litellm
            self.litellm.drop_params = True
            logger.info("LiteLLM initialized for lyrics-to-prompts")
            console.info("✅ LiteLLM initialized")
        except ImportError:
            logger.warning("LiteLLM not installed. Install with: pip install litellm")
            console.error("❌ LiteLLM not installed. Install with: pip install litellm")

    def _setup_providers(self):
        """Set up API keys as environment variables for LiteLLM"""
        if not self.litellm:
            return

        import os

        logger.debug(f"Setting up LLM providers with config keys: {list(self.config.keys())}")

        # OpenAI
        if 'openai_api_key' in self.config and self.config['openai_api_key']:
            os.environ['OPENAI_API_KEY'] = self.config['openai_api_key']
            logger.info("OpenAI API key configured")
            console.info("✅ OpenAI API key configured")
        else:
            logger.debug("No OpenAI API key available")

        # Anthropic (Claude)
        if 'anthropic_api_key' in self.config and self.config['anthropic_api_key']:
            os.environ['ANTHROPIC_API_KEY'] = self.config['anthropic_api_key']
            logger.info("Anthropic API key configured")
            console.info("✅ Anthropic (Claude) API key configured")
        else:
            logger.debug("No Anthropic API key available")

        # Google Gemini
        if 'google_api_key' in self.config and self.config['google_api_key']:
            os.environ['GEMINI_API_KEY'] = self.config['google_api_key']
            logger.info("Google Gemini API key configured")
            console.info("✅ Google Gemini API key configured")
        else:
            logger.debug("No Google API key available")

        # Ollama endpoint
        if 'ollama_endpoint' in self.config and self.config['ollama_endpoint']:
            os.environ['OLLAMA_API_BASE'] = self.config['ollama_endpoint']
        else:
            os.environ['OLLAMA_API_BASE'] = 'http://localhost:11434'

        # LM Studio endpoint
        if 'lmstudio_endpoint' in self.config and self.config['lmstudio_endpoint']:
            os.environ['OPENAI_API_BASE'] = self.config['lmstudio_endpoint']  # LM Studio uses OpenAI-compatible API
        else:
            # Default LM Studio endpoint
            pass  # Only set if explicitly provided

    def generate(
        self,
        lyrics: List[str],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        style_hint: Optional[str] = None
    ) -> LyricsToPromptsResult:
        """
        Generate image prompts from lyrics.

        **IMPORTANT**: This method uses BATCH PROCESSING - all lyrics are sent to the LLM
        in a single API call, and all prompts are generated at once. This is more efficient
        and ensures consistent style across all prompts.

        Args:
            lyrics: List of lyric lines (all sent in one batch)
            model: LLM model to use (e.g., "gpt-4o", "gemini/gemini-2.0-flash-exp", "claude-3-5-sonnet-20241022")
            temperature: Generation temperature (0.0-1.0)
            style_hint: Optional style guidance (e.g., "cinematic", "abstract", "photorealistic")

        Returns:
            LyricsToPromptsResult with generated prompts (one per input lyric line)
        """
        if not self.litellm:
            error = "LiteLLM not available"
            logger.error(error)
            return LyricsToPromptsResult(prompts=[], raw_response="", success=False, error=error)

        if not lyrics:
            error = "No lyrics provided"
            logger.error(error)
            return LyricsToPromptsResult(prompts=[], raw_response="", success=False, error=error)

        # Build user prompt
        lyrics_text = "\n".join(lyrics)
        user_prompt = f"Lyrics:\n{lyrics_text}"

        if style_hint:
            user_prompt += f"\n\nStyle guidance: {style_hint}"

        # Log the request
        logger.info(f"Generating prompts for {len(lyrics)} lyric lines using {model}")
        console.info(f"📝 Processing {len(lyrics)} lyric lines with {model}...")
        console.info(f"Temperature: {temperature}")
        if style_hint:
            console.info(f"Style: {style_hint}")

        try:
            # Call LLM
            response = self.litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=4096
            )

            raw_content = response.choices[0].message.content
            logger.debug(f"Raw LLM response: {raw_content[:200]}...")

            # Parse JSON response
            result = self._parse_response(raw_content, lyrics)

            if result.success:
                console.info(f"✅ Successfully generated {len(result.prompts)} image prompts")

                # Log each prompt
                console.info("\n" + "=" * 60)
                console.info("Generated Image Prompts:")
                console.info("=" * 60)
                for i, prompt in enumerate(result.prompts, 1):
                    console.info(f"\n{i}. Lyric: {prompt.line}")
                    console.info(f"   Prompt: {prompt.image_prompt}")
                console.info("=" * 60 + "\n")
            else:
                console.error(f"❌ Failed to parse response: {result.error}")

            return result

        except Exception as e:
            error = f"LLM generation failed: {str(e)}"
            logger.error(error, exc_info=True)
            console.error(f"❌ {error}")
            return LyricsToPromptsResult(prompts=[], raw_response="", success=False, error=error)

    def _parse_response(self, content: str, original_lyrics: List[str]) -> LyricsToPromptsResult:
        """
        Parse LLM response into structured format.

        Args:
            content: Raw LLM response
            original_lyrics: Original lyric lines for fallback

        Returns:
            LyricsToPromptsResult
        """
        if not content or not content.strip():
            return LyricsToPromptsResult(
                prompts=[],
                raw_response=content,
                success=False,
                error="Empty response from LLM"
            )

        content = content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                # Remove language identifier
                if content.startswith("json") or content.startswith("JSON"):
                    content = content[4:]
                content = content.strip()

        # Try to parse JSON
        try:
            data = json.loads(content)

            # Validate structure
            if not isinstance(data, dict) or "prompts" not in data:
                raise ValueError("Invalid JSON structure: missing 'prompts' key")

            prompts_data = data["prompts"]
            if not isinstance(prompts_data, list):
                raise ValueError("Invalid JSON structure: 'prompts' must be a list")

            # Parse each prompt
            prompts = []
            for item in prompts_data:
                if isinstance(item, dict) and "line" in item and "imagePrompt" in item:
                    prompts.append(LyricPrompt.from_dict(item))
                else:
                    logger.warning(f"Skipping invalid prompt item: {item}")

            if not prompts:
                return LyricsToPromptsResult(
                    prompts=[],
                    raw_response=content,
                    success=False,
                    error="No valid prompts found in response"
                )

            return LyricsToPromptsResult(
                prompts=prompts,
                raw_response=content,
                success=True
            )

        except json.JSONDecodeError as e:
            # JSON parsing failed, try plain text extraction
            logger.warning(f"JSON parsing failed: {e}. Attempting plain text extraction.")
            return self._parse_plain_text(content, original_lyrics)
        except ValueError as e:
            return LyricsToPromptsResult(
                prompts=[],
                raw_response=content,
                success=False,
                error=str(e)
            )

    def _parse_plain_text(self, content: str, original_lyrics: List[str]) -> LyricsToPromptsResult:
        """
        Fallback: parse plain text response.

        Expected format:
        [lyric] → [image description]
        or
        1. Lyric: [lyric]
           Prompt: [description]

        Args:
            content: Plain text content
            original_lyrics: Original lyric lines

        Returns:
            LyricsToPromptsResult
        """
        prompts = []
        lines = content.split('\n')

        current_lyric = None
        current_prompt = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Format 1: "lyric → description"
            if '→' in line:
                parts = line.split('→', 1)
                if len(parts) == 2:
                    lyric = parts[0].strip()
                    prompt = parts[1].strip()
                    # Remove numbering if present
                    lyric = lyric.lstrip('0123456789. ')
                    prompts.append(LyricPrompt(line=lyric, image_prompt=prompt))

            # Format 2: Multi-line with "Lyric:" and "Prompt:" markers
            elif line.lower().startswith('lyric:'):
                current_lyric = line[6:].strip()
            elif line.lower().startswith('prompt:') or line.lower().startswith('image:'):
                marker = 'prompt:' if 'prompt:' in line.lower() else 'image:'
                current_prompt = line[len(marker):].strip()
                if current_lyric and current_prompt:
                    prompts.append(LyricPrompt(line=current_lyric, image_prompt=current_prompt))
                    current_lyric = None
                    current_prompt = None

        if prompts:
            logger.info(f"Extracted {len(prompts)} prompts from plain text")
            return LyricsToPromptsResult(
                prompts=prompts,
                raw_response=content,
                success=True
            )
        else:
            # Ultimate fallback: create simple prompts
            fallback_prompts = []
            for lyric in original_lyrics:
                fallback_prompts.append(
                    LyricPrompt(
                        line=lyric,
                        image_prompt=f"Cinematic visualization of: {lyric}, highly detailed, photorealistic"
                    )
                )

            logger.warning("Using fallback prompts")
            return LyricsToPromptsResult(
                prompts=fallback_prompts,
                raw_response=content,
                success=False,
                error="Could not parse response, using fallback prompts"
            )

    def save_to_json(self, result: LyricsToPromptsResult, output_path: str):
        """
        Save result to JSON file.

        Args:
            result: Generation result
            output_path: Path to output JSON file
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved prompts to {output_path}")
            console.info(f"💾 Saved to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save to {output_path}: {e}")
            console.error(f"❌ Failed to save: {e}")


def load_lyrics_from_file(file_path: str) -> List[str]:
    """
    Load lyrics from a text file.

    Args:
        file_path: Path to lyrics file (one line per lyric)

    Returns:
        List of lyric lines
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines()]
            # Filter out empty lines
            lyrics = [line for line in lines if line]
            logger.info(f"Loaded {len(lyrics)} lyric lines from {file_path}")
            return lyrics
    except Exception as e:
        logger.error(f"Failed to load lyrics from {file_path}: {e}")
        raise
