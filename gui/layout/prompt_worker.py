"""Worker thread for per-region AI image-prompt suggestions.

Mirrors ``DesignerWorker``: when a ``completion_fn`` is injected (tests) the
caller runs it synchronously via ``run()``; in production the LayoutTab calls
``start()`` so the LLM call never blocks the GUI thread.
"""
import logging
from typing import Callable, Dict, List

from PySide6.QtCore import QThread, Signal

from core.layout import prompt_helper

logger = logging.getLogger("imageai.layout.prompt_worker")


class PromptSuggestWorker(QThread):
    suggested = Signal(str, str)  # (region_id, prompt)
    failed = Signal(str, str)     # (region_id, error)

    def __init__(self, region_id: str, messages: List[Dict[str, str]],
                 completion_fn: Callable[[List[Dict[str, str]]], str], parent=None):
        super().__init__(parent)
        self._region_id = region_id
        self._messages = messages
        self._completion_fn = completion_fn

    def run(self):
        try:
            prompt = prompt_helper.run_prompt_help(self._messages, self._completion_fn)
            self.suggested.emit(self._region_id, prompt)
        except Exception as e:  # noqa: BLE001 - surfaced to UI + log
            logger.error("Prompt-suggest worker failed: %s", e, exc_info=True)
            self.failed.emit(self._region_id, str(e))
