"""
Project file tracking for support and debugging.
Copies the current project file to the working directory on exit.
"""

import atexit
import shutil
from pathlib import Path
import logging

# Global variable to track current project path
_current_project_path = None
logger = logging.getLogger(__name__)


def set_current_project(project_path):
    """
    Set the current project file path to be copied on exit.
    
    Args:
        project_path: Path to the current project file
    """
    global _current_project_path
    if project_path:
        _current_project_path = Path(project_path)
        logger.info(f"Tracking project: {_current_project_path}")


def copy_project_on_exit():
    """Copy current project file to working directory on exit"""
    global _current_project_path
    if _current_project_path and _current_project_path.exists():
        try:
            current_project = Path("./imageai_current_project.json")
            shutil.copy2(_current_project_path, current_project)
            print(f"Project copied to: {current_project.absolute()}")
        except Exception as e:
            logger.error(f"Could not copy project file: {e}")


# Register the cleanup function
atexit.register(copy_project_on_exit)