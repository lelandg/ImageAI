"""
Reference Image Manager for Video Projects.
Handles reference image types, validation, generation, and smart selection.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from PIL import Image

logger = logging.getLogger(__name__)


class ReferenceImageType(Enum):
    """Types of reference images for Veo 3 video generation"""
    CHARACTER = "character"      # Person/face consistency
    OBJECT = "object"            # Props, items, products
    ENVIRONMENT = "environment"  # Locations, settings, backgrounds
    STYLE = "style"             # Visual style (Veo 2.0 only, future-proofing)


@dataclass
class ReferenceImageInfo:
    """Information about a reference image including validation results"""
    path: Path
    type: ReferenceImageType
    name: str  # User-friendly name like "Sarah", "Vintage Car"
    description: Optional[str] = None
    width: int = 0
    height: int = 0
    file_size_mb: float = 0.0
    format: str = ""
    aspect_ratio: float = 0.0
    is_valid: bool = False
    validation_errors: List[str] = None
    validation_warnings: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
        if self.validation_warnings is None:
            self.validation_warnings = []
        if self.metadata is None:
            self.metadata = {}


class ReferenceImageValidator:
    """Validates reference images for Veo 3 API requirements"""

    # Veo 3 requirements
    MIN_RESOLUTION = 720  # 720p minimum
    SUPPORTED_FORMATS = ['PNG', 'JPEG', 'JPG']
    RECOMMENDED_ASPECT_RATIOS = [16/9, 9/16, 1/1, 4/3, 3/4]
    MAX_FILE_SIZE_MB = 50  # Safety limit

    @classmethod
    def validate_reference_image(cls, image_path: Path) -> ReferenceImageInfo:
        """
        Validate a reference image against Veo 3 requirements.

        Args:
            image_path: Path to image file

        Returns:
            ReferenceImageInfo with validation results
        """
        info = ReferenceImageInfo(
            path=image_path,
            type=ReferenceImageType.CHARACTER,  # Default, user should change
            name=image_path.stem
        )

        # Check file exists
        if not image_path.exists():
            info.validation_errors.append(f"File not found: {image_path}")
            return info

        try:
            # Load image
            img = Image.open(image_path)
            info.width, info.height = img.size
            info.format = img.format or image_path.suffix[1:].upper()
            info.aspect_ratio = info.width / info.height if info.height > 0 else 0

            # Get file size
            file_size_bytes = image_path.stat().st_size
            info.file_size_mb = file_size_bytes / (1024 * 1024)

            # Validate format
            if info.format not in cls.SUPPORTED_FORMATS:
                info.validation_errors.append(
                    f"Unsupported format: {info.format}. Use PNG or JPEG."
                )

            # Validate resolution
            max_dim = max(info.width, info.height)
            if max_dim < cls.MIN_RESOLUTION:
                info.validation_errors.append(
                    f"Resolution too low: {info.width}×{info.height}. "
                    f"Minimum {cls.MIN_RESOLUTION}p (720p) required."
                )

            # Validate file size
            if info.file_size_mb > cls.MAX_FILE_SIZE_MB:
                info.validation_warnings.append(
                    f"Large file size: {info.file_size_mb:.1f}MB. "
                    f"Consider compressing to under {cls.MAX_FILE_SIZE_MB}MB."
                )

            # Check aspect ratio (warning only)
            aspect_match = any(
                abs(info.aspect_ratio - r) < 0.05
                for r in cls.RECOMMENDED_ASPECT_RATIOS
            )
            if not aspect_match:
                info.validation_warnings.append(
                    f"Non-standard aspect ratio: {info.aspect_ratio:.2f}. "
                    f"Recommended: 16:9, 9:16, 1:1, 4:3, or 3:4 for best results."
                )

            # Mark as valid if no errors
            info.is_valid = len(info.validation_errors) == 0

            if info.is_valid:
                logger.info(
                    f"✓ Valid reference image: {image_path.name} "
                    f"({info.width}×{info.height}, {info.format}, "
                    f"{info.file_size_mb:.1f}MB)"
                )
            else:
                logger.warning(
                    f"✗ Invalid reference image: {image_path.name} - "
                    f"{'; '.join(info.validation_errors)}"
                )

        except Exception as e:
            info.validation_errors.append(f"Failed to load image: {str(e)}")
            logger.error(f"Error validating {image_path}: {e}", exc_info=True)

        return info

    @classmethod
    def get_validation_summary(cls, info: ReferenceImageInfo) -> str:
        """Get human-readable validation summary"""
        if info.is_valid:
            summary = f"✓ Valid ({info.width}×{info.height}, {info.format})"
            if info.validation_warnings:
                summary += f"\n  Warnings: {'; '.join(info.validation_warnings)}"
            return summary
        else:
            return f"✗ Invalid: {'; '.join(info.validation_errors)}"


class ReferenceManager:
    """Manages reference images for video projects"""

    def __init__(self, project_dir: Optional[Path] = None):
        """
        Initialize reference manager.

        Args:
            project_dir: Project directory for storing references
        """
        self.project_dir = project_dir
        self.logger = logging.getLogger(__name__)

    def organize_references_by_type(
        self,
        references: List['ReferenceImage']
    ) -> Dict[ReferenceImageType, List['ReferenceImage']]:
        """
        Organize references by type for UI display.

        Args:
            references: List of ReferenceImage objects

        Returns:
            Dictionary mapping type to list of references
        """
        organized = {ref_type: [] for ref_type in ReferenceImageType}

        for ref in references:
            # Get type from label (legacy) or metadata
            ref_type = self._parse_reference_type(ref)
            organized[ref_type].append(ref)

        return organized

    def _parse_reference_type(self, ref: 'ReferenceImage') -> ReferenceImageType:
        """Parse reference type from ReferenceImage object"""
        # Check metadata first
        if ref.metadata and 'type' in ref.metadata:
            try:
                return ReferenceImageType(ref.metadata['type'])
            except ValueError:
                pass

        # Check label
        if ref.label:
            label_lower = ref.label.lower()
            if 'character' in label_lower or 'person' in label_lower:
                return ReferenceImageType.CHARACTER
            elif 'object' in label_lower or 'prop' in label_lower:
                return ReferenceImageType.OBJECT
            elif 'environment' in label_lower or 'scene' in label_lower or 'location' in label_lower:
                return ReferenceImageType.ENVIRONMENT
            elif 'style' in label_lower:
                return ReferenceImageType.STYLE

        # Default to CHARACTER
        return ReferenceImageType.CHARACTER

    def select_references_for_scene(
        self,
        scene_prompt: str,
        available_refs: List['ReferenceImage'],
        max_refs: int = 3
    ) -> List['ReferenceImage']:
        """
        Smart selection of references based on scene content.

        Args:
            scene_prompt: Scene prompt text
            available_refs: Available reference images
            max_refs: Maximum number to select (default 3)

        Returns:
            List of selected references (up to max_refs)
        """
        selected = []
        prompt_lower = scene_prompt.lower()

        # Score each reference based on relevance
        scored_refs = []
        for ref in available_refs:
            score = self._score_reference_relevance(ref, prompt_lower)
            scored_refs.append((score, ref))

        # Sort by score (descending) and take top N
        scored_refs.sort(key=lambda x: x[0], reverse=True)
        selected = [ref for _, ref in scored_refs[:max_refs]]

        if selected:
            self.logger.info(
                f"Auto-selected {len(selected)} reference(s) for scene: "
                f"{[self._get_reference_name(ref) for ref in selected]}"
            )

        return selected

    def _score_reference_relevance(self, ref: 'ReferenceImage', prompt_lower: str) -> float:
        """Score reference relevance to prompt (0.0 to 1.0)"""
        score = 0.0

        # Check if reference name/description appears in prompt
        ref_name = self._get_reference_name(ref).lower()
        if ref_name and ref_name in prompt_lower:
            score += 0.5

        if ref.description and ref.description.lower() in prompt_lower:
            score += 0.3

        # Prioritize characters
        ref_type = self._parse_reference_type(ref)
        if ref_type == ReferenceImageType.CHARACTER:
            score += 0.2
        elif ref_type == ReferenceImageType.ENVIRONMENT:
            score += 0.1

        return min(score, 1.0)

    def _get_reference_name(self, ref: 'ReferenceImage') -> str:
        """Get display name for reference"""
        if ref.metadata and 'name' in ref.metadata:
            return ref.metadata['name']
        if ref.label:
            return ref.label
        return ref.path.stem if ref.path else "Unknown"

    def should_use_last_frame_continuity(
        self,
        prev_scene: 'Scene',
        current_scene: 'Scene',
        check_prompts: bool = True
    ) -> Tuple[bool, str]:
        """
        Determine if last-frame continuity makes sense between scenes.

        Args:
            prev_scene: Previous scene
            current_scene: Current scene
            check_prompts: Whether to analyze prompts for compatibility

        Returns:
            Tuple of (should_use, reason)
        """
        # Check if scenes are sequential
        if abs(current_scene.order - prev_scene.order) != 1:
            return False, "Scenes are not sequential"

        # Check if previous scene has a last frame
        if not prev_scene.last_frame or not prev_scene.last_frame.exists():
            return False, "Previous scene has no last frame"

        if not check_prompts:
            return True, "Sequential scenes with last frame available"

        # Check for explicit transitions in prompt
        transition_keywords = [
            "fade to", "cut to", "later", "meanwhile", "elsewhere",
            "different location", "new scene", "next day", "hours later"
        ]

        current_prompt_lower = current_scene.video_prompt.lower()
        for keyword in transition_keywords:
            if keyword in current_prompt_lower:
                return False, f"Explicit transition detected: '{keyword}'"

        # Check for location changes (basic heuristic)
        location_words = [
            "bedroom", "kitchen", "street", "park", "office", "car",
            "restaurant", "cafe", "store", "building", "room", "house"
        ]

        prev_locations = [
            word for word in location_words
            if word in prev_scene.video_prompt.lower()
        ]
        curr_locations = [
            word for word in location_words
            if word in current_prompt_lower
        ]

        if prev_locations and curr_locations:
            if not any(loc in curr_locations for loc in prev_locations):
                return False, f"Location change detected: {prev_locations} → {curr_locations}"

        # All checks passed - use continuity
        return True, "Compatible sequential scenes"

    def generate_character_references(
        self,
        character_description: str,
        style: str,
        image_generator,
        output_dir: Path
    ) -> List[Path]:
        """
        Generate 3 reference images for a character.

        Args:
            character_description: Description like "Sarah - young woman, dark hair, blue jacket"
            style: Visual style to apply
            image_generator: Image generation function/provider
            output_dir: Directory to save references

        Returns:
            List of generated image paths
        """
        self.logger.info(f"Generating character references for: {character_description}")

        # Create reference prompts (3 angles)
        prompts = [
            f"{character_description}, front view portrait, neutral background, {style}",
            f"{character_description}, 3/4 side view, neutral background, {style}",
            f"{character_description}, full body standing, neutral background, {style}"
        ]

        output_dir.mkdir(parents=True, exist_ok=True)
        reference_paths = []

        for i, prompt in enumerate(prompts, 1):
            try:
                self.logger.info(f"Generating reference {i}/3: {prompt[:80]}...")

                # Generate image (implementation depends on image_generator interface)
                image_path = image_generator(prompt, output_dir, f"char_ref_{i}")

                if image_path and image_path.exists():
                    # Validate generated reference
                    info = ReferenceImageValidator.validate_reference_image(image_path)
                    if info.is_valid:
                        reference_paths.append(image_path)
                        self.logger.info(f"✓ Generated reference {i}/3: {image_path.name}")
                    else:
                        self.logger.warning(
                            f"✗ Generated reference {i}/3 failed validation: "
                            f"{'; '.join(info.validation_errors)}"
                        )
                else:
                    self.logger.error(f"✗ Failed to generate reference {i}/3")

            except Exception as e:
                self.logger.error(f"Error generating reference {i}/3: {e}", exc_info=True)

        self.logger.info(
            f"Character reference generation complete: "
            f"{len(reference_paths)}/3 successful"
        )

        return reference_paths
