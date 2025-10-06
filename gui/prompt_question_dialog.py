"""Enhanced LLM question dialog for analyzing prompts and general AI assistance."""

import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QGroupBox, QDialogButtonBox,
    QMessageBox, QSplitter, QWidget, QDoubleSpinBox,
    QTabWidget, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QSettings
from PySide6.QtGui import QKeySequence, QShortcut

from .llm_utils import DialogStatusConsole
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
                 temperature: float = 0.7, reasoning_effort: str = "medium", verbosity: str = "medium",
                 conversation_history=None):
        super().__init__()
        self.prompt = prompt
        self.question = question
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.api_key = api_key
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self.conversation_history = conversation_history or []

    def run(self):
        """Run the LLM question operation."""
        try:
            self.progress.emit("Processing question...")
            self.log_message.emit("Starting AI conversation...", "INFO")

            # Log request details
            logger.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            console.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            self.log_message.emit(f"Provider: {self.llm_provider}, Model: {self.llm_model}", "INFO")

            if self.prompt:
                logger.info(f"LLM Request - Prompt: {self.prompt}")
                console.info(f"LLM Request - Prompt: {self.prompt}")
                self.log_message.emit(f"Prompt: {self.prompt[:100]}...", "INFO")

            logger.info(f"LLM Request - Question: {self.question}")
            console.info(f"LLM Request - Question: {self.question}")
            self.log_message.emit(f"Question: {self.question}", "INFO")

            # Try to use litellm for better compatibility
            try:
                import litellm
                litellm.drop_params = True
                use_litellm = True
            except ImportError:
                logger.warning("LiteLLM not installed, falling back to direct SDK")
                use_litellm = False

            # Create appropriate system prompt based on context
            if self.prompt:
                system_prompt = """You are an expert prompt engineer for AI image generation.
                    Analyze prompts, answer questions, and provide helpful suggestions for improvement.
                    Be creative, specific, and helpful."""

                # Build conversation with context
                messages = [{"role": "system", "content": system_prompt}]

                # Add conversation history
                for entry in self.conversation_history:
                    if entry.get('prompt'):
                        messages.append({"role": "user", "content": f"Prompt: {entry['prompt']}\n\nQuestion: {entry['question']}"})
                    else:
                        messages.append({"role": "user", "content": entry['question']})
                    messages.append({"role": "assistant", "content": entry['answer']})

                # Add current question with prompt context
                messages.append({"role": "user", "content": f"Prompt: {self.prompt}\n\nQuestion: {self.question}"})

            else:
                # Freeform mode - no prompt context
                system_prompt = """You are a helpful AI assistant with expertise in AI image generation,
                    prompt engineering, creative visual concepts, and art styles.
                    Answer questions helpfully, creatively, and with specific examples when appropriate."""

                messages = [{"role": "system", "content": system_prompt}]

                # Add conversation history
                for entry in self.conversation_history:
                    messages.append({"role": "user", "content": entry['question']})
                    messages.append({"role": "assistant", "content": entry['answer']})

                # Add current question
                messages.append({"role": "user", "content": self.question})

            # Generate response based on provider
            answer = ""

            if self.llm_provider.lower() == "openai":
                model_name = self.llm_model or "gpt-4"

                if use_litellm:
                    import litellm
                    # Don't specify max_tokens - let model decide
                    response = litellm.completion(
                        model=model_name,
                        messages=messages,
                        temperature=self.temperature,
                        api_key=self.api_key
                    )
                    answer = response.choices[0].message.content
                else:
                    import openai
                    client = openai.OpenAI(api_key=self.api_key)
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=self.temperature
                    )
                    answer = response.choices[0].message.content

            elif self.llm_provider.lower() in ["google", "gemini"]:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)

                model_name = self.llm_model or "gemini-2.0-flash-exp"
                model = genai.GenerativeModel(model_name)

                # Format conversation for Gemini
                if self.prompt:
                    prompt_text = f"Prompt to analyze: {self.prompt}\n\nQuestion: {self.question}"
                else:
                    prompt_text = self.question

                response = model.generate_content(prompt_text)
                if response and hasattr(response, 'text'):
                    answer = response.text or ""

            # Fallback for empty response
            if not answer:
                answer = "I apologize, but I didn't receive a proper response. Please try again."

            # Log response
            logger.info(f"LLM Response - Answer: {answer[:200]}...")
            console.info(f"LLM Response - Answer: {answer[:200]}...")
            self.log_message.emit("Response received successfully", "SUCCESS")

            # Display answer in status console
            self.log_message.emit("=" * 40, "INFO")
            for line in answer.split('\n')[:5]:  # Show first 5 lines
                if line.strip():
                    self.log_message.emit(line.strip(), "INFO")
            self.log_message.emit("=" * 40, "INFO")

            self.finished.emit(answer)

        except Exception as e:
            error_msg = f"Failed to get answer: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)
            self.log_message.emit(error_msg, "ERROR")


