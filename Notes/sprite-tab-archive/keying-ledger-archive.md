# SDD ledger — plan: /mnt/d/Documents/Code/GitHub/ImageAI/Plans/2026-08-29-sprite-keying-plan.md
Chain position: 3 of (1 core-spine ✓ → 2 video-route → 3 keying → 4 pixel-art → 5a → 5b → 6).
Spec: Plans/2026-08-29-sprite-tab-design.md §1.7, §2, §4.3 (reachable).
Pre-flight scan: 37 rows in preflight-scan.md; 1 MISMATCH (Task 9 dejitter test expects flat stabilize settings; real `stabilize_stage_settings` returns `{"stabilize": asdict(...)}`); 1 duplication flag (test centroid helper vs stabilize.alpha_centroid); 0 constraint conflicts.
Ruling: keep the nested `{"stabilize": {...}}` settings shape (consistent with the `key` stage's `{"key": {...}}`); Task 9's test reads `settings["stabilize"]["dejitter"]` / `["dejitter_method"]` — carried into the Task 9 dispatch. Cost if wrong: one test line differs from the plan text.
Ruling: duplicated centroid math in tests/sprite/keying_fixtures.py is acceptable test/prod isolation — LEAVE.
Environment: scikit-image 0.26.0 (released 2025-12-20, 252 days old — passes the 7-day min-age rule) installed into .venv_linux by the controller on 2026-08-29; scipy 1.16.3 already present. Task 8 adds both to requirements.txt (line 37 insertion point verified).
Carry-forward from core spine: core/sprite/__init__.py must import the keying module so its register_stage calls run on package import (design §4.1).
Task 1: implemented 0b64ef5 (chroma_alpha, hex_to_rgb, keying_fixtures); review dispatched (rev-ky-1)
Task 1: minor (deferred): forward-reference unused imports in keying.py (plan-mandated, consumed by later tasks)
Task 1: minor (deferred): hex_to_rgb/chroma_alpha raise ValueError without logging (plan says ValueError; GUI callers must log)
Task 1: complete (commits 15de017..0b64ef5, review clean)
Task 2: minor (deferred): despill argmax tie for magenta key clamps only the first channel (plan formula)
Task 2: complete (commits 0b64ef5..44802e1, review clean)
Task 3: minor (deferred): negative feather_px/despeckle_px silently no-op (only choke_px documents negatives)
Task 3: minor (deferred): multi-clause docstrings (STE style)
Task 3: complete (commits 44802e1..2506e80, review clean)
Task 4: minor (deferred): OVERRIDE_KEYS constant unused by apply_overrides (hardcoded names; plan-mandated)
Task 4: minor (deferred): caplog fixture unused in test_apply_overrides_changes_only_known_keys
Task 4: minor (deferred): key_frame passes un-overridden settings to cleanup_pass (harmless: no cleanup field is overridable)
Task 4: minor (deferred): _ml_alpha lazy import unguarded — fallback belongs to Task 6 matting.ml_alpha (MattingUnavailable)
Task 4: complete (commits 2506e80..ca7d574, review clean)
Task 5: minor (deferred): ffmpeg_chromakey_preview calls hex_to_rgb unguarded (bare ValueError instead of KeyingError)
Task 5: complete (commits ca7d574..3490d8f, review clean)
Ruling (carry into Task 9): keying.py imports core.video.ffmpeg_utils.get_ffmpeg_path at module top (plan-mandated); core/video/__init__ loads google.genai, so wiring keying into core/sprite/__init__ will break the `import core.sprite` isolation pin — Task 9 must make that import lazy (inside ffmpeg_chromakey_preview) and keep tests/sprite/test_package.py green. Cost if wrong: none.
Task 6: minor (deferred): _installed() via find_spec can be True for a broken install → bare ImportError instead of MattingUnavailable (matting.py:139,163; plan-mandated)
Task 6: complete (commits 3490d8f..6e3f1cc, review clean; verdict tail truncated — spec ✅, minors only)
Task 7: complete (commits 6e3f1cc..2aa5816, review clean)
Task 8: minor (deferred): no end-to-end test for an all-transparent frame inside a multi-frame dejitter call (estimate_shift zero-shift path covered)
Task 8: complete (commits 2aa5816..9cdfe07, review clean)
Task 9: deviations accepted (documented): dejitter import placed after CancelToken defs (circular import); keying.get_ffmpeg_path lazy wrapper (monkeypatch seam); override list sized off extract-stage frames (fingerprint stability); __init__.py untouched — registration runs via pipeline.py's `from core.sprite import keying`.
Task 9: minor (deferred): hd_runner alpha post-pass lacks check(token) and progress calls (pipeline.py:305-307)
Task 9: minor (deferred): hd_runner re-reads/writes every frame even when apply_profile_alpha is a no-op
Task 9: minor (deferred): stale comment at tests/sprite/test_pipeline.py:414
Task 9: complete (commits 9cdfe07..4c123f4, review clean)
Task 10: complete (commits 4c123f4..6433d42, review clean)
Task 11: implemented 0ba8e93 (plan checkbox close-out only; full suite 1446 passed / 19 skipped; isolation pins green). Ruling: no separate task review — the diff is plan-file checkboxes; the final whole-branch review package (15de017..0ba8e93) includes it. Cost if wrong: none (no code in the commit).
Final whole-branch review dispatched (final-ky, opus).
Final review (keying): 0 Critical, 3 Important (I1 bad key colour → bare ValueError from run_pipeline; I2 dejitter loads all frames in RAM; I3 constant-alpha spurious skimage phase shift), 10 Minor (8 FIX NOW) — final-review.md; one fix wave dispatched (fix-ky, sonnet).
Final fix wave (keying): 4 commits 2aea02d..c3aa66c (I1-I3 + FIX-NOW rows 2,6,10,11,12,13,14); full suite 1461 passed / 19 skipped. Scoped re-review dispatched (rerev-final-ky).
Final re-review: all addressed, no new breakage. PLAN COMPLETE: 15de017..c3aa66c (15 commits), full suite 1461 passed / 19 skipped.
