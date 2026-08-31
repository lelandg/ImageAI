# Implementer contract (ImageAI sprite tab — all sub-projects)

## Environment
- Repo: `/mnt/d/Documents/Code/GitHub/ImageAI`, branch `feat/sprite-tab` (already checked out). Never `cd`; absolute paths only; git runs as `git -C /mnt/d/Documents/Code/GitHub/ImageAI …`.
- Python: `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python`; tests: `$PY -m pytest <abs path> -v`. GUI tests need `QT_QPA_PLATFORM=offscreen` (tests/conftest.py sets it).
- The working tree has unrelated uncommitted changes (deleted root `*.md`, untracked `Notes/*.md`, `feature-documenter.skill.zip`, `.superpowers/`). Never touch, stage, or commit those. Stage only files you create/modify, by explicit path.
- The plan's code blocks are a verified prototype: transcribe them verbatim, then run the tests. Deviate only when a test fails or the brief is self-contradictory — and say so in the report.

## Gate (per task)
- Run this task's tests + `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q`. If you touched a module that has other tests under `tests/sprite/`, run `tests/sprite` once before committing. Do NOT run the full repo suite (the controller owns it). Do NOT push. Never bump the version or edit CHANGELOG.md.
- Commit with the brief's exact commit command (Conventional Commit `feat(sprite): …` if the brief has none). Append to the commit body:
```
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GtoYSE5tdovrpWRGcUUZqE
```

## Rules
- Before you begin: if the brief is unclear or contradictory, reply NEEDS_CONTEXT with specifics rather than guess.
- You do not dispatch subagents — never a helper, never a reviewer. The controller dispatches the review after your report.
- Follow the plan's file structure exactly. If a file grows beyond the plan's intent, report DONE_WITH_CONCERNS; do not split it yourself.
- If in over your head, report BLOCKED with what you tried. Bad work is worse than no work.
- Self-review before reporting: completeness vs. brief; names match the brief exactly; no overbuilding; tests verify real behavior; test output pristine (no warnings).
- If resumed with review findings: fix, re-run the covering tests, append a fix report (what changed, covering tests, command, output) to the same report file, reply with the short status contract.

## Report
Write the full report to the report path given in your dispatch: what you implemented, tests + results (command + output tail), files changed, self-review findings, concerns.
Then reply with ONLY (under 15 lines): **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT; commits (short SHA + subject); one-line test summary; concerns; report path.