class PromptQuestionDialog(QDialog):
    """Enhanced dialog for AI conversations and prompt analysis."""

    def __init__(self, parent=None, config=None, current_prompt=""):
        super().__init__(parent)
        self.config = config
        self.initial_prompt = current_prompt
        self.current_prompt = ""  # Start with empty editable field
        self.worker = None
        self.thread = None
        self.conversation_history = []
        self.settings = QSettings("ImageAI", "PromptQuestionDialog")

        # Set window title based on mode
        if current_prompt:
            self.setWindowTitle("Ask About Prompt")
        else:
            self.setWindowTitle("Ask AI Anything")

        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        # Restore window geometry
        self.restore_settings()

        self.init_ui()
        self.load_llm_settings()
        self.restore_dialog_settings()

    def init_ui(self):
        """Initialize the UI with tabs."""
        main_layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Conversation tab
        conversation_widget = self.create_conversation_tab()
        self.tab_widget.addTab(conversation_widget, "Conversation")

        # History tab
        self.history_widget = DialogHistoryWidget("prompt_questions", self)
        self.history_widget.itemDoubleClicked.connect(self.load_history_item)
        self.tab_widget.addTab(self.history_widget, "History")

        main_layout.addWidget(self.tab_widget)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        # Add keyboard shortcuts
        self.setup_shortcuts()

    def create_conversation_tab(self):
        """Create the main conversation tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Create splitter for content and status
        splitter = QSplitter(Qt.Vertical)

        # Main content
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        # Prompt input section
        prompt_group = QGroupBox("Prompt to Analyze (Optional)")
        prompt_layout = QVBoxLayout(prompt_group)

        # Add info label about editability
        info_label = QLabel("💡 You can edit the prompt below before asking questions")
        info_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        prompt_layout.addWidget(info_label)

        self.prompt_input = QTextEdit()
        if self.initial_prompt:
            self.prompt_input.setPlainText(self.initial_prompt)
            self.prompt_input.setPlaceholderText("Enter a prompt to analyze...")
        else:
            self.prompt_input.setPlaceholderText("Enter a prompt to analyze (optional - leave empty for general questions)...")
        self.prompt_input.setMaximumHeight(80)

        # Initially set as read-only with visual indication
        self.prompt_input.setReadOnly(True)
        self.prompt_input.setStyleSheet("QTextEdit[readOnly=\"true\"] { background-color: #f5f5f5; }")

        prompt_layout.addWidget(self.prompt_input)

        # Control buttons
        control_layout = QHBoxLayout()

        # Edit/Save button
        self.edit_prompt_btn = QPushButton("✏️ Edit Prompt")
        self.edit_prompt_btn.setCheckable(True)
        self.edit_prompt_btn.setToolTip("Toggle edit mode (Ctrl+E)")
        self.edit_prompt_btn.clicked.connect(self.toggle_prompt_edit)
        control_layout.addWidget(self.edit_prompt_btn)

        # Clear button
        self.clear_prompt_btn = QPushButton("🗑️ Clear Prompt")
        self.clear_prompt_btn.clicked.connect(self.clear_prompt)
        control_layout.addWidget(self.clear_prompt_btn)

        # Reset button (only show if we had an initial prompt)
        if self.initial_prompt:
            self.reset_prompt_btn = QPushButton("↺ Reset to Original")
            self.reset_prompt_btn.clicked.connect(self.reset_prompt)
            control_layout.addWidget(self.reset_prompt_btn)

        control_layout.addStretch()
        prompt_layout.addLayout(control_layout)

        main_layout.addWidget(prompt_group)

        # Question section with quick questions
        question_group = QGroupBox("Your Question")
        question_layout = QVBoxLayout(question_group)

        # Quick questions combo
        self.quick_questions_combo = QComboBox()
        self.update_quick_questions()
        self.quick_questions_combo.currentTextChanged.connect(self.on_quick_question_selected)
        question_layout.addWidget(QLabel("Quick Questions:"))
        question_layout.addWidget(self.quick_questions_combo)

        # Question input
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText(
            "Ask anything about AI image generation, prompts, styles, or just chat..."
        )
        self.question_input.setMaximumHeight(80)
        question_layout.addWidget(self.question_input)

        main_layout.addWidget(question_group)

        # LLM settings (compact)
        settings_group = QGroupBox("AI Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Provider and model row
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.llm_provider_combo = QComboBox()
        provider_layout.addWidget(self.llm_provider_combo)

        provider_layout.addWidget(QLabel("Model:"))
        self.llm_model_combo = QComboBox()
        provider_layout.addWidget(self.llm_model_combo)

        provider_layout.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.setToolTip("Controls creativity (0=focused, 2=creative)")
        provider_layout.addWidget(self.temperature_spin)

        provider_layout.addStretch()
        settings_layout.addLayout(provider_layout)

        # GPT-5 specific params (hidden by default)
        self.gpt5_params_widget = QWidget()
        gpt5_layout = QHBoxLayout(self.gpt5_params_widget)
        gpt5_layout.setContentsMargins(0, 0, 0, 0)

        gpt5_layout.addWidget(QLabel("Reasoning:"))
        self.reasoning_combo = QComboBox()
        self.reasoning_combo.addItems(["low", "medium", "high"])
        self.reasoning_combo.setCurrentText("medium")
        gpt5_layout.addWidget(self.reasoning_combo)

        gpt5_layout.addWidget(QLabel("Verbosity:"))
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItems(["low", "medium", "high"])
        self.verbosity_combo.setCurrentText("medium")
        gpt5_layout.addWidget(self.verbosity_combo)

        gpt5_layout.addStretch()
        settings_layout.addWidget(self.gpt5_params_widget)
        self.gpt5_params_widget.hide()

        main_layout.addWidget(settings_group)

        # Conversation display
        convo_group = QGroupBox("Conversation")
        convo_layout = QVBoxLayout(convo_group)

        self.conversation_display = QTextEdit()
        self.conversation_display.setReadOnly(True)
        self.conversation_display.setPlaceholderText("Your conversation will appear here...")
        convo_layout.addWidget(self.conversation_display)

        # Conversation controls
        convo_controls = QHBoxLayout()
        self.ask_btn = QPushButton("Ask Question")
        self.ask_btn.setToolTip("Ask the AI a question (Ctrl+Enter)")
        self.ask_btn.setDefault(True)
        self.ask_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
            }
        """)
        self.ask_btn.clicked.connect(self.ask_question)
        convo_controls.addWidget(self.ask_btn)

        self.continue_checkbox = QCheckBox("Continue conversation")
        self.continue_checkbox.setChecked(True)
        self.continue_checkbox.setToolTip("Keep conversation context for follow-up questions")
        convo_controls.addWidget(self.continue_checkbox)

        convo_controls.addStretch()

        self.clear_convo_btn = QPushButton("Clear Conversation")
        self.clear_convo_btn.clicked.connect(self.clear_conversation)
        convo_controls.addWidget(self.clear_convo_btn)

        convo_layout.addLayout(convo_controls)

        # Add shortcut hint label
        shortcut_label = QLabel("<small style='color: gray;'>Shortcuts: Ctrl+Enter to ask, Ctrl+E to edit prompt, Esc to close</small>")
        shortcut_label.setAlignment(Qt.AlignCenter)
        convo_layout.addWidget(shortcut_label)

        main_layout.addWidget(convo_group)

        splitter.addWidget(main_widget)

        # Status console with history
        self.status_console = DialogStatusConsole("Status Console", self)
        self.status_console.setMaximumHeight(150)
        splitter.addWidget(self.status_console)

        # Set splitter proportions
        splitter.setSizes([450, 150])

        layout.addWidget(splitter)

        # Connect signals
        self.llm_provider_combo.currentTextChanged.connect(self.update_llm_models)
        self.llm_model_combo.currentTextChanged.connect(self.on_model_changed)
        self.prompt_input.textChanged.connect(self.on_prompt_changed)

        return widget

    def update_quick_questions(self):
        """Update quick questions based on whether there's a prompt."""
        self.quick_questions_combo.clear()

        has_prompt = bool(self.prompt_input.toPlainText().strip())

        if has_prompt:
            # Prompt-specific questions
            questions = [
                "Select a quick question...",
                "How can I make this prompt more detailed?",
                "What style keywords would improve this?",
                "What's missing from this prompt?",
                "How can I improve the composition?",
                "What lighting would work best?",
                "Suggest camera angles for this scene",
                "What color palette would enhance this?",
                "How can I make this more photorealistic?",
                "What artistic style would suit this?",
                "How can I add more emotion/mood?",
                "Rate this prompt and explain why"
            ]
        else:
            # General AI image generation questions
            questions = [
                "Select a quick question...",
                "Give me a creative fantasy scene prompt",
                "What makes a good AI image prompt?",
                "Create a photorealistic portrait prompt",
                "Suggest a sci-fi landscape description",
                "What are effective style keywords?",
                "How do I describe lighting effectively?",
                "Create an abstract art prompt",
                "Suggest a nature scene description",
                "What camera angles work for portraits?",
                "Create a cinematic scene prompt",
                "Explain composition techniques",
                "What are trending art styles?"
            ]

        self.quick_questions_combo.addItems(questions)

    def toggle_prompt_edit(self):
        """Toggle prompt edit mode."""
        if self.edit_prompt_btn.isChecked():
            # Enable editing
            self.prompt_input.setReadOnly(False)
            self.prompt_input.setStyleSheet("")  # Remove gray background
            self.edit_prompt_btn.setText("💾 Save Changes")
            self.prompt_input.setFocus()
            # Store original text for cancel
            self.temp_prompt_text = self.prompt_input.toPlainText()
        else:
            # Disable editing and save changes
            self.prompt_input.setReadOnly(True)
            self.prompt_input.setStyleSheet("QTextEdit[readOnly=\"true\"] { background-color: #f5f5f5; }")
            self.edit_prompt_btn.setText("✏️ Edit Prompt")
            # Trigger update of quick questions
            self.on_prompt_changed()

    def clear_prompt(self):
        """Clear the prompt field."""
        reply = QMessageBox.question(
            self, "Clear Prompt",
            "Are you sure you want to clear the prompt?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.prompt_input.clear()
            self.on_prompt_changed()
            # If in edit mode, exit it
            if self.edit_prompt_btn.isChecked():
                self.edit_prompt_btn.setChecked(False)
                self.toggle_prompt_edit()

    def reset_prompt(self):
        """Reset prompt to original value."""
        if self.initial_prompt:
            self.prompt_input.setPlainText(self.initial_prompt)
            self.on_prompt_changed()
            # If in edit mode, exit it
            if self.edit_prompt_btn.isChecked():
                self.edit_prompt_btn.setChecked(False)
                self.toggle_prompt_edit()

    def on_prompt_changed(self):
        """Handle prompt text changes."""
        # Update quick questions when prompt changes
        self.update_quick_questions()
        # Update current prompt
        self.current_prompt = self.prompt_input.toPlainText().strip()

    def on_quick_question_selected(self, text):
        """Handle quick question selection."""
        if text and text != "Select a quick question...":
            self.question_input.setPlainText(text)

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+Enter to ask
        ask_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        ask_shortcut.activated.connect(self.ask_question)

        # Ctrl+E to toggle edit mode
        edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        edit_shortcut.activated.connect(lambda: self.edit_prompt_btn.click())

        # Escape to close (only if not in edit mode)
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.handle_escape)

    def handle_escape(self):
        """Handle escape key - exit edit mode or close dialog."""
        if self.edit_prompt_btn.isChecked():
            # Exit edit mode without saving
            self.prompt_input.setPlainText(self.temp_prompt_text if hasattr(self, 'temp_prompt_text') else self.prompt_input.toPlainText())
            self.edit_prompt_btn.setChecked(False)
            self.toggle_prompt_edit()
        else:
            # Close dialog
            self.reject()

    def ask_question(self):
        """Process the current question."""
        question = self.question_input.toPlainText().strip()
        if not question:
            QMessageBox.warning(self, "No Question", "Please enter a question.")
            return

        self.current_prompt = self.prompt_input.toPlainText().strip()

        # Get LLM settings
        llm_provider = self.llm_provider_combo.currentText()
        llm_model = self.llm_model_combo.currentText()

        if not llm_provider or not llm_model:
            QMessageBox.warning(self, "LLM Not Configured", "Please select an AI provider and model.")
            return

        # Get API key
        api_key = None
        if self.config:
            if llm_provider.lower() == "openai":
                api_key = self.config.get_api_key('openai')
            elif llm_provider.lower() in ["google", "gemini"]:
                api_key = self.config.get_api_key('google')
            elif llm_provider.lower() in ["anthropic", "claude"]:
                api_key = self.config.get_api_key('anthropic')

        if not api_key:
            QMessageBox.warning(self, "API Key Missing",
                                f"Please configure your {llm_provider} API key in Settings.")
            return

        # Prepare conversation history if continuing
        conv_history = []
        if self.continue_checkbox.isChecked():
            conv_history = self.conversation_history.copy()

        # Disable UI during processing
        self.ask_btn.setEnabled(False)
        self.ask_btn.setText("Processing...")

        # Clear status console
        self.status_console.clear()
        self.status_console.log(f"Asking {llm_provider} {llm_model}...", "INFO")

        # Get temperature
        temperature = self.temperature_spin.value()

        # Get GPT-5 params if needed
        reasoning = "medium"
        verbosity = "medium"
        if self.gpt5_params_widget.isVisible():
            reasoning = self.reasoning_combo.currentText()
            verbosity = self.verbosity_combo.currentText()

        # Create worker thread
        self.thread = QThread()
        self.worker = QuestionWorker(
            self.current_prompt,
            question,
            llm_provider,
            llm_model,
            api_key,
            temperature,
            reasoning,
            verbosity,
            conv_history
        )

        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_answer_received)
        self.worker.error.connect(self.on_error)
        self.worker.progress.connect(lambda msg: self.status_console.log(msg, "INFO"))
        self.worker.log_message.connect(self.status_console.log)

        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)

        # Start the thread
        self.thread.start()

    def on_answer_received(self, answer):
        """Handle received answer."""
        # Update conversation display
        if not self.conversation_display.toPlainText():
            # First message
            if self.current_prompt:
                self.conversation_display.append(f"**Prompt:** {self.current_prompt}\n")
            self.conversation_display.append(f"**Q:** {self.question_input.toPlainText()}")
            self.conversation_display.append(f"**A:** {answer}\n")
        else:
            # Continuation
            self.conversation_display.append(f"**Q:** {self.question_input.toPlainText()}")
            self.conversation_display.append(f"**A:** {answer}\n")

        # Save to conversation history
        entry = {
            'prompt': self.current_prompt if self.current_prompt else None,
            'question': self.question_input.toPlainText(),
            'answer': answer,
            'timestamp': datetime.now().isoformat()
        }
        self.conversation_history.append(entry)

        # Save to history widget
        self.history_widget.add_entry(
            self.question_input.toPlainText(),
            answer,
            self.llm_provider_combo.currentText(),
            self.llm_model_combo.currentText(),
            {'prompt': self.current_prompt} if self.current_prompt else {}
        )

        # Clear question input for next question
        self.question_input.clear()

        # Re-enable UI
        self.ask_btn.setEnabled(True)
        self.ask_btn.setText("Ask Question")

        self.status_console.log("Answer received successfully!", "SUCCESS")

    def on_error(self, error):
        """Handle errors."""
        QMessageBox.critical(self, "Error", error)
        self.status_console.log(f"Error: {error}", "ERROR")

        # Re-enable UI
        self.ask_btn.setEnabled(True)
        self.ask_btn.setText("Ask Question")

    def clear_conversation(self):
        """Clear the conversation history."""
        self.conversation_display.clear()
        self.conversation_history = []
        self.status_console.log("Conversation cleared", "INFO")

    def load_history_item(self, item):
        """Load a history item into the conversation."""
        # Switch to main tab
        self.tab_widget.setCurrentIndex(0)

        # Restore the prompt if available
        if 'metadata' in item and 'prompt' in item['metadata']:
            self.prompt_input.setPlainText(item['metadata']['prompt'])

        # Restore the question
        question = item.get('input', '')
        self.question_input.setPlainText(question)

        # Restore the conversation
        answer = item.get('response', '')
        if answer:
            self.conversation_display.clear()
            self.conversation_display.append(f"**Q:** {question}")
            self.conversation_display.append(f"**A:** {answer}\n")

            # Show in status console
            self.status_console.log("="*60, "INFO")
            self.status_console.log("Restored from history:", "INFO")
            if 'metadata' in item and 'prompt' in item['metadata']:
                self.status_console.log(f"Prompt: {item['metadata']['prompt']}", "INFO")
            self.status_console.log(f"Question: {question}", "INFO")
            self.status_console.log("-"*40, "INFO")
            self.status_console.log(f"Answer:\n{answer}", "SUCCESS")
            self.status_console.log("="*60, "INFO")

            # Show provider info if available
            if 'provider' in item and item['provider']:
                self.status_console.log(f"Provider: {item['provider']} ({item.get('model', 'Unknown')})", "INFO")

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

        self.on_model_changed()

    def on_model_changed(self):
        """Handle model selection change."""
        model = self.llm_model_combo.currentText()
        is_gpt5 = "gpt-5" in model.lower() if model else False

        self.gpt5_params_widget.setVisible(is_gpt5)

        if is_gpt5:
            self.temperature_spin.setEnabled(False)
            self.temperature_spin.setValue(1.0)
            self.temperature_spin.setToolTip("GPT-5 only supports temperature=1")
        else:
            self.temperature_spin.setEnabled(True)
            self.temperature_spin.setToolTip("Controls creativity (0=focused, 2=creative)")

    def save_dialog_settings(self):
        """Save dialog-specific settings."""
        self.settings.setValue("temperature", self.temperature_spin.value())
        self.settings.setValue("continue_conversation", self.continue_checkbox.isChecked())
        self.settings.setValue("reasoning_effort", self.reasoning_combo.currentText())
        self.settings.setValue("verbosity", self.verbosity_combo.currentText())

        # Save current tab
        self.settings.setValue("current_tab", self.tab_widget.currentIndex())

        # Save splitter states
        splitters = self.findChildren(QSplitter)
        if splitters:
            self.settings.setValue("splitter_state", splitters[0].saveState())

        # Save LLM settings
        if self.config:
            self.config.set('llm_provider', self.llm_provider_combo.currentText())
            self.config.set('llm_model', self.llm_model_combo.currentText())

    def restore_dialog_settings(self):
        """Restore dialog-specific settings."""
        temperature = self.settings.value("temperature", type=float)
        if temperature is not None:
            self.temperature_spin.setValue(temperature)

        continue_conv = self.settings.value("continue_conversation", type=bool)
        if continue_conv is not None:
            self.continue_checkbox.setChecked(continue_conv)

        reasoning = self.settings.value("reasoning_effort", "medium")
        index = self.reasoning_combo.findText(reasoning)
        if index >= 0:
            self.reasoning_combo.setCurrentIndex(index)

        verbosity = self.settings.value("verbosity", "medium")
        index = self.verbosity_combo.findText(verbosity)
        if index >= 0:
            self.verbosity_combo.setCurrentIndex(index)

        # Restore tab
        tab_index = self.settings.value("current_tab", type=int)
        if tab_index is not None:
            self.tab_widget.setCurrentIndex(tab_index)

        # Restore splitter
        splitters = self.findChildren(QSplitter)
        if splitters:
            splitter_state = self.settings.value("splitter_state")
            if splitter_state:
                splitters[0].restoreState(splitter_state)

    def save_settings(self):
        """Save window geometry."""
        self.settings.setValue("geometry", self.saveGeometry())

    def restore_settings(self):
        """Restore window geometry."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def reject(self):
        """Override reject to save settings."""
        self.save_dialog_settings()
        self.save_settings()
        super().reject()

    def closeEvent(self, event):
        """Handle close event."""
        if self.worker and self.thread and self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()

        self.save_dialog_settings()
        self.save_settings()
        super().closeEvent(event)