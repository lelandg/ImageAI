"""Multi-file attachment widget for LLM dialogs.

Supports attaching multiple files including:
- Images (PNG, JPG, JPEG, GIF, BMP, WebP, etc.)
- Text files (TXT, MD, JSON, XML, YAML, etc.)
- Code files (PY, JS, TS, HTML, CSS, etc.)
- Documents (PDF - text extraction)
"""

import base64
import logging
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from io import BytesIO

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMenu,
    QAbstractItemView, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize, QMimeData
from PySide6.QtGui import QPixmap, QIcon, QDragEnterEvent, QDropEvent, QColor

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


# File type categories and their extensions
FILE_CATEGORIES = {
    'image': {
        'extensions': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.ico', '.svg'],
        'icon': '🖼️',
        'description': 'Image files'
    },
    'text': {
        'extensions': ['.txt', '.md', '.markdown', '.rst', '.log'],
        'icon': '📄',
        'description': 'Text files'
    },
    'code': {
        'extensions': ['.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
                       '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg',
                       '.sh', '.bash', '.bat', '.ps1', '.c', '.cpp', '.h', '.hpp',
                       '.java', '.kt', '.go', '.rs', '.rb', '.php', '.sql', '.r'],
        'icon': '💻',
        'description': 'Code files'
    },
    'document': {
        'extensions': ['.pdf'],
        'icon': '📑',
        'description': 'PDF documents'
    },
    'data': {
        'extensions': ['.csv', '.tsv'],
        'icon': '📊',
        'description': 'Data files'
    }
}

# Build flat lookup for extensions
EXTENSION_TO_CATEGORY = {}
for category, info in FILE_CATEGORIES.items():
    for ext in info['extensions']:
        EXTENSION_TO_CATEGORY[ext.lower()] = category


def get_file_category(file_path: str) -> str:
    """Get the category of a file based on its extension."""
    ext = Path(file_path).suffix.lower()
    return EXTENSION_TO_CATEGORY.get(ext, 'unknown')


def get_file_icon(file_path: str) -> str:
    """Get the emoji icon for a file type."""
    category = get_file_category(file_path)
    if category in FILE_CATEGORIES:
        return FILE_CATEGORIES[category]['icon']
    return '📎'  # Default attachment icon


def get_supported_extensions() -> List[str]:
    """Get all supported file extensions."""
    extensions = []
    for category, info in FILE_CATEGORIES.items():
        extensions.extend(info['extensions'])
    return extensions


def get_file_filter_string() -> str:
    """Get file filter string for QFileDialog."""
    # Create individual filters for each category
    filters = []

    # All supported files
    all_exts = []
    for category, info in FILE_CATEGORIES.items():
        all_exts.extend([f"*{ext}" for ext in info['extensions']])
    filters.append(f"All Supported Files ({' '.join(all_exts)})")

    # Individual category filters
    for category, info in FILE_CATEGORIES.items():
        exts = ' '.join([f"*{ext}" for ext in info['extensions']])
        filters.append(f"{info['description']} ({exts})")

    # All files
    filters.append("All Files (*.*)")

    return ';;'.join(filters)


