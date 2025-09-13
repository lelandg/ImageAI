# ImageAI Code Map Generator Agent

## Purpose
Generate a comprehensive, navigable code map for the ImageAI project that enables quick file and symbol location with precise line numbers.

## Instructions

You are tasked with creating or updating the code map at `/mnt/d/Documents/Code/GitHub/ImageAI/Docs/CodeMap.md`. Follow these steps:

### 1. Initial Analysis
- Check the current "Last Updated" timestamp in the existing CodeMap.md
- Run `git log --since="[last_update_date]" --name-status` to identify changed files
- Scan the project structure to identify all Python files and key directories

### 2. Generate the Code Map Structure

#### Header (REQUIRED)
```markdown
# ImageAI Code Map

*Last Updated: YYYY-MM-DD HH:MM:SS*
```
Use exact format with 24-hour time.

#### Main Table of Contents (REQUIRED)
Create a table with line numbers for EVERY major section:
```markdown
## Table of Contents

| Section | Line Number |
|---------|-------------|
| [Quick Navigation](#quick-navigation) | XX |
| [Visual Architecture](#visual-architecture) | XX |
| [Project Structure](#project-structure) | XX |
| [Core Modules](#core-modules) | XX |
| [GUI Components](#gui-components) | XX |
| [Providers](#providers) | XX |
| [Video System](#video-system) | XX |
| [CLI Components](#cli-components) | XX |
| [Cross-Module Dependencies](#cross-module-dependencies) | XX |
| [Configuration Files](#configuration-files) | XX |
| [Development Guidelines](#development-guidelines) | XX |
```

#### Quick Navigation Section
```markdown
## Quick Navigation

### Primary Entry Points
- **Main Application**: `main.py:66` - main() function
- **GUI Launch**: `gui/__init__.py:7` - launch_gui()
- **CLI Parser**: `cli/parser.py:XX` - build_arg_parser()
- **CLI Runner**: `cli/runner.py:XX` - run_cli()

### Key Configuration
- **App Constants**: `core/constants.py:XX` - Version, paths
- **Config Manager**: `core/config.py:XX` - Settings management
- **Logging Setup**: `core/logging_config.py:XX` - Log configuration

### Provider System
- **Provider Factory**: `providers/__init__.py:XX` - get_provider()
- **Base Provider**: `providers/base.py:XX` - ImageProvider class
- **Google Provider**: `providers/google.py:XX` - GoogleProvider
- **OpenAI Provider**: `providers/openai.py:XX` - OpenAIProvider
```

#### Visual Architecture
```markdown
## Visual Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     main.py                              │
│                  Entry Point & CLI                        │
└─────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
┌──────────────────┐                    ┌──────────────────┐
│       GUI        │                    │       CLI        │
│  gui/__init__.py │                    │  cli/runner.py   │
│  MainWindow      │                    │  cli/parser.py   │
└──────────────────┘                    └──────────────────┘
        │                                           │
        └─────────────────────┬─────────────────────┘
                              ▼
                  ┌──────────────────┐
                  │    Providers     │
                  │ Google, OpenAI,  │
                  │  Stability, etc. │
                  └──────────────────┘
                              │
                              ▼
                  ┌──────────────────┐
                  │      Core        │
                  │ Config, Utils,   │
                  │ Security, Video  │
                  └──────────────────┘
```
```

### 3. For Each Python File

#### File Header Format
```markdown
### [Module Name]
**Path**: `path/to/file.py` - [XXX lines]
**Purpose**: [Brief description]

#### Table of Contents
| Section | Line |
|---------|------|
| Imports | 1 |
| Constants | XX |
| Classes | XX |
| Functions | XX |
```

#### Class Documentation
```markdown
#### Class: ClassName
**Line**: XX
**Purpose**: [Description]

**Properties**:
| Name | Line | Type | Access | Description |
|------|------|------|--------|-------------|
| property_name | XX | str | private | Description |

