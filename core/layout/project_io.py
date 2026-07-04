"""Project persistence: .iaiproj.json save/load + legacy .layout.json migration."""
import json
import logging
from pathlib import Path, PureWindowsPath

from core.layout.models import DocumentSpec
from core.layout import schema

logger = logging.getLogger(__name__)


def save_project(doc: DocumentSpec, path: str) -> None:
    data = schema.document_to_dict(doc)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _resolve_image_refs(doc: DocumentSpec, project_dir: Path) -> None:
    """Rewrite image refs that don't resolve on this machine.

    Projects store absolute refs from the machine that generated the images
    (e.g. a WSL ``/home/...`` path opened later from Windows). Relative refs
    resolve against the project file's directory; dead absolute refs fall
    back by filename to the project dir or its ``images/`` subfolder.
    """
    for page in doc.pages:
        for r in page.regions:
            if r.kind != "image" or not r.image_ref:
                continue
            ref = Path(r.image_ref)
            if ref.is_file():
                continue
            # PureWindowsPath splits on both / and \, so a foreign-platform
            # absolute ref still yields its bare filename.
            name = PureWindowsPath(r.image_ref).name
            candidates = [] if ref.is_absolute() else [project_dir / ref]
            candidates += [project_dir / name, project_dir / "images" / name]
            for c in candidates:
                if c.is_file():
                    logger.info("Resolved image ref %s -> %s", r.image_ref, c)
                    r.image_ref = str(c.resolve())
                    break
            else:
                logger.warning("Image ref not found on this machine: %s",
                               r.image_ref)


def load_project(path: str) -> DocumentSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    doc = schema.document_from_dict(data)  # handles both new + legacy shapes
    _resolve_image_refs(doc, Path(path).resolve().parent)
    return doc
