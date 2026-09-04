import json
import uuid
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite import keying, pipeline
from core.sprite.models import FrameMeta
from core.sprite.project import ActionCard, SpriteProject
from tests.sprite.keying_fixtures import disc_on_field, write_png

CENTERS = [(30.0, 24.0), (32.0, 24.0), (34.0, 24.0), (33.0, 23.0)]


def _project(tmp_path: Path) -> SpriteProject:
    project = SpriteProject(name="keytest", project_dir=tmp_path / "proj")
    project.plate_color = "#00C800"
    return project


def _action() -> ActionCard:
    return ActionCard(id=uuid.uuid4().hex, name="walk", prompt="walk cycle")


def _seed_extract(project: SpriteProject, action: ActionCard) -> list:
    """Pretend the extract stage ran: write frames and record its fingerprint (design §1.2)."""
    out = pipeline.stage_dir(project, action, "extract")
    paths = []
    for i, c in enumerate(CENTERS):
        rgb, _cov = disc_on_field(center=c)
        paths.append(write_png(out / f"{i + 1:04d}.png", rgb))
    project.stage_fingerprints.setdefault(action.id, {})["extract"] = \
        pipeline.stage_fingerprint(project, action, "extract")
    action.frames = [FrameMeta(name=f"walk_{i:02d}", source_path=p, frame=(0, 0, 0, 0))
                     for i, p in enumerate(paths)]
    project.actions.append(action)
    return paths


