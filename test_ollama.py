#!/usr/bin/env python3
"""
Test script to verify Ollama connectivity and model detection.
Run this on the same machine where Ollama is running (Nick's Linux system).
"""

import sys
import json
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_ollama_connection(endpoint="http://localhost:11434"):
    """Test basic Ollama connectivity."""
    print("=" * 60)
    print("OLLAMA CONNECTIVITY TEST")
    print("=" * 60)
    print(f"Testing connection to: {endpoint}")

    try:
        response = requests.get(f"{endpoint}/api/tags", timeout=5)
        response.raise_for_status()
        print("✅ Connected to Ollama successfully!")
        return response.json()
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to Ollama at {endpoint}")
        print("   Make sure Ollama is running: sudo systemctl status ollama")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def list_models(data):
    """List all installed models with details."""
    if not data or "models" not in data:
        print("\n❌ No models found or invalid response")
        return []

    models = data["models"]
    print(f"\n{'=' * 60}")
    print(f"INSTALLED MODELS: {len(models)} total")
    print("=" * 60)

    model_list = []
    for idx, model_info in enumerate(models, 1):
        name = model_info.get("name", "Unknown")
        size = model_info.get("size", 0)
        size_gb = size / (1024**3)  # Convert to GB

        details = model_info.get("details", {})
        param_size = details.get("parameter_size", "Unknown")
        family = details.get("family", "Unknown")
        format_type = details.get("format", "Unknown")

        print(f"\n{idx}. {name}")
        print(f"   Size: {size_gb:.2f} GB")
        print(f"   Parameters: {param_size}")
        print(f"   Family: {family}")
        print(f"   Format: {format_type}")

        model_list.append(name)

    return model_list

def test_provider_import():
    """Test if OllamaProvider can be imported."""
    print(f"\n{'=' * 60}")
    print("PROVIDER IMPORT TEST")
    print("=" * 60)

    try:
        from providers.ollama import OllamaProvider
        print("✅ OllamaProvider imported successfully!")

        # Test provider initialization
        provider = OllamaProvider({"endpoint": "http://localhost:11434"})
        print(f"✅ Provider initialized")

        # Test model detection
        models = provider.get_models()
        print(f"✅ Detected {len(models)} models:")
        for model_id, display_name in models.items():
            print(f"   - {display_name}")

        # Test default model
        default = provider.get_default_model()
        print(f"✅ Default model: {default}")

        # Test validation
        is_valid, msg = provider.validate_auth()
        print(f"✅ Validation: {msg}")

        return True
    except Exception as e:
        print(f"❌ Error testing provider: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_llm_models():
    """Test LLM models integration."""
    print(f"\n{'=' * 60}")
    print("LLM MODELS INTEGRATION TEST")
    print("=" * 60)

    try:
        from core.llm_models import fetch_ollama_models, update_ollama_models, get_provider_models

        # Test fetching models
        models = fetch_ollama_models()
        print(f"✅ fetch_ollama_models() returned {len(models)} models:")
        for model in models:
            print(f"   - {model}")

        # Test updating models
        updated = update_ollama_models()
        if updated:
            print("✅ update_ollama_models() updated the model list")
        else:
            print("⚠️  update_ollama_models() did not update (no models detected)")

        # Test getting provider models
        provider_models = get_provider_models('ollama')
        print(f"✅ get_provider_models('ollama') returned {len(provider_models)} models:")
        for model in provider_models:
            print(f"   - {model}")

        return True
    except Exception as e:
        print(f"❌ Error testing LLM models: {e}")
        import traceback
        traceback.print_exc()
        return False

def search_for_dolphin(model_list):
    """Search for dolphin models in the list."""
    print(f"\n{'=' * 60}")
    print("SEARCHING FOR DOLPHIN MODELS")
    print("=" * 60)

    dolphin_models = [m for m in model_list if 'dolphin' in m.lower()]

    if dolphin_models:
        print(f"✅ Found {len(dolphin_models)} Dolphin model(s):")
        for model in dolphin_models:
            print(f"   - {model}")
    else:
        print("❌ No Dolphin models found")
        print("\nTo install Dolphin 3:8b, run:")
        print("   ollama pull dolphin-mixtral:8x7b")
        print("or")
        print("   ollama pull dolphin-llama3:8b")

    return dolphin_models

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("IMAGEAI OLLAMA INTEGRATION TEST")
    print("=" * 60)
    print("This script will test Ollama connectivity and model detection.")
    print()

    # Test 1: Connection
    data = test_ollama_connection()
    if not data:
        print("\n❌ Cannot proceed - Ollama is not accessible")
        return 1

    # Test 2: List models
    model_list = list_models(data)

    # Test 3: Search for Dolphin
    dolphin_models = search_for_dolphin(model_list)

    # Test 4: Provider import
    provider_ok = test_provider_import()

    # Test 5: LLM models integration
    llm_ok = test_llm_models()

    # Summary
    print(f"\n{'=' * 60}")
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Ollama Connection: ✅")
    print(f"Models Found: {len(model_list)}")
    print(f"Dolphin Models: {len(dolphin_models) if dolphin_models else 0}")
    print(f"Provider Import: {'✅' if provider_ok else '❌'}")
    print(f"LLM Integration: {'✅' if llm_ok else '❌'}")

    if not dolphin_models:
        print("\n⚠️  TIP: Install Dolphin with 'ollama pull dolphin-mixtral:8x7b'")

    print("\n" + "=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
