"""CLI generation lifecycle tests: fake cloud boundaries, real local media stages."""
import copy
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from cli.commands import sprite_generation as generation
from core.sprite.generation.action_cards import ActionCardDraft
from core.sprite.generation.errors import ProviderError
from core.sprite.models import FrameMeta
from core.sprite.pipeline import Cancelled, CancelToken, is_stage_current, run_pipeline, stage_dir
from core.sprite.project import ActionCard, BackgroundSettings, ClipRecord, SpriteProject


@pytest.fixture
def project(tmp_path):
    project = SpriteProject("Generation tests", tmp_path / "project")
    project.project_dir.mkdir()
    project.character_source = tmp_path / "character.png"
    Image.new("RGBA", (80, 48), "#142536").save(project.character_source)
    project.background = BackgroundSettings(mode="original")
    project.actions = [ActionCard("a1", "think", "the character thinks", target_frames=3)]
    project.save()
    return project


def execute(operation, project, data=None, **kwargs):
    return generation.execute_generation(operation, project, data or {}, log=kwargs.get("log", lambda _: None),
                                         progress=lambda *_: None, token=kwargs.get("token", CancelToken()))


def fake_sheet(provider, source, action, out, *, frames, **kwargs):
    sheet = Image.new("RGBA", (frames * 48, 48), "#123456")
    draw = ImageDraw.Draw(sheet)
    for frame in range(frames):
        x = frame * 48
        draw.rectangle((x + 10, 8 + frame, x + 34, 40), fill="#f1cb55")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    out.with_suffix(".json").write_text(json.dumps({"route": "test", "prompt": action.prompt}))
    return out


@pytest.fixture
def fake_images(monkeypatch):
    monkeypatch.setattr(generation, "_image_provider", lambda *_: (object(), "google", "mock-image"))
    monkeypatch.setattr(generation.image_route, "generate_sheet", fake_sheet)


def test_selector_rejects_unknown_duplicate_and_ambiguous(project):
    with pytest.raises(ValueError, match="exactly one"):
        generation.select_actions(project, single=True)
    with pytest.raises(ValueError, match="Unknown"):
        generation.select_actions(project, ["think", "missing"])
    with pytest.raises(ValueError, match="Repeated"):
        generation.select_actions(project, ["think", "a1"])
    project.actions.append(ActionCard("a2", "think", "the character rests"))
    with pytest.raises(ValueError, match="Ambiguous"):
        generation.select_actions(project, ["think"])
    assert generation.select_actions(project, ["a2"]) == [project.actions[1]]


def test_sheet_runs_real_pipeline_and_saves_reloadable_frames(project, fake_images):
    result = execute("render", project, {"route": "sheet", "actions": ["think"]})
    restored = SpriteProject.load(project.project_file())
    action = restored.actions[0]
    assert action.status == "processed"
    assert len(action.frames) == 3
    assert is_stage_current(restored, action, "stabilize")
    assert all(frame.source_path.is_file() for frame in action.frames)
    assert all("candidates" not in str(frame.source_path) for frame in action.frames)
    assert len(result["files"]) == 4
    assert restored.cost_ledger[-1].seconds == 1  # one sheet call, not three edits
    assert restored.cost_ledger[-1].provider == "google"


def test_failed_rerender_keeps_accepted_bytes_frames_and_fingerprints(project, fake_images, monkeypatch):
    execute("render", project, {"route": "sheet"})
    before_frames = copy.deepcopy(project.actions[0].frames)
    before_bytes = [frame.source_path.read_bytes() for frame in before_frames]
    before_fingerprints = copy.deepcopy(project.stage_fingerprints)

    def fail(*args, **kwargs):
        raise RuntimeError("provider failed")

    monkeypatch.setattr(generation.image_route, "generate_sheet", fail)
    with pytest.raises(RuntimeError, match="provider failed"):
        execute("render", project, {"route": "sheet"})
    assert project.actions[0].frames == before_frames
    assert [frame.source_path.read_bytes() for frame in before_frames] == before_bytes
    assert project.stage_fingerprints == before_fingerprints
    assert project.actions[0].status == "failed"
    assert len(project.cost_ledger) == 1


