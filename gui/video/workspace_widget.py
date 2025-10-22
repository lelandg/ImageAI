"""
Workspace widget for video project - main working area.

This module contains the main workspace UI that was previously
in video_project_tab.py, now separated for tab organization.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import textwrap
import os

# Suppress FFmpeg/codec console warnings (aac, h264, etc.)
os.environ.setdefault('QTAV_FFMPEG_LOG', '0')
os.environ.setdefault('QT_LOGGING_RULES', '*.debug=false;qt.multimedia.ffmpeg.warning=false')

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QSplitter, QProgressBar,
    QCheckBox, QSlider, QHeaderView, QSizePolicy, QDialog,
    QDialogButtonBox, QListWidget, QListWidgetItem, QInputDialog
)
from PySide6.QtCore import Qt, Signal, Slot, QEvent, QPoint, QTimer, QUrl
from PySide6.QtGui import QPixmap, QImage, QTextOption, QColor, QCursor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from core.config import ConfigManager
from core.video.project import VideoProject, Scene
from core.video.project_manager import ProjectManager
from core.video.storyboard import StoryboardGenerator
from core.video.config import VideoConfig
from core.security import SecureKeyStorage
from gui.common.dialog_manager import get_dialog_manager
from gui.video.wizard_widget import WorkflowWizardWidget
from gui.video.frame_button import FrameButton
from gui.video.video_button import VideoButton
from gui.video.end_prompt_dialog import EndPromptDialog
from gui.video.prompt_field_widget import PromptFieldWidget
from gui.video.reference_images_widget import ReferenceImagesWidget
from core.video.end_prompt_generator import EndPromptGenerator, EndPromptContext
from core.llm_models import get_provider_models, get_all_provider_ids, get_provider_display_name


class ImageHoverPreview(QLabel):
    """A popup label that shows full-size image preview on hover"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #333;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        self.setScaledContents(True)
        self.hide()

    def show_preview(self, image_path: str, cursor_pos: QPoint):
        """Show preview at cursor position"""
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                return

            # Scale down if image is too large (max 800x600)
            max_width = 800
            max_height = 600
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            self.setPixmap(pixmap)
            self.adjustSize()

            # Position the preview near cursor but ensure it stays on screen
            from PySide6.QtWidgets import QApplication
            screen_geometry = QApplication.primaryScreen().geometry()
            x = cursor_pos.x() + 20
            y = cursor_pos.y() + 20

            # Adjust if preview would go off screen
            if x + self.width() > screen_geometry.right():
                x = cursor_pos.x() - self.width() - 20
            if y + self.height() > screen_geometry.bottom():
                y = cursor_pos.y() - self.height() - 20

            self.move(x, y)
            self.show()
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to show image preview: {e}")


class ManageStylesDialog(QDialog):
    """Dialog for managing custom prompt styles"""

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Manage Custom Styles")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)

        # Instructions
        info_label = QLabel("Manage your custom prompt styles. Built-in styles cannot be edited.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._edit_style)
        layout.addWidget(self.list_widget)

        # Buttons
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._add_style)
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_style)
        button_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_style)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

        # Load styles
        self._load_styles()

        # Update button states
        self.list_widget.itemSelectionChanged.connect(self._update_buttons)
        self._update_buttons()

    def _load_styles(self):
        """Load custom styles into the list"""
        self.list_widget.clear()
        custom_styles = self.config.get('custom_prompt_styles', [])
        for style in custom_styles:
            self.list_widget.addItem(style)

    def _update_buttons(self):
        """Update button states based on selection"""
        has_selection = bool(self.list_widget.selectedItems())
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _add_style(self):
        """Add a new custom style"""
        text, ok = QInputDialog.getText(
            self, "Add Custom Style", "Enter style name:",
            QLineEdit.Normal, ""
        )
        if ok and text.strip():
            text = text.strip()
            # Check for duplicates
            custom_styles = self.config.get('custom_prompt_styles', [])
            if text in custom_styles:
                QMessageBox.warning(self, "Duplicate", f"Style '{text}' already exists.")
                return

            # Add to config
            custom_styles.append(text)
            self.config.set('custom_prompt_styles', custom_styles)
            self.config.save()

            # Refresh list
            self._load_styles()

    def _edit_style(self):
        """Edit selected custom style"""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        old_text = item.text()

        text, ok = QInputDialog.getText(
            self, "Edit Custom Style", "Enter new style name:",
            QLineEdit.Normal, old_text
        )
        if ok and text.strip() and text.strip() != old_text:
            text = text.strip()
            # Check for duplicates
            custom_styles = self.config.get('custom_prompt_styles', [])
            if text in custom_styles:
                QMessageBox.warning(self, "Duplicate", f"Style '{text}' already exists.")
                return

            # Update in config
            try:
                index = custom_styles.index(old_text)
                custom_styles[index] = text
                self.config.set('custom_prompt_styles', custom_styles)
                self.config.save()

                # Refresh list
                self._load_styles()
            except ValueError:
                pass

    def _delete_style(self):
        """Delete selected custom style"""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        text = item.text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete custom style '{text}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Remove from config
            custom_styles = self.config.get('custom_prompt_styles', [])
            try:
                custom_styles.remove(text)
                self.config.set('custom_prompt_styles', custom_styles)
                self.config.save()

                # Refresh list
                self._load_styles()
            except ValueError:
                pass

    def get_custom_styles(self):
        """Get list of custom styles"""
        return self.config.get('custom_prompt_styles', [])


