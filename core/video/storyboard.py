"""
Storyboard generation and scene management for video projects.
Handles lyric/text parsing, scene creation, and timing allocation.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
import logging

from .project import Scene


class InputFormat(Enum):
    """Input text format types"""
    TIMESTAMPED = "timestamped"  # [mm:ss] or [mm:ss.mmm] format
    STRUCTURED = "structured"  # # Verse, # Chorus format
    PLAIN = "plain"  # Plain text, no structure


@dataclass
class ParsedLine:
    """A parsed line from input text"""
    text: str
    timestamp: Optional[float] = None  # in seconds
    section: Optional[str] = None  # e.g., "Verse 1", "Chorus"
    line_number: int = 0


class LyricParser:
    """Parse lyrics/text in various formats"""
    
    # Regex patterns for different formats
    TIMESTAMP_PATTERN = re.compile(r'^\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$')
    SECTION_PATTERN = re.compile(r'^#\s*(.+)$')
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_format(self, text: str) -> InputFormat:
        """
        Auto-detect the format of input text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Detected InputFormat
        """
        lines = text.strip().split('\n')
        
        # Check for timestamps
        timestamp_count = 0
        section_count = 0
        
        for line in lines[:20]:  # Check first 20 lines
            if self.TIMESTAMP_PATTERN.match(line):
                timestamp_count += 1
            elif self.SECTION_PATTERN.match(line):
                section_count += 1
        
        # Determine format based on patterns found
        if timestamp_count > len(lines) * 0.3:  # >30% have timestamps
            return InputFormat.TIMESTAMPED
        elif section_count > 0:
            return InputFormat.STRUCTURED
        else:
            return InputFormat.PLAIN
    
    def parse_timestamped(self, text: str) -> List[ParsedLine]:
        """
        Parse timestamped format: [mm:ss] or [mm:ss.mmm]
        
        Args:
            text: Input text with timestamps
            
        Returns:
            List of parsed lines with timestamps
        """
        lines = []
        line_number = 0
        
        for raw_line in text.strip().split('\n'):
            line_number += 1
            
            # Skip empty lines
            if not raw_line.strip():
                continue
            
            # Try to match timestamp pattern
            match = self.TIMESTAMP_PATTERN.match(raw_line)
            
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                milliseconds = int(match.group(3) or 0)
                text_content = match.group(4).strip()
                
                # Convert to total seconds
                timestamp = minutes * 60 + seconds + milliseconds / 1000.0
                
                if text_content:  # Only add if there's actual content
                    lines.append(ParsedLine(
                        text=text_content,
                        timestamp=timestamp,
                        line_number=line_number
                    ))
            else:
                # Line without timestamp - add as-is
                stripped = raw_line.strip()
                if stripped and not stripped.startswith('['):
                    lines.append(ParsedLine(
                        text=stripped,
                        line_number=line_number
                    ))
        
        return lines
    
    def parse_structured(self, text: str) -> List[ParsedLine]:
        """
        Parse structured format: # Verse, # Chorus, etc.
        
        Args:
            text: Input text with section markers
            
        Returns:
            List of parsed lines with sections
        """
        lines = []
        current_section = None
        line_number = 0
        
        for raw_line in text.strip().split('\n'):
            line_number += 1
            
            # Skip empty lines
            if not raw_line.strip():
                continue
            
            # Check for section marker
            section_match = self.SECTION_PATTERN.match(raw_line)
            
            if section_match:
                current_section = section_match.group(1).strip()
            else:
                # Regular line within a section
                stripped = raw_line.strip()
                if stripped:
                    lines.append(ParsedLine(
                        text=stripped,
                        section=current_section,
                        line_number=line_number
                    ))
        
        return lines
    
    def parse_plain(self, text: str) -> List[ParsedLine]:
        """
        Parse plain text (no timestamps or structure).
        
        Args:
            text: Plain input text
            
        Returns:
            List of parsed lines
        """
        lines = []
        line_number = 0
        current_section = None
        
        for raw_line in text.strip().split('\n'):
            line_number += 1
            stripped = raw_line.strip()
            
            # Check if this is a section marker even in plain format
            if stripped and stripped.startswith('[') and stripped.endswith(']'):
                # Extract section name for metadata but keep the line
                current_section = stripped[1:-1].strip()
            
            if stripped:
                lines.append(ParsedLine(
                    text=stripped,
                    line_number=line_number,
                    section=current_section if not (stripped.startswith('[') and stripped.endswith(']')) else current_section
                ))
        
        return lines
    
    def parse(self, text: str, format_hint: Optional[InputFormat] = None) -> List[ParsedLine]:
        """
        Parse input text in any format.
        
        Args:
            text: Input text to parse
            format_hint: Optional format hint, auto-detects if None
            
        Returns:
            List of parsed lines
        """
        if not text or not text.strip():
            return []
        
        # Determine format
        if format_hint is None:
            format_hint = self.detect_format(text)
        
        self.logger.info(f"Parsing text as {format_hint.value} format")
        
        # Parse based on format
        if format_hint == InputFormat.TIMESTAMPED:
            return self.parse_timestamped(text)
        elif format_hint == InputFormat.STRUCTURED:
            return self.parse_structured(text)
        else:
            return self.parse_plain(text)


class TimingEngine:
    """Calculate and allocate timing for scenes"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize timing engine.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        
        # Default timing presets (seconds per scene)
        self.presets = {
            "fast": 2.5,
            "medium": 4.0,
            "slow": 6.0
        }
        
        if config and "timing_presets" in config:
            self.presets.update(config["timing_presets"])
        
        self.default_scene_duration = 4.0  # seconds
        self.min_scene_duration = 1.0
        self.max_scene_duration = 10.0
    
    def calculate_durations_from_timestamps(self, 
                                           parsed_lines: List[ParsedLine]) -> List[float]:
        """
        Calculate scene durations from timestamps.
        
        Args:
            parsed_lines: Lines with timestamps
            
        Returns:
            List of durations in seconds
        """
        durations = []
        
        for i, line in enumerate(parsed_lines):
            if line.timestamp is not None:
                # Calculate duration to next timestamp
                if i < len(parsed_lines) - 1 and parsed_lines[i + 1].timestamp is not None:
                    duration = parsed_lines[i + 1].timestamp - line.timestamp
                else:
                    # Last timestamped line - use default duration
                    duration = self.default_scene_duration
                
                # Clamp to reasonable range
                duration = max(self.min_scene_duration, 
                             min(duration, self.max_scene_duration))
                durations.append(duration)
            else:
                # No timestamp - use default
                durations.append(self.default_scene_duration)
        
        return durations
    
    def calculate_durations_with_target(self,
                                       line_count: int,
                                       target_duration: str,
                                       line_weights: Optional[List[float]] = None) -> List[float]:
        """
        Calculate scene durations to match a target total duration.
        
        Args:
            line_count: Number of lines/scenes
            target_duration: Target duration in "hh:mm:ss" or "mm:ss" format
            line_weights: Optional weights for each line (for uneven distribution)
            
        Returns:
            List of durations in seconds
        """
        # Parse target duration
        total_seconds = self._parse_duration_string(target_duration)
        
        if line_weights is None:
            # Equal distribution
            line_weights = [1.0] * line_count
        
        # Normalize weights
        total_weight = sum(line_weights)
        if total_weight == 0:
            line_weights = [1.0] * line_count
            total_weight = line_count
        
        # Distribute time based on weights
        durations = []
        for weight in line_weights:
            duration = (weight / total_weight) * total_seconds
            # Clamp to reasonable range
            duration = max(self.min_scene_duration,
                         min(duration, self.max_scene_duration))
            durations.append(duration)
        
        # Adjust for clamping errors
        actual_total = sum(durations)
        if actual_total != total_seconds and actual_total > 0:
            scale_factor = total_seconds / actual_total
            durations = [d * scale_factor for d in durations]
        
        return durations
    
    def calculate_durations_with_preset(self,
                                       line_count: int,
                                       preset: str = "medium",
                                       line_weights: Optional[List[float]] = None) -> List[float]:
        """
        Calculate scene durations using a pacing preset.
        
        Args:
            line_count: Number of lines/scenes
            preset: Pacing preset ("fast", "medium", "slow")
            line_weights: Optional weights for each line
            
        Returns:
            List of durations in seconds
        """
        base_duration = self.presets.get(preset, self.default_scene_duration)
        
        if line_weights is None:
            # Simple case - same duration for all
            return [base_duration] * line_count
        
        # Weighted distribution around base duration
        durations = []
        avg_weight = sum(line_weights) / len(line_weights) if line_weights else 1.0
        
        for weight in line_weights:
            # Scale duration based on weight
            duration = base_duration * (weight / avg_weight)
            # Clamp to reasonable range
            duration = max(self.min_scene_duration,
                         min(duration, self.max_scene_duration))
            durations.append(duration)
        
        return durations
    
    def _parse_duration_string(self, duration_str: str) -> float:
        """
        Parse duration string to seconds.
        
        Args:
            duration_str: Duration in "hh:mm:ss" or "mm:ss" format
            
        Returns:
            Total seconds
        """
        parts = duration_str.strip().split(':')
        
        if len(parts) == 3:  # hh:mm:ss
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:  # mm:ss
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        elif len(parts) == 1:  # seconds
            return float(parts[0])
        else:
            raise ValueError(f"Invalid duration format: {duration_str}")
    
    def calculate_line_weights(self, parsed_lines: List[ParsedLine]) -> List[float]:
        """
        Calculate relative weights for lines based on content.
        
        Args:
            parsed_lines: Parsed input lines
            
        Returns:
            List of weights (higher = more important/longer)
        """
        weights = []
        
        for line in parsed_lines:
            # Base weight
            weight = 1.0
            
            # Adjust based on line length (longer lines might need more time)
            char_count = len(line.text)
            if char_count > 100:
                weight *= 1.3
            elif char_count > 50:
                weight *= 1.1
            elif char_count < 20:
                weight *= 0.8
            
            # Adjust based on section (if structured)
            if line.section:
                if "chorus" in line.section.lower():
                    weight *= 1.2  # Chorus might be more prominent
                elif "bridge" in line.section.lower():
                    weight *= 1.1
                elif "outro" in line.section.lower() or "intro" in line.section.lower():
                    weight *= 0.9
            
            weights.append(weight)
        
        return weights


