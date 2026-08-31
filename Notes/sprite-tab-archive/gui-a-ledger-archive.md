# SDD ledger — plan: /mnt/d/Documents/Code/GitHub/ImageAI/Plans/2026-08-29-sprite-gui-a-plan.md
Chain position: 5a of (1 ✓ → 2 ✓ → 3 keying (running) → 4 pixel-art → 5a → 5b → 6).
Spec: Plans/2026-08-29-sprite-tab-design.md §1.1, §3, §4.5, §5 (reachable).
Pre-flight scan: 38 rows in preflight-scan.md; 0 MISMATCH/CONFLICT (harmless line-number drift on main_window.py anchors — implementers anchor on quoted content). Proceed when plans 3 and 4 are closed out.
Carry-forward: ActionQueue now has an RLock, re-queues a mid-render-cancelled card at head of pending, sliced backoff; core/utils.write_image_sidecar logs + swallows (TypeError, ValueError, OSError).
Task 1: dispatched (impl-ga-1, sonnet) at BASE 64a9673
Task 1: implemented 2d49faf (DONE_WITH_CONCERNS: tests need QApplication.processEvents() after wait() because PySide6 6.11.1 queues cross-thread signal delivery even to lambdas — workers.py untouched). Carry into every later GUI dispatch. Review dispatched (rev-ga-1).
Task 1: Ruling: plan-mandated Important (WorkerHost._release_worker identity-blind reset → chained job loses the running worker handle) ruled FIX — bind release to the specific worker; add a chained-job test. Cost if wrong: ~6 lines.
Task 1: fix round 1/5 (1 addressed, 0 open — identity-bound worker release + chained-job/timeout tests; commits 2d49faf..a7bfe82)
Task 1: complete (commits 64a9673..a7bfe82, review clean)
Task 2: complete (commits a7bfe82..d6e830a, review clean)
Task 3: complete (commits d6e830a..d360a4f, review clean) — prefs via QSettings per brief
Task 4: Ruling: reviewer's plan-mandated Important (set_project runs analyze_source on the GUI thread, character_panel.py:156) downgraded to deferred minor — local PIL/numpy on one image, ~10 ms; the §1.1 rule targets provider/pipeline work. Final review to triage. Cost if wrong: a brief stall on a huge source at project open.
Task 4: minor (deferred): make_plate job has no cancel checkpoint (make_chroma_plate takes no token)
Task 4: ⚠️ carried to Task 8: CharacterPanel never saves the project; SpriteTab must persist on sourceChanged/plateReady/turnaroundReady.
Task 4: complete (commits d360a4f..9c6eb1c, review clean)
Task 5: deviation accepted: delete_btn stays enabled for Default (Qt click() on a disabled button never emits clicked); _on_delete guard refuses + reports
Task 5: minor (deferred): pyright super().__init__(parent) false positive via bare mixin (generation_settings_dialog.py:46)
Task 5: complete (commits 9c6eb1c..fd77baa, review clean)
Task 6: minor (deferred, SYSTEMIC): panels read self.project in worker-finished slots without a None/identity guard — set_project(None)/swap mid-job crashes or writes to the wrong project (action_cards_panel.py:437; character_panel.py:295-312). Final review to triage (WorkerHost-level guard or capture project at job start).
Task 6: minor (deferred): add_card() returns Optional[ActionCard] vs brief's ActionCard
Task 6: ⚠️ carried to Task 8: cardsChanged/renderRequested/refineRequested must be consumed by SpriteTab (save project).
Task 6: complete (commits fd77baa..ca8f2aa, review clean)
Task 7: minor (deferred): _on_progress always emits INFO so queue warnings/errors appear twice (once mislabeled) (queue_panel.py:267-274)
Task 7: minor (deferred): refine() stats revision files on the UI thread before dispatch (cheap)
Task 7: complete (commits ca8f2aa..10240c3, review clean)
Task 8: Ruling: plan-mandated Important (project switch doesn't shut down in-flight panel workers → cross-project writes) ruled FIX at the tab: _apply_project shuts down every WorkerHost panel before switching; resolves the Task 6 systemic minor at its root. Cost if wrong: a running job is cancelled when the user opens another project — the intended behaviour.
Task 8: minor (deferred): pyright narrowing false positive at sprite_tab.py:265-266
Task 8: minor (deferred): plateColorChanged autosave is a superset of the brief's signal list (harmless)
Task 8: fix round 1/5 (1 addressed, 1 sub-case open — stale queued finished event after natural completion; commits 8610a21..b532692). Round 2 dispatched: WorkerHost-level stale-event guard.
Task 8: fix round 2/5 dispatched re-review (commits b532692..6366e2f — WorkerHost stale-event guard, 2 regression tests, 78 GUI tests green)
Task 8: fix round 2/5 (1 addressed, 0 open — WorkerHost._guarded stale-event drop + busy_label; commits b532692..6366e2f). Resolves the Task 6 systemic minor at the root.
Task 8: complete (commits 10240c3..6366e2f, review clean)
Task 9: implemented 76081fd; review dispatched (rev-ga-9). MANUAL STEP for Leland (headless agent could not do it): PowerShell .venv click-through of the three 'Send to Sprite' surfaces + tab lazy-load.
Task 9: minor (deferred): _on_send_to_sprite TypeError branch logs but does not show_error (main_window.py:8255-8258)
Task 9: minor (deferred): wiring tests verify _init_ui/_on_tab_changed/closeEvent via inspect.getsource (repo pattern; no real MainWindow test exists)
Task 9: complete (commits 6366e2f..76081fd, review clean)
Task 10: Steps 1-3 run by controller 2026-08-30 08:58: py_compile clean (12 modules); sprite+gui+path-guard 632 passed; FULL SUITE 1623 passed / 19 skipped / 2 warnings (google._upb DeprecationWarning, third-party) — 0 failures, no fix commit needed.
Task 10: Ruling: Step 5 (tick plan checkboxes + "docs(plans): sprite GUI (A) plan complete" commit) deferred until after the final-review fix wave so the plan closes in one commit — why: a fix wave may add commits the close-out should cover; cost if wrong: none (docs-only commit ordering).
Final review: dispatched as dynamic workflow wf_3f3e2242-e1c (6 dimension reviewers + deferred-minor triage → 3-lens adversarial verify → synthesize final-review.md); package review-64a9673..76081fd.diff (22 files, +3883/-6, 12 commits).
Final review: complete (wf_3f3e2242-e1c, 58 agents; final-review.md) — 0 Critical, 2 Important, 12 Minor, 4 refuted; deferred-minor triage tabled.
Final review: Ruling: Important 1 (shutdown timeout abandons running QThread → second worker + SIGABRT on exit) FIX — orphan list + reaper, is_busy True while an orphan runs, closeEvent joins unbounded after the bounded wait; plan text updated as deviation 15. Cost if wrong: app close blocks for one provider call — better than an abort.
Final review: Ruling: Important 2 (action cards read Google key under "gemini") FIX after a probe confirms the route; map provider id → config key via the same rule the repo's other chat callers use. Cost if wrong: one wrong key name; test pins it.
Final review: Ruling: Minor 2 + T4 fix-now (cancel token into make_chroma_plate / generate_action_cards; Cancel button on ActionCardsPanel) FIX — optional kwargs keep the sub-project 2 contract backward compatible. Minor 3 (guard progress), Minor 5 (is_busy = _worker is not None), Minor 6 (WA_DeleteOnClose), Minor 7 (refine pipeline failure → card.error), Minor 9 (configs save/delete must not overwrite an unreadable store), Minor 12 (isHidden asserts) FIX.
Final review: Ruling: Minor 4 (concurrent project.save) FIX with a process-wide RLock in SpriteProject.save now; the GUI-only-writer redesign is deferred to 5b (touches ActionQueue). Cost if wrong: a mid-mutation snapshot can persist for one save interval; no file corruption.
Final review: Ruling: Minor 1 (CharacterPanel Ctrl+Enter) DEFER to 5b install_shortcuts — the panel has two equal actions; recorded as deviation 16. Minor 8, 10, 11 DEFER to 5b/6. T4 analyze_source-on-GUI-thread, T9 TypeError branch, T9 getsource tests: defer (per triage). T5/T6/T7-refine/T8 pyright/T8 plateColorChanged: drop.
Final review: fix wave 1/1 dispatched — impl-ga-fixA (workers/cancel/key-lookup, brief fix-brief-A.md) + impl-ga-fixB (queue/configs/save-lock, brief fix-brief-B.md) in parallel, no commits (controller commits by path).
Task 10: NOTE — a pre-/clear implementer (impl-ga-10) independently committed the plan close-out as 840a8d8 (docs-only, plan ticks, Last Updated 08:56; 53/54 boxes, Task 9 Step 7 manual left open). Harmless; the controller's deviations 15/16 edit stays in the tree and lands with the fix-wave close-out commit. Fix-wave BASE for the re-review is 840a8d8.
Final review: fix wave 1/1 done — A: c0170e9 (orphan workers + terminal_delivered busy test, guarded progress, cancel token into plate/action cards, Cancel button, gemini→google key map + auth_mode, WA_DeleteOnClose, isHidden tests; probes: destroy-thread exit 0, key-lookup pre/post confirmed); B: c8c9be1 (refine pipeline error → card.error, NamedConfigStore strict save/delete + .corrupt, SpriteProject.save RLock, QueuePanel._on_worker_idle); plan deviations 15-16: 37f54a4. Merged gate 646 passed (sprite+gui+path guard).
Final review: Ruling: fix A's terminal_delivered flag accepted over the brief's literal "_worker is not None" — the flag flips on the GUI thread before the caller's slot, so on_finished→start_job still works and the emit→delivery window no longer reads idle. Cost if wrong: one extra attribute; re-review closure 5 judges it.
Final review: scoped re-review dispatched as workflow wf_50885404-04a (12 closure checks + 2 regression sweeps + 2-lens verify) on review-840a8d8..HEAD.diff.
Final review: re-review complete (wf_50885404-04a, 26 agents): all 12 original findings CLOSED (2 partially: deferred set + idle hook, both covered below); 6 new (1 Important: second shutdown() returned True while an orphan ran → closeEvent skipped join_orphans; 5 Minor in the same orphan window). Ruling: fixed by the controller directly (small, co-located) — commit above; 2 regression tests + ERROR-line assertion; gate 648 passed.
Final review: Ruling: "normally finished workers are never deleteLater'd" (pre-existing, one dead QThread child per job) DEFERRED to 5b — tests and panels inspect the worker after event delivery; adding deleteLater ripples. Cost if wrong: a small per-job leak for the session.
Final review: post-fix full suite (before the re-review fix) 1637 passed / 19 skipped; closing full suite running.
Final review: CLOSED 2026-08-30 11:10 — closing full suite 1639 passed / 19 skipped / 0 failures (0ec7ce9). Sub-project 5a complete: 64a9673..0ec7ce9. Workspace archived into the 5b workspace and removed.
