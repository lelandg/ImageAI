"""Style record dataclasses for the Custom Styles feature.

A Style is a hybrid object: an AI-derived structured descriptor plus a
flattened, user-editable prompt_text, plus copied reference images with a
starred exemplar subset. See Plans/2026-07-26-custom-styles-design.md §3.
"""
from dataclasses import dataclass, field
from typing import Dict, List

DESCRIPTOR_KEYS = (
    "summary", "medium", "palette", "lighting", "composition",
    "texture", "line_work", "mood", "negative",
)


@dataclass
class StyleDescriptor:
    summary: str = ""
    medium: str = ""
    palette: str = ""
    lighting: str = ""
    composition: str = ""
    texture: str = ""
    line_work: str = ""
    mood: str = ""
    negative: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {k: getattr(self, k) for k in DESCRIPTOR_KEYS}

    @classmethod
    def from_dict(cls, data) -> "StyleDescriptor":
        data = data or {}
        return cls(**{k: str(data.get(k) or "") for k in DESCRIPTOR_KEYS})


@dataclass
class Style:
    id: str
    name: str
    description: str = ""
    descriptor: StyleDescriptor = field(default_factory=StyleDescriptor)
    prompt_text: str = ""
    placement: str = "suffix"  # "prefix" | "suffix"
    reference_images: List[str] = field(default_factory=list)  # relative to style dir
    exemplars: List[str] = field(default_factory=list)  # subset of reference_images
    source: Dict = field(default_factory=dict)
    version: int = 1
    is_builtin: bool = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "descriptor": self.descriptor.to_dict(),
            "prompt_text": self.prompt_text,
            "placement": self.placement,
            "reference_images": list(self.reference_images),
            "exemplars": list(self.exemplars),
            "source": dict(self.source),
            "version": self.version,
            "is_builtin": self.is_builtin,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Style":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            descriptor=StyleDescriptor.from_dict(data.get("descriptor")),
            prompt_text=data.get("prompt_text", ""),
            placement=data.get("placement", "suffix"),
            reference_images=list(data.get("reference_images") or []),
            exemplars=list(data.get("exemplars") or []),
            source=dict(data.get("source") or {}),
            version=int(data.get("version", 1)),
            is_builtin=bool(data.get("is_builtin", False)),
        )
