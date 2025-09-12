# Changelog

All notable changes to ImageAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.3] - 2025-01-12

### Added
- **Custom Aspect Ratio Input** - New manual input field for entering custom aspect ratios
  - Supports ratio format (e.g., "16:10") and decimal format (e.g., "1.6")
  - Input validation ensures only valid formats are accepted
  - Custom button with visual indicator when active
- **Resolution/Aspect Ratio Mode Indicator** - Clear visual feedback showing which control is active
  - Green badge with "Using Aspect Ratio" when AR controls dimensions
  - Blue badge with "Using Resolution" when manual resolution is selected
  - Info text shows current mode and calculated values

### Changed
- **Enhanced Aspect Ratio Selector** - Improved interaction between aspect ratio and resolution controls
  - Selecting an aspect ratio automatically switches resolution to "Auto (from AR)" mode
  - Selecting a manual resolution automatically deselects all aspect ratio buttons
  - Resolution selector shows calculated resolution when in auto mode
- **Smart Resolution Calculation** - Provider-aware resolution calculation from aspect ratios
  - DALL·E 3: Maps to supported sizes (1024×1024, 1792×1024, 1024×1792)
  - Google Gemini: Maintains square (1:1) limitation
  - Stability AI: Maps to optimal SDXL resolutions

### Fixed
- Generation parameters now correctly send either aspect ratio OR resolution, not both
- Resolution selector properly updates when aspect ratio changes
- Clear visual feedback prevents confusion about which setting is controlling dimensions

## [0.10.1] - 2025-01-11

### Changed
- Cleaned up development notices from documentation
- Updated video feature status from "Coming Soon" to "Planned" for Veo integration
- Enhanced README documentation with comprehensive video feature details
- Added comprehensive pricing comparison table with free tier details

### Fixed
- Version number properly incremented to reflect stable UI implementation
- Google Gemini aspect ratio handling - now correctly indicates only square (1:1) images are supported
- Disabled aspect ratio selector for Google provider with explanatory tooltip
- Updated provider code to add aspect ratio hints to prompts for Google (best effort)

### Removed
- Removed Imagen 3/4 models from UI - these require Vertex AI access, not available through Gemini API
- Note: Imagen models (imagen-3.0-generate-002, imagen-4.0-generate-001) require Google Cloud Vertex AI, not the standard Gemini API used by ImageAI

### Known Limitations
- Google Gemini (Nano Banana) only generates square images regardless of aspect ratio settings

## [0.10.0] - 2025-01-11

### Added
- **Video Project Feature** - New tab for creating AI-powered videos from text/lyrics
  - Project management system with save/load functionality
  - Multiple input formats: timestamped lyrics, structured text, plain text
  - Automatic scene generation with intelligent timing allocation
  - AI-powered prompt enhancement using multiple LLM providers (OpenAI, Claude, Gemini, Ollama)
  - Audio track support with volume/fade controls (files linked, not copied)
  - Storyboard interface for scene management
  - Export options for both local slideshow and Gemini Veo (prepared for implementation)
- **Tab Icons** - Added visual icons to all tabs for better UI navigation
  - 🎨 Generate, 🎬 Video, 📝 Templates, ⚙️ Settings, ❓ Help, 📜 History
- **Video Dependencies** - Added new requirements for video features:
  - Jinja2 for template processing
  - moviepy for video assembly
  - litellm for unified LLM provider interface
  - anthropic for Claude API support

### Changed
- Improved tab visual design with icons for better user experience
- Updated project structure to support modular video features

### Technical
- Created comprehensive video module architecture (`core/video/`, `gui/video/`)
- Implemented data models for video projects with full serialization
- Added template system for prompt generation
- Built foundation for FFmpeg slideshow and Veo API integration

### Implementation Status
- Video UI and project management fully implemented
- Scene generation and LLM enhancement operational  
- FFmpeg slideshow rendering prepared
- Veo API integration planned for future release

## [0.9.3] - 2025-09-09

### Added
- Configuration migration script (`migrate_config.py`) for updating old config formats
- API key security script (`secure_keys.py`) for Windows Credential Manager integration
- Utility scripts documentation in README

### Changed
- Removed legacy `api_key` field from config.json root level
- Fixed incorrect `keys.<provider>` structure in configuration
- All API keys now properly stored under `providers.<provider>.api_key`
- Config structure cleaned up for consistency

### Security
- API keys can now be encrypted using Windows Credential Manager
- Automatic keyring storage attempted when available
- Fallback to config.json only when keyring unavailable

## [0.9.2] - 2025-09-09

### Security
- Added secure API key storage using system keyring (optional)
- Implemented path traversal validation for file operations  
- Added rate limiting for API calls (configurable per provider)

### Improved
- Google Cloud auth state now persists between sessions
- Settings tab shows cached auth status immediately on load
- Fixed "Check Status" button functionality
- Lazy initialization for Google Cloud provider
- Replaced generic Exception catches with specific exception types
- Improved error handling throughout the codebase
- Better subprocess exception handling

## [0.9.1] - 2025-09-08

### Added
- Project Save/Load functionality with full UI state preservation
- Auto-reload last displayed image at startup
- Enhanced project files (.imgai) containing image and all settings
- File menu with project management options
- Google Cloud authentication support
- Template UI with better error handling

### Improved
- Session persistence across application restarts
- Track last displayed image whether generated or loaded from history
- Fixed various UI bugs

## [0.9.0] - 2025-09-07

### Added
- Comprehensive UI state persistence - all settings saved between sessions
- Enhanced history display with detailed table (date, time, provider, model, resolution, cost)
- Automatic cost tracking and display for all generations
- Settings Tab with comprehensive application preferences
- Template Tab with community template access
- Enhanced Image Settings panel with aspect ratio and resolution selectors
- Template preview and generation capabilities
- Smart placeholder substitution in templates
- Interactive Help tab with embedded documentation
- Advanced settings for Local SD (steps, guidance scale)

### Improved
- Fixed quality radio button and prompt rewriting checkbox persistence
- All UI elements now properly save and restore their state
- Refactored code architecture with modular provider system
- Enhanced metadata sidecar files with complete generation details
- Improved cross-platform compatibility

### Ready for Integration
- Stability AI provider implementation

## [0.8.0] - 2025-09-07

### Added
- Version metadata tags (__version__, __author__, __email__, __license__, __copyright__)
- Display version in GUI title bar as "ImageAI v0.8.0"
- Enhanced CLI --version output with copyright and author information
- Improved package-level metadata access
- Version number prominently displayed in README

## [0.7.0] - 2025-09-06

### Added
- Google Cloud authentication support (Application Default Credentials)
- New `--auth-mode` CLI flag for authentication method selection
- Enhanced GUI Settings with auth mode selector and helper buttons
- Comprehensive API enablement documentation

### Changed
- Improved Windows/PowerShell compatibility
- Project renamed to ImageAI

## [0.6.0] - 2025-08-29

### Added
- OpenAI provider with DALL·E-3 and DALL·E-2 support
- Per-provider API key management
- Provider switching in GUI and CLI

### Improved
- Enhanced error messages and guidance

## [0.3.0] - 2025-08-29

### Added
- Initial public release
- Google Gemini integration
- GUI and CLI interfaces
- Auto-save with metadata sidecars
- Template system

## Notes

### Versioning
- Major version (X.0.0): Breaking changes or major feature additions
- Minor version (0.X.0): New features, backwards compatible
- Patch version (0.0.X): Bug fixes and minor improvements

### Future Releases
See [Plans/](Plans/) directory for upcoming features and roadmap.