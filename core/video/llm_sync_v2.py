"""
LLM-based synchronization for lyrics and timing - Version 2 with provider-specific prompts.
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
            provider: LLM provider (openai, gemini, etc.)
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
            # Use provider-specific implementations
            if self.provider.lower() == 'openai':
                return self._sync_with_openai(lyrics, audio_path, total_duration, sections)
            elif self.provider.lower() == 'gemini':
                return self._sync_with_gemini(lyrics, audio_path, total_duration, sections)
            else:
                # Default fallback for other providers
                self.logger.warning(f"Provider {self.provider} doesn't have specific sync implementation, using fallback")
                lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
                return self.estimate_lyric_timing(lines, total_duration or 120.0, sections)
                
        except Exception as e:
            self.logger.error(f"LLM sync failed: {e}")
            self.logger.error(f"Error type: {type(e).__name__}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Fall back to estimation if LLM sync fails
            self.logger.info("Falling back to timing estimation")
            lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
            return self.estimate_lyric_timing(lines, total_duration or 120.0, sections)
    
    def _sync_with_openai(self, lyrics: str, audio_path: Optional[str] = None,
                         total_duration: Optional[float] = None,
                         sections: Optional[Dict[str, List[Tuple[float, float]]]] = None) -> List[TimedLyric]:
        """
        OpenAI GPT-5 specific implementation using the prompt from Lyrics-TimeSync-Prompt-ASL-gpt-5.md
        """
        self.logger.info("Using OpenAI GPT-5 with Strict Lyric Timing Contract v1.0")
        
        try:
            # System prompt from the Strict Contract v1.0
            system_prompt = (
                'You are "Lyric Timing Aligner — Strict v1.0". Output must be a single JSON object '
                'that conforms exactly to the "Strict Lyric Timing Output Contract v1.0". '
                'Do not include any commentary or code fences. Do not split or merge lines. '
                'Preserve input order. Use integer milliseconds (units=ms). Round to nearest millisecond.'
            )
            
            # Count the lyric lines for validation
            lyric_lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
            num_lines = len(lyric_lines)
            
            # Build user message according to the contract
            user_message = (
                "TASK: Align each lyric line to the attached audio (MIDI optional). "
                "Return exactly one JSON object per the Strict Lyric Timing Output Contract v1.0.\n\n"
            )
            
            user_message += "ASSETS:\n"
            
            if audio_path and Path(audio_path).exists():
                audio_filename = Path(audio_path).name
                user_message += f"- audio: {audio_filename}\n"
                self.logger.info(f"Sending audio filename to LLM: {audio_filename}")
            else:
                user_message += "- audio: (not provided)\n"
            
            # Add MIDI timing data if available
            if sections:
                user_message += "- midi: timing data\n"
                midi_info = f"  Total Duration: {int(total_duration * 1000) if total_duration else 0} ms\n"
                for section_type, timings in sections.items():
                    for start, end in timings:
                        midi_info += f"  - {section_type}: {int(start * 1000)}ms - {int(end * 1000)}ms\n"
                user_message += midi_info
            
            user_message += f"- lyrics_text_utf8 (already filtered; lines in [] were removed on client):\n{lyrics}\n\n"
            
            user_message += "CONSTRAINTS:\n"
            user_message += "- One JSON entry per input line, in exact order.\n"
            user_message += "- start_ms/end_ms integers in milliseconds (or null if truly unalignable).\n"
            user_message += "- No other fields beyond the contract.\n"
            user_message += f"- Ensure 0 <= start_ms < end_ms <= {int(total_duration * 1000) if total_duration else 300000} (if not null).\n"
            user_message += "- Rounding rule: round(x * 1000) to nearest millisecond.\n\n"
            
            user_message += "OUTPUT:\n"
            user_message += "- Emit only the JSON object, with top-level keys [version, units, line_count, lyrics]. Nothing else."
            
            
            # Call the LLM
            self.logger.info("Calling OpenAI GPT-5 for lyric synchronization")
            self.logger.info("=== LLM REQUEST ===")
            self.logger.info(f"System prompt: {system_prompt[:200]}...")
            self.logger.info(f"User message ({len(user_message)} chars):")
            self.logger.info(user_message)
            self.logger.info("=== END LLM REQUEST ===")
            
            import time
            api_start = time.time()
            
            model_id = self.model
            
            self.logger.info(f"Making LLM API call with model: {model_id}")
            response = self.llm_provider.litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,  # Very low temperature for consistent timing
                response_format={"type": "json_object"}
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
                # Clean up response if needed (shouldn't happen with Strict Contract)
                if response_text.startswith('```'):
                    # Remove code fences
                    lines = response_text.split('\n')
                    response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
                
                timing_data = json.loads(response_text)
                
                # Check for Strict Contract v1.0 format first
                if isinstance(timing_data, dict) and timing_data.get('version') == '1.0' and timing_data.get('units') == 'ms':
                    # Strict Contract v1.0 format
                    self.logger.info("Detected Strict Lyric Timing Contract v1.0 format")
                    items = timing_data.get('lyrics', [])
                    is_strict_format = True
                else:
                    # Handle legacy formats for backward compatibility
                    is_strict_format = False
                    if isinstance(timing_data, list):
                        # Direct array format
                        items = timing_data
                    elif isinstance(timing_data, dict):
                        # Could be wrapped in an object
                        if 'captions' in timing_data:
                            # GPT-5 often returns this format
                            items = timing_data['captions']
                        elif 'lyrics' in timing_data:
                            items = timing_data['lyrics']
                        elif 'lyrics_timing' in timing_data:
                            items = timing_data['lyrics_timing']
                        else:
                            items = []
                    else:
                        items = []
                
                self.logger.info(f"Parsing {len(items)} timing entries from GPT-5 response")
                
                timed_lyrics = []
                for i, item in enumerate(items):
                    if is_strict_format:
                        # Strict Contract v1.0 format
                        if isinstance(item, dict) and 'text' in item and 'start_ms' in item and 'end_ms' in item:
                            # Times can be integers or null
                            start_ms = item['start_ms']
                            end_ms = item['end_ms']
                            
                            # Skip if times are null (unalignable)
                            if start_ms is None or end_ms is None:
                                self.logger.warning(f"Line {item.get('line_index', i+1)} has null timing, skipping")
                                continue
                            
                            start_time = float(start_ms) / 1000.0
                            end_time = float(end_ms) / 1000.0
                            
                            timed_lyric = TimedLyric(
                                text=item['text'],
                                start_time=start_time,
                                end_time=end_time,
                                section_type=None
                            )
                            timed_lyrics.append(timed_lyric)
                            
                            if i < 3 or i >= len(items) - 3:  # Log first 3 and last 3
                                self.logger.debug(f"  Line {item.get('line_index', i+1)}: '{timed_lyric.text[:40]}...' @ {timed_lyric.start_time:.2f}-{timed_lyric.end_time:.2f}s")
                    
                    elif isinstance(item, dict) and 'text' in item:
                        # Legacy format handling
                        # Convert times - could be in ms or seconds
                        if 'startMs' in item and 'endMs' in item:
                            # Camel case milliseconds format
                            start_time = float(item['startMs']) / 1000.0
                            end_time = float(item['endMs']) / 1000.0
                        elif 'start_ms' in item and 'end_ms' in item:
                            # Snake case milliseconds format
                            start_time = float(item['start_ms']) / 1000.0
                            end_time = float(item['end_ms']) / 1000.0
                        elif 'start' in item and 'end' in item:
                            # Simple seconds format (GPT-5 often uses this)
                            start_time = float(item['start'])
                            end_time = float(item['end'])
                        elif 'start_time' in item and 'end_time' in item:
                            # Verbose seconds format
                            start_time = float(item['start_time'])
                            end_time = float(item['end_time'])
                        else:
                            self.logger.warning(f"Item {i} missing timing fields: {item}")
                            continue
                        
                        timed_lyric = TimedLyric(
                            text=item['text'],
                            start_time=start_time,
                            end_time=end_time,
                            section_type=item.get('section_type')
                        )
                        timed_lyrics.append(timed_lyric)
                        
                        if i < 3 or i >= len(items) - 3:  # Log first 3 and last 3
                            self.logger.debug(f"  Entry {i}: '{timed_lyric.text[:40]}...' @ {timed_lyric.start_time:.2f}-{timed_lyric.end_time:.2f}s")
                
                if timed_lyrics:
                    self.logger.info(f"Successfully synchronized {len(timed_lyrics)} lyrics using GPT-5")
                    
                    if is_strict_format:
                        # Strict Contract v1.0 guarantees no fragmentation, one-to-one mapping
                        self.logger.info("Using Strict Contract v1.0 - no fragmentation merge needed")
                        
                        # Validate line count matches
                        if timing_data.get('line_count') != len(timed_lyrics):
                            self.logger.warning(f"Line count mismatch: expected {timing_data.get('line_count')}, got {len(timed_lyrics)}")
                        
                        return timed_lyrics
                    else:
                        # Legacy format: GPT-5 sometimes fragments lyrics for karaoke timing
                        # We need to merge them back to match original lyrics
                        if lyrics:
                            original_lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
                            if len(timed_lyrics) > len(original_lines):
                                self.logger.info(f"Legacy format with fragmentation detected ({len(timed_lyrics)} fragments for {len(original_lines)} lines)")
                                merged_lyrics = self._merge_fragmented_lyrics(timed_lyrics, original_lines)
                                if merged_lyrics:
                                    self.logger.info(f"Merged {len(timed_lyrics)} fragments into {len(merged_lyrics)} complete lyrics")
                                    return merged_lyrics
                    
                    return timed_lyrics
                else:
                    self.logger.warning("No valid timing data in GPT-5 response")
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse GPT-5 JSON response: {e}")
                self.logger.error(f"Response that failed to parse: {response_text[:1000]}...")
                
        except Exception as e:
            self.logger.error(f"GPT-5 sync failed: {e}")
            raise  # Re-raise to trigger fallback in main method
    
    def _sync_with_gemini(self, lyrics: str, audio_path: Optional[str] = None,
                          total_duration: Optional[float] = None,
                          sections: Optional[Dict[str, List[Tuple[float, float]]]] = None) -> List[TimedLyric]:
        """
        Gemini specific implementation using the prompt from Lyrics-TimeSync-Prompt-ASL-Gemini.md
        """
        self.logger.info("Using Gemini specific sync prompt")
        
        try:
            # Build the prompt based on Gemini's specifications
            system_prompt = (
                "You are an AI assistant specializing in audio and lyric synchronization. "
                "Your task is to analyze the audio to determine the precise timing of each line "
                "and return this information in a structured JSON format. "
                "The output MUST be a single JSON object containing one key 'lyrics' with an array of line objects."
            )
            
            # Build the user message based on Gemini's format
            user_message = "Analyze the following audio and lyrics to create time synchronization:\n\n"
            
            if audio_path and Path(audio_path).exists():
                audio_filename = Path(audio_path).name
                user_message += f"Audio file: {audio_filename}\n"
                self.logger.info(f"Sending audio filename to Gemini: {audio_filename}")
            
            if total_duration:
                user_message += f"Total Duration: {total_duration:.2f} seconds\n"
            
            if sections:
                user_message += "\nMIDI Section Timing:\n"
                for section_type, timings in sections.items():
                    for start, end in timings:
                        user_message += f"- {section_type}: {start:.2f}s - {end:.2f}s\n"
            
            # Count lyrics for format decision
            num_lines = len([line for line in lyrics.split('\n') if line.strip()])
            include_word_timing = num_lines <= 20  # Only include word-level for shorter songs
            
            user_message += f"\nLyrics to synchronize (ALL {num_lines} lines must be included):\n{lyrics}\n\n"
            
            if include_word_timing:
                user_message += (
                    "Return a JSON object with a 'lyrics' key containing an array of line objects. "
                    "Each line object must have: 'line' (text), 'startTime' (MM:SS.mmm), 'endTime' (MM:SS.mmm), "
                    "and 'words' array with word-level timing. Do not include code fences or commentary."
                )
            else:
                user_message += (
                    f"Return a JSON object with a 'lyrics' key containing an array of {num_lines} line objects. "
                    "Each line object must have: 'line' (text), 'startTime' (MM:SS.mmm), 'endTime' (MM:SS.mmm). "
                    "Skip word-level timing to ensure all lyrics fit in response. "
                    f"IMPORTANT: Include ALL {num_lines} lyrics with proper timing through the end of the song."
                )
            
            # Call the LLM
            self.logger.info("Calling Gemini for lyric synchronization")
            self.logger.info("=== LLM REQUEST ===")
            self.logger.info(f"System prompt: {system_prompt[:200]}...")
            self.logger.info(f"User message ({len(user_message)} chars):")
            self.logger.info(user_message)
            self.logger.info("=== END LLM REQUEST ===")
            
            import time
            api_start = time.time()
            
            # Use gemini prefix
            prefix = self.llm_provider.PROVIDER_PREFIXES.get('gemini', 'gemini/')
            model_id = f"{prefix}{self.model}" if prefix else self.model
            
            self.logger.info(f"Making LLM API call with model: {model_id}")
            response = self.llm_provider.litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1  # Low temperature for consistent timing
            )
            
            api_elapsed = time.time() - api_start
            self.logger.info(f"LLM API call completed in {api_elapsed:.1f} seconds")
            
            response_text = response.choices[0].message.content.strip()
            self.logger.info("=== LLM RESPONSE ===")
            self.logger.info(f"Response length: {len(response_text)} characters")
            self.logger.info(f"Full response:")
            self.logger.info(response_text)
            self.logger.info("=== END LLM RESPONSE ===")
            
            # Parse the Gemini JSON response
            try:
                # Clean up response if needed
                if response_text.startswith('```'):
                    lines = response_text.split('\n')
                    response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
                
                timing_data = json.loads(response_text)
                
                # Gemini format has 'lyrics' key with array of line objects
                if not isinstance(timing_data, dict) or 'lyrics' not in timing_data:
                    self.logger.warning("Gemini response doesn't have expected 'lyrics' key")
                    return []
                
                lines_data = timing_data['lyrics']
                timed_lyrics = []
                
                self.logger.info(f"Parsing {len(lines_data)} lines from Gemini response")
                
                for i, line_obj in enumerate(lines_data):
                    if isinstance(line_obj, dict) and 'line' in line_obj:
                        # Parse timestamps (format: MM:SS.mmm)
                        start_time = self._parse_timestamp(line_obj.get('startTime', '00:00.000'))
                        end_time = self._parse_timestamp(line_obj.get('endTime', '00:00.000'))
                        
                        # Skip entries with invalid timing
                        if start_time == 0 and end_time == 0:
                            self.logger.warning(f"Skipping line {i} with no timing: {line_obj.get('line', '')[:40]}...")
                            continue
                        
                        timed_lyric = TimedLyric(
                            text=line_obj['line'],
                            start_time=start_time,
                            end_time=end_time,
                            section_type=None
                        )
                        timed_lyrics.append(timed_lyric)
                        
                        if i < 3 or i >= len(lines_data) - 3:
                            self.logger.debug(f"  Line {i}: '{timed_lyric.text[:40]}...' @ {timed_lyric.start_time:.2f}-{timed_lyric.end_time:.2f}s")
                
                if timed_lyrics:
                    self.logger.info(f"Successfully synchronized {len(timed_lyrics)} lyrics using Gemini")
                    
                    # Check if Gemini returned fewer lyrics than expected
                    if lyrics:
                        original_lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
                        if len(timed_lyrics) < len(original_lines):
                            self.logger.warning(f"Gemini only returned {len(timed_lyrics)} of {len(original_lines)} expected lyrics")
                            self.logger.warning("Gemini may have hit response size limit due to word-level timing")
                            # Still return what we got - partial sync is better than none
                    
                    return timed_lyrics
                else:
                    self.logger.warning("No valid timing data in Gemini response")
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Gemini JSON response: {e}")
                self.logger.error(f"Response that failed to parse: {response_text[:1000]}...")
                
        except Exception as e:
            self.logger.error(f"Gemini sync failed: {e}")
            raise  # Re-raise to trigger fallback in main method
    
    def _merge_fragmented_lyrics(self, timed_fragments: List[TimedLyric], original_lines: List[str]) -> List[TimedLyric]:
        """
        Match timed fragments to original lyrics, handling both fragmentation and reordering.
        GPT-5 sometimes splits lyrics for karaoke-style timing and may reorder sections.
        """
        import difflib
        
        merged = []
        used_fragments = set()
        
        for original_line in original_lines:
            best_match_indices = []
            best_match_score = 0
            best_combined_text = ""
            
            # Try different combinations of fragments
            for start_idx in range(len(timed_fragments)):
                if start_idx in used_fragments:
                    continue
                
                # Try single fragment first
                fragment_text = timed_fragments[start_idx].text
                score = difflib.SequenceMatcher(None, fragment_text.lower(), original_line.lower()).ratio()
                
                if score > best_match_score:
                    best_match_score = score
                    best_match_indices = [start_idx]
                    best_combined_text = fragment_text
                
                # Try combining with subsequent fragments
                combined_text = fragment_text
                indices = [start_idx]
                
                for next_idx in range(start_idx + 1, min(start_idx + 4, len(timed_fragments))):  # Check up to 3 additional fragments
                    if next_idx in used_fragments:
                        break
                    
                    test_combined = combined_text + " " + timed_fragments[next_idx].text
                    score = difflib.SequenceMatcher(None, test_combined.lower(), original_line.lower()).ratio()
                    
                    if score > best_match_score:
                        best_match_score = score
                        best_match_indices = indices + [next_idx]
                        best_combined_text = test_combined
                    
                    # If we've already got a near-perfect match, stop
                    if score > 0.95:
                        break
                    
                    combined_text = test_combined
                    indices.append(next_idx)
            
            # Use the best match found
            if best_match_indices and best_match_score > 0.6:  # Threshold for accepting a match
                # Mark fragments as used
                for idx in best_match_indices:
                    used_fragments.add(idx)
                
                # Get timing from first and last fragments
                start_time = timed_fragments[best_match_indices[0]].start_time
                end_time = timed_fragments[best_match_indices[-1]].end_time
                
                merged.append(TimedLyric(
                    text=original_line,  # Use the original line text
                    start_time=start_time,
                    end_time=end_time,
                    section_type=None
                ))
                
                self.logger.debug(f"Matched: '{original_line[:40]}...' with {len(best_match_indices)} fragments @ {start_time:.2f}-{end_time:.2f}s (score: {best_match_score:.2f})")
            else:
                # No good match found, create a placeholder
                self.logger.warning(f"No match found for: '{original_line[:40]}...'")
        
        return merged
    
    def _lyrics_match(self, fragment_text: str, original_text: str) -> bool:
        """
        Check if fragmented text matches original line.
        Allows for minor differences in punctuation and case.
        """
        # Normalize for comparison
        frag_normalized = fragment_text.lower().strip()
        orig_normalized = original_text.lower().strip()
        
        # Remove punctuation for comparison
        import string
        for punct in string.punctuation:
            frag_normalized = frag_normalized.replace(punct, " ")
            orig_normalized = orig_normalized.replace(punct, " ")
        
        # Collapse multiple spaces
        frag_normalized = " ".join(frag_normalized.split())
        orig_normalized = " ".join(orig_normalized.split())
        
        # Check for exact match
        if frag_normalized == orig_normalized:
            return True
        
        # Check if fragment is complete enough (at least 90% of original)
        if frag_normalized in orig_normalized and len(frag_normalized) >= len(orig_normalized) * 0.9:
            return True
        
        return False
    
    def _parse_timestamp(self, timestamp: str) -> float:
        """
        Parse timestamp in MM:SS.mmm format to seconds.
        """
        try:
            # Handle different formats
            if ':' in timestamp:
                parts = timestamp.split(':')
                if len(parts) == 2:
                    # MM:SS.mmm format
                    minutes = int(parts[0])
                    seconds_parts = parts[1].split('.')
                    seconds = int(seconds_parts[0])
                    milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
                    return minutes * 60 + seconds + milliseconds / 1000.0
                elif len(parts) == 3:
                    # HH:MM:SS.mmm format
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds_parts = parts[2].split('.')
                    seconds = int(seconds_parts[0])
                    milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
                    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
            else:
                # Just seconds
                return float(timestamp)
        except:
            self.logger.warning(f"Failed to parse timestamp: {timestamp}")
            return 0.0
    
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