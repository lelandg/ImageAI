# Sprite CLI implementation and acceptance

Last updated: 2026-09-05 11:45

## Result

The CLI exposes 36 named Sprite operations through JSON requests, discoverable
schemas, stable exit codes and a single JSON result on stdout. Progress and
provider logging stay on stderr. Projects remain compatible with the Sprite tab.

The interface covers project creation/copy/deletion, character and reference
images, action cards, settings/configurations, frame editing with persistent
undo/redo, all generation routes, local imports, processing, previews, seven
export formats, eight engine presets and optional ML backend tools. Provider
calls are explicit. ML installation requires confirmation, an active virtual
environment and an available age-aware installer; no packages were installed
during this task.

Structural frame edits and retouches bake accepted RGBA frames into the shared
pipeline. Reprocessing preserves their pixels and ordering; undo/redo retains
older media across repeated edits, including deleting every frame. CLI project
writers use OS locks. Imports and generated replacements preserve accepted data
until candidates validate. Generated sheets with an uncertain layout are retained
for explicit grid import instead of being silently cut through characters.

The source-generation acceptance test exposed missing metadata for explicit image
output paths. The shared CLI save path now writes sidecars for explicit, numbered,
automatic and streaming partial outputs with prompt and generation provenance.

## Live acceptance

An existing `rock_3` project was independently copied into a test library, edited,
processed and exported in both HD and pixel profiles across all seven formats.
The original project was preserved.

Codex created **Lumen, the patient compiler**, a paper-and-brass nautilus carrying
an observatory, through the ImageAI CLI. Google's image provider generated the
source and two sheets: a thinking/orbit loop and an idea/constellation loop.
Both sheets contained six poses despite a request for eight. Visual inspection
identified the mismatch; explicit six-column imports recovered both animations.
A defective first pose was deleted through the CLI, leaving two five-frame loops.

The selected 320×320 GIF, original images, metadata and credit are checked into
`SampleData/SpriteCLI/`. Its frames each last 160 ms. Running `rebuild.py` uses only
public CLI commands and local source assets; the resulting GIF is byte-identical
to the checked-in sample (SHA-256
`2e1673bef73928d8f040d958f042aeeb563f289082fb334b7df4f2f53f65f2ba`).

## Validation and boundaries

- Sprite suite: **811 passed, one skipped** with real local image/video processing
  and exporters, plus mocked provider failure/cancellation tests.
- Image sidecar, storage-path and related Sprite GUI integration: **49 passed**.
- Isolated frame-strip GUI suite: **20 passed**, including preservation of internal
  baked-frame metadata when the GUI edits keying overrides.
- New CLI modules/tests: Ruff passed. Scoped mypy passed, including stricter
  checks on generation/history/project paths.
- Application source compilation passed for `main.py`, `core`, `cli`, `gui` and
  `providers`. Whitespace checks passed. Ruff comparison of every modified
  existing Python file found no added diagnostics and one removed diagnostic.
- Full-project mypy has existing failures: **1,248 diagnostics in this change,
  1,249 with modified existing files shadowed by `origin/main`**. Comparing
  normalized diagnostics found none added and one removed.
- The offline workbench embeds the live schemas for all 36 operations. Its
  requests and PowerShell/POSIX command generation passed offline Node checks.
  Browser rendering was unavailable under the browser tool's local-URL policy.
- Live provider verification covered Google source/sheet generation. An OpenAI
  source attempt failed with a connection error; other paid generation routes
  were exercised with provider doubles. No live ML installation was attempted.
- This repository runs from source. Whole-project GUI launch and a complete
  cross-platform/provider matrix are outside the validation performed here.

## Documentation and release

`Docs/Sprite-CLI-Guide.md` explains the full contract. The offline HTML workbench
has editable requests and copy buttons for every command. `Docs/CodeMap.md` is
regenerated while excluding runtime caches, generated tests and local tool trees.

Independent local Codex review found three defects, all corrected before push:
metadata-only undo removed the clip reference; immediate SIGINT bypassed accepted
remote-operation recovery; and nonfinite saved values escaped the JSON error
boundary. Follow-up review found no remaining actionable findings, with 33
independently run project/history tests passing. The final Sprite suite passed
811 tests with one skip. Strict dispatcher mypy, scoped Ruff and compilation of
the changed modules passed after the fixes.

History restoration now copies retained raw stage generations, preserving original
video references, keying settings, fingerprints and unprocessed imports. Metadata
undo avoids media changes. Cooperative cancellation saves accepted video job IDs;
a second interrupt can force exit. Invalid response values produce a JSON error.

A local Claude review was rejected by automatic approval review as source-code
egress without explicit destination authorization. The independent local Codex
review was completed instead. The configured automated PR review is still a
required publication gate.

The version manager dry run selected minor release 0.49.0. PR publication,
automated review and merge remain pending until their results are available.
