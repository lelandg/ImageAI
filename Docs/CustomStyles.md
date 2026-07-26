# Custom Styles Guide

> Derive a reusable visual style from your own reference images, then apply it
> across image generation, video, and publication layouts — no matter which
> provider you're using.

## Overview

A **style** is a small, named, reusable definition of "how things should
look." You build one by feeding ImageAI a handful of images that share a
look — a comic inking style, a product-photography lighting setup, a
painterly palette — and a vision LLM analyzes them and writes a style
description for you. The style is a hybrid object:

- **`prompt_text`** — a short, editable style instruction that gets appended
  (or prepended) to every prompt you apply the style to.
- **Reference images** — copies of the images you supplied, stored with the
  style.
- **Exemplars** — up to 3 of those reference images, starred as
  representative examples. Providers that accept multiple reference images
  (Google Gemini, OpenAI's `gpt-image-*` family) get these attached alongside
  your own references, so the model sees the look, not just a text
  description of it.

Once saved, a style can be applied to any generation — in the GUI or the
CLI — with a single picker or flag. It works the same way in image
generation, the Video tab, and layout region-filling.

## Creating a style in the GUI

1. Open the **Generate** tab. Next to the prompt field is a **Style** picker
   (`Style: [None ▾]  Manage…  ☐ Smart merge`). Click **Manage…** to open the
   **Style Manager**.
2. Click **New**, give the style a name, and it's created empty and selected
   in the list.
3. Add reference images with **Add Files…** or **Add Folder…** (PNG, JPG,
   JPEG, WebP, BMP). Each one appears as a thumbnail in the reference grid.
4. Check the boxes on up to 3 images to mark them as **exemplars** — the ones
   sent as reference images to providers that support it. If you check more
   than 3, only the first 3 are kept.
5. Pick a **Vision LLM** (OpenAI, Anthropic, or Gemini) and model, then click
   **Analyze Images**. ImageAI sends your images (in batches, if you have
   more than 8) to the LLM, which extracts the shared style — rendering
   medium, palette, lighting, composition, texture, line work, mood, and
   anything to avoid — and proposes a `prompt_text` summarizing it. This runs
   in the background; watch the analysis console at the bottom of the dialog
   for progress.
6. Review the proposed **style prompt text** and the read-only **derived
   descriptor**. Edit the prompt text if you want to tweak the wording — it's
   just a text field.
7. Choose **Placement**: `suffix` (default — style text is appended after
   your prompt) or `prefix` (style text comes first).
8. Click **Save Style**.

Analysis is non-destructive: nothing is written until you click Save, so you
can re-analyze or hand-edit the text as many times as you like first.

### Applying a style

Back on the Generate tab (or the Video tab, which has the same picker),
select your style from the **Style** dropdown. It stays applied to every
generation until you switch it back to **None**. Optionally check **Smart
merge** (see below).

If you're using your own reference image(s) for that generation (an edit
reference, a composite reference, etc.), your reference always wins — the
style is applied as **text only** so it doesn't push out or compete with the
reference image you actually chose. A status message says so when this
happens.

## Creating a style from the CLI

```bash
# Derive a style named "Watercolor" from a folder of reference images
python main.py --style-create "Watercolor" --style-images ./refs/watercolor/

# Or from explicit files / globs
python main.py --style-create "Neon Noir" \
    --style-images shot1.png shot2.png "refs/noir_*.jpg"

# Pick the vision LLM used for analysis (default: your configured LLM)
python main.py --style-create "Product Shot" --style-images ./refs/ \
    --style-llm-provider openai --style-llm-model gpt-4o
```

`--style-images` accepts any mix of files, directories, and glob patterns.
The style is derived, its first 3 reference images become the exemplars, and
the new style's id prints to stdout (handy for scripting). Progress and
status messages go to stderr, so stdout stays script-friendly.

### Managing styles

```bash
python main.py --style-list                     # list all saved styles
python main.py --style-show "Watercolor"         # full JSON record
python main.py --style-delete "Watercolor"       # delete (and its images)
```

### Applying a style

