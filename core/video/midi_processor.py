"""
MIDI Processing Module for Video Project
Handles MIDI file analysis, timing extraction, and synchronization
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import json

try:
    import pretty_midi
    import mido
    MIDI_AVAILABLE = True
except (ImportError, Exception) as e:
    MIDI_AVAILABLE = False
    pretty_midi = None
    mido = None
    import logging
    logging.getLogger(__name__).debug(f"MIDI libraries not available: {e}")

logger = logging.getLogger(__name__)


@dataclass
class MidiTimingData:
    """Container for MIDI timing information used in synchronization"""
    file_path: Path
    tempo_bpm: float
    time_signature: str
    duration_sec: float
    tempo_changes: List[Tuple[float, float]] = field(default_factory=list)  # (time, bpm)
    time_signatures: List[Tuple[float, int, int]] = field(default_factory=list)  # (time, num, denom)
    beats: List[float] = field(default_factory=list)  # Beat timestamps in seconds
    measures: List[float] = field(default_factory=list)  # Measure/downbeat timestamps
    lyrics: List[Tuple[float, str]] = field(default_factory=list)  # (time, lyric_text)
    sections: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)  # Musical sections
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'file_path': str(self.file_path),
            'tempo_bpm': self.tempo_bpm,
            'time_signature': self.time_signature,
            'duration_sec': self.duration_sec,
            'tempo_changes': self.tempo_changes,
            'time_signatures': self.time_signatures,
            'beats': self.beats,
            'measures': self.measures,
            'lyrics': self.lyrics,
            'sections': self.sections
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MidiTimingData':
        """Create from dictionary"""
        data['file_path'] = Path(data['file_path'])
        return cls(**data)


class MidiProcessor:
    """Process MIDI files for timing extraction and synchronization"""
    
    def __init__(self):
        if not MIDI_AVAILABLE:
            raise ImportError(
                "MIDI processing libraries not installed. "
                "Please install: pip install pretty-midi mido"
            )
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def extract_timing(self, midi_path: Path) -> MidiTimingData:
        """
        Extract all timing information from a MIDI file
        
        Args:
            midi_path: Path to MIDI file
            
        Returns:
            MidiTimingData with all timing information
        """
        if not midi_path.exists():
            raise FileNotFoundError(f"MIDI file not found: {midi_path}")
        
        self.logger.info(f"Extracting timing from MIDI: {midi_path}")
        
        # Load MIDI with pretty_midi for high-level analysis
        pm = pretty_midi.PrettyMIDI(str(midi_path))
        
        # Get basic timing info
        beats = pm.get_beats().tolist()
        downbeats = pm.get_downbeats().tolist()
        
        # Extract tempo information
        tempo_changes = self._extract_tempo_changes(pm)
        initial_tempo = tempo_changes[0][1] if tempo_changes else 120.0
        
        # Extract time signatures
        time_signatures = self._extract_time_signatures(pm)
        initial_time_sig = f"{time_signatures[0][1]}/{time_signatures[0][2]}" if time_signatures else "4/4"
        
        # Extract lyrics if present
        lyrics = self._extract_lyrics_from_midi(midi_path)
        
        # Detect musical sections (verse, chorus, etc.)
        sections = self._detect_musical_sections(pm, downbeats)
        
        # Get total duration
        duration = pm.get_end_time()
        
        timing_data = MidiTimingData(
            file_path=midi_path,
            tempo_bpm=initial_tempo,
            time_signature=initial_time_sig,
            duration_sec=duration,
            tempo_changes=tempo_changes,
            time_signatures=time_signatures,
            beats=beats,
            measures=downbeats,
            lyrics=lyrics,
            sections=sections
        )
        
        self.logger.info(
            f"Extracted MIDI timing: {initial_tempo:.1f} BPM, "
            f"{initial_time_sig}, {duration:.1f}s, "
            f"{len(beats)} beats, {len(downbeats)} measures"
        )
        
        return timing_data
    
    def _extract_tempo_changes(self, pm: 'pretty_midi.PrettyMIDI') -> List[Tuple[float, float]]:
        """Extract tempo changes from MIDI"""
        tempo_changes = []
        
        # Get tempo change times and values
        tempi = pm.get_tempo_changes()
        if len(tempi[0]) > 0:
            for time, tempo in zip(tempi[0], tempi[1]):
                tempo_changes.append((float(time), float(tempo)))
        else:
            # Default tempo if none specified
            tempo_changes.append((0.0, 120.0))
        
        return tempo_changes
    
    def _extract_time_signatures(self, pm: 'pretty_midi.PrettyMIDI') -> List[Tuple[float, int, int]]:
        """Extract time signature changes from MIDI"""
        time_sigs = []
        
        # Access time signature changes
        if hasattr(pm, 'time_signature_changes'):
            for ts in pm.time_signature_changes:
                time_sigs.append((float(ts.time), ts.numerator, ts.denominator))
        
        if not time_sigs:
            # Default 4/4 if none specified
            time_sigs.append((0.0, 4, 4))
        
        return time_sigs
    
    def _extract_lyrics_from_midi(self, midi_path: Path) -> List[Tuple[float, str]]:
        """
        Extract lyric events from MIDI file using mido
        
        Args:
            midi_path: Path to MIDI file
            
        Returns:
            List of (time, lyric_text) tuples
        """
        lyrics = []
        
        try:
            mid = mido.MidiFile(str(midi_path))
            
            current_time = 0.0
            tempo = 500000  # Default tempo (120 BPM)
            
            for track in mid.tracks:
                current_time = 0.0
                
                for msg in track:
                    # Convert delta time to seconds
                    current_time += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
                    
                    # Update tempo if changed
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                    
                    # Extract lyrics
                    elif msg.type == 'lyrics':
                        lyrics.append((current_time, msg.text.strip()))
                        self.logger.debug(f"Found lyric at {current_time:.2f}s: {msg.text}")
            
            # Sort by time
            lyrics.sort(key=lambda x: x[0])
            
        except Exception as e:
            self.logger.warning(f"Could not extract lyrics from MIDI: {e}")
        
        return lyrics
    
    def _detect_musical_sections(self, pm: 'pretty_midi.PrettyMIDI', 
                                 measures: List[float]) -> Dict[str, List[Tuple[float, float]]]:
        """
        Detect musical sections (verse, chorus, bridge) based on patterns
        
        This is a simplified heuristic - could be enhanced with music21 for better analysis
        """
        sections = {
            'intro': [],
            'verse': [],
            'chorus': [],
            'bridge': [],
            'outro': []
        }
        
        if len(measures) < 4:
            return sections
        
        # Simple heuristic: divide song into sections based on measure patterns
        # This is very basic - in production you'd want more sophisticated analysis
        total_measures = len(measures)
        duration = pm.get_end_time()
        
        # Typical pop song structure (simplified)
        if total_measures >= 32:
            # Intro: first 4-8 measures
            intro_end = min(8, total_measures // 16)
            if intro_end > 0:
                sections['intro'].append((measures[0], measures[intro_end-1]))
            
            # Verses and choruses alternate
            section_length = 8  # typical section length in measures
            current_measure = intro_end
            verse_num = 0
            
            while current_measure < total_measures - 8:
                # Verse
                verse_end = min(current_measure + section_length, total_measures - 1)
                if verse_end > current_measure:
                    sections['verse'].append((measures[current_measure], measures[verse_end]))
                    current_measure = verse_end + 1
                
                # Chorus
                if current_measure < total_measures - 4:
                    chorus_end = min(current_measure + section_length, total_measures - 1)
                    if chorus_end > current_measure:
                        sections['chorus'].append((measures[current_measure], measures[chorus_end]))
                        current_measure = chorus_end + 1
                
                verse_num += 1
                if verse_num >= 2 and current_measure < total_measures - 16:
                    # Add a bridge after second verse/chorus
                    bridge_end = min(current_measure + 4, total_measures - 1)
                    if bridge_end > current_measure:
                        sections['bridge'].append((measures[current_measure], measures[bridge_end]))
                        current_measure = bridge_end + 1
            
            # Outro: last 4-8 measures
            if current_measure < total_measures:
                sections['outro'].append((measures[current_measure], measures[-1]))
        
        return sections
    
    def align_scenes_to_beats(self, scenes: List[Dict[str, Any]], 
                             timing: MidiTimingData,
                             alignment: str = "measure",
                             snap_strength: float = 0.8) -> List[Dict[str, Any]]:
        """
        Align scene transitions to musical boundaries
        
        Args:
            scenes: List of scene dictionaries with duration_sec
            timing: MIDI timing data
            alignment: "beat", "measure", or "section"
            snap_strength: 0.0-1.0, how strongly to snap to grid
            
        Returns:
            Updated scenes with aligned durations
        """
        if alignment == "measure":
            boundaries = timing.measures
        elif alignment == "beat":
            boundaries = timing.beats
        elif alignment == "section":
            # Get section boundaries
            boundaries = []
            for section_list in timing.sections.values():
                for start, end in section_list:
                    boundaries.extend([start, end])
            boundaries = sorted(set(boundaries))
        else:
            # No alignment
            return scenes
        
        if not boundaries:
            self.logger.warning("No boundaries found for alignment")
            return scenes
        
        # Align each scene's start and end to nearest boundaries
        aligned_scenes = []
        current_time = 0.0
        
        for scene in scenes:
            original_duration = scene.get('duration_sec', 4.0)
            target_end = current_time + original_duration
            
            # Find nearest boundary for the end time
            nearest_boundary = min(boundaries, key=lambda b: abs(b - target_end))
            
            # Apply snap strength (interpolate between original and snapped)
            snapped_end = current_time + (
                original_duration * (1 - snap_strength) +
                (nearest_boundary - current_time) * snap_strength
            )
            
            # Update scene duration
            new_duration = max(0.5, snapped_end - current_time)  # Minimum 0.5s
            
            aligned_scene = scene.copy()
            aligned_scene['duration_sec'] = new_duration
            aligned_scene['start_time'] = current_time
            aligned_scene['end_time'] = current_time + new_duration
            
            # Add beat markers within this scene
            scene_beats = [b for b in timing.beats if current_time <= b < current_time + new_duration]
            aligned_scene['beat_markers'] = scene_beats
            
            aligned_scenes.append(aligned_scene)
            current_time += new_duration
        
        self.logger.info(
            f"Aligned {len(scenes)} scenes to {alignment} boundaries "
            f"with {snap_strength:.0%} snap strength"
        )
        
        return aligned_scenes
    
    def extract_lyrics_with_timing(self, midi_path: Path, 
                                  lyrics_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract lyrics with word-level timing from MIDI
        If lyrics_text is provided, align it to MIDI timing
        
        Args:
            midi_path: Path to MIDI file
            lyrics_text: Optional lyrics text to align
            
        Returns:
            List of dicts with 'time', 'text', and 'duration' for each word/syllable
        """
        timing_data = self.extract_timing(midi_path)
        
        if timing_data.lyrics:
            # Use MIDI lyrics if available
            result = []
            for i, (time, text) in enumerate(timing_data.lyrics):
                # Calculate duration to next lyric or use default
                if i < len(timing_data.lyrics) - 1:
                    duration = timing_data.lyrics[i + 1][0] - time
                else:
                    duration = 0.5  # Default duration for last word
                
                result.append({
                    'time': time,
                    'text': text,
                    'duration': duration
                })
            return result
        
        elif lyrics_text:
            # Align provided lyrics to beats/measures
            return self._align_lyrics_to_timing(lyrics_text, timing_data)
        
        else:
            self.logger.warning("No lyrics found in MIDI or provided")
            return []
    
    def _align_lyrics_to_timing(self, lyrics_text: str, 
                               timing: MidiTimingData) -> List[Dict[str, Any]]:
        """
        Align lyrics text to MIDI timing (simplified version)
        In production, you'd want phoneme-level alignment
        """
        # Split lyrics into words
        words = []
        for line in lyrics_text.split('\n'):
            if line.strip():
                # Remove timestamps if present [00:00]
                import re
                line = re.sub(r'\[\d+:\d+\.?\d*\]', '', line).strip()
                if line:
                    words.extend(line.split())
        
        if not words or not timing.beats:
            return []
        
        # Simple alignment: distribute words across beats
        words_per_beat = max(1, len(words) // len(timing.beats))
        
        result = []
        word_index = 0
        
        for i, beat_time in enumerate(timing.beats):
            if word_index >= len(words):
                break
            
            # Get words for this beat
            beat_words = []
            for _ in range(words_per_beat):
                if word_index < len(words):
                    beat_words.append(words[word_index])
                    word_index += 1
            
            if beat_words:
                # Calculate duration to next beat
                if i < len(timing.beats) - 1:
                    beat_duration = timing.beats[i + 1] - beat_time
                else:
                    beat_duration = 0.5
                
                # Distribute words within beat
                word_duration = beat_duration / len(beat_words)
                for j, word in enumerate(beat_words):
                    result.append({
                        'time': beat_time + j * word_duration,
                        'text': word,
                        'duration': word_duration
                    })
        
        # Add remaining words if any
        if word_index < len(words):
            last_time = result[-1]['time'] + result[-1]['duration'] if result else 0.0
            remaining = words[word_index:]
            for i, word in enumerate(remaining):
                result.append({
                    'time': last_time + i * 0.5,
                    'text': word,
                    'duration': 0.5
                })

        return result


# Utility functions for Veo video generation

def snap_duration_to_veo(duration: float, allowed_durations: List[int] = None) -> int:
    """
    Snap a float duration to the nearest Veo-compatible duration.

    Args:
        duration: Target duration in seconds (float)
        allowed_durations: List of valid Veo durations (default: [4, 6, 8])

    Returns:
        Nearest allowed duration as integer

    Example:
        >>> snap_duration_to_veo(5.2)
        6
        >>> snap_duration_to_veo(3.8)
        4
        >>> snap_duration_to_veo(7.5)
        8
    """
    if allowed_durations is None:
        allowed_durations = [4, 6, 8]

    if not allowed_durations:
        raise ValueError("allowed_durations cannot be empty")

    # Find closest allowed duration
    closest = min(allowed_durations, key=lambda d: abs(d - duration))
    return closest


def align_scene_durations_for_veo(
    scenes: List[Dict[str, Any]],
    timing: MidiTimingData,
    alignment: str = "measure",
    allowed_durations: List[int] = None,
    total_duration_target: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Align scene durations to MIDI timing and snap to Veo-compatible values.

    This combines MIDI-driven timing with Veo's duration constraints (4, 6, or 8 seconds).

    Args:
        scenes: List of scene dictionaries with at least 'prompt' key
        timing: MIDI timing data
        alignment: "beat", "measure", or "section"
        allowed_durations: Valid Veo durations (default: [4, 6, 8])
        total_duration_target: Optional target total duration to match

    Returns:
        List of scenes with duration_sec set to Veo-compatible values

    Example:
        >>> scenes = [{"prompt": "Scene 1"}, {"prompt": "Scene 2"}]
        >>> timing = midi_processor.extract_timing(Path("song.mid"))
        >>> aligned = align_scene_durations_for_veo(scenes, timing, "measure")
        >>> [s["duration_sec"] for s in aligned]
        [8, 6, 8, 4]  # All values are 4, 6, or 8
    """
    if allowed_durations is None:
        allowed_durations = [4, 6, 8]

    if not MIDI_AVAILABLE:
        # Fallback: distribute duration evenly with Veo constraints
        target_duration = total_duration_target or (len(scenes) * 6)  # Default to 6s per scene
        duration_per_scene = target_duration / len(scenes)

        aligned_scenes = []
        for scene in scenes:
            scene_copy = scene.copy()
            scene_copy["duration_sec"] = snap_duration_to_veo(duration_per_scene, allowed_durations)
            aligned_scenes.append(scene_copy)

        return aligned_scenes

    # Use MIDI processor to align to musical boundaries (returns float durations)
    processor = MidiProcessor()
    midi_aligned_scenes = processor.align_scenes_to_beats(
        scenes=scenes,
        timing=timing,
        alignment=alignment,
        snap_strength=0.8  # Strong snap to musical grid
    )

    # Snap each scene's duration to nearest Veo-compatible value
    veo_aligned_scenes = []
    total_assigned = 0.0

    for i, scene in enumerate(midi_aligned_scenes):
        scene_copy = scene.copy()
        float_duration = scene.get("duration_sec", 6.0)

        # Snap to Veo duration
        veo_duration = snap_duration_to_veo(float_duration, allowed_durations)

        # If we have a total target, adjust last scenes to fit
        if total_duration_target and i == len(midi_aligned_scenes) - 1:
            remaining = total_duration_target - total_assigned
            if remaining > 0:
                veo_duration = snap_duration_to_veo(remaining, allowed_durations)

        scene_copy["duration_sec"] = veo_duration
        scene_copy["veo_duration"] = veo_duration  # Mark as Veo-compatible
        scene_copy["midi_aligned_duration"] = float_duration  # Preserve original MIDI timing

        veo_aligned_scenes.append(scene_copy)
        total_assigned += veo_duration

    return veo_aligned_scenes


def estimate_veo_scene_count(
    total_duration: float,
    average_scene_duration: int = 6,
    allowed_durations: List[int] = None
) -> int:
    """
    Estimate number of Veo scenes needed for a target total duration.

    Args:
        total_duration: Target video duration in seconds
        average_scene_duration: Average scene duration (default: 6s)
        allowed_durations: Valid Veo durations

    Returns:
        Estimated number of scenes

    Example:
        >>> estimate_veo_scene_count(45.0, average_scene_duration=6)
        8  # 8 scenes averaging 6s ≈ 48s (close to 45s)
    """
    if allowed_durations is None:
        allowed_durations = [4, 6, 8]

    if average_scene_duration not in allowed_durations:
        average_scene_duration = allowed_durations[len(allowed_durations) // 2]  # Use middle value

    # Simple estimation: divide by average
    estimate = max(1, round(total_duration / average_scene_duration))
    return estimate