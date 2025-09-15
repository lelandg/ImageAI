# Changelog

All notable changes to ImageAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.16.0] - 2025-01-15

### Fixed
- **Find Dialog**
  - Fixed `QTextCursor.FindFlag` error in PySide6 by using `QTextDocument.FindFlag`
  - Find dialog now starts with clean state (empty search, disabled buttons)
  - Search text cleared on close for fresh start next time
  - Fixed button enable/disable state management
  - Proper case-sensitive and whole-word search support
- **Help Viewer Navigation**
  - Fixed back button being disabled when first navigating to Changelog
  - Now properly adds README to history before navigating away
  - Back/Forward buttons correctly reload markdown files when navigating between documents
- **Qt Warning Suppression**
  - Suppressed benign "Unable to open monitor interface" errors when displays are off
  - Filtered out window geometry warnings during resize
  - Added custom Qt message handler for cleaner console output

### Changed
- **Requirements.txt**
  - AI upscaling modules (torch, torchvision, etc.) now commented out
  - These are installed at runtime via GUI when needed
  - Reduces initial installation size significantly

## [0.15.1] - 2025-01-14

### Added
- **Advanced Reference Image Controls** (Google Gemini)
  - Style dropdown: Natural blend, Blurred edges, In circle, In frame, As background, etc.
  - Position dropdown: Auto, Left, Center, Right, Top, Bottom, corners
  - Auto-insert instructions into prompt based on selections
  - Preview of text that will be inserted
  - Resolution info automatically added when available
  - Settings persist across sessions
- **Improved Reference Image Workflow**
  - Instructions automatically prepended to prompt
  - Visual preview shows what will be inserted
  - Natural language instructions that Gemini understands
  - Tips displayed to help users

### Changed
- Reference image preview now shows alongside control options
- Console shows auto-inserted instructions in purple

## [0.15.0] - 2025-01-14

### Added
- **Reference Image Support** (Google Gemini)
  - Select a starting image to guide generation
  - Visual preview thumbnail in Image Settings panel
  - Enable/disable checkbox for quick toggling
  - Clear button to remove reference image
  - Automatic save/restore from settings
  - Provider detection (currently Google Gemini only)
- **Enhanced Find Dialog**
  - Fixed text highlighting to preserve original colors
  - Yellow highlight for current match
  - Orange highlight for other matches
  - Ctrl+F tip displayed above prompt box
  - F3/Shift+F3 for next/previous navigation

### Changed
- **Compact UI Layout**
  - All prompt buttons now on single row for space efficiency
  - Shortened button labels (Enhance, Ask, Save, Copy)
  - Generate button moved inline with prompt tools
  - Improved button spacing and organization

### Fixed
- Find dialog no longer causes black-on-black text
- Text color preservation when clearing search highlights
- Proper background-only highlight clearing

## [0.14.0] - 2025-01-14

### Added
- **Real-ESRGAN AI Upscaling Integration**
  - State-of-the-art AI upscaling support with Real-ESRGAN
  - Automatic NVIDIA GPU detection (CUDA acceleration for RTX cards)
  - Smart upscaling when target resolution exceeds provider limits
  - Multiple upscaling methods: AI, Lanczos, Stability API, or none
- **GUI Installation System**
  - One-click installation directly from the upscaling widget
  - Progress tracking with real-time output and elapsed time
  - Automatic PyTorch version selection (CUDA vs CPU)
  - Compatible version pinning to avoid dependency conflicts
  - Automatic requirements.txt updates with GPU info
  - System tray notifications on completion
- **Installation Features**
  - Detects RTX 4090 and other NVIDIA GPUs automatically
  - Installs CUDA-accelerated PyTorch for GPU users
  - CPU-only fallback for systems without NVIDIA GPUs
  - Time estimates: ~30 seconds (cached) to 3-5 minutes (fresh)
  - Disk space: ~7GB (mostly PyTorch)

## [0.13.1] - 2025-01-14

### Added
- **Full GPT-5 Support**
  - Fixed model name to use `gpt-5-chat-latest`
  - Correctly uses `max_completion_tokens` parameter (not `max_output_tokens`)
  - Added reasoning effort controls (low/medium/high) for GPT-5
  - Added verbosity controls (low/medium/high) for GPT-5
- **Enhanced Prompt Question Dialog**
  - User-adjustable temperature and max tokens controls
  - GPT-5-specific parameters auto-show when GPT-5 selected
  - Session persistence saves all settings including GPT-5 params
  - Improved empty response handling with fallback messages
  - Better console window expansion with splitters

### Changed
- **Video Tab Updates** - Same GPT-5 fixes applied to video prompt enhancement

