#!/usr/bin/env python3
"""
Quick verification that Ollama appears in UI dropdowns.
Run this to confirm Ollama integration is working.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def verify_ollama_integration():
    """Verify Ollama appears in all the right places."""
    print("\n" + "="*60)
    print("OLLAMA UI INTEGRATION VERIFICATION")
    print("="*60)

    # Test 1: Check if Ollama models can be fetched
    print("\n1. Testing Ollama model detection...")
    try:
        from core.llm_models import fetch_ollama_models, update_ollama_models

        models = fetch_ollama_models()
        if models:
            print(f"   ✅ Found {len(models)} Ollama models:")
            for model in models:
                print(f"      - {model}")
        else:
            print("   ⚠️  No Ollama models detected")
            print("      Make sure Ollama is running: sudo systemctl status ollama")
            print("      Install models with: ollama pull <model-name>")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Test 2: Check if Ollama appears in LLM provider list
    print("\n2. Testing LLM provider list...")
    try:
        from core.llm_models import get_all_provider_ids, get_provider_display_name

        provider_ids = get_all_provider_ids()
        if 'ollama' in provider_ids:
            print("   ✅ 'ollama' found in provider IDs")
            display_name = get_provider_display_name('ollama')
            print(f"      Display name: '{display_name}'")
        else:
            print("   ❌ 'ollama' NOT in provider IDs")
            print(f"      Available: {provider_ids}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Test 3: Simulate what the Generate tab dropdown shows
    print("\n3. Testing Generate tab LLM dropdown...")
    try:
        from core.llm_models import get_all_provider_ids, get_provider_display_name

        # This is exactly what MainWindow.get_llm_providers() does
        provider_names = [get_provider_display_name(pid) for pid in get_all_provider_ids()]
        dropdown_items = ["None"] + provider_names

        if "Ollama" in dropdown_items:
            index = dropdown_items.index("Ollama")
            print(f"   ✅ 'Ollama' appears at position {index}")
            print("      Full dropdown list:")
            for i, item in enumerate(dropdown_items):
                marker = " ← HERE!" if item == "Ollama" else ""
                print(f"         {i}. {item}{marker}")
        else:
            print("   ❌ 'Ollama' NOT in dropdown")
            print(f"      Dropdown shows: {dropdown_items}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Test 4: Check if OllamaProvider can be imported
    print("\n4. Testing OllamaProvider class...")
    try:
        from providers.ollama import OllamaProvider
        print("   ✅ OllamaProvider imported successfully")

        # Test initialization
        provider = OllamaProvider({"endpoint": "http://localhost:11434"})
        print("   ✅ Provider initialized")

        # Test model detection
        models = provider.get_models()
        if models:
            print(f"   ✅ Provider detected {len(models)} models")
        else:
            print("   ⚠️  Provider initialized but no models detected")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Summary
    print("\n" + "="*60)
    print("VERIFICATION COMPLETE")
    print("="*60)
    print("\n✅ Ollama integration is working correctly!")
    print("\nWHERE TO FIND OLLAMA IN THE UI:")
    print("  1. Generate Tab → 'LLM Provider:' dropdown → Select 'Ollama'")
    print("  2. Video Tab → 'LLM Provider:' dropdown → Select 'Ollama'")
    print("  3. Layout Tab → LLM provider dropdown → Select 'Ollama'")
    print("\nNOTE: Ollama will NOT appear in 'Image Provider:' dropdown")
    print("      (Ollama models cannot generate images, only text)")

    return True

if __name__ == "__main__":
    success = verify_ollama_integration()
    sys.exit(0 if success else 1)
