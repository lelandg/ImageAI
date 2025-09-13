# 🧠 ImageAI — GPT‑5 Prompt Enhancer Pack
_Last updated: 2025-09-13T12:38:06.812177Z_

This pack gives you **drop‑in prompts** for GPT‑5 that take a short user prompt and return:
- a **unified (model‑agnostic)** prompt
- **provider‑specific** prompts (DALL·E 3, SDXL/Stability, Midjourney, Gemini/Imagen)
- optional **negative prompts**, **parameters** (CFG/steps/seed/AR), and **continuity objects** (characters/props)
- **N variants** for A/B testing

It also includes a **strict JSON schema** and **style presets** your code can load.

---

## 1) System Prompt (paste this as your `system` message)

```text
You are **ImageAI Prompt Enhancer**, a world‑class prompt engineer.
Your job: Convert minimal user input into **excellent image prompts** for multiple generators
while preserving intent and avoiding unsafe or copyrighted content.

### Output format (REQUIRED)
Return a single JSON object that **validates** against the schema the user provides in the next message.

### Goals
1) Create a concise **unified_prompt** (model‑agnostic) that captures subject, composition, lighting, style, mood.
2) Produce **by_model** prompts optimized for each provider the user requests, respecting each provider’s quirks:
   - OpenAI DALL·E 3: strong natural language; avoid parameter syntax; no explicit negative prompt.
   - Stability SDXL: allow `negative_prompt`, `cfg`, `steps`, `seed`.
   - Midjourney: pack prompt text; add light parameter hints (`--ar`, `--stylize`, `--seed`) only if supplied by user or schema.
   - Gemini / Imagen: rich descriptive text; mention composition, medium, lighting, lens if relevant.
3) Include optional **continuity**: persist **character_sheet** (id, traits) and **reference_images**.
4) Generate **variants** (controlled rephrasings) if `num_variants > 0`.
5) Respect the **enhancement_level**: `"low" | "medium" | "high"` (rewrite degree and specificity).
6) Always keep it safe, tasteful, and non‑infringing. If user intent is unsafe, **refuse** with a clear explanation via the `error` field in JSON.

### Rules
- Do **not** include commentary, markdown, or extra keys—**only** valid JSON as defined by the schema.
- Keep descriptions vivid but **tight** (avoid purple prose and repetition).
- Prefer **photographically plausible** details when the user asks for realism.
- Preserve named entities, products, or sensitive attributes **only** if user explicitly asked.
- Never invent factual claims about real people; avoid private data.
```

---

## 2) User Prompt (template you can fill programmatically)

**Use as your `user` message**. Fill the placeholders or remove the optional blocks.

```text
Validate your response against the attached JSON schema.

INPUT:
- user_prompt: "{user_prompt}"
- enhancement_level: "{enhancement_level}"  # low | medium | high
- aspect_ratio: "{aspect_ratio}"            # e.g., 1:1, 16:9, 9:16, 3:2 (optional)
- guidance: {guidance}                      # e.g., 7.5 (SDXL) (optional)
- steps: {steps}                            # e.g., 30 (SDXL) (optional)
- seed: {seed}                              # integer or null (optional)
- num_variants: {num_variants}              # how many rephrasings to include

- target_models: ["openai_dalle3","stability_sdxl","midjourney","gemini_imagen"]

- style_preset: "{style_preset}"            # e.g., cinematic-photoreal, watercolor-children, pixel-art (optional)
- color_palette: ["{hex1}","{hex2}","{hex3}"]  # optional
- camera: {{ "shot":"{shot}", "lens":"{lens}", "aperture":"{aperture}" }}  # optional
- lighting: "{lighting}"                    # e.g., golden hour, studio softbox, Rembrandt (optional)
- negative_terms: ["{neg1}","{neg2}"]       # optional (used where supported)

- continuity: {{
    "character_sheet": {{"id":"{char_id}","name":"{char_name}","description":"{char_desc}","persistent_traits":["{trait1}","{trait2}"]}},
    "reference_images": ["{url_or_base64}"]
  }}

- provider_hints: {{
    "midjourney": {{"stylize": 250, "chaos": 0, "weird": 0}},
    "stability_sdxl": {{"clip_skip": null, "sampler": "DPM++ 2M Karras"}},
    "openai_dalle3": {{"quality": "standard"}},
    "gemini_imagen": {{}}
  }}

SCHEMA: (the schema will be provided separately or pasted below)
```

