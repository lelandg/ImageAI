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
    app.setApplicationName("ImageAI")

    # Always show keyboard shortcut underlines (not just when Alt is pressed)
    # This makes the mnemonics always visible like in your screenshot
    from PySide6.QtWidgets import QStyleFactory

    # Set style that shows underlines properly
    # Windows style shows underlines only when Alt is pressed by default
    # Fusion style can show them always
    available_styles = QStyleFactory.keys()
    if "Fusion" in available_styles:
        app.setStyle("Fusion")

    # Note: The & character in button text automatically creates underlines for mnemonics
    # The visibility of these underlines depends on the OS and Qt style settings
    # On Windows, underlines typically show when Alt is pressed
    # The Fusion style helps make them more visible

    print("Creating application window...")
    window = MainWindow()
    window.show()

    # Mark initialization as complete to stop suppressing protobuf errors
    if hasattr(sys.modules.get('__main__'), '_initialization_complete'):
        sys.modules['__main__']._initialization_complete = True

    print("Starting event loop...")
    sys.exit(app.exec())


__all__ = ["launch_gui"]