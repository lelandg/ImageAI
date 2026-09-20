"""Tasks API regression coverage without loading models or downloading assets."""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from PIL import Image

import core.mediapipe_tasks as tasks
from core.character_animator import segmenter as segmenter_module
from core.character_animator.segmenter import BodyPartSegmenter


@pytest.fixture
def task_models(monkeypatch):
    pose_points = [
        SimpleNamespace(x=i / 40, y=i / 50, z=-i / 100, visibility=0.9)
        for i in range(33)
    ]
    face_points = [
        SimpleNamespace(x=i / 500, y=i / 600, z=-i / 1000)
        for i in range(478)
    ]
    pose = Mock()
    pose.detect.return_value = SimpleNamespace(pose_landmarks=[pose_points])
    face = Mock()
    face.detect.return_value = SimpleNamespace(face_landmarks=[face_points])
    make_pose = Mock(return_value=pose)
    make_face = Mock(return_value=face)
    wrapped_image = object()
    wrap = Mock(return_value=wrapped_image)
    monkeypatch.setattr(segmenter_module, "POSE_DETECTION_AVAILABLE", True)
    monkeypatch.setattr(segmenter_module, "SEGMENTATION_AVAILABLE", False)
    monkeypatch.setattr(tasks, "create_pose_landmarker", make_pose)
    monkeypatch.setattr(tasks, "create_face_landmarker", make_face)
    monkeypatch.setattr(tasks, "image_from_rgb", wrap)
    return SimpleNamespace(
        pose=pose, face=face, make_pose=make_pose, make_face=make_face,
        wrap=wrap, wrapped_image=wrapped_image,
    )


def test_pose_uses_tasks_and_preserves_pixel_coordinates_and_visibility(task_models):
    segmenter = BodyPartSegmenter()
    image = Image.new("RGBA", (200, 100), (10, 20, 30, 50))

    landmarks = segmenter.detect_pose(image)

    assert landmarks.shape == (33, 4)
    np.testing.assert_allclose(landmarks[10], [50, 20, -0.1, 0.9])
    task_models.pose.detect.assert_called_once_with(task_models.wrapped_image)
    pixels = task_models.wrap.call_args.args[0]
    assert pixels.shape == (100, 200, 3)
    assert pixels.dtype == np.uint8
    np.testing.assert_array_equal(pixels[0, 0], [10, 20, 30])


def test_face_uses_first_tasks_face_and_preserves_iris_landmarks(task_models):
    segmenter = BodyPartSegmenter()
    # Multiple results must not merge into a single face.
    task_models.face.detect.return_value.face_landmarks.append([])

    landmarks = segmenter.detect_face(Image.new("L", (200, 100), 30))

    assert landmarks.shape == (478, 3)
    np.testing.assert_allclose(landmarks[477], [190.8, 79.5, -0.477])
    task_models.face.detect.assert_called_once_with(task_models.wrapped_image)
    pixels = task_models.wrap.call_args.args[0]
    assert pixels.shape == (100, 200, 3)
    np.testing.assert_array_equal(pixels[0, 0], [30, 30, 30])


@pytest.mark.parametrize("kind", ["pose", "face"])
def test_empty_tasks_results_return_none(task_models, kind):
    model = getattr(task_models, kind)
    setattr(model.detect.return_value, f"{kind}_landmarks", [])
    segmenter = BodyPartSegmenter()

    assert getattr(segmenter, f"detect_{kind}")(Image.new("RGB", (20, 10))) is None


def test_segment_body_parts_preserves_regions_and_polygon_mask(task_models):
    segmenter = BodyPartSegmenter()
    image = Image.new("RGB", (200, 100))

    result = segmenter.segment_body_parts(image)

    assert result.original_image is image
    assert result.pose_landmarks.shape == (33, 4)
    assert result.face_landmarks.shape == (478, 3)
    assert result.torso_bbox is not None
    assert result.left_arm_bbox is not None
    assert result.right_arm_bbox is not None
    assert result.head_bbox is not None
    assert result.head_mask.shape == (100, 200)
    assert result.head_mask.dtype == np.uint8
    assert result.head_mask.max() == 255
    assert result.mouth_region.name == "mouth"
    assert result.left_eye_region.name == "left_eye"
    assert result.right_eye_region.name == "right_eye"
    task_models.make_pose.assert_called_once_with()
    task_models.make_face.assert_called_once_with()


def test_partial_initialization_failure_closes_pose_and_allows_retry(task_models):
    segmenter = BodyPartSegmenter()
    task_models.make_face.side_effect = RuntimeError("face model failed")

    assert segmenter.initialize() is False
    task_models.pose.close.assert_called_once_with()
    assert segmenter._mp_pose is None
    assert segmenter._mp_face_mesh is None
    assert segmenter._initialized is False

    task_models.make_face.side_effect = None
    assert segmenter.initialize() is True
    assert task_models.make_pose.call_count == 2


def test_cleanup_releases_both_tasks_even_when_pose_close_fails(task_models, caplog):
    segmenter = BodyPartSegmenter()
    assert segmenter.initialize() is True
    task_models.pose.close.side_effect = RuntimeError("close failed")

    segmenter.cleanup()
    segmenter.cleanup()

    task_models.pose.close.assert_called_once_with()
    task_models.face.close.assert_called_once_with()
    assert segmenter._mp_pose is None
    assert segmenter._mp_face_mesh is None
    assert segmenter._initialized is False
    assert "Failed to close MediaPipe task _mp_pose" in caplog.text


def test_partial_initialization_cleanup_failure_does_not_mask_failure(task_models):
    segmenter = BodyPartSegmenter()
    task_models.make_face.side_effect = RuntimeError("face model failed")
    task_models.pose.close.side_effect = RuntimeError("close failed")

    assert segmenter.initialize() is False
    assert segmenter._mp_pose is None
    assert segmenter._mp_face_mesh is None
