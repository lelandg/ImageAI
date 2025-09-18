"""Main window for ImageAI GUI."""

import json
import logging
import webbrowser
from pathlib import Path
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QThread, Signal, QTimer
    from PySide6.QtGui import QPixmap, QAction
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QLabel, QTextEdit, QPushButton, QComboBox, QLineEdit,
        QFormLayout, QSizePolicy, QMessageBox, QFileDialog,
        QCheckBox, QTextBrowser, QListWidget, QListWidgetItem, QDialog, QSpinBox,
        QDoubleSpinBox, QGroupBox, QApplication, QSplitter, QScrollArea
    )
except ImportError:
    raise ImportError("PySide6 is required for GUI mode")

from core import (
    ConfigManager, APP_NAME, VERSION, DEFAULT_MODEL, sanitize_filename,
    scan_disk_history, images_output_dir, sidecar_path, write_image_sidecar,
    read_image_sidecar, auto_save_images, sanitize_stub_from_prompt,
    detect_image_extension, find_cached_demo, default_model_for_provider
)
from core.constants import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
from providers import get_provider, preload_provider, list_providers
from gui.dialogs import ExamplesDialog
# Defer video tab import to improve startup speed
# from gui.video.video_project_tab import VideoProjectTab
from gui.workers import GenWorker
from gui.image_crop_dialog import ImageCropDialog
from gui.find_dialog import FindDialog
from gui.prompt_generation_dialog import PromptGenerationDialog
from gui.prompt_question_dialog import PromptQuestionDialog
from gui.upscaling_widget import UpscalingSelector
try:
    from gui.model_browser import ModelBrowserDialog
except ImportError:
    ModelBrowserDialog = None
try:
    from gui.local_sd_widget import LocalSDWidget
except ImportError:
    LocalSDWidget = None
try:
    from gui.settings_widgets import (
        AspectRatioSelector, ResolutionSelector, QualitySelector,
        BatchSelector, AdvancedSettingsPanel, CostEstimator
    )
