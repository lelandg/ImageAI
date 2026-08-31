# Final whole-branch review — sub-project 4 (pixel-art profile)

**Reviewer:** final-px (senior code reviewer, read-only)
**Range:** `c3aa66c..5549d49` (9 commits)
**Date:** 2026-08-29
**Method:** read in passes — plan + design spec, then `core/sprite/pixelart.py` in full, then the
consumed contracts (`pipeline.py`, `project.py`, `keying.py`, `stabilize.py`), then both test
modules, then live probes. No subagents were dispatched. The working tree, index, HEAD and
branches were not modified.

**Verification actually run (not claimed):**

| Check | Command / probe | Result |
|---|---|---|
| Import graph | `import core.sprite` in a fresh interpreter | 2.75 s; `torch`/`torchvision`/`PySide6`/`google.genai`/`core.video`/`core.upscaling` **all absent** (`cv2` present, pulled by sub-project 3's `keying`, pre-existing) |
| Registration | `STAGE_RUNNERS["pixel"] is run_pixel_stage`, `STAGE_SETTINGS["pixel"] is pixel_stage_settings`, `STAGE_CODE_VERSION["pixel"]` | `True`, `True`, `2` |
| Fingerprint isolation | mutate `locked_palette` / `dither` / `cell_size` / `stabilize.anchor`, recompute all 7 stage fingerprints | palette → `['pixel']`; dither → `['pixel']`; cell → `['pixel']`; anchor → `['stabilize','hd','pixel']` (correct: anchor cascades through the upstream fingerprint) |
| 1-colour palette × every dither | `quantize_to_palette(grey, ["#123456"], d)` for all 5 modes | all return `(18,52,86,255)`; no raise, no divide-by-zero |
| All-transparent frame | `build_shared_palette` / `quantize_to_palette(..., "floyd")` | `[]` / all zeros — no crash |
| Floyd across an alpha hole | opaque‖transparent‖opaque row, b/w palette | `[255,0,255, 0,0,0, 255,0,255]`, alpha preserved — no visible bleed on this case |
| Exact multiple / off-by-one | `integer_fit_scale((256,256),(64,64))`, `((65,64),(64,64))` | `4`, `2` (65×64 → 33×32 content in a 64×64 cell) |
| Focused tests | `pytest tests/sprite/test_pixelart.py tests/sprite/test_pipeline_pixel.py -q` | **59 passed in 2.60 s** |
| Path guard | `pytest tests/test_no_hardcoded_paths.py -q` | 3 passed |

---

## Plan/spec alignment — verdict + deviations

**Verdict: aligned.** Every symbol design §4.4 names exists with the design's signature:
`integer_fit_scale` (pixelart.py:58), `fit_pad_integer` (:78), `resolution_check` (:99),
`build_shared_palette` (:176), `quantize_to_palette` (:236), `bayer_matrix` (:144). The palette-lock
rule of §4.4 ("`palette_lock` on + `locked_palette` exists → new frames map to it; rebuild only on an
explicit action") is implemented exactly by `ensure_palette` (:294) / `rebuild_palette` (:282), with
`remap_to_locked` (:277) as the Aseprite "Remap" entry point.

§2 fields are all read and none added here: `cell_size`, `binary_alpha`, `alpha_threshold`,
`defringe_px`, `palette_size`, `dither`, `palette_lock`, `locked_palette`, plus sub-project 1's
`upscale_small` / `upscale_method` (project.py:152-164). §2 `SheetMeta.palette` needs no code in this
sub-project — `SpriteProject.sheet_meta` (project.py:545) copies `locked_palette`, which
`ensure_palette` fills; `test_sheet_meta_pixel_carries_locked_palette` pins it.

§4.1 registration is correct and verified live: `register_stage("pixel", run_pixel_stage,
settings_fn=pixel_stage_settings, code_version=2)` at pixelart.py:397, reached because
`core/sprite/__init__.py:85` imports `pixelart` after `.pipeline`. Version 2 correctly invalidates
sub-project 1's `identity_runner` cache (registered at version 1, pipeline.py:477).

§1.2 fingerprints are correct **and correctly scoped** — the probe above shows a palette, dither or
cell change re-runs `pixel` and nothing else, and an anchor change cascades from `stabilize` down
(the pixel stage anchors with `project.stabilize.anchor`, so that cascade is required, not a leak).
Note `pixel_stage_settings` (pixelart.py:310) returns `asdict(profile)` where sub-project 1's
placeholder returned `{"profile": to_dict(), "anchor": ...}` (pipeline.py:242); the dropped explicit
`anchor` key is safe because the upstream `stabilize` fingerprint already hashes it.

**Deviations recorded in the plan (1–12): all justified, all match the code.** Deviation 12
(`check(token)`) landed in d362fd6 and is verified at pixelart.py:344, :351, :371.

**Deviations that landed but are NOT recorded** (see Minor 11): `_reset_dir(out_dir)` in place of
`mkdir(exist_ok=True)`; `anchor_offset` delegating to `stabilize.anchor_offset`; `palette_to_hex`
delegating to `keying.rgb_to_hex`; and the extra test
`test_pixel_stage_second_run_with_fewer_frames_removes_stale_output`.

**Ledger ruling to confirm — the `pixel.json` manifest vs. the AGENTS.md sidecar rule: CONFIRMED,
compliant.** The sidecar rule covers *generated images* (final deliverables). `stages/` is cache:
every sibling runner (`key_runner`, `cleanup_runner`, `alpha_runner`, `stabilize_runner`,
`hd_runner`, pipeline.py:360-468) writes PNGs and no sidecar at all. One `pixel.json` per action is
strictly more provenance than its siblings, is not a per-frame sidecar, and is invisible to
`list_frames` (which globs `*.png` only, pipeline.py:145). No conflict.

**Other project rules:** images are integer-box-filtered and padded on a transparent canvas, never
cropped, never distorted, never silently upscaled (pixelart.py:78-94, :99-139) — compliant. No
hand-built paths; the runner writes only under the `out_dir` the pipeline hands it; the path guard
passes. No PySide6/torch/`core.video` at import — verified live.

---

## Strengths

- **The Pillow traps are handled and pinned by a regression test, not just a comment.** The module
  docstring (pixelart.py:1-12) names all three; `test_pillow_mediancut_raises_on_rgba_but_our_path_does_not`
  asserts both that Pillow raises on RGBA *and* that this module's path does not. That test will
  catch a future refactor that "simplifies" back into the trap.
- **The shared `scale` for the whole action** (pixelart.py:347) is the right call and the reason the
  animation cannot jitter. It is the single most important design decision in the module and it is
  documented where it is made.
- **Palette built from the *fitted, binary-alpha* frames** (pixelart.py:365), not the sources — so
  the palette describes the pixels that actually ship, and fringe blends never enter it. Reinforced
  by `PALETTE_ALPHA_MIN` (:43).
- **`nearest_palette_indices` is exact, and the exactness claim is true.** All intermediates stay
  integers below 2²⁴, which float32 represents without rounding; the chunked path is proven
  equivalent to the unchunked one by `test_nearest_palette_indices_chunks_agree`.
- **Deterministic, engine-friendly palette order** — luma sort with an RGB tiebreak (`_luma_key`,
  :171) makes the output independent of MEDIANCUT internals, which is what sub-project 6's Aseprite
  palette chunk needs.
- **Every warning is both logged and pushed through `progress`** (pixelart.py:387-389) *and*
  persisted to `pixel.json`, so a cached run can still show it. That third channel is the part most
  implementations forget.
- **Cancellation, cache reset and the empty-input case are all tested**, including the
  fewer-frames-on-re-run case that `_reset_dir` exists to fix.

---

## Issues

### Critical

None.

### Important

**I1 — `palette_lock=False` with more than one action: permanent cache thrash, and a
`SheetMeta.palette` that contradicts the pixels on disk.**
`core/sprite/pixelart.py:294-305` (`ensure_palette`), `:282-291` (`rebuild_palette`),
`:310-320` (`pixel_stage_settings`), `core/sprite/project.py:545` (`sheet_meta`).

*What.* `locked_palette` is project-wide (one `OutputProfile`) but `rebuild_palette` is called
per-action. With the lock off, action B's run overwrites the palette action A was quantized with.
Because `locked_palette` is inside `asdict(profile)`, that overwrite also changes action A's
fingerprint, so A is never cached again. Measured directly (two actions, red and blue, `palette_lock=False`):

```
A#1 cached_before=False  palette_now=['#C82828']
B#1 cached_before=False  palette_now=['#2828C8']
A#2 cached_before=False  palette_now=['#C82828']     <- never caches
B#2 cached_before=False  palette_now=['#2828C8']     <- never caches
sheet_meta("pixel").palette == ['#2828C8']           <- A's PNGs are #C82828
```

With `palette_lock=True` (the default, project.py:161 and `default_profiles()` project.py:195-198)
everything is stable and correct — same probe, both actions cached on run 2, one palette. So this is
gated behind a non-default toggle.

*Why it matters.* Sub-project 6 writes the Aseprite palette chunk from `SheetMeta.palette`. Under the
unlocked setting that chunk is wrong for every action but the last one processed — a sheet whose
declared palette does not contain its own pixels. Sub-project 5b exposes the lock as a UI checkbox,
so a user can reach this without editing JSON. Secondary effect: every pixel stage re-runs on every
pipeline pass, which is the exact cost §1.2's cache exists to avoid.

*Sub-case — palette loss.* Same gate (lock off): if an action's fitted frames are all transparent
(e.g. keying removed everything), `build_shared_palette` returns `[]` and `rebuild_palette:287` sets
`profile.locked_palette = None`, destroying the palette every earlier action was quantized with.
Verified: `build_shared_palette([fully transparent]) == []`.

*Fix (pick one, decide before 5b/6 land).* (a) Make the unlocked palette per-action: keep it out of
`profile.locked_palette`, record it in `pixel.json` only, and have sub-project 6 read the per-action
manifest — `SheetMeta.palette` then honestly reports `None` when no shared palette is locked; or
(b) keep the current write but drop `locked_palette` from the fingerprint when `palette_lock` is
False, and have 5b rebuild across *all* actions' frames so "unlocked" still means one palette per
project (which is what design §4.4's "one shared palette" implies). Either way, guard
`rebuild_palette` against clobbering a non-empty palette with an empty result.

**I2 — the stage raises bare `ValueError` for bad profile config, where every sibling runner raises
`PipelineError` with a `user_message`, and logs nothing first.**
`core/sprite/pixelart.py:183` (reached via `:286`), `:243`, `:121`.

*What.* Three reachable configuration failures escape as un-annotated `ValueError`:
`palette_size` outside 1..256 (`build_shared_palette:182-183`), `dither` not in `DITHER_MODES`
(`quantize_to_palette:242-243`), `upscale_method` not in `UPSCALE_METHODS` (`upscale_then_fit:120-121`).
`OutputProfile.from_dict` (project.py:172-188) coerces types but validates none of these ranges, so a
hand-edited or older `project.iasprite.json` reaches them. `run_pipeline` (pipeline.py:551) does not
wrap runner exceptions, and `PipelineError.user_message` (pipeline.py:73-78) is the contract every
other runner uses for a user-facing failure (`extract_runner:348`, `:353`; `stabilize_runner:421`;
`hd_runner:453`).

*Why it matters.* Sub-project 5b's processing panel and sub-project 7's CLI will write their error
handling against this API. A raw `ValueError` gives them no `user_message` to show and, unlike every
other stage failure, is not logged before it is raised — which also misses the AGENTS.md rule that
every user-facing error is logged. Retrofitting the contract after 5b's panel exists is the painful
order.

*Fix.* Validate the profile once at the top of `run_pixel_stage` (after the enabled check, ~line 335):
check `palette_size`, `dither` and `upscale_method`, `logger.error(...)` the offending value, and
raise `PipelineError` with a message naming the profile field. The helper functions keep their
`ValueError`s for direct callers.

### Minor

1. **`ANCHORS` at pixelart.py:37 is dead and duplicates `stabilize.ANCHORS` (stabilize.py:28).**
   Grep confirms no use inside the module (the only occurrence is the definition) and no importer
   anywhere in the repo. Two copies of the same tuple will drift. Delete it, or re-export
   `stabilize.ANCHORS` under the name.
2. **`no_progress` is imported and never used** (pixelart.py:30). The plan's Task 1 note kept the
   header stable for later tasks; this one never found a consumer.
3. **The module imports the private `pipeline._reset_dir`** (pixelart.py:30) from another module.
   `check` beside it is public. Promote `_reset_dir` to `reset_dir` in `pipeline.py` (or add a public
   alias) — sub-projects 5b/6/7 will want the same helper and will copy this pattern.
4. **Peak memory holds two full frame lists.** `frames` (full-size source RGBA, pixelart.py:342-346)
   is still live through the write loop at `:370-377`, alongside `fitted`. For a 24-frame action of
   1024×1024 that is ~100 MB of avoidable retention. `frames.clear()` (or reuse the slot) after the
   fit loop at :363 halves it; `fitted` must stay, since `ensure_palette` needs all of it.
5. **Progress counts 1..N twice inside one stage** (`:363` fit loop, then `:377` write loop). A GUI
   bar driven by `done/total` fills, then restarts. Consider `2 * total` as the denominator, or
   `index + 1 + total` in the second loop.
6. **`resolution_check` tells the user to do something they cannot do** (pixelart.py:109-110):
   *"Run the pipeline with upscale_small=True"*. `upscale_small` is an `OutputProfile` field
   (project.py:163) that 5b exposes as a checkbox — it is not a pipeline argument. Reword to name the
   pixel profile setting. (`test_resolution_check_warns_when_smaller_in_both_axes` asserts the
   literal substring `upscale_small=True`, so the test moves with the text.)
7. **The `upscale_small` branch bypasses the shared `scale`** (pixelart.py:353-354): `upscale_then_fit`
   re-derives its own factor while the other branch forces `scale=scale` (`:358`). Harmless today
   because `stabilize`'s `crop_and_pad` gives every frame of an action the same size, so all frames
   take the same branch. It is a latent size-pop if that guarantee ever changes; a comment stating
   the dependency, or threading `scale` through, would close it.
8. **Floyd's transparent fill does not fully stop error travel** (pixelart.py:252-260). Transparent
   pixels are set to `pal[0]`, which quantizes with zero error *only while the accumulated diffusion
   into them is zero*. Error entering a transparent region from an opaque neighbour still propagates
   through it and can re-enter opaque pixels further along the scan.
   `test_quantize_floyd_transparent_pixels_do_not_bleed` only covers transparent-**before**-opaque,
   which the scan order makes trivially safe. My opaque‖transparent‖opaque probe showed no visible
   artifact, so this is cosmetic — but the test claims more than it proves.
9. **`pixel.json` omits `palette_lock` and `palette_size`** (pixelart.py:379-385). 5b cannot tell from
   the manifest whether the palette was rebuilt this run or reused from the lock. Two more keys.
10. **Naming mismatch with the design, not a behaviour mismatch.** Design §4.4 documents
    `integer_fit_scale` as "largest integer downscale that fits"; the implementation returns the
    *smallest* factor whose result fits (pixelart.py:58-64). Same output (largest resulting content);
    the code's docstring is the accurate one. Worth a one-line correction in the design so sub-project
    6/7 authors do not read it backwards.
11. **The plan's Deviations section is incomplete after the truth-up** (`5549d49` added only deviation
    12). Missing: `_reset_dir(out_dir)` replacing `mkdir(exist_ok=True)` (ledger ruling, landed at
    pixelart.py:338); `anchor_offset` delegating to `stabilize.anchor_offset` (ledger ruling, landed
    at :67-75); `palette_to_hex` delegating to `keying.rgb_to_hex` (Task 4 ruling, landed at :166-168);
    and the added test `test_pixel_stage_second_run_with_fewer_frames_removes_stale_output`
    (test_pipeline_pixel.py:162). The plan is the record 5b/6/7 read.
12. **No coverage for integer-scale waste.** A 65×64 source into a 64×64 cell reduces to 33×32 —
    26 % of the cell — with no warning, because `resolution_check` fires only when the source is
    smaller in *both* axes (pixelart.py:103). This is inherent to integer-only scaling and is the
    design's intent, but the `scale` is now recorded in `pixel.json`, so 5b could surface a
    "content covers N % of the cell" hint cheaply. Worth a note to 5b rather than a code change here.

---

## Deferred-minor triage

- **`Task 4: pyright false positive at pixelart.py:199 (getpalette Optional; quantize always yields P)`
  → LEAVE.** `Image.quantize` always returns a `P`-mode image, so `getpalette()` cannot be `None` on
  this path; a runtime `or []` would add a branch no test can reach. If the repo ever gates CI on
  pyright, the correct fix is a narrowing `assert flat is not None` on line 199, not a fallback.
- **`Task 5: no 1-colour palette × floyd test` → LEAVE.** I executed the case: all five dither modes
  with a 1-colour palette return that colour, no raise and no divide-by-zero (`palette_spread`
  short-circuits to `0.0` at pixelart.py:227-228, so the Bayer offset is zero and the path collapses
  to `none`). The behaviour is also covered indirectly by
  `test_quantize_output_colors_are_subset_of_palette` (all five modes) and `test_palette_spread` (the
  `len < 2` branch). Adding the case is 3 lines and harmless, but it is genuine polish, not a gap.
- **Ledger ruling `per-action pixel.json instead of per-frame sidecars — final review to confirm`
  → CONFIRMED compliant** (reasoning in "Plan/spec alignment" above). No action.
- **Ledger ruling `run_pixel_stage MUST call pipeline._reset_dir` → LANDED and tested**
  (pixelart.py:338; `test_pixel_stage_second_run_with_fewer_frames_removes_stale_output`). No action,
  except recording it in the plan's Deviations (Minor 11).
- **Ledger ruling `anchor_offset wraps stabilize.anchor_offset` → LANDED** (pixelart.py:67-75, with
  the oversize check kept ahead of the delegation so the plan's argument order and both `ValueError`
  cases still hold). No action, except Minor 11.
- **Ledger ruling `palette_to_hex delegates to keying.rgb_to_hex` → LANDED** (pixelart.py:168; clamping
  now comes from `keying.rgb_to_hex`, keying.py:75-77). No action, except Minor 11.
- **Ledger ruling `Task 7 inline cancel checks → pipeline.check` → LANDED** (pixelart.py:344, :351,
  :371; recorded as deviation 12). No action.

---

## Assessment

**Ready for downstream sub-projects: yes, with I1 and I2 scheduled before 5b's processing panel and
6's palette chunk are written.** The maths, the Pillow workarounds, the cache fingerprint scoping and
the import discipline are all correct and independently verified, and the `run_pixel_stage` /
`pixel.json` / `locked_palette` surface that 5b, 6 and 7 consume is stable enough to build against
today — nothing here forces a rewrite of those consumers. I1 and I2 are both about what happens off
the default path (the palette-lock toggle, and a malformed profile), which is precisely the kind of
contract that is cheap to settle now and expensive to retrofit once a GUI panel and a CLI flag are
written against it.
