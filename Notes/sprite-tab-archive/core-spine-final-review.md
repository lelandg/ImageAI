# Final whole-branch review — sub-project 1 (core spine)

**Range:** `069cd07..16382a0` (17 commits)
**Branch:** `feat/sprite-tab`
**Reviewer:** final-cs (Opus 5), read-only
**Date:** 2026-08-29

**Requirements reviewed against:**

- Plan: `Plans/2026-08-29-sprite-core-spine-plan.md` (Global Constraints, File Structure)
- Spec (binding): `Plans/2026-08-29-sprite-tab-design.md` §1, §2, §4.1, §5
- Project rules: `AGENTS.md`

**Method:** read every new source file in full (17 modules, ~2,600 lines) plus all 12 test
modules; read the migration/paths diff; reproduced three findings with focused
`.venv_linux` runs. The implementer's full-suite result (1174 passed, 19 skipped) is
taken as evidence; the suite was not re-run.

**Findings: 1 Critical, 3 Important, 7 Minor (+1 out-of-scope note).**

---

## Plan/spec alignment — verdict + deviations

**Verdict: aligned.** Every row of the plan's File Structure table exists, and every
signature in design §2 and §4.1 is present with matching names, parameters and defaults.
Storage (§1.6), the cancel/progress contract (§1.1), the fingerprint rule (§1.2) and the
testing strategy (§5) are all implemented as specified.

Global constraints hold:

| Constraint | Status | Evidence |
|---|---|---|
| `core/sprite` never imports PySide6 | Held | pinned by `tests/sprite/test_sprite_paths.py:37` (but see Minor 3) |
| No new hard dependencies | Held | only Pillow, numpy, opencv, ffmpeg; `requirements.txt` untouched |
| Never build a data path by hand | Held | `core/paths.py:227` + `:285`; `tests/test_no_hardcoded_paths.py` covers `core/` |
| Images scaled proportionally, never cropped/distorted | Held | `stabilize.fit_size` uses one factor for both axes (`core/sprite/stabilize.py:97-104`), tested at `tests/sprite/test_stabilize.py:252` |
| Every exported artifact gets a `.json` sidecar | Held | grid, PNG sequence, single frame, GIF all write one |
| Stage intermediates get no sidecar | Held | nothing under `stages/` writes one |
| No version bump / CHANGELOG entry | Held | correctly deferred to sub-project 7 |
| Lazy `core.video` import | Held | pinned by `tests/sprite/test_package.py:186` |

### Deviations from the spec, all defensible

1. **`export_gif` takes an extra `warnings` out-parameter** (`core/sprite/exporters/gif.py:246`).
   The spec asked for "a returned warning list" but fixed the return type as `Path`; the
   out-param resolves the contradiction, and warnings are also logged and written into the
   `.gif.json` sidecar. Accept.

2. **`export_grid` fills `FrameMeta.frame` with the *sprite* rect, not the *cell* rect**
   that the §2 comment describes (`core/sprite/exporters/grid.py:162`). With
   `trimmed=False` and `sourceSize == frame size` the emitted document is self-consistent
   and is what Aseprite / TexturePacker importers actually expect. Note that
   `filled.cell_size` is the *padded* cell, so the two disagree if frames ever vary in size
   within one sheet — harmless today because every frame leaving `stabilize`/`hd` shares a
   size. Accept, but downstream sub-project 6 (engine presets) should not assume
   `cell_size` slices the sheet uniformly.

3. **Additive API beyond the spec list.** `PipelineError`, `UPSTREAM`, `PROFILE_STAGES`,
   `list_frames`, `record_fingerprint`, `check`, `stage_settings`, `has_transparency`,
   `anchor_offset`, `fit_size`, `foreground_mask`. All useful to sub-projects 2-6 and none
   conflict with the spec. Accept.

4. **`core/sprite/__init__.py` does not import the keying / pixel-art modules.** §4.1
   requires the package `__init__` to import them so their `register_stage` calls run on
   package import. Those modules do not exist yet, so the omission is correct for now —
   but it is a **seam sub-projects 3 and 4 must add**, and nothing in this branch records
   that obligation. Recommend a line in each downstream plan (and, ideally, a TODO comment
   at `core/sprite/__init__.py:75`) so the registration is not silently forgotten; a
   missing import would mean the identity runners stay in place and keying/pixel-art
   silently do nothing.

