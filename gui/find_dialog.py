"""Find/Search dialog for text widgets."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QTextDocument

# Try to import QWebEngineView for type checking
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None
    QWebEnginePage = None


class FindDialog(QDialog):
    """Find dialog for searching text in QTextEdit or QWebEngineView widgets."""

    def __init__(self, parent=None, text_widget=None):
        super().__init__(parent)
        self.text_widget = text_widget
        self.current_match = 0
        self.matches = []
        self.match_length = 0  # Store the length of matched text
        self.settings = QSettings("ImageAI", "FindDialog")

        # Detect widget type
        self._is_webview = HAS_WEBENGINE and QWebEngineView is not None and isinstance(text_widget, QWebEngineView)

        self.setWindowTitle("Find")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(400)

        # Restore window geometry
        self.restore_settings()

        self.init_ui()
        self.restore_search_settings()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Search input row
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Find:"))

        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.returnPressed.connect(self.find_next)
        search_layout.addWidget(self.search_input)

        layout.addLayout(search_layout)

        # Options row
        options_layout = QHBoxLayout()

        self.case_sensitive_check = QCheckBox("Case sensitive")
        self.case_sensitive_check.stateChanged.connect(self.on_search_text_changed)
        options_layout.addWidget(self.case_sensitive_check)

        self.whole_words_check = QCheckBox("Whole words")
        self.whole_words_check.stateChanged.connect(self.on_search_text_changed)
        options_layout.addWidget(self.whole_words_check)

        options_layout.addStretch()

        layout.addLayout(options_layout)

        # Results and buttons row
        buttons_layout = QHBoxLayout()

        # Results label
        self.results_label = QLabel("0 results")
        self.results_label.setStyleSheet("color: #888;")
        buttons_layout.addWidget(self.results_label)

        buttons_layout.addStretch()

        # Navigation buttons
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self.find_previous)
        self.prev_btn.setEnabled(False)
        buttons_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.find_next)
        self.next_btn.setEnabled(False)
        self.next_btn.setDefault(True)
        buttons_layout.addWidget(self.next_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_search)
        self.clear_btn.setToolTip("Clear search and highlights")
        buttons_layout.addWidget(self.clear_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_btn)

        layout.addLayout(buttons_layout)

        # Focus on search input
        self.search_input.setFocus()

    def on_search_text_changed(self):
        """Handle search text change."""
        search_text = self.search_input.text()

        if not search_text or not self.text_widget:
            self.clear_highlights()
            self.results_label.setText("0 results")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        self.find_all_matches()

    def find_all_matches(self):
        """Find all matches in the text."""
        if not self.text_widget:
            return

        search_text = self.search_input.text()
        if not search_text:
            return

        # Handle QWebEngineView differently
        if self._is_webview:
            self._find_in_webview(search_text)
            return

        # Clear previous highlights BEFORE clearing matches array
        # (clear_highlights needs the matches array to find positions)
        self.clear_highlights()

        # Now clear the matches array and reset state
        self.matches.clear()
        self.current_match = 0
        self.match_length = len(search_text)

        # Get search options
        case_sensitive = self.case_sensitive_check.isChecked()
        whole_words = self.whole_words_check.isChecked()

        # Get document and cursor
        document = self.text_widget.document()
        cursor = QTextCursor(document)

        # Search flags - use QTextDocument.FindFlag in PySide6
        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if whole_words:
            flags |= QTextDocument.FindFlag.FindWholeWords

        # Find all matches - apply background ONLY
        while not cursor.isNull():
            cursor = document.find(search_text, cursor, flags)
            if not cursor.isNull():
                self.matches.append(cursor.position())
                # Get current format to preserve text color
                current_format = cursor.charFormat()
                current_format.setBackground(QColor("#ffaa00"))  # Orange for all matches
                cursor.setCharFormat(current_format)

        # Update results
        num_matches = len(self.matches)
        if num_matches == 0:
            self.results_label.setText("No results")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
        elif num_matches == 1:
            self.results_label.setText("1 result")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.highlight_current_match()
            # Don't auto-close - let user see the result and close manually
        else:
            self.results_label.setText(f"{num_matches} results")
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            self.highlight_current_match()

    def _find_in_webview(self, search_text: str):
        """Find text in QWebEngineView using its native findText method."""
        if not HAS_WEBENGINE:
            return

        # Build flags for QWebEngineView
        flags = QWebEnginePage.FindFlag(0)
        if self.case_sensitive_check.isChecked():
            flags |= QWebEnginePage.FindFlag.FindCaseSensitively

        # QWebEngineView doesn't support whole words directly, but we search anyway
        # Note: whole_words_check is ignored for web views

        # Use findText with callback to update UI
        def on_find_result(result):
            # result is a QWebEngineFindTextResult in newer Qt versions
            # or just a bool in older versions
            try:
                # Try newer API first (Qt 6.2+)
                num_matches = result.numberOfMatches() if hasattr(result, 'numberOfMatches') else (1 if result else 0)
                active_match = result.activeMatch() if hasattr(result, 'activeMatch') else 0
            except (AttributeError, TypeError):
                # Fallback for older Qt or bool result
                num_matches = 1 if result else 0
                active_match = 0

            if num_matches == 0:
                self.results_label.setText("No results")
                self.prev_btn.setEnabled(False)
                self.next_btn.setEnabled(False)
            else:
                if hasattr(result, 'numberOfMatches'):
                    self.results_label.setText(f"{active_match} of {num_matches}")
                else:
                    self.results_label.setText("Found")
                self.prev_btn.setEnabled(num_matches > 1)
                self.next_btn.setEnabled(num_matches > 1)

        # Perform the search
        self.text_widget.findText(search_text, flags, on_find_result)

    def highlight_current_match(self):
        """Highlight the current match with a different color."""
        if not self.matches or not self.text_widget:
            return

        if self.current_match >= len(self.matches):
            self.current_match = 0
        elif self.current_match < 0:
            self.current_match = len(self.matches) - 1

        # Get position of current match
        position = self.matches[self.current_match]

        # Move cursor to match
        cursor = self.text_widget.textCursor()
        cursor.setPosition(position - self.match_length)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, self.match_length)

        # Apply yellow highlight to current match (preserve text color)
        current_format = cursor.charFormat()
        current_format.setBackground(QColor("#ffff00"))  # Yellow for current
        cursor.setCharFormat(current_format)

        # Set cursor and ensure visible
        self.text_widget.setTextCursor(cursor)
        self.text_widget.ensureCursorVisible()

        # Update results label
        if len(self.matches) > 1:
            self.results_label.setText(f"{self.current_match + 1} of {len(self.matches)}")

    def find_next(self):
        """Find next match."""
        if self._is_webview:
            # For web views, just call findText again (it advances automatically)
            search_text = self.search_input.text()
            if search_text and self.text_widget:
                flags = QWebEnginePage.FindFlag(0)
                if self.case_sensitive_check.isChecked():
                    flags |= QWebEnginePage.FindFlag.FindCaseSensitively
                self.text_widget.findText(search_text, flags)
            return

        if not self.matches:
            self.on_search_text_changed()
            return

        if len(self.matches) > 0:
            # Restore previous match to yellow
            self.restore_match_highlight(self.current_match)

            self.current_match = (self.current_match + 1) % len(self.matches)
            self.highlight_current_match()

    def find_previous(self):
        """Find previous match."""
        if self._is_webview:
            # For web views, use FindBackward flag
            search_text = self.search_input.text()
            if search_text and self.text_widget:
                flags = QWebEnginePage.FindFlag.FindBackward
                if self.case_sensitive_check.isChecked():
                    flags |= QWebEnginePage.FindFlag.FindCaseSensitively
                self.text_widget.findText(search_text, flags)
            return

        if not self.matches:
            return

        if len(self.matches) > 0:
            # Restore previous match to yellow
            self.restore_match_highlight(self.current_match)

            self.current_match = (self.current_match - 1) % len(self.matches)
            self.highlight_current_match()

    def restore_match_highlight(self, match_index):
        """Restore a match to the default highlight color."""
        if not self.text_widget or match_index >= len(self.matches):
            return

        position = self.matches[match_index]
        cursor = self.text_widget.textCursor()
        cursor.setPosition(position - self.match_length)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, self.match_length)

        # Apply orange highlight (preserve text color)
        current_format = cursor.charFormat()
        current_format.setBackground(QColor("#ffaa00"))  # Orange for other matches
        cursor.setCharFormat(current_format)

    def clear_search(self):
        """Clear search input and all highlights."""
        self.search_input.clear()
        self.clear_highlights()
        self.matches.clear()
        self.current_match = 0
        self.match_length = 0
        self.results_label.setText("0 results")
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)

    def clear_highlights(self):
        """Clear all search highlights without affecting text color."""
        if not self.text_widget:
            return

        # For web views, clear by searching for empty string
        if self._is_webview:
            self.text_widget.findText("")  # Clears highlighting in QWebEngineView
            return

        # Use stored match length if available
        search_len = self.match_length if self.match_length > 0 else len(self.search_input.text())

        if search_len > 0 and self.matches:
            # Clear highlights from each match position
            for position in self.matches:
                cursor = self.text_widget.textCursor()
                cursor.setPosition(position - search_len)
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, search_len)

                # Get current format and only clear background
                current_format = cursor.charFormat()
                current_format.clearBackground()
                cursor.setCharFormat(current_format)

        # Clear selection
        cursor = self.text_widget.textCursor()
        cursor.clearSelection()
        self.text_widget.setTextCursor(cursor)

    def showEvent(self, event):
        """Handle show event - restore state when dialog is shown."""
        super().showEvent(event)

        # Clear any stale state from previous session
        self.matches.clear()
        self.current_match = 0
        self.match_length = 0

        # Clear any existing highlights first
        if self.text_widget and not self._is_webview:
            cursor = self.text_widget.textCursor()
            cursor.clearSelection()
            self.text_widget.setTextCursor(cursor)

        # Always start with clean UI state
        self.results_label.setText("0 results")
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)

        # Focus search input - it should be empty from closeEvent
        self.search_input.setFocus()

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_F3:
            if event.modifiers() & Qt.ShiftModifier:
                self.find_previous()
            else:
                self.find_next()
        else:
            super().keyPressEvent(event)

    def save_settings(self):
        """Save window geometry and search options."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("case_sensitive", self.case_sensitive_check.isChecked())
        self.settings.setValue("whole_words", self.whole_words_check.isChecked())
        self.settings.setValue("last_search", self.search_input.text())

    def restore_settings(self):
        """Restore window geometry."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def restore_search_settings(self):
        """Restore search options."""
        self.case_sensitive_check.setChecked(self.settings.value("case_sensitive", False, type=bool))
        self.whole_words_check.setChecked(self.settings.value("whole_words", False, type=bool))
        last_search = self.settings.value("last_search", "")
        if last_search:
            self.search_input.setText(last_search)

    def closeEvent(self, event):
        """Handle close event."""
        # Clear highlights for web views
        if self._is_webview and self.text_widget:
            self.text_widget.findText("")  # Clears highlighting
        self.save_settings()
        super().closeEvent(event)