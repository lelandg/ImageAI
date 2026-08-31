# Final whole-branch review — sub-project 5a (GUI-A)

**Reviewer:** final-ga (senior code reviewer, read-only)
**Range:** `64a9673..76081fd` (12 commits)
**Date:** 2026-08-30
**Method:** read in passes — the review context, the plan header, global constraints, all nine
task interface lists, the Self-review and the 14 recorded deviations; design spec §1.1, §1.3, §1.5,
§1.6, §4.5, §5 and decisions 8 and 9; then the full source portion of
`review-64a9673..76081fd.diff` (configs.py, main_window.py, gui/sprite/*, gui/video/*); then the
consumed core contracts (`core/sprite/generation/{queue,plate,turnaround,action_cards,video_route}.py`,
`core/sprite/{project,pipeline,source}.py`, `core/llm_params.py`, `core/config.py`); then all ten
test modules; then live offscreen probes. Five parallel verification dimensions (spec, threading,
errors, wiring, tests) each ran three independent votes per finding. A finding survives only when a
majority of votes confirm it against HEAD. The working tree, index, HEAD and branches were not
modified. All line numbers cite HEAD `76081fd`.

**Verification actually run (not claimed):**

| Check | Command / probe | Result |
|---|---|---|
| Focused suite | `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest -p no:cacheprovider -q tests/sprite/gui tests/sprite/test_named_configs.py` | **97 passed**, 2 warnings, 41.9 s |
| Wiring tests | same runner, `tests/sprite/gui/test_main_window_sprite_wiring.py` | 10 passed |
| Full suite (controller, 2026-08-30 08:58) | `pytest` | 1623 passed, 19 skipped, 0 failures |
| Path guard | `pytest tests/test_no_hardcoded_paths.py` | passed |
| Qt import isolation | `grep -i 'qt\|pyside' core/sprite/configs.py core/sprite/project.py core/paths.py` | no Qt import (docstring mention only) |
| Plan test-name parity | `comm` of `test_` names in the plan vs `def test_` in the tree | 0 missing functions; only 8 module basenames differ |
| Core signature parity | read every signature the GUI calls by keyword | all keywords exist |
| Slot thread affinity | `probe_partial_thread.py`, real `SpriteWorker` via `WorkerHost.start_job` | `finished` and `progress` both delivered on the main thread |
| Shutdown timeout | `probe_shutdown.py`, job ignores token, `shutdown(timeout_ms=200)` | `_worker` None while `isRunning()` True; second `start_job` accepted |
| Destroy running thread | `probe_destroy.py`, QMainWindow→tab→panel→worker, `win.close()` then exit | `QThread: Destroyed while thread '' is still running`; core dump; exit 134 |
| Stale progress | `probe_stale_progress.py`, shutdown then `set_project(P2)`, old worker emits | P1 progress text and log lines reach the P2 panel; Start enabled |
| Concurrent save | `probe_concurrent_save.py`, 800 saves from 2 threads | 262 `FileNotFoundError` on the shared `.tmp`; 64 reader observations of a missing file |
| `is_busy()` window | `probe_is_busy_window.py`, real `QueuePanel` + fake queue | A's `finished` event dropped after B accepted |
| QMenu leak | `probe_qmenu_leak.py`, 50 right-clicks | 50 `QMenu` children; 0 with `WA_DeleteOnClose` |
| Refine pipeline failure | `test_probe_refine_pipeline_fail.py`, `run_pipeline` raises | dialog shown; `card.status == "rendered"`, `card.error is None` |
| Queue log levels | `test_probe_t7.py`, two 429 retries | console shows `INFO` twice; file logger shows `WARNING` twice |
| Config store overwrite | `probe_cfg/probe.py`, five configs, file unreadable, then `save('x')` | file rewritten with only `x`; no dialog |
| Tab index shift | `probe_tab_shift.py`, saved `current_tab: 4` from base build | HEAD restores `tab_sprite`; `_load_sprite_tab()` runs at startup |
| Vacuous visibility asserts | plugin deletes `progress.setVisible(False)`; runs the two repo tests | 2 passed (regression not caught) |
| Ctrl+Enter on CharacterPanel | `probe_charpanel_ctrl_enter.py` | no `QShortcut`; no `_primary`; no call after Ctrl+Return |
| Wiring substring tests vs broken class | `probe_wiring_substr.py` | all string assertions pass; placeholder absent; lazy load not fired |

---

## Plan/spec alignment — verdict + deviations

**Verdict: aligned, with two unrecorded Minor deviations and one Important threading gap.**

All nine task interface lists are implemented with the promised names and shapes. Every 5b/6 hook
slot exists: `SpriteTab.set_frame_widget` / `set_preview_widget` / `set_processing_widget`,
`actionSelected(str)` on `ActionCardsPanel` and forwarded by `SpriteTab`, `current_action()`,
`add_toolbar_action(text, slot)`, `make_provider(name)`, and `ActionCardsPanel.add_card_action`.
`core/sprite/configs.py` is pure Python with an atomic `tmp + os.replace` write and an undeletable
`Default`. Every core signature the GUI consumes matches the design contract by keyword
(`ActionQueue`, `refine_action`, `make_chroma_plate`, `generate_turnaround`,
`generate_action_cards`, `normalize_source`, `analyze_source`, `suggest_clip_duration`,
`estimate_action`, `estimate_project`, `run_pipeline`). §1.6 storage layout is exact
(`source/character.png`, `source/plate.png`, `source/turnaround/<view>.png`, `clips/<id>.r<N>.mp4`),
all roots come from `get_data_paths()`, and one `QSettings("ImageAI","Sprite")` holds every key
under `sprite/`. Decisions 8 and 9 are visible: per-action Est./Actual cost columns with an
`unknown` count, and a settings dialog that edits all 11 `GenerationSettings` fields with named
configs. §4.5 main-window wiring is complete: lazy placeholder swap, `addToHistoryRequested`,
`closeEvent → shutdown()`, and three Send to Sprite surfaces.

**All 14 recorded deviations match the code.** `SpriteProjectManager` consumed; `cancelled()`
signal; mixin-first dialog; `QGroupBox` panels; `Signal(object)` Path payloads; context menus on
the image label and history view; `GENRE_CHECKLISTS` genres and FPS tooltip; sticky `llm_combo`
under `sprite/llm_provider` with `resolve_model(provider, "chat")`; refine runs
`run_pipeline(upto="stabilize", force=True)`; retry re-enqueues; `QSettings("ImageAI","Sprite")`;
extra tests; `closeEvent` shutdown; all 5b/6 hooks.

**Deviations that landed but are NOT recorded:**

1. §1.5 says every panel binds Ctrl+Enter via `bind_primary_action`. `CharacterPanel` does not
   (Minor 1). The plan's Task 4 interface list omitted it silently.
2. §1.1 says "the panel's Cancel button calls `token.cancel()`". `ActionCardsPanel` has no Cancel
   button, and the token is not consulted inside `make_chroma_plate` or `generate_action_cards`
   (Minor 2).
3. §4.5 names a `sendToSpriteRequested(Path)` signal for all three surfaces. The Image and History
   surfaces call `_on_send_to_sprite` directly from a shared `QMenu` builder; only the Video path
   emits the signal. Behaviour is equivalent and simpler. No finding.

**Threading contract (§1.1):** one `SpriteWorker(QThread)` per job, worker-owned `CancelToken`,
`Cancelled → cancelled()`, all provider/LLM/PIL work inside `job(progress, token)`, and slots that
run on the GUI thread (probe-verified). The "shutdown joins" clause holds only for 5 s. After the
timeout the host forgets a live `QThread`. That gap is Important 1.

**Repo hard rules:** LLM request and response logged in full via `emit()`; `resolve_model()` only;
`get_data_paths()` only; sidecars written for plate and turnaround PNGs; API keys read only through
`config.get_api_key`/`get_auth_mode`. One key-name mismatch on the action-card path is Important 2.

---

## Strengths

- **Stale-event protection is real and pinned.** `WorkerHost._guarded` drops `finished`/`failed`/
  `cancelled` events from a worker that is no longer the host's live worker
  (`gui/sprite/workers.py:102-131`), `_release_worker` is identity-bound, and
  `SpriteTab._apply_project` calls `shutdown()` on all three panels before `set_project`
  (`gui/sprite/sprite_tab.py:253-283`). Two regression tests (`test_sprite_tab_smoke.py:182-262`,
  `test_sprite_worker.py:163-229`) reproduce the exact race and fail if `_guarded` is removed.
- **Slots run on the GUI thread despite the `functools.partial` wrappers.** A live probe on
  PySide6 6.11.1 confirmed `finished` and `progress` delivery on the main thread, so the "bound
  methods only" constraint is met in effect.
- **Job closures capture every input on the GUI thread before dispatch.** No job body reads
  `self.project` or a widget from the worker thread (`character_panel.py:177-223`,
  `action_cards_panel.py:404-410`, `queue_panel.py:196-256`).
- **`SpriteWorker.run` separates `Cancelled`, `SpriteGenerationError` and generic exceptions**, maps
  `user_message` to `failed(str)`, logs with `exc_info`, and drops a result that completes after
  cancel (`workers.py:58-86`).
- **Full LLM logging.** `generate_action_cards` writes provider, model, params (with `api_key`
  stripped), every message and the full response to the file logger and the injected console sink
  (`core/sprite/generation/action_cards.py:284-307`).
- **Lazy load is idempotent and safe under re-entrancy.** `_load_sprite_tab` guards on
  `_sprite_tab_loaded`, swaps the placeholder in place, and the nested `currentChanged` cannot
  recurse (`gui/main_window.py:8239-8248`, `8122-8124`). Send to Sprite before first activation
  loads the tab on demand and bails cleanly when the load fails.
- **Missing-file paths are handled at both layers.** The shared menu disables the action when the
  path is absent, `ReferenceCard` disables it when `reference.path` is missing, and
  `_on_send_to_sprite` shows `show_error` for a vanished file.
- **Tests assert on real side effects**, not on mock return values: files under `project_dir`,
  dataclass mutations, captured Qt signals, console text. Fake signatures match the real ones, so
  kwarg drift at a call site fails the fakes. QSettings and data paths are sandboxed per session.
- **`configs.py` write path is atomic** and `Default` is always first and undeletable.

---

## Issues

### Critical

None.

### Important

**Important 1 — `shutdown()` timeout abandons a running `QThread`; second worker allowed; core dump
on app exit.** `gui/sprite/workers.py:150-158`.
`WorkerHost.shutdown()` cancels, waits at most 5000 ms, logs an error on timeout, and then sets
`self._worker = None` while the thread still runs. Two consequences. (1) `is_busy()`
(`workers.py:134`) returns False, so `start_job` accepts a second job; both workers are parented to
the same panel and write the same output paths (for example `source/plate.png`). (2) The abandoned
`QThread` is still a child of the panel. When `MainWindow.closeEvent` (`gui/main_window.py:7830-7834`)
returns and the widget tree is destroyed, Qt aborts with `QThread: Destroyed while thread '' is
still running`. The timeout is reachable in normal use: `make_chroma_plate` takes no token
(`character_panel.py:203`, `core/sprite/generation/plate.py:25-28`), `generate_action_cards` checks
the token only after the LLM call returns (`action_cards_panel.py:406-409`), and each turnaround
view is one blocking provider call (`turnaround.py:73-75`). A Gemini image call or a LiteLLM chat
call routinely exceeds 5 s.
*Failure scenario:* the user clicks "Make chroma plate" (10-30 s Gemini call) and closes the app.
`closeEvent → SpriteTab.shutdown → CharacterPanel.shutdown` times out, clears `_worker`, the app
tears down, and the process aborts with SIGABRT (probe 2: `timeout: the monitored command dumped
core`, exit 134). Variant: the user opens another project during the plate call; `_apply_project`
times out; the user clicks "Make chroma plate" again; two workers write `source/plate.png` at the
same time (probe: `second start_job allowed: True`).
*Suggested fix:* on timeout do not drop the reference. Keep the worker in a host-level `_orphans`
list, call `worker.setParent(None)`, connect `QThread.finished` to a small reaper that calls
`deleteLater`, and keep `is_busy()` True while any orphan of this host still runs. In
`MainWindow.closeEvent`, when a sprite worker still runs after the bounded wait, wait unbounded
behind a modal "Finishing sprite job…" progress rather than destroy a running `QThread`. Add cancel
checkpoints so the 5 s bound is normally met: thread the token into `generate_action_cards` and
add a token parameter to `make_chroma_plate` (core change; coordinate with sub-project 1's contract).
Note: the plan itself prescribes this `shutdown()` body (plan lines 443-451) and the timeout path is
covered by `test_worker_host_shutdown_timeout_logs_error`. The defect is in the plan, not in the
transcription; the fix must update the plan text as well.

**Important 2 — Action-card LLM call reads the Google key under `"gemini"`, so an API-key Google
user gets no key and falls to the Vertex/ADC route.** `gui/sprite/action_cards_panel.py:399`.
The LLM combo is filled from `get_all_provider_ids()` (`action_cards_panel.py:72-73`), whose Google
entry is `"gemini"`. `generate_cards()` therefore calls `config.get_api_key("gemini")`. The Settings
tab stores the Google key under `"google"` (`gui/main_window.py:4611`) and
`ConfigManager.get_api_key` takes the gcloud branch only for `"google"` (`core/config.py:420`), so
`api_key` is `None` in every auth mode. `build_completion_kwargs` with `auth_mode=None` and no
`api_key` routes to `vertex_ai/<model>` (`core/llm_params.py:513-518`). Existing chat callers map
`gemini → google` before the lookup and forward `auth_mode` (`gui/layout/text_gen_dialog.py:75-90`;
`CharacterPanel._provider_config`, `character_panel.py:247-253`). This panel is the one caller that
does not. This defect surfaced while the reviewers refuted the original "gcloud user gets an auth
failure" claim (see Refuted findings); it has one verifier's static trace plus a code read, not a
live probe, so the fix wave must confirm it with a probe before the change.
*Failure scenario:* the default configuration (Google API key in Settings, no ADC on the machine).
The user clicks "Generate cards". LiteLLM tries `vertex_ai/<model>` with no credentials and fails.
The dialog shows a Vertex credential error that does not name the real cause.
*Suggested fix:* map the combo id to the config key name (`"gemini" → "google"`), read
`config.get_auth_mode("google")`, and pass `auth_mode=` to `generate_action_cards` (the parameter
exists at `core/sprite/generation/action_cards.py:265`). Add a test that asserts the key lookup name
and the forwarded `auth_mode`.

### Minor

**Minor 1 — `CharacterPanel` has no Ctrl+Enter primary action.** `gui/sprite/character_panel.py:48`.
Design §1.5 binds Ctrl+Enter in "every panel & dialog". `ActionCardsPanel` (`action_cards_panel.py:54`),
`QueuePanel` (`queue_panel.py:48`) and `GenerationSettingsDialog` do this; `CharacterPanel` never
calls `bind_primary_action` and has no `_primary`. The omission is not one of the 14 accepted
deviations. Probe: no `QShortcut` on the panel; Ctrl+Return does nothing.
*Failure scenario:* the user focuses the Character panel with a loaded source and presses
Ctrl+Enter; nothing happens, while the same key works in both sibling panels.
*Suggested fix:* bind Ctrl+Enter to `make_plate` with
`bind_primary_action(self, self.make_plate, context=Qt.WidgetWithChildrenShortcut)` and gate it in
`_sync_enabled`; or record "CharacterPanel has two equal actions; no primary" as deviation 15.
Defer-to-5b is acceptable because 5b owns `install_shortcuts`.

**Minor 2 — Cancel token not honored during plate/LLM calls; `ActionCardsPanel` has no Cancel
control.** `gui/sprite/action_cards_panel.py:406`.
The panel builds only `generate_btn`, `Add card`, `Remove selected`, `Render all`
(`action_cards_panel.py:78-104`); `_sync_enabled` disables every control while busy (`:117-121`);
the job checks `token.raise_if_cancelled()` only after `generate_action_cards` returns (`:409`).
`CharacterPanel.make_plate` calls `make_chroma_plate` with no token (`character_panel.py:203`). Probe:
after `cancel_running()`, `token.cancelled == True` but the worker still runs; `shutdown(500)` logs
the timeout.
*Failure scenario:* a LiteLLM call stalls for 60 s. The user has no Cancel button; Ctrl+Enter is
disabled while busy; the panel stays disabled until the provider times out. A project switch runs
into the Important 1 timeout path.
*Suggested fix:* add a Cancel button wired to `cancel_running()` (mirror `CharacterPanel.cancel`);
pass `token` into `generate_action_cards` and `make_chroma_plate` and check it before and after each
provider call. This is the root of Important 1; fix together.

**Minor 3 — `progress` signal is not guarded; a released worker keeps driving the new project's UI.**
`gui/sprite/workers.py:107`.
`worker.progress.connect(on_progress)` bypasses `_guarded`, unlike `finished`/`failed`/`cancelled`
(`:102-105`). After a timed-out `shutdown()`, a still-running worker's progress events reach
`CharacterPanel._on_progress` (`character_panel.py:275`), `ActionCardsPanel._on_progress`
(`action_cards_panel.py:421`) and `QueuePanel._on_progress` (`queue_panel.py:267-276`), which also
calls `self.refresh()` on the new project. Probe: P1 progress text and log lines land in P2's panel;
Start is enabled; the stale status text is never cleared because the terminal event is dropped.
*Failure scenario:* queue worker A for P1 is abandoned by `_apply_project`; the user opens P2; P2's
queue panel shows "render: P1 clip a" status text and console lines that describe P1 clips.
*Suggested fix:* route `on_progress` through
`functools.partial(self._guarded, worker, "progress", on_progress)`.

**Minor 4 — Concurrent `project.save()` from the queue worker and GUI autosave.**
`gui/sprite/queue_panel.py:177`.
`ActionQueue.run()` calls `self.project.save()` on the worker thread after every action
(`core/sprite/generation/queue.py:182,190,247-251`). While the queue runs, `ActionCardsPanel` stays
editable (`_sync_enabled` checks only its own worker, `action_cards_panel.py:116-121`), so a cell
edit emits `cardsChanged → SpriteTab._autosave → save_project` on the GUI thread
(`sprite_tab.py:181-184,294-300`). Both threads write the same `<project>.tmp` and `replace()` it
(`core/sprite/project.py:427-436`); there is no lock. Probe: 800 saves from two threads produced 262
`FileNotFoundError` exceptions and 64 reader observations of a missing project file; a valid cell
edit while the queue runs triggered one GUI-thread save.
*Failure scenario:* on Windows, the worker holds `project.tmp` open while the GUI-thread
`tmp.replace(path)` runs; `PermissionError` pops an error dialog mid-render. On POSIX the last
`replace` wins and a GUI snapshot taken mid-mutation can persist `status="rendered"` with
`clip=None` until the next worker save.
*Suggested fix:* make the GUI the only writer — have `ActionQueue` report "save requested" through
progress and let `QueuePanel` trigger `_autosave` on the GUI thread; or add a `threading.Lock` on
`SpriteProject.save` and take the same lock in `_autosave`.

**Minor 5 — `is_busy()` window lets a new job start before the previous `finished` event is
delivered; the earlier result is then dropped.** `gui/sprite/workers.py:134`.
`is_busy()` uses `isRunning()`, but `finished(object)` is emitted from `run()` before the thread
exits and is delivered later on the GUI thread. In that window `start_job` accepts a new worker,
sets `self._worker` to it, and `_guarded` then drops the older worker's `finished` event.
`QueuePanel.start` is also driven from `ActionCardsPanel` Render buttons, which are enabled
independently of the queue's busy state (`sprite_tab.py:186-189`, `action_cards_panel.py:116-121`).
Probe with a real `QueuePanel`: A's `queueFinished` payload absent; only B's delivered.
*Failure scenario:* worker A finishes while the user clicks Render on another card; `start` sees
`is_busy()` False and starts B; A's `_on_queue_done` never runs — no SUCCESS/ERROR lines for A's
cards, no `queueFinished(results)` for 5b consumers, `_set_running`/autosave skipped until B ends.
*Suggested fix:* define busy as `self._worker is not None` (the release slot clears it on the GUI
thread) and keep `isRunning()` only inside `shutdown()`.

**Minor 6 — Context `QMenu` parented to the label/view is never deleted.** `gui/main_window.py:8279`.
`_build_send_to_sprite_menu` creates `QMenu(parent)`; after `exec()` the C++ object stays a child of
the parent widget. Probe: 50 right-clicks → 50 `QMenu` children; with `WA_DeleteOnClose` → 0. The
same pattern pre-exists in five other gui files; this branch adds two more sites.
*Failure scenario:* a long session with many right-clicks accumulates hidden `QMenu` and `QAction`
objects; small, but unbounded.
*Suggested fix:* `menu.setAttribute(Qt.WA_DeleteOnClose)` before `exec()`.

**Minor 7 — Refine job: pipeline failure leaves card status `rendered` with no `card.error`.**
`gui/sprite/queue_panel.py:249`.
The job sets `card.clip = record; card.status = "rendered"; card.error = None` (`:249-254`) and then
calls `run_pipeline(...)` unguarded (`:255`). Any pipeline exception reaches `failed(str)` and a
dialog, but the card keeps `rendered`, `card.error` stays `None`, and the tooltip is empty.
`ActionQueue._post_process` (`core/sprite/generation/queue.py:236-247`) handles the same case by
recording `action.error = f"pipeline: {exc}"`. Probe: dialog `ffmpeg not found`; `card.status ==
"rendered"`; `card.error is None`; tooltip empty.
*Failure scenario:* refine succeeds (money spent, r2 clip on disk), the extract stage fails. Nothing
tells the user the clip is saved and only the pipeline needs a re-run.
*Suggested fix:* wrap `run_pipeline` in the job — `except Cancelled: raise`, `except Exception as
exc: card.error = f"pipeline: {exc}"`, emit a progress line that says the clip is saved, and return
`record`. Add a test in `test_queue_panel.py`.

**Minor 8 — Queue-level warning/error messages reach the console as INFO (deferred T7).**
`gui/sprite/queue_panel.py:274`.
`ActionQueue` reports failures and retries with `level="warning"|"error"`; the panel wires
`log=lambda m: progress("queue", 0, 0, m)` (`:216-218`) and `_on_progress` re-emits every message as
`INFO`. Probe: two 429 retries show as `INFO` in the console and `WARNING` in the file logger. The
file log holds each line twice (true level via `emit`, INFO via `SpriteTab.log`).
*Failure scenario:* a retry sequence shows three plain INFO lines; only the final `_on_queue_done`
line is red.
*Suggested fix:* give `SpriteWorker` a `log(str, str)` signal and pass a level-aware sink to
`ActionQueue`, or encode the level in the stage name and map it in `_on_progress`.

**Minor 9 — `NamedConfigStore` swallows read errors, so the next save can drop every other saved
configuration.** `core/sprite/configs.py:56`.
`_read()` catches `(OSError, ValueError)`, logs at ERROR and returns `{}` (`:56-58`). `save()` and
`delete()` merge onto that `{}` and `_write()` the result (`:89-103`). Probe: five configs, file
unreadable, `Save as "x"` → file rewritten with only `x`; the dialog shows no error. The plan's
reference implementation contains the same branch, and the plan-mandated test asserts only the
read-side behaviour.
*Failure scenario:* another process holds `sprite_configs.json` open; the user opens Generation
Settings, sees only `Default`, saves as `x`; the five configs are gone, with no dialog.
*Suggested fix:* let `list_names()`/`get()` degrade to empty on `ValueError`, but make
`save()`/`delete()` re-raise `OSError` and refuse to overwrite a file that exists but did not parse
(rename it to `.corrupt` first). The dialog's `except (OSError, ValueError)` paths already
`show_error`.

**Minor 10 — Persisted current-tab index shifts by one after the Sprite tab insert.**
`gui/main_window.py:9219`.
`_save_ui_state` stores a bare `QTabWidget` index (`:8928`) and `_restore_ui_state` replays it
(`:9216-9219`). The branch inserts Sprite at index 4 (`:717`), so a config saved by the previous
build with `current_tab=4` (Settings) now lands on Sprite and, because `currentChanged` is connected
before `_restore_ui_state` runs (`:729`, `:255`), constructs `SpriteTab` at startup. Pre-existing
index-based design; the Layout tab insert caused the same shift before.
*Failure scenario:* one-time, self-correcting on next close.
*Suggested fix:* persist the tab by `tabText` and restore by lookup, or note the one-time shift in the
changelog. Triage: defer-to-5b-6.

**Minor 11 — Wiring tests assert on `inspect.getsource` text, not behavior.**
`tests/sprite/gui/test_main_window_sprite_wiring.py:72`.
`test_init_ui_adds_sprite_placeholder_after_layout` (`:68-79`) and
`test_video_tab_declares_and_main_window_connects_the_signal` (`:173-179`) check substrings of
`_init_ui`/`_on_tab_changed`/`closeEvent`/`_load_video_tab` source. The remaining eight tests
exercise the unbound methods against a stub, so the routing logic is covered. Probe: a broken class
that keeps the substrings passes every string assertion while the placeholder is absent and the
lazy load never fires. Already deferred T9.
*Failure scenario:* a refactor that keeps the substrings but breaks the hookup ships green.
*Suggested fix:* keep as-is; a real `MainWindow` construction test is expensive. Leland's manual
PowerShell click-through covers the live hookup.

**Minor 12 — Progress-bar hidden assertion is vacuous on never-shown panels.**
`tests/sprite/gui/test_character_panel.py:139` (also `tests/sprite/gui/test_queue_panel.py:109`).
`assert not panel.progress.isVisible()` cannot fail: the panel is never shown, and
`QWidget.isVisible()` returns False for a child of an unshown parent regardless of `setVisible()`.
Probe: a plugin that deletes `self.progress.setVisible(False)` in `CharacterPanel._finish` and
forces `QueuePanel._set_running(True)` leaves both tests green.
*Failure scenario:* a regression that leaves the progress bar on screen after a failure ships green.
*Suggested fix:* assert `panel.progress.isHidden()` (true only after an explicit
`setVisible(False)`) and add the positive half while the job runs (`not
panel.progress.isHidden()` right after `make_plate()`/`start()`).

---

## Deferred-minor triage

| Minor (ledger) | Verdict | Why | Cost if wrong |
|---|---|---|---|
| T4: `set_project` runs `analyze_source` on the GUI thread (`character_panel.py:156`) | defer | One PIL open plus a border-ring numpy pass on one normalized source PNG (≤1024 px), once per project open, wrapped in try/except; outside the §1.1 provider/pipeline contract. | A very large hand-placed PNG freezes the UI for a few hundred ms on open; cosmetic; a one-line move into a worker fixes it later. |
| T4: `make_plate` job has no cancel checkpoint (`character_panel.py:199`) | **fix-now** | This is the path that produces Important 1 (a plate call outlasts the 5 s shutdown bound). `make_chroma_plate` needs a token parameter; coordinate the core change. | Cancel during a plate render waits for one Gemini call and then hits the shutdown timeout; app-exit abort possible. |
| T5: pyright `super().__init__(parent)` false positive (`generation_settings_dialog.py:46`) | drop | Standard `DialogCleanupMixin + QDialog` MRO used across `gui/`; resolves to `QDialog.__init__` at runtime; the repo has no pyright/mypy gate. | Zero runtime cost; one `# type: ignore` if a gate is added. |
| T6: `add_card()` returns `Optional[ActionCard]` (`action_cards_panel.py:294`) | drop | Returns `None` only with no project open; the plan's own code block declares `Optional`; the only caller ignores the return value. The brief line is the stale text. | A 5b/6 caller that assumes non-None without a project raises; the annotation makes that visible. |
| T6 (systemic): panels read `self.project` in worker-finished slots without a guard (`workers.py:121`) | already-resolved | `_guarded` (6366e2f) plus `_shutdown_panel_workers` before `set_project` (b532692): late events are dropped before the panels are repointed. Verified by two regression tests. | A caller other than `SpriteTab` that calls `panel.set_project(None)` mid-run would raise in `_on_cards_done`; no such caller exists. Route switches through `_apply_project`. |
| T7: `_on_progress` always emits INFO (`queue_panel.py:274`) | defer-to-5b-6 (or cheap fix) | Console cosmetics on a surface 5b touches; the file logger already records the true level. Reported as Minor 8. | Duplicated queue lines with a wrong INFO tag in the console; nothing lost. |
| T7: `refine()` stats revision files on the UI thread (`queue_panel.py:241`) | drop | A handful of `Path.exists()` calls on the local clips dir once per click; moving them into the job would race with the worker's `out_mp4` choice. | A slow network mount stalls the click for a few stat calls; no correctness impact. |
| T8: pyright narrowing false positive (`sprite_tab.py:269`) | drop | `busy_label` is captured before `shutdown()` and checked `is not None` before use; correct at runtime; no checker gate. | None at runtime. |
| T8: `plateColorChanged` autosave superset (`sprite_tab.py:170`) | drop | The plan's own code connects it; `_pick_plate_color` writes `project.plate_color` before emitting, so the save persists a real model change. | Removing it loses a picked colour on crash before the next autosave. |
| T9: `_on_send_to_sprite` TypeError branch logs but does not `show_error` (`main_window.py:8261`) | defer | Unreachable from the three shipped surfaces (signal carries a `Path`; menu lambda is gated by `Path(path).exists()`); defensive code that already satisfies the log-every-error rule. 5b/6 add `show_error` if a non-path caller appears. | A future non-path caller gets silence in the UI with one log line; no data risk. |
| T9: wiring tests via `inspect.getsource` (`test_main_window_sprite_wiring.py:72`) | defer | Behavioural tests cover `_load_sprite_tab`, `_on_send_to_sprite` and the menu builder; only the `_init_ui`/`_on_tab_changed`/`closeEvent` hooks rely on text. A headless `MainWindow` is the same cost for every tab. Reported as Minor 11. | A text-preserving refactor that breaks the hookup passes CI and surfaces only in the manual click-through. |
| T9 MANUAL: PowerShell click-through of three Send to Sprite surfaces + lazy load | owed by Leland | Cannot be done headless. | Live hookup unverified until run. |

---

## Refuted findings

- **`_on_send_to_sprite` TypeError path logs but does not show the error** (`main_window.py:8262`):
  the branch is unreachable from every shipped caller — the reference card emits `Path(...)` and
  the shared menu builder disables the action unless `Path(path).exists()` succeeds — and the plan
  prescribes the identical log-and-return body; a guard against a programmer error is not a
  user-facing error.
- **Action-card LLM call omits `auth_mode`, so gcloud Google users get an auth failure**
  (`action_cards_panel.py:399`): the combo id is `"gemini"`, never `"google"`, so
  `get_api_key("gemini")` returns `None` in every mode and the call routes to `vertex_ai/` (the
  correct ADC route for a gcloud user); a gcloud token is never sent as an API key. The inverse
  defect (API-key users get no key) is real and is filed as Important 2.
- **Per-card render failures never reach a dialog** (`queue_panel.py:285`): the plan's Task 7 brief
  states the panel "only shows `user_message`", the plan's `_on_queue_done` is byte-identical to the
  implementation, the required test asserts the ERROR console line plus the `failed` status cell,
  and design §4.5 names status + tooltip + console as the surface; a per-card modal in a batch would
  contradict the spec.
- **`_on_send_to_sprite` TypeError branch has no test** (`test_main_window_sprite_wiring.py:128`):
  the branch is unreachable at HEAD, the plan's Task 9 test list contains no such test, and the
  implemented tests match that list one-for-one; coverage of an unreachable defensive branch is not
  a missed requirement.

---

## Assessment

**Needs fixes.** The branch meets the plan and the design in structure, naming, storage, logging
and wiring, and the suite is green (1623 passed). Two Important defects block trust: the
`shutdown()` timeout path can abort the process on app exit and permits two concurrent workers per
panel; and the action-card key lookup uses the wrong config key name, so the default Google
configuration cannot generate cards. Both fixes are small and local.

**Fix wave (in order):**

1. **Important 1 + Minor 2 + T4 fix-now** — `gui/sprite/workers.py`: keep a timed-out worker as an
   orphan (`setParent(None)`, reaper on `QThread.finished`), keep `is_busy()` True while an orphan
   runs; `gui/main_window.py:closeEvent`: never destroy a running sprite thread; add a Cancel button
   to `ActionCardsPanel`; thread `token` into `generate_action_cards`; add a `token` parameter to
   `make_chroma_plate` and check it around the provider call. Update plan lines 443-451 and record
   the change as deviation 15. Add a test: shutdown timeout → second `start_job` refused; app-exit
   probe no longer aborts.
2. **Important 2** — `gui/sprite/action_cards_panel.py:399`: confirm with a probe (API-key Google
   config, `generate_cards` → inspect the `build_completion_kwargs` route); then map `"gemini" →
   "google"`, read `get_auth_mode("google")`, pass `auth_mode=`. Add a test that asserts the lookup
   name and the forwarded mode.
3. **Minor 5** — `workers.py:134`: `is_busy()` = `self._worker is not None`.
4. **Minor 3** — `workers.py:107`: guard `progress` through `_guarded`.
5. **Minor 7** — `queue_panel.py:249-255`: catch pipeline failure after refine, set `card.error`,
   return `record`; test.
6. **Minor 9** — `core/sprite/configs.py`: `save()`/`delete()` re-raise `OSError`; do not overwrite a
   file that exists but did not parse; test that a subsequent save preserves entries.
7. **Minor 12** — replace the two vacuous `isVisible()` asserts with `isHidden()` plus the positive
   half.
8. **Minor 6** — `main_window.py:8279`: `WA_DeleteOnClose`.
9. **Minor 4** — decide the single-writer design for `project.save()` (GUI-only writer preferred);
   if the change touches `ActionQueue`, defer to 5b/6 and record it; otherwise add the lock now.
10. **Minor 1** — bind Ctrl+Enter on `CharacterPanel` or record deviation 15b; defer to 5b is
    acceptable.
11. **Minor 8, Minor 10, Minor 11** — defer to 5b/6; record in the ledger.

After the fix wave: rerun `tests/sprite tests/gui tests/test_no_hardcoded_paths.py` offscreen, rerun
the destroy-running-thread probe to confirm exit code 0, then the full suite, then re-review the
touched files only.
