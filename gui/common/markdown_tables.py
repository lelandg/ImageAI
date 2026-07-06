"""Shared helpers for parsing size-preset Markdown tables.

Extracted from the retired gui/social_sizes_dialog.py so the tree-based size
picker (gui/social_sizes_tree_dialog.py) and any future consumers share one
implementation.
"""

import re
from typing import List, Optional, Tuple


def parse_markdown_table(md_text: str) -> Tuple[List[str], List[List[str]]]:
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


def extract_resolution_px(size_text: str) -> Optional[str]:
    """Extract first WxH pair from text like '1080 × 1920' or '512x512'."""
    if not size_text:
        return None
    match = re.search(r"(\d{2,5})\s*[×x]\s*(\d{2,5})", size_text)
    if match:
        w, h = match.group(1), match.group(2)
        return f"{w}x{h}"
    return None
