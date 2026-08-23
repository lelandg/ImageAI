"""A storage move relocates project media; stored absolute paths must heal.

The migrator moves the whole ``video_projects`` tree to the new root, but
``project.iaproj.json`` records absolute paths from the old root. ``load``
must re-anchor every stored media path against the directory the project
file actually sits in, so the GUI finds the images and clips again.
"""

import shutil
from pathlib import Path

from core.video.project import (
    AudioTrack,
    ImageVariant,
    ReferenceImage,
    Scene,
    VideoProject,
)


def _write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _build_project(project_dir: Path) -> VideoProject:
    """Create a project whose media all live inside project_dir."""
    project = VideoProject(name="Move Me")
    project.project_dir = project_dir

    scene = Scene(source="line one", prompt="a prompt")
    scene.images = [
        ImageVariant(
            path=_write(project_dir / "images" / "scene_0000" / "v1.png"),
            provider="gemini",
            model="m",
        )
    ]
    scene.approved_image = _write(project_dir / "images" / "scene_0000" / "v1.png")
    scene.video_clip = _write(project_dir / "clips" / "scene_0000.mp4")
    scene.first_frame = _write(project_dir / "first_frames" / "scene_0000.png")
    scene.last_frame = _write(project_dir / "frames" / "scene_0000_last.png")
    scene.end_frame = _write(project_dir / "images" / "scene_0000" / "end.png")
    scene.end_frame_images = [
        ImageVariant(
            path=_write(project_dir / "images" / "scene_0000" / "end_v1.png"),
            provider="gemini",
            model="m",
        )
    ]
    scene.reference_images = [
        ReferenceImage(path=_write(project_dir / "references" / "ref1.png"))
    ]
    project.scenes = [scene]

    project.global_reference_images = [
        ReferenceImage(path=_write(project_dir / "references" / "global1.png"))
    ]
    project.extracted_frames = [
        {
            "path": str(_write(project_dir / "extracted_frames" / "f1.png")),
            "timestamp_sec": 1.0,
            "video_source": str(project_dir / "clips" / "scene_0000.mp4"),
            "extracted_at": "2026-08-23T12:00:00",
        }
    ]
    return project


def _move_video_projects(old_root: Path, new_root: Path) -> None:
    """Do what the migrator does: relocate the tree, leave the JSON alone."""
    shutil.move(str(old_root / "video_projects"), str(new_root / "video_projects"))


def test_load_reanchors_media_after_storage_move(tmp_path):
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    project_dir = old_root / "video_projects" / "Move_Me_20260801_120000"
    project_dir.mkdir(parents=True)

    project = _build_project(project_dir)
    project.save()

    _move_video_projects(old_root, new_root)
    new_dir = new_root / "video_projects" / "Move_Me_20260801_120000"

    loaded = VideoProject.load(new_dir / "project.iaproj.json")
    scene = loaded.scenes[0]

    assert scene.approved_image == new_dir / "images" / "scene_0000" / "v1.png"
    assert scene.approved_image.exists()
    assert scene.video_clip == new_dir / "clips" / "scene_0000.mp4"
    assert scene.video_clip.exists()
    assert scene.first_frame.exists()
    assert scene.last_frame.exists()
    assert scene.end_frame.exists()
    assert scene.images[0].path.exists()
    assert scene.end_frame_images[0].path.exists()
    assert scene.reference_images[0].path.exists()
    assert loaded.global_reference_images[0].path.exists()

    frame = loaded.extracted_frames[0]
    assert Path(frame["path"]).exists()
    assert Path(frame["video_source"]).exists()


def test_load_keeps_paths_that_still_exist(tmp_path):
    """A reachable external file (e.g. the audio track) is left alone."""
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    project_dir = old_root / "video_projects" / "Proj_20260801_120000"
    project_dir.mkdir(parents=True)

    external_audio = _write(tmp_path / "music" / "song.mp3")

    project = _build_project(project_dir)
    project.audio_tracks = [AudioTrack(file_path=external_audio)]
    project.save()

    _move_video_projects(old_root, new_root)
    new_dir = new_root / "video_projects" / "Proj_20260801_120000"

    loaded = VideoProject.load(new_dir / "project.iaproj.json")
    assert loaded.audio_tracks[0].file_path == external_audio


def test_load_keeps_unresolvable_paths_unchanged(tmp_path):
    """A missing path with no counterpart under the new dir is not invented."""
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    project_dir = old_root / "video_projects" / "Proj_20260801_120000"
    project_dir.mkdir(parents=True)

    gone = tmp_path / "elsewhere" / "deleted.mp3"

    project = _build_project(project_dir)
    project.audio_tracks = [AudioTrack(file_path=gone)]
    project.save()

    _move_video_projects(old_root, new_root)
    new_dir = new_root / "video_projects" / "Proj_20260801_120000"

    loaded = VideoProject.load(new_dir / "project.iaproj.json")
    assert loaded.audio_tracks[0].file_path == gone


def test_load_reanchors_after_project_dir_rename(tmp_path):
    """A renamed project folder still heals via the video_projects segment."""
    old_root = tmp_path / "old"
    project_dir = old_root / "video_projects" / "Old_Name_20260801_120000"
    project_dir.mkdir(parents=True)

    project = _build_project(project_dir)
    project.save()

    renamed = old_root / "video_projects" / "New_Name"
    shutil.move(str(project_dir), str(renamed))

    loaded = VideoProject.load(renamed / "project.iaproj.json")
    scene = loaded.scenes[0]
    assert scene.video_clip == renamed / "clips" / "scene_0000.mp4"
    assert scene.video_clip.exists()
