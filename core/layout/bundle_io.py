"""Self-contained ``.iaibundle`` export/import (Phase 5a, design spec §8).

A bundle is a zip a recipient can open without the original assets:

    project.iaiproj.json   # the DocumentSpec, with image refs rewritten relative
    bundle.json            # manifest: images map, fonts map, warnings
    images/...             # every referenced image, deduped
    fonts/...              # embedded font files (when resolvable; else by-name)

Font resolution is injected (``font_resolver``) so the module stays decoupled
from ``FontManager`` and fully unit-testable without scanning system fonts.
"""
import copy
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.layout.models import DocumentSpec
from core.layout import schema

logger = logging.getLogger("imageai.layout.bundle")

BUNDLE_SCHEMA_VERSION = "1"
_PROJECT_NAME = "project.iaiproj.json"
_MANIFEST_NAME = "bundle.json"
_IMAGES_DIR = "images"
_FONTS_DIR = "fonts"

# Resolve a priority-ordered family list to a concrete font file (or None).
FontResolver = Callable[[List[str]], Optional[Path]]


@dataclass
class BundleManifest:
    schema_version: str = BUNDLE_SCHEMA_VERSION
    title: str = ""
    images: Dict[str, str] = field(default_factory=dict)  # orig abs path -> bundle rel path
    fonts: Dict[str, str] = field(default_factory=dict)   # family -> bundle rel path | "by-name"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "schema_version": self.schema_version, "title": self.title,
            "images": dict(self.images), "fonts": dict(self.fonts),
            "warnings": list(self.warnings),
        }


def _safe_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "file"
    return stem


def _unique_member(directory: str, filename: str, used: set) -> str:
    stem = Path(filename).stem
    ext = Path(filename).suffix
    candidate = f"{directory}/{_safe_stem(stem)}{ext}"
    n = 1
    while candidate in used:
        candidate = f"{directory}/{_safe_stem(stem)}-{n}{ext}"
        n += 1
    used.add(candidate)
    return candidate


def _collect_font_family_lists(doc: DocumentSpec) -> List[List[str]]:
    """All distinct priority-ordered family lists used by the document."""
    seen = set()
    out: List[List[str]] = []

    def add(families):
        if not families:
            return
        key = tuple(families)
        if key in seen:
            return
        seen.add(key)
        out.append(list(families))

    if doc.style:
        for ts in doc.style.font_roles.values():
            add(ts.family)
    for page in doc.pages:
        for r in page.regions:
            if r.text_style and r.text_style.family:
                add(r.text_style.family)
    return out


def export_bundle(doc: DocumentSpec, path: str,
                  font_resolver: Optional[FontResolver] = None) -> BundleManifest:
    """Write ``doc`` and its assets to a ``.iaibundle`` zip at ``path``.

    Returns the :class:`BundleManifest` (also embedded as ``bundle.json``) so the
    caller can surface warnings (missing images, fonts embedded by name only).
    The live ``doc`` is never mutated — refs are rewritten on a deep copy.
    """
    manifest = BundleManifest(title=doc.title)
    doc2 = copy.deepcopy(doc)
    used_names: set = set()
    # abs source path -> (archive rel path); dedups identical sources.
    image_archive: Dict[str, str] = {}
    font_archive: Dict[str, str] = {}  # abs font source -> archive rel path

    # --- images: copy + rewrite refs to relative bundle paths ---
    for page in doc2.pages:
        for r in page.regions:
            if r.kind != "image" or not r.image_ref:
                continue
            src = Path(r.image_ref)
            if not src.is_file():
                manifest.warnings.append(f"Image not found, left as-is: {r.image_ref}")
                continue
            key = str(src.resolve())
            rel = image_archive.get(key)
            if rel is None:
                rel = _unique_member(_IMAGES_DIR, src.name, used_names)
                image_archive[key] = rel
                manifest.images[str(src)] = rel
            r.image_ref = rel  # forward-slash relative path inside the bundle

    # --- fonts: embed resolved files; record unresolved families by name ---
    for families in _collect_font_family_lists(doc2):
        primary = families[0]
        if primary in manifest.fonts:
            continue
        font_path = font_resolver(families) if font_resolver else None
        if font_path and Path(font_path).is_file():
            key = str(Path(font_path).resolve())
            rel = font_archive.get(key)
            if rel is None:
                rel = _unique_member(_FONTS_DIR, Path(font_path).name, used_names)
                font_archive[key] = rel
            manifest.fonts[primary] = rel
        else:
            manifest.fonts[primary] = "by-name"
            manifest.warnings.append(f"Font embedded by name only (not found): {primary}")

    # --- write the zip ---
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    project_json = json.dumps(schema.document_to_dict(doc2), indent=2)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_PROJECT_NAME, project_json)
        zf.writestr(_MANIFEST_NAME, json.dumps(manifest.to_dict(), indent=2))
        for src_key, rel in image_archive.items():
            zf.write(src_key, rel)
        for src_key, rel in font_archive.items():
            zf.write(src_key, rel)
    logger.info("Exported bundle %s (%d images, %d fonts, %d warnings)",
                out, len(image_archive), len(font_archive), len(manifest.warnings))
    return manifest


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract guarding against zip-slip (members escaping ``dest``)."""
    dest = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if target != dest and dest not in target.parents:
            raise ValueError(f"Unsafe path in bundle: {member.filename!r}")
    zf.extractall(dest)


def import_bundle(path: str, dest_dir: str) -> DocumentSpec:
    """Extract a ``.iaibundle`` into ``dest_dir`` and load its document.

    Relative image refs are rewritten back to absolute paths under ``dest_dir``
    so the returned :class:`DocumentSpec` renders without the original assets.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        _safe_extract(zf, dest)
    proj_path = dest / _PROJECT_NAME
    doc = schema.document_from_dict(json.loads(proj_path.read_text(encoding="utf-8")))
    for page in doc.pages:
        for r in page.regions:
            if r.kind == "image" and r.image_ref and not Path(r.image_ref).is_absolute():
                candidate = (dest / r.image_ref)
                if candidate.exists():
                    r.image_ref = str(candidate.resolve())
    logger.info("Imported bundle %s into %s", path, dest)
    return doc
