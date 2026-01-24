"""
Dialog for generating video prompts using LLM.

This dialog takes a start frame prompt and generates motion/camera instructions
optimized for Google Veo video generation.
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QGroupBox, QProgressBar, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from core.discord_rpc import discord_rpc, ActivityState
from core.video.video_prompt_generator import VideoPromptGenerator, VideoPromptContext


class VideoPromptGenerationThread(QThread):
    """Thread for generating video prompts without blocking UI"""

    # Signals
    generation_complete = Signal(str)  # Emits generated prompt
    generation_failed = Signal(str)  # Emits error message

    def __init__(
        self,
        generator: VideoPromptGenerator,
        start_prompt: str,
        duration: float,
        provider: str,
        model: str,
        enable_camera_movements: bool = True,
        enable_prompt_flow: bool = False,
        previous_video_prompt: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.generator = generator
        self.start_prompt = start_prompt
        self.duration = duration
        self.provider = provider
        self.model = model
        self.enable_camera_movements = enable_camera_movements
        self.enable_prompt_flow = enable_prompt_flow
        self.previous_video_prompt = previous_video_prompt

    def run(self):
        """Run generation in background"""
        try:
            # Create context for generation
            context = VideoPromptContext(
                start_prompt=self.start_prompt,
                duration=self.duration,
                enable_camera_movements=self.enable_camera_movements,
                enable_prompt_flow=self.enable_prompt_flow,
                previous_video_prompt=self.previous_video_prompt
            )

            # Use the generator to create the video prompt
            prompt = self.generator.generate_video_prompt(
                context=context,
                provider=self.provider,
                model=self.model,
                temperature=0.7
            )

            if prompt:
                self.generation_complete.emit(prompt)
            else:
                self.generation_failed.emit("LLM returned empty response")

        except Exception as e:
            self.generation_failed.emit(str(e))


class VideoPromptDialog(QDialog):
    """
    Dialog for generating video prompts with LLM.

    Takes start frame prompt and generates motion/camera instructions for Veo.
    Shows: start prompt, duration, generates video-optimized prompt.
    """

    def __init__(
        self,
        generator: VideoPromptGenerator,
        start_prompt: str,
        duration: float,
        provider: str,
        model: str,
        enable_camera_movements: bool = True,
        enable_prompt_flow: bool = False,
        previous_video_prompt: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.start_prompt = start_prompt
        self.duration = duration
        self.provider = provider
        self.model = model
        self.enable_camera_movements = enable_camera_movements
        self.enable_prompt_flow = enable_prompt_flow
        self.previous_video_prompt = previous_video_prompt
        self.generation_thread: Optional[VideoPromptGenerationThread] = None
        self.generated_prompt: Optional[str] = None

        self.setWindowTitle("Generate Video Prompt with LLM")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.init_ui()

        # Auto-generate on open
        self.generate_prompt()

    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # Start prompt section
        start_group = QGroupBox("Start Frame Description")
        start_layout = QVBoxLayout()

        self.start_prompt_display = QTextEdit()
        self.start_prompt_display.setPlainText(self.start_prompt)
        self.start_prompt_display.setReadOnly(True)
        self.start_prompt_display.setMaximumHeight(80)
        start_layout.addWidget(self.start_prompt_display)

        start_group.setLayout(start_layout)
        layout.addWidget(start_group)

        # Duration display
        duration_label = QLabel(f"Duration: {self.duration:.1f}s")
        duration_label.setStyleSheet("font-weight: bold; margin: 5px;")
        layout.addWidget(duration_label)

        # Generated video prompt section
        prompt_group = QGroupBox("Generated Video Prompt")
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
        """Generate video prompt using LLM"""
        # Disable buttons during generation
        self.regenerate_btn.setEnabled(False)
        self.progress_bar.show()

        # Create and start generation thread
        self.generation_thread = VideoPromptGenerationThread(
            self.generator,
            self.start_prompt,
            self.duration,
            self.provider,
            self.model,
            self.enable_camera_movements,
            self.enable_prompt_flow,
            self.previous_video_prompt,
            self
        )
        self.generation_thread.generation_complete.connect(self._on_generation_complete)
        self.generation_thread.generation_failed.connect(self._on_generation_failed)
        self.generation_thread.start()

        self.logger.info(f"Generating video prompt with {self.provider}/{self.model}")

    def _on_generation_complete(self, prompt: str):
        """Handle successful generation"""
        self.generated_prompt = prompt
        self.generated_prompt_edit.setPlainText(prompt)
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.logger.info(f"Video prompt generated:\n{prompt}")

    def _on_generation_failed(self, error: str):
        """Handle generation failure"""
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.generated_prompt_edit.setPlainText(f"Generation failed: {error}\n\nPlease try again or edit manually.")
        self.logger.error(f"Video prompt generation failed: {error}")

    def get_prompt(self) -> str:
        """Get the final prompt (edited or generated)"""
        return self.generated_prompt_edit.toPlainText().strip()

    def showEvent(self, event):
        """Handle show event - update Discord presence."""
        super().showEvent(event)
        discord_rpc.update_presence(
            ActivityState.CHATTING_WITH_AI,
            details="Video Prompt"
        )

    def closeEvent(self, event):
        """Handle close event."""
        # Reset Discord presence to IDLE
        discord_rpc.update_presence(ActivityState.IDLE)
        super().closeEvent(event)
