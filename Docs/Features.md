# ImageAI Features

> A comprehensive desktop application and CLI for multi-provider AI image generation, video creation, and professional layout design with enterprise-grade authentication.

## Core Features

### Multi-Provider Image Generation
- **Google Gemini** - Access Gemini 2.5 Flash Image and Nano Banana Pro (4K) models
- **OpenAI DALL·E** - Support for GPT Image 1.5, DALL·E 3, and DALL·E 2
- **Stability AI** - Stable Diffusion XL, SD 2.1, and more via API
- **Local Stable Diffusion** - Run models locally without API keys (GPU recommended)
- **Midjourney** - Integration for Midjourney generation
- **Ollama** - Local model support via Ollama server

### Flexible Authentication
- **API Key Mode** - Simple setup with per-provider key management
- **Google Cloud ADC** - Enterprise-ready Application Default Credentials
- **Secure Storage** - Platform-specific credential storage (AppData/Library/~/.config)

### Dual Interface
- **Modern GUI** - Qt/PySide6 desktop application with tabbed interface
- **Powerful CLI** - Full automation support with all generation options

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Launch GUI: `python main.py`
3. Configure API key in Settings tab (or use `-k` flag for CLI)
4. Enter a prompt and click Generate (or use `-p "prompt" -o output.png` for CLI)

## Feature Details

### Image Generation Tab

Generate AI images with fine-grained control over every aspect of the output.

- Enter text prompts with multi-line support and built-in search (Ctrl+F)
- Select provider and model from dynamically populated dropdowns
- Choose aspect ratio with visual preview buttons (1:1, 3:4, 4:3, 16:9, 9:16, 21:9)
- Set custom aspect ratios like "16:10" or decimal "1.6"
- Toggle between aspect ratio mode and direct resolution selection
- Generate 1-4 image variations in a single batch
- View real-time cost estimation before generating
- Track generation progress with live status updates

### Reference Images

Use existing images to guide AI generation with two specialized modes.

**Flexible Mode (Google Gemini):**
- Add unlimited reference images for style transformation
- Automatic compositing creates character design sheets from 2+ images
- Ideal for converting photos to cartoons or artistic styles

**Strict Mode (Imagen 3 Customization):**
- Up to 3 references with precise control per image
- Reference types: SUBJECT (person/animal/product), STYLE, CONTROL (canny/scribble/face_mesh)
- Optional descriptions and reference IDs ([1], [2], [3]) for prompt use
- Maintains character consistency across generations

**Edit Mode:**
- Load any generated image from history for enhancement
- Automatically preserves original prompt and all metadata
- Streamlined workflow for iterative refinement

### AI Prompt Tools

Enhance your prompts and get creative assistance with integrated LLM features.

- **Enhance Prompt** - Improve prompts with AI assistance (one-click)
- **Generate Prompts** - Create multiple prompt variations with history tracking
- **Ask AI Anything** - Interactive Q&A for prompt help with conversation context
- **Reference Image Analysis** - Upload images for AI-generated descriptions
- **Multi-Provider LLM Support** - OpenAI GPT-5, Claude, Gemini, Ollama, LM Studio

### Prompt Builder

Build comprehensive prompts with a professional modular template system.

- Select from subject types, transformation styles, art styles, mediums
- Choose lighting, mood, artist influences, and background options
- Add exclusions with automatic "no" prefix processing
- Watch live preview as you build your prompt
- Save to history and export/import prompts as JSON
- Load presets: MAD Magazine Style, Cyberpunk Neon, Renaissance Portrait, Anime Character, and more

### Advanced Generation Controls

Fine-tune generation parameters for precise results.

| Control | Range | Description |
|---------|-------|-------------|
| Inference Steps | 1-50 | Quality vs speed tradeoff |
| Guidance Scale (CFG) | 0-20 | How closely to follow the prompt |
| Seed | Any integer | Reproducible generation |
| Negative Prompts | Free text | What to avoid in output |
| Prompt Rewriting | Toggle | AI enhancement of prompts |

### Video Project Tab

Create AI-powered videos from text with MIDI synchronization and karaoke overlays.

**Project Management:**
- Create, open, save, and manage multiple video projects
- Version control with event sourcing and time-travel restoration
- Auto-save after generation operations

**Text Processing:**
- Timestamped lyrics: `[00:30] First verse lyrics`
- Structured sections: `# Verse 1`, `# Chorus`, `# Bridge`
- Plain text with intelligent scene detection
- Custom scene markers for precise control

**Storyboard & Scenes:**
- Interactive scene table with direct editing
- Adjustable duration per scene (0.5-30 seconds)
- Drag-and-drop scene reordering
- Batch operations across multiple scenes

