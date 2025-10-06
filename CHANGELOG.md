# Changelog

All notable changes to ImageAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.20.1] - 2025-01-06

### Fixed
- **Video Tab Image Generation**: Fixed critical API key retrieval issue preventing image generation in video projects
  - Refactored video generation to use fresh ConfigManager instance like image tab
  - Bypassed provider cache to ensure proper client initialization with `use_cache=False` parameter
  - Now calls providers directly instead of through ImageGenerator wrapper
  - Fixed Scene.images storage to use ImageVariant objects instead of raw Path objects
  - Fixed error handler indentation issue in workspace_widget.py
  - Successfully restored corrupted project file from backup

### Notes
- Video generation is not fully functional but still in active development
- Some advanced video features remain incomplete

## [0.20.0] - 2025-09-29

### Added
- **Use Current Image Feature**: New functionality to use the currently displayed image as reference
- **Enhanced Shortcut Visibility**: Improved keyboard shortcut hints and display
- **History Widget Standardization**: All dialogs now use unified DialogHistoryWidget for consistent history management
- **History Migration Tool**: Script to migrate old JSON history files to new format (`migrate_history.py`)
- **History Double-Click Restore**: Double-clicking history items now restores the full context without creating duplicates
- **Midjourney Provider**: New provider with embedded web interface for manual Midjourney image generation
  - Automatically builds and copies slash commands to clipboard
  - Opens embedded web browser (or external browser as fallback)
  - Supports all Midjourney parameters (model versions, stylize, chaos, weird, etc.)
- **Midjourney Download Watcher**: Intelligent system to automatically detect and associate downloaded Midjourney images
  - Monitors Downloads folder for new images when enabled
  - Smart confidence scoring based on timing, filename patterns, and session tracking
  - Auto-accepts high-confidence matches (configurable threshold)
  - Shows confirmation dialog for medium/low confidence matches with image preview
  - Tracks multiple concurrent Midjourney sessions
  - Automatically saves images to output directory with proper metadata

### Changed
- **Resolution Handling Improvements**:
  - Improved Gemini resolution handling and aspect ratio logic
  - Scale Google image resolutions to max 1024px proportionally
  - Add robust resolution handling and UI improvements
- **Button Layout Reorganization**:
  - Renamed "Reference Image" button to "Ask About Image" for clarity
  - Moved "Enhance" button next to "Generate Prompts" for better workflow grouping
  - Improved button naming consistency across the interface
- **Dialog History Improvements**:
  - Enhanced Prompt, Ask About Image, and Ask About Prompt dialogs now use DialogHistoryWidget
  - History items restore both input and output when double-clicked
  - Added status console output showing restored history details
  - Fixed platform-specific path handling for Windows/Linux/macOS

### Added
- **Midjourney Auto-Import Downloaded Images**:
  - Automatically imports downloaded Midjourney images when dialog closes
  - Matches images by prompt keywords in filename (no time limit needed)
  - Manual import button also available for on-demand imports
  - Creates proper metadata files with prompt, command, and provider info
  - Auto-refreshes history after import

### Fixed
- **Midjourney Login and Web Interface**:
  - Fixed infinite recursion loop when clicking login button
  - Fixed OAuth authentication flow getting interrupted by premature reloads
  - Fixed session cookies not persisting across dialog instances (added shared persistent QWebEngineProfile)
  - Fixed keyboard input not working in embedded web view (added proper focus policies)
  - Fixed incorrect command format showing Discord `/imagine prompt:` prefix in web UI
  - Fixed download button not working (added proper download request handler with state tracking)
- **History Tab Issues**:
  - Fixed history not loading in Generate Prompts dialog
  - Fixed DialogHistoryWidget using incorrect Linux paths on Windows
  - Fixed double-click creating duplicate history entries
  - Fixed attribute errors in Enhanced Prompt and Reference Image dialogs

## [0.19.1] - 2025-09-22

### 🐛 Fixed
- **History Tab Issues**:
  - Fixed prompt not restoring when clicking history items - corrected data retrieval from table's UserRole storage
  - Fixed history not refreshing when switching tabs - added automatic refresh on tab change
  - Fixed Unicode characters in prompts not displaying - added `ensure_ascii=False` to JSON serialization
  - Fixed thumbnails not displaying - simplified delegate data access and stored image path directly in cell

