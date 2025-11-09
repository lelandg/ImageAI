"""Tree-based dialog for selecting social media image sizes.

Displays sizes organized by platform in a collapsible tree view.
Double-click to select a size immediately. Remembers expansion state.
"""

from pathlib import Path
import re
import json
from typing import Dict, List, Optional, Tuple
from gui.dialog_utils import show_warning, show_error
import logging
logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon, QPixmap, QFont, QColor, QBrush, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QPushButton, QMessageBox
)


def _parse_markdown_table(md_text: str) -> Tuple[List[str], List[List[str]]]:
    """Parse the first GitHub-flavored Markdown table in text.

    Returns (headers, rows). Only lines starting with '|' are considered,
    and the second line with dashes is treated as the divider.
    """
    lines = [ln.rstrip() for ln in md_text.splitlines()]
    table_lines: List[str] = []
    in_table = False
    for ln in lines:
        if ln.strip().startswith('|'):
            table_lines.append(ln)
            in_table = True
        elif in_table:
            break
    if not table_lines:
        return [], []

    # Expect header |----| divider as second line
    header = [c.strip() for c in table_lines[0].strip('|').split('|')]
    # Skip divider line and parse data rows
    data_rows = []
    for ln in table_lines[2:]:
        parts = [c.strip() for c in ln.strip('|').split('|')]
        # pad or trim to header length
        if len(parts) < len(header):
            parts += [''] * (len(header) - len(parts))
        elif len(parts) > len(header):
            parts = parts[:len(header)]
        data_rows.append(parts)
    return header, data_rows


def _extract_resolution_px(size_text: str) -> Optional[str]:
    """Extract first WxH pair from text like '1080 × 1920' or '512x512'."""
    if not size_text:
        return None
    match = re.search(r"(\d{2,5})\s*[×x]\s*(\d{2,5})", size_text)
    if match:
        w, h = match.group(1), match.group(2)
        return f"{w}x{h}"
    return None


