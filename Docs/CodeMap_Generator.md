# Code Map: How to Generate

This document explains how to regenerate `Docs/CodeMap.md` so the repository map stays current.

Steps
- Activate your virtual environment (optional):
  - `python -m venv .venv && source .venv/bin/activate` (Windows: `\.venv\\Scripts\\Activate.ps1`)
- Run the generator:
  - `python tools/generate_code_map.py`
- Output:
  - The script writes a concise Markdown overview to `Docs/CodeMap.md` with:
    - Quick Navigation (entry points)
    - Project Structure tree with line counts
    - Core exports detected from `core/__init__.py`

Scope & Rules
- Excludes non-source directories: `.git`, `.venv*`, `__pycache__`, `Screenshots`, `Debug`, `.idea`, `.claude`, `.junie`.
- Counts lines for `.py`, `.md`, `.txt`, and `.j2` files for context.
- Uses simple heuristics to list exports from `core/__init__.py`.

Tips
- Regenerate after refactors or file moves.
- Use the map to quickly locate functions or classes before searching.
- If you add new top-level entry points, update the mapping in `tools/generate_code_map.py`.
