"""Tests for core/sprite/generation/queue.py (batch queue, G6 retries, G2 cancel)."""
from pathlib import Path

import pytest

from core.sprite.generation import queue as queue_mod
from core.sprite.generation.errors import ProviderError, QuotaExceeded, SafetyRefusal
from core.sprite.generation.queue import BACKOFF_SECONDS, MAX_RETRIES, ActionQueue
from core.sprite.generation.video_route import RenderRequest
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ClipRecord, CostEntry


def _record(req: RenderRequest) -> ClipRecord:
    req.out_mp4.parent.mkdir(parents=True, exist_ok=True)
    req.out_mp4.write_bytes(b"mp4")
    return ClipRecord(path=req.out_mp4, provider=req.settings.provider, model="m",
                      operation_id=f"op-{req.action.id}",
                      params={"duration_s": req.action.duration_s}, prompt=req.action.prompt,
                      generated_at="2026-08-29T10:00:00", estimated_usd=0.4, actual_usd=None)


@pytest.fixture
def harness(monkeypatch, make_project, make_action):
    """Fake render/pipeline seams plus a builder for (project, queue)."""
    state = {"renders": [], "pipelines": [], "sleeps": [], "saves": 0, "logs": [],
             "outcomes": []}

    def fake_render(req, *, api_key, auth_mode, progress, token, log):
        state["renders"].append(req)
        outcome = state["outcomes"].pop(0) if state["outcomes"] else "ok"
        if isinstance(outcome, BaseException):
            raise outcome
        return _record(req)

    def fake_pipeline(project, action, *, upto="pixel", progress=None, token=None, force=False):
        state["pipelines"].append((action.id, upto))
        return {"stabilize": []}

    monkeypatch.setattr(queue_mod, "render_action", fake_render)
    monkeypatch.setattr(queue_mod, "run_pipeline", fake_pipeline)

    def build(actions=None, token=None, **project_kwargs):
        if actions is None:
            actions = [make_action(id="a1", name="walk"), make_action(id="a2", name="run")]
        project = make_project(actions=actions, **project_kwargs)

        def _save(path=None):
            state["saves"] += 1
            return project.project_dir
        project.save = _save
        q = ActionQueue(project, api_key="k", auth_mode="api-key", token=token,
                        log=state["logs"].append)
        q._sleep = state["sleeps"].append
        return project, q

    state["build"] = build
    return state


def test_constants():
    assert BACKOFF_SECONDS == (2.0, 4.0, 8.0) and MAX_RETRIES == 3


def test_enqueue_marks_queued_and_dedupes(harness):
    project, q = harness["build"]()
    q.enqueue(["a1", "a2", "a1"])
    assert q.pending == ["a1", "a2"]
    assert all(a.status == "queued" and a.error is None for a in project.actions)
    with pytest.raises(ValueError):
        q.enqueue(["missing"])


def test_run_renders_in_order_runs_pipeline_and_records_cost(harness):
    project, q = harness["build"]()
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert [r.action.id for r in harness["renders"]] == ["a1", "a2"]
    assert harness["pipelines"] == [("a1", "stabilize"), ("a2", "stabilize")]
    assert set(results) == {"a1", "a2"}
    assert all(isinstance(r, ClipRecord) for r in results.values())
    for action in project.actions:
        assert action.status == "rendered" and action.clip is results[action.id]
        assert action.clip.path == project.project_dir / "clips" / f"{action.id}.mp4"
    assert [e.action_id for e in project.cost_ledger] == ["a1", "a2"]
    assert isinstance(project.cost_ledger[0], CostEntry)
    assert project.cost_ledger[0].estimated_usd == 0.4 and project.cost_ledger[0].actual_usd is None
    assert harness["saves"] == 2 and q.pending == []
    assert harness["renders"][0].plate == project.plate_path


def test_retries_retryable_errors_with_backoff(harness):
    project, q = harness["build"](actions=None)
    harness["outcomes"] = [QuotaExceeded("429"), ProviderError("503", retryable=True), "ok"]
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)
    assert len([r for r in harness["renders"] if r.action.id == "a1"]) == 3
    assert harness["sleeps"] == [2.0, 4.0]
    assert any("retry in 2s" in line for line in harness["logs"])


def test_gives_up_after_max_retries(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [QuotaExceeded("429")] * (MAX_RETRIES + 1)
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], QuotaExceeded)
    assert len(harness["renders"]) == MAX_RETRIES + 1
    assert harness["sleeps"] == list(BACKOFF_SECONDS)
    action = project.actions[0]
    assert action.status == "failed" and action.error == results["a1"].user_message


