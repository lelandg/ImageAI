# 🎬 ImageAI – Video Project Feature (PRD & Build Plan)
*Version:* 0.1 • *Date:* 2025-09-11 20:08 UTC  
*Owner:* ImageAI • *Status:* Draft

Veo API reference: 
https://ai.google.dev/gemini-api/docs/video?example=dialogue

---

## 1) Overview
Add a **Video Project** workflow to ImageAI that turns **lyrics/text** into an **auto‑storyboard** → **image generation** pipeline → **video assembly**.  
It uses existing provider integrations (Gemini, OpenAI, Stable Diffusion/local) for images and supports **Gemini Veo** (Veo 3 / Veo 3 Fast / Veo 2) for short AI‑native clips, plus a **local slideshow/ffmpeg** path for arbitrary lengths.

**Out of scope now:** music/beat/TTS, song mixing, external audio alignment.

**Additional development data:** I used ChatGPT-5 to create lyrics, image prompts, and "Veo project." Everything is in the (project root) `./Sample/` folder. It shows examples of image prompts based on lyrics, and a template folder layout for each Veo scene. I don't care what format the output is in, since it will produce a valid MP4. So consider this an example. It *would* be nice to save projects so the user can switch between them, and always restore the same images/videos.

---

## 2) Goals & Non‑Goals
### ✅ Goals
- Paste lyrics/text (the same format you used in *Grandpa Was a Democrat*) or load from file.
- Auto‑derive a **shotlist/storyboard** with scene durations that sum to either:
  - a user‑specified total length (e.g., 2:45), or
  - an auto‑estimate (based on line counts and pacing presets).
- Generate **N images** (per scene) using a selected **provider/model** (already wired in ImageAI).
- Human‑in‑the‑loop **review/approve/reorder/regenerate**.
- **Render video** via:
  - **Local slideshow** (Ken Burns, crossfades, captions; silent by default).
  - **Gemini Veo**: create 5–8s AI clips (Veo 2 silent, Veo 3 w/ audio) and concatenate.
- Save a **project file** (`.iaproj.json`) and all assets under a dedicated project folder.
- Keep detailed **metadata** for reproducibility & cost tracking.

### 🚫 Non‑Goals (initial)
- Audio/music timing, vocal synthesis, lyric karaoke overlays.
- Advanced continuity (face/character locking across all scenes) beyond seed/prompt carry‑over.
- Multi‑track timelines; we’ll ship a single-track MVP, then iterate.

---

## 3) UX Spec (GUI)
### New Tab: **🎬 Video Project**
- **Project header**: name, base folder, open/save.
- **Input panel**:
  - Text area + “Load from file…” (accepts `.txt`, `.md`, `.iaproj.json`).
  - **Format selector** (auto‑detect):  
    - *Timestamped lines:* `[mm:ss] line` (also accept `[mm:ss.mmm]`)  
    - *Structured lyrics:* `# Verse`, `# Chorus`, etc. (no timestamps)  
  - **Pacing preset**: *Fast / Medium / Slow* (affects scene durations when no timestamps).  
  - **Target Length**: `hh:mm:ss` (optional).

- **Provider & Prompting**:
  - **Image Provider**: Gemini / OpenAI / Stability / Local SD (+ model dropdown).  
  - **Style controls**: aspect ratio (pre‑set to **16:9**), quality, negative prompt, seed.  
  - **Prompt strategy**:  
    - “Literal line” vs “Cinematic rewrite” (LLM rewrites each line into a robust image prompt; supports template tokens).  
    - Template picker (Jinja‑like): `templates/lyric_prompt.j2`.

- **Storyboard panel**:
  - Auto‑computed **scenes table** (line → prompt → duration).  
  - Per‑scene **N variants** (e.g., 1–4) with thumbnail grid. Re‑roll per scene.  
  - Drag to reorder scenes; duration knob per scene; title/caption toggle.