> Tip: If you don’t want continuity, presets, or provider hints—omit those blocks.

---

## 3) Lite “one‑liner” prompt (handy for quick tests)

```text
Rewrite the following into (a) one unified prompt and (b) model‑specific prompts for DALL·E 3, SDXL, Midjourney, and Gemini/Imagen; include optional negative prompt (only where supported), recommended AR/CFG/steps/seed, and up to 3 concise variants. Return **only** JSON that validates the attached schema. Input: "{user_prompt}".
```

---

## 4) Scene/Storyboard Builder (lyrics → scene prompts)

```text
Task: Segment the input lyrics/text into coherent visual **scenes** and produce an ordered list of **scene prompts** for image generation with continuity.

Requirements:
- Maintain character/prop continuity across scenes (use continuity.character_sheet).
- Each scene: include a short title, visual objective, unified prompt, provider‑specific prompts, suggested AR, and optional duration (sec).
- Keep per‑scene prompts terse but specific; avoid repeating global continuity details.
- Return JSON: {{ "scenes":[ {{ "id":"S01","title":"...","duration":5,"unified":{{...}},"by_model":{{...}} }}, ... ] }}, validating the same schema.

Input:
- lyrics_or_text: <<<{lyrics_or_text}>>>
- continuity (optional): {{ "character_sheet": {{...}} , "reference_images": ["..."] }}
- target_models: ["openai_dalle3","stability_sdxl","midjourney","gemini_imagen"]
- enhancement_level: "medium"
- default_ar: "16:9"
- num_variants: 0
```

---

## 5) JSON Schema (load this on the tool side and send with each request)