### ✨ Added
- **History Tab Enhancements**:
  - Implemented thumbnail caching system with LRU eviction (200 image cache)
  - Added custom QStyledItemDelegate for owner-draw thumbnail rendering
  - Improved performance with cached 64×64 pixel thumbnails
  - Added single-click prompt restoration from history items

### 🎨 UI Improvements
- **Image Settings Layout**:
  - Reorganized layout - moved quality selector next to aspect ratio and social sizes
  - Reference image settings converted to collapsible flyout panel
  - Made Reference Image flyout text consistent with other flyouts (removed bold)
  - Reduced keyboard shortcut hint font size from 11px to 9px for better visual balance
  - Fixed image redraw when panels expand/collapse

### ⚡ Performance
- **Startup Improvements**:
  - Added loading progress display showing "Loading image metadata... (n/total)"
  - Progress updates every 10 images for better user feedback
  - Cost display now rounds to cents ($0.03 instead of $0.0300)

## [0.19.0] - 2025-09-20

### ✅ Added Features
- 🎨 **Reference Image Analysis Dialog** (`gui/reference_image_dialog.py` - 742 lines)
  - Upload and analyze images to generate detailed descriptions
  - Customizable analysis prompts
  - Option to copy descriptions directly to main prompt
  - Full LLM integration with all providers

- 📚 **Reusable History Widget** (`gui/history_widget.py` - 259 lines)
  - Persistent history saved to disk
  - Export history to JSON
  - Search and filter capabilities
  - Double-click to reload previous conversations

- ✨ **Enhanced Ask Dialog**: Complete redesign with new features
  - "Ask AI Anything" mode - works without a prompt for general questions
  - Editable prompt field with clear Edit/Save/Reset controls
  - Continuous conversation mode with context retention
  - Conversation history with detail view
  - Different quick questions based on context
  - Keyboard shortcuts (Ctrl+E for edit mode)

- 🎯 **Dialog Improvements**: Major enhancements across all LLM dialogs
  - Added Ctrl+Enter shortcut to all dialogs for quick submission
  - Removed max token settings - let models decide response length
  - Added status console history with visual separators
  - Tab-based interfaces with History tabs

### 🐛 Fixed
- **Google Provider**:
  - Fixed 1:1 aspect ratio handling - no longer adds dimensions to prompt for square images
  - **Canvas Centering Fix**: When reference image aspect ratio doesn't match requested ratio, now creates a transparent canvas with the target aspect ratio and centers the reference image within it. This forces Gemini to generate images with the correct aspect ratio instead of following the reference image's aspect ratio
- **Prompt Generation Dialog**: Now starts on Generate tab instead of History
- **Dialog Settings Persistence**: Fixed reasoning/verbosity settings not being saved
- **History Tab**:
  - Fixed incorrect sorting and now shows full prompts
  - Added 60x60 pixel image thumbnails for visual reference
- **Main Window**: Fixed auto-insertion of dimensions for Google square images

### 🔧 Changed
- **UI Layout**: Reordered AI buttons: Generate Prompts → Reference Image → Enhance → Ask
- **Ask Dialog Access**: Can now open with empty prompt for general AI assistance
- **Prompt Editing**: Added explicit edit mode with visual feedback
- **Quick Questions**: Dynamic questions that change based on context
- **Status Consoles**: Enhanced with persistent history and better formatting
- **Social Media Sizes**: Added label display showing selected platform and type

### 📁 File Reorganization
- Moved `Notes/Development.md` → `Plans/Development.md`

### 📊 Statistics
- **14 files changed**
- **2058 insertions(+)**, **764 deletions(-)**
- **2 new files created**
- **Net gain: ~1294 lines**

## [0.18.2] - 2025-09-18

### Changed
- **Google Provider Resolution Handling**: Improved resolution scaling for Gemini API
  - Now correctly scales resolutions proportionally when either dimension exceeds 1024px
  - Maintains aspect ratio when scaling down for API compatibility
  - Automatically scales back up to requested dimensions after generation
  - Added comprehensive logging of resolution transformations

### Fixed
- **Resolution Scaling Logic**: Fixed issue where only width was checked for >1024px threshold
  - Now properly checks both width and height dimensions
  - Ensures consistent scaling regardless of orientation (portrait/landscape)

