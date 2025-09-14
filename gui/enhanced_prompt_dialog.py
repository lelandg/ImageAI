"""Enhanced prompt dialog with LLM integration and status console."""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QGroupBox, QDialogButtonBox,
    QMessageBox, QSplitter, QWidget, QDoubleSpinBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QKeySequence, QShortcut

from .llm_utils import DialogStatusConsole
from core.prompt_enhancer import EnhancementLevel

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


class EnhanceWorker(QObject):
    """Worker for LLM enhancement operations."""
    finished = Signal(str)  # Enhanced prompt
    error = Signal(str)
    progress = Signal(str)
    log_message = Signal(str, str)  # Message, level (INFO/WARNING/ERROR)

    def __init__(self, prompt: str, llm_provider: str, llm_model: str, api_key: str,
                 enhancement_level: EnhancementLevel, style_preset: Optional[str] = None,
                 image_provider: str = "google", temperature: float = 0.7,
                 max_tokens: int = 1000, reasoning_effort: str = "medium",
                 verbosity: str = "medium"):
        super().__init__()
        self.prompt = prompt
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.api_key = api_key
        self.enhancement_level = enhancement_level
        self.style_preset = style_preset
        self.image_provider = image_provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity

    def run(self):
        """Run the enhancement operation."""
        try:
            self.progress.emit("Enhancing prompt...")
            self.log_message.emit("Starting prompt enhancement...", "INFO")

            # Log request details
            logger.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            console.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            self.log_message.emit(f"Provider: {self.llm_provider}, Model: {self.llm_model}", "INFO")

            logger.info(f"LLM Request - Original prompt: {self.prompt}")
            console.info(f"LLM Request - Original prompt: {self.prompt}")
            self.log_message.emit(f"Original prompt: {self.prompt[:100]}...", "INFO")

            logger.info(f"LLM Request - Enhancement level: {self.enhancement_level}")
            console.info(f"LLM Request - Enhancement level: {self.enhancement_level}")
            self.log_message.emit(f"Enhancement level: {self.enhancement_level}", "INFO")

            if self.style_preset:
                logger.info(f"LLM Request - Style preset: {self.style_preset}")
                console.info(f"LLM Request - Style preset: {self.style_preset}")
                self.log_message.emit(f"Style preset: {self.style_preset}", "INFO")

            # Import required modules
            from core.video.prompt_engine import UnifiedLLMProvider
            from core.prompt_enhancer_llm import PromptEnhancerLLM

            # Create API config
            api_config = {}
            provider_lower = self.llm_provider.lower()

            if provider_lower == "openai":
                api_config['openai_api_key'] = self.api_key
            elif provider_lower in ["google", "gemini"]:
                api_config['google_api_key'] = self.api_key
            elif provider_lower in ["claude", "anthropic"]:
                api_config['anthropic_api_key'] = self.api_key

            # Create LLM provider and enhancer
            llm = UnifiedLLMProvider(api_config)
            enhancer = PromptEnhancerLLM(llm)

            # Log parameters based on model
            is_gpt5 = "gpt-5" in self.llm_model.lower()
            if is_gpt5:
                logger.info(f"  Reasoning effort: {self.reasoning_effort}")
                console.info(f"  Reasoning effort: {self.reasoning_effort}")
                self.log_message.emit(f"Reasoning effort: {self.reasoning_effort}", "INFO")

                logger.info(f"  Verbosity: {self.verbosity}")
                console.info(f"  Verbosity: {self.verbosity}")
                self.log_message.emit(f"Verbosity: {self.verbosity}", "INFO")
            else:
                logger.info(f"  Temperature: {self.temperature}")
                console.info(f"  Temperature: {self.temperature}")
                self.log_message.emit(f"Temperature: {self.temperature}", "INFO")

                logger.info(f"  Max tokens: {self.max_tokens}")
                console.info(f"  Max tokens: {self.max_tokens}")
                self.log_message.emit(f"Max tokens: {self.max_tokens}", "INFO")

            # Enhance the prompt
            self.log_message.emit("Calling LLM for enhancement...", "INFO")
            enhanced_data = enhancer.enhance_with_llm(
                prompt=self.prompt,
                provider=self.image_provider,
                model=self.llm_model,
                enhancement_level=self.enhancement_level,
                style_preset=self.style_preset,
                temperature=self.temperature,
                llm_provider=self.llm_provider
            )

            # Extract the enhanced prompt
            enhanced_prompt = enhancer.get_enhanced_prompt_for_provider(
                enhanced_data, self.image_provider
            )

            if enhanced_prompt:
                logger.info(f"LLM Response - Status: Success")
                console.info(f"LLM Response - Status: Success")
                self.log_message.emit("Enhancement successful!", "SUCCESS")

                logger.info(f"LLM Response - Enhanced prompt: {enhanced_prompt}")
                console.info(f"LLM Response - Enhanced prompt: {enhanced_prompt}")

                # Show enhanced prompt in status console
                self.log_message.emit("=" * 60, "INFO")
                self.log_message.emit("Enhanced Prompt:", "SUCCESS")
                self.log_message.emit(enhanced_prompt, "INFO")
                self.log_message.emit("=" * 60, "INFO")

                self.finished.emit(enhanced_prompt)
            else:
                error_msg = "Failed to get enhanced prompt from LLM"
                logger.error(error_msg)
                console.error(error_msg)
                self.log_message.emit(error_msg, "ERROR")
                self.error.emit(error_msg)

        except Exception as e:
            error_msg = f"Enhancement failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            console.error(error_msg)
            self.log_message.emit(error_msg, "ERROR")
            self.error.emit(error_msg)


