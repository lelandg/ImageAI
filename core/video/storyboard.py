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
                 timing: Optional[TimingEngine] = None,
                 target_scene_duration: float = 8.0):
        """
        Initialize storyboard generator.

        Args:
            parser: LyricParser instance
            timing: TimingEngine instance
            target_scene_duration: Target duration per scene in seconds (default 8.0 for Veo 3.1)
        """
        self.parser = parser or LyricParser()
        self.timing = timing or TimingEngine()
        self.logger = logging.getLogger(__name__)
        self.target_scene_duration = target_scene_duration

    def _split_instrumental_vocal_pair(self, instrumental_scene: Scene, vocal_scene: Scene,
                                       max_duration: float = 8.0) -> List[Scene]:
        """
        Split an instrumental + vocal pair into multiple scenes of max_duration.

        For example, if instrumental is 9s and vocal is 7s (16s total), split into:
        - Scene 1: 8s (part of instrumental)
        - Scene 2: 8s (rest of instrumental + part of vocal)

        IMPORTANT: Properly calculates llm_start_time/llm_end_time for each split
        and adds timing hints (lyric_timings) to show when vocals appear.

        Args:
            instrumental_scene: The [Instrumental] scene
            vocal_scene: The following vocal scene
            max_duration: Maximum duration per scene

        Returns:
            List of split scenes with proper timing metadata
        """
        # Get absolute timing from LLM (if available)
        inst_start = instrumental_scene.metadata.get('llm_start_time', 0.0)
        vocal_end = vocal_scene.metadata.get('llm_end_time',
                                            inst_start + instrumental_scene.duration_sec + vocal_scene.duration_sec)

        total_duration = instrumental_scene.duration_sec + vocal_scene.duration_sec
        num_splits = int(total_duration / max_duration) + 1
        split_duration = max_duration  # Use exactly max_duration for all but potentially the last

        self.logger.info(f"Splitting instrumental ({instrumental_scene.duration_sec:.1f}s) + "
                        f"vocal ({vocal_scene.duration_sec:.1f}s) = {total_duration:.1f}s "
                        f"into {num_splits} scenes of ~{split_duration:.1f}s each")
        self.logger.info(f"  Absolute timing: {inst_start:.1f}s → {vocal_end:.1f}s")

        result = []
        remaining_instrumental = instrumental_scene.duration_sec
        remaining_vocal = vocal_scene.duration_sec
        current_time = inst_start  # Track absolute time position

        for i in range(num_splits):
            scene_duration = min(split_duration, remaining_instrumental + remaining_vocal)
            scene_start = current_time
            scene_end = current_time + scene_duration

            # Determine how much of instrumental and vocal to include in this split
            if remaining_instrumental >= split_duration:
                # This split contains only instrumental
                new_scene = Scene(
                    source="[Instrumental]",  # Pure instrumental, no lyrics
                    prompt=instrumental_scene.prompt,
                    duration_sec=scene_duration,
                    order=instrumental_scene.order + i * 0.1
                )
                new_scene.metadata = instrumental_scene.metadata.copy()
                new_scene.metadata['is_instrumental'] = True
                new_scene.metadata["split_part"] = i + 1
                new_scene.metadata["split_total"] = num_splits
                new_scene.metadata["split_type"] = "instrumental_only"
                new_scene.metadata["llm_start_time"] = scene_start
                new_scene.metadata["llm_end_time"] = scene_end

                if hasattr(instrumental_scene, 'environment'):
                    new_scene.environment = instrumental_scene.environment

                remaining_instrumental -= scene_duration

            elif remaining_instrumental > 0:
                # This split contains both instrumental and vocal
                vocal_start_in_scene = remaining_instrumental  # When vocals start within this scene
                vocal_duration_in_scene = min(scene_duration - remaining_instrumental, remaining_vocal)

                new_scene = Scene(
                    source=f"[Instrumental]\n{vocal_scene.source}",  # Show both parts
                    prompt=vocal_scene.prompt,  # Use vocal prompt for the combined scene
                    duration_sec=scene_duration,
                    order=instrumental_scene.order + i * 0.1
                )
                # Combine metadata
                new_scene.metadata = vocal_scene.metadata.copy()
                new_scene.metadata["split_part"] = i + 1
                new_scene.metadata["split_total"] = num_splits
                new_scene.metadata["split_type"] = "instrumental_and_vocal"
                new_scene.metadata["instrumental_duration"] = remaining_instrumental
                new_scene.metadata["vocal_duration"] = vocal_duration_in_scene
                new_scene.metadata["llm_start_time"] = scene_start
                new_scene.metadata["llm_end_time"] = scene_end

                # Add timing hints showing when each part appears
                new_scene.metadata["lyric_timings"] = [
                    {
                        "text": "[Instrumental]",
                        "start_sec": 0.0,
                        "end_sec": round(vocal_start_in_scene, 1),
                        "duration_sec": round(remaining_instrumental, 1),
                        "llm_start_time": scene_start,
                        "llm_end_time": scene_start + remaining_instrumental
                    },
                    {
                        "text": vocal_scene.source,
                        "start_sec": round(vocal_start_in_scene, 1),
                        "end_sec": round(vocal_start_in_scene + vocal_duration_in_scene, 1),
                        "duration_sec": round(vocal_duration_in_scene, 1),
                        "llm_start_time": scene_start + remaining_instrumental,
                        "llm_end_time": scene_start + remaining_instrumental + vocal_duration_in_scene
                    }
                ]

                if hasattr(vocal_scene, 'environment'):
                    new_scene.environment = vocal_scene.environment

                consumed_vocal = vocal_duration_in_scene
                remaining_vocal -= consumed_vocal
                remaining_instrumental = 0

            else:
                # This split contains only remaining vocal (continuation from previous scene)
                new_scene = Scene(
                    source=f"{vocal_scene.source} (continued)",  # Indicate this is a continuation
                    prompt=vocal_scene.prompt,
                    duration_sec=scene_duration,
                    order=instrumental_scene.order + i * 0.1
                )
                new_scene.metadata = vocal_scene.metadata.copy()
                new_scene.metadata["split_part"] = i + 1
                new_scene.metadata["split_total"] = num_splits
                new_scene.metadata["split_type"] = "vocal_continuation"
                new_scene.metadata["llm_start_time"] = scene_start
                new_scene.metadata["llm_end_time"] = scene_end

                # Add timing hint for continuation
                new_scene.metadata["lyric_timings"] = [
                    {
                        "text": vocal_scene.source,
                        "start_sec": 0.0,
                        "end_sec": round(scene_duration, 1),
                        "duration_sec": round(scene_duration, 1),
                        "llm_start_time": scene_start,
                        "llm_end_time": scene_end,
                        "note": f"Continuation from previous scene (part {i} of {num_splits})"
                    }
                ]

                if hasattr(vocal_scene, 'environment'):
                    new_scene.environment = vocal_scene.environment

                remaining_vocal -= scene_duration

            result.append(new_scene)
            current_time = scene_end  # Advance timeline

            self.logger.debug(f"  Split {i+1}/{num_splits}: {scene_duration:.1f}s ({scene_start:.1f}s → {scene_end:.1f}s) - {new_scene.metadata.get('split_type')}")

        return result

    def _batch_scenes_for_optimal_duration(self, scenes: List[Scene]) -> List[Scene]:
        """
        Batch consecutive scenes to aim for target_scene_duration per scene.

        This combines short lyric lines into longer scenes suitable for video generation.
        Respects section boundaries and aims for scenes close to target_scene_duration.

        SPECIAL HANDLING FOR INSTRUMENTALS:
        - [Instrumental] scenes are always combined with the immediately following vocal scene
        - If instrumental + vocal <= 8s, they're batched together
        - If instrumental + vocal > 8s, they're split into 8s chunks BEFORE batching
        - This ensures instrumental time is properly included in clip duration calculations

        Args:
            scenes: List of Scene objects (typically one per lyric line)

        Returns:
            List of batched Scene objects with combined lyrics and durations
        """
        if not scenes:
            return scenes

        batched_scenes = []
        current_batch = []
        current_duration = 0.0
        current_section = None
        current_environment = None  # Track environment to respect NEW SCENE markers

        self.logger.info(f"Batching {len(scenes)} scenes to aim for ~{self.target_scene_duration}s per scene")

        i = 0
        while i < len(scenes):
            scene = scenes[i]
            scene_duration = scene.duration_sec
            scene_section = scene.metadata.get('section')
            scene_environment = getattr(scene, 'environment', None)
            is_instrumental = scene.metadata.get('is_instrumental', False) or scene.source.strip() == '[Instrumental]'

            # Log environment tracking
            if scene_environment:
                self.logger.debug(f"Scene {i}: environment='{scene_environment}', "
                                f"current_env='{current_environment}', source='{scene.source[:30]}...'")

            # SPECIAL CASE: If this is an [Instrumental], peek ahead and combine with next vocal
            if is_instrumental:
                # Check if there's a next scene and if it's a vocal
                has_next = i + 1 < len(scenes)
                if has_next:
                    next_scene = scenes[i + 1]
                    next_is_instrumental = next_scene.metadata.get('is_instrumental', False) or next_scene.source.strip() == '[Instrumental]'
                else:
                    next_is_instrumental = True  # No next scene, treat as standalone

                # Only combine with non-instrumental vocals
                if not next_is_instrumental and has_next:
                    combined_duration = scene_duration + next_scene.duration_sec
                    self.logger.info(f"Found instrumental ({scene_duration:.1f}s) + vocal ({next_scene.duration_sec:.1f}s) = {combined_duration:.1f}s")

                    # Check if we need to finalize current batch before adding instrumental + vocal
                    if current_batch and current_duration + combined_duration > self.target_scene_duration:
                        # Finalize current batch first
                        batched_scene = self._merge_scenes(current_batch)
                        batched_scenes.append(batched_scene)
                        self.logger.debug(f"Finalized batch before instrumental+vocal: {len(current_batch)} scenes → {current_duration:.1f}s")
                        current_batch = []
                        current_duration = 0.0

                    # Now handle instrumental + vocal pair
                    if combined_duration <= self.target_scene_duration:
                        # Combined duration fits in one clip - batch them together
                        current_batch.extend([scene, next_scene])
                        current_duration += combined_duration
                        current_section = next_scene.metadata.get('section')
                        current_environment = getattr(next_scene, 'environment', scene_environment)
                        self.logger.info(f"✓ Batching instrumental + vocal together ({combined_duration:.1f}s <= {self.target_scene_duration}s)")
                        i += 2  # Skip both scenes
                        continue
                    else:
                        # Combined duration exceeds limit - split the pair into max_duration chunks
                        self.logger.info(f"⚠️ Instrumental + vocal ({combined_duration:.1f}s) exceeds {self.target_scene_duration}s - splitting pair...")
                        split_scenes = self._split_instrumental_vocal_pair(scene, next_scene, self.target_scene_duration)

                        # Add the split scenes to results (they're already properly sized)
                        for split_scene in split_scenes:
                            if current_batch and current_duration + split_scene.duration_sec > self.target_scene_duration:
                                # Finalize current batch
                                batched_scene = self._merge_scenes(current_batch)
                                batched_scenes.append(batched_scene)
                                self.logger.debug(f"Finalized batch: {len(current_batch)} scenes → {current_duration:.1f}s")
                                current_batch = []
                                current_duration = 0.0

                            # Each split scene is already at or near max_duration, so add directly
                            batched_scenes.append(split_scene)
                            self.logger.debug(f"Added split scene: {split_scene.duration_sec:.1f}s")

                        i += 2  # Skip both original scenes
                        continue
                else:
                    # Standalone instrumental (no following vocal or followed by another instrumental)
                    if scene_duration > self.target_scene_duration:
                        # Split standalone instrumental into max_duration chunks
                        self.logger.info(f"Standalone instrumental ({scene_duration:.1f}s) exceeds {self.target_scene_duration}s - splitting...")
                        num_inst_splits = int(scene_duration / self.target_scene_duration) + 1

                        for inst_i in range(num_inst_splits):
                            inst_duration = min(self.target_scene_duration, scene_duration - (inst_i * self.target_scene_duration))
                            inst_start = scene.metadata.get('llm_start_time', 0) + (inst_i * self.target_scene_duration)
                            inst_end = inst_start + inst_duration

                            inst_scene = Scene(
                                source="[Instrumental]",
                                prompt=scene.prompt,
                                duration_sec=inst_duration,
                                order=scene.order + inst_i * 0.1
                            )
                            inst_scene.metadata = scene.metadata.copy()
                            inst_scene.metadata['is_instrumental'] = True
                            inst_scene.metadata["split_part"] = inst_i + 1
                            inst_scene.metadata["split_total"] = num_inst_splits
                            inst_scene.metadata["split_type"] = "instrumental_only"
                            inst_scene.metadata["llm_start_time"] = inst_start
                            inst_scene.metadata["llm_end_time"] = inst_end

                            if hasattr(scene, 'environment'):
                                inst_scene.environment = scene.environment

                            # Finalize current batch if needed
                            if current_batch and current_duration + inst_duration > self.target_scene_duration:
                                batched_scene = self._merge_scenes(current_batch)
                                batched_scenes.append(batched_scene)
                                self.logger.debug(f"Finalized batch: {len(current_batch)} scenes → {current_duration:.1f}s")
                                current_batch = []
                                current_duration = 0.0

                            # Add split instrumental directly (it's already at max duration)
                            batched_scenes.append(inst_scene)
                            self.logger.debug(f"Added standalone instrumental split {inst_i+1}/{num_inst_splits}: {inst_duration:.1f}s")

                        i += 1  # Skip this instrumental
                        continue
                    # else: Instrumental fits in 8s, fall through to normal processing

            # Check if this would exceed our target (STRICT: never exceed target_scene_duration)
            # For Veo 3.1, this ensures scenes are always <= 8.0 seconds
            would_exceed = current_duration + scene_duration > self.target_scene_duration

            # Check if section changed (don't cross section boundaries like Verse → Chorus)
            section_changed = (current_section is not None and
                             scene_section is not None and
                             scene_section != current_section)

            # Check if environment changed (don't cross NEW SCENE boundaries)
            # Only finalize if BOTH scenes have environments set (ignore None → None transitions)
            environment_changed = (current_environment is not None and
                                 scene_environment is not None and
                                 scene_environment != current_environment)

            if environment_changed:
                self.logger.info(f"Environment change detected at scene {i}: "
                               f"'{current_environment}' → '{scene_environment}', forcing batch finalization")

            # Decide whether to add to current batch or finalize it
            # Finalize if: duration would exceed OR section changed OR environment changed
            should_finalize = current_batch and (would_exceed or section_changed or environment_changed)

            if should_finalize:
                # Finalize current batch
                batched_scene = self._merge_scenes(current_batch)
                batched_scenes.append(batched_scene)

                # Determine the reason for finalization (for logging)
                reason = 'exceed' if would_exceed else ('environment change' if environment_changed else 'section change')
                self.logger.debug(f"Batched {len(current_batch)} scenes → {current_duration:.1f}s (reason: {reason})")

                # Start new batch
                current_batch = [scene]
                current_duration = scene_duration
                current_section = scene_section
                current_environment = scene_environment
            else:
                # Add to current batch
                current_batch.append(scene)
                current_duration += scene_duration
                # Update section if this scene has one
                if scene_section:
                    current_section = scene_section
                # Update environment if this scene has one
                if scene_environment:
                    current_environment = scene_environment

            i += 1

        # Finalize any remaining batch
        if current_batch:
            batched_scene = self._merge_scenes(current_batch)
            batched_scenes.append(batched_scene)
            self.logger.debug(f"Final batch: {len(current_batch)} scenes → {current_duration:.1f}s")

        self.logger.info(f"Batched {len(scenes)} scenes into {len(batched_scenes)} combined scenes")

        # DEBUG: Check environment preservation after batching
        for i, scene in enumerate(batched_scenes[:5]):
            env = getattr(scene, 'environment', None)
            self.logger.info(f"After batching - Scene {i}: environment='{env}', source='{scene.source[:40]}...'")

        # Log statistics and validate max duration
        if batched_scenes:
            avg_duration = sum(s.duration_sec for s in batched_scenes) / len(batched_scenes)
            min_duration = min(s.duration_sec for s in batched_scenes)
            max_duration = max(s.duration_sec for s in batched_scenes)
            self.logger.info(f"Scene durations - Avg: {avg_duration:.1f}s, Min: {min_duration:.1f}s, "
                           f"Max: {max_duration:.1f}s (target: {self.target_scene_duration:.1f}s)")

            # Validate that no scene exceeds the target (should never happen after split)
            over_limit = [s for s in batched_scenes if s.duration_sec > self.target_scene_duration]
            if over_limit:
                self.logger.error(f"⚠️ WARNING: {len(over_limit)} batched scenes exceed {self.target_scene_duration}s limit!")
                for scene in over_limit:
                    self.logger.error(f"  - '{scene.source[:50]}...': {scene.duration_sec:.1f}s")

        return batched_scenes

    def _merge_scenes(self, scenes: List[Scene]) -> Scene:
        """
        Merge multiple scenes into one.

        Args:
            scenes: List of scenes to merge

        Returns:
            Single merged Scene object with timing information for each lyric line
        """
        if len(scenes) == 1:
            return scenes[0]

        # Combine source text with newlines
        combined_source = '\n'.join(scene.source for scene in scenes)

        # Combine prompts (if different from source)
        combined_prompt = '\n'.join(scene.prompt for scene in scenes)

        # Sum durations
        total_duration = sum(scene.duration_sec for scene in scenes)

        # Calculate timing information for each lyric line within the merged scene
        # IMPORTANT: Store both relative times (for scene-internal timing) AND absolute times (from LLM/MIDI)
        lyric_timings = []
        cumulative_time = 0.0
        for scene in scenes:
            start_time = cumulative_time
            end_time = cumulative_time + scene.duration_sec

            timing_info = {
                'text': scene.source,
                'start_sec': round(start_time, 1),      # Relative time within merged scene
                'end_sec': round(end_time, 1),          # Relative time within merged scene
                'duration_sec': round(scene.duration_sec, 1)
            }

            # Preserve absolute timing from LLM/MIDI sync (if available)
            if 'llm_start_time' in scene.metadata:
                timing_info['llm_start_time'] = scene.metadata['llm_start_time']
            if 'llm_end_time' in scene.metadata:
                timing_info['llm_end_time'] = scene.metadata['llm_end_time']

            lyric_timings.append(timing_info)
            cumulative_time = end_time

        # Use the order of the first scene
        merged_scene = Scene(
            source=combined_source,
            prompt=combined_prompt,
            duration_sec=total_duration,
            order=scenes[0].order
        )

        # Merge metadata
        merged_scene.metadata = scenes[0].metadata.copy()
        merged_scene.metadata['batched_count'] = len(scenes)
        merged_scene.metadata['original_scene_ids'] = [s.order for s in scenes]
        merged_scene.metadata['lyric_timings'] = lyric_timings  # Store timing for each lyric line

        # CRITICAL: Preserve precise timing from LLM/MIDI sync
        # Use llm_start_time from FIRST scene and llm_end_time from LAST scene
        first_scene = scenes[0]
        last_scene = scenes[-1]

        if 'llm_start_time' in first_scene.metadata:
            merged_scene.metadata['llm_start_time'] = first_scene.metadata['llm_start_time']

        if 'llm_end_time' in last_scene.metadata:
            merged_scene.metadata['llm_end_time'] = last_scene.metadata['llm_end_time']

        # Log timing for debugging
        if 'llm_start_time' in merged_scene.metadata and 'llm_end_time' in merged_scene.metadata:
            llm_duration = merged_scene.metadata['llm_end_time'] - merged_scene.metadata['llm_start_time']
            self.logger.debug(f"Merged scene timing: {merged_scene.metadata['llm_start_time']:.2f}s - "
                            f"{merged_scene.metadata['llm_end_time']:.2f}s (LLM duration: {llm_duration:.2f}s, "
                            f"Sum duration: {total_duration:.2f}s, diff: {abs(llm_duration - total_duration):.3f}s)")

            # Use the more precise LLM timing if available
            # The sum of durations might have accumulated rounding errors
            merged_scene.duration_sec = llm_duration

        # Copy environment from first scene (if set)
        if hasattr(scenes[0], 'environment') and scenes[0].environment:
            merged_scene.environment = scenes[0].environment

        return merged_scene

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
        current_environment = None  # Track current environment from NEW SCENE markers

        for i, (line, duration) in enumerate(zip(parsed_lines, durations)):
            # Check for NEW SCENE markers: === NEW SCENE: <environment> ===
            new_scene_match = re.match(r'^===\s*NEW SCENE:\s*(.+?)\s*===$', line.text.strip(), re.IGNORECASE)
            if new_scene_match:
                current_environment = new_scene_match.group(1).strip()
                self.logger.info(f"Found scene marker - Environment set to: '{current_environment}'")
                skipped_markers += 1
                continue

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

            # Set environment from current NEW SCENE marker (if any)
            if current_environment:
                scene.environment = current_environment
                self.logger.info(f"Scene {scene_index}: Applied environment '{current_environment}' to '{scene.source[:40]}...'")

            scenes.append(scene)
            scene_index += 1
        
        # Apply MIDI synchronization if available
        if midi_timing_data and sync_mode != "none":
            scenes = self.sync_scenes_to_midi(
                scenes, midi_timing_data, sync_mode, snap_strength
            )

        self.logger.info(f"Generated {len(scenes)} content scenes (skipped {skipped_markers} section markers), "
                        f"total duration: {sum(s.duration_sec for s in scenes):.1f} seconds")

        # NOTE: Splitting and batching are deferred to workspace_widget.py
        # This is because instrumental scenes are inserted AFTER scene generation,
        # and splitting/batching must happen AFTER instrumentals to maintain timing alignment

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
                    'metadata': scene.metadata,
                    'environment': getattr(scene, 'environment', '')  # Preserve environment
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

                # Restore environment attribute
                scene.environment = scene_dict.get('environment', '')

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

        NOTE: [Instrumental] scenes are NOT split here - they're handled during batching
        where they're combined with following vocal scenes and split as a pair if needed.

        Args:
            scenes: List of scenes
            max_duration: Maximum duration per scene (e.g., 8s for Veo)

        Returns:
            List of scenes with long ones split
        """
        result = []
        split_count = 0

        for scene in scenes:
            # Check if this is an instrumental scene
            is_instrumental = scene.metadata.get('is_instrumental', False) or scene.source.strip() == '[Instrumental]'

            if is_instrumental:
                # Don't split instrumental scenes here - they'll be handled during batching
                self.logger.info(f"Skipping split for [Instrumental] scene ({scene.duration_sec:.1f}s) - will be handled with next vocal")
                result.append(scene)
            elif scene.duration_sec <= max_duration:
                result.append(scene)
            else:
                # Split into multiple scenes
                num_splits = int(scene.duration_sec / max_duration) + 1
                split_duration = scene.duration_sec / num_splits

                self.logger.info(f"Splitting scene '{scene.source[:50]}...' ({scene.duration_sec:.1f}s) into {num_splits} parts of {split_duration:.1f}s each")
                split_count += 1

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

                    # Copy environment from original scene (if set)
                    if hasattr(scene, 'environment') and scene.environment:
                        new_scene.environment = scene.environment

                    result.append(new_scene)

        # Re-number order
        for i, scene in enumerate(result):
            scene.order = i

        if split_count > 0:
            self.logger.info(f"Split {split_count} non-instrumental scenes that exceeded {max_duration}s")

        return result