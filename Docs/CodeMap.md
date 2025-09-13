# ImageAI CodeMap

*Last Updated: 2025-09-13 15:57:56*

## Table of Contents

| Section | Line Number |
|---------|-------------|
| [Quick Navigation](#quick-navigation) | 19 |
| [Visual Architecture Overview](#visual-architecture-overview) | 37 |
| [Project Structure](#project-structure) | 91 |
| [Detailed Component Documentation](#detailed-component-documentation) | 183 |
| [Cross-File Dependencies](#cross-file-dependencies) | 354 |
| [Configuration Files](#configuration-files) | 424 |
| [Architecture Patterns](#architecture-patterns) | 441 |
| [Performance Considerations](#performance-considerations) | 485 |
| [Recent Changes](#recent-changes) | 509 |

## Quick Navigation

### Primary User Actions
- **Main Entry Point**: `main.py:70` - main() function that routes to CLI or GUI
- **GUI Launch**: `gui/__init__.py:7` - launch_gui() for GUI mode
- **CLI Entry**: `cli/runner.py:69` - run_cli() for command-line operations
- **Provider Factory**: `providers/__init__.py:106` - get_provider() factory for image providers
- **Configuration**: `core/config.py:13` - ConfigManager class for settings

### Key Components by Function
- **Image Generation**: `providers/base.py:8` - ImageProvider base class
- **Google Provider**: `providers/google.py:43` - GoogleProvider implementation
- **OpenAI Provider**: `providers/openai.py:25` - OpenAIProvider implementation
- **Local SD Provider**: `providers/local_sd.py:109` - LocalSDProvider implementation
- **Main Window**: `gui/main_window.py:56` - MainWindow class
- **Social Media Sizes**: `gui/social_sizes_dialog.py:66` - SocialSizesDialog (NEW)
- **Video Project**: `core/video/project.py:173` - VideoProject class

## Visual Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│                     main.py:70                          │
│                  Routes to GUI or CLI                    │
└────────────────────────────┬─────────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
┌──────────────────────┐          ┌──────────────────────┐
│      GUI Mode        │          │      CLI Mode        │
│  gui/__init__.py:7   │          │  cli/runner.py:69    │
│  - Main Window       │          │  - Parse arguments   │
│  - Dialogs           │          │  - Direct generation │
│  - Settings          │          │  - Batch processing  │
└──────────────────────┘          └──────────────────────┘
        │                                         │
        └────────────────────┬────────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │   Provider Layer     │
                  │ providers/__init__   │
                  │  - Factory pattern   │
                  │  - Provider cache    │
                  └──────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Google       │    │ OpenAI       │    │ Local SD     │
│ Provider     │    │ Provider     │    │ Provider     │
│ google.py:43 │    │ openai.py:25 │    │ local_sd.py  │
└──────────────┘    └──────────────┘    └──────────────┘
                             │
                  ┌──────────────────────┐
                  │    Core Services     │
                  │   core/__init__.py   │
                  │  - Configuration     │
                  │  - Logging          │
                  │  - Utils            │
                  │  - Security         │
                  └──────────────────────┘
                             │
                  ┌──────────────────────┐
                  │  Video Subsystem     │
                  │  core/video/*.py     │
                  │  - Project mgmt      │
                  │  - Rendering         │
                  │  - LLM sync         │
                  └──────────────────────┘
```

## Project Structure

```
ImageAI/
├── main.py                                   # 118 lines - Main entry point
├── CLAUDE.md                                 # 139 lines - Claude instructions
├── README.md                                 # 506 lines - Documentation
├── requirements.txt                          # 29 lines - Dependencies
├── imageai_codemap_agent.md                 # 437 lines - Code map agent instructions (NEW)
│
├── cli/                                      # Command-line interface
│   ├── __init__.py                          # 2 lines
│   ├── parser.py                            # 49 lines - Argument parsing
│   └── runner.py                            # 234 lines - CLI execution
│
├── core/                                     # Core functionality
│   ├── __init__.py                          # 41 lines - Core exports
│   ├── config.py                            # 190 lines - Configuration management
│   ├── constants.py                         # 26 lines - App constants
│   ├── gcloud_utils.py                      # 147 lines - Google Cloud utilities
│   ├── logging_config.py                    # 157 lines - Logging setup
│   ├── project_tracker.py                   # 42 lines - Project tracking
│   ├── prompt_enhancer.py                   # 246 lines - Prompt enhancement
│   ├── prompt_enhancer_llm.py               # 280 lines - LLM-based enhancement
│   ├── security.py                          # 210 lines - Security utilities
│   ├── utils.py                             # 352 lines - General utilities
│   └── video/                               # Video generation subsystem
│       ├── __init__.py                      # 23 lines
│       ├── config.py                        # 108 lines - Video configuration
│       ├── continuity_helper.py             # 88 lines - Image continuity
│       ├── event_store.py                   # 379 lines - Event management
│       ├── ffmpeg_renderer.py               # 426 lines - FFmpeg rendering
│       ├── image_continuity.py              # 324 lines - Continuity management
│       ├── image_generator.py               # 364 lines - Image generation
│       ├── image_processing.py              # 202 lines - Image processing
│       ├── karaoke_renderer.py              # 366 lines - Karaoke rendering
│       ├── llm_sync.py                      # 419 lines - LLM synchronization
│       ├── llm_sync_v2.py                   # 483 lines - LLM sync v2
│       ├── midi_processor.py                # 266 lines - MIDI processing
│       ├── midi_utils.py                    # 39 lines - MIDI utilities
│       ├── project.py                       # 723 lines - Project management
│       ├── project_enhancements.py          # 334 lines - Project enhancements
│       ├── project_manager.py               # 254 lines - Project manager
│       ├── prompt_engine.py                 # 853 lines - Prompt generation
│       ├── storyboard.py                    # 711 lines - Storyboard generation
│       ├── storyboard_v2.py                 # 418 lines - Storyboard v2
│       ├── thumbnail_manager.py             # 151 lines - Thumbnail management
│       └── veo_client.py                    # 373 lines - Veo API client
│
├── gui/                                      # GUI components
│   ├── __init__.py                          # 39 lines - GUI initialization
│   ├── dialog_utils.py                      # 75 lines - Dialog utilities
│   ├── dialogs.py                           # 332 lines - Dialog components
│   ├── local_sd_widget.py                   # 308 lines - Local SD widget
│   ├── main_window.py                       # 1265 lines - Main window (MODIFIED)
│   ├── model_browser.py                     # 353 lines - Model browser
│   ├── settings_widgets.py                  # 1055 lines - Settings widgets (MODIFIED)
│   ├── social_sizes_dialog.py               # 215 lines - Social media sizes (NEW)
│   ├── workers.py                           # 28 lines - Background workers
│   ├── common/                              # Common GUI utilities
│   │   ├── __init__.py                      # 1 lines
│   │   └── dialog_manager.py                # 204 lines - Dialog management
│   └── video/                               # Video GUI components
│       ├── __init__.py                      # 2 lines
│       ├── enhanced_workspace.py            # 559 lines - Enhanced workspace
│       ├── history_tab.py                   # 223 lines - History tab
│       ├── project_browser.py               # 264 lines - Project browser
│       ├── project_dialog.py                # 534 lines - Project dialogs
│       ├── video_project_tab.py             # 1053 lines - Video project tab
│       └── workspace_widget.py              # 414 lines - Workspace widget
│
├── providers/                                # Image generation providers (MODIFIED)
│   ├── __init__.py                          # 180 lines - Provider factory (MODIFIED)
│   ├── base.py                              # 39 lines - Base provider class
│   ├── google.py                            # 326 lines - Google provider (MODIFIED)
│   ├── local_sd.py                          # 444 lines - Local SD provider
│   ├── model_info.py                        # 35 lines - Model information
│   ├── openai.py                            # 226 lines - OpenAI provider
│   └── stability.py                         # 127 lines - Stability provider
│
├── Plans/                                    # Planning documents
│   ├── ImageAI-VideoProject-PRD.md          # 1603 lines - Product requirements
│   ├── ImageAI-Prompt-Enhancer-Pack/        # Prompt enhancement tools (NEW)
│   │   ├── ImageAI_Prompt_Enhancer_GPT5.md  # 297 lines
│   │   ├── image_prompt_schema.json         # 264 lines
│   │   └── prompt_presets.json              # 236 lines
│   └── social-media-image-sizes-2025.md     # 57 lines - Social media sizes
│
└── tools/                                    # Development tools
    └── generate_code_map.py                 # 251 lines - Code map generator
```

## Detailed Component Documentation

### Main Entry Point
**Path**: `main.py` - 118 lines
**Purpose**: Application entry point and import patching

#### Key Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| _patched_import() | 21 | module | Patches imports for compatibility |
| main() | 70 | int | Main entry point, routes to CLI or GUI |

### GUI Components

#### MainWindow
**Path**: `gui/main_window.py` - 1265 lines (MODIFIED)
**Purpose**: Main application window with tabs for generation, settings, templates

##### Table of Contents
| Section | Line Number |
|---------|-------------|
| Class Definition | 56 |
| Initialization | 59-96 |
| UI Creation | 135-334 |
| Menu System | 336-435 |
| Event Handlers | 437-798 |
| Image Operations | 800-1074 |
| Settings Management | 1076-1265 |

##### Complete Method Inventory
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 59 | public | None | Initialize main window |
| _init_ui() | 135 | private | None | Create UI components |
| _init_menu() | 336 | private | None | Setup menu bar |
| _create_generate_tab() | 157 | private | QWidget | Create generation tab |
| _create_settings_tab() | 221 | private | QWidget | Create settings tab |
| _create_templates_tab() | 256 | private | QWidget | Create templates tab |
| _create_help_tab() | 305 | private | QWidget | Create help tab |
| _setup_keyboard_shortcuts() | 437 | private | None | Configure keyboard shortcuts (NEW) |
| generate_image() | 473 | public | None | Start image generation |
| on_generation_done() | 517 | public | None | Handle generation completion |
| save_current_image() | 800 | public | None | Save generated image |
| copy_to_clipboard() | 834 | public | None | Copy image to clipboard |
| update_history_list() | 1076 | public | None | Update history display |

#### SocialSizesDialog (NEW Component)
**Path**: `gui/social_sizes_dialog.py` - 215 lines
**Purpose**: Dialog for selecting social media image sizes from markdown table

##### Table of Contents
| Section | Line Number |
|---------|-------------|
| Module Functions | 22-64 |
| Class Definition | 66 |
| Initialization | 69-76 |
| UI Setup | 77-111 |
| Data Loading | 112-158 |
| Event Handlers | 177-215 |

##### Module Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| _parse_markdown_table() | 22 | Tuple[List[str], List[List[str]]] | Parse markdown table |
| _extract_resolution_px() | 55 | Optional[str] | Extract WxH from text |

##### Class Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 69 | public | None | Initialize dialog |
| _init_ui() | 77 | private | None | Create UI components |
| _load_data() | 112 | private | None | Load markdown file |
| _append_row() | 159 | private | None | Add table row |
| _apply_filter() | 177 | private | None | Filter table rows |
| _on_selection_changed() | 187 | private | None | Handle selection |
| _current_row() | 195 | private | Optional[int] | Get selected row |
| _use_selected() | 201 | private | None | Accept selection |
| selected_resolution() | 213 | public | Optional[str] | Get selected size |

#### Settings Widgets (MODIFIED)
**Path**: `gui/settings_widgets.py` - 1055 lines
**Purpose**: Advanced settings components for image generation

##### Components
| Class | Line | Description |
|-------|------|-------------|
| AspectRatioSelector | 15 | Aspect ratio selection widget |
| ResolutionSelector | 324 | Resolution input widget (MODIFIED) |
| QualitySelector | 560 | Quality settings widget |
| BatchSelector | 674 | Batch size selector |
| AdvancedSettingsPanel | 730 | Advanced settings panel |
| CostEstimator | 977 | Cost estimation utility |

### Provider System

#### Provider Factory (MODIFIED)
**Path**: `providers/__init__.py` - 180 lines
**Purpose**: Factory pattern for image generation providers

##### Key Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| _get_providers() | 42 | Dict[str, Type[ImageProvider]] | Get provider registry |
| get_provider() | 106 | ImageProvider | Get or create provider instance |
| list_providers() | 150 | list[str] | List available providers |
| clear_provider_cache() | 156 | None | Clear provider cache |
| preload_provider() | 162 | None | Preload provider for performance |

#### Google Provider (MODIFIED)
**Path**: `providers/google.py` - 326 lines
**Purpose**: Google Gemini API integration

##### GoogleProvider Class
| Method | Line | Returns | Description |
|--------|------|---------|-------------|
| __init__() | 46 | None | Initialize provider |
| initialize() | 65 | None | Setup Gemini client |
| generate() | 101 | bytes | Generate image |
| test_connection() | 145 | Tuple[bool, str] | Test API connection |
| get_models() | 178 | List[str] | List available models |
| _setup_auth() | 205 | None | Configure authentication |
| _parse_response() | 245 | bytes | Parse API response |
| _handle_error() | 285 | None | Handle API errors |

### Core Services

#### ConfigManager
**Path**: `core/config.py` - 190 lines
**Purpose**: Application configuration management

##### Key Methods
| Method | Line | Returns | Description |
|--------|------|---------|-------------|
| __init__() | 15 | None | Initialize config |
| get() | 32 | Any | Get config value |
| set() | 45 | None | Set config value |
| get_api_key() | 67 | Optional[str] | Get API key for provider |
| set_api_key() | 89 | None | Store API key |
| get_config_path() | 112 | Path | Get config file path |
| save() | 134 | None | Save config to disk |
| load() | 156 | None | Load config from disk |

### Video Subsystem

#### VideoProject
**Path**: `core/video/project.py` - 723 lines
**Purpose**: Core video project management

##### Key Classes
| Class | Line | Description |
|-------|------|-------------|
| VideoProvider | 25 | Provider enumeration |
| SceneStatus | 31 | Scene status enum |
| AudioTrack | 40 | Audio track data |
| ImageVariant | 80 | Image variant data |
| Scene | 117 | Scene management |
| VideoProject | 173 | Main project class |

##### VideoProject Methods
| Method | Line | Returns | Description |
|--------|------|---------|-------------|
| __init__() | 176 | None | Initialize project |
| add_scene() | 234 | Scene | Add new scene |
| remove_scene() | 267 | bool | Remove scene |
| get_scene() | 289 | Optional[Scene] | Get scene by ID |
| save() | 345 | None | Save project to disk |
| load() | 412 | VideoProject | Load project from disk |
| export() | 489 | Dict | Export project data |
| validate() | 567 | Tuple[bool, List[str]] | Validate project |
| render() | 623 | Path | Render to video |

## Cross-File Dependencies

### State Management Flows

#### Provider Selection State
**Managed by**: `ConfigManager` (`core/config.py:13`)
**Consumed by**:
- `MainWindow` (`gui/main_window.py:66`) - UI provider selection
- `CLI Runner` (`cli/runner.py:85`) - CLI provider selection
- `Provider Factory` (`providers/__init__.py:106`) - Provider instantiation
- `GenWorker` (`gui/workers.py:10`) - Background generation

#### API Key Management
**Managed by**: `ConfigManager` (`core/config.py:67`)
**Secondary Storage**: `SecureKeyStorage` (`core/security.py:82`)
**Consumed by**:
- `MainWindow` (`gui/main_window.py:67`) - GUI key display
- `CLI Runner` (`cli/runner.py:12`) - CLI key resolution
- `All Providers` (`providers/*.py`) - API authentication

#### Generation Settings
**Managed by**: `MainWindow` (`gui/main_window.py:56`)
**Components**:
- `AspectRatioSelector` (`gui/settings_widgets.py:15`) - Aspect ratio
- `ResolutionSelector` (`gui/settings_widgets.py:324`) - Resolution input
- `QualitySelector` (`gui/settings_widgets.py:560`) - Quality settings
- `BatchSelector` (`gui/settings_widgets.py:674`) - Batch size

#### Video Project State
**Managed by**: `VideoProject` (`core/video/project.py:173`)
**Consumed by**:
- `VideoProjectTab` (`gui/video/video_project_tab.py:290`) - GUI interface
- `ProjectManager` (`core/video/project_manager.py:17`) - Project operations
- `FFmpegRenderer` (`core/video/ffmpeg_renderer.py:43`) - Video rendering
- `EventStore` (`core/video/event_store.py:122`) - Event tracking

### Service Dependencies

#### Image Generation Pipeline
```
MainWindow.generate_image() [gui/main_window.py:473]
    → GenWorker [gui/workers.py:10]
        → get_provider() [providers/__init__.py:106]
            → GoogleProvider.generate() [providers/google.py:101]
                or OpenAIProvider.generate() [providers/openai.py:78]
                or LocalSDProvider.generate() [providers/local_sd.py:234]
        → auto_save_images() [core/utils.py:260]
        → write_image_sidecar() [core/utils.py:194]
```

#### Video Rendering Pipeline
```
VideoProjectTab.render_video() [gui/video/video_project_tab.py:567]
    → VideoGenerationThread [gui/video/video_project_tab.py:27]
        → VideoProject.render() [core/video/project.py:623]
            → FFmpegRenderer.render() [core/video/ffmpeg_renderer.py:89]
                → ImageGenerator.generate_scene() [core/video/image_generator.py:123]
                → KaraokeRenderer.render() [core/video/karaoke_renderer.py:145]
```

### Import Dependencies

#### Core Module Exports
**File**: `core/__init__.py` - 41 lines
**Exports**:
- Configuration: `ConfigManager`, `APP_NAME`, `VERSION`
- Utils: `sanitize_filename`, `scan_disk_history`, `images_output_dir`
- Image operations: `write_image_sidecar`, `read_image_sidecar`, `auto_save_images`
- Provider utils: `default_model_for_provider`, `detect_image_extension`

## Configuration Files

### Application Configuration
| File | Purpose | Format |
|------|---------|--------|
| `~/.config/ImageAI/config.json` | User settings | JSON |
| `~/.config/ImageAI/api_keys.json` | Encrypted API keys | JSON |
| `requirements.txt` | Python dependencies | pip format |
| `.env` | Environment variables | KEY=VALUE |

### Project Files
| File | Purpose | Format |
|------|---------|--------|
| `*.imageai_project` | Video project files | JSON |
| `*.json` (sidecar) | Image metadata | JSON |
| `Plans/*.md` | Planning documents | Markdown |

## Architecture Patterns

### Design Patterns Used

#### Factory Pattern
- **Implementation**: `providers/__init__.py:106` - get_provider()
- **Purpose**: Dynamic provider instantiation
- **Benefits**: Extensible provider system

#### Singleton Pattern with Caching
- **Implementation**: `providers/__init__.py:106` - Provider cache
- **Purpose**: Reuse provider instances
- **Benefits**: Reduced initialization overhead

#### Observer Pattern
- **Implementation**: Qt Signals/Slots throughout GUI
- **Purpose**: Event-driven UI updates
- **Benefits**: Decoupled components

#### Strategy Pattern
- **Implementation**: `ImageProvider` base class (`providers/base.py:8`)
- **Purpose**: Interchangeable generation algorithms
- **Benefits**: Provider flexibility

### Development Guidelines

#### Adding New Providers
1. Create provider class inheriting from `ImageProvider`
2. Implement required methods: `generate()`, `test_connection()`
3. Register in `providers/__init__.py:_get_providers()`
4. Add configuration in `core/constants.py`

#### GUI Component Guidelines
- Use PySide6 for all GUI components
- Implement keyboard shortcuts for common actions
- Provide status feedback via status bar
- Handle errors with dialog_utils functions

#### Error Handling
- Use `ErrorLogger` class (`core/logging_config.py:143`)
- Show user-friendly messages via `dialog_utils`
- Log detailed errors for debugging
- Implement graceful degradation

## Performance Considerations

### Optimization Strategies

#### Provider Preloading
- Preload providers on startup (`gui/main_window.py:99`)
- Cache provider instances (`providers/__init__.py:106`)
- Lazy load heavy dependencies

#### Image History Management
- Scan disk on startup (`gui/main_window.py:73`)
- Cache metadata in memory
- Limit history to 500 items (`core/utils.py:288`)

#### Video Rendering
- Use FFmpeg for efficient encoding
- Process frames in parallel where possible
- Cache generated images for re-use

#### GUI Responsiveness
- Use QThread for long operations (`gui/workers.py:10`)
- Show progress indicators
- Process events during long operations

## Recent Changes

### 2025-09-13 Updates
**Commit**: d8da575 - Add social media sizes dialog and keyboard shortcuts

#### New Features
1. **Social Media Sizes Dialog** (`gui/social_sizes_dialog.py`)
   - Parse markdown table of social media image sizes
   - Searchable, filterable table interface
   - Direct resolution selection for generation

2. **Keyboard Shortcuts** (`gui/main_window.py:437`)
   - Ctrl+G: Generate image
   - Ctrl+S: Save current image
   - Ctrl+O: Open project
   - Ctrl+N: New project
   - F1: Show help

3. **Resolution Selector Enhancement** (`gui/settings_widgets.py:324`)
   - Added "Social Media Sizes" button
   - Integration with SocialSizesDialog
   - Auto-populate resolution from selection

4. **Prompt Enhancement Tools** (`Plans/ImageAI-Prompt-Enhancer-Pack/`)
   - New prompt enhancement documentation
   - JSON schemas for prompt structure
   - Preset prompt templates

#### Modified Files
- `gui/main_window.py` - Added keyboard shortcuts
- `gui/settings_widgets.py` - Enhanced resolution selector
- `providers/__init__.py` - Improved provider caching
- `providers/google.py` - Enhanced error handling
- `requirements.txt` - Updated dependencies

### File Size Changes
- `gui/main_window.py`: 1185 → 1265 lines
- `gui/settings_widgets.py`: 1012 → 1055 lines
- `providers/__init__.py`: 168 → 180 lines
- `providers/google.py`: 312 → 326 lines

### API Changes
- `ResolutionSelector` now has `show_social_sizes_dialog()` method
- `SocialSizesDialog.selected_resolution()` returns WxH string
- Provider factory enhanced with better error messages