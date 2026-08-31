# Task 10 review — Action-cards "Render (image)" button + ImageRouteDialog

Diff reviewed: `review-33050d1..5c6bc95.diff` (1 commit, 3 files, +559).
Focused test run (mine, once):

```
QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest \
  tests/sprite/gui/test_image_route_dialog.py tests/sprite/gui/test_sprite_tab_smoke.py -q -p no:cacheprovider
27 passed in 11.32s
```

No warnings, no errors. The implementer's reported counts (11 task tests, 261 in
`tests/sprite/gui`) are consistent with this. The `tests/sprite/test_retouch.py`
failure the report describes is Task 9's in-flight edit, confirmed by the dispatch;
it is not Task 10's.

## Spec Compliance

✅ Spec compliant.

Every produced name in the brief exists with the mandated shape:
`ImageRouteDialog(DialogCleanupMixin, QDialog)` with `rendered`/`logLine` signals
(`gui/sprite/image_route_dialog.py:48-58`), `build_job()` (155), `start_render()`
(216), `cancel_render()` (230), `generate_steps()` (134), `archive_existing_frames()`
(36), `install_image_route()` (308), `open_image_route_dialog(tab, action, *,
exec_dialog=True)` (294). All 11 brief tests are present in
`tests/sprite/gui/test_image_route_dialog.py`, verbatim except the one declared
deviation.

- **Missing:** none.
- **Extra:** none. The implementation file is the brief's prototype character for
  character; `sprite_tab.py` gained exactly the mandated import plus one call, placed
  right after `install_retouch(self)` (`gui/sprite/sprite_tab.py:29`, `:73-74`).
- **Misunderstood:** none.
- **Declared deviation, accepted:** `_png()` drops the `"RGBA"` mode argument to
  `Image.fromarray` (`tests/…/test_image_route_dialog.py:22`). Pillow removed that
  argument; a zero-filled `(16,16,4)` `uint8` array still yields RGBA. Behaviour is
  identical.

Named-risk checks (one focused check each, all outside the diff):

1. **G9 hand-off — verified correct.** `stage_dir` returns
   `project_dir/stages/<action.id>/extract` (`core/sprite/pipeline.py:133-138`).
   `extract_runner` takes the `action.clip is None` branch and accepts frames an
   importer already placed in `out_dir` (`core/sprite/pipeline.py:340-357`), so the
   dialog's write-then-`run_pipeline(upto="stabilize")` sequence is the supported
   entry point. `archive_existing_frames` **moves** (`Path.rename`,
   `image_route_dialog.py:43`) — never deletes — to the sibling
   `stages/<id>/extract.prev-<YYYYmmdd-HHMMSS>`. That sibling cannot be mistaken for a
   stage: `STAGES` is a fixed tuple and `stage_dir` composes names, it never globs
   (`pipeline.py:89`, `:133-138`). **No slice collision:** `slice_sheet` calls
   `_reset_dir(out_dir)` (`core/sprite/slicing.py:113`), and the sheet source is
   `project_dir/clips/<id>_sheet.png` (`image_route_dialog.py:178`) — a different
   tree — so the clear cannot eat its own input. The archive step also empties
   `extract/` first, so `_reset_dir` has nothing to destroy.
2. **Two modes — verified.** `mode_combo.currentData()` selects `sheet`
   (`generate_sheet` + `slice_generated_sheet`) vs `edit_chain` (`edit_chain` with
   `matte_pairs=matte`), read once at `build_job()` time on the GUI thread
   (`:156-162`); `mode`, `provider_id`, `model`, `frames`, `matte`, `typed_steps` are
   all captured by value. Keyword names match `generate_sheet`
   (`core/sprite/generation/image_route.py:151-162`) and `edit_chain` (`:230-243`).
   The one live-widget read that survives into the worker is in `_make_pose_fn` — see
   Important 3.
3. **Pose-step key lookup — defect, see Important 2.**
4. **`record_actual` — signature correct, coverage incomplete.** The call at
   `image_route_dialog.py:203-205` matches
   `core/sprite/generation/cost.py:125-128` exactly, and `action.clip = None` is set
   first (`:199`) so no video figures leak onto the row. The ledger row does **not**
   land on a partial or failed render — see Important 5.
5. **Frames enter the project through `apply_frames`.** `_on_rendered` restores
   `dialog.frames_before` and hands the rendered list to
   `tab.frames_workspace.apply_frames(action.id, rendered, "Render (image)")`
   (`:288-290`), so the undo snapshot captures the pre-render list.
   `add_card_action` wiring (`:309`) and `refresh_status()` (`:285`) are both present.
   The success path is right; the failure path is not — see Important 4.
