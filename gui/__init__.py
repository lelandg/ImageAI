"""Graphical User Interface for ImageAI."""

import sys
from pathlib import Path


def launch_gui():
    """Launch the GUI application."""
    print("Starting ImageAI GUI...")

    try:
        print("Loading Qt framework...")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except ImportError:
        raise ImportError("PySide6 is required for GUI mode. Install with: pip install PySide6")

    # Custom Qt message handler to suppress benign monitor errors
    def qt_message_handler(msg_type, context, msg):
        """Filter out benign Qt warnings about monitor interfaces."""
        # Suppress monitor interface errors (happens when displays are off/disconnected)
        if "Unable to open monitor interface" in msg and "DISPLAY" in msg:
            return  # Silently ignore these benign errors

        # Suppress other known benign Qt warnings
        if "QWindowsWindow::setGeometry" in msg:
            return  # Window geometry warnings during resize

        # Suppress FFmpeg/codec warnings during video playback
        if "[aac @" in msg and "Could not update timestamps" in msg:
            return  # Benign AAC codec timestamp warnings
        if "[h264 @" in msg or "[hevc @" in msg or "[vp9 @" in msg:
            return  # Benign video codec warnings

        # Log other Qt messages normally
        import logging
        logger = logging.getLogger("qt")

        if msg_type == QtMsgType.QtDebugMsg:
            logger.debug(f"Qt: {msg}")
        elif msg_type == QtMsgType.QtInfoMsg:
            logger.info(f"Qt: {msg}")
        elif msg_type == QtMsgType.QtWarningMsg:
            # Only log non-suppressed warnings
            logger.warning(f"Qt: {msg}")
        elif msg_type == QtMsgType.QtCriticalMsg:
            logger.error(f"Qt Critical: {msg}")
        elif msg_type == QtMsgType.QtFatalMsg:
            logger.critical(f"Qt Fatal: {msg}")

    # Install the custom message handler
    qInstallMessageHandler(qt_message_handler)

    # Use the modular MainWindow
    print("Initializing main window...")
    from .main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName("LelandGreenProductions")
    app.setApplicationName("ImageAI")

    # Load Maestro fonts (Roboto body, Limelight headings)
    from PySide6.QtGui import QFontDatabase
    _fonts_dir = Path(__file__).parent / "resources" / "fonts"
    for _font_file in ["Roboto-Regular.ttf", "Roboto-Bold.ttf", "Limelight-Regular.ttf"]:
        _font_path = _fonts_dir / _font_file
        if _font_path.exists():
            _font_id = QFontDatabase.addApplicationFont(str(_font_path))
            if _font_id == -1:
                import logging as _logging
                _logging.getLogger(__name__).warning(f"Failed to load font: {_font_file}")

    # Apply Maestro dark theme (brand-navy + brand-cyan)
    from .theme import apply_maestro_theme
    apply_maestro_theme(app)

    # Fusion style for proper mnemonic underline rendering
    from PySide6.QtWidgets import QStyleFactory
    available_styles = QStyleFactory.keys()
    if "Fusion" in available_styles:
        app.setStyle("Fusion")
    # Re-apply theme after Fusion style change (Fusion resets the stylesheet)
    apply_maestro_theme(app)

    # Log GUI environment details
    try:
        import logging
        from PySide6 import __version__ as PYSIDE_VERSION  # type: ignore
        from PySide6.QtCore import qVersion
        logger = logging.getLogger(__name__)
        logger.info(f"GUI environment -> PySide6: {PYSIDE_VERSION}, Qt: {qVersion()}")
        # QPA platform + style
        try:
            platform_name = app.platformName()
        except Exception:
            platform_name = "<unknown>"
        try:
            current_style = app.style().objectName()
        except Exception:
            current_style = "<unknown>"
        logger.info(f"QPA platform: {platform_name}, Style: {current_style}")
        # QtWebEngine availability
        try:
            import PySide6.QtWebEngineWidgets  # noqa: F401
            logger.info("QtWebEngineWidgets import: OK")
        except Exception as e:
            logger.info(f"QtWebEngineWidgets import: FAILED ({e})")
    except Exception:
        pass

    print("Creating application window...")
    window = MainWindow()
    window.show()

    # Mark initialization as complete to stop suppressing protobuf errors
    if hasattr(sys.modules.get('__main__'), '_initialization_complete'):
        sys.modules['__main__']._initialization_complete = True

    print("Starting event loop...")
    sys.exit(app.exec())


__all__ = ["launch_gui"]