## [0.18.1] - 2025-09-18

### Fixed
- **Google Provider Resolution Bug**: Fixed issue where images with max dimension exactly 1024px (e.g., 1024×576) were not being post-processed to match requested dimensions
  - Now correctly stores target dimensions for all requests
  - Post-processes any Gemini output that doesn't match requested size
  - Ensures consistent aspect ratio handling regardless of scale factor

## [0.18.0] - 2025-09-17

### Changed
- **Google Provider Resolution Handling**: Enhanced to proportionally scale image resolutions to max 1024px
  - Automatically scales down larger resolutions for Gemini API compatibility
  - Scales back up to original requested dimensions after generation
  - Maintains aspect ratio throughout the process

## [0.17.0] - 2025-09-17

### Added
- **AI-Powered Upscaling** (Local and Free)
  - Integrated Real-ESRGAN for high-quality image upscaling
  - Support for multiple upscaling models (RealESRGAN_x4plus, RealESRGAN_x4plus_anime_6B, etc.)
  - Automatic model download and management
  - Works with images of any size - no provider limitations
  - Seamless integration with generation workflow
  - Upscaling indicator shows when dimensions exceed provider limits
- **Enhanced Prompt Tools**
  - Improved prompt enhancement dialog with better LLM integration
  - Enhanced prompt question dialog with status console
  - Better error handling and fallback mechanisms
  - Comprehensive logging of all LLM interactions
- **Improved Search Functionality**
  - Enhanced find dialog with better text highlighting
  - Proper case-sensitive and whole-word search support
  - Keyboard shortcuts (Ctrl+F, F3, Shift+F3)
- **Help Tab Improvements**
  - Better navigation with screenshot gallery
  - Improved markdown rendering
  - Fixed back/forward navigation between documents
- **Image Cropping Dialog**
  - New image crop functionality
  - Support for social media sizes
  - Visual preview of crop area
- **Discord Integration**
  - Added Discord server information
  - Community support links

### Changed
- Improved settings widgets with better organization
- Enhanced status console logging across all dialogs
- Better error messages and user feedback
- Updated documentation with reference images

### Fixed
- Fixed AI upscaling dependencies and runtime installation
- Improved LLM response parsing with robust JSON extraction
- Better handling of empty LLM responses
- Fixed various UI consistency issues

## [0.16.2] - 2025-09-16

### Fixed
- **Google Gemini Aspect Ratio Support** (Complete Implementation)
  - For non-1:1 aspect ratios, dimensions are now properly sent in parentheses (e.g., "(1024x576)") per CLAUDE.md spec
  - When dimensions exceed 1024px, they are automatically scaled down proportionally for Gemini
  - After generation, images are automatically upscaled back to the target resolution
  - Added comprehensive logging for all resolution operations
- **Aspect Ratio Calculation Logic**
  - Fixed recursion prevention that was blocking height recalculation when aspect ratio changed
  - Width/height spinners now properly update when switching between aspect ratios
  - Added `force` parameter to ensure recalculation happens during aspect ratio changes
- **Upscaling Visibility Detection**
  - Added detailed logging for upscaling widget visibility changes
  - Logs now show aspect ratio, target dimensions, provider limits, and visibility decisions
  - Each dimension check is logged separately for debugging

### Added
- **Smart Gemini Scaling**
  - Automatic scaling: If width or height > 1024, scales proportionally so max = 1024
  - Example: 2048×1152 → 1024×576 sent to Gemini → 2048×1152 after upscaling
  - Preserves aspect ratio during scaling operations
- **Enhanced Logging**
  - "Scaling down for Gemini: 2048x1152 -> 1024x576 (factor: 0.500)"
  - "Sending to Gemini with aspect ratio 16:9: prompt ends with '(1024x576)'"
  - "Upscaling Gemini output back to target: 2048x1152"
  - Logs for square images: "Sending to Gemini with square aspect (1:1): 1024x1024"
- **Dimension Event Tracking**
  - WIDTH/HEIGHT SPINBOX VALUE CHANGED events logged
  - ASPECT RATIO CHANGED events with old/new values
  - Complete upscaling visibility check logs with separators
