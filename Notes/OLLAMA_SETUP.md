# Ollama Integration Setup and Troubleshooting

## Quick Diagnosis

Run this on your Linux machine (pop-os) where Ollama is running:

```bash
# 1. Check what models you have installed
ollama list

# 2. Run the test script
cd /path/to/ImageAI
python3 test_ollama.py
```

## Common Issue: Dolphin Model Not Found

If you don't see Dolphin in the list, it's not installed yet. Install it with:

```bash
# Option 1: Dolphin Mixtral (recommended - 8x7B parameters)
ollama pull dolphin-mixtral:8x7b

# Option 2: Dolphin Llama3 (8B parameters)
ollama pull dolphin-llama3:8b

# Option 3: Smaller Dolphin Phi (3B parameters)
ollama pull dolphin-phi:2.7b

# Verify installation
ollama list
```

## Running ImageAI with Ollama

### If ImageAI is on the Same Machine as Ollama

Simply launch ImageAI - it will auto-detect Ollama models:

```bash
python3 main.py
```

### If ImageAI is on a Different Machine (e.g., WSL)

You need to expose Ollama's API. Edit your Ollama service:

```bash
# Stop Ollama
sudo systemctl stop ollama

# Edit the service file
sudo nano /etc/systemd/system/ollama.service

# Find the [Service] section and add:
Environment="OLLAMA_HOST=0.0.0.0:11434"

# Save and reload
sudo systemctl daemon-reload
sudo systemctl start ollama

# Verify it's listening
curl http://YOUR_LINUX_IP:11434/api/tags
```

Then configure ImageAI to use that endpoint (we'll need to add a config option for this).

## What Models Work with ImageAI?

### For Text/LLM Tasks (Video Tab, Prompt Enhancement)
- ✅ **dolphin-mixtral:8x7b** - Excellent for text generation
- ✅ **dolphin-llama3:8b** - Good balance of speed/quality
- ✅ **llama3.2:latest** - General purpose
- ✅ **mistral:7b** - Fast and efficient

### For Image Understanding (Vision Models)
- ✅ **llava:latest** - Can analyze images
- ✅ **llava-llama3** - Better reasoning
- ✅ **bakllava** - Alternative vision model

### ❌ Cannot Generate Images
Ollama models do **NOT** generate actual image files. They:
- Generate text descriptions
- Enhance prompts for other image generators
- Analyze/understand existing images (vision models)

For actual image generation, use:
- Google Gemini (already in ImageAI)
- OpenAI DALL-E (already in ImageAI)
- Stability AI (already in ImageAI)
- Local Stable Diffusion (already in ImageAI)

## Troubleshooting

### "No Ollama models detected"

1. **Check Ollama is running:**
   ```bash
   sudo systemctl status ollama
   ```

2. **Test API directly:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. **Check firewall:**
   ```bash
   sudo ufw status
   # If needed: sudo ufw allow 11434/tcp
   ```

### "Dolphin not in list"

Run `ollama list` to see what you actually have installed. If Dolphin isn't there:

```bash
ollama pull dolphin-mixtral:8x7b
```

### Provider not showing in UI

1. Check provider loads correctly:
   ```bash
   python3 -c "from providers import list_providers; print(list_providers())"
   ```

2. Look for errors in ImageAI logs:
   ```bash
   tail -f ~/.config/ImageAI/logs/imageai.log
   ```

## Testing the Integration

The test script (`test_ollama.py`) will:
- ✅ Check Ollama connectivity
- ✅ List all installed models
- ✅ Search for Dolphin models
- ✅ Test provider import
- ✅ Test LLM integration

Run it to diagnose issues:

```bash
cd /path/to/ImageAI
python3 test_ollama.py
```

## Expected Output in ImageAI

Once working, you should see:

1. **Provider dropdown**: "ollama" appears in the list
2. **Model dropdown**: Shows all installed models with sizes
   - Example: "dolphin-mixtral:8x7b (8x7B)"
3. **LLM sections**: Ollama appears as option for text generation

## Need More Help?

1. Run `test_ollama.py` and share the output
2. Run `ollama list` and share what models you have
3. Check if ImageAI is running on the same machine as Ollama