class StoryboardGenerator:
    """Generate storyboard from parsed input"""
    
    def __init__(self, parser: Optional[LyricParser] = None, 
                 timing: Optional[TimingEngine] = None):
        """
        Initialize storyboard generator.
        
        Args:
            parser: LyricParser instance
            timing: TimingEngine instance
        """
        self.parser = parser or LyricParser()
        self.timing = timing or TimingEngine()
        self.logger = logging.getLogger(__name__)
    
    def generate_scenes(self,
                       text: str,
                       target_duration: Optional[str] = None,
                       preset: str = "medium",
                       format_hint: Optional[InputFormat] = None,
                       midi_timing_data: Optional[Any] = None,
                       sync_mode: str = "none",
                       snap_strength: float = 0.8) -> List[Scene]:
        """
        Generate scenes from input text.
        
        Args:
            text: Input text (lyrics, script, etc.)
            target_duration: Optional target duration "mm:ss" or "hh:mm:ss"
            preset: Pacing preset if no target duration
            format_hint: Optional format hint
            midi_timing_data: Optional MIDI timing data for synchronization
            sync_mode: Synchronization mode ("none", "beat", "measure", "section")
            snap_strength: How strongly to snap to MIDI boundaries (0.0-1.0)
            
        Returns:
            List of Scene objects
        """
        # Parse input text
        parsed_lines = self.parser.parse(text, format_hint)
        
        if not parsed_lines:
            self.logger.warning("No content found in input text")
            return []
        
        # Calculate durations
        if any(line.timestamp is not None for line in parsed_lines):
            # Has timestamps - use them
            durations = self.timing.calculate_durations_from_timestamps(parsed_lines)
        elif target_duration:
            # Has target duration - distribute time
            weights = self.timing.calculate_line_weights(parsed_lines)
            durations = self.timing.calculate_durations_with_target(
                len(parsed_lines), target_duration, weights
            )
        else:
            # Use preset pacing
            weights = self.timing.calculate_line_weights(parsed_lines)
            durations = self.timing.calculate_durations_with_preset(
                len(parsed_lines), preset, weights
            )
        
        # Create scenes (skip section markers)
        scenes = []
        scene_index = 0
        skipped_markers = 0
        for i, (line, duration) in enumerate(zip(parsed_lines, durations)):
            # Skip section markers like [Verse 1], [Chorus], etc.
            if line.text.strip().startswith('[') and line.text.strip().endswith(']'):
                self.logger.info(f"Skipping section marker: {line.text}")
                skipped_markers += 1
                continue
            
            scene = Scene(
                source=line.text,
                prompt=line.text,  # Initial prompt is the source text
                duration_sec=duration,
                order=scene_index
            )
            
            # Add metadata
            if line.timestamp is not None:
                scene.metadata["timestamp"] = line.timestamp
            if line.section:
                scene.metadata["section"] = line.section
            
            scenes.append(scene)
            scene_index += 1
        
        # Apply MIDI synchronization if available
        if midi_timing_data and sync_mode != "none":
            scenes = self.sync_scenes_to_midi(
                scenes, midi_timing_data, sync_mode, snap_strength
            )
        
        self.logger.info(f"Generated {len(scenes)} content scenes (skipped {skipped_markers} section markers), "
                        f"total duration: {sum(s.duration_sec for s in scenes):.1f} seconds")
        
        return scenes
    
    def sync_scenes_to_midi(self, scenes: List[Scene],
                           midi_timing_data: Any,
                           sync_mode: str,
                           snap_strength: float) -> List[Scene]:
        """
        Synchronize scenes to MIDI timing.
        
        Args:
            scenes: List of scenes to sync
            midi_timing_data: MIDI timing data
            sync_mode: "beat", "measure", or "section"
            snap_strength: How strongly to snap (0.0-1.0)
            
        Returns:
            List of synchronized scenes
        """
        try:
            from .midi_processor import MidiProcessor
            processor = MidiProcessor()
            
            # Convert scenes to dict format for processor
            scene_dicts = [
                {
                    'duration_sec': scene.duration_sec,
                    'source': scene.source,
                    'prompt': scene.prompt,
                    'order': scene.order,
                    'metadata': scene.metadata
                }
                for scene in scenes
            ]
            
            # Align to MIDI
            aligned = processor.align_scenes_to_beats(
                scene_dicts, midi_timing_data, sync_mode, snap_strength
            )
            
            # Convert back to Scene objects
            synced_scenes = []
            for scene_dict in aligned:
                scene = Scene(
                    source=scene_dict['source'],
                    prompt=scene_dict['prompt'],
                    duration_sec=scene_dict['duration_sec'],
                    order=scene_dict['order']
                )
                scene.metadata = scene_dict.get('metadata', {})
                
                # Add MIDI sync metadata
                if 'start_time' in scene_dict:
                    scene.metadata['midi_start'] = scene_dict['start_time']
                if 'end_time' in scene_dict:
                    scene.metadata['midi_end'] = scene_dict['end_time']
                if 'beat_markers' in scene_dict:
                    scene.metadata['beat_markers'] = scene_dict['beat_markers']
                
                synced_scenes.append(scene)
            
            self.logger.info(f"Synchronized {len(synced_scenes)} scenes to MIDI {sync_mode}")
            return synced_scenes
            
        except ImportError:
            self.logger.warning("MIDI processor not available, skipping synchronization")
            return scenes
        except Exception as e:
            self.logger.error(f"Failed to sync to MIDI: {e}")
            return scenes
    
    def split_long_scenes(self, scenes: List[Scene], 
                         max_duration: float = 8.0) -> List[Scene]:
        """
        Split scenes that are too long for video generation.
        
        Args:
            scenes: List of scenes
            max_duration: Maximum duration per scene (e.g., 8s for Veo)
            
        Returns:
            List of scenes with long ones split
        """
        result = []
        
        for scene in scenes:
            if scene.duration_sec <= max_duration:
                result.append(scene)
            else:
                # Split into multiple scenes
                num_splits = int(scene.duration_sec / max_duration) + 1
                split_duration = scene.duration_sec / num_splits
                
                for i in range(num_splits):
                    new_scene = Scene(
                        source=scene.source,
                        prompt=scene.prompt,
                        duration_sec=split_duration,
                        order=scene.order + i * 0.1  # Maintain relative order
                    )
                    new_scene.metadata = scene.metadata.copy()
                    new_scene.metadata["split_part"] = i + 1
                    new_scene.metadata["split_total"] = num_splits
                    
                    result.append(new_scene)
        
        # Re-number order
        for i, scene in enumerate(result):
            scene.order = i
        
        return result