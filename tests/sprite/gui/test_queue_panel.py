# tests/sprite/gui/test_queue_panel.py
"""QueuePanel: drives ActionQueue in a worker; cost labels; cancel/retry/refine."""
import time
import types
from pathlib import Path

import gui.sprite.queue_panel as qp
from core.sprite.pipeline import Cancelled
from gui.sprite.queue_panel import COL_ACTUAL, COL_ESTIMATE, COL_STATUS, QueuePanel, fmt_usd


class _FakeQueue:
    instances = []

    def __init__(self, project, *, api_key, auth_mode, progress, token, log, max_concurrent=1):
        self.project = project
        self.api_key = api_key
        self.auth_mode = auth_mode
        self.progress = progress
        self.token = token
        self.log = log
        self.ids = []
        _FakeQueue.instances.append(self)

    def enqueue(self, ids):
        self.ids.extend(ids)

    def run(self):
        results = {}
        for cid in self.ids:
            self.log(f"rendering {cid}")
            self.progress("render", 1, 1, cid)
            card = next(c for c in self.project.actions if c.id == cid)
            card.status = "rendered"
            card.clip = types.SimpleNamespace(path=Path(f"{cid}.mp4"), actual_usd=0.12,
                                              provider="omni", model="m")
            results[cid] = card.clip
        return results


class _BlockingQueue(_FakeQueue):
    def run(self):
        while not self.token.cancelled:
            time.sleep(0.005)
        raise Cancelled()


def _panel(fake_config, fake_project, monkeypatch, queue_cls=_FakeQueue):
    monkeypatch.setattr(qp, "ActionQueue", queue_cls)
    monkeypatch.setattr(qp, "estimate_action", lambda settings, card: 0.25)
    monkeypatch.setattr(qp, "estimate_project", lambda project: (0.5, 0))
    panel = QueuePanel(fake_config)
    panel.set_project(fake_project)
    return panel


def test_fmt_usd():
    assert fmt_usd(None) == "unknown" and fmt_usd(0.5) == "$0.50"


def test_rows_show_estimates_and_sheet_total(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project, monkeypatch)
    assert panel.table.rowCount() == 2
    assert panel.table.item(0, COL_ESTIMATE).text() == "$0.25"
    assert panel.table.item(0, COL_ACTUAL).text() == "-"
    assert panel.total_label.text() == "Sheet estimate: $0.50"
    monkeypatch.setattr(qp, "estimate_project", lambda project: (None, 2))
    panel.refresh()
    assert panel.total_label.text() == "Sheet estimate: unknown (2 actions without a verified rate)"


def test_estimator_failure_shows_unknown(qapp, fake_config, fake_project, monkeypatch, caplog):
    def broken(*a, **k):
        raise RuntimeError("no rate")

    panel = _panel(fake_config, fake_project, monkeypatch)
    monkeypatch.setattr(qp, "estimate_action", broken)
    monkeypatch.setattr(qp, "estimate_project", broken)
    with caplog.at_level("WARNING"):
        panel.refresh()
    assert panel.table.item(0, COL_ESTIMATE).text() == "unknown"
    assert "unknown" in panel.total_label.text()


def test_enqueue_marks_cards_queued(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project, monkeypatch)
    panel.enqueue(["a2"])
    assert fake_project.actions[1].status == "queued"
    assert panel.table.item(1, COL_STATUS).text() == "queued"


def test_start_runs_queue_in_worker_and_reports(qapp, fake_config, fake_project, monkeypatch,
                                                wait_for_worker):
    _FakeQueue.instances.clear()
    panel = _panel(fake_config, fake_project, monkeypatch)
    done, lines = [], []
    panel.queueFinished.connect(lambda r: done.append(r))
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    panel.enqueue(["a1"])
    panel.start()
    assert not panel.progress.isHidden()
    wait_for_worker(panel)
    queue = _FakeQueue.instances[-1]
    assert queue.ids == ["a1"] and queue.api_key == "test-key" and queue.auth_mode == "api-key"
    assert done and set(done[0]) == {"a1"}
    assert fake_project.actions[0].status == "rendered"
    assert panel.table.item(0, COL_ACTUAL).text() == "$0.12"
    assert any(level == "SUCCESS" for level, _ in lines)
    assert any("rendering a1" in m for _, m in lines)
    assert panel.progress.isHidden()


def test_start_with_nothing_queued_warns(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project, monkeypatch)
    lines = []
    panel.logMessage.connect(lambda m, level: lines.append(level))
    panel.start()
    assert "WARNING" in lines and panel._worker is None


