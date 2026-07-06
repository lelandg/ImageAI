"""
Dialog for generating start frame prompts using LLM.

This dialog shows the source text (lyric, narration, or scene description),
and allows the user to generate, edit, and regenerate start frame descriptions.
Supports visual continuity by analyzing previous frame for style or transitions.
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QGroupBox, QProgressBar, QDialogButtonBox, QWidget
)
from PySide6.QtCore import Qt, Signal, QThread, QSettings
from PySide6.QtGui import QFont

from core.video.end_prompt_generator import EndPromptGenerator
from core.video.style_analyzer import StyleAnalyzer, ContinuityMode
from core.discord_rpc import discord_rpc, ActivityState
from gui.llm_utils import DialogStatusConsole
from ..common.dialog_conventions import (
    DialogCleanupMixin, bind_primary_action, persist_splitter,
    restore_splitter, set_default_button, standard_splitter,
)


class StartPromptGenerationThread(QThread):
    """Thread for generating start prompts without blocking UI"""

    # Signals
    generation_complete = Signal(str)  # Emits generated prompt
    generation_failed = Signal(str)  # Emits error message
    progress_update = Signal(str)  # Emits progress messages

    def __init__(
        self,
        generator: EndPromptGenerator,
        source: str,
        current_prompt: str,
        provider: str,
        model: str,
        api_key: str,
        continuity_mode: ContinuityMode = ContinuityMode.NONE,
        previous_frame_path: Optional[Path] = None,
        parent=None
    ):
        super().__init__(parent)
        self.generator = generator
        self.source = source
        self.current_prompt = current_prompt
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.continuity_mode = continuity_mode
        self.previous_frame_path = previous_frame_path
        self.logger = logging.getLogger(__name__)

    def run(self):
        """Run generation in background"""
        try:
            # Step 1: Analyze previous frame if continuity mode is enabled
            style_info = None
            if self.continuity_mode != ContinuityMode.NONE and self.previous_frame_path:
                self.progress_update.emit("Analyzing previous frame for continuity...")
                self.logger.info(f"Analyzing previous frame: {self.previous_frame_path}")

                try:
                    analyzer = StyleAnalyzer(
                        api_key=self.api_key,
                        llm_provider=self.provider,
                        llm_model=self.model
                    )

                    if self.continuity_mode == ContinuityMode.STYLE_ONLY:
                        self.logger.info("Using STYLE_ONLY mode - extracting visual style")
                        style_info = analyzer.analyze_for_style(self.previous_frame_path)
                    elif self.continuity_mode == ContinuityMode.TRANSITION:
                        self.logger.info("Using TRANSITION mode - creating smooth continuation")
                        style_info = analyzer.analyze_for_transition(
                            self.previous_frame_path,
                            self.source
                        )

                    if style_info:
                        self.logger.info(f"Style analysis result (FULL, {len(style_info)} chars):")
                        self.logger.info(style_info)
                        self.progress_update.emit("Previous frame analyzed - generating prompt...")
                    else:
                        self.logger.warning("Style analysis returned no result")
                        self.progress_update.emit("Style analysis failed - using source text only...")

                except Exception as e:
                    self.logger.error(f"Style analysis failed: {e}")
                    self.progress_update.emit(f"Style analysis error: {str(e)} - continuing without it...")
                    style_info = None

            # Step 2: Generate prompt with or without style info
            self.progress_update.emit("Generating image prompt...")

            if style_info and self.continuity_mode == ContinuityMode.TRANSITION:
                # For transition mode, the style_info already contains the full prompt
                self.logger.info("Using transition analysis result directly as prompt")
                prompt = style_info
            else:
                # Generate prompt with optional style guidance
                prompt = self._generate_prompt_with_style(style_info)

            if prompt:
                self.generation_complete.emit(prompt)
            else:
                self.generation_failed.emit("LLM returned empty response")

        except Exception as e:
            self.logger.error(f"Start prompt generation failed: {e}")
            self.generation_failed.emit(str(e))

    def _generate_prompt_with_style(self, style_info: Optional[str]) -> str:
        """Generate image prompt, optionally incorporating style information."""

        # Build system prompt
        if style_info:
            system_prompt = """You are an AI image prompt specialist. Create a detailed, vivid description for generating a single image frame.

The user provides a text line (lyric, narration, or scene description) AND visual style guidance from a previous frame.
Your task is to create a prompt that:
- Incorporates the scene content from the source text
- Maintains the visual style from the style guidance
- Creates visual continuity with the previous frame
- Is 1-2 sentences describing what should be visible in the frame
- Focuses on composition, lighting, color palette, and atmosphere
- Is specific and concrete (avoid vague or abstract language)

