# **CLAUDE.md - ImageAI Project Instructions**
*Created for use with Claude Desktop | ImageAI v0.20.0*

## Project Overview

**ImageAI** is a sophisticated multi-provider AI image and video generation desktop application built with Python, PySide6, and multiple AI provider integrations. The project demonstrates advanced software architecture with provider abstraction, event-driven design, and comprehensive state management.

**Version**: 0.10.5  
**Primary Language**: Python 3.9-3.13  
**Tech Stack**: PySide6 (Qt), Google Gemini API, OpenAI API, Stability AI, Hugging Face Diffusers, FFmpeg, LiteLLM  
**Architecture Pattern**: Modular provider system with worker threads, event sourcing for video projects

---

## Core Philosophy & Standards

### Development Principles

1. **Professional Excellence**: Code should be production-ready, well-documented, and maintainable
2. **Artistic Sensibility**: UI/UX should be intuitive and delightful - balance functionality with aesthetics
3. **Ethical AI**: Responsible use of AI technologies, respect for copyright and user privacy
4. **Cross-Platform First**: Windows, macOS, and Linux must all work seamlessly
5. **Provider Agnostic**: New providers should integrate cleanly via the base provider interface

### Code Quality Standards

- **Type Hints**: Use comprehensive type hints for all functions and methods
- **Docstrings**: All classes and public methods must have clear docstrings (Google style preferred)
- **Error Handling**: Comprehensive try-except blocks with informative error messages
- **Logging**: Use Python's logging module for debug/info/warning/error appropriately
- **Testing**: Critical paths should have unit tests (though coverage could be improved)

---

## Project Structure

```
ImageAI/
├── main.py                 # Entry point - CLI and GUI launcher
├── cli/                    # Command-line interface
├── gui/                    # PySide6 GUI components
│   ├── main_window.py     # Primary GUI orchestrator
│   ├── video_tab.py       # Video project UI (complex state management)
│   └── widgets/           # Reusable UI components
├── core/                   # Core business logic
│   ├── config.py          # Configuration management
│   ├── image_generator.py # Main generation orchestrator
│   └── metadata.py        # JSON sidecar metadata
├── providers/              # Provider implementations
│   ├── base.py            # Abstract base provider interface
│   ├── google.py          # Gemini integration
│   ├── openai.py          # DALL-E integration
│   ├── stability.py       # Stability AI integration
│   └── local_sd.py        # Local Stable Diffusion
├── video/                  # Video generation subsystem
│   ├── project.py         # Event sourcing project model
│   ├── renderer.py        # FFmpeg rendering pipeline
│   └── llm_integration.py # Multi-provider LLM for prompts
├── templates/              # Prompt template system
├── requirements.txt        # Core dependencies
└── requirements-local-sd.txt  # Optional ML dependencies
```

---

## Key Architectural Patterns

### 1. Provider Abstraction Pattern

All AI providers implement the `BaseProvider` interface in `providers/base.py`:

```python
class BaseProvider(ABC):
    @abstractmethod
    async def generate_image(self, prompt: str, **kwargs) -> Image:
        """Generate image with provider-specific implementation"""
        pass
    
    @abstractmethod
    def validate_credentials(self) -> bool:
        """Check if provider credentials are valid"""
        pass
```

**When adding new providers**: Subclass `BaseProvider`, implement all abstract methods, add to provider registry in `core/config.py`.

### 2. Event Sourcing (Video Projects)

The video project system uses event sourcing for complete version control:
- All changes are stored as immutable events
- Project state can be reconstructed from event log
- Time-travel debugging via restoration points
- Located in `video/project.py` - study this for state management patterns

### 3. Worker Thread Pattern

Long-running operations (image generation, video rendering) run in `QThread` workers to keep UI responsive:
- Signals/slots for progress updates
- Cancel tokens for graceful termination
- Error propagation via signals

### 4. Configuration Management

Multi-layered configuration system:
1. Platform-specific config directories (Windows: `%APPDATA%`, macOS: `~/Library/Application Support`, Linux: `~/.config`)
2. Environment variables (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, etc.)
3. Command-line arguments
4. In-app settings UI

**Priority order**: CLI args > stored config > environment variables > defaults

