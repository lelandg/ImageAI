"""Model browser and downloader for Local SD provider."""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QTextEdit, QProgressBar,
    QGroupBox, QMessageBox, QSplitter, QWidget, QCheckBox,
    QComboBox, QTabWidget, QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QFont, QTextCursor

from providers.model_info import ModelInfo

logger = logging.getLogger(__name__)


class ModelDownloader(QThread):
    """Thread for downloading models."""
    
    progress = Signal(int)  # Progress percentage
    status = Signal(str)    # Status message
    finished = Signal(bool) # Success/failure
    
    def __init__(self, model_id: str, cache_dir: Path):
        super().__init__()
        self.model_id = model_id
        self.cache_dir = cache_dir
        self._should_stop = False
    
    def run(self):
        """Download the model."""
        try:
            # Try to import huggingface_hub
            try:
                from huggingface_hub import snapshot_download, HfApi
                from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError
            except ImportError:
                self.status.emit("Error: huggingface_hub not installed")
                self.finished.emit(False)
                return
            
            self.status.emit(f"Starting download of {self.model_id}...")
            
            # Create a simple progress callback
            def progress_callback(progress_info):
                if self._should_stop:
                    raise InterruptedError("Download cancelled")
                # This is simplified - actual progress tracking would need more work
                self.status.emit(f"Downloading files...")
            
            # Download the model
            try:
                local_dir = snapshot_download(
                    repo_id=self.model_id,
                    cache_dir=self.cache_dir,
                    resume_download=True,
                    local_files_only=False,
                    ignore_patterns=["*.md", "*.txt", ".gitattributes"]
                )
                
                self.status.emit(f"Successfully downloaded {self.model_id}")
                self.progress.emit(100)
                self.finished.emit(True)
                
            except GatedRepoError:
                self.status.emit(f"Error: {self.model_id} requires authentication. Please login to Hugging Face.")
                self.finished.emit(False)
            except RepositoryNotFoundError:
                self.status.emit(f"Error: Model {self.model_id} not found on Hugging Face")
                self.finished.emit(False)
            except InterruptedError:
                self.status.emit("Download cancelled")
                self.finished.emit(False)
            except Exception as e:
                self.status.emit(f"Download failed: {str(e)}")
                self.finished.emit(False)
                
        except Exception as e:
            self.status.emit(f"Error: {str(e)}")
            self.finished.emit(False)
    
    def stop(self):
        """Stop the download."""
        self._should_stop = True