class WorkspaceWidget(QWidget):
    """Main workspace for video project editing"""

    # Signals
    project_changed = Signal(object)  # VideoProject
    generation_requested = Signal(str, dict)  # operation, kwargs
    image_provider_changed = Signal(str)  # provider name
    llm_provider_changed = Signal(str, str)  # provider name, model name
    
    def __init__(self, config: ConfigManager, providers: Dict[str, Any]):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.info("=== WorkspaceWidget.__init__ CALLED ===")

        # Suppress FFmpeg console output (set before creating media player)
        import os
        # Suppress all FFmpeg info/debug messages and AAC decoder warnings
        os.environ['QT_LOGGING_RULES'] = 'qt.multimedia.ffmpeg.info=false;qt.multimedia.ffmpeg.warning=false'

        self.config = config
        self.providers = providers
        self.video_config = VideoConfig()
        self.project_manager = ProjectManager(self.video_config.get_projects_dir())
        self.current_project = None

        # Wizard widget initialization (will be created when project is loaded)
        self.wizard_widget = None

        # Create image preview widget
        self.image_preview = ImageHoverPreview(self)

        # Track row clicks for image/video toggle
        self.last_clicked_row = None
        self.showing_video = False  # True if showing video, False if showing image

        # Track currently playing scene for sequential playback
        self.current_playing_scene = None

        self.logger.info("Calling init_ui()...")
        self.init_ui()
        self.logger.info("init_ui() complete")

        # Auto-reload last project if enabled (deferred until widget is shown)
        self.logger.info("Scheduling auto_load_last_project in 100ms...")
        QTimer.singleShot(100, self.auto_load_last_project)
        self.logger.info("=== WorkspaceWidget.__init__ COMPLETE ===")
    
    def init_ui(self):
        """Initialize the workspace UI"""
        self.logger.info("Creating workspace layout...")
        layout = QVBoxLayout(self)

        # Enable tooltip text wrapping globally for this widget
        self.setStyleSheet("QToolTip { white-space: pre-wrap; max-width: 400px; }")

        # LLM Provider at the top (global setting)
        self.logger.info("Creating LLM provider panel...")
        layout.addWidget(self.create_llm_provider_panel())

        # Project header
        self.logger.info("Creating project header...")
        layout.addWidget(self.create_project_header())

        # Main vertical splitter - top for workspace, bottom for image/console
        from gui.common.splitter_style import apply_splitter_style
        main_splitter = QSplitter(Qt.Vertical)
        apply_splitter_style(main_splitter)

        # Top section - existing workspace (wrapped in scroll area for larger image/video panel)
        from PySide6.QtWidgets import QScrollArea
        workspace_scroll = QScrollArea()
        workspace_scroll.setWidgetResizable(True)
        workspace_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        workspace_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        workspace_scroll.setFrameShape(QScrollArea.NoFrame)

        workspace_widget = QWidget()
        workspace_layout = QVBoxLayout(workspace_widget)
        workspace_layout.setContentsMargins(0, 0, 0, 0)

        # Horizontal layout for button + splitter
        h_container = QWidget()
        h_container_layout = QHBoxLayout(h_container)
        h_container_layout.setContentsMargins(0, 0, 0, 0)
        h_container_layout.setSpacing(2)

        # Wizard toggle button (fixed position, left of splitter)
        self.wizard_toggle_btn_top = QPushButton("◀ Hide")
        self.wizard_toggle_btn_top.setCheckable(True)
        self.wizard_toggle_btn_top.setChecked(True)
        self.wizard_toggle_btn_top.setMaximumWidth(60)
        self.wizard_toggle_btn_top.setMaximumHeight(25)
        self.wizard_toggle_btn_top.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.wizard_toggle_btn_top.setStyleSheet("QPushButton { font-size: 8pt; padding: 2px; }")
        self.wizard_toggle_btn_top.clicked.connect(self._toggle_wizard)
        h_container_layout.addWidget(self.wizard_toggle_btn_top, 0, Qt.AlignTop)

        # Horizontal splitter for workspace
        self.h_splitter = QSplitter(Qt.Horizontal)
        apply_splitter_style(self.h_splitter)

        # Wizard container (far left panel in splitter)
        self.wizard_container = QWidget()
        self.wizard_layout = QVBoxLayout(self.wizard_container)
        self.wizard_layout.setContentsMargins(5, 5, 5, 5)
        self.wizard_layout.setSpacing(2)

        # Content container (collapsible)
        self.wizard_content = QWidget()
        self.wizard_content_layout = QVBoxLayout(self.wizard_content)
        self.wizard_content_layout.setContentsMargins(0, 0, 0, 0)

        # Wizard placeholder (shown when no project is loaded)
        self.wizard_placeholder = QLabel("Load or create a project to see workflow guide")
        self.wizard_placeholder.setStyleSheet("color: #666; padding: 20px;")
        self.wizard_placeholder.setWordWrap(True)
        self.wizard_placeholder.setAlignment(Qt.AlignCenter)
        self.wizard_content_layout.addWidget(self.wizard_placeholder)

        self.wizard_layout.addWidget(self.wizard_content)

        self.h_splitter.addWidget(self.wizard_container)
        self.h_splitter.setCollapsible(0, False)  # Don't allow complete collapse via splitter

        # Store original width for restoring
        self.wizard_original_width = 300

        # Left panel - Input and settings
        self.logger.info("Creating left panel (input/settings/audio)...")
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.logger.info("  - Creating input panel...")
        left_layout.addWidget(self.create_input_panel())
        self.logger.info("  - Creating settings panel...")
        left_layout.addWidget(self.create_settings_panel())
        self.logger.info("  - Creating audio panel...")
        left_layout.addWidget(self.create_audio_panel())
        left_layout.addStretch()
        self.h_splitter.addWidget(left_panel)

        # Right panel - Storyboard and export
        self.logger.info("Creating right panel (storyboard/export)...")
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.logger.info("  - Creating storyboard panel...")
        # Add storyboard with stretch factor so it expands to fill available space
        right_layout.addWidget(self.create_storyboard_panel(), stretch=3)
        self.logger.info("  - Creating export panel...")
        # Export panel stays compact at bottom
        right_layout.addWidget(self.create_export_panel(), stretch=0)
        # Remove addStretch() so storyboard can grow to fill available vertical space
        self.h_splitter.addWidget(right_panel)

        # Set initial splitter sizes (wizard, left panel, right panel)
        self.h_splitter.setSizes([300, 400, 600])
        # Equal stretch factors so manual resizing works smoothly
        self.h_splitter.setStretchFactor(0, 1)  # Wizard can stretch
        self.h_splitter.setStretchFactor(1, 1)  # Left panel stretches equally
        self.h_splitter.setStretchFactor(2, 1)  # Right panel stretches equally

        # Set minimum width constraint for wizard container (match screenshot)
        self.wizard_container.setMinimumWidth(300)  # Minimum when visible
        # Remove any maximum width constraint to allow manual resizing
        self.wizard_container.setMaximumWidth(16777215)  # Qt's QWIDGETSIZE_MAX

        # Connect to splitter moved signal to enforce max 50% width constraint
        self.h_splitter.splitterMoved.connect(self._on_splitter_moved)

        # Add splitter to h_container
        h_container_layout.addWidget(self.h_splitter)

        workspace_layout.addWidget(h_container)

        # Status bar
        workspace_layout.addWidget(self.create_status_bar())

        # Set workspace widget in scroll area
        workspace_scroll.setWidget(workspace_widget)
        main_splitter.addWidget(workspace_scroll)

        # Bottom section - Image view and status console
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        # Image view and status console in vertical splitter
        image_console_splitter = QSplitter(Qt.Vertical)
        apply_splitter_style(image_console_splitter)

        # Media viewer container (holds both image and video player)
        media_viewer_container = QWidget()
        media_viewer_layout = QHBoxLayout(media_viewer_container)
        media_viewer_layout.setContentsMargins(0, 0, 0, 0)
        media_viewer_layout.setSpacing(0)

        # Image view (for static images)
        self.output_image_label = QLabel()
        self.output_image_label.setAlignment(Qt.AlignCenter)
        self.output_image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        self.output_image_label.setScaledContents(False)
        self.output_image_label.setMinimumHeight(150)
        media_viewer_layout.addWidget(self.output_image_label)

        # Video player container with controls on the right
        self.video_player_container = QWidget()
        video_player_layout = QHBoxLayout(self.video_player_container)
        video_player_layout.setContentsMargins(0, 0, 0, 0)
        video_player_layout.setSpacing(0)

        # Video widget (for video playback)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("border: 1px solid #ccc; background-color: #000;")
        self.video_widget.setMinimumHeight(150)
        video_player_layout.addWidget(self.video_widget)

        # Video player instance
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        # Default to muted
        self.audio_output.setMuted(True)

        # Video controls container (right side with wider controls)
        video_controls = QWidget()
        video_controls.setMinimumWidth(300)
        video_controls.setMaximumWidth(350)
        video_controls_layout = QVBoxLayout(video_controls)
        video_controls_layout.setContentsMargins(5, 5, 5, 5)
        video_controls_layout.setSpacing(8)

        # Playback controls row
        playback_controls = QHBoxLayout()

        self.play_pause_btn = QPushButton("▶ Play")
        self.play_pause_btn.clicked.connect(self._toggle_play_pause)
        playback_controls.addWidget(self.play_pause_btn)

        self.mute_btn = QPushButton("🔇 Unmute")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setChecked(True)  # Muted by default
        self.mute_btn.clicked.connect(self._toggle_mute)
        playback_controls.addWidget(self.mute_btn)

        video_controls_layout.addLayout(playback_controls)

        # Time display with precise control
        time_container = QWidget()
        time_layout = QHBoxLayout(time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(5)

        time_label = QLabel("Time:")
        time_layout.addWidget(time_label)

        # Precise time textbox (format: MM:SS.mmm)
        self.video_time_textbox = QLineEdit()
        self.video_time_textbox.setPlaceholderText("00:00.000")
        self.video_time_textbox.setMaximumWidth(90)
        self.video_time_textbox.setToolTip("Enter time as MM:SS.mmm or SS.mmm to jump to position\nPress Enter to apply")
        self.video_time_textbox.returnPressed.connect(self._on_time_textbox_changed)
        time_layout.addWidget(self.video_time_textbox)

        # Duration label
        self.video_time_label = QLabel("/ 00:00.000")
        time_layout.addWidget(self.video_time_label)
        time_layout.addStretch()

        video_controls_layout.addWidget(time_container)

        # Horizontal timeline with markers
        timeline_label = QLabel("Timeline")
        timeline_label.setStyleSheet("font-size: 9pt; font-weight: bold;")
        video_controls_layout.addWidget(timeline_label)

        # Create custom slider with tick marks
        timeline_container = QWidget()
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(2)

        self.video_position_slider = QSlider(Qt.Horizontal)
        self.video_position_slider.setRange(0, 0)
        self.video_position_slider.setTickPosition(QSlider.TicksBelow)
        self.video_position_slider.setTickInterval(1000)  # Tick every 1000ms (1 second)
        self.video_position_slider.sliderMoved.connect(self._set_position)
        self.video_position_slider.setMinimumHeight(30)
        self.video_position_slider.setToolTip("Drag to seek video position\nHover shows precise time")
        # Enable mouse tracking for tooltip
        self.video_position_slider.setMouseTracking(True)
        # Install event filter to show precise time tooltip
        self.video_position_slider.installEventFilter(self)

        timeline_layout.addWidget(self.video_position_slider)

        video_controls_layout.addWidget(timeline_container)

        # Extract frame button
        self.extract_frame_btn = QPushButton("📸 Extract Frame at Playhead")
        self.extract_frame_btn.setToolTip("Extract the current frame from the video and save it to the project")
        self.extract_frame_btn.clicked.connect(self._extract_frame_at_playhead)
        self.extract_frame_btn.setEnabled(False)  # Disabled until video is loaded
        video_controls_layout.addWidget(self.extract_frame_btn)

        # Playback options
        playback_options_layout = QHBoxLayout()

        self.loop_video_checkbox = QCheckBox("Loop Video")
        self.loop_video_checkbox.setChecked(True)  # Default enabled
        self.loop_video_checkbox.setToolTip("Loop the current video continuously")
        playback_options_layout.addWidget(self.loop_video_checkbox)

        self.sequential_playback_checkbox = QCheckBox("Play Sequential")
        self.sequential_playback_checkbox.setToolTip("Play available scenes in order, starting with current scene\n(Respects loop setting, but loops through all scenes)")
        playback_options_layout.addWidget(self.sequential_playback_checkbox)

        playback_options_layout.addStretch()
        video_controls_layout.addLayout(playback_options_layout)

        video_controls_layout.addStretch()

        video_player_layout.addWidget(video_controls)

        self.video_controls = video_controls
        self.video_player_container.hide()  # Hidden by default
        media_viewer_layout.addWidget(self.video_player_container)

        # Connect media player signals
        self.media_player.positionChanged.connect(self._update_position)
        self.media_player.durationChanged.connect(self._update_duration)
        self.media_player.playbackStateChanged.connect(self._update_play_button)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)

        image_console_splitter.addWidget(media_viewer_container)

        # Status console container
        console_container = QWidget()
        console_layout = QVBoxLayout(console_container)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        # Console header
        console_header = QLabel("Status Console")
        console_header.setStyleSheet("color: #666; font-size: 9pt; padding: 0px; margin: 0px;")
        console_header.setMaximumHeight(16)
        console_layout.addWidget(console_header)

        # Status console - styled like a terminal
        self.status_console = QTextEdit()
        self.status_console.setReadOnly(True)
        self.status_console.setMinimumHeight(50)
        self.status_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.status_console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid #444;
                padding: 4px;
                line-height: 1.0;
            }
        """)
        doc = self.status_console.document()
        doc.setDocumentMargin(0)
        console_layout.addWidget(self.status_console)

        image_console_splitter.addWidget(console_container)

        # Set initial splitter sizes
        image_console_splitter.setSizes([300, 100])
        image_console_splitter.setStretchFactor(0, 3)
        image_console_splitter.setStretchFactor(1, 1)

        bottom_layout.addWidget(image_console_splitter)
        main_splitter.addWidget(bottom_widget)

        # Set main splitter sizes (workspace gets more space initially)
        main_splitter.setSizes([500, 400])
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        layout.addWidget(main_splitter)

        # Store splitter references for save/restore
        self.main_splitter = main_splitter
        self.image_console_splitter = image_console_splitter

        # Connect splitter signals to save positions
        main_splitter.splitterMoved.connect(self._save_splitter_positions)
        self.h_splitter.splitterMoved.connect(self._save_splitter_positions)
        image_console_splitter.splitterMoved.connect(self._save_splitter_positions)

        # Restore splitter positions from saved settings (deferred until widget is shown)
        QTimer.singleShot(200, self._restore_splitter_positions)
    
    def create_project_header(self) -> QWidget:
        """Create project header with name and controls"""
        widget = QWidget()
        widget.setMaximumHeight(40)  # Make it compact
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)  # Reduce margins

        layout.addWidget(QLabel("Project:"))
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("My Video Project")
        self.project_name.setMaximumWidth(200)
        layout.addWidget(self.project_name)

        # Make buttons compact
        button_style = "QPushButton { padding: 2px 8px; }"

        self.new_btn = QPushButton("New")
        self.new_btn.setStyleSheet(button_style)
        self.new_btn.clicked.connect(self.new_project)
        layout.addWidget(self.new_btn)

        self.open_btn = QPushButton("Open")
        self.open_btn.setStyleSheet(button_style)
        self.open_btn.clicked.connect(self.open_project)
        layout.addWidget(self.open_btn)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setStyleSheet(button_style)
        self.browse_btn.clicked.connect(self.browse_projects)
        layout.addWidget(self.browse_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet(button_style)
        self.save_btn.clicked.connect(self.save_project)
        layout.addWidget(self.save_btn)

        self.save_as_btn = QPushButton("Save As")
        self.save_as_btn.setStyleSheet(button_style)
        self.save_as_btn.clicked.connect(self.save_project_as)
        layout.addWidget(self.save_as_btn)

        layout.addStretch()

        return widget

    def create_llm_provider_panel(self) -> QWidget:
        """Create LLM provider panel at the top (global setting)"""
        widget = QWidget()
        widget.setMaximumHeight(40)  # Make it compact
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)  # Reduce margins

        # LLM provider for prompts
        layout.addWidget(QLabel("LLM Provider:"))
        self.llm_provider_combo = QComboBox()
        # Get available providers based on configured API keys
        available_providers = self._get_available_llm_providers()
        self.llm_provider_combo.addItems(available_providers)
        self.llm_provider_combo.setToolTip("Select the AI provider for prompt enhancement and storyboard generation")
        self.llm_provider_combo.currentTextChanged.connect(self.on_llm_provider_changed)
        layout.addWidget(self.llm_provider_combo)

        layout.addWidget(QLabel("Model:"))
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setEnabled(False)
        # Set minimum width to ensure model names are fully visible
        self.llm_model_combo.setMinimumWidth(250)
        self.llm_model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.llm_model_combo.setToolTip("Select the specific AI model to use for prompt enhancement")
        self.llm_model_combo.currentTextChanged.connect(lambda: self._auto_save_settings())
        layout.addWidget(self.llm_model_combo)

        layout.addStretch()
        return widget
    
    def create_input_panel(self) -> QWidget:
        """Create input panel for lyrics/text"""
        group = QGroupBox("Input")
        layout = QVBoxLayout()
        
        # Format selector
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Auto-detect", "Timestamped", "Structured", "Plain text"])
        self.format_combo.setToolTip("Select the format of your input text:\n- Auto-detect: Automatically detect format\n- Timestamped: Text with [MM:SS] timestamps\n- Structured: JSON or structured data\n- Plain text: Unformatted lyrics or text")
        format_layout.addWidget(self.format_combo)

        self.load_file_btn = QPushButton("Load File")
        self.load_file_btn.setToolTip("Load lyrics or text from a file")
        self.load_file_btn.clicked.connect(self.load_input_file)
        format_layout.addWidget(self.load_file_btn)
        
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        # Text input
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Paste lyrics or text here...")
        self.input_text.setMaximumHeight(150)
        layout.addWidget(self.input_text)

        # Scene marker controls
        marker_layout = QHBoxLayout()
        marker_layout.addWidget(QLabel("Scene Markers:"))

        self.new_scene_btn = QPushButton("Insert Scene Marker")
        self.new_scene_btn.setToolTip("Insert '=== NEW SCENE: <environment> ===' at cursor position")
        self.new_scene_btn.clicked.connect(self._insert_scene_marker)
        marker_layout.addWidget(self.new_scene_btn)

        self.scene_env_input = QLineEdit()
        self.scene_env_input.setPlaceholderText("Environment (e.g., bedroom, forest...)")
        self.scene_env_input.setMaximumWidth(250)
        self.scene_env_input.setToolTip("Environment description for the new scene")
        marker_layout.addWidget(self.scene_env_input)

        self.delete_scene_btn = QPushButton("Delete Marker at Cursor")
        self.delete_scene_btn.setToolTip("Delete scene marker line at cursor position")
        self.delete_scene_btn.clicked.connect(self._delete_scene_marker)
        marker_layout.addWidget(self.delete_scene_btn)

        marker_layout.addStretch()
        layout.addLayout(marker_layout)

        # Timing controls
        timing_layout = QHBoxLayout()
        timing_layout.addWidget(QLabel("Target Length:"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 600)
        self.duration_spin.setValue(120)
        self.duration_spin.setSuffix(" sec")
        self.duration_spin.setToolTip("Target video length in seconds")
        timing_layout.addWidget(self.duration_spin)

        timing_layout.addWidget(QLabel("Pacing:"))
        self.pacing_combo = QComboBox()
        self.pacing_combo.addItems(["Fast", "Medium", "Slow"])
        self.pacing_combo.setCurrentIndex(1)
        self.pacing_combo.setToolTip("Scene transition pacing:\n- Fast: Quick cuts, energetic\n- Medium: Balanced pacing\n- Slow: Longer scenes, contemplative")
        timing_layout.addWidget(self.pacing_combo)

        self.generate_storyboard_btn = QPushButton("Generate Storyboard")
        self.generate_storyboard_btn.setToolTip("Generate scene breakdown from input text")
        self.generate_storyboard_btn.clicked.connect(self.generate_storyboard)
        timing_layout.addWidget(self.generate_storyboard_btn)
        
        timing_layout.addStretch()
        layout.addLayout(timing_layout)
        
        group.setLayout(layout)
        return group
    
    def create_settings_panel(self) -> QWidget:
        """Create settings panel for providers and style"""
        group = QGroupBox("Generation Settings")
        layout = QVBoxLayout()

        # Image provider
        img_layout = QHBoxLayout()
        img_layout.addWidget(QLabel("Image Provider:"))
        self.img_provider_combo = QComboBox()
        self.img_provider_combo.addItems(["Google", "OpenAI", "Stability", "Local SD"])
        self.img_provider_combo.setToolTip("Select the AI provider for image generation")
        self.img_provider_combo.currentTextChanged.connect(self.on_img_provider_changed)
        img_layout.addWidget(self.img_provider_combo)

        self.img_model_combo = QComboBox()
        # Set minimum width for image model combo too
        self.img_model_combo.setMinimumWidth(250)
        self.img_model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.img_model_combo.setToolTip("Select the specific image generation model")
        self.img_model_combo.currentTextChanged.connect(lambda: self._auto_save_settings())
        img_layout.addWidget(self.img_model_combo)

        img_layout.addStretch()
        layout.addLayout(img_layout)
        
        # Style settings
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Style:"))

        # Built-in styles (read-only)
        self.builtin_styles = [
            "Cinematic",
            "Artistic",
            "Photorealistic",
            "Animated",
            "Noir",
            "Documentary",
            "Vintage",
            "Modern",
            "Abstract",
            "Minimalist"
        ]

        self.prompt_style_input = QComboBox()
        self.prompt_style_input.setEditable(False)  # Read-only selection
        self._populate_styles_combo()
        # Set default to first item (Cinematic)
        if self.prompt_style_input.count() > 0:
            self.prompt_style_input.setCurrentIndex(0)
        self.prompt_style_input.setToolTip("Visual style for prompt enhancement and image generation\nSelect from built-in or custom styles, or choose (Custom) to enter freeform text")
        self.prompt_style_input.currentTextChanged.connect(self._on_style_changed)
        self.prompt_style_input.setMinimumWidth(200)
        style_layout.addWidget(self.prompt_style_input)

        # Add/manage custom styles button
        self.manage_styles_btn = QPushButton("+")
        self.manage_styles_btn.setMaximumWidth(30)
        self.manage_styles_btn.setToolTip("Manage custom styles")
        self.manage_styles_btn.clicked.connect(self._manage_custom_styles)
        style_layout.addWidget(self.manage_styles_btn)

        # Custom text input (hidden by default, shown when (Custom) is selected)
        self.custom_style_input = QLineEdit()
        self.custom_style_input.setPlaceholderText("Enter custom style...")
        self.custom_style_input.setMinimumWidth(200)
        self.custom_style_input.hide()
        self.custom_style_input.textChanged.connect(lambda: self._auto_save_settings())
        style_layout.addWidget(self.custom_style_input)

        style_layout.addWidget(QLabel("Aspect Ratio:"))
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["16:9", "9:16", "1:1"])
        self.aspect_combo.setToolTip("Video aspect ratio (Veo 3 compatible):\n- 16:9: Widescreen (landscape)\n- 9:16: Vertical (portrait)\n- 1:1: Square")
        style_layout.addWidget(self.aspect_combo)

        style_layout.addWidget(QLabel("Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["720p", "1080p"])
        self.resolution_combo.setCurrentIndex(1)
        self.resolution_combo.setToolTip("Target resolution (Veo 3 compatible):\n- 720p: HD (1280x720)\n- 1080p: Full HD (1920x1080)")
        style_layout.addWidget(self.resolution_combo)

        style_layout.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(-1, 999999)
        self.seed_spin.setValue(-1)
        self.seed_spin.setSpecialValueText("Random")
        self.seed_spin.setToolTip("Generation seed for reproducibility (-1 for random)")
        style_layout.addWidget(self.seed_spin)

        # Visual continuity mode for start frame generation
        style_layout.addWidget(QLabel("Continuity:"))
        self.continuity_mode_combo = QComboBox()
        from core.video.style_analyzer import ContinuityMode
        self.continuity_mode_combo.addItem("None", ContinuityMode.NONE.value)
        self.continuity_mode_combo.addItem("Style Only", ContinuityMode.STYLE_ONLY.value)
        self.continuity_mode_combo.addItem("Transition", ContinuityMode.TRANSITION.value)
        self.continuity_mode_combo.setCurrentIndex(0)
        self.continuity_mode_combo.setToolTip(
            "Visual continuity for start frame generation:\n"
            "- None: Fresh scene without previous frame\n"
            "- Style Only: Match lighting/colors from previous frame\n"
            "- Transition: Smooth visual continuation from previous frame"
        )
        self.continuity_mode_combo.currentIndexChanged.connect(lambda: self._auto_save_settings())
        style_layout.addWidget(self.continuity_mode_combo)

        style_layout.addStretch()
        layout.addLayout(style_layout)
        
        # Negative prompt
        neg_layout = QHBoxLayout()
        neg_layout.addWidget(QLabel("Negative:"))
        self.negative_prompt = QLineEdit()
        self.negative_prompt.setPlaceholderText("Things to avoid in generation...")
        self.negative_prompt.setToolTip("Negative prompt: describe what you DON'T want in the images\n(e.g., 'blurry, low quality, text, watermark')")
        neg_layout.addWidget(self.negative_prompt)
        layout.addLayout(neg_layout)
        
        # Continuity features
        continuity_layout = QHBoxLayout()
        self.enable_continuity_checkbox = QCheckBox("Enable Visual Continuity")
        self.enable_continuity_checkbox.setToolTip(
            "Enhances visual consistency between scenes using provider-specific techniques:\n"
            "- Gemini: Iterative refinement with previous images\n"
            "- OpenAI: Reference IDs for style consistency\n"
            "- Claude: Style guides and character descriptions"
        )
        self.enable_continuity_checkbox.stateChanged.connect(lambda: self._auto_save_settings())
        continuity_layout.addWidget(self.enable_continuity_checkbox)
        
        self.enable_enhanced_storyboard = QCheckBox("Enhanced Storyboard")
        self.enable_enhanced_storyboard.setToolTip(
            "Use advanced storyboard generation with structured scene descriptions"
        )
        self.enable_enhanced_storyboard.stateChanged.connect(lambda: self._auto_save_settings())
        continuity_layout.addWidget(self.enable_enhanced_storyboard)

        continuity_layout.addStretch()
        layout.addLayout(continuity_layout)

        # Video prompt generation options
        video_prompt_layout = QHBoxLayout()
        self.enable_camera_movements_check = QCheckBox("Enable Camera Movements")
        self.enable_camera_movements_check.setToolTip(
            "Add camera movements (pan, tilt, zoom, dolly) to video prompts\n"
            "Disable for static or minimal-movement scenes"
        )
        self.enable_camera_movements_check.setChecked(True)  # Enabled by default
        self.enable_camera_movements_check.stateChanged.connect(lambda: self._auto_save_settings())
        video_prompt_layout.addWidget(self.enable_camera_movements_check)

        self.enable_prompt_flow_check = QCheckBox("Enable Prompt Flow")
        self.enable_prompt_flow_check.setToolTip(
            "Make video prompts flow continuously into each other (text-only continuity)\n"
            "Flow breaks between chorus/verses for natural section transitions"
        )
        self.enable_prompt_flow_check.setChecked(True)  # Enabled by default
        self.enable_prompt_flow_check.stateChanged.connect(lambda: self._auto_save_settings())
        video_prompt_layout.addWidget(self.enable_prompt_flow_check)

        video_prompt_layout.addStretch()
        layout.addLayout(video_prompt_layout)
        
        group.setLayout(layout)
        
        # Initialize the model combos with default selections
        # NOTE: Commented out - this was being called before project loading
        # and was interfering with restoring saved values
        # self.on_img_provider_changed(self.img_provider_combo.currentText())
        
        # Instead, populate the image model combo with default Gemini models
        # since Gemini is the first item in the provider combo
        self.img_model_combo.addItems([
            "gemini-2.5-flash-image-preview",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-pro"
        ])
        
        return group
    
    def create_audio_panel(self) -> QWidget:
        """Create audio and MIDI settings panel"""
        group = QGroupBox("Audio & MIDI")
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        # Audio file selection
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(QLabel("Audio:"))
        self.audio_file_label = QLabel("No file")
        self.audio_file_label.setMinimumWidth(150)
        audio_layout.addWidget(self.audio_file_label)
        
        self.browse_audio_btn = QPushButton("Browse...")
        self.browse_audio_btn.clicked.connect(self.browse_audio_file)
        audio_layout.addWidget(self.browse_audio_btn)
        
        self.clear_audio_btn = QPushButton("Clear")
        self.clear_audio_btn.clicked.connect(self.clear_audio)
        self.clear_audio_btn.setEnabled(False)
        audio_layout.addWidget(self.clear_audio_btn)
        
        layout.addLayout(audio_layout)
        
        # MIDI file selection
        midi_layout = QHBoxLayout()
        midi_layout.addWidget(QLabel("MIDI:"))
        self.midi_file_label = QLabel("No file")
        self.midi_file_label.setMinimumWidth(150)
        midi_layout.addWidget(self.midi_file_label)
        
        self.browse_midi_btn = QPushButton("Browse...")
        self.browse_midi_btn.clicked.connect(self.browse_midi_file)
        midi_layout.addWidget(self.browse_midi_btn)
        
        self.clear_midi_btn = QPushButton("Clear")
        self.clear_midi_btn.clicked.connect(self.clear_midi)
        self.clear_midi_btn.setEnabled(False)
        midi_layout.addWidget(self.clear_midi_btn)
        
        self.midi_info_label = QLabel("")
        self.midi_info_label.setStyleSheet("color: #666; font-size: 10pt;")
        midi_layout.addWidget(self.midi_info_label)
        
        layout.addLayout(midi_layout)
        
        # MIDI Sync controls
        sync_layout = QHBoxLayout()
        sync_layout.addWidget(QLabel("Sync:"))
        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItems(["None", "Beat", "Measure", "Section"])
        self.sync_mode_combo.setEnabled(False)
        sync_layout.addWidget(self.sync_mode_combo)
        
        sync_layout.addWidget(QLabel("Snap:"))
        self.snap_strength_slider = QSlider(Qt.Horizontal)
        self.snap_strength_slider.setRange(0, 100)
        self.snap_strength_slider.setValue(80)
        self.snap_strength_slider.setMaximumWidth(100)
        self.snap_strength_slider.setEnabled(False)
        sync_layout.addWidget(self.snap_strength_slider)
        
        self.snap_label = QLabel("80%")
        self.snap_strength_slider.valueChanged.connect(lambda v: self.snap_label.setText(f"{v}%"))
        sync_layout.addWidget(self.snap_label)
        
        self.extract_lyrics_btn = QPushButton("Extract Lyrics")
        self.extract_lyrics_btn.clicked.connect(self.extract_midi_lyrics)
        self.extract_lyrics_btn.setEnabled(False)
        sync_layout.addWidget(self.extract_lyrics_btn)
        
        sync_layout.addStretch()
        layout.addLayout(sync_layout)
        
        # Audio controls
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setMaximumWidth(100)
        controls_layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("80%")
        self.volume_slider.valueChanged.connect(lambda v: self.volume_label.setText(f"{v}%"))
        controls_layout.addWidget(self.volume_label)
        
        controls_layout.addWidget(QLabel("Fade In:"))
        self.fade_in_spin = QDoubleSpinBox()
        self.fade_in_spin.setRange(0, 5)
        self.fade_in_spin.setValue(0)
        self.fade_in_spin.setSuffix(" s")
        controls_layout.addWidget(self.fade_in_spin)
        
        controls_layout.addWidget(QLabel("Fade Out:"))
        self.fade_out_spin = QDoubleSpinBox()
        self.fade_out_spin.setRange(0, 5)
        self.fade_out_spin.setValue(0)
        self.fade_out_spin.setSuffix(" s")
        controls_layout.addWidget(self.fade_out_spin)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Karaoke options (hidden by default)
        self.karaoke_group = QGroupBox("Karaoke Options")
        self.karaoke_group.setCheckable(True)
        self.karaoke_group.setChecked(False)
        self.karaoke_group.setVisible(False)
        karaoke_layout = QVBoxLayout()
        
        karaoke_style_layout = QHBoxLayout()
        karaoke_style_layout.addWidget(QLabel("Style:"))
        self.karaoke_style_combo = QComboBox()
        self.karaoke_style_combo.addItems(["Bouncing Ball", "Highlight", "Fade In"])
        karaoke_style_layout.addWidget(self.karaoke_style_combo)
        
        karaoke_style_layout.addWidget(QLabel("Position:"))
        self.karaoke_position_combo = QComboBox()
        self.karaoke_position_combo.addItems(["Bottom", "Top", "Center"])
        karaoke_style_layout.addWidget(self.karaoke_position_combo)
        
        karaoke_style_layout.addWidget(QLabel("Font Size:"))
        self.karaoke_font_spin = QSpinBox()
        self.karaoke_font_spin.setRange(16, 72)
        self.karaoke_font_spin.setValue(32)
        karaoke_style_layout.addWidget(self.karaoke_font_spin)
        
        karaoke_style_layout.addStretch()
        karaoke_layout.addLayout(karaoke_style_layout)
        
        # Export formats
        export_layout = QHBoxLayout()
        export_layout.addWidget(QLabel("Export:"))
        self.export_lrc_check = QCheckBox("LRC")
        self.export_lrc_check.setChecked(True)
        export_layout.addWidget(self.export_lrc_check)
        
        self.export_srt_check = QCheckBox("SRT")
        self.export_srt_check.setChecked(True)
        export_layout.addWidget(self.export_srt_check)
        
        self.export_ass_check = QCheckBox("ASS")
        export_layout.addWidget(self.export_ass_check)
        
        export_layout.addStretch()
        karaoke_layout.addLayout(export_layout)
        
        self.karaoke_group.setLayout(karaoke_layout)
        layout.addWidget(self.karaoke_group)
        
        group.setLayout(layout)
        return group
    
    def create_storyboard_panel(self) -> QWidget:
        """Create storyboard panel with scene table"""
        group = QGroupBox("Storyboard")
        layout = QVBoxLayout()
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.enhance_prompts_btn = QPushButton("Enhance All Prompts")
        self.enhance_prompts_btn.setToolTip("Use AI to enhance all scene prompts for better image generation")
        self.enhance_prompts_btn.clicked.connect(self.enhance_all_prompts)
        self.enhance_prompts_btn.setEnabled(False)
        controls_layout.addWidget(self.enhance_prompts_btn)

        self.enhance_video_prompts_btn = QPushButton("Generate Video Prompts")
        self.enhance_video_prompts_btn.setToolTip("Add camera movement and motion to image prompts for video generation")
        self.enhance_video_prompts_btn.clicked.connect(self.enhance_for_video)
        self.enhance_video_prompts_btn.setEnabled(False)
        controls_layout.addWidget(self.enhance_video_prompts_btn)

        self.generate_images_btn = QPushButton("Generate Images")
        self.generate_images_btn.setToolTip("Generate images for all scenes with prompts")
        self.generate_images_btn.clicked.connect(self.generate_images)
        self.generate_images_btn.setEnabled(False)
        controls_layout.addWidget(self.generate_images_btn)

        # Character Reference Generation button
        self.char_ref_btn = QPushButton("🎨 Character Refs")
        self.char_ref_btn.setToolTip("Generate character reference images for consistency across scenes")
        self.char_ref_btn.clicked.connect(self.open_character_reference_wizard)
        controls_layout.addWidget(self.char_ref_btn)

        # Visual Reference Library button
        self.ref_library_btn = QPushButton("📸 Ref Library")
        self.ref_library_btn.setToolTip("Open visual reference library to manage global references")
        self.ref_library_btn.clicked.connect(self.open_reference_library)
        controls_layout.addWidget(self.ref_library_btn)

        controls_layout.addStretch()

        self.total_duration_label = QLabel("Total: 0:00")
        self.total_duration_label.setToolTip("Total video duration based on all scenes")
        controls_layout.addWidget(self.total_duration_label)

        # Warning label for invalid scene durations
        self.duration_warning_label = QLabel()
        self.duration_warning_label.setStyleSheet("color: #cc0000; font-weight: bold; padding: 4px;")
        self.duration_warning_label.setVisible(False)
        controls_layout.addWidget(self.duration_warning_label)

        layout.addLayout(controls_layout)
        
        # Scene table (11 columns - optimized for Veo 3.1)
        self.scene_table = QTableWidget()
        self.scene_table.setColumnCount(12)
        self.scene_table.setHorizontalHeaderLabels([
            "#", "Start Frame", "End Frame", "Ref Images", "🎬", "Time", "⤵️",
            "Source", "Environment", "Video Prompt", "Start Prompt", "End Prompt (Optional)"
        ])
        # Set size policy to expand vertically to show more rows
        self.scene_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Make table non-selectable
        self.scene_table.setSelectionMode(QTableWidget.NoSelection)
        self.scene_table.setFocusPolicy(Qt.NoFocus)
        # Disable auto-scroll on mouse hover
        self.scene_table.setAutoScroll(False)
        self.scene_table.setAutoScrollMargin(0)
        # Disable word wrap by default - individual rows can be toggled
        self.scene_table.setWordWrap(False)
        self.scene_table.setTextElideMode(Qt.ElideRight)
        # Set tooltips for headers (12 columns: 0-11)
        self.scene_table.horizontalHeaderItem(0).setToolTip("Scene number")
        self.scene_table.horizontalHeaderItem(1).setToolTip("Start Frame\nFirst frame of video (hover for preview, click to view, right-click for options)")
        self.scene_table.horizontalHeaderItem(2).setToolTip("End Frame\nLast frame of video (hover for preview, click to view, right-click for options)\nLeave empty for Veo 3 single-frame video")
        self.scene_table.horizontalHeaderItem(3).setToolTip("Reference Images (Veo 3)\nUp to 3 images for visual continuity (style/character/environment)\nAuto-links previous scene's last frame when enabled")
        self.scene_table.horizontalHeaderItem(4).setToolTip("Generate Video\nClick to view first frame when video exists, double-click to regenerate")
        # Column 5 (Time): No tooltip
        self.scene_table.horizontalHeaderItem(6).setToolTip("Wrap\nToggle prompt text wrapping for this row")
        self.scene_table.horizontalHeaderItem(7).setToolTip("Source\nOriginal lyrics or text (hover for full text)")
        self.scene_table.horizontalHeaderItem(8).setToolTip("Environment\nLocation/setting for this scene (e.g., 'bedroom', 'abstract', 'forest')\nPassed to LLM for consistent environment across scenes")
        self.scene_table.horizontalHeaderItem(9).setToolTip("Video Prompt\nAI-enhanced prompt with camera movement for video generation (✨ LLM + ↶↷ undo/redo)")
        self.scene_table.horizontalHeaderItem(10).setToolTip("Start Prompt\nAI-enhanced prompt for start frame generation (✨ LLM + ↶↷ undo/redo)")
        self.scene_table.horizontalHeaderItem(11).setToolTip("End Prompt\nOptional: describe the ending frame for Veo 3.1 transition (✨ LLM + ↶↷ undo/redo)")
        # Configure columns - all resizable by user
        header = self.scene_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)  # All columns user-resizable
        header.setStretchLastSection(False)
        # Set fixed row height to match PromptFieldWidget button height
        self.scene_table.verticalHeader().setDefaultSectionSize(30)  # Match LLM button height
        self.scene_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        # Set initial widths for 12-column layout (with Environment column)
        header.resizeSection(0, 35)   # Scene # - minimized
        header.resizeSection(1, 70)   # Start Frame - FrameButton widget
        header.resizeSection(2, 70)   # End Frame - FrameButton widget
        header.resizeSection(3, 160)  # Ref Images - ReferenceImagesWidget (3 buttons)
        header.resizeSection(4, 40)   # Video button (🎬)
        header.resizeSection(5, 45)   # Time - narrow
        header.resizeSection(6, 40)   # Wrap button (⤵️) - minimized
        header.resizeSection(7, 120)  # Source - compact
        header.resizeSection(8, 120)  # Environment - compact (editable text field)
        header.resizeSection(9, 360)  # Video Prompt - wide (text + ✨ + ↶↷)
        header.resizeSection(10, 360) # Start Prompt - wide (text + ✨ + ↶↷)
        header.resizeSection(11, 360) # End Prompt - wide (text + ✨ + ↶↷)
        # Enforce minimum width for Ref Images column (col 3) - must fit 3 buttons
        # 3 buttons × 50px (min) + 2 spacings × 2px + margins 4px = 158px minimum
        header.sectionResized.connect(self._on_column_resized)
        # Enable double-click to auto-resize and Ctrl+double-click for all columns
        header.sectionDoubleClicked.connect(self._on_header_double_clicked)

        # Install event filter for hover preview
        self.scene_table.viewport().installEventFilter(self)
        self.scene_table.setMouseTracking(True)

        # Connect cell click to show image in image view
        self.scene_table.cellClicked.connect(self._on_cell_clicked)

        # Connect scrollbar signals to save positions
        h_scrollbar = self.scene_table.horizontalScrollBar()
        v_scrollbar = self.scene_table.verticalScrollBar()
        if h_scrollbar:
            h_scrollbar.valueChanged.connect(self._save_scrollbar_positions)
        if v_scrollbar:
            v_scrollbar.valueChanged.connect(self._save_scrollbar_positions)

        layout.addWidget(self.scene_table)
        
        group.setLayout(layout)
        return group
    
    def create_export_panel(self) -> QWidget:
        """Create export/render panel"""
        group = QGroupBox("Video Export")
        layout = QVBoxLayout()
        
        # Video provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Render Method:"))
        self.video_provider_combo = QComboBox()
        self.video_provider_combo.addItems(["FFmpeg Slideshow", "Gemini Veo"])
        self.video_provider_combo.setCurrentIndex(1)  # Default to Gemini Veo
        self.video_provider_combo.setToolTip("Video rendering method:\n- FFmpeg Slideshow: Traditional slideshow with transitions\n- Gemini Veo: AI-powered video generation")
        self.video_provider_combo.currentTextChanged.connect(self.on_video_provider_changed)
        provider_layout.addWidget(self.video_provider_combo)

        self.veo_model_combo = QComboBox()
        self.veo_model_combo.addItems([
            "veo-3.1-generate-001",  # Veo 3.1 - supports frames-to-video
            "veo-3.0-generate-001",
            "veo-3.0-fast-generate-001",
            "veo-2.0-generate-001"
        ])
        self.veo_model_combo.setCurrentIndex(0)  # Default to veo-3.1-generate-001
        self.veo_model_combo.setVisible(True)  # Make visible by default since Veo is default
        # Set minimum width for Veo model combo
        self.veo_model_combo.setMinimumWidth(250)
        self.veo_model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.veo_model_combo.setToolTip("Veo model version:\n- veo-3.1: Frames-to-video (start + end frames)\n- veo-3.0: Latest quality\n- veo-3.0-fast: Faster generation\n- veo-2.0: Previous generation")
        self.veo_model_combo.currentTextChanged.connect(self.on_veo_model_changed)
        provider_layout.addWidget(self.veo_model_combo)
        
        provider_layout.addStretch()
        layout.addLayout(provider_layout)
        
        # Export settings
        export_layout = QHBoxLayout()

        self.ken_burns_check = QCheckBox("Ken Burns Effect")
        self.ken_burns_check.setChecked(True)
        self.ken_burns_check.setToolTip("Add slow pan and zoom motion to static images")
        export_layout.addWidget(self.ken_burns_check)

        self.transitions_check = QCheckBox("Transitions")
        self.transitions_check.setChecked(True)
        self.transitions_check.setToolTip("Add crossfade transitions between scenes")
        export_layout.addWidget(self.transitions_check)

        self.captions_check = QCheckBox("Captions")
        self.captions_check.setToolTip("Include lyrics/text as captions in the video")
        export_layout.addWidget(self.captions_check)

        # Veo 3.1 sequential chaining option
        self.use_prev_last_frame_check = QCheckBox("Smooth Transitions")
        self.use_prev_last_frame_check.setToolTip(
            "Use previous clip's last frame as next clip's start frame\n"
            "Creates smooth visual continuity between video clips\n"
            "(Veo 3.1 only - uses frame-to-frame interpolation)"
        )
        self.use_prev_last_frame_check.setChecked(False)
        export_layout.addWidget(self.use_prev_last_frame_check)

        export_layout.addStretch()
        layout.addLayout(export_layout)
        
        # Export buttons
        button_layout = QHBoxLayout()

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Generate a quick preview of the video")
        self.preview_btn.clicked.connect(self.preview_video)
        self.preview_btn.setEnabled(False)
        button_layout.addWidget(self.preview_btn)

        self.render_btn = QPushButton("Render Video")
        self.render_btn.setToolTip("Render the final video with all settings applied")
        self.render_btn.clicked.connect(self.render_video)
        self.render_btn.setEnabled(False)
        button_layout.addWidget(self.render_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group
    
    def create_status_bar(self) -> QWidget:
        """Create status bar with progress"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        
        self.cost_label = QLabel("Cost: $0.00")
        layout.addWidget(self.cost_label)
        
        widget.setLayout(layout)
        return widget
    
    # Event handlers
    def new_project(self):
        """Create a new project"""
        if self.current_project and len(self.current_project.scenes) > 0:
            dialog_manager = get_dialog_manager(self)
            reply = dialog_manager.show_question(
                "Save Project",
                "Save current project before creating new?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self.save_project()
            elif reply == QMessageBox.Cancel:
                return
        
        self.current_project = VideoProject(name=self.project_name.text() or "Untitled")
        self.project_name.setText(self.current_project.name)

        # Create wizard widget for new project
        self._create_wizard_widget()

        self.update_ui_state()
        self.project_changed.emit(self.current_project)
    
    def auto_load_last_project(self):
        """Auto-load the last opened project if enabled"""
        from gui.video.project_browser import get_last_project_path

        self.logger.info("=== AUTO-LOAD TRIGGERED ===")
        self.logger.info(f"Widget visible: {self.isVisible()}")
        self.logger.info(f"Widget has parent: {self.parent() is not None}")

        last_project = get_last_project_path()
        if last_project:
            self.logger.info(f"Auto-loading last project: {last_project}")
            try:
                # Suppress error dialogs during auto-load on startup
                self.load_project_from_path(last_project, show_error_dialog=False)
                self.logger.info(f"=== AUTO-LOAD COMPLETE - Style after load: {self._get_current_style()} ===")
            except Exception as e:
                self.logger.warning(f"Could not auto-load last project: {e}")
                # User will start with a clean slate instead
        else:
            self.logger.info("No last project to auto-load")
    
    def browse_projects(self):
        """Browse and open projects using the project browser"""
        from gui.video.project_browser import ProjectBrowserDialog
        
        dialog = ProjectBrowserDialog(self.project_manager, self)
        dialog.project_selected.connect(self.load_project_from_path)
        dialog.exec()
    
    def load_project_from_path(self, project_path, show_error_dialog=True):
        """Load a project from a given path

        Args:
            project_path: Path to the project file
            show_error_dialog: Whether to show error dialogs (False for auto-load on startup)
        """
        self.logger.info(f"=== load_project_from_path CALLED ===")
        self.logger.info(f"project_path: {project_path} (type: {type(project_path)})")
        self.logger.info(f"show_error_dialog: {show_error_dialog}")

        try:
            self.logger.info(f"Calling project_manager.load_project({project_path})...")
            self.current_project = self.project_manager.load_project(project_path)
            self.logger.info(f"Project loaded: {self.current_project.name}")
            self.load_project_to_ui()

            # Create wizard widget for loaded project
            self._create_wizard_widget()

            self.update_ui_state()
            self.project_changed.emit(self.current_project)
            self.status_label.setText(f"Loaded: {self.current_project.name}")

            # Save as last opened project
            from PySide6.QtCore import QSettings
            settings = QSettings("ImageAI", "VideoProjects")
            self.logger.info(f"Saving last_project to QSettings: {project_path}")
            settings.setValue("last_project", str(project_path))
            settings.sync()  # Force write to disk
            # Verify it was saved
            saved_value = settings.value("last_project")
            self.logger.info(f"Verified last_project in QSettings: {saved_value}")
        except (ValueError, FileNotFoundError) as e:
            # Handle corrupted/empty project files
            self.logger.error(f"Failed to load project from {project_path}: {e}", exc_info=True)

            if show_error_dialog:
                dialog_manager = get_dialog_manager(self)
                dialog_manager.show_error("Project Load Error", f"Failed to open project:\n\n{e}\n\nThe project file may be corrupted or empty.")

            # Clear the last project setting so we don't try to auto-load it again
            from PySide6.QtCore import QSettings
            settings = QSettings("ImageAI", "VideoProjects")
            settings.remove("last_project")
            self.logger.info("Cleared auto-load setting for corrupted project")

            # Re-raise so caller knows it failed
            raise
        except Exception as e:
            self.logger.error(f"Failed to load project from {project_path}: {e}", exc_info=True)

            if show_error_dialog:
                dialog_manager = get_dialog_manager(self)
                dialog_manager.show_error("Error", f"Failed to open project: {e}")

            # Re-raise so caller knows it failed
            raise
    
    def open_project(self):
        """Open existing project"""
        self.logger.info("=== open_project CALLED ===")
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Project",
            str(self.video_config.get_projects_dir()),
            "ImageAI Projects (*.iaproj.json)"
        )
        self.logger.info(f"Selected filename: {filename}")
        if filename:
            try:
                self.logger.info(f"Loading project from: {filename}")
                self.current_project = self.project_manager.load_project(Path(filename))
                self.project_name.setText(self.current_project.name)
                self.load_project_to_ui()
                self.update_ui_state()
                self.project_changed.emit(self.current_project)

                # Save as last opened project
                from PySide6.QtCore import QSettings
                settings = QSettings("ImageAI", "VideoProjects")
                self.logger.info(f"Saving last_project to QSettings: {filename}")
                settings.setValue("last_project", str(filename))
                settings.sync()  # Force write to disk
                # Verify it was saved
                saved_value = settings.value("last_project")
                self.logger.info(f"Verified last_project in QSettings: {saved_value}")
            except Exception as e:
                self.logger.error(f"Failed to open project: {e}", exc_info=True)
                dialog_manager = get_dialog_manager(self)
                dialog_manager.show_error("Error", f"Failed to open project: {e}")
    
    def save_project(self):
        """Save current project"""
        if not self.current_project:
            # Create a new project if none exists
            project_name = self.project_name.text().strip() or "Untitled"
            self.current_project = VideoProject(name=project_name)
            self.update_ui_state()

        try:
            self.update_project_from_ui()
            self.logger.info(f"Saving Ken Burns: {self.current_project.ken_burns}")

            self.project_manager.save_project(self.current_project)
            num_scenes = len(self.current_project.scenes) if self.current_project.scenes else 0
            self.status_label.setText(f"Project saved: {self.current_project.name} ({num_scenes} scenes)")
            self.project_changed.emit(self.current_project)

            # Refresh wizard after save
            self._refresh_wizard()
        except Exception as e:
            self.logger.error(f"Failed to save project: {e}", exc_info=True)
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_error("Error", f"Failed to save project: {e}")
    
    def save_project_as(self):
        """Save current project with a new name"""
        if not self.current_project:
            # Create a new project if none exists
            project_name = self.project_name.text().strip() or "Untitled"
            self.current_project = VideoProject(name=project_name)
            self.update_ui_state()
        
        # Ask user for new project name
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "Save Project As",
            "Enter new project name:",
            text=self.current_project.name + "_copy"
        )
        
        if ok and new_name.strip():
            try:
                # Update project from UI first
                self.update_project_from_ui()
                
                # Create a copy of the current project with new name
                import copy
                new_project = copy.deepcopy(self.current_project)
                new_project.name = new_name.strip()
                
                # IMPORTANT: Clear the project_dir so a new directory is created
                new_project.project_dir = None
                
                # Save the new project (this will create a new directory)
                self.project_manager.save_project(new_project)
                
                # Set it as current project
                self.current_project = new_project
                self.project_name.setText(new_project.name)
                
                # Update recent projects list
                self.update_recent_projects(new_project)
                
                # Update UI
                num_scenes = len(new_project.scenes) if new_project.scenes else 0
                self.status_label.setText(f"Project saved as: {new_project.name} ({num_scenes} scenes)")
                self.project_changed.emit(new_project)
                
                self.logger.info(f"Project saved as: {new_project.name}")
                
            except Exception as e:
                self.logger.error(f"Failed to save project as: {e}", exc_info=True)
                dialog_manager = get_dialog_manager(self)
                dialog_manager.show_error("Error", f"Failed to save project as: {e}")
    
    def update_recent_projects(self, project: VideoProject):
        """Update the recent projects list with the given project"""
        try:
            # Get all project files and sort by modification time
            projects_dir = self.project_manager.base_dir
            if projects_dir.exists():
                # Look for project files in subdirectories (each project has its own folder)
                project_files = list(projects_dir.glob("*/project.iaproj.json"))
                # Sort by modification time (most recent first)
                project_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                
                # Log for debugging
                if project.project_dir:
                    project_path = project.project_dir / "project.iaproj.json"
                else:
                    project_path = projects_dir / f"{project.name}_*" / "project.iaproj.json"
                self.logger.info(f"Updated recent projects - {project.name} saved")
                self.logger.info(f"Total projects in directory: {len(project_files)}")
                
                # The project_manager.save_project already handles the file saving,
                # so this is mainly for logging and potential future UI updates
        except Exception as e:
            self.logger.error(f"Error updating recent projects: {e}")

    def _insert_scene_marker(self):
        """Insert scene marker at cursor position"""
        environment = self.scene_env_input.text().strip() or "untitled"
        marker_text = f"=== NEW SCENE: {environment} ==="

        cursor = self.input_text.textCursor()
        cursor.insertText(f"\n{marker_text}\n")

        # Clear the environment input
        self.scene_env_input.clear()

        self.logger.info(f"Inserted scene marker: {marker_text}")

    def _delete_scene_marker(self):
        """Delete scene marker line at cursor position"""
        cursor = self.input_text.textCursor()
        cursor.select(cursor.LineUnderCursor)
        line_text = cursor.selectedText().strip()

        # Check if this line is a scene marker
        import re
        if re.match(r'^===\s*NEW SCENE:.*===$', line_text, re.IGNORECASE):
            cursor.removeSelectedText()
            cursor.deletePreviousChar()  # Remove the newline
            self.logger.info(f"Deleted scene marker: {line_text}")
        else:
            from gui.utils.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_error("Not a Scene Marker",
                                     "Cursor is not on a scene marker line.\n\n"
                                     "Scene markers have the format: === NEW SCENE: <environment> ===")

    def generate_storyboard(self):
        """Generate storyboard from input text"""
        self.logger.info("=== Starting storyboard generation ===")
        text = self.input_text.toPlainText()
        if not text:
            self.logger.warning("Generate storyboard called with no input text")
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Input", "Please enter text or lyrics")
            return
        
        self.logger.info(f"Input text length: {len(text)} characters, {len(text.splitlines())} lines")
        
        if not self.current_project:
            self.new_project()
        
        # For now, continue with the original working method
        # Enhanced storyboard can be enabled via a checkbox later
        
        # Generate scenes (original method)
        self.logger.info("Importing modules...")
        from core.video.storyboard import StoryboardGenerator
        from core.video.llm_sync_v2 import LLMSyncAssistant
        
        self.logger.info("Creating StoryboardGenerator...")
        generator = StoryboardGenerator()
        
        # Get format type
        format_type = self.format_combo.currentText()
        if format_type == "Auto-detect":
            format_type = None
        
        # Get MIDI sync settings first (before calculating target duration)
        midi_timing = None
        sync_mode = "none"
        snap_strength = 0.8
        midi_duration_sec = None

        if self.current_project and self.current_project.midi_timing_data:
            midi_timing = self.current_project.midi_timing_data
            sync_mode = self.sync_mode_combo.currentText().lower()
            snap_strength = self.snap_strength_slider.value() / 100.0
            self.logger.info(f"MIDI sync enabled: mode={sync_mode}, snap={snap_strength:.0%}")
            if hasattr(midi_timing, 'duration_sec'):
                midi_duration_sec = midi_timing.duration_sec
                self.logger.info(f"MIDI duration: {midi_duration_sec:.1f}s")
        else:
            self.logger.info("No MIDI timing data available")

        # Get target duration - use MIDI duration if available, otherwise use GUI spinner
        if midi_duration_sec:
            # Use MIDI duration
            minutes = int(midi_duration_sec // 60)
            seconds = int(midi_duration_sec % 60)
            target_duration = f"00:{minutes:02d}:{seconds:02d}"
            self.logger.info(f"Using MIDI duration for scene generation: {target_duration} ({midi_duration_sec:.1f}s)")
        else:
            # Use GUI spinner value
            target_duration = f"00:{self.duration_spin.value():02d}:00"
            self.logger.info(f"Using GUI spinner duration for scene generation: {target_duration}")

        preset = self.pacing_combo.currentText().lower()
        self.logger.info(f"Settings: format={format_type}, duration={target_duration}, preset={preset}")
        
        # Check if LLM sync should be used
        llm_provider = self.llm_provider_combo.currentText()
        llm_model = self.llm_model_combo.currentText()
        use_llm_sync = llm_provider != "None" and llm_model
        
        self.logger.info(f"LLM sync: {use_llm_sync} (provider={llm_provider}, model={llm_model})")

        # Generate scenes with MIDI sync if available
        self.logger.info("Generating initial scenes...")
        self._log_to_console("📝 Generating storyboard scenes...", "INFO")
        scenes = generator.generate_scenes(
            text,
            target_duration=target_duration,
            preset=preset,
            format_hint=format_type,
            midi_timing_data=midi_timing,
            sync_mode=sync_mode,
            snap_strength=snap_strength
        )
        self.logger.info(f"Generated {len(scenes)} scenes before LLM sync")
        
        # Apply LLM sync if enabled and we have timing data
        if use_llm_sync and midi_timing:
            self.logger.info(f"Starting LLM sync with {llm_provider}/{llm_model}...")
            self._log_to_console(f"🎵 Starting LLM sync with {llm_provider}/{llm_model}...", "INFO")
            import time
            start_time = time.time()

            # Get config for API keys
            config = self.get_provider_config()
            sync_assistant = LLMSyncAssistant(provider=llm_provider.lower(), model=llm_model, config=config)
            
            # Extract lyrics (skip section markers)
            lyrics_lines = [scene.source for scene in scenes 
                          if not (scene.source.strip().startswith('[') and scene.source.strip().endswith(']'))]
            lyrics_text = '\n'.join(lyrics_lines)
            self.logger.info(f"Extracted {len(lyrics_lines)} lyric lines (excluding section markers)")
            
            sections = {}
            total_duration = sum(s.duration_sec for s in scenes)
            
            # Handle MidiTimingData object or dict
            if hasattr(midi_timing, 'duration_sec'):
                # It's a MidiTimingData object
                total_duration = midi_timing.duration_sec
                if hasattr(midi_timing, 'sections'):
                    sections = midi_timing.sections
            elif isinstance(midi_timing, dict):
                # It's a dict
                total_duration = midi_timing.get('duration_sec', sum(s.duration_sec for s in scenes))
                sections = midi_timing.get('sections', {})
            
            # Get audio file path if available
            audio_path = None
            if self.current_project.audio_tracks and len(self.current_project.audio_tracks) > 0:
                audio_track = self.current_project.audio_tracks[0]
                if audio_track.file_path:
                    audio_path = audio_track.file_path
                    self.logger.info(f"Using audio file for LLM sync: {audio_path}")
            else:
                self.logger.info("No audio file available for LLM sync")
            
            # Call LLM sync with audio and lyrics
            self.logger.info(f"Calling sync_with_llm with {len(lyrics_lines)} lyrics, duration={total_duration:.1f}s")
            if sections:
                self.logger.info(f"  Sections: {list(sections.keys())}")
            
            timed_lyrics = sync_assistant.sync_with_llm(
                lyrics=lyrics_text,
                audio_path=audio_path,
                total_duration=total_duration,
                sections=sections
            )

            elapsed = time.time() - start_time
            self.logger.info(f"LLM sync completed in {elapsed:.1f} seconds, got {len(timed_lyrics) if timed_lyrics else 0} timed lyrics")

            # Fill instrumental gaps between lyrics
            if timed_lyrics:
                self.logger.info("Detecting and filling instrumental gaps...")
                timed_lyrics_with_gaps = sync_assistant.fill_instrumental_gaps(
                    timed_lyrics=timed_lyrics,
                    total_duration=total_duration,
                    min_gap_duration=1.0  # Only create scenes for gaps >= 1 second
                )
                self.logger.info(f"After gap filling: {len(timed_lyrics_with_gaps)} total sections (lyrics + instrumental)")

                # Create new Scene objects for instrumental sections and insert them into scenes list
                from core.video.project import Scene
                new_scenes = []
                lyric_index = 0

                for timed_item in timed_lyrics_with_gaps:
                    if timed_item.text == "[Instrumental]":
                        # Create a new scene for instrumental section
                        instrumental_scene = Scene(
                            source="[Instrumental]",
                            prompt="",  # Will be filled by video prompt generation
                            duration_sec=timed_item.end_time - timed_item.start_time,
                            metadata={
                                'llm_start_time': timed_item.start_time,
                                'llm_end_time': timed_item.end_time,
                                'section': timed_item.section_type or 'instrumental',
                                'is_instrumental': True
                            }
                        )
                        new_scenes.append(instrumental_scene)
                        self.logger.info(
                            f"Created instrumental scene: {timed_item.start_time:.1f}-{timed_item.end_time:.1f}s "
                            f"({timed_item.end_time - timed_item.start_time:.1f}s)"
                        )
                    else:
                        # This is a lyric - find the corresponding original scene
                        # Skip section markers in original scenes
                        while lyric_index < len(scenes) and scenes[lyric_index].source.strip().startswith('[') and scenes[lyric_index].source.strip().endswith(']'):
                            new_scenes.append(scenes[lyric_index])  # Keep section markers
                            lyric_index += 1

                        if lyric_index < len(scenes):
                            new_scenes.append(scenes[lyric_index])
                            lyric_index += 1

                # Replace scenes with new list that includes instrumental sections
                scenes = new_scenes
                self.logger.info(f"Updated scenes list: {len(scenes)} total scenes (including instrumental)")

                # Now timed_lyrics should refer to the filled list for timing application
                timed_lyrics = timed_lyrics_with_gaps

            # Update scene timings based on LLM sync (skip section markers)
            if timed_lyrics:
                self.logger.info("Applying LLM timing to scenes...")
                lyric_index = 0
                updated_count = 0
                for i, scene in enumerate(scenes):
                    # Skip section markers like [Verse 1], [Chorus], but NOT [Instrumental]
                    # [Instrumental] is a real scene that needs timing from timed_lyrics
                    is_section_marker = (scene.source.strip().startswith('[') and
                                       scene.source.strip().endswith(']') and
                                       scene.source.strip() != '[Instrumental]')

                    if is_section_marker:
                        self.logger.debug(f"Scene {i}: Skipping section marker '{scene.source}'")
                        continue

                    # Check if this scene was batched (contains multiple lyrics)
                    batched_count = scene.metadata.get('batched_count', 1)

                    if batched_count > 1:
                        # Batched scene - need to sum durations from multiple LLM timings
                        if lyric_index + batched_count <= len(timed_lyrics):
                            # Get all timings for this batched scene
                            batch_timings = timed_lyrics[lyric_index:lyric_index + batched_count]

                            # Calculate total duration from first start to last end
                            first_timing = batch_timings[0]
                            last_timing = batch_timings[-1]
                            total_duration = last_timing.end_time - first_timing.start_time

                            scene.duration_sec = total_duration
                            scene.metadata['llm_start_time'] = first_timing.start_time
                            scene.metadata['llm_end_time'] = last_timing.end_time

                            # Update the lyric_timings metadata with LLM-precise timings
                            if 'lyric_timings' in scene.metadata:
                                for j, (lyric_timing, timed_lyric) in enumerate(zip(scene.metadata['lyric_timings'], batch_timings)):
                                    lyric_timing['start_sec'] = timed_lyric.start_time
                                    lyric_timing['end_sec'] = timed_lyric.end_time
                                    lyric_timing['duration_sec'] = timed_lyric.end_time - timed_lyric.start_time

                            if first_timing.section_type:
                                scene.metadata['section'] = first_timing.section_type

                            lyric_index += batched_count
                            updated_count += 1
                            self.logger.debug(f"Scene {i}: Batched {batched_count} lyrics, duration={total_duration:.1f}s")
                    else:
                        # Single lyric scene
                        if lyric_index < len(timed_lyrics):
                            timed_lyric = timed_lyrics[lyric_index]
                            scene.duration_sec = timed_lyric.end_time - timed_lyric.start_time
                            scene.metadata['llm_start_time'] = timed_lyric.start_time
                            scene.metadata['llm_end_time'] = timed_lyric.end_time
                            if timed_lyric.section_type:
                                scene.metadata['section'] = timed_lyric.section_type

                            lyric_index += 1
                            updated_count += 1

                self.logger.info(f"Applied LLM sync to {updated_count} scenes (matched {lyric_index}/{len(timed_lyrics)} lyrics)")
            else:
                self.logger.warning("No timed lyrics returned from LLM sync")
        else:
            if not use_llm_sync:
                self.logger.info("LLM sync disabled")
            if not midi_timing:
                self.logger.info("No MIDI timing available for LLM sync")

        # CRITICAL: Split then batch scenes AFTER instrumental insertion and timing
        # Split must happen BEFORE batching to ensure no scene exceeds 8 seconds
        # This must happen AFTER instrumentals to preserve 1:1 lyric-to-scene mapping
        from core.video.storyboard import StoryboardGenerator
        storyboard_gen = StoryboardGenerator(target_scene_duration=8.0)

        self.logger.info(f"Splitting long scenes (>{storyboard_gen.target_scene_duration}s)...")
        scenes = storyboard_gen.split_long_scenes(scenes, max_duration=storyboard_gen.target_scene_duration)
        self.logger.info(f"After splitting: {len(scenes)} scenes")

        self.logger.info(f"Batching {len(scenes)} scenes to aim for {storyboard_gen.target_scene_duration}-second optimal duration...")
        scenes = storyboard_gen._batch_scenes_for_optimal_duration(scenes)
        self.logger.info(f"After batching: {len(scenes)} scenes")

        # Apply prompt style to initial prompts (before LLM enhancement)
        # Note: LLM enhancement will also apply style, but this ensures style is set even without LLM
        prompt_style = self._get_current_style()
        if prompt_style and prompt_style.lower() != 'none':
            self.logger.info(f"🎨 Pre-applying prompt style '{prompt_style}' to initial {len(scenes)} scene prompts...")
            prompt_count = 0

            for i, scene in enumerate(scenes):
                # Apply to regular prompt field (always present after storyboard generation)
                if hasattr(scene, 'prompt') and scene.prompt:
                    # Skip section markers like [Verse 1], [Chorus], [Instrumental]
                    if not (scene.prompt.strip().startswith('[') and scene.prompt.strip().endswith(']')):
                        if not scene.prompt.lower().startswith(prompt_style.lower()):
                            scene.prompt = f"{prompt_style} style: {scene.prompt}"
                            prompt_count += 1
                            self.logger.debug(f"Scene {i}: Applied style to prompt")

            self.logger.info(f"✓ Style '{prompt_style}' pre-applied to {prompt_count} initial prompts (will be preserved during LLM enhancement)")
        else:
            self.logger.debug("No prompt style to apply (style is 'None' or empty)")

        # Update project with ALL current settings
        self.update_project_from_ui()  # This now saves all settings including LLM

        # Update specific storyboard-related fields
        self.current_project.scenes = scenes
        self.current_project.input_text = text
        self.current_project.sync_mode = sync_mode
        self.current_project.snap_strength = snap_strength
        
        # Log scenes being added
        self.logger.info(f"Generated {len(scenes)} scenes for project")
        
        # Automatically enhance prompts if LLM is enabled
        if llm_provider != "None" and llm_model:
            self.logger.info(f"Auto-enhancing prompts with {llm_provider}/{llm_model}...")
            self._enhance_scene_prompts(scenes, llm_provider, llm_model)
        
        # Update karaoke settings if enabled
        if self.karaoke_group.isChecked():
            from core.video.karaoke_renderer import KaraokeConfig
            self.current_project.karaoke_config = KaraokeConfig(
                enabled=True,
                style=self.karaoke_style_combo.currentText().lower().replace(" ", "_"),
                position=self.karaoke_position_combo.currentText().lower(),
                font_size=self.karaoke_font_spin.value()
            )
            
            # Set export formats
            export_formats = []
            if self.export_lrc_check.isChecked():
                export_formats.append("lrc")
            if self.export_srt_check.isChecked():
                export_formats.append("srt")
            if self.export_ass_check.isChecked():
                export_formats.append("ass")
            self.current_project.karaoke_export_formats = export_formats
        
        self.populate_scene_table()
        self.update_ui_state()
        self.project_changed.emit(self.current_project)
        
        # Auto-save after generating storyboard to preserve scenes
        self.save_project()
        self.logger.info(f"Auto-saved project after storyboard generation with {len(scenes)} scenes")
    
    def get_provider_config(self) -> Dict[str, Any]:
        """Get provider configuration including API keys."""
        config = {}

        # Use ConfigManager to get API keys (has keyring + config file fallback)
        from core import ConfigManager
        config_manager = ConfigManager()

        # Get OpenAI key (with both keyring and config file fallback)
        openai_key = config_manager.get_api_key('openai')
        if openai_key:
            config['openai_api_key'] = openai_key

        # Get Anthropic/Claude key (with both keyring and config file fallback)
        anthropic_key = config_manager.get_api_key('anthropic')
        if anthropic_key:
            config['anthropic_api_key'] = anthropic_key

        # Get Google/Gemini key (with both keyring and config file fallback)
        google_key = config_manager.get_api_key('google')
        if google_key:
            config['google_api_key'] = google_key

        # Add LM Studio and Ollama endpoints if configured
        if hasattr(self.video_config, 'config'):
            llm_providers = self.video_config.config.get('llm_providers', {})
            if 'ollama' in llm_providers:
                config['ollama_endpoint'] = llm_providers['ollama'].get('endpoint', 'http://localhost:11434')
            if 'lmstudio' in llm_providers:
                config['lmstudio_endpoint'] = llm_providers['lmstudio'].get('endpoint', 'http://localhost:1234/v1')

        return config
    
    def _generate_enhanced_storyboard(self, text: str):
        """Generate storyboard using enhanced provider-specific methods with continuity"""
        try:
            from core.video.storyboard_v2 import EnhancedStoryboardGenerator
            from core.video.image_continuity import ImageContinuityManager
            from core.video.llm_sync_v2 import LLMSyncAssistant
            
            # Get configuration
            llm_provider = self.llm_provider_combo.currentText().lower()
            llm_model = self.llm_model_combo.currentText()
            project_name = self.project_name.text() or "Untitled"
            
            # Get target duration
            target_duration = self.duration_spin.value()
            
            # Get style settings
            prompt_style = self._get_current_style()
            aspect_ratio = self.aspect_combo.currentText()
            
            # Initialize enhanced generator
            config = self.get_provider_config()
            from core.video.prompt_engine import UnifiedLLMProvider
            llm = UnifiedLLMProvider(config)
            
            generator = EnhancedStoryboardGenerator(llm)

            # Get video render method for batching
            video_provider = self.video_provider_combo.currentText()
            veo_model = self.veo_model_combo.currentText() if hasattr(self, 'veo_model_combo') else None
            render_method = None
            if video_provider == "Gemini Veo" and veo_model:
                render_method = veo_model  # e.g., "veo-3.1-generate-001"

            # Generate storyboard with provider-specific approach
            self.logger.info(f"Generating enhanced storyboard using {llm_provider} approach")
            if render_method:
                self.logger.info(f"Render method: {render_method} - will generate batched prompts for Veo 3.1")

            style_guide, scenes, veo_batches = generator.generate_storyboard(
                lyrics=text,
                title=project_name,
                duration=target_duration,
                provider=llm_provider,
                model=llm_model,
                style=prompt_style,
                negatives=self.negative_prompt.text() or "low quality, blurry",
                render_method=render_method
            )

            if not scenes:
                self.logger.warning("No scenes generated")
                dialog_manager = get_dialog_manager(self)
                dialog_manager.show_warning("Generation Failed", "Failed to generate scenes from lyrics")
                return

            self.logger.info(f"Generated {len(scenes)} scenes with enhanced approach")
            if veo_batches:
                self.logger.info(f"Generated {len(veo_batches)} Veo batched prompts for 8-second clips")
            
            # Initialize continuity manager
            continuity_mgr = ImageContinuityManager()
            if style_guide:
                continuity_mgr.initialize_project_context(
                    project_name,
                    {
                        'character': style_guide.character,
                        'setting': style_guide.setting,
                        'mood': style_guide.mood,
                        'cinematic_style': style_guide.cinematic_style
                    }
                )
                
                # Store style guide in project metadata
                self.current_project.metadata['style_guide'] = {
                    'character': style_guide.character,
                    'setting': style_guide.setting,
                    'mood': style_guide.mood,
                    'cinematic_style': style_guide.cinematic_style
                }
            
            # Apply MIDI sync if available
            midi_timing = None
            sync_mode = "none"
            snap_strength = 0.8
            
            if self.current_project and self.current_project.midi_timing_data:
                midi_timing = self.current_project.midi_timing_data
                sync_mode = self.sync_mode_combo.currentText().lower()
                snap_strength = self.snap_strength_slider.value() / 100.0
                
                self.logger.info(f"Applying MIDI sync with mode={sync_mode}, snap={snap_strength:.0%}")
                
                # Use LLM sync for timing adjustment
                sync_assistant = LLMSyncAssistant(provider=llm_provider, model=llm_model, config=config)
                
                # Extract lyrics for sync
                lyrics_lines = [scene.source for scene in scenes 
                              if not (scene.source.strip().startswith('[') and scene.source.strip().endswith(']'))]
                lyrics_text = '\n'.join(lyrics_lines)
                
                sections = {}
                total_duration = target_duration
                
                # Handle MidiTimingData
                if hasattr(midi_timing, 'duration_sec'):
                    total_duration = midi_timing.duration_sec
                    if hasattr(midi_timing, 'sections'):
                        sections = midi_timing.sections
                
                # Get audio file path if available
                audio_path = None
                if self.current_project.audio_tracks and len(self.current_project.audio_tracks) > 0:
                    audio_track = self.current_project.audio_tracks[0]
                    if audio_track.file_path:
                        audio_path = audio_track.file_path
                
                # Apply timing
                timed_lyrics = sync_assistant.sync_with_llm(
                    lyrics=lyrics_text,
                    audio_path=audio_path,
                    total_duration=total_duration,
                    sections=sections
                )

                # Fill instrumental gaps
                if timed_lyrics:
                    self.logger.info("Detecting and filling instrumental gaps in enhanced storyboard...")
                    timed_lyrics_with_gaps = sync_assistant.fill_instrumental_gaps(
                        timed_lyrics=timed_lyrics,
                        total_duration=total_duration,
                        min_gap_duration=1.0
                    )
                    self.logger.info(f"After gap filling: {len(timed_lyrics_with_gaps)} total sections")

                    # Create new Scene objects for instrumental sections
                    from core.video.project import Scene
                    new_scenes = []
                    lyric_index = 0

                    for timed_item in timed_lyrics_with_gaps:
                        if timed_item.text == "[Instrumental]":
                            instrumental_scene = Scene(
                                source="[Instrumental]",
                                prompt="",
                                duration_sec=timed_item.end_time - timed_item.start_time,
                                metadata={
                                    'llm_start_time': timed_item.start_time,
                                    'llm_end_time': timed_item.end_time,
                                    'section': timed_item.section_type or 'instrumental',
                                    'is_instrumental': True
                                }
                            )
                            new_scenes.append(instrumental_scene)
                        else:
                            while lyric_index < len(scenes) and scenes[lyric_index].source.strip().startswith('[') and scenes[lyric_index].source.strip().endswith(']'):
                                new_scenes.append(scenes[lyric_index])
                                lyric_index += 1
                            if lyric_index < len(scenes):
                                new_scenes.append(scenes[lyric_index])
                                lyric_index += 1

                    scenes = new_scenes
                    timed_lyrics = timed_lyrics_with_gaps
                    self.logger.info(f"Updated scenes list: {len(scenes)} total scenes (including instrumental)")

                # Update scene timings
                if timed_lyrics:
                    self.logger.info(f"Applying enhanced timing to scenes...")
                    lyric_index = 0
                    for i, scene in enumerate(scenes):
                        if scene.source.strip().startswith('[') and scene.source.strip().endswith(']'):
                            continue

                        # Check if this scene was batched (contains multiple lyrics)
                        batched_count = scene.metadata.get('batched_count', 1)

                        if batched_count > 1:
                            # Batched scene - need to sum durations from multiple LLM timings
                            if lyric_index + batched_count <= len(timed_lyrics):
                                # Get all timings for this batched scene
                                batch_timings = timed_lyrics[lyric_index:lyric_index + batched_count]

                                # Calculate total duration from first start to last end
                                first_timing = batch_timings[0]
                                last_timing = batch_timings[-1]
                                total_duration = last_timing.end_time - first_timing.start_time

                                scene.duration_sec = total_duration
                                scene.metadata['llm_start_time'] = first_timing.start_time
                                scene.metadata['llm_end_time'] = last_timing.end_time

                                # Update the lyric_timings metadata with LLM-precise timings
                                if 'lyric_timings' in scene.metadata:
                                    for j, (lyric_timing, timed_lyric) in enumerate(zip(scene.metadata['lyric_timings'], batch_timings)):
                                        lyric_timing['start_sec'] = timed_lyric.start_time
                                        lyric_timing['end_sec'] = timed_lyric.end_time
                                        lyric_timing['duration_sec'] = timed_lyric.end_time - timed_lyric.start_time

                                if first_timing.section_type:
                                    scene.metadata['section'] = first_timing.section_type

                                lyric_index += batched_count
                        else:
                            # Single lyric scene
                            if lyric_index < len(timed_lyrics):
                                timed_lyric = timed_lyrics[lyric_index]
                                scene.duration_sec = timed_lyric.end_time - timed_lyric.start_time
                                scene.metadata['llm_start_time'] = timed_lyric.start_time
                                scene.metadata['llm_end_time'] = timed_lyric.end_time
                                if timed_lyric.section_type:
                                    scene.metadata['section'] = timed_lyric.section_type
                                lyric_index += 1
            
            # CRITICAL: Split then batch scenes AFTER instrumental insertion and timing
            # Split must happen BEFORE batching to ensure no scene exceeds 8 seconds
            # This must happen AFTER instrumentals to preserve 1:1 lyric-to-scene mapping
            from core.video.storyboard import StoryboardGenerator
            storyboard_gen = StoryboardGenerator(target_scene_duration=8.0)

            self.logger.info(f"Splitting long scenes (>{storyboard_gen.target_scene_duration}s)...")
            scenes = storyboard_gen.split_long_scenes(scenes, max_duration=storyboard_gen.target_scene_duration)
            self.logger.info(f"After splitting: {len(scenes)} scenes")

            self.logger.info(f"Batching {len(scenes)} scenes to aim for {storyboard_gen.target_scene_duration}-second optimal duration...")
            scenes = storyboard_gen._batch_scenes_for_optimal_duration(scenes)
            self.logger.info(f"After batching: {len(scenes)} scenes")

            # Store aspect ratio in scenes for continuity
            for scene in scenes:
                scene.metadata['aspect_ratio'] = aspect_ratio
                scene.metadata['continuity_enabled'] = True

            # Update project
            self.current_project.scenes = scenes
            self.current_project.veo_batches = veo_batches  # Store batched prompts for Veo 3.1
            self.current_project.input_text = text
            self.current_project.sync_mode = sync_mode
            self.current_project.snap_strength = snap_strength
            
            # Update karaoke settings if enabled
            if self.karaoke_group.isChecked():
                from core.video.karaoke_renderer import KaraokeConfig
                self.current_project.karaoke_config = KaraokeConfig(
                    enabled=True,
                    style=self.karaoke_style_combo.currentText().lower().replace(" ", "_"),
                    position=self.karaoke_position_combo.currentText().lower(),
                    font_size=self.karaoke_font_spin.value()
                )
            
            # Update UI
            self.populate_scene_table()
            self.update_ui_state()
            self.project_changed.emit(self.current_project)
            
            # Auto-save
            self.save_project()
            self.logger.info(f"Enhanced storyboard generation complete with {len(scenes)} scenes")
            
        except Exception as e:
            self.logger.error(f"Enhanced storyboard generation failed: {e}", exc_info=True)
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_error("Generation Failed", f"Failed to generate enhanced storyboard: {e}")
            # Fall back to regular generation
            self._generate_regular_storyboard(text)
    
    def _generate_regular_storyboard(self, text: str):
        """Fallback to regular storyboard generation"""
        from core.video.storyboard import StoryboardGenerator
        from core.video.llm_sync_v2 import LLMSyncAssistant
        
        generator = StoryboardGenerator()
        
        # Get format type
        format_type = self.format_combo.currentText()
        if format_type == "Auto-detect":
            format_type = None
        
        # Get target duration
        target_duration = f"00:{self.duration_spin.value():02d}:00"
        preset = self.pacing_combo.currentText().lower()
        
        # Continue with original generation logic...
        # (The rest of the original generate_storyboard method)
    
    def _enhance_scene_prompts(self, scenes: list, provider: str, model: str):
        """Enhance scene prompts using LLM."""
        try:
            from core.video.prompt_engine import UnifiedLLMProvider, PromptStyle
            from core.video.continuity_helper import get_continuity_helper

            # Get API keys
            config = self.get_provider_config()

            # Validate API key for selected provider BEFORE starting
            provider_key_map = {
                'openai': 'openai_api_key',
                'anthropic': 'anthropic_api_key',
                'claude': 'anthropic_api_key',
                'google': 'google_api_key',
                'gemini': 'google_api_key'
            }

            provider_lower = provider.lower()
            required_key = provider_key_map.get(provider_lower)

            if required_key and not config.get(required_key):
                error_msg = f"⚠️ {provider} API key not found. Please set it in Settings tab."
                self.logger.warning(error_msg)
                self._log_to_console(error_msg, "WARNING")
                self._log_to_console("Using fallback prompts (original lyrics with basic enhancements)", "INFO")
                # Continue anyway - will use fallback prompts

            llm = UnifiedLLMProvider(config)

            if not llm.is_available():
                self.logger.warning("LLM provider not available for prompt enhancement")
                return
            
            # Get continuity helper for adding continuity hints
            continuity = get_continuity_helper()
            project_name = self.project_name.text() or "untitled"
            
            # Get prompt style
            prompt_style = self._get_current_style()
            style_map = {
                "Cinematic": PromptStyle.CINEMATIC,
                "Artistic": PromptStyle.ARTISTIC,
                "Photorealistic": PromptStyle.PHOTOREALISTIC,
                "Animated": PromptStyle.ANIMATED,
                "Documentary": PromptStyle.DOCUMENTARY,
                "Abstract": PromptStyle.ABSTRACT
            }
            style = style_map.get(prompt_style, PromptStyle.CINEMATIC)
            
            # Get aspect ratio for continuity
            aspect_ratio = self.aspect_combo.currentText()

            # BATCH ENHANCE: Process all scene prompts in ONE API call
            enhanced_count = 0
            try:
                # Collect all original scene texts
                original_texts = [scene.source for scene in scenes]

                self.logger.info(f"🚀 BATCH enhancing {len(original_texts)} scene prompts in ONE API call...")
                self._log_to_console(f"🚀 BATCH processing {len(original_texts)} scenes in 1 API call...", "INFO")

                # Use batch_enhance for efficiency (ONE API call for all scenes)
                enhanced_prompts = llm.batch_enhance(
                    original_texts,
                    provider=provider.lower(),
                    model=model,
                    style=style,
                    temperature=0.7
                )

                # Apply enhanced prompts to scenes
                for i, (scene, enhanced) in enumerate(zip(scenes, enhanced_prompts)):
                    if enhanced and enhanced != scene.source:
                        # Add continuity hints only if enabled
                        if self.enable_continuity_checkbox.isChecked():
                            enhanced = continuity.enhance_prompt_for_continuity(
                                enhanced,
                                scene_index=i,
                                project_id=project_name,
                                provider=provider,
                                aspect_ratio=aspect_ratio
                            )

                        # Prepend prompt style if not already present
                        if prompt_style and prompt_style.lower() != 'none':
                            if not enhanced.lower().startswith(prompt_style.lower()):
                                enhanced = f"{prompt_style} style: {enhanced}"

                        scene.prompt = enhanced
                        enhanced_count += 1

                if enhanced_count == len(scenes):
                    self.logger.info(f"✅ Successfully enhanced {enhanced_count}/{len(scenes)} scenes with LLM")
                    self._log_to_console(f"✅ Successfully enhanced {enhanced_count}/{len(scenes)} scenes with LLM", "SUCCESS")
                elif enhanced_count > 0:
                    self.logger.info(f"⚠️ Enhanced {enhanced_count}/{len(scenes)} scenes (some used fallback)")
                    self._log_to_console(f"⚠️ Enhanced {enhanced_count}/{len(scenes)} scenes (some used fallback)", "WARNING")
                else:
                    self.logger.warning(f"⚠️ All scenes using fallback prompts (LLM unavailable)")
                    self._log_to_console(f"⚠️ All scenes using fallback prompts (check API key)", "WARNING")

            except Exception as e:
                self.logger.error(f"❌ Batch enhancement failed: {e}")
                self._log_to_console(f"❌ Batch enhancement failed: {str(e)}", "ERROR")
                self._log_to_console(f"Please check your API key and try again", "WARNING")
                return  # Stop processing - don't fall back to individual calls
            
        except Exception as e:
            self.logger.error(f"Failed to enhance prompts: {e}")
    
    def _create_top_aligned_widget(self, widget):
        """Wrap widget in container aligned to top of cell"""
        from PySide6.QtWidgets import QVBoxLayout
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)
        layout.addStretch()  # Push widget to top
        return container

    def _get_cell_widget(self, row: int, col: int):
        """Get the actual widget from a cell (unwraps container if needed)"""
        container = self.scene_table.cellWidget(row, col)
        if not container:
            return None
        # If it's a container with a layout, get the first widget
        layout = container.layout()
        if layout and layout.count() > 0:
            return layout.itemAt(0).widget()
        # Otherwise return the container itself (shouldn't happen)
        return container

    def populate_scene_table(self):
        """Populate scene table with project scenes (10-column Veo 3.1 layout)"""
        if not self.current_project:
            return

        self.scene_table.setRowCount(len(self.current_project.scenes))

        total_duration = 0
        for i, scene in enumerate(self.current_project.scenes):
            # Column 0: Scene # (use label widget for proper top alignment)
            scene_num_label = QLabel(str(i + 1))
            scene_num_label.setAlignment(Qt.AlignTop | Qt.AlignCenter)
            scene_num_label.setStyleSheet("padding: 2px;")
            self.scene_table.setCellWidget(i, 0, self._create_top_aligned_widget(scene_num_label))

            # Column 1: Start Frame (FrameButton widget)
            start_frame_btn = FrameButton(frame_type="start", parent=self)
            # ONLY use approved_image - DO NOT fall back to scene.images[0]
            # If user cleared the start frame, respect that choice (for reference images mode)
            start_frame_path = scene.approved_image if scene.approved_image and scene.approved_image.exists() else None
            if start_frame_path:
                start_frame_btn.set_frame(start_frame_path, auto_linked=False)

            # Connect ALL frame operations through FrameButton's built-in signals
            start_frame_btn.generate_requested.connect(lambda idx=i: self.generate_single_scene(idx))
            start_frame_btn.view_requested.connect(lambda idx=i: self._view_start_frame(idx))
            start_frame_btn.select_requested.connect(lambda idx=i: self._select_start_frame_variant(idx))
            start_frame_btn.select_from_scene_requested.connect(lambda idx=i: self._select_start_frame_from_scenes(idx))
            start_frame_btn.clear_requested.connect(lambda idx=i: self._clear_start_frame(idx))
            start_frame_btn.load_image_requested.connect(lambda idx=i: self._load_start_frame_image(idx))
            start_frame_btn.use_last_generated_requested.connect(lambda idx=i: self._use_last_generated_for_start_frame(idx))

            self.scene_table.setCellWidget(i, 1, self._create_top_aligned_widget(start_frame_btn))

            # Column 2: End Frame (FrameButton widget)
            end_frame_btn = FrameButton(frame_type="end", parent=self)
            is_auto_linked = scene.end_frame_auto_linked
            end_frame_path = scene.end_frame
            if end_frame_path:
                end_frame_btn.set_frame(end_frame_path, auto_linked=is_auto_linked)

            # Connect ALL end frame operations through FrameButton
            end_frame_btn.generate_requested.connect(lambda idx=i: self._generate_end_frame(idx))
            end_frame_btn.view_requested.connect(lambda idx=i: self._view_end_frame(idx))
            end_frame_btn.select_requested.connect(lambda idx=i: self._select_end_frame_variant(idx))
            end_frame_btn.select_from_scene_requested.connect(lambda idx=i: self._select_end_frame_from_scenes(idx))
            end_frame_btn.clear_requested.connect(lambda idx=i: self._clear_end_frame(idx))
            # auto_link_requested removed - auto-linking disabled
            end_frame_btn.load_image_requested.connect(lambda idx=i: self._load_end_frame_image(idx))
            end_frame_btn.use_last_generated_requested.connect(lambda idx=i: self._use_last_generated_for_end_frame(idx))

            self.scene_table.setCellWidget(i, 2, self._create_top_aligned_widget(end_frame_btn))

            # Column 3: Reference Images (ReferenceImagesWidget with up to 3 slots)
            ref_images_widget = ReferenceImagesWidget(max_references=3, parent=self)
            # Load existing reference images from scene
            for ref_idx, ref_image in enumerate(scene.reference_images[:3]):  # Max 3
                if ref_image and ref_image.path:
                    ref_images_widget.set_reference_image(ref_idx, ref_image.path, ref_image.auto_linked)

            # Connect all reference image signals
            ref_images_widget.reference_changed.connect(lambda slot_idx, path, scene_idx=i: self._on_reference_image_changed(scene_idx, slot_idx, path))
            ref_images_widget.select_from_scene_requested.connect(lambda slot_idx, scene_idx=i: self._select_reference_from_scenes(scene_idx, slot_idx))
            ref_images_widget.view_requested.connect(lambda slot_idx, scene_idx=i: self._view_reference_image(scene_idx, slot_idx))
            ref_images_widget.load_requested.connect(lambda slot_idx, scene_idx=i: self._load_reference_image(scene_idx, slot_idx))

            self.scene_table.setCellWidget(i, 3, self._create_top_aligned_widget(ref_images_widget))

            # Column 4: Video button (VideoButton widget with preview)
            video_btn = VideoButton(parent=self)
            has_video_prompt = bool(hasattr(scene, 'video_prompt') and scene.video_prompt and len(scene.video_prompt) > 0)
            video_path = scene.video_clip if scene.video_clip else None
            first_frame_path = scene.first_frame if hasattr(scene, 'first_frame') else None
            uses_veo_31 = scene.uses_veo_31() if hasattr(scene, 'uses_veo_31') else False

            video_btn.set_video_state(video_path, first_frame_path, has_video_prompt, uses_veo_31)

            # Install event filter for double-click detection
            video_btn.installEventFilter(self)
            video_btn.setProperty("scene_index", i)
            video_btn.setProperty("is_video_btn", True)

            # Connect signals
            video_btn.clicked_load_frame.connect(lambda idx=i: self._load_video_first_frame_in_panel(idx))
            video_btn.regenerate_requested.connect(lambda idx=i: self.generate_video_clip(idx))
            video_btn.clear_requested.connect(lambda idx=i: self._clear_video(idx))
            video_btn.play_requested.connect(lambda idx=i: self._play_video_in_panel(idx))
            video_btn.select_existing_requested.connect(lambda idx=i: self._select_existing_video(idx))

            self.scene_table.setCellWidget(i, 4, self._create_top_aligned_widget(video_btn))

            # Column 5: Time (use label widget for proper top alignment)
            time_label = QLabel(f"{scene.duration_sec:.1f}")
            time_label.setAlignment(Qt.AlignTop | Qt.AlignCenter)

            # Validate duration: must be <= 8.0 seconds
            if scene.duration_sec > 8.0:
                time_label.setStyleSheet("padding: 2px; background-color: #ffcccc; color: #cc0000; font-weight: bold;")
                time_label.setToolTip(f"⚠️ WARNING: Scene duration ({scene.duration_sec:.1f}s) exceeds maximum of 8.0s")
            else:
                time_label.setStyleSheet("padding: 2px;")

            self.scene_table.setCellWidget(i, 5, self._create_top_aligned_widget(time_label))

            # Column 6: Wrap button (⤵️)
            wrap_btn = QPushButton("⤵️")
            wrap_btn.setToolTip("Toggle text wrapping for this row")
            wrap_btn.setFixedHeight(30)  # Match LLM button height
            wrap_btn.setMinimumWidth(40)
            wrap_btn.setMaximumWidth(50)
            wrap_btn.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    padding: 2px;
                    border: 2px solid #ccc;
                    border-radius: 3px;
                    background-color: #f5f5f5;
                }
                QPushButton:hover {
                    border-color: #999;
                    background-color: #e8e8e8;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
                QPushButton:checked {
                    background-color: #d0e8ff;
                    border-color: #0078d4;
                }
            """)
            wrap_btn.setCheckable(True)

            # Check if row is already wrapped (from metadata or previous state)
            is_wrapped = scene.metadata.get('wrapped', False)
            wrap_btn.setChecked(is_wrapped)

            # Connect to toggle handler
            wrap_btn.clicked.connect(lambda checked, idx=i: self._toggle_row_wrap(idx, checked))
            self.scene_table.setCellWidget(i, 6, self._create_top_aligned_widget(wrap_btn))

            # Column 7: Source text (use label widget for proper top alignment)
            # Show full text without truncation
            source_label = QLabel(scene.source if scene.source else "")
            source_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            source_label.setWordWrap(True)  # Allow wrapping for long text
            source_label.setStyleSheet("padding: 2px;")
            # Set tooltip with full source text, wrapped at 80 characters
            if scene.source:
                wrapped_tooltip = '\n'.join(textwrap.wrap(scene.source, width=80))
                source_label.setToolTip(wrapped_tooltip)
            else:
                source_label.setToolTip("")
            self.scene_table.setCellWidget(i, 7, self._create_top_aligned_widget(source_label))

            # Column 8: Environment (editable text field)
            environment_edit = QLineEdit()
            environment_edit.setPlaceholderText("e.g., bedroom, abstract, forest...")
            environment_edit.setText(scene.environment if hasattr(scene, 'environment') and scene.environment else "")
            environment_edit.setStyleSheet("padding: 4px;")
            # Connect to auto-save
            environment_edit.textChanged.connect(
                lambda text, idx=i: self._on_environment_changed(idx, text)
            )
            self.scene_table.setCellWidget(i, 11, self._create_top_aligned_widget(environment_edit))

            # Column 9: Video Prompt (PromptFieldWidget with LLM + undo/redo) - MOVED
            video_prompt_widget = PromptFieldWidget(
                placeholder="Click ✨ to generate video motion prompt",
                parent=self
            )
            video_prompt_widget.set_text(scene.video_prompt if hasattr(scene, 'video_prompt') else "")

            # Connect text changes to auto-save
            video_prompt_widget.text_changed.connect(
                lambda text, idx=i: self._on_video_prompt_changed(idx, text)
            )

            # Connect LLM button to dialog
            video_prompt_widget.llm_requested.connect(
                lambda idx=i: self._show_video_prompt_llm_dialog(idx)
            )

            self.scene_table.setCellWidget(i, 9, self._create_top_aligned_widget(video_prompt_widget))

            # Column 10: Start Prompt (PromptFieldWidget with LLM + undo/redo) - MOVED
            start_prompt_widget = PromptFieldWidget(
                placeholder="Click ✨ to generate start frame prompt",
                parent=self
            )
            start_prompt_widget.set_text(scene.prompt)

            # Connect text changes to auto-save
            start_prompt_widget.text_changed.connect(
                lambda text, idx=i: self._on_start_prompt_changed(idx, text)
            )

            # Connect LLM button to dialog
            start_prompt_widget.llm_requested.connect(
                lambda idx=i: self._show_start_prompt_llm_dialog(idx)
            )

            self.scene_table.setCellWidget(i, 10, self._create_top_aligned_widget(start_prompt_widget))

            # Column 11: End Prompt (PromptFieldWidget with LLM + undo/redo) - MOVED
            end_prompt_widget = PromptFieldWidget(
                placeholder="Optional: click ✨ for end frame prompt",
                parent=self
            )
            end_prompt_widget.set_text(scene.end_prompt)

            # Connect text changes to auto-save
            end_prompt_widget.text_changed.connect(
                lambda text, idx=i: self._on_end_prompt_changed(idx, text)
            )

            # Connect LLM button to dialog
            end_prompt_widget.llm_requested.connect(
                lambda idx=i: self._show_end_prompt_llm_dialog(idx)
            )

            self.scene_table.setCellWidget(i, 11, self._create_top_aligned_widget(end_prompt_widget))

            # Apply initial wrap state
            if is_wrapped:
                self._apply_row_wrap(i, True)

            total_duration += scene.duration_sec

        # Update total duration
        minutes = int(total_duration // 60)
        seconds = int(total_duration % 60)
        self.total_duration_label.setText(f"Total: {minutes}:{seconds:02d}")

        # Check for invalid scene durations (> 8.0 seconds)
        invalid_scenes = [i+1 for i, scene in enumerate(self.current_project.scenes) if scene.duration_sec > 8.0]
        if invalid_scenes:
            self.duration_warning_label.setText(f"⚠️ {len(invalid_scenes)} scene(s) exceed 8.0s limit (#{', #'.join(map(str, invalid_scenes))})")
            self.duration_warning_label.setToolTip("Video generation is blocked until all scenes are 8.0 seconds or less. Please manually adjust the Time column.")
            self.duration_warning_label.setVisible(True)
        else:
            self.duration_warning_label.setVisible(False)

        # Refresh wizard after populating scenes
        self._refresh_wizard()

        # Restore column widths and scrollbar positions (deferred to ensure table is fully rendered)
        QTimer.singleShot(50, self._restore_column_widths)
        QTimer.singleShot(100, self._restore_scrollbar_positions)

    def enhance_single_prompt(self, scene_index: int):
        """Enhance a single scene's prompt with AI"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        try:
            # Get LLM settings
            provider = self.llm_provider_combo.currentText()
            model = self.llm_model_combo.currentText()
            prompt_style = self._get_current_style()

            # Map style to enum
            from core.video.prompt_engine import PromptStyle
            style_map = {
                "Cinematic": PromptStyle.CINEMATIC,
                "Artistic": PromptStyle.ARTISTIC,
                "Photorealistic": PromptStyle.PHOTOREALISTIC,
                "Animated": PromptStyle.ANIMATED,
                "Documentary": PromptStyle.DOCUMENTARY,
                "Abstract": PromptStyle.ABSTRACT
            }
            style = style_map.get(prompt_style, PromptStyle.CINEMATIC)

            # Create LLM provider
            from core.video.prompt_engine import UnifiedLLMProvider
            api_config = {
                'openai_api_key': self.config.get('openai_api_key'),
                'anthropic_api_key': self.config.get('anthropic_api_key'),
                'google_api_key': self.config.get('google_api_key')
            }
            llm = UnifiedLLMProvider(api_config)

            # Get aspect ratio for resolution hint
            aspect_ratio = self.aspect_combo.currentText()

            # Enhance the prompt
            original = scene.source
            enhanced = llm.enhance_prompt(
                original,
                provider=provider.lower(),
                model=model,
                style=style,
                temperature=0.7,
                max_tokens=150
            )

            if enhanced and enhanced != original:
                # Add continuity hints if enabled
                if self.enable_continuity_checkbox.isChecked():
                    from core.video.continuity import ContinuityManager
                    continuity = ContinuityManager()
                    project_name = self.current_project.metadata.get('title', 'Untitled')
                    enhanced = continuity.enhance_prompt_for_continuity(
                        enhanced,
                        scene_index=scene_index,
                        project_id=project_name,
                        provider=provider,
                        aspect_ratio=aspect_ratio
                    )

                # Update scene
                scene.prompt = enhanced

                # Save project
                self.save_project()

                # Refresh table
                self.populate_scene_table()

                self.logger.info(f"Enhanced prompt for scene {scene_index + 1}")
            else:
                self.logger.warning(f"No enhancement for scene {scene_index + 1}")

        except Exception as e:
            self.logger.error(f"Failed to enhance prompt for scene {scene_index + 1}: {e}")
            QMessageBox.warning(self, "Enhancement Failed", f"Failed to enhance prompt: {e}")

    def revert_single_prompt(self, scene_index: int):
        """Revert a single scene's prompt to original source text"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        # Revert to source
        scene.prompt = scene.source

        # Save project
        self.save_current_project()

        # Refresh table
        self.populate_scene_table()

        self.logger.info(f"Reverted prompt for scene {scene_index + 1}")

    def eventFilter(self, obj, event):
        """Event filter for scene table to handle image preview on hover and video button double-clicks"""
        # Handle double-click on video button to regenerate
        if isinstance(obj, QPushButton) and obj.property("is_video_btn"):
            if event.type() == QEvent.MouseButtonDblClick:
                scene_index = obj.property("scene_index")
                if scene_index is not None:
                    self.generate_video_clip(scene_index)
                    return True

        # Safety check: ensure scene_table still exists
        try:
            if not hasattr(self, 'scene_table') or not self.scene_table:
                return super().eventFilter(obj, event)

            viewport = self.scene_table.viewport()
        except (RuntimeError, AttributeError):
            # Widget has been deleted, remove event filter
            return super().eventFilter(obj, event)

        if obj == viewport:
            if event.type() == QEvent.Wheel:
                # Custom wheel scrolling: scroll by content line (row height), not by viewport row count
                # Get vertical scrollbar
                v_scrollbar = self.scene_table.verticalScrollBar()
                if v_scrollbar:
                    # Get row height
                    row_height = self.scene_table.verticalHeader().defaultSectionSize()

                    # Get wheel delta (120 units per notch on most mice)
                    delta = event.angleDelta().y()

                    # Scroll by one row height per wheel notch
                    scroll_amount = -(delta // 120) * row_height

                    # Apply scroll
                    new_value = v_scrollbar.value() + scroll_amount
                    v_scrollbar.setValue(new_value)

                    # Accept event to prevent default scrolling
                    return True

            elif event.type() == QEvent.MouseMove:
                # Get the item under the cursor
                pos = event.pos()
                item = self.scene_table.itemAt(pos)

                if item and item.column() == 4:  # Preview column (now column 4, swapped with video button)
                    row = item.row()
                    if self.current_project and row < len(self.current_project.scenes):
                        scene = self.current_project.scenes[row]
                        # ALWAYS prioritize source images first (the generated image), not last frame
                        preview_path = None
                        if scene.images and len(scene.images) > 0:
                            # Handle both Path objects and ImageVariant objects
                            img = scene.images[0]
                            preview_path = img.path if hasattr(img, 'path') else img
                        elif scene.last_frame and scene.last_frame.exists():
                            # Only show last frame if no images available
                            preview_path = scene.last_frame

                        if preview_path:
                            # Show preview
                            global_pos = viewport.mapToGlobal(pos)
                            self.image_preview.show_preview(str(preview_path), global_pos)
                            return True

                # Hide preview if not over preview column with image
                self.image_preview.hide()

            elif event.type() == QEvent.Leave:
                # Hide preview when mouse leaves table
                self.image_preview.hide()

        return super().eventFilter(obj, event)

    def _on_column_resized(self, logical_index: int, old_size: int, new_size: int):
        """Enforce minimum width for Ref Images column (column 3) and save column widths"""
        REF_IMAGES_COL = 3
        MIN_REF_IMAGES_WIDTH = 158  # 3 buttons × 50px (min) + 2 × 2px spacing + 4px margins

        if logical_index == REF_IMAGES_COL and new_size < MIN_REF_IMAGES_WIDTH:
            # Prevent resizing below minimum - block the signal to avoid recursion
            header = self.scene_table.horizontalHeader()
            header.blockSignals(True)
            header.resizeSection(REF_IMAGES_COL, MIN_REF_IMAGES_WIDTH)
            header.blockSignals(False)

        # Save column widths whenever any column is resized
        self._save_column_widths()

    def _on_header_double_clicked(self, logical_index: int):
        """Handle header double-click to auto-resize columns"""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt

        modifiers = QApplication.keyboardModifiers()

        # Define default widths for prompt columns (updated for new column order)
        default_widths = {
            8: 360,  # Video Prompt (moved from 10)
            9: 360,  # Start Prompt (moved from 8)
            10: 360,  # End Prompt (moved from 9)
        }

        if modifiers & Qt.ControlModifier:
            # Ctrl+double-click: resize all columns to contents
            for col in range(self.scene_table.columnCount()):
                self.scene_table.resizeColumnToContents(col)
        elif logical_index in default_widths:
            # Prompt columns (7, 8, 9): toggle between default and content width
            header = self.scene_table.horizontalHeader()
            current_width = header.sectionSize(logical_index)
            default_width = default_widths[logical_index]

            # If currently at or near default width, expand to fit content
            # Allow 20px tolerance for "near default"
            if abs(current_width - default_width) < 20:
                self.scene_table.resizeColumnToContents(logical_index)
            else:
                # Otherwise, return to default width
                header.resizeSection(logical_index, default_width)
        else:
            # Other columns: resize to contents
            self.scene_table.resizeColumnToContents(logical_index)

    def _on_cell_clicked(self, row: int, column: int):
        """Handle cell click to display image/video with toggle functionality"""
        if not self.current_project or row >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[row]

        # Check if we have both image and video
        has_image = scene.images and len(scene.images) > 0
        has_video = scene.video_clip and scene.video_clip.exists()

        # If clicking the same row again AND we have both image and video, toggle
        if row == self.last_clicked_row and has_image and has_video:
            self.showing_video = not self.showing_video
        else:
            # Different row or first click - reset to show image (or video if no image)
            self.last_clicked_row = row
            self.showing_video = False if has_image else True

        # Display based on current state
        if self.showing_video and has_video:
            self._show_video(scene, row)
        elif has_image:
            self._show_image(scene, row)
        elif scene.last_frame and scene.last_frame.exists():
            # Fallback to last frame if no image or video
            self._show_last_frame(scene, row)

    def _show_image(self, scene, row):
        """Display the scene's image in the viewer"""
        from pathlib import Path
        from PySide6.QtGui import QPixmap

        # Hide video player, show image label
        self.video_player_container.hide()
        self.output_image_label.show()
        self.media_player.stop()

        # Prefer approved_image, fallback to first image in list
        if scene.approved_image:
            img_path = scene.approved_image
        else:
            img_path = scene.images[0]

        # Handle both Path objects and ImageVariant objects
        if hasattr(img_path, 'path'):
            img_path = img_path.path
        img_path = Path(img_path)

        if img_path.exists():
            pixmap = QPixmap(str(img_path))
            if not pixmap.isNull():
                # Scale to fit the image view
                scaled = pixmap.scaled(
                    self.output_image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.output_image_label.setPixmap(scaled)
                self._log_to_console(f"🖼️ Scene {row + 1}: Displaying image ({img_path.name})")

    def _show_video(self, scene, row):
        """Display the scene's video in the video player"""
        from pathlib import Path

        video_path = scene.video_clip

        try:
            # Track current playing scene for sequential playback
            self.current_playing_scene = row

            # Hide image label, show video player
            self.output_image_label.hide()
            self.video_player_container.show()

            # Load and play the video
            self.media_player.setSource(QUrl.fromLocalFile(str(video_path)))
            self.media_player.play()

            self._log_to_console(f"🎬 Scene {row + 1}: Playing video ({video_path.name})")
        except Exception as e:
            self.logger.error(f"Failed to play video: {e}")
            self._log_to_console(f"❌ Failed to play video: {e}", "ERROR")

    def _toggle_play_pause(self):
        """Toggle video playback"""
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def _toggle_mute(self):
        """Toggle audio mute"""
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.mute_btn.setText("🔊 Mute" if not is_muted else "🔇 Unmute")
        self.mute_btn.setChecked(not is_muted)

    def _set_position(self, position):
        """Set video playback position"""
        self.media_player.setPosition(position)

    def _update_position(self, position):
        """Update position slider when video position changes"""
        self.video_position_slider.setValue(position)
        self._update_time_label(position, self.media_player.duration())

    def _update_duration(self, duration):
        """Update slider range when video duration is known"""
        self.video_position_slider.setRange(0, duration)
        self._update_time_label(self.media_player.position(), duration)

        # Enable extract frame button when video is loaded
        self.extract_frame_btn.setEnabled(duration > 0)

    def _update_play_button(self, state):
        """Update play/pause button text based on playback state"""
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setText("⏸ Pause")
        else:
            self.play_pause_btn.setText("▶ Play")

    def _on_media_status_changed(self, status):
        """Handle media status changes for loop and sequential playback"""
        from PySide6.QtMultimedia import QMediaPlayer

        # Check if video has finished playing
        if status == QMediaPlayer.EndOfMedia:
            # Check if loop is enabled
            if self.loop_video_checkbox.isChecked():
                if self.sequential_playback_checkbox.isChecked():
                    # Sequential mode: play next scene (or loop back to first)
                    self._play_next_scene()
                else:
                    # Loop current video
                    self.media_player.setPosition(0)
                    self.media_player.play()
                    # Don't log loop message to avoid console spam

    def _play_next_scene(self):
        """Play the next available scene with video"""
        if not self.current_project or not self.current_project.scenes:
            return

        # Find current scene index
        current_index = self.current_playing_scene if self.current_playing_scene is not None else 0

        # Find next scene with video
        next_index = None
        for i in range(current_index + 1, len(self.current_project.scenes)):
            scene = self.current_project.scenes[i]
            if scene.video_clip and scene.video_clip.exists():
                next_index = i
                break

        # If no next scene found, loop back to beginning
        if next_index is None:
            for i in range(0, current_index + 1):
                scene = self.current_project.scenes[i]
                if scene.video_clip and scene.video_clip.exists():
                    next_index = i
                    break

        # Play next scene if found
        if next_index is not None:
            self.current_playing_scene = next_index
            scene = self.current_project.scenes[next_index]
            self._show_video(scene, next_index)
            self._log_to_console(f"▶ Playing scene {next_index + 1} sequentially")

    def _update_time_label(self, position, duration):
        """Update time label and textbox with current position and duration (with milliseconds)"""
        def format_time_ms(ms):
            """Format time as MM:SS.mmm"""
            total_seconds = ms / 1000.0
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            milliseconds = int((total_seconds % 1) * 1000)
            return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

        pos_str = format_time_ms(position)
        dur_str = format_time_ms(duration)

        # Update duration label
        self.video_time_label.setText(f"/ {dur_str}")

        # Update time textbox (only if not currently being edited)
        if not self.video_time_textbox.hasFocus():
            self.video_time_textbox.setText(pos_str)

    def _on_time_textbox_changed(self):
        """Handle time textbox change - parse and seek to specified time"""
        try:
            time_str = self.video_time_textbox.text().strip()
            if not time_str:
                return

            # Parse time formats: MM:SS.mmm, SS.mmm, or just seconds
            parts = time_str.replace(',', '.').split(':')

            if len(parts) == 1:
                # Just seconds (with optional milliseconds)
                total_seconds = float(parts[0])
            elif len(parts) == 2:
                # MM:SS.mmm format
                minutes = int(parts[0])
                seconds = float(parts[1])
                total_seconds = minutes * 60 + seconds
            else:
                self.logger.warning(f"Invalid time format: {time_str}")
                return

            # Convert to milliseconds
            position_ms = int(total_seconds * 1000)

            # Clamp to valid range
            duration = self.media_player.duration()
            position_ms = max(0, min(position_ms, duration))

            # Seek to position
            self.media_player.setPosition(position_ms)
            self.logger.info(f"Seeking to {position_ms}ms ({total_seconds:.3f}s)")

        except ValueError as e:
            self.logger.warning(f"Failed to parse time '{time_str}': {e}")

    def eventFilter(self, obj, event):
        """Event filter for slider tooltip with precise time"""
        # Check if video_position_slider exists and if this event is for it
        if hasattr(self, 'video_position_slider') and obj == self.video_position_slider and event.type() == QEvent.ToolTip:
            # Get slider value at mouse position
            slider = obj
            mouse_pos = slider.mapFromGlobal(QCursor.pos())
            slider_width = slider.width()
            slider_min = slider.minimum()
            slider_max = slider.maximum()

            # Calculate value at mouse position
            if slider_max > slider_min:
                value_at_pos = slider_min + (slider_max - slider_min) * (mouse_pos.x() / slider_width)
                value_at_pos = max(slider_min, min(slider_max, value_at_pos))

                # Format time
                total_seconds = value_at_pos / 1000.0
                minutes = int(total_seconds // 60)
                seconds = int(total_seconds % 60)
                milliseconds = int((total_seconds % 1) * 1000)
                time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

                # Show tooltip
                slider.setToolTip(f"Time: {time_str}")

        return super().eventFilter(obj, event)

    def _extract_frame_at_playhead(self):
        """Extract the current frame from video at playhead position"""
        try:
            if not self.media_player or not self.media_player.source():
                self.logger.warning("No video loaded")
                return

            # Get current position
            position_ms = self.media_player.position()
            total_seconds = position_ms / 1000.0

            # Format timestamp for filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create extracted frames directory in project
            if not self.current_project:
                self.logger.warning("No project loaded")
                return

            project_dir = Path(self.current_project.file_path).parent if self.current_project.file_path else Path.cwd()
            extracted_dir = project_dir / "extracted_frames"
            extracted_dir.mkdir(exist_ok=True)

            # Generate filename
            frame_filename = f"frame_{timestamp}_{total_seconds:.3f}s.png"
            frame_path = extracted_dir / frame_filename

            # Use ffmpeg to extract frame at precise position
            video_path = Path(self.media_player.source().toLocalFile())

            from core.video.ffmpeg_renderer import FFmpegRenderer
            renderer = FFmpegRenderer()

            # Extract frame using ffmpeg
            import subprocess
            cmd = [
                "ffmpeg",
                "-ss", str(total_seconds),  # Seek to position
                "-i", str(video_path),
                "-frames:v", "1",  # Extract 1 frame
                "-q:v", "2",  # High quality
                "-y",  # Overwrite
                str(frame_path)
            ]

            self.logger.info(f"Extracting frame at {total_seconds:.3f}s: {frame_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and frame_path.exists():
                self.logger.info(f"✅ Frame extracted successfully: {frame_path}")

                # Add to project's extracted frames list
                if not hasattr(self.current_project, 'extracted_frames'):
                    self.current_project.extracted_frames = []

                self.current_project.extracted_frames.append({
                    'path': str(frame_path),
                    'timestamp_sec': total_seconds,
                    'video_source': str(video_path),
                    'extracted_at': timestamp
                })

                # Auto-save project
                self.save_project()

                # Show success message
                self._log_to_console(f"✅ Frame extracted: {frame_path.name}", "SUCCESS")
                QMessageBox.information(
                    self,
                    "Frame Extracted",
                    f"Frame extracted successfully:\n{frame_path.name}\n\nTime: {total_seconds:.3f}s"
                )
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                self.logger.error(f"Failed to extract frame: {error_msg}")
                self._log_to_console(f"❌ Failed to extract frame: {error_msg}", "ERROR")

        except subprocess.TimeoutExpired:
            self.logger.error("Frame extraction timed out")
            self._log_to_console("❌ Frame extraction timed out", "ERROR")
        except Exception as e:
            self.logger.error(f"Failed to extract frame: {e}")
            self._log_to_console(f"❌ Failed to extract frame: {e}", "ERROR")

    def _show_last_frame(self, scene, row):
        """Display the scene's last frame in the viewer"""
        from PySide6.QtGui import QPixmap

        # Hide video player, show image label
        self.video_player_container.hide()
        self.output_image_label.show()
        self.media_player.stop()

        pixmap = QPixmap(str(scene.last_frame))
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.output_image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.output_image_label.setPixmap(scaled)
            self._log_to_console(f"🖼️ Scene {row + 1}: Displaying last frame ({scene.last_frame.name})")

    def _log_to_console(self, message: str, level: str = "INFO"):
        """Log a message to the status console"""
        from datetime import datetime
        from PySide6.QtWidgets import QApplication
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color coding based on level
        colors = {
            "INFO": "#cccccc",
            "SUCCESS": "#4CAF50",
            "WARNING": "#FFC107",
            "ERROR": "#F44336"
        }
        color = colors.get(level, "#cccccc")

        html = f'<span style="color: {color};">[{timestamp}] {message}</span>'
        self.status_console.append(html)

        # Force immediate GUI update so messages appear in real-time
        QApplication.processEvents()

    def generate_single_scene(self, scene_index: int):
        """Generate image for a single scene"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        # Ensure scene has a prompt
        if not scene.prompt:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Prompt", "Please enhance the prompt first before generating images.")
            return

        # Emit generation request for just this scene
        params = self.gather_generation_params()
        params['scene_indices'] = [scene_index]  # Only generate for this scene
        self.generation_requested.emit("generate_images", params)

    def generate_video_clip(self, scene_index: int):
        """Generate video clip for a single scene using Veo 3 or Veo 3.1"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        # Validate scene duration (must be <= 8.0 seconds)
        if scene.duration_sec > 8.0:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning(
                "Invalid Scene Duration",
                f"Scene #{scene_index + 1} duration ({scene.duration_sec:.1f}s) exceeds the maximum of 8.0 seconds.\n\n"
                f"Please manually adjust the duration in the Time column before generating video."
            )
            return

        # Ensure scene has a video prompt
        if not hasattr(scene, 'video_prompt') or not scene.video_prompt:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Video Prompt", "Please enhance the prompts for video first (Enhance for Video button).")
            return

        # Determine start frame (OPTIONAL - only used if no reference images)
        # With reference images (Veo 3.1 "Ingredients to Video"), start frame is NOT used
        start_frame = None
        if scene.approved_image and scene.approved_image.exists():
            start_frame = scene.approved_image
        # Do NOT fall back to scene.images[0] - if user cleared start frame, respect that choice

        # Check for end frame (determines Veo 3 vs 3.1)
        end_frame = scene.end_frame if scene.end_frame and scene.end_frame.exists() else None
        use_veo_31 = end_frame is not None

        # IMPORTANT: No hybrid mode - if start or end frame is provided, don't use reference images
        use_reference_images = not (start_frame or end_frame)

        # Log what we're about to generate
        if use_veo_31:
            self.logger.info(f"Generating video with Veo 3.1 (start + end frames) for scene {scene_index + 1}")
            self.logger.info(f"  Start frame: {start_frame if start_frame else 'None'}")
            self.logger.info(f"  End frame: {end_frame}")
            self.logger.info(f"  Reference images: DISABLED (frames provided)")
        else:
            self.logger.info(f"Generating video for scene {scene_index + 1}")
            self.logger.info(f"  Start frame: {start_frame if start_frame else 'None'}")
            if use_reference_images:
                self.logger.info(f"  Reference images: Will be used if available")
            else:
                self.logger.info(f"  Reference images: DISABLED (start frame provided)")

        # Check if we need to show reference selector dialog (only if no frames provided)
        selected_refs = None
        if use_reference_images:
            available_refs = self.current_project.get_all_available_references(scene)

            self.logger.info(f"📸 Reference check: Found {len(available_refs)} available references")
            for ref in available_refs:
                ref_type = ref.ref_type.value if hasattr(ref.ref_type, 'value') else str(ref.ref_type)
                self.logger.info(f"   - {ref.name or ref.path.stem}: {ref_type}")

            # Check if there are 2+ references of the same type (requires user selection)
            from collections import Counter
            ref_types = [ref.ref_type for ref in available_refs]
            type_counts = Counter(ref_types)
            has_duplicate_types = any(count >= 2 for count in type_counts.values())

            self.logger.info(f"📸 Type analysis: {dict(type_counts)}, has_duplicate_types={has_duplicate_types}")

            # Also show selector if we have more than 3 total refs (max limit)
            needs_selection = has_duplicate_types or len(available_refs) > 3

            if needs_selection and len(available_refs) >= 2:
                if has_duplicate_types:
                    duplicate_types = [str(t.value if hasattr(t, 'value') else t) for t, count in type_counts.items() if count >= 2]
                    self.logger.info(f"📸 Found {len(available_refs)} references with duplicates of type(s): {', '.join(duplicate_types)}")
                else:
                    self.logger.info(f"📸 Found {len(available_refs)} references (exceeds max 3), showing selector")

                from gui.video.reference_selector_dialog import ReferenceSelectorDialog
                from PySide6.QtWidgets import QDialog

                dialog = ReferenceSelectorDialog(available_refs, max_selection=3, parent=self)
                if dialog.exec() == QDialog.Accepted:
                    selected_refs = dialog.selected_references
                    self.logger.info(f"📸 User selected {len(selected_refs)} references for video generation")
                else:
                    self.logger.info("📸 Reference selection cancelled, aborting video generation")
                    return  # User cancelled
            elif len(available_refs) > 0:
                self.logger.info(f"📸 Using all {len(available_refs)} available references (no duplicates, no selection needed)")
        else:
            self.logger.info(f"📸 Reference images SKIPPED (start or end frame provided - no hybrid mode)")

        # Emit generation request for video clip
        params = self.gather_generation_params()
        params['scene_indices'] = [scene_index]  # Only generate for this scene
        params['start_frame'] = str(start_frame)  # Veo 3/3.1 start frame
        params['end_frame'] = str(end_frame) if end_frame else None  # Veo 3.1 end frame
        params['use_veo_31'] = use_veo_31  # Flag for Veo 3.1 mode
        params['video_prompt'] = scene.video_prompt  # Use video-specific prompt
        params['duration'] = scene.duration_sec  # Scene duration
        params['generate_video'] = True  # Flag to indicate video generation
        params['selected_refs'] = selected_refs  # User-selected references (if any)

        # IMPORTANT: For single scene generation, never use previous scene's last frame
        # The start_frame is explicitly set above from the scene's approved_image/images
        # The use_prev_last_frame setting should only apply during batch/export operations
        params['use_prev_last_frame'] = False

        self.generation_requested.emit("generate_video_clip", params)

    # Veo 3.1 Frame Interaction Methods

    def _view_start_frame(self, scene_index: int):
        """View start frame in lower preview panel"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]
        image_path = scene.approved_image

        if not image_path or not image_path.exists():
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Image", "No start frame image available to view.")
            return

        # Display image in lower preview panel
        from PySide6.QtGui import QPixmap

        # Hide video player, show image label
        self.video_player_container.hide()
        self.output_image_label.show()
        self.media_player.stop()

        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            # Scale to fit the image view
            scaled = pixmap.scaled(
                self.output_image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.output_image_label.setPixmap(scaled)
            self._log_to_console(f"Displaying start frame: {image_path.name}", "INFO")

    def _select_start_frame_variant(self, scene_index: int):
        """Select start frame from generated variants"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.images:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Variants", "No image variants available. Generate images first.")
            return

        # Show variant selector dialog
        from gui.video.variant_selector_dialog import VariantSelectorDialog
        dialog = VariantSelectorDialog(
            scene.images,
            scene.approved_image,
            f"Select Start Frame - Scene {scene_index + 1}",
            self
        )

        if dialog.exec_():
            selected_path = dialog.get_selected_image()
            if selected_path:
                scene.approved_image = selected_path
                self.save_project()
                self.populate_scene_table()

    def _clear_start_frame(self, scene_index: int):
        """Clear the start frame selection"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        from gui.common.dialog_manager import get_dialog_manager
        dialog_manager = get_dialog_manager(self)

        if dialog_manager.show_question(
            "Clear Start Frame",
            "Clear the selected start frame? This won't delete generated images."
        ):
            scene.approved_image = None
            self.save_project()

            # Update the button directly to show + emoji immediately
            start_frame_btn = self._get_cell_widget(scene_index, 1)
            if start_frame_btn and hasattr(start_frame_btn, 'set_frame'):
                start_frame_btn.set_frame(None, auto_linked=False)

            self._log_to_console(f"✓ Scene {scene_index + 1}: Start frame cleared")

    def _load_start_frame_image(self, scene_index: int):
        """Load an image from disk for start frame"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Start Frame Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )

        if file_path:
            scene.approved_image = Path(file_path)
            self.save_project()
            self.populate_scene_table()
            self._log_to_console(f"Loaded start frame from: {file_path}", "INFO")

    def _use_last_generated_for_start_frame(self, scene_index: int):
        """Use the last generated image from history as start frame"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        # Get the last generated image from history
        from core.utils import scan_disk_history
        history_paths = scan_disk_history(project_only=False)

        if not history_paths:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning(
                "No History",
                "No generated images found in history."
            )
            return

        # Use the most recent image (first in list, since it's sorted by time)
        last_image_path = history_paths[0]
        scene.approved_image = last_image_path
        self.save_project()
        self.populate_scene_table()
        self._log_to_console(f"Using last generated image: {last_image_path.name}", "INFO")

    def _select_start_frame_from_scenes(self, scene_index: int):
        """Select start frame from any scene's images"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        # Check if any scenes have images (variants, first frame, or last frame)
        has_any_images = any(
            (hasattr(s, 'images') and s.images) or
            (hasattr(s, 'first_frame') and s.first_frame) or
            (hasattr(s, 'last_frame') and s.last_frame)
            for s in self.current_project.scenes
        )
        if not has_any_images:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Images", "No scenes have generated images yet. Generate images first.")
            return

        # Show scene image selector dialog
        from gui.video.scene_image_selector_dialog import SceneImageSelectorDialog
        dialog = SceneImageSelectorDialog(
            self.current_project.scenes,
            scene_index,
            f"Select Start Frame for Scene {scene_index + 1}",
            self
        )

        if dialog.exec_():
            selected_path = dialog.get_selected_image()
            selected_scene_idx = dialog.get_selected_scene_index()
            if selected_path:
                scene.approved_image = selected_path
                self.save_project()
                self.populate_scene_table()
                if selected_scene_idx is not None:
                    self._log_to_console(
                        f"Scene {scene_index + 1} start frame set from Scene {selected_scene_idx + 1}: {selected_path.name}",
                        "INFO"
                    )

    def _show_end_prompt_llm_dialog(self, scene_index: int):
        """Show LLM dialog for generating end prompt"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.prompt:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Start Prompt", "Please enhance the start prompt first.")
            return

        # Get next scene's start prompt if available
        next_start_prompt = None
        if scene_index + 1 < len(self.current_project.scenes):
            next_scene = self.current_project.scenes[scene_index + 1]
            next_start_prompt = next_scene.prompt

        # Get LLM provider/model
        llm_provider = self.llm_provider_combo.currentText().lower()
        llm_model = self.llm_model_combo.currentText()

        # Create end prompt generator
        end_prompt_gen = EndPromptGenerator(llm_provider=None)  # Will use litellm directly

        # Show dialog
        dialog = EndPromptDialog(
            end_prompt_gen,
            scene.prompt,
            next_start_prompt,
            scene.duration_sec,
            llm_provider,
            llm_model,
            self
        )

        if dialog.exec_():
            generated_prompt = dialog.get_prompt()
            if generated_prompt:
                scene.end_prompt = generated_prompt
                self.save_project()
                self.populate_scene_table()

    def _generate_end_frame(self, scene_index: int):
        """Generate end frame image from end_prompt"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.end_prompt:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No End Prompt", "Please create an end prompt first.")
            return

        # Emit generation request for end frame
        params = self.gather_generation_params()
        params['scene_indices'] = [scene_index]
        params['generate_end_frame'] = True  # Flag for end frame generation
        params['prompt_override'] = scene.end_prompt  # Use end_prompt instead of start prompt
        self.generation_requested.emit("generate_end_frame", params)

    def _view_end_frame(self, scene_index: int):
        """View end frame in lower preview panel"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.end_frame or not scene.end_frame.exists():
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Image", "No end frame image available to view.")
            return

        # Display image in lower preview panel
        from PySide6.QtGui import QPixmap

        # Hide video player, show image label
        self.video_player_container.hide()
        self.output_image_label.show()
        self.media_player.stop()

        pixmap = QPixmap(str(scene.end_frame))
        if not pixmap.isNull():
            # Scale to fit the image view
            scaled = pixmap.scaled(
                self.output_image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.output_image_label.setPixmap(scaled)
            self._log_to_console(f"Displaying end frame: {scene.end_frame.name}", "INFO")

    def _view_video_first_frame(self, scene_index: int):
        """View first frame of generated video in lower preview panel"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.video_clip or not scene.video_clip.exists():
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Video", "No video clip available to view.")
            return

        # Extract first frame if not already extracted
        if not scene.first_frame or not scene.first_frame.exists():
            self._extract_video_first_frame(scene_index)

        if not scene.first_frame or not scene.first_frame.exists():
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("Extraction Failed", "Could not extract first frame from video.")
            return

        # Display image in lower preview panel
        from PySide6.QtGui import QPixmap

        # Hide video player, show image label
        self.video_player_container.hide()
        self.output_image_label.show()
        self.media_player.stop()

        pixmap = QPixmap(str(scene.first_frame))
        if not pixmap.isNull():
            # Scale to fit the image view
            scaled = pixmap.scaled(
                self.output_image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.output_image_label.setPixmap(scaled)
            self._log_to_console(f"Displaying video first frame: {scene.first_frame.name}", "INFO")

    def _load_video_first_frame_in_panel(self, scene_index: int):
        """Load video's first frame in the lower image panel"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.first_frame or not scene.first_frame.exists():
            # Try to extract first frame if not already extracted
            if scene.video_clip and scene.video_clip.exists():
                self._extract_video_first_frame(scene_index)
                scene = self.current_project.scenes[scene_index]  # Refresh

        if not scene.first_frame or not scene.first_frame.exists():
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No First Frame", "Could not load first frame from video.")
            return

        # Hide video player, show image label
        self.video_player_container.hide()
        self.output_image_label.show()
        self.media_player.stop()

        # Load first frame in image panel
        pixmap = QPixmap(str(scene.first_frame))
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.output_image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.output_image_label.setPixmap(scaled)
            self._log_to_console(f"🖼️ Scene {scene_index + 1}: Displaying video first frame ({scene.first_frame.name})")

    def _play_video_in_panel(self, scene_index: int):
        """Play video in the lower video panel"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.video_clip or not scene.video_clip.exists():
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Video", "Video not found. Generate video first.")
            return

        try:
            # Hide image label, show video player
            self.output_image_label.hide()
            self.video_player_container.show()

            # Stop any currently playing video
            self.media_player.stop()

            # Load the video and restart from beginning
            self.media_player.setSource(QUrl.fromLocalFile(str(scene.video_clip)))
            self.media_player.setPosition(0)  # Ensure playback starts at beginning
            self.media_player.play()

            self._log_to_console(f"🎬 Scene {scene_index + 1}: Playing video ({scene.video_clip.name})")
        except Exception as e:
            self.logger.error(f"Failed to play video: {e}")
            self._log_to_console(f"❌ Failed to play video: {e}", "ERROR")

    def _clear_video(self, scene_index: int):
        """Clear the video clip"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        from gui.common.dialog_manager import get_dialog_manager
        from core.recycle_bin import send_to_recycle_bin, RecycleBinError
        dialog_manager = get_dialog_manager(self)

        if dialog_manager.show_question(
            "Clear Video",
            f"Clear the video clip for Scene {scene_index + 1}? This will move the video and extracted frames to the recycle bin."
        ):
            # Delete video file if it exists (use recycle bin)
            if scene.video_clip and scene.video_clip.exists():
                try:
                    send_to_recycle_bin(scene.video_clip)
                    self.logger.info(f"Moved video file to recycle bin: {scene.video_clip}")
                except RecycleBinError as e:
                    self.logger.error(f"Failed to move video file to recycle bin: {e}")
                except Exception as e:
                    self.logger.error(f"Failed to delete video file: {e}")

            # Delete first frame file if it exists (use recycle bin)
            if scene.first_frame and scene.first_frame.exists():
                try:
                    send_to_recycle_bin(scene.first_frame)
                    self.logger.info(f"Moved first frame to recycle bin: {scene.first_frame}")
                except RecycleBinError as e:
                    self.logger.error(f"Failed to move first frame to recycle bin: {e}")
                except Exception as e:
                    self.logger.error(f"Failed to delete first frame file: {e}")

            # Delete last frame file if it exists (use recycle bin)
            if scene.last_frame and scene.last_frame.exists():
                try:
                    send_to_recycle_bin(scene.last_frame)
                    self.logger.info(f"Moved last frame to recycle bin: {scene.last_frame}")
                except RecycleBinError as e:
                    self.logger.error(f"Failed to move last frame to recycle bin: {e}")
                except Exception as e:
                    self.logger.error(f"Failed to delete last frame file: {e}")

            # Clear video clip and frame references
            scene.video_clip = None
            scene.first_frame = None
            scene.last_frame = None

            # Stop media player and clear source completely
            self.media_player.stop()
            self.media_player.setSource(QUrl())  # Clear the source

            # Reset click tracking to prevent stale references
            if self.last_clicked_row == scene_index:
                self.last_clicked_row = -1  # Reset to invalid row
                self.showing_video = False

            # Always update the preview panel
            # Show the image if available, otherwise clear the panel
            if scene.images and len(scene.images) > 0:
                self._show_image(scene, scene_index)
            else:
                self.output_image_label.clear()
                self.output_image_label.show()
                self.video_player_container.hide()

            self.save_project()
            self.populate_scene_table()
            self._log_to_console(f"🗑️ Scene {scene_index + 1}: Video and first frame cleared")

    def _select_existing_video(self, scene_index: int):
        """Open dialog to select an existing video clip from the project to assign to this scene"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        # Import the dialog
        from gui.video.select_existing_video_dialog import SelectExistingVideoDialog

        # Show the dialog
        dialog = SelectExistingVideoDialog(
            project=self.current_project,
            current_scene_id=scene.id,
            parent=self
        )

        if dialog.exec() == QDialog.Accepted:
            # Get the selected video path
            selected_video_path = dialog.get_selected_video_path()

            if selected_video_path and selected_video_path.exists():
                # Assign the video to this scene
                scene.video_clip = selected_video_path

                # Try to extract first and last frames from the video
                try:
                    from core.video.veo_client import extract_first_last_frames
                    project_dir = self.project_manager.get_project_dir(self.current_project.project_id)

                    first_frame_path, last_frame_path = extract_first_last_frames(
                        video_path=selected_video_path,
                        output_dir=project_dir,
                        scene_id=scene.id
                    )

                    scene.first_frame = first_frame_path
                    scene.last_frame = last_frame_path

                    self.logger.info(f"Assigned existing video to Scene {scene_index + 1}: {selected_video_path}")
                    self.logger.info(f"Extracted frames: {first_frame_path}, {last_frame_path}")

                except Exception as e:
                    # If frame extraction fails, still assign the video but log the error
                    self.logger.error(f"Failed to extract frames from video: {e}")
                    self.logger.warning("Video assigned but frames not extracted")

                # Save and refresh
                self.save_project()
                self.populate_scene_table()
                self._log_to_console(f"📁 Scene {scene_index + 1}: Assigned existing video clip")

    def _select_end_frame_variant(self, scene_index: int):
        """Select end frame from generated variants"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.end_frame_images:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Variants", "No end frame variants available. Generate end frame first.")
            return

        # Show variant selector dialog
        from gui.video.variant_selector_dialog import VariantSelectorDialog
        dialog = VariantSelectorDialog(
            scene.end_frame_images,
            scene.end_frame,
            f"Select End Frame - Scene {scene_index + 1}",
            self
        )

        if dialog.exec_():
            selected_path = dialog.get_selected_image()
            if selected_path:
                scene.end_frame = selected_path
                scene.end_frame_auto_linked = False  # Clear auto-link when manually selecting
                self.save_project()
                self.populate_scene_table()

    def _clear_end_frame(self, scene_index: int):
        """Clear the end frame and end_prompt"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        from gui.common.dialog_manager import get_dialog_manager
        dialog_manager = get_dialog_manager(self)

        if dialog_manager.show_question(
            "Clear End Frame",
            "Clear the end frame and end prompt? This will revert to Veo 3 single-frame mode."
        ):
            scene.end_frame = None
            scene.end_frame_auto_linked = False
            scene.end_prompt = ""
            # Note: Not clearing end_frame_images so user can re-select if desired
            self.save_project()

            # Update the button directly to show + emoji immediately
            end_frame_btn = self._get_cell_widget(scene_index, 2)
            if end_frame_btn and hasattr(end_frame_btn, 'set_frame'):
                end_frame_btn.set_frame(None, auto_linked=False)

            self._log_to_console(f"✓ Scene {scene_index + 1}: End frame cleared")

    def _load_end_frame_image(self, scene_index: int):
        """Load an image from disk for end frame"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select End Frame Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )

        if file_path:
            scene.end_frame = Path(file_path)
            scene.end_frame_auto_linked = False  # Clear auto-link when manually loading
            self.save_project()
            self.populate_scene_table()
            self._log_to_console(f"Loaded end frame from: {file_path}", "INFO")

    def _use_last_generated_for_end_frame(self, scene_index: int):
        """Use the last generated image from history as end frame"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        # Get the last generated image from history
        from core.utils import scan_disk_history
        history_paths = scan_disk_history(project_only=False)

        if not history_paths:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning(
                "No History",
                "No generated images found in history."
            )
            return

        # Use the most recent image (first in list, since it's sorted by time)
        last_image_path = history_paths[0]
        scene.end_frame = last_image_path
        scene.end_frame_auto_linked = False  # Clear auto-link when using last generated
        self.save_project()
        self.populate_scene_table()
        self._log_to_console(f"Using last generated image for end frame: {last_image_path.name}", "INFO")

    def _select_end_frame_from_scenes(self, scene_index: int):
        """Select end frame from any scene's images"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        # Check if any scenes have images (variants, first frame, or last frame)
        has_any_images = any(
            (hasattr(s, 'images') and s.images) or
            (hasattr(s, 'first_frame') and s.first_frame) or
            (hasattr(s, 'last_frame') and s.last_frame)
            for s in self.current_project.scenes
        )
        if not has_any_images:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Images", "No scenes have generated images yet. Generate images first.")
            return

        # Show scene image selector dialog
        from gui.video.scene_image_selector_dialog import SceneImageSelectorDialog
        dialog = SceneImageSelectorDialog(
            self.current_project.scenes,
            scene_index,
            f"Select End Frame for Scene {scene_index + 1}",
            self
        )

        if dialog.exec_():
            selected_path = dialog.get_selected_image()
            selected_scene_idx = dialog.get_selected_scene_index()
            if selected_path:
                scene.end_frame = selected_path
                scene.end_frame_auto_linked = False  # Clear auto-link when manually selecting
                self.save_project()
                self.populate_scene_table()
                if selected_scene_idx is not None:
                    self._log_to_console(
                        f"Scene {scene_index + 1} end frame set from Scene {selected_scene_idx + 1}: {selected_path.name}",
                        "INFO"
                    )

    def _auto_link_end_frame(self, scene_index: int):
        """DISABLED: Auto-linking removed - use manual frame selection only"""
        # Auto-linking feature has been removed due to complexity and confusion
        # Users should manually select end frames using "Select from Scene Images" instead
        from gui.common.dialog_manager import get_dialog_manager
        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_info(
            "Feature Disabled",
            "Auto-linking has been disabled. Please manually select an end frame using:\n"
            "• Right-click → 'Select from Scene Images'\n"
            "• Or generate a new end frame"
        )

    def _extract_video_first_frame(self, scene_index: int):
        """Extract first frame from video clip using OpenCV"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.video_clip or not scene.video_clip.exists():
            self.logger.warning(f"Cannot extract first frame: video clip not found for scene {scene_index + 1}")
            return

        try:
            import cv2

            # Create first_frames directory in project directory
            first_frames_dir = self.current_project.project_dir / "first_frames"
            first_frames_dir.mkdir(exist_ok=True)

            # Generate output path
            output_path = first_frames_dir / f"scene_{scene_index + 1:03d}_first_frame.png"

            self.logger.info(f"Extracting first frame from {scene.video_clip.name}...")

            # Open video file
            cap = cv2.VideoCapture(str(scene.video_clip))
            if not cap.isOpened():
                self.logger.error(f"Failed to open video: {scene.video_clip}")
                return

            # Read the first frame
            ret, frame = cap.read()
            cap.release()

            if not ret:
                self.logger.error("Failed to read first frame from video")
                return

            # Save the frame
            cv2.imwrite(str(output_path), frame)

            if output_path.exists():
                scene.first_frame = output_path
                self.save_project()
                self.logger.info(f"First frame extracted to {output_path}")
            else:
                self.logger.error("Failed to save first frame")

        except ImportError:
            self.logger.error("OpenCV (cv2) not available. Please install opencv-python to extract video frames.")
        except Exception as e:
            self.logger.error(f"Error extracting first frame: {e}")

    def _extract_video_last_frame(self, scene_index: int):
        """Extract last frame from video clip using OpenCV"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.video_clip or not scene.video_clip.exists():
            self.logger.warning(f"Cannot extract last frame: video clip not found for scene {scene_index + 1}")
            return

        try:
            import cv2

            # Create frames directory in project directory (backward compatible)
            frames_dir = self.current_project.project_dir / "frames"
            frames_dir.mkdir(exist_ok=True)

            # Generate output path (use 0-based index to match video generation system)
            output_path = frames_dir / f"scene_{scene_index}_last_frame.png"

            self.logger.info(f"Extracting last frame from {scene.video_clip.name}...")

            # Open video file
            cap = cv2.VideoCapture(str(scene.video_clip))
            if not cap.isOpened():
                self.logger.error(f"Failed to open video: {scene.video_clip}")
                return

            # Get total frame count
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                self.logger.error("Failed to get frame count from video")
                cap.release()
                return

            # Seek to last frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)

            # Read the last frame
            ret, frame = cap.read()
            cap.release()

            if not ret:
                self.logger.error("Failed to read last frame from video")
                return

            # Save the frame
            cv2.imwrite(str(output_path), frame)

            if output_path.exists():
                scene.last_frame = output_path
                self.save_project()
                self.populate_scene_table()  # Refresh to show the new last frame
                self._log_to_console(f"Scene {scene_index + 1} last frame extracted: {output_path.name}", "INFO")
                self.logger.info(f"Last frame extracted to {output_path}")
            else:
                self.logger.error("Failed to save last frame")

        except ImportError:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_error(
                "OpenCV Required",
                "OpenCV (cv2) is required to extract video frames.\nPlease install opencv-python:\n\npip install opencv-python"
            )
        except Exception as e:
            self.logger.error(f"Error extracting last frame: {e}")
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_error("Extraction Failed", f"Failed to extract last frame:\n{e}")

    def _extract_all_first_frames(self):
        """Extract first frames for all scenes with videos but no first frame"""
        if not self.current_project:
            return

        extracted_count = 0
        for i, scene in enumerate(self.current_project.scenes):
            # Check if scene has video but no first frame
            has_video = scene.video_clip is not None and scene.video_clip.exists() if scene.video_clip else False
            has_first_frame = scene.first_frame is not None and scene.first_frame.exists() if scene.first_frame else False

            if has_video and not has_first_frame:
                self.logger.info(f"Scene {i + 1} has video but no first frame, extracting...")
                self._extract_video_first_frame(i)
                extracted_count += 1

        if extracted_count > 0:
            self.logger.info(f"Extracted first frames for {extracted_count} scene(s)")
            # Refresh the UI to show the updated button states
            self.populate_scene_table()

    def _on_end_prompt_changed(self, scene_index: int, text: str):
        """Handle end prompt text change"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]
        scene.end_prompt = text.strip()
        self.save_project()

        # Note: This method is now called from PromptFieldWidget in column 4

    def _on_start_prompt_changed(self, scene_index: int, text: str):
        """Handle start prompt text change"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]
        scene.prompt = text.strip()
        self.save_project()

    def _on_environment_changed(self, scene_index: int, text: str):
        """Handle environment text change"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]
        scene.environment = text.strip()
        self.save_project()

        self.logger.info(f"Scene {scene_index}: Environment set to '{text.strip()}'")

    def _on_reference_image_changed(self, scene_index: int, slot_idx: int, path):
        """Handle reference image change"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        from core.video.project import ReferenceImage
        scene = self.current_project.scenes[scene_index]

        # Ensure reference_images list exists and has enough slots
        while len(scene.reference_images) <= slot_idx:
            scene.reference_images.append(None)

        if path:
            # Update or add reference image
            ref_image = ReferenceImage(
                path=path,
                label=f"ref{slot_idx+1}",
                auto_linked=False
            )
            scene.reference_images[slot_idx] = ref_image
        else:
            # Clear reference image
            if slot_idx < len(scene.reference_images):
                scene.reference_images[slot_idx] = None

        # Clean up None entries at the end of the list
        while scene.reference_images and scene.reference_images[-1] is None:
            scene.reference_images.pop()

        self.save_project()
        self.logger.info(f"Reference image {slot_idx+1} for scene {scene_index} updated")

    def _select_reference_from_scenes(self, scene_index: int, slot_idx: int):
        """Select reference image from any scene's images"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        # Check if any scenes have images (variants, first frame, or last frame)
        has_any_images = any(
            (hasattr(s, 'images') and s.images) or
            (hasattr(s, 'first_frame') and s.first_frame) or
            (hasattr(s, 'last_frame') and s.last_frame)
            for s in self.current_project.scenes
        )
        if not has_any_images:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Images", "No scenes have generated images yet. Generate images first.")
            return

        # Show scene image selector dialog
        from gui.video.scene_image_selector_dialog import SceneImageSelectorDialog
        dialog = SceneImageSelectorDialog(
            self.current_project.scenes,
            scene_index,
            f"Select Reference Image {slot_idx + 1} for Scene {scene_index + 1}",
            self
        )

        if dialog.exec_():
            selected_path = dialog.get_selected_image()
            selected_scene_idx = dialog.get_selected_scene_index()
            if selected_path:
                # Get the ref_images_widget for this scene
                ref_images_widget = self._get_cell_widget(scene_index, 3)
                if ref_images_widget:
                    ref_images_widget.set_reference_image(slot_idx, selected_path, False)
                if selected_scene_idx is not None:
                    self._log_to_console(
                        f"Scene {scene_index + 1} reference {slot_idx + 1} set from Scene {selected_scene_idx + 1}: {selected_path.name}",
                        "INFO"
                    )

    def _view_reference_image(self, scene_index: int, slot_idx: int):
        """View reference image in full viewer"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]
        if slot_idx < len(scene.reference_images) and scene.reference_images[slot_idx]:
            ref_image = scene.reference_images[slot_idx]
            if ref_image.path and ref_image.path.exists():
                # Open image in system default viewer
                import subprocess
                import platform

                try:
                    if platform.system() == 'Windows':
                        subprocess.run(['start', str(ref_image.path)], shell=True, check=False)
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.run(['open', str(ref_image.path)], check=False)
                    else:  # Linux
                        subprocess.run(['xdg-open', str(ref_image.path)], check=False)
                except Exception as e:
                    self.logger.error(f"Failed to open image: {e}")
                    QMessageBox.warning(self, "Open Image Failed", f"Could not open image: {e}")

    def _load_reference_image(self, scene_index: int, slot_idx: int):
        """Load reference image from disk"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Reference Image {slot_idx + 1} for Scene {scene_index + 1}",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )

        if file_path:
            # Get the ref_images_widget for this scene
            ref_images_widget = self._get_cell_widget(scene_index, 3)
            if ref_images_widget:
                from pathlib import Path
                ref_images_widget.set_reference_image(slot_idx, Path(file_path), False)
                self._log_to_console(f"Scene {scene_index + 1} reference {slot_idx + 1} loaded: {Path(file_path).name}", "INFO")

    def _show_start_prompt_llm_dialog(self, scene_index: int):
        """Show LLM dialog for generating start prompt"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.source:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Source Text", "Please enter source text first.")
            return

        # Get LLM provider/model
        llm_provider = self.llm_provider_combo.currentText().lower()
        llm_model = self.llm_model_combo.currentText()

        # Get API key from config
        api_key = None
        if llm_provider == "openai":
            api_key = self.config.get_api_key('openai')
        elif llm_provider in ["google", "gemini"]:
            api_key = self.config.get_api_key('google')
        elif llm_provider in ["anthropic", "claude"]:
            api_key = self.config.get_api_key('anthropic')

        if not api_key:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning(
                "API Key Missing",
                f"Please configure your {llm_provider} API key in Settings."
            )
            return

        # Get continuity mode from settings
        from core.video.style_analyzer import ContinuityMode
        continuity_mode_str = self.continuity_mode_combo.currentData()
        continuity_mode = ContinuityMode(continuity_mode_str)

        self.logger.info(f"Using continuity mode: {continuity_mode.value}")

        # Get previous frame path for continuity (only if scene has no image yet)
        previous_frame_path = None
        has_start_image = (scene.approved_image and scene.approved_image.exists()) or (scene.images and len(scene.images) > 0)

        if scene_index > 0 and continuity_mode != ContinuityMode.NONE and not has_start_image:
            from core.video.style_analyzer import get_previous_scene_info
            previous_frame_path, _ = get_previous_scene_info(self.current_project, scene_index)
            if previous_frame_path:
                self.logger.info(f"Previous frame available for continuity: {previous_frame_path}")
            else:
                self.logger.warning(f"Continuity mode '{continuity_mode.value}' selected but no previous frame available")
        elif has_start_image and continuity_mode != ContinuityMode.NONE:
            self.logger.info(f"Scene {scene_index} already has an image - skipping continuity for prompt generation")

        # Create generator (can reuse EndPromptGenerator)
        from gui.video.start_prompt_dialog import StartPromptDialog
        generator = EndPromptGenerator(llm_provider=None)  # Will use litellm directly

        # Show dialog with continuity support
        dialog = StartPromptDialog(
            generator,
            scene.source,
            scene.prompt,
            llm_provider,
            llm_model,
            api_key,
            continuity_mode,
            previous_frame_path,
            self
        )

        if dialog.exec_():
            generated_prompt = dialog.get_prompt()
            if generated_prompt:
                # Get widget and update it (with history)
                start_prompt_widget = self._get_cell_widget(scene_index, 8)
                if isinstance(start_prompt_widget, PromptFieldWidget):
                    start_prompt_widget.set_text(generated_prompt, add_to_history=True)

                scene.prompt = generated_prompt
                self.save_project()

    def _on_video_prompt_changed(self, scene_index: int, text: str):
        """Handle video prompt text change"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]
        scene.video_prompt = text.strip()
        self.save_project()

        # Update video button enabled state
        video_btn = self._get_cell_widget(scene_index, 4)
        if video_btn:
            video_btn.setEnabled(bool(text.strip()))

    def _show_video_prompt_llm_dialog(self, scene_index: int):
        """Show LLM dialog for generating video prompt"""
        if not self.current_project or scene_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[scene_index]

        if not scene.prompt:
            from gui.common.dialog_manager import get_dialog_manager
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_warning("No Start Prompt", "Please generate a start prompt first.")
            return

        # Get LLM provider/model
        llm_provider = self.llm_provider_combo.currentText().lower()
        llm_model = self.llm_model_combo.currentText()

        # Create generator
        from gui.video.video_prompt_dialog import VideoPromptDialog
        generator = EndPromptGenerator(llm_provider=None)  # Reuse for simplicity

        # Get camera movement setting
        enable_camera_movements = self.enable_camera_movements_check.isChecked()

        # Show dialog
        dialog = VideoPromptDialog(
            generator,
            scene.prompt,
            scene.duration_sec,
            llm_provider,
            llm_model,
            enable_camera_movements,
            self
        )

        if dialog.exec_():
            generated_prompt = dialog.get_prompt()
            if generated_prompt:
                # Prepend prompt style if not already present
                prompt_style = self._get_current_style()
                if prompt_style and prompt_style.lower() != 'none':
                    if not generated_prompt.lower().startswith(prompt_style.lower()):
                        generated_prompt = f"{prompt_style} style: {generated_prompt}"

                # Get widget and update it (with history)
                video_prompt_widget = self._get_cell_widget(scene_index, 10)
                if isinstance(video_prompt_widget, PromptFieldWidget):
                    video_prompt_widget.set_text(generated_prompt, add_to_history=True)

                scene.video_prompt = generated_prompt
                self.save_project()

                # Enable video button
                video_btn = self._get_cell_widget(scene_index, 4)
                if video_btn:
                    video_btn.setEnabled(True)

    def _toggle_row_wrap(self, row_index: int, wrapped: bool):
        """Toggle text wrapping for a row"""
        if not self.current_project or row_index >= len(self.current_project.scenes):
            return

        scene = self.current_project.scenes[row_index]
        scene.metadata['wrapped'] = wrapped

        self._apply_row_wrap(row_index, wrapped)
        self.save_project()

    def _apply_row_wrap(self, row_index: int, wrapped: bool):
        """Apply wrap state to all text fields in a row"""
        # Adjust row height and PromptFieldWidget heights based on wrap state
        # When wrapped, make row taller to show more of the prompt text
        if wrapped:
            # Make row much taller when wrapped to show full prompts
            self.scene_table.setRowHeight(row_index, 200)

            # Update PromptFieldWidget heights for columns 8, 9, 10 (Start, End, Video prompts)
            for col in [9, 10, 11]:  # Video, Start, End prompts
                container = self.scene_table.cellWidget(row_index, col)
                if container:
                    # Find the PromptFieldWidget inside the container
                    layout = container.layout()
                    if layout and layout.count() > 0:
                        widget = layout.itemAt(0).widget()
                        if widget and hasattr(widget, 'text_edit'):
                            # Allow text edit to expand to show full content
                            widget.text_edit.setMinimumHeight(180)
                            widget.text_edit.setMaximumHeight(180)
        else:
            # Return to default height
            self.scene_table.setRowHeight(row_index, 30)

            # Reset PromptFieldWidget heights for columns 8, 9, 10
            for col in [9, 10, 11]:  # Video, Start, End prompts
                container = self.scene_table.cellWidget(row_index, col)
                if container:
                    # Find the PromptFieldWidget inside the container
                    layout = container.layout()
                    if layout and layout.count() > 0:
                        widget = layout.itemAt(0).widget()
                        if widget and hasattr(widget, 'text_edit'):
                            # Return to compact single-line height
                            widget.text_edit.setMinimumHeight(30)
                            widget.text_edit.setMaximumHeight(200)  # Still allow some growth

    def open_character_reference_wizard(self):
        """Open the character reference generation wizard"""
        from gui.video.reference_generation_dialog import ReferenceGenerationDialog

        if not self.current_project:
            QMessageBox.warning(self, "No Project", "Please create or open a project first")
            return

        # Get parent video_project_tab for image generator
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'generate_reference_image_sync'):
            parent_tab = parent_tab.parent()

        if not parent_tab:
            QMessageBox.warning(
                self,
                "Image Generator Not Available",
                "Could not find parent tab with image generation capability"
            )
            return

        # Create image generator wrapper
        def image_generator(prompt: str, output_dir: Path, filename_prefix: str):
            return parent_tab.generate_reference_image_sync(prompt, output_dir, filename_prefix)

        # Open dialog
        dialog = ReferenceGenerationDialog(self, self.current_project, image_generator)
        dialog.references_generated.connect(self._on_references_generated)
        dialog.exec()

    def open_reference_library(self):
        """Open the reference library management tab"""
        # Get parent video_project_tab to switch to references tab
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'tab_widget'):
            parent_tab = parent_tab.parent()

        if parent_tab and hasattr(parent_tab, 'tab_widget'):
            # Find the References tab and switch to it
            for i in range(parent_tab.tab_widget.count()):
                if "References" in parent_tab.tab_widget.tabText(i):
                    parent_tab.tab_widget.setCurrentIndex(i)
                    return

        QMessageBox.information(
            self,
            "Reference Library",
            "Reference library tab not found. Check the main tab bar for '📸 References'."
        )

    def _on_references_generated(self, paths: List[Path]):
        """Handle references generated from wizard"""
        self.logger.info(f"References generated: {len(paths)} images")
        # Refresh UI if needed
        self.populate_scene_table()

    def enhance_all_prompts(self):
        """Request prompt enhancement"""
        self.generation_requested.emit("enhance_prompts", self.gather_generation_params())

    def enhance_for_video(self):
        """Request video prompt enhancement"""
        self.generation_requested.emit("enhance_for_video", self.gather_generation_params())

    def generate_images(self):
        """Request image generation"""
        self.generation_requested.emit("generate_images", self.gather_generation_params())
    
    def preview_video(self):
        """Request video preview"""
        self.generation_requested.emit("preview_video", self.gather_generation_params())
    
    def render_video(self):
        """Request video rendering"""
        self.generation_requested.emit("render_video", self.gather_generation_params())
    
    def gather_generation_params(self) -> Dict[str, Any]:
        """Gather all generation parameters"""
        # Get API keys
        google_key = self.config.get_api_key('google')
        openai_key = self.config.get_api_key('openai')
        anthropic_key = self.config.get_api_key('anthropic')
        stability_key = self.config.get_api_key('stability')

        # Get auth mode from config (for Google Cloud authentication support)
        auth_mode = self.config.get('auth_mode', 'api-key')
        google_project_id = self.config.get('google_project_id', None)

        self.logger.debug(f"Gathering generation params - API keys: google={google_key is not None}, openai={openai_key is not None}, anthropic={anthropic_key is not None}, stability={stability_key is not None}")
        self.logger.debug(f"Auth mode: {auth_mode}, Google project: {google_project_id}")

        return {
            'provider': self.img_provider_combo.currentText().lower(),
            'model': self.img_model_combo.currentText(),
            'llm_provider': self.llm_provider_combo.currentText().lower(),
            'llm_model': self.llm_model_combo.currentText(),
            'prompt_style': self._get_current_style(),
            'variants': 1,  # Always generate 1 image per scene
            'aspect_ratio': self.aspect_combo.currentText(),
            'resolution': self.resolution_combo.currentText(),
            'seed': self.seed_spin.value() if self.seed_spin.value() >= 0 else None,
            'negative_prompt': self.negative_prompt.text(),
            'video_provider': self.video_provider_combo.currentText(),
            'veo_model': self.veo_model_combo.currentText(),
            'ken_burns': self.ken_burns_check.isChecked(),
            'transitions': self.transitions_check.isChecked(),
            'captions': self.captions_check.isChecked(),
            'use_prev_last_frame': self.use_prev_last_frame_check.isChecked(),  # For Veo 3.1 smooth transitions
            'use_last_frame_for_next': False,  # Deprecated - replaced by use_prev_last_frame
            'continuity_mode': self.continuity_mode_combo.currentData(),  # Visual continuity for images
            'enable_camera_movements': self.enable_camera_movements_check.isChecked(),  # Camera movements in video prompts
            'enable_prompt_flow': self.enable_prompt_flow_check.isChecked(),  # Prompt flow/continuity
            'auth_mode': auth_mode,  # Include auth mode for Google Cloud support
            'google_auth_mode': auth_mode,  # Alias for video generation
            'google_project_id': google_project_id,  # Google Cloud project ID
            'google_api_key': google_key,
            'openai_api_key': openai_key,
            'anthropic_api_key': anthropic_key,
            'stability_api_key': stability_key,
        }
    
    def set_image_provider(self, provider_name: str):
        """Set the image provider from external source (e.g., Image tab)."""
        if hasattr(self, 'img_provider_combo'):
            # Find the provider in the combo
            index = -1
            for i in range(self.img_provider_combo.count()):
                if self.img_provider_combo.itemText(i).lower() == provider_name.lower():
                    index = i
                    break

            if index >= 0:
                self.img_provider_combo.blockSignals(True)
                self.img_provider_combo.setCurrentIndex(index)
                self.img_provider_combo.blockSignals(False)
                # Trigger the provider change handler to update models
                self.on_img_provider_changed(self.img_provider_combo.currentText())

    def set_llm_provider(self, provider_name: str, model_name: str = None):
        """Set the LLM provider from external source (e.g., Image tab)."""
        if hasattr(self, 'llm_provider_combo'):
            # Find the provider in the combo
            index = self.llm_provider_combo.findText(provider_name)
            if index >= 0:
                self.llm_provider_combo.blockSignals(True)
                self.llm_provider_combo.setCurrentIndex(index)
                self.llm_provider_combo.blockSignals(False)
                # Trigger the provider change handler to update models
                self.on_llm_provider_changed(provider_name)

                # Set the model if provided
                if model_name and hasattr(self, 'llm_model_combo'):
                    model_index = self.llm_model_combo.findText(model_name)
                    if model_index >= 0:
                        self.llm_model_combo.setCurrentIndex(model_index)

    def on_llm_provider_changed(self, provider: str):
        """Handle LLM provider change"""
        # Always clear the combo first
        self.llm_model_combo.clear()

        if provider == "None":
            self.llm_model_combo.setEnabled(False)
        else:
            self.llm_model_combo.setEnabled(True)
            # Populate with actual models for provider using centralized lists
            provider_map = {"claude": "anthropic", "lm studio": "lmstudio"}
            provider_id = provider_map.get(provider.lower(), provider.lower())

            models = get_provider_models(provider_id)
            if models:
                self.llm_model_combo.addItems(models)

        # Emit signal to notify other tabs
        model = self.llm_model_combo.currentText() if provider != "None" else None
        self.llm_provider_changed.emit(provider, model)

        # Auto-save if we have a project
        self._auto_save_settings()

    def _get_available_llm_providers(self) -> list:
        """Get list of LLM providers with configured API keys"""
        available = ["None"]

        # Map providers to their API key config names
        key_map = {
            "OpenAI": "openai_api_key",
            "Anthropic": "anthropic_api_key",
            "Google": "google_api_key",
            "Ollama": None,  # No key needed (local)
            "LM Studio": None  # No key needed (local)
        }

        for provider, key_name in key_map.items():
            # If no key needed (local providers) or key is configured
            if key_name is None or self.config.get(key_name):
                available.append(provider)

        return available

    def on_img_provider_changed(self, provider: str):
        """Handle image provider change"""
        # Clear the model combo first
        self.img_model_combo.clear()

        # Populate with models based on provider
        if provider in ["Google", "Gemini"]:  # Support both new and old naming
            self.img_model_combo.addItems([
                "gemini-2.5-flash-image-preview",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ])
        elif provider == "OpenAI":
            self.img_model_combo.addItems([
                "dall-e-3",
                "dall-e-2"
            ])
        elif provider == "Stability":
            self.img_model_combo.addItems([
                "stable-diffusion-xl-1024-v1-0",
                "stable-diffusion-xl-1024-v0-9",
                "stable-diffusion-512-v2-1",
                "stable-diffusion-768-v2-1"
            ])
        elif provider == "Local SD":
            self.img_model_combo.addItems([
                "stabilityai/stable-diffusion-xl-base-1.0",
                "stabilityai/stable-diffusion-2-1",
                "runwayml/stable-diffusion-v1-5"
            ])
        # Emit signal to notify other tabs
        self.image_provider_changed.emit(provider)

        # Auto-save if we have a project
        self._auto_save_settings()
    
    def on_video_provider_changed(self, provider: str):
        """Handle video provider change"""
        self.veo_model_combo.setVisible(provider == "Gemini Veo")

    def on_veo_model_changed(self, model: str):
        """Handle Veo model selection change"""
        self._auto_save_settings()

    def _auto_save_settings(self):
        """Auto-save settings to project if we have one"""
        # Skip auto-save during initial loading
        if not hasattr(self, '_loading_project'):
            self._loading_project = False

        if self._loading_project:
            return

        # Only auto-save if we have a project with a name
        if self.current_project and self.project_name.text().strip():
            try:
                self.update_project_from_ui()
                self.project_manager.save_project(self.current_project)
            except Exception as e:
                pass

    def _populate_styles_combo(self):
        """Populate the styles combo box with built-in and custom styles"""
        current = self.prompt_style_input.currentText()
        self.logger.debug(f"_populate_styles_combo: current='{current}', count={self.prompt_style_input.count()}")
        self.prompt_style_input.clear()

        # Add built-in styles
        self.prompt_style_input.addItems(self.builtin_styles)

        # Add separator if we have custom styles
        custom_styles = self.config.get('custom_prompt_styles', [])
        if custom_styles:
            self.prompt_style_input.insertSeparator(self.prompt_style_input.count())
            self.prompt_style_input.addItems(custom_styles)
            self.logger.debug(f"_populate_styles_combo: Added {len(custom_styles)} custom styles")

        # Add (Custom) option at the end
        self.prompt_style_input.insertSeparator(self.prompt_style_input.count())
        self.prompt_style_input.addItem("(Custom)")
        self.logger.debug(f"_populate_styles_combo: Total items={self.prompt_style_input.count()}")

        # Restore selection if still valid
        if current:
            index = self.prompt_style_input.findText(current)
            if index >= 0:
                self.prompt_style_input.setCurrentIndex(index)
                self.logger.debug(f"_populate_styles_combo: Restored selection to '{current}' at index {index}")

    def _on_style_changed(self):
        """Handle style selection change"""
        import traceback
        selected = self.prompt_style_input.currentText()
        self.logger.debug(f"_on_style_changed: selected='{selected}', loading={getattr(self, '_loading_project', False)}")
        self.logger.debug(f"_on_style_changed: Called from:\n{''.join(traceback.format_stack()[-4:-1])}")

        # Show/hide custom input based on selection
        if selected == "(Custom)":
            self.custom_style_input.show()
            self.custom_style_input.setFocus()
            self.logger.debug(f"_on_style_changed: Showed custom input, current value='{self.custom_style_input.text()}'")
        else:
            self.logger.debug(f"_on_style_changed: Hiding and clearing custom input")
            self.custom_style_input.hide()
            self.custom_style_input.clear()

        # Auto-save
        self._auto_save_settings()

    def _manage_custom_styles(self):
        """Open dialog to manage custom styles"""
        dialog = ManageStylesDialog(self.config, self)
        if dialog.exec() == QDialog.Accepted:
            # Refresh the combo box
            self._populate_styles_combo()

    def _get_current_style(self) -> str:
        """Get the current style value (from combo or custom input)"""
        selected = self.prompt_style_input.currentText()
        if selected == "(Custom)":
            custom_value = self.custom_style_input.text().strip() or "Cinematic"
            self.logger.debug(f"_get_current_style: (Custom) selected, returning: '{custom_value}'")
            return custom_value
        self.logger.debug(f"_get_current_style: Returning preset: '{selected}'")
        return selected

    def _set_current_style(self, style: str):
        """Set the current style value"""
        self.logger.debug(f"_set_current_style called with: '{style}'")

        if not style:
            # No style set, use default
            self.logger.debug("No style provided, using default (index 0)")
            self.prompt_style_input.setCurrentIndex(0)
            self.custom_style_input.hide()
            self.custom_style_input.clear()
            return

        # Check if it's a built-in or custom style in the combo
        index = self.prompt_style_input.findText(style)
        self.logger.debug(f"Found style '{style}' at index: {index}")

        if index >= 0 and style != "(Custom)":
            self.logger.debug(f"Setting combo to index {index} (preset style)")
            self.prompt_style_input.setCurrentIndex(index)
            self.custom_style_input.hide()
            self.custom_style_input.clear()
        else:
            # It's a custom/freeform style - select (Custom) and populate input
            custom_index = self.prompt_style_input.findText("(Custom)")
            self.logger.debug(f"Style not in preset list, using (Custom) at index: {custom_index}")

            if custom_index >= 0:
                self.prompt_style_input.setCurrentIndex(custom_index)
                self.custom_style_input.setText(style)
                self.custom_style_input.show()
                self.logger.debug(f"Set custom input to: '{style}'")
            else:
                # Fallback: just set to first item if (Custom) not found
                self.logger.warning("(Custom) option not found in combo, using default")
                self.prompt_style_input.setCurrentIndex(0)
                self.custom_style_input.hide()
                self.custom_style_input.clear()

    def load_input_file(self):
        """Load input from file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Input File",
            "", "Text Files (*.txt *.md);;All Files (*.*)"
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.input_text.setPlainText(f.read())
            except Exception as e:
                self.logger.error(f"Failed to load file: {e}", exc_info=True)
                dialog_manager = get_dialog_manager(self)
                dialog_manager.show_error("Error", f"Failed to load file: {e}")
    
    def browse_audio_file(self):
        """Browse for audio file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File",
            "", "Audio Files (*.mp3 *.wav *.m4a *.ogg);;All Files (*.*)"
        )
        if filename:
            self.audio_file_label.setText(Path(filename).name)
            self.clear_audio_btn.setEnabled(True)
            if self.current_project:
                from core.video.project import AudioTrack
                # Clear existing tracks and add new one
                self.current_project.audio_tracks = []
                self.current_project.audio_tracks.append(AudioTrack(
                    file_path=Path(filename),
                    volume=self.volume_slider.value() / 100.0,
                    fade_in_duration=self.fade_in_spin.value(),
                    fade_out_duration=self.fade_out_spin.value()
                ))

                # Refresh wizard after audio file is loaded
                self._refresh_wizard()
    
    def clear_audio(self):
        """Clear audio selection"""
        self.audio_file_label.setText("No file")
        self.clear_audio_btn.setEnabled(False)
        if self.current_project:
            self.current_project.audio_tracks = []
    
    def browse_midi_file(self):
        """Browse for MIDI file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select MIDI File",
            "", "MIDI Files (*.mid *.midi);;All Files (*.*)"
        )
        if filename:
            try:
                # Process MIDI file
                from core.video.midi_utils import get_midi_processor
                processor = get_midi_processor()
                timing_data = processor.extract_timing(Path(filename))
                
                # Update UI
                self.midi_file_label.setText(Path(filename).name)
                self.midi_info_label.setText(
                    f"{timing_data.tempo_bpm:.0f} BPM, {timing_data.time_signature}, "
                    f"{timing_data.duration_sec:.1f}s"
                )
                self.clear_midi_btn.setEnabled(True)
                self.sync_mode_combo.setEnabled(True)
                self.snap_strength_slider.setEnabled(True)
                self.extract_lyrics_btn.setEnabled(True)
                self.karaoke_group.setVisible(True)
                
                # Store in project
                if self.current_project:
                    self.current_project.midi_file_path = Path(filename)
                    self.current_project.midi_timing_data = timing_data

                    # Refresh wizard after MIDI file is loaded
                    self._refresh_wizard()

            except Exception as e:
                self.logger.error(f"Failed to process MIDI file: {e}", exc_info=True)
                dialog_manager = get_dialog_manager(self)
                dialog_manager.show_error("MIDI Error", f"Failed to process MIDI file: {e}")
    
    def clear_midi(self):
        """Clear MIDI file"""
        self.midi_file_label.setText("No file")
        self.midi_info_label.setText("")
        self.clear_midi_btn.setEnabled(False)
        self.sync_mode_combo.setEnabled(False)
        self.snap_strength_slider.setEnabled(False)
        self.extract_lyrics_btn.setEnabled(False)
        self.karaoke_group.setVisible(False)
        
        if self.current_project:
            self.current_project.midi_file_path = None
            self.current_project.midi_timing_data = None
    
    def extract_midi_lyrics(self):
        """Extract lyrics from MIDI or align to timing"""
        if not self.current_project or not self.current_project.midi_timing_data:
            return
        
        # Get lyrics from MIDI timing data
        midi_lyrics = self.current_project.midi_timing_data.lyrics
        
        if midi_lyrics:
            # Format as text and insert into input
            lyrics_text = "\n".join([text for _, text in midi_lyrics])
            self.input_text.setPlainText(lyrics_text)
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_info("Lyrics Extracted", 
                                  f"Extracted {len(midi_lyrics)} lyric events from MIDI")
        else:
            # Try to align existing text to MIDI timing
            text = self.input_text.toPlainText()
            if text:
                try:
                    from core.video.midi_utils import get_midi_processor
                    processor = get_midi_processor()
                    aligned = processor._align_lyrics_to_timing(
                        text, self.current_project.midi_timing_data
                    )
                    if aligned:
                        dialog_manager = get_dialog_manager(self)
                        dialog_manager.show_info("Lyrics Aligned",
                                          f"Aligned {len(aligned)} words to MIDI timing")
                except Exception as e:
                    self.logger.error(f"MIDI lyrics alignment error: {e}", exc_info=True)
                    dialog_manager = get_dialog_manager(self)
                    dialog_manager.show_error("MIDI Error", str(e))
            else:
                dialog_manager = get_dialog_manager(self)
                dialog_manager.show_info("No Lyrics",
                                      "No lyrics found in MIDI. Enter lyrics manually to align to beats.")
    
    def _recalculate_scene_timing(self):
        """Recalculate scene timing using LLM or MIDI sync."""
        if not self.current_project or not self.current_project.scenes:
            return
        
        from core.video.llm_sync_v2 import LLMSyncAssistant
        
        # Get current settings
        llm_provider = self.current_project.llm_provider if hasattr(self.current_project, 'llm_provider') else None
        llm_model = self.current_project.llm_model if hasattr(self.current_project, 'llm_model') else None
        use_llm = llm_provider and llm_model
        
        # Get total duration
        total_duration = self.duration_spin.value()  # in seconds
        if total_duration <= 0:
            total_duration = 120  # Default to 2 minutes
        
        # Get MIDI timing data if available
        midi_timing = self.current_project.midi_timing_data if hasattr(self.current_project, 'midi_timing_data') else None
        sections = {}
        
        # Handle MidiTimingData object or dict
        if midi_timing:
            if hasattr(midi_timing, 'duration_sec'):
                # It's a MidiTimingData object
                total_duration = midi_timing.duration_sec
                if hasattr(midi_timing, 'sections'):
                    sections = midi_timing.sections
            elif isinstance(midi_timing, dict) and 'duration_sec' in midi_timing:
                # It's a dict
                total_duration = midi_timing['duration_sec']
                sections = midi_timing.get('sections', {})
        
        # Extract lyrics from scenes (skip section markers)
        lyrics_lines = [scene.source for scene in self.current_project.scenes
                       if not (scene.source.strip().startswith('[') and scene.source.strip().endswith(']'))]
        
        if use_llm or sections:
            # Use LLM sync assistant
            sync_assistant = LLMSyncAssistant(provider=llm_provider if use_llm else None,
                                            model=llm_model if use_llm else None)
            timed_lyrics = sync_assistant.estimate_lyric_timing(lyrics_lines, total_duration, sections)

            # Fill instrumental gaps
            if timed_lyrics:
                self.logger.info("Detecting and filling instrumental gaps during recalculation...")
                timed_lyrics_with_gaps = sync_assistant.fill_instrumental_gaps(
                    timed_lyrics=timed_lyrics,
                    total_duration=total_duration,
                    min_gap_duration=1.0
                )

                # Create/update scenes to include instrumental sections
                from core.video.project import Scene
                new_scenes = []
                lyric_index = 0

                for timed_item in timed_lyrics_with_gaps:
                    if timed_item.text == "[Instrumental]":
                        instrumental_scene = Scene(
                            source="[Instrumental]",
                            prompt="",
                            duration_sec=timed_item.end_time - timed_item.start_time,
                            metadata={
                                'start_time': timed_item.start_time,
                                'end_time': timed_item.end_time,
                                'section': timed_item.section_type or 'instrumental',
                                'is_instrumental': True
                            }
                        )
                        new_scenes.append(instrumental_scene)
                    else:
                        while lyric_index < len(self.current_project.scenes) and self.current_project.scenes[lyric_index].source.strip().startswith('[') and self.current_project.scenes[lyric_index].source.strip().endswith(']'):
                            new_scenes.append(self.current_project.scenes[lyric_index])
                            lyric_index += 1
                        if lyric_index < len(self.current_project.scenes):
                            new_scenes.append(self.current_project.scenes[lyric_index])
                            lyric_index += 1

                self.current_project.scenes = new_scenes
                timed_lyrics = timed_lyrics_with_gaps
                self.logger.info(f"Updated scenes during recalc: {len(self.current_project.scenes)} total scenes")

            # Update scene timings (skip section markers)
            if timed_lyrics:
                lyric_index = 0
                for i, scene in enumerate(self.current_project.scenes):
                    # Skip section markers
                    if scene.source.strip().startswith('[') and scene.source.strip().endswith(']'):
                        scene.duration_sec = 0.0  # Section markers get no time
                        continue

                    # Check if this scene was batched (contains multiple lyrics)
                    batched_count = scene.metadata.get('batched_count', 1)

                    if batched_count > 1:
                        # Batched scene - need to sum durations from multiple LLM timings
                        if lyric_index + batched_count <= len(timed_lyrics):
                            # Get all timings for this batched scene
                            batch_timings = timed_lyrics[lyric_index:lyric_index + batched_count]

                            # Calculate total duration from first start to last end
                            first_timing = batch_timings[0]
                            last_timing = batch_timings[-1]
                            total_duration = last_timing.end_time - first_timing.start_time

                            scene.duration_sec = total_duration
                            scene.metadata['start_time'] = first_timing.start_time
                            scene.metadata['end_time'] = last_timing.end_time

                            # Update the lyric_timings metadata with LLM-precise timings
                            if 'lyric_timings' in scene.metadata:
                                for j, (lyric_timing, timed_lyric) in enumerate(zip(scene.metadata['lyric_timings'], batch_timings)):
                                    lyric_timing['start_sec'] = timed_lyric.start_time
                                    lyric_timing['end_sec'] = timed_lyric.end_time
                                    lyric_timing['duration_sec'] = timed_lyric.end_time - timed_lyric.start_time

                            if first_timing.section_type:
                                scene.metadata['section'] = first_timing.section_type

                            lyric_index += batched_count
                    else:
                        # Single lyric scene
                        if lyric_index < len(timed_lyrics):
                            timed_lyric = timed_lyrics[lyric_index]
                            scene.duration_sec = timed_lyric.end_time - timed_lyric.start_time
                            scene.metadata['start_time'] = timed_lyric.start_time
                            scene.metadata['end_time'] = timed_lyric.end_time
                            if timed_lyric.section_type:
                                scene.metadata['section'] = timed_lyric.section_type
                            lyric_index += 1

                self.logger.info(f"Recalculated timing for {lyric_index} lyrics across {len([s for s in self.current_project.scenes if not (s.source.strip().startswith('[') and s.source.strip().endswith(']'))])} scenes using {'LLM' if use_llm else 'MIDI'} sync")
        else:
            # Simple even distribution
            avg_duration = total_duration / len(self.current_project.scenes)
            current_time = 0.0
            
            for scene in self.current_project.scenes:
                # Skip section markers or give them less time
                if scene.source.startswith('[') and scene.source.endswith(']'):
                    scene.duration_sec = avg_duration * 0.3
                else:
                    scene.duration_sec = avg_duration
                
                scene.metadata['start_time'] = current_time
                scene.metadata['end_time'] = current_time + scene.duration_sec
                current_time += scene.duration_sec
            
            self.logger.info(f"Recalculated timing for {len(self.current_project.scenes)} scenes with even distribution")

        # CRITICAL: Split then batch scenes AFTER instrumental insertion and timing recalculation
        # Split must happen BEFORE batching to ensure no scene exceeds 8 seconds
        # This must happen AFTER instrumentals to preserve 1:1 lyric-to-scene mapping
        from core.video.storyboard import StoryboardGenerator
        storyboard_gen = StoryboardGenerator(target_scene_duration=8.0)

        self.logger.info(f"Splitting long scenes (>{storyboard_gen.target_scene_duration}s)...")
        self.current_project.scenes = storyboard_gen.split_long_scenes(self.current_project.scenes, max_duration=storyboard_gen.target_scene_duration)
        self.logger.info(f"After splitting: {len(self.current_project.scenes)} scenes")

        self.logger.info(f"Batching {len(self.current_project.scenes)} scenes to aim for {storyboard_gen.target_scene_duration}-second optimal duration...")
        self.current_project.scenes = storyboard_gen._batch_scenes_for_optimal_duration(self.current_project.scenes)
        self.logger.info(f"After batching: {len(self.current_project.scenes)} scenes")

        # Auto-save the fixed timing
        self.save_project()

    # ========== Wizard Management Methods ==========

    def _toggle_wizard(self, checked):
        """Toggle wizard visibility and collapse/expand width"""
        if checked:
            # Show the wizard container
            self.wizard_container.setVisible(True)
            self.wizard_toggle_btn_top.setText("◀ Hide")

            # Restore minimum width constraint
            self.wizard_container.setMinimumWidth(300)

            # Restore to original width (or 300 if not set)
            sizes = self.h_splitter.sizes()
            sizes[0] = self.wizard_original_width
            self.h_splitter.setSizes(sizes)
        else:
            # Hide the wizard container completely
            self.wizard_container.setVisible(False)
            self.wizard_toggle_btn_top.setText("▶ Show")

            # Save current width before collapsing
            current_width = self.h_splitter.sizes()[0]
            if current_width > 50:  # Only save if not already collapsed
                self.wizard_original_width = current_width

            # Collapse to zero (container is hidden)
            sizes = self.h_splitter.sizes()
            sizes[0] = 0
            self.h_splitter.setSizes(sizes)

        # Save wizard visibility state
        self.config.set('video_tab_wizard_hidden', not checked)
        self.config.save()

    def _on_splitter_moved(self, pos, index):
        """Enforce max width constraint for wizard panel (50% of window)"""
        # Only check first splitter handle (between wizard and left panel)
        if index != 0:
            return

        # Only check when wizard container is visible
        if not self.wizard_container.isVisible():
            return

        # Get current sizes
        sizes = self.h_splitter.sizes()
        total_width = sum(sizes)

        # Only enforce if total width is reasonable (splitter has been sized)
        if total_width < 100:
            return

        max_wizard_width = total_width // 2  # 50% of total width

        # Only adjust if wizard panel exceeds the maximum
        if sizes[0] > max_wizard_width:
            # Calculate how much to redistribute
            excess = sizes[0] - max_wizard_width

            # Limit wizard to max 50% width
            sizes[0] = max_wizard_width

            # Redistribute excess to other panels proportionally
            if len(sizes) > 2:
                # Calculate proportional distribution
                other_total = sizes[1] + sizes[2]
                if other_total > 0:
                    ratio_1 = sizes[1] / other_total
                    ratio_2 = sizes[2] / other_total
                    sizes[1] += int(excess * ratio_1)
                    sizes[2] += excess - int(excess * ratio_1)
                else:
                    sizes[1] += excess // 2
                    sizes[2] += excess - (excess // 2)

            # Apply the adjusted sizes
            self.h_splitter.setSizes(sizes)

    def _create_wizard_widget(self):
        """Create wizard widget for current project"""
        if not self.current_project:
            return

        # Remove old wizard if exists
        if self.wizard_widget:
            self.wizard_content_layout.removeWidget(self.wizard_widget)
            self.wizard_widget.deleteLater()

        # Remove placeholder
        if self.wizard_placeholder:
            self.wizard_placeholder.setVisible(False)

        # Create new wizard
        self.wizard_widget = WorkflowWizardWidget(self.current_project, self)
        self.wizard_widget.action_requested.connect(self._on_wizard_action)
        self.wizard_widget.step_skipped.connect(self._on_wizard_step_skipped)

        self.wizard_content_layout.addWidget(self.wizard_widget)

    def _on_wizard_action(self, step, choice):
        """Handle wizard action request"""
        from core.video.workflow_wizard import WorkflowStep

        # Map wizard steps to actual actions
        if step == WorkflowStep.INPUT_TEXT:
            # Focus on input text field
            if hasattr(self, 'input_text'):
                self.input_text.setFocus()

        elif step == WorkflowStep.MIDI_FILE:
            # Open MIDI file dialog
            self.browse_midi_file()

        elif step == WorkflowStep.AUDIO_FILE:
            # Open audio file dialog
            self.browse_audio_file()

        elif step == WorkflowStep.GENERATE_STORYBOARD:
            # Trigger storyboard generation
            self.generate_storyboard()

        elif step == WorkflowStep.ENHANCE_PROMPTS:
            # Trigger prompt enhancement
            if choice == "enhance":
                self.enhance_all_prompts()
            elif choice == "skip":
                if self.wizard_widget:
                    self.wizard_widget.wizard.mark_step_skipped(step)
                    self.wizard_widget.refresh_wizard_display()

        elif step == WorkflowStep.GENERATE_MEDIA:
            # Trigger media generation based on choice
            if choice == "images":
                self.generate_images()
            elif choice == "videos":
                self.enhance_for_video()  # This generates video clips

        elif step == WorkflowStep.REVIEW_APPROVE:
            # Focus on scene table for review
            if hasattr(self, 'scene_table'):
                self.scene_table.setFocus()

        elif step == WorkflowStep.EXPORT_VIDEO:
            # Trigger video export
            self.render_video()

    def _on_wizard_step_skipped(self, step):
        """Handle wizard step skipped"""
        self.logger.info(f"Skipped workflow step: {step.value}")
        # Save project with updated state
        if self.current_project:
            self.save_project()

    def _refresh_wizard(self):
        """Refresh wizard display after project changes"""
        if self.wizard_widget and self.wizard_widget.isVisible():
            self.wizard_widget.refresh_wizard_display()

    # ========== End Wizard Management Methods ==========

    def update_ui_state(self):
        """Update UI element states based on project"""
        has_project = self.current_project is not None
        has_scenes = has_project and len(self.current_project.scenes) > 0
        has_images = has_scenes and any(s.images for s in self.current_project.scenes)
        has_video_clips = has_scenes and any(s.video_clip for s in self.current_project.scenes)

        self.save_btn.setEnabled(has_project)
        self.save_as_btn.setEnabled(has_project)
        self.generate_storyboard_btn.setEnabled(True)
        self.enhance_prompts_btn.setEnabled(has_scenes)
        # Enable video enhancement when scenes have prompts (image prompts are used as base)
        has_prompts = has_scenes and any(s.prompt for s in self.current_project.scenes)
        self.enhance_video_prompts_btn.setEnabled(has_prompts)
        self.generate_images_btn.setEnabled(has_scenes)
        self.preview_btn.setEnabled(has_images)
        # Enable render button if there are either images OR video clips
        self.render_btn.setEnabled(has_images or has_video_clips)
    
    def update_project_from_ui(self):
        """Update project from UI values"""
        if not self.current_project:
            return
        
        self.current_project.name = self.project_name.text()
        self.current_project.input_text = self.input_text.toPlainText()
        self.current_project.input_format = self.format_combo.currentText()
        self.current_project.timing_preset = self.pacing_combo.currentText()
        
        # Update target duration from spin box
        duration_sec = self.duration_spin.value()
        hours = duration_sec // 3600
        minutes = (duration_sec % 3600) // 60
        seconds = duration_sec % 60
        self.current_project.target_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Save LLM provider settings - preserve exact case
        llm_provider = self.llm_provider_combo.currentText()
        llm_model = self.llm_model_combo.currentText() if llm_provider != "None" else None

        if llm_provider != "None":
            self.current_project.llm_provider = llm_provider  # Keep exact case
            self.current_project.llm_model = llm_model
        else:
            self.current_project.llm_provider = None
            self.current_project.llm_model = None
        
        # Save image provider settings - preserve exact case
        img_provider = self.img_provider_combo.currentText()
        img_model = self.img_model_combo.currentText()

        self.current_project.image_provider = img_provider  # Keep exact case
        self.current_project.image_model = img_model
        
        # Save video provider settings
        self.current_project.video_provider = self.video_provider_combo.currentText().lower()
        if self.video_provider_combo.currentText() == "Google Veo":
            self.current_project.video_model = self.veo_model_combo.currentText()
        else:
            self.current_project.video_model = None
        
        # Save style settings
        self.current_project.aspect_ratio = self.aspect_combo.currentText()
        self.current_project.resolution = self.resolution_combo.currentText()
        self.current_project.seed = self.seed_spin.value() if self.seed_spin.value() >= 0 else None
        self.current_project.negative_prompt = self.negative_prompt.text()
        self.current_project.continuity_mode = self.continuity_mode_combo.currentData()

        # Save prompt template/style
        self.current_project.prompt_style = self._get_current_style()

        # Save generation settings (variants always 1)
        self.current_project.ken_burns = self.ken_burns_check.isChecked()
        self.current_project.transitions = self.transitions_check.isChecked()
        self.current_project.captions = self.captions_check.isChecked()

        # Save video prompt generation settings
        self.current_project.enable_camera_movements = self.enable_camera_movements_check.isChecked()
        self.current_project.enable_prompt_flow = self.enable_prompt_flow_check.isChecked()

        # Save video player settings
        self.current_project.video_muted = self.audio_output.isMuted()

        # Save continuity settings
        self.current_project.enable_continuity = self.enable_continuity_checkbox.isChecked()
        self.current_project.enable_enhanced_storyboard = self.enable_enhanced_storyboard.isChecked()
        # Note: Smart continuity detection now happens automatically during video generation
        # No need for use_last_frame_for_continuous or auto_link_enabled checkboxes

        # IMPORTANT: Save audio and MIDI file information
        # These are already set when browsing, but we need to ensure they're preserved
        # The audio_track and midi_file_path are already set in browse_audio_file and browse_midi_file
        # No additional action needed here as they're already part of self.current_project
        
    def load_project_to_ui(self):
        """Load project data to UI"""
        if not self.current_project:
            return
        
        self.logger.info("=== STARTING load_project_to_ui ===")
        self.logger.info(f"Project has LLM: {self.current_project.llm_provider}/{self.current_project.llm_model}")
        self.logger.info(f"Project has Image: {self.current_project.image_provider}/{self.current_project.image_model}")
        
        # Set flag to prevent auto-save during loading
        self._loading_project = True
        
        try:
            # Load basic project info
            self.project_name.setText(self.current_project.name)
            self.input_text.setPlainText(self.current_project.input_text or "")
            
            # Load format and timing settings
            if hasattr(self.current_project, 'input_format'):
                index = self.format_combo.findText(self.current_project.input_format)
                if index >= 0:
                    self.format_combo.setCurrentIndex(index)
            
            if hasattr(self.current_project, 'timing_preset'):
                index = self.pacing_combo.findText(self.current_project.timing_preset)
                if index >= 0:
                    self.pacing_combo.setCurrentIndex(index)
            
            # Disconnect signals during restoration to prevent cascading changes
            self.llm_provider_combo.currentTextChanged.disconnect()
            self.img_provider_combo.currentTextChanged.disconnect()
            self.prompt_style_input.currentTextChanged.disconnect()

            try:
                # Load LLM provider settings
                if self.current_project.llm_provider:
                    # Find and set the provider - handle both exact case and legacy lowercase
                    provider_text = self.current_project.llm_provider
                    
                    # First try exact match (new format)
                    if provider_text in ["OpenAI", "Google", "Gemini", "Anthropic", "Ollama", "LM Studio"]:
                        # Map legacy "Gemini" to "Google"
                        if provider_text == "Gemini":
                            provider_text = "Google"
                    # Then handle legacy lowercase format
                    elif provider_text.lower() == 'openai':
                        provider_text = 'OpenAI'
                    elif provider_text.lower() in ['claude', 'anthropic']:
                        provider_text = 'Anthropic'
                    elif provider_text.lower() in ['gemini', 'google']:
                        provider_text = 'Google'
                    elif provider_text.lower() == 'ollama':
                        provider_text = 'Ollama'
                    elif provider_text.lower() == 'lm studio':
                        provider_text = 'LM Studio'

                    index = self.llm_provider_combo.findText(provider_text)
                    if index >= 0:
                        self.llm_provider_combo.setCurrentIndex(index)

                        # Populate the model combo based on provider without clearing
                        self.llm_model_combo.clear()
                        if provider_text != "None":
                            self.llm_model_combo.setEnabled(True)
                            # Use centralized model lists
                            provider_map = {"claude": "anthropic", "google": "gemini", "lm studio": "lmstudio"}
                            provider_id = provider_map.get(provider_text.lower(), provider_text.lower())

                            models = get_provider_models(provider_id)
                            if models:
                                self.llm_model_combo.addItems(models)
                        else:
                            self.llm_model_combo.setEnabled(False)
                        
                        # Now set the model
                        if self.current_project.llm_model:
                            model_index = self.llm_model_combo.findText(self.current_project.llm_model)
                            if model_index >= 0:
                                self.llm_model_combo.setCurrentIndex(model_index)
                                self.logger.info(f"Restored LLM: {provider_text}/{self.current_project.llm_model}")
                            else:
                                self.logger.warning(f"LLM model not found in combo: {self.current_project.llm_model}")
                    else:
                        self.logger.warning(f"LLM provider not found in combo: {provider_text}")
                else:
                    self.llm_provider_combo.setCurrentIndex(0)  # Set to "None"
                
                # Load image provider settings
                if self.current_project.image_provider:
                    # Handle both exact case and legacy lowercase
                    provider_text = self.current_project.image_provider
                    
                    # First try exact match (new format)
                    if provider_text in ["OpenAI", "Google", "Gemini", "Stability", "Local SD"]:
                        # Map legacy "Gemini" to "Google"
                        if provider_text == "Gemini":
                            provider_text = "Google"
                    # Then handle legacy lowercase format
                    elif provider_text.lower() == 'openai':
                        provider_text = 'OpenAI'
                    elif provider_text.lower() in ['gemini', 'google']:
                        provider_text = 'Google'
                    elif provider_text.lower() == 'stability':
                        provider_text = 'Stability'
                    elif provider_text.lower() == 'local sd':
                        provider_text = 'Local SD'

                    index = self.img_provider_combo.findText(provider_text)
                    if index >= 0:
                        self.img_provider_combo.setCurrentIndex(index)

                        # Populate the model combo based on provider without clearing
                        self.img_model_combo.clear()
                        if provider_text in ["Google", "Gemini"]:  # Support both new and old naming
                            self.img_model_combo.addItems(["gemini-2.5-flash-image-preview", "gemini-2.5-flash", "gemini-2.5-pro"])
                        elif provider_text == "OpenAI":
                            self.img_model_combo.addItems(["dall-e-3", "dall-e-2"])
                        elif provider_text == "Stability":
                            self.img_model_combo.addItems(["stable-diffusion-xl-1024-v1-0", "stable-diffusion-v1-6"])
                        elif provider_text == "Local SD":
                            self.img_model_combo.addItems(["stabilityai/stable-diffusion-2-1", "runwayml/stable-diffusion-v1-5"])
                        
                        # Now set the model
                        if self.current_project.image_model:
                            model_index = self.img_model_combo.findText(self.current_project.image_model)
                            if model_index >= 0:
                                self.img_model_combo.setCurrentIndex(model_index)
                                self.logger.info(f"Restored Image: {provider_text}/{self.current_project.image_model}")
                            else:
                                self.logger.warning(f"Image model not found in combo: {self.current_project.image_model}")
                    else:
                        self.logger.warning(f"Image provider not found in combo: {provider_text}")

                # Load prompt style (before reconnecting signals)
                if hasattr(self.current_project, 'prompt_style') and self.current_project.prompt_style:
                    self.logger.info(f"Loading prompt style: {self.current_project.prompt_style}")
                    self._set_current_style(self.current_project.prompt_style)

            finally:
                # Reconnect signals after restoration
                self.llm_provider_combo.currentTextChanged.connect(self.on_llm_provider_changed)
                self.img_provider_combo.currentTextChanged.connect(self.on_img_provider_changed)
                self.prompt_style_input.currentTextChanged.connect(self._on_style_changed)

            # Load video provider settings
            if self.current_project.video_provider:
                if self.current_project.video_provider == "slideshow":
                    self.video_provider_combo.setCurrentIndex(0)
                elif self.current_project.video_provider == "veo" or self.current_project.video_provider == "google veo":
                    index = self.video_provider_combo.findText("Google Veo")
                    if index >= 0:
                        self.video_provider_combo.setCurrentIndex(index)
                        # Set Veo model if available
                        if self.current_project.video_model:
                            model_index = self.veo_model_combo.findText(self.current_project.video_model)
                            if model_index >= 0:
                                self.veo_model_combo.setCurrentIndex(model_index)
            
            # Load style settings
            if hasattr(self.current_project, 'aspect_ratio') and self.current_project.aspect_ratio:
                index = self.aspect_combo.findText(self.current_project.aspect_ratio)
                if index >= 0:
                    self.aspect_combo.setCurrentIndex(index)
            
            if hasattr(self.current_project, 'resolution') and self.current_project.resolution:
                index = self.resolution_combo.findText(self.current_project.resolution)
                if index >= 0:
                    self.resolution_combo.setCurrentIndex(index)

            if hasattr(self.current_project, 'seed') and self.current_project.seed is not None:
                self.seed_spin.setValue(self.current_project.seed)

            if hasattr(self.current_project, 'continuity_mode') and self.current_project.continuity_mode:
                # Find index by matching the data value
                for i in range(self.continuity_mode_combo.count()):
                    if self.continuity_mode_combo.itemData(i) == self.current_project.continuity_mode:
                        self.continuity_mode_combo.setCurrentIndex(i)
                        break
            
            if hasattr(self.current_project, 'negative_prompt') and self.current_project.negative_prompt:
                self.negative_prompt.setText(self.current_project.negative_prompt)

            # Prompt style is now loaded earlier (before signal reconnection)

            # Load generation settings (variants always 1)

            if hasattr(self.current_project, 'ken_burns'):
                self.ken_burns_check.setChecked(self.current_project.ken_burns)

            if hasattr(self.current_project, 'transitions'):
                self.transitions_check.setChecked(self.current_project.transitions)
            
            if hasattr(self.current_project, 'captions'):
                self.captions_check.setChecked(self.current_project.captions)

            # Load video prompt generation settings
            if hasattr(self.current_project, 'enable_camera_movements'):
                self.enable_camera_movements_check.setChecked(self.current_project.enable_camera_movements)
            else:
                self.enable_camera_movements_check.setChecked(True)  # Default to enabled

            if hasattr(self.current_project, 'enable_prompt_flow'):
                self.enable_prompt_flow_check.setChecked(self.current_project.enable_prompt_flow)
            else:
                self.enable_prompt_flow_check.setChecked(True)  # Default to enabled

            # Load video player settings
            if hasattr(self.current_project, 'video_muted'):
                is_muted = self.current_project.video_muted
                self.audio_output.setMuted(is_muted)
                self.mute_btn.setChecked(is_muted)
                self.mute_btn.setText("🔇 Unmute" if is_muted else "🔊 Mute")

            # Load continuity settings
            if hasattr(self.current_project, 'enable_continuity'):
                self.enable_continuity_checkbox.setChecked(self.current_project.enable_continuity)
            
            if hasattr(self.current_project, 'enable_enhanced_storyboard'):
                self.enable_enhanced_storyboard.setChecked(self.current_project.enable_enhanced_storyboard)

            # Note: Smart continuity detection now happens automatically
            # No UI controls needed for use_last_frame_for_continuous or auto_link_enabled

            # Load target duration
            if self.current_project.target_duration:
                try:
                    parts = self.current_project.target_duration.split(':')
                    if len(parts) == 3:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        seconds = int(parts[2])
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        self.duration_spin.setValue(total_seconds)
                except Exception as e:
                    self.logger.warning(f"Could not parse target duration: {e}")
            
            # Load audio track if present
            if self.current_project.audio_tracks and len(self.current_project.audio_tracks) > 0:
                audio_track = self.current_project.audio_tracks[0]
                if audio_track.file_path:
                    self.audio_file_label.setText(Path(audio_track.file_path).name)
                    self.clear_audio_btn.setEnabled(True)
                    # Set audio controls
                    self.volume_slider.setValue(int(audio_track.volume * 100))
                    self.fade_in_spin.setValue(audio_track.fade_in_duration)
                    self.fade_out_spin.setValue(audio_track.fade_out_duration)
            else:
                self.audio_file_label.setText("No file")
                self.clear_audio_btn.setEnabled(False)
            
            # Load MIDI file if present
            if self.current_project.midi_file_path:
                self.midi_file_label.setText(Path(self.current_project.midi_file_path).name)
                self.clear_midi_btn.setEnabled(True)
                self.sync_mode_combo.setEnabled(True)
                self.snap_strength_slider.setEnabled(True)
                self.extract_lyrics_btn.setEnabled(True)
                self.karaoke_group.setVisible(True)
                
                # Set sync controls
                if hasattr(self.current_project, 'sync_mode'):
                    index = self.sync_mode_combo.findText(self.current_project.sync_mode.title())
                    if index >= 0:
                        self.sync_mode_combo.setCurrentIndex(index)
                
                if hasattr(self.current_project, 'snap_strength'):
                    self.snap_strength_slider.setValue(int(self.current_project.snap_strength * 100))
                
                # Display MIDI info if available
                if self.current_project.midi_timing_data:
                    timing_data = self.current_project.midi_timing_data
                    self.midi_info_label.setText(
                        f"{timing_data.tempo_bpm:.0f} BPM, {timing_data.time_signature}, "
                        f"{timing_data.duration_sec:.1f}s"
                    )
            else:
                self.midi_file_label.setText("No file")
                self.midi_info_label.setText("")
                self.clear_midi_btn.setEnabled(False)
                self.sync_mode_combo.setEnabled(False)
                self.snap_strength_slider.setEnabled(False)
                self.extract_lyrics_btn.setEnabled(False)
                self.karaoke_group.setVisible(False)
            
            # Load scene table
            num_scenes = len(self.current_project.scenes) if self.current_project.scenes else 0
            self.logger.info(f"Loaded project with {num_scenes} scenes")
            
            # Check and fix incorrect scene timing if needed
            if self.current_project.scenes and len(self.current_project.scenes) > 2:
                durations = [s.duration_sec for s in self.current_project.scenes]
                # If most scenes have exactly 0.5 sec duration (except maybe the first), recalculate
                non_first_durations = durations[1:] if len(durations) > 1 else durations
                if non_first_durations.count(0.5) > len(non_first_durations) * 0.7:
                    self.logger.warning("Detected incorrect scene timing, recalculating...")
                    self._recalculate_scene_timing()
            
            self.populate_scene_table()
            
            # Update UI state
            self.update_ui_state()
            
            # Update status to show scene count
            self.status_label.setText(f"Loaded: {self.current_project.name} ({num_scenes} scenes)")
            
            # Save project with updated format if needed
            if not hasattr(self.current_project, 'variants'):
                self.logger.info("Upgrading project format and saving...")
                self.save_project()

            # Extract first frames from videos if they exist but frames haven't been extracted yet
            self._extract_all_first_frames()

        except Exception as e:
            self.logger.error(f"Error loading project to UI: {e}", exc_info=True)
            dialog_manager = get_dialog_manager(self)
            dialog_manager.show_error("Load Error",
                              f"Some project data could not be loaded.\nCheck logs for details.\nError: {e}")
        finally:
            # Clear loading flag to enable auto-save
            self._loading_project = False

            # Log final state
            self.logger.info("=== LOAD_PROJECT_TO_UI COMPLETE ===")
            self.logger.info(f"Style combo: '{self.prompt_style_input.currentText()}' (index {self.prompt_style_input.currentIndex()})")
            self.logger.info(f"Custom input: visible={self.custom_style_input.isVisible()}, text='{self.custom_style_input.text()}'")
            self.logger.info(f"Final style value: '{self._get_current_style()}'")
    def _save_splitter_positions(self):
        """Save current splitter positions to config"""
        try:
            # Save main splitter (vertical: workspace and image/console)
            main_sizes = self.main_splitter.sizes()
            self.config.set('video_tab_main_splitter', main_sizes)

            # Save horizontal splitter (wizard, left panel, right panel)
            h_sizes = self.h_splitter.sizes()
            self.config.set('video_tab_h_splitter', h_sizes)

            # Save image/console splitter (vertical: image and console)
            image_console_sizes = self.image_console_splitter.sizes()
            self.config.set('video_tab_image_console_splitter', image_console_sizes)

            self.config.save()
        except Exception as e:
            self.logger.error(f"Failed to save splitter positions: {e}")

    def _save_column_widths(self):
        """Save current column widths to config"""
        try:
            if hasattr(self, 'scene_table'):
                header = self.scene_table.horizontalHeader()
                widths = [header.sectionSize(i) for i in range(self.scene_table.columnCount())]
                self.config.set('video_tab_column_widths', widths)
                self.config.save()
        except Exception as e:
            self.logger.error(f"Failed to save column widths: {e}")

    def _save_scrollbar_positions(self):
        """Save current scrollbar positions to config"""
        try:
            if hasattr(self, 'scene_table'):
                h_scrollbar = self.scene_table.horizontalScrollBar()
                v_scrollbar = self.scene_table.verticalScrollBar()
                positions = {
                    'horizontal': h_scrollbar.value() if h_scrollbar else 0,
                    'vertical': v_scrollbar.value() if v_scrollbar else 0
                }
                self.config.set('video_tab_scrollbar_positions', positions)
                self.config.save()
        except Exception as e:
            self.logger.error(f"Failed to save scrollbar positions: {e}")

    def _restore_splitter_positions(self):
        """Restore splitter positions from config"""
        try:
            # Restore main splitter
            main_sizes = self.config.get('video_tab_main_splitter')
            if main_sizes and len(main_sizes) == 2:
                self.main_splitter.setSizes(main_sizes)

            # Restore horizontal splitter
            h_sizes = self.config.get('video_tab_h_splitter')
            if h_sizes and len(h_sizes) == 3:
                self.h_splitter.setSizes(h_sizes)

            # Restore image/console splitter
            image_console_sizes = self.config.get('video_tab_image_console_splitter')
            if image_console_sizes and len(image_console_sizes) == 2:
                self.image_console_splitter.setSizes(image_console_sizes)

            # Restore workflow guide visibility
            wizard_hidden = self.config.get('video_tab_wizard_hidden', False)
            if wizard_hidden and self.wizard_toggle_btn_top.isChecked():
                # Button is checked (visible), but should be hidden
                self.wizard_toggle_btn_top.setChecked(False)
                self._toggle_wizard(False)
            elif not wizard_hidden and not self.wizard_toggle_btn_top.isChecked():
                # Button is unchecked (hidden), but should be visible
                self.wizard_toggle_btn_top.setChecked(True)
                self._toggle_wizard(True)

        except Exception as e:
            self.logger.error(f"Failed to restore splitter positions: {e}")

    def _restore_column_widths(self):
        """Restore column widths from config"""
        try:
            if hasattr(self, 'scene_table'):
                widths = self.config.get('video_tab_column_widths')
                if widths and len(widths) == self.scene_table.columnCount():
                    header = self.scene_table.horizontalHeader()
                    for i, width in enumerate(widths):
                        header.resizeSection(i, width)
        except Exception as e:
            self.logger.error(f"Failed to restore column widths: {e}")

    def _restore_scrollbar_positions(self):
        """Restore scrollbar positions from config"""
        try:
            if hasattr(self, 'scene_table'):
                positions = self.config.get('video_tab_scrollbar_positions')
                if positions:
                    h_scrollbar = self.scene_table.horizontalScrollBar()
                    v_scrollbar = self.scene_table.verticalScrollBar()
                    if h_scrollbar and 'horizontal' in positions:
                        h_scrollbar.setValue(positions['horizontal'])
                    if v_scrollbar and 'vertical' in positions:
                        v_scrollbar.setValue(positions['vertical'])
        except Exception as e:
            self.logger.error(f"Failed to restore scrollbar positions: {e}")

    def closeEvent(self, event):
        """Save state when widget is closed"""
        self._save_splitter_positions()
        self._save_column_widths()
        self._save_scrollbar_positions()
        # Save workflow guide visibility state
        self.config.set('video_tab_wizard_hidden', not self.wizard_toggle_btn_top.isChecked())
        self.config.save()
        super().closeEvent(event)
