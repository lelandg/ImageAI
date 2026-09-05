# Sprite background modes

Updated: 2026-09-05 08:24

Implemented on `codex/sprite-background-modes`. The initial plan/diagnosis were committed under the standing plan rule; application code and tests remain uncommitted. No push, PR, version bump, provider calls, or modifications to the existing G: project assets were performed.

## Using the feature

In **Sprite > Processing > Background > Output**, choose:

- **Keep original background**: skip background removal and its edge cleanup while retaining the source background within the configured crop. Crop, stabilization, padding, alpha/palette conversion, and upscaling settings still apply. Output profile dimensions specify the exact canvas size; fitting remains proportional. See `2026-09-05-rock-3-export-dimensions.md` for the geometry correction and current verification.
- **Transparent**: use the existing chroma/ML/source-alpha workflow. This remains the default for existing projects.
- **Solid color (GIF)**: remove the existing background using the chosen method, then composite onto the chosen color during GIF export. Enter `#RRGGBB` or use **Choose color**. Editable PNG frames retain alpha.

After changing processing mode, select **Run pipeline**, then **Export** with Animated GIF selected. The Export dialog shows the project's chosen mode/color. Invalid colors and unavailable/stale profile preparation block export instead of silently using previous frames. Background changes are saved with the project and blocked while the affected workers run.

If ImageAI is already running, restart it after saving work to load the updated code.

## Generation and existing projects

Original mode uses the character reference directly for new Omni/Veo generation and for image-sheet/edit-chain generation. It skips chroma plates, chroma prompt instructions, chroma turnaround references, and matte pairs. New imports in this mode retain their original canvas.

A previously generated green-background clip remains green when keying is skipped. The feature cannot recover the original white background from that video. Previously normalized character imports may contain existing padding; reimport with Keep original background selected to preserve the source canvas. Generative providers can still change content, and GIF palette conversion can slightly change colors.

The black guitar motion marks diagnosed in the earlier report are part of the reference artwork. This change deliberately does not erase foreground artwork or overwrite those project frames.

## Implementation

- `core/sprite/project.py`: validated, backward-compatible background settings; original-mode metadata uses actual fitted dimensions and no obsolete pixel palette.
- `core/sprite/pipeline.py` and `pixelart.py`: original-mode bypass and cache invalidation; transparent/solid share keyed caches because the solid color is applied at export.
- `core/sprite/generation/` and `source.py`: original reference generation and intake preservation.
- `core/sprite/exporters/gif.py` and `engine_presets.py`: composite before palette conversion, retain an exact background palette entry, omit transparency for solid/opaque-original GIFs, preserve timing/disposal/repeat, and record mode/color in sidecars/logs.
- `gui/sprite/`: Processing controls, disabled irrelevant controls, worker guards, project autosave, generation controls and export summary.

## Verification

- Full core Sprite suite plus hardcoded-path guard: **652 passed, 1 skipped**.
- Isolated GUI suites: **159 passed** (Processing 30, workspace integration 29, export 45, Character 13, image route 26, Sprite smoke 16). Total core + GUI: **811 passed, 1 skipped**.
- Application compilation with the repository `.venv` Python: `core`, `gui`, `cli`, `providers` passed.
- Full project mypy checked 302 source files: **776 existing diagnostics in 149 files**, identical diagnostic multiset to HEAD using shadow files; no newly introduced diagnostics. This repository does not currently have a clean global typecheck.
- Scoped Ruff comparison: no new diagnostics; pre-existing lint findings remain. Diff whitespace check passed.
- Rendered the actual Processing widget offscreen with Segoe UI and inspected the new controls.
- Independent agent review found and resolved metadata sizing, stale disabled-profile export, and original-sheet slicing issues.
- Additional read-only Claude review was attempted with restricted tools, but authentication failed because its OAuth session expired. No Claude review is claimed.

Tests use temporary files and mocked provider calls. Windows-only path assertions were made platform-neutral. Sprite GUI settings fixtures explicitly use temporary INI files because native Windows QSettings use the registry and cannot be redirected by setting an INI search path. Test discovery ignored pre-existing inaccessible `_Research`, `_screenshots`, `_transfer` junctions and used an in-memory local `tests` namespace to avoid an installed package of the same name. GUI files were run in separate processes to avoid the suite's known Qt teardown instability.