- **Comprehensive API Request Logging**
  - All requests to Google Gemini API now logged with full prompt and parameters
  - All requests to OpenAI DALL·E API logged with model, prompt, size, quality, style
  - Complete request/response logging for all LLM conversations already in place
- **Image Save Status Enhancement**
  - Console now shows dimensions when saving: "Saved 1024×768 image to: filename.png"
  - Provides immediate visual confirmation of output resolution

### Changed
- Resolution selector now forces recalculation when aspect ratio changes
- Width/height change handlers properly update the opposite dimension
- Improved signal connection to use lambda functions for proper parameter passing

## [0.16.1] - 2025-09-16

### Fixed
- **Resolution and Aspect Ratio System** (Complete Refactor)
  - Width/Height spinners now properly update proportionally when aspect ratio is selected
  - When entering width, height automatically calculates based on aspect ratio (and vice versa)
  - Upscaling selector now properly shows when EITHER dimension exceeds provider maximum:
    - Google: > 1024 pixels
    - OpenAI: > 1792 pixels
    - Stability: > 1536 pixels
  - Fixed initialization order - aspect ratio is now set before dimensions are calculated
  - Fixed missing `valueChanged` signal connections that prevented upscaling from triggering
- **Dimension Handling**
  - Added proper dimension prompting to Google provider (e.g., "1024x576 resolution, 16:9 aspect ratio composition")
  - Fixed cropping logic - only crops when explicitly in aspect ratio mode
  - Added `crop_to_aspect` parameter to control when cropping should occur
- **UI Improvements**
  - Resolution combo box moved below width/height spinners for better flow
  - Added "Reset" button to set dimensions to provider maximum for current aspect ratio
  - Persistent settings - aspect ratio and dimensions saved/restored between sessions
  - Upscaling settings now persist across sessions (saved in config)
- **Video Project Tab**
  - Fixed `AttributeError: 'dict' object has no attribute 'get_api_key'` in workspace widget
  - Config is now properly accessed as dictionary

### Changed
- Width/Height spinners no longer use "Auto" - they always show calculated values
- When typing in one dimension field, the other immediately updates proportionally
- Clearer upscaling messages showing provider maximum capabilities

## [0.16.0] - 2025-09-15

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

## [0.15.1] - 2025-09-14

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

## [0.15.0] - 2025-09-14

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

## [0.14.0] - 2025-09-14

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

## [0.13.1] - 2025-09-14

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

## [0.13.0] - 2025-09-13

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

## [0.12.0] - 2025-09-13

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

## [0.11.0] - 2025-09-13

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

## [0.10.5] - 2025-09-13

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

## [0.10.4] - 2025-09-12

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

## [0.10.3] - 2025-09-12

### Added
- **Custom Aspect Ratio Input** - New manual input field for entering custom aspect ratios
  - Supports ratio format (e.g., "16:10") and decimal format (e.g., "1.6")
- **Smart Mode Switching** - Clear visual indicators showing whether aspect ratio or resolution is controlling dimensions
- **Improved UI Feedback**
  - Green badge for aspect ratio mode, blue badge for resolution mode
  - Auto mode in resolution selector calculates from aspect ratio
  - Selecting a manual resolution automatically clears aspect ratio selection
- **Provider-Aware Calculations** - Resolution automatically calculated based on provider capabilities (DALL·E, Gemini, Stability)

## [0.10.2] - 2025-09-12

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

## [0.10.1] - 2025-09-11

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

## [0.10.0] - 2025-09-11

### Added
- **Complete Video Pipeline** - Full implementation of text-to-video generation workflow
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
- **Workspace and History Tabs** - Dual-tab interface for editing and version control
- **Event Sourcing** - Complete project history with time-travel restoration
- **LLM Integration** - Multi-provider prompt enhancement (GPT-5, Claude, Gemini)
- **Scene Management** - Interactive storyboard with timing controls
- **Image Generation** - Batch generation with caching and thumbnails
- **FFmpeg Rendering** - Slideshow video with Ken Burns effects and transitions
- **Version Control** - Restore projects to any point in history
- **Audio Support** - Audio track integration with sync options
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

## [0.9.4] - 2025-09-11

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

## [0.9.3] - 2025-09-11

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

## [0.9.2] - 2025-09-08

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

## [0.4.0] - 2025-08-29

### Added
- Initial version tracking
- Core functionality implementation

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