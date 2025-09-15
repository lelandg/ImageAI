# ImageAI CodeMap

*Last Updated: 2025-09-14 19:54:08*

## Table of Contents

| Section | Line Number |
|---------|-------------|
| [Quick Navigation](#quick-navigation) | 19 |
| [Visual Architecture Overview](#visual-architecture-overview) | 43 |
| [Project Structure](#project-structure) | 99 |
| [Detailed Component Documentation](#detailed-component-documentation) | 170 |
| [Cross-File Dependencies](#cross-file-dependencies) | 369 |
| [Configuration Files](#configuration-files) | 428 |
| [Architecture Patterns](#architecture-patterns) | 444 |
| [Performance Considerations](#performance-considerations) | 483 |
| [Recent Changes](#recent-changes) | 503 |

## Quick Navigation

### Primary User Actions
- **Main Entry Point**: `main.py:69` - main() function that routes to CLI or GUI
- **GUI Launch**: `gui/__init__.py:7` - launch_gui() for GUI mode
- **CLI Entry**: `cli/runner.py:69` - run_cli() for command-line operations
- **Provider Factory**: `providers/__init__.py:106` - get_provider() factory for image providers
- **Configuration**: `core/config.py:13` - ConfigManager class for settings

### Key Components by Function
- **Image Generation**: `providers/base.py:8` - ImageProvider base class
- **Google Provider**: `providers/google.py:57` - GoogleProvider implementation
- **OpenAI Provider**: `providers/openai.py:25` - OpenAIProvider implementation
- **Local SD Provider**: `providers/local_sd.py:109` - LocalSDProvider implementation
- **Stability Provider**: `providers/stability.py:16` - StabilityProvider implementation
- **Main Window**: `gui/main_window.py:64` - MainWindow class (4959 lines)
- **Prompt Generation**: `gui/prompt_generation_dialog.py:501` - PromptGenerationDialog (NEW)
- **Prompt Questions**: `gui/prompt_question_dialog.py:386` - PromptQuestionDialog (NEW)
- **Image Upscaling**: `core/upscaling.py:39` - upscale_image() function (NEW)
- **Find Dialog**: `gui/find_dialog.py:11` - FindDialog for text search (NEW)
- **Package Installer**: `gui/install_dialog.py:127` - InstallDialog for dependencies (NEW)
- **LLM Utilities**: `gui/llm_utils.py:15` - LLMResponseParser and helpers (NEW)
- **Video Project**: `core/video/project.py:173` - VideoProject class

## Visual Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│                     main.py:69                          │
│                  Routes to GUI or CLI                    │
└────────────────────────────┬─────────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
┌──────────────────────┐          ┌──────────────────────┐
│      GUI Mode        │          │      CLI Mode        │
│  gui/__init__.py:7   │          │  cli/runner.py:69    │
│   PySide6 Desktop    │          │  Command Line Tool   │
└──────────┬───────────┘          └──────────┬───────────┘
           │                                  │
           └──────────────┬───────────────────┘
                          ▼
        ┌─────────────────────────────────────────┐
        │          Provider System                │
        │      providers/__init__.py:106          │
        │         Factory Pattern                 │
        └──────────────────┬──────────────────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     ▼                     ▼                     ▼
┌─────────────┐   ┌──────────────┐   ┌──────────────────┐
│   Google    │   │    OpenAI    │   │  Stability AI    │
│ google.py:57│   │ openai.py:25 │   │stability.py:16   │
└─────────────┘   └──────────────┘   └──────────────────┘
                           │
                           ▼
        ┌─────────────────────────────────────────┐
        │           Core Utilities                │
        │  - config.py:13 (ConfigManager)         │
        │  - utils.py (Helper functions)          │
        │  - image_utils.py (Image processing)    │
        │  - prompt_enhancer_llm.py (LLM prompts) │
        │  - upscaling.py (AI upscaling) [NEW]    │
        │  - package_installer.py (Deps) [NEW]    │
        └─────────────────────────────────────────┘
                           │
                           ▼
        ┌─────────────────────────────────────────┐
        │          GUI Components                 │
        │  - main_window.py:64 (MainWindow)       │
        │  - prompt_generation_dialog.py [NEW]    │
        │  - prompt_question_dialog.py [NEW]      │
        │  - find_dialog.py (Search) [NEW]        │
        │  - install_dialog.py (Setup) [NEW]      │
        │  - upscaling_widget.py [NEW]            │
        │  - llm_utils.py (LLM helpers) [NEW]     │
        └─────────────────────────────────────────┘
```

## Project Structure

```
ImageAI/
├── main.py                            # Entry point (113 lines)
├── cli/
│   ├── __init__.py                   # CLI package init
│   └── runner.py                     # CLI runner (147 lines)
├── core/
│   ├── __init__.py
│   ├── config.py                     # Configuration manager (222 lines)
│   ├── constants.py                  # App constants (23 lines)
│   ├── exceptions.py                 # Custom exceptions (20 lines)
│   ├── image_utils.py                # Image processing utilities (235 lines)
│   ├── package_installer.py          # Package installation (470 lines) [NEW]
│   ├── prompt_enhancer.py            # Prompt enhancement (144 lines)
│   ├── prompt_enhancer_llm.py        # LLM prompt enhancement (modified)
│   ├── upscaling.py                  # Image upscaling utilities (274 lines) [NEW]
│   ├── utils.py                      # General utilities (354 lines)
│   └── video/
│       ├── __init__.py
│       ├── config.py                 # Video config (modified)
│       ├── exceptions.py             # Video exceptions (15 lines)
│       ├── fonts.py                  # Font management (147 lines)
│       ├── generator.py              # Video generation (1024 lines)
│       ├── lyrics_parser.py          # Lyrics parsing (282 lines)
│       ├── project.py                # Video project (468 lines)
│       ├── prompt_engine.py          # Prompt engine (modified)
│       └── transitions.py            # Video transitions (141 lines)
├── gui/
│   ├── __init__.py                   # GUI package init (33 lines)
│   ├── enhanced_prompt_dialog.py     # Enhanced prompt dialog (modified)
│   ├── find_dialog.py                # Text search dialog (258 lines) [NEW]
│   ├── image_crop_dialog.py          # Image cropping dialog (409 lines)
│   ├── install_dialog.py             # Package installation UI (505 lines) [NEW]
│   ├── llm_utils.py                  # LLM helper utilities (281 lines) [NEW]
│   ├── main_window.py                # Main window (4959 lines, expanded)
│   ├── prompt_generation_dialog.py   # AI prompt generation (1090 lines) [NEW]
│   ├── prompt_question_dialog.py     # AI prompt questions (896 lines) [NEW]
│   ├── settings_widgets.py           # Settings components (modified)
│   ├── social_sizes_tree_dialog.py   # Social media sizes (293 lines)
│   ├── upscaling_widget.py           # Upscaling UI widget (288 lines) [NEW]
│   ├── workers.py                    # Background workers (modified)
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── generate_tab.py           # Generation tab (1341 lines)
│   │   ├── help_tab.py               # Help documentation (136 lines)
│   │   ├── settings_tab.py           # Settings management (496 lines)
│   │   └── templates_tab.py          # Template management (451 lines)
│   └── workers/
│       ├── __init__.py
│       └── image_generator.py        # Background generation (92 lines)
├── providers/
│   ├── __init__.py                   # Provider factory (154 lines)
│   ├── base.py                       # Base provider class (49 lines)
│   ├── google.py                     # Google Gemini provider (modified)
│   ├── local_sd.py                   # Local Stable Diffusion (271 lines)
│   ├── openai.py                     # OpenAI DALL-E provider (168 lines)
│   └── stability.py                  # Stability AI provider (209 lines)
├── Plans/                             # Development plans
│   ├── GoogleCloudAuth.md
│   ├── GPT_Image_API_ImageAI.md      # [NEW]
│   ├── ImageAI-VideoProject-PRD.md
│   ├── ImageAI_OpenAI_vs_Gemini.md   # [NEW]
│   ├── NewProviders.md
│   ├── litellm_gpt5_conversation/    # [NEW]
│   └── social-media-image-sizes-2025.md
└── Docs/
    └── CodeMap.md                    # This file
```

## Detailed Component Documentation

### Main Entry Point
**Path**: `main.py` - 113 lines
**Purpose**: Application entry point and import patching

| Function | Line | Description |
|----------|------|-------------|
| _patched_import() | 21 | Patches imports for PySide6 compatibility |
| main() | 69 | Routes to GUI or CLI based on arguments |

### GUI Package

#### MainWindow Class (EXPANDED)
**Path**: `gui/main_window.py` - 4959 lines (significantly expanded)
**Purpose**: Main application window with enhanced functionality

| Section | Line Number |
|---------|-------------|
| Class Definition | 64 |
| Constructor | 67 |
| UI Initialization | 298 |
| Menu Setup | 336 |
| Generate Tab | 373 |
| Settings Tab | 816 |
| Help Tab | 1069 |
| Templates Tab | 2073 |
| History Tab | 2129 |

| Method | Line | Access | Description |
|--------|------|--------|-------------|
| __init__() | 67 | public | Initialize main window |
| _init_ui() | 298 | private | Create UI components |
| _init_menu() | 336 | private | Setup menu bar |
| _init_generate_tab() | 373 | private | Setup generation interface |
| _init_settings_tab() | 816 | private | Setup settings interface |
| _init_help_tab() | 1069 | private | Setup help documentation |
| _open_social_sizes_dialog() | 789 | private | Open social media sizes selector |
| _enhance_prompt() | 2998 | private | Launch prompt enhancement |
| _open_prompt_generator() | 3033 | private | Open AI prompt generator [NEW] |
| _open_prompt_question() | 3039 | private | Open prompt questions dialog [NEW] |
| _open_find_dialog() | 3049 | private | Open text search dialog [NEW] |
| _on_upscaling_changed() | 3057 | private | Handle upscaling settings [NEW] |
| _generate() | 3108 | private | Main generation logic |
| _process_image_for_resolution_with_original() | 3356 | private | Process with original backup |
| _save_project() | 3896 | private | Save project file |
| _load_project() | 3972 | private | Load project file |
| closeEvent() | 4163 | public | Handle window close |

#### PromptGenerationDialog Class [NEW]
**Path**: `gui/prompt_generation_dialog.py` - 1090 lines
**Purpose**: AI-powered prompt generation with LLM integration

| Class | Line | Description |
|-------|------|-------------|
| LLMWorker | 21 | Worker thread for LLM operations |
| PromptGenerationDialog | 501 | Main dialog for prompt generation |

| Method | Line | Class | Description |
|--------|------|-------|-------------|
| __init__() | 28 | LLMWorker | Initialize worker with parameters |
| run() | 44 | LLMWorker | Execute LLM generation |
| __init__() | 501 | PromptGenerationDialog | Initialize dialog |
| init_ui() | 518 | PromptGenerationDialog | Build dialog interface |
| load_llm_settings() | 693 | PromptGenerationDialog | Load LLM configuration |
| generate_prompts() | 745 | PromptGenerationDialog | Start prompt generation |
| on_generation_finished() | 854 | PromptGenerationDialog | Handle generation results |
| save_to_history() | 971 | PromptGenerationDialog | Save generation history |
| restore_last_session() | 1070 | PromptGenerationDialog | Restore previous session |

#### PromptQuestionDialog Class [NEW]
**Path**: `gui/prompt_question_dialog.py` - 896 lines
**Purpose**: Interactive AI-driven prompt refinement through questions

| Class | Line | Description |
|-------|------|-------------|
| QuestionWorker | 20 | Worker for LLM question generation |
| PromptQuestionDialog | 386 | Main question dialog |

| Method | Line | Class | Description |
|--------|------|-------|-------------|
| __init__() | 20 | QuestionWorker | Initialize question worker |
| run() | 44 | QuestionWorker | Generate questions via LLM |
| __init__() | 386 | PromptQuestionDialog | Initialize dialog |
| init_ui() | 402 | PromptQuestionDialog | Build UI components |
| generate_questions() | 567 | PromptQuestionDialog | Start question generation |
| on_questions_generated() | 712 | PromptQuestionDialog | Handle generated questions |
| accept_answers() | 834 | PromptQuestionDialog | Process user answers |

#### FindDialog Class [NEW]
**Path**: `gui/find_dialog.py` - 258 lines
**Purpose**: Text search functionality for QTextEdit widgets

| Method | Line | Access | Description |
|--------|------|--------|-------------|
| __init__() | 14 | public | Initialize find dialog |
| init_ui() | 26 | private | Setup search interface |
| on_search_text_changed() | 78 | private | Handle search text changes |
| find_next() | 112 | public | Find next occurrence |
| find_previous() | 134 | public | Find previous occurrence |
| highlight_matches() | 156 | private | Highlight all matches |
| clear_highlights() | 189 | private | Clear search highlights |
| keyPressEvent() | 234 | public | Handle keyboard shortcuts |

#### UpscalingSelector Widget [NEW]
**Path**: `gui/upscaling_widget.py` - 288 lines
**Purpose**: UI widget for selecting upscaling options

| Method | Line | Access | Description |
|--------|------|--------|-------------|
| __init__() | 17 | public | Initialize upscaling selector |
| init_ui() | 29 | private | Build upscaling UI |
| on_method_changed() | 89 | private | Handle method selection |
| check_realesrgan_availability() | 134 | private | Check AI upscaling support |
| install_realesrgan() | 178 | private | Launch installation dialog |
| get_settings() | 234 | public | Return current settings |
| set_settings() | 256 | public | Apply settings |

#### InstallDialog Class [NEW]
**Path**: `gui/install_dialog.py` - 505 lines
**Purpose**: Package installation UI for Real-ESRGAN dependencies

| Class | Line | Description |
|-------|------|-------------|
| DiskSpaceWidget | 28 | Disk space indicator |
| InstallDialog | 127 | Main installation dialog |
| CompletionDialog | 428 | Installation completion dialog |

| Method | Line | Class | Description |
|--------|------|-------|-------------|
| __init__() | 127 | InstallDialog | Initialize dialog |
| init_ui() | 146 | InstallDialog | Build installation UI |
| start_installation() | 230 | InstallDialog | Begin package installation |
| download_model() | 305 | InstallDialog | Download AI model weights |
| on_installation_finished() | 279 | InstallDialog | Handle completion |
| restart_application() | 396 | InstallDialog | Restart app after install |

### Core Utilities

#### LLM Utilities [NEW]
**Path**: `gui/llm_utils.py` - 281 lines
**Purpose**: Shared utilities for LLM integration

| Class | Line | Description |
|-------|------|-------------|
| LLMResponseParser | 15 | Parse and clean LLM responses |
| DialogStatusConsole | 127 | Status console widget for dialogs |
| LiteLLMHandler | 201 | LiteLLM integration handler |

| Method | Line | Class | Description |
|--------|------|-------|-------------|
| parse_json() | 23 | LLMResponseParser | Extract JSON from LLM response |
| clean_markdown() | 67 | LLMResponseParser | Remove markdown formatting |
| extract_list() | 89 | LLMResponseParser | Extract list from text |
| __init__() | 129 | DialogStatusConsole | Initialize console widget |
| append_message() | 145 | DialogStatusConsole | Add message to console |
| setup_litellm() | 208 | LiteLLMHandler | Configure LiteLLM |
| get_completion() | 234 | LiteLLMHandler | Get LLM completion |

#### Upscaling Module [NEW]
**Path**: `core/upscaling.py` - 274 lines
**Purpose**: Image upscaling with multiple methods including AI

| Class/Function | Line | Description |
|----------------|------|-------------|
| UpscalingMethod | 31 | Enum for upscaling methods |
| upscale_image() | 39 | Main upscaling function |
| _upscale_lanczos() | 87 | Lanczos resampling method |
| _upscale_realesrgan() | 134 | AI upscaling with Real-ESRGAN |
| _upscale_stability_api() | 189 | Stability AI upscaling API |
| check_realesrgan_available() | 234 | Check if Real-ESRGAN installed |
| get_model_path() | 256 | Get path to model weights |

#### Package Installer [NEW]
**Path**: `core/package_installer.py` - 470 lines
**Purpose**: Manage installation of optional dependencies

| Class/Function | Line | Description |
|----------------|------|-------------|
| PackageInstaller | 16 | Thread for package installation |
| ModelDownloader | 203 | Thread for model download |
| check_disk_space() | 318 | Verify available disk space |
| get_installed_packages() | 345 | List installed packages |
| detect_nvidia_gpu() | 374 | Check for NVIDIA GPU |
| get_realesrgan_packages() | 412 | Get required packages list |
| get_model_info() | 453 | Get model download info |

### Provider System Updates

#### Google Provider (Modified)
**Path**: `providers/google.py` - Modified
**Changes**: Added aspect ratio cropping and resolution processing

| Method | Line | Description |
|--------|------|-------------|
| _process_resolution() | 167 | Handle resolution with cropping |
| _crop_to_resolution() | 234 | Apply aspect ratio cropping |
| _get_aspect_ratio() | 289 | Calculate aspect ratio |

### Cross-File Dependencies

### State Management Flows

#### LLM Integration Flow [NEW]
**Initiated by**: User action in MainWindow
**Flow**:
1. User clicks "Generate with AI" or "Enhance with AI"
2. Dialog opened (`PromptGenerationDialog` or `PromptQuestionDialog`)
3. LLM configuration loaded from `ConfigManager`
4. Worker thread started (`LLMWorker` or `QuestionWorker`)
5. LiteLLM setup via `LiteLLMHandler` (`gui/llm_utils.py:201`)
6. API call to configured LLM provider
7. Response parsed by `LLMResponseParser` (`gui/llm_utils.py:15`)
8. Results displayed in dialog's status console
9. Selected prompt returned to MainWindow

#### Upscaling Flow [NEW]
**Initiated by**: User enabling upscaling in Generate tab
**Flow**:
1. User selects upscaling method in `UpscalingSelector`
2. If Real-ESRGAN selected, availability checked
3. If not available, `InstallDialog` launched
4. During generation, image passed to `upscale_image()` (`core/upscaling.py:39`)
5. Method-specific upscaling applied
6. Upscaled image returned to generation worker

#### Package Installation Flow [NEW]
**Initiated by**: Missing optional dependencies
**Flow**:
1. Dependency check in component (e.g., upscaling)
2. `InstallDialog` launched (`gui/install_dialog.py:127`)
3. Disk space verified (`core/package_installer.py:318`)
4. `PackageInstaller` thread started
5. Packages installed via pip
6. Model weights downloaded if needed
7. Application restart offered

#### Configuration State
**Managed by**: `ConfigManager` (`core/config.py:13`)
**Consumed by**:
- `MainWindow` (`gui/main_window.py:67`) - Loads/saves settings
- All providers (`providers/*.py`) - API key retrieval
- LLM dialogs - API keys for LLM providers
- Upscaling - Settings persistence

#### Image Generation Flow
**Initiated by**: Generate button in MainWindow
**Flow**:
1. User input in MainWindow
2. Optional prompt enhancement via LLM
3. Worker thread (`gui/workers.py`)
4. Provider factory (`providers/__init__.py:106`)
5. Specific provider (`providers/google.py` or others)
6. Optional upscaling (`core/upscaling.py:39`)
7. Image processing (`core/image_utils.py`)
8. Auto-save (`core/utils.py:260`)
9. UI update in MainWindow

## Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| config.json | User settings | Platform-specific user directory |
| .env | API keys (optional) | Project root |
| requirements.txt | Python dependencies | Project root |
| settings.local.json | Local development settings | .claude/ directory |
| install_log.txt | Installation history | Project root [NEW] |
| weights/*.pth | AI model weights | weights/ directory [NEW] |

### Platform-Specific Paths
- **Windows**: `%APPDATA%\ImageAI\`
- **macOS**: `~/Library/Application Support/ImageAI/`
- **Linux**: `~/.config/ImageAI/`

## Architecture Patterns

### Design Patterns Used

#### Factory Pattern
- **Implementation**: `providers/__init__.py:106` (get_provider)
- **Purpose**: Dynamic provider instantiation based on user selection

#### Observer Pattern
- **Implementation**: Qt signals/slots throughout GUI
- **Example**: Image generation progress updates, LLM streaming

#### Worker Thread Pattern
- **Implementation**: Multiple worker classes for async operations
- **Examples**: `LLMWorker`, `QuestionWorker`, `PackageInstaller`, `ModelDownloader`

#### Strategy Pattern
- **Implementation**: Provider system, Upscaling methods
- **Purpose**: Interchangeable backends for generation and upscaling

#### Parser Pattern [NEW]
- **Implementation**: `LLMResponseParser` (`gui/llm_utils.py:15`)
- **Purpose**: Robust parsing of varied LLM outputs

### Development Guidelines

- **Provider Implementation**: Extend `ImageProvider` base class
- **LLM Integration**: Use `LiteLLMHandler` for consistency
- **Async Operations**: Always use QThread workers for long tasks
- **Status Display**: Include `DialogStatusConsole` in LLM dialogs
- **Error Handling**: Graceful fallbacks for LLM failures
- **Package Management**: Use `PackageInstaller` for optional deps
- **GUI Components**: Use PySide6 with proper signal/slot connections
- **File Operations**: Use `pathlib.Path` for cross-platform compatibility
- **API Keys**: Never hardcode, use ConfigManager
- **Threading**: Use QThread for long-running operations
- **Image Formats**: Support PNG, JPEG, WebP detection
- **Metadata**: Always write JSON sidecar files

## Performance Considerations

- **Lazy Loading**: GUI only loads when needed (not imported for CLI)
- **Background Generation**: Worker threads prevent UI freezing
- **LLM Streaming**: Real-time updates in status consoles
- **Conditional Imports**: Optional dependencies imported only when needed
- **Image Caching**: History scans are throttled and limited
- **Resolution Processing**: Smart cropping for aspect ratios
- **Model Loading**: AI models loaded once and cached
- **File I/O**: Batch operations where possible
- **Memory Management**: Process images in chunks for large files

### Optimization Points
- History scan limited to 500 most recent items
- Thumbnail generation for history display
- Async API calls in worker threads
- Efficient markdown parsing for help content
- LLM response parsing with multiple fallback strategies
- GPU acceleration for Real-ESRGAN when available

## Recent Changes

### 2025-09-14 Updates (Since 2025-09-13 21:55:04)

#### New Major Features

1. **AI-Powered Prompt Generation System**
   - `gui/prompt_generation_dialog.py` - Full LLM integration for prompt creation
   - `gui/prompt_question_dialog.py` - Interactive Q&A for prompt refinement
   - `gui/llm_utils.py` - Shared utilities for LLM operations
   - Support for multiple LLM providers via LiteLLM

2. **Advanced Image Upscaling**
   - `core/upscaling.py` - Multiple upscaling methods
   - `gui/upscaling_widget.py` - UI for upscaling configuration
   - Real-ESRGAN AI upscaling support
   - Lanczos and Stability API options

3. **Package Installation System**
   - `core/package_installer.py` - Automated dependency management
   - `gui/install_dialog.py` - User-friendly installation UI
   - GPU detection and appropriate package selection
   - Model weight download management

4. **Enhanced Search Functionality**
   - `gui/find_dialog.py` - Find/replace in text widgets
   - Case sensitive and whole word options
   - Keyboard shortcut support (Ctrl+F)

5. **Help System Improvements**
   - Enhanced markdown rendering in help tab
   - Screenshot gallery integration
   - Better navigation with forward/back buttons
   - Search functionality within help content

#### Modified Components
- `gui/main_window.py`: Major expansion (1653 → 4959 lines)
  - Added LLM prompt generation integration
  - Enhanced help tab with better navigation
  - Integrated upscaling controls
  - Added find dialog support
- `providers/google.py`: Enhanced with aspect ratio support
- `gui/settings_widgets.py`: Added upscaling configuration
- `gui/workers.py`: Modified for upscaling support
- `core/prompt_enhancer_llm.py`: Enhanced LLM integration
- `core/video/config.py`: Video configuration updates
- `core/video/prompt_engine.py`: Prompt engine improvements

#### Infrastructure Changes
- Added `weights/` directory for AI model storage
- New `Plans/` subdirectories for LLM examples
- Installation logging to `install_log.txt`
- Enhanced error handling throughout

#### Bug Fixes
- Improved LLM response parsing robustness
- Better handling of empty LLM responses
- Fixed configuration access in dialogs
- Enhanced error recovery in package installation

### Version Information
Current Version: 1.4.0+ (check constants.py for exact version)