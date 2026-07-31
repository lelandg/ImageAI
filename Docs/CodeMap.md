# ImageAI — Complete Code Map

*Last Updated: 2026-07-31 09:38:22*

Navigation guide for the ImageAI codebase with exact line numbers for classes,
methods, and key functions. Every `file.py:NNN` reference in this document was
extracted from the source with a deterministic AST parser and spot-verified
against the file — no line number here was estimated.

**Scope:** 377 Python files, 135,887 lines, 5,498 symbols (485 classes,
4,588 functions/methods, 305 module constants).
**Version:** 0.43.0 (`core/constants.py:9`)

## Table of Contents

| Section | Line Number |
|---------|-------------|
| [Quick Navigation](#quick-navigation) | 45 |
| [Visual Architecture Overview](#visual-architecture-overview) | 81 |
| [Project Structure](#project-structure) | 124 |
| [CLI & Entry Points](#cli-entry-points) | 185 |
| [Core Modules](#core-modules) | 552 |
| [Core Video — Prompt Engine, Project Model & Analysis](#core-video-prompt-engine-project-model-analysis) | 1440 |
| [Core Video — LLM Sync, Storyboard v2 & Generation Clients](#core-video-llm-sync-storyboard-v2-generation-clients) | 1936 |
| [Core Video — Storyboard, Veo Client, Rendering & Audio](#core-video-storyboard-veo-client-rendering-audio) | 2374 |
| [Core — Layout Engine, Styles, Reference & Model Registry](#core-layout-engine-styles-reference-model-registry) | 2852 |
| [Font Generator (Core + GUI)](#font-generator-core-gui) | 3919 |
| [Character Animator (Core + GUI)](#character-animator-core-gui) | 4542 |
| [Providers (AI Backends)](#providers-ai-backends) | 5042 |
| [GUI — Main Window](#gui-main-window) | 5516 |
| [GUI — Prompt Building & Settings](#gui-prompt-building-settings) | 5947 |
| [GUI — Reference Images, Midjourney & Batch](#gui-reference-images-midjourney-batch) | 6459 |
| [GUI — Supporting Dialogs & Widgets](#gui-supporting-dialogs-widgets) | 6984 |
| [GUI — Layout Tab, Styles & Common Widgets](#gui-layout-tab-styles-common-widgets) | 7735 |
| [GUI Video — Workspace Widget](#gui-video-workspace-widget) | 8668 |
| [GUI Video — Project, Workspace & Reference Dialogs](#gui-video-project-workspace-reference-dialogs) | 8988 |
| [GUI Video — Reference Library, Lipsync & Prompt Dialogs](#gui-video-reference-library-lipsync-prompt-dialogs) | 9450 |
| [Scripts, Tools & Standalone Utilities](#scripts-tools-standalone-utilities) | 9873 |
| [Cross-File Dependencies](#cross-file-dependencies) | 10586 |
| [Configuration Files](#configuration-files) | 10833 |
| [Architecture Patterns](#architecture-patterns) | 10867 |
| [Development Guidelines](#development-guidelines) | 10892 |
| [Performance Considerations](#performance-considerations) | 10951 |

## Quick Navigation

### Primary Entry Points

| Purpose | Location | Notes |
|---------|----------|-------|
| **Application entry** | `main.py:89` — `main()` | Routes to GUI (default) or CLI |
| **GUI main window** | `gui/main_window.py:138` — `MainWindow` | Generate / Settings / Templates / Video / Layout / Help tabs |
| **CLI dispatch** | `cli/runner.py:184` — `run_cli()` | Executes the parsed CLI command |
| **CLI argument parser** | `cli/parser.py:7` — `build_arg_parser()` | All flags and subcommands |
| **Provider factory** | `providers/__init__.py:126` — `get_provider()` | Selects the AI backend |
| **Provider interface** | `providers/base.py:8` — `ImageProvider` (ABC) | `generate()` at `providers/base.py:23` |
| **Configuration** | `core/config.py:16` — `ConfigManager` | API keys via `get_api_key()` at `core/config.py:121` |
| **Version constant** | `core/constants.py:9` — `VERSION` | Primary version definition |

### Key Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **Model ID resolution** | `core/llm_models.py:63` — `resolve_model()` | Runtime LLM model IDs; wraps the vendored registry client in `core/model_registry/` |
| **LLM response parsing** | `core/llm_parsing.py:15` — `LLMResponseParser` | Robust JSON extraction (strips Markdown fences); re-exported from `gui/llm_utils.py:9` |
| **Dialog status console** | `gui/llm_utils.py:15` — `DialogStatusConsole` | Standard bottom-of-dialog LLM status display |
| **LiteLLM setup** | `gui/llm_utils.py:89` — `LiteLLMHandler` | Captures LiteLLM internal messages for logging |
| **Operation guard** | `gui/dialog_utils.py:149` — `OperationGuardMixin` | Blocks concurrent operations in dialogs |
| **Logging setup** | `core/logging_config.py` | Per-user, platform-independent error logging |

### Debug Artifacts

On application exit these are copied to the working directory:

- `./imageai_current.log` — the most recent session log (**check this first when investigating errors**)
- `./imageai_current_project.json` — the last loaded/saved project

Full logs live in `logs/`, or the platform user directory
(Windows `%APPDATA%\ImageAI\`, Linux `~/.local/share`).

## Visual Architecture Overview

```
           ┌──────────────────────────────────────────────────────┐
           │          Entry Point  —  main.py:89  main()          │
           │            routes to GUI (default) or CLI            │
           └──────────────────────────────────────────────────────┘

                                      │
                     ┌────────────────┴──────────────────┐
                     ▼                                   ▼
      ┌────────────────────────────┐      ┌────────────────────────────┐
      │        PySide6 GUI         │      │            CLI             │
      │   gui/main_window.py:138   │      │     cli/runner.py:184      │
      │         MainWindow         │      │         run_cli()          │
      └────────────────────────────┘      └────────────────────────────┘

                     └─────────────────┬─────────────────┘
                                       ▼
         ┌──────────────────────────────────────────────────────────┐
         │              Core Business Logic  —  core/               │
         │     core/config.py:16 · core/constants.py:9 VERSION      │
         │          core/llm_models.py:63 resolve_model()           │
         └──────────────────────────────────────────────────────────┘

                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│     core/video/     │    │    core/layout/     │    │    core/styles/     │
│   storyboard, Veo   │    │   engine, tiling    │    │   font_generator    │
│   Omni · renderer   │    │   text, balloons    │    │    char_animator    │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘

                                       │
                                       ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │     Providers  —  providers/__init__.py:126  get_provider()      │
     │                  base.py:8 ImageProvider (ABC)                   │
     │   google · openai · stability · local_sd · ollama · midjourney   │
     └──────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
ImageAI/
├── main.py                       # Entry point — main() at :89 routes GUI vs CLI
├── core/                         # Business logic (27 files, 8,458 lines)
│   ├── config.py                 #   ConfigManager, layered API-key resolution
│   ├── constants.py              #   VERSION and app-wide constants
│   ├── llm_models.py             #   resolve_model() — runtime model IDs
│   ├── llm_parsing.py            #   LLMResponseParser
│   ├── video/                    # Video subsystem (34 files, 18,604 lines)
│   ├── layout/                   # Publication layout engine (29 files, 6,031 lines)
│   ├── font_generator/           # Font generation (9 files, 5,765 lines)
│   ├── character_animator/       # Character rigging/animation (10 files, 5,189 lines)
│   ├── styles/                   # Custom styles (5 files, 873 lines)
│   ├── reference/                # Reference-image compositing (3 files, 539 lines)
│   └── model_registry/           # Vendored model-registry client (2 files, 283 lines)
├── gui/                          # PySide6 interface (37 files, 31,254 lines)
│   ├── main_window.py            #   MainWindow at :138 — 9,138 lines
│   ├── llm_utils.py              #   Shared LLM dialog helpers
│   ├── video/                    # Video UI (25 files, 19,085 lines)
│   ├── layout/                   # Layout tab UI (20 files, 5,353 lines)
│   ├── font_generator/           # Font wizard (2 files, 2,406 lines)
│   ├── character_animator/       # Puppet wizard (3 files, 1,948 lines)
│   ├── styles/                   # Style manager UI (3 files, 656 lines)
│   ├── common/                   # Shared dialog conventions (5 files, 470 lines)
│   └── utils/                    # GUI utilities (1 file, 91 lines)
├── cli/                          # Command-line interface (3 files, 901 lines)
│   └── commands/                 #   video, layout, style subcommands (4 files, 695 lines)
├── providers/                    # AI backends (10 files, 5,966 lines)
│   ├── base.py                   #   ImageProvider ABC
│   ├── google.py                 #   Gemini / Imagen (2,156 lines)
│   ├── openai.py                 #   gpt-image / DALL·E (1,477 lines)
│   ├── stability.py, local_sd.py, ollama.py, midjourney*.py
│   └── video/                    #   Lipsync providers (3 files, 651 lines)
├── utils/                        # Maintenance utilities (5 files, 1,061 lines)
├── scripts/                      # Data-generation scripts (3 files, 1,977 lines)
├── tools/                        # generate_code_map.py (1 file, 237 lines)
├── templates/                    # Template definitions (1 file, 2,098 lines)
├── data/                         # JSON resources
│   ├── prompts/                  #   presets, artists, styles, moods, colors, lighting, mediums
│   ├── style_presets/            #   Custom style presets
│   └── model_capabilities.json   #   Provider/model capability matrix
├── tests/                        # pytest suite (102 files, 8,207 lines)
│   ├── layout/ (74)  styles/ (18)  video/ (6)  gui/ (1)  migration/ (2)
├── Docs/                         # Developer & user documentation
├── Plans/, Notes/                # Design docs and brainstorming
└── pytest.ini                    # testpaths=tests (keeps root demo scripts out)
```

### Python Environment

- **Windows / PowerShell** (Leland's run environment): `.venv` —
  `.\.venv\Scripts\Activate.ps1`, launched as `python main.py`
- **WSL / Linux** (agent environment): `.venv_linux` —
  `source .venv_linux/bin/activate`, invoked as `python3`
- Never use `.venv` from a WSL shell.
- Dependencies: `requirements.txt`; local Stable Diffusion extras in
  `requirements-local-sd.txt`.


## CLI & Entry Points

This section covers the application's process entry points (`main.py`), the argparse-based CLI surface (`cli/`), the sub-command handlers under `cli/commands/`, the standalone migration/security scripts at the repo root, and the one-off maintenance utilities in `utils/`.

**Entry-point flow**: `main.py:89` (`main()`) → no args → `gui.launch_gui()`; args → `cli.build_arg_parser()` (`cli/parser.py:7`) → `cli.run_cli()` (`cli/runner.py:184`) → optional dispatch into `cli/commands/{layout,video,style}.py`.

---

### main
**Path**: `main.py` - 209 lines
**Purpose**: Application entry point. Suppresses noisy third-party logging before any import, installs a protobuf-compatibility import hook, wires global exception hooks (`sys.excepthook`, `threading.excepthook`, `sys.unraisablehook`), routes `print()` through the console logger, then dispatches to the GUI (no args or `--gui`) or the CLI runner.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_original_import` | 27 | variable | Saved `builtins.__import__` used by the patch hook |
| `_patched` | 28 | variable | One-shot flag: protobuf already patched |
| `_initialization_complete` | 70 | variable | Gate that suppresses protobuf `GetPrototype` noise during startup |
| `_orig_print` | 74 | variable | Saved `builtins.print` (module level so numba can introspect it) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_patched_import` | 30 | private | module | No | Import hook installed on `builtins.__import__`; back-fills `GetPrototype` on protobuf's `MessageFactory` / `SymbolDatabase` for newer protobuf runtimes |
| `_logged_print` | 76 | private | None | No | `print` wrapper that mirrors output into the `console` logger and swallows startup protobuf errors |
| `main` | 89 | public | None | No | Entry point: defers output while protobuf loads, calls `core.logging_config.setup_logging()`, installs exception hooks, then launches GUI or `run_cli(args)` and `sys.exit`s with its code |

**Nested helpers inside `main()`** (defined per-call, not importable):

| Function | Line | Description |
|----------|------|-------------|
| `_deferred_print` | 96 | Buffers `print` output until logging is initialized |
| `_log_unhandled` | 129 | `sys.excepthook`: logs unhandled exceptions, points the user at `./imageai_current.log` |
| `_thread_excepthook` | 141 | `threading.excepthook`: logs background-thread failures |
| `_unraisable_hook` | 150 | `sys.unraisablehook`: logs unraisable exceptions with traceback |

---

### ImageAI package init
**Path**: `__init__.py` - 34 lines
**Purpose**: Top-level package metadata. Re-exports `__version__`, `__author__`, `__email__`, `__license__`, `__copyright__`, `APP_NAME`, and `VERSION` from `core` so the version has a single definition (`core/constants.py`).
**Language**: Python

No classes or functions — imports and `__all__` only.

---

### cli package init
**Path**: `cli/__init__.py` - 6 lines
**Purpose**: Public CLI surface. Re-exports `build_arg_parser` (from `cli.parser`) and `run_cli` (from `cli.runner`); `main.py` imports both from here.
**Language**: Python

No classes or functions — imports and `__all__` only.

---

### CLI Argument Parser
**Path**: `cli/parser.py` - 326 lines
**Purpose**: Single `argparse.ArgumentParser` definition for the whole CLI, organized into argument groups: authentication, actions, generation options, Batch API, lyrics-to-prompts, layout, video generation, styles, and help.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `build_arg_parser` | 7 | public | `argparse.ArgumentParser` | No | Builds and returns the complete `imageai` parser (all flags and groups below) |

#### Argument Groups (defined inside `build_arg_parser`)
| Group | Line | Key flags |
|-------|------|-----------|
| (root) | 14 | `--version`, `--provider {google,openai,stability,local_sd}` |
| authentication | 29 | `-k/--api-key`, `-K/--api-key-file`, `--auth-mode {api-key,gcloud}` |
| actions | 46 | `-p/--prompt`, `-t/--test`, `-s/--set-key`, `--gui`, `--lyrics-to-prompts` |
| generation options | 73 | `-m/--model`, `-o/--out`, `--size`, `--quality`, `--output-format`, `--output-compression`, `--moderation`, `--custom-size`, `--stream-partials`, `--reference`, `--mask`, `-n/--num-images` |
| batch API | 143 | `--batch`, `--batch-status`, `--batch-fetch` |
| lyrics-to-prompts options | 161 | `--lyrics-model`, `--lyrics-temperature`, `--lyrics-style`, `--lyrics-output` |
| layout | 183 | `--layout-design`, `--layout-export`, `--layout-fill`, `--content-kind`, `--page-size`, `--orientation`, `--dpi`, `--layout-llm-provider`, `--layout-llm-model` |
| video generation | 231 | `--video`, `--video-provider {omni,veo}`, `--video-model`, `--aspect`, `--ref-image`, `--last-frame`, `--extend`, `--delivery`, `--refine-from`, `--edit-video`, `--json` |
| styles | 290 | `--style`, `--style-smart`, `--style-create`, `--style-images`, `--style-llm-provider`, `--style-llm-model`, `--style-list`, `--style-show`, `--style-delete`, `--style-export`, `--style-import` |
| help | 319 | `--help-api-key` |

---

### CLI Runner
**Path**: `cli/runner.py` - 569 lines
**Purpose**: The CLI's main dispatcher. Resolves API keys through the layered precedence chain, routes to sub-command modules (layout / video / style), and implements the image-generation paths in-line: auth test, Batch API submit/status/fetch, style application, reference-image edit, streaming partials, and standard sync generation — including auto-save with JSON metadata sidecars.
**Language**: Python

#### Table of Contents
| Section | Line |
|---------|------|
| Imports | 1 |
| Key resolution / storage | 14 |
| Lyrics-to-prompts handler | 71 |
| `run_cli` dispatcher | 184 |
| Sub-command routing (layout/video/style) | 218 |
| `--set-key` / `--test` | 256 |
| Batch status & fetch | 307 |
| `--prompt` generation + style application | 340 |
| Dispatch: batch / reference-edit / stream / sync | 426 |
| Image save + sidecar metadata | 512 |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `resolve_api_key` | 14 | public | `Tuple[Optional[str], str]` | No | Resolves the provider key in priority order CLI arg → key file → `ConfigManager.get_api_key()` → env vars (`GOOGLE_API_KEY`/`GEMINI_API_KEY`, `OPENAI_API_KEY`, `STABILITY_KEY`/`STABILITY_API_KEY`), returning `(key, source)` |
| `store_api_key` | 64 | public | None | No | Persists a key for a provider via `ConfigManager.set_api_key()` + `save()` |
| `handle_lyrics_to_prompts` | 71 | public | int | No | Loads a lyrics file, builds a `LyricsToPromptsGenerator` with configured provider keys, generates per-line image prompts (model default via `resolve_model()`), prints them and saves JSON (`--lyrics-output` or `<lyrics>.prompts.json`) |
| `run_cli` | 184 | public | int | No | Main entry: validates `--size`/`--custom-size` mutual exclusion, handles `--help-api-key`, routes to layout/video/style handlers, `--set-key`, `--test`, batch ops, then the `--prompt` generation pipeline; returns the process exit code |

**Exit-code convention used throughout**: `0` success, `2` user/validation error, `3` auth or generation-service failure, `4` generation/batch failure.

**Nested helper inside `run_cli`**:

| Function | Line | Description |
|----------|------|-------------|
| `on_partial` | 480 | `--stream-partials` callback; writes each partial image as `<stem>.p<idx><ext>` and logs the path to stderr |

---

### CLI Commands package init
**Path**: `cli/commands/__init__.py` - 0 lines
**Purpose**: Empty package marker for the `cli.commands` sub-package (handlers are imported lazily by `run_cli`, e.g. `from cli.commands.video import run_video_cmd`).
**Language**: Python

---

### Video Command
**Path**: `cli/commands/video.py` - 288 lines
**Purpose**: `--video` handler for single-clip generation across the two video backends — Gemini Omni (`core.video.omni_client`) and Veo (`core.video.veo_client`). Validates provider-exclusive flags, applies a saved style as text, writes the `.mp4` plus a JSON sidecar, and emits either a machine-readable JSON line on stdout (`--json`) or human text on stderr.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `logger` | 12 | variable | `logging.getLogger("imageai.cli.video")` |
| `OMNI_MAX_REFS` | 14 | constant | Max `--ref-image` count for Gemini Omni |
| `VEO_MAX_REFS` | 15 | constant | Max `--ref-image` count for Veo |

#### Classes
##### VideoCliError
**Line**: 18 (ends 19)
**Extends**: `Exception`
**Purpose**: User-facing validation error; caught by `run_video_cmd` and mapped to exit code 2.

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_emit` | 22 | private | None | No | Prints a progress/result line to stderr, keeping stdout pure for `--json` |
| `_resolve_style` | 27 | private | `Style \| None` | No | Looks up `--style` in the `StyleStore`; raises `VideoCliError` listing available names when unknown |
| `_derive_output` | 41 | private | `Path` | No | Output `.mp4` path — `-o` if given, else a sanitized slug of the prompt in the CWD |
| `_ref_images` | 50 | private | `list[Path]` | No | Expands repeated `--ref-image` values to paths |
| `build_omni_config` | 55 | public | `OmniGenerationConfig` | No | Maps args to an Omni config; rejects `--extend`/`--last-frame`, enforces `OMNI_MAX_REFS`, wires `--delivery`, `--refine-from`, `--edit-video` |
| `_veo_model` | 90 | private | `VeoModel` | No | Resolves `--video-model` to the `VeoModel` enum (default Veo 3.1 GA); raises with the valid choices |
| `build_veo_config` | 103 | public | `VeoGenerationConfig` | No | Maps args to a Veo config; rejects the Omni-only flags (`--delivery`, `--refine-from`, `--edit-video`) and enforces `VEO_MAX_REFS` |
| `_run_omni` | 132 | private | dict | No | Resolves the Google key (api-key auth only), runs `OmniClient.generate_video()` to `out_path`, returns a normalized result dict |
| `_run_veo` | 158 | private | dict | No | Builds a `VeoClient` (gcloud via `GOOGLE_CLOUD_PROJECT`, or api-key), generates or extends (`--extend`), copies the produced file to `out_path` |
| `_status_payload` | 209 | private | dict | No | Converts the normalized result into the documented sidecar/JSON shape (`status`, `output_path`, `provider`, `model`, `aspect_ratio`, `operation_id`, `error`) |
| `_write_sidecar` | 222 | private | None | No | Best-effort write of `<out>.json` beside the video; logs a warning on `OSError` |
| `_report` | 232 | private | int | No | Emits the payload (stdout JSON when `--json`, else a stderr success/failure line) and returns the exit code |
| `run_video_cmd` | 243 | public | int | No | Top-level `--video` handler: applies the style, dispatches to omni/veo, writes the sidecar, reports; `0` ok, `1` generation failed, `2` validation, `3` runtime error |

**Nested helper inside `run_video_cmd`**:

| Function | Line | Description |
|----------|------|-------------|
| `_fail` | 249 | Logs the message and reports a failure payload with the given exit code |

---

### Layout Command
**Path**: `cli/commands/layout.py` - 258 lines
**Purpose**: CLI handlers for the publication layout engine — `--layout-design` (LLM-generated project), `--layout-fill` (generate an image for every prompted image region), and `--layout-export` (render to PDF/PNG through an offscreen Qt renderer).
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `logger` | 13 | variable | `logging.getLogger("imageai.cli.layout")` |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_resolve_preset` | 16 | private | dict | No | Case-insensitive exact-then-substring match of a page-size name against `core.layout.page_sizes.PRESETS`; raises `ValueError` listing choices |
| `_page_px` | 29 | private | tuple | No | `(width_px, height_px)` for a named page size at the given orientation and DPI |
| `_export_format` | 35 | private | str | No | Returns `'pdf'` or `'png'` from the `-o` suffix; raises `ValueError` otherwise |
| `_region_size_str` | 45 | private | str | No | `"WxH"` for a region's bbox, proportionally scaled so the long edge is ≤ `cap` (default 1024) |
| `run_design_cmd` | 57 | public | int | No | Builds designer messages, calls the layout LLM (`designer.run_completion`), parses the response, assembles a `DocumentSpec` and saves it via `project_io.save_project`; requires `-o` |
| `run_fill_cmd` | 98 | public | int | No | Loads a project, resolves the image provider + key, optionally applies `--style`, generates an image per prompted image region into the images dir, sets `region.image_ref`, and re-saves; returns 4 if any region failed |
| `_with_offscreen_qapp` | 180 | private | Any | No | Runs `fn()` under `QT_QPA_PLATFORM=offscreen` with a live `QApplication`; raises `RuntimeError` when PySide6 is missing |
| `run_export_cmd` | 192 | public | int | No | Renders a project to PDF (single file) or PNG (one file per page, `-NNN` suffixed when multi-page) via `core.layout.qt_renderer` |
| `_assemble_document` | 244 | private | `DocumentSpec` | No | Builds a one-page `DocumentSpec` from a `DesignerResult` (mirrors the GUI new-document path), falling back to `designer.fallback_result` when no regions were produced |

**Nested helper inside `run_export_cmd`**:

| Function | Line | Description |
|----------|------|-------------|
| `_do` | 219 | The actual render call, executed inside the offscreen QApplication |

---

### Style Command
**Path**: `cli/commands/style.py` - 149 lines
**Purpose**: Handler for the custom-style management verbs (`--style-create`, `--style-list`, `--style-show`, `--style-delete`, `--style-export`, `--style-import`). Derives a style from reference images via the vision LLM and persists it through `core.styles.store.StyleStore`.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `logger` | 12 | variable | `logging.getLogger("imageai.cli.style")` |
| `IMAGE_EXTS` | 19 | constant | Accepted image suffixes: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp` |

#### Classes
##### StyleCliError
**Line**: 15 (ends 16)
**Extends**: `Exception`
**Purpose**: User-facing validation error; mapped to exit code 2 by `run_style_cmd`.

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_emit` | 22 | private | None | No | Progress line to stderr, keeping stdout reserved for scriptable data (style ids, JSON) |
| `_require` | 27 | private | `Style` | No | Fetches a style by name or raises `StyleCliError` listing available names |
| `_collect_images` | 35 | private | list | No | Expands `--style-images` specs (files, directories, globs) into a sorted unique list of image paths; raises when nothing matches |
| `_handle_create` | 59 | private | int | No | Runs `StyleAnalysisService.derive()` over the collected images, builds a `Style` with its `StyleDescriptor`, attaches reference images/exemplars, saves it, and prints the new id on stdout |
| `run_style_cmd` | 85 | public | int | No | Routes the style verbs (list / show / delete / create / export-zip / import-zip); returns 0 ok, 2 user error, 3 unexpected failure |

---

### Config Migration Script
**Path**: `migrate_config.py` - 179 lines
**Purpose**: Standalone script that migrates legacy `config.json` layouts (top-level `api_key`, the incorrect `keys` object) into the canonical `providers.<name>.api_key` structure, and optionally moves keys into the OS keyring via `core.security.secure_storage`. Backs up the original config before writing.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `SECURITY_AVAILABLE` | 31 | constant | `True` when `core.security.secure_storage` imported successfully |
| `SECURITY_AVAILABLE` | 33 | constant | `False` fallback set in the `ImportError` branch (keys stay in `config.json`) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `get_config_path` | 37 | public | `Path` | No | Platform-specific `config.json` location (Windows `AppData/Roaming`, macOS `Library/Application Support`, Linux `$XDG_CONFIG_HOME`) |
| `migrate_config` | 52 | public | dict | No | Performs the migrations, optionally stores keys in the keyring and strips them from the file, backs up the original with a timestamped name, and returns the migrated dict (`dry_run` skips all writes) |
| `main` | 150 | public | int | No | Argparse front end (`--dry-run`, `--config`, `--no-secure`); prints the dry-run result and returns the exit code |

---

### History Migration Script
**Path**: `migrate_history.py` - 304 lines
**Purpose**: One-off script that converts the older per-dialog history JSON files into the unified `DialogHistoryWidget` record shape (`timestamp` / `input` / `response` / `provider` / `model` / `metadata`), backing up each original first.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `get_config_dir` | 19 | public | `Path` | No | ImageAI config directory (hardcoded Windows path, remapped to `/mnt/c/...` when run from WSL) |
| `migrate_enhancement_history` | 30 | public | int | No | `enhancement_history.json` → `enhanced_prompts_history.json`; returns the entry count |
| `migrate_image_analysis_history` | 73 | public | int | No | `image_analysis_history.json` → `reference_images_history.json` |
| `migrate_prompt_generation_history` | 115 | public | int | No | Verifies `prompt_history.json` is already in the correct shape and reports its entry count (no conversion needed) |
| `migrate_prompt_question_history` | 145 | public | int | No | `prompt_question_history.json` → `prompt_questions_history.json`, folding unknown keys into `metadata` |
| `create_backup` | 191 | public | `Path \| None` | No | Copies a history file to a timestamped `.backup_YYYYmmdd_HHMMSS.json` |
| `show_sample_entries` | 201 | public | None | No | Prints the entry count and first record of each known history file for pre-migration verification |
| `main` | 230 | public | None | No | Shows samples, backs up all four files, runs every migration, prints the total and post-migration verification instructions |

---

### Secure Keys Script
**Path**: `secure_keys.py` - 106 lines
**Purpose**: Windows-only helper that moves plaintext `providers.*.api_key` values out of `config.json` and into the Windows Credential Manager via `keyring`, verifying each write before deleting the plaintext copy and backing up the original config.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `main` | 15 | public | int | No | Guards on `platform.system() == "Windows"` and the `keyring` import, stores each provider key under service `ImageAI` / username `<provider>_api_key`, verifies the round-trip, removes the key from the config, backs it up and rewrites it; returns 1 on precondition failure |

---

### Reference Metadata Recovery Utility
**Path**: `utils/recover_reference_metadata.py` - 286 lines
**Purpose**: Maintenance script that scans every ImageAI log file for generations that used reference images (both the multi-reference Imagen 3 request blocks and the legacy single `reference_image` form) and back-fills the matching `*.png.json` sidecars.
**Language**: Python

#### Classes
##### ReferenceRecovery
**Line**: 27 (ends 242)
**Purpose**: Encapsulates the log scan, metadata update, and run statistics.

###### Properties
| Property | Line | Type | Access | Description |
|----------|------|------|--------|-------------|
| `config` | 29 | `ConfigManager` | public | Source of the config directory |
| `logs_dir` | 30 | `Path` | public | `<config_dir>/logs` |
| `generated_dir` | 31 | `Path` | public | `<config_dir>/generated` |
| `stats` | 32 | dict | public | Counters: `logs_scanned`, `images_found`, `already_has_refs`, `updated`, `missing_files`, `errors` |

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 28 | constructor | None | No | Binds config paths and zeroes the stats counters |
| `scan_logs` | 41 | public | `Dict[str, Dict]` | No | Iterates every `*.log`, aggregating image-path → reference-data mappings with progress every 100 files |
| `_parse_log_file` | 72 | private | `Dict[str, Dict]` | No | Regex-extracts the Imagen 3 multi-reference blocks, then line-scans for the legacy `reference_image` → "Saved image to" pairing |
| `update_metadata_files` | 161 | public | None | No | Remaps `C:` paths to `/mnt/c`, falls back to the generated dir, skips sidecars that already carry reference data, and writes `imagen_references` (multi) or `reference_image` (single) |
| `print_summary` | 231 | public | None | No | Prints the final statistics table |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `main` | 245 | public | int | No | Validates that the logs and generated directories exist, runs the scan + update, prints the summary |

---

### Reference Metadata Updater Utility
**Path**: `utils/update_reference_metadata.py` - 282 lines
**Purpose**: Earlier/alternate variant of the recovery tool — a function-based scanner that walks log files chronologically, tracks the current prompt/reference context, and writes reference data into the matching PNG sidecars.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `find_log_files` | 24 | public | `List[Path]` | No | All `*.log` in the logs dir, sorted by filename (chronological, since names carry timestamps) |
| `extract_reference_data_from_log` | 32 | public | `Dict[str, Dict]` | No | Line-by-line scan that reconstructs multi-line `imagen_references` JSON by brace counting, also matching the legacy `reference_image` form, and associates the context with the next saved `.png` path |
| `update_metadata_file` | 138 | public | bool | No | Writes `reference_image` (legacy key) or `imagen_references` into an existing sidecar; returns False when the sidecar is missing or already has reference data |
| `main` | 192 | public | int | No | Scans all logs with per-file progress, then updates sidecars and prints an updated/skipped/missing summary |

---

### History-From-Logs Updater Utility
**Path**: `utils/update_history_from_logs.py` - 321 lines
**Purpose**: Multi-source reference recovery: combines explicit log mappings with reference paths harvested from config files (current + backups) and, optionally, video project files, then correlates them to generated images by timestamp and updates the metadata sidecars.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `get_logs_directory` | 26 | public | `Path` | No | `<config_dir>/logs` via `ConfigManager` |
| `get_output_directory` | 32 | public | `Path` | No | `<config_dir>/generated` via `ConfigManager` |
| `get_config_directory` | 38 | public | `Path` | No | `ConfigManager.config_dir` |
| `parse_log_file` | 44 | public | `Dict[str, List[str]]` | No | Extracts existing reference-image paths and the saved-image filenames that follow them, producing a filename → references map |
| `scan_config_files` | 84 | public | `Set[str]` | No | Harvests still-existing reference paths from `config.json` and its backups (`imagen_references.references[*].path` and legacy `reference_images`) |
| `scan_video_projects` | 131 | public | `Set[str]` | No | Harvests `global_reference_images` paths from `video_projects/*/project.iaproj.json` (defined but intentionally not called by `main` — video refs are video-only) |
| `find_images_using_references` | 167 | public | `Dict[str, List[str]]` | No | Timestamp correlation: maps each generated `*.png` to references whose mtime falls within a 24-hour window |
| `update_metadata_file` | 210 | public | bool | No | Adds `reference_image` (one ref) or an `imagen_references` block (multiple) to a sidecar, skipping files that already have reference data |
| `main` | 251 | public | int | No | Runs the log scan and config scan, merges timestamp-correlated mappings with log mappings (logs win), updates sidecars, and prints updated/skipped counts |

---

### Reference Diagnostic Utility
**Path**: `utils/diagnose_references.py` - 116 lines
**Purpose**: Read-only diagnostic script (top-level statements, no functions) that reports how many generated PNGs carry reference metadata, how many have no sidecar at all, and which reference images appear in the current/backup config files — used to decide whether the recovery scripts above are worth running.
**Language**: Python

Executes on import: builds a `ConfigManager` (line 10), scans `<config_dir>/generated/*.png` sidecars for `imagen_references` / `reference_image`, prints a percentage summary, then inspects up to five config files for historical reference entries and prints a conclusion.

---

### Path Test Utility
**Path**: `utils/test_paths.py` - 56 lines
**Purpose**: Ad-hoc diagnostic (top-level statements, no functions) that prints the resolved ImageAI config directory, enumerates `video_projects/*/project.iaproj.json` and their `global_reference_images` (reporting whether each path still exists), and counts PNGs in the generated-images directory.
**Language**: Python

> Note: despite the `test_` prefix this is a manual script, not a pytest module — `pytest.ini` sets `testpaths` to `tests/` so it is not collected.

---

## Core Modules

The `core/` package holds all provider-agnostic business logic: configuration and
credential resolution, image/prompt utilities, batch and conversation state,
optional-dependency installers, and cross-cutting services (logging, security,
Discord presence).

---

### MuseTalk Installer
**Path**: `core/musetalk_installer.py` - 791 lines
**Purpose**: Detects, installs, and downloads everything MuseTalk lip-sync needs — Python packages (with GPU detection and Windows build workarounds) plus five model-weight bundles — from background `QThread` workers.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| MUSETALK_MODELS | 19 | constant | Manifest of every MuseTalk model weight (repo/URL, filename, destination) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_musetalk_model_path | 59 | public | Path | No | Platform-specific model storage path for MuseTalk |
| check_musetalk_installed | 80 | public | Tuple[bool, str] | No | Report whether packages *and* weights are fully installed |
| get_musetalk_packages | 132 | public | Tuple[List[str], str] | No | Package list for MuseTalk with GPU-support detection (returns extra pip index URL) |
| get_musetalk_disk_space_required | 786 | public | float | No | Total disk space (GB) needed for a full MuseTalk install |

#### Class: MuseTalkPackageInstaller
**Line**: 185-474 · **Base**: `QThread`
Background installer thread emitting progress while pip-installing the MuseTalk dependency set.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 192 | constructor | - | No | Store package list and optional extra index URL |
| run | 198 | public | - | No | Drive the whole install, emitting progress/percentage/finished |
| _install_package | 248 | private | Tuple[bool, str] | No | pip-install one package, with retries and error capture |
| _ensure_setuptools | 348 | private | Tuple[bool, str] | No | Guarantee setuptools/wheel exist for `--no-build-isolation` builds |
| _install_with_no_isolation | 372 | private | Tuple[bool, str] | No | Work around packages with broken `setup.py` |
| _install_xtcocotools_windows | 409 | private | Tuple[bool, str] | No | Install `xtcocotools` on Windows from a prebuilt wheel |
| stop | 459 | public | - | No | Request cooperative cancellation |
| _format_duration | 463 | private | str | No | Human-readable elapsed time |

#### Class: MuseTalkModelDownloader
**Line**: 477-783 · **Base**: `QThread`
Background downloader for MuseTalk's model weights, preferring HuggingFace Hub with direct-URL fallbacks.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 484 | constructor | - | No | Initialize download state |
| run | 489 | public | - | No | Download all required models in sequence |
| _download_musetalk_model | 542 | private | bool | No | Core MuseTalk model, HF first then direct URL |
| _download_via_hf_hub | 584 | private | bool | No | Fallback download through `huggingface_hub` |
| _download_dwpose_model | 621 | private | bool | No | DWPose pose-estimation weights |
| _download_face_parse_model | 645 | private | bool | No | Face-parsing weights |
| _download_vae_model | 673 | private | bool | No | Stable Diffusion VAE weights |
| _download_whisper_model | 714 | private | bool | No | Whisper tiny model for audio alignment |
| _download_file | 727 | private | bool | No | Generic download with progress tracking |
| stop | 768 | public | - | No | Request cooperative cancellation |
| _format_duration | 772 | private | str | No | Human-readable elapsed time |

---

### Package Installer
**Path**: `core/package_installer.py` - 624 lines
**Purpose**: Generic GUI-driven pip installer and model downloader threads, plus dependency/GPU/disk probes used by the Real-ESRGAN upscaler and Character Animator puppet features.
**Language**: Python

#### Class: PackageInstaller
**Line**: 16-257 · **Base**: `QThread`
Installs Python packages in the background, optionally appending them to `requirements.txt`. Emits `progress`, `finished`, and `percentage` signals.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 23 | constructor | - | No | Store packages, requirements-update flag, index URL |
| run | 30 | public | - | No | Install every package, emitting progress and a final result |
| _install_package | 130 | private | Tuple[bool, str] | No | pip-install a single package |
| _update_requirements_file | 202 | private | - | No | Append newly installed packages to `requirements.txt` |
| stop | 244 | public | - | No | Request cooperative cancellation |
| _format_duration | 248 | private | str | No | Human-readable elapsed time |

#### Class: ModelDownloader
**Line**: 260-372 · **Base**: `QThread`
Downloads a single AI model weight file with progress reporting.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 267 | constructor | - | No | Store source URL and destination path |
| run | 273 | public | - | No | Stream the model file to disk with progress |
| stop | 357 | public | - | No | Request cooperative cancellation |
| _format_duration | 361 | private | str | No | Human-readable elapsed time |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| check_disk_space | 375 | public | Tuple[bool, str] | No | Verify enough free space for an install |
| get_installed_packages | 402 | public | List[str] | No | List currently installed pip packages |
| is_package_installed | 425 | public | bool | No | Membership check for one package |
| detect_nvidia_gpu | 431 | public | Tuple[bool, Optional[str]] | No | Detect NVIDIA GPU and report its name |
| get_realesrgan_packages | 469 | public | Tuple[List[str], str] | No | Real-ESRGAN package list with GPU-aware wheel index |
| get_model_info | 510 | public | dict | No | Metadata for the Real-ESRGAN models |
| get_puppet_ai_packages | 535 | public | Tuple[List[str], str] | No | Package list for Character Animator puppet automation |
| get_puppet_model_info | 586 | public | dict | No | Metadata for puppet-automation models |
| check_puppet_disk_space | 611 | public | Tuple[bool, str] | No | Disk-space check for the puppet install |

---

### Discord Rich Presence
**Path**: `core/discord_rpc.py` - 579 lines
**Purpose**: Optional Discord Rich Presence integration — publishes the user's current ImageAI activity (provider, model, elapsed time) with privacy levels and graceful degradation when `pypresence` or Discord is absent.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| PYPRESENCE_AVAILABLE | 53 | constant | True branch — `pypresence` imported successfully |
| PYPRESENCE_AVAILABLE | 55 | constant | False branch — set in the `ImportError` handler |
| ACTIVITY_DESCRIPTIONS | 76 | constant | Human-readable label for each `ActivityState` |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| ActivityState | 62 | Enum | IDLE, GENERATING, UPSCALING, EDITING, VIDEO_PROJECT, BROWSING_HISTORY, SETTINGS, CHARACTER_GENERATOR, CHATTING_WITH_AI |

A module-level singleton `discord_rpc = DiscordRPCManager()` is exported for app-wide use.

#### Class: DiscordRPCManager
**Line**: 89-575
Owns the Discord RPC connection, privacy configuration, status callbacks, and presence payload construction.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 102 | constructor | - | No | Initialize connection state, settings, and callback list |
| @property is_available | 124 | property | bool | No | Whether `pypresence` is installed |
| @property is_connected | 129 | property | bool | No | Whether a Discord connection is live |
| @property is_enabled | 134 | property | bool | No | Whether the user enabled Rich Presence |
| add_status_callback | 138 | public | None | No | Subscribe to connection-status changes |
| remove_status_callback | 146 | public | None | No | Unsubscribe a status callback |
| _notify_status | 151 | private | None | No | Fan out a status change to all callbacks |
| set_enabled | 159 | public | None | No | Turn presence on/off (connects or disconnects) |
| configure | 175 | public | None | No | Set privacy level, elapsed-time, model, and button options |
| connect | 199 | public | bool | No | Establish the Discord IPC connection |
| disconnect | 250 | public | None | No | Tear down the connection |
| update_presence | 267 | public | None | No | Publish a new activity state with provider/model/batch info |
| _do_update | 303 | private | None | No | Perform the throttled RPC update call |
| _build_presence_data | 344 | private | dict | No | Assemble the presence payload honoring the privacy level |
| test_connection | 487 | public | tuple | No | Connectivity self-test for the Settings UI |
| print_diagnostics | 524 | public | None | No | Dump troubleshooting info for Rich Presence |

---

### Batch Manager
**Path**: `core/batch_manager.py` - 492 lines
**Purpose**: Wraps the Google GenAI Batch API — builds JSONL request files, submits and polls jobs, and harvests generated images/errors from completed batches.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| BatchJobState | 20 | Enum | PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED, EXPIRED, UNKNOWN |
| BatchRequest | 40 | @dataclass | key, prompt, model, aspect_ratio, width, height, output_quality |
| BatchJob | 77 | @dataclass | job_id, name, display_name, model, state, created_at, requests, results, error, completed_at |

##### BatchJobState methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @classmethod from_api_state | 31 | class | 'BatchJobState' | No | Map an API state string to the enum (UNKNOWN fallback) |

##### BatchRequest methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 50 | public | Dict[str, Any] | No | Convert to a JSONL-compatible request dict |

##### BatchJob methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property is_complete | 91 | property | bool | No | True when the job reached a terminal state |
| @property request_count | 101 | property | int | No | Number of requests in the job |
| @property completed_count | 106 | property | int | No | Number of completed results |
| to_dict | 110 | public | Dict[str, Any] | No | Serialize job metadata for persistence |

#### Class: BatchManager
**Line**: 126-480
Tracks submitted batch jobs and mediates all Batch API calls through an injected GenAI client.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 140 | constructor | - | No | Initialize job registry and optional client |
| set_client | 150 | public | - | No | Inject/replace the Google GenAI client |
| create_batch_job | 154 | public | BatchJob | No | Submit a batch from an in-memory request list |
| create_batch_job_from_file | 215 | public | BatchJob | No | Submit a batch from an existing JSONL file |
| get_job_status | 294 | public | BatchJob | No | Refresh and return a job's current state |
| get_job_results | 333 | public | Tuple[List[bytes], List[str]] | No | Harvest image bytes and error strings from a finished job |
| _process_result | 400 | private | - | No | Decode one result entry into images/errors |
| _process_inline_response | 422 | private | - | No | Decode an inline (non-file) batch response |
| cancel_job | 437 | public | bool | No | Cancel a running batch job |
| list_jobs | 464 | public | List[BatchJob] | No | All tracked jobs |
| save_requests_to_jsonl | 468 | public | - | No | Write requests to a JSONL file for submission |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_batch_manager | 487 | public | BatchManager | No | Accessor for the process-wide `BatchManager` singleton |

---

### Utilities
**Path**: `core/utils.py` - 482 lines
**Purpose**: Cross-cutting helpers — filename sanitization, key-file reading, README/help extraction, image sidecar metadata, auto-save, disk history scanning, and debug-image cleanup.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| EXAMPLES | 359 | constant | Demo prompt list used by `find_cached_demo` (local to that function's scope) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| sanitize_filename | 14 | public | str | No | Make an arbitrary string safe as a filename |
| read_key_file | 46 | public | Optional[str] | No | Read an API key from a file on disk |
| read_readme_text | 67 | public | str | No | Load README content for in-app help |
| extract_api_key_help | 99 | public | str | No | Pull the API-key section out of the README markdown |
| generate_timestamp | 134 | public | str | No | Timestamp string suitable for filenames |
| format_file_size | 144 | public | str | No | Human-readable byte size |
| parse_image_size | 161 | public | tuple[int, int] | No | Parse `"1024x768"` into `(w, h)` |
| images_output_dir | 180 | public | Path | No | Directory where generated images auto-save |
| sidecar_path | 189 | public | Path | No | JSON sidecar path for a given image |
| write_image_sidecar | 194 | public | None | No | Write prompt/generation metadata beside an image |
| read_image_sidecar | 224 | public | Optional[dict] | No | Read an image's sidecar metadata |
| detect_image_extension | 235 | public | str | No | Sniff the image format from raw bytes (defaults to `.png`) |
| sanitize_stub_from_prompt | 251 | public | str | No | Build a safe filename stub from a prompt |
| auto_save_images | 281 | public | list | No | Save all generated images to the output dir; return absolute paths |
| scan_disk_history | 309 | public | list[Path] | No | List generated images sorted newest-first |
| find_cached_demo | 355 | public | Optional[Path] | No | Reuse a cached demo image when prompt+provider match a sidecar |
| default_model_for_provider | 391 | public | str | No | Default model ID for a provider |
| cleanup_debug_images | 399 | public | tuple[int, int] | No | Remove leftover debug images at startup |

---

### Lyrics-to-Prompts Generator
**Path**: `core/lyrics_to_prompts.py` - 436 lines
**Purpose**: Turns song lyrics into one descriptive image prompt per line using an LLM (via LiteLLM), with structured-JSON parsing and a plain-text fallback parser.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| LyricPrompt | 20 | @dataclass | line, image_prompt |
| LyricsToPromptsResult | 39 | @dataclass | prompts, raw_response, success, error |

##### LyricPrompt methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 25 | public | Dict[str, Any] | No | Serialize to `{line, imagePrompt}` |
| @classmethod from_dict | 30 | class | 'LyricPrompt' | No | Rehydrate from the JSON schema shape |

##### LyricsToPromptsResult methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 46 | public | Dict[str, Any] | No | Serialize to the guide's JSON schema |

#### Class: LyricsToPromptsGenerator
**Line**: 53-414
Owns the system prompt, LiteLLM setup, provider credential export, generation call, and response parsing.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 84 | constructor | - | No | Bind a `ConfigManager` and prepare LLM access |
| _setup_litellm | 96 | private | - | No | Configure LiteLLM when it is importable |
| _setup_providers | 108 | private | - | No | Export provider API keys as env vars for LiteLLM |
| generate | 154 | public | LyricsToPromptsResult | No | Generate one image prompt per lyric line |
| _parse_response | 247 | private | LyricsToPromptsResult | No | Parse structured JSON output (fences tolerated) |
| _parse_plain_text | 324 | private | LyricsToPromptsResult | No | Fallback parser for non-JSON LLM output |
| save_to_json | 399 | public | - | No | Persist the result to a JSON file |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| load_lyrics_from_file | 417 | public | List[str] | No | Read lyrics from a text file into lines |

---

### Preset Loader
**Path**: `core/preset_loader.py` - 402 lines
**Purpose**: Loads built-in and user-defined style presets for the Prompt Builder, and supports create/delete/popularity/import/export of custom presets.
**Language**: Python

#### Class: PresetLoader
**Line**: 15-402

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 18 | constructor | - | No | Resolve preset file locations and initialize caches |
| get_presets | 29 | public | List[Dict] | No | All presets, optionally filtered by category / sorted by popularity |
| _load_built_in_presets | 70 | private | List[Dict] | No | Load shipped presets from `presets.json` |
| _load_custom_presets | 100 | private | List[Dict] | No | Load user presets from `custom_presets.json` |
| save_custom_preset | 130 | public | bool | No | Create a custom preset from name/settings/metadata |
| delete_preset | 194 | public | bool | No | Delete a custom preset by ID |
| update_preset_popularity | 225 | public | bool | No | Increment/decrement a preset's popularity score |
| get_categories | 253 | public | List[str] | No | Unique category list |
| get_preset_by_id | 271 | public | Optional[Dict] | No | Look up one preset by ID |
| _save_custom_presets_file | 294 | private | None | No | Persist the custom-preset file |
| _generate_preset_id | 320 | private | str | No | Derive a stable ID from a preset name |
| export_preset | 337 | public | bool | No | Write a preset to a standalone JSON file |
| import_preset | 370 | public | bool | No | Import a preset from a JSON file |

---

### Configuration Manager
**Path**: `core/config.py` - 381 lines
**Purpose**: Platform-aware config persistence and the single authority for API-key resolution, auth modes, layout/Discord settings, and user directories. **Always** read keys via `get_api_key()` rather than the raw config dict.
**Language**: Python

#### Class: ConfigManager
**Line**: 16-375

##### Methods — lifecycle & generic access
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 19 | constructor | - | No | Resolve the config dir, load and migrate config |
| _get_config_dir | 32 | private | Path | No | Platform-specific config directory |
| _load_config | 46 | private | Dict[str, Any] | No | Read `config.json` from disk |
| _normalize_auth_mode | 57 | private | None | No | Normalize legacy auth-mode values |
| _migrate_api_keys | 71 | private | None | No | Migrate top-level legacy keys into `providers` |
| save | 95 | public | None | No | Persist config to disk |
| get | 102 | public | Any | No | Generic key lookup with default |
| set | 106 | public | None | No | Generic key assignment |

##### Methods — provider credentials & auth
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| get_provider_config | 110 | public | Dict[str, Any] | No | Per-provider config block |
| set_provider_config | 115 | public | None | No | Replace a provider's config block |
| get_api_key | 121 | public | Optional[str] | No | Layered API-key resolution (key file > config > env) |
| set_api_key | 167 | public | None | No | Store a provider's API key |
| get_auth_mode | 178 | public | str | No | Auth mode for a provider (api key vs gcloud) |
| set_auth_mode | 184 | public | None | No | Set a provider's auth mode |
| get_auth_validated | 189 | public | bool | No | Whether the provider's auth was verified |
| set_auth_validated | 195 | public | None | No | Record auth-validation status |
| get_gcloud_project_id | 202 | public | Optional[str] | No | Stored Google Cloud project ID |
| set_gcloud_project_id | 206 | public | None | No | Persist the Google Cloud project ID |

##### Methods — records, directories & feature settings
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| save_details_record | 210 | public | None | No | Append a template/details record to history |
| load_details_records | 218 | public | list | No | Load all template/details records |
| get_images_dir | 232 | public | Path | No | Directory for saved images |
| get_layout_config | 240 | public | Dict[str, Any] | No | Layout-module configuration block |
| set_layout_config | 244 | public | None | No | Replace the layout configuration block |
| get_templates_dir | 248 | public | Path | No | Layout template directory |
| get_fonts_dir | 272 | public | Optional[Path] | No | Optional custom-fonts directory |
| get_layout_export_dpi | 284 | public | int | No | Default DPI for layout exports |
| set_layout_export_dpi | 289 | public | None | No | Persist layout export DPI |
| get_layout_llm_provider | 295 | public | str | No | LLM provider for layout text generation |
| set_layout_llm_provider | 300 | public | None | No | Persist layout LLM provider |
| get_layout_llm_model | 306 | public | str | No | Last-selected layout designer model |
| set_layout_llm_model | 311 | public | None | No | Persist layout designer model choice |
| get_layout_content_kind | 317 | public | str | No | Last-selected designer content kind |
| set_layout_content_kind | 322 | public | None | No | Persist designer content-kind choice |
| get_layout_style_role | 328 | public | str | No | Last-viewed style role in the Style panel |
| set_layout_style_role | 333 | public | None | No | Persist the Style panel's last-viewed role |
| get_discord_config | 341 | public | Dict[str, Any] | No | Discord Rich Presence configuration |
| set_discord_config | 363 | public | None | No | Replace the Discord configuration block |
| get_discord_enabled | 367 | public | bool | No | Whether Rich Presence is enabled |
| set_discord_enabled | 371 | public | None | No | Enable/disable Rich Presence |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_api_key_url | 378 | public | str | No | Documentation URL for obtaining a provider's API key |

---

### Prompt Enhancer
**Path**: `core/prompt_enhancer.py` - 358 lines
**Purpose**: Builds the structured "ImageAI Prompt Enhancer" LLM request (system prompt, schema, style presets) and converts the enhanced result into per-provider prompts, with non-LLM fallbacks.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| EnhancementLevel | 12 | Enum | LOW, MEDIUM, HIGH |

#### Class: PromptEnhancer
**Line**: 18-358
Holds the `SYSTEM_PROMPT` template and preset/schema loading logic.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 48 | constructor | - | No | Load schema/preset JSON from the plans directory |
| _load_json | 71 | private | Dict | No | Read a JSON resource file |
| get_preset | 84 | public | Optional[Dict] | No | Look up a style preset by ID |
| build_user_prompt | 99 | public | str | No | Assemble the full user prompt from all enhancement options |
| enhance_prompt | 193 | public | Dict[str, Any] | No | Run enhancement through an LLM client and parse the result |
| _create_enhanced_prompt | 295 | private | str | No | Basic non-LLM enhancement fallback |
| _enhance_for_gemini | 307 | private | str | No | Gemini/Imagen-optimized phrasing |
| _enhance_for_dalle | 313 | private | str | No | DALL·E 3-optimized phrasing |
| get_enhanced_prompt_for_provider | 323 | public | str | No | Pick the right `by_model` prompt for a target provider |

---

### Prompt Enhancer (LLM backend)
**Path**: `core/prompt_enhancer_llm.py` - 354 lines
**Purpose**: Executes prompt enhancement against a real LLM through LiteLLM, normalizing plain-text answers into the structured schema and providing a fallback response when the call fails.
**Language**: Python

#### Class: PromptEnhancerLLM
**Line**: 16-354

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 19 | constructor | - | No | Bind the default LLM provider |
| enhance_with_llm | 30 | public | Dict[str, Any] | No | Enhance a prompt with a live LLM call (level, aspect, preset, variants) |
| _call_with_litellm | 142 | private | Dict[str, Any] | No | Perform the LiteLLM completion with per-model parameter quirks |
| _text_to_structured | 267 | private | Dict[str, Any] | No | Wrap a plain-text enhancement in the structured schema |
| _create_fallback_response | 315 | private | Dict[str, Any] | No | Build a usable response when the LLM is unavailable |
| get_enhanced_prompt_for_provider | 333 | public | Optional[str] | No | Extract the provider-specific prompt from enhanced data |

---

### Tag Searcher
**Path**: `core/tag_searcher.py` - 346 lines
**Purpose**: Semantic-ish search over Prompt Builder items (artists, styles, mediums…) using pre-generated tag metadata, with per-category grouping and relevance scoring.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| SearchResult | 19 | @dataclass | item, category, score, matched_on |

#### Class: TagSearcher
**Line**: 27-346

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 48 | constructor | - | No | Load tag metadata from the given path |
| _load_metadata | 66 | private | bool | No | Parse the metadata JSON into memory |
| search | 91 | public | List[SearchResult] | No | Rank items against a query, optionally within one category |
| search_by_category | 152 | public | Dict[str, List[SearchResult]] | No | Search all categories, grouping results per category |
| _score_item | 183 | private | Tuple[float, List[str]] | No | Compute an item's relevance score and what matched |
| get_related_items | 284 | public | Dict[str, List[str]] | No | Items related to a given item via shared tags |
| get_item_tags | 307 | public | List[str] | No | All tags attached to one item |
| get_all_tags | 324 | public | Set[str] | No | Unique tag set, optionally scoped to a category |

---

### LLM Models Registry
**Path**: `core/llm_models.py` - 333 lines
**Purpose**: Central catalog of LLM providers, their model lists, and LiteLLM prefixes. Model IDs are resolved at runtime from the bundled model-registry snapshot via `resolve_model()` — cloud model IDs must never be hardcoded elsewhere.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| _REGISTRY_PROVIDER | 28 | constant | Provider-name mapping used against the registry snapshot |
| _REGISTRY_FAMILIES | 45 | constant | Cached provider→family→model-id map loaded at import |
| LLM_PROVIDERS | 94 | constant | The full `LLMProvider` catalog (OpenAI, Google, Anthropic, Ollama, …) |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| LLMProvider | 81 | @dataclass | id, display_name, models, enabled_by_default, requires_api_key, endpoint, prefix |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| _load_registry_families | 35 | private | Dict[str, Dict[str, str]] | No | Read provider→family→model-id from the bundled snapshot (no network) |
| _provider_models | 48 | private | List[str] | No | Current family IDs from the snapshot, followed by a curated legacy tail |
| resolve_model | 63 | public | str | No | Resolve the current model ID for a (provider, family) pair |
| get_provider_models | 186 | public | List[str] | No | Model list for a provider |
| get_all_provider_ids | 200 | public | List[str] | No | Every known provider ID |
| get_provider_display_name | 210 | public | str | No | Human-readable provider name |
| get_provider_config | 224 | public | Optional[LLMProvider] | No | Full provider record |
| get_provider_prefix | 238 | public | str | No | LiteLLM prefix (e.g. `gemini/`, `ollama/`) |
| get_enabled_providers | 252 | public | List[str] | No | Providers enabled by default |
| format_provider_dict | 262 | public | Dict[str, Dict[str, any]] | No | Provider dict shaped for `VideoConfig` compatibility |
| fetch_ollama_models | 280 | public | List[str] | No | Query a local Ollama server for installed models |
| update_ollama_models | 314 | public | bool | No | Refresh the Ollama provider's model list in place |

---

### Recycle Bin
**Path**: `core/recycle_bin.py` - 290 lines
**Purpose**: Cross-platform "move to trash" so deletions are recoverable — `send2trash` when available, otherwise native shell32 / osascript / `gio trash` paths.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| SEND2TRASH_AVAILABLE | 18 | constant | True branch — `send2trash` imported |
| SEND2TRASH_AVAILABLE | 20 | constant | False branch — import failed |
| FO_DELETE | 102 | constant | shell32 file-operation code (Windows path, function-local) |
| FOF_ALLOWUNDO | 103 | constant | shell32 flag enabling undo (recycle rather than delete) |
| FOF_NOCONFIRMATION | 104 | constant | shell32 flag suppressing confirmation dialogs |
| FOF_SILENT | 105 | constant | shell32 flag suppressing progress UI |

#### Classes
| Class | Line | Base | Description |
|-------|------|------|-------------|
| RecycleBinError | 24 | Exception | Raised when a file cannot be moved to the recycle bin |
| SHFILEOPSTRUCT | 89 | ctypes.Structure | Win32 file-operation struct declared inside `_windows_recycle` |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| send_to_recycle_bin | 29 | public | bool | No | Trash a file instead of permanently deleting it (dispatches per OS) |
| _windows_recycle | 74 | private | bool | No | Windows implementation via shell32 `SHFileOperation` |
| _macos_recycle | 133 | private | bool | No | macOS implementation via `osascript` |
| _linux_recycle | 166 | private | bool | No | Linux implementation via `gio trash` / `trash-cli` |
| is_recycle_bin_available | 225 | public | bool | No | Whether trashing works on this system |
| get_recycle_bin_status | 257 | public | str | No | Human-readable availability status for the UI |

---

### Security Utilities
**Path**: `core/security.py` - 283 lines
**Purpose**: Path-traversal validation, OS-keyring-backed API key storage, and a per-provider API rate limiter.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| KEYRING_AVAILABLE | 23 | constant | True branch — `keyring` imported |
| KEYRING_AVAILABLE | 25 | constant | False branch — falls back to file storage |

#### Class: PathValidator
**Line**: 30-79
Static validators guarding against directory traversal and unsafe filenames.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @staticmethod is_safe_path | 34 | static | bool | No | Confirm a path stays inside its base directory |
| @staticmethod validate_filename | 58 | static | bool | No | Reject filenames containing dangerous characters |

#### Class: SecureKeyStorage
**Line**: 82-166
Stores API keys in the system keyring under service name `ImageAI`, degrading to file-based storage when `keyring` is missing.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 87 | constructor | - | No | Detect keyring availability |
| store_key | 93 | public | bool | No | Store a provider's API key securely |
| retrieve_key | 119 | public | Optional[str] | No | Retrieve a stored API key |
| delete_key | 144 | public | bool | No | Remove a stored API key |

#### Class: RateLimiter
**Line**: 169-277
Sliding-window rate limiting for outbound provider API calls.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 172 | constructor | - | No | Initialize per-provider call history and defaults |
| set_limit | 185 | public | - | No | Set a custom calls/window limit for a provider |
| check_rate_limit | 196 | public | bool | No | Check (and optionally wait for) rate-limit headroom |
| get_remaining_calls | 245 | public | tuple[int, float] | No | Remaining calls and seconds until the window resets |

---

### Upscaling
**Path**: `core/upscaling.py` - 275 lines
**Purpose**: Upscales generated images to a requested resolution via Lanczos resampling, Real-ESRGAN, or the Stability AI upscale endpoint — always scaling proportionally.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| REALESRGAN_AVAILABLE | 27 | constant | True branch — Real-ESRGAN importable |
| REALESRGAN_AVAILABLE | 29 | constant | False branch — Real-ESRGAN unavailable |

#### Class: UpscalingMethod
**Line**: 31-36
Plain constant holder (not an `Enum`) with the method identifiers `NONE`, `LANCZOS`, `REALESRGAN`, `STABILITY_API`.

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| upscale_image | 39 | public | bytes | No | Dispatch to the requested upscaling method |
| upscale_lanczos | 84 | public | bytes | No | Traditional Lanczos resampling upscale |
| upscale_realesrgan | 118 | public | bytes | No | AI upscale via a local Real-ESRGAN model |
| upscale_stability_api | 181 | public | bytes | No | Upscale through Stability AI's hosted API |
| needs_upscaling | 248 | public | bool | No | Whether the current size falls short of the target |
| get_upscaling_factor | 262 | public | float | No | Scale factor required to reach the target size |

---

### Conversation Manager
**Path**: `core/conversation_manager.py` - 258 lines
**Purpose**: Tracks multi-turn image generation/editing conversations, keeping the provider chat session, message history, and current image path together with LRU eviction.
**Language**: Python

#### Class: ImageConversation
**Line**: 16-109
One conversation: its ID, model, chat session handle, and message/image history.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 23 | constructor | - | No | Initialize ID, initial prompt, model, and history |
| set_chat_session | 48 | public | - | No | Attach the SDK chat session |
| get_chat_session | 58 | public | - | No | Retrieve the attached chat session |
| add_message | 62 | public | - | No | Append a role/content message with optional image bytes/path |
| has_chat_session | 87 | public | bool | No | Whether a live chat session exists |
| get_message_count | 91 | public | int | No | Number of messages recorded |
| to_dict | 95 | public | Dict[str, Any] | No | Serialize conversation metadata |

#### Class: ConversationManager
**Line**: 112-246
Registry of active conversations, indexed by ID and by current image path.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 122 | constructor | - | No | Initialize the conversation store |
| create_conversation | 127 | public | ImageConversation | No | Start a new conversation from a prompt/model/image |
| get_conversation | 167 | public | Optional[ImageConversation] | No | Look up by conversation ID |
| get_conversation_by_image_path | 185 | public | Optional[ImageConversation] | No | Look up by the conversation's current image path |
| get_recent_conversations | 201 | public | List[ImageConversation] | No | Most recent conversations, newest first |
| remove_conversation | 214 | public | - | No | Drop a conversation |
| _evict_old_conversations | 227 | private | - | No | Evict oldest entries when the cap is exceeded |
| clear_all | 242 | public | - | No | Remove every conversation |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_conversation_manager | 253 | public | ConversationManager | No | Accessor for the process-wide manager singleton |

---

### Google Cloud Utilities
**Path**: `core/gcloud_utils.py` - 245 lines
**Purpose**: Locates the `gcloud` CLI across platforms, reads the active project, and reports Application Default Credentials auth status used to pick default providers.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| GCLOUD_AVAILABLE | 14 | constant | True branch — Google auth libraries importable |
| GCLOUD_AVAILABLE | 19 | constant | False branch — libraries missing |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| find_gcloud_command | 22 | public | Optional[str] | No | Locate the `gcloud` executable across Windows/macOS/Linux/WSL |
| get_gcloud_project_id | 100 | public | Optional[str] | No | Current Google Cloud project ID |
| is_gcloud_authenticated | 125 | public | bool | No | Fast auth check used for defaults |
| get_default_llm_provider | 166 | public | str | No | "Google" when a Google key or gcloud auth exists, else "OpenAI" |
| check_gcloud_auth_status | 191 | public | Tuple[bool, str] | No | Auth flag plus a human-readable status message |

---

### Wikimedia Commons Client
**Path**: `core/wikimedia_client.py` - 244 lines
**Purpose**: Searches Wikimedia Commons for reference imagery and downloads selected files.
**Language**: Python

#### Class: WikimediaImage
**Line**: 11-27
Value object describing a Commons image.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 14 | constructor | - | No | Store title, URL, thumbnail, description, dimensions, upload date |
| __repr__ | 26 | public | - | No | Debug representation |

#### Class: WikimediaClient
**Line**: 30-244

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 36 | constructor | - | No | Prepare the HTTP session and API endpoint |
| search_images | 42 | public | List[WikimediaImage] | No | Search Commons for images matching a query |
| download_image | 136 | public | bool | No | Download an image to a local path |
| get_image_by_filename | 169 | public | Optional[WikimediaImage] | No | Fetch image info by exact Commons filename |

---

### Whisper Installer
**Path**: `core/whisper_installer.py` - 226 lines
**Purpose**: Detects and installs the Whisper audio-analysis dependency set (used for lyric/audio alignment) with GPU-aware wheel selection.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| check_whisper_installed | 17 | public | Tuple[bool, str] | No | Whether Whisper and its audio packages are present |
| get_whisper_packages | 54 | public | Tuple[List[str], str] | No | Package list with GPU-support detection |
| get_whisper_disk_space_required | 107 | public | float | No | Disk space (GB) required for the install |

#### Class: WhisperPackageInstaller
**Line**: 116-226 · **Base**: `QThread`

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 123 | constructor | - | No | Store packages and optional index URL |
| run | 129 | public | - | No | Run the install with progress signalling |
| _install_package | 179 | private | Tuple[bool, str] | No | pip-install a single package |
| stop | 211 | public | - | No | Request cooperative cancellation |
| _format_duration | 215 | private | str | No | Human-readable elapsed time |

---

### Logging Configuration
**Path**: `core/logging_config.py` - 224 lines
**Purpose**: Sets up application-wide logging (file + console), captures Python warnings, registers an `atexit` hook that copies the session log to `./imageai_current.log`, and provides named-logger and exception-context helpers.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| setup_logging | 17 | public | - | No | Configure handlers, levels, warning capture, and exit-copy hook; returns the log path |
| copy_log_on_exit | 119 | private | - | No | Nested `atexit` callback that copies the log to the working directory |
| get_error_report_info | 136 | public | - | No | Gather environment/log details for an error report |

#### Class: LogManager
**Line**: 174-196
Factory for loggers namespaced under `imageai`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 182 | constructor | - | No | Initialize the logger cache |
| get_logger | 186 | public | logging.Logger | No | Get/create a named logger in the `imageai` namespace |

#### Class: ErrorLogger
**Line**: 199-224
Context manager that logs any exception raised inside the block, with an operation label and optional re-raise.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 202 | constructor | - | No | Store operation name, logger, and re-raise flag |
| __enter__ | 213 | public | - | No | Enter the context |
| __exit__ | 216 | public | - | No | Log the exception and re-raise unless suppressed |

---

### Image Utilities
**Path**: `core/image_utils.py` - 220 lines
**Purpose**: Post-processing helpers that strip letterbox/solid borders, crop to a target aspect ratio (centered), and detect an image's true content aspect ratio.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| auto_crop_solid_borders | 11 | public | bytes | No | Remove uniform-color borders using per-line color variance |
| calculate_line_variance | 38 | private | float | No | Nested helper computing color variance for one pixel line |
| crop_to_aspect_ratio | 127 | public | bytes | No | Center-crop to a target aspect ratio |
| detect_aspect_ratio | 196 | public | Tuple[int, int] | No | Detect content aspect ratio after auto-cropping |

---

### Constants
**Path**: `core/constants.py` - 161 lines
**Purpose**: Application metadata (including `VERSION`, the primary version definition), provider/model catalogs for the image-generation UI, default sizes and window geometry, template categories, Discord presence constants, and the user-data directory resolver.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| APP_NAME | 8 | constant | `"ImageAI"` |
| VERSION | 9 | constant | Primary version string (source of truth for version bumps) |
| DEFAULT_PROVIDER | 17 | constant | Default image provider (`google`) |
| DEFAULT_MODEL | 18 | constant | Default image model (`gemini-2.5-flash-image`) |
| PROVIDER_MODELS | 24 | constant | Image-generation model catalog per provider, newest-first for UI display |
| GPT_IMAGE_2_SNAPSHOT | 60 | constant | Pinned OpenAI gpt-image-2 snapshot for reproducible sidecar metadata |
| PROVIDER_KEY_URLS | 63 | constant | Where to obtain each provider's API key |
| README_PATH | 71 | constant | Path to the bundled README |
| GEMINI_TEMPLATES_PATH | 72 | constant | Path to the Gemini template resources |
| DEFAULT_IMAGE_SIZE | 75 | constant | Default generation size |
| DEFAULT_NUM_IMAGES | 76 | constant | Default image count |
| DEFAULT_QUALITY | 77 | constant | Default quality setting |
| DEFAULT_WINDOW_WIDTH | 80 | constant | Initial main-window width |
| DEFAULT_WINDOW_HEIGHT | 81 | constant | Initial main-window height |
| PREVIEW_MAX_WIDTH | 82 | constant | Preview pane max width |
| PREVIEW_MAX_HEIGHT | 83 | constant | Preview pane max height |
| TEMPLATE_CATEGORIES | 86 | constant | Prompt-template category list |
| IMAGE_FORMATS | 97 | constant | Supported image formats |
| DISCORD_CLIENT_ID | 107 | constant | Discord application ID for Rich Presence |
| DISCORD_UPDATE_INTERVAL | 108 | constant | Minimum seconds between presence updates |
| DISCORD_GITHUB_URL | 109 | constant | GitHub button URL in the presence card |
| DISCORD_SERVER_URL | 110 | constant | Discord invite button URL |
| DISCORD_PRIVACY_LEVELS | 113 | constant | Allowed privacy levels (full / activity_only / minimal) |
| DISCORD_ASSETS | 123 | constant | Presence image-asset keys |
| BATCH_JOBS_PATH | 161 | constant | Location of persisted batch-job records |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_user_data_dir | 140 | public | Path | No | Platform-specific ImageAI user-data directory |

---

### Prompt Data Loader
**Path**: `core/prompt_data_loader.py` - 150 lines
**Purpose**: Loads and caches the Prompt Builder's JSON vocabularies (artists, styles, mediums, colors, lighting, moods, banners) and writes edits back.
**Language**: Python

#### Class: PromptDataLoader
**Line**: 11-150

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 14 | constructor | - | No | Resolve the data directory and initialize the cache |
| load_data | 29 | public | List[str] | No | Load (and cache) one category's list |
| get_artists | 71 | public | List[str] | No | Artist list |
| get_styles | 75 | public | List[str] | No | Art-style list |
| get_mediums | 79 | public | List[str] | No | Medium/technique list |
| get_colors | 83 | public | List[str] | No | Color-scheme list |
| get_lighting | 87 | public | List[str] | No | Lighting-option list |
| get_moods | 91 | public | List[str] | No | Mood list |
| get_banners | 95 | public | List[str] | No | Banner/composition list |
| get_all_categories | 99 | public | Dict[str, List[str]] | No | Every category with its data |
| reload | 116 | public | - | No | Clear the cache and reload from disk |
| save_data | 121 | public | bool | No | Persist a category's data back to JSON |

---

### LLM Response Parsing
**Path**: `core/llm_parsing.py` - 124 lines
**Purpose**: Shared, fallback-tolerant parsing of LLM output — strips Markdown fences, recovers prompts from plain text, and synthesizes fallbacks when the model returns nothing usable. Used by both core pipelines and GUI dialogs.
**Language**: Python

#### Class: LLMResponseParser
**Line**: 15-124

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @staticmethod parse_json_response | 19 | static | Optional[Any] | No | Parse JSON from an LLM response, cleaning fences and stray prose |
| @staticmethod extract_text_prompts | 63 | static | List[str] | No | Pull N prompts out of a plain-text response |
| @staticmethod create_fallback_prompts | 105 | static | List[str] | No | Generate reasonable default prompts when the LLM fails |

---

### Core Package Init
**Path**: `core/__init__.py` - 69 lines
**Purpose**: Package facade — re-exports `ConfigManager`/`get_api_key_url`, application metadata and provider constants from `constants`, and the common helpers from `utils` via `__all__`.
**Language**: Python

No classes or functions are defined here; the module consists of re-export statements and the `__all__` list.

---

### Image Size Validation
**Path**: `core/image_size.py` - 69 lines
**Purpose**: Single shared implementation of custom width/height validation for OpenAI `gpt-image-2` and friends, called by both the provider pre-flight and the GUI's live red/green size label so the rules cannot drift.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| validate_custom_size | 12 | public | Tuple[bool, str] | No | Validate a custom WxH against a model-capability row (min/max pixels, custom-size support) |
| parse_size_string | 61 | public | Tuple[int, int] | No | Parse a `"WxH"` string into a `(width, height)` tuple |

---

### Project Tracker
**Path**: `core/project_tracker.py` - 42 lines
**Purpose**: Records the currently loaded project file and copies it to `./imageai_current_project.json` on exit for support and debugging.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| set_current_project | 16 | public | - | No | Register the project file to copy on exit |
| copy_project_on_exit | 29 | public | - | No | Copy the tracked project file into the working directory |

---

## Core Video — Prompt Engine, Project Model & Analysis

This group covers the data model and "brains" of the video subsystem: the LLM
prompt engine, the persisted project/scene model, LLM- and Whisper-based timing
analysis, event-sourced history, reference-image handling, thumbnails, image
processing, and cross-scene visual continuity.

---

### PromptEngine / UnifiedLLMProvider
**Path**: `core/video/prompt_engine.py` - 1466 lines
**Purpose**: LLM-backed prompt generation and enhancement — turns plain lyric/scene text into cinematic image and video prompts via LiteLLM, with retry/backoff, batch modes, and Jinja2 templates.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| T | 12 | constant | `TypeVar('T')` used by the retry-wrapper generics |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| PromptStyle | 21 | Enum | CINEMATIC, ARTISTIC, PHOTOREALISTIC, ANIMATED, DOCUMENTARY, ABSTRACT, NOIR, FANTASY, SCIFI, VINTAGE, MINIMALIST, DRAMATIC |
| PromptTemplate | 38 | @dataclass | name, template_path, template_string, variables |

#### Class: PromptTemplate (line 38)
A single reusable prompt template, backed either by a file path or an inline string.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| render | 45 | public | str | No | Render the template with the supplied keyword variables |

#### Class: UnifiedLLMProvider (line 62)
Single façade over every LLM backend (OpenAI, Anthropic, Google Gemini, Ollama, LM Studio) through LiteLLM. Owns API-key/endpoint setup, transient-error retry, response cleanup, and all prompt-enhancement entry points.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 70 | constructor | None | No | Store config and wire up provider credentials |
| _setup_providers | 95 | private | None | No | Set API keys / base URLs for each supported provider |
| is_available | 138 | public | bool | No | Whether LiteLLM is importable and usable |
| list_models | 142 | public | List[str] | No | List available model IDs for a provider |
| _is_retryable_error | 154 | private | bool | No | Classify an exception as transient (retry) vs. fatal |
| _retry_with_backoff | 195 | private | Any | No | Exponential-backoff retry wrapper around an LLM call |
| _strip_markdown_headers | 250 | private | str | No | Strip `#` headers, bold markers, and bullets from LLM output |
| _create_smart_fallback | 280 | private | str | No | Build a context-aware fallback prompt when the LLM fails |
| enhance_prompt | 328 | public | str | No | Enhance one text prompt for image generation in the chosen style |
| ↳ make_enhance_call | 424 | nested | — | No | Inner closure passed to the retry wrapper by `enhance_prompt` |
| batch_enhance | 485 | public | List[str] | No | Enhance many prompts, chunking into batched LLM calls |
| _parse_batch_response | 524 | private | list | No | Parse numbered/enumerated LLM batch output into a list |
| _batch_enhance_single | 575 | private | List[str] | No | Enhance one chunk of a batch (internal worker) |
| batch_enhance_for_video | 685 | public | List[str] | No | One-call video enhancement for all scenes: camera movement, motion, temporal progression, lyric timings, and cross-scene flow |
| analyze_image | 939 | public | str | No | Vision-model image analysis with automatic retry/backoff |
| ↳ make_llm_call | 1000 | nested | — | No | Inner closure performing the actual vision call under retry |
| generate | 1024 | public | — | No | Backward-compatible alias for `analyze_image` |
| _get_system_prompt | 1028 | private | str | No | System prompt text for a given `PromptStyle` |

#### Class: PromptEngine (line 1132)
Higher-level engine used by the GUI/CLI: owns a `UnifiedLLMProvider` plus a Jinja2 environment (defaults to `templates/video/`), and applies enhancement across `Scene` objects.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 1135 | constructor | None | No | Create/accept an LLM provider and resolve the template directory |
| enhance_scene_prompts | 1164 | public | List[Scene] | No | Enhance prompts for a list of scenes in batches |
| apply_template | 1210 | public | str | No | Render a Jinja2 template against a scene plus extra variables |
| enhance_prompt | 1257 | public | str | No | Delegate single-prompt enhancement to the provider |
| regenerate_prompt | 1284 | public | str | No | Regenerate one scene's prompt (fresh LLM pass) |
| enhance_for_video | 1319 | public | str | No | Video-specific enhancement for one scene, using previous-scene context for continuity |

---

### VideoProject Data Model
**Path**: `core/video/project.py` - 1055 lines
**Purpose**: Canonical data model and JSON persistence for video projects — scenes, prompts + undo history, image variants, reference images, audio tracks, MIDI/karaoke settings, and provider configuration.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| MIDI_SUPPORT | 21 | constant | `True` when `midi_processor` / `karaoke_renderer` import successfully |
| MIDI_SUPPORT | 25 | constant | `False` fallback set in the `ImportError` branch |
| REFERENCE_MANAGER_AVAILABLE | 30 | constant | `True` when `reference_manager.ReferenceImageType` imports |
| ReferenceImageType | 33 | class (fallback) | Local Enum stand-in (CHARACTER/OBJECT/ENVIRONMENT/STYLE) when `reference_manager` is unavailable |
| REFERENCE_MANAGER_AVAILABLE | 38 | constant | `False` fallback set in the `ImportError` branch |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| VideoProvider | 41 | Enum | VEO, SLIDESHOW |
| SceneStatus | 47 | Enum | PENDING, GENERATING, COMPLETED, ERROR |
| AudioTrack | 56 | @dataclass | track_id, file_path, track_type, volume, fade_in_duration, fade_out_duration, start_offset, end_offset |
| ReferenceImage | 164 | @dataclass | path, ref_type, name, description, is_global, auto_linked, label, metadata |
| ImageVariant | 252 | @dataclass | path, provider, model, seed, cost, metadata, generated_at |
| Scene | 289 | @dataclass | id, source, prompt, video_prompt, prompt_history, duration_sec, images, approved_image, video_clip, first_frame, last_frame, use_last_frame_as_seed, caption, status, order, metadata, end_prompt, end_frame_images, end_frame, end_frame_auto_linked, reference_images, use_global_references, environment, scene_group_id |
| VideoProject | 442 | @dataclass | schema, name, project_id, created/modified, LLM+image+video provider/model, prompt_template, prompt_style, style, variants, ken_burns, transitions, captions, video_muted, auto_link_enabled, enable_camera_movements, enable_prompt_flow, continuity_mode, enable_continuity, enable_enhanced_storyboard, use_last_frame_for_continuous, input_text/format, timing_preset, target_duration, aspect_ratio, resolution, seed, negative_prompt, audio_tracks, midi_file_path, midi_timing_data, sync_mode, snap_strength, word_timestamps, whisper_model_used, lyrics_extracted, auto_suggest_scenes, karaoke_config, karaoke_export_formats, karaoke_generated_files, suno_package_path, suno_selected_stems, suno_selected_midi, scenes, veo_batches, global_reference_images, extracted_frames, project_dir, export_path, total_cost, wizard_enabled |

#### Class: AudioTrack (line 56)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 67 | public | Dict[str, Any] | No | Serialize track for JSON |
| @classmethod from_dict | 81 | class | 'AudioTrack' | No | Rebuild a track from persisted JSON |

#### Class: PromptHistory (line 95)
Per-field undo/redo stack for prompt editing (256 levels).

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 98 | constructor | None | No | Create the ring with a max size |
| add | 103 | public | None | No | Push a new prompt, truncating any redo tail |
| can_undo | 118 | public | bool | No | Whether an undo step exists |
| can_redo | 122 | public | bool | No | Whether a redo step exists |
| undo | 126 | public | Optional[str] | No | Step back and return the prior prompt |
| redo | 133 | public | Optional[str] | No | Step forward and return the next prompt |
| get_current | 140 | public | Optional[str] | No | Current prompt at the cursor |
| to_dict | 146 | public | Dict[str, Any] | No | Serialize the history |
| @classmethod from_dict | 155 | class | 'PromptHistory' | No | Restore history from JSON |

#### Class: ReferenceImage (line 164)
A style/character/environment/object reference used to keep generations consistent.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __post_init__ | 175 | private | None | No | Backward-compat normalization for legacy project files |
| to_dict | 196 | public | Dict[str, Any] | No | Serialize reference (path + type as strings) |
| @classmethod from_dict | 210 | class | 'ReferenceImage' | No | Rebuild reference, tolerating legacy key names |

#### Class: ImageVariant (line 252)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 262 | public | Dict[str, Any] | No | Serialize variant metadata |
| @classmethod from_dict | 275 | class | 'ImageVariant' | No | Restore variant from JSON |

#### Class: Scene (line 289)
One storyboard beat: source text, image/video prompts, generated variants, approved image, first/last/end frames, and its own reference images.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 322 | public | Dict[str, Any] | No | Serialize the scene, including variants and references |
| @classmethod from_dict | 355 | class | 'Scene' | No | Rebuild a scene from persisted JSON |
| add_prompt_to_history | 387 | public | None | No | Record a prompt in history when it differs from current |
| uses_veo_31 | 394 | public | bool | No | True when an end frame is set (Veo 3.1 path) |
| can_generate_video | 398 | public | bool | No | Whether the scene has everything needed to render video |
| add_reference_image | 404 | public | bool | No | Attach a scene-level reference (capped, default max 3) |
| get_effective_reference_images | 421 | public | List[ReferenceImage] | No | Merge scene refs with project globals per the scene's flag |
| clear_reference_images | 435 | public | None | No | Drop all scene-specific references |

#### Class: VideoProject (line 442)
Root aggregate: metadata, provider/model choices, render options, audio/MIDI/karaoke config, scenes, global references, and file I/O.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 544 | public | Dict[str, Any] | No | Serialize the whole project graph to JSON-safe dicts |
| @classmethod from_dict | 627 | class | 'VideoProject' | No | Rebuild a project, handling schema/legacy migration |
| save | 760 | public | Path | No | Write the project JSON to disk and return the path |
| @classmethod load | 778 | class | 'VideoProject' | No | Read and deserialize a project JSON file |
| add_scene | 824 | public | Scene | No | Append a new scene with source text, prompt, and duration |
| reorder_scenes | 835 | public | None | No | Reorder scenes by an explicit list of IDs |
| get_total_duration | 845 | public | float | No | Sum of scene durations in seconds |
| get_veo_batch_for_scene | 849 | public | Optional[Dict[str, Any]] | No | Look up the Veo batched prompt covering a scene index |
| add_audio_track | 870 | public | AudioTrack | No | Register an audio file as a typed track |
| get_workflow_wizard | 882 | public | WorkflowWizard \| None | No | Build a fresh (non-persisted) wizard over current state |
| get_wizard_next_step | 901 | public | Optional[str] | No | One-line "what to do next" string from the wizard |
| add_global_reference | 916 | public | bool | No | Add a project-wide reference (only 3 are used per request) |
| remove_global_reference | 933 | public | bool | No | Remove a global reference by path |
| get_references_by_type | 949 | public | List[ReferenceImage] | No | Filter references by type, optionally including globals |
| get_references_by_name | 981 | public | List[ReferenceImage] | No | Case-insensitive partial-name reference lookup |
| get_effective_references_for_scene | 1000 | public | List[ReferenceImage] | No | Resolve the final reference set sent for a scene (respects max and explicit selection) |
| get_all_available_references | 1030 | public | List[ReferenceImage] | No | Full candidate set for the reference-picker dialog |
| has_character_references | 1046 | public | bool | No | Whether any CHARACTER reference exists |
| clear_global_references | 1053 | public | None | No | Remove all global references |

---

### LLM Sync Assistant
**Path**: `core/video/llm_sync.py` - 626 lines
**Purpose**: LLM-assisted (and heuristic-fallback) timing estimation — distributes lyrics or scene descriptions across a duration, honoring section markers, explicit durations, and MIDI sections.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| TimedLyric | 17 | @dataclass | text, start_time, end_time, section_type |

#### Class: LLMSyncAssistant (line 25)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 28 | constructor | None | No | Bind provider, model, and config for LLM calls |
| estimate_lyric_timing | 51 | public | List[TimedLyric] | No | Entry point: time lyrics against total duration and optional sections |
| _simple_timing_distribution | 76 | private | List[TimedLyric] | No | Even/weighted distribution when no section data exists |
| _sync_with_sections | 122 | private | List[TimedLyric] | No | Align lyric blocks to MIDI-derived section boundaries |
| _parse_lyric_sections | 165 | private | Dict[str, List[str]] | No | Split lyrics on `[Verse 1]`/`[Chorus]`-style markers |
| _is_section_marker | 199 | private | bool | No | Detect a bracketed section-marker line |
| _extract_section_type | 203 | private | str | No | Normalize a marker into a section type |
| _detect_section_type | 223 | private | Optional[str] | No | Infer section type from plain line content |
| _estimate_line_duration | 229 | private | float | No | Weight a line's duration by length/syllable heuristics |
| estimate_timing_from_descriptions | 246 | public | List[TimedLyric] | No | LLM-estimate realistic per-scene timings when no MIDI exists |
| estimate_timing_with_explicit | 371 | public | List[TimedLyric] | No | Fill in timings only for scenes lacking explicit durations |
| sync_with_llm | 455 | public | List[TimedLyric] | No | Full LLM alignment pass over lyrics + audio duration/sections |

---

### Project Enhancements (Versioning, Variants, Ken Burns)
**Path**: `core/video/project_enhancements.py` - 522 lines
**Purpose**: Project-level enhancement layer — directory versioning, per-scene image variants, crop settings, and Ken Burns presets, plus the manager that persists them on disk.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| VersioningMode | 18 | Enum | NONE, TIMESTAMP, SEQUENTIAL, BOTH |
| CropMode | 26 | Enum | CENTER, RULE_OF_THIRDS, MANUAL, SMART, TOP, BOTTOM |
| AudioHandling | 36 | Enum | LINK, COPY, CONVERT |
| CropSettings | 44 | @dataclass | mode, position, scale |
| KenBurnsSettings | 67 | @dataclass | enabled, start, end, duration_factor, easing |
| ProjectSettings | 84 | @dataclass | name, versioning_mode, ken_burns_enabled/intensity, auto_ken_burns_for_square, default_crop_mode/position, images_per_scene, auto_crop_square, auto_save_renders, keep_draft_renders, render_quality, audio_handling |
| ImageVariant | 149 | @dataclass | filename, provider, prompt, timestamp, is_selected, crop_settings, ken_burns_settings, metadata |
| SceneVariants | 189 | @dataclass | scene_index, variants, selected_index, max_variants |

#### Class: CropSettings (line 44)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 50 | public | Dict[str, Any] | No | Serialize crop mode/position/scale |
| @classmethod from_dict | 58 | class | 'CropSettings' | No | Restore crop settings from JSON |

#### Class: KenBurnsSettings (line 67)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 75 | public | Dict[str, Any] | No | Serialize pan/zoom start & end plus easing |
| @classmethod from_dict | 79 | class | 'KenBurnsSettings' | No | Restore Ken Burns settings from JSON |

#### Class: ProjectSettings (line 84)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 110 | public | Dict[str, Any] | No | Serialize settings (enums → values) |
| @classmethod from_dict | 129 | class | 'ProjectSettings' | No | Restore settings, coercing enum fields |

#### Class: ImageVariant (line 149)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 160 | public | Dict[str, Any] | No | Serialize variant with crop/Ken Burns settings |
| @classmethod from_dict | 174 | class | 'ImageVariant' | No | Restore variant from JSON |

#### Class: SceneVariants (line 189)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| add_variant | 196 | public | bool | No | Append a variant, enforcing `max_variants` |
| select_variant | 210 | public | None | No | Mark one variant as the selected image |
| get_selected | 220 | public | Optional[ImageVariant] | No | Return the currently selected variant |
| to_dict | 227 | public | Dict[str, Any] | No | Serialize the variant set |
| @classmethod from_dict | 236 | class | 'SceneVariants' | No | Restore the variant set from JSON |

#### Class: KenBurnsPresets (line 246)
Named Ken Burns templates (disabled, subtle zoom, and other pan/zoom recipes) held in a class-level `PRESETS` mapping.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @classmethod get_preset | 302 | class | KenBurnsSettings | No | Look up a preset by name |
| @classmethod list_presets | 307 | class | List[str] | No | List available preset names |

#### Class: EnhancedProjectManager (line 312)
Creates and maintains versioned project directories, recent-project tracking, settings/variant persistence, and render-file naming.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 315 | constructor | None | No | Set base directory and load recent-project list |
| _load_recent_projects | 338 | private | List[Dict[str, Any]] | No | Read the recent-projects index |
| _save_recent_projects | 348 | private | None | No | Write the recent-projects index |
| _add_to_recent | 356 | private | None | No | Push a project to the front of the recent list |
| create_project_directory | 372 | public | Path | No | Create a versioned project folder from settings |
| _generate_folder_name | 395 | private | str | No | Build folder name per `VersioningMode` |
| _get_next_version | 417 | private | int | No | Next sequential version number for a base name |
| _sanitize_filename | 437 | private | str | No | Strip filesystem-hostile characters |
| save_project_settings | 444 | public | None | No | Persist `ProjectSettings` into the project dir |
| load_project_settings | 450 | public | ProjectSettings | No | Load settings (defaults when absent) |
| init_workspace | 459 | public | None | No | Create the workspace file/skeleton for a project |
| save_scene_variants | 471 | public | None | No | Write a scene's variant set to disk |
| load_scene_variants | 480 | public | SceneVariants | No | Read a scene's variant set from disk |
| get_render_filename | 492 | public | Path | No | Compose an output filename from settings + quality |
| clean_old_drafts | 508 | public | None | No | Prune draft renders beyond `keep_count` |

---

### Event Store (Version History)
**Path**: `core/video/event_store.py` - 516 lines
**Purpose**: Event-sourced project history in SQLite — append-only compressed events with checksums, periodic state snapshots, replay-based state rebuild, and named restore points.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| EventType | 20 | Enum | PROJECT_CREATED/OPENED/SAVED/CLOSED, SCENE_ADDED/UPDATED/DELETED/REORDERED, PROMPT_GENERATED/EDITED/REGENERATED/BATCH_GENERATED, IMAGE_GENERATED/REGENERATED/APPROVED/REJECTED, AUDIO_ADDED/REMOVED/SETTINGS_CHANGED, VIDEO_RENDERED/EXPORTED, SETTINGS_UPDATED, PROVIDER_CHANGED, MODEL_CHANGED |
| ProjectEvent | 62 | @dataclass | id, project_id, event_type, timestamp, user, data, metadata, checksum |

#### Class: ProjectEvent (line 62)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __post_init__ | 73 | private | None | No | Fill defaults and compute the checksum if missing |
| calculate_checksum | 83 | public | str | No | SHA-256 over the event payload (dedupe + integrity) |
| to_dict | 94 | public | Dict[str, Any] | No | Serialize event for storage/transport |
| @classmethod from_dict | 108 | class | 'ProjectEvent' | No | Rebuild an event from a stored row |

#### Class: EventStore (line 122)
SQLite store with an `events` table (compressed `data_compressed` BLOB, `UNIQUE(project_id, checksum)`), a `snapshots` table, and indexes on project/timestamp and event type.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 125 | constructor | None | No | Open/create the database at `db_path` |
| _init_database | 138 | private | None | No | Create the events/snapshots tables and indexes |
| append | 185 | public | int | No | Append an event (compressed, deduped by checksum); returns row id |
| get_events | 221 | public | List[ProjectEvent] | No | Query events by project, time window, type filter, and limit |
| create_snapshot | 291 | public | None | No | Store a compressed state snapshot pinned to an event id |
| get_latest_snapshot | 315 | public | Optional[Dict[str, Any]] | No | Most recent snapshot for a project |
| rebuild_state | 341 | public | Dict[str, Any] | No | Replay events (from the newest snapshot) up to a point in time |
| _apply_event | 364 | private | Dict[str, Any] | No | Fold a single event into the running state dict |
| get_project_history | 424 | public | List[Dict[str, Any]] | No | Human-readable history summary for the UI |
| _generate_event_summary | 449 | private | str | No | Render one event as a readable summary line |
| create_restore_point | 465 | public | int | No | Create a named/described restore point |
| get_restore_points | 491 | public | List[Dict[str, Any]] | No | List a project's restore points |

---

### Whisper Analyzer
**Path**: `core/video/whisper_analyzer.py` - 501 lines
**Purpose**: OpenAI Whisper integration for lyric extraction, word-level timestamps, and alignment of user-supplied lyrics against the audio; includes FFmpeg path patching for Windows/WSL setups.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| WHISPER_MODELS | 17 | constant | Model size table (tiny/base/small/medium/large) with disk size, VRAM need, and description |

#### Class: WhisperAnalyzer (line 26)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 36 | constructor | None | No | Record model size and device; defer model load |
| _ensure_model_loaded | 49 | private | None | No | Lazy-load the Whisper model on first use |
| _ensure_ffmpeg_available | 83 | private | None | No | Locate an FFmpeg binary, patching Whisper if needed |
| _patch_whisper_ffmpeg | 108 | private | None | No | Monkey-patch `whisper.audio.load_audio` to use a full FFmpeg path |
| ↳ make_patched_load_audio | 113 | nested | callable | No | Factory baking the FFmpeg path into the replacement loader |
| ↳ patched_load_audio | 115 | nested | np.ndarray | No | Replacement `load_audio` invoking FFmpeg by absolute path |
| extract_lyrics | 158 | public | TranscriptionResult | No | Transcribe audio to text with word-level timings and progress callbacks |
| _extract_word_timings | 244 | private | List[WordTiming] | No | Flatten Whisper segments into word timing records |
| verify_lyrics | 287 | public | AlignmentResult | No | Compare user-provided lyrics against the transcription and align them |
| _normalize_text | 374 | private | str | No | Lowercase / strip punctuation for comparison |
| _build_aligned_text | 385 | private | str | No | Rebuild the original lyrics with timing annotations |
| get_timing_for_text_segment | 403 | public | Tuple[float, float] | No | Start/end time of a text segment within a transcription |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| check_whisper_installed | 450 | public | Tuple[bool, str] | No | Whether Whisper is importable, plus a status message |
| get_recommended_model | 472 | public | str | No | Pick a Whisper model size for the available VRAM |

---

### Reference Manager
**Path**: `core/video/reference_manager.py` - 404 lines
**Purpose**: Reference-image typing, Veo-3 validation, relevance-scored selection per scene, last-frame continuity decisions, and generation of character reference sets.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| ReferenceImageType | 16 | Enum | CHARACTER, OBJECT, ENVIRONMENT, STYLE |
| ReferenceImageInfo | 25 | @dataclass | path, type, name, description, width, height, file_size_mb, format, aspect_ratio, is_valid, validation_errors, validation_warnings, metadata |

#### Class: ReferenceImageInfo (line 25)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __post_init__ | 41 | private | None | No | Initialize the error/warning lists and metadata defaults |

#### Class: ReferenceImageValidator (line 50)
Checks candidate references against Veo 3 requirements using class constants for minimum resolution (720), supported formats (PNG/JPEG/JPG), recommended aspect ratios, and a max file size (50 MB).

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @classmethod validate_reference_image | 60 | class | ReferenceImageInfo | No | Inspect an image file and produce info + errors/warnings |
| @classmethod get_validation_summary | 146 | class | str | No | Human-readable summary of a validation result |

#### Class: ReferenceManager (line 157)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 160 | constructor | None | No | Bind to a project directory for reference storage |
| organize_references_by_type | 170 | public | Dict[ReferenceImageType, List[ReferenceImage]] | No | Group references by type for UI display |
| _parse_reference_type | 192 | private | ReferenceImageType | No | Coerce a reference's stored type into the enum |
| select_references_for_scene | 216 | public | List[ReferenceImage] | No | Pick the best-matching references (default max 3) for a scene prompt |
| _score_reference_relevance | 254 | private | float | No | Score 0.0–1.0 how well a reference matches the prompt text |
| _get_reference_name | 275 | private | str | No | Display name for a reference (falls back to filename) |
| should_use_last_frame_continuity | 283 | public | Tuple[bool, str] | No | Decide whether to seed a scene from the previous scene's last frame, with a reason |
| generate_character_references | 344 | public | List[Path] | No | Generate a 3-image character reference set via an image generator |

---

### Thumbnail Manager
**Path**: `core/video/thumbnail_manager.py` - 362 lines
**Purpose**: Generates, composites, and caches storyboard thumbnails for scenes (with title overlays, image-count badges, and placeholder/error tiles).
**Language**: Python

#### Class: ThumbnailManager (line 16)
Class constants define the default (160×90) and storyboard (320×180) thumbnail sizes and a cache version key.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 23 | constructor | None | No | Set up the on-disk thumbnail cache directory |
| create_thumbnail | 34 | public | bytes | No | Render a thumbnail from raw image bytes, preserving aspect by default |
| create_scene_thumbnail | 88 | public | bytes | No | Composite a scene tile from multiple images plus title and count badge |
| get_cached_thumbnail | 176 | public | Optional[bytes] | No | Fetch a cached thumbnail by image hash + size |
| cache_thumbnail | 200 | public | None | No | Store a rendered thumbnail in the cache |
| create_thumbnail_with_cache | 220 | public | bytes | No | Cache-aware wrapper around `create_thumbnail` |
| _create_placeholder_thumbnail | 252 | private | bytes | No | Grey placeholder tile with centered text |
| _create_error_thumbnail | 279 | private | bytes | No | Error tile used when rendering fails |
| _add_title_overlay | 283 | private | None | No | Draw the scene title band onto the tile |
| _add_count_badge | 305 | private | None | No | Draw the "N images" badge onto the tile |
| clear_cache | 335 | public | None | No | Delete cached thumbnails older than N days |
| get_cache_size | 354 | public | int | No | Total cache size in bytes |

---

### Image Processor (Crop & Ken Burns)
**Path**: `core/video/image_processing.py` - 346 lines
**Purpose**: Aspect-ratio cropping, blurred letterbox backgrounds, Ken Burns keyframe paths, and smart crop positioning via face detection / saliency.
**Language**: Python

#### Class: ImageProcessor (line 16)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 19 | constructor | None | No | Trivial initializer (stateless processor) |
| get_image_dimensions | 22 | public | Tuple[int, int] | No | Read width/height without decoding the full image |
| calculate_crop_box | 27 | public | Tuple[int, int, int, int] | No | Compute the crop rectangle for a target aspect and `CropSettings` |
| crop_image | 100 | public | Path | No | Crop a file to a target aspect and write the result |
| create_blurred_background | 127 | public | Image.Image | No | Build a blurred fill background for letterboxed output |
| calculate_ken_burns_path | 165 | public | List[Dict[str, float]] | No | Produce per-frame pan/zoom keyframes for a duration |
| detect_faces | 229 | public | List[Tuple[int, int, int, int]] | No | Face bounding boxes used to bias smart crops |
| calculate_saliency_map | 243 | public | np.ndarray | No | Saliency map guiding smart crop placement |
| find_optimal_crop_position | 268 | public | Dict[str, float] | No | Choose a crop position from faces/saliency |
| generate_crop_preview | 316 | public | Image.Image | No | Render a downscaled preview of the proposed crop |

---

### Image Continuity Manager
**Path**: `core/video/image_continuity.py` - 315 lines
**Purpose**: Keeps visual style consistent across scenes by tailoring prompts per provider — Gemini iterative refinement, OpenAI reference IDs, Claude style guides, and consistent descriptions for local models.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| ContinuityMethod | 18 | Enum | ITERATIVE_REFINEMENT, REFERENCE_IDS, CONSISTENT_DESCRIPTION, STYLE_GUIDE |
| ContinuityContext | 27 | @dataclass | style_guide, previous_image, previous_image_id, previous_prompt, scene_history |

#### Class: ContinuityContext (line 27)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __post_init__ | 35 | private | None | No | Initialize the scene-history list |

#### Class: ImageContinuityManager (line 40)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 43 | constructor | None | No | Create the per-project context registry |
| get_continuity_method | 47 | public | ContinuityMethod | No | Best continuity strategy for a given provider |
| initialize_project_context | 60 | public | None | No | Seed a project's continuity context with a style guide |
| get_context | 65 | public | ContinuityContext | No | Get (or lazily create) a project's context |
| prepare_gemini_prompt | 71 | public | Tuple[str, Optional[Image.Image]] | No | Gemini iterative-refinement prompt plus the previous image |
| prepare_openai_prompt | 98 | public | Tuple[str, Optional[str]] | No | DALL·E-style prompt plus a previous-image reference ID |
| prepare_claude_prompt | 125 | public | str | No | Style-guide-driven prompt for Claude |
| prepare_local_prompt | 149 | public | str | No | Consistent-description prompt for Ollama / LM Studio |
| update_context | 184 | public | None | No | Record the generated image, id, prompt, and scene data |
| _build_establishing_prompt | 204 | private | str | No | Detailed first-scene prompt from the style guide |
| _build_incremental_prompt | 225 | private | str | No | Change-focused prompt for follow-on scenes |
| _build_evolution_prompt | 241 | private | str | No | Prompt describing evolution from the previous scene |
| _extract_consistent_elements | 260 | private | str | No | Pull invariant descriptors out of the style guide |
| _infer_style_guide | 285 | private | Dict[str, str] | No | Derive a basic style guide from the first scene |
| prepare_aspect_ratio_reference | 296 | public | Image.Image | No | Blank canvas at the target aspect to anchor Gemini's framing |

---

### Continuity Helper
**Path**: `core/video/continuity_helper.py` - 90 lines
**Purpose**: Lightweight, non-invasive continuity hints bolted onto existing prompts — a process-wide singleton used by the ordinary generation path.
**Language**: Python

#### Class: ContinuityHelper (line 11)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 14 | constructor | None | No | Initialize per-project style-guide storage |
| enhance_prompt_for_continuity | 19 | public | str | No | Append provider-appropriate continuity hints (and aspect ratio) without breaking the base prompt |
| set_style_guide | 54 | public | None | No | Store a style guide for a project id |
| get_style_prefix | 58 | public | str | No | Build a style prefix string from the stored guide |
| clear_project | 73 | public | None | No | Drop stored data for a project |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_continuity_helper | 85 | public | ContinuityHelper | No | Lazily create and return the module-level singleton |

---

## Core Video — LLM Sync, Storyboard v2 & Generation Clients

This group covers the LLM-driven half of the video subsystem: aligning lyrics to
audio time, turning lyrics into storyboards and scene prompts, generating the
actual images/videos, and the supporting project/FFmpeg/timing infrastructure.

---

### LLM Sync Assistant (v2)
**Path**: `core/video/llm_sync_v2.py` - 1381 lines
**Purpose**: Provider-specific LLM synchronization of lyrics to audio timing, with
estimation fallbacks, fragment re-merging, and instrumental-gap detection.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| TimedLyric | 17 | @dataclass | text: str, start_time: float, end_time: float, section_type: Optional[str] |

#### Class: LLMSyncAssistant (line 25)
Uses LLMs to align lyric lines to timestamps. Constructs a `UnifiedLLMProvider`
lazily from `core/video/prompt_engine`; if that import fails or the provider is
unavailable, every entry point degrades to arithmetic estimation instead of
raising.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 28 | constructor | None | No | Store provider/model/config; try to build `UnifiedLLMProvider`, warn on ImportError |
| sync_with_llm | 51 | public | List[TimedLyric] | No | Main entry: logs all sync parameters, dispatches to the openai/gemini/anthropic implementation, falls back to `estimate_lyric_timing` on unavailability or exception |
| _sync_with_openai | 112 | private | List[TimedLyric] | No | OpenAI GPT-5 path using the "Strict Lyric Timing Contract v1.0" prompt |
| _sync_with_anthropic | 349 | private | List[TimedLyric] | No | Anthropic Claude path; OpenAI-like JSON contract tailored to Claude |
| _sync_with_gemini | 484 | private | List[TimedLyric] | No | Gemini path using section-by-section processing (Strict-Lyric-Timing-Gemini) |
| _parse_lyrics_into_sections | 538 | private | List[Tuple[str, str]] | No | Split lyrics on structural tags (`[Verse 1]`, `[Chorus]`) into (name, text) pairs |
| _sync_single_section_with_gemini | 575 | private | List[TimedLyric] | No | Time one section against a start offset / end time window |
| _merge_fragmented_lyrics | 717 | private | List[TimedLyric] | No | Reconcile karaoke-style fragmented and reordered LLM output back onto the original lyric lines |
| _lyrics_match | 793 | private | bool | No | Fuzzy compare fragment vs. original line, ignoring punctuation/case |
| _parse_timestamp | 822 | private | float | No | Convert `MM:SS.mmm` to seconds |
| estimate_timing_from_descriptions | 852 | public | List[TimedLyric] | No | LLM-estimate durations for scene descriptions when no MIDI exists; optionally fit a target duration |
| estimate_timing_with_explicit | 998 | public | List[TimedLyric] | No | Same, but preserves scenes that already carry explicit durations |
| estimate_lyric_timing | 1082 | public | List[TimedLyric] | No | Non-LLM estimator driven by total duration plus optional MIDI section markers |
| _simple_timing_distribution | 1107 | private | List[TimedLyric] | No | Even/weighted distribution when no section info is available |
| _sync_with_sections | 1153 | private | List[TimedLyric] | No | Align lyric sections to MIDI section time ranges |
| _parse_lyric_sections | 1196 | private | Dict[str, List[str]] | No | Group lyric lines under their section markers |
| _is_section_marker | 1230 | private | bool | No | Detect a `[...]` section marker line |
| _extract_section_type | 1234 | private | str | No | Normalize a marker to a section type |
| _detect_section_type | 1254 | private | Optional[str] | No | Infer section type from line content |
| _estimate_line_duration | 1260 | private | float | No | Weight a line's duration by its characteristics (length/syllables) |
| fill_instrumental_gaps | 1277 | public | List[TimedLyric] | No | Emit synthetic entries for silent/instrumental gaps so the storyboard can create scenes for them |

---

### Enhanced Storyboard Generator (v2)
**Path**: `core/video/storyboard_v2.py` - 1079 lines
**Purpose**: Lyrics-to-scene storyboard generation with provider-specific strategies
(OpenAI structured JSON vs. Gemini director's treatment), Veo batching, scene
markers, Whisper/time-tag timing, and reference-image continuity.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| StoryboardApproach | 107 | Enum | STRUCTURED_JSON, DIRECTORS_TREATMENT, HYBRID |
| SceneSpec | 115 | @dataclass | scene_id, section, start_sec, duration_sec, summary, rationale, continuity, veo_prompt, image_prompts, negatives |
| StyleGuide | 130 | @dataclass | character: str, setting: str, mood: str, cinematic_style: str |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| parse_scene_markers | 20 | public | Tuple[str, List[Dict[str, str]]] | No | Strip inline markers from lyrics — new `{scene: ...}` / `{camera: ...}` form plus the deprecated `=== NEW SCENE: ... ===` form — returning cleaned text and marker records (`line_index`, `environment`, `group_id`) |

#### Class: EnhancedStoryboardGenerator (line 138)
Holds the two large class-level prompt templates (`OPENAI_SCENE_PROMPT`,
`GEMINI_TREATMENT_PROMPT`) and drives generation through a `UnifiedLLMProvider`.
`enable_auto_link_references` defaults to True so each scene inherits the previous
scene's last frame as a reference image.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 223 | constructor | None | No | Bind (or create) the `UnifiedLLMProvider`; enable auto reference linking |
| _batch_scenes_for_veo | 228 | private | List[Dict[str, Any]] | No | Pack consecutive scenes into groups that fit Veo 3.1's max clip duration (default 8.0s) |
| _generate_veo_batches | 285 | private | Optional[List[Dict]] | No | Ask the LLM for frame-accurate batched video prompts across those groups |
| get_approach | 409 | public | StoryboardApproach | No | Pick the strategy enum for a given provider |
| generate_storyboard | 421 | public | Tuple[Optional[StyleGuide], List[Scene], Optional[List[Dict]]] | No | Top-level entry: chooses approach, generates scenes, applies markers/timing/reference linking, returns style guide + scenes + optional Veo batches |
| _generate_structured_json | 511 | private | Tuple[Optional[StyleGuide], List[Scene]] | No | OpenAI structured-JSON schema path |
| _generate_directors_treatment | 597 | private | Tuple[Optional[StyleGuide], List[Scene]] | No | Gemini director's-treatment path producing a style guide plus continuous Veo prompts |
| _generate_hybrid | 682 | private | Tuple[Optional[StyleGuide], List[Scene]] | No | Simplified hybrid prompt for local/smaller models |
| _parse_json_response | 752 | private | Optional[Dict] | No | Extract JSON from an LLM reply (handles Markdown fences) |
| _convert_json_to_scenes | 782 | private | List[Scene] | No | Map parsed JSON scene dicts onto `Scene` objects |
| _fallback_scene_split | 813 | private | List[Scene] | No | Deterministic split when the LLM fails entirely |
| _apply_scene_markers | 848 | private | List[Scene] | No | Attach `environment` / `scene_group_id` from parsed markers by matching line content |
| _apply_whisper_timing | 894 | private | List[Scene] | No | Set precise scene start/end from Whisper word timestamps |
| _apply_time_tags | 977 | private | List[Scene] | No | Set scene times from `{time: MM:SS}` tags when no Whisper data exists |
| apply_reference_image_auto_linking | 1041 | public | List[Scene] | No | Chain each scene's `last_frame` into the next scene's first reference image for visual continuity |

---

### Video Prompt Generator
**Path**: `core/video/video_prompt_generator.py` - 637 lines
**Purpose**: LLM generation of Veo motion/camera prompts (with explicit timing
markers) describing how a scene evolves over its clip duration.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| VideoPromptContext | 14 | @dataclass | start_prompt, duration (6.0), style ('cinematic'), enable_camera_movements, enable_prompt_flow, previous_video_prompt, lyric_timings, tempo_bpm |

#### Class: VideoPromptGenerator (line 26)
Carries large class-level system prompts (e.g. `SYSTEM_PROMPT_WITH_CAMERA`,
line 26–151 region) that instruct the model to emit `X-Ys:` timing markers for
Veo's fixed 8-second clips, with and without camera movement.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 152 | constructor | None | No | Store LLM provider/model and optional config for API-key resolution |
| is_available | 166 | public | bool | No | True when both provider and model are configured |
| generate_video_prompt | 170 | public | Optional[str] | No | Build the system/user prompt from context (duration, tempo, lyric timings, previous prompt), call the LLM, parse and validate the motion prompt |
| _fallback_prompt | 404 | private | str | No | Derive a simple motion prompt from the start prompt when the LLM fails |
| batch_generate_video_prompts | 419 | public | list[Optional[str]] | No | True batching — all contexts in one API call, results split back per scene |

---

### Workflow Wizard
**Path**: `core/video/workflow_wizard.py` - 594 lines
**Purpose**: Resumable step tracker for the video generation pipeline — infers
which stage a project is at and what the user should do next.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| WorkflowStep | 18 | Enum | INPUT_TEXT, MIDI_FILE, AUDIO_FILE, GENERATE_STORYBOARD, ENHANCE_PROMPTS, GENERATE_MEDIA, REVIEW_APPROVE, EXPORT_VIDEO |
| StepStatus | 30 | Enum | NOT_STARTED, IN_PROGRESS, COMPLETED, OPTIONAL_SKIPPED |
| WorkflowStepInfo | 39 | @dataclass | step, status, title, description, is_optional, is_blocking, help_text, estimated_time |

#### WorkflowStepInfo Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_dict | 50 | public | Dict[str, Any] | No | Serialize the step info for the GUI |

#### Class: WorkflowWizard (line 64)
Holds `STEP_DEFINITIONS`, a class-level map of `WorkflowStep` → `WorkflowStepInfo`
with user-facing titles, descriptions, optionality, and time estimates.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 234 | constructor | None | No | Bind a `VideoProject` and analyze its state |
| _analyze_project_state | 247 | private | None | No | Inspect the project (text, MIDI, audio, scenes, media, approvals, exports) to mark each step's status — this is what makes the wizard resumable |
| get_current_step | 325 | public | WorkflowStep | No | First incomplete required step, or the last step when all are done |
| get_next_action | 346 | public | Dict[str, Any] | No | Suggested action bundle: step, description, button text, whether it's blocked, and available choices |
| _get_button_text | 377 | private | str | No | Button label for a step |
| _can_proceed | 391 | private | bool | No | Whether prerequisites for a step are satisfied |
| _get_blocking_reason | 406 | private | Optional[str] | No | Human-readable reason the user is blocked |
| _calculate_progress | 422 | private | int | No | Overall completion percentage |
| _get_step_choices | 441 | private | Optional[Dict[str, Any]] | No | Branching options at a step (e.g. image vs. video path) with explanations |
| get_all_steps | 546 | public | List[WorkflowStepInfo] | No | All steps with current status, for a progress panel |
| mark_step_complete | 550 | public | None | No | Force a step to COMPLETED |
| mark_step_skipped | 555 | public | None | No | Mark an optional step OPTIONAL_SKIPPED |
| get_summary | 563 | public | str | No | Multi-line human-readable progress summary |

---

### Gemini Omni Video Client
**Path**: `core/video/omni_client.py` - 514 lines
**Purpose**: Client for Google Gemini Omni video generation/editing through the
`google.genai` **Interactions API**, including Files-API uploads, polling, and
inline/URI delivery.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| GENAI_AVAILABLE | 38 | constant | True when `import google.genai` succeeds |
| GENAI_AVAILABLE | 40 | constant | False branch set in the ImportError handler (`genai = None`) |
| _TERMINAL_STATUSES | 45 | constant | Interaction statuses that end polling: completed/failed/cancelled/incomplete/budget_exceeded |
| _FAILED_STATUSES | 46 | constant | Subset of terminal statuses treated as failure |
| _IMAGE_MIME_BY_SUFFIX | 49 | constant | Reference-image MIME lookup by file suffix (png/jpg/jpeg/webp/gif) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| _file_state | 58 | private | Optional[str] | No | Normalize a Files-API object's state to a string (`PROCESSING`/`ACTIVE`/`FAILED`) |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| OmniModel | 64 | Enum | OMNI_FLASH = "gemini-omni-flash-preview" (offline fallback only) |
| OmniGenerationConfig | 81 | @dataclass | prompt, model, aspect_ratio, reference_image, reference_images, input_video, previous_interaction_id, delivery, task |
| OmniGenerationResult | 195 | @dataclass | success, video_path, interaction_id, error, generation_time, has_synthid, metadata |

#### OmniModel Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @classmethod default_id | 75 | class | str | No | Resolve the live Omni model ID via `resolve_model("google", "omni", ...)` — registry-first, never hard-coded |

#### OmniGenerationConfig Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __post_init__ | 95 | constructor | None | No | Default the model from the registry, fold the legacy single `reference_image` into `reference_images`, infer the task, and self-validate |
| _infer_task | 139 | private | str | No | Derive the `video_config` task from the input shape (text/image/reference/edit) |
| to_interaction_kwargs | 149 | public | Dict[str, Any] | No | Build `client.interactions.create(**kwargs)` — inputs plus `response_format={"type": "video", "aspect_ratio": ...}` |

#### Class: OmniClient (line 207)
Wraps `genai.Client`, raising ImportError up front when `google-genai>=2.3.0` is
missing. `MODEL_CONSTRAINTS` documents supported aspect ratios, tasks, the
3-reference-image cap, delivery modes, duration range, fps, resolution, audio
support, and conversational-edit support.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 222 | constructor | None | No | Store API key, polling interval (10s) and timeout (600s); construct the genai client |
| validate_config | 243 | public | Tuple[bool, Optional[str]] | No | Check a config against `MODEL_CONSTRAINTS` |
| generate_video_async | 259 | public | OmniGenerationResult | Yes | Create the interaction (uploading any input video first), poll to terminal, extract and write the MP4 to `output_path` |
| generate_video | 368 | public | OmniGenerationResult | No | Synchronous wrapper around `generate_video_async` |
| _await_terminal | 378 | private | Any | Yes | Poll `interactions.get` until a terminal status or timeout |
| _upload_video | 408 | private | str | Yes | Upload a video via the Files API, wait for ACTIVE, return the file URI |
| @classmethod _extract_video | 431 | class | Tuple[Optional[bytes], Optional[str], Optional[str]] | No | Pull (bytes, uri, mime) from a completed interaction — `output_video` first, with defensive fallbacks |
| @staticmethod _video_content_parts | 462 | static | Tuple[Optional[bytes], Optional[str], Optional[str]] | No | Decode a VideoContent-like object or dict to (bytes, uri, mime) |
| _download_uri | 478 | private | Optional[bytes] | Yes | Fetch bytes for a Files-API URI, polling until ACTIVE |
| @staticmethod _error_text | 508 | static | str | No | Best-effort error message extraction from a failed interaction |

---

### Scene Image Generator
**Path**: `core/video/image_generator.py` - 474 lines
**Purpose**: Batch image generation for storyboard scenes across ImageAI's providers,
with a thread pool, disk cache, cost estimation, and event-store logging.
**Language**: Python

#### Class: ImageGenerationResult (line 24)
Plain result object; `__init__` (line 27) sets `scene_id`, `success`, `images`,
`paths`, `error`, `cost`, `duration`, and `metadata`.

#### Class: ImageGenerator (line 38)
Owns a `ThreadPoolExecutor` sized by `config['concurrent_images']` (default 3) and
a cache directory under `~/.imageai/cache/video`.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 41 | constructor | None | No | Set config, cache dir, optional `EventStore`, and the concurrency executor |
| generate_batch | 63 | public | List[ImageGenerationResult] | No | Generate N variants per scene across the thread pool for a given provider/model |
| @staticmethod _clean_prompt_for_generation | 115 | static | str | No | Strip scene numbering and lyric prefixes (`**1.** *lyrics* — description`) down to the description |
| _generate_scene_images | 151 | private | ImageGenerationResult | No | Single-scene generation: cache lookup, provider call, save, cost/event recording |
| regenerate_scene | 266 | public | ImageGenerationResult | No | Re-run one scene, optionally preserving already-approved images |
| _get_api_key | 315 | private | Optional[str] | No | Resolve the provider API key from config |
| _prepare_generation_params | 331 | private | Dict[str, Any] | No | Translate scene + user kwargs into provider-specific parameters |
| _add_prompt_variation | 382 | private | str | No | Nudge the prompt per variant index for diversity |
| _get_cache_key | 396 | private | str | No | Hash prompt + provider + model + params into a cache key |
| _get_cached_images | 408 | private | List[bytes] | No | Load up to `count` cached images for a key |
| _cache_images | 424 | private | None | No | Write generated images into the cache |
| _save_images | 433 | private | List[Path] | No | Persist images into the project directory for a scene |
| _estimate_cost | 448 | private | float | No | Estimate per-provider/model cost for a count of images |
| cleanup | 472 | public | None | No | Shut down the executor |

---

### Style Analyzer
**Path**: `core/video/style_analyzer.py` - 406 lines
**Purpose**: Vision-LLM analysis of a previous clip's end frame to extract style or a
transition description, giving video scenes visual continuity.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| ContinuityMode | 18 | Enum | NONE, STYLE_ONLY, TRANSITION |

#### Class: StyleAnalyzer (line 25)
Dispatches image analysis to Google, OpenAI, or Anthropic vision APIs, with the
default model resolved from the model registry.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 28 | constructor | None | No | Store API key, provider, and model (defaulting via `_get_default_model`) |
| _get_default_model | 41 | private | str | No | Registry-resolved default vision model for the provider |
| analyze_for_style | 54 | public | Optional[str] | No | Extract lighting, palette, composition, camera angle, artistic style, and mood from an image |
| analyze_for_transition | 101 | public | Optional[str] | No | Extract style *and* content to build a continuation prompt toward the next scene's text |
| _analyze_image | 145 | private | Optional[str] | No | Read/encode the image and route to the provider-specific analyzer |
| _analyze_with_google | 178 | private | str | No | Gemini vision call |
| _analyze_with_openai | 219 | private | str | No | OpenAI vision call |
| _analyze_with_anthropic | 282 | private | str | No | Anthropic Claude vision call |
| _get_mime_type | 354 | private | str | No | MIME type from the image file extension |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_previous_scene_info | 380 | public | Tuple[Optional[Path], Optional[str]] | No | Return the previous scene's end-frame path and source text for continuity |

---

### Video Project Manager
**Path**: `core/video/project_manager.py` - 394 lines
**Purpose**: Lifecycle and persistence for video projects — create, load, save, list,
duplicate, export/import archives, and cleanup.
**Language**: Python

#### Class: ProjectManager (line 17)

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 20 | constructor | None | No | Set the projects base directory (defaults to the platform user config dir) |
| create_project | 46 | public | VideoProject | No | Create a new project directory and `VideoProject` |
| load_project | 88 | public | VideoProject | No | Load from a project file or directory |
| save_project | 115 | public | Path | No | Persist a project, returning the saved file path |
| list_projects | 146 | public | List[Dict[str, Any]] | No | Enumerate available projects with metadata |
| delete_project | 183 | public | bool | No | Remove a project and all its files |
| duplicate_project | 205 | public | VideoProject | No | Deep-copy a project under a new name |
| export_project | 266 | public | Path | No | Write a portable archive of the project |
| import_project | 301 | public | VideoProject | No | Restore a project from an archive |
| get_project_size | 347 | public | int | No | Total project directory size in bytes |
| cleanup_old_projects | 367 | public | int | No | Delete projects older than `days`; returns the count removed |

---

### FFmpeg Utilities
**Path**: `core/video/ffmpeg_utils.py` - 345 lines
**Purpose**: Single point of access for FFmpeg — detection (system → imageio-ffmpeg),
optional auto-install, verification, and status caching in the main config.
**Language**: Python

#### Class: FFmpegManager (line 18)
Singleton (class-level `_instance`, `_ffmpeg_path`, `_ffprobe_path`,
`_is_available`, `_source`) so detection runs once per process and its result is
persisted to config.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __new__ | 35 | constructor | FFmpegManager | No | Singleton allocation |
| __init__ | 41 | constructor | None | No | Runs once: load cached status, else detect |
| _load_from_config | 54 | private | None | No | Read cached FFmpeg status from the main config |
| _save_to_config | 77 | private | None | No | Persist detected status back to config |
| _verify_ffmpeg | 94 | private | bool | No | Confirm the binary at a path actually runs |
| _detect_ffmpeg | 107 | private | None | No | Try system FFmpeg, then imageio-ffmpeg |
| _try_system_ffmpeg | 126 | private | bool | No | Locate and verify FFmpeg/ffprobe on PATH |
| _try_imageio_ffmpeg | 160 | private | bool | No | Fall back to the bundled `imageio-ffmpeg` binary |
| install_ffmpeg | 193 | public | Tuple[bool, str] | No | pip-install `imageio-ffmpeg` and re-detect |
| @property is_available | 242 | property | bool | No | Whether FFmpeg was found |
| @property ffmpeg_path | 247 | property | Optional[str] | No | Path to the FFmpeg executable |
| @property ffprobe_path | 252 | property | Optional[str] | No | Path to ffprobe (may be None with imageio) |
| @property source | 257 | property | Optional[str] | No | `'system'`, `'imageio'`, or None |
| get_status | 261 | public | dict | No | Full status dictionary |
| ensure_available | 270 | public | Tuple[bool, str] | No | Guarantee availability, optionally auto-installing |
| refresh | 289 | public | None | No | Clear the cache and re-detect |

#### Functions (module-level convenience wrappers over the singleton)
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_ffmpeg_manager | 302 | public | FFmpegManager | No | Return the singleton |
| get_ffmpeg_path | 310 | public | Optional[str] | No | FFmpeg executable path or None |
| is_ffmpeg_available | 315 | public | bool | No | Availability check |
| ensure_ffmpeg | 320 | public | Tuple[bool, str] | No | Ensure availability with optional auto-install |
| install_ffmpeg | 333 | public | Tuple[bool, str] | No | Install via imageio-ffmpeg |
| get_ffmpeg_status | 343 | public | dict | No | Full status dictionary |

---

### Timing Models
**Path**: `core/video/timing_models.py` - 205 lines
**Purpose**: Serializable data models for Whisper transcription, word-level timing,
lyric alignment, and per-scene timing.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| WordTiming | 8 | @dataclass | text, start_time, end_time, confidence (1.0) |
| TranscriptionResult | 42 | @dataclass | full_text, words: List[WordTiming], language ('en'), duration, model_used ('tiny') |
| AlignmentResult | 140 | @dataclass | matched_words, unmatched_provided, unmatched_extracted, similarity_score, aligned_text |
| SceneTiming | 166 | @dataclass | scene_index, start_time, end_time, text, words, lip_sync_enabled, lip_sync_character |

#### WordTiming Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property duration | 17 | property | float | No | `end_time - start_time` |
| to_dict | 21 | public | dict | No | JSON-serializable form |
| @classmethod from_dict | 31 | class | 'WordTiming' | No | Rehydrate from a dict |

#### TranscriptionResult Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property word_count | 52 | property | int | No | Number of transcribed words |
| get_words_in_range | 56 | public | List[WordTiming] | No | Words falling inside a time window |
| get_text_in_range | 63 | public | str | No | Transcribed text for a time window |
| to_dict | 68 | public | dict | No | JSON-serializable form |
| @classmethod from_dict | 79 | class | 'TranscriptionResult' | No | Rehydrate from a dict |
| format_as_lyrics | 89 | public | str | No | Insert line/stanza breaks based on inter-word pause thresholds to produce lyric-shaped text |

#### AlignmentResult Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property is_good_match | 150 | property | bool | No | Whether the similarity score clears the usable threshold |
| to_dict | 154 | public | dict | No | JSON-serializable form |

#### SceneTiming Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property duration | 178 | property | float | No | Scene length in seconds |
| to_dict | 182 | public | dict | No | JSON-serializable form |
| @classmethod from_dict | 195 | class | 'SceneTiming' | No | Rehydrate from a dict |

---

### End Prompt Generator
**Path**: `core/video/end_prompt_generator.py` - 173 lines
**Purpose**: LLM generation of end-frame descriptions so Veo 3.1 can animate a smooth
transition into the next scene.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| EndPromptContext | 16 | @dataclass | start_prompt, next_start_prompt (None), duration (6.0), style ('cinematic') |

#### Class: EndPromptGenerator (line 24)
Holds a class-level `SYSTEM_PROMPT` instructing the model to describe the final
frame's visual state in 1–2 sentences (no camera movement — Veo handles the
animation).

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 36 | constructor | None | No | Accept or construct a `UnifiedLLMProvider` |
| is_available | 46 | public | bool | No | Whether the LLM provider is usable |
| generate_end_prompt | 52 | public | Optional[str] | No | Produce the end-frame description for one context |
| _fallback_prompt | 132 | private | str | No | Simple derived prompt when the LLM fails |
| batch_generate_end_prompts | 147 | public | list[Optional[str]] | No | Generate end prompts for multiple contexts in one pass |

---

## Core Video — Storyboard, Veo Client, Rendering & Audio

The `core/video/` package implements ImageAI's lyric-synced video pipeline: text/lyrics are parsed into a storyboard, scenes are timed (optionally against MIDI or Whisper timestamps), imagery or Veo clips are generated, and FFmpeg assembles the final video with optional karaoke overlays and audio.

```
lyrics/text ──► tag_parser ──► storyboard ──► scene_suggester (LLM)
                                   │
                     midi_processor / audio_segmenter
                                   │
                   veo_client (clips)  or  images (slideshow)
                                   │
                    ffmpeg_renderer ──► karaoke_renderer ──► .mp4
```

---

### Video Package Init

**Path**: `core/video/__init__.py` - 45 lines
**Purpose**: Package entry point. Re-exports the FFmpeg utility surface (`get_ffmpeg_manager`, `get_ffmpeg_path`, `is_ffmpeg_available`, `ensure_ffmpeg`, `install_ffmpeg`, `get_ffmpeg_status`, `FFmpegManager`) and lazily imports the Gemini Omni client, degrading gracefully when `google-genai >= 2.3.0` (the Interactions API) is unavailable.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| OMNI_AVAILABLE | 22 | constant | Set `True` when `omni_client` (OmniClient / OmniModel / OmniGenerationConfig / OmniGenerationResult) imports successfully |
| OMNI_AVAILABLE | 24 | constant | Fallback `False` in the `ImportError` branch; the Omni names are set to `None` so callers can feature-detect |

---

### Video Configuration

**Path**: `core/video/config.py` - 345 lines
**Purpose**: Persistent configuration for all video features — projects directory, default provider (slideshow / veo / omni), FFmpeg path, timing presets, per-model Veo and Omni capability tables, LLM provider settings, and export codec settings. Stored as `video_config.json` in the platform user-config directory.
**Language**: Python

#### Class: `VideoConfig` (line 13)
Holds `DEFAULT_CONFIG` (line 16) — the full defaults tree including `timing_presets`, `veo_settings.models`, `omni_settings.models`, and `export_settings` — plus `_LEGACY_VEO_MIGRATION` (line 85), the map that rewrites Veo model IDs Google discontinued on 2026-06-30.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 91 | constructor | None | Resolve the config path per-platform (Windows `%APPDATA%`, macOS Application Support, else `~/.config/ImageAI`), deep-copy defaults, set the dynamic projects dir, then `load()` |
| `_migrate_legacy_models` | 125 | private | None | Idempotently rewrite legacy `veo-3.0-*` / `veo-2.0-*` IDs to their GA replacements; called from `load()` |
| `load` | 162 | public | bool | Read the JSON file and deep-merge over defaults, then migrate legacy models; `False` when no file exists or load fails |
| `save` | 189 | public | bool | Create the parent directory and write the config as indented JSON |
| `get` | 209 | public | Any | Dot-notation lookup (`"veo_settings.timeout"`) with default fallback |
| `set` | 231 | public | None | Dot-notation write, creating intermediate dicts as needed |
| `_deep_merge` | 249 | private | None | Recursive in-place merge of an override dict into a base dict |
| `validate_ffmpeg` | 263 | public | bool | Delegate to `ffmpeg_utils.ensure_ffmpeg()`; on success record the detected path and source in config and save |
| `get_veo_model_config` | 290 | public | Dict[str, Any] | Capability dict for a Veo model (duration, fps, resolutions, aspect ratios, audio) |
| `get_omni_model_config` | 302 | public | Dict[str, Any] | Capability dict for a Gemini Omni model |
| `is_llm_provider_enabled` | 314 | public | bool | Whether an LLM provider (openai / anthropic / gemini …) is enabled |
| `get_llm_models` | 326 | public | list | Model list for an LLM provider |
| `get_projects_dir` | 338 | public | Path | Path to the video projects directory |

---

### Tag Parser

**Path**: `core/video/tag_parser.py` - 502 lines
**Purpose**: Parses curly-brace storyboard markers (`{scene: bedroom}`, `{camera: slow pan}`, `{lipsync}`, `{time: 1:30}`) out of lyric text, with backward compatibility for the legacy `=== NEW SCENE: … ===` format. Also provides time-value parsing/formatting and Whisper timestamp injection.
**Language**: Python

#### Class: `TagType` (line 17) — `Enum`
Tag vocabulary: `SCENE`, `CAMERA`, `MOOD`, `FOCUS`, `TRANSITION`, `STYLE`, `LIPSYNC`, `TEMPO`, `TIME`, `UNKNOWN`.

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `Tag` | 32 | @dataclass | tag_type: TagType, value: Optional[str], line_number: int, raw_text: str |
| `ParseResult` | 54 | @dataclass | clean_text: str, tags: List[Tag], tags_by_line: Dict[int, List[Tag]], legacy_markers_found: bool |

##### `Tag` Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__str__` | 39 | magic | str | Re-render the tag as `{type: value}` (or `{type}` for boolean tags) |
| `to_dict` | 44 | public | Dict[str, Any] | Serializable form (type, value, line_number, raw_text) |

##### `ParseResult` Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `has_tags` | 61 | public | bool | Whether any tags were found |
| `get_tags_of_type` | 64 | public | List[Tag] | Filter tags by `TagType` |
| `get_scene_tags` | 67 | public | List[Tag] | Convenience filter for `TagType.SCENE` |

#### Class: `TagParser` (line 71)
Regex-driven parser. Class constants: `TAG_PATTERN` (line 90) for `{type: value}`, `LEGACY_SCENE_PATTERN` (line 96) for `=== NEW SCENE: … ===`, and `TAG_TYPE_MAP` (line 102) which also maps aliases (`lip-sync`, `timestamp`, `t`).

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `parse` | 117 | public | ParseResult | Strip and collect all tags line by line, optionally converting legacy scene markers first |
| `has_tags` | 204 | public | bool | Quick test for curly-brace or legacy markers |
| `count_tags` | 212 | public | Dict[str, int] | Tally of tags by type name |
| `insert_tag` | 221 | public | str | Insert a tag at a given line, before or after existing content |
| `remove_all_tags` | 257 | public | str | Strip both curly-brace and legacy markers, returning clean lyrics |
| `convert_legacy_to_new` | 276 | public | str | Rewrite `=== NEW SCENE: x ===` lines as `{scene: x}` |
| `format_tags_for_display` | 296 | public | str | Human-readable tag summary for the GUI |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| `parse_time_value` | 311 | public | Optional[float] | Parse `SS`, `SS.s`, `MM:SS`, `MM:SS.s`, or `HH:MM:SS.s` into seconds |
| `format_time_value` | 353 | public | str | Inverse of the above, with optional decimal precision |
| `extract_scene_metadata` | 381 | public | Dict[str, Any] | Fold a list of tags into a metadata dict used when building `Scene` objects |
| `inject_whisper_timestamps` | 415 | public | str | Insert `{time: …}` tags into text at intervals derived from Whisper word timestamps, optionally at line starts |
| `extract_time_tags` | 485 | public | List[Tuple[int, float]] | Return `(line_number, seconds)` pairs for every time tag |

---

### MIDI Processor

**Path**: `core/video/midi_processor.py` - 589 lines
**Purpose**: Extracts tempo, beat, measure, lyric, and section timing from MIDI files (via `pretty_midi` / `mido`) and uses it to align storyboard scenes to musical boundaries, including snapping durations to Veo's fixed clip lengths.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| MIDI_AVAILABLE | 15 | constant | `True` when `pretty_midi` / `mido` import successfully |
| MIDI_AVAILABLE | 17 | constant | `False` fallback in the `ImportError` branch; guarded at line 66 and line 512 |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `MidiTimingData` | 27 | @dataclass | file_path, tempo_bpm, time_signature, duration_sec, tempo_changes, time_signatures, beats, measures, lyrics, sections |

##### `MidiTimingData` Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `to_dict` | 40 | public | Dict[str, Any] | JSON-serializable timing payload |
| `from_dict` | 56 | class | 'MidiTimingData' | `@classmethod` reconstructor from serialized form |

#### Class: `MidiProcessor` (line 62)
Loads a MIDI file once and exposes timing extraction plus scene/lyric alignment.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 65 | constructor | None | Raise/flag when MIDI libraries are missing (`MIDI_AVAILABLE` guard) |
| `extract_timing` | 73 | public | MidiTimingData | Full timing pass: tempo, time signatures, beats, measures, lyrics, and detected sections |
| `_extract_tempo_changes` | 133 | private | List[Tuple[float, float]] | `(time, bpm)` tempo change list |
| `_extract_time_signatures` | 148 | private | List[Tuple[float, int, int]] | `(time, numerator, denominator)` list |
| `_extract_lyrics_from_midi` | 163 | private | List[Tuple[float, str]] | Read lyric meta-events with `mido` |
| `_detect_musical_sections` | 205 | private | Dict[str, List[Tuple[float, float]]] | Heuristic verse/chorus/bridge detection from measure patterns |
| `align_scenes_to_beats` | 268 | public | List[Dict[str, Any]] | Snap scene boundaries to beats/measures/sections with a configurable snap strength |
| `extract_lyrics_with_timing` | 342 | public | List[Dict[str, Any]] | Word/line-level lyric timing, optionally aligning supplied lyrics text to the MIDI |
| `_align_lyrics_to_timing` | 382 | private | List[Dict[str, Any]] | Simplified (non-phoneme) alignment of lyric lines onto extracted timing |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| `snap_duration_to_veo` | 450 | public | int | Snap a float duration to the nearest Veo-allowed clip length (4 / 6 / 8 s) |
| `align_scene_durations_for_veo` | 480 | public | List[Dict[str, Any]] | Combine MIDI-driven alignment with Veo duration constraints, optionally targeting a total duration |
| `estimate_veo_scene_count` | 561 | public | int | Estimate how many Veo clips are needed to cover a target total duration |

---

### MIDI Utilities

**Path**: `core/video/midi_utils.py` - 34 lines
**Purpose**: Runtime availability check for the optional MIDI stack, keeping `pretty_midi` / `mido` out of import-time dependencies.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| `check_midi_available` | 9 | public | tuple | `(available, error_message)` — imports `pretty_midi` and `mido`, logging warnings/errors instead of raising |
| `get_midi_processor` | 25 | public | MidiProcessor | Lazily import and construct `MidiProcessor`, raising `ImportError` with a pip-install hint when unavailable |

---

### Storyboard Generation

**Path**: `core/video/storyboard.py` - 1210 lines
**Purpose**: The heart of lyrics-to-storyboard conversion. Detects the input format (timestamped / structured / plain), parses lines, allocates per-scene durations from timestamps, a target total, or a pacing preset, then batches, splits, and merges scenes into clip-sized units suitable for video generation.
**Language**: Python

#### Table of Contents
| Section | Line |
|---------|------|
| `InputFormat` enum | 15 |
| `ParsedLine` dataclass | 23 |
| `LyricParser` | 32 |
| `TimingEngine` | 272 |
| `StoryboardGenerator` | 475 |

#### Class: `InputFormat` (line 15) — `Enum`
`TIMESTAMPED`, `STRUCTURED`, `PLAIN`.

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `ParsedLine` | 23 | @dataclass | text, timestamp, section, line_number, duration |

#### Class: `LyricParser` (line 32)
Format detection and parsing. Class constants: `TIMESTAMP_PATTERN` (line 36) for `[mm:ss(.mmm)]`, `SECTION_PATTERN` (line 37) for `# Verse` headings, `DURATION_PATTERN` (line 38) for `[5s]` markers in prefix or suffix position.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 40 | constructor | None | Initialize parser state |
| `extract_explicit_duration` | 43 | public | Tuple[str, Optional[float]] | Pull an explicit `[5s]` / `[5.5s]` duration off a line (prefix or suffix) and return the cleaned text |
| `detect_format` | 79 | public | InputFormat | Auto-detect timestamped vs structured vs plain input |
| `parse_timestamped` | 109 | public | List[ParsedLine] | Parse `[mm:ss]`-prefixed lyric lines |
| `parse_structured` | 158 | public | List[ParsedLine] | Parse `# Verse` / `# Chorus` section headings with their lines |
| `parse_plain` | 196 | public | List[ParsedLine] | Parse unstructured text, one scene per non-empty line |
| `parse` | 243 | public | List[ParsedLine] | Dispatch to the right parser using `format_hint` or auto-detection |

#### Class: `TimingEngine` (line 272)
Turns parsed lines into per-scene durations.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 275 | constructor | None | Read timing presets and defaults from `VideoConfig` |
| `calculate_durations_from_timestamps` | 298 | public | List[float] | Derive durations from consecutive timestamps |
| `calculate_durations_with_target` | 330 | public | List[float] | Distribute a target total duration across lines, honoring per-line weights |
| `calculate_durations_with_preset` | 375 | public | List[float] | Apply a `fast` / `medium` / `slow` pacing preset |
| `_parse_duration_string` | 410 | private | float | Convert a duration string to seconds |
| `calculate_line_weights` | 436 | public | List[float] | Weight lines by content (length/syllable proxy) so longer lines get more screen time |

#### Class: `StoryboardGenerator` (line 475)
Builds the final `Scene` list, with substantial special handling for `[Instrumental]` + vocal pairs and for clip-length limits.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 478 | constructor | None | Wire in a `LyricParser`, `TimingEngine`, and the target scene duration |
| `_split_instrumental_vocal_pair` | 494 | private | List[Scene] | Split an instrumental+vocal pair that exceeds `max_duration` into multiple clip-sized scenes while preserving lyric attribution |
| `_preprocess_instrumental_vocal_pairs` | 648 | private | List[Scene] | First pass: keep small instrumental/vocal pairs as two scenes, split large ones, pass everything else through |
| `_batch_scenes_for_optimal_duration` | 739 | private | List[Scene] | Combine short lyric lines into scenes near the target duration, respecting section boundaries |
| `_merge_scenes` | 868 | private | Scene | Merge several scenes into one, combining text, duration, and metadata |
| `generate_scenes` | 956 | public | List[Scene] | Main entry point: parse text, allocate timing, optionally apply MIDI sync mode and snap strength, then batch/split into final scenes |
| `sync_scenes_to_midi` | 1078 | public | List[Scene] | Re-time an existing scene list against `MidiTimingData` |
| `split_long_scenes` | 1150 | public | List[Scene] | Split scenes exceeding the max clip duration (instrumental scenes are deliberately excluded — they are handled during batching) |

---

### Scene Suggester (LLM)

**Path**: `core/video/scene_suggester.py` - 396 lines
**Purpose**: Uses an LLM to read lyrics and inject storyboard tags — scene breaks, camera movements, mood, focus — without altering the lyrics themselves. Includes a verification step that confirms the original text was preserved.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `SuggestionResult` | 21 | @dataclass | tagged_text, tags_added, scenes_detected, original_preserved, warnings |

#### Class: `SceneSuggester` (line 30)
Holds `SCENE_ANALYSIS_PROMPT` (line 37), the music-video-director system prompt sent to the LLM.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 74 | constructor | None | Store `VideoConfig` and prepare the tag parser |
| `suggest_scenes` | 85 | public | SuggestionResult | Full flow: build the prompt (with style / tempo / duration context), call the LLM, clean and validate the response, report tags added |
| `_build_tempo_context` | 175 | private | str | Compose the BPM/duration hint appended to the prompt |
| `_call_llm` | 206 | private | Optional[str] | Provider/model dispatch and response text extraction, streaming progress to a `console_callback` |
| `_process_llm_response` | 261 | private | SuggestionResult | Clean, verify, and tally the tagged text returned by the model |
| `_clean_response` | 310 | private | str | Strip Markdown fences and other LLM formatting artifacts |
| `_verify_lyrics_preserved` | 324 | private | bool | Compare non-tag content against the original to catch a model that rewrote the lyrics (uses a nested `normalize` helper at line 331) |
| `has_existing_tags` | 356 | public | bool | Whether the text already carries scene tags |
| `count_existing_tags` | 360 | public | Dict[str, int] | Tally existing tags by type |
| `remove_tags` | 364 | public | str | Strip all tags from the text |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| `suggest_scenes_for_lyrics` | 370 | public | SuggestionResult | Convenience wrapper that constructs a `SceneSuggester` and forwards provider/model/kwargs |

---

### Veo Client

**Path**: `core/video/veo_client.py` - 1162 lines
**Purpose**: Google Veo video-generation client. Supports API-key and Google Cloud ADC authentication, config validation against per-model constraints, async generation with long-poll completion, video extension for multi-clip continuity, batch generation, clip concatenation, and cost estimation.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| GENAI_AVAILABLE | 26 | constant | `True` when the `google.genai` SDK imports |
| GENAI_AVAILABLE | 28 | constant | `False` fallback in the `ImportError` branch |
| GCLOUD_AVAILABLE | 35 | constant | `True` when Google Cloud auth libraries import |
| GCLOUD_AVAILABLE | 37 | constant | `False` fallback in the `ImportError` branch |

#### Class: `VeoModel` (line 45) — `Enum`
Production models: `VEO_3_1_GENERATE` (`veo-3.1-generate-001`, 1080p, 8 s clips, reference images, frame interpolation) and `VEO_3_1_FAST` (`veo-3.1-fast-generate-001`, 720p, variable 4-8 s).

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `VeoGenerationConfig` | 66 | @dataclass | model, prompt, aspect_ratio, resolution, duration, fps, include_audio, person_generation, seed, image, last_frame, reference_images |
| `VeoGenerationResult` | 138 | @dataclass | success, video_url, video_path, operation_id, error, metadata, generation_time, has_synthid |

##### Dataclass Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `VeoGenerationConfig.__post_init__` | 81 | magic | None | Validate model/duration/resolution/aspect combinations at construction |
| `VeoGenerationConfig.to_dict` | 112 | public | Dict[str, Any] | API payload (image inputs excluded — they are attached separately) |
| `VeoGenerationResult.__post_init__` | 149 | magic | None | Normalize default metadata |

#### Class: `VeoClient` (line 154)
Holds `MODEL_CONSTRAINTS` (line 158) — the per-model max/fixed durations, resolutions, and aspect-ratio allowances used by `validate_config`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 183 | constructor | None | No | Build the genai client from an API key or switch to gcloud ADC based on `auth_mode` / `project_id` / `region` |
| `_init_gcloud_client` | 213 | private | None | No | Initialize the Vertex-backed client via Application Default Credentials |
| `_detect_region` | 271 | private | str | No | Infer the caller's region (drives person-generation policy) |
| `_check_person_generation` | 280 | private | bool | No | Whether person generation is permitted in the detected region |
| `validate_config` | 289 | public | Tuple[bool, Optional[str]] | No | Check a `VeoGenerationConfig` against `MODEL_CONSTRAINTS`, returning a human-readable reason on failure |
| `generate_video_async` | 325 | public | VeoGenerationResult | Yes | Main generation path — submit the request (with optional seed image, last frame, and reference images), poll, download, and record metadata |
| `generate_video` | 611 | public | VeoGenerationResult | No | Blocking wrapper around `generate_video_async` |
| `extend_video_async` | 629 | public | VeoGenerationResult | Yes | Continue a previous clip using its tail as seed; supports up to 20 extensions (~148 s), noting extended segments render at 720p |
| `extend_video` | 766 | public | VeoGenerationResult | No | Blocking wrapper around `extend_video_async` |
| `_poll_for_completion` | 792 | private | Optional[Union[str, bytes]] | Yes | Long-poll the operation per Google's official pattern until a URL or raw bytes are available |
| `_download_video` | 905 | private | Optional[Path] | Yes | Authenticated download of the finished video to local storage |
| `_save_video_bytes` | 975 | private | Optional[Path] | Yes | Persist inline video bytes returned by the API |
| `generate_batch` | 1020 | public | List[VeoGenerationResult] | No | Run several configs with a concurrency cap |
| `concatenate_clips` | 1052 | public | bool | No | Join generated clips into one file, optionally stripping audio |
| `estimate_cost` | 1105 | public | float | No | USD estimate per second of generated video (audio doubles the rate on Veo 3.x) |
| `estimate_cost_formatted` | 1138 | public | str | No | Display string for the cost estimate |
| `get_model_info` | 1151 | public | Dict[str, Any] | No | Capability/constraint summary for a model |

---

### FFmpeg Renderer

**Path**: `core/video/ffmpeg_renderer.py` - 753 lines
**Purpose**: Assembles the final video with FFmpeg — Ken Burns pan/zoom slideshows from stills, or trimmed-and-concatenated Veo clips — then muxes the audio track, applies karaoke overlays, and produces previews and thumbnails.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `RenderSettings` | 24 | @dataclass | resolution, fps, video_codec, audio_codec, preset, crf, aspect_ratio, transition_duration, enable_ken_burns, ken_burns_scale, output_format |

##### `RenderSettings` Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `get_dimensions` | 38 | public | Tuple[int, int] | Resolve `"1080p"`-style strings into pixel width/height |

#### Class: `FFmpegRenderer` (line 44)

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 47 | constructor | None | Locate/verify FFmpeg, optionally auto-installing `imageio-ffmpeg` |
| `_verify_ffmpeg_path` | 72 | private | bool | Confirm an FFmpeg binary exists and runs at the given path |
| `render_slideshow` | 85 | public | Path | Render a slideshow video from project scenes (Ken Burns or static), with progress callback and optional karaoke |
| `render_from_clips` | 150 | public | Path | Assemble Veo clips, trimming each to its intended scene duration (Veo often returns fixed 8 s clips) |
| `_trim_clip` | 261 | private | None | Trim a single clip to a duration |
| `_concatenate_clips` | 285 | private | None | Join clips via the FFmpeg concat demuxer |
| `_prepare_ken_burns_images` | 309 | private | List[Path] | Render per-scene pan/zoom image clips |
| `_prepare_static_images` | 385 | private | List[Path] | Render per-scene static image clips (no effects) |
| `_create_static_video` | 415 | private | None | Turn one image into a fixed-duration video segment |
| `_create_video_from_images` | 439 | private | None | Concatenate prepared image clips into the base video, reporting progress |
| `_add_audio_track` | 491 | private | None | Mux the project audio onto the rendered video |
| `_run_with_progress` | 542 | private | None | Execute an FFmpeg command while parsing progress output against a known total duration |
| `create_preview` | 576 | public | Path | Produce a small, short preview version of a video |
| `extract_thumbnail` | 610 | public | Path | Grab a frame at a timestamp and scale it to a target size |
| `_add_karaoke_overlay` | 641 | private | Path | Burn the karaoke/lyrics overlay onto a rendered video |
| `get_video_info` | 715 | public | Dict[str, Any] | Probe a video file for duration, streams, and codec details |

---

### Karaoke Renderer

**Path**: `core/video/karaoke_renderer.py` - 427 lines
**Purpose**: Generates synchronized lyric assets — LRC, SRT, and styled ASS subtitle files — and renders karaoke overlays (including a bouncing-ball effect and animated lyric videos) with FFmpeg.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `KaraokeConfig` | 19 | @dataclass | enabled, style, position, font_size, font_color, background_opacity, ball_image, lead_time |

##### `KaraokeConfig` Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `to_dict` | 30 | public | Dict[str, Any] | JSON-serializable settings |
| `from_dict` | 44 | class | 'KaraokeConfig' | `@classmethod` reconstructor |

#### Class: `KaraokeRenderer` (line 51)

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 54 | constructor | None | Resolve the FFmpeg binary used for overlay rendering |
| `generate_lrc` | 73 | public | Path | Write an LRC lyrics file from timing data, optionally in enhanced (word-level) form |
| `generate_srt` | 153 | public | Path | Write an SRT subtitle file, optionally grouping words into caption lines |
| `_format_srt_time` | 231 | private | str | Format an SRT `start --> end` range (uses a nested `format_time` helper at line 233) |
| `generate_ass` | 244 | public | Path | Write an ASS/SSA file with karaoke styling driven by `KaraokeConfig` |
| `_format_ass_time` | 302 | private | str | Format `h:mm:ss.cc` timestamps for ASS |
| `add_bouncing_ball_overlay` | 311 | public | Path | Composite a bouncing-ball karaoke overlay onto a video via FFmpeg filters |
| `create_animated_lyrics_video` | 382 | public | Path | Produce a video with animated lyrics (and optional audio) from timing data |

---

### Audio Segmenter

**Path**: `core/video/audio_segmenter.py` - 299 lines
**Purpose**: Cuts scene-specific audio clips out of the full project audio with FFmpeg — used chiefly to feed per-scene audio to lip-sync video generation — with optional padding and fades.
**Language**: Python

#### Class: `AudioSegmenter` (line 12)

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 19 | constructor | None | Set up the cache directory for extracted segments |
| `_find_ffmpeg` | 29 | private | Optional[str] | Locate an FFmpeg executable |
| `extract_segment` | 50 | public | Optional[Path] | Extract `[start, end)` from the source audio with optional padding and fade in/out |
| `extract_scene_segments` | 150 | public | List[Tuple[int, Optional[Path]]] | Extract one segment per scene, returning `(scene_index, path)` pairs |
| `get_audio_duration` | 194 | public | Optional[float] | Probe the total duration of an audio file |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| `get_scene_audio_path` | 250 | public | Path | Canonical on-disk path for a scene's audio segment inside a project directory |
| `extract_scene_audio_for_lipsync` | 265 | public | Optional[Path] | One-call helper: extract a single scene's audio clip for lip-sync generation |

---

### Suno Package Support

**Path**: `core/video/suno_package.py` - 437 lines
**Purpose**: Detects, extracts, and merges Suno multi-file export zips (audio stems plus per-stem MIDI). Includes a permissive MIDI loader shim because Suno emits MIDI files with invalid key signatures that would otherwise crash `mido`. Stems are merged at equal volume — volume balancing is expected to happen in Suno before export.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_PERMISSIVE_MIDI_REGISTERED` | 25 | constant | Module-level guard flag, initially `False` |
| `_PERMISSIVE_MIDI_REGISTERED` | 68 | constant | Set `True` inside `_register_permissive_midi_loader` once the handler is installed (idempotent) |
| `KNOWN_STEM_NAMES` | 77 | constant | Recognized Suno stem names (Vocals, Drums, Bass, …) used by `_extract_stem_name` |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `SunoPackage` | 85 | @dataclass | source_zip, extract_dir, audio_stems, midi_files, merged_audio, merged_midi |

##### `SunoPackage` Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `cleanup` | 94 | public | None | Remove the temporary extraction directory |
| `__del__` | 103 | magic | None | Best-effort cleanup on garbage collection |

#### Nested Helper Class
| Name | Line | Description |
|------|------|-------------|
| `PermissiveKeySignatureSpec` | 49 | Defined inside `_register_permissive_midi_loader`; replaces mido's key-signature spec so invalid values (e.g. 19 sharps) decode to `None` instead of raising. Methods: `decode` (line 52), `check` (line 60) |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| `_register_permissive_midi_loader` | 27 | private | None | Install the tolerant key-signature handler into mido once per process |
| `_extract_stem_name` | 108 | private | Optional[str] | Pull the stem name out of a Suno filename (`"… (Vocals).wav"` → `"Vocals"`) |
| `detect_suno_package` | 130 | public | Optional[SunoPackage] | Identify and extract a Suno zip — valid packages hold at least one recognizable `.wav` stem plus optional matching MIDI |
| `merge_audio_stems` | 204 | public | Path | Merge selected stems into a single audio file with FFmpeg at equal volume |
| `merge_midi_files` | 294 | public | Path | Merge per-stem MIDI files into one multi-track MIDI, preserving stem names as track names |
| `get_package_info` | 422 | public | Dict[str, any] | Human-readable summary of a detected package (stems, MIDI files, paths) |

---

### Renderers Package Init

**Path**: `core/video/renderers/__init__.py` - 0 lines
**Purpose**: Empty package marker for the `core/video/renderers/` subpackage; contains no symbols.
**Language**: Python

---

## Core — Layout Engine, Styles, Reference & Model Registry

This section covers the publication layout engine (`core/layout/`), the Custom Styles
feature (`core/styles/`), Imagen reference-image support (`core/reference/`), and the
runtime LLM model-ID registry (`core/model_registry/`).

The layout stack is deliberately split into a **pure, Qt-free model/geometry core**
(`models`, `schema`, `geometry`, `polygon`, `tiling`, `balloons`, `svg_path`,
`text_path`, `region_ops`, `overlay_ops`) and **renderers** — a native Qt renderer
(`qt_renderer.py`, the source of truth for on-screen/PNG/PDF output) plus a legacy
PIL-based engine (`engine.py` + `text_renderer.py` + `image_processor.py` +
`layout_algorithms.py`) used for template-driven book/magazine pages.

---

### qt_renderer
**Path**: `core/layout/qt_renderer.py` - 578 lines
**Purpose**: Native Qt renderer — turns a `PageSpec` into a `QGraphicsScene`, then into a `QImage`, PNG, or multi-page PDF. Source of truth for all layout rendering, including bleed compositing, comic overlays, and text-on-a-curve.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_PLACEHOLDER_FILL` | 22 | constant | Brush for empty image regions |
| `_PLACEHOLDER_PEN` | 23 | constant | Pen for empty image-region outlines |
| `_TEXT_GUIDE_PEN` | 28 | constant | Dashed guide pen for text-region boxes |
| `_DEFAULT_TEXT_PX` | 31 | constant | Fallback text size when no style resolves |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `_RegionMoveMixin` | 133 | Mixin that writes drag deltas back into the bound `Region` so moves survive the model-driven scene rebuild |
| `_RegionRectItem` | 152 | `QGraphicsRectItem` bound to a rect region |
| `_RegionPixmapItem` | 158 | `QGraphicsPixmapItem` bound to an image region |
| `_RegionPathItem` | 164 | `QGraphicsPathItem` bound to a polygon/path region |
| `_OverlayPathItem` | 262 | Balloon body item whose `shape()` returns the *filled* interior (not the stroked outline) so child text clips correctly |
| `_OverlayStyleable` | 275 | Minimal adapter exposing `.text_style`/`.role` so overlays can reuse `effective_text_style` |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_RegionMoveMixin._bind_region` | 140 | private | None | No | Attach the model `Region` the item writes back to |
| `_RegionMoveMixin.itemChange` | 146 | public | Any | No | Qt hook; persists position changes into the region geometry |
| `_RegionRectItem.__init__` | 153 | constructor | None | No | Build from `QRectF` + region |
| `_RegionPixmapItem.__init__` | 159 | constructor | None | No | Build from `QPixmap` + region |
| `_RegionPathItem.__init__` | 165 | constructor | None | No | Build from `QPainterPath` + region |
| `_RegionPathItem.shape` | 169 | public | QPainterPath | No | Hit-test shape for path regions |
| `_OverlayPathItem.shape` | 271 | public | QPainterPath | No | Filled-interior hit/clip shape |
| `_OverlayStyleable.__init__` | 279 | constructor | None | No | Wrap an overlay's text style + role |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_resolve_bg` | 34 | private | str | No | Resolve a page background to a hex color (non-hex → white) |
| `segments_to_painter_path` | 46 | public | QPainterPath | No | `PathSegment` list → `QPainterPath` (move/line/quad/cubic/close) |
| `region_to_painter_path` | 69 | public | QPainterPath | No | Path for a rect/polygon/path region; invalid segments fall back to the bbox |
| `_apply_flags` | 97 | private | None | No | Set selectable/movable flags and stash the region id on an item |
| `_writeback_move` | 109 | private | None | No | Persist a drag delta into the bound region's bbox/points/segments |
| `_add_image_region` | 175 | private | None | No | Add an image region (pixmap or placeholder) to the scene |
| `_add_text_region` | 220 | private | None | No | Add a text region with resolved project style and guide box |
| `overlay_as_styleable` | 284 | public | `_OverlayStyleable` | No | Adapt an `Overlay` for the shared style resolver |
| `overlay_font` | 292 | public | QFont | No | Pick the first available family from the style list (DejaVu Sans last resort) |
| `_point_angle_at` | 315 | private | tuple | No | (point, tangent angle°) at an arc length along a painter path |
| `_curved_text_glyphs` | 334 | private | QPainterPath | No | Combined glyph outline with each glyph rotated to the local tangent |
| `_add_curved_text_overlay` | 357 | private | None | No | Render a caption/SFX overlay whose text follows `ov.text_path` |
| `_add_overlay` | 387 | private | None | No | Measure wrapped text, build balloon body + tail, add body and text items |
| `build_scene` | 497 | public | QGraphicsScene | No | Compose a page into a scene (z-sorted regions, then overlays); supports `region_filter` and `include_overlays` |
| `render_page_to_image` | 520 | public | QImage | No | Rasterize a page at `scale`, compositing trim-clipped and bleed passes separately |
| `save_page_png` | 554 | public | None | No | Render and write a single page PNG |
| `export_document_pdf` | 558 | public | None | No | Multi-page vector PDF via `QPdfWriter` at the requested DPI |

---

### template_manager
**Path**: `core/layout/template_manager.py` - 559 lines
**Purpose**: Template discovery, JSON-schema validation, inheritance resolution, preview thumbnail generation/caching, and category/tag search.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `HAS_JSONSCHEMA` | 17, 19 | constant | Set in the `try`/`except ImportError` guard around `jsonschema` |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `TemplateMetadata` | 30 | @dataclass | name, filepath, category, description, tags, author, schema_version, page_size_px, thumbnail_path, extends, block_count, last_modified |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `TemplateMetadata` | 30 | Lightweight record describing a discovered template file |
| `ValidationError` | 56 | Template validation error with path/message formatting |
| `TemplateValidator` | 68 | Validates template JSON against the bundled schema (with manual fallback when `jsonschema` is absent) |
| `TemplatePreviewGenerator` | 182 | Generates and caches preview thumbnails rendered from template data |
| `TemplateManager` | 298 | Discovery, loading, inheritance resolution, search, and caching of templates |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `TemplateMetadata.matches_search` | 45 | public | bool | No | Case-insensitive match over name/description/tags |
| `ValidationError.__str__` | 62 | dunder | str | No | Human-readable `path: message` rendering |
| `TemplateValidator.__init__` | 71 | constructor | None | No | Load the schema from `schema_path` |
| `TemplateValidator.validate` | 85 | public | `List[ValidationError]` | No | Validate template data; empty list means valid |
| `TemplatePreviewGenerator.__init__` | 185 | constructor | None | No | Set up the on-disk preview cache directory |
| `TemplatePreviewGenerator.get_cache_path` | 194 | public | Path | No | Hash-derived cache path for a template file |
| `TemplatePreviewGenerator.get_preview` | 202 | public | `Optional[Path]` | No | Return a cached preview or generate one |
| `TemplatePreviewGenerator._generate_preview` | 226 | private | `Image.Image` | No | Draw a thumbnail from the template's blocks |
| `TemplatePreviewGenerator.clear_cache` | 285 | public | None | No | Clear all previews or one template's preview |
| `TemplateManager.__init__` | 303 | constructor | None | No | Configure search dirs (defaults to `ConfigManager.get_templates_dir()`) |
| `TemplateManager.discover_templates` | 327 | public | `List[TemplateMetadata]` | No | Scan the template dirs; `rescan=True` bypasses the cache |
| `TemplateManager._load_template_metadata` | 362 | private | `Optional[TemplateMetadata]` | No | Read one template file's header fields |
| `TemplateManager.get_template` | 408 | public | `Optional[TemplateMetadata]` | No | Look up metadata by template key |
| `TemplateManager.load_template_data` | 414 | public | `Optional[Dict[str, Any]]` | No | Load full template JSON with inheritance resolved |
| `TemplateManager._resolve_inheritance` | 451 | private | `Dict[str, Any]` | No | Merge a child template over its `extends` parent |
| `TemplateManager.search_templates` | 480 | public | `List[TemplateMetadata]` | No | Filter by free-text query, category, and tags |
| `TemplateManager.get_categories` | 519 | public | `List[str]` | No | Distinct categories across discovered templates |
| `TemplateManager.get_all_tags` | 527 | public | `List[str]` | No | Distinct tags across discovered templates |
| `TemplateManager.validate_template_file` | 538 | public | `List[ValidationError]` | No | Validate a template file on disk |
| `TemplateManager.clear_cache` | 556 | public | None | No | Drop the loaded-template-data cache |

---

### engine (LayoutEngine)
**Path**: `core/layout/engine.py` - 433 lines
**Purpose**: PIL-based page/document renderer for the template (blocks) pipeline — PNG page rendering, text and image block drawing, and PDF assembly via ReportLab.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `REPORTLAB_AVAILABLE` | 15, 18 | constant | Set in the `try`/`except ImportError` guard around `reportlab` |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `LayoutEngine` | 33 | Main PIL rendering engine; optionally uses the advanced text engine with hyphenation |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 43 | constructor | None | No | Wire a `FontManager`, advanced-text toggle, hyphenation language |
| `render_page_png` | 65 | public | None | No | Render one page to a PNG file, optionally running template substitution |
| `render_page_to_image` | 109 | public | `Image.Image` | No | Render one page to a PIL image (GUI preview path) |
| `_render_image_block` | 149 | private | None | No | Draw an image block through `ImageProcessor` |
| `_render_text_block` | 186 | private | None | No | Draw a text block with auto-sizing |
| `_render_text_advanced` | 201 | private | None | No | Draw via `TextLayoutEngine` (hyphenation + justification) |
| `_render_text_simple` | 220 | private | None | No | Legacy simple wrap/draw path |
| `_wrap_to_width` | 240 | private | `List[str]` | No | Word-wrap text to a pixel width |
| `_measure_text_height` | 260 | private | int | No | Total height of wrapped lines |
| `_draw_multiline_text` | 266 | private | None | No | Draw wrapped lines honoring alignment |
| `_draw_rounded_rectangle` | 298 | private | None | No | Rounded border stroke helper |
| `_hex_to_rgb` | 322 | private | `Tuple[int, int, int]` | No | Hex color → RGB tuple |
| `render_document_png` | 329 | public | `List[Path]` | No | Render every page of a document to PNGs |
| `save_pdf` | 353 | public | None | No | Assemble rendered PNG pages into a PDF |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `load_template_json` | 384 | public | PageSpec | No | Parse a page-template JSON file into a `PageSpec` |

---

### layout_algorithms
**Path**: `core/layout/layout_algorithms.py` - 389 lines
**Purpose**: Smart layout math — binary-search text auto-fit, overflow splitting across pages, comic panel grids, magazine column flow, safe-area/bleed adjustment, and proportional scaling.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `FitResult` | 23 | @dataclass | font_size, fits, overflow_text |
| `PanelGrid` | 31 | @dataclass | rows, cols, gutter, panel_rects |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `LayoutAlgorithms` | 39 | Namespace of stateless `@staticmethod` layout algorithms |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `@staticmethod auto_fit_text` | 45 | static | FitResult | No | Binary-search the largest font size that fits text in a rect |
| `@staticmethod _wrap_text` | 103 | static | `List[str]` | No | Simple word wrapping |
| `@staticmethod _measure_text_height` | 129 | static | int | No | Total wrapped-text height |
| `@staticmethod split_text_overflow` | 140 | static | `Tuple[str, str]` | No | Split into (visible, overflow) for continuation pages |
| `@staticmethod compute_panel_grid` | 187 | static | PanelGrid | No | Comic panel rectangles for rows × cols with gutters |
| `@staticmethod compute_column_layout` | 242 | static | `List[Rect]` | No | Magazine-style column rectangles |
| `@staticmethod apply_safe_area` | 285 | static | Rect | No | Adjust a rect for margin and bleed |
| `@staticmethod distribute_space` | 316 | static | `List[Tuple[int, int]]` | No | Even (offset, size) distribution with spacing |
| `@staticmethod calculate_aspect_ratio` | 354 | static | Size | No | Proportional scale to a target size (never distorts) |

---

### text_renderer
**Path**: `core/layout/text_renderer.py` - 386 lines
**Purpose**: Advanced text layout for the PIL engine — hyphenated word wrapping, justification, widow/orphan control, and multi-paragraph drawing.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `HYPHENATION_AVAILABLE` | 14, 17 | constant | Set in the `try`/`except ImportError` guard around `pyphen` |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `LayoutLine` | 26 | @dataclass | text, width, word_count, has_hyphen, is_paragraph_end |
| `LayoutParagraph` | 36 | @dataclass | lines, spacing_after |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `TextLayoutEngine` | 42 | Line-breaking + drawing engine with hyphenation and justification |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 52 | constructor | None | No | Set the hyphenation language (e.g. `en_US`) |
| `layout_text` | 71 | public | `Tuple[List[LayoutParagraph], int]` | No | Lay text out into paragraphs/lines; returns used height |
| `_wrap_paragraph` | 158 | private | `List[LayoutLine]` | No | Wrap one paragraph, hyphenating where needed |
| `_try_hyphenate` | 228 | private | `Optional[Tuple[str, str]]` | No | Split a word at a hyphenation point to fill the line |
| `_apply_widow_orphan_control` | 264 | private | `List[LayoutLine]` | No | Prevent single stranded lines at column boundaries |
| `draw_layout` | 293 | public | None | No | Draw laid-out paragraphs onto a PIL `ImageDraw` |
| `_draw_justified_line` | 344 | private | None | No | Draw one line with expanded word spacing |
| `_hex_to_rgb` | 381 | private | `Tuple[int, int, int]` | No | Hex color → RGB tuple |

---

### designer (AI layout designer)
**Path**: `core/layout/designer.py` - 342 lines
**Purpose**: The AI page designer — builds the LLM chat messages, parses the model's JSON layout (regions, tiling presets, comic overlays), and performs the live LiteLLM call.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_SYSTEM` | 14 | constant | System prompt: design page *geometry* only, reply with one JSON object |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `DesignerResult` | 105 | @dataclass | questions, regions, overlays, raw |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `build_messages` | 21 | public | `List[Dict[str, str]]` | No | Compose system+user messages from content kind, page pixels, user text, and current regions |
| `resolve_provider_ids` | 81 | public | `Tuple[str, str]` | No | Map a provider display name/alias to (api-key id, registry id) |
| `fallback_result` | 112 | public | DesignerResult | No | Single full-page frame + a clarifying question when parsing fails |
| `_resolve_overlay_anchor` | 122 | private | tuple | No | Resolve an overlay's anchor/tail to page pixels (raw px wins over region+offset) |
| `_build_overlay` | 170 | private | `Optional[Overlay]` | No | Build one `Overlay` from an LLM dict, or skip it |
| `_regions_from_tiling` | 209 | private | `List[Region]` | No | Expand a tiling-preset request into gap-free panel regions |
| `_normalize_region_dict` | 239 | private | Dict | No | Map LLM shorthands (`svg`, top-level `stroke_px`) onto schema keys |
| `parse_response` | 260 | public | DesignerResult | No | Parse the JSON reply into questions + normalized regions + overlays |
| `run_design` | 303 | public | DesignerResult | No | Run an injected completion callable and parse the result (test seam) |
| `run_completion` | 309 | public | str | No | Real LiteLLM call with key resolution, gcloud auth mode, and full request/response logging |

---

### polygon
**Path**: `core/layout/polygon.py` - 310 lines
**Purpose**: Pure straight-edge polygon math for the tiling engine (no Qt) — orientation, half-plane clipping, mitred inset, and edge-cancellation union.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `EPS` | 21 | constant | Geometric tolerance |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `signed_area` | 24 | public | float | No | Signed area of an open-ring polygon |
| `ensure_orientation` | 34 | public | Poly | No | Copy oriented to positive signed area (canonical) |
| `_side` | 39 | private | float | No | Left/right/on-line test for a point vs a directed line |
| `clip_halfplane` | 44 | public | Poly | No | Sutherland–Hodgman clip keeping the LEFT half of line a→b |
| `polygon_to_segments` | 75 | public | `List[PathSegment]` | No | Open ring → move/line…/close `PathSegment`s |
| `_unit` | 86 | private | `Tuple[float, float]` | No | Normalized direction vector |
| `_line_intersect` | 93 | private | `Optional[Point]` | No | Parametric line intersection (None if near-parallel) |
| `inset_polygon` | 102 | public | `Optional[Poly]` | No | Per-edge inward offset with miter limit; None on collapse |
| `_q` | 151 | private | Point | No | Quantize a point (3 decimals) for edge matching |
| `_colinear_between` | 155 | private | bool | No | Point strictly between two colinear endpoints |
| `_subdivide` | 171 | private | `List[Tuple[Point, Point]]` | No | Split edges at other edges' endpoints lying on them |
| `_remove_colinear` | 189 | private | Poly | No | Drop vertices colinear with their neighbors |
| `union_polygons` | 215 | public | `List[Poly]` | No | Union edge-sharing polygons by directed-edge cancellation; one ring per component |

---

### image_processor
**Path**: `core/layout/image_processor.py` - 305 lines
**Purpose**: PIL image handling for layout blocks — fit modes, anti-aliased rounded corners, filters, tonal adjustments, and border drawing.
**Language**: Python

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `ImageProcessor` | 18 | Stateless `@staticmethod` image pipeline for layout rendering |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `@staticmethod load_and_process` | 31 | static | `Optional[Image.Image]` | No | Load an image and apply fit, corners, filters, and adjustments per `ImageStyle` |
| `@staticmethod _apply_fit_mode` | 74 | static | `Image.Image` | No | cover / contain / fill sizing (always proportional, never distorted) |
| `@staticmethod _apply_rounded_corners` | 134 | static | `Image.Image` | No | Anti-aliased rounded-corner alpha mask |
| `@staticmethod apply_filter` | 176 | static | `Image.Image` | No | Blur/sharpen/etc. at a normalized intensity |
| `@staticmethod apply_adjustments` | 237 | static | `Image.Image` | No | Brightness, contrast, saturation factors |
| `@staticmethod draw_border` | 274 | static | None | No | Stroke a (rounded) border around a rect |

---

### template_engine
**Path**: `core/layout/template_engine.py` - 301 lines
**Purpose**: `{{variable}}` substitution for template pages, plus color-palette helpers (computed lighter/darker variants) and theme-file loading.
**Language**: Python

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `TemplateEngine` | 19 | Variable substitution engine with color-palette and computed-value support |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 33 | constructor | None | No | Seed global variables shared by all templates |
| `process_page` | 42 | public | PageSpec | No | Return a page with every block's variables substituted |
| `_process_text_block` | 85 | private | TextBlock | No | Substitute in text content and text style |
| `_process_image_block` | 114 | private | ImageBlock | No | Substitute in image path and image style |
| `_substitute` | 139 | private | str | No | Replace `{{name}}` and computed color functions (`{{accent_light}}`) |
| `_substitute.replace_var` | 150 | nested | str | No | Regex callback resolving one variable token |
| `_lighten_color` | 174 | private | str | No | Lighten a hex color by a 0–1 amount |
| `_darken_color` | 204 | private | str | No | Darken a hex color by a 0–1 amount |
| `@staticmethod create_color_palette` | 235 | static | `Dict[str, str]` | No | Derive a named palette from one primary color |
| `@staticmethod load_theme` | 260 | static | `Dict[str, str]` | No | Load a JSON theme (colors + variables) into a flat variable map |

---

### schema (layout serialization)
**Path**: `core/layout/schema.py` - 290 lines
**Purpose**: Serialization, normalization, and validation for layout documents — dataclass ⇄ dict for every model, forward-compatible key filtering, region clamping, and document validation.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `REGION_JSON_SCHEMA` | 26 | constant | JSON-schema fragment describing a region (used to constrain LLM output) |
| `OVERLAY_JSON_SCHEMA` | 54 | constant | JSON-schema fragment describing a comic overlay |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_filtered` | 17 | private | Dict | No | Keep only keys that are real dataclass fields, so forward/hand-edited files load instead of crashing |
| `_style_to_dict` | 77 | private | `Optional[Dict]` | No | `asdict` a style or pass through None |
| `region_to_dict` | 81 | public | Dict | No | Serialize a `Region` (bbox, points, segments, styles, gen settings) |
| `region_from_dict` | 94 | public | Region | No | Deserialize a `Region` with filtered style kwargs |
| `_overlay_style_to_dict` | 114 | private | Dict | No | Serialize an `OverlayStyle` |
| `_overlay_style_from_dict` | 121 | private | OverlayStyle | No | Deserialize an `OverlayStyle` |
| `overlay_to_dict` | 125 | public | Dict | No | Serialize an `Overlay` (anchor, tail, rotation, text path) |
| `overlay_from_dict` | 141 | public | Overlay | No | Deserialize an `Overlay`, validating its text path |
| `snapshot_to_dict` | 168 | public | Dict | No | Serialize a history `Snapshot` |
| `snapshot_from_dict` | 175 | public | Snapshot | No | Deserialize a history `Snapshot` |
| `project_style_to_dict` | 183 | public | Dict | No | Serialize `ProjectStyle` font roles + palette |
| `project_style_from_dict` | 191 | public | ProjectStyle | No | Deserialize `ProjectStyle` |
| `_page_size_from_dict` | 200 | private | PageSize | No | Deserialize a physical `PageSize` |
| `page_to_dict` | 204 | public | Dict | No | Serialize a `PageSpec` (regions + overlays + page size) |
| `page_from_dict` | 215 | public | PageSpec | No | Deserialize a `PageSpec`, migrating legacy blocks |
| `document_to_dict` | 239 | public | Dict | No | Serialize a `DocumentSpec` including history and style |
| `document_from_dict` | 250 | public | DocumentSpec | No | Deserialize a `DocumentSpec` |
| `normalize_region` | 263 | public | Region | No | Recompute the bbox from points/segments and clamp it inside the page |
| `validate_document` | 282 | public | `List[str]` | No | Report structural problems (no pages, duplicate region ids) |

---

### models (layout data model)
**Path**: `core/layout/models.py` - 241 lines
**Purpose**: Every dataclass in the layout domain — page sizes, styles, legacy blocks, path segments, regions, comic overlays, snapshots, project style, pages, and documents.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `PageSize` | 16 | @dataclass | width, height, unit, orientation, dpi |
| `TextStyle` | 40 | @dataclass | family, weight, italic, size_px, line_height, color, align, wrap, letter_spacing, outline_px, outline_color |
| `OverlayStyle` | 58 | @dataclass | fill, stroke_px, stroke_color, padding_px, radius_px, max_width_px |
| `ImageStyle` | 69 | @dataclass | fit, border_radius_px, stroke_px, stroke_color |
| `BlockBase` | 79 | @dataclass | id, rect |
| `TextBlock` | 87 | @dataclass | type, text, style (legacy block) |
| `ImageBlock` | 98 | @dataclass | type, image_path, style, alt_text (legacy block) |
| `PathSegment` | 108 | @dataclass | type (move/line/quad/cubic/close), pts |
| `Region` | 120 | @dataclass | id, kind, shape, bbox, points, segments, bleed, z, name, text, role, image_ref, prompt, gen_settings, text_style, image_style |
| `Overlay` | 145 | @dataclass | id, kind, text, anchor, anchor_mode, tail_target, z, role, text_style, style, rotation, text_path |
| `Snapshot` | 170 | @dataclass | id, parent_id, timestamp, prompt, document, thumbnail |
| `ProjectStyle` | 182 | @dataclass | font_roles, palette, default_text_role |
| `PageSpec` | 191 | @dataclass | page_size_px, margin_px, bleed_px, background, blocks, variables, page_size, regions, overlays |
| `DocumentSpec` | 206 | @dataclass | title, author, pages, theme, metadata, content_kind, schema_version, history, style, render_on_top |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `PageSize.to_pixels` | 25 | public | `Tuple[int, int]` | No | Convert physical size + DPI to page pixels |
| `PageSize.swapped` | 34 | public | PageSize | No | Flip width/height and the orientation flag |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `migrate_legacy_blocks` | 223 | public | `List[Region]` | No | Convert legacy `TextBlock`/`ImageBlock` objects into `Region`s |

---

### tiling
**Path**: `core/layout/tiling.py` - 217 lines
**Purpose**: Page-partition engine — a slice tree becomes gap-free panels, merged cells become concave panels, and each panel is inset by gutter/margin. Emits `shape="path"` regions; pure (no Qt).
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_CUT_EPS` | 21 | constant | Tolerance for cut-line placement |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `Split` | 25 | @dataclass | axis, at, a, b, skew |
| `Leaf` | 34 | @dataclass | id, kind, bleed, merge |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_cut_line` | 44 | private | tuple | No | Endpoint pair for a (possibly skewed) split line through a cell |
| `_collect_leaves` | 60 | private | None | No | Recursively clip the tree into leaf polygons |
| `_edge_is_boundary` | 76 | private | bool | No | Whether an edge lies on the page rect (no gutter inset there) |
| `_inset_dists` | 85 | private | `List[float]` | No | Per-edge inset distances from gutter, margin, and bleed |
| `_panel_to_region` | 97 | private | `Optional[Region]` | No | Inset a panel polygon and wrap it as a path `Region` |
| `tile` | 109 | public | `List[Region]` | No | Partition the page rect, merge cells sharing a merge key, inset each panel |
| `grid` | 162 | public | Node | No | Regular rows × cols grid preset (nested y-then-x splits) |
| `grid.row` / `grid.col` / `grid.build` | 167 / 168 / 175 | nested | Node | No | Recursive helpers that build the grid tree |
| `three_tiers` | 183 | public | Node | No | Preset: three full-width horizontal tiers |
| `splash_with_strip` | 189 | public | Node | No | Preset: large top splash over a bottom strip of two |
| `diagonal_action` | 195 | public | Node | No | Preset: two panels split by a strongly angled gutter |
| `feature_L` | 200 | public | Node | No | Preset: concave L hero beside a tall right panel |
| `apply_tiling` | 206 | public | PageSpec | No | Tile a page and layer floating panels above it (mutates and returns the page) |

---

### font_manager
**Path**: `core/layout/font_manager.py` - 212 lines
**Purpose**: Font discovery across platform-specific system directories and custom paths, manifest building/persistence, and priority-ordered PIL font loading.
**Language**: Python

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `FontManager` | 19 | Discovers fonts, maintains a manifest, and resolves family lists to files/PIL fonts |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 29 | constructor | None | No | Load an existing manifest and register custom scan dirs |
| `discover_fonts` | 53 | public | None | No | Scan system + custom directories into the manifest |
| `_get_system_font_dirs` | 78 | private | `List[Path]` | No | Platform-specific font directories |
| `_add_font_to_manifest` | 101 | private | None | No | Extract family/weight/italic from a font file and record it |
| `save_manifest` | 137 | public | None | No | Persist the manifest as JSON |
| `select_font_file` | 146 | public | `Optional[Path]` | No | First matching font file for a priority-ordered family list |
| `pil_font` | 179 | public | `ImageFont.FreeTypeFont` | No | Load a PIL font at a pixel size (with fallbacks) |
| `get_available_families` | 210 | public | `List[str]` | No | All families known to the manifest |

---

### balloons
**Path**: `core/layout/balloons.py` - 204 lines
**Purpose**: Pure (Qt-free) comic-overlay geometry — compiles an overlay's inner text rect into balloon/caption/thought body outlines plus tails, as `PathSegment`s the Qt renderer draws unchanged.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `KAPPA` | 22 | constant | Circle-to-cubic-Bézier control constant |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_valid_rect` | 25 | private | bool | No | Reject degenerate inner rects |
| `caption_body` | 30 | public | `List[PathSegment]` | No | Plain rectangle caption box around `inner` |
| `speech_body` | 42 | public | `List[PathSegment]` | No | Rounded rectangle with circular cubic corners, in a fixed segment order the tail splice depends on |
| `_edge_for_target` | 67 | private | str | No | Which body edge faces the tail target |
| `_edge_span` | 78 | private | `Tuple[Point, Point, int]` | No | Straight-edge endpoints + segment index for a rounded body |
| `_splice_speech_tail` | 92 | private | `List[PathSegment]` | No | Insert a tapered tail into the body outline at the chosen edge |
| `_splice_speech_tail._d2` | 111 | nested | float | No | Squared distance helper |
| `_circle_segments` | 126 | private | `List[PathSegment]` | No | Closed circle as four cubic quarter-arcs |
| `thought_body` | 139 | public | `List[PathSegment]` | No | Scalloped cloud on an ellipse circumscribing `inner` |
| `thought_trail` | 163 | public | `List[PathSegment]` | No | Shrinking circles from the body toward the tail target |
| `overlay_to_segments` | 175 | public | `List[PathSegment]` | No | Dispatch by overlay kind → body (+ tail) geometry |

---

### bundle_io
**Path**: `core/layout/bundle_io.py` - 188 lines
**Purpose**: Self-contained `.iaibundle` export/import — zips the document with every referenced image and (where resolvable) embedded fonts, with zip-slip-safe extraction.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `BUNDLE_SCHEMA_VERSION` | 27 | constant | Bundle format version |
| `_PROJECT_NAME` | 28 | constant | `project.iaiproj.json` member name |
| `_MANIFEST_NAME` | 29 | constant | `bundle.json` member name |
| `_IMAGES_DIR` | 30 | constant | `images/` member prefix |
| `_FONTS_DIR` | 31 | constant | `fonts/` member prefix |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `BundleManifest` | 38 | @dataclass | schema_version, title, images, fonts, warnings |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `BundleManifest.to_dict` | 45 | public | Dict | No | Serialize the manifest for `bundle.json` |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_safe_stem` | 53 | private | str | No | Sanitize a filename stem for zip members |
| `_unique_member` | 58 | private | str | No | De-duplicate member names within the bundle |
| `_collect_font_family_lists` | 70 | private | `List[List[str]]` | No | All distinct priority-ordered family lists used by the document |
| `_collect_font_family_lists.add` | 75 | nested | None | No | Accumulate one family list |
| `export_bundle` | 94 | public | BundleManifest | No | Write document + assets to a `.iaibundle` zip; font resolution is injected for testability |
| `_safe_extract` | 159 | private | None | No | Extract guarding against zip-slip (members escaping the destination) |
| `import_bundle` | 169 | public | DocumentSpec | No | Extract a bundle and load its document with image refs rewritten to absolute paths |

---

### svg_path
**Path**: `core/layout/svg_path.py` - 135 lines
**Purpose**: Pure converter between SVG path `d` strings and `PathSegment`s (subset `M L H V C Q Z`, absolute + relative), so the AI designer can author curves natively. Never raises — malformed input degrades to what parsed cleanly.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_NUM` | 20 | constant | Number regex fragment |
| `_TOKEN_RE` | 21 | constant | Command/number tokenizer |
| `_ARGC` | 22 | constant | Argument count per path command |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_tokenize` | 25 | private | `List[Tuple[str, object]]` | No | Split a `d` string into command/number tokens |
| `svg_to_segments` | 35 | public | `List[PathSegment]` | No | Parse an SVG `d` string into `PathSegment`s |
| `_fmt` | 113 | private | str | No | Compact number formatting |
| `segments_to_svg` | 117 | public | str | No | Serialize segments back to an absolute-coordinate `d` string |

---

### prompt_helper
**Path**: `core/layout/prompt_helper.py` - 126 lines
**Purpose**: Per-region AI prompt help — build the chat messages that ask an LLM for one image prompt using page/neighbor context, and parse the reply. The live LLM call is injected (`designer.run_completion`) so the module is headless-testable.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_SYSTEM` | 16 | constant | System prompt; explicitly forbids pixel/aspect tokens in prompt text (per AGENTS.md §9) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_aspect_ratio` | 25 | private | str | No | Reduced `w:h` ratio, used as context only |
| `_find_page` | 35 | private | `Optional[PageSpec]` | No | Locate the page containing a region |
| `_neighbor_text` | 43 | private | `List[str]` | No | Text from sibling text regions (scene context) |
| `build_prompt_messages` | 52 | public | `List[Dict[str, str]]` | No | Build the chat messages requesting one image prompt |
| `_strip_fences` | 91 | private | str | No | Remove Markdown code fences from a reply |
| `parse_prompt_response` | 105 | public | str | No | Extract the prompt — JSON `{"prompt": …}` first, else fenced/plain text |
| `run_prompt_help` | 122 | public | str | No | Run the injected completion and parse out the suggested prompt |

---

### batch_fill
**Path**: `core/layout/batch_fill.py` - 114 lines
**Purpose**: Pure helpers for filling layout regions through the Google Batch API — build region-keyed batch requests, snap aspect ratios to supported values, and map JSONL results back to regions.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_SUPPORTED_RATIOS` | 21 | constant | Google-supported image aspect ratios |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `nearest_supported_ratio` | 24 | public | str | No | Closest supported aspect ratio to `width:height` by value |
| `_ratio_value` | 34 | private | float | No | Numeric value of a `"w:h"` ratio string |
| `build_requests` | 39 | public | tuple | No | Build `(requests, skipped_ids)` keyed by region id, with ratio (never pixels) in the request |
| `_first_image_bytes` | 73 | private | `Optional[bytes]` | No | Decode the first image part of a batch response |
| `parse_result_jsonl` | 87 | public | `Dict[str, bytes]` | No | Map each result line's key → decoded image bytes |
| `results_to_placements` | 110 | public | `List[Tuple[str, bytes]]` | No | `(region_id, bytes)` for results matching image regions in the document |

---

### region_ops
**Path**: `core/layout/region_ops.py` - 114 lines
**Purpose**: Pure panel operations for the manual editor — split, merge, and delete regions via polygon clipping/union. Curved regions return None so callers degrade gracefully.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_AREA_EPS` | 18 | constant | Square-pixel tolerance for the merge area-conservation check |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `region_to_polygon` | 21 | public | `Optional[Poly]` | No | Region → open-ring polygon (rect corners, polygon points, or straight-only path anchors) |
| `_poly_bbox` | 48 | private | Rect | No | Integer bbox of a polygon |
| `_region_from_polygon` | 55 | private | Region | No | Build a polygon `Region`, copying identity/style from a template region |
| `split_region` | 72 | public | `Optional[Tuple[Region, Region]]` | No | Cut a region by the line a→b into (left, right) halves |
| `merge_regions` | 94 | public | `Optional[Region]` | No | Union two edge-adjacent regions, keeping the base region's identity |

---

### layout package init
**Path**: `core/layout/__init__.py` - 83 lines
**Purpose**: Package facade for the Layout/Books module. Re-exports the data models (`TextStyle`, `ImageStyle`, `TextBlock`, `ImageBlock`, `PageSpec`, `DocumentSpec`, `PageSize`, `Region`, `migrate_legacy_blocks`, `Size`, `Rect`), Phase 1 core (`FontManager`, `LayoutEngine`, `load_template_json`), Phase 2 features (`TextLayoutEngine`, `LayoutLine`, `LayoutParagraph`, `ImageProcessor`, `TemplateEngine`, `LayoutAlgorithms`, `FitResult`, `PanelGrid`), and Phase 3 template management (`TemplateManager`, `TemplateMetadata`, `TemplateValidator`, `TemplatePreviewGenerator`, `ValidationError`) through `__all__`.
**Language**: Python

*(No classes or functions defined here — imports and `__all__` only.)*

---

### styles (project style defaults)
**Path**: `core/layout/styles.py` - 79 lines
**Purpose**: Default project style — font roles and palette seeded by content kind — plus the precedence rule that resolves which `TextStyle` renders a region.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_PALETTE` | 13 | constant | Default background/text/accent colors |
| `_KIND_ROLES` | 15 | constant | Per-content-kind font-role tables (children, comic, magazine, …) |
| `_DEFAULT_ROLE` | 44 | constant | Role used when nothing else resolves |
| `_FALLBACK_ROLES` | 49 | constant | Role table for unknown content kinds |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_role` | 7 | private | TextStyle | No | Build a `TextStyle` role from family/size/weight/color |
| `default_style_for` | 55 | public | ProjectStyle | No | Seed a `ProjectStyle` for a content kind |
| `effective_text_style` | 65 | public | `Optional[TextStyle]` | No | Resolve the style to render a region: explicit `text_style` > project role > project default role |

---

### overlay_ops
**Path**: `core/layout/overlay_ops.py` - 70 lines
**Purpose**: Pure overlay repair — detect overlays whose anchor was stranded over empty space by a regions-only redesign, and move them onto the nearest region.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_bbox_contains` | 20 | private | bool | No | Point-in-bbox test |
| `_bbox_center` | 25 | private | Point | No | Center of a bbox |
| `overlay_anchor_stranded` | 30 | public | bool | No | True when the anchor lies outside every region's bbox |
| `nearest_region_center` | 36 | public | `Optional[Point]` | No | Bbox center of the region nearest a point |
| `reposition_stranded_overlays` | 52 | public | int | No | Move every stranded anchor to the nearest region center; returns the count moved |

---

### text_path
**Path**: `core/layout/text_path.py` - 66 lines
**Purpose**: Pure math for text-on-a-curve overlays — validate the single-quadratic baseline contract, seed a default arch, and compute per-glyph arc-length offsets (the Qt renderer maps them onto the painter path).
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `validate_text_path` | 15 | public | `List[str]` | No | Problems with an overlay text path; `[]` means valid (v1: exactly one `move` + one `quad`) |
| `default_text_path` | 29 | public | `List[PathSegment]` | No | Seed a gentle upward arch centered on an anchor (`peak_px` defaults to 12% of the chord) |
| `glyph_offsets` | 46 | public | `List[float]` | No | Arc-length position of each glyph's advance midpoint, honoring alignment and letter spacing |

---

### geometry
**Path**: `core/layout/geometry.py` - 63 lines
**Purpose**: Pure geometry helpers for path-based regions (no Qt) — segment validation, bounding boxes, and translation.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_EXPECTED_PTS` | 9 | constant | Required point count per segment type |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `validate_segments` | 12 | public | `List[str]` | No | Problem descriptions for a segment list; empty means valid |
| `segments_bbox` | 35 | public | `Tuple[float, float, float, float]` | No | Bounding box over all points (control points included — a safe superset for curves) |
| `translate_segments` | 53 | public | `List[PathSegment]` | No | New segments offset by (dx, dy); used to persist whole-panel drags |

---

### history
**Path**: `core/layout/history.py` - 61 lines
**Purpose**: Iteration history for the layout designer — append, browse, branch, and restore document snapshots stored on the `DocumentSpec`.
**Language**: Python

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `History` | 10 | Append/browse/restore layout snapshots stored on a `DocumentSpec` |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 13 | constructor | None | No | Bind a document and reset the current-branch pointer |
| `snapshots` | 21 | public | `List[Snapshot]` | No | The document's snapshot timeline |
| `get` | 24 | public | `Optional[Snapshot]` | No | Look up a snapshot by id |
| `append` | 30 | public | Snapshot | No | Serialize the document (history stripped) as a new snapshot parented to the current branch point |
| `branch_from` | 50 | public | None | No | Record the snapshot a restore branched from, so the next append parents to it |
| `restore` | 55 | public | DocumentSpec | No | Rebuild a document from a snapshot while keeping the existing timeline |

---

### page_sizes
**Path**: `core/layout/page_sizes.py` - 53 lines
**Purpose**: Page-size presets (Letter, Legal, Tabloid, A4, A5, US Comic, …), unit conversion, size-text parsing, and persistence of user-defined custom sizes.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_INCHES_PER` | 7 | constant | Unit → inches conversion factors (`px` is special-cased) |
| `PRESETS` | 10 | constant | Built-in page-size presets |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `to_inches` | 23 | public | float | No | Convert a value from in/mm/pt to inches (raises for `px`) |
| `preset_to_page_size` | 30 | public | PageSize | No | Preset dict + orientation + DPI → `PageSize` |
| `parse_size_text` | 35 | public | `Optional[Tuple[float, float]]` | No | Parse `"8.5 x 11"`-style text into (width, height) |
| `load_custom_sizes` | 42 | public | `List[Dict]` | No | Read custom page sizes from the layout config |
| `save_custom_size` | 46 | public | None | No | Upsert a custom page size by name and persist the config |

---

### project_io
**Path**: `core/layout/project_io.py` - 51 lines
**Purpose**: Project persistence — `.iaiproj.json` save/load with legacy `.layout.json` migration and cross-machine image-reference repair.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `save_project` | 12 | public | None | No | Serialize a `DocumentSpec` to indented JSON |
| `_resolve_image_refs` | 17 | private | None | No | Rewrite absolute image refs that don't resolve on this machine (e.g. WSL paths opened from Windows) |
| `load_project` | 47 | public | DocumentSpec | No | Load a project file and repair its image references |

---

### fill_plan
**Path**: `core/layout/fill_plan.py` - 39 lines
**Purpose**: Pure sequencing state for the layout → Image-tab handoff: an ordered list of region payloads with a cursor. "Send to Image" is a one-element plan; "Fill all regions" is a many-element plan.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `FillPlan` | 13 | @dataclass | payloads, index |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `current` | 17 | public | `Optional[Dict]` | No | Payload at the cursor, or None |
| `current_region_id` | 22 | public | `Optional[str]` | No | Region id at the cursor |
| `advance` | 26 | public | `Optional[Dict]` | No | Move to the next region; None when the plan is done |
| `done` | 31 | public | bool | No | Whether the cursor has run past the end |
| `progress` | 34 | public | `Tuple[int, int]` | No | (1-based position, total); (0, 0) when empty |

---

### template_io
**Path**: `core/layout/template_io.py` - 22 lines
**Purpose**: Layout-template export/import — a shareable document that keeps structure and style but strips all content and history.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `export_template` | 9 | public | None | No | Serialize a document with text, image refs, and history stripped |
| `import_template` | 20 | public | DocumentSpec | No | Load a template file back into a `DocumentSpec` |

---

### styles/store (StyleStore)
**Path**: `core/styles/store.py` - 325 lines
**Purpose**: Persistence for Custom Styles — a `styles.json` index plus per-style directories of copied, downscaled reference images, with hardened zip export/import.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `MAX_IMPORT_DIM` | 21 | constant | Max pixel dimension for imported reference images |
| `JPEG_QUALITY` | 22 | constant | Re-encode quality for copied references |
| `EXEMPLAR_DEFAULT_CAP` | 23 | constant | Default cap on starred exemplars |
| `MAX_IMPORT_BYTES` | 24 | constant | Size ceiling guarding zip import |
| `_SAFE_REL` | 27 | constant | Regex for safe `refs/<basename>` entries |
| `_SAFE_ID` | 28 | constant | Regex for safe style ids |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `StyleStore` | 45 | CRUD + reference-image management for styles (shaped like `PresetLoader`) |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 48 | constructor | None | No | Base dir defaults to `get_user_data_dir()/"styles"` |
| `_read_index` | 57 | private | `List[dict]` | No | Read `styles.json` records |
| `_write_index` | 67 | private | None | No | Write `styles.json` records |
| `list_styles` | 80 | public | `List[Style]` | No | All stored styles |
| `get` | 94 | public | `Optional[Style]` | No | Look up by id |
| `get_by_name` | 100 | public | `Optional[Style]` | No | Match by display name or id, case-insensitively |
| `new_id` | 108 | public | str | No | Generate a collision-free id from a name |
| `save` | 118 | public | None | No | Upsert a style into the index |
| `delete` | 130 | public | bool | No | Remove a style and its directory |
| `style_dir` | 148 | public | Path | No | On-disk directory for a style id |
| `add_reference_images` | 153 | public | `List[str]` | No | Copy images into `<style>/refs/` downscaled to JPEG; returns the new relative paths |
| `remove_reference_image` | 190 | public | None | No | Drop one reference (and its exemplar entry) |
| `resolve_refs` | 201 | public | `List[Path]` | No | Absolute paths of existing references, in stored order |
| `export_zip` | 219 | public | bool | No | Write a shareable zip: `style.json` + `refs/*` |
| `import_zip` | 236 | public | `Optional[Style]` | No | Import a style zip with a fresh id on collision; only members referenced by the sanitized reference list are extracted |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `is_safe_rel` | 31 | public | bool | No | True only for `refs/<plain-basename>` — no separators, no traversal (also used by the Style Manager UI) |

---

### styles/analyzer
**Path**: `core/styles/analyzer.py` - 279 lines
**Purpose**: Derive a reusable style from N reference images via a map-reduce over vision-LLM calls: chunk → per-chunk descriptor → merged descriptor + flattened `prompt_text`. Transports are injected so tests, GUI, and CLI share one code path.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `ANALYZE_CHUNK_SIZE` | 20 | constant | Images per vision call |
| `MAX_LLM_IMAGE_DIM` | 21 | constant | Downscale ceiling before base64 encoding |
| `_JSON_SHAPE` | 23 | constant | Expected descriptor JSON shape |
| `CHUNK_PROMPT` | 25 | constant | Per-chunk extraction prompt (style, not content) |
| `MERGE_PROMPT` | 46 | constant | Reduce prompt that fuses chunk descriptors |
| `_PROVIDER_SPECS` | 198 | constant | Per-provider config/model defaults for the real transport |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `StyleAnalysisError` | 63 | Style derivation failed; the message is user-facing |
| `StyleAnalysisService` | 266 | Real-transport wrapper that derives a style from image paths |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `StyleAnalysisService.__init__` | 269 | constructor | None | No | Bind config, provider, and model |
| `StyleAnalysisService.derive` | 273 | public | Dict | No | Run the map-reduce; map (vision) and reduce (text) share one `UnifiedLLMProvider` callable |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `chunk_paths` | 67 | public | `List[List[Path]]` | No | Split image paths into per-call chunks |
| `encode_image_for_llm` | 72 | public | `Tuple[str, str]` | No | Downscale and return (mime, base64) |
| `build_chunk_messages` | 83 | public | `List[Dict]` | No | One user message: prompt + each image as a data-URI part |
| `parse_descriptor` | 93 | public | `Optional[Dict[str, str]]` | No | Parse an LLM reply into a filtered/defaulted descriptor dict |
| `flatten_descriptor` | 102 | public | str | No | Deterministic `prompt_text` from summary + non-empty fields (negatives excluded) |
| `merge_descriptors` | 114 | public | `Dict[str, str]` | No | Reduce chunk descriptors to one; single chunk flattens without an LLM call |
| `derive_style_data` | 147 | public | Dict | No | Full map-reduce → `{"descriptor": {...}, "prompt_text": str}` |
| `derive_style_data.emit` | 157 | nested | None | No | Progress-callback shim |
| `normalize_llm_provider` | 206 | public | str | No | Canonicalize a provider name to openai/anthropic/google |
| `default_vision_model` | 215 | public | str | No | Registry-resolved default vision model for a provider |
| `build_completion_fn` | 221 | public | Callable | No | Build an LLM callable over `UnifiedLLMProvider` with retries |
| `build_completion_fn.fn` | 254 | nested | str | No | The returned completion closure |

---

### styles/applicator
**Path**: `core/styles/applicator.py` - 179 lines
**Purpose**: Apply a saved style to a generation request across all four seams (GUI image gen, CLI image gen, video scenes, layout fill). Plain concatenation by default; opt-in "smart merge" via an LLM that can never fail a generation.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `GOOGLE_REF_LIMITS` | 21 | constant | Per-model Google reference-image caps |
| `GOOGLE_DEFAULT_REF_LIMIT` | 26 | constant | Fallback Google cap |
| `OPENAI_REF_LIMIT` | 27 | constant | OpenAI reference-image cap |
| `_OPENAI_IMAGE_MODEL_PREFIXES` | 28 | constant | Model-id prefixes treated as OpenAI image models |
| `SMART_MERGE_PROMPT` | 30 | constant | Prompt used to fuse a user prompt with a style descriptor |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `StyledRequest` | 49 | @dataclass | prompt, extra_kwargs, meta |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `style_ref_limit` | 55 | public | int | No | How many total reference images a provider/model accepts (0 = none) |
| `_plain_apply` | 68 | private | str | No | Prefix/suffix concatenation of the style's `prompt_text` |
| `_smart_merge` | 77 | private | `Optional[str]` | No | One LLM call fusing prompt + descriptor; None on any failure |
| `apply_style` | 102 | public | StyledRequest | No | Apply a style for a provider/model; merges exemplars into `reference_images` (user refs first) within the cap |
| `apply_style_for_surface` | 151 | public | tuple | No | Convenience seam for GUI/CLI surfaces; builds the smart-merge completion from config; `style=None` is a no-op |

---

### styles/models
**Path**: `core/styles/models.py` - 80 lines
**Purpose**: Dataclasses for the Custom Styles feature — an AI-derived structured descriptor plus a user-editable flattened prompt and copied reference images with a starred exemplar subset.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `DESCRIPTOR_KEYS` | 10 | constant | The nine descriptor fields (summary, medium, palette, lighting, composition, texture, line_work, mood, negative) |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `StyleDescriptor` | 17 | @dataclass | summary, medium, palette, lighting, composition, texture, line_work, mood, negative |
| `Style` | 38 | @dataclass | id, name, description, descriptor, prompt_text, placement, reference_images, exemplars, source, version, is_builtin |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `StyleDescriptor.to_dict` | 28 | public | `Dict[str, str]` | No | Serialize the nine descriptor keys |
| `@classmethod StyleDescriptor.from_dict` | 32 | class | StyleDescriptor | No | Build from a dict, coercing every key to str |
| `Style.to_dict` | 51 | public | Dict | No | Serialize the full style record |
| `@classmethod Style.from_dict` | 67 | class | Style | No | Build a style from a stored record |

---

### styles package init
**Path**: `core/styles/__init__.py` - 10 lines
**Purpose**: Public facade for Custom Styles — re-exports `DESCRIPTOR_KEYS`, `Style`, `StyleDescriptor`, `StyleStore`, `StyleAnalysisError`, `StyledRequest`, `apply_style`, `apply_style_for_surface`, and `style_ref_limit`.
**Language**: Python

*(No classes or functions defined here — imports and `__all__` only.)*

---

### reference/image_compositor
**Path**: `core/reference/image_compositor.py` - 264 lines
**Purpose**: Composite multiple reference images into one square "character design sheet" canvas, for models that limit how many people/characters a single reference can carry.
**Language**: Python

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `ReferenceImageCompositor` | 17 | Composites several reference images onto a square canvas with grid/horizontal/vertical arrangements |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 29 | constructor | None | No | Set the square canvas size |
| `composite_images` | 39 | public | `Optional[Path]` | No | Composite the images and save the sheet |
| `_arrange_grid` | 116 | private | None | No | Grid arrangement |
| `_arrange_horizontal` | 159 | private | None | No | Side-by-side arrangement |
| `_arrange_vertical` | 188 | private | None | No | Stacked arrangement |
| `_resize_to_fit` | 217 | private | `Image.Image` | No | Proportional resize within max dimensions (never cropped or distorted) |
| `@staticmethod generate_composite_prompt` | 242 | static | str | No | Append arrangement instructions to the user's description |

---

### reference/imagen_reference
**Path**: `core/reference/imagen_reference.py` - 253 lines
**Purpose**: Data models for Google Imagen 3 customization reference images — reference/subject/control enums, the `ImagenReference` record with validation and serialization, and list-level validation/ID assignment.
**Language**: Python

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `ImagenReferenceType` | 17 | Enum: SUBJECT, STYLE, CONTROL, RAW, MASK |
| `ImagenSubjectType` | 26 | Enum: PERSON, ANIMAL, PRODUCT, DEFAULT |
| `ImagenControlType` | 34 | Enum: FACE_MESH, CANNY, SCRIBBLE |
| `ImagenReference` | 42 | Dataclass: one reference image plus its Imagen 3 metadata |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__post_init__` | 71 | dunder | None | No | Validate the reference's type/subtype combination after construction |
| `load_image_data` | 102 | public | bytes | No | Read the image file (raises `FileNotFoundError` / `IOError`) |
| `get_display_name` | 124 | public | str | No | Friendly label combining file name and description |
| `to_dict` | 136 | public | `Dict[str, Any]` | No | Serialize for persistence |
| `@classmethod from_dict` | 160 | class | ImagenReference | No | Rebuild from a serialized dict |
| `__repr__` | 192 | dunder | str | No | Debug representation |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `validate_references` | 200 | public | `tuple[bool, list[str]]` | No | Validate a reference list for API submission; returns (is_valid, errors) |
| `auto_assign_reference_ids` | 243 | public | None | No | Assign sequential reference IDs in place |

---

### reference package init
**Path**: `core/reference/__init__.py` - 22 lines
**Purpose**: Package facade for Imagen 3 reference-image management — re-exports `ImagenReferenceType`, `ImagenSubjectType`, `ImagenControlType`, `ImagenReference`, and `validate_references`.
**Language**: Python

*(No classes or functions defined here — imports and `__all__` only.)*

---

### model_registry/client
**Path**: `core/model_registry/client.py` - 220 lines
**Purpose**: Vendored ChameleonLabs model-registry client (stdlib only). Resolves current LLM model IDs and pricing from a published registry JSON so nothing hardcodes IDs that go stale. Fetch ladder: TTL cache → live fetch → stale cache → bundled fallback → `RegistryError`.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `DEFAULT_URL` | 32 | constant | Public registry URL (overridable via `MODEL_REGISTRY_URL`) |
| `DEFAULT_PRICING_URL` | 33 | constant | Public token-pricing document URL |
| `DEFAULT_TTL_SECONDS` | 36 | constant | In-memory cache lifetime |
| `FETCH_TIMEOUT_SECONDS` | 37 | constant | HTTP timeout |
| `MIN_SCHEMA_VERSION` | 38 | constant | Minimum accepted registry schema version |

#### Classes
| Class | Line | Description |
|-------|------|-------------|
| `RegistryError` | 44 | Raised when the registry cannot be fetched and no fallback is available |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_default_fetch` | 48 | private | str | No | urllib GET with timeout (injectable test seam) |
| `_is_valid` | 55 | private | bool | No | Schema-version/shape check for a registry document |
| `clear_cache` | 68 | public | None | No | Drop the in-memory cache (test seam) |
| `_get_json` | 73 | private | dict | No | Shared fetch ladder: TTL cache → fetch → stale cache → fallback file → raise |
| `get_registry` | 105 | public | dict | No | Parsed registry dict, fetched at most once per TTL |
| `resolve` | 129 | public | str | No | Resolve (provider, family) to the current model ID; `channel` may be active/stable/preview |
| `context_window` | 153 | public | `Optional[int]` | No | A model's context window in tokens, or None |
| `available` | 159 | public | `list[str]` | No | Full curated model-ID list for a provider |
| `_is_valid_pricing` | 165 | private | bool | No | Shape check for the pricing document |
| `get_pricing` | 173 | public | dict | No | Parsed token-pricing document (daily scrape of official pricing pages) |
| `pricing_rows` | 203 | public | `list[dict]` | No | Flatten a provider's pricing tables into rows tagged with their `section` |

---

### model_registry package init
**Path**: `core/model_registry/__init__.py` - 63 lines
**Purpose**: Project wrapper around the vendored client — every call auto-defaults `fallback_path` to the snapshot bundled at `core/model-registry.fallback.json`, so resolution never raises even fully offline. **Use these helpers instead of hardcoding `claude-*`/`gpt-*`/`gemini-*` IDs** (AGENTS.md §8).
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `FALLBACK_PATH` | 39 | constant | Absolute path to the bundled `core/model-registry.fallback.json` snapshot |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `resolve` | 42 | public | str | No | Resolve (provider, family) to the current model ID, bundled fallback wired |
| `get_registry` | 48 | public | dict | No | Parsed registry dict, bundled fallback wired |
| `context_window` | 54 | public | `Optional[int]` | No | Model context window in tokens, bundled fallback wired |
| `available` | 60 | public | `list[str]` | No | Curated model-ID list for a provider, bundled fallback wired |

---

## Font Generator (Core + GUI)

The font generator turns a scanned/hand-drawn alphabet image into a real TTF/OTF
typeface. The pipeline is: **segment** the image into character cells →
optionally **identify/generate** glyphs with AI → **vectorize** the bitmaps into
Bezier outlines → **calculate metrics** (baseline, x-height, cap-height, kerning)
→ **build** the font file. `core/font_generator/` holds the pipeline;
`gui/font_generator/` wraps it in a five-page `QWizard`.

```
   alphabet image
        │
        ▼
┌──────────────────────┐   ┌──────────────────────┐
│ row_detector.py      │──►│ row_column_segmenter │
│ (horizontal rows)    │   │ (rows → columns)     │
└──────────────────────┘   └──────────┬───────────┘
                                      ▼
                       ┌──────────────────────────┐    ┌─────────────────────┐
                       │ segmentation.py          │◄──►│ glyph_identifier.py │
                       │ AlphabetSegmenter        │    │ (AI vision labels)  │
                       │ → SegmentationResult     │    └─────────────────────┘
                       └──────────┬───────────────┘    ┌─────────────────────┐
                                  │                    │ glyph_generator.py  │
                                  │◄───────────────────│ (AI fills missing)  │
                                  ▼                    └─────────────────────┘
                       ┌──────────────────────────┐
                       │ vectorizer.py            │
                       │ → VectorGlyph paths      │
                       └──────────┬───────────────┘
                                  ▼
                       ┌──────────────────────────┐
                       │ metrics.py               │
                       │ → FontMetrics + kerning  │
                       └──────────┬───────────────┘
                                  ▼
                       ┌──────────────────────────┐
                       │ font_builder.py (fontTools)
                       │ → .ttf / .otf            │
                       └──────────────────────────┘
                                  ▲
                       gui/font_generator/font_wizard.py
                       (5-page QWizard drives all of the above)
```

---

### Font Generator Package Init
**Path**: `core/font_generator/__init__.py` - 106 lines
**Purpose**: Public API surface for the font-generator pipeline. Re-exports the
segmentation, vectorization, metrics, font-building, AI-identification and
AI-generation types, plus the standard character-set constants, and documents the
five-step workflow in its module docstring.
**Language**: Python

#### Re-exported Symbols (`__all__`)
| Group | Names |
|-------|-------|
| Segmentation | `AlphabetSegmenter`, `CharacterCell`, `SegmentationResult`, `SegmentationMethod` |
| Character sets | `UPPERCASE`, `LOWERCASE`, `DIGITS`, `PUNCTUATION`, `FULL_ALPHABET` |
| Vectorization | `GlyphVectorizer`, `VectorGlyph`, `VectorPath`, `PathSegment`, `PathCommand`, `SmoothingLevel`, `glyphs_to_svg_font` |
| Metrics | `FontMetrics`, `FontMetricsCalculator` |
| Font building | `FontBuilder`, `FontInfo`, `create_font_from_glyphs`, `FONTTOOLS_AVAILABLE` |
| AI identification | `AIGlyphIdentifier`, `GlyphIdentificationResult`, `BatchIdentificationResult`, `get_position_hint` |
| AI generation | `GlyphGenerator`, `GlyphGenerationResult` |
| Row/column segmentation | `RowDetector`, `TextRow`, `CharacterColumn`, `RowColumnSegmenter` |

---

### Character Segmentation
**Path**: `core/font_generator/segmentation.py` - 1392 lines
**Purpose**: Detects and isolates individual characters from an alphabet image.
Supports grid-based (uniform layouts), contour-based (hand-drawn/irregular), and
row-column segmentation, with auto-detection of the best method, automatic
inversion detection, merging of multi-part glyphs (`i`/`j` dots), splitting of
touching characters (projection analysis or AI), and punctuation-vs-noise
discrimination.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| SegmentationMethod | 21 | Enum | GRID, CONTOUR, AUTO, ROW_COLUMN |
| CharacterCell | 30 | @dataclass | label, bbox, image, confidence, row, col |
| SegmentationResult | 76 | @dataclass | characters, method, grid_size, image_size, warnings |

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| UPPERCASE | 108 | constant | `"ABCDEFGHIJKLMNOPQRSTUVWXYZ"` |
| LOWERCASE | 109 | constant | `"abcdefghijklmnopqrstuvwxyz"` |
| DIGITS | 110 | constant | `"0123456789"` |
| PUNCTUATION | 112 | constant | Extended punctuation set for handwriting samples |
| FULL_ALPHABET | 113 | constant | Uppercase + lowercase + digits + punctuation |

#### Class: CharacterCell (line 30)
A single segmented character: its label, bounding box in the source image, the
cropped pixel data, a confidence score, and grid row/col indices.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property x | 50 | property | int | No | Bounding-box left edge |
| @property y | 54 | property | int | No | Bounding-box top edge |
| @property width | 58 | property | int | No | Bounding-box width |
| @property height | 62 | property | int | No | Bounding-box height |
| to_pil | 65 | public | Image.Image | No | Convert the numpy cell to a PIL image (L/RGB/RGBA) |

#### Class: SegmentationResult (line 76)
Container for the segmented characters plus the method used, detected grid size,
source image size, and any warnings raised during segmentation.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| get_character | 94 | public | Optional[CharacterCell] | No | Look up a segmented cell by its label |
| get_missing_characters | 101 | public | List[str] | No | Expected characters that were not found |

#### Class: AlphabetSegmenter (line 116)
Main segmentation engine. Loads the image, binarizes it, picks (or is told) a
method, and produces a `SegmentationResult`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 125 | constructor | None | No | Configure method, expected chars, min sizes, padding, threshold, inversion, small-glyph handling, AI assist |
| @staticmethod detect_needs_inversion | 162 | static | bool | No | Decide whether the image is light-on-dark and needs inverting |
| @staticmethod detect_character_set | 227 | static | Tuple[str, str] | No | Guess the character set (and a description) from the detected glyph count |
| @staticmethod validate_character_count | 260 | static | List[str] | No | Warn when detected count differs from the expected set |
| segment_auto_detect | 301 | public | Tuple[SegmentationResult, str, str] | No | Segment, then infer the character set from the number of glyphs found |
| segment | 391 | public | SegmentationResult | No | Main entry point: segment an image with the configured/auto method |
| _segment_row_column | 431 | private | SegmentationResult | No | Delegate to `RowColumnSegmenter` (rows then columns) |
| _load_image | 450 | private | np.ndarray | No | Accept path / PIL image / ndarray and normalize to ndarray |
| _to_grayscale | 470 | private | np.ndarray | No | Grayscale conversion |
| _binarize | 487 | private | np.ndarray | No | Gaussian blur + threshold to binary |
| _detect_best_method | 507 | private | SegmentationMethod | No | Choose grid vs contour from image analysis |
| _segment_grid | 547 | private | SegmentationResult | No | Uniform-grid segmentation |
| _segment_contour | 603 | private | SegmentationResult | No | Contour-based segmentation for irregular layouts |
| _sort_bboxes_reading_order | 746 | private | List[tuple] | No | Sort boxes top-to-bottom, left-to-right |
| _merge_component_bboxes | 782 | private | List[tuple] | No | Rejoin split components (e.g. the dot of `i`/`j`) using overlap + size + vertical-separation rules |
| _split_wide_bboxes | 921 | private | List[tuple] | No | Split abnormally wide boxes containing touching characters |
| _find_split_points_ai | 999 | private | Optional[List[int]] | No | Ask `AIGlyphIdentifier` where to split a wide region |
| _find_split_points | 1044 | private | List[int] | No | Vertical-projection fallback for split points |
| _apply_splits | 1115 | private | List[tuple] | No | Materialize new bounding boxes/contours from split x-coordinates |
| _is_likely_punctuation | 1160 | private | bool | No | Shape analysis to keep punctuation and reject noise |
| _detect_grid_size | 1236 | private | Tuple[int, int] | No | Auto-detect rows/cols from projection gaps (nested helper `count_groups` at line 1252) |
| _extract_cell | 1279 | private | np.ndarray | No | Tight crop of a character using its own contour bbox |
| preview_segmentation | 1348 | public | np.ndarray | No | Render an annotated preview with boxes and labels |

---

### AI Glyph Identifier
**Path**: `core/font_generator/glyph_identifier.py` - 946 lines
**Purpose**: Uses AI vision models to label glyph images that contour analysis
cannot resolve (punctuation, ambiguous marks) and to advise on splitting wide
regions. Supports Anthropic Claude (preferred for accuracy) and Google Gemini
(fast fallback, optionally via Application Default Credentials), with single,
multiple and batched-composite identification modes.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| GlyphIdentificationResult | 28 | @dataclass | identified_char, confidence, alternatives, error |
| BatchIdentificationResult | 37 | @dataclass | identifications, total_glyphs, successful_count, error |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_position_hint | 45 | public | str | No | Map a glyph's y-offset/height within its row to `"top"`, `"middle"`, `"bottom"` or `"full"` — disambiguates marks like `'` vs `,` |

#### Class: AIGlyphIdentifier (line 76)
Vision-model wrapper for glyph recognition. Lazily creates the provider client,
builds prompts that include the expected character set and a vertical position
hint, and parses (often Markdown-fenced) model responses.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 127 | constructor | None | No | Select provider (`anthropic`/`gemini`), API key, model, cloud-auth flag |
| _ensure_client | 157 | private | None | No | Dispatch to the provider-specific client initializer |
| _ensure_anthropic_client | 164 | private | None | No | Lazily construct the Anthropic client |
| _ensure_gemini_client | 206 | private | None | No | Lazily construct the Gemini client (API key or ADC) |
| identify_glyph | 264 | public | GlyphIdentificationResult | No | Identify one glyph image with context chars + position hint |
| _identify_glyph_anthropic | 309 | private | GlyphIdentificationResult | No | Claude vision call |
| _identify_glyph_gemini | 383 | private | GlyphIdentificationResult | No | Gemini vision call |
| identify_multiple_glyphs | 438 | public | List[GlyphIdentificationResult] | No | Identify a list of (image, label[, position_hint]) tuples |
| _build_identification_prompt | 473 | private | str | No | Compose the single-glyph prompt |
| _parse_response | 519 | private | GlyphIdentificationResult | No | Parse a single-glyph model response |
| analyze_region_for_splitting | 559 | public | Tuple[int, List[float]] | No | Ask the model how many characters a wide region holds and where to split (ratios) |
| _parse_split_response | 651 | private | Tuple[int, List[float]] | No | Parse the split-analysis response |
| count_characters_in_image | 683 | public | int | No | Estimate total character count in a full handwriting sample |
| batch_identify | 745 | public | BatchIdentificationResult | No | Identify many glyphs using few requests (`max_per_request` chunking) |
| _identify_batch | 794 | private | List[GlyphIdentificationResult] | No | One API call for a chunk of glyph images |
| _create_numbered_composite | 835 | private | Image.Image | No | Tile glyphs into a numbered grid image for batch prompts |
| _build_batch_prompt | 874 | private | str | No | Compose the batch prompt |
| _parse_batch_response | 901 | private | List[GlyphIdentificationResult] | No | Parse numbered batch results, padding to the expected count |

---

### Glyph Vectorizer
**Path**: `core/font_generator/vectorizer.py` - 687 lines
**Purpose**: Converts segmented bitmap characters into smooth vector outlines
suitable for font construction. Uses OpenCV contour detection with hierarchy
(so counters/holes in `O`, `A`, `B` are preserved), corner detection, and cubic
Bezier fitting, flipping to Y-up font coordinates and optionally normalizing all
glyphs to a common em height.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| PathCommand | 22 | Enum | MOVE `M`, LINE `L`, CURVE `C`, QUAD `Q`, CLOSE `Z` |
| PathSegment | 32 | @dataclass | command, points |
| VectorPath | 46 | @dataclass | segments, is_hole |
| VectorGlyph | 69 | @dataclass | label, paths, width, height, advance_width |
| SmoothingLevel | 105 | Enum | NONE, LOW, MEDIUM, HIGH, MAXIMUM |

#### Class: PathSegment (line 32)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_svg | 37 | public | str | No | Render this segment as SVG path-data text |

#### Class: VectorPath (line 46)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_svg_d | 51 | public | str | No | Concatenate segments into an SVG `d` attribute |
| @property bounds | 56 | property | Tuple[float, float, float, float] | No | (min_x, min_y, max_x, max_y) of the contour |

#### Class: VectorGlyph (line 69)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| to_svg | 77 | public | str | No | Complete SVG element for the glyph at a given scale |
| @property bounds | 92 | property | Tuple[float, float, float, float] | No | Combined bounds across all paths |

#### Class: GlyphVectorizer (line 114)
Bitmap→vector engine. A class-level `SMOOTHING_PARAMS` table maps each
`SmoothingLevel` to epsilon/corner-threshold/blur/morphology settings.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 158 | constructor | None | No | Set smoothing level, min contour area, Bezier vs polyline, normalization height, detail preservation |
| vectorize | 188 | public | VectorGlyph | No | Convert one character image into a labeled `VectorGlyph` |
| _prepare_binary | 244 | private | np.ndarray | No | Blur/threshold/morphology preprocessing for smooth edges |
| _process_contours | 285 | private | List[VectorPath] | No | Walk the contour hierarchy, marking inner contours as holes |
| _contour_to_path | 323 | private | VectorPath | No | Contour → path, flipping Y into font space |
| _points_to_polyline | 365 | private | List[PathSegment] | No | Straight-line fallback path |
| _fit_bezier_path | 381 | private | List[PathSegment] | No | Fit smooth cubic curves through a contour |
| _detect_corners | 408 | private | List[int] | No | Find sharp direction changes to keep as corners |
| _angle_between | 432 | private | float | No | Angle at a vertex between two adjacent edges |
| _fit_bezier_segment | 453 | private | List[PathSegment] | No | Fit cubic Beziers to one smooth run of points |
| _resample_points | 504 | private | List[tuple] | No | Even-spacing resample before fitting |
| _calculate_tangents | 543 | private | List[tuple] | No | Unit tangents per point for continuity |
| _calculate_control_points | 574 | private | Tuple[tuple, tuple] | No | Control points for a 4-point cubic fit |
| _normalize_glyph | 597 | private | VectorGlyph | No | Scale a glyph to the configured standard height |
| vectorize_all | 620 | public | List[VectorGlyph] | No | Vectorize every `CharacterCell` from segmentation |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| glyphs_to_svg_font | 642 | public | str | No | Emit a (deprecated but handy for preview) SVG font from vector glyphs |

---

### Font Builder
**Path**: `core/font_generator/font_builder.py` - 599 lines
**Purpose**: Assembles vectorized glyphs plus calculated metrics into real font
files via fontTools — TrueType (`.ttf`, quadratic outlines) or CFF-based
OpenType (`.otf`, cubic charstrings) — including `.notdef`, name/OS-2/head
tables, and an optional kerning table.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| FONTTOOLS_AVAILABLE | 19 | constant | `True` when the fontTools import succeeds |
| FONTTOOLS_AVAILABLE | 21 | constant | `False` fallback in the `except ImportError` branch |
| CU2QU_AVAILABLE | 26 | constant | `True` when `cu2qu` (cubic→quadratic) is importable |
| CU2QU_AVAILABLE | 28 | constant | `False` fallback in the `except ImportError` branch |
| _FONT_EPOCH | 36 | constant | `datetime(1904, 1, 1)` — the font timestamp epoch |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| _datetime_to_font_timestamp | 39 | private | int | No | Seconds since 1904-01-01 for `head` table dates |
| create_font_from_glyphs | 578 | public | Path | No | Convenience wrapper: glyphs + name + kwargs → built font file |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| FontInfo | 45 | @dataclass | family_name, style_name, version, copyright, designer, description, vendor_url, designer_url, license, license_url |

#### Class: FontInfo (line 45)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property full_name | 59 | property | str | No | "Family Style" display name |
| @property postscript_name | 63 | property | str | No | PostScript-safe name |
| @property unique_id | 67 | property | str | No | Unique font identifier string |

#### Class: FontBuilder (line 71)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 78 | constructor | None | No | Store `FontInfo` and (optional pre-calculated) `FontMetrics` |
| add_glyph | 100 | public | None | No | Append one `VectorGlyph` |
| add_glyphs | 105 | public | None | No | Append many `VectorGlyph`s |
| build | 110 | public | Path | No | Compute metrics if needed and write `.ttf` or `.otf` by extension |
| _build_truetype | 156 | private | TTFont | No | Assemble a TrueType font (glyf/loca, name, OS/2, hhea, head) |
| _build_cff | 255 | private | TTFont | No | Assemble a CFF/OpenType font from charstrings |
| _draw_empty_tt | 347 | private | Glyph | No | Empty TrueType glyph (e.g. space) |
| _draw_notdef_tt | 353 | private | Glyph | No | `.notdef` box glyph for TrueType |
| _draw_glyph_tt | 379 | private | Glyph | No | Draw a `VectorGlyph` through `TTGlyphPen` |
| _cubic_to_quadratic | 405 | private | List[tuple] | No | Approximate a cubic Bezier with quadratics within `max_err` |
| _draw_path_to_pen_tt | 449 | private | None | No | Replay a path onto a TrueType pen, converting curves |
| _glyph_to_charstring | 484 | private | T2CharString | No | Convert a `VectorGlyph` to a CFF charstring |
| _draw_path_to_pen | 493 | private | None | No | Replay a path onto a generic (CFF) pen |
| _create_notdef_charstring | 519 | private | T2CharString | No | `.notdef` charstring for CFF |
| _add_kerning | 543 | private | None | No | Write the kern table from the metrics' kerning pairs |

---

### Font Metrics Calculator
**Path**: `core/font_generator/metrics.py` - 563 lines
**Purpose**: Analyzes vectorized glyphs to derive font metrics — baseline,
x-height, cap-height, ascender, descender, advance widths and per-glyph bounding
boxes — normalizes all glyphs into a shared em-based coordinate space (descenders
below the baseline as negative Y), and generates heuristic kerning pairs from
edge-shape analysis.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| UPPERCASE_FLAT | 19 | constant | `"EFHILTZ"` — flat-topped caps used for cap-height |
| UPPERCASE_ROUND | 20 | constant | `"CDGOQS"` — round-topped caps (overshoot allowance) |
| LOWERCASE_XHEIGHT | 21 | constant | `"acemnorsuvwxz"` — x-height reference letters |
| LOWERCASE_ASCENDER | 22 | constant | `"bdfhklt"` — ascender reference letters |
| LOWERCASE_DESCENDER | 23 | constant | `"gjpqy"` — descender reference letters |
| DIGITS | 24 | constant | `"0123456789"` |
| PUNCT_TOP | 28 | constant | Marks hanging at the top (`'"`` ^`) |
| PUNCT_MIDDLE | 30 | constant | Mid-height marks (`- ~ *`) |
| PUNCT_BASELINE | 32 | constant | Baseline-sitting marks (`. _`) |
| PUNCT_DESCENDER | 34 | constant | Marks below the baseline (`,`) |
| PUNCT_PARTIAL_DESCENDER | 36 | constant | Partially descending marks (`;`) |
| PUNCT_FULL | 38 | constant | Full-height symbols (`! ? \| / \\ ( ) [ ] { } @ # $ % & + < > = :`) |
| PUNCT_SUPER | 40 | constant | Superscript marks (`°`) |
| KERNING_PAIRS | 43 | constant | Candidate character pairs evaluated for kerning |

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| FontMetrics | 69 | @dataclass | units_per_em, ascender, descender, cap_height, x_height, baseline, line_gap, advance_widths, kerning, bboxes |

#### Class: FontMetrics (line 69)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property typo_ascender | 97 | property | float | No | OS/2 `sTypoAscender` |
| @property typo_descender | 102 | property | float | No | OS/2 `sTypoDescender` (negative) |
| @property win_ascent | 107 | property | float | No | OS/2 `usWinAscent` (positive) |
| @property win_descent | 112 | property | float | No | OS/2 `usWinDescent` (positive magnitude) |

#### Class: FontMetricsCalculator (line 117)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 125 | constructor | None | No | Set units-per-em, default side bearing %, kerning threshold |
| get_normalized_glyphs | 144 | public | List[VectorGlyph] | No | Glyphs repositioned onto the baseline — call after `calculate()` |
| calculate | 154 | public | FontMetrics | No | Main entry: normalize glyphs and compute all metrics + kerning |
| _normalize_glyphs | 207 | private | List[VectorGlyph] | No | Scale to em space, put baseline at y=0, align descender x-heights |
| _calculate_cap_height | 372 | private | float | No | Cap height from flat-topped uppercase letters |
| _calculate_x_height | 394 | private | float | No | x-height from lowercase reference letters |
| _calculate_ascender | 409 | private | float | No | Ascender from `bdfhklt` (falls back to cap height) |
| _calculate_descender | 428 | private | float | No | Descender depth from `gjpqy` |
| _calculate_kerning | 443 | private | Dict[Tuple[str, str], float] | No | Build kerning pairs from shape heuristics |
| _calculate_kern_value | 473 | private | float | No | Per-pair adjustment (negative = tighter) |
| _analyze_edge | 518 | private | str | No | Classify a glyph edge as straight / diagonal / round / open |

---

### Row-Column Segmenter
**Path**: `core/font_generator/row_column_segmenter.py` - 543 lines
**Purpose**: Alternative segmentation strategy tuned for handwriting samples:
find text rows by horizontal projection, then find whole contours inside each row
(never splitting a glyph), merge multi-part glyphs (`i`/`j` dots, `"`/`:`, and
diagonally overlapping parts of `%`), sort left-to-right, and optionally hand the
extracted cells to the AI identifier for labeling.
**Language**: Python

#### Class: RowColumnSegmenter (line 24)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 27 | constructor | None | No | Expected chars, min char size, padding, inversion, AI-assist flag |
| segment | 42 | public | SegmentationResult | No | Row projection → per-row contours → merge → sort → `CharacterCell`s |
| _identify_with_ai | 190 | private | None | No | Label the extracted glyphs via `AIGlyphIdentifier` |
| _load_image | 243 | private | np.ndarray | No | Normalize path / PIL / ndarray input |
| _to_grayscale | 261 | private | np.ndarray | No | Grayscale conversion |
| _binarize | 269 | private | np.ndarray | No | Threshold to binary (honoring `invert`) |
| _merge_aligned_in_row | 281 | private | List[tuple] | No | Merge horizontally aligned boxes within one row (nested helper `is_narrow` at line 302) |
| _merge_diagonal_components | 453 | private | List[tuple] | No | Union-find merge of horizontally overlapping, vertically separated parts (nested helpers `get_x_range` 470, `horizontal_overlap` 474, `find` 493, `union` 498) |

---

### AI Glyph Generator
**Path**: `core/font_generator/glyph_generator.py` - 530 lines
**Purpose**: Fills gaps in an alphabet by generating missing glyphs with an AI
image model in the style of the detected ones. Picks style-matched reference
glyphs, builds typographic prompts (deliberately omitting pixel dimensions, which
Gemini would render as literal text), post-processes the returned image
(threshold/crop/scale to match existing glyph height), and short-circuits to a
mirror transform where one exists (e.g. `\` from `/`).
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| GlyphGenerationResult | 22 | @dataclass | success, character, cell, error |

#### Class: GlyphGenerator (line 30)
Class-level lookup tables live between the methods below: `SIMILAR_CHARS`
(visual-similarity groups for reference selection, declared inside the class body
starting at line 30), `CHAR_NAMES` (unambiguous symbol names for prompts) and
`MIRROR_PAIRS` (target → source + mirror axis), both declared between
`_select_references` (ends line 308) and `_build_prompt` (line 346).

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 51 | constructor | None | No | Provider, model, API key and auth mode (`api-key` / `gcloud`) |
| _get_provider | 69 | private | Provider | No | Lazy-load the image provider instance |
| generate_glyph | 81 | public | GlyphGenerationResult | No | Generate one character in the reference style (tries mirroring first) |
| _try_mirror_glyph | 176 | private | Optional[GlyphGenerationResult] | No | Build a glyph by flipping an existing one per `MIRROR_PAIRS` |
| _select_references | 254 | private | List[CharacterCell] | No | Pick the best style-reference glyphs for the target character |
| _build_prompt | 346 | private | str | No | Compose the typographic generation prompt (no dimensions in text) |
| _prepare_reference_images | 380 | private | List[bytes] | No | Encode reference cells as PNG bytes for the model |
| _process_image | 403 | private | Optional[np.ndarray] | No | Convert, threshold, crop and scale the generated image to target height |
| generate_multiple | 488 | public | List[GlyphGenerationResult] | No | Generate a batch of characters with a progress callback |

---

### Row Detector
**Path**: `core/font_generator/row_detector.py` - 399 lines
**Purpose**: Detects horizontal text rows in an alphabet image from its
horizontal projection profile, merging fragments (descenders like `g j p q y`
that separate from their row, punctuation slivers) and resolving rows that
overlap. Also segments a row into character columns using gap analysis.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| TextRow | 19 | @dataclass | y, height, baseline |
| CharacterColumn | 32 | @dataclass | x, width, y, height, row_index |

#### Class: TextRow (line 19)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property bottom | 26 | property | int | No | `y + height` |

#### Class: CharacterColumn (line 32)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @property right | 41 | property | int | No | `x + width` |
| @property center_x | 46 | property | int | No | Horizontal center of the column |

#### Class: RowDetector (line 51)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 59 | constructor | None | No | Min row height, gap-threshold ratio, descender ratio |
| detect_rows | 69 | public | List[TextRow] | No | Horizontal projection → row bands with estimated baselines |
| _merge_small_rows | 126 | private | List[TextRow] | No | Fold undersized bands (descender/punctuation fragments) into neighbors |
| _merge_overlapping_rows | 206 | private | List[TextRow] | No | Resolve rows whose descenders bleed into the next row |
| segment_columns | 254 | public | List[CharacterColumn] | No | Split a row into character columns using a small gap threshold |
| _split_wide_columns | 324 | private | List[CharacterColumn] | No | Split unusually wide columns only at clear ink gaps |
| _find_gap_splits | 370 | private | List[int] | No | Locate projection minima below the ink threshold |

---

### Font Generator Wizard (GUI)
**Path**: `gui/font_generator/font_wizard.py` - 2397 lines
**Purpose**: Five-page PySide6 `QWizard` that drives the whole pipeline: upload
an alphabet image, preview/tune segmentation (with optional AI assist and
auto-detected character set), verify and edit character mappings (AI
identification, auto-mirroring, AI generation of missing glyphs on a worker
thread), configure font metadata/smoothing, then preview rendered sample text and
export the `.ttf`/`.otf`. Page state is persisted under the `font_generator`
settings prefix.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| SETTINGS_PREFIX | 51 | constant | `"font_generator"` — QSettings namespace for all wizard pages |

#### Class: ImageUploadPage (line 54) — Wizard page 0
Step 1: choose the alphabet image, preview it scaled to fit, and pick the
expected character set (full / upper+lower / upper+digits / uppercase /
lowercase / custom).

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 59 | constructor | None | No | Initialize page state |
| init_ui | 67 | public | None | No | Build the upload/preview/charset layout |
| browse_image | 148 | public | None | No | File dialog for image selection |
| load_image | 160 | public | None | No | Load and display the chosen image |
| _scale_preview_to_fit | 196 | private | None | No | Proportionally scale the preview (never crop) |
| resizeEvent | 215 | public | None | No | Rescale preview on resize |
| clear_image | 221 | public | None | No | Reset the selection |
| on_charset_changed | 231 | public | None | No | React to character-set combo changes |
| get_expected_chars | 235 | public | str | No | Resolve the combo index (0 full … 5 custom) to a character string |
| isComplete | 260 | public | bool | No | Enable Next only when an image is loaded |
| initializePage | 263 | public | None | No | Restore saved settings on entry |
| save_settings | 280 | public | None | No | Persist page state |
| validatePage | 290 | public | bool | No | Save settings when leaving the page |

#### Class: SegmentationPage (line 296) — Wizard page 1
Step 2: run and preview segmentation, adjust threshold/inversion/method, and
optionally auto-detect the character set or invoke AI-assisted segmentation.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 303 | constructor | None | No | Initialize page state |
| init_ui | 311 | public | None | No | Build controls and the preview canvas |
| initializePage | 413 | public | None | No | Restore settings and run an initial segmentation |
| save_settings | 457 | public | None | No | Persist segmentation settings |
| on_settings_changed | 467 | public | None | No | Invalidate the preview when controls change |
| run_segmentation_auto | 474 | public | None | No | Segment with automatic character-set detection |
| _update_charset_selection | 597 | private | None | No | Push the detected charset back to `ImageUploadPage` |
| run_segmentation | 628 | public | None | No | Segment with the user's explicit settings |
| run_segmentation_with_ai | 712 | public | None | No | Re-run segmentation with AI assistance enabled |
| display_preview | 716 | public | None | No | Show the annotated preview image |
| _scale_preview_to_fit | 726 | private | None | No | Scale the preview pixmap to the available area |
| resizeEvent | 743 | public | None | No | Rescale preview on resize |
| isComplete | 750 | public | bool | No | Enable Next once characters were segmented |

#### Class: GlyphGenerationWorker (line 754)
`QThread` worker that runs `GlyphGenerator.generate_multiple()` off the UI
thread. Signals: `progress(int, int, str)`, `finished(list)`, `error(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 761 | constructor | None | No | Hold generator, target chars, reference glyphs, target height |
| run | 775 | public | None | No | Generate glyphs, emitting progress/finished/error |

#### Class: CharacterMappingPage (line 789) — Wizard page 2
Step 3: review the segmented glyph grid, relabel cells, select glyphs for AI
identification, auto-mirror derivable characters, and generate whatever is still
missing with the AI image model.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 794 | constructor | None | No | Initialize mapping state |
| init_ui | 805 | public | None | No | Build the glyph grid, selection controls and action buttons |
| initializePage | 894 | public | None | No | Populate widgets from the segmentation result |
| _create_missing_char_widget | 972 | private | QWidget | No | Placeholder tile for a character that wasn't found |
| _auto_mirror_glyphs | 1003 | private | None | No | Derive missing glyphs by mirroring existing ones (e.g. `\` from `/`) |
| create_char_widget | 1078 | public | QWidget | No | Selectable tile for one detected character |
| _update_widget_style | 1131 | private | None | No | Restyle a tile for its selection state |
| toggle_char_selection | 1144 | public | None | No | Toggle a glyph's inclusion in AI identification |
| select_all_chars | 1160 | public | None | No | Select every glyph |
| select_no_chars | 1173 | public | None | No | Clear the selection |
| on_label_changed | 1181 | public | None | No | Apply a manual label edit to the cell |
| _refresh_missing_chars | 1202 | private | None | No | Recompute and redisplay the missing-character list |
| generate_missing_glyphs | 1268 | public | None | No | Launch `GlyphGenerationWorker` for the missing characters |
| _on_generation_progress | 1360 | private | None | No | Worker progress → status/progress bar |
| _on_generation_finished | 1377 | private | None | No | Merge generated cells into the segmentation result |
| _on_generation_error | 1413 | private | None | No | Surface and log generation failures |
| identify_with_ai | 1424 | public | None | No | Run AI identification over selected or small/ambiguous glyphs |
| isComplete | 1566 | public | bool | No | Enable Next once mappings are usable |

#### Class: FontSettingsPage (line 1572) — Wizard page 3
Step 4: font metadata (family, style, version, designer, copyright, license) and
vectorization smoothing level.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 1577 | constructor | None | No | Initialize page state |
| init_ui | 1583 | public | None | No | Build metadata fields and the smoothing slider |
| on_smoothing_changed | 1675 | public | None | No | Update the smoothing label |
| get_smoothing_level | 1680 | public | SmoothingLevel | No | Map the slider value to a `SmoothingLevel` |
| get_font_info | 1691 | public | FontInfo | No | Build a `FontInfo` from the form |
| isComplete | 1701 | public | bool | No | Require a font family name |
| initializePage | 1704 | public | None | No | Restore saved metadata |
| save_settings | 1732 | public | None | No | Persist metadata and smoothing |

#### Class: ExportPage (line 1745) — Wizard page 4
Step 5: vectorize all glyphs, build a temporary font for live preview (with a
bitmap fallback when font loading fails), render sample text, and export the
final font file.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 1750 | constructor | None | No | Initialize export state |
| init_ui | 1762 | public | None | No | Build the preview canvas, sample-text field and export controls |
| initializePage | 1825 | public | None | No | Kick off glyph processing when the page opens |
| process_glyphs | 1859 | public | None | No | Vectorize every character and build the preview font |
| _build_preview_font | 1900 | private | None | No | Write a temp font file and register it with Qt's font database |
| update_preview | 1954 | public | None | No | Re-render the sample using the font or the bitmap fallback |
| _render_with_font | 1970 | private | None | No | Render sample text with the loaded font, wrapping lines |
| _render_with_bitmaps | 2039 | private | None | No | Fallback renderer using the original glyph bitmaps (nested helper `get_char_width` at line 2056) |
| _numpy_to_qimage | 2144 | private | Optional[QImage] | No | Convert a grayscale/RGBA numpy array to `QImage` |
| _render_glyph | 2163 | private | None | No | Paint one `VectorGlyph`'s paths at a position/scale relative to the baseline |
| export_font | 2220 | public | None | No | Build and save the final `.ttf`/`.otf` to a user-chosen path |
| save_settings | 2319 | public | None | No | Persist export-page state |

#### Class: FontGeneratorWizard (line 2327)
Top-level `QWizard`. Adds the five pages in order (ImageUpload 0, Segmentation 1,
CharacterMapping 2, FontSettings 3, Export 4), sets Modern style, custom button
text, and saves every page's settings when the wizard closes — however it closed.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 2332 | constructor | None | No | Assemble the pages, style the wizard, wire the `finished` signal |
| on_finished | 2356 | public | None | No | Persist all settings on completion or cancel |
| save_all_settings | 2366 | public | None | No | Call `save_settings()` on each page |

---

### Font Generator GUI Package Init
**Path**: `gui/font_generator/__init__.py` - 9 lines
**Purpose**: Exposes the wizard as the package's single public entry point.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `from .font_wizard import FontGeneratorWizard` | 7 | import | Re-export of the wizard class |
| `__all__` | 9 | constant | `["FontGeneratorWizard"]` |

---

## Character Animator (Core + GUI)

Converts a single character image into an Adobe Character Animator puppet: MediaPipe detects the body/face, cloud AI (Gemini/OpenAI) generates the 14 lip-sync visemes plus eye-blink and eyebrow variants, and the result is exported as a layered PSD or grouped SVG. Core logic lives in `core/character_animator/`; the PySide6 wizard and installer dialogs live in `gui/character_animator/`.

```
Image ──► BodyPartSegmenter ──► SegmentationResult ──► FaceVariantGenerator ──► AIFaceEditor
 (segmenter.py)                     (models.py)          (face_generator.py)    (ai_face_editor.py)
                                                                │
                                                    VisemeSet / EyeBlinkSet
                                                                │
                                          PuppetStructure ──► PSDExporter / SVGExporter
```

---

### AI Face Editor
**Path**: `core/character_animator/ai_face_editor.py` - 1071 lines
**Purpose**: Cloud-AI editing of individual facial regions (mouth, eyes, eyebrows) for viseme/blink/expression generation, with style detection, disk caching, and provider-specific edit strategies. Replaces the earlier local Stable Diffusion inpainting path.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| AIProvider | 38 | Enum | GOOGLE, OPENAI |
| StyleInfo | 45 | @dataclass | style_name, style_hint, dominant_colors, has_outlines, is_stylized |
| EditResult | 55 | @dataclass | success, image, error, provider, model, cached, quality_score |

#### Class: AIFaceEditor (line 66)
Edits a specific bbox of a character image via Gemini (conversational editing for style consistency) or OpenAI GPT-Image (alpha-mask editing with `input_fidelity=high`). Class attributes `DEFAULT_MODELS` / `HIGH_QUALITY_MODELS` map each provider to its standard and quality-tier image model.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 86 | constructor | None | Stores provider/model/cache dir/quality threshold/style hint; creates the cache directory |
| initialize | 125 | public | bool | Lazily constructs the provider client |
| _init_google | 151 | private | bool | Builds the `google.genai` client and caches the types module |
| _init_openai | 189 | private | bool | Builds the `openai.OpenAI` client |
| _get_cache_key | 225 | private | str | Cache key from image hash + provider + model + region + variant |
| _get_image_hash | 234 | private | str | 12-char MD5 of raw image bytes |
| _load_cached | 239 | private | Optional[Image] | Loads a previously generated variant PNG |
| _save_to_cache | 251 | private | None | Writes a generated variant to the cache directory |
| _image_to_bytes | 260 | private | bytes | PIL image → RGBA PNG bytes |
| _bytes_to_image | 269 | private | Image | PNG bytes → PIL image |
| _create_alpha_mask | 273 | private | bytes | Feathered RGBA mask (transparent = editable) for OpenAI edits |
| edit_face_region | 320 | public | EditResult | Main entry: cache lookup, provider dispatch, validation, retries |
| _edit_with_gemini | 398 | private | EditResult | Region-scoped prompt + image part → `generate_content`, extracts inline image data |
| _edit_with_openai | 471 | private | EditResult | Mask-based image edit call, decodes the returned base64 image |
| _validate_edit | 561 | private | bool | Confirms the region actually changed and warns if pixels outside it drifted |
| extract_style_info | 619 | public | StyleInfo | Detects/reconciles art style, palette, outlines, stylization level |
| _extract_dominant_colors | 679 | private | List[str] | Quantized palette extraction → hex strings |
| _detect_outlines | 705 | private | bool | Flags strong dark line art (>2% very dark pixels) |
| _analyze_stylization | 723 | private | bool | Local-variance (scipy) heuristic, with unique-color fallback |
| _detect_art_style | 757 | private | Optional[str] | Maps outline/stylization flags to "realistic"/"cartoon"/"stylized" |
| _build_prompt_with_style | 776 | private | str | Appends style hint, palette, and outline notes to a base prompt |
| generate_viseme | 806 | public | EditResult | Single viseme from `AI_VISEME_PROMPTS` |
| generate_all_visemes | 844 | public | Dict[str, EditResult] | Iterates `REQUIRED_VISEMES` with progress callback |
| generate_eye_blink | 883 | public | EditResult | Left/right eye open or blink state |
| generate_expression | 924 | public | EditResult | Eyebrow/expression variant |
| start_conversation_session | 965 | public | bool | Gemini-only chat session seeded with the character image + style context |
| end_conversation_session | 1035 | public | None | Drops the chat session |
| cleanup | 1040 | public | None | Releases chat session and client |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| get_ai_face_editor | 1048 | public | Optional[AIFaceEditor] | Factory: constructs and initializes an editor, `None` on failure |

---

### PSD Exporter
**Path**: `core/character_animator/psd_exporter.py` - 723 lines
**Purpose**: Writes a `PuppetStructure` to a layered Photoshop file that Character Animator can auto-rig, with a hand-rolled binary PSD writer and an ExtendScript fallback.
**Language**: Python

#### Class: PSDExporter (line 25)
Builds the Character Animator layer hierarchy (groups, `+` warp-independent prefixes, viseme/blink layers) and serializes it.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 36 | constructor | None | Holds the puppet and an empty flat layer-data list |
| create_layer_hierarchy | 46 | public | List[Dict] | Walks the root layer to produce PSD layer records |
| _process_layer | 60 | private | None | Recursive walk emitting open/close group markers; children reversed for PSD order |
| add_layer | 100 | public | None | Adds an RGBA image layer under a group path |
| _find_or_create_group | 137 | private | PuppetLayer | Resolves (creating as needed) a group by path |
| add_group | 158 | public | PuppetLayer | Creates a named group under an optional parent path |
| set_layer_properties | 183 | public | None | Updates visibility/opacity/blend mode on an existing layer |
| _find_layer_by_path | 211 | private | Optional[PuppetLayer] | Path lookup without creation |
| populate_from_visemes | 228 | public | None | Adds all 14 mouth shapes to `Head/Mouth`, only "Neutral" visible |
| populate_from_blinks | 251 | public | None | Adds eye-blink layers to the `Head` group |
| export | 280 | public | bool | Entry point; falls back to the .jsx script when psd-tools is missing or fails |
| _export_with_psd_tools | 310 | private | bool | Thin wrapper that delegates to the manual writer (psd-tools has limited write support) |
| _create_psd_manual | 327 | private | bool | Assembles PSD header, layer section, and composite, then writes the file |
| _flatten_layers_for_export | 387 | private | List[Dict] | Depth-first flatten of layers that carry images (logs the resulting layer list) |
| process | 391 | nested | None | Inner recursion used by `_flatten_layers_for_export` |
| _build_layer_section | 419 | private | bytes | Packs the PSD layer-and-mask information section with `struct` |
| _build_layer_extra_data | 493 | private | bytes | Per-layer mask/blending-range stubs plus the 4-byte-padded Pascal name |
| _create_composite_image | 515 | private | np.ndarray | Flattened RGBA composite for the PSD image data section |
| _export_fallback_script | 559 | private | bool | Writes layer PNGs plus a Photoshop `.jsx` that rebuilds the document |
| _export_layer_images | 601 | private | None | Recursively saves each layer image as PNG and records its path |
| _generate_photoshop_script | 642 | private | str | Emits the ExtendScript that recreates the layer hierarchy in Photoshop |

---

### SVG Exporter
**Path**: `core/character_animator/svg_exporter.py` - 636 lines
**Purpose**: Writes a `PuppetStructure` to SVG, where nested `<g>` groups map to Character Animator layers; supports base64-embedded raster layers, external PNGs, or true vectorization.
**Language**: Python

#### Class: SVGExporter (line 27)
##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 35 | constructor | None | Stores puppet plus `embed_images` / `vectorize` flags |
| image_to_svg_path | 54 | public | str | OpenCV threshold + contour trace → SVG path data (optionally simplified) |
| _image_to_base64 | 119 | private | str | PNG → `data:image/png;base64,…` URI |
| create_group_hierarchy | 126 | public | str | Builds the full SVG document string from the layer tree |
| _process_layer_to_svg | 161 | private | None | Recursive `<g>`/image emission with indentation |
| _make_svg_id | 193 | private | str | Sanitizes a layer name into a valid SVG id, preserving the `+` prefix |
| _add_image_element | 206 | private | None | Emits an `<image>` element (embedded or external href) |
| embed_raster_layers | 271 | public | None | Attaches a dict of images onto matching layers in the tree |
| populate_from_visemes | 284 | public | None | Adds the 14 mouth shapes to `Head/Mouth`, only "Neutral" visible |
| populate_from_blinks | 309 | public | None | Adds blink-state layers to the head group |
| _find_or_create_group | 339 | private | PuppetLayer | Resolves/creates a group path in the puppet tree |
| export | 360 | public | bool | Writes the SVG file and, if not embedding, the sibling PNGs |
| _save_external_images | 393 | private | None | Saves each layer image next to the SVG |
| save_recursive | 395 | nested | None | Inner recursion used by `_save_external_images` |
| export_with_svgwrite | 406 | public | bool | Alternate export path using the `svgwrite` library |
| _create_svgwrite_group | 450 | private | object | Builds an svgwrite group/image node for one layer |

#### Class: SVGVectorizer (line 506)
Standalone raster → vector converter used when `vectorize=True`.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 516 | constructor | None | Selects the method ("opencv", "potrace", "ai") |
| vectorize | 525 | public | str | Dispatches to the configured backend, returns SVG path data |
| _vectorize_opencv | 550 | private | str | Contour-based vectorization via OpenCV |
| _vectorize_potrace | 596 | private | str | Shells out to `potrace` through temporary BMP/SVG files |

---

### Body Part Segmenter
**Path**: `core/character_animator/segmenter.py` - 608 lines
**Purpose**: MediaPipe-driven detection of pose landmarks (33) and face mesh (478), turned into body-part masks/bboxes and facial regions; SAM 2 is an optional mask-refinement step.
**Language**: Python

#### Class: BodyPartSegmenter (line 42)
##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 50 | constructor | None | Optional SAM 2 weights path; lazy model handles |
| _init_mediapipe | 63 | private | bool | Creates the Pose (complexity 2, segmentation on) and FaceMesh (refined landmarks) solvers |
| _init_sam | 95 | private | bool | Optionally builds a SAM 2 predictor on CUDA/CPU if weights exist |
| initialize | 132 | public | bool | Requires MediaPipe; SAM is best-effort |
| detect_pose | 153 | public | Optional[np.ndarray] | Pose landmarks scaled to pixel coordinates |
| detect_face | 191 | public | Optional[np.ndarray] | 478 face-mesh landmarks in pixel coordinates |
| _get_bbox_from_landmarks | 232 | private | Tuple[int,int,int,int] | Padded bbox around selected landmark indices |
| _create_mask_from_landmarks | 257 | private | np.ndarray | Filled polygon mask via `cv2.fillPoly` |
| _get_facial_region | 289 | private | FacialRegion | Bundles bbox + landmark subset under a region name |
| segment_body_parts | 321 | public | SegmentationResult | Main entry: pose → face mesh → body masks → facial regions |
| _segment_body_from_pose | 364 | private | None | Derives head/torso/arm masks and bboxes from pose landmarks |
| _segment_face_from_mesh | 417 | private | None | Extracts mouth, eyes, and eyebrow regions from the face mesh |
| _refine_with_sam | 477 | private | None | Uses detected bboxes as SAM 2 box prompts to sharpen masks |
| extract_layer_image | 551 | public | Image | Applies a mask to the alpha channel and crops to bbox (resizes mismatched masks) |
| cleanup | 595 | public | None | Closes MediaPipe solvers and drops the SAM predictor |

---

### Face Variant Generator
**Path**: `core/character_animator/face_generator.py` - 539 lines
**Purpose**: Orchestration layer between segmentation results and `AIFaceEditor` — locates mouth/eye regions, then produces a populated `VisemeSet`, `EyeBlinkSet`, and eyebrow variants.
**Language**: Python

#### Class: FaceVariantGenerator (line 34)
##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 42 | constructor | None | Cache dir, quality threshold, provider and model selection |
| initialize | 65 | public | bool | Requires `AI_EDITING_AVAILABLE`; builds the `AIFaceEditor` via the factory |
| _get_image_hash | 101 | private | str | 12-char MD5 used for cache keys |
| get_mouth_region | 106 | public | Tuple[Image, ndarray, bbox] | Padded, in-bounds mouth crop + convex-hull mask + expanded bbox |
| get_eye_regions | 155 | public | Tuple[…, …] | Same treatment for left and right eyes |
| _create_region_mask | 206 | private | np.ndarray | Convex hull of offset landmarks, all-white fallback on error |
| generate_viseme | 243 | public | Image | Delegates to `AIFaceEditor.generate_viseme`; returns the original image on failure |
| generate_all_visemes | 285 | public | VisemeSet | Loops `REQUIRED_VISEMES`, stores the mouth bbox for export cropping |
| generate_blink_states | 343 | public | EyeBlinkSet | Generates open/blink images for both eyes and records their bboxes |
| generate_eyebrow_variants | 430 | public | Dict[str, Image] | Generates raised/lowered/concerned (or supplied) eyebrow expressions |
| start_batch_session | 508 | public | bool | Opens the Gemini conversational session for cross-variant style consistency |
| end_batch_session | 527 | public | None | Closes that session |
| cleanup | 532 | public | None | Releases the underlying editor |

---

### Character Animator Constants
**Path**: `core/character_animator/constants.py` - 463 lines
**Purpose**: Layer-naming conventions, viseme/expression prompt catalogs, phoneme mapping, MediaPipe landmark index tables, and export defaults.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| LAYER_NAMES | 17 | constant | Canonical Character Animator layer names (root, body parts, eyes, mouth) |
| WARP_INDEPENDENT_LAYERS | 53 | constant | Keys that must carry the `+` prefix |
| REQUIRED_VISEMES | 66 | constant | The 14 mouth shapes (Neutral … Surprised) |
| OPTIONAL_EXPRESSIONS | 84 | constant | Angry / Sad / Disgusted / Afraid |
| VISEME_PROMPTS | 92 | constant | Legacy short viseme descriptions |
| AI_VISEME_PROMPTS | 112 | constant | Detailed cloud-AI edit prompts with facial-hair/style preservation rules |
| AI_EYE_BLINK_PROMPTS | 199 | constant | Per-eye open/blink edit prompts |
| AI_EYEBROW_PROMPTS | 219 | constant | Eyebrow expression edit prompts |
| STYLE_HINT_TEMPLATES | 244 | constant | Style-preservation clauses per art style (cartoon, anime, realistic, …) |
| PHONEME_TO_VISEME | 258 | constant | ARPAbet phoneme → viseme mapping for lip-sync timing |
| EYE_BLINK_PROMPTS | 289 | constant | Legacy short blink descriptions |
| BODY_PART_ORDER | 301 | constant | Z-order of body parts (left arm → head) |
| BODY_PART_DEPTH_RANGES | 309 | constant | Normalized depth bands per body part |
| MOUTH_LANDMARKS | 326 | constant | Face-mesh indices for outer/inner lip contours |
| LEFT_EYE_LANDMARKS | 334 | constant | Upper/lower/iris indices, left eye |
| RIGHT_EYE_LANDMARKS | 340 | constant | Upper/lower/iris indices, right eye |
| LEFT_EYEBROW_LANDMARKS | 347 | constant | Left eyebrow indices |
| RIGHT_EYEBROW_LANDMARKS | 348 | constant | Right eyebrow indices |
| FACE_OVAL_LANDMARKS | 351 | constant | Face outline indices for head segmentation |
| NOSE_LANDMARKS | 358 | constant | Bridge/tip/nostril indices |
| POSE_LANDMARK_INDICES | 369 | constant | Name → index for the 33 MediaPipe pose landmarks |
| POSE_CONNECTIONS | 406 | constant | Skeleton edge list for drawing |
| PSD_SETTINGS | 441 | constant | Color mode and bit depth for PSD export |
| SVG_SETTINGS | 447 | constant | Embed-images / vectorize defaults |
| DEFAULT_CANVAS_SIZE | 453 | constant | (2048, 2048) default puppet canvas |
| MIN_REGION_SIZES | 456 | constant | Minimum pixel sizes per detected region |

---

### Character Animator Models
**Path**: `core/character_animator/models.py` - 399 lines
**Purpose**: Dataclasses for the puppet pipeline — layers, hierarchy, viseme/blink collections, segmentation output, and export format enum.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| ExportFormat | 19 | Enum | PSD, SVG, AI |
| FacialRegion | 27 | @dataclass | name, bbox, landmarks, mask |
| PuppetLayer | 47 | @dataclass | name, image, children, visible, opacity, blend_mode, position, warp_independent, depth_order |
| VisemeSet | 99 | @dataclass | 14 viseme images + mouth_bbox |
| EyeBlinkSet | 172 | @dataclass | left/right open + blink images, per-eye bboxes |
| SegmentationResult | 195 | @dataclass | original_image, head/torso/arm masks + bboxes, facial regions, depth_map, pose_landmarks, face_landmarks |
| PuppetStructure | 254 | @dataclass | name, root_layer, visemes, eye_blinks, segmentation, width, height, export_format |

#### Methods by Class
| Class | Member | Line | Type | Returns | Description |
|-------|--------|------|------|---------|-------------|
| FacialRegion | @property center | 35 | property | Tuple[int,int] | Center point of the bbox |
| FacialRegion | @property area | 41 | property | int | Bbox area |
| PuppetLayer | @property display_name | 73 | property | str | Name with `+` prefix when warp-independent |
| PuppetLayer | is_group | 79 | public | bool | True when the layer has children |
| PuppetLayer | add_child | 83 | public | None | Appends a child layer |
| PuppetLayer | find_layer | 87 | public | Optional[PuppetLayer] | Recursive name lookup |
| VisemeSet | to_dict | 138 | public | Dict[str, Image] | Maps Character Animator viseme names to images |
| VisemeSet | get_missing | 157 | public | List[str] | Names of not-yet-generated visemes |
| VisemeSet | is_complete | 166 | public | bool | True when all 14 exist |
| EyeBlinkSet | is_complete | 184 | public | bool | True when all four eye states exist |
| SegmentationResult | get_body_parts | 233 | public | Dict[str, Tuple] | head/torso/left_arm/right_arm (mask, bbox) pairs |
| SegmentationResult | get_facial_regions | 242 | public | Dict[str, FacialRegion] | eyes, mouth, eyebrows |
| PuppetStructure | get_head_layer | 295 | public | Optional[PuppetLayer] | Finds the "Head" layer |
| PuppetStructure | get_body_layer | 299 | public | Optional[PuppetLayer] | Finds the "Body" layer |
| PuppetStructure | get_mouth_group | 303 | public | Optional[PuppetLayer] | Finds "Mouth" under "Head" |
| PuppetStructure | validate | 310 | public | Tuple[bool, List[str]] | Checks required layers, visemes, and blink completeness |
| PuppetStructure | @classmethod create_empty | 351 | class | PuppetStructure | Builds the standard Body/Head hierarchy with warp-independent eyebrows and pupils |

---

### Character Animator Installer
**Path**: `core/character_animator/installer.py` - 384 lines
**Purpose**: Declares the heavy AI dependency set and model downloads for puppet automation, detects what is missing, and estimates install size/time.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| PUPPET_PACKAGES | 28 | constant | Package groups: core, segmentation, pose_detection, depth_estimation, inpainting |
| LIGHTWEIGHT_PACKAGES | 53 | constant | Alias for the always-required `core` group |
| HEAVY_AI_PACKAGES | 56 | constant | Concatenation of the on-demand groups |
| PUPPET_MODELS | 64 | constant | Model registry (SAM 2 large/base, Depth-Anything, ControlNet OpenPose, SDXL inpainting) with URLs and sizes |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| get_puppet_packages | 101 | public | Tuple[List[str], str] | Package list plus the CUDA/CPU PyTorch index URL based on GPU detection |
| check_dependencies | 141 | public | Dict[str, bool] | Import-probes torch/CUDA, sam2, mediapipe, transformers, diffusers, controlnet, psd-tools, svgwrite |
| get_missing_packages | 211 | public | List[str] | Pip requirement strings for whatever failed to import |
| get_model_paths | 240 | public | Dict[str, Path] | Weights under the user data dir; HF repos under `~/.cache/huggingface` |
| get_missing_models | 261 | public | List[str] | Models whose paths do not exist |
| get_install_info | 278 | public | Dict | GPU, disk space, missing package/model counts, total download estimate |
| is_fully_installed | 314 | public | bool | True when no packages and no models are missing |
| get_pytorch_install_command | 326 | public | List[str] | pip argv for the CUDA or CPU torch wheel index |
| estimate_install_time | 350 | public | str | Human-readable estimate from package mix and model sizes |

---

### Character Animator Availability
**Path**: `core/character_animator/availability.py` - 304 lines
**Purpose**: Import-time capability flags (mirroring the `REALESRGAN_AVAILABLE` pattern) plus helpers that turn them into UI-ready status text and feature tables.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| SEGMENTATION_AVAILABLE | 20 | constant | Declared `False`; set `True` at line 30 if SAM 2 imports |
| POSE_DETECTION_AVAILABLE | 21 | constant | Declared `False`; set `True` at line 38 if MediaPipe imports |
| PSD_EXPORT_AVAILABLE | 22 | constant | Declared `False`; set `True` at line 75 if psd-tools imports |
| SVG_EXPORT_AVAILABLE | 23 | constant | Declared `False`; set `True` at line 83 if svgwrite imports |
| AI_EDITING_AVAILABLE | 24 | constant | Declared `False`; resolved at line 59 from google-genai / openai presence |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| check_all_dependencies | 93 | public | Dict[str, bool] | All five flags plus `torch` and `torch_cuda` |
| get_missing_dependencies | 121 | public | List[str] | Human-readable names of unavailable components |
| get_install_status_message | 147 | public | str | Fully-installed / partially-installed / not-installed message for dialogs |
| can_create_puppet | 178 | public | Tuple[bool, str] | Gate: MediaPipe required, PSD or SVG required; warns about limited mode |
| is_full_installation | 205 | public | bool | True when segmentation, pose, AI editing, and PSD export are all present |
| get_feature_availability | 220 | public | Dict[str, Dict] | Per-feature name/available/description/package for the status UI |
| get_gpu_info | 261 | public | Dict | CUDA device name, version, and memory via torch, with an `nvidia-smi` fallback |

---

### Character Animator Package Init
**Path**: `core/character_animator/__init__.py` - 62 lines
**Purpose**: Public surface of the core package — re-exports the models, key constants, availability helpers, AI face-editing types, and `FaceVariantGenerator` via `__all__`.
**Language**: Python

Re-exported names: `PuppetLayer`, `PuppetStructure`, `VisemeSet`, `EyeBlinkSet`, `ExportFormat`, `SegmentationResult`, `FacialRegion`, `LAYER_NAMES`, `VISEME_PROMPTS`, `BODY_PART_ORDER`, `REQUIRED_VISEMES`, `OPTIONAL_EXPRESSIONS`, `SEGMENTATION_AVAILABLE`, `AI_EDITING_AVAILABLE`, `check_all_dependencies`, `get_install_status_message`, `get_missing_dependencies`, `AIFaceEditor`, `EditResult`, `StyleInfo`, `get_ai_face_editor`, `FaceVariantGenerator`.

---

### Puppet Wizard (GUI)
**Path**: `gui/character_animator/puppet_wizard.py` - 1373 lines
**Purpose**: Five-page `QWizard` driving the whole puppet workflow — dependency check, image selection, detection preview, AI variant generation, and export — with worker threads and Discord Rich Presence integration.
**Language**: Python

#### Class: DependencyCheckPage (line 45)
Step 0 — installation status and the "Install AI Components" entry point.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 50 | constructor | None | Sets title/subtitle and builds the UI |
| init_ui | 56 | public | None | Status group, per-component checklist, capability label, install button |
| initializePage | 112 | public | None | Refreshes status each time the page is shown |
| refresh_status | 116 | public | None | Recolors component rows, updates status/capability text and button state |
| isComplete | 153 | public | bool | Gated by `can_create_puppet()` |
| on_install_clicked | 158 | public | None | Chains the confirm dialog into the progress dialog |
| on_installation_complete | 171 | public | None | Re-runs `refresh_status` after install |

#### Class: ImageSelectionPage (line 176)
Step 1 — pick the source image; remembers the last path in `QSettings("ImageAI", "CharacterAnimator")`. Signal: `image_selected(str)` (line 181).

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 183 | constructor | None | Restores the last used image path if it still exists |
| init_ui | 196 | public | None | Path field, browse button, preview pane |
| browse_image | 246 | public | None | File dialog for the source image |
| on_path_changed | 257 | public | None | Persists the path and refreshes the preview |
| update_preview | 267 | public | None | Scaled (never cropped) pixmap preview |
| isComplete | 299 | public | bool | Requires an existing image file |

#### Class: SegmentationPage (line 306)
Step 2 — runs `DetectionThread` and shows annotated results.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 311 | constructor | None | Holds the segmentation result and thread handles |
| init_ui | 319 | public | None | Progress bar, status label, results text, image pane |
| initializePage | 361 | public | None | Kicks off detection on entry |
| run_detection | 365 | public | None | Starts `DetectionThread` for the selected image |
| on_progress | 383 | public | None | Status text + progress bar updates |
| on_detection_finished | 388 | public | None | Stores results or shows detection-failure guidance |
| display_results | 405 | public | None | Text summary of detected parts and regions |
| display_annotated_image | 445 | public | None | Draws colored body-part and mouth bboxes over the image |
| isComplete | 496 | public | bool | Requires a segmentation result |

#### Class: VisemeGenerationPage (line 501)
Step 3 — provider/model choice, cost + time estimation, and threaded generation. Class tables `MODEL_COSTS` and `MODEL_NAMES` hold per-image pricing and display labels for the Gemini/GPT-Image options.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 524 | constructor | None | Holds visemes/blinks, thread handle, and `QSettings` |
| init_ui | 534 | public | None | Provider/model combos, generation checkboxes, estimates, output console |
| _on_provider_changed | 637 | private | None | Repopulates the model combo for Google vs OpenAI |
| _update_cost_estimate | 662 | private | None | Recomputes image count (14 visemes / 2 blinks / 6 eyebrows), cost, and ETA |
| _get_selected_provider | 699 | private | str | "google" or "openai" |
| _get_selected_model | 703 | private | str | Model id from the combo's user data |
| initializePage | 707 | public | None | Resets state and restores the saved provider preference |
| start_generation | 721 | public | None | Launches `GenerationThread` with the chosen options |
| on_progress | 769 | public | None | Progress bar + status updates |
| on_viseme_complete | 775 | public | None | Appends each completed viseme to the console |
| on_generation_finished | 779 | public | None | Stores the `VisemeSet`/`EyeBlinkSet` and re-enables controls |
| on_generation_error | 798 | public | None | Classifies rate-limit / API-key / quota errors and suggests remedies |
| isComplete | 815 | public | bool | Allows continuing when visemes exist or generation was opted out |

#### Class: ExportPage (line 821)
Step 4 — name, format (PSD / SVG / both), and output folder; settings persist across runs.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 826 | constructor | None | Builds UI then restores saved settings |
| init_ui | 834 | public | None | Name field, format combo, output path, export button |
| _load_settings | 912 | private | None | Restores name/format/output; defaults to `<user data>/Characters` |
| _save_settings | 934 | private | None | Persists name, format index, and output path |
| browse_output | 940 | public | None | Output-folder chooser |
| export_puppet | 948 | public | None | Assembles the `PuppetStructure` and runs the PSD and/or SVG exporter |

#### Class: DetectionThread (line 1068)
`QThread` wrapper around `BodyPartSegmenter`. Signals: `progress(str, int)` (line 1071), `finished(bool, object)` (line 1072).

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 1074 | constructor | None | Stores the image path |
| run | 1078 | public | None | Initializes the segmenter, segments body parts, emits the result, cleans up |

#### Class: GenerationThread (line 1108)
`QThread` wrapper around `FaceVariantGenerator`. Signals: `progress(str, int)` (line 1111), `viseme_complete(str)` (line 1112), `error(str, str)` (line 1113), `finished(bool, object, object)` (line 1114).

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 1116 | constructor | None | Captures image path, segmentation, feature toggles, provider/model, cache flag |
| run | 1137 | public | None | Generates visemes, blinks, and eyebrow variants, emitting per-item progress |
| on_viseme_progress | 1162 | nested | None | Progress callback passed into `generate_all_visemes` |

#### Class: PuppetWizard (line 1219)
The wizard shell. Page ids: `PAGE_DEPENDENCY=0`, `PAGE_IMAGE=1`, `PAGE_SEGMENTATION=2`, `PAGE_VISEME=3`, `PAGE_EXPORT=4`.

##### Methods
| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 1231 | constructor | None | Registers the five pages, skips the dependency page when fully installed, sets button text |
| has_unsaved_generation | 1263 | public | bool | True when variants were generated but not yet exported |
| accept | 1275 | public | None | Auto-triggers export on Finish and warns if the output folder is unset or export failed |
| reject | 1312 | public | None | Confirms before discarding unexported generation |
| showEvent | 1329 | public | None | Sets Discord presence to `CHARACTER_GENERATOR` |
| closeEvent | 1338 | public | None | Resets presence to IDLE and reuses the unsaved-work confirmation |

#### Functions
| Function | Line | Scope | Returns | Description |
|----------|------|-------|---------|-------------|
| launch_puppet_wizard | 1360 | public | Optional[PuppetWizard] | Executes the wizard modally; returns it only when accepted |

---

### Puppet Install Dialogs (GUI)
**Path**: `gui/character_animator/install_dialog.py` - 555 lines
**Purpose**: Confirm-then-install flow for the heavy Character Animator AI dependencies, following the Real-ESRGAN installer pattern — package install, model downloads, verification, and optional app restart.
**Language**: Python

#### Class: PuppetInstallConfirmDialog (line 40)
Pre-install summary: what gets installed, GPU detection, disk-space check, and estimated download size.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 51 | constructor | None | Modal dialog setup |
| init_ui | 58 | public | None | Builds the full summary UI and Install/Cancel buttons |

#### Class: PuppetInstallProgressDialog (line 192)
Three-phase progress dialog (packages → models → verification) with elapsed-time display; close is blocked while work is running. Signal: `installation_complete(bool, str)` (line 203).

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 205 | constructor | None | Strips the close button, initializes installer/downloader state |
| init_ui | 227 | public | None | Title, phase label, elapsed timer, progress bar, output console |
| start_installation | 313 | public | None | Reports GPU status and starts `PackageInstaller` with the right index URL |
| _time_str | 344 | private | str | `HH:MM:SS` stamp used to prefix log lines |
| update_elapsed_time | 348 | public | None | Ticks the "Elapsed: m:ss" label |
| on_progress | 356 | public | None | Appends a message and auto-scrolls the console |
| on_percentage | 367 | public | None | Updates the progress bar |
| on_packages_finished | 371 | public | None | Advances to model download, or reports failure and notifies |
| download_next_model | 390 | public | None | Pops the next model from the queue via `ModelDownloader` |
| on_model_downloaded | 428 | public | None | Logs success/warning and advances the queue index |
| verify_installation | 439 | public | None | Re-runs `check_all_dependencies()` and reports each component (CUDA optional) |
| on_all_complete | 455 | public | None | Stops the timer, sets final state, emits `installation_complete` |
| show_completion_buttons | 487 | public | None | Reveals Close and (optionally) Restart |
| show_notification | 492 | public | None | System-tray notification with a color-coded icon |
| safe_hide_tray | 512 | nested | None | Deferred tray teardown guarded against `RuntimeError` on deleted objects |
| restart_application | 524 | public | None | `QProcess.startDetached` relaunch, then quits the app |
| reject | 537 | public | None | Blocks closing while the installer or downloader thread is running |

---

### Character Animator GUI Package Init
**Path**: `gui/character_animator/__init__.py` - 20 lines
**Purpose**: Exports the GUI entry points for the puppet feature.
**Language**: Python

Re-exported names: `PuppetInstallConfirmDialog`, `PuppetInstallProgressDialog`, `PuppetWizard`.

---

## Providers (AI Backends)

The `providers/` package holds every AI backend behind one abstract interface
(`ImageProvider`). All backends are **lazily imported** so a missing optional
dependency (TensorFlow, diffusers, openai) degrades to "provider unavailable"
instead of crashing the app. `providers/video/` is a separate, parallel hierarchy
for lip-sync video backends.

```
                    providers/__init__.py
                  get_provider() factory + cache
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
      providers/base.py                providers/video/__init__.py
      ImageProvider (ABC)              get_lipsync_provider()
              │                               │
   ┌──────┬───┴───┬─────────┬────────┐        ▼
   ▼      ▼       ▼         ▼        ▼   base_lipsync.py
 google openai stability local_sd midjourney   BaseLipSyncProvider
                            │      ollama            │
                            ▼                        ▼
                      model_info.py          musetalk_provider.py
```

---

### Provider Base Interface
**Path**: `providers/base.py` - 225 lines
**Purpose**: Abstract base class every image provider implements — generation, auth
validation, model listing, feature probing, and optional edit/inpaint hooks.
**Language**: Python

#### Classes

##### `ImageProvider` (line 8)
Abstract base class (`ABC`) for image generation providers. Subclasses **must**
implement `generate`, `validate_auth`, `get_models`, and `get_default_model`;
everything else has a working default. `__init__` reads `api_key` and `auth_mode`
out of the config dict. `get_model_auth_requirements` / `check_model_auth` are the
single, shared mechanism for enforcing per-model auth rules identically in the GUI
and CLI. `edit_image` and `inpaint` raise `NotImplementedError` unless overridden.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 11 | constructor | None | No | Stores config, `api_key`, `auth_mode` |
| `@abstractmethod generate` | 23 | public | `Tuple[List[str], List[bytes]]` | No | Generate content from a text prompt; returns (texts, image bytes) |
| `@abstractmethod validate_auth` | 47 | public | `Tuple[bool, str]` | No | Validate credentials, returning (is_valid, message) |
| `@abstractmethod get_models` | 57 | public | `Dict[str, str]` | No | Model ID → display name map |
| `@abstractmethod get_default_model` | 67 | public | `str` | No | Provider's default model ID |
| `supports_feature` | 76 | public | `bool` | No | Membership test against `get_supported_features()` |
| `get_supported_features` | 88 | public | `List[str]` | No | Feature names; base returns `["generate"]` |
| `get_api_key_url` | 98 | public | `str` | No | Where to obtain an API key (empty by default) |
| `get_model_auth_requirements` | 107 | public | `Dict[str, Any]` | No | Per-model auth spec (requires_api_key/requires_gcloud/display_name/error_message) |
| `check_model_auth` | 132 | public | `Tuple[bool, str]` | No | Enforce the auth spec against the current `auth_mode` |
| `edit_image` | 159 | public | `Tuple[List[str], List[bytes]]` | No | Optional hook; raises `NotImplementedError` by default |
| `inpaint` | 180 | public | `Tuple[List[str], List[bytes]]` | No | Optional masked-region hook; raises `NotImplementedError` by default |
| `_load_reference_image` | 203 | private | `Optional[bytes]` | No | Normalize a reference image (bytes / str / `Path`) to bytes |

---

### Provider Registry & Factory
**Path**: `providers/__init__.py` - 200 lines
**Purpose**: Lazy provider discovery, the `get_provider()` factory, and an instance
cache. Also patches protobuf `MessageFactory.GetPrototype` and silences TensorFlow /
FutureWarning noise before any backend imports.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_PROVIDERS` | 37 | constant | Lazy cache of provider name → class (populated at line 50 inside `_get_providers`) |
| `_PROVIDER_CACHE` | 40 | constant | Instantiated-provider cache (reset at line 179 by `clear_provider_cache`) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_get_providers` | 42 | private | `Dict[str, Type[ImageProvider]]` | No | Import each backend inside `try/except`, registering only those whose deps load: `google`, `openai`, `stability`, `local_sd`, `midjourney`, `ollama` |
| `suppress_stderr` | 54 | private (nested) | context manager | No | Temporarily redirects `sys.stderr` to hide protobuf/TF import errors |
| `get_provider` | 126 | public | `ImageProvider` | No | Factory by name; refreshes `api_key`/`auth_mode` on cache hits, raises `ValueError` for unknown names |
| `list_providers` | 170 | public | `list[str]` | No | Names of successfully-loaded providers |
| `clear_provider_cache` | 176 | public | None | No | Drop all cached instances |
| `preload_provider` | 182 | public | None | No | Warm the cache for one provider (prints a loading line) |

> Note: `midjourney_provider.py` is **not** registered here — the registry binds
> `midjourney` to `providers/midjourney.py`.

---

### Google Gemini Provider
**Path**: `providers/google.py` - 2156 lines
**Purpose**: Google Gemini image generation (Nano Banana / Nano Banana Pro), dual
authentication (API key or gcloud ADC), multi-turn chat editing sessions, region
editing, and Veo video generation.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `GENAI_AVAILABLE` | 17 | constant | `google.genai` presence probe via `importlib.util.find_spec` (fallback assignment at line 19) |
| `MODEL_AUTH_REQUIREMENTS` | 54 | constant | **Single source of truth** for per-model auth rules; `gemini-3-pro-image-preview` (Nano Banana Pro) is API-key-only |
| `GCLOUD_AVAILABLE` | 192 | constant | `google.cloud.aiplatform` presence probe (fallback at line 194) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `apply_transparent_canvas_fix` | 70 | public | `bytes` | No | Center a reference image on a transparent canvas of the target aspect ratio so Gemini receives the expected geometry |

#### Classes

##### `GoogleProvider(ImageProvider)` (line 202)
The largest provider. Holds a lazily-created `google.genai` client whose mode
(`"api_key"` vs `"gcloud"`) is tracked in `_client_mode` and re-initialized when the
user flips auth modes at runtime. `_last_chat_session` backs multi-turn ("conversational")
editing for Nano Banana Pro. Two class-level constants sit between the methods below:
`LEGACY_IMAGE_MODEL_ALIASES` (retired Imagen/Vertex IDs → `gemini-2.5-flash-image`,
for the 2026-06-30 Google Cloud deprecation) and `_EDIT_MIME_BY_SUFFIX` (reference-image
MIME lookup).

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 205 | constructor | None | No | Builds a `ConfigManager`; initializes the API-key client eagerly, defers gcloud init to `generate()` |
| `get_last_chat_session` | 233 | public | chat session | No | Accessor for the multi-turn editing session |
| `create_chat_session` | 242 | public | chat session | No | Open a `client.chats` session with response modalities, `ImageConfig` aspect ratio, optional Google Search grounding |
| `_init_api_key_client` | 297 | private | None | No | Lazy-import `google.genai` and construct the API-key client |
| `_init_gcloud_client` | 323 | private | None | No | Construct the Vertex/ADC client; `raise_on_error` controls hard-fail vs silent probe |
| `_get_gcloud_project_id` | 397 | private | `Optional[str]` | No | Read the active project from the gcloud config file (Linux/snap/Windows paths), falling back to `gcloud config get-value project` |
| `get_model_auth_requirements` | 437 | public | `Dict[str, Any]` | No | Look the model up in `MODEL_AUTH_REQUIREMENTS` |
| `generate` | 457 | public | `Tuple[List[str], List[bytes]]` | No | Main generation path (~980 lines): client re-init on auth change, legacy-model aliasing, `check_model_auth`, rate limiting, `image_config` aspect ratio, retries on `NO_IMAGE`, optional aspect cropping/scaling |
| `validate_auth` | 1442 | public | `Tuple[bool, str]` | No | gcloud check, or a minimal `generate_content` probe for API keys |
| `_check_gcloud_auth` | 1464 | private | `Tuple[bool, str]` | No | Cached-then-live gcloud/ADC credential check with project ID |
| `_check_crop_edges_uniform` | 1525 | private | `bool` | No | Color-variance test on the crop margins — uniform edges auto-crop, varied content defers to the crop dialog |
| `get_models` | 1597 | public | `Dict[str, str]` | No | Image models only (Gemini 3 Pro Image, 3.1 Flash Image, 2.5 Flash Image), newest first |
| `get_models_with_details` | 1611 | public | `Dict[str, Dict[str, str]]` | No | Adds nickname, description, `requires_gcloud`, and max resolution for UI display |
| `resolve_model_alias` | 1672 | public | `str` | No | Map a legacy Imagen/Vertex ID to its GA equivalent (pass-through otherwise) |
| `get_default_model` | 1680 | public | `str` | No | `gemini-2.5-flash-image` |
| `get_models_for_auth` | 1684 | public | `Dict[str, str]` | No | Filter the model list by `"api-key"` vs `"gcloud"` |
| `_format_model_display` | 1709 | private | `str` | No | Compose the combo-box label from name + nickname |
| `is_model_available` | 1733 | public | `Tuple[bool, Optional[str]]` | No | Availability check against configured API key / gcloud credentials |
| `get_api_key_url` | 1766 | public | `str` | No | `https://aistudio.google.com/apikey` |
| `get_supported_features` | 1770 | public | `List[str]` | No | `["generate", "edit", "compose"]` |
| `@classmethod _edit_input_parts` | 1784 | class | `List[dict]` | No | Normalize bytes / path / list-of-either into `inline_data` parts for multi-reference compose |
| `edit_image` | 1806 | public | `Tuple[List[str], List[bytes]]` | No | Prompt-driven edit/compose over one or more reference images |
| `edit_image_region` | 1843 | public | `Tuple[List[str], List[bytes]]` | No | Edit a bbox region, optionally reusing the chat session for style consistency across regions (visemes) |
| `start_edit_session` | 1952 | public | `bool` | No | Seed a conversational session with the base character image + style context |
| `reset_edit_session` | 2023 | public | None | No | Clear `_last_chat_session` when switching characters |
| `generate_video` | 2033 | public | `Tuple[Optional[Path], Dict[str, Any]]` | No | Veo 3 / Veo 3.1 video generation from a start frame (plus optional end frame), duration snapping, aspect ratio |

---

### OpenAI Provider
**Path**: `providers/openai.py` - 1477 lines
**Purpose**: OpenAI image generation (gpt-image-2 / 1.5 / 1 / 1-mini, DALL·E 3 / 2),
including streaming partials, masked region edits, viseme batches, and the Batch API.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `OPENAI_AVAILABLE` | 19 | constant | `openai` package presence probe (fallback at line 21) |
| `MODEL_CAPS` | 46 | constant | Per-model capability table (display name, snapshot, endpoint, sizes, quality values). All per-model behavior must be expressed here rather than in `if model == ...` branches |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_connection_error_types` | 27 | private | tuple of exception classes | No | Lazily returns `APIConnectionError`/`APITimeoutError` so network failures get an actionable message instead of the SDK's bare "Connection error." |
| `_caps_for` | 171 | private | `dict` | No | `MODEL_CAPS` lookup falling back to `gpt-image-1` |

#### Classes

##### `_UnsupportedParam(ValueError)` (line 176)
Raised when a request carries a parameter the selected model does not support.

##### `OpenAIProvider(ImageProvider)` (line 180)
Client is created lazily by `_ensure_client` with `max_retries=2` and a long
600 s read timeout (gpt-image-2 "thinking" generations can take minutes) but a
15 s connect timeout.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 183 | constructor | None | No | Defers all client construction |
| `_ensure_client` | 190 | private | None | No | Import `openai`, validate the key, build the client with httpx timeouts |
| `generate` | 219 | public | `Tuple[List[str], List[bytes]]` | No | Main generation path (~550 lines): capability-table validation of quality/size/n, streaming dispatch, rate limiting, b64 decode |
| `validate_auth` | 770 | public | `Tuple[bool, str]` | No | `models.list()` probe; specifically detects the gpt-image-2 org-verification gate |
| `get_models` | 790 | public | `Dict[str, str]` | No | Derived from `MODEL_CAPS` |
| `get_models_with_details` | 794 | public | `Dict[str, Dict[str, str]]` | No | Adds per-model descriptions for the UI |
| `get_default_model` | 809 | public | `str` | No | `gpt-image-2` |
| `get_api_key_url` | 813 | public | `str` | No | `https://platform.openai.com/api-keys` |
| `get_supported_features` | 817 | public | `List[str]` | No | `["generate", "edit", "variations", "reference_images"]` |
| `edit_image` | 821 | public | `Tuple[List[str], List[bytes]]` | No | Edit with optional mask; accepts bytes, a path, or a list of either (multi-reference) |
| `create_variations` | 942 | public | `Tuple[List[str], List[bytes]]` | No | Image variations (forced to `dall-e-2`, the only model that supports them) |
| `_generate_streaming` | 989 | private | `Optional[List[bytes]]` | No | Stream partial frames via the Responses API, invoking `on_partial(index, png_bytes)`; returns `None` if the SDK lacks streaming |
| `_create_alpha_mask` | 1070 | private | `bytes` | No | Build a feathered PNG alpha mask (transparent = editable, opaque = preserved) |
| `edit_image_region` | 1124 | public | `Tuple[List[str], List[bytes]]` | No | Masked region edit driven by `_create_alpha_mask` plus optional style context |
| `generate_viseme_batch` | 1273 | public | `Dict[str, Tuple[List[str], List[bytes]]]` | No | Generate every viseme for a character mouth bbox, reporting progress per viseme |
| `submit_batch_job` | 1329 | public | `str` | No | Submit an OpenAI Batch API job and persist a record to `BATCH_JOBS_PATH`; returns the batch ID |
| `check_batch_job` | 1418 | public | `dict` | No | Poll a batch job and, when complete, download images + JSON sidecars to an output directory |

---

### Local Stable Diffusion Provider
**Path**: `providers/local_sd.py` - 491 lines
**Purpose**: On-device generation with Hugging Face Diffusers — device/dtype
detection, VRAM-aware memory optimizations, and txt2img / img2img / inpaint.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `ML_AVAILABLE` | 33 | constant | True when torch/psutil/diffusers/huggingface_hub all import (fallback at line 35) |

#### Classes

##### `DeviceManager` (line 40)
Detects the best inference device and derives memory-saving settings from it.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 43 | constructor | None | No | Falls back to a CPU-only stub when `ML_AVAILABLE` is False |
| `_detect_best_device` | 54 | private | `str` | No | `cuda` → `mps` (Apple Silicon) → `cpu` |
| `_get_optimal_dtype` | 63 | private | torch dtype | No | fp16 vs fp32 selection for the detected device |
| `_get_memory_info` | 72 | private | `dict` | No | GPU/system memory totals via torch + psutil |
| `should_use_cpu_offload` | 96 | public | `bool` | No | True on CUDA with < 8 GB VRAM |
| `should_use_attention_slicing` | 102 | public | `bool` | No | True on CUDA with < 6 GB VRAM, and always on CPU |

##### `LocalSDProvider(ImageProvider)` (line 109)
Wraps a cached Diffusers pipeline. Tracks `current_model` so switching models
reloads (and frees) the pipeline rather than stacking them in VRAM.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 112 | constructor | None | No | Reads model ID + HF cache dir, builds a `DeviceManager`, resolves offload/slicing defaults |
| `get_models` | 133 | public | `Dict[str, str]` | No | Merges `ModelInfo.POPULAR_MODELS` with what is actually installed in the HF cache |
| `get_default_model` | 163 | public | `str` | No | Default checkpoint (`stabilityai/stable-diffusion-2-1`) |
| `get_supported_features` | 172 | public | `List[str]` | No | generate / edit / inpaint |
| `get_api_key_url` | 181 | public | `str` | No | Hugging Face model hub URL (no key required) |
| `validate_auth` | 190 | public | `Tuple[bool, str]` | No | Reports whether the ML dependency stack is installed rather than checking a key |
| `_load_pipeline` | 209 | private | pipeline | No | Load/switch the SD or SDXL pipeline, applying offload, attention slicing, and dtype |
| `generate` | 270 | public | `Tuple[List[str], List[bytes]]` | No | txt2img with steps/guidance/seed/size kwargs |
| `edit_image` | 362 | public | `Tuple[List[str], List[bytes]]` | No | img2img from an input image plus strength |
| `inpaint` | 452 | public | `Tuple[List[str], List[bytes]]` | No | Masked inpainting (white = region to repaint) |

---

### Local SD Model Catalog
**Path**: `providers/model_info.py` - 146 lines
**Purpose**: Static catalog of popular Stable Diffusion checkpoints plus
Hugging-Face-cache introspection (what's installed, and how big).
**Language**: Python

#### Classes

##### `ModelInfo` (line 8)
Class-level `POPULAR_MODELS` dict maps HF model IDs to name, description,
`size_gb`, `recommended` flag, tags, and hub URL (SD 1.4/1.5/2.1, SDXL base +
refiner, SDXL Turbo, SSD-1B, Dreamlike, OpenJourney).

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `@classmethod get_installed_models` | 87 | class | `List[str]` | No | Scan `<cache>/hub` for `models--*` folders, excluding non-generation models (depth, segmentation, upscale, …) |
| `@classmethod is_model_installed` | 123 | class | `bool` | No | Existence check for one model's cache folder |
| `@classmethod get_model_size` | 131 | class | `float` | No | Walk the cache folder and total its size in GB |

---

### Stability AI Provider
**Path**: `providers/stability.py` - 465 lines
**Purpose**: Stability AI REST backend (`https://api.stability.ai`) for SDXL/SD
text-to-image, image-to-image, and masked inpainting.
**Language**: Python

#### Classes

##### `StabilityProvider(ImageProvider)` (line 16)
Pure `requests`-based client — no vendor SDK, so it avoids the protobuf conflicts
that affect the other local/ML backends. Responses arrive as base64 artifacts.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 19 | constructor | None | No | Sets `api_base` and the configured engine (default SDXL 1.0) |
| `get_models` | 30 | public | `Dict[str, str]` | No | SDXL 1.0, SD 1.6, SD 2.1, SDXL Beta |
| `get_default_model` | 44 | public | `str` | No | `stable-diffusion-xl-1024-v1-0` |
| `get_supported_features` | 53 | public | `List[str]` | No | generate / edit / inpaint / reference_image |
| `get_api_key_url` | 62 | public | `str` | No | Stability platform key page |
| `validate_auth` | 71 | public | `Tuple[bool, str]` | No | Calls the account endpoint with the bearer token |
| `generate` | 102 | public | `Tuple[List[str], List[bytes]]` | No | `text-to-image` REST call; decodes base64 artifacts to PNG bytes |
| `edit_image` | 250 | public | `Tuple[List[str], List[bytes]]` | No | `image-to-image` with init image + strength |
| `inpaint` | 360 | public | `Tuple[List[str], List[bytes]]` | No | `image-to-image/masking` with a supplied mask |

---

### Midjourney Provider (registered)
**Path**: `providers/midjourney.py` - 275 lines
**Purpose**: Midjourney has no public API, so this provider composes an `/imagine`
slash command, copies it to the clipboard, and opens the Midjourney web app (or a
Discord channel). This is the implementation the registry binds to `midjourney`.
**Language**: Python

#### Data Structures
| Name | Line | Type | Fields |
|------|------|------|--------|
| `MidjourneyParams` | 17 | `@dataclass` | prompt, negative_prompt, image_urls, aspect_ratio, stylize, quality, seed, chaos, weird, tile, raw, model_version |

#### Classes

##### `MidjourneyProvider(ImageProvider)` (line 33)
Class constants `PROVIDER_ID`, `PROVIDER_NAME`, `MODELS` (v7, v6.1, v6, niji-6,
v5.2) and `WEB_URL` (`https://www.midjourney.com/home` — the `/app` route 404s in
some embedded browsers). Config toggles pick web vs Discord mode and internal vs
external browser.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 55 | constructor | None | No | Reads web URL, auto-open, and Discord server/channel settings |
| `generate` | 67 | public | `Tuple[List[str], List[bytes]]` | No | Build `MidjourneyParams` from kwargs, emit the slash command, copy it, open the interface; returns a manual-mode marker rather than pixels |
| `_build_slash_command` | 146 | private | `str` | No | Assemble `/imagine prompt:` with image URLs, `--no`, `--ar`, `--stylize`, `--chaos`, `--weird`, `--tile`, `--raw`, `--v` |
| `_copy_to_clipboard` | 200 | private | None | No | `clip` / `pbcopy` / `xclip` per platform |
| `validate_auth` | 232 | public | `Tuple[bool, str]` | No | Always valid — auth happens in the Midjourney web session |
| `get_models` | 241 | public | `Dict[str, str]` | No | The `MODELS` map |
| `get_default_model` | 245 | public | `str` | No | `v7` |
| `get_supported_features` | 249 | public | `List[str]` | No | generate, reference_image, negative_prompt, aspect_ratio, style/quality/seed/chaos/weird control, tile, raw |
| `get_api_key_url` | 265 | public | `str` | No | Midjourney account page |
| `supports_web_interface` | 269 | public | `bool` | No | True — signals the GUI to embed the web view |
| `get_web_url` | 273 | public | `str` | No | Configured web URL |

---

### Midjourney Provider (manual/instruction-image variant)
**Path**: `providers/midjourney_provider.py` - 278 lines
**Purpose**: Alternative manual-mode Midjourney backend that renders a PNG
"instruction card" showing the Discord command. **Not registered** in
`providers/__init__.py`; `providers/midjourney.py` is the live implementation.
**Language**: Python

#### Classes

##### `MidjourneyProvider(ImageProvider)` (line 17)
Class flag `_first_time_shown` gates the first-run message. Defaults to the
official Midjourney Discord server ID.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 23 | constructor | None | No | Manual mode; stores Discord server/channel IDs and `last_command` |
| `generate` | 32 | public | `bytes` | No | Build the `/imagine` command from model_version/ar/stylize/chaos/weird/quality/seed/negative, copy it, and return an instruction PNG |
| `_copy_to_clipboard` | 101 | private | None | No | Platform clipboard write; on Linux tries xclip → xsel → wl-copy (Wayland) |
| `_open_discord` | 126 | private | None | No | Open `discord.com/channels/@me` in the browser |
| `_open_discord_channel` | 135 | private | None | No | Open the configured server/channel, falling back to generic Discord |
| `_generate_instruction_image` | 145 | private | `bytes` | No | Draw an 800x600 Discord-themed PNG with the command and step-by-step instructions (PIL) |
| `get_models` | 255 | public | `list` | No | v7, v6.1, v6, v5.2, v5.1, v5, niji6, niji5 |
| `get_default_model` | 268 | public | `str` | No | `v7` |
| `validate_auth` | 272 | public | `Tuple[bool, str]` | No | Always valid in manual mode |
| `get_last_command` | 276 | public | `Optional[str]` | No | The most recently generated Discord command |

---

### Ollama Provider
**Path**: `providers/ollama.py` - 253 lines
**Purpose**: Local Ollama server backend. Ollama's vision models describe rather
than draw, so `generate()` returns text outputs and an empty image list.
**Language**: Python

#### Classes

##### `OllamaProvider(ImageProvider)` (line 12)
Class constant `VISION_MODELS` lists the multimodal families recognized as
vision-capable (llava*, bakllava, moondream, dolphin-*). No API key is used;
the endpoint defaults to `http://localhost:11434`, and the installed-model list
is cached in `_cached_models`.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 22 | constructor | None | No | Reads the endpoint, nulls the API key, clears the model cache |
| `_is_vision_model` | 35 | private | `bool` | No | Substring match of a model name against `VISION_MODELS` |
| `_fetch_installed_models` | 48 | private | `Dict[str, str]` | No | Query the Ollama server's tag list for installed models |
| `get_models` | 87 | public | `Dict[str, str]` | No | Cached model map; warns and returns `{}` when the server is unreachable |
| `get_default_model` | 104 | public | `str` | No | First available (preferring vision) model |
| `validate_auth` | 124 | public | `Tuple[bool, str]` | No | Ping the local server instead of checking a key |
| `generate` | 150 | public | `Tuple[List[str], List[bytes]]` | No | POST the prompt to Ollama and return the text response with an empty image list |
| `get_supported_features` | 232 | public | `List[str]` | No | `["generate", "text-generation"]` |
| `get_api_key_url` | 241 | public | `str` | No | `https://ollama.ai/library` (documentation, not a key page) |
| `refresh_models` | 250 | public | `Dict[str, str]` | No | Invalidate the cache and re-fetch |

---

### Video Provider Registry (Lip-Sync)
**Path**: `providers/video/__init__.py` - 66 lines
**Purpose**: Backend selection for lip-sync video generation.
**Language**: Python

#### Classes

##### `LipSyncBackend(Enum)` (line 9)
`MUSETALK = "musetalk"`, `DID = "did"` (D-ID cloud API, reserved for future use).

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `get_lipsync_provider` | 15 | public | `BaseLipSyncProvider` | No | Instantiate the requested backend; `DID` raises `NotImplementedError` |
| `get_available_lipsync_backends` | 37 | public | `list` | No | Probe each backend's `is_available()` and return only the installed ones |

---

### Lip-Sync Provider Base
**Path**: `providers/video/base_lipsync.py` - 118 lines
**Purpose**: Abstract interface for lip-sync backends: take a video/image plus an
audio track and produce a video whose mouth movement matches the audio.
**Language**: Python

#### Classes

##### `BaseLipSyncProvider` (line 11)
`ABC` requiring `generate`, `is_available`, and `get_install_prompt`; the format
lists and `validate_inputs` are shared defaults.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `@abstractmethod generate` | 20 | public | `Path` | No | Produce the lip-synced video, auto-naming the output when none is given |
| `@abstractmethod is_available` | 42 | public | `bool` | No | Whether the backend is installed and usable |
| `@abstractmethod get_install_prompt` | 52 | public | `str` | No | User-facing install instructions |
| `get_name` | 61 | public | `str` | No | Class name minus the `Provider` suffix |
| `get_supported_video_formats` | 65 | public | `list` | No | `.mp4 .avi .mov .mkv .webm` |
| `get_supported_image_formats` | 69 | public | `list` | No | `.jpg .jpeg .png .bmp .webp` |
| `get_supported_audio_formats` | 73 | public | `list` | No | `.wav .mp3 .m4a .aac .flac .ogg` |
| `validate_inputs` | 77 | public | `tuple[bool, str]` | No | Existence + extension checks for both inputs |
| `get_parameters_schema` | 111 | public | `Dict[str, Any]` | No | Backend-specific parameter schema (empty by default) |

---

### MuseTalk Lip-Sync Provider
**Path**: `providers/video/musetalk_provider.py` - 467 lines
**Purpose**: Local MuseTalk inference — detect face/pose, extract Whisper audio
features, synthesize mouth movement per frame, composite, and encode with audio.
**Language**: Python

#### Classes

##### `MuseTalkProvider(BaseLipSyncProvider)` (line 19)
Model weights are located through `core.musetalk_installer`
(`check_musetalk_installed`, `get_musetalk_model_path`). All four sub-models
(`_musetalk`, `_dwpose`, `_vae`, `_whisper`) load lazily on first `generate()`,
guarded by `_models_loaded`.

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 30 | constructor | None | No | Resolve the model directory and null out the four lazy model handles |
| `is_available` | 45 | public | `bool` | No | Delegates to `check_musetalk_installed()` |
| `get_install_prompt` | 52 | public | `str` | No | Download sizes (~2 GB packages + ~2.5 GB weights) and GPU/disk requirements |
| `generate` | 65 | public | `Path` | No | Full pipeline: validate → load models → frames (image or video) → Whisper features → lip-sync frames → encode; `bbox_shift` tunes mouth openness |
| `_load_models` | 144 | private | None | No | One-time load of all sub-models |
| `_load_musetalk_model` | 174 | private | model | No | Load the MuseTalk UNet weights |
| `_load_dwpose_model` | 195 | private | model | No | Load the DWPose face/pose detector |
| `_load_vae_model` | 207 | private | model | No | Load the VAE used for latent encode/decode |
| `_load_whisper_model` | 222 | private | model | No | Load Whisper for audio feature extraction |
| `_image_to_frames` | 234 | private | `List[np.ndarray]` | No | Repeat a still image into a frame sequence sized by the audio duration |
| `_extract_video_frames` | 257 | private | `List[np.ndarray]` | No | Decode an input video into frames |
| `_extract_audio_features` | 293 | private | `np.ndarray` | No | Whisper feature extraction from the audio track |
| `_generate_lipsync_frames` | 342 | private | `List[np.ndarray]` | No | Per-frame mouth synthesis and compositing back onto the source |
| `_encode_video` | 385 | private | None | No | Mux frames + audio into the output file via ffmpeg |
| `get_parameters_schema` | 457 | public | `Dict[str, Any]` | No | Exposes `bbox_shift` (integer, −7..7, default 0) to the GUI |

---

## GUI — Main Window

### MainWindow (application shell)
**Path**: `gui/main_window.py` - 9138 lines
**Purpose**: The PySide6 application shell. Builds and owns every top-level tab (Image/Generate, Templates, Video, Layout, Settings, Help, History, Batch Jobs), the menu bar and status bar; drives the image-generation pipeline through a `QThread` worker; manages provider/model/LLM selection, reference images, upscaling and resolution logic; persists all UI state to `ConfigManager`; and hosts auxiliary integrations (Google Cloud auth, Midjourney watcher, Discord Rich Presence, Layout cross-tab handoff).
**Language**: Python

#### Table of Contents
| Section | Line |
|---------|------|
| Module docstring / imports | 1 |
| `ISSUES_URL` constant | 14 |
| `GCloudStatusChecker` | 31 |
| Deferred core/provider/gui imports | 56 |
| `ProviderAuthTester` | 112 |
| `MainWindow` | 138 |
| `MainWindow.CustomWebPage` (nested in `_init_help_tab`) | 2090 |
| `MainWindow.CustomHelpBrowser` (nested in `_init_help_tab`) | 2312 |

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `logger` | 11 | variable | Module logger (`logging.getLogger(__name__)`) |
| `ISSUES_URL` | 14 | constant | Single source of truth for the GitHub issue tracker URL (Help tab + error-report dialog) |

**Import note**: PySide6 imports are wrapped in `try/except ImportError` (lines 16–28) and re-raised as `ImportError("PySide6 is required for GUI mode")`, so CLI use never requires Qt. `core`/`providers`/`gui` imports sit *after* `GCloudStatusChecker` (line 56 onward); the video tab, `ModelBrowserDialog`, `LocalSDWidget` and `gui.settings_widgets` are deferred/optional so startup stays fast and degrades gracefully.

---

### Class: `GCloudStatusChecker`
**Line**: 31–53 · Base: `QThread`
**Purpose**: Background thread that runs the blocking `gcloud` subprocess calls (`check_gcloud_auth_status`, `get_gcloud_project_id`) off the GUI thread.

#### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| `status_checked` | 35 | `(bool, str)` | `(is_authenticated, status_message)` |
| `project_id_fetched` | 36 | `(str)` | Active gcloud project ID (emitted only when authenticated) |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `run` | 38 | public | — | No (QThread) | Queries gcloud auth status and project ID, emitting results; exceptions are converted into a `status_checked(False, "Error: …")` emission |

---

### Class: `ProviderAuthTester`
**Line**: 112–135 · Base: `QThread`
**Purpose**: Background thread that validates provider credentials (`provider.validate_auth()`) without blocking the GUI. Staged for the dialog-UX TLC main-window batch (`Plans/DialogUX-TLC-Plan.md` Batch 3) — `_save_and_test` is intended to move its `validate_auth()` call here.

#### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| `auth_tested` | 120 | `(bool, str)` | `(is_valid, message)` |

#### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 122 | constructor | None | No | Stores `provider_name` and `provider_config` |
| `run` | 127 | public | — | No (QThread) | Builds the provider via `get_provider()`, calls `validate_auth()`, emits the result (errors emitted as `(False, "Error: …")`) |

---

### Class: `MainWindow`
**Line**: 138–9135 · Base: `QMainWindow`
**Purpose**: Main application window; owns all tabs, generation state, and configuration persistence.

#### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| `api_keys_updated` | 142 | `()` | Emitted when API keys are saved/updated; wired to `_refresh_provider_combos` |

#### Key Instance State (set in `__init__`, line 144)
| Attribute | Line | Type | Description |
|-----------|------|------|-------------|
| `config` | 148 | `ConfigManager` | Central config/API-key accessor (always via `get_api_key()`) |
| `thumbnail_cache` | 155 | `ThumbnailCache` | LRU thumbnail cache (max 200) for the history table |
| `current_provider` | 159 | `str` | Active image provider; legacy `imagen_customization` is migrated to `google` (163–165) |
| `current_api_key` | 167 | `str` | Resolved key for the active provider |
| `current_model` | 168 | `str` | Active image model |
| `_selected_models_per_provider` | 173 | `dict` | Per-provider model memory across provider switches |
| `_selected_llm_models_per_provider` | 174 | `dict` | Per-LLM-provider model memory |
| `_current_llm_provider` | 175 | `str` | Current LLM provider name (default `"None"`) |
| `history_paths` | 185 | `List[Path]` | Disk scan of previously generated images |
| `history` / `history_loaded_count` / `history_initial_load_size` | 188–190 | `list` / `int` / `int` | In-memory history and lazy-load bookkeeping (first 50 loaded synchronously) |
| `gen_thread` / `gen_worker` | 192–193 | `QThread` / `GenWorker` | Async generation worker pair |
| `history_loader_thread` / `history_loader_worker` | 194–195 | `QThread` / `HistoryLoaderWorker` | Background history metadata loader |
| `ollama_detection_thread` / `ollama_detection_worker` | 196–197 | `QThread` / `OllamaDetectionWorker` | Background local-LLM model detection |
| `current_image_data` | 198 | `Optional[bytes]` | Bytes of the image currently displayed |
| `upscaling_settings` | 202 | `dict` | Defaults to Lanczos auto-upscale enabled |
| `midjourney_watcher` / `midjourney_session_id` | 205–206 | — | Downloads-folder watcher + current session tracking |
| `_pending_layout_region_id` | 593 | `Optional[str]` | Layout region awaiting the next generated image |
| `_layout_fill_plan` | 594 | `Optional[FillPlan]` | Drives layout-complete "fill every region" mode |

`__init__` (144) also cleans debug images, scans disk history, builds the UI (`_init_ui`), preloads the provider, restores geometry + UI state, and starts the background history/Ollama loaders — printing progress to stdout and the status bar throughout.

#### Methods — Lifecycle, Window & Events
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 144 | constructor | None | No | Full application bootstrap (see state table above) |
| `_set_app_icon` | 6980 | private | — | No | Sets the window/application icon |
| `_restore_geometry` | 7507 | private | — | No | Restores saved window geometry from config |
| `eventFilter` | 7521 | public (Qt) | `bool` | No | Prompt-editor filter: Ctrl+Enter generates, Ctrl+F opens Find |
| `resizeEvent` | 7541 | public (Qt) | — | No | Debounces window resizes before rescaling the displayed image |
| `showEvent` | 7556 | public (Qt) | — | No | Scales the initial image when the window first shows |
| `_perform_image_resize` | 7566 | private | — | No | Executes the debounced image rescale |
| `closeEvent` | 7590 | public (Qt) | — | No | Persists all UI state, stops threads/watchers on close |
| `eventFilter` | 7832 | public (Qt) | `bool` | No | **Second definition — overrides the one at 7521 at class-creation time.** Handles history-table hover preview and keyboard navigation |
| `_cleanup_thread` | 6822 | private | — | No | Tears down the finished generation worker/thread |

#### Methods — UI & Tab Construction
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_init_ui` | 559 | private | — | No | Creates the status bar, `QTabWidget` and all tabs (Image, Templates, Video placeholder, Layout, Settings, Help, History, Batch Jobs); wires the Layout tab's `sendToImageRequested` / `fillAllRequested` handoff signals |
| `_refresh_provider_combos` | 639 | private | — | No | Repopulates the Image- and Settings-tab provider combos from `list_providers()` after keys change, preserving selection |
| `_init_menu` | 680 | private | — | No | Builds the menu bar (File/project actions, tools, help) |
| `_init_generate_tab` | 757 | private | — | No | Builds the Image/Generate tab: LLM provider+model row, image provider+model row, prompt editor, reference-image panel, settings selectors, preview pane and action buttons |
| `_open_social_sizes_dialog` | 1565 | private | — | No | Opens the social-media size picker and applies the chosen resolution to `resolution_selector` |
| `_init_settings_tab` | 1606 | private | — | No | Builds the scrollable Settings tab (provider keys, auth mode, gcloud, Midjourney, Discord RPC, appearance) |
| `_init_help_tab` | 2077 | private | — | No | Builds the Help tab — QWebEngineView when available (with `CustomWebPage`), otherwise a `CustomHelpBrowser` QTextBrowser fallback; loads README as anchored HTML |
| `_init_templates_tab` | 3172 | private | — | No | Builds the Templates tab |
| `_init_history_tab` | 3232 | private | — | No | Builds the History tab: `QTableView` + `HistoryTableModel`/`HistoryFilterProxyModel`, thumbnail delegate, search and date filters |
| `_on_tab_changed` | 7879 | private | — | No | Tab-switch handling (triggers help render, lazy video-tab load, refreshes) |
| `_load_video_tab` | 7911 | private | — | No | Lazily imports and installs the real `VideoProjectTab` on first access |

#### Methods — Console & Status
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_append_to_console` | 348 | private | — | No | Appends a colored/separator message to the status console and mirrors it to the logger |
| `_auto_resize_console` | 388 | private | — | No | Deprecated no-op (console no longer auto-resizes) |

#### Methods — History Loading (background)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_on_show_all_images_toggled` | 281 | private | — | No | Stops the loader and reloads history under the new "show all images" filter |
| `_load_history_from_disk` | 392 | private | — | No | Loads history entries + sidecar metadata into memory (initial slice or all) |
| `_start_background_history_loader` | 457 | private | — | No | Spawns `HistoryLoaderWorker` on a `QThread` for the remaining entries |
| `_on_history_batch_loaded` | 482 | private | — | No | Slot: merges a loaded batch into the history model |
| `_on_history_load_progress` | 489 | private | — | No | Slot: shows loading progress in the status bar |
| `_on_history_load_finished` | 495 | private | — | No | Slot: finalizes/refreshes the table when loading completes |
| `_on_history_load_error` | 508 | private | — | No | Slot: logs/reports a background loading error |

#### Methods — Ollama Detection (background)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_start_background_ollama_detection` | 514 | private | — | No | Spawns `OllamaDetectionWorker` to probe local Ollama models |
| `_on_ollama_models_detected` | 535 | private | — | No | Slot: stores/exposes detected local models |
| `_on_ollama_not_available` | 541 | private | — | No | Slot: handles "Ollama not installed/running" |
| `_on_ollama_detection_finished` | 545 | private | — | No | Slot: cleans up the detection thread |
| `_on_ollama_detection_error` | 554 | private | — | No | Slot: logs a detection failure |

#### Methods — History Tab (search, dates, entries)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_parse_partial_date` | 3408 | `@staticmethod` | `Optional[QDate]` | No | Parses partial/full date strings into a `QDate` |
| `_apply_history_search` | 3427 | private | — | No | Applies text + date filters to the proxy model |
| `_clear_history_search` | 3436 | private | — | No | Clears filters and resets the date range |
| `_init_history_date_defaults` | 3441 | private | — | No | Seeds the date fields with earliest entry → today |
| `_parse_ts_to_qdate` | 3455 | `@staticmethod` | `Optional[QDate]` | No | Converts a float/ISO timestamp to `QDate` |
| `_show_calendar_popup` | 3473 | private | — | No | Shows a calendar popup for a date field |
| `_on_calendar_picked` | 3495 | private | — | No | Applies the picked calendar date |
| `_set_date_today` | 3501 | private | — | No | Sets a date field to today |
| `_update_history_count` | 3507 | private | — | No | Updates the visible/total history count label |
| `_on_history_item_double_clicked` | 7729 | private | — | No | Loads a double-clicked entry into the Image or Video tab |
| `_load_history_item` | 7809 | private | — | No | Loads an entry and switches to the Generate tab |
| `_load_selected_history` | 7814 | private | — | No | Loads the currently selected history row |
| `_clear_history` | 7820 | private | — | No | Clears the in-memory history list and table |
| `_add_to_history_table` | 8957 | private | — | No | Inserts a single new entry into the table model |
| `add_to_history` | 8962 | **public** | — | No | Public API used by other tabs (e.g. Video) to append a history entry |
| `_check_for_external_images` | 8967 | private | — | No | Detects images added to the output folder outside the app |
| `_refresh_history_table` | 9008 | private | — | No | Rebuilds the table from the current history list |

#### Methods — Provider & Model Selection
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_find_model_in_combo` | 3517 | private | `int` | No | Locates a model by ID in a combo box, returning its index |
| `_update_model_list` | 3540 | private | — | No | Repopulates the image-model combo for the active provider |
| `_update_advanced_visibility` | 3611 | private | — | No | Shows/hides the advanced settings panel per provider |
| `_on_video_image_provider_changed` | 3798 | private | — | No | Mirrors an image-provider change made on the Video tab |
| `_on_image_provider_changed` | 3827 | private | — | No | Image-tab provider switch: reloads models, keys, auth UI and per-provider selections |
| `_on_model_changed` | 3975 | private | — | No | Model switch: updates capabilities, resolution/aspect options and auth checks |
| `_check_nano_banana_pro_requirements` | 4045 | private | — | No | Detects models with special auth requirements (`MODEL_AUTH_REQUIREMENTS`) and warns |
| `_show_model_auth_dialog` | 4065 | private | — | No | Shows the appropriate auth-requirement dialog for the selected model |
| `_on_provider_changed` | 4149 | private | — | No | Settings-tab provider switch (keeps Image tab and config in sync) |
| `_update_generate_button_for_provider` | 4282 | private | — | No | Adjusts Generate button text/tooltip for the provider + settings (e.g. Midjourney) |

#### Methods — LLM Provider/Model Combos
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `get_llm_providers` | 3626 | `@staticmethod` | — | No | **Public**: list of available LLM providers (from `core.llm_models`) |
| `get_llm_models_for_provider` | 3633 | `@staticmethod` | — | No | **Public**: model list for one LLM provider |
| `populate_llm_combo` | 3644 | **public** | — | No | Fills a provider+model combo pair and restores the current selection |
| `_on_llm_provider_changed` | 3684 | private | — | No | Image-tab LLM provider change; restores that provider's remembered model |
| `_on_llm_model_changed` | 3724 | private | — | No | Image-tab LLM model change; persists per-provider choice |
| `_on_video_llm_provider_changed` | 3754 | private | — | No | Mirrors an LLM provider/model change made on the Video tab |

#### Methods — Generation Settings, Sizing & Upscaling
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_on_aspect_ratio_changed` | 4298 | private | — | No | Handles aspect-ratio selection |
| `_on_resolution_changed` | 4317 | private | — | No | Handles explicit resolution selection |
| `_on_resolution_mode_changed` | 4336 | private | — | No | Switches between aspect-ratio and resolution modes |
| `_on_quality_settings_changed` | 4348 | private | — | No | Handles quality/style selector changes |
| `_on_nbp_quality_changed` | 4353 | private | — | No | Handles Nano Banana Pro quality-tier change (and its max resolution) |
| `_on_advanced_settings_changed` | 4381 | private | — | No | Stores advanced-panel settings |
| `_update_cost_estimate` | 4385 | private | — | No | Recomputes the cost estimate for the current model/batch |
| `_on_upscaling_changed` | 4965 | private | — | No | Stores upscaling selector settings |
| `_get_target_resolution` | 4973 | private | `tuple` | No | Resolves the target (width, height) from the current UI settings |
| `_get_provider_max_resolution` | 4985 | private | `int` | No | Maximum native resolution for the active provider/model |
| `test_dimension_logic` | 5002 | **public** | — | No | Self-test helper that exercises the dimension/upscaling decision logic |
| `_update_upscaling_visibility` | 5056 | private | — | No | Shows/hides the upscaling selector based on target vs. native size |
| `_get_resolution_for_aspect_ratio` | 5850 | private | `str` | No | Maps an aspect ratio + provider to a concrete resolution string |
| `_find_closest_aspect_ratio` | 5882 | private | `str` | No | Picks the nearest supported aspect ratio for a target size |

#### Methods — Generation Pipeline & Image Display
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_generate` | 5134 | private | — | No | Main generation entry point: validates the prompt, applies edit-mode prefix, blocks literal pixel dimensions in prompt text (with a "Remove and Continue" dialog), assembles provider kwargs and starts the `GenWorker` thread |
| `_process_image_for_resolution_with_original` | 5916 | private | — | No | Post-processes to the target resolution, returning both original and processed bytes when cropping occurred |
| `_process_image_for_resolution` | 6054 | private | `bytes` | No | Scales/crops the returned image to the selected resolution |
| `_on_progress` | 6144 | private | — | No | Slot: streams worker progress into the console |
| `_on_error` | 6150 | private | — | No | Slot: reports generation errors and re-enables the UI |
| `_on_streaming_partial` | 6163 | private | — | No | Slot: shows a streamed partial frame in the preview pane |
| `_on_generation_finished` | 6285 | private | — | No | Slot: handles success — Midjourney web-mode redirect, resolution post-processing, auto-save + sidecars, history insert, layout placement, Discord presence reset |
| `_display_image` | 6581 | private | — | No | Renders image bytes into the output label, scaled proportionally |
| `_enable_original_toggle` | 314 | private | — | No | Enables the original/cropped toggle after a crop occurred |
| `_toggle_original_image` | 323 | private | — | No | Swaps the preview between original and cropped versions |
| `_save_image_as` | 6650 | private | — | No | Save-as dialog for the current image (writes sidecar metadata) |
| `_copy_image_to_clipboard` | 6804 | private | — | No | Copies the current image to the clipboard |
| `_load_image_file` | 7239 | private | — | No | Loads an image file from disk into the preview and state |

#### Methods — OpenAI Batch Jobs
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_submit_current_as_batch` | 6719 | private | — | No | Confirmation dialog, then submits the current prompt as a Batch API job |
| `_refresh_batch_jobs_subtab` | 6763 | private | — | No | Repopulates the Batch Jobs table from `BATCH_JOBS_PATH` |
| `_check_batch_job_action` | 6791 | private | — | No | Per-row action: checks/collects a batch job's status |

#### Methods — Layout Cross-Tab Handoff (Phase 5b)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_configure_image_for_region` | 6183 | private | — | No | Sets prompt + resolution for a layout region, marks it pending and switches to the Image tab; every step guarded so a handoff can never destabilize the tab |
| `_on_layout_send_to_image` | 6210 | private | — | No | Single-region handoff — wraps the payload as a one-element fill plan |
| `_on_layout_fill_all` | 6219 | private | — | No | Layout-complete mode — builds a plan across every prompted image region |
| `_begin_layout_fill` | 6235 | private | — | No | Creates the `core.layout.fill_plan.FillPlan` and configures its first region |
| `_clear_layout_handoff` | 6242 | private | — | No | Drops any pending handoff so a later normal generation can't be misrouted (called on every failure path) |
| `_maybe_place_image_in_layout` | 6248 | private | — | No | Places the generated image into its region via `tab_layout.set_region_content()`, then advances or finishes the fill plan |

#### Methods — Reference Images
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_update_imagen_reference_visibility` | 4166 | private | — | No | Shows the multi-reference panel only for providers that support it |
| `_on_imagen_references_changed` | 4189 | private | — | No | Reacts to reference-set changes (hint label, edit mode, persistence) |
| `_on_use_current_image_as_reference` | 4220 | private | — | No | "Use Current Image" from the reference widget (replace or add mode) |
| `_update_reference_hint_label` | 4258 | private | — | No | Updates the hint shown next to the Prompt label |
| `_open_reference_image` | 4909 | private | — | No | Opens the reference-image analysis dialog and inserts the generated description |
| `_toggle_image_settings` | 8145 | private | — | No | Expands/collapses the image-settings panel |
| `_toggle_ref_image_settings` | 8162 | private | — | No | Expands/collapses the reference-image panel |
| `_update_ref_toggle_text` | 8175 | private | — | No | Refreshes the reference toggle label with a count badge |
| `_select_reference_image` | 8230 | private | — | No | File dialog to pick a reference image |
| `_clear_reference_image` | 8292 | private | — | No | Clears the selected reference image |
| `_use_current_as_reference` | 8314 | private | — | No | Promotes the displayed image to reference image |
| `_update_use_current_button_state` | 8368 | private | — | No | Enables/disables the "Use Current Image" button |
| `_on_ref_image_toggled` | 8389 | private | — | No | Reference-image checkbox toggle |
| `_on_ref_style_changed` | 8399 | private | — | No | Reference style change |
| `_on_ref_position_changed` | 8405 | private | — | No | Reference position change |
| `_on_ref_type_changed` | 8411 | private | — | No | Reference type change (`ReferenceImageType`) |
| `_on_ref_usage_changed` | 8417 | private | — | No | Reference usage-text change |
| `_update_ref_instruction_preview` | 8423 | private | — | No | Previews the reference instruction that will be injected into the prompt |
| `_save_reference_image_to_config` | 8494 | private | — | No | Persists the reference image path |
| `_clear_reference_image_from_config` | 8509 | private | — | No | Removes the reference image from config |
| `_load_reference_image_from_config` | 8518 | private | — | No | Restores the reference image on startup |
| `_save_imagen_references_to_config` | 8581 | private | — | No | Persists the Imagen multi-reference set |
| `_load_imagen_references_from_config` | 8599 | private | — | No | Restores the Imagen multi-reference set |

#### Methods — Settings, Keys & Google Cloud Auth
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_open_api_key_page` | 4438 | private | — | No | Opens the provider's API-key documentation page |
| `_open_model_browser` | 4455 | private | — | No | Opens the Local SD model browser dialog |
| `_browse_downloads_folder` | 4478 | private | — | No | Picks the Midjourney downloads folder |
| `_on_midjourney_discord_fields_changed` | 4490 | private | — | No | Persists Discord server/channel IDs as they are edited |
| `_on_midjourney_use_discord_toggled` | 4502 | private | — | No | Persists the "Use Discord" setting and updates the button label |
| `_save_and_test` | 4509 | private | — | No | Saves every provider key + setting, emits `api_keys_updated`, then validates the active provider |
| `_toggle_auto_copy` | 4643 | private | — | No | Toggles auto-copy-filename behavior |
| `_apply_appearance` | 4649 | private | — | No | Applies and persists the theme setting immediately |
| `_update_auth_visibility` | 4663 | private | — | No | Shows API-key vs. gcloud widgets per provider/auth mode |
| `_on_auth_mode_changed` | 4682 | private | — | No | Handles the api-key ⇄ gcloud auth-mode switch |
| `_test_discord_channel` | 4700 | private | — | No | Opens the configured Discord channel to verify it |
| `_check_gcloud_status` | 4733 | private | — | No | Starts `GCloudStatusChecker` (async, non-blocking) |
| `_on_gcloud_status_checked` | 4747 | private | — | No | Slot: applies auth status to the Settings UI |
| `_on_project_id_fetched` | 4769 | private | — | No | Slot: fills the project-ID field |
| `_authenticate_gcloud` | 4775 | private | — | No | Runs `gcloud auth application-default login` |
| `_on_project_id_changed` | 4815 | private | — | No | Persists manual project-ID edits |
| `_open_gcloud_cli_page` | 4834 | private | — | No | Opens the gcloud CLI download page |
| `_open_cloud_console` | 4838 | private | — | No | Opens the Google Cloud Console |
| `_show_login_help` | 4842 | private | — | No | Shows Google Cloud login help |

#### Methods — Prompt Tools & Dialogs
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_on_prompt_text_changed` | 4695 | private | — | No | Reacts to prompt edits (button state, scheduled save) |
| `_enhance_prompt` | 4861 | private | — | No | Enhances the current prompt with the selected LLM |
| `_on_prompt_enhanced` | 4877 | private | — | No | Applies the enhanced prompt returned by the dialog |
| `_open_examples` | 4884 | private | — | No | Opens `ExamplesDialog` |
| `_open_prompt_generator` | 4896 | private | — | No | Opens `PromptGenerationDialog` |
| `_open_prompt_question` | 4902 | private | — | No | Opens `PromptQuestionDialog` |
| `_open_find_dialog` | 4928 | private | — | No | Opens `FindDialog` bound to the searchable widget of the current tab |
| `_open_wikimedia_search` | 9013 | private | — | No | Opens the Wikimedia Commons image search dialog and ingests downloads |
| `_open_character_prompt_builder` | 9064 | private | — | No | Opens the character prompt builder and inserts the generated prompt |
| `_open_puppet_wizard` | 9079 | private | — | No | Opens the Character Animator puppet wizard |
| `_open_font_generator` | 9086 | private | — | No | Opens the Font Generator wizard |

#### Methods — Help Tab Rendering, Markdown & Search
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_load_readme_content` | 2663 | private | `str` | No | Loads README.md for help display (optionally de-emojified) |
| `_markdown_to_html_with_anchors` | 2707 | private | `str` | No | Converts markdown to HTML with GitHub-style anchor IDs and rewritten image paths |
| `_github_slugify` | 2929 | private | — | No | Produces GitHub-style anchor slugs from header text |
| `_add_explicit_anchors` | 2943 | private | `str` | No | Injects explicit `<a>` anchors so in-page navigation works |
| `_basic_markdown_to_html` | 2962 | private | `str` | No | Dependency-free markdown→HTML fallback with anchors and UTF-8 handling |
| `_replace_emojis_with_text` | 3068 | private | `str` | No | Substitutes emoji with text equivalents for the QTextBrowser path |
| `_get_fallback_help` | 3094 | private | `str` | No | Built-in help content when README cannot be loaded |
| `_trigger_help_render` | 8005 | private | — | No | Nudges the browser to render via a minimal scroll |
| `_update_help_nav_buttons` | 8016 | private | — | No | Syncs Back/Forward button enablement with browser history |
| `_search_help_webengine` | 8025 | private | — | No | Find-in-page for the QWebEngineView help browser |
| `_search_help_textbrowser` | 8076 | private | — | No | Find-in-page for the QTextBrowser fallback |

#### Methods — Templates
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_get_template_data` | 7638 | private | — | No | Returns template definitions and their placeholders |
| `_create_template_fields` | 7675 | private | — | No | Builds input fields for the selected template's placeholders |
| `_on_template_changed` | 7698 | private | — | No | Rebuilds fields when the template selection changes |
| `_apply_template` | 7702 | private | — | No | Renders the filled template into the prompt editor |

#### Methods — Projects (save/open)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_save_project` | 7284 | private | — | No | Ctrl+S — delegates saving to the active tab (video/layout/image) |
| `_save_project_as` | 7373 | private | — | No | Save-as, delegated to the active tab |
| `_open_project` | 7386 | private | — | No | Open-project dialog, delegated to the active tab |
| `_load_project_file` | 7407 | private | — | No | Loads a project JSON file and restores its state |

#### Methods — Midjourney Integration & Discord Rich Presence
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_open_midjourney_external_browser` | 6830 | private | — | No | Opens Midjourney in the system browser with the slash command ready |
| `_open_midjourney_web_dialog` | 6878 | private | — | No | Opens the embedded Midjourney web dialog for manual generation |
| `_on_midjourney_image_ready` | 6944 | private | — | No | Handles the user signalling that a Midjourney image is ready |
| `_init_midjourney_watcher` | 6950 | private | — | No | Starts the downloads-folder watcher when enabled |
| `_init_discord_rpc` | 7004 | private | — | No | Initializes Discord Rich Presence (`pypresence`) if enabled |
| `_on_discord_status_changed` | 7036 | private | — | No | Slot: reflects RPC connection status in the UI |
| `_on_discord_enabled_changed` | 7046 | private | — | No | Enables/disables presence and persists the choice |
| `_on_discord_settings_changed` | 7065 | private | — | No | Persists privacy/detail checkboxes and re-applies presence |
| `_test_discord_connection` | 7098 | private | — | No | Tests the RPC connection and prints diagnostics |
| `_update_discord_presence` | 7116 | private | — | No | Publishes the current `ActivityState` (e.g. GENERATING/IDLE) |
| `_on_midjourney_session_started` | 7126 | private | — | No | Records the start of a Midjourney session |
| `_on_midjourney_session_ended` | 7134 | private | — | No | Clears session tracking |
| `_on_midjourney_image_detected` | 7140 | private | — | No | Handles a watcher-detected download with confidence data |
| `_process_midjourney_image` | 7178 | private | — | No | Imports an accepted Midjourney image (sidecar, history, preview) |

#### Methods — UI State Persistence
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_schedule_ui_save` | 3735 | private | — | No | Debounces UI-state saves behind a `QTimer` |
| `_delayed_ui_save` | 3746 | private | — | No | Timer callback that performs the save |
| `_save_ui_state` | 8616 | private | — | No | Writes every widget's state (providers, models, prompt, sizing, references, toggles) to config |
| `_restore_ui_state` | 8718 | private | — | No | Restores all widget state on startup, populating combos before restoring selections |

#### Methods — Diagnostics
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `_show_log_location` | 9093 | private | — | No | Shows where platform-specific log files live |
| `_show_error_reporting` | 9111 | private | — | No | Shows how to report errors (links `ISSUES_URL`) |

---

#### Nested Class: `MainWindow.CustomWebPage`
**Line**: 2090–2158 · Defined inside `_init_help_tab` · Base: `QWebEnginePage`
**Purpose**: Help-browser page policy — routes `http/https/ftp` links to the system browser and renders local `.md` links (README/CHANGELOG) in-place as anchored HTML.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 2092 | constructor | None | No | Stores the owning `main_window` reference |
| `acceptNavigationRequest` | 2096 | public (Qt) | `bool` | No | Intercepts navigation: external URLs open in the OS browser (returns `False`); local markdown link clicks are converted via `_markdown_to_html_with_anchors` and injected with `setHtml`, then scrolled to top |

#### Nested Class: `MainWindow.CustomHelpBrowser`
**Line**: 2312–2553 · Defined inside `_init_help_tab` · Base: `QTextBrowser`
**Purpose**: QTextBrowser fallback used when QWebEngine is unavailable; implements its own anchor history with back/forward/home navigation and keyboard/mouse shortcuts.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 2313 | constructor | None | No | Sets up `anchor_history`, `history_index`, parent-window ref and the `anchorClicked` interception flag |
| `handle_anchor_click` | 2323 | public | — | No | Handles all link clicks (in-page anchors, local markdown, external URLs) |
| `add_to_history` | 2395 | public | — | No | Pushes an anchor onto the navigation history |
| `go_back` | 2408 | public | — | No | Navigates back one history entry |
| `go_forward` | 2455 | public | — | No | Navigates forward one history entry |
| `go_home` | 2502 | public | — | No | Scrolls to the top of the document |
| `update_nav_buttons` | 2515 | public | — | No | Syncs Back/Forward enablement with the internal history |
| `keyPressEvent` | 2523 | public (Qt) | — | No | Keyboard shortcuts (navigation/search) |
| `mousePressEvent` | 2541 | public (Qt) | — | No | Mouse back/forward button navigation |

#### Nested Helper Functions (closures)
These are local callbacks defined inside the methods above; listed for line-accurate navigation.

| Function | Line | Enclosing scope | Description |
|----------|------|-----------------|-------------|
| `trigger_initial_scroll` | 2270 | `_init_help_tab` | Runs JS to force the WebEngine view to render after initial load |
| `on_initial_load_finished` | 2281 | `_init_help_tab` | One-shot `loadFinished` handler that schedules the scroll and disconnects itself |
| `do_navigation` | 2418 | `CustomHelpBrowser.go_back` | Deferred scroll-to-anchor for back navigation |
| `do_navigation` | 2465 | `CustomHelpBrowser.go_forward` | Deferred scroll-to-anchor for forward navigation |
| `do_scroll` | 2507 | `CustomHelpBrowser.go_home` | Deferred scroll-to-top |
| `fix_image_path` | 2737 | `_markdown_to_html_with_anchors` | Regex callback rewriting relative image paths to absolute file URLs |
| `replace_header` | 2950 | `_add_explicit_anchors` | Regex callback inserting explicit anchors into header tags |
| `on_description_generated` | 4916 | `_open_reference_image` | Receives the generated reference description and inserts it into the prompt |
| `parse_ratio` | 5899 | `_find_closest_aspect_ratio` | Parses an `"W:H"` ratio string into a float |
| `handle_result` | 8046 | `_search_help_webengine` | Async find-in-page result callback |
| `on_images_downloaded` | 9020 | `_open_wikimedia_search` | Handles downloaded Wikimedia images (reference/history ingestion) |
| `on_prompt_generated` | 9071 | `_open_character_prompt_builder` | Inserts the builder-generated prompt into the prompt editor |

---

#### Notes for Navigators
- **Duplicate `eventFilter`**: `gui/main_window.py:7521` (prompt shortcuts) is shadowed by the later definition at `gui/main_window.py:7832` (history-table hover/keyboard), which is the one Qt actually calls. Prompt Ctrl+Enter / Ctrl+F handling therefore depends on the second implementation's fall-through to `super()`.
- **Largest methods** (read selectively): `_generate` `gui/main_window.py:5134`, `_init_generate_tab:757`, `_on_generation_finished:6285`, `_init_help_tab:2077`, `_init_settings_tab:1606`, `_restore_ui_state:8718`.
- **Threading**: three `QThread` workers are owned here — generation (`GenWorker`), history loading (`HistoryLoaderWorker`), Ollama detection (`OllamaDetectionWorker`) — plus the two thread classes defined in this file (`GCloudStatusChecker:31`, `ProviderAuthTester:112`). All results return to the GUI thread via signals.
- **Cross-tab contracts**: `add_to_history:8962` (public, called by other tabs), `api_keys_updated:142` → `_refresh_provider_combos:639`, and the Layout handoff pair `_on_layout_send_to_image:6210` / `_maybe_place_image_in_layout:6248`.

---

## GUI — Prompt Building & Settings

Widgets and dialogs that let the user compose, enhance, interrogate, and
parameterize image-generation prompts. `gui/settings_widgets.py` supplies the
reusable generation-parameter controls embedded in the Generate tab; the other
five modules are standalone `QDialog`s launched from `gui/main_window.py`.

---

### Settings Widgets

**Path**: `gui/settings_widgets.py` - 2198 lines
**Purpose**: Reusable PySide6 widgets for generation parameters — aspect ratio, resolution, quality/style, batch size, provider-specific advanced settings, output format, moderation, streaming toggle — plus a static cost estimator. Imported by `gui/main_window.py` to build the Generate tab's settings column.
**Language**: Python

Every widget is self-contained (`QWidget` subclass with `_init_ui()`), emits Qt
signals on change, and exposes `get_settings()` / `set_settings()` or
getter/setter pairs so the main window can persist state. Capability-driven
widgets (`OutputFormatRow`, `ModerationCheckbox`, `ThinkingProgressToggle`)
import `providers.openai.MODEL_CAPS` lazily inside `update_model()` and hide
themselves when the active model doesn't advertise the capability.

#### Classes

| Class | Line | End | Description |
|-------|------|-----|-------------|
| AspectRatioSelector | 18 | 330 | Visual AR picker: preset preview buttons plus validated custom `W:H`/decimal input |
| ResolutionSelector | 333 | 1267 | Resolution/aspect-ratio dual-mode selector with per-model maxima, AR lock, and a custom-size popup |
| QualitySelector | 1270 | 1576 | Quality/style controls, including Nano Banana Pro (NBP) and gpt-image-2 tier modes |
| BatchSelector | 1579 | 1632 | Image-count spinbox with a live cost estimate |
| AdvancedSettingsPanel | 1635 | 1969 | Collapsible panel of provider-specific advanced options |
| OutputFormatRow | 1972 | 2058 | PNG/JPEG/WebP radios plus a compression slider (capability-gated) |
| ModerationCheckbox | 2061 | 2093 | Permissive-moderation checkbox (capability-gated) |
| ThinkingProgressToggle | 2096 | 2131 | Stream-partial-frames checkbox (capability-gated) |
| CostEstimator | 2134 | 2198 | Stateless pricing calculator (class-level pricing tables) |

#### AspectRatioSelector (line 18)

Signal: `ratioChanged(str)`. Class constant `ASPECT_RATIOS` maps each preset
(1:1, 3:4, 4:3, 16:9, 9:16, 21:9) to a label, icon, and usage hint; the buttons
live in an exclusive `QButtonGroup` alongside a "Custom" toggle.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 32 | constructor | None | Set default ratio `1:1`, create the exclusive button group |
| `_init_ui` | 43 | private | None | Build the preset button row plus the hidden custom-input row |
| `_create_ratio_button` | 102 | private | QToolButton | Render a checkable button with a scaled preview rectangle |
| `_create_custom_button` | 171 | private | QToolButton | Build the "Custom" toggle button |
| `_on_ratio_clicked` | 228 | private | None | Apply a preset ratio and emit `ratioChanged` |
| `_on_custom_clicked` | 239 | private | None | Reveal the custom-input row and switch to custom mode |
| `_show_custom_input` | 257 | private | None | Show/hide the custom label, line edit, and Apply button |
| `_on_custom_input_changed` | 263 | private | None | Handle `editingFinished` on the custom field |
| `_apply_custom_ratio` | 269 | private | None | Parse `W:H` or a decimal, normalize, and emit the result |
| `set_ratio` | 304 | public | None | Programmatically select a ratio (preset or custom) |
| `get_ratio` | 324 | public | str | Current ratio string |
| `is_using_custom` | 328 | public | bool | Whether the custom entry is active |

#### ResolutionSelector (line 333)

Signals: `resolutionChanged(str)`, `modeChanged(str)` (`"resolution"` /
`"aspect_ratio"`). Class constants `MODEL_MAX_RESOLUTIONS` (per-model native max
edge, e.g. NBP 4096, NB2 2048, DALL·E 3 1792), `PROVIDER_MAX_RESOLUTIONS`
(fallback per provider), and `PRESETS` (per-provider named sizes). Spinboxes
always allow up to the upscale ceiling; model max only drives defaults and the
info text.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 388 | constructor | None | Seed provider, AR mode, width/height modes, and AR lock |
| `_init_ui` | 402 | private | None | Build mode indicator, preset combo, W/H spinboxes, lock, Reset, and Custom… button |
| `update_provider` | 519 | public | None | Repopulate presets/limits when the image provider changes |
| `_update_info_text` | 556 | private | None | Refresh the hint line (native max, upscaling notice) |
| `_on_resolution_changed` | 597 | private | None | React to preset combo selection |
| `set_mode_aspect_ratio` | 609 | public | None | Switch to AR-driven sizing and emit `modeChanged` |
| `set_mode_resolution` | 633 | public | None | Switch to explicit W×H sizing and emit `modeChanged` |
| `update_aspect_ratio` | 653 | public | None | Apply a new AR from `AspectRatioSelector` |
| `_on_width_value_changed` | 671 | private | None | Spinbox hook forwarding to `_on_width_changed` |
| `_on_width_changed` | 677 | private | None | Recompute height when the AR lock is engaged |
| `_on_height_value_changed` | 727 | private | None | Spinbox hook forwarding to `_on_height_changed` |
| `_on_height_changed` | 733 | private | None | Recompute width when the AR lock is engaged |
| `_on_width_edited` | 783 | private | None | Mark width as the last manually edited field |
| `_on_height_edited` | 787 | private | None | Mark height as the last manually edited field |
| `_reset_to_defaults` | 791 | private | None | Reset to the model's max for the current AR |
| `_toggle_lock_aspect_ratio` | 795 | private | None | Toggle the AR lock and restyle the lock button |
| `_get_provider_max` | 838 | private | int | Effective max edge for the active provider/model |
| `update_model` | 868 | public | None | Track model changes; auto-resize to the new model's max and show/hide Custom… per `MODEL_CAPS` |
| `update_max_resolution` | 913 | public | None | Externally override the max resolution (e.g. NBP tier) |
| `set_upscale_mode` | 936 | public | None | Deprecated no-op kept for backward compatibility |
| `_get_model_max` | 945 | private | int | Look up a model in `MODEL_MAX_RESOLUTIONS` |
| `_set_to_max_for_aspect_ratio` | 960 | private | None | Compute the largest W×H for the current AR within the max edge |
| `_initialize_dimensions` | 1013 | private | None | Populate initial W/H on first construction |
| `_on_size_changed` | 1035 | private | None | Compatibility entry point routed to the last-edited field |
| `_on_custom_resolution` | 1043 | private | None | Parse a typed `1920x1080` string from the combo |
| `_update_suggested_resolution` | 1059 | private | None | Rewrite the "Auto (…)" combo item with the derived size |
| `_calculate_resolution_from_ar` | 1067 | private | str | Derive a `W×H` suggestion from an aspect ratio |
| `get_resolution` | 1100 | public | str | Current resolution string (or `auto`) |
| `set_resolution` | 1108 | public | None | Restore a saved resolution, optionally without switching modes |
| `is_using_aspect_ratio` | 1170 | public | bool | Whether AR mode is active |
| `get_aspect_ratio` | 1174 | public | str | Current aspect ratio |
| `get_width_height` | 1178 | public | tuple | Resolved `(width, height)` |
| `_open_custom_size_dialog` | 1200 | private | None | Modal W/H popup validated by `core.image_size.validate_custom_size` against `MODEL_CAPS` |
| `revalidate` | 1228 | closure | None | Nested live-validation callback inside `_open_custom_size_dialog`; colors the status label and enables/disables OK |
| `get_custom_size` | 1265 | public | str \| None | `"WxH"` set by the custom-size popup, else `None` |

#### QualitySelector (line 1270)

Signals: `settingsChanged(dict)`, `nbpQualityChanged(str, int)` — the latter
carries `(quality_tier, max_resolution)` so the resolution selector can retune.
Class constant `NBP_TIERS` holds 1K/2K/4K pricing and resolution caps.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 1283 | constructor | None | Seed provider, settings dict, NBP mode flag, default `2K` tier |
| `_init_ui` | 1291 | private | None | Build the shared Quality group (standard radios, NBP tiers, gpt-image-2 tiers, style combo) |
| `update_provider` | 1386 | public | None | Swap the visible controls for the active provider |
| `update_model` | 1412 | public | None | Enable NBP / gpt-image-2 modes based on the model ID |
| `_set_nbp_mode` | 1425 | private | None | Show the Nano Banana Pro 1K/2K/4K tier radios |
| `_on_nbp_quality_changed` | 1448 | private | None | Emit `nbpQualityChanged` with the tier's max resolution |
| `get_nbp_quality` | 1467 | public | str | Selected NBP tier |
| `get_nbp_cost_per_image` | 1471 | public | float | Per-image price for the selected NBP tier |
| `_on_quality_changed` | 1477 | private | None | Emit `settingsChanged` for standard quality radios |
| `_set_gi2_mode` | 1483 | private | None | Show gpt-image-2 quality tiers |
| `_on_gi2_quality_changed` | 1497 | private | None | Handle a gpt-image-2 tier change |
| `_on_style_changed` | 1508 | private | None | Handle style-combo changes (e.g. vivid/natural) |
| `get_settings` | 1514 | public | dict | Serialize quality/style state |
| `set_settings` | 1539 | public | None | Restore quality/style state |

#### BatchSelector (line 1579)

Signal: `batchChanged(int)`. Spinbox range 1–4 with a green cost label.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 1584 | constructor | None | Default 1 image at $0.04 each |
| `_init_ui` | 1590 | private | None | Build the "Images:" spinbox and cost label |
| `_on_value_changed` | 1611 | private | None | Update count, refresh cost, emit `batchChanged` |
| `_update_cost` | 1617 | private | None | Render `≈ $total (n × $each)` |
| `set_cost_per_image` | 1625 | public | None | Set unit price (called after model/tier changes) |
| `get_num_images` | 1630 | public | int | Current batch size |

#### AdvancedSettingsPanel (line 1635)

Signal: `settingsChanged(dict)`. A toggle button expands a stacked, per-provider
options widget.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 1640 | constructor | None | Seed provider, settings dict, collapsed state |
| `_init_ui` | 1647 | private | None | Build the ▶/▼ toggle and the per-provider content container |
| `_create_google_settings` | 1689 | private | QWidget | Prompt rewriting, safety filter, person generation, Google Search grounding, seed |
| `_create_openai_settings` | 1753 | private | QWidget | Response format (URL vs base64 JSON) |
| `_create_stability_settings` | 1772 | private | QWidget | CFG scale slider and step count |
| `_create_local_sd_settings` | 1806 | private | QWidget | Inference steps and other local-SD knobs |
| `_on_cfg_changed` | 1842 | private | None | Map the CFG slider (10–150) to a 1.0–15.0 label/value |
| `_toggle_expanded` | 1848 | private | None | Expand/collapse the panel |
| `_update_setting` | 1854 | private | None | Write one key and emit `settingsChanged` |
| `update_provider` | 1859 | public | None | Swap in the matching provider page |
| `get_settings` | 1867 | public | dict | Collect all advanced values for the active provider |
| `set_settings` | 1912 | public | None | Restore advanced values into the widgets |

#### OutputFormatRow (line 1972)

Signal: `settingsChanged(dict)`. Visible only when
`MODEL_CAPS[model]['supports_output_format']`; the compression slider appears
only for `jpeg`/`webp`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 1981 | constructor | None | Build PNG/JPEG/WebP radios plus a 0–100 compression slider (default 90) |
| `update_model` | 2017 | public | None | Show/hide the group from `MODEL_CAPS`; hides on `ImportError` |
| `_on_changed` | 2026 | private | None | Toggle compression visibility and emit settings |
| `_set_compression_visible` | 2031 | private | None | Show/hide the label, slider, and value readout |
| `get_format` | 2035 | public | str | `png` / `jpeg` / `webp` |
| `get_settings` | 2042 | public | dict | `output_format` plus `output_compression` when applicable |
| `set_settings` | 2048 | public | None | Restore format and compression |

#### ModerationCheckbox (line 2061)

Signal: `settingsChanged(dict)`. Emits `{"moderation": "low"|"auto"}`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 2066 | constructor | None | Build the permissive-moderation checkbox with a usage-policy tooltip |
| `update_model` | 2081 | public | None | Visible only when `caps['supports_moderation']` |
| `get_settings` | 2089 | public | dict | `moderation` = `low` when checked, else `auto` |
| `set_settings` | 2092 | public | None | Restore the checkbox from settings |

#### ThinkingProgressToggle (line 2096)

Signal: `settingsChanged(dict)`. Emits `{"stream_partials": bool}`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 2101 | constructor | None | Build the stream-partial-frames checkbox with a cost tooltip |
| `update_model` | 2116 | public | None | Visible only when `caps['supports_streaming']` |
| `is_enabled` | 2124 | public | bool | Whether streaming partials is checked |
| `get_settings` | 2127 | public | dict | `stream_partials` flag |
| `set_settings` | 2130 | public | None | Restore the flag |

#### CostEstimator (line 2134)

Stateless helper with class-level pricing tables `NBP_PRICING` (1K/2K $0.134,
4K $0.24) and `PRICING` (google / openai / stability tiers).

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `@classmethod calculate` | 2162 | class | float | Total cost for `num_images` given provider, settings, and optional model; `gemini-3` models route to NBP tier pricing, Google falls back to 1K vs 2K, others to the provider tier table |

---

### Prompt Builder

**Path**: `gui/prompt_builder.py` - 1838 lines
**Purpose**: Non-LLM, data-driven prompt composer. Combines subject, transformation, style, medium, background, pose, purpose, technique, artist, lighting, and mood into a comma-joined prompt, with style presets, semantic tag search, exclusions, history, and JSON import/export. Opened from `gui/main_window.py:9066` (`_open_character_prompt_builder`).
**Language**: Python

Data comes from `core.prompt_data_loader.PromptDataLoader`,
`core.preset_loader.PresetLoader`, and `core.tag_searcher.TagSearcher`; loading
is deferred until the dialog is first shown. History persists to
`prompt_builder_history.json` under the config directory; combo/search state
persists via `QSettings("ImageAI", "PromptBuilder")`.

#### SavePresetDialog (line 26)

Modal form for saving the current builder state as a reusable custom preset.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 29 | constructor | None | Store the `PresetLoader`, set title/min width |
| `_init_ui` | 44 | private | None | Build the name/description/category form and buttons |
| `_on_save` | 132 | private | None | Validate required fields and persist via the loader |
| `get_preset_data` | 165 | public | dict \| None | Saved preset payload, or `None` if cancelled |

#### PromptBuilder (line 174)

`QDialog` emitting `prompt_generated(str)` when the user accepts a prompt.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 179 | constructor | None | Create loaders lazily, wire the search debounce timer, restore geometry |
| `_load_all_data` | 212 | private | None | One-shot load of prompt data, presets, tag index, and history on first show |
| `_populate_combo_boxes` | 242 | private | None | Fill style/medium/artist/lighting/mood combos (sorted, signals blocked) |
| `_populate_presets` | 281 | private | None | Fill the preset combo, ordered by popularity |
| `_init_ui` | 313 | private | None | Assemble the tab widget and dialog buttons |
| `_create_builder_tab` | 334 | private | QWidget | Build the field grid, special-instruction checkboxes, preview, and action buttons |
| `_create_history_tab` | 561 | private | QWidget | Build the history list, detail pane, and history actions |
| `_create_combo` | 618 | private | QComboBox | Helper producing an editable combo seeded with items |
| `_get_all_combos` | 626 | private | list | All eleven field combos, for bulk clear/save/restore |
| `_process_exclusions` | 642 | private | str | Turn `"hands, text"` into `"no hands, no text"` |
| `_on_subject_changed` | 661 | private | None | Auto-populate exclusions for known subjects (e.g. headshots) |
| `_update_preview` | 681 | private | None | Rebuild the ordered, comma-joined prompt preview |
| `_load_example` | 753 | private | None | Seed the fields with the built-in caricature example |
| `_clear_all` | 769 | private | None | Reset every field and checkbox |
| `_use_prompt` | 778 | private | None | Emit `prompt_generated` and accept the dialog |
| `_save_to_history` | 791 | private | None | Append the current prompt to history with confirmation |
| `_save_to_history_silent` | 832 | private | None | Same, without user feedback (used on accept) |
| `_show_history_details` | 871 | private | None | Render the selected history entry in the detail pane |
| `_load_from_history` | 899 | private | None | Load a history entry on double-click |
| `_load_selected_history` | 908 | private | None | Load the currently selected entry |
| `_delete_history_item` | 914 | private | None | Delete the selected entry and re-save |
| `_clear_all_history` | 934 | private | None | Clear the entire history after confirmation |
| `_create_preset_panel` | 954 | private | QGroupBox | "🎨 Style Presets" selector plus Save-custom button |
| `_create_search_panel` | 1006 | private | QGroupBox | "🔍 Smart Search" bar, auto-filter checkbox, results label, clear button |
| `_on_preset_selected` | 1087 | private | None | Apply a preset (index 0 is the placeholder) |
| `_load_preset` | 1123 | private | None | Push a preset's settings into the fields |
| `_on_save_custom_preset` | 1136 | private | None | Show `SavePresetDialog` and persist the current state |
| `_apply_settings` | 1211 | private | None | Restore all combos, exclusions, notes, and checkboxes from a settings dict |
| `_update_history_list` | 1233 | private | None | Rebuild the history list widget |
| `_export` | 1252 | private | None | Ask whether to export the current prompt or all history |
| `_export_current` | 1296 | private | None | Write the current prompt + settings to JSON |
| `_export_all_history` | 1343 | private | None | Write the full history to JSON |
| `_import_prompt` | 1376 | private | None | Load a prompt/settings JSON file back into the builder |
| `_load_history` | 1438 | private | None | Read `prompt_builder_history.json` |
| `_save_history` | 1451 | private | None | Write `prompt_builder_history.json` |
| `_restore_geometry` | 1464 | private | None | Restore window geometry from `QSettings` |
| `_restore_builder_state` | 1475 | private | None | Restore combo selections and search state from the last session |
| `_save_geometry` | 1534 | private | None | Persist window geometry |
| `_save_builder_state` | 1539 | private | None | Persist combo selections and search state |
| `keyPressEvent` | 1568 | override | None | Ctrl+Enter uses the prompt |
| `_save_combo_items` | 1577 | private | None | Snapshot original combo contents so search filters can be undone |
| `_on_search_text_changed` | 1597 | private | None | Debounce typing when auto-filter is on |
| `_on_auto_filter_changed` | 1622 | private | None | Toggle live filtering vs. manual search |
| `_on_search_enter_pressed` | 1644 | private | None | Run a search immediately on Enter |
| `_trigger_manual_search` | 1648 | private | None | Run a search from the Search button |
| `_execute_search` | 1658 | private | None | Debounce-timer callback that dispatches `_perform_search` |
| `_perform_search` | 1664 | private | None | Query `TagSearcher.search_by_category` and filter artist/style/medium/lighting/mood combos to the matches |
| `_clear_search_filters` | 1765 | private | None | Restore the full combo contents from the snapshot |
| `showEvent` | 1815 | override | None | Trigger first-show data loading |
| `closeEvent` | 1822 | override | None | Save geometry and builder state |
| `accept` | 1828 | override | None | Save state, then accept |
| `reject` | 1834 | override | None | Save state, then reject |

---

### Prompt Generation Dialog

**Path**: `gui/prompt_generation_dialog.py` - 1581 lines
**Purpose**: "AI Prompt Generator" — turns a free-form idea into N LLM-generated prompt variations on a background thread, with a Generate/Stop button, status console, history tab, and session restore. Imported by `gui/main_window.py:79`.
**Language**: Python

Built on the shared dialog conventions (`DialogCleanupMixin`,
`bind_primary_action`, `standard_splitter`, `persist_splitter`) and
`OperationGuardMixin` / `@guard_operation` for re-entry protection; the guard is
initialized with `block_all_input=False` so the Generate→Stop button stays
clickable mid-run. Session state uses `QSettings("ImageAI",
"PromptGenerationDialog")`, and Discord Rich Presence is updated on show.

#### LLMWorker (line 30)

`QObject` worker moved onto a `QThread`. Signals: `finished(list)`,
`error(str)`, `progress(str)`, `log_message(str, str)`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 37 | constructor | None | Capture operation, input text, variation count, provider/model/key, temperature, max tokens, reasoning effort, verbosity |
| `stop` | 54 | public | None | Set the cooperative stop flag |
| `run` | 58 | public | None | Log the full request to file + console loggers, call LiteLLM (falling back to native SDKs), parse the response into prompt variations, emit results or errors |

##### LiteLLMConsoleHandler (line 90, nested in `LLMWorker.run`)

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `emit` | 91 | override | None | Mirror LiteLLM's internal log records into the app's `console` logger |

#### PromptGenerationDialog (line 704)

`DialogCleanupMixin, QDialog, OperationGuardMixin`; signal
`promptSelected(str)`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 709 | constructor | None | Load last session, restore geometry, build UI, init the operation guard, load LLM settings |
| `init_ui` | 737 | public | None | Build the Generate/History tabs, idea input, variation count, LLM controls, results list, and status console inside vertical splitters |
| `load_llm_settings` | 980 | public | None | Read LLM provider/model/params from `ConfigManager` |
| `update_llm_models` | 1016 | public | None | Repopulate the model combo for the chosen LLM provider |
| `on_model_changed` | 1031 | public | None | Show/hide GPT-5-specific parameters (reasoning effort, verbosity) |
| `_on_generate_clicked` | 1041 | private | None | Dispatcher: Generate when idle, Stop while running |
| `_cancel_generation` | 1048 | private | None | Cancel an in-flight request at the user's request |
| `_reset_generate_button` | 1055 | private | None | Restore the button after a run or a Stop |
| `generate_prompts` | 1062 | public | None | Validate input, resolve auth mode and per-provider API key via `config.get_api_key()`, spin up `LLMWorker` on a `QThread` |
| `on_generation_finished` | 1209 | public | None | Populate the results list, retarget the primary action to OK, save the session |
| `on_generation_error` | 1260 | public | None | Surface the error in the console and a message box |
| `on_generation_progress` | 1272 | public | None | Append progress text to the status console |
| `on_log_message` | 1276 | public | None | Route worker log messages to the status console |
| `cleanup_thread` | 1280 | public | None | Quit and dispose of the worker thread |
| `on_selection_changed` | 1289 | public | None | Enable/disable OK as the selection changes |
| `on_item_double_clicked` | 1295 | public | None | Accept the double-clicked prompt |
| `load_history_item` | 1301 | public | None | Restore inputs and results from a history entry |
| `accept_selection` | 1356 | public | None | Emit `promptSelected`, record history, and accept |
| `save_last_session` | 1413 | public | None | Persist idea text, settings, and results |
| `load_last_session` | 1443 | public | dict | Read the persisted session payload |
| `restore_last_session` | 1455 | public | None | Repopulate the dialog from the saved session |
| `save_settings` | 1524 | public | None | Save window geometry and splitter states |
| `restore_settings` | 1536 | public | None | Restore window geometry and splitter states |
| `showEvent` | 1542 | override | None | Update Discord presence on show |
| `_stop_worker` | 1550 | private | None | Stop the worker and wait briefly for its thread |
| `on_dialog_close` | 1576 | public | None | `DialogCleanupMixin` hook run on every exit path (OK, Cancel, Escape, X) |

---

### Prompt Question Dialog (current)

**Path**: `gui/prompt_question_dialog.py` - 941 lines
**Purpose**: "Ask AI Anything" / "Ask About Prompt" — a multi-turn conversational dialog that answers questions about the current prompt (or general questions when no prompt is supplied), with quick-question presets, an editable prompt pane, conversation history, and a status console. Imported by `gui/main_window.py:80`; instantiated at `gui/main_window.py:4906`.
**Language**: Python

Uses `gui/llm_utils.DialogStatusConsole`, `gui/history_widget.DialogHistoryWidget`,
and `OperationGuardMixin` with `block_all_input=True`. Settings persist under
`QSettings("ImageAI", "PromptQuestionDialog")`.

#### QuestionWorker (line 23)

Signals: `finished(str)`, `error(str)`, `progress(str)`,
`log_message(str, str)`. Unlike the legacy worker it carries
`conversation_history` for multi-turn context.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 30 | constructor | None | Capture prompt, question, provider/model/key, temperature, reasoning effort, verbosity, and prior turns |
| `stop` | 45 | public | None | Set the cooperative stop flag |
| `run` | 49 | public | None | Build the message list from the conversation history, call the LLM, log request/response, emit the answer |

#### PromptQuestionDialog (line 201)

`QDialog, OperationGuardMixin`. Window title switches between "Ask About Prompt"
and "Ask AI Anything" depending on whether a prompt was passed in.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 204 | constructor | None | Seed conversation state, restore geometry, build UI, init the input-blocking guard |
| `init_ui` | 234 | public | None | Assemble the Conversation and History tabs plus the Close button |
| `create_conversation_tab` | 260 | public | QWidget | Build the editable prompt pane, quick-question combo, question box, answer view, LLM controls, and status console in a splitter |
| `update_quick_questions` | 451 | public | None | Swap the preset question list depending on whether a prompt is present |
| `toggle_prompt_edit` | 493 | public | None | Enter/leave prompt edit mode |
| `clear_prompt` | 511 | public | None | Empty the prompt field |
| `reset_prompt` | 527 | public | None | Restore the prompt passed in by the caller |
| `on_prompt_changed` | 537 | public | None | Track edits and refresh quick questions |
| `on_quick_question_selected` | 544 | public | None | Copy the chosen preset into the question box |
| `setup_shortcuts` | 549 | public | None | Bind Ctrl+Enter (ask) and Escape |
| `handle_escape` | 563 | public | None | Escape exits edit mode first, then closes the dialog |
| `ask_question` | 575 | public | None | Resolve the API key, start `QuestionWorker` on a `QThread` (guarded against re-entry) |
| `on_answer_received` | 677 | public | None | Append the turn to the conversation, render the answer, save history |
| `on_error` | 721 | public | None | Log and display the failure |
| `clear_conversation` | 733 | public | None | Reset the multi-turn history |
| `load_history_item` | 739 | public | None | Restore a saved Q&A into the conversation view |
| `load_llm_settings` | 773 | public | None | Read LLM provider/model/params from config |
| `update_llm_models` | 806 | public | None | Repopulate the model combo for the provider |
| `on_model_changed` | 819 | public | None | Show/hide model-specific parameter controls |
| `save_dialog_settings` | 834 | public | None | Persist dialog-specific choices (provider, model, temperature, …) |
| `restore_dialog_settings` | 854 | public | None | Restore those choices |
| `save_settings` | 886 | public | None | Save window geometry |
| `restore_settings` | 890 | public | None | Restore window geometry |
| `reject` | 896 | override | None | Save settings before closing |
| `showEvent` | 902 | override | None | Update Discord presence on show |
| `closeEvent` | 910 | override | None | Stop the worker, save settings, clean up |

---

### Prompt Question Dialog (legacy)

**Path**: `gui/prompt_question_dialog_old.py` - 1080 lines
**Purpose**: Superseded single-turn version of the Ask-About-Prompt dialog, kept for reference. **Not imported anywhere** — `gui/main_window.py:80` imports `PromptQuestionDialog` from `gui/prompt_question_dialog.py` instead. Differences from the current version: one question/answer round trip (no `conversation_history`), no `OperationGuardMixin`, hand-rolled JSON history/session files instead of `DialogHistoryWidget` persistence, and a `QuestionWorker` without a `stop()` method.
**Language**: Python

#### QuestionWorker (line 22)

Signals: `finished(str)`, `error(str)`, `progress(str)`, `log_message(str, str)`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 29 | constructor | None | Capture prompt, question, provider/model/key, temperature, reasoning effort, verbosity |
| `run` | 42 | public | None | Call the LLM (LiteLLM first, native SDK fallback), log request/response, emit the answer |

#### PromptQuestionDialog (line 522)

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 525 | constructor | None | Load last session and question history, restore geometry, build UI |
| `init_ui` | 546 | public | None | Build the prompt view, predefined-question combo, question box, answer view, and status console in a splitter |
| `setup_shortcuts` | 721 | public | None | Bind Ctrl+Enter and Escape |
| `load_llm_settings` | 731 | public | None | Read LLM provider/model/params from config |
| `update_llm_models` | 755 | public | None | Repopulate the model combo for the provider |
| `on_model_changed` | 770 | public | None | Show/hide GPT-5-specific parameters |
| `on_predefined_selected` | 779 | public | None | Copy a predefined question into the question box |
| `ask_question` | 784 | public | None | Resolve the API key and run `QuestionWorker` on a `QThread` |
| `on_answer_received` | 882 | public | None | Render the answer and save it to history |
| `on_error` | 896 | public | None | Log and display the failure |
| `on_log_message` | 903 | public | None | Route worker logs to the status console |
| `cleanup_thread` | 907 | public | None | Quit and dispose of the worker thread |
| `save_last_session` | 916 | public | None | Persist the last question/answer pair |
| `load_last_session` | 944 | public | dict | Read the persisted session |
| `restore_last_session` | 958 | public | None | Repopulate the dialog from the saved session |
| `save_to_history` | 1008 | public | None | Append a question/answer (or error) to the JSON history |
| `load_history` | 1034 | public | list | Read the question/answer history file |
| `save_settings` | 1048 | public | None | Save window geometry and splitter state |
| `restore_settings` | 1056 | public | None | Restore window geometry and splitter state |
| `reject` | 1062 | override | None | Save settings before closing |
| `closeEvent` | 1068 | override | None | Clean up the thread and save settings |

---

### Enhanced Prompt Dialog

**Path**: `gui/enhanced_prompt_dialog.py` - 867 lines
**Purpose**: "Enhance Prompt with AI" — sends the current prompt to an LLM for rewriting at a chosen `EnhancementLevel` (from `core.prompt_enhancer`), optionally with a style preset and tuned for the target image provider. Shows original vs. enhanced side by side, keeps a history tab, and emits the accepted result. Opened from `gui/main_window.py:4871`.
**Language**: Python

`QDialog, OperationGuardMixin` with `block_all_input=True`; status console from
`gui/llm_utils.DialogStatusConsole`, history from
`gui/history_widget.DialogHistoryWidget`, settings under
`QSettings("ImageAI", "EnhancedPromptDialog")`.

#### EnhanceWorker (line 24)

Signals: `finished(str)`, `error(str)`, `progress(str)`,
`log_message(str, str)`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 31 | constructor | None | Capture prompt, LLM provider/model/key, `EnhancementLevel`, style preset, target image provider, temperature, max tokens, reasoning effort, verbosity |
| `stop` | 50 | public | None | Set the cooperative stop flag |
| `run` | 54 | public | None | Build the enhancement request, call the LLM, log request/response, emit the enhanced prompt |

#### EnhancedPromptDialog (line 170)

Signal: `promptEnhanced(str)`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| `__init__` | 175 | constructor | None | Store the current prompt, restore geometry, build UI, init the input-blocking guard |
| `init_ui` | 200 | public | None | Build the Enhance/History tabs, original + enhanced panes, level and style controls, LLM controls, and status console in a splitter |
| `setup_shortcuts` | 428 | public | None | Bind Ctrl+Enter (enhance) and Escape |
| `load_llm_settings` | 438 | public | None | Read LLM provider/model/params from config |
| `update_llm_models` | 471 | public | None | Repopulate the model combo for the provider |
| `on_model_changed` | 485 | public | None | Show/hide GPT-5-specific parameters |
| `enhance_prompt` | 496 | public | None | Resolve the API key and run `EnhanceWorker` on a `QThread` (guarded against re-entry) |
| `on_enhancement_finished` | 634 | public | None | Display the enhanced prompt, enable Accept, save to history |
| `on_enhancement_error` | 663 | public | None | Log and display the failure |
| `on_log_message` | 673 | public | None | Route worker logs to the status console |
| `cleanup_thread` | 677 | public | None | Quit and dispose of the worker thread |
| `accept_selection` | 686 | public | None | Emit `promptEnhanced` with the accepted text and close |
| `load_history_item` | 708 | public | None | Restore an earlier enhancement on double-click |
| `reject` | 745 | override | None | Save settings before closing |
| `save_settings` | 751 | public | None | Save window geometry and splitter state |
| `restore_settings` | 759 | public | None | Restore window geometry |
| `save_dialog_settings` | 765 | public | None | Persist application-wide dialog choices (level, style, LLM params) |
| `restore_dialog_settings` | 786 | public | None | Restore those choices |
| `showEvent` | 826 | override | None | Update Discord presence on show |
| `closeEvent` | 834 | override | None | Stop the worker, save settings, clean up |

---

## GUI — Reference Images, Midjourney & Batch

This group covers the reference-image / file-attachment pipeline (feeding images and documents to vision LLMs and to Imagen-style multi-reference generation), the Midjourney command builder and embedded web view, conversational image refinement, async batch submission, the social-size picker, and the Real-ESRGAN installer dialogs.

---

### ReferenceImageDialog
**Path**: `gui/reference_image_dialog.py` - 1186 lines
**Purpose**: LLM-vision dialog that analyzes attached files (images, text/code, PDFs) and turns them into a reference description usable as a prompt. Includes provider-specific image downscaling for Anthropic limits and a background analysis worker.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| ANTHROPIC_MAX_PIXELS | 37 | constant | Max total pixels (1,150,000) accepted by Anthropic vision |
| ANTHROPIC_MAX_DIMENSION | 38 | constant | Max single dimension (1568 px) before downscale |
| ANTHROPIC_JPEG_QUALITY | 39 | constant | JPEG quality (85) used when re-encoding oversized images |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| resize_image_for_anthropic | 42 | public | tuple[bytes, str] | No | Downscale/recompress raw image bytes to fit Anthropic pixel and dimension caps; returns bytes + MIME type |
| get_image_mime_type | 116 | public | str | No | Detect an image file's MIME type (`image/png`, `image/jpeg`, …) |

#### Class: ImageAnalysisWorker (line 151) — `QObject` (moveToThread pattern)
QThread worker that runs the multi-file LLM analysis off the GUI thread.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| finished | 153 | str | Emitted with the generated description text |
| error | 154 | str | Emitted on analysis failure |
| progress | 155 | str | Progress/status text for the dialog console |
| log_message | 156 | str, str | Message + level mirrored into the status console |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 158 | constructor | None | No | Store attachments, provider/model, key, prompt, sampling params, auth mode |
| stop | 177 | public | None | No | Request cooperative cancellation of the worker |
| _analyze_with_google_gemini | 181 | private | str | No | Native Google Gemini vision path (API key or gcloud auth) |
| run | 298 | public | None | No | Thread body: dispatch to the right provider, emit progress/finished/error |
| retry_callback | 456 | nested | None | No | Retry progress callback defined inside `run` |

#### Class: ReferenceImageDialog (line 501)
Dialog for attaching files, running LLM analysis, and returning a description to the caller.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| descriptionGenerated | 504 | str | Emitted on accept with the generated reference description |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 506 | constructor | None | No | Build state from config; optional initial `image_path` |
| init_ui | 536 | public | None | No | Compose attachment widget, provider/model selectors, prompt box, history, status console |
| setup_shortcuts | 720 | public | None | No | Keyboard shortcuts (Ctrl+Enter analyze, Escape close) |
| on_attachments_changed | 730 | public | None | No | React to attachment add/remove (enable/disable analyze) |
| load_llm_settings | 739 | public | None | No | Populate providers/models and sampling params from config |
| update_llm_models | 784 | public | None | No | Refresh the model list for the selected provider |
| on_model_changed | 802 | public | None | No | Apply per-model capability tweaks (temperature/effort/verbosity) |
| analyze_files | 824 | public | None | No | Start `ImageAnalysisWorker`; guarded by `@guard_operation('File Analysis')` |
| cleanup_thread | 942 | public | None | No | Drop worker/thread references once fully stopped |
| on_analysis_complete | 947 | public | None | No | Show the description and add it to history |
| on_analysis_error | 960 | public | None | No | Report a failed analysis to console + user |
| accept | 972 | public | None | No | Emit `descriptionGenerated` and persist settings |
| reject | 1000 | public | None | No | Save settings before cancelling |
| save_settings | 1006 | public | None | No | Persist geometry and splitter state |
| restore_settings | 1014 | public | None | No | Restore geometry |
| save_dialog_settings | 1020 | public | None | No | Persist provider/model/prompt and dialog-specific choices |
| restore_dialog_settings | 1046 | public | None | No | Restore provider/model/prompt selections |
| load_history_item | 1095 | public | None | No | Repopulate the dialog from a double-clicked history entry |
| showEvent | 1157 | public | None | No | Update Discord Rich Presence on show |
| closeEvent | 1165 | public | None | No | Stop worker threads and save state on close |

---

### FileAttachmentWidget
**Path**: `gui/file_attachment_widget.py` - 646 lines
**Purpose**: Reusable multi-file attachment control for LLM dialogs — drag-and-drop file list, category/extension detection, content loading (images, text/code, PDF text extraction) and conversion into OpenAI-style or Gemini-style content parts.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| FILE_CATEGORIES | 30 | constant | Category → extensions/icon map (image, text, code, document) |
| EXTENSION_TO_CATEGORY | 62 | constant | Reverse lookup built from `FILE_CATEGORIES` |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_file_category | 68 | public | str | No | Category name for a path's extension |
| get_file_icon | 74 | public | str | No | Emoji icon for a file type |
| get_supported_extensions | 82 | public | List[str] | No | All extensions the widget accepts |
| get_file_filter_string | 90 | public | str | No | QFileDialog filter string across categories |
| read_file_content | 112 | public | Tuple[Optional[bytes], Optional[str], str] | No | Read a file as (raw_bytes, text, mime) — bytes for images, text for code, both for PDFs |

#### Class: AttachmentItem (line 202)
Value object for one attached file, lazily loading content into memory.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 205 | constructor | None | No | Capture path, name, size, category |
| load_content | 219 | public | bool | No | Read the file via `read_file_content`; False on failure |
| @property raw_bytes | 232 | property | Optional[bytes] | No | Binary content (images/PDFs) |
| @property text_content | 238 | property | Optional[str] | No | Decoded text content |
| @property mime_type | 244 | property | str | No | Detected MIME type |
| @property base64_data | 250 | property | Optional[str] | No | Base64 payload for image/PDF API parts |
| get_size_str | 256 | public | str | No | Human-readable size string |
| __repr__ | 265 | magic | str | No | Debug representation |

#### Class: FileAttachmentWidget (line 269)
List-based attachment manager with add/remove, drag-drop and LLM payload builders.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| attachmentsChanged | 273 | — | Emitted whenever the attachment set changes |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 275 | constructor | None | No | Configure `max_files` and `allowed_categories` |
| init_ui | 292 | public | None | No | Build list view, buttons, info label; enable drops |
| update_info_label | 351 | public | None | No | Refresh count/size summary |
| add_files_dialog | 362 | public | None | No | Open QFileDialog with the generated filter |
| add_files | 374 | public | None | No | Add many paths, respecting limits |
| add_file | 392 | public | bool | No | Validate, load and append one file (`silent` suppresses error dialogs) |
| remove_selected | 472 | public | None | No | Remove the selected rows |
| clear_attachments | 488 | public | None | No | Drop all attachments |
| show_context_menu | 506 | public | None | No | Right-click menu (remove/clear) |
| dragEnterEvent | 522 | public | None | No | Accept URL drags |
| dropEvent | 529 | public | None | No | Add dropped files |
| get_attachments | 542 | public | List[AttachmentItem] | No | All items |
| get_image_attachments | 546 | public | List[AttachmentItem] | No | Image-category items only |
| get_text_attachments | 550 | public | List[AttachmentItem] | No | Text + code items |
| get_document_attachments | 554 | public | List[AttachmentItem] | No | PDF/document items |
| has_attachments | 558 | public | bool | No | Non-empty check |
| get_attachment_count | 562 | public | int | No | Item count |
| prepare_for_llm | 566 | public | List[Dict] | No | Build OpenAI-style content parts (image_url + text) |
| prepare_for_gemini | 614 | public | List | No | Build Google Gemini `generate_content` parts |

---

### ImagenReferenceWidget
**Path**: `gui/imagen_reference_widget.py` - 1071 lines
**Purpose**: Multi-reference-image panel for Imagen/Gemini image models — per-slot thumbnails with reference/subject/control types, flexible vs strict modes, edit and composite modes, and per-model reference limits.
**Language**: Python

#### Class: FlowLayout (line 28)
Custom `QLayout` that flows child widgets left-to-right and wraps to new rows.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 34 | constructor | None | No | Set margins/spacing and item list |
| __del__ | 41 | magic | None | No | Delete remaining layout items |
| addItem | 46 | public | None | No | Append a layout item |
| count | 49 | public | int | No | Item count |
| itemAt | 52 | public | QLayoutItem | No | Item lookup by index |
| takeAt | 57 | public | QLayoutItem | No | Remove and return an item |
| expandingDirections | 62 | public | Qt.Orientations | No | No expansion (returns empty) |
| hasHeightForWidth | 65 | public | bool | No | Height-for-width supported |
| heightForWidth | 68 | public | int | No | Compute wrapped height for a width |
| setGeometry | 72 | public | None | No | Apply the real layout pass |
| sizeHint | 76 | public | QSize | No | Preferred size |
| minimumSize | 79 | public | QSize | No | Minimum enclosing size |
| _do_layout | 87 | private | int | No | Core wrap algorithm (test-only mode for measuring) |

#### Class: ImagenReferenceItemWidget (line 113)
One reference slot: thumbnail, reference ID, type/subject/control selectors and description.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| reference_changed | 121 | — | Slot contents or type changed |
| remove_requested | 122 | — | User asked to remove this slot |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 124 | constructor | None | No | Bind reference ID (1-N) and parent |
| _init_ui | 139 | private | None | No | Build thumbnail, combos, description field, remove button |
| _on_control_type_changed | 303 | private | None | No | Handle control-type combo change |
| set_reference_image | 307 | public | None | No | Load a path, generate the thumbnail preview |
| get_reference | 337 | public | Optional[ImagenReference] | No | Build the core `ImagenReference` model, or None if empty |
| clear | 376 | public | None | No | Reset the slot to empty |
| _on_type_changed | 385 | private | None | No | Switch visible sub-controls for SUBJECT/STYLE/CONTROL |
| _on_subject_type_changed | 409 | private | None | No | Handle subject-type combo change |
| set_combos_visible | 413 | public | None | No | Hide type combos in flexible (style-transfer) mode |

#### Class: ImagenReferenceWidget (line 436)
Container managing all reference slots, mode switching and serialization.

##### Properties / Signals
| Name | Line | Type | Access | Description |
|------|------|------|--------|-------------|
| MODEL_REF_LIMITS | 450 | dict | class | Per-model max reference count (flash 5, 3.1-flash 8, 3-pro 14, default 3) |
| references_changed | 458 | Signal() | class | Any slot changed |
| mode_changed | 459 | Signal(str) | class | Flexible/strict mode switch |
| use_current_image_requested | 460 | Signal(bool) | class | Request the current generated image as a reference |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 462 | constructor | None | No | Initialize slot list and default mode |
| _init_ui | 478 | private | None | No | Build mode selector, flow layout of slots, edit/composite checkboxes |
| _on_mode_changed | 607 | private | None | No | Apply flexible vs strict UI rules and emit `mode_changed` |
| _add_reference | 656 | private | None | No | File-dialog add of one or more reference images |
| _remove_reference | 707 | private | None | No | Remove a slot widget and renumber |
| _on_reference_changed | 729 | private | None | No | Re-emit `references_changed` and refresh UI |
| _on_edit_mode_changed | 734 | private | None | No | Handle edit-mode checkbox toggle |
| _on_use_current_clicked | 739 | private | None | No | Emit `use_current_image_requested` |
| set_use_current_enabled | 745 | public | None | No | Enable/disable "Use Current Image" (called by MainWindow) |
| add_reference_from_path | 756 | public | None | No | Programmatically add a reference, optionally clearing existing |
| _update_ui | 793 | private | None | No | Sync labels, counts and enabled state |
| update_model | 837 | public | None | No | Re-apply the reference limit for the selected model |
| get_references | 870 | public | List[ImagenReference] | No | All valid references |
| has_references | 884 | public | bool | No | At least one reference set |
| get_mode | 893 | public | str | No | `"flexible"` or `"strict"` |
| is_flexible_mode | 902 | public | bool | No | Style-transfer mode check |
| is_strict_mode | 911 | public | bool | No | Subject-preservation mode check |
| needs_compositing | 920 | public | bool | No | True when flexible mode has multiple images |
| is_edit_mode_active | 929 | public | bool | No | Edit mode on and exactly one reference |
| is_composite_mode | 944 | public | bool | No | Combine multiple references into a grid |
| get_edit_mode_prefix | 957 | public | str | No | Prompt prefix injected in edit mode |
| validate_references | 966 | public | tuple[bool, list[str]] | No | Validate all slots, returning error messages |
| clear_all | 980 | public | None | No | Clear every slot |
| to_dict | 985 | public | dict | No | Serialize mode + references (project save) |
| from_dict | 998 | public | None | No | Restore from dict or legacy list form |

---

### RefineImageDialog
**Path**: `gui/refine_image_dialog.py` - 549 lines
**Purpose**: Multi-turn conversational image editing against a Gemini image chat session (Nano Banana Pro), preserving thought signatures across turns; shows the running image, chat history, and a save action.
**Language**: Python

#### Class: RefineWorker (line 31)
QThread worker that issues one refinement turn on the existing chat session.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| finished | 35 | bytes, str | New image bytes + model response text |
| error | 36 | str | Failure message |
| progress | 37 | str | Progress updates for the status console |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 39 | constructor | None | No | Bind chat session, refinement prompt, aspect ratio, image size |
| run | 56 | public | None | No | Send the turn, decode the returned image, emit results |

#### Class: RefineImageDialog (line 108)
Dialog wrapping the refinement loop and conversation history.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| image_refined | 116 | bytes, str, str | Refined image bytes plus prompt/response metadata |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 118 | constructor | None | No | Take an `ImageConversation`, current image bytes and aspect ratio |
| _init_ui | 149 | private | None | No | Build image pane, chat history, prompt input, status console |
| _restore_settings | 300 | private | None | No | Restore geometry and splitter proportions |
| on_dialog_close | 313 | public | None | No | Shared cleanup for Close/Escape/title-bar X |
| _display_image | 333 | private | None | No | Load bytes into the preview pixmap |
| _rescale_image | 349 | private | None | No | Rescale preview proportionally (scaled, never cropped) |
| resizeEvent | 360 | public | None | No | Re-scale the preview on resize |
| _load_history | 364 | private | None | No | Replay stored conversation turns into the chat view |
| _add_history_message | 376 | private | None | No | Append one role-tagged message (optionally with image) |
| _on_refine_clicked | 428 | private | None | No | Start a refinement, or act as Stop while one is running |
| _cancel_refine | 476 | private | None | No | Stop an in-flight refinement |
| _reset_refine_ui | 482 | private | None | No | Restore input/button state after run or stop |
| _on_progress | 490 | private | None | No | Surface worker progress in the console |
| _on_refine_finished | 495 | private | None | No | Update image + history, emit `image_refined` |
| _on_refine_error | 520 | private | None | No | Log and display refinement errors |
| _on_save_clicked | 530 | private | None | No | Save the refined image via QFileDialog |

---

### MidjourneyTab
**Path**: `gui/midjourney_tab.py` - 687 lines
**Purpose**: ToS-compliant Midjourney command builder — assembles `/imagine` slash commands from prompt, model, aspect, stylize/chaos/weird sliders and templates; copies to clipboard and keeps a command history. Generates commands only, never calls Midjourney.
**Language**: Python

#### Class: MidjourneyTab (line 17)

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| commandGenerated | 21 | str | Emitted with the assembled slash command |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 23 | constructor | None | No | Store config and build the tab |
| init_ui | 31 | public | None | No | Build prompt fields, parameter controls, templates, history and preview |
| _on_aspect_changed | 347 | private | None | No | Apply the selected aspect-ratio preset |
| _toggle_negative | 352 | private | None | No | Show/hide the negative (`--no`) prompt field |
| _update_stylize_label | 357 | private | None | No | Live label for the stylize slider |
| _update_chaos_label | 362 | private | None | No | Live label for the chaos slider |
| _update_weird_label | 367 | private | None | No | Live label for the weird slider |
| update_command | 372 | public | None | No | Rebuild the full slash command from current UI state |
| copy_command | 459 | public | None | No | Copy the command to the clipboard and add it to history |
| add_to_history | 476 | public | None | No | Append a command to the history list |
| restore_from_history | 490 | public | None | No | Repopulate all controls from a history entry |
| _parse_parameters | 514 | private | dict | No | Parse `--param value` flags back out of a command string |
| clear_history | 568 | public | None | No | Empty the history list |
| apply_template | 579 | public | None | No | Apply a named preset (Photorealistic, Cinematic, Artistic, …) |
| load_settings | 660 | public | None | No | Restore saved tab settings |
| save_settings | 676 | public | None | No | Persist current tab settings |

---

### MidjourneyWebDialog
**Path**: `gui/midjourney_dialog.py` - 1129 lines
**Purpose**: Embedded QtWebEngine view of the Midjourney web interface with a shared persistent profile (cookies/login), Discord auth popups, download interception, and import of downloaded images back into ImageAI.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| WEBENGINE_CORE | 23 | constant | True when `PySide6.QtWebEngineCore` imported successfully |
| WEBENGINE_CORE | 25 | constant | False fallback assignment when the import fails |
| WEBENGINE_ENHANCED | 30 | constant | True when the enhanced WebEngine widgets are available |
| WEBENGINE_ENHANCED | 32 | constant | False fallback assignment when the import fails |
| _SHARED_MIDJOURNEY_PROFILE | 39 | constant | Module-global cached `QWebEngineProfile` (initially None) |
| _ACTIVE_STATUS_CONSOLE | 44 | constant | Status console of the most recently opened dialog, for download feedback |
| _SHARED_MIDJOURNEY_PROFILE | 160 | constant | Re-assignment inside `get_shared_midjourney_profile` caching the created profile |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| _console_status | 47 | private | None | No | Log to the console logger and mirror into the active dialog console |
| _handle_download | 60 | private | None | No | Accept and track Midjourney file downloads |
| on_state_change | 86 | nested | None | No | Download state callback defined inside `_handle_download` |
| get_shared_midjourney_profile | 112 | public | QWebEngineProfile | No | Create/return the persistent profile (modern UA, on-disk cookies & cache) |

#### Class: MidjourneyWebDialog (line 168)

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| imageGenerated | 171 | str | Path of an imported Midjourney image |
| sessionStarted | 172 | str, str | Session start (prompt, command) |
| sessionEnded | 173 | — | Session finished/dialog closed |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 175 | constructor | None | No | Take web URL, slash command, prompt and parent |
| _suppress_qt_warnings | 205 | private | None | No | Install a log filter for noisy Qt WebEngine warnings |
| _extract_prompt_from_command | 249 | private | str | No | Strip flags to recover the prompt text from a slash command |
| setup_ui | 259 | public | None | No | Build instructions pane, toolbar, web view and status console |
| _configure_web_view | 445 | private | None | No | Attach the shared profile, request/cookie logging, custom page and permissions |
| load_url | 669 | public | None | No | Navigate to the Midjourney web interface |
| copy_command | 680 | public | None | No | Copy the slash command to the clipboard |
| open_in_browser | 695 | public | None | No | Open Midjourney in the system browser |
| _open_discord_login_popup | 703 | private | None | No | Host Discord login in an embedded popup sharing the profile |
| _import_downloaded_images | 741 | private | None | No | Scan Downloads for matching images and import them (auto or prompted) |
| _post_load_check | 895 | private | None | No | Detect blank/404 pages after load and soft-reload |
| _inspect | 916 | nested | None | No | JS result callback inside `_post_load_check` |
| _reset_session | 942 | private | None | No | Clear cookies/cache for the profile and reload (Cloudflare/login recovery) |
| _handle_popup_url | 964 | private | None | No | Route a popup URL to embedded or external handling |
| _open_external_auth | 973 | private | None | No | Send an auth URL to the system browser |
| _register_popup | 983 | private | None | No | Track an open `_AuthPopupDialog` |
| on_image_ready | 991 | public | None | No | Handle the user signalling that an image is ready |
| on_dialog_close | 1006 | public | None | No | Cleanup for every exit path (accept, Escape, title-bar X) |

##### Nested Classes
| Class | Line | Parent | Description |
|-------|------|--------|-------------|
| QtWarningFilter | 222 | MidjourneyWebDialog._suppress_qt_warnings | Logging filter; `filter` at line 223 drops known-noisy WebEngine records |
| _RequestLogger | 481 | MidjourneyWebDialog._configure_web_view | `QWebEngineUrlRequestInterceptor`; `interceptRequest` at line 482 debug-logs method + URL |
| _LoggingWebPage | 509 | MidjourneyWebDialog._configure_web_view | `QWebEnginePage` subclass with JS-console logging and popup/auth support |

##### _LoggingWebPage Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 510 | constructor | None | No | Bind profile, parent and owning dialog |
| javaScriptConsoleMessage | 514 | public | None | No | Forward page JS console output to the logger |
| acceptNavigationRequest | 522 | public | bool | No | Intercept auth/external navigations |
| createWindow | 548 | public | QWebEnginePage | No | Create an embedded popup page for `window.open` |

##### Other Nested Helpers
| Helper | Line | Enclosing Method | Description |
|--------|------|------------------|-------------|
| _cookie_name | 498 | _configure_web_view | Safely decode a cookie name for debug logging |
| _on_feature | 575 | _configure_web_view | Grant/deny WebEngine feature permission requests |

#### Class: _AuthPopupDialog (line 1043)
Small dialog hosting popup auth windows in-app, sharing the same `QWebEngineProfile` so cookies propagate back to the main view.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 1050 | constructor | None | No | Wrap the supplied page in a web view sized for auth |
| _on_url | 1090 | private | None | No | Watch URL changes and close once auth completes |
| page | 1128 | public | QWebEnginePage | No | Accessor for the hosted page |

---

### BatchModeWidget
**Path**: `gui/batch_mode_widget.py` - 552 lines
**Purpose**: Queue prompts and submit them as an async Google Gemini batch job (50% discount), then poll job state and download results. Wraps `core.batch_manager` (`BatchRequest` / `BatchJob` / `get_batch_manager`).
**Language**: Python

#### Class: BatchModeWidget (line 32)

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| batch_started | 41 | str | Job ID of a newly submitted batch |
| batch_completed | 42 | str, list | Job ID + downloaded result paths |
| batch_failed | 43 | str, str | Job ID + failure message |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 45 | constructor | None | No | Init queue, jobs list, poll timer and current model/aspect/quality |
| _init_ui | 63 | private | None | No | Build prompt queue, job list, cost estimate and status console |
| add_prompt | 247 | public | None | No | Append a prompt to the queue |
| set_model | 260 | public | None | No | Set the model used for submissions |
| set_aspect_ratio | 265 | public | None | No | Set the batch aspect ratio |
| set_quality | 269 | public | None | No | Set the NBP quality tier |
| _update_ui | 274 | private | None | No | Sync button/label state to queue and job contents |
| _estimate_cost | 286 | private | float | No | Estimate job cost with the 50% batch discount |
| _remove_selected | 305 | private | None | No | Remove selected prompts from the queue |
| _clear_queue | 317 | private | None | No | Empty the prompt queue |
| _import_prompts | 330 | private | None | No | Load prompts from a text file |
| _export_prompts | 347 | private | None | No | Save the queue to a text file |
| _submit_batch | 365 | private | None | No | Build `BatchRequest`s, submit via the batch manager, log full details |
| _add_job_to_list | 438 | private | None | No | Add a submitted job row |
| _update_job_item | 445 | private | None | No | Refresh a job row's state/progress text |
| _poll_job_status | 460 | private | None | No | Timer callback polling active jobs for state changes |
| _refresh_all_jobs | 505 | private | None | No | Manual refresh of every job's status |
| _download_results | 511 | private | None | No | Download images from the selected completed job |

---

### SocialSizesTreeDialog
**Path**: `gui/social_sizes_tree_dialog.py` - 548 lines
**Purpose**: Three-level tree browser (Category → Platform → Size) for social-media, favicon and common image presets loaded from repo markdown tables; supports filtering, platform icons, double-click select and persistent expansion state.
**Language**: Python

#### Class: SocialSizesTreeDialog (line 29)

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 32 | constructor | None | No | Init settings, icon cache and selection state |
| _load_icons | 50 | private | None | No | Load platform icons from the assets directory |
| _init_ui | 94 | private | None | No | Build the tree, search box, info panel and buttons |
| _load_data | 174 | private | None | No | Parse `social-media-image-sizes-2025.md`, `favicon-sizes.md`, `common-sizes.md` into categories |
| norm | 219 | nested | str | No | String normalizer used while matching platform names in `_load_data` |
| _apply_filter | 301 | private | None | No | Word-match filter across size columns, platform and category; expands matches |
| _show_help_text | 353 | private | None | No | Show default help in the info panel when nothing is selected |
| _on_selection_changed | 361 | private | None | No | Update the info panel and highlight for the selected size |
| _clear_all_highlights | 402 | private | None | No | Clear the previously highlighted level-3 item |
| _on_double_click | 410 | private | None | No | Accept the dialog on double-clicking a size |
| _use_selected | 416 | private | None | No | Confirm the current selection and close |
| _save_expansion_state | 431 | private | None | No | Persist expanded categories/platforms and the selected item |
| _restore_expansion_state | 468 | private | None | No | Restore expansion and selection from settings |
| on_dialog_close | 542 | public | None | No | Save state on every exit path (OK, Close, Escape, X) |
| selected_resolution | 547 | public | Optional[str] | No | Chosen resolution string, or None |

---

### Install Dialogs (Real-ESRGAN)
**Path**: `gui/install_dialog.py` - 529 lines
**Purpose**: Three-stage installer UX for Real-ESRGAN AI upscaling — confirm, run `core.package_installer.PackageInstaller` / `ModelDownloader` with live progress, then offer restart. Detects NVIDIA GPUs to choose CUDA vs CPU packages.
**Language**: Python

#### Class: InstallConfirmDialog (line 31)
Pre-install confirmation showing package list, disk-space and GPU status.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 34 | constructor | None | No | Build the confirmation dialog |
| init_ui | 41 | public | None | No | Compose explanation text, requirements and Install/Cancel buttons |

#### Class: InstallProgressDialog (line 133)
Runs the install, streams progress, then downloads the default model.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| installation_complete | 136 | bool, str | Success flag + summary message |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 138 | constructor | None | No | Init timers, installer/downloader handles and state |
| init_ui | 158 | public | None | No | Build progress bar, elapsed-time label and status console |
| start_installation | 245 | public | None | No | Detect GPU, pick packages/index URL, start `PackageInstaller` thread |
| update_elapsed_time | 271 | public | None | No | Tick the elapsed-time readout |
| on_progress | 279 | public | None | No | Append a timestamped progress line |
| on_percentage | 284 | public | None | No | Update the progress bar value |
| on_installation_finished | 288 | public | None | No | Handle install success/failure and chain to model download |
| download_model | 314 | public | None | No | Start `ModelDownloader` for the default Real-ESRGAN weights |
| on_download_finished | 338 | public | None | No | Finish up, emit `installation_complete`, notify the user |
| show_notification | 376 | public | None | No | Show a system-tray notification when available |
| restart_application | 406 | public | None | No | Relaunch ImageAI via `QProcess` |
| reject | 421 | public | None | No | Block closing while installing or downloading |
| on_dialog_close | 443 | public | None | No | Persist splitter proportions on every exit path |

#### Class: InstallCompleteDialog (line 448)
Post-install summary with a restart action.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 451 | constructor | None | No | Take success flag and message |
| init_ui | 460 | public | None | No | Show outcome text and Restart/Close buttons |
| restart_application | 520 | public | None | No | Relaunch the application |

---

## GUI — Supporting Dialogs & Widgets

Reusable PySide6 dialogs, panels, model/view classes, worker threads, and layout
helpers that sit alongside the main window and tab widgets. Everything here is
importable in isolation and used from multiple tabs.

---

### theme

**Path**: `gui/theme.py` - 696 lines
**Purpose**: Single source of truth for the Maestro (ChameleonLabs) dark brand theme — named color constants, font families, the full Qt Style Sheet, and the one-call application helper.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| NAVY | 24 | constant | Main background (brand-navy) |
| NAVY_LIGHT | 25 | constant | Panels / cards |
| NAVY_DARK | 26 | constant | Deepest background layer |
| NAVY_INPUT | 27 | constant | Input-field background |
| CYAN | 32 | constant | Primary accent |
| CYAN_LIGHT | 33 | constant | Hover/active accent |
| CYAN_DARK | 34 | constant | Pressed/border accent |
| GREEN | 39 | constant | Success state |
| AMBER | 40 | constant | Warning state |
| RED | 41 | constant | Error state |
| MAGENTA | 42 | constant | Secondary highlight |
| PURPLE | 43 | constant | Secondary highlight |
| BLUE | 44 | constant | Secondary highlight |
| TEXT_PRIMARY | 49 | constant | Default foreground text |
| TEXT_SECONDARY | 50 | constant | De-emphasized text |
| TEXT_MUTED | 51 | constant | Hint / caption text |
| TEXT_DISABLED | 52 | constant | Disabled-control text |
| BORDER_SUBTLE | 57 | constant | Low-contrast separators |
| BORDER_CYAN | 58 | constant | Accented/focused borders |
| FONT_BODY | 63 | constant | Body font family (Roboto) |
| FONT_HEADING | 64 | constant | Heading font family (Limelight) |
| FONT_MONO | 65 | constant | Monospace font family |
| MAESTRO_QSS | 70 | constant | Full Qt Style Sheet covering all standard Qt widgets |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| apply_maestro_theme | 689 | public | None | No | Applies `MAESTRO_QSS` to a QApplication via `setStyleSheet()` |

---

### WikimediaSearchDialog

**Path**: `gui/wikimedia_search_dialog.py` - 502 lines
**Purpose**: Search Wikimedia Commons, preview results with thumbnails and license/attribution details, and download selected images (optionally adding them straight to the reference-image set).
**Language**: Python

#### Classes

**`NumericTableWidgetItem`** (line 18) — QTableWidgetItem subclass that sorts by an integer key rather than lexicographically.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 21 | constructor | None | No | Stores display text plus the numeric sort key |
| __lt__ | 25 | dunder | bool | No | Compares on the stored numeric value |

**`ImageDownloader`** (line 37) — QThread that downloads a batch of `WikimediaImage` results to a directory. Signals: `progress(int, int)`, `finished(list)`, `error(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 44 | constructor | None | No | Takes client, image list, and output directory |
| run | 51 | public | None | No | Downloads each image, emitting per-item progress |
| cancel | 78 | public | None | No | Sets the cancellation flag |

**`SearchWorker`** (line 83) — QThread wrapping the Wikimedia search API call. Signals: `finished(list)`, `error(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 89 | constructor | None | No | Takes client, query string, and result limit |
| run | 95 | public | None | No | Executes the search, emits results or error |

**`ThumbnailLoader`** (line 104) — QThread that fetches a single thumbnail URL. Signals: `finished(bytes)` (raw bytes, not QPixmap — cross-thread safe), `error(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 110 | constructor | None | No | Stores the thumbnail URL |
| run | 115 | public | None | No | Fetches the image bytes |
| cancel | 151 | public | None | No | Sets the cancellation flag |

**`WikimediaSearchDialog`** (line 156) — the dialog itself. Signal: `images_downloaded(list)`. Resolves its download directory from `ConfigManager.get_images_dir() / "wikimedia"`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 161 | constructor | None | No | Creates client, config, download dir; builds UI |
| _init_ui | 178 | private | None | No | Search bar, results table, splitter preview/details pane |
| _search | 274 | private | None | No | Kicks off a `SearchWorker` |
| _on_search_finished | 296 | private | None | No | Populates the results table |
| _on_search_error | 331 | private | None | No | Shows the search failure |
| _on_selection_changed | 337 | private | None | No | Loads details + thumbnail for the selected row |
| _show_image_details | 358 | private | None | No | Renders title, author, license, dimensions |
| _on_thumbnail_loaded | 387 | private | None | No | Builds a QPixmap from the loaded bytes |
| _on_thumbnail_error | 408 | private | None | No | Falls back when a thumbnail fails |
| _download_selected | 413 | private | None | No | Downloads checked images only |
| _download_and_add_references | 427 | private | None | No | Downloads and flags results for the reference set |
| _start_download | 441 | private | None | No | Spins up the `ImageDownloader` thread |
| _on_download_progress | 459 | private | None | No | Updates the progress bar |
| _on_download_finished | 464 | private | None | No | Emits `images_downloaded`, optionally as references |
| closeEvent | 486 | public | None | No | Cancels in-flight workers before closing |

---

### LocalSDWidget

**Path**: `gui/local_sd_widget.py` - 474 lines
**Purpose**: Settings-tab widget for managing local Stable Diffusion models — listing installed models, downloading new ones from Hugging Face, and managing the HF auth token.
**Language**: Python

#### Classes

**`ModelDownloadThread`** (line 20) — QThread that pulls a model into the HF cache. Signals: `progress(int)`, `status(str)`, `finished(bool)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 27 | constructor | None | No | Takes model id and cache directory |
| run | 32 | public | None | No | Performs the download, emitting status/progress |

**`LocalSDWidget`** (line 61) — the management widget. Signal: `models_changed()`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 66 | constructor | None | No | Resolves HF cache dir, checks auth, refreshes model list |
| _init_ui | 74 | private | None | No | Model combo, install list, download controls, token box |
| _populate_model_combo | 212 | private | None | No | Fills the combo from `providers.model_info` |
| _refresh_models | 232 | private | None | No | Rescans the cache for installed models |
| _download_selected | 260 | private | None | No | Downloads the model chosen in the combo |
| _download_custom | 280 | private | None | No | Downloads an arbitrary user-entered model id |
| _start_download | 296 | private | None | No | Launches `ModelDownloadThread` and wires signals |
| _on_download_status | 341 | private | None | No | Appends a status line |
| _on_download_finished | 345 | private | None | No | Refreshes the list and emits `models_changed` |
| get_installed_models | 359 | public | list | No | Returns the currently detected installed models |
| _check_hf_auth | 363 | private | None | No | Detects whether a Hugging Face token is present |
| _open_hf_token_page | 394 | private | None | No | Opens the HF token page in a browser |
| _logout_huggingface | 404 | private | None | No | Clears the stored HF credentials |
| _save_token | 428 | private | None | No | Persists a newly entered HF token |

---

### ModelBrowserDialog

**Path**: `gui/model_browser.py` - 447 lines
**Purpose**: Full-screen browser for Stable Diffusion models — popular-model catalog, installed models, and custom model-id entry, each with download progress.
**Language**: Python

#### Classes

**`ModelDownloader`** (line 25) — QThread for model downloads. Signals: `progress(int)`, `status(str)`, `finished(bool)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 32 | constructor | None | No | Takes model id and cache directory |
| run | 38 | public | None | No | Downloads the model with a progress callback |
| progress_callback | 53 | nested | None | No | Inner callback translating HF progress into `progress`/`status` |
| stop | 90 | public | None | No | Requests cancellation |

**`ModelBrowserDialog`** (line 95) — the tabbed browser dialog.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 98 | constructor | None | No | Resolves cache dir, builds UI, loads the model catalog |
| _init_ui | 110 | private | None | No | Tab widget, detail pane, progress bar, buttons |
| _create_popular_models_tab | 182 | private | QWidget | No | Curated model list with a filter box |
| _create_installed_models_tab | 232 | private | QWidget | No | Models already present in the cache |
| _create_custom_model_tab | 252 | private | QWidget | No | Free-form Hugging Face model-id entry |
| _load_models | 287 | private | None | No | Populates the popular-models list |
| _load_installed_models | 308 | private | None | No | Scans the cache directory |
| _filter_models | 322 | private | None | No | Live text filter over the popular list |
| _on_model_selected | 341 | private | None | No | Shows description/size/requirements for the selection |
| _download_selected | 369 | private | None | No | Downloads the highlighted catalog model |
| _download_custom | 379 | private | None | No | Downloads the custom-entered model id |
| _start_download | 393 | private | None | No | Starts `ModelDownloader` and wires progress |
| _cancel_download | 425 | private | None | No | Stops the running downloader |
| _on_download_finished | 431 | private | None | No | Refreshes lists and reports success/failure |

---

### FindDialog

**Path**: `gui/find_dialog.py` - 434 lines
**Purpose**: Reusable Find/Search tool window that works against either a `QTextEdit` (highlight-based) or a `QWebEngineView` (page-find based), with persisted geometry and search options.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| HAS_WEBENGINE | 14 | constant | True when `PySide6.QtWebEngine*` imported successfully |
| HAS_WEBENGINE | 16 | constant | False fallback set in the ImportError branch |

#### Classes

**`FindDialog`** (line 21) — tool-style always-on-top find window; auto-detects the target widget type in `__init__`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 24 | constructor | None | No | Detects webview vs text widget, restores geometry/options |
| init_ui | 45 | public | None | No | Search field, match counter, case/whole-word checkboxes, nav buttons |
| on_search_text_changed | 120 | public | None | No | Re-runs the search as the user types |
| find_all_matches | 133 | public | None | No | Collects every match position in a QTextEdit |
| _find_in_webview | 199 | private | None | No | Delegates to `QWebEnginePage.findText` |
| on_find_result | 213 | nested | None | No | Async callback receiving the webview find result |
| highlight_current_match | 240 | public | None | No | Applies the "current match" highlight format |
| find_next | 271 | public | None | No | Advances to the next match (wraps) |
| find_previous | 294 | public | None | No | Steps back to the previous match (wraps) |
| restore_match_highlight | 316 | public | None | No | Restores the normal highlight on a previously current match |
| clear_search | 331 | public | None | No | Empties the field and resets match state |
| clear_highlights | 342 | public | None | No | Removes all applied highlight formats |
| showEvent | 372 | public | None | No | Focuses/selects the search field on show |
| keyPressEvent | 395 | public | None | No | Enter = next, Shift+Enter = previous, Esc = close |
| save_settings | 407 | public | None | No | Persists geometry to QSettings |
| restore_settings | 414 | public | None | No | Restores geometry from QSettings |
| restore_search_settings | 420 | public | None | No | Restores case/whole-word checkbox state |
| closeEvent | 428 | public | None | No | Clears highlights and saves settings |

---

### ImageCropDialog

**Path**: `gui/image_crop_dialog.py` - 421 lines
**Purpose**: Interactive crop dialog with an animated "marching ants" selection rectangle, keyboard nudging, and a scale-vs-crop choice for fitting an image to a target resolution.
**Language**: Python

#### Classes

**`MarchingAntsRect`** (line 17) — QGraphicsRectItem whose dashed pen offset animates on a 50 ms QTimer.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 20 | constructor | None | No | Creates the rect and starts the animation timer |
| create_pen | 31 | public | QPen | No | Builds the dashed pen at the current offset |
| update_offset | 37 | public | None | No | Advances the dash offset and repaints |
| stop_animation | 42 | public | None | No | Stops the timer |

**`ImageCropView`** (line 46) — QGraphicsView hosting the image and selection rect. Signal: `selection_moved()`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 51 | constructor | None | No | Initializes move-step sizes and item refs |
| set_selection_rect | 58 | public | None | No | Binds the selection rect item to the view |
| keyPressEvent | 63 | public | None | No | Arrow keys nudge the selection (Shift = fast step) |
| mousePressEvent | 102 | public | None | No | Begins a drag of the selection rectangle |
| mouseMoveEvent | 125 | public | None | No | Moves the selection, clamped to image bounds |
| mouseReleaseEvent | 145 | public | None | No | Ends the drag and emits `selection_moved` |

**`ImageCropDialog`** (line 151) — the crop dialog proper.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 154 | constructor | None | No | Stores source image + target size, builds and positions the scene |
| setup_ui | 166 | public | None | No | Graphics view, info labels, restore/scale/crop buttons |
| scale_and_position_image | 254 | public | None | No | Scales the source proportionally and centers the selection |
| update_info | 303 | public | None | No | Refreshes source/target/output dimension labels |
| update_position_info | 324 | public | None | No | Refreshes the live crop-offset readout |
| restore_size | 330 | public | None | No | Switches to full-size (1:1) restore mode |
| show_scaled | 377 | public | None | No | Returns to the scaled-to-fit view |
| accept_crop | 386 | public | None | No | Renders the cropped result and accepts the dialog |
| get_result | 416 | public | tuple | No | Returns the cropped image and mode chosen |

---

### history_model

**Path**: `gui/history_model.py` - 412 lines
**Purpose**: Model/View layer for the history tab — an LRU thumbnail cache, a thumbnail-painting delegate, the in-memory table model, and a text+date filter proxy.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| COL_THUMBNAIL | 15 | constant | Column index 0 |
| COL_DATETIME | 16 | constant | Column index 1 |
| COL_PROVIDER | 17 | constant | Column index 2 |
| COL_MODEL | 18 | constant | Column index 3 |
| COL_PROMPT | 19 | constant | Column index 4 |
| COL_RESOLUTION | 20 | constant | Column index 5 |
| COL_COST | 21 | constant | Column index 6 |
| COL_REFS | 22 | constant | Column index 7 |
| NUM_COLUMNS | 23 | constant | Total column count (8) |
| COLUMN_HEADERS | 25 | constant | Display header strings |
| ROLE_ENTRY_DICT | 31 | constant | Custom role returning the raw history dict |
| ROLE_THUMBNAIL_PATH | 32 | constant | Custom role returning the thumbnail path |
| ROLE_SORT_VALUE | 33 | constant | Custom role used as the proxy's sort role |

#### Classes

**`ThumbnailCache`** (line 36) — LRU cache of QPixmap thumbnails with hit/miss statistics.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 39 | constructor | None | No | Sets max size and initializes counters |
| get | 46 | public | Optional[QPixmap] | No | Returns a cached pixmap, loading and evicting as needed |
| get_stats | 67 | public | dict | No | Hit/miss/size statistics |
| clear | 78 | public | None | No | Empties the cache |

**`ThumbnailDelegate`** (line 84) — QStyledItemDelegate that centers cached thumbnails in the thumbnail column.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 87 | constructor | None | No | Holds a reference to the shared `ThumbnailCache` |
| paint | 91 | public | None | No | Centers the pixmap, honoring selection highlight |
| sizeHint | 106 | public | QSize | No | Returns 80×80 for the thumbnail column |

**`HistoryTableModel`** (line 113) — QAbstractTableModel holding all history entries in memory; only visible rows are rendered.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 119 | constructor | None | No | Initializes the backing entry list |
| rowCount | 123 | public | int | No | Number of history entries |
| columnCount | 126 | public | int | No | `NUM_COLUMNS` |
| headerData | 129 | public | Optional[str] | No | Horizontal display headers |
| data | 135 | public | Any | No | Dispatches by role (display, tooltip, custom roles) |
| _display_data | 162 | private | Any | No | Per-column display strings |
| _tooltip_data | 191 | private | Optional[str] | No | Per-column tooltip text |
| _sort_value | 200 | private | Any | No | Per-column sortable value for `ROLE_SORT_VALUE` |
| _format_timestamp | 211 | private | str | No | Human-readable date/time string |
| _parse_timestamp | 228 | private | float | No | Accepts epoch or ISO string forms |
| @staticmethod _ref_count | 241 | static | int | No | Counts `imagen_references` / `reference_image` entries |
| @staticmethod _ref_tooltip | 251 | static | Optional[str] | No | Builds the reference-image tooltip listing |
| add_entry | 270 | public | None | No | Appends one entry with begin/endInsertRows |
| add_entries | 277 | public | None | No | Appends a batch (used by progressive loading) |
| set_data | 287 | public | None | No | Replaces the whole dataset |
| clear | 293 | public | None | No | Removes all rows |
| get_entry | 299 | public | Optional[Dict] | No | Raw dict for a source row |
| total_count | 305 | public | int | No | Entry count |
| entry_paths | 309 | public | set | No | Image paths for all entries |

**`HistoryFilterProxyModel`** (line 314) — QSortFilterProxyModel adding free-text search plus a date range, sorting on `ROLE_SORT_VALUE`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 317 | constructor | None | No | Sets the sort role and clears filters |
| setFilterText | 325 | public | None | No | Matches filename, prompt, provider, model |
| setDateRange | 330 | public | None | No | Sets optional from/to QDate bounds |
| filterAcceptsRow | 336 | public | bool | No | Combines text and date-range predicates |
| @staticmethod _extract_date | 372 | static | Optional[QDate] | No | Normalizes epoch/ISO timestamps to QDate |
| filtered_count | 410 | public | int | No | Number of rows surviving the filter |

---

### UpscalingSelector

**Path**: `gui/upscaling_widget.py` - 328 lines
**Purpose**: Radio-button widget shown when the requested resolution exceeds the provider's native output — lets the user pick Lanczos, Real-ESRGAN, or the Stability API upscaler, and offers an in-app Real-ESRGAN install.
**Language**: Python

#### Classes

**`UpscalingSelector`** (line 15) — hidden by default; revealed by callers when upscaling is relevant. Signal: `upscalingChanged(dict)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 20 | constructor | None | No | Builds the UI and hides the widget |
| init_ui | 25 | public | None | No | Method radio group, Real-ESRGAN model combo, install button, info label |
| _on_method_changed | 145 | private | None | No | Shows/hides method-specific options |
| _on_settings_changed | 153 | private | None | No | Emits `upscalingChanged` with current settings |
| update_resolution_info | 158 | public | None | No | Recomputes and displays the current→target scale factor |
| get_settings | 188 | public | dict | No | Returns `{method, enabled, model_name?}` |
| set_settings | 210 | public | None | No | Restores selection from saved config |
| set_enabled_methods | 234 | public | None | No | Enables/disables each method by availability, toggling the install prompt |
| check_realesrgan_availability | 257 | public | bool | No | Imports torch/torchvision/realesrgan, patching the legacy `functional_tensor` path |
| check_stability_api_availability | 277 | public | bool | No | True when a Stability API key is configured |
| _on_install_clicked | 281 | private | None | No | Runs the confirm + progress install dialogs |
| _on_installation_complete | 294 | private | None | No | Re-checks availability and updates the UI |

---

### MidjourneyWatcher

**Path**: `gui/midjourney_watcher.py` - 323 lines
**Purpose**: Watches the downloads folder for images produced by Midjourney (via Discord) and scores them against active generation sessions so a downloaded file can be auto-associated with the prompt that produced it.
**Language**: Python

#### Classes

**`MidjourneySession`** (line 19) — `@dataclass` describing one in-flight Midjourney generation.

**Fields**: `session_id`, `prompt`, `slash_command`, `start_time`, `dialog_open` (default True), `associated_images` (list), `model`, `provider` (default `"midjourney"`).

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| is_expired | 30 | public | bool | No | True once the session is older than the window (default 300 s) |
| time_since_start | 35 | public | float | No | Seconds elapsed since the session began |

**`MidjourneyWatcher`** (line 40) — QObject wrapping a `QFileSystemWatcher` plus a 30 s expiry timer. Signals: `imageDetected(Path, dict)`, `sessionStarted(str, str, str)`, `sessionEnded(str)`. Class constants `MIDJOURNEY_PATTERNS` and `IMAGE_EXTENSIONS` drive filename heuristics.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 62 | constructor | None | No | Creates the watcher, session map, cleanup timer, and default thresholds |
| set_watch_path | 84 | public | None | No | Points the file-system watcher at a directory |
| start_session | 118 | public | str | No | Registers a new session and emits `sessionStarted` |
| end_session | 137 | public | None | No | Marks a session finished and emits `sessionEnded` |
| _on_directory_changed | 144 | private | None | No | Detects newly appeared image files, skipping already-processed ones |
| _process_new_image | 179 | private | None | No | Scores the image and emits `imageDetected` |
| _calculate_confidence | 190 | private | Optional[Dict] | No | Ranks sessions by filename pattern + timing to pick the best match |
| _cleanup_expired_sessions | 286 | private | None | No | Timer slot removing sessions past the time window |
| set_enabled | 302 | public | None | No | Turns watching on/off |
| set_auto_accept_threshold | 310 | public | None | No | Confidence % above which matching is automatic (default 85) |
| set_time_window | 315 | public | None | No | Session expiry window in seconds |
| get_active_sessions | 320 | public | list | No | Currently live sessions |

---

### dialog_utils

**Path**: `gui/dialog_utils.py` - 319 lines
**Purpose**: Message-box helpers that guarantee every user-facing message is also logged, plus the operation-guard system that blocks input and prevents re-entrancy while a dialog runs an async QThread operation.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| show_error | 15 | public | None | No | Logs (with `exc_info` when an exception is passed) then shows a critical box |
| show_warning | 32 | public | None | No | Logs at the requested level then shows a warning box |
| show_info | 46 | public | None | No | Optionally logs then shows an information box |
| show_question | 61 | public | QMessageBox.StandardButton | No | Logs both the question and the user's answer |
| guard_operation | 273 | public | Callable | No | Decorator factory blocking a method while another guarded operation runs |
| decorator | 295 | private | Callable | No | Inner decorator returned by `guard_operation` |
| wrapper | 297 | private | Any | No | Innermost wrapper performing the `check_operation_running` gate |

#### Classes

**`InputBlockerEventFilter`** (line 84) — QObject event filter installed on the **QApplication** but scoped to descendants of `root` (installing on the dialog alone is ineffective, since events go to the focused child). Blocks mouse press/release/double-click, key press/release, and shortcut/shortcut-override events; optionally focus changes. Paint, Escape, and close events are allowed through so the UI stays responsive and cancellable.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 104 | constructor | None | No | Builds the blocked-event-type set from the root and options |
| eventFilter | 124 | public | bool | No | Returns True (swallow) for blocked types on in-scope widgets |

**`OperationGuardMixin`** (line 149) — mixin for dialogs running async QThread work; tracks operation state, installs the input blocker, and reports warnings through a `status_console` attribute when present.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| init_operation_guard | 174 | public | None | No | Sets up state and discovers an optional status console |
| is_operation_running | 193 | public | bool | No | Current guard state |
| start_operation | 197 | public | None | No | Marks the operation running and installs the input blocker |
| end_operation | 224 | public | None | No | Clears state and removes the blocker |
| check_operation_running | 244 | public | bool | No | Gate used by `@guard_operation`; optionally warns and logs |

---

### DialogHistoryWidget

**Path**: `gui/history_widget.py` - 295 lines
**Purpose**: Reusable per-dialog interaction history — a table of past LLM inputs/responses with preview, persistence to disk, and export, embeddable in any dialog that calls an LLM.
**Language**: Python

#### Classes

**`DialogHistoryWidget`** (line 19) — namespaced by `dialog_name` so each dialog keeps its own history file and QSettings. Signals: `itemSelected(dict)`, `itemDoubleClicked(dict)`. Uses `common.dialog_conventions` splitter helpers.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 25 | constructor | None | No | Sets the dialog namespace, QSettings, and empty history |
| init_ui | 33 | public | None | No | Table + preview pane in a standard persisted splitter |
| add_entry | 115 | public | None | No | Appends an input/response pair with provider, model, metadata |
| refresh_table | 133 | public | None | No | Rebuilds table rows from the history list |
| _on_selection_changed | 186 | private | None | No | Shows the selected entry in the preview and emits `itemSelected` |
| _on_item_double_clicked | 205 | private | None | No | Emits `itemDoubleClicked` for reuse of a past entry |
| clear_history | 212 | public | None | No | Confirms, then empties history and file |
| save_history | 230 | public | None | No | Writes the history JSON to disk |
| load_history | 251 | public | None | No | Reads the history JSON back |
| export_history | 270 | public | None | No | Saves history to a user-chosen file |
| get_latest_entry | 289 | public | Optional[dict] | No | Most recent entry |
| get_history | 293 | public | list | No | Full history list |

---

### MidjourneyPanel

**Path**: `gui/midjourney_panel.py` - 286 lines
**Purpose**: Provider panel exposing Midjourney-specific parameters (aspect, stylize, chaos, version, quality, etc.) and building the `/imagine` slash command to paste into Discord.
**Language**: Python

#### Classes

**`MidjourneyPanel`** (line 17) — Signals: `settingsChanged(dict)`, `openDiscord()`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 24 | constructor | None | No | Stores config, builds the UI, loads saved settings |
| init_ui | 31 | public | None | No | Parameter controls, generated-command box, Discord button |
| on_settings_changed | 181 | public | None | No | Recomputes settings and emits `settingsChanged` |
| get_settings | 186 | public | Dict | No | Current parameter values as a dict |
| set_settings | 201 | public | None | No | Applies a settings dict back onto the controls |
| update_command | 232 | public | str | No | Renders the full `/imagine` slash command for a prompt |
| load_settings | 273 | public | None | No | Restores settings from config |
| save_settings | 281 | public | None | No | Persists settings to config |

---

### ReferenceSelectionDialog

**Path**: `gui/reference_selection_dialog.py` - 286 lines
**Purpose**: Card-grid dialog for choosing at most N images from a larger set — used when switching modes or when a provider's reference-image limit forces a narrowing.
**Language**: Python

#### Classes

**`ReferenceImageCard`** (line 22) — QFrame card with thumbnail, reference id, and checkbox. Signal: `selection_changed(bool)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 29 | constructor | None | No | Stores path/id and builds the card |
| _init_ui | 50 | private | None | No | Thumbnail label, filename, reference-id badge, checkbox |
| _on_checkbox_changed | 111 | private | None | No | Emits `selection_changed` and restyles |
| _update_style | 117 | private | None | No | Applies the selected/unselected border styling |
| set_selected | 134 | public | None | No | Programmatically sets the checkbox state |
| mousePressEvent | 138 | public | None | No | Clicking anywhere on the card toggles selection |

**`ReferenceSelectionDialog`** (line 145) — modal dialog wrapping a scrollable grid of cards with an N-item cap.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 152 | constructor | None | No | Takes paths, max selection, title, and explanation message |
| _init_ui | 182 | private | None | No | Message label, scrollable card grid, counter, button box |
| _on_selection_changed | 228 | private | None | No | Enforces the cap and updates the selection count |
| _update_ok_button | 247 | private | None | No | Enables OK only when the selection is valid |
| _on_accept | 262 | private | None | No | Collects the checked paths and accepts |
| get_selected_paths | 279 | public | List[Path] | No | The chosen image paths |

---

### MidjourneyMatchDialog

**Path**: `gui/midjourney_match_dialog.py` - 280 lines
**Purpose**: Confirmation dialog shown when the watcher detects a downloaded image — previews the image, shows the confidence breakdown, and lets the user accept, reject, or manually reassign the session.
**Language**: Python

#### Classes

**`MidjourneyMatchDialog`** (line 18) — Signals: `accepted(str, str, Path)` (session_id, prompt, image_path) and `rejected(Path)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 25 | constructor | None | No | Takes the image path, confidence data, and all active sessions |
| setup_ui | 45 | public | None | No | Splitter with image preview, confidence bar/details, session combo, buttons |
| load_image | 226 | public | None | No | Loads and proportionally scales the preview pixmap |
| _on_session_changed | 244 | private | None | No | Switches the displayed prompt when a different session is picked |
| _accept_match | 255 | private | None | No | Emits `accepted` for the chosen session |
| _reject_match | 264 | private | None | No | Emits `rejected` for the image |
| keyPressEvent | 269 | public | None | No | Keyboard accept/reject shortcuts |

---

### workers

**Path**: `gui/workers.py` - 270 lines
**Purpose**: QObject worker classes moved onto QThreads for every blocking GUI operation — image generation (batch and streaming), batch-job loading, progressive history loading, and Ollama detection.
**Language**: Python

#### Classes

**`GenWorker`** (line 12) — image generation worker. Signals: `progress(str)`, `error(str)`, `finished(list, list)` — `(texts, images)`. Constructs its provider inside `run()` via `providers.get_provider`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 19 | constructor | None | No | Stores provider, model, prompt, auth mode, and extra kwargs (width/height/steps/…) |
| run | 27 | public | None | No | Runs generation and emits progress/finished/error |

**`StreamingGenWorker`** (line 76) — streams partial frames through the provider's `on_partial` callback, keeping the same constructor and `finished` shape as `GenWorker` so `MainWindow` can swap workers without changing dispatch. Signals: `partial(int, bytes)`, `finished(list, list)`, `error(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 95 | constructor | None | No | Same keyword-only signature as `GenWorker` |
| run | 103 | public | None | No | Builds the provider and streams frames until completion |
| on_partial | 113 | nested | None | No | Callback re-emitting each partial PNG as `partial(index, bytes)` |

**`BatchJobsLoaderWorker`** (line 130) — loads `BATCH_JOBS_PATH`. Signals: `loaded(list)`, `error(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 135 | constructor | None | No | No arguments |
| run | 138 | public | None | No | Reads the batch-jobs JSON and emits the entries |

**`HistoryLoaderWorker`** (line 155) — progressive history metadata loader. Signals: `progress(int, int)`, `batch_loaded(list)`, `finished()`, `error(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 163 | constructor | None | No | Takes history paths, a start index, and a batch size (default 25) |
| stop | 170 | public | None | No | Requests cooperative cancellation |
| run | 174 | public | None | No | Reads sidecar metadata in batches, emitting each batch |

**`OllamaDetectionWorker`** (line 242) — probes a local Ollama endpoint without blocking startup. Signals: `models_detected(list)`, `no_ollama()`, `finished()`, `error(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 250 | constructor | None | No | Defaults the endpoint to `http://localhost:11434` |
| run | 254 | public | None | No | Queries the endpoint and emits detected models or `no_ollama` |

---

### ExamplesDialog

**Path**: `gui/dialogs.py` - 225 lines
**Purpose**: "Examples & Templates" picker — a curated list of sample prompts plus Gemini doc templates whose `[placeholder]` fields are turned into a live form with remembered values.
**Language**: Python

#### Classes

**`ExamplesDialog`** (line 19) — inherits `DialogCleanupMixin` and `QDialog`; the `EXAMPLES` class constant holds the sample prompt strings, and templates come from `templates.get_gemini_doc_templates()`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 33 | constructor | None | No | Builds the Examples/Templates tabs, append checkbox, shortcut hint, and restores geometry |
| on_dialog_close | 140 | public | None | No | Persists geometry on every exit path (OK, Cancel, Escape, X) |
| _rebuild_template_form | 144 | private | None | No | Regex-extracts `[placeholders]`, builds fields, applies defaults and last-used values |
| _on_ok | 186 | private | None | No | Records the append-to-prompt choice and accepts |
| get_selected_prompt | 191 | public | Optional[str] | No | Returns the chosen example or the filled-in template text |

---

### llm_utils

**Path**: `gui/llm_utils.py` - 181 lines
**Purpose**: Shared LLM-dialog utilities — the standard status console widget and LiteLLM setup/request helpers. Also re-exports `core.llm_parsing.LLMResponseParser` for backwards compatibility.
**Language**: Python

#### Classes

**`DialogStatusConsole`** (line 15) — QGroupBox with a read-only monospace `QTextEdit`, used at the bottom of every LLM-calling dialog.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 18 | constructor | None | No | Sets the group title and builds the UI |
| init_ui | 22 | public | None | No | Read-only console with Consolas/Courier fallback font |
| log | 52 | public | None | No | Appends a level-colored, timestamped line |
| clear | 80 | public | None | No | Empties the console |
| separator | 84 | public | None | No | Writes a visual separator line |

**`LiteLLMHandler`** (line 89) — static helpers for LiteLLM configuration and request assembly.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| @staticmethod setup_litellm | 93 | static | Tuple[bool, Optional[Any]] | No | Imports LiteLLM, sets `LITELLM_LOG`, attaches the console log handler |
| @staticmethod prepare_request | 145 | static | Dict[str, Any] | No | Builds the request dict (model, messages, temperature, max tokens, auth mode) |

**`LiteLLMHandler.LiteLLMConsoleHandler`** (line 113) — nested `logging.Handler` defined inside `setup_litellm`, forwarding LiteLLM's own log records to the console logger.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| emit | 114 | public | None | No | Re-emits `LiteLLM` records as `console.info("LiteLLM: …")` |

---

### FlowLayout

**Path**: `gui/flow_layout.py` - 162 lines
**Purpose**: Qt layout that arranges child widgets left-to-right and wraps to the next line when the row is full (based on Qt's Flow Layout example).
**Language**: Python

#### Classes

**`FlowLayout`** (line 7) — QLayout subclass with independent horizontal/vertical spacing.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 13 | constructor | None | No | Takes parent, margin, and h/v spacing (−1 = derive from style) |
| __del__ | 31 | dunder | None | No | Drains and releases all layout items |
| addItem | 37 | public | None | No | Appends a layout item |
| horizontalSpacing | 41 | public | int | No | Explicit h-spacing or the smart default |
| verticalSpacing | 48 | public | int | No | Explicit v-spacing or the smart default |
| count | 55 | public | int | No | Number of items |
| itemAt | 59 | public | QWidgetItem | No | Item at an index |
| takeAt | 65 | public | QWidgetItem | No | Removes and returns the item at an index |
| expandingDirections | 71 | public | Qt.Orientations | No | No expansion in either direction |
| hasHeightForWidth | 75 | public | bool | No | True — height depends on width |
| heightForWidth | 79 | public | int | No | Height required to lay out at a given width |
| setGeometry | 84 | public | None | No | Performs the real layout pass |
| sizeHint | 89 | public | QSize | No | Same as `minimumSize` |
| minimumSize | 93 | public | QSize | No | Union of item minimum sizes plus margins |
| _do_layout | 104 | private | int | No | Core wrapping algorithm; `test_only` computes height without moving widgets |
| _smart_spacing | 151 | private | int | No | Derives spacing from the parent widget's style metrics |

---

### shortcut_hint_widget

**Path**: `gui/shortcut_hint_widget.py` - 132 lines
**Purpose**: The small "Shortcuts: …" hint line shown at the bottom of dialogs — subtle by default, brightened on hover.
**Language**: Python

#### Classes

**`ShortcutHintLabel`** (line 8) — QLabel with mouse tracking and a hover style swap.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 11 | constructor | None | No | Stores the plain text, enables word wrap and mouse tracking |
| _set_default_style | 34 | private | None | No | Applies the muted, non-hovered styling |
| _set_hover_style | 55 | private | None | No | Applies the high-contrast hover styling |
| enterEvent | 80 | public | None | No | Switches to the hover style |
| leaveEvent | 87 | public | None | No | Restores the default style |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| create_shortcut_hint | 95 | public | ShortcutHintLabel | No | Factory that prefixes `"Shortcuts: "` when absent |
| create_enhanced_shortcut_html | 113 | public | str | No | Hover-free alternative returning styled HTML with better base contrast |

---

### gui (package init)

**Path**: `gui/__init__.py` - 126 lines
**Purpose**: GUI package entry point — installs a Qt message filter, loads the Maestro fonts and theme, applies the Fusion style, logs the GUI environment, and runs `MainWindow`.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| launch_gui | 7 | public | NoReturn | No | Imports PySide6 (raising a clear install message if missing), creates/reuses the QApplication, sets org/app names, loads Roboto + Limelight from `gui/resources/fonts`, applies Fusion then the Maestro theme when `ui_maestro_theme` is set, logs PySide6/Qt/QPA/style/QtWebEngine availability, shows `MainWindow`, and enters `app.exec()` |
| qt_message_handler | 19 | private | None | No | Nested handler suppressing benign Qt/FFmpeg noise (monitor-interface, `setGeometry`, aac/h264/hevc/vp9 warnings) and logging everything else |

**Exports**: `__all__ = ["launch_gui"]`

---

### ImagePreviewPopup

**Path**: `gui/image_preview_popup.py` - 115 lines
**Purpose**: Frameless always-on-top popup that shows a scaled full-size image preview when hovering a thumbnail, with a delayed-hide timer to avoid flicker.
**Language**: Python

#### Classes

**`ImagePreviewPopup`** (line 10) — QLabel configured with `Qt.ToolTip | FramelessWindowHint | WindowStaysOnTopHint` so it bypasses the window manager.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 13 | constructor | None | No | Sets max width/height, popup window flags, border/background styling, and the hide timer |
| show_preview | 49 | public | None | No | Loads the image, scales it proportionally into the max box, and positions it near the cursor within screen bounds |
| schedule_hide | 109 | public | None | No | Starts the delayed-hide timer |
| cancel_hide | 113 | public | None | No | Cancels a pending hide (cursor re-entered) |

---

### gui.resources (package init)

**Path**: `gui/resources/__init__.py` - 0 lines
**Purpose**: Empty package marker making `gui/resources/` importable; the directory holds bundled assets such as the Roboto and Limelight font files loaded by `launch_gui`.
**Language**: Python

*(No symbols — empty file.)*

---

## GUI — Layout Tab, Styles & Common Widgets

The publication **layout engine's** PySide6 front end (`gui/layout/`), the **Custom Styles** UI (`gui/styles/`), and the shared dialog/widget conventions every tab depends on (`gui/common/`, `gui/utils/`). The layout package follows a strict split: inspector/panel widgets emit *intent* signals only, and `LayoutTab` owns every mutation of the `DocumentSpec` model plus the history snapshots.

---

### LayoutTab
**Path**: `gui/layout/layout_tab.py` - 1031 lines
**Purpose**: The Layout tab itself — toolbar, page setup, canvas, designer panel, inspectors, and the single owner of all document mutation, history snapshots, project/template/bundle I/O, and PDF/PNG export.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_DEFAULT_STROKE_PX` | 27 | constant | Panel stroke applied when "borderless" is unchecked |

#### Classes

##### `LayoutTab` (QWidget) — line 30
Hosts the whole Layout workspace. Signals: `documentChanged` (any model change), `sendToImageRequested` (asks `MainWindow` to open the Image tab for one region; payload `{region_id, prompt, width, height}`), and `fillAllRequested` (layout-complete mode — an ordered list of those payloads). Both decouple the tab from `MainWindow`. A class-level `_OVERLAY_DEFAULT_TEXT` map supplies starter text per overlay kind.

Key instance state set in `__init__` (line 40): `config`, `document: DocumentSpec`, `history: History`, `_prompt_worker` (kept alive so the QThread isn't GC'd mid-run), `_locked`, `_knife_region_id`, `_merge_base_id`, `_last_orientation`.

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 40 | constructor | None | No | Store config, load lock state, build UI, restore last session |
| `_build` | 56 | private | None | No | Toolbar (New/Open/Save/Export PDF/PNG/History/Template/Bundle/Fill all), lock toggle, main splitter, canvas + panels |
| `_adopt_document` | 191 | private | None | No | Take ownership of a `DocumentSpec`, start a new `History`, apply the default style for its content kind |
| `_sync_page_setup_from_document` | 202 | private | None | No | Reflect the loaded page size/orientation in the controls; a stored `render_on_top` override wins over the orientation default |
| `new_document` | 224 | public | None | No | Create a blank one-page document at the current page setup |
| `_on_page_size_changed` | 232 | private | None | No | Push a new `PageSize` onto page 0 and re-render; keeps the split orientation in step |
| `_on_orient_split_toggled` | 244 | private | None | No | Apply the render-on-top choice and persist it on the document |
| `_apply_split_orientation` | 251 | private | None | No | Horizontal = canvas left/settings right; Vertical = canvas above settings |
| `_sync_split_to_orientation` | 264 | private | None | No | Auto-flip the toggle only on a real portrait↔landscape change, so manual overrides survive |
| `_refresh` | 279 | private | None | No | Rebuild the canvas scene, rebuild geometry/overlay handles, refresh the overlay list, emit `documentChanged` |
| `set_refresh_suspended` | 297 | public | None | No | Block scene rebuilds during a live handle drag (else handles vanish) |
| `snapshot_and_refresh` | 301 | public | None | No | Append a history snapshot then refresh |
| `_load_locked` | 307 | private | bool | No | Read the persisted text-lock state (defaults to locked; never blocks startup) |
| `_update_lock_button` | 316 | private | None | No | Update lock button label/tooltip (frames are always locked; the toggle governs text) |
| `_on_lock_toggled` | 326 | private | None | No | Apply, persist and re-render on lock change |
| `_persist_locked` | 332 | private | None | No | Best-effort write of the lock flag to the layout config |
| `_session_path` | 344 | private | Optional[Path] | No | `<config_dir>/layout/last_session.iaiproj.json` |
| `_restore_session_or_new` | 350 | private | None | No | Reload the last session on startup; a corrupt session falls back to a new document |
| `save_session` | 363 | public | None | No | Persist the current document as the session file |
| `_find_region` | 381 | private | Optional[Region] | No | Look up a region on page 0 by id |
| `_current_page` | 391 | private | Optional[PageSpec] | No | Page 0 of the current document |
| `_region_index` | 396 | private | Optional[int] | No | Index of a region within page 0 |
| `_apply_delete` | 405 | private | bool | No | Delete a region (clearing the shape editor first) and snapshot |
| `_apply_knife` | 417 | private | bool | No | Split a region along a cut line via `region_ops.split_region`; reports a miss in the status bar |
| `_apply_merge` | 433 | private | bool | No | Merge two adjacent regions via `region_ops.merge_regions`; reports non-adjacency |
| `_on_region_delete_requested` | 453 | private | None | No | Inspector delete → `_apply_delete` |
| `_on_region_knife_toggled` | 456 | private | None | No | Arm/disarm the knife tool on the canvas |
| `_on_canvas_knife_line` | 469 | private | None | No | Two canvas clicks became a cut line → apply the split and disarm |
| `_on_region_merge_toggled` | 476 | private | None | No | Arm/disarm merge mode with the given region as base |
| `_on_canvas_merge_target` | 485 | private | None | No | Clicked region becomes the merge partner |
| `_reset_region_tools` | 492 | private | None | No | Disarm knife/merge and uncheck inspector toggles without re-emitting |
| `_on_region_selected` | 504 | private | None | No | Feed the content + geometry inspectors with the region and its resolved text style |
| `_on_region_edit_shape_toggled` | 515 | private | None | No | Enter/leave manual geometry editing for a region |
| `_on_region_content_changed` | 518 | private | None | No | Inspector content edit → `set_region_content` |
| `_on_region_text_style_changed` | 521 | private | None | No | Apply a chosen font family/size to a text region |
| `_on_region_bleed_toggled` | 538 | private | None | No | Toggle full-bleed on a region and snapshot |
| `_on_region_borderless_toggled` | 547 | private | None | No | Toggle the panel stroke (uses `_DEFAULT_STROKE_PX`) and snapshot |
| `_on_region_z_changed` | 559 | private | None | No | Change a region's z-order and snapshot |
| `_new_overlay_id` | 574 | private | str | No | Next free `ovN` id on the page |
| `_add_overlay` | 581 | private | bool | No | Add a speech/thought/caption/SFX overlay centered on the page (speech/thought get a tail) |
| `_find_overlay` | 597 | private | Optional[Overlay] | No | Look up an overlay by id |
| `_delete_overlay` | 606 | private | bool | No | Remove an overlay and snapshot |
| `_set_overlay_rotation` | 619 | private | bool | No | Set overlay rotation in degrees |
| `_set_overlay_curve` | 627 | private | bool | No | Turn text-on-a-curve on/off for caption/SFX overlays; materializes a default arc and centers the alignment |
| `_set_overlay_outline` | 660 | private | bool | No | Set outline width/color on the overlay's text style; no-ops on unchanged values so undo history stays clean |
| `_on_overlay_selected` | 688 | private | None | No | Sync the overlay inspector selection and leave edit mode |
| `_on_overlay_edit_toggled` | 692 | private | None | No | Enter/leave overlay handle editing |
| `set_region_content` | 695 | public | None | No | Programmatic API: set a region's `image_ref` or `text` and re-render |
| `_on_region_prompt_changed` | 711 | private | None | No | Persist an edited image prompt on the region (metadata only, no re-render) |
| `_on_region_prompt_suggest` | 719 | private | None | No | Inspector "Suggest with AI" → `suggest_region_prompt` |
| `_on_region_send_to_image` | 722 | private | None | No | Persist the prompt and emit `sendToImageRequested` with the region's pixel size |
| `_collect_fill_payloads` | 735 | private | list[dict] | No | Ordered payloads for every page-0 image region carrying a prompt |
| `_on_fill_all_clicked` | 748 | private | None | No | Layout-complete mode: emit `fillAllRequested` for sequential filling |
| `suggest_region_prompt` | 758 | public | None | No | Draft an image prompt from the project theme via `PromptSuggestWorker`; an injected `completion_fn` runs synchronously (tests), production wraps `designer.run_completion` |
| `_on_prompt_suggested` | 791 | private | None | No | Store the suggestion on the region, push it into the inspector, log to the designer console |
| `_on_prompt_failed` | 806 | private | None | No | Re-enable Suggest, force the console open, log the error |
| `save_project_to` | 814 | public | None | No | Programmatic save via `project_io.save_project` |
| `open_project_from` | 818 | public | None | No | Load a project, adopt it, sync page setup, refresh |
| `export_pdf_to` | 823 | public | None | No | `qt_renderer.export_document_pdf` |
| `export_png_to` | 827 | public | None | No | `qt_renderer.save_page_png` for page 0 with the project style |
| `_on_design_clicked` | 836 | private | None | No | Kick off the AI designer with the prompt text and current regions |
| `_on_layout_proposed` | 846 | private | None | No | Designer result → `apply_designer_result` |
| `apply_designer_result` | 850 | public | None | No | Adopt proposed regions/overlays, switch the default style on a content-kind change, reposition stranded overlays on a regions-only redesign, snapshot |
| `restore_snapshot` | 878 | public | None | No | Restore a history snapshot and branch the timeline from it |
| `_open_history` | 886 | private | None | No | Open `HistoryWindow` wired to `restore_snapshot` |
| `apply_style` | 891 | public | None | No | Apply a `ProjectStyle`, marking it user-modified so the designer won't overwrite it |
| `export_template_to` | 898 | public | None | No | `template_io.export_template` |
| `import_template_from` | 904 | public | None | No | `template_io.import_template` then adopt + refresh |
| `_bundle_font_resolver` | 910 | private | Optional[Callable] | No | Lazily build/cache a `FontManager` resolver; failure degrades to by-name font records |
| `_bundle_extract_dir` | 928 | private | Path | No | Where an imported `.iaibundle` is unpacked (`<config_dir>/layout/bundles/<stem>`) |
| `export_bundle_to` | 935 | public | None | No | `bundle_io.export_bundle` (project + images + fonts); surfaces manifest warning counts |
| `import_bundle_from` | 945 | public | None | No | Unpack a bundle, adopt the document, sync page setup |
| `_export_bundle_dialog` | 951 | private | None | No | `.iaibundle` save dialog |
| `_import_bundle_dialog` | 960 | private | None | No | `.iaibundle` open dialog |
| `_report_error` | 970 | private | None | No | Repo rule: log with traceback, set the status bar, show a `QMessageBox` — and never crash while reporting |
| `_export_template_dialog` | 980 | private | None | No | `.iailayout.json` save dialog |
| `_import_template_dialog` | 989 | private | None | No | `.iailayout.json` open dialog |
| `_save_dialog` | 999 | private | None | No | `.iaiproj.json` save dialog |
| `_open_dialog` | 1007 | private | None | No | Project open dialog (`*.iaiproj.json *.layout.json`) |
| `_export_dialog` | 1016 | private | None | No | PDF export dialog |
| `_export_png_dialog` | 1024 | private | None | No | PNG export dialog |

---

### Text Generation Dialog
**Path**: `gui/layout/text_gen_dialog.py` - 669 lines
**Purpose**: LLM-driven text generation for a layout text block, with per-template-category prompt builders and a status console.
**Language**: Python

#### Classes

##### `TextGenerationWorker` (QThread) — line 29
Off-thread LLM call. Signals: `finished(str)`, `error(str)`, `progress(str)`.

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 36 | constructor | None | No | Capture config, block context, custom prompt, temperature, provider, model |
| `run` | 48 | public | None | No | Set up LiteLLM, resolve provider/auth mode/API key (Google `api-key` vs `gcloud`), call the model, emit the text |
| `_build_prompt` | 172 | private | str | No | Dispatch to the category-specific prompt builder (or the custom prompt) |
| `_build_children_book_prompt` | 208 | private | str | No | Children's-book page prose prompt |
| `_build_comic_prompt` | 254 | private | str | No | Comic panel/dialogue prompt |
| `_build_magazine_prompt` | 308 | private | str | No | Magazine article/pull-quote prompt |
| `_build_generic_prompt` | 364 | private | str | No | Fallback prompt for uncategorized templates |

##### `TextGenerationDialog` (DialogCleanupMixin, QDialog) — line 383
Dialog wrapper: settings row, custom-prompt toggle, generated-text editor, and a `DialogStatusConsole` below a persisted splitter.

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 386 | constructor | None | No | Capture block/document/template context, provider/model, build UI, load settings |
| `init_ui` | 420 | public | None | No | Splitter layout, editor, console, primary action + default button binding |
| `_create_top_section` | 467 | private | QWidget | No | Provider/model/temperature controls and the custom-prompt box |
| `_on_custom_prompt_toggled` | 539 | private | None | No | Enable/disable the custom-prompt editor |
| `load_settings` | 543 | public | None | No | Restore QSettings (geometry, splitter, provider/model) |
| `save_settings` | 550 | public | None | No | Persist those settings |
| `generate` | 556 | public | None | No | Primary action: start the worker, disabling re-entry |
| `_on_progress` | 607 | private | None | No | Log worker progress to the console |
| `_on_finished` | 611 | private | None | No | Put generated text in the editor and log it |
| `_on_error` | 625 | private | None | No | Surface and log a generation failure |
| `get_generated_text` | 630 | public | str | No | The accepted text, for the caller to apply |
| `showEvent` | 636 | public | None | No | Reset cleanup state / restore geometry on show |
| `on_dialog_close` | 644 | public | None | No | `DialogCleanupMixin` hook: stop the worker and save settings on every exit path |

---

### InspectorWidget
**Path**: `gui/layout/inspector_widget.py` - 484 lines
**Purpose**: Block-level property inspector for the templated Books/Layout model (`TextBlock` / `ImageBlock`) — geometry, typography, image source, and LLM/image generation entry points.
**Language**: Python

#### Classes

##### `InspectorWidget` (QWidget) — line 21
Signal: `blockModified` (emitted after `apply_changes`). Holds the current page/block plus LLM context (config, document, template category/name, page number, provider/model).

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 26 | constructor | None | No | Initialize state + LLM context defaults, build and clear the inspector |
| `init_ui` | 45 | public | None | No | Scrollable form with common, text, and image property groups |
| `set_context` | 75 | public | None | No | Inject config/document/template/page/provider/model used by the generators |
| `set_block` | 89 | public | None | No | Bind the inspector to a page + block id |
| `clear_inspector` | 108 | public | None | No | Hide all type-specific groups and disable Apply |
| `display_block_properties` | 129 | public | None | No | Populate the common (x/y/w/h) fields and dispatch by block type |
| `display_text_block_properties` | 185 | public | None | No | Text, font family/size/weight/italic, color, alignment |
| `display_image_block_properties` | 264 | public | None | No | Image path, fit mode, border radius, stroke width/color |
| `apply_changes` | 337 | public | None | No | Write rect + type-specific edits back to the block and emit `blockModified` |
| `apply_text_block_changes` | 363 | public | None | No | Commit text and `TextStyle` fields |
| `apply_image_block_changes` | 376 | public | None | No | Commit image path and `ImageStyle` fields |
| `choose_text_color` | 387 | public | None | No | `QColorDialog` for the text color |
| `choose_stroke_color` | 394 | public | None | No | `QColorDialog` for the stroke color |
| `browse_image` | 401 | public | None | No | File dialog for an image file |
| `select_from_history` | 413 | public | None | No | Pick a previously generated image via `ImageHistoryDialog` |
| `generate_image` | 428 | public | None | No | Walk up to `MainWindow` and switch to the Generate tab |
| `generate_text` | 445 | public | None | No | Open `TextGenerationDialog` with the full context and apply the result |

---

### Document Properties Dialog
**Path**: `gui/layout/document_dialog.py` - 454 lines
**Purpose**: Tabbed editor for document metadata, page settings, theme colors/variables, and custom metadata rows.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `PAGE_SIZES` | 23 | constant | Named page presets in pixels at 300 DPI (A4/Letter/Legal/A5/A3/Tabloid/Square/Custom) |

#### Classes

##### `DocumentPropertiesDialog` (QDialog) — line 37

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 40 | constructor | None | No | Bind a `DocumentSpec`, build UI, load current properties |
| `init_ui` | 48 | public | None | No | Tab widget (General / Page Settings / Theme / Metadata) + button box |
| `create_general_tab` | 74 | public | QWidget | No | Title, author, content kind, description |
| `create_page_settings_tab` | 111 | public | QWidget | No | Preset combo, custom width/height, DPI, margins |
| `create_theme_tab` | 177 | public | QWidget | No | Theme color pickers and template variable rows |
| `create_metadata_tab` | 243 | public | QWidget | No | Free-form key/value metadata table |
| `load_properties` | 283 | public | None | No | Populate every tab from the document |
| `save_properties` | 332 | public | None | No | Write all edited fields back to the document |
| `get_selected_page_size` | 384 | public | tuple | No | Pixel size for the selected preset (or the custom spinboxes) |
| `on_page_size_changed` | 393 | public | None | No | Enable custom spinboxes only for "Custom"; otherwise apply the preset |
| `pick_theme_color` | 406 | public | None | No | Color dialog for one theme slot |
| `set_button_color` | 416 | public | None | No | Paint a swatch button with a hex color |
| `get_button_color` | 421 | public | str | No | Read the hex color back off a swatch button |
| `add_variable_row` | 425 | public | None | No | Add a template-variable row |
| `remove_variable_row` | 432 | public | None | No | Remove the selected variable row |
| `add_metadata_row` | 438 | public | None | No | Add a metadata key/value row |
| `remove_metadata_row` | 445 | public | None | No | Remove the selected metadata row |
| `accept` | 451 | public | None | No | Save properties, then accept |

---

### Export Dialog
**Path**: `gui/layout/export_dialog.py` - 428 lines
**Purpose**: Threaded export of a layout document to PNG, PDF, or JSON with DPI presets, page ranges, and progress reporting.
**Language**: Python

#### Classes

##### `ExportWorker` (QThread) — line 22
Signals: `progress(int, str)`, `finished(bool, str)`, `error(str)`.

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 29 | constructor | None | No | Capture document, format, output path, DPI, optional `(start, end)` page range |
| `run` | 39 | public | None | No | Resolve the page subset and dispatch to the format-specific exporter |
| `_export_png` | 70 | private | None | No | Write one PNG per page, emitting progress |
| `_export_pdf` | 87 | private | None | No | Write a multi-page PDF |
| `_export_json` | 97 | private | None | No | Serialize the document spec to JSON |

##### `ExportDialog` (QDialog) — line 115

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 118 | constructor | None | No | Bind document + config, build UI, load settings |
| `init_ui` | 130 | public | None | No | Format radios, DPI spinner, preset combo, page-range group, output picker, progress bar |
| `_on_range_toggled` | 258 | private | None | No | Enable/disable the start/end page spinners |
| `_on_preset_changed` | 263 | private | None | No | Apply a preset (Web PNG 72 / Draft PDF 150 / High-quality PDF 300 / Ultra PNG 600) |
| `load_settings` | 298 | public | None | No | Settings hook (DPI is loaded during `init_ui`) |
| `save_settings` | 303 | public | None | No | Persist the DPI via `config.set_layout_export_dpi` |
| `start_export` | 307 | public | None | No | Validate inputs, refuse re-entry, launch `ExportWorker` |
| `_on_progress` | 375 | private | None | No | Update the progress bar and status text |
| `_on_finished` | 380 | private | None | No | Report success/failure and re-enable the UI |
| `_on_error` | 394 | private | None | No | Show and log an export error |
| `closeEvent` | 404 | public | None | No | Stop a running worker and save settings before closing |

---

### Template Selector
**Path**: `gui/layout/template_selector.py` - 340 lines
**Purpose**: Browsable gallery of layout templates — thumbnail cards, search/category filters, and selection signalling.
**Language**: Python

#### Classes

##### `TemplateCard` (QWidget) — line 20
One template tile (thumbnail + name/category). Signal: `clicked(str)` carrying the template path.

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 25 | constructor | None | No | Store metadata + thumbnail path, build the card |
| `init_ui` | 33 | public | None | No | 128×128 thumbnail, title, category/description labels |
| `update_style` | 89 | public | None | No | Restyle the border for selected vs. normal state |
| `set_selected` | 115 | public | None | No | Toggle the selected flag and restyle |
| `mousePressEvent` | 120 | public | None | No | Emit `clicked` with the template path |

##### `TemplateSelectorWidget` (QWidget) — line 127
Signal: `templateSelected(path, metadata)`.

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 132 | constructor | None | No | Bind a `TemplateManager`, build UI, load templates |
| `init_ui` | 144 | public | None | No | Search box, category combo, grid/list view buttons, scrollable card grid |
| `set_template_manager` | 215 | public | None | No | Swap the manager and reload |
| `refresh_templates` | 220 | public | None | No | Re-scan templates and repopulate the category filter |
| `filter_templates` | 239 | public | None | No | Apply the search text + category filter |
| `display_templates` | 259 | public | None | No | Rebuild the card grid for a template list |
| `on_template_clicked` | 301 | public | None | No | Move the selection highlight and emit `templateSelected` with metadata |
| `set_view_mode` | 328 | public | None | No | Grid vs. list toggle (list view reserved for later) |
| `get_selected_template` | 338 | public | Optional[str] | No | Path of the currently selected template |

---

### Image History Dialog
**Path**: `gui/layout/image_history_dialog.py` - 317 lines
**Purpose**: Browse previously generated images (with their `.json` metadata sidecars) and pick one for a layout image block/region.
**Language**: Python

#### Classes

##### `ImageCard` (QFrame) — line 24
Fixed-size thumbnail card with formatted metadata. Signal: `clicked(str)` carrying the image path.

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 30 | constructor | None | No | Load and scale the thumbnail, lay out labels |
| `_format_metadata` | 73 | private | str | No | Condense the sidecar (prompt, model, date) for display |
| `mousePressEvent` | 98 | public | None | No | Emit `clicked` |
| `set_selected` | 103 | public | None | No | Set the selected flag and restyle |
| `_update_style` | 108 | private | None | No | Selected vs. normal frame styling |

##### `ImageHistoryDialog` (QDialog) — line 130

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 135 | constructor | None | No | Bind config + logger, build UI, load images |
| `_init_ui` | 148 | public | None | No | Search/filter row, scrollable card grid, status label, buttons |
| `_load_images` | 208 | private | None | No | Glob PNG/JPG from the output directory, sort newest-first, attach metadata; errors are logged and shown |
| `_load_metadata` | 244 | private | dict | No | Read the image's JSON sidecar (empty dict when absent/invalid) |
| `_display_images` | 264 | private | None | No | Rebuild the card grid |
| `_filter_images` | 282 | private | None | No | Filter by search text over prompt/metadata |
| `_on_image_selected` | 305 | private | None | No | Track the selection and enable OK |
| `get_selected_image` | 315 | public | Optional[str] | No | Path of the chosen image |

---

### ContentInspector
**Path**: `gui/layout/content_inspector.py` - 255 lines
**Purpose**: Edit the selected region's content — image reference (import / from history), AI image prompt (apply / suggest / send to Image tab), or text plus font family and size.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_DEFAULT_TEXT_PX` | 12 | constant | 48 px fallback text size, mirroring `qt_renderer` |

#### Classes

##### `ContentInspector` (QWidget) — line 15
Display-only: it emits `regionContentChanged`, `regionTextStyleChanged`, `regionPromptChanged`, `regionPromptSuggestRequested`, and `regionSendToImageRequested`; `LayoutTab` owns every mutation. A `QStackedWidget` switches between empty / image / text pages.

###### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 34 | constructor | None | No | Build, kick off background font loading, start with no region |
| `_build` | 43 | private | None | No | Stacked empty/image/text editors, prompt box, font combo + size spinner |
| `_start_font_load` | 132 | private | None | No | Use the cached family list or start a `FontLoader` thread (kept referenced) |
| `_populate_fonts` | 142 | private | None | No | Fill the font combo once families arrive |
| `set_region` | 153 | public | None | No | Show the editor for a region; the *resolved* `TextStyle` is passed in so "Apply text" can't silently shrink the text |
| `_load_text_style` | 181 | private | None | No | Push family/size into the controls without emitting change signals |
| `_on_import_image` | 192 | private | None | No | File dialog → set the image reference |
| `_on_from_history` | 201 | private | None | No | `ImageHistoryDialog` → set the image reference |
| `_set_image_ref` | 211 | private | None | No | Update the label and emit `regionContentChanged` |
| `_on_apply_prompt` | 218 | private | None | No | Emit `regionPromptChanged` with the trimmed prompt |
| `_on_suggest_prompt` | 223 | private | None | No | Emit a suggest request; the current text doubles as a steering hint |
| `_on_send_to_image` | 230 | private | None | No | Emit `regionSendToImageRequested` |
| `set_prompt_text` | 236 | public | None | No | Push an AI-suggested prompt into the box, only if that region is still shown |
| `set_suggest_enabled` | 243 | public | None | No | Disable Suggest while a suggestion is in flight |
| `_on_apply_text` | 248 | private | None | No | Emit the style change first (so a font-only edit still re-renders), then the content |

---

### GeometryEditor
**Path**: `gui/layout/geometry_editor.py` - 209 lines
**Purpose**: Manual region-geometry editing — draggable vertex/control handles layered over the canvas scene, with validation and revert on commit.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_HANDLE_R` | 18 | constant | Handle radius in scene (page-pixel) units |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `edit_points_for_region` | 33 | public | List[_EditPoint] | No | Ordered editable points for a `path`/`polygon` region (rect → empty list) |
| `_polygon_point` | 54 | private | _EditPoint | No | Editable point for polygon vertex `i` (its nested `apply` closure at line 57 writes the new coordinate back) |
| `_seg_point` | 63 | private | _EditPoint | No | Editable point for path-segment point `j` (nested `apply` closure at line 66) |

#### Classes

##### `_EditPoint` — line 21
`__slots__`-based record of one draggable model point: `x`, `y`, `is_control`, and an `apply(x, y)` callback that writes the new position into the model.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 25 | constructor | None | No | Store position, control-point flag, and writer callback |

##### `_HandleItem` (QGraphicsEllipseItem) — line 72
A movable scene handle bound to one edit-point index.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 75 | constructor | None | No | Set movable + geometry-change flags for its index |
| `mousePressEvent` | 82 | public | None | No | Start an edit (`GeometryEditor.begin_edit`) |
| `itemChange` | 86 | public | value | No | Live-apply the dragged position to the model |
| `mouseReleaseEvent` | 91 | public | None | No | Commit the edit |

##### `GeometryEditor` — line 96
Handles are regenerated from the model after every scene rebuild (see `LayoutTab._refresh`) rather than preserved.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 99 | constructor | None | No | Bind the canvas and owning `LayoutTab`; no active region |
| `active_region_id` | 108 | public | Optional[str] | No | Region currently in shape-edit mode |
| `edit_points` | 111 | public | List[_EditPoint] | No | The current editable point list |
| `set_edit_region` | 114 | public | None | No | Enter/leave editing for a region and rebuild handles |
| `rebuild_handles` | 118 | public | None | No | Recreate handle items from the model over the region's shape item |
| `_find_shape_item` | 146 | private | Optional[QGraphicsItem] | No | Locate the scene item drawing this region |
| `_clear` | 152 | private | None | No | Remove all handle items from the scene |
| `begin_edit` | 161 | public | None | No | Snapshot pre-edit geometry (for revert) and suspend refreshes |
| `move_handle` | 174 | public | None | No | Write the handle's new position to the model and live-update the painter path |
| `commit` | 183 | public | None | No | Validate segments (revert on failure), recompute the bbox, snapshot and refresh |

---

### DesignerPanel
**Path**: `gui/layout/designer_panel.py` - 200 lines
**Purpose**: The AI layout designer — content-kind/provider/model selection, description-and-iterate prompt box, status console, and the off-thread LLM worker.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `CONTENT_KINDS` | 15 | constant | children, comic, comic_strip, magazine, newspaper, scientific, custom |

#### Classes

##### `DesignerWorker` (QThread) — line 18
Signals: `progress(str)`, `proposed(object)` (a `DesignerResult`), `failed(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 23 | constructor | None | No | Capture messages, page pixel size, and the completion callable |
| `run` | 29 | public | None | No | Call `designer.run_design`; failures are logged with traceback and surfaced |

##### `DesignerPanel` (QWidget) — line 39
Signal: `layoutProposed(object)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 42 | constructor | None | No | Store config, build UI, populate providers |
| `_build` | 48 | private | None | No | Kind/provider/model combos, prompt editor, Design button, collapsible `DialogStatusConsole` |
| `_on_toggle_console` | 94 | private | None | No | Show/hide the status console |
| `_populate_providers` | 99 | private | None | No | Fill the provider combo and restore the saved selection |
| `_on_provider_changed` | 114 | private | None | No | Repopulate models for the provider and restore the saved model |
| `_cfg_get` | 129 | private | Any | No | Call an optional config getter, tolerating minimal test fakes |
| `_cfg_set` | 134 | private | None | No | Call an optional config setter then `save()` if present |
| `_save_kind` | 142 | private | None | No | Persist the content kind |
| `_save_provider` | 145 | private | None | No | Persist the LLM provider |
| `_save_model` | 148 | private | None | No | Persist the model, ignoring the transient empty state during repopulation |
| `content_kind` | 152 | public | str | No | Currently selected content kind |
| `start_design` | 155 | public | None | No | Build messages, log the full prompt, and run the worker — synchronously when a `completion_fn` is injected (tests), else `start()`; refuses to clobber a running QThread |
| `_on_proposed` | 183 | private | None | No | Log the raw LLM response, region/overlay/question counts, and emit `layoutProposed` |
| `_on_failed` | 196 | private | None | No | Force the console open and log the error |

---

### OverlayInspector
**Path**: `gui/layout/overlay_inspector.py` - 193 lines
**Purpose**: List and author comic text overlays (speech, thought, caption, SFX) — add/delete, rotation, edit toggle, text-on-a-curve, and outline width/color.
**Language**: Python

#### Classes

##### `OverlayInspector` (QWidget) — line 17
Emits intent signals only (`addRequested`, `deleteRequested`, `rotationChanged`, `overlaySelected`, `editToggled`, `curveToggled`, `outlineChanged`); `LayoutTab` owns the model — the same split as the Geometry/Content inspectors.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 26 | constructor | None | No | Build the panel with nothing selected |
| `_build` | 32 | private | None | No | Overlay list, add-kind buttons, delete, rotation spinner, edit/curve checkboxes, outline width + color |
| `set_page` | 101 | public | None | No | Repopulate the list from a `PageSpec`, caching each row's rotation/kind/curve/outline state |
| `set_selected` | 119 | public | None | No | Sync every control to the selected row; curve/outline controls only enable for caption/SFX overlays that are curved |
| `_selected_overlay_id` | 163 | private | Optional[str] | No | Overlay id of the current row |
| `_on_row_changed` | 167 | private | None | No | Emit `overlaySelected` for the new row |
| `_on_delete` | 173 | private | None | No | Emit `deleteRequested` |
| `_on_rotation` | 177 | private | None | No | Emit `rotationChanged` |
| `_on_edit` | 181 | private | None | No | Emit `editToggled` |
| `_on_curve` | 185 | private | None | No | Emit `curveToggled` |
| `_on_outline` | 189 | private | None | No | Emit `outlineChanged` with width + hex color |

---

### OverlayEditor
**Path**: `gui/layout/overlay_editor.py` - 160 lines
**Purpose**: Drag handles for overlays layered on the canvas — body anchor, balloon tail (which snaps to the nearest region center), and the three text-path arc points.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_HANDLE_R` | 15 | constant | Handle radius in scene units |
| `_SNAP_RADIUS` | 16 | constant | 40 px — tail snaps to a region center within this distance |
| `_HANDLE_COLORS` | 18 | constant | Per-handle-kind colors (body, tail, tp0/tp1/tpc) |

#### Classes

##### `_OvHandle` (QGraphicsEllipseItem) — line 24
A draggable overlay handle identified by `kind`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 27 | constructor | None | No | Set movable + geometry-change flags for its kind |
| `mousePressEvent` | 34 | public | None | No | `OverlayEditor.begin_edit` |
| `itemChange` | 38 | public | value | No | Live-apply the drag to the model |
| `mouseReleaseEvent` | 43 | public | None | No | Commit |

##### `OverlayEditor` — line 48
Mirrors `GeometryEditor`: handles are regenerated after each scene rebuild, move-only.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 51 | constructor | None | No | Bind the canvas and owning `LayoutTab` |
| `active_overlay_id` | 58 | public | Optional[str] | No | Overlay currently in edit mode |
| `set_edit_overlay` | 61 | public | None | No | Enter/leave editing and rebuild handles |
| `_find_overlay` | 65 | private | Optional[Overlay] | No | Look up the overlay on the current page |
| `_clear` | 74 | private | None | No | Remove handle items from the scene |
| `rebuild_handles` | 81 | public | None | No | Create body/tail (and text-path) handles from the model |
| `_add_handle` | 98 | private | None | No | Instantiate one colored handle at a scene position |
| `begin_edit` | 109 | public | None | No | Snapshot anchor, tail target, and a deep copy of the text path; suspend refreshes |
| `move_handle` | 120 | public | None | No | Apply the drag to anchor / tail / arc point |
| `commit` | 136 | public | None | No | Snap the tail to the nearest region center within `_SNAP_RADIUS`, revert an invalid text path, then snapshot and refresh |

---

### PageSetupWidget
**Path**: `gui/layout/page_setup_widget.py` - 144 lines
**Purpose**: Page-setup toolbar — size presets plus freeform entry, unit, DPI, and portrait/landscape orientation.
**Language**: Python

#### Classes

##### `PageSetupWidget` (QWidget) — line 11
Signal: `pageSizeChanged(PageSize)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 14 | constructor | None | No | Read the export DPI from config, build, load presets, emit the initial size |
| `_build` | 23 | private | None | No | Editable size combo, unit combo, DPI spinner, portrait/landscape buttons |
| `_reload_presets` | 56 | private | None | No | Refill the combo from `core.layout.page_sizes` (built-in + saved custom) |
| `_current_preset` | 64 | private | dict | No | The preset dict behind the current combo row |
| `page_size` | 70 | public | PageSize | No | Current size honoring unit, DPI and orientation |
| `set_page_size` | 74 | public | None | No | Reflect an externally loaded `PageSize` in every control |
| `add_custom_from_text` | 99 | public | bool | No | Parse freeform text (e.g. `8.5x11`), save it as a custom preset, select and emit it |
| `_on_preset_selected` | 116 | private | None | No | Emit the current size |
| `_on_freeform_entered` | 119 | private | None | No | Return-key in the combo → `add_custom_from_text` |
| `_on_dpi_changed` | 122 | private | None | No | Emit the current size |
| `_on_portrait` | 125 | private | None | No | Switch to portrait and emit |
| `_on_landscape` | 130 | private | None | No | Switch to landscape and emit |
| `_sync_orientation_buttons` | 135 | private | None | No | Reflect `_orientation` in the mutually exclusive buttons without re-emitting |
| `_emit_current` | 143 | private | None | No | Emit `pageSizeChanged` |

---

### GeometryInspector
**Path**: `gui/layout/geometry_inspector.py` - 137 lines
**Purpose**: Per-region controls — bleed, borderless, z-order, edit-shape, delete, knife (split), and merge.
**Language**: Python

#### Classes

##### `GeometryInspector` (QWidget) — line 17
Signals: `bleedToggled`, `borderlessToggled`, `zChanged`, `editShapeToggled`, `deleteRequested`, `knifeToggled`, `mergeToggled`. Intent-only; `LayoutTab` mutates the model.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 26 | constructor | None | No | Build with no region selected |
| `_build` | 32 | private | None | No | Header label, bleed/borderless checkboxes, z spinner, edit-shape/knife/merge toggles, delete |
| `set_region` | 78 | public | None | No | Populate (and enable/disable) all controls for a region without re-emitting |
| `_on_bleed` | 111 | private | None | No | Emit `bleedToggled` |
| `_on_borderless` | 115 | private | None | No | Emit `borderlessToggled` |
| `_on_z` | 119 | private | None | No | Emit `zChanged` |
| `_on_edit_shape` | 123 | private | None | No | Emit `editShapeToggled` |
| `_on_delete` | 127 | private | None | No | Emit `deleteRequested` |
| `_on_knife` | 131 | private | None | No | Emit `knifeToggled` |
| `_on_merge` | 135 | private | None | No | Emit `mergeToggled` |

---

### CanvasWidget
**Path**: `gui/layout/canvas_widget.py` - 103 lines
**Purpose**: The live editor canvas — a `QGraphicsView` over a scene built by `core.layout.qt_renderer`, with region selection and the knife/merge click tools.
**Language**: Python

#### Classes

##### `CanvasWidget` (QGraphicsView) — line 12
Signals: `regionSelected(str)`, `knifeLine(x1, y1, x2, y2)`, `mergeTarget(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 17 | constructor | None | No | Antialiasing, rubber-band drag, empty scene, `none` tool mode |
| `load_page` | 27 | public | None | No | Rebuild the scene for a page; disconnects and `deleteLater()`s the old scene so replaced scenes don't accumulate as children |
| `selected_region_id` | 43 | public | Optional[str] | No | Region id of the selected scene item |
| `set_tool_mode` | 50 | public | None | No | Switch between `none`, `knife`, and `merge` |
| `tool_mode` | 57 | public | str | No | Current tool mode |
| `_register_knife_point` | 60 | private | None | No | Collect the two knife clicks and emit `knifeLine` |
| `_region_id_at` | 69 | private | Optional[str] | No | Hit-test a scene point to a region id |
| `mousePressEvent` | 76 | public | None | No | Route the click to the knife/merge tool or normal selection |
| `resizeEvent` | 95 | public | None | No | Refit the page in the view |
| `_on_selection_changed` | 101 | private | None | No | Emit `regionSelected` |

---

### StylePanel
**Path**: `gui/layout/style_panel.py` - 95 lines
**Purpose**: Project style editor — per-role font family, size, and color for the document's `ProjectStyle`.
**Language**: Python

#### Classes

##### `StylePanel` (QWidget) — line 10
Signal: `styleChanged(ProjectStyle)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 13 | constructor | None | No | Hold config, start from a default `ProjectStyle`, build the form |
| `_build` | 19 | private | None | No | Role combo plus family / size / color fields |
| `set_style` | 35 | public | None | No | Adopt a `ProjectStyle` and repopulate the role list |
| `style` | 49 | public | ProjectStyle | No | The current style object |
| `_load_role` | 52 | private | None | No | Load one role's `TextStyle` into the fields |
| `_on_role_selected` | 64 | private | None | No | Switch the edited role |
| `_cfg_get` | 70 | private | Any | No | Optional config getter, tolerant of test fakes |
| `_cfg_set` | 74 | private | None | No | Optional config setter + `save()` |
| `_on_field_changed` | 82 | private | None | No | Write edited family/size/color back into the role and emit `styleChanged` |

---

### FontLoader
**Path**: `gui/layout/font_loader.py` - 48 lines
**Purpose**: Enumerate installed system font families off the GUI thread (first access can stall Qt) and cache them process-wide.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_CACHE` | 16 | constant | Process-wide cached family list (`None` until loaded) |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `cached_families` | 19 | public | Optional[List[str]] | No | The cached family list, or `None` if it hasn't loaded yet |
| `_enumerate` | 24 | private | List[str] | No | `QFontDatabase.families()` filtered of `.`/`@` names, deduped, case-insensitively sorted |

#### Classes

##### `FontLoader` (QThread) — line 30
Emits `loaded(list_of_family_names)` exactly once; on failure it logs and emits an empty list — font enumeration must never crash or hang the UI.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `run` | 39 | public | None | No | Enumerate, populate `_CACHE`, emit `loaded` |

---

### HistoryWindow
**Path**: `gui/layout/history_window.py` - 47 lines
**Purpose**: Browsable iteration history for the layout designer, with restore-to-snapshot.
**Language**: Python

#### Classes

##### `HistoryWindow` (QDialog) — line 8
Signal: `restoreRequested(snapshot_id)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 11 | constructor | None | No | Title/size, build, populate from the `History` |
| `_build` | 19 | private | None | No | Iteration list plus Restore/Close buttons |
| `set_history` | 34 | public | None | No | Repopulate the list (newest last) from a `History` |
| `_on_restore` | 43 | private | None | No | Emit `restoreRequested` for the selected snapshot and accept |

---

### PromptSuggestWorker
**Path**: `gui/layout/prompt_worker.py` - 34 lines
**Purpose**: Off-thread per-region AI image-prompt suggestion; mirrors `DesignerWorker` (injected `completion_fn` → synchronous `run()` in tests, `start()` in production).
**Language**: Python

#### Classes

##### `PromptSuggestWorker` (QThread) — line 17
Signals: `suggested(region_id, prompt)`, `failed(region_id, error)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 21 | constructor | None | No | Capture region id, messages, and completion callable |
| `run` | 28 | public | None | No | `prompt_helper.run_prompt_help`; failures are logged with traceback and emitted |

---

### Layout package init
**Path**: `gui/layout/__init__.py` - 5 lines
**Purpose**: Layout/Books GUI package; re-exports `LayoutTab` (`__all__ = ['LayoutTab']`).
**Language**: Python

---

### Style Manager Dialog
**Path**: `gui/styles/style_manager_dialog.py` - 550 lines
**Purpose**: Create, edit, analyze, and import/export custom styles — style list, reference-image grid with drag-and-drop, exemplar checkboxes, vision-LLM analysis, and a status console.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_SPLITTER_KEY` | 27 | constant | QSettings key for the vertical splitter state |
| `_ORPHAN_WORKERS` | 31 | constant | Set holding workers orphaned at dialog close until `run()` returns, so Python GC can't destroy a live QThread |
| `_IMAGE_EXTS` | 33 | constant | Accepted reference-image extensions |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `_image_paths_from_mime` | 36 | private | List[Path] | No | Local image files in a drag payload, order preserved |

#### Classes

##### `_RefsListWidget` (QListWidget) — line 50
Reference-image grid that accepts dropped image files.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 54 | constructor | None | No | Enable drops |
| `dragEnterEvent` | 58 | public | None | No | Accept payloads containing local images |
| `dragMoveEvent` | 64 | public | None | No | Same acceptance check while dragging |
| `dropEvent` | 70 | public | None | No | Emit the dropped image paths for the dialog to add |

##### `StyleAnalysisWorker` (QThread) — line 79
Runs vision-LLM style analysis off the GUI thread. Signals include `progress`, `finished_ok`, and `failed`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 85 | constructor | None | No | Capture the analysis service and exemplar paths |
| `run` | 90 | public | None | No | Analyze the images and emit the descriptor dict, or the failure message |

##### `StyleManagerDialog` (DialogCleanupMixin, QDialog, OperationGuardMixin) — line 99
Left: style list. Right: details + refs grid + analyze. Bottom: console.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 102 | constructor | None | No | Bind config/`StyleStore`, build UI, restore geometry then provider (repopulates models) then model, arm the operation guard, load styles |
| `_build_ui` | 130 | private | None | No | Vertical `standard_splitter`, style list + New/Duplicate/Delete/Import/Export, detail form, exemplar grid, vision-LLM combos, `DialogStatusConsole` |
| `_load_styles` | 251 | private | None | No | Repopulate the list with 48 px exemplar icons, honoring `is_safe_rel`, restoring a selection |
| `_current_style` | 269 | private | Optional[Style] | No | The `Style` behind the selected row |
| `_on_selected` | 275 | private | None | No | Load a style into the form; drops any pending analysis result so it can't be applied to a different style |
| `_collect_exemplars` | 307 | private | List[str] | No | Relative paths of the checked reference images |
| `_save_current` | 315 | private | None | No | Write form fields + exemplars (auto-selecting/capping at `EXEMPLAR_DEFAULT_CAP`) and any pending descriptor, then save and reload |
| `_on_new` | 348 | private | None | No | Prompt for a name and create a style |
| `_on_duplicate` | 356 | private | None | No | Deep-copy the selected style under a new id/name |
| `_on_delete` | 382 | private | None | No | Confirm and delete the selected style |
| `_on_import` | 393 | private | None | No | Import a style package from disk |
| `_on_export` | 405 | private | None | No | Export the selected style to disk |
| `_on_add_files` | 418 | private | None | No | File dialog → add reference images |
| `_on_add_folder` | 424 | private | None | No | Add every image in a chosen folder |
| `_add_paths` | 431 | private | None | No | Copy paths into the style store, save, and refresh the grid |
| `_on_remove_ref` | 440 | private | None | No | Remove the selected reference image |
| `_on_llm_provider_changed` | 451 | private | None | No | Repopulate the vision-model combo via `get_provider_models` |
| `_on_analyze` | 459 | private | None | No | Clear stale pending results, resolve exemplars, and launch `StyleAnalysisWorker` |
| `_on_analysis_done` | 503 | private | None | No | Show the descriptor JSON and hold it pending until Save |
| `_on_analysis_failed` | 517 | private | None | No | Log and show the analysis failure |
| `on_dialog_close` | 525 | public | None | No | Interrupt/await the worker (orphaning it into `_ORPHAN_WORKERS` if still running), end the operation guard so the app-level input blocker can't outlive the dialog, then persist splitter/geometry/provider/model |

---

### StylePickerWidget
**Path**: `gui/styles/style_picker.py` - 105 lines
**Purpose**: Compact reusable "Style: [None ▾] [Manage…] ☐ Smart merge" row, dropped into the Generate tab, video workspace, and layout fill; selection and smart-merge state persist per surface.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `_PICKERS` | 21 | constant | `WeakSet` of every live picker across all surfaces, so closing the Style Manager refreshes them all (issue #37) |

#### Classes

##### `StylePickerWidget` (QWidget) — line 24
Signal: `style_changed(str)` — style id, or `""` for None.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 27 | constructor | None | No | Build the row, restore the per-surface smart-merge state, register in `_PICKERS` |
| `set_store` | 59 | public | None | No | Swap the backing `StyleStore` |
| `refresh` | 62 | public | None | No | Reload styles with description tooltips, keeping the current selection when it still exists |
| `current_style` | 79 | public | Optional[Style] | No | The selected `Style` (None when "None") |
| `smart_merge_enabled` | 83 | public | bool | No | Whether LLM smart-merge is checked |
| `_on_changed` | 87 | private | None | No | Persist `style_selected_<surface>` and emit `style_changed` |
| `_on_smart_toggled` | 93 | private | None | No | Persist `style_smart_<surface>` |
| `_open_manager` | 97 | private | None | No | Open `StyleManagerDialog`, then refresh every registered picker (skipping already-deleted C++ widgets) |

---

### Styles package init
**Path**: `gui/styles/__init__.py` - 1 lines
**Purpose**: Package marker for the Custom Styles GUI.
**Language**: Python

---

### DialogManager
**Path**: `gui/common/dialog_manager.py` - 225 lines
**Purpose**: Centralized message dialogs so every user-facing error/warning/info is also logged (repo rule: all errors must be logged).
**Language**: Python

#### Classes

##### `DialogManager` (QObject) — line 12
Signal: `dialog_shown(type, title, message)` — connected to its own logger so every dialog is recorded.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 21 | constructor | None | No | Store the default parent widget and wire `dialog_shown` → `_log_dialog` |
| `_log_dialog` | 29 | private | None | No | Log `[DIALOG] timestamp | type | title | message` |
| `show_error` | 34 | public | int | No | `QMessageBox.critical` + logging |
| `show_warning` | 56 | public | int | No | `QMessageBox.warning` + logging |
| `show_info` | 78 | public | int | No | `QMessageBox.information` + logging |
| `show_question` | 100 | public | int | No | Yes/No (configurable buttons) question dialog + logging |
| `show_generation_error` | 145 | public | int | No | "Generation Failed" dialog for a named operation, with an extra raw-error log line |
| `show_success` | 173 | public | int | No | Success information dialog + logging |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `get_dialog_manager` | 200 | public | DialogManager | No | Lazily create and return the process-wide manager |
| `set_dialog_manager_parent` | 216 | public | None | No | Re-point the global manager at a new parent widget |

---

### Dialog Conventions
**Path**: `gui/common/dialog_conventions.py` - 141 lines
**Purpose**: The shared dialog standards from `Plans/DialogUX-TLC-Plan.md` — visible non-collapsible splitters persisted under named keys, Ctrl+Return/Ctrl+Enter primary actions, exactly one default button, and cleanup on every exit path.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `standard_splitter` | 22 | public | QSplitter | No | Splitter with the canonical style and non-collapsible panes |
| `persist_splitter` | 30 | public | None | No | Save splitter state under an explicit named key (never `findChildren(QSplitter)[0]`) |
| `restore_splitter` | 35 | public | bool | No | Restore state; `False` means the caller should apply its hardcoded `setSizes()` default |
| `bind_primary_action` | 77 | public | PrimaryAction | No | Bind a widget's primary action to both Ctrl+Return and Ctrl+Enter |
| `set_default_button` | 82 | public | None | No | Make exactly one button the dialog default (clearing others) so utility buttons never steal Enter |

#### Classes

##### `PrimaryAction` (QObject) — line 47
Ctrl+Return and keypad Ctrl+Enter bound to the same slot, always created and retargeted together (Qt reports keypad Enter as `Qt.Key_Enter`, which `"Ctrl+Return"` does not match).

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 54 | constructor | None | No | Create both `QShortcut`s in the given context |
| `_activated` | 64 | private | None | No | Invoke the bound slot |
| `retarget` | 68 | public | None | No | Point both shortcuts at a new slot |
| `set_enabled` | 72 | public | None | No | Enable/disable both shortcuts together |

##### `DialogCleanupMixin` — line 103
Runs cleanup on every exit path exactly once per showing, because `QDialog.accept()/reject()` never fire `closeEvent`. Documented caveat: a subclass that guards closes must put the guard in `reject()`/`done()` or fully override `closeEvent`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `on_dialog_close` | 122 | public | None | No | Override hook: worker shutdown, QSettings/geometry/splitter saves |
| `_run_dialog_cleanup` | 125 | private | None | No | Idempotent guard around `on_dialog_close` |
| `showEvent` | 131 | public | None | No | Reset the once-per-showing flag |
| `done` | 135 | public | None | No | Run cleanup before `QDialog.done` (OK/Cancel/Escape) |
| `closeEvent` | 139 | public | None | No | Run cleanup before the close event |

---

### Markdown Table Helpers
**Path**: `gui/common/markdown_tables.py` - 53 lines
**Purpose**: Parse size-preset Markdown tables; extracted from the retired `gui/social_sizes_dialog.py` so the tree-based size picker and future consumers share one implementation.
**Language**: Python

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `parse_markdown_table` | 12 | public | Tuple[List[str], List[List[str]]] | No | Parse the first GFM table in the text into headers + rows, padding/trimming rows to the header width |
| `extract_resolution_px` | 45 | public | Optional[str] | No | Pull the first `WxH` pair out of text like `1080 × 1920` or `512x512` |

---

### Splitter Style
**Path**: `gui/common/splitter_style.py` - 44 lines
**Purpose**: Single source of truth for `QSplitter` styling (Maestro brand colors from `gui/theme.py`) — handles must be visible at rest, not only on hover.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `SPLITTER_STYLESHEET` | 16 | constant | Gradient handle body with a bright center grip line, plus hover state; size comes from `setHandleWidth()` so callers can widen one splitter without the stylesheet fighting them |
| `DEFAULT_HANDLE_WIDTH` | 38 | constant | 8 px default handle width |

#### Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `apply_splitter_style` | 41 | public | None | No | Set the handle width and apply `SPLITTER_STYLESHEET` |

---

### Common package init
**Path**: `gui/common/__init__.py` - 7 lines
**Purpose**: Re-exports `DialogManager`, `get_dialog_manager`, and `set_dialog_manager_parent`.
**Language**: Python

---

### SuppressStderr
**Path**: `gui/utils/stderr_suppressor.py` - 91 lines
**Purpose**: File-descriptor-level stderr suppression for C libraries (FFmpeg, codecs) that bypass `sys.stderr` — used around `QMediaPlayer` operations. Cross-platform; not thread-safe.
**Language**: Python

#### Classes

##### `SuppressStderr` — line 17
Context manager holding `original_stderr_fd`, `devnull_fd`, and `saved_stderr_fd`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 31 | constructor | None | No | Set the `log_errors` flag and null out the three descriptors |
| `__enter__` | 43 | public | Self | No | `dup` the real stderr, open `os.devnull`, `dup2` it over fd 2 |
| `__exit__` | 62 | public | bool | No | Flush, restore the saved fd, always `_cleanup()`; returns `False` so exceptions propagate |
| `_cleanup` | 77 | private | None | No | Close the saved and devnull descriptors, ignoring `OSError` |

---

## GUI Video — Workspace Widget

The single largest GUI module in the project: the whole editing surface of the Video tab — project header, LLM/image/video provider pickers, lyric/text input, audio + MIDI panel, the 10-column scene/storyboard table, the image/video preview pane with transport controls, and the export/render panel.

### WorkspaceWidget (video project workspace)
**Path**: `gui/video/workspace_widget.py` - 8026 lines
**Purpose**: Main working area of the video project tab — project load/save, storyboard generation via LLM, per-scene image/video/frame operations, Whisper & MIDI lyric extraction, scene timing, and UI-state persistence.
**Language**: Python

#### Module-Level Functions
| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| apply_stored_style_to_scenes | 51 | public | int | No | Applies a stored custom style to every scene prompt (text-only, spec §5); skips `[Section]` markers, idempotent (re-applying never duplicates the suffix), returns the number of scenes styled |

#### Key Imports (selected)
| Import | Line | Type | From |
|--------|------|------|------|
| PySide6 widgets (QWidget, QTableWidget, QSplitter, …) | 18 | external | PySide6.QtWidgets |
| Qt, Signal, Slot, QEvent, QPoint, QTimer, QUrl | 27 | external | PySide6.QtCore |
| QMediaPlayer, QAudioOutput | 29 | external | PySide6.QtMultimedia |
| QVideoWidget | 30 | external | PySide6.QtMultimediaWidgets |
| ConfigManager | 32 | local | core.config |
| VideoProject, Scene | 33 | local | core.video.project |
| ProjectManager | 34 | local | core.video.project_manager |
| StoryboardGenerator | 35 | local | core.video.storyboard |
| VideoConfig | 36 | local | core.video.config |
| SecureKeyStorage | 37 | local | core.security |
| get_default_llm_provider | 38 | local | core.gcloud_utils |
| get_dialog_manager | 39 | local | gui.common.dialog_manager |
| WorkflowWizardWidget | 40 | local | gui.video.wizard_widget |
| FrameButton | 41 | local | gui.video.frame_button |
| VideoButton | 42 | local | gui.video.video_button |
| EndPromptDialog | 43 | local | gui.video.end_prompt_dialog |
| PromptFieldWidget | 44 | local | gui.video.prompt_field_widget |
| ReferenceImagesWidget | 45 | local | gui.video.reference_images_widget |
| EndPromptGenerator, EndPromptContext | 46 | local | core.video.end_prompt_generator |
| get_provider_models, get_all_provider_ids, get_provider_display_name | 47 | local | core.llm_models |
| SuppressStderr | 48 | local | gui.utils.stderr_suppressor |

---

#### Class: ImageHoverPreview
**Line**: 81-130 · **Base**: `QLabel`
Frameless always-on-top tooltip window that shows a full-size image preview while hovering a scene-table cell.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 84 | constructor | None | No | Configures tooltip/frameless/stay-on-top window flags, white bordered stylesheet, scaled contents; starts hidden |
| show_preview | 99 | public | None | No | Loads the pixmap, downscales to max 800×600 with `KeepAspectRatio`, positions near the cursor and flips it when it would run off screen; logs failures |

---

#### Class: ManageStylesDialog
**Line**: 133-284 · **Base**: `QDialog`
Modal editor for the user's custom prompt styles (add / edit / delete), persisted through `ConfigManager`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 136 | constructor | None | No | Builds the list widget + Add/Edit/Delete buttons and dialog button box; loads existing styles |
| _load_styles | 185 | private | None | No | Populates the list widget from the stored custom styles |
| _update_buttons | 192 | private | None | No | Enables/disables Edit and Delete based on the current selection |
| _add_style | 198 | private | None | No | Prompts for a new style string and appends it |
| _edit_style | 220 | private | None | No | Prompts with the selected style pre-filled and replaces it |
| _delete_style | 253 | private | None | No | Confirms, then removes the selected style |
| get_custom_styles | 282 | public | list | No | Returns the edited list of custom styles for the caller to persist |

---

#### Class: WorkspaceWidget
**Line**: 287-8026 · **Base**: `QWidget`
The main video-project workspace. Owns the current `VideoProject`, the `ProjectManager`, the scene table, the media player, and every panel of the Video tab.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| project_changed | 291 | `object` (VideoProject) | Emitted when the active project changes |
| generation_requested | 292 | `str, dict` | Operation name + kwargs, forwarded to the tab's generation controller |
| image_provider_changed | 293 | `str` | Image provider name selected here (syncs with the Image tab) |
| llm_provider_changed | 294 | `str, str` | LLM provider name + model name |

##### Methods — Lifecycle & UI construction
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 296 | constructor | None | No | Sets FFmpeg/Qt logging env vars, stores config + providers, creates `VideoConfig` and `ProjectManager`, initializes hover preview and row-click state, calls `init_ui()`, wires Ctrl+S / Ctrl+Shift+S shortcuts, and defers `auto_load_last_project` via a 100 ms `QTimer` (each step is logged as `WORKSPACE STEP n`) |
| changeEvent | 361 | override | None | No | Hides the hover preview when the window deactivates or loses focus |
| eventFilter | 370 | override | bool | No | Hides the hover preview when a context menu opens (**shadowed** — see Caveats) |
| init_ui | 379 | public | None | No | Assembles the whole workspace: header, provider panel, splitters, input/settings/audio/storyboard/export panels, status bar, and restores saved geometry |
| create_project_header | 833 | public | QWidget | No | Project name field plus New / Open / Save / Save As / Browse controls |
| create_llm_provider_panel | 863 | public | QWidget | No | Global LLM provider + model selectors shown at the top |
| create_input_panel | 893 | public | QWidget | No | Lyrics/text editor with the insert-tag menu |
| create_input_options_panel | 922 | public | QWidget | No | Collapsible input options below the splitter (format, tags, time hints, scene suggestion) |
| create_settings_panel | 1097 | public | QWidget | No | Image/video provider, model, style, aspect, and generation settings |
| create_audio_panel | 1320 | public | QWidget | No | Audio + MIDI selection, Suno package import, Whisper/MIDI lyric extraction |
| create_storyboard_panel | 1529 | public | QWidget | No | Scene table plus the image/video preview pane and transport controls |
| create_export_panel | 1658 | public | QWidget | No | Preview/render controls, output settings, cost label |
| create_status_bar | 1814 | public | QWidget | No | Status label + progress bar |
| closeEvent | 8018 | override | None | No | Persists splitter positions, column widths, and scrollbar positions on close |

##### Methods — Project lifecycle
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| new_project | 1828 | public | None | No | Creates a fresh `VideoProject` and resets the UI |
| auto_load_last_project | 1880 | public | None | No | Reopens the most recent project when the preference is enabled |
| browse_projects | 1926 | public | None | No | Opens the project browser dialog |
| load_project_from_path | 1934 | public | bool | No | Loads a project file, with optional error dialog suppression |
| open_project | 1993 | public | None | No | File dialog → `load_project_from_path` |
| save_project | 2025 | public | None | No | Saves to the current path (Ctrl+S) |
| save_project_as | 2049 | public | None | No | Prompts for a new path and saves (Ctrl+Shift+S) |
| update_recent_projects | 2100 | public | None | No | Pushes the project onto the recent-projects list in config |
| update_project_from_ui | 7442 | public | None | No | Copies name, input text, format, pacing, target duration and provider/model selections from widgets into the project |
| load_project_to_ui | 7520 | public | None | No | Inverse of the above — repopulates every panel, the scene table, and provider combos from the loaded project |
| update_ui_state | 7398 | public | None | No | Enables/disables actions based on whether a project and scenes exist |

##### Methods — Input text, tags & scene suggestion
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| load_input_file | 6596 | public | None | No | Loads lyrics/text from a file into the editor |
| _on_auto_suggest_changed | 2124 | private | None | No | Handles the auto-suggest checkbox |
| _setup_insert_tag_menu | 2131 | private | None | No | Builds the dropdown of insertable tags |
| _insert_tag | 2156 | private | None | No | Inserts the chosen tag at the cursor |
| _insert_scene_marker | 2190 | private | None | No | Legacy compatibility wrapper for scene-marker insertion |
| _delete_scene_marker | 2194 | private | None | No | Deletes the tag (any type, incl. legacy markers) at the cursor |
| _toggle_time_hints | 2235 | private | None | No | Shows/hides inline time hints in the input text |
| _inject_whisper_timestamps | 2252 | private | None | No | Injects time tags derived from Whisper word timestamps |
| _update_whisper_ui_state | 2319 | private | None | No | Enables timestamp-dependent controls when Whisper data exists |
| _suggest_scenes | 2339 | private | None | No | Runs the LLM scene suggester on a background `QThread` (worker defined inline at 2405) |
| _on_scene_suggestion_finished | 2451 | private | None | No | Applies suggested scene tags or reports the worker's exception |

###### Nested class: SceneSuggesterWorker (defined inside `_suggest_scenes`)
**Line**: 2405-2432 · **Base**: `QThread` · Signals: `finished(object)`, `progress(str, str)`

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| __init__ | 2409 | constructor | None | No | Captures suggester, text, provider, model, style, tempo, duration |
| run | 2419 | override | None | No | Calls the suggester off the UI thread and emits the result (or the exception) via `finished` |

##### Methods — Storyboard & prompt generation
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| generate_storyboard | 2485 | public | None | No | Main storyboard entry point: validates input, creates a project if needed, builds a `StoryboardGenerator`, resolves format/MIDI-sync/target duration, generates scenes and repopulates the table |
| get_provider_config | 2984 | public | dict | No | Assembles provider configuration including API keys (via `config.get_api_key()`) |
| _generate_enhanced_storyboard | 3017 | private | None | No | Provider-specific enhanced generation with cross-scene continuity |
| _generate_regular_storyboard | 3295 | private | None | No | Fallback path when enhanced generation is unavailable |
| _enhance_scene_prompts | 3314 | private | None | No | Batch-enhances scene prompts with the selected LLM |
| _generate_video_prompts_for_all_scenes | 3425 | private | None | No | Batch-generates per-scene video (motion) prompts |
| _generate_end_prompts_for_all_scenes | 3522 | private | None | No | Batch-generates end-frame prompts |
| enhance_all_prompts | 6080 | public | None | No | Emits `generation_requested` for prompt enhancement |
| enhance_for_video | 6084 | public | None | No | Emits `generation_requested` for video-prompt enhancement |
| generate_start_end_prompts | 6088 | public | None | No | Generates start/end frame prompts, honoring the per-type checkboxes |
| generate_images | 6130 | public | None | No | Emits `generation_requested` for image generation |
| preview_video | 6134 | public | None | No | Emits `generation_requested` for preview render |
| render_video | 6138 | public | None | No | Emits `generation_requested` for the final render |
| gather_generation_params | 6142 | public | dict | No | Collects every generation parameter from the UI into a kwargs dict |

##### Methods — Scene table
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| _create_top_aligned_widget | 3591 | private | QWidget | No | Wraps a cell widget in a top-aligned container |
| _get_cell_widget | 3602 | private | QWidget | No | Retrieves a cell's real widget, unwrapping the container |
| populate_scene_table | 3614 | public | None | No | Rebuilds the 10-column Veo 3.1 scene table — scene #, start-frame and end-frame `FrameButton`s, reference images, prompts, duration, video button — wiring every per-row signal to the handlers below |
| enhance_single_prompt | 3889 | public | None | No | AI-enhances one scene's prompt |
| revert_single_prompt | 3968 | public | None | No | Restores a scene's prompt to the original source text |
| eventFilter | 3986 | override | bool | No | Scene-table filter: hover image preview and video-button double-click (**shadowed** — see Caveats) |
| _on_column_resized | 4062 | private | None | No | Enforces the minimum width of the Ref Images column (col 3) and saves widths |
| _on_header_double_clicked | 4077 | private | None | No | Auto-resizes a column on header double-click |
| _on_cell_clicked | 4112 | private | None | No | Toggles between the scene's image and video in the preview pane |
| _toggle_row_wrap | 5988 | private | None | No | Toggles word wrap for one row |
| _apply_row_wrap | 5999 | private | None | No | Applies the wrap state to every text field in the row |

##### Methods — Preview pane & media transport
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| _show_image | 4140 | private | None | No | Shows a scene's image in the viewer |
| _show_video | 4173 | private | None | No | Loads a scene's video into the `QMediaPlayer` |
| _toggle_play_pause | 4200 | private | None | No | Play/pause toggle |
| _toggle_mute | 4209 | private | None | No | Mutes/unmutes the audio output |
| _set_position | 4218 | private | None | No | Seeks to the slider position |
| _update_position | 4224 | private | None | No | Syncs the slider to playback position |
| _update_duration | 4231 | private | None | No | Sets slider range once duration is known |
| _update_play_button | 4241 | private | None | No | Updates the button label from playback state |
| _safe_stop_media_player | 4250 | private | None | No | Stops the player defensively if it exists |
| _on_media_status_changed | 4258 | private | None | No | Drives looping and sequential playback on end-of-media |
| _play_next_scene | 4277 | private | None | No | Advances to the next scene that has a video |
| _update_time_label | 4308 | private | None | No | Updates the time label/textbox with millisecond precision |
| ↳ format_time_ms | 4310 | nested | str | No | Formats milliseconds as `MM:SS.mmm` |
| _on_time_textbox_changed | 4328 | private | None | No | Parses a typed timecode and seeks to it |
| eventFilter | 4366 | override | bool | No | Position-slider `ToolTip` handler that shows the precise time under the mouse, then defers to `super()` (this is the definition that wins at runtime) |
| _extract_frame_at_playhead | 4394 | private | None | No | Grabs the current video frame at the playhead and saves it as an image |
| _show_last_frame | 4486 | private | None | No | Shows a scene's last frame in the viewer |
| _log_to_console | 4505 | private | None | No | Appends a leveled message to the status console (and the logger) |

##### Methods — Per-scene generation (image & video)
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| generate_single_scene | 4526 | public | None | No | Requests image generation for one scene |
| generate_video_clip | 4545 | public | None | No | Generates a video clip for one scene via Veo 3 / Veo 3.1 (or the selected video provider) |
| _refine_video_clip | 4659 | private | None | No | Conversationally refines an existing Gemini Omni clip |
| _extend_video_clip | 4726 | private | None | No | Extends an existing clip using Veo 3.1 scene extension |
| _generate_end_frame | 5032 | private | None | No | Generates the end-frame image from `end_prompt` |
| _clear_video | 5196 | private | None | No | Clears a scene's video clip (and derived frames) |
| _select_existing_video | 5269 | private | None | No | Assigns an existing project video file to the scene |
| _play_video_in_panel | 5161 | private | None | No | Plays the scene video in the lower panel |
| _view_video_first_frame | 5084 | private | None | No | Shows the video's first frame in the lower preview panel |
| _load_video_first_frame_in_panel | 5126 | private | None | No | Loads that first frame into the lower image panel |
| _extract_video_first_frame | 5484 | private | None | No | Extracts the first frame from the clip with OpenCV |
| _extract_video_last_frame | 5536 | private | None | No | Extracts the last frame from the clip with OpenCV |
| _extract_all_first_frames | 5608 | private | None | No | Batch-extracts first frames for every scene that has a video but no first frame |

##### Methods — Start / end frames & reference images
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| _view_start_frame | 4812 | private | None | No | Shows the start frame in the lower preview panel |
| _select_start_frame_variant | 4845 | private | None | No | Picks the start frame from generated variants |
| _clear_start_frame | 4874 | private | None | No | Clears the start-frame selection (respected — never auto-refilled from `scene.images[0]`) |
| _load_start_frame_image | 4898 | private | None | No | Loads a start frame from disk |
| _use_last_generated_for_start_frame | 4919 | private | None | No | Uses the newest history image as the start frame |
| _select_start_frame_from_scenes | 4946 | private | None | No | Picks a start frame from any other scene's images |
| _show_end_prompt_llm_dialog | 4988 | private | None | No | Opens the LLM dialog that writes the end prompt |
| _view_end_frame | 5052 | private | None | No | Shows the end frame in the lower preview panel |
| _select_end_frame_variant | 5321 | private | None | No | Picks the end frame from generated variants |
| _clear_end_frame | 5351 | private | None | No | Clears both the end frame and `end_prompt` |
| _load_end_frame_image | 5378 | private | None | No | Loads an end frame from disk |
| _use_last_generated_for_end_frame | 5400 | private | None | No | Uses the newest history image as the end frame |
| _select_end_frame_from_scenes | 5428 | private | None | No | Picks an end frame from any other scene's images |
| _auto_link_end_frame | 5471 | private | None | No | Disabled stub — auto-linking was removed in favor of manual frame selection |
| _select_reference_from_scenes | 5747 | private | None | No | Picks a reference image from any scene's images into a slot |
| _view_reference_image | 5788 | private | None | No | Opens a reference image in the full viewer |
| _load_reference_image | 5812 | private | None | No | Loads a reference image from disk into a slot |
| open_character_reference_wizard | 6036 | public | None | No | Opens the character-reference generation wizard |
| open_reference_library | 6054 | public | None | No | Switches to the reference library management tab |
| _on_references_generated | 6074 | private | None | No | Receives generated reference paths from the wizard |

##### Methods — Per-scene field editing
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| _on_end_prompt_changed | 5629 | private | None | No | Writes edited end-prompt text back to the scene |
| _on_start_prompt_changed | 5640 | private | None | No | Writes edited start-prompt text back to the scene |
| _on_environment_changed | 5649 | private | None | No | Writes the environment/setting field back to the scene |
| _on_reference_image_changed | 5660 | private | None | No | Stores a reference image path in the given slot |
| _on_duration_changed | 5692 | private | None | No | Parses and validates a scene's duration edit |
| _on_lipsync_changed | 5730 | private | None | No | Toggles per-scene lip-sync |
| _on_video_prompt_changed | 5917 | private | None | No | Writes edited video-prompt text back to the scene |
| _show_start_prompt_llm_dialog | 5833 | private | None | No | Opens the LLM dialog for the start prompt |
| _show_video_prompt_llm_dialog | 5931 | private | None | No | Opens the LLM dialog for the video prompt |

##### Methods — Providers, models & cost
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| set_image_provider | 6189 | public | None | No | Sets the image provider from an external source (e.g. the Image tab) |
| @property image_provider | 6207 | property | provider or None | No | Resolves the current combo selection through a name→key map (`gemini`→`google`, `local sd`→`local_sd`, …) and returns the instance from `self.providers` |
| set_llm_provider | 6230 | public | None | No | Sets the LLM provider/model from an external source |
| on_llm_provider_changed | 6248 | public | None | No | Repopulates models and emits `llm_provider_changed` |
| _get_available_llm_providers | 6278 | private | list | No | Lists LLM providers that have a configured key or usable gcloud auth |
| on_img_provider_changed | 6309 | public | None | No | Updates image models/options and emits `image_provider_changed` |
| on_video_provider_changed | 6353 | public | None | No | Swaps the video model list (Veo / Omni) and dependent options |
| on_veo_model_changed | 6391 | public | None | No | Applies model-specific constraints when the Veo model changes |
| _update_cost_estimate | 6412 | private | None | No | Recomputes the estimated cost from the current model and audio settings |
| _update_cost_label | 7418 | private | None | No | Updates the cost label from what has actually been generated |

##### Methods — Styles & panel state
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| _toggle_input_options | 6449 | private | None | No | Collapses/expands the input-options panel |
| _toggle_settings | 6458 | private | None | No | Collapses/expands the generation-settings panel |
| _toggle_music | 6467 | private | None | No | Collapses/expands the music panel |
| _auto_save_settings | 6476 | private | None | No | Writes changed settings into the open project |
| _populate_styles_combo | 6493 | private | None | No | Fills the style combo with built-in plus custom styles |
| _on_style_changed | 6521 | private | None | No | Reacts to style selection (including the custom-entry case) |
| _manage_custom_styles | 6541 | private | None | No | Opens `ManageStylesDialog` and persists the result |
| _get_current_style | 6548 | private | str | No | Returns the effective style (combo selection or free-text input) |
| _set_current_style | 6558 | private | None | No | Restores a style value into the combo/free-text pair |

##### Methods — Audio, MIDI, Whisper & timing
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| browse_audio_file | 6611 | public | None | No | Chooses an audio file, or routes a Suno `.zip` to the importer |
| clear_audio | 6651 | public | None | No | Clears the audio selection |
| browse_midi_file | 6665 | public | None | No | Chooses a MIDI file, or routes a Suno `.zip` to the importer |
| clear_midi | 6710 | public | None | No | Clears the MIDI selection |
| _import_suno_package | 6724 | private | None | No | Unpacks and preprocesses a multi-file Suno zip, optionally importing its audio and MIDI |
| extract_midi_lyrics | 6866 | public | None | No | Extracts lyrics from MIDI, or aligns existing text to MIDI timing |
| extract_audio_lyrics | 6904 | public | None | No | Runs Whisper transcription on a background thread (worker + callbacks defined inline) to produce lyrics with word timestamps |
| _recalculate_scene_timing | 7069 | private | None | No | Recomputes scene start/duration using the LLM sync assistant or MIDI sync |

###### Nested definitions inside `extract_audio_lyrics`
| Symbol | Line | Type | Description |
|--------|------|------|-------------|
| class WhisperWorker | 6953 | QThread | Signals `finished(object)`, `progress(str, float)` |
| WhisperWorker.__init__ | 6957 | constructor | Stores the audio path |
| WhisperWorker.run | 6961 | override | Picks the recommended model size, runs `WhisperAnalyzer.extract_lyrics` with a progress callback, emits the result or the exception |
| on_whisper_progress | 6974 | callback | Updates the timestamp status label with the percentage |
| on_whisper_finished | 6977 | callback | Re-enables the button and applies the transcription (lyrics + word timestamps) to the project |

##### Methods — Workflow wizard
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| _toggle_wizard | 7239 | private | None | No | Shows/hides the wizard panel and collapses/expands its width |
| _on_splitter_moved | 7272 | private | None | No | Clamps the wizard panel to at most 50% of the window width |
| _create_wizard_widget | 7316 | private | WorkflowWizardWidget | No | Builds the wizard for the current project |
| _on_wizard_action | 7337 | private | None | No | Dispatches a wizard step/choice to the matching workspace action |
| _on_wizard_step_skipped | 7384 | private | None | No | Records a skipped wizard step |
| _refresh_wizard | 7391 | private | None | No | Re-renders the wizard after project changes |

##### Methods — UI-state persistence
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| _save_splitter_positions | 7914 | private | None | No | Stores splitter sizes in config |
| _save_column_widths | 7933 | private | None | No | Stores scene-table column widths in config |
| _save_scrollbar_positions | 7944 | private | None | No | Stores scroll offsets in config |
| _restore_splitter_positions | 7959 | private | None | No | Restores splitter sizes from config |
| _restore_column_widths | 7991 | private | None | No | Restores column widths from config |
| _restore_scrollbar_positions | 8003 | private | None | No | Restores scroll offsets from config |

#### Caveats
- **Three `eventFilter` definitions on `WorkspaceWidget`** (lines 370, 3986, 4366). Python keeps only the last one, so at runtime `eventFilter` is the slider-tooltip version at 4366; the context-menu hide (370) and the scene-table hover-preview / video double-click logic (3986) are not reached through this method. Anything relying on them needs the handlers merged into the 4366 definition.
- Two `QThread` workers (`SceneSuggesterWorker` at 2405, `WhisperWorker` at 6953) are declared *inside* the methods that use them, so they are not importable from module scope.
- `_auto_link_end_frame` (5471) is an intentionally disabled stub; end frames are chosen manually.

---

## GUI Video — Project, Workspace & Reference Dialogs

The `gui/video/` package holds the PySide6 front end for the lyric/MIDI-synced video subsystem. This section covers the top-level tab that owns the whole video workflow and its background generation thread, the enhanced-workspace control widgets (variants, crop, Ken Burns), the project lifecycle dialogs, the workflow wizard, and the reference/frame/clip picker widgets and dialogs.

---

### VideoProjectTab
**Path**: `gui/video/video_project_tab.py` - 2167 lines
**Purpose**: Top-level "Video" tab. Hosts the Workspace / History / References sub-tabs, owns the `VideoGenerationThread` that runs every long-running operation (storyboard, prompt enhancement, image generation, Veo/Omni clip generation, FFmpeg render), and marshals results back onto the GUI thread.
**Language**: Python

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports | 1 |
| `VideoGenerationThread` | 31 |
| `VideoProjectTab` | 1572 |

#### Class: VideoGenerationThread (line 31)
`QThread` worker dispatched by operation name. `run()` switches on `self.operation` and calls the matching private method; each method emits `progress_update(int, str)`, `scene_complete(str, dict)`, and finally `generation_complete(bool, str)`. All failures are caught and reported through `generation_complete(False, ...)` rather than raised.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 37 | constructor | None | No | Stores the `VideoProject`, the operation name, and free-form `**kwargs` used by each operation; sets `cancelled = False` |
| `run` | 44 | public | None | Yes (QThread) | Dispatch table: routes `generate_storyboard` / `enhance_prompts` / `enhance_for_video` / `generate_images` / `generate_end_frame` / `generate_video_clip` / `render_video` / `preview_video` to the handlers below |
| `_generate_storyboard` | 66 | private | None | No | Storyboard-from-text hook; currently a stub (`pass`) — storyboard building happens in the workspace widget |
| `_enhance_prompts` | 71 | private | None | No | Batch LLM prompt enhancement via `core.video.prompt_engine` (`PromptEngine`, `UnifiedLLMProvider`, `PromptStyle`); a batch failure aborts instead of falling back to per-scene calls |
| `_enhance_for_video` | 157 | private | None | No | Rewrites scene prompts for motion — camera movement and shot-to-shot continuity — using the same prompt engine |
| `_generate_images` | 271 | private | None | No | Generates N image variants per scene: resolves the API key through `ConfigManager.get_api_key()`, builds the provider via `get_provider()`, writes thumbnails through `ThumbnailManager`, emits `scene_complete` per scene |
| `_generate_end_frame_images` | 544 | private | None | No | Generates the end-frame image for a scene from its `end_prompt` (Veo 3.1 start→end transitions) |
| `_generate_video_clip` | 725 | private | None | No | Single-scene clip generation. Coerces the retired `OpenAI Sora` provider to `Gemini Omni`, delegates to `_generate_video_clip_omni()` for Omni, otherwise drives `VeoClient` with `VeoGenerationConfig`, MIDI duration snapping, and `ReferenceManager` references |
| `_extract_last_frame` | 1151 | private | Path | No | OpenCV seek to the final frame; writes `frames/scene_{i}_last_frame.png` (0-based name kept for backward compatibility) |
| `_extract_first_frame` | 1182 | private | Path | No | OpenCV read of frame 0; writes `first_frames/scene_{i+1:03d}_first_frame.png` (used as the `VideoButton` hover preview) |
| `_apply_lipsync_to_scene` | 1206 | private | Optional[Path] | No | Applies lip-sync when the scene has `lip_sync_enabled`; returns the original path unchanged if dependencies are missing or processing fails |
| `_generate_video_clip_omni` | 1301 | private | None | No | Gemini Omni path via `OmniClient` / `OmniGenerationConfig` (Interactions API): seed image from `start_frame`, prompt from `video_prompt` falling back to `prompt`, aspect ratio from kwargs |
| `_render_video` | 1466 | private | None | No | Chooses the render backend — `Gemini Veo` → `_render_with_veo()`, otherwise `_render_with_ffmpeg()` |
| `_render_with_ffmpeg` | 1482 | private | None | No | Slideshow render through `FFmpegRenderer` with `RenderSettings` (1920x1080, 24 fps, Ken Burns, transitions); output goes to `<project_dir>/<name>_<timestamp>.mp4` |
| `progress_callback` | 1506 | nested | None | No | Local closure inside `_render_with_ffmpeg` that forwards renderer percent/status to `progress_update` |
| `_render_with_veo` | 1523 | private | None | No | Concatenates Veo-generated clips with correct trimming via `FFmpegRenderer` |
| `progress_callback` | 1545 | nested | None | No | Same forwarding closure for the Veo render path |
| `_preview_video` | 1562 | private | None | No | Preview render — delegates to `_render_video()` |
| `cancel` | 1567 | public | None | No | Sets the `cancelled` flag polled by the long-running loops |

#### Class: VideoProjectTab (line 1572)
`QWidget` that assembles `WorkspaceWidget`, `HistoryTab`, `ReferenceLibraryWidget`, and `LipSyncWidget` into a `QTabWidget`. The Lip-Sync tab is hidden by default (`show_lipsync_tab = False`) because lip-sync moved to the per-scene 🎤 toggle in the storyboard. `__init__` and `init_ui` are heavily instrumented with `INIT STEP` / `UI STEP` log lines so start-up failures are traceable in `imageai_current.log`.

##### Signals
| Signal | Line | Payload | Description |
|--------|------|---------|-------------|
| `image_provider_changed` | 1576 | `str` | Image provider name, forwarded up to the main window |
| `llm_provider_changed` | 1577 | `str, str` | LLM provider + model name, forwarded up to the main window |
| `add_to_history_signal` | 1578 | `dict` | History entry for a newly generated asset |

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 1580 | constructor | None | No | Builds `VideoConfig` and `ProjectManager(projects_dir)`, initializes project/thread state, then calls `init_ui()` |
| `init_ui` | 1614 | public | None | No | Creates the sub-tabs, wires workspace/history/reference/lip-sync signals, syncs an already-loaded project, and restores the last active sub-tab |
| `set_provider` | 1735 | public | None | No | Pushes the image provider name down to the workspace widget |
| `set_llm_provider` | 1740 | public | None | No | Pushes the LLM provider + model down to the workspace widget |
| `on_image_provider_changed` | 1745 | public | None | No | Re-emits `image_provider_changed` for the main window |
| `on_llm_provider_changed` | 1750 | public | None | No | Re-emits `llm_provider_changed` for the main window |
| `_on_sub_tab_changed` | 1755 | private | None | No | Sub-tab change handler; persists the new index |
| `_save_sub_tab_index` | 1759 | private | None | No | Writes `last_sub_tab_index` to `QSettings("ImageAI", "VideoProjects")` |
| `_restore_sub_tab_index` | 1766 | private | None | No | Restores the saved sub-tab index after bounds-checking it |
| `on_project_changed` | 1779 | public | None | No | Adopts the workspace's project and re-points the history tab and reference library at it |
| `on_generation_requested` | 1789 | public | None | No | Entry point for all generation: validates that a project exists (auto-creating one for `generate_storyboard`), constructs and starts a `VideoGenerationThread`, and shows the progress bar |
| `on_restore_requested` | 1820 | public | None | No | Rebuilds project state from `EventStore` up to a timestamp, reloads the workspace UI, and switches to the Workspace tab |
| `@Slot on_progress_update` | 1855 | slot | None | No | Updates the workspace progress bar / status label and mirrors the message into the status console |
| `@Slot on_scene_complete` | 1863 | slot | None | No | Per-scene completion: reads the image sidecar via `read_image_sidecar()` and adds the result to history without hijacking the lower preview panel |
| `@Slot on_generation_complete` | 1979 | slot | None | No | Hides progress, tears the thread down safely (`wait()` + `deleteLater()`), saves the project, appends a `ProjectEvent` to the event store, or shows a generation error via the dialog manager |
| `on_references_changed` | 2046 | public | None | No | Refreshes the workspace when the reference library changes |
| `on_lipsync_finished` | 2053 | public | None | No | Logs and reports a completed lip-sync render |
| `on_lipsync_failed` | 2062 | public | None | No | Logs and reports a lip-sync failure |
| `send_video_to_lipsync` | 2071 | public | None | No | Loads a clip into `LipSyncWidget` and switches to the Lip-Sync tab if it is visible |
| `generate_reference_image_sync` | 2086 | public | Optional[Path] | No | Blocking single-image generation for the reference wizard; forces 1:1 aspect, uses `gemini-2.5-flash-image`, optionally passes a PIL reference image |

---

### Enhanced Workspace Controls
**Path**: `gui/video/enhanced_workspace.py` - 609 lines
**Purpose**: Three self-contained control widgets used by the enhanced video workspace — image-variant browsing/selection, crop positioning, and Ken Burns pan/zoom configuration. Each emits its settings object so the parent can persist it on the project.
**Language**: Python

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports | 1 |
| `ImageVariantSelector` | 30 |
| `CropControlWidget` | 312 |
| `KenBurnsControlWidget` | 451 |

#### Class: ImageVariantSelector (line 30)
Browses the `SceneVariants` for one scene: prev/next navigation, a large preview, a thumbnail strip, and select/delete/regenerate actions. Emits `variant_selected(int)` and `generate_more()`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 36 | constructor | None | No | Initializes `current_variants` / `current_index` and builds the UI |
| `init_ui` | 42 | public | None | No | Scene label, ◀/▶ nav + "Generate More", 300px-min preview, Use/Delete/Regenerate row, scrollable thumbnail strip |
| `set_scene_variants` | 111 | public | None | No | Binds a `SceneVariants` object (and scene name), seeds the index from `selected_index`, refreshes UI + thumbnails |
| `update_ui` | 119 | public | None | No | Enables/disables nav buttons and updates the "Image N of M" label; shows the current variant |
| `show_variant` | 139 | public | None | No | Loads and scales the variant at `index` into the preview label |
| `update_thumbnails` | 163 | public | None | No | Rebuilds the thumbnail strip, marking the selected variant |
| `thumbnail_clicked` | 197 | public | None | No | Jumps the preview to the clicked thumbnail index |
| `show_previous` | 202 | public | None | No | Steps back one variant (no wrap) |
| `show_next` | 208 | public | None | No | Steps forward one variant (no wrap) |
| `select_current` | 214 | public | None | No | Marks the current variant as the scene's selection and emits `variant_selected` |
| `delete_current` | 222 | public | None | No | Guards protected frames (auto-extracted `last_frame`s and auto-linked reference images cannot be deleted), confirms, then sends the file to the recycle bin via `send_to_recycle_bin()` and re-indexes the list |
| `regenerate_current` | 305 | public | None | No | Regeneration hook; currently a stub for the parent to override |

#### Class: CropControlWidget (line 312)
Radio-button crop-position picker with manual X/Y sliders. Emits `crop_changed(CropSettings)` on every change.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 317 | constructor | None | No | Starts from a default `CropSettings()` and builds the UI |
| `init_ui` | 322 | public | None | No | 2x3 mode grid (Center / Top / Bottom / Rule of Thirds / Manual / Smart), manual X/Y sliders (disabled unless Manual), preview label, Reset / Apply-to-All buttons |
| `set_mode` | 397 | public | None | No | Sets `CropMode`, enables the manual group only for `MANUAL`, emits `crop_changed` |
| `update_position` | 404 | public | None | No | Converts slider values to 0.0–1.0 x/y, updates the numeric labels, emits `crop_changed` |
| `set_settings` | 415 | public | None | No | Applies an existing `CropSettings` to the radio buttons and sliders |
| `update_preview` | 430 | public | None | No | Renders the textual crop summary in the preview label |
| `reset_to_defaults` | 441 | public | None | No | Restores a fresh `CropSettings()` |
| `apply_to_all` | 445 | public | None | No | Apply-to-all-similar hook handled by the parent (stub) |

#### Class: KenBurnsControlWidget (line 451)
Enable toggle, preset combo (from `KenBurnsPresets`), start/end x/y/scale spin boxes, and an easing selector. Emits `ken_burns_changed(KenBurnsSettings)`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 456 | constructor | None | No | Starts from a default `KenBurnsSettings()` and builds the UI |
| `init_ui` | 461 | public | None | No | Enable checkbox, preset combo, start/end position + scale grid, easing combo (linear / ease-in / ease-out / ease-in-out), preview and "Set Current as Start/End" buttons (all disabled until enabled) |
| `toggle_enabled` | 565 | public | None | No | Enables/disables the whole control block and emits the updated settings |
| `apply_preset` | 574 | public | None | No | Loads a named preset via `KenBurnsPresets.get_preset()` and applies it |
| `update_settings` | 579 | public | None | No | Reads start/end dicts and easing out of the widgets and emits `ken_burns_changed` |
| `set_settings` | 594 | public | None | No | Pushes an existing `KenBurnsSettings` back into the widgets |

---

### Start Prompt Dialog
**Path**: `gui/video/start_prompt_dialog.py` - 461 lines
**Purpose**: LLM-assisted generation of a scene's start-frame image prompt, with optional visual continuity from the previous frame (style-only or transition mode). Runs the LLM on a worker thread and mirrors all traffic into a status console.
**Language**: Python

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports | 1 |
| `StartPromptGenerationThread` | 30 |
| `StartPromptDialog` | 190 |

#### Class: StartPromptGenerationThread (line 30)
`QThread` that (optionally) analyzes the previous frame with `StyleAnalyzer`, then calls LiteLLM. Signals: `generation_complete(str)`, `generation_failed(str)`, `progress_update(str)`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 38 | constructor | None | No | Captures generator, source text, current prompt, provider/model/api_key, `ContinuityMode`, and the previous frame path |
| `run` | 61 | public | None | Yes (QThread) | Two-step flow: style/transition analysis of the previous frame (failures degrade gracefully to source-only), then prompt generation; `TRANSITION` mode uses the analyzer output directly as the prompt |
| `_generate_prompt_with_style` | 120 | private | str | No | Builds the system/user prompts (with or without style guidance) and calls `litellm.completion()` at `temperature=0.7` with `drop_params=True`; logs the full user prompt and response |

#### Class: StartPromptDialog (line 190)
`DialogCleanupMixin` + `QDialog`. Auto-generates on open, supports regenerate and free-hand editing, persists geometry and splitter sizes in `QSettings("ImageAI", "StartPromptDialog")`, and updates Discord Rich Presence while open.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 199 | constructor | None | No | Stores generation params, sets the window title/min size, builds UI, restores geometry, and immediately calls `generate_prompt()` |
| `init_ui` | 235 | public | None | No | Vertical splitter of context pane (source text, continuity banner, current prompt) / editable generated prompt + indeterminate progress bar / `DialogStatusConsole`; Regenerate button, OK/Cancel box, Ctrl+Enter primary action |
| `generate_prompt` | 341 | public | None | No | Disables OK/Regenerate, logs parameters to both the file logger and the status console, then starts a `StartPromptGenerationThread` |
| `_on_progress_update` | 382 | private | None | No | Mirrors thread progress messages to the log and status console |
| `_get_mode_display_name` | 387 | private | str | No | Maps `ContinuityMode` to "None" / "Style Only" / "Transition" |
| `_on_generation_complete` | 396 | private | None | No | Fills the editor, re-enables buttons, logs the response as SUCCESS |
| `_on_generation_failed` | 409 | private | None | No | Re-enables buttons, logs the error, and leaves an editable failure message in the prompt box |
| `get_prompt` | 424 | public | str | No | Returns the (possibly hand-edited) prompt text |
| `restore_window_geometry` | 428 | public | None | No | Restores saved geometry from `QSettings` |
| `showEvent` | 434 | public | None | No | Sets Discord presence to `CHATTING_WITH_AI` / "Start Frame Prompt" |
| `on_dialog_close` | 442 | public | None | No | Every exit path: resets Discord presence, persists geometry + splitter, disconnects and stops the generation thread with a 2 s wait |

---

### Project Dialogs
**Path**: `gui/video/project_dialog.py` - 452 lines
**Purpose**: The three video-project lifecycle dialogs — create, open, and edit settings — all backed by `ProjectSettings` / `EnhancedProjectManager` from `core.video.project_enhancements`.
**Language**: Python

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports | 1 |
| `NewProjectDialog` | 29 |
| `OpenProjectDialog` | 197 |
| `ProjectSettingsDialog` | 338 |

#### Class: NewProjectDialog (line 29)
Tabbed new-project form (Basic / Generation / Ken Burns / Rendering). Produces a populated `ProjectSettings` in `self.settings` on accept.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 32 | constructor | None | No | Modal 600x500 dialog; `self.settings = None` until accepted |
| `init_ui` | 41 | public | None | No | Basic tab (name + `VersioningMode` radio grid with worked examples + audio handling), Generation tab (images per scene, auto-crop, default `CropMode`), Ken Burns tab (enable, intensity, auto-for-square), Rendering tab (auto-save, draft retention, quality) |
| `accept` | 165 | public | None | No | Rejects an empty name with a warning, otherwise assembles `ProjectSettings(...)` from every control and accepts |

#### Class: OpenProjectDialog (line 197)
Recent-projects list with an info panel and a Browse… escape hatch. `self.selected_project` holds the chosen `Path`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 200 | constructor | None | No | Takes the `EnhancedProjectManager`, builds UI, then loads recent projects |
| `init_ui` | 211 | public | None | No | Recent list (double-click accepts), Project Information form, Browse button, Open/Cancel box, selection-change wiring |
| `load_projects` | 263 | public | None | No | Fills the list from `project_manager.recent_projects`, annotating each entry with Today / Yesterday / N days ago |
| `update_info` | 284 | public | None | No | Shows name/path and reads `workspace.json` (and `project_settings.json`) from the project folder for created/modified timestamps |
| `browse_for_project` | 311 | public | None | No | `QFileDialog.getExistingDirectory()` rooted at the manager's base dir; accepts immediately on pick |
| `accept` | 323 | public | None | No | Falls back to the list selection when nothing was browsed; warns if the resolved path does not exist |

#### Class: ProjectSettingsDialog (line 338)
Edits an existing `ProjectSettings` in place (project name shown read-only).

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 341 | constructor | None | No | Modal 500x400 dialog bound to the passed-in `ProjectSettings` |
| `init_ui` | 350 | public | None | No | Grouped form: Ken Burns defaults, Crop defaults, Generation (images per scene), Rendering (auto-save, draft retention) — all pre-seeded from the current settings |
| `accept` | 440 | public | None | No | Writes every control back onto the `ProjectSettings` instance, then accepts |

---

### Workflow Wizard Widget
**Path**: `gui/video/wizard_widget.py` - 402 lines
**Purpose**: Step-by-step guidance panel for the video workflow. Reads state from `core.video.workflow_wizard.WorkflowWizard` and renders progress, a clickable step list, the current step's description/choices, and contextual help.
**Language**: Python

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports | 1 |
| `WizardStepWidget` | 25 |
| `WorkflowWizardWidget` | 102 |

#### Class: WizardStepWidget (line 25)
A single clickable step row: status glyph, title (bold when current), and an "(optional)" tag. Emits `clicked(WorkflowStep)`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 30 | constructor | None | No | Builds the row from a `step_info` record and sets the description as tooltip |
| `set_style` | 63 | public | None | No | Blue highlighted frame when current, plain white with hover border otherwise |
| `_get_status_icon` | 85 | private | str | No | Maps `StepStatus` to ○ / ◐ / ● / ─ |
| `mousePressEvent` | 95 | public | None | No | Emits `clicked` with the step on left-click |

#### Class: WorkflowWizardWidget (line 102)
Signals: `action_requested(WorkflowStep, choice_key)`, `step_skipped(WorkflowStep)`, `help_requested(WorkflowStep)`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 114 | constructor | None | No | Stores the project, builds the UI, and performs the first refresh |
| `init_ui` | 123 | public | None | No | Title, progress label + bar, scrollable step list, "Current Step" group box containing description, Help button, a scrollable choices panel, and Action / Skip buttons |
| `refresh_wizard_display` | 207 | public | None | No | Pulls a fresh wizard via `project.get_workflow_wizard()`, updates progress/step list/choices, and disables the action button with the blocking reason as tooltip when the step cannot proceed; exceptions are logged, never raised |
| `_update_step_list` | 252 | private | None | No | Rebuilds the `WizardStepWidget` rows (preserving the trailing stretch) and marks the current step |
| `_update_choices_panel` | 274 | private | None | No | Renders each choice as a radio button plus a rich-text block listing benefits (✓), drawbacks (⚠), and requirements; selects the first option by default |
| `_show_help` | 337 | private | None | No | Shows the current step's help text in a `QMessageBox`, with estimated time as informative text |
| `_on_action_clicked` | 358 | private | None | No | Emits `action_requested` with the current step and the selected choice key |
| `_on_skip_clicked` | 373 | private | None | No | Marks an optional step skipped, refreshes, and emits `step_skipped`; a `ValueError` becomes a "Cannot Skip" warning |
| `_on_step_clicked` | 388 | private | None | No | Informational only — pops up that step's help text |
| `set_project` | 399 | public | None | No | Rebinds to a new `VideoProject` and refreshes |

---

### Reference Selector Dialog
**Path**: `gui/video/reference_selector_dialog.py` - 320 lines
**Purpose**: Lets the user pick which global reference images to send to a video generation when more exist than the provider allows (Veo 3 caps at 3). Selection and geometry persist across sessions.
**Language**: Python

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports | 1 |
| `ReferenceCheckCard` | 23 |
| `ReferenceSelectorDialog` | 113 |

#### Class: ReferenceCheckCard (line 23)
A `QFrame` card per `ReferenceImage`: checkbox, colored type badge, 160x160 proportional thumbnail, name, and description. Missing files render a red "(File not found)" placeholder.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 26 | constructor | None | No | Sizes the card (180x240 min, 200 max width) and builds it |
| `setup_ui` | 37 | public | None | No | Checkbox header + type badge, scaled preview (`KeepAspectRatio`), name and optional italic description |
| `_get_type_color` | 97 | private | str | No | Badge color per reference type — character green, object blue, environment orange, style purple, else gray |
| `is_checked` | 108 | public | bool | No | Whether this card's checkbox is ticked |

#### Class: ReferenceSelectorDialog (line 113)
Groups cards by `ReferenceImageType` in a horizontal scroll area with Select All / None / First N shortcuts.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 116 | constructor | None | No | Stores available refs and `max_selection`, opens `QSettings("ImageAI", "ReferenceSelectorDialog")`, builds UI, restores geometry and prior selection |
| `setup_ui` | 131 | public | None | No | Header, explanatory info label, live count label, per-type `QGroupBox` of cards, quick-select buttons, Cancel / "Use Selected References" |
| `update_selection_count` | 226 | public | None | No | Three states: over the limit (orange, OK disabled), zero selected (blue, OK relabelled "Continue (Text-to-Video)"), within limit (green, OK enabled) |
| `select_all` | 248 | public | None | No | Ticks every card |
| `select_none` | 253 | public | None | No | Unticks every card |
| `select_first_n` | 258 | public | None | No | Ticks only the first `max_selection` cards |
| `get_selected_references` | 263 | public | List[ReferenceImage] | No | The checked cards' reference objects |
| `accept` | 267 | public | None | No | Captures the selection, logs it, saves geometry and selected paths, then accepts |
| `reject` | 275 | public | None | No | Saves geometry before rejecting |
| `restore_window_geometry` | 280 | public | None | No | Restores saved geometry |
| `save_window_geometry` | 287 | public | None | No | Persists geometry |
| `restore_selected_references` | 292 | public | None | No | Re-ticks cards whose paths were saved last time; falls back to `select_first_n()` when nothing matched |
| `save_selected_references` | 316 | public | None | No | Persists the checked paths as strings for next launch |

---

### Select Existing Video Dialog
**Path**: `gui/video/select_existing_video_dialog.py` - 295 lines
**Purpose**: Reuse an already-generated clip from another scene — useful after a storyboard regeneration. Lists every scene with a `video_clip`, previews it with `QMediaPlayer`, and returns the chosen path.
**Language**: Python

#### Module-Level Elements
| Element | Line | Type | Description |
|---------|------|------|-------------|
| `QTAV_FFMPEG_LOG` / `QT_LOGGING_RULES` defaults | 15 | env setup | Set at import time to suppress FFmpeg/codec console noise (aac, h264) |

#### Class: SelectExistingVideoDialog (line 32)

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 43 | constructor | None | No | Stores the project and target scene id, creates `QMediaPlayer` + `QAudioOutput`, builds the UI, and loads clips |
| `_setup_ui` | 66 | private | None | No | Info banner, horizontal splitter (40/60) of clip list and preview pane with `QVideoWidget`, Play/Stop controls, and a read-only context `QTextEdit`; OK starts disabled |
| `_load_available_clips` | 155 | private | None | No | Adds one item per scene with an existing `video_clip`, stashing the `Scene` in `Qt.UserRole`; marks the current scene with ⭐ and shows a disabled placeholder when none exist |
| `_on_selection_changed` | 192 | private | None | No | Updates preview and context info, enables OK, and records `selected_video_path` |
| `_on_item_double_clicked` | 212 | private | None | No | Double-click selects and accepts in one action |
| `_update_preview` | 219 | private | None | No | Stops playback and loads the clip via `QUrl.fromLocalFile()` inside `SuppressStderr()` to hide decoder chatter |
| `_update_context_info` | 239 | private | None | No | HTML summary — scene number, source line, duration, truncated image and video prompts, file name |
| `_clear_preview` | 258 | private | None | No | Stops playback, clears the source and context, and disables OK |
| `_toggle_playback` | 269 | private | None | No | Play/Pause toggle with matching button text |
| `_stop_playback` | 278 | private | None | No | Stops and resets the button label |
| `get_selected_video_path` | 283 | public | Optional[Path] | No | The chosen clip path, or `None` |
| `closeEvent` | 292 | public | None | No | Stops playback on close so the media player releases the file |

---

### Frame Button
**Path**: `gui/video/frame_button.py` - 274 lines
**Purpose**: The compact start/end-frame (and reference-slot) button used throughout the storyboard table, plus the shared hover-preview popup. Encodes three states — empty (➕), generated (🖼️), auto-linked (🔗) — and exposes all frame actions as signals so the owning widget performs the work.
**Language**: Python

#### Table of Contents
| Section | Line Number |
|---------|-------------|
| Imports | 1 |
| `FramePreviewPopup` | 17 |
| `FrameButton` | 70 |

#### Class: FramePreviewPopup (line 17)
Frameless always-on-top `QLabel` used as a hover thumbnail; also reused by `VideoButton`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 20 | constructor | None | No | Tooltip/frameless/stay-on-top flags, bordered white styling, starts hidden |
| `show_preview` | 36 | public | None | No | Loads the image, scales it proportionally to 200x200 (`KeepAspectRatio`, `SmoothTransformation`), offsets 20px from the cursor and flips side when it would run off-screen; all failures are logged, never raised |

#### Class: FrameButton (line 70)
Signals (lines 86–94): `frame_clicked`, `generate_requested`, `select_requested`, `select_from_scene_requested`, `clear_requested`, `view_requested`, `auto_link_requested`, `load_image_requested`, `use_last_generated_requested`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 96 | constructor | None | No | Takes `frame_type` ("start"/"end"/`ref{n}`), fixes height to 30px to match the LLM buttons, leaves max width unset for high-DPI, enables mouse tracking |
| `set_frame` | 142 | public | None | No | Sets the frame path and auto-linked flag, then refreshes the appearance |
| `update_appearance` | 154 | public | None | No | Chooses glyph and tooltip for auto-linked / generated / empty states |
| `enterEvent` | 174 | public | None | No | Shows the hover preview for a real (non-auto-linked) frame |
| `leaveEvent` | 180 | public | None | No | Hides the preview |
| `_show_preview` | 185 | private | None | No | Lazily creates the `FramePreviewPopup` and shows it at the cursor |
| `_hide_preview` | 193 | private | None | No | Hides the popup if it exists |
| `hide_preview` | 198 | public | None | No | Public wrapper so parents can force-hide the popup |
| `_on_clicked` | 202 | private | None | No | Emits `view_requested` when a frame exists, otherwise `generate_requested` |
| `contextMenuEvent` | 211 | public | None | No | Hides the preview, then builds a state-dependent menu — populated: View / Select from Variants / Select from Scene Images / Load Image… / Regenerate / Clear; empty: Generate / Load Image… / Use Last Generated / Select from Scene Images |
| `mouseMoveEvent` | 269 | public | None | No | Keeps the visible preview pinned to the cursor |

---

### Video Button
**Path**: `gui/video/video_button.py` - 253 lines
**Purpose**: Per-scene video-clip button in the storyboard. Shows 🎬 before generation and 👁️ once a clip exists, previews the clip's first frame on hover, and exposes Play / Extend / Refine / Regenerate / Select-existing / Clear through a context menu.
**Language**: Python

#### Class: VideoButton (line 19)
Signals (lines 35–41): `clicked_load_frame`, `regenerate_requested`, `clear_requested`, `play_requested`, `select_existing_requested`, `extend_requested` (Veo 3.1 only), `refine_requested` (Gemini Omni only).

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 43 | constructor | None | No | Initializes clip/frame/flag state (`has_video_prompt`, `uses_veo_31`, `is_omni`), fixes height to 30px, enables mouse tracking, sets the initial appearance |
| `set_video_state` | 94 | public | None | No | Updates clip path, first-frame path, prompt presence, Veo 3.1 flag, and the Omni flag that enables Refine; then refreshes appearance |
| `update_appearance` | 119 | public | None | No | 👁️ + play/regenerate tooltip when a clip exists; 🎬 otherwise, with Veo 3 vs Veo 3.1 wording, and disabled entirely until a video prompt exists |
| `has_video` | 143 | public | bool | No | True when `video_path` is set and the file exists |
| `enterEvent` | 147 | public | None | No | Shows the first-frame hover preview when a clip and frame both exist |
| `leaveEvent` | 153 | public | None | No | Hides the preview |
| `_show_preview` | 158 | private | None | No | Lazily creates a `FramePreviewPopup` (imported from `frame_button`) and shows the 200x200 first-frame thumbnail |
| `_hide_preview` | 166 | private | None | No | Hides the popup |
| `_on_clicked` | 171 | private | None | No | Plays the clip when one exists, otherwise emits `regenerate_requested` to start generation |
| `reset_toggle_state` | 180 | public | None | No | No-op retained for API compatibility with earlier toggle behavior |
| `contextMenuEvent` | 185 | public | None | No | With a clip: Play, Extend Video (+7s) when `uses_veo_31`, Refine (Omni)… when `is_omni`, Regenerate, Select Existing Video…, Clear. Without: Generate Video, Select Existing Video… |
| `mouseMoveEvent` | 248 | public | None | No | Repositions a visible preview to follow the cursor |

---

### Variant Selector Dialog
**Path**: `gui/video/variant_selector_dialog.py` - 182 lines
**Purpose**: Grid picker for choosing one generated image variant as a scene's start or end frame. Accepts either `ImageVariant` objects or bare `Path`s.
**Language**: Python

#### Class: VariantSelectorDialog (line 16)
`DialogCleanupMixin` + `QDialog`; geometry is persisted under `variant_selector/geometry` in `QSettings("ImageAI", "VideoProjects")`.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 19 | constructor | None | No | Stores the variant list, current selection and title; 800x600 minimum; builds UI and restores geometry |
| `on_dialog_close` | 47 | public | None | No | Persists geometry on every exit path (OK / Cancel / Escape / X) |
| `init_ui` | 51 | public | None | No | Scrollable 3-column grid of cards — each an exclusive `QRadioButton` (accessible name + path tooltip), a 200x200 proportionally scaled preview that is itself clickable, and a filename label; Cancel / Select buttons with Select disabled until something is chosen, plus a Ctrl+Enter primary action |
| `_accept_if_enabled` | 167 | private | None | No | Ctrl+Enter accepts only while the Select button is enabled |
| `_on_selection_changed` | 172 | private | None | No | Records the chosen path and enables Select, guarding the initial `setChecked()` that fires before `select_btn` exists |
| `get_selected_image` | 180 | public | Optional[Path] | No | The chosen image path |

---

### Reference Images Widget
**Path**: `gui/video/reference_images_widget.py` - 169 lines
**Purpose**: Horizontal strip of up to three `FrameButton` slots holding style/character/environment reference images for Veo 3 visual continuity. Pure signal relay — it owns no generation logic.
**Language**: Python

#### Class: ReferenceImagesWidget (line 18)
Signals (lines 33–38): `reference_changed(int, object)`, `generate_requested(int)`, `select_requested(int)`, `select_from_scene_requested(int)`, `view_requested(int)`, `load_requested(int)` — each carrying the slot index.

##### Methods
| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 40 | constructor | None | No | Creates `max_references` (default 3) `FrameButton`s typed `ref1..refN` with per-slot tooltips, forwards each button signal through a slot-index lambda, and sets a 158px minimum width so all three fit |
| `set_reference_image` | 86 | public | None | No | Bounds-checked slot assignment (or clear) that also emits `reference_changed` |
| `get_reference_image` | 99 | public | Optional[Path] | No | Path in the given slot, or `None` |
| `get_all_references` | 113 | public | List[Optional[Path]] | No | All slots, including empty ones |
| `get_valid_references` | 122 | public | List[Path] | No | Only slots whose file actually exists — what gets sent to the provider |
| `clear_all` | 135 | public | None | No | Clears every slot |
| `_on_generate_requested` | 140 | private | None | No | Logs and re-emits `generate_requested` with the slot index |
| `_on_select_requested` | 145 | private | None | No | Logs and re-emits `select_requested` (select from variants) |
| `_on_select_from_scene_requested` | 150 | private | None | No | Logs and re-emits `select_from_scene_requested` (select from any scene's images) |
| `_on_clear_requested` | 155 | private | None | No | Clears the slot directly rather than re-emitting |
| `_on_view_requested` | 159 | private | None | No | Re-emits `view_requested` only when the file exists |
| `_on_load_requested` | 166 | private | None | No | Logs and re-emits `load_requested` (load from disk) |

---

## GUI Video — Reference Library, Lipsync & Prompt Dialogs

Supporting PySide6 widgets and dialogs for the Video Project tab: character-reference generation and library management, MuseTalk lip-sync, project history/version control, dependency-installer wizards (MuseTalk, Whisper), Suno package preprocessing, LLM prompt-generation dialogs, project browsing, and the reusable prompt field.

---

### ReferenceGenerationDialog
**Path**: `gui/video/reference_generation_dialog.py` - 955 lines
**Purpose**: Standalone wizard that generates three character reference images (front / 3-4 side / full body) for cross-scene consistency, with its own provider + model selection, settings persistence, and import-from-library/disk paths.
**Language**: Python

#### Classes

**`ReferenceGenerationWorker(QThread)`** (line 30) — Background worker mirroring the main `GenWorker` pattern: instantiates the provider from `ConfigManager`, builds three angle prompts from the description + style, and emits per-image results. Signals: `progress(int, str)`, `reference_generated(int, str)`, `generation_complete(bool, str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 37 | constructor | None | No | Stores description, style, output dir, provider/model, auth mode, aspect ratio, optional reference image |
| `run` | 57 | public | None | No | Generates the 3 angle views via `provider.generate()`, emitting progress and per-file signals |

**`ReferenceGenerationDialog(QDialog)`** (line 170) — Modal dialog (800×900) driving the worker; also supports importing existing references instead of generating. Signal: `references_generated(list)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 178 | constructor | None | No | Takes parent, `VideoProject`, `ConfigManager`, providers dict; loads settings then builds UI |
| `load_settings` | 196 | public | None | No | Reads `char_ref_*` keys (provider, model, style, quality, description, reference image) from config |
| `save_settings` | 213 | public | None | No | Writes current combo/text state back to config and saves |
| `setup_ui` | 234 | public | None | No | Builds provider/model group, description + style/quality controls, 3 preview slots, progress bar, buttons |
| `on_provider_changed` | 505 | public | None | No | Repopulates the model list per provider (Google/Gemini, OpenAI, Stability, fallback) and restores the saved model |
| `upload_reference_image` | 542 | public | None | No | File dialog to pick a guide image that steers all 3 views |
| `clear_reference_image` | 571 | public | None | No | Drops the guide image and resets its label |
| `import_from_library` | 579 | public | None | No | Selection sub-dialog over the project's global references; fills preview slots |
| `import_from_files` | 669 | public | None | No | Copies up to 3 picked files into `<project>/references` as `imported_N_*` |
| `start_generation` | 726 | public | None | No | Validates description/model, resolves auth mode (api-key vs gcloud), saves settings, launches the worker |
| `on_progress` | 812 | public | None | No | Updates progress bar and status label |
| `on_reference_generated` | 817 | public | None | No | Loads the new image into its preview slot (scaled, aspect-preserved) |
| `on_generation_complete` | 838 | public | None | No | Re-enables controls, sets final status, marks slots that never produced an image |
| `add_to_project` | 864 | public | None | No | Wraps paths as `ReferenceImage` (type CHARACTER, `is_global=True`), adds to project, saves, emits `references_generated` |
| `showEvent` | 921 | public | None | No | Sets Discord Rich Presence to "Generate References" |
| `closeEvent` | 929 | public | None | No | Resets presence, saves settings, disconnects and stops the worker (2 s wait) |

---

### ReferenceLibraryWidget
**Path**: `gui/video/reference_library_widget.py` - 819 lines
**Purpose**: Two-tab library UI for a video project's global reference images and for frames extracted from generated scene clips, with per-card validation feedback and add/edit/remove flows.
**Language**: Python

#### Classes

**`ReferenceCard(QFrame)`** (line 24) — Card for one `ReferenceImage`: thumbnail, type badge, global checkbox, validation status, context menu. Signals: `remove_clicked(object)`, `edit_clicked(object)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 30 | constructor | None | No | Sets fixed sizing (min 200×280, max width 250), builds UI, applies validation border |
| `setup_ui` | 42 | public | None | No | Builds type badge, name, thumbnail, global checkbox, validation label |
| `_on_global_changed` | 123 | private | None | No | Syncs the checkbox into `reference.is_global` |
| `_get_type_color` | 128 | private | str | No | Badge color by ref type (character/object/environment/style) |
| `update_validation_status` | 139 | public | None | No | Runs `ReferenceImageValidator`; shows valid dimensions, warning count, or error count with tooltips |
| `update_validation_border` | 163 | public | None | No | Green/orange/red frame border reflecting validation result |
| `contextMenuEvent` | 180 | public | None | No | "Edit Info" / "Remove" context menu emitting the card signals |

**`ExtractedFrameCard(QFrame)`** (line 195) — Compact fixed-size (160×200) card for a start/end frame pulled from a scene clip. Signal: `add_as_reference_clicked(Path, str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 200 | constructor | None | No | Stores frame path, frame type ("start"/"end"), source scene text |
| `setup_ui` | 212 | public | None | No | Builds the compact thumbnail + label + add-as-reference action |

**`ReferenceLibraryWidget(QWidget)`** (line 262) — Tab host for the two library views. Signals: `references_changed()`, `frame_selected(Path)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 268 | constructor | None | No | Holds project plus card lists; builds UI and refreshes if a project exists |
| `setup_ui` | 278 | public | None | No | Creates the `QTabWidget` and both tabs |
| `_setup_references_tab` | 295 | private | None | No | Header, count label, Generate / Add Existing buttons, scrollable card row, empty state |
| `_setup_extracted_frames_tab` | 360 | private | None | No | "Extracted Frames" header, count label, grid container, empty state |
| `set_project` | 412 | public | None | No | Swaps the active `VideoProject` and refreshes |
| `refresh` | 417 | public | None | No | Deletes existing cards, then refreshes both tabs (or shows "(No project)") |
| `_refresh_references` | 442 | private | None | No | Rebuilds `ReferenceCard`s, updates global/total counts, wires remove/edit signals |
| `_refresh_extracted_frames` | 470 | private | None | No | Scans every scene's `first_frame`/`last_frame`, lays cards out 6-per-row |
| `on_generate_clicked` | 508 | public | None | No | Walks the parent chain for config/providers and opens `ReferenceGenerationDialog` |
| `on_add_existing_clicked` | 536 | public | None | No | File-picker flow to register an on-disk image as a project reference |
| `on_remove_reference` | 659 | public | None | No | Confirms, calls `project.remove_global_reference()`, saves, refreshes, emits change |
| `on_edit_reference` | 677 | public | None | No | Inline form dialog for type / name / description; writes back and saves the project |
| `on_references_generated` | 730 | public | None | No | Handler for the wizard's `references_generated` — refresh + emit `references_changed` |
| `on_frame_selected` | 736 | public | None | No | Prompts for reference details, then promotes an extracted frame into the library |

---

### LipSyncWidget
**Path**: `gui/video/lipsync_widget.py` - 682 lines
**Purpose**: Lip-sync tab UI — MuseTalk install status/gating, drag-and-drop video + audio selection, backend and bbox-shift configuration, threaded generation with a status console.
**Language**: Python

#### Classes

**`LipSyncGenerationThread(QThread)`** (line 28) — Runs the selected lip-sync provider off the UI thread. Signals: `progress(str)`, `finished(bool, str, str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 34 | constructor | None | No | Stores video, audio, output path, `LipSyncBackend`, bbox shift |
| `run` | 49 | public | None | No | Invokes the provider and emits success/message/output-path |

**`DropLabel(QLabel)`** (line 73) — Dashed drop target that accepts only whitelisted extensions. Signal: `file_dropped(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 78 | constructor | None | No | Normalizes accepted extensions, enables drops, applies dashed styling |
| `dragEnterEvent` | 98 | public | None | No | Accepts the drag only for matching URLs |
| `dragLeaveEvent` | 117 | public | None | No | Restores the idle border style |
| `dropEvent` | 133 | public | None | No | Emits `file_dropped` with the local path |

**`LipSyncWidget(QWidget)`** (line 159) — Main lip-sync surface. Signals: `generation_started()`, `generation_finished(str)`, `generation_failed(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 174 | constructor | None | No | Tracks video/audio paths and the worker; builds UI and checks install state |
| `init_ui` | 182 | public | None | No | Dev-notice banner, install-status frame, drop targets, provider combo, bbox slider, splitters, `DialogStatusConsole` |
| `_on_primary_action` | 441 | private | None | No | Ctrl+Enter → `start_generation()` when the button is enabled |
| `hideEvent` | 446 | public | None | No | Persists both splitter states to `QSettings("ImageAI", "VideoProjects")` |
| `update_install_status` | 453 | public | None | No | Runs `check_musetalk_installed()` and swaps the status frame/install button |
| `update_generate_button` | 484 | public | None | No | Enables the button only when installed + video + audio + not running; sets its label accordingly |
| `on_install_clicked` | 506 | public | None | No | Runs `show_musetalk_install_dialog()` then re-checks status |
| `browse_video` | 511 | public | None | No | File dialog for video/image sources |
| `browse_audio` | 530 | public | None | No | File dialog for the driving audio |
| `on_video_dropped` | 547 | public | None | No | Drop handler → `set_video_path` |
| `on_audio_dropped` | 551 | public | None | No | Drop handler → `set_audio_path` |
| `set_video_path` | 555 | public | None | No | Stores the path, updates the label/preview, refreshes button state |
| `set_audio_path` | 567 | public | None | No | Same for the audio input |
| `clear_video` | 579 | public | None | No | Clears the video selection |
| `clear_audio` | 588 | public | None | No | Clears the audio selection |
| `on_bbox_changed` | 597 | public | None | No | Mirrors slider value into its label |
| `start_generation` | 601 | public | None | No | Builds `<video dir>/lipsync_output/<stem>_lipsync.mp4`, logs params to the console, starts the thread |
| `on_generation_progress` | 641 | public | None | No | Appends worker messages to the status console |
| `on_generation_finished` | 645 | public | None | No | Logs SUCCESS/ERROR, stores `_output_path`, re-evaluates the button, re-emits |
| `open_output_folder` | 660 | public | None | No | Opens the output directory via explorer/open/xdg-open |
| `set_video_from_project` | 675 | public | None | No | Integration hook so the Video Project tab can push a rendered clip in |

---

### HistoryTab
**Path**: `gui/video/history_tab.py` - 550 lines
**Purpose**: Visual timeline over the project event store (`~/.imageai/video_projects/events.db`) — browse events, inspect details, create restore points, restore, export, and prune.
**Language**: Python

#### Classes

**`HistoryTab(QWidget)`** (line 25) — Signals: `restore_requested(str, datetime)`, `event_selected(dict)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 32 | constructor | None | No | Stores project id, event list, logger; builds UI and connects the event store |
| `init_ui` | 48 | public | None | No | Assembles timeline panel, details panel, and control row into the layout |
| `create_timeline_panel` | 72 | public | QWidget | No | Filter combo + `QTreeWidget` timeline grouped by date |
| `create_details_panel` | 130 | public | QWidget | No | Event info label plus the detail text view |
| `create_controls` | 167 | public | QWidget | No | Restore-point / restore / export / cleanup buttons and statistics labels |
| `init_event_store` | 192 | public | None | No | Opens `EventStore` at the user DB path; loads history when a project id is set |
| `set_project` | 203 | public | None | No | Switches project and reloads history |
| `load_history` | 213 | public | None | No | Fetches events for the project, applies the filter, updates statistics |
| `apply_filter` | 232 | public | None | No | Maps the combo selection to event types and rebuilds the tree |
| `on_event_selected` | 297 | public | None | No | Shows details, enables restore buttons, emits `event_selected` |
| `show_event_details` | 319 | public | None | No | Renders id/timestamp and the event payload into the details panel |
| `create_restore_point` | 361 | public | None | No | Prompts for name + description and writes a restore point to the store |
| `restore_to_point` | 404 | public | None | No | Confirms and requests restore to the selected event's timestamp |
| `toggle_details` | 427 | public | None | No | Detail-level toggle (placeholder) |
| `update_statistics` | 432 | public | None | No | Updates event count and approximate storage labels |
| `export_history` | 447 | public | None | No | Saves the event list as JSON via a file dialog |
| `clear_old_events` | 483 | public | None | No | Drops events older than 30 days, preserving `PROJECT_RESTORED` entries |
| `_get_event_display_name` | 514 | private | str | No | Title-cases an `EventType` value |
| `_get_event_summary` | 518 | private | str | No | Per-type one-line summary (scene added, images generated, duration, …) |
| `_get_event_color` | 537 | private | Optional[QColor] | No | Per-type row color for the timeline |

---

### MuseTalk Install Dialogs
**Path**: `gui/video/musetalk_install_dialog.py` - 456 lines
**Purpose**: Two-phase install wizard for the MuseTalk lip-sync dependency — confirmation (disk/GPU requirements) followed by a non-closable progress dialog covering package install then model download.
**Language**: Python

#### Classes

**`MuseTalkInstallConfirmDialog(QDialog)`** (line 26) — Pre-install confirmation.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 29 | constructor | None | No | Modal, min width 550 |
| `init_ui` | 36 | public | None | No | Requirements/disk/GPU summary and Install/Cancel buttons |

**`MuseTalkInstallProgressDialog(QDialog)`** (line 144) — Progress UI with the window close button removed while work is running. Signal: `installation_complete(bool, str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 149 | constructor | None | No | Strips close hint, tracks installer/downloader, start time, and current phase |
| `init_ui` | 169 | public | None | No | Title, phase label, progress bar, elapsed timer, scrolling output log |
| `start_installation` | 251 | public | None | No | Detects GPU, resolves packages/index URL, wires and starts `MuseTalkPackageInstaller` |
| `update_elapsed_time` | 275 | public | None | No | Ticks the "Elapsed: m:ss" label |
| `on_progress` | 283 | public | None | No | Appends a timestamped line and auto-scrolls the log |
| `on_percentage` | 293 | public | None | No | Scales phase percentage into the 0-50 / 50-100 halves |
| `on_packages_finished` | 305 | public | None | No | On success advances to phase 2; on failure notifies and emits completion |
| `download_models` | 326 | public | None | No | Starts `MuseTalkModelDownloader` for phase 2 |
| `on_models_finished` | 338 | public | None | No | Stops the timer, reports outcome, offers restart |
| `show_notification` | 376 | public | None | No | System-tray toast (color-coded, auto-hidden after ~11 s) |
| `restart_application` | 401 | public | None | No | Relaunches via `QProcess.startDetached` and quits |
| `reject` | 415 | public | None | No | Blocks Escape/close while an installer thread is running |

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `show_musetalk_install_dialog` | 429 | public | bool | No | Full flow: skip if already installed, confirm, then run the progress dialog |

---

### Whisper Install Dialogs
**Path**: `gui/video/whisper_install_dialog.py` - 410 lines
**Purpose**: Install wizard for the Whisper audio-analysis dependency — same confirm-then-progress pattern as MuseTalk but single-phase (packages only).
**Language**: Python

#### Classes

**`WhisperInstallConfirmDialog(QDialog)`** (line 25)

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 28 | constructor | None | No | Modal, min width 500 |
| `init_ui` | 35 | public | None | No | Requirements/disk/GPU summary with Install/Cancel |

**`WhisperInstallProgressDialog(QDialog)`** (line 145) — Signal: `installation_complete(bool, str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 150 | constructor | None | No | Strips the close button, tracks installer and start time |
| `init_ui` | 168 | public | None | No | Title, progress bar, elapsed label, output log |
| `start_installation` | 250 | public | None | No | Detects GPU, logs the package list, starts `WhisperPackageInstaller` |
| `update_elapsed_time` | 277 | public | None | No | Updates the elapsed-time label |
| `on_progress` | 285 | public | None | No | Appends a log line and auto-scrolls |
| `on_percentage` | 295 | public | None | No | Sets the progress bar directly (single phase) |
| `on_packages_finished` | 299 | public | None | No | Reports success/failure, notifies, emits completion, offers restart |
| `show_notification` | 331 | public | None | No | System-tray toast |
| `restart_application` | 356 | public | None | No | Detached relaunch then quit |
| `reject` | 370 | public | None | No | Blocks close while installing |

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `show_whisper_install_dialog` | 383 | public | bool | No | Already-installed check → confirm dialog → progress dialog |

---

### SunoPreprocessDialog
**Path**: `gui/video/suno_preprocess_dialog.py` - 341 lines
**Purpose**: Lets the user choose which Suno stems (WAV) and MIDI files to merge into a project; WAV/MIDI pairs for the same stem are linked so toggling one toggles the other.
**Language**: Python

#### Classes

**`SunoPreprocessDialog(DialogCleanupMixin, QDialog)`** (line 28) — All items selected by default; volume mixing is intentionally out of scope (do it in Suno before export).

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 43 | constructor | None | No | Computes the linked-stem intersection of audio and MIDI names, builds UI, restores geometry |
| `on_dialog_close` | 70 | public | None | No | Saves geometry under `suno_preprocess/geometry` on every exit path |
| `_setup_ui` | 74 | private | None | No | Scrollable checkbox lists for stems and MIDI, select/deselect-all, OK/Cancel |
| `_on_audio_checkbox_changed` | 210 | private | None | No | Mirrors an audio toggle onto the linked MIDI checkbox (signals blocked) |
| `_on_midi_checkbox_changed` | 223 | private | None | No | Mirrors a MIDI toggle onto the linked audio checkbox |
| `_select_all` | 236 | private | None | No | Checks every audio and MIDI box |
| `_deselect_all` | 243 | private | None | No | Unchecks every box |
| `_validate_and_accept` | 250 | private | None | No | Rejects an empty selection with a warning, otherwise accepts |
| `get_selected_audio_stems` | 266 | public | Set[str] | No | Checked audio stem names |
| `get_selected_midi_files` | 278 | public | Set[str] | No | Checked MIDI stem names |
| `has_audio_selection` | 290 | public | bool | No | True when any audio stem is checked |
| `has_midi_selection` | 294 | public | bool | No | True when any MIDI file is checked |

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `show_merge_progress_dialog` | 299 | public | QProgressDialog | No | Indeterminate, deliberately non-cancellable modal shown while the synchronous merge runs |

---

### VideoPromptDialog
**Path**: `gui/video/video_prompt_dialog.py` - 304 lines
**Purpose**: LLM dialog that turns a start-frame prompt into motion/camera instructions optimized for video generation (Veo-style), with regenerate, manual editing, and a full request/response status console.
**Language**: Python

#### Classes

**`VideoPromptGenerationThread(QThread)`** (line 27) — Signals: `generation_complete(str)`, `generation_failed(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 34 | constructor | None | No | Captures generator, start prompt, duration, provider/model, camera-movement and prompt-flow flags, previous video prompt |
| `run` | 56 | public | None | No | Builds a `VideoPromptContext`, calls the generator, emits result or error |

**`VideoPromptDialog(DialogCleanupMixin, QDialog)`** (line 85) — Auto-generates on open.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 93 | constructor | None | No | Stores generation params, sets up `QSettings("ImageAI", "VideoPromptDialog")`, builds UI, restores geometry, kicks off generation |
| `init_ui` | 129 | public | None | No | Context group, editable result box, progress bar, Regenerate/OK/Cancel, splitter-mounted `DialogStatusConsole` |
| `generate_prompt` | 212 | public | None | No | Disables OK while running, logs the outgoing request (provider/model/duration/flags/prompts), starts the thread |
| `_on_generation_complete` | 247 | private | None | No | Fills the editor, re-enables actions, logs the response as SUCCESS |
| `_on_generation_failed` | 258 | private | None | No | Shows the failure inline, logs ERROR, keeps manual editing available |
| `get_prompt` | 268 | public | str | No | Returns the final (possibly hand-edited) prompt text |
| `restore_window_geometry` | 272 | public | None | No | Restores saved geometry |
| `showEvent` | 278 | public | None | No | Sets Discord presence to "Video Prompt" |
| `on_dialog_close` | 286 | public | None | No | Resets presence, persists geometry + splitter, disconnects and stops the worker (2 s wait) |

---

### ProjectBrowserDialog
**Path**: `gui/video/project_browser.py` - 294 lines
**Purpose**: Table-based browser for existing video projects with metadata preview, "auto-reload last project" preference, and last-project persistence in `QSettings`.
**Language**: Python

#### Classes

**`ProjectBrowserDialog(QDialog)`** (line 23) — Signal: `project_selected(Path)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 28 | constructor | None | No | Holds the project manager and `QSettings("ImageAI", "VideoProjects")`; min size 800×500 |
| `setup_ui` | 40 | public | None | No | Title, projects table (name/created/modified/duration/path), info panel, auto-reload checkbox, Open/Cancel |
| `load_projects` | 117 | public | None | No | Populates rows from `project_manager.list_projects()`, formats ISO dates, sorts newest-first, preselects row 0 |
| `on_selection_changed` | 175 | public | None | No | Tracks the selected project path and toggles the Open button |
| `update_info` | 193 | public | None | No | Reads the project JSON and renders a details summary |
| `on_double_click` | 235 | public | None | No | Double-click shortcut for `open_selected()` |
| `open_selected` | 240 | public | None | No | Persists `last_project`, emits `project_selected`, accepts the dialog (verbose logging throughout) |
| `on_auto_reload_toggled` | 260 | public | None | No | Persists the `auto_reload_last` preference |

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| `get_last_project_path` | 266 | public | Optional[Path] | No | Returns the last opened project path when auto-reload is on and the file still exists |

---

### SceneImageSelectorDialog
**Path**: `gui/video/scene_image_selector_dialog.py` - 255 lines
**Purpose**: Radio-button picker for choosing one image from any scene in the project (used to source start/end frames and references), grouped per scene with source-text previews.
**Language**: Python

#### Classes

**`SceneImageSelectorDialog(DialogCleanupMixin, QDialog)`** (line 17) — Min size 900×700; geometry persisted per-dialog.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 20 | constructor | None | No | Stores scenes, current index, custom title; builds UI and restores saved geometry |
| `on_dialog_close` | 49 | public | None | No | Saves geometry under `scene_image_selector/geometry` on every exit path |
| `init_ui` | 53 | public | None | No | Scroll area of per-scene groups, exclusive `QButtonGroup`, Select/Cancel with Ctrl+Enter binding |
| `_accept_if_enabled` | 120 | private | None | No | Ctrl+Enter accepts only when Select is enabled |
| `_create_scene_group` | 125 | private | QGroupBox | No | Builds one scene's group box — title with truncated source text plus a grid of image radio thumbnails |
| `_on_selection_changed` | 242 | private | None | No | Records the chosen image path and scene index, enables Select |
| `get_selected_image` | 249 | public | Optional[Path] | No | Chosen image path |
| `get_selected_scene_index` | 253 | public | Optional[int] | No | Scene index the chosen image came from |

---

### EndPromptDialog
**Path**: `gui/video/end_prompt_dialog.py` - 232 lines
**Purpose**: LLM dialog for generating an end-frame prompt from the current scene's start prompt and the next scene's start prompt, with regenerate and manual editing.
**Language**: Python

#### Classes

**`EndPromptGenerationThread(QThread)`** (line 22) — Signals: `generation_complete(str)`, `generation_failed(str)`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 29 | constructor | None | No | Stores generator, `EndPromptContext`, provider, model |
| `run` | 43 | public | None | No | Calls `generate_end_prompt()`; treats an empty response as a failure |

**`EndPromptDialog(QDialog)`** (line 61) — Auto-generates on open; min size 600×500.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 69 | constructor | None | No | Stores start/next prompts, duration, provider/model; builds UI and starts generation |
| `init_ui` | 99 | public | None | No | Context groups (current + next scene), editable result box, progress bar, Regenerate/Use buttons |
| `generate_prompt` | 174 | public | None | No | Builds the `EndPromptContext` and starts the worker thread |
| `_on_generation_complete` | 201 | private | None | No | Populates the editor and logs the generated prompt |
| `_on_generation_failed` | 209 | private | None | No | Shows the error inline and logs it, leaving the text editable |
| `get_prompt` | 216 | public | str | No | Returns the final prompt text |
| `showEvent` | 220 | public | None | No | Sets Discord presence to "End Frame Prompt" |
| `closeEvent` | 228 | public | None | No | Resets Discord presence to IDLE |

---

### PromptFieldWidget
**Path**: `gui/video/prompt_field_widget.py` - 177 lines
**Purpose**: Reusable prompt editor row — multiline `QTextEdit` plus ✨ LLM, ↶ undo and ↷ redo buttons backed by a `PromptHistory` (256 levels) that serializes with the project.
**Language**: Python

#### Classes

**`PromptFieldWidget(QWidget)`** (line 22) — Signals: `text_changed(str)`, `llm_requested()`, `undo_clicked()`, `redo_clicked()`.

| Method | Line | Type | Returns | Async | Description |
|--------|------|------|---------|-------|-------------|
| `__init__` | 39 | constructor | None | No | Creates the history, plain-text edit (30-200 px tall, word-wrapped) and the three top-aligned 30 px buttons |
| `_on_text_changed` | 96 | private | None | No | Mirrors text into the tooltip, re-emits `text_changed`, refreshes button states |
| `set_text` | 106 | public | None | No | Programmatic set with optional history push; blocks signals to avoid recursion |
| `get_text` | 129 | public | str | No | Current text |
| `commit_to_history` | 133 | public | None | No | Pushes the current text onto the history stack |
| `_on_undo` | 140 | private | None | No | Saves uncommitted text, pops the previous entry, re-emits `text_changed` and `undo_clicked` |
| `_on_redo` | 155 | private | None | No | Restores the next history entry and emits `redo_clicked` |
| `_update_button_states` | 165 | private | None | No | Enables undo/redo from `history.can_undo()` / `can_redo()` |
| `get_history` | 170 | public | PromptHistory | No | History object for serialization into the project |
| `set_history` | 174 | public | None | No | Restores a deserialized history and refreshes button states |

---

### gui/video package init
**Path**: `gui/video/__init__.py` - 0 lines
**Purpose**: Empty package marker — all `gui.video` modules are imported by their full paths; no re-exports.
**Language**: Python

---

## Scripts, Tools & Standalone Utilities

Loose-standing developer utilities that live outside the packaged `core/`, `gui/`, `cli/`, and `providers/` modules. Three groups:

- **`scripts/`** and **`tools/`** — maintained build/data-generation tooling (model capability database, semantic tag generation, viseme export, code-map generation).
- **Repo-root `check_*.py` / `diagnose_*.py` / `download_*.py` / `extract_*.py` / `test_*.py` / `verify_*.py`** — ad-hoc diagnostic and manual verification scripts kept from feature development. These are *not* pytest tests (the real suite lives in `tests/`, and `pytest.ini` restricts `testpaths` to it); most are run by hand with `python <file>.py` and several open Qt windows or hit live provider APIs.
- **`templates/`** and **`Sample/`** — data-only template module and a reference provider sketch.

---

### fetch_model_capabilities

**Path**: `scripts/fetch_model_capabilities.py` - 1147 lines
**Purpose**: Builds `data/model_capabilities.json`, the structured database of every provider model (id, display name, category, capabilities, limits, pricing, status, tags). OpenAI models are discovered live from the API with a hardcoded fallback list; Google and Anthropic models are compiled from curated documentation tables.
**Language**: Python

#### Module-Level Elements

| Element | Line | Type | Description |
|---------|------|------|-------------|
| PROJECT_ROOT | 27 | constant | Repo root, prepended to `sys.path` for imports |

#### Data Structures

| Name | Line | Type | Fields |
|------|------|------|--------|
| ModelCategory | 41 | `str` Enum | LLM, IMAGE_GEN, IMAGE_EDIT, VIDEO_GEN, AUDIO_TTS, AUDIO_STT, AUDIO_REALTIME, EMBEDDING, MODERATION, REASONING, CODE |
| ModelStatus | 56 | `str` Enum | PRODUCTION, PREVIEW, BETA, DEPRECATED, EXPERIMENTAL |
| ModelCapabilities | 66 | @dataclass | text/image/audio/video in-out flags, function_calling, structured_output, streaming, json_mode, system_prompt, transparent_background, reference_images, inpainting, outpainting, frame_interpolation, audio_generation |
| ModelLimits | 92 | @dataclass | context_window, max_output_tokens, max_images, supported_sizes, supported_aspects, max_duration_seconds, supported_resolutions |
| ModelPricing | 104 | @dataclass | input_per_million, output_per_million, per_image, per_second_video, currency |
| ModelInfo | 114 | @dataclass | id, display_name, provider, category, capabilities, limits, pricing, status, description, nickname, requires_api_key, requires_gcloud, knowledge_cutoff, release_date, aliases, tags |
| ProviderInfo | 135 | @dataclass | id, display_name, api_key_url, docs_url, models |

#### Class: ModelDatabase (line 145)

Top-level container (`last_updated`, `version`, `providers`) serialized to the output JSON.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| to_dict | 151 | public | `Dict[str, Any]` | Serialize the whole database (providers → models) for JSON output |
| _model_to_dict | 171 | private | `Dict[str, Any]` | Flatten one `ModelInfo`, unwrapping enum values and nested dataclasses via `asdict` |

#### Class: OpenAIModelFetcher (line 197)

Live fetch + categorization of OpenAI models. Carries class-level `PATTERNS` (regex → category) and `KNOWN_CAPABILITIES` (per-model context/output/vision/sizes overrides) tables spanning lines 197-424.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 426 | constructor | None | Store optional API key; client created lazily |
| _ensure_client | 431 | private | None | Lazily construct `openai.OpenAI`; raises `ImportError` with a pip hint if the SDK is missing |
| fetch_model_list | 440 | public | `List[str]` | `client.models.list()` → model IDs |
| categorize_model | 446 | public | `ModelCategory` | Regex-match the model ID against `PATTERNS`, defaulting to LLM |
| get_model_info | 457 | public | `ModelInfo` | Assemble capabilities, limits, status (preview/beta/exp from the ID), display name, and tags |
| _generate_display_name | 513 | private | `str` | Special-case names (DALL·E 3, GPT Image 1.5, Whisper…) else title-case the ID |
| _get_tags | 547 | private | `List[str]` | Derive tags such as fast/efficient/fastest/advanced/high-quality/web-search/realtime/research |
| fetch_all | 571 | public | `ProviderInfo` | Fetch (or fall back to the known list), drop fine-tuned + dated variants, build every `ModelInfo` |

#### Class: GoogleModelFetcher (line 617)

Curated `MODELS` table (lines 617-754) covering Gemini 3/2.5/2.0 LLMs, Gemini image models (incl. the "Nano Banana" nickname), Imagen, and Veo. A comment at lines 751-753 records that veo-3.0/2.0 were discontinued 2026-06-30 and legacy IDs are migrated in `core/video/config.py::_migrate_legacy_models`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| get_model_info | 756 | public | `ModelInfo` | Convert one curated dict into a `ModelInfo`, including video duration/resolution limits and gcloud requirement |
| fetch_all | 807 | public | `ProviderInfo` | Compile every entry in `MODELS` into the Google provider record |

#### Class: AnthropicModelFetcher (line 834)

Curated Claude model table (lines 834-960) with context/output limits, per-million pricing, knowledge cutoffs, and release dates.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| get_model_info | 962 | public | `ModelInfo` | Build a Claude `ModelInfo` (always text in/out + streaming + JSON mode; vision and pricing from the table) |
| fetch_all | 1012 | public | `ProviderInfo` | Compile all Claude models into the Anthropic provider record |

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| load_api_key | 1039 | public | `Optional[str]` | No | Read `{provider}_api_key` from the Windows-side config (via `/mnt/c/...`) then the Linux `~/.config/ImageAI/config.json` |
| main | 1066 | public | None | No | CLI entry: `--output`, `--providers`, `--verbose`; runs each fetcher, writes the JSON, prints a per-provider model-count summary |

---

### generate_tags

**Path**: `scripts/generate_tags.py` - 642 lines
**Purpose**: One-shot LLM pass that generates semantic metadata (tags, related styles/artists/moods, cultural keywords, description, era, popularity) for every prompt-builder item, writing `data/prompts/metadata.json`. Resumable — existing entries are skipped on re-run.
**Language**: Python

Module setup (lines 20-81) wires a timestamped `generate_tags_YYYYmmdd_HHMMSS.log` file handler plus stdout logging, hard-fails on missing `tqdm`/`litellm`, and installs SIGINT/SIGTERM handlers for graceful shutdown.

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| signal_handler | 70 | public | None | No | Ctrl+C / SIGTERM handler; sets the global `shutdown_requested` flag so the run saves progress |
| main | 446 | public | `int` | No | Arg parsing (`--test`, `--limit`, `--provider`, `--model`), loads existing metadata for resume, iterates categories with a tqdm progress bar, writes `data/prompts/metadata.json` |

#### Class: TagGenerator (line 84)

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 87 | constructor | None | Pick the model per provider/auth mode (Vertex AI `vertex_ai/gemini-1.5-flash` under gcloud auth, `gemini/gemini-2.0-flash-exp` for API keys, `gpt-5-chat-latest` for OpenAI), resolve auth, log project ID |
| _get_api_key | 151 | private | `Optional[str]` | Resolve an API key or a gcloud access token through `ConfigManager`, logging the auth mode and failure guidance |
| generate_metadata | 223 | public | `Optional[Dict]` | Call `litellm.completion` with retries; forces `temperature=1.0` for gpt-5/o1/o3, adds `vertex_project`/`vertex_location` for Vertex models, exponential backoff (5/10/20s) on 429 / RESOURCE_EXHAUSTED, falls back to stub metadata |
| _build_prompt | 292 | private | `str` | Category-specific prompt templates (artists, styles, mediums, and the remaining categories) requesting strict JSON |
| _parse_json_response | 391 | private | `Optional[Dict]` | Strip Markdown code fences then `json.loads`; returns None and logs on parse failure |
| _create_fallback_metadata | 425 | private | `Dict` | Minimal metadata derived from the item name when every LLM attempt fails |

---

### export_cached_visemes

**Path**: `scripts/export_cached_visemes.py` - 188 lines
**Purpose**: Manual export of cached mouth visemes into an Adobe Character Animator puppet folder (`Mouth/` PNGs + `manifest.txt` + a contact-sheet preview).
**Language**: Python

#### Module-Level Elements

| Element | Line | Type | Description |
|---------|------|------|-------------|
| CACHE_DIR | 17 | constant | `<repo>/cache/visemes` |
| VISEME_ORDER | 20 | constant | Character Animator viseme names in canonical order (Neutral, Ah, D, Ee, F, L, M, Oh, R, S, Uh, W-Oo, Smile, Surprised) |

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| find_latest_viseme_set | 26 | public | `dict` | No | Group `*_mouth_*.png` cache files by hash prefix and return the largest/newest complete set |
| export_visemes | 70 | public | `list` | No | Copy visemes into `<out>/Mouth/<Name>.png`, write `manifest.txt` with import instructions, optionally build the PSD/preview |
| create_simple_psd | 116 | public | None | No | PSD creation is not supported by `psd_tools`; instead renders a 4-column labelled preview grid (`preview_all_visemes.png`) |
| main | 157 | public | `int` | No | Resolve the output folder from `argv[1]` (default `cache/exported_puppet`), export, return 0/1 |

---

### generate_code_map (legacy generator)

**Path**: `tools/generate_code_map.py` - 237 lines
**Purpose**: Standalone AST-based generator that writes a *concise* `Docs/CodeMap.md` (structure tree with line counts, entry points, `core` re-exports, top-level symbol index). Superseded for day-to-day use by the `update-code-map` skill, which produces the detailed map, but retained as the tool-agnostic fallback referenced in AGENTS.md §12.
**Language**: Python

#### Module-Level Elements

| Element | Line | Type | Description |
|---------|------|------|-------------|
| REPO_ROOT | 23 | constant | Repository root (parent of `tools/`) |
| DOCS_PATH | 24 | constant | Output path `Docs/CodeMap.md` |
| EXCLUDE_DIRS | 26 | constant | Skipped directories (`.git`, `.venv`, `.venv_linux`, `__pycache__`, `Screenshots`, `Debug`, `.junie`, `.claude`) |
| EXCLUDE_FILES | 30 | constant | Explicit file exclusions |
| MAX_SYMBOL_FILES | 33 | constant | Cap of 60 files in the symbol index |
| MAX_SYMBOLS_PER_FILE | 34 | constant | Cap of 20 symbols per file |

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| list_source_files | 37 | public | `list[Path]` | No | Walk the repo collecting `.py`/`.md`/`.txt`/`.j2`, pruning excluded dirs |
| count_lines | 52 | public | `int` | No | Line count with encoding errors ignored; 0 on failure |
| tree_structure_with_counts | 60 | public | `str` | No | Render the directory tree with per-file line counts |
| walk | 63 | private (nested) | None | No | Recursive tree emitter inside `tree_structure_with_counts` |
| detect_primary_entries | 86 | public | `list[tuple[str, str]]` | No | Report which of `main.py`, `gui/__init__.py`, `cli/parser.py`, `cli/runner.py`, `providers/__init__.py` exist |
| summarize_core_exports | 103 | public | `list[str]` | No | Regex-parse `core/__init__.py` for single-line and parenthesized `from .mod import …` re-exports |
| parse_module_symbols | 146 | public | `tuple[list[str], list[str]]` | No | `ast.parse` a module and return its top-level classes and functions |
| collect_symbol_index | 163 | public | `list[tuple[str, list[str], list[str]]]` | No | Index `core`/`cli`/`providers`/`gui`, smallest files first, capped at `MAX_SYMBOL_FILES` |
| generate | 188 | public | `str` | No | Assemble the full Markdown document with a `YYYY-MM-DD HH:MM:SS` timestamp |
| main | 228 | public | `int` | No | Write `Docs/CodeMap.md` and print the path |

---

### templates (Gemini prompt templates)

**Path**: `templates/__init__.py` - 2098 lines
**Purpose**: Data-only module holding the built-in Gemini prompt templates used by the Templates tab and the Examples dialog. Nearly the entire file is one large literal list of `{name, template, defaults}` dicts; sibling packages `templates/layouts/` and `templates/video/` hold JSON layout and video templates.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_gemini_doc_templates | 9 | public | `List[Dict[str, Any]]` | No | Return the default template list (placeholder-slot prompts with per-slot defaults). Contains a stub hook that would merge extra templates parsed from `GEMINI_TEMPLATES_PATH` if that file exists — currently a no-op `pass` |

---

### check_avif_support

**Path**: `check_avif_support.py` - 99 lines
**Purpose**: Diagnostic that reports whether Pillow can read/write AVIF, prints per-platform install instructions for `pillow-avif-plugin`/`libavif`, lists all registered image formats, and optionally opens an AVIF file passed as `argv[1]`.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| check_avif_support | 13 | public | `bool` | No | Print the Pillow version, whether `.avif` is a registered extension, install guidance, and a grouped list of supported formats |

---

### check_durations

**Path**: `check_durations.py` - 33 lines
**Purpose**: Throwaway inspector for the debug project sidecar. Loads `imageai_current_project.json`, prints scene count, the unique set of `duration_sec` values and their distribution, the first ten scenes' text + duration, and the `llm_start_time` / `llm_end_time` metadata for the first five scenes.
**Language**: Python

No functions or classes — the whole file is top-level script body. The project path is hardcoded to the WSL repo location.

---

### diagnose_ollama

**Path**: `diagnose_ollama.py` - 66 lines
**Purpose**: Step-by-step diagnostic for Ollama model detection, written to chase a bug where the UI showed the hardcoded default list instead of the machine's installed models. Prints the default `LLM_PROVIDERS['ollama'].models`, the models returned by `fetch_ollama_models()`, the result of `update_ollama_models()`, what `get_provider_models('ollama')` finally returns, and a specific "is Dolphin present?" check.
**Language**: Python

No functions or classes — top-level script body only. Companions: `test_ollama.py` (connectivity + provider import) and `verify_ollama_ui.py` (dropdown wiring).

---

### diagnose_qt_multimedia

**Path**: `diagnose_qt_multimedia.py` - 237 lines
**Purpose**: Cross-machine Qt6 multimedia diagnostic built to explain why `QMediaPlayer` hangs on some Linux systems. Dumps platform/Python info, GStreamer and Qt plugin presence, audio-stack state, then attempts a guarded `QMediaPlayer` construction under a SIGALRM timeout — deliberately skipping `QAudioOutput`, which is the known hang.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| run_command | 13 | public | `tuple[str, int]` | No | Run a shell/argv command with a 5s timeout, returning stdout and return code (or `TIMEOUT`/`ERROR: …`) |
| check_file_exists | 25 | public | `str` | No | `✓ EXISTS` / `✗ MISSING` marker for a path |
| main | 29 | public | None | No | Emit the full diagnostic report, ending with the timeout-guarded `QMediaPlayer` creation test |
| timeout_handler | 199 | private (nested) | None | No | SIGALRM handler inside `main` that raises `TimeoutError` if `QMediaPlayer()` blocks past 5 seconds |

---

### download_models

**Path**: `download_models.py` - 161 lines
**Purpose**: Command-line downloader for Local Stable Diffusion checkpoints, backed by `providers.model_info.ModelInfo` and `huggingface_hub`.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| list_models | 9 | public | None | No | Print installed models with on-disk size, then the remaining `ModelInfo.POPULAR_MODELS` with a ⭐ marker for recommended entries |
| download_model | 27 | public | None | No | `snapshot_download` a model into the cache; warns and prompts when no HuggingFace token is present |
| login_huggingface | 71 | public | None | No | Hidden-input (`getpass`) token entry, validated with `whoami` and persisted via `HfFolder.save_token`; shows the current login first |
| main | 121 | public | None | No | Arg parsing and dispatch across list / download / `login` |

---

### download_social_icons

**Path**: `download_social_icons.py` - 173 lines
**Purpose**: One-time asset fetcher that populates `assets/icons/social/` with platform icons from the Simple Icons CDN, falling back to PNG sources and finally to generated letter placeholders.
**Language**: Python

#### Module-Level Elements

| Element | Line | Type | Description |
|---------|------|------|-------------|
| PLATFORM_ICONS | 19 | constant | Platform → Simple Icons SVG CDN URL (Apple Podcasts, Bandcamp, Discord, Instagram, Spotify, TikTok, X, YouTube, …) |
| PNG_ICONS | 54 | constant | PNG fallback URLs for platforms whose SVG fetch may fail |

The module also creates `assets/icons/social/` at import time (lines 12-13).

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| download_icon | 69 | public | `bool` | No | Fetch one icon URL and write `<platform>.<svg\|png>`; returns success |
| main | 103 | public | None | No | Download all SVGs (0.1s CDN courtesy delay), retry failures as PNG, print a summary, generate placeholders for whatever is still missing |
| create_placeholder_svg | 157 | public | None | No | Emit a grey-circle SVG with the platform's first letter for each missing platform |

---

### extract_all_last_frames

**Path**: `extract_all_last_frames.py` - 223 lines
**Purpose**: Batch-extracts the final frame of every `scene_*.mp4` clip in an ImageAI video project's `clips/` folder — used to seed continuity references for Veo clip extension. Requires `opencv-python` and exits with an install hint if missing.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| extract_scene_index_from_filename | 25 | public | `Optional[int]` | No | Parse the scene index out of names like `scene_12_20251017_135633.mp4` |
| extract_last_frame | 48 | public | `bool` | No | Seek to the last readable frame with OpenCV and write it as an image; `force` overwrites an existing output |
| find_video_clips | 102 | public | `List[Tuple[int, Path]]` | No | Glob `clips/scene_*.mp4`, log directory contents for debugging, return `(scene_index, path)` sorted by index |
| main | 144 | public | None | No | Validate the project folder from `argv[1]`, extract every clip's last frame, print a per-clip and overall summary |

---

### main_original (pre-refactor monolith)

**Path**: `main_original.py` - 2646 lines
**Purpose**: Historical snapshot of ImageAI when the entire application — config, key resolution, gcloud auth, provider clients, CLI, and the full PySide6 GUI — lived in a single file (`__version__ = "0.7.0"`, line 33). Superseded by `main.py` + `core/` + `gui/` + `cli/` + `providers/`. **Reference only — do not extend.** Useful for archaeology when tracking down where a behaviour originated.
**Language**: Python

#### Module-Level Elements

| Element | Line | Type | Description |
|---------|------|------|-------------|
| GCLOUD_AVAILABLE | 26 | constant | `True` branch — set when `google.cloud.aiplatform` + `google.auth` import cleanly |
| GCLOUD_AVAILABLE | 31 | constant | `False` branch — set in the `except ImportError` fallback |
| PROVIDER_NAME | 35 | constant | Module-level active provider, mutated at runtime by CLI and GUI |
| APP_NAME | 67 | constant | `"ImageAI"` |
| DEFAULT_MODEL | 68 | constant | `"gemini-2.5-flash-image-preview"` — the now-deprecated preview model (see AGENTS.md §9) |
| README_PATH | 151 | constant | Path to `README.md`, used for the `--help-api-key` text |
| PROVIDER_NAME | 841 | constant | `global` re-binding inside `run_cli` |

#### Functions — configuration, keys, and help text

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| get_api_key_url | 70 | public | `str` | No | Provider → API-key console URL |
| user_config_dir | 81 | public | `Path` | No | Platform-specific config directory (`%APPDATA%`, `~/Library/Application Support`, `~/.config`) |
| config_path | 95 | public | `Path` | No | `<config dir>/config.json` |
| load_config | 101 | public | `dict` | No | Read the JSON config, empty dict on any failure |
| save_config | 111 | public | None | No | Write the config JSON |
| details_path | 120 | public | `Path` | No | Path of the last-generation details record |
| save_details_record | 126 | public | None | No | Persist the details of the most recent generation |
| read_key_file | 135 | public | `Optional[str]` | No | Read and strip an API key from a file |
| read_readme_text | 154 | public | `str` | No | Load `README.md` text for in-app help |
| extract_api_key_help | 178 | public | `str` | No | Slice the API-key setup section out of the README Markdown |
| resolve_api_key | 209 | public | `Optional[str]` | No | Layered resolution: CLI key > key file > config > environment |
| store_api_key | 239 | public | None | No | Persist a key into the per-provider config |
| default_model_for_provider | 259 | public | `str` | No | Provider → default model |
| default_model_for_provider | 887 | private (nested) | `str` | No | Shadowing helper defined inside `run_cli` |

#### Functions — gcloud auth and generation

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| find_gcloud_command | 269 | public | `Optional[str]` | No | Locate the `gcloud` executable across platforms and common install paths |
| get_gcloud_project_id | 351 | public | `Optional[str]` | No | Read the active project from `gcloud config` |
| check_gcloud_auth_status | 378 | public | `tuple` | No | Report whether Application Default Credentials are usable, with remediation text |
| make_client | 437 | public | client | No | Build the Google GenAI or OpenAI client for the chosen provider and auth mode |
| generate_any | 500 | public | `tuple[list, list]` | No | Provider-agnostic generation returning `(texts, images)` |

#### Functions — image output, sidecars, and history

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| images_output_dir | 573 | public | `Path` | No | Directory generated images are auto-saved to |
| sidecar_path | 580 | public | `Path` | No | `.json` sidecar path for an image |
| write_image_sidecar | 585 | public | None | No | Write prompt/provider/model metadata beside the image |
| detect_image_extension | 595 | public | `str` | No | Sniff PNG/JPEG/GIF/WebP from the leading bytes |
| sanitize_stub_from_prompt | 611 | public | `str` | No | Turn a prompt into a safe, length-capped filename stub |
| auto_save_images | 642 | public | `list` | No | Save every returned image using the prompt-derived stub |
| read_image_sidecar | 656 | public | `Optional[dict]` | No | Load an image's sidecar metadata |
| scan_disk_history | 666 | public | `list[Path]` | No | List generated images newest-first, capped at `max_items` |
| find_cached_demo | 678 | public | `Optional[Path]` | No | For a built-in example prompt, find the newest previously generated image whose sidecar matches prompt + provider |
| get_gemini_doc_templates | 706 | public | `list` | No | In-file copy of the template list later extracted to `templates/__init__.py` |

#### Functions — CLI and entry point

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| run_cli | 836 | public | `int` | No | Whole CLI flow: provider/auth selection, `--help-api-key`, key storage, key test, generate, save |
| build_arg_parser | 2612 | public | `ArgumentParser` | No | Defines `-k/-K/-s/-t/-p/-m/-o`, `--provider`, `--auth-mode`, `-H/--help-api-key` |
| main | 2628 | public | `int` | No | No args → launch the GUI; any args (including `-h`) → `run_cli` |

#### Class: GenWorker (line 955)

`QObject` worker moved onto a `QThread` so generation never blocks the UI. Signal: `finished(list, list, str)` — texts, image bytes, error string.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 958 | constructor | None | Capture api_key, model, prompt, normalized provider, auth mode |
| run | 966 | public | None | Build the client, call `generate_any`, emit results or the exception text |

#### Class: ExamplesDialog (line 975)

Modal "Examples & Templates" browser. Class-level `EXAMPLES` (8 showcase prompts) and `TEMPLATES` (photorealistic product shot, character concept art, landscape matte painting, isometric game asset, flat icon/logo) live at lines 975-1010.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 1011 | constructor | None | Build the examples list, template picker, dynamic field form, and preview pane |
| _current_template | 1087 | private | `Tuple[str, str]` | Currently selected template record |
| _rebuild_template_form | 1094 | private | None | Regenerate one input row per `[placeholder]` slot in the template |
| _collect_template_fields | 1149 | private | `dict` | Read the current field values |
| _assemble_preview | 1156 | private | `str` | Substitute fields into the template for the live preview |
| _autosave_template_state | 1201 | private | None | Persist in-progress template field values to config |
| _on_field_changed | 1220 | private | None | Field-edit slot → refresh preview + autosave |
| _assemble_from_template | 1226 | private | `Optional[str]` | Produce the final prompt text from template + fields |
| _on_insert | 1246 | private | None | Accept the dialog with the chosen example or assembled template |
| selected_text | 1293 | public | `Optional[str]` | The text the caller should insert into the prompt box |

#### Class: MainWindow (line 1297)

The original single-class `QMainWindow` carrying all four tabs (Generate, Templates, Settings, Help) plus History — the ancestor of today's `gui/main_window.py`.

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| __init__ | 1298 | constructor | None | Load config, resolve the provider/key, build tabs and menu |
| _init_menu | 1369 | private | None | Menu bar construction |
| _init_generate | 1376 | private | None | Generate tab: prompt box, model picker, generate button, image view |
| _init_templates | 1456 | private | None | Templates tab UI |
| _tmpl_current_template | 1520 | private | `Tuple[str, str]` | Selected template on the Templates tab |
| _tmpl_rebuild_template_form | 1527 | private | None | Rebuild the placeholder field form |
| _tmpl_collect_fields | 1590 | private | `dict` | Collect Templates-tab field values |
| _tmpl_assemble_preview | 1597 | private | `str` | Live preview of the substituted template |
| _tmpl_autosave_template_state | 1637 | private | None | Autosave Templates-tab state |
| _tmpl_on_field_changed | 1655 | private | None | Field-edit slot for the Templates tab |
| _on_insert_template_to_prompt | 1661 | private | None | Push the assembled template into the Generate tab prompt |
| _init_settings | 1704 | private | None | Settings tab: provider, auth mode, key entry/browse, gcloud status |
| _toggle_auto_copy | 1822 | private | None | Toggle auto-copy of generated text |
| _browse_key | 1834 | private | None | File dialog for a key file |
| _save_and_test | 1843 | private | None | Persist the key then run a live key test |
| _open_api_key_page | 1878 | private | None | Open the provider's API-key console in a browser |
| _on_provider_changed | 1884 | private | None | Re-resolve key/model and update UI when the provider changes |
| _on_auth_mode_changed | 1929 | private | None | Switch between API-key and gcloud auth |
| _check_gcloud_status | 1978 | private | None | Query and display ADC status |
| _open_gcloud_install_page | 2018 | private | None | Open the gcloud SDK install docs |
| _open_gcloud_console | 2025 | private | None | Open the Google Cloud console |
| _show_gcloud_login_help | 2032 | private | None | Show the `gcloud auth application-default login` instructions |
| _update_auth_ui_visibility | 2056 | private | None | Show/hide auth widgets per provider and mode |
| _init_help | 2092 | private | None | Help tab rendered from the README |
| _init_history | 2120 | private | None | History pane backed by the on-disk image scan |
| _refresh_history_list | 2148 | private | None | Re-scan generated images into the list |
| _on_history_selection_changed | 2161 | private | None | Show the selected image and its sidecar metadata |
| _on_history_item_double_clicked | 2240 | private | None | Restore prompt/settings from a history entry |
| _restore_template_from_context | 2261 | private | None | Rehydrate template name + field values from stored context |
| _history_save_as | 2318 | private | None | Save the selected history image elsewhere |
| _open_examples | 2346 | private | None | Launch `ExamplesDialog` and insert the result |
| _mark_dirty | 2375 | private | None | Flag unsaved prompt/template edits |
| _on_generate | 2387 | private | None | Validate inputs, check the demo cache, spin up `GenWorker` on a `QThread` |
| _on_generated | 2468 | private | None | Worker-completion slot: display text/images, auto-save with sidecars, surface errors |
| resizeEvent | 2563 | public (Qt override) | None | Rescale the preview proportionally on resize |
| closeEvent | 2576 | public (Qt override) | None | Persist window/config state before exit |
| _save_image_as | 2595 | private | None | Save-as for the currently displayed image |

---

### test_aspect_ratio (standalone logic check)

**Path**: `test_aspect_ratio.py` - 59 lines
**Purpose**: Self-contained sanity check of the closest-supported-aspect-ratio algorithm. Carries its own copy of the per-provider ratio tables and prints results for seven cases (OpenAI 800x600, 1920x1080, 500x800, 1024x1024, 1600x900; Stability 800x600, 600x800). Comments at lines 9-11 record that Gemini supports only `1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9` — `2:1` and `1:2` are invalid.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| find_closest_aspect_ratio | 4 | public | `str` | No | Pick the provider-supported ratio with the smallest absolute difference from `width/height`, defaulting to `"1:1"` |
| parse_ratio | 21 | private (nested) | `float` | No | `"16:9"` → `1.777…` |

---

### test_auth_mode

**Path**: `test_auth_mode.py` - 66 lines
**Purpose**: Prints the raw `auth_mode` value from `ConfigManager` and its normalized form, mirroring the legacy/display-value handling in `main_window.py` (`api_key`/`API Key` → `api-key`, `Google Cloud Account` → `gcloud`), then reports which auth path the reference-generation dialog will take.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_auth_mode | 12 | public | None | No | Load config, normalize `auth_mode`, print the resolved authentication path |

---

### test_enhanced_dialog_focus

**Path**: `test_enhanced_dialog_focus.py` - 61 lines
**Purpose**: Manual GUI check that `EnhancedPromptDialog` opens with focus in the prompt text box and the right default button. Constructs a real `QApplication` and shows the dialog, so it needs a display.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| main | 14 | public | None | No | Build `QApplication` + `ConfigManager`, open the dialog with a sample prompt, assert focus/default-button state, run the event loop |
| on_prompt_enhanced | 52 | private (nested) | None | No | Signal handler printing the enhanced prompt returned by the dialog |

---

### test_imagen_customization

**Path**: `test_imagen_customization.py` - 450 lines
**Purpose**: Live exercise of `providers.imagen_customization.ImagenCustomizationProvider` (Imagen 3 Customization API) with 1-4 reference images. Requires gcloud ADC, a configured project, the Vertex AI API enabled, and `google-cloud-aiplatform`; the module docstring (lines 1-24) lists the full prerequisite and usage matrix.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_single_reference | 38 | public | `bool` | No | Generate from a single subject reference image |
| test_two_references | 108 | public | `bool` | No | Generate from two reference images |
| test_subject_with_style | 189 | public | `bool` | No | Combine a subject reference with a style reference |
| test_custom_references | 269 | public | `bool` | No | Use `--ref1`..`--ref4` from the command line, validating that every path exists before calling the provider |
| main | 377 | public | `int` | No | Arg parsing and dispatch across the four scenarios |

---

### test_layout_phase1

**Path**: `test_layout_phase1.py` - 236 lines
**Purpose**: Phase 1 verification for the publication layout engine (core integration and foundation) — imports, font manager, config wiring, template loading, and a basic page render.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_imports | 36 | public | `bool` | No | Confirm `core.layout` exports (`FontManager`, `LayoutEngine`, `load_template_json`, `PageSpec`, `DocumentSpec`, `TextBlock`, `ImageBlock`) import cleanly |
| test_font_manager | 49 | public | `bool` | No | Initialize `FontManager` and enumerate discovered fonts |
| test_config_integration | 76 | public | `bool` | No | Verify layout settings round-trip through `ConfigManager` |
| test_template_loading | 100 | public | `bool` | No | Load a layout template JSON and validate its shape |
| test_basic_rendering | 139 | public | `bool` | No | Render a page containing a text block and an image block |
| main | 190 | public | `int` | No | Run all five checks and report pass/fail |

---

### test_layout_phase2

**Path**: `test_layout_phase2.py` - 369 lines
**Purpose**: Phase 2 verification for the layout engine — advanced text rendering (hyphenation, justification), image processing effects, template variable substitution, and smart layout algorithms.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_advanced_text_rendering | 39 | public | `bool` | No | `TextLayoutEngine` with hyphenation and justified text |
| test_image_processing | 87 | public | `bool` | No | `ImageProcessor` rounded corners and effects |
| test_template_variables | 141 | public | `bool` | No | `TemplateEngine` variable substitution |
| test_layout_algorithms | 202 | public | `bool` | No | `LayoutAlgorithms` automatic block placement |
| test_integrated_rendering | 250 | public | `bool` | No | Full-page render combining styled text and images |
| main | 323 | public | `int` | No | Run all five checks and report pass/fail |

---

### test_ollama

**Path**: `test_ollama.py` - 202 lines
**Purpose**: Ollama connectivity and model-detection check, intended to be run on the machine where Ollama itself is running.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_ollama_connection | 16 | public | `Optional[dict]` | No | `GET {endpoint}/api/tags` with a 5s timeout; prints a `systemctl status ollama` hint on connection failure |
| list_models | 36 | public | `list` | No | Print each installed model with its details |
| test_provider_import | 68 | public | `bool` | No | Verify the Ollama provider module imports and constructs |
| test_llm_models | 103 | public | `bool` | No | Check what `core.llm_models` reports for Ollama |
| search_for_dolphin | 138 | public | `list` | No | Filter for Dolphin models and print `ollama pull` instructions when none are found |
| main | 159 | public | `int` | No | Run the sequence end to end |

---

### test_phase3_templates

**Path**: `test_phase3_templates.py` - 296 lines
**Purpose**: Phase 3 verification for the layout template management system — discovery, schema validation, preview generation, categories/search, inheritance, and user templates.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_template_discovery | 27 | public | `TemplateManager` | No | Discover bundled templates and report the count |
| test_schema_validation | 52 | public | `bool` | No | Confirm invalid templates raise `ValidationError` |
| test_preview_generation | 82 | public | `bool` | No | Render a template preview image |
| test_categories_and_search | 104 | public | `bool` | No | Exercise category listing and template search |
| test_template_inheritance | 146 | public | `bool` | No | Verify child templates inherit and override parent fields |
| test_user_templates | 217 | public | `bool` | No | Round-trip a user-defined template through the manager |
| main | 247 | public | `int` | No | Run the six checks in order, threading the shared manager through |

---

### test_prompt_dialog_focus

**Path**: `test_prompt_dialog_focus.py` - 59 lines
**Purpose**: Manual GUI check that `PromptGenerationDialog` opens with focus in the input box and `generate_btn` as the default button. Sibling of `test_enhanced_dialog_focus.py`; needs a display.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| main | 15 | public | None | No | Build `QApplication` + `ConfigManager`, open the dialog, assert focus and default-button state, run the event loop |
| on_prompt_selected | 50 | private (nested) | None | No | Signal handler printing the prompt the dialog returned |

---

### test_scaling

**Path**: `test_scaling.py` - 82 lines
**Purpose**: Interactive harness for `ImageCropDialog`. Builds a 1024x1024 gradient `QImage` in memory and offers two buttons that open the crop dialog against different target sizes, reporting the resulting dimensions.
**Language**: Python

> **Note**: this script calls `app.exec()` and blocks. It is one of the root-level scripts that caused bare `pytest` to hang before `pytest.ini` pinned `testpaths` to `tests/`.

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_crop_dialog | 18 | public | None | No | Create the gradient test image and a window with two crop-test buttons, then run the Qt event loop |
| show_crop | 48 | private (nested) | None | No | Open `ImageCropDialog` targeting 512x768 and report the crop result |
| show_crop2 | 62 | private (nested) | None | No | Open `ImageCropDialog` targeting 800x600 and report the crop result |

---

### test_tempo_descriptors

**Path**: `test_tempo_descriptors.py` - 159 lines
**Purpose**: Demonstrates that `core.video.video_prompt_generator` lets the LLM pick tempo-appropriate motion descriptors dynamically instead of using hardcoded BPM ranges. Runs `VideoPromptGenerator` over several `VideoPromptContext` cases at different BPMs (e.g. 60 BPM melancholic streetlight scene).
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_tempo_descriptors | 19 | public | None | No | Build the BPM test cases, generate prompts for each, and print the descriptors the LLM chose |

---

### test_veo_batching

**Path**: `test_veo_batching.py` - 177 lines
**Purpose**: Verifies Veo 3.1 scene batching — that short scenes are grouped into 8-second generation batches, that batch assignments survive project serialization, and that per-scene batch lookup works.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_batching_logic | 17 | public | `bool` | No | Build sample `Scene`s of mixed durations and check `EnhancedStoryboardGenerator`'s batching |
| test_project_serialization | 72 | public | `bool` | No | Round-trip a `VideoProject` and confirm batch metadata is preserved |
| test_batch_lookup | 114 | public | `bool` | No | Resolve which batch a given scene belongs to |
| main | 151 | public | `int` | No | Run the three checks and report pass/fail |

---

### test_veo_duration_prompts

**Path**: `test_veo_duration_prompts.py` - 187 lines
**Purpose**: Confirms Veo 3.x duration validation (only 8-second clips are accepted — a 4-second `VeoGenerationConfig` must raise `ValueError`) and that prompts for short scenes carry correct in-clip time markers.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| test_duration_validation | 12 | public | `bool` | No | Assert `VeoGenerationConfig` rejects non-8-second durations for VEO_3_GENERATE and VEO_3_1_GENERATE |
| test_short_scene_prompts | 64 | public | `bool` | No | Generate prompts for very short scenes (down to 0.2s) and check the emitted time markers |
| test_batched_scene_prompts | 125 | public | `bool` | No | Check prompt generation for multi-scene batches packed into one 8-second clip |
| main | 157 | public | `int` | No | Run the three checks and report pass/fail |

---

### verify_ollama_ui

**Path**: `verify_ollama_ui.py` - 117 lines
**Purpose**: Quick confirmation that Ollama is wired into every UI dropdown — fetches models via `fetch_ollama_models()` / `update_ollama_models()` and verifies the provider appears everywhere it should. Prints `systemctl status ollama` and `ollama pull` guidance when nothing is detected.
**Language**: Python

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| verify_ollama_integration | 13 | public | `bool` | No | Run the model-detection and dropdown-presence checks, printing a pass/fail report |

---

### midjourney_provider (sample)

**Path**: `Sample/midjourney_provider.py` - 99 lines
**Purpose**: Reference sketch (MIT, not wired into `providers/`) for a **manual-handoff** Midjourney provider: no automation, no bots, no API keys, so it stays inside Midjourney's ToS. It builds an `/imagine` slash command, copies it to the clipboard, and opens the target Discord channel for the user to paste.
**Language**: Python

#### Module-Level Elements

| Element | Line | Type | Description |
|---------|------|------|-------------|
| ProviderID | 10 | constant | `"midjourney_manual"` |
| ProviderDisplayName | 11 | constant | `"Midjourney (Manual Handoff)"` |
| ProviderGroup | 12 | constant | `"cloud"` |
| MJModel | 14 | type alias | `Literal["v7", "v6.1", "niji-6"]` |

#### Data Structures

| Name | Line | Type | Fields |
|------|------|------|--------|
| MidjourneyParams | 17 | @dataclass | prompt, negative_prompt, image_urls, aspect_ratio, stylize, quality, seed, chaos, weird, tile, raw, niji, model |

#### Functions

| Function | Line | Scope | Returns | Async | Description |
|----------|------|-------|---------|-------|-------------|
| _bool_flag | 32 | private | `List[str]` | No | Emit `--name` when a boolean flag is set, else nothing |
| build_slash_command | 35 | public | `str` | No | Assemble `/imagine prompt: …` with image URLs, `--no`, `--ar`, `--s`, `--q`, `--seed`, `--chaos`, `--weird`, `--v`, and the boolean flags |
| copy_to_clipboard | 57 | public | None | No | Platform-specific clipboard write (`clip` / `pbcopy` / `xclip`), reporting failures rather than raising |
| open_discord_channel | 69 | public | None | No | Open `https://discord.com/channels/{server_id}/{channel_id}` in a new browser tab |

#### Class: MidjourneyManualProvider (line 73)

Class attributes `id`, `name`, and `group` mirror the module-level provider constants (lines 74-76).

| Method | Line | Type | Returns | Description |
|--------|------|------|---------|-------------|
| submit | 78 | public | `dict` | Build the slash command from `**kwargs`, copy it to the clipboard, open the Discord channel, and return `{mode, slash_command, note}` telling the user to paste and press Enter |

A `__main__` block (lines 89-99) demos the flow with a sample 16:9 `v7` prompt.

---

## Cross-File Dependencies

All references below were verified by `grep -n` against the working tree (or come from the symbol inventory). Import counts exclude `tests/` and the loose root-level `test_*.py`/diagnostic scripts unless stated.

### Layering Overview

```
                        ┌──────────────────────────────┐
                        │  main.py (entry point)       │
                        │  main.py:174 from gui import │
                        │  main.py:188 from cli import │
                        └──────┬────────────────┬──────┘
                               │                │
             ┌─────────────────▼──┐          ┌──▼─────────────────────┐
             │  cli/             │          │  gui/  (PySide6)        │
             │  parser · runner  │          │  main_window · workers  │
             │  commands/        │          │  video/ · layout/ ·     │
             │                   │          │  styles/ · common/      │
             └────────┬──────────┘          └───────┬─────────────────┘
                      │                             │
                      └──────────┬──────────────────┘
                                 ▼
                 ┌───────────────────────────────────┐
                 │  core/   (business logic)         │
                 │  config · constants · utils ·     │
                 │  styles/ · layout/ · video/ ·     │
                 │  reference/ · llm_models          │
                 └───────┬───────────────────┬───────┘
                         │                   │
                         ▼                   ▼
           ┌──────────────────────┐  ┌──────────────────────┐
           │  providers/          │  │ core/model_registry/ │
           │  base · google ·     │  │ client.py (+ bundled │
           │  openai · stability ·│  │ fallback snapshot)   │
           │  local_sd · ollama · │  └──────────────────────┘
           │  midjourney · video/ │
           └──────────────────────┘
                         │
                         ▼
                 external SDKs / HTTP
```

**Rule of thumb, as actually enforced by the code:** `gui/*` may import `core/*` and `providers/*`; `core/*` may import `providers/*`; `providers/*` may import a narrow slice of `core/*` (config, security, constants, image utils) — but nothing under `core/` or `providers/` imports `gui/` except one deliberate exception (see *Layering Exceptions* below).

### Module Dependency Matrix (edge counts)

| From ↓ / To → | core | core/video | core/layout | core/styles | providers | gui | gui/common | gui/video | gui/layout | cli |
|---|---|---|---|---|---|---|---|---|---|---|
| `main.py` | 1 | – | – | – | – | 2 | – | – | – | 1 |
| `cli/` | 5 | – | – | 2 | 1 | – | – | – | – | – |
| `cli/commands/` | 1 | 5 | 4 | 7 | 1 | – | – | – | – | 2 |
| `core/` (top) | – | – | – | – | – | – | – | – | – | – |
| `core/video/` | 16 | – | – | – | 1 | – | – | – | – | – |
| `core/layout/` | 12 | – | – | 1 | – | 1 | – | – | – | – |
| `core/styles/` | 6 | 1 | – | – | – | – | – | – | – | – |
| `providers/` | 10 | – | – | – | – | – | – | – | – | – |
| `gui/` (top) | 40 | 3 | 1 | 1 | 14 | – | 11 | 1 | 1 | – |
| `gui/video/` | 26 | 94 | – | 1 | 4 (+2 `providers/video`) | 6 | 39 | – | – | – |
| `gui/layout/` | 9 | – | 41 | – | – | 3 | 2 | – | – | – |
| `gui/styles/` | 1 | – | – | 5 | – | 2 | 1 | – | – | – |
| `utils/` | 7 | – | – | – | – | – | – | – | – | – |

`core/` never imports `core/video`, `core/layout`, or `gui/` at the top level — the only outbound edge from top-level `core/` is `core/llm_models.py:15 → core/model_registry`.

### Module Dependencies

#### `main.py` — 210 lines (entry point)
**Imports/Uses**:
- `core.logging_config` — `main.py:120` `setup_logging()`, called before anything else so all later errors land in the session log.
- `gui.launch_gui` — `main.py:174` (no-args default path) and `main.py:196` (explicit `--gui`); both guarded by `try/except ImportError` so a missing PySide6 degrades to CLI help.
- `cli.build_arg_parser`, `cli.run_cli` — `main.py:188`, dispatched at `main.py:204`.

**Imported By**: nothing (top of the graph).

#### `cli/` — `cli/__init__.py`, `cli/parser.py`, `cli/runner.py` (569 lines), `cli/commands/`
**Imports/Uses**:
- `cli/__init__.py:3-4` re-exports `build_arg_parser` (from `.parser`) and `run_cli` (from `.runner`).
- `cli/parser.py:4` — `core.constants` (`VERSION`, `__author__`, `__email__`, `__copyright__`) for `--version`/help text.
- `cli/runner.py:7` — `core` package facade: `ConfigManager`, `get_api_key_url`, `sanitize_filename`, `read_key_file`.
- `cli/runner.py:8` — `core.utils` (`read_readme_text`, `extract_api_key_help`, used by `--help-api-key` at `cli/runner.py:208-210`).
- `cli/runner.py:9` — `core.lyrics_to_prompts` (`LyricsToPromptsGenerator`, `load_lyrics_from_file`).
- `cli/runner.py:10` — `core.llm_models.resolve_model` (used at `cli/runner.py:99`).
- `cli/runner.py:11` — `providers.get_provider`, `providers.preload_provider`.
- Lazy sub-command dispatch: `cli/runner.py:220,223,226` → `cli.commands.layout`; `cli/runner.py:231` → `cli.commands.video`; `cli/runner.py:240` → `cli.commands.style`.
- `cli/runner.py:373,383` — `core.styles` (`StyleStore`, `apply_style`) and `core.styles.analyzer.build_completion_fn`.

**Imported By**: `main.py:188`; `cli/commands/layout.py:7` and `cli/commands/video.py:10` both import `resolve_api_key` back out of `cli/runner.py` (the one intra-package cycle, broken by being a module-level function import, not a package import).

#### `cli/commands/`
- `cli/commands/layout.py:7-11` — `cli.runner.resolve_api_key`, `core.layout` (`designer`, `project_io`, `styles`), `core.layout.models` (`DocumentSpec`, `PageSpec`, `Region`), `core.layout.page_sizes`, `providers.get_provider`; lazily `core.styles` at `:129,153` and `core.layout.qt_renderer` at `:220` (Qt only loaded when exporting).
- `cli/commands/video.py:9-10` — `core.sanitize_filename`, `cli.runner.resolve_api_key`; lazily `core.styles` (`:32,264`), `core.video.omni_client` (`:57,134` — `OmniGenerationConfig`, `OmniClient`), `core.video.veo_client` (`:92,105,160` — `VeoModel`, `VeoGenerationConfig`, `VeoClient`).
- `cli/commands/style.py:8-10` — `core.styles.analyzer` (`StyleAnalysisError`, `StyleAnalysisService`), `core.styles.models` (`Style`, `StyleDescriptor`), `core.styles.store` (`StyleStore`, `EXEMPLAR_DEFAULT_CAP`).

#### `core/` (package facade) — `core/__init__.py`
**Re-exports** (this is the import surface everything else uses):
- `core/__init__.py:3` — `ConfigManager`, `get_api_key_url` from `.config`.
- `core/__init__.py:4-16` — `APP_NAME`, `VERSION`, `DEFAULT_MODEL`, `DEFAULT_PROVIDER`, `PROVIDER_MODELS`, `PROVIDER_KEY_URLS` from `.constants`.
- `core/__init__.py:17-32` — `sanitize_filename`, `read_key_file`, `images_output_dir`, `sidecar_path`, `write_image_sidecar`, `read_image_sidecar`, `detect_image_extension`, `sanitize_stub_from_prompt`, `auto_save_images`, `scan_disk_history`, `find_cached_demo`, `default_model_for_provider` from `.utils`.

**Imported By** (top fan-in, non-test): `core/config.py` is imported by 26 non-test modules; `core/constants.py` by 19; `core/utils.py` by 8 (`cli/runner.py:8`, `gui/main_window.py:56-61`, `gui/workers.py:8`, `gui/video/workspace_widget.py`, `gui/video/video_project_tab.py:1881`, `utils/recover_reference_metadata.py:24`, `utils/update_reference_metadata.py:21`).

#### `core/config.py` — 381 lines
**Imports/Uses**: `core/config.py:10` `.constants` (`APP_NAME`, `PROVIDER_KEY_URLS`); `core/config.py:11` `.security.secure_storage`; lazily `core/config.py:130` `.gcloud_utils.find_gcloud_command`.
**Imported By** (26 non-test modules), notably: `core/__init__.py:3`, `core/utils.py`, `core/prompt_enhancer_llm.py`, `core/layout/template_manager.py`, `core/video/ffmpeg_utils.py`, `core/video/prompt_engine.py`, `core/video/veo_client.py`, `providers/google.py:220`, `gui/__init__.py`, `gui/workers.py:7`, `gui/prompt_builder.py`, `gui/wikimedia_search_dialog.py`, `gui/video/video_project_tab.py:18`, `gui/video/workspace_widget.py:32`, `gui/layout/{export_dialog,image_history_dialog,inspector_widget,text_gen_dialog}.py`, and all five `utils/*.py` scripts.

#### `core/llm_models.py` — 333 lines
**Imports/Uses**: `core/llm_models.py:15` — `core.model_registry` (`FALLBACK_PATH`, `resolve as _registry_resolve`, `RegistryError`); `requests` for the Ollama probe.
**Imported By** (21 non-test modules): `cli/runner.py:10`; `core/lyrics_to_prompts.py:13`; `core/prompt_enhancer_llm.py:12`; `core/styles/analyzer.py:216,247`; `core/layout/designer.py:313`; `core/font_generator/glyph_identifier.py:150`; `core/video/{config.py:10, end_prompt_generator.py:12, omni_client.py:33, prompt_engine.py:18, scene_suggester.py:15, style_analyzer.py:51}`; `gui/main_window.py:9`; `gui/workers.py:257`; `gui/prompt_generation_dialog.py:515`; `gui/prompt_question_dialog.py`; `gui/styles/style_manager_dialog.py`; `gui/layout/{designer_panel.py, text_gen_dialog.py}`; `gui/video/workspace_widget.py:47`.

#### `core/model_registry/`
**Imports/Uses**: `core/model_registry/__init__.py:26-27` — `.client` (vendored ChameleonLabs registry client) and `RegistryError`; stdlib `urllib.request` only (`core/model_registry/client.py:29`) — no third-party deps.
**Imported By**: only `core/llm_models.py:15`. Every other module reaches the registry through `resolve_model()` / `get_provider_models()`, which is the enforcement point for the "no hardcoded model IDs" rule.

#### `providers/` — `providers/__init__.py` (200 lines)
**Imports/Uses**:
- `providers/__init__.py:34` — `.base.ImageProvider` (the ABC every backend subclasses).
- Lazy per-provider imports inside `_load_providers()`: Google `:69`, OpenAI `:77`, Stability `:85`, LocalSD `:96`, Midjourney `:107`, Ollama `:117` — heavy SDKs are never imported unless requested.
- Narrow `core/` usage from the concrete providers: `providers/google.py:31` `core.security.rate_limiter`, `:38` `core.image_utils` (`auto_crop_solid_borders`, `crop_to_aspect_ratio`), `:220` `core.config.ConfigManager`; `providers/openai.py:14` `core.security.rate_limiter`, `:264` `core.image_size`, `:1350` `core.constants.BATCH_JOBS_PATH`; `providers/video/musetalk_provider.py:11` `core.musetalk_installer`.

**Imported By** (non-test): `cli/runner.py:11`, `cli/commands/layout.py:11`, `core/video/image_generator.py:19`, `core/font_generator/glyph_generator.py`, `gui/main_window.py:65-66`, `gui/workers.py:9` and `:105`, `gui/video/video_project_tab.py:275,548,1267`, `gui/video/reference_generation_dialog.py:25,64`.

#### `core/video/` — 35 modules
**Internal spine**: `core/video/project.py` (1055 lines) is the root data model and imports nothing from the rest of the subsystem (only `.karaoke_renderer.KaraokeConfig` under `TYPE_CHECKING` at `core/video/project.py:20`). Everything else depends on it:
- `core/video/storyboard.py:12` → `.project.Scene`
- `core/video/storyboard_v2.py:14-15` → `core.video.project` (`Scene`, `ReferenceImage`) + `core.video.prompt_engine` (`UnifiedLLMProvider`, `PromptStyle`)
- `core/video/prompt_engine.py:17-18` → `.project.Scene`, `core.llm_models`
- `core/video/project_manager.py:13-14` → `.project.VideoProject`, `core.project_tracker.set_current_project`
- `core/video/ffmpeg_renderer.py:19-20` → `.project` (`Scene`, `AudioTrack`, `VideoProject`), `.ffmpeg_utils` (`get_ffmpeg_manager`, `ensure_ffmpeg`); lazily `..karaoke_renderer.KaraokeRenderer` at `core/video/ffmpeg_renderer.py:659`
- `core/video/veo_client.py:1070` → `.ffmpeg_renderer.FFmpegRenderer` (stitching multi-clip Veo output)
- `core/video/image_generator.py:19-21` → `providers.get_provider`, `.project.Scene`, `.event_store`

**Outbound to `core/`** (16 edges): `core.llm_models`, `core.config`, `core.project_tracker`, `core.logging_config`, `core.llm_parsing`.
**Imported By**: `gui/video/*` (94 import statements — the dominant edge in the whole repo), `cli/commands/video.py` (5), `gui/main_window.py:64` (`core.video.reference_manager.ReferenceImageType`).

#### `core/layout/` — 29 modules
**Internal**: `core/layout/models.py` (241 lines) is the most-imported file in the repo (39 importers incl. tests). Render path: `core/layout/engine.py:20-28` → `core.logging_config.LogManager`, `.models`, `.font_manager.FontManager`, `.text_renderer.TextLayoutEngine`, `.image_processor.ImageProcessor`, `.template_engine.TemplateEngine`. Qt path: `core/layout/qt_renderer.py:15-18` → `.models` (`PageSpec`, `Region`, `DocumentSpec`), `.styles.effective_text_style`, `.geometry.validate_segments`, `.text_path` (`glyph_offsets`, `validate_text_path`). Persistence: `core/layout/project_io.py:6-7` → `.models.DocumentSpec`, `.schema`.
**Outbound**: 12 edges to `core/` (mostly `core.logging_config`, `core.config`), 1 to `core.styles` (`core/layout/batch_fill.py:63` `apply_style`), and 1 to `gui/` (see exceptions).
**Imported By**: `gui/layout/*` (41 statements), `cli/commands/layout.py:8-10`, `gui/main_window.py:6236` (`core.layout.fill_plan.FillPlan`, for the Generate↔Layout hand-off).

#### `core/styles/`
**Imports/Uses**: `core/styles/__init__.py:2-5` re-exports `models` (`DESCRIPTOR_KEYS`, `Style`, `StyleDescriptor`), `store.StyleStore`, `analyzer.StyleAnalysisError`, `applicator` (`StyledRequest`, `apply_style`, `apply_style_for_surface`, `style_ref_limit`). `core/styles/analyzer.py:216,247` pulls `core.llm_models`; `core/styles/store.py:17` pulls `core.styles.models` and `core.constants`.
**Imported By**: `cli/runner.py:373`, `cli/commands/{layout,video,style}.py`, `core/layout/batch_fill.py:63`, `gui/main_window.py:5771`, `gui/styles/style_picker.py:14`, `gui/styles/style_manager_dialog.py`.

#### `gui/` (top level)
**Imports/Uses** — `gui/__init__.py:7` defines `launch_gui()`, which lazily imports `MainWindow` at `gui/__init__.py:56` and instantiates it at `:115` (so importing `gui` alone does not pull in the 9138-line main window).
`gui/main_window.py` import block: `:9` `core.llm_models`; `:56-61` the `core` facade; `:62` `core.constants`; `:63` `core.discord_rpc`; `:64` `core.video.reference_manager.ReferenceImageType`; `:65-66` `providers` + `providers.google.MODEL_AUTH_REQUIREMENTS`; `:67-95` sibling GUI modules (`gui.dialogs`, `gui.shortcut_hint_widget`, `gui.history_model`, `gui.workers`, `gui.image_crop_dialog`, `gui.find_dialog`, `gui.prompt_generation_dialog`, `gui.prompt_question_dialog`, `gui.upscaling_widget`, `gui.theme`, `gui.common.dialog_conventions`).
Heavy tabs are deferred: `gui/main_window.py:583` `gui.layout.LayoutTab`, `:7920` `gui.video.video_project_tab.VideoProjectTab`, `:9081` `gui.character_animator.PuppetWizard`, `:9088` `gui.font_generator.FontGeneratorWizard`.
**Imported By**: `main.py:174,196`; `gui/main_window.py` itself is imported by 7 sibling dialogs — always lazily inside a method to avoid a circular import at module load: `gui/enhanced_prompt_dialog.py:440,473`, `gui/prompt_generation_dialog.py:983,1018`, `gui/reference_image_dialog.py:742,786`, `gui/prompt_question_dialog.py:775,808`, `gui/layout/inspector_widget.py:432`.

#### `gui/video/`
**Imports/Uses**: 94 statements into `core/video/`, 39 into `gui/common/`, 26 into `core/`, 6 into top-level `gui/`, 4 into `providers/`, 2 into `providers/video/`.
- `gui/video/video_project_tab.py:17-28` — `gui.common.dialog_manager.get_dialog_manager`, `core.config.ConfigManager`, `core.video.project.VideoProject`, `core.video.project_manager.ProjectManager`, `core.video.config.VideoConfig`, then siblings `.workspace_widget`, `.history_tab`, `.reference_selector_dialog`, `.lipsync_widget`.
- `gui/video/workspace_widget.py:32-48` — `core.config`, `core.video.project` (`VideoProject`, `Scene`), `core.video.project_manager`, `core.video.storyboard.StoryboardGenerator`, `core.video.config.VideoConfig`, `core.security.SecureKeyStorage`, `core.gcloud_utils.get_default_llm_provider`, `core.video.end_prompt_generator`, `core.llm_models`, plus `gui.common.dialog_manager`, `gui.video.{wizard_widget,frame_button,video_button,end_prompt_dialog,prompt_field_widget,reference_images_widget}`, `gui.utils.stderr_suppressor`.
**Imported By**: `gui/main_window.py:7920` only.

#### `gui/layout/`
**Imports/Uses**: `gui/layout/layout_tab.py:12-23` — `core.layout.models` (`DocumentSpec`, `PageSpec`, `PageSize`, `TextStyle`), `core.layout` (`project_io`, `qt_renderer`, `styles`, `template_io`, `designer`, `prompt_helper`, `bundle_io`), `core.layout.history.History`, then siblings `gui.layout.{page_setup_widget,canvas_widget,designer_panel,history_window,style_panel,content_inspector}` and `gui.common.dialog_conventions.standard_splitter`.
Cross-package edges out of `gui/layout/`: `gui/layout/designer_panel.py:11` and `gui/layout/text_gen_dialog.py:19` → `gui.llm_utils`; `gui/layout/inspector_widget.py:432` → `gui.main_window` (tab switch).
**Imported By**: `gui/main_window.py:583`.

#### `gui/common/`, `gui/llm_utils.py`, `gui/theme.py` (shared GUI infrastructure)
- `gui/common/dialog_conventions.py` — 18 importers (the highest GUI fan-in); it imports only `.splitter_style` (`gui/common/dialog_conventions.py:19`), which in turn imports `..theme` (`gui/common/splitter_style.py:9`). `gui/common/` has no other outbound dependencies — it is a leaf by design.
- `gui/llm_utils.py` — `DialogStatusConsole` (`gui/llm_utils.py:15`) and `LiteLLMHandler` (`gui/llm_utils.py:89`); 16 importers, all LLM-facing dialogs (`gui/batch_mode_widget.py`, `gui/enhanced_prompt_dialog.py`, `gui/midjourney_dialog.py`, `gui/prompt_generation_dialog.py`, `gui/prompt_question_dialog.py`, `gui/refine_image_dialog.py`, `gui/reference_image_dialog.py`, `gui/styles/style_manager_dialog.py`, `gui/layout/{designer_panel,text_gen_dialog}.py`, `gui/video/{lipsync_widget,start_prompt_dialog,video_prompt_dialog}.py`) **plus** `core/layout/designer.py:312`.
- `gui/theme.py` — 9 importers, incl. `gui/video/{scene_image_selector_dialog.py:13, suno_preprocess_dialog.py:20, variant_selector_dialog.py:12}`.

#### `utils/` (maintenance scripts, not an app package)
**Imports/Uses**: `core.config.ConfigManager` in `utils/diagnose_references.py:8`, `utils/recover_reference_metadata.py:23`, `utils/test_paths.py:7`, `utils/update_history_from_logs.py:23`, `utils/update_reference_metadata.py:20`; `core.utils.sidecar_path` at `utils/recover_reference_metadata.py:24` and `utils/update_reference_metadata.py:21`.
**Imported By**: nothing — these are standalone `python3 utils/<script>.py` tools.

### Layering Exceptions & Cycles

| Kind | Location | Notes |
|---|---|---|
| `core/` → `gui/` inversion | `core/layout/designer.py:312` `from gui.llm_utils import LiteLLMHandler` | The **only** upward import in the repo. It is function-local (inside `run_completion`, `core/layout/designer.py:309`), so headless/CLI layout design still imports cleanly; but it does couple the layout designer to PySide6-adjacent code. |
| `cli/commands` ↔ `cli/runner` | `cli/commands/layout.py:7`, `cli/commands/video.py:10` import `resolve_api_key`; `cli/runner.py:220,223,226,231,240` import the command modules | Cycle is broken because `runner`'s imports are function-local at dispatch time. |
| Dialogs ↔ `MainWindow` | 7 sibling modules import `gui.main_window` inside methods (`gui/enhanced_prompt_dialog.py:440`, `gui/layout/inspector_widget.py:432`, …) | Deliberate lazy import to avoid a module-load cycle with `gui/main_window.py:67-81`. |
| Orphan module | `core/video/image_generator.py` (`ImageGenerator` at `core/video/image_generator.py:38`) | `grep -rn "image_generator" --include=*.py` finds **no importer** — the live GUI path calls `providers.get_provider()` directly (`gui/video/video_project_tab.py:275,303` and `:548,580`). Dead-ish code / candidate for removal or re-wiring. |
| Qt in `core/` | `core/layout/qt_renderer.py:2-10` imports PySide6 | Isolated to this one `core/` module; CLI export imports it lazily at `cli/commands/layout.py:220` so `--layout-design`/`--layout-fill` stay Qt-free. |

### Data Flow

#### Config & API-key resolution
**Producer**: `ConfigManager` (`core/config.py:16`), backed by `SecureKeyStorage` (`core/security.py`, imported at `core/config.py:11`).

CLI precedence chain — `resolve_api_key()` (`cli/runner.py:14`), documented "CLI arg > file > config > env":
1. `--api-key` value → returned directly (`cli/runner.py:31`).
2. `--api-key-file` → `core.utils.read_key_file` (`core/utils.py:46`, called at `cli/runner.py:37`).
3. `ConfigManager.get_api_key(provider)` (`cli/runner.py:43` → `core/config.py:121`).
4. Environment variables per provider (`cli/runner.py:47-61`; `GOOGLE_API_KEY`/`GEMINI_API_KEY`, `OPENAI_API_KEY`, `STABILITY_KEY`/`STABILITY_API_KEY`).

Inside `ConfigManager.get_api_key` (`core/config.py:121`) the order is: gcloud ADC access token when `auth_mode == "gcloud"` for Google (`core/config.py:128-149`, via `core.gcloud_utils.find_gcloud_command` at `:130`) → OS keyring (`core/config.py:152` `secure_storage.retrieve_key`) → per-provider config dict (`core/config.py:158`). Writes go the other way in `set_api_key` (`core/config.py:167`): keyring first, file only as fallback.

**Consumers**:
- `cli/runner.py:254` (`--test`/generate paths), `cli/runner.py:275` builds the `provider_config` dict passed to `get_provider`.
- `gui/workers.py:7,63` (worker builds its own `ConfigManager` + provider).
- `gui/main_window.py:4440,4511` (Settings tab, key-URL help and `core.security.secure_storage`).
- `providers/google.py:220` reads `ConfigManager` directly for auth-mode decisions.
- `gui/video/workspace_widget.py:37` uses `SecureKeyStorage` for the video tab's LLM keys.

#### Model-registry resolution (no hardcoded LLM model IDs)
**Producer**: `core/model_registry/client.py` — `get_registry()` (`:105`) / `resolve()` (`:129`), wrapped by `core/model_registry/__init__.py:42` which auto-injects `FALLBACK_PATH` (`core/model_registry/__init__.py:39` → `core/model-registry.fallback.json`).
**Adapter**: `core/llm_models.py` — `resolve_model(provider_id, family, static_default)` (`core/llm_models.py:63`) maps app provider aliases (`google`→gemini, `claude`→anthropic) and degrades gracefully: live registry → in-memory cache → bundled snapshot → `static_default`. The snapshot is also read eagerly at import for menu population (`core/llm_models.py:35` `_load_registry_families`, `:44` `_REGISTRY_FAMILIES`, consumed by `_provider_models` at `:48` and `get_provider_models` at `:186`).
**Consumers** (each passes its own `static_default`): `cli/runner.py:99` (lyrics model), `core/lyrics_to_prompts.py:191`, `core/prompt_enhancer_llm.py:159,161,163,165`, `core/styles/analyzer.py:216`, `core/video/end_prompt_generator.py:76`, `core/video/omni_client.py:77`, `core/video/prompt_engine.py:968`, `core/video/style_analyzer.py:51`, `core/font_generator/glyph_identifier.py:150`, `gui/prompt_generation_dialog.py:515`. Model *lists* for combo boxes flow through `get_provider_models()`/`get_provider_display_name()` into `gui/main_window.py:9`, `gui/video/workspace_widget.py:47`, `gui/layout/designer_panel.py`, `gui/workers.py:257` (Ollama live refresh via `update_ollama_models`, `core/llm_models.py:314`).

#### Prompt → provider → image + metadata sidecar
**Producer (factory)**: `providers.get_provider()` (`providers/__init__.py:126`) resolves a name to a lazily-registered `ImageProvider` subclass (`providers/__init__.py:44-123`) and memoizes instances in `_PROVIDER_CACHE` (`providers/__init__.py:40`); `preload_provider()` (`providers/__init__.py:182`) warms it. The contract is `ImageProvider.generate()` (`providers/base.py:23`, abstract on `providers/base.py:8`), returning `(texts, images)`.

**CLI path**:
`cli/runner.py:291/318/347` build the provider → `provider_instance.generate(...)` at `cli/runner.py:489` (or `:500` for the streaming/partial variant) → bytes written at `cli/runner.py:517` (explicit `--out`), `:523-524` (numbered multi-image), or auto-named via `core.sanitize_filename` at `cli/runner.py:531` and `:535` → JSON sidecar written at `cli/runner.py:553-555` (`<image>.png.json`).

**GUI path**:
`MainWindow` constructs `GenWorker` (`gui/workers.py:12`) or `StreamingGenWorker` (`gui/workers.py:76`) at `gui/main_window.py:5814-5840` → the worker builds its own provider (`gui/workers.py:63`, `:105-108`) and calls `generate()` (`gui/workers.py:64`, `:120`) on a `QThread` → `finished` signal lands in `MainWindow._on_generation_finished` (`gui/main_window.py:6285`) → `core.utils.auto_save_images` (`core/utils.py:281`, called at `gui/main_window.py:6435`; original pre-processing copy at `:6381`) → `core.utils.write_image_sidecar` (`core/utils.py:194`, called at `gui/main_window.py:6507`). The Midjourney path mirrors this at `gui/main_window.py:7189,7204`.

**Sidecar consumers**: `core.utils.read_image_sidecar` (`core/utils.py:224`) feeds history restore in `core/utils.py:374` (`scan_disk_history`, `core/utils.py:309`), `gui/workers.py:191` (`HistoryLoaderWorker`), `gui/main_window.py:419` and `:8980`, `gui/video/video_project_tab.py:1881,1893` (importing scene images into a video project), and the `utils/` recovery scripts.

#### Video project → storyboard → renderer
**Producer**: `VideoProject` (`core/video/project.py:442`) with `Scene` (`:289`), `AudioTrack` (`:56`), `ReferenceImage` (`:164`), `ImageVariant` (`:252`); serialization via `to_dict`/`from_dict` (`core/video/project.py:544/627`) and `save`/`load` (`core/video/project.py:760/778`). `ProjectManager` (`core/video/project_manager.py:17`) owns the on-disk lifecycle (`create_project:46`, `load_project:88`, `save_project:115`, `export_project:266`, `import_project:301`) and notifies `core.project_tracker.set_current_project` (`core/video/project_manager.py:14`).

**Stage 1 — lyrics/text → scenes**: `StoryboardGenerator` (`core/video/storyboard.py:475`) consumes `Scene` (`core/video/storyboard.py:12`); driven from the GUI at `gui/video/workspace_widget.py:2505-2509`, `:2870`, `:3246`, `:3297`, `:7223`. The LLM-assisted variant `EnhancedStoryboardGenerator` (`core/video/storyboard_v2.py:138`) additionally consumes `UnifiedLLMProvider`/`PromptStyle` from `core/video/prompt_engine.py` (`core/video/storyboard_v2.py:15`) and is instantiated at `gui/video/workspace_widget.py:3020,3041`.

**Stage 2 — scene → image**: prompts built by `core/video/prompt_engine.py` (Jinja2 templates, `core/video/prompt_engine.py:15`); images generated through `providers.get_provider()` called from `gui/video/video_project_tab.py:275,303` / `:548,580` and `gui/video/reference_generation_dialog.py:64,76`. Video clips go through `core/video/veo_client.py` / `core/video/omni_client.py` (also driven headless by `cli/commands/video.py:134,160`).

**Stage 3 — render**: `FFmpegRenderer` (`core/video/ffmpeg_renderer.py:44`) with `RenderSettings` (`:24`) — `render_slideshow` (`:85`) or `render_from_clips` (`:150`), Ken Burns prep at `:309`, audio mux at `:491`, karaoke overlay at `:641-659` (lazily importing `core.video.karaoke_renderer.KaraokeRenderer`). Invoked from `gui/video/video_project_tab.py:1469,1484-1488,1525-1529` and internally by `core/video/veo_client.py:1070-1072` to stitch multi-clip Veo output. `KaraokeConfig` is configured GUI-side at `gui/video/workspace_widget.py:2958,3271`.

**Audit trail**: `EventStore` (`core/video/event_store.py`) is written from `core/video/image_generator.py:21` and read/written by `gui/video/history_tab.py:22,196` and `gui/video/video_project_tab.py:1824-1828, 2010-2014`.

#### Layout: design → DocumentSpec → render/export
**Producer**: `core.layout.designer` (`core/layout/designer.py`) — `build_messages` (`:21`), `run_design` (`:303`) / `run_completion` (`:309`, which reaches into `gui.llm_utils.LiteLLMHandler` at `:312` and `core.llm_models` at `:313`), `parse_response` (`:260`) → a `DesignerResult` of `Region`/`Overlay` (`core/layout/models.py`, imported at `core/layout/designer.py:7`), with `fallback_result` (`:112`) when the LLM fails.
**Model**: `DocumentSpec`/`PageSpec`/`Region`/`TextStyle` in `core/layout/models.py` — 39 importers, the widest-shared data structure in the repo.
**Persistence**: `core/layout/project_io.py:6-7` (`DocumentSpec` ↔ JSON via `core/layout/schema.py`); bundles via `core/layout/bundle_io.py` (`gui/layout/layout_tab.py:15`).
**Fill**: `core/layout/batch_fill.py` — `build_requests` (`:39`), `parse_result_jsonl` (`:87`), `results_to_placements` (`:110`), applying custom styles at `core/layout/batch_fill.py:63`.
**Render/export**: `core/layout/qt_renderer.py` (`export_document_pdf` / `save_page_png`) consuming `models`, `styles.effective_text_style` (`core/layout/styles.py:65`), `geometry.validate_segments`, `text_path.glyph_offsets` (`core/layout/qt_renderer.py:15-18`). PIL-based path: `core/layout/engine.py:20-28`.
**Consumers**: GUI `gui/layout/layout_tab.py:12-16` (canvas, inspector, history, style panel); CLI `cli/commands/layout.py:8-10` with export at `cli/commands/layout.py:220-232`.
**Cross-tab hand-off**: `gui/main_window.py:6236` imports `core.layout.fill_plan.FillPlan` to receive Generate-tab output; `gui/layout/inspector_widget.py:432` walks up to `MainWindow` and switches to the Generate tab (index 0) to request a new image.

#### Custom styles
**Producer**: `StyleAnalysisService` (`core/styles/analyzer.py`) turns reference images into a `Style`/`StyleDescriptor` (`core/styles/models.py`), persisted by `StyleStore` (`core/styles/store.py`).
**Applicator**: `core/styles/applicator.py` — `apply_style` / `apply_style_for_surface` / `style_ref_limit`, re-exported at `core/styles/__init__.py:5`.
**Consumers**: CLI `cli/runner.py:373,383`, `cli/commands/style.py:8-10`, `cli/commands/layout.py:129,153`, `cli/commands/video.py:32,264`; core `core/layout/batch_fill.py:63`; GUI `gui/main_window.py:5771`, `gui/styles/style_picker.py:14`, `gui/styles/style_manager_dialog.py`.

#### Ambient cross-cutting services
- **Logging**: `core/logging_config.py` — initialized once at `main.py:120`; `LogManager` consumed by `core/layout/{engine,font_manager,image_processor,layout_algorithms,template_engine,template_manager,text_renderer}.py`; error-report metadata pulled by `gui/main_window.py:9095,9113`.
- **Discord Rich Presence**: `core/discord_rpc.py` (`discord_rpc`, `ActivityState`) — imported by 11 GUI modules (`gui/main_window.py:63`, `gui/enhanced_prompt_dialog.py:18`, `gui/prompt_generation_dialog.py:24`, `gui/prompt_question_dialog.py:17`, `gui/reference_image_dialog.py:31`, `gui/character_animator/puppet_wizard.py:40`, `gui/layout/text_gen_dialog.py:18`, `gui/video/{end_prompt_dialog.py:18, reference_generation_dialog.py:21, start_prompt_dialog.py:22, video_prompt_dialog.py:18}`).
- **Rate limiting**: `core.security.rate_limiter` — `providers/google.py:31`, `providers/openai.py:14`.

---

## Configuration Files

### Application Configuration

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `requirements-local-sd.txt` | Extra dependencies for local Stable Diffusion |
| `pytest.ini` | Pytest config — `testpaths=tests` (keeps root-level demo scripts out of collection) |
| `.gitignore` | Must block `config.json`, `.env`, `*.key` |
| `AGENTS.md` | Canonical instructions for all AI coding assistants |
| `CLAUDE.md`, `GEMINI.md` | Thin per-tool pointers that import `AGENTS.md` |
| `.claude/VERSION_LOCATIONS.md` | Every file to touch when bumping the version |

### Data Configuration (`data/`)

- `data/prompts/` — `presets.json`, `artists.json`, `styles.json`, `moods.json`,
  `colors.json`, `lighting.json`, `mediums.json`, `banners.json`,
  `metadata.json`
- `data/style_presets/` — custom style presets
- `data/model_capabilities.json` — provider/model capability matrix

### User Configuration (never in source control)

API keys and settings live in platform-specific user directories:

- **Windows**: `%APPDATA%\ImageAI\config.json`
- **macOS**: `~/Library/Application Support/ImageAI/config.json`
- **Linux**: `~/.config/ImageAI/config.json`

Always read keys through `ConfigManager.get_api_key()`
(`core/config.py:121`) — never index the config dict directly. Resolution is
layered: CLI argument > key file > config > environment variable.

## Architecture Patterns

### Design Patterns

| Pattern | Implementation | Purpose |
|---------|----------------|---------|
| **Factory** | `providers/__init__.py:126` — `get_provider()` | Centralizes provider instantiation; `--provider` switch selects the backend |
| **Strategy** | `providers/base.py:8` — `ImageProvider` (ABC), `generate()` at `:23` | Common interface across Google, OpenAI, Stability, local SD, Ollama, Midjourney |
| **Singleton-ish config** | `core/config.py:16` — `ConfigManager` | One object owns settings and layered key resolution |
| **Observer** | Qt signals/slots throughout `gui/` | Decoupled events, reactive UI |
| **Mixin** | `gui/dialog_utils.py:149` — `OperationGuardMixin` | Reusable concurrent-operation blocking for dialogs |
| **Worker thread** | `gui/workers.py` | `QThread` workers keep generation off the UI thread |

### Architectural Principles

- **Separation of concerns** — `core/` business logic, `gui/` presentation,
  `providers/` external integration, `cli/` command-line surface. The GUI is
  optional: PySide6 is required for the GUI but not for CLI usage.
- **Plugin-style providers** — adding a backend means implementing
  `ImageProvider` and registering it in the factory; nothing else changes.
- **Event-driven UI** — Qt signals for cross-component communication;
  background workers for long operations.
- **Metadata sidecars** — every generated image is written alongside a `.json`
  file recording the prompt and generation details.

## Development Guidelines

### Adding a New Provider

1. Implement the `ImageProvider` interface (`providers/base.py:8`), including
   `generate()` (`providers/base.py:23`).
2. Register the provider in the factory (`providers/__init__.py:126`).
3. Add its key handling to `ConfigManager` and the `--provider` choices in
   `cli/parser.py:7`.
4. Add capability entries to `data/model_capabilities.json`.

### Hard Project Rules

- Images are **scaled proportionally — never cropped or distorted**.
- **Log every LLM interaction in full** — request (provider, model, parameters,
  prompts) and complete response — to both the file logger and the status
  console. Every user-facing error must also be logged, per user, in a
  platform-independent way.
- Never hardcode cloud LLM model IDs (`claude-*`, `gpt-*`, `gemini-*`); resolve
  them at runtime via `resolve_model()` (`core/llm_models.py:63`).
- Never store API keys or secrets in the project directory.

### Gemini Image Generation Gotchas

- Use `gemini-2.5-flash-image`; **avoid** `gemini-2.5-flash-image-preview`
  (deprecated, broken aspect-ratio support).
- Set aspect ratio via `image_config={'aspect_ratio': '4:3'}` in the generation
  config and log it. **Never put dimensions or ratios in the prompt text** —
  strings like `"(1024x768)"` render as literal text in the generated image.
- Supported ratios: 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.
- For targets above 1024px, generate at max dimension 1024, then upscale.
- Reference images whose aspect doesn't match the target: center them on a
  transparent canvas of the correct aspect ratio.
- Gemini frequently wraps JSON in Markdown fences — parse with
  `LLMResponseParser` (`core/llm_parsing.py:15`).

### Threading

- Long operations run on `QThread` workers (`gui/workers.py`).
- Never touch widgets from a background thread; communicate via signals.
- Qt object ownership: set parents with `setParentItem()` rather than passing a
  parent to a `QGraphicsItem` constructor, which can lead to premature GC.

### Testing

```bash
python3 -m pytest                    # full suite (pytest.ini scopes to tests/)
python3 -m pytest tests/layout -q    # one area
```

GUI tests need a display; in headless WSL, mock or skip GUI construction.
Never commit on a broken build — run the syntax/build check first.

### Version Management

`VERSION` is defined at `core/constants.py:9`. Bumping it means updating every
location listed in `.claude/VERSION_LOCATIONS.md` (including the `README.md`
display and changelog) in the same commit.

## Performance Considerations

- **Lazy loading** — heavy resources (diffusers pipelines, Whisper models,
  MuseTalk) load on first use, not at import; see the installer modules
  (`core/package_installer.py`, `core/whisper_installer.py`,
  `core/musetalk_installer.py`).
- **Thumbnail caching** — `core/video/thumbnail_manager.py` caches rendered
  thumbnails rather than re-decoding frames.
- **Background I/O** — generation, rendering, and network calls run on worker
  threads so the UI stays responsive.
- **Batch operations** — `core/batch_manager.py` and
  `core/layout/batch_fill.py` group work instead of issuing per-item calls.
- **Event sourcing for video projects** — `core/video/event_store.py` appends
  events rather than rewriting whole project files.
- **Selective rendering** — the layout engine renders only dirty regions where
  possible (`core/layout/engine.py`, `core/layout/qt_renderer.py`).
