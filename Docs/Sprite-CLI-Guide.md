# Sprite CLI

The Sprite workflow is available without opening Qt. Humans and agents use the
same project files, processing stages, provider integrations and exporters as
the Sprite tab. Open [the offline workbench](Sprite-CLI-Workbench.html) to build
requests, validate their structure and copy commands for PowerShell or POSIX.

## Start with discovery

This command uses the existing Windows checkout and virtual environment. It
prints one JSON result with `status: "ok"`, `schema_version: 1` and the request
schema for every operation; it makes no provider call.

```powershell
& 'D:\Documents\Code\GitHub\ImageAI\.venv\Scripts\python.exe' 'D:\Documents\Code\GitHub\ImageAI\main.py' --sprite schema --json
```

The workbench has editable paths and a copy button for every request and command.
Its embedded schema is a snapshot; `--sprite schema` from the running checkout is
the authority. To narrow discovery, supply `{"operation":"export"}` as the schema
request. Unknown request fields and invalid types are rejected before dispatch.

| Argument | Meaning |
| --- | --- |
| `--sprite OP` | Operation from the table below. |
| `--sprite-data FILE` | UTF-8 JSON options file; `-` reads JSON from standard input. Omit for `{}`. |
| `--sprite-project PATH_OR_NAME` | Project JSON file, project directory, or unique library name. Prefer the returned absolute project path. |
| `--sprite-root DIRECTORY` | Override the project library. Otherwise use configured Images storage. |
| `--json` | Send the single result object to stdout. Progress and diagnostic output go to stderr. |
| `--sprite-name NAME` | Convenience for a request's `name`; do not also supply `name` in JSON. |
| `--sprite-source IMAGE` | Convenience for `new`'s `source`; do not also supply `source` in JSON. |

## A dependable agent sequence

1. Discover the schema, then `list` and `inspect`. Save returned project paths and
   action IDs instead of guessing filenames or matching partial names.
2. Use `copy` for experiments on an existing project, or `new` to create one.
   Import a character with `source` or `new.source`. These operations use local files.
3. Add actions with `action-edit`, or request generated cards with `cards`.
   Populate each action with `import-frames`, `import-sheet`, `import-video`, or
   `render`. Imports select exactly one action.
4. Run `process`, then `inspect` or `validate`. Export requires current processing
   and complete profile frames. `preview` makes GIFs for headless visual inspection.
5. Edit timing or other settings, process again when needed, and `export` the
   required formats. Read `files` and `manifest` from the result and inspect the
   actual images. A successful process exit does not establish visual quality.

Use explicit action IDs for automation. An `actions` list also accepts exact
names; ambiguous names fail. Omitted action selection generally means all actions.
Exports fail if a selected action has no processed frames, so select completed
actions when a project also contains drafts. Frame indices are zero-based.

## Operations

The 36 operations below summarize each request. Discovery returns every supported field,
enum, nested setting and required property, including conditional requirements
that the command checks against the loaded project.

