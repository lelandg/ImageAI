
# 🎵 Lyrics-to-Image Prompt Generator (Cross-Model Guide)

This document explains how to submit a **lyrics file** to GPT‑5, Gemini, Claude, or local LLMs to generate **one image prompt per lyric line**.

---

## ✅ Universal Prompt Template

### **System Prompt**
```
You are a text-to-image prompt generator. 
The user will provide song lyrics (one or more lines). 
For each lyric line, output one descriptive image prompt suitable for an image generation model. 
Do not include commentary or additional text.

Format the response in valid JSON with the following schema:
{
  "prompts": [
    {"line": "original lyric line", "imagePrompt": "detailed descriptive image prompt"}
  ]
}

Rules:
- Keep "line" identical to the input lyric.
- Make "imagePrompt" visually descriptive, cinematic, or stylistically matched to the lyric’s tone.
- Avoid repeating phrases or song structure terms.
- Do not include the word "prompt" or reference to AI or art tools.
```

### **User Prompt Example**
```
Lyrics:
When the night feels endless and I'm wide awake
I shuffle numbers like cards
I hum a rhythm, let the numbers dance
And suddenly it’s not so hard
```

### **Expected Output**
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
    },
    {
      "line": "I hum a rhythm, let the numbers dance",
      "imagePrompt": "musician surrounded by floating numbers forming rhythmic patterns, jazz ambience"
    },
    {
      "line": "And suddenly it’s not so hard",
      "imagePrompt": "warm sunrise through window, calm expression, soft light filling the room"
    }
  ]
}
```

---

## 🧩 Model-Specific Variants

| Model | Input Format | Notes |
|--------|---------------|-------|
| **GPT‑5 / OpenAI** | JSON or plain text lyrics. Use the above full prompt verbatim. | Use `gpt‑5‑turbo` or `gpt‑5‑chat‑latest` for best structure. |
| **Gemini 2.5 Pro / Flash** | Same format. Prefix with “Output must be valid JSON only.” | Gemini sometimes needs stricter JSON enforcement. |
| **Claude Sonnet / Opus** | Identical prompt. Add “Ensure perfect JSON syntax, no extra commentary.” | Claude sometimes adds prose before JSON. |
| **Local LLMs (Mistral, Llama, etc.)** | Use shorter prompt: “Generate a JSON array of descriptive image prompts per lyric line.” | Simpler to reduce token overhead. |

---

## 💡 Output Handling

If you want a **machine‑readable** return (for pipelines), JSON is best.  
If you only need a **human‑readable** version, you can use this lighter instruction:

```
Return one image prompt per line, formatted as:
[lyric] → [image description]
```

Example:
```
When the night feels endless and I'm wide awake → lonely figure under a starry sky
I shuffle numbers like cards → glowing cards with equations
```

---

## ⚙️ Optional Code Integration

You can automate this process in Python or shell using the OpenAI, Gemini, or Anthropic APIs.  
Ask ChatGPT to create a ready‑to‑use uploader script if needed (e.g., submit `.txt` lyrics → receive `.json` of prompts).

---

**© 2025 Leland Green Productions — ImageAI Project**
