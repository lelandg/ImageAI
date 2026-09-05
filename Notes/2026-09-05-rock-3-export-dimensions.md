# rock_3 background export geometry fix

Updated: 2026-09-05 08:24 (local).

## Result

Keep original background now uses the same crop, padding, anchor, stabilization, and HD/pixel profile processing as the other background modes. Output cells use their exact configured size. Background removal and its edge cleanup remain bypassed in Original mode, while output alpha, palette, and upscaling settings apply normally. Background mode no longer overrides export canvas or palette metadata.

The original diagnosis found rock_3 saved in Original mode with 16:9 generation and square 256 x 256 / 64 x 64 output profiles. Original mode previously bypassed stabilization and treated profile dimensions as bounds, yielding 256 x 144 / 64 x 36 GIFs. The user clarified that background selection must not override cropping or export geometry; this fix supersedes the earlier recommendation to change modes.

## Changes

- Removed the Original-only stabilization and profile runners; all modes use shared geometry code.
- Kept crop and output-profile controls enabled, and corrected Processing help text.
- Included stabilization, full profile settings, and pixel anchor in cache fingerprints. Bumped processing-stage cache versions so old rectangular outputs cannot be reused.
- Removed Original-only export metadata overrides, including the obsolete palette suppression.
- Added geometry/cache regressions and actual pipeline-to-export tests for all three background modes, square/rectangular profiles, upscaling on/off, PNG, GIF, sprite-sheet, and Aseprite JSON output.

## Verification

- The initial regression failed with 256 x 144 instead of 256 x 256 before the fix.
- Final Sprite core suite: 675 passed, 1 skipped.
- Processing panel and Export dialog suites: 87 passed.
- Actual rock_3 extracted frames were copied into a temporary project and exported through the real pipeline: Original HD GIF 256 x 256, pixel GIF 64 x 64, each retaining all nine frames. PNG sequence dimensions also passed.
- Scoped Ruff passed for production files and core/export tests. Processing-panel GUI tests have ten existing E741 diagnostics in untouched lines.
- Compilation and git diff whitespace checks passed.
- Project-wide mypy completed with 1319 errors across 170 files (304 source files checked); none reported in the changed sections. The repository-wide typecheck is not clean. No provider calls, model downloads, or GPU/AI upscaler execution were tested.
- Independent review found obsolete palette metadata suppression; it was fixed. Final review found no further actionable issues.

## Use

Save any open work and reopen ImageAI to load the changed code. Keep Original selected, select rock_out, run the pipeline, then export. Existing rectangular exports are not rewritten until export runs again.

The saved rock_3 project and its existing assets/exports were not modified. Changes remain in the existing codex/sprite-background-modes checkout alongside prior work; no commit, push, PR, or version release was requested.

Automatic crop bounds may differ between keyed and opaque inputs because alpha cleanup changes the detected foreground; all modes now use the same crop rules and output settings. No image is stretched to force a square aspect.

Docs/CodeMap.md is dated 2026-08-11 and was not regenerated during this fix; a separate refresh is recommended.
