"""Graphical User Interface for ImageAI."""

import sys
from pathlib import Path


def launch_gui():
    """Launch the GUI application."""
    print("Starting ImageAI GUI...")

    try:
        print("Loading Qt framework...")
        from PySide6.QtWidgets import QApplication
    except ImportError:
        raise ImportError("PySide6 is required for GUI mode. Install with: pip install PySide6")

    # Use the modular MainWindow
    print("Initializing main window...")
    from .main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ImageAI")

    print("Creating application window...")
    window = MainWindow()
    window.show()

    # Mark initialization as complete to stop suppressing protobuf errors
    if hasattr(sys.modules.get('__main__'), '_initialization_complete'):
        sys.modules['__main__']._initialization_complete = True

    print("Starting event loop...")
    sys.exit(app.exec())


__all__ = ["launch_gui"]