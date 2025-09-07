# ImageAI CodeMap

*Last Updated: 2025-09-07 13:07:10*

## Table of Contents

| Section | Line Number |
|---------|-------------|
| [Quick Navigation](#quick-navigation) | 22 |
| [Visual Architecture Overview](#visual-architecture-overview) | 41 |
| [Project Structure](#project-structure) | 109 |
| [Core Module](#core-module) | 165 |
| [Providers Module](#providers-module) | 276 |
| [GUI Module](#gui-module) | 432 |
| [CLI Module](#cli-module) | 619 |
| [Templates](#templates) | 673 |
| [Cross-File Dependencies](#cross-file-dependencies) | 703 |
| [Configuration Files](#configuration-files) | 739 |
| [Architecture Patterns](#architecture-patterns) | 781 |
| [Development Guidelines](#development-guidelines) | 819 |

## Quick Navigation

### Primary Entry Points
- **Main Application**: `main.py:25` - Entry point function
- **GUI Launch**: `gui/__init__.py:15` - GUI initialization
- **CLI Runner**: `cli/runner.py:69` - CLI execution handler
- **Provider Factory**: `providers/__init__.py:77` - Provider instantiation

### Key Configuration
- **App Constants**: `core/constants.py:6` - APP_NAME and VERSION
- **Config Manager**: `core/config.py:11` - Configuration handling class
- **Provider Models**: `core/constants.py:14` - Model mappings per provider

### User Actions
- **Generate Image (GUI)**: `gui/main_window.py:837` - handle_generate()
- **Generate Image (CLI)**: `cli/runner.py:162` - provider.generate()
- **Manage API Keys**: `gui/main_window.py:623` - handle_save_settings()
- **Test Authentication**: `cli/runner.py:133` - provider.validate_auth()

## Visual Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                        main.py                           │
│              Application Entry Point & Router            │
└────────────────────────────┬─────────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
┌──────────────────────┐          ┌──────────────────────┐
│     GUI Module       │          │     CLI Module       │
│  - MainWindow        │          │  - ArgumentParser    │
│  - Dialogs           │          │  - CLIRunner         │
│  - Workers           │          │  - API Key Resolver │
└──────────────────────┘          └──────────────────────┘
        ▲                                         ▲
        └────────────────────┬────────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │    Core Module       │
                  │  - ConfigManager     │
                  │  - Constants         │
                  │  - Utilities         │
                  └──────────────────────┘
                             ▲
                             │
                  ┌──────────────────────┐
                  │  Providers Module    │
                  │  - Base Interface    │
                  │  - Google Provider   │
                  │  - OpenAI Provider   │
                  │  - Stability AI      │
                  │  - Local SD          │
                  └──────────────────────┘
```

### Data Flow Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    User Input                            │
│           (Prompt, Model, Provider, Settings)            │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│                 Provider Selection                        │
│            providers.get_provider(name, config)          │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│                  API Authentication                       │
│         provider.validate_auth() → (bool, message)       │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│                   Image Generation                        │
│    provider.generate(prompt, model) → (texts, images)    │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│                    Output Handling                        │
│      - Save images to disk                               │
│      - Create metadata sidecars (.json)                  │
│      - Update history                                    │
└──────────────────────────────────────────────────────────┘
```

## Project Structure

```
ImageAI/
├── main.py                 # Main entry point (66 lines)
├── main_original.py        # Original single-file version (2646 lines)
│
├── core/                   # Core functionality module
│   ├── __init__.py        # Module exports (51 lines)
│   ├── config.py          # Configuration management (138 lines)
│   ├── constants.py       # Application constants (80 lines)
│   └── utils.py           # Utility functions (327 lines)
│
├── providers/             # AI provider implementations
│   ├── __init__.py       # Provider factory (111 lines)
│   ├── base.py           # Abstract base class (144 lines)
│   ├── google.py         # Google Gemini provider (274 lines)
│   ├── openai.py         # OpenAI DALL-E provider (217 lines)
│   ├── stability.py      # Stability AI provider (445 lines)
│   ├── local_sd.py       # Local Stable Diffusion (490 lines)
│   └── model_info.py     # Model information registry (145 lines)
│
├── gui/                   # GUI components
│   ├── __init__.py       # GUI launcher (25 lines)
│   ├── main_window.py    # Main window class (1562 lines)
│   ├── dialogs.py        # Dialog windows (194 lines)
│   ├── workers.py        # Background workers (50 lines)
│   ├── model_browser.py  # Model browser dialog (442 lines)
│   └── local_sd_widget.py # Local SD settings widget (473 lines)
│
├── cli/                   # CLI components
│   ├── __init__.py       # CLI exports (5 lines)
│   ├── parser.py         # Argument parser (102 lines)
│   └── runner.py         # CLI execution (232 lines)
│
├── templates/             # Prompt templates
│   └── __init__.py       # Template definitions (2097 lines)
│
├── Plans/                 # Development plans
│   ├── GoogleCloudAuth.md
│   ├── GeminiFullFeatures.md
│   ├── NewProviders.md
│   ├── ProviderIntegration.md
│   └── RefactoringPlan.md
│
├── Docs/                  # Documentation
│   └── CodeMap.md        # This file
│
├── requirements.txt       # Python dependencies
├── requirements-local-sd.txt # Local SD dependencies
├── README.md             # User documentation
├── CLAUDE.md             # Claude AI instructions
├── GEMINI.md             # Gemini templates guide
└── download_models.py    # Model download utility (160 lines)
```

## Core Module

### core/__init__.py
**Path**: `core/__init__.py` - 51 lines
**Purpose**: Module exports and public API

#### Exports
| Export | Line | Type | Source Module |
|--------|------|------|---------------|
| ConfigManager | 3 | class | config |
| get_api_key_url | 3 | function | config |
| APP_NAME | 5 | constant | constants |
| VERSION | 6 | constant | constants |
| DEFAULT_MODEL | 7 | constant | constants |
| DEFAULT_PROVIDER | 8 | constant | constants |
| PROVIDER_MODELS | 9 | dict | constants |
| PROVIDER_KEY_URLS | 10 | dict | constants |
| sanitize_filename | 13 | function | utils |
| read_key_file | 14 | function | utils |
| extract_api_key_help | 15 | function | utils |
| read_readme_text | 16 | function | utils |
| images_output_dir | 17 | function | utils |
| sidecar_path | 18 | function | utils |
| write_image_sidecar | 19 | function | utils |
| read_image_sidecar | 20 | function | utils |
| detect_image_extension | 21 | function | utils |
| sanitize_stub_from_prompt | 22 | function | utils |
| auto_save_images | 23 | function | utils |
| scan_disk_history | 24 | function | utils |
| find_cached_demo | 25 | function | utils |
| default_model_for_provider | 26 | function | utils |

### core/config.py
**Path**: `core/config.py` - 138 lines
**Purpose**: Configuration management and API key storage

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| ConfigManager | 11 | Main configuration handler |

#### ConfigManager Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 14 | public | None | Initialize config with platform-specific paths |
| _ensure_config_exists() | 29 | private | None | Create config file if missing |
| load() | 35 | public | None | Load configuration from disk |
| save() | 44 | public | None | Save configuration to disk |
| get() | 50 | public | Any | Get config value with default |
| set() | 58 | public | None | Set config value |
| get_api_key() | 63 | public | str | Get API key for provider |
| set_api_key() | 74 | public | None | Set API key for provider |
| get_images_dir() | 83 | public | Path | Get images output directory |
| get_templates() | 94 | public | list | Get saved templates |
| add_template() | 100 | public | None | Add new template |
| remove_template() | 110 | public | None | Remove template |

#### Module Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| get_api_key_url() | 119 | str | Get API key URL for provider |

### core/constants.py
**Path**: `core/constants.py` - 80 lines
**Purpose**: Application constants and default values

#### Constants
| Constant | Line | Type | Value/Description |
|----------|------|------|-------------------|
| APP_NAME | 6 | str | "ImageAI" |
| VERSION | 7 | str | "0.7.0" |
| DEFAULT_PROVIDER | 10 | str | "google" |
| DEFAULT_MODEL | 11 | str | "gemini-2.5-flash-image-preview" |
| PROVIDER_MODELS | 14 | dict | Model mappings per provider |
| PROVIDER_KEY_URLS | 42 | dict | API key URLs per provider |
| README_PATH | 50 | Path | Path to README.md |
| GEMINI_TEMPLATES_PATH | 51 | Path | Path to GEMINI.md |
| DEFAULT_IMAGE_SIZE | 54 | str | "1024x1024" |
| DEFAULT_NUM_IMAGES | 55 | int | 1 |
| DEFAULT_QUALITY | 56 | str | "standard" |
| DEFAULT_WINDOW_WIDTH | 59 | int | 1000 |
| DEFAULT_WINDOW_HEIGHT | 60 | int | 700 |
| PREVIEW_MAX_WIDTH | 61 | int | 512 |
| PREVIEW_MAX_HEIGHT | 62 | int | 512 |
| TEMPLATE_CATEGORIES | 65 | list | Template category names |
| IMAGE_FORMATS | 76 | dict | Supported image formats |

### core/utils.py
**Path**: `core/utils.py` - 327 lines
**Purpose**: Utility functions for file handling, text processing, and image management

#### Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| sanitize_filename() | 13 | str | Clean filename from text |
| read_key_file() | 38 | str | Read API key from file |
| extract_api_key_help() | 51 | str | Extract API key help from markdown |
| read_readme_text() | 69 | str | Read README.md content |
| images_output_dir() | 79 | Path | Get images output directory |
| sidecar_path() | 90 | Path | Get metadata sidecar path |
| write_image_sidecar() | 97 | None | Write image metadata JSON |
| read_image_sidecar() | 115 | dict | Read image metadata JSON |
| detect_image_extension() | 128 | str | Detect image format from bytes |
| sanitize_stub_from_prompt() | 147 | str | Create filename stub from prompt |
| auto_save_images() | 165 | list | Save images with metadata |
| scan_disk_history() | 217 | list | Scan for existing images |
| find_cached_demo() | 249 | Path | Find cached demo resources |
| default_model_for_provider() | 270 | str | Get default model for provider |
| parse_template_placeholders() | 284 | list | Extract template placeholders |
| apply_template() | 303 | str | Apply values to template |

## Providers Module

### providers/__init__.py
**Path**: `providers/__init__.py` - 111 lines
**Purpose**: Provider factory and lazy loading

#### Module Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| _get_providers() | 17 | dict | Lazy load provider classes |
| get_provider() | 77 | ImageProvider | Get provider instance by name |
| list_providers() | 102 | list | Get available provider names |

#### Provider Loading
| Provider | Line | Class | Module |
|----------|------|-------|--------|
| google | 41 | GoogleProvider | providers.google |
| openai | 48 | OpenAIProvider | providers.openai |
| stability | 56 | StabilityProvider | providers.stability |
| local_sd | 67 | LocalSDProvider | providers.local_sd |

### providers/base.py
**Path**: `providers/base.py` - 144 lines
**Purpose**: Abstract base class for all providers

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| ImageProvider | 8 | Abstract base class |

#### ImageProvider Methods (Abstract)
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 11 | public | None | Initialize with config |
| generate() | 23 | abstract | Tuple | Generate from prompt |
| validate_auth() | 43 | abstract | Tuple | Validate credentials |
| get_models() | 52 | abstract | dict | Get available models |
| get_default_model() | 62 | abstract | str | Get default model |
| supports_feature() | 72 | public | bool | Check feature support |
| get_supported_features() | 84 | public | list | List supported features |
| get_api_key_url() | 94 | public | str | Get API key URL |
| edit_image() | 103 | public | Tuple | Edit existing image |
| inpaint() | 124 | public | Tuple | Inpaint masked regions |

### providers/google.py
**Path**: `providers/google.py` - 274 lines
**Purpose**: Google Gemini provider implementation

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| GoogleProvider | 14 | Google Gemini implementation |

#### GoogleProvider Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 17 | public | None | Initialize with config |
| _get_client() | 35 | private | genai | Get configured client |
| generate() | 65 | public | Tuple | Generate content |
| _generate_with_imagen() | 131 | private | Tuple | Use Imagen models |
| _generate_with_gemini() | 150 | private | Tuple | Use Gemini models |
| validate_auth() | 211 | public | Tuple | Validate API key |
| get_models() | 241 | public | dict | Get model list |
| get_default_model() | 248 | public | str | Get default model |
| get_api_key_url() | 252 | public | str | Get API key URL |
| get_supported_features() | 256 | public | list | List features |

### providers/openai.py
**Path**: `providers/openai.py` - 217 lines
**Purpose**: OpenAI DALL-E provider implementation

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| OpenAIProvider | 12 | OpenAI DALL-E implementation |

#### OpenAIProvider Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 15 | public | None | Initialize with config |
| generate() | 23 | public | Tuple | Generate images |
| edit_image() | 93 | public | Tuple | Edit image with DALL-E 2 |
| validate_auth() | 143 | public | Tuple | Validate API key |
| get_models() | 173 | public | dict | Get model list |
| get_default_model() | 183 | public | str | Get default model |
| get_api_key_url() | 187 | public | str | Get API key URL |
| get_supported_features() | 191 | public | list | List features |

### providers/stability.py
**Path**: `providers/stability.py` - 445 lines
**Purpose**: Stability AI provider implementation

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| StabilityProvider | 15 | Stability AI implementation |

#### StabilityProvider Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 18 | public | None | Initialize with config |
| _get_client() | 26 | private | Client | Get API client |
| generate() | 41 | public | Tuple | Generate images |
| upscale() | 162 | public | Tuple | Upscale image |
| edit_image() | 231 | public | Tuple | Edit with search/replace |
| inpaint() | 293 | public | Tuple | Inpaint masked regions |
| validate_auth() | 355 | public | Tuple | Validate API key |
| get_models() | 385 | public | dict | Get model list |
| get_default_model() | 398 | public | str | Get default model |
| get_api_key_url() | 402 | public | str | Get API key URL |
| get_supported_features() | 406 | public | list | List features |

### providers/local_sd.py
**Path**: `providers/local_sd.py` - 490 lines
**Purpose**: Local Stable Diffusion provider using HuggingFace

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| LocalSDProvider | 23 | Local SD implementation |

#### LocalSDProvider Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 26 | public | None | Initialize with config |
| _get_pipeline() | 58 | private | Pipeline | Get or create pipeline |
| _load_pipeline() | 111 | private | Pipeline | Load model pipeline |
| generate() | 198 | public | Tuple | Generate images |
| validate_auth() | 290 | public | Tuple | Check HF token |
| _check_hf_auth() | 320 | private | Tuple | Validate HF authentication |
| get_models() | 359 | public | dict | Get model list |
| get_default_model() | 372 | public | str | Get default model |
| get_supported_features() | 376 | public | list | List features |
| get_model_info() | 380 | public | dict | Get model metadata |
| download_model() | 403 | public | bool | Download model files |
| list_downloaded_models() | 442 | public | list | List cached models |
| get_model_size() | 461 | public | str | Get model disk size |

### providers/model_info.py
**Path**: `providers/model_info.py` - 145 lines
**Purpose**: Model information registry for local models

#### Constants
| Constant | Line | Type | Description |
|----------|------|------|-------------|
| MODEL_INFO | 4 | dict | Model metadata registry |

#### Model Information Structure
| Model ID | Line | Requirements | Size | Description |
|----------|------|--------------|------|-------------|
| stabilityai/stable-diffusion-2-1 | 5 | 768x768 | ~5GB | SD 2.1 base |
| runwayml/stable-diffusion-v1-5 | 16 | 512x512 | ~4GB | SD 1.5 classic |
| stabilityai/stable-diffusion-xl-base-1.0 | 27 | 1024x1024 | ~7GB | SDXL base |
| segmind/SSD-1B | 39 | 1024x1024 | ~2.5GB | Fast SDXL variant |
| CompVis/stable-diffusion-v1-4 | 51 | 512x512 | ~4GB | SD 1.4 original |

## GUI Module

### gui/__init__.py
**Path**: `gui/__init__.py` - 25 lines
**Purpose**: GUI module initialization and launcher

#### Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| launch_gui() | 15 | None | Create and run GUI application |

### gui/main_window.py
**Path**: `gui/main_window.py` - 1562 lines
**Purpose**: Main application window and UI logic

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports and Setup | 1-39 |
| MainWindow Class | 42 |
| Initialization Methods | 44-98 |
| UI Creation Methods | 99-558 |
| Event Handlers | 559-1150 |
| Helper Methods | 1151-1450 |
| Window Management | 1451-1562 |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| MainWindow | 42 | Main application window |

#### MainWindow Core Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 44 | public | None | Initialize window |
| _load_history_from_disk() | 75 | private | None | Load image history |
| _init_ui() | 99 | private | None | Create UI elements |
| _init_menu() | 108 | private | None | Create menu bar |
| _create_generate_tab() | 151 | private | QWidget | Create generation tab |
| _create_settings_tab() | 273 | private | QWidget | Create settings tab |
| _create_templates_tab() | 397 | private | QWidget | Create templates tab |
| _create_help_tab() | 482 | private | QWidget | Create help tab |
| _create_history_tab() | 513 | private | QWidget | Create history tab |

#### Event Handler Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| handle_provider_change() | 559 | private | None | Provider selection changed |
| handle_auth_mode_change() | 593 | private | None | Auth mode changed |
| handle_save_settings() | 623 | private | None | Save settings |
| handle_test_key() | 656 | private | None | Test API key |
| handle_get_key() | 686 | private | None | Open API key URL |
| handle_template_selected() | 711 | private | None | Template selected |
| handle_apply_template() | 745 | private | None | Apply template |
| handle_save_template() | 789 | private | None | Save new template |
| handle_delete_template() | 825 | private | None | Delete template |
| handle_generate() | 837 | private | None | Start generation |
| handle_generation_done() | 901 | private | None | Generation completed |
| handle_generation_error() | 945 | private | None | Generation failed |
| handle_copy_prompt() | 975 | private | None | Copy prompt to clipboard |
| handle_save_image() | 985 | private | None | Save image to file |
| handle_auto_save_changed() | 1025 | private | None | Auto-save toggled |
| handle_image_size_changed() | 1035 | private | None | Image size changed |
| handle_copy_filename_changed() | 1045 | private | None | Copy filename toggled |
| handle_history_selected() | 1055 | private | None | History item selected |
| handle_load_from_history() | 1085 | private | None | Load history item |
| handle_clear_history() | 1115 | private | None | Clear history |
| handle_show_examples() | 1135 | private | None | Show examples dialog |

#### Helper Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| _update_models_for_provider() | 1151 | private | None | Update model list |
| _load_templates() | 1185 | private | None | Load saved templates |
| _refresh_template_list() | 1215 | private | None | Refresh template UI |
| _update_preview() | 1245 | private | None | Update image preview |
| _add_to_history() | 1285 | private | None | Add to history |
| _refresh_history_list() | 1315 | private | None | Refresh history UI |
| _get_template_defaults() | 1355 | private | dict | Get template defaults |
| _parse_template_placeholders() | 1385 | private | list | Parse placeholders |
| _apply_template_with_values() | 1415 | private | str | Apply template values |

#### Window Management Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| _restore_geometry() | 1451 | private | None | Restore window position |
| _save_geometry() | 1485 | private | None | Save window position |
| closeEvent() | 1515 | protected | None | Handle window close |
| show_about() | 1535 | private | None | Show about dialog |

### gui/dialogs.py
**Path**: `gui/dialogs.py` - 194 lines
**Purpose**: Dialog windows for examples and input

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| ExamplesDialog | 15 | Example prompts dialog |
| PlaceholderInputDialog | 145 | Template placeholder input |

#### ExamplesDialog Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 18 | public | None | Initialize dialog |
| _init_ui() | 25 | private | None | Create UI |
| _load_examples() | 85 | private | list | Load example prompts |
| handle_select() | 115 | private | None | Select example |
| handle_close() | 125 | private | None | Close dialog |
| get_selected_prompt() | 135 | public | str | Get selected prompt |

#### PlaceholderInputDialog Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 148 | public | None | Initialize dialog |
| get_values() | 155 | public | dict | Get input values |
| exec_with_defaults() | 175 | public | int | Show with defaults |

### gui/workers.py
**Path**: `gui/workers.py` - 50 lines
**Purpose**: Background worker threads for generation

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| GenWorker | 10 | Background generation worker |

#### GenWorker Signals
| Signal | Line | Type | Description |
|--------|------|------|-------------|
| finished | 13 | Signal | Generation completed |
| error | 14 | Signal | Generation failed |

#### GenWorker Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 16 | public | None | Initialize worker |
| run() | 25 | public | None | Execute generation |

### gui/model_browser.py
**Path**: `gui/model_browser.py` - 442 lines
**Purpose**: Model browser and download manager for HuggingFace models

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| ModelBrowserDialog | 25 | Model browser dialog |
| DownloadThread | 385 | Download worker thread |

#### ModelBrowserDialog Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 28 | public | None | Initialize dialog |
| _init_ui() | 45 | private | None | Create UI |
| _create_model_list() | 95 | private | QWidget | Create model list |
| _create_details_panel() | 135 | private | QWidget | Create details panel |
| _create_auth_section() | 185 | private | QWidget | Create auth UI |
| _update_auth_status() | 225 | private | None | Update auth display |
| _handle_save_token() | 255 | private | None | Save HF token |
| _handle_model_selected() | 285 | private | None | Model selected |
| _handle_download() | 315 | private | None | Start download |
| _handle_download_complete() | 355 | private | None | Download finished |

### gui/local_sd_widget.py
**Path**: `gui/local_sd_widget.py` - 473 lines
**Purpose**: Settings widget for local Stable Diffusion

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| LocalSDWidget | 18 | Local SD settings widget |

#### LocalSDWidget Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 21 | public | None | Initialize widget |
| _init_ui() | 35 | private | None | Create UI |
| _create_model_section() | 65 | private | QWidget | Model selection UI |
| _create_performance_section() | 115 | private | QWidget | Performance settings |
| _create_auth_section() | 175 | private | QWidget | HF auth UI |
| _update_model_info() | 225 | private | None | Update model display |
| _handle_open_browser() | 265 | private | None | Open model browser |
| _handle_refresh_models() | 285 | private | None | Refresh model list |
| _handle_save_token() | 315 | private | None | Save HF token |
| _handle_device_changed() | 345 | private | None | Device selection |
| get_settings() | 385 | public | dict | Get current settings |
| set_settings() | 415 | public | None | Apply settings |

## CLI Module

### cli/__init__.py
**Path**: `cli/__init__.py` - 5 lines
**Purpose**: CLI module exports

#### Exports
| Export | Line | Source |
|--------|------|--------|
| build_arg_parser | 3 | parser |
| run_cli | 4 | runner |

### cli/parser.py
**Path**: `cli/parser.py` - 102 lines
**Purpose**: Command-line argument parser

#### Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| build_arg_parser() | 9 | ArgumentParser | Create argument parser |

#### Argument Groups
| Group | Line | Arguments |
|-------|------|----------|
| Mode Arguments | 18 | --gui, --help-api-key |
| Provider Selection | 28 | --provider, --auth-mode |
| API Key Management | 38 | --api-key, --api-key-file, --set-key, --test |
| Generation Options | 52 | --prompt, --model, --size, --quality, --num-images |
| Output Options | 72 | --out, --format |
| Template Options | 82 | --template, --template-vars |
| Advanced Options | 92 | --verbose, --debug |

### cli/runner.py
**Path**: `cli/runner.py` - 232 lines
**Purpose**: CLI execution and coordination

#### Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| resolve_api_key() | 12 | Tuple | Resolve API key from sources |
| store_api_key() | 62 | None | Save API key to config |
| run_cli() | 69 | int | Execute CLI with arguments |

#### CLI Execution Flow
| Step | Line | Action |
|------|------|--------|
| Parse Provider | 80 | Get provider and auth mode |
| Handle Help | 84 | Show API key help if requested |
| Resolve API Key | 97 | Get key from various sources |
| Handle --set-key | 104 | Store API key if provided |
| Handle --test | 127 | Test authentication |
| Handle --prompt | 150 | Generate images |
| Save Output | 177 | Save images and metadata |

## Templates

### templates/__init__.py
**Path**: `templates/__init__.py` - 2097 lines
**Purpose**: Extensive collection of prompt templates

#### Template Categories
| Category | Line | Template Count | Description |
|----------|------|----------------|-------------|
| Art Style | 15 | 150+ | Artistic style templates |
| Photography | 485 | 100+ | Photography templates |
| Character | 825 | 80+ | Character design templates |
| Scene | 1185 | 120+ | Scene composition templates |
| Product | 1545 | 60+ | Product visualization |
| Marketing | 1785 | 50+ | Marketing materials |
| Design | 1945 | 70+ | Design templates |

#### Template Structure
```python
{
    "name": "Template Name",
    "category": "Category",
    "prompt": "Prompt with {placeholders}",
    "defaults": {
        "placeholder": "default value"
    },
    "tags": ["tag1", "tag2"]
}
```

## Cross-File Dependencies

### Configuration Flow
**Managed by**: `core/config.py:ConfigManager`
**Consumed by**:
- `gui/main_window.py:46` - Load settings
- `cli/runner.py:40` - Get API keys
- `providers/*.py` - Provider initialization

### Provider System
**Factory**: `providers/__init__.py:get_provider()`
**Implementations**:
- `providers/google.py:GoogleProvider`
- `providers/openai.py:OpenAIProvider`
- `providers/stability.py:StabilityProvider`
- `providers/local_sd.py:LocalSDProvider`
**Consumers**:
- `gui/workers.py:30` - Generation worker
- `cli/runner.py:133` - CLI generation

### Template System
**Definitions**: `templates/__init__.py`
**Parser**: `core/utils.py:284` - parse_template_placeholders()
**Consumers**:
- `gui/main_window.py:397` - Templates tab
- `gui/dialogs.py:145` - Placeholder input
- `cli/parser.py:82` - Template CLI args

### Image Management
**Output Directory**: `core/utils.py:79` - images_output_dir()
**Metadata Sidecars**: `core/utils.py:97` - write_image_sidecar()
**History Scanning**: `core/utils.py:217` - scan_disk_history()
**Consumers**:
- `gui/main_window.py:57` - Load history
- `cli/runner.py:204` - Save images

## Configuration Files

### requirements.txt
**Path**: `requirements.txt`
**Purpose**: Python package dependencies

#### Core Dependencies
- `PySide6>=6.5.0` - GUI framework
- `google-generativeai>=0.8.0` - Google Gemini
- `openai>=1.0.0` - OpenAI API
- `stability-sdk>=0.8.0` - Stability AI
- `Pillow>=10.0.0` - Image processing

### requirements-local-sd.txt
**Path**: `requirements-local-sd.txt`
**Purpose**: Local Stable Diffusion dependencies

#### ML Dependencies
- `torch>=2.0.0` - PyTorch framework
- `diffusers>=0.24.0` - Diffusion models
- `transformers>=4.35.0` - Transformers
- `accelerate>=0.24.0` - Training acceleration
- `safetensors>=0.4.0` - Safe tensor storage
- `huggingface-hub>=0.19.0` - HF Hub client

### CLAUDE.md
**Path**: `CLAUDE.md`
**Purpose**: Instructions for Claude AI assistant
- Project overview and context
- Key commands and usage
- Architecture documentation
- Development guidelines

### README.md
**Path**: `README.md`
**Purpose**: User documentation
- Installation instructions
- Usage examples
- API key setup
- Feature documentation
- Troubleshooting guide

## Architecture Patterns

### Design Patterns Used

#### Factory Pattern
**Implementation**: `providers/__init__.py:get_provider()`
**Purpose**: Dynamic provider instantiation based on configuration

#### Strategy Pattern
**Implementation**: `providers/base.py:ImageProvider` interface
**Purpose**: Swappable image generation strategies per provider

#### Observer Pattern
**Implementation**: Qt Signals/Slots in GUI
**Purpose**: Event-driven UI updates and async operations

#### Template Method Pattern
**Implementation**: `providers/base.py` abstract methods
**Purpose**: Define provider interface with customizable implementation

### Architectural Principles

#### Separation of Concerns
- **CLI** - Command-line interface logic
- **GUI** - Graphical interface and widgets
- **Core** - Business logic and utilities
- **Providers** - External API integrations

#### Dependency Injection
- Providers receive configuration via constructor
- No hard-coded API keys or settings
- Configuration managed centrally

#### Lazy Loading
- Providers loaded only when needed
- Import errors handled gracefully
- Optional dependencies isolated

## Development Guidelines

### Adding New Providers

1. **Create Provider Class** (`providers/new_provider.py`)
   - Inherit from `ImageProvider`
   - Implement all abstract methods
   - Handle authentication and generation

2. **Register Provider** (`providers/__init__.py`)
   - Add import with error handling
   - Register in `_get_providers()`

3. **Add Constants** (`core/constants.py`)
   - Add to `PROVIDER_MODELS`
   - Add to `PROVIDER_KEY_URLS`

4. **Update UI** (`gui/main_window.py`)
   - Provider will auto-appear in dropdown
   - Add provider-specific UI if needed

### Code Style Guidelines

- Use type hints for all function parameters
- Document classes and methods with docstrings
- Handle errors gracefully with try/except
- Use Path objects for file operations
- Follow PEP 8 naming conventions

### Testing Guidelines

- Test each provider independently
- Verify API key validation
- Test generation with various parameters
- Check error handling and recovery
- Validate metadata sidecar creation

### Performance Considerations

- Lazy load heavy dependencies
- Cache provider instances
- Use threading for long operations
- Stream large images efficiently
- Minimize API calls

### Security Best Practices

- Never log API keys
- Store keys in user config directory
- Validate all user inputs
- Sanitize filenames
- Use HTTPS for all API calls