## [0.13.0] - 2025-01-13

### Added
- **Reorganized Settings Tab** - All provider API keys now visible simultaneously
  - Dedicated sections for Image Providers, API Keys, and Google Cloud Auth
  - Scrollable interface for better organization on smaller screens
  - Single "Save & Test" button saves all keys and tests current provider
- **LLM Logging Option** - New checkbox in settings to enable LLM interaction logging
  - Logs all LLM prompts and responses when enabled
  - Useful for debugging prompt enhancement issues
- **Width/Height Specification** - Custom width/height input when using aspect ratios
  - Target Width and Target Height spinboxes in resolution selector
  - Works alongside aspect ratio selection for finer control
  - Google provider uses dimensions to add resolution hints to prompts

### Changed
- **Full Prompt Display** - Prompts no longer truncated in console and logs
  - Complete prompts shown in status window
  - Full prompt text logged for debugging
- **Settings Layout** - Improved organization with grouped sections
  - All API keys visible at once (no provider switching needed)
  - Better visual hierarchy with QGroupBox sections
  - Consistent layout across all providers

### Fixed
- **Empty Window Popup** - Fixed parent widget issues causing empty window on startup
  - All QWidget and QLineEdit instances now have proper parents
  - No more floating windows during initialization
- **Prompt Enhancement Errors** - Fixed NoneType errors in enhancement
  - Better error handling when LLM returns None
  - Proper fallback when enhancement fails
- **API Key Loading** - Fixed backward compatibility with old config format
  - Supports loading from multiple config key locations
  - Preserves existing API keys during migration
- **Auto-crop Algorithm** - Fixed logic errors in border detection
  - Algorithm now properly identifies uniform borders
  - Currently disabled pending further testing

## [0.12.0] - 2025-01-13

### Added
- **Social Media Sizes Dialog** - New dialog for quick access to platform-specific image dimensions
  - Comprehensive list of sizes for Instagram, Twitter/X, Facebook, LinkedIn, YouTube, TikTok
  - One-click application of social media dimensions to image generation
  - Searchable and categorized by platform
  - "Social Sizes..." button next to resolution selector for easy access
- **Comprehensive Keyboard Shortcuts** - Full keyboard accessibility
  - Alt+key mnemonics for all buttons (Alt+G to Generate, Alt+S to Save, etc.)
  - Ctrl+Enter to generate from anywhere, even while typing in prompt field
  - Ctrl+S to save image, Ctrl+Shift+C to copy to clipboard
  - F1 for instant help access
  - All shortcuts shown in button tooltips
- **Protobuf v5+ Compatibility** - Fixed AttributeError with MessageFactory.GetPrototype
  - Added runtime compatibility patch for protobuf v5 changes
  - Suppresses initialization errors during startup
  - Allows installation with latest protobuf versions
  - No more version conflicts with other packages

### Changed
- **Provider Improvements**
  - Google Gemini (Nano Banana) now supports aspect ratios via prompt specification
  - Resolution and aspect ratio settings are preserved when switching providers
  - No more forced 1:1 aspect ratio for Google - all ratios now work
- **UI Improvements**
  - Fixed status console auto-resizing - now stays at user-set size
  - Removed white lines between console messages for cleaner output
  - Console starts at fixed 100px height, resizable via splitter only
- **Code Organization**
  - Added comprehensive code map documentation at `Docs/CodeMap.md`
  - Created code map generator agent for maintaining navigation
  - Updated CLAUDE.md with modularized structure information

## [0.11.0] - 2025-01-13

### Added
- **Global LLM Provider System** - Unified LLM provider selection across Image and Video tabs
  - Support for OpenAI (GPT-5), Claude, Gemini, Ollama, and LM Studio
  - Automatic model detection and population per provider
  - Bidirectional syncing between Image and Video tabs
  - Persistent LLM provider settings across sessions
- **Prompt Enhancement** - One-click prompt improvement using selected LLM
  - Works on both Image and Video tabs
  - Shows original and enhanced prompts side-by-side
  - Integrated with the new console output for progress tracking
- **Console Output Window** - New terminal-style status console
  - Color-coded messages (green for success, red for errors, blue for progress)
  - Timestamped entries for all operations
  - Visual separators between operations
  - Resizable with vertical splitter
  - Shows LLM interactions and provider communications

### Changed
- **UI Improvements**
  - Added status bar for real-time feedback
  - Startup progress messages
  - Lazy loading for Video tab (faster startup)
  - Improved layout with LLM provider at top of tabs

## [0.10.5] - 2025-01-13

