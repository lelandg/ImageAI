"""
Data models for Character Animator puppet generation.

Defines the core data structures used throughout the puppet automation pipeline:
- PuppetLayer: Individual layers with images and properties
- PuppetStructure: Complete puppet hierarchy
- VisemeSet: 14 mouth shapes for lip-sync
- EyeBlinkSet: Eye blink states
- ExportFormat: Output format options
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from PIL import Image
import numpy as np


class ExportFormat(Enum):
    """Supported export formats for Character Animator puppets."""
    PSD = "psd"  # Photoshop format - most common, best for photorealistic
    SVG = "svg"  # Vector format - good for cartoons, groups map to layers
    AI = "ai"    # Adobe Illustrator - vector-based, preserves layers


@dataclass
class FacialRegion:
    """Represents a facial region with bounding box and landmarks."""
    name: str
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    landmarks: Optional[np.ndarray] = None  # MediaPipe landmarks
    mask: Optional[np.ndarray] = None  # Binary mask for the region

    @property
    def center(self) -> Tuple[int, int]:
        """Get the center point of the bounding box."""
        x, y, w, h = self.bbox
        return (x + w // 2, y + h // 2)

    @property
    def area(self) -> int:
        """Get the area of the bounding box."""
        return self.bbox[2] * self.bbox[3]


@dataclass
class PuppetLayer:
    """
    Represents a single layer in the puppet structure.

    Attributes:
        name: Layer name following Adobe Character Animator naming conventions
        image: PIL Image for this layer (RGBA)
        children: Child layers (for groups)
        visible: Whether layer is visible by default
        opacity: Layer opacity (0.0 - 1.0)
        blend_mode: Photoshop blend mode
        position: Position offset from parent (x, y)
        warp_independent: Whether this layer has + prefix (warp independently)
        depth_order: Z-order from depth estimation (higher = closer)
    """
    name: str
    image: Optional[Image.Image] = None
    children: List["PuppetLayer"] = field(default_factory=list)
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = "normal"
    position: Tuple[int, int] = (0, 0)
    warp_independent: bool = False
    depth_order: int = 0

    @property
    def display_name(self) -> str:
        """Get the display name with warp prefix if applicable."""
        if self.warp_independent:
            return f"+{self.name}"
        return self.name

    def is_group(self) -> bool:
        """Check if this layer is a group (has children)."""
        return len(self.children) > 0

    def add_child(self, layer: "PuppetLayer") -> None:
        """Add a child layer."""
        self.children.append(layer)

    def find_layer(self, name: str) -> Optional["PuppetLayer"]:
        """Recursively find a layer by name."""
        if self.name == name:
            return self
        for child in self.children:
            found = child.find_layer(name)
            if found:
                return found
        return None


@dataclass
class VisemeSet:
    """
    Collection of 14 mouth shapes for Character Animator lip-sync.

    The 14 visemes map to phoneme groups:
    - Neutral: Resting mouth
    - Ah: Open mouth (A, AI, AU)
    - D: Tongue behind teeth (D, T, N, TH)
    - Ee: Wide smile (E, EE)
    - F: Lower lip under teeth (F, V)
    - L: Tongue up (L)
    - M: Closed lips (M, B, P)
    - Oh: Rounded open (O, OO)
    - R: Slightly rounded (R)
    - S: Teeth together (S, Z, SH, CH)
    - Uh: Slightly open (U, UH)
    - W-Oo: Pursed lips (W, OO, Q)
    - Smile: Camera-driven expression
    - Surprised: Camera-driven expression
    """
    neutral: Optional[Image.Image] = None
    ah: Optional[Image.Image] = None
    d: Optional[Image.Image] = None
    ee: Optional[Image.Image] = None
    f: Optional[Image.Image] = None
    l: Optional[Image.Image] = None
    m: Optional[Image.Image] = None
    oh: Optional[Image.Image] = None
    r: Optional[Image.Image] = None
    s: Optional[Image.Image] = None
    uh: Optional[Image.Image] = None
    w_oo: Optional[Image.Image] = None
    smile: Optional[Image.Image] = None
    surprised: Optional[Image.Image] = None

    # Bounding box for mouth region (x, y, width, height)
    # Used for cropping viseme layers to just the mouth area
    mouth_bbox: Optional[Tuple[int, int, int, int]] = None

    def to_dict(self) -> Dict[str, Optional[Image.Image]]:
        """Convert to dictionary with standard viseme names."""
        return {
            "Neutral": self.neutral,
            "Ah": self.ah,
            "D": self.d,
            "Ee": self.ee,
            "F": self.f,
            "L": self.l,
            "M": self.m,
            "Oh": self.oh,
            "R": self.r,
            "S": self.s,
            "Uh": self.uh,
            "W-Oo": self.w_oo,
            "Smile": self.smile,
            "Surprised": self.surprised,
        }

    def get_missing(self) -> List[str]:
        """Get list of missing visemes."""
        missing = []
        viseme_dict = self.to_dict()
        for name, img in viseme_dict.items():
            if img is None:
                missing.append(name)
        return missing

    def is_complete(self) -> bool:
        """Check if all visemes are generated."""
        return len(self.get_missing()) == 0


@dataclass
class EyeBlinkSet:
    """Collection of eye blink states for Character Animator."""
    left_open: Optional[Image.Image] = None
    left_blink: Optional[Image.Image] = None
    right_open: Optional[Image.Image] = None
    right_blink: Optional[Image.Image] = None

    # Bounding boxes for eye regions (x, y, width, height)
    # Used for cropping eye layers to just the eye areas
    left_eye_bbox: Optional[Tuple[int, int, int, int]] = None
    right_eye_bbox: Optional[Tuple[int, int, int, int]] = None

    def is_complete(self) -> bool:
        """Check if all blink states are generated."""
        return all([
            self.left_open is not None,
            self.left_blink is not None,
            self.right_open is not None,
            self.right_blink is not None,
        ])


@dataclass
class SegmentationResult:
    """
    Results from body part segmentation.

    Contains masks and bounding boxes for each detected body part,
    plus depth information for z-ordering.
    """
    original_image: Image.Image

    # Body parts
    head_mask: Optional[np.ndarray] = None
    head_bbox: Optional[Tuple[int, int, int, int]] = None

    torso_mask: Optional[np.ndarray] = None
    torso_bbox: Optional[Tuple[int, int, int, int]] = None

    left_arm_mask: Optional[np.ndarray] = None
    left_arm_bbox: Optional[Tuple[int, int, int, int]] = None

    right_arm_mask: Optional[np.ndarray] = None
    right_arm_bbox: Optional[Tuple[int, int, int, int]] = None

    # Facial regions (extracted from head)
    left_eye_region: Optional[FacialRegion] = None
    right_eye_region: Optional[FacialRegion] = None
    mouth_region: Optional[FacialRegion] = None
    left_eyebrow_region: Optional[FacialRegion] = None
    right_eyebrow_region: Optional[FacialRegion] = None

    # Depth map for z-ordering
    depth_map: Optional[np.ndarray] = None

    # Pose landmarks from MediaPipe
    pose_landmarks: Optional[np.ndarray] = None

    # Face mesh landmarks (478 points)
    face_landmarks: Optional[np.ndarray] = None

    def get_body_parts(self) -> Dict[str, Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]]:
        """Get all body parts as a dictionary."""
        return {
            "head": (self.head_mask, self.head_bbox),
            "torso": (self.torso_mask, self.torso_bbox),
            "left_arm": (self.left_arm_mask, self.left_arm_bbox),
            "right_arm": (self.right_arm_mask, self.right_arm_bbox),
        }

    def get_facial_regions(self) -> Dict[str, Optional[FacialRegion]]:
        """Get all facial regions as a dictionary."""
        return {
            "left_eye": self.left_eye_region,
            "right_eye": self.right_eye_region,
            "mouth": self.mouth_region,
            "left_eyebrow": self.left_eyebrow_region,
            "right_eyebrow": self.right_eyebrow_region,
        }


@dataclass
class PuppetStructure:
    """
    Complete puppet structure ready for export.

    Represents the full hierarchy of a Character Animator puppet:
    +[CharacterName]
    ├── Body
    │   ├── Torso
    │   ├── Left Arm
    │   ├── Right Arm
    │   └── [Legs if full body]
    └── Head
        ├── +Left Eyebrow
        ├── +Right Eyebrow
        ├── Left Eye (group)
        │   ├── Left Pupil Range
        │   └── +Left Pupil
        ├── Right Eye (group)
        │   ├── Right Pupil Range
        │   └── +Right Pupil
        ├── Left Blink
        ├── Right Blink
        └── Mouth (group)
            ├── Neutral
            ├── Ah, D, Ee, F, L, M, Oh, R, S, Uh, W-Oo
            ├── Smile
            └── Surprised
    """
    name: str
    root_layer: PuppetLayer
    visemes: VisemeSet
    eye_blinks: EyeBlinkSet
    segmentation: Optional[SegmentationResult] = None

    # Canvas dimensions
    width: int = 0
    height: int = 0

    # Export settings
    export_format: ExportFormat = ExportFormat.PSD

    def get_head_layer(self) -> Optional[PuppetLayer]:
        """Get the Head layer."""
        return self.root_layer.find_layer("Head")

    def get_body_layer(self) -> Optional[PuppetLayer]:
        """Get the Body layer."""
        return self.root_layer.find_layer("Body")

    def get_mouth_group(self) -> Optional[PuppetLayer]:
        """Get the Mouth group layer."""
        head = self.get_head_layer()
        if head:
            return head.find_layer("Mouth")
        return None

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate that the puppet has all required layers.

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check root layer
        if not self.root_layer:
            issues.append("Missing root layer")
            return False, issues

        # Check Head
        head = self.get_head_layer()
        if not head:
            issues.append("Missing Head layer")

        # Check Body
        body = self.get_body_layer()
        if not body:
            issues.append("Missing Body layer")

        # Check Mouth group
        mouth = self.get_mouth_group()
        if not mouth:
            issues.append("Missing Mouth group")

        # Check visemes
        missing_visemes = self.visemes.get_missing()
        if missing_visemes:
            issues.append(f"Missing visemes: {', '.join(missing_visemes)}")

        # Check eye blinks
        if not self.eye_blinks.is_complete():
            issues.append("Incomplete eye blink states")

        return len(issues) == 0, issues

    @classmethod
    def create_empty(cls, name: str, width: int, height: int) -> "PuppetStructure":
        """Create an empty puppet structure with standard hierarchy."""
        root = PuppetLayer(name=name, warp_independent=True)

        # Create Body group
        body = PuppetLayer(name="Body")
        body.add_child(PuppetLayer(name="Torso"))
        body.add_child(PuppetLayer(name="Left Arm"))
        body.add_child(PuppetLayer(name="Right Arm"))
        root.add_child(body)

        # Create Head group
        head = PuppetLayer(name="Head")

        # Eyebrows
        head.add_child(PuppetLayer(name="Left Eyebrow", warp_independent=True))
        head.add_child(PuppetLayer(name="Right Eyebrow", warp_independent=True))

        # Left Eye group
        left_eye = PuppetLayer(name="Left Eye")
        left_eye.add_child(PuppetLayer(name="Left Pupil Range"))
        left_eye.add_child(PuppetLayer(name="Left Pupil", warp_independent=True))
        head.add_child(left_eye)

        # Right Eye group
        right_eye = PuppetLayer(name="Right Eye")
        right_eye.add_child(PuppetLayer(name="Right Pupil Range"))
        right_eye.add_child(PuppetLayer(name="Right Pupil", warp_independent=True))
        head.add_child(right_eye)

        # Blink layers
        head.add_child(PuppetLayer(name="Left Blink"))
        head.add_child(PuppetLayer(name="Right Blink"))

        # Mouth group - visemes will be added by populate_from_visemes()
        # Don't create placeholder children here to avoid duplicates
        mouth = PuppetLayer(name="Mouth")
        head.add_child(mouth)

        root.add_child(head)

        return cls(
            name=name,
            root_layer=root,
            visemes=VisemeSet(),
            eye_blinks=EyeBlinkSet(),
            width=width,
            height=height,
        )
