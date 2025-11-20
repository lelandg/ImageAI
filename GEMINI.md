# ImageAI Project Context

## Project Overview
**ImageAI** is a comprehensive desktop application and CLI tool for AI image and video generation. It integrates multiple AI providers (Google Gemini, OpenAI DALL·E, Stability AI, Local Stable Diffusion) into a unified interface. The project features advanced capabilities for video creation (including MIDI synchronization and karaoke), a professional layout engine for publications, and sophisticated prompt engineering tools.

## Code Navigation & Debugging
*   **Code Map**: Use `Docs/CodeMap.md` for navigating the codebase. It contains exact line numbers and component relationships.
    *   **Currency Check**: Always check the "Last Updated" timestamp in `Docs/CodeMap.md`. If older than 7 days, offer to update it.
*   **Debug Files**: On exit, the app copies debug info to the current directory:
    *   `./imageai_current.log`: Most recent log file.
    *   `./imageai_current_project.json`: Last loaded/saved project.
*   **Logs**: Check `logs/` (or platform-specific log dir) for `imageai_YYYYMMDD.log`.

## Tech Stack
*   **Language:** Python 3.9+
*   **GUI Framework:** PySide6 (Qt for Python)
*   **AI Providers**:
    *   **Google:** `google-genai`, `google-cloud-aiplatform` (Gemini, Imagen 3, Veo)
    *   **OpenAI:** `openai` (DALL·E 3, GPT-4/5)
    *   **Stability AI:** REST API
    *   **Local:** `diffusers`, `torch` (Optional for Local Stable Diffusion)
    *   **LLM Integration:** `litellm` (Unified interface)
*   **Video/Audio**:
    *   `moviepy`: Video assembly
    *   `imageio-ffmpeg`: FFmpeg bindings
    *   `pretty-midi`, `mido`: MIDI processing and timing extraction
*   **Data:** JSON for configuration and presets.

## Project Structure

### Core Directories
*   **`main.py`**: Application entry point (handles both CLI and GUI launch).
*   **`cli/`**: Command-line interface logic (`parser.py`, `runner.py`).
*   **`gui/`**: PySide6 graphical user interface.
    *   `main_window.py`: Main application window.
    *   `video/`: Video project UI components.
    *   `layout/`: Publication layout engine UI.
    *   `dialogs.py`, `settings_widgets.py`: Reusable UI components.
*   **`core/`**: Business logic and utilities.
    *   `config.py`: Configuration management.
    *   `image_utils.py`: Image processing.
    *   `llm_models.py`: LLM interaction logic.
    *   `video/`: Video generation and processing logic.
*   **`providers/`**: Base class (`base.py`) and implementations for Google, OpenAI, Stability, etc.
*   **`data/`**: JSON files for the Prompt Builder (artists, styles, metadata).
*   **`Docs/`**: Extensive documentation (guides, architectural reviews).
*   **`scripts/`**: Utility scripts (e.g., `generate_tags.py` for metadata).

### Key Design Patterns
*   **Multi-provider Support**: Swappable backends via `providers/`.
*   **Async Generation**: GUI uses `QThread` workers for non-blocking operations.
*   **Metadata Sidecars**: Generated images get a `.json` sidecar with prompt/gen details.

## Setup & Installation

1.  **Environment**: Create a Python virtual environment.
    ```powershell
    python -m venv .venv
    # Activate virtual environment (PowerShell)
    .\.venv\Scripts\Activate.ps1
    ```
    *   **WSL/Linux Note**: Use `source .venv/bin/activate` (or `.venv_linux` if separate).
2.  **Dependencies**:
    ```powershell
    pip install -r requirements.txt
    # Optional: For Local Stable Diffusion
    pip install -r requirements-local-sd.txt
    ```
3.  **Configuration**:
    *   Config file stored in `%APPDATA%\ImageAI\` (Windows) or `~/.config/ImageAI/` (Linux).
    *   API keys can be set via GUI Settings or CLI args.

## Usage

### GUI Mode
Launch the full desktop interface:
```powershell
python main.py
```

### CLI Mode
Generate images directly from the terminal:
```powershell
# Basic generation
python main.py -p "A cyberpunk city" -o output.png

# Specify provider and model
python main.py --provider openai -m dall-e-3 -p "A cute cat" -o cat.png

