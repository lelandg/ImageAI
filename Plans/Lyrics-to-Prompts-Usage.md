# Lyrics-to-Image Prompts Feature - Usage Guide

## Overview

The **Lyrics-to-Image Prompts** feature converts song lyrics into descriptive image generation prompts using AI language models (LLMs). This is useful for creating visual content that matches lyrics, such as lyric videos, album art concepts, or video projects.

**IMPORTANT: Batch Processing** - All lyrics are sent to the LLM in a **single API call** and all prompts are generated at once. This is more efficient, cost-effective, and ensures consistent style across all prompts. You don't need to process lyrics one at a time.

## Features

- **Multiple LLM Support**: Works with OpenAI (GPT-4, GPT-5), Google (Gemini), Anthropic (Claude), Ollama, and LM Studio
- **Flexible Input**: Load lyrics from files or paste directly
- **Style Control**: Optional style hints (cinematic, photorealistic, artistic, etc.)
- **Temperature Control**: Adjust creativity/randomness of generated prompts
- **JSON Export**: Save results in structured JSON format
- **Video Project Integration**: Create video projects directly from lyrics/prompts (GUI only)

## GUI Usage

### Opening the Dialog

1. Launch ImageAI GUI
2. Go to **Tools** → **Lyrics to Image Prompts...**

### Using the Dialog

1. **Input Lyrics**:
   - Paste lyrics directly into the text area (one line per lyric)
   - OR click **Load from File...** to load a `.txt` file

2. **Configure Settings**:
   - **Model**: Select the LLM model (e.g., "OpenAI: gpt-4o", "Google: gemini-2.0-flash-exp")
   - **Temperature**: 0.0 (deterministic) to 2.0 (very creative). Default: 0.7
   - **Style Hint** (optional): Add style guidance like "cinematic", "photorealistic", "abstract"

3. **Generate**:
   - Click **Generate Image Prompts** (or press Ctrl+Enter)
   - Watch the status console for progress
   - Generated prompts appear in the results section

4. **Export or Use**:
   - **Export JSON**: Save prompts to a JSON file
   - **Create Video Project**: Create a new video project with lyrics as scenes (switches to Video tab)
   - **Close**: Exit the dialog

### Keyboard Shortcuts

- **Ctrl+Enter**: Generate prompts
- **Escape**: Close dialog

## CLI Usage

### Basic Command

```bash
python main.py --lyrics-to-prompts LYRICS_FILE.txt
```

### Full Example

```bash
python main.py \
  --lyrics-to-prompts my_song_lyrics.txt \
  --lyrics-model gpt-4o \
  --lyrics-temperature 0.7 \
  --lyrics-style cinematic \
  --lyrics-output my_prompts.json
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--lyrics-to-prompts FILE` | Path to lyrics file (required) | - |
| `--lyrics-model MODEL` | LLM model to use | `gpt-4o` |
| `--lyrics-temperature FLOAT` | Creativity (0.0-2.0) | `0.7` |
| `--lyrics-style STYLE` | Style hint (optional) | None |
| `--lyrics-output FILE` | Output JSON file | `{input}.prompts.json` |

### Model Format

Models are specified with provider prefixes:

- **OpenAI**: `gpt-4o`, `gpt-4-turbo`, `o1`, `o1-mini`
- **Google**: `gemini/gemini-2.0-flash-exp`, `gemini/gemini-2.5-flash-preview`
- **Anthropic**: `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`
- **Ollama**: `ollama/llama3.1`, `ollama/mistral`
- **LM Studio**: `lmstudio/model-name`

## Input Format

### Lyrics File Format

Plain text file with one lyric line per line:

```
When the night feels endless and I'm wide awake
I shuffle numbers like cards
I hum a rhythm, let the numbers dance
And suddenly it's not so hard
```

Empty lines are automatically filtered out.

## Output Format

### JSON Structure

```json
{
  "prompts": [
    {
      "line": "When the night feels endless and I'm wide awake",
      "imagePrompt": "lonely figure under a starry night sky, glowing city lights below, eyes open in wonder, cinematic lighting"
    },
    {
      "line": "I shuffle numbers like cards",
      "imagePrompt": "mathematician at a dim jazz club table, cards with glowing equations swirling midair"
    }
  ]
}
```

