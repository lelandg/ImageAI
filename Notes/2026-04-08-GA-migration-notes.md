# GA Endpoint Migration — Completion Notes

**Date completed:** 2026-04-08
**Deadline:** 2026-06-30 (Google Cloud discontinues legacy Imagen + Veo endpoints)
**Affected GCP project:** `gen-lang-client-0898520379`
**Plan:** [`Plans/2026-04-08-GA-endpoint-migration.md`](../Plans/2026-04-08-GA-endpoint-migration.md)
**Source email:** `[Action Required] Migrate to newly available Cloud AI Image and Video GA endpoints` (received 2026-03-23)

## What changed

All references to the following Google Cloud endpoints were removed from runtime code, and legacy IDs from saved configs/projects are transparently migrated or aliased:

| Discontinued | Replacement |
|---|---|
| `imagegeneration@002…006`, `imagetext@001`, `imagen-3.0-*`, `imagen-4.0-*`, `imagen-3.0-capability-00{1,2}` | `gemini-2.5-flash-image` (via `GoogleProvider.resolve_model_alias`) |
| `veo-2.0-generate-001` | `veo-3.1-generate-001` |
| `veo-3.0-generate-001` | `veo-3.1-generate-001` |
| `veo-3.0-fast-generate-001` | `veo-3.1-fast-generate-001` |

The Imagen 3 Customization "Strict mode" (`imagen-3.0-capability-001` multi-reference subject preservation) was not simply removed — the user-facing `[1] [2] [3] [4]` prompt syntax is preserved by rewriting the bracket tags into natural-language labels and routing the references through `gemini-2.5-flash-image` using the `reference_images` kwarg, matching the existing Flexible direct-mode path.

## Commits (on `main`)

| # | SHA | Task | Summary |
|---|---|---|---|
| 0 | `7df9967` | Plan | Plan doc committed before implementation |
| 1 | `46ef750` | Task 1 | Drop Veo 3.0/2.0 from `VeoModel` enum + MODEL_CONSTRAINTS + pricing dicts |
| 2 | `b18efcb` | Task 2 | `VideoConfig` defaults + `_migrate_legacy_models` shim + 3 pytest cases |
| 2.1 | `3cd1e81` | Task 2 fix | `copy.deepcopy(DEFAULT_CONFIG)` to prevent nested-dict aliasing (quality review finding) |
| 3 | `dd428e6` | Task 3 | Strip Veo 3.0/2.0 from workspace combobox, tooltip, pricing dicts + `video_project_tab.py` default |
| 4 | `781b19b` | Task 4 | Delete `ImagenCustomizationProvider`, rewrite strict-mode branch to use Gemini multi-reference (615 lines removed) |
| 5 | `e9e8c30` | Task 5 | Drop Imagen 3/4 from registry, add `LEGACY_IMAGE_MODEL_ALIASES` + `resolve_model_alias` + 2 pytest cases |
| 6 | `20abde3` | Task 6 | Scrub discontinued entries from `scripts/fetch_model_capabilities.py` |
| 7 | _(this commit)_ | Task 8 | Cleanup, CHANGELOG, README, wrap-up doc |

## Test coverage

- `tests/migration/test_legacy_model_migration.py` — 5 pytest cases, all passing
  - 3 for Veo `VideoConfig` load-time migration
  - 2 for the Google provider's legacy Imagen ID alias

## Manual smoke test (Task 7 — YOU run this)

The following must be exercised manually on Windows PowerShell with the full `.venv`:

1. **Launch GUI, Generate tab, Provider: Google** — Model dropdown must contain ONLY the three Gemini entries (Nano Banana Pro / 2 / 1). No Imagen rows.
2. **Video tab** — Veo model combobox must contain ONLY `veo-3.1-generate-001` and `veo-3.1-fast-generate-001`. Cost estimate label should show a non-`N/A` value.
3. **Strict-mode references** — Generate tab, add 2 reference images, set reference widget to strict mode, prompt `A photo of [1] and [2] at the beach`, Generate. Status console should say `Using Strict mode (Gemini multi-reference)` and `Rewritten prompt: A photo of reference image 1 and reference image 2 at the beach` (or the subject_description if set). Image should generate without provider switching.
4. **Legacy video_config migration** — Quit the app, edit `%APPDATA%\ImageAI\video_config.json` (or platform equivalent) and set `"veo_model": "veo-3.0-generate-001"`. Relaunch, confirm Video tab defaults to `veo-3.1-generate-001` and the JSON file on disk has been rewritten.

## Known stragglers (NOT addressed by this migration)

These are either documentation (historical) or user-local throwaway files that this migration intentionally left alone:

### User-local orphan scripts (hidden from git by `.gitignore`'s `test_*.py` rule)
- `test_imagen_customization.py` (repo root) — imports `ImagenCustomizationProvider`, now broken. Delete manually if no longer wanted.
- `test_veo_duration_prompts.py` (repo root) — references `VeoModel.VEO_3_GENERATE` / `VEO_3_FAST`, now broken. Delete manually if no longer wanted.

### Historical design docs (intentionally preserved as point-in-time records)
- `Plans/Google-Imagen3-Multi-Reference-Implementation.md`, `Plans/Phase1-Completion-Summary.md`, `Plans/Phase3-Completion-Summary.md` — document the original Imagen 3 Customization implementation that Task 4 dismantled. Kept as historical record.
- `Plans/VEO_3_1_INTEGRATION_PLAN.md`, `Plans/Veo3-Music-Sync-Strategy.md`, `Plans/Veo3-Continuity-Research.md`, `Plans/MIDI_Timing_Sync_Design.md` — reference `VeoModel.VEO_3_GENERATE` in code examples.

### Developer guides with stale code samples (update in a future doc pass)
- `Docs/Veo3-Frame-Continuity-Guide.md` — 3 code examples using `VeoModel.VEO_3_GENERATE`
- `Docs/Veo3-Duration-Update-Summary.md` — 1 code sample
- `Docs/Veo-Wizard-Integration-Guide.md` — 1 code sample
- `Docs/Reference-Image-System.md` — 1 code sample
- `Docs/Reference-Image-Usage.md` — 2 lines referencing deleted `imagen_customization.py`

These will cause **user confusion** if someone copy-pastes from them — worth scheduling a dedicated docs refresh sprint. The runtime code is correct; the docs are stale.

### `.gitignore` rule blocking legitimate tests
- `.gitignore:207` has a blanket `test_*.py` rule that force-hides any file matching `test_*.py`, including legitimate pytest files under `tests/`. The new `tests/migration/test_legacy_model_migration.py` had to be force-added. A future cleanup should narrow the rule (e.g., add `!tests/**/test_*.py` below the blanket pattern).

## Rollback strategy (in case of field-reported regressions)

The migration is 8 commits on `main` (`7df9967..HEAD`). Any single commit is individually revertable. The most likely regression sources are:

- **Task 4** (strict-mode rewrite) — if users report that multi-reference subject preservation quality is noticeably worse than Imagen 3 Customization, the `str.replace` tag rewrite may be too aggressive or the subject_description fallback may be insufficient. Iterate on the label format.
- **Task 5** (Imagen alias) — if a user has a saved project with a legacy Imagen ID and `gemini-2.5-flash-image` produces an unexpectedly different output, they should see the info log line calling out the alias. Direct them to update the saved project to use the Gemini ID explicitly.

Google's deprecation deadline is **2026-06-30**. After that, any unmigrated code will return `404 Not Found` from Vertex, so the migration is not optional.
