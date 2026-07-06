"""
Refine Image Dialog for Multi-Turn Image Editing.

Allows users to iteratively refine images using conversational prompts
with Gemini 3 Pro Image (Nano Banana Pro). Uses chat sessions that
automatically handle thought signatures for context preservation.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QThread, QSettings
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QWidget, QMessageBox,
    QFrame, QSizePolicy, QProgressBar
)

from .common.dialog_conventions import (
    DialogCleanupMixin, bind_primary_action, persist_splitter,
    restore_splitter, standard_splitter
)
from .llm_utils import DialogStatusConsole

logger = logging.getLogger(__name__)


class RefineWorker(QThread):
    """Background worker for sending refinement requests."""

    # Signals
    finished = Signal(bytes, str)  # (image_bytes, response_text)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, chat_session, refinement_prompt: str, aspect_ratio: str = None,
                 image_size: str = None):
        """
        Initialize the refine worker.

        Args:
            chat_session: The SDK chat session to use
            refinement_prompt: The user's refinement instructions
            aspect_ratio: Optional aspect ratio for the output
            image_size: Optional image size (1K, 2K, 4K)
        """
        super().__init__()
        self.chat_session = chat_session
        self.refinement_prompt = refinement_prompt
        self.aspect_ratio = aspect_ratio
        self.image_size = image_size

    def run(self):
        """Execute the refinement request."""
        try:
            from google.genai import types

            self.progress.emit("Sending refinement request...")

            # Build config for this refinement
            config_kwargs = {}
            if self.aspect_ratio or self.image_size:
                image_config_kwargs = {}
                if self.aspect_ratio:
                    image_config_kwargs['aspect_ratio'] = self.aspect_ratio
                # Note: image_size may not be supported in ImageConfig
                config_kwargs['image_config'] = types.ImageConfig(**image_config_kwargs)

            # Send message to existing chat session
            if config_kwargs:
                response = self.chat_session.send_message(
                    self.refinement_prompt,
                    config=types.GenerateContentConfig(**config_kwargs)
                )
            else:
                response = self.chat_session.send_message(self.refinement_prompt)

            self.progress.emit("Processing response...")

            # Extract image and text from response
            image_bytes = None
            response_text = ""

            if response and response.candidates:
                for cand in response.candidates:
                    if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                        for part in cand.content.parts:
                            if getattr(part, "text", None):
                                response_text += part.text
                            elif getattr(part, "inline_data", None) is not None:
                                data = getattr(part.inline_data, "data", None)
                                if isinstance(data, (bytes, bytearray)):
                                    image_bytes = bytes(data)

            if image_bytes:
                self.finished.emit(image_bytes, response_text)
            else:
                self.error.emit("No image returned in refinement response")

        except Exception as e:
            logger.error(f"Refinement failed: {e}", exc_info=True)
            self.error.emit(str(e))


class RefineImageDialog(DialogCleanupMixin, QDialog):
    """
    Dialog for iteratively refining images through conversation.

    Uses the stored chat session to maintain context across refinements.
    """

    # Signals
    image_refined = Signal(bytes, str, str)  # (image_bytes, prompt, response_text)

    def __init__(self, conversation, image_bytes: bytes = None,
                 aspect_ratio: str = None, parent=None):
        """
        Initialize the refine image dialog.

        Args:
            conversation: ImageConversation object with chat session
            image_bytes: Current image bytes to display
            aspect_ratio: Current aspect ratio setting
            parent: Parent widget
        """
        super().__init__(parent)
        self.conversation = conversation
        self.current_image_bytes = image_bytes or conversation.current_image_bytes
        self.aspect_ratio = aspect_ratio
        self.worker = None
        self._refine_cancelled = False
        self._original_pixmap = None
        self.settings = QSettings("ImageAI", "RefineImageDialog")

        self.setWindowTitle("Refine Image - Multi-Turn Editing")
        self.setMinimumSize(800, 600)
        self.setModal(False)  # Allow interaction with main window

        self._init_ui()
        self._load_history()
        self._restore_settings()

        # Initial focus goes to the primary input
        self.prompt_input.setFocus()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel(
            "<b>Refine your image with conversational prompts.</b><br>"
            "The AI remembers previous context and can make incremental changes."
        )
        header_label.setWordWrap(True)
        layout.addWidget(header_label)

        # Vertical splitter: main content on top, status console at bottom
        self.console_splitter = standard_splitter(Qt.Vertical)

        # Main splitter: image on left, chat on right
        self.main_splitter = standard_splitter(Qt.Horizontal)
        self.main_splitter.splitterMoved.connect(self._rescale_image)

        # Left side: Image display
        image_frame = QFrame()
        image_frame.setFrameShape(QFrame.StyledPanel)
        image_layout = QVBoxLayout(image_frame)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(300, 300)
        self.image_label.setStyleSheet("background-color: #f0f0f0;")

        # Display current image
        if self.current_image_bytes:
            self._display_image(self.current_image_bytes)
        else:
            self.image_label.setText("No image loaded")

        image_layout.addWidget(self.image_label)

        # Image info
        self.image_info_label = QLabel()
        self.image_info_label.setStyleSheet("color: #666; font-size: 10px;")
        image_layout.addWidget(self.image_info_label)

        self.main_splitter.addWidget(image_frame)

        # Right side: Chat history and input
        chat_frame = QFrame()
        chat_frame.setFrameShape(QFrame.StyledPanel)
        chat_layout = QVBoxLayout(chat_frame)

        # History and input share a user-adjustable vertical splitter
        self.chat_splitter = standard_splitter(Qt.Vertical)

        # Chat history
        history_container = QWidget()
        history_container_layout = QVBoxLayout(history_container)
        history_container_layout.setContentsMargins(0, 0, 0, 0)
        history_container_layout.addWidget(QLabel("<b>Conversation History:</b>"))

        self.history_area = QScrollArea()
        self.history_area.setWidgetResizable(True)
        self.history_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.setAlignment(Qt.AlignTop)
        self.history_area.setWidget(self.history_widget)

        history_container_layout.addWidget(self.history_area, 1)
        self.chat_splitter.addWidget(history_container)

        # Refinement input
        prompt_container = QWidget()
        prompt_container_layout = QVBoxLayout(prompt_container)
        prompt_container_layout.setContentsMargins(0, 0, 0, 0)
        prompt_container_layout.addWidget(QLabel("<b>Refinement Instructions:</b>"))

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            "Describe how you want to modify the image...\n\n"
            "Examples:\n"
            "- Make the background more blue\n"
            "- Add a sunset in the sky\n"
            "- Change the text to say 'Hello World'\n"
            "- Make the person smile more"
        )
        self.prompt_input.setMinimumHeight(80)
        self.prompt_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        prompt_container_layout.addWidget(self.prompt_input, 1)
        self.chat_splitter.addWidget(prompt_container)

        chat_layout.addWidget(self.chat_splitter, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        chat_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666;")
        chat_layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.refine_btn = QPushButton("Refine Image")
        self.refine_btn.setDefault(True)
        self.refine_btn.setToolTip("Refine the image (Ctrl+Enter). Click again while running to stop.")
        self.refine_btn.clicked.connect(self._on_refine_clicked)
        self.refine_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_layout.addWidget(self.refine_btn)

        self.save_btn = QPushButton("Save Image")
        self.save_btn.clicked.connect(self._on_save_clicked)
        button_layout.addWidget(self.save_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        chat_layout.addLayout(button_layout)

        self.main_splitter.addWidget(chat_frame)

        self.console_splitter.addWidget(self.main_splitter)

        # Status console at the bottom (LLM request/response log)
        self.status_console = DialogStatusConsole("Status Console")
        self.console_splitter.addWidget(self.status_console)

        layout.addWidget(self.console_splitter, 1)

        # Primary action: Ctrl+Return AND Ctrl+Enter
        self._primary_action = bind_primary_action(self, self._on_refine_clicked)

    def _restore_settings(self):
        """Restore window geometry and splitter proportions."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        if not restore_splitter(self.settings, "console_splitter", self.console_splitter):
            self.console_splitter.setSizes([500, 150])
        if not restore_splitter(self.settings, "main_splitter", self.main_splitter):
            # 40% image, 60% chat
            self.main_splitter.setSizes([400, 600])
        if not restore_splitter(self.settings, "chat_splitter", self.chat_splitter):
            self.chat_splitter.setSizes([350, 150])

    def on_dialog_close(self):
        """Cleanup on every exit path (Close, Escape, title-bar X)."""
        self.settings.setValue("geometry", self.saveGeometry())
        persist_splitter(self.settings, "console_splitter", self.console_splitter)
        persist_splitter(self.settings, "main_splitter", self.main_splitter)
        persist_splitter(self.settings, "chat_splitter", self.chat_splitter)

        # Stop the refine worker if it is still running
        if self.worker and self.worker.isRunning():
            self._refine_cancelled = True
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
                self.worker.progress.disconnect()
            except (RuntimeError, TypeError):
                pass  # Signals may already be disconnected
            self.worker.quit()
            if not self.worker.wait(2000):
                logger.warning("Refine worker did not finish in time")

    def _display_image(self, image_bytes: bytes):
        """Display image bytes in the image label."""
        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)

        if not pixmap.isNull():
            # Keep the original for rescaling on resize/splitter moves
            self._original_pixmap = pixmap
            self._rescale_image()

            # Update info label
            self.image_info_label.setText(
                f"Size: {pixmap.width()}x{pixmap.height()} | "
                f"Refinements: {self.conversation.get_message_count() // 2}"
            )

    def _rescale_image(self, *args):
        """Rescale the displayed pixmap to the label size (scaled, never cropped)."""
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return
        scaled = self._original_pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale_image()

    def _load_history(self):
        """Load conversation history into the chat display."""
        # Clear existing history
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add messages
        for msg in self.conversation.messages:
            self._add_history_message(msg['role'], msg['content'], msg.get('has_image', False))

    def _add_history_message(self, role: str, content: str, has_image: bool = False):
        """Add a message to the history display."""
        msg_frame = QFrame()
        msg_frame.setFrameShape(QFrame.StyledPanel)

        if role == 'user':
            msg_frame.setStyleSheet("""
                QFrame {
                    background-color: #e3f2fd;
                    border-radius: 8px;
                    margin: 4px;
                    padding: 8px;
                }
            """)
        else:
            msg_frame.setStyleSheet("""
                QFrame {
                    background-color: #f5f5f5;
                    border-radius: 8px;
                    margin: 4px;
                    padding: 8px;
                }
            """)

        msg_layout = QVBoxLayout(msg_frame)
        msg_layout.setContentsMargins(8, 4, 8, 4)

        # Role label
        role_label = QLabel(f"<b>{'You' if role == 'user' else 'AI'}:</b>")
        msg_layout.addWidget(role_label)

        # Content
        content_label = QLabel(content[:200] + "..." if len(content) > 200 else content)
        content_label.setWordWrap(True)
        if len(content) > 200:
            # Full text available on hover for truncated messages
            content_label.setToolTip(content)
        msg_layout.addWidget(content_label)

        # Image indicator
        if has_image:
            img_indicator = QLabel("[Image generated]")
            img_indicator.setStyleSheet("color: #4CAF50; font-style: italic;")
            msg_layout.addWidget(img_indicator)

        self.history_layout.addWidget(msg_frame)

        # Scroll to bottom
        self.history_area.verticalScrollBar().setValue(
            self.history_area.verticalScrollBar().maximum()
        )

    def _on_refine_clicked(self):
        """Refine button dispatcher: refine normally, Stop while running."""
        if self.worker and self.worker.isRunning():
            self._cancel_refine()
            return

        prompt = self.prompt_input.toPlainText().strip()

        if not prompt:
            QMessageBox.warning(self, "Empty Prompt", "Please enter refinement instructions.")
            return

        if not self.conversation.has_chat_session():
            QMessageBox.warning(
                self, "No Chat Session",
                "This conversation does not have an active chat session.\n"
                "Multi-turn refinement requires the original chat session to be preserved."
            )
            return

        # Repurpose the Refine button as Stop while the worker runs
        self._refine_cancelled = False
        self.refine_btn.setText("Stop")
        self.prompt_input.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        # Add user message to history immediately
        self._add_history_message('user', prompt)
        self.conversation.add_message('user', prompt)

        # Log the outgoing request to the status console
        self.status_console.separator()
        self.status_console.log(
            f"Refinement request (aspect_ratio={self.aspect_ratio or 'unchanged'}):\n{prompt}"
        )

        # Start worker
        self.worker = RefineWorker(
            chat_session=self.conversation.get_chat_session(),
            refinement_prompt=prompt,
            aspect_ratio=self.aspect_ratio
        )
        self.worker.finished.connect(self._on_refine_finished)
        self.worker.error.connect(self._on_refine_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.start()

    def _cancel_refine(self):
        """Stop an in-flight refinement at the user's request."""
        self._refine_cancelled = True
        self.status_console.log("Refinement stopped by user", "WARNING")
        self._reset_refine_ui("Refinement stopped")

    def _reset_refine_ui(self, status: str = ""):
        """Restore the input/button state after a run (or a Stop)."""
        self.refine_btn.setText("Refine Image")
        self.prompt_input.setEnabled(True)
        self.progress_bar.setVisible(False)
        if status:
            self.status_label.setText(status)

    def _on_progress(self, message: str):
        """Handle progress updates."""
        self.status_label.setText(message)
        self.status_console.log(message)

    def _on_refine_finished(self, image_bytes: bytes, response_text: str):
        """Handle successful refinement."""
        if self._refine_cancelled:
            return  # User stopped this run; drop the late result

        self.status_console.log(
            f"Response received:\n{response_text or 'Image refined'}", "SUCCESS"
        )

        # Update conversation
        self.conversation.add_message('model', response_text or 'Image refined', image_bytes)

        # Update display
        self.current_image_bytes = image_bytes
        self._display_image(image_bytes)
        self._add_history_message('model', response_text or 'Image refined', True)

        # Clear input and re-enable UI
        self.prompt_input.clear()
        self._reset_refine_ui("Refinement complete!")

        # Emit signal for main window
        prompt = self.prompt_input.toPlainText() or self.conversation.messages[-2]['content']
        self.image_refined.emit(image_bytes, prompt, response_text)

    def _on_refine_error(self, error: str):
        """Handle refinement error."""
        if self._refine_cancelled:
            return  # User stopped this run; drop the late error

        self.status_console.log(f"Refinement failed: {error}", "ERROR")
        self._reset_refine_ui(f"Error: {error}")

        QMessageBox.critical(self, "Refinement Failed", f"Failed to refine image:\n{error}")

    def _on_save_clicked(self):
        """Handle save button click."""
        if not self.current_image_bytes:
            QMessageBox.warning(self, "No Image", "No image to save.")
            return

        from PySide6.QtWidgets import QFileDialog

        # Get save path
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Refined Image", "",
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*.*)"
        )

        if file_path:
            try:
                Path(file_path).write_bytes(self.current_image_bytes)
                self.status_label.setText(f"Saved to: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Failed to save image:\n{e}")
