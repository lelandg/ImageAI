"""
Data models for Imagen 3 reference images.

This module defines the data structures for managing reference images
used with Google's Imagen 3 Customization API.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ImagenReferenceType(Enum):
    """Types of reference images supported by Imagen 3 Customization API."""
    SUBJECT = "subject"  # Person, animal, or product to preserve
    STYLE = "style"      # Artistic style to apply
    CONTROL = "control"  # Structural control (edges, face mesh, scribble)
    RAW = "raw"         # Base image for editing (editing mode only)
    MASK = "mask"       # Segmentation mask (editing mode only)


class ImagenSubjectType(Enum):
    """Subject types for SUBJECT reference images."""
    PERSON = "person"    # Human subjects
    ANIMAL = "animal"    # Animal subjects
    PRODUCT = "product"  # Product/object subjects
    DEFAULT = "default"  # Generic subject


class ImagenControlType(Enum):
    """Control types for CONTROL reference images."""
    FACE_MESH = "face_mesh"  # Face landmark control
    CANNY = "canny"          # Canny edge detection
    SCRIBBLE = "scribble"    # Hand-drawn scribble control


@dataclass
class ImagenReference:
    """
    Reference image for Imagen 3 customization.

    Represents a single reference image with its associated metadata
    for use with the Imagen 3 Customization API.

    Attributes:
        path: Path to the image file
        reference_type: Type of reference (SUBJECT, STYLE, CONTROL, etc.)
        reference_id: Reference ID (1-4) used in prompt tags like [1], [2]
        subject_type: Subject type (for SUBJECT references)
        subject_description: Text description of the subject/style
        control_type: Control method (for CONTROL references)
        image_data: Cached image bytes (loaded on demand)
        mime_type: MIME type of the image
        metadata: Additional metadata
    """

    path: Path
    reference_type: ImagenReferenceType
    reference_id: int
    subject_type: Optional[ImagenSubjectType] = None
    subject_description: Optional[str] = None
    control_type: Optional[ImagenControlType] = None
    image_data: Optional[bytes] = None
    mime_type: str = "image/png"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate reference data after initialization."""
        # Validate reference ID range
        if not 1 <= self.reference_id <= 4:
            raise ValueError(f"reference_id must be 1-4, got {self.reference_id}")

        # Validate path exists
        if not self.path.exists():
            logger.warning(f"Reference image path does not exist: {self.path}")

        # Validate type-specific requirements
        if self.reference_type == ImagenReferenceType.SUBJECT:
            if self.subject_type is None:
                logger.warning(f"SUBJECT reference without subject_type: {self.path.name}")

        elif self.reference_type == ImagenReferenceType.CONTROL:
            if self.control_type is None:
                logger.warning(f"CONTROL reference without control_type: {self.path.name}")

        # Auto-detect MIME type from file extension if needed
        if not self.mime_type or self.mime_type == "image/png":
            ext = self.path.suffix.lower()
            mime_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            self.mime_type = mime_map.get(ext, 'image/png')

    def load_image_data(self) -> bytes:
        """
        Load image data from file.

        Returns:
            Image data as bytes

        Raises:
            FileNotFoundError: If image file doesn't exist
            IOError: If image cannot be read
        """
        if self.image_data is None:
            try:
                with open(self.path, 'rb') as f:
                    self.image_data = f.read()
                logger.debug(f"Loaded image data: {self.path.name} ({len(self.image_data)} bytes)")
            except Exception as e:
                logger.error(f"Failed to load image {self.path}: {e}")
                raise

        return self.image_data

    def get_display_name(self) -> str:
        """
        Get user-friendly display name for this reference.

        Returns:
            Display name combining file name and description
        """
        name = self.path.stem
        if self.subject_description:
            return f"{name} - {self.subject_description[:30]}"
        return name

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert reference to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        data = {
            'path': str(self.path),
            'reference_type': self.reference_type.value,
            'reference_id': self.reference_id,
            'subject_type': self.subject_type.value if self.subject_type else None,
            'subject_description': self.subject_description,
            'mime_type': self.mime_type,
            'metadata': self.metadata
        }

        # Save control_type for CONTROL references
        if self.control_type:
            data['control_type'] = self.control_type.value

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImagenReference':
        """
        Create reference from dictionary.

        Args:
            data: Dictionary with reference data

        Returns:
            ImagenReference instance
        """
        # Parse reference type
        ref_type = ImagenReferenceType(data['reference_type'])

        # For CONTROL type, default to CANNY if not specified
        control_type = None
        if ref_type == ImagenReferenceType.CONTROL:
            if data.get('control_type'):
                control_type = ImagenControlType(data['control_type'])
            else:
                control_type = ImagenControlType.CANNY  # Default

        return cls(
            path=Path(data['path']),
            reference_type=ref_type,
            reference_id=data['reference_id'],
            subject_type=ImagenSubjectType(data['subject_type']) if data.get('subject_type') else None,
            subject_description=data.get('subject_description'),
            control_type=control_type,
            mime_type=data.get('mime_type', 'image/png'),
            metadata=data.get('metadata', {})
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"ImagenReference(id={self.reference_id}, type={self.reference_type.value}, "
            f"path={self.path.name})"
        )


def validate_references(references: list['ImagenReference']) -> tuple[bool, list[str]]:
    """
    Validate a list of references for API submission.

    Args:
        references: List of ImagenReference objects

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check count
    if len(references) == 0:
        errors.append("At least 1 reference image required")
    elif len(references) > 4:
        errors.append(f"Maximum 4 references allowed, got {len(references)}")

    # Check reference IDs are sequential and unique
    reference_ids = [ref.reference_id for ref in references]
    expected_ids = list(range(1, len(references) + 1))

    if sorted(reference_ids) != expected_ids:
        errors.append(
            f"Reference IDs must be sequential 1-{len(references)}, "
            f"got {reference_ids}"
        )

    if len(set(reference_ids)) != len(reference_ids):
        errors.append("Duplicate reference IDs found")

    # Check each reference
    for ref in references:
        if not ref.path.exists():
            errors.append(f"Image file not found: {ref.path}")

        # Type-specific validation
        if ref.reference_type == ImagenReferenceType.SUBJECT:
            if ref.subject_type is None:
                errors.append(f"SUBJECT reference {ref.reference_id} missing subject_type")

    is_valid = len(errors) == 0
    return is_valid, errors


def auto_assign_reference_ids(references: list['ImagenReference']) -> None:
    """
    Automatically assign sequential reference IDs to references.

    Args:
        references: List of ImagenReference objects (modified in place)
    """
    for idx, ref in enumerate(references, start=1):
        ref.reference_id = idx

    logger.debug(f"Auto-assigned reference IDs 1-{len(references)}")
