"""Headless Sprite command dispatcher. One JSON request, one JSON result."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import signal
import sys
import uuid
from contextlib import contextmanager, redirect_stdout
from datetime import datetime
from pathlib import Path

from cli.sprite_schema import OPERATIONS, schemas, validate

logger = logging.getLogger(__name__)
READ_ONLY = {"inspect", "validate", "estimate"}
MEDIA = {"import-video", "import-frames", "import-sheet", "process", "export", "frame-export", "preview"}
GENERATION = {"cards", "render", "plate", "turnaround", "refine", "loop-trim", "retouch", "estimate"}
UTILITIES = {"key-preview", "ml-status", "ml-install"}


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot encode {type(value).__name__}")


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False,
                                        default=_json_default, allow_nan=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_request(args):
    path = getattr(args, "sprite_data", None)
    if not path:
        data = {}
    else:
        raw = sys.stdin.read() if path == "-" else Path(path).expanduser().read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Sprite request must be a JSON object")
    # Convenience flags deliberately use the same schema as file/stdin requests.
    for flag, key in (("sprite_name", "name"), ("sprite_source", "source")):
        value = getattr(args, flag, None)
        if value is not None:
            if key in data:
                raise ValueError(f"Specify {key} in either the request or the flag, not both")
            data[key] = value
    validate(data, schemas()[args.sprite])
    return data


def _log(message):
    from core.sprite.generation._common import redact_secrets
    text = redact_secrets(str(message))
    logger.info(text)
    print(text, file=sys.stderr)


def _progress(stage, done, total, message):
    _log(f"[{stage} {done}/{total}] {message}")


@contextmanager
def _cancellation(token):
    previous = signal.getsignal(signal.SIGINT)

    def cancel(_signum, _frame):
        token.cancel()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, cancel)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


@contextmanager
def _project_lock(project):
    """Prevent two CLI writers sharing a project. OS locks release on interruption."""
    # Keep the lock beside the project so deletion can hold it on Windows.
    path = project.project_dir.with_name("." + project.project_dir.name + ".sprite-cli.lock")
    with path.open("a+b") as handle:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError("Another Sprite CLI operation is writing this project") from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError("Another Sprite CLI operation is writing this project") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _manager(args):
    from core.sprite.project import SpriteProjectManager
    root = getattr(args, "sprite_root", None)
    return SpriteProjectManager(Path(root).expanduser().resolve() if root else None)


def _load(args):
    from core.sprite.project import SpriteProject
    target = getattr(args, "sprite_project", None)
    if not target:
        raise ValueError("--sprite-project PATH (or unique project name) is required")
    candidate = Path(target).expanduser()
    if candidate.exists():
        return SpriteProject.load(candidate.resolve())
    matches = [p for p in _manager(args).list_projects()
               if p["name"].casefold() == target.casefold() or p["slug"] == target]
    if len(matches) != 1:
        raise ValueError(f"Project {target!r} matched {len(matches)} projects; use its full path")
    return SpriteProject.load(matches[0]["path"])


def _action(project, selector):
    found = [a for a in project.actions if a.id == selector or a.name == selector]
    if len(found) != 1:
        raise ValueError(f"Action {selector!r} matched {len(found)} actions; use an exact ID")
    return found[0]


def _settings(project, data):
    from core.sprite.project import OutputProfile
    for key, value in data.items():
        if key == "profiles":
            names = [p["name"] for p in value]
            if len(set(names)) != len(names):
                raise ValueError("Profile names must be unique")
            for update in value:
                existing = project.profile(update["name"])
                merged = {**(existing.to_dict() if existing else {}), **update}
                replacement = OutputProfile.from_dict(merged)
                project.profiles = [p for p in project.profiles if p.name != replacement.name] + [replacement]
        elif isinstance(value, dict):
            current = getattr(project, key)
            setattr(project, key, type(current).from_dict({**current.to_dict(), **value}))
        else:
            setattr(project, key, value)
    if "plate_color" in data:
        project.generation.plate_color = project.plate_color
    elif "plate_color" in data.get("generation", {}):
        project.plate_color = project.generation.plate_color


def _source(project, data):
    from PIL import Image
    from core.sprite.source import analyze_source, normalize_source
    from core.sprite.generation.turnaround import VIEWS
    from core.utils import sanitize_filename, write_image_sidecar
    source = Path(data["path"]).expanduser().resolve()
    # Decode before creating any files.
    with Image.open(source) as image:
        image.verify()
    kind = data.get("kind", "character")
    view = data.get("view", "")
    if kind == "turnaround" and view not in VIEWS:
        raise ValueError(f"Turnaround view must be one of {VIEWS}")
    destination = project.project_dir / "source" / f"{kind}_{sanitize_filename(source.stem)}_{uuid.uuid4().hex[:8]}.png"
    if kind == "character":
        normalize_source(source, destination, project.generation.aspect_ratio,
                         preserve_background=project.background.mode == "original")
        project.character_source = destination
        project.plate_path = None
        project.turnaround = {}
    else:
        with Image.open(source) as image:
            image.convert("RGBA").save(destination)
        write_image_sidecar(destination, {"kind": kind, "source": str(source)})
        if kind == "plate":
            project.plate_path = destination
        else:
            project.turnaround[view] = destination
    analysis = analyze_source(destination)
    return {"files": [str(destination)], "analysis": {
        "has_alpha": analysis.has_alpha, "border_color": analysis.border_color}}


def _edit_action(project, data):
    from core.sprite.project import ActionCard
    operation = data["operation"]
    values = data.get("values", {})
    if operation == "add":
        if not values.get("name"):
            raise ValueError("action-edit add requires values.name")
        action = ActionCard.from_dict(values)
        project.actions.append(action)
    elif operation == "reorder":
        order = data.get("order", [])
        resolved = [_action(project, item) for item in order]
        if len(resolved) != len(project.actions) or len({a.id for a in resolved}) != len(resolved):
            raise ValueError("order must contain each action exactly once")
        project.actions = resolved
        return {"actions": [a.id for a in resolved]}
    else:
        action = _action(project, data.get("action"))
        if operation == "remove":
            project.actions.remove(action)
        elif operation == "duplicate":
            duplicate = copy.deepcopy(action)
            duplicate.id = ActionCard.new_id()
            duplicate.name = values.get("name", action.name + " copy")
            # A new card starts in draft; accepted outputs remain with the original.
            duplicate.frames, duplicate.clip, duplicate.status = [], None, "draft"
            for key, value in values.items():
                setattr(duplicate, key, value)
            project.actions.append(duplicate)
            action = duplicate
        else:
            for key, value in values.items():
                setattr(action, key, value)
    return {"action": action.to_dict()}


def _edit_frames(project, data):
    from PIL import Image
    from core.sprite.models import FrameMeta
    from core.utils import sanitize_filename, write_image_sidecar
    action = _action(project, data["action"])
    operation = data["operation"]
    frames = action.frames
    indices = data.get("indices", [])
    if any(i >= len(frames) for i in indices):
        raise ValueError("Frame index is out of range (indices are zero-based)")
    if operation in ("update", "duplicate", "delete") and not indices:
        raise ValueError(f"{operation} requires indices")
    if operation == "reorder":
        order = data.get("order", [])
        if sorted(order) != list(range(len(frames))):
            raise ValueError("order must contain every frame index exactly once")
        action.frames = [frames[i] for i in order]
    elif operation == "delete":
        action.frames = [f for i, f in enumerate(frames) if i not in indices]
    elif operation == "duplicate":
        for i in sorted(indices, reverse=True):
            frame = copy.deepcopy(frames[i])
            frame.name += "_" + uuid.uuid4().hex[:8]
            frames.insert(i + 1, frame)
    elif operation == "insert":
        paths = [Path(p).expanduser().resolve() for p in data.get("paths", [])]
        if not paths:
            raise ValueError("insert requires paths")
        at = data.get("at", len(frames))
        if at > len(frames):
            raise ValueError("at is beyond the end of the frame list")
        decoded = []
        for path in paths:
            with Image.open(path) as image:
                decoded.append((path, image.convert("RGBA")))
        inserted = []
        for path, image in decoded:
            destination = project.project_dir / "source" / f"inserted_{sanitize_filename(path.stem)}_{uuid.uuid4().hex[:8]}.png"
            image.save(destination)
            write_image_sidecar(destination, {"kind": "inserted_frame", "source": str(path)})
            w, h = image.size
            inserted.append(FrameMeta(destination.stem, destination, (0, 0, w, h),
                                      source_size=(w, h), sprite_source_size=(0, 0, w, h)))
        frames[at:at] = inserted
    else:
        values = data.get("values", {})
        if not values:
            raise ValueError("update requires values")
        for i in indices:
            for key, value in values.items():
                if key == "overrides":
                    from core.sprite.keying import OVERRIDE_KEYS
                    retained = {k: v for k, v in frames[i].overrides.items() if k not in OVERRIDE_KEYS}
                    frames[i].overrides = {**retained, **copy.deepcopy(value)}
                else:
                    setattr(frames[i], key, tuple(value) if key == "pivot" else copy.deepcopy(value))
    return {"action": action.id, "frames": [f.to_dict() for f in action.frames]}


def _digest(data):
    normalized = {k: v for k, v in data.items() if k != "modified"}
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def _history_path(project):
    return project.project_dir / "runs" / "cli-history.json"


def _read_history(project):
    path = _history_path(project)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"undo": [], "redo": []}


def _record_edit(project, before, original_digest=None):
    history = _read_history(project)
    if history.get("expected") != (original_digest or _digest(before)):
        history = {"undo": [], "redo": []}
    history["undo"] = (history["undo"] + [before])[-50:]
    history["redo"] = []
    history["expected"] = _digest(project.to_dict())
    _write_json(_history_path(project), history)


def _archive_snapshot(snapshot, action_id, old_stages, archive):
    if not archive:
        return
    for action in snapshot["actions"]:
        if action["id"] != action_id:
            continue
        for frame in action["frames"]:
            if frame["source_path"]:
                try:
                    frame["source_path"] = str(Path(archive) / Path(frame["source_path"]).relative_to(old_stages))
                except ValueError:
                    pass


def _archive_history(history, action_id, old_stages, archive):
    for direction in ("undo", "redo"):
        for snapshot in history[direction]:
            _archive_snapshot(snapshot, action_id, old_stages, archive)


def _undo(project, operation):
    from core.sprite.project import SpriteProject
    history = _read_history(project)
    if history.get("expected") != _digest(project.to_dict()):
        raise ValueError("Project changed since the last CLI edit; old undo history cannot be applied")
    if not history[operation]:
        raise ValueError(f"Nothing to {operation}")
    opposite = "redo" if operation == "undo" else "undo"
    opposite_snapshot = project.to_dict()
    restored = SpriteProject.from_dict(history[operation].pop())
    restored.project_dir = project.project_dir
    # Restore media generations as well as metadata after frame insertion/baking.
    for action in restored.actions:
        current = project.action_by_id(action.id)
        if (current and current.to_dict()["frames"] != action.to_dict()["frames"]
                and all(f.source_path and f.source_path.is_file() for f in action.frames)):
            from cli.commands.sprite_generation import bake_working_frames
            from core.sprite.pipeline import CancelToken, stage_dir
            old_stages = stage_dir(project, current, "extract").parent
            baked = bake_working_frames(restored, action, action.frames,
                                       progress=_progress, token=CancelToken())
            _archive_snapshot(opposite_snapshot, action.id, old_stages, baked["archive"])
            _archive_history(history, action.id, old_stages, baked["archive"])
    history[opposite].append(opposite_snapshot)
    history["expected"] = _digest(restored.to_dict())
    restored.save()
    _write_json(_history_path(project), history)
    return restored


def _inspect(project):
    from core.sprite.pipeline import STAGES, is_stage_current
    return {"project": str(project.project_file()), "document": project.to_dict(),
            "stages": {a.id: {s: is_stage_current(project, a, s) for s in STAGES} for a in project.actions}}


def _execute(args, data, token):
    from core.sprite.configs import NamedConfigStore
    from core.sprite.project import SpriteProject
    operation = args.sprite
    if operation == "schema":
        available = schemas()
        selected = data.get("operation")
        if selected and selected not in available:
            raise ValueError(f"Unknown operation: {selected}")
        return {"schema_version": 1, "operations": available if not selected else {selected: available[selected]},
                "request_format": "--sprite OP --sprite-data FILE (or - for stdin)",
                "exit_codes": {"success": 0, "failure": 1, "invalid_request": 2, "unexpected": 3, "cancelled": 130}}
    if operation == "list":
        return {"projects": _manager(args).list_projects()}
    if operation in {"ml-status", "ml-install"}:
        from cli.commands.sprite_utilities import execute_utility
        return execute_utility(operation, None, data, log=_log, progress=_progress, token=token)
    if operation == "config-list":
        store = NamedConfigStore()
        return {"configurations": {n: store.get(n).to_dict() for n in store.list_names()}}
    if operation == "config-delete":
        NamedConfigStore().delete(data["name"])
        return {"deleted": data["name"]}
    if operation == "new":
        # Validate full settings/source before allocating a project directory.
        candidate = SpriteProject(data["name"])
        _settings(candidate, data.get("settings", {}))
        if data.get("source"):
            from PIL import Image
            with Image.open(Path(data["source"]).expanduser()) as image:
                image.verify()
        created = _manager(args).create_project(candidate.name)
        candidate.project_dir = created.project_dir
        if data.get("source"):
            _source(candidate, {"path": data["source"]})
        candidate.save()
        return _inspect(candidate)
    project = _load(args)
    if operation in READ_ONLY:
        if operation == "estimate":
            from cli.commands.sprite_generation import execute_generation
            return execute_generation(operation, project, data, log=_log, progress=_progress, token=token)
        result = _inspect(project)
        if operation == "validate":
            missing = []
            for path in [project.character_source, project.plate_path, *project.turnaround.values(),
                         *(a.clip.path for a in project.actions if a.clip),
                         *(f.source_path for a in project.actions for f in a.frames)]:
                if path and not path.is_file():
                    missing.append(str(path))
            result["missing_media"] = missing
            if missing:
                raise ValueError("Project references missing media: " + ", ".join(missing))
        return result
    with _project_lock(project):
        # Load again under the lock so a preceding CLI writer cannot be lost.
        project = SpriteProject.load(project.project_file())
        if operation == "delete":
            if not _manager(args).delete_project(project):
                raise RuntimeError("Project could not be deleted")
            return {"deleted": str(project.project_dir)}
        before = project.to_dict()
        before_digest = _digest(before)
        original_bytes = project.project_file().read_bytes()
        if operation == "copy":
            from core.sprite.project_copy import copy_project
            project = copy_project(project, data["name"], _manager(args))
            return _inspect(project)
        if operation in ("undo", "redo"):
            return _inspect(_undo(project, operation))
        if operation == "edit":
            _settings(project, data)
            result = {}
        elif operation == "source":
            result = _source(project, data)
        elif operation == "action-edit":
            result = _edit_action(project, data)
        elif operation == "frame-edit":
            result = _edit_frames(project, data)
            action = _action(project, data["action"])
            if (data["operation"] in {"insert", "delete", "duplicate", "reorder"}
                    and all(f.source_path and f.source_path.is_file() for f in action.frames)):
                if project.project_file().read_bytes() != original_bytes:
                    raise ValueError("Project changed in another application; reload before retrying")
                from cli.commands.sprite_generation import bake_working_frames
                from core.sprite.pipeline import stage_dir
                old_stages = stage_dir(project, action, "extract").parent
                baked = bake_working_frames(project, action, action.frames,
                                           progress=_progress, token=token)
                _archive_snapshot(before, action.id, old_stages, baked["archive"])
                history = _read_history(project)
                _archive_history(history, action.id, old_stages, baked["archive"])
                _write_json(_history_path(project), history)
                original_bytes = project.project_file().read_bytes()
                result["frames"] = [f.to_dict() for f in action.frames]
        elif operation == "config-apply":
            project.generation = NamedConfigStore().get(data["name"])
            project.plate_color = project.generation.plate_color
            result = {}
        elif operation == "config-save":
            NamedConfigStore().save(data["name"], project.generation)
            return {"configuration": data["name"]}
        elif operation == "purge":
            result = {"removed_files": project.purge_intermediates()}
        elif operation in MEDIA:
            from cli.commands.sprite_media import execute_media
            result = execute_media(operation, project, data, log=_log, progress=_progress, token=token)
        elif operation in GENERATION:
            from cli.commands.sprite_generation import execute_generation
            result = execute_generation(operation, project, data, log=_log, progress=_progress, token=token)
        elif operation in UTILITIES:
            from cli.commands.sprite_utilities import execute_utility
            result = execute_utility(operation, project, data, log=_log, progress=_progress, token=token)
        else:
            raise ValueError(f"Unsupported operation: {operation}")
        token.raise_if_cancelled()
        if operation in {"edit", "source", "action-edit", "frame-edit", "config-apply"}:
            if project.project_file().read_bytes() != original_bytes:
                raise ValueError("Project changed in another application; reload it before retrying this edit")
            project.save()
            _record_edit(project, before, before_digest)
        else:
            project.save()
            if operation in {"export", "preview", "frame-export"}:
                history = _read_history(project)
                if history.get("expected") == before_digest:
                    history["expected"] = _digest(project.to_dict())
                    _write_json(_history_path(project), history)
        result["project"] = str(project.project_file())
        result["modified"] = project.modified
        record = project.project_dir / "runs" / f"{operation}-{datetime.now():%Y%m%d_%H%M%S}-{uuid.uuid4().hex[:8]}.json"
        _write_json(record, {"operation": operation, "result": result})
        result["run_record"] = str(record)
        return result


def run_sprite_cmd(args):
    from core.sprite.generation._common import redact_secrets
    from core.sprite.generation.errors import SpriteGenerationError
    from core.sprite.extract import FFmpegError
    from core.sprite.pipeline import CancelToken, Cancelled, PipelineError
    token = CancelToken()
    result = {"status": "ok", "operation": args.sprite}
    exit_code = 0
    try:
        # Provider libraries sometimes print. Keep stdout exclusively for the final result.
        with redirect_stdout(sys.stderr), _cancellation(token):
            data = _read_request(args)
            result.update(_execute(args, data, token))
    except (KeyboardInterrupt, Cancelled):
        token.cancel()
        logger.warning("Sprite operation cancelled")
        result.update(status="cancelled", error="Sprite operation cancelled")
        exit_code = 130
    except (ValueError, KeyError, FileNotFoundError) as exc:
        message = redact_secrets(str(exc))
        logger.error("Invalid Sprite request: %s", message)
        result.update(status="error", error=message)
        exit_code = 2
    except (SpriteGenerationError, PipelineError, FFmpegError, OSError, RuntimeError) as exc:
        message = redact_secrets(getattr(exc, "user_message", str(exc)))
        logger.error("Sprite operation failed: %s", message)
        result.update(status="error", error=message)
        exit_code = 1
    except Exception as exc:
        message = redact_secrets(str(exc))
        logger.error("Unexpected Sprite failure (%s): %s", type(exc).__name__, message)
        result.update(status="error", error=message)
        exit_code = 3
    result["exit_code"] = exit_code
    output = json.dumps(result, ensure_ascii=False, default=_json_default, allow_nan=False)
    print(output, file=sys.stdout if getattr(args, "json", False) else sys.stderr)
    return exit_code


def add_sprite_arguments(parser):
    group = parser.add_argument_group("Sprite workflow (headless; JSON requests)")
    group.add_argument("--sprite", choices=OPERATIONS, help="Sprite operation; use schema to discover request fields")
    group.add_argument("--sprite-project", metavar="PATH_OR_NAME", help="Sprite project file, folder, or unique library name")
    group.add_argument("--sprite-data", metavar="FILE", help="JSON options file; - reads stdin")
    group.add_argument("--sprite-root", metavar="DIRECTORY", help="Project library override (default: configured Images storage)")
    group.add_argument("--sprite-name", metavar="NAME", help="Name for new/copy/config operations")
    group.add_argument("--sprite-source", metavar="IMAGE", help="Source image for a new project")