## Examples

### Example 1: Basic Usage (GUI)

1. Open **Tools** → **Lyrics to Image Prompts**
2. Paste lyrics:
   ```
   Sunset on the mountain peak
   Colors bleeding through the sky
   Silence louder than my thoughts
   ```
3. Select model: "OpenAI: gpt-4o"
4. Click **Generate Image Prompts**
5. Review results and export or create video project

### Example 2: CLI with Custom Settings

```bash
# Generate prompts with photorealistic style
python main.py \
  --lyrics-to-prompts lyrics/verse1.txt \
  --lyrics-model gemini/gemini-2.0-flash-exp \
  --lyrics-style photorealistic \
  --lyrics-temperature 0.5 \
  --lyrics-output prompts/verse1_prompts.json
```

### Example 3: Batch Processing (Shell Script)

```bash
#!/bin/bash
# Process multiple lyric files

for file in lyrics/*.txt; do
  output="prompts/$(basename "$file" .txt)_prompts.json"
  python main.py \
    --lyrics-to-prompts "$file" \
    --lyrics-model gpt-4o \
    --lyrics-output "$output"
done
```

## Style Hints

Supported style hints include:

- **cinematic**: Movie-style visuals with dramatic lighting and composition
- **photorealistic**: Realistic photography style
- **artistic**: Artistic interpretation, painterly
- **abstract**: Abstract visual concepts
- **animated**: Animation/cartoon style
- **documentary**: Documentary photography style
- **noir**: Film noir style (high contrast, dramatic shadows)
- **fantasy**: Fantasy art style
- **sci-fi**: Science fiction themes
- **vintage**: Retro/vintage aesthetic
- **minimalist**: Simple, clean compositions

You can also use custom style descriptions.

## Troubleshooting

### "No API keys found"

**Solution**: Set up API keys first:

```bash
# Set OpenAI key
python main.py --provider openai --api-key YOUR_KEY --set-key

# Set Google key
python main.py --provider google --api-key YOUR_KEY --set-key

# Set Anthropic key
python main.py --provider anthropic --api-key YOUR_KEY --set-key
```

Or set via GUI: **Settings** tab → Provider API keys

### "LiteLLM not installed"

**Solution**: Install LiteLLM:

```bash
pip install litellm
```

### Empty or Poor Quality Prompts

**Try**:
- Increase temperature (0.7 → 1.0)
- Add a style hint
- Use a different model (try GPT-4 or Gemini 2.0)
- Make lyrics more descriptive

### JSON Parsing Errors

The system has fallback parsers that handle:
- Markdown code blocks
- Plain text responses
- Malformed JSON

If parsing fails completely, fallback prompts are generated based on the input lyrics.

## API Costs

Be aware of API costs when using cloud LLM providers:

- **OpenAI GPT-4**: ~$0.01-0.03 per song
- **Google Gemini**: Often free tier available
- **Anthropic Claude**: Pay-per-token pricing
- **Local models** (Ollama, LM Studio): Free

Check your provider's pricing page for current rates.

## Integration with Video Projects

When using **Create Video Project** in the GUI:

1. Prompts are converted to video scenes
2. Each lyric becomes a scene with its generated prompt
3. The Video tab opens with the new project
4. You can then:
   - Generate images for each scene
   - Adjust scene durations
   - Add audio
   - Render the final video

## Best Practices

1. **Quality Lyrics**: More descriptive lyrics produce better prompts
2. **Style Consistency**: Use the same style hint for a cohesive look
3. **Temperature**: Start at 0.7, adjust based on results
4. **Model Selection**: GPT-4 and Gemini 2.0 generally produce the best results
5. **Review & Edit**: Always review generated prompts before using them
6. **Version Control**: Save JSON files for future reference

## See Also

- [Lyrics-to-Image-Prompt-Guide.md](./Lyrics-to-Image-Prompt-Guide.md) - Technical specification
- [ImageAI-VideoProject-PRD.md](./ImageAI-VideoProject-PRD.md) - Video project features
- Main README.md - General ImageAI documentation

---

**© 2025 Leland Green Productions — ImageAI Project**
