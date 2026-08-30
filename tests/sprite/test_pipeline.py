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
    is_stage_current,
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
    # Sub-project 3 re-registers "key" with the real keying settings (flat, not
    # nested under "key" -- see core.sprite.pipeline.key_stage_settings).
    assert stage_settings(project, action, "key")["tolerance"] == 0.20
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

    # Sub-project 3 registers "key" at code_version=2; bump past whatever the
    # current baseline is so this still exercises a genuine version change.
    bumped = STAGE_CODE_VERSION["key"] + 1
    register_stage("key", runner, key_stage_settings, code_version=bumped)
    assert STAGE_RUNNERS["key"] is runner
    assert STAGE_CODE_VERSION["key"] == bumped
    assert stage_fingerprint(project, action, "key") != before
    register_stage("key", runner)  # no settings function -> empty settings
    assert stage_settings(project, action, "key") == {}
    with pytest.raises(ValueError):
        register_stage("bogus", runner)


def test_register_external_frames_requires_frames(tmp_path):
    project, action = _project(tmp_path)
    with pytest.raises(PipelineError):
        register_external_frames(project, action)


def test_a_missing_external_frame_invalidates_the_extract_fingerprint(tmp_path, alpha_frames):
    """M5 regression: a frame removed between runs must change the extract
    settings (so the stage re-runs), not raise a bare OSError."""
    from core.sprite.slicing import import_png_sequence

    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    before = stage_fingerprint(project, action, "extract")
    (stage_dir(project, action, "extract") / "0001.png").unlink()
    after = stage_fingerprint(project, action, "extract")  # must not raise
    assert after != before
    assert not is_stage_current(project, action, "extract")


# --- run_pipeline (Task 10) -------------------------------------------------------
from PIL import Image  # noqa: E402 - grouped with the tests it serves

from core.sprite import keying, pipeline  # noqa: E402
from core.sprite.pipeline import identity_runner, run_pipeline  # noqa: E402
from core.sprite.project import ClipRecord  # noqa: E402
from core.sprite.slicing import import_png_sequence  # noqa: E402


def test_every_stage_has_a_registered_runner():
    """Sub-projects 3 and 4 re-register key/cleanup/alpha and pixel, so this
    test pins only that every stage has a callable runner and that the
    extract runner is this module's."""
    assert set(STAGE_RUNNERS) == set(STAGES)
    assert all(callable(runner) for runner in STAGE_RUNNERS.values())
    assert STAGE_RUNNERS["extract"] is pipeline.extract_runner


def test_missing_input_is_a_pipeline_error(tmp_path):
    project, action = _project(tmp_path)
    with pytest.raises(PipelineError) as info:
        run_pipeline(project, action, upto="extract")
    assert "no clip" in info.value.user_message


def test_pipeline_runs_external_frames_through_hd(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    project.stabilize.pad_px = 2
    project.profiles[0].cell_size = (48, 48)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    events = []
    out = run_pipeline(project, action, upto="hd", progress=lambda *a: events.append(a))
    assert set(out) == {"extract", "key", "cleanup", "alpha", "stabilize", "hd"}
    assert len(out["hd"]) == 12
    with Image.open(out["hd"][0]) as im:
        assert im.size == (48, 48)
    # The moving square spans x 8..98 => union bbox 90 wide, 24 tall, +2 pad each side.
    with Image.open(out["stabilize"][0]) as im:
        assert im.size == (94, 28)
    assert len(action.frames) == 12
    assert action.frames[0].name == "walk_00"
    assert action.frames[0].source_path == out["stabilize"][0]
    assert action.frames[0].duration_ms == round(1000 / 12)
    assert action.status == "processed"
    assert set(project.stage_fingerprints["a1"]) == set(out)
    assert any(e[0] == "stabilize" and e[3].endswith("done") for e in events)
    # I1 regression: hd's per-frame progress must report as "hd", not
    # "stabilize" -- no stabilize event may appear after hd starts running.
    hd_running_at = next(i for i, e in enumerate(events) if e[0] == "hd" and e[3].endswith("running"))
    assert all(e[0] != "stabilize" for e in events[hd_running_at:])
    assert any(e[0] == "hd" and e[3].startswith("hd:") for e in events[hd_running_at:])


def test_hd_runner_honours_upscale_small_and_upscale_method(tmp_path, alpha_frames):
    """M1 regression: hd_runner ignored OutputProfile.upscale_small/upscale_method,
    always upscaling a crop smaller than the hd cell with LANCZOS."""
    from core.sprite.stabilize import union_alpha_bbox

    project, action = _project(tmp_path)
    project.stabilize.pad_px = 0
    project.profiles[0].cell_size = (200, 200)  # far larger than the stabilized crop
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)

    project.profiles[0].upscale_small = False
    out = run_pipeline(project, action, upto="hd")
    with Image.open(out["stabilize"][0]) as stab:
        # No pad_px, so the stabilize crop is the tight union bbox (90x24).
        assert stab.size == (90, 24)
    # upscale_small=False: content across all frames keeps its native
    # (stabilized) footprint instead of being enlarged to fill the cell.
    _, _, w, h = union_alpha_bbox(out["hd"])
    assert (w, h) == (90, 24)

    project.profiles[0].upscale_small = True
    out = run_pipeline(project, action, upto="hd", force=True)
    # upscale_small=True: content is scaled up (one factor for both axes)
    # until it fills the 200x200 cell on at least one axis.
    _, _, w, h = union_alpha_bbox(out["hd"])
    assert w == 200 or h == 200
    assert (w, h) != (90, 24)


