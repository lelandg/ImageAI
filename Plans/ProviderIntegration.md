# Provider Integration Plan: ImageGenToolkit → ImageAI

*Created: 2025-09-06*

## Overview
This plan outlines the integration of missing providers from ImageGenToolkit into ImageAI while preserving the current working implementation of ImageAI's existing providers (Google Gemini and OpenAI DALL·E).

## Current State

### ImageAI (Current Project)
- **Architecture**: Single-file application (`main.py`)
- **UI**: PySide6/Qt GUI with CLI support
- **Existing Providers**:
  - ✅ Google Gemini (gemini-2.5-flash-image-preview)
  - ✅ OpenAI DALL·E (dall-e-3, dall-e-2)
- **Features**:
  - GUI with Generate, Settings, Templates, Help tabs
  - Per-provider API key management
  - Template system with placeholders
  - History tracking with metadata sidecars
  - Cross-platform config storage

### ImageGenToolkit (Source Project)
- **Architecture**: Modular CLI with provider system
- **UI**: CLI-only with argparse
- **Available Providers**:
  - ✅ OpenAI (overlaps with ImageAI)
  - ✅ Google (overlaps with ImageAI)
  - 🆕 **Stability AI** (Stable Diffusion via API)
  - 🆕 **Local Stable Diffusion** (Hugging Face Diffusers)
  - 🔜 Replicate (mentioned but not implemented)
  - 🔜 Hugging Face (mentioned but not implemented)

## Providers to Add

### 1. Stability AI Provider
**Source**: `providers/stability_provider.py`
**Features**:
- Stable Diffusion XL via Stability AI API
- Generate, edit, inpaint capabilities
- Uses `stability-sdk` library

**Integration Tasks**:
- [ ] Add stability-sdk to requirements.txt
- [ ] Integrate StabilityProvider class into main.py
- [ ] Add Stability AI to provider selection in GUI
- [ ] Add API key management for Stability AI
- [ ] Map Stability models (e.g., stable-diffusion-xl-1024-v1-0)
- [ ] Add Stability-specific templates

### 2. Local Stable Diffusion Provider
**Source**: `providers/local_sd_provider.py`
**Features**:
- Local model execution using Hugging Face Diffusers
- No API key required
- Supports SD 1.5, SDXL, custom models
- Device management (CPU/GPU/MPS)
- Model downloading and caching

**Integration Tasks**:
- [ ] Add diffusers, torch, transformers to requirements.txt
- [ ] Integrate LocalSDProvider class into main.py
- [ ] Add "Local SD" to provider selection
- [ ] Create GUI for model selection/download
- [ ] Add model installation UI:
  - [ ] Model search/browse from Hugging Face
  - [ ] Download progress indicator
  - [ ] Model management (list/delete cached models)
  - [ ] Device selection (CPU/GPU/MPS)
- [ ] Add memory management settings
- [ ] Handle torch installation instructions (CPU vs CUDA)

### 3. Future Providers (Lower Priority)
**Replicate**: Cloud-based model hosting
**Hugging Face Inference**: API-based inference

## GUI Enhancements for Local Models

### New "Models" Tab
Create a new tab in the GUI for local model management:

```
Models Tab:
├── Provider Selection (Local SD, Future: Local FLUX, etc.)
├── Installed Models List
│   ├── Model Name
│   ├── Size
│   ├── Location
│   └── Delete Button
├── Install New Model
│   ├── Model ID Input (e.g., "stabilityai/stable-diffusion-2-1")
│   ├── Browse Hugging Face Button
│   ├── Download Progress Bar
│   └── Install Button
└── Device Settings
    ├── Device Selection (Auto/CPU/CUDA/MPS)
    ├── Memory Limit
    └── Precision (fp16/fp32)
```

### Settings Tab Updates
- Add provider-specific sections
- Stability AI API key field
- Local model cache directory setting
- Default device preference

## Implementation Phases

### Phase 1: Stability AI Integration (Week 1)
1. [ ] Add Stability SDK dependency
2. [ ] Implement Stability provider in main.py
3. [ ] Add to provider selection
4. [ ] Test basic generation
5. [ ] Add API key management

### Phase 2: Local SD Basic Integration (Week 2)
1. [ ] Add ML dependencies (torch, diffusers)
2. [ ] Implement basic local SD provider
3. [ ] Add to provider selection
4. [ ] Test with one default model
5. [ ] Handle device detection

### Phase 3: Model Management GUI (Week 3)
1. [ ] Create Models tab
2. [ ] Implement model listing
3. [ ] Add download functionality
4. [ ] Create progress indicators
5. [ ] Add model deletion

### Phase 4: Advanced Features (Week 4)
1. [ ] Add edit/inpaint for new providers
2. [ ] Implement memory optimization
3. [ ] Add batch generation
4. [ ] Create provider-specific templates
5. [ ] Add upscaling support

## Technical Considerations

### Dependencies
**New Requirements**:
```txt
# Stability AI
stability-sdk>=0.1.0

# Local Stable Diffusion
torch>=2.0.0  # Note: User may need CUDA version
diffusers>=0.24.0
transformers>=4.35.0
accelerate>=0.24.0
safetensors>=0.4.0
```

### Provider Interface
Maintain consistency with existing provider pattern:
```python
def generate_image_[provider](prompt, model, api_key, **kwargs):
    # Provider-specific implementation
    return image_bytes, metadata
```

### Configuration Schema
Extend existing config.json:
```json
{
  "providers": {
    "google": {"api_key": "..."},
    "openai": {"api_key": "..."},
    "stability": {"api_key": "..."},
    "local_sd": {
      "model_cache": "~/.cache/huggingface",
      "device": "auto",
      "memory_limit": null
    }
  }
}
```

## Testing Checklist

### Stability AI
- [ ] Generate image with text prompt
- [ ] Test different models
- [ ] Verify API key handling
- [ ] Test error cases (invalid key, rate limits)

### Local SD
- [ ] Download and cache model
- [ ] Generate on CPU
- [ ] Generate on GPU (if available)
- [ ] Test memory limits
- [ ] Model switching
- [ ] Cache management

### GUI Integration
- [ ] Provider switching works
- [ ] Settings persist
- [ ] Templates work with all providers
- [ ] History tracks all providers
- [ ] Error messages are clear

## Migration Notes

### Preserving Existing Functionality
- **DO NOT** modify existing Google/OpenAI implementations
- Keep all current UI elements functional
- Maintain backward compatibility with config files
- Preserve existing template system

### Code Organization
Since ImageAI uses a single-file architecture:
1. Add new provider functions alongside existing ones
2. Extend provider selection logic
3. Keep provider-specific code in dedicated functions
4. Use lazy imports for heavy ML libraries

## Success Criteria
- [ ] All existing features continue working
- [ ] Stability AI provider generates images
- [ ] Local SD provider works without API keys
- [ ] GUI allows model installation/management
- [ ] Documentation updated with new providers
- [ ] Cross-platform compatibility maintained

## Notes
- ImageGenToolkit's modular architecture needs adaptation for ImageAI's single-file approach
- Consider extracting provider logic to separate file if main.py becomes too large (>3000 lines)
- Local model support significantly increases dependency size - consider optional dependencies
- GPU support requires platform-specific PyTorch installation instructions