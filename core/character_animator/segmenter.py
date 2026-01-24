"""
Body part segmentation for Character Animator puppets.

Uses MediaPipe for:
- Pose detection (33 landmarks) for body structure
- Face mesh (478 landmarks) for precise facial feature extraction

This module handles the extraction of body parts and facial features from
a single image, preparing them for puppet layer creation.

Note: SAM 2 and Depth-Anything have been removed in favor of simpler
MediaPipe-only detection. Cloud AI (Gemini/OpenAI) handles the complex
viseme generation. See Plans/AICharacterGenerator.md.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from core.constants import get_user_data_dir
from .models import SegmentationResult, FacialRegion
from .constants import (
    POSE_LANDMARK_INDICES,
    FACE_OVAL_LANDMARKS,
    MOUTH_LANDMARKS,
    LEFT_EYE_LANDMARKS,
    RIGHT_EYE_LANDMARKS,
    LEFT_EYEBROW_LANDMARKS,
    RIGHT_EYEBROW_LANDMARKS,
    MIN_REGION_SIZES,
)
from .availability import (
    SEGMENTATION_AVAILABLE,
    POSE_DETECTION_AVAILABLE,
)

logger = logging.getLogger(__name__)


class BodyPartSegmenter:
    """
    Segments body parts from an image for Character Animator puppet creation.

    Uses MediaPipe for pose and face detection. SAM 2 can optionally be used
    for more precise mask generation if available.
    """

    def __init__(self, model_path: Optional[Path] = None):
        """
        Initialize the segmenter.

        Args:
            model_path: Optional path to SAM 2 model weights (if using SAM)
        """
        self.model_path = model_path
        self._mp_pose = None
        self._mp_face_mesh = None
        self._sam_predictor = None
        self._initialized = False

    def _init_mediapipe(self):
        """Initialize MediaPipe models."""
        if not POSE_DETECTION_AVAILABLE:
            logger.warning("MediaPipe not available for pose detection")
            return False

        try:
            import mediapipe as mp

            # Initialize pose detection
            self._mp_pose = mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=2,  # Most accurate
                enable_segmentation=True,
                min_detection_confidence=0.5,
            )

            # Initialize face mesh
            self._mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,  # Include iris landmarks
                min_detection_confidence=0.5,
            )

            logger.info("MediaPipe pose and face detection initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe: {e}")
            return False

    def _init_sam(self):
        """Initialize SAM 2 for optional mask refinement."""
        if not SEGMENTATION_AVAILABLE:
            logger.debug("SAM 2 not available - using MediaPipe masks only")
            return False

        try:
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            import torch

            # Use default model path if not specified
            if self.model_path is None:
                self.model_path = get_user_data_dir() / "weights" / "character_animator" / "sam2_hiera_large.pt"

            if not self.model_path.exists():
                logger.debug(f"SAM 2 model not found at {self.model_path}")
                return False

            # Detect device
            device = "cuda" if torch.cuda.is_available() else "cpu"

            # Build SAM 2 model
            sam2_model = build_sam2(
                config_file="sam2_hiera_l.yaml",
                ckpt_path=str(self.model_path),
                device=device,
            )

            self._sam_predictor = SAM2ImagePredictor(sam2_model)
            logger.info(f"SAM 2 initialized on {device} (optional enhancement)")
            return True

        except Exception as e:
            logger.debug(f"SAM 2 not initialized (optional): {e}")
            return False

    def initialize(self) -> bool:
        """
        Initialize all available AI models.

        Returns:
            True if at least MediaPipe was initialized successfully
        """
        if self._initialized:
            return True

        # MediaPipe is required minimum
        if not self._init_mediapipe():
            logger.error("Cannot initialize - MediaPipe is required")
            return False

        # SAM is optional enhancement
        self._init_sam()

        self._initialized = True
        return True

    def detect_pose(self, image: Image.Image) -> Optional[np.ndarray]:
        """
        Detect pose landmarks using MediaPipe.

        Args:
            image: PIL Image to process

        Returns:
            Array of 33 pose landmarks (x, y, z, visibility) or None
        """
        if self._mp_pose is None:
            if not self._init_mediapipe():
                return None

        try:
            # Convert to RGB numpy array
            img_array = np.array(image.convert("RGB"))

            # Process with MediaPipe
            results = self._mp_pose.process(img_array)

            if results.pose_landmarks is None:
                logger.warning("No pose detected in image")
                return None

            # Extract landmarks as numpy array
            landmarks = np.array([
                [lm.x * image.width, lm.y * image.height, lm.z, lm.visibility]
                for lm in results.pose_landmarks.landmark
            ])

            logger.info(f"Detected {len(landmarks)} pose landmarks")
            return landmarks

        except Exception as e:
            logger.error(f"Pose detection failed: {e}")
            return None

    def detect_face(self, image: Image.Image) -> Optional[np.ndarray]:
        """
        Detect face mesh landmarks using MediaPipe.

        Args:
            image: PIL Image to process

        Returns:
            Array of 478 face landmarks (x, y, z) or None
        """
        if self._mp_face_mesh is None:
            if not self._init_mediapipe():
                return None

        try:
            # Convert to RGB numpy array
            img_array = np.array(image.convert("RGB"))

            # Process with MediaPipe
            results = self._mp_face_mesh.process(img_array)

            if not results.multi_face_landmarks:
                logger.warning("No face detected in image")
                return None

            # Get first face
            face_landmarks = results.multi_face_landmarks[0]

            # Extract landmarks as numpy array
            landmarks = np.array([
                [lm.x * image.width, lm.y * image.height, lm.z]
                for lm in face_landmarks.landmark
            ])

            logger.info(f"Detected {len(landmarks)} face landmarks")
            return landmarks

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return None

    def _get_bbox_from_landmarks(
        self, landmarks: np.ndarray, indices: List[int], padding: int = 10
    ) -> Tuple[int, int, int, int]:
        """
        Get bounding box from landmark indices.

        Args:
            landmarks: All landmarks array
            indices: Indices of landmarks to include
            padding: Pixels to add around bounding box

        Returns:
            Bounding box as (x, y, width, height)
        """
        points = landmarks[indices][:, :2]  # Only x, y
        x_min, y_min = points.min(axis=0) - padding
        x_max, y_max = points.max(axis=0) + padding

        return (
            int(max(0, x_min)),
            int(max(0, y_min)),
            int(x_max - x_min),
            int(y_max - y_min),
        )

    def _create_mask_from_landmarks(
        self, landmarks: np.ndarray, indices: List[int], image_size: Tuple[int, int]
    ) -> np.ndarray:
        """
        Create a binary mask from landmark polygon.

        Args:
            landmarks: All landmarks array
            indices: Indices of landmarks forming the polygon
            image_size: (width, height) of the image

        Returns:
            Binary mask as numpy array
        """
        try:
            import cv2

            # Create empty mask
            mask = np.zeros((image_size[1], image_size[0]), dtype=np.uint8)

            # Get polygon points
            points = landmarks[indices][:, :2].astype(np.int32)

            # Fill polygon
            cv2.fillPoly(mask, [points], 255)

            return mask

        except Exception as e:
            logger.error(f"Failed to create mask: {e}")
            return np.zeros((image_size[1], image_size[0]), dtype=np.uint8)

    def _get_facial_region(
        self,
        landmarks: np.ndarray,
        region_indices: Dict[str, List[int]],
        name: str,
    ) -> FacialRegion:
        """
        Extract a facial region from landmarks.

        Args:
            landmarks: Face mesh landmarks
            region_indices: Dictionary of landmark indices for this region
            name: Name of the region

        Returns:
            FacialRegion object
        """
        # Flatten all indices
        all_indices = []
        for indices in region_indices.values():
            all_indices.extend(indices)
        all_indices = list(set(all_indices))  # Remove duplicates

        bbox = self._get_bbox_from_landmarks(landmarks, all_indices, padding=5)
        region_landmarks = landmarks[all_indices]

        return FacialRegion(
            name=name,
            bbox=bbox,
            landmarks=region_landmarks,
        )

    def segment_body_parts(self, image: Image.Image) -> SegmentationResult:
        """
        Segment all body parts from the image.

        This is the main entry point for segmentation. It:
        1. Detects pose landmarks
        2. Detects face mesh
        3. Creates bounding boxes and masks for body parts
        4. Extracts facial regions for viseme/blink generation

        Args:
            image: PIL Image to process

        Returns:
            SegmentationResult with all detected regions
        """
        if not self.initialize():
            raise RuntimeError("Failed to initialize segmentation models")

        result = SegmentationResult(original_image=image)

        # Step 1: Detect pose
        pose_landmarks = self.detect_pose(image)
        if pose_landmarks is not None:
            result.pose_landmarks = pose_landmarks

            # Create body part regions from pose
            self._segment_body_from_pose(result, pose_landmarks, image.size)

        # Step 2: Detect face mesh
        face_landmarks = self.detect_face(image)
        if face_landmarks is not None:
            result.face_landmarks = face_landmarks

            # Extract facial regions
            self._segment_face_from_mesh(result, face_landmarks, image.size)

        # Step 3: Optionally refine with SAM if available
        if self._sam_predictor is not None:
            self._refine_with_sam(result, image)

        return result

    def _segment_body_from_pose(
        self,
        result: SegmentationResult,
        landmarks: np.ndarray,
        image_size: Tuple[int, int],
    ):
        """
        Create body part segmentation from pose landmarks.

        Args:
            result: SegmentationResult to update
            landmarks: Pose landmarks array
            image_size: (width, height) of image
        """
        # Head region (from face landmarks in pose)
        head_indices = [
            POSE_LANDMARK_INDICES["nose"],
            POSE_LANDMARK_INDICES["left_eye"],
            POSE_LANDMARK_INDICES["right_eye"],
            POSE_LANDMARK_INDICES["left_ear"],
            POSE_LANDMARK_INDICES["right_ear"],
            POSE_LANDMARK_INDICES["mouth_left"],
            POSE_LANDMARK_INDICES["mouth_right"],
        ]
        result.head_bbox = self._get_bbox_from_landmarks(landmarks, head_indices, padding=50)

        # Torso region
        torso_indices = [
            POSE_LANDMARK_INDICES["left_shoulder"],
            POSE_LANDMARK_INDICES["right_shoulder"],
            POSE_LANDMARK_INDICES["left_hip"],
            POSE_LANDMARK_INDICES["right_hip"],
        ]
        result.torso_bbox = self._get_bbox_from_landmarks(landmarks, torso_indices, padding=20)

        # Left arm
        left_arm_indices = [
            POSE_LANDMARK_INDICES["left_shoulder"],
            POSE_LANDMARK_INDICES["left_elbow"],
            POSE_LANDMARK_INDICES["left_wrist"],
        ]
        result.left_arm_bbox = self._get_bbox_from_landmarks(landmarks, left_arm_indices, padding=15)

        # Right arm
        right_arm_indices = [
            POSE_LANDMARK_INDICES["right_shoulder"],
            POSE_LANDMARK_INDICES["right_elbow"],
            POSE_LANDMARK_INDICES["right_wrist"],
        ]
        result.right_arm_bbox = self._get_bbox_from_landmarks(landmarks, right_arm_indices, padding=15)

        logger.info("Created body part bounding boxes from pose landmarks")

    def _segment_face_from_mesh(
        self,
        result: SegmentationResult,
        landmarks: np.ndarray,
        image_size: Tuple[int, int],
    ):
        """
        Extract facial regions from face mesh landmarks.

        Args:
            result: SegmentationResult to update
            landmarks: Face mesh landmarks array (478 points)
            image_size: (width, height) of image
        """
        # Update head bbox with face mesh (more accurate than pose)
        result.head_bbox = self._get_bbox_from_landmarks(
            landmarks, FACE_OVAL_LANDMARKS, padding=30
        )
        result.head_mask = self._create_mask_from_landmarks(
            landmarks, FACE_OVAL_LANDMARKS, image_size
        )

        # Left eye region
        result.left_eye_region = self._get_facial_region(
            landmarks, LEFT_EYE_LANDMARKS, "left_eye"
        )

        # Right eye region
        result.right_eye_region = self._get_facial_region(
            landmarks, RIGHT_EYE_LANDMARKS, "right_eye"
        )

        # Mouth region - combine all mouth landmarks
        mouth_indices = []
        for indices in MOUTH_LANDMARKS.values():
            mouth_indices.extend(indices)
        mouth_indices = list(set(mouth_indices))

        result.mouth_region = FacialRegion(
            name="mouth",
            bbox=self._get_bbox_from_landmarks(landmarks, mouth_indices, padding=10),
            landmarks=landmarks[mouth_indices],
        )

        # Left eyebrow
        result.left_eyebrow_region = FacialRegion(
            name="left_eyebrow",
            bbox=self._get_bbox_from_landmarks(landmarks, LEFT_EYEBROW_LANDMARKS, padding=5),
            landmarks=landmarks[LEFT_EYEBROW_LANDMARKS],
        )

        # Right eyebrow
        result.right_eyebrow_region = FacialRegion(
            name="right_eyebrow",
            bbox=self._get_bbox_from_landmarks(landmarks, RIGHT_EYEBROW_LANDMARKS, padding=5),
            landmarks=landmarks[RIGHT_EYEBROW_LANDMARKS],
        )

        logger.info("Extracted facial regions from face mesh")

    def _refine_with_sam(self, result: SegmentationResult, image: Image.Image):
        """
        Optionally refine segmentation masks using SAM 2.

        Uses bounding boxes from pose/face detection as prompts for SAM
        to generate more precise masks. This is optional - if SAM is not
        available, MediaPipe masks are used directly.

        Args:
            result: SegmentationResult to update
            image: Original image
        """
        if self._sam_predictor is None:
            return

        try:
            # Set image for SAM
            img_array = np.array(image.convert("RGB"))
            self._sam_predictor.set_image(img_array)

            # Refine head mask if we have a bbox
            if result.head_bbox is not None:
                x, y, w, h = result.head_bbox
                box = np.array([x, y, x + w, y + h])

                masks, scores, _ = self._sam_predictor.predict(
                    box=box,
                    multimask_output=True,
                )

                # Use highest scoring mask
                best_mask_idx = np.argmax(scores)
                result.head_mask = masks[best_mask_idx].astype(np.uint8) * 255

                logger.info(f"Refined head mask with SAM (score: {scores[best_mask_idx]:.3f})")

            # Refine torso mask
            if result.torso_bbox is not None:
                x, y, w, h = result.torso_bbox
                box = np.array([x, y, x + w, y + h])

                masks, scores, _ = self._sam_predictor.predict(
                    box=box,
                    multimask_output=True,
                )

                best_mask_idx = np.argmax(scores)
                result.torso_mask = masks[best_mask_idx].astype(np.uint8) * 255

                logger.info(f"Refined torso mask with SAM (score: {scores[best_mask_idx]:.3f})")

            # Refine arm masks
            for arm_name, bbox_attr, mask_attr in [
                ("left_arm", "left_arm_bbox", "left_arm_mask"),
                ("right_arm", "right_arm_bbox", "right_arm_mask"),
            ]:
                bbox = getattr(result, bbox_attr)
                if bbox is not None:
                    x, y, w, h = bbox
                    box = np.array([x, y, x + w, y + h])

                    masks, scores, _ = self._sam_predictor.predict(
                        box=box,
                        multimask_output=True,
                    )

                    best_mask_idx = np.argmax(scores)
                    setattr(result, mask_attr, masks[best_mask_idx].astype(np.uint8) * 255)

                    logger.info(f"Refined {arm_name} mask with SAM")

        except Exception as e:
            logger.warning(f"SAM refinement failed (using MediaPipe masks): {e}")

    def extract_layer_image(
        self,
        image: Image.Image,
        mask: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> Image.Image:
        """
        Extract a layer image using a mask.

        Args:
            image: Source image
            mask: Binary mask for extraction
            bbox: Optional bounding box to crop to

        Returns:
            RGBA image with transparent background where mask is 0
        """
        # Ensure RGBA
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        # Create output with transparency
        img_array = np.array(image)
        output = img_array.copy()

        # Apply mask to alpha channel
        if mask.shape[:2] != img_array.shape[:2]:
            # Resize mask to match image
            from PIL import Image as PILImage
            mask_img = PILImage.fromarray(mask)
            mask_img = mask_img.resize(image.size, PILImage.Resampling.NEAREST)
            mask = np.array(mask_img)

        output[:, :, 3] = mask

        result = Image.fromarray(output)

        # Crop to bounding box if provided
        if bbox is not None:
            x, y, w, h = bbox
            result = result.crop((x, y, x + w, y + h))

        return result

    def cleanup(self):
        """Release resources."""
        if self._mp_pose is not None:
            self._mp_pose.close()
            self._mp_pose = None

        if self._mp_face_mesh is not None:
            self._mp_face_mesh.close()
            self._mp_face_mesh = None

        self._sam_predictor = None
        self._initialized = False

        logger.info("Segmenter resources released")
