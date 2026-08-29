# Sprite CLI, Docs & Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `Plans/2026-08-29-sprite-tab-design.md` — §4.7 (CLI), decision 3 ("CLI parity ships before the PR"), decision 4 (Python floor 3.11; README support line moves to "3.11+"). This plan implements sub-project **7 of 8**.

**Goal:** Give every Sprite-tab capability a command-line verb (`--sprite-*`) with the same output contract as `--video`, document the feature for users and agents, refresh the CodeMap, bump the version with the changelog entry, and open the single feature PR.

**Architecture:** One new command module `cli/commands/sprite.py` holds one `run_<verb>_cmd(args, token)` per verb and one dispatcher `run_sprite_cmd(args)` that maps exceptions to exit codes. The module calls the `core/sprite/` entry points from sub-projects 1–6 and never re-implements them. `cli/parser.py` gains a `sprite animations` argument group; `cli/runner.py` dispatches sprite verbs after the video block and before the style verbs and the image path. Human text goes to stderr through `_emit`; `--json` prints exactly one JSON object on stdout. A `CancelToken` is wired to SIGINT so Ctrl+C cancels cleanly and reports `cancelled`. Docs: a user guide, feature-list entries, README edits, the `imageai-cli` skill, and the CodeMap. Release: full suite, local review, version bump through the version-manager tool, push, PR.

**Tech Stack:** Python 3.11+, argparse, stdlib `signal`/`json`/`contextlib`, `pytest` with `unittest.mock.patch`, `core.sprite.*` (sub-projects 1–6), `cli.runner.resolve_api_key`, `core.llm_models.resolve_model`, `providers.get_provider`, version-manager tool, `gh` CLI.

