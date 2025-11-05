"""Shared utilities for LLM interactions in dialogs."""

import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QGroupBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QFont, QTextCharFormat, QColor

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


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


class DialogStatusConsole(QGroupBox):
    """Status console widget for displaying LLM interactions in dialogs."""

    def __init__(self, title: str = "Status Console", parent=None):
        super().__init__(title, parent)
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        # Create text display
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        # Remove maximum height constraint to allow expansion
        self.console.setMinimumHeight(100)

        # Set monospace font
        font = QFont("Consolas" if "Consolas" in QFont().families() else "Courier", 9)
        self.console.setFont(font)

        # Dark theme styling
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                padding: 5px;
            }
        """)

        layout.addWidget(self.console)
        # Ensure the console can expand
        layout.setStretchFactor(self.console, 1)

    def log(self, message: str, level: str = "INFO"):
        """
        Log a message to the console.

        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR, SUCCESS)
        """
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Set color based on level
        format = QTextCharFormat()
        if level == "ERROR":
            format.setForeground(QColor("#f14c4c"))
        elif level == "WARNING":
            format.setForeground(QColor("#cca700"))
        elif level == "SUCCESS":
            format.setForeground(QColor("#73c991"))
        else:  # INFO
            format.setForeground(QColor("#d4d4d4"))

        cursor.insertText(f"{message}\n", format)

        # Auto-scroll to bottom
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def clear(self):
        """Clear the console."""
        self.console.clear()

    def separator(self):
        """Add a separator line."""
        self.log("=" * 60)


class LiteLLMHandler:
    """Handler for LiteLLM setup and configuration."""

    @staticmethod
    def setup_litellm(enable_console_logging: bool = True) -> Tuple[bool, Optional[Any]]:
        """
        Set up LiteLLM with proper configuration.

        Args:
            enable_console_logging: Whether to enable console logging

        Returns:
            Tuple of (success, litellm module or None)
        """
        try:
            import litellm
            import logging as py_logging
            import os

            # Set environment variable for debugging if needed
            if enable_console_logging:
                os.environ['LITELLM_LOG'] = 'INFO'

                # Set up custom handler to capture litellm logs
                class LiteLLMConsoleHandler(py_logging.Handler):
                    def emit(self, record):
                        if record.name == "LiteLLM":
                            # Only show the message, not the file info
                            msg = record.getMessage()
                            console.info(f"LiteLLM: {msg}")

                # Add console handler for litellm
                litellm_logger = py_logging.getLogger("LiteLLM")

                # Remove existing handlers to avoid duplicates
                litellm_logger.handlers = []

                console_handler = LiteLLMConsoleHandler()
                console_handler.setFormatter(py_logging.Formatter('%(message)s'))
                litellm_logger.addHandler(console_handler)

            litellm.drop_params = True  # Drop unsupported params

            logger.info("LiteLLM set up successfully")
            if enable_console_logging:
                console.info("LiteLLM ready for use")

            return True, litellm

        except ImportError:
            logger.warning("LiteLLM not installed")
            if enable_console_logging:
                console.warning("LiteLLM not installed, using direct SDK")
            return False, None

    @staticmethod
    def prepare_request(provider: str, model: str, messages: List[Dict[str, str]],
                        temperature: float = 0.7, max_tokens: int = 1000,
                        api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Prepare request data for LiteLLM.

        Args:
            provider: LLM provider name
            model: Model name
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Maximum tokens
            api_key: Optional API key (determines auth mode for Google/Gemini)

        Returns:
            Request dictionary
        """
        # Handle provider-specific model naming
        if provider.lower() == "google" or provider.lower() == "gemini":
            # Determine model prefix based on auth mode
            # - API key mode: use "gemini/" (Google AI Studio API)
            # - gcloud/ADC mode: use "vertex_ai/" (Google Cloud Vertex AI)
            if api_key:
                # API key authentication - use Google AI Studio
                if not model.startswith("gemini/"):
                    model = f"gemini/{model}"
            else:
                # Google Cloud authentication (ADC) - use Vertex AI
                if not model.startswith("vertex_ai/"):
                    model = f"vertex_ai/{model}"

        return {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }