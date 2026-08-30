"""Named generation configurations for the Sprite tab (design decision 9, §1.6).

One JSON file under the Settings root — ``get_data_paths().sprite_configs()`` —
holds every named ``GenerationSettings``. The "Default" entry always exists:
the user may overwrite it, never delete it. Pure Python (no Qt) so the CLI
reads the same file.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from core.paths import get_data_paths
from core.sprite.project import GenerationSettings

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
DEFAULT_NAME = "Default"


def settings_to_dict(settings: GenerationSettings) -> dict:
    return dataclasses.asdict(settings)


def settings_from_dict(data: Optional[dict], *, name: Optional[str] = None) -> GenerationSettings:
    """Build settings from a dict. Unknown keys are dropped; missing keys keep defaults."""
    known = {f.name for f in dataclasses.fields(GenerationSettings)}
    kwargs = {k: v for k, v in (data or {}).items() if k in known}
    if name is not None:
        kwargs["config_name"] = name
    return GenerationSettings(**kwargs)


class NamedConfigStore:
    """Read/write named GenerationSettings in one JSON document."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path is not None else get_data_paths().sprite_configs()

    @property
    def path(self) -> Path:
        return self._path

    # -- persistence -------------------------------------------------------

    def _read(self) -> Dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.error("Sprite config store unreadable (%s): %s", self._path, exc)
            return {}
        configs = document.get("configs") if isinstance(document, dict) else None
        return {str(k): dict(v) for k, v in configs.items() if isinstance(v, dict)} \
            if isinstance(configs, dict) else {}

    def _write(self, configs: Dict[str, dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps({"version": FORMAT_VERSION, "configs": configs}, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self._path)

    # -- API ---------------------------------------------------------------

    def list_names(self) -> List[str]:
        names = set(self._read().keys())
        names.discard(DEFAULT_NAME)
        return [DEFAULT_NAME] + sorted(names)

    def get(self, name: str) -> GenerationSettings:
        configs = self._read()
        if name in configs:
            return settings_from_dict(configs[name], name=name)
        if name == DEFAULT_NAME:
            return GenerationSettings(config_name=DEFAULT_NAME)
        raise KeyError(name)

    def save(self, name: str, settings: GenerationSettings) -> None:
        name = (name or "").strip()
        if not name:
            raise ValueError("A configuration needs a name.")
        configs = self._read()
        data = settings_to_dict(settings)
        data["config_name"] = name
        configs[name] = data
        self._write(configs)
        logger.info("Saved sprite generation configuration %r", name)

    def delete(self, name: str) -> None:
        if name == DEFAULT_NAME:
            raise ValueError('The "Default" configuration cannot be deleted.')
        configs = self._read()
        if name not in configs:
            raise KeyError(name)
        del configs[name]
        self._write(configs)
        logger.info("Deleted sprite generation configuration %r", name)
