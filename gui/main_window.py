"""Main window for ImageAI GUI."""

import json
import logging
import webbrowser
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from core.llm_models import get_provider_models, get_all_provider_ids, get_provider_display_name

logger = logging.getLogger(__name__)

# Import additional Qt classes needed for thumbnail delegate
try:
    from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QTableWidget, QTableWidgetItem, QStyle
except ImportError:
    QStyledItemDelegate = None
    QStyleOptionViewItem = None
    QStyle = None


class ThumbnailCache:
    """Cache for thumbnail images to improve performance."""

    def __init__(self, max_size=50):
        self.cache = {}  # path -> QPixmap
        self.max_size = max_size
        self.access_order = []  # LRU tracking
        self.hits = 0
        self.misses = 0

    def get(self, path):
        """Get thumbnail from cache or create and cache it."""
        path_str = str(path)
        if path_str in self.cache:
            # Cache hit
            self.hits += 1
            # Move to end for LRU
            self.access_order.remove(path_str)
            self.access_order.append(path_str)
            return self.cache[path_str]

        # Cache miss
        self.misses += 1

        # Create thumbnail
        if Path(path_str).exists():
            pixmap = QPixmap(path_str)
            if not pixmap.isNull():
                # Scale to thumbnail size - use faster scaling for performance
                thumbnail = pixmap.scaled(
                    64, 64,
                    Qt.KeepAspectRatio,
                    Qt.FastTransformation  # Faster scaling
                )

                # Add to cache
                self.cache[path_str] = thumbnail
                self.access_order.append(path_str)

                # Evict oldest if cache is full
                if len(self.cache) > self.max_size:
                    oldest = self.access_order.pop(0)
                    del self.cache[oldest]

                return thumbnail

        return None

    def get_stats(self):
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'size': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate
        }

    def clear(self):
        """Clear the cache."""
        self.cache.clear()
        self.access_order.clear()


# Only define delegate if imports succeeded
if QStyledItemDelegate and QStyle:
    class ThumbnailDelegate(QStyledItemDelegate):
        """Custom delegate for rendering thumbnails in the history table."""

        def __init__(self, thumbnail_cache, parent=None):
            super().__init__(parent)
            self.thumbnail_cache = thumbnail_cache

        def paint(self, painter, option, index):
            """Custom painting for thumbnail column."""
            if index.column() == 0:  # Thumbnail column
                # Get the path directly from this item's UserRole
                path_str = index.data(Qt.UserRole)

                if path_str and Path(path_str).exists():
                    # Get thumbnail from cache
                    thumbnail = self.thumbnail_cache.get(path_str)
                    if thumbnail:
                        # Calculate centered position
                        x = option.rect.center().x() - thumbnail.width() // 2
                        y = option.rect.center().y() - thumbnail.height() // 2

                        # Draw background if selected
                        if option.state & QStyle.State_Selected:
                            painter.fillRect(option.rect, option.palette.highlight())

                        # Draw thumbnail
                        painter.drawPixmap(x, y, thumbnail)
                        return

            # Default painting for other columns
            super().paint(painter, option, index)

        def sizeHint(self, option, index):
            """Provide size hint for thumbnail column."""
            if index.column() == 0:  # Thumbnail column
                return QSize(80, 80)  # Fixed size for thumbnails
            return super().sizeHint(option, index)
else:
    # Fallback when QStyledItemDelegate is not available
    ThumbnailDelegate = None

try:
    from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRect, QStandardPaths
    from PySide6.QtGui import QPixmap, QAction, QPainter
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QLabel, QTextEdit, QPushButton, QComboBox, QLineEdit,
        QFormLayout, QSizePolicy, QMessageBox, QFileDialog,
        QCheckBox, QTextBrowser, QListWidget, QListWidgetItem, QDialog, QSpinBox,
        QDoubleSpinBox, QGroupBox, QApplication, QSplitter, QScrollArea,
        QStyledItemDelegate, QStyleOptionViewItem, QSlider
    )
except ImportError:
    raise ImportError("PySide6 is required for GUI mode")


class GCloudStatusChecker(QThread):
    """Background thread for checking gcloud auth status without blocking the main GUI thread."""

    # Signals to communicate results back to main thread
    status_checked = Signal(bool, str)  # (is_authenticated, status_message)
    project_id_fetched = Signal(str)    # project_id

    def run(self):
        """Run in background thread - subprocess calls are safe here."""
        try:
            from core.gcloud_utils import check_gcloud_auth_status, get_gcloud_project_id

            # These blocking subprocess calls are OK in background thread
            is_auth, status_msg = check_gcloud_auth_status()
            self.status_checked.emit(is_auth, status_msg)

            if is_auth:
                project_id = get_gcloud_project_id()
                if project_id:
                    self.project_id_fetched.emit(project_id)
        except Exception as e:
            # Emit error status
            self.status_checked.emit(False, f"Error: {str(e)}")


from core import (
    ConfigManager, APP_NAME, VERSION, DEFAULT_MODEL, sanitize_filename,
    scan_disk_history, images_output_dir, sidecar_path, write_image_sidecar,
    read_image_sidecar, auto_save_images, sanitize_stub_from_prompt,
    detect_image_extension, find_cached_demo, default_model_for_provider
)
from core.constants import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
from core.video.reference_manager import ReferenceImageType
from providers import get_provider, preload_provider, list_providers
from gui.dialogs import ExamplesDialog
from gui.shortcut_hint_widget import create_shortcut_hint
# Defer video tab import to improve startup speed
# from gui.video.video_project_tab import VideoProjectTab
from gui.workers import GenWorker, HistoryLoaderWorker, OllamaDetectionWorker
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

