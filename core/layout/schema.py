"""Serialization, normalization, and validation for layout documents."""
from dataclasses import asdict, replace, fields
from typing import Dict, List, Tuple

from core.layout.models import (
    Region, PageSpec, DocumentSpec, PageSize, TextStyle, ImageStyle, Snapshot, ProjectStyle,
    migrate_legacy_blocks, TextBlock, ImageBlock, PathSegment,
    Overlay, OverlayStyle,
)


def _filtered(cls, d: Dict) -> Dict:
    """Keep only keys that are real fields of dataclass ``cls``.

    Lets a hand-edited or forward-version file carrying extra/renamed keys load
    instead of crashing with ``TypeError: unexpected keyword argument``.
    """
    valid = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in valid}

REGION_JSON_SCHEMA: Dict = {
    "type": "object",
    "required": ["id", "kind"],
    "properties": {
        "id": {"type": "string"},
        "kind": {"enum": ["image", "text"]},
        "shape": {"enum": ["rect", "polygon", "path"]},
        "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
        "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "segments": {"type": "array", "items": {
            "type": "object",
            "required": ["type", "pts"],
            "properties": {
                "type": {"enum": ["move", "line", "quad", "cubic", "close"]},
                "pts": {"type": "array", "items": {
                    "type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}},
            },
        }},
        "bleed": {"type": "boolean"},
        "z": {"type": "integer"},
        "text": {"type": "string"},
        "role": {"type": "string"},
        "image_ref": {"type": ["string", "null"]},
        "prompt": {"type": "string"},
    },
}


