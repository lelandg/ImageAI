"""Discoverable JSON request contracts for the headless Sprite interface."""
from __future__ import annotations

import dataclasses
import math
import re
from typing import get_args, get_origin, get_type_hints, Union


def obj(properties=None, required=(), *, extra=False):
    return {"type": "object", "properties": properties or {},
            "required": list(required), "additionalProperties": extra}


def array(items, **kwargs):
    return {"type": "array", "items": items, **kwargs}


TEXT = {"type": "string"}
NAME = {"type": "string", "minLength": 1}
BOOL = {"type": "boolean"}
NUMBER = {"type": "number"}
POSITIVE = {"type": "integer", "minimum": 1}
INDEX = {"type": "integer", "minimum": 0}
COLOR = {"type": "string", "pattern": r"^#[0-9a-fA-F]{6}$"}
PAIR = array(NUMBER, minItems=2, maxItems=2)
PIVOT = array({"type": "number", "minimum": 0, "maximum": 1}, minItems=2, maxItems=2)
ACTIONS = array(NAME, minItems=1, uniqueItems=True)


def choice(*values):
    return {"type": "string", "enum": list(values)}


def integer_range(minimum, maximum):
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def _type_schema(annotation):
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Union:
        return {"anyOf": [_type_schema(a) for a in args]}
    if origin is list:
        return array(_type_schema(args[0]))
    if origin is tuple:
        return array(_type_schema(args[0]), minItems=len(args), maxItems=len(args))
    return {"type": {str: "string", int: "integer", float: "number",
                     bool: "boolean", type(None): "null"}.get(annotation, "string")}


def settings_schema(cls):
    return obj({f.name: _type_schema(get_type_hints(cls)[f.name])
                for f in dataclasses.fields(cls)})


