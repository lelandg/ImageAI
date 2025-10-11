"""Reference image description dialog using LLM vision capabilities."""

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Optional
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

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


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
    """Worker for LLM image analysis operations."""
    finished = Signal(str)  # Description text
    error = Signal(str)
    progress = Signal(str)
    log_message = Signal(str, str)  # Message, level (INFO/WARNING/ERROR)

    def __init__(self, image_path: str, llm_provider: str, llm_model: str, api_key: str,
                 analysis_prompt: str = None, temperature: float = 0.7,
                 max_tokens: int = 1000, reasoning_effort: str = "medium",
                 verbosity: str = "medium"):
        super().__init__()
        self.image_path = image_path
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.api_key = api_key
        self.analysis_prompt = analysis_prompt or "Describe this image in detail for AI image generation."
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self._stopped = False

    def stop(self):
        """Stop the worker."""
        self._stopped = True

    def _analyze_with_google_gemini(self, image_data: bytes, mime_type: str,
                                     temperature: float, max_tokens: int) -> str:
        """
        Analyze image using Google Gemini's direct API (not Vertex AI).

        Args:
            image_data: Raw image bytes
            mime_type: MIME type of the image
            temperature: Temperature parameter
            max_tokens: Maximum tokens to generate

        Returns:
            Generated description text
        """
        try:
            import google.genai as genai
            from google.genai import types

            # Configure with API key
            genai.configure(api_key=self.api_key)

            # Create client
            client = genai.Client()

            # Create the system prompt
            system_prompt = """You are an expert at analyzing images and creating detailed descriptions
            that can be used as prompts for AI image generation systems. Provide clear, detailed descriptions
            focusing on visual elements, style, composition, colors, lighting, and mood."""

            # Combine with user's analysis prompt
            full_prompt = f"{system_prompt}\n\n{self.analysis_prompt}"

            self.log_message.emit("Sending request to Google Gemini...", "INFO")

            # Create the content with image
            content = types.Content(
                parts=[
                    types.Part(text=full_prompt),
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=image_data
                        )
                    )
                ]
            )

            # Generate with vision model
            response = client.models.generate_content(
                model=self.llm_model,  # e.g., 'gemini-2.5-pro'
                contents=content,
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
        """Run the image analysis operation."""
        try:
            self.progress.emit("Analyzing image...")
            self.log_message.emit("Starting image analysis...", "INFO")

            # Log request details
            logger.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            console.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            self.log_message.emit(f"Provider: {self.llm_provider}, Model: {self.llm_model}", "INFO")

            logger.info(f"LLM Request - Image path: {self.image_path}")
            console.info(f"LLM Request - Image path: {self.image_path}")
            self.log_message.emit(f"Image: {Path(self.image_path).name}", "INFO")

            logger.info(f"LLM Request - Analysis prompt: {self.analysis_prompt}")
            console.info(f"LLM Request - Analysis prompt: {self.analysis_prompt}")
            self.log_message.emit(f"Prompt: {self.analysis_prompt[:100]}...", "INFO")

            # Read and encode image
            image_path = Path(self.image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {self.image_path}")

            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Encode to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Detect the correct MIME type
            mime_type = get_image_mime_type(str(image_path))
            self.log_message.emit(f"Image MIME type: {mime_type}", "INFO")

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

            # For Google Gemini, use direct API to avoid Vertex AI
            if provider_lower in ["google", "gemini"]:
                description = self._analyze_with_google_gemini(
                    image_data, mime_type, temperature, max_tokens
                )
                if self._stopped:
                    return

                # Log response
                logger.info(f"LLM Response - Description: {description[:200]}...")
                console.info(f"LLM Response - Description: {description[:200]}...")
                self.log_message.emit("Description generated successfully", "INFO")

                self.finished.emit(description)
                return

            # Create LLM provider for OpenAI and Anthropic
            llm = UnifiedLLMProvider(api_config)

            # Log parameters based on model
            is_gpt5 = "gpt-5" in self.llm_model.lower()
            if is_gpt5:
                logger.info(f"  Reasoning effort: {self.reasoning_effort}")
                console.info(f"  Reasoning effort: {self.reasoning_effort}")
                self.log_message.emit(f"Reasoning effort: {self.reasoning_effort}", "INFO")

                logger.info(f"  Verbosity: {self.verbosity}")
                console.info(f"  Verbosity: {self.verbosity}")
                self.log_message.emit(f"Verbosity: {self.verbosity}", "INFO")

                # GPT-5 has fixed parameters
                temperature = 1.0
                max_tokens = 1000
            else:
                logger.info(f"  Temperature: {self.temperature}")
                console.info(f"  Temperature: {self.temperature}")
                self.log_message.emit(f"Temperature: {self.temperature}", "INFO")

                logger.info(f"  Max tokens: {self.max_tokens}")
                console.info(f"  Max tokens: {self.max_tokens}")
                self.log_message.emit(f"Max tokens: {self.max_tokens}", "INFO")

                temperature = self.temperature
                max_tokens = self.max_tokens

            # Create the system prompt
            system_prompt = """You are an expert at analyzing images and creating detailed descriptions
            that can be used as prompts for AI image generation systems. Provide clear, detailed descriptions
            focusing on visual elements, style, composition, colors, lighting, and mood."""

            # Combine with user's analysis prompt
            full_prompt = f"{system_prompt}\n\n{self.analysis_prompt}"

            # Prepare messages with image using correct MIME type
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": full_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]

            if self._stopped:
                return

            # Log the request
            self.log_message.emit("Sending request to LLM...", "INFO")
            self.progress.emit("Waiting for LLM response...")

            # Generate description using appropriate parameters
            if is_gpt5:
                # GPT-5 has fixed parameters (temperature=1.0)
                # Note: reasoning_effort is UI-only, not sent to API yet
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
            logger.info(f"LLM Response - Description: {description[:200]}...")
            console.info(f"LLM Response - Description: {description[:200]}...")
            self.log_message.emit("Description generated successfully", "INFO")

            self.finished.emit(description)

        except Exception as e:
            error_msg = f"Image analysis failed: {str(e)}"
            logger.error(error_msg)
            console.error(error_msg)
            self.log_message.emit(error_msg, "ERROR")
            self.error.emit(error_msg)


class ReferenceImageDialog(QDialog):
    """Dialog for analyzing reference images with LLM."""

    descriptionGenerated = Signal(str)

    def __init__(self, parent=None, config=None, image_path=None):
        super().__init__(parent)
        self.config = config
        self.image_path = image_path
        self.worker = None
        self.thread = None
        self.generated_description = None
        self.settings = QSettings("ImageAI", "ReferenceImageDialog")

        self.setWindowTitle("Analyze Reference Image with AI")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        # Restore window geometry
        self.restore_settings()

        self.init_ui()
        self.load_llm_settings()

        # Load image if provided, or restore previous image
        if image_path:
            self.load_image(image_path)
        else:
            # Try to restore previous image
            saved_image_path = self.settings.value("last_image_path", "")
            if saved_image_path and Path(saved_image_path).exists():
                self.load_image(saved_image_path)
                # Add a note that we restored the previous image
                QTimer.singleShot(100, lambda: self.status_console.log(
                    f"Restored previous image: {Path(saved_image_path).name}", "INFO"))

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

        # Image section
        image_group = QGroupBox("Reference Image")
        image_layout = QVBoxLayout(image_group)

        # Image display area with scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("No image loaded")
        self.image_label.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px dashed #ccc; }")
        scroll_area.setWidget(self.image_label)

        image_layout.addWidget(scroll_area)

        # Image controls
        image_controls = QHBoxLayout()
        self.btn_load_image = QPushButton("Load Image...")
        self.btn_load_image.clicked.connect(self.load_image_dialog)
        image_controls.addWidget(self.btn_load_image)

        self.image_path_label = QLabel("No image loaded")
        image_controls.addWidget(self.image_path_label)
        image_controls.addStretch()

        image_layout.addLayout(image_controls)
        main_layout.addWidget(image_group)

        # Analysis settings
        settings_group = QGroupBox("Analysis Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Analysis prompt
        prompt_layout = QVBoxLayout()
        prompt_layout.addWidget(QLabel("Analysis Prompt:"))

        self.analysis_prompt = QTextEdit()
        self.analysis_prompt.setPlaceholderText(
            "Describe what you want to know about the image...\n"
            "Default: 'Describe this image in detail for AI image generation.'"
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
        result_group = QGroupBox("Generated Description")
        result_layout = QVBoxLayout(result_group)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Description will appear here after analysis...")
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
        self.analyze_btn = QPushButton("Analyze Image")
        self.analyze_btn.setToolTip("Analyze the reference image with AI (Ctrl+Enter)")
        self.analyze_btn.setDefault(True)
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
            }
        """)
        self.analyze_btn.clicked.connect(self.analyze_image)
        self.analyze_btn.setEnabled(False)  # Disabled until image is loaded
        main_layout.addWidget(self.analyze_btn)

        # Add shortcut hint label
        shortcut_label = QLabel("<small style='color: gray;'>Shortcuts: Ctrl+Enter to analyze, Ctrl+O to open image, Esc to close</small>")
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
        analyze_shortcut.activated.connect(lambda: self.analyze_image() if self.analyze_btn.isEnabled() else None)

        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.reject)

    def load_image_dialog(self):
        """Open file dialog to load an image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff *.tif *.ico *.svg);;All Files (*.*)"
        )

        if file_path:
            self.load_image(file_path)

    def load_image(self, image_path):
        """Load and display an image."""
        try:
            self.image_path = image_path
            pixmap = QPixmap(image_path)

            if pixmap.isNull():
                QMessageBox.warning(self, "Invalid Image", "Could not load the selected image.")
                return

            # Scale image to fit while maintaining aspect ratio
            max_size = QSize(600, 400)
            scaled_pixmap = pixmap.scaled(max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setStyleSheet("")  # Remove placeholder style

            # Update path label
            path_obj = Path(image_path)
            self.image_path_label.setText(path_obj.name)
            self.image_path_label.setToolTip(str(path_obj))

            # Enable analyze button
            self.analyze_btn.setEnabled(True)

            # Save image path for next time
            self.settings.setValue("last_image_path", str(image_path))

            self.status_console.log(f"Loaded image: {path_obj.name}", "INFO")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")
            self.status_console.log(f"Error loading image: {str(e)}", "ERROR")

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
            # Set saved provider if available, or default to first provider
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
                # No saved provider or was "None", select first available
                if self.llm_provider_combo.count() > 0:
                    self.llm_provider_combo.setCurrentIndex(0)
        else:
            # No config, just select first available provider
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

    def analyze_image(self):
        """Analyze the loaded image with LLM."""
        if not self.image_path:
            QMessageBox.warning(self, "No Image", "Please load an image first.")
            return

        # Check if analysis is already running
        if self.thread and self.thread.isRunning():
            self.status_console.log("Analysis already in progress, please wait...", "WARNING")
            return

        # Get LLM settings
        llm_provider = self.llm_provider_combo.currentText()
        llm_model = self.llm_model_combo.currentText()

        if not llm_provider or not llm_model:
            QMessageBox.warning(self, "LLM Not Configured",
                                 "Please select an LLM provider and model.")
            return

        # Get API key
        api_key = None
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

        # Get analysis prompt
        analysis_prompt = self.analysis_prompt.toPlainText().strip()
        if not analysis_prompt:
            analysis_prompt = "Describe this image in detail for AI image generation."

        # Save settings before analysis
        self.save_dialog_settings()

        # Disable UI during analysis
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing...")

        # Clear previous results
        self.result_text.clear()

        # Log to status console
        self.status_console.clear()
        self.status_console.log(f"Analyzing image with {llm_provider} {llm_model}...", "INFO")

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
            self.image_path,
            llm_provider,
            llm_model,
            api_key,
            analysis_prompt,
            temperature,
            max_tokens,
            reasoning,
            verbosity
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
        self.status_console.log("Analysis complete!", "INFO")

        # Re-enable UI
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Image")

    def on_analysis_error(self, error: str):
        """Handle analysis error."""
        QMessageBox.critical(self, "Analysis Error", error)
        self.status_console.log(f"Error: {error}", "ERROR")

        # Re-enable UI
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Image")

    def accept(self):
        """Override accept to emit description if requested."""
        if self.generated_description:
            # Save to history
            self.history_widget.add_entry(
                self.analysis_prompt.toPlainText() if hasattr(self, 'analysis_prompt') else "Image analysis",
                self.generated_description,
                self.llm_provider_combo.currentText() if hasattr(self, 'llm_provider_combo') else "",
                self.llm_model_combo.currentText() if hasattr(self, 'llm_model_combo') else "",
                {
                    "image_path": str(self.image_path) if self.image_path else "No image"
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
                if 'image_path' in metadata:
                    self.status_console.log(f"Image: {metadata['image_path']}", "INFO")
            if 'provider' in item and item['provider']:
                self.status_console.log(f"Provider: {item['provider']} ({item.get('model', 'Unknown')})", "INFO")

            # Enable the Use Description button
            if hasattr(self, 'use_description_button'):
                self.use_description_button.setEnabled(True)



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