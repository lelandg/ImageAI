"""Sequential action render queue (design §4.2, §1.3, §1.1).

Renders queued cards one at a time with ``render_action``, retries
retryable errors with exponential backoff, never retries a safety refusal,
runs the processing pipeline after each clip, writes a ``CostEntry`` row per
rendered clip, and honors the cancel token between jobs, inside jobs
(through ``render_action``), and during backoff waits.

The post-render pipeline stops at ``PIPELINE_UPTO`` (``stabilize``); a
failure there sets ``action.error``. The queue never runs a profile stage.
The ``pixel`` stage locks the project-wide palette on its first run
(``core.sprite.pixelart.ensure_palette``), so a queue-driven run would lock
the palette from the first card's untuned keying before the user adjusts
anything. The Processing panel runs the profile stages on demand, and the
export runs any missing profile stage through
``core.sprite.pipeline.ensure_profile_stages``.

Thread-safety: ``run()`` is meant to execute on a worker thread (5a's
``SpriteWorker`` QThread) while ``enqueue``/``retry`` are called from the GUI
thread. A ``threading.RLock`` guards every read-modify-write sequence around
``pending``, ``results``, and an action's ``status``/``error``/``clip``
fields; it is never held across a provider call (``render_action``) or a
pipeline run, so a slow render never blocks the GUI thread from enqueuing
more work.

A ``Cancelled`` raised while an action has no clip yet puts the action back
at the head of ``pending`` with ``status = "queued"`` so it is picked up
again automatically; a ``Cancelled`` raised after the clip exists (e.g. the
post-render pipeline stage) leaves the action ``"rendered"`` and does not
re-queue it, since the clip is already saved.
"""
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from core.sprite.generation._common import emit
from core.sprite.generation.cost import record_actual
from core.sprite.generation.errors import (
    ProviderError,
    SafetyRefusal,
    SpriteGenerationError,
    classify_provider_error,
)
from core.sprite.generation.turnaround import VIEWS
from core.sprite.generation.video_route import RenderRequest, render_action
from core.sprite.pipeline import CancelToken, Cancelled, ProgressFn, no_progress, run_pipeline
from core.sprite.project import ActionCard, ClipRecord, SpriteProject

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = (2.0, 4.0, 8.0)
MAX_RETRIES = len(BACKOFF_SECONDS)
PIPELINE_UPTO = "stabilize"  # never a profile stage: pixel locks the project palette
_SLEEP_SLICE = 0.2  # backoff waits sleep in slices this long so a cancel is seen promptly

QueueResult = Dict[str, Union[ClipRecord, SpriteGenerationError]]