**Sub-project:** 7 of 8 — depends on 1–6 (every `core/sprite/` symbol named below must exist with the design's signature). This sub-project is the **PR gate**: nothing is pushed before its last task.

## Global Constraints

- Repo: `/mnt/d/Documents/Code/GitHub/ImageAI`, branch `feat/sprite-tab`. Never `cd`; use absolute paths and `git -C /mnt/d/Documents/Code/GitHub/ImageAI …`.
- Interpreter: `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python`. Tests: `$PY -m pytest <path> -v`. Never use `.venv`.
- CLI output contract (copied from `cli/commands/video.py`): human progress and results go to **stderr** via `_emit`; with `--json`, **stdout carries exactly one JSON object**; exit codes `0` ok, `1` failure (a provider or pipeline failure the CLI reports), `2` usage error (`SpriteCliError`), `3` unexpected exception, `130` cancelled by Ctrl+C. Every file output gets a `.json` record next to it (sidecar); verbs whose output is a tree of files write `<project>/runs/<verb>-<timestamp>.json`.
- API keys only via `cli.runner.resolve_api_key`; never read the config dict directly; never print a key.
- Every user-facing error is logged (`logger.error`) before it is reported. Every LLM call passes `log=_log_and_emit`, so the full request and response reach the file logger and stderr.
- Tests mock `core.sprite.*` entry points with `patch("core.sprite.<module>.<name>")`, the way `tests/video/test_cli_video_dispatch.py` patches `core.video.omni_client.OmniClient`. The command module imports those names **inside** the verb functions, so the patch is seen at call time.
- `tests/test_no_hardcoded_paths.py` must stay green: the CLI builds paths only from `project.project_dir`, `pipeline.stage_dir`, `SpriteProjectManager`, `-o`, and `Path.cwd()`.
- Prose in Simplified Technical English style. Conventional Commits; one commit per task.
- Version bump only through `python3 ~/.claude/skills/version-manager/version_tool.py`; never hand-edit a version number or a changelog heading. The changelog entry lands in the same commit as the bump (the tool does this).
- Local review runs **before** push. This plan runs the `code-reviewer` agent. It does **not** run Codex; Leland may run `/codex:review --base origin/main` after the push-ready commit exists.
- The PR opens once, at the very end, after the review pass and the version bump.

---

## File Structure

| Action | Path | Purpose |
|---|---|---|
| Modify | `cli/parser.py` (video group lines 230–288; insert the sprite group before `# Styles` at line 289) | `sprite animations` argument group; `--video-provider` default becomes `None`; `--json` help mentions sprite verbs |
| Modify | `tests/video/test_cli_video_parser.py` (lines 22–25) | `--video-provider` default test follows the new contract |
| Create | `cli/commands/sprite.py` | `SpriteCliError`, `_emit`, `_progress`, `_sigint_cancels`, `_load_project`, verbs, `run_sprite_cmd` |
| Modify | `cli/runner.py` (`resolve_api_key` env table lines 46–52; dispatch after the video block lines 250–253) | anthropic env var; sprite dispatch |
| Create | `tests/sprite/test_cli_sprite_parser.py` | flag parsing; choices pinned to core constants |
| Create | `tests/sprite/test_cli_sprite_report.py` | payload, sidecar, `--json` purity, exit codes, cancel |
| Create | `tests/sprite/test_cli_sprite_dispatch.py` | every verb against mocked `core.sprite.*` |
| Create | `tests/sprite/test_cli_sprite_runner.py` | `run_cli` routes sprite verbs |
| Create | `Docs/Sprite-Tab-Guide.md` | user guide |
| Modify | `Docs/Features.md` (Layout/Books Tab lines 131–138; CLI Reference lines 235–255) | feature section + CLI examples |
| Modify | `README.md` (Video features lines 220–228; Requirements line 279; "Generate video (CLI)" lines 672–697) | feature bullets; Python 3.11+ line; CLI examples |
| Modify | `Docs/ImageAI-CLI-Guide.md` (TOC lines 17–37; layout section lines 388–410; exit codes lines 478–510; flag reference lines 512–561) | sprite section, exit codes, flags |
| Modify | `.claude/skills/imageai-cli/SKILL.md` (frontmatter line 3; layout section lines 330–401; contract lines 402–411; flag table lines 434–485; anti-footguns lines 486–517) | sprite verbs for agents |
| Modify | `Docs/CodeMap.md` | refresh with `core/sprite`, `gui/sprite`, `cli/commands/sprite.py`, tests |
| Modify (tool) | `core/constants.py`, `README.md`, `CHANGELOG.md` | version bump + changelog (version-manager) |

---

### Task 1: `sprite animations` argument group

**Files:**
- Modify: `cli/parser.py` — add constants after the imports (line 5), insert the group between the video group (ends line 288) and `# Styles` (line 289), change `--video-provider` (lines 244–249) and `--json` (lines 284–288)
- Modify: `tests/video/test_cli_video_parser.py` lines 22–25
- Create: `tests/sprite/test_cli_sprite_parser.py`

**Interfaces:**
- Produces module constants in `cli/parser.py`:
  - `SPRITE_STAGES = ("extract", "key", "cleanup", "alpha", "stabilize", "hd", "pixel")` — mirrors `core.sprite.pipeline.STAGES`
  - `SPRITE_ENGINE_PRESETS = ("unity", "godot4", "phaser3", "pixijs", "unreal", "libgdx", "rpgmaker_mz", "web_preview")` — mirrors `ENGINE_PRESETS` keys
  - `SPRITE_EXPORT_FORMATS = ("grid", "aseprite_json", "texturepacker_json", "png_sequence", "gif", "godot_tres", "aseprite_native")` — the ids of `core.sprite.exporters.engine_presets.FORMAT_IDS` (confirmed by the sub-project 6 planner on 2026-08-29)
- Produces flags: `--sprite-new NAME`, `--sprite-source IMAGE`, `--sprite-project PROJECT`, `--sprite-list`, `--sprite-estimate`, `--sprite-cards BRIEF`, `--sprite-genre {sidescroller,top_down,fighting}`, `--sprite-llm-provider {openai,anthropic,google}`, `--sprite-llm-model MODEL`, `--sprite-render`, `--sprite-actions A,B`, `--sprite-route {video,sheet,edit-chain}`, `--sprite-process`, `--sprite-upto STAGE`, `--force`, `--sprite-import-video PATH`, `--sprite-import-frames DIR`, `--sprite-import-sheet PATH`, `--sprite-grid CxR`, `--sprite-export`, `--sprite-preset ENGINE`, `--sprite-profile {hd,pixel,both}`, `--sprite-formats A,B`. Reused: `--json`, `-o/--out`, `--aspect`, `--video-provider`, `--video-model`, `--provider`, `-m/--model`, `-k/-K`, `--auth-mode`.
- Changes: `--video-provider` default `"veo"` → `None`. `cli/commands/video.py:245` already applies `or "veo"`, so `--video` keeps its behavior; a sprite render keeps the project's own provider (Omni by default, decision 9) unless the user passes the flag.

- [ ] **Step 1: Write the failing parser tests**

```python
# tests/sprite/test_cli_sprite_parser.py
import pytest
from unittest.mock import patch

from cli.parser import (SPRITE_ENGINE_PRESETS, SPRITE_EXPORT_FORMATS, SPRITE_STAGES,
                        build_arg_parser)


def _parse(argv):
    return build_arg_parser().parse_args(argv)


def test_sprite_new_flags_parse():
    args = _parse(["--sprite-new", "hero", "--sprite-source", "hero.png",
                   "--sprite-genre", "fighting", "--aspect", "16:9", "--json"])
    assert args.sprite_new == "hero"
    assert args.sprite_source == "hero.png"
    assert args.sprite_genre == "fighting"
    assert args.aspect == "16:9"
    assert args.json is True


def test_sprite_cards_flags_parse():
    args = _parse(["--sprite-cards", "a knight with a lantern", "--sprite-project", "hero",
                   "--sprite-llm-provider", "anthropic", "--sprite-llm-model", "m", "-o", "cards.json"])
    assert args.sprite_cards == "a knight with a lantern"
    assert args.sprite_project == "hero"
    assert args.sprite_llm_provider == "anthropic"
    assert args.sprite_llm_model == "m"
    assert args.out == "cards.json"


def test_sprite_render_flags_parse():
    args = _parse(["--sprite-render", "--sprite-project", "hero", "--sprite-actions", "idle,walk",
                   "--sprite-route", "sheet", "--video-provider", "omni", "--video-model", "vm"])
    assert args.sprite_render is True
    assert args.sprite_actions == "idle,walk"
    assert args.sprite_route == "sheet"
    assert args.video_provider == "omni"
    assert args.video_model == "vm"


def test_sprite_process_and_import_flags_parse():
    args = _parse(["--sprite-process", "--sprite-project", "hero", "--sprite-upto", "key", "--force"])
    assert args.sprite_process is True
    assert args.sprite_upto == "key"
    assert args.force is True
    a2 = _parse(["--sprite-import-video", "clip.mp4", "--sprite-project", "hero", "--sprite-actions", "walk"])
    assert a2.sprite_import_video == "clip.mp4"
    a3 = _parse(["--sprite-import-frames", "frames/", "--sprite-project", "hero", "--sprite-actions", "walk"])
    assert a3.sprite_import_frames == "frames/"
    a4 = _parse(["--sprite-import-sheet", "sheet.png", "--sprite-grid", "8x1",
                 "--sprite-project", "hero", "--sprite-actions", "walk"])
    assert a4.sprite_import_sheet == "sheet.png"
    assert a4.sprite_grid == "8x1"


def test_sprite_export_flags_parse():
    args = _parse(["--sprite-export", "--sprite-project", "hero", "--sprite-preset", "godot4",
                   "--sprite-profile", "pixel", "--sprite-formats", "grid,gif", "-o", "out/"])
    assert args.sprite_export is True
    assert args.sprite_preset == "godot4"
    assert args.sprite_profile == "pixel"
    assert args.sprite_formats == "grid,gif"
    assert args.out == "out/"


def test_sprite_list_and_estimate_flags_parse():
    assert _parse(["--sprite-list"]).sprite_list is True
    assert _parse(["--sprite-estimate", "--sprite-project", "hero"]).sprite_estimate is True


def test_sprite_defaults_are_unset():
    args = _parse(["--sprite-list"])
    assert args.sprite_genre is None
    assert args.sprite_route is None
    assert args.sprite_upto is None
    assert args.sprite_preset is None
    assert args.sprite_profile is None
    assert args.force is False


@pytest.mark.parametrize("argv", [
    ["--sprite-cards", "x", "--sprite-genre", "platformer"],
    ["--sprite-render", "--sprite-route", "gif"],
    ["--sprite-process", "--sprite-upto", "polish"],
    ["--sprite-export", "--sprite-preset", "unity5"],
    ["--sprite-export", "--sprite-profile", "4k"],
    ["--sprite-cards", "x", "--sprite-llm-provider", "ollama"],
])
def test_sprite_choices_reject_unknown(argv):
    with pytest.raises(SystemExit):
        _parse(argv)


def test_sprite_upto_choices_match_pipeline_stages():
    from core.sprite.pipeline import STAGES
    assert tuple(SPRITE_STAGES) == tuple(STAGES)


def test_sprite_preset_choices_match_engine_presets():
    from core.sprite.exporters.engine_presets import ENGINE_PRESETS
    assert set(SPRITE_ENGINE_PRESETS) == set(ENGINE_PRESETS)


def test_sprite_export_formats_constant_is_stable():
    assert SPRITE_EXPORT_FORMATS == ("grid", "aseprite_json", "texturepacker_json",
                                     "png_sequence", "gif", "godot_tres", "aseprite_native")


def test_sprite_export_formats_match_core_format_ids():
    from core.sprite.exporters.engine_presets import FORMAT_IDS
    assert tuple(SPRITE_EXPORT_FORMATS) == tuple(FORMAT_IDS)


def test_video_provider_default_is_none_so_projects_keep_their_own():
    assert _parse(["--sprite-render", "--sprite-project", "hero"]).video_provider is None
    assert _parse(["--video", "-p", "x"]).video_provider is None
```

- [ ] **Step 2: Update the video parser test that pinned the old default**

Replace `tests/video/test_cli_video_parser.py` lines 22–25 (`test_video_provider_defaults_to_veo`) with:

```python
def test_video_provider_defaults_to_veo(tmp_path):
    """The parser leaves --video-provider unset; run_video_cmd applies the veo default."""
    parser = build_arg_parser()
    out = tmp_path / "x.mp4"
    args = parser.parse_args(["--video", "-p", "x", "-o", str(out)])
    assert args.video_provider is None
    ok = {"success": True, "output_path": str(out), "provider": "veo", "model": "m",
          "aspect_ratio": "16:9", "operation_id": None, "error": None}
    with patch("cli.commands.video._run_veo", return_value=ok) as m:
        from cli.commands.video import run_video_cmd
        assert run_video_cmd(args) == 0
    m.assert_called_once()
```

- [ ] **Step 3: Run the tests; expect failures**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_parser.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/test_cli_video_parser.py -v
```

Expected: `ImportError` for `SPRITE_STAGES` and `unrecognized arguments` errors.

- [ ] **Step 4: Add the constants and the group to `cli/parser.py`**

After line 4 (`from core.constants import ...`) add:

```python
# Sprite CLI choice lists. They mirror core.sprite.pipeline.STAGES and the keys of
# core.sprite.exporters.engine_presets.ENGINE_PRESETS. The parser must not import
# core.sprite (numpy/PIL) just to build --help, so the lists live here, and
# tests/sprite/test_cli_sprite_parser.py pins them to the core: a drift fails the build.
SPRITE_STAGES = ("extract", "key", "cleanup", "alpha", "stabilize", "hd", "pixel")
SPRITE_ENGINE_PRESETS = ("unity", "godot4", "phaser3", "pixijs", "unreal",
                         "libgdx", "rpgmaker_mz", "web_preview")
SPRITE_EXPORT_FORMATS = ("grid", "aseprite_json", "texturepacker_json",
                         "png_sequence", "gif", "godot_tres", "aseprite_native")
```

Change the `--video-provider` argument (lines 244–249) to:

```python
    video_group.add_argument(
        "--video-provider",
        choices=["omni", "veo"],
        default=None,
        help="Video provider: 'omni' (Gemini Omni) or 'veo' (default: veo for --video; "
             "the project's own provider for --sprite-render)",
    )
```

Change the `--json` help (lines 284–288) to `help="Emit a single machine-readable JSON result on stdout (--video and --sprite-* verbs)"`.

Insert before `# Styles (custom styles derived from reference images)` (line 289):

```python
    # Sprite animations (game-sprite pipeline; one --sprite-* verb per call)
    sprite_group = parser.add_argument_group("sprite animations")
    sprite_group.add_argument(
        "--sprite-new", metavar="NAME",
        help="Create a sprite project (needs --sprite-source IMAGE)",
    )
    sprite_group.add_argument(
        "--sprite-source", metavar="IMAGE",
        help="Character image for --sprite-new (padded onto the aspect canvas, never cropped)",
    )
    sprite_group.add_argument(
        "--sprite-project", metavar="PROJECT",
        help="Sprite project for the other verbs: a project name or slug, or a path to "
             "project.iasprite.json (or its folder)",
    )
    sprite_group.add_argument(
        "--sprite-list", action="store_true",
        help="List sprite projects",
    )
    sprite_group.add_argument(
        "--sprite-estimate", action="store_true",
        help="Print the cost estimate per action and per sheet for --sprite-project",
    )
    sprite_group.add_argument(
        "--sprite-cards", metavar="BRIEF",
        help="Generate action cards from a one-line brief (appended to --sprite-project "
             "when given; the card list is also written to -o or cards.json)",
    )
    sprite_group.add_argument(
        "--sprite-genre", choices=["sidescroller", "top_down", "fighting"],
        help="Genre checklist for --sprite-cards / --sprite-new (default: the project's, else sidescroller)",
    )
    sprite_group.add_argument(
        "--sprite-llm-provider", choices=["openai", "anthropic", "google"],
        help="Text-LLM provider for --sprite-cards and the edit-chain route (default: google)",
    )
    sprite_group.add_argument(
        "--sprite-llm-model",
        help="Text-LLM model id for --sprite-cards (default: the registry default for the provider)",
    )
    sprite_group.add_argument(
        "--sprite-render", action="store_true",
        help="Render action cards of --sprite-project (draft/failed cards, or --sprite-actions)",
    )
    sprite_group.add_argument(
        "--sprite-actions", metavar="A,B",
        help="Comma-separated action names: filter for render/process/export; "
             "the single target action for --sprite-import-*",
    )
    sprite_group.add_argument(
        "--sprite-route", choices=["video", "sheet", "edit-chain"],
        help="Generation route for --sprite-render (default: video; video uses "
             "--video-provider/--video-model, image routes use --provider/-m)",
    )
    sprite_group.add_argument(
        "--sprite-process", action="store_true",
        help="Run the processing pipeline on --sprite-project (all actions with frames, or --sprite-actions)",
    )
    sprite_group.add_argument(
        "--sprite-upto", choices=list(SPRITE_STAGES), metavar="STAGE",
        help="Last pipeline stage to run: " + ", ".join(SPRITE_STAGES) +
             " (default: pixel for --sprite-process; stabilize after a render or import)",
    )
    sprite_group.add_argument(
        "--force", action="store_true",
        help="Ignore the stage cache and re-run every stage (--sprite-process)",
    )
    sprite_group.add_argument(
        "--sprite-import-video", metavar="PATH",
        help="Import an external clip as the action named by --sprite-actions, then extract and process",
    )
    sprite_group.add_argument(
        "--sprite-import-frames", metavar="DIR",
        help="Import a PNG sequence (sorted *.png) as the action named by --sprite-actions",
    )
    sprite_group.add_argument(
        "--sprite-import-sheet", metavar="PATH",
        help="Import a sprite sheet as the action named by --sprite-actions (needs --sprite-grid)",
    )
    sprite_group.add_argument(
        "--sprite-grid", metavar="CxR",
        help="Columns x rows of the sheet for --sprite-import-sheet, e.g. 8x1",
    )
    sprite_group.add_argument(
        "--sprite-export", action="store_true",
        help="Export --sprite-project: engine preset x profile x formats into -o DIR "
             "(default: <project>/exports)",
    )
    sprite_group.add_argument(
        "--sprite-preset", choices=list(SPRITE_ENGINE_PRESETS), metavar="ENGINE",
        help="Engine preset for --sprite-export: " + ", ".join(SPRITE_ENGINE_PRESETS) +
             " (default: web_preview)",
    )
    sprite_group.add_argument(
        "--sprite-profile", choices=["hd", "pixel", "both"],
        help="Output profile(s) for --sprite-export (default: both enabled profiles)",
    )
    sprite_group.add_argument(
        "--sprite-formats", metavar="A,B",
        help="Override the preset's formats: " + ", ".join(SPRITE_EXPORT_FORMATS),
    )
```

- [ ] **Step 5: Run the tests; expect green**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_parser.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/ /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_cli_layout_parser.py -v
```

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/parser.py tests/sprite/test_cli_sprite_parser.py tests/video/test_cli_video_parser.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): sprite argument group; --video-provider default follows the project"
```

---

### Task 2: Command module skeleton — contract helpers, `new`, `list`, `estimate`

**Files:**
- Create: `cli/commands/sprite.py`
- Create: `tests/sprite/test_cli_sprite_report.py`
- Create: `tests/sprite/test_cli_sprite_dispatch.py` (first tests; later tasks append)

**Interfaces:**
- Consumes (sub-project 1/2): `core.sprite.pipeline.CancelToken`, `core.sprite.pipeline.Cancelled`, `core.sprite.generation.errors.SpriteGenerationError` (attribute `user_message`), `core.sprite.project.SpriteProjectManager(base_dir=None)` (default `get_data_paths().sprite_projects()`) with `create_project(name) -> SpriteProject` (folder `<base>/<slug>_<YYYYmmdd_HHMMSS>/` with `source/ clips/ stages/ exports/`, saves `project.iasprite.json`), `list_projects() -> List[dict]` (keys `name, slug, path` — the `project.iasprite.json` Path — `created, modified, actions` — int count; newest first), `load_project(path) -> SpriteProject` (folder or `.json`), `save_project(project) -> Path`, `delete_project(project) -> bool` (confirmed by the sub-project 1 planner on 2026-08-29); `SpriteProject` fields `name, project_dir, character_source, plate_color, genre_preset, brief, actions, generation, profiles`, methods `save(path=None) -> Path`, `total_cost() -> (estimated, actual)`; `core.sprite.source.normalize_source(image, out_png, aspect_ratio)`; `core.sprite.generation.cost.estimate_action(settings, action) -> Optional[float]`, `estimate_project(project) -> (Optional[float], int)`.
- Produces in `cli/commands/sprite.py`:
  - `EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_UNEXPECTED, EXIT_CANCELLED = 0, 1, 2, 3, 130`
  - `class SpriteCliError(Exception)`
  - `_emit(msg)`, `_log_and_emit(msg)`, `_progress(stage, done, total, message)`
  - `_sigint_cancels(token)` context manager
  - `_split_csv(value) -> List[str]`, `_parse_grid(value) -> (cols, rows)`
  - `_google_key(args) -> str`, `_resolve_project_path(value) -> Path`, `_load_project(args) -> SpriteProject`, `_project_file(project) -> Path`
  - `_select_actions(project, args, *, default="all"|"renderable")`, `_single_action_name(args)`, `_find_or_create_action(project, name)`
  - `_status_payload(verb, success, *, project=None, output_path=None, error=None, **extra) -> dict`
  - `_write_json(path, payload)`, `_write_sidecar(out_path, payload)`, `_run_record(project, verb, payload) -> Path`
  - `_report(payload, as_json, exit_code) -> int`
  - `run_new_cmd(args, token=None)`, `run_list_cmd(args, token=None)`, `_estimate_rows(project) -> dict`, `run_estimate_cmd(args, token=None)`
  - `_handler_for(verb) -> Callable`, `run_sprite_cmd(args) -> int`

- [ ] **Step 1: Write the failing report/contract tests**

```python
# tests/sprite/test_cli_sprite_report.py
import json
import signal
from argparse import Namespace
from unittest.mock import patch

import pytest

from cli.commands import sprite as sprite_cli
from cli.commands.sprite import (EXIT_CANCELLED, EXIT_FAILED, EXIT_UNEXPECTED, EXIT_USAGE,
                                 SpriteCliError, _progress, _report, _sigint_cancels,
                                 _status_payload, _write_sidecar, run_sprite_cmd)
from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.pipeline import CancelToken, Cancelled


def _ns(**kw):
    base = dict(sprite_new=None, sprite_source=None, sprite_project=None, sprite_list=False,
                sprite_estimate=False, sprite_cards=None, sprite_genre=None,
                sprite_llm_provider=None, sprite_llm_model=None, sprite_render=False,
                sprite_actions=None, sprite_route=None, sprite_process=False, sprite_upto=None,
                force=False, sprite_import_video=None, sprite_import_frames=None,
                sprite_import_sheet=None, sprite_grid=None, sprite_export=False,
                sprite_preset=None, sprite_profile=None, sprite_formats=None,
                json=False, out=None, aspect=None, video_provider=None, video_model=None,
                provider="google", model=None, api_key="k", api_key_file=None, auth_mode="api-key")
    base.update(kw)
    return Namespace(**base)


class _Refusal(SpriteGenerationError):
    user_message = "The provider refused this character. Try the other provider."
    retryable = False


def test_status_payload_has_the_contract_keys_plus_extras():
    p = _status_payload("new", True, project="p.json", output_path="c.png", frames=3)
    assert p["status"] == "completed"
    assert p["verb"] == "new"
    assert p["project"] == "p.json"
    assert p["output_path"] == "c.png"
    assert p["error"] is None
    assert p["frames"] == 3
    assert _status_payload("x", False, error="bad")["status"] == "failed"


def test_write_sidecar_lands_next_to_the_output(tmp_path):
    out = tmp_path / "source" / "character.png"
    _write_sidecar(out, {"a": 1, "p": tmp_path})
    data = json.loads((tmp_path / "source" / "character.json").read_text(encoding="utf-8"))
    assert data["a"] == 1
    assert data["p"] == str(tmp_path)


def test_report_json_prints_exactly_one_object_on_stdout(capsys):
    rc = _report(_status_payload("list", True, projects=[]), True, 0)
    cap = capsys.readouterr()
    assert rc == 0
    assert json.loads(cap.out)["verb"] == "list"
    assert cap.err == ""


def test_report_text_goes_to_stderr_only(capsys):
    _report(_status_payload("new", True, output_path="c.png"), False, 0)
    cap = capsys.readouterr()
    assert cap.out == ""
    assert "sprite new: done -> c.png" in cap.err
    _report(_status_payload("render", False, error="boom"), False, 1)
    assert "sprite render failed: boom" in capsys.readouterr().err


def test_progress_line_format(capsys):
    _progress("key", 3, 8, "0003.png")
    _progress("extract", 0, 0, "probing clip")
    err = capsys.readouterr().err.splitlines()
    assert err == ["[key] 3/8 0003.png", "[extract] probing clip"]


def test_sigint_cancels_token_and_restores_the_handler():
    token = CancelToken()
    before = signal.getsignal(signal.SIGINT)
    with _sigint_cancels(token):
        handler = signal.getsignal(signal.SIGINT)
        assert handler is not before
        handler(signal.SIGINT, None)
        assert token.cancelled
    assert signal.getsignal(signal.SIGINT) is before


def test_usage_error_maps_to_two_and_keeps_stdout_pure(capsys):
    with patch.object(sprite_cli, "run_list_cmd", side_effect=SpriteCliError("bad flag")):
        rc = run_sprite_cmd(_ns(sprite_list=True, json=True))
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_USAGE
    assert obj["status"] == "failed"
    assert obj["verb"] == "list"
    assert obj["error"] == "bad flag"


def test_cancelled_maps_to_130(capsys):
    with patch.object(sprite_cli, "run_list_cmd", side_effect=Cancelled()):
        rc = run_sprite_cmd(_ns(sprite_list=True, json=True))
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_CANCELLED
    assert obj["status"] == "cancelled"


def test_generation_error_maps_to_one_with_user_message(capsys):
    with patch.object(sprite_cli, "run_list_cmd", side_effect=_Refusal("raw provider text")):
        rc = run_sprite_cmd(_ns(sprite_list=True, json=True))
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_FAILED
    assert obj["error"] == _Refusal.user_message


class _FFmpeg(Exception):
    """Stand-in for extract.FFmpegError / pipeline.PipelineError: not a SpriteGenerationError, has user_message."""
    user_message = "ffmpeg exited with status 1 (see the log)"


def test_pipeline_error_with_user_message_maps_to_one(capsys):
    with patch.object(sprite_cli, "run_list_cmd", side_effect=_FFmpeg("raw")):
        rc = run_sprite_cmd(_ns(sprite_list=True, json=True))
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_FAILED
    assert obj["error"] == _FFmpeg.user_message


def test_unexpected_exception_maps_to_three(capsys):
    with patch.object(sprite_cli, "run_list_cmd", side_effect=RuntimeError("boom")):
        rc = run_sprite_cmd(_ns(sprite_list=True, json=True))
    assert rc == EXIT_UNEXPECTED
    assert json.loads(capsys.readouterr().out)["error"] == "boom"


def test_two_verbs_in_one_call_is_a_usage_error(capsys):
    rc = run_sprite_cmd(_ns(sprite_list=True, sprite_estimate=True, json=True))
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_USAGE
    assert "--sprite-list" in obj["error"] and "--sprite-estimate" in obj["error"]


def test_no_verb_is_a_usage_error():
    assert run_sprite_cmd(_ns()) == EXIT_USAGE


def test_json_stdout_pure_with_setup_logging(capsys):
    """Regression guard copied from the video CLI: logger.error must not reach stdout."""
    from core.logging_config import setup_logging
    setup_logging(log_to_file=False)
    with patch.object(sprite_cli, "run_list_cmd", side_effect=SpriteCliError("bad")):
        rc = run_sprite_cmd(_ns(sprite_list=True, json=True))
    assert rc == EXIT_USAGE
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
```

- [ ] **Step 2: Write the failing dispatch tests for `new`, `list`, `estimate`, `_load_project`**

```python
# tests/sprite/test_cli_sprite_dispatch.py
import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cli.commands import sprite as sprite_cli
from cli.commands.sprite import (SpriteCliError, _load_project, _parse_grid, run_estimate_cmd,
                                 run_list_cmd, run_new_cmd)


def _ns(**kw):
    base = dict(sprite_new=None, sprite_source=None, sprite_project=None, sprite_list=False,
                sprite_estimate=False, sprite_cards=None, sprite_genre=None,
                sprite_llm_provider=None, sprite_llm_model=None, sprite_render=False,
                sprite_actions=None, sprite_route=None, sprite_process=False, sprite_upto=None,
                force=False, sprite_import_video=None, sprite_import_frames=None,
                sprite_import_sheet=None, sprite_grid=None, sprite_export=False,
                sprite_preset=None, sprite_profile=None, sprite_formats=None,
                json=False, out=None, aspect=None, video_provider=None, video_model=None,
                provider="google", model=None, api_key="k", api_key_file=None, auth_mode="api-key")
    base.update(kw)
    return Namespace(**base)


def _card(name, **kw):
    base = dict(id=f"{name}-id", name=name, prompt="p", duration_s=8, loop=True, target_frames=8,
                fps=12, status="draft", error=None, clip=None, frames=[])
    base.update(kw)
    return SimpleNamespace(**base)


def _fake_project(tmp_path, actions=(), pixel_enabled=True):
    pdir = tmp_path / "hero"
    pdir.mkdir(exist_ok=True)
    proj = SimpleNamespace(
        name="hero", project_dir=pdir, character_source=None, plate_path=None,
        plate_color="#00FF00", brief="", genre_preset="sidescroller", actions=list(actions),
        generation=SimpleNamespace(provider="omni", model="", aspect_ratio="16:9"),
        profiles=[SimpleNamespace(name="hd", enabled=True),
                  SimpleNamespace(name="pixel", enabled=pixel_enabled)],
        saves=0)

    def _save(path=None):
        proj.saves += 1
        f = pdir / "project.iasprite.json"
        f.write_text("{}", encoding="utf-8")
        return f

    proj.save = _save
    proj.total_cost = lambda: (1.5, 0.75)
    proj.sheet_meta = lambda profile: SimpleNamespace(
        title="hero", profile=profile, frames=[1, 2], tags=[SimpleNamespace(name="idle")])
    return proj


# ---------- --sprite-new ----------

def test_run_new_creates_project_normalizes_and_writes_sidecar(tmp_path, capsys):
    src = tmp_path / "char.png"
    src.write_bytes(b"png")
    proj = _fake_project(tmp_path)
    mgr = MagicMock()
    mgr.create_project.return_value = proj
    with patch("core.sprite.project.SpriteProjectManager", return_value=mgr), \
         patch("core.sprite.source.normalize_source",
               side_effect=lambda image, out_png, aspect_ratio: out_png) as norm:
        rc = run_new_cmd(_ns(sprite_new="hero", sprite_source=str(src), sprite_genre="fighting",
                             json=True))
    assert rc == 0
    mgr.create_project.assert_called_once_with("hero")
    expected_png = proj.project_dir / "source" / "character.png"
    norm.assert_called_once_with(src, expected_png, aspect_ratio="16:9")
    assert proj.character_source == expected_png
    assert proj.genre_preset == "fighting"
    assert proj.saves == 1
    sidecar = json.loads((proj.project_dir / "source" / "character.json").read_text())
    assert sidecar["status"] == "completed" and sidecar["verb"] == "new"
    out = json.loads(capsys.readouterr().out)
    assert out["output_path"] == str(expected_png)
    assert out["project"] == str(proj.project_dir / "project.iasprite.json")


def test_run_new_requires_source():
    with pytest.raises(SpriteCliError, match="--sprite-source"):
        run_new_cmd(_ns(sprite_new="hero"))


def test_run_new_rejects_missing_image(tmp_path):
    with pytest.raises(SpriteCliError, match="not found"):
        run_new_cmd(_ns(sprite_new="hero", sprite_source=str(tmp_path / "nope.png")))


# ---------- --sprite-list ----------

def test_run_list_reports_rows(capsys):
    rows = [{"name": "hero", "slug": "hero_20260829_101500", "path": "/x/hero_20260829_101500/project.iasprite.json",
             "created": "2026-08-29T10:15:00", "modified": "2026-08-29T11:00:00", "actions": 3}]
    mgr = MagicMock()
    mgr.list_projects.return_value = rows
    with patch("core.sprite.project.SpriteProjectManager", return_value=mgr):
        rc = run_list_cmd(_ns(sprite_list=True, json=True))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["count"] == 1 and out["projects"] == rows


# ---------- _load_project / _resolve_project_path ----------

def test_load_project_by_file_or_folder_path(tmp_path):
    f = tmp_path / "hero_20260829_101500" / "project.iasprite.json"
    f.parent.mkdir()
    f.write_text("{}")
    mgr = MagicMock()
    mgr.load_project.return_value = "PROJ"
    with patch("core.sprite.project.SpriteProjectManager", return_value=mgr):
        assert _load_project(_ns(sprite_project=str(f))) == "PROJ"
        assert _load_project(_ns(sprite_project=str(f.parent))) == "PROJ"
    assert [c.args for c in mgr.load_project.call_args_list] == [(f,), (f,)]
    mgr.list_projects.assert_not_called()


def test_load_project_by_name_or_slug_searches_the_list(tmp_path):
    rows = [{"name": "Hero", "slug": "hero_20260829_101500",
             "path": tmp_path / "hero_20260829_101500" / "project.iasprite.json",
             "created": "c", "modified": "m", "actions": 2},
            {"name": "Slime", "slug": "slime_20260828_090000",
             "path": tmp_path / "slime_20260828_090000" / "project.iasprite.json",
             "created": "c", "modified": "m", "actions": 0}]
    mgr = MagicMock()
    mgr.list_projects.return_value = rows
    mgr.load_project.return_value = "PROJ"
    with patch("core.sprite.project.SpriteProjectManager", return_value=mgr):
        assert _load_project(_ns(sprite_project="Slime")) == "PROJ"
        assert _load_project(_ns(sprite_project="hero_20260829_101500")) == "PROJ"
    assert [c.args[0] for c in mgr.load_project.call_args_list] == [rows[1]["path"], rows[0]["path"]]


def test_load_project_unknown_name_lists_available():
    mgr = MagicMock()
    mgr.list_projects.return_value = [
        {"name": "knight", "slug": "knight_1", "path": "p1", "created": "c", "modified": "m", "actions": 1},
        {"name": "slime", "slug": "slime_1", "path": "p2", "created": "c", "modified": "m", "actions": 0}]
    with patch("core.sprite.project.SpriteProjectManager", return_value=mgr):
        with pytest.raises(SpriteCliError, match="knight, slime"):
            _load_project(_ns(sprite_project="hero"))
    mgr.load_project.assert_not_called()


def test_load_project_folder_without_project_file_is_usage_error(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SpriteCliError, match="No project.iasprite.json"):
        _load_project(_ns(sprite_project=str(empty)))


def test_load_project_requires_the_flag():
    with pytest.raises(SpriteCliError, match="--sprite-project is required"):
        _load_project(_ns())


# ---------- --sprite-estimate ----------

def test_run_estimate_reports_per_action_and_sheet(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[_card("idle"), _card("walk", duration_s=4)])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.generation.cost.estimate_action", side_effect=lambda g, a: 0.4), \
         patch("core.sprite.generation.cost.estimate_project", return_value=(0.8, 0)):
        rc = run_estimate_cmd(_ns(sprite_estimate=True, sprite_project="hero", json=True))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [a["name"] for a in out["actions"]] == ["idle", "walk"]
    assert out["actions"][1]["seconds"] == 4
    assert out["actions"][0]["estimated_usd"] == 0.4
    assert out["sheet_estimated_usd"] == 0.8
    assert out["unknown_count"] == 0
    assert out["ledger_estimated_usd"] == 1.5 and out["ledger_actual_usd"] == 0.75
    assert out["provider"] == "omni"


def test_run_estimate_text_mode_prints_unknown(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[_card("idle")])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.generation.cost.estimate_action", return_value=None), \
         patch("core.sprite.generation.cost.estimate_project", return_value=(None, 1)):
        rc = run_estimate_cmd(_ns(sprite_estimate=True, sprite_project="hero"))
    cap = capsys.readouterr()
    assert rc == 0 and cap.out == ""
    assert "unknown" in cap.err


# ---------- helpers ----------

@pytest.mark.parametrize("bad", ["8", "0x1", "axb", "", "8x"])
def test_parse_grid_rejects_bad_values(bad):
    with pytest.raises(SpriteCliError, match="CxR"):
        _parse_grid(bad)


def test_parse_grid_accepts_cxr():
    assert _parse_grid("8x1") == (8, 1)
    assert _parse_grid("4X3") == (4, 3)
```

- [ ] **Step 3: Run the tests; expect `ModuleNotFoundError: cli.commands.sprite`**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_report.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_dispatch.py -v
```

- [ ] **Step 4: Create `cli/commands/sprite.py`**

```python
"""CLI handlers for the Sprite tab: the --sprite-* verbs.

Design: Plans/2026-08-29-sprite-tab-design.md §4.7. Output contract copied from
cli/commands/video.py: human text -> stderr via _emit, --json -> exactly one JSON
object on stdout, exit codes 0 ok / 1 failure / 2 usage / 3 unexpected / 130 cancelled.
"""
import contextlib
import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cli.parser import SPRITE_EXPORT_FORMATS
from cli.runner import SPRITE_VERB_ATTRS, resolve_api_key
from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.pipeline import CancelToken, Cancelled

logger = logging.getLogger("imageai.cli.sprite")

PROJECT_FILE = "project.iasprite.json"
EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_UNEXPECTED, EXIT_CANCELLED = 0, 1, 2, 3, 130


class SpriteCliError(Exception):
    """User-facing CLI validation error (maps to exit code 2)."""


# ---------- output helpers ----------

def _emit(msg: str) -> None:
    """Human-facing progress/result line -> stderr (keeps stdout pure for --json)."""
    print(msg, file=sys.stderr)


def _log_and_emit(msg: str) -> None:
    """`log=` callback for core.sprite: file logger + stderr (AGENTS.md: log every LLM call in full)."""
    logger.info(msg)
    _emit(msg)


def _progress(stage: str, done: int, total: int, message: str) -> None:
    """ProgressFn for core.sprite: one `[stage] done/total message` line per callback."""
    if total:
        _emit(f"[{stage}] {done}/{total} {message}".rstrip())
    else:
        _emit(f"[{stage}] {message}".rstrip())


@contextlib.contextmanager
def _sigint_cancels(token: CancelToken):
    """Route Ctrl+C into token.cancel() while a verb runs; restore the previous handler after."""
    def _handler(signum, frame):  # noqa: ARG001 - signal handler signature
        token.cancel()
        _emit("Cancel requested (Ctrl+C). The current frame finishes, then the verb stops.")

    try:
        previous = signal.signal(signal.SIGINT, _handler)
    except ValueError:
        # Not the main thread (e.g. a GUI or a threaded test runner): no handler, no cancel key.
        yield
        return
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def _split_csv(value: Optional[str]) -> List[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _parse_grid(value: Optional[str]) -> tuple:
    """'CxR' -> (columns, rows); SpriteCliError on anything else."""
    text = (value or "").lower().replace(" ", "")
    cols, sep, rows = text.partition("x")
    if not sep or not cols.isdigit() or not rows.isdigit() or int(cols) < 1 or int(rows) < 1:
        raise SpriteCliError(
            f"--sprite-grid must be CxR with positive integers, e.g. 8x1 (got {value!r}).")
    return int(cols), int(rows)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ---------- project helpers ----------

def _google_key(args) -> str:
    key, _src = resolve_api_key(getattr(args, "api_key", None),
                                getattr(args, "api_key_file", None), "google")
    if not key:
        raise SpriteCliError(
            "No Google API key found. Use --api-key/--api-key-file or set GOOGLE_API_KEY.")
    return key


def _resolve_project_path(value: str) -> Path:
    """--sprite-project value -> the project.iasprite.json path.

    An existing file is used as is; an existing folder must hold project.iasprite.json;
    anything else is matched against list_projects() by name or slug (newest first).
    """
    from core.sprite.project import SpriteProjectManager
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return candidate
    if candidate.is_dir():
        path = candidate / PROJECT_FILE
        if path.is_file():
            return path
        raise SpriteCliError(f"No {PROJECT_FILE} in {candidate}")
    rows = SpriteProjectManager().list_projects()
    for row in rows:
        if value in (row["name"], row["slug"]):
            return Path(row["path"])
    names = ", ".join(row["name"] for row in rows) or "(none)"
    raise SpriteCliError(f"Sprite project not found: {value}. Available: {names}")


def _load_project(args):
    """Resolve --sprite-project (name, slug, folder, or project file) to a SpriteProject."""
    from core.sprite.project import SpriteProjectManager
    ref = getattr(args, "sprite_project", None)
    if not ref:
        raise SpriteCliError(
            "--sprite-project is required: a project name or slug, or a path to project.iasprite.json.")
    path = _resolve_project_path(ref)
    return SpriteProjectManager().load_project(path)


def _project_file(project) -> Path:
    return Path(project.project_dir) / PROJECT_FILE


def _select_actions(project, args, *, default: str = "all") -> list:
    """Resolve --sprite-actions (names or ids) to ActionCards.

    default="all" returns every card when the flag is absent; default="renderable"
    returns the draft/failed/queued cards.
    """
    wanted = _split_csv(getattr(args, "sprite_actions", None))
    if not wanted:
        if default == "renderable":
            return [a for a in project.actions if a.status in ("draft", "failed", "queued")]
        return list(project.actions)
    by_key = {}
    for card in project.actions:
        by_key[card.name] = card
        by_key[card.id] = card
    missing = [w for w in wanted if w not in by_key]
    if missing:
        names = ", ".join(a.name for a in project.actions) or "(none)"
        raise SpriteCliError(f"Unknown action(s): {', '.join(missing)}. Available: {names}")
    return [by_key[w] for w in wanted]


def _single_action_name(args) -> str:
    names = _split_csv(getattr(args, "sprite_actions", None))
    if len(names) != 1:
        raise SpriteCliError(
            "Imports need exactly one action name in --sprite-actions, e.g. --sprite-actions walk.")
    return names[0]


def _find_or_create_action(project, name: str):
    from uuid import uuid4
    from core.sprite.project import ActionCard
    for card in project.actions:
        if card.name == name:
            return card
    card = ActionCard(id=uuid4().hex, name=name, prompt="")
    project.actions.append(card)
    return card


# ---------- payload / sidecar / report ----------

def _status_payload(verb: str, success: bool, *, project=None, output_path=None,
                    error: Optional[str] = None, **extra) -> Dict[str, Any]:
    """The documented JSON/sidecar shape: five fixed keys, then verb-specific extras."""
    payload: Dict[str, Any] = {
        "status": "completed" if success else "failed",
        "verb": verb,
        "project": str(project) if project else None,
        "output_path": str(output_path) if output_path else None,
        "error": error,
    }
    payload.update(extra)
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Best-effort JSON record (sidecar or run record); logs on failure, never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write %s: %s", path, e)


def _write_sidecar(out_path: Path, payload: Dict[str, Any]) -> None:
    """Sidecar next to a file output (`character.png` -> `character.json`)."""
    _write_json(Path(out_path).with_suffix(".json"), payload)


def _run_record(project, verb: str, payload: Dict[str, Any]) -> Path:
    """Run record for verbs whose output is a tree of files: <project>/runs/<verb>-<ts>.json."""
    path = Path(project.project_dir) / "runs" / f"{verb}-{_timestamp()}.json"
    _write_json(path, payload)
    return path


def _report(payload: Dict[str, Any], as_json: bool, exit_code: int) -> int:
    """Emit the payload (stdout JSON if as_json, else a stderr line) and return exit_code."""
    if as_json:
        print(json.dumps(payload, default=str), file=sys.stdout)
        return exit_code
    verb = payload.get("verb")
    status = payload.get("status")
    if status == "completed":
        tail = f" -> {payload['output_path']}" if payload.get("output_path") else ""
        _emit(f"sprite {verb}: done{tail}")
    elif status == "cancelled":
        _emit(f"sprite {verb}: cancelled")
    else:
        _emit(f"sprite {verb} failed: {payload.get('error')}")
    return exit_code


# ---------- verbs: new / list / estimate ----------

def run_new_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-new NAME --sprite-source IMAGE: create a project and normalize the character."""
    from core.sprite.project import SpriteProjectManager
    from core.sprite.source import normalize_source
    name = args.sprite_new
    source = getattr(args, "sprite_source", None)
    if not source:
        raise SpriteCliError("--sprite-new needs --sprite-source IMAGE.")
    src = Path(source).expanduser()
    if not src.is_file():
        raise SpriteCliError(f"--sprite-source image not found: {src}")
    project = SpriteProjectManager().create_project(name)
    if getattr(args, "sprite_genre", None):
        project.genre_preset = args.sprite_genre
    out_png = Path(project.project_dir) / "source" / "character.png"
    aspect = getattr(args, "aspect", None) or project.generation.aspect_ratio
    _emit(f"[source] normalizing {src.name} on a {aspect} canvas (pad, never crop)")
    normalize_source(src, out_png, aspect_ratio=aspect)
    project.character_source = out_png
    project_file = project.save()
    payload = _status_payload("new", True, project=project_file, output_path=out_png,
                              name=project.name, source=str(src), aspect_ratio=aspect,
                              genre=project.genre_preset)
    _write_sidecar(out_png, payload)
    return _report(payload, bool(getattr(args, "json", False)), EXIT_OK)


def run_list_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-list: one row per project under the sprites folder."""
    from core.sprite.project import SpriteProjectManager
    rows = SpriteProjectManager().list_projects()
    as_json = bool(getattr(args, "json", False))
    if not as_json:
        if not rows:
            _emit("No sprite projects.")
        for row in rows:
            _emit(f"{row['name']:<24} {row.get('actions', 0):>3} actions  "
                  f"{row.get('modified', '')}  {row['path']}")
    payload = _status_payload("list", True, projects=rows, count=len(rows))
    return _report(payload, as_json, EXIT_OK)


def _estimate_rows(project) -> Dict[str, Any]:
    """Per-action and per-sheet estimate plus the ledger totals (design decision 8)."""
    from core.sprite.generation.cost import estimate_action, estimate_project
    rows = []
    for card in project.actions:
        rows.append({"id": card.id, "name": card.name, "status": card.status,
                     "seconds": card.duration_s,
                     "estimated_usd": estimate_action(project.generation, card)})
    sheet_usd, unknown = estimate_project(project)
    est_total, actual_total = project.total_cost()
    return {"provider": project.generation.provider,
            "model": project.generation.model or "(default)",
            "actions": rows, "sheet_estimated_usd": sheet_usd, "unknown_count": unknown,
            "ledger_estimated_usd": est_total, "ledger_actual_usd": actual_total}


def _usd(value: Optional[float]) -> str:
    return "unknown" if value is None else f"${value:.3f}"


def run_estimate_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-estimate: print the estimate per action and per sheet; never spends."""
    project = _load_project(args)
    est = _estimate_rows(project)
    as_json = bool(getattr(args, "json", False))
    if not as_json:
        _emit(f"Estimate for {project.name} ({est['provider']} / {est['model']}):")
        for row in est["actions"]:
            _emit(f"  {row['name']:<20} {row['seconds']:>3}s  {_usd(row['estimated_usd'])}")
        _emit(f"  sheet total: {_usd(est['sheet_estimated_usd'])} "
              f"({est['unknown_count']} unknown)  ledger: est {_usd(est['ledger_estimated_usd'])}"
              f" / actual {_usd(est['ledger_actual_usd'])}")
    payload = _status_payload("estimate", True, project=_project_file(project), **est)
    return _report(payload, as_json, EXIT_OK)


# ---------- dispatcher ----------

def _handler_for(verb: str) -> Callable:
    """Verb name -> handler, resolved at call time so tests can patch a handler."""
    return {
        "new": run_new_cmd,
        "list": run_list_cmd,
        "estimate": run_estimate_cmd,
    }[verb]


def run_sprite_cmd(args) -> int:
    """Dispatch exactly one --sprite-* verb; map exceptions to the exit-code contract."""
    as_json = bool(getattr(args, "json", False))
    selected = [attr for attr in SPRITE_VERB_ATTRS if getattr(args, attr, None)]
    verb = selected[0][len("sprite_"):] if selected else "sprite"
    project_ref = getattr(args, "sprite_project", None)

    def _fail(status: str, message: str, code: int) -> int:
        payload = _status_payload(verb, False, project=project_ref, error=message)
        payload["status"] = status
        return _report(payload, as_json, code)

    if not selected:
        logger.error("Sprite CLI: no verb given")
        return _fail("failed", "No sprite verb given (see --help, group 'sprite animations').",
                     EXIT_USAGE)
    if len(selected) > 1:
        names = ", ".join("--" + attr.replace("_", "-") for attr in selected)
        logger.error("Sprite CLI: more than one verb: %s", names)
        return _fail("failed", f"One sprite verb per call; got {names}.", EXIT_USAGE)

    token = CancelToken()
    try:
        with _sigint_cancels(token):
            return _handler_for(verb)(args, token)
    except SpriteCliError as e:
        logger.error("Sprite CLI (%s): %s", verb, e)
        return _fail("failed", str(e), EXIT_USAGE)
    except Cancelled:
        logger.warning("Sprite CLI (%s): cancelled by the user", verb)
        return _fail("cancelled", "cancelled", EXIT_CANCELLED)
    except Exception as e:  # noqa: BLE001 - surface + log any runtime failure
        # SpriteGenerationError, pipeline.PipelineError, and extract.FFmpegError carry a
        # user_message: a reported failure (exit 1). Anything else is unexpected (exit 3).
        message = getattr(e, "user_message", None)
        if message or isinstance(e, SpriteGenerationError):
            message = message or str(e)
            logger.error("Sprite CLI (%s): %s", verb, message, exc_info=True)
            return _fail("failed", message, EXIT_FAILED)
        logger.error("Sprite CLI (%s) failed: %s", verb, e, exc_info=True)
        return _fail("failed", str(e), EXIT_UNEXPECTED)
```

- [ ] **Step 5: Add `SPRITE_VERB_ATTRS` to `cli/runner.py`**

The dispatcher and the runner share one list. Add after the imports (line 11 of `cli/runner.py`):

```python
# Attributes that select a --sprite-* verb. run_cli checks them without importing
# core.sprite; cli/commands/sprite.py imports the same tuple for its dispatcher.
SPRITE_VERB_ATTRS = ("sprite_new", "sprite_list", "sprite_estimate", "sprite_cards",
                     "sprite_import_video", "sprite_import_frames", "sprite_import_sheet",
                     "sprite_render", "sprite_process", "sprite_export")
```

(The `run_cli` branch that uses it is Task 8.)

- [ ] **Step 6: Run the tests; expect green**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_report.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_dispatch.py -v
```

- [ ] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/commands/sprite.py cli/runner.py tests/sprite/test_cli_sprite_report.py tests/sprite/test_cli_sprite_dispatch.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): sprite command module — new/list/estimate, report + cancel contract"
```

---

### Task 3: Import verbs — `--sprite-import-video`, `--sprite-import-frames`, `--sprite-import-sheet`

**Files:**
- Modify: `cli/commands/sprite.py` (append the pipeline helper and three verbs; extend `_handler_for`)
- Modify: `tests/sprite/test_cli_sprite_dispatch.py` (append)

**Interfaces:**
- Consumes (sub-project 1): `core.sprite.pipeline.run_pipeline(project, action, *, upto, progress, token, force) -> Dict[str, List[Path]]`, `core.sprite.pipeline.stage_dir(project, action, stage) -> Path`, `core.sprite.pipeline.register_external_frames(project, action)`, `core.sprite.slicing.import_png_sequence(paths, out_dir) -> List[Path]`, `core.sprite.slicing.slice_sheet(sheet, out_dir, columns, rows) -> List[Path]`, `core.sprite.project.ClipRecord(path, provider, model, operation_id, params, prompt, generated_at, estimated_usd, actual_usd)`.
- G9 contract with sub-project 1: an action with `clip is None` and a non-empty `stage_dir(project, action, "extract")` starts the pipeline at `key`. An imported video sets `action.clip` (provider `"import"`) and lets `extract` run. After writing external frames the CLI calls `register_external_frames(project, action)`, which records the extract fingerprint (confirmed by the sub-project 1 planner on 2026-08-29). Pipeline errors are `pipeline.PipelineError` / `extract.FFmpegError`, both with `.user_message`; the dispatcher maps any exception with `user_message` to exit 1.
- Produces: `_pipeline_upto(args, default) -> str`, `_run_pipeline_for(project, action, args, token, default_upto, *, force=None) -> Dict[str, int]`, `_import_common(args) -> (project, action)`, `run_import_video_cmd`, `run_import_frames_cmd`, `run_import_sheet_cmd`.
- Imports always pass `force=True` to the pipeline: the stage cache fingerprints settings, not frame content, so a re-import must re-run every stage after `extract`.

- [ ] **Step 1: Append the failing tests**

```python
# tests/sprite/test_cli_sprite_dispatch.py (append)
from cli.commands.sprite import run_import_frames_cmd, run_import_sheet_cmd, run_import_video_cmd


def _stage_dir_factory(tmp_path):
    def _stage_dir(project, action, stage):
        return tmp_path / "stages" / action.id / stage
    return _stage_dir


def test_import_frames_copies_and_runs_pipeline(tmp_path, capsys):
    src = tmp_path / "frames"
    src.mkdir()
    for i in (3, 1, 2):
        (src / f"f{i}.png").write_bytes(b"png")
    (src / "notes.txt").write_text("x")
    proj = _fake_project(tmp_path, actions=[_card("walk")])
    outputs = {"extract": [1, 2, 3], "key": [1, 2, 3], "stabilize": [1, 2, 3]}
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.slicing.import_png_sequence", return_value=[1, 2, 3]) as imp, \
         patch("core.sprite.pipeline.register_external_frames") as reg, \
         patch("core.sprite.pipeline.run_pipeline", return_value=outputs) as run:
        rc = run_import_frames_cmd(_ns(sprite_import_frames=str(src), sprite_project="hero",
                                       sprite_actions="walk", json=True))
    assert rc == 0
    paths, out_dir = imp.call_args.args
    assert [p.name for p in paths] == ["f1.png", "f2.png", "f3.png"]
    assert out_dir == tmp_path / "stages" / "walk-id" / "extract"
    reg.assert_called_once_with(proj, proj.actions[0])
    kwargs = run.call_args.kwargs
    assert kwargs["upto"] == "stabilize" and kwargs["force"] is True
    assert kwargs["progress"] is sprite_cli._progress
    card = proj.actions[0]
    assert card.status == "processed" and card.clip is None
    out = json.loads(capsys.readouterr().out)
    assert out["stages"] == {"extract": 3, "key": 3, "stabilize": 3}
    assert out["imported"] == 3
    assert (out_dir.parent / "extract.json").exists()          # sidecar beside the stage dir
    assert list((proj.project_dir / "runs").glob("import_frames-*.json"))


def test_import_frames_honors_upto_and_creates_missing_action(tmp_path):
    src = tmp_path / "frames"
    src.mkdir()
    (src / "0001.png").write_bytes(b"png")
    proj = _fake_project(tmp_path)
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.slicing.import_png_sequence", return_value=[1]), \
         patch("core.sprite.pipeline.register_external_frames"), \
         patch("core.sprite.pipeline.run_pipeline", return_value={"extract": [1]}) as run:
        rc = run_import_frames_cmd(_ns(sprite_import_frames=str(src), sprite_project="hero",
                                       sprite_actions="jump", sprite_upto="key"))
    assert rc == 0
    assert run.call_args.kwargs["upto"] == "key"
    assert [a.name for a in proj.actions] == ["jump"]           # real ActionCard appended


def test_import_frames_requires_exactly_one_action_name(tmp_path):
    src = tmp_path / "frames"
    src.mkdir()
    (src / "0001.png").write_bytes(b"png")
    proj = _fake_project(tmp_path)
    with patch.object(sprite_cli, "_load_project", return_value=proj):
        with pytest.raises(SpriteCliError, match="exactly one action name"):
            run_import_frames_cmd(_ns(sprite_import_frames=str(src), sprite_project="hero",
                                      sprite_actions="a,b"))


def test_import_frames_rejects_empty_dir(tmp_path):
    src = tmp_path / "frames"
    src.mkdir()
    with pytest.raises(SpriteCliError, match="No .png frames"):
        run_import_frames_cmd(_ns(sprite_import_frames=str(src), sprite_project="hero",
                                  sprite_actions="walk"))


def test_import_sheet_slices_with_grid(tmp_path):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(b"png")
    proj = _fake_project(tmp_path, actions=[_card("walk")])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.slicing.slice_sheet", return_value=[1] * 8) as sl, \
         patch("core.sprite.pipeline.register_external_frames") as reg, \
         patch("core.sprite.pipeline.run_pipeline", return_value={"extract": [1] * 8}):
        rc = run_import_sheet_cmd(_ns(sprite_import_sheet=str(sheet), sprite_grid="8x1",
                                      sprite_project="hero", sprite_actions="walk"))
    assert rc == 0
    sl.assert_called_once_with(sheet, tmp_path / "stages" / "walk-id" / "extract", 8, 1)
    reg.assert_called_once_with(proj, proj.actions[0])


def test_import_sheet_requires_grid(tmp_path):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(b"png")
    with pytest.raises(SpriteCliError, match="CxR"):
        run_import_sheet_cmd(_ns(sprite_import_sheet=str(sheet), sprite_project="hero",
                                 sprite_actions="walk"))


def test_import_video_copies_clip_sets_clip_record_and_extracts(tmp_path, capsys):
    clip = tmp_path / "walk.MP4"
    clip.write_bytes(b"vid")
    proj = _fake_project(tmp_path, actions=[_card("walk")])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.run_pipeline", return_value={"extract": [1] * 12}) as run:
        rc = run_import_video_cmd(_ns(sprite_import_video=str(clip), sprite_project="hero",
                                      sprite_actions="walk", json=True))
    assert rc == 0
    card = proj.actions[0]
    dest = proj.project_dir / "clips" / "walk-id.mp4"
    assert dest.read_bytes() == b"vid"
    assert card.clip.path == dest and card.clip.provider == "import"
    assert card.clip.params["source"] == str(clip)
    assert json.loads(dest.with_suffix(".json").read_text())["provider"] == "import"
    assert run.call_args.kwargs["upto"] == "stabilize"
    assert json.loads(capsys.readouterr().out)["output_path"] == str(dest)


def test_import_video_missing_file(tmp_path):
    with pytest.raises(SpriteCliError, match="not found"):
        run_import_video_cmd(_ns(sprite_import_video=str(tmp_path / "no.mp4"),
                                 sprite_project="hero", sprite_actions="walk"))
```

- [ ] **Step 2: Run; expect `ImportError` for the three verbs**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_dispatch.py -v -k import
```

- [ ] **Step 3: Append the pipeline helper and the import verbs to `cli/commands/sprite.py`** (insert before `# ---------- dispatcher ----------`)

```python
# ---------- pipeline helper ----------

def _pipeline_upto(args, default: str) -> str:
    return getattr(args, "sprite_upto", None) or default


def _run_pipeline_for(project, action, args, token, default_upto: str,
                      *, force: Optional[bool] = None) -> Dict[str, int]:
    """Run the processing spine for one action; returns {stage: frame_count}."""
    from core.sprite.pipeline import run_pipeline
    upto = _pipeline_upto(args, default_upto)
    if force is None:
        force = bool(getattr(args, "force", False))
    _emit(f"[pipeline] {action.name}: running up to '{upto}'" + (" (forced)" if force else ""))
    outputs = run_pipeline(project, action, upto=upto, progress=_progress, token=token,
                           force=force)
    action.status = "processed"
    action.error = None
    return {stage: len(paths) for stage, paths in outputs.items()}


# ---------- verbs: imports (G9) ----------

def _import_common(args):
    """Project + the single target action for an import (created when missing)."""
    project = _load_project(args)
    name = _single_action_name(args)
    return project, _find_or_create_action(project, name)


def run_import_video_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-import-video PATH: copy the clip under clips/, then extract and process."""
    import shutil
    from core.sprite.project import ClipRecord
    src = Path(args.sprite_import_video).expanduser()
    if not src.is_file():
        raise SpriteCliError(f"--sprite-import-video file not found: {src}")
    project, action = _import_common(args)
    clip_path = Path(project.project_dir) / "clips" / f"{action.id}{src.suffix.lower() or '.mp4'}"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, clip_path)
    stamp = datetime.now().isoformat(timespec="seconds")
    action.clip = ClipRecord(path=clip_path, provider="import", model="", operation_id=None,
                             params={"source": str(src)}, prompt="", generated_at=stamp,
                             estimated_usd=None, actual_usd=None)
    action.status = "rendered"
    action.error = None
    _write_sidecar(clip_path, {"provider": "import", "model": "", "source": str(src),
                               "action": action.name, "action_id": action.id,
                               "imported_at": stamp, "cost_usd": None})
    project.save()
    _emit(f"[import] {src.name} -> {clip_path}")
    counts = _run_pipeline_for(project, action, args, token, "stabilize", force=True)
    project_file = project.save()
    payload = _status_payload("import_video", True, project=project_file, output_path=clip_path,
                              action=action.name, action_id=action.id, stages=counts)
    _run_record(project, "import_video", payload)
    return _report(payload, bool(getattr(args, "json", False)), EXIT_OK)


def run_import_frames_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-import-frames DIR: copy a PNG sequence into the extract stage, then process."""
    from core.sprite.pipeline import register_external_frames, stage_dir
    from core.sprite.slicing import import_png_sequence
    src_dir = Path(args.sprite_import_frames).expanduser()
    if not src_dir.is_dir():
        raise SpriteCliError(f"--sprite-import-frames directory not found: {src_dir}")
    frames = sorted(p for p in src_dir.iterdir() if p.suffix.lower() == ".png")
    if not frames:
        raise SpriteCliError(f"No .png frames in {src_dir}")
    project, action = _import_common(args)
    out_dir = stage_dir(project, action, "extract")
    _emit(f"[import] {len(frames)} frames -> {out_dir}")
    written = import_png_sequence(frames, out_dir)
    action.clip = None
    register_external_frames(project, action)   # records the extract fingerprint (G9)
    action.status = "rendered"
    action.error = None
    project.save()
    counts = _run_pipeline_for(project, action, args, token, "stabilize", force=True)
    project_file = project.save()
    payload = _status_payload("import_frames", True, project=project_file, output_path=out_dir,
                              action=action.name, action_id=action.id, source=str(src_dir),
                              imported=len(written), stages=counts)
    _write_json(Path(out_dir).with_suffix(".json"), payload)
    _run_record(project, "import_frames", payload)
    return _report(payload, bool(getattr(args, "json", False)), EXIT_OK)


def run_import_sheet_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-import-sheet PATH --sprite-grid CxR: slice a sheet into the extract stage."""
    from core.sprite.pipeline import register_external_frames, stage_dir
    from core.sprite.slicing import slice_sheet
    sheet = Path(args.sprite_import_sheet).expanduser()
    if not sheet.is_file():
        raise SpriteCliError(f"--sprite-import-sheet file not found: {sheet}")
    columns, rows = _parse_grid(getattr(args, "sprite_grid", None))
    project, action = _import_common(args)
    out_dir = stage_dir(project, action, "extract")
    _emit(f"[import] slicing {sheet.name} as {columns}x{rows} -> {out_dir}")
    written = slice_sheet(sheet, out_dir, columns, rows)
    action.clip = None
    register_external_frames(project, action)   # records the extract fingerprint (G9)
    action.status = "rendered"
    action.error = None
    project.save()
    counts = _run_pipeline_for(project, action, args, token, "stabilize", force=True)
    project_file = project.save()
    payload = _status_payload("import_sheet", True, project=project_file, output_path=out_dir,
                              action=action.name, action_id=action.id, source=str(sheet),
                              grid=[columns, rows], imported=len(written), stages=counts)
    _write_json(Path(out_dir).with_suffix(".json"), payload)
    _run_record(project, "import_sheet", payload)
    return _report(payload, bool(getattr(args, "json", False)), EXIT_OK)
```

Extend `_handler_for`:

```python
    return {
        "new": run_new_cmd,
        "list": run_list_cmd,
        "estimate": run_estimate_cmd,
        "import_video": run_import_video_cmd,
        "import_frames": run_import_frames_cmd,
        "import_sheet": run_import_sheet_cmd,
    }[verb]
```

- [ ] **Step 4: Run; expect green**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_dispatch.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_report.py -v
```

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/commands/sprite.py tests/sprite/test_cli_sprite_dispatch.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): sprite import verbs (video, frames, sheet)"
```

---

### Task 4: `--sprite-cards` — action-card generation

**Files:**
- Modify: `cli/commands/sprite.py` (append `_llm_settings`, `_unique_name`, `run_cards_cmd`; extend `_handler_for`)
- Modify: `cli/runner.py` lines 46–52 (`env_vars` table in `resolve_api_key`)
- Modify: `tests/sprite/test_cli_sprite_dispatch.py` (append)

**Interfaces:**
- Consumes (sub-project 2): `core.sprite.generation.action_cards.generate_action_cards(brief, genre, *, provider, model, api_key, plate_color, completion_fn=None, log) -> List[ActionCardDraft]` (draft fields `name, prompt, duration_s, loop, target_frames, fps`); `core.llm_models.resolve_model(provider_id, family)`; `core.sprite.project.ActionCard(id, name, prompt, duration_s, loop, target_frames, fps)`.
- Changes: `resolve_api_key` gains `"anthropic": ["ANTHROPIC_API_KEY"]` in its env table, so `--sprite-llm-provider anthropic` resolves a key the same way the other providers do (config first, env second).
- Produces: `_llm_settings(args, project) -> (provider, model, key)`, `_unique_name(existing, name) -> str`, `run_cards_cmd(args, token=None)`.
- Output: the card list is written as JSON to `-o`, else `<project>/cards.json`, else `./sprite_cards.json`. That file is JSON, so it is its own sidecar.

- [ ] **Step 1: Append the failing tests**

```python
# tests/sprite/test_cli_sprite_dispatch.py (append)
from cli.commands.sprite import run_cards_cmd


