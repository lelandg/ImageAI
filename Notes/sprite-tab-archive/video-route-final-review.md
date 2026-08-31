# Final whole-branch review — sub-project 2 (video route)

Range: `83c21b1..0b24aec` (17 commits) on `feat/sprite-tab`.
Reviewed 2026-08-29 by a senior code reviewer, read-only, in passes:
(1) ledger + task-11 review, (2) `_common`/`errors`/`prompts`/`__init__`,
(3) `cost`/`plate`/`turnaround`, (4) `video_route`, (5) `queue`/`timing`,
(6) `action_cards`/`source`, (7) the two video-client diffs and every existing
caller, (8) plan + spec cross-check, (9) tests, (10) two focused runtime probes
(package import cost, `write_image_sidecar` failure path). No subagents were
dispatched. The full suite was not re-run.

**Note on the working tree.** While this review was in progress the controller's
Task 13 ruling (lazy client imports in `video_route.py`) was applied on disk.
Findings below are written against the code as it now stands, and the one
Critical is marked resolved-in-tree.

---

## Plan/spec alignment

**Verdict: aligned.** Every symbol the design (§4.2) names exists with the
signature the design gives it, and every §1.1/§1.3 rule the sub-project owns is
implemented.

Checked symbol by symbol against `Plans/2026-08-29-sprite-tab-design.md:589-708`:

| Design symbol | Implemented | Location |
|---|---|---|
| `SourceAnalysis`, `normalize_source`, `analyze_source` | yes | `core/sprite/source.py:29,45,69` |
| `CHROMA_SUFFIX`, `LOOP_SUFFIX`, `FORBIDDEN_WORDS`, `inject_chroma`, `color_name` | yes, text verbatim | `core/sprite/generation/prompts.py:11-14,36,74` |
| `make_chroma_plate` (+ prompt text, `plate_color` in sidecar) | yes | `core/sprite/generation/plate.py:21,25` |
| `VIEWS`, `generate_turnaround` (do-not-change list, `token`) | yes | `core/sprite/generation/turnaround.py:22,57` |
| `ActionCardDraft`, `GENRE_CHECKLISTS`, `build_messages`, `parse_action_cards`, `generate_action_cards` | yes | `core/sprite/generation/action_cards.py:101,32,111,167,263` |
| `loop_seconds`, `suggest_clip_duration`, `frames_per_clip`, `ms_to_fps` | yes | `core/sprite/timing.py:19,43,63,77` |
| `RenderRequest`, `build_omni_config`, `build_veo_config`, `render_action`, `refine_action`, `trim_to_loop` | yes | `core/sprite/generation/video_route.py:43,58,82,186,304,406` |
| `PRICE_TABLE_VERIFIED`, `price_per_second`, `estimate_action`, `estimate_project`, `record_actual` | yes | `core/sprite/generation/cost.py:29,82,97,110,125` |
| `ActionQueue.enqueue/run/retry` | yes | `core/sprite/generation/queue.py:37,85,104,98` |
| §1.1 `cancel_check` on `VeoClient._poll_for_completion` / `OmniClient._await_terminal`, `success=False, error="cancelled"`, id preserved | yes | `core/video/veo_client.py:816,838`; `core/video/omni_client.py:403,421` |
| §1.3 error family + `classify_provider_error` | yes | `core/sprite/generation/errors.py:16-128` |

Verified behavioural requirements:

- **Veo loop conditioning forces 8 s and logs why** — `video_route.py:96-99`,
  `timing.py:57-58`. Design §4.2 line 674.
- **Backoff 2/4/8 s, `SafetyRefusal` never retried** — `queue.py:29,157`.
  Design §1.3. The plan's documented deviation 6 (one try + three retries, so
  the 8 s wait is actually used) is sound; without it the third value is dead.
- **Queue runs `run_pipeline(upto="stabilize")` after each clip** —
  `queue.py:31,183`. Design §4.2.
