# Comprehensive Settings Plan for ImageAI
*Created: 2025-09-07*

## Executive Summary

This document outlines a comprehensive plan to implement advanced settings for all image generation providers in ImageAI, making it a full-featured application with user-friendly controls for aspect ratio, resolution, quality, style, and provider-specific parameters.

## Core Design Principles

1. **Progressive Disclosure**: Show basic settings by default, with an "Advanced" section for power users
2. **Provider-Aware UI**: Settings dynamically adapt based on selected provider
3. **Presets & Templates**: Common configurations saved as presets (e.g., "Social Media Square", "HD Wallpaper", "Print Quality")
4. **Visual Feedback**: Preview aspect ratios, show resolution dimensions, display estimated costs
5. **Smart Defaults**: Each provider has optimized defaults that work well out-of-the-box
6. **Validation & Guidance**: Prevent invalid combinations, show warnings for suboptimal settings

## Universal Settings (All Providers)

### 1. Aspect Ratio
**Implementation**: Dropdown with visual preview icons
```python
ASPECT_RATIOS = {
    "Square (1:1)": {"ratio": "1:1", "icon": "⬜", "use_cases": "Social media posts, avatars"},
    "Portrait (3:4)": {"ratio": "3:4", "icon": "📱", "use_cases": "Phone wallpapers, portraits"},
    "Landscape (4:3)": {"ratio": "4:3", "icon": "🖼️", "use_cases": "Classic photos, presentations"},
    "Wide (16:9)": {"ratio": "16:9", "icon": "🖥️", "use_cases": "Desktop wallpapers, videos"},
    "Ultrawide (21:9)": {"ratio": "21:9", "icon": "🎬", "use_cases": "Cinematic, dual monitors"},
    "Portrait Full (9:16)": {"ratio": "9:16", "icon": "📲", "use_cases": "Stories, TikTok, Reels"},
    "Custom": {"ratio": "custom", "icon": "⚙️", "use_cases": "User-defined dimensions"}
}
```

### 2. Resolution/Size
**Implementation**: Smart selector with presets and custom input
```python
RESOLUTION_PRESETS = {
    "Standard": {"dimensions": "1024x1024", "megapixels": 1.0, "label": "1K - Fast & Balanced"},
    "High": {"dimensions": "2048x2048", "megapixels": 4.0, "label": "2K - High Quality"},
    "Ultra": {"dimensions": "4096x4096", "megapixels": 16.0, "label": "4K - Maximum Detail"},
    "Print Small": {"dimensions": "2400x3000", "megapixels": 7.2, "label": "8x10 inch @ 300 DPI"},
    "Print Large": {"dimensions": "4200x5400", "megapixels": 22.7, "label": "14x18 inch @ 300 DPI"}
}
```

### 3. Batch Generation
**Implementation**: Slider with cost estimate
```python
batch_settings = {
    "num_images": IntSlider(min=1, max=4, default=1),
    "show_cost": True,  # Display: "4 images × $0.03 = $0.12"
    "parallel": CheckBox("Generate in parallel", default=False)
}
```

## Provider-Specific Settings

### Google Gemini (Imagen 3)

```python
GEMINI_SETTINGS = {
    # Basic
    "model": {
        "type": "dropdown",
        "options": ["imagen-3.0-generate-002", "imagen-3.0-fast-generate-001"],
        "default": "imagen-3.0-generate-002",
        "labels": {"002": "Quality", "001": "Fast"}
    },
    "aspect_ratio": {
        "type": "dropdown",
        "options": ["1:1", "3:4", "4:3", "9:16", "16:9"],
        "default": "1:1"
    },
    "resolution": {
        "type": "dropdown", 
        "options": ["1K", "2K"],
        "default": "1K",
        "note": "2K only for Standard/Ultra models"
    },
    
    # Advanced
    "prompt_rewriting": {
        "type": "toggle",
        "default": True,
        "tooltip": "AI enhancement for better image quality"
    },
    "safety_filter": {
        "type": "dropdown",
        "options": ["block_most", "block_some", "block_few", "block_fewest"],
        "default": "block_some"
    },
    "person_generation": {
        "type": "toggle",
        "default": True,
        "tooltip": "Allow generation of people in images"
    },
    "seed": {
        "type": "number",
        "min": 0,
        "max": 2147483647,
        "default": None,
        "tooltip": "For reproducible results"
    }
}
```