**Rendering Options:**
- **FFmpeg Slideshow** - Ken Burns effects, transitions, up to 4K resolution, 24/30/60 fps
- **Google Veo 3.0/3.1** - AI motion video with automatic frame continuity

**MIDI & Karaoke:**
- MIDI-based timing for perfect beat/measure alignment
- Musical structure detection (verse, chorus, bridge)
- Karaoke overlays: bouncing ball, highlighting, fade-in
- Export to LRC, SRT, and ASS subtitle formats
- Import Suno packages with stem merging

### Layout/Books Tab

Professional layout engine for photo books, comics, and publications.

- **Templates** - Children's book, comic book, magazine, photo book layouts
- **Typography** - Word wrapping, hyphenation, widow/orphan control, justification
- **Image Processing** - Rounded corners, filters (blur/grayscale/sepia/sharpen), borders
- **Export** - PDF with embedded fonts or PNG sequence at 300 DPI

### Character Animator Puppet Creation

Convert character images into animatable puppets for Adobe Character Animator.

- AI body segmentation using MediaPipe and SAM 2
- Generate 14 mouth visemes for lip-sync animation
- Create eye blink states for natural animation
- Occlusion inpainting fills hidden body parts
- Export to PSD or SVG with Adobe-compatible naming
- Heavy AI components install on first use (~8-12GB)

### AI Image Upscaling

Enhance image resolution with state-of-the-art AI upscaling.

- **Real-ESRGAN** - AI upscaling for enhanced quality
- **GPU Acceleration** - Automatic NVIDIA GPU detection
- **One-Click Install** - Install directly from the application
- **Multiple Methods** - AI upscaling, Lanczos, or cloud services

### History & Tracking

Track all generations with detailed metadata.

- Thumbnail preview, date/time, provider, model, prompt, resolution, cost
- Reference images indicator with tooltip showing linked files
- Double-click to reload prompt and all settings
- Hover for instant image preview
- Filter by provider, search by prompt, sort by date/cost/model
- JSON sidecar files with complete generation metadata

### Wikimedia Commons Integration

Access millions of freely licensed images for reference and inspiration.

- Search by keywords with real-time results
- Filter by license type (Public Domain, CC BY, CC BY-SA)
- Batch download with automatic integration to reference panel
- Complete licensing and attribution information

### Discord Rich Presence

Show your ImageAI activity in Discord status.

- Privacy levels: Full (provider/model), Activity Only, or Minimal
- Optional elapsed time and GitHub link button
- Graceful handling when Discord isn't running

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| Provider | Image generation provider | google |
| Model | Provider-specific model | gemini-2.5-flash-image |
| Image Size | Output dimensions | 1024x1024 |
| Quality | Standard or HD | standard |
| Auto-save | Save images automatically | enabled |
| Output Directory | Where images are saved | ~/ImageAI/generated |
| Copy Filename | Copy path to clipboard | disabled |
| Discord RPC | Show activity in Discord | disabled |

## Supported Formats

**Image Input:**
- PNG, JPEG, WebP for reference images

**Image Output:**
- PNG (default), JPEG, WebP

**Video:**
- MP4, AVI, MOV output
- MIDI (.mid) for timing synchronization
- MP3, WAV, M4A, OGG audio tracks
- LRC, SRT, ASS subtitle export

**Project Files:**
- JSON for video projects and prompt history
- PSD, SVG for Character Animator export
- PDF, PNG for Layout/Books export

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+Enter | Generate image (from anywhere in Generate tab) |
| Ctrl+S | Save generated image |
| Ctrl+Shift+C | Copy image to clipboard |
| F1 | Jump to Help tab |
| F3 | Find next (in Help tab) |
| Shift+F3 | Find previous (in Help tab) |
| F11 | Full screen mode |
| Ctrl+N | New generation |
| Ctrl+Q | Exit application |
| Escape | Close dialog |

## CLI Reference

```bash
# Generate image
python main.py -p "A sunset over mountains" -o sunset.png

# Use specific provider and model
python main.py --provider openai -m dall-e-3 -p "Abstract art" -o art.png

# Test API key
python main.py -t

# Save API key
python main.py -s -k "YOUR_API_KEY"

# Use Google Cloud authentication
python main.py --auth-mode gcloud -p "Space station" -o space.png

# Convert lyrics to prompts
python main.py --lyrics-to-prompts lyrics.txt --lyrics-style cinematic
```

## Platform Support

- **Windows** - Full support (config: `%APPDATA%\ImageAI\`)
- **macOS** - Full support (config: `~/Library/Application Support/ImageAI/`)
- **Linux** - Full support (config: `~/.config/ImageAI/`)

---

*Version 0.31.1 | [GitHub Repository](https://github.com/lelandg/ImageAI) | [Chameleon Labs Discord](https://discord.gg/chameleonlabs)*
