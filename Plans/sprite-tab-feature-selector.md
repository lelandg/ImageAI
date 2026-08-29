# Sprite Tab — feature selections
_Generated from Plans/2026-08-24-sprite-tab-feature-selector.html_

## Selected features (39 of 60)

### Source & Character Setup
- [x] `character-source-import` — Character Source Import & Normalization (core, effort S)
- [x] `chroma-plate-prep` — Chroma Plate Preparation (core, effort M)
- [x] `sprite-size-presets` — Sprite Size & Canvas Presets (core, effort S)
- [x] `character-turnaround-pack` — Character Turnaround Reference Pack (high, effort M)
- [x] `chroma-prompt-injection` — Chroma-Ready Prompt Injection (high, effort S)

### AI Animation Generation
- [x] `action-card-generator` — AI Action-Card Generator with Genre Presets (core, effort M)
- [x] `video-route-rendering` — Per-Action Video Clip Rendering (Veo/Omni) (core, effort L)
- [x] `loop-closure-conditioning` — Loop-Closure Conditioning (FIRST&LAST) (high, effort M)
- [x] `image-route-frame-generation` — Image-Model Frame Generation (Sheet or Edit-Chain) (high, effort L)
- [x] `clip-timing-hints` — Per-Action Clip Timing Hints (high, effort S)
- [x] `omni-conversational-refine` — Conversational Per-Action Refine (nice, effort S)

### Frame Processing
- [x] `frame-extractor` — Frame Extractor (Every-N / Target-FPS) (core, effort S)
- [x] `chroma-keyer` — YCbCr Color-Distance Chroma Keyer (high, effort M)
- [x] `despill-edge-cleanup` — Despill & Edge Cleanup Suite (high, effort M)
- [x] `ml-background-removal` — ML Background Removal (Local, Model-Gated) (high, effort M)
- [x] `binary-alpha-threshold` — Binary Alpha Threshold (high, effort S)
- [x] `autocrop-stabilize` — Union-Bbox Auto-Crop & Uniform Cell Re-Pad (core, effort M)
- [x] `frame-dejitter` — Sub-Pixel Frame De-Jitter (high, effort S)

### Pixel-Art Conversion
- [x] `fit-pad-integer-downscale` — Fit-and-Pad Integer Downscale (high, effort S)
- [x] `shared-palette-quantization` — Shared-Palette Quantization (high, effort M)
- [x] `dither-selector` — Dither Mode Selector (Default: None) (high, effort S)

### Sheet Assembly & Export
- [x] `grid-sheet-export` — Uniform Grid Sheet Export (core, effort M)
- [x] `aseprite-json-export` — Aseprite-Compatible JSON Export (core, effort S)
- [x] `texturepacker-json-export` — TexturePacker-Style JSON Export (Hash + Array + Pixi Animations) (high, effort S)
- [x] `per-tag-png-export` — Per-Tag PNG Sequence Export with Filename Templates (core, effort S)
- [x] `gif-export` — Animated GIF Export (Safe Transparent Recipe) (core, effort M)
- [x] `godot-tres-export` — Godot 4 SpriteFrames .tres Export (high, effort M)
- [x] `engine-preset-picker` — Engine Export Preset Picker (high, effort S)
- [x] `sheet-import-slicing` — Sheet Import & Slicing (core, effort M)

### Editing & Preview
- [x] `animation-preview-player` — Animation Preview Player (core, effort M)
- [x] `frame-strip-manager` — Frame Strip Management (core, effort M)
- [x] `pixel-zoom-view` — Pixel-Perfect Zoom View (core, effort S)
- [x] `ai-frame-retouch` — AI Single-Frame Retouch (high, effort M)

### Project & Workflow Integration
- [x] `frame-metadata-model` — Internal Frame Metadata Model (core, effort S)
- [x] `sprite-project-persistence` — Sprite Project Save/Load with Provenance Sidecars (core, effort M)
- [x] `send-to-sprite` — Send to Sprite (Cross-Tab Handoff) (high, effort S)
- [x] `sprite-cli` — Sprite CLI Parity (high, effort M)
- [x] `batch-queue-cost-estimator` — Batch Queue with Status Console & Cost Estimate (high, effort M)