### OpenAI DALL-E 3

```python
OPENAI_SETTINGS = {
    # Basic
    "size": {
        "type": "dropdown",
        "options": ["1024x1024", "1024x1792", "1792x1024"],
        "labels": {
            "1024x1024": "Square",
            "1024x1792": "Portrait", 
            "1792x1024": "Landscape"
        },
        "default": "1024x1024"
    },
    "quality": {
        "type": "dropdown",
        "options": ["standard", "hd"],
        "default": "standard",
        "pricing": {"standard": "$0.04", "hd": "$0.08"}
    },
    "style": {
        "type": "dropdown",
        "options": ["vivid", "natural"],
        "default": "vivid",
        "descriptions": {
            "vivid": "Hyper-real and cinematic",
            "natural": "More realistic and subtle"
        }
    },
    
    # Advanced
    "response_format": {
        "type": "dropdown",
        "options": ["url", "b64_json"],
        "default": "url"
    }
}
```

### Stability AI (SDXL/SD3)

```python
STABILITY_SETTINGS = {
    # Basic
    "model": {
        "type": "dropdown",
        "options": ["sdxl-1.0", "sd3-medium", "sd3-large", "sd3.5-turbo"],
        "default": "sd3-medium"
    },
    "aspect_ratio": {
        "type": "smart_selector",  # Shows optimal ratios per model
        "sdxl_optimal": ["1024x1024", "1152x896", "896x1152", "1216x832", "832x1216"],
        "sd3_optimal": ["1024x1024", "1344x768", "768x1344", "1536x640"]
    },
    
    # Generation Controls
    "cfg_scale": {
        "type": "slider",
        "min": 1.0,
        "max": 15.0,
        "step": 0.5,
        "default": {"sdxl": 7.0, "sd3": 4.0},
        "tooltip": "Prompt adherence (lower for SD3)"
    },
    "steps": {
        "type": "slider",
        "min": 20,
        "max": 150,
        "default": 50,
        "warning": "< 50 may cause artifacts with DPM++ scheduler"
    },
    
    # Advanced
    "sampler": {
        "type": "dropdown",
        "options": ["DPM++ 2M", "DPM++ SDE", "Euler a", "DDIM", "K_LMS"],
        "default": "DPM++ 2M"
    },
    "seed": {
        "type": "number",
        "default": -1,
        "tooltip": "-1 for random"
    },
    "clip_skip": {
        "type": "slider",
        "min": 1,
        "max": 2,
        "default": 1
    }
}
```

### Adobe Firefly

```python
FIREFLY_SETTINGS = {
    # Basic
    "content_class": {
        "type": "dropdown",
        "options": ["photo", "art"],
        "default": "photo",
        "auto_detect": True
    },
    "aspect_ratio": {
        "type": "dropdown",
        "options": ["1:1", "4:3", "3:4", "16:9", "9:16"],
        "social_presets": {
            "Instagram Post": "1:1",
            "Instagram Story": "9:16",
            "Twitter": "16:9",
            "Facebook": "1.91:1"
        }
    },
    
    # Style Controls
    "style_strength": {
        "type": "slider",
        "min": 1,
        "max": 100,
        "default": 50
    },
    "structure_strength": {
        "type": "slider",
        "min": 1,
        "max": 100,
        "default": 50,
        "tooltip": "How closely to match reference structure"
    },
    
    # Advanced
    "negative_prompt": {
        "type": "text",
        "placeholder": "Things to avoid...",
        "default": ""
    },
    "seed": {
        "type": "number",
        "default": None
    }
}
```

### Midjourney (Future - via unofficial APIs)

```python
MIDJOURNEY_SETTINGS = {
    # Basic
    "version": {
        "type": "dropdown",
        "options": ["v6.1", "v6", "v5.2", "niji6"],
        "default": "v6.1"
    },
    "aspect_ratio": {
        "type": "text_input",
        "placeholder": "16:9",
        "validator": "ratio_pattern",
        "common": ["1:1", "4:3", "16:9", "2:3", "3:2"]
    },
    
    # Artistic Controls
    "stylize": {
        "type": "slider",
        "min": 0,
        "max": 1000,
        "default": 100,
        "labels": {0: "Accurate", 100: "Balanced", 1000: "Artistic"}
    },
    "chaos": {
        "type": "slider",
        "min": 0,
        "max": 100,
        "default": 0,
        "tooltip": "Variation in results"
    },
    "weird": {
        "type": "slider",
        "min": 0,
        "max": 3000,
        "default": 0,
        "tooltip": "Unconventional aesthetics"
    },
    
    # Quality
    "quality": {
        "type": "dropdown",
        "options": [0.25, 0.5, 1],
        "labels": {0.25: "Draft", 0.5: "Good", 1: "Best"},
        "default": 1
    },
    
    # Special
    "tile": {
        "type": "toggle",
        "default": False,
        "tooltip": "Create seamless patterns"
    }
}
```

