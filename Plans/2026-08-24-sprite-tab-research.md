# Sprite Tab — Research Summary

*Date: 2026-08-24*
*Status: research complete — awaiting feature selection*

## Purpose

Research for a new **Sprite tab**: AI-generated game sprite animations
(transparent backgrounds, standard resolutions, fps, color counts, palettes),
inspired by Nim.video's Animate Studio pipeline.

## Deliverables

| File | Content |
|------|---------|
| `2026-08-24-sprite-tab-feature-selector.html` | **Interactive selector** — 60 features, 18 critic gaps, 10 open questions, proposed defaults, live-test evidence. Open in a browser, check features, press "Copy selections as Markdown", paste the result back into a Claude session. |
| `2026-08-24-sprite-tab-research/` | Raw research JSON: full finder reports, synthesized catalog, claim verdicts, critique. |

## Method

- 19-agent research workflow: 7 parallel researchers (sheet formats,
  pixel-art conventions, editor survey, AI animation landscape,
  chroma/matting, Python libraries, repo audit) → synthesis →
  10 adversarial claim verifications → completeness critic.
- 6 live generation tests through the existing ImageAI CLI, plus a local
  slice → chroma-key → assemble proof of concept (Pillow + numpy only).

## Live test results

| Test | Result |
|------|--------|
| Nano Banana, one-shot 8-frame sheet | Works. Consistent character, clean 4×2 grid, uniform green. Pose progression is subtle; the two rows differ slightly in scale. |
| Nano Banana, edit → next frame | Excellent fidelity. Same design, pose changed as instructed, shadow removed on request. Confirms the edit-chain hypothesis. |
| GPT Image 2, edit → next frame | Excellent fidelity. Both models can drive an edit-chain pipeline. |
| GPT Image 2, "transparent" via prompt | Fails. The model paints a literal checkerboard; no alpha channel. Real alpha needs the API `background=transparent` parameter. |
| Nano Banana, reference → full sheet | Character preserved, but pose progression is unreliable and shadows return. Per-frame regeneration and culling tools are required. |
| Local proof of concept | Sheet slice + YCbCr-style key + despill + union-bbox crop + GIF/APNG assembly all work with shipped libraries. No green fringe. |

## Key verified facts

- **No Gemini image model emits alpha.** Green-plate prompting + local keying
  is the documented workaround. Never write "transparent" into a Gemini
  prompt — it paints a checkerboard.
- **gpt-image-2 gained `background=transparent` on 2026-08-20 (API preview).**
  The repo caps table (`providers/openai.py` `supports_transparent_bg: False`)
  is now stale. The preview has known defects: opaque alpha 252–254, halo
  edges. Post-process with threshold + defringe.
- **Veo 3.1 `last_frame` is wired in `veo_client.py`.** Same-image first/last
  conditioning produces loops. Caveat: `last_frame` works only with 8 s
  durations today, and seamlessness is a technique, not a guarantee.
- **Refuted claim (corrected):** rembg's onnxruntime moved behind extras
  (`rembg[cpu]`); base install pulls scipy/scikit-image/pymatting; the default
  model is now `bria-rmbg` (~1 GB, CC BY-NC — paid license for commercial
  use). Pin a permissive model explicitly.
- **Refuted claim (corrected):** Pillow raises `ValueError` on explicit
  MEDIANCUT/MAXCOVERAGE for RGBA (no silent fallback). Quantize flattened
  RGB and carry alpha separately. `Dither.ORDERED` is unimplemented — a Bayer
  pass must be in-house.
- **License traps:** libimagequant (GPLv3-or-commercial), CorridorKey
  (CC BY-NC-SA, no repackaging, uv-only, 6–8 GB VRAM), bria-rmbg (paid
  commercial), LPC art (GPL3/CC-BY-SA). All must stay optional or bridged.
- **Repo audit:** no every-N frame extractor, no chroma-key code, no
  quantization pipeline exist today. FFmpeg management, Veo/Omni clients,
  transparent-canvas compositing, MediaPipe segmentation (runtime-installed),
  and the VideoProject persistence pattern all exist and are reusable.
- **Broadest export compatibility:** uniform grid PNG + TexturePacker-style
  JSON hash + Aseprite-style JSON covers essentially every engine. Godot
  needs a generated `.tres` (no native JSON atlas import).

## Recommended pipeline (from synthesis)

Two generation routes over one shared processing spine:

- **Route A (video, flagship):** character image → chroma-plate prep
  (Nano Banana edit → flat green) → LLM action cards → Veo/Omni
  image-to-video clips → every-N frame extraction → key/clean → export.
- **Route B (image, cheap iteration):** one-shot multi-frame sheets (sliced)
  or iterative edit-chaining; gpt-image `background=transparent` variant
  skips keying.

Phasing: Phase 1 = core skeleton without keying (brief in → sheet out, frames
may stay green). Phase 2 = keying + image route + CLI. Phase 3 = pixel-art
conversion + engine exporters. Phase 4 = advanced items by demand.
The full recommendation, risks, and defaults are in the selector page.

## Next step

1. Open `Plans/2026-08-24-sprite-tab-feature-selector.html` in a browser.
2. Select features, answer the open questions.
3. Press **Copy selections as Markdown** and paste the result into a Claude
   session. The selections drive the design doc and the phase plan.