- **Omni rate left `None` / `PRICE_TABLE_VERIFIED = "unverified"`** —
  `cost.py:29-31`. Design §4.2 explicitly forbids a guessed rate; the
  verification note at `cost.py:11-16` records why the page's per-second figure
  was rejected. This is the design's requested behaviour, not a gap.

Project-rule compliance:

- **No hardcoded cloud model IDs.** `action_cards.py:231-244` routes every
  provider through `resolve_model()`; the three literals are `static_default=`
  arguments, which the rules permit.
- **Full request + response logging on every provider path.** Image edits:
  `plate.py:40-54`, `turnaround.py:77-92`. LLM chat: `action_cards.py:285-307`
  (request and response both fully emitted). Video generate:
  `video_route.py:174-183` (request) and `270-277` (full response —
  `generation_time`, `has_synthid`, `metadata`, `video_url`, `video_path`,
  operation/interaction id). Refine: `video_route.py:325-327`.
- **Every user-facing error logged.** Every `raise` of a
  `SpriteGenerationError` in `plate`, `turnaround`, `action_cards`,
  `video_route`, and `queue` is preceded by an `emit(..., level="error")`.
- **Prompt hygiene.** `strip_render_terms` removes the three forbidden words,
  a known-ratio list, and pixel sizes (`prompts.py:16-18,62`); aspect always
  travels as an `aspect_ratio=` kwarg (`plate.py:46`, `turnaround.py:82-83`,
  `video_route.py:72,117`). The LLM system prompt also forbids them at source
  (`action_cards.py:77`).
- **Sidecars.** Images via `write_image_sidecar` (`plate.py:68`,
  `turnaround.py:104`, `source.py:91`); clips via `write_clip_sidecar` on the
  completed, failed, and cancelled paths (`video_route.py:257,265,294,350`).
- **No hand-built data paths, no PySide6 under `core/`, no credentials in
  code.** Confirmed by inspection; `queue.clip_path` derives from
  `project.project_dir`.
- **Backward compatibility of the two production clients.** `cancel_check` is
  keyword-only-in-practice with a `None` default on
  `VeoClient.generate_video/generate_video_async/_poll_for_completion` and
  `OmniClient.generate_video/generate_video_async/_await_terminal`. All five
  pre-existing call sites still bind correctly: `gui/video/video_project_tab.py:1093`,
  `gui/video/video_project_tab.py:1420`, `cli/commands/video.py:146`,
  `cli/commands/video.py:186`, `core/video/veo_client.py:1090`. The second Veo
  generation path (`veo_client.py:758`) still calls `_poll_for_completion`
  without the hook, which is unchanged behaviour, not a regression.
  `poll_interval` moved to an instance attribute but is read through
  `getattr(self, "poll_interval", 10)` (`veo_client.py:830`), so instances built
  with `__new__` (as `cost.py:78` does) are unaffected.

**Deviations from the plan/design:** none beyond the eight the plan's own
self-review already declares (`Plans/2026-08-29-sprite-video-route-plan.md:4572-4581`).
Each was checked against the code and each is justified. The one to keep in
mind downstream is deviation 5: a cancel mid-render surfaces as
`pipeline.Cancelled` from `render_action`, which the queue converts into a
`ProviderError(retryable=True)` result entry.

**Cancellation end-to-end.** Traced the whole chain and it closes:
`CancelToken.cancelled` (`core/sprite/pipeline.py:49-51`) →
`ActionQueue._cancelled` (`queue.py:101`) checked between jobs (106) and during
backoff (`_wait_or_cancel`, 167-179) → `render_action` pre-checks the token
(`video_route.py:196`) and derives `cancel_check = lambda: token.cancelled`
(198) → both clients poll it before submission and inside the poll loop, raising
`VeoPollCancelled`/`OmniPollCancelled`, which they catch internally and convert
to `success=False, error="cancelled"` (`veo_client.py:622-626`,
`omni_client.py:377-382`) → `render_action` writes a `"cancelled"` sidecar
carrying the remote job id and raises `Cancelled` (`video_route.py:256-262`).
Both clients record the operation/interaction id *before* polling
(`veo_client.py:578`, `omni_client.py:323`), so the id survives a cancel — the
recoverability §1.1 asks for. Frame extraction inside `trim_to_loop` is the one
uncancellable leg, but nothing calls `trim_to_loop` yet (see Minor).

