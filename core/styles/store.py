"""Persistence for custom styles.

Layout (per Plans/2026-07-26-custom-styles-design.md §3):
    <base_dir>/styles.json      index: {"styles": [record, ...]}
    <base_dir>/<id>/refs/*.jpg  copied, downscaled source images
base_dir defaults to get_user_data_dir()/"styles" — personal artifacts never
live in the repo (unlike data/prompts/custom_presets.json).
"""
import json
import logging
import re
import shutil
from pathlib import Path
from typing import List, Optional

from core.styles.models import Style

logger = logging.getLogger(__name__)

MAX_IMPORT_DIM = 2048
JPEG_QUALITY = 90
EXEMPLAR_DEFAULT_CAP = 3


class StyleStore:
    """CRUD + reference-image management for styles (PresetLoader-shaped)."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            from core.constants import get_user_data_dir
            base_dir = get_user_data_dir() / "styles"
        self.base_dir = Path(base_dir)
        self.index_path = self.base_dir / "styles.json"

    # ---- index I/O -------------------------------------------------------

    def _read_index(self) -> List[dict]:
        if not self.index_path.exists():
            return []
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f).get("styles", [])
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read style index {self.index_path}: {e}")
            return []

    def _write_index(self, records: List[dict]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({"styles": records}, f, indent=2, ensure_ascii=False)

    # ---- CRUD ------------------------------------------------------------

    def list_styles(self) -> List[Style]:
        out = []
        for rec in self._read_index():
            try:
                out.append(Style.from_dict(rec))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed style record: {e}")
        return out

    def get(self, style_id: str) -> Optional[Style]:
        for s in self.list_styles():
            if s.id == style_id:
                return s
        return None

    def get_by_name(self, name: str) -> Optional[Style]:
        """Match by display name or id, case-insensitively."""
        needle = (name or "").strip().lower()
        for s in self.list_styles():
            if s.name.lower() == needle or s.id.lower() == needle:
                return s
        return None

    def new_id(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (name or "style").lower()).strip("-") or "style"
        existing = {s.id for s in self.list_styles()}
        if slug not in existing:
            return slug
        n = 2
        while f"{slug}-{n}" in existing:
            n += 1
        return f"{slug}-{n}"

    def save(self, style: Style) -> None:
        records = self._read_index()
        rec = style.to_dict()
        for i, existing in enumerate(records):
            if existing.get("id") == style.id:
                records[i] = rec
                break
        else:
            records.append(rec)
        self._write_index(records)
        logger.info(f"Saved style '{style.name}' ({style.id})")

    def delete(self, style_id: str) -> bool:
        records = self._read_index()
        kept = [r for r in records if r.get("id") != style_id]
        if len(kept) == len(records):
            return False
        self._write_index(kept)
        d = self.style_dir(style_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        logger.info(f"Deleted style {style_id}")
        return True

    # ---- reference images ------------------------------------------------

    def style_dir(self, style_id: str) -> Path:
        return self.base_dir / style_id

    def add_reference_images(self, style: Style, paths: List[Path]) -> List[str]:
        """Copy images into <style>/refs/ downscaled to MAX_IMPORT_DIM JPEG.

        Appends relative paths to style.reference_images and returns them.
        Caller must save() afterwards. Unreadable files are skipped with a
        logged warning, never fatal.
        """
        from PIL import Image
        refs_dir = self.style_dir(style.id) / "refs"
        refs_dir.mkdir(parents=True, exist_ok=True)
        seq = len(style.reference_images)
        added: List[str] = []
        for src in paths:
            src = Path(src)
            try:
                with Image.open(src) as img:
                    img = img.convert("RGB")
                    img.thumbnail((MAX_IMPORT_DIM, MAX_IMPORT_DIM))
                    seq += 1
                    rel = f"refs/{seq:04d}.jpg"
                    img.save(refs_dir / f"{seq:04d}.jpg", "JPEG", quality=JPEG_QUALITY)
            except (OSError, ValueError) as e:
                logger.warning(f"Skipping unreadable image {src}: {e}")
                continue
            style.reference_images.append(rel)
            added.append(rel)
        logger.info(f"Added {len(added)} reference image(s) to style {style.id}")
        return added

    def remove_reference_image(self, style: Style, rel_path: str) -> None:
        p = self.style_dir(style.id) / rel_path
        if p.exists():
            p.unlink()
        style.reference_images = [r for r in style.reference_images if r != rel_path]
        style.exemplars = [r for r in style.exemplars if r != rel_path]

    def resolve_refs(self, style: Style, exemplars_only: bool = False) -> List[Path]:
        """Absolute paths of (existing) reference images, in stored order."""
        rels = style.exemplars if exemplars_only else style.reference_images
        base = self.style_dir(style.id)
        out = []
        for rel in rels:
            p = base / rel
            if p.exists():
                out.append(p)
            else:
                logger.warning(f"Style {style.id}: missing reference file {rel}")
        return out
