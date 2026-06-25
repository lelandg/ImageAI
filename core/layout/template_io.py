"""Layout-template export/import: shareable structure + style, no content."""
import json
from pathlib import Path

from core.layout.models import DocumentSpec
from core.layout import schema


def export_template(doc: DocumentSpec, path: str) -> None:
    data = schema.document_to_dict(doc)
    data["history"] = []  # templates carry no iteration history
    for page in data.get("pages", []):
        for region in page.get("regions", []):
            region["text"] = ""        # strip text content
            region["image_ref"] = None  # strip image content
            # keep: id, kind, shape, bbox, points, z, role, prompt, styles
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def import_template(path: str) -> DocumentSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return schema.document_from_dict(data)
