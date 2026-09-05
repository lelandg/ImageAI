# Sprite CLI implementation checklist

**Last Updated:** 2026-09-05 10:48
**Status:** In Progress
**Progress:** 1/8 tasks complete

## Overview

Expose the Sprite workflow to humans and agents through named CLI operations,
discoverable JSON schemas, structured requests, and machine-readable results.
Use the existing Sprite engine and project format so GUI and CLI interoperate.

## Implementation tasks

- [x] Inspect existing work and create `codex/sprite-cli` from `origin/main`.
- [~] Map GUI features and implement project, action, settings, and frame editing.
- [~] Implement generation, references, imports, processing, previews, and exports.
- [ ] Verify contracts and regression tests, including malformed inputs and cancellation.
- [ ] Test an independent copy of an existing Sprite project.
- [ ] Generate an original self-themed project with two animations; inspect and credit a repository GIF sample.
- [ ] Document commands, refresh CodeMap, run local reviews and release checks, bump version through version manager.
- [ ] Push one feature PR, reconcile automated review, merge when green, and notify the user.

## Decisions

- Keep provider operations explicit. Editing or inspecting a project never generates paid content.
- `--sprite OP` selects an operation; `--sprite-data FILE` supplies structured options, with `-` reading stdin.
- `--sprite schema` exposes supported operations and option schemas.
- `--json` reserves stdout for exactly one result. Human progress and full provider logs use stderr.
- Existing projects are tested through independent copies to preserve the user's accepted outputs.
- Use the Windows `.venv` runtime. No system packages or global configuration changes.