```bash
# Image generation
python main.py -p "a lighthouse at dusk" --style "Watercolor" -o lighthouse.png

# Fuse the prompt and style with an LLM instead of plain concatenation
python main.py -p "a lighthouse at dusk" --style "Watercolor" --style-smart -o lighthouse.png

# Video (text-only — see the provider table below)
python main.py --video -p "waves rolling in" --style "Watercolor" -o waves.mp4

# Layout fill (text-only, applied to every region's prompt)
python main.py --layout-fill comic.json --style "Neon Noir"
```

`--style NAME` matches by style name or id, case-insensitively. An unknown
name exits with code 2 and lists the styles that *are* available. `--style-smart`
only applies to image generation (see Smart merge below); it's silently
ignored elsewhere.

## Sharing a style (export / import)

Styles bundle into a single zip — the style definition plus its reference
images — so you can hand one to a teammate or move it between machines.

**GUI:** in the Style Manager, select a style and click **Export…** to save a
`.zip`, or **Import…** to load one someone sent you (a name collision gets a
fresh id automatically, so importing never overwrites an existing style).

**CLI:**

```bash
python main.py --style-export "Watercolor" -o watercolor.zip
python main.py --style-import watercolor.zip
```

## Per-provider behavior

| Surface | Text style applied | Exemplar images attached |
|---|---|---|
| Image generation — Google Gemini | Yes | Yes, up to the model's reference limit (3–14 depending on model) |
| Image generation — OpenAI `gpt-image-*` | Yes | Yes, up to 10 total references |
| Image generation — Stability AI | Yes | No (text only) |
| Image generation — Local Stable Diffusion | Yes | No (text only) |
| Video (Omni / Veo, either provider) | Yes | No (text only) |
| Layout fill (per-region prompts) | Yes | No (text only) |

Exemplars are always added *after* any reference images you already supplied
for that generation — your own references take priority and are never
displaced. If a provider's reference limit is reached, extra exemplars are
silently dropped (logged as a warning) rather than failing the generation.

### Smart merge (image generation only)

By default, applying a style plainly concatenates your prompt and the
style's `prompt_text` (style text goes before or after your prompt depending
on the style's **Placement**). Checking **Smart merge** (GUI) or passing
`--style-smart` (CLI) instead makes one extra LLM call that rewrites your
prompt and the style together into a single, more coherent instruction.

Smart merge can never fail your generation: if the LLM call errors, times
out, or returns something unusable, ImageAI logs a warning and falls back to
the plain concatenation automatically. It's only available for image
generation — video scenes and layout fill always use plain concatenation.

## Storage and provenance

Styles live outside the repo, in your platform's ImageAI user data directory:

- **Windows:** `%APPDATA%\ImageAI\styles\`
- **macOS:** `~/Library/Application Support/ImageAI/styles/`
- **Linux:** `~/.config/ImageAI/styles/`

Inside: `styles.json` (the index of all styles) and one `<style-id>/refs/`
folder per style holding its downscaled reference images.

Every generated image's `.json` sidecar records a `style_applied` block
(style id/name, whether smart merge was used, how many exemplars were
attached/dropped) when a style was used — so you can always tell which style
produced a given image. The **prompt shown in History** is always your
original, un-styled prompt; the style is provenance metadata, not something
that rewrites what you typed.

## Troubleshooting

**"No `<provider>` API key configured"** when creating or analyzing a style —
style derivation needs a vision-capable LLM. Set an API key for the provider
you picked (OpenAI, Anthropic, or Google) in **Settings** (GUI) or with
`--set-key --provider <provider>` (CLI), then try again.

**"Style not found: `<name>`. Available: ..."** — `--style` matches by exact
name or id (case-insensitive). Run `--style-list` to see what's actually
saved, or check for a typo.

**"No images found in: ..."** (CLI `--style-create`) — none of the paths,
directories, or globs passed to `--style-images` resolved to a supported
image file (`.png .jpg .jpeg .webp .bmp`). Double-check the path.

**A reference image doesn't get attached even though the style has
exemplars** — either the provider/model doesn't accept extra reference
images (Stability AI, Local SD, video, layout — see the table above), or an
active reference image of your own is already occupying that slot (your
reference always wins; the style still applies as text). Missing files on
disk are skipped with a logged warning rather than failing the generation.

**Style analysis fails partway through** — with many reference images,
analysis runs in chunks; if any chunk's LLM call fails or returns
unparseable output, the whole analysis is aborted and nothing is saved (no
half-derived styles). Check the analysis console for the specific error and
retry.