def test_pipeline_failure_retains_old_stage_tree_and_accounts_new_sheet(project, fake_images, monkeypatch):
    execute("render", project, {"route": "sheet"})
    old_frames = copy.deepcopy(project.actions[0].frames)
    old_bytes = [frame.source_path.read_bytes() for frame in old_frames]

    def fail(*args, **kwargs):
        raise RuntimeError("processing failed")

    monkeypatch.setattr(generation, "run_pipeline", fail)
    with pytest.raises(RuntimeError, match="processing failed"):
        execute("render", project, {"route": "sheet"})
    assert project.actions[0].frames == old_frames
    assert [frame.source_path.read_bytes() for frame in old_frames] == old_bytes
    assert len(project.cost_ledger) == 2


def test_rerender_archives_accepted_stage_tree_and_invalidates_profiles(project, fake_images):
    execute("render", project, {"route": "sheet"})
    action = project.actions[0]
    run_pipeline(project, action, upto="hd")
    previous = action.frames[0].source_path.read_bytes()
    result = execute("render", project, {"route": "sheet", "frames": 2})
    archive = Path(result["actions"][0]["archive"])
    assert archive.is_dir()
    assert (archive / "stabilize" / action.frames[0].source_path.name).read_bytes() == previous
    assert not stage_dir(project, action, "hd").exists()
    assert len(action.frames) == 2


def test_partial_edit_chain_accounts_successes_and_retains_old_animation(project, fake_images, monkeypatch):
    execute("render", project, {"route": "sheet"})
    frames_before = copy.deepcopy(project.actions[0].frames)

    def partial(provider, source, action, out, **kwargs):
        out.mkdir(parents=True)
        Image.new("RGBA", (48, 48), "red").save(out / "0001.png")
        raise RuntimeError("second edit failed")

    monkeypatch.setattr(generation.image_route, "edit_chain", partial)
    with pytest.raises(RuntimeError, match="second edit failed"):
        execute("render", project, {"route": "edit-chain"})
    assert project.actions[0].frames == frames_before
    assert project.cost_ledger[-1].seconds == 1
    assert "partial" in project.cost_ledger[-1].note


def test_all_explicit_steps_validate_before_paid_call(project, fake_images, monkeypatch):
    calls = []
    monkeypatch.setattr(generation, "_image_provider", lambda *_: calls.append(True))
    with pytest.raises(ValueError, match="3 nonempty strings"):
        execute("render", project, {"route": "edit-chain", "pose_instructions": ["one"]})
    assert calls == []


def test_cards_append_by_default_and_replace_only_when_explicit(project, monkeypatch):
    monkeypatch.setattr(generation, "_chat_settings", lambda *_: {})
    monkeypatch.setattr(generation.action_cards, "generate_action_cards", lambda *_, **kw: [
        ActionCardDraft("orbit", "the character orbits", 2, True, 8, 12)])
    execute("cards", project, {"brief": "A curious satellite"})
    assert [action.name for action in project.actions] == ["think", "orbit"]
    execute("cards", project, {"replace": True})
    assert [action.name for action in project.actions] == ["orbit"]


def test_estimate_image_routes_are_explicitly_unknown_dollars(project):
    result = execute("estimate", project, {"route": "sheet"})
    assert result["actions"][0]["image_calls"] == 1
    assert result["unknown_count"] == 1
    assert project.cost_ledger == []


def test_cancel_before_operation_makes_no_changes(project, fake_images):
    before = project.to_dict()
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        execute("render", project, {"route": "sheet"}, token=token)
    assert project.to_dict() == before


def test_logs_redact_core_provider_exception_before_file_logger(project, fake_images, monkeypatch, caplog):
    def fail(*_, **kwargs):
        import logging
        logging.getLogger("core.sprite.generation.image_route").error("failed api_key=private-test-value")
        raise RuntimeError("failed api_key=private-test-value")

    logs = []
    monkeypatch.setattr(generation.image_route, "generate_sheet", fail)
    with pytest.raises(RuntimeError, match=r"api_key=\*\*\*"):
        execute("render", project, {"route": "sheet"}, log=logs.append)
    assert "private-test-value" not in caplog.text
    assert "private-test-value" not in "\n".join(logs)
    assert "private-test-value" not in project.actions[0].error


def test_loop_trim_uses_real_ffmpeg_and_preserves_input(project, synthetic_mp4):
    project.actions[0].clip = ClipRecord.from_dict({"path": str(synthetic_mp4), "provider": "import",
                                                  "params": {"duration_s": 0.5}})
    original = synthetic_mp4.read_bytes()
    result = execute("loop-trim", project, {"actions": ["think"]})
    assert Path(result["clip"]).is_file()
    assert synthetic_mp4.read_bytes() == original
    assert len(project.actions[0].frames) > 0
    assert 0 <= result["seam_score"] <= 1


