"""Sticky Sprite-tab preferences (QSettings) and the purge confirmation.

Every Sprite GUI module reads QSettings through ``sprite_settings()`` so all
keys live under one ``sprite/`` namespace in ``QSettings("ImageAI", "Sprite")``.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox, QWidget

ORGANIZATION = "ImageAI"
APPLICATION = "Sprite"

PURGE_KEY = "sprite/purge_after_export"
LLM_PROVIDER_KEY = "sprite/llm_provider"

PURGE_MESSAGE = (
    "After every export, ImageAI deletes these folders of the current sprite project:\n\n"
    "  • clips/   — the generated video clips and their sidecars\n"
    "  • stages/  — every extracted, keyed, cleaned and resized frame\n\n"
    "The source image, the plate, the turnaround pack, the project file and the "
    "exports stay.\nDeleted files go to the system recycle bin.\n\n"
    "Turn on auto-purge after export?"
)


def sprite_settings() -> QSettings:
    return QSettings(ORGANIZATION, APPLICATION)


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def get_pref(key: str, default: Any = None) -> Any:
    value = sprite_settings().value(key, default)
    return default if value is None else value


def set_pref(key: str, value: Any) -> None:
    settings = sprite_settings()
    settings.setValue(key, value)
    settings.sync()


def purge_after_export_enabled() -> bool:
    return _as_bool(get_pref(PURGE_KEY, False))


def set_purge_after_export(enabled: bool) -> None:
    set_pref(PURGE_KEY, bool(enabled))


def confirm_purge(parent: Optional[QWidget]) -> bool:
    """Ask before the purge preference turns on. Names what gets deleted."""
    reply = QMessageBox.question(
        parent, "Purge intermediates after export?", PURGE_MESSAGE,
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
    )
    return reply == QMessageBox.Yes
