"""Dialog to select social media image sizes from a Markdown table.

Parses Plans/social-media-image-sizes-2025.md and presents a searchable,
sortable table. On accept, exposes a WxH resolution string.
"""

from pathlib import Path
import re
from typing import List, Optional, Tuple
from gui.dialog_utils import show_warning, show_error
import logging
logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QMessageBox,
    QAbstractItemView
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


class SocialSizesDialog(QDialog):
    """A dialog to browse and pick social media sizes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Social Media Image Sizes")
        self.resize(920, 520)
        self._selected_resolution: Optional[str] = None
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        v = QVBoxLayout(self)

        # Search
        sh = QHBoxLayout()
        sh.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by platform, type, size, ratio, notes...")
        self.search_edit.textChanged.connect(self._apply_filter)
        sh.addWidget(self.search_edit)
        v.addLayout(sh)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "#", "Platform", "Image Type", "Recommended Size (px)", "Aspect Ratio", "Notes"
        ])
        self.table.setSortingEnabled(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        v.addWidget(self.table)

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
            logger.warning("SocialSizesDialog: No table rows parsed from %s", md_path)
            return
        # Map columns by normalized name (robust to spacing/punctuation)
        def norm(s: str) -> str:
            s = (s or '').lower()
            return re.sub(r"[^a-z0-9]+", "", s)
        name_to_idx = {norm(h): i for i, h in enumerate(headers)}
        idx_platform = name_to_idx.get("platform")
        idx_type = name_to_idx.get("imagetype")
        # allow both with/without (px)
        idx_size = name_to_idx.get("recommendedsizepx") or name_to_idx.get("recommendedsize")
        idx_ratio = name_to_idx.get("aspectratio")
        idx_notes = name_to_idx.get("notes") if "notes" in name_to_idx else -1
        if None in (idx_platform, idx_type, idx_size, idx_ratio):
            show_warning(self, "Parse Error", f"Unexpected table headers: {headers}")
            logger.warning("SocialSizesDialog: Header mapping failed. Headers=%s NormMap=%s", headers, name_to_idx)
            return

        # Populate table
        self.table.setRowCount(0)
        for i, row in enumerate(rows):
            platform = row[idx_platform] if idx_platform >= 0 else ""
            img_type = row[idx_type] if idx_type >= 0 else ""
            size_text = row[idx_size] if idx_size >= 0 else ""
            ratio = row[idx_ratio] if idx_ratio >= 0 else ""
            notes = row[idx_notes] if idx_notes >= 0 else ""
            self._append_row(i, platform, img_type, size_text, ratio, notes)

        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        logger.info("SocialSizesDialog: Loaded %d rows from %s", self.table.rowCount(), md_path)

    def _append_row(self, idx: int, platform: str, img_type: str, size_text: str, ratio: str, notes: str):
        r = self.table.rowCount()
        self.table.insertRow(r)

        self.table.setItem(r, 0, QTableWidgetItem(str(idx)))
        self.table.setItem(r, 1, QTableWidgetItem(platform))
        self.table.setItem(r, 2, QTableWidgetItem(img_type))
        self.table.setItem(r, 3, QTableWidgetItem(size_text))
        self.table.setItem(r, 4, QTableWidgetItem(ratio))
        self.table.setItem(r, 5, QTableWidgetItem(notes))

        # Store extracted resolution in the row for quick retrieval
        resolution = _extract_resolution_px(size_text)
        for c in range(self.table.columnCount()):
            item = self.table.item(r, c)
            if item:
                item.setData(Qt.UserRole, resolution)

    def _apply_filter(self, text: str):
        text = (text or '').lower().strip()
        for r in range(self.table.rowCount()):
            row_text = []
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                row_text.append(it.text().lower() if it else '')
            visible = all(word in " ".join(row_text) for word in text.split()) if text else True
            self.table.setRowHidden(r, not visible)

    def _on_selection_changed(self):
        r = self._current_row()
        resolution = None
        if r is not None:
            item = self.table.item(r, 0)
            resolution = item.data(Qt.UserRole) if item else None
        self.btn_use.setEnabled(bool(resolution))

    def _current_row(self) -> Optional[int]:
        items = self.table.selectedItems()
        if not items:
            return None
        return items[0].row()

    def _use_selected(self):
        r = self._current_row()
        if r is None:
            return
        item = self.table.item(r, 0)
        resolution = item.data(Qt.UserRole) if item else None
        if not resolution:
            QMessageBox.information(self, "Unavailable", "Selected row has no explicit pixel size.")
            return
        self._selected_resolution = resolution
        self.accept()

    def selected_resolution(self) -> Optional[str]:
        return self._selected_resolution
