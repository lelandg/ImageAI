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
        QCheckBox, QTextBrowser, QListWidget
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
        self.current_prompt: str = ""
        self.gen_thread: Optional[QThread] = None
        self.gen_worker: Optional[GenWorker] = None
        self.current_image_data: Optional[bytes] = None
        self._last_template_context: Optional[dict] = None
        
        # Create UI
        self._init_ui()
        self._init_menu()
        
        # Restore window geometry
        self._restore_geometry()
    
    def _init_ui(self):
        """Initialize the user interface."""
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Create tabs
        self.tab_generate = QWidget()
        self.tab_settings = QWidget()
        self.tab_help = QWidget()
        
        self.tabs.addTab(self.tab_generate, "Generate")
        self.tabs.addTab(self.tab_settings, "Settings")
        self.tabs.addTab(self.tab_help, "Help")
        
        self._init_generate_tab()
        self._init_settings_tab()
        self._init_help_tab()
    
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
        form.addRow("Model:", self.model_combo)
        
        # Prompt input
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Describe what to generate...")
        self.prompt_edit.setAcceptRichText(False)
        self.prompt_edit.setMaximumHeight(100)
        form.addRow("Prompt:", self.prompt_edit)
        v.addLayout(form)
        
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
        
        # Connect signals
        self.btn_examples.clicked.connect(self._open_examples)
        self.btn_generate.clicked.connect(self._generate)
    
    def _init_settings_tab(self):
        """Initialize the Settings tab."""
        v = QVBoxLayout(self.tab_settings)
        
        # Provider selection
        form = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["google", "openai"])
        self.provider_combo.setCurrentText(self.current_provider)
        form.addRow("Provider:", self.provider_combo)
        
        # API key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Enter API key...")
        if self.current_api_key:
            self.api_key_edit.setText(self.current_api_key)
        form.addRow("API Key:", self.api_key_edit)
        
        v.addLayout(form)
        
        # Buttons
        hb = QHBoxLayout()
        self.btn_get_key = QPushButton("Get API Key")
        self.btn_save_test = QPushButton("Save & Test")
        hb.addWidget(self.btn_get_key)
        hb.addStretch(1)
        hb.addWidget(self.btn_save_test)
        v.addLayout(hb)
        
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
    
    def _update_model_list(self):
        """Update model combo box based on current provider."""
        self.model_combo.clear()
        
        if self.current_provider == "openai":
            self.model_combo.addItems(["dall-e-3", "dall-e-2"])
        else:
            self.model_combo.addItems([
                "gemini-2.5-flash-image-preview",
                "gemini-2.5-flash",
                "gemini-2.5-pro"
            ])
    
    def _on_provider_changed(self, provider: str):
        """Handle provider change."""
        self.current_provider = provider.lower()
        self.config.set("provider", self.current_provider)
        self.config.save()
        
        # Update API key field
        self.current_api_key = self.config.get_api_key(self.current_provider)
        self.api_key_edit.setText(self.current_api_key or "")
        
        # Update model list
        self._update_model_list()
    
    def _open_api_key_page(self):
        """Open API key documentation page."""
        from core import get_api_key_url
        url = get_api_key_url(self.current_provider)
        try:
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Could not open browser: {e}")
    
    def _save_and_test(self):
        """Save API key and test connection."""
        key = self.api_key_edit.text().strip()
        if not key:
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
        
        if not self.current_api_key:
            QMessageBox.warning(self, APP_NAME, "Please set an API key in Settings.")
            return
        
        # Disable generate button
        self.btn_generate.setEnabled(False)
        self.status_label.setText("Generating...")
        self.output_text.clear()
        self.current_image_data = None
        
        # Get current model
        model = self.model_combo.currentText()
        
        # Create worker thread
        self.gen_thread = QThread()
        self.gen_worker = GenWorker(
            provider=self.current_provider,
            model=model,
            prompt=prompt,
            auth_mode="api-key"
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
        
        event.accept()