5. **`SpriteProject.sheet_meta` always sets tag `direction="forward"`**
   (`core/sprite/project.py:536`). `ActionCard` has no direction field in the spec, so this
   is correct; the GIF exporter reads `direction` off a `TagMeta` the caller may edit.
   Accept.

---

## Strengths

- **The stage registry is the right shape.**
  `test_a_replacement_key_runner_changes_output_and_invalidates_downstream`
  (`tests/sprite/test_pipeline.py:208`) performs the exact substitution sub-projects 3 and
  4 will do — re-register `key` with a real runner at `code_version=2`, confirm `extract`
  stays cached, confirm `key`…`hd` all re-run, confirm the new pixels propagate through the
  identity stages, confirm every downstream fingerprint changed. That is the single most
  important thing this sub-project had to get right, and it is verified end to end rather
  than asserted.

- **Fingerprint scoping is precise and tested in both directions.** A changed keying
  tolerance invalidates `key`…`pixel` but not `extract`; a changed `pad_px` invalidates
  `stabilize` but not `alpha` (`tests/sprite/test_pipeline.py:72-83`). This is the §1.2
  requirement stated almost verbatim as a test.

- **`_sync_frames` is subtle and correct.** It carries `duration_ms`, `pivot` and
  `overrides` across a re-run *by index* while leaving the `key` fingerprint untouched
  (`tests/sprite/test_pipeline.py:252-274`), including the short-old-list case. A naive
  implementation would either lose user edits or churn the cache.

- **The Task 7 ruling was right, and the resulting test is real.**
  `test_run_ffmpeg_cancel_stops_a_running_process_promptly`
  (`tests/sprite/test_extract.py:101`) uses `-re` so the lavfi source genuinely spans 20 s,
  then asserts cancellation returns in under 5 s. That test fails against the plan's
  blocking `subprocess.run` prototype, which is what makes it worth having.

- **Tests verify behaviour, not shape.** The GIF test reloads with Pillow and checks
  `n_frames`, `disposal_method`, the transparency index, per-frame `duration` and actual
  pixel alpha at two coordinates. The extrude test samples the extruded border pixels and
  the corner fill. `test_extract_exact_n_picks_evenly_spaced_frames` scans a pixel row to
  confirm the square actually advances. Golden files compare parsed structures with the
  version field normalised, as §5 requires.

- **Storage integration is pinned from both ends.**
  `test_group_contents_name_every_sprite_accessor_leaf`
  (`tests/migration/test_sprite_storage.py:18`) ties the `DataPaths` accessor leaf to the
  migrator's manifest, so an accessor rename cannot silently orphan user data during a
  storage move. `test_reanchor_marker_matches_the_accessor_leaf` does the same for the
  re-anchor marker.

- **Atomic project writes.** `SpriteProject.save` writes to `.tmp` then `replace`
  (`core/sprite/project.py:433-435`), and `load` backs up a corrupt file before raising
  (`:452-458`). Good hygiene for a file the GUI will save on every edit.

---

## Issues

### Critical

#### C1. Re-importing external frames leaves stale frames from the previous import — silently wrong output

**Where:** `core/sprite/slicing.py:142` (`import_png_sequence`) and `core/sprite/slicing.py:109` (`slice_sheet`)

**What:** Both functions do `out_dir.mkdir(parents=True, exist_ok=True)` and then write
`0001.png…NNNN.png`. Neither clears what is already there. Both are documented to write
into `stage_dir(project, action, "extract")`, and `register_external_frames` /
`extract_runner` then accept whatever `pipeline.list_frames` returns.

Reproduced:

```
import 12 frames into the extract dir, register, run the pipeline
then re-import a shorter 8-frame sequence into the same dir:
  frames now visible to the pipeline: 12   (expected 8)
```

**Why it matters:** The animation silently carries four frames from the discarded import,
with no error anywhere. `register_external_frames` then records a fingerprint over the
polluted set, so the stage is marked *current* and a re-run will not fix it. This is the
normal "I picked the wrong files, let me redo it" flow, and the G9 external-input contract
is consumed by sub-project 5b (import dialog), sub-project 6 (image route) and sub-project 7
(CLI) — all three inherit the bug. Note the asymmetry that causes it: the video path
already resets the directory (`core/sprite/extract.py:278-280`, pinned by
`test_extract_clears_stale_output`), while the import path does not.

**Fix:** Clear existing `*.png` in `out_dir` at the top of both `slice_sheet` and
`import_png_sequence` — mirror `extract_frames`' `rmtree` + `mkdir`, or unlink the PNGs if
you prefer not to remove a directory the caller created. Add one test per function that
imports a long sequence, re-imports a shorter one, and asserts the resulting count.

