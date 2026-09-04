"""
Centralized logging configuration for ImageAI.
Logs errors to both console and file for easy debugging and error reporting.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
import platform
import re
import sys
import atexit
import shutil
import traceback
import warnings


# Secret shapes that must never reach a log line. Compiled once; the filter
# runs on every record, so the match must stay cheap.
_QUERY_KEY_RE = re.compile(r"([?&]key=)[^&\s'\"]+")
_GOOGLE_KEY_RE = re.compile(r"AIza[0-9A-Za-z_\-]{20,}")
_OPENAI_KEY_RE = re.compile(r"sk-[0-9A-Za-z_\-]{20,}")
_HF_KEY_RE = re.compile(r"hf_[A-Za-z0-9]{16,}")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+\S+")
_MASK = "***"


def redact_secrets(text: str) -> str:
    """Replace API keys and bearer tokens in ``text`` with ``***``.

    Only the ``?key=`` / ``&key=`` query form is masked. A bare ``key=`` is
    not: the sprite pipeline has a stage named ``key``.
    """
    text = _QUERY_KEY_RE.sub(r"\g<1>" + _MASK, text)
    text = _GOOGLE_KEY_RE.sub(_MASK, text)
    text = _OPENAI_KEY_RE.sub(_MASK, text)
    text = _HF_KEY_RE.sub(_MASK, text)
    return _BEARER_RE.sub("Bearer " + _MASK, text)


class SecretRedactionFilter(logging.Filter):
    """Mask API keys in the message and in the traceback of every record.

    The filter formats the message once and stores the redacted text back in
    ``record.msg``. A traceback is rendered once into ``record.exc_text``.
    ``logging.Formatter.format`` prints a pre-set ``exc_text`` and does not
    render ``exc_info`` again, so every handler prints the redacted copy.
    ``record.exc_info`` stays on the record: one ``LogRecord`` is shared by
    every handler, and a later handler (pytest ``caplog``, a handler added
    after ``setup_logging``) must still see the exception.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Handler.handle does not guard filter(). An exception here would
        # escape into the caller of the logging call, so the filter never
        # raises. On failure the record passes through unredacted and the
        # stdlib path handles it.
        try:
            self._redact(record)
        except Exception:
            pass
        return True

    @staticmethod
    def _redact(record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            # A bad format string must not drop the record.
            message = f"{record.msg} {record.args!r}"
        record.msg = redact_secrets(message)
        record.args = None

        exc_info = record.exc_info
        if exc_info:
            # Logger._log turns exc_info=True or an exception instance into a
            # tuple before the record exists, so exc_info is a tuple here.
            rendered = "".join(traceback.format_exception(*exc_info))
            record.exc_text = redact_secrets(rendered.rstrip("\n"))
        elif record.exc_text:
            record.exc_text = redact_secrets(record.exc_text)


def _report_storage_warnings(root_logger, data_paths, set_warning_sink):
    """Route storage-location warnings to the log file and to stderr.

    ``core.paths`` resolves the Settings root before this logger exists, so it
    buffers that warning. This function drains the buffer first. It then
    installs itself as the sink for later warnings. The Images, Video and
    Models roots resolve after startup, and a CLI run has no other reader for
    the buffer, so without the sink the user would get a silent fallback.

    Args:
        root_logger: The configured root logger.
        data_paths: The DataPaths singleton that holds the buffer.
        set_warning_sink: ``core.paths.set_warning_sink``.
    """
    for message in data_paths.drain_warnings():
        root_logger.warning(message)

    def _emit(message):
        # The root logger holds a stderr console handler at WARNING level and
        # the file handler, so one call reaches both destinations.
        try:
            root_logger.warning(message)
        except Exception:
            # Never let a logging failure stop path resolution.
            print(f"WARNING - {message}", file=sys.stderr)

    set_warning_sink(_emit)


def setup_logging(log_level=logging.INFO, log_to_file=True):
    """
    Set up comprehensive logging for the entire application.
    
    Args:
        log_level: Minimum level to log (default: INFO)
        log_to_file: Whether to also log to file (default: True)
    
    Returns:
        Path to log file if logging to file, None otherwise
    """
    # Resolve the log directory through the single path resolver. This import
    # is safe here: core.paths deliberately has no logging dependency.
    from core.paths import get_data_paths, set_warning_sink

    data_paths = get_data_paths()
    log_dir = data_paths.logs()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamp for log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"imageai_{timestamp}.log"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # Console handler (simple format for user)
    # Use stderr so diagnostic logs never pollute stdout (critical for --json CLI purity).
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in console
    console_handler.setFormatter(simple_formatter)
    console_handler.addFilter(SecretRedactionFilter())
    root_logger.addHandler(console_handler)
    
    # File handler (detailed format for debugging)
    if log_to_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(detailed_formatter)
        file_handler.addFilter(SecretRedactionFilter())
        root_logger.addHandler(file_handler)
        
        # Log startup information
        root_logger.info("=" * 60)
        root_logger.info("ImageAI Started")
        root_logger.info(f"Python: {sys.executable}")
        root_logger.info(f"Version: {sys.version}")
        root_logger.info(f"Platform: {platform.platform()}")
        root_logger.info(f"Log file: {log_file}")
        root_logger.info("=" * 60)

    # Both handlers are attached now, so storage warnings can reach the user.
    # The console handler writes to stderr, which keeps stdout clean for --json.
    _report_storage_warnings(root_logger, data_paths, set_warning_sink)

    if log_to_file:
        # Optional: Log GUI/Qt environment if available
        try:
            import PySide6  # type: ignore
            from PySide6 import QtCore  # type: ignore
            pyside_ver = getattr(PySide6, "__version__", None) or getattr(QtCore, "__version__", None)
            qt_ver = None
            try:
                qt_ver = QtCore.qVersion()  # runtime Qt version
            except Exception:
                pass
            root_logger.info("PySide6 detected: True")
            if pyside_ver:
                root_logger.info(f"PySide6 version: {pyside_ver}")
            if qt_ver:
                root_logger.info(f"Qt version: {qt_ver}")
            # Check QtWebEngine availability
            try:
                import PySide6.QtWebEngineWidgets  # type: ignore
                root_logger.info("QtWebEngine: available (QtWebEngineWidgets import succeeded)")
            except Exception as _we:
                root_logger.info(f"QtWebEngine: NOT available ({_we})")
        except Exception as _e:
            root_logger.info(f"PySide6 not detected at startup: {_e}")

        # Capture Python warnings to the log file
        logging.captureWarnings(True)
        warnings_logger = logging.getLogger('py.warnings')
        warnings_logger.setLevel(logging.WARNING)

        # Register cleanup function to copy log on exit
        def copy_log_on_exit():
            """Copy log file to current directory on exit"""
            try:
                current_log = Path("./imageai_current.log")
                if log_file.exists():
                    shutil.copy2(log_file, current_log)
                    print(f"\nLog copied to: {current_log.absolute()}", file=sys.stderr)
            except Exception as e:
                print(f"Could not copy log file: {e}", file=sys.stderr)
        
        # A pytest process must not overwrite the repo's ./imageai_current.log
        # with a short test log. The copy is for real app runs only.
        if "pytest" not in sys.modules:
            atexit.register(copy_log_on_exit)

        return log_file
    
    return None


def get_error_report_info():
    """
    Get information for error reporting.
    
    Returns:
        Dictionary with system info and recent log location
    """
    # Resolve the log directory through the single path resolver. This import
    # is safe here: core.paths deliberately has no logging dependency.
    from core.paths import get_data_paths

    data_paths = get_data_paths()
    log_dir = data_paths.logs()

    # Find most recent log file
    recent_log = None
    if log_dir.exists():
        log_files = sorted(log_dir.glob("imageai_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if log_files:
            recent_log = log_files[0]
    
    return {
        "platform": platform.platform(),
        "python_version": sys.version,
        "log_directory": str(log_dir),
        "recent_log": str(recent_log) if recent_log else None,
        "report_instructions": (
            "To report an error:\n"
            "1. Find the log file at: {}\n"
            "2. Copy the relevant error messages\n"
            "3. Report at: https://github.com/anthropics/imageai/issues\n"
            "4. Include: Error message, steps to reproduce, and log excerpt"
        ).format(log_dir)
    }


class LogManager:
    """
    Centralized log manager for getting named loggers.

    Provides a consistent interface for obtaining loggers with proper naming conventions.
    All loggers use the 'imageai' namespace.
    """

    def __init__(self):
        """Initialize the log manager."""
        self.base_logger = logging.getLogger("imageai")

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger with the specified name under the 'imageai' namespace.

        Args:
            name: Logger name (e.g., 'layout.engine', 'layout.fonts', 'gui.main')

        Returns:
            Logger instance
        """
        return logging.getLogger(f"imageai.{name}")


class ErrorLogger:
    """Context manager for logging exceptions with additional context"""

    def __init__(self, operation_name, logger=None, reraise=True):
        """
        Args:
            operation_name: Description of the operation being performed
            logger: Logger instance to use (default: root logger)
            reraise: Whether to re-raise the exception after logging
        """
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger()
        self.reraise = reraise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.logger.error(
                f"Error during {self.operation_name}: {exc_type.__name__}: {exc_val}",
                exc_info=True
            )
            if not self.reraise:
                return True  # Suppress exception
        return False
