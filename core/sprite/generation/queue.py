"""Sequential action render queue (design §4.2, §1.3, §1.1).

Renders queued cards one at a time with ``render_action``, retries
retryable errors with exponential backoff, never retries a safety refusal,
runs the processing pipeline up to ``stabilize`` after each clip, writes a
``CostEntry`` row per rendered clip, and honors the cancel token between
jobs, inside jobs (through ``render_action``), and during backoff waits.
"""
import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Union

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
PIPELINE_UPTO = "stabilize"

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
        for action_id in action_ids:
            action = self._action(action_id)
            action.status = "queued"
            action.error = None
            self.results.pop(action_id, None)
            if action_id not in self.pending:
                self.pending.append(action_id)
        names = ", ".join(self._action(i).name for i in self.pending)
        emit(logger, self.log, f"Queue: {len(self.pending)} action(s) queued: {names}")

    def retry(self, action_id: str) -> None:
        self.enqueue([action_id])

    def _cancelled(self) -> bool:
        return self.token is not None and self.token.cancelled

    def run(self) -> QueueResult:
        """Render every pending card in order. Returns results for cards it touched."""
        while self.pending:
            if self._cancelled():
                emit(logger, self.log, f"Queue cancelled; {len(self.pending)} action(s) stay queued",
                     level="warning")
                break
            action_id = self.pending.pop(0)
            action = self._action(action_id)
            action.status = "rendering"
            action.error = None
            try:
                record = self._render_with_retries(action)
                action.clip = record
                action.status = "rendered"
                entry = record_actual(self.project, action, None, note="rendered")
                emit(logger, self.log, f"Cost: '{action.name}' estimated ${entry.estimated_usd} "
                                       f"({entry.seconds:.0f}s {entry.provider}/{entry.model})")
                self.results[action_id] = record
                self._post_process(action)
            except Cancelled as exc:
                if action.clip is None:
                    action.status = "draft"
                    action.error = f"cancelled: {exc}"
                    self.results[action_id] = ProviderError(
                        f"Render of '{action.name}' was cancelled. {exc}", retryable=True)
                else:
                    action.error = f"cancelled after render: {exc}"
                emit(logger, self.log, f"Queue stopped: {exc}", level="warning")
                self._save()
                break
            except SpriteGenerationError as err:
                action.status = "failed"
                action.error = err.user_message
                self.results[action_id] = err
                emit(logger, self.log, f"'{action.name}' failed: {err.user_message}", level="error")
            self._save()
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
                self._sleep(delay)
                if self._cancelled():
                    raise Cancelled(f"cancelled while waiting to retry '{action.name}'")

    def _post_process(self, action: ActionCard) -> None:
        try:
            run_pipeline(self.project, action, upto=PIPELINE_UPTO,
                         progress=self.progress, token=self.token)
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - the clip is safe; report and continue
            action.error = f"pipeline: {exc}"
            emit(logger, self.log, f"Pipeline for '{action.name}' failed after render: {exc}. "
                                   f"The clip is saved; run the pipeline again from the "
                                   f"processing panel.", level="error")
        else:
            emit(logger, self.log, f"Frames ready for '{action.name}' "
                                   f"(pipeline up to '{PIPELINE_UPTO}')")

    def _save(self) -> None:
        if self.project.project_dir is None:
            return
        try:
            self.project.save()
        except Exception as exc:  # noqa: BLE001 - never lose a rendered clip over a save error
            emit(logger, self.log, f"Could not save the project: {exc}", level="warning")
