"""Headless Sprite generation commands, with recoverable candidate outputs.

The core owns provider prompts, media formats and processing. This module owns
CLI selection, credentials, save checkpoints and promotion of accepted results.
"""
from __future__ import annotations

import copy
import logging
import uuid
from contextlib import contextmanager
from pathlib import Path

from PIL import Image

from core.sprite.generation import action_cards, image_route, plate, retouch, turnaround, video_route
from core.sprite.generation._common import now_iso, redact_secrets
from core.sprite.generation.cost import estimate_action, record_actual
from core.sprite.generation.errors import ProviderError, SpriteGenerationError
from core.sprite.generation.pose_steps import fallback_pose_steps, generate_pose_instructions
from core.sprite.models import FrameMeta
from core.sprite.pipeline import (
    Cancelled, is_stage_current, register_external_frames, run_pipeline, stage_dir,
)
from core.sprite.project import CostEntry, SpriteProject
from core.utils import write_image_sidecar

GENERATION_OPERATIONS = ("cards", "render", "plate", "turnaround", "refine", "loop-trim", "retouch", "estimate")


def _count_image_calls(provider):
    """Count returned edit calls, including a rejected retouch or half matte pair.

    Providers are fresh, uncached instances. Wrapping their bound methods keeps
    core provider capability checks intact and never adds retry behavior.
    """
    completed = [0]

    def counted(method):
        def invoke(*args, **kwargs):
            result = method(*args, **kwargs)
            completed[0] += 1
            return result
        return invoke

    for name in ("edit_image", "edit_image_region"):
        method = getattr(provider, name, None)
        if callable(method):
            setattr(provider, name, counted(method))
    return completed


def select_actions(project, selectors=None, *, single=False):
    """Resolve every selector before mutating anything; names must be exact."""
    if selectors is None:
        if single:
            raise ValueError("This operation requires exactly one action in 'actions'.")
        return list(project.actions)
    if not isinstance(selectors, list) or not selectors:
        raise ValueError("'actions' must be a nonempty list of action ids or names.")
    result = []
    for selector in selectors:
        if not isinstance(selector, str):
            raise ValueError("Action selectors must be strings.")
        matches = [a for a in project.actions if a.id == selector or a.name == selector]
        if not matches:
            raise ValueError(f"Unknown action: {selector!r}")
        if len(matches) != 1:
            raise ValueError(f"Ambiguous action: {selector!r}; use its unique id.")
        if matches[0] in result:
            raise ValueError(f"Repeated action selector: {selector!r}")
        result.append(matches[0])
    if single and len(result) != 1:
        raise ValueError("This operation requires exactly one action in 'actions'.")
    return result


def _integer(data, key, default, low, high):
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"'{key}' must be an integer from {low} to {high}.")
    return value


def _boolean(data, key, default=False):
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"'{key}' must be true or false.")
    return value


def _text(data, key, default="", *, required=False):
    value = data.get(key, default)
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"'{key}' must be {'nonempty ' if required else ''}text.")
    return value.strip()


