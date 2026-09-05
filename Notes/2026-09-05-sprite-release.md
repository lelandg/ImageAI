# Sprite background and project workflow release

Updated: 2026-09-05 09:26 (local).

The user authorized committing and pushing all completed work in the existing `codex/sprite-background-modes` checkout, including project-library and startup improvements from the separate task.

## Included

- Original, transparent, and solid Sprite background modes, with exact configured export canvases and shared crop/profile settings.
- Cache freshness and export guards, exact solid GIF background colors, and metadata.
- Named/searchable project opening, last-project restoration, Save As with independent media copies, and malformed project handling.
- Deferred Layout/Help startup and corrected lazy-tab selection behavior.

## Checks

- Sprite core: 675 passed, 1 skipped in the completed geometry verification; no subsequent core source changes.
- Affected GUI files plus startup and shared-path tests: 171 passed in isolated processes. The combined GUI process hit a Windows native Qt heap exception during fixture garbage collection; isolated runs passed.
- All application Python sources compiled. This repository is source-run and has no packaging/build configuration; no executable bundle or deployment was produced.
- Ruff comparison across changed Python files: 93 diagnostics versus 94 at HEAD, with no added diagnostics after normalizing line references.
- Project-wide mypy was compared against HEAD shadow files. Two new project-library diagnostics were corrected (saved-setting type validation and the typed QDialog enum). The repository remains non-type-clean; unrelated diagnostics were left in place.
- Git whitespace checks passed. No provider requests, generated asset replacement, global configuration changes, or app restart occurred.

## Release procedure

Refresh origin and check branch history, commit the implementation, review the committed diff, then use the shared version manager for a minor release and changelog. Push the feature branch and its release tag. The user did not request a PR or merge into main.

The version manager check/backfill found no missing tags or changelog sections to create. Historical date disagreements were reported and left unchanged. The existing plan commit is the only original commit ahead of origin/main; no unrelated local-main commits are being published.