### Advanced/Later
- [x] `native-aseprite-writer` — Native .aseprite File Writer (later, effort M)

## Critic gaps to include as features
- [x] G1 — Pipeline-stage caching & non-destructive re-processing
- [x] G2 — Cancellation for in-flight generation & processing
- [x] G3 — Worker-thread + progress contract for the tab
- [x] G4 — Undo/redo model for frame edits
- [x] G5 — Keyboard-shortcut spec (Space, comma/period, Ctrl+Enter…)
- [x] G6 — Generation-failure & safety-filter handling (RAI refusals, 429s)
- [x] G9 — Import existing video / PNG sequence into the processing spine
- [x] G12 — Cost estimator price source + actual-spend ledger
- [x] G16 — Testing strategy: golden-file exporter tests + headless smoke tests
- [x] G17 — First-class HD soft-alpha path (skip pixel-art conversion)

## Open-question answers
1. Phase-1 route conflict: the catalog makes the Veo/Omni video route the Phase-1 flagship, but your request leans image-first ('Nano Banana Edit ... might even produce several frames', 'GPT Image 2 can produce animations too'). Which route ships in Phase 1 — video, image, or both? This decides most of Phase 1's cost and scope.
   - ANSWER: Veo/Omni
2. Is pixel-art conversion (quantization, binary alpha, integer downscale) the default output path, or an optional branch beside an HD soft-alpha sprite path? Your request named palettes/colors but not pixel art explicitly; defaults like binary-alpha-128 hinge on the answer.
   - ANSWER: Optional: Modern games might use HD or have options/modes for both. So we can generate both.
3. Sprite CLI is scheduled Phase 2, but the house rules treat CLI parity as expected for headless pipelines. Accept the deferral, or pull a minimal CLI (process+export, no generation) into Phase 1?
   - ANSWER: That's fine, but we should implement before PR.
4. What Python versions must ImageAI keep supporting? rembg pins >=3.11,<3.14 and the answer gates whether it can even be an optional extra.
   - ANSWER: >= 3.11 is fine. We can assume rembg will increase ceiling.
5. New hard dependencies to approve for Phase 1/2: scikit-image + scipy (de-jitter) vs an OpenCV phaseCorrelate-only fallback; and is promoting mediapipe from runtime-installed to a declared optional extra acceptable?
   - ANSWER: yes
6. Undo model: full command-stack undo for frame edits, or the cheaper 'non-destructive + snapshot on destructive ops' model? Affects the frame-strip and retouch designs from day one.
   - ANSWER: Cheaper
7. Content policy: is the tab allowed to send user photos of real people (or trademarked characters) to Veo/Gemini at all, or should it pre-warn/block? Determines the error-handling design and support burden.
   - ANSWER: Allow
8. Cost controls: should the batch queue require an explicit confirmation above a spend threshold (e.g. >$1 estimated), and should per-project actual spend be recorded in the SpriteProject?
   - ANSWER: No confirmation, but we can print a cost estimate per page of sprites &/or per sprite,  given the current settings. 
All projects should record cost per sprite since they may vary if I change settings in the middle of a project.
9. Default cell size 64x64 and default video length 8s at 720p — confirm, or prefer 4s veo-3.1-fast drafts as the default to cut iteration cost?
   - ANSWER: Defaults configured in dialog with default pickers, but edit all fields. Then save multiple configurations. Some may want full 720 x 720 sprites.
Omni is better, faster and generally cheaper. Use it by default.
10. Where should intermediates live and how long: keep raw clips + extracted frames forever in the project (re-processable, large) or offer auto-purge after export? Also confirm sprite_projects() gets added to the storage-migration journal.
   - ANSWER: Intermediates in a sibling of the generated folder. Auto-purge after export might be a good idea, but I want to keep all of mine, so it should be optional and a sticky preference. Then confirm when enabled, since it deletes files. Yes, support storage migration journal.

## Defaults
All proposed defaults accepted.

## General notes
This may be used to export individual frames. Not just animated sprites. Be flexible in supported resolutions. If anything add more for quality sprites.