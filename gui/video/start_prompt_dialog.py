"""
Dialog for generating start frame prompts using LLM.

This dialog shows the source text (lyric, narration, or scene description),
and allows the user to generate, edit, and regenerate start frame descriptions.
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QGroupBox, QProgressBar, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from core.video.end_prompt_generator import EndPromptGenerator


class StartPromptGenerationThread(QThread):
    """Thread for generating start prompts without blocking UI"""

    # Signals
    generation_complete = Signal(str)  # Emits generated prompt
    generation_failed = Signal(str)  # Emits error message

    def __init__(
        self,
        generator: EndPromptGenerator,
        source: str,
        current_prompt: str,
        provider: str,
        model: str,
        parent=None
    ):
        super().__init__(parent)
        self.generator = generator
        self.source = source
        self.current_prompt = current_prompt
        self.provider = provider
        self.model = model

    def run(self):
        """Run generation in background"""
        try:
            # Use LiteLLM directly through the generator's provider
            system_prompt = """You are an AI image prompt specialist. Create a detailed, vivid description for generating a single image frame.

The user provides a text line (lyric, narration, or scene description). Generate a comprehensive prompt that:
- Captures the mood, setting, and key visual elements
- Is 1-2 sentences describing what should be visible in the frame
- Focuses on composition, lighting, color palette, and atmosphere
- Is specific and concrete (avoid vague or abstract language)

Format: 1-2 sentences describing the visual scene."""

            current_info = f'"{self.current_prompt}"' if self.current_prompt else "None - generate new"
            user_prompt = f"""Create an image prompt from this text:

Source: "{self.source}"
Current prompt: {current_info}

Generate a detailed visual description suitable for AI image generation."""

            # Use the generator's LLM provider to make the call
            import litellm

            response = litellm.completion(
                model=f"{self.provider}/{self.model}",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )

            prompt = response.choices[0].message.content.strip()

            if prompt:
                self.generation_complete.emit(prompt)
            else:
                self.generation_failed.emit("LLM returned empty response")

        except Exception as e:
            self.generation_failed.emit(str(e))


class StartPromptDialog(QDialog):
    """
    Dialog for generating start frame prompts with LLM.

    Shows source text, current prompt (if any), generates enhanced prompt,
    and allows edit/regenerate/use actions.
    """

    def __init__(
        self,
        generator: EndPromptGenerator,
        source: str,
        current_prompt: str,
        provider: str,
        model: str,
        parent=None
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.source = source
        self.current_prompt = current_prompt
        self.provider = provider
        self.model = model
        self.generation_thread: Optional[StartPromptGenerationThread] = None
        self.generated_prompt: Optional[str] = None

        self.setWindowTitle("Generate Start Frame Prompt with LLM")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)

        self.init_ui()

        # Auto-generate on open
        self.generate_prompt()

    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # Source text section
        source_group = QGroupBox("Source Text")
        source_layout = QVBoxLayout()

        self.source_display = QTextEdit()
        self.source_display.setPlainText(self.source)
        self.source_display.setReadOnly(True)
        self.source_display.setMaximumHeight(80)
        source_layout.addWidget(self.source_display)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # Current prompt section (if exists)
        if self.current_prompt:
            current_group = QGroupBox("Current Prompt")
            current_layout = QVBoxLayout()

            self.current_prompt_display = QTextEdit()
            self.current_prompt_display.setPlainText(self.current_prompt)
            self.current_prompt_display.setReadOnly(True)
            self.current_prompt_display.setMaximumHeight(80)
            current_layout.addWidget(self.current_prompt_display)

            current_group.setLayout(current_layout)
            layout.addWidget(current_group)

        # Generated prompt section
        prompt_group = QGroupBox("Generated Start Prompt")
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
        """Generate start prompt using LLM"""
        # Disable buttons during generation
        self.regenerate_btn.setEnabled(False)
        self.progress_bar.show()

        # Create and start generation thread
        self.generation_thread = StartPromptGenerationThread(
            self.generator,
            self.source,
            self.current_prompt,
            self.provider,
            self.model,
            self
        )
        self.generation_thread.generation_complete.connect(self._on_generation_complete)
        self.generation_thread.generation_failed.connect(self._on_generation_failed)
        self.generation_thread.start()

        self.logger.info(f"Generating start prompt with {self.provider}/{self.model}")

    def _on_generation_complete(self, prompt: str):
        """Handle successful generation"""
        self.generated_prompt = prompt
        self.generated_prompt_edit.setPlainText(prompt)
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.logger.info(f"Start prompt generated: {prompt[:100]}...")

    def _on_generation_failed(self, error: str):
        """Handle generation failure"""
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.generated_prompt_edit.setPlainText(f"Generation failed: {error}\n\nPlease try again or edit manually.")
        self.logger.error(f"Start prompt generation failed: {error}")

    def get_prompt(self) -> str:
        """Get the final prompt (edited or generated)"""
        return self.generated_prompt_edit.toPlainText().strip()