def test_imported_frames_without_registration_count_as_extracted(tmp_path, alpha_frames):
    """G9 entry contract: a populated extract dir and no clip means extract is done."""
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    messages = []
    out = run_pipeline(project, action, upto="key", progress=lambda s, d, t, m: messages.append(m))
    assert len(out["extract"]) == 12 and len(out["key"]) == 12
    assert "extract: running" in messages  # the runner accepted the frames as-is
    messages.clear()
    run_pipeline(project, action, upto="key", progress=lambda s, d, t, m: messages.append(m))
    assert messages == ["extract: cached", "key: cached"]


def test_pixel_stage_is_skipped_while_disabled_and_runs_when_enabled(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    project.profiles[1].enabled = False
    out = run_pipeline(project, action)
    assert "pixel" not in out
    project.profiles[1].enabled = True
    out = run_pipeline(project, action)
    assert [p.name for p in out["pixel"]] == [p.name for p in out["stabilize"]]
    assert out["pixel"][0].parent == stage_dir(project, action, "pixel")


def test_identity_runner_copies_inputs_byte_for_byte(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    out = identity_runner(project, action, alpha_frames, tmp_path / "proj" / "stages" / "a1" / "key",
                          no_progress, None)
    assert [p.name for p in out] == [p.name for p in alpha_frames]
    assert out[3].read_bytes() == alpha_frames[3].read_bytes()


def test_cached_stages_are_skipped_and_a_changed_slider_reruns_downstream(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="hd")
    messages = []
    run_pipeline(project, action, upto="hd", progress=lambda s, d, t, m: messages.append(m))
    assert all(m.endswith("cached") for m in messages)
    project.key.tolerance = 0.9
    messages.clear()
    run_pipeline(project, action, upto="hd", progress=lambda s, d, t, m: messages.append(m))
    assert "extract: cached" in messages
    assert "key: running" in messages
    assert "hd: running" in messages


def test_a_replacement_key_runner_changes_output_and_invalidates_downstream(tmp_path, alpha_frames, registry):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="hd")
    before = dict(project.stage_fingerprints["a1"])

    def blue_corner_runner(project, action, input_frames, out_dir, progress, token):
        out = identity_runner(project, action, input_frames, out_dir, progress, token)
        for path in out:
            with Image.open(path) as im:
                rgba = im.convert("RGBA")
            rgba.putpixel((0, 0), (0, 0, 255, 255))
            rgba.save(path)
        return out

    # Sub-project 3 registers "key" at code_version=2; bump past whatever the
    # current baseline is so this still exercises a genuine version change.
    register_stage("key", blue_corner_runner, key_stage_settings,
                   code_version=STAGE_CODE_VERSION["key"] + 1)
    messages = []
    out = run_pipeline(project, action, upto="hd", progress=lambda s, d, t, m: messages.append(m))
    assert "extract: cached" in messages
    for stage in ("key", "cleanup", "alpha", "stabilize", "hd"):
        assert f"{stage}: running" in messages, stage
    with Image.open(out["key"][0]) as im:
        assert im.getpixel((0, 0)) == (0, 0, 255, 255)
    with Image.open(out["cleanup"][0]) as im:
        assert im.getpixel((0, 0)) == (0, 0, 255, 255)  # identity stages carry it forward
    after = project.stage_fingerprints["a1"]
    assert after["extract"] == before["extract"]
    for stage in ("key", "cleanup", "alpha", "stabilize", "hd"):
        assert after[stage] != before[stage], stage


def test_force_reruns_everything_but_never_extract_without_a_clip(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="stabilize")
    messages = []
    run_pipeline(project, action, upto="stabilize", force=True,
                 progress=lambda s, d, t, m: messages.append(m))
    assert "extract: running" in messages and "stabilize: running" in messages
    assert len(pipeline.list_frames(stage_dir(project, action, "extract"))) == 12


def test_sync_frames_keeps_user_edits_by_index(tmp_path, alpha_frames):
    """Per-frame edits survive a re-run and keep the key fingerprint stable."""
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="stabilize")
    action.frames[1].overrides = {"tolerance": 0.95}
    action.frames[2].duration_ms = 250
    action.frames[2].pivot = (0.25, 0.75)
    key_before = stage_fingerprint(project, action, "key")
    project.stabilize.pad_px = 1
    out = run_pipeline(project, action, upto="stabilize")
    assert action.frames[1].overrides == {"tolerance": 0.95}
    assert action.frames[2].duration_ms == 250 and action.frames[2].pivot == (0.25, 0.75)
    assert action.frames[0].overrides == {} and action.frames[0].duration_ms == round(1000 / 12)
    assert action.frames[2].source_path == out["stabilize"][2]
    assert stage_fingerprint(project, action, "key") == key_before
    # A shorter old list: indices beyond it get defaults.
    action.frames = action.frames[:2]
    run_pipeline(project, action, upto="stabilize", force=True)
    assert len(action.frames) == 12
    assert action.frames[1].overrides == {"tolerance": 0.95}
    assert action.frames[2].duration_ms == round(1000 / 12)


