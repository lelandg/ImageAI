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
        self.setWindowTitle("Social Media Image Sizes")
        self.resize(800, 600)
        self._selected_resolution: Optional[str] = None
        self.settings = QSettings("ImageAI", "SocialSizesDialog")
        self._init_ui()
        self._load_data()
        self._restore_expansion_state()

    def _init_ui(self):
        v = QVBoxLayout(self)

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
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 150)
        self.tree.setColumnWidth(2, 100)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        v.addWidget(self.tree)

        # Buttons
        bh = QHBoxLayout()
        bh.addStretch()
        self.btn_use = QPushButton("Use Size")
        self.btn_use.setEnabled(False)
        self.btn_use.clicked.connect(self._use_selected)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        bh.addWidget(self.btn_use)
        bh.addWidget(self.btn_close)
        v.addLayout(bh)

    def _load_data(self):
        # Load markdown
        repo_root = Path(__file__).resolve().parents[1]
        md_path = repo_root / "Plans" / "social-media-image-sizes-2025.md"
        if not md_path.exists():
            show_warning(self, "Not Found", f"Could not find {md_path}")
            return
        try:
            text = md_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            show_error(self, "Read Error", f"Could not read {md_path}", exception=e)
            return

        headers, rows = _parse_markdown_table(text)
        if not headers or not rows:
            show_warning(self, "Parse Error", "No table rows found in sizes document.")
            logger.warning("SocialSizesTreeDialog: No table rows parsed from %s", md_path)
            return

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
            show_warning(self, "Parse Error", f"Unexpected table headers: {headers}")
            logger.warning("SocialSizesTreeDialog: Header mapping failed. Headers=%s", headers)
            return

        # Build tree structure
        platform_items: Dict[str, QTreeWidgetItem] = {}

        for row in rows:
            platform = row[idx_platform] if idx_platform >= 0 else ""
            img_type = row[idx_type] if idx_type >= 0 else ""
            size_text = row[idx_size] if idx_size >= 0 else ""
            ratio = row[idx_ratio] if idx_ratio >= 0 else ""
            notes = row[idx_notes] if idx_notes >= 0 else ""

            if not platform:
                continue

            # Get or create platform item
            if platform not in platform_items:
                platform_item = QTreeWidgetItem(self.tree)
                platform_item.setText(0, platform)
                platform_item.setFlags(platform_item.flags() & ~Qt.ItemIsSelectable)
                platform_items[platform] = platform_item
            else:
                platform_item = platform_items[platform]

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

        # Collapse all by default
        self.tree.collapseAll()

        logger.info("SocialSizesTreeDialog: Loaded %d platforms from %s",
                   len(platform_items), md_path)

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
        else:
            self.btn_use.setEnabled(False)

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