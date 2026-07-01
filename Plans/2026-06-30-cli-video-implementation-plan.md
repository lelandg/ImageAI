# CLI Video Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single-clip video-generation path to the ImageAI CLI (Gemini Omni + Veo), with reference images, Veo file-extend, and agent-friendly `--json` output.

**Architecture:** Mirror the existing layout-CLI routing pattern: `cli/runner.py:run_cli()` dispatches `--video` to a new `cli/commands/video.py:run_video_cmd(args)`. That module maps CLI args to `OmniGenerationConfig` / `VeoGenerationConfig`, calls the existing synchronous client wrappers, normalizes the result, writes the `.mp4` + a `.json` sidecar, and reports (human text on stderr; one JSON object on stdout with `--json`).

**Tech Stack:** Python 3.12, argparse, `core/video/omni_client.py` (`OmniClient`), `core/video/veo_client.py` (`VeoClient`, `VeoModel`), pytest with `unittest.mock`.

## Global Constraints

- Spec: `Plans/2026-06-30-cli-video-support.md` (approved).
- Providers: **Omni + Veo only**. Sora is out of scope (removal tracked in issue #32).
- Both providers authenticate with the **Google** key via `resolve_api_key(cli_key, key_file, "google")`. Veo additionally supports `--auth-mode gcloud` (project id from `GOOGLE_CLOUD_PROJECT`); Omni is **api-key only**.
- Clip length is **model-fixed** (~8s); no `--duration` flag.
- Reference images: **Omni max 1**, **Veo max 3**.
- Aspect ratios are validated by each client's `__post_init__` (Omni: `16:9`, `9:16`; Veo: `16:9`, `9:16`, `1:1`) — do not re-validate in the CLI; surface the client's `ValueError`.
- Reporting contract: progress/human lines → **stderr**; `--json` → exactly one JSON object on **stdout** and nothing else. Default (non-`--json`) writes nothing to stdout.
- Exit codes: `0` success · `1` generation failed (client returned `success=False`) · `2` user/validation error · `3` unexpected exception.
- Model IDs resolved at runtime (no hardcoding): Omni via `OmniGenerationConfig.__post_init__`; Veo via the `VeoModel` enum (default `VeoModel.VEO_3_1_GENERATE`).
- Conventional Commits; commit after each task. Branch: `feat/cli-video`.
- Tests are **fully mocked** — no real API calls. Run with `.venv_linux` + `python3 -m pytest`.

---

## File Structure

- **Create** `cli/commands/video.py` — the entire video CLI handler: arg→config builders, validation (`VideoCliError`), provider dispatch (`_run_omni`/`_run_veo`), output/sidecar writing, and reporting (`run_video_cmd`).
- **Modify** `cli/parser.py` — add a "video generation" argument group.
- **Modify** `cli/runner.py` — route `--video` to `run_video_cmd` inside `run_cli()`.
- **Modify** `README.md` — document the CLI video flags.
- **Create** tests under `tests/video/`: `test_cli_video_parser.py`, `test_cli_video_config.py`, `test_cli_video_dispatch.py`, `test_cli_video_report.py`.

---

## Task 1: Parser flags + runner routing + command skeleton

**Files:**
- Modify: `cli/parser.py` (add a "video generation" group before the `help` group, ~line 230)
- Modify: `cli/runner.py:run_cli` (add routing after the layout block, ~line 227)
- Create: `cli/commands/video.py`
- Test: `tests/video/test_cli_video_parser.py`

**Interfaces:**
- Produces: `cli/commands/video.py:run_video_cmd(args, config=None) -> int`; `_derive_output(args) -> pathlib.Path`.
- Consumes: `argparse` parser from `cli/parser.py:build_arg_parser()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/video/test_cli_video_parser.py
from unittest.mock import patch
from cli.parser import build_arg_parser


def test_video_flags_parse():
    parser = build_arg_parser()
    args = parser.parse_args([
        "--video", "-p", "a fox in snow", "-o", "fox.mp4",
        "--video-provider", "omni", "--aspect", "9:16",
        "--ref-image", "a.png", "--ref-image", "b.png",
        "--last-frame", "end.png", "--extend", "prev.mp4",
        "--video-model", "veo-3.1-fast-generate-001", "--json",
    ])
    assert args.video is True
    assert args.video_provider == "omni"
    assert args.aspect == "9:16"
    assert args.ref_image == ["a.png", "b.png"]
    assert args.last_frame == "end.png"
    assert args.extend == "prev.mp4"
    assert args.video_model == "veo-3.1-fast-generate-001"
    assert args.json is True


def test_video_provider_defaults_to_veo():
    parser = build_arg_parser()
    args = parser.parse_args(["--video", "-p", "x"])
    assert args.video_provider == "veo"


def test_run_cli_routes_to_video_command():
    parser = build_arg_parser()
    args = parser.parse_args(["--video", "-p", "x", "-o", "x.mp4"])
    with patch("cli.commands.video.run_video_cmd", return_value=0) as m:
        from cli.runner import run_cli
        rc = run_cli(args)
    assert rc == 0
    m.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/video/test_cli_video_parser.py -v`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'video'` (and `ModuleNotFoundError: cli.commands.video`).

- [ ] **Step 3: Add the parser group**

In `cli/parser.py`, immediately before the `help_group = parser.add_argument_group("help")` block, add:

```python
    # Video generation (single clip)
    video_group = parser.add_argument_group("video generation")
    video_group.add_argument(
        "--video",
        action="store_true",
        help="Generate a single video clip (uses -p/--prompt and -o/--out)",
    )
    video_group.add_argument(
        "--video-provider",
        choices=["omni", "veo"],
        default="veo",
        help="Video provider: 'omni' (Gemini Omni) or 'veo' (default: veo)",
    )
    video_group.add_argument(
        "--video-model",
        help="Video model id override (default: provider's resolved default)",
    )
    video_group.add_argument(
        "--aspect",
        help="Aspect ratio, e.g. 16:9 or 9:16 (validated per provider)",
    )
    video_group.add_argument(
        "--ref-image",
        action="append",
        metavar="PATH",
        help="Reference image (repeatable; omni: 1, veo: up to 3)",
    )
    video_group.add_argument(
        "--last-frame",
        metavar="PATH",
        help="End frame for Veo frame-to-frame interpolation (veo only)",
    )
    video_group.add_argument(
        "--extend",
        metavar="PATH",
        help="Extend this existing video (veo only); implies extend mode",
    )
    video_group.add_argument(
        "--json",
        action="store_true",
        help="Emit a single machine-readable JSON result on stdout",
    )
```

- [ ] **Step 4: Add the routing in `run_cli`**

In `cli/runner.py:run_cli`, directly after the `layout_export` routing block (currently ending ~line 227), add:

```python
    # Handle video generation (single clip)
    if getattr(args, "video", False):
        from cli.commands.video import run_video_cmd
        return run_video_cmd(args)
```

- [ ] **Step 5: Create the command skeleton**

```python
# cli/commands/video.py
"""CLI handler for single-clip video generation (Gemini Omni + Veo)."""
import logging
import sys
from pathlib import Path

from core import sanitize_filename

logger = logging.getLogger("imageai.cli.video")

OMNI_MAX_REFS = 1
VEO_MAX_REFS = 3


class VideoCliError(Exception):
    """User-facing CLI validation error (maps to exit code 2)."""


def _emit(msg: str) -> None:
    """Human-facing progress/result line -> stderr (keeps stdout pure for --json)."""
    print(msg, file=sys.stderr)


def _derive_output(args) -> Path:
    """Resolve the output .mp4 path: -o if given, else a slug from the prompt."""
    out = getattr(args, "out", None)
    if out:
        return Path(out).expanduser()
    name = sanitize_filename((getattr(args, "prompt", None) or "video")[:60]) or "video"
    return Path.cwd() / f"{name}.mp4"


def run_video_cmd(args, config=None) -> int:
    """Generate a single video clip via Gemini Omni or Veo. Returns an exit code."""
    # Full implementation lands in Tasks 2-4.
    _emit("Video CLI not yet implemented.")
    return 0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/video/test_cli_video_parser.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add cli/parser.py cli/runner.py cli/commands/video.py tests/video/test_cli_video_parser.py
git commit -m "feat(cli-video): add video flags, runner routing, command skeleton"
```

---

## Task 2: Config builders + validation (pure functions)

**Files:**
- Modify: `cli/commands/video.py`
- Test: `tests/video/test_cli_video_config.py`

**Interfaces:**
- Consumes: `OMNI_MAX_REFS`, `VEO_MAX_REFS`, `VideoCliError` (Task 1).
- Produces:
  - `build_omni_config(args) -> core.video.omni_client.OmniGenerationConfig`
  - `build_veo_config(args) -> core.video.veo_client.VeoGenerationConfig`
  - `_ref_images(args) -> list[pathlib.Path]`
  - `_veo_model(args) -> core.video.veo_client.VeoModel`

- [ ] **Step 1: Write the failing test**

```python
# tests/video/test_cli_video_config.py
from argparse import Namespace
import pytest
from cli.commands.video import build_omni_config, build_veo_config, VideoCliError


def _ns(**kw):
    base = dict(prompt="p", aspect=None, ref_image=None, last_frame=None,
                extend=None, video_model=None)
    base.update(kw)
    return Namespace(**base)


def test_omni_text_to_video():
    cfg = build_omni_config(_ns())
    assert cfg.task == "text_to_video"
    assert cfg.reference_image is None


def test_omni_single_ref_is_image_to_video():
    cfg = build_omni_config(_ns(ref_image=["a.png"]))
    assert cfg.task == "image_to_video"
    assert str(cfg.reference_image).endswith("a.png")


def test_omni_rejects_extend():
    with pytest.raises(VideoCliError, match="extend"):
        build_omni_config(_ns(extend="prev.mp4"))


def test_omni_rejects_last_frame():
    with pytest.raises(VideoCliError, match="last-frame"):
        build_omni_config(_ns(last_frame="end.png"))


def test_omni_rejects_two_refs():
    with pytest.raises(VideoCliError, match="1 reference"):
        build_omni_config(_ns(ref_image=["a.png", "b.png"]))


def test_veo_accepts_three_refs():
    cfg = build_veo_config(_ns(ref_image=["a.png", "b.png", "c.png"]))
    assert len(cfg.reference_images) == 3


def test_veo_rejects_four_refs():
    with pytest.raises(VideoCliError, match="up to 3"):
        build_veo_config(_ns(ref_image=["a", "b", "c", "d"]))


def test_veo_unknown_model_errors():
    with pytest.raises(VideoCliError, match="Unknown Veo model"):
        build_veo_config(_ns(video_model="not-a-model"))


def test_veo_default_model():
    from core.video.veo_client import VeoModel
    cfg = build_veo_config(_ns())
    assert cfg.model == VeoModel.VEO_3_1_GENERATE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/video/test_cli_video_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_omni_config'`.

- [ ] **Step 3: Implement the builders**

Add to `cli/commands/video.py` (below `_derive_output`):

```python
def _ref_images(args):
    """Reference image paths from repeated --ref-image (empty list if none)."""
    return [Path(p).expanduser() for p in (getattr(args, "ref_image", None) or [])]


def build_omni_config(args):
    """Map CLI args to an OmniGenerationConfig (raises VideoCliError on misuse)."""
    from core.video.omni_client import OmniGenerationConfig
    if getattr(args, "extend", None):
        raise VideoCliError("--extend is only supported with --video-provider veo.")
    if getattr(args, "last_frame", None):
        raise VideoCliError("--last-frame is only supported with --video-provider veo.")
    refs = _ref_images(args)
    if len(refs) > OMNI_MAX_REFS:
        raise VideoCliError(
            f"Gemini Omni supports {OMNI_MAX_REFS} reference image; got {len(refs)}."
        )
    kwargs = dict(
        prompt=getattr(args, "prompt", None) or "",
        task="image_to_video" if refs else "text_to_video",
        aspect_ratio=getattr(args, "aspect", None) or "16:9",
    )
    if getattr(args, "video_model", None):
        kwargs["model"] = args.video_model
    if refs:
        kwargs["reference_image"] = refs[0]
    try:
        return OmniGenerationConfig(**kwargs)  # __post_init__ validates aspect/task
    except ValueError as e:
        raise VideoCliError(str(e))


def _veo_model(args):
    """Resolve --video-model to a VeoModel enum (default: Veo 3.1 GA)."""
    from core.video.veo_client import VeoModel
    val = getattr(args, "video_model", None)
    if not val:
        return VeoModel.VEO_3_1_GENERATE
    try:
        return VeoModel(val)
    except ValueError:
        choices = ", ".join(m.value for m in VeoModel)
        raise VideoCliError(f"Unknown Veo model {val!r}. Choices: {choices}")


def build_veo_config(args):
    """Map CLI args to a VeoGenerationConfig (raises VideoCliError on misuse)."""
    from core.video.veo_client import VeoGenerationConfig
    refs = _ref_images(args)
    if len(refs) > VEO_MAX_REFS:
        raise VideoCliError(
            f"Veo supports up to {VEO_MAX_REFS} reference images; got {len(refs)}."
        )
    kwargs = dict(
        model=_veo_model(args),
        prompt=getattr(args, "prompt", None) or "",
        aspect_ratio=getattr(args, "aspect", None) or "16:9",
    )
    if refs:
        kwargs["reference_images"] = refs
    if getattr(args, "last_frame", None):
        kwargs["last_frame"] = Path(args.last_frame).expanduser()
    try:
        return VeoGenerationConfig(**kwargs)  # __post_init__ validates model/refs
    except ValueError as e:
        raise VideoCliError(str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/video/test_cli_video_config.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add cli/commands/video.py tests/video/test_cli_video_config.py
git commit -m "feat(cli-video): arg->config builders with per-provider validation"
```

---

## Task 3: Provider dispatch + execution (mocked clients)

**Files:**
- Modify: `cli/commands/video.py`
- Test: `tests/video/test_cli_video_dispatch.py`

**Interfaces:**
- Consumes: `build_omni_config`, `build_veo_config` (Task 2); `resolve_api_key` from `cli.runner`.
- Produces:
  - `_run_omni(args, out_path: Path) -> dict`
  - `_run_veo(args, out_path: Path) -> dict`
  - Both return a normalized dict with keys: `success, output_path, provider, model, aspect_ratio, operation_id, error`.

- [ ] **Step 1: Write the failing test**

```python
# tests/video/test_cli_video_dispatch.py
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from cli.commands.video import _run_omni, _run_veo, VideoCliError


def _ns(**kw):
    base = dict(prompt="p", aspect="16:9", ref_image=None, last_frame=None,
                extend=None, video_model=None, api_key="k", api_key_file=None,
                auth_mode="api-key")
    base.update(kw)
    return Namespace(**base)


def test_run_omni_returns_normalized_result(tmp_path):
    out = tmp_path / "o.mp4"
    fake = MagicMock()
    fake.generate_video.return_value = MagicMock(
        success=True, video_path=out, interaction_id="int-1", error=None)
    with patch("core.video.omni_client.OmniClient", return_value=fake), \
         patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        res = _run_omni(_ns(), out)
    assert res["success"] is True
    assert res["provider"] == "omni"
    assert res["operation_id"] == "int-1"
    fake.generate_video.assert_called_once()


def test_run_omni_rejects_gcloud():
    with patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        with pytest.raises(VideoCliError, match="api-key auth only"):
            _run_omni(_ns(auth_mode="gcloud"), Path("o.mp4"))


def test_run_omni_missing_key_errors():
    with patch("cli.commands.video.resolve_api_key", return_value=(None, "none")):
        with pytest.raises(VideoCliError, match="No Google API key"):
            _run_omni(_ns(api_key=None), Path("o.mp4"))


def test_run_veo_copies_output(tmp_path):
    src = tmp_path / "veo_native.mp4"
    src.write_bytes(b"vid")
    out = tmp_path / "final.mp4"
    fake = MagicMock()
    fake.generate_video.return_value = MagicMock(
        success=True, video_path=src, operation_id="op-1", error=None)
    with patch("core.video.veo_client.VeoClient", return_value=fake), \
         patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        res = _run_veo(_ns(), out)
    assert res["success"] is True
    assert out.exists() and out.read_bytes() == b"vid"
    assert res["operation_id"] == "op-1"


def test_run_veo_extend_calls_extend(tmp_path):
    prev = tmp_path / "prev.mp4"
    prev.write_bytes(b"old")
    out = tmp_path / "ext.mp4"
    native = tmp_path / "veo_ext.mp4"
    native.write_bytes(b"new")
    fake = MagicMock()
    fake.extend_video.return_value = MagicMock(
        success=True, video_path=native, operation_id="op-2", error=None)
    with patch("core.video.veo_client.VeoClient", return_value=fake), \
         patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        res = _run_veo(_ns(extend=str(prev)), out)
    fake.extend_video.assert_called_once()
    assert res["success"] is True


def test_run_veo_extend_missing_file_errors(tmp_path):
    with patch("cli.commands.video.resolve_api_key", return_value=("k", "config")):
        with pytest.raises(VideoCliError, match="extend video not found"):
            _run_veo(_ns(extend=str(tmp_path / "nope.mp4")), tmp_path / "o.mp4")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/video/test_cli_video_dispatch.py -v`
Expected: FAIL — `ImportError: cannot import name '_run_omni'`.

- [ ] **Step 3: Implement dispatch**

Add `import shutil` to the top imports of `cli/commands/video.py`, add `from cli.runner import resolve_api_key` near the other imports, then add:

```python
def _run_omni(args, out_path):
    """Generate via Gemini Omni; writes directly to out_path. Returns normalized dict."""
    from core.video.omni_client import OmniClient
    if getattr(args, "auth_mode", "api-key") == "gcloud":
        raise VideoCliError(
            "Gemini Omni supports api-key auth only (not --auth-mode gcloud)."
        )
    key, _src = resolve_api_key(
        getattr(args, "api_key", None), getattr(args, "api_key_file", None), "google")
    if not key:
        raise VideoCliError(
            "No Google API key found. Use --api-key/--api-key-file or set GOOGLE_API_KEY.")
    cfg = build_omni_config(args)
    _emit(f"[omni] generating video (aspect={cfg.aspect_ratio}, model={cfg.model})...")
    result = OmniClient(api_key=key).generate_video(cfg, out_path)
    return {
        "success": bool(result.success),
        "output_path": str(result.video_path or out_path),
        "provider": "omni",
        "model": cfg.model,
        "aspect_ratio": cfg.aspect_ratio,
        "operation_id": getattr(result, "interaction_id", None),
        "error": getattr(result, "error", None),
    }


def _run_veo(args, out_path):
    """Generate or extend via Veo; copies Veo's saved file to out_path. Returns dict."""
    import os
    from core.video.veo_client import VeoClient
    cfg = build_veo_config(args)
    if getattr(args, "auth_mode", "api-key") == "gcloud":
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise VideoCliError(
                "--auth-mode gcloud requires GOOGLE_CLOUD_PROJECT to be set.")
        client = VeoClient(auth_mode="gcloud", project_id=project_id)
    else:
        key, _src = resolve_api_key(
            getattr(args, "api_key", None), getattr(args, "api_key_file", None), "google")
        if not key:
            raise VideoCliError(
                "No Google API key found. Use --api-key/--api-key-file or set GOOGLE_API_KEY.")
        client = VeoClient(api_key=key, auth_mode="api-key")

    extend = getattr(args, "extend", None)
    if extend:
        prev = Path(extend).expanduser()
        if not prev.exists():
            raise VideoCliError(f"--extend video not found: {prev}")
        _emit(f"[veo] extending {prev.name} (model={cfg.model.value})...")
        result = client.extend_video(previous_video_path=prev,
                                     prompt=getattr(args, "prompt", None) or "", config=cfg)
    else:
        _emit(f"[veo] generating video (aspect={cfg.aspect_ratio}, model={cfg.model.value})...")
        result = client.generate_video(cfg)

    final_path = out_path
    if result.success and result.video_path and Path(result.video_path) != out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result.video_path, out_path)
    elif not result.success:
        final_path = Path(result.video_path) if result.video_path else out_path

    return {
        "success": bool(result.success),
        "output_path": str(final_path),
        "provider": "veo",
        "model": cfg.model.value,
        "aspect_ratio": cfg.aspect_ratio,
        "operation_id": getattr(result, "operation_id", None),
        "error": getattr(result, "error", None),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/video/test_cli_video_dispatch.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add cli/commands/video.py tests/video/test_cli_video_dispatch.py
git commit -m "feat(cli-video): omni/veo dispatch + execution (generate, extend, copy-out)"
```

---

## Task 4: Reporting (sidecar, --json, stderr) + wire `run_video_cmd`

**Files:**
- Modify: `cli/commands/video.py` (replace the skeleton `run_video_cmd`)
- Test: `tests/video/test_cli_video_report.py`

**Interfaces:**
- Consumes: `_run_omni`, `_run_veo`, `_derive_output`, `VideoCliError` (Tasks 1-3).
- Produces:
  - `_status_payload(result: dict) -> dict` (keys: `status, output_path, provider, model, aspect_ratio, operation_id, error`)
  - `_write_sidecar(out_path: Path, payload: dict) -> None`
  - `_report(result: dict, as_json: bool, exit_code: int) -> int`
  - `run_video_cmd(args, config=None) -> int` (final form)

- [ ] **Step 1: Write the failing test**

```python
# tests/video/test_cli_video_report.py
import json
from argparse import Namespace
from unittest.mock import patch
from cli.commands.video import run_video_cmd


def _ns(**kw):
    base = dict(prompt="p", out=None, aspect="16:9", ref_image=None, last_frame=None,
                extend=None, video_model=None, api_key="k", api_key_file=None,
                auth_mode="api-key", video_provider="veo", json=False)
    base.update(kw)
    return Namespace(**base)


def _ok(out):
    return {"success": True, "output_path": str(out), "provider": "veo",
            "model": "veo-3.1-generate-001", "aspect_ratio": "16:9",
            "operation_id": "op-1", "error": None}


def test_success_writes_sidecar_and_returns_zero(tmp_path):
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", return_value=_ok(out)):
        rc = run_video_cmd(_ns(out=str(out)))
    assert rc == 0
    sidecar = out.with_suffix(".json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["status"] == "completed"
    assert data["provider"] == "veo"


def test_json_mode_prints_one_object_to_stdout(tmp_path, capsys):
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", return_value=_ok(out)):
        rc = run_video_cmd(_ns(out=str(out), json=True))
    captured = capsys.readouterr()
    assert rc == 0
    obj = json.loads(captured.out)  # exactly one JSON object, nothing else on stdout
    assert obj["status"] == "completed"
    assert obj["operation_id"] == "op-1"


def test_non_json_mode_keeps_stdout_empty(tmp_path, capsys):
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", return_value=_ok(out)):
        run_video_cmd(_ns(out=str(out), json=False))
    captured = capsys.readouterr()
    assert captured.out == ""           # human text goes to stderr only
    assert "Video saved" in captured.err


def test_validation_error_returns_two(tmp_path, capsys):
    # omni + --extend is a VideoCliError raised inside _run_omni
    out = tmp_path / "v.mp4"
    rc = run_video_cmd(_ns(out=str(out), video_provider="omni",
                           extend="prev.mp4", json=True))
    captured = capsys.readouterr()
    assert rc == 2
    obj = json.loads(captured.out)
    assert obj["status"] == "failed"
    assert "extend" in obj["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/video/test_cli_video_report.py -v`
Expected: FAIL — skeleton `run_video_cmd` returns 0 without writing a sidecar (assertions fail).

- [ ] **Step 3: Implement reporting + final `run_video_cmd`**

Add `import json` to the top of `cli/commands/video.py`. Replace the skeleton `run_video_cmd` with:

```python
def _status_payload(result):
    """Normalized result dict -> the documented JSON/sidecar shape."""
    return {
        "status": "completed" if result.get("success") else "failed",
        "output_path": result.get("output_path"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "aspect_ratio": result.get("aspect_ratio"),
        "operation_id": result.get("operation_id"),
        "error": result.get("error"),
    }


def _write_sidecar(out_path, payload):
    """Write the JSON sidecar next to the .mp4 (best-effort; logs on failure)."""
    sidecar = out_path.with_suffix(".json")
    try:
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write sidecar %s: %s", sidecar, e)


def _report(result, as_json, exit_code):
    """Emit the result (stdout JSON if as_json, else stderr text) and return exit_code."""
    payload = _status_payload(result)
    if as_json:
        print(json.dumps(payload), file=sys.stdout)
    elif result.get("success"):
        _emit(f"✅ Video saved: {result.get('output_path')}")
    else:
        _emit(f"❌ Video generation failed: {result.get('error')}")
    return exit_code


def run_video_cmd(args, config=None) -> int:
    """Generate a single video clip via Gemini Omni or Veo. Returns an exit code."""
    provider = (getattr(args, "video_provider", None) or "veo").strip().lower()
    as_json = bool(getattr(args, "json", False))
    out_path = _derive_output(args)

    def _fail(message, code):
        logger.error("Video CLI: %s", message)
        return _report({
            "success": False, "output_path": str(out_path), "provider": provider,
            "model": getattr(args, "video_model", None),
            "aspect_ratio": getattr(args, "aspect", None),
            "operation_id": None, "error": message,
        }, as_json, code)

    try:
        if provider == "omni":
            result = _run_omni(args, out_path)
        elif provider == "veo":
            result = _run_veo(args, out_path)
        else:
            return _fail(f"Unknown --video-provider {provider!r}. Choices: omni, veo.", 2)
    except VideoCliError as e:
        return _fail(str(e), 2)
    except Exception as e:  # noqa: BLE001 - surface + log any client/runtime failure
        logger.error("Video generation failed: %s", e, exc_info=True)
        return _fail(str(e), 3)

    _write_sidecar(out_path, _status_payload(result))
    return _report(result, as_json, 0 if result["success"] else 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/video/test_cli_video_report.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full video + layout suites (no regressions)**

Run: `python3 -m pytest tests/video tests/layout -q`
Expected: PASS (existing 388 layout + 22 video + the new CLI video tests).

- [ ] **Step 6: Commit**

```bash
git add cli/commands/video.py tests/video/test_cli_video_report.py
git commit -m "feat(cli-video): sidecar + --json reporting, full run_video_cmd wiring"
```

---

## Task 5: Docs + plan status + final verification

**Files:**
- Modify: `README.md` (add a CLI video subsection)
- Modify: `Plans/2026-06-30-cli-video-support.md` (mark Implementation Status done)

**Interfaces:** none (documentation only).

- [ ] **Step 1: Add a README CLI video section**

Find the CLI usage / "Running the Application" area of `README.md` and add:

````markdown
### Generate video (CLI)

Single-clip video generation with Gemini Omni or Veo:

```bash
# Text -> video (Veo is the default provider)
python main.py --video -p "a fox running through snow" -o fox.mp4

# Gemini Omni, portrait
python main.py --video --video-provider omni --aspect 9:16 -p "neon city" -o city.mp4

# Reference images (Veo up to 3, Omni 1)
python main.py --video -p "she walks toward camera" -o walk.mp4 \
    --ref-image style.png --ref-image character.png

# Extend an existing clip (Veo only)
python main.py --video --extend fox.mp4 -p "the fox leaps a log" -o fox2.mp4

# Machine-readable result for agents (single JSON object on stdout)
python main.py --video -p "a fox in snow" -o fox.mp4 --json
```

Both providers use the Google API key (`--api-key`/`--api-key-file`/`GOOGLE_API_KEY`);
Veo also supports `--auth-mode gcloud` (`GOOGLE_CLOUD_PROJECT`). A `.json` sidecar is
written next to the `.mp4`. Clip length is model-fixed (~8s).
````

- [ ] **Step 2: Update the spec's Implementation Status**

In `Plans/2026-06-30-cli-video-support.md`, change the `## 8. Implementation Status` bullets from `⏳` to `✅` and set `**Status:**` at the top to `✅ Implemented`.

- [ ] **Step 3: Full suite verification**

Run: `python3 -m pytest tests/ -q`
Expected: PASS — no regressions across the whole suite.

- [ ] **Step 4: Smoke-check the CLI help lists the flags**

Run: `python3 main.py -h | grep -- "--video"`
Expected: the `--video`, `--video-provider`, `--video-model`, `--aspect`, `--ref-image`, `--last-frame`, `--extend`, `--json` flags appear.

- [ ] **Step 5: Commit**

```bash
git add README.md Plans/2026-06-30-cli-video-support.md
git commit -m "docs(cli-video): README usage + mark spec implemented"
```

---

## Self-Review

**Spec coverage**
- §2 architecture (new `cli/commands/video.py` + routing) → Task 1. ✅
- §3 flags (`--video`, `--video-provider`, `--video-model`, `--aspect`, `--ref-image`, `--last-frame`, `--extend`, `--json`) → Task 1. ✅
- §4 dispatch/auth (omni api-key; veo api-key + gcloud; extend) → Task 3. ✅
- §5 output (`-o` or derived name), sidecar, `--json`/stderr → Tasks 1 (`_derive_output`) + 4. ✅
- §6 validation/errors (extend/last-frame+omni, ref counts, gcloud+omni, missing key, unknown model/aspect) → Tasks 2 + 3 + 4. ✅
- §7 testing (parser, dispatch, guards, json shape, sidecar, exit codes) → Tasks 1-4 test files. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code. The parser factory is confirmed as `cli/parser.py:build_arg_parser()` and used verbatim in Task 1.

**Type consistency:** Normalized result dict keys (`success, output_path, provider, model, aspect_ratio, operation_id, error`) are identical across `_run_omni`/`_run_veo`/`run_video_cmd`/`_status_payload`. `VeoModel(value)` and `OmniGenerationConfig(**kwargs)` match the verified client signatures. `extend_video(previous_video_path, prompt, config)` and `generate_video(config[, output_path])` match the verified wrappers.
