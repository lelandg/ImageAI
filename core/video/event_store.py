"""
Event sourcing system for comprehensive version history.

This module implements an event-driven architecture for tracking all changes
to video projects, enabling time-travel restore to any previous state.
"""

import sqlite3
import json
import gzip
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import logging


class EventType(Enum):
    """Types of events that can occur in a video project"""
    # Project lifecycle
    PROJECT_CREATED = "project_created"
    PROJECT_OPENED = "project_opened"
    PROJECT_SAVED = "project_saved"
    PROJECT_CLOSED = "project_closed"
    
    # Scene operations
    SCENE_ADDED = "scene_added"
    SCENE_UPDATED = "scene_updated"
    SCENE_DELETED = "scene_deleted"
    SCENE_REORDERED = "scene_reordered"
    
    # Prompt operations
    PROMPT_GENERATED = "prompt_generated"
    PROMPT_EDITED = "prompt_edited"
    PROMPT_REGENERATED = "prompt_regenerated"
    PROMPT_BATCH_GENERATED = "prompt_batch_generated"
    
    # Image operations
    IMAGE_GENERATED = "image_generated"
    IMAGE_REGENERATED = "image_regenerated"
    IMAGE_APPROVED = "image_approved"
    IMAGE_REJECTED = "image_rejected"
    
    # Audio operations
    AUDIO_ADDED = "audio_added"
    AUDIO_REMOVED = "audio_removed"
    AUDIO_SETTINGS_CHANGED = "audio_settings_changed"
    
    # Video operations
    VIDEO_RENDERED = "video_rendered"
    VIDEO_EXPORTED = "video_exported"
    
    # Settings changes
    SETTINGS_UPDATED = "settings_updated"
    PROVIDER_CHANGED = "provider_changed"
    MODEL_CHANGED = "model_changed"