6. **Console writes.** The only worker-thread console path is
   `log = self.logLine.emit` (`:163`, `:139`), queued into `console.log`
   (`gui/llm_utils.py:52`). `progress` reaches the GUI through `SpriteWorker.progress`
   (`gui/sprite/workers.py:107-109`). `Cancelled` → `cancelled()` → `_on_cancelled`
   logs at WARNING; `SpriteGenerationError`/`ProviderError` → `failed(user_message)` →
   `_on_failed` logs `logger.error` **and** the console (`workers.py:112-127`,
   `image_route_dialog.py:242-245`). Constraint "every user-facing error is logged" is
   met.
7. **`install_image_route` is one line + one import**, after `install_retouch`.
   `test_sprite_tab_smoke.py` still passes in my run, so tab behaviour is intact.
8. **Tests** use the brief's synchronous-start monkeypatch
   (`monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)`, test file lines
   119, 128, 141) — no real thread starts, so no join is needed and none is missing.
   No `MainWindow`, no repo scratch files: every artifact goes under `tmp_path`.

## Strengths

- The G9 contract is honoured precisely, including the subtle part: seeding
  `action.frames` with `duration_ms = round(1000/fps)` **before** `run_pipeline`
  (`:194-198`) is what makes the frame durations survive, because
  `_sync_frames` carries `prev.duration_ms` across by index
  (`core/sprite/pipeline.py:496-506`). A naive implementation that set durations
  afterwards would have them overwritten.
- `archive_existing_frames` satisfies the "never overwrite raw frames" constraint
  with a move and a returned path that is echoed to the console (`:174`), so the user
  can find the previous take.
- The undo hand-off is genuinely tested, not mocked away: `_FakeTab._apply_frames`
  records the list length *at snapshot time*, and the assertion
  `tab.applied == [("a1", "Render (image)", 0, 1)]` (test line 222) proves the
  snapshot sees the pre-render list and the new list is installed.
- `build_job()` snapshots every widget value on the GUI thread, so the worker never
  races the form.
- Model IDs are never literal: OpenAI comes from `default_openai_edit_model()`,
  Google from `provider.get_default_model()` (`:169-170`). No prompt text is written
  in this file at all.

## Issues

### Critical (Must Fix)

None.

### Important (Should Fix)

1. **Close-while-busy uses the superseded `cancel(); wait(2000); clear` shape**
   (`gui/sprite/image_route_dialog.py:259-263`) — *already ruled by the controller;
   recorded here for completeness, no re-litigation.* Concretely: when `wait(2000)`
   times out (a provider HTTP call that has not reached a token poll), the dialog
   drops its Python reference while the `SpriteWorker` is still a running `QThread`
   **child of the dialog**. Deleting a running `QThread` aborts the process — the
   hazard `gui/sprite/workers.py:30-34` documents. A fix round will mirror Task 9's
   corrected close path.

2. **`_make_pose_fn` skips the `gemini` → `google` config-key mapping — the Task 5a
   bug, reintroduced** (`gui/sprite/image_route_dialog.py:271-274`). The panel's
   provider id comes from `get_all_provider_ids()`, which yields **`"gemini"`** for
   Google (`gui/sprite/action_cards_panel.py:76-83`, `:365-367`); the Settings tab
   stores that key and its auth mode under **`"google"`**. 5a fixed this with
   `CONFIG_KEY_BY_PROVIDER_ID = {"gemini": "google"}` and `_config_key_for()`
   (`action_cards_panel.py:39`, `:369-380`) after a final-review Important. This file
   passes the raw id straight to `tab.config.get_api_key(provider)`, so an API-key
   Google user gets `api_key=None` and falls through to the `vertex_ai/` route — the
   exact failure 5a's docstring describes. The fix is one line: map through
   `_config_key_for` (or the shared constant) before both lookups. The
   `provider in ("google", "gemini")` guard on line 272 shows the author knew both ids
   exist, which makes the unmapped key lookup on line 274 the harder failure to spot.
   **The test cannot catch it:** `_FakeConfig.get_api_key` returns `"test-key"` for
   any argument (test line 172) and `_FakeTab.llm_provider` returns `"google"`
   (test line 187), so `test_pose_fn_uses_panel_provider_and_config` (test line 234)
   asserts the happy id only.

3. **`_make_pose_fn` reads a live widget from the worker thread**
   (`gui/sprite/image_route_dialog.py:271`). `tab.action_cards_panel.llm_provider()`
   is `self.llm_combo.currentData()` (`action_cards_panel.py:365-367`), and the
   closure runs inside `SpriteWorker.run` on both paths — `generate_steps`'s job
   (`:141`) and `build_job`'s edit-chain fallback (`:184`). Qt widgets are not
   thread-safe. 5a's own precedent snapshots provider, mapped config key, api_key and
   auth_mode on the GUI thread **before** the job closure is built
   (`action_cards_panel.py:420-434`); this dialog should do the same. Fixing this and
   Important 2 together is one change: resolve provider + mapped key + api_key +
   auth_mode in `_make_pose_fn`'s outer scope, close over the values.