| Operation | Purpose and principal request fields |
| --- | --- |
| `schema` | All request schemas, or one named `operation`; no project required. |
| `list` | List the library; no project required. |
| `new` | Create a project: `name`, optional `source`, `settings`. |
| `inspect` | Project document, action IDs, media paths and cache freshness. |
| `validate` | Inspect and reject references to missing media. |
| `copy` | Copy project and media under a new `name`. |
| `edit` | Patch project settings; see below. |
| `source` | Import `path` as `kind`: `character`, `plate`, or `turnaround`; turnaround also needs `view`. |
| `action-edit` | `operation`: `add`, `update`, `remove`, `duplicate`, `reorder`; `action`, `values`, `order` as applicable. |
| `frame-edit` | `operation`: `update`, `duplicate`, `delete`, `reorder`, `insert`; `action`, `indices`, `values`, `order`, `paths`, `at`. |
| `undo` | Undo the last compatible CLI edit. |
| `redo` | Reapply an undone compatible CLI edit. |
| `config-list` | List named generation configurations; no project required. |
| `config-save` | Save the project's generation settings under `name`. |
| `config-apply` | Apply generation configuration `name` to the project. |
| `config-delete` | Delete named configuration: `name`, `confirm: true`; no project required. |
| `delete` | Delete the selected project through the project manager; requires `confirm: true`. |
| `purge` | Recycle intermediate clips and stages; requires `confirm: true`. |
| `import-video` | `actions`, `path`, optional `extraction` overrides; retain a project copy of the clip. |
| `import-frames` | `actions`, ordered `paths`, or one `path` to an image/directory. Directory files are sorted by name. |
| `import-sheet` | `actions`, `path`, `columns`, `rows`; optional `cell`, `margin`, `spacing`. |
| `process` | `actions`, `upto`, `force`, `profiles`. Defaults through `pixel`, with caching. |
| `estimate` | Estimate a `route` for `actions`, `frames`, `matte_pairs`; does not generate media. |
| `cards` | Generate action cards from `brief`, `genre`, `character_notes`; optional `replace`. Provider call. |
| `plate` | Generate a chroma plate; optional image provider, model and `aspect_ratio`. Provider call. |
| `turnaround` | Generate `views`, with optional `do_not_change` and provider options. Provider calls. |
| `render` | Generate `actions` using `route`: `video`, `sheet`, or `edit-chain`; optional `frames`, `pose_instructions`, `generate_poses`, `matte_pairs`, `process`, provider options. Provider calls. |
| `refine` | Refine selected video clips using `instruction`; optional `process` and provider options. Provider calls. |
| `loop-trim` | Trim selected video loops using `seam_threshold`; optional `process`. Local processing. |
| `retouch` | Retouch an action's `frame` using `instruction`, optional `region`, `neighbors`, `attempts`, `process`, provider options. Provider calls. |
| `export` | Selected actions/profiles in selected formats or an engine preset; details below. |
| `preview` | Same export options; always writes GIFs. |
| `frame-export` | One action's `index`, optional `profile` (default `hd`) and PNG `output`. |
| `key-preview` | One action in `actions`; optional MP4 `output`, `key_color`, `tolerance`, `softness`. Local chromakey preview over gray. |
| `ml-status` | Inspect the current Python environment, backend availability, versions and model information; no project required. |
| `ml-install` | Explicit `backends` (`mediapipe`, `rembg`), `confirm: true`, optional `dry_run`; no project required. Installs into the running virtual environment. |

## Settings, edits and history

`edit` merges supplied nested settings into the existing project. Its groups are
`generation`, `extraction`, `key`, `stabilize`, `background` and `profiles`; it also
accepts `name`, `brief`, `genre_preset` and `plate_color`. Profile entries patch
the profile identified by `name`, which is `hd` or `pixel`. Unspecified settings
remain in place. For example, `{"background":{"mode":"solid","color":"#102438"}}`
changes GIF background intent without replacing extraction settings.

`action-edit` mutates cards. `frame-edit` mutates the working frame list and
per-frame `duration_ms`, `pivot`, or supported key `overrides`. Reorder requests
must contain each existing item exactly once. CLI insert, delete, duplicate and
reorder operations save the edited visible frames as the action's new processing
source. Their order and count survive forced processing; accepted transparency is
preserved. Re-import the original media if you need to restart background removal
from that original. GUI frame-list changes are not automatically converted this way.

Deleting every frame leaves an empty draft action. Undo restores the prior frames;
redo restores the empty list. Export requires a nonempty processed action, so undo,
insert or import frames before exporting it. Frame override edits preserve internal
processing metadata while replacing the selected user overrides.

To rebuild a pixel palette, use `edit` with
`{"profiles":[{"name":"pixel","locked_palette":null}]}`, then process the chosen
action. `palette_size: null` instead disables quantization; values 1 through 256
select a shared palette size.

CLI undo/redo history is persisted in the project, so it can span CLI invocations.
It covers project/settings/source/action/frame edits and applied configurations,
with up to 50 undo entries. It is separate from the GUI undo stack. An intervening
project change invalidates incompatible history rather than overwriting that
change. Imports, processing, paid generation, exports, configuration deletion,
project deletion and purge are not generic undo transactions. Keep a project copy
when you need a durable return point. Avoid simultaneous GUI and CLI writers:
the CLI lock coordinates CLI processes, and does not lock a running GUI session.

## Sources, processing and generation

Local imports validate and stage replacement frames before accepting them. A
shorter import removes old trailing frames and invalidates downstream stages.
The processing order is `extract → key → cleanup → alpha → stabilize`, followed
by `hd` and `pixel`. Completed processing stages are saved as checkpoints.
Export can prepare a missing profile after current stabilization, but refuses
stale stabilization or incomplete profile output. Follow its error with a
`process` request, then retry the export.

`cards`, `plate`, `turnaround`, `render`, `refine` and `retouch` may charge the
configured provider account. `estimate` gives available estimates, which are not
final billing guarantees. Image provider choices are `google` and `openai`; chat
provider choices include `google`, `openai` and `anthropic`. Video settings use
the project's `omni` or `veo` configuration. Models resolve through ImageAI's
runtime registry when omitted. Credentials come from ImageAI configuration; no
request accepts an inline API key. Use the separate image-generation CLI to make
a new character image, then import that output into the Sprite project.

