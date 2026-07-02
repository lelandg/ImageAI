# The Fifth Fox — a fable about Fable 5

**Created:** 2026-07-02 · single-page Aesop-style comic built entirely with the ImageAI CLI
(layout engine + Nano Banana Pro), as a dogfooding run of the `--layout-*` pipeline from WSL.

## Story

A workshop of clever foxes makes a fifth — a fox that tells tales. The forest gathers to
listen; the Eagle King (stars-and-stripes heraldry) decrees it SILENCED — June 12–30; the
forest goes gray for eighteen days; the decree crumbles and the fox returns to a bigger
crowd, telling the tale of its own banishment.

**Moral:** *Silence a storyteller, and you only write its best chapter.*

## Files

- `fable5.iaibundle` — **portable project** with all 7 panel images embedded; open this
  in ImageAI on any machine
- `fable5.json` — layout project (US Comic portrait, 300 DPI, 8 regions + 7 overlays);
  references panel art in the local images dir (`~/.config/ImageAI/images/fable5_*.png`)
- `fable5.png` / `fable5.pdf` — exports
- Panel art: 7 × `gemini-3-pro-image-preview` (Nano Banana Pro)

Multi-line captions use explicit `\n` breaks at phrase boundaries; the moral is a
body-less `sfx` overlay centered in the scroll's blank oval at (1007, 2767).

## Pipeline used

1. `--layout-design` (Anthropic designer) → page grid, captions, decree overlay
2. Injected 7 style-locked image prompts (shared Aesop-woodcut style block, "no text in image")
3. `--layout-fill --provider google -m gemini-3-pro-image-preview` — 7/7, no failures
4. Converted caption text regions → `caption` overlays (parchment boxes); moral → body-less
   `sfx` overlay centered on the scroll; decree restyled as rotated red stamp
5. `--layout-export` to PNG + PDF

## Renderer bugs found & fixed (core/layout/qt_renderer.py, uncommitted)

1. **Overlay text vanished on export** — `QGraphicsTextItem(text, parent=body)` doesn't
   transfer C++ ownership in PySide6/Shiboken; the child is deleted at the next GC.
   Fix: explicit `setParentItem()` (which does transfer ownership).
2. **Last line of overlay text clipped** — body sized via `QFontMetricsF.boundingRect`
   but text laid out by `QTextDocument` (different wrap + 4px doc margins). Fix: size the
   body from the text item's own document (`idealWidth`/`size()`), margin 0; also honor
   `align` and bold weights in overlay text styles.

Suite: 472 passed after both fixes.

## Follow-up ideas

- Omni video: the fox telling the tale, camera pulling back through the five scenes,
  narrated fable VO with baked-in audio (`--video --video-provider omni`, refs from panel art)
