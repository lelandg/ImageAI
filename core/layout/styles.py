"""Default project style (font roles + palette) seeded by content kind."""
from typing import Dict, List, Literal

from core.layout.models import ProjectStyle, TextStyle


def _role(family: List[str], size: int,
          weight: Literal["regular", "medium", "semibold", "bold", "black"] = "regular",
          color: str = "#111111") -> TextStyle:
    return TextStyle(family=list(family), size_px=size, weight=weight, color=color)


_PALETTE = {"background": "#FFFFFF", "text": "#111111", "accent": "#2C7BE5"}

_KIND_ROLES: Dict[str, Dict[str, TextStyle]] = {
    "children": {
        "title": _role(["Georgia", "DejaVu Serif"], 64, "bold"),
        "narration": _role(["Georgia", "DejaVu Serif"], 36),
    },
    "comic": {
        "logo_title": _role(["Impact", "DejaVu Sans"], 72, "black"),
        "dialogue": _role(["Comic Sans MS", "DejaVu Sans"], 28),
        "sfx": _role(["Impact", "DejaVu Sans"], 48, "black", "#D7263D"),
        "caption": _role(["Arial", "DejaVu Sans"], 24),
    },
    "magazine": {
        "masthead": _role(["Georgia", "DejaVu Serif"], 72, "bold"),
        "headline": _role(["Georgia", "DejaVu Serif"], 48, "bold"),
        "body": _role(["Arial", "DejaVu Sans"], 28),
        "caption": _role(["Arial", "DejaVu Sans"], 22),
        "pull_quote": _role(["Georgia", "DejaVu Serif"], 36, "semibold", "#2C7BE5"),
    },
    "scientific": {
        "title": _role(["Times New Roman", "DejaVu Serif"], 56, "bold"),
        "heading": _role(["Times New Roman", "DejaVu Serif"], 36, "bold"),
        "body": _role(["Times New Roman", "DejaVu Serif"], 28),
        "caption": _role(["Arial", "DejaVu Sans"], 22),
    },
}
# aliases
_KIND_ROLES["comic_strip"] = dict(_KIND_ROLES["comic"])
_KIND_ROLES["newspaper"] = dict(_KIND_ROLES["magazine"])

_DEFAULT_ROLE = {
    "children": "narration", "comic": "dialogue", "comic_strip": "dialogue",
    "magazine": "body", "newspaper": "body", "scientific": "body",
}

_FALLBACK_ROLES = {
    "title": _role(["Arial", "DejaVu Sans"], 56, "bold"),
    "body": _role(["Arial", "DejaVu Sans"], 28),
}


def default_style_for(content_kind: str) -> ProjectStyle:
    roles = _KIND_ROLES.get(content_kind, _FALLBACK_ROLES)
    return ProjectStyle(
        font_roles={name: _role(ts.family, ts.size_px, ts.weight, ts.color)
                    for name, ts in roles.items()},
        palette=dict(_PALETTE),
        default_text_role=_DEFAULT_ROLE.get(content_kind, "body"),
    )