def schemas():
    from core.sprite.project import (BackgroundSettings, ExtractionSettings,
                                     GenerationSettings, KeySettings,
                                     OutputProfile, StabilizeSettings)
    from core.sprite.exporters.engine_presets import ENGINE_PRESETS, FORMAT_IDS
    from core.sprite.generation.turnaround import VIEWS
    from core.sprite.keying import DESPILL_MODES
    from core.sprite.matting import ML_BACKENDS, REMBG_MODELS
    from core.sprite.pixelart import DITHER_MODES, UPSCALE_METHODS
    from core.sprite.pipeline import STAGES
    from core.sprite.stabilize import ANCHORS, DEJITTER_METHODS

    # The bounds mirror the editable Sprite controls, without importing Qt.
    fps = integer_range(1, 60)
    frame_count = integer_range(1, 64)
    generation = settings_schema(GenerationSettings)
    generation["properties"].update(provider=choice("omni", "veo"), duration_s=integer_range(1, 15),
                                    resolution=choice("720p", "1080p"),
                                    fps=fps, plate_color=COLOR, config_name=NAME,
                                    aspect_ratio={"type": "string", "pattern": r"^[1-9][0-9]*:[1-9][0-9]*$"})
    extraction = settings_schema(ExtractionSettings)
    extraction["properties"].update(mode=choice("every_n", "target_fps", "exact_n"),
                                    every_n=integer_range(1, 120), target_fps=fps, exact_n=integer_range(1, 512),
                                    trim_start_s={"type": "number", "minimum": 0, "maximum": 600},
                                    trim_end_s={"type": "number", "minimum": 0, "maximum": 600},
                                    duplicate_threshold={"type": "number", "minimum": 0, "maximum": 1})
    key = settings_schema(KeySettings)
    key["properties"].update(method=choice("chroma", "ml", "none"),
                             despill=choice(*DESPILL_MODES), ml_backend=choice(*ML_BACKENDS),
                             ml_model=choice(*REMBG_MODELS),
                             key_color={"anyOf": [COLOR, {"type": "null"}]})
    for name in ("tolerance", "softness"):
        key["properties"][name] = {"type": "number", "minimum": 0, "maximum": 1}
    for name in ("choke_px", "feather_px", "despeckle_px"):
        key["properties"][name] = integer_range(0, 16)
    stabilize = settings_schema(StabilizeSettings)
    stabilize["properties"].update(pad_px=integer_range(0, 256), anchor=choice(*ANCHORS),
                                   dejitter_method=choice(*DEJITTER_METHODS))
    profile = settings_schema(OutputProfile)
    profile["properties"].update(name=choice("hd", "pixel"),
                                 cell_size=array(integer_range(1, 4096), minItems=2, maxItems=2),
                                 alpha_threshold={"type": "integer", "minimum": 0, "maximum": 255},
                                 defringe_px=integer_range(0, 16), dither=choice(*DITHER_MODES),
                                 upscale_method=choice(*UPSCALE_METHODS),
                                 locked_palette={"anyOf": [array(COLOR, maxItems=256), {"type": "null"}]},
                                 palette_size={"anyOf": [integer_range(1, 256), {"type": "null"}]})
    profile["required"] = ["name"]
    background = settings_schema(BackgroundSettings)
    background["properties"].update(mode=choice("original", "transparent", "solid"), color=COLOR)
    edit = obj({"name": NAME, "brief": TEXT, "genre_preset": choice("sidescroller", "top_down", "fighting"),
                "plate_color": COLOR, "generation": generation, "extraction": extraction,
                "key": key, "stabilize": stabilize, "background": background,
                "profiles": array(profile, minItems=1)})
    action = obj({"name": NAME, "prompt": TEXT, "duration_s": integer_range(1, 15),
                  "loop": BOOL, "target_frames": frame_count, "fps": fps})
    grid = obj({"columns": integer_range(0, 256), "border_px": integer_range(0, 64),
                "shape_px": integer_range(0, 64), "inner_px": integer_range(0, 64),
                "extrude_px": integer_range(0, 16), "power_of_two": BOOL,
                "scales": array(POSITIVE, minItems=1)})
    exports = {"actions": ACTIONS, "profiles": array(choice("hd", "pixel"), minItems=1, uniqueItems=True),
               "formats": array(choice(*FORMAT_IDS), minItems=1, uniqueItems=True),
               "engine_preset": choice(*ENGINE_PRESETS), "output": NAME, "grid": grid,
               "template": NAME, "pivot": PIVOT,
               "json_layout": choice("hash", "array"),
               "background": background,
               "tags": {"type": "object", "additionalProperties": obj({
                   "direction": choice("forward", "reverse", "pingpong", "pingpong_reverse"),
                   "repeat": INDEX, "fps": POSITIVE, "durations_ms": array(POSITIVE, minItems=1)})}}
    provider = {"provider": choice("google", "openai"), "model": NAME,
                "auth_mode": choice("api-key", "gcloud"),
                "llm_provider": choice("google", "openai", "anthropic"), "llm_model": NAME,
                "llm_auth_mode": choice("api-key", "gcloud")}
    result = {
        "schema": obj({"operation": NAME}), "list": obj(), "inspect": obj(), "validate": obj(),
        "new": obj({"name": NAME, "source": NAME, "settings": edit}, ("name",)),
        "copy": obj({"name": NAME}, ("name",)), "edit": edit,
        "source": obj({"path": NAME, "kind": choice("character", "plate", "turnaround"),
                       "view": choice(*VIEWS)}, ("path",)),
        "action-edit": obj({"operation": choice("add", "update", "remove", "duplicate", "reorder"),
                            "action": NAME, "values": action, "order": ACTIONS}, ("operation",)),
        "frame-edit": obj({"operation": choice("update", "duplicate", "delete", "reorder", "insert"),
                           "action": NAME, "indices": array(INDEX, minItems=1, uniqueItems=True),
                           "order": array(INDEX, uniqueItems=True), "paths": array(NAME, minItems=1),
                           "at": INDEX, "values": obj({"duration_ms": integer_range(1, 10000), "pivot": PIVOT,
                                                       "overrides": obj({"key_color": COLOR,
                                                                         "tolerance": key["properties"]["tolerance"],
                                                                         "softness": key["properties"]["softness"]})})},
                          ("operation", "action")),
        "undo": obj(), "redo": obj(),
        "ml-status": obj(),
        "ml-install": obj({"backends": array(choice(*ML_BACKENDS), minItems=1, uniqueItems=True),
                           "confirm": {"const": True}, "dry_run": BOOL}, ("backends", "confirm")),
        "key-preview": obj({"actions": array(NAME, minItems=1, maxItems=1), "output": NAME,
                            "key_color": COLOR, "tolerance": key["properties"]["tolerance"],
                            "softness": key["properties"]["softness"]}, ("actions",)),
        "config-list": obj(), "config-save": obj({"name": NAME}, ("name",)),
        "config-apply": obj({"name": NAME}, ("name",)),
        "config-delete": obj({"name": NAME, "confirm": {"const": True}}, ("name", "confirm")),
        "delete": obj({"confirm": {"const": True}}, ("confirm",)),
        "purge": obj({"confirm": {"const": True}}, ("confirm",)),
        "import-video": obj({"actions": ACTIONS, "path": NAME, "extraction": extraction}, ("path", "actions")),
        "import-frames": obj({"actions": ACTIONS, "path": NAME, "paths": array(NAME, minItems=1)}, ("actions",)),
        "import-sheet": obj({"actions": ACTIONS, "path": NAME, "columns": POSITIVE, "rows": POSITIVE,
                             "cell": array(POSITIVE, minItems=2, maxItems=2), "margin": INDEX,
                             "spacing": INDEX}, ("actions", "path", "columns", "rows")),
        "process": obj({"actions": ACTIONS, "upto": choice(*STAGES), "force": BOOL,
                        "profiles": array(choice("hd", "pixel"), minItems=1, uniqueItems=True)}),
        "export": obj(exports), "preview": obj(exports),
        "frame-export": obj({"actions": ACTIONS, "profile": choice("hd", "pixel"),
                             "index": INDEX, "output": NAME}, ("actions", "index")),
        "estimate": obj({"actions": ACTIONS, "route": choice("video", "sheet", "edit-chain"),
                         "frames": frame_count, "matte_pairs": BOOL}),
        "cards": obj({**provider, "brief": NAME, "genre": choice("sidescroller", "top_down", "fighting"),
                      "replace": BOOL, "character_notes": TEXT}),
        "render": obj({**provider, "actions": ACTIONS, "route": choice("video", "sheet", "edit-chain"),
                       "frames": frame_count, "pose_instructions": {"anyOf": [array(NAME, minItems=1),
                           {"type": "object", "additionalProperties": array(NAME, minItems=1)}]},
                       "generate_poses": BOOL, "matte_pairs": BOOL, "process": BOOL, "character_notes": TEXT}),
        "plate": obj({**provider, "aspect_ratio": NAME}),
        "turnaround": obj({**provider, "views": array(choice(*VIEWS), minItems=1, uniqueItems=True),
                           "do_not_change": array(NAME), "aspect_ratio": NAME}),
        "refine": obj({**provider, "actions": ACTIONS, "instruction": NAME, "process": BOOL}, ("actions", "instruction")),
        "loop-trim": obj({"actions": ACTIONS, "seam_threshold": {"type": "number", "minimum": 0},
                          "process": BOOL}, ("actions",)),
        "retouch": obj({**provider, "actions": ACTIONS, "frame": INDEX, "instruction": NAME,
                        "region": array(INDEX, minItems=4, maxItems=4),
                        "neighbors": {"anyOf": [BOOL, array(INDEX)]}, "attempts": integer_range(1, 5), "process": BOOL},
                       ("actions", "frame", "instruction")),
    }
    return result