> A copy of this schema is saved as **`image_prompt_schema.json`** in this pack.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ImageAI Prompt Enhancer Output",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "error": {
      "type": [
        "string",
        "null"
      ]
    },
    "unified": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "prompt": {
          "type": "string"
        },
        "negative_prompt": {
          "type": [
            "string",
            "null"
          ]
        },
        "style_tags": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "aspect_ratio": {
          "type": [
            "string",
            "null"
          ],
          "pattern": "^(1:1|16:9|9:16|4:3|3:2|21:9)$"
        },
        "guidance": {
          "type": [
            "number",
            "null"
          ],
          "minimum": 0,
          "maximum": 30
        },
        "steps": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 1,
          "maximum": 200
        },
        "seed": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        }
      },
      "required": [
        "prompt"
      ]
    },
    "by_model": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "openai_dalle3": {
          "type": [
            "string",
            "null"
          ]
        },
        "stability_sdxl": {
          "type": [
            "object",
            "null"
          ],
          "additionalProperties": false,
          "properties": {
            "prompt": {
              "type": "string"
            },
            "negative_prompt": {
              "type": [
                "string",
                "null"
              ]
            },
            "cfg": {
              "type": [
                "number",
                "null"
              ],
              "minimum": 0,
              "maximum": 25
            },
            "steps": {
              "type": [
                "integer",
                "null"
              ],
              "minimum": 1,
              "maximum": 200
            },
            "seed": {
              "type": [
                "integer",
                "null"
              ],
              "minimum": 0
            },
            "sampler": {
              "type": [
                "string",
                "null"
              ]
            }
          },
          "required": [
            "prompt"
          ]
        },
        "midjourney": {
          "type": [
            "string",
            "null"
          ]
        },
        "gemini_imagen": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "openai_dalle3",
        "stability_sdxl",
        "midjourney",
        "gemini_imagen"
      ]
    },
    "continuity": {
      "type": [
        "object",
        "null"
      ],
      "additionalProperties": false,
      "properties": {
        "character_sheet": {
          "type": [
            "object",
            "null"
          ],
          "additionalProperties": false,
          "properties": {
            "id": {
              "type": "string"
            },
            "name": {
              "type": [
                "string",
                "null"
              ]
            },
            "description": {
              "type": [
                "string",
                "null"
              ]
            },
            "persistent_traits": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          },
          "required": [
            "id"
          ]
        },
        "reference_images": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    },
    "variants": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "prompt": {
            "type": "string"
          },
          "note": {
            "type": [
              "string",
              "null"
            ]
          }
        },
        "required": [
          "prompt"
        ]
      }
    }
  },
  "required": [
    "unified",
    "by_model"
  ]
}
```

---

## 6) Style Presets (optional)

> A copy is saved as **`prompt_presets.json`**. Load these into a dropdown.

```json
{
  "presets": [
    {
      "id": "cinematic-photoreal",
      "label": "Cinematic Photoreal",
      "style_tags": [
        "photorealistic",
        "cinematic",
        "volumetric lighting",
        "film grain"
      ],
      "camera": {
        "shot": "wide",
        "lens": "35mm",
        "aperture": "f/2.8"
      },
      "lighting": "golden hour soft rim light",
      "default_ar": "16:9"
    },
    {
      "id": "illustrated-watercolor",
      "label": "Watercolor Illustration",
      "style_tags": [
        "watercolor",
        "paper texture",
        "soft edges",
        "ink outline"
      ],
      "lighting": "soft diffuse daylight",
      "default_ar": "3:2"
    },
    {
      "id": "pixel-art",
      "label": "Pixel Art (8\u2011bit)",
      "style_tags": [
        "8-bit",
        "pixel art",
        "limited palette",
        "CRT scanlines"
      ],
      "default_ar": "1:1"
    },
    {
      "id": "studio-portrait",
      "label": "Studio Portrait",
      "style_tags": [
        "portrait",
        "skin\u2011tone accurate",
        "high detail",
        "bokeh"
      ],
      "camera": {
        "shot": "headshot",
        "lens": "85mm",
        "aperture": "f/1.8"
      },
      "lighting": "beauty dish + fill card",
      "default_ar": "4:5"
    }
  ]
}
```

---

## 7) Integration sketch (Python, pseudo‑API)

```python
from your_llm_client import chat

SYSTEM = open("system_prompt.txt").read()  # or paste from section 1
USER = make_user_prompt(user_prompt, opts, schema_json)
resp = chat(model="gpt-5", system=SYSTEM, user=USER, temperature=0.2)
data = json.loads(resp)  # validate against schema before using

# Then route:
# - data["by_model"]["openai_dalle3"] -> DALL·E 3 call
# - data["by_model"]["stability_sdxl"]["prompt"], ["negative_prompt"], cfg/steps/seed -> SDXL
# - data["by_model"]["midjourney"] -> MJ (relay)
# - data["by_model"]["gemini_imagen"] -> Gemini image gen
```

---

## 8) Suggested UX Options (value‑add surface)

- **Enhancement Level** slider: low / medium / high
- **Style Preset** dropdown (ships with `prompt_presets.json`)
- **Continuity** panel: Character sheet builder + Reference image(s)
- **Aspect Ratio** picker with previews
- **Negative Prompt** library (with on/off toggle per provider)
- **A/B Variants**: choose N; auto‑label thumbnails with diff (AR/guidance/wording)
- **Seed Controls**: lock/unlock global seed for reproducibility
- **Lighting & Camera** quick‑pills (golden hour, studio softbox; 35mm, 85mm, macro)
- **Safety guardrails** toggles (disallow NSFW/gore; disallow real‑person likeness)
- **Project Memory**: save continuity + presets into named “Style Kits” for reuse

---

Happy generating! ✨