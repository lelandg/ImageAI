# Repository Agents Guidelines

This document serves as the **Source of Truth** for all AI agents (Gemini, Claude, etc.) working on the ImageAI repository. It consolidates project context, operational procedures, and coding standards.

**Note to Agents:** Before starting any task, review this file to ensure compliance with project standards.

---

## 1. Project Overview
**ImageAI** is a comprehensive desktop application and CLI tool for AI image and video generation.
- **Goal:** Unified interface for Google Gemini, OpenAI DALL·E, Stability AI, and Local Stable Diffusion.
- **Key Features:** Video creation (lyrics/MIDI sync), publication layout engine, prompt engineering tools.
- **Architecture:** Modular Python codebase (GUI: PySide6, Logic: `core/`, Providers: `providers/`).

## 2. Code Navigation & Debugging
*   **Code Map (`Docs/CodeMap.md`)**: This is your primary navigation tool. It contains exact line numbers, component relationships, and architectural diagrams.
    *   **Rule:** Always check the "Last Updated" timestamp. If > 7 days old, regenerate it using the `code-map-updater` agent (or `tools/generate_code_map.py`).
*   **Debug Files**: Checked on exit.
    *   `./imageai_current.log`: Most recent session log.
    *   `./imageai_current_project.json`: Last loaded project state.
*   **Logs**: stored in `logs/` (or platform-specific: Windows `%APPDATA%`, Linux `~/.local/share`).

## 3. Project Structure
- **`main.py`**: Entry point (CLI & GUI).
- **`core/`**: Business logic, config, utils.
- **`gui/`**: PySide6 interface (Separated into `main_window`, `video/`, `layout/`).
- **`cli/`**: Command-line logic (`parser`, `runner`).
- **`providers/`**: AI backend implementations (Google, OpenAI, etc.).
- **`data/`**: JSON resources (prompts, presets).
- **`Docs/`**: Documentation.

## 4. Plan File Management (CRITICAL)
Plan files in `Plans/` or `Notes/` tracks progress. You **MUST** keep them current.

### When to Update
- **Immediately** after completing a task (✅), starting a task (⏳), creating files, or hitting blockers (❌).
- **Recovery:** If interrupted, read the plan file first to resume context.

### Format Standard
```markdown
## Phase N: [Name] [Status Emoji] [Progress %]
**Last Updated:** YYYY-MM-DD HH:MM

### Tasks
1. ✅ Task Name - **COMPLETED** (file.py:line)
   - Implementation notes...
   - Files created: `path/to/file.py`
2. ⏳ Task Name - **IN PROGRESS**
```

## 5. Operational Guidelines

### File Navigation & Shell Commands
- **NO `cd`**: Never change directories. Use **absolute paths** for all operations (`read_file`, `run_shell_command`).
- **Path Examples**:
    - Linux/WSL: `/mnt/d/Documents/Code/GitHub/ImageAI/main.py`
    - Use `git -C /full/path status`
- **Batch Tools**: Use parallel tool calls (e.g., searching multiple directories) for efficiency.

### Credentials & Security
- **NEVER** store API keys/secrets in the project directory.
- **Locations**:
    - Windows: `%APPDATA%\Roaming\ImageAI\config.json`
    - Linux: `~/.config/ImageAI/config.json`
- **Git**: `.gitignore` must block `config.json`, `.env`, `*.key`.

### Development Environment
- **System**: WSL (Linux) is the primary shell environment for agents.
- **Python**:
    - WSL: `python3` (uses `.venv_linux`).
    - Windows (PowerShell): `python` (uses `.venv`).
- **GUI Framework**: `PyQt6`/`PySide6`.
    - Note: GUI tests may require a display. If in headless WSL, use mocks or skip GUI launch.

### Screenshots
- **Location**: `_screenshots` (symlink to system pictures).
- **Usage**: Check the most recent file by timestamp to visualize UI state.

### Agent Tools
- **Playwright**: Available for web tasks. Set `NODE_PATH` to `~/.nvm/.../lib/node_modules` if needed.
- **File Creation**: Always **verify** file existence after creation. If an agent claims to create a file but doesn't, use `write_file` explicitly.

## 6. Tech Stack
- **Language**: Python 3.9+
- **UI**: PySide6
- **AI**: Google GenAI SDK, OpenAI SDK, Diffusers (Local).
- **Video**: MoviePy, ImageIO-FFmpeg, Pretty-MIDI.

## 7. Commit Guidelines
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`.
- **Style**: Concise subject (<72 chars), detailed body.