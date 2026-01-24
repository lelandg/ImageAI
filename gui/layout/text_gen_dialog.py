"""Text Generation Dialog for Layout/Books module.

Uses LLM to generate contextually appropriate text for layout blocks.
"""

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QSplitter,
    QGroupBox, QFormLayout, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut

from core.config import ConfigManager
from core.layout.models import TextBlock, DocumentSpec
from core.llm_models import get_provider_models, get_provider_prefix
from core.discord_rpc import discord_rpc, ActivityState
from gui.llm_utils import DialogStatusConsole, LiteLLMHandler, LLMResponseParser

logger = logging.getLogger(__name__)
console_logger = logging.getLogger("console")


class TextGenerationWorker(QThread):
    """Worker thread for LLM text generation."""

    finished = Signal(str)  # Generated text
    error = Signal(str)  # Error message
    progress = Signal(str)  # Progress updates

    def __init__(self, config: ConfigManager, block_context: Dict[str, Any],
                 custom_prompt: Optional[str] = None, temperature: float = 0.7,
                 provider: Optional[str] = None, model: Optional[str] = None):
        super().__init__()
        self.config = config
        self.block_context = block_context
        self.custom_prompt = custom_prompt
        self.temperature = temperature
        self.provider = provider
        self.model = model
        self.litellm = None

    def run(self):
        """Generate text using LLM."""
        try:
            # Set up LiteLLM
            self.progress.emit("Setting up LiteLLM...")
            success, litellm = LiteLLMHandler.setup_litellm(enable_console_logging=True)
            if not success:
                self.error.emit("Failed to initialize LiteLLM")
                return
            self.litellm = litellm

            # Get LLM provider and API key
            # Use passed provider or fallback to config
            provider = self.provider or self.config.get_layout_llm_provider() or "google"

            # Map display name to provider ID (for llm_models.py compatibility and API key lookup)
            provider_map = {
                "google": "google",
                "anthropic": "anthropic",
                "openai": "openai",
                "ollama": "ollama",
                "lm studio": "lmstudio"
            }
            provider_id_for_api = provider_map.get(provider.lower(), provider.lower())

            # Map provider to llm_models.py provider ID (google -> gemini)
            provider_id = "gemini" if provider_id_for_api == "google" else provider_id_for_api

            # Check authentication mode (for Google Cloud auth support)
            auth_mode = "api-key"  # Default
            if provider_id_for_api == "google":
                auth_mode = self.config.get("auth_mode", "api-key")
                # Normalize auth mode values
                if auth_mode in ["api_key", "API Key"]:
                    auth_mode = "api-key"
                elif auth_mode == "Google Cloud Account":
                    auth_mode = "gcloud"

            # Get API key (only required for api-key mode)
            api_key = None
            if auth_mode == "api-key":
                api_key = self.config.get_api_key(provider_id_for_api)
                if not api_key:
                    self.error.emit(f"No API key configured for provider: {provider}")
                    return
                self.progress.emit(f"Using LLM provider: {provider} (API key)")
            else:
                # Using Google Cloud auth - no API key needed
                self.progress.emit(f"Using LLM provider: {provider} (Google Cloud auth)")
                logger.info("Using Google Cloud authentication (ADC)")
                console_logger.info("Using Google Cloud authentication (ADC)")

            # Build the prompt
            prompt = self._build_prompt()
            self.progress.emit(f"Generated prompt ({len(prompt)} chars)")
            console_logger.info("=" * 80)
            console_logger.info("TEXT GENERATION PROMPT:")
            console_logger.info(prompt)
            console_logger.info("=" * 80)

            # Get model - use passed model or first from provider
            if self.model:
                model_name = self.model
            else:
                # Get model list for provider and use first (most capable) model
                models = get_provider_models(provider_id)
                if not models:
                    self.error.emit(f"No models available for provider: {provider}")
                    return
                # Use first model (typically the most capable/newest)
                model_name = models[0]

            # Apply LiteLLM prefix
            prefix = get_provider_prefix(provider_id)
            model = f"{prefix}{model_name}" if prefix else model_name

            # Call LLM
            self.progress.emit(f"Calling {model}...")
            messages = [{"role": "user", "content": prompt}]

            # Handle temperature parameter compatibility
            completion_kwargs = {
                "model": model,
                "messages": messages,
                "temperature": self.temperature
            }

            # Only add API key if provided (for API key auth mode)
            # For gcloud auth, LiteLLM will use Application Default Credentials
            if api_key:
                completion_kwargs["api_key"] = api_key

            response = litellm.completion(**completion_kwargs)

            # Extract content
            if not response or not response.choices:
                self.error.emit("Empty response from LLM")
                return

            content = response.choices[0].message.content
            if not content or not content.strip():
                self.error.emit("LLM returned empty content")
                return

            console_logger.info("=" * 80)
            console_logger.info("TEXT GENERATION RESPONSE:")
            console_logger.info(content)
            console_logger.info("=" * 80)

            # Clean up the response (remove any markdown formatting)
            content = content.strip()
            if content.startswith("```") and content.endswith("```"):
                # Remove markdown code blocks
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]).strip()

            self.progress.emit(f"Generated {len(content)} characters")
            self.finished.emit(content)

        except Exception as e:
            logger.error(f"Text generation error: {e}", exc_info=True)
            console_logger.error(f"TEXT GENERATION ERROR: {e}")
            self.error.emit(str(e))

    def _build_prompt(self) -> str:
        """Build the LLM prompt based on block context."""
        # If custom prompt provided, use it directly
        if self.custom_prompt:
            return self.custom_prompt

        # Extract context
        block_id = self.block_context.get("block_id", "")
        block_type = self.block_context.get("block_type", "text")
        category = self.block_context.get("template_category", "children")
        template_name = self.block_context.get("template_name", "")
        document_title = self.block_context.get("document_title", "")
        current_text = self.block_context.get("current_text", "")
        page_number = self.block_context.get("page_number", 1)
        total_pages = self.block_context.get("total_pages", 1)

        # Build prompt based on category
        if category == "children":
            prompt = self._build_children_book_prompt(
                block_id, document_title, current_text, page_number, total_pages
            )
        elif category == "comic":
            prompt = self._build_comic_prompt(
                block_id, document_title, current_text, page_number, total_pages
            )
        elif category == "magazine":
            prompt = self._build_magazine_prompt(
                block_id, document_title, current_text, page_number, total_pages
            )
        else:
            prompt = self._build_generic_prompt(
                block_id, document_title, current_text, page_number, total_pages
            )

        return prompt

    def _build_children_book_prompt(self, block_id: str, title: str, current_text: str,
                                     page_num: int, total_pages: int) -> str:
        """Build prompt for children's book content."""
        context = f"for page {page_num} of {total_pages}" if total_pages > 1 else ""

        if "narration" in block_id.lower() or "story" in block_id.lower():
            prompt = f"""You are writing a children's picture book titled "{title or 'Untitled Book'}".

Generate engaging, age-appropriate narration {context}. The text should:
- Be simple and easy to read (ages 3-8)
- Use vivid, descriptive language
- Be 2-4 sentences long
- Tell part of the story with a clear beginning, middle, or end
- Leave room for illustration to show details
- Avoid complex words or concepts

Current text (if any): {current_text or 'None - starting fresh'}

Generate ONLY the narration text, no other commentary."""

        elif "title" in block_id.lower() or "heading" in block_id.lower():
            prompt = f"""Generate a catchy, child-friendly title for a children's picture book.

The title should:
- Be short and memorable (2-6 words)
- Use simple, fun language
- Hint at adventure, friendship, or discovery
- Be appropriate for ages 3-8

Current title (if any): {current_text or 'None'}

Generate ONLY the title, no other commentary."""

        else:
            prompt = f"""Generate short, engaging text for a children's book page.

The text should:
- Be age-appropriate (ages 3-8)
- Be 1-3 sentences
- Use simple, fun language
- Complement an illustration

Generate ONLY the text, no other commentary."""

        return prompt

    def _build_comic_prompt(self, block_id: str, title: str, current_text: str,
                           page_num: int, total_pages: int) -> str:
        """Build prompt for comic book content."""
        if "dialogue" in block_id.lower() or "speech" in block_id.lower():
            prompt = f"""You are writing dialogue for a comic book titled "{title or 'Untitled Comic'}".

Generate snappy, expressive dialogue for panel {page_num} of {total_pages}.

The dialogue should:
- Be brief and punchy (1-2 sentences max)
- Show character personality
- Advance the plot or reveal information
- Work well in a speech bubble

Current dialogue (if any): {current_text or 'None'}

Generate ONLY the dialogue text, no character names or stage directions."""

        elif "caption" in block_id.lower() or "narration" in block_id.lower():
            prompt = f"""Generate a narrative caption for a comic book panel.

The caption should:
- Set the scene or advance the story
- Be brief (1-2 sentences)
- Use evocative, dramatic language
- Complement the visual storytelling

Current caption (if any): {current_text or 'None'}

Generate ONLY the caption text, no other commentary."""

        elif "title" in block_id.lower():
            prompt = f"""Generate a dynamic, attention-grabbing comic book title.

The title should:
- Be bold and memorable
- Suggest action, adventure, or mystery
- Be 1-5 words
- Work well in large, stylized lettering

Generate ONLY the title, no other commentary."""

        else:
            prompt = f"""Generate brief text for a comic book panel.

The text should:
- Be concise (1-2 sentences max)
- Be dramatic or engaging
- Work in a comic format

Generate ONLY the text, no other commentary."""

        return prompt

    def _build_magazine_prompt(self, block_id: str, title: str, current_text: str,
                               page_num: int, total_pages: int) -> str:
        """Build prompt for magazine article content."""
        if "headline" in block_id.lower() or "title" in block_id.lower():
            prompt = f"""Generate a compelling magazine article headline.

The headline should:
- Grab attention and create curiosity
- Be clear and informative
- Be 5-12 words
- Use active voice
- Work for a general interest magazine

Article topic: {title or 'General interest'}

Generate ONLY the headline, no other commentary."""

        elif "pullquote" in block_id.lower() or "quote" in block_id.lower():
            prompt = f"""Generate an impactful pullquote for a magazine article about "{title or 'this topic'}".

The pullquote should:
- Be a complete, standalone statement
- Highlight a key insight or interesting fact
- Be 10-25 words
- Be provocative or thought-provoking
- Work well in large typography

Generate ONLY the pullquote text, no attribution or commentary."""

        elif "body" in block_id.lower() or "paragraph" in block_id.lower():
            prompt = f"""Generate engaging body text for a magazine article about "{title or 'this topic'}".

The paragraph should:
- Be informative and well-written
- Be 3-5 sentences
- Use a journalistic style
- Flow naturally
- Include specific details or examples

Current text (if any): {current_text or 'None - starting fresh'}

Generate ONLY the paragraph text, no other commentary."""

        else:
            prompt = f"""Generate professional text for a magazine layout.

The text should:
- Be clear and engaging
- Use a journalistic style
- Be appropriate for a general interest magazine
- Be 2-4 sentences

Generate ONLY the text, no other commentary."""

        return prompt

    def _build_generic_prompt(self, block_id: str, title: str, current_text: str,
                             page_num: int, total_pages: int) -> str:
        """Build generic prompt for unknown categories."""
        prompt = f"""Generate text for a layout block in a document titled "{title or 'Untitled'}".

Block ID: {block_id}
Page: {page_num} of {total_pages}
Current text: {current_text or 'None'}

Generate engaging, appropriate text for this block. The text should:
- Be clear and well-written
- Fit the context of a professional layout
- Be 2-5 sentences

Generate ONLY the text content, no other commentary."""

        return prompt