except ImportError:
    AspectRatioSelector = None
    ResolutionSelector = None
    QualitySelector = None
    BatchSelector = None
    AdvancedSettingsPanel = None
    CostEstimator = None


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        
        # Initialize provider
        self.current_provider = self.config.get("provider", "google")
        self.current_api_key = self.config.get_api_key(self.current_provider)
        self.current_model = DEFAULT_MODEL
        self.auto_copy_filename = self.config.get("auto_copy_filename", False)
        
        # Session state
        print("Scanning image history...")
        self.history_paths: List[Path] = scan_disk_history(project_only=True)
        print(f"Found {len(self.history_paths)} images in history")

        self.history = []  # Initialize empty history list
        self.current_prompt: str = ""
        self.gen_thread: Optional[QThread] = None
        self.gen_worker: Optional[GenWorker] = None
        self.current_image_data: Optional[bytes] = None
        self._last_template_context: Optional[dict] = None
        self._video_tab_loaded = False  # Track lazy loading of video tab
        self.upscaling_settings = {}  # Initialize upscaling settings

        # Load history from disk
        print("Loading image metadata...")
        self._load_history_from_disk()
        print(f"Loaded metadata for {len(self.history)} images")

        # Create UI first so we have status bar
        print("Creating user interface...")
        self._init_ui()
        self.status_bar.showMessage("Initializing application...")
        QApplication.processEvents()

        print("Setting up menus...")
        self._init_menu()

        # Preload providers for faster first use
        print(f"Preloading {self.current_provider} provider...")
        self.status_bar.showMessage(f"Loading {self.current_provider} provider...")
        QApplication.processEvents()

        auth_mode_value = self.config.get("auth_mode", "api-key")
        # Handle legacy/display values
        if auth_mode_value in ["api_key", "API Key"]:
            auth_mode_value = "api-key"
        elif auth_mode_value == "Google Cloud Account":
            auth_mode_value = "gcloud"

        provider_config = {
            "api_key": self.current_api_key,
            "auth_mode": auth_mode_value
        }
        preload_provider(self.current_provider, provider_config)
        print(f"{self.current_provider} provider loaded")

        # Check for LLM provider
        llm_provider = self.config.get("llm_provider", "None")
        if llm_provider and llm_provider != "None":
            print(f"LLM Provider configured: {llm_provider}")
            self.status_bar.showMessage(f"Loading LLM provider: {llm_provider}...")
            QApplication.processEvents()

        # Restore window geometry and UI state
        print("Restoring window state...")
        self.status_bar.showMessage("Restoring window state...")
        QApplication.processEvents()
        self._restore_geometry()
        self._restore_ui_state()

        print("Application ready!")
        self.status_bar.showMessage("Ready")
        QApplication.processEvents()
    

    def _on_show_all_images_toggled(self, checked: bool):
        """Handle toggle of show all images checkbox."""
        # Reload history with new filter
        self.history_paths = scan_disk_history(project_only=not checked)

        # Clear existing history data
        self.history = []

        # Load metadata for new set of images
        print(f"Loading metadata for {len(self.history_paths)} images...")
        for img_path in self.history_paths[:100]:  # Limit to first 100 for performance
            meta = read_image_sidecar(img_path)
            if meta:
                self.history.append({
                    'path': img_path,
                    'prompt': meta.get('prompt', ''),
                    'timestamp': meta.get('timestamp', ''),
                    'model': meta.get('model', ''),
                    'provider': meta.get('provider', ''),
                    'cost': meta.get('cost', 0.0),
                    'width': meta.get('width', 0),
                    'height': meta.get('height', 0)
                })
            elif checked:  # Only add non-project images if showing all
                # For non-project images, create minimal entry
                self.history.append({
                    'path': img_path,
                    'prompt': '',
                    'timestamp': datetime.fromtimestamp(img_path.stat().st_mtime).isoformat(),
                    'model': '',
                    'provider': '',
                    'cost': 0.0,
                    'width': 0,
                    'height': 0
                })

        print(f"Loaded metadata for {len(self.history)} images")

        # Refresh the history table
        if hasattr(self, 'history_table'):
            self._refresh_history_table()

    def _enable_original_toggle(self, original_path, cropped_path):
        """Enable toggle button for switching between original and cropped."""
        self.btn_toggle_original.setEnabled(True)
        self.btn_toggle_original.setVisible(True)
        self.btn_toggle_original.setText("Show Original")
        self._showing_original = False
        self._original_path = original_path
        self._cropped_path = cropped_path

    def _toggle_original_image(self):
        """Toggle between original and cropped image."""
        if not hasattr(self, '_showing_original') or not hasattr(self, '_original_path'):
            return

        try:
            if self._showing_original:
                # Switch to cropped
                with open(self._cropped_path, 'rb') as f:
                    image_data = f.read()
                self._display_image(image_data)
                self.current_image_data = image_data
                self.btn_toggle_original.setText("Show Original")
                self._showing_original = False
            else:
                # Switch to original
                with open(self._original_path, 'rb') as f:
                    image_data = f.read()
                self._display_image(image_data)
                self.current_image_data = image_data
                self.btn_toggle_original.setText("Show Cropped")
                self._showing_original = True
        except Exception as e:
            logger.error(f"Error toggling image: {e}")

    def _append_to_console(self, message: str, color: str = "#cccccc", is_separator: bool = False):
        """Append a message to the console with optional color and log it."""
        from PySide6.QtGui import QTextCursor

        # Log the message (skip separators)
        if not is_separator and message:
            # Determine log level based on color
            if color == "#ff6666":  # Red - Error
                logger.error(f"Console: {message}")
            elif color == "#ffaa00":  # Orange - Warning
                logger.warning(f"Console: {message}")
            elif color == "#00ff00":  # Green - Success/Info
                logger.info(f"Console: {message}")
            elif color == "#66ccff":  # Blue - Debug/Progress
                logger.debug(f"Console: {message}")
            else:  # Default
                logger.info(f"Console: {message}")

        if is_separator:
            # Add a horizontal separator
            cursor = self.output_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertHtml('<hr style="border: none; border-top: 1px solid #666; margin: 2px 0; padding: 0;">')

        # Format the message with color
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'

        # Append to console without extra spacing
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(formatted + '<br/>')

        # Auto-scroll to bottom
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_text.setTextCursor(cursor)

        # Don't auto-resize - let user control the console size

    def _auto_resize_console(self):
        """Deprecated - no longer auto-resize console."""
        pass  # Let user control console size via splitter

    def _load_history_from_disk(self):
        """Load history from disk into memory with enhanced metadata."""
        for path in self.history_paths:
            try:
                # Try to read sidecar file for metadata
                sidecar = read_image_sidecar(path)
                if sidecar:
                    self.history.append({
                        'path': path,
                        'prompt': sidecar.get('prompt', ''),
                        'timestamp': sidecar.get('timestamp', path.stat().st_mtime),
                        'model': sidecar.get('model', ''),
                        'provider': sidecar.get('provider', ''),
                        'width': sidecar.get('width', ''),
                        'height': sidecar.get('height', ''),
                        'num_images': sidecar.get('num_images', 1),
                        'quality': sidecar.get('quality', ''),
                        'style': sidecar.get('style', ''),
                        'cost': sidecar.get('cost', 0.0)
                    })
                else:
                    # No sidecar, just add path with basic info
                    self.history.append({
                        'path': path,
                        'prompt': path.stem.replace('_', ' '),
                        'timestamp': path.stat().st_mtime,
                        'model': '',
                        'provider': '',
                        'cost': 0.0
                    })
            except Exception:
                pass
    
    def _init_ui(self):
        """Initialize the user interface."""
        # Create status bar
        from PySide6.QtWidgets import QStatusBar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create tabs
        self.tab_generate = QWidget()
        self.tab_templates = QWidget()
        self.tab_settings = QWidget()
        self.tab_help = QWidget()
        self.tab_history = QWidget()
        
        # Create placeholder for video tab - will be loaded lazily
        self.tab_video = QWidget()  # Placeholder widget
        self._video_tab_loaded = False  # Track if real video tab is loaded

        self.tabs.addTab(self.tab_generate, "🎨 Image")
        self.tabs.addTab(self.tab_templates, "📝 Templates")
        self.tabs.addTab(self.tab_video, "🎬 Video")
        self.tabs.addTab(self.tab_settings, "⚙️ Settings")
        self.tabs.addTab(self.tab_help, "❓ Help")
        self.tabs.addTab(self.tab_history, "📜 History")  # Always add history tab
        
        self._init_generate_tab()
        self._init_templates_tab()
        self._init_settings_tab()
        self._init_help_tab()
        self._init_history_tab()  # Always init history tab
        
        # Connect tab change signal to handle help tab rendering
        self.tabs.currentChanged.connect(self._on_tab_changed)
    
    def _init_menu(self):
        """Initialize menu bar."""
        mb = self.menuBar()
        file_menu = mb.addMenu("File")
        
        # Project actions
        act_save_project = QAction("Save Project...", self)
        act_save_project.triggered.connect(self._save_project)
        file_menu.addAction(act_save_project)
        
        act_load_project = QAction("Load Project...", self)
        act_load_project.triggered.connect(self._load_project)
        file_menu.addAction(act_load_project)
        
        file_menu.addSeparator()
        
        act_save = QAction("Save Image As...", self)
        act_save.triggered.connect(self._save_image_as)
        file_menu.addAction(act_save)
        
        file_menu.addSeparator()
        
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)
        
        # Help menu
        help_menu = mb.addMenu("Help")
        
        act_show_logs = QAction("Show Log Location", self)
        act_show_logs.triggered.connect(self._show_log_location)
        help_menu.addAction(act_show_logs)
        
        act_report_error = QAction("How to Report Errors", self)
        act_report_error.triggered.connect(self._show_error_reporting)
        help_menu.addAction(act_report_error)
    
    def _init_generate_tab(self):
        """Initialize the Generate tab."""
        v = QVBoxLayout(self.tab_generate)
        v.setSpacing(2)
        v.setContentsMargins(5, 5, 5, 5)

        # LLM Provider and model selection at the very top
        llm_provider_layout = QHBoxLayout()

        # LLM Provider dropdown
        llm_provider_layout.addWidget(QLabel("LLM Provider:"))
        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.setMinimumWidth(150)
        self.llm_provider_combo.addItems(["None", "OpenAI", "Claude", "Gemini", "Ollama", "LM Studio"])
        self.llm_provider_combo.currentTextChanged.connect(self._on_llm_provider_changed)
        llm_provider_layout.addWidget(self.llm_provider_combo)

        # LLM Model dropdown
        llm_provider_layout.addWidget(QLabel("Model:"))
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setMinimumWidth(250)
        self.llm_model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.llm_model_combo.setEnabled(False)
        self.llm_model_combo.currentTextChanged.connect(self._on_llm_model_changed)
        llm_provider_layout.addWidget(self.llm_model_combo)
        llm_provider_layout.addStretch()
        v.addLayout(llm_provider_layout)

        # Image Provider and model selection
        provider_model_layout = QHBoxLayout()

        # Image Provider dropdown
        provider_model_layout.addWidget(QLabel("Image Provider:"))
        self.image_provider_combo = QComboBox()
        self.image_provider_combo.setMinimumWidth(150)
        # Get available providers with a defensive fallback
        try:
            available_providers = list_providers()
            if not available_providers:
                # Ensure we have at least core providers listed
                available_providers = ["google", "openai"]
        except Exception as e:
            # Avoid bubbling import-time errors (e.g., protobuf incompat)
            import logging as _logging
            _logging.getLogger(__name__).debug(f"Provider discovery failed: {e}")
            available_providers = ["google", "openai"]
        self.image_provider_combo.addItems(available_providers)
        if self.current_provider in available_providers:
            self.image_provider_combo.setCurrentText(self.current_provider)
        self.image_provider_combo.currentTextChanged.connect(self._on_image_provider_changed)
        provider_model_layout.addWidget(self.image_provider_combo)

        # Image Model dropdown
        provider_model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        # Set minimum width to ensure model names are fully visible
        self.model_combo.setMinimumWidth(350)
        # Adjust size policy to show full text
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._update_model_list()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        provider_model_layout.addWidget(self.model_combo)
        provider_model_layout.addStretch()
        v.addLayout(provider_model_layout)
        
        # Create vertical splitter for prompt and image
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(8)  # Make handle thicker and more visible
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e0e0e0, stop:0.5 #888888, stop:1 #e0e0e0);
                border: 1px solid #cccccc;
            }
            QSplitter::handle:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #a0a0ff, stop:0.5 #6060ff, stop:1 #a0a0ff);
            }
        """)
        
        # Top section: Prompt input (resizable via splitter)
        prompt_container = QWidget()
        prompt_layout = QVBoxLayout(prompt_container)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(2)
        
        # Prompt label with tips
        prompt_header_layout = QHBoxLayout()
        prompt_label = QLabel("Prompt:")
        prompt_header_layout.addWidget(prompt_label)

        # Add find tip
        find_tip = QLabel("(Ctrl+F to search)")
        find_tip.setStyleSheet("color: #888; font-size: 9pt;")
        prompt_header_layout.addWidget(find_tip)
        prompt_header_layout.addStretch()
        prompt_layout.addLayout(prompt_header_layout)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Describe what to generate... (Ctrl+Enter to generate)")
        self.prompt_edit.setAcceptRichText(False)
        # Ensure minimum height for 3 lines of text
        font_metrics = self.prompt_edit.fontMetrics()
        min_height = font_metrics.lineSpacing() * 3 + 10  # 3 lines + padding
        self.prompt_edit.setMinimumHeight(min_height)

        # Install event filter for Ctrl+Enter shortcut
        self.prompt_edit.installEventFilter(self)

        prompt_layout.addWidget(self.prompt_edit)

        # Add prompt container to splitter
        splitter.addWidget(prompt_container)
        
        # Bottom section: Everything else
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(5)

        # Single buttons row - below splitter, above Image Settings
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 5, 0, 5)
        buttons_layout.setSpacing(3)

        # All buttons in one row
        self.btn_examples = QPushButton("E&xamples")
        self.btn_examples.setToolTip("Browse example prompts (Alt+X)")
        buttons_layout.addWidget(self.btn_examples)

        self.btn_enhance_prompt = QPushButton("&Enhance")
        self.btn_enhance_prompt.setToolTip("Improve prompt with AI (Alt+E)")
        buttons_layout.addWidget(self.btn_enhance_prompt)

        self.btn_generate_prompts = QPushButton("Generate &Prompts")
        self.btn_generate_prompts.setToolTip("Generate multiple prompt variations (Alt+P)")
        buttons_layout.addWidget(self.btn_generate_prompts)

        self.btn_ask_about = QPushButton("&Ask")
        self.btn_ask_about.setToolTip("Ask questions about your prompt (Alt+A)")
        buttons_layout.addWidget(self.btn_ask_about)

        # Separator
        buttons_layout.addSpacing(10)

        self.btn_generate = QPushButton("&Generate")
        self.btn_generate.setToolTip("Generate image (Alt+G or Ctrl+Enter)")
        buttons_layout.addWidget(self.btn_generate)

        # Spacer
        buttons_layout.addStretch()

        # Toggle button for original/cropped (initially hidden)
        self.btn_toggle_original = QPushButton("Show Original")
        self.btn_toggle_original.setEnabled(False)
        self.btn_toggle_original.setVisible(False)
        self.btn_toggle_original.clicked.connect(self._toggle_original_image)
        buttons_layout.addWidget(self.btn_toggle_original)

        self.btn_save_image = QPushButton("&Save")
        self.btn_save_image.setToolTip("Save generated image (Alt+S or Ctrl+S)")
        self.btn_save_image.setEnabled(False)
        buttons_layout.addWidget(self.btn_save_image)

        self.btn_copy_image = QPushButton("&Copy")
        self.btn_copy_image.setToolTip("Copy image to clipboard (Alt+C)")
        self.btn_copy_image.setEnabled(False)
        buttons_layout.addWidget(self.btn_copy_image)

        bottom_layout.addWidget(buttons_container)
        
        # Image Settings - expandable like Advanced Settings
        # Toggle button
        self.image_settings_toggle = QPushButton("▶ Image Settings")
        self.image_settings_toggle.setCheckable(True)
        self.image_settings_toggle.clicked.connect(self._toggle_image_settings)
        self.image_settings_toggle.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                border: none;
                background: transparent;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
            }
        """)
        bottom_layout.addWidget(self.image_settings_toggle)
        
        # Container for image settings (initially hidden)
        self.image_settings_container = QWidget()
        self.image_settings_container.setVisible(False)
        image_settings_layout = QVBoxLayout(self.image_settings_container)
        image_settings_layout.setSpacing(5)
        image_settings_layout.setContentsMargins(10, 0, 0, 0)  # Indent for hierarchy
        
        # Aspect Ratio Selector
        if AspectRatioSelector:
            aspect_label = QLabel("Aspect Ratio:")
            aspect_label.setMaximumHeight(20)
            image_settings_layout.addWidget(aspect_label)
            
            self.aspect_selector = AspectRatioSelector()
            self.aspect_selector.ratioChanged.connect(self._on_aspect_ratio_changed)
            image_settings_layout.addWidget(self.aspect_selector)
            
            # Aspect ratios are now supported by all providers including Google Gemini
            self.aspect_selector.setEnabled(True)
            self.aspect_selector.setToolTip("Select aspect ratio for your image")
        else:
            self.aspect_selector = None
        
        # Resolution and Quality
        settings_form = QFormLayout()
        settings_form.setVerticalSpacing(5)
        
        if ResolutionSelector:
            self.resolution_selector = ResolutionSelector(self.current_provider)
            self.resolution_selector.resolutionChanged.connect(self._on_resolution_changed)
            # Connect resolution selector to aspect ratio changes
            if hasattr(self, 'aspect_selector') and self.aspect_selector:
                self.aspect_selector.ratioChanged.connect(self.resolution_selector.update_aspect_ratio)
                self.resolution_selector.modeChanged.connect(self._on_resolution_mode_changed)
                # Initialize resolution selector with current aspect ratio
                self.resolution_selector.update_aspect_ratio(self.aspect_selector.get_ratio())

                # Restore saved aspect ratio if available
                saved_aspect = self.config.config.get('last_aspect_ratio')
                if saved_aspect:
                    self.aspect_selector.set_ratio(saved_aspect)

                # Restore saved resolution dimensions
                saved_width = self.config.config.get('last_resolution_width')
                if saved_width:
                    self.resolution_selector._last_edited = "width"
                    self.resolution_selector.width_spin.setValue(saved_width)
                    # Height will be calculated automatically from aspect ratio
            # Wrap selector with a button for social sizes
            from PySide6.QtWidgets import QWidget as _W, QHBoxLayout as _HB
            res_container = _W()
            res_layout = _HB(res_container)
            res_layout.setContentsMargins(0, 0, 0, 0)
            res_layout.setSpacing(6)
            res_layout.addWidget(self.resolution_selector)
            self.btn_social_sizes = QPushButton("Social Sizes…")
            self.btn_social_sizes.setToolTip("Browse common social media sizes and apply")
            self.btn_social_sizes.clicked.connect(self._open_social_sizes_dialog)
            res_layout.addWidget(self.btn_social_sizes)
            res_layout.addStretch(1)
            settings_form.addRow("Resolution:", res_container)
        else:
            # Fallback to old resolution combo
            self.resolution_selector = None
            self.resolution_combo = QComboBox()
            self.resolution_combo.addItems([
                "Auto (based on model)",
                "512x512 (SD 1.x/2.x)",
                "768x768 (SD 1.x/2.x HQ)",
                "1024x1024 (SDXL)"
            ])
            self.resolution_combo.setCurrentIndex(0)
            settings_form.addRow("Resolution:", self.resolution_combo)
        
        if QualitySelector:
            self.quality_selector = QualitySelector(self.current_provider)
            self.quality_selector.settingsChanged.connect(self._on_quality_settings_changed)
            settings_form.addRow(self.quality_selector)
        else:
            self.quality_selector = None
        
        if BatchSelector:
            self.batch_selector = BatchSelector()
            self.batch_selector.batchChanged.connect(self._update_cost_estimate)
            settings_form.addRow("Batch:", self.batch_selector)
        else:
            self.batch_selector = None
        
        image_settings_layout.addLayout(settings_form)

        # Add upscaling selector (initially hidden)
        self.upscaling_selector = UpscalingSelector()
        self.upscaling_selector.upscalingChanged.connect(self._on_upscaling_changed)
        # Check availability
        if self.config:
            realesrgan_available = self.upscaling_selector.check_realesrgan_availability()
            stability_available = self.upscaling_selector.check_stability_api_availability(self.config)
            self.upscaling_selector.set_enabled_methods(
                lanczos=True,
                realesrgan=realesrgan_available,
                stability=stability_available
            )
            # Load saved upscaling settings
            saved_upscaling = self.config.config.get('upscaling_settings')
            if saved_upscaling:
                self.upscaling_selector.set_settings(saved_upscaling)
                self.upscaling_settings = saved_upscaling
        image_settings_layout.addWidget(self.upscaling_selector)

        # Add reference image section
        ref_image_group = QGroupBox("Reference Image")
        ref_image_layout = QVBoxLayout()
        ref_image_layout.setSpacing(5)

        # Horizontal layout for reference image controls
        ref_controls_layout = QHBoxLayout()

        # Reference image button
        self.btn_select_ref_image = QPushButton("Select Reference Image...")
        self.btn_select_ref_image.setToolTip("Choose a starting image for generation (Google Gemini only)")
        self.btn_select_ref_image.clicked.connect(self._select_reference_image)
        ref_controls_layout.addWidget(self.btn_select_ref_image)

        # Enable/disable checkbox
        self.ref_image_enabled = QCheckBox("Use reference")
        self.ref_image_enabled.setChecked(False)
        self.ref_image_enabled.setEnabled(False)  # Disabled until image selected
        self.ref_image_enabled.toggled.connect(self._on_ref_image_toggled)
        ref_controls_layout.addWidget(self.ref_image_enabled)

        # Clear button
        self.btn_clear_ref_image = QPushButton("Clear")
        self.btn_clear_ref_image.setEnabled(False)
        self.btn_clear_ref_image.clicked.connect(self._clear_reference_image)
        ref_controls_layout.addWidget(self.btn_clear_ref_image)

        ref_controls_layout.addStretch()
        ref_image_layout.addLayout(ref_controls_layout)

        # Container for image preview and controls
        ref_preview_container = QHBoxLayout()

        # Reference image preview (initially hidden)
        self.ref_image_preview = QLabel()
        self.ref_image_preview.setAlignment(Qt.AlignCenter)
        self.ref_image_preview.setMaximumHeight(150)
        self.ref_image_preview.setMaximumWidth(200)
        self.ref_image_preview.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        self.ref_image_preview.setScaledContents(False)
        self.ref_image_preview.setVisible(False)
        ref_preview_container.addWidget(self.ref_image_preview)

        # Reference image options (initially hidden)
        self.ref_options_widget = QWidget()
        self.ref_options_widget.setVisible(False)
        ref_options_layout = QVBoxLayout(self.ref_options_widget)
        ref_options_layout.setSpacing(3)

        # Placement style dropdown
        style_layout = QHBoxLayout()
        style_label = QLabel("Style:")
        style_label.setMinimumWidth(60)
        style_layout.addWidget(style_label)

        self.ref_style_combo = QComboBox()
        self.ref_style_combo.addItems([
            "Natural blend",
            "In center",
            "Blurred edges",
            "In circle",
            "In frame",
            "Seamless merge",
            "As background",
            "As overlay",
            "Split screen"
        ])
        self.ref_style_combo.currentTextChanged.connect(self._on_ref_style_changed)
        style_layout.addWidget(self.ref_style_combo)
        ref_options_layout.addLayout(style_layout)

        # Position dropdown
        position_layout = QHBoxLayout()
        position_label = QLabel("Position:")
        position_label.setMinimumWidth(60)
        position_layout.addWidget(position_label)

        self.ref_position_combo = QComboBox()
        self.ref_position_combo.addItems([
            "Auto",
            "Left",
            "Center",
            "Right",
            "Top",
            "Bottom",
            "Top-left",
            "Top-right",
            "Bottom-left",
            "Bottom-right"
        ])
        self.ref_position_combo.currentTextChanged.connect(self._on_ref_position_changed)
        position_layout.addWidget(self.ref_position_combo)
        ref_options_layout.addLayout(position_layout)

        # Tips label
        tips_label = QLabel("Tips: Gemini understands natural language\ninstructions about your reference image.")
        tips_label.setStyleSheet("color: #666; font-size: 9pt; padding: 5px 0;")
        tips_label.setWordWrap(True)
        ref_options_layout.addWidget(tips_label)

        # Auto-insert preview
        self.ref_instruction_label = QLabel("Will insert: [nothing]")
        self.ref_instruction_label.setStyleSheet("color: #0066cc; font-size: 9pt; padding: 5px; background: #f0f8ff; border: 1px solid #cce0ff; border-radius: 3px;")
        self.ref_instruction_label.setWordWrap(True)
        ref_options_layout.addWidget(self.ref_instruction_label)

        ref_preview_container.addWidget(self.ref_options_widget)
        ref_preview_container.addStretch()
        ref_image_layout.addLayout(ref_preview_container)

        ref_image_group.setLayout(ref_image_layout)
        image_settings_layout.addWidget(ref_image_group)

        # Store reference image data
        self.reference_image_path = None
        self.reference_image_data = None

        bottom_layout.addWidget(self.image_settings_container)
        
        # Advanced Settings (collapsible)
        if AdvancedSettingsPanel:
            self.advanced_panel = AdvancedSettingsPanel(self.current_provider)
            self.advanced_panel.settingsChanged.connect(self._on_advanced_settings_changed)
            bottom_layout.addWidget(self.advanced_panel)
        else:
            # Fallback to old advanced settings
            advanced_group = QGroupBox("Advanced Settings")
            advanced_layout = QFormLayout()
            
            # Steps spinner (for Local SD)
            self.steps_spin = QSpinBox()
            self.steps_spin.setRange(1, 50)
            self.steps_spin.setValue(20)
            self.steps_spin.setToolTip("Number of inference steps (1-4 for Turbo models, 20-50 for regular)")
            advanced_layout.addRow("Steps:", self.steps_spin)
            
            # Guidance scale
            self.guidance_spin = QDoubleSpinBox()
            self.guidance_spin.setRange(0.0, 20.0)
            self.guidance_spin.setSingleStep(0.5)
            self.guidance_spin.setValue(7.5)
            self.guidance_spin.setToolTip("Guidance scale (0.0 for Turbo models, 7-8 for regular)")
            advanced_layout.addRow("Guidance:", self.guidance_spin)
            
            advanced_group.setLayout(advanced_layout)
            bottom_layout.addWidget(advanced_group)
            self.advanced_group = advanced_group
            self.advanced_panel = None
        
        # Update visibility based on provider
        self._update_advanced_visibility()
        
        # Status - compact
        self.status_label = QLabel("Ready.")
        self.status_label.setMaximumHeight(20)
        bottom_layout.addWidget(self.status_label)
        
        # Create a vertical splitter for image and status console
        image_console_splitter = QSplitter(Qt.Vertical)

        # Output image
        self.output_image_label = QLabel()
        self.output_image_label.setAlignment(Qt.AlignCenter)
        self.output_image_label.setMinimumHeight(200)
        self.output_image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output_image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        self.output_image_label.setScaledContents(False)  # We handle scaling manually
        image_console_splitter.addWidget(self.output_image_label)

        # Status console container
        console_container = QWidget()
        console_layout = QVBoxLayout(console_container)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)  # No spacing between header and console

        # Minimal console header label
        console_header = QLabel("Status Console")
        console_header.setStyleSheet("color: #666; font-size: 9pt; padding: 0px; margin: 0px;")
        console_header.setMaximumHeight(16)
        console_layout.addWidget(console_header)

        # Status console - styled like a terminal
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        # Set fixed initial height, user can resize via splitter
        self.output_text.setMinimumHeight(50)  # Minimum height to prevent collapse
        self.output_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Terminal-like styling - remove paragraph spacing
        self.output_text.setStyleSheet("""
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
        # Set document margins to reduce spacing between lines
        doc = self.output_text.document()
        doc.setDocumentMargin(0)
        console_layout.addWidget(self.output_text)
        # Don't auto-resize - let user control size via splitter

        image_console_splitter.addWidget(console_container)

        # Set initial splitter sizes (large image, small fixed console)
        image_console_splitter.setSizes([500, 100])  # Fixed initial console height
        image_console_splitter.setStretchFactor(0, 3)  # Image gets more stretch
        image_console_splitter.setStretchFactor(1, 1)  # Console can grow when resizing

        bottom_layout.addWidget(image_console_splitter, 1)
        
        # Add bottom widget to splitter
        splitter.addWidget(bottom_widget)
        
        # Set initial splitter sizes (small prompt, large image area)
        splitter.setSizes([100, 600])  # 100px for prompt, 600px for rest
        splitter.setStretchFactor(0, 0)  # Don't stretch prompt section
        splitter.setStretchFactor(1, 1)  # Stretch image section
        # Set minimum sizes to prevent prompt from disappearing
        font_metrics = self.prompt_edit.fontMetrics()
        min_prompt_height = font_metrics.lineSpacing() * 3 + 35  # 3 lines + label + padding
        splitter.setChildrenCollapsible(False)  # Prevent sections from collapsing
        prompt_container.setMinimumHeight(min_prompt_height)
        bottom_widget.setMinimumHeight(200)  # Minimum for image area
        
        # Add splitter to main layout
        v.addWidget(splitter)
        
        # Connect signals
        self.btn_examples.clicked.connect(self._open_examples)
        self.btn_enhance_prompt.clicked.connect(self._enhance_prompt)
        self.btn_generate_prompts.clicked.connect(self._open_prompt_generator)
        self.btn_ask_about.clicked.connect(self._open_prompt_question)
        self.btn_generate.clicked.connect(self._generate)

        # Add keyboard shortcuts for common actions
        from PySide6.QtGui import QShortcut, QKeySequence

        # Ctrl+Enter always triggers generate
        shortcut_ctrl_enter = QShortcut(QKeySequence("Ctrl+Return"), self.tab_generate)
        shortcut_ctrl_enter.activated.connect(lambda: self._generate() if self.btn_generate.isEnabled() else None)

        # Also support Cmd+Enter on macOS
        shortcut_cmd_enter = QShortcut(QKeySequence("Meta+Return"), self.tab_generate)
        shortcut_cmd_enter.activated.connect(lambda: self._generate() if self.btn_generate.isEnabled() else None)

        # Ctrl+S to save image
        shortcut_save = QShortcut(QKeySequence.StandardKey.Save, self.tab_generate)
        shortcut_save.activated.connect(lambda: self._save_image_as() if self.btn_save_image.isEnabled() else None)

        # Ctrl+Shift+C to copy image
        shortcut_copy = QShortcut(QKeySequence("Ctrl+Shift+C"), self.tab_generate)
        shortcut_copy.activated.connect(lambda: self._copy_image_to_clipboard() if self.btn_copy_image.isEnabled() else None)

        # F1 for help
        shortcut_help = QShortcut(QKeySequence.StandardKey.HelpContents, self)
        shortcut_help.activated.connect(lambda: self.tabs.setCurrentWidget(self.tab_help))

        # Load reference image from config if available
        self._load_reference_image_from_config()

        # Check provider support for reference images
        if hasattr(self, 'btn_select_ref_image'):
            is_google = self.current_provider == "google"
            self.btn_select_ref_image.setEnabled(is_google)
            if is_google:
                self.btn_select_ref_image.setToolTip("Choose a starting image for generation (Google Gemini)")
            else:
                self.btn_select_ref_image.setToolTip(f"Reference images not supported by {self.current_provider} provider")

    def _open_social_sizes_dialog(self):
        """Open the Social Media Image Sizes dialog and apply selection."""
        try:
            from gui.social_sizes_tree_dialog import SocialSizesTreeDialog
        except Exception as e:
            from gui.dialog_utils import show_error
            show_error(self, APP_NAME, f"Unable to open sizes dialog: {e}", exception=e)
            return
        try:
            dlg = SocialSizesTreeDialog(self)
            from PySide6.QtWidgets import QDialog
            if dlg.exec() == QDialog.Accepted:
                res = dlg.selected_resolution()
                if res and hasattr(self, 'resolution_selector') and self.resolution_selector:
                    # Switch to explicit resolution mode and set the value
                    self.resolution_selector.set_mode_resolution()
                    # If preset list does not contain this size, temporarily add it
                    if hasattr(self.resolution_selector, 'set_resolution'):
                        self.resolution_selector.set_resolution(res)
                    # Store as current resolution for persistence
                    self.current_resolution = res
        except Exception as e:
            from gui.dialog_utils import show_error
            show_error(self, APP_NAME, f"Sizes dialog error: {e}", exception=e)
        self.btn_save_image.clicked.connect(self._save_image_as)
        self.btn_copy_image.clicked.connect(self._copy_image_to_clipboard)
    
    def _init_settings_tab(self):
        """Initialize the Settings tab."""
        # Create scroll area for settings
        scroll = QScrollArea(self.tab_settings)
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget(scroll)
        scroll_layout = QVBoxLayout(scroll_widget)

        # Main settings layout
        v = scroll_layout

        # === IMAGE PROVIDERS SECTION ===
        providers_group = QGroupBox("Image Generation Providers")
        providers_layout = QVBoxLayout(providers_group)

        # Current provider selection
        provider_form = QFormLayout()
        self.provider_combo = QComboBox()
        # Get available providers dynamically, with safe fallback
        try:
            available_providers = list_providers()
            if not available_providers:
                available_providers = ["google", "openai"]
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).debug(f"Provider discovery failed (settings tab): {e}")
            available_providers = ["google", "openai"]
        self.provider_combo.addItems(available_providers)
        if self.current_provider in available_providers:
            self.provider_combo.setCurrentText(self.current_provider)
        elif available_providers:
            self.current_provider = available_providers[0]
            self.provider_combo.setCurrentText(self.current_provider)
            # Save the fallback provider so it persists
            self.config.set("provider", self.current_provider)
            self.config.save()
        provider_form.addRow("Active Provider:", self.provider_combo)
        providers_layout.addLayout(provider_form)

        # === API KEYS SECTION (All providers shown) ===
        api_keys_group = QGroupBox("API Keys")
        api_keys_layout = QFormLayout(api_keys_group)

        # Google API Key
        self.google_key_edit = QLineEdit(self.tab_settings)
        self.google_key_edit.setEchoMode(QLineEdit.Password)
        self.google_key_edit.setPlaceholderText("Enter Google API key...")
        # Try multiple locations for backward compatibility
        google_api_key = (self.config.get("google_api_key", "") or
                         self.config.get("api_key", "") or  # Old format
                         self.config.get_api_key("google"))
        if google_api_key:
            self.google_key_edit.setText(google_api_key)
        api_keys_layout.addRow("Google:", self.google_key_edit)

        # OpenAI API Key
        self.openai_key_edit = QLineEdit(self.tab_settings)
        self.openai_key_edit.setEchoMode(QLineEdit.Password)
        self.openai_key_edit.setPlaceholderText("Enter OpenAI API key...")
        # Try multiple locations for backward compatibility
        openai_api_key = (self.config.get("openai_api_key", "") or
                         self.config.get_api_key("openai"))
        if openai_api_key:
            self.openai_key_edit.setText(openai_api_key)
        api_keys_layout.addRow("OpenAI:", self.openai_key_edit)

        # Stability API Key
        self.stability_key_edit = QLineEdit(self.tab_settings)
        self.stability_key_edit.setEchoMode(QLineEdit.Password)
        self.stability_key_edit.setPlaceholderText("Enter Stability API key...")
        # Try multiple locations for backward compatibility
        stability_api_key = (self.config.get("stability_api_key", "") or
                            self.config.get_api_key("stability"))
        if stability_api_key:
            self.stability_key_edit.setText(stability_api_key)
        api_keys_layout.addRow("Stability:", self.stability_key_edit)

        # Anthropic API Key (for LLM)
        self.anthropic_key_edit = QLineEdit(self.tab_settings)
        self.anthropic_key_edit.setEchoMode(QLineEdit.Password)
        self.anthropic_key_edit.setPlaceholderText("Enter Anthropic API key (for Claude LLM)...")
        anthropic_api_key = self.config.get("anthropic_api_key", "")
        if anthropic_api_key:
            self.anthropic_key_edit.setText(anthropic_api_key)
        api_keys_layout.addRow("Anthropic:", self.anthropic_key_edit)

        providers_layout.addWidget(api_keys_group)

        # API Key buttons
        api_buttons = QHBoxLayout()
        self.btn_get_key = QPushButton("Get API &Keys")
        self.btn_get_key.setToolTip("Open provider documentation for API keys")
        self.btn_save_test = QPushButton("&Save && Test")
        self.btn_save_test.setToolTip("Save all API keys and test current provider")
        api_buttons.addWidget(self.btn_get_key)
        api_buttons.addStretch(1)
        api_buttons.addWidget(self.btn_save_test)
        providers_layout.addLayout(api_buttons)

        v.addWidget(providers_group)

        # Keep old API key edit reference for compatibility
        self.api_key_edit = self.google_key_edit  # Default to Google for backward compat

        # === GOOGLE CLOUD AUTH SECTION ===
        gcloud_group = QGroupBox("Google Cloud Authentication (Alternative)")
        gcloud_layout = QVBoxLayout(gcloud_group)

        form = QFormLayout()
        # Auth Mode selection (for Google provider)
        self.auth_mode_combo = QComboBox()
        self.auth_mode_combo.addItems(["API Key", "Google Cloud Account"])
        # Map internal auth mode to display text
        auth_mode_internal = self.config.get("auth_mode", "api-key")
        # Handle legacy values
        if auth_mode_internal in ["api_key", "API Key"]:
            auth_mode_internal = "api-key"
        elif auth_mode_internal == "Google Cloud Account":
            auth_mode_internal = "gcloud"
        auth_mode_display = "Google Cloud Account" if auth_mode_internal == "gcloud" else "API Key"
        self.auth_mode_combo.setCurrentText(auth_mode_display)
        form.addRow("Auth Mode:", self.auth_mode_combo)
        
        # Google Cloud Project ID (shown for Google Cloud Account mode)
        self.project_id_edit = QLineEdit(self.tab_settings)
        self.project_id_edit.setPlaceholderText("Enter project ID or leave blank to detect")
        project_id = self.config.get("gcloud_project_id", "")
        if project_id:
            self.project_id_edit.setText(project_id)
        form.addRow("Project ID:", self.project_id_edit)
        
        # Status field
        self.gcloud_status_label = QLabel("Not checked")
        form.addRow("Status:", self.gcloud_status_label)

        gcloud_layout.addLayout(form)
        
        # Google Cloud Setup Help
        self.gcloud_help_widget = QWidget(self.tab_settings)
        gcloud_help_layout = QVBoxLayout(self.gcloud_help_widget)
        gcloud_help_layout.setContentsMargins(0, 10, 0, 0)
        
        quick_setup = QLabel("""<b>Quick Setup:</b>
1. Install Google Cloud CLI
2. Run: <code>gcloud auth application-default login</code>
3. Click 'Check Status' below""")
        quick_setup.setWordWrap(True)
        quick_setup.setStyleSheet("QLabel { padding: 10px; background-color: #f5f5f5; }")
        gcloud_help_layout.addWidget(quick_setup)
        
        # Google Cloud buttons
        gcloud_buttons = QHBoxLayout()
        self.btn_authenticate = QPushButton("&Authenticate")  # Alt+A
        self.btn_authenticate.setToolTip("Run: gcloud auth application-default login (Alt+A)")
        self.btn_check_status = QPushButton("Check &Status")  # Alt+S
        self.btn_get_gcloud = QPushButton("Get &gcloud CLI")  # Alt+G
        self.btn_cloud_console = QPushButton("Cloud C&onsole")  # Alt+O
        
        gcloud_buttons.addWidget(self.btn_authenticate)
        gcloud_buttons.addWidget(self.btn_check_status)
        gcloud_buttons.addWidget(self.btn_get_gcloud)
        gcloud_buttons.addWidget(self.btn_cloud_console)
        gcloud_help_layout.addLayout(gcloud_buttons)

        gcloud_layout.addWidget(self.gcloud_help_widget)
        v.addWidget(gcloud_group)
        
        # Create placeholder for backward compatibility
        self.api_key_widget = QWidget(self.tab_settings)
        self.api_key_widget.setVisible(False)
        
        # === GENERAL OPTIONS ===
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        # LLM logging option
        self.chk_log_llm = QCheckBox("Log LLM prompts and responses (for debugging)")
        self.chk_log_llm.setChecked(self.config.get("log_llm_interactions", False))
        self.chk_log_llm.toggled.connect(lambda checked: self.config.set("log_llm_interactions", checked))
        options_layout.addWidget(self.chk_log_llm)

        # Auto-copy filename option
        self.chk_auto_copy = QCheckBox("Auto-copy saved filename to clipboard")
        self.chk_auto_copy.setChecked(self.auto_copy_filename)
        options_layout.addWidget(self.chk_auto_copy)

        # Config location info
        config_path = str(self.config.config_path)
        config_label = QLabel(f"Config stored at: {config_path}")
        config_label.setWordWrap(True)
        config_label.setStyleSheet("color: gray; font-size: 10pt;")
        options_layout.addWidget(config_label)

        v.addWidget(options_group)

        # Create placeholder for backward compatibility
        self.config_location_widget = QWidget(self.tab_settings)
        self.config_location_widget.setVisible(False)
        
        # Update visibility based on auth mode
        self._update_auth_visibility()
        
        # Check and display cached auth status if in Google Cloud mode
        if self.current_provider == "google" and auth_mode_display == "Google Cloud Account":
            if self.config.get("gcloud_auth_validated", False):
                project_id = self.config.get("gcloud_project_id", "")
                if project_id:
                    self.gcloud_status_label.setText(f"✓ Authenticated (Project: {project_id}) [cached]")
                    self.project_id_edit.setText(project_id)
                else:
                    self.gcloud_status_label.setText("✓ Authenticated [cached]")
                    self.project_id_edit.setText("")
                self.gcloud_status_label.setStyleSheet("color: green;")
        
        # Local SD model management widget
        if LocalSDWidget:
            local_sd_group = QGroupBox("Local Stable Diffusion")
            local_sd_layout = QVBoxLayout(local_sd_group)
            self.local_sd_widget = LocalSDWidget()
            self.local_sd_widget.models_changed.connect(self._update_model_list)
            local_sd_layout.addWidget(self.local_sd_widget)
            v.addWidget(local_sd_group)
            # Show/hide based on provider
            local_sd_group.setVisible(self.current_provider == "local_sd")
        else:
            self.local_sd_widget = None

        v.addStretch(1)

        # Set scroll widget
        scroll.setWidget(scroll_widget)

        # Add scroll area to tab
        tab_layout = QVBoxLayout(self.tab_settings)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        
        # Connect signals
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.auth_mode_combo.currentTextChanged.connect(self._on_auth_mode_changed)
        self.btn_get_key.clicked.connect(self._open_api_key_page)
        self.btn_save_test.clicked.connect(self._save_and_test)
        self.chk_auto_copy.toggled.connect(self._toggle_auto_copy)
        
        # Google Cloud buttons
        self.btn_authenticate.clicked.connect(self._authenticate_gcloud)
        self.btn_check_status.clicked.connect(self._check_gcloud_status)
        self.btn_get_gcloud.clicked.connect(self._open_gcloud_cli_page)
        self.btn_cloud_console.clicked.connect(self._open_cloud_console)
        
        # Connect project ID edit
        self.project_id_edit.editingFinished.connect(self._on_project_id_changed)
    
    def _init_help_tab(self):
        """Initialize the Help tab."""
        v = QVBoxLayout(self.tab_help)
        v.setSpacing(0)
        v.setContentsMargins(2, 2, 2, 2)
        
        # Try to use QWebEngineView for better emoji support, fallback to QTextBrowser
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebEngineCore import QWebEnginePage
            from PySide6.QtCore import QUrl
            import webbrowser
            
            class CustomWebPage(QWebEnginePage):
                """Custom page to handle external links and local markdown files."""
                def __init__(self, parent=None, main_window=None):
                    super().__init__(parent)
                    self.main_window = main_window

                def acceptNavigationRequest(self, url, nav_type, is_main_frame):
                    from PySide6.QtWebEngineCore import QWebEnginePage
                    from PySide6.QtCore import QTimer

                    # Open external links in system browser
                    if url.scheme() in ('http', 'https', 'ftp'):
                        webbrowser.open(url.toString())
                        return False

                    # Handle local markdown file links (like CHANGELOG.md and README.md)
                    url_str = url.toString()

                    # Check if this is a markdown file URL - only process link clicks
                    if ((url_str.endswith('.md') or 'README.md' in url_str or 'CHANGELOG.md' in url_str)
                        and not url_str.startswith('#')
                        and nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked):

                        from pathlib import Path

                        # Parse the file path from URL
                        if url_str.startswith('file:///'):
                            file_path = url_str.replace('file:///', '')
                        else:
                            file_path = url_str

                        # Get the project root directory
                        project_root = Path(__file__).parent.parent

                        # Resolve relative to project root
                        full_path = project_root / file_path

                        if full_path.exists() and full_path.suffix.lower() == '.md':
                            try:
                                # Load the markdown file content
                                if 'README' in file_path.upper():
                                    content = self.main_window._load_readme_content(replace_emojis=False) if self.main_window else full_path.read_text(encoding='utf-8')
                                else:
                                    content = full_path.read_text(encoding='utf-8')

                                # Convert to HTML
                                if self.main_window:
                                    html = self.main_window._markdown_to_html_with_anchors(content, use_webengine=True)
                                    browser = self.parent()

                                    # Load the formatted HTML immediately
                                    browser.setHtml(html, url)

                                    # Trigger scroll after content loads
                                    QTimer.singleShot(200, lambda: browser.page().runJavaScript("""
                                        window.scrollTo(0, 0);
                                        setTimeout(function() {
                                            window.scrollBy(0, 1);
                                            window.scrollBy(0, -1);
                                        }, 50);
                                    """))

                                # Prevent default navigation
                                return False
                            except Exception as e:
                                print(f"Error loading markdown file: {e}")
                                return True

                    return super().acceptNavigationRequest(url, nav_type, is_main_frame)
            
            # Create web view for help with full emoji support
            self.help_browser = QWebEngineView()
            custom_page = CustomWebPage(self.help_browser, main_window=self)
            self.help_browser.setPage(custom_page)

            
            # Create navigation toolbar container widget with fixed height
            nav_widget = QWidget()
            nav_widget.setMaximumHeight(30)
            nav_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            
            nav_layout = QHBoxLayout(nav_widget)
            nav_layout.setSpacing(2)
            nav_layout.setContentsMargins(0, 0, 0, 0)
            
            # Back button
            self.btn_help_back = QPushButton("◀ Back")
            self.btn_help_back.clicked.connect(self.help_browser.back)
            self.btn_help_back.setToolTip("Go back (Alt+Left, Backspace)")
            nav_layout.addWidget(self.btn_help_back)

            # Forward button
            self.btn_help_forward = QPushButton("Forward ▶")
            self.btn_help_forward.clicked.connect(self.help_browser.forward)
            self.btn_help_forward.setToolTip("Go forward (Alt+Right)")
            nav_layout.addWidget(self.btn_help_forward)

            # Add keyboard shortcuts for navigation when help tab is active
            from PySide6.QtGui import QShortcut, QKeySequence
            from PySide6.QtCore import Qt

            # Alt+Left for back (only when help tab is active)
            shortcut_back = QShortcut(QKeySequence("Alt+Left"), self.tab_help)
            shortcut_back.activated.connect(self.help_browser.back)

            # Alt+Right for forward (only when help tab is active)
            shortcut_forward = QShortcut(QKeySequence("Alt+Right"), self.tab_help)
            shortcut_forward.activated.connect(self.help_browser.forward)

            # Backspace for back as well
            shortcut_backspace = QShortcut(QKeySequence(Qt.Key_Backspace), self.tab_help)
            shortcut_backspace.activated.connect(self.help_browser.back)
            
            # Home button
            self.btn_help_home = QPushButton("⌂ Home")
            self.btn_help_home.clicked.connect(lambda: self.help_browser.page().runJavaScript(
                "window.scrollTo(0, 0);"))
            self.btn_help_home.setToolTip("Go to top (Ctrl+Home)")
            nav_layout.addWidget(self.btn_help_home)

            # Report Problem button
            self.btn_report_problem = QPushButton("🐛 Report Problem")
            self.btn_report_problem.clicked.connect(lambda: webbrowser.open("https://github.com/lelandg/ImageAI/issues"))
            self.btn_report_problem.setToolTip("Report an issue on GitHub")
            nav_layout.addWidget(self.btn_report_problem)

            nav_layout.addStretch()
            
            # Search controls - compact layout
            search_label = QLabel("Search:")
            nav_layout.addWidget(search_label)
            
            self.help_search_input = QLineEdit()
            self.help_search_input.setPlaceholderText("Find in docs...")
            self.help_search_input.setMaximumWidth(200)
            self.help_search_input.returnPressed.connect(self._search_help_webengine)
            nav_layout.addWidget(self.help_search_input)
            
            self.btn_help_search_prev = QPushButton("◀")
            self.btn_help_search_prev.setToolTip("Previous match (Shift+F3)")
            self.btn_help_search_prev.clicked.connect(lambda: self._search_help_webengine(backward=True))
            self.btn_help_search_prev.setMaximumWidth(25)
            nav_layout.addWidget(self.btn_help_search_prev)
            
            self.btn_help_search_next = QPushButton("▶")
            self.btn_help_search_next.setToolTip("Next match (F3)")
            self.btn_help_search_next.clicked.connect(self._search_help_webengine)
            self.btn_help_search_next.setMaximumWidth(25)
            nav_layout.addWidget(self.btn_help_search_next)
            
            self.help_search_results = QLabel("")
            self.help_search_results.setMinimumWidth(80)
            self.help_search_results.setStyleSheet("color: #666;")
            nav_layout.addWidget(self.help_search_results)
            
            # Add the navigation widget (not layout) to the main layout
            v.addWidget(nav_widget)
            
            # Update button states based on history
            self.help_browser.urlChanged.connect(
                lambda: self.btn_help_back.setEnabled(self.help_browser.history().canGoBack()))
            self.help_browser.urlChanged.connect(
                lambda: self.btn_help_forward.setEnabled(self.help_browser.history().canGoForward()))
            
            # Load content
            readme_content = self._load_readme_content(replace_emojis=False)  # Don't replace - WebEngine handles emojis!
            html_content = self._markdown_to_html_with_anchors(readme_content, use_webengine=True)

            # Define a function to trigger the scroll after load
            def trigger_initial_scroll():
                # More aggressive scroll to force render
                self.help_browser.page().runJavaScript("""
                    window.scrollTo(0, 0);
                    setTimeout(function() {
                        window.scrollBy(0, 1);
                        window.scrollBy(0, -1);
                    }, 50);
                """)

            # Connect to loadFinished signal for one-time trigger
            def on_initial_load_finished():
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, trigger_initial_scroll)
                # Disconnect after use to avoid multiple triggers
                try:
                    self.help_browser.loadFinished.disconnect(on_initial_load_finished)
                except:
                    pass

            self.help_browser.loadFinished.connect(on_initial_load_finished)

            # Load HTML with base URL for relative links
            self.help_browser.setHtml(html_content, QUrl("file:///"))

            v.addWidget(self.help_browser)

            # Enable initial button states
            self.btn_help_back.setEnabled(False)
            self.btn_help_forward.setEnabled(False)
            
            return  # Exit early if WebEngine works
            
        except ImportError:
            print("QWebEngineView not available, falling back to QTextBrowser")
            
        # Fallback to QTextBrowser implementation
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QFont, QFontDatabase
        import platform
        
        class CustomHelpBrowser(QTextBrowser):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.anchor_history = []
                self.history_index = -1
                self._parent_window = parent
                self._navigating_history = False  # Flag to prevent adding to history during back/forward
                
                # Connect to anchorClicked signal to intercept ALL link clicks
                self.anchorClicked.connect(self.handle_anchor_click)
                
            def handle_anchor_click(self, url):
                """Handle all anchor/link clicks."""
                import webbrowser
                from pathlib import Path

                # Check if it's an external link
                if url.scheme() in ('http', 'https', 'ftp'):
                    webbrowser.open(url.toString())
                    return

                # Check if it's a local file link (like CHANGELOG.md)
                url_str = url.toString()
                if url.scheme() in ('', 'file') and not url_str.startswith('#'):
                    # Try to load local markdown file
                    try:
                        # Get the project root directory
                        project_root = Path(__file__).parent.parent

                        # Parse the file path from URL
                        if url_str.startswith('file:///'):
                            file_path = url_str.replace('file:///', '')
                        else:
                            file_path = url_str

                        # Resolve relative to project root
                        full_path = project_root / file_path

                        if full_path.exists() and full_path.suffix.lower() == '.md':
                            # Before navigating away, ensure current position is in history
                            # This fixes the back button being disabled on first navigation
                            if len(self.anchor_history) <= 1:
                                # We're at the initial README, add it to history
                                self.add_to_history("README.md")

                            # Load and display the markdown file
                            content = full_path.read_text(encoding='utf-8')

                            # Convert to HTML and display
                            parent = self.parent()
                            while parent and not hasattr(parent, '_markdown_to_html_with_anchors'):
                                parent = parent.parent()

                            if parent:
                                # Convert to HTML
                                html = parent._markdown_to_html_with_anchors(content, use_webengine=False)
                                self.setHtml(html)
                                self.verticalScrollBar().setValue(0)
                                self.add_to_history(file_path)

                                # Update the window/tab title or status to show current file
                                if hasattr(parent, 'status_label'):
                                    parent.status_label.setText(f"Viewing: {file_path}")

                                return
                    except Exception as e:
                        print(f"Error loading local file: {e}")
                
                # Internal anchor link
                anchor = url.fragment() if url.hasFragment() else ""
                
                # Don't add to history if we're navigating via back/forward
                if not self._navigating_history:
                    # If it's just a fragment, scroll to it
                    if anchor:
                        self.scrollToAnchor(anchor)
                    else:
                        # No anchor means go to top
                        self.verticalScrollBar().setValue(0)
                    
                    # Add to history
                    self.add_to_history(anchor)
                
            def add_to_history(self, anchor):
                """Add anchor to navigation history."""
                # Remove any forward history when navigating to a new anchor
                if self.history_index < len(self.anchor_history) - 1:
                    self.anchor_history = self.anchor_history[:self.history_index + 1]
                
                # Don't add duplicate entries
                if not self.anchor_history or self.anchor_history[-1] != anchor:
                    self.anchor_history.append(anchor)
                    self.history_index = len(self.anchor_history) - 1
                
                self.update_nav_buttons()
            
            def go_back(self):
                """Navigate back in history."""
                if self.history_index > 0:
                    from PySide6.QtCore import QTimer
                    from pathlib import Path
                    self._navigating_history = True
                    self.history_index -= 1
                    anchor = self.anchor_history[self.history_index]

                    # Use QTimer to delay scrolling to avoid focus-related timing issues
                    def do_navigation():
                        # Check if anchor is a file path (like README.md or CHANGELOG.md)
                        if anchor and (anchor.endswith('.md') or anchor == "README.md"):
                            # Reload the file
                            parent = self.parent()
                            while parent and not hasattr(parent, '_load_readme_content'):
                                parent = parent.parent()

                            if parent and anchor == "README.md":
                                # Reload README
                                readme_content = parent._load_readme_content(replace_emojis=False)
                                html = parent._markdown_to_html_with_anchors(readme_content, use_webengine=False)
                                self.setHtml(html)
                                self.verticalScrollBar().setValue(0)
                            elif anchor.endswith('.md'):
                                # Load other markdown file
                                try:
                                    project_root = Path(__file__).parent.parent
                                    full_path = project_root / anchor
                                    if full_path.exists():
                                        content = full_path.read_text(encoding='utf-8')
                                        html = parent._markdown_to_html_with_anchors(content, use_webengine=False)
                                        self.setHtml(html)
                                        self.verticalScrollBar().setValue(0)
                                except Exception as e:
                                    print(f"Error loading {anchor}: {e}")
                        elif anchor:
                            self.scrollToAnchor(anchor)
                        else:
                            # Scroll to top
                            self.verticalScrollBar().setValue(0)
                        self._navigating_history = False

                    # Small delay to let Qt process focus events
                    QTimer.singleShot(10, do_navigation)
                    self.update_nav_buttons()
            
            def go_forward(self):
                """Navigate forward in history."""
                if self.history_index < len(self.anchor_history) - 1:
                    from PySide6.QtCore import QTimer
                    from pathlib import Path
                    self._navigating_history = True
                    self.history_index += 1
                    anchor = self.anchor_history[self.history_index]

                    # Use QTimer to delay scrolling to avoid focus-related timing issues
                    def do_navigation():
                        # Check if anchor is a file path (like README.md or CHANGELOG.md)
                        if anchor and (anchor.endswith('.md') or anchor == "README.md"):
                            # Reload the file
                            parent = self.parent()
                            while parent and not hasattr(parent, '_load_readme_content'):
                                parent = parent.parent()

                            if parent and anchor == "README.md":
                                # Reload README
                                readme_content = parent._load_readme_content(replace_emojis=False)
                                html = parent._markdown_to_html_with_anchors(readme_content, use_webengine=False)
                                self.setHtml(html)
                                self.verticalScrollBar().setValue(0)
                            elif anchor.endswith('.md'):
                                # Load other markdown file
                                try:
                                    project_root = Path(__file__).parent.parent
                                    full_path = project_root / anchor
                                    if full_path.exists():
                                        content = full_path.read_text(encoding='utf-8')
                                        html = parent._markdown_to_html_with_anchors(content, use_webengine=False)
                                        self.setHtml(html)
                                        self.verticalScrollBar().setValue(0)
                                except Exception as e:
                                    print(f"Error loading {anchor}: {e}")
                        elif anchor:
                            self.scrollToAnchor(anchor)
                        else:
                            # Scroll to top
                            self.verticalScrollBar().setValue(0)
                        self._navigating_history = False

                    # Small delay to let Qt process focus events
                    QTimer.singleShot(10, do_navigation)
                    self.update_nav_buttons()
            
            def go_home(self):
                """Go to top of document."""
                from PySide6.QtCore import QTimer
                
                # Use QTimer for consistency with other navigation
                def do_scroll():
                    self.verticalScrollBar().setValue(0)
                
                QTimer.singleShot(10, do_scroll)
                
                if not self._navigating_history:
                    self.add_to_history(None)  # Add top as a history entry
            
            def update_nav_buttons(self):
                """Update navigation button states."""
                if self._parent_window and hasattr(self._parent_window, 'btn_help_back'):
                    self._parent_window.btn_help_back.setEnabled(self.history_index > 0)
                    self._parent_window.btn_help_forward.setEnabled(
                        self.history_index < len(self.anchor_history) - 1
                    )
            
            def keyPressEvent(self, event):
                """Handle keyboard shortcuts."""
                from PySide6.QtCore import Qt
                key = event.key()
                modifiers = event.modifiers()
                
                if key == Qt.Key_Backspace or (key == Qt.Key_Left and modifiers == Qt.AltModifier):
                    self.go_back()
                    event.accept()
                elif key == Qt.Key_Right and modifiers == Qt.AltModifier:
                    self.go_forward()
                    event.accept()
                elif key == Qt.Key_Home and modifiers == Qt.ControlModifier:
                    self.go_home()
                    event.accept()
                else:
                    super().keyPressEvent(event)
            
            def mousePressEvent(self, event):
                """Handle mouse button navigation."""
                from PySide6.QtCore import Qt
                button = event.button()
                
                if button == Qt.XButton1:  # Mouse back button (usually button 4)
                    self.go_back()
                    event.accept()
                elif button == Qt.XButton2:  # Mouse forward button (usually button 5)
                    self.go_forward()
                    event.accept()
                else:
                    super().mousePressEvent(event)
        
        # Create navigation toolbar container widget with fixed height
        nav_widget = QWidget()
        nav_widget.setMaximumHeight(30)
        nav_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setSpacing(2)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        
        # Back button
        self.btn_help_back = QPushButton("◀ Back")
        self.btn_help_back.setEnabled(False)
        self.btn_help_back.setToolTip("Go back (Alt+Left, Backspace)")
        nav_layout.addWidget(self.btn_help_back)
        
        # Forward button
        self.btn_help_forward = QPushButton("Forward ▶")
        self.btn_help_forward.setEnabled(False)
        self.btn_help_forward.setToolTip("Go forward (Alt+Right)")
        nav_layout.addWidget(self.btn_help_forward)
        
        # Home button
        self.btn_help_home = QPushButton("⌂ Home")
        self.btn_help_home.setToolTip("Go to top (Ctrl+Home)")
        nav_layout.addWidget(self.btn_help_home)
        
        nav_layout.addStretch()
        
        # Search controls - compact layout
        search_label = QLabel("Search:")
        nav_layout.addWidget(search_label)
        
        self.help_search_input = QLineEdit()
        self.help_search_input.setPlaceholderText("Find in docs...")
        self.help_search_input.setMaximumWidth(200)
        self.help_search_input.returnPressed.connect(self._search_help_textbrowser)
        nav_layout.addWidget(self.help_search_input)
        
        self.btn_help_search_prev = QPushButton("◀")
        self.btn_help_search_prev.setToolTip("Previous match (Shift+F3)")
        self.btn_help_search_prev.clicked.connect(lambda: self._search_help_textbrowser(backward=True))
        self.btn_help_search_prev.setMaximumWidth(25)
        nav_layout.addWidget(self.btn_help_search_prev)
        
        self.btn_help_search_next = QPushButton("▶")
        self.btn_help_search_next.setToolTip("Next match (F3)")
        self.btn_help_search_next.clicked.connect(self._search_help_textbrowser)
        self.btn_help_search_next.setMaximumWidth(25)
        nav_layout.addWidget(self.btn_help_search_next)
        
        self.help_search_results = QLabel("")
        self.help_search_results.setMinimumWidth(80)
        self.help_search_results.setStyleSheet("color: #666;")
        nav_layout.addWidget(self.help_search_results)
        
        # Add the navigation widget (not layout) to the main layout
        v.addWidget(nav_widget)
        
        # Create custom help browser
        self.help_browser = CustomHelpBrowser(self)
        
        # Connect button clicks
        self.btn_help_back.clicked.connect(self.help_browser.go_back)
        self.btn_help_forward.clicked.connect(self.help_browser.go_forward)
        self.btn_help_home.clicked.connect(self.help_browser.go_home)
        
        # Set minimal stylesheet - let system handle fonts for emoji support
        try:
            self.help_browser.setStyleSheet("QTextBrowser { font-size: 13pt; }")
            # Don't override document fonts - let HTML content control it
        except Exception:
            pass
        
        # Load and convert README content to HTML with proper anchors
        readme_content = self._load_readme_content(replace_emojis=True)  # Replace for QTextBrowser
        html_content = self._markdown_to_html_with_anchors(readme_content, use_webengine=False)
        
        try:
            self.help_browser.setHtml(html_content)
            # Start with "top" in history
            self.help_browser.add_to_history(None)
        except Exception:
            # Fallback to markdown if HTML fails
            try:
                self.help_browser.setMarkdown(readme_content)
            except Exception:
                self.help_browser.setPlainText(readme_content)
        
        # IMPORTANT: Set to False so we can intercept ALL link clicks via anchorClicked signal
        self.help_browser.setOpenExternalLinks(False)
        
        v.addWidget(self.help_browser)
        
        # Trigger initial render with minimal scroll
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._trigger_help_render)
    
    def _load_readme_content(self, replace_emojis=True) -> str:
        """Load and process README.md content for help display."""
        try:
            # Get the README path relative to main.py location
            from pathlib import Path
            
            # Look for README.md in the project root (parent of gui folder)
            readme_path = Path(__file__).parent.parent / "README.md"
            
            if readme_path.exists():
                content = readme_path.read_text(encoding="utf-8")
                
                # Only replace emojis for QTextBrowser, not QWebEngineView
                if replace_emojis:
                    content = self._replace_emojis_with_text(content)
                
                # Filter out development-specific sections for user help
                lines = content.split('\n')
                filtered_lines = []
                skip_section = False
                skip_headers = {'## 13. Development', '## 14. Changelog', '## Credits', '## License', '## Support'}
                
                for line in lines:
                    # Check if we should skip this section
                    if any(line.startswith(header) for header in skip_headers):
                        skip_section = True
                        continue
                    
                    # Check if we're starting a new major section (reset skip)
                    if line.startswith('## ') and not any(line.startswith(header) for header in skip_headers):
                        skip_section = False
                    
                    # Add line if we're not skipping
                    if not skip_section:
                        filtered_lines.append(line)
                
                return '\n'.join(filtered_lines)
                
        except Exception as e:
            print(f"Could not load README.md: {e}")
        
        # Fallback help text if README.md can't be loaded
        return self._get_fallback_help()
    
    def _markdown_to_html_with_anchors(self, markdown_text: str, use_webengine: bool = False, base_path: str = None) -> str:
        """Convert markdown to HTML with proper GitHub-style anchor IDs.

        Args:
            markdown_text: The markdown text to convert
            use_webengine: Whether to format for QWebEngineView (vs QTextBrowser)
            base_path: Base path for resolving relative image URLs
        """
        try:
            # Try to use the markdown library if available
            import markdown
            from markdown.extensions.toc import TocExtension
            from pathlib import Path

            # If base_path not specified, use project root
            if base_path is None:
                base_path = str(Path(__file__).parent.parent)

            # Configure to generate GitHub-style anchors
            md = markdown.Markdown(extensions=[
                'fenced_code',
                'tables',
                TocExtension(slugify=self._github_slugify),
            ])

            # Process the markdown
            html_body = md.convert(markdown_text)

            # Fix image paths to be absolute file:/// URLs for local images
            import re
            def fix_image_path(match):
                img_path = match.group(1)
                # Skip if already an absolute URL
                if img_path.startswith(('http://', 'https://', 'file:///')):
                    return match.group(0)
                # Convert to absolute path
                full_path = Path(base_path) / img_path
                if full_path.exists():
                    # Convert to file:/// URL
                    file_url = full_path.as_uri()
                    return f'<img src="{file_url}"'
                return match.group(0)

            html_body = re.sub(r'<img src="([^"]+)"', fix_image_path, html_body)
            
            # Add explicit anchors for headers that might not have them
            html_body = self._add_explicit_anchors(html_body)
            
            # Wrap in proper HTML document with UTF-8 encoding
            if use_webengine:
                # QWebEngineView can handle emojis with proper font stack
                html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Color Emoji", 
                         "Apple Color Emoji", "Segoe UI Emoji", Roboto, Helvetica, Arial, sans-serif;
            font-size: 13pt;
            line-height: 1.4;
            margin: 10px;
        }}
        h1 {{ font-size: 20pt; color: #2c3e50; }}
        h2 {{ font-size: 16pt; color: #2c3e50; }}
        h3 {{ font-size: 14pt; color: #2c3e50; }}
        code {{ 
            background-color: #f8f9fa; 
            padding: 2px 4px; 
            border-radius: 3px; 
        }}
        pre {{ 
            background-color: #f8f9fa; 
            padding: 10px; 
            border-radius: 5px; 
            overflow-x: auto; 
        }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        table {{ 
            border-collapse: collapse; 
            width: 100%; 
            margin: 15px 0;
        }}
        th, td {{ 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: left;
        }}
        th {{ 
            background-color: #f0f0f0; 
            font-weight: bold;
        }}
        tr:nth-child(even) {{ 
            background-color: #f9f9f9;
        }}
        td:first-child {{
            background-color: #f5f5f5;
            font-weight: 500;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        hr {{
            border: 0;
            height: 1px;
            background: #e1e4e8;
            margin: 30px 0;
        }}
        em {{
            color: #666;
            font-style: italic;
            display: block;
            text-align: center;
            margin-top: -15px;
            margin-bottom: 20px;
            font-size: 12pt;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>'''
            else:
                # QTextBrowser - simpler styling
                html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <style>
        body {{ 
            font-size: 13pt;
            line-height: 1.4;
            margin: 10px;
        }}
        h1 {{ font-size: 20pt; color: #2c3e50; }}
        h2 {{ font-size: 16pt; color: #2c3e50; }}
        h3 {{ font-size: 14pt; color: #2c3e50; }}
        code {{ 
            background-color: #f8f9fa; 
            padding: 2px 4px; 
            border-radius: 3px; 
        }}
        pre {{ 
            background-color: #f8f9fa; 
            padding: 10px; 
            border-radius: 5px; 
            overflow-x: auto; 
        }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        table {{ 
            border-collapse: collapse; 
            width: 100%; 
            margin: 15px 0;
        }}
        th, td {{ 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: left;
        }}
        th {{ 
            background-color: #f0f0f0; 
            font-weight: bold;
        }}
        tr:nth-child(even) {{ 
            background-color: #f9f9f9;
        }}
        td:first-child {{
            background-color: #f5f5f5;
            font-weight: 500;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        hr {{
            border: 0;
            height: 1px;
            background: #e1e4e8;
            margin: 30px 0;
        }}
        em {{
            color: #666;
            font-style: italic;
            display: block;
            text-align: center;
            margin-top: -15px;
            margin-bottom: 20px;
            font-size: 12pt;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>'''
            
            return html
            
        except ImportError:
            # If markdown library is not available, do basic conversion
            return self._basic_markdown_to_html(markdown_text)
    
    def _github_slugify(self, value, separator):
        """Generate GitHub-style anchor IDs from header text."""
        # Convert to lowercase and replace spaces with hyphens
        # Keep numbers and letters, replace other chars with hyphens
        import re
        value = value.lower()
        # Replace spaces and dots with hyphens
        value = re.sub(r'[\s\.]+', '-', value)
        # Remove other special characters
        value = re.sub(r'[^\w\-]', '', value)
        # Remove leading/trailing hyphens
        value = value.strip('-')
        return value
    
    def _add_explicit_anchors(self, html: str) -> str:
        """Add explicit anchor tags for headers to ensure navigation works."""
        import re
        
        # Pattern to find headers - use non-greedy match and handle any content
        header_pattern = r'<h([1-6])[^>]*>(.+?)</h\1>'
        
        def replace_header(match):
            level = match.group(1)
            text = match.group(2)
            # Strip any existing anchor tags or IDs from the text
            clean_text = re.sub(r'<[^>]+>', '', text)
            # Generate anchor ID from clean text (without HTML tags)
            anchor_id = self._github_slugify(clean_text, '-')
            # Return header with explicit anchor, preserving original text (with emojis)
            return f'<h{level} id="{anchor_id}"><a name="{anchor_id}"></a>{text}</h{level}>'
        
        return re.sub(header_pattern, replace_header, html, flags=re.DOTALL)
    
    def _basic_markdown_to_html(self, markdown_text: str) -> str:
        """Basic markdown to HTML conversion with proper anchors and UTF-8 encoding."""
        import re
        
        lines = markdown_text.split('\n')
        html_lines = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<meta charset="UTF-8">',
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">',
            '<style>',
            'body { font-size: 13pt; line-height: 1.4; margin: 10px; }',
            'h1 { font-size: 20pt; color: #2c3e50; }',
            'h2 { font-size: 16pt; color: #2c3e50; }',
            'h3 { font-size: 14pt; color: #2c3e50; }',
            'code { background-color: #f8f9fa; padding: 2px 4px; border-radius: 3px; }',
            'pre { background-color: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto; }',
            'a { color: #0366d6; text-decoration: none; }',
            'a:hover { text-decoration: underline; }',
            'table { border-collapse: collapse; width: 100%; margin: 15px 0; }',
            'th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }',
            'th { background-color: #f0f0f0; font-weight: bold; }',
            'tr:nth-child(even) { background-color: #f9f9f9; }',
            'td:first-child { background-color: #f5f5f5; font-weight: 500; }',
            '</style>',
            '</head>',
            '<body>'
        ]
        in_code_block = False
        in_list = False
        
        for line in lines:
            # Handle code blocks
            if line.startswith('```'):
                if in_code_block:
                    html_lines.append('</pre>')
                    in_code_block = False
                else:
                    html_lines.append('<pre>')
                    in_code_block = True
                continue
            
            if in_code_block:
                # Escape HTML in code blocks
                line = line.replace('<', '&lt;').replace('>', '&gt;')
                html_lines.append(line)
                continue
            
            # Convert headers with anchors (preserve emojis)
            if line.startswith('#'):
                match = re.match(r'^(#+)\s+(.+)$', line)
                if match:
                    level = len(match.group(1))
                    text = match.group(2)
                    anchor_id = self._github_slugify(text, '-')
                    # Don't escape the text - preserve emojis
                    html_lines.append(f'<h{level} id="{anchor_id}"><a name="{anchor_id}"></a>{text}</h{level}>')
                    continue
            
            # Handle lists
            is_list_item = False
            if line.strip().startswith('- ') or line.strip().startswith('* '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                line = '<li>' + line.strip()[2:] + '</li>'
                is_list_item = True
            elif re.match(r'^\d+\.\s', line.strip()):
                if not in_list:
                    html_lines.append('<ol>')
                    in_list = True
                line = '<li>' + re.sub(r'^\d+\.\s', '', line.strip()) + '</li>'
                is_list_item = True
            elif in_list and not line.strip():
                # End of list
                html_lines.append('</ul>' if '<ul>' in html_lines[-10:] else '</ol>')
                in_list = False
            
            # Convert links
            # Handle [text](url) style links
            line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', line)
            
            # Convert bold and italic
            line = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', line)
            
            # Convert inline code
            line = re.sub(r'`([^`]+)`', r'<code>\1</code>', line)
            
            # Add line breaks for non-empty lines
            if line.strip():
                if not is_list_item:
                    html_lines.append(line + '<br>')
                else:
                    html_lines.append(line)
            else:
                html_lines.append('<br>')
        
        # Close any open list
        if in_list:
            html_lines.append('</ul>' if '<ul>' in html_lines[-10:] else '</ol>')
        
        html_lines.extend(['</body>', '</html>'])
        return '\n'.join(html_lines)
    
    def _replace_emojis_with_text(self, content: str) -> str:
        """Replace emojis with text equivalents for better compatibility."""
        # Use simple text/symbol replacements that work universally
        replacements = {
            "🎨": "●",  # Art/Palette - bullet point
            "🔐": "●",  # Security/Lock - bullet point
            "💻": "●",  # Computer - bullet point
            "📁": "●",  # Folder - bullet point
            "🏠": "[Home]",
            "⌂": "[Home]",
            "◀": "←",  # Left arrow
            "▶": "→",  # Right arrow
            "✓": "✓",  # Checkmark (basic unicode)
            "✅": "[✓]",
            "❌": "[X]",
            "⚙️": "[Settings]",
            "🚀": "[>]",
            "❤️": "♥",  # Heart (basic unicode)
            "🌟": "★",  # Star (basic unicode)
        }
        
        for emoji, text in replacements.items():
            content = content.replace(emoji, text)
        
        return content
    
    def _get_fallback_help(self) -> str:
        """Return fallback help content if README cannot be loaded."""
        return f"""# ImageAI Help

## Quick Start Guide

### Setting Up Authentication

**For Google Gemini:**
1. Visit [Google AI Studio](https://aistudio.google.com/apikey)
2. Create or copy an API key
3. Enter the key in Settings tab
4. Click "Save & Test"

**For OpenAI DALL-E:**
1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create an API key
3. Select "OpenAI" provider in Settings
4. Enter your key and save

**For Stability AI:**
1. Visit [Stability AI Platform](https://platform.stability.ai/)
2. Create an API key
3. Select "Stability AI" provider in Settings
4. Enter your key and save

**For Local Stable Diffusion:**
1. No API key needed!
2. Select "Local SD" provider in Settings
3. Requires additional dependencies (see installation guide)

### Generating Images

1. **Enter a Prompt**: Type your image description in the text area
2. **Select Model**: Choose a model from the dropdown (optional)
3. **Click Generate**: Press the Generate button or Ctrl+Enter
4. **Wait**: Generation typically takes 5-30 seconds
5. **View Result**: Image appears below when complete

### Using Templates

Templates help you create consistent prompts:
1. Go to Templates tab
2. Select a template from the dropdown
3. Fill in the placeholders (optional)
4. Click "Insert into Prompt"

### Tips for Better Results

**Be Specific**: Instead of "a cat", try "a fluffy orange tabby cat sitting on a windowsill"

**Include Style**: Add artistic style like "oil painting", "photorealistic", "cartoon style"

**Describe Mood**: Include lighting and atmosphere like "golden hour", "dramatic lighting", "cozy"

**Add Details**: More details generally produce better results

### Keyboard Shortcuts

- **Ctrl+Enter**: Generate image
- **Ctrl+S**: Save current image
- **Ctrl+Q**: Quit application
- **Ctrl+A**: Select all text
- **Ctrl+C/V/X**: Copy/Paste/Cut

### Common Issues

**"API key not found"**: Make sure you've entered and saved your API key in Settings

**"Invalid API key"**: Verify your key is correct and active on the provider's website

**"Quota exceeded"**: Check your usage limits on the provider's dashboard

**"Module not found"**: Run `pip install -r requirements.txt` to install dependencies

For more detailed information, please refer to the full documentation.
"""
    
    def _init_templates_tab(self):
        """Initialize templates tab."""
        v = QVBoxLayout(self.tab_templates)
        v.setSpacing(10)
        
        # Info text
        info_label = QLabel("Select a template and fill in any attributes (all optional):")
        v.addWidget(info_label)
        
        # Template selection dropdown
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "Photorealistic product shot",
            "Fantasy Landscape", 
            "Sci-Fi Scene",
            "Abstract Art",
            "Character concept art",
            "Architectural Render",
            "Character Design",
            "Logo Design"
        ])
        v.addWidget(self.template_combo)
        
        # Template attributes form
        self.template_form = QFormLayout()
        self.template_form.setSpacing(8)
        
        # Dictionary to store attribute input fields
        self.template_inputs = {}
        
        # Create initial attribute fields for the first template
        self._create_template_fields()
        
        v.addLayout(self.template_form)
        
        # Add stretch to push everything to the top
        v.addStretch()
        
        # Options
        self.append_prompt_check = QCheckBox("Append to current prompt instead of replacing")
        v.addWidget(self.append_prompt_check)
        
        # Apply button
        self.btn_insert_prompt = QPushButton("&Insert into Prompt")  # Alt+I
        self.btn_insert_prompt.setStyleSheet("""
            QPushButton {
                padding: 8px;
                font-weight: bold;
            }
        """)
        v.addWidget(self.btn_insert_prompt)
        
        # Connect signals
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        self.btn_insert_prompt.clicked.connect(self._apply_template)
    
    def _init_history_tab(self):
        """Initialize history tab with enhanced table display."""
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QHBoxLayout

        v = QVBoxLayout(self.tab_history)

        # Add checkbox for showing non-project images
        controls_layout = QHBoxLayout()
        self.chk_show_all_images = QCheckBox("Show non-project images")
        self.chk_show_all_images.setChecked(False)
        self.chk_show_all_images.toggled.connect(self._on_show_all_images_toggled)
        controls_layout.addWidget(self.chk_show_all_images)
        controls_layout.addStretch()
        v.addLayout(controls_layout)

        # Create table widget for better organization
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Date & Time", "Provider", "Model", "Prompt", "Resolution", "Cost"
        ])
        
        # Configure table
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSortingEnabled(True)
        
        # Set column widths
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Date & Time
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Provider
        header.setSectionResizeMode(2, QHeaderView.Interactive)  # Model
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Prompt - takes remaining space
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Resolution
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Cost
        
        # Populate table with history
        self.history_table.setRowCount(len(self.history))
        for row, item in enumerate(self.history):
            if isinstance(item, dict):
                # Parse timestamp and combine date & time
                timestamp = item.get('timestamp', '')
                datetime_str = ''
                sortable_datetime = None
                if isinstance(timestamp, float):
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp)
                    datetime_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    sortable_datetime = dt
                elif isinstance(timestamp, str) and 'T' in timestamp:
                    # ISO format
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        datetime_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        sortable_datetime = dt
                    except:
                        parts = timestamp.split('T')
                        date_str = parts[0]
                        time_str = parts[1].split('.')[0] if len(parts) > 1 else ''
                        datetime_str = f"{date_str} {time_str}"
                
                # Date & Time column (combined)
                datetime_item = QTableWidgetItem(datetime_str)
                # Store sortable datetime for proper chronological sorting
                if sortable_datetime:
                    datetime_item.setData(Qt.UserRole + 1, sortable_datetime)
                self.history_table.setItem(row, 0, datetime_item)
                
                # Provider column (now column 1)
                provider = item.get('provider', '')
                provider_item = QTableWidgetItem(provider.title() if provider else 'Unknown')
                self.history_table.setItem(row, 1, provider_item)
                
                # Model column (now column 2)
                model = item.get('model', '')
                model_display = model.split('/')[-1] if '/' in model else model  # Simplify model names
                model_item = QTableWidgetItem(model_display)
                model_item.setToolTip(model)  # Full model name in tooltip
                self.history_table.setItem(row, 2, model_item)
                
                # Prompt column (now column 3)
                prompt = item.get('prompt', 'No prompt')
                prompt_item = QTableWidgetItem(prompt[:100] + '...' if len(prompt) > 100 else prompt)
                prompt_item.setToolTip(f"Full prompt:\n{prompt}")
                self.history_table.setItem(row, 3, prompt_item)
                
                # Resolution column (now column 4)
                width = item.get('width', '')
                height = item.get('height', '')
                resolution = f"{width}x{height}" if width and height else ''
                resolution_item = QTableWidgetItem(resolution)
                self.history_table.setItem(row, 4, resolution_item)
                
                # Cost column (now column 5)
                cost = item.get('cost', 0.0)
                cost_str = f"${cost:.4f}" if cost > 0 else '-'
                cost_item = QTableWidgetItem(cost_str)
                self.history_table.setItem(row, 5, cost_item)
                
                # Store the history item data in the first column for easy retrieval
                datetime_item.setData(Qt.UserRole, item)
        
        v.addWidget(QLabel(f"History ({len(self.history)} items):"))
        v.addWidget(self.history_table)
        
        # Buttons
        h = QHBoxLayout()
        self.btn_load_history = QPushButton("&Load Selected")  # Alt+L
        self.btn_clear_history = QPushButton("C&lear History")  # Alt+L
        h.addWidget(self.btn_load_history)
        h.addStretch()
        h.addWidget(self.btn_clear_history)
        v.addLayout(h)
        
        # Connect signals
        self.history_table.selectionModel().selectionChanged.connect(self._on_history_selection_changed)
        self.history_table.itemDoubleClicked.connect(self._load_history_item)
        self.btn_load_history.clicked.connect(self._load_selected_history)
        self.btn_clear_history.clicked.connect(self._clear_history)
    
    def _find_model_in_combo(self, model_id: str) -> int:
        """Find a model by its ID in the combo box.
        
        Args:
            model_id: The model ID to search for
            
        Returns:
            Index of the model in the combo box, or -1 if not found
        """
        # First try to find by data (preferred method)
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == model_id:
                return i
        
        # Fallback: try to find by text (for backward compatibility)
        for i in range(self.model_combo.count()):
            text = self.model_combo.itemText(i)
            # Check if the model ID is in the text (e.g., "Name (model-id)")
            if f"({model_id})" in text or text == model_id:
                return i
        
        return -1
    
    def _update_model_list(self):
        """Update model combo box based on current provider."""
        self.model_combo.clear()
        
        try:
            # Get provider instance to fetch available models
            provider = get_provider(self.current_provider, {"api_key": ""})
            
            # Try to get detailed model information if available
            if hasattr(provider, 'get_models_with_details'):
                models_details = provider.get_models_with_details()
                
                for model_id, details in models_details.items():
                    # Format display text based on available information
                    display_text = ""
                    
                    # Add nickname if available (e.g., "Nano Banana")
                    if details.get('nickname'):
                        display_text = f"{details['nickname']} — "
                    
                    # Add model name
                    display_text += details.get('name', model_id)
                    
                    # Add model ID in parentheses
                    display_text += f" ({model_id})"
                    
                    # Add item with display text and store model ID as data
                    self.model_combo.addItem(display_text, model_id)
            else:
                # Fallback to simple models list
                models = provider.get_models()
                if models:
                    for model_id, display_name in models.items():
                        # Format: "Display Name (model-id)"
                        display_text = f"{display_name} ({model_id})"
                        self.model_combo.addItem(display_text, model_id)
            
            # Set default model
            default_model = provider.get_default_model()
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == default_model:
                    self.model_combo.setCurrentIndex(i)
                    break
                    
        except Exception as e:
            # Fallback to some basic models if provider fails to load
            print(f"Error loading models for {self.current_provider}: {e}")
            if self.current_provider == "google":
                self.model_combo.addItem("Gemini 2.5 Flash Image (gemini-2.5-flash-image-preview)", 
                                        "gemini-2.5-flash-image-preview")
            elif self.current_provider == "openai":
                self.model_combo.addItem("DALL·E 3 (dall-e-3)", "dall-e-3")
            elif self.current_provider == "stability":
                self.model_combo.addItem("Stable Diffusion XL (stable-diffusion-xl-1024-v1-0)", 
                                        "stable-diffusion-xl-1024-v1-0")
            elif self.current_provider == "local_sd":
                self.model_combo.addItem("Stable Diffusion 2.1 (stabilityai/stable-diffusion-2-1)", 
                                        "stabilityai/stable-diffusion-2-1")
    
    def _update_advanced_visibility(self):
        """Show/hide advanced settings based on provider."""
        # Update new advanced panel if available
        if hasattr(self, 'advanced_panel') and self.advanced_panel:
            self.advanced_panel.update_provider(self.current_provider)
        # Update old advanced group for fallback
        elif hasattr(self, 'advanced_group'):
            # Only show for local_sd provider
            self.advanced_group.setVisible(self.current_provider == "local_sd")

    @staticmethod
    def get_llm_providers():
        """Get list of all available LLM providers."""
        return ["None", "OpenAI", "Claude", "Gemini", "Ollama", "LM Studio"]

    @staticmethod
    def get_llm_models_for_provider(provider: str):
        """Get list of models for a specific LLM provider."""
        models = {
            "OpenAI": ["gpt-5-chat-latest", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"],
            "Claude": ["claude-opus-4.1", "claude-opus-4", "claude-sonnet-4", "claude-3.7-sonnet", "claude-3.5-sonnet", "claude-3.5-haiku"],
            "Gemini": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-pro"],
            "Ollama": ["llama2", "mistral", "mixtral", "phi-2", "neural-chat"],
            "LM Studio": ["local-model", "custom-model"]
        }
        return models.get(provider, [])

    def populate_llm_combo(self, provider_combo, model_combo, current_provider=None, current_model=None):
        """Populate LLM provider and model combos with all available options.

        Args:
            provider_combo: The provider QComboBox to populate
            model_combo: The model QComboBox to populate
            current_provider: Optional current provider to select
            current_model: Optional current model to select
        """
        # Populate providers
        provider_combo.blockSignals(True)
        provider_combo.clear()
        provider_combo.addItems(self.get_llm_providers())

        if current_provider:
            index = provider_combo.findText(current_provider)
            if index >= 0:
                provider_combo.setCurrentIndex(index)

        provider_combo.blockSignals(False)

        # Populate models based on selected provider
        selected_provider = provider_combo.currentText()
        model_combo.blockSignals(True)
        model_combo.clear()

        if selected_provider and selected_provider != "None":
            models = self.get_llm_models_for_provider(selected_provider)
            model_combo.addItems(models)
            model_combo.setEnabled(True)

            if current_model:
                index = model_combo.findText(current_model)
                if index >= 0:
                    model_combo.setCurrentIndex(index)
        else:
            model_combo.setEnabled(False)

        model_combo.blockSignals(False)

    def _on_llm_provider_changed(self, provider: str):
        """Handle LLM provider change on Image tab."""
        # Don't do anything if we're being updated programmatically
        if getattr(self, '_updating_llm_provider', False):
            return

        # Use centralized function to populate models
        self.llm_model_combo.blockSignals(True)
        self.llm_model_combo.clear()

        if provider == "None":
            self.llm_model_combo.setEnabled(False)
        else:
            self.llm_model_combo.setEnabled(True)
            models = self.get_llm_models_for_provider(provider)
            self.llm_model_combo.addItems(models)

        self.llm_model_combo.blockSignals(False)

        # Sync with Video tab if it's loaded
        if self._video_tab_loaded and hasattr(self.tab_video, 'set_llm_provider'):
            self.tab_video.set_llm_provider(provider, self.llm_model_combo.currentText() if provider != "None" else None)

    def _on_llm_model_changed(self, model: str):
        """Handle LLM model change on Image tab."""
        # Don't do anything if we're being updated programmatically
        if getattr(self, '_updating_llm_provider', False):
            return

        # Sync with Video tab if it's loaded
        if self._video_tab_loaded and hasattr(self.tab_video, 'set_llm_provider'):
            provider = self.llm_provider_combo.currentText()
            self.tab_video.set_llm_provider(provider, model if provider != "None" else None)

    def _schedule_ui_save(self):
        """Schedule a UI state save after a short delay to avoid rapid saves."""
        if not hasattr(self, '_save_timer'):
            self._save_timer = QTimer()
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._delayed_ui_save)

        # Cancel any pending save and schedule a new one
        self._save_timer.stop()
        self._save_timer.start(500)  # Save after 500ms of no changes

    def _delayed_ui_save(self):
        """Perform the actual UI state save."""
        try:
            self._save_ui_state()
            self.config.save()
        except Exception as e:
            print(f"Error saving UI state: {e}")

    def _on_video_llm_provider_changed(self, provider_name: str, model_name: str):
        """Handle LLM provider change from Video tab."""
        if hasattr(self, 'llm_provider_combo'):
            # Set flag to prevent circular updates
            self._updating_llm_provider = True

            # Sync with Image tab LLM provider combo
            self.llm_provider_combo.blockSignals(True)
            index = self.llm_provider_combo.findText(provider_name)
            if index >= 0:
                self.llm_provider_combo.setCurrentIndex(index)
                # Manually trigger the provider change to populate models
                self.llm_model_combo.blockSignals(True)
                self.llm_model_combo.clear()

                if provider_name != "None":
                    self.llm_model_combo.setEnabled(True)
                    # Populate with actual models for provider
                    if provider_name == "OpenAI":
                        self.llm_model_combo.addItems(["gpt-5-chat-latest", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"])
                    elif provider_name == "Claude":
                        self.llm_model_combo.addItems(["claude-opus-4.1", "claude-opus-4", "claude-sonnet-4", "claude-3.7-sonnet", "claude-3.5-sonnet", "claude-3.5-haiku"])
                    elif provider_name == "Gemini":
                        self.llm_model_combo.addItems(["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-pro"])
                    elif provider_name == "Ollama":
                        self.llm_model_combo.addItems(["llama2", "mistral", "mixtral", "phi-2", "neural-chat"])
                    elif provider_name == "LM Studio":
                        self.llm_model_combo.addItems(["local-model", "custom-model"])
                else:
                    self.llm_model_combo.setEnabled(False)

                self.llm_model_combo.blockSignals(False)

            self.llm_provider_combo.blockSignals(False)

            # Set the specific model if provided
            if model_name and hasattr(self, 'llm_model_combo'):
                self.llm_model_combo.blockSignals(True)
                model_index = self.llm_model_combo.findText(model_name)
                if model_index >= 0:
                    self.llm_model_combo.setCurrentIndex(model_index)
                self.llm_model_combo.blockSignals(False)

            # Clear flag
            self._updating_llm_provider = False

    def _on_video_image_provider_changed(self, provider_name: str):
        """Handle image provider change from Video tab."""
        if provider_name and provider_name != self.current_provider:
            # Update the current provider
            self.current_provider = provider_name
            self.config.set("provider", provider_name)
            self.config.save()

            # Update API key for new provider
            self.current_api_key = self.config.get_api_key(provider_name)

            # Sync with Image tab provider combo
            if hasattr(self, 'image_provider_combo'):
                self.image_provider_combo.blockSignals(True)
                self.image_provider_combo.setCurrentText(provider_name)
                self.image_provider_combo.blockSignals(False)

            # Sync with Settings tab provider combo
            if hasattr(self, 'provider_combo'):
                self.provider_combo.blockSignals(True)
                self.provider_combo.setCurrentText(provider_name)
                self.provider_combo.blockSignals(False)

            # Update model list for new provider
            self._update_model_list()

            # Update settings visibility
            self._update_advanced_visibility()

    def _on_image_provider_changed(self, provider_name: str):
        """Handle provider selection change on Image tab."""
        if provider_name and provider_name != self.current_provider:
            self.current_provider = provider_name
            # Update the config
            self.config.set("provider", provider_name)
            self.config.save()

            # Update API key for new provider
            self.current_api_key = self.config.get_api_key(provider_name)

            # Update model list for new provider
            self._update_model_list()

            # Show status but don't preload - it will load on first use
            self.status_bar.showMessage(f"Image provider changed to {provider_name}")

            # Sync with Settings tab provider combo
            if hasattr(self, 'provider_combo'):
                self.provider_combo.blockSignals(True)
                self.provider_combo.setCurrentText(provider_name)
                self.provider_combo.blockSignals(False)

            # Sync with Video tab if it's loaded
            if self._video_tab_loaded and hasattr(self.tab_video, 'set_provider'):
                self.tab_video.set_provider(provider_name)

            # Update settings visibility
            self._update_advanced_visibility()

            # Don't change aspect ratio or resolution when switching providers
            # Google Gemini (Nano Banana) now supports aspect ratios via the prompt
            if hasattr(self, 'aspect_selector') and self.aspect_selector:
                self.aspect_selector.setEnabled(True)
                self.aspect_selector.setToolTip("Aspect ratio is preserved across provider changes")

            # Update reference image availability based on provider
            # Currently only Google Gemini supports reference images
            if hasattr(self, 'btn_select_ref_image'):
                is_google = provider_name == "google"
                self.btn_select_ref_image.setEnabled(is_google)
                if is_google:
                    self.btn_select_ref_image.setToolTip("Choose a starting image for generation (Google Gemini)")
                else:
                    self.btn_select_ref_image.setToolTip(f"Reference images not supported by {provider_name} provider")

            # Preload the new provider
            auth_mode_internal = self.config.get("auth_mode", "api-key")
            if auth_mode_internal in ["api_key", "API Key"]:
                auth_mode_internal = "api-key"
            elif auth_mode_internal == "Google Cloud Account":
                auth_mode_internal = "gcloud"

            provider_config = {
                "api_key": self.current_api_key,
                "auth_mode": auth_mode_internal
            }
            preload_provider(self.current_provider, provider_config)

            # Update new widgets if available
            if hasattr(self, 'resolution_selector') and self.resolution_selector:
                self.resolution_selector.update_provider(self.current_provider)
            if hasattr(self, 'quality_selector') and self.quality_selector:
                self.quality_selector.update_provider(self.current_provider)
            if hasattr(self, 'advanced_panel') and self.advanced_panel:
                self.advanced_panel.update_provider(self.current_provider)

    def _on_model_changed(self, model_name: str):
        """Handle model selection change."""
        if self.current_provider == "local_sd" and hasattr(self, 'steps_spin'):
            # Auto-adjust for Turbo models
            if 'turbo' in model_name.lower():
                self.steps_spin.setValue(2)  # 1-4 steps for turbo
                self.guidance_spin.setValue(0.0)  # No CFG for turbo
                # Set resolution to 1024x1024 for SDXL turbo
                if 'sdxl' in model_name.lower():
                    idx = self.resolution_combo.findText("1024x1024", Qt.MatchContains)
                    if idx >= 0:
                        self.resolution_combo.setCurrentIndex(idx)
    
    def _on_provider_changed(self, provider: str):
        """Handle provider change from Settings tab."""
        self.current_provider = provider.lower()
        self.config.set("provider", self.current_provider)
        self.config.save()

        # Show status but don't preload - it will load on first use
        self.status_bar.showMessage(f"Image provider changed to {self.current_provider}")

        # Sync with Image tab provider combo
        if hasattr(self, 'image_provider_combo'):
            self.image_provider_combo.blockSignals(True)
            self.image_provider_combo.setCurrentText(self.current_provider)
            self.image_provider_combo.blockSignals(False)

        # Sync with Video tab if it's loaded
        if self._video_tab_loaded and hasattr(self.tab_video, 'set_provider'):
            self.tab_video.set_provider(self.current_provider)

        # Don't preload provider here - it will be loaded when actually used

        # Update new widgets if available
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            self.resolution_selector.update_provider(self.current_provider)
        if hasattr(self, 'quality_selector') and self.quality_selector:
            self.quality_selector.update_provider(self.current_provider)
        if hasattr(self, 'advanced_panel') and self.advanced_panel:
            self.advanced_panel.update_provider(self.current_provider)

        # All providers now support aspect ratios including Google Gemini
        if hasattr(self, 'aspect_selector') and self.aspect_selector:
            self.aspect_selector.setEnabled(True)
            self.aspect_selector.setToolTip("Aspect ratio is preserved across provider changes")

        # Update model list for new provider
        self._update_model_list()
        
        # Update cost estimate
        self._update_cost_estimate()
        
        # Update API key field reference based on provider
        if self.current_provider == "google":
            self.api_key_edit = self.google_key_edit
            self.current_api_key = self.google_key_edit.text().strip()
        elif self.current_provider == "openai":
            self.api_key_edit = self.openai_key_edit
            self.current_api_key = self.openai_key_edit.text().strip()
        elif self.current_provider == "stability":
            self.api_key_edit = self.stability_key_edit
            self.current_api_key = self.stability_key_edit.text().strip()
        else:
            # For unknown providers or local_sd
            if not hasattr(self, '_dummy_key_edit'):
                self._dummy_key_edit = QLineEdit(self)  # Add parent to prevent popup
                self._dummy_key_edit.setVisible(False)
            self.api_key_edit = self._dummy_key_edit
            self.current_api_key = self.config.get_api_key(self.current_provider) or ""
        
        # Update auth visibility
        self._update_auth_visibility()
        
        # Update Local SD widget visibility
        if hasattr(self, 'local_sd_widget') and self.local_sd_widget:
            # Get the parent group box if it exists
            parent = self.local_sd_widget.parent()
            if parent and isinstance(parent, QGroupBox):
                parent.setVisible(self.current_provider == "local_sd")
            else:
                self.local_sd_widget.setVisible(self.current_provider == "local_sd")
    
    def _on_aspect_ratio_changed(self, ratio: str):
        """Handle aspect ratio change."""
        logger.info(f"ASPECT RATIO CHANGED EVENT: {ratio}")
        # Store for use in generation
        self.current_aspect_ratio = ratio
        # Save to config
        self.config.config['last_aspect_ratio'] = ratio
        self.config.save()
        # When aspect ratio changes, switch resolution selector to auto mode
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            self.resolution_selector.set_mode_aspect_ratio()
        # Could update resolution options based on aspect ratio
        # Update upscaling visibility
        self._update_upscaling_visibility()
        self._update_cost_estimate()
        # Update the "Will insert" preview to show resolution
        self._update_ref_instruction_preview()
    
    def _on_resolution_changed(self, resolution: str):
        """Handle resolution change."""
        self.current_resolution = resolution
        # Save resolution settings including custom width/height
        if hasattr(self, 'resolution_selector'):
            width, height = self.resolution_selector.get_width_height()
            if width and height:
                self.config.config['last_resolution_width'] = width
                self.config.config['last_resolution_height'] = height
                self.config.save()
        self._update_cost_estimate()
        self._update_upscaling_visibility()
        # Update the "Will insert" preview to show resolution
        self._update_ref_instruction_preview()
    
    def _on_resolution_mode_changed(self, mode: str):
        """Handle resolution mode change (aspect_ratio vs resolution)."""
        # When user manually selects a resolution, clear aspect ratio selection
        if mode == "resolution" and hasattr(self, 'aspect_selector') and self.aspect_selector:
            # Don't trigger aspect ratio change when switching to resolution mode
            # Just visually uncheck all aspect ratio buttons
            for button in self.aspect_selector.buttons.values():
                button.setChecked(False)
            if hasattr(self.aspect_selector, 'custom_button'):
                self.aspect_selector.custom_button.setChecked(False)
                self.aspect_selector._show_custom_input(False)
    
    def _on_quality_settings_changed(self, settings: dict):
        """Handle quality/style settings change."""
        self.quality_settings = settings
        self._update_cost_estimate()
    
    def _on_advanced_settings_changed(self, settings: dict):
        """Handle advanced settings change."""
        self.advanced_settings = settings
    
    def _update_cost_estimate(self, num_images: int = None):
        """Update cost estimate display."""
        if not CostEstimator or not hasattr(self, 'batch_selector'):
            return
        
        # Gather all settings
        settings = {}
        
        # Get number of images
        if num_images is None and self.batch_selector:
            num_images = self.batch_selector.get_num_images()
        settings["num_images"] = num_images or 1
        
        # Get resolution
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            settings["resolution"] = self.resolution_selector.get_resolution()
        
        # Get quality settings
        if hasattr(self, 'quality_settings'):
            settings.update(self.quality_settings)
        
        # Calculate cost
        cost = CostEstimator.calculate(self.current_provider, settings)
        
        # Update batch selector display
        if self.batch_selector:
            self.batch_selector.set_cost_per_image(cost / settings["num_images"])
        
        # Show/hide appropriate widgets based on provider
        if self.current_provider == "local_sd":
            if hasattr(self, 'api_key_widget'):
                self.api_key_widget.setVisible(False)
            if hasattr(self, 'local_sd_widget') and self.local_sd_widget:
                self.local_sd_widget.setVisible(True)
        else:
            if hasattr(self, 'api_key_widget'):
                self.api_key_widget.setVisible(True)
                self.api_key_edit.setPlaceholderText("Enter API key...")
                self.api_key_edit.setEnabled(True)
            if hasattr(self, 'local_sd_widget') and self.local_sd_widget:
                self.local_sd_widget.setVisible(False)
        
        # Update model list
        self._update_model_list()
        
        # Update advanced settings visibility
        self._update_advanced_visibility()
    
    def _open_api_key_page(self):
        """Open API key documentation page."""
        from core import get_api_key_url
        url = get_api_key_url(self.current_provider)
        
        if self.current_provider == "local_sd":
            # Local SD widget is embedded, no need for separate dialog
            return
        elif url:
            try:
                webbrowser.open(url)
            except Exception as e:
                QMessageBox.warning(self, APP_NAME, f"Could not open browser: {e}")
        else:
            QMessageBox.warning(self, APP_NAME, 
                f"No API key URL available for {self.current_provider}")
    
    def _open_model_browser(self):
        """Open the model browser dialog for Local SD."""
        if not ModelBrowserDialog:
            QMessageBox.warning(self, APP_NAME, 
                "Model browser not available. Please ensure all dependencies are installed.")
            return
            
        try:
            # Get cache directory from config or use default
            cache_dir = Path.home() / ".cache" / "huggingface"
            
            # Create and show model browser
            dialog = ModelBrowserDialog(self, cache_dir)
            result = dialog.exec()
            
            if result == QDialog.Accepted:
                # Refresh model list after potential downloads
                self._update_model_list()
                if hasattr(self, 'status_bar'):
                    self.status_bar.showMessage("Model browser closed", 3000)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Could not open model browser: {e}")
    
    def _save_and_test(self):
        """Save API key and test connection."""
        key = self.api_key_edit.text().strip()
        
        # Local SD doesn't need an API key
        if self.current_provider == "local_sd":
            key = ""
        elif not key:
            QMessageBox.warning(self, APP_NAME, "Please enter an API key.")
            return
        
        # Save key
        self.config.set_api_key(self.current_provider, key)
        self.config.save()
        self.current_api_key = key
        
        # Test connection
        try:
            provider_config = {"api_key": key}
            provider = get_provider(self.current_provider, provider_config)
            is_valid, message = provider.validate_auth()
            
            if is_valid:
                QMessageBox.information(self, APP_NAME, f"API key saved and validated!\n{message}")
            else:
                QMessageBox.warning(self, APP_NAME, f"API key test failed:\n{message}")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Error testing API key:\n{str(e)}")
    
    def _toggle_auto_copy(self, checked: bool):
        """Toggle auto-copy filename setting."""
        self.auto_copy_filename = checked
        self.config.set("auto_copy_filename", checked)
        self.config.save()
    
    def _update_auth_visibility(self):
        """Update visibility of auth-related widgets based on provider and auth mode."""
        is_google = self.current_provider == "google"
        is_gcloud_auth = self.auth_mode_combo.currentText() == "Google Cloud Account"
        
        # Show auth mode only for Google provider
        self.auth_mode_combo.setVisible(is_google)
        
        # Show Google Cloud fields only for Google Cloud Account auth mode
        show_gcloud = is_google and is_gcloud_auth
        self.project_id_edit.setVisible(show_gcloud)
        self.gcloud_status_label.setVisible(show_gcloud)
        self.gcloud_help_widget.setVisible(show_gcloud)
        
        # Show API key fields for API Key mode or non-Google providers
        show_api_key = (not is_google or not is_gcloud_auth) and self.current_provider != "local_sd"
        self.api_key_widget.setVisible(show_api_key)
        self.config_location_widget.setVisible(show_api_key)
    
    def _on_auth_mode_changed(self, auth_mode: str):
        """Handle auth mode change."""
        # Map display text to internal auth mode value
        auth_mode_internal = "gcloud" if auth_mode == "Google Cloud Account" else "api-key"
        self.config.set("auth_mode", auth_mode_internal)
        self._update_auth_visibility()
        
        # Only check status if switching to Google Cloud Account and no cached auth
        if auth_mode == "Google Cloud Account":
            if not self.config.get("gcloud_auth_validated", False):
                self._check_gcloud_status()
    
    def _check_gcloud_status(self):
        """Check Google Cloud CLI status and credentials."""
        try:
            # Import the functions from gcloud_utils
            from core.gcloud_utils import check_gcloud_auth_status, get_gcloud_project_id
            
            # Use the exact same functions as the original
            is_auth, status_msg = check_gcloud_auth_status()
            
            if is_auth:
                # Get project ID
                project_id = get_gcloud_project_id()
                if project_id:
                    self.project_id_edit.setText(project_id)
                    self.gcloud_status_label.setText("✓ Authenticated")
                    self.gcloud_status_label.setStyleSheet("color: green;")
                else:
                    self.project_id_edit.setText("")
                    self.gcloud_status_label.setText("✓ Authenticated (no project)")
                    self.gcloud_status_label.setStyleSheet("color: orange;")
                
                # Save the auth validation status
                self.config.set("gcloud_auth_validated", True)
                if project_id:
                    self.config.set("gcloud_project_id", project_id)
                self.config.save()
            else:
                self.project_id_edit.setText("")
                # Show the status message from check_gcloud_auth_status
                if len(status_msg) > 50:
                    # Truncate long messages for the status label
                    self.gcloud_status_label.setText("✗ Not authenticated")
                else:
                    self.gcloud_status_label.setText(f"✗ {status_msg}")
                self.gcloud_status_label.setStyleSheet("color: red;")
                
                # Clear cached auth validation
                self.config.set("gcloud_auth_validated", False)
                self.config.set("gcloud_project_id", "")
                self.config.save()
                
        except Exception as e:
            self.project_id_edit.setText("")
            self.gcloud_status_label.setText(f"✗ Error: {str(e)[:50]}")
            self.gcloud_status_label.setStyleSheet("color: red;")
    
    def _authenticate_gcloud(self):
        """Run gcloud auth application-default login."""
        try:
            # Clear any cached validation before authenticating
            self.config.set("gcloud_auth_validated", False)
            self.config.save()
            
            # Show progress dialog
            msg = QMessageBox(self)
            msg.setWindowTitle(APP_NAME)
            msg.setText("Starting Google Cloud authentication...")
            msg.setInformativeText("A browser window will open for authentication.\nPlease complete the login process.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setIcon(QMessageBox.Information)
            
            # Start authentication in background
            import subprocess
            import platform
            
            gcloud_cmd = "gcloud.cmd" if platform.system() == "Windows" else "gcloud"
            
            # Open the auth URL in browser
            try:
                subprocess.Popen([gcloud_cmd, "auth", "application-default", "login"])
                msg.exec()
                
                # After user closes dialog, check status
                QTimer.singleShot(1000, self._check_gcloud_status)
                
            except FileNotFoundError:
                QMessageBox.critical(self, APP_NAME, 
                    "Google Cloud CLI not found.\n\n"
                    "Please install it from:\n"
                    "https://cloud.google.com/sdk/docs/install")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Authentication failed:\n{str(e)}")
                
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Error starting authentication:\n{str(e)}")
    
    def _on_project_id_changed(self):
        """Handle project ID edit changes."""
        project_id = self.project_id_edit.text().strip()
        
        # Save the project ID
        if project_id:
            self.config.set("gcloud_project_id", project_id)
        else:
            # If empty, try to detect from gcloud config
            try:
                from core.gcloud_utils import get_gcloud_project_id
                detected_id = get_gcloud_project_id()
                if detected_id:
                    self.project_id_edit.setText(detected_id)
                    project_id = detected_id
                    self.config.set("gcloud_project_id", project_id)
            except:
                pass
        
        self.config.save()
        
        # Update status if we have a project ID
        if project_id:
            self.gcloud_status_label.setText(f"Project: {project_id}")
            self.gcloud_status_label.setStyleSheet("color: blue;")
    
    def _open_gcloud_cli_page(self):
        """Open Google Cloud CLI download page."""
        webbrowser.open("https://cloud.google.com/sdk/docs/install")
    
    def _open_cloud_console(self):
        """Open Google Cloud Console."""
        webbrowser.open("https://console.cloud.google.com/")
    
    def _show_login_help(self):
        """Show help for Google Cloud login."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Google Cloud Login Help")
        msg.setText("""To authenticate with Google Cloud:

1. Install Google Cloud CLI from: https://cloud.google.com/sdk

2. Open a terminal/command prompt and run:
   gcloud auth application-default login

3. Follow the browser prompts to authenticate

4. Optionally set a default project:
   gcloud config set project YOUR_PROJECT_ID

5. Click 'Check Status' to verify authentication""")
        msg.exec()
    
    def _enhance_prompt(self):
        """Enhance the current prompt using the selected LLM."""
        # Get current prompt
        current_prompt = self.prompt_edit.toPlainText().strip()
        if not current_prompt:
            QMessageBox.information(self, "No Prompt",
                                   "Please enter a prompt to enhance.")
            return

        # Use the new enhanced prompt dialog
        from gui.enhanced_prompt_dialog import EnhancedPromptDialog

        dialog = EnhancedPromptDialog(self, self.config, current_prompt)
        dialog.promptEnhanced.connect(self._on_prompt_enhanced)
        dialog.exec()

    def _on_prompt_enhanced(self, enhanced_prompt):
        """Handle the enhanced prompt from the dialog."""
        if enhanced_prompt:
            self.prompt_edit.setPlainText(enhanced_prompt)
            self._append_to_console("Prompt enhanced successfully!", "#00ff00")  # Green


    def _open_examples(self):
        """Open examples dialog."""
        dlg = ExamplesDialog(self)
        if dlg.exec():
            prompt = dlg.get_selected_prompt()
            if prompt:
                if dlg.append_to_prompt and self.prompt_edit.toPlainText():
                    current = self.prompt_edit.toPlainText()
                    self.prompt_edit.setPlainText(f"{current}\n{prompt}")
                else:
                    self.prompt_edit.setPlainText(prompt)

    def _open_prompt_generator(self):
        """Open prompt generation dialog."""
        dlg = PromptGenerationDialog(self, self.config)
        dlg.promptSelected.connect(self.prompt_edit.setPlainText)
        dlg.exec()

    def _open_prompt_question(self):
        """Open prompt question dialog."""
        current_prompt = self.prompt_edit.toPlainText().strip()
        if not current_prompt:
            QMessageBox.warning(self, APP_NAME, "Please enter a prompt first.")
            return

        dlg = PromptQuestionDialog(self, self.config, current_prompt)
        dlg.exec()

    def _open_find_dialog(self):
        """Open find dialog for prompt text."""
        if not hasattr(self, '_find_dialog') or not self._find_dialog:
            self._find_dialog = FindDialog(self, self.prompt_edit)
        self._find_dialog.show()
        self._find_dialog.raise_()
        self._find_dialog.activateWindow()

    def _on_upscaling_changed(self, settings: dict):
        """Handle upscaling settings change."""
        self.upscaling_settings = settings
        # Save upscaling settings to config
        self.config.config['upscaling_settings'] = settings
        self.config.save()
        self._update_cost_estimate()

    def _get_target_resolution(self) -> tuple:
        """Get target resolution from UI settings."""
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            resolution = self.resolution_selector.get_resolution()
            if resolution and 'x' in resolution and resolution != 'auto':
                try:
                    width, height = map(int, resolution.split('x'))
                    return width, height
                except:
                    pass
        return None, None

    def test_dimension_logic(self):
        """Test function to verify dimension and upscaling logic."""
        print("\n=== Testing Dimension and Upscaling Logic ===\n")

        if not hasattr(self, 'resolution_selector'):
            print("ERROR: No resolution selector found")
            return

        # Test cases for each provider
        test_cases = [
            # (provider, aspect_ratio, width, height, expected_show_upscaling)
            ("google", "16:9", 1024, 0, False),  # 1024x576 - no upscaling
            ("google", "16:9", 2048, 0, True),   # 2048x1152 - needs upscaling
            ("google", "16:9", 0, 1152, True),   # 2048x1152 - needs upscaling
            ("google", "1:1", 1024, 0, False),   # 1024x1024 - no upscaling
            ("google", "1:1", 1025, 0, True),    # 1025x1025 - needs upscaling
            ("openai", "16:9", 1792, 0, False),  # 1792x1008 - no upscaling
            ("openai", "16:9", 1793, 0, True),   # 1793x1008 - needs upscaling
            ("openai", "9:16", 0, 1792, False),  # 1008x1792 - no upscaling
            ("openai", "9:16", 0, 1793, True),   # 1008x1793 - needs upscaling
        ]

        for provider, aspect_ratio, width, height, expected in test_cases:
            # Set provider
            self.current_provider = provider
            self.resolution_selector.update_provider(provider)

            # Set aspect ratio
            if hasattr(self, 'aspect_selector'):
                self.aspect_selector.set_ratio(aspect_ratio)
            self.resolution_selector._aspect_ratio = aspect_ratio

            # Set dimensions - only set the primary one
            if width > 0:
                self.resolution_selector._last_edited = "width"
                self.resolution_selector.width_spin.setValue(width)
            else:
                self.resolution_selector._last_edited = "height"
                self.resolution_selector.height_spin.setValue(height)

            # Wait for signals to propagate
            QApplication.processEvents()

            # Get results
            calc_w, calc_h = self.resolution_selector.get_width_height()
            visible = self.upscaling_selector.isVisible()

            # Check
            result = "✓" if visible == expected else "✗"
            print(f"{result} Provider: {provider:8} AR: {aspect_ratio:5} Input: W={width:4} H={height:4} → "
                  f"Calculated: {calc_w}x{calc_h} Upscaling: {visible} (expected: {expected})")

        print("\n=== Test Complete ===\n")

    def _update_upscaling_visibility(self):
        """Update upscaling selector visibility based on current settings."""
        if not hasattr(self, 'upscaling_selector'):
            return

        logger.info("=" * 60)
        logger.info("UPSCALING VISIBILITY CHECK")

        # Get target dimensions from resolution selector
        target_width = target_height = None

        if hasattr(self, 'resolution_selector'):
            width, height = self.resolution_selector.get_width_height()
            if width and height:
                target_width, target_height = width, height
                aspect_ratio = self.aspect_selector.get_ratio() if hasattr(self, 'aspect_selector') else "unknown"
                logger.info(f"Current aspect ratio: {aspect_ratio}")
                logger.info(f"Target dimensions: {target_width}×{target_height}px")

        if not (target_width and target_height):
            logger.info("No dimensions available - hiding upscaling widget")
            self.upscaling_selector.setVisible(False)
            logger.info("=" * 60)
            return

        # Get provider maximum resolution
        provider_max = 1024  # Default
        if self.current_provider == "google":
            provider_max = 1024
        elif self.current_provider == "openai":
            provider_max = 1792
        elif self.current_provider == "stability":
            provider_max = 1536

        logger.info(f"Provider: {self.current_provider} (max: {provider_max}px)")

        # RULE: Show upscaling if EITHER dimension > provider max
        needs_upscaling = target_width > provider_max or target_height > provider_max

        logger.info(f"  Width check: {target_width} > {provider_max}? {target_width > provider_max}")
        logger.info(f"  Height check: {target_height} > {provider_max}? {target_height > provider_max}")
        logger.info(f"  Needs upscaling: {needs_upscaling}")

        old_visibility = self.upscaling_selector.isVisible()
        self.upscaling_selector.setVisible(needs_upscaling)

        if old_visibility != needs_upscaling:
            logger.info(f"UPSCALING WIDGET VISIBILITY CHANGED: {old_visibility} → {needs_upscaling}")
        logger.info("=" * 60)

        if needs_upscaling:
            # Calculate what the provider will actually output
            if self.current_provider == "google":
                # Google outputs 1024x1024 then crops to aspect
                expected_width = expected_height = 1024
                if target_width != target_height:
                    aspect = target_width / target_height
                    if aspect > 1:
                        expected_height = int(1024 / aspect)
                    else:
                        expected_width = int(1024 * aspect)
            else:
                # Other providers output at their max, maintaining aspect
                scale = min(provider_max / target_width, provider_max / target_height)
                expected_width = int(target_width * scale)
                expected_height = int(target_height * scale)

            self.upscaling_selector.update_resolution_info(
                expected_width, expected_height,
                target_width, target_height
            )

    def _generate(self):
        """Generate image from prompt."""
        # Add separator for new generation
        self._append_to_console("", is_separator=True)
        self._append_to_console("Starting image generation...", "#00ff00")  # Green

        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            self._append_to_console("ERROR: No prompt provided", "#ff6666")  # Red
            QMessageBox.warning(self, APP_NAME, "Please enter a prompt.")
            return

        # Store original prompt (before reference image modifications)
        original_prompt = prompt

        if not self.current_api_key and self.current_provider != "local_sd":
            self._append_to_console("ERROR: No API key configured", "#ff6666")  # Red
            QMessageBox.warning(self, APP_NAME, "Please set an API key in Settings.")
            return

        # Log generation details
        self._append_to_console(f"Provider: {self.current_provider}", "#66ccff")  # Blue
        self._append_to_console(f"Prompt: {prompt}", "#888888")  # Gray

        # Disable/reset buttons
        self.btn_generate.setEnabled(False)
        self.btn_save_image.setEnabled(False)
        self.btn_copy_image.setEnabled(False)
        self.btn_toggle_original.setEnabled(False)
        self.btn_toggle_original.setVisible(False)
        self.status_label.setText("Generating...")
        self.output_image_label.clear()
        self.current_image_data = None
        
        # Get current model
        # Get the actual model ID from the combo box data
        model = self.model_combo.currentData()
        if not model:
            # Fallback to text if no data is stored (for backward compatibility)
            model = self.model_combo.currentText()
        
        # Gather all generation parameters
        kwargs = {}

        # Store target resolution for later processing
        self.target_resolution = None

        # Get resolution or aspect ratio settings based on which mode is active
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            if self.resolution_selector.is_using_aspect_ratio():
                # Using aspect ratio mode - send aspect ratio
                if hasattr(self, 'aspect_selector') and self.aspect_selector:
                    aspect_ratio = self.aspect_selector.get_ratio()
                    kwargs['aspect_ratio'] = aspect_ratio
                    # Enable cropping for Google provider when aspect ratio is selected
                    if self.current_provider == "google":
                        kwargs['crop_to_aspect'] = True

                    # For non-Google providers, provide resolution string for proper size mapping
                    if self.current_provider != "google":
                        # Map aspect ratios to appropriate resolutions per provider
                        resolution_map = self._get_resolution_for_aspect_ratio(aspect_ratio, self.current_provider)
                        if resolution_map:
                            kwargs['resolution'] = resolution_map

                        # Store target for potential scaling/cropping later
                        if hasattr(self.resolution_selector, 'get_width_height'):
                            width, height = self.resolution_selector.get_width_height()
                            if width and height:
                                self.target_resolution = (width, height)
                    else:
                        # For Google, ALWAYS get width/height for any aspect ratio
                        # This ensures dimensions are sent when resolution != 1024x1024
                        width = height = None
                        if hasattr(self.resolution_selector, 'get_width_height'):
                            width, height = self.resolution_selector.get_width_height()

                        # If no width/height from selector, calculate from aspect ratio
                        if not width or not height:
                            # Try to get resolution from selector
                            resolution = self.resolution_selector.get_resolution() if hasattr(self.resolution_selector, 'get_resolution') else None
                            if resolution and 'x' in resolution:
                                width, height = map(int, resolution.split('x'))
                            elif aspect_ratio:
                                # Calculate dimensions based on aspect ratio
                                if aspect_ratio == '16:9':
                                    width, height = 1024, 576
                                elif aspect_ratio == '9:16':
                                    width, height = 576, 1024
                                elif aspect_ratio == '4:3':
                                    width, height = 1024, 768
                                elif aspect_ratio == '3:4':
                                    width, height = 768, 1024
                                elif aspect_ratio == '21:9':
                                    width, height = 1024, 439
                                else:
                                    width, height = 1024, 1024

                        # Always pass dimensions for Google
                        if width:
                            kwargs['width'] = width
                        if height:
                            kwargs['height'] = height
            else:
                # Using explicit resolution mode
                width = height = None
                if hasattr(self.resolution_selector, 'get_width_height'):
                    width, height = self.resolution_selector.get_width_height()
                else:
                    resolution = self.resolution_selector.get_resolution()
                    if resolution and 'x' in resolution:
                        width, height = map(int, resolution.split('x'))

                if width and height:
                    # For non-Gemini providers, use closest aspect ratio and store target for scaling
                    if self.current_provider != "google":
                        self.target_resolution = (width, height)
                        closest_ar = self._find_closest_aspect_ratio(width, height, self.current_provider)
                        kwargs['aspect_ratio'] = closest_ar

                        # Inform user about aspect ratio matching
                        self._append_to_console(
                            f"Using aspect ratio {closest_ar} (closest to {width}x{height}), will scale to fit",
                            "#ffaa00"  # Orange for info
                        )

                        # For non-Google providers, provide resolution string for proper handling
                        resolution_map = self._get_resolution_for_aspect_ratio(closest_ar, self.current_provider)
                        if resolution_map:
                            kwargs['resolution'] = resolution_map
                        # Keep aspect_ratio for fallback - providers use it
                    else:
                        # Gemini: use exact dimensions
                        kwargs['width'] = width
                        kwargs['height'] = height
        elif hasattr(self, 'resolution_combo'):
            # Fallback to old resolution combo
            resolution_text = self.resolution_combo.currentText()
            if "512x512" in resolution_text:
                kwargs['width'] = 512
                kwargs['height'] = 512
            elif "768x768" in resolution_text:
                kwargs['width'] = 768
                kwargs['height'] = 768
            elif "1024x1024" in resolution_text:
                kwargs['width'] = 1024
                kwargs['height'] = 1024
            
            # Also check for old aspect selector
            if hasattr(self, 'aspect_selector') and self.aspect_selector:
                aspect_ratio = self.aspect_selector.get_ratio()
                kwargs['aspect_ratio'] = aspect_ratio
        
        # Get quality/style settings
        if hasattr(self, 'quality_selector') and self.quality_selector:
            quality_settings = self.quality_selector.get_settings()
            kwargs.update(quality_settings)
        
        # Get batch settings
        if hasattr(self, 'batch_selector') and self.batch_selector:
            num_images = self.batch_selector.get_num_images()
            kwargs['num_images'] = num_images
        
        # Get advanced settings
        if hasattr(self, 'advanced_panel') and self.advanced_panel:
            advanced_settings = self.advanced_panel.get_settings()
            kwargs.update(advanced_settings)
        elif self.current_provider == "local_sd":
            # Fallback to old advanced settings for local_sd
            if hasattr(self, 'steps_spin'):
                kwargs['steps'] = self.steps_spin.value()
            if hasattr(self, 'guidance_spin'):
                kwargs['cfg_scale'] = self.guidance_spin.value()
        
        # Add reference image if enabled and available (Google Gemini only)
        if (self.current_provider == "google" and
            hasattr(self, 'reference_image_data') and
            self.reference_image_data and
            hasattr(self, 'ref_image_enabled') and
            self.ref_image_enabled.isChecked()):
            kwargs['reference_image'] = self.reference_image_data

            # Build and prepend instruction to prompt
            style = self.ref_style_combo.currentText() if hasattr(self, 'ref_style_combo') else "Natural blend"
            position = self.ref_position_combo.currentText() if hasattr(self, 'ref_position_combo') else "Auto"

            instruction_parts = []
            if position != "Auto":
                instruction_parts.append(f"Attached photo on the {position.lower()}")
            else:
                instruction_parts.append("Attached photo")

            style_map = {
                "Natural blend": "naturally blended into the scene",
                "In center": "placed in the center",
                "Blurred edges": "with blurred edges",
                "In circle": "inside a circular frame",
                "In frame": "in a decorative frame",
                "Seamless merge": "seamlessly merged",
                "As background": "as the background",
                "As overlay": "as an overlay",
                "Split screen": "in split-screen style"
            }

            if style in style_map:
                instruction_parts.append(style_map[style])

            # Get resolution if available
            resolution_text = ""
            if 'width' in kwargs and 'height' in kwargs:
                width = kwargs['width']
                height = kwargs['height']

                # If using Google provider and resolution > 1024, calculate scaled dimensions
                if self.current_provider == 'google':
                    max_dim = max(width, height)
                    if max_dim > 1024:
                        scale_factor = 1024 / max_dim
                        scaled_width = int(width * scale_factor)
                        scaled_height = int(height * scale_factor)
                        resolution_text = f" (Image will be {scaled_width}x{scaled_height}, scale to fit.)"
                    else:
                        resolution_text = f" (Image will be {width}x{height}, scale to fit.)"
                else:
                    resolution_text = f" (Image will be {width}x{height}, scale to fit.)"

            # Build instruction and prepend to prompt for generation only
            instruction = f"{', '.join(instruction_parts)}.{resolution_text}"
            # Create modified prompt for generation (original_prompt already stored)
            prompt = f"{instruction} {prompt}"

            self._append_to_console(f"Using reference image: {self.reference_image_path.name if self.reference_image_path else 'Unknown'}", "#66ccff")
            self._append_to_console(f"Auto-inserted: \"{instruction}\"", "#9966ff")
        else:
            # No reference image, but check if we need to add resolution info
            if 'width' in kwargs and 'height' in kwargs:
                width = kwargs['width']
                height = kwargs['height']
                if width != 1024 or height != 1024:
                    # If using Google provider and resolution > 1024, calculate scaled dimensions
                    if self.current_provider == 'google':
                        max_dim = max(width, height)
                        if max_dim > 1024:
                            scale_factor = 1024 / max_dim
                            scaled_width = int(width * scale_factor)
                            scaled_height = int(height * scale_factor)
                            resolution_text = f"(Image will be {scaled_width}x{scaled_height}, scale to fit.)"
                        else:
                            resolution_text = f"(Image will be {width}x{height}, scale to fit.)"
                    else:
                        resolution_text = f"(Image will be {width}x{height}, scale to fit.)"
                    prompt = f"{resolution_text} {prompt}"
                    self._append_to_console(f"Auto-inserted: \"{resolution_text}\"", "#9966ff")

        # Show status for provider loading
        self.status_bar.showMessage(f"Connecting to {self.current_provider}...")
        self._append_to_console(f"Connecting to {self.current_provider}...", "#66ccff")  # Blue
        QApplication.processEvents()

        # Create worker thread
        self.gen_thread = QThread()
        # Get the actual auth mode from config
        auth_mode = "api-key"  # default
        if self.current_provider == "google":
            auth_mode_text = self.auth_mode_combo.currentText()
            if auth_mode_text == "Google Cloud Account":
                auth_mode = "gcloud"

        self.gen_worker = GenWorker(
            provider=self.current_provider,
            model=model,
            prompt=prompt,
            auth_mode=auth_mode,
            **kwargs
        )

        self.gen_worker.moveToThread(self.gen_thread)

        # Connect signals
        self.gen_thread.started.connect(self.gen_worker.run)
        self.gen_worker.progress.connect(self._on_progress)
        self.gen_worker.error.connect(self._on_error)
        self.gen_worker.finished.connect(self._on_generation_finished)

        # Start generation
        self.gen_thread.start()
        # Save the original prompt (not the modified one with reference image instructions)
        self.current_prompt = original_prompt
        self.current_model = model
    
    def _get_resolution_for_aspect_ratio(self, aspect_ratio: str, provider: str) -> str:
        """Get the appropriate resolution string for a given aspect ratio and provider."""
        # Provider-specific resolution mappings
        resolution_maps = {
            "openai": {
                "1:1": "1024x1024",
                "16:9": "1792x1024",
                "9:16": "1024x1792",
                "4:3": "1792x1024",  # Map to closest landscape
                "3:4": "1024x1792",  # Map to closest portrait
            },
            "stability": {
                "1:1": "1024x1024",
                "16:9": "1344x768",
                "9:16": "768x1344",
                "4:3": "1152x896",
                "3:4": "896x1152",
                "3:2": "1216x832",
                "2:3": "832x1216",
            },
            "local_sd": {
                "1:1": "512x512",
                "16:9": "768x432",
                "9:16": "432x768",
                "4:3": "512x384",
                "3:4": "384x512",
            }
        }

        provider_map = resolution_maps.get(provider, resolution_maps.get("openai"))
        return provider_map.get(aspect_ratio, "1024x1024")

    def _find_closest_aspect_ratio(self, target_width: int, target_height: int, provider: str) -> str:
        """Find the closest supported aspect ratio for the given resolution."""
        target_ratio = target_width / target_height

        # Define supported aspect ratios per provider
        aspect_ratios = {
            "google": ["1:1", "4:3", "3:4", "16:9", "9:16", "2:1", "1:2"],
            "openai": ["1:1", "16:9", "9:16"],  # DALL-E 3 only supports these
            "stability": ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
        }

        provider_ratios = aspect_ratios.get(provider, ["1:1"])

        # Convert aspect ratio strings to float values
        def parse_ratio(ratio_str):
            parts = ratio_str.split(":")
            return float(parts[0]) / float(parts[1])

        # Find closest ratio
        closest_ratio = None
        min_diff = float('inf')

        for ratio_str in provider_ratios:
            ratio_val = parse_ratio(ratio_str)
            diff = abs(ratio_val - target_ratio)
            if diff < min_diff:
                min_diff = diff
                closest_ratio = ratio_str

        return closest_ratio or "1:1"

    def _process_image_for_resolution_with_original(self, image_data: bytes):
        """Process image and return both original and processed if cropping occurred.

        Returns:
            - tuple(processed_bytes, original_bytes) if cropping was done
            - bytes if no processing was needed
        """
        # Skip processing for Gemini provider
        if self.current_provider == "google":
            return image_data

        # Get target resolution
        if hasattr(self, 'target_resolution') and self.target_resolution:
            target_width, target_height = self.target_resolution
        else:
            # Fallback to getting from UI if not stored
            target_width = None
            target_height = None

            # Check resolution selector
            if hasattr(self, 'resolution_selector') and self.resolution_selector:
                resolution_text = self.resolution_selector.get_resolution()
                # Parse resolution like "1024x1024"
                if 'x' in resolution_text:
                    try:
                        parts = resolution_text.split('x')
                        if len(parts) == 2:
                            target_width = int(parts[0])
                            target_height = int(parts[1])
                    except (ValueError, IndexError):
                        pass

        # If no valid resolution found, return original
        if not target_width or not target_height:
            return image_data

        try:
            from PIL import Image
            import io
            from PySide6.QtGui import QImage, QPixmap
            from PySide6.QtCore import QByteArray, QBuffer, QIODevice

            # Load image
            img = Image.open(io.BytesIO(image_data))
            original_width, original_height = img.size

            # Check if scaling is needed
            if original_width == target_width and original_height == target_height:
                return image_data

            # Convert PIL image to QImage properly
            img_rgba = img.convert("RGBA")
            data = img_rgba.tobytes("raw", "RGBA")
            bytes_per_line = 4 * original_width
            qimage = QImage(data, original_width, original_height, bytes_per_line, QImage.Format_RGBA8888)
            # Need to copy the data since QImage doesn't own it
            qimage = qimage.copy()

            # Scale to target width
            scale_factor = target_width / original_width
            scaled_height = int(original_height * scale_factor)

            # Scale the image
            scaled_qimage = qimage.scaled(
                target_width, scaled_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # Save scaled version (before potential cropping)
            scaled_bytes = QByteArray()
            scaled_buffer = QBuffer(scaled_bytes)
            scaled_buffer.open(QIODevice.WriteOnly)
            scaled_qimage.save(scaled_buffer, "PNG")
            scaled_data = bytes(scaled_bytes)

            # Check if cropping is needed
            if scaled_height != target_height:
                # Show crop dialog
                dialog = ImageCropDialog(scaled_qimage, target_width, target_height, self)
                if dialog.exec() == QDialog.Accepted:
                    # Get cropped image
                    result_image = dialog.get_result()

                    # Convert cropped QImage back to bytes
                    cropped_bytes = QByteArray()
                    cropped_buffer = QBuffer(cropped_bytes)
                    cropped_buffer.open(QIODevice.WriteOnly)
                    result_image.save(cropped_buffer, "PNG")

                    # Return both cropped and original scaled
                    return (bytes(cropped_bytes), scaled_data)
                else:
                    # User cancelled, use scaled image only
                    return scaled_data
            else:
                # No cropping needed
                return scaled_data

        except Exception as e:
            logger.error(f"Error processing image for resolution: {e}")
            self._append_to_console(f"Warning: Could not process image resolution: {e}", "#ffaa00")
            return image_data

    def _process_image_for_resolution(self, image_data: bytes) -> bytes:
        """Process image to match selected resolution (scaling/cropping)."""
        # Skip processing for Gemini provider
        if self.current_provider == "google":
            return image_data

        # Get target resolution
        if hasattr(self, 'target_resolution') and self.target_resolution:
            target_width, target_height = self.target_resolution
        else:
            # Fallback to getting from UI if not stored
            target_width = None
            target_height = None

            # Check resolution selector
            if hasattr(self, 'resolution_selector') and self.resolution_selector:
                resolution_text = self.resolution_selector.get_resolution()
                # Parse resolution like "1024x1024"
                if 'x' in resolution_text:
                    try:
                        parts = resolution_text.split('x')
                        if len(parts) == 2:
                            target_width = int(parts[0])
                            target_height = int(parts[1])
                    except (ValueError, IndexError):
                        pass

        # If no valid resolution found, return original
        if not target_width or not target_height:
            return image_data

        try:
            from PIL import Image
            import io
            from PySide6.QtGui import QImage, QPixmap
            from PySide6.QtCore import QByteArray, QBuffer, QIODevice

            # Load image
            img = Image.open(io.BytesIO(image_data))
            original_width, original_height = img.size

            # Check if scaling is needed
            if original_width == target_width and original_height == target_height:
                return image_data

            # Convert PIL image to QImage properly
            img_rgba = img.convert("RGBA")
            data = img_rgba.tobytes("raw", "RGBA")
            bytes_per_line = 4 * original_width
            qimage = QImage(data, original_width, original_height, bytes_per_line, QImage.Format_RGBA8888)
            # Need to copy the data since QImage doesn't own it
            qimage = qimage.copy()

            # Scale to target width
            scale_factor = target_width / original_width
            scaled_height = int(original_height * scale_factor)

            # Scale the image
            scaled_qimage = qimage.scaled(
                target_width, scaled_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # Check if cropping is needed
            if scaled_height != target_height:
                # Show crop dialog
                dialog = ImageCropDialog(scaled_qimage, target_width, target_height, self)
                if dialog.exec() == QDialog.Accepted:
                    # Get cropped image
                    result_image = dialog.get_result()
                else:
                    # User cancelled, use scaled image
                    result_image = scaled_qimage
            else:
                # No cropping needed
                result_image = scaled_qimage

            # Convert QImage back to bytes
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            result_image.save(buffer, "PNG")
            return bytes(byte_array)

        except Exception as e:
            logger.error(f"Error processing image for resolution: {e}")
            self._append_to_console(f"Warning: Could not process image resolution: {e}", "#ffaa00")
            return image_data

    def _on_progress(self, message: str):
        """Handle progress update."""
        self.status_label.setText(message)
        self.status_bar.showMessage(message)
        self._append_to_console(message, "#66ccff")  # Blue for progress

    def _on_error(self, error: str):
        """Handle generation error."""
        self.status_label.setText("Error occurred.")
        self.status_bar.showMessage(f"Error: {error[:50]}...")  # Show truncated error in status
        self._append_to_console(f"ERROR: {error}", "#ff6666")  # Red
        QMessageBox.critical(self, APP_NAME, f"Generation failed:\n{error}")
        self.btn_generate.setEnabled(True)
        self._cleanup_thread()

    def _on_generation_finished(self, texts: List[str], images: List[bytes]):
        """Handle successful generation."""
        self.status_label.setText("Generation complete.")
        self.status_bar.showMessage("Image generated successfully")
        self._append_to_console("Generation complete!", "#00ff00")  # Green

        # Log any text responses from the provider
        if texts:
            for text in texts:
                self._append_to_console(f"Response: {text}", "#ffff66")  # Yellow

        # Display and save images
        if images:
            self._append_to_console(f"Received {len(images)} image(s)", "#66ccff")

            # Process images for scaling/cropping if needed (non-Gemini providers only)
            processed_images = []
            original_paths = []

            for i, image_data in enumerate(images):
                processed_result = self._process_image_for_resolution_with_original(image_data)

                if isinstance(processed_result, tuple):
                    # Got both original and processed
                    processed_image, original_image = processed_result
                    processed_images.append(processed_image)

                    # Save original with _original suffix
                    stub = sanitize_stub_from_prompt(self.current_prompt)
                    original_stub = f"{stub}_original"
                    orig_paths = auto_save_images([original_image], base_stub=original_stub)
                    if orig_paths:
                        original_paths.append(orig_paths[0])
                else:
                    # Just processed image (no cropping needed)
                    processed_images.append(processed_result)
                    original_paths.append(None)

            # Apply upscaling if enabled and needed
            if hasattr(self, 'upscaling_settings') and self.upscaling_settings.get('enabled'):
                target_width, target_height = self._get_target_resolution()
                if target_width and target_height:
                    upscaled_images = []
                    for image_data in processed_images:
                        # Check if upscaling is needed
                        from PIL import Image
                        import io
                        from core.upscaling import needs_upscaling, upscale_image

                        img = Image.open(io.BytesIO(image_data))
                        if needs_upscaling(img.width, img.height, target_width, target_height):
                            self._append_to_console(
                                f"Upscaling from {img.width}x{img.height} to {target_width}x{target_height}...",
                                "#66ccff"
                            )
                            upscaled = upscale_image(
                                image_data,
                                target_width,
                                target_height,
                                method=self.upscaling_settings.get('method', 'lanczos'),
                                model_name=self.upscaling_settings.get('model_name'),
                                api_key=self.config.get_api_key('stability') if self.upscaling_settings.get('method') == 'stability_api' else None
                            )
                            upscaled_images.append(upscaled)
                        else:
                            upscaled_images.append(image_data)
                    processed_images = upscaled_images

            # Save processed images
            stub = sanitize_stub_from_prompt(self.current_prompt)
            saved_paths = auto_save_images(processed_images, base_stub=stub)

            if saved_paths:
                # Get dimensions of saved image
                try:
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(processed_images[0]))
                    width, height = img.width, img.height
                    self._append_to_console(f"Saved {width}×{height} image to: {saved_paths[0].name}", "#00ff00")
                except:
                    # Fallback if we can't get dimensions
                    self._append_to_console(f"Saved to: {saved_paths[0].name}", "#00ff00")
            
            # Calculate cost for this generation
            generation_cost = 0.0
            settings = {}
            settings["num_images"] = len(processed_images)

            # Get resolution from processed image data
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(processed_images[0]))
                settings["width"] = img.width
                settings["height"] = img.height
                settings["resolution"] = f"{img.width}x{img.height}"
            except:
                pass
            
            # Get quality/style settings if available
            if hasattr(self, 'quality_settings'):
                settings.update(self.quality_settings)
            
            # Calculate the cost if estimator is available
            if CostEstimator:
                try:
                    generation_cost = CostEstimator.calculate(self.current_provider, settings)
                except:
                    generation_cost = 0.0
            
            # Save metadata with cost
            for i, path in enumerate(saved_paths):
                meta = {
                    "prompt": self.current_prompt,
                    "provider": self.current_provider,
                    "model": self.current_model,
                    "timestamp": datetime.now().isoformat(),
                    "cost": generation_cost / len(images),  # Cost per image
                }
                
                # Add resolution info if we got it
                if 'width' in settings:
                    meta["width"] = settings["width"]
                    meta["height"] = settings["height"]
                
                # Add quality/style info
                if hasattr(self, 'quality_settings'):
                    meta.update(self.quality_settings)
                
                write_image_sidecar(path, meta)
            
            # Store original path references
            self.current_original_paths = original_paths
            self.current_saved_paths = saved_paths

            # Display first processed image
            self.current_image_data = processed_images[0]
            self._display_image(processed_images[0])
            if saved_paths:
                self._last_displayed_image_path = saved_paths[0]  # Track last displayed image

            # Enable toggle button if we have an original version
            if original_paths and original_paths[0]:
                self._enable_original_toggle(original_paths[0], saved_paths[0])
                self._append_to_console("Saved both cropped and original versions", "#66ccff")
            
            # Enable save/copy buttons
            self.btn_save_image.setEnabled(True)
            self.btn_copy_image.setEnabled(True)
            
            # Update history with the new generation
            # Use current filter setting
            show_all = hasattr(self, 'chk_show_all_images') and self.chk_show_all_images.isChecked()
            self.history_paths = scan_disk_history(project_only=not show_all)
            
            # Add to in-memory history for immediate display
            for i, path in enumerate(saved_paths):
                history_entry = {
                    'path': path,
                    'prompt': self.current_prompt,
                    'timestamp': datetime.now().isoformat(),
                    'model': self.current_model,
                    'provider': self.current_provider,
                    'cost': generation_cost / len(images) if generation_cost else 0.0
                }
                
                # Add resolution if available
                if 'width' in settings:
                    history_entry['width'] = settings['width']
                    history_entry['height'] = settings['height']
                
                # Add to history list
                self.history.append(history_entry)
            
            # Update history tab if it exists
            if hasattr(self, 'history_table'):
                self._refresh_history_table()
            
            # Copy filename if enabled
            if self.auto_copy_filename and saved_paths:
                try:
                    from PySide6.QtGui import QGuiApplication
                    clipboard = QGuiApplication.clipboard()
                    clipboard.setText(str(saved_paths[0]))
                    self.status_label.setText(f"Generated and saved to: {saved_paths[0].name} (copied)")
                except Exception:
                    self.status_label.setText(f"Generated and saved to: {saved_paths[0].name}")
        
        self.btn_generate.setEnabled(True)
        self._cleanup_thread()
    
    def _display_image(self, image_data: bytes):
        """Display image in the output label."""
        try:
            # TODO: Re-enable auto-crop after fixing the algorithm
            # Currently disabled as it's cropping incorrectly
            # # Apply auto-crop for Nano Banana images if available
            # try:
            #     from core.image_utils import auto_crop_solid_borders
            #     # Only auto-crop for Google provider (Nano Banana)
            #     if hasattr(self, 'current_provider') and self.current_provider == 'google':
            #         image_data = auto_crop_solid_borders(image_data)
            # except ImportError:
            #     pass  # image_utils not available, skip auto-crop

            pixmap = QPixmap()
            pixmap.loadFromData(image_data)

            # Get the label's current size
            label_size = self.output_image_label.size()

            # Ensure we have valid dimensions
            if label_size.width() <= 0 or label_size.height() <= 0:
                # Label not ready yet, schedule retry
                QTimer.singleShot(50, lambda: self._display_image(image_data))
                return

            # Scale to fit the label completely while maintaining aspect ratio
            # Use the full available space
            scaled = pixmap.scaled(
                label_size.width() - 4,  # Account for border
                label_size.height() - 4,  # Account for border
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.output_image_label.setPixmap(scaled)

            # Store the original pixmap for potential resizing
            self.output_image_label.setProperty("original_pixmap", pixmap)

            # Update current image data
            self.current_image_data = image_data

            # After layout settles, ensure the image scales to the final size
            # Schedule multiple resize attempts to handle various layout timing
            for delay in [50, 100, 200, 500]:
                try:
                    QTimer.singleShot(delay, self._perform_image_resize)
                except Exception:
                    pass
        except Exception as e:
            self.output_image_label.setText(f"Error displaying image: {e}")
    
    def _save_image_as(self):
        """Save current image with file dialog."""
        if not self.current_image_data:
            QMessageBox.warning(self, APP_NAME, "No image to save.")
            return
        
        # Determine extension
        ext = detect_image_extension(self.current_image_data)
        
        # Get save path
        default_name = f"{sanitize_stub_from_prompt(self.current_prompt)}{ext}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            str(Path.home() / default_name),
            f"Images (*{ext})"
        )
        
        if path:
            try:
                Path(path).write_bytes(self.current_image_data)
                QMessageBox.information(self, APP_NAME, f"Image saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Error saving image:\n{e}")
    
    def _copy_image_to_clipboard(self):
        """Copy current image to clipboard."""
        if not self.current_image_data:
            QMessageBox.warning(self, APP_NAME, "No image to copy.")
            return
        
        try:
            from PySide6.QtGui import QClipboard
            pixmap = QPixmap()
            pixmap.loadFromData(self.current_image_data)
            
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(pixmap)
            
            self.status_label.setText("Image copied to clipboard.")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Error copying image:\n{e}")
    
    def _cleanup_thread(self):
        """Clean up worker thread."""
        if self.gen_thread and self.gen_thread.isRunning():
            self.gen_thread.quit()
            self.gen_thread.wait()
        self.gen_thread = None
        self.gen_worker = None
    
    def _load_image_file(self, path: Path):
        """Load and display an image file."""
        try:
            if not path.exists():
                return
            
            # Read image data
            image_data = path.read_bytes()
            self.current_image_data = image_data
            self._last_displayed_image_path = path
            
            # Display the image
            self._display_image(image_data)
            
            # Enable save/copy buttons
            self.btn_save_image.setEnabled(True)
            self.btn_copy_image.setEnabled(True)
            
            # Try to load metadata if it exists
            json_path = path.with_suffix(path.suffix + ".json")
            if json_path.exists():
                try:
                    with open(json_path, 'r') as f:
                        metadata = json.load(f)
                        
                        # Restore prompt
                        if 'prompt' in metadata:
                            self.prompt_edit.setPlainText(metadata['prompt'])
                        
                        # Restore model
                        if 'model' in metadata:
                            idx = self._find_model_in_combo(metadata['model'])
                            if idx >= 0:
                                self.model_combo.setCurrentIndex(idx)
                        
                        # Don't restore provider - it's a persistent app setting
                        # The user's selected provider shouldn't change just because
                        # they're viewing an image made with a different provider
                except Exception:
                    pass  # Ignore metadata errors
            
            self.status_label.setText("Image loaded")
        except Exception as e:
            self.status_label.setText(f"Error loading image: {e}")
    
    def _save_project(self):
        """Save current project including image and all settings."""
        if not self.current_image_data:
            QMessageBox.warning(self, APP_NAME, "No image to save in project.")
            return
        
        # Get save path
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(Path.home() / "project.imgai"),
            "ImageAI Projects (*.imgai)"
        )
        
        if not path:
            return
        
        try:
            project_path = Path(path)
            
            # Create project data
            project_data = {
                'version': VERSION,
                'timestamp': datetime.now().isoformat(),
                'provider': self.current_provider,
                'model': self.model_combo.currentData() or self.model_combo.currentText(),
                'prompt': self.prompt_edit.toPlainText(),
                'ui_state': {}
            }
            
            # Add all UI state
            if hasattr(self, 'aspect_selector') and self.aspect_selector:
                project_data['ui_state']['aspect_ratio'] = self.aspect_selector.get_ratio()
            
            if hasattr(self, 'resolution_selector') and self.resolution_selector:
                project_data['ui_state']['resolution'] = self.resolution_selector.get_resolution()
            elif hasattr(self, 'resolution_combo'):
                project_data['ui_state']['resolution_combo_index'] = self.resolution_combo.currentIndex()
            
            if hasattr(self, 'quality_selector') and self.quality_selector:
                project_data['ui_state']['quality_settings'] = self.quality_selector.get_settings()
            
            if hasattr(self, 'batch_selector') and self.batch_selector:
                project_data['ui_state']['batch_num'] = self.batch_selector.get_num_images()
            
            # Advanced settings
            if hasattr(self, 'advanced_panel') and self.advanced_panel:
                project_data['ui_state']['advanced_settings'] = self.advanced_panel.get_settings()
            elif hasattr(self, 'steps_spin'):
                project_data['ui_state']['steps'] = self.steps_spin.value()
                project_data['ui_state']['guidance'] = self.guidance_spin.value()
            
            # Image settings visibility
            project_data['ui_state']['image_settings_expanded'] = self.image_settings_container.isVisible()
            
            # Encode image data
            import base64
            project_data['image_data'] = base64.b64encode(self.current_image_data).decode('utf-8')
            
            # Detect image format
            ext = detect_image_extension(self.current_image_data)
            project_data['image_format'] = ext
            
            # Save project file
            with open(project_path, 'w') as f:
                json.dump(project_data, f, indent=2)
            
            # Track current project
            self._current_project_path = project_path
            
            self.status_label.setText(f"Project saved: {project_path.name}")
            QMessageBox.information(self, APP_NAME, f"Project saved to:\n{project_path}")
            
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Error saving project:\n{e}")
    
    def _load_project(self):
        """Load a project file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project",
            str(Path.home()),
            "ImageAI Projects (*.imgai)"
        )
        
        if path:
            self._load_project_file(Path(path))
    
    def _load_project_file(self, project_path: Path):
        """Load a project from file."""
        try:
            if not project_path.exists():
                return
            
            with open(project_path, 'r') as f:
                project_data = json.load(f)
            
            # Load provider first if different
            if 'provider' in project_data and project_data['provider'] != self.current_provider:
                idx = self.provider_combo.findText(project_data['provider'])
                if idx >= 0:
                    self.provider_combo.setCurrentIndex(idx)
            
            # Load model
            if 'model' in project_data:
                idx = self._find_model_in_combo(project_data['model'])
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
            
            # Load prompt
            if 'prompt' in project_data:
                self.prompt_edit.setPlainText(project_data['prompt'])
            
            # Load UI state
            ui_state = project_data.get('ui_state', {})
            
            # Aspect ratio
            if 'aspect_ratio' in ui_state and hasattr(self, 'aspect_selector') and self.aspect_selector:
                # Try to set the aspect ratio
                for button in self.aspect_selector.buttons.values():
                    if button.property('ratio') == ui_state['aspect_ratio']:
                        button.click()
                        break
            
            # Resolution
            if 'resolution' in ui_state and hasattr(self, 'resolution_selector') and self.resolution_selector:
                # The resolution selector might need a method to set resolution
                if hasattr(self.resolution_selector, 'set_resolution'):
                    self.resolution_selector.set_resolution(ui_state['resolution'])
            elif 'resolution_combo_index' in ui_state and hasattr(self, 'resolution_combo'):
                if ui_state['resolution_combo_index'] < self.resolution_combo.count():
                    self.resolution_combo.setCurrentIndex(ui_state['resolution_combo_index'])
            
            # Quality settings
            if 'quality_settings' in ui_state and hasattr(self, 'quality_selector') and self.quality_selector:
                if hasattr(self.quality_selector, 'set_settings'):
                    self.quality_selector.set_settings(ui_state['quality_settings'])
            
            # Batch number
            if 'batch_num' in ui_state and hasattr(self, 'batch_selector') and self.batch_selector:
                if hasattr(self.batch_selector, 'set_num_images'):
                    self.batch_selector.set_num_images(ui_state['batch_num'])
            
            # Advanced settings
            if 'advanced_settings' in ui_state and hasattr(self, 'advanced_panel') and self.advanced_panel:
                if hasattr(self.advanced_panel, 'set_settings'):
                    self.advanced_panel.set_settings(ui_state['advanced_settings'])
            elif hasattr(self, 'steps_spin'):
                if 'steps' in ui_state:
                    self.steps_spin.setValue(ui_state['steps'])
                if 'guidance' in ui_state:
                    self.guidance_spin.setValue(ui_state['guidance'])
            
            # Image settings visibility
            if 'image_settings_expanded' in ui_state:
                if ui_state['image_settings_expanded']:
                    self.image_settings_container.setVisible(True)
                    self.image_settings_toggle.setText("▼ Image Settings")
                    self.image_settings_toggle.setChecked(True)
                else:
                    self.image_settings_container.setVisible(False)
                    self.image_settings_toggle.setText("▶ Image Settings")
                    self.image_settings_toggle.setChecked(False)
            
            # Load and display image
            if 'image_data' in project_data:
                import base64
                image_data = base64.b64decode(project_data['image_data'])
                self.current_image_data = image_data
                self._display_image(image_data)
                
                # Enable save/copy buttons
                self.btn_save_image.setEnabled(True)
                self.btn_copy_image.setEnabled(True)
            
            # Track current project
            self._current_project_path = project_path
            
            self.status_label.setText(f"Project loaded: {project_path.name}")
            
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Error loading project:\n{e}")
            self.status_label.setText(f"Error loading project: {e}")
    
    def _restore_geometry(self):
        """Restore window geometry from config."""
        geo = self.config.get("window_geometry")
        if isinstance(geo, dict):
            try:
                x = int(geo.get("x", self.x()))
                y = int(geo.get("y", self.y()))
                w = int(geo.get("w", self.width()))
                h = int(geo.get("h", self.height()))
                self.move(x, y)
                self.resize(w, h)
            except Exception:
                pass
    
    def eventFilter(self, obj, event):
        """Handle events for child widgets."""
        from PySide6.QtCore import QEvent, Qt

        # Handle Ctrl+Enter in prompt_edit to trigger generation
        if obj == self.prompt_edit and event.type() == QEvent.KeyPress:
            # Check for both Return and Enter keys with Ctrl modifier
            if (event.key() in [Qt.Key_Return, Qt.Key_Enter] and
                event.modifiers() & Qt.ControlModifier):
                # Trigger generate if button is enabled
                if self.btn_generate.isEnabled():
                    self._generate()
                    return True  # Event handled
            # Handle Ctrl+F for find
            elif event.key() == Qt.Key_F and event.modifiers() & Qt.ControlModifier:
                self._open_find_dialog()
                return True  # Event handled

        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """Handle window resize to scale images appropriately."""
        super().resizeEvent(event)
        
        # Use a timer to debounce resize events to prevent errors
        if not hasattr(self, '_resize_timer'):
            from PySide6.QtCore import QTimer
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._perform_image_resize)
        
        # Reset timer on each resize event (debounce)
        self._resize_timer.stop()
        self._resize_timer.start(50)  # 50ms delay

    def showEvent(self, event):
        """Ensure initial image scales when the window first shows."""
        super().showEvent(event)
        # Schedule multiple resize attempts to handle different layout timings
        for delay in [50, 100, 200, 350, 500]:
            try:
                QTimer.singleShot(delay, self._perform_image_resize)
            except Exception:
                pass
    
    def _perform_image_resize(self):
        """Actually perform the image resize after debounce."""
        # If we have an image displayed, rescale it to fit the new size
        if hasattr(self, 'output_image_label'):
            original_pixmap = self.output_image_label.property("original_pixmap")
            if original_pixmap and isinstance(original_pixmap, QPixmap):
                try:
                    # Get current label size and validate
                    label_size = self.output_image_label.size()
                    if label_size.width() <= 0 or label_size.height() <= 0:
                        return  # Skip if label has invalid size
                    
                    # Rescale the original pixmap to fit the new label size
                    scaled = original_pixmap.scaled(
                        max(1, label_size.width() - 4),  # Ensure minimum size
                        max(1, label_size.height() - 4),  # Ensure minimum size
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.output_image_label.setPixmap(scaled)
                except Exception:
                    # Silently ignore resize errors during rapid resizing
                    pass
    
    def closeEvent(self, event):
        """Save all UI state on close."""
        try:
            # Auto-save video project if exists
            if hasattr(self, 'tab_video') and self.tab_video:
                try:
                    # Check if the video tab is loaded and has a workspace widget with a current project
                    if self._video_tab_loaded and hasattr(self.tab_video, 'workspace') and self.tab_video.workspace:
                        workspace = self.tab_video.workspace
                        if hasattr(workspace, 'current_project') and workspace.current_project:
                            # Auto-save the project
                            workspace.save_project()
                            print(f"Auto-saved video project: {workspace.current_project.name}")
                except Exception as e:
                    print(f"Error auto-saving video project: {e}")
            
            # Save window geometry
            geo = {
                "x": self.x(),
                "y": self.y(),
                "w": self.width(),
                "h": self.height(),
            }
            self.config.set("window_geometry", geo)
            
            # Save all UI state
            self._save_ui_state()
            
            # Save config
            self.config.save()
        except Exception as e:
            print(f"Error saving UI state: {e}")
        
        # Clean up thread if running
        self._cleanup_thread()
    
    def _get_template_data(self):
        """Get template data with placeholders."""
        return {
            "Photorealistic product shot": {
                "template": "A high-resolution studio photograph of [product] on a [background] background, [lighting] lighting, shot with a [camera] lens, [style] style, [mood] mood",
                "fields": ["product", "background", "lighting", "camera", "style", "mood"]
            },
            "Fantasy Landscape": {
                "template": "Epic fantasy landscape with [feature], [atmosphere] atmosphere, [colors] colors, detailed environment, [style] art style",
                "fields": ["feature", "atmosphere", "colors", "style"]
            },
            "Sci-Fi Scene": {
                "template": "Futuristic [scene] with [technology], [aesthetic] aesthetic, [lighting], detailed sci-fi environment",
                "fields": ["scene", "technology", "aesthetic", "lighting"]
            },
            "Abstract Art": {
                "template": "Abstract [concept] artwork, [style] art style, [colors] colors, [composition] composition",
                "fields": ["concept", "style", "colors", "composition"]
            },
            "Character concept art": {
                "template": "Character design of [character], [style] style, [pose] pose, [setting], detailed costume design",
                "fields": ["character", "style", "pose", "setting"]
            },
            "Architectural Render": {
                "template": "Architectural visualization of [building], [style] design, [materials], [lighting] lighting, photorealistic render",
                "fields": ["building", "style", "materials", "lighting"]
            },
            "Character Design": {
                "template": "Character design of [character], concept art, [costume] costume, [pose] view, professional illustration",
                "fields": ["character", "costume", "pose"]
            },
            "Logo Design": {
                "template": "Logo design for [company], [style] style, [colors] colors, [elements], professional branding",
                "fields": ["company", "style", "colors", "elements"]
            }
        }
    
    def _create_template_fields(self):
        """Create input fields for the current template."""
        # Clear existing fields
        while self.template_form.count():
            item = self.template_form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.template_inputs.clear()
        
        # Get current template
        template_name = self.template_combo.currentText()
        template_data = self._get_template_data().get(template_name, {})
        
        if not template_data:
            return
        
        # Create field for each placeholder
        for field in template_data.get("fields", []):
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"[{field}]")
            self.template_form.addRow(f"{field}:", line_edit)
            self.template_inputs[field] = line_edit
    
    def _on_template_changed(self, template_name: str):
        """Handle template selection change."""
        self._create_template_fields()
    
    def _apply_template(self):
        """Apply selected template to prompt."""
        template_name = self.template_combo.currentText()
        template_data = self._get_template_data().get(template_name, {})
        
        if not template_data:
            return
        
        # Get the template string
        template_text = template_data.get("template", "")
        
        # Replace placeholders with user input
        for field, input_widget in self.template_inputs.items():
            value = input_widget.text().strip()
            if value:
                template_text = template_text.replace(f"[{field}]", value)
        
        # Apply to prompt
        if self.append_prompt_check.isChecked():
            # Append to existing prompt
            current_prompt = self.prompt_edit.toPlainText()
            if current_prompt:
                template_text = f"{current_prompt}\n\n{template_text}"
        
        self.prompt_edit.setPlainText(template_text)
        self.tabs.setCurrentWidget(self.tab_generate)
    
    def _on_history_selection_changed(self, selected, deselected):
        """Handle history selection change - display the image."""
        indexes = self.history_table.selectionModel().selectedRows()
        if not indexes:
            return
        
        # Get the selected history item from the table
        row = indexes[0].row()
        date_item = self.history_table.item(row, 0)
        if date_item:
            history_item = date_item.data(Qt.UserRole)
            if isinstance(history_item, dict):
                path = history_item.get('path')
                if path and path.exists():
                    try:
                        # Read and display the image
                        image_data = path.read_bytes()
                        self._last_displayed_image_path = path  # Track last displayed image

                        # TODO: Re-enable auto-crop after fixing the algorithm
                        # Currently disabled as it's cropping incorrectly
                        # # Apply auto-crop for Google provider images if available
                        # provider = history_item.get('provider', '')
                        # if provider == 'google':
                        #     try:
                        #         from core.image_utils import auto_crop_solid_borders
                        #         image_data = auto_crop_solid_borders(image_data)
                        #     except ImportError:
                        #         pass  # image_utils not available, skip auto-crop

                        self.current_image_data = image_data

                        # Display in output label
                        pixmap = QPixmap()
                        if pixmap.loadFromData(image_data):
                            # Get the label's current size
                            label_size = self.output_image_label.size()

                            # Ensure we have valid dimensions
                            if label_size.width() <= 0 or label_size.height() <= 0:
                                # Label not ready yet, use _display_image which handles this
                                self._display_image(image_data)
                            else:
                                # Scale to fit the label while maintaining aspect ratio
                                scaled = pixmap.scaled(
                                    label_size.width() - 4,  # Account for border
                                    label_size.height() - 4,  # Account for border
                                    Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation
                                )
                                self.output_image_label.setPixmap(scaled)

                                # Store the original pixmap for resizing
                                self.output_image_label.setProperty("original_pixmap", pixmap)
                                # Ensure scaling after layout completes
                                for delay in [50, 100, 200, 500]:
                                    try:
                                        QTimer.singleShot(delay, self._perform_image_resize)
                                    except Exception:
                                        pass
                        
                        # Enable save and copy buttons since we have an image
                        self.btn_save_image.setEnabled(True)
                        self.btn_copy_image.setEnabled(True)
                        
                        # Load metadata
                        prompt = history_item.get('prompt', '')
                        self.prompt_edit.setPlainText(prompt)
                        
                        # Load model if available
                        model = history_item.get('model', '')
                        if model:
                            idx = self._find_model_in_combo(model)
                            if idx >= 0:
                                self.model_combo.setCurrentIndex(idx)
                        
                        # Load provider if available and different
                        provider = history_item.get('provider', '')
                        if provider and provider != self.current_provider:
                            idx = self.provider_combo.findText(provider)
                            if idx >= 0:
                                self.provider_combo.setCurrentIndex(idx)
                        
                        # Update status
                        self.status_label.setText("Loaded from history")
                        
                    except Exception as e:
                        self.output_image_label.setText(f"Error loading image: {e}")
    
    def _load_history_item(self, item):
        """Load a history item and switch to Generate tab."""
        # Selection change will handle the loading
        self.tabs.setCurrentWidget(self.tab_generate)
    
    def _load_selected_history(self):
        """Load the selected history item."""
        indexes = self.history_table.selectionModel().selectedRows()
        if indexes:
            row = indexes[0].row()
            date_item = self.history_table.item(row, 0)
            if date_item:
                self._load_history_item(date_item)
    
    def _clear_history(self):
        """Clear history."""
        reply = QMessageBox.question(
            self, APP_NAME, 
            "Clear all history?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.history.clear()
            self.history_table.setRowCount(0)
    
    def _on_tab_changed(self, index):
        """Handle tab change events."""
        current_widget = self.tabs.widget(index)

        # Lazy load video tab on first access
        if current_widget == self.tab_video and not self._video_tab_loaded:
            self._load_video_tab()

        # If switching to help tab, trigger a minimal scroll to fix rendering
        if current_widget == self.tab_help:
            self._trigger_help_render()

    def _load_video_tab(self):
        """Lazy load the video tab when first accessed."""
        try:
            # Import and create the real video tab
            from gui.video.video_project_tab import VideoProjectTab

            providers_dict = {
                'available': list_providers(),
                'current': self.current_provider,
                'config': self.config
            }

            # Store the index before replacing
            video_index = self.tabs.indexOf(self.tab_video)

            # Create the real video tab
            real_video_tab = VideoProjectTab(self.config.config, providers_dict)

            # Connect signals
            if hasattr(real_video_tab, 'image_provider_changed'):
                real_video_tab.image_provider_changed.connect(self._on_video_image_provider_changed)
            if hasattr(real_video_tab, 'llm_provider_changed'):
                real_video_tab.llm_provider_changed.connect(self._on_video_llm_provider_changed)

            # Replace the placeholder with the real tab
            self.tabs.removeTab(video_index)
            self.tabs.insertTab(video_index, real_video_tab, "🎬 Video")
            self.tabs.setCurrentIndex(video_index)

            # Update references
            self.tab_video = real_video_tab
            self._video_tab_loaded = True

            # Sync LLM provider to video tab if it's set
            if hasattr(self, 'llm_provider_combo') and self.llm_provider_combo.currentText() != "None":
                provider_name = self.llm_provider_combo.currentText()
                model_name = self.llm_model_combo.currentText() if self.llm_model_combo.isEnabled() else None
                if hasattr(self.tab_video, 'set_llm_provider'):
                    self.tab_video.set_llm_provider(provider_name, model_name)

        except Exception as e:
            import traceback
            QMessageBox.warning(self, "Video Tab Error",
                              f"Failed to load video tab: {str(e)}\n\n{traceback.format_exc()}")
    
    def _trigger_help_render(self):
        """Trigger rendering by doing a minimal scroll."""
        if hasattr(self, 'help_browser') and hasattr(self.help_browser, 'verticalScrollBar'):
            try:
                # Do a minimal scroll down then back up to trigger rendering
                scrollbar = self.help_browser.verticalScrollBar()
                scrollbar.setValue(1)
                scrollbar.setValue(0)
            except Exception:
                pass
    
    def _update_help_nav_buttons(self):
        """Update the state of help navigation buttons based on browser history."""
        if hasattr(self, 'help_browser') and hasattr(self.help_browser, 'history'):
            try:
                self.btn_help_back.setEnabled(self.help_browser.history().canGoBack())
                self.btn_help_forward.setEnabled(self.help_browser.history().canGoForward())
            except Exception:
                pass  # Silently ignore if buttons don't exist yet

    def _search_help_webengine(self, backward=False):
        """Search in WebEngine-based help browser."""
        if not hasattr(self, 'help_browser'):
            return
            
        search_text = self.help_search_input.text().strip()
        if not search_text:
            self.help_search_results.setText("")
            return
        
        try:
            from PySide6.QtWebEngineCore import QWebEnginePage
            
            # Create search flags
            flags = QWebEnginePage.FindFlag(0)
            if backward:
                flags |= QWebEnginePage.FindBackward
            
            # Perform search with callback for result count
            def handle_result(result):
                if hasattr(result, 'numberOfMatches'):
                    total = result.numberOfMatches()
                    current = result.activeMatch()
                    if total > 0:
                        self.help_search_results.setText(f"{current}/{total} matches")
                    else:
                        self.help_search_results.setText("No matches")
                else:
                    # Fallback for older Qt versions
                    self.help_search_results.setText("Searching...")
            
            # Search with callback
            self.help_browser.findText(search_text, flags, handle_result)
            
        except Exception as e:
            print(f"Search error: {e}")
            # Fallback to simple search without match count
            try:
                from PySide6.QtWebEngineCore import QWebEnginePage
                flags = QWebEnginePage.FindFlag(0)
                if backward:
                    flags |= QWebEnginePage.FindBackward
                self.help_browser.findText(search_text, flags)
                self.help_search_results.setText("Searching...")
            except:
                pass
    
    def _search_help_textbrowser(self, backward=False):
        """Search in QTextBrowser-based help browser."""
        if not hasattr(self, 'help_browser'):
            return
            
        search_text = self.help_search_input.text().strip()
        if not search_text:
            self.help_search_results.setText("")
            # Clear any existing highlights
            cursor = self.help_browser.textCursor()
            cursor.clearSelection()
            self.help_browser.setTextCursor(cursor)
            return
        
        try:
            from PySide6.QtGui import QTextDocument
            from PySide6.QtCore import Qt
            
            # Set up search flags
            flags = QTextDocument.FindFlag(0)
            if backward:
                flags |= QTextDocument.FindBackward
            
            # Search from current position
            found = self.help_browser.find(search_text, flags)
            
            if not found:
                # If not found and we're going forward, try from beginning
                if not backward:
                    cursor = self.help_browser.textCursor()
                    cursor.movePosition(cursor.Start)
                    self.help_browser.setTextCursor(cursor)
                    found = self.help_browser.find(search_text, flags)
                # If not found and we're going backward, try from end
                else:
                    cursor = self.help_browser.textCursor()
                    cursor.movePosition(cursor.End)
                    self.help_browser.setTextCursor(cursor)
                    found = self.help_browser.find(search_text, flags)
            
            # Update search results label
            if found:
                # Count total matches (simple approach)
                doc = self.help_browser.document()
                cursor = doc.find(search_text)
                count = 0
                while not cursor.isNull():
                    count += 1
                    cursor = doc.find(search_text, cursor)
                
                if count > 0:
                    self.help_search_results.setText(f"{count} matches")
                else:
                    self.help_search_results.setText("Found")
            else:
                self.help_search_results.setText("No matches")
                
        except Exception as e:
            print(f"Search error: {e}")
            self.help_search_results.setText("Error")
    
    def _toggle_image_settings(self):
        """Toggle the image settings panel visibility."""
        is_visible = self.image_settings_container.isVisible()
        self.image_settings_container.setVisible(not is_visible)
        self.image_settings_toggle.setText("▼ Image Settings" if not is_visible else "▶ Image Settings")

    def _select_reference_image(self):
        """Open dialog to select a reference image."""
        from PySide6.QtGui import QImage
        import base64

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            str(images_output_dir()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)"
        )

        if file_path:
            try:
                # Load and display the image
                pixmap = QPixmap(file_path)
                if pixmap.isNull():
                    QMessageBox.warning(self, "Error", "Failed to load image")
                    return

                # Scale for preview (maintain aspect ratio)
                scaled_pixmap = pixmap.scaled(
                    300, 150,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.ref_image_preview.setPixmap(scaled_pixmap)
                self.ref_image_preview.setVisible(True)

                # Store the image data
                self.reference_image_path = Path(file_path)
                with open(file_path, 'rb') as f:
                    self.reference_image_data = f.read()

                # Enable controls
                self.ref_image_enabled.setEnabled(True)
                self.ref_image_enabled.setChecked(True)
                self.btn_clear_ref_image.setEnabled(True)

                # Show options widget
                self.ref_options_widget.setVisible(True)
                self._update_ref_instruction_preview()

                # Update button text to show filename
                filename = self.reference_image_path.name
                if len(filename) > 30:
                    filename = filename[:27] + "..."
                self.btn_select_ref_image.setText(f"Reference: {filename}")

                # Save to project/settings
                self._save_reference_image_to_config()

                # Update status
                self.status_bar.showMessage(f"Reference image loaded: {self.reference_image_path.name}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load reference image: {str(e)}")

    def _clear_reference_image(self):
        """Clear the selected reference image."""
        self.reference_image_path = None
        self.reference_image_data = None
        self.ref_image_preview.setPixmap(QPixmap())
        self.ref_image_preview.setVisible(False)
        self.ref_image_enabled.setChecked(False)
        self.ref_image_enabled.setEnabled(False)
        self.btn_clear_ref_image.setEnabled(False)
        self.btn_select_ref_image.setText("Select Reference Image...")

        # Hide options widget
        self.ref_options_widget.setVisible(False)

        # Remove from project/settings
        self._clear_reference_image_from_config()

        self.status_bar.showMessage("Reference image cleared")

    def _on_ref_image_toggled(self, checked):
        """Handle reference image checkbox toggle."""
        if self.reference_image_path:
            status = "enabled" if checked else "disabled"
            self.status_bar.showMessage(f"Reference image {status}")
            # Save state to config
            self._save_reference_image_to_config()
            # Update instruction preview
            self._update_ref_instruction_preview()

    def _on_ref_style_changed(self, style):
        """Handle reference image style change."""
        self._update_ref_instruction_preview()
        if self.reference_image_path:
            self._save_reference_image_to_config()

    def _on_ref_position_changed(self, position):
        """Handle reference image position change."""
        self._update_ref_instruction_preview()
        if self.reference_image_path:
            self._save_reference_image_to_config()

    def _update_ref_instruction_preview(self):
        """Update the preview of what will be inserted into the prompt."""
        if not hasattr(self, 'ref_instruction_label'):
            return

        # Get resolution if available (show this even without reference image)
        resolution_text = ""
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            if hasattr(self.resolution_selector, 'get_width_height'):
                width, height = self.resolution_selector.get_width_height()
                if width and height and (width != 1024 or height != 1024):
                    # If using Google provider and resolution > 1024, calculate scaled dimensions
                    if self.current_provider == 'google':
                        max_dim = max(width, height)
                        if max_dim > 1024:
                            scale_factor = 1024 / max_dim
                            scaled_width = int(width * scale_factor)
                            scaled_height = int(height * scale_factor)
                            resolution_text = f"(Image will be {scaled_width}x{scaled_height}, scale to fit.)"
                        else:
                            resolution_text = f"(Image will be {width}x{height}, scale to fit.)"
                    else:
                        resolution_text = f"(Image will be {width}x{height}, scale to fit.)"

        if not self.reference_image_path or not self.ref_image_enabled.isChecked():
            # Show resolution info even without reference image
            if resolution_text:
                self.ref_instruction_label.setText(f"Will insert: \"{resolution_text}\"")
            else:
                self.ref_instruction_label.setText("Will insert: [nothing]")
            return

        # Get selected style and position
        style = self.ref_style_combo.currentText() if hasattr(self, 'ref_style_combo') else "Natural blend"
        position = self.ref_position_combo.currentText() if hasattr(self, 'ref_position_combo') else "Auto"

        # Build the instruction text
        instruction_parts = []

        # Add base text
        if position != "Auto":
            instruction_parts.append(f"Attached photo on the {position.lower()}")
        else:
            instruction_parts.append("Attached photo")

        # Add style
        style_map = {
            "Natural blend": "naturally blended into the scene",
            "In center": "placed in the center",
            "Blurred edges": "with blurred edges",
            "In circle": "inside a circular frame",
            "In frame": "in a decorative frame",
            "Seamless merge": "seamlessly merged",
            "As background": "as the background",
            "As overlay": "as an overlay",
            "Split screen": "in split-screen style"
        }

        if style in style_map:
            instruction_parts.append(style_map[style])

        # Resolution text is already computed above, add space if needed
        if resolution_text and not resolution_text.startswith(" "):
            resolution_text = f" {resolution_text}"

        # Combine the instruction
        instruction = f"{', '.join(instruction_parts)}.{resolution_text}"

        # Update the preview label
        self.ref_instruction_label.setText(f"Will insert: \"{instruction}\"")

    def _save_reference_image_to_config(self):
        """Save reference image path to settings."""
        # Save to global settings (project support can be added later)
        ref_images = self.config.get('reference_images', {})
        ref_images['image_tab'] = {
            'path': str(self.reference_image_path) if self.reference_image_path else None,
            'enabled': self.ref_image_enabled.isChecked(),
            'style': self.ref_style_combo.currentText() if hasattr(self, 'ref_style_combo') else "Natural blend",
            'position': self.ref_position_combo.currentText() if hasattr(self, 'ref_position_combo') else "Auto"
        }
        self.config.set('reference_images', ref_images)
        self.config.save()

    def _clear_reference_image_from_config(self):
        """Remove reference image from settings."""
        # Remove from global settings
        ref_images = self.config.get('reference_images', {})
        if 'image_tab' in ref_images:
            del ref_images['image_tab']
            self.config.set('reference_images', ref_images)
            self.config.save()

    def _load_reference_image_from_config(self):
        """Load reference image from settings."""
        # Load from global settings
        ref_images = self.config.get('reference_images', {})
        ref_image_data = ref_images.get('image_tab')

        # Load the image if found
        if ref_image_data and ref_image_data.get('path'):
            path = Path(ref_image_data['path'])
            if path.exists():
                try:
                    # Load and display the image
                    pixmap = QPixmap(str(path))
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            300, 150,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        self.ref_image_preview.setPixmap(scaled_pixmap)
                        self.ref_image_preview.setVisible(True)

                        # Store the image data
                        self.reference_image_path = path
                        with open(path, 'rb') as f:
                            self.reference_image_data = f.read()

                        # Update controls
                        self.ref_image_enabled.setEnabled(True)
                        self.ref_image_enabled.setChecked(ref_image_data.get('enabled', False))
                        self.btn_clear_ref_image.setEnabled(True)

                        # Update button text
                        filename = path.name
                        if len(filename) > 30:
                            filename = filename[:27] + "..."
                        self.btn_select_ref_image.setText(f"Reference: {filename}")

                        # Show options widget and restore settings
                        self.ref_options_widget.setVisible(True)
                        if 'style' in ref_image_data:
                            self.ref_style_combo.setCurrentText(ref_image_data['style'])
                        if 'position' in ref_image_data:
                            self.ref_position_combo.setCurrentText(ref_image_data['position'])
                        self._update_ref_instruction_preview()

                except Exception as e:
                    logger.warning(f"Failed to load reference image from config: {e}")

    def _save_ui_state(self):
        """Save all UI widget states to config."""
        ui_state = {}
        
        try:
            # Current tab index
            ui_state['current_tab'] = self.tabs.currentIndex()
            
            # Generate tab settings
            ui_state['prompt'] = self.prompt_edit.toPlainText()
            ui_state['model'] = self.model_combo.currentData() or self.model_combo.currentText()
            ui_state['model_index'] = self.model_combo.currentIndex()

            # LLM Provider settings
            if hasattr(self, 'llm_provider_combo'):
                ui_state['llm_provider'] = self.llm_provider_combo.currentText()
                ui_state['llm_model'] = self.llm_model_combo.currentText() if self.llm_model_combo.isEnabled() else None

            # Image settings expansion state
            ui_state['image_settings_expanded'] = self.image_settings_container.isVisible()
            
            # Image settings values
            if hasattr(self, 'aspect_selector') and self.aspect_selector:
                ui_state['aspect_ratio'] = self.aspect_selector.get_ratio()
            
            if hasattr(self, 'resolution_selector') and self.resolution_selector:
                ui_state['resolution'] = self.resolution_selector.get_resolution()
            elif hasattr(self, 'resolution_combo'):
                ui_state['resolution_combo_index'] = self.resolution_combo.currentIndex()
            
            if hasattr(self, 'quality_selector') and self.quality_selector:
                ui_state['quality_settings'] = self.quality_selector.get_settings()
            
            if hasattr(self, 'batch_selector') and self.batch_selector:
                ui_state['batch_num'] = self.batch_selector.get_num_images()
            
            # Save last displayed image path
            if hasattr(self, '_last_displayed_image_path'):
                ui_state['last_displayed_image'] = str(self._last_displayed_image_path)
            
            # Save current project if any
            if hasattr(self, '_current_project_path'):
                ui_state['last_project'] = str(self._current_project_path)
            
            # Advanced settings
            if hasattr(self, 'advanced_panel') and self.advanced_panel:
                ui_state['advanced_expanded'] = self.advanced_panel.expanded  # Use attribute, not method
                ui_state['advanced_settings'] = self.advanced_panel.get_settings()
            elif hasattr(self, 'advanced_group'):
                ui_state['advanced_visible'] = self.advanced_group.isVisible()
                if hasattr(self, 'steps_spin'):
                    ui_state['steps'] = self.steps_spin.value()
                if hasattr(self, 'guidance_spin'):
                    ui_state['guidance'] = self.guidance_spin.value()
            
            # Splitter sizes (for prompt/image split)
            if hasattr(self, 'tab_generate'):
                splitters = self.tab_generate.findChildren(QSplitter)
                if splitters:
                    ui_state['splitter_sizes'] = splitters[0].sizes()
            
            # Templates tab
            if hasattr(self, 'template_combo'):
                ui_state['template_index'] = self.template_combo.currentIndex()
            
            # Settings tab - provider is saved in config, not UI state
            
            # History tab - column widths
            if hasattr(self, 'history_table'):
                header = self.history_table.horizontalHeader()
                column_widths = []
                for i in range(self.history_table.columnCount()):
                    column_widths.append(header.sectionSize(i))
                ui_state['history_column_widths'] = column_widths
                ui_state['history_sort_column'] = header.sortIndicatorSection()
                # Convert Qt.SortOrder enum to int
                from PySide6.QtCore import Qt
                sort_order = header.sortIndicatorOrder()
                ui_state['history_sort_order'] = 0 if sort_order == Qt.AscendingOrder else 1
            
            # Output console height is auto-managed; do not persist
            
            # Save to config
            self.config.set('ui_state', ui_state)
            
        except Exception as e:
            print(f"Error saving UI state: {e}")
    
    def _restore_ui_state(self):
        """Restore all UI widget states from config."""
        ui_state = self.config.get('ui_state', {})
        if not ui_state:
            return
        
        try:
            # Restore prompt
            if 'prompt' in ui_state:
                self.prompt_edit.setPlainText(ui_state['prompt'])
            
            # Restore model selection
            if 'model_index' in ui_state and ui_state['model_index'] >= 0:
                if ui_state['model_index'] < self.model_combo.count():
                    self.model_combo.setCurrentIndex(ui_state['model_index'])
            elif 'model' in ui_state:
                idx = self._find_model_in_combo(ui_state['model'])
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)

            # Restore LLM Provider settings
            if 'llm_provider' in ui_state and hasattr(self, 'llm_provider_combo'):
                # Set flag to prevent triggering saves during restoration
                self._updating_llm_provider = True

                provider_index = self.llm_provider_combo.findText(ui_state['llm_provider'])
                if provider_index >= 0:
                    self.llm_provider_combo.blockSignals(True)
                    self.llm_provider_combo.setCurrentIndex(provider_index)
                    self.llm_provider_combo.blockSignals(False)

                    # Manually populate models for the provider
                    self.llm_model_combo.blockSignals(True)
                    self.llm_model_combo.clear()

                    provider = ui_state['llm_provider']
                    if provider != "None":
                        self.llm_model_combo.setEnabled(True)
                        if provider == "OpenAI":
                            self.llm_model_combo.addItems(["gpt-5-chat-latest", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"])
                        elif provider == "Claude":
                            self.llm_model_combo.addItems(["claude-opus-4.1", "claude-opus-4", "claude-sonnet-4", "claude-3.7-sonnet", "claude-3.5-sonnet", "claude-3.5-haiku"])
                        elif provider == "Gemini":
                            self.llm_model_combo.addItems(["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-pro"])
                        elif provider == "Ollama":
                            self.llm_model_combo.addItems(["llama2", "mistral", "mixtral", "phi-2", "neural-chat"])
                        elif provider == "LM Studio":
                            self.llm_model_combo.addItems(["local-model", "custom-model"])
                    else:
                        self.llm_model_combo.setEnabled(False)

                    self.llm_model_combo.blockSignals(False)

                    # Now restore the model if it was saved
                    if 'llm_model' in ui_state and ui_state['llm_model'] and hasattr(self, 'llm_model_combo'):
                        self.llm_model_combo.blockSignals(True)
                        model_index = self.llm_model_combo.findText(ui_state['llm_model'])
                        if model_index >= 0:
                            self.llm_model_combo.setCurrentIndex(model_index)
                        self.llm_model_combo.blockSignals(False)

                # Clear flag
                self._updating_llm_provider = False

            # Restore image settings expansion
            if 'image_settings_expanded' in ui_state:
                if ui_state['image_settings_expanded']:
                    self.image_settings_container.setVisible(True)
                    self.image_settings_toggle.setText("▼ Image Settings")
                    self.image_settings_toggle.setChecked(True)
            
            # Restore aspect ratio
            if 'aspect_ratio' in ui_state and hasattr(self, 'aspect_selector') and self.aspect_selector:
                # The aspect selector might have a method to set the ratio
                try:
                    self.aspect_selector.set_ratio(ui_state['aspect_ratio'])
                except:
                    pass
            
            # Restore resolution
            if 'resolution' in ui_state and hasattr(self, 'resolution_selector') and self.resolution_selector:
                try:
                    self.resolution_selector.set_resolution(ui_state['resolution'])
                except:
                    pass
            elif 'resolution_combo_index' in ui_state and hasattr(self, 'resolution_combo'):
                if ui_state['resolution_combo_index'] < self.resolution_combo.count():
                    self.resolution_combo.setCurrentIndex(ui_state['resolution_combo_index'])
            
            # Restore quality settings
            if 'quality_settings' in ui_state and hasattr(self, 'quality_selector') and self.quality_selector:
                try:
                    # Now QualitySelector has set_settings method
                    self.quality_selector.set_settings(ui_state['quality_settings'])
                except Exception as e:
                    print(f"Error restoring quality settings: {e}")
            
            # Restore batch number
            if 'batch_num' in ui_state and hasattr(self, 'batch_selector') and self.batch_selector:
                try:
                    # BatchSelector uses a spin box
                    if hasattr(self.batch_selector, 'spin'):
                        self.batch_selector.spin.setValue(ui_state['batch_num'])
                        self.batch_selector.num_images = ui_state['batch_num']
                except:
                    pass
            
            # Restore advanced settings
            if hasattr(self, 'advanced_panel') and self.advanced_panel:
                if 'advanced_expanded' in ui_state:
                    try:
                        # Set the expanded state directly
                        if ui_state['advanced_expanded']:
                            self.advanced_panel.expanded = True
                            self.advanced_panel.container.setVisible(True)
                            self.advanced_panel.toggle_btn.setText("▼ Advanced Settings")
                            self.advanced_panel.toggle_btn.setChecked(True)
                    except:
                        pass
                if 'advanced_settings' in ui_state:
                    try:
                        # Now AdvancedSettingsPanel has set_settings method
                        self.advanced_panel.set_settings(ui_state['advanced_settings'])
                    except Exception as e:
                        print(f"Error restoring advanced settings: {e}")
            elif hasattr(self, 'advanced_group'):
                if 'advanced_visible' in ui_state:
                    self.advanced_group.setVisible(ui_state['advanced_visible'])
                if 'steps' in ui_state and hasattr(self, 'steps_spin'):
                    self.steps_spin.setValue(ui_state['steps'])
                if 'guidance' in ui_state and hasattr(self, 'guidance_spin'):
                    self.guidance_spin.setValue(ui_state['guidance'])
            
            # Restore splitter sizes
            if 'splitter_sizes' in ui_state and hasattr(self, 'tab_generate'):
                splitters = self.tab_generate.findChildren(QSplitter)
                if splitters and len(ui_state['splitter_sizes']) == 2:
                    splitters[0].setSizes(ui_state['splitter_sizes'])
            
            # Restore template selection
            if 'template_index' in ui_state and hasattr(self, 'template_combo'):
                if ui_state['template_index'] < self.template_combo.count():
                    self.template_combo.setCurrentIndex(ui_state['template_index'])
            
            # Provider is restored from config, not UI state
            # This ensures the provider selection persists correctly
            # (UI state is for session state, config is for persistent settings)
            
            # Restore history table column widths
            if hasattr(self, 'history_table'):
                if 'history_column_widths' in ui_state:
                    header = self.history_table.horizontalHeader()
                    widths = ui_state['history_column_widths']
                    for i, width in enumerate(widths):
                        if i < self.history_table.columnCount():
                            header.resizeSection(i, width)
                
                if 'history_sort_column' in ui_state and 'history_sort_order' in ui_state:
                    from PySide6.QtCore import Qt
                    sort_order = Qt.AscendingOrder if ui_state['history_sort_order'] == 0 else Qt.DescendingOrder
                    self.history_table.sortItems(ui_state['history_sort_column'], sort_order)
            
            # Output console height is auto-managed; nothing to restore
            
            # Restore current tab (do this last so all content is ready)
            if 'current_tab' in ui_state:
                if ui_state['current_tab'] < self.tabs.count():
                    self.tabs.setCurrentIndex(ui_state['current_tab'])
            
            # Restore last project if saved
            if 'last_project' in ui_state:
                project_path = Path(ui_state['last_project'])
                if project_path.exists():
                    # Use QTimer to load project after UI is fully initialized
                    QTimer.singleShot(100, lambda: self._load_project_file(project_path))
            # Otherwise restore last displayed image if available
            elif 'last_displayed_image' in ui_state:
                image_path = Path(ui_state['last_displayed_image'])
                if image_path.exists():
                    # Use QTimer to load image after UI is fully initialized
                    QTimer.singleShot(100, lambda: self._load_image_file(image_path))
            
        except Exception as e:
            print(f"Error restoring UI state: {e}")
    
    def _refresh_history_table(self):
        """Refresh the history table with current history data."""
        if not hasattr(self, 'history_table'):
            return
        
        # Clear and repopulate the table
        self.history_table.setRowCount(len(self.history))
        
        for row, item in enumerate(self.history):
            if isinstance(item, dict):
                # Parse timestamp and combine date & time
                timestamp = item.get('timestamp', '')
                datetime_str = ''
                sortable_datetime = None
                if isinstance(timestamp, float):
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp)
                    datetime_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    sortable_datetime = dt
                elif isinstance(timestamp, str) and 'T' in timestamp:
                    # ISO format
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        datetime_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        sortable_datetime = dt
                    except:
                        parts = timestamp.split('T')
                        date_str = parts[0]
                        time_str = parts[1].split('.')[0] if len(parts) > 1 else ''
                        datetime_str = f"{date_str} {time_str}"
                
                # Date & Time column (combined)
                from PySide6.QtWidgets import QTableWidgetItem
                datetime_item = QTableWidgetItem(datetime_str)
                # Store sortable datetime for proper chronological sorting
                if sortable_datetime:
                    datetime_item.setData(Qt.UserRole + 1, sortable_datetime)
                self.history_table.setItem(row, 0, datetime_item)
                
                # Provider column (now column 1)
                provider = item.get('provider', '')
                provider_item = QTableWidgetItem(provider.title() if provider else 'Unknown')
                self.history_table.setItem(row, 1, provider_item)
                
                # Model column (now column 2)
                model = item.get('model', '')
                model_display = model.split('/')[-1] if '/' in model else model
                model_item = QTableWidgetItem(model_display)
                model_item.setToolTip(model)
                self.history_table.setItem(row, 2, model_item)
                
                # Prompt column (now column 3)
                prompt = item.get('prompt', 'No prompt')
                prompt_item = QTableWidgetItem(prompt[:100] + '...' if len(prompt) > 100 else prompt)
                prompt_item.setToolTip(f"Full prompt:\n{prompt}")
                self.history_table.setItem(row, 3, prompt_item)
                
                # Resolution column (now column 4)
                width = item.get('width', '')
                height = item.get('height', '')
                resolution = f"{width}x{height}" if width and height else ''
                resolution_item = QTableWidgetItem(resolution)
                self.history_table.setItem(row, 4, resolution_item)
                
                # Cost column (now column 5)
                cost = item.get('cost', 0.0)
                cost_str = f"${cost:.4f}" if cost > 0 else '-'
                cost_item = QTableWidgetItem(cost_str)
                self.history_table.setItem(row, 5, cost_item)
                
                # Store the history item data in the first column for easy retrieval
                datetime_item.setData(Qt.UserRole, item)
    def _show_log_location(self):
        """Show the location of log files to the user."""
        from core.logging_config import get_error_report_info
        info = get_error_report_info()
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Log File Location")
        msg.setIcon(QMessageBox.Information)
        
        text = f"<b>Log files are stored in:</b><br>{info['log_directory']}<br><br>"
        if info['recent_log']:
            text += f"<b>Most recent log:</b><br>{info['recent_log']}<br><br>"
        text += "<b>Logs contain:</b><br>• Error messages<br>• Debug information<br>• System information"
        
        msg.setText(text)
        msg.setDetailedText(info['report_instructions'])
        msg.exec()
    
    def _show_error_reporting(self):
        """Show instructions for reporting errors."""
        from core.logging_config import get_error_report_info
        info = get_error_report_info()
        
        msg = QMessageBox(self)
        msg.setWindowTitle("How to Report Errors")
        msg.setIcon(QMessageBox.Information)
        
        text = (
            "<b>To report an error:</b><br><br>"
            "1. Find the log file (Help → Show Log Location)<br>"
            "2. Copy the error messages from the log<br>"
            "3. Create an issue at:<br>"
            "   <a href='https://github.com/anthropics/imageai/issues'>github.com/anthropics/imageai/issues</a><br><br>"
            "<b>Include in your report:</b><br>"
            "• What you were trying to do<br>"
            "• The exact error message<br>"
            "• Steps to reproduce the issue<br>"
            "• Relevant log excerpts"
        )
        
        msg.setText(text)
        msg.setTextFormat(Qt.RichText)
        msg.exec()