def test_start_requires_api_key(qapp, fake_project, monkeypatch):
    seen = []
    monkeypatch.setattr(qp, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    config = types.SimpleNamespace(get_api_key=lambda p: None,
                                   get_auth_mode=lambda p="google": "api-key")
    panel = _panel(config, fake_project, monkeypatch)
    panel.enqueue(["a1"])
    panel.start()
    assert seen and "api key" in seen[0].lower() and panel._worker is None


def test_start_refuses_illegal_aspect_before_worker(qapp, fake_config, fake_project, monkeypatch):
    seen = []
    monkeypatch.setattr(qp, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    _FakeQueue.instances.clear()
    fake_project.generation.aspect_ratio = "1:1"   # provider omni: not legal
    panel = _panel(fake_config, fake_project, monkeypatch)
    lines = []
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    panel.enqueue(["a1"])
    panel.start()
    assert len(seen) == 1 and "1:1" in seen[0] and "16:9" in seen[0]
    assert panel._worker is None
    assert _FakeQueue.instances == []
    assert fake_project.actions[0].status == "queued"
    assert ("ERROR", seen[0]) in lines


def test_cancel_stops_queue_without_error_dialog(qapp, fake_config, fake_project, monkeypatch,
                                                 wait_for_worker):
    seen = []
    monkeypatch.setattr(qp, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    panel = _panel(fake_config, fake_project, monkeypatch, queue_cls=_BlockingQueue)
    panel.enqueue(["a1"])
    panel.start()
    assert panel.is_busy()
    panel.cancel()
    wait_for_worker(panel)
    assert seen == []
    assert "cancel" in panel.status_label.text().lower()


def test_retry_requeues_failed_cards(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project, monkeypatch)
    fake_project.actions[0].status = "failed"
    fake_project.actions[0].error = "boom"
    panel.refresh()
    started = []
    monkeypatch.setattr(panel, "start", lambda ids=None: started.append(list(ids or [])))
    panel.table.selectRow(0)
    panel.retry()
    assert fake_project.actions[0].status == "queued" and fake_project.actions[0].error is None
    assert started == [["a1"]]


def test_queue_errors_are_logged_per_card(qapp, fake_config, fake_project, monkeypatch,
                                          wait_for_worker):
    from core.sprite.generation.errors import SpriteGenerationError

    class _Err(SpriteGenerationError):
        def __init__(self, message):
            Exception.__init__(self, message)
            self.user_message = message
            self.retryable = False

    class _ErrQueue(_FakeQueue):
        def run(self):
            card = self.project.actions[0]
            card.status = "failed"
            card.error = "safety refusal"
            return {"a1": _Err("safety refusal")}

    panel = _panel(fake_config, fake_project, monkeypatch, queue_cls=_ErrQueue)
    lines = []
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    panel.enqueue(["a1"])
    panel.start()
    wait_for_worker(panel)
    assert any(level == "ERROR" and "safety refusal" in m for level, m in lines)
    assert panel.table.item(0, COL_STATUS).text() == "failed"


def test_refine_replaces_clip_and_reruns_pipeline(qapp, fake_config, fake_project, monkeypatch,
                                                  wait_for_worker):
    calls = {}
    fake_project.actions[0].clip = types.SimpleNamespace(path=Path("a1.mp4"), actual_usd=0.1)
    new_clip = types.SimpleNamespace(path=Path("a1.r1.mp4"), actual_usd=0.2)

    def fake_refine(clip, instruction, out_mp4, *, api_key, log):
        calls.update(instruction=instruction, out=out_mp4, api_key=api_key)
        return new_clip

    def fake_pipeline(project, action, *, upto, progress, token, force):
        calls.update(upto=upto, force=force, action=action.id)
        return {}

    monkeypatch.setattr(qp, "refine_action", fake_refine)
    monkeypatch.setattr(qp, "run_pipeline", fake_pipeline)
    panel = _panel(fake_config, fake_project, monkeypatch)
    changed = []
    panel.statusChanged.connect(lambda: changed.append(1))
    panel.refine("a1", "make the cape swing")
    wait_for_worker(panel)
    assert calls["instruction"] == "make the cape swing"
    assert calls["out"] == fake_project.project_dir / "clips" / "a1.r1.mp4"
    assert calls["upto"] == "stabilize" and calls["force"] is True and calls["action"] == "a1"
    assert fake_project.actions[0].clip is new_clip
    assert fake_project.actions[0].status == "rendered"
    assert changed


def test_refine_pipeline_failure_keeps_clip_and_records_error(qapp, fake_config, fake_project,
                                                               monkeypatch, wait_for_worker):
    fake_project.actions[0].clip = types.SimpleNamespace(path=Path("a1.mp4"), actual_usd=0.1)
    new_clip = types.SimpleNamespace(path=Path("a1.r1.mp4"), actual_usd=0.2)

    def fake_refine(clip, instruction, out_mp4, *, api_key, log):
        return new_clip

    def fake_pipeline(project, action, *, upto, progress, token, force):
        raise RuntimeError("ffmpeg not found")

    monkeypatch.setattr(qp, "refine_action", fake_refine)
    monkeypatch.setattr(qp, "run_pipeline", fake_pipeline)
    seen_errors = []
    monkeypatch.setattr(qp, "show_error",
                        lambda parent, title, message, exception=None: seen_errors.append(message))
    panel = _panel(fake_config, fake_project, monkeypatch)
    console = []
    panel.logMessage.connect(lambda message, level: console.append((level, message)))
    panel.refine("a1", "make the cape swing")
    wait_for_worker(panel)
    assert fake_project.actions[0].clip is new_clip
    assert fake_project.actions[0].status == "rendered"
    assert fake_project.actions[0].error is not None
    assert fake_project.actions[0].error.startswith("pipeline:")
    assert seen_errors == []  # finished path ran; no error dialog
    # The failure is logged at ERROR (house rule), not reported as SUCCESS.
    assert any(level == "ERROR" and "pipeline: ffmpeg not found" in message
               for level, message in console)
    assert not any(level == "SUCCESS" and "Refined clip ready" in message
                   for level, message in console)
    tooltip = panel.table.item(0, COL_STATUS).toolTip()
    assert tooltip