- **Preview & Export**:
  - **Preview cut**: quick render (low res, fast transitions).  
  - **Export**:
    - **Local Slideshow** → `MP4 (H.264, 24fps)`; pan/zoom + crossfades; optional burned‑in captions.  
    - **Gemini Veo**: choose model (**Veo 3**, **Veo 3 Fast**, **Veo 2**), aspect ratio 16:9, resolution 720p/1080p (per model constraints), negative prompt; clip chaining with concat.  
    - **Mute audio** option (for Veo 3 outputs).  
  - **Render queue** with progress & logs.

---

## 4) Data & Files
```
{
  "schema": "imageai.video_project.v1",
  "name": "Grandpa Was a Democrat",
  "created": "ISO-8601",
  "provider": {
    "images": { "provider": "gemini|openai|stability|local", "model": "…" },
    "video":   { "provider": "veo|slideshow", "model": "veo-3.0-generate-001|veo-2.0-generate-001|…" }
  },
  "prompt_template": "templates/lyric_prompt.j2",
  "style": { "aspect_ratio": "16:9", "negative": "…", "seed": 1234 },
  "input": { "raw": "…lyrics…", "format": "timestamped|structured" },
  "timing": { "target": "00:02:45", "preset": "medium" },
  "scenes": [
    {
      "id": "scene-001",
      "source": "[00:12] Grandpa was a Democrat…",
      "prompt": "Cinematic Americana kitchen…",
      "duration_sec": 4.5,
      "images": [
        {
          "path": "assets/scene-001/var-1.png",
          "provider": "gemini",
          "model": "imagen-4.0-generate-001",
          "seed": 1234,
          "cost": 0.02,
          "metadata": {…}
        }
      ],
      "approved_image": "assets/scene-001/var-1.png"
    }
  ],
  "export": { "path": "exports/grandpa_2025-09-11.mp4" }
}
```

**Folders under project root**
- `assets/scene-xxx/*.png` (all variants + chosen)  
- `exports/*.mp4` (finals + previews)  
- `logs/*.jsonl` (events & cost)  
- `project.iaproj.json`

---

## 5) Architecture & Code Layout (proposed)
```
/gui
  video_project_tab.py            # New PySide6 tab widget
  widgets/storyboard_table.py     # Scene grid + thumbnails
  widgets/render_queue.py         # Progress & logs

/core
  storyboard.py                   # Parse input → scenes (ids, prompts, durations)
  prompt_engine.py                # LLM rewrite via Gemini/OpenAI
  image_batcher.py                # Fan‑out image jobs, retries, caching
  timing.py                       # Target-length allocation algorithm
  video/ffmpeg_slideshow.py       # Local slideshow builder
  video/veo_client.py             # Thin wrapper over google-genai generate_videos

/providers
  images/                         # (existing) ensure unified: generate_image(prompt, cfg)
  video/gemini_veo.py             # High-level “clip” API (5–8s), chaining, concat

/cli
  video.py                        # `python main.py video …` entry
  ```

**Touch points in existing repo**
- `main.py`: register tab → `VideoProjectTab()`  
- `providers/`: ensure image providers expose **uniform** signature:  
  `generate_image(prompt:str, size:tuple, negative:str|None, seed:int|None, **kwargs) -> Path`
- `templates/`: add `lyric_prompt.j2`, `shot_prompt.j2`

---

## 6) Core Algorithms
### 6.1 Lyric/Text → Scenes
- **Timestamped** lines: exact cut points from `[mm:ss(.mmm)]`; otherwise use **pacing preset** to distribute total length over lines, weighted by line length.
- **Shot count**: `ceil(total_length / target_shot_seconds)` (defaults: 3–5s per shot).  
- **LLM rewrite** (optional): for each line, produce a **cinematic** prompt (subject, action, style, camera, ambiance, negative).

### 6.2 Image Batch
- Concurrency capped per provider.
- **Idempotent cache** by hash of `(provider, model, prompt, seed, size)`.
- Backoff on rate limits; light dedupe of semantically near‑identical prompts.

### 6.3 Video Assembly
- **Local slideshow**: 24fps, H.264 MP4, default 16:9; per‑scene pan/zoom + 0.5s crossfades; optional captions (line text).  
- **Gemini Veo**:
  - Clip generator → `generate_videos(model, prompt, image=approved_first_frame, config)` producing **5–8s** segments (Veo 3/3 Fast: **audio on**; Veo 2: **silent**).  
  - Concat clips; **mute** if requested.  
  - Download within **2 days** (server retention) and store locally.