class TextGenerationDialog(QDialog):
    """Dialog for generating text content using LLM."""

    def __init__(self, config: ConfigManager, block: TextBlock,
                 document: Optional[DocumentSpec] = None,
                 template_category: str = "children",
                 template_name: str = "",
                 page_number: int = 1,
                 total_pages: int = 1,
                 provider: Optional[str] = None,
                 model: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        self.config = config
        self.block = block
        self.document = document
        self.template_category = template_category
        self.template_name = template_name
        self.page_number = page_number
        self.total_pages = total_pages
        self.provider = provider
        self.model = model
        self.generated_text = None
        self.worker: Optional[TextGenerationWorker] = None

        self.setWindowTitle("Generate Text with LLM")
        self.resize(800, 700)

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Splitter for main content and status console
        splitter = QSplitter(Qt.Vertical)

        # Top section: settings and preview
        top_widget = self._create_top_section()
        splitter.addWidget(top_widget)

        # Bottom section: status console
        self.status_console = DialogStatusConsole("Generation Status")
        splitter.addWidget(self.status_console)

        # Set splitter sizes (70% top, 30% bottom)
        splitter.setSizes([500, 200])
        layout.addWidget(splitter)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setDefault(True)
        self.generate_btn.clicked.connect(self.generate)
        button_layout.addWidget(self.generate_btn)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.apply_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+Return"), self, self.generate)
        QShortcut(QKeySequence("Escape"), self, self.reject)

    def _create_top_section(self):
        """Create the top section with settings and preview."""
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Context info
        context_group = QGroupBox("Context")
        context_layout = QFormLayout()

        doc_title = self.document.title if self.document else "Untitled"
        context_layout.addRow("Document:", QLabel(doc_title))
        context_layout.addRow("Template Category:", QLabel(self.template_category.title()))
        context_layout.addRow("Block ID:", QLabel(self.block.id))
        context_layout.addRow("Page:", QLabel(f"{self.page_number} of {self.total_pages}"))

        context_group.setLayout(context_layout)
        layout.addWidget(context_group)

        # Generation settings
        settings_group = QGroupBox("Generation Settings")
        settings_layout = QFormLayout()

        # LLM provider (info only)
        provider = self.config.get_layout_llm_provider() or "google"
        settings_layout.addRow("LLM Provider:", QLabel(provider.title()))

        # Temperature
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.setToolTip("Higher = more creative, Lower = more focused")
        settings_layout.addRow("Temperature:", self.temperature_spin)

        # Custom prompt checkbox
        self.custom_prompt_check = QCheckBox("Use custom prompt")
        self.custom_prompt_check.toggled.connect(self._on_custom_prompt_toggled)
        settings_layout.addRow("", self.custom_prompt_check)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Custom prompt (hidden by default)
        self.custom_prompt_group = QGroupBox("Custom Prompt")
        custom_layout = QVBoxLayout()

        self.custom_prompt_edit = QTextEdit()
        self.custom_prompt_edit.setPlaceholderText("Enter your custom prompt here...")
        self.custom_prompt_edit.setMaximumHeight(100)
        custom_layout.addWidget(self.custom_prompt_edit)

        self.custom_prompt_group.setLayout(custom_layout)
        self.custom_prompt_group.setVisible(False)
        layout.addWidget(self.custom_prompt_group)

        # Preview
        preview_group = QGroupBox("Generated Text Preview")
        preview_layout = QVBoxLayout()

        self.preview_edit = QTextEdit()
        self.preview_edit.setPlaceholderText("Generated text will appear here...")
        self.preview_edit.setMinimumHeight(150)
        preview_layout.addWidget(self.preview_edit)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        return widget

    def _on_custom_prompt_toggled(self, checked: bool):
        """Handle custom prompt checkbox toggle."""
        self.custom_prompt_group.setVisible(checked)

    def load_settings(self):
        """Load settings from config."""
        # Temperature
        # Could add config storage for last-used temperature
        pass

    def save_settings(self):
        """Save settings to config."""
        # Could save temperature preference
        pass

    def generate(self):
        """Start text generation."""
        if self.worker and self.worker.isRunning():
            self.status_console.log("Generation already in progress...", "WARNING")
            return

        # Clear previous results
        self.preview_edit.clear()
        self.apply_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.status_console.clear()

        # Build block context
        block_context = {
            "block_id": self.block.id,
            "block_type": "text",
            "template_category": self.template_category,
            "template_name": self.template_name,
            "document_title": self.document.title if self.document else "",
            "current_text": self.block.text,
            "page_number": self.page_number,
            "total_pages": self.total_pages
        }

        # Get custom prompt if enabled
        custom_prompt = None
        if self.custom_prompt_check.isChecked():
            custom_prompt = self.custom_prompt_edit.toPlainText().strip()
            if not custom_prompt:
                self.status_console.log("Custom prompt is empty", "ERROR")
                self.generate_btn.setEnabled(True)
                return

        # Create and start worker
        self.status_console.log("Starting text generation...", "INFO")
        self.worker = TextGenerationWorker(
            self.config,
            block_context,
            custom_prompt,
            self.temperature_spin.value(),
            self.provider,
            self.model
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, message: str):
        """Handle progress updates."""
        self.status_console.log(message, "INFO")

    def _on_finished(self, text: str):
        """Handle generation completion."""
        self.status_console.log("Text generation complete!", "SUCCESS")
        self.status_console.separator()

        self.generated_text = text
        self.preview_edit.setPlainText(text)
        self.apply_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)

    def _on_error(self, error: str):
        """Handle generation error."""
        self.status_console.log(f"Error: {error}", "ERROR")
        self.generate_btn.setEnabled(True)

    def get_generated_text(self) -> Optional[str]:
        """Get the generated text (after dialog is accepted)."""
        # Return edited text from preview
        text = self.preview_edit.toPlainText().strip()
        return text if text else None

    def showEvent(self, event):
        """Handle show event - update Discord presence."""
        super().showEvent(event)
        discord_rpc.update_presence(
            ActivityState.CHATTING_WITH_AI,
            details="Generate Text"
        )

    def closeEvent(self, event):
        """Handle close event - ensure worker thread is stopped."""
        # Reset Discord presence to IDLE
        discord_rpc.update_presence(ActivityState.IDLE)

        if self.worker and self.worker.isRunning():
            # Disconnect signals to prevent crashes during cleanup
            try:
                self.worker.progress.disconnect()
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except:
                pass  # Signals may already be disconnected

            # Try to quit the thread gracefully
            self.worker.quit()

            # Wait up to 2 seconds for thread to finish
            if not self.worker.wait(2000):
                logger.warning("Worker thread did not finish in time, forcing termination")
                console_logger.warning("Worker thread did not finish in time")
                # Thread is still running, but we've disconnected signals
                # QThread's destructor will wait for it

        super().closeEvent(event)