### Added
- **Visual Continuity Features** - New optional features for maintaining consistency across video scenes
  - Provider-specific continuity techniques (Gemini iterative refinement, OpenAI reference IDs, Claude style guides)
  - Checkbox controls to enable/disable continuity and enhanced storyboard generation
  - Automatic aspect ratio hints for Gemini provider
  - Project-level continuity tracking for multi-scene consistency
- **Improved Lyric Enhancement** - Smart detection and processing of lyric lines vs. regular text
  - Lyric-specific prompts create detailed visual scene descriptions
  - Fallback generation ensures all scenes get visual prompts even with empty LLM responses
  - Better handling of short text fragments from song lyrics

### Changed
- **UI Improvements** - New continuity control checkboxes with informative tooltips
- **GPT-5 Confirmed Working** - Full integration tested with OpenAI's GPT-5 model
  - Successful time synchronization using Strict Lyric Timing Contract v1.0
  - Robust fallback handling for prompt enhancement

## [0.10.4] - 2025-01-12

### Added
- **Strict Lyric Timing Contract v1.0** - Implemented standardized format for GPT-5 lyric synchronization
  - No fragmentation - one-to-one mapping between lyrics and timing entries
  - Consistent millisecond integer format
  - Order preservation without reordering
- **Multi-Format LLM Response Handling** - Smart parsing for various GPT-5 response formats
  - Handles `startMs`/`endMs`, `start`/`end` in seconds, and mixed formats
  - Intelligent fragment merging for karaoke-style timing
  - Automatic detection of Strict Contract v1.0 format
- **Gemini Response Optimization** - Adjusted prompts to avoid response size limits
  - Line-level timing for longer songs (>20 lines)
  - Emphasis on including all lyrics in response

### Fixed
- **Critical Scene Table Update Bug** - Resolved indentation issue preventing UI updates after storyboard generation
- **Enhanced Settings Persistence** - All video tab settings now properly saved
  - LLM provider and model selection
  - Image provider and model selection
  - Variants, Ken Burns, transitions, captions settings

## [0.10.3] - 2025-01-12

### Added
- **Custom Aspect Ratio Input** - New manual input field for entering custom aspect ratios
  - Supports ratio format (e.g., "16:10") and decimal format (e.g., "1.6")
- **Smart Mode Switching** - Clear visual indicators showing whether aspect ratio or resolution is controlling dimensions
- **Improved UI Feedback**
  - Green badge for aspect ratio mode, blue badge for resolution mode
  - Auto mode in resolution selector calculates from aspect ratio
  - Selecting a manual resolution automatically clears aspect ratio selection
- **Provider-Aware Calculations** - Resolution automatically calculated based on provider capabilities (DALL·E, Gemini, Stability)

## [0.10.2] - 2025-01-12

### Added
- **Project Browser** - New dialog for easy project management with double-click to open
- **Auto-reload** - Last opened project automatically loads on startup (configurable)
- **MIDI Support** - Fixed MIDI import errors by adding setuptools dependency
- **Enhanced Logging** - Comprehensive error logging with automatic log/project file copying on exit

### Changed
- **UI Improvements**
  - Renamed "Generate" tab to "Image" for clarity
  - Moved Templates tab next to Image tab for better workflow
  - Made Video Project header more compact
  - Added development notice to Video tab

### Fixed
- **Project save/load** - Fixed not preserving lyrics and settings
- **`timing_combo` AttributeError** - Fixed error on project load
- **Error logging** - Added proper error logging for all dialog messages

## [0.10.0] - 2025-01-11

### Added
- **Complete Video Pipeline** - Full implementation of text-to-video generation workflow
- **Workspace and History Tabs** - Dual-tab interface for editing and version control
- **Event Sourcing** - Complete project history with time-travel restoration
- **LLM Integration** - Multi-provider prompt enhancement (GPT-5, Claude, Gemini)
- **Scene Management** - Interactive storyboard with timing controls
- **Image Generation** - Batch generation with caching and thumbnails
- **FFmpeg Rendering** - Slideshow video with Ken Burns effects and transitions
- **Version Control** - Restore projects to any point in history
- **Audio Support** - Audio track integration with sync options

## [0.9.4] - 2025-01-10

### Added
- **Local Stable Diffusion Provider** - Run AI models locally without API keys
  - Automatic model detection from Hugging Face cache
  - Support for SD XL, SD 2.1, SD 1.5 models
  - GPU acceleration with CUDA support
  - Model browser and downloader UI
  - Popular model recommendations with descriptions
  - Progress tracking for model downloads
  - Automatic dependency installation
- **Enhanced Model Management**
  - Cached model detection (~/.cache/huggingface)
  - One-click model installation
  - Size indicators for downloads (1-7GB typical)
  - Support for custom Hugging Face models
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