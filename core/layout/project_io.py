"""Project persistence: .iaiproj.json save/load + legacy .layout.json migration."""
import json
from pathlib import Path

from core.layout.models import DocumentSpec
from core.layout import schema


def save_project(doc: DocumentSpec, path: str) -> None:
    data = schema.document_to_dict(doc)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_project(path: str) -> DocumentSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return schema.document_from_dict(data)  # handles both new + legacy shapes
