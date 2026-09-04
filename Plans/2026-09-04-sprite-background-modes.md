# Sprite Background Modes Implementation Checklist

**Last Updated:** 2026-09-04 18:52
**Status:** In Progress
**Progress:** 0/5 tasks complete

## Overview

Implement Keep original background, Transparent, and Solid color as persisted Sprite project choices. Original bypasses chroma generation and removal, cleanup, cropping, stabilization, and transparent profile padding. Solid GIFs composite keyed frames onto the selected color; existing projects retain transparent behavior by default.

## Implementation Tasks

- [~] Persist background settings and expose clear Processing controls with synchronized project state.
- [~] Preserve whole input frames through processing and profile resizing; invalidate affected caches on mode changes.
- [~] Bypass chroma generation for original-background video/image routes while preserving loop and reference behavior.
- [~] Implement opaque solid GIF export, exact background palette color, metadata, and export controls.
- [ ] Run scoped regressions, integration checks, final review, and document verified behavior and limitations.

## Notes

- Based on `Notes/2026-09-04-sprite-gif-background-and-artifacts.md`.
- Use proportional fitting with the original aspect ratio for original-mode output; profile cell dimensions act as bounds.
- Existing project media on G: is diagnostic input only and must not be overwritten by tests.
- No provider calls or package installation needed. No push/PR requested.
