"""Reference image description dialog using LLM vision capabilities.

Supports analyzing multiple files including:
- Images (PNG, JPG, JPEG, GIF, BMP, WebP, etc.)
- Text files (TXT, MD, JSON, XML, YAML, etc.)
- Code files (PY, JS, TS, HTML, CSS, etc.)
- Documents (PDF - text extraction)
"""

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Optional, List
from io import BytesIO

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QGroupBox, QDialogButtonBox,
    QMessageBox, QSplitter, QWidget, QFileDialog,
    QScrollArea, QSizePolicy, QDoubleSpinBox, QSpinBox,
    QCheckBox, QTabWidget
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QSettings, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut

from .llm_utils import DialogStatusConsole
from .history_widget import DialogHistoryWidget
from .dialog_utils import OperationGuardMixin, guard_operation
from .file_attachment_widget import FileAttachmentWidget, AttachmentItem

logger = logging.getLogger(__name__)
console = logging.getLogger("console")

# Anthropic limits - max ~1.15 megapixels per image, max request size ~25MB
ANTHROPIC_MAX_PIXELS = 1_150_000  # ~1092x1092 square or equivalent
ANTHROPIC_MAX_DIMENSION = 1568  # Max single dimension recommended by Anthropic
ANTHROPIC_JPEG_QUALITY = 85  # Quality for JPEG compression


def resize_image_for_anthropic(raw_bytes: bytes, max_pixels: int = ANTHROPIC_MAX_PIXELS,
                                max_dimension: int = ANTHROPIC_MAX_DIMENSION) -> tuple[bytes, str]:
    """
    Resize and compress an image to fit within Anthropic's limits.

    Args:
        raw_bytes: Original image bytes
        max_pixels: Maximum total pixels (width * height)
        max_dimension: Maximum single dimension

    Returns:
        Tuple of (compressed_bytes, mime_type)
    """
    from PIL import Image
    import io

    # Open image
    img = Image.open(io.BytesIO(raw_bytes))
    original_size = img.size
    original_pixels = original_size[0] * original_size[1]

    # Convert to RGB if needed (for JPEG output)
    if img.mode in ('RGBA', 'P', 'LA'):
        # Create white background for transparent images
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        if img.mode in ('RGBA', 'LA'):
            background.paste(img, mask=img.split()[-1])  # Use alpha as mask
            img = background
        else:
            img = img.convert('RGB')
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Check if resizing is needed
    needs_resize = False
    new_width, new_height = original_size

    # Check max dimension
    if max(original_size) > max_dimension:
        needs_resize = True
        if original_size[0] > original_size[1]:
            new_width = max_dimension
            new_height = int(original_size[1] * max_dimension / original_size[0])
        else:
            new_height = max_dimension
            new_width = int(original_size[0] * max_dimension / original_size[1])

    # Check total pixels (after dimension resize if applied)
    current_pixels = new_width * new_height
    if current_pixels > max_pixels:
        needs_resize = True
        scale = (max_pixels / current_pixels) ** 0.5
        new_width = int(new_width * scale)
        new_height = int(new_height * scale)

    # Apply resize if needed
    if needs_resize:
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        logger.info(f"Resized image from {original_size} to ({new_width}, {new_height}) for Anthropic")

    # Compress as JPEG
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=ANTHROPIC_JPEG_QUALITY, optimize=True)
    compressed_bytes = output.getvalue()

    original_kb = len(raw_bytes) / 1024
    compressed_kb = len(compressed_bytes) / 1024
    logger.info(f"Compressed image: {original_kb:.1f}KB → {compressed_kb:.1f}KB ({compressed_kb/original_kb*100:.0f}%)")

    return compressed_bytes, 'image/jpeg'


def get_image_mime_type(image_path: str) -> str:
    """
    Detect the MIME type of an image file.

    Args:
        image_path: Path to the image file

    Returns:
        MIME type string (e.g., 'image/png', 'image/jpeg')
    """
    # Initialize mimetypes if needed
    if not mimetypes.inited:
        mimetypes.init()

    # Get MIME type from file extension
    mime_type, _ = mimetypes.guess_type(image_path)

    # If detection failed, try to detect from file extension manually
    if not mime_type:
        ext = Path(image_path).suffix.lower()
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
        mime_type = mime_map.get(ext, 'image/jpeg')  # Default to jpeg if unknown

    return mime_type