---

## Current Focus Areas for Improvement

### High-Priority Enhancements

1. **Video Project Stabilization** (video/*)
   - The video generation system is feature-rich but needs stability improvements
   - Focus on: timing synchronization, LLM response parsing robustness, MIDI lyric extraction
   - Known issues: Fragment handling in karaoke timing, Gemini response size limits

2. **Local SD Model Management** (providers/local_sd.py, gui/model_browser.py)
   - Phase 3 of model browser implementation is incomplete
   - Need: better model discovery, caching improvements, GPU memory management

3. **Error Recovery & User Feedback** 
   - Enhance error messages with actionable suggestions
   - Add retry logic with exponential backoff for API calls
   - Implement better progress indicators during multi-step operations

4. **Testing Coverage**
   - Critical paths like provider switching, configuration migration, metadata handling need tests
   - Add integration tests for video rendering pipeline
   - Mock external API calls for reliable CI/CD

### Code Modernization Opportunities

- **Async/Await**: Some synchronous API calls could be made async for better performance
- **Type Safety**: Add `Protocol` classes for duck-typed interfaces
- **Dependency Injection**: Replace global config with DI for better testability
- **Pydantic Models**: Replace dict-based config with validated Pydantic models

---

## Working with This Codebase

### Common Tasks

#### Adding a New AI Provider

1. Create `providers/new_provider.py` inheriting from `BaseProvider`
2. Implement `generate_image()`, `validate_credentials()`, `get_models()`
3. Add provider to `PROVIDERS` dict in `core/config.py`
4. Update GUI provider dropdown in `gui/main_window.py`
5. Add authentication UI in `gui/settings_dialog.py`
6. Update documentation in README.md

#### Modifying Video Generation Pipeline

The video system is complex - start here:
1. **Scene Management**: `video/project.py` - `VideoProject` class
2. **Rendering**: `video/renderer.py` - FFmpeg command construction
3. **LLM Integration**: `video/llm_integration.py` - Multi-provider prompt enhancement
4. **UI State**: `gui/video_tab.py` - 1500+ lines, needs careful refactoring

**Critical**: Always test with actual MIDI files and various lyric formats (timestamped, sectioned, plain text)

#### Improving UI/UX

PySide6/Qt patterns used throughout:
- Signal/slot connections for all async operations
- `QSettings` for persistent UI state
- Custom widgets in `gui/widgets/`
- Dark theme support via `QStyleSheet`

**UI Philosophy**: Clean, professional, minimal chrome. Every control should have a clear purpose. Use tooltips generously.

---

## Dependencies & Environment

### Core Dependencies
- **google-genai**: Gemini API client (native, not vertex)
- **google-cloud-aiplatform**: For enterprise Google Cloud auth
- **openai**: DALL-E API client  
- **PySide6**: Qt6 bindings for GUI
- **pillow**: Image processing
- **litellm**: Unified LLM interface for video prompts

### Optional Dependencies (Local SD)
- **torch, diffusers, transformers**: Hugging Face ML stack
- **accelerate**: GPU optimization
- CUDA support via torch index-url for NVIDIA GPUs

### Development Tools
- **PyCharm**: Primary IDE (JetBrains, creator is PyCharm power user)
- **Claude Code**: Used extensively for development
- **pytest**: Testing framework (needs more tests!)

---

## Style Preferences

### Code Style
- **PEP 8 compliant** with 100-character line length (not 79)
- **Descriptive variable names**: `image_generation_worker` not `igw`
- **Avoid magic numbers**: Use named constants
- **Comments**: Explain "why", not "what" (code should be self-documenting)

### Git Commit Messages
- Use present tense: "Add feature" not "Added feature"
- First line summary <50 chars, detailed description below if needed
- Reference issue numbers when applicable

### Documentation
- README.md is comprehensive - keep it updated
- Inline code comments for complex algorithms
- Docstrings for all public APIs
- Changelog.md for version history (exists, use it!)

---

## Known Issues & Gotchas

### Platform-Specific Issues
- **Windows**: Google Cloud CLI path issues with PowerShell execution policy
- **macOS**: Requires Xcode Command Line Tools for some dependencies  
- **Linux**: PySide6 may need system Qt packages (`python3-pyside6`)

### API Provider Quirks
- **Gemini**: Only generates 1:1 aspect ratio currently (limitation, not bug)
- **DALL-E**: Strict content policy, failures are cryptic
- **Stability AI**: Credit-based pricing can be confusing
- **Local SD**: GPU memory management requires attention

### Video System Caveats
- **MIDI Processing**: `pretty-midi` library can be fragile with non-standard MIDI files
- **LLM Response Parsing**: Different providers return prompts in different formats (needs robust parsing)
- **FFmpeg Dependencies**: Must be in system PATH, not bundled

---

## Testing & Quality Assurance

### Before Committing Changes
1. Test with at least 2 different providers (e.g., Gemini + OpenAI)
2. Run on your primary OS + check cross-platform implications
3. Test with and without API keys set (auth failure paths)
4. Check console for any warnings or exceptions
5. Verify metadata sidecars are generated correctly

### Manual Test Checklist
- [ ] Image generation with various aspect ratios
- [ ] Provider switching mid-session
- [ ] Settings persistence across app restarts
- [ ] History table population and click-to-reload
- [ ] Video project save/load cycle
- [ ] MIDI import with lyrics extraction
- [ ] Template system with placeholder substitution

---

## Security Considerations

### API Key Management
- **NEVER commit API keys** to version control
- Use `secure_keys.py` utility on Windows for encrypted storage
- Config migration scripts handle legacy plaintext keys
- Support for environment variables in CI/CD

### Content Safety
- Respect provider content policies
- Handle "safety filter triggered" responses gracefully
- No storage of generated images by providers (only local)

---

## Future Roadmap Alignment

When suggesting improvements, consider these planned features:
- **Google Veo Integration**: True AI video generation (not just slideshow)
- **Image Editing**: Inpainting/outpainting for Local SD
- **Web Interface**: Flask/FastAPI backend + React frontend
- **Mobile Companion**: Remote trigger/monitoring app
- **Plugin System**: Community extensions for custom providers

Don't reinvent what's already planned - build foundations for these features instead.

---

## Communication Style

When working with me on this project:
- **Be Direct**: Tell me if something is a bad idea - I value honest feedback
- **Think Big Picture**: How does this change affect maintainability, extensibility?
- **Show Trade-offs**: "Option A is faster but Option B is more maintainable because..."
- **Celebrate Wins**: This project represents months of work - acknowledge good design when you see it!
- **Have Fun**: Software should be enjoyable to build. Creative solutions are encouraged! 🎨

---

## Quick Reference Commands

```bash
# Run GUI
python main.py

# CLI image generation
python main.py -p "Your prompt" -o output.png

# Test provider authentication
python main.py --provider google -t
python main.py --provider openai -t

# Video generation with MIDI sync
python main.py video --in lyrics.txt --midi song.mid --audio song.mp3 --out video.mp4

# Run with different provider
python main.py --provider local_sd -p "Cyberpunk city" -o cyber.png

# Migrate old config format
python migrate_config.py --dry-run
python migrate_config.py

# Secure API keys (Windows)
python secure_keys.py
```

---

## Getting Help

- **README.md**: Comprehensive usage documentation
- **CHANGELOG.md**: Version history and breaking changes  
- **Plans/ directory**: Design documents for new features
- **GitHub Issues**: Bug tracking and feature requests
- **Creator Contact**: support@lelandgreen.com

---

## Final Notes for Claude

This is a **mature, production-quality** project with real users. Code changes should maintain:
- ✅ Backward compatibility with existing configurations
- ✅ Cross-platform behavior parity
- ✅ Comprehensive error handling
- ✅ Professional UI/UX standards
- ✅ Clear documentation updates

When improving code:
1. **Understand first**: Read the surrounding code carefully
2. **Minimal changes**: Surgical improvements, not rewrites
3. **Test thoroughly**: Multiple providers, multiple platforms
4. **Document why**: Update comments and docstrings
5. **Respect patterns**: Follow established architectural patterns

**Remember**: The goal is to make the codebase more maintainable, performant, and delightful to use. Every line of code is an opportunity to make developers' (and artists'!) lives better. Let's build something amazing together! 🚀✨

---

