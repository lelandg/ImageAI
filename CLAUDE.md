# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

1. **main.py** - Single-file application containing all functionality:
   - **CLI Interface** (`run_cli()`, `build_arg_parser()`) - Handles command-line arguments and operations
   - **GUI Interface** (`MainWindow`, `ExamplesDialog`, `GenWorker`) - PySide6/Qt-based desktop interface
   - **Provider Abstraction** - Supports multiple providers (Google Gemini, OpenAI) with unified interface
   - **Configuration Management** - Cross-platform config storage in user directories
   - **Image Generation** - Handles both text and image generation with provider-specific implementations

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

- The application is a single-file Python script (`main.py`) for simplicity
- PySide6 is required for GUI but optional for CLI usage
- API keys are never committed to source control
- Images auto-save with sanitized filenames based on prompts
- Template system supports placeholder substitution for prompt generation

## Future Development Plans

The `Plans/` directory contains documentation for upcoming features:
- **GoogleCloudAuth.md**: Implementation plan for Google Cloud authentication via Application Default Credentials
- **NewProviders.md**: Comprehensive plan for adding additional AI image providers (Stability AI, Adobe Firefly, etc.) and features like image editing, masking, and upscaling
- When implementing new features, keep file sizes reasonable for your use.
- For testing Python code use 'source /mnt/d/Documents/Code/GitHub/ImageAI/.venv/bin/activate' first