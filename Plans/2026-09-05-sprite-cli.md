# Sprite CLI implementation checklist

**Last Updated:** 2026-09-05 11:45
**Status:** In Progress
**Progress:** 6/8 tasks complete

## Overview

Expose the Sprite workflow to humans and agents through named CLI operations,
discoverable JSON schemas, structured requests, and machine-readable results.
Use the existing Sprite engine and project format so GUI and CLI interoperate.

## Implementation tasks

- [x] Inspect existing work and create `codex/sprite-cli` from `origin/main`.
- [x] Map GUI features and implement project, action, settings, and frame editing.
- [x] Implement generation, references, imports, processing, previews, and exports.
- [x] Verify contracts and regression tests, including malformed inputs and cancellation.
- [x] Test an independent copy of an existing Sprite project.
- [x] Generate an original self-themed project with two animations; inspect and credit a repository GIF sample.
- [~] Document commands, refresh CodeMap, run local reviews and release checks, bump version through version manager.
- [ ] Push one feature PR, reconcile automated review, merge when green, and notify the user.

## Decisions

- Keep provider operations explicit. Editing or inspecting a project never generates paid content.
- `--sprite OP` selects an operation; `--sprite-data FILE` supplies structured options, with `-` reading stdin.
- `--sprite schema` exposes supported operations and option schemas.
- `--json` reserves stdout for exactly one result. Human progress and full provider logs use stderr.
- Existing projects are tested through independent copies to preserve the user's accepted outputs.
- Use the Windows `.venv` runtime. No system packages or global configuration changes.

## Acceptance evidence

- 36 discoverable operations cover project/library management, settings, actions,
  durable frame editing/history, all generation routes, imports, processing,
  seven export formats, eight engine presets and optional backend tools.
- Sprite core suite: 811 passed, one skipped. Integration checks: 49 passed.
  Isolated frame-strip GUI suite: 20 passed.
- Existing `rock_3` project was copied before processing and exporting all formats.
- Created Lumen with two generated animations. The selected credited GIF and its
  source assets are in `SampleData/SpriteCLI/`; the public CLI rebuild produces
  a byte-identical GIF without provider calls.
- Full-project mypy comparison: 1,248 current diagnostics versus 1,249 baseline;
  no added diagnostics. New CLI modules pass scoped mypy and Ruff.
- See `Notes/2026-09-05-Sprite-CLI-Validation.md` for boundaries and release status.
