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
from PySide6.QtCore import Qt, Signal, QThread, QSettings
from PySide6.QtGui import QFont

from core.discord_rpc import discord_rpc, ActivityState
from core.video.video_prompt_generator import VideoPromptGenerator, VideoPromptContext
from gui.llm_utils import DialogStatusConsole
from ..common.dialog_conventions import (
    DialogCleanupMixin, bind_primary_action, persist_splitter,
    restore_splitter, set_default_button, standard_splitter,
)


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


class VideoPromptDialog(DialogCleanupMixin, QDialog):
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
        self.settings = QSettings("ImageAI", "VideoPromptDialog")

        self.setWindowTitle("Generate Video Prompt with LLM")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.init_ui()
        self.restore_window_geometry()

        # Auto-generate on open
        self.generate_prompt()

    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # Vertical splitter: context / generated prompt / status console
        self.main_splitter = standard_splitter(Qt.Vertical, self)

        # Start prompt section
        start_group = QGroupBox("Start Frame Description")
        start_layout = QVBoxLayout()

        self.start_prompt_display = QTextEdit()
        self.start_prompt_display.setPlainText(self.start_prompt)
        self.start_prompt_display.setReadOnly(True)
        self.start_prompt_display.setMinimumHeight(60)
        self.start_prompt_display.setFocusPolicy(Qt.ClickFocus)
        start_layout.addWidget(self.start_prompt_display)

        # Duration display
        duration_label = QLabel(f"Duration: {self.duration:.1f}s")
        duration_label.setStyleSheet("font-weight: bold; margin: 5px;")
        start_layout.addWidget(duration_label)

        start_group.setLayout(start_layout)
        self.main_splitter.addWidget(start_group)

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
        self.main_splitter.addWidget(prompt_group)

        # Status console (LLM request/response traffic)
        self.status_console = DialogStatusConsole("Status Console")
        self.main_splitter.addWidget(self.status_console)

        layout.addWidget(self.main_splitter, stretch=1)

        # Restore splitter proportions, or apply defaults on first run
        if not restore_splitter(self.settings, "main_splitter", self.main_splitter):
            self.main_splitter.setSizes([120, 220, 140])

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

        self.ok_btn = button_box.button(QDialogButtonBox.Ok)
        set_default_button(self, self.ok_btn, focus=False)

        # Ctrl+Enter / Ctrl+Return accepts the dialog (Enter in the prompt
        # edit inserts a newline)
        self._primary_action = bind_primary_action(self, self.accept)

        # Initial focus on the editable prompt, not the read-only context
        self.generated_prompt_edit.setFocus()

    def generate_prompt(self):
        """Generate video prompt using LLM"""
        # Disable buttons during generation - OK must not accept an empty
        # prompt while the thread runs
        self.regenerate_btn.setEnabled(False)
        self.ok_btn.setEnabled(False)
        self._primary_action.set_enabled(False)
        self.progress_bar.show()

        # Log the outgoing request to the status console
        self.status_console.separator()
        self.status_console.log(f"Generating video prompt with {self.provider}/{self.model} (temperature=0.7)")
        self.status_console.log(f"Duration: {self.duration:.1f}s | Camera movements: {self.enable_camera_movements} | Prompt flow: {self.enable_prompt_flow}")
        self.status_console.log(f"Start frame prompt:\n{self.start_prompt}")
        if self.previous_video_prompt:
            self.status_console.log(f"Previous video prompt:\n{self.previous_video_prompt}")

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
        self.ok_btn.setEnabled(True)
        self._primary_action.set_enabled(True)
        self.status_console.log(f"Response received:\n{prompt}", level="SUCCESS")
        self.logger.info(f"Video prompt generated:\n{prompt}")

    def _on_generation_failed(self, error: str):
        """Handle generation failure"""
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.ok_btn.setEnabled(True)
        self._primary_action.set_enabled(True)
        self.generated_prompt_edit.setPlainText(f"Generation failed: {error}\n\nPlease try again or edit manually.")
        self.status_console.log(f"Generation failed: {error}", level="ERROR")
        self.logger.error(f"Video prompt generation failed: {error}")

    def get_prompt(self) -> str:
        """Get the final prompt (edited or generated)"""
        return self.generated_prompt_edit.toPlainText().strip()

    def restore_window_geometry(self):
        """Restore window size and position from settings"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def showEvent(self, event):
        """Handle show event - update Discord presence."""
        super().showEvent(event)
        discord_rpc.update_presence(
            ActivityState.CHATTING_WITH_AI,
            details="Video Prompt"
        )

    def on_dialog_close(self):
        """Cleanup on every exit path (OK, Cancel, Escape, title-bar X)."""
        # Reset Discord presence to IDLE
        discord_rpc.update_presence(ActivityState.IDLE)

        # Persist geometry and splitter proportions
        self.settings.setValue("geometry", self.saveGeometry())
        persist_splitter(self.settings, "main_splitter", self.main_splitter)

        # Stop the generation thread if it is still running
        if self.generation_thread and self.generation_thread.isRunning():
            try:
                self.generation_thread.generation_complete.disconnect()
                self.generation_thread.generation_failed.disconnect()
            except (RuntimeError, TypeError):
                pass  # Signals may already be disconnected
            self.generation_thread.quit()
            if not self.generation_thread.wait(2000):
                self.logger.warning("Video prompt generation thread did not finish in time")