class EnhancedPromptDialog(QDialog):
    """Dialog for enhancing prompts with LLM."""

    promptEnhanced = Signal(str)

    def __init__(self, parent=None, config=None, current_prompt=""):
        super().__init__(parent)
        self.config = config
        self.current_prompt = current_prompt
        self.worker = None
        self.thread = None

        self.setWindowTitle("Enhance Prompt with AI")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)

        self.init_ui()
        self.load_llm_settings()

    def init_ui(self):
        """Initialize the UI."""
        main_layout = QVBoxLayout(self)

        # Create splitter for main content and status console
        splitter = QSplitter(Qt.Vertical)

        # Main content widget
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Current prompt
        prompt_group = QGroupBox("Current Prompt")
        prompt_layout = QVBoxLayout(prompt_group)

        self.prompt_display = QTextEdit()
        self.prompt_display.setPlainText(self.current_prompt)
        self.prompt_display.setMaximumHeight(100)
        prompt_layout.addWidget(self.prompt_display)

        layout.addWidget(prompt_group)

        # Enhancement settings
        settings_group = QGroupBox("Enhancement Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Enhancement level
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("Enhancement Level:"))

        self.level_combo = QComboBox()
        self.level_combo.addItems([
            "Low - Minimal changes",
            "Medium - Moderate enhancement",
            "High - Maximum detail"
        ])
        self.level_combo.setCurrentIndex(1)  # Default to medium
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()

        settings_layout.addLayout(level_layout)

        # Style preset
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Style Preset:"))

        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "None",
            "Cinematic Photoreal",
            "Watercolor Illustration",
            "Pixel Art (8-bit)",
            "Studio Portrait",
            "Anime/Manga",
            "Oil Painting",
            "Digital Art",
            "3D Render",
            "Comic Book",
            "Art Nouveau",
            "Cyberpunk",
            "Fantasy Art",
            "Minimalist",
            "Surrealism",
            "Pop Art",
            "Gothic",
            "Steampunk",
            "Vaporwave",
            "Film Noir",
            "Renaissance",
            "Abstract",
            "Photojournalism",
            "Fashion Editorial",
            "Architectural"
        ])
        style_layout.addWidget(self.style_combo)
        style_layout.addStretch()

        settings_layout.addLayout(style_layout)

        layout.addWidget(settings_group)

        # LLM settings
        llm_group = QGroupBox("LLM Settings")
        llm_layout = QVBoxLayout(llm_group)

        # Provider and model
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))

        self.llm_provider_combo = QComboBox()
        provider_layout.addWidget(self.llm_provider_combo)

        provider_layout.addWidget(QLabel("Model:"))
        self.llm_model_combo = QComboBox()
        provider_layout.addWidget(self.llm_model_combo)

        provider_layout.addStretch()
        llm_layout.addLayout(provider_layout)

        # Standard parameters (temperature, max tokens)
        self.standard_params_widget = QWidget()
        standard_layout = QHBoxLayout(self.standard_params_widget)
        standard_layout.setContentsMargins(0, 0, 0, 0)

        standard_layout.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.setToolTip("Controls randomness (0=deterministic, 2=very creative)")
        standard_layout.addWidget(self.temperature_spin)

        standard_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 4000)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(1000)
        self.max_tokens_spin.setToolTip("Maximum length of the response")
        standard_layout.addWidget(self.max_tokens_spin)

        standard_layout.addStretch()
        llm_layout.addWidget(self.standard_params_widget)

        # GPT-5 specific parameters
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
        llm_layout.addWidget(self.gpt5_params_widget)
        self.gpt5_params_widget.setVisible(False)  # Hidden by default

        layout.addWidget(llm_group)

        # Enhance button
        self.enhance_btn = QPushButton("Enhance Prompt")
        self.enhance_btn.clicked.connect(self.enhance_prompt)
        layout.addWidget(self.enhance_btn)

        # Enhanced prompt display
        result_group = QGroupBox("Enhanced Prompt")
        result_layout = QVBoxLayout(result_group)

        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        result_layout.addWidget(self.result_display)

        layout.addWidget(result_group)

        # Add main widget to splitter
        splitter.addWidget(main_widget)

        # Status console at the bottom
        self.status_console = DialogStatusConsole("Status", self)
        splitter.addWidget(self.status_console)

        # Set splitter sizes (70% content, 30% console)
        splitter.setSizes([420, 180])
        splitter.setStretchFactor(0, 1)  # Main content can stretch
        splitter.setStretchFactor(1, 0)  # Console maintains minimum size but can expand

        # Add splitter to main layout
        main_layout.addWidget(splitter)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        # Connect provider and model changes
        self.llm_provider_combo.currentTextChanged.connect(self.update_llm_models)
        self.llm_model_combo.currentTextChanged.connect(self.on_model_changed)

        # Add keyboard shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+Enter to enhance
        enhance_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        enhance_shortcut.activated.connect(self.enhance_prompt)

        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.reject)

    def load_llm_settings(self):
        """Load LLM settings from config."""
        from gui.main_window import MainWindow

        # Populate providers
        self.llm_provider_combo.clear()
        providers = [p for p in MainWindow.get_llm_providers() if p != "None"]
        self.llm_provider_combo.addItems(providers)

        if self.config:
            provider = self.config.get("llm_provider", "OpenAI")
            index = self.llm_provider_combo.findText(provider)
            if index >= 0:
                self.llm_provider_combo.setCurrentIndex(index)

            self.update_llm_models()

            model = self.config.get("llm_model", "")
            if model:
                index = self.llm_model_combo.findText(model)
                if index >= 0:
                    self.llm_model_combo.setCurrentIndex(index)

    def update_llm_models(self):
        """Update available models based on provider."""
        from gui.main_window import MainWindow

        provider = self.llm_provider_combo.currentText()
        self.llm_model_combo.clear()

        models = MainWindow.get_llm_models_for_provider(provider)
        if models:
            self.llm_model_combo.addItems(models)

        # Trigger model change to update parameter visibility
        self.on_model_changed()

    def on_model_changed(self, text=None):
        """Handle model change to show/hide GPT-5 specific parameters."""
        if text is None:
            text = self.llm_model_combo.currentText()

        # Show GPT-5 params only for GPT-5 models, hide standard params
        is_gpt5 = "gpt-5" in text.lower() if text else False
        self.gpt5_params_widget.setVisible(is_gpt5)
        self.standard_params_widget.setVisible(not is_gpt5)

    def enhance_prompt(self):
        """Enhance the prompt using LLM."""
        prompt = self.prompt_display.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt Required", "Please enter a prompt to enhance.")
            return

        # Get API key
        llm_provider = self.llm_provider_combo.currentText()
        api_key = None
        if self.config:
            provider_lower = llm_provider.lower()

            if provider_lower == "openai":
                api_key = self.config.get_api_key('openai')
                if not api_key:
                    api_key = self.config.get('openai_api_key')

            elif provider_lower in ["gemini", "google"]:
                api_key = self.config.get_api_key('google')
                if not api_key:
                    api_key = self.config.get('google_api_key') or self.config.get('api_key')

            elif provider_lower in ["claude", "anthropic"]:
                api_key = self.config.get_api_key('anthropic')
                if not api_key:
                    api_key = self.config.get('anthropic_api_key')

            if not api_key:
                QMessageBox.warning(
                    self, "API Key Required",
                    f"Please configure your {llm_provider} API key in Settings."
                )
                return
        else:
            return

        # Get enhancement level
        level_map = {
            0: EnhancementLevel.LOW,
            1: EnhancementLevel.MEDIUM,
            2: EnhancementLevel.HIGH
        }
        enhancement_level = level_map[self.level_combo.currentIndex()]

        # Get style preset
        style_preset = None if self.style_combo.currentText() == "None" else self.style_combo.currentText()

        # Get image provider
        image_provider = self.config.get('provider', 'google').lower() if self.config else 'google'

        # Disable UI during enhancement
        self.enhance_btn.setEnabled(False)
        self.enhance_btn.setText("Enhancing...")
        self.result_display.clear()

        # Clear status console
        self.status_console.clear()
        self.status_console.log("Starting enhancement...", "INFO")

        # Create worker thread
        self.thread = QThread()

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

        self.worker = EnhanceWorker(
            prompt,
            llm_provider,
            self.llm_model_combo.currentText(),
            api_key,
            enhancement_level,
            style_preset,
            image_provider,
            temperature,
            max_tokens,
            reasoning,
            verbosity
        )
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_enhancement_finished)
        self.worker.error.connect(self.on_enhancement_error)
        self.worker.progress.connect(lambda msg: self.enhance_btn.setText(msg))
        self.worker.log_message.connect(self.on_log_message)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup_thread)

        self.thread.start()

    def on_enhancement_finished(self, enhanced_prompt):
        """Handle successful enhancement."""
        self.result_display.setPlainText(enhanced_prompt)
        self.enhance_btn.setEnabled(True)
        self.enhance_btn.setText("Enhance Prompt")
        self.status_console.log("Enhancement completed successfully!", "SUCCESS")

    def on_enhancement_error(self, error):
        """Handle enhancement error."""
        QMessageBox.critical(self, "Enhancement Error", error)
        self.enhance_btn.setEnabled(True)
        self.enhance_btn.setText("Enhance Prompt")
        self.status_console.log(f"Error: {error}", "ERROR")

    def on_log_message(self, message, level):
        """Handle log message from worker."""
        self.status_console.log(message, level)

    def cleanup_thread(self):
        """Clean up worker thread."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.thread:
            self.thread.deleteLater()
            self.thread = None

    def accept_selection(self):
        """Accept the enhanced prompt."""
        enhanced = self.result_display.toPlainText().strip()
        if enhanced:
            self.promptEnhanced.emit(enhanced)
            self.accept()
        else:
            QMessageBox.warning(
                self, "No Enhancement",
                "Please enhance the prompt first or click Cancel to close."
            )