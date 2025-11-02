#!/bin/bash
# Quick test to see what models ImageAI sees

echo "=== QUICK OLLAMA TEST ==="
echo ""
echo "1. What Ollama has installed:"
ollama list
echo ""
echo "2. What Python sees:"
python3 -c "
import sys
sys.path.insert(0, '.')
from core.llm_models import fetch_ollama_models, update_ollama_models, get_provider_models

print('Before update:', get_provider_models('ollama'))
print('')
update_ollama_models()
print('After update:', get_provider_models('ollama'))
"