@dataclass
class ProjectEvent:
    """Represents a single event in the project history"""
    id: Optional[int] = None
    project_id: str = ""
    event_type: EventType = EventType.PROJECT_CREATED
    timestamp: datetime = None
    user: str = ""
    data: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    checksum: str = ""
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.data is None:
            self.data = {}
        if self.metadata is None:
            self.metadata = {}
        if not self.checksum:
            self.checksum = self.calculate_checksum()
    
    def calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum of event data"""
        content = json.dumps({
            'project_id': self.project_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat() if self.timestamp else "",
            'user': self.user,
            'data': self.data
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user': self.user,
            'data': self.data,
            'metadata': self.metadata,
            'checksum': self.checksum
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectEvent':
        """Create event from dictionary"""
        return cls(
            id=data.get('id'),
            project_id=data.get('project_id', ''),
            event_type=EventType(data.get('event_type', 'project_created')),
            timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else None,
            user=data.get('user', ''),
            data=data.get('data', {}),
            metadata=data.get('metadata', {}),
            checksum=data.get('checksum', '')
        )


class EventStore:
    """SQLite-based event store with compression and snapshots"""
    
    def __init__(self, db_path: Union[str, Path]):
        """
        Initialize event store.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user TEXT,
                    data_compressed BLOB,
                    metadata TEXT,
                    checksum TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, checksum)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_project_timestamp 
                ON events(project_id, timestamp)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_event_type 
                ON events(event_type)
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    state_compressed BLOB NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES events(id)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_snapshot_project 
                ON snapshots(project_id, timestamp)
            ''')
            
            conn.commit()
    
    def append(self, event: ProjectEvent) -> int:
        """
        Append an event to the store.
        
        Args:
            event: Event to append
            
        Returns:
            Event ID
        """
        # Compress event data
        data_json = json.dumps(event.data)
        data_compressed = gzip.compress(data_json.encode())
        
        metadata_json = json.dumps(event.metadata)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute('''
                INSERT OR IGNORE INTO events 
                (project_id, event_type, timestamp, user, data_compressed, metadata, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.project_id,
                event.event_type.value,
                event.timestamp.isoformat(),
                event.user,
                data_compressed,
                metadata_json,
                event.checksum
            ))
            
            event_id = cursor.lastrowid
            conn.commit()
            
        return event_id
    
    def get_events(self, 
                  project_id: str,
                  since: Optional[datetime] = None,
                  until: Optional[datetime] = None,
                  event_types: Optional[List[EventType]] = None,
                  limit: Optional[int] = None) -> List[ProjectEvent]:
        """
        Query events for a project.
        
        Args:
            project_id: Project ID
            since: Start timestamp (inclusive)
            until: End timestamp (inclusive)
            event_types: Filter by event types
            limit: Maximum number of events to return
            
        Returns:
            List of events
        """
        query = "SELECT * FROM events WHERE project_id = ?"
        params = [project_id]
        
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        
        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())
        
        if event_types:
            placeholders = ','.join(['?' for _ in event_types])
            query += f" AND event_type IN ({placeholders})"
            params.extend([et.value for et in event_types])
        
        query += " ORDER BY timestamp ASC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        events = []
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            for row in cursor:
                # Decompress data
                data = {}
                if row['data_compressed']:
                    data_json = gzip.decompress(row['data_compressed']).decode()
                    data = json.loads(data_json)
                
                metadata = {}
                if row['metadata']:
                    metadata = json.loads(row['metadata'])
                
                event = ProjectEvent(
                    id=row['id'],
                    project_id=row['project_id'],
                    event_type=EventType(row['event_type']),
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    user=row['user'] or '',
                    data=data,
                    metadata=metadata,
                    checksum=row['checksum']
                )
                events.append(event)
        
        return events
    
    def create_snapshot(self, project_id: str, event_id: int, state: Dict[str, Any]):
        """
        Create a snapshot of project state at a specific event.
        
        Args:
            project_id: Project ID
            event_id: Event ID to snapshot at
            state: Complete project state
        """
        state_json = json.dumps(state)
        state_compressed = gzip.compress(state_json.encode())
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                INSERT INTO snapshots (project_id, event_id, state_compressed, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (
                project_id,
                event_id,
                state_compressed,
                datetime.now().isoformat()
            ))
            conn.commit()
    
    def get_latest_snapshot(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent snapshot for a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            Snapshot state or None
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT state_compressed FROM snapshots 
                WHERE project_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (project_id,))
            
            row = cursor.fetchone()
            if row and row['state_compressed']:
                state_json = gzip.decompress(row['state_compressed']).decode()
                return json.loads(state_json)
        
        return None
    
    def rebuild_state(self, project_id: str, until: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Rebuild project state by replaying events.
        
        Args:
            project_id: Project ID
            until: Replay events until this timestamp
            
        Returns:
            Rebuilt project state
        """
        # Start from latest snapshot if available
        state = self.get_latest_snapshot(project_id) or {'project_id': project_id, 'scenes': []}
        
        # Get events to replay
        events = self.get_events(project_id, until=until)
        
        # Apply each event to rebuild state
        for event in events:
            state = self._apply_event(state, event)
        
        return state
    
    def _apply_event(self, state: Dict[str, Any], event: ProjectEvent) -> Dict[str, Any]:
        """
        Apply an event to the current state.
        
        Args:
            state: Current state
            event: Event to apply
            
        Returns:
            Updated state
        """
        # Deep copy to avoid mutation
        import copy
        new_state = copy.deepcopy(state)
        
        # Apply event based on type
        if event.event_type == EventType.PROJECT_CREATED:
            new_state.update(event.data)
        
        elif event.event_type == EventType.SCENE_ADDED:
            if 'scenes' not in new_state:
                new_state['scenes'] = []
            new_state['scenes'].append(event.data['scene'])
        
        elif event.event_type == EventType.SCENE_UPDATED:
            scene_id = event.data.get('scene_id')
            if scene_id and 'scenes' in new_state:
                for i, scene in enumerate(new_state['scenes']):
                    if scene.get('id') == scene_id:
                        new_state['scenes'][i].update(event.data.get('updates', {}))
                        break
        
        elif event.event_type == EventType.SCENE_DELETED:
            scene_id = event.data.get('scene_id')
            if scene_id and 'scenes' in new_state:
                new_state['scenes'] = [s for s in new_state['scenes'] if s.get('id') != scene_id]
        
        elif event.event_type == EventType.PROMPT_EDITED:
            scene_id = event.data.get('scene_id')
            if scene_id and 'scenes' in new_state:
                for scene in new_state['scenes']:
                    if scene.get('id') == scene_id:
                        scene['prompt'] = event.data.get('prompt', '')
                        scene['prompt_history'] = scene.get('prompt_history', [])
                        scene['prompt_history'].append({
                            'timestamp': event.timestamp.isoformat(),
                            'prompt': event.data.get('prompt', ''),
                            'user': event.user
                        })
                        break
        
        elif event.event_type == EventType.SETTINGS_UPDATED:
            if 'settings' not in new_state:
                new_state['settings'] = {}
            new_state['settings'].update(event.data)
        
        # Add more event handlers as needed
        
        return new_state
    
    def get_project_history(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get complete history summary for a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of history entries with summary information
        """
        events = self.get_events(project_id)
        
        history = []
        for event in events:
            entry = {
                'id': event.id,
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type.value,
                'user': event.user,
                'summary': self._generate_event_summary(event)
            }
            history.append(entry)
        
        return history
    
    def _generate_event_summary(self, event: ProjectEvent) -> str:
        """Generate human-readable summary for an event"""
        summaries = {
            EventType.PROJECT_CREATED: "Project created",
            EventType.SCENE_ADDED: f"Added scene: {event.data.get('scene', {}).get('title', 'Untitled')}",
            EventType.SCENE_UPDATED: f"Updated scene {event.data.get('scene_id', '')}",
            EventType.PROMPT_GENERATED: "Generated prompt with AI",
            EventType.PROMPT_EDITED: "Edited prompt manually",
            EventType.IMAGE_GENERATED: f"Generated {event.data.get('count', 1)} image(s)",
            EventType.VIDEO_RENDERED: "Rendered video",
            EventType.AUDIO_ADDED: f"Added audio: {event.data.get('filename', 'Unknown')}",
            EventType.SETTINGS_UPDATED: "Updated settings"
        }
        
        return summaries.get(event.event_type, event.event_type.value.replace('_', ' ').title())
    
    def create_restore_point(self, project_id: str, name: str, description: str = "") -> int:
        """
        Create a named restore point.
        
        Args:
            project_id: Project ID
            name: Restore point name
            description: Optional description
            
        Returns:
            Event ID of the restore point
        """
        event = ProjectEvent(
            project_id=project_id,
            event_type=EventType.PROJECT_SAVED,
            user="system",
            data={
                'restore_point': True,
                'name': name,
                'description': description
            },
            metadata={'is_restore_point': True}
        )
        
        return self.append(event)
    
    def get_restore_points(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get all restore points for a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of restore points
        """
        events = self.get_events(
            project_id,
            event_types=[EventType.PROJECT_SAVED]
        )
        
        restore_points = []
        for event in events:
            if event.metadata.get('is_restore_point'):
                restore_points.append({
                    'id': event.id,
                    'timestamp': event.timestamp.isoformat(),
                    'name': event.data.get('name', 'Unnamed'),
                    'description': event.data.get('description', '')
                })
        
        return restore_points