---

## Strengths

- **The cancel hooks are genuinely correct, not just present.** The Veo check is
  `cancel_check() and not operation.done` (`veo_client.py:838`), so a job that
  finished during the last sleep is still delivered instead of thrown away — the
  user does not pay for a clip and then lose it. Both clients also sleep in
  1-second slices (`veo_client.py:937-947`, `omni_client.py:443-452`) so a
  cancel lands within a second of a 10-second poll interval, and both check
  before submission so a cancel that arrives early spends nothing.
- **No `ClipRecord` is ever constructed on a failed or cancelled render.** The
  record is built only after the output file is confirmed to exist
  (`video_route.py:286-292`), and Veo's "success with no file" case is caught
  explicitly (279-288). The project can never hold a record pointing at a
  missing clip.
- **Errors chain and redact.** `_wrap` sets both `__cause__` and `.original`
  (`errors.py:80-91`) so `raise classify_provider_error(exc)` keeps the
  traceback, and `user_message` runs through `redact_secrets`
  (`errors.py:112`, `_common.py:41-53`) so bearer tokens, `key=`/`api_key=`
  parameters, and `AIza…`/`sk-…`/`hf_…` shapes never reach the UI. This is a
  house rule most modules in this repo do not yet honour.
- **The cost module refuses to guess.** `_veo_rate` reuses
  `VeoClient.estimate_cost` rather than restating rates (`cost.py:68-79`), the
  unverifiable Omni rate stays `None` with a written record of *why*
  (`cost.py:11-16`), and `estimate_project` reports an `unknown_count` so the UI
  can say "unknown" instead of "$0.00" (`cost.py:110-122`).
- **The action-card parser is tolerant where it should be and strict where it
  matters.** Fences and prose are stripped (`action_cards.py:130-144`), scalars
  are coerced (147-164), out-of-range and non-snake_case cards are dropped with
  a logged reason rather than silently repaired, and forbidden words are removed
  from the model's own prompt text (201) — defence in depth behind the system
  prompt.
- **Tests exercise behaviour, not mocks.** Seam scoring runs on real numpy/PIL
  pixels with a synthetic duplicate frame
  (`tests/sprite/generation/test_gen_video_route.py:302-321`); the queue tests
  cover backoff timing, cancel-within-one-slice, safety-refusal non-retry,
  pipeline-failure isolation, and enqueue atomicity
  (`tests/sprite/generation/test_gen_queue.py:100-274`); the client tests
  include an explicit old-signature compatibility case
  (`tests/video/test_veo_cancel_hook.py:110`) and a cancel-after-done case (51).
- **`emit`'s double-log guard.** `_common.py:21-22` skips the sink when it is a
  bound method of the same logger, so the `log=logger.info` default does not
  duplicate every line — a small thing that would otherwise have doubled every
  status-console message across five modules.

---

## Issues

### Critical