def test_refine_requires_single_omni_clip_before_call(project):
    with pytest.raises(ValueError, match="exactly one"):
        execute("refine", project, {"instruction": "Improve loop"})
    with pytest.raises(ValueError, match="no video clip"):
        execute("refine", project, {"actions": ["think"], "instruction": "Improve loop"})


def test_baked_rgba_survives_forced_chroma_cleanup_and_preserves_metadata(project, tmp_path):
    import numpy as np
    project.background.mode = "transparent"
    project.key.key_color = "#00FF00"
    project.key.choke_px = 2
    project.key.feather_px = 2
    project.stabilize.pad_px = 0
    rgba = Image.new("RGBA", (16, 16), (0, 255, 0, 128))
    source = tmp_path / "accepted.png"
    rgba.save(source)
    frame = FrameMeta("edited", source, (0, 0, 16, 16), duration_ms=230,
                      pivot=(0.3, 0.7), overrides={"tolerance": 0.9, "key_color": "#123456"})
    generation.bake_working_frames(project, project.actions[0], [frame], progress=lambda *_: None,
                                    token=CancelToken())
    restored = SpriteProject.load(project.project_file())
    action = restored.actions[0]
    assert action.frames[0].overrides == {"baked_rgba": True}
    assert action.frames[0].duration_ms == 230
    assert action.frames[0].pivot == (0.3, 0.7)
    run_pipeline(restored, action, upto="stabilize", force=True)
    with Image.open(action.frames[0].source_path) as saved:
        assert np.array_equal(np.asarray(saved), np.asarray(rgba))


def test_retouch_real_core_region_neighbors_single_attempt_and_durable_export(project, fake_images, monkeypatch):
    from io import BytesIO
    from core.sprite.exporters.gif import export_gif

    execute("render", project, {"route": "sheet"})
    originals = [frame.source_path.read_bytes() for frame in project.actions[0].frames]
    calls = []

    class Provider:
        def edit_image_region(self, original, region, prompt, **kwargs):
            calls.append((region, prompt))
            with Image.open(BytesIO(original)) as image:
                edited = image.convert("RGBA")
            draw = ImageDraw.Draw(edited)
            x, y, w, h = region
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill="#f01066")
            buf = BytesIO()
            edited.save(buf, "PNG")
            return ["Retouched the requested area."], [buf.getvalue()]

    monkeypatch.setattr(generation, "_image_provider", lambda *_: (Provider(), "google", "mock-image"))
    result = execute("retouch", project, {"actions": ["think"], "frame": 1,
                      "instruction": "Make this pink", "region": [0, 0, 10, 10]})
    assert len(calls) == 1
    assert "neighboring" not in calls[0][1]  # Google region edits cannot carry neighbors
    archive = Path(result["archive"])
    assert [p.read_bytes() for p in sorted((archive / "stabilize").glob("*.png"))] == originals
    action = project.actions[0]
    assert all(f.overrides["baked_rgba"] for f in action.frames)
    run_pipeline(project, action, upto="hd", force=True)
    meta = project.sheet_meta("hd")
    out = project.project_dir / "test.gif"
    export_gif(meta, meta.tags[0], out)
    assert out.is_file()
    assert project.cost_ledger[-1].seconds == 1


def test_retouch_rejects_invalid_region_before_provider(project, fake_images, monkeypatch):
    execute("render", project, {"route": "sheet"})
    calls = []
    monkeypatch.setattr(generation, "_image_provider", lambda *_: calls.append(True))
    with pytest.raises(ValueError, match="fit inside"):
        execute("retouch", project, {"actions": ["think"], "instruction": "Red", "region": [0, 0, 999, 999]})
    assert calls == []


def test_promotion_rolls_back_on_save_failure(project, fake_images, monkeypatch):
    execute("render", project, {"route": "sheet"})
    action = project.actions[0]
    frames_before = copy.deepcopy(action.frames)
    bytes_before = [f.source_path.read_bytes() for f in frames_before]
    candidate, card = generation._candidate(project, action)
    extract = stage_dir(candidate, card, "extract")
    extract.mkdir(parents=True)
    source = extract / "0001.png"
    Image.new("RGBA", (16, 16), "pink").save(source)
    card.frames = generation._frames([source], card)

    def fail():
        raise OSError("disk full")

    monkeypatch.setattr(project, "save", fail)
    with pytest.raises(OSError, match="disk full"):
        generation._promote(project, action, candidate, card)
    assert action.frames == frames_before
    assert [f.source_path.read_bytes() for f in action.frames] == bytes_before
    assert source.is_file()