## UI Implementation Strategy

### Settings Panel Design

```
┌─────────────────────────────────────────┐
│ Provider: [Dropdown] │ Preset: [Dropdown]│
├─────────────────────────────────────────┤
│ ▼ Basic Settings                        │
│   Aspect Ratio:  [Visual Selector]      │
│   Resolution:    [Smart Dropdown]       │
│   Quality:       [Radio Buttons]        │
│   # Images:      [1] [2] [3] [4]       │
│                                         │
│ ▶ Advanced Settings                     │
│   (Collapsed by default)                │
│                                         │
│ Cost Estimate: $0.12 (4 images)        │
│ [Generate] [Save Preset]                │
└─────────────────────────────────────────┘
```

### Visual Aspect Ratio Selector

```python
class AspectRatioSelector(QWidget):
    """Visual grid of aspect ratio options with preview rectangles"""
    
    def __init__(self):
        self.options = [
            {"ratio": "1:1", "preview": "□", "label": "Square"},
            {"ratio": "3:4", "preview": "▭", "label": "Portrait"},
            {"ratio": "4:3", "preview": "▬", "label": "Landscape"},
            {"ratio": "16:9", "preview": "▭▭", "label": "Wide"},
            {"ratio": "9:16", "preview": "▯", "label": "Tall"},
        ]
        
    def create_preview_widget(self, ratio):
        """Create visual preview of aspect ratio"""
        width, height = map(int, ratio.split(':'))
        # Scale to fit in 60x60 box
        scale = 60 / max(width, height)
        w, h = int(width * scale), int(height * scale)
        
        widget = QLabel()
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor("#4CAF50"))
        widget.setPixmap(pixmap)
        return widget
```

### Dynamic Settings Loading

```python
class ProviderSettings:
    """Dynamically load and display provider-specific settings"""
    
    def __init__(self, provider: str):
        self.provider = provider
        self.settings = self.load_provider_settings(provider)
        
    def load_provider_settings(self, provider: str) -> dict:
        """Load settings configuration for provider"""
        configs = {
            "google": GEMINI_SETTINGS,
            "openai": OPENAI_SETTINGS,
            "stability": STABILITY_SETTINGS,
            "firefly": FIREFLY_SETTINGS,
        }
        return configs.get(provider, {})
        
    def create_widget(self, setting_name: str, config: dict) -> QWidget:
        """Create appropriate widget based on setting type"""
        setting_type = config.get("type")
        
        if setting_type == "dropdown":
            return self.create_dropdown(config)
        elif setting_type == "slider":
            return self.create_slider(config)
        elif setting_type == "toggle":
            return self.create_toggle(config)
        elif setting_type == "text":
            return self.create_text_input(config)
        elif setting_type == "number":
            return self.create_number_input(config)
```

## Preset System

### Built-in Presets

```python
PRESETS = {
    "Quick Draft": {
        "description": "Fast, low-cost generation for ideation",
        "settings": {
            "quality": "standard",
            "resolution": "1024x1024",
            "num_images": 1
        }
    },
    "Social Media Pack": {
        "description": "Multiple formats for social platforms",
        "settings": {
            "num_images": 3,
            "aspect_ratios": ["1:1", "9:16", "16:9"],
            "quality": "standard"
        }
    },
    "Print Quality": {
        "description": "High-resolution for printing",
        "settings": {
            "quality": "hd",
            "resolution": "4096x4096",
            "num_images": 1
        }
    },
    "Artistic Exploration": {
        "description": "High variation for creative exploration",
        "settings": {
            "chaos": 50,  # For Midjourney-style
            "cfg_scale": 5,  # For Stable Diffusion
            "num_images": 4
        }
    }
}
```

