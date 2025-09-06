"""Graphical User Interface for ImageAI."""

import sys
from pathlib import Path


def launch_gui():
    """Launch the GUI application."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        raise ImportError("PySide6 is required for GUI mode. Install with: pip install PySide6")
    
    # Use the original MainWindow for now to preserve all functionality
    # This ensures 100% compatibility while we gradually refactor
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from main_original import MainWindow
    
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ImageAI")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


__all__ = ["launch_gui"]