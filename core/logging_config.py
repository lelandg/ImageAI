"""
Centralized logging configuration for ImageAI.
Logs errors to both console and file for easy debugging and error reporting.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
import platform
import sys
import atexit
import shutil
import warnings


def setup_logging(log_level=logging.INFO, log_to_file=True):
    """
    Set up comprehensive logging for the entire application.
    
    Args:
        log_level: Minimum level to log (default: INFO)
        log_to_file: Whether to also log to file (default: True)
    
    Returns:
        Path to log file if logging to file, None otherwise
    """
    # Determine log directory based on platform
    system = platform.system()
    if system == "Windows":
        import os
        log_dir = Path(os.environ.get('APPDATA', '')) / 'ImageAI' / 'logs'
    elif system == "Darwin":  # macOS
        log_dir = Path.home() / 'Library' / 'Application Support' / 'ImageAI' / 'logs'
    else:  # Linux
        log_dir = Path.home() / '.config' / 'ImageAI' / 'logs'
    
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
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in console
    console_handler.setFormatter(simple_formatter)
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
        root_logger.addHandler(file_handler)
        
        # Log startup information
        root_logger.info("=" * 60)
        root_logger.info("ImageAI Started")
        root_logger.info(f"Python: {sys.executable}")
        root_logger.info(f"Version: {sys.version}")
        root_logger.info(f"Platform: {platform.platform()}")
        root_logger.info(f"Log file: {log_file}")
        root_logger.info("=" * 60)

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
                    print(f"\nLog copied to: {current_log.absolute()}")
            except Exception as e:
                print(f"Could not copy log file: {e}")
        
        atexit.register(copy_log_on_exit)
        
        return log_file
    
    return None


def get_error_report_info():
    """
    Get information for error reporting.
    
    Returns:
        Dictionary with system info and recent log location
    """
    system = platform.system()
    if system == "Windows":
        import os
        log_dir = Path(os.environ.get('APPDATA', '')) / 'ImageAI' / 'logs'
    elif system == "Darwin":
        log_dir = Path.home() / 'Library' / 'Application Support' / 'ImageAI' / 'logs'
    else:
        log_dir = Path.home() / '.config' / 'ImageAI' / 'logs'
    
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
