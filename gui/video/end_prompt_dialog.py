"""
Dialog for generating end frame prompts using LLM.

This dialog shows the current scene, next scene (if exists), and allows
the user to generate, edit, and regenerate end frame descriptions.
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QGroupBox, QProgressBar, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from core.video.end_prompt_generator import EndPromptGenerator, EndPromptContext


class EndPromptGenerationThread(QThread):
    """Thread for generating end prompts without blocking UI"""

    # Signals
    generation_complete = Signal(str)  # Emits generated prompt
    generation_failed = Signal(str)  # Emits error message

    def __init__(
        self,
        generator: EndPromptGenerator,
        context: EndPromptContext,
        provider: str,
        model: str,
        parent=None
    ):
        super().__init__(parent)
        self.generator = generator
        self.context = context
        self.provider = provider
        self.model = model

    def run(self):
        """Run generation in background"""
        try:
            prompt = self.generator.generate_end_prompt(
                self.context,
                provider=self.provider,
                model=self.model
            )

            if prompt:
                self.generation_complete.emit(prompt)
            else:
                self.generation_failed.emit("LLM returned empty response")

        except Exception as e:
            self.generation_failed.emit(str(e))


class EndPromptDialog(QDialog):
    """
    Dialog for generating end frame prompts with LLM.

    Shows context (start prompt, next scene), generates prompt,
    and allows edit/regenerate/use actions.
    """

    def __init__(
        self,
        generator: EndPromptGenerator,
        start_prompt: str,
        next_start_prompt: Optional[str],
        duration: float,
        provider: str,
        model: str,
        parent=None
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.start_prompt = start_prompt
        self.next_start_prompt = next_start_prompt
        self.duration = duration
        self.provider = provider
        self.model = model
        self.generation_thread: Optional[EndPromptGenerationThread] = None
        self.generated_prompt: Optional[str] = None

        self.setWindowTitle("Generate End Frame Prompt with LLM")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self.init_ui()

        # Auto-generate on open
        self.generate_prompt()

    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # Context section
        context_group = QGroupBox("Scene Context")
        context_layout = QVBoxLayout()

        # Current scene (start)
        start_label = QLabel("Current scene (start):")
        start_label.setStyleSheet("font-weight: bold;")
        context_layout.addWidget(start_label)

        self.start_prompt_display = QTextEdit()
        self.start_prompt_display.setPlainText(self.start_prompt)
        self.start_prompt_display.setReadOnly(True)
        self.start_prompt_display.setMaximumHeight(80)
        context_layout.addWidget(self.start_prompt_display)

        # Next scene
        if self.next_start_prompt:
            next_label = QLabel("Next scene (target):")
            next_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            context_layout.addWidget(next_label)

            self.next_prompt_display = QTextEdit()
            self.next_prompt_display.setPlainText(self.next_start_prompt)
            self.next_prompt_display.setReadOnly(True)
            self.next_prompt_display.setMaximumHeight(80)
            context_layout.addWidget(self.next_prompt_display)
        else:
            no_next_label = QLabel("(No next scene - will generate standalone ending)")
            no_next_label.setStyleSheet("font-style: italic; color: #666; margin-top: 10px;")
            context_layout.addWidget(no_next_label)

        context_group.setLayout(context_layout)
        layout.addWidget(context_group)

        # Generated prompt section
        prompt_group = QGroupBox("Generated End Prompt")
        prompt_layout = QVBoxLayout()

        self.generated_prompt_edit = QTextEdit()
        self.generated_prompt_edit.setPlaceholderText("Generating...")
        self.generated_prompt_edit.setMinimumHeight(120)
        prompt_layout.addWidget(self.generated_prompt_edit)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        prompt_layout.addWidget(self.progress_bar)

        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        # Action buttons
        action_layout = QHBoxLayout()

        self.regenerate_btn = QPushButton("🔄 Regenerate")
        self.regenerate_btn.setToolTip("Generate a new variation")
        self.regenerate_btn.clicked.connect(self.generate_prompt)
        action_layout.addWidget(self.regenerate_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def generate_prompt(self):
        """Generate end prompt using LLM"""
        # Disable buttons during generation
        self.regenerate_btn.setEnabled(False)
        self.progress_bar.show()

        # Create context
        context = EndPromptContext(
            start_prompt=self.start_prompt,
            next_start_prompt=self.next_start_prompt,
            duration=self.duration
        )

        # Create and start generation thread
        self.generation_thread = EndPromptGenerationThread(
            self.generator,
            context,
            self.provider,
            self.model,
            self
        )
        self.generation_thread.generation_complete.connect(self._on_generation_complete)
        self.generation_thread.generation_failed.connect(self._on_generation_failed)
        self.generation_thread.start()

        self.logger.info(f"Generating end prompt with {self.provider}/{self.model}")

    def _on_generation_complete(self, prompt: str):
        """Handle successful generation"""
        self.generated_prompt = prompt
        self.generated_prompt_edit.setPlainText(prompt)
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.logger.info(f"End prompt generated: {prompt[:100]}...")

    def _on_generation_failed(self, error: str):
        """Handle generation failure"""
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.generated_prompt_edit.setPlainText(f"Generation failed: {error}\n\nPlease try again or edit manually.")
        self.logger.error(f"End prompt generation failed: {error}")

    def get_prompt(self) -> str:
        """Get the final prompt (edited or generated)"""
        return self.generated_prompt_edit.toPlainText().strip()