def _drafts():
    return [SimpleNamespace(name="idle", prompt="stands and breathes", duration_s=4, loop=True,
                            target_frames=8, fps=12),
            SimpleNamespace(name="idle", prompt="a second idle", duration_s=4, loop=True,
                            target_frames=6, fps=12),
            SimpleNamespace(name="walk", prompt="walks right", duration_s=8, loop=True,
                            target_frames=8, fps=12)]


def test_cards_appends_to_project_and_writes_cards_json(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[_card("walk")])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.generation.action_cards.generate_action_cards",
               return_value=_drafts()) as gen, \
         patch("core.llm_models.resolve_model", return_value="gemini-x") as rm, \
         patch("cli.commands.sprite.resolve_api_key", return_value=("k", "config")):
        rc = run_cards_cmd(_ns(sprite_cards="a knight with a lantern", sprite_project="hero",
                               sprite_genre="fighting", json=True))
    assert rc == 0
    rm.assert_called_once_with("google", "chat")
    kw = gen.call_args.kwargs
    assert gen.call_args.args == ("a knight with a lantern", "fighting")
    assert kw["provider"] == "google" and kw["model"] == "gemini-x" and kw["api_key"] == "k"
    assert kw["plate_color"] == "#00FF00"
    assert kw["log"] is sprite_cli._log_and_emit
    names = [a.name for a in proj.actions]
    assert names == ["walk", "idle", "idle_2", "walk_2"]        # unique per project
    assert proj.brief == "a knight with a lantern" and proj.genre_preset == "fighting"
    assert proj.saves == 1
    cards_file = proj.project_dir / "cards.json"
    data = json.loads(cards_file.read_text(encoding="utf-8"))
    assert data["count"] == 3 and data["cards"][0]["name"] == "idle"
    out = json.loads(capsys.readouterr().out)
    assert out["output_path"] == str(cards_file)
    assert out["llm_model"] == "gemini-x"


def test_cards_without_project_writes_to_out(tmp_path, capsys):
    target = tmp_path / "cards.json"
    with patch("core.sprite.generation.action_cards.generate_action_cards", return_value=_drafts()[:1]), \
         patch("core.llm_models.resolve_model", return_value="m"), \
         patch("cli.commands.sprite.resolve_api_key", return_value=("k", "env")):
        rc = run_cards_cmd(_ns(sprite_cards="a slime", sprite_llm_provider="anthropic",
                               sprite_llm_model="claude-x", out=str(target)))
    assert rc == 0
    data = json.loads(target.read_text())
    assert data["genre"] == "sidescroller" and data["llm_provider"] == "anthropic"
    assert data["llm_model"] == "claude-x" and data["project"] is None
    assert capsys.readouterr().out == ""