def read_file_content(file_path: str) -> Tuple[Optional[bytes], Optional[str], str]:
    """
    Read file content based on its type.

    Returns:
        Tuple of (raw_bytes, text_content, mime_type)
        - For images: (bytes, None, mime_type)
        - For text/code: (None, text_content, mime_type)
        - For PDF: (bytes, extracted_text, mime_type)
    """
    path = Path(file_path)
    category = get_file_category(file_path)

    # Get MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        ext = path.suffix.lower()
        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf',
            '.md': 'text/markdown',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.yaml': 'application/x-yaml',
            '.yml': 'application/x-yaml',
        }
        mime_type = mime_map.get(ext, 'application/octet-stream')

    try:
        if category == 'image':
            with open(path, 'rb') as f:
                return f.read(), None, mime_type

        elif category in ['text', 'code', 'data']:
            # Try multiple encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    with open(path, 'r', encoding=encoding) as f:
                        return None, f.read(), f'text/plain; charset={encoding}'
                except UnicodeDecodeError:
                    continue
            # If all fail, read as binary and try to decode
            with open(path, 'rb') as f:
                raw = f.read()
                return raw, raw.decode('utf-8', errors='replace'), mime_type

        elif category == 'document':
            # PDF handling
            with open(path, 'rb') as f:
                raw_bytes = f.read()

            # Try to extract text from PDF
            text_content = None
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=raw_bytes, filetype="pdf")
                text_parts = []
                for page in doc:
                    text_parts.append(page.get_text())
                text_content = '\n\n'.join(text_parts)
                doc.close()
            except ImportError:
                logger.warning("PyMuPDF not installed, PDF text extraction unavailable")
                text_content = "[PDF text extraction requires PyMuPDF: pip install pymupdf]"
            except Exception as e:
                logger.warning(f"Failed to extract PDF text: {e}")
                text_content = f"[Failed to extract PDF text: {e}]"

            return raw_bytes, text_content, mime_type

        else:
            # Unknown type - try to read as text
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return None, f.read(), 'text/plain'
            except:
                with open(path, 'rb') as f:
                    return f.read(), None, 'application/octet-stream'

    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise


