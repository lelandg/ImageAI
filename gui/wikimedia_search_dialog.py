"""Dialog for searching and downloading images from Wikimedia Commons."""

import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QMessageBox, QProgressBar,
    QSplitter, QTextEdit, QAbstractItemView, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap


class NumericTableWidgetItem(QTableWidgetItem):
    """Table widget item that sorts numerically."""

    def __init__(self, text: str, sort_value: int):
        super().__init__(text)
        self._sort_value = sort_value

    def __lt__(self, other):
        """Compare items for sorting."""
        if isinstance(other, NumericTableWidgetItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)

from core.wikimedia_client import WikimediaClient, WikimediaImage
from core.config import ConfigManager

logger = logging.getLogger(__name__)


class ImageDownloader(QThread):
    """Background thread for downloading images."""

    progress = Signal(int, int)  # current, total
    finished = Signal(list)  # list of downloaded paths
    error = Signal(str)

    def __init__(self, client: WikimediaClient, images: List[WikimediaImage], output_dir: Path):
        super().__init__()
        self.client = client
        self.images = images
        self.output_dir = output_dir
        self._is_cancelled = False

    def run(self):
        """Download images in background."""
        downloaded_paths = []

        for i, image in enumerate(self.images):
            if self._is_cancelled:
                break

            # Create sanitized filename from title
            filename = image.title.replace("File:", "").replace("/", "_")
            output_path = self.output_dir / filename

            # Add timestamp if file exists
            if output_path.exists():
                stem = output_path.stem
                suffix = output_path.suffix
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = self.output_dir / f"{stem}_{timestamp}{suffix}"

            if self.client.download_image(image, output_path):
                downloaded_paths.append(output_path)

            self.progress.emit(i + 1, len(self.images))

        if not self._is_cancelled:
            self.finished.emit(downloaded_paths)

    def cancel(self):
        """Cancel the download."""
        self._is_cancelled = True


class SearchWorker(QThread):
    """Background thread for searching images."""

    finished = Signal(list)  # list of WikimediaImage
    error = Signal(str)

    def __init__(self, client: WikimediaClient, query: str, limit: int = 50):
        super().__init__()
        self.client = client
        self.query = query
        self.limit = limit

    def run(self):
        """Search for images in background."""
        try:
            images = self.client.search_images(self.query, self.limit)
            self.finished.emit(images)
        except Exception as e:
            self.error.emit(str(e))