def test_cards_missing_key_is_usage_error():
    with patch("core.llm_models.resolve_model", return_value="m"), \
         patch("cli.commands.sprite.resolve_api_key", return_value=(None, "none")):
        with pytest.raises(SpriteCliError, match="No openai API key"):
            run_cards_cmd(_ns(sprite_cards="x", sprite_llm_provider="openai"))


def test_cards_empty_brief_is_usage_error():
    with pytest.raises(SpriteCliError, match="non-empty brief"):
        run_cards_cmd(_ns(sprite_cards="   "))


def test_resolve_api_key_reads_anthropic_env(monkeypatch):
    from cli.runner import resolve_api_key
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with patch("cli.runner.ConfigManager") as CM:
        CM.return_value.get_api_key.return_value = None
        assert resolve_api_key(None, None, "anthropic") == ("sk-test", "env:ANTHROPIC_API_KEY")
```

- [ ] **Step 2: Run; expect `ImportError: run_cards_cmd` and the env test failing**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_dispatch.py -v -k "cards or anthropic"
```

- [ ] **Step 3: Extend the env table in `cli/runner.py` (lines 46–52)**

```python
    env_vars = {
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "stability": ["STABILITY_KEY", "STABILITY_API_KEY"],
        "local_sd": [],  # No API key needed
    }
```

- [ ] **Step 4: Append to `cli/commands/sprite.py`** (before `# ---------- dispatcher ----------`)

```python
# ---------- verbs: action cards ----------

def _llm_settings(args, project) -> tuple:
    """Text-LLM provider, model, and key for the card and pose contracts."""
    from core.llm_models import resolve_model
    provider = getattr(args, "sprite_llm_provider", None) or "google"
    model = getattr(args, "sprite_llm_model", None) or resolve_model(provider, "chat")
    key, _src = resolve_api_key(getattr(args, "api_key", None),
                                getattr(args, "api_key_file", None), provider)
    if not key:
        raise SpriteCliError(
            f"No {provider} API key found for the text LLM. Use --api-key/--api-key-file, "
            f"or store one in Settings.")
    return provider, model, key


def _unique_name(existing: set, name: str) -> str:
    if name not in existing:
        return name
    k = 2
    while f"{name}_{k}" in existing:
        k += 1
    return f"{name}_{k}"


def run_cards_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-cards BRIEF: LLM contract 'Sprite Action Cards — Strict v1.0' -> ActionCards."""
    from uuid import uuid4
    from core.sprite.generation.action_cards import generate_action_cards
    from core.sprite.project import ActionCard
    brief = (args.sprite_cards or "").strip()
    if not brief:
        raise SpriteCliError("--sprite-cards needs a non-empty brief.")
    project = _load_project(args) if getattr(args, "sprite_project", None) else None
    genre = getattr(args, "sprite_genre", None) or (project.genre_preset if project else "sidescroller")
    plate_color = project.plate_color if project else "#00FF00"
    provider, model, key = _llm_settings(args, project)
    _emit(f"[cards] {provider}/{model}: genre={genre}")
    drafts = generate_action_cards(brief, genre, provider=provider, model=model, api_key=key,
                                   plate_color=plate_color, log=_log_and_emit)
    existing = {a.name for a in project.actions} if project else set()
    cards = []
    for draft in drafts:
        name = _unique_name(existing, draft.name)
        existing.add(name)
        card = ActionCard(id=uuid4().hex, name=name, prompt=draft.prompt,
                          duration_s=draft.duration_s, loop=draft.loop,
                          target_frames=draft.target_frames, fps=draft.fps)
        cards.append(card)
        if project is not None:
            project.actions.append(card)
    rows = [{"id": c.id, "name": c.name, "prompt": c.prompt, "duration_s": c.duration_s,
             "loop": c.loop, "target_frames": c.target_frames, "fps": c.fps} for c in cards]
    project_file = None
    if project is not None:
        project.brief = brief
        project.genre_preset = genre
        project_file = project.save()
    out = getattr(args, "out", None)
    if out:
        out_path = Path(out).expanduser()
    elif project is not None:
        out_path = Path(project.project_dir) / "cards.json"
    else:
        out_path = Path.cwd() / "sprite_cards.json"
    payload = _status_payload("cards", True, project=project_file, output_path=out_path,
                              brief=brief, genre=genre, llm_provider=provider, llm_model=model,
                              cards=rows, count=len(rows))
    _write_json(out_path, payload)  # the card file is JSON: it is its own sidecar
    as_json = bool(getattr(args, "json", False))
    if not as_json:
        for row in rows:
            _emit(f"  {row['name']:<16} {row['duration_s']}s  {row['target_frames']} frames "
                  f"@ {row['fps']} fps  loop={row['loop']}")
    return _report(payload, as_json, EXIT_OK)
```

Extend `_handler_for` with `"cards": run_cards_cmd`.

- [ ] **Step 5: Run; expect green**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/ /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/ -v
```

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/commands/sprite.py cli/runner.py tests/sprite/test_cli_sprite_dispatch.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): --sprite-cards action-card generation"
```

---

### Task 5: `--sprite-render` — video, sheet, and edit-chain routes with cost estimate

**Files:**
- Modify: `cli/commands/sprite.py` (append `_apply_provider_overrides`, `_image_provider`, `_render_video_route`, `_render_image_route`, `run_render_cmd`; extend `_handler_for`)
- Modify: `tests/sprite/test_cli_sprite_dispatch.py` (append)

**Interfaces:**
- Consumes (sub-projects 2, 6, 1): `core.sprite.generation.queue.ActionQueue(project, *, api_key, auth_mode, progress, token, log, max_concurrent=1)` with `enqueue(ids)` and `run() -> Dict[str, ClipRecord | SpriteGenerationError]`; `core.sprite.generation.cost.estimate_action`; `core.sprite.generation.errors.classify_provider_error(exc) -> SpriteGenerationError`; `core.sprite.generation.image_route.generate_sheet(provider, character, action, out_png, *, frames, plate_color, model, log) -> Path`, `edit_chain(provider, character, action, out_dir, *, frames, pose_instructions, plate_color, model, log, token) -> List[Path]`, `generate_pose_instructions(action, frames, *, provider, model, api_key, log) -> List[str]`; `core.sprite.slicing.guess_grid(image, key_color) -> GridGuess(columns, rows, cell, confidence)`, `slice_sheet`; `core.sprite.pipeline.stage_dir`; `providers.get_provider(name, config)`.
- Produces: `_apply_provider_overrides(project, args)`, `_image_provider(args) -> (name, provider)`, `_render_video_route(project, actions, args, token) -> List[dict]`, `_render_image_route(project, actions, args, token, route) -> List[dict]`, `run_render_cmd(args, token=None)`.
- Default action set: draft/failed/queued cards (`_select_actions(default="renderable")`); `--sprite-actions` overrides. Exit 1 when any selected action failed; the payload lists `failed` names and always carries `estimate` (decision 8).

- [ ] **Step 1: Append the failing tests**

```python
# tests/sprite/test_cli_sprite_dispatch.py (append)
from cli.commands.sprite import run_render_cmd
from core.sprite.generation.errors import SpriteGenerationError


class _Quota(SpriteGenerationError):
    user_message = "Quota exceeded. Try again in a minute."
    retryable = True


def _cost_patches():
    return (patch("core.sprite.generation.cost.estimate_action", side_effect=lambda g, a: 0.4),
            patch("core.sprite.generation.cost.estimate_project", return_value=(0.4, 0)))


def test_render_video_route_uses_queue_and_reports_estimate(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[_card("idle"), _card("walk", status="rendered")])
    clip = SimpleNamespace(path=proj.project_dir / "clips" / "idle-id.mp4", actual_usd=0.5,
                           operation_id="op-1")
    queue = MagicMock()
    queue.run.return_value = {"idle-id": clip}
    ea, ep = _cost_patches()
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.generation.queue.ActionQueue", return_value=queue) as AQ, \
         patch("cli.commands.sprite.resolve_api_key", return_value=("gk", "config")), ea, ep:
        rc = run_render_cmd(_ns(sprite_render=True, sprite_project="hero",
                                video_provider="veo", video_model="veo-x", json=True))
    assert rc == 0
    AQ.assert_called_once()
    kw = AQ.call_args.kwargs
    assert kw["api_key"] == "gk" and kw["auth_mode"] == "api-key"
    assert kw["progress"] is sprite_cli._progress and kw["log"] is sprite_cli._log_and_emit
    queue.enqueue.assert_called_once_with(["idle-id"])          # renderable cards only
    assert proj.generation.provider == "veo" and proj.generation.model == "veo-x"
    out = json.loads(capsys.readouterr().out)
    assert out["route"] == "video" and out["failed"] == []
    row = out["actions"][0]
    assert row["name"] == "idle" and row["clip"].endswith("idle-id.mp4")
    assert row["operation_id"] == "op-1" and row["actual_usd"] == 0.5
    assert row["estimated_usd"] == 0.4
    assert out["estimate"]["sheet_estimated_usd"] == 0.4
    assert list((proj.project_dir / "runs").glob("render-*.json"))


def test_render_video_route_keeps_project_provider_when_flags_unset(tmp_path):
    proj = _fake_project(tmp_path, actions=[_card("idle")])
    queue = MagicMock()
    queue.run.return_value = {"idle-id": SimpleNamespace(path="c.mp4", actual_usd=None, operation_id=None)}
    ea, ep = _cost_patches()
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.generation.queue.ActionQueue", return_value=queue), \
         patch("cli.commands.sprite.resolve_api_key", return_value=("gk", "config")), ea, ep:
        run_render_cmd(_ns(sprite_render=True, sprite_project="hero"))
    assert proj.generation.provider == "omni"


def test_render_video_route_reports_failed_action_exit_one(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[_card("idle"), _card("walk")])
    queue = MagicMock()
    queue.run.return_value = {"idle-id": SimpleNamespace(path="c.mp4", actual_usd=0.1, operation_id="o"),
                              "walk-id": _Quota("429")}
    ea, ep = _cost_patches()
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.generation.queue.ActionQueue", return_value=queue), \
         patch("cli.commands.sprite.resolve_api_key", return_value=("gk", "config")), ea, ep:
        rc = run_render_cmd(_ns(sprite_render=True, sprite_project="hero", json=True))
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["status"] == "failed" and out["failed"] == ["walk"]
    assert out["actions"][1]["error"] == _Quota.user_message


def test_render_with_nothing_to_render_is_usage_error(tmp_path):
    proj = _fake_project(tmp_path, actions=[_card("idle", status="rendered")])
    with patch.object(sprite_cli, "_load_project", return_value=proj):
        with pytest.raises(SpriteCliError, match="No actions to render"):
            run_render_cmd(_ns(sprite_render=True, sprite_project="hero"))


def test_render_sheet_route_generates_slices_and_processes(tmp_path, capsys):
    from PIL import Image
    proj = _fake_project(tmp_path, actions=[_card("idle")])
    proj.character_source = tmp_path / "hero" / "source" / "character.png"

    def _fake_sheet(provider, character, action, out_png, **kw):
        out_png.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (16, 2), "green").save(out_png)
        return out_png

    guess = SimpleNamespace(columns=8, rows=1, cell=(2, 2), confidence=0.9)
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("providers.get_provider", return_value="PROVIDER") as gp, \
         patch("cli.commands.sprite.resolve_api_key", return_value=("k", "config")), \
         patch("core.sprite.generation.image_route.generate_sheet", side_effect=_fake_sheet) as gs, \
         patch("core.sprite.slicing.guess_grid", return_value=guess), \
         patch("core.sprite.slicing.slice_sheet", return_value=[1] * 8) as sl, \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.pipeline.run_pipeline", return_value={"extract": [1] * 8}) as run, \
         patch("core.sprite.generation.cost.estimate_action", return_value=None), \
         patch("core.sprite.generation.cost.estimate_project", return_value=(None, 1)):
        rc = run_render_cmd(_ns(sprite_render=True, sprite_project="hero", sprite_route="sheet",
                                provider="openai", model="gpt-image-2", json=True))
    assert rc == 0
    gp.assert_called_once_with("openai", {"api_key": "k", "auth_mode": "api-key"})
    kw = gs.call_args.kwargs
    assert kw["frames"] == 8 and kw["plate_color"] == "#00FF00" and kw["model"] == "gpt-image-2"
    sheet_png = proj.project_dir / "sheets" / "idle-id.png"
    assert gs.call_args.args[3] == sheet_png
    assert json.loads(sheet_png.with_suffix(".json").read_text())["grid"] == [8, 1]
    sl.assert_called_once_with(sheet_png, tmp_path / "stages" / "idle-id" / "extract", 8, 1)
    assert run.call_args.kwargs["force"] is True and run.call_args.kwargs["upto"] == "stabilize"
    out = json.loads(capsys.readouterr().out)
    assert out["actions"][0]["route"] == "sheet" and out["actions"][0]["frames"] == 8
    assert proj.actions[0].status == "processed"


def test_render_sheet_route_low_confidence_falls_back_to_target_frames(tmp_path):
    from PIL import Image
    proj = _fake_project(tmp_path, actions=[_card("idle", target_frames=6)])
    proj.character_source = tmp_path / "c.png"

    def _fake_sheet(provider, character, action, out_png, **kw):
        out_png.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (12, 2), "green").save(out_png)
        return out_png

    guess = SimpleNamespace(columns=3, rows=2, cell=(4, 1), confidence=0.2)
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("providers.get_provider", return_value="P"), \
         patch("cli.commands.sprite.resolve_api_key", return_value=("k", "config")), \
         patch("core.sprite.generation.image_route.generate_sheet", side_effect=_fake_sheet), \
         patch("core.sprite.slicing.guess_grid", return_value=guess), \
         patch("core.sprite.slicing.slice_sheet", return_value=[1] * 6) as sl, \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.pipeline.run_pipeline", return_value={"extract": [1] * 6}), \
         patch("core.sprite.generation.cost.estimate_action", return_value=None), \
         patch("core.sprite.generation.cost.estimate_project", return_value=(None, 1)):
        run_render_cmd(_ns(sprite_render=True, sprite_project="hero", sprite_route="sheet"))
    assert sl.call_args.args[2:] == (6, 1)


def test_render_edit_chain_route_uses_pose_steps(tmp_path):
    proj = _fake_project(tmp_path, actions=[_card("jump", target_frames=5)])
    proj.character_source = tmp_path / "c.png"
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("providers.get_provider", return_value="P"), \
         patch("cli.commands.sprite.resolve_api_key", return_value=("k", "config")), \
         patch("core.llm_models.resolve_model", return_value="llm-m"), \
         patch("core.sprite.generation.image_route.generate_pose_instructions",
               return_value=["crouch", "launch", "apex", "fall", "land"]) as gp, \
         patch("core.sprite.generation.image_route.edit_chain", return_value=[1] * 5) as ec, \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.pipeline.run_pipeline", return_value={"extract": [1] * 5}), \
         patch("core.sprite.generation.cost.estimate_action", return_value=None), \
         patch("core.sprite.generation.cost.estimate_project", return_value=(None, 1)):
        rc = run_render_cmd(_ns(sprite_render=True, sprite_project="hero",
                                sprite_route="edit-chain", sprite_llm_provider="openai"))
    assert rc == 0
    assert gp.call_args.args == (proj.actions[0], 5)
    assert gp.call_args.kwargs["provider"] == "openai" and gp.call_args.kwargs["model"] == "llm-m"
    kw = ec.call_args.kwargs
    assert kw["pose_instructions"] == ["crouch", "launch", "apex", "fall", "land"]
    assert kw["frames"] == 5
    assert ec.call_args.args[3] == tmp_path / "stages" / "jump-id" / "extract"


def test_render_image_route_classifies_provider_errors_and_continues(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[_card("idle"), _card("walk")])
    proj.character_source = tmp_path / "c.png"
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("providers.get_provider", return_value="P"), \
         patch("cli.commands.sprite.resolve_api_key", return_value=("k", "config")), \
         patch("core.llm_models.resolve_model", return_value="m"), \
         patch("core.sprite.generation.image_route.generate_pose_instructions", return_value=["a"]), \
         patch("core.sprite.generation.image_route.edit_chain",
               side_effect=[RuntimeError("safety block"), [1]]), \
         patch("core.sprite.generation.errors.classify_provider_error",
               return_value=_Quota("x")) as cls, \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.pipeline.run_pipeline", return_value={"extract": [1]}), \
         patch("core.sprite.generation.cost.estimate_action", return_value=None), \
         patch("core.sprite.generation.cost.estimate_project", return_value=(None, 1)):
        rc = run_render_cmd(_ns(sprite_render=True, sprite_project="hero",
                                sprite_route="edit-chain", json=True))
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    cls.assert_called_once()
    assert out["failed"] == ["idle"]
    assert proj.actions[0].status == "failed" and proj.actions[0].error == _Quota.user_message
    assert proj.actions[1].status == "processed"


def test_render_image_route_needs_character_source(tmp_path):
    proj = _fake_project(tmp_path, actions=[_card("idle")])
    with patch.object(sprite_cli, "_load_project", return_value=proj):
        with pytest.raises(SpriteCliError, match="no character source"):
            run_render_cmd(_ns(sprite_render=True, sprite_project="hero", sprite_route="sheet"))
```

- [ ] **Step 2: Run; expect `ImportError: run_render_cmd`**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_dispatch.py -v -k render
```

- [ ] **Step 3: Append to `cli/commands/sprite.py`** (before `# ---------- dispatcher ----------`)

```python
# ---------- verbs: render ----------

def _apply_provider_overrides(project, args) -> None:
    """--video-provider / --video-model win over the project's generation settings."""
    video_provider = getattr(args, "video_provider", None)
    video_model = getattr(args, "video_model", None)
    if video_provider:
        project.generation.provider = video_provider
    if video_model:
        project.generation.model = video_model


def _image_provider(args) -> tuple:
    """Image provider for the sheet / edit-chain routes (google or openai)."""
    from providers import get_provider
    name = (getattr(args, "provider", None) or "google").strip().lower()
    if name not in ("google", "openai"):
        raise SpriteCliError("--sprite-route sheet/edit-chain needs --provider google or openai.")
    key, _src = resolve_api_key(getattr(args, "api_key", None),
                                getattr(args, "api_key_file", None), name)
    if not key:
        raise SpriteCliError(
            f"No {name} API key found. Use --api-key/--api-key-file or store one in Settings.")
    provider = get_provider(name, {"api_key": key,
                                   "auth_mode": getattr(args, "auth_mode", "api-key")})
    return name, provider


def _render_video_route(project, actions, args, token) -> List[Dict[str, Any]]:
    """Route A: ActionQueue renders each card (Omni/Veo) and runs the spine up to stabilize."""
    from core.sprite.generation.cost import estimate_action
    from core.sprite.generation.queue import ActionQueue
    key = _google_key(args)
    queue = ActionQueue(project, api_key=key, auth_mode=getattr(args, "auth_mode", "api-key"),
                        progress=_progress, token=token, log=_log_and_emit)
    queue.enqueue([card.id for card in actions])
    _emit(f"[render] {len(actions)} action(s) via {project.generation.provider}"
          f"/{project.generation.model or 'default'}")
    results = queue.run()
    rows = []
    for card in actions:
        result = results.get(card.id)
        ok = result is not None and not isinstance(result, Exception)
        if ok:
            error = None
        elif result is None:
            error = "no result from the queue"
        else:
            error = getattr(result, "user_message", None) or str(result)
        rows.append({"id": card.id, "name": card.name, "route": "video", "status": card.status,
                     "estimated_usd": estimate_action(project.generation, card),
                     "actual_usd": getattr(result, "actual_usd", None) if ok else None,
                     "clip": str(getattr(result, "path", "")) if ok else None,
                     "operation_id": getattr(result, "operation_id", None) if ok else None,
                     "error": error})
    return rows


def _render_image_route(project, actions, args, token, route: str) -> List[Dict[str, Any]]:
    """Route B: one sprite sheet (sliced) or an edit chain per card, then the spine."""
    from PIL import Image
    from core.sprite.generation.errors import classify_provider_error
    from core.sprite.generation.image_route import (edit_chain, generate_pose_instructions,
                                                    generate_sheet)
    from core.sprite.pipeline import stage_dir
    from core.sprite.slicing import guess_grid, slice_sheet
    if not project.character_source:
        raise SpriteCliError("The project has no character source. Run --sprite-new first.")
    provider_name, provider = _image_provider(args)
    model = getattr(args, "model", None)
    character = Path(project.character_source)
    rows: List[Dict[str, Any]] = []
    for card in actions:
        if token is not None:
            token.raise_if_cancelled()
        out_dir = stage_dir(project, card, "extract")
        try:
            if route == "sheet":
                sheet_png = Path(project.project_dir) / "sheets" / f"{card.id}.png"
                _emit(f"[sheet] {card.name}: {card.target_frames} frames via {provider_name}")
                generate_sheet(provider, character, card, sheet_png, frames=card.target_frames,
                               plate_color=project.plate_color, model=model, log=_log_and_emit)
                with Image.open(sheet_png) as img:
                    guess = guess_grid(img, key_color=project.plate_color)
                if guess.confidence >= 0.6:
                    columns, grid_rows = guess.columns, guess.rows
                else:
                    columns, grid_rows = card.target_frames, 1
                _emit(f"[sheet] {card.name}: grid {columns}x{grid_rows} "
                      f"(confidence {guess.confidence:.2f})")
                _write_sidecar(sheet_png, {"action": card.name, "action_id": card.id,
                                           "provider": provider_name, "model": model,
                                           "frames": card.target_frames,
                                           "grid": [columns, grid_rows],
                                           "plate_color": project.plate_color})
                frames = slice_sheet(sheet_png, out_dir, columns, grid_rows)
            else:
                llm_provider, llm_model, llm_key = _llm_settings(args, project)
                steps = generate_pose_instructions(card, card.target_frames, provider=llm_provider,
                                                   model=llm_model, api_key=llm_key,
                                                   log=_log_and_emit)
                _emit(f"[edit-chain] {card.name}: {len(steps)} steps via {provider_name}")
                frames = edit_chain(provider, character, card, out_dir, frames=card.target_frames,
                                    pose_instructions=steps, plate_color=project.plate_color,
                                    model=model, log=_log_and_emit, token=token)
            card.clip = None
            card.status = "rendered"
            card.error = None
            counts = _run_pipeline_for(project, card, args, token, "stabilize", force=True)
            rows.append({"id": card.id, "name": card.name, "route": route, "status": card.status,
                         "frames": len(frames), "stages": counts, "error": None})
        except Cancelled:
            project.save()
            raise
        except SpriteCliError:
            raise
        except Exception as exc:  # noqa: BLE001 - classify, record, continue with the next card
            err = exc if isinstance(exc, SpriteGenerationError) else classify_provider_error(exc)
            card.status = "failed"
            card.error = getattr(err, "user_message", None) or str(err)
            logger.error("Sprite render (%s, %s) failed: %s", route, card.name, card.error,
                         exc_info=True)
            _emit(f"[{route}] {card.name} failed: {card.error}")
            rows.append({"id": card.id, "name": card.name, "route": route, "status": card.status,
                         "frames": 0, "stages": {}, "error": card.error})
        project.save()
    return rows


def run_render_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-render: render draft/failed cards (or --sprite-actions) through one route."""
    project = _load_project(args)
    route = getattr(args, "sprite_route", None) or "video"
    actions = _select_actions(project, args, default="renderable")
    if not actions:
        raise SpriteCliError(
            "No actions to render: every card is already rendered, or --sprite-actions matched "
            "none. Run --sprite-cards first, or name cards with --sprite-actions.")
    _apply_provider_overrides(project, args)
    project.save()
    if route == "video":
        rows = _render_video_route(project, actions, args, token)
    else:
        rows = _render_image_route(project, actions, args, token, route)
    project_file = project.save()
    failed = [row["name"] for row in rows if row.get("error")]
    error = f"{len(failed)} action(s) failed: {', '.join(failed)}" if failed else None
    payload = _status_payload("render", not failed, project=project_file, error=error,
                              route=route, provider=project.generation.provider,
                              model=project.generation.model or "(default)",
                              actions=rows, failed=failed, estimate=_estimate_rows(project))
    _run_record(project, "render", payload)
    return _report(payload, bool(getattr(args, "json", False)),
                   EXIT_FAILED if failed else EXIT_OK)
```

