"""Lazy MediaPipe vision Tasks and verified models in the configured model cache."""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import threading
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
import requests
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from core.paths import get_data_paths

logger = logging.getLogger(__name__)
MEDIAPIPE_SPEC = "mediapipe>=1.0.1,<2"
# Official Google model downloads, pinned by digest. Model changes require review.
_MODELS = {
    "selfie": (
        "image_segmenter/selfie_segmenter_landscape/float16/1/selfie_segmenter_landscape.tflite",
        "490e9ea734313e0de10fa0cd9e3c6133e36ea4db2b7a49bde9ef019f72796b8e",
    ),
    "pose": (
        "pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
        "64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b",
    ),
    "face": (
        "face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    ),
}
_MODEL_LOCK = threading.Lock()
_MAX_MODEL_BYTES = 64 * 1024 * 1024


def mediapipe_available() -> bool:
    """Legacy installed builds must offer an upgrade, not appear ready to use."""
    try:
        return Version(version("mediapipe")) in SpecifierSet(">=1.0.1,<2")
    except PackageNotFoundError:
        return False


def import_mediapipe() -> Any:
    """Load the optional Tasks runtime after the core platform guard."""
    import mediapipe
    if Version(mediapipe.__version__) not in SpecifierSet(">=1.0.1,<2"):
        raise ImportError(f"Upgrade MediaPipe with {MEDIAPIPE_SPEC}")
    return mediapipe


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_path(name: str) -> Path:
    """Download an official model on first use, verify it, then publish atomically."""
    relative_url, expected_hash = _MODELS[name]
    destination = get_data_paths().model_cache("mediapipe") / relative_url.rsplit("/", 1)[-1]
    temporary: Path | None = None
    try:
        with _MODEL_LOCK:
            if destination.is_file() and _digest(destination) == expected_hash:
                return destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            logger.info("Downloading MediaPipe %s model to %s", name, destination)
            with requests.get(
                "https://storage.googleapis.com/mediapipe-models/" + relative_url,
                stream=True, timeout=(15, 60), allow_redirects=False,
            ) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise RuntimeError(f"MediaPipe model download returned HTTP {response.status_code}")
                with tempfile.NamedTemporaryFile(
                    dir=destination.parent, prefix=destination.name + ".", suffix=".part", delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    size = 0
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        size += len(chunk)
                        if size > _MAX_MODEL_BYTES:
                            raise RuntimeError("MediaPipe model exceeds its download size limit")
                        stream.write(chunk)
            if _digest(temporary) != expected_hash:
                raise RuntimeError("MediaPipe model checksum does not match the verified release")
            os.replace(temporary, destination)
            temporary = None
            logger.info("MediaPipe %s model verified", name)
            return destination
    except Exception:
        logger.exception("Could not prepare MediaPipe %s model", name)
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def image_from_rgb(rgb: np.ndarray) -> Any:
    mp = import_mediapipe()
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb, dtype=np.uint8))


def create_image_segmenter() -> Any:
    mp = import_mediapipe()
    options = mp.tasks.vision.ImageSegmenterOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path("selfie"))),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        output_confidence_masks=True,
        output_category_mask=False,
    )
    return mp.tasks.vision.ImageSegmenter.create_from_options(options)


def create_pose_landmarker() -> Any:
    mp = import_mediapipe()
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path("pose"))),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        output_segmentation_masks=True,
    )
    return mp.tasks.vision.PoseLandmarker.create_from_options(options)


def create_face_landmarker() -> Any:
    mp = import_mediapipe()
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path("face"))),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1,
        min_face_detection_confidence=0.5,
    )
    return mp.tasks.vision.FaceLandmarker.create_from_options(options)
