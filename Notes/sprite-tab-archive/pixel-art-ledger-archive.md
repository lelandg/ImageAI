# SDD ledger — plan: /mnt/d/Documents/Code/GitHub/ImageAI/Plans/2026-08-29-sprite-pixel-art-plan.md
Chain position: 4 of (1 ✓ → 2 ✓ → 3 keying (running) → 4 pixel-art → 5a → 5b → 6).
Spec: Plans/2026-08-29-sprite-tab-design.md §2, §4.4, §1.2 (reachable).
Pre-flight scan: preflight-scan.md — 1 BLOCKING (keying.apply_profile_alpha not landed) → RESOLVED by keying Task 3 (2506e80); 1 CONFLICT; 1 MISMATCH; rest MATCH.
Ruling: `run_pixel_stage` (Task 7) MUST call `pipeline._reset_dir(out_dir)` before writing, like every sibling runner — carry into the Task 7 dispatch. Cost if wrong: none; prevents orphaned stale frames on re-run.
Ruling: pixel plan Task 1 `anchor_offset(content, cell, anchor)` becomes a thin wrapper that delegates to the landed `stabilize.anchor_offset(anchor, content, cell)` (no duplicated math; plan's tests keep the plan's argument order). Carry into the Task 1 dispatch. Cost if wrong: one extra 3-line function.
Note: per-action `pixel.json` manifest instead of per-frame sidecars — stage intermediates are cache (core-spine rule: no sidecar for stages/), so acceptable; final review to confirm.
Task 1: complete (commits c3aa66c..8743d22, review clean) — anchor_offset wraps stabilize.anchor_offset + oversize check
Task 2: complete (commits 8743d22..8d4b52e, review clean)
Task 3: complete (commits 8d4b52e..fd50268, review clean)
Task 4: Ruling: plan-mandated Important (palette_to_hex duplicates keying.rgb_to_hex without clamping) — FIX by delegating to keying.rgb_to_hex, folded into the Task 5 dispatch (same file) instead of a separate fix round; Task 5's reviewer verifies it. Cost if wrong: one extra review round later.
Task 4: minor (deferred): pyright false positive at pixelart.py:199 (getpalette Optional; quantize always yields P)
Task 4: complete (commits fd50268..68084e2, review clean apart from the carried fix)
Task 5: minor (deferred): no 1-colour palette × floyd test
Task 5: complete (commits 68084e2..14c206d, review clean; Task 4 palette_to_hex fix verified)
Task 6: complete (commits 14c206d..bda3877, review clean) — palette change already invalidates pixel fingerprint via _profile_settings full to_dict
Task 7: Ruling: plan-mandated Important (run_pixel_stage inlines `if token: token.raise_if_cancelled()` ×3 instead of pipeline.check) — FIX folded into Task 8's dispatch (import `check` from pipeline, replace the three inlines); final review verifies. Cost if wrong: none.
Task 7: complete (commits bda3877..cb5ffb5, review clean apart from the carried fix); registration via core/sprite/__init__.py importing pixelart last, code_version=2
Task 8: implemented d362fd6 (check() helper — carried Task 7 fix) + 5549d49 (plan truth-up); full suite 1520 passed / 19 skipped. Ruling: no separate Task 8 review — the final whole-branch review package (c3aa66c..5549d49) covers both commits. Cost if wrong: none.
Final whole-branch review dispatched (final-px, opus).
Final review (pixel-art): 0 Critical, 2 Important (I1 palette_lock=False cross-action overwrite of locked_palette; I2 bare ValueError for bad palette_size/dither/upscale_method), 12 Minor — final-review.md; fix wave dispatched (fix-px).
Final fix wave (pixel-art): 64a9673 (I1 shared palette semantics, I2 PipelineError contract, 6 of 12 minors; 6 left with reasons in final-fix-report.md); full suite 1526 passed / 19 skipped. Scoped re-review dispatched (rerev-final-px).
Final re-review: all addressed, no new breakage. PLAN COMPLETE: c3aa66c..64a9673 (10 commits), full suite 1526 passed / 19 skipped.
