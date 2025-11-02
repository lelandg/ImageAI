#!/usr/bin/env python3
"""Diagnose why Ollama models aren't showing correctly."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("="*60)
print("OLLAMA MODEL DETECTION DIAGNOSTIC")
print("="*60)

# Step 1: Check default models
print("\n1. DEFAULT hardcoded models:")
from core.llm_models import LLM_PROVIDERS
default_models = LLM_PROVIDERS['ollama'].models.copy()
print(f"   Count: {len(default_models)}")
for m in default_models:
    print(f"   - {m}")

# Step 2: Fetch from API
print("\n2. DETECTED models from Ollama API:")
from core.llm_models import fetch_ollama_models
detected = fetch_ollama_models()
print(f"   Count: {len(detected)}")
for m in detected:
    print(f"   - {m}")

# Step 3: Update the provider
print("\n3. UPDATING provider with detected models...")
from core.llm_models import update_ollama_models
result = update_ollama_models()
print(f"   Update result: {result}")

# Step 4: Check what get_provider_models returns
print("\n4. What get_provider_models('ollama') returns:")
from core.llm_models import get_provider_models
current_models = get_provider_models('ollama')
print(f"   Count: {len(current_models)}")
for m in current_models:
    marker = " ← DOLPHIN!" if 'dolphin' in m.lower() else ""
    print(f"   - {m}{marker}")

# Step 5: Check if Dolphin is there
print("\n5. DOLPHIN CHECK:")
dolphin_found = any('dolphin' in m.lower() for m in current_models)
if dolphin_found:
    print("   ✅ DOLPHIN MODELS FOUND!")
    dolphin_models = [m for m in current_models if 'dolphin' in m.lower()]
    for m in dolphin_models:
        print(f"      - {m}")
else:
    print("   ❌ NO DOLPHIN MODELS")
    print("\n   Expected to find:")
    print("      - dolphin-max:latest")
    print("      - dolphin3:8b")
    print("\n   But UI will show:")
    for m in current_models:
        print(f"      - {m}")

print("\n" + "="*60)
if not dolphin_found:
    print("❌ PROBLEM: Ollama models are NOT being detected properly")
    print("   The UI will show the hardcoded default list instead of Nick's models")
else:
    print("✅ SUCCESS: Ollama models detected correctly")
print("="*60)