# Video generation
python main.py video --in lyrics.txt --midi song.mid --out video.mp4
```

## Agent Operational Guidelines

### Work Procedures
*   **Agent Usage**: Use an agent when one is available for a task (e.g., code-reviewer, code-map-updater).
*   **Code Review**: When reviewing code, always verify assumptions with actual code, read files before claiming problems, check for existing implementations, distinguish actual vs. potential issues, and consider modern best practices.
*   **File Creation**: When agents report creating files, always verify the file exists afterward. If not, create it directly using the Write tool with the agent's output.

### Plan File Management (CRITICAL)
*   Plan files in `Plans/` or `Notes/` directories must be kept current.
*   **Updates**: Immediately update after completing/starting tasks, creating/modifying files, discovering blockers, or changing approach.
*   **Required Info**: Mark task completion status (✅, ⏳, ❌, ⏸️), add timestamps, document deliverables (files created/modified with line counts), update progress percentages, add implementation notes, and cross-reference files.
*   **Auto-Update Triggers**: Automatically update plan files when completing `TodoWrite` tasks, creating new files, finishing phases, encountering errors, or resuming a plan.
*   **Recovery**: When resuming after interruption, read the plan file first, review status, check deliverables, resume from the last checkpoint, and immediately update the plan.

### File Navigation Best Practices
*   **Always use full paths**: Never use `cd` commands; stay in the current working directory and use absolute paths (e.g., `/mnt/d/Documents/Code/GitHub/ProjectName/file.py`).
*   **Batch Operations**: Call multiple tools in parallel when searching different locations.
*   **Tool-Specific**: Use `Grep(path=...)`, `Glob(path=...)`, `Read(file_path=...)`, `LS(path=...)`, `Edit(file_path=...)`.
*   **Bash Commands**: Use absolute paths (e.g., `python3 /absolute/path/script.py`, `git -C /absolute/path status`).

### Credentials and Secrets Management (CRITICAL)
*   **Never store API keys, passwords, or credentials in project directories**.
*   **Standard Pattern**: Store in platform-specific user config directories *outside the project*:
    *   **Windows**: `%APPDATA%\Roaming\{AppName}\config.json`
    *   **macOS**: `~/Library/Application Support/{AppName}/config.json`
    *   **Linux**: `~/.config/{AppName}/config.json`
*   **Implementation**: Use a `UserConfigManager` to handle loading/saving from these paths.
*   **`.gitignore`**: Update `.gitignore` to block common secret patterns (`.env*`, `config.json`, `*.key`, etc.).

### Screenshots and Analysis Guidelines
*   **Location**: Screenshots are stored via the `_screenshots` symlink (e.g., `/mnt/e/Pictures/Screenshots/2025`).
*   **Most Recent**: If I refer to "screenshot", look at the newest one by timestamp (`ls -lt _screenshots/*.png | head -1`).
*   **Multiple**: For "# screenshots", consider the # newest, analyzing the newest first.
*   **Correlation**: Use timestamps in logs to correlate screenshots with log entries.

### User Preferences
*   Always allow the user to run `sudo` commands.
*   Only perform `git` commands that are read-only.
*   All errors must be logged.

## LLM Integration Guidelines

### Logging & Error Handling
*   **Log Everything**: Show all request details (provider, model, temperature, prompts) and full responses in both log file and console.
*   **Console Output**: Display generated/enhanced prompts with clear formatting.
*   **Graceful Failure**: Handle empty responses and provide fallback content.

### Google Gemini Image Generation
*   **Model**: Use `gemini-2.5-flash-image` (production). Avoid `gemini-2.5-flash-image-preview`.
*   **Aspect Ratio**: Set via `image_config={'aspect_ratio': '4:3'}`, NOT in prompt text.
*   **Prompting**: DO NOT add dimensions like "(1024x768)" to the prompt text.
*   **Supported Ratios**: 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.
*   **Scaling**: For targets > 1024px, scale proportionally so max is 1024, then upscale.

## Development Notes
*   **Python Environments**: I have PyQt6 installed in Python for PowerShell (3.12). For WSL, use `python3` and `.venv_linux`.
*   **Code Style**: Follow existing Python conventions.
*   **Testing**: Run `python migrate_config.py --dry-run` to test config changes safely.
*   **Metadata**: Use `scripts/generate_tags.py` to regenerate prompt builder metadata.
*   **Version Management**: When incrementing version, update `core/constants.py` and `README.md`. See `.claude/VERSION_LOCATIONS.md`.
