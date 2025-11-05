"""
History tab for video project version control.

This module provides a visual timeline interface for viewing project history,
comparing versions, and restoring to previous states.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QSplitter, QComboBox, QCheckBox,
    QMessageBox, QInputDialog, QHeaderView
)
from PySide6.QtCore import Qt, Signal, Slot, QDateTime
from PySide6.QtGui import QColor, QBrush, QIcon

from core.video.event_store import EventStore, EventType, ProjectEvent


class HistoryTab(QWidget):
    """History tab for project version control"""
    
    # Signals
    restore_requested = Signal(str, datetime)  # project_id, timestamp
    event_selected = Signal(dict)  # event details
    
    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize history tab.
        
        Args:
            project_id: Current project ID
        """
        super().__init__()
        self.project_id = project_id
        self.event_store = None
        self.current_events = []
        self.logger = logging.getLogger(__name__)
        
        self.init_ui()
        self.init_event_store()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Create main splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Timeline
        left_panel = self.create_timeline_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Details
        right_panel = self.create_details_panel()
        splitter.addWidget(right_panel)
        
        # Set initial splitter sizes (60/40 split)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        
        # Bottom controls
        controls = self.create_controls()
        layout.addWidget(controls)
    
    def create_timeline_panel(self) -> QWidget:
        """Create timeline panel with event tree"""
        group = QGroupBox("Project History")
        layout = QVBoxLayout()
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Filter:"))
        
        self.event_filter = QComboBox()
        self.event_filter.addItems([
            "All Events",
            "Project Changes",
            "Scene Changes",
            "Prompt Changes",
            "Image Generation",
            "Video Rendering",
            "Settings Changes"
        ])
        self.event_filter.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.event_filter)
        
        self.show_details_check = QCheckBox("Show Details")
        self.show_details_check.setChecked(True)
        self.show_details_check.toggled.connect(self.toggle_details)
        filter_layout.addWidget(self.show_details_check)
        
        filter_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_history)
        filter_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(filter_layout)
        
        # Timeline tree
        self.timeline_tree = QTreeWidget()
        self.timeline_tree.setHeaderLabels(["Time", "Event", "User", "Summary"])
        self.timeline_tree.setAlternatingRowColors(True)
        self.timeline_tree.itemSelectionChanged.connect(self.on_event_selected)
        
        # Configure column widths
        header = self.timeline_tree.header()
        header.resizeSection(0, 150)  # Time
        header.resizeSection(1, 150)  # Event
        header.resizeSection(2, 100)  # User
        header.setStretchLastSection(True)  # Summary
        
        layout.addWidget(self.timeline_tree)
        
        # Statistics
        self.stats_label = QLabel("0 events")
        layout.addWidget(self.stats_label)
        
        group.setLayout(layout)
        return group
    
    def create_details_panel(self) -> QWidget:
        """Create details panel for selected event"""
        group = QGroupBox("Event Details")
        layout = QVBoxLayout()
        
        # Event info
        info_layout = QHBoxLayout()
        self.event_info_label = QLabel("Select an event to view details")
        info_layout.addWidget(self.event_info_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # Details text
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Event details will appear here...")
        layout.addWidget(self.details_text)
        
        # Restore point controls
        restore_layout = QHBoxLayout()
        
        self.create_restore_btn = QPushButton("Create Restore Point")
        self.create_restore_btn.clicked.connect(self.create_restore_point)
        self.create_restore_btn.setEnabled(False)
        restore_layout.addWidget(self.create_restore_btn)
        
        self.restore_to_btn = QPushButton("Restore to This Point")
        self.restore_to_btn.clicked.connect(self.restore_to_point)
        self.restore_to_btn.setEnabled(False)
        restore_layout.addWidget(self.restore_to_btn)
        
        restore_layout.addStretch()
        layout.addLayout(restore_layout)
        
        group.setLayout(layout)
        return group
    
    def create_controls(self) -> QWidget:
        """Create bottom control panel"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Storage info
        self.storage_label = QLabel("Storage: 0 KB")
        layout.addWidget(self.storage_label)
        
        layout.addStretch()
        
        # Export/Import
        self.export_btn = QPushButton("Export History")
        self.export_btn.clicked.connect(self.export_history)
        layout.addWidget(self.export_btn)
        
        # Clear old events
        self.clear_old_btn = QPushButton("Clear Old Events")
        self.clear_old_btn.clicked.connect(self.clear_old_events)
        layout.addWidget(self.clear_old_btn)
        
        widget.setLayout(layout)
        return widget
    
    def init_event_store(self):
        """Initialize event store connection"""
        try:
            db_path = Path.home() / ".imageai" / "video_projects" / "events.db"
            self.event_store = EventStore(db_path)
            
            if self.project_id:
                self.load_history()
        except Exception as e:
            self.logger.error(f"Failed to initialize event store: {e}")
    
    def set_project(self, project_id: str):
        """
        Set the current project to display history for.
        
        Args:
            project_id: Project ID
        """
        self.project_id = project_id
        self.load_history()
    
    def load_history(self):
        """Load project history from event store"""
        if not self.event_store or not self.project_id:
            return
        
        try:
            # Get all events for project
            self.current_events = self.event_store.get_events(self.project_id)
            
            # Apply filter
            self.apply_filter()
            
            # Update statistics
            self.update_statistics()
            
        except Exception as e:
            self.logger.error(f"Failed to load history: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load history: {e}")
    
    def apply_filter(self):
        """Apply event filter to timeline"""
        if not self.current_events:
            return
        
        filter_text = self.event_filter.currentText()
        
        # Map filter to event types
        filter_map = {
            "All Events": None,
            "Project Changes": [EventType.PROJECT_CREATED, EventType.PROJECT_SAVED],
            "Scene Changes": [EventType.SCENE_ADDED, EventType.SCENE_UPDATED, 
                            EventType.SCENE_DELETED, EventType.SCENE_REORDERED],
            "Prompt Changes": [EventType.PROMPT_GENERATED, EventType.PROMPT_EDITED,
                             EventType.PROMPT_REGENERATED, EventType.PROMPT_BATCH_GENERATED],
            "Image Generation": [EventType.IMAGE_GENERATED, EventType.IMAGE_REGENERATED,
                                EventType.IMAGE_APPROVED, EventType.IMAGE_REJECTED],
            "Video Rendering": [EventType.VIDEO_RENDERED, EventType.VIDEO_EXPORTED],
            "Settings Changes": [EventType.SETTINGS_UPDATED, EventType.PROVIDER_CHANGED,
                               EventType.MODEL_CHANGED]
        }
        
        event_types = filter_map.get(filter_text)
        
        # Clear timeline
        self.timeline_tree.clear()
        
        # Group events by date
        events_by_date = {}
        for event in self.current_events:
            if event_types and event.event_type not in event_types:
                continue
            
            date_key = event.timestamp.date()
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)
        
        # Add to tree
        for date in sorted(events_by_date.keys(), reverse=True):
            # Create date node
            date_item = QTreeWidgetItem(self.timeline_tree)
            date_item.setText(0, date.strftime("%Y-%m-%d"))
            date_item.setExpanded(True)
            
            # Style date node
            for col in range(4):
                date_item.setBackground(col, QBrush(QColor(240, 240, 240)))
            
            # Add events for this date
            for event in events_by_date[date]:
                event_item = QTreeWidgetItem(date_item)
                event_item.setText(0, event.timestamp.strftime("%H:%M:%S"))
                event_item.setText(1, self._get_event_display_name(event.event_type))
                event_item.setText(2, event.user or "System")
                event_item.setText(3, self._get_event_summary(event))
                
                # Store event data
                event_item.setData(0, Qt.UserRole, event)
                
                # Color code by event type
                color = self._get_event_color(event.event_type)
                if color:
                    event_item.setForeground(1, QBrush(color))
    
    def on_event_selected(self):
        """Handle event selection in timeline"""
        items = self.timeline_tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        event = item.data(0, Qt.UserRole)
        
        if not event:
            return  # Date node selected
        
        # Update details panel
        self.show_event_details(event)
        
        # Enable buttons
        self.create_restore_btn.setEnabled(True)
        self.restore_to_btn.setEnabled(True)
        
        # Emit signal
        self.event_selected.emit(event.to_dict())
    
    def show_event_details(self, event: ProjectEvent):
        """
        Show detailed information for an event.
        
        Args:
            event: Event to display
        """
        # Update info label
        self.event_info_label.setText(
            f"Event #{event.id} - {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Format details
        details = []
        details.append(f"Event Type: {self._get_event_display_name(event.event_type)}")
        details.append(f"User: {event.user or 'System'}")
        details.append(f"Timestamp: {event.timestamp.isoformat()}")
        details.append(f"Checksum: {event.checksum[:16]}...")
        details.append("")
        
        # Event data
        if event.data:
            details.append("Event Data:")
            for key, value in event.data.items():
                if isinstance(value, dict):
                    details.append(f"  {key}:")
                    for k, v in value.items():
                        details.append(f"    {k}: {v}")
                elif isinstance(value, list):
                    details.append(f"  {key}: [{len(value)} items]")
                else:
                    details.append(f"  {key}: {value}")
        
        # Metadata
        if event.metadata:
            details.append("")
            details.append("Metadata:")
            for key, value in event.metadata.items():
                details.append(f"  {key}: {value}")
        
        self.details_text.setPlainText("\n".join(details))
    
    def create_restore_point(self):
        """Create a named restore point at current selection"""
        items = self.timeline_tree.selectedItems()
        if not items:
            return
        
        event = items[0].data(0, Qt.UserRole)
        if not event:
            return
        
        # Get name from user
        name, ok = QInputDialog.getText(
            self,
            "Create Restore Point",
            "Enter a name for this restore point:"
        )
        
        if ok and name:
            description, ok = QInputDialog.getText(
                self,
                "Restore Point Description",
                "Enter an optional description:"
            )
            
            try:
                event_id = self.event_store.create_restore_point(
                    self.project_id,
                    name,
                    description or ""
                )
                
                QMessageBox.information(
                    self,
                    "Success",
                    f"Restore point '{name}' created successfully"
                )
                
                # Reload history
                self.load_history()
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create restore point: {e}")
    
    def restore_to_point(self):
        """Restore project to selected point in history"""
        items = self.timeline_tree.selectedItems()
        if not items:
            return
        
        event = items[0].data(0, Qt.UserRole)
        if not event:
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            f"Restore project to state at {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}?\n\n"
            "This will revert all changes made after this point.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Emit restore signal
            self.restore_requested.emit(self.project_id, event.timestamp)
    
    def toggle_details(self, checked: bool):
        """Toggle detail level in timeline"""
        # This would show/hide additional columns or expand items
        pass
    
    def update_statistics(self):
        """Update statistics display"""
        if not self.current_events:
            self.stats_label.setText("0 events")
            self.storage_label.setText("Storage: 0 KB")
            return
        
        # Event count
        self.stats_label.setText(f"{len(self.current_events)} events")
        
        # Calculate storage (approximate)
        # This would need actual DB size calculation
        storage_kb = len(self.current_events) * 2  # Rough estimate
        self.storage_label.setText(f"Storage: {storage_kb} KB")
    
    def export_history(self):
        """Export project history to file"""
        if not self.current_events:
            QMessageBox.information(self, "No History", "No history to export")
            return
        
        from PySide6.QtWidgets import QFileDialog
        import json

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export History",
            f"{self.project_id}_history.json",
            "JSON Files (*.json)"
        )
        
        if filename:
            try:
                history_data = {
                    "project_id": self.project_id,
                    "exported_at": datetime.now().isoformat(),
                    "events": [event.to_dict() for event in self.current_events]
                }
                
                with open(filename, 'w') as f:
                    json.dump(history_data, f, indent=2)
                
                QMessageBox.information(
                    self,
                    "Success",
                    f"History exported to {filename}"
                )
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to export: {e}")
    
    def clear_old_events(self):
        """Clear old events to save space"""
        # This would implement cleanup logic
        reply = QMessageBox.question(
            self,
            "Clear Old Events",
            "Remove events older than 30 days?\n\n"
            "Restore points will be preserved.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=30)

            # Filter events older than 30 days
            original_count = len(self.all_events)
            self.all_events = [
                event for event in self.all_events
                if event.timestamp >= cutoff_date or event.event_type == EventType.PROJECT_RESTORED
            ]
            removed_count = original_count - len(self.all_events)

            # Update display
            self._apply_filters()
            QMessageBox.information(
                self,
                "Cleanup Complete",
                f"Removed {removed_count} old events.\nRestored points preserved."
            )
    
    def _get_event_display_name(self, event_type: EventType) -> str:
        """Get display name for event type"""
        return event_type.value.replace('_', ' ').title()
    
    def _get_event_summary(self, event: ProjectEvent) -> str:
        """Get summary text for event"""
        summaries = {
            EventType.SCENE_ADDED: lambda e: f"Added: {e.data.get('scene', {}).get('title', 'Untitled')}",
            EventType.PROMPT_EDITED: lambda e: f"Scene {e.data.get('scene_id', '')}",
            EventType.IMAGE_GENERATED: lambda e: f"{e.data.get('count', 0)} images",
            EventType.VIDEO_RENDERED: lambda e: f"Duration: {e.data.get('duration', 0)}s",
            EventType.SETTINGS_UPDATED: lambda e: f"Changed: {', '.join(e.data.keys())}",
        }
        
        handler = summaries.get(event.event_type)
        if handler:
            try:
                return handler(event)
            except:
                pass
        
        return ""
    
    def _get_event_color(self, event_type: EventType) -> Optional[QColor]:
        """Get color for event type"""
        colors = {
            EventType.PROJECT_CREATED: QColor(0, 150, 0),
            EventType.PROJECT_SAVED: QColor(0, 100, 200),
            EventType.SCENE_ADDED: QColor(100, 100, 200),
            EventType.SCENE_DELETED: QColor(200, 0, 0),
            EventType.PROMPT_GENERATED: QColor(150, 100, 0),
            EventType.IMAGE_GENERATED: QColor(0, 150, 150),
            EventType.VIDEO_RENDERED: QColor(150, 0, 150),
            EventType.SETTINGS_UPDATED: QColor(100, 100, 100),
        }
        
        return colors.get(event_type)