"""Local SD model management widget for embedding in Settings tab."""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QProgressBar, QGroupBox,
    QMessageBox, QListWidget, QListWidgetItem, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCursor

from providers.model_info import ModelInfo

logger = logging.getLogger(__name__)


class ModelDownloadThread(QThread):
    """Thread for downloading models."""
    
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool)
    
    def __init__(self, model_id: str, cache_dir: Path):
        super().__init__()
        self.model_id = model_id
        self.cache_dir = cache_dir
    
    def run(self):
        """Download the model."""
        try:
            from huggingface_hub import snapshot_download, HfFolder
            
            self.status.emit(f"Downloading {self.model_id}...")
            
            # Use token if available
            token = HfFolder.get_token()
            
            snapshot_download(
                repo_id=self.model_id,
                cache_dir=self.cache_dir,
                resume_download=True,
                ignore_patterns=["*.md", "*.txt", ".gitattributes"],
                token=token
            )
            
            self.status.emit(f"✓ Downloaded {self.model_id}")
            self.finished.emit(True)
            
        except ImportError:
            self.status.emit("Error: huggingface_hub not installed")
            self.finished.emit(False)
        except Exception as e:
            self.status.emit(f"Error: {str(e)}")
            self.finished.emit(False)


class LocalSDWidget(QWidget):
    """Widget for managing Local SD models."""
    
    models_changed = Signal()  # Emitted when models are installed/removed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache_dir = Path.home() / ".cache" / "huggingface"
        self.download_thread = None
        self._init_ui()
        self._check_hf_auth()
        self._refresh_models()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # HuggingFace authentication section
        auth_group = QGroupBox("HuggingFace Authentication")
        auth_layout = QVBoxLayout(auth_group)
        
        # Status label
        self.auth_status_label = QLabel("Checking authentication...")
        auth_layout.addWidget(self.auth_status_label)
        
        # Token input section
        self.token_widget = QWidget()
        token_layout = QVBoxLayout(self.token_widget)
        token_layout.setContentsMargins(0, 0, 0, 0)
        
        # Token input row
        token_input_layout = QHBoxLayout()
        token_input_layout.addWidget(QLabel("Token:"))
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setPlaceholderText("Paste your HuggingFace token here (starts with hf_)")
        token_input_layout.addWidget(self.token_input)
        
        self.save_token_btn = QPushButton("Save Token")
        self.save_token_btn.clicked.connect(self._save_token)
        token_input_layout.addWidget(self.save_token_btn)
        
        token_layout.addLayout(token_input_layout)
        
        # Get token button row
        get_token_layout = QHBoxLayout()
        get_token_layout.addWidget(QLabel("Don't have a token?"))
        
        self.get_token_btn = QPushButton("Get Token from HuggingFace")
        self.get_token_btn.setStyleSheet("QPushButton { color: #0066cc; text-decoration: underline; border: none; text-align: left; }")
        self.get_token_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.get_token_btn.clicked.connect(self._open_hf_token_page)
        get_token_layout.addWidget(self.get_token_btn)
        get_token_layout.addStretch()
        
        token_layout.addLayout(get_token_layout)
        
        auth_layout.addWidget(self.token_widget)
        
        # Logout button (initially hidden)
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.clicked.connect(self._logout_huggingface)
        auth_layout.addWidget(self.logout_btn)
        self.logout_btn.setVisible(False)
        
        # Help text
        help_text = QLabel("ℹ️ Some models (like SD 2.1) require authentication. Create a free READ token on HuggingFace.")
        help_text.setStyleSheet("color: gray; font-size: 11px;")
        help_text.setWordWrap(True)
        auth_layout.addWidget(help_text)
        
        layout.addWidget(auth_group)
        
        # Model selection section
        model_group = QGroupBox("Model Selection")
        model_layout = QVBoxLayout(model_group)
        
        # Popular models dropdown
        model_select_layout = QHBoxLayout()
        model_select_layout.addWidget(QLabel("Popular Models:"))
        
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(300)
        self._populate_model_combo()
        model_select_layout.addWidget(self.model_combo)
        
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self._download_selected)
        model_select_layout.addWidget(self.download_btn)
        
        model_select_layout.addStretch()
        model_layout.addLayout(model_select_layout)
        
        # Custom model input
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Custom Model:"))
        
        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("e.g., username/model-name")
        self.custom_input.setMinimumWidth(300)
        custom_layout.addWidget(self.custom_input)
        
        self.custom_download_btn = QPushButton("Download Custom")
        self.custom_download_btn.clicked.connect(self._download_custom)
        custom_layout.addWidget(self.custom_download_btn)
        
        custom_layout.addStretch()
        model_layout.addLayout(custom_layout)
        
        # Help text
        help_text = QLabel("Enter a Hugging Face model ID or select from popular models above")
        help_text.setStyleSheet("color: gray; font-size: 11px;")
        model_layout.addWidget(help_text)
        
        layout.addWidget(model_group)
        
        # Installed models section
        installed_group = QGroupBox("Installed Models")
        installed_layout = QVBoxLayout(installed_group)
        
        self.installed_list = QListWidget()
        self.installed_list.setMaximumHeight(150)
        installed_layout.addWidget(self.installed_list)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_models)
        refresh_btn.setMaximumWidth(100)
        installed_layout.addWidget(refresh_btn)
        
        layout.addWidget(installed_group)
        
        # Download status section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(80)
        self.status_text.setPlainText("Ready to download models")
        status_layout.addWidget(self.status_text)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        layout.addWidget(status_group)
        
        layout.addStretch()
    
    def _populate_model_combo(self):
        """Populate the model combo box."""
        self.model_combo.clear()
        
        # Add a default item
        self.model_combo.addItem("-- Select a model to download --", None)
        
        # Add popular models
        installed = ModelInfo.get_installed_models(self.cache_dir)
        
        for model_id, info in ModelInfo.POPULAR_MODELS.items():
            if model_id in installed:
                # Already installed
                self.model_combo.addItem(f"✓ {info['name']} (installed)", model_id)
            else:
                # Not installed
                recommended = "⭐ " if info.get("recommended") else ""
                size = f" (~{info['size_gb']:.1f} GB)"
                self.model_combo.addItem(f"{recommended}{info['name']}{size}", model_id)
    
    def _refresh_models(self):
        """Refresh the list of installed models."""
        self.installed_list.clear()
        
        installed = ModelInfo.get_installed_models(self.cache_dir)
        if installed:
            for model_id in installed:
                size = ModelInfo.get_model_size(model_id, self.cache_dir)
                
                # Get display name
                if model_id in ModelInfo.POPULAR_MODELS:
                    name = ModelInfo.POPULAR_MODELS[model_id]["name"]
                    item_text = f"{name} ({model_id}) - {size:.1f} GB"
                else:
                    item_text = f"{model_id} - {size:.1f} GB"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, model_id)
                self.installed_list.addItem(item)
        else:
            self.installed_list.addItem("No models installed yet")
        
        # Refresh combo box
        self._populate_model_combo()
        
        # Emit signal
        self.models_changed.emit()
    
    def _download_selected(self):
        """Download the selected model."""
        model_id = self.model_combo.currentData()
        
        if not model_id:
            QMessageBox.warning(self, "No Selection", 
                              "Please select a model to download.")
            return
        
        # Check if already installed
        if ModelInfo.is_model_installed(model_id, self.cache_dir):
            reply = QMessageBox.question(self, "Model Installed",
                                        f"{model_id} is already installed.\n"
                                        "Do you want to re-download it?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        self._start_download(model_id)
    
    def _download_custom(self):
        """Download a custom model."""
        model_id = self.custom_input.text().strip()
        
        if not model_id:
            QMessageBox.warning(self, "No Model ID", 
                              "Please enter a model ID.")
            return
        
        if "/" not in model_id:
            QMessageBox.warning(self, "Invalid Model ID",
                              "Model ID should be in format: username/model-name")
            return
        
        self._start_download(model_id)
    
    def _start_download(self, model_id: str):
        """Start downloading a model."""
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "Download in Progress",
                              "Please wait for the current download to finish.")
            return
        
        # Check dependencies
        try:
            from huggingface_hub import HfFolder
            
            # Check if we have a token for private models
            token = HfFolder.get_token()
            if not token:
                reply = QMessageBox.question(self, "No Authentication",
                                           f"Downloading {model_id} may require authentication.\n\n"
                                           "Continue without authentication?\n"
                                           "(Public models will work, private/gated models will fail)",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
                    
        except ImportError:
            QMessageBox.critical(self, "Dependencies Missing",
                               "huggingface_hub is not installed.\n"
                               "Please install it with:\n"
                               "pip install huggingface_hub")
            return
        
        self.status_text.clear()
        self.status_text.append(f"Starting download of {model_id}...")
        
        # Create download thread
        self.download_thread = ModelDownloadThread(model_id, self.cache_dir)
        self.download_thread.status.connect(self._on_download_status)
        self.download_thread.finished.connect(self._on_download_finished)
        
        # Update UI
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.download_btn.setEnabled(False)
        self.custom_download_btn.setEnabled(False)
        
        self.download_thread.start()
    
    def _on_download_status(self, message: str):
        """Handle download status updates."""
        self.status_text.append(message)
    
    def _on_download_finished(self, success: bool):
        """Handle download completion."""
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        self.custom_download_btn.setEnabled(True)
        
        if success:
            self.status_text.append("Download completed successfully!")
            self._refresh_models()
            QMessageBox.information(self, "Download Complete",
                                  "Model downloaded successfully!")
        else:
            self.status_text.append("Download failed.")
    
    def get_installed_models(self):
        """Get list of installed model IDs."""
        return ModelInfo.get_installed_models(self.cache_dir)
    
    def _check_hf_auth(self):
        """Check HuggingFace authentication status."""
        try:
            from huggingface_hub import HfFolder, whoami
            
            token = HfFolder.get_token()
            if token:
                try:
                    # Try to get user info
                    user_info = whoami(token)
                    username = user_info.get('name', 'Unknown')
                    self.auth_status_label.setText(f"✓ Logged in as: {username}")
                    self.auth_status_label.setStyleSheet("color: green; font-weight: bold;")
                    self.token_widget.setVisible(False)
                    self.logout_btn.setVisible(True)
                except Exception:
                    # Token exists but invalid
                    self.auth_status_label.setText("⚠ Invalid token - please enter a new token")
                    self.auth_status_label.setStyleSheet("color: orange;")
                    self.token_widget.setVisible(True)
                    self.logout_btn.setVisible(False)
            else:
                self.auth_status_label.setText("⚠ Not logged in - Authentication required for some models")
                self.auth_status_label.setStyleSheet("color: #666;")
                self.token_widget.setVisible(True)
                self.logout_btn.setVisible(False)
        except ImportError:
            self.auth_status_label.setText("❌ huggingface_hub not installed")
            self.auth_status_label.setStyleSheet("color: red;")
            self.token_widget.setEnabled(False)
    
    def _open_hf_token_page(self):
        """Open the HuggingFace token page in browser."""
        import webbrowser
        try:
            webbrowser.open("https://huggingface.co/settings/tokens")
        except Exception as e:
            QMessageBox.warning(self, "Error",
                              f"Could not open browser: {str(e)}\n\n"
                              "Please go to: https://huggingface.co/settings/tokens")
    
    def _logout_huggingface(self):
        """Logout from HuggingFace."""
        try:
            from huggingface_hub import HfFolder
            
            reply = QMessageBox.question(self, "Logout",
                                        "Are you sure you want to logout from HuggingFace?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                # Clear the token
                HfFolder.delete_token()
                
                # Update UI
                self.auth_status_label.setText("⚠ Not logged in - Authentication required for some models")
                self.auth_status_label.setStyleSheet("color: #666;")
                self.token_widget.setVisible(True)
                self.logout_btn.setVisible(False)
                
                QMessageBox.information(self, "Logged Out",
                                      "Successfully logged out from HuggingFace.")
        except Exception as e:
            QMessageBox.warning(self, "Error",
                              f"Failed to logout: {str(e)}")
    
    def _save_token(self):
        """Save the HuggingFace token."""
        token = self.token_input.text().strip()
        
        if not token:
            QMessageBox.warning(self, "No Token", 
                              "Please enter a token.")
            return
        
        if not token.startswith('hf_'):
            reply = QMessageBox.question(self, "Invalid Token Format",
                                        "Token should start with 'hf_'. Continue anyway?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        try:
            from huggingface_hub import HfFolder, whoami
            
            # Validate token
            try:
                user_info = whoami(token)
                username = user_info.get('name', 'Unknown')
                
                # Save token
                HfFolder.save_token(token)
                
                # Update UI
                self.auth_status_label.setText(f"✓ Logged in as: {username}")
                self.auth_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.token_widget.setVisible(False)
                self.logout_btn.setVisible(True)
                self.token_input.clear()
                
                QMessageBox.information(self, "Success",
                                      f"Successfully logged in as {username}!")
                
            except Exception as e:
                QMessageBox.critical(self, "Invalid Token",
                                   f"Failed to authenticate with token:\n{str(e)}")
                
        except ImportError:
            QMessageBox.critical(self, "Dependencies Missing",
                               "huggingface_hub is not installed.")
        except Exception as e:
            QMessageBox.critical(self, "Error",
                               f"Failed to save token: {str(e)}")