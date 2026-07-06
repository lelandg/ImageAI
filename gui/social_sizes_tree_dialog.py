"""Tree-based dialog for selecting social media image sizes.

Displays sizes organized by platform in a collapsible tree view.
Double-click to select a size immediately. Remembers expansion state.
"""

from pathlib import Path
import re
import json
from typing import Dict, List, Optional
from gui.dialog_utils import show_warning, show_error
import logging
logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon, QPixmap, QFont, QColor, QBrush, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QPushButton, QMessageBox
)

from .common.dialog_conventions import (
    DialogCleanupMixin, bind_primary_action, set_default_button
)
from .common.markdown_tables import parse_markdown_table, extract_resolution_px
from .theme import NAVY_LIGHT, BORDER_CYAN, TEXT_PRIMARY, CYAN_DARK


class SocialSizesTreeDialog(DialogCleanupMixin, QDialog):
    """A dialog to browse and pick social media sizes using a tree view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Size Presets")
        self.resize(900, 650)
        self._selected_resolution: Optional[str] = None
        self._selected_platform: Optional[str] = None
        self._selected_type: Optional[str] = None
        self._highlighted_item: Optional[QTreeWidgetItem] = None
        self.settings = QSettings("ImageAI", "SocialSizesDialog")
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
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

        # Selection info panel - always visible with a font-metrics minimum
        # height (two lines of rich text) to prevent layout shift
        self.info_panel = QLabel("")
        self.info_panel.setStyleSheet(f"""
            QLabel {{
                background-color: {NAVY_LIGHT};
                border: 2px solid {BORDER_CYAN};
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
                color: {TEXT_PRIMARY};
            }}
        """)
        self.info_panel.setWordWrap(True)
        self.info_panel.setMinimumHeight(
            2 * self.info_panel.fontMetrics().lineSpacing() + 20
        )
        self._show_help_text()
        v.addWidget(self.info_panel)

        # Search
        sh = QHBoxLayout()
        search_label = QLabel("&Search:")
        sh.addWidget(search_label)
        self.search_edit = QLineEdit()
        search_label.setBuddy(self.search_edit)
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
        shortcut_label = QLabel("<small style='color: gray;'>Double-click or press Enter to select (Ctrl+Enter also works). Esc to close</small>")
        shortcut_label.setAlignment(Qt.AlignCenter)
        v.addWidget(shortcut_label)

        # Buttons
        bh = QHBoxLayout()
        bh.addStretch()
        self.btn_use = QPushButton("&Use Size")
        self.btn_use.setToolTip("Apply selected size (Enter or Ctrl+Enter)")
        self.btn_use.setStyleSheet("""
            QPushButton {
                font-weight: bold;
            }
        """)
        self.btn_use.setEnabled(False)
        self.btn_use.clicked.connect(self._use_selected)
        self.btn_close = QPushButton("&Close")
        self.btn_close.clicked.connect(self.reject)
        bh.addWidget(self.btn_use)
        bh.addWidget(self.btn_close)
        v.addLayout(bh)

        # Set up keyboard shortcuts.
        # Enter activates the single default button (no window-wide bare
        # Return shortcut — that fired while typing in the search box).
        set_default_button(self, self.btn_use, focus=False)
        # Ctrl+Return / Ctrl+Enter also apply the selected size
        self._primary_action = bind_primary_action(self, self._use_selected)
        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.reject)
        # Initial focus goes to the primary input
        self.search_edit.setFocus()

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

            headers, rows = parse_markdown_table(text)
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
                resolution = extract_resolution_px(size_text)
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
        """Filter the three-level tree: Category → Platform → Size item.

        Search words are matched against each size item's four columns plus
        its platform and category names. Matching size items are revealed by
        expanding both their category and platform.
        """
        text = (text or '').lower().strip()
        words = text.split()

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            category_item = root.child(i)
            category_name = category_item.text(0).lower()
            category_visible = False

            for j in range(category_item.childCount()):
                platform_item = category_item.child(j)
                platform_name = platform_item.text(0).lower()
                platform_visible = False

                for k in range(platform_item.childCount()):
                    size_item = platform_item.child(k)
                    # Match against the size row plus its ancestors' names
                    item_text = [category_name, platform_name]
                    for col in range(4):
                        item_text.append(size_item.text(col).lower())
                    full_text = " ".join(item_text)

                    # Check if all search words are in the text
                    visible = all(word in full_text for word in words) if words else True
                    size_item.setHidden(not visible)

                    if visible:
                        platform_visible = True

                # Hide platform if no size items are visible
                platform_item.setHidden(not platform_visible)
                if platform_visible:
                    category_visible = True

                # Expand platform if it has visible items and there's a search
                if platform_visible and words:
                    platform_item.setExpanded(True)

            # Hide category if no platforms are visible
            category_item.setHidden(not category_visible)

            # Expand category if it has visible items and there's a search
            if category_visible and words:
                category_item.setExpanded(True)

    def _show_help_text(self):
        """Show help text in the info panel when nothing is selected."""
        help_text = (
            "<b>💡 Tip:</b> Expand a category to browse sizes. "
            "Double-click or press Enter to apply a size."
        )
        self.info_panel.setText(help_text)

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if items:
            item = items[0]
            resolution = item.data(0, Qt.UserRole)
            self.btn_use.setEnabled(bool(resolution))

            # Clear previous highlights first
            self._clear_all_highlights()

            # Update visual feedback
            if resolution:
                # Highlight current selection (theme colors, readable on dark)
                for col in range(4):
                    item.setBackground(col, QBrush(QColor(CYAN_DARK)))
                    item.setForeground(col, QBrush(QColor(TEXT_PRIMARY)))
                self._highlighted_item = item

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

                    self._selected_platform = platform
                    self._selected_type = type_name
            else:
                # Selected a non-size item (platform header), show help
                self._show_help_text()
        else:
            self.btn_use.setEnabled(False)
            self._show_help_text()
            self._clear_all_highlights()

    def _clear_all_highlights(self):
        """Clear the last highlighted size item (level 3) in the tree."""
        if self._highlighted_item is not None:
            for col in range(4):
                self._highlighted_item.setBackground(col, QBrush())
                self._highlighted_item.setForeground(col, QBrush())
            self._highlighted_item = None

    def _on_double_click(self, item: QTreeWidgetItem, column: int):
        resolution = item.data(0, Qt.UserRole)
        if resolution:
            self._selected_resolution = resolution
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
        self.accept()

    def _save_expansion_state(self):
        """Save which categories and platforms are expanded, and which item is selected.

        Tree structure: Category (level 1) → Platform (level 2) → Size Item (level 3)
        """
        expanded_categories = []
        expanded_platforms = []

        # Level 1: Categories
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            category_item = root.child(i)
            if category_item.isExpanded():
                expanded_categories.append(category_item.text(0))

            # Level 2: Platforms within this category
            for j in range(category_item.childCount()):
                platform_item = category_item.child(j)
                if platform_item.isExpanded():
                    # Store as "category::platform" to uniquely identify
                    expanded_platforms.append(f"{category_item.text(0)}::{platform_item.text(0)}")

        self.settings.setValue("expanded_categories", json.dumps(expanded_categories))
        self.settings.setValue("expanded_platforms", json.dumps(expanded_platforms))

        # Save selected item path (category|platform|type)
        items = self.tree.selectedItems()
        if items:
            item = items[0]
            parent = item.parent()  # Platform
            if parent:
                grandparent = parent.parent()  # Category
                if grandparent:
                    # Full path: category|platform|type
                    selected_path = f"{grandparent.text(0)}|{parent.text(0)}|{item.text(0)}"
                    self.settings.setValue("selected_item", selected_path)

    def _restore_expansion_state(self):
        """Restore previously expanded categories/platforms and selected item.

        Tree structure: Category (level 1) → Platform (level 2) → Size Item (level 3)
        """
        # Load saved expansion state
        expanded_categories_str = self.settings.value("expanded_categories", "[]")
        expanded_platforms_str = self.settings.value("expanded_platforms", "[]")
        try:
            expanded_categories = json.loads(expanded_categories_str)
        except:
            expanded_categories = []
        try:
            expanded_platforms = json.loads(expanded_platforms_str)
        except:
            expanded_platforms = []

        # Restore expansion state
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            category_item = root.child(i)

            # Expand category if it was expanded before
            if category_item.text(0) in expanded_categories:
                category_item.setExpanded(True)

            # Check platforms within this category
            for j in range(category_item.childCount()):
                platform_item = category_item.child(j)
                platform_key = f"{category_item.text(0)}::{platform_item.text(0)}"
                if platform_key in expanded_platforms:
                    # Also expand the parent category to make this visible
                    category_item.setExpanded(True)
                    platform_item.setExpanded(True)

        # Restore selected item
        selected_path = self.settings.value("selected_item", "")
        if selected_path:
            parts = selected_path.split("|")
            if len(parts) == 3:
                category_name, platform_name, item_name = parts
                # Navigate the tree to find and select the item
                for i in range(root.childCount()):
                    category_item = root.child(i)
                    if category_item.text(0) == category_name:
                        category_item.setExpanded(True)
                        for j in range(category_item.childCount()):
                            platform_item = category_item.child(j)
                            if platform_item.text(0) == platform_name:
                                platform_item.setExpanded(True)
                                for k in range(platform_item.childCount()):
                                    size_item = platform_item.child(k)
                                    if size_item.text(0) == item_name:
                                        self.tree.setCurrentItem(size_item)
                                        self.tree.scrollToItem(size_item)
                                        return
            elif len(parts) == 2:
                # Legacy format: platform|type (migrate to new format)
                platform_name, item_name = parts
                # Try to find in any category
                for i in range(root.childCount()):
                    category_item = root.child(i)
                    for j in range(category_item.childCount()):
                        platform_item = category_item.child(j)
                        if platform_item.text(0) == platform_name:
                            category_item.setExpanded(True)
                            platform_item.setExpanded(True)
                            for k in range(platform_item.childCount()):
                                size_item = platform_item.child(k)
                                if size_item.text(0) == item_name:
                                    self.tree.setCurrentItem(size_item)
                                    self.tree.scrollToItem(size_item)
                                    return

    def on_dialog_close(self):
        """Save state on every exit path (OK, Close, Escape, title-bar X)."""
        self._save_expansion_state()
        self.settings.setValue("geometry", self.saveGeometry())

    def selected_resolution(self) -> Optional[str]:
        return self._selected_resolution