"""Shared utilities for LLM interactions in dialogs."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QGroupBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QFont, QTextCharFormat, QColor

from core.llm_parsing import LLMResponseParser  # noqa: F401 — back-compat re-export
from core.logging_config import SecretRedactionFilter

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


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


class LLMHandler:
    """Handler for LLM client setup and configuration."""

    @staticmethod
    def setup_llm(enable_console_logging: bool = True) -> Tuple[bool, Any]:
        """
        Set up the vendored chameleon_llm package.

        Args:
            enable_console_logging: Whether to mirror package logs to the console

        Returns:
            Tuple of (True, the ``core.chameleon_llm`` module); call
            ``.completion(...)`` on the module.
        """
        from core import chameleon_llm

        if enable_console_logging:
            pkg_logger = logging.getLogger("chameleon_llm")

            # Remove our own earlier handler so repeated setup never stacks.
            for existing in list(pkg_logger.handlers):
                if getattr(existing, "_imageai_console", False):
                    pkg_logger.removeHandler(existing)

            class ChameleonLLMConsoleHandler(logging.Handler):
                _imageai_console = True

                def emit(self, record):
                    # Only show the message, not the file info
                    console.info(f"LLM: {record.getMessage()}")

            console_handler = ChameleonLLMConsoleHandler()
            console_handler.setFormatter(logging.Formatter('%(message)s'))
            # This handler runs before propagation to the root logger, so
            # it needs its own redaction filter.
            console_handler.addFilter(SecretRedactionFilter())
            pkg_logger.addHandler(console_handler)

        logger.info("LLM client (chameleon_llm) set up successfully")
        if enable_console_logging:
            console.info("LLM client ready for use")

        return True, chameleon_llm

    @staticmethod
    def prepare_request(provider: str, model: str, messages: List[Dict[str, str]],
                        temperature: float = 0.7, max_tokens: int = 1000,
                        api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Prepare request data for a ``chameleon_llm.completion`` call.

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

