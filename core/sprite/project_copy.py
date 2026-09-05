"""Create an independent, named copy of a Sprite project and its media."""
import copy
import logging
import shutil
from dataclasses import fields, is_dataclass
from pathlib import Path

from .project import SpriteProject, SpriteProjectManager

logger = logging.getLogger(__name__)


def copy_project(project: SpriteProject, name: str,
                 manager: SpriteProjectManager) -> SpriteProject:
    """Keep internal media references inside the copy; retain external references."""
    if project.project_dir is None:
        raise ValueError("Save the original project before making a copy.")
    source = project.project_dir.resolve()
    created = manager.create_project(name)
    assert created.project_dir is not None
    destination = created.project_dir.resolve()
    try:
        if destination.is_relative_to(source):
            raise ValueError("The project library cannot be inside the source project.")
        for item in source.iterdir():
            if item.name in (project.project_file().name, ".sprite-cli.lock"):
                continue
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

        def relocate(value):
            if isinstance(value, Path):
                try:
                    return destination / value.resolve().relative_to(source)
                except ValueError:
                    return value
            if is_dataclass(value) and not isinstance(value, type):
                for field in fields(value):
                    setattr(value, field.name, relocate(getattr(value, field.name)))
            elif isinstance(value, list):
                return [relocate(item) for item in value]
            elif isinstance(value, dict):
                return {key: relocate(item) for key, item in value.items()}
            elif isinstance(value, tuple):
                return tuple(relocate(item) for item in value)
            return value

        result = relocate(copy.deepcopy(project))
        result.name = name
        result.project_dir = destination
        result.created = created.created
        manager.save_project(result)
        return result
    except Exception:
        logger.exception("Could not copy Sprite project %r", project.name)
        # This directory was uniquely created above; the original is untouched.
        try:
            shutil.rmtree(destination)
        except OSError:
            logger.exception("Could not remove incomplete Sprite project copy")
        raise