def test_safety_refusal_never_retried(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [SafetyRefusal("RAI refused; try Veo")]
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert isinstance(results["a1"], SafetyRefusal)
    assert harness["sleeps"] == []
    assert project.actions[0].status == "failed"
    assert project.actions[0].error == "RAI refused; try Veo"
    # The queue continues with the next card.
    assert isinstance(results["a2"], ClipRecord)


def test_non_retryable_provider_error_not_retried(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [ProviderError("bad config")]
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ProviderError) and harness["sleeps"] == []
    assert len(harness["renders"]) == 1


def test_raw_exception_is_classified_and_retried(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [RuntimeError("503 Service Unavailable"), "ok"]
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord) and harness["sleeps"] == [2.0]


def test_cancel_before_run_leaves_actions_queued(harness):
    token = CancelToken()
    token.cancel()
    project, q = harness["build"](token=token)
    q.enqueue(["a1", "a2"])
    assert q.run() == {}
    assert harness["renders"] == []
    assert all(a.status == "queued" for a in project.actions)
    assert q.pending == ["a1", "a2"]


def test_cancel_inside_job_stops_queue_and_keeps_card_reusable(harness):
    token = CancelToken()
    project, q = harness["build"](token=token)
    harness["outcomes"] = [Cancelled("render of 'walk' cancelled; omni operation int-9 keeps running")]
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert set(results) == {"a1"}
    assert isinstance(results["a1"], ProviderError) and results["a1"].retryable is True
    assert "int-9" in results["a1"].user_message
    walk, run = project.actions
    assert walk.status == "draft" and "int-9" in walk.error
    assert run.status == "queued" and q.pending == ["a2"]
    assert harness["saves"] == 1


def test_cancel_during_backoff_stops_before_next_try(harness):
    token = CancelToken()
    project, q = harness["build"](token=token)
    harness["outcomes"] = [QuotaExceeded("429"), "ok"]
    q._sleep = lambda seconds: token.cancel()
    q.enqueue(["a1"])
    results = q.run()
    assert len(harness["renders"]) == 1
    assert isinstance(results["a1"], ProviderError)
    assert project.actions[0].status == "draft"


def test_pipeline_failure_keeps_rendered_status(harness, monkeypatch):
    project, q = harness["build"]()
    def broken_pipeline(project, action, **kw):
        raise RuntimeError("ffmpeg missing")
    monkeypatch.setattr(queue_mod, "run_pipeline", broken_pipeline)
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)
    action = project.actions[0]
    assert action.status == "rendered" and action.error.startswith("pipeline: ffmpeg missing")
    assert any("Pipeline for 'walk' failed" in line for line in harness["logs"])


def test_pipeline_cancel_after_render_keeps_clip(harness, monkeypatch):
    token = CancelToken()
    project, q = harness["build"](token=token)
    def cancelling_pipeline(project, action, **kw):
        raise Cancelled("stage cancelled")
    monkeypatch.setattr(queue_mod, "run_pipeline", cancelling_pipeline)
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)
    assert project.actions[0].status == "rendered" and project.actions[0].clip is not None
    assert q.pending == ["a2"]


def test_missing_plate_fails_without_render(harness):
    project, q = harness["build"](plate=False)
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ProviderError)
    assert "plate" in results["a1"].user_message.lower()
    assert harness["renders"] == [] and project.actions[0].status == "failed"


def test_turnaround_refs_follow_setting(harness):
    project, q = harness["build"](turnaround=True)
    project.generation.use_turnaround_refs = True
    q.enqueue(["a1"])
    q.run()
    assert harness["renders"][0].refs == [project.turnaround["front"], project.turnaround["side"]]
    project.generation.use_turnaround_refs = False
    q.enqueue(["a2"])
    q.run()
    assert harness["renders"][1].refs == []


def test_retry_requeues_failed_action(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [ProviderError("bad")]
    q.enqueue(["a1"])
    q.run()
    assert project.actions[0].status == "failed"
    q.retry("a1")
    assert q.pending == ["a1"] and project.actions[0].status == "queued"
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)


def test_max_concurrent_is_logged_and_ignored(harness):
    project, _ = harness["build"]()
    logs = []
    q = ActionQueue(project, api_key="k", auth_mode="api-key", log=logs.append, max_concurrent=4)
    assert q.max_concurrent == 1
    assert any("max_concurrent" in line for line in logs)
