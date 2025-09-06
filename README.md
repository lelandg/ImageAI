# ImageAI — Advanced AI Image Generation

###### See [LelandGreen.com](https://www.lelandgreen.com) for links to other code and free stuff.
#### Created with _JetBrains **PyCharm**_ and AI assistance
###### Enterprise-ready with multiple authentication methods and provider support  

## Overview

**ImageAI** is a powerful desktop application and CLI tool for AI image generation supporting multiple providers including Google's Gemini API, OpenAI's DALL·E models, Stability AI's Stable Diffusion, and local Stable Diffusion models. It features enterprise-grade authentication options, secure credential management, and works seamlessly across Windows, macOS, and Linux.

![ImageAI Screenshot](screenshot_20250906.jpg)

## Key Features

### 🎨 Multi-Provider Support
- **Google Gemini** - Access to latest Gemini models for image generation
- **OpenAI DALL·E** - Support for DALL·E-3 and DALL·E-2 models
- **Stability AI** - Stable Diffusion XL, SD 2.1, and more via API
- **Local Stable Diffusion** - Run models locally without API keys (GPU recommended)
- Easy provider switching in both GUI and CLI
- Support for custom Hugging Face models

### 🔐 Flexible Authentication
- **API Key Authentication** - Simple setup for individual users
- **Google Cloud Authentication** - Enterprise-ready with Application Default Credentials
- Secure credential storage in platform-specific directories
- Environment variable support for CI/CD integration

### 💻 Dual Interface
- **Modern GUI** - User-friendly desktop interface built with Qt/PySide6
- **Powerful CLI** - Full-featured command-line interface for automation
- Cross-platform support (Windows, macOS, Linux)

### 📁 Smart Features
- Auto-save generated images with metadata sidecars
- Template system with placeholder substitution
- In-session history tracking
- Customizable output paths and filenames
- Batch generation support

## Table of Contents
- [Requirements](#1-requirements)
- [Authentication Setup](#2-authentication-setup)
- [Installation](#3-installation)
- [Running the Application](#4-running-the-application)
- [Authentication Management](#5-authentication-management)
- [CLI Reference](#6-cli-reference)
- [GUI Features](#7-gui-features)
- [Image Management](#8-image-management)
- [Examples & Templates](#9-examples--templates)
- [Troubleshooting](#10-troubleshooting)
- [API Reference](#11-api-reference)
- [Development](#12-development)
- [Changelog](#13-changelog)

## 1) Requirements

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

## 2) Authentication Setup

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

## 3) Installation

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
- **Linux**: Install python3-venv if not present: `sudo apt install python3-venv`

## 4) Running the Application

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

## 5) Authentication Management

### Key Storage Locations

Configuration and keys are stored in platform-specific directories:

- **Windows**: `%APPDATA%\ImageAI\config.json`
- **macOS**: `~/Library/Application Support/ImageAI/config.json`
- **Linux**: `~/.config/ImageAI/config.json`

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

## 6) CLI Reference

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

## 7) GUI Features

### Main Interface

#### Generate Tab
- **Model Selection**: Dropdown with provider-specific models
- **Prompt Input**: Multi-line text area for detailed prompts
- **Generate Button**: Start image generation
- **Image Display**: Preview generated images
- **Output Text**: View generation status and file paths
- **Examples Button**: Access curated prompts

#### Settings Tab
- **Provider Selection**: Switch between Google and OpenAI
- **Authentication Mode** (Google only):
  - API Key mode with key input field
  - Google Cloud Account mode with status display
- **Helper Buttons**:
  - Get API Key - Opens provider's key page
  - Load from File - Import key from text file
  - Check Status - Verify Google Cloud auth
  - Cloud Console - Open Google Cloud Console
- **Auto-save Options**: Configure clipboard and file handling

#### Templates Tab
- Predefined prompt templates with placeholders
- Variable substitution system
- Append or replace current prompt
- Custom template creation

#### Help Tab
- Embedded documentation
- Quick reference guide
- Keyboard shortcuts

### Menu System

#### File Menu
- Save Image As... (Ctrl+S)
- Exit (Ctrl+Q)

#### Edit Menu
- Copy prompt
- Paste prompt
- Clear all

#### View Menu
- History panel
- Full screen mode

## 8) Image Management

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

## 9) Examples & Templates

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

Built-in templates with placeholders:

```
"[style] painting of [subject] in [setting], [mood] lighting"
"Photograph of [object] with [effect], [camera] angle, [quality]"
"[character] in [action] at [location], [art_style] style"
```

Variables are replaced with user input or defaults.

## 10) Troubleshooting

### Common Issues

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

## 11) API Reference

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

## 12) Development

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
- Image editing capabilities (inpainting, outpainting) - Partially implemented
- Local model management GUI (Phase 3 in progress)
- Batch processing improvements
- Plugin system for custom providers
- Additional providers (Midjourney API, Adobe Firefly, etc.)
- Web interface option
- Mobile app companion

## 13) Changelog

### v0.7.0 (2025-09-06)
- Added Google Cloud authentication support (Application Default Credentials)
- New `--auth-mode` CLI flag for authentication method selection
- Enhanced GUI Settings with auth mode selector and helper buttons
- Improved Windows/PowerShell compatibility
- Added comprehensive API enablement documentation
- Project renamed to ImageAI

### v0.6.0 (2025-08-29)
- Added OpenAI provider with DALL·E-3 and DALL·E-2 support
- Per-provider API key management
- Provider switching in GUI and CLI
- Enhanced error messages and guidance

### v0.3.0 (2025-08-29)
- Initial public release
- Google Gemini integration
- GUI and CLI interfaces
- Auto-save with metadata sidecars
- Template system

## Credits

Created by Leland Green | [LelandGreen.com](https://www.lelandgreen.com)

Built with:
- JetBrains PyCharm
- PySide6/Qt Framework
- Google Gemini API
- OpenAI API

## License

See LICENSE file for details.

## Support

For issues, feature requests, or questions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/ImageAI/issues)
- Email: support@lelandgreen.com

---

**Happy Creating!** 🎨