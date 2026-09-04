# Fix wave C report — `image_route.py` / `retouch.py` (final review, sub-project 6)

**Implementer:** fix-ir-C
**Date:** 2026-08-30
**Files owned and changed:**

- `/mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation/image_route.py`
- `/mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation/retouch.py`
- `/mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py`
- `/mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_retouch.py`

No other file was touched. Nothing was committed or staged. `git status` over
`core/sprite/generation`, `gui/sprite` and `tests/sprite` shows only these four files plus the
four files the sibling implementers own.

---

## Important 6 — matte plates left the pipeline stage directory

`edit_chain` now writes the two plates into `out_dir / "plates"`:

- `image_route.py:320-326` — `plates_dir = out_dir / "plates"`, then
  `save_png(..., plates_dir / f"{k:04d}.white.png")` and the black plate beside it.
  `save_png` creates the parent, so no separate `mkdir` is needed.
- Each plate keeps its own `write_image_sidecar` call with the same provenance fields
  (prompt, provider, model, step, of, pose, plate colour). Only the location moved.
- The composed frame's sidecar `plates` list still records both plate paths, now pointing at
  `plates/NNNN.white.png` and `plates/NNNN.black.png`.
- The matte-mode chain reference still cites the white plate, so
  `sidecar["reference_images"][1]` still ends with `0001.white.png`.
- `edit_chain`'s docstring states the rule and the reason.

`core/sprite/pipeline.py:145` `list_frames` was **not** changed: it is a sub-project 1 contract.
Its `directory.glob("*.png")` is not recursive, so a `plates` subdirectory is invisible to it.

`gui/sprite/image_route_dialog.py:70` `billed_units` is unaffected. It counts
`extract_dir.glob("*.png")` with `path.stem.isdigit()`, which is also non-recursive, and the
plate stems never were digits. The fix is therefore core-side only, as the brief required.

## Important 4 — the Gemini region retouch now tells the truth

**Option taken: build the prompt, the request params and the sidecar from what is actually
sent.** I read `providers/google.py:1907-1916` first: `edit_image_region(self, image: bytes,
region_bbox, prompt, model=None, use_conversation=False, style_context=None, **kwargs)` takes a
single `image`. It has no parameter that can carry the neighbour frames, and `**kwargs` reaches
the Gemini call, not an extra-image list. Sending the neighbours on that branch is therefore not
available without a provider change, which is outside this slice.

`retouch.py:145-152` computes the effective list once:

```
sent_neighbors: List[Path] = [] if (kind == "google" and region is not None) else neighbor_paths
```

`neighbor_bytes`, `retouch_prompt(instruction, neighbors=len(sent_neighbors))`,
`params["neighbors"]` and the sidecar `reference_images` all derive from that one list. On the
Gemini region path the prompt no longer claims neighbours, the request log prints
`'neighbors': []`, and the sidecar records no reference image. Every other path is unchanged and
still sends and records all neighbours. The `List` import that the review flagged as dead is now
used.

## Important 5 — no more double logging on the default retouch log path

**Option taken: the `logger` keyword on the three shared helpers.** I read `_common.emit` first.
`emit` does handle a `None` sink correctly (it returns after writing the module logger), so
setting retouch's default sink to `None` would also stop the duplicate. I did not take that
option, because it moves the retouch route's request and response lines under the *image_route*
logger name, which is the wrong provenance for a CLI reading `imageai_current.log`. The keyword
option keeps every line under `core.sprite.generation.retouch`.

- `image_route.py:74-104` — `log_request`, `log_response` and `call_provider` take
  `logger: logging.Logger = logger`. The default binds image_route's module logger at definition
  time, so every existing caller inside `image_route.py` is unaffected.
- `retouch.py:160-176` — all three call sites pass `logger=logger`.

`emit`'s guard at `_common.py:21` now matches: the sink `logger.info` and the emitting logger are
both retouch's, so the sink is skipped and each full-content line is written once.

## Minor 1 — the four bare progress lines go through `emit`

`image_route.py:206` (sheet saved), `:225` and `:227-228` (grid detected / grid rejected), `:355`
(step k/n saved) now call `emit(logger, log, ...)`. They reach the file logger as well as the
sink, and a raising sink can no longer abort a render.

## Minor 2 — the cancel poll between the two matte plates

**Deviation from the review's suggested fix, deliberate — one poll, not two.** The review asked
for a poll at the top of the `for color in plates:` body **and** again right after
`log_response`. I added the first one only (`image_route.py:299-301`).