---

### Important

#### I1. The `hd` stage reports per-frame progress under the stage name `"stabilize"`

**Where:** `core/sprite/stabilize.py:143`, reached from `core/sprite/pipeline.py:341` (`hd_runner`)

**What:** `crop_and_pad` hardcodes its progress stage label:

```python
progress("stabilize", index, total, f"stabilize: {path.name}")
```

`hd_runner` calls the same function. Observed during a real `run_pipeline(upto="hd")`:

```
stage=stabilize  msg=stabilize: 0001.png     <- emitted while the hd stage ran
stage=hd         msg=hd: running
stage=stabilize  msg=stabilize: 0001.png     <- and again
stage=hd         msg=hd: done
```

**Why it matters:** §1.1 defines the progress tuple as `(stage_name, done, total, message)`
and gives it to the GUI worker; 5a/5b will drive a per-stage progress bar and a stage label
off `stage_name`. The bar will jump backwards to "stabilize" mid-`hd`. Sub-project 4
re-registers `pixel` and will hit the identical trap if it reuses `crop_and_pad`. No test
catches this — `tests/sprite/test_pipeline.py:155` only asserts the `stabilize: done` event,
which `run_pipeline` emits itself with the correct name.

**Fix:** Add `stage: str = "stabilize"` to `crop_and_pad` and pass `out_dir.name` from both
`stabilize_runner` and `hd_runner`. `identity_runner` already does exactly this
(`core/sprite/pipeline.py:279`), so the pattern is established. Extend
`test_pipeline_runs_external_frames_through_hd` to assert that no event carries
`stage == "stabilize"` after the `hd: running` event.

#### I2. `SnapshotStack` loses history after a redo — undo becomes a no-op

**Where:** `core/sprite/undo.py:53-58`

**What:** `redo()` pushes the snapshot it is *restoring* onto the undo stack instead of the
one it is *leaving*:

```python
def redo(self):
    if not self._redo: return None
    snap = self._redo.pop()
    self._undo.append(snap)      # <- pushes the state being entered
    return snap
```

Reproduced:

```
undo       -> state A
redo       -> state B
undo again -> state B      (expected: state A)
```

`state A` is unreachable from then on, and every further undo/redo pair oscillates on
`state B`.

**Why it matters:** §1.5 binds Ctrl+Z / Ctrl+Y in the Sprite tab to this stack, and §1.4
makes it the safety net for every destructive frame-list edit (delete, reorder, duplicate,
insert, duration edit, retouch, override edit). 5a and 5b inherit a broken undo directly.
`test_undo_returns_previous_state_and_parks_current_for_redo`
(`tests/sprite/test_undo.py:20`) stops exactly one step short of catching it.