def test_plate_and_turnaround_use_core_sidecars_and_checkpoint_views(project, monkeypatch):
    from io import BytesIO
    from core.utils import sidecar_path
    calls = []

    class Provider:
        def edit_image(self, source, prompt, model, **kwargs):
            calls.append((source, prompt, model, kwargs))
            image = Image.new("RGBA", (80, 48), "#00FF00")
            ImageDraw.Draw(image).rectangle((20, 10, 50, 40), fill="red")
            buf = BytesIO()
            image.save(buf, "PNG")
            return ["Completed."], [buf.getvalue()]

    monkeypatch.setattr(generation, "_image_provider", lambda *_: (Provider(), "google", "mock-image"))
    plate_result = execute("plate", project)
    assert calls[0][0] == project.character_source
    assert sidecar_path(Path(plate_result["plate"])).is_file()
    result = execute("turnaround", project, {"views": ["front", "side"], "do_not_change": ["antenna"]})
    assert set(result["turnaround"]) == {"front", "side"}
    assert all(sidecar_path(Path(path)).is_file() for path in result["files"])
    restored = SpriteProject.load(project.project_file())
    assert set(restored.turnaround) == {"front", "side"}
    assert len(restored.cost_ledger) == 3


def test_video_render_passes_saved_settings_and_calls_provider_once(project, monkeypatch, synthetic_mp4):
    import shutil
    calls = []
    monkeypatch.setattr(generation, "_credentials", lambda *_: (None, "api-key"))
    monkeypatch.setattr(generation.video_route, "validate_generation_settings", lambda *_: None)

    def render(request, **kwargs):
        calls.append(request)
        shutil.copy2(synthetic_mp4, request.out_mp4)
        return ClipRecord.from_dict({"path": str(request.out_mp4), "provider": "omni", "model": "mock-video",
                                     "params": {"duration_s": 1}})

    monkeypatch.setattr(generation.video_route, "render_action", render)
    result = execute("render", project, {"route": "video"})
    assert len(calls) == 1
    assert calls[0].settings == project.generation
    assert calls[0].background_mode == "original"
    assert project.actions[0].clip.path.is_file()
    assert project.actions[0].status == "processed"
    assert result["actions"][0]["frames"] > 0
    assert project.cost_ledger[-1].provider == "omni"


def test_rejected_retouch_keeps_accepted_frames_and_records_completed_call(project, fake_images, monkeypatch):
    execute("render", project, {"route": "sheet"})
    before = copy.deepcopy(project.actions[0].frames)
    calls = []

    class Provider:
        def edit_image(self, references, prompt, **kwargs):
            calls.append(True)
            return [], [references[0]]  # unchanged image must fail validation

    monkeypatch.setattr(generation, "_image_provider", lambda *_: (Provider(), "google", "mock-image"))
    with pytest.raises(ProviderError, match="no visible change after 1"):
        execute("retouch", project, {"actions": ["think"], "instruction": "Make it clearer"})
    assert len(calls) == 1
    assert project.actions[0].frames == before
    assert project.cost_ledger[-1].seconds == 1
    assert "incomplete" in project.cost_ledger[-1].note


def test_retouch_cannot_bake_unapplied_key_overrides(project, fake_images, monkeypatch):
    execute("render", project, {"route": "sheet"})
    project.background.mode = "transparent"
    project.actions[0].frames[0].overrides["tolerance"] = 0.4
    calls = []
    monkeypatch.setattr(generation, "_image_provider", lambda *_: calls.append(True))
    with pytest.raises(ValueError, match="current key settings"):
        execute("retouch", project, {"actions": ["think"], "instruction": "Make it clearer"})
    assert calls == []
    assert project.actions[0].frames[0].overrides["tolerance"] == 0.4