4. **A failed or cancelled render leaves the action in an inconsistent, unsnapshotted
   state** (`gui/sprite/image_route_dialog.py:194-208`) — *plan-mandated: the brief's
   prototype has this ordering.* The job replaces `action.frames`, sets `clip = None`,
   `status = "rendered"`, `error = None`, then calls `run_pipeline`. If `run_pipeline`
   raises (or the user cancels inside it), control leaves via `_on_failed` /
   `_on_cancelled`, which only log (`:242-250`). The result: the in-memory action now
   holds the new frame list with **no undo snapshot** and **no strip refresh** (the
   `rendered` signal never fires, so `_on_rendered` never runs), `status` still reads
   `"rendered"` and `error` is still `None` although the render failed, and
   `project.save()` (`:208`) was never reached — so the next unrelated save persists
   the half-applied state. The card badge therefore lies to the user after a failure.
   A fix should set `status = "failed"` / `action.error` on the failure path and
   restore `frames_before`, or defer the `action.frames` write until after the
   pipeline succeeds.

5. **No ledger row when generation fails partway — paid calls go unrecorded**
   (`gui/sprite/image_route_dialog.py:203-205`) — *plan-mandated.* `record_actual` is
   reached only after `generate_sheet`/`edit_chain` returns. `edit_chain` bills one
   provider edit per step, two with `matte_pairs` (`core/sprite/generation/image_route.py:266-290`);
   a failure at step 5 of 8 has already spent 5 (or 10) edits and writes nothing to
   `project.cost_ledger`. The action-card badge and the cost panel then understate real
   spend, and a retry compounds it. Recording the units actually consumed on the
   failure path (or wrapping the generation call in `try/finally` around a partial
   `record_actual`) is the fix.

### Minor (Nice to Have)

1. **The sheet test asserts a transient the real pipeline overwrites.**
   `run_pipeline` is a `MagicMock` (test line 46), so
   `assert [f.source_path for f in action.frames] == produced` (test line 77) checks
   the pre-pipeline list. In production `_sync_frames` rebuilds `action.frames` from
   the *stabilize* outputs (`core/sprite/pipeline.py:492-507`), so those source paths
   are never the end state. The `duration_ms` assertion on the next line is the one
   that matters; the `source_path` one documents an intermediate. Consider a test that
   lets a stub `run_pipeline` rebuild the list, to pin the seeding contract.
2. **`FrameMeta.name` is dead work.** `f"{project.name}_{action.name}_{i:02d}"`
   (`:195`) is discarded by `_sync_frames`, which renames to
   `f"{action.name}_{index:02d}"` (`core/sprite/pipeline.py:498`).
3. **Both `SpriteWorker`s are built without `label=`** (`:142`, `:219`), so every log
   line reads `Sprite worker 'job'` (`workers.py:112-127`). `label="image route"` /
   `label="pose steps"` would make the file log readable.
4. **Same-second re-render raises a raw `OSError`.** The archive stamp has
   one-second resolution (`:41-42`); a second render inside the same second renames
   onto an existing directory, which fails on Linux (non-empty target) and always on
   Windows. A uniquifying suffix would keep the destination collision-free.
5. **Workers accumulate on the dialog.** `_set_running(False)` clears
   `self._worker` (`:257`) but each `SpriteWorker` stays a Qt child of the dialog for
   its whole life. Many renders in one sitting leave many finished `QThread` objects.
   A `deleteLater()` on terminal delivery would clean up.
6. **Name shadowing:** the module-level `_on_rendered(tab, action, dialog)` (`:278`)
   and the method `ImageRouteDialog._on_rendered(self, paths)` (`:236`) share a name
   and are two hops apart in the same call chain.
7. **`frames_spin` never writes back to `action.target_frames`** (`:84`), so
   rendering 8 frames leaves the card claiming its old target.
8. **Untested paths:** `cancel_render`, `on_dialog_close`, and the `cancelled()` slot
   have no test. Given Important 1 and 4 both live on those paths, a test would be
   worth adding with the fix round.
9. **No snapshot at all when the rendered action is not the current one**
   (`:287-290`): `apply_frames` is skipped, so that action's frame replacement never
   enters the undo stack. Defensible, but it means undo coverage depends on which card
   is selected.

## Assessment

**Task quality:** Needs fixes — **Reasoning:** The spec is met line for line and the
G9 hand-off, archive-not-delete, and undo-snapshot mechanics all verify correct
against the real collaborators, but `_make_pose_fn` reintroduces 5a's `gemini` →
`google` config-key bug (silently breaking API-key Google users, and masked by the
test's permissive fake config) while reading a combo box from the worker thread, and
the failure path leaves the action with swapped frames, a lying `"rendered"` status,
and no ledger row for edits already paid for.
