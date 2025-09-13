This is awesome progress. Below is a complete, copy‑ready workflow that:

1. splits lyrics into scenes with an LLM,
2. turns scenes into high‑quality image prompts (for stills) and Veo prompts, and
3. submits those prompts to **Veo 3** in Python.

I also packaged everything as a small starter kit you can download.

**Download:** [Lyrics → Scenes → Prompts → Veo 3 (Python kit)](sandbox:/mnt/data/lyrics_to_video_kit.zip)

---

## What’s inside the kit

* `docs/Lyrics_to_Video_Pipeline.md` – instructions + **exact prompts** to copy/paste
* `src/models.py` – Pydantic schema to enforce structured JSON
* `src/lyrics_to_scenes.py` – **Gemini 2.5 Pro** structured-output example
* `src/lyrics_to_scenes_claude.py` – **Anthropic Claude** example
* `src/lyrics_to_scenes_local.py` – **Ollama/local LLM** example
* `src/scenes_to_prompts.py` – polishes per‑scene **image prompts** and Veo prompts
* `src/submit_to_veo.py` – sends prompts to **Veo 3** and downloads MP4s
* `examples/sample_lyrics.txt` – a test lyric

> Set environment variables before running:
>
> ```bash
> export GEMINI_API_KEY="..."
> export ANTHROPIC_API_KEY="..."
> ```

---

## The prompts you asked for (exact text)

You can use these with Gemini, Claude, or a local LLM. They are also embedded in the kit.

### A) Scene splitter (lyrics → scenes JSON)

**SYSTEM**

> You are a senior film editor and story artist. From input song lyrics, divide the music video into scenes that maximize emotional clarity and visual continuity. Your output MUST be valid JSON that conforms to the provided schema exactly—no extra keys, no commentary. Use clean language. Prefer realistic, cinematic imagery. Avoid fantasy/sci‑fi unless present in the lyrics. Keep scenes coherent and minimize unnecessary cuts.

**USER**

> Task: Create a scene plan from these lyrics.
> Inputs:
> – SONG\_TITLE: {{SONG\_TITLE}}
> – LYRICS:
> {{LYRICS}}
> – TARGET\_DURATION\_SEC: {{TOTAL\_SECONDS}}  # if unknown, distribute proportionally by section length
> – GLOBAL\_STYLE: {{GLOBAL\_STYLE}}  # e.g., “warm Kodak palette, 35mm grain, soft halation”
> – NEGATIVES: {{NEGATIVES}}  # e.g., “neon, sci‑fi UI, cartoon, unreadable text, gore”
>
> Schema (must match exactly):
>
> ```json
> {
>   "scenes": [
>     {
>       "scene_id": "S1",
>       "section": "Intro|Verse|Pre-chorus|Chorus|Bridge|Outro|Instrumental",
>       "start_sec": 0,
>       "duration_sec": 8,
>       "summary": "string, \u2266140 chars",
>       "rationale": "string, why cut here",
>       "continuity": {
>         "characters": ["names or roles"],
>         "locations": ["kitchen", "rural church", "..."],
>         "props": ["Bible", "banner", "loaf of bread"]
>       },
>       "veo_prompt": "One paragraph: subject \u2192 context \u2192 action \u2192 camera \u2192 light \u2192 ambience \u2192 style. Include subtle audio cues if helpful.",
>       "image_prompts": {
>         "dalle3": "concise cinematic still description",
>         "sd_style": {
>           "positive": "strong descriptive tokens",
>           "negative": "artifact avoiders",
>           "params": {"ar": "16:9", "cfg": 7, "steps": 30}
>         }
>       },
>       "negatives": ["list of discouraged elements"]
>     }
>   ]
> }
> ```
>
> Rules:
>
> 1. If sections are labeled in the lyrics (\[Verse], etc.), use them to guide scenes. Otherwise infer natural breaks by imagery/POV/time.
> 2. Assign `duration_sec` so total ≈ `TARGET_DURATION_SEC`. If missing, assume \~8s per scene (or match your preferred clip length).
> 3. Keep continuity tight: repeat characters/locations/props across scenes when the lyrics suggest.
> 4. Veo prompt must be single-paragraph, filmic, concrete, and avoid brand names unless explicitly in lyrics.
> 5. Image prompts should be still-friendly (clean composition, texture details).
> 6. Use NEGATIVES to avoid undesirable elements.

---

### B) Prompt polisher (upgrade per‑scene image prompts)

**SYSTEM**

> You are a cinematographer and photo director. Refine each scene’s `image_prompts` for one perfect hero still. Keep style consistent with `GLOBAL_STYLE`. Return updated JSON matching the schema exactly.

**USER**

> Inputs:
> – GLOBAL\_STYLE: {{GLOBAL\_STYLE}}
> – NEGATIVES: {{NEGATIVES}}
> – SCENES\_JSON: `{{SCENES_JSON}}`
>
> Instructions: Make the DALL·E prompt concise but cinematic. For SD-style, enrich **positive** with lens/film terms (e.g., “35mm, shallow DOF, warm halation, subtle grain”) and keep **negative** practical (artifacts/anatomy/text). Preserve meaning; improve clarity.

---

### C) Veo 3 prompt assembler

**SYSTEM**

> You are a video director preparing submit‑ready prompts for Veo 3. Each scene must become an 8‑second 16:9 clip with optional audio cues. Return a list of objects with fields: `scene_id`, `duration_sec` (≤8), `aspect_ratio` ("16:9" or "9:16"), `resolution` ("720p" or "1080p"), `prompt`, `negative_prompt`.

