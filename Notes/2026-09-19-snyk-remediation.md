# Snyk dependency remediation

Checked: 2026-09-19 19:05 America/Chicago

Branch: `codex/snyk-dependency-fixes`, based on `origin/main` at `6ac0ded`.

## Result

The Snyk CLI scan passes locally (exit 0), covering 109 dependencies with zero unignored advisories. The raw scan falls from 98 distinct advisories to three. Those three are the explicitly approved LiteLLM proxy exceptions, expiring 2026-10-19; this is a policy-filtered pass, not an unfiltered zero-finding result. Protobuf is patched without an exception.

## Changes

Security floors cover direct and transitive dependencies. Unused MoviePy was removed because it blocks patched Pillow; video rendering uses FFmpeg directly. Pretty-MIDI was upgraded alongside Setuptools to avoid its removed pkg_resources dependency. The isolated Python 3.12 environment was installed with uv's seven-day publication cutoff; the original checkout's environment is unchanged.

Sprite and Character Animator now use MediaPipe 1.x Tasks, allowing protobuf 5.29.6. Shared factories download official Google models into the configured Models cache, verify pinned SHA-256 digests, enforce a size limit, and publish atomically. The Models storage-move registry includes the new cache. Sprite alpha masks and Character Animator's pose/face coordinate contracts are preserved. Install actions recognize legacy MediaPipe and offer the compatible upgrade. A narrowly scoped early Windows CPython 3.12 WMI guard fixes reproduced native import crashes.

The user approved exactly three SDK-only LiteLLM proxy exceptions after reviewing the remaining scan blockers. [Exception rationale and expiry](../Docs/Snyk-Exceptions.md) and [MediaPipe migration details](../Docs/MediaPipe-Tasks.md) document operational limits and upgrade behavior.

## Validation

- Final policy-aware Snyk CLI 1.1307.3 scan: passed, 109 dependencies, zero unignored findings, exactly three ignored findings.
- Unfiltered scan: exactly the three approved LiteLLM advisories; no Protobuf finding.
- Dependency consistency: 132 installed packages compatible.
- Focused migration, model-cache verification, optional installation UI, matting, and configuration tests: 98 passed, one Windows-specific skip. Earlier SDK, Sprite generation, exporters, CLI sidecars, and image processing gate: 207 passed (overlapping coverage, not an additive total).
- Native Tasks inference with official assets: 512x512 alpha mask, 33x4 pose landmarks, 478x3 face landmarks; finite output and clean resource closure.
- Scoped Ruff correctness checks and full application byte compilation passed. New shared modules pass mypy.
- Whole-project mypy reports the existing 753 errors in 144 files. Unchanged main was checked with the same interpreter: the diagnostic count is unchanged. No claim of a globally clean typecheck.
- The complete non-live suite cannot finish on this Windows runner: native Qt worker/event-loop teardown crashes occur. The isolated ContentInspector crash also reproduces on unchanged main with the same environment. A subsequent run excluding that file hit another Qt event-loop access violation. No claim that the full suite passes.
- Broader tests caught a missing model-cache ownership entry, now corrected. Ordinary tests now use an isolated null keyring backend before application imports; explicit IMAGEAI_LIVE_TESTS=1 retains live credential behavior. Final non-layout run: 1,449 passed, 10 skipped, 19 deselected, one failure. The sole failure is test_logging_redaction.test_message_whose_str_raises_does_not_escape_the_logging_call in pytest log capture; the same test fails on unchanged main with the same interpreter. The final keyring-isolated configuration/install UI gate passed 38 tests with one skip.
- Independent dependency and migration reviews were reconciled: the Pretty-MIDI floor and first-use model download copy were corrected.
- Live paid provider calls and optional GPU stacks were not exercised. Snyk Open Source scanned the base requirements; this does not constitute a Snyk Code or exhaustive optional-manifest audit.

## Evidence

- [Passing policy scan](2026-09-19-snyk-final.json)
- [Unfiltered scan](2026-09-19-snyk-unfiltered.json)

Implementation and local verification are complete. Delivery proceeds through the version-manager patch release and the configured automated PR review; merge is authorized after reviews pass. GitHub records the delivery state.

## PR review follow-up

The configured CL PR Reviewer approved PR #53 without blockers. Follow-ups restore CodeMap symbols when the checkout lives under a .codex ancestor, pin verified model URLs to immutable version 1, declare packaging explicitly, and reduce/redact committed scan evidence. The hosted Snyk project now has exactly the three approved expiring exceptions, configured to stop ignoring once a fix is available. A fresh hosted check is required before merge.

Review follow-up validation: final combined focused gate passed 103 tests with one platform skip; new helper mypy and scoped Ruff passed. Immutable model URLs downloaded bytes matching all three existing hashes. Model-mask and legacy-runtime error tests passed, and module-level availability mocking was removed.
