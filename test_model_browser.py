#!/usr/bin/env python3
"""Test script for the model browser dialog."""

import sys
from pathlib import Path

# Test if we can import the module
try:
    from gui.model_browser import ModelBrowserDialog, ModelInfo
    print("✓ Model browser module imported successfully")
except ImportError as e:
    print(f"✗ Failed to import model browser: {e}")
    sys.exit(1)

# Test ModelInfo static methods
cache_dir = Path.home() / ".cache" / "huggingface"
print(f"\nCache directory: {cache_dir}")

# Check for installed models
installed = ModelInfo.get_installed_models(cache_dir)
if installed:
    print(f"\nFound {len(installed)} installed models:")
    for model_id in installed[:5]:  # Show first 5
        size = ModelInfo.get_model_size(model_id, cache_dir)
        print(f"  - {model_id} ({size:.1f} GB)")
else:
    print("\nNo models installed yet")

# Check if a specific model is installed
test_model = "runwayml/stable-diffusion-v1-5"
is_installed = ModelInfo.is_model_installed(test_model, cache_dir)
print(f"\n{test_model}: {'Installed' if is_installed else 'Not installed'}")

# Show available models
print("\nAvailable models in browser:")
for model_id, info in list(ModelInfo.POPULAR_MODELS.items())[:3]:
    print(f"  - {info['name']}: {info['description'][:50]}...")
    print(f"    Size: ~{info['size_gb']:.1f} GB, Recommended: {info.get('recommended', False)}")

print("\n✓ Model browser tests completed successfully")