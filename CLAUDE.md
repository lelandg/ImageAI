# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Code Navigation

**IMPORTANT**: Use the comprehensive code map at `Docs/CodeMap.md` for navigating this codebase. It provides:
- Exact line numbers for all classes, methods, and functions (format: `file.py:123`)
- Visual architecture diagram showing component relationships
- Cross-module dependency tracking
- Quick navigation to primary entry points

To update the code map, follow the instructions in `imageai_codemap_agent.md`.

## Debug Files

When the application exits, it automatically copies debug files to the current directory:
- **`./imageai_current.log`** - Copy of the most recent log file with all errors and debug info
- **`./imageai_current_project.json`** - Copy of the last loaded/saved project file
- Use these when you need to check the current log or project file for errors.

These files are invaluable for debugging issues. Always check them first when investigating errors.

## Project Overview

**ImageAI** - A Python desktop GUI and CLI application for AI image generation using Google Gemini and OpenAI (DALL·E) APIs. The application securely stores API keys and provides both a Qt-based GUI interface and a command-line interface for generating images.

## Key Commands

### Setup and Installation
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Launch GUI (default)
python main.py

# CLI mode with help
python main.py -h

# Test API key (Google/default)
python main.py -t

# Test OpenAI API key
python main.py --provider openai -t

# Generate image (Google)
python main.py -p "Your prompt here" -o output.png

# Generate image (OpenAI DALL·E)
python main.py --provider openai -m dall-e-3 -p "Your prompt" -o output.png
```

## Architecture and Structure

### Main Components

The codebase is now modularized (no longer a single file). See `Docs/CodeMap.md` for complete navigation with line numbers.

**Primary Entry Points:**
- `main.py:69` - main() function that routes to CLI or GUI
- `gui/__init__.py:7` - launch_gui() for GUI mode
- `cli/runner.py` - run_cli() for command-line operations
- `providers/__init__.py` - get_provider() factory for image providers

**Core Systems:**
- **GUI**: `gui/main_window.py` - MainWindow class with tabs for Generate, Settings, Templates, Help
- **Providers**: Base class at `providers/base.py`, implementations for Google, OpenAI, Stability, Local SD
- **Video Project**: Complex subsystem in `core/video/` for lyric-synced video generation
- **Configuration**: `core/config.py` - ConfigManager for settings and API keys

### Key Design Patterns

- **Multi-provider Support**: Provider parameter (`--provider google|openai`) switches between API backends
- **API Key Management**: Per-provider key storage with multiple resolution methods (CLI > file > config > env)
- **Cross-platform Paths**: Uses `Path` objects and platform-specific user directories
- **Async Generation**: GUI uses `QThread` worker for non-blocking image generation
- **Metadata Sidecars**: Each generated image gets a `.json` sidecar file with prompt and generation details

### Data Storage Locations

Configuration and generated images are stored in platform-specific user directories:
- **Windows**: `%APPDATA%\ImageAI\`
- **macOS**: `~/Library/Application Support/ImageAI/`
- **Linux**: `~/.config/ImageAI/`

### Provider-Specific Implementation

- **Google Gemini**: Uses `google.genai` client with base64 image decoding
- **OpenAI**: Uses `openai.OpenAI` client with direct URL image responses
- Model defaults: Gemini uses `gemini-2.5-flash-image-preview`, OpenAI uses `dall-e-3`

### GUI Features

- **Generate Tab**: Main interface for prompt input and image generation
- **Settings Tab**: API key management and provider selection
- **Templates Tab**: Predefined prompts with placeholder substitution
- **Help Tab**: Embedded README documentation
- **History**: In-session tracking of generated images with disk scanning on startup

## Important Notes

- The application is now fully modularized with separate packages for GUI, CLI, providers, and core functionality
- PySide6 is required for GUI but optional for CLI usage
- API keys are never committed to source control
- Images auto-save with sanitized filenames based on prompts
- Template system supports placeholder substitution for prompt generation
- When navigating code, always check `Docs/CodeMap.md` first for quick symbol location

## Version Management

**IMPORTANT**: When incrementing the version, see `.claude/VERSION_LOCATIONS.md` for all locations that need updating:
1. `core/constants.py` - Primary version definition
2. `README.md` - Version display and changelog
3. The VERSION_LOCATIONS.md file documents all locations

## Future Development Plans

The `Plans/` directory contains documentation for upcoming features:
- **GoogleCloudAuth.md**: Implementation plan for Google Cloud authentication via Application Default Credentials
- **NewProviders.md**: Comprehensive plan for adding additional AI image providers (Stability AI, Adobe Firefly, etc.) and features like image editing, masking, and upscaling
- **ImageAI-VideoProject-PRD.md**: Comprehensive product requirements for video generation features

## Code Map Maintenance

When the code map needs updating:
1. Check last update: `head -5 Docs/CodeMap.md`
2. Run the code map agent: Follow instructions in `imageai_codemap_agent.md`
3. The agent will:
   - Check git history for changes since last update
   - Extract all symbols with exact line numbers
   - Update cross-module dependencies
   - Generate visual architecture diagram

## Development Notes

- When implementing new features, keep file sizes reasonable for your use
- For testing Python code:
  - **In WSL/Linux bash**: Use `source /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/activate`
  - **In PowerShell**: Use `.\.venv\Scripts\Activate.ps1` (this is the primary environment)
- Never add files to git