# Midjourney has its own dedicated tab now, no longer needs panel import
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
        import logging
        self.logger = logging.getLogger(__name__)
        self.config = ConfigManager()
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")

        # Initialize thumbnail cache
        self.thumbnail_cache = ThumbnailCache(max_size=50)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        
        # Initialize provider (respect last selection, including Midjourney)
        self.current_provider = self.config.get("provider", "google")

        # Migrate old imagen_customization selection to google
        # imagen_customization is now integrated into google provider
        if self.current_provider == "imagen_customization":
            self.current_provider = "google"
            self.config.set("provider", "google")

        self.current_api_key = self.config.get_api_key(self.current_provider)
        self.current_model = DEFAULT_MODEL
        self.auto_copy_filename = self.config.get("auto_copy_filename", False)

        # Session state
        print("Cleaning up debug images...")
        from core.utils import cleanup_debug_images
        composed_deleted, raw_deleted = cleanup_debug_images()
        if composed_deleted > 0 or raw_deleted > 0:
            print(f"Deleted {composed_deleted} DEBUG_COMPOSED and {raw_deleted} redundant DEBUG_RAW images")

        print("Scanning image history...")
        self.history_paths: List[Path] = scan_disk_history(project_only=True)
        print(f"Found {len(self.history_paths)} images in history")

        self.history = []  # Initialize empty history list
        self.history_loaded_count = 0  # Track how many items are loaded
        self.history_initial_load_size = 50  # Load only 50 items initially
        self.current_prompt: str = ""
        self.gen_thread: Optional[QThread] = None
        self.gen_worker: Optional[GenWorker] = None
        self.history_loader_thread: Optional[QThread] = None
        self.history_loader_worker: Optional[HistoryLoaderWorker] = None
        self.ollama_detection_thread: Optional[QThread] = None
        self.ollama_detection_worker: Optional[OllamaDetectionWorker] = None
        self.current_image_data: Optional[bytes] = None
        self._last_template_context: Optional[dict] = None
        self._video_tab_loaded = False  # Track lazy loading of video tab
        self.upscaling_settings = {}  # Initialize upscaling settings

        # Initialize Midjourney watcher
        self.midjourney_watcher = None
        self.midjourney_session_id = None  # Track current session

        # Load history from disk with progress display
        if self.history_paths:
            total_images = len(self.history_paths)
            print(f"Loading image metadata... (0/{total_images})", end='', flush=True)
            self._load_history_from_disk()
            print(f"\rLoaded metadata for {len(self.history)}/{total_images} images")

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

        # Initialize Midjourney watcher if enabled
        self._init_midjourney_watcher()

        # Ensure UI reflects the restored provider (including Midjourney)
        try:
            self._on_provider_changed(self.current_provider)
        except Exception:
            pass

        # Start background loading of remaining history items
        if self.history_loaded_count < len(self.history_paths):
            self._start_background_history_loader()

        # Start background Ollama model detection
        self._start_background_ollama_detection()

        print("Application ready!")
        self.status_bar.showMessage("Ready")
        QApplication.processEvents()
    

    def _on_show_all_images_toggled(self, checked: bool):
        """Handle toggle of show all images checkbox."""
        # Stop any running background loader
        if self.history_loader_worker:
            self.history_loader_worker.stop()
        if self.history_loader_thread and self.history_loader_thread.isRunning():
            self.history_loader_thread.quit()
            self.history_loader_thread.wait()

        # Reload history with new filter
        self.history_paths = scan_disk_history(project_only=not checked)

        # Clear existing history data
        self.history = []
        self.history_loaded_count = 0

        # Load initial batch only
        print(f"Loading initial metadata for {min(self.history_initial_load_size, len(self.history_paths))} of {len(self.history_paths)} images...")
        self._load_history_from_disk()
        print(f"Loaded metadata for {len(self.history)} images")

        # Refresh the history table
        if hasattr(self, 'history_table'):
            self._refresh_history_table()

        # Start background loading of remaining items
        if self.history_loaded_count < len(self.history_paths):
            self._start_background_history_loader()

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

    def _load_history_from_disk(self, load_all: bool = False):
        """Load history from disk into memory with enhanced metadata.

        Args:
            load_all: If True, load all remaining items. Otherwise, load only initial batch.
        """
        total = len(self.history_paths)

        # Determine how many items to load
        if load_all:
            start_idx = self.history_loaded_count
            end_idx = total
            items_to_load = self.history_paths[start_idx:end_idx]
        else:
            # Load only initial batch
            end_idx = min(self.history_initial_load_size, total)
            items_to_load = self.history_paths[:end_idx]

        for i, path in enumerate(items_to_load):
            actual_idx = self.history_loaded_count + i

            # Update progress every 10 images or on first/last
            if i == 0 or (i + 1) % 10 == 0 or actual_idx == total - 1:
                print(f"\rLoading image metadata... ({actual_idx + 1}/{total})", end='', flush=True)

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

        # Update loaded count
        self.history_loaded_count = len(self.history)

    def _start_background_history_loader(self):
        """Start background thread to load remaining history items."""
        if self.history_loader_thread and self.history_loader_thread.isRunning():
            return  # Already running

        # Create worker and thread
        self.history_loader_worker = HistoryLoaderWorker(
            history_paths=self.history_paths,
            start_index=self.history_loaded_count,
            batch_size=25
        )
        self.history_loader_thread = QThread()
        self.history_loader_worker.moveToThread(self.history_loader_thread)

        # Connect signals
        self.history_loader_worker.batch_loaded.connect(self._on_history_batch_loaded)
        self.history_loader_worker.progress.connect(self._on_history_load_progress)
        self.history_loader_worker.finished.connect(self._on_history_load_finished)
        self.history_loader_worker.error.connect(self._on_history_load_error)
        self.history_loader_thread.started.connect(self.history_loader_worker.run)

        # Start thread
        self.history_loader_thread.start()
        print(f"Background loading {len(self.history_paths) - self.history_loaded_count} remaining history items...")

    def _on_history_batch_loaded(self, batch_items: list):
        """Handle a batch of history items loaded in background."""
        self.history.extend(batch_items)
        self.history_loaded_count = len(self.history)
        # Refresh history display if on history tab
        if hasattr(self, 'history_table'):
            self._refresh_history_table()

    def _on_history_load_progress(self, loaded: int, total: int):
        """Update status bar with loading progress."""
        remaining = total - loaded
        if remaining > 0 and hasattr(self, 'status_bar'):
            self.status_bar.showMessage(f"Loading history: {loaded}/{total} ({remaining} remaining)")

    def _on_history_load_finished(self):
        """Handle completion of background history loading."""
        print(f"\rBackground history loading complete! Total: {len(self.history)} items")
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage("Ready", 3000)

        # Clean up thread
        if self.history_loader_thread:
            self.history_loader_thread.quit()
            self.history_loader_thread.wait()
            self.history_loader_thread = None
            self.history_loader_worker = None

    def _on_history_load_error(self, error_msg: str):
        """Handle error during background history loading."""
        self.logger.error(f"History loading error: {error_msg}")
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage("History loading error", 5000)

    def _start_background_ollama_detection(self):
        """Start background thread to detect Ollama models."""
        if self.ollama_detection_thread and self.ollama_detection_thread.isRunning():
            return  # Already running

        # Create worker and thread
        self.ollama_detection_worker = OllamaDetectionWorker()
        self.ollama_detection_thread = QThread()
        self.ollama_detection_worker.moveToThread(self.ollama_detection_thread)

        # Connect signals
        self.ollama_detection_worker.models_detected.connect(self._on_ollama_models_detected)
        self.ollama_detection_worker.no_ollama.connect(self._on_ollama_not_available)
        self.ollama_detection_worker.finished.connect(self._on_ollama_detection_finished)
        self.ollama_detection_worker.error.connect(self._on_ollama_detection_error)
        self.ollama_detection_thread.started.connect(self.ollama_detection_worker.run)

        # Start thread
        self.ollama_detection_thread.start()
        print("Detecting Ollama models in background...")

    def _on_ollama_models_detected(self, models: list):
        """Handle successful Ollama model detection."""
        print(f"✓ Detected {len(models)} Ollama models: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
        # Update any UI that depends on Ollama models
        # (e.g., LLM provider dropdowns in dialogs)

    def _on_ollama_not_available(self):
        """Handle case when Ollama is not available."""
        print("No Ollama installation detected (using defaults)")

    def _on_ollama_detection_finished(self):
        """Handle completion of Ollama detection."""
        # Clean up thread
        if self.ollama_detection_thread:
            self.ollama_detection_thread.quit()
            self.ollama_detection_thread.wait()
            self.ollama_detection_thread = None
            self.ollama_detection_worker = None

    def _on_ollama_detection_error(self, error_msg: str):
        """Handle error during Ollama detection."""
        self.logger.debug(f"Ollama detection error: {error_msg}")
        # Don't show to user - Ollama is optional

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

        # Create layout tab
        try:
            from gui.layout import LayoutTab
            self.tab_layout = LayoutTab(config=self.config)
            logger.info("Layout tab created successfully")
        except Exception as e:
            logger.error(f"Failed to create layout tab: {e}", exc_info=True)
            self.tab_layout = QWidget()  # Fallback placeholder

        # Add tabs
        self.tabs.addTab(self.tab_generate, "🎨 Image")
        self.tabs.addTab(self.tab_templates, "📝 Templates")
        self.tabs.addTab(self.tab_video, "🎬 Video")
        self.tabs.addTab(self.tab_layout, "📖 Layout")
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

        # Tools menu
        tools_menu = mb.addMenu("Tools")

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
        self.llm_provider_combo.addItems(self.get_llm_providers())
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
            # Midjourney is now integrated in the Image tab
            if not available_providers:
                # Ensure we have at least core providers listed
                available_providers = ["google", "openai", "midjourney"]
        except Exception as e:
            # Avoid bubbling import-time errors (e.g., protobuf incompat)
            import logging as _logging
            _logging.getLogger(__name__).debug(f"Provider discovery failed: {e}")
            available_providers = ["google", "openai", "midjourney"]

        # Filter out imagen_customization - it's used internally by google provider
        available_providers = [p for p in available_providers if p != "imagen_customization"]
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
        from gui.common.splitter_style import apply_splitter_style
        splitter = QSplitter(Qt.Vertical)
        apply_splitter_style(splitter)
        
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

        # Add quick reference tag insertion buttons (dynamically created based on reference count)
        self.ref_tag_buttons_widget = QWidget()
        self.ref_tag_buttons_layout = QHBoxLayout(self.ref_tag_buttons_widget)
        self.ref_tag_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.ref_tag_buttons_layout.setSpacing(2)

        self.ref_tag_label = QLabel("Insert ref:")
        self.ref_tag_buttons_layout.addWidget(self.ref_tag_label)
        # Buttons will be created dynamically in _update_reference_buttons()

        self.ref_tag_buttons_widget.setVisible(False)  # Hidden initially
        prompt_header_layout.addWidget(self.ref_tag_buttons_widget)

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

        # All buttons in one row - reordered as requested
        self.btn_generate_prompts = QPushButton("Generate &Prompts")
        self.btn_generate_prompts.setToolTip("Generate multiple prompt variations (Alt+P)")
        buttons_layout.addWidget(self.btn_generate_prompts)

        self.btn_enhance_prompt = QPushButton("&Enhance")
        self.btn_enhance_prompt.setToolTip("Improve prompt with AI (Alt+E)")
        buttons_layout.addWidget(self.btn_enhance_prompt)

        self.btn_reference_image = QPushButton("Ask About &Image")
        self.btn_reference_image.setToolTip("Analyze reference image with AI (Alt+I)")
        buttons_layout.addWidget(self.btn_reference_image)

        self.btn_ask_about = QPushButton("&Ask About Prompt")
        self.btn_ask_about.setToolTip("Ask questions about your prompt (Alt+A)")
        buttons_layout.addWidget(self.btn_ask_about)

        self.btn_generate = QPushButton("&Generate")
        self.btn_generate.setToolTip("Generate image (Alt+G or Ctrl+Enter)")
        buttons_layout.addWidget(self.btn_generate)

        # Spacer to center Examples button
        buttons_layout.addStretch()

        self.btn_examples = QPushButton("E&xamples")
        self.btn_examples.setToolTip("Browse example prompts (Alt+X)")
        buttons_layout.addWidget(self.btn_examples)

        # Spacer
        buttons_layout.addStretch()

        # Toggle button for original/cropped (initially hidden)
        self.btn_toggle_original = QPushButton("Show &Original")
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

        # Add shortcuts hint label with enhanced visibility
        shortcuts_label = create_shortcut_hint("Ctrl+Enter to generate, Ctrl+S to save, Ctrl+Shift+C to copy, Alt+key for buttons, Ctrl+F to search")
        bottom_layout.addWidget(shortcuts_label)

        # Image Settings - expandable like Advanced Settings
        # Toggle button
        self.image_settings_toggle = QPushButton("▶ &Image Settings")
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
        # Set size policy to prevent compression when other sections expand
        self.image_settings_container.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum
        )
        image_settings_layout = QVBoxLayout(self.image_settings_container)
        image_settings_layout.setSpacing(5)
        image_settings_layout.setContentsMargins(10, 0, 0, 0)  # Indent for hierarchy
        
        # Create horizontal layout for aspect ratio, quality, and social sizes
        aspect_quality_layout = QHBoxLayout()
        aspect_quality_layout.setSpacing(15)

        # Aspect Ratio Selector (left)
        if AspectRatioSelector:
            aspect_group = QWidget()
            aspect_v_layout = QVBoxLayout(aspect_group)
            aspect_v_layout.setContentsMargins(0, 0, 0, 0)
            aspect_v_layout.setSpacing(3)

            aspect_label = QLabel("Aspect Ratio:")
            aspect_label.setMaximumHeight(20)
            aspect_v_layout.addWidget(aspect_label)

            self.aspect_selector = AspectRatioSelector()
            self.aspect_selector.ratioChanged.connect(self._on_aspect_ratio_changed)
            aspect_v_layout.addWidget(self.aspect_selector)

            # Aspect ratios are now supported by all providers including Google Gemini
            self.aspect_selector.setEnabled(True)
            self.aspect_selector.setToolTip("Select aspect ratio for your image")

            aspect_quality_layout.addWidget(aspect_group)
        else:
            self.aspect_selector = None

        # Quality Selector (middle)
        if QualitySelector:
            quality_group = QWidget()
            quality_v_layout = QVBoxLayout(quality_group)
            quality_v_layout.setContentsMargins(0, 0, 0, 0)
            quality_v_layout.setSpacing(3)

            self.quality_selector = QualitySelector(self.current_provider)
            self.quality_selector.settingsChanged.connect(self._on_quality_settings_changed)
            quality_v_layout.addWidget(self.quality_selector)

            aspect_quality_layout.addWidget(quality_group)
        else:
            self.quality_selector = None

        # Social Sizes Button (right)
        social_group = QWidget()
        social_v_layout = QVBoxLayout(social_group)
        social_v_layout.setContentsMargins(0, 0, 0, 0)
        social_v_layout.setSpacing(3)

        social_label = QLabel(" ")  # Empty label for alignment
        social_label.setMaximumHeight(20)
        social_v_layout.addWidget(social_label)

        self.btn_social_sizes = QPushButton("&Social Sizes…")
        self.btn_social_sizes.setToolTip("Browse common social media sizes and apply")
        self.btn_social_sizes.clicked.connect(self._open_social_sizes_dialog)
        social_v_layout.addWidget(self.btn_social_sizes)

        # Label to show selected social media size
        self.social_size_label = QLabel("")
        self.social_size_label.setStyleSheet("""
            QLabel {
                color: #2c5aa0;
                font-weight: bold;
                padding: 2px 5px;
                background-color: #e8f4ff;
                border: 1px solid #b3d9ff;
                border-radius: 3px;
            }
        """)
        self.social_size_label.setVisible(False)
        social_v_layout.addWidget(self.social_size_label)

        aspect_quality_layout.addWidget(social_group)
        aspect_quality_layout.addStretch(1)

        image_settings_layout.addLayout(aspect_quality_layout)

        # Resolution settings
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

        bottom_layout.addWidget(self.image_settings_container)

        # Reference Image Settings (collapsible flyout) - Multi-reference for Imagen 3
        self.ref_image_toggle = QPushButton("▶ Reference Images (Google Only - Imagen 3)")
        self.ref_image_toggle.setCheckable(True)
        self.ref_image_toggle.setChecked(False)
        self.ref_image_toggle.clicked.connect(lambda checked: self._toggle_ref_image_settings(checked))
        self.ref_image_toggle.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
            }
        """)
        bottom_layout.addWidget(self.ref_image_toggle)

        # Container for reference image settings (initially hidden)
        self.ref_image_container = QWidget()
        self.ref_image_container.setVisible(False)
        ref_container_layout = QVBoxLayout(self.ref_image_container)
        ref_container_layout.setContentsMargins(10, 0, 0, 0)  # Indent for hierarchy

        # Add Imagen 3 multi-reference widget
        from gui.imagen_reference_widget import ImagenReferenceWidget
        self.imagen_reference_widget = ImagenReferenceWidget()
        self.imagen_reference_widget.references_changed.connect(self._on_imagen_references_changed)
        ref_container_layout.addWidget(self.imagen_reference_widget)

        # Create splitter below reference images to allow independent resizing
        ref_splitter = QSplitter(Qt.Vertical)
        ref_splitter.setChildrenCollapsible(False)

        # Add reference images container to TOP of splitter
        ref_splitter.addWidget(self.ref_image_container)

        # Bottom section widget for everything below reference images
        ref_bottom_section = QWidget()
        ref_bottom_layout = QVBoxLayout(ref_bottom_section)
        ref_bottom_layout.setContentsMargins(0, 0, 0, 0)
        ref_bottom_layout.setSpacing(5)
        ref_splitter.addWidget(ref_bottom_section)

        # Set splitter sizes (reference images: 250px, bottom section: rest)
        ref_splitter.setSizes([250, 500])
        ref_splitter.setStretchFactor(0, 0)  # Reference images don't auto-stretch
        ref_splitter.setStretchFactor(1, 1)  # Bottom section stretches to fill

        bottom_layout.addWidget(ref_splitter, 1)  # Stretch to fill

        # Store reference image data (legacy - kept for backward compatibility)
        # NEW: Multi-reference data is stored in self.imagen_reference_widget
        self.reference_image_path = None
        self.reference_image_data = None

        # Advanced Settings (collapsible) - now added to ref_bottom_layout
        if AdvancedSettingsPanel:
            self.advanced_panel = AdvancedSettingsPanel(self.current_provider)
            self.advanced_panel.settingsChanged.connect(self._on_advanced_settings_changed)
            ref_bottom_layout.addWidget(self.advanced_panel)
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
            ref_bottom_layout.addWidget(advanced_group)
            self.advanced_group = advanced_group
            self.advanced_panel = None
        
        # Update visibility based on provider
        self._update_advanced_visibility()

        # Midjourney-specific options (shown when Midjourney is selected)
        self.midjourney_options_group = QGroupBox("Midjourney Options")
        mj_layout = QFormLayout()

        # Model Version
        self.mj_version_combo = QComboBox()
        self.mj_version_combo.addItems(["v7", "v6.1", "v6", "v5.2", "v5.1", "v5", "niji6", "niji5"])
        self.mj_version_combo.setCurrentText("v7")
        # Version changes are now handled by the provider
        mj_layout.addRow("Version:", self.mj_version_combo)

        # Stylize
        self.mj_stylize_slider = QSlider(Qt.Horizontal)
        self.mj_stylize_slider.setRange(0, 1000)
        self.mj_stylize_slider.setValue(100)
        self.mj_stylize_slider.setTickInterval(100)
        self.mj_stylize_slider.setTickPosition(QSlider.TicksBelow)
        self.mj_stylize_label = QLabel("100")
        stylize_widget = QWidget()
        stylize_layout = QHBoxLayout(stylize_widget)
        stylize_layout.setContentsMargins(0, 0, 0, 0)
        stylize_layout.addWidget(self.mj_stylize_slider)
        stylize_layout.addWidget(self.mj_stylize_label)
        self.mj_stylize_slider.valueChanged.connect(lambda v: self.mj_stylize_label.setText(str(v)))
        mj_layout.addRow("Stylize:", stylize_widget)

        # Chaos
        self.mj_chaos_slider = QSlider(Qt.Horizontal)
        self.mj_chaos_slider.setRange(0, 100)
        self.mj_chaos_slider.setValue(0)
        self.mj_chaos_slider.setTickInterval(10)
        self.mj_chaos_slider.setTickPosition(QSlider.TicksBelow)
        self.mj_chaos_label = QLabel("0")
        chaos_widget = QWidget()
        chaos_layout = QHBoxLayout(chaos_widget)
        chaos_layout.setContentsMargins(0, 0, 0, 0)
        chaos_layout.addWidget(self.mj_chaos_slider)
        chaos_layout.addWidget(self.mj_chaos_label)
        self.mj_chaos_slider.valueChanged.connect(lambda v: self.mj_chaos_label.setText(str(v)))
        mj_layout.addRow("Chaos:", chaos_widget)

        # Weird
        self.mj_weird_slider = QSlider(Qt.Horizontal)
        self.mj_weird_slider.setRange(0, 3000)
        self.mj_weird_slider.setValue(0)
        self.mj_weird_slider.setTickInterval(250)
        self.mj_weird_slider.setTickPosition(QSlider.TicksBelow)
        self.mj_weird_label = QLabel("0")
        weird_widget = QWidget()
        weird_layout = QHBoxLayout(weird_widget)
        weird_layout.setContentsMargins(0, 0, 0, 0)
        weird_layout.addWidget(self.mj_weird_slider)
        weird_layout.addWidget(self.mj_weird_label)
        self.mj_weird_slider.valueChanged.connect(lambda v: self.mj_weird_label.setText(str(v)))
        mj_layout.addRow("Weird:", weird_widget)

        # Quality
        self.mj_quality_combo = QComboBox()
        self.mj_quality_combo.addItems(["0.25", "0.5", "1", "2"])
        self.mj_quality_combo.setCurrentText("1")
        # Quality changes are now handled by the provider
        mj_layout.addRow("Quality:", self.mj_quality_combo)

        # Seed
        self.mj_seed_spin = QSpinBox()
        self.mj_seed_spin.setRange(-1, 2147483647)
        self.mj_seed_spin.setValue(-1)
        self.mj_seed_spin.setSpecialValueText("Random")
        self.mj_seed_spin.setSuffix(" (-1 for random)")
        # Seed changes are now handled by the provider
        mj_layout.addRow("Seed:", self.mj_seed_spin)

        self.midjourney_options_group.setLayout(mj_layout)
        ref_bottom_layout.addWidget(self.midjourney_options_group)
        self.midjourney_options_group.setVisible(False)  # Initially hidden

        # Status - compact
        self.status_label = QLabel("Ready.")
        self.status_label.setMaximumHeight(20)
        ref_bottom_layout.addWidget(self.status_label)
        
        # Create a vertical splitter for image and status console
        image_console_splitter = QSplitter(Qt.Vertical)
        # Connect splitter movement to image resize
        image_console_splitter.splitterMoved.connect(lambda: QTimer.singleShot(10, self._perform_image_resize))

        # Create stacked widget for image/Midjourney command display
        from PySide6.QtWidgets import QStackedWidget
        self.output_stack = QStackedWidget()
        self.output_stack.setMinimumHeight(200)
        self.output_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Output image widget
        self.output_image_label = QLabel()
        self.output_image_label.setAlignment(Qt.AlignCenter)
        self.output_image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        self.output_image_label.setScaledContents(False)  # We handle scaling manually

        # Midjourney command display widget
        self.midjourney_command_widget = QWidget()
        mj_layout = QVBoxLayout(self.midjourney_command_widget)
        mj_layout.setContentsMargins(20, 20, 20, 20)

        # Discord-styled command display
        self.midjourney_command_display = QTextEdit()
        self.midjourney_command_display.setReadOnly(True)
        self.midjourney_command_display.setMaximumHeight(120)
        from PySide6.QtGui import QFont
        self.midjourney_command_display.setFont(QFont("Consolas", 11))
        self.midjourney_command_display.setStyleSheet("""
            QTextEdit {
                background-color: #40444B;
                color: #7289DA;
                border: 2px solid #7289DA;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        mj_layout.addWidget(QLabel("Discord Command:"))
        mj_layout.addWidget(self.midjourney_command_display)

        # Info label
        mj_info = QLabel("✅ Command will be copied when you click Generate\n📋 Paste in Discord and press Enter")
        mj_info.setStyleSheet("color: #666; padding: 10px;")
        mj_info.setAlignment(Qt.AlignCenter)
        mj_layout.addWidget(mj_info)

        mj_layout.addStretch()

        # Add both to stacked widget
        self.output_stack.addWidget(self.output_image_label)  # Index 0
        self.output_stack.addWidget(self.midjourney_command_widget)  # Index 1

        image_console_splitter.addWidget(self.output_stack)

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

        ref_bottom_layout.addWidget(image_console_splitter, 1)
        
        # Add bottom widget to splitter
        splitter.addWidget(bottom_widget)

        # Set initial splitter sizes (small prompt, large bottom area)
        splitter.setSizes([80, 800])  # 80px for prompt, 800px for rest (more space for expanded sections)
        splitter.setStretchFactor(0, 0)  # Don't stretch prompt section
        splitter.setStretchFactor(1, 3)  # Give bottom section more stretch priority
        # Set minimum sizes to prevent sections from disappearing
        font_metrics = self.prompt_edit.fontMetrics()
        min_prompt_height = font_metrics.lineSpacing() * 3 + 35  # 3 lines + label + padding
        splitter.setChildrenCollapsible(False)  # Prevent sections from collapsing
        prompt_container.setMinimumHeight(min_prompt_height)
        bottom_widget.setMinimumHeight(400)  # Increased minimum to accommodate expanded settings sections
        
        # Add splitter to main layout
        v.addWidget(splitter)
        
        # Connect signals
        self.btn_examples.clicked.connect(self._open_examples)
        self.btn_enhance_prompt.clicked.connect(self._enhance_prompt)
        self.btn_generate_prompts.clicked.connect(self._open_prompt_generator)
        self.btn_ask_about.clicked.connect(self._open_prompt_question)
        self.btn_reference_image.clicked.connect(self._open_reference_image)
        self.btn_generate.clicked.connect(self._generate)

        # Connect prompt changes to Midjourney panel
        self.prompt_edit.textChanged.connect(self._on_prompt_text_changed)

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

        # Load Imagen multi-reference images from config
        self._load_imagen_references_from_config()

        # Restore reference images expansion state
        if hasattr(self, 'ref_image_toggle'):
            expanded = self.config.get('reference_images_expanded', False)
            self.ref_image_toggle.setChecked(expanded)
            self.ref_image_container.setVisible(expanded)
            self.ref_image_toggle.setText("▼ Reference Images (Google Only - Imagen 3)" if expanded else "▶ Reference Images (Google Only - Imagen 3)")

        # Check provider support for reference images
        if hasattr(self, 'btn_select_ref_image'):
            is_google = self.current_provider.lower() == "google"
            self.btn_select_ref_image.setEnabled(is_google)
            if is_google:
                self.btn_select_ref_image.setToolTip("Choose a starting image for generation (Google Gemini)")
            else:
                self.btn_select_ref_image.setToolTip(f"Reference images not supported by {self.current_provider} provider")

        # Update use current button state on startup
        self._update_use_current_button_state()

        # Restore Image Settings expansion state from config
        image_settings_expanded = self.config.get('image_settings_expanded', False)
        if image_settings_expanded:
            self.image_settings_container.setVisible(True)
            self.image_settings_toggle.setText("▼ &Image Settings")
            self.image_settings_toggle.setChecked(True)

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
                platform = dlg._selected_platform
                type_name = dlg._selected_type

                if res and hasattr(self, 'resolution_selector') and self.resolution_selector:
                    # Switch to explicit resolution mode and set the value
                    self.resolution_selector.set_mode_resolution()
                    # If preset list does not contain this size, temporarily add it
                    if hasattr(self.resolution_selector, 'set_resolution'):
                        self.resolution_selector.set_resolution(res)
                    # Store as current resolution for persistence
                    self.current_resolution = res

                    # Update the label to show selected social media size
                    if platform and type_name and hasattr(self, 'social_size_label'):
                        # Truncate if too long
                        display_text = f"{platform}: {type_name}"
                        if len(display_text) > 30:
                            display_text = f"{platform[:15]}: {type_name[:12]}..."
                        self.social_size_label.setText(display_text)
                        self.social_size_label.setVisible(True)
                        # Add tooltip with full info
                        self.social_size_label.setToolTip(f"{platform} - {type_name}\nSize: {res}")
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
            # Midjourney is now integrated in the Image tab
            if not available_providers:
                available_providers = ["google", "openai", "midjourney"]
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).debug(f"Provider discovery failed (settings tab): {e}")
            available_providers = ["google", "openai", "midjourney"]

        # Filter out imagen_customization - it's used internally by google provider
        available_providers = [p for p in available_providers if p != "imagen_customization"]
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

        # Add shortcuts hint for API keys section with enhanced visibility
        api_shortcuts_label = create_shortcut_hint("Alt+K to get keys, Alt+S to save & test")
        providers_layout.addWidget(api_shortcuts_label)

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

        # === MIDJOURNEY SETTINGS ===
        midjourney_group = QGroupBox("Midjourney Settings")
        midjourney_layout = QVBoxLayout(midjourney_group)

        # Enable download watching
        self.chk_midjourney_watch = QCheckBox("Watch Downloads folder for Midjourney images")
        self.chk_midjourney_watch.setToolTip("Automatically detect and associate Midjourney images when downloaded")
        self.chk_midjourney_watch.setChecked(self.config.get("midjourney_watch_enabled", False))
        midjourney_layout.addWidget(self.chk_midjourney_watch)

        # Downloads folder path
        downloads_layout = QHBoxLayout()
        downloads_layout.addWidget(QLabel("Downloads folder:"))
        self.midjourney_downloads_edit = QLineEdit()
        default_downloads = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        self.midjourney_downloads_edit.setText(
            self.config.get("midjourney_downloads_path", default_downloads)
        )
        self.midjourney_downloads_edit.setToolTip("Path to watch for downloaded Midjourney images")
        downloads_layout.addWidget(self.midjourney_downloads_edit)

        self.btn_browse_downloads = QPushButton("Browse...")
        self.btn_browse_downloads.clicked.connect(self._browse_downloads_folder)
        downloads_layout.addWidget(self.btn_browse_downloads)
        midjourney_layout.addLayout(downloads_layout)

        # Auto-accept confidence threshold
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Auto-accept confidence:"))
        self.midjourney_threshold_spin = QSpinBox()
        self.midjourney_threshold_spin.setRange(0, 100)
        self.midjourney_threshold_spin.setSuffix("%")
        self.midjourney_threshold_spin.setValue(self.config.get("midjourney_auto_accept", 85))
        self.midjourney_threshold_spin.setToolTip("Automatically accept matches above this confidence level")
        threshold_layout.addWidget(self.midjourney_threshold_spin)

        self.midjourney_threshold_label = QLabel("(85% recommended)")
        threshold_layout.addWidget(self.midjourney_threshold_label)
        threshold_layout.addStretch()
        midjourney_layout.addLayout(threshold_layout)

        # Time window
        window_layout = QHBoxLayout()
        window_layout.addWidget(QLabel("Detection time window:"))
        self.midjourney_window_spin = QSpinBox()
        self.midjourney_window_spin.setRange(30, 600)
        self.midjourney_window_spin.setSuffix(" seconds")
        self.midjourney_window_spin.setValue(self.config.get("midjourney_time_window", 300))
        self.midjourney_window_spin.setToolTip("How long after generation to watch for images")
        window_layout.addWidget(self.midjourney_window_spin)
        window_layout.addStretch()
        midjourney_layout.addLayout(window_layout)

        # Show notifications
        self.chk_midjourney_notify = QCheckBox("Show notifications when images are detected")
        self.chk_midjourney_notify.setChecked(self.config.get("midjourney_notifications", True))
        midjourney_layout.addWidget(self.chk_midjourney_notify)

        # Discord configuration
        discord_label = QLabel("<b>Discord Configuration (Optional)</b>")
        midjourney_layout.addWidget(discord_label)

        # Use Discord checkbox
        self.chk_use_discord = QCheckBox("Use Discord instead of Midjourney web app")
        self.chk_use_discord.setChecked(self.config.get("midjourney_use_discord", False))
        self.chk_use_discord.toggled.connect(self._on_midjourney_use_discord_toggled)
        midjourney_layout.addWidget(self.chk_use_discord)

        # Discord server ID
        discord_server_layout = QHBoxLayout()
        discord_server_layout.addWidget(QLabel("Discord Server ID:"))
        self.discord_server_edit = QLineEdit()
        self.discord_server_edit.setPlaceholderText("e.g., 662267976984297473")
        self.discord_server_edit.setText(self.config.get("midjourney_discord_server", ""))
        self.discord_server_edit.setToolTip("Your Discord server ID (right-click server > Copy Server ID)")
        self.discord_server_edit.editingFinished.connect(self._on_midjourney_discord_fields_changed)
        discord_server_layout.addWidget(self.discord_server_edit)
        discord_server_layout.addStretch()
        midjourney_layout.addLayout(discord_server_layout)

        # Discord channel ID
        discord_channel_layout = QHBoxLayout()
        discord_channel_layout.addWidget(QLabel("Discord Channel ID:"))
        self.discord_channel_edit = QLineEdit()
        self.discord_channel_edit.setPlaceholderText("e.g., 989268300185776158")
        self.discord_channel_edit.setText(self.config.get("midjourney_discord_channel", ""))
        self.discord_channel_edit.setToolTip("Your Discord channel ID (right-click channel > Copy Channel ID)")
        self.discord_channel_edit.editingFinished.connect(self._on_midjourney_discord_fields_changed)
        discord_channel_layout.addWidget(self.discord_channel_edit)
        discord_channel_layout.addStretch()
        midjourney_layout.addLayout(discord_channel_layout)

        # Test Discord button
        self.btn_test_discord = QPushButton("Test Discord Channel")
        self.btn_test_discord.clicked.connect(self._test_discord_channel)
        self.btn_test_discord.setToolTip("Open the configured Discord channel to verify it works")
        midjourney_layout.addWidget(self.btn_test_discord)

        # Use external browser checkbox
        self.chk_external_browser = QCheckBox("Always use external browser (no embedded view)")
        self.chk_external_browser.setChecked(self.config.get("midjourney_external_browser", False))
        self.chk_external_browser.toggled.connect(lambda s: (self.config.set("midjourney_external_browser", bool(s)), self.config.save()))
        midjourney_layout.addWidget(self.chk_external_browser)

        # Info text
        info_label = QLabel(
            "<i>When download watching is enabled, ImageAI will monitor your Downloads folder for new Midjourney images "
            "and automatically associate them with your prompts based on timing and confidence scoring.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 9pt; padding: 10px;")
        midjourney_layout.addWidget(info_label)

        v.addWidget(midjourney_group)

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
        if self.current_provider.lower() == "google" and auth_mode_display == "Google Cloud Account":
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
            self.local_sd_group = QGroupBox("Local Stable Diffusion")
            local_sd_layout = QVBoxLayout(self.local_sd_group)
            self.local_sd_widget = LocalSDWidget()
            self.local_sd_widget.models_changed.connect(self._update_model_list)
            local_sd_layout.addWidget(self.local_sd_widget)
            v.addWidget(self.local_sd_group)
            # Show/hide based on provider
            self.local_sd_group.setVisible(self.current_provider.lower() == "local_sd")
        else:
            self.local_sd_widget = None
            self.local_sd_group = None

        # Midjourney now has its own dedicated tab, no settings needed here

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
            self.btn_help_back = QPushButton("◀ &Back")
            self.btn_help_back.clicked.connect(self.help_browser.back)
            self.btn_help_back.setToolTip("Go back (Alt+Left, Backspace)")
            nav_layout.addWidget(self.btn_help_back)

            # Forward button
            self.btn_help_forward = QPushButton("&Forward ▶")
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
            self.btn_help_home = QPushButton("⌂ &Home")
            self.btn_help_home.clicked.connect(lambda: self.help_browser.page().runJavaScript(
                "window.scrollTo(0, 0);"))
            self.btn_help_home.setToolTip("Go to top (Ctrl+Home)")
            nav_layout.addWidget(self.btn_help_home)

            # Report Problem button
            self.btn_report_problem = QPushButton("🐛 &Report Problem")
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

        except Exception as e:
            # Catch all exceptions, not just ImportError, to ensure fallback always works
            print(f"QWebEngineView initialization failed ({type(e).__name__}: {e}), falling back to QTextBrowser")
            
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
        self.btn_help_back = QPushButton("◀ &Back")
        self.btn_help_back.setEnabled(False)
        self.btn_help_back.setToolTip("Go back (Alt+Left, Backspace)")
        nav_layout.addWidget(self.btn_help_back)
        
        # Forward button
        self.btn_help_forward = QPushButton("&Forward ▶")
        self.btn_help_forward.setEnabled(False)
        self.btn_help_forward.setToolTip("Go forward (Alt+Right)")
        nav_layout.addWidget(self.btn_help_forward)
        
        # Home button
        self.btn_help_home = QPushButton("⌂ &Home")
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

        # Add shortcuts hint with enhanced visibility
        templates_shortcuts_label = create_shortcut_hint("Alt+I to insert into prompt")
        v.addWidget(templates_shortcuts_label)

        # Connect signals
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        self.btn_insert_prompt.clicked.connect(self._apply_template)
    
    def _init_history_tab(self):
        """Initialize history tab with enhanced table display."""
        from PySide6.QtWidgets import QHeaderView, QCheckBox, QHBoxLayout
        # QTableWidget should already be imported at the top, but fallback if needed
        try:
            _ = QTableWidget
        except NameError:
            from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

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
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "Thumbnail", "Date & Time", "Provider", "Model", "Prompt", "Resolution", "Cost"
        ])

        # Configure table
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSortingEnabled(True)

        # Set custom delegate for thumbnail column (owner draw) if available
        if ThumbnailDelegate:
            thumbnail_delegate = ThumbnailDelegate(self.thumbnail_cache, self.history_table)
            self.history_table.setItemDelegateForColumn(0, thumbnail_delegate)
        
        # Set column widths
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Thumbnail
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Date & Time
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Provider
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Model
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # Prompt - takes remaining space
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Resolution
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Cost
        
        # Populate table with history
        self.history_table.setRowCount(len(self.history))

        # Preload thumbnails for first visible rows
        first_visible = 0
        last_visible = min(20, len(self.history))  # Preload first 20 thumbnails

        for row, item in enumerate(self.history):
            if isinstance(item, dict):
                # Thumbnail column - handled by custom delegate
                # Store the path in the item so delegate can access it
                thumbnail_item = QTableWidgetItem()
                file_path = item.get('path', item.get('file_path', ''))
                if file_path:
                    path_str = str(file_path)
                    thumbnail_item.setData(Qt.UserRole, path_str)

                    # Preload thumbnail for visible rows
                    if first_visible <= row <= last_visible:
                        self.thumbnail_cache.get(path_str)  # Load into cache

                self.history_table.setItem(row, 0, thumbnail_item)
                # Set row height to accommodate thumbnail
                self.history_table.setRowHeight(row, 80)

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
                self.history_table.setItem(row, 1, datetime_item)
                
                # Provider column (now column 1)
                provider = item.get('provider', '')
                provider_item = QTableWidgetItem(provider.title() if provider else 'Unknown')
                self.history_table.setItem(row, 2, provider_item)
                
                # Model column (now column 2)
                model = item.get('model', '')
                model_display = model.split('/')[-1] if '/' in model else model  # Simplify model names
                model_item = QTableWidgetItem(model_display)
                model_item.setToolTip(model)  # Full model name in tooltip
                self.history_table.setItem(row, 3, model_item)
                
                # Prompt column (now column 3)
                prompt = item.get('prompt', 'No prompt')
                prompt_item = QTableWidgetItem(prompt)  # Show full prompt, not truncated
                prompt_item.setToolTip(f"Full prompt:\n{prompt}")
                self.history_table.setItem(row, 4, prompt_item)
                
                # Resolution column (now column 4)
                width = item.get('width', '')
                height = item.get('height', '')
                resolution = f"{width}x{height}" if width and height else ''
                resolution_item = QTableWidgetItem(resolution)
                self.history_table.setItem(row, 5, resolution_item)
                
                # Cost column (now column 5)
                cost = item.get('cost', 0.0)
                cost_str = f"${cost:.2f}" if cost > 0 else '-'
                cost_item = QTableWidgetItem(cost_str)
                self.history_table.setItem(row, 6, cost_item)
                
                # Store the history item data in the first column for easy retrieval
                datetime_item.setData(Qt.UserRole, item)

        # Sort by date/time column (1) in descending order (newest first)
        self.history_table.sortByColumn(1, Qt.DescendingOrder)

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

        # Add shortcuts hint with enhanced visibility
        history_shortcuts_label = create_shortcut_hint("Alt+L to load, Alt+C to clear, Click to select and load item")
        v.addWidget(history_shortcuts_label)

        # Connect signals
        self.history_table.selectionModel().selectionChanged.connect(self._on_history_selection_changed)
        self.history_table.itemClicked.connect(self._on_history_item_clicked)
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
            if self.current_provider.lower() == "google":
                self.model_combo.addItem("Gemini 2.5 Flash Image (gemini-2.5-flash-image-preview)", 
                                        "gemini-2.5-flash-image-preview")
            elif self.current_provider.lower() == "openai":
                self.model_combo.addItem("DALL·E 3 (dall-e-3)", "dall-e-3")
            elif self.current_provider.lower() == "stability":
                self.model_combo.addItem("Stable Diffusion XL (stable-diffusion-xl-1024-v1-0)", 
                                        "stable-diffusion-xl-1024-v1-0")
            elif self.current_provider.lower() == "local_sd":
                self.model_combo.addItem("Stable Diffusion 2.1 (stabilityai/stable-diffusion-2-1)",
                                        "stabilityai/stable-diffusion-2-1")
            elif self.current_provider.lower() == "midjourney":
                # Midjourney versions
                self.model_combo.addItem("v6.1 (Latest)", "v6.1")
                self.model_combo.addItem("v6", "v6")
                self.model_combo.addItem("v5.2", "v5.2")
                self.model_combo.addItem("Niji 6 (Anime)", "niji6")
                self.model_combo.addItem("Niji 5 (Anime)", "niji5")
    
    def _update_advanced_visibility(self):
        """Show/hide advanced settings based on provider."""
        # Update new advanced panel if available
        if hasattr(self, 'advanced_panel') and self.advanced_panel:
            self.advanced_panel.update_provider(self.current_provider)
        # Update old advanced group for fallback
        elif hasattr(self, 'advanced_group'):
            # Only show for local_sd provider
            self.advanced_group.setVisible(self.current_provider.lower() == "local_sd")

        # Show/hide Midjourney settings
        if hasattr(self, 'midjourney_group'):
            self.midjourney_group.setVisible(self.current_provider.lower() == "midjourney")

    @staticmethod
    def get_llm_providers():
        """Get list of all available LLM providers."""
        # Get provider IDs, convert to display names, add "None" option
        provider_names = [get_provider_display_name(pid) for pid in get_all_provider_ids()]
        return ["None"] + provider_names

    @staticmethod
    def get_llm_models_for_provider(provider: str):
        """Get list of models for a specific LLM provider."""
        # Handle display name -> provider ID mapping
        provider_map = {
            "claude": "anthropic",
            "google": "gemini",
            "lm studio": "lmstudio"
        }
        provider_id = provider_map.get(provider.lower(), provider.lower())
        return get_provider_models(provider_id)

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
                    # Use centralized model lists
                    models = self.get_llm_models_for_provider(provider_name)
                    if models:
                        self.llm_model_combo.addItems(models)
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

            # Update advanced/Midjourney visibility
            self._update_advanced_visibility()

            # Switch display between image and Midjourney command
            if hasattr(self, 'output_stack'):
                if provider_name == "midjourney":
                    self.output_stack.setCurrentIndex(1)  # Show Midjourney command widget
                else:
                    self.output_stack.setCurrentIndex(0)  # Show image widget

            # Update Generate button text for Midjourney
            if hasattr(self, 'btn_generate'):
                self._update_generate_button_for_provider(provider_name)

            # Hide resolution selector for Midjourney (aspect ratio only)
            if hasattr(self, 'resolution_selector') and self.resolution_selector:
                if provider_name == "midjourney":
                    self.resolution_selector.setVisible(False)
                    # Keep aspect ratio visible and enabled
                    if hasattr(self, 'aspect_selector') and self.aspect_selector:
                        self.aspect_selector.setEnabled(True)
                        self.aspect_selector.setToolTip("Midjourney aspect ratio (e.g., --ar 16:9)")
                else:
                    self.resolution_selector.setVisible(True)
                    if hasattr(self, 'aspect_selector') and self.aspect_selector:
                        self.aspect_selector.setEnabled(True)
                        self.aspect_selector.setToolTip("Select aspect ratio for your image")

            # Show/hide Midjourney options
            if hasattr(self, 'midjourney_options_group'):
                self.midjourney_options_group.setVisible(provider_name == "midjourney")

            # Hide advanced settings for Midjourney
            if hasattr(self, 'advanced_panel') and self.advanced_panel:
                self.advanced_panel.setVisible(provider_name != "midjourney")
            elif hasattr(self, 'advanced_group'):
                self.advanced_group.setVisible(provider_name != "midjourney")

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
            # Google Gemini and Midjourney support reference images
            if hasattr(self, 'btn_select_ref_image'):
                supports_ref = provider_name in ["google", "midjourney"]
                self.btn_select_ref_image.setEnabled(supports_ref)
                if provider_name == "google":
                    self.btn_select_ref_image.setToolTip("Choose a starting image for generation (Google Gemini)")
                elif provider_name == "midjourney":
                    self.btn_select_ref_image.setToolTip("Choose a reference image (will be noted in command)")
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
                # Hide resolution for Midjourney (not yet supported)
                self.resolution_selector.setVisible(provider_name != "midjourney")
                if provider_name != "midjourney":
                    self.resolution_selector.update_provider(self.current_provider)

            if hasattr(self, 'quality_selector') and self.quality_selector:
                # Hide quality for Midjourney (has its own quality control)
                self.quality_selector.setVisible(provider_name != "midjourney")
                if provider_name != "midjourney":
                    self.quality_selector.update_provider(self.current_provider)

            if hasattr(self, 'advanced_panel') and self.advanced_panel:
                # Hide advanced panel for Midjourney (has its own settings)
                self.advanced_panel.setVisible(provider_name != "midjourney")
                if provider_name != "midjourney":
                    self.advanced_panel.update_provider(self.current_provider)

            # Hide upscaling for Midjourney
            if hasattr(self, 'upscaling_selector') and self.upscaling_selector:
                self.upscaling_selector.setVisible(provider_name != "midjourney")

            # Hide batch selector for Midjourney
            if hasattr(self, 'batch_selector') and self.batch_selector:
                self.batch_selector.setVisible(provider_name != "midjourney")

            # Hide social sizes button for Midjourney
            if hasattr(self, 'btn_social_sizes') and self.btn_social_sizes:
                self.btn_social_sizes.setVisible(provider_name != "midjourney")

            # Update Imagen reference widget visibility
            self._update_imagen_reference_visibility()

    def _on_model_changed(self, model_name: str):
        """Handle model selection change."""
        if self.current_provider.lower() == "local_sd" and hasattr(self, 'steps_spin'):
            # Auto-adjust for Turbo models
            if 'turbo' in model_name.lower():
                self.steps_spin.setValue(2)  # 1-4 steps for turbo
                self.guidance_spin.setValue(0.0)  # No CFG for turbo
                # Set resolution to 1024x1024 for SDXL turbo
                if 'sdxl' in model_name.lower():
                    idx = self.resolution_combo.findText("1024x1024", Qt.MatchContains)
                    if idx >= 0:
                        self.resolution_combo.setCurrentIndex(idx)

        # Show/hide Imagen reference widget based on provider and model
        self._update_imagen_reference_visibility()
    
    def _on_provider_changed(self, provider: str):
        """Handle provider change from Settings tab."""
        self.current_provider = provider.lower()
        self.config.set("provider", self.current_provider)
        self.config.save()

        # Update reference image button states
        self._update_use_current_button_state()

        # Switch display between image and Midjourney command
        if hasattr(self, 'output_stack'):
            if self.current_provider.lower() == "midjourney":
                self.output_stack.setCurrentIndex(1)  # Show Midjourney command widget
                # Midjourney command is now built by the provider, no update needed
            else:
                self.output_stack.setCurrentIndex(0)  # Show image widget

    def _update_imagen_reference_visibility(self):
        """Update visibility of Reference Images toggle based on provider."""
        if not hasattr(self, 'ref_image_toggle'):
            return

        # Show Reference Images section only for Google provider
        current_provider = self.image_provider_combo.currentText().lower()
        show_toggle = current_provider == "google"

        self.ref_image_toggle.setVisible(show_toggle)

        # If switching away from Google and section is expanded, collapse it
        if not show_toggle and self.ref_image_toggle.isChecked():
            self.ref_image_toggle.setChecked(False)
            self.ref_image_container.setVisible(False)

        # If switching TO Google, show a helpful message if there are references
        if show_toggle and hasattr(self, 'imagen_reference_widget'):
            if self.imagen_reference_widget.has_references():
                logger.info(f"Google provider selected with {len(self.imagen_reference_widget.get_references())} reference images ready")

        logger.debug(f"Reference images toggle visibility: {show_toggle} (provider: {current_provider})")

    def _update_reference_buttons(self, num_references):
        """Dynamically create/update reference insertion buttons based on count."""
        if not hasattr(self, 'ref_tag_buttons_layout'):
            return

        # Remove existing buttons (keep the label)
        while self.ref_tag_buttons_layout.count() > 1:  # Keep "Insert ref:" label
            item = self.ref_tag_buttons_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        # Create buttons for each reference
        for i in range(1, num_references + 1):
            btn = QPushButton(f"[{i}]")
            btn.setFixedSize(35, 22)
            btn.setToolTip(f"Insert reference tag [{i}] at cursor position")
            btn.clicked.connect(lambda checked, tag=f"[{i}]": self._insert_reference_tag(tag))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            self.ref_tag_buttons_layout.addWidget(btn)

    def _on_imagen_references_changed(self):
        """Handle when Imagen reference images change."""
        if not hasattr(self, 'imagen_reference_widget'):
            return

        references = self.imagen_reference_widget.get_references()
        logger.info(f"Imagen references changed: {len(references)} references")

        # Auto-save to config
        self._save_imagen_references_to_config()

        # Update reference tag insertion buttons dynamically
        if hasattr(self, 'ref_tag_buttons_widget'):
            self._update_reference_buttons(len(references))
            self.ref_tag_buttons_widget.setVisible(len(references) > 0)

        # Update prompt placeholder if references exist
        if references and hasattr(self, 'prompt_edit'):
            ref_tags = ", ".join([f"[{i+1}]" for i in range(len(references))])
            hint = f"Use {ref_tags} in your prompt to reference the images above"
            current_placeholder = self.prompt_edit.placeholderText()
            if "[" not in current_placeholder:  # Don't override if already has hint
                self.prompt_edit.setPlaceholderText(
                    f"Describe what to generate... (Ctrl+Enter to generate)\n{hint}"
                )
        else:
            # Reset placeholder when no references
            if hasattr(self, 'prompt_edit'):
                self.prompt_edit.setPlaceholderText("Describe what to generate... (Ctrl+Enter to generate)")

    def _insert_reference_tag(self, tag: str):
        """Insert a reference tag at the current cursor position in the prompt."""
        if hasattr(self, 'prompt_edit'):
            cursor = self.prompt_edit.textCursor()
            cursor.insertText(tag)
            self.prompt_edit.setFocus()
            logger.debug(f"Inserted reference tag: {tag}")

        # Update Generate button text for Midjourney
        if hasattr(self, 'btn_generate'):
            self._update_generate_button_for_provider(self.current_provider)

        # Hide resolution selector for Midjourney (aspect ratio only)
        if hasattr(self, 'resolution_selector') and self.resolution_selector:
            if self.current_provider.lower() == "midjourney":
                self.resolution_selector.setVisible(False)
                # Keep aspect ratio visible and enabled
                if hasattr(self, 'aspect_selector') and self.aspect_selector:
                    self.aspect_selector.setEnabled(True)
                    self.aspect_selector.setToolTip("Midjourney aspect ratio (e.g., --ar 16:9)")
            else:
                self.resolution_selector.setVisible(True)
                if hasattr(self, 'aspect_selector') and self.aspect_selector:
                    self.aspect_selector.setEnabled(True)
                    self.aspect_selector.setToolTip("Select aspect ratio for your image")

        # Show/hide Midjourney options
        if hasattr(self, 'midjourney_options_group'):
            self.midjourney_options_group.setVisible(self.current_provider.lower() == "midjourney")

        # Hide advanced settings for Midjourney
        if hasattr(self, 'advanced_panel') and self.advanced_panel:
            self.advanced_panel.setVisible(self.current_provider != "midjourney")
        elif hasattr(self, 'advanced_group'):
            self.advanced_group.setVisible(self.current_provider != "midjourney")

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
        if self.current_provider.lower() == "google":
            self.api_key_edit = self.google_key_edit
            self.current_api_key = self.google_key_edit.text().strip()
        elif self.current_provider.lower() == "openai":
            self.api_key_edit = self.openai_key_edit
            self.current_api_key = self.openai_key_edit.text().strip()
        elif self.current_provider.lower() == "stability":
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
        if hasattr(self, 'local_sd_group') and self.local_sd_group:
            self.local_sd_group.setVisible(self.current_provider.lower() == "local_sd")

        # Midjourney is now in its own tab, no provider-specific settings needed

    def _update_generate_button_for_provider(self, provider_name: str):
        """Set the Generate button text/tooltip based on provider + settings."""
        if not hasattr(self, 'btn_generate'):
            return
        if provider_name == "midjourney":
            use_discord = self.config.get("midjourney_use_discord", False)
            if use_discord:
                self.btn_generate.setText("Copy && Open &Discord")
                self.btn_generate.setToolTip("Copy command to clipboard and open Discord (Alt+D or Ctrl+Enter)")
            else:
                self.btn_generate.setText("Generate with &Midjourney")
                self.btn_generate.setToolTip("Open Midjourney web interface (Alt+G or Ctrl+Enter)")
        else:
            self.btn_generate.setText("&Generate")
            self.btn_generate.setToolTip("Generate image (Alt+G or Ctrl+Enter)")
    
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
        # Midjourney command is now built by the provider, no update needed
        # Update the "Will insert" preview to show resolution
        self._update_ref_instruction_preview()
    
    def _on_resolution_changed(self, resolution: str):
        """Handle resolution change."""
        self.current_resolution = resolution
        # Clear social size label when resolution is manually changed
        if hasattr(self, 'social_size_label'):
            self.social_size_label.setVisible(False)
            self.social_size_label.setText("")
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
        if self.current_provider.lower() == "local_sd":
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
        
        if self.current_provider.lower() == "local_sd":
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
    
    def _browse_downloads_folder(self):
        """Browse for Midjourney downloads folder."""
        current_path = self.midjourney_downloads_edit.text() or QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Downloads Folder",
            current_path,
            QFileDialog.ShowDirsOnly
        )
        if folder:
            self.midjourney_downloads_edit.setText(folder)

    def _on_midjourney_discord_fields_changed(self):
        """Persist Discord server/channel IDs immediately when edited."""
        try:
            server = self.discord_server_edit.text().strip()
            channel = self.discord_channel_edit.text().strip()
            self.config.set("midjourney_discord_server", server)
            self.config.set("midjourney_discord_channel", channel)
            self.config.save()
            # No dialog; keep it quiet
        except Exception:
            pass

    def _on_midjourney_use_discord_toggled(self, checked: bool):
        """Persist Use Discord setting and update button label."""
        self.config.set("midjourney_use_discord", bool(checked))
        self.config.save()
        if hasattr(self, 'btn_generate'):
            self._update_generate_button_for_provider(self.current_provider)

    def _save_and_test(self):
        """Save all API keys and settings, then test the current provider."""
        from core.security import secure_storage

        # Save all API keys - IMPORTANT: Delete if empty to allow switching to gcloud
        google_key = self.google_key_edit.text().strip()
        if google_key:
            self.config.set_api_key("google", google_key)
            self.config.set("google_api_key", google_key)  # Backward compatibility
        else:
            # Clear Google API key from all locations
            secure_storage.delete_key("google")
            # Remove from config file
            if "google_api_key" in self.config.config:
                del self.config.config["google_api_key"]
            # Remove from providers config
            provider_config = self.config.get_provider_config("google")
            if "api_key" in provider_config:
                del provider_config["api_key"]
                self.config.set_provider_config("google", provider_config)

        openai_key = self.openai_key_edit.text().strip()
        if openai_key:
            self.config.set_api_key("openai", openai_key)
            self.config.set("openai_api_key", openai_key)  # Backward compatibility
        else:
            # Clear OpenAI API key from all locations
            secure_storage.delete_key("openai")
            if "openai_api_key" in self.config.config:
                del self.config.config["openai_api_key"]
            provider_config = self.config.get_provider_config("openai")
            if "api_key" in provider_config:
                del provider_config["api_key"]
                self.config.set_provider_config("openai", provider_config)

        stability_key = self.stability_key_edit.text().strip()
        if stability_key:
            self.config.set_api_key("stability", stability_key)
            self.config.set("stability_api_key", stability_key)  # Backward compatibility
        else:
            # Clear Stability API key from all locations
            secure_storage.delete_key("stability")
            if "stability_api_key" in self.config.config:
                del self.config.config["stability_api_key"]
            provider_config = self.config.get_provider_config("stability")
            if "api_key" in provider_config:
                del provider_config["api_key"]
                self.config.set_provider_config("stability", provider_config)

        anthropic_key = self.anthropic_key_edit.text().strip()
        if anthropic_key:
            self.config.set_api_key("anthropic", anthropic_key)
            self.config.set("anthropic_api_key", anthropic_key)  # Backward compatibility
        else:
            # Clear Anthropic API key from all locations
            secure_storage.delete_key("anthropic")
            if "anthropic_api_key" in self.config.config:
                del self.config.config["anthropic_api_key"]
            provider_config = self.config.get_provider_config("anthropic")
            if "api_key" in provider_config:
                del provider_config["api_key"]
                self.config.set_provider_config("anthropic", provider_config)

        # Save Midjourney settings
        self.config.set("midjourney_watch_enabled", self.chk_midjourney_watch.isChecked())
        self.config.set("midjourney_downloads_path", self.midjourney_downloads_edit.text())
        self.config.set("midjourney_auto_accept", self.midjourney_threshold_spin.value())
        self.config.set("midjourney_time_window", self.midjourney_window_spin.value())
        self.config.set("midjourney_notifications", self.chk_midjourney_notify.isChecked())
        self.config.set("midjourney_use_discord", self.chk_use_discord.isChecked())
        self.config.set("midjourney_discord_server", self.discord_server_edit.text())
        self.config.set("midjourney_discord_channel", self.discord_channel_edit.text())
        self.config.set("midjourney_external_browser", self.chk_external_browser.isChecked())

        # Save configuration
        self.config.save()

        # Reinitialize watcher if settings changed
        if self.chk_midjourney_watch.isChecked():
            self._init_midjourney_watcher()
        elif self.midjourney_watcher:
            # Disable watcher if unchecked
            self.midjourney_watcher.set_enabled(False)
            self._append_to_console("Midjourney download watcher disabled", "#888888")

        # Get the key for the current provider
        if self.current_provider.lower() == "google":
            key = google_key
        elif self.current_provider.lower() == "openai":
            key = openai_key
        elif self.current_provider.lower() == "stability":
            key = stability_key
        elif self.current_provider.lower() == "midjourney":
            # Midjourney is manual-only, no authentication needed
            key = ""
        elif self.current_provider.lower() == "local_sd":
            key = ""
        else:
            key = self.api_key_edit.text().strip()

        # Check if using Google Cloud auth mode
        is_google = self.current_provider.lower() == "google"
        auth_mode_text = self.auth_mode_combo.currentText() if is_google else "API Key"
        is_gcloud_auth = auth_mode_text == "Google Cloud Account"

        # Validate we have a key for non-local providers (unless using gcloud auth)
        if self.current_provider.lower() not in ["local_sd", "midjourney"] and not key and not is_gcloud_auth:
            QMessageBox.warning(self, APP_NAME, f"Please enter an API key for {self.current_provider}.")
            return

        self.current_api_key = key

        # Test connection for the current provider
        try:
            # Include auth_mode in provider config
            auth_mode_value = "gcloud" if is_gcloud_auth else "api-key"
            provider_config = {
                "api_key": key,
                "auth_mode": auth_mode_value
            }

            provider = get_provider(self.current_provider, provider_config)
            is_valid, message = provider.validate_auth()

            if is_valid:
                QMessageBox.information(self, APP_NAME, f"Settings saved and {self.current_provider} validated!\n{message}")
            else:
                QMessageBox.warning(self, APP_NAME, f"{self.current_provider} test failed:\n{message}")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Error testing {self.current_provider}:\n{str(e)}")
    
    def _toggle_auto_copy(self, checked: bool):
        """Toggle auto-copy filename setting."""
        self.auto_copy_filename = checked
        self.config.set("auto_copy_filename", checked)
        self.config.save()
    
    def _update_auth_visibility(self):
        """Update visibility of auth-related widgets based on provider and auth mode."""
        is_google = self.current_provider.lower() == "google"
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

        # DON'T auto-check on mode change - this was causing main thread to freeze
        # User must click "Check Status" button explicitly to check gcloud auth
        # The check now runs in a background thread (GCloudStatusChecker)
    
    # Midjourney settings are now handled in the dedicated Midjourney tab

    def _on_prompt_text_changed(self):
        """Handle prompt text changes."""
        # Midjourney command is now built by the provider, no update needed
        pass

    def _test_discord_channel(self):
        """Test the Discord channel configuration by opening it."""
        server_id = self.discord_server_edit.text().strip()
        channel_id = self.discord_channel_edit.text().strip()

        if not server_id or not channel_id:
            QMessageBox.warning(
                self,
                APP_NAME,
                "Please enter both Discord Server ID and Channel ID to test."
            )
            return

        # Build Discord URL
        discord_url = f"https://discord.com/channels/{server_id}/{channel_id}"

        try:
            import webbrowser
            webbrowser.open(discord_url)
            self._append_to_console(f"Opening Discord channel: {discord_url}", "#7289DA")
            QMessageBox.information(
                self,
                APP_NAME,
                f"Discord channel opened in browser.\n\nIf the channel loads correctly, your configuration is valid."
            )
        except Exception as e:
            logger.error(f"Failed to open Discord channel: {e}")
            QMessageBox.critical(
                self,
                APP_NAME,
                f"Failed to open Discord channel:\n{str(e)}"
            )

    def _check_gcloud_status(self):
        """Check Google Cloud CLI status asynchronously using background thread."""
        # Show "checking" status immediately (non-blocking)
        self.gcloud_status_label.setText("⟳ Checking...")
        self.gcloud_status_label.setStyleSheet("color: blue;")
        self.btn_check_status.setEnabled(False)  # Prevent multiple simultaneous checks

        # Start background thread (non-blocking)
        self.gcloud_checker = GCloudStatusChecker()
        self.gcloud_checker.status_checked.connect(self._on_gcloud_status_checked)
        self.gcloud_checker.project_id_fetched.connect(self._on_project_id_fetched)
        self.gcloud_checker.finished.connect(lambda: self.btn_check_status.setEnabled(True))
        self.gcloud_checker.start()

    def _on_gcloud_status_checked(self, is_auth: bool, status_msg: str):
        """Handle gcloud status check results (runs on main thread via signal)."""
        if is_auth:
            self.gcloud_status_label.setText("✓ Authenticated")
            self.gcloud_status_label.setStyleSheet("color: green;")
            self.config.set("gcloud_auth_validated", True)
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

    def _on_project_id_fetched(self, project_id: str):
        """Handle project ID fetch (runs on main thread via signal)."""
        self.project_id_edit.setText(project_id)
        self.config.set("gcloud_project_id", project_id)
        self.config.save()
    
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
            # DON'T try to detect from gcloud here - it would block the main thread
            # User can click "Check Status" button to detect it in background thread
            self.config.set("gcloud_project_id", "")

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
        # Allow opening with empty prompt - dialog becomes "Ask Anything"
        dlg = PromptQuestionDialog(self, self.config, current_prompt)
        dlg.exec()

    def _open_reference_image(self):
        """Open reference image analysis dialog."""
        from .reference_image_dialog import ReferenceImageDialog

        dlg = ReferenceImageDialog(self, self.config)

        # Connect to receive the generated description
        def on_description_generated(description):
            # Append to existing prompt or replace if empty
            current_prompt = self.prompt_edit.toPlainText().strip()
            if current_prompt:
                # Append with a newline
                self.prompt_edit.setPlainText(f"{current_prompt}\n\n{description}")
            else:
                self.prompt_edit.setPlainText(description)

        dlg.descriptionGenerated.connect(on_description_generated)
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

    def _get_provider_max_resolution(self) -> int:
        """Get maximum resolution for current provider."""
        if self.current_provider.lower() == "google":
            return 1024
        elif self.current_provider.lower() == "openai":
            return 1792
        elif self.current_provider.lower() == "stability":
            return 1536
        elif self.current_provider.lower() == "local_sd":
            return 2048  # Can vary based on local GPU
        else:
            return 1024  # Default conservative limit

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
        if self.current_provider.lower() == "google":
            provider_max = 1024
        elif self.current_provider.lower() == "openai":
            provider_max = 1792
        elif self.current_provider.lower() == "stability":
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
            if self.current_provider.lower() == "google":
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

        # Check for resolution in prompt and warn user
        # NOTE: Only block LITERAL dimensions (1024x768, 1920x1080, etc.) that get rendered as text.
        # Quality descriptors like "8K resolution", "4K quality" are artistic direction and are fine.
        import re
        resolution_patterns = [
            r'\(\d+\s*[xX]\s*\d+\)',  # (1024x768)
            r'\[\d+\s*[xX]\s*\d+\]',  # [1024x768]
            r'\b\d{3,4}\s*[xX]\s*\d{3,4}\b',  # 1024x768 or 1920x1080
            r'\bat\s+\d+\s*[xX]\s*\d+',  # at 1024x768
            r'\b\d+\s*[xX]\s*\d+\s*(resolution|pixels?|size)',  # 1024x768 resolution
            # Removed 4K/8K/HD pattern - these are quality descriptors, not literal dimensions
        ]

        detected_resolutions = []
        for pattern in resolution_patterns:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            detected_resolutions.extend(matches)

        if detected_resolutions:
            # Create warning dialog
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Literal Dimensions Detected in Prompt")
            msg.setText("Your prompt contains literal pixel dimensions (e.g., '1024x768') which may be rendered as text in the image. Please remove them and use the Resolution/Aspect Ratio controls instead.\n\nNote: Quality descriptors like '8K resolution' or '4K quality' are fine and won't trigger this warning.")

            # Show what was detected
            # Convert tuples to strings (regex patterns with capture groups return tuples)
            detected_strings = []
            for match in detected_resolutions:
                if isinstance(match, tuple):
                    # Join non-empty tuple elements
                    detected_strings.append(" ".join(filter(None, match)))
                else:
                    detected_strings.append(str(match))
            detected_text = ", ".join(set(detected_strings))
            msg.setInformativeText(f"Detected literal dimensions: {detected_text}\n\nUse the Resolution/Aspect Ratio controls in the GUI to specify your desired output size.")

            # Add buttons
            remove_btn = msg.addButton("Remove and Continue", QMessageBox.AcceptRole)
            cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)
            msg.setDefaultButton(cancel_btn)

            msg.exec_()

            if msg.clickedButton() == cancel_btn:
                self.btn_generate.setEnabled(True)
                self._append_to_console("Generation cancelled - please edit your prompt", "#ffaa00")  # Orange
                return
            elif msg.clickedButton() == remove_btn:
                # Remove all resolution patterns from prompt
                cleaned_prompt = prompt
                for pattern in resolution_patterns:
                    cleaned_prompt = re.sub(pattern, '', cleaned_prompt, flags=re.IGNORECASE)
                # Clean up extra spaces
                cleaned_prompt = re.sub(r'\s+', ' ', cleaned_prompt).strip()

                # Update the prompt in the GUI
                self.prompt_edit.setPlainText(cleaned_prompt)
                prompt = cleaned_prompt
                self._append_to_console(f"Removed literal dimensions from prompt", "#66ccff")  # Blue

        # Store original prompt (before reference image modifications)
        original_prompt = prompt

        # Check if using Google Cloud auth mode (no API key needed)
        is_using_gcloud = False
        if self.current_provider.lower() in ["google", "imagen_customization"]:
            auth_mode_text = self.auth_mode_combo.currentText()
            is_using_gcloud = auth_mode_text == "Google Cloud Account"

        # Validate API key (unless using gcloud auth or local/manual providers)
        if not self.current_api_key and not is_using_gcloud and self.current_provider.lower() not in ["local_sd", "midjourney"]:
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
                # Using aspect ratio mode - get aspect ratio from resolution selector
                aspect_ratio = self.resolution_selector.get_aspect_ratio()
                kwargs['aspect_ratio'] = aspect_ratio
                # Enable cropping for Google provider when aspect ratio is selected
                # But the provider will now check if the returned image already matches before cropping
                if self.current_provider.lower() == "google":
                    kwargs['crop_to_aspect'] = True

                    # For non-Google providers, provide resolution string for proper size mapping
                    if self.current_provider.lower() != "google":
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

                        # Pass width/height for all providers including Google
                        # Google provider needs these to determine if dimensions should be added to prompt
                        if width:
                            kwargs['width'] = width
                        if height:
                            kwargs['height'] = height

                        # Also store for UI message display
                        if self.current_provider.lower() == "google":
                            self._pending_resolution = (width, height)
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
                    # Google providers (google and imagen_customization) support exact aspect ratios
                    google_providers = ["google", "imagen_customization"]
                    if self.current_provider.lower() not in google_providers:
                        # Non-Google providers: use closest aspect ratio and store target for scaling
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
                        # Google providers: use exact dimensions and calculate aspect ratio
                        kwargs['width'] = width
                        kwargs['height'] = height
                        # Calculate aspect ratio for proper logging and prompt generation
                        aspect_ratio = self._find_closest_aspect_ratio(width, height, "google")
                        kwargs['aspect_ratio'] = aspect_ratio
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
        elif self.current_provider.lower() == "local_sd":
            # Fallback to old advanced settings for local_sd
            if hasattr(self, 'steps_spin'):
                kwargs['steps'] = self.steps_spin.value()
            if hasattr(self, 'guidance_spin'):
                kwargs['cfg_scale'] = self.guidance_spin.value()
        
        # Add reference image if enabled and available (Google Gemini only)
        if (self.current_provider.lower() == "google" and
            hasattr(self, 'reference_image_data') and
            self.reference_image_data and
            hasattr(self, 'ref_image_enabled') and
            self.ref_image_enabled.isChecked()):
            kwargs['reference_image'] = self.reference_image_data


        # Check if we have a reference image
        if (hasattr(self, 'reference_image_data') and
            self.reference_image_data and
            hasattr(self, 'ref_image_enabled') and
            self.ref_image_enabled.isChecked()):
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
            width = height = None
            if 'width' in kwargs and 'height' in kwargs:
                width = kwargs['width']
                height = kwargs['height']
            elif hasattr(self, '_pending_resolution') and self._pending_resolution:
                # Use stored resolution from aspect ratio mode (Google provider)
                width, height = self._pending_resolution
                # Don't clear here, might be needed for the else block too

            if width and height:
                # For Google provider, don't add dimensions (they get rendered as literal text)
                # For other providers, add dimensions to instruction
                if self.current_provider.lower() == 'google':
                    # Google uses image_config parameter, dimensions in text get rendered
                    resolution_text = ""
                else:
                    resolution_text = f" (Image will be {width}x{height}, scale to fit.)"

            # Build instruction and prepend to prompt for generation only
            if resolution_text:
                instruction = f"{', '.join(instruction_parts)}.{resolution_text}"
            else:
                instruction = f"{', '.join(instruction_parts)}."
            # Create modified prompt for generation (original_prompt already stored)
            prompt = f"{instruction} {prompt}"

            self._append_to_console(f"Using reference image: {self.reference_image_path.name if self.reference_image_path else 'Unknown'}", "#66ccff")
            self._append_to_console(f"Auto-inserted: \"{instruction}\"", "#9966ff")
        else:
            # No reference image, but check if we need to add resolution info
            # Check both kwargs and pending_resolution for Google aspect ratio mode
            width = height = None
            if 'width' in kwargs and 'height' in kwargs:
                width = kwargs['width']
                height = kwargs['height']
            elif hasattr(self, '_pending_resolution') and self._pending_resolution:
                # Use stored resolution from aspect ratio mode (Google provider)
                width, height = self._pending_resolution
                self._pending_resolution = None  # Clear it after use

            # For Google provider, NEVER insert dimensions into prompt (they get rendered as literal text)
            # Google uses image_config parameter instead
            # For other providers, insert dimensions into prompt
            if width and height:
                if self.current_provider.lower() == 'google':
                    # Don't insert dimensions for Google - it uses image_config parameter
                    # Dimensions in text get rendered as literal text in the image
                    pass
                elif width != 1024 or height != 1024:
                    # For non-Google providers, add dimensions to prompt
                    resolution_text = f"(Image will be {width}x{height}, scale to fit.)"
                    prompt = f"{resolution_text} {prompt}"
                    self._append_to_console(f"Auto-inserted: \"{resolution_text}\"", "#9966ff")

        # Handle Midjourney-specific setup
        if self.current_provider.lower() == "midjourney":
            # Add Midjourney parameters from UI elements
            if hasattr(self, 'mj_stylize_slider'):
                kwargs['stylize'] = self.mj_stylize_slider.value()
            if hasattr(self, 'mj_chaos_slider'):
                kwargs['chaos'] = self.mj_chaos_slider.value()
            if hasattr(self, 'mj_weird_slider'):
                kwargs['weird'] = self.mj_weird_slider.value()
            if hasattr(self, 'mj_quality_combo'):
                kwargs['quality'] = float(self.mj_quality_combo.currentText())
            if hasattr(self, 'mj_seed_spin') and self.mj_seed_spin.value() >= 0:
                kwargs['seed'] = self.mj_seed_spin.value()

            # The provider will handle command building and mode selection

        # Check for Imagen 3 multi-reference generation
        use_imagen_customization = False

        # First, check if user has references but is NOT using Google
        if (hasattr(self, 'imagen_reference_widget') and
            self.imagen_reference_widget.has_references() and
            self.current_provider.lower() != "google"):

            # User has reference images but is using a non-Google provider
            error_msg = (f"Reference images are only supported with Google Imagen 3.\n\n"
                        f"Current provider: {self.current_provider}\n\n"
                        f"Please either:\n"
                        f"• Switch to Google provider in Settings, or\n"
                        f"• Remove the reference images to use {self.current_provider}")
            self._append_to_console(f"ERROR: {error_msg}", "#ff6666")
            QMessageBox.warning(self, APP_NAME, error_msg)
            self.btn_generate.setEnabled(True)
            return

        # Now check if using Google with references
        if (hasattr(self, 'imagen_reference_widget') and
            self.imagen_reference_widget.has_references() and
            self.current_provider.lower() == "google"):

            # Get references from widget
            references = self.imagen_reference_widget.get_references()

            # Validate references
            is_valid, errors = self.imagen_reference_widget.validate_references()
            if not is_valid:
                error_msg = "Invalid reference images:\n" + "\n".join(errors)
                self._append_to_console(f"ERROR: {error_msg}", "#ff6666")
                QMessageBox.warning(self, APP_NAME, error_msg)
                self.btn_generate.setEnabled(True)
                return

            # Check mode: Flexible or Strict
            mode = self.imagen_reference_widget.get_mode()

            if mode == "flexible":
                # Flexible mode: Use Google Gemini with reference(s) (style transfer)
                # Multiple references are auto-composited into a single image

                ref_path = None  # Will hold either single ref or composite

                if len(references) == 1:
                    # Single reference: use as-is
                    ref_path = references[0].path
                    self._append_to_console(
                        f"Using Flexible mode (style transfer) with reference: {ref_path.name}",
                        "#00ff00"
                    )

                elif len(references) > 1:
                    # Multiple references: composite them
                    self._append_to_console(
                        f"Compositing {len(references)} reference images...",
                        "#66ccff"
                    )

                    # Import compositor
                    from core.reference.image_compositor import ReferenceImageCompositor
                    from core.constants import get_user_data_dir

                    # Create compositor
                    compositor = ReferenceImageCompositor(canvas_size=1024)

                    # Collect image paths
                    image_paths = [ref.path for ref in references]

                    # Create output path for composite
                    composite_dir = get_user_data_dir() / "composites"
                    composite_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    composite_path = composite_dir / f"composite_{timestamp}.png"

                    # Composite images
                    ref_path = compositor.composite_images(
                        image_paths=image_paths,
                        output_path=composite_path,
                        arrangement="grid"
                    )

                    if not ref_path or not ref_path.exists():
                        msg = "Failed to composite reference images. Check console for details."
                        self._append_to_console(f"ERROR: {msg}", "#ff6666")
                        QMessageBox.warning(self, APP_NAME, msg)
                        self.btn_generate.setEnabled(True)
                        return

                    self._append_to_console(
                        f"✓ Composited {len(references)} images: {ref_path.name}",
                        "#00ff00"
                    )

                    # Enhance prompt with arrangement instructions
                    # User's prompt should be like "These people as cartoon characters"
                    # We append the arrangement instructions
                    composite_prompt = ReferenceImageCompositor.generate_composite_prompt(
                        prompt,  # User's prompt is the composite description
                        len(references)
                    )

                    # Use the enhanced prompt
                    prompt = composite_prompt

                    self._append_to_console(
                        f"Enhanced prompt: {prompt}",
                        "#66ccff"
                    )

                # Read the reference image as bytes (single or composite)
                with open(ref_path, 'rb') as f:
                    reference_image_bytes = f.read()

                # Pass as reference_image parameter (Google provider behavior)
                kwargs['reference_image'] = reference_image_bytes

            else:
                # Strict mode: Use Imagen 3 Customization (subject preservation)
                # Validate prompt has reference tags [N]
                import re
                ref_tags = re.findall(r'\[(\d+)\]', prompt)
                if not ref_tags:
                    msg = (f"Your prompt must reference the images using tags like [1], [2], etc.\n\n"
                           f"You have {len(references)} reference image(s).\n"
                           f"Example: 'A photo of [1] and [2] at the beach'")
                    self._append_to_console(f"ERROR: {msg}", "#ff6666")
                    QMessageBox.warning(self, APP_NAME, msg)
                    self.btn_generate.setEnabled(True)
                    return

                # Switch to ImagenCustomizationProvider
                use_imagen_customization = True
                # Store original provider to restore after generation
                self._imagen_original_provider = self.current_provider
                self.current_provider = "imagen_customization"

                # Pass references in kwargs
                kwargs['references'] = references

                self._append_to_console(
                    f"Using Strict mode (Imagen 3 Customization) with {len(references)} reference image(s)",
                    "#00ff00"
                )
                for i, ref in enumerate(references, start=1):
                    self._append_to_console(
                        f"  [{i}] {ref.reference_type.value.upper()}: {ref.path.name}",
                        "#66ccff"
                    )

        # Show status for provider loading
        self.status_bar.showMessage(f"Connecting to {self.current_provider}...")
        self._append_to_console(f"Connecting to {self.current_provider}...", "#66ccff")  # Blue
        QApplication.processEvents()

        # Create worker thread
        self.gen_thread = QThread()
        # Get the actual auth mode from config
        auth_mode = "api-key"  # default
        if self.current_provider.lower() == "google" or use_imagen_customization:
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
        if self.current_provider.lower() == "google":
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
        if self.current_provider.lower() == "google":
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
        # Restore original provider if we used Imagen customization
        if hasattr(self, '_imagen_original_provider'):
            self.current_provider = self._imagen_original_provider
            delattr(self, '_imagen_original_provider')

        self.status_label.setText("Error occurred.")
        self.status_bar.showMessage(f"Error: {error[:50]}...")  # Show truncated error in status
        self._append_to_console(f"ERROR: {error}", "#ff6666")  # Red
        QMessageBox.critical(self, APP_NAME, f"Generation failed:\n{error}")
        self.btn_generate.setEnabled(True)
        self._cleanup_thread()

    def _on_generation_finished(self, texts: List[str], images: List[bytes]):
        """Handle successful generation."""
        # Restore original provider if we used Imagen customization
        if hasattr(self, '_imagen_original_provider'):
            self.current_provider = self._imagen_original_provider
            delattr(self, '_imagen_original_provider')

        # Check if this is a Midjourney mode response
        if texts:
            for text in texts:
                if text.startswith("MIDJOURNEY_WEB_MODE:"):
                    # Handle embedded web mode
                    # Parse the response: MIDJOURNEY_WEB_MODE:url|slash_command
                    parts = text.replace("MIDJOURNEY_WEB_MODE:", "").split("|", 1)
                    if len(parts) == 2:
                        web_url, slash_command = parts
                        self._open_midjourney_web_dialog(web_url, slash_command)
                        return
                elif text.startswith("MIDJOURNEY_EXTERNAL_BROWSER:"):
                    # Handle external browser mode
                    # Parse the response: MIDJOURNEY_EXTERNAL_BROWSER:url|slash_command
                    parts = text.replace("MIDJOURNEY_EXTERNAL_BROWSER:", "").split("|", 1)
                    if len(parts) == 2:
                        web_url, slash_command = parts
                        self._open_midjourney_external_browser(web_url, slash_command)
                        return

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
                    # Only upscale if target exceeds provider capabilities
                    # Never upscale just because provider returned smaller than expected
                    provider_max = self._get_provider_max_resolution()
                    should_enable_upscaling = target_width > provider_max or target_height > provider_max

                    upscaled_images = []
                    for image_data in processed_images:
                        # Check if upscaling is needed
                        from PIL import Image
                        import io
                        from core.upscaling import needs_upscaling, upscale_image

                        img = Image.open(io.BytesIO(image_data))
                        # Only upscale if target exceeds provider limits AND image is smaller than target
                        if should_enable_upscaling and needs_upscaling(img.width, img.height, target_width, target_height):
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
                    'cost': generation_cost / len(images) if generation_cost else 0.0,
                    'source_tab': 'image'  # Mark as from image tab
                }

                # Add resolution if available
                if 'width' in settings:
                    history_entry['width'] = settings['width']
                    history_entry['height'] = settings['height']
                
                # Add to history list
                self.history.append(history_entry)

            # Add new entries to history table without refreshing everything
            if hasattr(self, 'history_table'):
                self._add_to_history_table(history_entry)
            
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
            #     if hasattr(self, 'current_provider') and self.current_provider.lower() == 'google':
            #         image_data = auto_crop_solid_borders(image_data)
            # except ImportError:
            #     pass  # image_utils not available, skip auto-crop

            pixmap = QPixmap()
            pixmap.loadFromData(image_data)

            # Force layout update before getting size
            QApplication.processEvents()
            self.output_image_label.updateGeometry()

            # Get the label's current size
            label_size = self.output_image_label.size()

            # Ensure we have valid dimensions
            if label_size.width() <= 0 or label_size.height() <= 0:
                # Use minimum size if label not ready
                label_size = QSize(400, 400)

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

            # Update use current button state when image changes
            self._update_use_current_button_state()

            # Auto-expand Image Settings when an image is displayed (if user hasn't manually collapsed it)
            # Check config to see if user wants it expanded
            image_settings_should_expand = self.config.get('image_settings_expanded', True)
            if image_settings_should_expand and not self.image_settings_container.isVisible():
                self.image_settings_container.setVisible(True)
                self.image_settings_toggle.setText("▼ &Image Settings")
                self.image_settings_toggle.setChecked(True)

            # After layout settles, ensure the image scales to the final size
            # Schedule multiple resize attempts to handle various layout timing
            for delay in [10, 50, 100, 200, 500]:
                try:
                    QTimer.singleShot(delay, self._perform_image_resize)
                except Exception:
                    pass

            # Also trigger immediate resize
            self._perform_image_resize()
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

        # Build filter string for multiple formats
        # Default to current format but allow saving in other formats
        current_format_filter = f"Current format (*{ext})"
        other_formats = "PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp);;BMP (*.bmp);;TIFF (*.tiff *.tif)"
        all_formats = f"{current_format_filter};;{other_formats};;All files (*.*)"

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            str(Path.home() / default_name),
            all_formats
        )
        
        if path:
            try:
                # Check if we need to convert format
                path = Path(path)
                target_ext = path.suffix.lower()

                # If target extension differs from current or user wants specific format
                if target_ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif'] and target_ext != ext:
                    # Convert using PIL
                    from PIL import Image
                    import io

                    # Load current image data
                    img = Image.open(io.BytesIO(self.current_image_data))

                    # Handle JPEG conversion (no alpha channel)
                    if target_ext in ['.jpg', '.jpeg']:
                        # Convert RGBA to RGB
                        if img.mode == 'RGBA':
                            # Create white background
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                            img = background
                        img.save(str(path), 'JPEG', quality=95)
                    elif target_ext == '.webp':
                        img.save(str(path), 'WEBP', quality=90, lossless=False)
                    elif target_ext in ['.tiff', '.tif']:
                        img.save(str(path), 'TIFF')
                    elif target_ext == '.bmp':
                        img.save(str(path), 'BMP')
                    else:
                        img.save(str(path), 'PNG')

                    logger.info(f"Saved image as {target_ext} to: {path}")
                else:
                    # Save as-is
                    path.write_bytes(self.current_image_data)
                    logger.info(f"Saved image to: {path}")

                QMessageBox.information(self, APP_NAME, f"Image saved to:\n{path}")
            except Exception as e:
                logger.error(f"Error saving image: {e}")
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

    def _open_midjourney_external_browser(self, web_url: str, slash_command: str):
        """Open Midjourney in external browser."""
        try:
            import webbrowser
            import subprocess
            import platform

            self._append_to_console("Opening in external browser...", "#66ccff")
            self.status_label.setText("Opening Midjourney in browser")

            # Copy command to clipboard
            try:
                system = platform.system()
                if system == "Windows":
                    subprocess.run(['clip'], input=slash_command, text=True, check=True)
                elif system == "Darwin":
                    subprocess.run(['pbcopy'], input=slash_command, text=True, check=True)
                else:
                    subprocess.run(['xclip', '-selection', 'clipboard'], input=slash_command, text=True, check=True)

                self._append_to_console(f"Command copied: {slash_command}", "#00ff00")
            except:
                self._append_to_console(f"Manual copy: {slash_command}", "#ffff66")

            # Open browser
            webbrowser.open(web_url)
            self._append_to_console("Midjourney opened in browser. Paste the command there.", "#66ccff")

            # Start download watcher session if enabled
            if hasattr(self, 'midjourney_watcher') and self.midjourney_watcher.enabled:
                session_id = self.midjourney_watcher.start_session(
                    self.current_prompt,
                    slash_command,
                    self.cbo_model.currentData()
                )
                self.current_midjourney_session = session_id
                self._append_to_console("Download watcher started for this generation", "#66ccff")

            # Re-enable generate button
            self.btn_generate.setEnabled(True)
            self._cleanup_thread()

        except Exception as e:
            logger.error(f"Failed to open external browser: {e}")
            self._append_to_console(f"Error opening browser: {e}", "#ff6666")
            self.btn_generate.setEnabled(True)
            self._cleanup_thread()

    def _open_midjourney_web_dialog(self, web_url: str, slash_command: str):
        """Open Midjourney web dialog for manual image generation."""
        try:
            # Check if QWebEngineView is available
            try:
                from PySide6.QtWebEngineWidgets import QWebEngineView
                from gui.midjourney_dialog import MidjourneyWebDialog

                self._append_to_console("Opening Midjourney web interface...", "#66ccff")
                self.status_label.setText("Midjourney web interface opened")

                # Create and show dialog with prompt
                dialog = MidjourneyWebDialog(web_url, slash_command, self.current_prompt, self)

                # Connect dialog signals
                dialog.imageGenerated.connect(self._on_midjourney_image_ready)
                dialog.sessionStarted.connect(self._on_midjourney_session_started)
                dialog.sessionEnded.connect(self._on_midjourney_session_ended)

                # Show dialog (non-modal)
                dialog.show()

                # Re-enable generate button
                self.btn_generate.setEnabled(True)
                self._cleanup_thread()

            except ImportError:
                # Fallback: Open in external browser
                self._append_to_console("Web engine not available, opening in browser...", "#ffff66")
                import webbrowser
                import subprocess
                import platform

                # Copy command to clipboard
                try:
                    system = platform.system()
                    if system == "Windows":
                        subprocess.run(['clip'], input=slash_command, text=True, check=True)
                    elif system == "Darwin":
                        subprocess.run(['pbcopy'], input=slash_command, text=True, check=True)
                    else:
                        subprocess.run(['xclip', '-selection', 'clipboard'], input=slash_command, text=True, check=True)

                    self._append_to_console(f"Command copied: {slash_command}", "#00ff00")
                except:
                    self._append_to_console(f"Manual copy: {slash_command}", "#ffff66")

                # Open browser
                webbrowser.open(web_url)
                self._append_to_console("Midjourney opened in browser. Paste the command there.", "#66ccff")

                # Re-enable generate button
                self.btn_generate.setEnabled(True)
                self._cleanup_thread()

        except Exception as e:
            logger.error(f"Error opening Midjourney dialog: {e}")
            # Fallback: attempt to open in external browser so user can proceed
            try:
                self._append_to_console("Dialog failed; opening Midjourney in external browser...", "#ffff66")
                self._open_midjourney_external_browser(web_url, slash_command)
            except Exception as e2:
                self._append_to_console(f"Error: {str(e2)}", "#ff6666")
                self.btn_generate.setEnabled(True)
                self._cleanup_thread()

    def _on_midjourney_image_ready(self, message: str):
        """Handle when user indicates Midjourney image is ready."""
        self._append_to_console(message, "#00ff00")
        self.status_label.setText("Midjourney image generated - save from web interface")
        self.status_bar.showMessage("Please save your image from the Midjourney interface")

    def _init_midjourney_watcher(self):
        """Initialize the Midjourney download watcher if enabled."""
        if self.config.get("midjourney_watch_enabled", False):
            try:
                from gui.midjourney_watcher import MidjourneyWatcher

                self.midjourney_watcher = MidjourneyWatcher(self)
                self.midjourney_watcher.imageDetected.connect(self._on_midjourney_image_detected)

                # Set configuration
                watch_path = self.config.get("midjourney_downloads_path")
                if watch_path:
                    from pathlib import Path
                    self.midjourney_watcher.set_watch_path(Path(watch_path))
                else:
                    self.midjourney_watcher.set_watch_path()  # Use default

                self.midjourney_watcher.set_auto_accept_threshold(
                    self.config.get("midjourney_auto_accept", 85)
                )
                self.midjourney_watcher.set_time_window(
                    self.config.get("midjourney_time_window", 300)
                )
                self.midjourney_watcher.set_enabled(True)

                self._append_to_console("Midjourney download watcher enabled", "#66ccff")
            except Exception as e:
                logger.error(f"Failed to initialize Midjourney watcher: {e}")
                self._append_to_console(f"Failed to start download watcher: {e}", "#ff6666")

    def _on_midjourney_session_started(self, prompt: str, command: str):
        """Handle Midjourney session start."""
        if self.midjourney_watcher:
            self.midjourney_session_id = self.midjourney_watcher.start_session(
                prompt, command, self.current_model
            )
            logger.info(f"Started Midjourney session: {self.midjourney_session_id}")

    def _on_midjourney_session_ended(self):
        """Handle Midjourney session end."""
        if self.midjourney_watcher and self.midjourney_session_id:
            self.midjourney_watcher.end_session(self.midjourney_session_id)
            logger.info(f"Ended Midjourney session: {self.midjourney_session_id}")

    def _on_midjourney_image_detected(self, image_path, confidence_data):
        """Handle detected Midjourney image from downloads."""
        from pathlib import Path
        from gui.midjourney_match_dialog import MidjourneyMatchDialog

        # Show notification if enabled
        if self.config.get("midjourney_notifications", True):
            self.status_bar.showMessage(f"Midjourney image detected: {image_path.name}", 5000)
            self._append_to_console(
                f"Image detected: {image_path.name} ({confidence_data['confidence']:.0f}%)",
                "#66ccff"
            )

        # Check if auto-accept
        if confidence_data.get('auto_accept', False):
            # Auto-accept the match
            self._process_midjourney_image(
                image_path,
                confidence_data.get('prompt', ''),
                confidence_data.get('session_id')
            )
        else:
            # Show confirmation dialog
            all_sessions = []
            if self.midjourney_watcher:
                all_sessions = self.midjourney_watcher.get_active_sessions()

            dialog = MidjourneyMatchDialog(
                image_path, confidence_data, all_sessions, self
            )
            dialog.accepted.connect(
                lambda sid, prompt, path: self._process_midjourney_image(path, prompt, sid)
            )
            dialog.rejected.connect(
                lambda path: self._append_to_console(f"Rejected: {path.name}", "#ffaa00")
            )
            dialog.show()

    def _process_midjourney_image(self, image_path, prompt, session_id):
        """Process an accepted Midjourney image."""
        try:
            from pathlib import Path
            import shutil

            # Read the image
            image_data = image_path.read_bytes()

            # Save to output directory with metadata
            stub = sanitize_stub_from_prompt(prompt)
            saved_paths = auto_save_images([image_data], base_stub=f"mj_{stub}")

            if saved_paths:
                saved_path = saved_paths[0]

                # Create metadata sidecar
                from datetime import datetime
                metadata = {
                    "prompt": prompt,
                    "provider": "midjourney",
                    "model": self.current_model or "midjourney",
                    "timestamp": datetime.now().isoformat(),
                    "original_path": str(image_path),
                    "session_id": session_id
                }
                write_image_sidecar(saved_path, metadata)

                # Add to history
                history_entry = {
                    'path': saved_path,
                    'prompt': prompt,
                    'timestamp': datetime.now().isoformat(),
                    'model': "midjourney",
                    'provider': "midjourney",
                    'cost': 0.0  # Midjourney uses subscription
                }
                self.history.append(history_entry)

                # Update UI
                if hasattr(self, 'history_table'):
                    self._add_to_history_table(history_entry)

                # Load the image
                self._load_image_file(saved_path)

                self._append_to_console(f"✓ Saved Midjourney image: {saved_path.name}", "#00ff00")
                self.status_bar.showMessage(f"Midjourney image saved: {saved_path.name}", 5000)

                # Optionally delete from downloads
                if self.config.get("midjourney_delete_downloads", False):
                    try:
                        image_path.unlink()
                        self._append_to_console(f"Removed from downloads: {image_path.name}", "#888888")
                    except:
                        pass

        except Exception as e:
            logger.error(f"Error processing Midjourney image: {e}")
            self._append_to_console(f"Error: {str(e)}", "#ff6666")

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

            # Save Imagen multi-reference images
            if hasattr(self, 'imagen_reference_widget'):
                project_data['ui_state']['imagen_references'] = self.imagen_reference_widget.to_dict()

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
                    self.image_settings_toggle.setText("▼ &Image Settings")
                    self.image_settings_toggle.setChecked(True)
                else:
                    self.image_settings_container.setVisible(False)
                    self.image_settings_toggle.setText("▶ &Image Settings")
                    self.image_settings_toggle.setChecked(False)

            # Load Imagen multi-reference images
            if 'imagen_references' in ui_state and hasattr(self, 'imagen_reference_widget'):
                self.imagen_reference_widget.from_dict(ui_state['imagen_references'])

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
                except Exception as e:
                    logger.error(f"Error auto-saving video project: {e}")

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
            logger.error(f"Error saving UI state: {e}")
        
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
    
    def _on_history_item_clicked(self, item):
        """Handle single click on history item - restore prompt and switch to appropriate tab."""
        row = self.history_table.row(item)
        if row >= 0:
            # Get the history data from the DateTime column (column 1) where it's stored
            datetime_item = self.history_table.item(row, 1)
            if datetime_item:
                history_item = datetime_item.data(Qt.UserRole)
                if isinstance(history_item, dict):
                    # Check which tab the image came from
                    source_tab = history_item.get('source_tab', 'image')

                    if source_tab == 'video':
                        # Switch to video tab and display image there
                        if hasattr(self, 'tab_video'):
                            self.tabs.setCurrentWidget(self.tab_video)
                            # Display image in video tab's image view
                            path = history_item.get('path')
                            if path and path.exists():
                                from PySide6.QtGui import QPixmap
                                pixmap = QPixmap(str(path))
                                if not pixmap.isNull() and hasattr(self.tab_video, 'workspace_widget'):
                                    scaled = pixmap.scaled(
                                        self.tab_video.workspace_widget.output_image_label.size(),
                                        Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation
                                    )
                                    self.tab_video.workspace_widget.output_image_label.setPixmap(scaled)
                                    self.tab_video.workspace_widget._log_to_console(f"Loaded from history: {path.name}", "INFO")
                    else:
                        # Default to image tab
                        prompt = history_item.get('prompt', '')
                        if prompt:
                            # Switch to Generate tab
                            self.tabs.setCurrentWidget(self.tab_generate)
                            # Set the prompt in the input box
                            self.prompt_edit.setPlainText(prompt)
                            # Show status message
                        self.status_bar.showMessage(f"Loaded prompt from history", 3000)

    def _on_history_selection_changed(self, selected, deselected):
        """Handle history selection change - display the image in appropriate tab."""
        indexes = self.history_table.selectionModel().selectedRows()
        if not indexes:
            return

        # Get the selected history item from the table
        row = indexes[0].row()
        date_item = self.history_table.item(row, 1)  # Column 1 has the full history data
        if date_item:
            history_item = date_item.data(Qt.UserRole)
            if isinstance(history_item, dict):
                # Check which tab the image came from
                source_tab = history_item.get('source_tab', 'image')

                path = history_item.get('path')
                if path and path.exists():
                    try:
                        # Read and display the image
                        image_data = path.read_bytes()
                        self._last_displayed_image_path = path  # Track last displayed image

                        # Display in the appropriate tab
                        if source_tab == 'video' and hasattr(self, 'tab_video'):
                            # Display in video tab - handled by _on_history_item_clicked
                            return
                        # Otherwise display in image tab (default)

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

                        # Update use current button state after loading history
                        self._update_use_current_button_state()

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

        self.logger.info(f"=== TAB CHANGED to index {index} ===")
        self.logger.info(f"Current widget: {current_widget.__class__.__name__ if current_widget else 'None'}")
        self.logger.info(f"Is video tab: {current_widget == self.tab_video}")
        self.logger.info(f"Video tab loaded: {self._video_tab_loaded}")

        # Lazy load video tab on first access
        if current_widget == self.tab_video and not self._video_tab_loaded:
            self.logger.info("Triggering video tab lazy load...")
            self._load_video_tab()

        # If switching to help tab, trigger a minimal scroll to fix rendering
        if current_widget == self.tab_help:
            self._trigger_help_render()

        # If switching to history tab, check for new images not created by us
        if current_widget == self.tab_history:
            # Check if there are new images in the folder that we didn't generate
            self._check_for_external_images()

    def _load_video_tab(self):
        """Lazy load the video tab when first accessed."""
        self.logger.info("=== _LOAD_VIDEO_TAB CALLED ===")
        self.logger.info(f"Thread ID: {__import__('threading').current_thread().ident}")
        self.logger.info(f"Current platform: {__import__('sys').platform}")

        try:
            # Step 1: Import
            self.logger.info("STEP 1: Importing VideoProjectTab...")
            from gui.video.video_project_tab import VideoProjectTab
            self.logger.info("STEP 1: Import successful")

            # Step 2: Prepare providers
            self.logger.info("STEP 2: Preparing providers dictionary...")
            available_providers = [p for p in list_providers() if p != "imagen_customization"]
            self.logger.info(f"STEP 2: Available providers: {available_providers}")
            providers_dict = {
                'available': available_providers,
                'current': self.current_provider,
                'config': self.config
            }
            self.logger.info("STEP 2: Providers dictionary created")

            # Step 3: Get tab index
            self.logger.info("STEP 3: Getting video tab index...")
            video_index = self.tabs.indexOf(self.tab_video)
            self.logger.info(f"STEP 3: Video tab index = {video_index}")

            # Step 4: Create video tab
            self.logger.info("STEP 4: Creating VideoProjectTab instance...")
            self.logger.info(f"STEP 4: Passing config type: {type(self.config)}")
            self.logger.info(f"STEP 4: Passing providers_dict keys: {providers_dict.keys()}")
            real_video_tab = VideoProjectTab(self.config, providers_dict)
            self.logger.info("STEP 4: VideoProjectTab instance created successfully")

            # Step 5: Connect signals
            self.logger.info("STEP 5: Connecting signals...")
            if hasattr(real_video_tab, 'image_provider_changed'):
                real_video_tab.image_provider_changed.connect(self._on_video_image_provider_changed)
                self.logger.info("STEP 5: Connected image_provider_changed signal")
            if hasattr(real_video_tab, 'llm_provider_changed'):
                real_video_tab.llm_provider_changed.connect(self._on_video_llm_provider_changed)
                self.logger.info("STEP 5: Connected llm_provider_changed signal")
            if hasattr(real_video_tab, 'add_to_history_signal'):
                real_video_tab.add_to_history_signal.connect(self.add_to_history)
                self.logger.info("STEP 5: Connected add_to_history_signal")
            self.logger.info("STEP 5: Signal connections complete")

            # Step 6: Replace placeholder tab
            self.logger.info("STEP 6: Replacing placeholder tab...")
            self.logger.info(f"STEP 6a: Removing placeholder tab at index {video_index}")
            self.tabs.removeTab(video_index)
            self.logger.info(f"STEP 6b: Inserting real video tab at index {video_index}")
            self.tabs.insertTab(video_index, real_video_tab, "🎬 Video")
            self.logger.info(f"STEP 6c: Setting current index to {video_index}")
            self.tabs.setCurrentIndex(video_index)
            self.logger.info("STEP 6: Tab replacement complete")

            # Step 7: Update references
            self.logger.info("STEP 7: Updating internal references...")
            self.tab_video = real_video_tab
            self._video_tab_loaded = True
            self.logger.info("STEP 7: References updated, _video_tab_loaded = True")

            # Step 8: Refresh Ollama models (in case they were detected during startup)
            self.logger.info("STEP 8: Refreshing Ollama models...")
            try:
                from core.llm_models import update_ollama_models, get_provider_models
                if update_ollama_models():
                    models = get_provider_models('ollama')
                    self.logger.info(f"Refreshed Ollama models: {models}")
            except Exception as e:
                self.logger.debug(f"Ollama refresh skipped: {e}")

            # Step 9: Sync LLM provider
            self.logger.info("STEP 9: Syncing LLM provider settings...")
            if hasattr(self, 'llm_provider_combo') and self.llm_provider_combo.currentText() != "None":
                provider_name = self.llm_provider_combo.currentText()
                model_name = self.llm_model_combo.currentText() if self.llm_model_combo.isEnabled() else None
                self.logger.info(f"STEP 9: Syncing provider={provider_name}, model={model_name}")
                if hasattr(self.tab_video, 'set_llm_provider'):
                    self.tab_video.set_llm_provider(provider_name, model_name)
                    self.logger.info("STEP 9: LLM provider synced")
            else:
                self.logger.info("STEP 9: No LLM provider to sync")

            self.logger.info("=== _LOAD_VIDEO_TAB COMPLETE ===")

        except Exception as e:
            import traceback
            error_msg = f"Failed to load video tab: {str(e)}\n\n{traceback.format_exc()}"
            self.logger.error(f"VIDEO TAB LOAD ERROR:\n{error_msg}")
            QMessageBox.warning(self, "Video Tab Error", error_msg)
    
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
    
    def _toggle_image_settings(self, checked=None):
        """Toggle the image settings panel visibility."""
        if checked is None:
            is_visible = self.image_settings_container.isVisible()
        else:
            is_visible = checked
        self.image_settings_container.setVisible(is_visible)
        self.image_settings_toggle.setText("▼ &Image Settings" if is_visible else "▶ &Image Settings")

        # Save the expansion state when user manually toggles
        self.config.set('image_settings_expanded', is_visible)
        self.config.save()

        # Trigger image resize after layout change
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._perform_image_resize)

    def _toggle_ref_image_settings(self, checked):
        """Toggle the reference image settings panel visibility."""
        self.ref_image_container.setVisible(checked)
        self.ref_image_toggle.setText("▼ Reference Images (Google Only - Imagen 3)" if checked else "▶ Reference Images (Google Only - Imagen 3)")

        # Save the expansion state
        self.config.set('reference_images_expanded', checked)
        self.config.save()

        # Trigger image resize after layout change
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._perform_image_resize)

    def _select_reference_image(self):
        """Open dialog to select a reference image."""
        from PySide6.QtGui import QImage
        import base64

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            str(images_output_dir()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tiff *.tif *.ico *.svg);;All files (*.*)"
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
                # Don't change style - preserve whatever is currently selected
                self._update_ref_instruction_preview()

                # Update button text to show filename
                filename = self.reference_image_path.name
                if len(filename) > 30:
                    filename = filename[:27] + "..."
                self.btn_select_ref_image.setText(f"Reference: {filename}")

                # Save to project/settings
                self._save_reference_image_to_config()

                # Update use current button state
                self._update_use_current_button_state()

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

        # Update use current button state
        self._update_use_current_button_state()

    def _use_current_as_reference(self):
        """Use the currently displayed image as reference image."""
        if not hasattr(self, 'current_image_data') or not self.current_image_data:
            return

        try:
            from PySide6.QtGui import QImage

            # Create QImage from current image data
            image = QImage()
            if not image.loadFromData(self.current_image_data):
                QMessageBox.critical(self, "Error", "Failed to process current image")
                return

            # Store the image data
            self.reference_image_path = Path("Current Display Image")  # Virtual path
            self.reference_image_data = self.current_image_data

            # Update preview
            pixmap = QPixmap.fromImage(image)
            preview_pixmap = pixmap.scaled(
                200, 150,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.ref_image_preview.setPixmap(preview_pixmap)
            self.ref_image_preview.setVisible(True)

            # Enable controls
            self.ref_image_enabled.setEnabled(True)
            self.ref_image_enabled.setChecked(True)
            self.btn_clear_ref_image.setEnabled(True)
            self.ref_options_widget.setVisible(True)

            # Update instruction preview
            self._update_ref_instruction_preview()

            # Update button text
            self.btn_select_ref_image.setText("Change Reference...")

            # Save to config (with special marker for current image)
            self._save_reference_image_to_config()

            # Update button state
            self._update_use_current_button_state()

            self.status_bar.showMessage("Using current image as reference")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set current image as reference: {str(e)}")

    # Note: _handle_midjourney_generate and _update_midjourney_command methods removed
    # as they are now handled by the Midjourney provider

    def _update_use_current_button_state(self):
        """Update the state of the 'Use Current Image' button."""
        if not hasattr(self, 'btn_use_current_as_ref'):
            return

        # Button should be enabled if:
        # 1. Provider is Google (reference images only work with Google) AND
        # 2. There is a current image displayed AND
        # 3. It's not already the reference image (or reference is cleared)
        is_google = self.current_provider.lower() == "google"
        has_current_image = bool(hasattr(self, 'current_image_data') and self.current_image_data)

        # Check if current image is already the reference
        is_same_as_reference = False
        if has_current_image and hasattr(self, 'reference_image_data') and self.reference_image_data:
            is_same_as_reference = (self.current_image_data == self.reference_image_data)

        # Enable button only if Google provider, we have an image, and it's different from reference
        self.btn_use_current_as_ref.setEnabled(bool(is_google and has_current_image and not is_same_as_reference))

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

    def _on_ref_type_changed(self, ref_type):
        """Handle reference image type change."""
        self._update_ref_instruction_preview()
        if self.reference_image_path:
            self._save_reference_image_to_config()

    def _on_ref_usage_changed(self, usage_text):
        """Handle reference image usage text change."""
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
                    if self.current_provider.lower() == 'google':
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
            'position': self.ref_position_combo.currentText() if hasattr(self, 'ref_position_combo') else "Auto",
            'type': self.ref_type_combo.currentText() if hasattr(self, 'ref_type_combo') else "CHARACTER",
            'usage': self.ref_usage_edit.text() if hasattr(self, 'ref_usage_edit') else ""
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
        # NOTE: This is legacy single-reference image loading
        # The new multi-reference system uses _load_imagen_references_from_config()

        # Check if the old UI elements exist (they may have been removed)
        if not hasattr(self, 'ref_image_preview'):
            return

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
                        if 'type' in ref_image_data:
                            self.ref_type_combo.setCurrentText(ref_image_data['type'])
                        if 'usage' in ref_image_data:
                            self.ref_usage_edit.setText(ref_image_data['usage'])
                        self._update_ref_instruction_preview()

                        # Update button state after loading reference
                        self._update_use_current_button_state()

                except Exception as e:
                    logger.warning(f"Failed to load reference image from config: {e}")

    def _save_imagen_references_to_config(self):
        """Save Imagen multi-reference images to config."""
        if not hasattr(self, 'imagen_reference_widget'):
            return

        try:
            # Get reference data from widget
            ref_data = self.imagen_reference_widget.to_dict()

            # Save to config
            self.config.set('imagen_references', ref_data)
            self.config.save()

            logger.info(f"Saved {len(ref_data)} Imagen references to config")

        except Exception as e:
            logger.error(f"Failed to save Imagen references to config: {e}")

    def _load_imagen_references_from_config(self):
        """Load Imagen multi-reference images from config."""
        if not hasattr(self, 'imagen_reference_widget'):
            return

        try:
            # Get reference data from config
            ref_data = self.config.get('imagen_references', [])

            if ref_data:
                # Load into widget
                self.imagen_reference_widget.from_dict(ref_data)
                logger.info(f"Loaded {len(ref_data)} Imagen references from config")

        except Exception as e:
            logger.error(f"Failed to load Imagen references from config: {e}")

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
            logger.error(f"Error saving UI state: {e}")
    
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
                        # Use centralized model lists
                        models = self.get_llm_models_for_provider(provider)
                        if models:
                            self.llm_model_combo.addItems(models)
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
                    self.image_settings_toggle.setText("▼ &Image Settings")
                    self.image_settings_toggle.setChecked(True)
            
            # Restore aspect ratio
            if 'aspect_ratio' in ui_state and hasattr(self, 'aspect_selector') and self.aspect_selector:
                try:
                    self.aspect_selector.set_ratio(ui_state['aspect_ratio'])
                except Exception as e:
                    logger.debug(f"Error restoring aspect ratio: {e}")

            # Restore resolution
            if 'resolution' in ui_state and hasattr(self, 'resolution_selector') and self.resolution_selector:
                try:
                    # Use skip_mode_change=True to avoid unchecking aspect ratio during restoration
                    self.resolution_selector.set_resolution(ui_state['resolution'], skip_mode_change=True)
                except Exception as e:
                    logger.debug(f"Error restoring resolution: {e}")
            elif 'resolution_combo_index' in ui_state and hasattr(self, 'resolution_combo'):
                if ui_state['resolution_combo_index'] < self.resolution_combo.count():
                    self.resolution_combo.setCurrentIndex(ui_state['resolution_combo_index'])
            
            # Restore quality settings
            if 'quality_settings' in ui_state and hasattr(self, 'quality_selector') and self.quality_selector:
                try:
                    self.quality_selector.set_settings(ui_state['quality_settings'])
                except Exception as e:
                    logger.debug(f"Error restoring quality settings: {e}")
            
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
                        self.advanced_panel.set_settings(ui_state['advanced_settings'])
                    except Exception as e:
                        logger.debug(f"Error restoring advanced settings: {e}")
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

            # Always restore the last tab the user was on
            if 'current_tab' in ui_state:
                if ui_state['current_tab'] < self.tabs.count():
                    self.logger.info(f"Restoring last active tab: {ui_state['current_tab']}")
                    self.tabs.setCurrentIndex(ui_state['current_tab'])

            # Only auto-load video project if user was on the Video tab when they closed the app
            from PySide6.QtCore import QSettings
            video_settings = QSettings("ImageAI", "VideoProjects")
            last_video_project = video_settings.value("last_project")
            video_tab_index = self.tabs.indexOf(self.tab_video)
            current_tab_is_video = self.tabs.currentIndex() == video_tab_index

            self.logger.info("=== STARTUP VIDEO PROJECT CHECK ===")
            self.logger.info(f"Last video project from QSettings: {last_video_project}")
            self.logger.info(f"Current tab is Video tab: {current_tab_is_video}")

            if last_video_project and current_tab_is_video:
                project_path = Path(last_video_project)
                self.logger.info(f"Project path exists: {project_path.exists()}")

                if project_path.exists():
                    # Video tab is already active, project will auto-load via tab change handler
                    self.logger.info(f"Video tab active, project will auto-load: {last_video_project}")
                else:
                    self.logger.info("Video project path does not exist, skipping")
            else:
                if not last_video_project:
                    self.logger.info("No last video project found")
                if not current_tab_is_video:
                    self.logger.info("User was not on Video tab, skipping video project auto-load")

            # Restore last IMAGE project if saved
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
            logger.error(f"Error restoring UI state: {e}")

    def _add_to_history_table(self, history_entry):
        """Add a single new entry to the history table without refreshing everything."""
        if not hasattr(self, 'history_table'):
            return

        from PySide6.QtWidgets import QTableWidgetItem

        # Block selection signals to prevent triggering image display while inserting
        self.history_table.selectionModel().blockSignals(True)

        try:
            # Add a new row at the top (newest first)
            row_count = self.history_table.rowCount()
            self.history_table.insertRow(0)  # Insert at top

            # Thumbnail column
            thumbnail_item = QTableWidgetItem()
            file_path = history_entry.get('path', '')
            if file_path:
                path_str = str(file_path)
                thumbnail_item.setData(Qt.UserRole, path_str)
                # Preload thumbnail
                self.thumbnail_cache.get(path_str)
            self.history_table.setItem(0, 0, thumbnail_item)
            self.history_table.setRowHeight(0, 80)

            # Parse timestamp
            timestamp = history_entry.get('timestamp', '')
            datetime_str = ''
            sortable_datetime = None
            if timestamp:
                try:
                    if isinstance(timestamp, (int, float)):
                        dt = datetime.fromtimestamp(timestamp)
                        datetime_str = dt.strftime('%Y-%m-%d %H:%M')
                        sortable_datetime = dt.isoformat()
                    elif 'T' in str(timestamp):
                        parts = str(timestamp).split('T')
                        date_str = parts[0]
                        time_str = parts[1].split('.')[0] if len(parts) > 1 else ''
                        datetime_str = f"{date_str} {time_str}"
                except:
                    datetime_str = str(timestamp)

            # Date & Time column
            datetime_item = QTableWidgetItem(datetime_str)
            if sortable_datetime:
                datetime_item.setData(Qt.UserRole + 1, sortable_datetime)
            self.history_table.setItem(0, 1, datetime_item)

            # Provider column
            provider = history_entry.get('provider', '')
            provider_item = QTableWidgetItem(provider.title() if provider else 'Unknown')
            self.history_table.setItem(0, 2, provider_item)

            # Model column
            model = history_entry.get('model', '')
            model_display = model.split('/')[-1] if '/' in model else model
            model_item = QTableWidgetItem(model_display)
            model_item.setToolTip(model)
            self.history_table.setItem(0, 3, model_item)

            # Prompt column
            prompt = history_entry.get('prompt', 'No prompt')
            prompt_item = QTableWidgetItem(prompt)
            prompt_item.setToolTip(f"Full prompt:\n{prompt}")
            self.history_table.setItem(0, 4, prompt_item)

            # Resolution column
            width = history_entry.get('width', '')
            height = history_entry.get('height', '')
            resolution = f"{width}x{height}" if width and height else ''
            resolution_item = QTableWidgetItem(resolution)
            self.history_table.setItem(0, 5, resolution_item)

            # Cost column
            cost = history_entry.get('cost', 0.0)
            cost_str = f"${cost:.2f}" if cost > 0 else '-'
            cost_item = QTableWidgetItem(cost_str)
            self.history_table.setItem(0, 6, cost_item)

            # Store the history item data for retrieval
            datetime_item.setData(Qt.UserRole, history_entry)

            # Clear any existing selection to prevent old images from overriding the new one
            self.history_table.clearSelection()

        finally:
            # Always unblock signals, even if an error occurred
            self.history_table.selectionModel().blockSignals(False)

    def add_to_history(self, history_entry):
        """Public method to add an entry to history from other tabs."""
        self.history.append(history_entry)
        self._add_to_history_table(history_entry)

    def _check_for_external_images(self):
        """Check if there are new images in the folder that we didn't generate."""
        # Get current paths in our history
        current_paths = {str(item.get('path', '')) for item in self.history if item.get('path')}

        # Scan disk for all images
        show_all = hasattr(self, 'chk_show_all_images') and self.chk_show_all_images.isChecked()
        disk_paths = scan_disk_history(project_only=not show_all)

        # Find new images
        new_images = []
        for path in disk_paths[:100]:  # Limit scan
            if str(path) not in current_paths:
                new_images.append(path)

        # If we found new images, add them
        if new_images:
            for path in new_images:
                # Try to read metadata
                sidecar = read_image_sidecar(path)
                if sidecar:
                    history_entry = {
                        'path': path,
                        'prompt': sidecar.get('prompt', ''),
                        'timestamp': sidecar.get('timestamp', path.stat().st_mtime),
                        'model': sidecar.get('model', ''),
                        'provider': sidecar.get('provider', ''),
                        'width': sidecar.get('width', ''),
                        'height': sidecar.get('height', ''),
                        'cost': sidecar.get('cost', 0.0)
                    }
                else:
                    history_entry = {
                        'path': path,
                        'prompt': path.stem.replace('_', ' '),
                        'timestamp': path.stat().st_mtime,
                        'model': '',
                        'provider': '',
                        'cost': 0.0
                    }

                self.history.append(history_entry)
                self._add_to_history_table(history_entry)

    def _refresh_history_table(self):
        """Refresh the history table with current history data."""
        if not hasattr(self, 'history_table'):
            return

        # Import QTableWidgetItem if needed
        from PySide6.QtWidgets import QTableWidgetItem

        # Clear and repopulate the table
        self.history_table.setRowCount(len(self.history))

        # Preload thumbnails for visible rows to improve performance
        # Get visible range
        first_visible = 0
        last_visible = min(20, len(self.history))  # Preload first 20

        for row, item in enumerate(self.history):
            if isinstance(item, dict):
                # Thumbnail column - handled by custom delegate
                # Store the path in the item so delegate can access it
                thumbnail_item = QTableWidgetItem()
                file_path = item.get('path', item.get('file_path', ''))
                if file_path:
                    path_str = str(file_path)
                    thumbnail_item.setData(Qt.UserRole, path_str)

                    # Preload thumbnail for visible rows
                    if first_visible <= row <= last_visible:
                        self.thumbnail_cache.get(path_str)  # Load into cache

                self.history_table.setItem(row, 0, thumbnail_item)
                # Set row height to accommodate thumbnail
                self.history_table.setRowHeight(row, 80)

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
                self.history_table.setItem(row, 1, datetime_item)
                
                # Provider column (now column 1)
                provider = item.get('provider', '')
                provider_item = QTableWidgetItem(provider.title() if provider else 'Unknown')
                self.history_table.setItem(row, 2, provider_item)
                
                # Model column (now column 2)
                model = item.get('model', '')
                model_display = model.split('/')[-1] if '/' in model else model
                model_item = QTableWidgetItem(model_display)
                model_item.setToolTip(model)
                self.history_table.setItem(row, 3, model_item)
                
                # Prompt column (now column 3)
                prompt = item.get('prompt', 'No prompt')
                prompt_item = QTableWidgetItem(prompt)  # Show full prompt, not truncated
                prompt_item.setToolTip(f"Full prompt:\n{prompt}")
                self.history_table.setItem(row, 4, prompt_item)
                
                # Resolution column (now column 4)
                width = item.get('width', '')
                height = item.get('height', '')
                resolution = f"{width}x{height}" if width and height else ''
                resolution_item = QTableWidgetItem(resolution)
                self.history_table.setItem(row, 5, resolution_item)
                
                # Cost column (now column 5)
                cost = item.get('cost', 0.0)
                cost_str = f"${cost:.2f}" if cost > 0 else '-'
                cost_item = QTableWidgetItem(cost_str)
                self.history_table.setItem(row, 6, cost_item)
                
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

    # Midjourney-specific methods
    # Midjourney methods removed - all functionality is now in the dedicated Midjourney tab
