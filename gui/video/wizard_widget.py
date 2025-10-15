"""
Workflow Wizard Widget for Video Project.

Provides step-by-step guidance through the video generation process
with smart state detection and contextual help.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QMessageBox, QScrollArea, QButtonGroup,
    QRadioButton, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from core.video.project import VideoProject
from core.video.workflow_wizard import WorkflowWizard, WorkflowStep, StepStatus


class WizardStepWidget(QFrame):
    """Widget for displaying a single workflow step"""

    clicked = Signal(object)  # Emits WorkflowStep

    def __init__(self, step_info, is_current=False, parent=None):
        super().__init__(parent)
        self.step_info = step_info
        self.is_current = is_current

        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.set_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        # Status icon
        status_icon = self._get_status_icon(step_info.status)
        self.icon_label = QLabel(status_icon)
        self.icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.icon_label)

        # Step title
        self.title_label = QLabel(step_info.title)
        title_font = QFont()
        if is_current:
            title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label, 1)

        # Optional tag
        if step_info.is_optional:
            optional_label = QLabel("(optional)")
            optional_label.setStyleSheet("color: #666; font-size: 10px;")
            layout.addWidget(optional_label)

        self.setToolTip(step_info.description)

    def set_style(self):
        """Apply styling based on state"""
        if self.is_current:
            self.setStyleSheet("""
                QFrame {
                    background-color: #e3f2fd;
                    border: 2px solid #2196F3;
                    border-radius: 5px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                }
                QFrame:hover {
                    border: 1px solid #999;
                }
            """)

    def _get_status_icon(self, status: StepStatus) -> str:
        """Get emoji icon for step status"""
        icons = {
            StepStatus.NOT_STARTED: "○",
            StepStatus.IN_PROGRESS: "◐",
            StepStatus.COMPLETED: "●",
            StepStatus.OPTIONAL_SKIPPED: "─"
        }
        return icons.get(status, "?")

    def mousePressEvent(self, event):
        """Handle click"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.step_info.step)
        super().mousePressEvent(event)


