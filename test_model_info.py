#!/usr/bin/env python3
"""Test ModelInfo without requiring PySide6."""

import sys
from pathlib import Path

# Mock PySide6 for testing
sys.modules['PySide6'] = type(sys)('PySide6')
sys.modules['PySide6.QtWidgets'] = type(sys)('QtWidgets')
sys.modules['PySide6.QtCore'] = type(sys)('QtCore')
sys.modules['PySide6.QtGui'] = type(sys)('QtGui')

# Now import ModelInfo
from gui.model_browser import ModelInfo

# Test ModelInfo static methods
cache_dir = Path.home() / ".cache" / "huggingface"
print(f"Cache directory: {cache_dir}")

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
for model_id, info in list(ModelInfo.POPULAR_MODELS.items())[:5]:
    print(f"\n  {info['name']}")
    print(f"    ID: {model_id}")
    print(f"    Description: {info['description']}")
    print(f"    Size: ~{info['size_gb']:.1f} GB")
    print(f"    Recommended: {info.get('recommended', False)}")
    print(f"    Tags: {', '.join(info['tags'])}")

print("\n✓ Model info tests completed successfully")