**USER**

> Inputs:
> – SCENES\_JSON: `{{SCENES_JSON}}`
> – DEFAULTS: aspect\_ratio=16:9, resolution=1080p (16:9 only), duration\_sec=8, negative\_prompt={{NEGATIVES}}
> – NOTES: For vertical tests, set aspect\_ratio=9:16 (720p). Keep prompt single paragraph with gentle camera moves.

---

## Python commands (quick start)

1. **Gemini 2.5 Pro** (structured scenes)

```bash
python src/lyrics_to_scenes.py examples/sample_lyrics.txt \
  --title "Grandpa Was a Democrat" \
  --total-sec 96 \
  --style "warm Kodak, 35mm grain, soft halation" \
  --negatives "neon, sci-fi UI, cartoon, unreadable text, gore"
```

2. **Claude** (same JSON schema; with a repair step)

```bash
python src/lyrics_to_scenes_claude.py examples/sample_lyrics.txt \
  --title "Grandpa Was a Democrat" \
  --total-sec 96 \
  --style "warm Kodak, 35mm grain, soft halation" \
  --negatives "neon, sci-fi UI, cartoon, unreadable text, gore"
```

3. **Local LLM (Ollama)**

```bash
python src/lyrics_to_scenes_local.py examples/sample_lyrics.txt \
  --model "llama3.1" \
  --title "Grandpa Was a Democrat" \
  --total-sec 96 \
  --style "warm Kodak, 35mm grain, soft halation" \
  --negatives "neon, sci-fi UI, cartoon, unreadable text, gore"
```

4. **Polish image + Veo prompts**

```bash
python src/scenes_to_prompts.py scenes.json polished_scenes.json \
  --style "warm Kodak, 35mm grain, soft halation" \
  --negatives "neon, sci-fi UI, cartoon, unreadable text, gore"
```

5. **Submit to Veo 3** (Gemini API via `google-genai`):

```bash
python src/submit_to_veo.py polished_scenes.json \
  --model veo-3.0-generate-001 \
  --ar 16:9 \
  --res 1080p \
  --out videos/
```

---

## Model choices & API notes (verified)

* **Gemini 2.5 Pro** model id is `gemini-2.5-pro`; install the official **google‑genai** SDK and use `Client().models.generate_content(...)`. It supports **structured outputs** with `response_schema`, which we use to force valid JSON. ([Google AI for Developers][1])

* **Veo 3** text/image → video via Gemini API or Vertex AI:

  * Gemini API examples show Python `client.models.generate_videos(model="veo-3.0-generate-001", ...)` and clarify **parameters** like `aspectRatio`, `negativePrompt`, `resolution` (1080p for 16:9), and long‑running operations polling. ([Google AI for Developers][2])
  * Vertex AI reference lists current **model IDs** (`veo-3.0-generate-001`, `veo-3.0-fast-generate-001`) and request parameters (`durationSeconds`, `aspectRatio`, `resolution`, `negativePrompt`, `seed`, etc.). ([Google Cloud][3])
  * Recent updates note **9:16 vertical support** (720p) and broader GA availability; pricing and capabilities can evolve—always check the latest docs. ([Google AI for Developers][2])

* **Anthropic Claude**: Use the **Messages API** with a system prompt and JSON‑only instruction. Model names include snapshots like `claude-sonnet-4-20250514`; production code should prefer specific snapshots for consistency. ([Anthropic][4])

* **Local LLMs**: Use **Ollama** via REST or the Python library (`pip install ollama-python`). Endpoint `/api/chat` or `/api/generate` can return responses; add a JSON repair step and validate against your schema. ([Ollama][5])

---

## Practical tips

* **Continuity control**: the schema’s `continuity` block carries character, location, and prop “memory” across scenes. Seed your prompts with those to keep Grandpa/church/march consistent.
* **Durations**: Veo 3 generates 8‑second clips; if your music sync differs, create multiple adjacent prompts per section.
* **Vertical**: For social cutdowns, set `aspectRatio="9:16"`; current docs show **720p** vertical for Veo 3; keep your master in 16:9 1080p. ([Google AI for Developers][2])
* **People generation**: obey `personGeneration` and regional allowances in the docs; if in a restricted region, adjust. ([Google AI for Developers][2])
* **Structured output**: Gemini 2.5 Pro’s `response_schema` is the most reliable way to force valid JSON; if other models stray, run a fast “repair + re‑validate” pass. ([Google AI for Developers][6])

---

If you want, I can also wire this into your **Reference Workflow Kit** so every scene automatically writes still prompts into the right folders (01\_References / 02\_Scenes / 03\_Broll) and then uploads selected stills to GCS for image‑to‑video variants.

[1]: https://ai.google.dev/gemini-api/docs/models "Gemini models  |  Gemini API  |  Google AI for Developers"
[2]: https://ai.google.dev/gemini-api/docs/video "Generate videos with Veo 3 in Gemini API  |  Google AI for Developers"
[3]: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation "Veo on Vertex AI video generation API  |  Generative AI on Vertex AI  |  Google Cloud"
[4]: https://docs.anthropic.com/en/api/messages "Messages - Anthropic"
[5]: https://ollama.readthedocs.io/en/api/?utm_source=chatgpt.com "API Reference - Ollama English Documentation"
[6]: https://ai.google.dev/gemini-api/docs/structured-output?utm_source=chatgpt.com "Structured output | Gemini API | Google AI for Developers"
