# Main.py Refactoring Plan

*Created: 2025-09-06*

## Current State
- **File**: main.py
- **Size**: 2,646 lines (too large for maintainability)
- **Structure**: Monolithic single-file application

## Proposed Module Structure

```
ImageAI/
├── main.py                    # Entry point (~100 lines)
├── core/
│   ├── __init__.py
│   ├── config.py             # Configuration management (~200 lines)
│   ├── constants.py          # App constants and defaults (~50 lines)
│   └── utils.py              # Utility functions (~150 lines)
├── providers/
│   ├── __init__.py
│   ├── base.py               # Base provider interface (~100 lines)
│   ├── google.py             # Google Gemini provider (~300 lines)
│   ├── openai.py             # OpenAI DALL-E provider (~250 lines)
│   ├── stability.py          # Stability AI provider (new) (~250 lines)
│   └── local_sd.py           # Local SD provider (new) (~400 lines)
├── gui/
│   ├── __init__.py
│   ├── main_window.py        # Main window class (~400 lines)
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── generate.py       # Generate tab (~250 lines)
│   │   ├── edit.py           # Edit tab (new) (~200 lines)
│   │   ├── settings.py       # Settings tab (~200 lines)
│   │   ├── templates.py      # Templates tab (~150 lines)
│   │   ├── history.py        # History tab (~150 lines)
│   │   ├── models.py         # Models tab (new) (~250 lines)
│   │   └── help.py           # Help tab (~100 lines)
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── examples.py       # Examples dialog (~150 lines)
│   │   └── about.py          # About dialog (~50 lines)
│   ├── workers/
│   │   ├── __init__.py
│   │   └── generation.py     # Generation worker thread (~150 lines)
│   └── styles.py             # UI styles and themes (~100 lines)
├── cli/
│   ├── __init__.py
│   ├── parser.py             # Argument parser (~150 lines)
│   └── runner.py             # CLI command runner (~200 lines)
└── templates/
    ├── __init__.py
    └── defaults.py           # Default templates (~100 lines)
```

## Refactoring Steps

### Phase 1: Core Infrastructure
1. Create directory structure
2. Extract configuration management
3. Move constants and utils
4. Set up base provider interface

### Phase 2: Provider Modules
1. Extract Google provider logic
2. Extract OpenAI provider logic  
3. Create provider registry
4. Add provider factory pattern

### Phase 3: GUI Components
1. Extract main window class
2. Split tabs into separate modules
3. Move dialogs to dedicated files
4. Extract worker threads

### Phase 4: CLI Separation
1. Move argument parser
2. Extract CLI runner logic
3. Create CLI-GUI bridge

### Phase 5: Integration
1. Update main.py as entry point
2. Fix all imports
3. Test all functionality
4. Update documentation

## Implementation Details

### main.py (New Entry Point)
```python
#!/usr/bin/env python3
"""ImageAI - AI Image Generation Tool"""

import sys
from pathlib import Path

def main():
    """Main entry point."""
    # Parse initial arguments to determine mode
    if "--gui" in sys.argv or len(sys.argv) == 1:
        from gui import run_gui
        run_gui()
    else:
        from cli import run_cli
        run_cli()

if __name__ == "__main__":
    main()
```

### core/config.py
```python
"""Configuration management for ImageAI."""

from pathlib import Path
import json
import platform

class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self):
        self.config_path = self._get_config_path()
        self.config = self._load_config()
    
    def _get_config_path(self) -> Path:
        """Get platform-specific config path."""
        # Implementation here
    
    def _load_config(self) -> dict:
        """Load configuration from disk."""
        # Implementation here
    
    def save(self):
        """Save configuration to disk."""
        # Implementation here
```

### providers/base.py
```python
"""Base provider interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ImageProvider(ABC):
    """Abstract base class for image providers."""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> bytes:
        """Generate image from prompt."""
        pass
    
    @abstractmethod
    def validate_api_key(self, api_key: str) -> bool:
        """Validate API key."""
        pass
    
    @abstractmethod
    def get_models(self) -> Dict[str, str]:
        """Get available models."""
        pass
```

### providers/__init__.py
```python
"""Provider registry and factory."""

from typing import Dict, Type
from .base import ImageProvider
from .google import GoogleProvider
from .openai import OpenAIProvider

PROVIDERS: Dict[str, Type[ImageProvider]] = {
    "google": GoogleProvider,
    "openai": OpenAIProvider,
}

def get_provider(name: str, config: dict) -> ImageProvider:
    """Get provider instance by name."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}")
    return PROVIDERS[name](config)
```

## Benefits of Refactoring

1. **Maintainability**: Easier to find and modify specific functionality
2. **Testability**: Can unit test individual modules
3. **Scalability**: Easy to add new providers and features
4. **Readability**: Logical separation of concerns
5. **Collaboration**: Multiple developers can work on different modules
6. **Performance**: Can lazy-load heavy modules (torch, transformers)

## Migration Strategy

### Step 1: Create New Structure (No Breaking Changes)
- Create all new directories and files
- Copy code to new modules
- Keep main.py working during transition

### Step 2: Test New Modules
- Import and test each module individually
- Verify no functionality is lost
- Check for circular imports

### Step 3: Update Entry Point
- Modify main.py to use new modules
- Remove old monolithic code
- Update imports throughout

### Step 4: Cleanup
- Remove duplicate code
- Optimize imports
- Add module docstrings

## Testing Checklist

- [ ] CLI mode works (generate, test, help)
- [ ] GUI launches correctly
- [ ] All tabs functional
- [ ] Google provider generates images
- [ ] OpenAI provider generates images
- [ ] API key management works
- [ ] Templates load and work
- [ ] History tracking functions
- [ ] Settings persist
- [ ] Cross-platform paths work

## File Size Targets

- No single file over 500 lines
- Most files between 100-300 lines
- Clear separation of concerns
- Logical grouping of related functionality

## Notes

- Keep backward compatibility with config files
- Preserve all existing functionality
- Use relative imports within packages
- Add __init__.py files for proper packaging
- Consider using lazy imports for heavy dependencies
- Document module interfaces clearly