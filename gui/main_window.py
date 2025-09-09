"""Main window for ImageAI GUI."""

import json
import webbrowser
from pathlib import Path
from typing import Optional, List
from datetime import datetime

try:
    from PySide6.QtCore import Qt, QThread, Signal, QTimer
    from PySide6.QtGui import QPixmap, QAction
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QLabel, QTextEdit, QPushButton, QComboBox, QLineEdit,
        QFormLayout, QSizePolicy, QMessageBox, QFileDialog,
        QCheckBox, QTextBrowser, QListWidget, QListWidgetItem, QDialog, QSpinBox,
        QDoubleSpinBox, QGroupBox, QApplication, QSplitter
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
from providers import get_provider, list_providers
from gui.dialogs import ExamplesDialog
from gui.workers import GenWorker
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
        self.history_paths: List[Path] = scan_disk_history()
        self.history = []  # Initialize empty history list
        self.current_prompt: str = ""
        self.gen_thread: Optional[QThread] = None
        self.gen_worker: Optional[GenWorker] = None
        self.current_image_data: Optional[bytes] = None
        self._last_template_context: Optional[dict] = None
        
        # Load history from disk
        self._load_history_from_disk()
        
        # Create UI
        self._init_ui()
        self._init_menu()
        
        # Restore window geometry and UI state
        self._restore_geometry()
        self._restore_ui_state()
    
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
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Create tabs
        self.tab_generate = QWidget()
        self.tab_templates = QWidget()
        self.tab_settings = QWidget()
        self.tab_help = QWidget()
        self.tab_history = QWidget()
        
        self.tabs.addTab(self.tab_generate, "Generate")
        self.tabs.addTab(self.tab_templates, "Templates")
        self.tabs.addTab(self.tab_settings, "Settings")
        self.tabs.addTab(self.tab_help, "Help")
        self.tabs.addTab(self.tab_history, "History")  # Always add history tab
        
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
    
    def _init_generate_tab(self):
        """Initialize the Generate tab."""
        v = QVBoxLayout(self.tab_generate)
        v.setSpacing(2)
        v.setContentsMargins(5, 5, 5, 5)
        
        # Model selection at the very top
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self._update_model_list()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        v.addLayout(model_layout)
        
        # Create vertical splitter for prompt and image
        splitter = QSplitter(Qt.Vertical)
        
        # Top section: Prompt input (resizable via splitter)
        prompt_container = QWidget()
        prompt_layout = QVBoxLayout(prompt_container)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(2)
        
        prompt_label = QLabel("Prompt:")
        prompt_layout.addWidget(prompt_label)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Describe what to generate...")
        self.prompt_edit.setAcceptRichText(False)
        prompt_layout.addWidget(self.prompt_edit)
        
        # Add prompt container to splitter
        splitter.addWidget(prompt_container)
        
        # Bottom section: Everything else
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(5)
        
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
        else:
            self.aspect_selector = None
        
        # Resolution and Quality
        settings_form = QFormLayout()
        settings_form.setVerticalSpacing(5)
        
        if ResolutionSelector:
            self.resolution_selector = ResolutionSelector(self.current_provider)
            self.resolution_selector.resolutionChanged.connect(self._on_resolution_changed)
            settings_form.addRow("Resolution:", self.resolution_selector)
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
        
        # Buttons - all on one row for compactness
        hb = QHBoxLayout()
        self.btn_examples = QPushButton("Examples")
        self.btn_generate = QPushButton("Generate")
        self.btn_save_image = QPushButton("Save Image")
        self.btn_copy_image = QPushButton("Copy to Clipboard")
        self.btn_save_image.setEnabled(False)
        self.btn_copy_image.setEnabled(False)
        
        hb.addWidget(self.btn_examples)
        hb.addWidget(self.btn_generate)
        hb.addStretch(1)
        hb.addWidget(self.btn_save_image)
        hb.addWidget(self.btn_copy_image)
        bottom_layout.addLayout(hb)
        
        # Status - compact
        self.status_label = QLabel("Ready.")
        self.status_label.setMaximumHeight(20)
        bottom_layout.addWidget(self.status_label)
        
        # Output image - maximize this area
        self.output_image_label = QLabel()
        self.output_image_label.setAlignment(Qt.AlignCenter)
        self.output_image_label.setMinimumHeight(300)  # Reduced minimum
        self.output_image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output_image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        self.output_image_label.setScaledContents(False)  # We handle scaling manually
        bottom_layout.addWidget(self.output_image_label, 20)  # Increased stretch factor to take more space
        
        # Output text - much smaller
        output_text_label = QLabel("Output Text:")
        output_text_label.setMaximumHeight(15)
        bottom_layout.addWidget(output_text_label)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(40)  # Much smaller
        self.output_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        bottom_layout.addWidget(self.output_text)
        
        # Add bottom widget to splitter
        splitter.addWidget(bottom_widget)
        
        # Set initial splitter sizes (small prompt, large image area)
        splitter.setSizes([100, 600])  # 100px for prompt, 600px for rest
        splitter.setStretchFactor(0, 0)  # Don't stretch prompt section
        splitter.setStretchFactor(1, 1)  # Stretch image section
        
        # Add splitter to main layout
        v.addWidget(splitter)
        
        # Connect signals
        self.btn_examples.clicked.connect(self._open_examples)
        self.btn_generate.clicked.connect(self._generate)
        self.btn_save_image.clicked.connect(self._save_image_as)
        self.btn_copy_image.clicked.connect(self._copy_image_to_clipboard)
    
    def _init_settings_tab(self):
        """Initialize the Settings tab."""
        v = QVBoxLayout(self.tab_settings)
        
        # Provider selection
        form = QFormLayout()
        self.provider_combo = QComboBox()
        # Get available providers dynamically
        available_providers = list_providers()
        self.provider_combo.addItems(available_providers)
        if self.current_provider in available_providers:
            self.provider_combo.setCurrentText(self.current_provider)
        elif available_providers:
            self.current_provider = available_providers[0]
            self.provider_combo.setCurrentText(self.current_provider)
        form.addRow("Provider:", self.provider_combo)
        
        # Auth Mode selection (for Google provider)
        self.auth_mode_combo = QComboBox()
        self.auth_mode_combo.addItems(["API Key", "Google Cloud Account"])
        auth_mode = self.config.get("auth_mode", "API Key")
        self.auth_mode_combo.setCurrentText(auth_mode)
        form.addRow("Auth Mode:", self.auth_mode_combo)
        
        # Google Cloud Project ID (shown for Google Cloud Account mode)
        self.project_id_label = QLabel("Not detected")
        form.addRow("Project ID:", self.project_id_label)
        
        # Status field
        self.gcloud_status_label = QLabel("Not checked")
        form.addRow("Status:", self.gcloud_status_label)
        
        v.addLayout(form)
        
        # Google Cloud Setup Help (shown for Google Cloud Account mode)
        self.gcloud_help_widget = QWidget()
        gcloud_layout = QVBoxLayout(self.gcloud_help_widget)
        gcloud_layout.setContentsMargins(0, 10, 0, 0)
        
        help_label = QLabel("<b>Setup Help:</b>")
        gcloud_layout.addWidget(help_label)
        
        quick_setup = QLabel("""<b>Quick Setup:</b>
1. Install Google Cloud CLI
2. Run: <code>gcloud auth application-default login</code>
3. Click 'Check Status' below""")
        quick_setup.setWordWrap(True)
        quick_setup.setStyleSheet("QLabel { padding: 10px; background-color: #f5f5f5; }")
        gcloud_layout.addWidget(quick_setup)
        
        # Google Cloud buttons
        gcloud_buttons = QHBoxLayout()
        self.btn_check_status = QPushButton("Check Status")
        self.btn_get_gcloud = QPushButton("Get gcloud CLI")
        self.btn_cloud_console = QPushButton("Cloud Console")
        self.btn_login_help = QPushButton("Login Help")
        
        gcloud_buttons.addWidget(self.btn_check_status)
        gcloud_buttons.addWidget(self.btn_get_gcloud)
        gcloud_buttons.addWidget(self.btn_cloud_console)
        gcloud_buttons.addWidget(self.btn_login_help)
        gcloud_layout.addLayout(gcloud_buttons)
        
        v.addWidget(self.gcloud_help_widget)
        
        # API key section (hidden for Local SD and Google Cloud Account)
        self.api_key_widget = QWidget()
        api_key_layout = QVBoxLayout(self.api_key_widget)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        
        api_key_form = QFormLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        
        # Set placeholder and enabled state based on provider
        if self.current_provider == "local_sd":
            self.api_key_edit.setPlaceholderText("No API key needed for Local SD")
            self.api_key_edit.setEnabled(False)
        else:
            self.api_key_edit.setPlaceholderText("Enter API key...")
            self.api_key_edit.setEnabled(True)
            
        if self.current_api_key:
            self.api_key_edit.setText(self.current_api_key)
        api_key_form.addRow("API Key:", self.api_key_edit)
        api_key_layout.addLayout(api_key_form)
        
        # Buttons
        hb = QHBoxLayout()
        self.btn_get_key = QPushButton("Get API Key")
        self.btn_save_test = QPushButton("Test Connection")
        hb.addWidget(self.btn_get_key)
        hb.addStretch(1)
        hb.addWidget(self.btn_save_test)
        api_key_layout.addLayout(hb)
        
        v.addWidget(self.api_key_widget)
        
        # Config storage location info (visible when using API Key mode)
        self.config_location_widget = QWidget()
        config_layout = QVBoxLayout(self.config_location_widget)
        config_layout.setContentsMargins(0, 10, 0, 0)
        
        config_path = str(self.config.config_path)
        self.config_location_label = QLabel(f"Stored at: {config_path}")
        self.config_location_label.setWordWrap(True)
        self.config_location_label.setStyleSheet("color: gray; font-size: 10pt;")
        config_layout.addWidget(self.config_location_label)
        
        v.addWidget(self.config_location_widget)
        
        # Update visibility based on auth mode
        self._update_auth_visibility()
        
        # Check and display cached auth status if in Google Cloud mode
        if self.current_provider == "google" and auth_mode == "Google Cloud Account":
            if self.config.get("gcloud_auth_validated", False):
                project_id = self.config.get("gcloud_project_id", "")
                if project_id:
                    self.gcloud_status_label.setText(f"✓ Authenticated (Project: {project_id}) [cached]")
                    self.project_id_label.setText(project_id)
                else:
                    self.gcloud_status_label.setText("✓ Authenticated [cached]")
                    self.project_id_label.setText("Not set")
                self.gcloud_status_label.setStyleSheet("color: green;")
        
        # Local SD model management widget (initially hidden)
        if LocalSDWidget:
            self.local_sd_widget = LocalSDWidget()
            self.local_sd_widget.models_changed.connect(self._update_model_list)
            v.addWidget(self.local_sd_widget)
            # Show/hide based on provider
            self.local_sd_widget.setVisible(self.current_provider == "local_sd")
        else:
            self.local_sd_widget = None
        
        # Options
        self.chk_auto_copy = QCheckBox("Auto-copy saved filename to clipboard")
        self.chk_auto_copy.setChecked(self.auto_copy_filename)
        v.addWidget(self.chk_auto_copy)
        
        v.addStretch(1)
        
        # Connect signals
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.auth_mode_combo.currentTextChanged.connect(self._on_auth_mode_changed)
        self.btn_get_key.clicked.connect(self._open_api_key_page)
        self.btn_save_test.clicked.connect(self._save_and_test)
        self.chk_auto_copy.toggled.connect(self._toggle_auto_copy)
        
        # Google Cloud buttons
        self.btn_check_status.clicked.connect(self._check_gcloud_status)
        self.btn_get_gcloud.clicked.connect(self._open_gcloud_cli_page)
        self.btn_cloud_console.clicked.connect(self._open_cloud_console)
        self.btn_login_help.clicked.connect(self._show_login_help)
    
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
                """Custom page to handle external links."""
                def acceptNavigationRequest(self, url, nav_type, is_main_frame):
                    # Open external links in system browser
                    if url.scheme() in ('http', 'https', 'ftp'):
                        webbrowser.open(url.toString())
                        return False
                    return super().acceptNavigationRequest(url, nav_type, is_main_frame)
            
            # Create web view for help with full emoji support
            self.help_browser = QWebEngineView()
            self.help_browser.setPage(CustomWebPage(self.help_browser))
            
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
            
            # Home button
            self.btn_help_home = QPushButton("⌂ Home")
            self.btn_help_home.clicked.connect(lambda: self.help_browser.page().runJavaScript(
                "window.scrollTo(0, 0);"))
            self.btn_help_home.setToolTip("Go to top (Ctrl+Home)")
            nav_layout.addWidget(self.btn_help_home)
            
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
            
            # Load HTML with base URL for relative links
            self.help_browser.setHtml(html_content, QUrl("file:///"))
            
            v.addWidget(self.help_browser)
            
            # Enable initial button states
            self.btn_help_back.setEnabled(False)
            self.btn_help_forward.setEnabled(False)
            
            # Trigger initial render with minimal scroll (for QWebEngineView)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self.help_browser.page().runJavaScript("window.scrollBy(0, 1); window.scrollBy(0, -1);"))
            
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
                            # Load and display the markdown file
                            content = full_path.read_text(encoding='utf-8')
                            
                            # Convert to HTML and display
                            parent = self.parent()
                            while parent and not hasattr(parent, '_markdown_to_html_with_anchors'):
                                parent = parent.parent()
                            
                            if parent:
                                # Add a "Back to README" link at the top if not viewing README
                                if 'README' not in file_path.upper():
                                    back_link = '<p><a href="README.md">← Back to README</a></p><hr>'
                                    content = back_link + '\n\n' + content
                                
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
                    self._navigating_history = True
                    self.history_index -= 1
                    anchor = self.anchor_history[self.history_index]
                    
                    # Use QTimer to delay scrolling to avoid focus-related timing issues
                    def do_scroll():
                        if anchor:
                            self.scrollToAnchor(anchor)
                        else:
                            # Scroll to top
                            self.verticalScrollBar().setValue(0)
                        self._navigating_history = False
                    
                    # Small delay to let Qt process focus events
                    QTimer.singleShot(10, do_scroll)
                    self.update_nav_buttons()
            
            def go_forward(self):
                """Navigate forward in history."""
                if self.history_index < len(self.anchor_history) - 1:
                    from PySide6.QtCore import QTimer
                    self._navigating_history = True
                    self.history_index += 1
                    anchor = self.anchor_history[self.history_index]
                    
                    # Use QTimer to delay scrolling to avoid focus-related timing issues
                    def do_scroll():
                        if anchor:
                            self.scrollToAnchor(anchor)
                        else:
                            # Scroll to top
                            self.verticalScrollBar().setValue(0)
                        self._navigating_history = False
                    
                    # Small delay to let Qt process focus events
                    QTimer.singleShot(10, do_scroll)
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
    
    def _markdown_to_html_with_anchors(self, markdown_text: str, use_webengine: bool = False) -> str:
        """Convert markdown to HTML with proper GitHub-style anchor IDs."""
        try:
            # Try to use the markdown library if available
            import markdown
            from markdown.extensions.toc import TocExtension
            
            # Configure to generate GitHub-style anchors
            md = markdown.Markdown(extensions=[
                'fenced_code',
                'tables',
                TocExtension(slugify=self._github_slugify),
            ])
            
            # Process the markdown
            html_body = md.convert(markdown_text)
            
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
        self.btn_insert_prompt = QPushButton("Insert into Prompt")
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
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        
        v = QVBoxLayout(self.tab_history)
        
        # Create table widget for better organization
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Time", "Provider", "Model", "Prompt", "Resolution", "Cost"
        ])
        
        # Configure table
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSortingEnabled(True)
        
        # Set column widths
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Time
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Provider
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Model
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # Prompt - takes remaining space
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Resolution
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Cost
        
        # Populate table with history
        self.history_table.setRowCount(len(self.history))
        for row, item in enumerate(self.history):
            if isinstance(item, dict):
                # Parse timestamp
                timestamp = item.get('timestamp', '')
                date_str = time_str = ''
                if isinstance(timestamp, float):
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp)
                    date_str = dt.strftime("%Y-%m-%d")
                    time_str = dt.strftime("%H:%M:%S")
                elif isinstance(timestamp, str) and 'T' in timestamp:
                    # ISO format
                    parts = timestamp.split('T')
                    date_str = parts[0]
                    time_str = parts[1].split('.')[0] if len(parts) > 1 else ''
                
                # Date column
                date_item = QTableWidgetItem(date_str)
                self.history_table.setItem(row, 0, date_item)
                
                # Time column
                time_item = QTableWidgetItem(time_str)
                self.history_table.setItem(row, 1, time_item)
                
                # Provider column
                provider = item.get('provider', '')
                provider_item = QTableWidgetItem(provider.title() if provider else 'Unknown')
                self.history_table.setItem(row, 2, provider_item)
                
                # Model column
                model = item.get('model', '')
                model_display = model.split('/')[-1] if '/' in model else model  # Simplify model names
                model_item = QTableWidgetItem(model_display)
                model_item.setToolTip(model)  # Full model name in tooltip
                self.history_table.setItem(row, 3, model_item)
                
                # Prompt column
                prompt = item.get('prompt', 'No prompt')
                prompt_item = QTableWidgetItem(prompt[:100] + '...' if len(prompt) > 100 else prompt)
                prompt_item.setToolTip(f"Full prompt:\n{prompt}")
                self.history_table.setItem(row, 4, prompt_item)
                
                # Resolution column
                width = item.get('width', '')
                height = item.get('height', '')
                resolution = f"{width}x{height}" if width and height else ''
                resolution_item = QTableWidgetItem(resolution)
                self.history_table.setItem(row, 5, resolution_item)
                
                # Cost column
                cost = item.get('cost', 0.0)
                cost_str = f"${cost:.4f}" if cost > 0 else '-'
                cost_item = QTableWidgetItem(cost_str)
                self.history_table.setItem(row, 6, cost_item)
                
                # Store the history item data in the first column for easy retrieval
                date_item.setData(Qt.UserRole, item)
        
        v.addWidget(QLabel(f"History ({len(self.history)} items):"))
        v.addWidget(self.history_table)
        
        # Buttons
        h = QHBoxLayout()
        self.btn_load_history = QPushButton("Load Selected")
        self.btn_clear_history = QPushButton("Clear History")
        h.addWidget(self.btn_load_history)
        h.addStretch()
        h.addWidget(self.btn_clear_history)
        v.addLayout(h)
        
        # Connect signals
        self.history_table.selectionModel().selectionChanged.connect(self._on_history_selection_changed)
        self.history_table.itemDoubleClicked.connect(self._load_history_item)
        self.btn_load_history.clicked.connect(self._load_selected_history)
        self.btn_clear_history.clicked.connect(self._clear_history)
    
    def _update_model_list(self):
        """Update model combo box based on current provider."""
        self.model_combo.clear()
        
        try:
            # Get provider instance to fetch available models
            provider = get_provider(self.current_provider, {"api_key": ""})
            models = provider.get_models()
            
            # Add model IDs to the combo box
            if models:
                self.model_combo.addItems(list(models.keys()))
                
                # Set default model
                default_model = provider.get_default_model()
                if default_model in models:
                    self.model_combo.setCurrentText(default_model)
        except Exception as e:
            # Fallback to some basic models if provider fails to load
            print(f"Error loading models for {self.current_provider}: {e}")
            if self.current_provider == "google":
                self.model_combo.addItems(["gemini-2.5-flash-image-preview"])
            elif self.current_provider == "openai":
                self.model_combo.addItems(["dall-e-3"])
            elif self.current_provider == "stability":
                self.model_combo.addItems(["stable-diffusion-xl-1024-v1-0"])
            elif self.current_provider == "local_sd":
                self.model_combo.addItems(["stabilityai/stable-diffusion-2-1"])
    
    def _update_advanced_visibility(self):
        """Show/hide advanced settings based on provider."""
        # Update new advanced panel if available
        if hasattr(self, 'advanced_panel') and self.advanced_panel:
            self.advanced_panel.update_provider(self.current_provider)
        # Update old advanced group for fallback
        elif hasattr(self, 'advanced_group'):
            # Only show for local_sd provider
            self.advanced_group.setVisible(self.current_provider == "local_sd")
    
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
        """Handle provider change."""
        self.current_provider = provider.lower()
        self.config.set("provider", self.current_provider)
        self.config.save()
        
        # Update new widgets if available
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            self.resolution_selector.update_provider(self.current_provider)
        if hasattr(self, 'quality_selector') and self.quality_selector:
            self.quality_selector.update_provider(self.current_provider)
        if hasattr(self, 'advanced_panel') and self.advanced_panel:
            self.advanced_panel.update_provider(self.current_provider)
        
        # Update cost estimate
        self._update_cost_estimate()
        
        # Update API key field
        self.current_api_key = self.config.get_api_key(self.current_provider)
        self.api_key_edit.setText(self.current_api_key or "")
        
        # Update auth visibility
        self._update_auth_visibility()
        
        # Update Local SD widget visibility
        if hasattr(self, 'local_sd_widget') and self.local_sd_widget:
            self.local_sd_widget.setVisible(self.current_provider == "local_sd")
    
    def _on_aspect_ratio_changed(self, ratio: str):
        """Handle aspect ratio change."""
        # Store for use in generation
        self.current_aspect_ratio = ratio
        # Could update resolution options based on aspect ratio
        self._update_cost_estimate()
    
    def _on_resolution_changed(self, resolution: str):
        """Handle resolution change."""
        self.current_resolution = resolution
        self._update_cost_estimate()
    
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
        self.project_id_label.setVisible(show_gcloud)
        self.gcloud_status_label.setVisible(show_gcloud)
        self.gcloud_help_widget.setVisible(show_gcloud)
        
        # Show API key fields for API Key mode or non-Google providers
        show_api_key = (not is_google or not is_gcloud_auth) and self.current_provider != "local_sd"
        self.api_key_widget.setVisible(show_api_key)
        self.config_location_widget.setVisible(show_api_key)
    
    def _on_auth_mode_changed(self, auth_mode: str):
        """Handle auth mode change."""
        self.config.set("auth_mode", auth_mode)
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
                    self.project_id_label.setText(project_id)
                    self.gcloud_status_label.setText("✓ Authenticated")
                    self.gcloud_status_label.setStyleSheet("color: green;")
                else:
                    self.project_id_label.setText("Not set")
                    self.gcloud_status_label.setText("✓ Authenticated (no project)")
                    self.gcloud_status_label.setStyleSheet("color: orange;")
                
                # Save the auth validation status
                self.config.set("gcloud_auth_validated", True)
                if project_id:
                    self.config.set("gcloud_project_id", project_id)
                self.config.save()
            else:
                self.project_id_label.setText("Not detected")
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
            self.project_id_label.setText("Error")
            self.gcloud_status_label.setText(f"✗ Error: {str(e)[:50]}")
            self.gcloud_status_label.setStyleSheet("color: red;")
    
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
    
    def _generate(self):
        """Generate image from prompt."""
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, APP_NAME, "Please enter a prompt.")
            return
        
        if not self.current_api_key and self.current_provider != "local_sd":
            QMessageBox.warning(self, APP_NAME, "Please set an API key in Settings.")
            return
        
        # Disable/reset buttons
        self.btn_generate.setEnabled(False)
        self.btn_save_image.setEnabled(False)
        self.btn_copy_image.setEnabled(False)
        self.status_label.setText("Generating...")
        self.output_text.clear()
        self.output_image_label.clear()
        self.current_image_data = None
        
        # Get current model
        model = self.model_combo.currentText()
        
        # Gather all generation parameters
        kwargs = {}
        
        # Get resolution settings
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            resolution = self.resolution_selector.get_resolution()
            if resolution and 'x' in resolution:
                width, height = map(int, resolution.split('x'))
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
        
        # Get aspect ratio (for providers that support it)
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
        
        # Create worker thread
        self.gen_thread = QThread()
        self.gen_worker = GenWorker(
            provider=self.current_provider,
            model=model,
            prompt=prompt,
            auth_mode="api-key",
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
        self.current_prompt = prompt
        self.current_model = model
    
    def _on_progress(self, message: str):
        """Handle progress update."""
        self.status_label.setText(message)
    
    def _on_error(self, error: str):
        """Handle generation error."""
        self.status_label.setText("Error occurred.")
        QMessageBox.critical(self, APP_NAME, f"Generation failed:\n{error}")
        self.btn_generate.setEnabled(True)
        self._cleanup_thread()
    
    def _on_generation_finished(self, texts: List[str], images: List[bytes]):
        """Handle successful generation."""
        self.status_label.setText("Generation complete.")
        
        # Display text output
        if texts:
            self.output_text.setPlainText("\n".join(texts))
        
        # Display and save images
        if images:
            # Save images
            stub = sanitize_stub_from_prompt(self.current_prompt)
            saved_paths = auto_save_images(images, base_stub=stub)
            
            # Calculate cost for this generation
            generation_cost = 0.0
            settings = {}
            settings["num_images"] = len(images)
            
            # Get resolution from image data if possible
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(images[0]))
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
            
            # Display first image
            self.current_image_data = images[0]
            self._display_image(images[0])
            if saved_paths:
                self._last_displayed_image_path = saved_paths[0]  # Track last displayed image
            
            # Enable save/copy buttons
            self.btn_save_image.setEnabled(True)
            self.btn_copy_image.setEnabled(True)
            
            # Update history with the new generation
            self.history_paths = scan_disk_history()
            
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
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            
            # Get the label's current size
            label_size = self.output_image_label.size()
            
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
                            idx = self.model_combo.findText(metadata['model'])
                            if idx >= 0:
                                self.model_combo.setCurrentIndex(idx)
                        
                        # Restore provider
                        if 'provider' in metadata and metadata['provider'] != self.current_provider:
                            idx = self.provider_combo.findText(metadata['provider'])
                            if idx >= 0:
                                self.provider_combo.setCurrentIndex(idx)
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
                'model': self.model_combo.currentText(),
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
                idx = self.model_combo.findText(project_data['model'])
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
    
    def resizeEvent(self, event):
        """Handle window resize to scale images appropriately."""
        super().resizeEvent(event)
        
        # If we have an image displayed, rescale it to fit the new size
        if hasattr(self, 'output_image_label'):
            original_pixmap = self.output_image_label.property("original_pixmap")
            if original_pixmap and isinstance(original_pixmap, QPixmap):
                # Rescale the original pixmap to fit the new label size
                label_size = self.output_image_label.size()
                scaled = original_pixmap.scaled(
                    label_size.width() - 4,  # Account for border
                    label_size.height() - 4,  # Account for border
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.output_image_label.setPixmap(scaled)
    
    def closeEvent(self, event):
        """Save all UI state on close."""
        try:
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
                        self.current_image_data = image_data
                        self._last_displayed_image_path = path  # Track last displayed image
                        
                        # Display in output label
                        pixmap = QPixmap()
                        if pixmap.loadFromData(image_data):
                            # Scale to fit the label while maintaining aspect ratio
                            # Use the label's current size for better fit
                            label_size = self.output_image_label.size()
                            scaled = pixmap.scaled(
                                label_size.width() - 4,  # Account for border
                                label_size.height() - 4,  # Account for border
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            self.output_image_label.setPixmap(scaled)
                            
                            # Store the original pixmap for resizing
                            self.output_image_label.setProperty("original_pixmap", pixmap)
                        
                        # Enable save and copy buttons since we have an image
                        self.btn_save_image.setEnabled(True)
                        self.btn_copy_image.setEnabled(True)
                        
                        # Load metadata
                        prompt = history_item.get('prompt', '')
                        self.prompt_edit.setPlainText(prompt)
                        
                        # Load model if available
                        model = history_item.get('model', '')
                        if model:
                            idx = self.model_combo.findText(model)
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
        # If switching to help tab, trigger a minimal scroll to fix rendering
        if self.tabs.widget(index) == self.tab_help:
            self._trigger_help_render()
    
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
    
    def _save_ui_state(self):
        """Save all UI widget states to config."""
        ui_state = {}
        
        try:
            # Current tab index
            ui_state['current_tab'] = self.tabs.currentIndex()
            
            # Generate tab settings
            ui_state['prompt'] = self.prompt_edit.toPlainText()
            ui_state['model'] = self.model_combo.currentText()
            ui_state['model_index'] = self.model_combo.currentIndex()
            
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
            
            # Settings tab
            ui_state['provider'] = self.current_provider
            if hasattr(self, 'provider_combo'):
                ui_state['provider_index'] = self.provider_combo.currentIndex()
            
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
            
            # Output text height
            if hasattr(self, 'output_text'):
                ui_state['output_text_height'] = self.output_text.height()
            
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
                idx = self.model_combo.findText(ui_state['model'])
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
            
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
            
            # Restore provider selection
            if 'provider_index' in ui_state and hasattr(self, 'provider_combo'):
                if ui_state['provider_index'] < self.provider_combo.count():
                    self.provider_combo.setCurrentIndex(ui_state['provider_index'])
            elif 'provider' in ui_state:
                self.current_provider = ui_state['provider']
            
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
            
            # Restore output text height
            if 'output_text_height' in ui_state and hasattr(self, 'output_text'):
                self.output_text.setMaximumHeight(ui_state['output_text_height'])
            
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
                # Parse timestamp
                timestamp = item.get('timestamp', '')
                date_str = time_str = ''
                if isinstance(timestamp, float):
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp)
                    date_str = dt.strftime("%Y-%m-%d")
                    time_str = dt.strftime("%H:%M:%S")
                elif isinstance(timestamp, str) and 'T' in timestamp:
                    # ISO format
                    parts = timestamp.split('T')
                    date_str = parts[0]
                    time_str = parts[1].split('.')[0] if len(parts) > 1 else ''
                
                # Date column
                from PySide6.QtWidgets import QTableWidgetItem
                date_item = QTableWidgetItem(date_str)
                self.history_table.setItem(row, 0, date_item)
                
                # Time column
                time_item = QTableWidgetItem(time_str)
                self.history_table.setItem(row, 1, time_item)
                
                # Provider column
                provider = item.get('provider', '')
                provider_item = QTableWidgetItem(provider.title() if provider else 'Unknown')
                self.history_table.setItem(row, 2, provider_item)
                
                # Model column
                model = item.get('model', '')
                model_display = model.split('/')[-1] if '/' in model else model
                model_item = QTableWidgetItem(model_display)
                model_item.setToolTip(model)
                self.history_table.setItem(row, 3, model_item)
                
                # Prompt column
                prompt = item.get('prompt', 'No prompt')
                prompt_item = QTableWidgetItem(prompt[:100] + '...' if len(prompt) > 100 else prompt)
                prompt_item.setToolTip(f"Full prompt:\n{prompt}")
                self.history_table.setItem(row, 4, prompt_item)
                
                # Resolution column
                width = item.get('width', '')
                height = item.get('height', '')
                resolution = f"{width}x{height}" if width and height else ''
                resolution_item = QTableWidgetItem(resolution)
                self.history_table.setItem(row, 5, resolution_item)
                
                # Cost column
                cost = item.get('cost', 0.0)
                cost_str = f"${cost:.4f}" if cost > 0 else '-'
                cost_item = QTableWidgetItem(cost_str)
                self.history_table.setItem(row, 6, cost_item)
                
                # Store the history item data in the first column for easy retrieval
                date_item.setData(Qt.UserRole, item)