class ActionQueue:
    """Render queued action cards for one project."""

    def __init__(self, project: SpriteProject, *, api_key: Optional[str], auth_mode: str,
                 progress: ProgressFn = no_progress, token: Optional[CancelToken] = None,
                 log: Callable[[str], None] = logger.info, max_concurrent: int = 1) -> None:
        self.project = project
        self.api_key = api_key
        self.auth_mode = auth_mode
        self.progress = progress
        self.token = token
        self.log = log
        self.max_concurrent = 1
        if max_concurrent != 1:
            emit(logger, log, f"ActionQueue renders one clip at a time; "
                              f"max_concurrent={max_concurrent} is ignored")
        self.pending: List[str] = []
        self.results: QueueResult = {}
        self._sleep: Callable[[float], None] = time.sleep
        self._lock = threading.RLock()

    # -- lookup / requests ---------------------------------------------------

    def _action(self, action_id: str) -> ActionCard:
        for action in self.project.actions:
            if action.id == action_id:
                return action
        raise ValueError(f"No action with id {action_id!r} in project {self.project.name!r}")

    def clip_path(self, action: ActionCard) -> Path:
        """``<project_dir>/clips/<action_id>.mp4`` (design §1.6)."""
        if self.project.project_dir is None:
            raise ProviderError("Save the project before rendering so the clips folder has a home.")
        return Path(self.project.project_dir) / "clips" / f"{action.id}.mp4"

    def build_request(self, action: ActionCard) -> RenderRequest:
        plate = self.project.plate_path
        if not plate or not Path(plate).exists():
            raise ProviderError("Make the chroma plate before rendering (Character panel > Make chroma plate).")
        settings = self.project.generation
        refs: List[Path] = []
        if settings.use_turnaround_refs:
            refs = [Path(self.project.turnaround[view]) for view in VIEWS
                    if view in self.project.turnaround]
        return RenderRequest(action=action, plate=Path(plate), refs=refs,
                             settings=settings, out_mp4=self.clip_path(action))

    # -- queue operations ----------------------------------------------------

    def enqueue(self, action_ids: Sequence[str]) -> None:
        # Look up every id first so an unknown id raises before anything is
        # mutated: enqueue([valid, invalid]) leaves the valid card untouched.
        actions = [self._action(action_id) for action_id in action_ids]
        with self._lock:
            for action_id, action in zip(action_ids, actions):
                action.status = "queued"
                action.error = None
                self.results.pop(action_id, None)
                if action_id not in self.pending:
                    self.pending.append(action_id)
            names = ", ".join(self._action(i).name for i in self.pending)
            count = len(self.pending)
        emit(logger, self.log, f"Queue: {count} action(s) queued: {names}")

    def retry(self, action_id: str) -> None:
        self.enqueue([action_id])

    def _cancelled(self) -> bool:
        return self.token is not None and self.token.cancelled

    def _pop_next(self) -> Optional[Tuple[str, ActionCard]]:
        """Atomically check-cancel and pop the next pending id, if any.

        Runs under the lock so a concurrent ``enqueue`` from another thread
        can never interleave with the pop/status-set sequence.
        """
        with self._lock:
            if self._cancelled():
                emit(logger, self.log, f"Queue cancelled; {len(self.pending)} action(s) stay queued",
                     level="warning")
                return None
            if not self.pending:
                return None
            action_id = self.pending.pop(0)
            action = self._action(action_id)
            action.status = "rendering"
            action.error = None
            return action_id, action

    def run(self) -> QueueResult:
        """Render every pending card in order. Returns results for cards it touched."""
        while True:
            popped = self._pop_next()
            if popped is None:
                break
            action_id, action = popped
            try:
                # Provider call and pipeline run happen with the lock released
                # so a slow render never blocks a concurrent enqueue().
                record = self._render_with_retries(action)
                with self._lock:
                    action.clip = record
                    action.status = "rendered"
                entry = record_actual(self.project, action, None, note="rendered")
                emit(logger, self.log, f"Cost: '{action.name}' estimated ${entry.estimated_usd} "
                                       f"({entry.seconds:.0f}s {entry.provider}/{entry.model})")
                with self._lock:
                    self.results[action_id] = record
                self._post_process(action)
            except Cancelled as exc:
                requeue_count: Optional[int] = None
                with self._lock:
                    if action.clip is None:
                        # No clip yet: put the card back where it can be
                        # picked up again instead of dropping it silently.
                        action.status = "queued"
                        action.error = f"cancelled: {exc}"
                        self.pending.insert(0, action_id)
                        self.results[action_id] = ProviderError(
                            f"Render of '{action.name}' was cancelled. {exc}", retryable=True)
                        requeue_count = len(self.pending)
                    else:
                        # The clip already exists (e.g. cancelled during the
                        # post-render pipeline stage); nothing to re-queue.
                        action.error = f"cancelled after render: {exc}"
                if requeue_count is not None:
                    emit(logger, self.log, f"Queue cancelled; {requeue_count} action(s) stay queued",
                         level="warning")
                else:
                    emit(logger, self.log, f"Queue stopped: {exc}", level="warning")
                self._save()
                break
            except SpriteGenerationError as err:
                with self._lock:
                    action.status = "failed"
                    action.error = err.user_message
                    self.results[action_id] = err
                emit(logger, self.log, f"'{action.name}' failed: {err.user_message}", level="error")
            self._save()
        with self._lock:
            return dict(self.results)

    # -- internals -----------------------------------------------------------

    def _render_with_retries(self, action: ActionCard) -> ClipRecord:
        request = self.build_request(action)
        attempt = 0
        while True:
            attempt += 1
            try:
                return render_action(request, api_key=self.api_key, auth_mode=self.auth_mode,
                                     progress=self.progress, token=self.token, log=self.log)
            except Cancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - classified below
                err = classify_provider_error(exc, provider=request.settings.provider)
                if isinstance(err, SafetyRefusal) or not err.retryable or attempt > MAX_RETRIES:
                    if err is exc:
                        raise
                    raise err from exc
                delay = BACKOFF_SECONDS[attempt - 1]
                emit(logger, self.log, f"'{action.name}' attempt {attempt} failed "
                                       f"({err.user_message}); retry in {delay:.0f}s",
                     level="warning")
                self._wait_or_cancel(delay, action)

    def _wait_or_cancel(self, delay: float, action: ActionCard) -> None:
        """Sleep ``delay`` seconds in ``_SLEEP_SLICE`` slices.

        Checks the cancel token after every slice so a cancel fired during a
        long backoff wait is seen within one slice instead of only after the
        full delay elapses.
        """
        remaining = delay
        while remaining > 1e-9:
            self._sleep(min(_SLEEP_SLICE, remaining))
            remaining -= _SLEEP_SLICE
            if self._cancelled():
                raise Cancelled(f"cancelled while waiting to retry '{action.name}'")

    def _post_process(self, action: ActionCard) -> None:
        """Run the pipeline up to ``PIPELINE_UPTO`` (stabilize); a failure marks the card."""
        try:
            outputs = run_pipeline(self.project, action, upto=PIPELINE_UPTO,
                                   progress=self.progress, token=self.token)
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - the clip is safe; report and continue
            action.error = f"pipeline: {exc}"
            emit(logger, self.log, f"Pipeline for '{action.name}' failed after render: {exc}. "
                                   f"The clip is saved; run the pipeline again from the "
                                   f"processing panel.", level="error")
            return
        stages = ", ".join(outputs) or "none"
        emit(logger, self.log, f"Frames ready for '{action.name}' (stages: {stages})")

    def _save(self) -> None:
        if self.project.project_dir is None:
            return
        try:
            self.project.save()
        except Exception as exc:  # noqa: BLE001 - never lose a rendered clip over a save error
            emit(logger, self.log, f"Could not save the project: {exc}", level="warning")
