"""Tests for core/sprite/generation/queue.py (batch queue, G6 retries, G2 cancel)."""
import logging
import threading
from pathlib import Path

import pytest

from core.sprite.generation import queue as queue_mod
from core.sprite.generation.errors import ProviderError, QuotaExceeded, SafetyRefusal
from core.sprite.generation.queue import (
    BACKOFF_SECONDS,
    MAX_RETRIES,
    PIPELINE_UPTO,
    ActionQueue,
)
from core.sprite.generation.video_route import RenderRequest
from core.sprite.pipeline import PROFILE_STAGES, STAGES, CancelToken, Cancelled, PipelineError
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


def test_enqueue_is_atomic_on_invalid_id(harness):
    project, q = harness["build"]()
    with pytest.raises(ValueError):
        q.enqueue(["a1", "missing"])
    assert q.pending == []
    assert project.actions[0].status == "draft" and project.actions[0].error is None


def test_run_renders_in_order_runs_pipeline_and_records_cost(harness):
    project, q = harness["build"]()
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert [r.action.id for r in harness["renders"]] == ["a1", "a2"]
    # One run per card, up to stabilize. The queue never runs a profile
    # stage: pixel would lock the project palette from untuned keying.
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
    # The backoff wait sleeps in small slices (interruptible), so the total
    # slept time -- not the call count -- matches the backoff policy.
    assert sum(harness["sleeps"]) == pytest.approx(2.0 + 4.0)
    assert any("retry in 2s" in line for line in harness["logs"])


def test_gives_up_after_max_retries(harness):
    project, q = harness["build"]()
    harness["outcomes"] = [QuotaExceeded("429")] * (MAX_RETRIES + 1)
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], QuotaExceeded)
    assert len(harness["renders"]) == MAX_RETRIES + 1
    # Sliced sleeps; total time still matches the backoff policy.
    assert sum(harness["sleeps"]) == pytest.approx(sum(BACKOFF_SECONDS))
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
    assert isinstance(results["a1"], ClipRecord)
    assert sum(harness["sleeps"]) == pytest.approx(2.0)


def test_cancel_before_run_leaves_actions_queued(harness):
    token = CancelToken()
    token.cancel()
    project, q = harness["build"](token=token)
    q.enqueue(["a1", "a2"])
    assert q.run() == {}
    assert harness["renders"] == []
    assert all(a.status == "queued" for a in project.actions)
    assert q.pending == ["a1", "a2"]


def test_cancel_inside_job_stops_queue_and_requeues_card(harness):
    """I3: a mid-render cancel (no clip yet) puts the card back at the head
    of ``pending`` with status ``"queued"`` instead of dropping it."""
    token = CancelToken()
    project, q = harness["build"](token=token)
    harness["outcomes"] = [Cancelled("render of 'walk' cancelled; omni operation int-9 keeps running")]
    q.enqueue(["a1", "a2"])
    results = q.run()
    assert set(results) == {"a1"}
    assert isinstance(results["a1"], ProviderError) and results["a1"].retryable is True
    assert "int-9" in results["a1"].user_message
    walk, run = project.actions
    assert walk.status == "queued" and "int-9" in walk.error
    assert run.status == "queued"
    # a1 is back at the head of pending -- its original enqueue order --
    # and the "stay queued" count includes it.
    assert q.pending == ["a1", "a2"]
    assert any("2 action(s) stay queued" in line for line in harness["logs"])
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
    assert project.actions[0].status == "queued"
    assert q.pending == ["a1"]


def test_cancel_during_backoff_stops_within_one_slice(harness):
    """A cancel fired mid-wait is seen within one sleep slice, not only after
    the full backoff delay elapses (the wait is interruptible)."""
    token = CancelToken()
    project, q = harness["build"](token=token)
    harness["outcomes"] = [QuotaExceeded("429"), "ok"]

    def fake_sleep(seconds):
        harness["sleeps"].append(seconds)
        token.cancel()

    q._sleep = fake_sleep
    q.enqueue(["a1"])
    results = q.run()
    assert len(harness["renders"]) == 1
    assert isinstance(results["a1"], ProviderError)
    assert project.actions[0].status == "queued"
    assert q.pending == ["a1"]
    assert sum(harness["sleeps"]) < 0.5


def test_pipeline_upto_stops_before_the_profile_stages():
    """The queue stops at stabilize. The pixel stage locks the project-wide
    palette on its first run (core.sprite.pixelart.ensure_palette), so a
    queue-driven run would bake the first card's untuned keying into every
    later card. The Processing panel and the export own the profile stages."""
    assert PIPELINE_UPTO == "stabilize"
    stop = STAGES.index(PIPELINE_UPTO)
    assert not any(stage in STAGES[:stop + 1] for stage in PROFILE_STAGES)


def test_queue_never_runs_a_profile_stage(harness, monkeypatch):
    """One pipeline call per card, and never one that reaches hd or pixel."""
    project, q = harness["build"]()

    def pipeline(project, action, *, upto="pixel", progress=None, token=None, force=False):
        harness["pipelines"].append((action.id, upto))
        assert upto not in PROFILE_STAGES, f"queue ran profile stage {upto!r}"
        action.status = "processed"
        return {"stabilize": [Path("0000.png")]}

    monkeypatch.setattr(queue_mod, "run_pipeline", pipeline)
    q.enqueue(["a1"])
    results = q.run()
    assert isinstance(results["a1"], ClipRecord)
    action = project.actions[0]
    assert action.status == "processed" and action.error is None
    assert harness["pipelines"] == [("a1", "stabilize")]
    assert project.profile("pixel") is None or project.profile("pixel").locked_palette is None


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


def test_enqueue_from_another_thread_while_run_is_mid_job(harness, make_action, monkeypatch):
    """I2 regression: 5a calls ``enqueue`` from the GUI thread while ``run``
    executes on a worker thread. The queue's pending/results/status
    read-modify-write sequences must not corrupt under that interleaving."""
    project, q = harness["build"](actions=[make_action(id="a1", name="walk")])
    started = threading.Event()
    release = threading.Event()

    def blocking_render(req, *, api_key, auth_mode, progress, token, log):
        started.set()
        assert release.wait(timeout=5), "test deadlocked waiting for release"
        return _record(req)

    monkeypatch.setattr(queue_mod, "render_action", blocking_render)

    q.enqueue(["a1"])
    run_results = {}

    def _run():
        run_results.update(q.run())

    runner = threading.Thread(target=_run)
    runner.start()
    assert started.wait(timeout=5), "render did not start on the worker thread"

    # Enqueue a second card from the "GUI thread" while a1 is mid-render.
    project.actions.append(make_action(id="a2", name="run"))
    q.enqueue(["a2"])

    release.set()
    runner.join(timeout=5)
    assert not runner.is_alive(), "worker thread did not finish"

    assert set(run_results) == {"a1", "a2"}
    assert all(isinstance(r, ClipRecord) for r in run_results.values())
    assert project.actions[0].status == "rendered"
    assert project.actions[1].status == "rendered"
    assert q.pending == []