1. **`import core.sprite.generation` pulled in `google.genai` and cost ~7 s**
   — `core/sprite/generation/video_route.py` (top-level
   `from core.video.omni_client import …` / `veo_client import …`), re-exported
   by `__init__.py:38` and imported by `queue.py:23`.
   *Measured before the fix:* `import core.sprite.generation` = **6.81 s** with
   `google.genai` in `sys.modules`. Sub-projects 5a (GUI tab) and 7 (CLI) import
   this package at startup, so every GUI launch and every `python main.py
   --help` would have paid seven seconds — and the core spine had deliberately
   avoided exactly this (`core/sprite/extract.py:50-54` documents the same
   hazard for `core.video`, and `timing.py:30,37` / `cost.py:69` already import
   the clients inside functions).
   **Status: RESOLVED in the working tree** (not yet committed at the time of
   this review). `video_route.py:11,20,34-36,61,85,133,138` now uses
   `from __future__ import annotations` + `TYPE_CHECKING` + function-scope
   imports. Re-measured: **1.58 s, `google.genai` not loaded.** The controller's
   Task 13 ruling also calls for an import-isolation test; confirm
   `test_import_does_not_load_cloud_video_clients` (named in the new module
   docstring) is committed with the fix, otherwise this silently regresses the
   first time someone adds a convenience import.

### Important

1. **`write_image_sidecar` raises `AttributeError` instead of failing quietly —
   every sprite image artifact depends on it.** `core/utils.py:219` catches
   `(OSError, IOError, json.JSONEncodeError)`, but `json.JSONEncodeError` does
   not exist in the standard library. Verified at runtime:

   ```
   >>> with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
   ...     write_image_sidecar(Path("/tmp/x.png"), {"a": 1})
   RAISED: AttributeError module 'json' has no attribute 'JSONEncodeError'
   ```

   Python evaluates the except tuple only when an exception occurs, so the bug
   is invisible until a sidecar write actually fails — and then the intended
   silent `pass` becomes an unclassified `AttributeError`. Three new call sites
   inherit it: `plate.py:68`, `turnaround.py:104`, `source.py:91`. Consequence:
   on a disk-full or permission failure the PNG is already on disk
   (`plate.py:62-66`), the sidecar is missing, and the caller propagates an
   `AttributeError` that has no `user_message` — so the §1.3 error path in 5a/7
   shows a bare traceback instead of a message. This is also the concrete
   resolution of the deferred systemic "PNG before sidecar" item: the ordering
   is not the problem, the swallow is.
   *Why it matters now:* it is a one-line fix in shared code, and after four
   more sub-projects there will be a dozen more call sites relying on the
   documented "never raises" contract.
   *Fix:* `except (OSError, IOError, TypeError):` and log a warning rather than
   `pass`, so a missing sidecar is at least traceable. (Pre-existing — last
   touched in `344e45a`, outside this range — but newly load-bearing.)

2. **`ActionQueue` shares mutable state across threads with no lock.**
   `queue.py:53-54` (`self.pending`, `self.results`), mutated by `enqueue`
   (85-96) and `retry` (98-99) and read/mutated by `run` (104-141).
   Design §1.1 puts every generation job in a `SpriteWorker` QThread while the
   GUI thread stays responsive, and the obvious 5a interaction is "queue more
   cards while the batch renders". Then `run`'s `self.pending.pop(0)` (111) races
   `enqueue`'s `self.pending.append` (94), and — the part that actually
   corrupts state — `enqueue` sets `action.status = "queued"` and
   `self.results.pop(action_id)` (90-92) on a card the worker may have just set
   to `"rendering"` and just written a result for. The list operations
   themselves are safe under the GIL; the read-modify-write sequences around
   them are not.
   *Why it matters now:* 5a builds the queue UI directly on this object, and 6
   adds the image route to it. Adding a lock later means auditing every caller.
   *Fix:* a `threading.Lock` guarding `pending`/`results`/`action.status`
   mutations in `enqueue`, `retry`, and the top of `run`'s loop body — or, if
   single-threaded use is the intent, say so in the class docstring and have
   `enqueue` raise when `run` is active.

