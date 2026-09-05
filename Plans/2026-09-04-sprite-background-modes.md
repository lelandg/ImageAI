# Sprite Background Modes Implementation Checklist

**Last Updated:** 2026-09-05 08:24
**Status:** Complete
**Progress:** 5/5 tasks complete

## Overview

Implement Keep original background, Transparent, and Solid color as persisted Sprite project choices. Original bypasses chroma generation and removal plus background edge cleanup; every mode shares crop, stabilization, padding, and output-profile settings. Solid GIFs composite keyed frames onto the selected color; existing projects retain transparent behavior by default.

## Implementation Tasks

- [x] Persist background settings and expose clear Processing controls with synchronized project state.
- [x] Preserve whole input frames through processing and profile resizing; invalidate affected caches on mode changes.
- [x] Bypass chroma generation for original-background video/image routes while preserving loop and reference behavior.
- [x] Implement opaque solid GIF export, exact background palette color, metadata, and export controls.
- [x] Run scoped regressions, integration checks, final review, and document verified behavior and limitations.

## Notes

- Based on `Notes/2026-09-04-sprite-gif-background-and-artifacts.md`.
- Use exact configured output cells in every mode, with proportional fitting, shared crop/padding/anchor rules, and the requested output profile. Background selection must not override geometry.
- Existing project media on G: is diagnostic input only and must not be overwritten by tests.
- No provider calls or package installation needed. No push/PR requested.

- Core generation checks: 108 passed; Character controls: 13 passed; Image route dialog: 26 passed. Pipeline checks: 78 passed. Processing/settings and workspace/project checks passed in isolated runs.
- Project-wide mypy has 776 diagnostics on the baseline; verified this feature adds none. No release/push is requested, so version/changelog remain unchanged.

- Final validation: 652 core tests passed, 1 skipped; 159 GUI tests passed in isolated files. Application compilation passed. See `Notes/2026-09-04-sprite-background-implementation.md` for the full verification record and the expired-auth limitation on the attempted Claude review.

- Geometry correction completed: 675 core tests passed, 1 skipped; 87 Processing/Export GUI tests passed. Real rock_3 Original exports verified at 256 x 256 and 64 x 64 using temporary copies. See `Notes/2026-09-05-rock-3-export-dimensions.md`.
