#!/usr/bin/env python3
"""
Generate a concise Code Map for the ImageAI repository.

Outputs Markdown to Docs/CodeMap.md summarizing:
- Project structure with line counts
- Primary entry points and key modules
- Quick links to important files

Usage:
  python tools/generate_code_map.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_PATH = REPO_ROOT / "Docs" / "CodeMap.md"

EXCLUDE_DIRS = {
    ".git", ".idea", ".venv", ".venv_linux", "__pycache__",
    "Screenshots", "Debug", ".junie", ".claude",
}
EXCLUDE_FILES = {"screenshot_20250912.png"}


def list_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories
        parts = Path(dirpath).parts
        if any(p in EXCLUDE_DIRS for p in parts):
            continue
        for name in filenames:
            if name in EXCLUDE_FILES:
                continue
            if name.endswith((".py", ".md", ".txt", ".j2")):
                files.append(Path(dirpath) / name)
    return files


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def tree_structure_with_counts(root: Path) -> str:
    lines: list[str] = ["``\nImageAI/"]

    def walk(dir_path: Path, prefix: str = ""):
        # List dirs and files
        entries = sorted([p for p in dir_path.iterdir() if p.name not in EXCLUDE_DIRS], key=lambda p: (p.is_file(), p.name))
        for i, p in enumerate(entries):
            is_last = i == len(entries) - 1
            branch = "└── " if is_last else "├── "
            next_prefix = prefix + ("    " if is_last else "│   ")
            if p.is_dir():
                lines.append(f"{prefix}{branch}{p.name}/")
                walk(p, next_prefix)
            else:
                if p.suffix in {".py", ".md", ".txt", ".j2"}:
                    cnt = count_lines(p)
                    comment = ""
                    if p.name == "main.py":
                        comment = " # Main entry point"
                    lines.append(f"{prefix}{branch}{p.name}  # {cnt} lines{comment}")

    walk(root)
    lines.append("```")
    return "\n".join(lines)


def detect_primary_entries(root: Path) -> list[tuple[str, str]]:
    entries = []
    # Known primary files
    mapping = {
        "Main Application": "main.py",
        "GUI Launch": "gui/__init__.py",
        "CLI Parser": "cli/parser.py",
        "CLI Runner": "cli/runner.py",
        "Provider Factory": "providers/__init__.py",
    }
    for title, rel in mapping.items():
        p = root / rel
        if p.exists():
            entries.append((title, rel))
    return entries


def summarize_core_exports(core_init: Path) -> list[str]:
    exports: list[str] = []
    if not core_init.exists():
        return exports
    try:
        lines = core_init.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return exports
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Single-line: from .module import A, B
        m = re.match(r"from \.([\w_]+) import ([^()]+)$", line)
        if m and "(" not in line:
            module = m.group(1)
            names = [n.strip() for n in m.group(2).split(",") if n.strip()]
            for n in names:
                exports.append(f"- {n} (from core.{module})")
            i += 1
            continue
        # Multi-line: from .module import ( ... )
        m2 = re.match(r"from \.([\w_]+) import \($", line)
        if m2:
            module = m2.group(1)
            collected = []
            i += 1
            while i < len(lines):
                inner = lines[i].strip()
                if inner.startswith(")"):
                    break
                inner = inner.rstrip(",")
                if inner:
                    collected.append(inner)
                i += 1
            for n in collected:
                exports.append(f"- {n} (from core.{module})")
            # Skip the closing line
            i += 1
            continue
        i += 1
    return exports


def generate() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts: list[str] = []
    parts.append("# ImageAI CodeMap")
    parts.append("")
    parts.append(f"Last Updated: {now}")
    parts.append("")
    parts.append("## Quick Navigation")
    for title, rel in detect_primary_entries(REPO_ROOT):
        parts.append(f"- {title}: `{rel}`")
    parts.append("")
    parts.append("## Project Structure")
    parts.append("")
    parts.append(tree_structure_with_counts(REPO_ROOT))
    parts.append("")
    parts.append("## Core Exports")
    exports = summarize_core_exports(REPO_ROOT / "core" / "__init__.py")
    if exports:
        parts.extend(exports)
    else:
        parts.append("- (No exports detected)")
    parts.append("")
    parts.append("## Notes")
    parts.append("- Refer to this map to quickly locate functions, classes, and modules.")
    parts.append("- Line counts approximate; regenerate after refactors.")
    return "\n".join(parts)


def main() -> int:
    out = generate()
    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_PATH.write_text(out, encoding="utf-8")
    print(f"Updated {DOCS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
