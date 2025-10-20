"""
Cross-platform recycle bin functionality for safe file deletion.

This module provides a safe way to delete files by moving them to the recycle bin
instead of permanently deleting them. Supports Windows, macOS, and Linux.
"""

import logging
import platform
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Check for send2trash availability
try:
    from send2trash import send2trash
    SEND2TRASH_AVAILABLE = True
except ImportError:
    SEND2TRASH_AVAILABLE = False
    send2trash = None


class RecycleBinError(Exception):
    """Exception raised when file cannot be moved to recycle bin"""
    pass


def send_to_recycle_bin(file_path: Path) -> bool:
    """
    Move a file to the recycle bin (trash) instead of permanently deleting it.

    Args:
        file_path: Path to the file to delete

    Returns:
        True if successful, False otherwise

    Raises:
        RecycleBinError: If the file cannot be moved to recycle bin and fallback fails
    """
    if not file_path.exists():
        logger.warning(f"File does not exist, cannot recycle: {file_path}")
        return False

    try:
        if SEND2TRASH_AVAILABLE:
            # Use send2trash library (cross-platform)
            send2trash(str(file_path))
            logger.info(f"Moved to recycle bin: {file_path}")
            return True
        else:
            # Fallback: Use platform-specific methods
            system = platform.system()

            if system == "Windows":
                # Windows: Use Windows API via ctypes
                return _windows_recycle(file_path)
            elif system == "Darwin":
                # macOS: Use osascript to move to trash
                return _macos_recycle(file_path)
            elif system == "Linux":
                # Linux: Use trash-cli or gio trash
                return _linux_recycle(file_path)
            else:
                logger.error(f"Unsupported platform: {system}")
                raise RecycleBinError(f"Recycle bin not supported on {system}")

    except Exception as e:
        logger.error(f"Failed to move file to recycle bin: {e}")
        raise RecycleBinError(f"Failed to recycle {file_path}: {e}") from e


def _windows_recycle(file_path: Path) -> bool:
    """
    Windows-specific recycle bin implementation using shell32.

    Args:
        file_path: Path to the file to recycle

    Returns:
        True if successful
    """
    try:
        import ctypes
        from ctypes import windll, c_wchar_p, c_uint

        # SHFILEOPSTRUCT structure
        class SHFILEOPSTRUCT(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("wFunc", c_uint),
                ("pFrom", c_wchar_p),
                ("pTo", c_wchar_p),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", ctypes.c_bool),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", c_wchar_p),
            ]

        # Constants
        FO_DELETE = 0x0003
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004

        # Setup operation
        file_op = SHFILEOPSTRUCT()
        file_op.hwnd = None
        file_op.wFunc = FO_DELETE
        file_op.pFrom = str(file_path) + '\0'  # Must be double-null terminated
        file_op.pTo = None
        file_op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
        file_op.fAnyOperationsAborted = False
        file_op.hNameMappings = None
        file_op.lpszProgressTitle = None

        # Execute
        result = windll.shell32.SHFileOperationW(ctypes.byref(file_op))

        if result == 0:
            logger.info(f"Windows: Moved to recycle bin: {file_path}")
            return True
        else:
            logger.error(f"Windows SHFileOperation failed with code: {result}")
            return False

    except Exception as e:
        logger.error(f"Windows recycle bin error: {e}")
        return False


def _macos_recycle(file_path: Path) -> bool:
    """
    macOS-specific recycle bin implementation using osascript.

    Args:
        file_path: Path to the file to recycle

    Returns:
        True if successful
    """
    try:
        import subprocess

        # Use osascript to move to trash
        script = f'tell application "Finder" to delete POSIX file "{file_path}"'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True
        )

        logger.info(f"macOS: Moved to trash: {file_path}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"macOS trash error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"macOS recycle bin error: {e}")
        return False


def _linux_recycle(file_path: Path) -> bool:
    """
    Linux-specific recycle bin implementation using gio trash or trash-cli.

    Args:
        file_path: Path to the file to recycle

    Returns:
        True if successful
    """
    try:
        import subprocess
        import shutil

        # Try gio trash first (GNOME/modern Linux)
        if shutil.which("gio"):
            result = subprocess.run(
                ["gio", "trash", str(file_path)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Linux (gio): Moved to trash: {file_path}")
            return True

        # Fallback to trash-cli
        elif shutil.which("trash-put"):
            result = subprocess.run(
                ["trash-put", str(file_path)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Linux (trash-cli): Moved to trash: {file_path}")
            return True

        # Fallback to gvfs-trash (older systems)
        elif shutil.which("gvfs-trash"):
            result = subprocess.run(
                ["gvfs-trash", str(file_path)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Linux (gvfs): Moved to trash: {file_path}")
            return True

        else:
            logger.error("No trash utility found (gio, trash-put, or gvfs-trash)")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Linux trash error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Linux recycle bin error: {e}")
        return False


def is_recycle_bin_available() -> bool:
    """
    Check if recycle bin functionality is available on this system.

    Returns:
        True if recycle bin is available, False otherwise
    """
    if SEND2TRASH_AVAILABLE:
        return True

    system = platform.system()

    if system == "Windows":
        try:
            import ctypes
            return True
        except ImportError:
            return False
    elif system == "Darwin":
        import shutil
        return shutil.which("osascript") is not None
    elif system == "Linux":
        import shutil
        return (
            shutil.which("gio") is not None
            or shutil.which("trash-put") is not None
            or shutil.which("gvfs-trash") is not None
        )
    else:
        return False


def get_recycle_bin_status() -> str:
    """
    Get a human-readable status of recycle bin availability.

    Returns:
        Status string describing recycle bin availability
    """
    if SEND2TRASH_AVAILABLE:
        return "send2trash library (cross-platform)"

    system = platform.system()

    if system == "Windows":
        try:
            import ctypes
            return "Windows Shell API"
        except ImportError:
            return "Not available (ctypes missing)"
    elif system == "Darwin":
        import shutil
        if shutil.which("osascript"):
            return "macOS Finder (osascript)"
        return "Not available (osascript missing)"
    elif system == "Linux":
        import shutil
        if shutil.which("gio"):
            return "Linux (gio trash)"
        elif shutil.which("trash-put"):
            return "Linux (trash-cli)"
        elif shutil.which("gvfs-trash"):
            return "Linux (gvfs-trash)"
        return "Not available (no trash utility found)"
    else:
        return f"Unsupported platform: {system}"
