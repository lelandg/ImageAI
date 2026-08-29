import pytest

from core.sprite.pipeline import (
    STAGE_CODE_VERSION,
    STAGE_RUNNERS,
    STAGE_SETTINGS,
    STAGES,
    UPSTREAM,
    CancelToken,
    Cancelled,
    PipelineError,
    key_stage_settings,
    no_progress,
    register_external_frames,
    register_stage,
    stage_dir,
    stage_fingerprint,
    stage_settings,
)
from core.sprite.project import ActionCard, SpriteProject


def _project(tmp_path):
    project = SpriteProject(name="P")
    project.project_dir = tmp_path / "proj"
    project.project_dir.mkdir()
    action = ActionCard(id="a1", name="walk", prompt="walk")
    project.actions = [action]
    return project, action


@pytest.fixture
def registry():
    """Restore the stage registry after a test that re-registers a stage."""
    saved = (dict(STAGE_RUNNERS), dict(STAGE_SETTINGS), dict(STAGE_CODE_VERSION))
    yield
    for table, copy in zip((STAGE_RUNNERS, STAGE_SETTINGS, STAGE_CODE_VERSION), saved):
        table.clear()
        table.update(copy)


def test_cancel_token_contract():
    token = CancelToken()
    assert not token.cancelled
    token.raise_if_cancelled()
    token.cancel()
    assert token.cancelled
    with pytest.raises(Cancelled):
        token.raise_if_cancelled()
    no_progress("extract", 0, 0, "ok")


def test_stage_order_and_dirs(tmp_path):
    project, action = _project(tmp_path)
    assert STAGES == ("extract", "key", "cleanup", "alpha", "stabilize", "hd", "pixel")
    assert UPSTREAM["pixel"] == "stabilize" and UPSTREAM["hd"] == "stabilize"
    assert stage_dir(project, action, "key") == project.project_dir / "stages" / "a1" / "key"
    with pytest.raises(ValueError):
        stage_dir(project, action, "nope")


def test_every_stage_has_registered_settings_and_a_code_version(tmp_path):
    project, action = _project(tmp_path)
    assert set(STAGE_SETTINGS) == set(STAGES)
    assert set(STAGE_CODE_VERSION) == set(STAGES)
    assert stage_settings(project, action, "key")["key"]["tolerance"] == 0.20
    assert stage_settings(project, action, "extract")["clip"] is None
    with pytest.raises(ValueError):
        stage_settings(project, action, "nope")


def test_fingerprint_changes_only_downstream_of_a_changed_setting(tmp_path):
    project, action = _project(tmp_path)
    before = {s: stage_fingerprint(project, action, s) for s in STAGES}
    project.key.tolerance = 0.5
    after = {s: stage_fingerprint(project, action, s) for s in STAGES}
    assert after["extract"] == before["extract"]
    for stage in ("key", "cleanup", "alpha", "stabilize", "hd", "pixel"):
        assert after[stage] != before[stage], stage
    project.stabilize.pad_px = 4
    later = {s: stage_fingerprint(project, action, s) for s in STAGES}
    assert later["alpha"] == after["alpha"]
    assert later["stabilize"] != after["stabilize"]


def test_register_stage_replaces_settings_and_code_version(tmp_path, registry):
    project, action = _project(tmp_path)
    before = stage_fingerprint(project, action, "key")

    def runner(project, action, input_frames, out_dir, progress, token):
        return []

    register_stage("key", runner, key_stage_settings, code_version=2)
    assert STAGE_RUNNERS["key"] is runner
    assert STAGE_CODE_VERSION["key"] == 2
    assert stage_fingerprint(project, action, "key") != before
    register_stage("key", runner)  # no settings function -> empty settings
    assert stage_settings(project, action, "key") == {}
    with pytest.raises(ValueError):
        register_stage("bogus", runner)


def test_register_external_frames_requires_frames(tmp_path):
    project, action = _project(tmp_path)
    with pytest.raises(PipelineError):
        register_external_frames(project, action)
