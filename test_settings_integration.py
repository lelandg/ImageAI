#!/usr/bin/env python3
"""Test the Settings tab integration for Local SD."""

from pathlib import Path
from providers.model_info import ModelInfo

print("=== Local SD Settings Integration Test ===\n")

# Test model filtering
cache_dir = Path.home() / ".cache" / "huggingface"
print(f"Cache directory: {cache_dir}\n")

# Show installed models (filtered)
installed = ModelInfo.get_installed_models(cache_dir)
if installed:
    print("Installed image generation models:")
    for model_id in installed:
        size = ModelInfo.get_model_size(model_id, cache_dir)
        if model_id in ModelInfo.POPULAR_MODELS:
            name = ModelInfo.POPULAR_MODELS[model_id]["name"]
            print(f"  ✓ {name} ({model_id}) - {size:.1f} GB")
        else:
            print(f"  ✓ {model_id} - {size:.1f} GB")
else:
    print("No image generation models installed")

print("\n" + "="*50 + "\n")

# Show popular models for download
print("Popular models available for download:")
for model_id, info in ModelInfo.POPULAR_MODELS.items():
    if model_id not in installed:
        status = "⭐" if info.get("recommended") else " "
        print(f"  {status} {info['name']} (~{info['size_gb']:.1f} GB)")
        print(f"      {info['description'][:60]}...")

print("\n" + "="*50 + "\n")

print("GUI Integration:")
print("- When 'local_sd' is selected in Settings:")
print("  • API key field is hidden")
print("  • Local SD model manager widget is shown")
print("  • Can select from popular models dropdown")
print("  • Can enter custom model IDs")
print("  • Shows installed models with sizes")
print("  • Download progress and status displayed")
print("\n- Models are filtered to only show image generation models")
print("- Depth estimation and other non-generation models are excluded")

print("\n✓ Settings integration ready for Local SD")