Extend `_handler_for` with `"render": run_render_cmd`.

- [ ] **Step 4: Run; expect green**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/ -v
```

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/commands/sprite.py tests/sprite/test_cli_sprite_dispatch.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): --sprite-render (video, sheet, edit-chain routes) with cost estimate"
```

---

### Task 6: `--sprite-process` — pipeline runner

**Files:**
- Modify: `cli/commands/sprite.py` (append `run_process_cmd`; extend `_handler_for`)
- Modify: `tests/sprite/test_cli_sprite_dispatch.py` (append)

**Interfaces:**
- Consumes: `core.sprite.pipeline.run_pipeline`, `stage_dir` (Task 3 helper `_run_pipeline_for`).
- Produces: `run_process_cmd(args, token=None)`. Default `--sprite-upto` is `pixel`; `--force` re-runs every stage. An action without a clip and without an extract dir is skipped and listed under `skipped`. One failing action does not stop the others; exit 1 when any failed.

- [ ] **Step 1: Append the failing tests**

```python
# tests/sprite/test_cli_sprite_dispatch.py (append)
from cli.commands.sprite import run_process_cmd, run_sprite_cmd
from core.sprite.pipeline import Cancelled


def test_process_runs_ready_actions_only(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[
        _card("idle", clip=SimpleNamespace(path="c.mp4")), _card("walk"), _card("jump")])
    (tmp_path / "stages" / "walk-id" / "extract").mkdir(parents=True)
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.pipeline.run_pipeline", return_value={"pixel": [1, 2]}) as run:
        rc = run_process_cmd(_ns(sprite_process=True, sprite_project="hero", json=True))
    assert rc == 0
    assert run.call_count == 2
    assert run.call_args.kwargs["upto"] == "pixel" and run.call_args.kwargs["force"] is False
    out = json.loads(capsys.readouterr().out)
    assert [r["name"] for r in out["actions"]] == ["idle", "walk"]
    assert out["skipped"] == ["jump"] and out["upto"] == "pixel"
    assert list((proj.project_dir / "runs").glob("process-*.json"))


def test_process_passes_upto_force_and_action_filter(tmp_path):
    proj = _fake_project(tmp_path, actions=[
        _card("idle", clip=SimpleNamespace(path="a")), _card("walk", clip=SimpleNamespace(path="b"))])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.pipeline.run_pipeline", return_value={"key": [1]}) as run:
        rc = run_process_cmd(_ns(sprite_process=True, sprite_project="hero",
                                 sprite_actions="walk", sprite_upto="key", force=True))
    assert rc == 0
    run.assert_called_once()
    assert run.call_args.args[1].name == "walk"
    assert run.call_args.kwargs["upto"] == "key" and run.call_args.kwargs["force"] is True


def test_process_continues_after_a_failure_and_exits_one(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[
        _card("idle", clip=SimpleNamespace(path="a")), _card("walk", clip=SimpleNamespace(path="b"))])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.pipeline.run_pipeline",
               side_effect=[RuntimeError("ffmpeg missing"), {"pixel": [1]}]):
        rc = run_process_cmd(_ns(sprite_process=True, sprite_project="hero", json=True))
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["failed"] == ["idle"] and out["actions"][0]["error"] == "ffmpeg missing"
    assert proj.actions[0].status == "failed" and proj.actions[1].status == "processed"


def test_process_nothing_ready_is_usage_error(tmp_path):
    proj = _fake_project(tmp_path, actions=[_card("idle")])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)):
        with pytest.raises(SpriteCliError, match="No action has frames"):
            run_process_cmd(_ns(sprite_process=True, sprite_project="hero"))


def test_process_cancel_reports_cancelled_via_dispatcher(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[_card("idle", clip=SimpleNamespace(path="a"))])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.pipeline.stage_dir", side_effect=_stage_dir_factory(tmp_path)), \
         patch("core.sprite.pipeline.run_pipeline", side_effect=Cancelled()):
        rc = run_sprite_cmd(_ns(sprite_process=True, sprite_project="hero", json=True))
    out = json.loads(capsys.readouterr().out)
    assert rc == 130 and out["status"] == "cancelled" and out["verb"] == "process"
    assert proj.saves >= 1                                     # progress persisted before exit
```

- [ ] **Step 2: Run; expect `ImportError: run_process_cmd`**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_dispatch.py -v -k process
```

- [ ] **Step 3: Append to `cli/commands/sprite.py`** (before `# ---------- dispatcher ----------`)

```python
# ---------- verbs: process ----------

def run_process_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-process: run the spine for every action that has frames (or --sprite-actions)."""
    from core.sprite.pipeline import stage_dir
    project = _load_project(args)
    selected = _select_actions(project, args, default="all")
    ready = [card for card in selected
             if card.clip is not None or Path(stage_dir(project, card, "extract")).exists()]
    if not ready:
        raise SpriteCliError(
            "No action has frames to process. Render (--sprite-render) or import first.")
    skipped = [card.name for card in selected if card not in ready]
    upto = _pipeline_upto(args, "pixel")
    force = bool(getattr(args, "force", False))
    rows: List[Dict[str, Any]] = []
    for card in ready:
        if token is not None:
            token.raise_if_cancelled()
        try:
            counts = _run_pipeline_for(project, card, args, token, "pixel")
            rows.append({"id": card.id, "name": card.name, "status": card.status,
                         "stages": counts, "error": None})
        except Cancelled:
            project.save()
            raise
        except Exception as exc:  # noqa: BLE001 - record per action, continue with the rest
            card.status = "failed"
            card.error = getattr(exc, "user_message", None) or str(exc)
            logger.error("Sprite process (%s) failed: %s", card.name, card.error, exc_info=True)
            _emit(f"[pipeline] {card.name} failed: {card.error}")
            rows.append({"id": card.id, "name": card.name, "status": card.status,
                         "stages": {}, "error": card.error})
        project.save()
    project_file = project.save()
    failed = [row["name"] for row in rows if row["error"]]
    error = f"{len(failed)} action(s) failed: {', '.join(failed)}" if failed else None
    payload = _status_payload("process", not failed, project=project_file, error=error,
                              upto=upto, force=force, actions=rows, failed=failed,
                              skipped=skipped)
    _run_record(project, "process", payload)
    return _report(payload, bool(getattr(args, "json", False)),
                   EXIT_FAILED if failed else EXIT_OK)
```

Extend `_handler_for` with `"process": run_process_cmd`.

- [ ] **Step 4: Run; expect green**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/ -v
```

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/commands/sprite.py tests/sprite/test_cli_sprite_dispatch.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): --sprite-process pipeline runner"
```

---

### Task 7: `--sprite-export` — engine presets, profiles, format overrides

**Files:**
- Modify: `cli/commands/sprite.py` (append `_profiles_for`, `_filter_meta`, `_export_formats`, `run_export_cmd`; extend `_handler_for`)
- Modify: `tests/sprite/test_cli_sprite_dispatch.py` (append)

**Interfaces:**
- Consumes (sub-projects 1, 6; confirmed by the sub-project 6 planner on 2026-08-29): `core.sprite.exporters.engine_presets.ENGINE_PRESETS: Dict[str, EnginePreset]` (keys unity, godot4, phaser3, pixijs, unreal, libgdx, rpgmaker_mz, web_preview; fields `id, label, formats, grid, pivot, name_template, how_to_import` — a 2–4 sentence user-facing string), `FORMAT_IDS` (= `SPRITE_EXPORT_FORMATS`), `export_with_preset(meta, preset_id, out_dir) -> List[Path]`, `fps_reconciliation(meta, "godot" | "gif") -> List[str]` (rounding-drift notes); `core.sprite.exporters.grid.export_grid(meta, out_png, opts) -> SheetMeta`, `aseprite_json.export_aseprite_json(meta, out_json, *, image_name, layout="hash")`, `texturepacker_json.export_texturepacker_json(...)`, `png_sequence.export_png_sequence(meta, out_dir) -> List[Path]`, `gif.export_gif(meta, tag, out_gif, *, loop=0) -> Path`, `godot_tres.export_godot_tres(meta, out_tres, *, atlas_res_path) -> Path`, `aseprite_native.export_aseprite(meta, out_ase) -> Path`; `core.sprite.models.SheetMeta` (fields `title, frames, tags, profile`, method `frames_for(tag)`), `TagMeta(name, from_index, to_index, ...)`; `SpriteProject.sheet_meta(profile) -> SheetMeta`, `SpriteProject.profiles: List[OutputProfile(name, enabled, ...)]`.
- Produces: `_profiles_for(project, args) -> List[str]`, `_filter_meta(meta, names) -> SheetMeta`, `_export_formats(meta, formats, out_dir, preset) -> List[Path]`, `run_export_cmd(args, token=None)`.
- Output tree: `<-o or <project>/exports>/<profile>/<preset>/…` plus `export.json` in each preset folder (the sidecar). The CLI never purges intermediates: purge-after-export is a GUI preference (design §1.6) that needs the confirmation dialog.

- [ ] **Step 1: Append the failing tests**

```python
# tests/sprite/test_cli_sprite_dispatch.py (append)
from cli.commands.sprite import _filter_meta, run_export_cmd


def _preset(formats=("grid", "gif")):
    return SimpleNamespace(id="web_preview", label="Web preview", formats=tuple(formats),
                           grid=SimpleNamespace(columns=0), pivot=(0.5, 1.0),
                           name_template="{title}_{tag}_{frame01}.png",
                           how_to_import="Open index.html in a browser.")


def test_export_runs_the_preset_per_enabled_profile(tmp_path, capsys):
    proj = _fake_project(tmp_path, actions=[_card("idle", status="processed")])
    out_base = tmp_path / "out"

    def _fake_export(meta, preset_id, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        f = out_dir / f"{meta.title}_{meta.profile}.png"
        f.write_bytes(b"png")
        return [f]

    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.exporters.engine_presets.ENGINE_PRESETS", {"web_preview": _preset()}), \
         patch("core.sprite.exporters.engine_presets.export_with_preset",
               side_effect=_fake_export) as ex, \
         patch("core.sprite.exporters.engine_presets.fps_reconciliation",
               side_effect=lambda meta, target: [f"{target}: 12 fps = 83 ms per frame, rounded"]) as fps:
        rc = run_export_cmd(_ns(sprite_export=True, sprite_project="hero", out=str(out_base),
                                json=True))
    assert rc == 0
    assert [c.args[1] for c in ex.call_args_list] == ["web_preview", "web_preview"]
    assert [c.args[2] for c in ex.call_args_list] == [out_base / "hd" / "web_preview",
                                                      out_base / "pixel" / "web_preview"]
    record = json.loads((out_base / "hd" / "web_preview" / "export.json").read_text())
    assert record["profile"] == "hd" and record["files"][0].endswith("hero_hd.png")
    assert record["how_to_import"] == "Open index.html in a browser."
    assert record["notes"] == ["gif: 12 fps = 83 ms per frame, rounded"]   # gif in formats, godot not
    assert [c.args[1] for c in fps.call_args_list] == ["gif", "gif"]
    out = json.loads(capsys.readouterr().out)
    assert out["preset"] == "web_preview" and out["profiles"] == ["hd", "pixel"]
    assert out["formats"] == ["grid", "gif"] and len(out["exports"]) == 2


def test_export_default_dir_is_project_exports(tmp_path):
    proj = _fake_project(tmp_path, pixel_enabled=False)
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.exporters.engine_presets.ENGINE_PRESETS", {"godot4": _preset()}), \
         patch("core.sprite.exporters.engine_presets.export_with_preset", return_value=[]) as ex, \
         patch("core.sprite.exporters.engine_presets.fps_reconciliation", return_value=[]):
        rc = run_export_cmd(_ns(sprite_export=True, sprite_project="hero", sprite_preset="godot4"))
    assert rc == 0
    ex.assert_called_once()
    assert ex.call_args.args[2] == proj.project_dir / "exports" / "hd" / "godot4"


def test_export_disabled_profile_is_usage_error(tmp_path):
    proj = _fake_project(tmp_path, pixel_enabled=False)
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.exporters.engine_presets.ENGINE_PRESETS", {"web_preview": _preset()}):
        with pytest.raises(SpriteCliError, match="not enabled"):
            run_export_cmd(_ns(sprite_export=True, sprite_project="hero", sprite_profile="pixel"))


def test_export_no_frames_is_usage_error(tmp_path):
    proj = _fake_project(tmp_path)
    proj.sheet_meta = lambda profile: SimpleNamespace(title="hero", profile=profile, frames=[], tags=[])
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.exporters.engine_presets.ENGINE_PRESETS", {"web_preview": _preset()}):
        with pytest.raises(SpriteCliError, match="no processed frames"):
            run_export_cmd(_ns(sprite_export=True, sprite_project="hero"))


def test_export_formats_override_calls_individual_exporters(tmp_path):
    proj = _fake_project(tmp_path, pixel_enabled=False)
    meta = SimpleNamespace(title="hero", profile="hd", frames=[1, 2],
                           tags=[SimpleNamespace(name="idle"), SimpleNamespace(name="walk")])
    proj.sheet_meta = lambda profile: meta
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.exporters.engine_presets.ENGINE_PRESETS", {"unity": _preset()}), \
         patch("core.sprite.exporters.engine_presets.export_with_preset") as ex, \
         patch("core.sprite.exporters.engine_presets.fps_reconciliation", return_value=[]), \
         patch("core.sprite.exporters.grid.export_grid", return_value=meta) as grid, \
         patch("core.sprite.exporters.texturepacker_json.export_texturepacker_json") as tp, \
         patch("core.sprite.exporters.gif.export_gif", side_effect=lambda m, t, p: p) as gif:
        rc = run_export_cmd(_ns(sprite_export=True, sprite_project="hero", sprite_preset="unity",
                                sprite_formats="texturepacker_json,gif", out=str(tmp_path / "o")))
    assert rc == 0
    ex.assert_not_called()
    out_dir = tmp_path / "o" / "hd" / "unity"
    grid.assert_called_once()                                  # rects are needed for the JSON
    assert grid.call_args.args[1] == out_dir / "hero_hd.png"
    tp.assert_called_once()
    assert tp.call_args.kwargs["image_name"] == "hero_hd.png"
    assert [c.args[2].name for c in gif.call_args_list] == ["hero_idle.gif", "hero_walk.gif"]


def test_export_unknown_format_is_usage_error(tmp_path):
    proj = _fake_project(tmp_path, pixel_enabled=False)
    with patch.object(sprite_cli, "_load_project", return_value=proj), \
         patch("core.sprite.exporters.engine_presets.ENGINE_PRESETS", {"web_preview": _preset()}):
        with pytest.raises(SpriteCliError, match="Unknown --sprite-formats: webp"):
            run_export_cmd(_ns(sprite_export=True, sprite_project="hero", sprite_formats="gif,webp"))


def test_filter_meta_keeps_named_tags_and_reindexes():
    from core.sprite.models import FrameMeta, SheetMeta, TagMeta
    frames = [FrameMeta(name=f"hero_{i}", source_path=None, frame=(0, 0, 0, 0)) for i in range(4)]
    meta = SheetMeta(title="hero", frames=frames,
                     tags=[TagMeta("idle", 0, 1), TagMeta("walk", 2, 3)])
    kept = _filter_meta(meta, {"walk"})
    assert [f.name for f in kept.frames] == ["hero_2", "hero_3"]
    assert len(kept.tags) == 1
    assert (kept.tags[0].name, kept.tags[0].from_index, kept.tags[0].to_index) == ("walk", 0, 1)
    assert kept.title == "hero"
```

- [ ] **Step 2: Run; expect `ImportError: run_export_cmd`**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_dispatch.py -v -k "export or filter_meta"
```

- [ ] **Step 3: Append to `cli/commands/sprite.py`** (before `# ---------- dispatcher ----------`)

```python
# ---------- verbs: export ----------

def _profiles_for(project, args) -> List[str]:
    """Profiles to export: both enabled ones, or the one named (which must be enabled)."""
    wanted = getattr(args, "sprite_profile", None) or "both"
    enabled = [profile.name for profile in project.profiles if profile.enabled]
    if wanted == "both":
        if not enabled:
            raise SpriteCliError("No output profile is enabled in the project.")
        return enabled
    if wanted not in enabled:
        raise SpriteCliError(
            f"Profile '{wanted}' is not enabled in the project "
            f"(enabled: {', '.join(enabled) or 'none'}).")
    return [wanted]


def _filter_meta(meta, names):
    """Keep only the tags in `names`; rebuild the frame list and re-index the tags."""
    from dataclasses import replace
    frames = []
    tags = []
    for tag in meta.tags:
        if tag.name not in names:
            continue
        start = len(frames)
        frames.extend(meta.frames_for(tag))
        tags.append(replace(tag, from_index=start, to_index=len(frames) - 1))
    return replace(meta, frames=frames, tags=tags)


def _export_formats(meta, formats: List[str], out_dir: Path, preset) -> List[Path]:
    """--sprite-formats: run the individual exporters (grid first; the JSON/tres need its rects)."""
    from core.sprite.exporters.aseprite_json import export_aseprite_json
    from core.sprite.exporters.aseprite_native import export_aseprite
    from core.sprite.exporters.gif import export_gif
    from core.sprite.exporters.godot_tres import export_godot_tres
    from core.sprite.exporters.grid import export_grid
    from core.sprite.exporters.png_sequence import export_png_sequence
    from core.sprite.exporters.texturepacker_json import export_texturepacker_json
    unknown = [f for f in formats if f not in SPRITE_EXPORT_FORMATS]
    if unknown:
        raise SpriteCliError(f"Unknown --sprite-formats: {', '.join(unknown)}. "
                             f"Choices: {', '.join(SPRITE_EXPORT_FORMATS)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    stem = f"{meta.title}_{meta.profile}"
    png = out_dir / f"{stem}.png"
    if {"grid", "aseprite_json", "texturepacker_json", "godot_tres"} & set(formats):
        meta = export_grid(meta, png, preset.grid)
        written.append(png)
        written.append(png.with_suffix(".json"))   # the grid exporter always writes this sidecar
    if "aseprite_json" in formats:
        path = out_dir / f"{stem}.aseprite.json"
        export_aseprite_json(meta, path, image_name=png.name)
        written.append(path)
    if "texturepacker_json" in formats:
        path = out_dir / f"{stem}.tp.json"
        export_texturepacker_json(meta, path, image_name=png.name)
        written.append(path)
    if "godot_tres" in formats:
        path = out_dir / f"{stem}.tres"
        export_godot_tres(meta, path, atlas_res_path=f"res://{png.name}")
        written.append(path)
    if "png_sequence" in formats:
        written.extend(export_png_sequence(meta, out_dir / "frames"))
    if "gif" in formats:
        for tag in meta.tags:
            written.append(export_gif(meta, tag, out_dir / f"{meta.title}_{tag.name}.gif"))
    if "aseprite_native" in formats:
        written.append(export_aseprite(meta, out_dir / f"{stem}.ase"))
    return written


def run_export_cmd(args, token: Optional[CancelToken] = None) -> int:
    """--sprite-export: preset x profile x formats -> -o DIR (default <project>/exports)."""
    from core.sprite.exporters.engine_presets import (ENGINE_PRESETS, export_with_preset,
                                                      fps_reconciliation)
    project = _load_project(args)
    preset_id = getattr(args, "sprite_preset", None) or "web_preview"
    preset = ENGINE_PRESETS[preset_id]
    formats = _split_csv(getattr(args, "sprite_formats", None))
    profiles = _profiles_for(project, args)
    out_arg = getattr(args, "out", None)
    base = Path(out_arg).expanduser() if out_arg else Path(project.project_dir) / "exports"
    names = None
    if getattr(args, "sprite_actions", None):
        names = {card.name for card in _select_actions(project, args, default="all")}
    results = []
    for profile in profiles:
        if token is not None:
            token.raise_if_cancelled()
        meta = project.sheet_meta(profile)
        if names is not None:
            meta = _filter_meta(meta, names)
        if not meta.frames:
            raise SpriteCliError(
                f"Profile '{profile}' has no processed frames. Run --sprite-process first.")
        out_dir = base / profile / preset_id
        used = formats or list(preset.formats)
        _emit(f"[export] {profile} -> {preset_id} ({', '.join(used)}) -> {out_dir}")
        if formats:
            files = _export_formats(meta, formats, out_dir, preset)
        else:
            files = export_with_preset(meta, preset_id, out_dir)
        notes: List[str] = []
        if "godot_tres" in used:
            notes.extend(fps_reconciliation(meta, "godot"))
        if "gif" in used:
            notes.extend(fps_reconciliation(meta, "gif"))
        for note in notes:
            _emit(f"[export] note: {note}")
        record = {"profile": profile, "preset": preset_id, "out_dir": str(out_dir),
                  "formats": used, "files": [str(f) for f in files],
                  "frames": len(meta.frames), "tags": [t.name for t in meta.tags],
                  "notes": notes, "how_to_import": preset.how_to_import}
        _write_json(out_dir / "export.json", {"status": "completed", "verb": "export",
                                              "project": str(_project_file(project)), **record})
        _emit(f"[export] {preset.how_to_import}")
        results.append(record)
    payload = _status_payload("export", True, project=_project_file(project), output_path=base,
                              preset=preset_id, profiles=profiles,
                              formats=formats or list(preset.formats), exports=results)
    return _report(payload, bool(getattr(args, "json", False)), EXIT_OK)
```

Extend `_handler_for` with `"export": run_export_cmd`. The final mapping has ten entries: new, list, estimate, import_video, import_frames, import_sheet, cards, render, process, export.

- [ ] **Step 4: Run; expect green**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/ -v
```

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/commands/sprite.py tests/sprite/test_cli_sprite_dispatch.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): --sprite-export engine presets, profiles, format overrides"
```

---

### Task 8: Runner dispatch

**Files:**
- Modify: `cli/runner.py` — insert after the video block (lines 250–253), before `# Handle style management verbs` (line 255)
- Create: `tests/sprite/test_cli_sprite_runner.py`

**Interfaces:**
- Consumes: `SPRITE_VERB_ATTRS` (Task 2), `cli.commands.sprite.run_sprite_cmd`.
- Order in `run_cli`: help → lyrics → layout → video → **sprite** → style → image path. A sprite verb never falls through to the image path, so `-o` and `-m` keep their sprite meaning.

- [ ] **Step 1: Write the failing runner tests**