class AttachmentItem:
    """Represents a single attached file."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.path = Path(file_path)
        self.name = self.path.name
        self.category = get_file_category(file_path)
        self.icon = get_file_icon(file_path)
        self.size = self.path.stat().st_size if self.path.exists() else 0

        # Content cache (loaded on demand)
        self._raw_bytes: Optional[bytes] = None
        self._text_content: Optional[str] = None
        self._mime_type: Optional[str] = None
        self._loaded = False

    def load_content(self) -> bool:
        """Load file content into memory."""
        if self._loaded:
            return True
        try:
            self._raw_bytes, self._text_content, self._mime_type = read_file_content(self.file_path)
            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load {self.file_path}: {e}")
            return False

    @property
    def raw_bytes(self) -> Optional[bytes]:
        if not self._loaded:
            self.load_content()
        return self._raw_bytes

    @property
    def text_content(self) -> Optional[str]:
        if not self._loaded:
            self.load_content()
        return self._text_content

    @property
    def mime_type(self) -> str:
        if not self._loaded:
            self.load_content()
        return self._mime_type or 'application/octet-stream'

    @property
    def base64_data(self) -> Optional[str]:
        """Get base64 encoded content for images/PDFs."""
        if self.raw_bytes:
            return base64.b64encode(self.raw_bytes).decode('utf-8')
        return None

    def get_size_str(self) -> str:
        """Get human-readable file size."""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        else:
            return f"{self.size / (1024 * 1024):.1f} MB"

    def __repr__(self):
        return f"AttachmentItem({self.name}, {self.category})"


class FileAttachmentWidget(QWidget):
    """Widget for managing multiple file attachments."""

    # Signals
    attachmentsChanged = Signal()  # Emitted when attachments change

    def __init__(self, parent=None, max_files: int = 10,
                 allowed_categories: Optional[List[str]] = None):
        """
        Initialize the file attachment widget.

        Args:
            parent: Parent widget
            max_files: Maximum number of files allowed (default 10)
            allowed_categories: List of allowed file categories, or None for all
        """
        super().__init__(parent)
        self.max_files = max_files
        self.allowed_categories = allowed_categories
        self.attachments: List[AttachmentItem] = []

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with label and buttons
        header_layout = QHBoxLayout()

        self.label = QLabel("Attachments:")
        header_layout.addWidget(self.label)

        header_layout.addStretch()

        self.add_btn = QPushButton("+ Add Files")
        self.add_btn.setToolTip("Add files to attach (images, text, code, PDFs)")
        self.add_btn.clicked.connect(self.add_files_dialog)
        header_layout.addWidget(self.add_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setToolTip("Remove all attachments")
        self.clear_btn.clicked.connect(self.clear_attachments)
        self.clear_btn.setEnabled(False)
        header_layout.addWidget(self.clear_btn)

        layout.addLayout(header_layout)

        # File list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        self.file_list.setIconSize(QSize(24, 24))
        self.file_list.setMinimumHeight(80)
        self.file_list.setMaximumHeight(150)

        # Enable drag and drop
        self.setAcceptDrops(True)
        self.file_list.setAcceptDrops(True)

        # Placeholder text
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px dashed #ccc;
                border-radius: 4px;
            }
            QListWidget:empty {
                background-color: #f9f9f9;
            }
        """)

        layout.addWidget(self.file_list)

        # Info label
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.info_label)

        self.update_info_label()

    def update_info_label(self):
        """Update the info label with current state."""
        if not self.attachments:
            self.info_label.setText("Drag & drop files or click 'Add Files'")
        else:
            total_size = sum(a.size for a in self.attachments)
            size_str = f"{total_size / 1024:.1f} KB" if total_size < 1024*1024 else f"{total_size / (1024*1024):.1f} MB"
            self.info_label.setText(f"{len(self.attachments)}/{self.max_files} files ({size_str})")

        self.clear_btn.setEnabled(len(self.attachments) > 0)

    def add_files_dialog(self):
        """Open file dialog to add files."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Attach",
            "",
            get_file_filter_string()
        )

        if files:
            self.add_files(files)

    def add_files(self, file_paths: List[str]):
        """Add multiple files to attachments."""
        added = 0
        for path in file_paths:
            if len(self.attachments) >= self.max_files:
                QMessageBox.warning(
                    self, "Maximum Files Reached",
                    f"Cannot add more files. Maximum is {self.max_files}."
                )
                break

            if self.add_file(path, silent=True):
                added += 1

        if added > 0:
            self.attachmentsChanged.emit()
            logger.info(f"Added {added} file(s) as attachments")

    def add_file(self, file_path: str, silent: bool = False) -> bool:
        """
        Add a single file to attachments.

        Args:
            file_path: Path to the file
            silent: If True, don't show error dialogs

        Returns:
            True if file was added successfully
        """
        path = Path(file_path)

        # Check if file exists
        if not path.exists():
            if not silent:
                QMessageBox.warning(self, "File Not Found", f"File not found: {path.name}")
            return False

        # Check if already added
        for att in self.attachments:
            if att.file_path == str(path):
                if not silent:
                    QMessageBox.information(self, "Already Added", f"{path.name} is already attached.")
                return False

        # Check file category
        category = get_file_category(file_path)
        if self.allowed_categories and category not in self.allowed_categories:
            if not silent:
                QMessageBox.warning(
                    self, "Unsupported File Type",
                    f"File type not supported: {path.suffix}\n\nAllowed types: {', '.join(self.allowed_categories)}"
                )
            return False

        # Check max files
        if len(self.attachments) >= self.max_files:
            if not silent:
                QMessageBox.warning(
                    self, "Maximum Files Reached",
                    f"Cannot add more files. Maximum is {self.max_files}."
                )
            return False

        # Create attachment item
        try:
            attachment = AttachmentItem(file_path)
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "Error", f"Failed to read file: {e}")
            return False

        # Add to list
        self.attachments.append(attachment)

        # Create list item with icon
        item = QListWidgetItem()
        item.setText(f"{attachment.icon} {attachment.name} ({attachment.get_size_str()})")
        item.setData(Qt.UserRole, file_path)
        item.setToolTip(f"{file_path}\n{attachment.category.title()} • {attachment.get_size_str()}")

        # Create thumbnail for images
        if attachment.category == 'image':
            try:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    item.setIcon(icon)
            except:
                pass

        self.file_list.addItem(item)
        self.update_info_label()

        if not silent:
            self.attachmentsChanged.emit()

        return True

    def remove_selected(self):
        """Remove selected files from attachments."""
        selected = self.file_list.selectedItems()
        if not selected:
            return

        for item in selected:
            file_path = item.data(Qt.UserRole)
            # Remove from attachments list
            self.attachments = [a for a in self.attachments if a.file_path != file_path]
            # Remove from list widget
            self.file_list.takeItem(self.file_list.row(item))

        self.update_info_label()
        self.attachmentsChanged.emit()

    def clear_attachments(self):
        """Remove all attachments."""
        if not self.attachments:
            return

        reply = QMessageBox.question(
            self, "Clear Attachments",
            f"Remove all {len(self.attachments)} attachments?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.attachments.clear()
            self.file_list.clear()
            self.update_info_label()
            self.attachmentsChanged.emit()

    def show_context_menu(self, position):
        """Show context menu for file list."""
        menu = QMenu(self)

        remove_action = menu.addAction("Remove Selected")
        remove_action.triggered.connect(self.remove_selected)
        remove_action.setEnabled(len(self.file_list.selectedItems()) > 0)

        menu.addSeparator()

        clear_action = menu.addAction("Clear All")
        clear_action.triggered.connect(self.clear_attachments)
        clear_action.setEnabled(len(self.attachments) > 0)

        menu.exec(self.file_list.mapToGlobal(position))

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle drop event."""
        urls = event.mimeData().urls()
        if urls:
            files = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if files:
                self.add_files(files)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def get_attachments(self) -> List[AttachmentItem]:
        """Get all attachment items."""
        return self.attachments

    def get_image_attachments(self) -> List[AttachmentItem]:
        """Get only image attachments."""
        return [a for a in self.attachments if a.category == 'image']

    def get_text_attachments(self) -> List[AttachmentItem]:
        """Get text and code attachments."""
        return [a for a in self.attachments if a.category in ['text', 'code', 'data']]

    def get_document_attachments(self) -> List[AttachmentItem]:
        """Get document (PDF) attachments."""
        return [a for a in self.attachments if a.category == 'document']

    def has_attachments(self) -> bool:
        """Check if there are any attachments."""
        return len(self.attachments) > 0

    def get_attachment_count(self) -> int:
        """Get number of attachments."""
        return len(self.attachments)

    def prepare_for_llm(self) -> List[Dict]:
        """
        Prepare attachments for LLM API calls.

        Returns a list of content parts suitable for LLM message content arrays.
        For OpenAI-style APIs, this returns image_url and text parts.
        """
        parts = []

        for attachment in self.attachments:
            if not attachment.load_content():
                continue

            if attachment.category == 'image':
                # Image as base64 data URL
                if attachment.base64_data:
                    parts.append({
                        'type': 'image_url',
                        'image_url': {
                            'url': f"data:{attachment.mime_type};base64,{attachment.base64_data}"
                        }
                    })

            elif attachment.category in ['text', 'code', 'data']:
                # Text content
                if attachment.text_content:
                    parts.append({
                        'type': 'text',
                        'text': f"[File: {attachment.name}]\n```\n{attachment.text_content}\n```"
                    })

            elif attachment.category == 'document':
                # PDF - include both image (if possible) and extracted text
                if attachment.base64_data:
                    parts.append({
                        'type': 'image_url',
                        'image_url': {
                            'url': f"data:{attachment.mime_type};base64,{attachment.base64_data}"
                        }
                    })
                if attachment.text_content:
                    parts.append({
                        'type': 'text',
                        'text': f"[PDF: {attachment.name} - Extracted Text]\n{attachment.text_content}"
                    })

        return parts

    def prepare_for_gemini(self) -> List:
        """
        Prepare attachments for Google Gemini API.

        Returns a list of content parts suitable for Gemini generate_content.
        """
        parts = []

        for attachment in self.attachments:
            if not attachment.load_content():
                continue

            if attachment.category == 'image':
                # For Gemini, we can use PIL Image directly
                if attachment.raw_bytes:
                    try:
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(attachment.raw_bytes))
                        parts.append(img)
                    except Exception as e:
                        logger.warning(f"Failed to load image for Gemini: {e}")

            elif attachment.category in ['text', 'code', 'data']:
                if attachment.text_content:
                    parts.append(f"[File: {attachment.name}]\n```\n{attachment.text_content}\n```")

            elif attachment.category == 'document':
                # For PDFs, include extracted text
                if attachment.text_content:
                    parts.append(f"[PDF: {attachment.name}]\n{attachment.text_content}")

        return parts