OVERLAY_JSON_SCHEMA: Dict = {
    "type": "object",
    "required": ["id", "kind", "text", "anchor"],
    "properties": {
        "id": {"type": "string"},
        "kind": {"enum": ["speech", "thought", "caption", "sfx"]},
        "text": {"type": "string"},
        "anchor": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
        "anchor_mode": {"enum": ["center", "topleft"]},
        "tail_target": {"oneOf": [
            {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
            {"type": "null"},
        ]},
        "z": {"type": "integer"},
        "role": {"type": "string"},
        "text_style": {"type": ["object", "null"]},
        "style": {"type": "object"},
    },
}


def _style_to_dict(style):
    return asdict(style) if style is not None else None


def region_to_dict(r: Region) -> Dict:
    return {
        "id": r.id, "kind": r.kind, "shape": r.shape,
        "bbox": list(r.bbox), "points": [list(p) for p in r.points],
        "z": r.z, "name": r.name, "text": r.text, "role": r.role,
        "image_ref": r.image_ref, "prompt": r.prompt, "gen_settings": dict(r.gen_settings),
        "segments": [{"type": s.type, "pts": [list(p) for p in s.pts]} for s in r.segments],
        "bleed": r.bleed,
        "text_style": _style_to_dict(r.text_style),
        "image_style": _style_to_dict(r.image_style),
    }


def region_from_dict(d: Dict) -> Region:
    ts = d.get("text_style")
    is_ = d.get("image_style")
    return Region(
        id=d.get("id", ""), kind=d.get("kind", "image"), shape=d.get("shape", "rect"),
        bbox=tuple(d.get("bbox", (0, 0, 100, 100))),
        points=[tuple(p) for p in d.get("points", [])],
        z=int(d.get("z", 0)), name=d.get("name", ""),
        text=d.get("text", ""), role=d.get("role", ""),
        image_ref=d.get("image_ref"), prompt=d.get("prompt", ""),
        gen_settings=dict(d.get("gen_settings", {})),
        segments=[PathSegment(type=s.get("type", "line"),
                              pts=[tuple(p) for p in s.get("pts", [])])
                  for s in d.get("segments", [])],
        bleed=bool(d.get("bleed", False)),
        text_style=TextStyle(**_filtered(TextStyle, ts)) if ts else None,
        image_style=ImageStyle(**_filtered(ImageStyle, is_)) if is_ else None,
    )


def _overlay_style_to_dict(s: OverlayStyle) -> Dict:
    return {
        "fill": s.fill, "stroke_px": s.stroke_px, "stroke_color": s.stroke_color,
        "padding_px": s.padding_px, "radius_px": s.radius_px, "max_width_px": s.max_width_px,
    }


def _overlay_style_from_dict(d: Dict) -> OverlayStyle:
    return OverlayStyle(**_filtered(OverlayStyle, d)) if d else OverlayStyle()


def overlay_to_dict(ov: Overlay) -> Dict:
    d: Dict = {
        "id": ov.id, "kind": ov.kind, "text": ov.text,
        "anchor": [ov.anchor[0], ov.anchor[1]],
        "anchor_mode": ov.anchor_mode,
        "tail_target": (None if ov.tail_target is None
                        else [ov.tail_target[0], ov.tail_target[1]]),
        "z": ov.z, "role": ov.role, "rotation": ov.rotation,
        "text_style": _style_to_dict(ov.text_style),
        "style": _overlay_style_to_dict(ov.style),
    }
    return d


def overlay_from_dict(d: Dict) -> Overlay:
    anchor_raw = d["anchor"]
    tt = d.get("tail_target")
    ts = d.get("text_style")
    return Overlay(
        id=d["id"], kind=d["kind"], text=d.get("text", ""),
        anchor=(float(anchor_raw[0]), float(anchor_raw[1])),
        anchor_mode=d.get("anchor_mode", "center"),
        tail_target=(None if tt is None else (float(tt[0]), float(tt[1]))),
        z=int(d.get("z", 0)), role=d.get("role", ""),
        text_style=TextStyle(**_filtered(TextStyle, ts)) if ts else None,
        style=_overlay_style_from_dict(d.get("style") or {}),
        rotation=float(d.get("rotation", 0.0) or 0.0),
    )


def snapshot_to_dict(s: "Snapshot") -> Dict:
    return {
        "id": s.id, "parent_id": s.parent_id, "timestamp": s.timestamp,
        "prompt": s.prompt, "document": s.document, "thumbnail": s.thumbnail,
    }


def snapshot_from_dict(d: Dict) -> "Snapshot":
    return Snapshot(
        id=d["id"], parent_id=d.get("parent_id"), timestamp=d.get("timestamp", ""),
        prompt=d.get("prompt", ""), document=d.get("document", {}),
        thumbnail=d.get("thumbnail"),
    )


def project_style_to_dict(s: "ProjectStyle") -> Dict:
    return {
        "font_roles": {name: asdict(ts) for name, ts in s.font_roles.items()},
        "palette": dict(s.palette),
        "default_text_role": s.default_text_role,
    }


def project_style_from_dict(d: Dict) -> "ProjectStyle":
    return ProjectStyle(
        font_roles={name: TextStyle(**_filtered(TextStyle, ts))
                    for name, ts in d.get("font_roles", {}).items()},
        palette=dict(d.get("palette", {})),
        default_text_role=d.get("default_text_role", "body"),
    )


def _page_size_from_dict(d):
    return PageSize(**_filtered(PageSize, d)) if d else None


def page_to_dict(p: PageSpec) -> Dict:
    return {
        "page_size_px": list(p.page_size_px),
        "page_size": asdict(p.page_size) if p.page_size else None,
        "margin_px": p.margin_px, "bleed_px": p.bleed_px, "background": p.background,
        "regions": [region_to_dict(r) for r in p.regions],
        "overlays": [overlay_to_dict(o) for o in p.overlays],
        "variables": dict(p.variables),
    }


def page_from_dict(d: Dict) -> PageSpec:
    if "regions" in d:
        regions = [region_from_dict(r) for r in d["regions"]]
    else:  # legacy: migrate blocks -> regions
        legacy = []
        for b in d.get("blocks", []):
            rect = tuple(b.get("rect", (0, 0, 100, 100)))
            if b.get("type") == "image":
                legacy.append(ImageBlock(id=b.get("id", ""), rect=rect,
                                         image_path=b.get("image_path")))
            else:
                legacy.append(TextBlock(id=b.get("id", ""), rect=rect,
                                        text=b.get("text", "")))
        regions = migrate_legacy_blocks(legacy)
    return PageSpec(
        page_size_px=tuple(d.get("page_size_px", (1000, 1000))),
        page_size=_page_size_from_dict(d.get("page_size")),
        margin_px=d.get("margin_px", 64), bleed_px=d.get("bleed_px", 0),
        background=d.get("background"), regions=regions,
        overlays=[overlay_from_dict(o) for o in d.get("overlays", [])],
        variables=dict(d.get("variables", {})),
    )


def document_to_dict(doc: DocumentSpec) -> Dict:
    return {
        "schema_version": doc.schema_version, "title": doc.title, "author": doc.author,
        "content_kind": doc.content_kind, "theme": dict(doc.theme),
        "metadata": dict(doc.metadata), "pages": [page_to_dict(p) for p in doc.pages],
        "history": [snapshot_to_dict(s) for s in doc.history],
        "style": project_style_to_dict(doc.style) if doc.style else None,
        "render_on_top": doc.render_on_top,
    }


def document_from_dict(d: Dict) -> DocumentSpec:
    return DocumentSpec(
        title=d.get("title", "Untitled"), author=d.get("author"),
        pages=[page_from_dict(p) for p in d.get("pages", [])],
        theme=dict(d.get("theme", {})), metadata=dict(d.get("metadata", {})),
        content_kind=d.get("content_kind", "custom"),
        schema_version=d.get("schema_version", "2.0"),
        history=[snapshot_from_dict(s) for s in d.get("history", [])],
        style=project_style_from_dict(d["style"]) if d.get("style") else None,
        render_on_top=d.get("render_on_top"),
    )


def normalize_region(r: Region, page_px: Tuple[int, int]) -> Region:
    pw, ph = page_px
    if r.shape == "polygon" and r.points:
        xs = [p[0] for p in r.points]
        ys = [p[1] for p in r.points]
        bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    elif r.shape == "path" and r.segments:
        from core.layout.geometry import segments_bbox
        bbox = tuple(round(v) for v in segments_bbox(r.segments))
    else:
        bbox = r.bbox
    x, y, w, h = bbox
    x = max(0, min(x, pw - 1))
    y = max(0, min(y, ph - 1))
    w = max(1, min(w, pw - x))
    h = max(1, min(h, ph - y))
    return replace(r, bbox=(x, y, w, h))


def validate_document(doc: DocumentSpec) -> List[str]:
    issues: List[str] = []
    if not doc.pages:
        issues.append("Document has no pages.")
    for pi, p in enumerate(doc.pages):
        ids = [r.id for r in p.regions]
        if len(ids) != len(set(ids)):
            issues.append(f"Page {pi}: duplicate region ids.")
    return issues