3. **A cancelled in-flight action is silently dropped from the queue.**
   `queue.py:111` pops the id before the job starts; the `except Cancelled`
   branch (124-134) sets `action.status = "draft"`, stores a retryable
   `ProviderError`, and `break`s — but never returns the id to `self.pending`.
   The "N action(s) stay queued" message (108) only fires on the *pre-job*
   cancel path, so after a mid-render cancel the user sees one fewer queued card
   than they cancelled, with no message saying so. It is recoverable (the card
   is `draft` and its `error` carries the remote operation id), but only if 5a
   knows to re-enqueue.
   *Why it matters now:* either behaviour is defensible — "cancel means stop"
   or "cancel means pause" — but 5a's queue panel has to be built against one of
   them, and changing it after that panel exists means changing the panel too.
   *Fix:* `self.pending.insert(0, action_id)` before the `break` (and adjust the
   log line to name the true remaining count), or state the drop explicitly in
   the `run()` docstring and cover it with a test.

### Minor

- **`render_action` writes no sidecar on the hard-exception path.**
  `video_route.py:247-250` classifies and re-raises without a sidecar, while the
  soft-failure path writes `status: "failed"` (265). A `SafetyRefusal` or a
  network error therefore leaves no on-disk trace of the attempt.
- **`operation_id` is always `None` in that same handler.** It is assigned only
  after the client call returns (242/246), so a classified exception never
  carries the remote job id. Low impact — the clients swallow nearly everything
  into `result` — but the id is exactly what §1.1 wants preserved.
- **`refine_action` cannot be cancelled and writes no failure sidecar.**
  `video_route.py:304-306` takes no `token`/`cancel_check`; the call at 331 is
  the only uncancellable provider call in the package. Additive to fix
  (keyword-only, defaulted), so not painful later.
- **`trim_to_loop` has no caller anywhere on the branch** (`video_route.py:406`),
  and it hardcodes `search_from=0.5` at 433 instead of exposing
  `find_loop_seam`'s parameter. The design lists it as the mitigation for
  "loops that do not close" (design §6, line 874) and pairs it with 5b's seam
  meter (line 761) — confirm 5b wires it, gated on `action.loop`.
- **`trim_to_loop` extracts every frame with no cancel token**
  (`video_route.py:423`), so a trim of a long clip cannot be interrupted.
- **`import json` at function scope four times** — `video_route.py:152,176,270,325`.
  Style only.
- **`snap_duration` computed twice on the Omni path** — `video_route.py:62` (inside
  `build_omni_config`, result unused for `params`) and again at 212. Pure and
  deterministic, so harmless; the Veo branch reuses `cfg.duration` instead.
- **`classify_provider_error` logs the raw, unredacted exception text.**
  `errors.py:111` passes `raw` and `exc_info=exc` to the module logger while only
  `user_message` is redacted (112). `imageai_current.log` is auto-copied to the
  working directory on exit and users routinely attach it to issues, so a Google
  error carrying `?key=AIza…` reaches a shared file. No other ImageAI module
  redacts logs either, so this is consistent with the codebase and defensible
  against the "log every error in full" rule — but the redaction helper is two
  lines away if the standard tightens.
- **`_veo_rate` builds a client via `__new__`** (`cost.py:78`). Safe today —
  `VeoClient.estimate_cost` reads only its `config` argument
  (`veo_client.py:1151-1182`) — and the comment says so, but it breaks silently
  if `estimate_cost` ever touches `self`.
- **The queue always records `actual_usd=None`** (`queue.py:119`), so the ledger
  only ever holds estimates, and a re-render appends a second row for the same
  action. Honest (no provider reports actual spend) but worth a note for 5a's
  cost panel so it does not sum duplicates.
- **`_CHAT_FAMILY`'s Anthropic static default is `claude-sonnet-4-6`**
  (`action_cards.py:233`) — legal as a `static_default=`, but a generation
  behind; it only applies when the registry is unreachable.
