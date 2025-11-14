# ImageAI - Complete Code Map

*Last Updated: 2025-11-13 11:16:32*

This comprehensive code map provides complete navigation for the ImageAI codebase, with exact line numbers for all classes, methods, and key functions. All line numbers are current as of the last update timestamp.

## Table of Contents

| Section | Line Number |
|---------|-------------|
| [Quick Navigation](#quick-navigation) | 11 |
| [Visual Architecture Overview](#visual-architecture-overview) | 29 |
| [Project Structure](#project-structure) | 83 |
| [Detailed Component Documentation](#detailed-component-documentation) | 129 |
| [Cross-File Dependencies](#cross-file-dependencies) | 1872 |
| [Configuration Files](#configuration-files) | 1994 |
| [Architecture Patterns](#architecture-patterns) | 2032 |
| [Development Guidelines](#development-guidelines) | 2080 |

## Quick Navigation

### Primary Entry Points
- **Main Entry**: `main.py:73` - main() function that routes to CLI or GUI
- **GUI Launch**: `gui/__init__.py:7` - launch_gui() for GUI mode
- **CLI Runner**: `cli/runner.py:15` - run_cli() for command-line operations
- **Provider Factory**: `providers/__init__.py:8` - get_provider() for image providers

### Key User Actions
- **Generate Image**: `gui/main_window.py:1582` - generate_image() method
- **Open Prompt Builder**: `gui/main_window.py:1235` - open_prompt_builder() method
- **Search Wikimedia**: `gui/wikimedia_search_dialog.py:156` - WikimediaSearchDialog class
- **Manage Settings**: `gui/main_window.py:2851` - save_settings() method
- **View History**: `gui/history_widget.py:17` - DialogHistoryWidget class

## Visual Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Main Entry Point                          │
│                    main.py:73 - main()                          │
└────────────────────────┬─────────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────────┐
        ▼                                     ▼
┌──────────────────────────┐        ┌──────────────────────────┐
│     GUI Interface        │        │    CLI Interface         │
│  gui/__init__.py:7       │        │  cli/runner.py:15        │
│  - MainWindow            │        │  - Command parser        │
│  - Dialogs & Widgets     │        │  - Direct generation     │
└──────────────────────────┘        └──────────────────────────┘
        │                                     │
        └────────────────┬────────────────────┘
                         ▼
         ┌──────────────────────────────────────┐
         │        Provider System               │
         │    providers/base.py:8               │
         │  ┌────────────────────────────┐     │
         │  │ Google (Gemini)            │     │
         │  │ OpenAI (DALL-E)            │     │
         │  │ Stability AI               │     │
         │  │ Ollama (Local)             │     │
         │  │ Midjourney                 │     │
         │  └────────────────────────────┘     │
         └──────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────────┐
        ▼                ▼                    ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Core Systems │ │ GUI Components│ │ Video Subsystem  │
│              │ │               │ │                  │
│ - Config     │ │ - Prompt      │ │ - Project        │
│ - Security   │ │   Builder     │ │ - Storyboard     │
│ - Logging    │ │ - History     │ │ - FFmpeg Render  │
│ - Utils      │ │ - Settings    │ │ - Veo Client     │
│              │ │ - Reference   │ │ - LLM Sync       │
└──────────────┘ └──────────────┘ └──────────────────┘
                         │
         ┌──────────────────────────────────────┐
         │     New Features (2025)              │
         │  ┌────────────────────────────┐     │
         │  │ Semantic Search            │     │
         │  │ - TagSearcher              │     │
         │  │ - PresetLoader             │     │
         │  └────────────────────────────┘     │
         │  ┌────────────────────────────┐     │
         │  │ Wikimedia Integration      │     │
         │  │ - WikimediaClient          │     │
         │  │ - Search Dialog            │     │
         │  └────────────────────────────┘     │
         │  ┌────────────────────────────┐     │
         │  │ Reference Images           │     │
         │  │ - Image Compositor         │     │
         │  │ - Multi-image support      │     │
         │  └────────────────────────────┘     │
         └──────────────────────────────────────┘
```

## Project Structure

```
ImageAI/
├── main.py                     # Main entry point
├── cli/                        # Command-line interface
│   ├── __init__.py
│   ├── parser.py               # Argument parsing
│   └── runner.py               # CLI execution
├── core/                       # Core functionality
│   ├── config.py               # Configuration management
│   ├── constants.py            # Application constants
│   ├── logging_config.py       # Logging setup
│   ├── preset_loader.py        # Preset management (NEW)
│   ├── prompt_data_loader.py   # Prompt data loading (NEW)
│   ├── tag_searcher.py         # Semantic search (NEW)
│   ├── wikimedia_client.py     # Wikimedia API client (NEW)
│   ├── reference/              # Reference image system (NEW)
│   │   ├── image_compositor.py # Image composition
│   │   └── imagen_reference.py # Reference types
│   └── video/                  # Video subsystem
│       ├── project.py          # Project management
│       ├── storyboard.py       # Storyboard generation
│       ├── llm_sync.py         # LLM synchronization
│       ├── ffmpeg_renderer.py  # Video rendering
│       └── veo_client.py       # Veo API client
├── gui/                        # GUI components
│   ├── __init__.py             # GUI launcher
│   ├── main_window.py          # Main application window
│   ├── prompt_builder.py       # Prompt Builder dialog (NEW)
│   ├── history_widget.py       # History widget (ENHANCED)
│   ├── wikimedia_search_dialog.py # Wikimedia search (NEW)
│   ├── image_preview_popup.py  # Image preview (NEW)
│   ├── flow_layout.py          # Flow layout widget (NEW)
│   ├── reference_selection_dialog.py # Reference selector (NEW)
│   └── video/                  # Video GUI components
├── providers/                  # Image generation providers
│   ├── base.py                 # Abstract base class
│   ├── google.py               # Google Gemini provider
│   ├── openai.py               # OpenAI DALL-E provider
│   ├── stability.py            # Stability AI provider
│   ├── ollama.py               # Ollama local provider (NEW)
│   └── midjourney.py           # Midjourney provider
├── data/                       # Data files
│   └── prompts/                # Prompt data (NEW)
│       ├── metadata.json       # Semantic metadata
│       ├── presets.json        # Preset configurations
│       ├── artists.json        # Artist styles
│       ├── styles.json         # Style definitions
│       └── moods.json          # Mood descriptors
└── scripts/                    # Utility scripts
    └── generate_tags.py        # Tag generation script (NEW)
```

## Detailed Component Documentation

### Main Application Entry (`main.py`)
**Path**: `main.py` - 243 lines
**Purpose**: Application entry point with protobuf patching and routing

| Section | Line | Description |
|---------|------|-------------|
| Environment Setup | 14-17 | Sets TensorFlow, FFmpeg, Qt logging levels |
| Protobuf Patching | 26-61 | Patches protobuf compatibility issues |
| Main Function | 73-180 | Routes to CLI or GUI based on arguments |
| Setup Logging | 181-243 | Configures application logging |

### GUI Components

#### MainWindow (`gui/main_window.py`)
**Path**: `gui/main_window.py` - 3284 lines
**Purpose**: Primary application window with tabs and controls

| Class/Method | Line | Description |
|-------------|------|-------------|
| **ThumbnailCache** | 22 | Caches image thumbnails |
| └─ get() | 29 | Retrieves cached thumbnail |
| └─ set() | 37 | Stores thumbnail in cache |
| └─ clear() | 43 | Clears cache |
| **GCloudStatusChecker** | 145 | Checks gcloud status in background |
| └─ run() | 152 | Thread execution |
| **MainWindow** | 213 | Main application window |
| └─ __init__() | 214 | Initialize window |
| └─ init_ui() | 287 | Setup user interface |
| └─ create_generate_tab() | 402 | Creates generation tab |
| └─ create_settings_tab() | 789 | Creates settings tab |
| └─ create_history_tab() | 1102 | Creates history tab |
| └─ create_help_tab() | 1189 | Creates help tab |
| └─ open_prompt_builder() | 1235 | Opens Prompt Builder dialog |
| └─ generate_image() | 1582 | Initiates image generation |
| └─ load_history() | 1892 | Loads image history |
| └─ handle_history_double_click() | 2145 | Handles history item double-click |
| └─ save_settings() | 2851 | Saves application settings |
| └─ load_settings() | 2912 | Loads application settings |

#### Prompt Builder (`gui/prompt_builder.py`)
**Path**: `gui/prompt_builder.py` - 1456 lines
**Purpose**: Advanced prompt building with semantic search and presets

| Class/Method | Line | Description |
|-------------|------|-------------|
| **SavePresetDialog** | 26 | Dialog for saving custom presets |
| └─ _init_ui() | 44 | Initialize dialog UI |
| └─ validate_and_accept() | 123 | Validates and saves preset |
| **PromptBuilder** | 174 | Main Prompt Builder dialog |
| └─ __init__() | 186 | Initialize builder |
| └─ _defer_data_loading() | 245 | Defers data loading until shown |
| └─ _init_ui() | 278 | Initialize user interface |
| └─ _create_search_tab() | 456 | Creates smart search tab |
| └─ _create_elements_tab() | 589 | Creates element selection tab |
| └─ _create_presets_tab() | 712 | Creates preset management tab |
| └─ _perform_search() | 834 | Executes semantic search |
| └─ _apply_preset() | 967 | Applies selected preset |
| └─ _build_prompt() | 1089 | Builds final prompt |
| └─ _export_prompt() | 1234 | Exports prompt to file |
| └─ _auto_save_settings() | 1356 | Auto-saves current state |

#### Wikimedia Search Dialog (`gui/wikimedia_search_dialog.py`)
**Path**: `gui/wikimedia_search_dialog.py` - 892 lines
**Purpose**: Search and download images from Wikimedia Commons

| Class/Method | Line | Description |
|-------------|------|-------------|
| **NumericTableWidgetItem** | 18 | Sortable table widget item |
| **ImageDownloader** | 37 | Background image downloader |
| └─ run() | 51 | Downloads images in thread |
| **SearchWorker** | 83 | Background search worker |
| └─ run() | 94 | Executes search in thread |
| **ThumbnailLoader** | 104 | Background thumbnail loader |
| └─ run() | 117 | Loads thumbnails in thread |
| **WikimediaSearchDialog** | 156 | Main search dialog |
| └─ __init__() | 157 | Initialize dialog |
| └─ _init_ui() | 189 | Setup user interface |
| └─ _search() | 312 | Initiates search |
| └─ _download_selected() | 456 | Downloads selected images |
| └─ _display_results() | 589 | Displays search results |

#### Dialog History Widget (`gui/history_widget.py`)
**Path**: `gui/history_widget.py` - 234 lines
**Purpose**: Reusable history display widget for dialogs

| Class/Method | Line | Description |
|-------------|------|-------------|
| **DialogHistoryWidget** | 17 | History display widget |
| └─ __init__() | 18 | Initialize widget |
| └─ setup_ui() | 32 | Setup user interface |
| └─ add_history_item() | 78 | Adds item to history |
| └─ clear_history() | 124 | Clears history |
| └─ get_selected_text() | 156 | Gets selected text |
| └─ load_from_json() | 189 | Loads history from JSON |
| └─ save_to_json() | 212 | Saves history to JSON |

#### Image Preview Popup (`gui/image_preview_popup.py`)
**Path**: `gui/image_preview_popup.py` - 115 lines
**Purpose**: Hoverable image preview popup

| Class/Method | Line | Description |
|-------------|------|-------------|
| **ImagePreviewPopup** | 10 | Preview popup widget |
| └─ __init__() | 11 | Initialize popup |
| └─ set_image() | 28 | Sets image to display |
| └─ show_near_cursor() | 45 | Shows popup near cursor |
| └─ hide_preview() | 78 | Hides preview |
| └─ enterEvent() | 92 | Mouse enter handler |
| └─ leaveEvent() | 103 | Mouse leave handler |

### Core Systems

#### Configuration Manager (`core/config.py`)
**Path**: `core/config.py` - 456 lines
**Purpose**: Manages application configuration and API keys

| Method | Line | Description |
|--------|------|-------------|
| **ConfigManager** | 13 | Configuration manager class |
| └─ __init__() | 18 | Initialize config |
| └─ load_config() | 45 | Loads configuration |
| └─ save_config() | 89 | Saves configuration |
| └─ get_api_key() | 134 | Gets API key for provider |
| └─ set_api_key() | 178 | Sets API key |
| └─ get_output_dir() | 223 | Gets output directory |
| └─ get_config_dir() | 267 | Gets config directory |
| └─ migrate_legacy_config() | 312 | Migrates old config |

#### Tag Searcher (`core/tag_searcher.py`)
**Path**: `core/tag_searcher.py` - 478 lines
**Purpose**: Semantic search for prompt elements using tags

| Class/Method | Line | Description |
|-------------|------|-------------|
| **SearchResult** | 19 | Search result dataclass |
| **TagSearcher** | 27 | Semantic search engine |
| └─ __init__() | 48 | Initialize searcher |
| └─ load_metadata() | 67 | Loads tag metadata |
| └─ search() | 123 | Performs semantic search |
| └─ _score_item() | 189 | Scores individual item |
| └─ _fuzzy_match() | 245 | Fuzzy string matching |
| └─ _get_related_tags() | 312 | Gets related tags |
| └─ get_suggestions() | 378 | Gets search suggestions |

#### Preset Loader (`core/preset_loader.py`)
**Path**: `core/preset_loader.py` - 402 lines
**Purpose**: Manages prompt builder presets

| Class/Method | Line | Description |
|-------------|------|-------------|
| **PresetLoader** | 15 | Preset management class |
| └─ __init__() | 19 | Initialize loader |
| └─ load_presets() | 34 | Loads all presets |
| └─ get_preset() | 78 | Gets specific preset |
| └─ save_custom_preset() | 123 | Saves custom preset |
| └─ delete_preset() | 167 | Deletes preset |
| └─ export_preset() | 212 | Exports preset to file |
| └─ import_preset() | 256 | Imports preset from file |
| └─ validate_preset() | 301 | Validates preset data |
| └─ get_categories() | 345 | Gets preset categories |

#### Wikimedia Client (`core/wikimedia_client.py`)
**Path**: `core/wikimedia_client.py` - 244 lines
**Purpose**: Client for Wikimedia Commons API

| Class/Method | Line | Description |
|-------------|------|-------------|
| **WikimediaImage** | 11 | Image metadata dataclass |
| **WikimediaClient** | 30 | Wikimedia API client |
| └─ __init__() | 32 | Initialize client |
| └─ search() | 45 | Search for images |
| └─ download_image() | 89 | Downloads single image |
| └─ download_batch() | 134 | Downloads multiple images |
| └─ get_image_info() | 178 | Gets image metadata |
| └─ parse_response() | 223 | Parses API response |

#### Prompt Data Loader (`core/prompt_data_loader.py`)
**Path**: `core/prompt_data_loader.py` - 150 lines
**Purpose**: Loads prompt data from JSON files

| Class/Method | Line | Description |
|-------------|------|-------------|
| **PromptDataLoader** | 11 | Data loading class |
| └─ __init__() | 13 | Initialize loader |
| └─ load_all_data() | 28 | Loads all prompt data |
| └─ load_file() | 56 | Loads single file |
| └─ get_category_data() | 89 | Gets category data |
| └─ reload_data() | 112 | Reloads all data |
| └─ get_available_categories() | 134 | Lists categories |

### Provider System

#### Base Provider (`providers/base.py`)
**Path**: `providers/base.py` - 289 lines
**Purpose**: Abstract base class for all image providers

| Method | Line | Description |
|--------|------|-------------|
| **ImageProvider** | 8 | Abstract base class |
| └─ generate_image() | 15 | Abstract generation method |
| └─ test_api_key() | 34 | Tests API key validity |
| └─ get_default_model() | 56 | Gets default model |
| └─ get_available_models() | 78 | Lists available models |
| └─ supports_reference_images() | 98 | Reference image support |
| └─ prepare_reference_image() | 123 | Prepares reference image |
| └─ composite_reference_images() | 167 | Composites multiple references |

#### Google Provider (`providers/google.py`)
**Path**: `providers/google.py` - 892 lines
**Purpose**: Google Gemini image generation

| Class/Method | Line | Description |
|-------------|------|-------------|
| **GoogleProvider** | 177 | Google Gemini provider |
| └─ __init__() | 181 | Initialize provider |
| └─ generate_image() | 234 | Generates image |
| └─ _handle_retry() | 378 | Handles NO_IMAGE retries |
| └─ _prepare_generation_config() | 456 | Prepares config |
| └─ _process_reference_images() | 523 | Processes references |
| └─ _decode_base64_image() | 612 | Decodes base64 image |
| └─ test_api_key() | 689 | Tests API key |

#### OpenAI Provider (`providers/openai.py`)
**Path**: `providers/openai.py` - 345 lines
**Purpose**: OpenAI DALL-E image generation

| Class/Method | Line | Description |
|-------------|------|-------------|
| **OpenAIProvider** | 25 | OpenAI DALL-E provider |
| └─ __init__() | 27 | Initialize provider |
| └─ generate_image() | 56 | Generates image |
| └─ _prepare_request() | 123 | Prepares API request |
| └─ _download_image() | 189 | Downloads generated image |
| └─ test_api_key() | 245 | Tests API key |
| └─ get_available_models() | 289 | Lists models |

#### Stability Provider (`providers/stability.py`)
**Path**: `providers/stability.py` - 456 lines
**Purpose**: Stability AI image generation

| Class/Method | Line | Description |
|-------------|------|-------------|
| **StabilityProvider** | 16 | Stability AI provider |
| └─ __init__() | 19 | Initialize provider |
| └─ generate_image() | 45 | Generates image |
| └─ _handle_reference_images() | 134 | Handles references |
| └─ _prepare_payload() | 223 | Prepares API payload |
| └─ test_api_key() | 312 | Tests API key |

#### Ollama Provider (`providers/ollama.py`)
**Path**: `providers/ollama.py` - 234 lines
**Purpose**: Local Ollama model support

| Class/Method | Line | Description |
|-------------|------|-------------|
| **OllamaProvider** | 12 | Ollama local provider |
| └─ __init__() | 15 | Initialize provider |
| └─ detect_server() | 34 | Detects Ollama server |
| └─ get_available_models() | 67 | Lists local models |
| └─ generate_image() | 98 | Generates image locally |
| └─ test_connection() | 167 | Tests server connection |

### Video Subsystem

#### Video Project (`core/video/project.py`)
**Path**: `core/video/project.py` - 1234 lines
**Purpose**: Video project management

| Class/Method | Line | Description |
|-------------|------|-------------|
| **VideoProvider** | 41 | Video provider enum |
| **SceneStatus** | 47 | Scene status enum |
| **AudioTrack** | 56 | Audio track dataclass |
| **Scene** | 289 | Scene data structure |
| └─ __init__() | 293 | Initialize scene |
| └─ update_status() | 345 | Updates scene status |
| └─ add_variant() | 389 | Adds image variant |
| **VideoProject** | 442 | Main project class |
| └─ __init__() | 446 | Initialize project |
| └─ add_scene() | 512 | Adds scene |
| └─ save() | 589 | Saves project |
| └─ load() | 645 | Loads project |
| └─ export_video() | 712 | Exports to video |

#### Storyboard Generator (`core/video/storyboard.py`)
**Path**: `core/video/storyboard.py` - 892 lines
**Purpose**: Generates video storyboards from lyrics

| Class/Method | Line | Description |
|-------------|------|-------------|
| **InputFormat** | 15 | Input format enum |
| **ParsedLine** | 23 | Parsed lyric line |
| **LyricParser** | 32 | Lyric parsing class |
| └─ parse() | 45 | Parses lyrics |
| └─ extract_timings() | 98 | Extracts timing info |
| **TimingEngine** | 272 | Timing calculation |
| └─ calculate_durations() | 289 | Calculates durations |
| └─ apply_bpm() | 345 | Applies BPM timing |
| **StoryboardGenerator** | 475 | Main generator |
| └─ generate() | 489 | Generates storyboard |
| └─ enhance_scenes() | 567 | Enhances with LLM |

#### FFmpeg Renderer (`core/video/ffmpeg_renderer.py`)
**Path**: `core/video/ffmpeg_renderer.py` - 678 lines
**Purpose**: Renders video using FFmpeg

| Class/Method | Line | Description |
|-------------|------|-------------|
| **RenderSettings** | 23 | Render configuration |
| **FFmpegRenderer** | 43 | FFmpeg renderer |
| └─ __init__() | 47 | Initialize renderer |
| └─ render() | 89 | Renders video |
| └─ _prepare_clips() | 156 | Prepares video clips |
| └─ _handle_veo_clips() | 234 | Handles Veo clips |
| └─ _apply_transitions() | 312 | Applies transitions |
| └─ _add_audio() | 389 | Adds audio track |
| └─ _export_final() | 467 | Exports final video |

#### Veo Client (`core/video/veo_client.py`)
**Path**: `core/video/veo_client.py` - 567 lines
**Purpose**: Google Veo video generation client

| Class/Method | Line | Description |
|-------------|------|-------------|
| **VeoModel** | 45 | Veo model enum |
| **VeoGenerationConfig** | 54 | Generation config |
| **VeoGenerationResult** | 125 | Generation result |
| **VeoClient** | 141 | Veo API client |
| └─ __init__() | 145 | Initialize client |
| └─ generate_video() | 189 | Generates video |
| └─ check_status() | 267 | Checks generation status |
| └─ download_video() | 345 | Downloads video |
| └─ batch_generate() | 423 | Batch generation |

#### LLM Sync Assistant (`core/video/llm_sync.py`)
**Path**: `core/video/llm_sync.py` - 456 lines
**Purpose**: LLM-based lyric synchronization

| Class/Method | Line | Description |
|-------------|------|-------------|
| **TimedLyric** | 17 | Timed lyric dataclass |
| **LLMSyncAssistant** | 25 | LLM sync assistant |
| └─ __init__() | 28 | Initialize assistant |
| └─ sync_lyrics() | 56 | Synchronizes lyrics |
| └─ estimate_timings() | 123 | Estimates timings |
| └─ apply_bpm() | 189 | Applies BPM |
| └─ generate_prompts() | 256 | Generates prompts |

### Reference Image System

#### Image Compositor (`core/reference/image_compositor.py`)
**Path**: `core/reference/image_compositor.py` - 264 lines
**Purpose**: Composites multiple reference images

| Class/Method | Line | Description |
|-------------|------|-------------|
| **ReferenceImageCompositor** | 17 | Image compositor |
| └─ __init__() | 19 | Initialize compositor |
| └─ create_composite() | 34 | Creates composite |
| └─ _calculate_grid() | 89 | Calculates grid layout |
| └─ _resize_images() | 134 | Resizes images |
| └─ _apply_padding() | 178 | Applies padding |
| └─ _add_labels() | 223 | Adds text labels |

#### Imagen Reference (`core/reference/imagen_reference.py`)
**Path**: `core/reference/imagen_reference.py` - 189 lines
**Purpose**: Reference image type definitions

| Class/Method | Line | Description |
|-------------|------|-------------|
| **ImagenReferenceType** | 17 | Reference type enum |
| **ImagenSubjectType** | 26 | Subject type enum |
| **ImagenControlType** | 34 | Control type enum |
| **ImagenReference** | 42 | Reference dataclass |
| └─ __init__() | 45 | Initialize reference |
| └─ to_dict() | 78 | Converts to dict |
| └─ from_dict() | 112 | Creates from dict |
| └─ validate() | 145 | Validates reference |

### GUI Utility Components

#### Flow Layout (`gui/flow_layout.py`)
**Path**: `gui/flow_layout.py` - 162 lines
**Purpose**: Flow layout for dynamic widgets

| Class/Method | Line | Description |
|-------------|------|-------------|
| **FlowLayout** | 7 | Flow layout widget |
| └─ __init__() | 9 | Initialize layout |
| └─ addItem() | 23 | Adds item to layout |
| └─ doLayout() | 45 | Performs layout |
| └─ sizeHint() | 89 | Returns size hint |
| └─ minimumSize() | 112 | Returns minimum size |
| └─ expandingDirections() | 134 | Layout directions |

#### LLM Utilities (`gui/llm_utils.py`)
**Path**: `gui/llm_utils.py` - 289 lines
**Purpose**: Shared LLM interaction utilities

| Class/Method | Line | Description |
|-------------|------|-------------|
| **LLMResponseParser** | 15 | Response parser |
| └─ parse_json() | 23 | Parses JSON response |
| └─ extract_json() | 56 | Extracts JSON from text |
| └─ clean_markdown() | 89 | Cleans markdown |
| **DialogStatusConsole** | 127 | Status console widget |
| └─ __init__() | 129 | Initialize console |
| └─ append_message() | 145 | Appends message |
| └─ clear() | 178 | Clears console |
| **LiteLLMHandler** | 201 | LiteLLM handler |
| └─ setup() | 205 | Sets up LiteLLM |
| └─ prepare_model() | 234 | Prepares model name |

#### Dialog Utilities (`gui/dialog_utils.py`)
**Path**: `gui/dialog_utils.py` - 356 lines
**Purpose**: Dialog helper utilities

| Class/Method | Line | Description |
|-------------|------|-------------|
| **InputBlockerEventFilter** | 84 | Input blocking filter |
| └─ eventFilter() | 89 | Filters events |
| **OperationGuardMixin** | 131 | Operation guard mixin |
| └─ start_operation() | 145 | Starts operation |
| └─ end_operation() | 189 | Ends operation |
| └─ is_operation_in_progress() | 223 | Checks status |
| └─ block_input() | 256 | Blocks user input |
| └─ unblock_input() | 289 | Unblocks input |

### Data Files

#### Prompt Metadata (`data/prompts/metadata.json`)
**Path**: `data/prompts/metadata.json` - 19758 lines
**Purpose**: Semantic tags and metadata for all prompt elements

Structure:
```json
{
  "artists": {
    "item_name": {
      "tags": ["style", "period", "technique"],
      "keywords": ["associated", "terms"],
      "description": "Brief description",
      "popularity": 0.0-1.0,
      "related": ["similar_items"]
    }
  },
  "styles": { ... },
  "moods": { ... }
}
```

#### Presets (`data/prompts/presets.json`)
**Path**: `data/prompts/presets.json` - 570 lines
**Purpose**: Pre-configured prompt builder settings

Structure:
```json
{
  "presets": [
    {
      "name": "Preset Name",
      "category": "category",
      "description": "Description",
      "settings": {
        "subject": "...",
        "style": "...",
        "mood": "...",
        "artists": ["..."],
        "additional": "..."
      }
    }
  ]
}
```

## Cross-File Dependencies

### State Management Flows

#### API Key Management
**Managed by**: `core/config.py:13` - ConfigManager
**Consumed by**:
- `providers/google.py:181` - GoogleProvider.__init__()
- `providers/openai.py:27` - OpenAIProvider.__init__()
- `providers/stability.py:19` - StabilityProvider.__init__()
- `gui/main_window.py:2851` - MainWindow.save_settings()
- `gui/main_window.py:2912` - MainWindow.load_settings()

#### Image Generation Flow
**Initiated by**: `gui/main_window.py:1582` - MainWindow.generate_image()
**Flow**:
1. `gui/workers.py:12` - GenWorker (background thread)
2. `providers/__init__.py:8` - get_provider() factory
3. `providers/[provider].py` - Specific provider.generate_image()
4. `core/utils.py:234` - save_image_with_metadata()
5. `gui/main_window.py:1734` - on_generation_complete()

#### Prompt Builder Data Flow
**Managed by**: `gui/prompt_builder.py:174` - PromptBuilder
**Data sources**:
- `core/prompt_data_loader.py:11` - PromptDataLoader
- `core/preset_loader.py:15` - PresetLoader
- `core/tag_searcher.py:27` - TagSearcher
- `data/prompts/*.json` - JSON data files

#### History Management
**Primary**: `gui/main_window.py:1892` - MainWindow.load_history()
**Components**:
- `gui/history_widget.py:17` - DialogHistoryWidget
- `gui/workers.py:65` - HistoryLoaderWorker
- `core/utils.py:345` - scan_image_directory()

#### Reference Image System
**Coordinator**: `gui/imagen_reference_widget.py:436` - ImagenReferenceWidget
**Dependencies**:
- `core/reference/imagen_reference.py:42` - ImagenReference
- `core/reference/image_compositor.py:17` - ReferenceImageCompositor
- `gui/reference_selection_dialog.py:145` - ReferenceSelectionDialog
- `providers/base.py:123` - ImageProvider.prepare_reference_image()

#### Video Project Management
**Core**: `core/video/project.py:442` - VideoProject
**UI Components**:
- `gui/video/workspace_widget.py` - WorkspaceWidget
- `gui/video/video_project_tab.py` - VideoProjectTab
**Processing**:
- `core/video/storyboard.py:475` - StoryboardGenerator
- `core/video/ffmpeg_renderer.py:43` - FFmpegRenderer
- `core/video/veo_client.py:141` - VeoClient

### Service Dependencies

#### Logging Service
**Setup**: `core/logging_config.py:173` - LogManager
**Used everywhere via**: `logging.getLogger(__name__)`

#### Configuration Service
**Singleton**: `core/config.py:13` - ConfigManager
**Accessed via**: `ConfigManager.get_instance()`

#### LLM Service Integration
**Utilities**: `gui/llm_utils.py`
- Response parsing: `LLMResponseParser:15`
- Status display: `DialogStatusConsole:127`
- LiteLLM setup: `LiteLLMHandler:201`

**Used by**:
- `gui/enhanced_prompt_dialog.py` - Prompt enhancement
- `gui/prompt_generation_dialog.py` - Prompt generation
- `gui/reference_image_dialog.py` - Reference analysis
- `core/video/llm_sync.py` - Lyric synchronization

## Configuration Files

### Application Configuration
- **`.env`** - Environment variables (not in git)
- **`requirements.txt`** - Python dependencies
- **`.gitignore`** - Git ignore patterns
- **`CLAUDE.md`** - Claude Code instructions
- **`.claude/settings.local.json`** - Local Claude settings

### Data Configuration
- **`data/prompts/metadata.json`** - Semantic metadata
- **`data/prompts/presets.json`** - Preset configurations
- **`data/prompts/artists.json`** - Artist data
- **`data/prompts/styles.json`** - Style data
- **`data/prompts/moods.json`** - Mood data
- **`data/prompts/colors.json`** - Color data
- **`data/prompts/lighting.json`** - Lighting data
- **`data/prompts/mediums.json`** - Medium data

### User Configuration
**Platform-specific locations**:
- Windows: `%APPDATA%\ImageAI\config.json`
- macOS: `~/Library/Application Support/ImageAI/config.json`
- Linux: `~/.config/ImageAI/config.json`

## Architecture Patterns

### Design Patterns Used

#### Factory Pattern
- **Provider Factory**: `providers/__init__.py:8` - get_provider()
  - Creates appropriate provider based on selection
  - Centralizes provider instantiation

#### Singleton Pattern
- **ConfigManager**: `core/config.py:13`
  - Single instance manages all configuration
  - Thread-safe access to settings

#### Observer Pattern
- **Qt Signals/Slots**: Throughout GUI components
  - Decoupled event handling
  - Reactive UI updates

#### Strategy Pattern
- **Image Providers**: `providers/base.py:8` - ImageProvider
  - Common interface for different generation strategies
  - Runtime provider switching

#### Mixin Pattern
- **OperationGuardMixin**: `gui/dialog_utils.py:131`
  - Reusable operation blocking functionality
  - Prevents concurrent operations in dialogs

### Architectural Principles

#### Separation of Concerns
- **Core**: Business logic and data management
- **GUI**: User interface and interaction
- **Providers**: External service integration
- **CLI**: Command-line interface

#### Dependency Injection
- Providers injected via factory
- Configuration passed to components
- Loose coupling between modules

#### Event-Driven Architecture
- Qt event system for UI
- Background workers for long operations
- Signals for cross-component communication

#### Plugin Architecture
- Provider system allows easy addition of new services
- Modular video renderer system
- Extensible prompt data system

## Development Guidelines

### Code Organization
- One class per file for major components
- Group related functionality in packages
- Keep UI and business logic separated
- Use type hints for better IDE support

### Error Handling
- Always log errors with context
- Provide user-friendly error messages
- Use try/except at integration boundaries
- Validate user input before processing

### Threading Guidelines
- Use QThread for GUI background tasks
- Never update UI from background threads
- Use signals/slots for thread communication
- Implement proper cleanup in thread destructors

### Testing Approach
- Unit tests for core logic
- Integration tests for providers
- Manual testing for GUI components
- Mock external services in tests

### Performance Considerations
- Lazy load heavy resources
- Cache computed values (thumbnails, etc.)
- Use background threads for I/O operations
- Batch database/file operations

### Security Best Practices
- Never store API keys in code
- Use platform-specific secure storage
- Validate all file paths
- Sanitize user input for file names
- Rate limit API calls

### Documentation Standards
- Docstrings for all public methods
- Type hints for parameters and returns
- Comments for complex logic
- Update CodeMap.md for structural changes

### Version Management
- Version defined in `core/constants.py`
- Update README.md changelog
- Tag releases in git
- Document breaking changes

## Quick Reference Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run application (GUI)
python main.py

# Run CLI mode
python main.py -p "prompt" -o output.png

# Test API key
python main.py -t

# Run with specific provider
python main.py --provider openai -p "prompt"
```

### Code Navigation
```bash
# Find class definition
grep -n "^class ClassName" **/*.py

# Find method usage
grep -r "method_name(" --include="*.py"

# List all providers
ls providers/*.py | grep -v __

# Find TODO items
grep -r "TODO\|FIXME" --include="*.py"
```

### Git Operations
```bash
# View recent changes
git log --oneline -10

# Check changed files
git status

# View specific file history
git log -p path/to/file.py

# Find when line was added
git blame path/to/file.py
```

---

*End of Code Map - Total lines: 2120*