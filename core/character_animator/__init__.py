"""
Character Animator Puppet Automation package.

This package provides tools for automating the conversion of a single image
into an Adobe Character Animator puppet with proper layer structure, including
auto-generated mouth visemes (14 shapes) and eye blink states.
"""

from .models import (
    PuppetLayer,
    PuppetStructure,
    VisemeSet,
    EyeBlinkSet,
    ExportFormat,
    SegmentationResult,
    FacialRegion,
)
from .constants import (
    LAYER_NAMES,
    VISEME_PROMPTS,
    BODY_PART_ORDER,
    REQUIRED_VISEMES,
    OPTIONAL_EXPRESSIONS,
)
from .availability import (
    SEGMENTATION_AVAILABLE,
    AI_EDITING_AVAILABLE,
    check_all_dependencies,
    get_install_status_message,
    get_missing_dependencies,
)
from .ai_face_editor import AIFaceEditor, EditResult, StyleInfo, get_ai_face_editor
from .face_generator import FaceVariantGenerator

__all__ = [
    # Models
    "PuppetLayer",
    "PuppetStructure",
    "VisemeSet",
    "EyeBlinkSet",
    "ExportFormat",
    "SegmentationResult",
    "FacialRegion",
    # Constants
    "LAYER_NAMES",
    "VISEME_PROMPTS",
    "BODY_PART_ORDER",
    "REQUIRED_VISEMES",
    "OPTIONAL_EXPRESSIONS",
    # Availability
    "SEGMENTATION_AVAILABLE",
    "AI_EDITING_AVAILABLE",
    "check_all_dependencies",
    "get_install_status_message",
    "get_missing_dependencies",
    # AI Face Editing
    "AIFaceEditor",
    "EditResult",
    "StyleInfo",
    "get_ai_face_editor",
    "FaceVariantGenerator",
]
