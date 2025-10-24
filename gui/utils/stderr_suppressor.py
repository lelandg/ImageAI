"""
Utility for suppressing stderr output from C libraries (FFmpeg, codecs, etc.)

This module provides a context manager that redirects stderr at the file
descriptor level, which is necessary to suppress output from C libraries
that bypass Python's sys.stderr redirection.
"""

import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SuppressStderr:
    """
    Context manager to suppress stderr at the file descriptor level.

    Use this to suppress FFmpeg warnings from QMediaPlayer operations:

    Example:
        with SuppressStderr():
            media_player.setSource(QUrl.fromLocalFile(video_path))

    Platform: Works on Windows, Linux, and macOS
    Thread-safety: Not thread-safe; use only in main thread or with locks
    """

    def __init__(self, log_errors: bool = False):
        """
        Initialize stderr suppressor.

        Args:
            log_errors: If True, log any errors during suppression setup/teardown
        """
        self.log_errors = log_errors
        self.original_stderr_fd: Optional[int] = None
        self.devnull_fd: Optional[int] = None
        self.saved_stderr_fd: Optional[int] = None

    def __enter__(self):
        """Redirect stderr to devnull"""
        try:
            self.original_stderr_fd = sys.stderr.fileno()
            # Duplicate the original stderr fd to restore later
            self.saved_stderr_fd = os.dup(self.original_stderr_fd)
            # Open devnull for writing
            self.devnull_fd = os.open(os.devnull, os.O_WRONLY)
            # Flush any pending stderr output before redirecting
            sys.stderr.flush()
            # Redirect stderr to devnull
            os.dup2(self.devnull_fd, self.original_stderr_fd)
        except Exception as e:
            # If redirection fails, clean up and continue without suppression
            self._cleanup()
            if self.log_errors:
                logger.warning(f"Could not suppress stderr: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original stderr"""
        try:
            if self.saved_stderr_fd is not None and self.original_stderr_fd is not None:
                # Flush any buffered output before restoring
                sys.stderr.flush()
                # Restore original stderr
                os.dup2(self.saved_stderr_fd, self.original_stderr_fd)
        except Exception as e:
            if self.log_errors:
                logger.warning(f"Could not restore stderr: {e}")
        finally:
            self._cleanup()
        return False  # Don't suppress exceptions

    def _cleanup(self):
        """Close file descriptors"""
        if self.saved_stderr_fd is not None:
            try:
                os.close(self.saved_stderr_fd)
            except OSError:
                pass
            self.saved_stderr_fd = None

        if self.devnull_fd is not None:
            try:
                os.close(self.devnull_fd)
            except OSError:
                pass
            self.devnull_fd = None
