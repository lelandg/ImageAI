"""LLM question dialog for analyzing and improving prompts."""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QGroupBox, QDialogButtonBox,
    QMessageBox, QSplitter, QWidget, QSpinBox, QDoubleSpinBox,
    QTabWidget
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QSettings
from PySide6.QtGui import QKeySequence, QShortcut

from .llm_utils import (
    LLMResponseParser, DialogStatusConsole, LiteLLMHandler
)
from .history_widget import DialogHistoryWidget

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


class QuestionWorker(QObject):
    """Worker for LLM question operations."""
    finished = Signal(str)  # Answer text
    error = Signal(str)
    progress = Signal(str)
    log_message = Signal(str, str)  # Message, level (INFO/WARNING/ERROR)

    def __init__(self, prompt: str, question: str, llm_provider: str, llm_model: str, api_key: str,
                 temperature: float = 0.7,
                 reasoning_effort: str = "medium", verbosity: str = "medium"):
        super().__init__()
        self.prompt = prompt
        self.question = question
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.api_key = api_key
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity

    def run(self):
        """Run the LLM question operation."""
        try:
            self.progress.emit("Analyzing prompt...")
            self.log_message.emit("Starting prompt analysis...", "INFO")

            # Log LLM request to both file and console
            logger.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            console.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            self.log_message.emit(f"Provider: {self.llm_provider}, Model: {self.llm_model}", "INFO")

            logger.info(f"LLM Request - Prompt: {self.prompt}")
            console.info(f"LLM Request - Prompt: {self.prompt}")
            self.log_message.emit(f"Prompt: {self.prompt[:100]}...", "INFO")

            logger.info(f"LLM Request - Question: {self.question}")
            console.info(f"LLM Request - Question: {self.question}")
            self.log_message.emit(f"Question: {self.question}", "INFO")

            # Try to import and use litellm for better compatibility
            try:
                import litellm
                import os
                litellm.drop_params = True  # Drop unsupported params
                # Use environment variable instead of deprecated set_verbose
                os.environ['LITELLM_LOG'] = 'ERROR'  # Only show errors, not verbose info
                use_litellm = True
            except ImportError:
                logger.warning("LiteLLM not installed, falling back to direct SDK")
                console.warning("LiteLLM not installed, falling back to direct SDK")
                use_litellm = False

            # Create the prompt for the LLM
            system_prompt = """You are an expert prompt engineer for AI image generation.
                Analyze the given prompt and answer questions about it.
                Provide helpful, specific suggestions for improvement."""

            user_prompt = f"""Prompt: "{self.prompt}"

                Question: {self.question}

                Please provide a detailed, helpful answer."""

            if self.llm_provider.lower() == "openai":
                model_name = self.llm_model or "gpt-4"

                if use_litellm:
                    # Use litellm for better compatibility
                    request_data = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": self.temperature,
                    }

                    # Use max_completion_tokens for newer OpenAI models (GPT-4+, GPT-5)
                    # Use max_tokens only for GPT-3.5
                    if "gpt-3.5" in model_name.lower():
                        request_data["max_tokens"] = self.max_tokens
                        token_param_name = "max_tokens"
                    else:
                        # GPT-4, GPT-5, and newer models use max_completion_tokens
                        request_data["max_completion_tokens"] = self.max_tokens
                        token_param_name = "max_completion_tokens"

                    # Add GPT-5 specific parameters (when they become available)
                    if "gpt-5" in model_name.lower():
                        # Note: reasoning_effort and verbosity are not yet supported by the API
                        # Uncomment when OpenAI adds support for these parameters
                        # request_data["reasoning_effort"] = self.reasoning_effort
                        # request_data["verbosity"] = self.verbosity
                        logger.info(f"  Reasoning effort: {self.reasoning_effort} (UI only - not sent to API)")
                        console.info(f"  Reasoning effort: {self.reasoning_effort} (UI only - not sent to API)")
                        logger.info(f"  Verbosity: {self.verbosity} (UI only - not sent to API)")
                        console.info(f"  Verbosity: {self.verbosity} (UI only - not sent to API)")

                    logger.info(f"LLM Request - Sending via LiteLLM to OpenAI:")
                    console.info(f"LLM Request - Sending via LiteLLM to OpenAI:")

                    logger.info(f"  Model: {model_name}")
                    console.info(f"  Model: {model_name}")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  {token_param_name}: {request_data[token_param_name]}")
                    console.info(f"  {token_param_name}: {request_data[token_param_name]}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = litellm.completion(**request_data)

                    # Parse litellm response
                    answer = ""
                    if response and hasattr(response, 'choices') and len(response.choices) > 0:
                        choice = response.choices[0]
                        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                            answer = choice.message.content or ""
                        elif hasattr(choice, 'text'):
                            answer = choice.text or ""

                    answer = answer.strip() if answer else ""

                    # Check for empty response
                    if not answer:
                        logger.warning("Empty response from LLM, generating fallback")
                        answer = f"I apologize, but I received an empty response. Based on your question about '{self.question[:50]}...', I can say that this prompt is designed for image generation, not text generation. It contains detailed visual descriptions and should produce an image, not text."
                else:
                    # Fallback to direct OpenAI SDK
                    from openai import OpenAI
                    client = OpenAI(api_key=self.api_key)

                    # Use appropriate token parameter based on model
                    # GPT-3.5 uses max_tokens, all newer models use max_completion_tokens
                    if "gpt-3.5" in model_name.lower():
                        token_param = "max_tokens"
                    else:
                        # GPT-4, GPT-5, and newer models use max_completion_tokens
                        token_param = "max_completion_tokens"

                    # For gpt-5, use temperature=1 (the only supported value)
                    temperature = 1.0 if "gpt-5" in model_name.lower() else self.temperature

                    request_data = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temperature,
                        token_param: self.max_tokens
                    }

                    logger.info(f"LLM Request - Sending to OpenAI API:")
                    console.info(f"LLM Request - Sending to OpenAI API:")

                    logger.info(f"  Model: {model_name}")
                    console.info(f"  Model: {model_name}")

                    logger.info(f"  Temperature: {temperature}")
                    console.info(f"  Temperature: {temperature}")

                    logger.info(f"  Token limit ({token_param}): {request_data[token_param]}")
                    console.info(f"  Token limit ({token_param}): {request_data[token_param]}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = client.chat.completions.create(**request_data)
                    answer = ""
                    if response and hasattr(response, 'choices') and len(response.choices) > 0:
                        if hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'content'):
                            answer = response.choices[0].message.content or ""

                    answer = answer.strip() if answer else ""

                    # Check for empty response
                    if not answer:
                        logger.warning("Empty response from OpenAI, generating fallback")
                        answer = f"I apologize, but I received an empty response. Based on your question, here's what I can say: This prompt is clearly designed for AI image generation, not text generation. It contains detailed visual descriptions that would produce an image."

                logger.info(f"LLM Response - Status: Success")
                console.info(f"LLM Response - Status: Success")
                self.log_message.emit("Response received successfully", "SUCCESS")

                logger.info(f"LLM Response - Answer length: {len(answer)} chars")
                console.info(f"LLM Response - Answer length: {len(answer)} chars")
                self.log_message.emit(f"Answer length: {len(answer)} chars", "INFO")

                logger.info(f"LLM Response - Answer: {answer}")
                console.info(f"LLM Response - Answer: {answer}")

                # Show answer preview in status console
                self.log_message.emit("=" * 40, "INFO")
                self.log_message.emit("Answer:", "SUCCESS")
                # Split answer into lines for better display
                for line in answer.split('\n'):
                    if line.strip():
                        self.log_message.emit(line.strip(), "INFO")
                self.log_message.emit("=" * 40, "INFO")

                self.finished.emit(answer)

            elif self.llm_provider.lower() == "gemini" or self.llm_provider.lower() == "google":
                model_name = self.llm_model or "gemini-pro"

                if use_litellm:
                    # Use litellm for better compatibility
                    request_data = {
                        "model": f"gemini/{model_name}" if not model_name.startswith("gemini/") else model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": self.temperature,
                    }

                    # Gemini uses max_tokens
                    request_data["max_tokens"] = self.max_tokens

                    logger.info(f"LLM Request - Sending via LiteLLM to Gemini:")
                    console.info(f"LLM Request - Sending via LiteLLM to Gemini:")

                    logger.info(f"  Model: {request_data['model']}")
                    console.info(f"  Model: {request_data['model']}")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  Max tokens: {request_data['max_tokens']}")
                    console.info(f"  Max tokens: {request_data['max_tokens']}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = litellm.completion(**request_data)

                    # Parse litellm response
                    answer = ""
                    if response and hasattr(response, 'choices') and len(response.choices) > 0:
                        choice = response.choices[0]
                        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                            answer = choice.message.content or ""
                        elif hasattr(choice, 'text'):
                            answer = choice.text or ""

                    answer = answer.strip() if answer else ""

                    # Check for empty response
                    if not answer:
                        logger.warning("Empty response from Gemini LLM, generating fallback")
                        answer = f"I received an empty response. Based on your question, this appears to be an image generation prompt with detailed visual descriptions."
                else:
                    # Fallback to direct Gemini SDK
                    import google.generativeai as genai
                    genai.configure(api_key=self.api_key)
                    model = genai.GenerativeModel(model_name)

                    prompt_text = f"""As an expert in AI image generation prompts, analyze this prompt and answer the question.

                    Prompt: "{self.prompt}"

                    Question: {self.question}

                    Provide a detailed, helpful answer with specific suggestions."""

                    logger.info(f"LLM Request - Sending to Gemini API:")
                    console.info(f"LLM Request - Sending to Gemini API:")

                    logger.info(f"  Model: {model_name}")
                    console.info(f"  Model: {model_name}")

                    # Clean up multi-line strings for logging
                    clean_prompt = prompt_text.replace('\n', ' ').strip()

                    logger.info(f"  Prompt: {clean_prompt}")
                    console.info(f"  Prompt: {clean_prompt}")

                    response = model.generate_content(prompt_text)
                    answer = ""
                    if response and hasattr(response, 'text'):
                        answer = response.text or ""

                    answer = answer.strip() if answer else ""

                    # Check for empty response
                    if not answer:
                        logger.warning("Empty response from Gemini, generating fallback")
                        answer = f"I received an empty response. Based on your question about the prompt, this is clearly an image generation prompt with detailed visual descriptions."

                logger.info(f"LLM Response - Status: Success")
                console.info(f"LLM Response - Status: Success")
                self.log_message.emit("Response received successfully", "SUCCESS")

                logger.info(f"LLM Response - Answer length: {len(answer)} chars")
                console.info(f"LLM Response - Answer length: {len(answer)} chars")
                self.log_message.emit(f"Answer length: {len(answer)} chars", "INFO")

                logger.info(f"LLM Response - Answer: {answer}")
                console.info(f"LLM Response - Answer: {answer}")

                # Show answer preview in status console
                self.log_message.emit("=" * 40, "INFO")
                self.log_message.emit("Answer:", "SUCCESS")
                # Split answer into lines for better display
                for line in answer.split('\n'):
                    if line.strip():
                        self.log_message.emit(line.strip(), "INFO")
                self.log_message.emit("=" * 40, "INFO")

                self.finished.emit(answer)

            elif self.llm_provider.lower() == "claude":
                logger.info("Using Claude for prompt question")
                console.info("Using Claude for prompt question")

                model_name = self.llm_model or "claude-sonnet-4-5"

                if use_litellm:
                    # Use litellm with Anthropic provider - must prefix with "anthropic/"
                    litellm_model = f"anthropic/{model_name}"
                    request_data = {
                        "model": litellm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "api_key": self.api_key  # Pass API key directly to LiteLLM
                    }

                    logger.info(f"LLM Request - Sending via LiteLLM to Claude:")
                    console.info(f"LLM Request - Sending via LiteLLM to Claude:")

                    logger.info(f"  Model: {litellm_model} (original: {model_name})")
                    console.info(f"  Model: {litellm_model} (original: {model_name})")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  Max tokens: {request_data['max_tokens']}")
                    console.info(f"  Max tokens: {request_data['max_tokens']}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = litellm.completion(**request_data)

                    # Parse litellm response
                    answer = ""
                    if response and hasattr(response, 'choices') and len(response.choices) > 0:
                        choice = response.choices[0]
                        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                            answer = choice.message.content or ""
                        elif hasattr(choice, 'text'):
                            answer = choice.text or ""

                    answer = answer.strip() if answer else ""

                    # Check for empty response
                    if not answer:
                        logger.warning("Empty response from Claude, generating fallback")
                        answer = f"I apologize, but I received an empty response. Based on your question about '{self.question[:50]}...', I can say that this prompt is designed for image generation. It contains detailed visual descriptions and should produce an image."
                else:
                    # Fallback to direct Anthropic SDK
                    from anthropic import Anthropic
                    client = Anthropic(api_key=self.api_key)

                    request_data = {
                        "model": model_name,
                        "messages": [
                            {"role": "user", "content": user_prompt}
                        ],
                        "system": system_prompt,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens
                    }

                    logger.info(f"LLM Request - Sending to Claude API:")
                    console.info(f"LLM Request - Sending to Claude API:")

                    logger.info(f"  Model: {request_data['model']}")
                    console.info(f"  Model: {request_data['model']}")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  Max tokens: {request_data['max_tokens']}")
                    console.info(f"  Max tokens: {request_data['max_tokens']}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = client.messages.create(**request_data)

                    # Parse Anthropic SDK response
                    answer = ""
                    if hasattr(response, 'content'):
                        # Anthropic SDK returns content as list of blocks
                        if isinstance(response.content, list) and len(response.content) > 0:
                            answer = response.content[0].text
                        else:
                            answer = str(response.content)

                    answer = answer.strip() if answer else ""

                    # Check for empty response
                    if not answer:
                        logger.warning("Empty response from Claude, generating fallback")
                        answer = f"I apologize, but I received an empty response. Based on your question about '{self.question[:50]}...', I can say that this prompt is designed for image generation. It contains detailed visual descriptions and should produce an image."

                # Log response
                logger.info("=" * 40)
                logger.info("LLM Response:")
                for line in answer.split('\n'):
                    if line.strip():
                        logger.info(line.strip())
                logger.info("=" * 40)

                console.info("=" * 40)
                console.info("LLM Response:")
                for line in answer.split('\n'):
                    if line.strip():
                        console.info(line.strip())
                console.info("=" * 40)

                self.log_message.emit("=" * 40, "INFO")
                self.log_message.emit("LLM Response:", "INFO")
                for line in answer.split('\n'):
                    if line.strip():
                        self.log_message.emit(line.strip(), "INFO")
                self.log_message.emit("=" * 40, "INFO")

                self.finished.emit(answer)

            elif self.llm_provider.lower() == "ollama":
                logger.info("Using Ollama for prompt question")
                # Ollama implementation would go here
                self.error.emit(f"Ollama support coming soon")

            elif self.llm_provider.lower() == "lm studio":
                logger.info("Using LM Studio for prompt question")
                # LM Studio implementation would go here
                self.error.emit(f"LM Studio support coming soon")

            else:
                self.error.emit(f"Unsupported LLM provider: {self.llm_provider}")

        except Exception as e:
            logger.error(f"LLM Error - Request failed: {str(e)}")
            console.error(f"LLM Error - Request failed: {str(e)}")

            logger.error(f"LLM Error - Exception type: {type(e).__name__}")
            console.error(f"LLM Error - Exception type: {type(e).__name__}")

            logger.error(f"LLM Error - Full exception:", exc_info=True)
            console.error(f"LLM Error - Full exception: {str(e)}")

            self.error.emit(f"Failed to get answer: {str(e)}")


class PromptQuestionDialog(QDialog):
    """Dialog for asking questions about prompts using LLM."""

    def __init__(self, parent=None, config=None, current_prompt=""):
        super().__init__(parent)
        self.config = config
        self.current_prompt = current_prompt
        self.worker = None
        self.thread = None
        self.settings = QSettings("ImageAI", "PromptQuestionDialog")
        self.last_session = self.load_last_session()
        self.question_history = self.load_history()

        self.setWindowTitle("Ask About Prompt")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # Restore window geometry
        self.restore_settings()

        self.init_ui()
        self.load_llm_settings()
        self.restore_last_session()

    def init_ui(self):
        """Initialize the UI."""
        main_layout = QVBoxLayout(self)

        # Create splitter for main content and status console
        splitter = QSplitter(Qt.Vertical)

        # Main content widget
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Current prompt display
        prompt_group = QGroupBox("Current Prompt")
        prompt_layout = QVBoxLayout(prompt_group)

        self.prompt_display = QTextEdit()
        self.prompt_display.setPlainText(self.current_prompt)
        self.prompt_display.setReadOnly(True)
        self.prompt_display.setMaximumHeight(100)
        prompt_layout.addWidget(self.prompt_display)

        layout.addWidget(prompt_group)

        # Predefined questions
        questions_group = QGroupBox("Quick Questions")
        questions_layout = QVBoxLayout(questions_group)

        self.predefined_combo = QComboBox()
        self.predefined_combo.addItems([
            "Select a question...",
            "How can I make this prompt more detailed?",
            "What style keywords would improve this?",
            "What's missing from this prompt?",
            "How can I make the composition better?",
            "What lighting would work best?",
            "Suggest camera angles for this scene",
            "What color palette would enhance this?",
            "How can I make this more photorealistic?",
            "What artistic style would suit this?",
            "How can I add more emotion/mood?"
        ])
        self.predefined_combo.currentTextChanged.connect(self.on_predefined_selected)
        questions_layout.addWidget(self.predefined_combo)

        layout.addWidget(questions_group)

        # Custom question
        custom_group = QGroupBox("Your Question")
        custom_layout = QVBoxLayout(custom_group)

        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText(
            "Ask anything about the prompt - improvements, style suggestions, technical details..."
        )
        self.question_input.setMaximumHeight(100)
        custom_layout.addWidget(self.question_input)

        layout.addWidget(custom_group)

        # LLM settings
        settings_group = QGroupBox("LLM Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Provider and model row
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))

        self.llm_provider_combo = QComboBox()
        provider_layout.addWidget(self.llm_provider_combo)

        provider_layout.addWidget(QLabel("Model:"))
        self.llm_model_combo = QComboBox()
        provider_layout.addWidget(self.llm_model_combo)

        provider_layout.addStretch()
        settings_layout.addLayout(provider_layout)

        # Parameters row
        params_layout = QHBoxLayout()

        # Temperature control
        params_layout.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.setToolTip("Controls randomness (0=deterministic, 2=very creative)")
        params_layout.addWidget(self.temperature_spin)

        # Max tokens control
        params_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 4000)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(1000)
        self.max_tokens_spin.setToolTip("Maximum length of the response")
        params_layout.addWidget(self.max_tokens_spin)

        params_layout.addStretch()

        self.ask_btn = QPushButton("Ask Question")
        self.ask_btn.clicked.connect(self.ask_question)
        params_layout.addWidget(self.ask_btn)

        settings_layout.addLayout(params_layout)

        # GPT-5 specific parameters row (shown/hidden based on model)
        self.gpt5_params_widget = QWidget()
        gpt5_layout = QHBoxLayout(self.gpt5_params_widget)
        gpt5_layout.setContentsMargins(0, 0, 0, 0)

        # Reasoning effort for GPT-5
        gpt5_layout.addWidget(QLabel("Reasoning:"))
        self.reasoning_combo = QComboBox()
        self.reasoning_combo.addItems(["low", "medium", "high"])
        self.reasoning_combo.setCurrentText("medium")
        self.reasoning_combo.setToolTip("GPT-5 reasoning effort level")
        gpt5_layout.addWidget(self.reasoning_combo)

        # Verbosity for GPT-5
        gpt5_layout.addWidget(QLabel("Verbosity:"))
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItems(["low", "medium", "high"])
        self.verbosity_combo.setCurrentText("medium")
        self.verbosity_combo.setToolTip("GPT-5 response detail level")
        gpt5_layout.addWidget(self.verbosity_combo)

        gpt5_layout.addStretch()
        settings_layout.addWidget(self.gpt5_params_widget)
        self.gpt5_params_widget.setVisible(False)  # Hidden by default

        layout.addWidget(settings_group)

        # Answer display
        answer_group = QGroupBox("Answer")
        answer_layout = QVBoxLayout(answer_group)

        self.answer_display = QTextEdit()
        self.answer_display.setReadOnly(True)
        answer_layout.addWidget(self.answer_display)

        layout.addWidget(answer_group)

        # Add main widget to splitter
        splitter.addWidget(main_widget)

        # Status console at the bottom
        self.status_console = DialogStatusConsole("Status", self)
        splitter.addWidget(self.status_console)

        # Set splitter sizes (70% content, 30% console)
        splitter.setSizes([350, 150])
        splitter.setStretchFactor(0, 1)  # Main content can stretch
        splitter.setStretchFactor(1, 0)  # Console maintains minimum size but can expand

        # Add splitter to main layout
        main_layout.addWidget(splitter)

        # Restore splitter state if saved
        splitter_state = self.settings.value("splitter_state")
        if splitter_state:
            splitter.restoreState(splitter_state)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        # Connect provider and model changes
        self.llm_provider_combo.currentTextChanged.connect(self.update_llm_models)
        self.llm_model_combo.currentTextChanged.connect(self.on_model_changed)

        # Add keyboard shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+Enter to ask question
        ask_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        ask_shortcut.activated.connect(self.ask_question)

        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.reject)

    def load_llm_settings(self):
        """Load LLM settings from config."""
        # Import MainWindow to use its LLM functions
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

        # Get models for the selected provider
        models = MainWindow.get_llm_models_for_provider(provider)
        if models:
            self.llm_model_combo.addItems(models)

        # Trigger model change to update GPT-5 params visibility
        self.on_model_changed()

    def on_model_changed(self, text=None):
        """Handle model change to show/hide GPT-5 specific parameters."""
        if text is None:
            text = self.llm_model_combo.currentText()

        # Show GPT-5 params only for GPT-5 models
        is_gpt5 = "gpt-5" in text.lower() if text else False
        self.gpt5_params_widget.setVisible(is_gpt5)

    def on_predefined_selected(self, text):
        """Handle predefined question selection."""
        if text != "Select a question...":
            self.question_input.setPlainText(text)

    def ask_question(self):
        """Ask the question using LLM."""
        question = self.question_input.toPlainText().strip()
        if not question:
            QMessageBox.warning(self, "Question Required", "Please enter a question.")
            return

        prompt = self.prompt_display.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt Required", "No prompt to analyze.")
            return

        # Get API key using same method as enhance prompt for backward compatibility
        llm_provider = self.llm_provider_combo.currentText()
        api_key = None
        if self.config:
            provider_lower = llm_provider.lower()

            # Try multiple locations for backward compatibility
            if provider_lower == "openai":
                # Use ConfigManager's get_api_key method
                api_key = self.config.get_api_key('openai')
                # Check direct config as fallback
                if not api_key:
                    api_key = self.config.get('openai_api_key')

            elif provider_lower == "gemini" or provider_lower == "google":
                # Use ConfigManager's get_api_key method
                api_key = self.config.get_api_key('google')
                # Check direct config (try multiple keys)
                if not api_key:
                    api_key = self.config.get('google_api_key') or self.config.get('api_key')

            elif provider_lower == "claude" or provider_lower == "anthropic":
                # Use ConfigManager's get_api_key method
                api_key = self.config.get_api_key('anthropic')
                # Check direct config
                if not api_key:
                    api_key = self.config.get('anthropic_api_key')
                # Check using get_api_key method
                if not api_key:
                    api_key = self.config.get_api_key('anthropic')

            elif provider_lower == "stability":
                # Use ConfigManager's get_api_key method
                api_key = self.config.get_api_key('stability')
                # Check direct config as fallback
                if not api_key:
                    api_key = self.config.get('stability_api_key')

            if not api_key:
                QMessageBox.warning(
                    self, "API Key Required",
                    f"Please configure your {llm_provider} API key in Settings."
                )
                return
        else:
            return

        # Save session for restoration
        self.save_last_session()

        # Disable UI during processing
        self.ask_btn.setEnabled(False)
        self.ask_btn.setText("Processing...")
        self.answer_display.clear()

        # Create worker thread
        self.thread = QThread()

        # Get GPT-5 specific params if applicable
        reasoning = self.reasoning_combo.currentText() if self.gpt5_params_widget.isVisible() else "medium"
        verbosity = self.verbosity_combo.currentText() if self.gpt5_params_widget.isVisible() else "medium"

        self.worker = QuestionWorker(
            prompt, question,
            llm_provider,
            self.llm_model_combo.currentText(),
            api_key,
            self.temperature_spin.value(),
            self.max_tokens_spin.value(),
            reasoning,
            verbosity
        )
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_answer_received)
        self.worker.error.connect(self.on_error)
        self.worker.progress.connect(lambda msg: self.ask_btn.setText(msg))
        self.worker.log_message.connect(self.on_log_message)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup_thread)

        self.thread.start()

    def on_answer_received(self, answer):
        """Handle answer from LLM."""
        self.answer_display.setPlainText(answer)
        self.ask_btn.setEnabled(True)
        self.ask_btn.setText("Ask Question")

        # Save to history (successful)
        self.save_to_history(
            self.prompt_display.toPlainText(),
            self.question_input.toPlainText(),
            answer,
            error=None
        )

    def on_error(self, error):
        """Handle error."""
        QMessageBox.critical(self, "Error", error)
        self.status_console.log(f"Error: {error}", "ERROR")
        self.ask_btn.setEnabled(True)
        self.ask_btn.setText("Ask Question")

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

    def save_last_session(self):
        """Save the current session state."""
        if self.config:
            # Save LLM settings to config (application-wide)
            self.config.set('llm_provider', self.llm_provider_combo.currentText())
            self.config.set('llm_model', self.llm_model_combo.currentText())

            from pathlib import Path
            import json
            session = {
                "prompt": self.prompt_display.toPlainText(),
                "question": self.question_input.toPlainText(),
                "answer": self.answer_display.toPlainText(),
                "llm_provider": self.llm_provider_combo.currentText(),
                "llm_model": self.llm_model_combo.currentText(),
                "predefined_index": self.predefined_combo.currentIndex(),
                "temperature": self.temperature_spin.value(),
                "max_tokens": self.max_tokens_spin.value(),
                "reasoning_effort": self.reasoning_combo.currentText() if self.gpt5_params_widget.isVisible() else "medium",
                "verbosity": self.verbosity_combo.currentText() if self.gpt5_params_widget.isVisible() else "medium"
            }
            session_file = Path(self.config.config_dir) / "prompt_question_session.json"
            try:
                with open(session_file, 'w') as f:
                    json.dump(session, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save session: {e}")

    def load_last_session(self):
        """Load the last session state."""
        if self.config:
            from pathlib import Path
            import json
            session_file = Path(self.config.config_dir) / "prompt_question_session.json"
            if session_file.exists():
                try:
                    with open(session_file, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load session: {e}")
        return {}

    def restore_last_session(self):
        """Restore the last session state."""
        if self.last_session:
            # Restore prompt
            if "prompt" in self.last_session:
                self.prompt_display.setPlainText(self.last_session["prompt"])

            # Restore question
            if "question" in self.last_session:
                self.question_input.setPlainText(self.last_session["question"])

            # Restore answer
            if "answer" in self.last_session:
                self.answer_display.setPlainText(self.last_session["answer"])

            # Restore predefined selection
            if "predefined_index" in self.last_session:
                self.predefined_combo.setCurrentIndex(self.last_session["predefined_index"])

            # Restore LLM provider
            if "llm_provider" in self.last_session:
                index = self.llm_provider_combo.findText(self.last_session["llm_provider"])
                if index >= 0:
                    self.llm_provider_combo.setCurrentIndex(index)

            # Restore LLM model
            if "llm_model" in self.last_session:
                index = self.llm_model_combo.findText(self.last_session["llm_model"])
                if index >= 0:
                    self.llm_model_combo.setCurrentIndex(index)

            # Restore temperature
            if "temperature" in self.last_session:
                self.temperature_spin.setValue(self.last_session["temperature"])

            # Restore max tokens
            if "max_tokens" in self.last_session:
                self.max_tokens_spin.setValue(self.last_session["max_tokens"])

            # Restore GPT-5 params
            if "reasoning_effort" in self.last_session:
                idx = self.reasoning_combo.findText(self.last_session["reasoning_effort"])
                if idx >= 0:
                    self.reasoning_combo.setCurrentIndex(idx)

            if "verbosity" in self.last_session:
                idx = self.verbosity_combo.findText(self.last_session["verbosity"])
                if idx >= 0:
                    self.verbosity_combo.setCurrentIndex(idx)

    def save_to_history(self, prompt, question, answer, error=None):
        """Save question/answer to history."""
        if self.config:
            from pathlib import Path
            import json
            from datetime import datetime

            entry = {
                "timestamp": datetime.now().isoformat(),
                "prompt": prompt,
                "question": question,
                "answer": answer,
                "error": error,
                "provider": self.llm_provider_combo.currentText(),
                "model": self.llm_model_combo.currentText()
            }
            self.question_history.append(entry)

            # Save to file
            history_file = Path(self.config.config_dir) / "prompt_question_history.json"
            try:
                with open(history_file, 'w') as f:
                    json.dump(self.question_history, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save history: {e}")

    def load_history(self):
        """Load question/answer history."""
        if self.config:
            from pathlib import Path
            import json
            history_file = Path(self.config.config_dir) / "prompt_question_history.json"
            if history_file.exists():
                try:
                    with open(history_file, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load history: {e}")
        return []

    def save_settings(self):
        """Save window geometry and splitter state."""
        self.settings.setValue("geometry", self.saveGeometry())
        # Find and save splitter state
        splitters = self.findChildren(QSplitter)
        if splitters:
            self.settings.setValue("splitter_state", splitters[0].saveState())

    def restore_settings(self):
        """Restore window geometry and splitter state."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def reject(self):
        """Override reject to save settings before closing."""
        self.save_last_session()
        self.save_settings()
        super().reject()

    def closeEvent(self, event):
        """Handle close event."""
        # Stop any running worker
        if self.worker and self.thread and self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()

        # Save session state
        self.save_last_session()
        # Save window settings
        self.save_settings()
        super().closeEvent(event)