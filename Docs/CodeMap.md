# ImageAI CodeMap

*Last Updated: 2025-09-13 21:55:04*

## Table of Contents

| Section | Line Number |
|---------|-------------|
| [Quick Navigation](#quick-navigation) | 19 |
| [Visual Architecture Overview](#visual-architecture-overview) | 39 |
| [Project Structure](#project-structure) | 90 |
| [Detailed Component Documentation](#detailed-component-documentation) | 145 |
| [Cross-File Dependencies](#cross-file-dependencies) | 325 |
| [Configuration Files](#configuration-files) | 361 |
| [Architecture Patterns](#architecture-patterns) | 375 |
| [Performance Considerations](#performance-considerations) | 406 |
| [Recent Changes](#recent-changes) | 421 |

## Quick Navigation

### Primary User Actions
- **Main Entry Point**: `main.py:70` - main() function that routes to CLI or GUI
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
- **Main Window**: `gui/main_window.py:60` - MainWindow class
- **Image Crop Dialog**: `gui/image_crop_dialog.py:151` - ImageCropDialog (NEW)
- **Social Media Sizes**: `gui/social_sizes_tree_dialog.py:66` - SocialSizesTreeDialog (NEW)
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
        │  - prompt_enhancer.py (AI prompts)      │
        └─────────────────────────────────────────┘
                           │
                           ▼
        ┌─────────────────────────────────────────┐
        │          GUI Components                 │
        │  - main_window.py:60 (MainWindow)       │
        │  - image_crop_dialog.py:151 (Cropping)  │
        │  - social_sizes_tree_dialog.py:66       │
        │  - tabs/* (Generate/Settings/etc)       │
        └─────────────────────────────────────────┘
```

## Project Structure

```
ImageAI/
├── main.py                     # Entry point (70 lines)
├── cli/
│   ├── __init__.py            # CLI package init
│   └── runner.py              # CLI runner (147 lines)
├── core/
│   ├── __init__.py
│   ├── config.py              # Configuration manager (222 lines)
│   ├── constants.py           # App constants (23 lines)
│   ├── exceptions.py          # Custom exceptions (20 lines)
│   ├── image_utils.py         # Image processing utilities (235 lines)
│   ├── prompt_enhancer.py     # Prompt enhancement (144 lines)
│   ├── utils.py               # General utilities (354 lines)
│   └── video/
│       ├── __init__.py
│       ├── config.py          # Video config (71 lines)
│       ├── exceptions.py      # Video exceptions (15 lines)
│       ├── fonts.py           # Font management (147 lines)
│       ├── generator.py       # Video generation (1024 lines)
│       ├── lyrics_parser.py   # Lyrics parsing (282 lines)
│       ├── project.py         # Video project (468 lines)
│       └── transitions.py     # Video transitions (141 lines)
├── gui/
│   ├── __init__.py            # GUI package init (33 lines)
│   ├── image_crop_dialog.py   # Image cropping dialog (409 lines) [NEW]
│   ├── main_window.py         # Main window (1653 lines)
│   ├── social_sizes_tree_dialog.py  # Social media sizes (293 lines) [NEW]
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── generate_tab.py    # Generation tab (1341 lines)
│   │   ├── help_tab.py        # Help documentation (136 lines)
│   │   ├── settings_tab.py    # Settings management (496 lines)
│   │   └── templates_tab.py   # Template management (451 lines)
│   └── workers/
│       ├── __init__.py
│       └── image_generator.py # Background generation (92 lines)
├── providers/
│   ├── __init__.py            # Provider factory (154 lines)
│   ├── base.py                # Base provider class (49 lines)
│   ├── google.py              # Google Gemini provider (333 lines)
│   ├── local_sd.py            # Local Stable Diffusion (271 lines)
│   ├── openai.py              # OpenAI DALL-E provider (168 lines)
│   └── stability.py           # Stability AI provider (209 lines)
├── Plans/                      # Development plans
│   ├── GoogleCloudAuth.md
│   ├── ImageAI-VideoProject-PRD.md
│   ├── NewProviders.md
│   └── social-media-image-sizes-2025.md
└── Docs/
    └── CodeMap.md             # This file
```

## Detailed Component Documentation

### Main Entry Point
**Path**: `main.py` - 113 lines
**Purpose**: Application entry point and import patching

| Function | Line | Description |
|----------|------|-------------|
| _patched_import() | 21 | Patches imports for PySide6 compatibility |
| main() | 70 | Routes to GUI or CLI based on arguments |

### GUI Package

#### MainWindow Class
**Path**: `gui/main_window.py` - 1653 lines
**Purpose**: Main application window

| Section | Line Number |
|---------|-------------|
| Class Definition | 60 |
| Constructor | 62 |
| UI Setup | 134 |
| Event Handlers | 524 |
| File Operations | 867 |
| History Management | 1234 |

| Method | Line | Access | Description |
|--------|------|--------|-------------|
| __init__() | 62 | public | Initialize main window |
| setup_ui() | 134 | private | Create UI components |
| load_project() | 867 | public | Load project file |
| save_project() | 923 | public | Save project file |
| update_history() | 1234 | private | Update history list |

#### ImageCropDialog Class [NEW]
**Path**: `gui/image_crop_dialog.py` - 409 lines
**Purpose**: Interactive image cropping dialog with marching ants selection

| Class | Line | Description |
|-------|------|-------------|
| MarchingAntsRect | 17 | Animated selection rectangle |
| ImageCropView | 46 | Custom graphics view for cropping |
| ImageCropDialog | 151 | Main cropping dialog |

| Method | Line | Class | Description |
|--------|------|-------|-------------|
| __init__() | 20 | MarchingAntsRect | Initialize animated rectangle |
| create_pen() | 31 | MarchingAntsRect | Create dashed pen for animation |
| update_offset() | 37 | MarchingAntsRect | Animate marching ants |
| keyPressEvent() | 63 | ImageCropView | Handle keyboard shortcuts |
| mousePressEvent() | 102 | ImageCropView | Start crop selection |
| mouseMoveEvent() | 125 | ImageCropView | Update crop selection |
| mouseReleaseEvent() | 145 | ImageCropView | Finish crop selection |
| setup_ui() | 166 | ImageCropDialog | Build dialog interface |
| scale_and_position_image() | 242 | ImageCropDialog | Position image in view |
| update_info() | 291 | ImageCropDialog | Update crop information |
| accept_crop() | 374 | ImageCropDialog | Apply crop operation |
| get_result() | 404 | ImageCropDialog | Return cropped image |

#### SocialSizesTreeDialog Class [NEW]
**Path**: `gui/social_sizes_tree_dialog.py` - 293 lines
**Purpose**: Tree-based dialog for selecting social media image sizes

| Function/Class | Line | Description |
|----------------|------|-------------|
| _parse_markdown_table() | 22 | Parse markdown table to data |
| _extract_resolution_px() | 55 | Extract resolution from text |
| SocialSizesTreeDialog | 66 | Main dialog class |

| Method | Line | Access | Description |
|--------|------|--------|-------------|
| __init__() | 69 | public | Initialize dialog |
| _init_ui() | 79 | private | Setup UI components |
| _load_data() | 113 | private | Load social media sizes data |
| _apply_filter() | 192 | private | Filter tree by search text |
| _on_selection_changed() | 223 | private | Handle selection changes |
| _use_selected() | 239 | private | Apply selected resolution |
| selected_resolution() | 286 | public | Get selected resolution |

### Provider System

#### Base Provider
**Path**: `providers/base.py` - 49 lines
**Purpose**: Abstract base class for all image providers

| Method | Line | Type | Description |
|--------|------|------|-------------|
| generate() | 14 | abstract | Generate image from prompt |
| test_connection() | 29 | abstract | Test API connection |
| get_models() | 37 | abstract | List available models |

#### Google Provider
**Path**: `providers/google.py` - 333 lines
**Purpose**: Google Gemini image generation

| Method | Line | Access | Description |
|--------|------|--------|-------------|
| __init__() | 59 | public | Initialize with API key |
| configure() | 84 | public | Setup Gemini client |
| generate() | 113 | public | Generate image with Gemini |
| _process_resolution() | 167 | private | Handle resolution and cropping |
| _crop_to_resolution() | 234 | private | Apply aspect ratio cropping |
| test_connection() | 289 | public | Verify API connectivity |

#### Stability AI Provider
**Path**: `providers/stability.py` - 209 lines
**Purpose**: Stability AI image generation

| Method | Line | Access | Description |
|--------|------|--------|-------------|
| __init__() | 18 | public | Initialize provider |
| generate() | 45 | public | Generate image via API |
| _get_style_preset() | 123 | private | Map style to API preset |
| test_connection() | 178 | public | Test API connection |

### Core Utilities

#### ConfigManager
**Path**: `core/config.py` - 222 lines
**Purpose**: Application configuration and API key management

| Method | Line | Access | Description |
|--------|------|--------|-------------|
| __init__() | 15 | public | Initialize config manager |
| load() | 43 | public | Load configuration |
| save() | 78 | public | Save configuration |
| get_api_key() | 112 | public | Retrieve API key |
| set_api_key() | 145 | public | Store API key |

#### Image Utilities
**Path**: `core/image_utils.py` - 235 lines
**Purpose**: Image processing and manipulation functions

| Function | Line | Description |
|----------|------|-------------|
| auto_crop_solid_borders() | 11 | Remove solid color borders |
| crop_to_aspect_ratio() | 127 | Crop image to target aspect ratio |
| detect_aspect_ratio() | 196 | Detect image aspect ratio |

#### General Utilities
**Path**: `core/utils.py` - 354 lines
**Purpose**: General helper functions

| Function | Line | Description |
|----------|------|-------------|
| sanitize_filename() | 14 | Clean filename for filesystem |
| read_key_file() | 46 | Read API key from file |
| generate_timestamp() | 134 | Create timestamp string |
| format_file_size() | 144 | Format bytes to human readable |
| parse_image_size() | 161 | Parse resolution string |
| images_output_dir() | 180 | Get output directory |
| detect_image_extension() | 214 | Detect image format |
| auto_save_images() | 260 | Save images with metadata |
| scan_disk_history() | 288 | Scan for existing images |

### GUI Tabs

#### Generate Tab
**Path**: `gui/tabs/generate_tab.py` - 1341 lines
**Purpose**: Main image generation interface

| Section | Line Number |
|---------|-------------|
| Class Definition | 52 |
| UI Setup | 89 |
| Generation Logic | 456 |
| History Management | 823 |
| Event Handlers | 1067 |

#### Settings Tab
**Path**: `gui/tabs/settings_tab.py` - 496 lines
**Purpose**: Application settings and API configuration

| Method | Line | Description |
|--------|------|-------------|
| setup_ui() | 45 | Create settings interface |
| load_settings() | 178 | Load from config |
| save_settings() | 234 | Save to config |
| test_api_key() | 389 | Verify API key works |

## Cross-File Dependencies

### State Management Flows

#### Configuration State
**Managed by**: `ConfigManager` (`core/config.py:13`)
**Consumed by**:
- `MainWindow` (`gui/main_window.py:62`) - Loads/saves settings
- `SettingsTab` (`gui/tabs/settings_tab.py:45`) - UI for configuration
- All providers (`providers/*.py`) - API key retrieval
- `GenerateTab` (`gui/tabs/generate_tab.py:52`) - Generation settings

#### Image Generation Flow
**Initiated by**: `GenerateTab` (`gui/tabs/generate_tab.py:456`)
**Flow**:
1. User input in GenerateTab
2. Worker thread (`gui/workers/image_generator.py:32`)
3. Provider factory (`providers/__init__.py:106`)
4. Specific provider (`providers/google.py:113` or others)
5. Image processing (`core/image_utils.py`)
6. Auto-save (`core/utils.py:260`)
7. UI update in GenerateTab

#### History Management
**Managed by**: `GenerateTab` (`gui/tabs/generate_tab.py:823`)
**Data flow**:
- Disk scan: `core/utils.py:288` (scan_disk_history)
- Metadata: `core/utils.py:194` (write_image_sidecar)
- Display: `GenerateTab` history list widget
- Filtering: Original/cropped toggle in GenerateTab

#### Social Media Sizes
**Source**: `Plans/social-media-image-sizes-2025.md`
**UI**: `gui/social_sizes_tree_dialog.py:66`
**Consumer**: `GenerateTab` - populates resolution field

## Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| config.json | User settings | Platform-specific user directory |
| .env | API keys (optional) | Project root |
| requirements.txt | Python dependencies | Project root |
| settings.local.json | Local development settings | .claude/ directory |

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
- **Example**: Image generation progress updates

#### Template Method Pattern
- **Implementation**: `providers/base.py:8` (ImageProvider)
- **Purpose**: Consistent interface for all providers

#### Strategy Pattern
- **Implementation**: Provider system
- **Purpose**: Interchangeable image generation backends

### Development Guidelines

- **Provider Implementation**: Extend `ImageProvider` base class
- **GUI Components**: Use PySide6 with proper signal/slot connections
- **File Operations**: Use `pathlib.Path` for cross-platform compatibility
- **API Keys**: Never hardcode, use ConfigManager
- **Error Handling**: Catch and display user-friendly messages
- **Threading**: Use QThread for long-running operations
- **Image Formats**: Support PNG, JPEG, WebP detection
- **Metadata**: Always write JSON sidecar files

## Performance Considerations

- **Lazy Loading**: GUI only loads when needed (not imported for CLI)
- **Background Generation**: Worker threads prevent UI freezing
- **Image Caching**: History scans are throttled and limited
- **Resolution Processing**: Smart cropping for aspect ratios
- **File I/O**: Batch operations where possible
- **Memory Management**: Process images in chunks for large files

### Optimization Points
- History scan limited to 500 most recent items
- Thumbnail generation for history display
- Async API calls in worker threads
- Efficient markdown parsing for social media sizes

## Recent Changes

### 2025-09-13 Updates (Since 15:57:56)

#### New Features
1. **Image Crop Dialog** (`gui/image_crop_dialog.py`)
   - Interactive cropping with marching ants selection
   - Keyboard shortcuts for navigation
   - Real-time preview and info display

2. **Social Media Sizes Dialog** (`gui/social_sizes_tree_dialog.py`)
   - Tree-based organization by platform
   - Search/filter functionality
   - Persistent expansion state

3. **Enhanced Image Processing**
   - Auto-crop solid borders (`core/image_utils.py:11`)
   - Aspect ratio cropping (`core/image_utils.py:127`)
   - Aspect ratio detection (`core/image_utils.py:196`)

4. **Resolution Handling**
   - Google provider now supports aspect ratio cropping
   - Original vs cropped image toggle in history
   - Smart resolution processing for all providers

#### Modified Components
- `providers/google.py`: Added resolution processing and cropping
- `providers/stability.py`: Expanded style presets
- `gui/main_window.py`: Integration with new dialogs
- `core/utils.py`: Enhanced utility functions

#### Bug Fixes
- Fixed aspect ratio handling in Google provider
- Improved history filtering for original/cropped images
- Enhanced error handling in image processing

### Version Information
Current Version: 1.4.0 (as of constants.py)