# Scoped re-review — sub-project 6 final-review fix wave

## What you review

**Range:** `4567f8a..dd48719` — 4 commits, 13 files, +531/-55.
`4567f8a` is the state the final review examined. The four commits are the fix wave:

| Commit | Implementer | Findings |
|---|---|---|
| `a9703b5` | A | Important 1 (png_sequence sidecars in the preset manifest), Important 2 (GIF sidecar frame count), Minor 4 (golden `.tres` line-by-line) |
| `0a655b4` | B | Important 3 (pose-step chat model) |
| `d51c164` | C | Important 6 (matte plates out of the frame directory), Important 4 (retouch neighbour provenance), Important 5 (retouch double-log), Minor 1 (bare `log()`), Minor 2 (cancel poll) |
| `dd48719` | D | Important 7 + 8 (busy guards), M9 (undo snapshot for any card), the lost-render guard, the `billed_units` docstring, Minors 5 + 6 (tests) |

**Primary input:** `/mnt/d/Documents/Code/GitHub/ImageAI/.superpowers/sdd/2026-08-29-sprite-image-route-exports-plan/rereview-4567f8a..dd48719.diff` (git log + `--stat` + `git diff -U8`).

**HEAD is `dd48719`.** Every line number you cite must be a line number at HEAD.

## Inputs

| Input | Path |
|---|---|
| The final review that produced these fixes — read the finding you are checking, in full | `.superpowers/sdd/2026-08-29-sprite-image-route-exports-plan/image-route-final-review.md` |
| Controller rulings on the fix wave | `.superpowers/sdd/2026-08-29-sprite-image-route-exports-plan/progress.md` (search "Fix wave") |
| Implementer reports | `final-fix-A-report.md`, `final-fix-B-report.md`, `final-fix-C-report.md`, `final-fix-D-report.md` |
| Plan (13 recorded deviations, global constraints) | `Plans/2026-08-29-sprite-image-route-exports-plan.md` |
| Repo hard rules | `AGENTS.md` |

**Do not trust the implementer reports.** One implementer reported "Status: DONE" twice for a change it had not made; the controller caught it only by reading the source. Verify every closure claim against the code at HEAD.

## Your job

This is a **scoped** re-review, not a fresh whole-branch review. Two questions only:

1. **Is each finding actually closed at the root?** Not patched at the symptom, not closed in a way that only satisfies the new test.
2. **Did the fix introduce a new defect or a regression?** The fix wave touched a shared logging helper, a public export manifest, an exporter sidecar, the frame-directory layout, and two GUI entry points — each has blast radius beyond its own finding.

Do NOT re-litigate findings the final review already **refuted** (there are 8, listed in that document) or triage rows already ruled **defer** or **drop**. The controller has ruled. Two rulings you must treat as settled:
- **Minor 2 is ONE cancel poll, not two.** A second poll after `log_response` fires only on a step's last plate, where it discards a frame the user already paid for and breaks the existing between-steps cancel test. Do not raise its absence.
- **Minor 3 (`deleteLater` on the two new dialogs) is deferred to sub-project 7** on purpose, because `DialogCleanupMixin` deletes nothing by design and 5b's `ExportDialog` shares the pattern. Do not raise it.

## Read-only rules — absolute

- Never mutate the working tree, the index, HEAD, or branches. No `git add`, `commit`, `checkout`, `restore`, `stash`, `reset`.
- **Never write a file inside the repository.** Scratch only under
  `/home/leland/.claude/run/claude-1000/-mnt-d-Documents-Code-GitHub-ImageAI/142c578d-2b8c-4a99-9936-b57d066b736f/scratchpad/`.
- Never dispatch subagents.
- The working tree carries Leland's own unrelated items (deleted root `*.md`, untracked `Notes/*.md`, `feature-documenter.skill.zip`, modified `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`). Ignore them; they are never findings.
- Run tests in the **FOREGROUND** with a 600000 ms timeout:
  `QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest … -q -p no:cacheprovider`.
  Never run the whole suite — the controller owns it.
- Report only what you can cite as `file:line` at HEAD. A clean group returns an empty findings list. Do not pad.

## Severity calibration

| Severity | Meaning |
|---|---|
| **Critical** | Data loss, a crash on a reachable path, a corrupt artifact a user ships. |
| **Important** | The finding is NOT closed; or the fix introduced a user-visible defect, broke a seam sub-project 7 consumes, violated a repo hard rule, or made a test that cannot fail. |
| **Minor** | Style, naming, a coverage gap on obviously-correct code, a docstring that overstates. |

## Repo hard rules that the fix wave could have broken

- Every artifact gets a `.json` sidecar through `core.utils.write_image_sidecar`.
- Every provider call logs the full request and the full response to both the module logger and the `log` callable — **exactly once** on the default path.
- Every user-facing error is logged AND shown.
- No `claude-*` / `gpt-*` / `gemini-*` literal in runtime code. The only permitted exception is the two `MODEL_CAPS["gpt-image-1"]` fallback keys in `image_route.py`, which mirror `providers/openai.py` `_caps_for`.
- No hand-built data paths; `core/paths.py` owns every location.
- Never a dimension, an aspect ratio, or the word "transparent" in prompt text.
- Worker lifetime: `WorkerHost` binds WEAK references into signal partials; `shutdown() -> bool`; a timed-out worker becomes an orphan in `_LIVE_ORPHANS`; every subclass overrides `_on_worker_idle` and never writes `self._worker`.
- `FramesWorkspace.apply_frames(action_id, frames, label)` pushes the undo snapshot itself; a caller passes a NEW deep-copied list and never mutates live `FrameMeta` objects first.

## Output

Return structured results only. Do not write the final document unless you are the synthesizer.