### User Preset Management

```python
class PresetManager:
    """Handle saving and loading user presets"""
    
    def save_preset(self, name: str, settings: dict):
        """Save current settings as preset"""
        preset_file = self.config_dir / "presets.json"
        presets = self.load_presets()
        presets[name] = {
            "created": datetime.now().isoformat(),
            "provider": self.current_provider,
            "settings": settings
        }
        preset_file.write_text(json.dumps(presets, indent=2))
        
    def apply_preset(self, name: str):
        """Apply saved preset to current settings"""
        presets = self.load_presets()
        if name in presets:
            preset = presets[name]
            self.apply_settings(preset["settings"])
```

## Cost Estimation

```python
class CostCalculator:
    """Calculate and display generation costs"""
    
    PRICING = {
        "google": {"base": 0.03, "2k": 0.06},
        "openai": {"standard": 0.04, "hd": 0.08},
        "stability": {"sdxl": 0.011, "sd3": 0.037},
        "firefly": {"standard": 0.05, "premium": 0.10}
    }
    
    def calculate_cost(self, provider: str, settings: dict) -> float:
        """Calculate cost based on provider and settings"""
        base_price = self.PRICING[provider]
        num_images = settings.get("num_images", 1)
        
        # Apply quality multipliers
        if provider == "openai" and settings.get("quality") == "hd":
            price_per_image = base_price["hd"]
        elif provider == "google" and settings.get("resolution") == "2K":
            price_per_image = base_price["2k"]
        else:
            price_per_image = base_price.get("base", base_price.get("standard"))
            
        return price_per_image * num_images
```

## Validation & Warnings

```python
class SettingsValidator:
    """Validate settings and show warnings"""
    
    def validate(self, provider: str, settings: dict) -> tuple[bool, list[str]]:
        """Return (is_valid, warnings)"""
        warnings = []
        
        # Provider-specific validations
        if provider == "stability":
            if settings.get("steps", 50) < 50:
                warnings.append("Steps < 50 may cause artifacts with DPM++ scheduler")
            
            resolution = settings.get("resolution", "1024x1024")
            if resolution not in STABILITY_OPTIMAL_RESOLUTIONS:
                warnings.append(f"Non-optimal resolution may affect quality")
                
        elif provider == "google":
            if settings.get("resolution") == "2K" and settings.get("model") == "fast":
                warnings.append("2K resolution not available with Fast model")
                return False, warnings
                
        return True, warnings
```

## Implementation Timeline

### Phase 1: Core Settings (Week 1)
- [x] Research provider capabilities
- [ ] Implement universal settings (aspect ratio, resolution, batch)
- [ ] Create dynamic settings framework
- [ ] Add provider detection and setting adaptation

### Phase 2: UI Enhancement (Week 2)
- [ ] Build visual aspect ratio selector
- [ ] Create resolution preset system
- [ ] Implement advanced settings collapsible panel
- [ ] Add tooltips and help text

### Phase 3: Provider Integration (Week 3)
- [ ] Update Google provider with all Imagen 3 settings
- [ ] Update OpenAI provider with style options
- [ ] Add Stability AI provider with full controls
- [ ] Implement Adobe Firefly provider

### Phase 4: Polish & UX (Week 4)
- [ ] Add preset system with built-in presets
- [ ] Implement cost estimation display
- [ ] Add settings validation and warnings
- [ ] Create settings import/export functionality
- [ ] Add keyboard shortcuts for common presets

## Technical Considerations

1. **Settings Storage**: Use JSON schema for settings definition, allowing easy updates
2. **Provider Plugins**: Each provider implements `IProviderSettings` interface
3. **Backwards Compatibility**: Maintain support for existing CLI arguments
4. **Performance**: Lazy load provider-specific settings only when selected
5. **Accessibility**: Ensure all controls are keyboard navigable with proper labels

## Success Metrics

- Users can access 90% of provider capabilities through GUI
- Settings load in < 100ms when switching providers
- Preset application takes < 50ms
- Zero invalid API calls due to setting combinations
- 95% of users successfully generate images without reading documentation

## Conclusion

This comprehensive settings implementation will transform ImageAI into a professional-grade image generation tool that rivals commercial applications while maintaining its open-source, user-friendly nature. The progressive disclosure approach ensures beginners aren't overwhelmed while power users have full control.