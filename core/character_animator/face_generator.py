"""
Facial variant generation for Character Animator puppets.

Generates the 14 mouth visemes and eye blink states needed for lip-sync
animation in Adobe Character Animator. Uses cloud AI (Gemini/OpenAI) to
modify the original face to create each expression.
"""

import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from core.constants import get_user_data_dir
from .models import (
    SegmentationResult,
    FacialRegion,
    VisemeSet,
    EyeBlinkSet,
)
from .constants import (
    VISEME_PROMPTS,
    EYE_BLINK_PROMPTS,
    REQUIRED_VISEMES,
)
from .availability import AI_EDITING_AVAILABLE
from .ai_face_editor import AIFaceEditor, EditResult, get_ai_face_editor

logger = logging.getLogger(__name__)


class FaceVariantGenerator:
    """
    Generates mouth visemes and eye blinks for Character Animator puppets.

    Uses cloud AI (Gemini/OpenAI) via AIFaceEditor to modify specific facial
    regions while preserving the overall style and appearance.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        quality_threshold: float = 0.7,
        provider: str = "google",
        model: Optional[str] = None,
    ):
        """
        Initialize the face variant generator.

        Args:
            cache_dir: Directory for caching generated variants
            quality_threshold: Minimum quality score for acceptance (0-1)
            provider: AI provider to use ("google" or "openai")
            model: Specific model to use (defaults to provider's best option)
        """
        self.cache_dir = cache_dir or (get_user_data_dir() / "cache" / "ai_visemes")
        self.quality_threshold = quality_threshold
        self.provider = provider
        self.model = model
        self._ai_editor: Optional[AIFaceEditor] = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize the generator and AI editing pipeline.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        if not AI_EDITING_AVAILABLE:
            logger.error(
                "Cloud AI editing not available for face generation. "
                "Install google-genai or openai package and configure API key."
            )
            return False

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize AIFaceEditor
        self._ai_editor = get_ai_face_editor(
            provider=self.provider,
            model=self.model,
            cache_dir=self.cache_dir,
            quality_threshold=self.quality_threshold,
        )

        if self._ai_editor is None:
            logger.error("Failed to initialize AIFaceEditor")
            return False

        self._initialized = True
        logger.info(f"FaceVariantGenerator initialized with {self.provider} provider")
        return True

    def _get_image_hash(self, image: Image.Image) -> str:
        """Get hash of an image for caching."""
        img_bytes = image.tobytes()
        return hashlib.md5(img_bytes).hexdigest()[:12]

    def get_mouth_region(
        self,
        segmentation: SegmentationResult,
        padding: int = 20,
    ) -> Tuple[Optional[Image.Image], Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
        """
        Extract the mouth region from segmentation results.

        Args:
            segmentation: Segmentation results with face landmarks
            padding: Extra pixels around mouth bbox

        Returns:
            Tuple of (mouth_region_image, mouth_mask, expanded_bbox)
        """
        if segmentation.mouth_region is None:
            logger.error("No mouth region in segmentation")
            return None, None, None

        region = segmentation.mouth_region
        bbox = region.bbox

        # Expand bbox with padding
        x, y, w, h = bbox
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = w + padding * 2
        h = h + padding * 2

        # Ensure within image bounds
        img_w, img_h = segmentation.original_image.size
        x = min(x, img_w - w)
        y = min(y, img_h - h)

        # Store expanded bbox
        expanded_bbox = (x, y, w, h)

        # Extract region
        mouth_image = segmentation.original_image.crop((x, y, x + w, y + h))

        # Create mask for the mouth region
        if region.landmarks is not None:
            mask = self._create_region_mask(region.landmarks, (w, h), (x, y))
        else:
            # Use full region as mask
            mask = np.ones((h, w), dtype=np.uint8) * 255

        return mouth_image, mask, expanded_bbox

    def get_eye_regions(
        self,
        segmentation: SegmentationResult,
        padding: int = 15,
    ) -> Tuple[
        Optional[Tuple[Image.Image, np.ndarray, Tuple[int, int, int, int]]],
        Optional[Tuple[Image.Image, np.ndarray, Tuple[int, int, int, int]]]
    ]:
        """
        Extract left and right eye regions.

        Args:
            segmentation: Segmentation results
            padding: Extra pixels around eye bbox

        Returns:
            Tuple of ((left_eye_img, left_mask, left_bbox), (right_eye_img, right_mask, right_bbox))
        """
        results = []

        for region_attr in ["left_eye_region", "right_eye_region"]:
            region = getattr(segmentation, region_attr)

            if region is None:
                results.append(None)
                continue

            bbox = region.bbox
            x, y, w, h = bbox

            # Expand bbox
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = w + padding * 2
            h = h + padding * 2

            expanded_bbox = (x, y, w, h)

            # Extract region
            eye_image = segmentation.original_image.crop((x, y, x + w, y + h))

            # Create mask
            if region.landmarks is not None:
                mask = self._create_region_mask(region.landmarks, (w, h), (x, y))
            else:
                mask = np.ones((h, w), dtype=np.uint8) * 255

            results.append((eye_image, mask, expanded_bbox))

        return results[0], results[1]

    def _create_region_mask(
        self,
        landmarks: np.ndarray,
        size: Tuple[int, int],
        offset: Tuple[int, int],
    ) -> np.ndarray:
        """
        Create a mask from landmarks.

        Args:
            landmarks: Landmark points
            size: (width, height) of mask
            offset: (x, y) offset to subtract from landmarks

        Returns:
            Binary mask
        """
        try:
            import cv2

            mask = np.zeros((size[1], size[0]), dtype=np.uint8)

            # Adjust landmarks for offset
            adjusted = landmarks[:, :2].copy()
            adjusted[:, 0] -= offset[0]
            adjusted[:, 1] -= offset[1]

            # Create convex hull of landmarks
            hull = cv2.convexHull(adjusted.astype(np.int32))
            cv2.fillConvexPoly(mask, hull, 255)

            return mask

        except Exception as e:
            logger.warning(f"Failed to create region mask: {e}")
            return np.ones((size[1], size[0]), dtype=np.uint8) * 255

    def generate_viseme(
        self,
        full_image: Image.Image,
        mouth_bbox: Tuple[int, int, int, int],
        viseme_name: str,
        use_cache: bool = True,
    ) -> Image.Image:
        """
        Generate a single viseme using cloud AI to edit the mouth region.

        Args:
            full_image: Full face/head image
            mouth_bbox: Bounding box of mouth in full image (x, y, w, h)
            viseme_name: Name of viseme (e.g., "Ah", "Ee")
            use_cache: Whether to use caching

        Returns:
            Full image with modified mouth showing the viseme
        """
        if not self._initialized:
            if not self.initialize():
                logger.error("Failed to initialize generator")
                return full_image

        # Use AIFaceEditor to generate viseme
        result = self._ai_editor.generate_viseme(
            image=full_image,
            mouth_bbox=mouth_bbox,
            viseme_name=viseme_name,
            use_cache=use_cache,
        )

        if result.success and result.image:
            if result.cached:
                logger.info(f"Loaded viseme {viseme_name} from cache")
            else:
                logger.info(f"Generated viseme {viseme_name} via {result.provider}")
            return result.image
        else:
            logger.warning(f"Failed to generate viseme {viseme_name}: {result.error}")
            return full_image

    def generate_all_visemes(
        self,
        full_image: Image.Image,
        segmentation: SegmentationResult,
        progress_callback: Optional[callable] = None,
        use_cache: bool = True,
    ) -> VisemeSet:
        """
        Generate all 14 mouth visemes using cloud AI.

        Args:
            full_image: Full face/head image
            segmentation: Segmentation results with mouth region
            progress_callback: Optional callback(viseme_name, index, total)
            use_cache: Whether to use cached visemes if available

        Returns:
            VisemeSet with all generated visemes
        """
        viseme_set = VisemeSet()

        if not self._initialized:
            if not self.initialize():
                logger.error("Failed to initialize generator")
                return viseme_set

        # Extract mouth region info
        _, _, mouth_bbox = self.get_mouth_region(segmentation, padding=25)

        if mouth_bbox is None:
            logger.error("Cannot extract mouth region")
            return viseme_set

        # Store the mouth bbox for cropping during export
        viseme_set.mouth_bbox = mouth_bbox
        logger.info(f"Mouth bbox for visemes: {mouth_bbox}")

        # Generate each viseme
        for i, viseme_name in enumerate(REQUIRED_VISEMES):
            if progress_callback:
                progress_callback(viseme_name, i, len(REQUIRED_VISEMES))

            logger.info(f"Generating viseme {i+1}/{len(REQUIRED_VISEMES)}: {viseme_name}")

            viseme_image = self.generate_viseme(
                full_image=full_image,
                mouth_bbox=mouth_bbox,
                viseme_name=viseme_name,
                use_cache=use_cache,
            )

            # Store in VisemeSet
            attr_name = viseme_name.lower().replace("-", "_")
            if hasattr(viseme_set, attr_name):
                setattr(viseme_set, attr_name, viseme_image)

        return viseme_set

    def generate_blink_states(
        self,
        full_image: Image.Image,
        segmentation: SegmentationResult,
        use_cache: bool = True,
    ) -> EyeBlinkSet:
        """
        Generate eye blink states using cloud AI.

        Args:
            full_image: Full face/head image
            segmentation: Segmentation results with eye regions
            use_cache: Whether to use cached blink states if available

        Returns:
            EyeBlinkSet with all blink states
        """
        blink_set = EyeBlinkSet()

        if not self._initialized:
            if not self.initialize():
                logger.error("Failed to initialize generator")
                return blink_set

        # Get eye regions
        left_eye_data, right_eye_data = self.get_eye_regions(segmentation)

        # Generate left eye states
        if left_eye_data is not None:
            _, _, left_bbox = left_eye_data

            # Store bbox for positioning during export
            blink_set.left_eye_bbox = left_bbox
            logger.info(f"Left eye bbox: {left_bbox}")

            # Open state - extract original
            blink_set.left_open = full_image.crop((
                left_bbox[0], left_bbox[1],
                left_bbox[0] + left_bbox[2], left_bbox[1] + left_bbox[3]
            )).convert("RGBA")

            # Blink state - generate via AI
            result = self._ai_editor.generate_eye_blink(
                image=full_image,
                eye_bbox=left_bbox,
                side="left",
                state="blink",
                use_cache=use_cache,
            )
            if result.success and result.image:
                # Keep full image - Character Animator handles positioning via layer names
                blink_set.left_blink = result.image.convert("RGBA")
                logger.info("Generated left eye blink state")
            else:
                logger.warning(f"Failed to generate left blink: {result.error}")

        # Generate right eye states
        if right_eye_data is not None:
            _, _, right_bbox = right_eye_data

            # Store bbox for positioning during export
            blink_set.right_eye_bbox = right_bbox
            logger.info(f"Right eye bbox: {right_bbox}")

            # Open state - extract original
            blink_set.right_open = full_image.crop((
                right_bbox[0], right_bbox[1],
                right_bbox[0] + right_bbox[2], right_bbox[1] + right_bbox[3]
            )).convert("RGBA")

            # Blink state - generate via AI
            result = self._ai_editor.generate_eye_blink(
                image=full_image,
                eye_bbox=right_bbox,
                side="right",
                state="blink",
                use_cache=use_cache,
            )
            if result.success and result.image:
                # Keep full image - Character Animator handles positioning via layer names
                blink_set.right_blink = result.image.convert("RGBA")
                logger.info("Generated right eye blink state")
            else:
                logger.warning(f"Failed to generate right blink: {result.error}")

        return blink_set

    def generate_eyebrow_variants(
        self,
        full_image: Image.Image,
        segmentation: SegmentationResult,
        expressions: List[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Image.Image]:
        """
        Generate eyebrow expression variants using cloud AI.

        Args:
            full_image: Full face/head image
            segmentation: Segmentation results
            expressions: List of expressions to generate (default: raised, lowered, concerned)
            use_cache: Whether to use cached variants if available

        Returns:
            Dictionary of expression name to image
        """
        if expressions is None:
            expressions = ["raised", "lowered", "concerned"]

        variants = {}

        if not self._initialized:
            if not self.initialize():
                logger.error("Failed to initialize generator")
                return variants

        # Calculate combined eyebrow region bbox
        left_brow = segmentation.left_eyebrow_region
        right_brow = segmentation.right_eyebrow_region

        if left_brow is None and right_brow is None:
            logger.warning("No eyebrow regions found")
            return variants

        # Combine bboxes
        if left_brow and right_brow:
            lx, ly, lw, lh = left_brow.bbox
            rx, ry, rw, rh = right_brow.bbox
            x = min(lx, rx)
            y = min(ly, ry)
            w = max(lx + lw, rx + rw) - x
            h = max(ly + lh, ry + rh) - y
            combined_bbox = (x, y, w, h)
        elif left_brow:
            combined_bbox = left_brow.bbox
        else:
            combined_bbox = right_brow.bbox

        # Add padding
        padding = 10
        x, y, w, h = combined_bbox
        combined_bbox = (
            max(0, x - padding),
            max(0, y - padding),
            w + padding * 2,
            h + padding * 2,
        )

        # Generate each expression
        for expression in expressions:
            result = self._ai_editor.generate_expression(
                image=full_image,
                face_bbox=combined_bbox,
                expression=expression,
                use_cache=use_cache,
            )

            if result.success and result.image:
                variants[expression] = result.image
                logger.info(f"Generated eyebrow variant: {expression}")
            else:
                logger.warning(f"Failed to generate {expression}: {result.error}")

        return variants

    def start_batch_session(self, character_image: Image.Image) -> bool:
        """
        Start a batch editing session for generating multiple visemes.

        Uses conversational editing (Gemini) for better style consistency
        across all generated variants.

        Args:
            character_image: The base character image

        Returns:
            True if session started successfully
        """
        if not self._initialized:
            if not self.initialize():
                return False

        return self._ai_editor.start_conversation_session(character_image)

    def end_batch_session(self):
        """End the batch editing session."""
        if self._ai_editor:
            self._ai_editor.end_conversation_session()

    def cleanup(self):
        """Release resources."""
        if self._ai_editor is not None:
            self._ai_editor.cleanup()
            self._ai_editor = None

        self._initialized = False
        logger.info("Face generator resources released")
