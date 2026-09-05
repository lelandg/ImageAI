# Sprite image sizing and UX plan

Updated: 2026-09-05 09:55

## Implemented

The Character reference now retains its source pixmap and scales proportionally to its available space whenever the panel resizes. The image receives spare vertical space and can shrink again without its displayed pixmap imposing a large layout minimum.

The animation preview starts in automatic fit mode, scales large frames down and small frames up, and follows splitter/window resizing. Original size (1×) switches to native image dimensions with scrolling and panning; Fit to panel restores automatic fitting. Changing frames preserves the chosen sizing mode. Existing manual zoom shortcuts leave fit mode, and directional zoom no longer reverses direction when fit exceeds manual zoom limits. Shared PixelView users retain manual zoom by default.

The image stays proportional and fully visible in fit mode. Reference rendering uses smooth scaling; sprite preview retains nearest-neighbor rendering and the existing pixel grid. Display size does not change image files, frame dimensions, processing settings, or exports.

## Validation

- 84 targeted GUI tests passed: CharacterPanel 14, PreviewPlayer 11, PixelView 11, shortcuts 8, retouch 11, workspace integration 29. Includes new splitter grow/shrink, native-size toggle, downscale, scrolling, empty-image, and directional zoom regression coverage.
- Rendered and inspected actual CharacterPanel and PreviewPlayer widgets offscreen in fit and original-size modes using synthetic artwork. Explicitly loaded Segoe UI for the sandbox renderer. The running desktop application was not restarted or manipulated; manual native-window/high-DPI verification remains outstanding.
- Scoped Ruff has one existing unused-import diagnostic in PreviewPlayer and no new diagnostics compared with HEAD.
- Project-wide mypy completed with explicit package bases: 1,249 errors versus 1,252 in the HEAD shadow-file baseline, with no added errors after normalizing line numbers. The repository does not have a clean global typecheck. The initial invocation without explicit package bases stopped on duplicate module naming; the corrected invocation completed.
- All application sources compiled using the repository .venv Python. The final typing-only edits were compiled again. Git whitespace validation passed.
- Independent read-only review identified the zoom-direction edge case; it was fixed and tested.

Tests used temporary assets/preferences and mocked provider calls. The default pytest entry hit an installed tests-package collision; rerunning with a local in-memory tests namespace resolved it. Integration-related files ran in separate processes to avoid the known Qt teardown issue. No dependencies were installed.

## Follow-up

[Sprite UI/UX plan](../Plans/2026-09-05-sprite-ui-ux.md) contains seven prioritized improvements with evidence and acceptance criteria: playback continuity, explicit bulk edits, preview freshness, relevant processing controls, clearer queue actions, narrow-pane card editing, and visible undo/recoverable card removal.

Changes remain in the current checkout, uncommitted. No provider jobs, generated-asset replacement, app restart, commit, push, or release was performed. The stale Docs/CodeMap.md can be refreshed separately.