class _Secrets(logging.Filter):
    def __init__(self):
        super().__init__()
        self.values = []

    def clean(self, text):
        value = str(text)
        for secret in self.values:
            value = value.replace(secret, "***")
        return redact_secrets(value)

    def filter(self, record):
        record.msg = self.clean(record.getMessage())
        record.args = ()
        # Raw provider traceback strings can contain request credentials.
        if record.exc_info:
            record.exc_text = self.clean(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


@contextmanager
def _safe_logging(secrets):
    # Core helpers log to their own file logger before calling the CLI sink.
    # Filter both that path and the sink, preserving complete nonsecret content.
    targets: list[logging.Logger | logging.Handler] = [logging.getLogger(name) for name in (
        "core.sprite.generation.action_cards", "core.sprite.generation.image_route",
        "core.sprite.generation.plate", "core.sprite.generation.turnaround",
        "core.sprite.generation.retouch", "core.sprite.generation.pose_steps",
        "core.sprite.generation.video_route", "core.sprite.generation.errors",
    )]
    targets.extend(logging.getLogger().handlers)
    for target in targets:
        target.addFilter(secrets)
    try:
        yield
    finally:
        for target in targets:
            target.removeFilter(secrets)


def _credentials(provider, auth_mode, secrets):
    from cli.runner import resolve_api_key
    from core.config import ConfigManager

    provider = "google" if provider in ("gemini", "veo", "omni") else provider
    auth_mode = auth_mode or ConfigManager().get_auth_mode(provider)
    if auth_mode not in ("api-key", "gcloud"):
        raise ValueError("auth_mode must be 'api-key' or 'gcloud'.")
    if auth_mode == "gcloud" and provider != "google":
        raise ValueError("gcloud authentication is only supported for Google.")
    key = None
    if auth_mode != "gcloud":
        key, _source = resolve_api_key(None, None, provider)
        if not key:
            raise ValueError(f"No {provider} API key is configured.")
        secrets.values.append(key)
    return key, auth_mode


def _image_provider(data, secrets):
    from providers import get_provider

    name = _text(data, "provider", "google")
    if name not in ("google", "openai"):
        raise ValueError("Sprite image operations support provider 'google' or 'openai'.")
    key, auth = _credentials(name, data.get("auth_mode"), secrets)
    provider = get_provider(name, {"api_key": key, "auth_mode": auth}, use_cache=False)
    model = _text(data, "model") or (
        image_route.default_openai_edit_model() if name == "openai" else provider.get_default_model())
    return provider, name, model


def _chat_settings(data, secrets):
    provider = _text(data, "llm_provider", "google")
    if provider not in ("google", "gemini", "openai", "anthropic"):
        raise ValueError("Unsupported llm_provider; use google, openai or anthropic.")
    key, auth = _credentials(provider, data.get("llm_auth_mode", data.get("auth_mode")), secrets)
    return {"provider": provider, "model": _text(data, "llm_model") or None,
            "api_key": key, "auth_mode": auth}


def _source(project, *, plate_required=False):
    path = (project.character_source if project.background.mode == "original"
            else project.plate_path or (None if plate_required else project.character_source))
    if path is None or not Path(path).is_file():
        raise ValueError("Import a character image first" +
                         (" and make a chroma plate before video rendering." if plate_required else "."))
    return Path(path)


def _unique(project, folder, stem, suffix):
    path = Path(project.project_dir) / folder / f"{stem}-{uuid.uuid4().hex[:12]}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _image_cost(project, action, provider, model, units, note):
    if units <= 0:
        return
    project.cost_ledger.append(CostEntry(
        action_id=action.id if action else "", action_name=action.name if action else project.name,
        provider=provider, model=model, seconds=float(units), estimated_usd=None,
        actual_usd=None, timestamp=now_iso(), note=f"{note}; {units} completed image call(s)"))


def _candidate(project, action):
    candidate = copy.deepcopy(project)
    candidate.project_dir = _unique(project, "candidates", action.id, "")
    candidate.project_dir.mkdir(parents=True)
    candidate.stage_fingerprints = {}
    card = copy.deepcopy(action)
    card.frames = []
    card.clip = None
    card.error = None
    card.status = "rendered"
    candidate.actions = [card]
    return candidate, card


def _frames(paths, action):
    frames = []
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            w, h = image.size
        frames.append(FrameMeta(name=f"{action.name}_{index:02d}", source_path=path,
                                frame=(0, 0, w, h), sprite_source_size=(0, 0, w, h),
                                source_size=(w, h), duration_ms=round(1000 / max(1, action.fps))))
    return frames


def _promote(project, action, candidate, card):
    """Replace a complete stage tree, retaining the previous tree for recovery."""
    source = stage_dir(candidate, card, "extract").parent
    destination = stage_dir(project, action, "extract").parent
    archive = destination.with_name(f"{destination.name}.prev-{uuid.uuid4().hex[:12]}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    before = copy.deepcopy(action)
    old_fingerprints = copy.deepcopy(project.stage_fingerprints.get(action.id))
    moved_old = moved_new = False
    try:
        if destination.exists():
            destination.rename(archive)
            moved_old = True
        if source.exists():
            source.rename(destination)
            moved_new = True
        for frame in card.frames:
            if frame.source_path is not None:
                try:
                    frame.source_path = destination / Path(frame.source_path).relative_to(source)
                except ValueError:
                    pass
        action.frames, action.clip = card.frames, card.clip
        action.target_frames = card.target_frames
        action.status, action.error = card.status, None
        project.stage_fingerprints[action.id] = candidate.stage_fingerprints.get(card.id, {})
        project.save()
    except BaseException:
        # SIGINT and a failed atomic project save are rollback boundaries too.
        if moved_new:
            source.parent.mkdir(parents=True, exist_ok=True)
            destination.rename(source)
        if moved_old:
            archive.rename(destination)
        action.__dict__.update(before.__dict__)
        if old_fingerprints is None:
            project.stage_fingerprints.pop(action.id, None)
        else:
            project.stage_fingerprints[action.id] = old_fingerprints
        raise
    return str(archive) if archive.exists() else None


def _route(data):
    route = _text(data, "route", "video")
    if route not in ("video", "sheet", "edit-chain"):
        raise ValueError("route must be 'video', 'sheet' or 'edit-chain'.")
    return route


def _pose_steps(data, action, count, secrets, log, token):
    steps = data.get("pose_instructions")
    if isinstance(steps, dict):
        steps = steps.get(action.id, steps.get(action.name))
    if steps is not None:
        if (not isinstance(steps, list) or len(steps) != count or
                any(not isinstance(step, str) or not step.strip() for step in steps)):
            raise ValueError(f"pose_instructions for {action.name!r} must contain {count} nonempty strings.")
        return steps
    if _boolean(data, "generate_poses"):
        token.raise_if_cancelled()
        steps = generate_pose_instructions(action, count, **_chat_settings(data, secrets),
                                           character_notes=_text(data, "character_notes"), log=log)
        token.raise_if_cancelled()
        return steps
    return fallback_pose_steps(action, count)


def _slice_checked_sheet(sheet, extract, requested, project, log):
    """Inspect the returned sheet, never silently fall back to cutting figures."""
    from core.sprite.slicing import foreground_mask, guess_grid
    from core.sprite.source import analyze_source

    analysis = analyze_source(sheet)
    sampled = analysis.border_color if analysis.border_uniform else None
    color = sampled or project.plate_color
    warnings = []
    evidence = {"requested_frames": requested, "requested_key_color": project.plate_color,
                "sampled_key_color": sampled, "border_uniform": analysis.border_uniform}
    if project.background.mode == "original":
        # Scenery is not a chroma grid. The explicit original-background route
        # still supports equal cells, with its verification boundary visible.
        count = requested
        evidence.update({"columns": requested, "rows": 1, "confidence": None,
                         "layout_verified": False})
        warnings.append("Original-background sheet uses the requested equal-cell layout; visually verify pose boundaries.")
    else:
        with Image.open(sheet) as image:
            guess = guess_grid(image, key_color=color)
            mask = foreground_mask(image, key_color=color)
        count = guess.columns * guess.rows
        evidence.update({"columns": guess.columns, "rows": guess.rows,
                         "confidence": guess.confidence, "layout_verified": False})
        if guess.confidence < image_route.MIN_GRID_CONFIDENCE or count < 2:
            raise ProviderError(f"Sheet grid is ambiguous: detected {guess.columns}x{guess.rows}, "
                             f"confidence {guess.confidence:.3f}, sampled border {sampled or 'nonuniform'}. "
                             f"Saved sheet: {sheet}. Inspect it and use import-sheet with an explicit grid; "
                             "no accepted frames were replaced.")
        height, width = mask.shape
        cell_w, cell_h = width // guess.columns, height // guess.rows
        crossed = any(mask[:, index * cell_w - 1:index * cell_w + 1].any()
                      for index in range(1, guess.columns))
        crossed = crossed or any(mask[index * cell_h - 1:index * cell_h + 1, :].any()
                                 for index in range(1, guess.rows))
        cropped_edge = (mask[:, cell_w * guess.columns:].any() or
                        mask[cell_h * guess.rows:, :].any())
        if crossed or cropped_edge:
            raise ProviderError(f"Detected {guess.columns}x{guess.rows} grid (confidence {guess.confidence:.3f}) "
                             f"would cut foreground pixels. Saved sheet: {sheet}. "
                             "Use import-sheet with explicit cell, margin and spacing settings.")
        evidence["layout_verified"] = True
        if sampled and sampled.upper() != project.plate_color.upper():
            warnings.append(f"Sheet border is {sampled}; grid detection used that sampled color instead of {project.plate_color}.")
        if count != requested:
            warnings.append(f"Model returned {count} detected poses for {requested} requested frames; using the detected grid.")
    evidence["actual_frames"] = count
    evidence["warnings"] = warnings
    for warning in warnings:
        log(f"Sheet warning: {warning}")
    log(f"Sheet grid: {evidence}")
    paths = image_route.slice_generated_sheet(sheet, extract, count, color, log=log,
                                              background_mode=project.background.mode)
    return paths, evidence


def _render(project, data, log, progress, token, secrets):
    route = _route(data)
    actions = select_actions(project, data.get("actions"))
    if not actions:
        raise ValueError("Create action cards before rendering.")
    process = _boolean(data, "process", True)
    source = _source(project, plate_required=route == "video")
    # Validate all explicit pose lists and counts before the first paid call.
    for action in actions:
        count = _integer(data, "frames", action.target_frames, 2 if route == "sheet" else 1, 64)
        if data.get("pose_instructions") is not None:
            _pose_steps({**data, "generate_poses": False}, action, count, secrets, log, token)
    if route == "video":
        invalid = video_route.validate_generation_settings(project.generation)
        if invalid:
            raise ValueError(invalid)
        key, auth = _credentials(project.generation.provider, data.get("auth_mode"), secrets)
    else:
        provider, provider_name, model = _image_provider(data, secrets)
        completed_calls = _count_image_calls(provider)
    results, files = [], []
    for action in actions:
        token.raise_if_cancelled()
        candidate, card = _candidate(project, action)
        count = _integer(data, "frames", action.target_frames, 2 if route == "sheet" else 1, 64)
        card.target_frames = count
        extract = stage_dir(candidate, card, "extract")
        matte = (_boolean(data, "matte_pairs") and project.background.mode != "original")
        sheet = None
        sheet_grid = None
        accounted = False
        starting_calls = completed_calls[0] if route != "video" else 0
        previous_status = action.status
        action.status, action.error = "rendering", None
        project.save()
        try:
            if route == "video":
                refs = ([Path(project.turnaround[v]) for v in turnaround.VIEWS if v in project.turnaround]
                        if project.generation.use_turnaround_refs and project.background.mode != "original" else [])
                out = _unique(project, "clips", action.id, ".mp4")
                request = video_route.RenderRequest(card, source, refs, copy.deepcopy(project.generation),
                                                    out, project.background.mode)
                card.clip = video_route.render_action(request, api_key=key, auth_mode=auth,
                                                       progress=progress, token=token, log=log)
                record_actual(project, card, None, note="CLI video render")
                files.append(str(out))
            else:
                if route == "sheet":
                    out = _unique(project, "clips", f"{action.id}-sheet", ".png")
                    sheet = image_route.generate_sheet(provider, source, card, out, frames=count,
                        plate_color=project.plate_color, background_mode=project.background.mode,
                        model=model, log=log, token=token)
                    paths, sheet_grid = _slice_checked_sheet(sheet, extract, count, project, log)
                    card.target_frames = len(paths)
                    units = 1
                    files.append(str(sheet))
                else:
                    steps = _pose_steps(data, action, count, secrets, log, token)
                    paths = image_route.edit_chain(provider, source, card, extract, frames=count,
                        pose_instructions=steps, plate_color=project.plate_color,
                        background_mode=project.background.mode, model=model, log=log,
                        token=token, matte_pairs=matte)
                    units = len(paths) * (2 if matte else 1)
                units = max(units, completed_calls[0] - starting_calls)
                card.frames = _frames(paths, card)
                register_external_frames(candidate, card)
                _image_cost(project, action, provider_name, model, units, f"CLI {route} render")
            accounted = True
            project.save()  # completed paid media remains accounted if processing fails
            token.raise_if_cancelled()
            if process:
                run_pipeline(candidate, card, upto="stabilize", progress=progress, token=token)
            else:
                card.status = "rendered"
            archive = _promote(project, action, candidate, card)
            files.extend(str(frame.source_path) for frame in action.frames if frame.source_path)
            results.append({"id": action.id, "name": action.name, "status": action.status,
                            "frames": len(action.frames), "archive": archive,
                            "sheet_grid": sheet_grid,
                            "clip": str(action.clip.path) if action.clip else None})
        except BaseException as exc:
            if route != "video" and not accounted:
                units = (int(sheet is not None) if route == "sheet" else
                         sum(p.stem.isdigit() for p in extract.glob("*.png")) * (2 if matte else 1))
                units = max(units, completed_calls[0] - starting_calls)
                _image_cost(project, action, provider_name, model, units, f"CLI {route} partial render")
            action.status = previous_status if isinstance(exc, (Cancelled, KeyboardInterrupt)) else "failed"
            action.error = secrets.clean(getattr(exc, "user_message", str(exc)))
            project.save()
            log(f"{action.name}: {action.error}. Candidate media kept at {candidate.project_dir}")
            raise
    return {"route": route, "actions": results, "files": files}


def _clip_edit(operation, project, data, log, progress, token, secrets):
    action = select_actions(project, data.get("actions"), single=True)[0]
    if action.clip is None or not Path(action.clip.path).is_file():
        raise ValueError("This action has no video clip; render or import one first.")
    process = _boolean(data, "process", True)
    candidate, card = _candidate(project, action)
    out = _unique(project, "clips", f"{action.id}-{operation}", ".mp4")
    token.raise_if_cancelled()
    if operation == "refine":
        instruction = _text(data, "instruction", required=True)
        if action.clip.provider != "omni":
            raise ValueError("Refine supports Omni clips only.")
        key, auth = _credentials("google", data.get("auth_mode"), secrets)
        if auth != "api-key":
            raise ValueError("Omni refine requires API key authentication.")
        card.clip = video_route.refine_action(action.clip, instruction, out, api_key=key, log=log)
        record_actual(project, card, None, note="CLI refine")
        project.save()
        score = None
    else:
        threshold = data.get("seam_threshold", 0.08)
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
            raise ValueError("seam_threshold must be between 0 and 1.")
        path, score = video_route.trim_to_loop(action.clip.path, out, seam_threshold=threshold)
        card.clip = copy.deepcopy(action.clip)
        card.clip.path = path
        card.clip.params.update({"trimmed_from": str(action.clip.path), "seam_score": score})
        video_route.write_clip_sidecar(path, video_route.clip_record_payload(card.clip))
    token.raise_if_cancelled()
    if process:
        run_pipeline(candidate, card, upto="stabilize", progress=progress, token=token)
    archive = _promote(project, action, candidate, card)
    return {"action": action.id, "clip": str(out), "seam_score": score, "archive": archive,
            "files": [str(out), *[str(f.source_path) for f in action.frames if f.source_path]]}


def _estimate(project, data):
    route = _route(data)
    entries = []
    for action in select_actions(project, data.get("actions")):
        count = _integer(data, "frames", action.target_frames, 1, 64)
        units = (1 if route == "sheet" else count *
                 (2 if _boolean(data, "matte_pairs") and project.background.mode != "original" else 1))
        entries.append({"id": action.id, "name": action.name,
                        "estimated_usd": estimate_action(project.generation, action) if route == "video" else None,
                        "image_calls": None if route == "video" else units})
    known = [entry["estimated_usd"] for entry in entries if entry["estimated_usd"] is not None]
    return {"route": route, "actions": entries, "known_estimated_usd": round(sum(known), 4),
            "unknown_count": len(entries) - len(known), "files": []}


def bake_working_frames(project, action, frames, *, progress, token, process=True):
    """Make an edited visible frame list durable across later pipeline runs.

    The old stage tree is retained. ``previous_frames`` points into that
    archive so callers can keep an honest undo snapshot after promotion.
    """
    from core.sprite.keying import OVERRIDE_KEYS

    candidate, card = _candidate(project, action)
    extract = stage_dir(candidate, card, "extract")
    extract.mkdir(parents=True)
    card.frames = copy.deepcopy(frames)
    for index, frame in enumerate(card.frames):
        token.raise_if_cancelled()
        if frame.source_path is None or not Path(frame.source_path).is_file():
            raise ValueError(f"Frame {index} has no readable source image.")
        original = Path(frame.source_path)
        out = extract / f"{index + 1:04d}.png"
        with Image.open(original) as image:
            image.convert("RGBA").save(out)
            w, h = image.size
        write_image_sidecar(out, {"route": "sprite_working_frame", "source": str(original),
                                 "action_id": action.id, "frame": index, "baked_rgba": True})
        frame.source_path = out
        frame.frame = frame.sprite_source_size = (0, 0, w, h)
        frame.source_size = (w, h)
        frame.overrides = {key: value for key, value in frame.overrides.items() if key not in OVERRIDE_KEYS}
        frame.overrides["baked_rgba"] = True
    if card.frames:
        register_external_frames(candidate, card)
    else:
        card.status = "draft"
    if process and card.frames:
        run_pipeline(candidate, card, upto="stabilize", progress=progress, token=token)
    previous = copy.deepcopy(action.frames)
    old_stages = stage_dir(project, action, "extract").parent
    archive = _promote(project, action, candidate, card)
    if archive:
        for frame in previous:
            if frame.source_path is not None:
                try:
                    frame.source_path = Path(archive) / Path(frame.source_path).relative_to(old_stages)
                except ValueError:
                    pass
    return {"archive": archive, "previous_frames": previous,
            "files": [str(frame.source_path) for frame in action.frames]}


def _retouch(project, data, log, progress, token, secrets):
    action = select_actions(project, data.get("actions"), single=True)[0]
    if not action.frames:
        raise ValueError("The selected action has no frames to retouch.")
    if not is_stage_current(project, action, "stabilize"):
        raise ValueError("Process this action before retouching so its current key settings are applied.")
    index = _integer(data, "frame", 0, 0, len(action.frames) - 1)
    instruction = _text(data, "instruction", required=True)
    attempts = _integer(data, "attempts", 1, 1, 5)
    process = _boolean(data, "process", True)
    source = action.frames[index].source_path
    if source is None or not Path(source).is_file():
        raise ValueError("The selected frame has no readable image.")
    region = data.get("region")
    if region is not None:
        if (not isinstance(region, list) or len(region) != 4 or
                any(isinstance(v, bool) or not isinstance(v, int) for v in region)):
            raise ValueError("region must be [x, y, width, height] in frame pixels.")
        with Image.open(source) as image:
            width, height = image.size
        x, y, w, h = region
        if x < 0 or y < 0 or w < 1 or h < 1 or x + w > width or y + h > height:
            raise ValueError("region must fit inside the selected frame.")
        region = tuple(region)
    neighbors = data.get("neighbors", True)
    if isinstance(neighbors, bool):
        neighbors = ([i for i in (index - 1, index + 1) if 0 <= i < len(action.frames)]
                     if neighbors else [])
    if (not isinstance(neighbors, list) or any(isinstance(i, bool) or not isinstance(i, int)
            or i < 0 or i >= len(action.frames) or i == index for i in neighbors)):
        raise ValueError("neighbors must be true, false, or a list of other frame indices.")
    if len(neighbors) != len(set(neighbors)):
        raise ValueError("neighbors must not contain duplicates.")
    neighbor_paths = [action.frames[i].source_path for i in neighbors]
    if any(p is None or not Path(p).is_file() for p in neighbor_paths):
        raise ValueError("Every neighbor must have a readable image.")
    provider, name, model = _image_provider(data, secrets)
    completed_calls = _count_image_calls(provider)
    output = _unique(project, "retouch", f"{action.id}-{index:04d}", ".png")
    try:
        new_path = retouch.retouch_frame(provider, source, instruction, output, neighbors=neighbor_paths,
            region=region, model=model, log=log, attempts=attempts, token=token)
    except BaseException:
        _image_cost(project, action, name, model, completed_calls[0], f"CLI retouch frame {index} incomplete")
        project.save()
        raise
    # Core sidecars record the successful attempt, including explicitly requested retries.
    import json
    from core.utils import sidecar_path
    units = 1
    metadata = sidecar_path(new_path)
    if metadata.is_file():
        units = int(json.loads(metadata.read_text(encoding="utf-8")).get("attempt", 1))
    _image_cost(project, action, name, model, max(units, completed_calls[0]), f"CLI retouch frame {index}")
    project.save()
    frames = copy.deepcopy(action.frames)
    frames[index].source_path = new_path
    baked = bake_working_frames(project, action, frames, progress=progress, token=token, process=process)
    return {"action": action.id, "frame": index, "retouch": str(new_path),
            "archive": baked["archive"], "files": [str(new_path), *baked["files"]]}


def execute_generation(operation, project, data, *, log, progress, token):
    """Execute one generation command. Outputs contain metadata and paths only."""
    if not isinstance(project, SpriteProject) or project.project_dir is None:
        raise ValueError("Save or create a Sprite project before this operation.")
    secrets = _Secrets()
    def safe_log(message):
        log(secrets.clean(message))

    def safe_progress(stage, done, total, message):
        progress(stage, done, total, secrets.clean(message))
    with _safe_logging(secrets):
        try:
            token.raise_if_cancelled()
            if operation == "estimate":
                return _estimate(project, data)
            if operation == "render":
                return _render(project, data, safe_log, safe_progress, token, secrets)
            if operation in ("refine", "loop-trim"):
                return _clip_edit(operation, project, data, safe_log, safe_progress, token, secrets)
            if operation == "cards":
                brief = _text(data, "brief", project.brief, required=True)
                genre = _text(data, "genre", project.genre_preset)
                replace = _boolean(data, "replace")
                drafts = action_cards.generate_action_cards(brief, genre, **_chat_settings(data, secrets),
                    plate_color=project.plate_color, character_notes=_text(data, "character_notes"),
                    log=safe_log, token=token)
                cards = [action_cards.draft_to_card(draft) for draft in drafts]
                project.actions = cards if replace else [*project.actions, *cards]
                project.brief, project.genre_preset = brief, genre
                project.save()
                return {"actions": [card.to_dict() for card in cards], "files": []}
            if operation in ("plate", "turnaround"):
                source = _source(project)
                if operation == "plate":
                    source = project.character_source
                    if source is None or not Path(source).is_file():
                        raise ValueError("Import a character image before making a plate.")
                provider, name, model = _image_provider(data, secrets)
                if operation == "plate":
                    out = _unique(project, "character", "plate", ".png")
                    path = plate.make_chroma_plate(provider, source, out, project.plate_color, model=model,
                        aspect_ratio=_text(data, "aspect_ratio", project.generation.aspect_ratio),
                        log=safe_log, token=token)
                    project.plate_path = path
                    _image_cost(project, None, name, model, 1, "CLI chroma plate")
                    project.save()
                    return {"plate": str(path), "files": [str(path)]}
                views = data.get("views", list(turnaround.VIEWS))
                keep = data.get("do_not_change", ["face", "hair", "proportions", "outfit"])
                if not isinstance(views, list) or not views or any(v not in turnaround.VIEWS for v in views):
                    raise ValueError(f"views must be a nonempty list drawn from {turnaround.VIEWS}.")
                if len(set(views)) != len(views):
                    raise ValueError("views must not contain duplicates.")
                if not isinstance(keep, list) or any(not isinstance(v, str) for v in keep):
                    raise ValueError("do_not_change must be a list of strings.")
                out = _unique(project, "character", "turnaround", "")
                produced = {}
                for view in views:
                    paths = turnaround.generate_turnaround(provider, source, out, [view],
                        plate_color=project.plate_color, do_not_change=keep, model=model,
                        aspect_ratio=_text(data, "aspect_ratio", "1:1"), log=safe_log, token=token)
                    produced.update(paths)
                    project.turnaround.update(paths)
                    _image_cost(project, None, name, model, 1, f"CLI turnaround {view}")
                    project.save()
                return {"turnaround": {k: str(v) for k, v in produced.items()},
                        "files": [str(v) for v in produced.values()]}
            if operation == "retouch":
                return _retouch(project, data, safe_log, safe_progress, token, secrets)
            raise ValueError(f"Unknown generation operation: {operation}")
        except Cancelled:
            safe_log(f"Sprite {operation} cancelled.")
            raise
        except Exception as exc:
            message = secrets.clean(getattr(exc, "user_message", str(exc)))
            safe_log(f"Sprite {operation} failed: {message}")
            # Preserve the dispatcher's distinction between invalid requests,
            # operational failures, and unexpected bugs without exposing the
            # provider's original exception chain or credential-bearing text.
            from core.sprite.extract import FFmpegError
            from core.sprite.pipeline import PipelineError
            sanitized: Exception
            if isinstance(exc, SpriteGenerationError):
                sanitized = type(exc)(message, retryable=exc.retryable,
                                      operation_id=exc.operation_id)
            elif isinstance(exc, (PipelineError, FFmpegError)):
                sanitized = type(exc)(message)
            elif isinstance(exc, FileNotFoundError):
                sanitized = FileNotFoundError(message)
            elif isinstance(exc, (ValueError, KeyError)):
                sanitized = ValueError(message)
            elif isinstance(exc, OSError):
                sanitized = OSError(message)
            elif isinstance(exc, RuntimeError):
                sanitized = RuntimeError(message)
            else:
                sanitized = Exception(message)
            raise sanitized from None
