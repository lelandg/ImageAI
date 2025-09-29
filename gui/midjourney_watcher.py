"""Midjourney download watcher for automatic image detection and association."""

import logging
import time
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal, QFileSystemWatcher, QTimer, QStandardPaths
from PySide6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


@dataclass
class MidjourneySession:
    """Represents a Midjourney generation session."""
    session_id: str
    prompt: str
    slash_command: str
    start_time: datetime
    dialog_open: bool = True
    associated_images: List[Path] = field(default_factory=list)
    model: str = ""
    provider: str = "midjourney"

    def is_expired(self, window_seconds: int = 300) -> bool:
        """Check if session has expired based on time window."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return elapsed > window_seconds and not self.dialog_open

    def time_since_start(self) -> float:
        """Get seconds elapsed since session started."""
        return (datetime.now() - self.start_time).total_seconds()


class MidjourneyWatcher(QObject):
    """Watches downloads folder for Midjourney images."""

    # Signals
    imageDetected = Signal(Path, dict)  # Path to image, confidence info
    sessionStarted = Signal(str, str, str)  # session_id, prompt, command
    sessionEnded = Signal(str)  # session_id

    # Common Midjourney filename patterns
    MIDJOURNEY_PATTERNS = [
        "midjourney",
        "mj_",
        "discord",
        "_upscaled",
        "_variation",
        "imagine_",
        "grid_"
    ]

    # Supported image extensions
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    def __init__(self, parent=None):
        """Initialize the Midjourney watcher."""
        super().__init__(parent)

        self.watcher = QFileSystemWatcher()
        self.sessions: Dict[str, MidjourneySession] = {}
        self.watched_path: Optional[Path] = None
        self.enabled = False
        self.auto_accept_threshold = 85  # Default 85% confidence
        self.time_window = 300  # Default 5 minutes
        self.processed_files = set()  # Track already processed files

        # Cleanup timer for expired sessions
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_expired_sessions)
        self.cleanup_timer.start(30000)  # Check every 30 seconds

        # Connect watcher signal
        self.watcher.directoryChanged.connect(self._on_directory_changed)

        logger.info("MidjourneyWatcher initialized")

    def set_watch_path(self, path: Optional[Path] = None) -> bool:
        """Set the path to watch for downloads."""
        # Remove existing watch
        if self.watched_path:
            self.watcher.removePath(str(self.watched_path))
            self.watched_path = None

        if path is None:
            # Use system downloads folder
            downloads = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            if downloads:
                path = Path(downloads)
            else:
                # Fallback to user home / Downloads
                path = Path.home() / "Downloads"

        if not path.exists():
            logger.error(f"Watch path does not exist: {path}")
            return False

        if not path.is_dir():
            logger.error(f"Watch path is not a directory: {path}")
            return False

        # Add new watch
        if self.watcher.addPath(str(path)):
            self.watched_path = path
            logger.info(f"Watching directory: {path}")
            console.info(f"Midjourney watcher: Monitoring {path}")
            return True
        else:
            logger.error(f"Failed to watch directory: {path}")
            return False

    def start_session(self, prompt: str, slash_command: str, model: str = "") -> str:
        """Start a new Midjourney generation session."""
        session_id = str(uuid.uuid4())
        session = MidjourneySession(
            session_id=session_id,
            prompt=prompt,
            slash_command=slash_command,
            start_time=datetime.now(),
            model=model
        )

        self.sessions[session_id] = session
        self.sessionStarted.emit(session_id, prompt, slash_command)

        logger.info(f"Started Midjourney session {session_id}: {prompt[:50]}...")
        console.info(f"Watching for images from prompt: {prompt[:50]}...")

        return session_id

    def end_session(self, session_id: str):
        """Mark a session as dialog closed (but keep tracking for time window)."""
        if session_id in self.sessions:
            self.sessions[session_id].dialog_open = False
            self.sessionEnded.emit(session_id)
            logger.info(f"Ended Midjourney session {session_id}")

    def _on_directory_changed(self, path: str):
        """Handle directory change event."""
        if not self.enabled or not self.watched_path:
            return

        # Check for new image files
        watch_dir = Path(path)
        current_time = time.time()

        for file_path in watch_dir.iterdir():
            if not file_path.is_file():
                continue

            # Check if it's an image file
            if file_path.suffix.lower() not in self.IMAGE_EXTENSIONS:
                continue

            # Skip already processed files
            if str(file_path) in self.processed_files:
                continue

            # Check if file was created recently (within last 10 seconds)
            try:
                file_mtime = file_path.stat().st_mtime
                if current_time - file_mtime > 10:
                    continue  # Too old, probably not from current download
            except OSError:
                continue

            # Mark as processed
            self.processed_files.add(str(file_path))

            # Process the new image
            self._process_new_image(file_path)

    def _process_new_image(self, image_path: Path):
        """Process a newly detected image file."""
        logger.info(f"New image detected: {image_path.name}")

        # Calculate confidence and find best matching session
        confidence_data = self._calculate_confidence(image_path)

        if confidence_data:
            self.imageDetected.emit(image_path, confidence_data)
            console.info(f"Image detected: {image_path.name} (confidence: {confidence_data['confidence']:.0f}%)")

    def _calculate_confidence(self, image_path: Path) -> Optional[Dict]:
        """Calculate confidence score for image-to-session matching."""
        if not self.sessions:
            return None

        best_match = None
        best_confidence = 0
        confidence_details = []

        filename_lower = image_path.name.lower()

        for session_id, session in self.sessions.items():
            if session.is_expired(self.time_window):
                continue

            confidence = 0
            details = []

            # Time-based scoring (max 40 points)
            time_elapsed = session.time_since_start()
            if session.dialog_open:
                # Dialog is still open - high confidence
                if time_elapsed < 30:
                    confidence += 40
                    details.append("Dialog open, very recent (40pts)")
                elif time_elapsed < 60:
                    confidence += 35
                    details.append("Dialog open, recent (35pts)")
                elif time_elapsed < 120:
                    confidence += 30
                    details.append("Dialog open (30pts)")
                else:
                    confidence += 25
                    details.append("Dialog open, older (25pts)")
            else:
                # Dialog closed - lower confidence
                if time_elapsed < 60:
                    confidence += 30
                    details.append("Just closed (<1min) (30pts)")
                elif time_elapsed < 120:
                    confidence += 20
                    details.append("Recently closed (<2min) (20pts)")
                elif time_elapsed < 300:
                    confidence += 10
                    details.append("Closed <5min ago (10pts)")
                else:
                    confidence += 5
                    details.append("Closed >5min ago (5pts)")

            # Filename pattern matching (max 30 points)
            for pattern in self.MIDJOURNEY_PATTERNS:
                if pattern in filename_lower:
                    confidence += 30
                    details.append(f"Filename contains '{pattern}' (30pts)")
                    break

            # Session uniqueness (max 20 points)
            active_sessions = sum(1 for s in self.sessions.values()
                                if not s.is_expired(self.time_window))
            if active_sessions == 1:
                confidence += 20
                details.append("Only active session (20pts)")
            elif active_sessions == 2:
                confidence += 10
                details.append("One of 2 active sessions (10pts)")
            else:
                confidence += 5
                details.append(f"One of {active_sessions} sessions (5pts)")

            # Prompt keywords in filename (max 10 points)
            prompt_words = session.prompt.lower().split()[:5]  # Check first 5 words
            matching_words = sum(1 for word in prompt_words
                               if len(word) > 3 and word in filename_lower)
            if matching_words > 0:
                points = min(matching_words * 3, 10)
                confidence += points
                details.append(f"Prompt words in filename ({points}pts)")

            # Track best match
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = session
                confidence_details = details

        if best_match:
            return {
                'confidence': best_confidence,
                'session_id': best_match.session_id,
                'prompt': best_match.prompt,
                'command': best_match.slash_command,
                'details': confidence_details,
                'auto_accept': best_confidence >= self.auto_accept_threshold
            }

        return None

    def _cleanup_expired_sessions(self):
        """Remove expired sessions from tracking."""
        expired = []
        for session_id, session in self.sessions.items():
            if session.is_expired(self.time_window + 60):  # Add buffer
                expired.append(session_id)

        for session_id in expired:
            del self.sessions[session_id]
            logger.debug(f"Cleaned up expired session: {session_id}")

        # Also clean up old processed files
        if len(self.processed_files) > 1000:
            # Keep only last 500 files
            self.processed_files = set(list(self.processed_files)[-500:])

    def set_enabled(self, enabled: bool):
        """Enable or disable the watcher."""
        self.enabled = enabled
        if enabled:
            console.info("Midjourney download watcher enabled")
        else:
            console.info("Midjourney download watcher disabled")

    def set_auto_accept_threshold(self, threshold: int):
        """Set the confidence threshold for auto-accepting matches."""
        self.auto_accept_threshold = max(0, min(100, threshold))
        logger.info(f"Auto-accept threshold set to {self.auto_accept_threshold}%")

    def set_time_window(self, seconds: int):
        """Set the time window for session tracking."""
        self.time_window = max(30, min(3600, seconds))  # 30s to 1 hour
        logger.info(f"Time window set to {self.time_window} seconds")

    def get_active_sessions(self) -> List[MidjourneySession]:
        """Get list of active (non-expired) sessions."""
        return [s for s in self.sessions.values()
                if not s.is_expired(self.time_window)]