```python
# tests/sprite/test_cli_sprite_runner.py
from unittest.mock import patch

import pytest

from cli.parser import build_arg_parser
from cli.runner import SPRITE_VERB_ATTRS, run_cli


def _args(argv):
    return build_arg_parser().parse_args(argv)


@pytest.mark.parametrize("argv", [
    ["--sprite-new", "hero", "--sprite-source", "c.png"],
    ["--sprite-list"],
    ["--sprite-estimate", "--sprite-project", "hero"],
    ["--sprite-cards", "a slime", "--sprite-project", "hero"],
    ["--sprite-import-video", "c.mp4", "--sprite-project", "hero", "--sprite-actions", "walk"],
    ["--sprite-import-frames", "d/", "--sprite-project", "hero", "--sprite-actions", "walk"],
    ["--sprite-import-sheet", "s.png", "--sprite-grid", "8x1", "--sprite-project", "hero",
     "--sprite-actions", "walk"],
    ["--sprite-render", "--sprite-project", "hero", "-o", "x"],
    ["--sprite-process", "--sprite-project", "hero", "-m", "m"],
    ["--sprite-export", "--sprite-project", "hero", "-o", "out/"],
])
def test_run_cli_routes_every_sprite_verb(argv):
    with patch("cli.commands.sprite.run_sprite_cmd", return_value=0) as m, \
         patch("cli.commands.video.run_video_cmd") as video:
        assert run_cli(_args(argv)) == 0
    m.assert_called_once()
    video.assert_not_called()


def test_run_cli_returns_the_sprite_exit_code():
    with patch("cli.commands.sprite.run_sprite_cmd", return_value=2):
        assert run_cli(_args(["--sprite-list"])) == 2


def test_video_still_routes_to_video():
    with patch("cli.commands.video.run_video_cmd", return_value=0) as video, \
         patch("cli.commands.sprite.run_sprite_cmd") as sprite:
        assert run_cli(_args(["--video", "-p", "x", "-o", "x.mp4"])) == 0
    video.assert_called_once()
    sprite.assert_not_called()


def test_sprite_dispatches_before_style_verbs():
    with patch("cli.commands.sprite.run_sprite_cmd", return_value=0) as sprite, \
         patch("cli.commands.style.run_style_cmd") as style:
        assert run_cli(_args(["--sprite-list", "--style-list"])) == 0
    sprite.assert_called_once()
    style.assert_not_called()


def test_verb_attrs_cover_every_sprite_verb_flag():
    parser = build_arg_parser()
    verbs = {a.dest for a in parser._actions
             if a.dest.startswith("sprite_") and a.dest not in (
                 "sprite_source", "sprite_project", "sprite_genre", "sprite_llm_provider",
                 "sprite_llm_model", "sprite_actions", "sprite_route", "sprite_upto",
                 "sprite_grid", "sprite_preset", "sprite_profile", "sprite_formats")}
    assert verbs == set(SPRITE_VERB_ATTRS)
```

- [ ] **Step 2: Run; expect the routing tests to fail (the image path runs instead)**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_runner.py -v
```

- [ ] **Step 3: Add the dispatch branch to `cli/runner.py`** (after line 253 `return run_video_cmd(args)`)

```python
    # Handle sprite verbs (game-sprite pipeline); exactly one --sprite-* verb per call
    if any(getattr(args, attr, None) for attr in SPRITE_VERB_ATTRS):
        from cli.commands.sprite import run_sprite_cmd
        return run_sprite_cmd(args)
```

- [ ] **Step 4: Run; expect green — then run every CLI test group**

```bash
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/ /mnt/d/Documents/Code/GitHub/ImageAI/tests/video/ /mnt/d/Documents/Code/GitHub/ImageAI/tests/layout/test_cli_layout_dispatch.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/styles/ /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -v
```

- [ ] **Step 5: Smoke the real entry point (no key needed)**

```bash
$PY /mnt/d/Documents/Code/GitHub/ImageAI/main.py --sprite-list --json 2>/dev/null | $PY -c "import json,sys; d=json.load(sys.stdin); print(d['verb'], d['status'], d['count'])"
$PY /mnt/d/Documents/Code/GitHub/ImageAI/main.py --sprite-estimate --sprite-project does-not-exist; echo "exit=$?"
$PY /mnt/d/Documents/Code/GitHub/ImageAI/main.py --help | grep -A3 "sprite animations"
```

Expected: `list completed <n>`; the second command prints `sprite estimate failed: Sprite project not found: does-not-exist. Available: …` on stderr and `exit=2`; the help shows the group.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add cli/runner.py tests/sprite/test_cli_sprite_runner.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(cli): dispatch sprite verbs in run_cli"
```

---

### Task 9: `Docs/Sprite-Tab-Guide.md` — user guide

**Files:**
- Create: `Docs/Sprite-Tab-Guide.md`

**Interfaces:** documentation only. Facts come from the design (§1.5 shortcuts, §1.6 storage, §2 settings, §4.6 presets, decisions 2, 4, 8, 9, 10) and from the CLI built in Tasks 1–8. Before writing, check the GUI plan files (`Plans/2026-08-29-sprite-gui-a-plan.md`, `Plans/2026-08-29-sprite-gui-b-plan.md`) for panel and button labels and use their exact strings. Where a label below differs from the shipped GUI, the shipped GUI wins — fix the guide, not the GUI.

- [ ] **Step 1: Write the guide**

```markdown
# Sprite Tab Guide

The Sprite tab turns one character image and a one-line brief into per-action
animations, then exports them as sprite sheets, PNG sequences, GIFs, and
engine files. It also processes clips and PNG sequences that other tools made,
and it exports single frames.

Design reference: `Plans/2026-08-29-sprite-tab-design.md`.
CLI reference: `Docs/ImageAI-CLI-Guide.md` (section "Sprite animations").

---

## Table of Contents

- [Requirements](#requirements)
- [Workflow](#workflow)
- [Panels](#panels)
- [Generation settings and named configurations](#generation-settings-and-named-configurations)
- [Cost estimate and ledger](#cost-estimate-and-ledger)
- [Output profiles: hd and pixel](#output-profiles-hd-and-pixel)
- [External inputs](#external-inputs)
- [Exports per engine](#exports-per-engine)
- [Purge intermediates after export](#purge-intermediates-after-export)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Command line](#command-line)
- [Where the files are](#where-the-files-are)
- [Troubleshooting](#troubleshooting)

---

## Requirements

- Python 3.11 or newer. The Sprite tab checks `sys.version_info` and tells you when the
  interpreter is too old.
- `ffmpeg` on the PATH (the app can install `imageio-ffmpeg` for you; see Settings).
- `scikit-image` and `scipy` (in `requirements.txt`) for the de-jitter stage. When the
  import fails, the app uses the OpenCV `phaseCorrelate` fallback.
- Optional ML background removal: `pip install -r requirements-sprite-ml.txt` installs
  `mediapipe` and `rembg[cpu]`. `rembg` needs Python 3.11–3.13. The default `rembg`
  model is `isnet-anime` (MIT). The `bria-rmbg` model is non-commercial and is never the
  default.
- A Google API key for the video route (Omni or Veo) and for the Gemini image route. An
  OpenAI key for the gpt-image route. Keys live in the Settings tab.

## Workflow

The tab reads from left to right and top to bottom. Every step writes files that the
next step reads, so you can stop and continue later.

### 1. Create a project and import the character

1. Click **New** in the project header and type a name. The project folder appears under
   `<Images root>/sprites/<name>/`.
2. Drop a character image on the **Character** panel, or click **Import**. You can also
   right-click a result in the Image tab, the History tab, or the Video reference library
   and pick **Send to Sprite**.
3. The app pads the image onto the canvas of the current aspect ratio. It never crops
   and never distorts.
4. Optional: click **Make chroma plate**. Gemini places the same character on a flat
   solid green background (`#00FF00` by default). The plate is the reference image for
   every clip, which keeps the key clean.
5. Optional: click **Generate turnaround**. The app makes front, side, back, and
   three-quarter views. Every render sends them as references, which reduces character
   drift between actions.

### 2. Write the brief and generate action cards

1. In the **Actions** panel, type one line that describes the character and the game,
   for example `a small knight with a lantern, side-scrolling platformer`.
2. Pick a genre: **sidescroller**, **top_down**, or **fighting**. The genre supplies the
   checklist of actions (idle, walk, run, jump, fall, attack, hurt, death for a
   sidescroller).
3. Click **Generate cards**. The text LLM returns one card per action: name, prompt,
   clip length, loop flag, target frame count, and frame rate. Every field is editable.
4. Add, remove, or rename cards. Names are `snake_case` and unique in the project.

### 3. Check the settings and the cost

1. Open **Generation Settings** (gear button). Pick the provider (Omni is the default),
   the model, resolution, aspect ratio, clip length, fps, loop conditioning, and plate
   color. Save the set as a named configuration when you want it again.
2. The **Queue** panel shows the estimate per action and the total per sheet for the
   current settings. There is no spend confirmation dialog: read the estimate, then
   render.

### 4. Render

1. Select cards and click **Render selected** (Ctrl+Enter in the queue panel), or
   **Render all**.
2. The queue renders one card at a time. Each clip lands in `clips/`, and the pipeline
   runs extract → key → cleanup → alpha → stabilize at once, so frames appear in the
   strip while the next clip renders.
3. **Cancel** stops after the current frame. A remote job keeps running at the provider;
   the queue keeps its operation id so you can recover the clip later with **Retry**.
4. A refusal shows the provider's message and names the other provider as an option.
   A quota error retries three times with backoff before it is marked failed.
5. Omni clips can be refined: select a card and click **Refine**, then type an
   instruction such as `make the cape swing less`.

### 5. Review the frames

- The **Frame strip** shows every frame of the selected action. Drag to reorder;
  Delete removes; Ctrl+D duplicates; the duration spin box sets the per-frame time.
- The **Preview** plays the action at its fps, forward, reverse, or ping-pong. The
  **loop-seam meter** shows the difference between the last and first frame (0 = a
  perfect loop).
- The **Pixel view** zooms 1–16× with nearest-neighbour scaling, a pixel grid, and a
  checkerboard behind transparent pixels.
- **Retouch** sends one frame with its neighbours to the image model with an
  instruction. The result is a new file next to the original, so Undo is instant.

### 6. Process

The **Processing** panel groups the stages:

| Group | Controls | What it does |
|---|---|---|
| Key | method (chroma / ml / none), key color picker, tolerance, softness, despill mode | Removes the plate color. `ml` uses mediapipe or rembg when installed. `none` keeps an existing alpha channel. |
| Cleanup | edge decontaminate, choke, feather, despeckle | Cleans the matte edge. |
| Alpha | binary alpha, threshold, defringe | Hard-edged alpha for the pixel profile. |
| Stabilize | anchor, de-jitter, method (phase / centroid), padding | Crops every frame to the union bounding box, pads to the cell, and removes per-frame jitter. |
| Profiles | hd on/off, pixel on/off, cell size, palette size, dither, palette lock | See [Output profiles](#output-profiles-hd-and-pixel). |

Click **Run pipeline** (Ctrl+Enter). Only the stages whose settings changed run again;
raw clips and extracted frames are never overwritten. A per-frame override (right-click
a frame → **Override…**) applies a different setting to one frame.

### 7. Export

1. Click **Export** (Ctrl+Enter in the export dialog).
2. Pick the profile (hd, pixel, or both), the engine preset, and the formats.
3. Pick the output folder. The default is `<project>/exports/<profile>/<preset>/`.
4. **Export selected frame** writes one PNG of the frame under the cursor.

## Panels

| Panel | Where | Purpose |
|---|---|---|
| Project header | top | New, Open, Save, Save As |
| Character | left, top | import / drag-drop, normalize, Make chroma plate, Generate turnaround, key-color picker |
| Actions | left, middle | brief, genre, Generate cards, the editable card list with Render / Refine / Re-render per card |
| Queue | left, bottom | per-card status, estimate per action, sheet total, Cancel, Retry, status console |
| Frame strip | right, top | thumbnails, reorder, duplicate / delete / insert, duration, overrides |
| Preview | right, middle | player, loop mode, tag selector, scrub bar, loop-seam meter |
| Pixel view | right, middle (tab) | integer zoom, grid, checkerboard |
| Processing | right, bottom | key / cleanup / alpha / stabilize / profile groups, Run pipeline |
| Status console | bottom | every LLM request and response, every provider call, every error |

## Generation settings and named configurations

| Setting | Default | Notes |
|---|---|---|
| Provider | omni | `omni` or `veo` |
| Model | provider default | resolved at runtime from the model registry |
| Resolution | 720p | |
| Aspect ratio | 16:9 | the canvas the character is padded onto |
| Clip length | 8 s | Veo loop conditioning forces 8 s |
| fps | 24 | source fps of the clip; extraction picks the sprite fps |
| Loop conditioning | on | Veo first-and-last-frame; ignored by Omni |
| Plate color | #00FF00 | any color; pick one that is absent from the character |
| Turnaround refs | on | sends the turnaround views with every render |
| Include audio | off | Veo only; audio doubles the price |

Named configurations are stored in `<Settings root>/sprite_configs.json`. **Save as…**
stores the current values under a name; the picker loads them; **Delete** removes one.

Cell-size presets: 8, 16, 16×24, 24, 16×32, 32, 48, 64 (default), 96, 128, 256, 512,
720, 1024, and custom W×H. Canvas presets: 320×180, 384×216, 400×240, 480×270, 640×360
with an integer-scale calculator to 720p, 1080p, and 4K. FPS presets: 8, 12 (default),
24, 30, 60.

## Cost estimate and ledger

- The Queue panel and `--sprite-estimate` show the estimate per action and per sheet
  for the current provider, model, clip length, and audio flag.
- When no verified rate exists for a model, the estimate shows **unknown**. It never
  shows a guess. You can set your own rates in `config.json` under
  `sprite.price_overrides`.
- Every render appends a row to the project's cost ledger with the estimated and, when
  the provider reports it, the actual cost. The ledger survives setting changes, so the
  sheet total stays correct when you switch providers mid-project.

## Output profiles: hd and pixel

| | hd | pixel |
|---|---|---|
| Cell | large (256–1024) | small (16–128) |
| Alpha | soft | binary (threshold + defringe) |
| Downscale | Lanczos, proportional | integer box filter, proportional, then pad |
| Palette | none | shared across all frames (default 32 colors) |
| Dither | none | none / Bayer 2, 4, 8 / Floyd–Steinberg |

Turn either profile on or off. Every exporter runs once per enabled profile. **Palette
lock** keeps the palette fixed when you add or retouch frames; **Rebuild palette**
recomputes it from all frames. A source smaller than the cell triggers a warning,
because an upscale cannot add detail.

## External inputs

You do not need to generate the frames in ImageAI.

| Input | GUI | CLI | Enters the pipeline at |
|---|---|---|---|
| Video clip | Actions → **Import clip…** | `--sprite-import-video PATH` | extract |
| PNG sequence | Actions → **Import frames…** | `--sprite-import-frames DIR` | key |
| Sprite sheet | Actions → **Import sheet…** (grid guessed, ask when unsure) | `--sprite-import-sheet PATH --sprite-grid CxR` | key |

An import creates the action when it does not exist and re-runs every stage after
extract, because the cache fingerprints settings, not frame content.

## Exports per engine

Every preset writes the files an engine loads directly plus the Aseprite JSON sidecar
next to the grid PNG, so timing is never lost. `how_to_import` from the preset is also
written to `export.json` in the output folder.

| Preset | Files | Import notes |
|---|---|---|
| `unity` | grid PNG, TexturePacker JSON (hash) | Texture Type = Sprite (2D and UI), Sprite Mode = Multiple, Filter = Point and Compression = None for pixel art. Slice with Sprite Editor → Grid By Cell Size, or install a TexturePacker importer and drop the JSON next to the PNG. |
| `godot4` | grid PNG, `.tres` SpriteFrames | Add an `AnimatedSprite2D`, set **Sprite Frames** → Load → the `.tres`. Set Project Settings → Rendering → Textures → Default Texture Filter = Nearest for pixel art. The `.tres` references the PNG as `res://<name>.png`; keep both in the same folder. |
| `phaser3` | grid PNG, TexturePacker JSON (hash) | `this.load.atlas('hero', 'hero_hd.png', 'hero_hd.tp.json')`, then `this.anims.create({ key: 'walk', frames: this.anims.generateFrameNames('hero', { prefix: 'hero_walk_', start: 1, end: 8, zeroPad: 2 }), frameRate: 12, repeat: -1 })`. Set `pixelArt: true` in the game config for the pixel profile. |
| `pixijs` | grid PNG, TexturePacker JSON (hash, with `animations`) | `const sheet = await Assets.load('hero_hd.tp.json'); new AnimatedSprite(sheet.animations.walk)`. For pixel art set the texture scale mode to nearest before loading. |
| `unreal` | grid PNG, TexturePacker JSON (array) | Import the PNG, right-click → Sprite Actions → Apply Paper2D Texture Settings, then import the JSON to get one Sprite per frame; build a Flipbook from the sprites of one action. |
| `libgdx` | grid PNG, PNG sequence | `TextureRegion.split(texture, cellW, cellH)` and `new Animation<>(1f / fps, frames)`. Set `Texture.TextureFilter.Nearest` for pixel art. |
| `rpgmaker_mz` | 48×48 character sheet (3 columns × 4 rows per character) | Copy to `img/characters/`. Name the file with a `$` prefix for a single-character sheet. Map walk_down, walk_left, walk_right, walk_up to the four rows. |
| `web_preview` | grid PNG, GIF per action, `index.html` | Open `index.html` in a browser to check every loop. |

Format list for `--sprite-formats`: `grid`, `aseprite_json`, `texturepacker_json`,
`png_sequence`, `gif`, `godot_tres`, `aseprite_native` (native `.ase`, one layer, one cel per
frame, tags, and the palette when quantized).

GIF export uses a reserved transparent index, `disposal=2`, and clamps every frame
duration to 20 ms or more. Frame rates that do not divide evenly into whole
milliseconds are reported in the export summary.

## Purge intermediates after export

Intermediate files (`clips/` and `stages/`) can be large. The export dialog has a
**Purge intermediates after export** checkbox. It is off by default and sticky. When
you turn it on, a dialog lists what gets deleted and asks you to confirm. Deleted files
go through the recycle bin. The command line never purges.

## Keyboard shortcuts

| Key | Action | Where |
|---|---|---|
| Space | Play / pause | preview player |
| `,` / `.` | Previous / next frame | preview + strip |
| Home / End | First / last frame | preview + strip |
| Ctrl+Enter | Primary action (Generate selected / Run pipeline / Export) | every panel and dialog |
| Escape | Close dialog | dialogs |
| Delete | Delete selected frame(s) | strip |
| Ctrl+D | Duplicate frame | strip |
| Ctrl+Z / Ctrl+Y | Undo / redo | tab |
| `+` / `-` / Ctrl+0 | Zoom in / out / 100 % | pixel view |
| G | Toggle pixel grid | pixel view |
| L | Cycle loop mode (forward → reverse → ping-pong) | preview |

Undo covers frame-list edits: delete, reorder, duplicate, insert, duration, retouch,
per-frame overrides. Fifty steps per action. Pipeline re-runs are not undo steps: they
never destroy anything.

## Command line

Every tab action has a verb. One verb per call. `--sprite-project` takes a project
name or the path to `project.iasprite.json`.

```bash
# Create a project from a character image
python main.py --sprite-new hero --sprite-source hero.png --sprite-genre sidescroller

# Action cards from a brief (appended to the project; also written to cards.json)
python main.py --sprite-cards "a small knight with a lantern" --sprite-project hero

# Cost per action and per sheet, no spend
python main.py --sprite-estimate --sprite-project hero

# Render every draft card through the video route (project provider, Omni by default)
python main.py --sprite-render --sprite-project hero
# ... or two cards on Veo, then the image-sheet route for one more
python main.py --sprite-render --sprite-project hero --sprite-actions idle,walk --video-provider veo
python main.py --sprite-render --sprite-project hero --sprite-actions jump --sprite-route sheet --provider openai -m gpt-image-2

# Run the pipeline to the end (hd + pixel), or only up to the key stage, or force every stage
python main.py --sprite-process --sprite-project hero
python main.py --sprite-process --sprite-project hero --sprite-upto key
python main.py --sprite-process --sprite-project hero --force

# External inputs (one action name per import)
python main.py --sprite-import-video walk.mp4 --sprite-project hero --sprite-actions walk
python main.py --sprite-import-frames ./frames --sprite-project hero --sprite-actions idle
python main.py --sprite-import-sheet sheet.png --sprite-grid 8x1 --sprite-project hero --sprite-actions run

# Export
python main.py --sprite-export --sprite-project hero --sprite-preset godot4 --sprite-profile pixel -o ./out
python main.py --sprite-export --sprite-project hero --sprite-preset unity --sprite-formats grid,texturepacker_json,gif

# Projects, and machine-readable output for scripts
python main.py --sprite-list
python main.py --sprite-render --sprite-project hero --json 2>render.log
```

Human-readable progress goes to stderr as `[stage] done/total message` lines. With
`--json`, stdout carries exactly one JSON object. Exit codes: `0` ok, `1` a render or
pipeline step failed, `2` usage error, `3` unexpected error, `130` cancelled with Ctrl+C
(the current frame finishes first). Every output has a `.json` record next to it, and
verbs that write many files also write `<project>/runs/<verb>-<timestamp>.json`.

## Where the files are

```
<Images root>/sprites/<project-slug>/
  project.iasprite.json
  source/character.png (+ .json)   plate.png (+ .json)   turnaround/<view>.png (+ .json)
  clips/<action_id>.mp4 (+ .json: provider, model, params, prompt, cost)
  sheets/<action_id>.png (+ .json)              image-sheet route only
  stages/<action_id>/extract/ key/ cleanup/ alpha/ stabilize/ hd/ pixel/
  exports/<profile>/<engine-preset>/<files> + export.json
  runs/<verb>-<timestamp>.json                  CLI run records
  cards.json                                     --sprite-cards output
<Settings root>/sprite_configs.json              named generation configurations
```

The Images root moves with the Storage Locations section of the Settings tab; the
`sprites` folder is part of the Images group in the migration journal, and a moved
project re-anchors its clip paths on load.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Python 3.11 or newer is required" | the interpreter is older | create the venv with Python 3.11–3.13 |
| Estimate shows "unknown" | no verified rate for this model | set `sprite.price_overrides` in `config.json`, or switch model |
| Card marked failed with a safety message | the provider refused the character | try the other provider; edit the prompt; the app never pre-blocks |
| Green fringe around the character | despill off, or tolerance too low | turn on despill (average) and edge decontamination; raise tolerance a little |
| Holes inside the character | key color also appears in the character | pick a different plate color and re-render the plate |
| Frames jump between cells | de-jitter off or the phase method fails on a symmetric sprite | switch de-jitter method to centroid |
| Loop pops at the seam | the clip did not close | keep Veo loop conditioning at 8 s; use the seam meter to trim the tail |
| "ffmpeg not found" | no ffmpeg on the PATH | install ffmpeg, or let Settings install `imageio-ffmpeg` |
| GIF shows a halo or leftover pixels | a viewer ignores `disposal=2` | check in a browser; the file is correct |
```

- [ ] **Step 2: Check the labels against the shipped GUI**

```bash
grep -rn "setText(\|addAction(\|QPushButton(\|setTitle(" /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/*.py | grep -o '"[^"]*"' | sort -u
```

Compare the list with the guide. Change the guide where a label differs.

- [ ] **Step 3: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Docs/Sprite-Tab-Guide.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs: Sprite tab user guide"
```

---

### Task 10: Feature list, README, and CLI guide

**Files:**
- Modify: `Docs/Features.md` — insert a `### Sprite Tab` section after the Layout/Books Tab section (after line 138, before `### Character Animator Puppet Creation` at line 140); extend the `## CLI Reference` block (lines 237–254)
- Modify: `README.md` — insert a `### 🕹️ Sprite Tab (NEW!)` section after `### 🎬 Video Project Features` (after line 228, before `### 🎵 MIDI Synchronization & Karaoke` at line 230); change line 279; insert `### Sprite animations (CLI)` after the "Generate video (CLI)" section (after line 695, before `### Video Generation with MIDI Sync` at line 697)
- Modify: `Docs/ImageAI-CLI-Guide.md` — TOC (after line 33 `- [Publication layout engine]…`), new `## Sprite animations` section after the layout section (before `## Keys, auth & testing` at line 451), exit-code table (lines 485–492), flag reference (after the Video table, before `### Lyrics / layout / keys / auth` at line 550), anti-footguns (after line 563)

**Interfaces:** documentation only. Verify every insertion anchor with `grep -n` first; the line numbers above are from 2026-08-29 and shift when other sub-projects touch these files.

- [ ] **Step 1: Verify the anchors**

```bash
grep -n "^### Character Animator Puppet Creation\|^## CLI Reference\|^### Layout/Books Tab" /mnt/d/Documents/Code/GitHub/ImageAI/Docs/Features.md
grep -n "^### 🎵 MIDI Synchronization\|^- Python 3.9+\|^### Video Generation with MIDI Sync\|^### Generate video (CLI)" /mnt/d/Documents/Code/GitHub/ImageAI/README.md
grep -n "^## Keys, auth & testing\|^### Lyrics / layout / keys / auth\|^## Anti-footguns\|^\*\*Video exit codes:\*\*\|Publication layout engine\](#" /mnt/d/Documents/Code/GitHub/ImageAI/Docs/ImageAI-CLI-Guide.md
```

- [ ] **Step 2: `Docs/Features.md` — feature section**

Insert before `### Character Animator Puppet Creation`:

```markdown
### Sprite Tab

Turn one character image and a one-line brief into engine-ready sprite animations.

- **Action cards** - An LLM drafts one card per action from a genre checklist (sidescroller, top-down, fighting); every field is editable
- **Two generation routes** - Video clips (Gemini Omni default, Veo with loop conditioning) or image sheets / edit chains (Gemini, gpt-image)
- **Chroma plate + turnaround pack** - A flat-color plate and front/side/back/three-quarter references keep the character consistent
- **Processing pipeline** - extract → chroma or ML key → despill and edge cleanup → alpha → crop, pad, and de-jitter; every stage is cached and re-runs only when its settings change
- **Two output profiles** - `hd` (soft alpha, cells up to 1024) and `pixel` (binary alpha, integer downscale, shared palette, dither)
- **Frame tools** - strip with reorder/duplicate/delete, preview player with loop-seam meter, pixel zoom view, AI retouch per frame, 50-step undo
- **External inputs** - import a video clip, a PNG sequence, or a sprite sheet made elsewhere
- **Exports** - grid PNG, Aseprite JSON, TexturePacker JSON, PNG sequence, GIF, Godot `.tres`, native `.aseprite`, single frames, and engine presets for Unity, Godot 4, Phaser 3, PixiJS, Unreal, libGDX, RPG Maker MZ, and a web preview
- **Cost** - estimate per action and per sheet before rendering; a ledger records actual spend
- **CLI parity** - every action has a `--sprite-*` verb with `--json` output (see `Docs/Sprite-Tab-Guide.md`)
```

Append to the CLI Reference code block (after `# Convert lyrics to prompts` and its command):

```bash
# Sprite animations: project, cards, render, process, export
python main.py --sprite-new hero --sprite-source hero.png
python main.py --sprite-cards "a small knight with a lantern" --sprite-project hero
python main.py --sprite-render --sprite-project hero
python main.py --sprite-process --sprite-project hero
python main.py --sprite-export --sprite-project hero --sprite-preset godot4 -o ./out
```

- [ ] **Step 3: `README.md` — feature bullets, Python line, CLI examples**

Insert before `### 🎵 MIDI Synchronization & Karaoke (NEW!)`:

```markdown
### 🕹️ Sprite Tab (NEW!)
- **Character to animation** - One image plus a one-line brief becomes per-action animations
- **Video or image route** - Gemini Omni (default) / Veo clips, or Gemini / gpt-image sheets and edit chains
- **Keying pipeline** - Chroma key with despill, optional ML background removal (mediapipe, rembg), de-jitter, crop and pad
- **HD and pixel profiles** - Soft-alpha large cells, or integer downscale with a shared palette and dither
- **Engine exports** - Aseprite, TexturePacker, Godot `.tres`, GIF, PNG sequences, presets for Unity, Godot 4, Phaser 3, PixiJS, Unreal, libGDX, RPG Maker MZ
- **CLI parity** - `--sprite-*` verbs with `--json` output; guide: `Docs/Sprite-Tab-Guide.md`
```

Replace line 279 `- Python 3.9+ (3.9 to 3.13 supported)` with:

```markdown
- Python 3.11+ (3.11 to 3.13 supported). The optional Sprite ML extras
  (`requirements-sprite-ml.txt`: `rembg`, `mediapipe`) need Python 3.11–3.13.
```

Insert before `### Video Generation with MIDI Sync (NEW!)`:

````markdown
### Sprite animations (CLI)

Every Sprite tab action has a `--sprite-*` verb. One verb per call; `--sprite-project`
takes a project name or a path to `project.iasprite.json`.

```bash
# Project from a character image, then action cards from a brief
python main.py --sprite-new hero --sprite-source hero.png --sprite-genre sidescroller
python main.py --sprite-cards "a small knight with a lantern" --sprite-project hero

# Estimate, render (project provider; Omni by default), process, export
python main.py --sprite-estimate --sprite-project hero
python main.py --sprite-render --sprite-project hero --sprite-actions idle,walk
python main.py --sprite-process --sprite-project hero
python main.py --sprite-export --sprite-project hero --sprite-preset godot4 --sprite-profile pixel -o ./out

# External inputs
python main.py --sprite-import-video walk.mp4 --sprite-project hero --sprite-actions walk
python main.py --sprite-import-sheet sheet.png --sprite-grid 8x1 --sprite-project hero --sprite-actions run

# Machine-readable result (one JSON object on stdout; progress on stderr)
python main.py --sprite-render --sprite-project hero --json
```

Exit codes: `0` ok, `1` a step failed, `2` usage error, `3` unexpected error, `130`
cancelled with Ctrl+C. Full guide: `Docs/Sprite-Tab-Guide.md`.
````

- [ ] **Step 4: `Docs/ImageAI-CLI-Guide.md` — section, exit codes, flags, anti-footguns**

TOC: add `- [Sprite animations](#sprite-animations)` after the layout entry.

Insert before `## Keys, auth & testing`:

````markdown
## Sprite animations

The CLI drives the whole Sprite tab (design: `Plans/2026-08-29-sprite-tab-design.md`;
user guide: `Docs/Sprite-Tab-Guide.md`). One `--sprite-*` verb per call.

```bash
# 1. Project + character (padded onto the aspect canvas, never cropped)
python main.py --sprite-new hero --sprite-source hero.png --sprite-genre sidescroller

# 2. Action cards from a one-line brief (LLM contract "Sprite Action Cards — Strict v1.0")
python main.py --sprite-cards "a small knight with a lantern" --sprite-project hero \
    --sprite-llm-provider anthropic

# 3. Cost per action and per sheet for the current settings (never spends)
python main.py --sprite-estimate --sprite-project hero --json

# 4. Render: video route (default; the project's provider, Omni unless changed)
python main.py --sprite-render --sprite-project hero
python main.py --sprite-render --sprite-project hero --sprite-actions idle,walk --video-provider veo
#    ... or the image routes (sheet = one sprite sheet sliced by a grid guess; edit-chain = frame k edits frame k-1)
python main.py --sprite-render --sprite-project hero --sprite-actions jump --sprite-route sheet --provider openai -m gpt-image-2
python main.py --sprite-render --sprite-project hero --sprite-actions hurt --sprite-route edit-chain

# 5. Processing spine: extract → key → cleanup → alpha → stabilize → hd → pixel (cached per stage)
python main.py --sprite-process --sprite-project hero
python main.py --sprite-process --sprite-project hero --sprite-upto stabilize
python main.py --sprite-process --sprite-project hero --force

# External inputs enter the spine (video at extract; frames and sheets after it)
python main.py --sprite-import-video walk.mp4 --sprite-project hero --sprite-actions walk
python main.py --sprite-import-frames ./frames --sprite-project hero --sprite-actions idle
python main.py --sprite-import-sheet sheet.png --sprite-grid 8x1 --sprite-project hero --sprite-actions run

# 6. Export: preset x profile x formats -> -o DIR (default <project>/exports/<profile>/<preset>)
python main.py --sprite-export --sprite-project hero --sprite-preset godot4 --sprite-profile pixel -o ./out
python main.py --sprite-export --sprite-project hero --sprite-preset unity --sprite-formats grid,texturepacker_json,gif

# Projects
python main.py --sprite-list --json
```

### Output & reporting contract (sprite)

- Progress lines on **stderr**: `[stage] done/total message` (`[key] 3/8 0003.png`).
- With `--json`, stdout carries exactly one object with five fixed keys —
  `status` (`completed` | `failed` | `cancelled`), `verb`, `project`, `output_path`,
  `error` — plus verb-specific keys: `cards` (cards), `actions` + `failed` + `estimate`
  (render), `actions` + `skipped` (process), `exports` (export), `projects` (list),
  `actions` + `sheet_estimated_usd` + `unknown_count` (estimate), `stages` (imports).
- Records: `character.json` next to the normalized source, `clips/<id>.json` next to a
  clip, `sheets/<id>.json` next to a generated sheet, `export.json` in every export
  folder, and `<project>/runs/<verb>-<timestamp>.json` for render / process / imports.
  `--sprite-cards` writes the card list as JSON (`-o`, else `<project>/cards.json`).
- Ctrl+C cancels after the current frame; the verb reports `cancelled` and exits 130.
  A remote video job keeps running at the provider; the project keeps its operation id.

```json
{
  "status": "completed",
  "verb": "render",
  "project": "/home/me/.config/ImageAI/generated/sprites/hero/project.iasprite.json",
  "output_path": null,
  "error": null,
  "route": "video",
  "provider": "omni",
  "model": "(default)",
  "actions": [{"id": "…", "name": "idle", "route": "video", "status": "processed",
               "estimated_usd": 0.32, "actual_usd": 0.32, "clip": "…/clips/….mp4",
               "operation_id": "…", "error": null}],
  "failed": [],
  "estimate": {"provider": "omni", "model": "(default)", "actions": ["…"],
               "sheet_estimated_usd": 2.56, "unknown_count": 0,
               "ledger_estimated_usd": 0.32, "ledger_actual_usd": 0.32}
}
```
````

Exit-code table (`**Video exit codes:**`): rename the heading to `**Video and sprite exit codes:**` and add one row after `3`:

```markdown
| `130` | Cancelled with Ctrl+C (sprite verbs; the current frame finishes first) |
```

Flag reference: insert a `### Sprite` table before `### Lyrics / layout / keys / auth`:

```markdown
### Sprite

| Flag | Values | Notes |
|------|--------|-------|
| `--sprite-new` | NAME | Create a project; needs `--sprite-source IMAGE`; `--sprite-genre`, `--aspect` optional. |
| `--sprite-project` | name, slug, or path | Target project for every other verb: the project name, the folder slug, `project.iasprite.json`, or its folder. |
| `--sprite-list` / `--sprite-estimate` | flag | List projects / print the cost estimate per action and per sheet. |
| `--sprite-cards` | BRIEF | Generate action cards; `--sprite-genre`, `--sprite-llm-provider`, `--sprite-llm-model`; list written to `-o` or `cards.json`. |
| `--sprite-render` | flag | Render draft/failed cards or `--sprite-actions`; `--sprite-route video\|sheet\|edit-chain`; video route uses `--video-provider`/`--video-model`, image routes use `--provider`/`-m`. |
| `--sprite-actions` | `a,b` | Filter for render/process/export; the single target action for imports. |
| `--sprite-process` | flag | Run the pipeline; `--sprite-upto STAGE` (extract, key, cleanup, alpha, stabilize, hd, pixel), `--force`. |
| `--sprite-import-video` / `--sprite-import-frames` / `--sprite-import-sheet` | PATH / DIR / PATH | External inputs; sheets need `--sprite-grid CxR`. |
| `--sprite-export` | flag | `--sprite-preset` (unity, godot4, phaser3, pixijs, unreal, libgdx, rpgmaker_mz, web_preview), `--sprite-profile hd\|pixel\|both`, `--sprite-formats a,b`, `-o DIR`. |
| `--json` | flag | One JSON object on stdout (shared with `--video`). |
```

Anti-footguns: add after the first bullet of `## Anti-footguns`:

```markdown
- **One sprite verb per call.** `--sprite-render --sprite-export` exits 2. Chain calls.
- **`--sprite-render` skips rendered cards** unless you name them with `--sprite-actions`.
- **`--video-provider` is unset by default** so a sprite render keeps the project's
  provider; `--video` still defaults to Veo.
- **Imports re-run every stage after extract** — the cache fingerprints settings, not
  frame content.
- **The CLI never purges intermediates**; purge-after-export is a GUI preference with a
  confirmation.
```

- [ ] **Step 5: Check the Markdown renders (no broken fences) and the links resolve**

```bash
$PY - <<'EOF'
import re, pathlib
for p in ["Docs/Features.md", "README.md", "Docs/ImageAI-CLI-Guide.md", "Docs/Sprite-Tab-Guide.md"]:
    text = pathlib.Path("/mnt/d/Documents/Code/GitHub/ImageAI", p).read_text(encoding="utf-8")
    fences = len(re.findall(r"^```", text, flags=re.M))
    assert fences % 2 == 0, f"{p}: unbalanced code fences ({fences})"
    print(p, "fences ok")
EOF
grep -n "Sprite-Tab-Guide.md" /mnt/d/Documents/Code/GitHub/ImageAI/README.md /mnt/d/Documents/Code/GitHub/ImageAI/Docs/Features.md /mnt/d/Documents/Code/GitHub/ImageAI/Docs/ImageAI-CLI-Guide.md
```

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Docs/Features.md README.md Docs/ImageAI-CLI-Guide.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs: sprite feature in Features.md, README (Python 3.11+), CLI guide"
```

---

### Task 11: `imageai-cli` skill — sprite verbs

**Files:**
- Modify: `.claude/skills/imageai-cli/SKILL.md` — frontmatter `description` (line 3); intro blockquote (lines 15–17); new `## Sprite animations (`--sprite-*`)` section after `### `.iaibundle` is GUI-only` (line 396–401) and before `## Agent output contract` (line 402); contract bullets (lines 402–411); flag table (lines 434–485); anti-footguns (lines 486–517)

**Interfaces:** documentation for agents. Same style as the video and layout sections: a code block of real commands, a capability table, contract bullets, table rows. The skill is symlinked into `~/.claude/skills` and `~/.agents/skills` (memory: `imageai-cli-skill-symlinks`); do not touch `.skill-lock.json`.

- [ ] **Step 1: Verify the anchors**

```bash
grep -n "^description:\|^> GUI is the default\|^## Agent output contract\|^## Full flag reference\|^## Anti-footguns\|^### \`.iaibundle\` is GUI-only" /mnt/d/Documents/Code/GitHub/ImageAI/.claude/skills/imageai-cli/SKILL.md
```

- [ ] **Step 2: Frontmatter and intro**

In the `description:` line, after `… for comics, magazines, PDFs)`, insert `, and the sprite pipeline (--sprite-new/--sprite-cards/--sprite-render/--sprite-process/--sprite-export plus imports: character image → action cards → Omni/Veo clips or image sheets → keyed, stabilized frames → Aseprite/TexturePacker/Godot/GIF/engine-preset exports)`. In the trigger sentence, change `make or edit an image, video, or layout` to `make or edit an image, video, layout, or game sprite`.

In the intro blockquote, add `--sprite-*` to the list of flags that stay in the CLI: `… \`--lyrics-to-prompts\`, or any \`--layout-*\` or \`--sprite-*\` action to stay in the CLI.`

- [ ] **Step 3: The section** (insert before `## Agent output contract`)

````markdown
## Sprite animations (`--sprite-*`)

One character image + a one-line brief → per-action animations → engine files. One
verb per call; `--sprite-project` takes a project name or a `project.iasprite.json`
path. Full guide: `Docs/Sprite-Tab-Guide.md`.

```bash
# Project from a character image (padded onto the aspect canvas, never cropped)
python main.py --sprite-new hero --sprite-source hero.png --sprite-genre sidescroller

# Action cards from a brief → appended to the project + written to cards.json
python main.py --sprite-cards "a small knight with a lantern" --sprite-project hero

# Cost per action + per sheet (never spends); scriptable
python main.py --sprite-estimate --sprite-project hero --json

# Render draft cards through the video route (project provider; Omni by default)
python main.py --sprite-render --sprite-project hero
python main.py --sprite-render --sprite-project hero --sprite-actions idle,walk --video-provider veo
# Image routes: one sliced sheet, or an edit chain (frame k edits frame k-1)
python main.py --sprite-render --sprite-project hero --sprite-actions jump --sprite-route sheet --provider openai -m gpt-image-2
python main.py --sprite-render --sprite-project hero --sprite-actions hurt --sprite-route edit-chain

# Pipeline: extract → key → cleanup → alpha → stabilize → hd → pixel (cached; --force re-runs all)
python main.py --sprite-process --sprite-project hero
python main.py --sprite-process --sprite-project hero --sprite-upto stabilize --sprite-actions walk

# External inputs (exactly one action name per import)
python main.py --sprite-import-video walk.mp4 --sprite-project hero --sprite-actions walk
python main.py --sprite-import-frames ./frames --sprite-project hero --sprite-actions idle
python main.py --sprite-import-sheet sheet.png --sprite-grid 8x1 --sprite-project hero --sprite-actions run

# Export: preset × profile × formats
python main.py --sprite-export --sprite-project hero --sprite-preset godot4 --sprite-profile pixel -o ./out
python main.py --sprite-export --sprite-project hero --sprite-preset unity --sprite-formats grid,texturepacker_json,gif

python main.py --sprite-list --json
```

### Verb → route → provider

| Verb | Provider / key | Notes |
|---|---|---|
| `--sprite-cards` | text LLM: `--sprite-llm-provider openai\|anthropic\|google` (default google), key via `-k`/config/env | Genre checklist: `sidescroller` (default), `top_down`, `fighting`. |
| `--sprite-render` (video route, default) | Google key; `--video-provider omni\|veo`, `--video-model` | Unset flags keep the **project's** provider (Omni). Veo loop conditioning forces 8 s. |
| `--sprite-render --sprite-route sheet\|edit-chain` | `--provider google\|openai`, `-m` | edit-chain also needs the text LLM for pose steps. |
| `--sprite-process`, imports, `--sprite-export`, `--sprite-list`, `--sprite-estimate` | no key | Local work only. |

- Presets: `unity`, `godot4`, `phaser3`, `pixijs`, `unreal`, `libgdx`, `rpgmaker_mz`,
  `web_preview` (default). Formats for `--sprite-formats`: `grid`, `aseprite_json`,
  `texturepacker_json`, `png_sequence`, `gif`, `godot_tres`, `aseprite_native`.
- Profiles: `hd` (soft alpha, big cells) and `pixel` (binary alpha, integer downscale,
  shared palette); `--sprite-profile both` (default) exports each enabled one into
  `<out>/<profile>/<preset>/`.
- Stages for `--sprite-upto`: `extract`, `key`, `cleanup`, `alpha`, `stabilize`, `hd`, `pixel`.
- Every export folder gets `export.json` with `files` and the preset's `how_to_import`
  text — read it instead of guessing engine import steps.
````

- [ ] **Step 4: Contract, flag table, anti-footguns**

Under `## Agent output contract` add:

```markdown
- **`--json` (sprite):** one object with `status` (`completed|failed|cancelled`), `verb`,
  `project`, `output_path`, `error`, plus verb keys (`cards`, `actions`/`failed`/`estimate`,
  `actions`/`skipped`, `exports`, `projects`, `stages`). Progress is on stderr as
  `[stage] done/total message`.
- **Exit codes (sprite):** `0` ok, `1` a render/pipeline step failed (see `failed`),
  `2` usage error, `3` unexpected exception, `130` cancelled (Ctrl+C).
- **Records:** `character.json`, `clips/<id>.json`, `sheets/<id>.json`, `export.json`,
  `<project>/runs/<verb>-<timestamp>.json`, `cards.json`.
```

Flag table: add these rows after the `--layout-llm-provider / --layout-llm-model` row:

```markdown
| `--sprite-new` | NAME | New project; needs `--sprite-source IMAGE`; optional `--sprite-genre`, `--aspect`. |
| `--sprite-project` | name, slug, or path | Target project for every other sprite verb. |
| `--sprite-list` / `--sprite-estimate` | flag | List projects / cost per action + per sheet. |
| `--sprite-cards` | BRIEF | Action cards; `--sprite-genre`, `--sprite-llm-provider`, `--sprite-llm-model`; `-o` for the card file. |
| `--sprite-render` | flag | Draft/failed cards or `--sprite-actions`; `--sprite-route video\|sheet\|edit-chain`. |
| `--sprite-actions` | `a,b` | Filter (render/process/export) or the one target action (imports). |
| `--sprite-process` | flag | Pipeline; `--sprite-upto STAGE`, `--force`. |
| `--sprite-import-video` / `--sprite-import-frames` / `--sprite-import-sheet` | PATH / DIR / PATH | External inputs; sheet needs `--sprite-grid CxR`. |
| `--sprite-export` | flag | `--sprite-preset ENGINE`, `--sprite-profile hd\|pixel\|both`, `--sprite-formats a,b`, `-o DIR`. |
```

Change the `--json` row to `| \`--json\` | flag | Video and sprite verbs: one JSON object on stdout. |` and the `--video-provider` row to `| \`--video-provider\` | \`omni\` \| \`veo\` | Default \`veo\` for \`--video\`; unset keeps the project's provider for \`--sprite-render\`. |`.

Anti-footguns: add before `- **In `--json` mode, parse stdout only**`:

```markdown
- **Sprite verbs: one per call**; two exit 2. `--sprite-render` skips already-rendered
  cards unless named in `--sprite-actions`. Imports need exactly one action name.
- **Sprite keys:** the video route and Gemini image route need the Google key; the
  gpt-image route needs `--provider openai`; cards need the text-LLM provider's key.
- **The sprite CLI never purges intermediates** (GUI preference only) and never
  confirms spend — read `--sprite-estimate` first.
```

- [ ] **Step 5: Check the frontmatter still parses and the fences balance**

```bash
$PY - <<'EOF'
import re, pathlib
p = pathlib.Path("/mnt/d/Documents/Code/GitHub/ImageAI/.claude/skills/imageai-cli/SKILL.md")
text = p.read_text(encoding="utf-8")
assert text.startswith("---\nname: imageai-cli\ndescription: "), "frontmatter changed shape"
assert text.count("\n---\n", 0, 4000) >= 1
fences = len(re.findall(r"^```", text, flags=re.M))
assert fences % 2 == 0, f"unbalanced fences: {fences}"
print("skill ok", len(text), "bytes")
EOF
```

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add .claude/skills/imageai-cli/SKILL.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(skills): sprite verbs in imageai-cli skill"
```

---

### Task 12: CodeMap refresh

**Files:**
- Modify: `Docs/CodeMap.md` (header lines 1–12: timestamp, scope, version; new sections for `core/sprite/`, `gui/sprite/`, `cli/commands/sprite.py`, `tests/sprite/`; TOC line numbers last)

**Interfaces:** the `update-code-map` skill (`~/.claude/skills/update-code-map/SKILL.md`). Every line number in the CodeMap comes from the extractor's inventory; no line number is estimated. The header timestamp comes from `date`.

- [ ] **Step 1: Scout and build the inventory**

```bash
date +"%Y-%m-%d %H:%M:%S"
head -3 /mnt/d/Documents/Code/GitHub/ImageAI/Docs/CodeMap.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI diff --stat origin/main...HEAD -- '*.py' | tail -1
SCRATCH="$HOME/.claude/run/codemap-sprite"; mkdir -p "$SCRATCH"
python3 ~/.claude/skills/update-code-map/references/extract_symbols.py \
    --root /mnt/d/Documents/Code/GitHub/ImageAI --out "$SCRATCH/inventory.json"
python3 - "$SCRATCH/inventory.json" <<'EOF'
import json, sys
inv = json.load(open(sys.argv[1]))
files = inv if isinstance(inv, list) else inv.get("files", inv)
names = [f["path"] if isinstance(f, dict) else f for f in files]
print(sum(1 for n in names if "sprite" in n), "sprite files in inventory")
EOF
```

- [ ] **Step 2: Run the skill in INCREMENTAL mode**

Invoke the `update-code-map` skill (Claude Code: `Skill` tool, `skill: update-code-map`). Tell it: mode INCREMENTAL; new module groups `core/sprite` (+ `core/sprite/generation`, `core/sprite/exporters`), `gui/sprite`, `cli/commands/sprite.py` (add to the "CLI & Entry Points" section), `tests/sprite`; keep every untouched section; update the header scope counts and the `**Version:**` line from `core/constants.py:9`; regenerate the TOC line numbers last; verify 25 sampled `file:line` claims with `sed -n`.

Fallback when the skill is unavailable in the running CLI: `$PY /mnt/d/Documents/Code/GitHub/ImageAI/tools/generate_code_map.py` writes `Docs/CodeMap.md` from the AST directly (a full regeneration; less prose, same line-number guarantee).

- [ ] **Step 3: Verify**

```bash
head -12 /mnt/d/Documents/Code/GitHub/ImageAI/Docs/CodeMap.md
grep -n "cli/commands/sprite.py\|core/sprite/pipeline.py\|gui/sprite/sprite_tab.py" /mnt/d/Documents/Code/GitHub/ImageAI/Docs/CodeMap.md | head
# Spot-check: every sampled claim must print a def/class line
grep -o "cli/commands/sprite.py:[0-9]*" /mnt/d/Documents/Code/GitHub/ImageAI/Docs/CodeMap.md | sort -u | head -8 | while IFS=: read -r f n; do printf '%s:%s  ' "$f" "$n"; sed -n "${n}p" "/mnt/d/Documents/Code/GitHub/ImageAI/$f"; done
grep -c "\[ACTUAL_LINE\]" /mnt/d/Documents/Code/GitHub/ImageAI/Docs/CodeMap.md   # must be 0
```

- [ ] **Step 4: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Docs/CodeMap.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs: refresh CodeMap for the sprite feature"
```

---

### Task 13: Full suite + local review

**Files:**
- Modify: whatever the review findings touch (fixes commit as `fix: address sprite review findings`)

**Interfaces:** the `code-reviewer` agent (Agent tool, `subagent_type: code-reviewer`). Review scope: `git diff origin/main...HEAD`. Codex is **not** run by this plan.

- [ ] **Step 1: Full suite, guard tests, and a clean tree**

```bash
$PY -m pytest -q /mnt/d/Documents/Code/GitHub/ImageAI/tests 2>&1 | tail -5
$PY -m pytest -q /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/migration -q 2>&1 | tail -3
git -C /mnt/d/Documents/Code/GitHub/ImageAI status --porcelain
```

Expected: `N passed, M skipped`, zero failures, an empty status. Record `N` and `M` for the PR body.

- [ ] **Step 2: Lint the touched files**

```bash
$PY -m pyflakes /mnt/d/Documents/Code/GitHub/ImageAI/cli/commands/sprite.py /mnt/d/Documents/Code/GitHub/ImageAI/cli/parser.py /mnt/d/Documents/Code/GitHub/ImageAI/cli/runner.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_cli_sprite_*.py || $PY -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/cli/commands/sprite.py
```

- [ ] **Step 3: Launch the local review**

Use the Agent tool with `subagent_type: code-reviewer` and this prompt:

```
Review the sprite feature branch of /mnt/d/Documents/Code/GitHub/ImageAI: run
`git -C /mnt/d/Documents/Code/GitHub/ImageAI diff origin/main...HEAD --stat` and then read
the diff of every file under core/sprite/, gui/sprite/, cli/commands/sprite.py, cli/parser.py,
cli/runner.py, core/paths.py, core/data_migration.py, requirements*.txt, and tests/sprite/.
Design spec: Plans/2026-08-29-sprite-tab-design.md. Check, with file:line evidence:
1. Images are scaled proportionally, never cropped or distorted (source normalize, crop_and_pad, fit_pad_integer).
2. Every LLM and provider call logs the full request and response and every user-facing error is logged.
3. No hardcoded data paths (core/paths.py owns every location); no new hard dependency on GPL or non-commercial code (libimagequant, CorridorKey, bria-rmbg weights); rembg/mediapipe are optional extras only.
4. CLI contract: stderr for humans, one JSON object on stdout with --json, exit codes 0/1/2/3/130, sidecar/run record next to every output; SIGINT handler restored.
5. Cancel token honored at least once per frame in every long stage; the video clients stop polling on cancel.
6. Stage cache: a changed setting re-runs only its stage and later ones; raw clips and extracted frames are never overwritten.
7. Pillow RGBA quantize trap (quantize flattened RGB, carry alpha); GIF recipe (disposal=2, optimize=False, transparency index, durations >= 20 ms).
8. Threading: the GUI thread never runs PIL/ffmpeg beyond one thumbnail; one CancelToken per SpriteWorker.
Report real defects first (with the failing scenario), then hypothetical ones, then style. Separate the two clearly.
```

- [ ] **Step 4: Fix real findings, re-run the suite, commit**

```bash
$PY -m pytest -q /mnt/d/Documents/Code/GitHub/ImageAI/tests 2>&1 | tail -3
git -C /mnt/d/Documents/Code/GitHub/ImageAI add -A
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "fix: address sprite review findings"
```

Skip the commit when the review found nothing to change. Write a short list of the findings and their disposition (fixed / rejected with reason) for the PR body.

- [ ] **Step 5: Hand-off point for Codex (optional, Leland runs it)**

The tree is clean and committed. Leland may now run `/codex:review --base origin/main`. This plan does not run it. When Codex findings arrive, reconcile them the same way as Step 4 before the version bump.

---

### Task 14: Version bump + changelog (version-manager)

**Files:**
- Modify (by the tool only): `core/constants.py` (`VERSION`, line 9), `README.md` (`**Version X.Y.Z**`, line 5), `CHANGELOG.md` (new section under `## [Unreleased]`)
- `.claude/VERSION_LOCATIONS.md` lists these locations; the other entries there (`core/__init__.py`, `cli/parser.py`, `gui/main_window.py`, root `__init__.py`) import `VERSION` and need no edit.

**Interfaces:** `python3 ~/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/ImageAI release minor`. Level is `minor`: a new feature, no breaking change. The tool refuses on a dirty tree, an existing tag, or disagreeing version locations. Expected result: `0.46.0` → `0.47.0` (use the number the dry run prints).

- [ ] **Step 1: Clean tree and drift check**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI status --porcelain          # must print nothing
python3 ~/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/ImageAI check
```

If `check` reports disagreeing locations, stop and report; do not hand-edit.

- [ ] **Step 2: Dry run**

```bash
python3 ~/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/ImageAI release minor
```

Read the draft. Note the new version number `X.Y.0`.

- [ ] **Step 3: Curate the notes (outside the repo, so the tree stays clean)**

```bash
NOTES="$HOME/sprite-tab-release-notes.md"
cat > "$NOTES" <<'EOF'
### Added
- Sprite tab: turn one character image and a one-line brief into per-action
  animations and export them as sprite sheets, PNG sequences, GIFs, and engine
  files. Two generation routes: video clips (Gemini Omni by default, Veo with
  loop conditioning) and image sheets or edit chains (Gemini, gpt-image). A
  chroma plate and a turnaround pack keep the character consistent across
  actions.
- Processing pipeline with a per-stage cache: extract, chroma or ML key,
  despill and edge cleanup, alpha, crop-pad-dejitter. A changed setting re-runs
  only its stage and the stages after it; raw clips and extracted frames are
  never overwritten.
- Two output profiles: `hd` (soft alpha, cells up to 1024) and `pixel` (binary
  alpha, integer downscale, shared palette with lock and remap, Bayer or
  Floyd-Steinberg dither).
- Frame tools: strip with reorder, duplicate, delete, insert, and per-frame
  duration; preview player with forward, reverse, and ping-pong loops and a
  loop-seam meter; pixel zoom view; AI retouch per frame; 50-step undo.
- External inputs: import a video clip, a PNG sequence, or a sprite sheet
  (grid guessed, confirmed by the user when unsure).
- Exporters: grid PNG with an Aseprite JSON sidecar, Aseprite JSON (hash and
  array), TexturePacker JSON, PNG sequence, single frame, GIF, Godot 4
  `.tres` SpriteFrames, native `.aseprite`, and engine presets for Unity,
  Godot 4, Phaser 3, PixiJS, Unreal, libGDX, RPG Maker MZ, and a web preview.
- Cost estimate per action and per sheet before a render, and a ledger of
  actual spend per action in the project.
- Named generation configurations (`sprite_configs.json` under the Settings
  root) with presets for cells up to 1024 and canvases from 320x180 to
  640x360.
- CLI parity: `--sprite-new`, `--sprite-cards`, `--sprite-estimate`,
  `--sprite-render` (video, sheet, edit-chain routes), `--sprite-process`,
  `--sprite-import-video`, `--sprite-import-frames`, `--sprite-import-sheet`,
  `--sprite-export`, `--sprite-list`, with `--json` output, stderr progress,
  exit codes 0/1/2/3/130, and a JSON record next to every output. Ctrl+C
  cancels after the current frame.
- Docs: `Docs/Sprite-Tab-Guide.md`, sprite sections in `Docs/Features.md`,
  `README.md`, `Docs/ImageAI-CLI-Guide.md`, and the `imageai-cli` skill;
  CodeMap refreshed.

### Changed
- Python floor is 3.11. The optional Sprite ML extras
  (`requirements-sprite-ml.txt`: rembg, mediapipe) need Python 3.11 to 3.13.
- New hard dependencies: scikit-image and scipy (de-jitter), with an OpenCV
  fallback when the import fails.
- `--video-provider` has no parser default. `--video` still uses Veo when the
  flag is absent; `--sprite-render` keeps the project's own provider.
- `resolve_api_key` reads `ANTHROPIC_API_KEY` for the anthropic provider.
- The `sprites` folder joins the Images group in the storage-migration
  journal, and `sprite_configs.json` joins the Settings files.
EOF
```

Edit the notes to match what the branch actually shipped: remove any bullet for a sub-project feature that was cut, and add any deviation the other plans recorded. Keep prose, not commit subjects.

- [ ] **Step 4: Apply**

```bash
python3 ~/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/ImageAI release minor --notes "$NOTES" --apply
```

- [ ] **Step 5: Verify every location moved together**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI show --stat HEAD | head -20
grep -n '^VERSION = ' /mnt/d/Documents/Code/GitHub/ImageAI/core/constants.py
grep -n '^\*\*Version ' /mnt/d/Documents/Code/GitHub/ImageAI/README.md
grep -n '^## \[' /mnt/d/Documents/Code/GitHub/ImageAI/CHANGELOG.md | head -3
git -C /mnt/d/Documents/Code/GitHub/ImageAI tag --list 'v0.4*' | tail -3
$PY /mnt/d/Documents/Code/GitHub/ImageAI/main.py --version | head -1
```

Expected: one commit that touches `core/constants.py`, `README.md`, `CHANGELOG.md`; the three greps agree on `X.Y.0`; a tag `vX.Y.0` exists; `imageai X.Y.0`.

---

### Task 15: Push + PR

**Files:** none modified. Outward-facing actions: `git push`, `gh pr create`.

**Interfaces:** `gh` (logged in as `lelandg`), remote `origin` = `https://github.com/lelandg/ImageAI.git`, base `main`, head `feat/sprite-tab`.

- [ ] **Step 1: Confirm the branch holds only this feature's commits**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI fetch origin
git -C /mnt/d/Documents/Code/GitHub/ImageAI log --oneline origin/main..HEAD
git -C /mnt/d/Documents/Code/GitHub/ImageAI status --porcelain
```

Every listed commit must belong to the sprite feature (research `572d246` cherry-pick, design, plans, sub-projects 1–7, review fixes, the bump). Drop or rebase out anything else before the push. The status must be empty.

- [ ] **Step 2: Push the branch and the tag**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI push -u origin feat/sprite-tab
git -C /mnt/d/Documents/Code/GitHub/ImageAI push origin "v$(grep -oP '^VERSION = "\K[^"]+' /mnt/d/Documents/Code/GitHub/ImageAI/core/constants.py)"
```

- [ ] **Step 3: Write the PR body**

Fill `<N passed, M skipped>` from Task 13 Step 1 and `X.Y.0` from Task 14. Keep the footer exactly as written.

```bash
VER=$(grep -oP '^VERSION = "\K[^"]+' /mnt/d/Documents/Code/GitHub/ImageAI/core/constants.py)
BODY="$HOME/sprite-tab-pr-body.md"
cat > "$BODY" <<EOF
## Summary

Adds the Sprite tab (v${VER}): one character image plus a one-line brief becomes per-action animations, processed into engine-ready frames and exported as sprite sheets, PNG sequences, GIFs, and engine files. Design: \`Plans/2026-08-29-sprite-tab-design.md\` (selections from the 2026-08-24 feature selector).

## Sub-projects

1. **Core spine** — \`core/sprite/\`: frame/sheet metadata model, project persistence under the Images root (joins the migration journal), size presets, ffmpeg frame extraction (every-N / fps / exact-N), sheet slicing and PNG-sequence import, crop-pad-stabilize, per-stage cache with fingerprints, cancel/progress contract, grid / Aseprite JSON / TexturePacker JSON / PNG-sequence / GIF exporters.
2. **Video generation route** — source normalize, chroma plate, turnaround pack, action-card LLM contract, clip timing, Omni/Veo rendering with loop conditioning and conversational refine, action queue with retry/backoff, cost estimate + ledger, client cancel hooks.
3. **Keying & cleanup** — chroma keyer (Cr/Cb distance), despill, edge decontamination, choke/feather/despeckle, binary alpha + defringe, optional ML matting (mediapipe / rembg extras), de-jitter, per-frame overrides.
4. **Pixel-art profile** — integer fit/pad downscale, shared palette with lock/remap, Bayer and Floyd–Steinberg dither.
5. **GUI** — \`gui/sprite/\`: lazy-loaded tab, character / action-cards / queue panels, generation settings dialog with named configs, frame strip, preview player with loop-seam meter, pixel zoom view, processing panel, export dialog, SpriteWorker, shortcuts, undo, Send-to-Sprite, purge preference.
6. **Image route, retouch, engine exports** — sheet and edit-chain generation, difference matting, AI frame retouch, Godot \`.tres\`, engine presets, native \`.aseprite\` writer.
7. **CLI + docs + release** — \`cli/commands/sprite.py\` with every verb, \`--json\` contract, SIGINT cancel; user guide; feature list; README (Python 3.11+); CLI guide; \`imageai-cli\` skill; CodeMap; version bump.

## Test plan

- Full suite: <N passed, M skipped> (\`python -m pytest -q\`).
- \`tests/sprite/\` covers every core module against synthetic numpy frames and golden JSON/\`.tres\` files; GUI smoke tests run offscreen; ffmpeg tests skip when ffmpeg is absent.
- CLI: parser choices pinned to the core constants; every verb tested against mocked \`core.sprite\` entry points; \`--json\` purity with logging enabled; exit codes 0/1/2/3/130; SIGINT handler installed and restored.
- Guard tests: \`tests/test_no_hardcoded_paths.py\` and the migration journal tests stay green.
- Local review: \`code-reviewer\` agent on \`origin/main...HEAD\`; findings fixed in \`fix: address sprite review findings\`.
- Manual: GUI walkthrough (create project → cards → render → process → export) on Windows by Leland.

## Docs

- \`Docs/Sprite-Tab-Guide.md\` (new), \`Docs/Features.md\`, \`README.md\` (features, Python 3.11+, CLI examples), \`Docs/ImageAI-CLI-Guide.md\`, \`.claude/skills/imageai-cli/SKILL.md\`, \`Docs/CodeMap.md\`.
- \`CHANGELOG.md\`: v${VER} entry; tag pushed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01GtoYSE5tdovrpWRGcUUZqE
EOF
sed -n '1,12p' "$BODY"
```

- [ ] **Step 4: Open the PR**

```bash
VER=$(grep -oP '^VERSION = "\K[^"]+' /mnt/d/Documents/Code/GitHub/ImageAI/core/constants.py)
gh pr create --repo lelandg/ImageAI --base main --head feat/sprite-tab \
    --title "feat: Sprite tab — AI game-sprite animations (v${VER})" \
    --body-file "$HOME/sprite-tab-pr-body.md"
gh pr view --repo lelandg/ImageAI --json number,url,title -q '"#\(.number) \(.title)\n\(.url)"'
```

- [ ] **Step 5: Report**

Post the PR URL, the suite counts, the version, and the list of review findings with their disposition. Update the memory file `sprite-tab-feature.md` with the PR number and "awaiting merge; retag after squash if needed".

---

## Self-review

- **Spec coverage.** §4.7 table: `--sprite-cards` (+genre) ✔ Task 4; `--sprite-render` (+actions) ✔ Task 5; `--sprite-process` (+upto, force) ✔ Task 6; `--sprite-import-video/frames/sheet` (+grid) ✔ Task 3; `--sprite-export` (+preset, profile, -o) ✔ Task 7; `--sprite-new` (+source) ✔ Task 2; `--json` ✔ Task 2; dispatch after video, before the image path ✔ Task 8; sidecar next to every output ✔ Tasks 2–7; cost estimate in the render payload ✔ Task 5. Decision 3 (CLI before PR) ✔ ordering; decision 4 (README 3.11+) ✔ Task 10. Docs, skill, CodeMap, bump, PR ✔ Tasks 9–15.
- **Placeholders.** None: every step carries the full code or the full command. The only fill-ins are runtime values (`X.Y.0`, `<N passed, M skipped>`) that the steps compute.
- **Type / signature consistency.** `run_<verb>_cmd(args, token=None) -> int` for all ten verbs; `_handler_for` resolves handlers at call time so the tests' `patch.object` works; `SPRITE_VERB_ATTRS` is defined once in `cli/runner.py` and imported by the command module; `SPRITE_EXPORT_FORMATS` is defined once in `cli/parser.py`. `_status_payload` always carries the five fixed keys. Every `_report` call passes `bool(getattr(args, "json", False))`.
- **Test independence.** The tests build fake projects from `SimpleNamespace` and patch `core.sprite.<module>.<name>`; the only real core classes the tests touch are `CancelToken`, `Cancelled`, `SpriteGenerationError`, `ActionCard`, `ClipRecord`, `FrameMeta`, `TagMeta`, `SheetMeta`, and `STAGES` / `ENGINE_PRESETS` for the pin tests — all defined by the design.
- **Import cycle check.** `cli/commands/sprite.py` imports `cli.parser` and `cli.runner` at module level; `cli/runner.py` imports the sprite module lazily inside `run_cli`, so there is no cycle (same shape as `cli/commands/video.py` ↔ `cli/runner.py`).
- **Output purity.** Every human line goes through `_emit` (stderr); the only `stdout` write is the JSON object in `_report`. The regression test with `setup_logging()` guards the log handler.

## Deviations from the design

1. **`--sprite-project` instead of a positional PROJECT on each verb.** §4.7 writes `--sprite-render PROJECT`, `--sprite-process PROJECT`, `--sprite-export PROJECT`. The lead's contract for this sub-project makes those verbs flags and supplies the project through one `--sprite-project PATH` (name or `project.iasprite.json`). Reason: one flag carries the project for all nine project verbs, including the imports and the estimate that §4.7 did not enumerate.
2. **Extra flags not in §4.7:** `--sprite-list`, `--sprite-estimate`, `--sprite-profile both`, `--sprite-formats`, `--sprite-llm-provider`, `--sprite-llm-model`. The first four are in the lead's contract. The LLM pair mirrors `--layout-llm-provider/--layout-llm-model`; the card contract needs a text-LLM provider and the image `--provider` list has no `anthropic`.
3. **`--video-provider` parser default changed from `"veo"` to `None`.** Needed so a sprite render can tell "unset" from "veo" and keep the project's Omni default (decision 9). `cli/commands/video.py` already applied `or "veo"`, so `--video` behavior is unchanged; one video parser test is updated.
4. **`resolve_api_key` gains the `anthropic` env entry.** Root-cause fix for the card verb; without it `--sprite-llm-provider anthropic` could only use a stored key.
5. **Exit code `130` for cancellation.** The lead's contract lists 0/2/1; the video CLI uses 3 for unexpected exceptions. This plan keeps 0/1/2/3 from the video CLI and adds 130 (the POSIX SIGINT convention) so scripts can tell a cancel from a failure. Documented in every doc task.
6. **Run records for tree outputs.** "A `.json` sidecar next to every output" is applied literally to file outputs (`character.png`, clips, sheets, `cards.json`, `export.json` per export folder). Render and process produce trees, so they write `<project>/runs/<verb>-<timestamp>.json`; a `with_suffix(".json")` of `project.iasprite.json` would overwrite the project file.
7. **Imports force a re-run after `extract`.** The design's cache fingerprints settings and code versions, not frame content, so a re-import into an existing action would be skipped by the cache. The import verbs pass `force=True`.
8. **The CLI does not purge intermediates.** Decision 10 ties purge to a sticky QSettings preference with a confirmation dialog. A headless verb cannot show the confirmation, so the CLI never deletes; the guide says so.
9. **Core signatures the design left open.** Confirmed with the sub-project 1 planner on 2026-08-29 and used as-is: `SpriteProjectManager(base_dir=None)` with `create_project` / `list_projects` / `load_project` / `save_project` / `delete_project`, list keys `name, slug, path, created, modified, actions`; `pipeline.register_external_frames(project, action)` and the G9 extract-dir contract; `run_pipeline(project, action, *, upto="pixel", progress=no_progress, token=None, force=False)`; `pipeline.PipelineError` / `extract.FFmpegError` with `.user_message`; the nine positional `ClipRecord` fields. Name-or-slug lookup is the CLI's own `_resolve_project_path` (file → folder → `list_projects()` search), as the lead specified, so the CLI does not depend on the optional `find_project`. Confirmed by the sub-project 6 planner on 2026-08-29: the eight preset keys, `export_with_preset`, `how_to_import`, `fps_reconciliation`, and the format ids (`aseprite_native`, not `aseprite`, for the native writer — it matches the export dialog id). Still assumed: `generate_pose_instructions(action, frames, *, provider, model, api_key, log)`. If sub-project 6 picked different kwargs, change the one call in `_render_image_route` and `test_render_edit_chain_route_uses_pose_steps` — nothing else depends on it.
10. **`Docs/ImageAI-CLI-Guide.md` is updated** although the lead's docs list named only the guide, Features, README, and the skill. The skill points at the CLI guide as "full documentation", so leaving it without the sprite verbs would break that pointer.