Reason: the top-of-body poll already runs after the previous plate's `log_response`, so it is the
poll that prevents the second, unwanted provider call — which is the entire harm the finding
describes. A second poll after `log_response` fires only on the **last** plate of a step, where
it cannot save a provider call and can only discard an image the user has already paid for. Two
concrete costs of that extra poll:

1. The step's `NNNN.png` would never be written, so the frame the user paid for is lost.
2. `gui/sprite/image_route_dialog.py:70` `billed_units` counts the `NNNN.png` files on disk to
   bill a render that stopped, so the discarded frame would be under-billed by a whole step.

It also breaks the existing `test_edit_chain_cancels_between_steps`, which pins that a step whose
provider call completed lands on disk. I kept that behaviour rather than weaken the test.

---

## Tests added, with the reversion check for each

All four new tests were verified by reverting the source change, confirming a FAIL, restoring the
file from a scratchpad copy, and confirming a PASS. No scratch file was written inside the repo.

| Test | File:line | Reversion applied | Result |
|---|---|---|---|
| `test_matte_plates_stay_out_of_the_pipeline_stage_directory` | `tests/sprite/test_image_route.py:287` | plates saved to `out_dir` again | **FAILED** at `:303` (`list_frames` returned the plates), passes when restored |
| `test_edit_chain_cancel_during_the_white_plate_does_not_buy_the_black_one` | `tests/sprite/test_image_route.py:314` | per-plate poll removed | **FAILED** at `:329` (`edit_image.call_count == 2`), passes when restored |
| `test_google_region_prompt_and_provenance_report_no_neighbors` | `tests/sprite/test_retouch.py:90` | `sent_neighbors = neighbor_paths` | **FAILED** at `:101` (prompt said "the other 2 image(s) are the neighboring animation frames"), passes when restored |
| `test_google_whole_frame_prompt_and_provenance_keep_the_neighbors` (control) | `tests/sprite/test_retouch.py:108` | `sent_neighbors = []` for every branch | **FAILED** at `:114` (prompt lost "neighboring"), passes when restored |
| `test_default_log_writes_each_full_content_message_once` | `tests/sprite/test_retouch.py:119` | `logger=logger` dropped at the three call sites | **FAILED** — the run printed the same response line twice, under `core.sprite.generation.image_route` and `core.sprite.generation.retouch`; passes when restored |

The control test is deliberate: it proves the Important 4 fix narrowed the neighbour list on the
region branch only and did not simply delete the neighbour feature.

One existing test was updated for the new plate location, with no assertion weakened:
`test_edit_chain_matte_pairs` (`tests/sprite/test_image_route.py:248`) now reads the plates and
their sidecars from `chain/plates/`. Every other assertion in it is unchanged.

## Gate

```
QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest \
  tests/sprite/test_image_route.py tests/sprite/test_retouch.py tests/sprite/test_pose_steps.py \
  -q -p no:cacheprovider
...................................................                      [100%]
51 passed in 23.88s

QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest \
  tests/test_no_hardcoded_paths.py -q -p no:cacheprovider
...                                                                      [100%]
3 passed in 3.04s
```

Zero warnings in both runs. `test_pose_steps.py` passes, so the `generate_pose_instructions`
re-export from `image_route.py:19` still works.

Model-ID literal guard over both runtime files: only the two permitted
`MODEL_CAPS["gpt-image-1"]` fallback keys (`image_route.py:113`, `:128`).

## Concerns

1. **Minor 2 is one poll, not two** — see the reasoning above. If the controller wants the second
   poll after `log_response`, it needs a ruling on the lost paid frame and on
   `test_edit_chain_cancels_between_steps`, which currently pins the opposite.
2. **No GUI change was needed** for Important 6. The plates leave the extract directory inside
   `edit_chain`, and both GUI readers of that directory (`run_pipeline` through
   `pipeline.list_frames`, and `billed_units`) glob non-recursively, so neither sees the new
   subdirectory. `gui/sprite/image_route_dialog.py:60-61` carries a docstring sentence that now
   describes a location the plates no longer use ("the `NNNN.white.png` and `NNNN.black.png`
   plates keep a non-numeric stem"). The statement is still true and the count is still correct,
   but the sentence is stale prose. That file belongs to fix-ir-D, so I did not touch it; the
   controller may want a one-line docstring refresh there.
3. **The `logger` keyword shadows the module global** inside the three helpers. That is the shape
   the brief prescribed. The default is bound at definition time, so the shadowing is local to
   each call and no existing caller changes behaviour.
4. `retouch.py` still carries the deferred triage note that non-existent neighbour paths are
   dropped before `sent_neighbors` is computed. That drop is now visible in the request log and
   in the sidecar, which is stricter than before.