def test_sheet_uses_sampled_muted_border_and_reports_actual_pose_count(project, fake_images, monkeypatch):
    project.background.mode = "transparent"

    def six_poses(provider, source, action, out, **kwargs):
        image = Image.new("RGBA", (600, 100), "#7BBD73")
        draw = ImageDraw.Draw(image)
        for column in range(6):
            x = column * 100
            draw.rectangle((x + 20, 15, x + 75, 85), fill="#233454")
        image.save(out)
        return out

    monkeypatch.setattr(generation.image_route, "generate_sheet", six_poses)
    result = execute("render", project, {"route": "sheet", "frames": 8})
    grid = result["actions"][0]["sheet_grid"]
    assert grid["sampled_key_color"] == "#7BBD73"
    assert grid["requested_frames"] == 8
    assert grid["actual_frames"] == 6
    assert grid["confidence"] == 1
    assert grid["layout_verified"] is True
    assert len(grid["warnings"]) == 2
    assert len(project.actions[0].frames) == 6
    assert project.actions[0].target_frames == 6
    assert project.cost_ledger[-1].seconds == 1


def test_ambiguous_sheet_is_preserved_without_replacing_accepted_frames(project, fake_images, monkeypatch):
    execute("render", project, {"route": "sheet"})
    accepted = copy.deepcopy(project.actions[0].frames)
    accepted_bytes = [frame.source_path.read_bytes() for frame in accepted]
    project.background.mode = "transparent"
    saved = []

    def ambiguous(provider, source, action, out, **kwargs):
        Image.new("RGBA", (120, 80), "#7BBD73").save(out)
        saved.append(out)
        return out

    monkeypatch.setattr(generation.image_route, "generate_sheet", ambiguous)
    with pytest.raises(ProviderError, match="Sheet grid is ambiguous.*Saved sheet"):
        execute("render", project, {"route": "sheet"})
    assert saved[0].is_file()
    assert project.actions[0].frames == accepted
    assert [frame.source_path.read_bytes() for frame in accepted] == accepted_bytes
    assert project.cost_ledger[-1].seconds == 1


def test_sheet_rejects_equal_cell_cuts_through_offset_figures(project, fake_images, monkeypatch):
    project.background.mode = "transparent"

    def offset(provider, source, action, out, **kwargs):
        image = Image.new("RGBA", (300, 100), "#7BBD73")
        draw = ImageDraw.Draw(image)
        for x in (40, 100, 160):
            draw.rectangle((x, 20, x + 20, 80), fill="red")
        image.save(out)
        return out

    monkeypatch.setattr(generation.image_route, "generate_sheet", offset)
    with pytest.raises(ProviderError, match="would cut foreground pixels"):
        execute("render", project, {"route": "sheet"})
    assert project.actions[0].frames == []


@pytest.mark.parametrize("kind", ["provider", "pipeline", "ffmpeg", "io", "invalid", "unexpected"])
def test_dispatch_preserves_redacted_generation_error_exit_codes(project, monkeypatch, capsys, kind):
    from types import SimpleNamespace
    from cli.commands.sprite import run_sprite_cmd
    from core.sprite.extract import FFmpegError
    from core.sprite.pipeline import PipelineError

    errors = {"provider": ProviderError, "pipeline": PipelineError, "ffmpeg": FFmpegError,
              "io": OSError, "invalid": ValueError, "unexpected": TypeError}

    def fail(*_, **kwargs):
        raise errors[kind]("failure api_key=private-review-token")

    monkeypatch.setattr(generation, "_render", fail)
    args = SimpleNamespace(sprite="render", sprite_data=None, sprite_name=None, sprite_source=None,
                           sprite_project=str(project.project_file()), sprite_root=None, json=True)
    expected = 2 if kind == "invalid" else 3 if kind == "unexpected" else 1
    assert run_sprite_cmd(args) == expected
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["exit_code"] == expected
    assert "private-review-token" not in captured.out + captured.err
    assert result["error"] == "failure api_key=***"


def test_empty_bake_keeps_original_archive_and_cannot_resurrect_deleted_frames(project, fake_images):
    from core.sprite.pipeline import PipelineError
    execute("render", project, {"route": "sheet"})
    action = project.actions[0]
    baked = generation.bake_working_frames(project, action, [], progress=lambda *_: None, token=CancelToken())
    assert Path(baked["archive"]).is_dir()
    assert len(baked["previous_frames"]) == 3
    assert all(frame.source_path.is_file() for frame in baked["previous_frames"])
    assert action.frames == []
    assert action.clip is None
    assert action.status == "draft"
    with pytest.raises(PipelineError, match="no clip and no imported frames"):
        run_pipeline(project, action, upto="stabilize", force=True)
    assert action.frames == []
