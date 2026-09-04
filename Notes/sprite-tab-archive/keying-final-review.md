# Final whole-branch review — sub-project 3 (keying & cleanup)

**Range:** 15de017..0ba8e93 (11 commits) · **Branch:** feat/sprite-tab · **Date:** 2026-08-29
**Reviewer:** final-ky (read-only; no subagents; reviewed in passes — plan/spec, then
keying.py + matting.py, then pipeline.py + stabilize.py, then ml_install/requirements,
then tests, then live probes of the import graph and the numeric edge cases).

---

## Plan/spec alignment — verdict + deviations

**Verdict: aligned.** Every artefact the plan's File Structure names exists, every public
signature in spec §4.3 is present with the documented shape, and the four accepted Task 9
deviations are all sound. I verified the following by running them, not by reading:

| Check | Result |
|---|---|
| `import core.sprite` from a fresh interpreter | no `core.video`, `google.genai`, `PySide6`, `mediapipe`, `rembg` loaded |
| Stage registration | runs exactly once, via `pipeline.py`'s module-level `register_stage` block |
| Registered runners | `key_runner`, `cleanup_runner`, `alpha_runner`, `stabilize_runner`, `hd_runner` — no identity placeholders left except `pixel` (sub-project 4's) |
| `code_version` | key/cleanup/alpha/stabilize/hd all `2`; extract/pixel `1` — correct, cached frames rebuild |
| Downstream API present | `keying.binary_alpha`, `hex_to_rgb`, `key_frame`, `pick_key_color`, `ffmpeg_chromakey_preview`, `KeyingError`; `matting.difference_matte`, `ml_alpha`, `available_backends`, `MattingUnavailable`; `stabilize.dejitter`; `ml_install.sprite_ml_packages` |
| Fingerprints (§1.2) | an override change invalidates `key`→downstream; an unrelated `duration_ms` edit does not (`test_changed_override_changes_the_key_fingerprint`, `test_overrides_survive_the_stabilize_frame_sync`) |

**Deviations, all accepted and correct:**

1. **`keying.get_ffmpeg_path` lazy wrapper** (`keying.py:305-314`). Necessary and correct —
   `core.video.__init__` pulls in `google.genai`, and `pipeline.py` imports `keying` at
   module top. Verified: the isolation pin holds. It doubles as the monkeypatch seam the
   ffmpeg tests use.
2. **`from .stabilize import dejitter` placed after the `CancelToken`/`check` definitions**
   (`pipeline.py:84`, with the reason in a comment at :81-83). Genuinely required —
   `stabilize` imports those names back from `pipeline`.
3. **Override list sized off the extract stage, not `len(action.frames)`**
   (`pipeline.py:192-203`). This is the right call and the docstring explains why:
   `run_pipeline` rewrites `action.frames` from the *stabilize* output mid-run, so a
   settings function keyed on its length would read different counts before and after
   stabilize in the same pass and destabilise the `key` fingerprint on every run. I
   confirmed the index spaces line up (extract order == stabilize order; `crop_and_pad`
   and `dejitter` both preserve names and order).
4. **`core/sprite/__init__.py` untouched.** Correct — the `register_stage` calls live in
   `pipeline.py`, which `__init__.py` already imports. See Minor 5 on the export surface.

**Nested-vs-flat settings ruling:** the ledger's pre-flight recorded a MISMATCH and ruled
for the nested `{"stabilize": {...}}` shape. The delivered code went **flat** for
key/cleanup/alpha (`pipeline.py:206-226`) and **nested** for stabilize (`:229-230`). That is
inconsistent between sibling settings functions, but it is a deliberate, tested choice
(`test_pipeline.py:64-70` was updated for the flat key shape, `test_pipeline_keying.py`
asserts the nested stabilize shape) and the fingerprint is a hash of whatever JSON comes
back, so neither shape is more correct. Not worth churning now — see Minor 6.

---

## Strengths

- **De-jitter is correct, and I verified it end-to-end rather than trusting the tests.**
  I built three frames with known offsets, ran `dejitter`, and every output frame's alpha
  matched frame 0 exactly (mean abs diff 0.00). I then checked the sign convention on
  *both* backends independently: skimage returns `(-3.0, +2.0)` for a `+3,-2` displacement
  and the cv2 fallback returns `(-4.0, +3.0)` for `+4,-3`. Both correct, and they agree —
  the `-dy, -dx` negation on the cv2 path (`stabilize.py:221`) is right, which is exactly
  the kind of thing that is usually wrong.
- **`translate_rgba` premultiplies before warping** (`stabilize.py:224-236`) and un-premultiplies
  after. This is the correct way to resample RGBA and it avoids the dark halo that a naive
  `warpAffine` on straight alpha produces. Genuinely good.
- **The despill luminance restoration is right, and for the right reason.** `despill`
  clamps the key's dominant channel then adds the lost luma back as a *neutral* offset on
  all three channels (`keying.py:122-125`). I checked the weights: `_CB` and `_CR` each sum
  to exactly 0, so a neutral offset leaves (Cb, Cr) untouched — the spill is removed in
  chroma while luminance is preserved. Matches the plan prototype line for line.
- **`difference_matte` derives the correct formula** (`matting.py:138-151`): from
  `W = Fa + (1-a)` and `B = Fa`, `W - B = 1 - a`, so `a = 1 - mean(W - B)` and `F = B/a`.
  Correct, with a sane `1/255` floor.
- **Fingerprint discipline.** `cleanup_stage_settings` carries only the three morphology
  fields and `alpha_stage_settings` only the decontamination inputs, so a choke change
  rebuilds cleanup-and-later but not `key` — asserted directly in
  `test_cleanup_settings_change_only_cleanup_and_later`.
- **Tests assert real behaviour, not mocks.** `test_key_cleanup_alpha_stages_produce_keyed_rgba`
  checks that plate pixels reach alpha 0, interior pixels reach 255, and the subject colour
  survives at `(220,40,40)`. `test_hd_profile_keeps_soft_alpha_unless_binary_requested`
  checks the anti-aliased edge is preserved and then that it collapses to `{0,255}`. These
  would catch a real regression.
- **The optional extras are genuinely optional.** `matting._installed` uses `find_spec` and
  never imports; `mediapipe`/`rembg` load inside the backend functions. Verified in the
  import probe. `ml_install.py` is the single source of truth and a test pins
  `requirements-sprite-ml.txt` to it.
- **`rembg_model_dir` uses `get_data_paths().model_cache("rembg")`** with the matching
  `CACHE_OWNERS[Group.MODELS]` entry and a migration test — the cache moves with the
  storage root instead of being stranded. Exactly what the paths rule asks for.

---

## Issues

### Critical

None.

### Important

**I1. A bad key colour escapes `run_pipeline` as a bare `ValueError` — no `user_message`, no log line.**
`core/sprite/keying.py:261` · `core/sprite/pipeline.py:405` · `core/sprite/keying.py:328`

I ran this rather than inferring it. With `project.plate_color = "not-a-color"`,
`run_pipeline(..., upto="alpha")` raises:

```
ValueError -> Not a #RRGGBB color: 'not-a-color' | has user_message: False
```

**Why it matters:** every other failure mode in this sub-project raises `KeyingError` or
`PipelineError` carrying a UI-safe `user_message`, and sub-projects 5b and 7 will catch on
that contract. This path bypasses it and, because nothing logs, it also breaches the
AGENTS.md rule that every user-facing error is logged. The trigger is not exotic: 5b gives
the user a per-frame `key_color` override field and a plate-colour field, so a typo or a
pasted `rgb(0,200,0)` reaches here. `apply_overrides` (`keying.py:225`) has the same problem
via `float(value)` on a non-numeric `tolerance`/`softness` override.

**Fix:** wrap the three `hex_to_rgb` call sites (and the `float()` casts in
`apply_overrides`) so a parse failure is logged and re-raised as `KeyingError` naming the
offending value and frame index. `ffmpeg_chromakey_preview` should raise `KeyingError` for
consistency with the two failures already below it in the same function.

**I2. `dejitter` reads every frame into memory before writing any.**
`core/sprite/stabilize.py:252-256`

```python
images = []
for path in frames:
    ...
    images.append(np.asarray(Image.open(path).convert("RGBA")))
```

**Why it matters:** the algorithm only ever needs `images[0]`'s alpha (the reference) and
the frame currently being warped — every frame is registered against frame 0, never against
its predecessor. Holding all N is therefore unnecessary, and it is the peak-memory point of
the whole pipeline: a 300-frame action cropped to 1024×1024 is ~1.2 GB of uint8 RGBA in one
list. The docstring justifies it with "``out_dir`` may be the input directory: all inputs
are read before any output is written", but that hazard does not actually exist here —
output file names match input names, and each frame is written immediately after it is read,
so the only frame that must survive is frame 0, whose alpha is already extracted into
`ref_alpha` before the loop starts.

**Fix:** keep `ref_alpha` (and frame 0's array, to write it out), then stream the rest one at
a time inside the existing loop. The cancel poll and progress call stay where they are.

**I3. A uniformly opaque alpha makes the `phase` de-jitter apply a spurious ~0.7 px shift to every frame after the first.**
`core/sprite/stabilize.py:212-216`

The degenerate-input guard is `ref.sum() <= 0.0 or mov.sum() <= 0.0`, which catches an
*empty* mask but not a *constant* one. I measured it:

```
estimate_shift(ones(64,64), ones(64,64), 'phase')  ->  (-0.7, -0.7)     # skimage
estimate_shift(blob, blob, 'phase')                ->  (0.0, 0.0)       # correct
estimate_shift(zeros, blob, 'phase')               ->  (0.0, 0.0)       # correct
```

Two identical constant frames should register at (0, 0); skimage's sub-pixel refinement on
a signal with no structure returns −0.7 px instead. The value survives the
`MAX_SHIFT_FRACTION` clamp, so `translate_rgba` bilinearly resamples every frame after the
first by −0.7, −0.7 px: a 0.7 px misregistration against frame 0 plus a 1 px transparent
seam along two edges from `BORDER_CONSTANT`.

**Why it matters:** `StabilizeSettings.dejitter` defaults to `True`, and the constant-alpha
condition is reachable on a real workflow — `key.method = "none"` on an opaque imported PNG
sequence (crop-and-stabilise only, no keying), where `crop_and_pad` with `pad_px=0` yields a
fully opaque frame. It also fires on top of a *failed* chroma key (tolerance too low, wrong
plate colour → alpha all 1), compounding that failure with a resampling blur. The cv2
fallback path is already protected by `MIN_PHASE_RESPONSE`; only the skimage path is exposed.
I checked whether skimage's returned `error` could serve as the guard — it cannot, it reports
~1.0 for both the degenerate case and a perfect match.

**Fix:** before the phase branch, fall back to `_centroid_shift` (or return `(0.0, 0.0)`)
when either mask has near-zero variance, e.g. `if ref.std() < 1e-6 or mov.std() < 1e-6`.
Add the constant-alpha case to `test_dejitter.py` alongside the all-transparent case that
deferred minor 12 already asks for.

### Minor

1. **`hd_runner`'s alpha post-pass has no cancel poll and no progress** (`pipeline.py:456-459`).
   The loop re-opens and re-saves every frame with no `check(token)`, so a cancel during the
   slowest stage waits for the whole pass. Add `check(token)` and a `progress("hd", ...)` call.
2. **`hd_runner` re-encodes every frame even when `apply_profile_alpha` is a no-op**
   (`pipeline.py:456-459`). When `prof.binary_alpha` is False the function returns the same
   image and the save is pure waste — a full PNG re-encode of the whole action. I confirmed
   the in-place `Image.open(dst) … .save(dst)` round-trip is *safe* (Pillow 11.3.0 calls
   `load()` before truncating; byte-identical after), so this is cost, not corruption. Guard
   the loop with `if prof.binary_alpha:`.
3. **`OVERRIDE_KEYS` is declared but never used** (`keying.py:29`; `apply_overrides` at
   `:222-226` hardcodes the same three names). Two sources of truth that can drift, and 5b
   will read the constant to build the override UI. Drive the branch from `OVERRIDE_KEYS`.
4. **`_installed()` can report True for a broken install** (`matting.py:91, 108`), so a
   corrupt `mediapipe`/`rembg` surfaces as a bare `ImportError` instead of
   `MattingUnavailable`. Wrap the two lazy imports in `try/except ImportError` and route
   through `_fail()`.
5. **The new API is not exported from `core/sprite/__init__.py`.** `crop_and_pad`,
   `union_alpha_bbox` and friends are re-exported, but `dejitter`, `binary_alpha`,
   `key_frame` and `hex_to_rgb` are not, so sub-projects 4/5b/6/7 must reach into
   submodules while sibling helpers are available at package level. Harmless but
   inconsistent; add them to `__init__` and `__all__` before downstream code hardcodes the
   deep paths.
6. **Settings-shape inconsistency between sibling stages** (`pipeline.py:206-230`):
   key/cleanup/alpha return flat dicts, stabilize returns `{"stabilize": {...}}`. Both are
   tested and correct; note it so sub-project 4's `pixel_stage_settings` picks one on
   purpose.
7. **No warning when the key colour is neutral** (`keying.py:79-96`). A grey/white/black key
   has (Cb, Cr) = (0, 0), so *every* neutral pixel in the subject is at distance 0 and gets
   keyed out. Inherent to chroma keying, but it fails silently; a one-line
   `logger.warning` when the key colour's chroma magnitude is below a small threshold would
   save a confusing support round-trip in 5b.
8. **`_rembg_alpha` mutates process-global state and caches sessions that nothing
   invalidates** (`matting.py:116-122`, `_REMBG_SESSIONS` at `:43`). `os.environ["U2NET_HOME"]`
   is set on every call, and `clear_sessions()` exists but has no caller — if the user moves
   the storage root from the Settings tab mid-session, the cached session still points at
   the old directory. Wire `clear_sessions()` into the storage-root change handler in 5b.
9. **Repeated directory scans during fingerprinting.** `stage_fingerprint` recurses through
   the upstream chain, and both `key_stage_settings` and `alpha_stage_settings` call
   `_frame_override_list`, which globs the extract directory each time; `extract_stage_settings`
   additionally `stat()`s every frame when `clip is None`. `run_pipeline` calls
   `is_stage_current` per stage, so a 7-stage run repeats the glob many times over. Not a
   correctness issue and not currently slow; worth a memo if action lengths grow.
10. **No cancellation test for the key/cleanup/alpha runners.** All three do call
    `check(token)` per frame (`pipeline.py:368, 385, 403`) so the behaviour is present, but
    only `dejitter` has a `Cancelled` test. One parametrised test would cover all three.

---

## Deferred-minor triage

| # | Deferred minor (from progress.md) | Ruling |
|---|---|---|
| 1 | T1 — forward-reference unused imports in `keying.py` | **LEAVE** — resolved; I checked every import in `keying.py` and `matting.py` and all are now used. |
| 2 | T1 — `hex_to_rgb`/`chroma_alpha` raise `ValueError` without logging | **FIX NOW** — this is Important **I1**; the bare `ValueError` reaches `run_pipeline` callers. |
| 3 | T2 — despill argmax tie clamps only the first channel for a magenta key | **LEAVE** — matches the plan formula; magenta plates are out of scope and the failure is visible, not silent. |
| 4 | T3 — negative `feather_px`/`despeckle_px` silently no-op | **LEAVE** — only `choke_px` documents a negative meaning; a no-op is the safe reading. |
| 5 | T3 — multi-clause docstrings (STE style) | **LEAVE** — prose polish, no behaviour. |
| 6 | T4 — `OVERRIDE_KEYS` unused by `apply_overrides` | **FIX NOW** — Minor 3; two sources of truth, and 5b will consume the constant. |
| 7 | T4 — unused `caplog` fixture in `test_apply_overrides_changes_only_known_keys` | **LEAVE** — cosmetic. |
| 8 | T4 — `key_frame` passes un-overridden settings to `cleanup_pass` | **LEAVE** — confirmed harmless; `OVERRIDE_KEYS` contains no cleanup field, so the two are identical by construction. |
| 9 | T4 — `_ml_alpha` lazy import unguarded | **LEAVE** — Task 6 resolved it; `matting.ml_alpha` now raises `MattingUnavailable`. Residual broken-install gap is Minor 4. |
| 10 | T5 — `ffmpeg_chromakey_preview` calls `hex_to_rgb` unguarded | **FIX NOW** — folded into **I1**; inconsistent with the two `KeyingError`s in the same function. |
| 11 | T6 — `_installed()` True for a broken install → bare `ImportError` | **FIX NOW** — Minor 4; three lines, and 5b's install dialog branches on this error type. |
| 12 | T8 — no end-to-end all-transparent-frame test inside a multi-frame `dejitter` | **FIX NOW** — cheap, and it is the natural home for the **I3** constant-alpha regression test. |
| 13 | T9 — `hd_runner` post-pass lacks `check(token)`/progress | **FIX NOW** — Minor 1; the HD stage is the slowest, so this is where cancel latency is felt. |
| 14 | T9 — `hd_runner` re-reads/writes every frame when the alpha pass is a no-op | **FIX NOW** — Minor 2; one-line guard, removes a full re-encode pass. Verified not corrupting. |
| 15 | T9 — stale comment at `tests/sprite/test_pipeline.py:414` | **LEAVE** — moot; the file is 397 lines and the three comments this branch added there are accurate. |
| 16 | Ruling — nested `{"stabilize": {...}}` settings shape | **LEAVE** — tested and correct; see Minor 6 for the sibling inconsistency memo. |
| 17 | Ruling — lazy ffmpeg import in `keying.get_ffmpeg_path` | **LEAVE** — verified: the isolation pin holds from a fresh interpreter. |
| 18 | Ruling — override list sized off extract-stage frames | **LEAVE** — verified correct; the reasoning in the docstring is sound and the index spaces line up. |

---

## Assessment

**Ready for downstream sub-projects: yes**, once I1–I3 are fixed — none of them changes a
public signature, so 4/5b/6/7 can be planned against this API as it stands. The contract
surface the downstream work consumes is complete and correct, the fingerprint semantics
behave exactly as §1.2 requires, and the de-jitter maths is right on both backends, which I
confirmed by running it rather than reading it.

The three Important findings are all localised — one error-type wrapper, one streaming loop,
one variance guard — and the only one that produces wrong pixels (I3) needs a degenerate
uniformly-opaque input to trigger. Nothing here will be painful to change after three more
sub-projects land on top.