- **Deferred carry-overs, all confirmed still present and still cosmetic:**
  unused `Path` import in `tests/sprite/generation/conftest.py:2`; plate response
  log omits per-image byte sizes (`plate.py:52`); `normalize_source` opens the
  image twice (`source.py:84` and again via `analyze_source` at 90);
  `_border_ring` unguarded for images ≤ 2×`ring_width` (`source.py:37-42`);
  pyright closure-narrowing artefact (`action_cards.py:221`); `cancel_check`
  missing from the two `generate_video_async` docstrings.

---

## Deferred-minor triage

| Item | Ruling | Reason |
|---|---|---|
| Unused `Path` import in `tests/.../conftest.py:2` | **LEAVE** | Cosmetic, in a test fixture file; no lint gate flags it. |
| `normalize_source` opens/analyses the image twice (`source.py:84,90`) | **LEAVE** | One extra decode of a single character image at import time; correctness is unaffected and the split keeps `analyze_source` independently testable. |
| `_border_ring` unguarded for images ≤ 2×ring_width (`source.py:37-42`) | **LEAVE** | `ring_width = max(1, min(w,h)//50)`, so the slices only degenerate for a ≤2 px image — not a real character source. Revisit only if 6 lets users import thumbnails. |
| Plate response log omits per-image byte sizes (`plate.py:52`) | **LEAVE** | The full response text and the saved size are already logged; byte counts add little for a single-image edit. |
| **PNG written before sidecar in `plate.py`/`turnaround.py` (systemic)** | **FIX NOW** — but at the real root | The ordering is not the defect. `core/utils.py:219` names a non-existent `json.JSONEncodeError`, so a sidecar write failure raises `AttributeError` instead of the documented silent pass (verified at runtime). Fix that one line (`TypeError`, plus a logged warning); then the ordering is genuinely harmless, because a failed sidecar can neither raise nor pass unnoticed. See Important 1. |
| No mid-pack cancel test for the turnaround (`turnaround.py:74-75`) | **FIX NOW** (cheap) | The existing test cancels before the first view (`test_gen_turnaround.py:79-86`), so the per-view check inside the loop is uncovered. One test — cancel after the first `edit_image` — pins the behaviour 5a depends on. Two lines of fixture change. |
| pyright closure-narrowing artefact (`action_cards.py:221`) | **LEAVE** | Runtime-safe; a type-checker artefact on `min(..., key=lambda f: abs(f - fps_value))`. Not worth a `cast` for noise suppression. |
| `cancel_check` missing from `generate_video_async` docstrings (veo/omni) | **FIX NOW** (cheap) | These are the two production clients other features call. A one-line `Args:` entry each; the parameter is otherwise undiscoverable from the docstring. |
| No Omni cancel-after-terminal test (Veo has one) | **FIX NOW** (cheap) | Veo's `test_poll_returns_finished_video_even_if_cancel_fires_after_done` guards the "do not throw away a paid clip" rule. Omni's `_await_terminal` has the same early-return at `omni_client.py:414-415` and no test. Mirror the Veo test. |
| Three task-11 minors (no failure sidecar on the raise path; repeated `import json`; `snap_duration` computed twice) | **LEAVE**, except the sidecar | The two style items are noise. The missing failure sidecar is listed above as a Minor — worth doing when `refine_action` next gets touched, not worth a commit on its own. |

---

## Assessment

**Ready for downstream sub-projects: yes**, once the working-tree lazy-import
fix is committed with its isolation test and the `core/utils.py:219` one-liner
lands — everything else on the list is either cosmetic or a decision to record
rather than a defect to repair.

The API that 5a/6/7 will consume (`ActionQueue`, `RenderRequest`/`render_action`,
`generate_action_cards`, `record_actual`, `ms_to_fps`,
`SpriteGenerationError.user_message`, the `cancel_check=` hooks) matches the
design exactly, cancellation closes end to end from token to provider poll loop,
and the two production video clients stay backward compatible with all five
existing callers; the two things worth settling before 5a starts are the queue's
thread-safety contract and whether a mid-render cancel re-queues the card,
because the GUI panel will be built against whichever answer is chosen.