**Fix (keeps the spec's no-arg `redo()` signature):** track the last-restored snapshot.

```python
def __init__(self, depth: int = 50) -> None:
    ...
    self._restored: Optional[FrameListSnapshot] = None

def undo(self, current):
    if not self._undo:
        return None
    self._redo.append(current)
    snap = self._undo.pop()
    self._restored = snap
    return snap

def redo(self):
    if not self._redo:
        return None
    snap = self._redo.pop()
    self._undo.append(self._restored if self._restored is not None else snap)
    self._restored = snap
    return snap
```

Traced: push(A) → undo(B) returns A → redo() returns B and leaves `undo=[A]` → undo(B)
returns A. Correct in both directions. Add a test that performs undo → redo → undo and
asserts the first state comes back.

#### I3. `exact_n` drops the tail of the clip when `exact_n` exceeds the extracted frame count

**Where:** `core/sprite/extract.py:311`

**What:** the loop is capped at `min(n, count)` but the divisor stays `n - 1`, so the picks
compress into the front of the clip:

```
n=20, count=12 -> [0,1,2,3,4,5,6]   (7 frames, all from the first half)
n=8,  count=5  -> [0,1,2]           (3 frames)
n=12, count=12 -> [0..11]           (correct)
```

**Why it matters:** The user asks for 20 evenly-spaced frames of a walk cycle and gets
7 frames of its first half — a truncated animation, no error. `estimate_frame_count`
disagrees with the result it is meant to predict:
`tests/sprite/test_extract.py:39` asserts `estimate == 48` for `exact_n=99` on a 48-frame
source, while extraction would return roughly half that, so the GUI's pre-flight count
lies. Triggers: a short clip, a heavily trimmed clip, or simply a large `exact_n`. The
spec's own formula (`round(i * (count-1) / (N-1))`, §4.1) has the same gap, so this is
inherited rather than introduced — it still needs fixing before the GUI exposes the field.

**Fix:**

```python
n_eff = min(n, count)
if n_eff == 1 or count == 1:
    picks = [0]
else:
    picks = sorted({int(round(i * (count - 1) / (n_eff - 1))) for i in range(n_eff)})
```

With `n >= count` this keeps every frame, which is also what `estimate_frame_count`
already predicts. Add a test that requests more frames than the fixture clip contains and
asserts all 12 come back, spanning the full motion.

---

### Minor

#### M1. `hd_runner` ignores `upscale_small` / `upscale_method`

`core/sprite/pipeline.py:335-343`. A crop smaller than the hd cell is always LANCZOS-upscaled
even with `OutputProfile.upscale_small=False` (the default). Because `_profile_settings`
(`:185-187`) hashes the whole profile dict, toggling the flag invalidates the hd cache and
changes nothing — confusing for the user and wasteful. Either honour the flags in
`hd_runner`, or document in `OutputProfile` that they apply to the pixel profile only and
drop them from the hd fingerprint.

#### M2. `render_frame_name` raises raw formatting exceptions on a user-typed template

`core/sprite/exporters/png_sequence.py:28`. `template.format(...)` raises a bare `KeyError`
for an unknown field (`{name}`), `IndexError` for `{0}`, or `ValueError` for an unbalanced
brace. The team already ruled the collision guard in (Task 13) precisely because 5b's
ExportDialog feeds this a user string; the same input deserves a wrapped, user-facing
message. Suggest catching `(KeyError, IndexError, ValueError)` and re-raising a `ValueError`
naming the offending field and the supported field list.

#### M3. The Qt-import pin uses a cwd-relative path and can pass vacuously

`tests/sprite/test_sprite_paths.py:42` — `pathlib.Path("core/sprite").rglob("*.py")`. Run
from any directory other than the repo root the glob yields nothing and the assertion
passes with an empty offender list, silently retiring a global-constraint guard. Use
`Path(__file__).resolve().parents[2] / "core" / "sprite"`, as `test_package.py:192` already
does for the repo root.

#### M4. `_renumber` temp files match the frame glob

`core/sprite/extract.py:236` stages through `.tmp_{index:04d}.png`, which matches the
`*.png` glob in `pipeline.list_frames` (`core/sprite/pipeline.py:138`). A crash or a
`shutil.move` failure mid-renumber leaves temp files the pipeline would count as frames.
Use a `.tmp` *suffix* (`0001.png.tmp`) instead of a `.tmp_` prefix so they stay out of the
glob.

#### M5. A missing external frame escapes as a bare `OSError`

`core/sprite/pipeline.py:164` — `extract_stage_settings` calls `p.stat()` on every external
frame. If a file is removed between runs, `FileNotFoundError` propagates out of
`is_stage_current` and `run_pipeline` rather than the `PipelineError` the GUI and CLI know
how to display. Wrap the `stat()` the way `_clip_info` (`:150-154`) already does, and treat
a missing frame as a settings change (which correctly invalidates the stage).

#### M6. `_sync_frames` never runs when `stabilize` is cached

`core/sprite/pipeline.py:358-382` and `:420-421`. If the stabilize cache is current but
`action.frames` is empty — a project whose frames were cleared, or a hand-edited
project file — the action stays frameless and `sheet_meta` yields nothing, with `force=True`
the only escape. Consider rebuilding `action.frames` from the cached stabilize output when
the list is empty. (Deliberately *not* rebuilding when the list is non-empty is correct:
that preserves user deletions.)

#### M7. `CUSTOM_CELL_LABEL` is not re-exported

`core/sprite/presets.py:131` is absent from `core/sprite/__init__.py`'s import list and
`__all__` although the rest of the preset surface is exported. Sub-project 5a's cell-size
combo box will want it. Same, lower-priority, for `has_transparency`, `anchor_offset`,
`fit_size` and `foreground_mask` — all reachable from their submodules, so this is
convenience only.

#### Out-of-scope note (pre-existing, not introduced by this branch)

`core.utils.write_image_sidecar` (`core/utils.py:216-220`, last touched at `344e45a`,
before this branch's base) silently swallows write failures, and its `except` tuple names
`json.JSONEncodeError`, which does not exist in the stdlib — so a real `OSError` there
raises `AttributeError` while evaluating the handler instead of being suppressed. Verified:
`hasattr(json, "JSONEncodeError")` is `False`. Every sprite exporter is now a caller, and
AGENTS.md requires every error to be logged. Worth a separate one-line fix
(`json.JSONDecodeError` → drop it, add `TypeError`, and log) outside this branch.

---

## Deferred-minor triage

| # | Ledger item | Ruling | Reason |
|---|---|---|---|
| 1 | Task 3 — settings dataclass `to_dict`/`from_dict` boilerplate (`project.py:104-166`) | **LEAVE** | Plan-mandated. A mixin would hide the per-field coercion `OutputProfile.from_dict` genuinely needs (`:171-188`). |
| 2 | Task 3 — `_reanchored` `SPRITES_DIR_NAME` fallback branch untested (`project.py:61-65`) | **LEAVE** | The primary branch is covered by `test_load_reanchors_media_after_a_storage_move`, and `test_reanchor_marker_matches_the_accessor_leaf` pins the marker itself. |
| 3 | Task 3 — `delete_project` / `list_projects` failure branches untested | **LEAVE** | Both are log-and-return-falsy paths with no state change. |
| 4 | Task 6 — `stage_settings` uses `.get(stage, _no_settings)` (`pipeline.py:219`) | **LEAVE** | `register_stage` guarantees the key, and the `stage not in STAGES` guard fires first. The default is unreachable and harmless. |
| 5 | Task 6 — `stage_fingerprint` re-walks the upstream chain, O(n²) at n=7 (`pipeline.py:222-231`) | **LEAVE**, with a note | 49 hashes of small dicts is nothing, but for external-frame actions each walk re-`stat()`s every frame (`:164`). A 200-frame import costs a few thousand `stat` calls per pipeline run. Still well under a second; revisit only if 5b's UI feels sluggish. Fixing M5 is a natural place to memoise. |
| 6 | Task 7 — `_terminate` may leave an unreaped process after SIGKILL + 2 s (`extract.py:182-192`) | **LEAVE** | Uninterruptible-sleep edge only; the process is reaped at interpreter exit. |
| 7 | Task 8 — numpy-stub typing artefact (`slicing.py:93-94`) | **LEAVE** | Type-checker artefact, no runtime path. |
| 8 | Task 9 — pyright narrowing gap (`stabilize.py:51`, `:80`) | **LEAVE** | `x0 is None` implies the siblings are None by construction; runtime-safe. |
| 9 | Task 9 — no test for the `union_alpha_bbox` / `solid_border_bbox` "nothing found" branch | **LEAVE** | The fully-transparent-clip path returns the full frame, which is the defensible behaviour (stabilize then emits full-size empty cells rather than erroring). A test would be cheap but is not a merge gate. |
| 10 | Task 14 — `pingpong_reverse` direction untested (`gif.py:225-227`) | **LEAVE** | Traced by hand: `reversed(frames) + frames[1:-1]` gives `n-1…0,1…n-2`, correct, with the `len > 2` guard matching `pingpong`. One assert would close it if convenient. |

**Both Task-level rulings were sound.** Task 7 (cancellable ffmpeg) is vindicated by a test
that genuinely exercises a long-running process rather than a pre-cancelled token. Task 13
(template-collision guard) is verified to raise *before* any file is written
(`tests/sprite/test_exporters.py:194` asserts the output directory does not exist after the
rejection).

---

## Assessment

**Ready for downstream sub-projects: not yet — fix C1 and I1-I3 first. All four are small
and local.**

The architecture is right and the contracts sub-projects 2-6 depend on — the stage
registry, the fingerprint cache, cancellation, `SheetMeta` and the exporter signatures —
are correct and genuinely well tested; the four findings are contained bugs in
`slicing.py`, `stabilize.py`, `undo.py` and `extract.py` rather than design problems.
They block only because C1 and I3 produce silently wrong sprite sheets, and I1/I2 are
user-facing contracts (progress reporting, Ctrl+Z) that the GUI sub-projects will build
directly on top of, where a late fix means re-testing GUI wiring rather than one function.

**Suggested order:** C1 (one line each in two functions + 2 tests) → I2 (undo, ~8 lines +
1 test) → I3 (extract picks, ~4 lines + 1 test) → I1 (progress label, 3 call sites +
1 assertion). Estimated well under two hours in total. The Minor items can travel with
sub-project 2 or later; M3 (the vacuous Qt pin) is the one worth folding into the same
pass, since it currently protects a stated global constraint only by accident of cwd.