Turnaround generation and reference imports use the same view names: `front`,
`side`, `back`, and `three_quarter`.

Generated sheets are checked before replacing accepted frames. An ambiguous grid
or a proposed slice crossing foreground pixels fails with the saved sheet path.
Inspect that image, load the workbench's `import-sheet` starter, and supply the
actual `columns`, `rows`, and, when needed, `cell`, `margin`, and `spacing`. Import
into the intended action and process it. This recovery uses the already generated
sheet without another provider call. A confidently detected grid may contain a
different number of poses than requested; the result reports the actual count and
warnings. Original-background sheets use the requested equal-cell layout and
require visual inspection of the pose boundaries.

## Previewing keys and checking ML backends

`key-preview` writes an MP4 composited over neutral gray and a JSON sidecar. It uses
an imported or rendered video clip, and leaves that clip intact. Omitted key color
uses the project's explicit key, a uniform border sampled from extracted frames,
or the requested plate color, in that order. This is the same quick FFmpeg preview
as the GUI, separate from the full cleanup and stabilization pipeline. Projects
keeping the original background use the regular GIF `preview` instead.

`ml-status` is a local inspection. It reports the running Python executable and
virtual environment, module availability and distribution versions, rembg's Python
compatibility, model metadata and installer availability. Importability does not
prove a model has been downloaded or that inference succeeds.

`ml-install` accepts only the selected Sprite backends. It requires the running
Python to be a virtual environment and an installed `uv`; rembg additionally
requires Python 3.11–3.13. It uses the core package specifications and a seven-day
package-age cutoff, targets that interpreter, and does not update requirements
files. There is no unrestricted pip fallback. With `dry_run: true`, it returns the
exact command and package selection without installing anything; set it to `false`
to install the reviewed selection. Both forms require `confirm: true`. The
workbench starts with a dry run. Successful installation reports whether the
modules can now be found and requests an application restart. Model downloads
may still occur on first use.

## Exports

Both enabled profiles export by default; set `profiles` to `hd`, `pixel`, or both.
Available `formats` are `grid`, `aseprite_json`, `texturepacker_json`,
`png_sequence`, `gif`, `godot_tres`, and `aseprite_native`. Engine presets supply
format/layout defaults for `unity`, `godot4`, `phaser3`, `pixijs`, `unreal`,
`libgdx`, `rpgmaker_mz`, and `web_preview`; explicit options override those defaults.

The optional `output` is a directory. Exports go into a subdirectory per profile
and produce a `sprite-export.json` manifest. Generated image outputs also carry
metadata sidecars. `frame-export.output` instead names one PNG file.

`grid` accepts `columns` (0 means one row per tag), `border_px`, `shape_px`,
`inner_px`, `extrude_px`, `power_of_two` and integer `scales`. Scale 1 is included
automatically. Extrusion needs sufficient border and shape padding. `template`
controls PNG sequence names using `{title}`, `{tag}`, `{frame}`, `{tagframe}` and
`{frame01}`; names must be unique. `pivot` is normalized `[x,y]`; `json_layout`
is `hash` or `array`.

`tags` maps an action ID or exact name to `direction` (`forward`, `reverse`,
`pingpong`, `pingpong_reverse`), `repeat` (0 means continuous looping), `fps`,
and/or `durations_ms`. Supply one duration per selected frame; explicit durations
take precedence over `fps`. These options affect this export without rewriting
the action. Individual formats have timing constraints, such as GIF's
centisecond resolution and Godot's limited repeat semantics.

`background` can override transparent/solid GIF intent for an export. Solid uses
an exact `#RRGGBB` color. Switching into or out of `original` requires a project
settings edit and reprocessing first. Solid compositing applies to GIFs; the
other exports retain their processed RGBA frames.

## Results and recovery

With `--json`, parse one stdout JSON object. Every result includes `status`,
`operation` and `exit_code`. Project results commonly include `project` and
`modified`; successful mutations generally add `run_record`. Media commands
return `files`, processing returns stages, and exports return `manifest`.
Progress goes to stderr; do not parse it as the result. Without `--json`, the
result is sent to stderr too.

| Exit code | Meaning |
| --- | --- |
| 0 | Success; `status` is `ok`. |
| 1 | Operational failure. |
| 2 | Invalid request, missing file, unsupported selection or stale export. |
| 3 | Unexpected failure. |
| 130 | Cancelled, including Ctrl+C. |

Failures include `error`. Inspect saved state after interruption: earlier completed
actions or stage checkpoints may already be committed. Correct the request or
provider issue and resume deliberately; do not automatically retry a paid call
without checking its project record and outputs.

CLI media implementation, guide and offline workbench: **Codex (OpenAI)**.