def _rgba(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"))


def test_key_cleanup_alpha_stages_produce_keyed_rgba(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    result = pipeline.run_pipeline(project, action, upto="alpha")
    for stage in ("key", "cleanup", "alpha"):
        assert len(result[stage]) == len(CENTERS)
        assert [p.name for p in result[stage]] == [f"{i + 1:04d}.png" for i in range(len(CENTERS))]
    _rgb, cov = disc_on_field(center=CENTERS[0])
    out = _rgba(result["alpha"][0])
    assert out[cov == 0][:, 3].max() == 0
    assert out[cov == 1][:, 3].min() == 255
    assert tuple(out[24, 30, :3]) == (220, 40, 40)


def test_per_frame_override_changes_only_that_frame(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    action.frames[1].overrides = {"tolerance": 0.95}
    result = pipeline.run_pipeline(project, action, upto="key")
    assert _rgba(result["key"][0])[:, :, 3].max() == 255
    assert _rgba(result["key"][1])[:, :, 3].max() == 0
    assert _rgba(result["key"][2])[:, :, 3].max() == 255


def test_changed_override_changes_the_key_fingerprint(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    before = pipeline.stage_fingerprint(project, action, "key")
    action.frames[1].overrides = {"softness": 0.3}
    assert pipeline.stage_fingerprint(project, action, "key") != before
    settings = pipeline.STAGE_SETTINGS["key"](project, action)
    assert settings["overrides"][1] == {"softness": 0.3}
    assert settings["key_color"] == "auto"   # sampled from the clip at run time


def test_cleanup_settings_change_only_cleanup_and_later(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    key_fp = pipeline.stage_fingerprint(project, action, "key")
    cleanup_fp = pipeline.stage_fingerprint(project, action, "cleanup")
    project.key.choke_px = 2
    assert pipeline.stage_fingerprint(project, action, "key") == key_fp
    assert pipeline.stage_fingerprint(project, action, "cleanup") != cleanup_fp


def test_choke_shrinks_the_cleanup_alpha(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    plain = pipeline.run_pipeline(project, action, upto="cleanup")
    plain_sum = int(_rgba(plain["cleanup"][0])[:, :, 3].sum())
    project.key.choke_px = 2
    choked = pipeline.run_pipeline(project, action, upto="cleanup")
    assert int(_rgba(choked["cleanup"][0])[:, :, 3].sum()) < plain_sum


def test_stabilize_settings_include_dejitter_flags(tmp_path):
    project = _project(tmp_path)
    action = _action()
    settings = pipeline.STAGE_SETTINGS["stabilize"](project, action)
    assert settings["stabilize"]["dejitter"] is True and settings["stabilize"]["dejitter_method"] == "phase"


def test_stabilize_dejitters_when_enabled(tmp_path):
    from tests.sprite.keying_fixtures import centroid
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    project.stabilize.dejitter = True
    project.stabilize.dejitter_method = "centroid"
    result = pipeline.run_pipeline(project, action, upto="stabilize")
    cents = [centroid(_rgba(p)[:, :, 3].astype(np.float32) / 255.0) for p in result["stabilize"]]
    for c in cents[1:]:
        assert abs(c[1] - cents[0][1]) < 0.6 and abs(c[0] - cents[0][0]) < 0.6
    project.stabilize.dejitter = False
    result2 = pipeline.run_pipeline(project, action, upto="stabilize")
    cents2 = [centroid(_rgba(p)[:, :, 3].astype(np.float32) / 255.0) for p in result2["stabilize"]]
    assert max(abs(c[1] - cents2[0][1]) for c in cents2[1:]) > 1.0


def test_overrides_survive_the_stabilize_frame_sync(tmp_path):
    """run_pipeline rebuilds action.frames after stabilize (_sync_frames); user edits must survive."""
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    action.frames[1].overrides = {"tolerance": 0.95}
    action.frames[2].duration_ms = 250
    first = pipeline.run_pipeline(project, action, upto="stabilize")
    assert action.frames[1].overrides == {"tolerance": 0.95}
    assert action.frames[2].duration_ms == 250
    assert action.frames[1].source_path == first["stabilize"][1]
    # A second run sees the same overrides, so the key stage is still current (no re-run).
    key_fp = project.stage_fingerprints[action.id]["key"]
    pipeline.run_pipeline(project, action, upto="stabilize")
    assert project.stage_fingerprints[action.id]["key"] == key_fp
    assert _rgba(first["key"][1])[:, :, 3].max() == 0


def test_hd_profile_keeps_soft_alpha_unless_binary_requested(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    hd = next(p for p in project.profiles if p.name == "hd")
    assert hd.binary_alpha is False
    soft = pipeline.run_pipeline(project, action, upto="hd")
    values = set(np.unique(_rgba(soft["hd"][0])[:, :, 3]).tolist())
    assert values - {0, 255}, "hd must keep the anti-aliased edge"
    hd.binary_alpha = True
    hard = pipeline.run_pipeline(project, action, upto="hd")
    assert set(np.unique(_rgba(hard["hd"][0])[:, :, 3]).tolist()) <= {0, 255}


def test_stage_code_versions_were_bumped():
    for stage in ("key", "cleanup", "alpha", "stabilize", "hd"):
        assert pipeline.STAGE_CODE_VERSION[stage] >= 2, stage


def test_bad_plate_color_raises_keying_error_not_a_bare_value_error(tmp_path, caplog):
    """I1 regression: a bad key colour reaching ``run_pipeline`` (here via a
    typo'd plate colour) must surface as ``KeyingError`` with a ``user_message``
    and a logged line, not an un-logged bare ``ValueError``."""
    project = _project(tmp_path)
    project.plate_color = "not-a-color"
    action = _action()
    _seed_extract(project, action)
    with caplog.at_level("ERROR"):
        with pytest.raises(keying.KeyingError) as info:
            pipeline.run_pipeline(project, action, upto="alpha")
    assert info.value.user_message
    assert "not-a-color" in caplog.text


def test_bad_tolerance_override_raises_keying_error_through_the_key_stage(tmp_path, caplog):
    """I1 regression: apply_overrides' float() cast on a bad per-frame override
    must not leak a bare ValueError out of run_pipeline either."""
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    action.frames[1].overrides = {"tolerance": "not-a-number"}
    with caplog.at_level("ERROR"):
        with pytest.raises(keying.KeyingError) as info:
            pipeline.run_pipeline(project, action, upto="key")
    assert info.value.user_message
    assert "not-a-number" in caplog.text


def test_alpha_runner_rejects_a_bad_key_color_override(tmp_path, caplog):
    """I1 regression at the pipeline.py:405 boundary specifically: alpha_runner's
    own hex parse must raise KeyingError, not a bare ValueError."""
    project = _project(tmp_path)
    action = _action()
    paths = _seed_extract(project, action)
    action.frames[0].overrides = {"key_color": "rgb(0,200,0)"}
    with caplog.at_level("ERROR"):
        with pytest.raises(keying.KeyingError) as info:
            pipeline.alpha_runner(project, action, paths, pipeline.stage_dir(project, action, "alpha"),
                                  pipeline.no_progress, None)
    assert info.value.user_message
    assert "rgb(0,200,0)" in caplog.text


def _seed_extract_field(project: SpriteProject, action: ActionCard, field) -> list:
    """Like ``_seed_extract`` but with a flat (no gradient) field of ``field`` color."""
    out = pipeline.stage_dir(project, action, "extract")
    paths = []
    for i, c in enumerate(CENTERS):
        rgb, _cov = disc_on_field(center=c, field=field, gradient=False)
        paths.append(write_png(out / f"{i + 1:04d}.png", rgb))
    project.stage_fingerprints.setdefault(action.id, {})["extract"] = \
        pipeline.stage_fingerprint(project, action, "extract")
    action.frames = [FrameMeta(name=f"walk_{i:02d}", source_path=p, frame=(0, 0, 0, 0))
                     for i, p in enumerate(paths)]
    project.actions.append(action)
    return paths


def test_key_stage_warns_when_the_key_color_is_not_in_the_clip(tmp_path, caplog):
    """T9: a wrong key color removes almost nothing; the key stage says so and
    names the color it sampled from the clip. The alpha result does not change."""
    project = _project(tmp_path)
    project.plate_color = "#00FF00"
    project.key.key_color = "#00FF00"   # explicit: auto sampling would key this clip
    action = _action()
    _seed_extract_field(project, action, field=(118, 188, 103))
    reports = []
    with caplog.at_level("WARNING", logger="core.sprite.pipeline"):
        result = pipeline.run_pipeline(project, action, upto="key",
                                       progress=lambda s, d, t, m: reports.append((s, m)))
    warnings = [r for r in caplog.records if r.levelname == "WARNING" and "Key color" in r.getMessage()]
    assert len(warnings) == 1
    text = warnings[0].getMessage()
    assert "#00FF00" in text and "#76BC67" in text
    assert "Keying settings" in text
    # The runner reports the warning last, after every per-frame line, so the
    # per-frame lines do not overwrite it. Only run_pipeline's "done" follows.
    key_reports = [m for s, m in reports if s == "key"]
    assert "#76BC67" in key_reports[-2] and key_reports[-1] == "key: done"
    assert all("#76BC67" not in m for m in key_reports[:-2])
    # Warning only: the key result stays as the wrong key produced it (nothing removed).
    assert _rgba(result["key"][0])[:, :, 3].min() == 255


def test_key_stage_stays_silent_when_the_key_color_matches_the_clip(tmp_path, caplog):
    project = _project(tmp_path)
    project.plate_color = "#00FF00"
    action = _action()
    _seed_extract_field(project, action, field=(0, 255, 0))
    with caplog.at_level("WARNING", logger="core.sprite.pipeline"):
        result = pipeline.run_pipeline(project, action, upto="key")
    assert not [r for r in caplog.records if r.levelname == "WARNING" and "Key color" in r.getMessage()]
    assert _rgba(result["key"][0])[:, :, 3].min() == 0


def test_key_stage_samples_the_clip_when_no_key_color_is_set(tmp_path, caplog):
    """Out of the box: the plate asked for #00FF00, the clip came back #89C55F.
    The key stage samples the clip border, keys on that, and says so."""
    project = _project(tmp_path)
    project.plate_color = "#00FF00"
    assert project.key.key_color is None
    action = _action()
    _seed_extract_field(project, action, field=(137, 197, 95))
    reports = []
    with caplog.at_level("INFO", logger="core.sprite.pipeline"):
        result = pipeline.run_pipeline(project, action, upto="alpha",
                                       progress=lambda s, d, t, m: reports.append((s, m)))
    keyed = _rgba(result["key"][0])
    assert keyed[0, 0, 3] == 0 and keyed[-1, -1, 3] == 0      # the field is gone
    assert keyed[24, 32, 3] == 255                             # the disc stays
    assert not [r for r in caplog.records if r.levelname == "WARNING" and "removed" in r.getMessage()]
    sampled = [r.getMessage() for r in caplog.records if "#89C55F" in r.getMessage()]
    assert sampled and "#00FF00" in sampled[0]
    assert any("#89C55F" in m for s, m in reports if s == "key")
    report = json.loads((pipeline.stage_dir(project, action, "key") / "key.json").read_text())
    assert report["key_color"] == "#89C55F" and report["auto"] is True
    # The alpha stage decontaminates against the same sampled color and keeps the result.
    final = _rgba(result["alpha"][0])
    assert final[0, 0, 3] == 0 and final[24, 32, 3] == 255


def test_key_stage_falls_back_to_the_plate_color_when_the_border_is_not_one_color(tmp_path, caplog):
    project = _project(tmp_path)
    project.plate_color = "#00FF00"
    action = _action()
    out = pipeline.stage_dir(project, action, "extract")
    rng = np.random.default_rng(3)
    paths = [write_png(out / f"{i + 1:04d}.png", rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8))
             for i in range(2)]
    project.stage_fingerprints.setdefault(action.id, {})["extract"] = \
        pipeline.stage_fingerprint(project, action, "extract")
    action.frames = [FrameMeta(name=f"walk_{i:02d}", source_path=p, frame=(0, 0, 0, 0))
                     for i, p in enumerate(paths)]
    project.actions.append(action)
    with caplog.at_level("WARNING", logger="core.sprite.pipeline"):
        pipeline.run_pipeline(project, action, upto="key")
    texts = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("not one color" in t and "#00FF00" in t for t in texts)
    report = json.loads((pipeline.stage_dir(project, action, "key") / "key.json").read_text())
    assert report["key_color"] == "#00FF00" and report["auto"] is False


def test_explicit_key_color_is_not_overridden_by_sampling(tmp_path):
    project = _project(tmp_path)
    project.plate_color = "#00FF00"
    project.key.key_color = "#00FF00"
    action = _action()
    _seed_extract_field(project, action, field=(137, 197, 95))
    result = pipeline.run_pipeline(project, action, upto="key")
    assert _rgba(result["key"][0])[:, :, 3].min() == 255   # wrong explicit key removes nothing
    report = json.loads((pipeline.stage_dir(project, action, "key") / "key.json").read_text())
    assert report["key_color"] == "#00FF00" and report["auto"] is False
