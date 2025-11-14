# ImageAI — Advanced AI Image Generation

### [ImageAI on GitHub](https://github.com/lelandg/ImageAI) Desktop + CLI for multi‑provider AI image and video generation with enterprise auth, prompt tools, and MIDI‑synced karaoke/video workflows.

**Version 0.25.0**

**See [LelandGreen.com](https://www.lelandgreen.com) for links to other code and free stuff**. _Under construction. Implementing social links soon._ 
- **ChatMaster BBS - The Intersection of Art and AI - Support and Fun: [ChatMaster BBS Discord Server](https://discord.gg/chatmaster)**
- **Facebook Page: [Leland Green Productions](https://www.facebook.com/LelandGreenProductions)**
- **Facebook Group: [The Intersection of Art and AI Community](https://www.facebook.com/groups/4047864425428695)**
 
#### Created primarily with _Antrhopic **Claude Code**_, with PyCharm IDE and AI assistance from Junie (early-on), Codex. Extra Google auth guidance from Gemini CLI.
#### Enterprise-ready with multiple authentication methods and provider support  

## Overview

**ImageAI** is a powerful desktop application and CLI tool for AI image generation, video creation, and professional layout design. It supports multiple providers including Google's Gemini API (with Imagen 3 and Veo 3), OpenAI's DALL·E models, Stability AI's Stable Diffusion, and local Stable Diffusion models. Beyond image generation, ImageAI provides a complete workflow for creating AI-powered videos with MIDI synchronization, karaoke overlays, and a professional layout engine for photo books, comics, and publications. It features enterprise-grade authentication options, secure credential management, and works seamlessly across Windows, macOS, and Linux.

## Table of Contents
- [Project Review & Recommendations](Docs/ProjectReview.md)
- [Requirements](#1-requirements)
- [Authentication Setup](#2-authentication-setup)
- [Installation](#3-installation)
- [Running the Application](#4-running-the-application)
- [Authentication Management](#5-authentication-management)
- [CLI Reference](#6-cli-reference)
- [GUI Features](#7-gui-features)
  - [Image Tab](#image-tab-primary)
  - [Templates Tab](#templates-tab)
  - [Video Tab](#video-tab)
  - [Layout/Books Tab (NEW!)](#layoutbooks-tab-new)
  - [Settings Tab](#settings-tab)
  - [History Tab](#history-tab)
  - [Help Tab](#help-tab)
- [Image Management](#8-image-management)
- [Examples and Templates](#9-examples-and-templates)
- [Advanced Features](#10-advanced-features)
- [Utility Scripts](#11-utility-scripts)
- [Frequently Asked Questions](#12-frequently-asked-questions)
- [Pricing and Cost Comparison](#13-pricing-and-cost-comparison)
- [API Reference](#14-api-reference)
- [Development](#15-development)
- [Changelog](CHANGELOG.md)
- [Screenshots Gallery](#17-screenshots-gallery)

![screenshot_20250915.png](screenshot_20250915.png)

## Key Features

### 🎨 Multi-Provider Support
- **Google Gemini** - Access to latest Gemini models for image generation
- **OpenAI DALL·E** - Support for DALL·E-3 and DALL·E-2 models
- **Stability AI** - Stable Diffusion XL, SD 2.1, and more via API
- **Local Stable Diffusion** - Run models locally without API keys (GPU recommended)
- Easy provider switching in both GUI and CLI
- Support for custom Hugging Face models
- Model browser and downloader for Local SD models
- Popular model recommendations with descriptions

### 🔐 Flexible Authentication
- **API Key Authentication** - Simple setup for individual users
- **Google Cloud Authentication** - Enterprise-ready with Application Default Credentials
- **Hugging Face Authentication** - Built-in token management for model downloads
- Secure credential storage in platform-specific directories

### 🚀 AI Image Upscaling
- **Real-ESRGAN** - State-of-the-art AI upscaling for enhanced image quality
- **GPU Acceleration** - Automatic NVIDIA GPU detection for faster processing
- **GUI Installation** - One-click installation directly from the application
- **Multiple Methods** - Choose between AI upscaling, Lanczos, or cloud services
- Smart upscaling when target resolution exceeds provider capabilities
- Environment variable support for CI/CD integration
- Per-provider API key management

### 💻 Quad Interface
- **Modern GUI** - User-friendly desktop interface built with Qt/PySide6
- **Video Project** - Full-featured 🎬 Video tab for creating AI-powered videos with version control
- **Layout/Books** - 📖 Professional layout engine for photo books, comics, and publications
- **Powerful CLI** - Full-featured command-line interface for automation
- Cross-platform support (Windows, macOS, Linux)
- Responsive layout with resizable panels

### 🎯 Advanced Generation Controls

- **Multiple Reference Images** - Professional multi-reference image support with two modes:
    - **Flexible Mode** (Google Gemini):
      - Unlimited reference images
      - Style transformation and cartoonification
      - Automatic compositing for 2+ images (creates character design sheet)
      - Perfect for: "Convert these photos to cartoon characters"
    - **Strict Mode** (Imagen 3 Customization):
      - Up to 3 reference images with precise control
      - Subject preservation with scene/composition changes
      - Reference types: SUBJECT (person/animal/product), STYLE, CONTROL (canny/scribble/face_mesh)
      - Subject-specific types with optional descriptions
      - Perfect for: Maintaining character consistency across generations
    - **Smart Features**:
      - Multi-select file dialog (add multiple images at once)
      - Flow layout (automatically wraps to fit window)
      - Reference IDs ([1], [2], [3]) for prompt referencing
      - Mode switching with automatic reference limit handling
      - Thumbnail previews with individual controls per reference
      - Per-reference type selectors and descriptions
      - **Edit Mode** - When using a single reference image, enable checkbox to auto-prefix prompt with "Edit this image. Keep everything already in the image exactly the same."
- **Enhanced Aspect Ratio Selector** - Interactive preview rectangles with custom input support:
  - Visual preset buttons for common ratios (1:1, 3:4, 4:3, 16:9, 9:16, 21:9)
  - **Custom aspect ratio input** - Enter any ratio like "16:10" or decimal "1.6"
  - Clear mode indicator showing "Using Aspect Ratio" or "Using Resolution"
  - Automatic resolution calculation based on provider capabilities
- **Smart Resolution System** - Dual-mode resolution control:
  - **Auto mode** - Resolution calculated from selected aspect ratio
  - **Manual mode** - Direct resolution selection overrides aspect ratio
  - Provider-optimized presets (DALL·E, Gemini, Stability AI)
  - Visual feedback showing which mode is active (green for AR, blue for resolution)
  - **Social Media Sizes Dialog** - Quick access to platform-specific image dimensions for Instagram, Twitter/X, Facebook, LinkedIn, YouTube, TikTok, and more
- **Quality & Style Options** - Standard/HD quality, style presets for different looks
- **Batch Generation** - Generate multiple variations at once
- **Cost Estimation** - Real-time cost calculation for all providers
- **Advanced Settings Panel** - Fine-tune generation parameters:
  - Inference steps (1-50)
  - Guidance scale (CFG 0-20)
  - Scheduler selection
  - Seed control for reproducibility
  - Negative prompts
  - Prompt rewriting/enhancement

### 📊 Enhanced History and Tracking
- **Detailed History Table** - View all generations with:
  - Date and time stamps
  - Provider and model used
  - Resolution information
  - Cost tracking
  - Original prompts
- **Session Persistence** - All UI settings saved between sessions
- **Metadata Sidecars** - JSON files with complete generation details
- **Disk History Scanning** - Automatically finds previous generations
- **Quick History Access** - Click to reload prompts and settings

### 🖼️ Smart Features
- Auto-save generated images with metadata sidecars
- Template system with placeholder substitution
- Customizable output paths and filenames
- Auto-copy filename to clipboard option
- Smart filename generation from prompts

### ⌨️ Keyboard Shortcuts & Accessibility
- **Comprehensive keyboard navigation** - Full keyboard control for all features
- **Button mnemonics** - Alt+key shortcuts for all buttons (e.g., Alt+G for Generate)
- **Global shortcuts**:
  - **Ctrl+Enter** - Generate image from anywhere in the Generate tab
  - **Ctrl+S** - Save generated image
  - **Ctrl+Shift+C** - Copy image to clipboard
  - **F1** - Jump to Help tab
- **Text field support** - Ctrl+Enter works even when typing in the prompt field
- **Tooltips** - All buttons show their keyboard shortcuts
- **Screen reader compatible** - Proper labels and navigation order
- Image format detection and optimization
- Preview scaling with aspect ratio preservation

### 🤖 LLM Integration (NEW!)

- **Global LLM Provider Selection** - Unified provider and model selection across tabs:
    - Provider dropdown syncs between Image and Video tabs
    - Model list updates automatically per provider
    - Remembers selections between sessions
    - Project-specific provider settings
- **Multi-Provider Support** - OpenAI GPT-5, Claude, Gemini, Ollama, LM Studio
  - **GPT-5 Model Support** - `gpt-5-chat-latest` (auto-updating to newest version)
  - Correctly uses `max_completion_tokens` parameter for GPT-5 and GPT-4+ models
  - **GPT-5 Specific Controls** (UI ready for future API support):
    - Reasoning effort selector (low/medium/high) - prepared for when API supports it
    - Verbosity control (low/medium/high) - prepared for when API supports it
    - Auto-shows/hides based on selected model
- **Prompt Enhancement** - One-click prompt improvement using selected LLM
  - Automatic fallback when LLM returns empty response
  - Configurable temperature and max tokens for fine-tuning
  - Works across both Image and Video tabs with shared enhancement engine
- **Ask Questions About Prompts** - Interactive Q&A dialog for prompt analysis
  - Pre-defined questions for quick insights
  - Custom question support with detailed answers
  - User-adjustable temperature (0-2) and max tokens (100-4000)
  - GPT-5 reasoning and verbosity controls when using GPT-5 models
  - Session persistence - remembers last question, settings, and GPT-5 parameters
  - History tracking of all Q&A interactions
- **Automatic Model Syncing** - Provider and model selections sync between tabs
- **Smart Model Detection** - Automatically populates available models per provider

### 💻 Enhanced UI Features (NEW!)

- **Reference Image Panel** - UI controls for starting with reference images:
    - File selection dialog
    - Reference image thumbnail
    - Enable/disable checkbox
    - Clear button
    - Provider compatibility indicators
- **Status Bar** - Real-time status messages and provider connection feedback
- **Console Output Window** - Terminal-style log with color-coded messages:
  - Timestamp for each operation
  - Color coding: Green (success), Red (errors), Blue (progress), Yellow (responses)
  - Visual separators between operations
  - Resizable with splitter control
- **Improved Startup** - Progress messages during initialization
- **Lazy Video Tab Loading** - Faster startup by loading video features on-demand

### 🎬 Video Project Features
- **Complete Video Creation Pipeline** - Text to video with AI scene generation
- **Version Control System** - Event sourcing with time-travel capabilities
- **Dual Rendering Engines** - FFmpeg slideshow and Google Veo AI (coming soon)
- **Multi-Provider LLM Integration** - Enhance prompts with GPT-5, Gemini, Claude, and more
- **Visual Continuity System** - Maintain consistency across scenes with provider-specific techniques
- **Smart Lyric Processing** - Automatic detection and visual scene creation from song lyrics
- **Professional Effects** - Ken Burns, transitions, audio sync
- **Project History** - Complete audit trail with restore points

### 🎵 MIDI Synchronization & Karaoke (NEW!)
- **MIDI-Based Timing** - Perfect beat/measure alignment for scene transitions
- **Musical Structure Detection** - Identify verses, choruses, bridges from MIDI
- **Karaoke Overlays** - Bouncing ball, highlighting, fade-in styles
- **Lyric Export Formats** - Generate LRC, SRT, and ASS subtitle files
- **Word-Level Synchronization** - Extract timing from MIDI lyric events
- **Adjustable Snap Strength** - Control how tightly scenes align to beats
- **Audio Track Support** - Link MP3, WAV, M4A files without copying
- **Volume & Fade Controls** - Professional audio mixing options

### 🔧 Developer Features
- Modular architecture with provider abstraction
- Worker threads for non-blocking generation
- Comprehensive error handling and recovery
- Progress tracking and status updates
- Event-driven architecture with Qt signals
- Extensible provider system for new services

## 1. Requirements

- Python 3.9+ (3.9 to 3.13 supported)
- Internet connection
- Google account (for Gemini) or OpenAI account (for DALL·E)
- Dependencies (auto-installed via requirements.txt):
  - `google-genai` - Google Gemini API client
  - `google-cloud-aiplatform` - Google Cloud authentication support
  - `openai` - OpenAI API client
  - `PySide6` - GUI framework (optional for CLI-only usage)
  - `pillow` - Image processing
  - `protobuf` - Protocol buffer support
  - `pretty-midi` - MIDI file analysis and timing extraction
  - `mido` - Low-level MIDI manipulation for lyrics and events
  - `moviepy` - Video processing and assembly
  - `litellm` - Unified LLM provider interface (for video prompts)

## 2. Authentication Setup

### Google Gemini Authentication

You have two options for authenticating with Google's Gemini API:

#### Option A: API Key (Recommended for Individual Users)

1. **Get your API key**:
   - Visit [Google AI Studio](https://aistudio.google.com/apikey)
   - Create a new API key or use an existing one
   - Copy the key (keep it secure!)

2. **Review documentation**:
   - [Gemini API Overview](https://ai.google.dev/)
   - [Pricing and Quotas](https://ai.google.dev/pricing)
   - [Safety Policies](https://ai.google.dev/gemini-api/docs/safety)

3. **Enable billing if required**:
   - Some regions/models require billing
   - Visit [Google AI Pricing](https://ai.google.dev/pricing)

#### Option B: Google Cloud Account (Enterprise/Advanced Users)

1. **Install Google Cloud CLI**:
   - Download from [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
   - Windows: Use the interactive installer
   - macOS: `brew install google-cloud-sdk`
   - Linux: Follow distribution-specific instructions

2. **Set up Google Cloud project**:
   - Create/select project at [Cloud Console](https://console.cloud.google.com/projectcreate)
   - Note your Project ID

3. **Authenticate**:
   ```bash
   # Login to Google account
   gcloud auth application-default login
   
   # Set your project
   gcloud config set project YOUR_PROJECT_ID
   
   # Verify authentication
   gcloud auth list
   ```

4. **Enable required APIs**:
   ```bash
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable cloudresourcemanager.googleapis.com
   ```
   Or enable via [Cloud Console](https://console.cloud.google.com/apis/library)

5. **Enable billing**:
   - Visit [Cloud Billing](https://console.cloud.google.com/billing)
   - New accounts may have free credits

### OpenAI Authentication

1. **Get your API key**:
   - Sign in at [OpenAI Platform](https://platform.openai.com/)
   - Create API key at [API Keys page](https://platform.openai.com/api-keys)

2. **Review documentation**:
   - [Rate Limits](https://platform.openai.com/docs/guides/rate-limits)
   - [Pricing](https://openai.com/pricing)

## 3. Installation

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/ImageAI.git
cd ImageAI

# Create virtual environment (recommended)
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows Command Prompt:
.venv\Scripts\activate.bat
# macOS/Linux:
source .venv/bin/activate

# Install core dependencies
pip install -r requirements.txt

# Optional: Install Local Stable Diffusion support
# For CPU-only:
pip install -r requirements-local-sd.txt

# For GPU support (CUDA):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements-local-sd.txt
```

### Platform-Specific Notes

- **Windows**: Ensure Python is added to PATH during installation
- **macOS**: You may need to install Xcode Command Line Tools
- **Linux**: You may need to install the venv module first:
  ```bash
  # Ubuntu/Debian:
  sudo apt install python3.10-venv
  # Or for Python 3.11:
  sudo apt install python3.11-venv
  # Or use your specific Python version:
  sudo apt install python3-venv

  # Fedora/RHEL:
  sudo dnf install python3-pip python3-devel

  # Arch Linux:
  sudo pacman -S python-pip
  ```

## 4. Running the Application

### GUI Mode (Default)

```bash
# Launch the graphical interface
python main.py
```

### CLI Mode

```bash
# Show help
python main.py -h

# Quick examples
python main.py -p "A majestic mountain landscape at sunset" -o mountain.png
python main.py --provider openai -m dall-e-3 -p "Futuristic cityscape" -o city.png
```

### Authentication Examples

#### Using API Keys

```bash
# Google Gemini with API key
python main.py -s -k "YOUR_GOOGLE_API_KEY"  # Save key
python main.py -p "Beautiful ocean sunset" -o ocean.png  # Generate

# OpenAI with API key
python main.py --provider openai -s -k "YOUR_OPENAI_API_KEY"  # Save key
python main.py --provider openai -m dall-e-3 -p "Abstract art" -o art.png  # Generate

# Using environment variables
export GOOGLE_API_KEY="YOUR_KEY"  # Linux/macOS
$env:GOOGLE_API_KEY = "YOUR_KEY"  # Windows PowerShell
python main.py -p "Mountain landscape"  # Uses env variable
```

#### Using Google Cloud Authentication

```bash
# First-time setup
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# Generate images
python main.py --auth-mode gcloud -p "Tropical paradise" -o paradise.png

# Test authentication
python main.py --auth-mode gcloud -t
```

#### Loading Keys from Files

```bash
# Save key from file
python main.py -s -K /path/to/key.txt

# Use key file directly (one-time)
python main.py -K /path/to/key.txt -p "Desert oasis" -o oasis.png
```

## 5. Authentication Management

### Key Storage Locations

Configuration and keys are stored in platform-specific directories:

- **Windows**: `%APPDATA%\ImageAI\config.json`
- **macOS**: `~/Library/Application Support/ImageAI/config.json`
- **Linux**: `~/.config/ImageAI/config.json`

### Log File Locations

Application logs are stored in platform-specific directories for easy debugging:

- **Windows**: `%APPDATA%\ImageAI\logs\`
  - Full path: `C:\Users\<username>\AppData\Roaming\ImageAI\logs`
- **macOS**: `~/Library/Application Support/ImageAI/logs/`
  - Full path: `/Users/<username>/Library/Application Support/ImageAI/logs`
- **Linux**: `~/.config/ImageAI/logs/`
  - Full path: `/home/<username>/.config/ImageAI/logs`

**Log file format**: `imageai_YYYYMMDD_HHMMSS.log` (timestamp when app starts)

**Additional features**:
- **Automatic rotation**: Log files rotate at 10MB with 5 backups kept
- **Current log copy**: On application exit, the most recent log is automatically copied to `./imageai_current.log` in your current directory for easy access
- Use these log files when reporting issues or debugging problems

**Quick access to most recent log**:
```bash
# Windows (PowerShell)
ls "$env:APPDATA\ImageAI\logs" | sort LastWriteTime -Descending | select -First 1

# macOS
ls -lt ~/Library/Application\ Support/ImageAI/logs/imageai_*.log | head -1

# Linux
ls -lt ~/.config/ImageAI/logs/imageai_*.log | head -1
```

### Authentication Precedence

For each provider, the authentication order is:
1. Command-line key (`-k` or `-K` flags)
2. Stored configuration
3. Environment variables (`GOOGLE_API_KEY`, `OPENAI_API_KEY`)
4. Google Cloud ADC (for Google provider with `--auth-mode gcloud`)

### Security Best Practices

- Never commit API keys to version control
- Use environment variables for CI/CD
- Rotate keys regularly
- Use Google Cloud authentication for enterprise deployments
- Store keys in secure password managers

## 6. CLI Reference

### Core Arguments

```
-h, --help              Show help message
-p, --prompt TEXT       Prompt for image generation
-o, --out PATH          Output path for generated image
-m, --model TEXT        Model to use (provider-specific)
-t, --test              Test authentication
```

### Authentication Arguments

```
-k, --api-key TEXT      API key string
-K, --api-key-file PATH Path to file containing API key
-s, --set-key           Save the provided key
--auth-mode {api-key|gcloud}  Google auth mode (default: api-key)
```

### Provider Arguments

```
--provider {google|openai|stability|local_sd}  Provider to use (default: google)
```

### Model Defaults

- **Google**: `gemini-2.5-flash-image-preview`
- **OpenAI**: `dall-e-3`
- **Stability AI**: `stable-diffusion-xl-1024-v1-0`
- **Local SD**: `stabilityai/stable-diffusion-2-1`

### Complete Examples

```bash
# Test authentication
python main.py -t
python main.py --provider openai -t
python main.py --provider stability -t
python main.py --provider local_sd -t  # Check if ML deps installed
python main.py --auth-mode gcloud -t

# Generate with different providers
python main.py -p "Sunset over mountains" -o sunset.png
python main.py --provider openai -m dall-e-2 -p "Abstract art" -o abstract.png
python main.py --provider stability -p "Fantasy landscape" -o fantasy.png
python main.py --provider local_sd -p "Cyberpunk city" -o cyber.png
python main.py --auth-mode gcloud -p "Space station" -o space.png

# Save and use API keys
python main.py -s -k "YOUR_KEY"  # Save to config
python main.py --provider stability -s -k "YOUR_STABILITY_KEY"
python main.py -K ~/keys/api.txt -p "Ocean waves"  # Use from file
```

### Video Generation with MIDI Sync (NEW!)

```bash
# Basic video generation with slideshow
python main.py video --in lyrics.txt --provider gemini --slideshow \
  --audio /path/to/music.mp3 --out video.mp4

# MIDI-synchronized video with beat alignment
python main.py video --in lyrics.txt --midi /path/to/song.mid \
  --audio /path/to/song.mp3 --sync-mode measure --snap-strength 0.9 \
  --out synced_video.mp4

# Video with karaoke overlay
python main.py video --in lyrics.txt --midi song.mid --audio song.mp3 \
  --karaoke --karaoke-style bouncing_ball \
  --export-lrc --export-srt --export-ass \
  --out karaoke_video.mp4

# Using Veo AI for video generation (when available)
python main.py video --in script.txt --veo-model veo-3.0-generate-001 \
  --audio soundtrack.mp3 --out ai_video.mp4
```

## 7. GUI Features

### Main Interface

#### Image Tab (Primary)
- **Model Selection**: Dropdown with provider-specific models
- **Prompt Input**: Multi-line text area with built-in search (Ctrl+F)
- **AI Prompt Tools**:
  - **Enhance Prompt**: Improve your prompt with AI assistance
  - **Generate Prompts**: Create multiple prompt variations with history tracking
  - **Ask AI Anything**: Interactive AI assistant for prompt help or general questions
    - Works with or without a prompt
    - Continuous conversation mode with context retention
    - Editable prompt field with clear edit controls
    - Conversation history saved across sessions
  - **Reference Image Analysis**: Analyze images to generate detailed descriptions
    - Upload any image for AI analysis
    - Customizable analysis prompts
    - Copy descriptions directly to main prompt
- **Generate Button**: Start image generation with progress tracking
- **Image Display**: High-quality preview with automatic scaling
- **Generation Controls**:
  - Aspect ratio selector with visual previews
  - Resolution selector with provider-optimized presets
  - Quality settings (Standard/HD)
  - Batch size selector (1-4 images)
  - Cost estimator showing real-time pricing
- **Multiple Reference Images** - Two modes for different use cases:
  - **Flexible Mode** (Google Gemini - Style Transfer):
    - Click "+ Add Reference Image" to select one or multiple files at once
    - Unlimited reference images (adds as many as you select)
    - When 2+ images: Automatically composites into character design sheet
    - Use case: "These people as high resolution cartoon characters"
    - Use case: Style transformation, artistic interpretations
    - Type/subject selectors hidden (mode focuses on style transfer)
    - Visual help tooltip appears when using multiple images
  - **Strict Mode** (Imagen 3 Customization - Subject Preservation):
    - Maximum 3 reference images with precise control
    - Each reference has:
      - **Type selector**: SUBJECT, STYLE, or CONTROL
      - **Subject Type** (for SUBJECT): Person, Animal, Product, Default
      - **Control Type** (for CONTROL): Canny, Scribble, Face Mesh
      - **Description field**: Optional text description per reference
      - **Reference ID**: [1], [2], [3] for use in prompts
    - Use case: Keep character appearance while changing scene
    - Use case: Maintain product consistency in different contexts
  - **Mode Switching**:
    - Toggle between Flexible and Strict with radio buttons
    - If switching Strict→Flexible with >3 refs: Shows selection dialog
    - References automatically revalidated on mode change
  - **UI Features**:
    - Multi-select file dialog (Ctrl+Click or Shift+Click)
    - Flow layout wraps thumbnails automatically
    - Individual remove buttons (✕) per reference
    - Visual thumbnails (120×120) with file names
    - Reference count display: "Reference Images (2/3)" or "(5)"
- **Advanced Settings** (collapsible panel):
  - Inference steps slider (1-50)
  - Guidance scale (CFG) control
  - Scheduler selection
  - Seed input for reproducibility
  - Negative prompt field
  - Prompt rewriting toggle
- **Output Text**: Live generation status and file paths
- **Examples Button**: Access curated prompts library

#### Templates Tab
- **Predefined Templates**: Ready-to-use prompts with customizable placeholders
- **Quick Generation**: Jump-start your creativity with proven prompt patterns
- **Placeholder System**: Customize templates with your own variables

#### Video Tab
The Video Project feature provides comprehensive tools for creating AI-powered videos from text, with advanced version control and multiple rendering options.

**Project Management**:
- **Workspace and History Tabs**: Dual-tab interface for active editing and version control
- **Project Operations**: Create, open, save, and manage multiple video projects
- **Auto-save**: Automatic project saving after generation operations
- **Project Directory**: Organized storage in `~/.imageai/video_projects/`

**Text Processing**:
- **Multiple Input Formats**:
  - Timestamped lyrics: `[00:30] First verse lyrics`
  - Structured sections: `# Verse 1`, `# Chorus`, `# Bridge`
  - Plain text with intelligent scene detection
  - Custom scene markers for precise control
- **Smart Scene Detection**: Automatic breaking of text into scenes based on:
  - Timestamps in lyrics
  - Section headers
  - Paragraph breaks
  - Semantic analysis

**Storyboard & Scene Management**:
- **Interactive Scene Table**: Edit titles, durations, and prompts directly
- **Timing Controls**: Adjustable duration for each scene (0.5-30 seconds)
- **Scene Reordering**: Drag-and-drop to rearrange scenes
- **Batch Operations**: Apply settings to multiple scenes at once
- **Preview**: Real-time preview of scene timings and transitions

**AI-Powered Enhancement**:
- **Multi-Provider LLM Support**:
  - OpenAI GPT-5 and GPT-4o
  - Anthropic Claude 3.5 Sonnet, Opus, Haiku
  - Google Gemini 2.0 Flash and Pro models
  - Local Ollama models
- **Prompt Styles**:
  - Cinematic: Movie-like dramatic scenes
  - Artistic: Painterly and stylized visuals
  - Photorealistic: High-fidelity realistic images
  - Animated: Cartoon and animation styles
  - Documentary: Authentic, journalistic look
  - Abstract: Experimental and artistic
- **Batch Enhancement**: Process all scenes with consistent style

**Image Generation**:
- **Multi-Provider Support**: Generate with Google Gemini, OpenAI DALL-E, Stability AI
- **Variant Generation**: Create 1-4 variations per scene
- **Concurrent Processing**: Generate multiple scenes in parallel
- **Smart Caching**: Hash-based caching to avoid regenerating identical prompts
- **Thumbnail System**: Automatic thumbnail generation with composite previews
- **Cost Tracking**: Real-time cost estimation and tracking per scene

**Video Rendering Options**:

1. **FFmpeg Slideshow Rendering**:
   - **Ken Burns Effects**: Automatic pan and zoom animations
   - **Transitions**: Smooth crossfade between scenes
   - **Multiple Aspect Ratios**: 16:9, 4:3, 9:16 (vertical), 1:1 (square)
   - **Resolution Options**: Up to 4K output
   - **Frame Rate Control**: 24, 30, or 60 fps
   - **Audio Integration**: Sync with audio tracks

2. **Google Veo 3.1 AI Video** (NEW! - Version 0.23.1):
   - **Continuous Video Generation**: Automatically grab end frame and use as start frame for next scene
   - **Seamless Scene Transitions**: Maintain visual continuity across multi-scene videos
   - **Optional End Frame Control**: Set custom end frames for precise scene endings
   - **Start/End Frame Support**: Google released start/end frame control on October 15, 2025
   - **True AI Video**: Generate motion video from text prompts
   - **Model Selection**: Veo 3.0 and Veo 3.1 models with frame-to-frame continuity
   - **Duration Control**: 4, 6, or 8 second clips per scene (auto-snapped to provider limits)
   - **Advanced Features**: Camera movements, visual styles, physics-accurate motion
   - **Duration Enforcement**: Automatic snapping to 8-second duration for Veo 3.0/3.1 compliance

**Version Control and History**:
- **Event Sourcing Architecture**: Complete history of all changes
- **Time Travel**: Restore project to any point in history
- **History Timeline**: Visual timeline with event markers
- **Event Types Tracked**:
  - Project creation and saves
  - Scene additions and edits
  - Prompt enhancements
  - Image generations
  - Video renders
- **Filtering and Search**: Find specific events quickly
- **Restore Points**: One-click restoration to previous states
- **Diff Viewer**: See exact changes between versions

**Audio & MIDI Support**:
- **Audio Track Integration**: Link MP3/WAV/M4A/OGG files without copying
- **MIDI Synchronization**: Load MIDI files for precise timing control
  - Beat grid alignment for scene transitions
  - Measure and section synchronization
  - Tempo and time signature display
  - Musical structure detection (verse, chorus, bridge)
- **Karaoke Features**:
  - Bouncing ball, highlighting, and fade-in styles
  - Export to LRC, SRT, and ASS formats
  - Word-level timing from MIDI lyrics
  - Customizable font size and position
- **Audio Controls**:
  - Volume adjustment with real-time preview
  - Fade in/out transitions
  - Trim controls for start/end offsets
- **Sync Options**: 
  - None, Beat, Measure, or Section alignment
  - Adjustable snap strength (0-100%)
  - Extract lyrics from MIDI files

**Advanced Settings**:
- **Generation Settings**:
  - Image provider and model selection
  - Quality settings per provider
  - Batch size and concurrency limits
- **Render Settings**:
  - Output format (MP4, AVI, MOV)
  - Codec selection
  - Bitrate control
  - Metadata embedding
- **Performance Options**:
  - GPU acceleration toggle
  - Memory usage limits
  - Cache management

**Video Project Workflow Examples**:

These examples are based on actual production workflows used to create music videos with ImageAI.

1. **MIDI-Synced Music Video with Scene Markers** (Real Example: "Do Math v2"):

   **Day 1 - Project Setup (October 14):**
   - Open Video tab → Click "New Project"
   - Name project: "Do Math v2"
   - Paste lyrics formatted with square brackets. (Like Suno and AISongGenerator use.)
   - Optionally, edit to include manual scene markers:
```
=== NEW SCENE: bedroom ===
[Verse 1]
When the night feels endless and I'm wide awake

=== NEW SCENE: abstract ===
I shuffle numbers like cards
I hum a rhythm, let the numbers dance
And suddenly it's not so hard

[Chorus]
=== NEW SCENE: bedroom ===
I'm doin' math, I do math, I do math
I'm tap-tap-tappin' in my head
(etc.)
```
   - In Audio/MIDI section, click "Browse..." next to MIDI file → Select `Do Math v2.mid`
     - System auto-detects tempo (e.g., 120 BPM, 4/4 time, 125 seconds)
   - Click "Browse..." next to Audio file → Select audio WAV file
     - This is used in final step to produce your video
   - Set MIDI Sync mode: "Beat" with snap strength 1.0
   - Configure providers:
     - LLM: Google Gemini 2.5 Pro
     - Images: Google Gemini 2.5 Flash Image Preview
   - Set prompt style: "Hi-res Cartoon"
   - Set aspect ratio: 16:9 (1024×576)
   - Scenes auto-detected (22 scenes) when you proceed to storyboard generation

   **Day 2 - Character Reference Setup (October 16):**
   - Generate character reference images in main Image tab
   - Switch to Video tab → Click "Reference Library" button (bottom of workspace)
   - In Reference Library panel, click "Generate Character Refs"
     - Or click "Add Reference" to load existing images
   - Add character images (Janelle, Dave) and environment reference (bedroom scene)
   - References auto-apply to all scenes

   **Day 13 - Video Generation (October 27):**
   - In Workspace tab, select scene 0 in the scene table
   - Click the 🎬 icon in the scene row to generate video
   - Veo generates 8-second clip in ~86 seconds
   - System extracts last frame automatically for continuity
   - Video saved to: `project/clips/scene_0_20251027_152943.mp4`

   **Result:** 22 scenes with perfect beat synchronization, character consistency, and smooth transitions

2. **Structured Lyrics Without MIDI** (Simpler Workflow):
   - Create new project
   - Paste lyrics with section headers into the input text area:
     ```
     [Verse 1]
     Your lyrics here...

     [Chorus]
     Your lyrics here...

     [Bridge]
     Your lyrics here...
     ```
   - Scenes are automatically detected from section headers when you generate the storyboard
   - Select LLM provider (OpenAI GPT-5, Claude 3.5, or Gemini 2.5 Pro)
   - Choose prompt style (Cinematic, Artistic, Photorealistic, etc.)
   - Click "Enhance All Prompts" → LLM generates detailed scene descriptions
   - Choose rendering method:
     - FFmpeg Slideshow: Generate images first, then render with Ken Burns effects
     - Google Veo: Generate motion video clips for each scene
   - Click "Render Video" to create final output

3. **Professional AI Motion Video with Continuity** (Google Veo 3.0/3.1):
   - Create project with storyboard/lyrics (text auto-parsed into scenes)
   - Configure video provider: Select "Gemini Veo" in provider dropdown
   - Enable continuity: Check "Auto-link previous end frame as reference" option
   - Set up first scene:
     - Write detailed prompt or click ✨ button for LLM enhancement
     - Optional: Add reference images in the Reference Images column
   - Click 🎬 icon to generate first video clip
   - System automatically:
     - Extracts last frame from generated clip
     - Uses it as start frame for next scene (or reference image)
     - Maintains visual continuity across scenes
   - Generate remaining scenes sequentially
   - Each 8-second clip links seamlessly to the next
   - Final assembly: Use "Render Video" to combine clips with crossfade transitions

4. **Quick Slideshow from Plain Text**:
   - Create new project
   - Paste plain text (no timestamps or markers) into input area
   - Scenes are automatically created from paragraph breaks during storyboard generation
   - Select "Quick" preset (short scenes, fast generation) if available
   - Choose image provider (Google, OpenAI, Stability AI)
   - Click "Enhance All Prompts" to generate scene descriptions
   - Generate all scene images (system processes multiple scenes in parallel)
   - Click "Render Video" and configure:
     - Resolution: 1080p or 4K
     - Ken Burns: Enabled for motion
     - Transitions: Crossfade between scenes
     - Audio: Optional background music
   - Export as MP4 in minutes

**Video Tab Troubleshooting**:

| Issue | Solution |
|-------|----------|
| "Scene detection failed" | Ensure text has clear line breaks or timestamps |
| "MIDI sync not working" | Verify MIDI file format (SMF 0 or 1) and load audio first |
| "Veo model not available" | Ensure Google API key is set and Gemini 2.0 API is enabled |
| "Duration mismatch" | System auto-snaps to 4, 6, or 8 seconds; manual adjustment limited |
| "Video rendering slow" | Reduce resolution or disable Ken Burns effects |
| "Memory errors during generation" | Reduce batch size or number of concurrent scene generations |
| "Audio sync issues" | Adjust "snap strength" slider (0-100%) for timing flexibility |
| "Karaoke export blank" | Ensure MIDI file contains lyric events and is properly formatted |
| "Generated images don't match style" | Use consistent LLM provider and set strong style descriptors in prompts |

#### Layout/Books Tab (NEW!)

⚠️ <b>Layout tab Development is in Progress — It's not yet fully functional.</b>

The Layout/Books tab provides a professional layout engine for creating photo books, comics, children's books, and magazine-style publications with AI-generated images.

**Core Features**:
- **Template-Driven Design**: Pre-built templates for common layouts
  - Children's book: Single illustration per page with text
  - Comic book: Multi-panel grid layouts (3-panel, 4-panel, etc.)
  - Magazine: Two-column layouts with pull quotes
  - Photo book: Grid layouts with captions
- **Intelligent Placement**: Automatic positioning of text and images
- **Professional Typography**:
  - Advanced text rendering with word wrapping
  - Hyphenation support (framework ready)
  - Widow/orphan control
  - Text justification with word spacing
  - Multiple fonts and styles per page
- **Image Processing**:
  - Rounded corners with anti-aliasing
  - Image filters (blur, grayscale, sepia, sharpen)
  - Borders and strokes
  - Multiple fit modes (cover, contain, fill)
  - Brightness, contrast, saturation adjustments
- **Smart Layout Algorithms**:
  - Auto-fit text to available space
  - Text overflow handling across pages
  - Panel grid computation for comics
  - Column flow for magazine layouts
  - Safe area margins and bleed handling

**Template System**:
- **Variable Substitution**: Use `{{variable}}` syntax in templates
- **Color Palettes**: Define theme colors with automatic variants
- **Per-Page Overrides**: Customize variables on specific pages
- **Theme Files**: Load color schemes from JSON

**Workflow**:
1. **Select Template**: Choose from built-in templates or create custom
2. **Set Theme**: Configure colors, fonts, and spacing
3. **Add Content**:
   - Import AI-generated images from Generate tab
   - Write or paste text content
   - Use LLM to generate story text
4. **Customize Layout**: Adjust positions, sizes, and styles
5. **Export**: Generate high-resolution PDF or PNG (300 DPI default)

**Use Cases**:
- **Children's Books**: Illustrated stories with consistent page layouts
- **Comic Books**: Sequential art with panel-based storytelling
- **Photo Books**: Family albums with captions and decorative layouts
- **Magazine Articles**: Multi-column text with pull quotes and images
- **Marketing Materials**: Brochures, flyers, and promotional content

**Advanced Features**:
- **Font Management**:
  - System font discovery (Windows, macOS, Linux)
  - Custom font directory support
  - Font fallback chains
- **Export Options**:
  - Configurable DPI (default 300 for print quality)
  - PDF with embedded fonts
  - PNG sequence for individual pages
- **LLM Integration**: Generate story text with AI assistance
- **Multi-Page Projects**: Create complete publications with consistent styling

**Example Projects**:
```
Children's Book: "The Adventure"
- Generate 10 scene images in Image tab with prompt: "Illustrated children's book scene showing [description]"
- Switch to Layout tab
- Select "Children's Book" template
- Import generated images
- Add text for each page
- Customize colors to match story mood
- Export as PDF for printing

Comic Strip: "Monday Morning"
- Generate 3 comic panels in Image tab
- Switch to Layout tab
- Select "Comic 3-Panel" template
- Import panels in sequence
- Add speech bubbles and captions
- Export as high-res PNG
```

**Tips for Best Results**:
- Generate images with consistent style and color palette
- Use Layout tab's theme colors to match your generated images
- Export at 300 DPI for print-quality results
- Test with low-DPI preview before final high-res export

#### Settings Tab
- **Provider Selection**: Switch between Google, OpenAI, Stability AI, and Local SD
- **Authentication Mode** (Google only):
  - API Key mode with key input field
  - Google Cloud Account mode with status display
- **Helper Buttons**:
  - Get API Key - Opens provider's key page
  - Load from File - Import key from text file
  - Check Status - Verify authentication
  - Cloud Console - Open Google Cloud Console (Google only)
- **Auto-save Options**: 
  - Auto-save generated images toggle
  - Copy filename to clipboard option
  - Custom output directory selection
- **Local SD Settings** (when selected):
  - Model browser and downloader
  - Hugging Face authentication
  - Cache directory management
  - GPU/CPU device selection

#### Templates Tab
- Predefined prompt templates with placeholders
- Variable substitution system with live preview
- Template categories:
  - Art Style
  - Photography
  - Design
  - Character
  - Scene
  - Product
  - Marketing
- Append or replace current prompt
- Custom template creation and saving

#### History Tab
- **Detailed History Table** with columns:
  - Date and time
  - Provider used
  - Model name
  - Resolution
  - Cost (when applicable)
  - Original prompt
- **Quick Actions**:
  - Click to reload prompt and settings
  - Open image file location
  - View metadata sidecar
- **Search and Filter**:
  - Filter by provider
  - Search by prompt text
  - Sort by date, cost, or model

#### Help Tab
- Embedded README documentation with full content
- **Interactive Search**:
  - Search box with real-time results
  - Navigate between matches with Previous/Next buttons
  - Match counter showing current/total results
  - Keyboard shortcuts (F3 for next, Shift+F3 for previous)
- Navigation controls:
  - Back/Forward buttons for history
  - Home button to return to top
  - Keyboard navigation (Alt+Left/Right, Backspace)
- Quick reference guide
- Keyboard shortcuts reference
- Provider-specific tips
- Troubleshooting guide

### Menu System

#### File Menu
- New Generation (Ctrl+N)
- Save Image As... (Ctrl+S)
- Open Output Directory
- Recent Files
- Exit (Ctrl+Q)

#### Edit Menu
- Copy Prompt (Ctrl+C)
- Paste Prompt (Ctrl+V)
- Clear All (Ctrl+Shift+C)
- Copy Image to Clipboard
- Copy Filename

#### View Menu
- Show/Hide History Panel
- Show/Hide Advanced Settings
- Full Screen Mode (F11)
- Reset Layout
- Zoom In/Out

#### Tools Menu

##### Search Wikimedia Commons

Access millions of freely licensed images from Wikimedia Commons for use as reference images or inspiration.

**Features:**
- **Advanced Search**: Search by keywords with real-time results
- **Category Browsing**: Browse by media type (images, photos, drawings, etc.)
- **License Filtering**: Filter by license type (Public Domain, CC BY, CC BY-SA, etc.)
- **Batch Download**: Select and download multiple images at once
- **Auto-Integration**: Downloaded images automatically added to reference images panel (Google provider)
- **Organized Storage**: Images saved to `<output_dir>/wikimedia/` with metadata
- **Image Preview**: Full-size preview with licensing information
- **Attribution Info**: Complete licensing and author information for each image

**Usage:**
1. Open **Tools → Search Wikimedia Commons**
2. Enter search terms (e.g., "mountain landscape", "vintage cars")
3. Browse results with thumbnail previews
4. Click image for full preview and licensing details
5. Select images to download (single or multiple)
6. Downloaded images appear in reference images panel
7. Use in your prompts for style transfer or reference

**Example Workflows:**
- **Character Reference**: Search "portrait photography" → Download reference → Use in Flexible mode for style transformation
- **Style Reference**: Search "oil painting landscape" → Download → Use as style reference in Strict mode
- **Historical Reference**: Search "1920s architecture" → Download → Use for period-accurate generation

##### Prompt Builder

Build comprehensive, modular prompts with a professional template system. Perfect for character transformations, style transfers, and consistent prompt generation.

**Features:**
- **Dual Tab Interface**:
  - **Builder Tab**: Create and preview prompts in real-time
  - **History Tab**: Access previously saved prompts with full details
- **Modular Prompt Components**: Optional fields for complete control
  - Subject type (Headshot, Full body, Portrait, Character sheet, etc.)
  - Transformation style (Caricature, Cartoon, Anime, Oil painting, etc.)
  - Art style (from `styles.json` - Abstract, Cyberpunk, Baroque, etc.)
  - Medium/Technique (from `mediums.json` - Oil painting, Digital art, etc.)
  - Background options (Clean white, Solid black, Transparent, Studio, etc.)
  - Pose/Orientation (Facing forward, Three-quarter view, Dynamic pose, etc.)
  - Purpose/Context (Character design, Avatar, Game character, etc.)
  - Technique details (Line work, Bold outlines, Photorealistic, etc.)
  - Artist style (from `artists.json` - specific artist influences)
  - Lighting (from `lighting.json` - Golden hour, Studio lighting, etc.)
  - Mood (from `moods.json` - Dramatic, Peaceful, Energetic, etc.)
  - Exclusions (Automatic "no" prefix for negative prompts)
  - Additional notes (Free-form custom details)
- **Smart Exclusion Processing**: Automatically adds "no" to exclusion items
- **Live Preview**: Real-time preview of assembled prompt
- **Keyboard Shortcuts**:
  - **Ctrl+Enter**: Use current prompt (Builder tab)
  - **Escape**: Close dialog
- **History Management**:
  - Auto-save to history when using prompts
  - Manual save option for building without using
  - Full prompt display in history list (no truncation)
  - Timestamp for each entry (YYYY-MM-DD HH:MM)
  - Double-click to load prompt into builder
  - Delete individual entries
  - Clear all history option
- **Import/Export**:
  - **Export**: Single button with smart dialog
    - Export current prompt (JSON format with all settings)
    - Export all history (N entries with metadata)
    - Automatically detects what's available
  - **Import**: Load prompts from JSON files
    - Single prompt files
    - Full history exports (import all or load most recent)
- **Editable Combo Boxes**: All dropdowns allow custom entries
- **Data-Driven**: Uses JSON files for customizable options
- **Session Persistence**: Remembers window position and last tab

**Data Files** (customizable):
- `data/prompts/artists.json` - Artist names and styles
- `data/prompts/styles.json` - Art styles
- `data/prompts/mediums.json` - Art mediums and techniques
- `data/prompts/lighting.json` - Lighting options
- `data/prompts/moods.json` - Mood descriptors

**Usage:**
1. Open **Tools → Prompt Builder** (or use keyboard shortcut if configured)
2. Fill in desired fields (all optional):
   - Select subject type or enter custom
   - Choose transformation style
   - Pick art style, medium, etc.
   - Add exclusions (text, watermark, etc.) - "no" automatically added
   - Enter additional custom details
3. Watch live preview update as you build
4. Press **Ctrl+Enter** or click **Use Prompt** to apply
5. Prompt is automatically saved to history
6. Switch to **History Tab** to browse previous prompts

**Example Prompts:**

*Cartoon Character Transformation*:
```
Subject: Headshot of attached
Transform As: as full color super-exaggerated caricature cartoon
Background: on a clean white background
Pose: facing forward
Purpose: suitable as character design sheet
Technique: use line work and cross-hatching
Exclude: text

Result: "Headshot of attached as full color super-exaggerated caricature cartoon,
on a clean white background, facing forward, suitable as character design sheet,
use line work and cross-hatching, no text"
```

*Artistic Portrait*:
```
Subject: Portrait of attached
Art Style: Impressionist
Medium: Oil Painting
Artist Style: Claude Monet
Lighting: Golden Hour
Mood: Peaceful
Exclude: modern elements, photographs

Result: "Portrait of attached in Impressionist style, using Oil Painting, in the
style of Claude Monet, with Golden Hour, Peaceful mood, no modern elements, no
photographs"
```

*Anime Character Design*:
```
Subject: Full body of attached
Transform As: as anime character
Background: with gradient background
Pose: dynamic pose
Purpose: for character concept art
Technique: with cel shading
Mood: Energetic

Result: "Full body of attached as anime character, with gradient background,
dynamic pose, for character concept art, with cel shading, Energetic mood"
```

**Tips:**
- Leave fields blank to omit from prompt
- Use exclusions to prevent unwanted elements
- Save multiple variations in history for A/B testing
- Export your best prompts for sharing or backup
- Import community prompt collections

#### Semantic Search & Tag System

The Prompt Builder includes an intelligent search system powered by semantic metadata to help you discover artists, styles, moods, and other prompt elements naturally.

**Smart Search Panel** (at top of Builder tab):
- **Auto-filter**: Enabled by default - filters dropdown options as you type (300ms debounce)
- **Manual Search**: Disable auto-filter to search on-demand (press Enter or click Search button)
- **Clear Filters**: Restore all items after filtering
- **Multi-category Search**: Searches across Artists, Styles, Mediums, Lighting, and Moods simultaneously

**Search Features**:
- **Semantic Matching**: Search by concepts, not just exact names
  - "60s satire" finds Al Jaffee and MAD Magazine-related artists
  - "cyberpunk" discovers related styles, moods, and lighting options
  - "vintage comics" surfaces comic artists and relevant art styles
- **Cultural Keywords**: Recognizes common search terms and pop culture references
- **Tag-Based Discovery**: Items tagged with related concepts appear in results
- **Fuzzy Matching**: Typo-tolerant search helps even with misspellings
- **Popularity Scoring**: More popular/well-known items appear higher in results

**How It Works**:
1. Type a search term (e.g., "Mad Magazine", "cyberpunk", "1960s")
2. With auto-filter enabled, results appear automatically after 300ms pause
3. Dropdown menus filter to show only matching items
4. Result counter shows matches per category: "Artists (3), Styles (5), Moods (2)"
5. Select from filtered results or click "Clear" to restore all items

**Example Searches**:
- "MAD Magazine" → Finds Al Jaffee, Jack Davis, Mort Drucker, Comic Art style
- "1960s" → Discovers period artists, vintage styles, retro moods
- "cyberpunk" → Returns Cyberpunk style, neon lighting, futuristic moods
- "watercolor" → Finds Watercolor Painting medium, related artists, soft moods
- "dramatic" → Surfaces Dramatic mood, related lighting options, intense styles

**Metadata System**:
The search is powered by a comprehensive metadata file (`data/prompts/metadata.json`) containing semantic tags, cultural keywords, descriptions, relationships, and popularity scores for every item in the prompt builder.

**Generating and Customizing Tags**:
See the "Customizing Search Metadata" section below for information on how to regenerate metadata with your own preferences, add custom tags, or contribute improved metadata to the community.

- Model Browser (Local SD)
- Batch Generator
- Template Editor
- Settings Manager

#### Help Menu
- Documentation (F1)
- Keyboard Shortcuts
- Check for Updates
- About ImageAI

## 8. Image Management

### Auto-Save System

Generated images are automatically saved to:
- **Windows**: `%APPDATA%\ImageAI\generated\`
- **macOS**: `~/Library/Application Support/ImageAI/generated/`
- **Linux**: `~/.config/ImageAI/generated/`

### File Naming

- Filenames derived from prompt (sanitized)
- Timestamp added for uniqueness
- Format: `prompt_words_YYYYMMDD_HHMMSS.png`

### Metadata Sidecars

Each image gets a `.json` sidecar file containing:
```json
{
  "prompt": "User's prompt text",
  "model": "Model used",
  "provider": "Provider name",
  "created_at": "ISO timestamp",
  "app_version": "Version number",
  "output_text": "Any text output",
  "template": "Template data if used"
}
```

### History Tracking

- In-session history of generated images
- Persistent history across sessions
- Quick access to recent generations
- Metadata search and filtering

## 9. Examples and Templates

### Example Prompts

#### Artistic Styles
```
"Oil painting of a serene mountain lake at golden hour, impressionist style"
"Cyberpunk street scene with neon lights and rain reflections, ultra-detailed"
"Watercolor portrait of a wise owl in autumn forest, soft pastels"
```

#### Photorealistic
```
"Professional photograph of a modern minimalist living room, magazine quality"
"Macro shot of dewdrops on a spider web at sunrise, shallow depth of field"
"Aerial view of tropical islands with crystal clear water, drone photography"
```

#### Creative Concepts
```
"Steampunk airship floating above Victorian London, brass and copper details"
"Bioluminescent underwater cave with glowing creatures, fantasy art"
"Isometric cutaway of a cozy treehouse library with magical elements"
```

### Template System

The template system allows you to create consistent, reusable prompts with variable placeholders.

#### Using Templates

1. **Select a Template**: Choose from the dropdown in the Templates tab
2. **Fill Placeholders**: Enter values for each variable field (optional)
3. **Preview**: See the assembled prompt update in real-time
4. **Insert**: Click "Insert into Prompt" to use the template
5. **Append Option**: Check "Append to existing" to add to current prompt

#### Built-in Templates

**Portrait Photography**:
```
"[style] portrait of [subject] with [expression], [lighting] lighting, [background] background"
```

**Landscape Scene**:
```
"[time_of_day] landscape of [location] with [features], [weather] weather, [style] style"
```

**Product Shot**:
```
"Product photography of [item] on [surface], [lighting] lighting, [angle] angle, commercial quality"
```

**Fantasy Art**:
```
"[character] [action] in [setting], [magic_effect], [art_style] fantasy art style"
```

**Architectural**:
```
"[building_type] in [architectural_style] style, [time_of_day], [weather], [perspective] view"
```

#### Template Variables

- Variables are defined with square brackets: `[variable_name]`
- Leaving a field empty removes it from the final prompt
- Multiple instances of the same variable use the same value
- Commas are automatically managed when variables are empty

### Using Multiple Reference Images

**Flexible Mode Examples**:

```
Scenario 1: Family Cartoon Conversion
1. Select Flexible Mode
2. Click "+ Add Reference Image" → Select 4 family photos
3. Images automatically composite into character design sheet
4. Enter prompt: "These people as Pixar-style animated characters"
5. Generate → Creates cartoon versions with all family members

Scenario 2: Style Transfer
1. Select Flexible Mode
2. Add single reference image (person's photo)
3. Enter prompt: "This person as a watercolor painting"
4. Generate → Applies artistic style to the photo
```

**Strict Mode Examples**:

```
Scenario 1: Product Consistency (E-commerce)
1. Select Strict Mode
2. Add reference image → Type: SUBJECT, Subject Type: PRODUCT
3. Description: "Red ceramic coffee mug with handle"
4. Enter prompt: "Show [1] on a wooden kitchen table with morning light"
5. Generate → Shows same mug in new scene

Scenario 2: Character in Multiple Scenes
1. Select Strict Mode
2. Add 3 character references:
   - Front view → Type: SUBJECT, Subject Type: PERSON, Desc: "Sarah, main character"
   - Side view → Type: SUBJECT, Subject Type: PERSON
   - Full body → Type: SUBJECT, Subject Type: PERSON
3. Enter prompt: "Show [1] walking through a forest at sunset"
4. Generate → Character maintains appearance across generations

Scenario 3: Control with Edge Detection
1. Select Strict Mode
2. Add reference → Type: CONTROL, Control Type: CANNY
3. Enter prompt: "Follow the structural lines of [1], create modern architecture"
4. Generate → Uses edge structure while changing content
```

**Edit Mode** (Single Reference Only):

When you have exactly one reference image, you can enable **Edit Mode** to make precise edits while preserving everything else in the image:

```
Example: Changing one element while keeping everything else
1. Add a single reference image (e.g., photo of a room)
2. Check the "Edit Mode" checkbox (appears next to "+ Add Reference Image")
3. Enter your edit instruction: "Replace the sofa with a modern blue sectional"
4. Generate → The prompt is auto-prefixed with:
   "Edit this image. Keep everything already in the image exactly the same."
5. Result: Only the specified element changes, everything else stays identical

Tips for Edit Mode:
- Be specific about what to change: "Replace X with Y", "Change the color of X to Y"
- Works best with clear, focused edit requests
- The checkbox is only enabled when exactly 1 reference image is present
- Automatically disabled when adding more images or removing the last image
```

**Tips for Best Results**:
- **Flexible Mode**: Works best with consistent lighting across input images
- **Strict Mode**: Use all 3 reference slots for best subject preservation
- **Reference IDs**: Use [1], [2], [3] in prompts to explicitly reference images
- **Compositing**: When using 2+ images in Flexible, use prompts like "these people" or "all subjects"
- **Mode Selection**: Use Flexible for creative transformations, Strict for consistency

### Tips for Better Results

**Be Specific**: Instead of "a cat", try "a fluffy orange tabby cat sitting on a windowsill"

**Include Style**: Add artistic style like "oil painting", "photorealistic", "cartoon style"

**Describe Mood**: Include lighting and atmosphere like "golden hour", "dramatic lighting", "cozy"

**Add Details**: More details generally produce better results

**Composition Tips**:
- Use camera angles: "aerial view", "close-up", "wide angle"
- Specify perspective: "first-person view", "isometric", "side profile"
- Include depth: "shallow depth of field", "bokeh background", "infinite focus"

**Quality Modifiers**:
- "highly detailed", "ultra-realistic", "4K", "HD"
- "professional photography", "award-winning"
- "trending on artstation", "masterpiece"

## 10. Advanced Features

### Keyboard Shortcuts

**GUI Mode**:
- **Ctrl+Enter**: Generate image
- **Ctrl+F**: Find/search in prompt text
- **F3**: Find next match
- **Shift+F3**: Find previous match
- **Escape**: Close find dialog
- **Ctrl+S**: Save current image as...
- **Ctrl+Q**: Quit application
- **Ctrl+N**: Clear prompt
- **Ctrl+A**: Select all text
- **Ctrl+C/V/X**: Copy/Paste/Cut
- **Tab**: Switch between tabs
- **F1**: Show help
- **F3**: Find next in help documentation
- **Shift+F3**: Find previous in help documentation
- **Ctrl+F**: Focus search box in help tab
- **Alt+Left/Backspace**: Navigate back in help
- **Alt+Right**: Navigate forward in help
- **Ctrl+Home**: Go to top of help

### Batch Generation

Generate multiple images with variations:

```bash
# Generate 3 variations of the same prompt
for i in {1..3}; do python main.py -p "Sunset landscape" -o "sunset_$i.png"; done

# Generate from a list of prompts
while read prompt; do
  python main.py -p "$prompt" -o "${prompt// /_}.png"
done < prompts.txt
```

### Using Environment Variables

```bash
# Set default provider
export IMAGEAI_PROVIDER="openai"
export OPENAI_API_KEY="your-key"

# Set default model
export IMAGEAI_MODEL="dall-e-3"

# Set output directory
export IMAGEAI_OUTPUT_DIR="/path/to/images"
```

### Custom Configuration

Edit config file directly:
- **Windows**: `%APPDATA%\ImageAI\config.json`
- **macOS**: `~/Library/Application Support/ImageAI/config.json`
- **Linux**: `~/.config/ImageAI/config.json`

Example config:
```json
{
  "provider": "google",
  "google_api_key": "your-key",
  "openai_api_key": "your-key",
  "stability_api_key": "your-key",
  "auto_save": true,
  "output_format": "png",
  "jpeg_quality": 95,
  "default_model": {
    "google": "gemini-2.5-flash-image-preview",
    "openai": "dall-e-3",
    "stability": "stable-diffusion-xl-1024-v1-0"
  }
}
```

### Customizing Prompt Data

The Prompt Builder uses JSON data files that you can customize to add your own options:

**Data Files Location**:
- `data/prompts/artists.json` - Artist names and styles
- `data/prompts/styles.json` - Art styles (Abstract, Anime, Cyberpunk, etc.)
- `data/prompts/mediums.json` - Art mediums and techniques (Oil Painting, Digital Art, etc.)
- `data/prompts/colors.json` - Color schemes
- `data/prompts/lighting.json` - Lighting options
- `data/prompts/moods.json` - Mood descriptors
- `data/prompts/banners.json` - Banner/composition options

**Editing Data Files**:

All data files use simple JSON array format:
```json
[
  "Option 1",
  "Option 2",
  "Option 3"
]
```

**Adding Custom Options**:

1. Open the appropriate JSON file in any text editor
2. Add your new option to the array (maintain JSON format):
```json
[
  "Existing Option",
  "Your New Option",
  "Another New Option"
]
```
3. Save the file
4. Restart ImageAI or reload the Prompt Builder

**Examples**:

Add a new artist to `artists.json`:
```json
[
  "Pablo Picasso",
  "Your Favorite Artist",
  "Another Artist"
]
```

Add a new style to `styles.json`:
```json
[
  "Cyberpunk",
  "My Custom Style",
  "Retro Future"
]
```

**Tips**:
- Keep entries concise and descriptive
- Test your custom options in the Prompt Builder
- Backup files before editing
- Maintain valid JSON format (commas between items, no trailing comma)

### Customizing Search Metadata

The Prompt Builder's semantic search is powered by metadata tags generated using AI. You can regenerate this metadata with your own preferences, add custom tags, or contribute improved metadata back to the community.

#### Understanding the Metadata File

The metadata file (`data/prompts/metadata.json`) contains structured information for each item:

```json
{
  "artists": {
    "Al Jaffee": {
      "tags": ["mad_magazine", "caricature", "satire", "1960s", "comics"],
      "related_styles": ["Comic Art", "Cartoon Art"],
      "related_moods": ["Satirical", "Humorous"],
      "cultural_keywords": ["MAD Magazine", "fold-in", "satirical cartoons"],
      "description": "Legendary MAD Magazine cartoonist",
      "era": "1960s-2010s",
      "popularity": 8
    }
  }
}
```

**Metadata Fields**:
- **tags**: Lowercase keywords for search matching (use underscores, not spaces)
- **related_styles/moods/artists**: Cross-category relationships for discovery
- **cultural_keywords**: Common search terms people might use
- **description**: Brief 1-sentence description
- **era**: Time period (for artists/styles)
- **popularity**: 1-10 score (higher = more well-known)

#### Using generate_tags.py

The `scripts/generate_tags.py` utility uses AI (Google Gemini or OpenAI) to automatically generate semantic metadata for all prompt builder items.

**Basic Usage**:

```bash
# Test mode: Generate tags for first 10 items of each category
python scripts/generate_tags.py --test

# Full generation using default provider (Google Gemini)
python scripts/generate_tags.py

# Use OpenAI instead
python scripts/generate_tags.py --provider openai

# Limit to specific number of items per category
python scripts/generate_tags.py --limit 50

# Use specific model
python scripts/generate_tags.py --provider google --model gemini-2.0-flash-exp
python scripts/generate_tags.py --provider openai --model gpt-5-chat-latest
```

**Authentication**:
- **Google**: Requires API key or gcloud authentication (same as ImageAI Settings)
- **OpenAI**: Requires API key set in ImageAI Settings
- Script automatically detects your authentication method

**Features**:
- **Resume Capability**: If interrupted (Ctrl+C), progress is saved automatically
  - Run script again to resume - already-processed items are skipped
  - Incremental saves after each category prevent data loss
- **Rate Limit Handling**: Automatic exponential backoff on quota errors
- **Progress Tracking**: Real-time progress bar with tqdm
- **Detailed Logging**: Complete log file saved for debugging (`generate_tags_YYYYMMDD_HHMMSS.log`)
- **Graceful Shutdown**: Ctrl+C saves progress cleanly

**Process**:
1. Script loads all items from `data/prompts/*.json` files
2. For each item, sends a prompt to the LLM asking for metadata
3. LLM responds with JSON containing tags, relationships, descriptions, etc.
4. Metadata is validated and saved incrementally to `metadata.json`
5. Progress is saved after each category completes

**Example Session**:
```bash
$ python scripts/generate_tags.py --test
======================================================================
  ImageAI - Tag Generation Script
======================================================================
  Log file: generate_tags_20250112_143022.log
  Press Ctrl+C to abort (progress will be saved)
======================================================================

2025-01-12 14:30:22 - INFO - Test mode: processing only first 10 items per category
2025-01-12 14:30:23 - INFO - Initialized TagGenerator with provider=google, model=gemini/gemini-2.0-flash-exp
2025-01-12 14:30:23 - INFO - Loading prompt builder items...
2025-01-12 14:30:23 - INFO - Processing 60 items across 6 categories
Generating metadata: 100%|████████████████| 60/60 [02:15<00:00,  2.25s/it]
2025-01-12 14:32:38 - INFO - ✓ Saved progress: 60 items total
2025-01-12 14:32:38 - INFO - Metadata saved to: data/prompts/metadata.json
```

#### Adding Custom Tags Manually

You can also edit `metadata.json` directly to add custom tags or improve existing metadata:

1. **Open metadata.json** in any text editor
2. **Find the item** you want to enhance (e.g., "Al Jaffee" under "artists")
3. **Add tags**: Include relevant keywords in the "tags" array
4. **Add cultural_keywords**: Terms people might search for
5. **Update relationships**: Link to related styles, moods, artists
6. **Save the file**
7. **Restart ImageAI** or reload Prompt Builder

**Example - Adding Custom Tags**:
```json
{
  "artists": {
    "Al Jaffee": {
      "tags": [
        "mad_magazine",
        "caricature",
        "satire",
        "1960s",
        "comics",
        "fold_in",          // Added: distinctive MAD feature
        "political_satire"  // Added: specific genre
      ],
      "cultural_keywords": [
        "MAD Magazine",
        "fold-in",
        "satirical cartoons",
        "Spy vs Spy"        // Added: related MAD content
      ]
    }
  }
}
```

**Tips for Manual Editing**:
- Use lowercase with underscores for tags: `comic_book_art`, not `Comic Book Art`
- Keep tags concise (1-3 words max)
- Add common misspellings to cultural_keywords for better discovery
- Test your changes in the Prompt Builder search
- Keep a backup of the original file

#### Contributing Improved Metadata

If you generate high-quality metadata or manually curate better tags, consider sharing:

1. **Test thoroughly**: Ensure search works well with your changes
2. **Document additions**: Note any new tags or relationships you added
3. **Share metadata.json**: Submit via GitHub issue or pull request
4. **Describe methodology**: If using custom LLM prompts, share your approach

**Community Benefits**:
- Better search results for all users
- More accurate cultural keywords and relationships
- Improved discovery of lesser-known artists and styles
- Shared AI prompts for generating consistent metadata

**Metadata Best Practices**:
- **Accuracy**: Verify artist names, eras, and descriptions
- **Completeness**: Include all relevant tags and relationships
- **Consistency**: Use consistent tag formats across similar items
- **Cultural Sensitivity**: Use respectful, inclusive terminology
- **Attribution**: Note sources for factual information (eras, popularity)

### Local Stable Diffusion Settings

When using Local SD provider, advanced settings are available:

**Inference Steps**: Number of denoising steps (1-50)
- More steps = better quality but slower
- Turbo models: 1-4 steps
- Standard models: 20-50 steps
- Real-time preview of step count impact

**Guidance Scale (CFG)**: How closely to follow prompt (0-20)
- Lower (1-5): More creative/artistic
- Medium (7-8): Balanced
- Higher (10-15): More literal prompt following
- Visual indicator shows optimal range per model

**Resolution**: Output image dimensions
- SD 1.5/2.1: 512x512 optimal
- SDXL: 1024x1024 optimal
- Custom sizes supported but may affect quality
- Aspect ratio preservation with smart presets

**Scheduler**: Sampling algorithm
- DPM++ 2M Karras: Good balance
- Euler A: Fast, good for most cases
- DPM++ SDE Karras: Higher quality, slower
- DDIM: Deterministic, good for reproducibility
- LMS: Classic scheduler
- PNDM: Fast convergence

**Additional Controls**:
- **Seed**: Set specific seed for reproducible results
- **Negative Prompt**: Specify what to avoid in generation
- **VAE Selection**: Choose different VAE models for style
- **Attention Slicing**: Memory optimization for large images
- **CPU Offload**: Move models to CPU when not in use

### Hugging Face Model Management

**Using Custom Models**:
```bash
# Download a specific model
python main.py --provider local_sd -m "runwayml/stable-diffusion-v1-5" -p "Test" -o test.png

# Use downloaded model (cached)
python main.py --provider local_sd -m "runwayml/stable-diffusion-v1-5" -p "Art" -o art.png
```

**Popular Models**:
- `stabilityai/stable-diffusion-2-1`: Balanced quality/speed
- `runwayml/stable-diffusion-v1-5`: Classic, widely compatible
- `stabilityai/stable-diffusion-xl-base-1.0`: High quality, 1024x1024
- `segmind/SSD-1B`: Fast SDXL variant
- `stabilityai/sdxl-turbo`: Ultra-fast 1-4 step generation

**Model Cache Location**:
- Default: `~/.cache/huggingface/hub/`
- Size: Models range from 2GB to 7GB
- First use downloads the model
- Subsequent uses load from cache

### Performance Optimization

**GPU Acceleration** (Local SD only):
```bash
# Install CUDA support
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Verify GPU is detected
python -c "import torch; print(torch.cuda.is_available())"
```

**Memory Management**:
- Close other applications when using Local SD
- Use smaller models for limited VRAM (< 6GB)
- Enable attention slicing for large images
- Reduce batch size if out of memory

### Troubleshooting Common Issues

#### Startup Performance

**Typical startup time: 20-30 seconds** on first launch. This is normal and expected due to Qt/PySide6 framework initialization and complex UI creation.

**Startup Time Breakdown:**
- **Qt Framework Loading** (~6 seconds): PySide6/Qt initialization and main window creation
- **UI Tab Creation** (~8 seconds): Building complex tabs like Layout (with templates), Video tab components, and widget initialization
- **Provider Preloading** (<1 second): Loading the selected AI provider (Google, OpenAI, etc.)
- **Settings Restoration** (<1 second): Restoring window geometry, last selections, and UI state
- **History Scanning** (<1 second): Fast scan of generated images folder (optimized to skip debug files)

**What takes the longest:**
1. **Layout Tab**: Template system, schema validation, and font rendering setup
2. **Video Tab Components**: MIDI support, timeline widgets, and scene management UI
3. **Qt WebEngine**: If Help tab uses QtWebEngine for rich rendering
4. **Reference Image Widgets**: Loading and initializing image preview components

**Performance Tips:**
- Startup time is consistent after first launch (libraries are cached)
- Provider switching is faster after initial load (<1 second)
- File scanning is now optimized and near-instant (skips debug images)
- The time is spent on UI creation, not file operations

**Console Output During Startup:**
You'll see progress messages like:
```
Creating application window...
Cleaning up debug images...
Scanning image history...
Creating user interface...
Setting up menus...
Preloading [provider] provider...
Restoring window state...
Application ready!
```

**Note:** The startup performance is typical for full-featured Qt applications with rich UI components. Lightweight CLI mode starts much faster since it skips all GUI initialization.

#### Authentication Errors

**Google API Key Issues**:
- Verify key at [AI Studio](https://aistudio.google.com/apikey)
- Check billing is enabled
- Ensure API is not restricted by IP

**Google Cloud Auth Issues**:
```bash
# Verify authentication
gcloud auth list
gcloud auth application-default print-access-token

# Enable required APIs
gcloud services enable aiplatform.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com

# Check project
gcloud config get-value project
```

**OpenAI Issues**:
- Verify key at [OpenAI Platform](https://platform.openai.com/api-keys)
- Check rate limits and quotas
- Ensure billing is active

#### Installation Problems

**Windows PowerShell**:
```powershell
# If scripts are blocked
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# If gcloud not found
$env:PATH += ";C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin"
```

**Module Import Errors**:
```bash
# Reinstall specific package
pip install --upgrade google-genai
pip install --upgrade PySide6

# Clear pip cache
pip cache purge
```

#### GUI Issues

**PySide6 not loading**:
```bash
# Install with specific version
pip install PySide6==6.5.3

# Linux: Install system dependencies
sudo apt-get install python3-pyside6
```

**Display scaling issues**:
```bash
# Set Qt scaling
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_SCALE_FACTOR=1.25
```

### Error Messages

| Error | Solution |
|-------|----------|
| "API key not found" | Set key via Settings or use `-s -k YOUR_KEY` |
| "Quota exceeded" | Check billing and quotas in provider console |
| "Invalid prompt" | Avoid restricted content, check provider policies |
| "Module not found" | Run `pip install -r requirements.txt` |
| "gcloud not found" | Install Google Cloud SDK or use API key mode |

## 11. Utility Scripts

### Configuration Migration (`migrate_config.py`)

Migrates old configuration formats to the current structure and optionally secures API keys.

**Usage:**
```bash
# Dry run to see what changes would be made
python migrate_config.py --dry-run

# Perform migration
python migrate_config.py

# Migration without securing keys
python migrate_config.py --no-secure
```

**What it does:**
- Removes legacy `api_key` field from root level
- Fixes incorrect `keys.<provider>` structure
- Moves all API keys to proper `providers.<provider>.api_key` format
- Attempts to secure keys in system keyring when available
- Creates timestamped backups before making changes

### API Key Security (`secure_keys.py`)

**Windows only:** Moves API keys from plaintext config.json to Windows Credential Manager for encryption.

**Usage (run in Windows PowerShell/Command Prompt, not WSL):**
```bash
cd D:\path\to\ImageAI
python secure_keys.py
```

**What it does:**
- Reads API keys from config.json
- Stores them securely in Windows Credential Manager (encrypted by OS)
- Removes plaintext keys from config.json
- Creates backup before modification
- Keys are automatically retrieved by the app when needed

**Benefits:**
- API keys are encrypted by Windows
- Keys survive config.json deletion/corruption
- More secure than plaintext storage
- Works seamlessly with the application

## 12. Frequently Asked Questions

### General Questions

**Q: Which provider should I use?**
A: It depends on your needs:
- **Google Gemini**: Best for general purpose, good quality, reliable
- **OpenAI DALL-E**: Best for creative/artistic images
- **Stability AI**: Best for photorealistic and detailed images
- **Local SD**: Best for privacy, unlimited generation, customization

**Q: Can I use multiple providers?**
A: Yes! You can switch providers anytime in Settings or via CLI `--provider` flag.

**Q: Are my prompts and images private?**
A: 
- API providers (Google, OpenAI, Stability) process prompts on their servers
- Local SD runs entirely on your machine - fully private
- Generated images are saved locally only

**Q: How much does it cost?**
A: See the detailed pricing table below for current rates across all providers.

### Setup Issues

**Q: "API key not found" error**
A: 
1. Make sure you've entered the key in Settings
2. Click "Save & Test" to save it
3. Check the key is valid on provider's website

**Q: "Module not found" error**
A: Run `pip install -r requirements.txt` in your terminal

**Q: GUI won't start on Linux**
A: Install system Qt libraries: `sudo apt-get install python3-pyside6`

**Q: Local SD says "No module named 'diffusers'"**
A: Install Local SD dependencies: `pip install -r requirements-local-sd.txt`

### Image Generation Issues

**Q: "Safety filter triggered" or "Blocked" message**
A: Your prompt may contain restricted content. Try:
- Rephrasing your prompt
- Avoiding violence, explicit content, or real people's names
- Using more general terms

**Q: Images are low quality**
A: 
- Add quality modifiers: "high quality", "detailed", "4K"
- Try different models (DALL-E 3, SDXL)
- For Local SD: increase steps and guidance scale

**Q: Generation is very slow**
A: 
- API providers: Network speed dependent, typically 5-20 seconds
- Local SD on CPU: Can take 2-10 minutes
- Local SD on GPU: Usually 10-60 seconds
- Use turbo models for faster generation

**Q: "Out of memory" with Local SD**
A:
- Use smaller models (SD 1.5 instead of SDXL)
- Reduce image resolution
- Close other applications
- Consider upgrading GPU VRAM

### Feature Questions

**Q: Can I edit existing images?**
A: Not yet in current version. Planned features include inpainting and image-to-image.

**Q: Can I generate multiple images at once?**
A: Currently one at a time in GUI. Use CLI with shell scripts for batch generation.

**Q: Can I use my own Stable Diffusion models?**
A: Yes! With Local SD, enter any Hugging Face model ID or use the Model Browser.

**Q: Is there a web version?**
A: Not currently. This is a desktop application. Web interface is planned for future.

**Q: Can I use this commercially?**
A: Check each provider's terms:
- Google, OpenAI: Commercial use allowed with paid plans
- Stability AI: Commercial use allowed
- Local SD: Depends on specific model license

## 13. Pricing and Cost Comparison

### Image Generation Pricing Table (January 2025)

| Provider | Model | Free Tier | API Cost per Image | Subscription Plans |
|----------|-------|-----------|-------------------|-------------------|
| **Google Gemini** | | | | |
| | Gemini 2.5 Flash (Image Preview) | **25 images/day**<br>5 requests/min<br>Via AI Studio (free) | $0.039 @ 1024x1024<br>($30 per 1M tokens) | Gemini Advanced: $19.99/mo<br>• 100-150 images/day<br>• Priority access |
| **OpenAI** | | | | |
| | DALL·E 3 | **2 images/day**<br>(via ChatGPT free) | Standard: $0.04 @ 1024x1024<br>HD: $0.08 @ 1024x1024<br>Large: $0.08-0.12 @ 1024x1792 | ChatGPT Plus: $20/mo<br>• Unlimited within caps<br>• GPT-4 access included |
| | DALL·E 2 | None | $0.02 @ 1024x1024<br>$0.018 @ 512x512<br>$0.016 @ 256x256 | Included in Plus |
| | GPT-4o Image | **40 images/month**<br>(via API free tier) | $0.035 @ 1024x1024 | Same as above |
| **Stability AI** | | | | |
| | Stable Diffusion XL | **25 free credits**<br>on signup | ~$0.01-0.02 per image<br>(credit-based) | Stable Assistant: $9/mo<br>Commercial: $20/mo<br>Enterprise: Custom |
| | SD 3.5 Large | Limited free credits | ~$0.068 @ 1024x1024<br>(via third-party APIs) | Included in plans |
| **Local SD** | | | | |
| | Any Hugging Face Model | **Unlimited** | **$0** (your hardware) | N/A |

### Detailed Pricing Notes

#### Google Gemini
- **Free Tier**: 25 requests/day, 5 RPM via AI Studio (completely free)
- **Token Pricing**: Images consume ~1,290 tokens for 1024x1024
- **Rate Limits**: Preview models have stricter limits
- **Limitations**: Currently only generates square (1:1) images regardless of aspect ratio settings
- **Best For**: Free testing, development, and moderate usage

#### OpenAI
- **Free Access**: ChatGPT free users get 2 DALL·E images/day
- **API Free Tier**: New accounts get 40 images/month free
- **Quality Tiers**: Standard vs HD (2x price for better quality)
- **Resolution Impact**: Larger sizes cost 2-3x more
- **Best For**: High-quality artistic images, professional use

#### Stability AI
- **Credit System**: 6.5 credits per image, 0.1 credit per message
- **Community License**: FREE for businesses <$1M annual revenue
- **Enterprise License**: Required for >$1M revenue (custom pricing)
- **Open Source**: Models can be self-hosted for free
- **Best For**: High-volume generation, customization needs

#### Local Stable Diffusion
- **Completely Free**: No API costs, unlimited generation
- **Hardware Requirements**: 
  - Minimum: 8GB RAM (CPU mode, slow)
  - Recommended: 6GB+ VRAM GPU
  - Optimal: 12GB+ VRAM for SDXL models
- **Generation Speed**: 
  - CPU: 2-10 minutes per image
  - GPU: 10-60 seconds per image
- **Best For**: Privacy, unlimited generation, experimentation

### Cost Optimization Tips

1. **For Hobbyists**: Use Google Gemini free tier (25 images/day)
2. **For Developers**: Start with free tiers, upgrade as needed
3. **For Production**: Compare subscription vs API costs based on volume
4. **For Privacy**: Use Local SD with one-time hardware investment
5. **For Quality**: OpenAI DALL·E 3 HD or Stability AI enterprise

### Monthly Cost Examples

| Usage Pattern | Best Option | Monthly Cost |
|--------------|-------------|--------------|
| <25 images/day | Google Gemini Free | **$0** |
| 50-100 images/day | ChatGPT Plus | $20 |
| 500 images/month | Mix free tiers + API | ~$10-20 |
| 1000+ images/month | Stability AI subscription | $20 |
| Unlimited | Local SD | $0 (after setup) |

### Enterprise and Volume Pricing

- **Google Cloud**: Custom Vertex AI pricing, volume discounts
- **OpenAI**: Enterprise agreements available, contact sales
- **Stability AI**: Custom pricing for >$1M revenue companies
- **Azure OpenAI**: Enterprise SLAs, regional deployment options

### Google Veo Video Generation Pricing

Since ImageAI's Video Project feature is designed to work with Google Veo for AI video generation, here's the current pricing:

#### AI Video Generation Models (January 2025)

| Model | Model ID | Duration | Audio | Gemini API Price | Features |
|-------|----------|----------|-------|-----------------|----------|
| **Veo 3** | `veo-3.0-generate-001` | 8 sec | ✅ Yes | $0.75/second<br>($6.00/video) | Best quality, physics-accurate |
| **Veo 3 Fast** | `veo-3.0-fast-generate-001` | 8 sec | ✅ Yes | $0.40/second<br>($3.20/video) | Optimized for speed |
| **Veo 2** | `veo-2.0-generate-001` | 5-8 sec | ❌ No | $0.35/second<br>($2.10-2.80/video) | 4K support, no audio |

#### Subscription Options

| Plan | Price/Month | Video Credits | Best For |
|------|------------|---------------|----------|
| **Google AI Pro** | $19.99 | 90 Veo 3 Fast videos | Individual creators |
| **Google AI Ultra** | $249.99 | Higher limits + Veo 3 | Professional use |
| **API Pay-as-you-go** | Usage-based | Unlimited | Developers |

**Notes**: 
- Videos are 8 seconds max (chain for longer content)
- Generated videos stored for 2 days only
- All videos include SynthID watermark
- Available in US (consumer plans), global via Vertex AI

## 14. API Reference

### Provider Specifications

#### Google Gemini Models
- `gemini-2.5-flash-image-preview` (default)
- `gemini-2.0-flash-lite-preview-02-05`
- `gemini-2.0-flash-thinking-exp-01-21`

#### OpenAI Models
- `dall-e-3` (default) - Best quality, 1024x1024
- `dall-e-2` - Good quality, multiple sizes

#### Stability AI Models
- `stable-diffusion-xl-1024-v1-0` (default) - SDXL, best quality
- `stable-diffusion-v1-6` - SD 1.6, balanced
- `stable-diffusion-512-v2-1` - SD 2.1, faster
- `stable-diffusion-xl-beta-v2-2-2` - SDXL beta

#### Local SD Models (Hugging Face)
- `stabilityai/stable-diffusion-2-1` (default)
- `runwayml/stable-diffusion-v1-5` - Popular SD 1.5
- `stabilityai/stable-diffusion-xl-base-1.0` - SDXL base
- `segmind/SSD-1B` - Fast SDXL variant
- Custom models from Hugging Face Hub

### Rate Limits

| Provider | Requests/Min | Daily Limit | Notes |
|----------|-------------|-------------|--------|
| Google (Free) | 60 | 1,500 | Varies by region |
| Google (Paid) | 360 | Unlimited | Billing required |
| OpenAI | Varies | By tier | Check dashboard |
| Stability AI | 150 | By credits | Pay per generation |
| Local SD | Unlimited | Unlimited | Limited by hardware |

### Response Formats

All API providers return images as base64-encoded PNG data or URLs, automatically decoded and saved by the application. Local SD generates images directly as PIL Image objects.

## 15. Development

### Project Structure

```
ImageAI/
├── main.py                   # Main entry point
├── cli/                      # CLI interface
├── gui/                      # GUI interface
├── core/                     # Core functionality
├── providers/                # Provider implementations
│   ├── base.py              # Base provider interface
│   ├── google.py            # Google Gemini provider
│   ├── openai.py            # OpenAI DALL-E provider
│   ├── stability.py         # Stability AI provider
│   └── local_sd.py          # Local Stable Diffusion
├── templates/                # Prompt templates
├── requirements.txt          # Core dependencies
├── requirements-local-sd.txt # Local SD dependencies
├── README.md                 # This file
├── CLAUDE.md                 # Claude AI guidance
├── GEMINI.md                 # Gemini setup guide
├── Plans/                    # Future development plans
│   ├── GoogleCloudAuth.md
│   ├── NewProviders.md
│   └── ProviderIntegration.md
└── .gitignore                # Git ignore rules
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Future Plans

- ✅ Stability AI integration (completed)
- ✅ Local Stable Diffusion support (completed)
- ✅ Video Project System with version control (completed)
- ✅ Google Veo AI video generation (completed)
- ✅ Layout/Books system for photo books and comics (completed)
- ✅ Multiple reference images with Imagen 3 (completed)
- Advanced video transitions and effects (in progress)
- Multi-track audio support (in progress)
- Image editing capabilities (inpainting, outpainting) - Partially implemented
- Local model management GUI (Phase 3 in progress)
- Layout template marketplace and custom template editor
- Batch processing improvements
- Plugin system for custom providers
- Additional providers (Midjourney API, Adobe Firefly, etc.)
- Web interface option
- Mobile app companion

## 16. Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete version history and release notes.

## 17. Screenshots Gallery

### UI when using a reference image for Facebook cover photo.
Sizes are automatically set when using the "Social Sizes" button!

![screenshot_20250915.png](screenshot_20250915.png)

### Generation Workflow

#### Before Generation
Starting point with an empty canvas, ready for your creative prompts.

![Before Generation](Screenshots/screenshot_before_generate.png)
*Clean interface state before generating any images - shows the prompt input area and configuration options*

#### Generate with AI Prompt
Creating images using AI-powered prompt generation for optimal results.

![Generate Prompt with AI](Screenshots/screenshot_generate_prompt_with_AI.png)
*Using the AI prompt generation feature to create detailed, optimized prompts for better image quality*

#### Enhance Existing Prompts
Improving and refining your prompts with AI assistance for more detailed outputs.

![Enhance Prompt with AI](Screenshots/screenshot_enhance_prompt_with_AI.png)
*The AI enhancement feature taking simple prompts and expanding them with artistic details and style descriptions*

### Features Demonstrated

The screenshots showcase:
- **Multi-Provider Support**: Switch seamlessly between Google Gemini, OpenAI DALL·E, Stability AI, and Local SD
- **AI-Powered Prompts**: Generate and enhance prompts using GPT-5, Claude, Gemini, or local LLMs
- **Flexible Resolution Control**: Aspect ratio presets, custom ratios, and direct resolution input
- **Real-time Console**: Color-coded status messages showing generation progress and API interactions
- **Session Persistence**: All settings and history maintained between sessions
- **Cost Tracking**: Real-time cost estimation for all providers
- **Tabbed Navigation**: Easy access to Image, Templates, Video, Settings, and Help sections
- **History Tracking**: Visual timeline of all generated images with metadata

## Credits

Created by Leland Green | [LelandGreen.com](https://www.lelandgreen.com)
Contact: | [contact@lelandgreen.com](mailto:contact@lelandgreen.com)

Built with:
- Claude Code and online
- Codex CLI and online
- Gemini CLI
- JetBrains PyCharm
- PySide6/Qt Framework
- Google Gemini API
- OpenAI API

## License

See LICENSE file for details.

## Support

For issues, feature requests, or questions:
- GitHub Issues: [Create an issue](https://github.com/lelandg/ImageAI/issues)
- Support: contact@lelandgreen.com
- **LelandGreen.com on Discord -- The Intersection of Art and AI** [Discord](https://discord.gg/a64xRg9w)
- Fun stuff:
    - Original Boogie Woogie! [Leland Green's Boogie Woogie (HQ) on SoundCloud](https://soundcloud.com/aboogieman/leland-greens-boogie-woogie-hq)
    - [Leland's Old Art](https://www.flickr.com/photos/lelandgreen/albums/72177720314118018)
    - Art Gallery: [Art by Leland](https://www.flickr.com/photos/lelandgreen/albums/72157643063177694/)
- Fun stuff:
  - [Leland Green's Boogie Woogie (HQ) on SoundCloud](https://soundcloud.- com/aboogieman/leland-greens-boogie-woogie-hq)
  - Old art 
 
---

**Happy Creating!** 🎨