def test_a_cleared_frame_list_is_rebuilt_from_a_cached_stabilize_stage(tmp_path, alpha_frames):
    """M6 regression: a project whose action.frames was cleared (or hand-edited)
    must not stay frameless forever just because the stabilize cache is current."""
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="stabilize")
    assert len(action.frames) == 12

    action.frames = []  # simulate a hand-edited project file
    messages = []
    run_pipeline(project, action, upto="stabilize", progress=lambda s, d, t, m: messages.append(m))
    assert "stabilize: cached" in messages and "stabilize: running" not in messages
    assert len(action.frames) == 12
    assert action.frames[0].name == "walk_00"


def test_a_non_empty_frame_list_is_left_alone_by_a_cached_stabilize_stage(tmp_path, alpha_frames):
    """M6: user deletions must survive a cache hit -- only an empty list rebuilds."""
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="stabilize")
    del action.frames[3]  # a user deletion
    assert len(action.frames) == 11
    run_pipeline(project, action, upto="stabilize")
    assert len(action.frames) == 11


def test_cancel_stops_between_frames(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    token = CancelToken()

    def cancel_after_two(stage, done, total, message):
        if stage == "key" and done == 2:
            token.cancel()

    with pytest.raises(Cancelled):
        run_pipeline(project, action, progress=cancel_after_two, token=token)
    assert "key" not in project.stage_fingerprints.get("a1", {})


def test_unregistered_stage_is_a_pipeline_error(tmp_path, alpha_frames, registry):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    del STAGE_RUNNERS["cleanup"]
    with pytest.raises(PipelineError) as info:
        run_pipeline(project, action, upto="cleanup")
    assert "cleanup" in info.value.user_message


def test_pipeline_extracts_from_a_clip(tmp_path, synthetic_mp4):
    project, action = _project(tmp_path)
    project.extraction.mode = "every_n"
    project.extraction.every_n = 4
    action.clip = ClipRecord(path=synthetic_mp4, provider="omni", model="m", operation_id=None, params={},
                             prompt="p", generated_at="t", estimated_usd=None, actual_usd=None)
    out = run_pipeline(project, action, upto="stabilize")
    assert len(out["extract"]) == 3
    assert len(action.frames) == 3


def test_hd_alpha_post_pass_is_skipped_when_binary_alpha_is_off(tmp_path, alpha_frames, monkeypatch):
    """Minor 2 regression: hd's soft-alpha default must not re-encode every
    frame through a no-op apply_profile_alpha."""
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    assert project.profiles[0].binary_alpha is False  # default hd profile keeps soft alpha
    calls = []
    monkeypatch.setattr(keying, "apply_profile_alpha", lambda img, prof: calls.append(1) or img)
    run_pipeline(project, action, upto="hd")
    assert calls == []


def test_hd_alpha_post_pass_runs_and_honours_cancel_with_progress(tmp_path, alpha_frames):
    """Minor 1 regression: the hd alpha post-pass polls the cancel token and
    reports per-frame progress, so a cancel does not wait for the whole pass."""
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    project.profiles[0].binary_alpha = True  # force the hd post-pass to run
    token = CancelToken()
    seen = []

    def watch(stage, done, total, message):
        seen.append((stage, done, total, message))
        if message.startswith("hd: alpha") and done == 2:
            token.cancel()

    with pytest.raises(Cancelled):
        run_pipeline(project, action, upto="hd", progress=watch, token=token)
    alpha_events = [e for e in seen if e[3].startswith("hd: alpha")]
    assert len(alpha_events) == 2, "the post-pass must stop as soon as the token is cancelled"
    assert "hd" not in project.stage_fingerprints.get("a1", {})
