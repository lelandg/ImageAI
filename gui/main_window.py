"""Main window for ImageAI GUI."""

import webbrowser
from pathlib import Path
from typing import Optional, List
from datetime import datetime

try:
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QPixmap, QAction
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QLabel, QTextEdit, QPushButton, QComboBox, QLineEdit,
        QFormLayout, QSizePolicy, QMessageBox, QFileDialog,
        QCheckBox, QTextBrowser, QListWidget, QDialog, QSpinBox,
        QDoubleSpinBox, QGroupBox
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
        
        # Restore window geometry
        self._restore_geometry()
    
    def _load_history_from_disk(self):
        """Load history from disk into memory."""
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
                        'provider': sidecar.get('provider', '')
                    })
                else:
                    # No sidecar, just add path
                    self.history.append({
                        'path': path,
                        'prompt': path.stem.replace('_', ' '),
                        'timestamp': path.stat().st_mtime
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
        
        # Add History tab if there's history
        if self.history:
            self.tabs.addTab(self.tab_history, "History")
        
        self._init_generate_tab()
        self._init_templates_tab()
        self._init_settings_tab()
        self._init_help_tab()
        if self.history:
            self._init_history_tab()
        
        # Connect tab change signal to handle help tab rendering
        self.tabs.currentChanged.connect(self._on_tab_changed)
    
    def _init_menu(self):
        """Initialize menu bar."""
        mb = self.menuBar()
        file_menu = mb.addMenu("File")
        
        act_save = QAction("Save Image As...", self)
        act_save.triggered.connect(self._save_image_as)
        file_menu.addAction(act_save)
        
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)
    
    def _init_generate_tab(self):
        """Initialize the Generate tab."""
        v = QVBoxLayout(self.tab_generate)
        
        # Model selection
        form = QFormLayout()
        self.model_combo = QComboBox()
        self._update_model_list()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        form.addRow("Model:", self.model_combo)
        
        # Prompt input
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Describe what to generate...")
        self.prompt_edit.setAcceptRichText(False)
        self.prompt_edit.setMaximumHeight(100)
        form.addRow("Prompt:", self.prompt_edit)
        v.addLayout(form)
        
        # Advanced settings group (collapsible)
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QFormLayout()
        
        # Resolution dropdown
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "Auto (based on model)",
            "512x512 (SD 1.x/2.x)",
            "768x768 (SD 1.x/2.x HQ)",
            "1024x1024 (SDXL)"
        ])
        self.resolution_combo.setCurrentIndex(0)  # Default to Auto
        advanced_layout.addRow("Resolution:", self.resolution_combo)
        
        # Steps spinner (for Local SD)
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(1, 50)
        self.steps_spin.setValue(20)  # Default to 20 for better balance
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
        v.addWidget(advanced_group)
        
        # Hide advanced settings for non-local providers initially
        self.advanced_group = advanced_group
        self._update_advanced_visibility()
        
        # Buttons
        hb = QHBoxLayout()
        self.btn_examples = QPushButton("Examples")
        self.btn_generate = QPushButton("Generate")
        hb.addWidget(self.btn_examples)
        hb.addStretch(1)
        hb.addWidget(self.btn_generate)
        v.addLayout(hb)
        
        # Status
        self.status_label = QLabel("Ready.")
        v.addWidget(self.status_label)
        
        # Output image
        self.output_image_label = QLabel()
        self.output_image_label.setAlignment(Qt.AlignCenter)
        self.output_image_label.setMinimumHeight(400)
        self.output_image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output_image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        self.output_image_label.setScaledContents(False)  # We handle scaling manually
        v.addWidget(self.output_image_label, 10)
        
        # Output text
        v.addWidget(QLabel("Output Text:"))
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(100)
        v.addWidget(self.output_text)
        
        # Output actions
        hb_output = QHBoxLayout()
        self.btn_save_image = QPushButton("Save Image")
        self.btn_copy_image = QPushButton("Copy to Clipboard")
        self.btn_save_image.setEnabled(False)
        self.btn_copy_image.setEnabled(False)
        hb_output.addWidget(self.btn_save_image)
        hb_output.addWidget(self.btn_copy_image)
        hb_output.addStretch()
        v.addLayout(hb_output)
        
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
        
        # API key section (hidden for Local SD)
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
        self.btn_save_test = QPushButton("Save & Test")
        hb.addWidget(self.btn_get_key)
        hb.addStretch(1)
        hb.addWidget(self.btn_save_test)
        api_key_layout.addLayout(hb)
        
        v.addLayout(form)
        v.addWidget(self.api_key_widget)
        
        # Local SD model management widget (initially hidden)
        if LocalSDWidget:
            self.local_sd_widget = LocalSDWidget()
            self.local_sd_widget.models_changed.connect(self._update_model_list)
            v.addWidget(self.local_sd_widget)
            # Show/hide based on provider
            self.local_sd_widget.setVisible(self.current_provider == "local_sd")
            self.api_key_widget.setVisible(self.current_provider != "local_sd")
        else:
            self.local_sd_widget = None
        
        # Options
        self.chk_auto_copy = QCheckBox("Auto-copy filename to clipboard")
        self.chk_auto_copy.setChecked(self.auto_copy_filename)
        v.addWidget(self.chk_auto_copy)
        
        v.addStretch(1)
        
        # Connect signals
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.btn_get_key.clicked.connect(self._open_api_key_page)
        self.btn_save_test.clicked.connect(self._save_and_test)
        self.chk_auto_copy.toggled.connect(self._toggle_auto_copy)
    
    def _init_help_tab(self):
        """Initialize the Help tab."""
        v = QVBoxLayout(self.tab_help)
        
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
            
            # Add navigation toolbar
            nav_layout = QHBoxLayout()
            
            # Create web view for help with full emoji support
            self.help_browser = QWebEngineView()
            self.help_browser.setPage(CustomWebPage(self.help_browser))
            
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
            v.addLayout(nav_layout)
            
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
                
                # Check if it's an external link
                if url.scheme() in ('http', 'https', 'ftp'):
                    webbrowser.open(url.toString())
                    return
                
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
        
        # Add navigation toolbar
        nav_layout = QHBoxLayout()
        
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
        v.addLayout(nav_layout)
        
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
        
        # Template selection
        h = QHBoxLayout()
        h.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "Photorealistic Portrait",
            "Fantasy Landscape", 
            "Sci-Fi Scene",
            "Abstract Art",
            "Product Photography",
            "Architectural Render",
            "Character Design",
            "Logo Design"
        ])
        h.addWidget(self.template_combo, 1)
        self.btn_apply_template = QPushButton("Apply Template")
        h.addWidget(self.btn_apply_template)
        v.addLayout(h)
        
        # Template preview
        self.template_preview = QTextEdit()
        self.template_preview.setReadOnly(True)
        self.template_preview.setPlaceholderText("Template preview will appear here...")
        v.addWidget(self.template_preview)
        
        # Connect signals
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        self.btn_apply_template.clicked.connect(self._apply_template)
        
        # Load initial template
        self._on_template_changed(self.template_combo.currentText())
    
    def _init_history_tab(self):
        """Initialize history tab."""
        v = QVBoxLayout(self.tab_history)
        
        # History list
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        
        # Add history items
        for item in self.history:
            if isinstance(item, dict):
                display_text = f"{item.get('timestamp', 'Unknown time')} - {item.get('prompt', 'No prompt')[:50]}..."
            else:
                display_text = str(item)
            self.history_list.addItem(display_text)
        
        v.addWidget(QLabel(f"History ({len(self.history)} items):"))
        v.addWidget(self.history_list)
        
        # Buttons
        h = QHBoxLayout()
        self.btn_load_history = QPushButton("Load Selected")
        self.btn_clear_history = QPushButton("Clear History")
        h.addWidget(self.btn_load_history)
        h.addStretch()
        h.addWidget(self.btn_clear_history)
        v.addLayout(h)
        
        # Connect signals
        self.history_list.itemSelectionChanged.connect(self._on_history_selection_changed)
        self.history_list.itemDoubleClicked.connect(self._load_history_item)
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
        if hasattr(self, 'advanced_group'):
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
        
        # Update API key field
        self.current_api_key = self.config.get_api_key(self.current_provider)
        self.api_key_edit.setText(self.current_api_key or "")
        
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
        
        # Get advanced parameters for Local SD
        kwargs = {}
        if self.current_provider == "local_sd":
            # Get resolution
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
            # else Auto - let provider decide
            
            # Get steps and guidance
            kwargs['steps'] = self.steps_spin.value()
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
            
            # Save metadata
            for path in saved_paths:
                meta = {
                    "prompt": self.current_prompt,
                    "provider": self.current_provider,
                    "model": self.current_model,
                    "timestamp": datetime.now().isoformat(),
                }
                write_image_sidecar(path, meta)
            
            # Display first image
            self.current_image_data = images[0]
            self._display_image(images[0])
            
            # Enable save/copy buttons
            self.btn_save_image.setEnabled(True)
            self.btn_copy_image.setEnabled(True)
            
            # Update history
            self.history_paths = scan_disk_history()
            
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
            
            # Scale to fit label while maintaining aspect ratio
            label_size = self.output_image_label.size()
            scaled = pixmap.scaled(
                label_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.output_image_label.setPixmap(scaled)
            
            # Store the original pixmap for potential resizing
            self.output_image_label.setProperty("original_pixmap", pixmap)
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
                    label_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.output_image_label.setPixmap(scaled)
    
    def closeEvent(self, event):
        """Save geometry on close."""
        try:
            geo = {
                "x": self.x(),
                "y": self.y(),
                "w": self.width(),
                "h": self.height(),
            }
            self.config.set("window_geometry", geo)
            self.config.save()
        except Exception:
            pass
        
        # Clean up thread if running
        self._cleanup_thread()
    
    def _on_template_changed(self, template_name: str):
        """Handle template selection change."""
        templates = {
            "Photorealistic Portrait": "Ultra-realistic portrait of {subject}, professional photography, studio lighting, 8K resolution, highly detailed",
            "Fantasy Landscape": "Epic fantasy landscape with {feature}, magical atmosphere, vibrant colors, detailed environment, concept art style",
            "Sci-Fi Scene": "Futuristic {scene} with advanced technology, cyberpunk aesthetic, neon lights, detailed sci-fi environment",
            "Abstract Art": "Abstract {concept} artwork, modern art style, bold colors, dynamic composition, artistic interpretation",
            "Product Photography": "Professional product photo of {product}, white background, studio lighting, commercial photography",
            "Architectural Render": "Architectural visualization of {building}, photorealistic render, modern design, detailed materials",
            "Character Design": "Character design of {character}, concept art, detailed costume, full body view, professional illustration",
            "Logo Design": "Minimalist logo design for {company}, vector style, clean lines, professional branding"
        }
        
        template_text = templates.get(template_name, "")
        self.template_preview.setPlainText(template_text)
    
    def _apply_template(self):
        """Apply selected template to prompt."""
        template_text = self.template_preview.toPlainText()
        if template_text:
            self.prompt_edit.setPlainText(template_text)
            self.tabs.setCurrentWidget(self.tab_generate)
    
    def _on_history_selection_changed(self):
        """Handle history selection change - display the image."""
        items = self.history_list.selectedItems()
        if not items:
            return
        
        # Get the selected history item
        index = self.history_list.row(items[0])
        if 0 <= index < len(self.history):
            history_item = self.history[index]
            if isinstance(history_item, dict):
                path = history_item.get('path')
                if path and path.exists():
                    try:
                        # Read and display the image
                        image_data = path.read_bytes()
                        self.current_image_data = image_data
                        
                        # Display in output label
                        pixmap = QPixmap()
                        if pixmap.loadFromData(image_data):
                            # Scale to fit the label while maintaining aspect ratio
                            # Use the label's current size for better fit
                            label_size = self.output_image_label.size()
                            scaled = pixmap.scaled(
                                label_size,
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
        current_item = self.history_list.currentItem()
        if current_item:
            self._load_history_item(current_item)
    
    def _clear_history(self):
        """Clear history."""
        reply = QMessageBox.question(
            self, APP_NAME, 
            "Clear all history?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.history.clear()
            self.history_list.clear()
    
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