class ThumbnailLoader(QThread):
    """Background thread for loading thumbnail images."""

    finished = Signal(bytes)  # Emit raw bytes instead of QPixmap
    error = Signal(str)

    def __init__(self, thumb_url: str):
        super().__init__()
        self.thumb_url = thumb_url
        self._is_cancelled = False

    def run(self):
        """Download thumbnail image data."""
        try:
            import requests

            logger.info(f"Downloading thumbnail from: {self.thumb_url}")

            # Use headers to identify as a browser-like client
            headers = {
                'User-Agent': 'ImageAI/1.0 (https://github.com/yourusername/ImageAI)'
            }

            response = requests.get(self.thumb_url, timeout=10, headers=headers)
            response.raise_for_status()

            logger.info(f"Thumbnail downloaded successfully, size: {len(response.content)} bytes")

            if self._is_cancelled:
                return

            # Emit raw bytes - QPixmap will be created in main thread
            if not self._is_cancelled and response.content:
                self.finished.emit(response.content)
            else:
                logger.error("No image data received from thumbnail URL")
                self.error.emit("No image data received")

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error loading thumbnail from {self.thumb_url}: {e}")
            if not self._is_cancelled:
                self.error.emit(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error loading thumbnail: {e}", exc_info=True)
            if not self._is_cancelled:
                self.error.emit(str(e))

    def cancel(self):
        """Cancel the thumbnail loading."""
        self._is_cancelled = True


class WikimediaSearchDialog(QDialog):
    """Dialog for searching and downloading images from Wikimedia Commons."""

    images_downloaded = Signal(list)  # Emits list of downloaded image paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = WikimediaClient()
        self.search_results: List[WikimediaImage] = []
        self.search_worker: Optional[SearchWorker] = None
        self.download_worker: Optional[ImageDownloader] = None
        self.thumbnail_loader: Optional[ThumbnailLoader] = None

        # Get download directory from config
        self.config = ConfigManager()
        self.download_dir = self.config.get_images_dir() / "wikimedia"
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.setWindowTitle("Wikimedia Commons Image Search")
        self.setMinimumSize(800, 600)
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search terms (e.g., 'mountain landscape')")
        self.search_input.returnPressed.connect(self._search)
        search_layout.addWidget(self.search_input)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._search)
        search_layout.addWidget(self.search_btn)

        layout.addLayout(search_layout)

        # Splitter for results and details
        splitter = QSplitter(Qt.Horizontal)

        # Results table
        results_widget = QVBoxLayout()
        results_widget.addWidget(QLabel("Search Results:"))

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Title", "Resolution", "Upload Date"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.results_table.horizontalHeader().setStretchLastSection(False)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.results_table.itemSelectionChanged.connect(self._on_selection_changed)
        results_widget.addWidget(self.results_table)

        results_container = QWidget()  # Container for layout
        results_container.setLayout(results_widget)
        splitter.addWidget(results_container)

        # Details panel
        details_layout = QVBoxLayout()
        details_layout.addWidget(QLabel("Image Details:"))

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(200, 200)
        self.preview_label.setStyleSheet("border: 1px solid #ccc;")
        details_layout.addWidget(self.preview_label)

        details_container = QWidget()  # Container for layout
        details_container.setLayout(details_layout)
        splitter.addWidget(details_container)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=10)  # Give splitter most of the space

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar, stretch=0)

        # Status label - minimal size
        self.status_label = QLabel("")
        self.status_label.setMaximumHeight(30)  # Limit height to minimal
        layout.addWidget(self.status_label, stretch=0)

        # Buttons
        button_layout = QHBoxLayout()

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download_selected)
        button_layout.addWidget(self.download_btn)

        self.add_reference_btn = QPushButton("Download && Add to Reference Images")
        self.add_reference_btn.setEnabled(False)
        self.add_reference_btn.clicked.connect(self._download_and_add_references)
        button_layout.addWidget(self.add_reference_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _search(self):
        """Perform a search."""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Search", "Please enter a search query.")
            return

        self.status_label.setText(f"Searching for '{query}'...")
        self.search_btn.setEnabled(False)
        self.results_table.setSortingEnabled(False)  # Disable during population
        self.results_table.setRowCount(0)
        self.details_text.clear()
        self.preview_label.clear()
        self.download_btn.setEnabled(False)
        self.add_reference_btn.setEnabled(False)

        # Start search in background
        self.search_worker = SearchWorker(self.client, query)
        self.search_worker.finished.connect(self._on_search_finished)
        self.search_worker.error.connect(self._on_search_error)
        self.search_worker.start()

    def _on_search_finished(self, images: List[WikimediaImage]):
        """Handle search completion."""
        self.search_results = images
        self.search_btn.setEnabled(True)

        if not images:
            self.status_label.setText("No results found.")
            return

        # Populate results table
        self.results_table.setRowCount(len(images))
        for row, image in enumerate(images):
            # Extract filename from title
            display_name = image.title.replace("File:", "")

            # Title column
            title_item = QTableWidgetItem(display_name)
            title_item.setData(Qt.UserRole, image)
            self.results_table.setItem(row, 0, title_item)

            # Resolution column (with numeric sorting)
            resolution = f"{image.width} × {image.height}" if image.width and image.height else "Unknown"
            # Sort by total pixel count (width * height)
            pixel_count = image.width * image.height if image.width and image.height else 0
            resolution_item = NumericTableWidgetItem(resolution, pixel_count)
            self.results_table.setItem(row, 1, resolution_item)

            # Date column
            date_item = QTableWidgetItem(image.upload_date)
            self.results_table.setItem(row, 2, date_item)

        # Enable sorting after populating the table
        self.results_table.setSortingEnabled(True)
        self.status_label.setText(f"Found {len(images)} images.")

    def _on_search_error(self, error: str):
        """Handle search error."""
        self.search_btn.setEnabled(True)
        self.status_label.setText(f"Search error: {error}")
        QMessageBox.critical(self, "Search Error", f"Failed to search:\n{error}")

    def _on_selection_changed(self):
        """Handle selection change in results table."""
        selected_rows = self.results_table.selectionModel().selectedRows()

        if not selected_rows:
            self.details_text.clear()
            self.preview_label.clear()
            self.download_btn.setEnabled(False)
            self.add_reference_btn.setEnabled(False)
            return

        self.download_btn.setEnabled(True)
        self.add_reference_btn.setEnabled(True)

        # Show details of first selected row
        if selected_rows:
            row = selected_rows[0].row()
            title_item = self.results_table.item(row, 0)
            image = title_item.data(Qt.UserRole)
            self._show_image_details(image)

    def _show_image_details(self, image: WikimediaImage):
        """Show details of an image."""
        details = f"<b>Title:</b> {image.title}<br>"
        details += f"<b>Size:</b> {image.width} x {image.height}<br>"

        if image.upload_date:
            details += f"<b>Upload Date:</b> {image.upload_date}<br>"

        details += f"<b>URL:</b> <a href='{image.page_url}'>{image.page_url}</a><br><br>"

        if image.description:
            details += f"<b>Description:</b><br>{image.description}"

        self.details_text.setHtml(details)

        # Cancel any previous thumbnail loading
        if self.thumbnail_loader and self.thumbnail_loader.isRunning():
            self.thumbnail_loader.cancel()
            self.thumbnail_loader.quit()
            self.thumbnail_loader.wait()

        # Load thumbnail preview asynchronously
        self.preview_label.setText("Loading preview...")
        logger.info(f"Starting thumbnail load for: {image.title}, URL: {image.thumb_url}")
        self.thumbnail_loader = ThumbnailLoader(image.thumb_url)
        self.thumbnail_loader.finished.connect(self._on_thumbnail_loaded)
        self.thumbnail_loader.error.connect(self._on_thumbnail_error)
        self.thumbnail_loader.start()

    def _on_thumbnail_loaded(self, image_data: bytes):
        """Handle thumbnail loading completion."""
        logger.info(f"Creating QPixmap from {len(image_data)} bytes of image data")

        # Create QPixmap from bytes in main thread (Qt requirement)
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data):
            logger.error(f"Failed to load {len(image_data)} bytes into QPixmap")
            self.preview_label.setText("Failed to load image")
            return

        logger.info(f"QPixmap created successfully: {pixmap.width()}x{pixmap.height()}")

        # Scale pixmap to fit preview label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled_pixmap)

    def _on_thumbnail_error(self, error: str):
        """Handle thumbnail loading error."""
        logger.error(f"Thumbnail loading error: {error}")
        self.preview_label.setText(f"Failed to load preview:\n{error}")

    def _download_selected(self):
        """Download selected images."""
        selected_rows = self.results_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        selected_images = []
        for row_index in selected_rows:
            row = row_index.row()
            title_item = self.results_table.item(row, 0)
            selected_images.append(title_item.data(Qt.UserRole))

        self._start_download(selected_images, add_to_references=False)

    def _download_and_add_references(self):
        """Download selected images and add them to reference images."""
        selected_rows = self.results_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        selected_images = []
        for row_index in selected_rows:
            row = row_index.row()
            title_item = self.results_table.item(row, 0)
            selected_images.append(title_item.data(Qt.UserRole))

        self._start_download(selected_images, add_to_references=True)

    def _start_download(self, images: List[WikimediaImage], add_to_references: bool):
        """Start downloading images."""
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(images))
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Downloading {len(images)} image(s)...")

        self.search_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.add_reference_btn.setEnabled(False)

        self.download_worker = ImageDownloader(self.client, images, self.download_dir)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(
            lambda paths: self._on_download_finished(paths, add_to_references)
        )
        self.download_worker.start()

    def _on_download_progress(self, current: int, total: int):
        """Update download progress."""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Downloading {current}/{total}...")

    def _on_download_finished(self, downloaded_paths: List[Path], add_to_references: bool):
        """Handle download completion."""
        self.progress_bar.setVisible(False)
        self.search_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.add_reference_btn.setEnabled(True)

        if not downloaded_paths:
            self.status_label.setText("No images downloaded.")
            QMessageBox.warning(self, "Download", "No images were downloaded.")
            return

        self.status_label.setText(f"Downloaded {len(downloaded_paths)} image(s) to {self.download_dir}")

        # Show success message
        msg = f"Successfully downloaded {len(downloaded_paths)} image(s) to:\n{self.download_dir}"
        QMessageBox.information(self, "Download Complete", msg)

        # Emit signal with downloaded paths
        if add_to_references:
            self.images_downloaded.emit([str(p) for p in downloaded_paths])

    def closeEvent(self, event):
        """Clean up when dialog is closed."""
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.quit()
            self.search_worker.wait()

        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.download_worker.quit()
            self.download_worker.wait()

        if self.thumbnail_loader and self.thumbnail_loader.isRunning():
            self.thumbnail_loader.cancel()
            self.thumbnail_loader.quit()
            self.thumbnail_loader.wait()

        super().closeEvent(event)
