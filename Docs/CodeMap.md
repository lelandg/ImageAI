# ImageAI CodeMap

*Last Updated: 2025-09-11 19:46:26*

## Table of Contents

| Section | Line Number |
|---------|-------------|
| [Quick Navigation](#quick-navigation) | 23 |
| [Visual Architecture Overview](#visual-architecture-overview) | 48 |
| [Project Structure](#project-structure) | 142 |
| [Core Module](#core-module) | 217 |
| [Providers Module](#providers-module) | 386 |
| [GUI Module](#gui-module) | 542 |
| [CLI Module](#cli-module) | 764 |
| [Templates](#templates) | 818 |
| [Utility Scripts](#utility-scripts) | 848 |
| [Cross-File Dependencies](#cross-file-dependencies) | 884 |
| [Configuration Files](#configuration-files) | 945 |
| [Architecture Patterns](#architecture-patterns) | 1007 |
| [Development Guidelines](#development-guidelines) | 1058 |

## Quick Navigation

### Primary Entry Points
- **Main Application**: `main.py:25` - Entry point function
- **GUI Launch**: `gui/__init__.py:15` - GUI initialization
- **CLI Runner**: `cli/runner.py:69` - CLI execution handler
- **Provider Factory**: `providers/__init__.py:121` - Provider instantiation

### Key Configuration
- **App Constants**: `core/constants.py:6` - APP_NAME and VERSION (0.9.3)
- **Config Manager**: `core/config.py:13` - Configuration handling class
- **Security Module**: `core/security.py:30` - Path validation, key storage, rate limiting
- **Provider Models**: `core/constants.py:14` - Model mappings per provider

### User Actions
- **Generate Image (GUI)**: `gui/main_window.py:1563` - handle_generate()
- **Generate Image (CLI)**: `cli/runner.py:164` - provider.generate()
- **Manage API Keys**: `gui/main_window.py:1182` - handle_save_settings()
- **Test Authentication**: `cli/runner.py:133` - provider.validate_auth()
- **Google Cloud Auth**: `core/gcloud_utils.py:22` - find_gcloud_command()

### Utility Scripts
- **Config Migration**: `migrate_config.py:52` - Migrate old config format
- **Secure Keys**: `secure_keys.py:15` - Store keys in system keyring

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
│  - SettingsWidgets   │          │  - CLIRunner         │
│  - Workers           │          │  - API Key Resolver │
└──────────────────────┘          └──────────────────────┘
        ▲                                         ▲
        └────────────────────┬────────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │    Core Module       │
                  │  - ConfigManager     │
                  │  - Security Utils    │
                  │  - GCloud Utils      │
                  │  - Constants         │
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

### Security Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Security Layer                        │
│                  core/security.py                        │
└────────────────────────────┬─────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  PathValidator   │ │ SecureKeyStorage │ │   RateLimiter    │
│  - Path safety   │ │ - Keyring API    │ │ - API throttling │
│  - Filename      │ │ - Encryption     │ │ - Per-provider   │
│    validation    │ │ - Secure store   │ │   limits         │
└──────────────────┘ └──────────────────┘ └──────────────────┘
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
│      (Google Cloud Auth / API Key / Keyring Storage)     │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│                   Rate Limiting Check                     │
│         rate_limiter.check_rate_limit(provider)          │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│                   Image Generation                        │
│    provider.generate(prompt, model) → (texts, images)    │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│                    Output Handling                        │
│      - Path validation for auto_save                     │
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
│   ├── config.py          # Configuration management (177 lines)
│   ├── constants.py       # Application constants (85 lines)
│   ├── gcloud_utils.py    # Google Cloud utilities (143 lines)
│   ├── security.py        # Security utilities (283 lines)
│   └── utils.py           # Utility functions (345 lines)
│
├── providers/             # AI provider implementations
│   ├── __init__.py       # Provider factory (153 lines)
│   ├── base.py           # Abstract base class (144 lines)
│   ├── google.py         # Google Gemini provider (471 lines)
│   ├── openai.py         # OpenAI DALL-E provider (348 lines)
│   ├── stability.py      # Stability AI provider (445 lines)
│   ├── local_sd.py       # Local Stable Diffusion (490 lines)
│   └── model_info.py     # Model information registry (145 lines)
│
├── gui/                   # GUI components
│   ├── __init__.py       # GUI launcher (25 lines)
│   ├── main_window.py    # Main window class (3230 lines)
│   ├── dialogs.py        # Dialog windows (194 lines)
│   ├── workers.py        # Background workers (50 lines)
│   ├── settings_widgets.py # Settings UI widgets (487 lines)
│   ├── model_browser.py  # Model browser dialog (442 lines)
│   └── local_sd_widget.py # Local SD settings widget (473 lines)
│
├── cli/                   # CLI components
│   ├── __init__.py       # CLI exports (5 lines)
│   ├── parser.py         # Argument parser (102 lines)
│   └── runner.py         # CLI execution (237 lines)
│
├── templates/             # Prompt templates
│   └── __init__.py       # Template definitions (2097 lines)
│
├── Screenshots/           # Application screenshots
│   ├── screenshot_generate.jpg
│   ├── screenshot_help.png
│   ├── screenshot_history.png
│   ├── screenshot_template_art.png
│   └── screenshot_template_styles.png
│
├── Plans/                 # Development plans
│   ├── ComprehensiveSettings.md
│   ├── GeminiFullFeatures.md
│   ├── GoogleCloudAuth.md
│   ├── ImageAI-VideoProject-PRD.md # Video project specification
│   ├── NewProviders.md
│   ├── ProviderIntegration.md
│   └── RefactoringPlan.md
│
├── Docs/                  # Documentation
│   └── CodeMap.md        # This file
│
├── .claude/               # Claude AI configuration
│   ├── settings.local.json
│   └── VERSION_LOCATIONS.md
│
├── migrate_config.py      # Config migration utility (179 lines)
├── secure_keys.py         # API key security utility (106 lines)
├── requirements.txt       # Python dependencies
├── requirements-local-sd.txt # Local SD dependencies
├── README.md             # User documentation
├── CHANGELOG.md          # Version history
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
**Path**: `core/config.py` - 177 lines
**Purpose**: Configuration management and API key storage with secure keyring integration

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| ConfigManager | 13 | Main configuration handler with keyring support |

#### ConfigManager Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 16 | public | None | Initialize config with platform-specific paths |
| _get_config_dir() | 23 | private | Path | Get platform-specific config directory |
| _load_config() | 37 | private | dict | Load configuration from disk |
| save() | 48 | public | None | Save configuration to disk |
| get() | 55 | public | Any | Get config value with default |
| set() | 59 | public | None | Set config value |
| get_provider_config() | 63 | public | dict | Get provider-specific config |
| set_provider_config() | 68 | public | None | Set provider-specific config |
| get_api_key() | 74 | public | str | Get API key from keyring or config |
| set_api_key() | 88 | public | None | Set API key in keyring and config |
| get_auth_mode() | 99 | public | str | Get auth mode for provider |
| set_auth_mode() | 105 | public | None | Set auth mode for provider |
| get_auth_validated() | 110 | public | bool | Get auth validation state |
| set_auth_validated() | 116 | public | None | Set auth validation state |
| get_gcloud_project_id() | 138 | public | str | Get Google Cloud project ID |
| set_gcloud_project_id() | 142 | public | None | Set Google Cloud project ID |
| save_details_record() | 146 | public | None | Save generation details |
| load_details_records() | 154 | public | list | Load generation records |
| get_images_dir() | 168 | public | Path | Get images output directory |

#### Module Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| get_api_key_url() | 175 | str | Get API key URL for provider |

### core/constants.py
**Path**: `core/constants.py` - 85 lines
**Purpose**: Application constants and default values

#### Constants
| Constant | Line | Type | Value/Description |
|----------|------|------|-------------------|
| APP_NAME | 6 | str | "ImageAI" |
| VERSION | 7 | str | "0.9.3" |
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
| IMAGE_FORMATS | 81 | dict | Supported image formats |

### core/security.py
**Path**: `core/security.py` - 283 lines
**Purpose**: Security utilities for path validation, API key encryption, and rate limiting

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| PathValidator | 30 | Validates paths to prevent directory traversal |
| SecureKeyStorage | 82 | Manages secure API key storage using keyring |
| RateLimiter | 169 | Implements rate limiting for API calls |

#### PathValidator Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| is_safe_path() | 34 | static | bool | Check if path is within base directory |
| validate_filename() | 58 | static | bool | Validate filename for dangerous characters |

#### SecureKeyStorage Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 87 | public | None | Initialize with keyring availability check |
| store_key() | 93 | public | bool | Store API key in system keyring |
| retrieve_key() | 119 | public | str | Retrieve API key from keyring |
| delete_key() | 144 | public | bool | Delete API key from keyring |

#### RateLimiter Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 172 | public | None | Initialize with default rate limits |
| set_limit() | 185 | public | None | Set custom rate limit for provider |
| check_rate_limit() | 196 | public | bool | Check/enforce rate limits with optional wait |
| get_remaining_calls() | 245 | public | tuple | Get remaining calls and reset time |

#### Global Instances
| Instance | Line | Type | Description |
|----------|------|------|-------------|
| path_validator | 281 | PathValidator | Global path validator instance |
| secure_storage | 282 | SecureKeyStorage | Global secure storage instance |
| rate_limiter | 283 | RateLimiter | Global rate limiter instance |

### core/gcloud_utils.py
**Path**: `core/gcloud_utils.py` - 143 lines
**Purpose**: Google Cloud authentication and SDK utilities

#### Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| find_gcloud_command() | 22 | str | Find gcloud CLI on various platforms |
| get_gcloud_project_id() | 100 | str | Get current Google Cloud project ID |
| check_gcloud_auth() | 118 | tuple | Check Google Cloud authentication status |

### core/utils.py
**Path**: `core/utils.py` - 345 lines
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
| auto_save_images() | 165 | list | Save images with path validation |
| scan_disk_history() | 217 | list | Scan for existing images |
| find_cached_demo() | 249 | Path | Find cached demo resources |
| default_model_for_provider() | 270 | str | Get default model for provider |
| parse_template_placeholders() | 284 | list | Extract template placeholders |
| apply_template() | 303 | str | Apply values to template |

## Providers Module

### providers/__init__.py
**Path**: `providers/__init__.py` - 153 lines
**Purpose**: Provider factory and lazy loading with performance improvements

#### Module Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| _get_providers() | 23 | dict | Lazy load provider classes with caching |
| get_provider() | 121 | ImageProvider | Get provider instance by name |
| list_providers() | 144 | list | Get available provider names |

#### Provider Loading
| Provider | Line | Class | Module |
|----------|------|-------|--------|
| google | 62 | GoogleProvider | providers.google |
| openai | 69 | OpenAIProvider | providers.openai |
| stability | 80 | StabilityProvider | providers.stability |
| local_sd | 91 | LocalSDProvider | providers.local_sd |

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
**Path**: `providers/google.py` - 471 lines
**Purpose**: Google Gemini provider with Google Cloud auth support and improved performance

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| GoogleProvider | 17 | Google Gemini implementation |

#### GoogleProvider Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 21 | public | None | Initialize with auth mode support |
| _get_client() | 45 | private | genai | Get configured client (lazy init) |
| generate() | 109 | public | Tuple | Generate with conditional rate limiting |
| _generate_with_imagen() | 197 | private | Tuple | Use Imagen models |
| _generate_with_gemini() | 231 | private | Tuple | Use Gemini models with rate limiting |
| validate_auth() | 323 | public | Tuple | Validate API key or Google Cloud auth |
| get_models() | 399 | public | dict | Get model list with caching |
| get_default_model() | 419 | public | str | Get default model |
| get_api_key_url() | 427 | public | str | Get API key URL |
| get_supported_features() | 435 | public | list | List features |

### providers/openai.py
**Path**: `providers/openai.py` - 348 lines
**Purpose**: OpenAI DALL-E provider with rate limiting and enhanced error handling

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| OpenAIProvider | 14 | OpenAI DALL-E implementation |

#### OpenAIProvider Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 18 | public | None | Initialize with config |
| generate() | 35 | public | Tuple | Generate images with rate limiting |
| edit_image() | 145 | public | Tuple | Edit image with DALL-E 2 |
| validate_auth() | 223 | public | Tuple | Validate API key |
| get_models() | 274 | public | dict | Get model list with details |
| get_default_model() | 302 | public | str | Get default model |
| get_api_key_url() | 310 | public | str | Get API key URL |
| get_supported_features() | 318 | public | list | List features |

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
**Path**: `gui/main_window.py` - 3230 lines
**Purpose**: Main application window with enhanced provider handling and UI improvements

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports and Setup | 1-52 |
| MainWindow Class | 55 |
| Initialization Methods | 57-142 |
| UI Creation Methods | 143-802 |
| Event Handlers | 803-2100 |
| Helper Methods | 2101-2850 |
| Window Management | 2851-3230 |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| MainWindow | 55 | Main application window |

#### MainWindow Core Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 57 | public | None | Initialize window with improved state |
| _load_history_from_disk() | 107 | private | None | Load image history |
| _init_ui() | 143 | private | None | Create UI elements |
| _init_menu() | 156 | private | None | Create menu bar |
| _create_generate_tab() | 232 | private | QWidget | Create generation tab with splitter |
| _create_settings_tab() | 485 | private | QWidget | Create settings with provider persistence |
| _create_templates_tab() | 671 | private | QWidget | Create templates tab |
| _create_help_tab() | 742 | private | QWidget | Create help tab with search |
| _create_history_tab() | 781 | private | QWidget | Create history tab |

#### Event Handler Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| handle_provider_change() | 1107 | private | None | Provider selection with model update |
| handle_auth_mode_change() | 1168 | private | None | Auth mode changed with persistence |
| handle_save_settings() | 1182 | private | None | Save settings with keyring |
| handle_test_key() | 1235 | private | None | Test API key or Google Cloud auth |
| handle_get_key() | 1312 | private | None | Open API key URL |
| handle_template_selected() | 1345 | private | None | Template selected |
| handle_apply_template() | 1402 | private | None | Apply template |
| handle_save_template() | 1482 | private | None | Save new template |
| handle_delete_template() | 1534 | private | None | Delete template |
| handle_generate() | 1563 | private | None | Start generation with validation |
| handle_generation_done() | 1685 | private | None | Generation completed |
| handle_generation_error() | 1756 | private | None | Generation failed |
| handle_copy_prompt() | 1812 | private | None | Copy prompt to clipboard |
| handle_save_image() | 1835 | private | None | Save image to file |
| handle_auto_save_changed() | 1912 | private | None | Auto-save toggled |
| handle_image_size_changed() | 1935 | private | None | Image size changed |
| handle_copy_filename_changed() | 1956 | private | None | Copy filename toggled |
| handle_history_selected() | 1978 | private | None | History item selected |
| handle_load_from_history() | 2023 | private | None | Load history item |
| handle_clear_history() | 2078 | private | None | Clear history |
| handle_show_examples() | 2112 | private | None | Show examples dialog |

#### Helper Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| _update_models_for_provider() | 2145 | private | None | Update model list with caching |
| _load_templates() | 2212 | private | None | Load saved templates |
| _refresh_template_list() | 2267 | private | None | Refresh template UI |
| _update_preview() | 2312 | private | None | Update image preview with debouncing |
| _add_to_history() | 2389 | private | None | Add to history |
| _refresh_history_list() | 2445 | private | None | Refresh history UI |
| _get_template_defaults() | 2512 | private | dict | Get template defaults |
| _parse_template_placeholders() | 2567 | private | list | Parse placeholders |
| _apply_template_with_values() | 2612 | private | str | Apply template values |
| _update_auth_status() | 2678 | private | None | Update auth status display |
| _restore_auth_state() | 2734 | private | None | Restore cached auth state |

#### Window Management Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| _restore_geometry() | 2789 | private | None | Restore window position |
| _save_geometry() | 2845 | private | None | Save window position |
| closeEvent() | 2901 | protected | None | Handle window close |
| show_about() | 2967 | private | None | Show about dialog |
| handle_save_project() | 3023 | private | None | Save project state |
| handle_load_project() | 3089 | private | None | Load project state |

### gui/settings_widgets.py
**Path**: `gui/settings_widgets.py` - 487 lines
**Purpose**: Advanced settings widgets for enhanced UI

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| AspectRatioSelector | 15 | Visual aspect ratio selector |
| ImageSizeSelector | 145 | Image size configuration widget |
| QualitySelector | 285 | Image quality settings |
| AdvancedSettingsPanel | 385 | Collapsible advanced settings |

#### AspectRatioSelector Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 29 | public | None | Initialize selector |
| _init_ui() | 35 | private | None | Create ratio buttons |
| _create_ratio_button() | 52 | private | QToolButton | Create single ratio button |
| set_ratio() | 85 | public | None | Set selected ratio |
| get_ratio() | 95 | public | str | Get current ratio |
| _handle_ratio_clicked() | 105 | private | None | Handle ratio selection |

#### ImageSizeSelector Methods
| Method | Line | Access | Returns | Description |
|--------|------|--------|---------|-------------|
| __init__() | 148 | public | None | Initialize with size options |
| _init_ui() | 155 | private | None | Create size controls |
| set_size() | 185 | public | None | Set image dimensions |
| get_size() | 195 | public | tuple | Get width and height |
| _update_from_ratio() | 205 | private | None | Update size from aspect ratio |

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
**Path**: `cli/runner.py` - 237 lines
**Purpose**: CLI execution and coordination with improved provider handling

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
| Handle --test | 127 | Test authentication with feedback |
| Handle --prompt | 150 | Generate images with validation |
| Save Output | 182 | Save images and metadata |

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

## Utility Scripts

### migrate_config.py
**Path**: `migrate_config.py` - 179 lines
**Purpose**: Migrate old config.json format to new structure and secure API keys

#### Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| get_config_path() | 37 | Path | Get platform-specific config path |
| migrate_config() | 52 | dict | Migrate configuration format |
| main() | 150 | int | Main entry point |

#### Migration Features
- Moves legacy top-level `api_key` to `providers.google.api_key`
- Fixes incorrect `keys.<provider>` structure
- Optionally stores API keys in system keyring
- Creates timestamped backups
- Supports dry-run mode

### secure_keys.py
**Path**: `secure_keys.py` - 106 lines
**Purpose**: Move API keys from config.json to Windows Credential Manager

#### Functions
| Function | Line | Returns | Description |
|----------|------|---------|-------------|
| main() | 15 | int | Secure API keys in keyring |

#### Security Features
- Windows-specific (must run in PowerShell/CMD)
- Stores keys in Windows Credential Manager
- Verifies successful storage
- Creates backup before modification
- Removes keys from config.json after securing

## Cross-File Dependencies

### Configuration Flow
**Managed by**: `core/config.py:ConfigManager`
**Consumed by**:
- `gui/main_window.py:59` - Load settings with auth persistence
- `cli/runner.py:40` - Get API keys
- `providers/*.py` - Provider initialization
- `core/security.py:82` - SecureKeyStorage integration

### Security Layer
**Components**: `core/security.py`
**Path Validation**:
- `core/utils.py:165` - auto_save_images() validates paths
- `gui/main_window.py:1841` - Save operations use validated paths

**Key Storage**:
- `core/config.py:74` - get_api_key() checks keyring first
- `core/config.py:88` - set_api_key() stores in keyring
- `gui/main_window.py:1189` - Settings save uses secure storage

**Rate Limiting**:
- `providers/google.py:265` - Conditional rate limiting (API key mode only)
- `providers/openai.py:82` - Rate limiting for all operations

### Google Cloud Authentication
**Managed by**: `core/gcloud_utils.py`
**Integration Points**:
- `providers/google.py:45` - Lazy initialization for Google Cloud auth
- `gui/main_window.py:1168` - Auth mode selection and persistence
- `gui/main_window.py:2678` - Cached auth status display
- `core/config.py:110` - Auth validation state persistence

### Provider System
**Factory**: `providers/__init__.py:get_provider()`
**Implementations**:
- `providers/google.py:GoogleProvider` - With Google Cloud auth support
- `providers/openai.py:OpenAIProvider` - With rate limiting
- `providers/stability.py:StabilityProvider`
- `providers/local_sd.py:LocalSDProvider`
**Consumers**:
- `gui/workers.py:30` - Generation worker
- `cli/runner.py:133` - CLI generation

### Template System
**Definitions**: `templates/__init__.py`
**Parser**: `core/utils.py:284` - parse_template_placeholders()
**Consumers**:
- `gui/main_window.py:671` - Templates tab with improved UI
- `gui/dialogs.py:145` - Placeholder input
- `cli/parser.py:82` - Template CLI args

### Image Management
**Output Directory**: `core/utils.py:79` - images_output_dir()
**Path Validation**: `core/security.py:34` - is_safe_path()
**Metadata Sidecars**: `core/utils.py:97` - write_image_sidecar()
**History Scanning**: `core/utils.py:217` - scan_disk_history()
**Consumers**:
- `gui/main_window.py:107` - Load history
- `cli/runner.py:209` - Save images with validation

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
- `keyring>=24.0.0` - Secure key storage

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

### CHANGELOG.md
**Path**: `CHANGELOG.md`
**Purpose**: Version history and release notes
- Documents changes from v0.3.0 to v0.9.3
- Follows Keep a Changelog format
- Tracks features, improvements, and security updates

### CLAUDE.md
**Path**: `CLAUDE.md`
**Purpose**: Instructions for Claude AI assistant
- Project overview and context
- Key commands and usage
- Architecture documentation
- Development guidelines
- Version management locations

### README.md
**Path**: `README.md`
**Purpose**: User documentation
- Installation instructions
- Usage examples
- API key setup
- Feature documentation
- Troubleshooting guide
- Changelog (v0.9.3)

### Plans/ImageAI-VideoProject-PRD.md
**Path**: `Plans/ImageAI-VideoProject-PRD.md`
**Purpose**: Video project feature specification
- Lyrics-to-video storyboard pipeline
- AI-powered prompt generation with LLM support
- Comprehensive version history system
- Gemini Veo API integration for video generation
- Local FFmpeg video assembly option
- Multi-provider LLM support (cloud and local)

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

#### Singleton Pattern
**Implementation**: `core/security.py` global instances
**Purpose**: Single instances of security utilities across application

### Architectural Principles

#### Separation of Concerns
- **CLI** - Command-line interface logic
- **GUI** - Graphical interface and widgets
- **Core** - Business logic, utilities, and security
- **Providers** - External API integrations

#### Dependency Injection
- Providers receive configuration via constructor
- No hard-coded API keys or settings
- Configuration managed centrally with keyring support

#### Lazy Loading
- Providers loaded only when needed
- Google Cloud auth initialized on first use
- Import errors handled gracefully
- Optional dependencies isolated
- Provider list cached after first load

#### Security First
- Path traversal prevention in all file operations
- API keys stored in system keyring when available
- Rate limiting prevents API abuse
- Input validation throughout
- Config migration utilities for secure key storage

## Development Guidelines

### Adding New Providers

1. **Create Provider Class** (`providers/new_provider.py`)
   - Inherit from `ImageProvider`
   - Implement all abstract methods
   - Handle authentication and generation
   - Add rate limiting if needed

2. **Register Provider** (`providers/__init__.py`)
   - Add import with error handling
   - Register in `_get_providers()`

3. **Add Constants** (`core/constants.py`)
   - Add to `PROVIDER_MODELS`
   - Add to `PROVIDER_KEY_URLS`

4. **Security Integration**
   - Use `rate_limiter.check_rate_limit()` for API calls
   - Store keys with `secure_storage.store_key()`
   - Validate paths with `path_validator.is_safe_path()`

5. **Update UI** (`gui/main_window.py`)
   - Provider will auto-appear in dropdown
   - Add provider-specific UI if needed

### Code Style Guidelines

- Use type hints for all function parameters
- Document classes and methods with docstrings
- Handle errors with specific exception types (not generic Exception)
- Use Path objects for file operations
- Follow PEP 8 naming conventions
- Validate all user inputs

### Testing Guidelines

- Test each provider independently
- Verify API key validation with keyring
- Test Google Cloud authentication flow
- Test generation with various parameters
- Check error handling and recovery
- Validate metadata sidecar creation
- Test rate limiting behavior
- Run migration scripts in dry-run mode first

### Performance Considerations

- Lazy load heavy dependencies
- Cache provider instances and model lists
- Use threading for long operations
- Stream large images efficiently
- Minimize API calls with rate limiting
- Initialize Google Cloud auth only when needed
- Debounce UI updates (image resizing)

### Security Best Practices

- Never log API keys
- Store keys in system keyring when available
- Validate all paths before file operations
- Sanitize filenames thoroughly
- Use HTTPS for all API calls
- Implement rate limiting for API providers
- Handle authentication failures gracefully
- Clear sensitive data from memory after use
- Run secure_keys.py on Windows for key encryption
- Use migrate_config.py to update old configurations