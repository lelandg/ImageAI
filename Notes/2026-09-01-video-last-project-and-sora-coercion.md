# Video tab: stale auto-load key and Sora coercion (2026-09-01)

## Symptom

The "Provider Removed" dialog appeared at every startup, even after the user
created a new video project.

## Root cause

Startup reloads `QSettings("ImageAI", "VideoProjects")/last_project`. Only
the two open paths wrote that key. New Project and Save never touched it, so
the key still pointed at an old project saved with `openai sora`. The loader
coerced that provider to Gemini Omni in the combo only, and nothing wrote the
change back, so the dialog fired on every launch.

## Fix (`gui/video/workspace_widget.py`)

- New helper `_remember_last_project(path | None)` owns the key. Open, load,
  Save, and Save As call it with the saved path. New Project calls it with
  `None`, so an unsaved new project does not reload the previous one.
- New helper `_coerce_legacy_video_provider()` moves a `sora` / `openai sora`
  project to Gemini Omni in the combo AND in the in-memory project, then
  shows the warning. Save persists the new provider.

## Tests

`tests/video/test_last_project_tracking.py` (8 tests) runs the widget methods
unbound against stubs, as `tests/gui/test_provider_model_sync.py` does.
Video, GUI, styles, and path-guard suites: 332 passed.

## User action

The key still points at the old project until the next open, save, or New
Project. Open the old project once and save it, or create a new project.
