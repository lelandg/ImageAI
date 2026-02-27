# Prompt Tools

## Overview

ImageAI includes a full suite of AI-powered prompt tools to help you write better prompts, explore creative variations, and get answers about image generation — all without leaving the app.

## Features

### Prompt Builder

Build a complete prompt from modular building blocks instead of writing everything from scratch.

1. Open the Prompt Builder tab.
2. Select from the structured categories:

| Category | Examples |
|----------|---------|
| Subject type | Portrait, landscape, product, animal |
| Transformation style | Cartoon, realistic, watercolor, oil paint |
| Art style | Impressionist, anime, cyberpunk, art nouveau |
| Medium | Digital painting, pencil sketch, photography |
| Lighting | Golden hour, studio, neon, dramatic shadow |
| Mood | Mysterious, joyful, melancholic, epic |
| Artist influence | Monet, Banksy, Miyazaki, Rembrandt |
| Background | Abstract, urban, nature, studio white |
| Exclusions | Enter words you want excluded; "no" is added automatically |

3. Watch the live prompt preview update as you click.
4. When you are satisfied, click Use Prompt to send it to the Generate tab.

**Built-in Presets:**
Load a complete starting point in one click — MAD Magazine Style, Cyberpunk Neon, Renaissance Portrait, Anime Character, and others.

**Export and Import:**
Save your prompt as a JSON file to reuse later. Import previously saved prompt files to pick up where you left off.

### Enhance Prompt

One-click AI improvement of your existing prompt.

1. Write a basic prompt in the Generate tab (e.g., "a dog in a park").
2. Click Enhance Prompt.
3. The AI rewrites and expands your prompt with more detail, then places the result back in the prompt field ready to generate.

This feature uses your configured LLM provider.

### Generate Prompts

Create a list of prompt variations from your starting idea.

1. Enter your concept or a rough idea.
2. Click Generate Prompts.
3. Choose from the list of generated variations — each one is tracked in history so you can return to any version.

Useful for exploring creative directions before committing to a generation.

### Ask AI Anything

An interactive Q&A assistant for prompt help, image generation advice, and creative guidance.

1. Click Ask AI Anything in the Generate tab.
2. Type your question — for example, "How do I make an image look like a vintage movie poster?" or "What's a good prompt for a stormy seascape?".
3. The assistant responds with advice and can include prompt suggestions you can copy directly.

The conversation context is maintained within the session so you can ask follow-up questions.

### Reference Image Analysis

Get an AI-written description of any image you upload.

1. Open Reference Image Analysis (in the AI Tools section).
2. Upload an image.
3. The AI describes the image in detail — you can use the description as a starting point for a prompt.

Supported input formats: PNG, JPEG, WebP.

### Supported LLM Providers for Prompt Tools

All prompt AI features use your configured LLM provider:

- OpenAI GPT-5
- Anthropic Claude
- Google Gemini
- Ollama (local)
- LM Studio (local)

Configure your LLM provider in Settings.

## Common Questions

**Q: Does using prompt tools cost extra?**
Enhance Prompt and Ask AI Anything make calls to your LLM provider, which may incur API costs depending on your plan. Local providers (Ollama, LM Studio) have no API cost.

**Q: Can I undo an Enhance Prompt result?**
The original prompt is replaced in the field. If you want to keep your original, copy it before clicking Enhance, or use Ctrl+Z to undo the text replacement.

**Q: How many prompt variations does Generate Prompts create?**
Typically 5–10 variations, depending on your prompt length and the LLM provider's response. The full list appears in the generation dialog.

**Q: Do I need a separate API key for prompt AI features?**
Prompt tools use whichever LLM provider is selected in Settings. This can be a different key from your image generation provider.
