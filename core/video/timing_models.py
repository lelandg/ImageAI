"""Data models for audio timing and transcription results."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class WordTiming:
    """Represents timing information for a single word."""

    text: str
    start_time: float  # seconds from audio start
    end_time: float    # seconds from audio start
    confidence: float = 1.0  # 0.0 - 1.0, transcription confidence

    @property
    def duration(self) -> float:
        """Duration of this word in seconds."""
        return self.end_time - self.start_time

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WordTiming":
        """Create from dictionary."""
        return cls(
            text=data["text"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            confidence=data.get("confidence", 1.0)
        )


@dataclass
class TranscriptionResult:
    """Complete transcription result from Whisper analysis."""

    full_text: str  # Complete transcribed text
    words: List[WordTiming] = field(default_factory=list)
    language: str = "en"
    duration: float = 0.0  # Total audio duration in seconds
    model_used: str = "tiny"  # Whisper model size used

    @property
    def word_count(self) -> int:
        """Number of words transcribed."""
        return len(self.words)

    def get_words_in_range(self, start: float, end: float) -> List[WordTiming]:
        """Get all words that fall within a time range."""
        return [
            w for w in self.words
            if w.start_time >= start and w.end_time <= end
        ]

    def get_text_in_range(self, start: float, end: float) -> str:
        """Get transcribed text within a time range."""
        words = self.get_words_in_range(start, end)
        return " ".join(w.text for w in words)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "full_text": self.full_text,
            "words": [w.to_dict() for w in self.words],
            "language": self.language,
            "duration": self.duration,
            "model_used": self.model_used
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptionResult":
        """Create from dictionary."""
        return cls(
            full_text=data["full_text"],
            words=[WordTiming.from_dict(w) for w in data.get("words", [])],
            language=data.get("language", "en"),
            duration=data.get("duration", 0.0),
            model_used=data.get("model_used", "tiny")
        )

    def format_as_lyrics(
        self,
        line_break_gap: float = 0.5,
        stanza_break_gap: float = 1.5
    ) -> str:
        """
        Format the transcription as lyrics with natural line breaks.

        Uses pauses between words to determine where to insert line breaks,
        similar to how lyrics are naturally formatted with each phrase on
        its own line.

        Args:
            line_break_gap: Minimum gap (seconds) between words to insert a line break
            stanza_break_gap: Minimum gap (seconds) to insert a blank line (stanza break)

        Returns:
            Formatted lyrics text with line breaks
        """
        if not self.words:
            return self.full_text

        lines = []
        current_line = []

        for i, word in enumerate(self.words):
            current_line.append(word.text)

            # Check gap to next word
            if i < len(self.words) - 1:
                next_word = self.words[i + 1]
                gap = next_word.start_time - word.end_time

                if gap >= stanza_break_gap:
                    # Large gap - end of stanza, add blank line
                    lines.append(" ".join(current_line))
                    lines.append("")  # Blank line for stanza break
                    current_line = []
                elif gap >= line_break_gap:
                    # Medium gap - end of phrase/line
                    lines.append(" ".join(current_line))
                    current_line = []

        # Don't forget the last line
        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)


@dataclass
class AlignmentResult:
    """Result of comparing provided lyrics with extracted transcription."""

    matched_words: List[WordTiming]  # Words that match between provided and extracted
    unmatched_provided: List[str]  # Words in provided lyrics not found in audio
    unmatched_extracted: List[str]  # Words in audio not in provided lyrics
    similarity_score: float  # 0.0 - 1.0, overall match quality
    aligned_text: str  # Provided lyrics with timestamps applied

    @property
    def is_good_match(self) -> bool:
        """Whether the alignment is good enough to use."""
        return self.similarity_score >= 0.7

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "matched_words": [w.to_dict() for w in self.matched_words],
            "unmatched_provided": self.unmatched_provided,
            "unmatched_extracted": self.unmatched_extracted,
            "similarity_score": self.similarity_score,
            "aligned_text": self.aligned_text
        }


@dataclass
class SceneTiming:
    """Timing information for a scene derived from word timestamps."""

    scene_index: int
    start_time: float
    end_time: float
    text: str  # Lyrics/text for this scene
    words: List[WordTiming] = field(default_factory=list)
    lip_sync_enabled: bool = False
    lip_sync_character: Optional[str] = None

    @property
    def duration(self) -> float:
        """Duration of this scene in seconds."""
        return self.end_time - self.start_time

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "scene_index": self.scene_index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
            "lip_sync_enabled": self.lip_sync_enabled,
            "lip_sync_character": self.lip_sync_character
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SceneTiming":
        """Create from dictionary."""
        return cls(
            scene_index=data["scene_index"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            text=data["text"],
            words=[WordTiming.from_dict(w) for w in data.get("words", [])],
            lip_sync_enabled=data.get("lip_sync_enabled", False),
            lip_sync_character=data.get("lip_sync_character")
        )