**Methods**:
| Method | Line | Returns | Async | Description |
|--------|------|---------|-------|-------------|
| __init__() | XX | None | No | Constructor |
| method_name() | XX | type | Yes/No | Description |
```

#### Function Documentation
```markdown
#### Functions
| Function | Line | Returns | Async | Description |
|----------|------|---------|-------|-------------|
| function_name | XX | type | Yes/No | Description |
```

### 4. Cross-Module Dependencies

```markdown
## Cross-Module Dependencies

### Provider System
**Base**: `providers/base.py:XX` - ImageProvider
**Implementations**:
- `providers/google.py` imports from `providers/base.py`
- `providers/openai.py` imports from `providers/base.py`

**Factory**: `providers/__init__.py:XX`
**Used by**:
- `main.py:XX` - CLI image generation
- `gui/main_window.py:XX` - GUI provider selection
- `gui/workers.py:XX` - Background generation

### Configuration Flow
**Source**: `core/config.py:XX` - ConfigManager
**Consumers**:
- `providers/*` - API key retrieval
- `gui/main_window.py` - Settings persistence
- `cli/runner.py` - CLI configuration
```

### 5. Special Sections for ImageAI

#### Video Project System
Document the complex video generation subsystem:
```markdown
### Video Project System
**Core**: `core/video/project.py` - VideoProject class
**Manager**: `core/video/project_manager.py` - ProjectManager
**Components**:
- Storyboard: `core/video/storyboard.py`
- LLM Sync: `core/video/llm_sync.py`
- FFmpeg Renderer: `core/video/ffmpeg_renderer.py`
- Image Generator: `core/video/image_generator.py`
```

#### GUI Component Hierarchy
```markdown
### GUI Components
**Main Window**: `gui/main_window.py:XX` - MainWindow class
**Tabs**:
- Generate Tab: Lines XX-XX
- Settings Tab: Lines XX-XX
- Templates Tab: Lines XX-XX
- Help Tab: Lines XX-XX

**Dialogs**:
- Examples: `gui/dialogs.py:XX` - ExamplesDialog
- Social Sizes: `gui/social_sizes_dialog.py:XX` - SocialSizesDialog
- Model Browser: `gui/model_browser.py:XX` - ModelBrowserDialog
```

### 6. Important Notes

1. **Line Numbers**: ALWAYS include accurate line numbers using format `file.py:123`
2. **File Sizes**: Show as line counts like `main.py - 201 lines`
3. **Updates**: When updating, check git history since last update timestamp
4. **Completeness**: Document ALL public classes, methods, and functions
5. **Navigation**: Ensure every section has a line number in the main TOC
6. **Python-Specific**: Focus on classes, methods, decorators, and async functions

### 7. Validation Checklist

Before completing the code map, verify:
- [ ] Timestamp is in exact format: YYYY-MM-DD HH:MM:SS
- [ ] Main TOC has line numbers for all sections
- [ ] Every file shows total line count
- [ ] All classes have method/property tables with line numbers
- [ ] Cross-dependencies are documented
- [ ] Visual architecture diagram is included
- [ ] Quick Navigation section lists all entry points

### 8. Example Entry

```markdown
### Main Application
**Path**: `main.py` - 201 lines
**Purpose**: Application entry point with CLI/GUI launch logic

#### Table of Contents
| Section | Line |
|---------|------|
| Imports | 1 |
| Protobuf Patch | 16 |
| Global Variables | 66 |
| main() Function | 69 |
| Entry Point | 200 |

#### Functions
| Function | Line | Returns | Async | Description |
|----------|------|---------|-------|-------------|
| _patched_import | 21 | module | No | Import hook for protobuf compatibility |
| main | 69 | None | No | Main entry point, handles CLI/GUI routing |
```

## Usage

When asked to update the code map:
1. Check current timestamp: `head -5 /mnt/d/Documents/Code/GitHub/ImageAI/Docs/CodeMap.md`
2. Get recent changes: `git -C /mnt/d/Documents/Code/GitHub/ImageAI log --since="[timestamp]" --name-status`
3. For each changed file, extract symbols with line numbers
4. Update the CodeMap.md with new information
5. Verify all cross-references are accurate
6. Update the timestamp to current time

This agent ensures the code map is comprehensive, navigable, and provides quick access to any symbol in the codebase.