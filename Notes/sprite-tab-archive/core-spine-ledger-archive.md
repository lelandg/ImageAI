# SDD ledger — plan: /mnt/d/Documents/Code/GitHub/ImageAI/Plans/2026-08-29-sprite-core-spine-plan.md
Chain (user decision 2026-08-29): 1 core-spine → 2 video-route → 3 keying → 4 pixel-art → 5a gui-a → 5b gui-b → 6 image-route-exports. Sub-project 7 (CLI, PR gate) not in this run.
Spec: Plans/2026-08-29-sprite-tab-design.md (reachable).
Ruling: work directly in /mnt/d/Documents/Code/GitHub/ImageAI on feat/sprite-tab (no worktree) — the branch is already checked out here and every plan hardcodes this path — cost if wrong: unrelated WIP in the tree (Notes/ moves, feature-documenter.skill.zip) sits beside sprite commits; implementers commit only their own files.
Ruling: plan-6 seam edits committed as 069cd07 before any implementation — plan-commit rule.
Pre-flight scan: delegated to a Sonnet agent (plan is 5.6K lines); table appended below when it lands.
Task 1: complete (commits 069cd07..954c79c, review clean)
Pre-flight scan: 70 rows in preflight-scan.md, 0 MISMATCH/CONFLICT rows (pairs, per-task self-consistency, constraints, rubric, repo-surface checks). Proceeding.
Task 2: complete (commits 954c79c..c8706d5, review clean)
Task 3: minor (deferred): settings dataclasses duplicate to_dict/from_dict boilerplate (project.py:104-166, plan-mandated) — mixin candidate
Task 3: minor (deferred): _reanchored SPRITES_DIR_NAME fallback branch (project.py:79-83) untested
Task 3: minor (deferred): delete_project / list_projects failure branches untested
Task 3: complete (commits c8706d5..1489cde, review clean)
Task 4: complete (commits 1489cde..f77bbc9, review clean)
Task 5: complete (commits f77bbc9..eb518d5, review clean)
Task 6: minor (deferred): stage_settings uses .get(stage, _no_settings) instead of direct index (pipeline.py:228-232)
Task 6: minor (deferred): stage_fingerprint re-walks upstream chain, O(n^2) at n=7 (pipeline.py:235-244)
Task 6: complete (commits eb518d5..9efcb15, review clean)
Task 7: Ruling: plan-mandated `_run_ffmpeg` uses blocking subprocess.run, so CancelToken cannot stop ffmpeg mid-run — FIX (Popen + poll token + terminate/kill → Cancelled). Spec §1.1 gives the worker a CancelToken so the user can cancel responsively; a 600 s uninterruptible wait defeats that. Cost if wrong: ~30 lines of extra subprocess handling and one more test; no API change.
Task 7: fix round 1/5 (1 addressed, 0 open — cancellable ffmpeg subprocess; commits 304f92e..7ea19fe)
Task 7: minor (deferred): _terminate falls through unreaped if process survives SIGKILL 2 s (D-state edge)
Task 7: complete (commits 9efcb15..7ea19fe, review clean)
Task 8: minor (deferred): numpy-stub typing artefact at slicing.py:93-94 (mask.any union type); no runtime path
Task 8: complete (commits 7ea19fe..bad4d67, review clean)
Task 9: minor (deferred): pyright narrowing gap at stabilize.py:51,:80 (x1/y1 not in guard; runtime-safe)
Task 9: minor (deferred): no test for union_alpha_bbox / solid_border_bbox "nothing found" branch
Task 9: complete (commits bad4d67..cbe39ed, review clean)
Task 10: complete (commits cbe39ed..b7ae4c3, review clean)
Task 11: complete (commits b7ae4c3..28d12e6, review clean)
Task 12: complete (commits 28d12e6..d7c3158, review clean)
Task 13: Ruling: reviewer's "collision detection" Important is NOT a brief requirement (brief is silent; the reviewer echoed the controller's named risk). Ruled FIX anyway: export_png_sequence raises ValueError when a template renders two frames to the same name — the template is user-typed in 5b's ExportDialog and a silent overwrite loses frames. Cost if wrong: ~5 lines + 1 test; CLI/GUI get a clear error instead of partial output.
Task 13: fix round 1/5 (1 addressed, 0 open — duplicate-name guard; commits 42588c8..42213de)
Task 13: complete (commits d7c3158..42213de, review clean)
Task 14: minor (deferred): pingpong_reverse direction (gif.py:105-107) untested
Task 14: complete (commits 42213de..250f3fa, review clean)
Task 15: complete (commits 250f3fa..16382a0, review clean) — full suite 1174 passed / 19 skipped. All 15 tasks complete; final whole-branch review dispatched (final-cs, opus).
Final review: 1 Critical (C1 stale frames on re-import, slicing.py:109/142), 3 Important (I1 stabilize progress stage name, I2 undo.redo pushes wrong state, I3 exact_n divisor), 7 Minor — report in final-review.md; one fix wave dispatched (fix-cs, sonnet).
Final fix wave: 6 commits 16382a0..83c21b1 (C1, I1, I2, I3, M1-M7 all fixed; +15 regression tests; full suite 1189 passed / 19 skipped). Scoped re-review dispatched (rerev-final-cs).
Ruling: no finishing-a-development-branch / version bump / PR after this plan — Leland's standing decision is ONE PR after the whole chain (plan 7 owns bump + docs + PR); continue straight into plan 2. Cost if wrong: a larger single PR to review.
Final re-review: all 11 addressed, no new Critical/Important. 
Parked — Ruling: `slice_sheet`/`import_png_sequence` now `_reset_dir(out_dir)` before reading sources, so sources located INSIDE out_dir are deleted (no current caller does this). Ruled: leave in core; every downstream caller (5b import dialog, 7 CLI `--sprite-import-frames`) must reject/copy-aside sources under the extract stage dir — carry this into those dispatches. Cost if wrong: a future caller loses user frames; guard is one line when that caller lands.
PLAN COMPLETE: 069cd07..83c21b1 (23 commits), full suite 1189 passed / 19 skipped.