OPERATIONS = ("schema", "list", "new", "inspect", "validate", "copy", "edit", "source",
              "action-edit", "frame-edit", "undo", "redo", "config-list", "config-save",
              "config-apply", "config-delete", "delete", "purge", "cards", "estimate",
              "plate", "turnaround", "render", "refine", "loop-trim", "retouch",
              "import-video", "import-frames", "import-sheet", "process", "export",
              "frame-export", "preview", "key-preview", "ml-status", "ml-install")


def validate(value, schema, path="request"):
    """Validate the JSON Schema subset emitted above without an extra dependency."""
    if "anyOf" in schema:
        for alternative in schema["anyOf"]:
            try:
                validate(value, alternative, path)
                return
            except ValueError:
                pass
        raise ValueError(f"{path}: value does not match any allowed type")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: expected one of {schema['enum']}")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError(f"{path}: expected {schema['const']}")
    kind = schema.get("type")
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
               "string": isinstance(value, str), "boolean": type(value) is bool,
               "integer": type(value) is int, "number": type(value) in (int, float),
               "null": value is None}
    if kind and not matches[kind]:
        raise ValueError(f"{path}: expected {kind}")
    if type(value) in (int, float):
        if not math.isfinite(value):
            raise ValueError(f"{path}: must be finite")
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            raise ValueError(f"{path}: outside allowed range")
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            raise ValueError(f"{path}: must not be blank")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise ValueError(f"{path}: invalid format")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", math.inf):
            raise ValueError(f"{path}: invalid item count")
        if schema.get("uniqueItems") and any(v in value[:i] for i, v in enumerate(value)):
            raise ValueError(f"{path}: duplicate items")
        for i, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{path}[{i}]")
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                raise ValueError(f"{path}.{name}: required")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name not in properties and extra is False:
                raise ValueError(f"{path}.{name}: unknown option")
            validate(item, properties.get(name, extra if isinstance(extra, dict) else {}), f"{path}.{name}")