class WorkflowWizardWidget(QWidget):
    """
    Main wizard widget for video project workflow.

    Displays progress, current step info, and actions.
    """

    # Signals
    action_requested = Signal(object, object)  # (WorkflowStep, choice_key)
    step_skipped = Signal(object)  # WorkflowStep
    help_requested = Signal(object)  # WorkflowStep

    def __init__(self, project: VideoProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.wizard = None
        self.logger = logging.getLogger(__name__)

        self.init_ui()
        self.refresh_wizard_display()

    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title_label = QLabel("Workflow Guide")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Progress bar
        self.progress_label = QLabel()
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(15)
        layout.addWidget(self.progress_bar)

        # Scroll area for steps
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(QFrame.NoFrame)

        steps_container = QWidget()
        self.steps_layout = QVBoxLayout(steps_container)
        self.steps_layout.setSpacing(5)
        self.steps_layout.addStretch()

        scroll.setWidget(steps_container)
        layout.addWidget(scroll, 1)  # Take remaining space

        # Current step panel
        self.step_panel = QGroupBox("Current Step")
        step_layout = QVBoxLayout()

        self.step_title_label = QLabel()
        step_title_font = QFont()
        step_title_font.setBold(True)
        self.step_title_label.setFont(step_title_font)
        step_layout.addWidget(self.step_title_label)

        self.step_desc_label = QLabel()
        self.step_desc_label.setWordWrap(True)
        step_layout.addWidget(self.step_desc_label)

        # Help button
        self.help_button = QPushButton("? Show Help")
        self.help_button.setMaximumWidth(120)
        self.help_button.clicked.connect(self._show_help)
        step_layout.addWidget(self.help_button)

        # Scroll area for choices (this is what was missing!)
        choices_scroll = QScrollArea()
        choices_scroll.setWidgetResizable(True)
        choices_scroll.setFrameStyle(QFrame.NoFrame)
        choices_scroll.setMinimumHeight(100)  # Ensure some minimum visible space

        # Choices panel (dynamically populated)
        self.choices_widget = QWidget()
        self.choices_layout = QVBoxLayout(self.choices_widget)
        self.choices_layout.setContentsMargins(0, 10, 0, 10)

        choices_scroll.setWidget(self.choices_widget)
        step_layout.addWidget(choices_scroll, 1)  # Take remaining space in step panel

        # Action buttons (keep these outside scroll area)
        button_layout = QHBoxLayout()

        self.action_button = QPushButton()
        self.action_button.clicked.connect(self._on_action_clicked)
        button_layout.addWidget(self.action_button)

        self.skip_button = QPushButton("Skip")
        self.skip_button.clicked.connect(self._on_skip_clicked)
        button_layout.addWidget(self.skip_button)

        step_layout.addLayout(button_layout)

        self.step_panel.setLayout(step_layout)
        layout.addWidget(self.step_panel, 2)  # Give step panel more space

    def refresh_wizard_display(self):
        """Update wizard display based on current project state"""
        if not self.project:
            return

        try:
            # Get fresh wizard with current project state
            self.wizard = self.project.get_workflow_wizard()

            if not self.wizard:
                self.logger.warning("Workflow wizard not available")
                return

            next_action = self.wizard.get_next_action()

            # Update progress
            progress = next_action['progress_percent']
            self.progress_bar.setValue(progress)
            self.progress_label.setText(f"Progress: {progress}% Complete")

            # Update step list
            self._update_step_list()

            # Update current step panel
            self.step_title_label.setText(next_action['step_title'])
            self.step_desc_label.setText(next_action['action'])
            self.action_button.setText(next_action['button_text'])

            # Show/hide skip button
            self.skip_button.setVisible(next_action['is_optional'])

            # Update choices if available
            self._update_choices_panel(next_action.get('choices'))

            # Enable/disable action button based on blocking state
            if not next_action['can_proceed'] and next_action['blocking_reason']:
                self.action_button.setEnabled(False)
                self.action_button.setToolTip(next_action['blocking_reason'])
            else:
                self.action_button.setEnabled(True)
                self.action_button.setToolTip("")

        except Exception as e:
            self.logger.error(f"Error refreshing wizard display: {e}", exc_info=True)

    def _update_step_list(self):
        """Update the list of workflow steps"""
        # Clear existing step widgets
        while self.steps_layout.count() > 1:  # Keep the stretch item
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_step = self.wizard.get_current_step()

        # Add step widgets
        for step_info in self.wizard.get_all_steps():
            is_current = (step_info.step == current_step)

            step_widget = WizardStepWidget(step_info, is_current)
            step_widget.clicked.connect(self._on_step_clicked)

            self.steps_layout.insertWidget(
                self.steps_layout.count() - 1,  # Before stretch
                step_widget
            )

    def _update_choices_panel(self, choices: Optional[Dict[str, Any]]):
        """Update the choices panel with available options"""
        # Clear existing choices
        while self.choices_layout.count():
            item = self.choices_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not choices:
            self.choices_widget.setVisible(False)
            return

        self.choices_widget.setVisible(True)

        choices_label = QLabel("<b>Choose an option:</b>")
        self.choices_layout.addWidget(choices_label)

        # Create radio button group
        self.choice_buttons = QButtonGroup(self)

        for i, (choice_key, choice_info) in enumerate(choices.items()):
            # Radio button with label
            radio = QRadioButton(choice_info['label'])
            radio.setProperty("choice_key", choice_key)

            # Description
            desc_text = f"<small>{choice_info['description']}</small>"

            # Add benefits
            if 'benefits' in choice_info and choice_info['benefits']:
                desc_text += "<ul style='margin-left: 15px; margin-top: 5px;'>"
                for benefit in choice_info['benefits']:
                    desc_text += f"<li><small>✓ {benefit}</small></li>"
                desc_text += "</ul>"

            # Add drawbacks if present
            if 'drawbacks' in choice_info and choice_info['drawbacks']:
                desc_text += "<ul style='margin-left: 15px; margin-top: 5px;'>"
                for drawback in choice_info['drawbacks']:
                    desc_text += f"<li><small>⚠ {drawback}</small></li>"
                desc_text += "</ul>"

            # Add requirements if present
            if 'requirements' in choice_info and choice_info['requirements']:
                desc_text += "<p style='margin-left: 15px;'><small><b>Requirements:</b></small></p>"
                desc_text += "<ul style='margin-left: 15px; margin-top: 0;'>"
                for req in choice_info['requirements']:
                    desc_text += f"<li><small>{req}</small></li>"
                desc_text += "</ul>"

            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("margin-left: 20px; margin-bottom: 10px;")

            self.choices_layout.addWidget(radio)
            self.choices_layout.addWidget(desc_label)

            self.choice_buttons.addButton(radio, i)

            # Select first option by default
            if i == 0:
                radio.setChecked(True)

    def _show_help(self):
        """Show detailed help for current step"""
        if not self.wizard:
            return

        next_action = self.wizard.get_next_action()
        help_text = next_action['help_text']

        if help_text:
            msg = QMessageBox(self)
            msg.setWindowTitle(f"Help: {next_action['step_title']}")
            msg.setText(help_text)
            msg.setIcon(QMessageBox.Information)

            # Add estimated time as informative text
            if next_action.get('estimated_time'):
                msg.setInformativeText(f"Estimated Time: {next_action['estimated_time']}")

            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()

    def _on_action_clicked(self):
        """Handle action button click"""
        if not self.wizard:
            return

        current_step = self.wizard.get_current_step()

        # Get selected choice if choices are available
        selected_choice = None
        if hasattr(self, 'choice_buttons') and self.choice_buttons.checkedButton():
            selected_choice = self.choice_buttons.checkedButton().property("choice_key")

        # Emit signal for parent to handle actual action
        self.action_requested.emit(current_step, selected_choice)

    def _on_skip_clicked(self):
        """Handle skip button for optional steps"""
        if not self.wizard:
            return

        current_step = self.wizard.get_current_step()

        try:
            self.wizard.mark_step_skipped(current_step)
            self.refresh_wizard_display()
            self.step_skipped.emit(current_step)

        except ValueError as e:
            QMessageBox.warning(self, "Cannot Skip", str(e))

    def _on_step_clicked(self, step: WorkflowStep):
        """Handle step widget click (informational only)"""
        # For now, just show the step's help
        step_info = self.wizard.steps.get(step)
        if step_info and step_info.help_text:
            msg = QMessageBox(self)
            msg.setWindowTitle(f"{step_info.title}")
            msg.setText(step_info.help_text)
            msg.setIcon(QMessageBox.Information)
            msg.exec()

    def set_project(self, project: VideoProject):
        """Update wizard with new project"""
        self.project = project
        self.refresh_wizard_display()