---

## 7) Constraints & Model Notes
- **Veo 3 / Veo 3 Fast**: 8s, 24fps, 720p or 1080p (16:9 only), audio always on.  
- **Veo 2**: 5–8s, 24fps, 720p, silent; can do 9:16 portrait.  
- **Region/person rules**: `personGeneration` options vary by region; enforce in UI.  
- **Ops pattern**: long‑running operation; poll until `done`, then download video file.  
- **Watermarking**: SynthID applied to Veo output.
- **Token/Input limits**: keep prompts concise; image‑to‑video supported.

> See links in References for the official docs; implement guardrails in the tab (tooltips & validation).

---

## 8) CLI (initial sketch)
```bash
# Build storyboard and images, then render slideshow
imageai video --in lyrics.txt --provider gemini --model imagen-4.0-generate-001   --length 00:02:30 --slideshow --out exports/grandpa.mp4

# Build Gemini Veo chain (silent)
imageai video --in lyrics.txt --image-provider openai --image-model dall-e-3   --veo-model veo-2.0-generate-001 --out exports/grandpa_veo.mp4 --mute
```

---

## 9) API Call Shapes
### Google Gemini – Veo (Python, google-genai)
```python
from google import genai
from google.genai import types

client = genai.Client()

op = client.models.generate_videos(
    model="veo-3.0-generate-001",
    prompt="Close-up cinematic shot of…",
    image=approved_png,  # optional
    config=types.GenerateVideosConfig(
        aspect_ratio="16:9",
        resolution="720p",             # Veo 3: 720p or 1080p; Veo 2: 720p only
        negative_prompt="low quality, cartoon, artifacting",
        person_generation="allow_adult",  # allowed values depend on region & mode
        seed=1234
    ),
)
while not op.done:
    op = client.operations.get(op)

video = op.response.generated_videos[0]
client.files.download(file=video.video)
video.video.save("clip-001.mp4")
```

### Local slideshow (ffmpeg idea)
```bash
ffmpeg -r 24 -f concat -safe 0 -i frames.txt -filter_complex   "zoompan=d=120,fade=t=in:st=0:d=0.5,fade=t=out:st=4.5:d=0.5"   -c:v libx264 -pix_fmt yuv420p exports/out.mp4
```

---

## 10) Validation
- Golden sample projects checked into `Plans/samples/` with deterministic seeds.
- Headless **CI smoke**: generate 2 scenes with tiny images + 2s clips; assert MP4 exists.

---

## 11) Risks & Mitigations
- **Model safety blocks** → auto‑rewrite prompts (LLM), add negative terms, or switch provider.
- **Latency** (Veo ops) → queue + UI progress + local preview path.
- **Regional restrictions** → gate `personGeneration` options by `iso_region`.
- **Cost overruns** → show running cost estimate per batch.

---

## 12) Phased Delivery
1. **MVP**: Tab, parser, storyboard, image batcher, slideshow export.  
2. **Veo integration**: 5–8s clips + concat; mute option; region gates.  
3. **Polish**: captions, presets, caching, cost panel, drag‑reorder UX.  
4. **Continuity**: seed carry‑over & “character sheet”.  
5. **Audio (future)**: external track alignment, beat mapping.

---

## 13) References
- Gemini API – Generate videos with Veo (models, durations, polling, retention): https://ai.google.dev/gemini-api/docs/video  
- Gemini API – Models catalog: https://ai.google.dev/gemini-api/docs/models  
- ImageAI repo README (providers, PySide6 GUI, CLI): https://github.com/lelandg/ImageAI

---

## 14) Acceptance Criteria (MVP)
- I can paste lyrics, click **Storyboard**, see scene rows with durations summing to target length.
- I can **Generate Images** and see thumbnails per scene; re‑roll one scene without touching others.
- I can **Export → Slideshow** and get a valid MP4 at 24fps, 16:9.
- All artifacts + a `project.iaproj.json` are saved under the project folder.
- Rerunning the same prompts with the same seed reuses cached images.