class ModelBrowserDialog(QDialog):
    """Dialog for browsing and downloading Stable Diffusion models."""
    
    def __init__(self, parent=None, cache_dir: Optional[Path] = None):
        super().__init__(parent)
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "huggingface")
        self.downloader = None
        
        self.setWindowTitle("Stable Diffusion Model Browser")
        self.setModal(True)
        self.resize(900, 600)
        
        self._init_ui()
        self._load_models()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Browse and Download Stable Diffusion Models")
        header_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        # Cache location
        cache_label = QLabel(f"Cache: {self.cache_dir}")
        cache_label.setStyleSheet("color: gray;")
        header_layout.addWidget(cache_label)
        layout.addLayout(header_layout)
        
        # Create tabs
        self.tabs = QTabWidget()
        
        # Popular models tab
        self.popular_widget = self._create_popular_models_tab()
        self.tabs.addTab(self.popular_widget, "Popular Models")
        
        # Installed models tab
        self.installed_widget = self._create_installed_models_tab()
        self.tabs.addTab(self.installed_widget, "Installed Models")
        
        # Custom model tab
        self.custom_widget = self._create_custom_model_tab()
        self.tabs.addTab(self.custom_widget, "Custom Model")
        
        layout.addWidget(self.tabs)
        
        # Status section
        status_group = QGroupBox("Download Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        status_layout.addWidget(self.status_text)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        layout.addWidget(status_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self._download_selected)
        button_layout.addWidget(self.download_btn)
        
        self.cancel_btn = QPushButton("Cancel Download")
        self.cancel_btn.clicked.connect(self._cancel_download)
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_popular_models_tab(self) -> QWidget:
        """Create the popular models tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Filter options
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Recommended", "Fast", "High Quality", "Artistic"])
        self.filter_combo.currentTextChanged.connect(self._filter_models)
        filter_layout.addWidget(self.filter_combo)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Model list
        splitter = QSplitter(Qt.Horizontal)
        
        self.model_list = QListWidget()
        self.model_list.itemSelectionChanged.connect(self._on_model_selected)
        splitter.addWidget(self.model_list)
        
        # Model details
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        self.model_name_label = QLabel("Select a model")
        self.model_name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        details_layout.addWidget(self.model_name_label)
        
        self.model_desc_text = QTextEdit()
        self.model_desc_text.setReadOnly(True)
        details_layout.addWidget(self.model_desc_text)
        
        self.model_info_label = QLabel("")
        details_layout.addWidget(self.model_info_label)
        
        self.model_status_label = QLabel("")
        self.model_status_label.setStyleSheet("color: green;")
        details_layout.addWidget(self.model_status_label)
        
        splitter.addWidget(details_widget)
        splitter.setSizes([400, 400])
        
        layout.addWidget(splitter)
        
        return widget
    
    def _create_installed_models_tab(self) -> QWidget:
        """Create the installed models tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info label
        info_label = QLabel("Models installed in your cache directory:")
        layout.addWidget(info_label)
        
        # Installed models list
        self.installed_list = QListWidget()
        layout.addWidget(self.installed_list)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Installed Models")
        refresh_btn.clicked.connect(self._load_installed_models)
        layout.addWidget(refresh_btn)
        
        return widget
    
    def _create_custom_model_tab(self) -> QWidget:
        """Create the custom model tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Instructions
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(100)
        instructions.setPlainText(
            "Enter a Hugging Face model ID to download any Stable Diffusion model.\n"
            "Format: username/model-name (e.g., 'runwayml/stable-diffusion-v1-5')\n"
            "You can find models at: https://huggingface.co/models?library=diffusers"
        )
        layout.addWidget(instructions)
        
        # Model ID input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Model ID:"))
        
        self.custom_model_input = QLineEdit()
        self.custom_model_input.setPlaceholderText("username/model-name")
        input_layout.addWidget(self.custom_model_input)
        
        layout.addLayout(input_layout)
        
        # Download button
        custom_download_btn = QPushButton("Download Custom Model")
        custom_download_btn.clicked.connect(self._download_custom)
        layout.addWidget(custom_download_btn)
        
        layout.addStretch()
        
        return widget
    
    def _load_models(self):
        """Load the model lists."""
        # Load popular models
        for model_id, info in ModelInfo.POPULAR_MODELS.items():
            item = QListWidgetItem(info["name"])
            item.setData(Qt.UserRole, model_id)
            
            # Check if installed
            if ModelInfo.is_model_installed(model_id, self.cache_dir):
                item.setText(f"✓ {info['name']}")
                item.setForeground(Qt.darkGreen)
            
            # Add recommended badge
            if info.get("recommended"):
                item.setText(f"{item.text()} ⭐")
            
            self.model_list.addItem(item)
        
        # Load installed models
        self._load_installed_models()
    
    def _load_installed_models(self):
        """Load the list of installed models."""
        self.installed_list.clear()
        
        installed = ModelInfo.get_installed_models(self.cache_dir)
        for model_id in installed:
            size = ModelInfo.get_model_size(model_id, self.cache_dir)
            item = QListWidgetItem(f"{model_id} ({size:.1f} GB)")
            item.setData(Qt.UserRole, model_id)
            self.installed_list.addItem(item)
        
        if not installed:
            self.installed_list.addItem("No models installed yet")
    
    def _filter_models(self, filter_text: str):
        """Filter the model list."""
        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            model_id = item.data(Qt.UserRole)
            info = ModelInfo.POPULAR_MODELS.get(model_id, {})
            
            show = True
            if filter_text == "Recommended":
                show = info.get("recommended", False)
            elif filter_text == "Fast":
                show = "fast" in info.get("tags", [])
            elif filter_text == "High Quality":
                show = "quality" in info.get("tags", []) or "1024x1024" in info.get("tags", [])
            elif filter_text == "Artistic":
                show = "artistic" in info.get("tags", []) or "stylized" in info.get("tags", [])
            
            item.setHidden(not show)
    
    def _on_model_selected(self):
        """Handle model selection."""
        items = self.model_list.selectedItems()
        if not items:
            return
        
        model_id = items[0].data(Qt.UserRole)
        info = ModelInfo.POPULAR_MODELS.get(model_id, {})
        
        self.model_name_label.setText(info.get("name", model_id))
        self.model_desc_text.setPlainText(info.get("description", "No description available"))
        
        # Show model info
        size_gb = info.get("size_gb", 0)
        tags = ", ".join(info.get("tags", []))
        self.model_info_label.setText(f"Size: ~{size_gb:.1f} GB | Tags: {tags}")
        
        # Show installation status
        if ModelInfo.is_model_installed(model_id, self.cache_dir):
            actual_size = ModelInfo.get_model_size(model_id, self.cache_dir)
            self.model_status_label.setText(f"✓ Installed ({actual_size:.1f} GB)")
            self.model_status_label.setStyleSheet("color: green;")
            self.download_btn.setText("Re-download")
        else:
            self.model_status_label.setText("Not installed")
            self.model_status_label.setStyleSheet("color: gray;")
            self.download_btn.setText("Download Selected")
    
    def _download_selected(self):
        """Download the selected model."""
        items = self.model_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "No Selection", "Please select a model to download.")
            return
        
        model_id = items[0].data(Qt.UserRole)
        self._start_download(model_id)
    
    def _download_custom(self):
        """Download a custom model."""
        model_id = self.custom_model_input.text().strip()
        if not model_id:
            QMessageBox.warning(self, "No Model ID", "Please enter a model ID.")
            return
        
        if "/" not in model_id:
            QMessageBox.warning(self, "Invalid Model ID", 
                               "Model ID should be in format: username/model-name")
            return
        
        self._start_download(model_id)
    
    def _start_download(self, model_id: str):
        """Start downloading a model."""
        if self.downloader and self.downloader.isRunning():
            QMessageBox.warning(self, "Download in Progress", 
                               "Please wait for the current download to finish.")
            return
        
        # Check if dependencies are installed
        try:
            import huggingface_hub
        except ImportError:
            QMessageBox.critical(self, "Dependencies Missing",
                                "huggingface_hub is not installed.\n"
                                "Please install it with: pip install huggingface_hub")
            return
        
        self.status_text.append(f"\n--- Starting download of {model_id} ---")
        
        # Create and start downloader
        self.downloader = ModelDownloader(model_id, self.cache_dir)
        self.downloader.progress.connect(self.progress_bar.setValue)
        self.downloader.status.connect(self.status_text.append)
        self.downloader.finished.connect(self._on_download_finished)
        
        # Update UI
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        self.downloader.start()
    
    def _cancel_download(self):
        """Cancel the current download."""
        if self.downloader and self.downloader.isRunning():
            self.downloader.stop()
            self.status_text.append("Cancelling download...")
    
    def _on_download_finished(self, success: bool):
        """Handle download completion."""
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        if success:
            self.status_text.append("✓ Download completed successfully!")
            # Refresh the model lists
            self._load_models()
        else:
            self.status_text.append("✗ Download failed or was cancelled")
        
        # Auto-scroll to bottom
        cursor = self.status_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.status_text.setTextCursor(cursor)