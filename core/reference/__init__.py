"""
Reference image management for Imagen 3 customization.

This package provides data models and utilities for managing multiple
reference images for Google Imagen 3's customization API.
"""

from .imagen_reference import (
    ImagenReferenceType,
    ImagenSubjectType,
    ImagenControlType,
    ImagenReference,
    validate_references
)

__all__ = [
    'ImagenReferenceType',
    'ImagenSubjectType',
    'ImagenControlType',
    'ImagenReference',
    'validate_references'
]