class ImageAnalysisWorker(QObject):
    """Worker for LLM image/file analysis operations."""
    finished = Signal(str)  # Description text
    error = Signal(str)
    progress = Signal(str)
    log_message = Signal(str, str)  # Message, level (INFO/WARNING/ERROR)

    def __init__(self, attachments: List[AttachmentItem], llm_provider: str, llm_model: str, api_key: str,
                 analysis_prompt: str = None, temperature: float = 0.7,
                 max_tokens: int = 1000, reasoning_effort: str = "medium",
                 verbosity: str = "medium", auth_mode: str = "api-key",
                 image_path: str = None):  # Legacy single image support
        super().__init__()
        self.attachments = attachments
        self.image_path = image_path  # Legacy - for backward compatibility
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.api_key = api_key
        self.analysis_prompt = analysis_prompt or "Describe this image in detail for AI image generation."
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self.auth_mode = auth_mode
        self._stopped = False

    def stop(self):
        """Stop the worker."""
        self._stopped = True

    def _analyze_with_google_gemini(self, temperature: float, max_tokens: int, auth_mode: str = "api-key") -> str:
        """
        Analyze files using Google Gemini API.

        Args:
            temperature: Temperature parameter
            max_tokens: Maximum tokens to generate
            auth_mode: Authentication mode ("api-key" or "gcloud")

        Returns:
            Generated description text
        """
        try:
            import google.genai as genai
            from google.genai import types

            # Create client based on auth mode
            if auth_mode == "gcloud":
                # Use Google Cloud authentication (Vertex AI mode)
                from google.auth import default as google_auth_default

                # Get Application Default Credentials
                credentials, project = google_auth_default()
                if not project:
                    # Try to get from gcloud config
                    import subprocess
                    result = subprocess.run(
                        ["gcloud", "config", "get-value", "project"],
                        capture_output=True, text=True, timeout=5
                    )
                    project = result.stdout.strip()

                if not project:
                    raise ValueError(
                        "No Google Cloud project found. "
                        "Set a project with: gcloud config set project YOUR_PROJECT_ID"
                    )

                self.log_message.emit(f"Using Google Cloud project: {project}", "INFO")

                # Create client in Vertex AI mode
                client = genai.Client(
                    vertexai=True,
                    project=project,
                    location="us-central1"
                )
            else:
                # Use API key authentication
                client = genai.Client(api_key=self.api_key)

            # Create the system prompt
            system_prompt = """You are an expert at analyzing images and files, creating detailed descriptions
            that can be used as prompts for AI image generation systems. Provide clear, detailed descriptions
            focusing on visual elements, style, composition, colors, lighting, and mood."""

            # Combine with user's analysis prompt
            full_prompt = f"{system_prompt}\n\n{self.analysis_prompt}"

            self.log_message.emit("Sending request to Google Gemini...", "INFO")

            # Build contents list with all attachments
            from PIL import Image
            import io

            contents = []

            for attachment in self.attachments:
                if not attachment.load_content():
                    self.log_message.emit(f"Warning: Failed to load {attachment.name}", "WARNING")
                    continue

                if attachment.category == 'image':
                    # Convert image bytes to PIL Image
                    if attachment.raw_bytes:
                        img = Image.open(io.BytesIO(attachment.raw_bytes))
                        contents.append(img)
                        self.log_message.emit(f"Added image: {attachment.name}", "INFO")

                elif attachment.category in ['text', 'code', 'data']:
                    # Add text content
                    if attachment.text_content:
                        contents.append(f"[File: {attachment.name}]\n```\n{attachment.text_content}\n```")
                        self.log_message.emit(f"Added text file: {attachment.name}", "INFO")

                elif attachment.category == 'document':
                    # PDF - add extracted text
                    if attachment.text_content:
                        contents.append(f"[PDF: {attachment.name}]\n{attachment.text_content}")
                        self.log_message.emit(f"Added PDF text: {attachment.name}", "INFO")

            # Add the prompt at the end
            contents.append(full_prompt)

            if len(contents) <= 1:
                raise ValueError("No valid content to analyze")

            # Generate with vision model
            response = client.models.generate_content(
                model=self.llm_model,  # e.g., 'gemini-2.5-pro'
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            )

            # Extract text from response
            if response and response.text:
                return response.text.strip()
            else:
                raise ValueError("Empty response from Google Gemini")

        except Exception as e:
            error_msg = f"Google Gemini analysis failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def run(self):
        """Run the file analysis operation."""
        try:
            file_count = len(self.attachments)
            self.progress.emit(f"Analyzing {file_count} file(s)...")
            self.log_message.emit(f"Starting analysis of {file_count} file(s)...", "INFO")

            # Log request details
            logger.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            console.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            self.log_message.emit(f"Provider: {self.llm_provider}, Model: {self.llm_model}", "INFO")

            # Log attached files
            for att in self.attachments:
                logger.info(f"LLM Request - File: {att.name} ({att.category})")
                console.info(f"LLM Request - File: {att.name} ({att.category})")
                self.log_message.emit(f"File: {att.icon} {att.name}", "INFO")

            logger.info(f"LLM Request - Analysis prompt: {self.analysis_prompt}")
            console.info(f"LLM Request - Analysis prompt: {self.analysis_prompt}")
            self.log_message.emit(f"Prompt: {self.analysis_prompt[:100]}...", "INFO")

            # Import required modules
            from core.video.prompt_engine import UnifiedLLMProvider

            # Create API config
            api_config = {}
            provider_lower = self.llm_provider.lower()

            if provider_lower == "openai":
                api_config['openai_api_key'] = self.api_key
            elif provider_lower in ["google", "gemini"]:
                api_config['google_api_key'] = self.api_key
            elif provider_lower in ["claude", "anthropic"]:
                api_config['anthropic_api_key'] = self.api_key

            # Determine temperature and max_tokens based on model
            is_gpt5 = "gpt-5" in self.llm_model.lower()
            if is_gpt5:
                temperature = 1.0
                max_tokens = 1000
            else:
                temperature = self.temperature
                max_tokens = self.max_tokens

            # Log parameters
            logger.info(f"  Temperature: {temperature}")
            console.info(f"  Temperature: {temperature}")
            self.log_message.emit(f"Temperature: {temperature}", "INFO")

            logger.info(f"  Max tokens: {max_tokens}")
            console.info(f"  Max tokens: {max_tokens}")
            self.log_message.emit(f"Max tokens: {max_tokens}", "INFO")

            # For Google Gemini, use direct API or Vertex AI based on auth mode
            if provider_lower in ["google", "gemini"]:
                description = self._analyze_with_google_gemini(
                    temperature, max_tokens, self.auth_mode
                )
                if self._stopped:
                    return

                # Log response (FULL)
                logger.info(f"LLM Response - Description (FULL, {len(description)} chars):")
                logger.info(description)
                console.info(f"LLM Response - Description (FULL, {len(description)} chars):")
                console.info(description)
                self.log_message.emit("Description generated successfully", "INFO")

                self.finished.emit(description)
                return

            # Create LLM provider for OpenAI and Anthropic
            llm = UnifiedLLMProvider(api_config)

            # Log parameters based on model
            if is_gpt5:
                logger.info(f"  Reasoning effort: {self.reasoning_effort}")
                console.info(f"  Reasoning effort: {self.reasoning_effort}")
                self.log_message.emit(f"Reasoning effort: {self.reasoning_effort}", "INFO")

                logger.info(f"  Verbosity: {self.verbosity}")
                console.info(f"  Verbosity: {self.verbosity}")
                self.log_message.emit(f"Verbosity: {self.verbosity}", "INFO")

            # Create the system prompt
            system_prompt = """You are an expert at analyzing images and files, creating detailed descriptions
            that can be used as prompts for AI image generation systems. Provide clear, detailed descriptions
            focusing on visual elements, style, composition, colors, lighting, and mood."""

            # Combine with user's analysis prompt
            full_prompt = f"{system_prompt}\n\n{self.analysis_prompt}"

            # Build message content with all attachments
            content_parts = [{"type": "text", "text": full_prompt}]

            # Check if using Anthropic (needs image resizing)
            is_anthropic = provider_lower in ["claude", "anthropic"]

            for attachment in self.attachments:
                if not attachment.load_content():
                    self.log_message.emit(f"Warning: Failed to load {attachment.name}", "WARNING")
                    continue

                if attachment.category == 'image':
                    # Image as base64 data URL
                    if attachment.raw_bytes:
                        # Resize images for Anthropic to avoid request_too_large error
                        if is_anthropic:
                            try:
                                resized_bytes, mime_type = resize_image_for_anthropic(attachment.raw_bytes)
                                base64_data = base64.b64encode(resized_bytes).decode('utf-8')
                                self.log_message.emit(f"Resized image for Anthropic: {attachment.name}", "INFO")
                            except Exception as e:
                                self.log_message.emit(f"Warning: Failed to resize {attachment.name}: {e}", "WARNING")
                                base64_data = attachment.base64_data
                                mime_type = attachment.mime_type
                        else:
                            base64_data = attachment.base64_data
                            mime_type = attachment.mime_type

                        content_parts.append({
                            'type': 'image_url',
                            'image_url': {
                                'url': f"data:{mime_type};base64,{base64_data}"
                            }
                        })
                        self.log_message.emit(f"Added image: {attachment.name}", "INFO")

                elif attachment.category in ['text', 'code', 'data']:
                    # Text content
                    if attachment.text_content:
                        content_parts.append({
                            'type': 'text',
                            'text': f"[File: {attachment.name}]\n```\n{attachment.text_content}\n```"
                        })
                        self.log_message.emit(f"Added text file: {attachment.name}", "INFO")

                elif attachment.category == 'document':
                    # PDF - include extracted text
                    if attachment.text_content:
                        content_parts.append({
                            'type': 'text',
                            'text': f"[PDF: {attachment.name}]\n{attachment.text_content}"
                        })
                        self.log_message.emit(f"Added PDF text: {attachment.name}", "INFO")

            # Prepare messages
            messages = [{"role": "user", "content": content_parts}]

            if self._stopped:
                return

            # Log the request
            self.log_message.emit("Sending request to LLM...", "INFO")
            self.progress.emit("Waiting for LLM response...")

            # Generate description using appropriate parameters
            if is_gpt5:
                # GPT-5 has fixed parameters (temperature=1.0)
                description = llm.generate(
                    messages,
                    model=self.llm_model,
                    temperature=1.0,  # GPT-5 requires temperature=1
                    max_tokens=1000,  # Fixed for GPT-5
                    response_format={"type": "text"}
                )
            else:
                description = llm.generate(
                    messages,
                    model=self.llm_model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

            if self._stopped:
                return

            # Log response
            logger.info(f"LLM Response - Description (FULL, {len(description)} chars):")
            logger.info(description)
            console.info(f"LLM Response - Description (FULL, {len(description)} chars):")
            console.info(description)
            self.log_message.emit("Description generated successfully", "INFO")

            self.finished.emit(description)

        except Exception as e:
            error_msg = f"File analysis failed: {str(e)}"
            logger.error(error_msg)
            console.error(error_msg)
            self.log_message.emit(error_msg, "ERROR")
            self.error.emit(error_msg)


class ReferenceImageDialog(QDialog, OperationGuardMixin):
    """Dialog for analyzing files (images, text, code, PDFs) with LLM."""

    descriptionGenerated = Signal(str)

    def __init__(self, parent=None, config=None, image_path=None):
        super().__init__(parent)
        self.config = config
        self.image_path = image_path  # Legacy - for backward compatibility
        self.worker = None
        self.thread = None
        self.generated_description = None
        self.settings = QSettings("ImageAI", "ReferenceImageDialog")

        self.setWindowTitle("Ask About Files with AI")
        self.setMinimumWidth(800)
        self.setMinimumHeight(650)

        # Restore window geometry
        self.restore_settings()

        self.init_ui()

        # Initialize operation guard AFTER UI is created (needs status_console)
        self.init_operation_guard(block_all_input=True)

        self.load_llm_settings()

        # Load image if provided (backward compatibility)
        if image_path:
            self.attachment_widget.add_file(image_path)

        # Restore dialog-specific settings
        self.restore_dialog_settings()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Create splitter for main content and status console
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Analyze tab
        analyze_widget = QWidget()
        main_layout = QVBoxLayout(analyze_widget)

        # File attachments section
        attachments_group = QGroupBox("Files to Analyze")
        attachments_layout = QVBoxLayout(attachments_group)

        # Info label
        info_label = QLabel(
            "Attach images, text files, code files, or PDFs to analyze with AI. "
            "Drag & drop or click 'Add Files'."
        )
        info_label.setStyleSheet("color: #666; font-style: italic;")
        info_label.setWordWrap(True)
        attachments_layout.addWidget(info_label)

        # File attachment widget
        self.attachment_widget = FileAttachmentWidget(self, max_files=10)
        self.attachment_widget.attachmentsChanged.connect(self.on_attachments_changed)
        attachments_layout.addWidget(self.attachment_widget)

        main_layout.addWidget(attachments_group)

        # Analysis settings
        settings_group = QGroupBox("Analysis Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Analysis prompt
        prompt_layout = QVBoxLayout()
        prompt_layout.addWidget(QLabel("Analysis Prompt:"))

        self.analysis_prompt = QTextEdit()
        self.analysis_prompt.setPlaceholderText(
            "Ask a question or describe what you want to know about the attached files...\n"
            "Examples: 'Describe this image for AI generation', 'Summarize this code', 'What does this document say?'"
        )
        self.analysis_prompt.setMaximumHeight(80)
        prompt_layout.addWidget(self.analysis_prompt)

        settings_layout.addLayout(prompt_layout)

        # LLM settings
        llm_layout = QHBoxLayout()

        # Provider selection
        llm_layout.addWidget(QLabel("LLM Provider:"))
        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.currentTextChanged.connect(self.update_llm_models)
        llm_layout.addWidget(self.llm_provider_combo)

        # Model selection
        llm_layout.addWidget(QLabel("Model:"))
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.currentTextChanged.connect(self.on_model_changed)
        llm_layout.addWidget(self.llm_model_combo)

        # Temperature
        llm_layout.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.setToolTip("Controls randomness (0=deterministic, 2=very random)")
        llm_layout.addWidget(self.temperature_spin)

        # Max tokens
        llm_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 4000)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(1000)
        self.max_tokens_spin.setToolTip("Maximum length of generated description")
        llm_layout.addWidget(self.max_tokens_spin)

        llm_layout.addStretch()
        settings_layout.addLayout(llm_layout)

        # GPT-5 specific parameters (initially hidden)
        self.gpt5_params_widget = QWidget()
        gpt5_layout = QHBoxLayout(self.gpt5_params_widget)
        gpt5_layout.setContentsMargins(0, 0, 0, 0)

        gpt5_layout.addWidget(QLabel("Reasoning:"))
        self.reasoning_combo = QComboBox()
        self.reasoning_combo.addItems(["low", "medium", "high"])
        self.reasoning_combo.setCurrentText("medium")
        self.reasoning_combo.setToolTip("GPT-5 reasoning effort level")
        gpt5_layout.addWidget(self.reasoning_combo)

        gpt5_layout.addWidget(QLabel("Verbosity:"))
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItems(["low", "medium", "high"])
        self.verbosity_combo.setCurrentText("medium")
        self.verbosity_combo.setToolTip("GPT-5 response detail level")
        gpt5_layout.addWidget(self.verbosity_combo)

        gpt5_layout.addStretch()
        settings_layout.addWidget(self.gpt5_params_widget)

        # Initially hide GPT-5 params
        self.gpt5_params_widget.hide()

        main_layout.addWidget(settings_group)

        # Result section
        result_group = QGroupBox("AI Response")
        result_layout = QVBoxLayout(result_group)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Response will appear here after analysis...")
        result_layout.addWidget(self.result_text)

        # Copy to prompt checkbox
        controls_layout = QHBoxLayout()
        self.copy_to_prompt_checkbox = QCheckBox("Copy to main prompt when done")
        self.copy_to_prompt_checkbox.setChecked(True)
        controls_layout.addWidget(self.copy_to_prompt_checkbox)
        controls_layout.addStretch()
        result_layout.addLayout(controls_layout)

        main_layout.addWidget(result_group)

        # Analyze button
        self.analyze_btn = QPushButton("Analyze Files")
        self.analyze_btn.setToolTip("Analyze attached files with AI (Ctrl+Enter)")
        self.analyze_btn.setDefault(True)
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
            }
        """)
        self.analyze_btn.clicked.connect(self.analyze_files)
        self.analyze_btn.setEnabled(False)  # Disabled until files are attached
        main_layout.addWidget(self.analyze_btn)

        # Add shortcut hint label
        shortcut_label = QLabel("<small style='color: gray;'>Shortcuts: Ctrl+Enter to analyze, Drag & drop files, Esc to close</small>")
        shortcut_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(shortcut_label)

        # Add Analyze tab
        self.tab_widget.addTab(analyze_widget, "Analyze")

        # History tab
        self.history_widget = DialogHistoryWidget("reference_images", self)
        self.history_widget.itemDoubleClicked.connect(self.load_history_item)
        self.tab_widget.addTab(self.history_widget, "History")

        # Add tabs to splitter
        splitter.addWidget(self.tab_widget)

        # Status console at bottom
        self.status_console = DialogStatusConsole()
        self.status_console.setMaximumHeight(150)
        splitter.addWidget(self.status_console)

        # Set initial splitter sizes (80% main, 20% console)
        splitter.setSizes([400, 100])

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Set up keyboard shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+Enter to analyze
        analyze_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        analyze_shortcut.activated.connect(lambda: self.analyze_files() if self.analyze_btn.isEnabled() else None)

        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.reject)

    def on_attachments_changed(self):
        """Handle changes to the attachments list."""
        has_attachments = self.attachment_widget.has_attachments()
        self.analyze_btn.setEnabled(has_attachments)

        if has_attachments:
            count = self.attachment_widget.get_attachment_count()
            self.status_console.log(f"Attachments updated: {count} file(s)", "INFO")

    def load_llm_settings(self):
        """Load LLM settings from config."""
        # Load available providers (doesn't need config)
        from gui.main_window import MainWindow

        providers = MainWindow.get_llm_providers()

        # Filter out "None" as it's not valid for image analysis
        providers = [p for p in providers if p != "None"]

        self.llm_provider_combo.clear()
        self.llm_provider_combo.addItems(providers)

        # Try to restore saved settings if config is available
        if self.config:
            # Set saved provider if available
            saved_provider = self.config.get('llm_provider', '')
            if saved_provider and saved_provider != "None":
                index = self.llm_provider_combo.findText(saved_provider)
                if index >= 0:
                    self.llm_provider_combo.setCurrentIndex(index)
                else:
                    # Saved provider not found, use first available
                    if self.llm_provider_combo.count() > 0:
                        self.llm_provider_combo.setCurrentIndex(0)
            else:
                # No saved provider, use first available
                if self.llm_provider_combo.count() > 0:
                    self.llm_provider_combo.setCurrentIndex(0)
        else:
            # No config, use first available
            if self.llm_provider_combo.count() > 0:
                self.llm_provider_combo.setCurrentIndex(0)

        # Update models for the selected provider
        self.update_llm_models()

        # Set model if saved and config available
        if self.config:
            saved_model = self.config.get('llm_model', '')
            if saved_model:
                index = self.llm_model_combo.findText(saved_model)
                if index >= 0:
                    self.llm_model_combo.setCurrentIndex(index)

    def update_llm_models(self):
        """Update available models based on selected provider."""
        from gui.main_window import MainWindow

        provider = self.llm_provider_combo.currentText()
        if not provider:
            return

        # Get models for this provider
        models = MainWindow.get_llm_models_for_provider(provider)

        self.llm_model_combo.clear()
        self.llm_model_combo.addItems(models)

        # Select default model if available (first in list)
        if models:
            self.llm_model_combo.setCurrentIndex(0)

    def on_model_changed(self):
        """Handle model selection change."""
        model = self.llm_model_combo.currentText()

        # Show/hide GPT-5 specific parameters
        is_gpt5 = "gpt-5" in model.lower()

        if is_gpt5:
            self.gpt5_params_widget.show()
            self.temperature_spin.setEnabled(False)
            self.temperature_spin.setValue(1.0)
            self.temperature_spin.setToolTip("GPT-5 only supports temperature=1")
            self.max_tokens_spin.setEnabled(False)
            self.max_tokens_spin.setToolTip("GPT-5 has fixed token limits")
        else:
            self.gpt5_params_widget.hide()
            self.temperature_spin.setEnabled(True)
            self.temperature_spin.setToolTip("Controls randomness (0=deterministic, 2=very random)")
            self.max_tokens_spin.setEnabled(True)
            self.max_tokens_spin.setToolTip("Maximum length of generated description")

    @guard_operation("File Analysis")
    def analyze_files(self):
        """Analyze attached files with LLM."""
        if not self.attachment_widget.has_attachments():
            QMessageBox.warning(self, "No Files", "Please attach at least one file to analyze.")
            return

        # Get LLM settings
        llm_provider = self.llm_provider_combo.currentText()
        llm_model = self.llm_model_combo.currentText()

        if not llm_provider or not llm_model:
            QMessageBox.warning(self, "LLM Not Configured",
                                 "Please select an LLM provider and model.")
            return

        # Check authentication mode (for Google Cloud auth support)
        auth_mode = "api-key"  # Default
        if self.config and llm_provider.lower() in ["google", "gemini"]:
            auth_mode = self.config.get("auth_mode", "api-key")
            # Normalize auth mode values
            if auth_mode in ["api_key", "API Key"]:
                auth_mode = "api-key"
            elif auth_mode == "Google Cloud Account":
                auth_mode = "gcloud"

        # Get API key (only required for api-key mode)
        api_key = None
        if auth_mode == "api-key":
            if self.config:
                if llm_provider.lower() == "openai":
                    api_key = self.config.get_api_key('openai')
                elif llm_provider.lower() in ["google", "gemini"]:
                    api_key = self.config.get_api_key('google')
                elif llm_provider.lower() in ["claude", "anthropic"]:
                    api_key = self.config.get_api_key('anthropic')

            if not api_key:
                QMessageBox.warning(self, "API Key Missing",
                                     f"Please configure your {llm_provider} API key in Settings.")
                return
        else:
            # Using Google Cloud auth - no API key needed
            self.status_console.log("Using Google Cloud authentication", "INFO")

        # Get analysis prompt
        analysis_prompt = self.analysis_prompt.toPlainText().strip()
        if not analysis_prompt:
            analysis_prompt = "Analyze the attached files and provide a detailed description."

        # Save settings before analysis
        self.save_dialog_settings()

        # Disable UI during analysis
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing...")

        # Clear previous results
        self.result_text.clear()

        # Get attachments
        attachments = self.attachment_widget.get_attachments()
        file_count = len(attachments)

        # Log to status console
        self.status_console.clear()
        self.status_console.log(f"Analyzing {file_count} file(s) with {llm_provider} {llm_model}...", "INFO")

        # Mark operation as started (enables input blocking)
        self.start_operation("File Analysis")

        # Get GPT-5 specific params if applicable
        is_gpt5 = self.gpt5_params_widget.isVisible()
        if is_gpt5:
            reasoning = self.reasoning_combo.currentText()
            verbosity = self.verbosity_combo.currentText()
            temperature = 1.0  # GPT-5 only supports temperature=1
            max_tokens = 1000  # Default for GPT-5
        else:
            reasoning = "medium"
            verbosity = "medium"
            temperature = self.temperature_spin.value()
            max_tokens = self.max_tokens_spin.value()

        # Create worker thread
        self.thread = QThread()
        self.worker = ImageAnalysisWorker(
            attachments=attachments,
            llm_provider=llm_provider,
            llm_model=llm_model,
            api_key=api_key,
            analysis_prompt=analysis_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning,
            verbosity=verbosity,
            auth_mode=auth_mode
        )

        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_analysis_complete)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.progress.connect(lambda msg: self.status_console.log(msg, "INFO"))
        self.worker.log_message.connect(self.status_console.log)

        # Proper cleanup sequence
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        # Clean up references after thread is truly done
        self.thread.finished.connect(lambda: self.cleanup_thread())

        # Start the thread
        self.thread.start()

    def cleanup_thread(self):
        """Clean up thread references after thread has fully stopped."""
        self.worker = None
        self.thread = None

    def on_analysis_complete(self, description: str):
        """Handle successful analysis."""
        self.generated_description = description
        self.result_text.setPlainText(description)
        self.status_console.log("Analysis complete!", "SUCCESS")

        # Re-enable UI
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Files")

        # End operation (disables input blocking)
        self.end_operation()

    def on_analysis_error(self, error: str):
        """Handle analysis error."""
        QMessageBox.critical(self, "Analysis Error", error)
        self.status_console.log(f"Error: {error}", "ERROR")

        # Re-enable UI
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Files")

        # End operation (disables input blocking)
        self.end_operation()

    def accept(self):
        """Override accept to emit description if requested."""
        if self.generated_description:
            # Build file list for metadata (include paths for restore)
            attachments = self.attachment_widget.get_attachments()
            file_names = [a.name for a in attachments]
            file_paths = [a.path for a in attachments]

            # Save to history
            self.history_widget.add_entry(
                self.analysis_prompt.toPlainText() if hasattr(self, 'analysis_prompt') else "File analysis",
                self.generated_description,
                self.llm_provider_combo.currentText() if hasattr(self, 'llm_provider_combo') else "",
                self.llm_model_combo.currentText() if hasattr(self, 'llm_model_combo') else "",
                {
                    "files": file_names,
                    "file_paths": file_paths,  # Store full paths for restore
                    "file_count": len(file_names)
                }
            )

            if self.copy_to_prompt_checkbox.isChecked():
                self.descriptionGenerated.emit(self.generated_description)

        self.save_dialog_settings()
        self.save_settings()
        super().accept()

    def reject(self):
        """Override reject to save settings before closing."""
        self.save_dialog_settings()
        self.save_settings()
        super().reject()

    def save_settings(self):
        """Save window geometry and splitter state."""
        self.settings.setValue("geometry", self.saveGeometry())
        # Find and save splitter state
        splitters = self.findChildren(QSplitter)
        if splitters:
            self.settings.setValue("splitter_state", splitters[0].saveState())

    def restore_settings(self):
        """Restore window geometry."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def save_dialog_settings(self):
        """Save dialog-specific settings."""
        # Save analysis prompt
        self.settings.setValue("analysis_prompt", self.analysis_prompt.toPlainText())

        # Save temperature and max tokens
        self.settings.setValue("temperature", self.temperature_spin.value())
        self.settings.setValue("max_tokens", self.max_tokens_spin.value())

        # Save copy to prompt checkbox
        self.settings.setValue("copy_to_prompt", self.copy_to_prompt_checkbox.isChecked())

        # Save LLM settings to config if available
        if self.config:
            self.config.set('llm_provider', self.llm_provider_combo.currentText())
            self.config.set('llm_model', self.llm_model_combo.currentText())

        # Save GPT-5 specific settings
        self.settings.setValue("reasoning_effort", self.reasoning_combo.currentText())
        self.settings.setValue("verbosity", self.verbosity_combo.currentText())

        # Save attached file paths for session persistence
        attachments = self.attachment_widget.get_attachments()
        file_paths = [a.path for a in attachments]
        self.settings.setValue("last_file_paths", file_paths)

    def restore_dialog_settings(self):
        """Restore dialog-specific settings."""
        # Restore analysis prompt
        analysis_prompt = self.settings.value("analysis_prompt", "")
        if analysis_prompt:
            self.analysis_prompt.setPlainText(analysis_prompt)

        # Restore temperature and max tokens
        temperature = self.settings.value("temperature", type=float)
        if temperature is not None:
            self.temperature_spin.setValue(temperature)

        max_tokens = self.settings.value("max_tokens", type=int)
        if max_tokens is not None:
            self.max_tokens_spin.setValue(max_tokens)

        # Restore copy to prompt checkbox
        copy_to_prompt = self.settings.value("copy_to_prompt", type=bool)
        if copy_to_prompt is not None:
            self.copy_to_prompt_checkbox.setChecked(copy_to_prompt)

        # Restore GPT-5 specific settings
        reasoning = self.settings.value("reasoning_effort", "medium")
        index = self.reasoning_combo.findText(reasoning)
        if index >= 0:
            self.reasoning_combo.setCurrentIndex(index)

        verbosity = self.settings.value("verbosity", "medium")
        index = self.verbosity_combo.findText(verbosity)
        if index >= 0:
            self.verbosity_combo.setCurrentIndex(index)

        # Restore splitter state after UI is created
        splitters = self.findChildren(QSplitter)
        if splitters:
            splitter_state = self.settings.value("splitter_state")
            if splitter_state:
                splitters[0].restoreState(splitter_state)

        # Restore last used files (only if no image_path was provided at init)
        if not self.image_path:
            last_file_paths = self.settings.value("last_file_paths", [])
            if last_file_paths:
                for file_path in last_file_paths:
                    if Path(file_path).exists():
                        self.attachment_widget.add_file(file_path)
                if self.attachment_widget.has_attachments():
                    self.status_console.log(f"Restored {self.attachment_widget.get_attachment_count()} file(s) from last session", "INFO")

    def load_history_item(self, item):
        """Load a history item when double-clicked."""
        # Switch to main tab
        self.tab_widget.setCurrentIndex(0)

        # Restore the input
        analysis_prompt = item.get('input', '')
        if analysis_prompt:
            self.analysis_prompt.setPlainText(analysis_prompt)

        # Restore the response
        description = item.get('response', '')
        if description:
            self.generated_description = description
            self.result_text.setPlainText(description)

            # Show in status console
            self.status_console.log("="*60, "INFO")
            self.status_console.log("Restored from history:", "INFO")
            self.status_console.log(f"Analysis Prompt: {analysis_prompt}", "INFO")
            self.status_console.log("-"*40, "INFO")
            self.status_console.log(f"Generated Description:\n{description}", "SUCCESS")
            self.status_console.log("="*60, "INFO")

            # Show metadata if available
            if 'metadata' in item:
                metadata = item['metadata']
                # Try to restore files from paths
                if 'file_paths' in metadata:
                    file_paths = metadata['file_paths']
                    # Clear current attachments
                    self.attachment_widget.clear_attachments()
                    # Add files that still exist
                    restored_count = 0
                    missing_files = []
                    for file_path in file_paths:
                        if Path(file_path).exists():
                            self.attachment_widget.add_file(file_path)
                            restored_count += 1
                        else:
                            missing_files.append(Path(file_path).name)
                    if restored_count > 0:
                        self.status_console.log(f"Restored {restored_count} file(s)", "SUCCESS")
                    if missing_files:
                        self.status_console.log(f"Missing files: {', '.join(missing_files)}", "WARNING")
                # Handle old format (files list without paths)
                elif 'files' in metadata:
                    files = metadata['files']
                    self.status_console.log(f"Files (not restored - no paths): {', '.join(files)}", "INFO")
                # Handle old format (single image_path)
                elif 'image_path' in metadata:
                    image_path = metadata['image_path']
                    if Path(image_path).exists():
                        self.attachment_widget.clear_attachments()
                        self.attachment_widget.add_file(image_path)
                        self.status_console.log(f"Restored image: {image_path}", "SUCCESS")
                    else:
                        self.status_console.log(f"Image not found: {image_path}", "WARNING")
            if 'provider' in item and item['provider']:
                self.status_console.log(f"Provider: {item['provider']} ({item.get('model', 'Unknown')})", "INFO")



    def closeEvent(self, event):
        """Handle close event."""
        # Stop any running worker
        try:
            if self.worker:
                self.worker.stop()
            if self.thread:
                # Check if thread still exists and is running
                if hasattr(self.thread, 'isRunning') and self.thread.isRunning():
                    self.thread.quit()
                    self.thread.wait(1000)  # Wait up to 1 second
        except RuntimeError:
            # Thread might already be deleted by Qt
            pass

        # Save settings
        self.save_dialog_settings()
        self.save_settings()
        super().closeEvent(event)