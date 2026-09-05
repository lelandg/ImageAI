# Sprite projects and startup improvements

Updated: 2026-09-05 06:50

## Delivered

- Sprite restores the last successfully selected project when its tab is first
  constructed, after the workspace and panel signals are connected.
- The remembered reference is relative to the Sprite library for managed
  projects, so it follows a changed Images storage root. External projects use
  an absolute reference. Failed automatic restoration logs a warning without
  opening a blocking dialog and retains the reference for a later retry.
- Open lists saved project names, with search and distinct labels for duplicate
  names. An optional Browse button supports projects outside the library.
  Invalid metadata is logged and skipped without hiding valid projects.
- The project title and save confirmation show the project name. Save As asks
  for a name and copies the project and its internal media into a managed
  project directory. It remaps internal media paths and preserves the original.
  Copying is blocked while workers or Export are active; failed copies clean
  up only their newly created destination.
- Layout and Help now load on first activation. Sprite and Video were already
  lazy, but their placeholder replacement emitted transient tab-selection
  events that could load neighboring tabs. Signal blocking fixes that cascade
  for all four lazy tabs. Help initialization failures are logged and can retry.
- Startup logs now include elapsed constructor time after the history scan,
  initial tabs, session restoration, and application readiness.

## Startup findings

Settings is still constructed at startup because Image/provider/auth handlers
share its controls. Templates is small and still constructed eagerly. History
also remains eager; its disk scan, initial metadata reads, and cleanup are
separate candidates for further measured work. Provider discovery/model-list
population already constructs provider instances, so deleting the explicit
preload call alone would not avoid provider initialization.

An isolated offscreen measurement of the original Help implementation took
0.740 seconds for QtWebEngine import/profile initialization and 0.303 seconds
for synchronous Help construction: 1.043 seconds total. The measurement blocked
external browser requests, used a stub config, and did not start the full app.
This is one local sample of work now deferred until Help opens, not a measured
end-to-end startup improvement. Layout's restoration/rendering cost and the
avoided accidental Video load were not separately benchmarked.

## Verification

- Six initial regression tests failed on the original behavior, including the
  unintended Video load when opening Sprite.
- Final focused suite: **111 passed**, 9 warnings, in 20.42 seconds. Coverage
  includes persistence, failed restores/opens, storage-root moves, named copies,
  copy failure isolation, malformed project entries, filtering/cancel, lazy tab
  activation/retry, existing Sprite integration, and the shared path rules.
- Ruff passes for the Sprite UI changes, new modules, and new tests. Existing
  modified modules introduce no additional lint findings versus HEAD after
  normalizing line-number references in existing diagnostics.
- The two new production modules pass mypy. A broad repository check reported
  776 errors across 149 files; the repository is not type-clean. A separate
  touched-module comparison reported 36 errors versus 37 with HEAD shadow
  files; the apparent added diagnostic was the existing duplicate eventFilter
  definition with its shifted line number.
- Changed production files compile, and git diff whitespace checks pass.
- Visually inspected the actual Open dialog in offscreen Qt with an explicitly
  loaded system font: names, search, duplicate labels, Browse, Open and Cancel
  fit without showing library paths.
- Independent agent review identified malformed-list handling and transient
  storage restore behavior; both findings were addressed.

## Scope and remaining work

Existing Sprite background work was preserved on the current
`codex/sprite-background-modes` branch. The only overlapping production file
edited was `core/sprite/project.py`, with additive validation in list_projects.
No commit, push, package installation, live provider call, or restart of the
user's application was performed. The full application was not benchmarked.
CodeMap regeneration was explicitly deferred by the user.