Format: 1-2 sentences describing the visual scene with the specified style."""
        else:
            system_prompt = """You are an AI image prompt specialist. Create a detailed, vivid description for generating a single image frame.

The user provides a text line (lyric, narration, or scene description). Generate a comprehensive prompt that:
- Captures the mood, setting, and key visual elements
- Is 1-2 sentences describing what should be visible in the frame
- Focuses on composition, lighting, color palette, and atmosphere
- Is specific and concrete (avoid vague or abstract language)

Format: 1-2 sentences describing the visual scene."""

        # Build user prompt
        current_info = f'"{self.current_prompt}"' if self.current_prompt else "None - generate new"

        if style_info:
            user_prompt = f"""Create an image prompt from this text, maintaining the visual style:

Source Text: "{self.source}"
Style Guidance: {style_info}
Current prompt: {current_info}

Generate a detailed visual description that incorporates BOTH the source content AND the style guidance."""
        else:
            user_prompt = f"""Create an image prompt from this text:

Source: "{self.source}"
Current prompt: {current_info}

Generate a detailed visual description suitable for AI image generation."""

        # Use LiteLLM to make the call
        import litellm
        litellm.drop_params = True

        self.logger.info(f"Calling LLM with provider={self.provider}, model={self.model}")
        self.logger.info(f"User prompt: {user_prompt}")

        response = litellm.completion(
            model=f"{self.provider}/{self.model}",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            api_key=self.api_key
        )

        prompt = response.choices[0].message.content.strip()
        self.logger.info(f"Generated prompt: {prompt}")

        return prompt


class StartPromptDialog(DialogCleanupMixin, QDialog):
    """
    Dialog for generating start frame prompts with LLM.

    Shows source text, current prompt (if any), generates enhanced prompt,
    and allows edit/regenerate/use actions.
    Supports visual continuity from previous frame.
    """

    def __init__(
        self,
        generator: EndPromptGenerator,
        source: str,
        current_prompt: str,
        provider: str,
        model: str,
        api_key: str,
        continuity_mode: ContinuityMode = ContinuityMode.NONE,
        previous_frame_path: Optional[Path] = None,
        parent=None
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.source = source
        self.current_prompt = current_prompt
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.continuity_mode = continuity_mode
        self.previous_frame_path = previous_frame_path
        self.generation_thread: Optional[StartPromptGenerationThread] = None
        self.generated_prompt: Optional[str] = None
        self.settings = QSettings("ImageAI", "StartPromptDialog")

        self.setWindowTitle("Generate Start Frame Prompt with LLM")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)

        self.init_ui()
        self.restore_window_geometry()

        # Auto-generate on open
        self.generate_prompt()

    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # Vertical splitter: context / generated prompt / status console
        self.main_splitter = standard_splitter(Qt.Vertical, self)

        # Context pane: source text (+ continuity info, current prompt)
        context_widget = QWidget()
        context_layout = QVBoxLayout(context_widget)
        context_layout.setContentsMargins(0, 0, 0, 0)

        # Source text section
        source_group = QGroupBox("Source Text")
        source_layout = QVBoxLayout()

        self.source_display = QTextEdit()
        self.source_display.setPlainText(self.source)
        self.source_display.setReadOnly(True)
        self.source_display.setMinimumHeight(60)
        self.source_display.setFocusPolicy(Qt.ClickFocus)
        source_layout.addWidget(self.source_display)

        source_group.setLayout(source_layout)
        context_layout.addWidget(source_group)

        # Show continuity info if enabled
        if self.continuity_mode != ContinuityMode.NONE:
            continuity_info = QLabel(f"ℹ️ Continuity mode: {self._get_mode_display_name(self.continuity_mode)}")
            continuity_info.setStyleSheet("QLabel { color: #0066cc; font-style: italic; padding: 5px; }")
            context_layout.addWidget(continuity_info)

        # Current prompt section (if exists)
        if self.current_prompt:
            current_group = QGroupBox("Current Prompt")
            current_layout = QVBoxLayout()

            self.current_prompt_display = QTextEdit()
            self.current_prompt_display.setPlainText(self.current_prompt)
            self.current_prompt_display.setReadOnly(True)
            self.current_prompt_display.setMinimumHeight(60)
            self.current_prompt_display.setFocusPolicy(Qt.ClickFocus)
            current_layout.addWidget(self.current_prompt_display)

            current_group.setLayout(current_layout)
            context_layout.addWidget(current_group)

        self.main_splitter.addWidget(context_widget)

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
        self.main_splitter.addWidget(prompt_group)

        # Status console (LLM request/response traffic + progress)
        self.status_console = DialogStatusConsole("Status Console")
        self.main_splitter.addWidget(self.status_console)

        layout.addWidget(self.main_splitter, stretch=1)

        # Restore splitter proportions, or apply defaults on first run
        if not restore_splitter(self.settings, "main_splitter", self.main_splitter):
            self.main_splitter.setSizes([150, 220, 140])

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

        # Initial focus on the editable prompt, not the read-only source
        self.generated_prompt_edit.setFocus()

    def generate_prompt(self):
        """Generate start prompt using LLM"""
        # Disable buttons during generation - OK must not accept an empty
        # prompt while the thread runs
        self.regenerate_btn.setEnabled(False)
        self.ok_btn.setEnabled(False)
        self._primary_action.set_enabled(False)
        self.progress_bar.show()

        # Log generation parameters (file log + status console)
        self.logger.info(f"Generating start prompt with {self.provider}/{self.model}")
        self.logger.info(f"Continuity mode: {self.continuity_mode.value}")
        if self.previous_frame_path:
            self.logger.info(f"Previous frame: {self.previous_frame_path}")

        self.status_console.separator()
        self.status_console.log(f"Generating start prompt with {self.provider}/{self.model}")
        self.status_console.log(f"Continuity mode: {self._get_mode_display_name(self.continuity_mode)}")
        if self.previous_frame_path:
            self.status_console.log(f"Previous frame: {self.previous_frame_path}")
        self.status_console.log(f"Source text:\n{self.source}")
        if self.current_prompt:
            self.status_console.log(f"Current prompt:\n{self.current_prompt}")

        # Create and start generation thread
        self.generation_thread = StartPromptGenerationThread(
            self.generator,
            self.source,
            self.current_prompt,
            self.provider,
            self.model,
            self.api_key,
            self.continuity_mode,
            self.previous_frame_path,
            self
        )
        self.generation_thread.generation_complete.connect(self._on_generation_complete)
        self.generation_thread.generation_failed.connect(self._on_generation_failed)
        self.generation_thread.progress_update.connect(self._on_progress_update)
        self.generation_thread.start()

    def _on_progress_update(self, message: str):
        """Handle progress updates from generation thread."""
        self.logger.info(f"Progress: {message}")
        self.status_console.log(message)

    def _get_mode_display_name(self, mode: ContinuityMode) -> str:
        """Get display name for continuity mode."""
        names = {
            ContinuityMode.NONE: "None",
            ContinuityMode.STYLE_ONLY: "Style Only",
            ContinuityMode.TRANSITION: "Transition"
        }
        return names.get(mode, "Unknown")

    def _on_generation_complete(self, prompt: str):
        """Handle successful generation"""
        self.generated_prompt = prompt
        self.generated_prompt_edit.setPlainText(prompt)
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.ok_btn.setEnabled(True)
        self._primary_action.set_enabled(True)
        # Change button text back to "Regenerate" after first generation
        self.regenerate_btn.setText("🔄 Regenerate")
        self.status_console.log(f"Response received:\n{prompt}", level="SUCCESS")
        self.logger.info(f"Start prompt generated:\n{prompt}")

    def _on_generation_failed(self, error: str):
        """Handle generation failure"""
        self.progress_bar.hide()
        self.regenerate_btn.setEnabled(True)
        self.ok_btn.setEnabled(True)
        self._primary_action.set_enabled(True)
        self.status_console.log(f"Generation failed: {error}", level="ERROR")
        # Keep button as "Generate" if it was the first attempt, or change to "Regenerate"
        if self.generated_prompt is None:
            self.regenerate_btn.setText("🎨 Generate")
        else:
            self.regenerate_btn.setText("🔄 Regenerate")
        self.generated_prompt_edit.setPlainText(f"Generation failed: {error}\n\nPlease try again or edit manually.")
        self.logger.error(f"Start prompt generation failed: {error}")

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
            details="Start Frame Prompt"
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
                self.generation_thread.progress_update.disconnect()
            except (RuntimeError, TypeError):
                pass  # Signals may already be disconnected
            self.generation_thread.quit()
            if not self.generation_thread.wait(2000):
                self.logger.warning("Start prompt generation thread did not finish in time")
