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
        self.setWindowTitle(APP_NAME)
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
        self.output_image_label.setMinimumHeight(300)
        self.output_image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output_image_label.setStyleSheet("border: 1px solid #ccc;")
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
        
        self.help_browser = QTextBrowser()
        self.help_browser.setOpenExternalLinks(True)
        
        # Load help text
        help_text = f"""
        <h2>ImageAI v{VERSION}</h2>
        <p>AI Image Generation Tool</p>
        
        <h3>Quick Start</h3>
        <ol>
        <li>Get an API key from your provider</li>
        <li>Enter the key in Settings tab</li>
        <li>Enter a prompt in Generate tab</li>
        <li>Click Generate</li>
        </ol>
        
        <h3>Providers</h3>
        <ul>
        <li><b>Google Gemini</b> - Advanced image generation</li>
        <li><b>OpenAI DALL-E</b> - Creative image generation</li>
        <li><b>Stability AI</b> - Stable Diffusion models (API)</li>
        <li><b>Local SD</b> - Run Stable Diffusion locally (no API key needed)</li>
        </ul>
        
        <h3>Tips</h3>
        <ul>
        <li>Be specific in your prompts</li>
        <li>Use the Examples button for inspiration</li>
        <li>Images are auto-saved to the config directory</li>
        </ul>
        """
        
        self.help_browser.setHtml(help_text)
        v.addWidget(self.help_browser)
    
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
            scaled = pixmap.scaled(
                self.output_image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.output_image_label.setPixmap(scaled)
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
                            scaled = pixmap.scaled(
                                self.output_image_label.size(),
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            self.output_image_label.setPixmap(scaled)
                        
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