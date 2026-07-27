"""LLM response parsing shared by core pipelines and GUI dialogs.

Lives in core (no Qt imports) so PySide6-less CLI paths — e.g.
--style-create — can use it. gui/llm_utils.py re-exports it for
back-compat with existing dialog imports.
"""
import json
import logging
import re
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class LLMResponseParser:
    """Shared parser for LLM responses with fallback handling."""

    @staticmethod
    def parse_json_response(content: str, expected_type: type = list) -> Optional[Any]:
        """
        Parse JSON from LLM response with cleanup.

        Args:
            content: Raw response content
            expected_type: Expected type of parsed result (list or dict)

        Returns:
            Parsed JSON or None if parsing fails
        """
        if not content or not content.strip():
            return None

        content = content.strip()

        # Remove markdown formatting if present
        if content.startswith("```"):
            # Extract content between backticks
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                # Remove language identifier if present
                if content.startswith("json"):
                    content = content[4:]
                elif content.startswith("JSON"):
                    content = content[4:]
                content = content.strip()

        # Try to parse JSON
        try:
            result = json.loads(content)

            # Validate type
            if expected_type and not isinstance(result, expected_type):
                logger.warning(f"Expected {expected_type.__name__}, got {type(result).__name__}")
                return None

            return result
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parsing failed: {e}")
            return None

    @staticmethod
    def extract_text_prompts(content: str, num_items: int = 3) -> List[str]:
        """
        Extract prompts from plain text response.

        Args:
            content: Text content
            num_items: Maximum number of items to extract

        Returns:
            List of extracted prompts
        """
        if not content:
            return []

        lines = content.split('\n')
        prompts = []

        for line in lines:
            line = line.strip()

            # Skip empty lines and headers
            if not line or line.startswith('#') or len(line) < 20:
                continue

            # Clean up common prefixes (1., -, *, etc.)
            cleaned = re.sub(r'^[\d\.\-\*\s]+', '', line).strip()

            # Clean up quotes
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1]
            elif cleaned.startswith("'") and cleaned.endswith("'"):
                cleaned = cleaned[1:-1]

            if cleaned and len(cleaned) > 20:
                prompts.append(cleaned)

            if len(prompts) >= num_items:
                break

        return prompts[:num_items]

    @staticmethod
    def create_fallback_prompts(input_text: str, num_variations: int = 3) -> List[str]:
        """
        Create fallback prompts when LLM fails.

        Args:
            input_text: Original input text
            num_variations: Number of variations to create

        Returns:
            List of fallback prompts
        """
        base_prompts = [
            f"A detailed, photorealistic image of {input_text}",
            f"An artistic interpretation of {input_text}, cinematic lighting, highly detailed",
            f"A creative visualization of {input_text}, trending on artstation, 8k resolution",
            f"A futuristic rendering of {input_text}, volumetric lighting, ultra-detailed",
            f"A stylized depiction of {input_text}, professional photography, high quality"
        ]

        return base_prompts[:num_variations]
