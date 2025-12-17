"""
Tag parser for video storyboard scene markers and metadata.

Parses curly brace tags like {scene: bedroom}, {camera: slow pan}, etc.
Also provides backward compatibility with legacy === NEW SCENE: === format.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class TagType(Enum):
    """Types of supported tags"""
    SCENE = "scene"           # Environment/setting change
    CAMERA = "camera"         # Camera movement
    MOOD = "mood"             # Emotional atmosphere
    FOCUS = "focus"           # Visual focus/subject
    TRANSITION = "transition" # Scene transition type
    STYLE = "style"           # Visual style hint
    LIPSYNC = "lipsync"       # Lip-sync marker (boolean)
    TEMPO = "tempo"           # Tempo/energy indicator
    TIME = "time"             # Timestamp marker (MM:SS, SS.s, or HH:MM:SS.s)
    UNKNOWN = "unknown"       # Unrecognized tag


@dataclass
class Tag:
    """Represents a parsed tag"""
    tag_type: TagType
    value: Optional[str]  # None for boolean tags like {lipsync}
    line_number: int      # Line number where tag appears (0-indexed)
    raw_text: str         # Original tag text, e.g., "{scene: bedroom}"

    def __str__(self) -> str:
        if self.value:
            return f"{{{self.tag_type.value}: {self.value}}}"
        return f"{{{self.tag_type.value}}}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.tag_type.value,
            'value': self.value,
            'line_number': self.line_number,
            'raw_text': self.raw_text
        }


@dataclass
class ParseResult:
    """Result of parsing tags from text"""
    clean_text: str                    # Text with tags removed
    tags: List[Tag]                    # All parsed tags
    tags_by_line: Dict[int, List[Tag]] # Tags grouped by line number
    legacy_markers_found: bool         # True if === format was detected

    def has_tags(self) -> bool:
        return len(self.tags) > 0

    def get_tags_of_type(self, tag_type: TagType) -> List[Tag]:
        return [t for t in self.tags if t.tag_type == tag_type]

    def get_scene_tags(self) -> List[Tag]:
        return self.get_tags_of_type(TagType.SCENE)


class TagParser:
    """
    Parser for curly brace tags in lyrics/storyboard text.

    Supported formats:
    - {scene: bedroom}      -> TagType.SCENE, value="bedroom"
    - {camera: slow pan}    -> TagType.CAMERA, value="slow pan"
    - {mood: melancholy}    -> TagType.MOOD, value="melancholy"
    - {focus: singer}       -> TagType.FOCUS, value="singer"
    - {transition: fade}    -> TagType.TRANSITION, value="fade"
    - {style: noir}         -> TagType.STYLE, value="noir"
    - {lipsync}             -> TagType.LIPSYNC, value=None (boolean)
    - {tempo: building}     -> TagType.TEMPO, value="building"

    Legacy support:
    - === NEW SCENE: bedroom === -> converted to {scene: bedroom}
    """

    # Pattern for curly brace tags: {type: value} or {type}
    TAG_PATTERN = re.compile(
        r'\{([a-zA-Z_-]+)(?:\s*:\s*([^}]+))?\}',
        re.IGNORECASE
    )

    # Pattern for legacy scene markers: === NEW SCENE: env ===
    LEGACY_SCENE_PATTERN = re.compile(
        r'^===\s*NEW\s+SCENE\s*:\s*(.+?)\s*===$',
        re.IGNORECASE
    )

    # Map of tag names to TagType enum
    TAG_TYPE_MAP = {
        'scene': TagType.SCENE,
        'camera': TagType.CAMERA,
        'mood': TagType.MOOD,
        'focus': TagType.FOCUS,
        'transition': TagType.TRANSITION,
        'style': TagType.STYLE,
        'lipsync': TagType.LIPSYNC,
        'lip-sync': TagType.LIPSYNC,
        'tempo': TagType.TEMPO,
        'time': TagType.TIME,
        'timestamp': TagType.TIME,  # Alias
        't': TagType.TIME,          # Short alias
    }

    def parse(self, text: str, convert_legacy: bool = True) -> ParseResult:
        """
        Parse tags from text.

        Args:
            text: Input text containing lyrics and tags
            convert_legacy: If True, convert === NEW SCENE === to {scene:}

        Returns:
            ParseResult with cleaned text and extracted tags
        """
        lines = text.split('\n')
        clean_lines = []
        all_tags: List[Tag] = []
        tags_by_line: Dict[int, List[Tag]] = {}
        legacy_found = False

        for line_num, line in enumerate(lines):
            original_line = line
            line_tags: List[Tag] = []

            # Check for legacy === NEW SCENE === format
            if convert_legacy:
                legacy_match = self.LEGACY_SCENE_PATTERN.match(line.strip())
                if legacy_match:
                    legacy_found = True
                    environment = legacy_match.group(1).strip()
                    tag = Tag(
                        tag_type=TagType.SCENE,
                        value=environment,
                        line_number=line_num,
                        raw_text=line.strip()
                    )
                    line_tags.append(tag)
                    logger.debug(f"Converted legacy marker: '{line.strip()}' -> {tag}")
                    # Don't include legacy marker line in clean output
                    continue

            # Find all curly brace tags in this line
            tag_matches = list(self.TAG_PATTERN.finditer(line))

            if tag_matches:
                for match in tag_matches:
                    tag_name = match.group(1).lower()
                    tag_value = match.group(2).strip() if match.group(2) else None
                    raw_text = match.group(0)

                    tag_type = self.TAG_TYPE_MAP.get(tag_name, TagType.UNKNOWN)

                    if tag_type == TagType.UNKNOWN:
                        logger.warning(f"Unknown tag type: '{tag_name}' in '{raw_text}'")

                    tag = Tag(
                        tag_type=tag_type,
                        value=tag_value,
                        line_number=line_num,
                        raw_text=raw_text
                    )
                    line_tags.append(tag)

                # Check if line is ONLY tags (no other content)
                cleaned_line = self.TAG_PATTERN.sub('', line).strip()
                if cleaned_line:
                    clean_lines.append(cleaned_line)
                # If line was only tags, don't add to clean output
            else:
                # No tags on this line
                clean_lines.append(line)

            # Store tags for this line
            if line_tags:
                all_tags.extend(line_tags)
                tags_by_line[line_num] = line_tags

        if legacy_found:
            logger.warning(
                "Legacy '=== NEW SCENE ===' format detected. "
                "Consider using {scene: environment} format instead."
            )

        return ParseResult(
            clean_text='\n'.join(clean_lines),
            tags=all_tags,
            tags_by_line=tags_by_line,
            legacy_markers_found=legacy_found
        )

    def has_tags(self, text: str) -> bool:
        """Check if text contains any tags (curly brace or legacy)"""
        if self.TAG_PATTERN.search(text):
            return True
        if self.LEGACY_SCENE_PATTERN.search(text):
            return True
        return False

    def count_tags(self, text: str) -> Dict[str, int]:
        """Count tags by type in text"""
        result = self.parse(text)
        counts: Dict[str, int] = {}
        for tag in result.tags:
            type_name = tag.tag_type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts

    def insert_tag(self, text: str, tag_type: TagType, value: Optional[str],
                   line_number: int, position: str = "before") -> str:
        """
        Insert a tag at a specific line.

        Args:
            text: Input text
            tag_type: Type of tag to insert
            value: Tag value (None for boolean tags)
            line_number: Line number to insert at (0-indexed)
            position: "before" inserts on new line before, "inline" adds to line

        Returns:
            Text with tag inserted
        """
        lines = text.split('\n')

        if line_number < 0 or line_number > len(lines):
            logger.warning(f"Invalid line number {line_number}, appending to end")
            line_number = len(lines)

        # Create tag string
        if value:
            tag_str = f"{{{tag_type.value}: {value}}}"
        else:
            tag_str = f"{{{tag_type.value}}}"

        if position == "before":
            lines.insert(line_number, tag_str)
        elif position == "inline" and line_number < len(lines):
            lines[line_number] = f"{tag_str} {lines[line_number]}"
        else:
            lines.append(tag_str)

        return '\n'.join(lines)

    def remove_all_tags(self, text: str) -> str:
        """Remove all tags from text (both curly brace and legacy)"""
        lines = text.split('\n')
        clean_lines = []

        for line in lines:
            # Skip legacy scene markers entirely
            if self.LEGACY_SCENE_PATTERN.match(line.strip()):
                continue

            # Remove curly brace tags
            cleaned = self.TAG_PATTERN.sub('', line).strip()

            # Only keep line if it has content after removing tags
            if cleaned:
                clean_lines.append(cleaned)

        return '\n'.join(clean_lines)

    def convert_legacy_to_new(self, text: str) -> str:
        """
        Convert all legacy === NEW SCENE === markers to {scene:} format.

        Returns text with legacy markers replaced.
        """
        lines = text.split('\n')
        converted_lines = []

        for line in lines:
            legacy_match = self.LEGACY_SCENE_PATTERN.match(line.strip())
            if legacy_match:
                environment = legacy_match.group(1).strip()
                converted_lines.append(f"{{scene: {environment}}}")
                logger.info(f"Converted: '{line.strip()}' -> '{{scene: {environment}}}'")
            else:
                converted_lines.append(line)

        return '\n'.join(converted_lines)

    def format_tags_for_display(self, tags: List[Tag]) -> str:
        """Format tags for display in UI"""
        if not tags:
            return ""

        parts = []
        for tag in tags:
            if tag.value:
                parts.append(f"{tag.tag_type.value}: {tag.value}")
            else:
                parts.append(tag.tag_type.value)

        return " | ".join(parts)


def parse_time_value(time_str: str) -> Optional[float]:
    """
    Parse a time string into seconds.

    Supported formats:
    - "SS" or "SS.s" - Seconds (e.g., "90", "90.5")
    - "MM:SS" or "MM:SS.s" - Minutes:Seconds (e.g., "1:30", "1:30.5")
    - "HH:MM:SS" or "HH:MM:SS.s" - Hours:Minutes:Seconds (e.g., "0:01:30")

    Returns:
        Float seconds, or None if parsing fails.
    """
    if not time_str:
        return None

    time_str = time_str.strip()

    try:
        parts = time_str.split(':')

        if len(parts) == 1:
            # Just seconds: "90" or "90.5"
            return float(parts[0])
        elif len(parts) == 2:
            # MM:SS or MM:SS.s
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        elif len(parts) == 3:
            # HH:MM:SS or HH:MM:SS.s
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        else:
            logger.warning(f"Invalid time format: {time_str}")
            return None
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse time value '{time_str}': {e}")
        return None


def format_time_value(seconds: float, include_decimals: bool = True) -> str:
    """
    Format seconds into a readable time string.

    Args:
        seconds: Time in seconds
        include_decimals: Whether to include decimal places

    Returns:
        Formatted string like "1:30" or "1:30.5"
    """
    if seconds < 0:
        return "0:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    if hours > 0:
        if include_decimals and secs != int(secs):
            return f"{hours}:{minutes:02d}:{secs:05.2f}"
        return f"{hours}:{minutes:02d}:{int(secs):02d}"
    elif include_decimals and secs != int(secs):
        return f"{minutes}:{secs:05.2f}"
    else:
        return f"{minutes}:{int(secs):02d}"


def extract_scene_metadata(tags: List[Tag]) -> Dict[str, Any]:
    """
    Convert a list of tags to scene metadata dict.

    Used when creating Scene objects from parsed tags.
    """
    metadata: Dict[str, Any] = {}

    for tag in tags:
        if tag.tag_type == TagType.SCENE:
            metadata['environment'] = tag.value
        elif tag.tag_type == TagType.CAMERA:
            metadata['camera_movement'] = tag.value
        elif tag.tag_type == TagType.MOOD:
            metadata['mood'] = tag.value
        elif tag.tag_type == TagType.FOCUS:
            metadata['visual_focus'] = tag.value
        elif tag.tag_type == TagType.TRANSITION:
            metadata['transition'] = tag.value
        elif tag.tag_type == TagType.STYLE:
            metadata['style_hint'] = tag.value
        elif tag.tag_type == TagType.LIPSYNC:
            metadata['lip_sync_enabled'] = True
        elif tag.tag_type == TagType.TEMPO:
            metadata['tempo_hint'] = tag.value
        elif tag.tag_type == TagType.TIME:
            time_seconds = parse_time_value(tag.value)
            if time_seconds is not None:
                metadata['timestamp'] = time_seconds
                metadata['timestamp_raw'] = tag.value

    return metadata


def inject_whisper_timestamps(
    text: str,
    word_timestamps: List[Dict[str, Any]],
    interval_seconds: float = 5.0,
    at_line_starts: bool = True
) -> str:
    """
    Inject time tags into text based on Whisper word timestamps.

    This is used to show timing information to the user when Whisper
    data is available. Time tags are inserted at regular intervals.

    Args:
        text: The lyrics/text to annotate
        word_timestamps: List of dicts with 'text', 'start_time', 'end_time'
        interval_seconds: Minimum seconds between time tags (default 5s)
        at_line_starts: If True, only insert at line beginnings

    Returns:
        Text with {time: MM:SS} tags inserted
    """
    if not word_timestamps:
        return text

    lines = text.split('\n')
    result_lines = []

    # Build a mapping of words to their timing
    word_timing_map = {}
    for wt in word_timestamps:
        word = wt.get('text', '').strip().lower()
        if word:
            # Store first occurrence timing for each word
            if word not in word_timing_map:
                word_timing_map[word] = wt.get('start_time', 0.0)

    last_time_tag = -interval_seconds  # Start negative to allow first tag

    for line in lines:
        if not line.strip():
            result_lines.append(line)
            continue

        # Find first word in this line
        words = line.split()
        if not words:
            result_lines.append(line)
            continue

        first_word = words[0].strip().lower()
        # Remove punctuation for matching
        first_word_clean = ''.join(c for c in first_word if c.isalnum())

        # Try to find timing for this word
        word_time = word_timing_map.get(first_word_clean)

        if word_time is not None and (word_time - last_time_tag) >= interval_seconds:
            # Insert time tag at start of line
            time_str = format_time_value(word_time, include_decimals=False)
            if at_line_starts:
                result_lines.append(f"{{time: {time_str}}} {line}")
            else:
                result_lines.append(f"{{time: {time_str}}}\n{line}")
            last_time_tag = word_time
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


def extract_time_tags(text: str) -> List[Tuple[int, float]]:
    """
    Extract all time tags from text with their line numbers.

    Returns:
        List of (line_number, seconds) tuples
    """
    parser = TagParser()
    result = parser.parse(text)

    time_tags = []
    for tag in result.tags:
        if tag.tag_type == TagType.TIME:
            seconds = parse_time_value(tag.value)
            if seconds is not None:
                time_tags.append((tag.line_number, seconds))

    return sorted(time_tags, key=lambda x: x[0])
