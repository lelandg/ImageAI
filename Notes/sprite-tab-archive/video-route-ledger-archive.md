# SDD ledger — plan: /mnt/d/Documents/Code/GitHub/ImageAI/Plans/2026-08-29-sprite-video-route-plan.md
Chain position: 2 of (1 core-spine → 2 video-route → 3 keying → 4 pixel-art → 5a → 5b → 6). Core spine complete on feat/sprite-tab.
Spec: Plans/2026-08-29-sprite-tab-design.md §1.1, §1.3, §2, §4.2 (reachable).
Pre-flight scan: 21 rows in preflight-scan.md; 0 interface/constraint conflicts; 6 MISMATCH rows = Task 9 line-number citations into core/video/veo_client.py off by one (content quoted correctly).
Ruling: Task 9 implementer edits veo_client.py by matching the quoted content, not the cited line numbers — cost if wrong: none (content match is the safer anchor).
Carry-forward from core spine: see core-spine-ledger-archive.md (parked slicing self-source hazard; §4.1 seam: core/sprite/__init__ must import keying + pixel modules in plans 3/4 so register_stage runs on package import).
Task 1: Ruling: two plan-mandated Importants ruled FIX — (1) classify_provider_error must chain the original (`__cause__` + `original` attr, log with exc_info) so tracebacks survive `raise classify_provider_error(exc)`; (2) user_message must pass `{exc}` through a `redact_secrets()` helper (Bearer tokens, key=/api_key= query params, AIza…/sk-… shapes) — house rule: never expose credentials. Cost if wrong: ~25 lines + 3 tests; a slightly less verbose user message.
Task 1: fix round 1/5 (2 addressed, 0 open — cause chaining, redact_secrets; commits ae9d811..570e92a)
Task 1: minor (deferred): unused `Path` import in tests/sprite/generation/conftest.py
Task 1: complete (commits 83c21b1..570e92a, review clean)
Task 2: Ruling: reviewer's Critical ("_ASPECT_RE strips times like 10:30") is not a brief requirement (it echoes the controller's named risk) — downgraded to Important and ruled FIX: match only a known aspect-ratio list (Gemini set 1:1,3:2,2:3,3:4,4:3,4:5,5:4,9:16,16:9,21:9 + 16:10,10:16,2:1,1:2,5:3,3:5) instead of any N:M. Cost if wrong: an exotic ratio like 7:5 survives into the prompt text (renders as literal text) — acceptable vs. silently deleting user words.
Task 2: fix round 1/5 (1 addressed, 0 open — known-ratio aspect regex; commits 2b210e8..d72de07)
Task 2: complete (commits 570e92a..d72de07, review clean)
Task 3: minor (deferred): normalize_source opens/analyses the image twice (source.py:107)
Task 3: minor (deferred): _border_ring unguarded for images ≤ 2×ring_width (source.py:54-59)
Task 3: complete (commits d72de07..d80d13d, review clean)
Task 4: complete (commits d80d13d..e34c97e, review clean)
Task 5: complete (commits e34c97e..9087258, review clean) — Omni per-second rate left unverified per brief rule; config override sprite.price_overrides available
Task 6: minor (deferred): plate response log omits per-image byte sizes (plate.py:52)
Task 6: complete (commits 9087258..7d7447c, review clean)
Task 7: minor (deferred): PNG written before sidecar in plate.py/turnaround.py — sidecar-write failure leaves orphan PNG (systemic across generation modules; final review to triage)
Task 7: minor (deferred): no mid-pack cancel test
Task 7: complete (commits 7d7447c..3606a56, review clean)
Task 8: minor (deferred): pyright closure-narrowing artefact at action_cards.py:221 (runtime-safe)
Task 8: complete (commits 3606a56..74a6fae, review clean) — note: zero valid cards → ProviderError (spec), no default card set
Task 9: minor (deferred): generate_video_async docstrings lack an Args line for cancel_check (veo/omni)
Task 9: minor (deferred): no Omni cancel-after-terminal test (Veo has one)
Task 9: complete (commits 74a6fae..78c6035, review clean)
Task 10: complete (commits 78c6035..36dd39b, review clean)
Task 11: Ruling: two plan-mandated Importants ruled FIX — (1) trim_to_loop cuts at (index+1)/fps, keeping the frame that matches frame 0 → visible duplicate at the loop seam; cut at index/fps (exclusive) and make the test assert the seam frame is excluded. (2) render_action success path logs only a one-line summary; log the full result (generation_time, has_synthid, metadata, video_url/path, operation/interaction id) via emit per AGENTS.md. Cost if wrong: (1) loops are one frame shorter than the plan's arithmetic — correct behaviour; (2) more verbose status console.
Task 11: fix round 1/5 (2 addressed, 0 open — exclusive seam trim, full response log; commits dc78b1c..42965f5)
Task 11: minor (deferred): 3 minors listed in task-11-review.md (see file)
Task 11: complete (commits 36dd39b..42965f5, review clean)
Task 12: Ruling: plan-mandated Important (backoff `time.sleep` up to 8 s not interruptible; cancel honoured only after the wait) ruled FIX — chunked sleep that polls the cancel token, consistent with the Task 7 cancellable-ffmpeg ruling. Also folding in the enqueue atomicity minor (validate all ids before mutating). Cost if wrong: ~15 lines + 2 tests.
Task 12: fix round 1/5 (2 addressed, 0 open — interruptible backoff, atomic enqueue; commits 642f725..1f531c0)
Task 12: complete (commits 42965f5..1f531c0, review clean)
Task 13: Ruling: reviewer Critical — `import core.sprite.generation` loads google.genai (~6 s) because video_route.py imports OmniClient/VeoClient at module top (plan-mandated). Ruled FIX: make those two imports lazy (TYPE_CHECKING for annotations, import inside the functions that use them) and pin with an import-isolation test — consistent with timing.py/cost.py which the plan already made lazy and with the core-spine `import core.sprite` pin. Cost if wrong: ~10 lines; a first provider call pays the import instead of package import.
Final review (video route): 1 Critical (lazy imports — Task 13 fix round in flight), 3 Important (core/utils.py:219 json.JSONEncodeError nonexistent → sidecar failure raises AttributeError; ActionQueue no lock; mid-render cancel drops popped action from pending), 13 Minor — final-review.md; one fix wave after Task 13 fix lands.
Task 13: fix round 1/5 (2 addressed pending re-review — lazy imports + isolation test; commits 0b24aec..4b03886). Fix wave dispatched (fix-vr, sonnet): I1 core/utils.py sidecar except, I2 queue lock, I3 cancel re-queue, 4 FIX-NOW minors.
Final fix wave (video route): 3 commits d961b3b..15de017 (I1 utils sidecar except, I2 queue RLock, I3 cancel re-queue, 4 FIX-NOW minors); full suite 1347 passed / 19 skipped. Scoped re-review dispatched (rerev-final-vr) covering 0b24aec..15de017.
Task 13: complete (commits 1f531c0..4b03886, review clean after fix round)
Final re-review: all addressed, no new breakage. PLAN COMPLETE: 83c21b1..15de017 (21 commits), full suite 1347 passed / 19 skipped.
