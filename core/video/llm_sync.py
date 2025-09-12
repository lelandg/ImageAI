"""
LLM-based synchronization for lyrics and timing.
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TimedLyric:
    """Represents a lyric line with timing information"""
    text: str
    start_time: float
    end_time: float
    section_type: Optional[str] = None


class LLMSyncAssistant:
    """Use LLMs to assist with audio/lyric alignment"""
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize LLM sync assistant.
        
        Args:
            provider: LLM provider (openai, claude, gemini, etc.)
            model: Specific model to use
        """
        self.provider = provider
        self.model = model
        self.logger = logging.getLogger(__name__)
    
    def estimate_lyric_timing(self, lyrics: List[str], total_duration: float, 
                             sections: Optional[Dict[str, List[Tuple[float, float]]]] = None) -> List[TimedLyric]:
        """
        Estimate timing for lyrics based on total duration and optional section markers.
        
        Args:
            lyrics: List of lyric lines
            total_duration: Total duration in seconds
            sections: Optional dict of section types to time ranges from MIDI
            
        Returns:
            List of TimedLyric objects with estimated timing
        """
        timed_lyrics = []
        
        if not lyrics:
            return timed_lyrics
        
        # If we have MIDI sections, use them to better distribute timing
        if sections:
            return self._sync_with_sections(lyrics, sections)
        
        # Otherwise, use simple even distribution with adjustments
        return self._simple_timing_distribution(lyrics, total_duration)
    
    def _simple_timing_distribution(self, lyrics: List[str], total_duration: float) -> List[TimedLyric]:
        """
        Simple timing distribution when no section information is available.
        """
        timed_lyrics = []
        
        # Filter out empty lines and section markers
        content_lines = []
        for line in lyrics:
            line = line.strip()
            if line and not self._is_section_marker(line):
                content_lines.append(line)
        
        if not content_lines:
            return timed_lyrics
        
        # Calculate base duration per line
        avg_duration = total_duration / len(content_lines)
        
        current_time = 0.0
        for i, line in enumerate(lyrics):
            line = line.strip()
            if not line:
                continue
            
            # Adjust duration based on line characteristics
            duration = self._estimate_line_duration(line, avg_duration)
            
            # Don't exceed total duration
            if current_time + duration > total_duration:
                duration = total_duration - current_time
            
            timed_lyrics.append(TimedLyric(
                text=line,
                start_time=current_time,
                end_time=min(current_time + duration, total_duration),
                section_type=self._detect_section_type(line)
            ))
            
            current_time += duration
            
            if current_time >= total_duration:
                break
        
        return timed_lyrics
    
    def _sync_with_sections(self, lyrics: List[str], sections: Dict[str, List[Tuple[float, float]]]) -> List[TimedLyric]:
        """
        Sync lyrics with MIDI section information.
        """
        timed_lyrics = []
        
        # Parse lyrics into sections
        lyric_sections = self._parse_lyric_sections(lyrics)
        
        # Match lyric sections to MIDI sections
        for section_type, section_lyrics in lyric_sections.items():
            if section_type.lower() in sections:
                midi_times = sections[section_type.lower()]
                
                # Distribute lyrics across matching MIDI sections
                if midi_times and section_lyrics:
                    # If multiple instances of the section (e.g., multiple choruses)
                    lyrics_per_instance = len(section_lyrics) / len(midi_times)
                    
                    for i, (start, end) in enumerate(midi_times):
                        # Determine which lyrics go in this instance
                        start_idx = int(i * lyrics_per_instance)
                        end_idx = int((i + 1) * lyrics_per_instance)
                        instance_lyrics = section_lyrics[start_idx:end_idx]
                        
                        if instance_lyrics:
                            duration_per_line = (end - start) / len(instance_lyrics)
                            current_time = start
                            
                            for line in instance_lyrics:
                                timed_lyrics.append(TimedLyric(
                                    text=line,
                                    start_time=current_time,
                                    end_time=min(current_time + duration_per_line, end),
                                    section_type=section_type
                                ))
                                current_time += duration_per_line
        
        # Sort by start time
        timed_lyrics.sort(key=lambda x: x.start_time)
        
        return timed_lyrics
    
    def _parse_lyric_sections(self, lyrics: List[str]) -> Dict[str, List[str]]:
        """
        Parse lyrics into sections based on markers like [Verse 1], [Chorus], etc.
        """
        sections = {}
        current_section = "intro"
        current_lines = []
        
        for line in lyrics:
            line = line.strip()
            if not line:
                continue
            
            if self._is_section_marker(line):
                # Save previous section
                if current_lines:
                    if current_section not in sections:
                        sections[current_section] = []
                    sections[current_section].extend(current_lines)
                    current_lines = []
                
                # Start new section
                current_section = self._extract_section_type(line)
            else:
                current_lines.append(line)
        
        # Save last section
        if current_lines:
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].extend(current_lines)
        
        return sections
    
    def _is_section_marker(self, line: str) -> bool:
        """Check if a line is a section marker."""
        return bool(re.match(r'^\[.*\]$', line.strip()))
    
    def _extract_section_type(self, marker: str) -> str:
        """Extract section type from marker."""
        match = re.match(r'^\[(.*?)\]', marker.strip())
        if match:
            section = match.group(1).lower()
            # Normalize section names
            if 'verse' in section:
                return 'verse'
            elif 'chorus' in section:
                return 'chorus'
            elif 'bridge' in section:
                return 'bridge'
            elif 'outro' in section:
                return 'outro'
            elif 'intro' in section:
                return 'intro'
            else:
                return section
        return 'unknown'
    
    def _detect_section_type(self, line: str) -> Optional[str]:
        """Detect section type from line content."""
        if self._is_section_marker(line):
            return self._extract_section_type(line)
        return None
    
    def _estimate_line_duration(self, line: str, base_duration: float) -> float:
        """
        Estimate duration for a line based on its characteristics.
        """
        # Section markers get minimal time
        if self._is_section_marker(line):
            return base_duration * 0.3
        
        # Adjust based on line length (more words = more time)
        word_count = len(line.split())
        if word_count < 5:
            return base_duration * 0.8
        elif word_count > 10:
            return base_duration * 1.3
        else:
            return base_duration
    
    async def sync_with_llm(self, lyrics: str, audio_features: Optional[Dict] = None) -> List[TimedLyric]:
        """
        Use actual LLM API to sync lyrics (future implementation).
        
        Args:
            lyrics: Full lyrics text
            audio_features: Optional audio analysis data
            
        Returns:
            List of timed lyrics
        """
        # This would connect to actual LLM APIs when implemented
        # For now, return a placeholder
        self.logger.info(f"LLM sync requested with provider: {self.provider}, model: {self.model}")
        
        # Parse lyrics into lines
        lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
        
        # Use simple distribution for now
        total_duration = 120.0  # Default 2 minutes
        if audio_features and 'duration' in audio_features:
            total_duration = audio_features['duration']
        
        return self.estimate_lyric_timing(lines, total_duration)