class SocialSizesTreeDialog(QDialog):
    """A dialog to browse and pick social media sizes using a tree view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Size Presets")
        self.resize(900, 650)
        self._selected_resolution: Optional[str] = None
        self._selected_platform: Optional[str] = None
        self._selected_type: Optional[str] = None
        self.settings = QSettings("ImageAI", "SocialSizesDialog")
        self._platform_icons: Dict[str, QIcon] = {}
        self._load_icons()
        self._init_ui()
        self._load_data()
        self._restore_expansion_state()

    def _load_icons(self):
        """Load platform icons from the assets directory."""
        repo_root = Path(__file__).resolve().parents[1]
        icons_dir = repo_root / "assets" / "icons" / "social"

        if not icons_dir.exists():
            logger.info(f"Icons directory not found: {icons_dir}")
            return

        # Map of platform names to icon filenames
        platform_mappings = {
            "Apple Podcasts": "apple-podcasts",
            "Bandcamp": "bandcamp",
            "CD Baby": "cd-baby",
            "Discord": "discord",
            "Facebook": "facebook",
            "Instagram": "instagram",
            "LinkedIn": "linkedin",
            "Mastodon": "mastodon",
            "Pinterest": "pinterest",
            "Reddit": "reddit",
            "Snapchat": "snapchat",
            "SoundCloud": "soundcloud",
            "Spotify": "spotify",
            "Threads": "threads",
            "TikTok": "tiktok",
            "Tumblr": "tumblr",
            "Twitch": "twitch",
            "Twitter": "twitter",
            "X": "x",
            "YouTube": "youtube",
            "Vimeo": "vimeo",
            "WhatsApp": "whatsapp",
            "Telegram": "telegram",
        }

        for platform, icon_name in platform_mappings.items():
            # Try SVG first, then PNG
            for ext in [".svg", ".png"]:
                icon_path = icons_dir / f"{icon_name}{ext}"
                if icon_path.exists():
                    self._platform_icons[platform] = QIcon(str(icon_path))
                    break

    def _init_ui(self):
        v = QVBoxLayout(self)

        # Selection info panel
        self.info_panel = QLabel("")
        self.info_panel.setStyleSheet("""
            QLabel {
                background-color: #f0f8ff;
                border: 2px solid #4a90e2;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
                color: #2c3e50;
                min-height: 40px;
            }
        """)
        self.info_panel.setVisible(False)
        v.addWidget(self.info_panel)

        # Search
        sh = QHBoxLayout()
        sh.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by platform, type, size...")
        self.search_edit.textChanged.connect(self._apply_filter)
        sh.addWidget(self.search_edit)
        v.addLayout(sh)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Platform / Type", "Size (px)", "Aspect Ratio", "Notes"])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 150)
        self.tree.setColumnWidth(2, 100)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        v.addWidget(self.tree)

        # Add shortcut hint label
        shortcut_label = QLabel("<small style='color: gray;'>Double-click to select, or use Enter key. Esc to close</small>")
        shortcut_label.setAlignment(Qt.AlignCenter)
        v.addWidget(shortcut_label)

        # Buttons
        bh = QHBoxLayout()
        bh.addStretch()
        self.btn_use = QPushButton("Use Size")
        self.btn_use.setToolTip("Apply selected size (Enter)")
        self.btn_use.setDefault(True)
        self.btn_use.setStyleSheet("""
            QPushButton {
                font-weight: bold;
            }
        """)
        self.btn_use.setEnabled(False)
        self.btn_use.clicked.connect(self._use_selected)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        bh.addWidget(self.btn_use)
        bh.addWidget(self.btn_close)
        v.addLayout(bh)

        # Set up keyboard shortcuts
        # Enter to use selected size
        self.btn_use.setShortcut(QKeySequence("Return"))
        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.reject)

    def _load_data(self):
        """Load size presets from multiple markdown files organized by category."""
        repo_root = Path(__file__).resolve().parents[1]

        # Define categories and their markdown files
        categories = [
            {
                "name": "📱 Social Media",
                "file": "social-media-image-sizes-2025.md",
                "icon_name": None
            },
            {
                "name": "🔖 Favicon Sizes",
                "file": "favicon-sizes.md",
                "icon_name": None
            },
            {
                "name": "🖼️ Common Sizes",
                "file": "common-sizes.md",
                "icon_name": None
            }
        ]

        total_loaded = 0

        for category_info in categories:
            category_name = category_info["name"]
            md_path = repo_root / "Plans" / category_info["file"]

            if not md_path.exists():
                logger.warning(f"Size file not found: {md_path}")
                continue

            try:
                text = md_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.error(f"Could not read {md_path}: {e}")
                continue

            headers, rows = _parse_markdown_table(text)
            if not headers or not rows:
                logger.warning(f"No table rows parsed from {md_path}")
                continue

            # Map columns by normalized name
            def norm(s: str) -> str:
                s = (s or '').lower()
                return re.sub(r"[^a-z0-9]+", "", s)

            name_to_idx = {norm(h): i for i, h in enumerate(headers)}
            idx_platform = name_to_idx.get("platform")
            idx_type = name_to_idx.get("imagetype")
            idx_size = name_to_idx.get("recommendedsizepx") or name_to_idx.get("recommendedsize")
            idx_ratio = name_to_idx.get("aspectratio")
            idx_notes = name_to_idx.get("notes") if "notes" in name_to_idx else -1

            if None in (idx_platform, idx_type, idx_size, idx_ratio):
                logger.warning(f"Header mapping failed for {md_path}. Headers={headers}")
                continue

            # Create category item at top level
            category_item = QTreeWidgetItem(self.tree)
            category_item.setText(0, category_name)
            category_item.setFlags(category_item.flags() & ~Qt.ItemIsSelectable)

            # Bold and larger font for category headers
            font = QFont()
            font.setBold(True)
            font.setPointSize(font.pointSize() + 1)
            category_item.setFont(0, font)

            # Color category headers
            category_item.setForeground(0, QBrush(QColor(40, 100, 180)))

            # Build tree structure under this category
            platform_items: Dict[str, QTreeWidgetItem] = {}

            for row in rows:
                platform = row[idx_platform] if idx_platform >= 0 else ""
                img_type = row[idx_type] if idx_type >= 0 else ""
                size_text = row[idx_size] if idx_size >= 0 else ""
                ratio = row[idx_ratio] if idx_ratio >= 0 else ""
                notes = row[idx_notes] if idx_notes >= 0 else ""

                if not platform:
                    continue

                # Get or create platform item under category
                platform_key = f"{category_name}::{platform}"
                if platform_key not in platform_items:
                    platform_item = QTreeWidgetItem(category_item)
                    platform_item.setText(0, platform)
                    platform_item.setFlags(platform_item.flags() & ~Qt.ItemIsSelectable)
                    # Set icon if available (mainly for social media)
                    if platform in self._platform_icons:
                        platform_item.setIcon(0, self._platform_icons[platform])
                    # Bold font for platform headers
                    pfont = QFont()
                    pfont.setBold(True)
                    platform_item.setFont(0, pfont)
                    platform_items[platform_key] = platform_item
                else:
                    platform_item = platform_items[platform_key]

                # Create size item under platform
                size_item = QTreeWidgetItem(platform_item)
                size_item.setText(0, img_type)
                size_item.setText(1, size_text)
                size_item.setText(2, ratio)
                size_item.setText(3, notes)

                # Store resolution for quick retrieval
                resolution = _extract_resolution_px(size_text)
                size_item.setData(0, Qt.UserRole, resolution)

                # Make non-editable
                for col in range(4):
                    size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)

                total_loaded += 1

        # Collapse all by default
        self.tree.collapseAll()

        logger.info("SocialSizesTreeDialog: Loaded %d total size presets from %d categories",
                   total_loaded, len(categories))

    def _apply_filter(self, text: str):
        text = (text or '').lower().strip()

        # Iterate through all items
        iterator = self.tree.invisibleRootItem()
        for i in range(iterator.childCount()):
            platform_item = iterator.child(i)
            platform_visible = False

            for j in range(platform_item.childCount()):
                child_item = platform_item.child(j)
                # Get all text from the item
                item_text = []
                for col in range(4):
                    item_text.append(child_item.text(col).lower())
                full_text = " ".join(item_text)

                # Check if all search words are in the text
                visible = all(word in full_text for word in text.split()) if text else True
                child_item.setHidden(not visible)

                if visible:
                    platform_visible = True

            # Hide platform if no children are visible
            platform_item.setHidden(not platform_visible)

            # Expand platform if it has visible items and there's a search
            if platform_visible and text:
                platform_item.setExpanded(True)

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if items:
            item = items[0]
            resolution = item.data(0, Qt.UserRole)
            self.btn_use.setEnabled(bool(resolution))

            # Update visual feedback
            if resolution:
                # Highlight selected item with background color
                for col in range(4):
                    item.setBackground(col, QBrush(QColor(220, 240, 255)))

                # Get platform and type info
                parent = item.parent()
                if parent:
                    platform = parent.text(0)
                    type_name = item.text(0)
                    size = item.text(1)
                    aspect = item.text(2)

                    # Update info panel with selection details
                    info_text = f"<b>Selected:</b> {platform} - {type_name}<br>"
                    info_text += f"<b>Size:</b> {size} | <b>Aspect Ratio:</b> {aspect}"
                    self.info_panel.setText(info_text)
                    self.info_panel.setVisible(True)

                    self._selected_platform = platform
                    self._selected_type = type_name

            # Clear previous highlights
            self._clear_all_highlights()
            # Highlight current selection
            for col in range(4):
                item.setBackground(col, QBrush(QColor(220, 240, 255)))
        else:
            self.btn_use.setEnabled(False)
            self.info_panel.setVisible(False)
            self._clear_all_highlights()

    def _clear_all_highlights(self):
        """Clear all item highlights in the tree."""
        iterator = self.tree.invisibleRootItem()
        for i in range(iterator.childCount()):
            platform_item = iterator.child(i)
            for j in range(platform_item.childCount()):
                child_item = platform_item.child(j)
                for col in range(4):
                    child_item.setBackground(col, QBrush())

    def _on_double_click(self, item: QTreeWidgetItem, column: int):
        resolution = item.data(0, Qt.UserRole)
        if resolution:
            self._selected_resolution = resolution
            self._save_expansion_state()
            self.accept()

    def _use_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return

        item = items[0]
        resolution = item.data(0, Qt.UserRole)
        if not resolution:
            QMessageBox.information(self, "Unavailable",
                                  "Selected item has no explicit pixel size.")
            return

        self._selected_resolution = resolution
        self._save_expansion_state()
        self.accept()

    def _save_expansion_state(self):
        """Save which platforms are expanded."""
        expanded = []
        iterator = self.tree.invisibleRootItem()
        for i in range(iterator.childCount()):
            platform_item = iterator.child(i)
            if platform_item.isExpanded():
                expanded.append(platform_item.text(0))

        self.settings.setValue("expanded_platforms", json.dumps(expanded))

    def _restore_expansion_state(self):
        """Restore previously expanded platforms."""
        expanded_str = self.settings.value("expanded_platforms", "[]")
        try:
            expanded = json.loads(expanded_str)
        except:
            expanded = []

        if expanded:
            iterator = self.tree.invisibleRootItem()
            for i in range(iterator.childCount()):
                platform_item = iterator.child(i)
                if platform_item.text(0) in expanded:
                    platform_item.setExpanded(True)

    def closeEvent(self, event):
        """Save state when closing."""
        self._save_expansion_state()
        super().closeEvent(event)

    def selected_resolution(self) -> Optional[str]:
        return self._selected_resolution