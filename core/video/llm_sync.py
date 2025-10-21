"""
LLM-based synchronization for lyrics and timing.
"""

import json
import re
import base64
from pathlib import Path
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
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None, config: Optional[Dict] = None):
        """
        Initialize LLM sync assistant.
        
        Args:
            provider: LLM provider (openai, claude, gemini, etc.)
            model: Specific model to use
            config: Optional configuration with API keys
        """
        self.provider = provider
        self.model = model
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize LLM provider if available
        self.llm_provider = None
        if provider and model:
            try:
                from .prompt_engine import UnifiedLLMProvider
                self.llm_provider = UnifiedLLMProvider(config)
            except ImportError:
                self.logger.warning("Could not import UnifiedLLMProvider")
    
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
    
    def sync_with_llm(self, lyrics: str, audio_path: Optional[str] = None, 
                      total_duration: Optional[float] = None,
                      sections: Optional[Dict[str, List[Tuple[float, float]]]] = None) -> List[TimedLyric]:
        """
        Use actual LLM API to sync lyrics with audio.
        
        Args:
            lyrics: Full lyrics text (without section markers)
            audio_path: Path to audio file
            total_duration: Total duration of the audio in seconds
            sections: Optional MIDI section timing data
            
        Returns:
            List of timed lyrics
        """
        self.logger.info(f"LLM sync requested with provider: {self.provider}, model: {self.model}")
        
        # Log input parameters
        self.logger.info("=== SYNC PARAMETERS ===")
        self.logger.info(f"Audio path: {audio_path if audio_path else 'None'}")
        self.logger.info(f"Total duration: {total_duration:.2f}s" if total_duration else "No duration specified")
        self.logger.info(f"Number of lyric lines: {len(lyrics.splitlines())}")
        self.logger.info(f"Sections available: {list(sections.keys()) if sections else 'None'}")
        self.logger.info("Lyrics to sync:")
        for i, line in enumerate(lyrics.splitlines()[:5], 1):  # Show first 5 lines
            self.logger.info(f"  Line {i}: {line}")
        if len(lyrics.splitlines()) > 5:
            self.logger.info(f"  ... and {len(lyrics.splitlines()) - 5} more lines")
        self.logger.info("=== END SYNC PARAMETERS ===")
        
        # If no LLM provider or not properly configured, fall back to estimation
        if not self.llm_provider or not self.llm_provider.is_available():
            self.logger.warning("LLM provider not available, using fallback timing estimation")
            lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
            return self.estimate_lyric_timing(lines, total_duration or 120.0, sections)
        
        try:
            # Prepare the prompt for the LLM
            system_prompt = (
                "You are an expert at synchronizing lyrics with audio. "
                "Analyze the provided lyrics and audio information to create precise timing for each lyric line. "
                "Consider the rhythm, beats, and natural pauses in speech/singing. "
                "Return a JSON array where each object has: "
                '{"text": "lyric line", "start_time": seconds_as_float, "end_time": seconds_as_float}'
            )
            
            # Build the user message
            user_message = f"""Synchronize these lyrics with the audio:

Total Duration: {total_duration:.2f} seconds

Lyrics:
{lyrics}
"""
            
            # Add MIDI section information if available
            if sections:
                user_message += "\n\nMIDI Section Timing:\n"
                for section_type, timings in sections.items():
                    for start, end in timings:
                        user_message += f"- {section_type}: {start:.2f}s - {end:.2f}s\n"
            
            # If we have audio file, mention it (though most LLMs can't process audio directly yet)
            if audio_path and Path(audio_path).exists():
                audio_filename = Path(audio_path).name
                user_message += f"\n\nAudio file: {audio_filename}"
                self.logger.info(f"Sending audio filename to LLM: {audio_filename}")
                self.logger.info(f"Full audio path: {audio_path}")
                # Note: Future enhancement - when LLMs support audio, we can encode and send the audio file
                # For now, we just use the filename as context
            else:
                self.logger.info("No audio file to send to LLM")
            
            user_message += "\n\nProvide timing for each lyric line as a JSON array."
            
            # Call the LLM
            self.logger.info("Calling LLM for lyric synchronization")
            self.logger.info("=== LLM REQUEST ===")
            self.logger.info(f"System prompt (FULL, {len(system_prompt)} chars):")
            self.logger.info(system_prompt)
            self.logger.info(f"User message (FULL, {len(user_message)} chars):")
            self.logger.info(user_message)
            self.logger.info("=== END LLM REQUEST ===")
            
            import time
            api_start = time.time()
            
            # Use litellm through the UnifiedLLMProvider
            if self.provider == 'lmstudio':
                model_id = self.model
            else:
                prefix = self.llm_provider.PROVIDER_PREFIXES.get(self.provider.lower(), '')
                model_id = f"{prefix}{self.model}" if prefix else self.model
            
            self.logger.info(f"Making LLM API call with model: {model_id}")
            response = self.llm_provider.litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,  # Lower temperature for more consistent timing
                response_format={"type": "json_object"} if self.provider == "openai" else None
            )
            
            api_elapsed = time.time() - api_start
            self.logger.info(f"LLM API call completed in {api_elapsed:.1f} seconds")
            
            response_text = response.choices[0].message.content.strip()
            self.logger.info("=== LLM RESPONSE ===")
            self.logger.info(f"Response length: {len(response_text)} characters")
            self.logger.info(f"Full response:")
            self.logger.info(response_text)
            self.logger.info("=== END LLM RESPONSE ===")
            
            # Parse the JSON response
            try:
                # Try to extract JSON from the response
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                
                timing_data = json.loads(response_text)
                
                # Handle both array and object with array
                if isinstance(timing_data, dict) and 'lyrics' in timing_data:
                    timing_data = timing_data['lyrics']
                elif isinstance(timing_data, dict) and 'timings' in timing_data:
                    timing_data = timing_data['timings']
                
                # Convert to TimedLyric objects
                timed_lyrics = []
                self.logger.info(f"Parsing {len(timing_data)} timing entries from LLM response")
                for i, item in enumerate(timing_data):
                    if isinstance(item, dict) and 'text' in item:
                        timed_lyric = TimedLyric(
                            text=item['text'],
                            start_time=float(item.get('start_time', 0)),
                            end_time=float(item.get('end_time', 0)),
                            section_type=item.get('section_type')
                        )
                        timed_lyrics.append(timed_lyric)
                        if i < 3 or i >= len(timing_data) - 3:  # Log first 3 and last 3
                            self.logger.debug(f"  Entry {i}: '{timed_lyric.text[:40]}...' @ {timed_lyric.start_time:.2f}-{timed_lyric.end_time:.2f}s")
                
                if timed_lyrics:
                    self.logger.info(f"Successfully synchronized {len(timed_lyrics)} lyrics using LLM")
                    # Log sample of timings
                    if len(timed_lyrics) > 0:
                        first = timed_lyrics[0]
                        last = timed_lyrics[-1]
                        self.logger.debug(f"First lyric: '{first.text[:30]}...' at {first.start_time:.2f}-{first.end_time:.2f}s")
                        self.logger.debug(f"Last lyric: '{last.text[:30]}...' at {last.start_time:.2f}-{last.end_time:.2f}s")
                    return timed_lyrics
                else:
                    self.logger.warning("No valid timing data in LLM response")
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse LLM JSON response: {e}")
                self.logger.error(f"Response that failed to parse: {response_text[:1000]}...")
            
        except Exception as e:
            self.logger.error(f"LLM sync failed: {e}")
            self.logger.error(f"Error type: {type(e).__name__}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
        
        # Fall back to estimation if LLM sync fails
        self.logger.info("Falling back to timing estimation")
        lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
        return self.estimate_lyric_timing(lines, total_duration or 120.0, sections)