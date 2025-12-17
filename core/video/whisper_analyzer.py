"""Whisper-based audio analysis for lyrics extraction and timing."""

import logging
import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from difflib import SequenceMatcher

from .timing_models import WordTiming, TranscriptionResult, AlignmentResult

logger = logging.getLogger(__name__)

# Suppress noisy whisper_timestamped warnings (they're harmless internal DTW edge cases)
logging.getLogger("whisper_timestamped").setLevel(logging.ERROR)

# Whisper model sizes and their approximate memory requirements
WHISPER_MODELS = {
    "tiny": {"size_mb": 75, "vram_mb": 1000, "description": "Fastest, least accurate"},
    "base": {"size_mb": 142, "vram_mb": 1000, "description": "Good balance"},
    "small": {"size_mb": 466, "vram_mb": 2000, "description": "Better accuracy"},
    "medium": {"size_mb": 1500, "vram_mb": 5000, "description": "High accuracy"},
    "large": {"size_mb": 3000, "vram_mb": 10000, "description": "Best accuracy"},
}


class WhisperAnalyzer:
    """
    Analyzes audio using OpenAI Whisper to extract lyrics and word-level timestamps.

    This class provides:
    - Full transcription of audio to text
    - Word-level timing information
    - Alignment of provided lyrics with audio
    """

    def __init__(self, model_size: str = "base", device: str = None):
        """
        Initialize the Whisper analyzer.

        Args:
            model_size: Whisper model size (tiny/base/small/medium/large)
            device: Device to run on (cuda/cpu/None for auto-detect)
        """
        self.model_size = model_size
        self.device = device
        self._model = None
        self._whisper_module = None

    def _ensure_model_loaded(self) -> None:
        """Load the Whisper model if not already loaded."""
        if self._model is not None:
            return

        logger.info(f"Loading Whisper {self.model_size} model...")

        try:
            # Try whisper-timestamped first (better word-level timing)
            import whisper_timestamped as whisper
            self._whisper_module = whisper
            logger.info("Using whisper-timestamped for improved word timing")
        except ImportError:
            # Fall back to standard whisper
            try:
                import whisper
                self._whisper_module = whisper
                logger.info("Using standard whisper (install whisper-timestamped for better timing)")
            except ImportError:
                raise ImportError(
                    "Whisper is not installed. Install with: pip install openai-whisper "
                    "or pip install whisper-timestamped"
                )

        # Determine device
        if self.device is None:
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Auto-detected device: {self.device}")

        # Load model
        self._model = self._whisper_module.load_model(self.model_size, device=self.device)
        logger.info(f"Whisper {self.model_size} model loaded on {self.device}")

    def _ensure_ffmpeg_available(self) -> None:
        """Ensure FFmpeg is available for audio loading."""
        try:
            from .ffmpeg_utils import get_ffmpeg_path, ensure_ffmpeg

            # Check if FFmpeg is available
            available, message = ensure_ffmpeg(auto_install=True)
            if not available:
                raise RuntimeError(f"FFmpeg not available: {message}")

            # Get FFmpeg path and add its directory to PATH
            ffmpeg_path = get_ffmpeg_path()
            if ffmpeg_path:
                ffmpeg_dir = str(Path(ffmpeg_path).parent)
                current_path = os.environ.get('PATH', '')
                if ffmpeg_dir not in current_path:
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
                    logger.info(f"Added FFmpeg to PATH: {ffmpeg_dir}")

                # Also patch whisper's audio module to use full path
                # (Windows subprocess doesn't always pick up PATH changes)
                self._patch_whisper_ffmpeg(ffmpeg_path)
        except ImportError:
            logger.warning("ffmpeg_utils not available, assuming FFmpeg is in PATH")

    def _patch_whisper_ffmpeg(self, ffmpeg_path: str) -> None:
        """Patch whisper's audio module to use full FFmpeg path."""
        import subprocess
        import numpy as np

        def make_patched_load_audio(ffmpeg_exe: str):
            """Create a patched load_audio function with the ffmpeg path baked in."""
            def patched_load_audio(file: str, sr: int = 16000):
                """Load audio using full FFmpeg path."""
                cmd = [
                    ffmpeg_exe,
                    "-nostdin",
                    "-threads", "0",
                    "-i", file,
                    "-f", "s16le",
                    "-ac", "1",
                    "-acodec", "pcm_s16le",
                    "-ar", str(sr),
                    "-"
                ]
                logger.info(f"Running FFmpeg: {' '.join(cmd[:5])}...")
                try:
                    out = subprocess.run(
                        cmd, capture_output=True, check=True
                    ).stdout
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e

                return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
            return patched_load_audio

        patched_func = make_patched_load_audio(ffmpeg_path)

        # Patch the module we're actually using (whisper_timestamped or whisper)
        if self._whisper_module is not None:
            if not hasattr(self._whisper_module, '_original_load_audio'):
                self._whisper_module._original_load_audio = self._whisper_module.load_audio
                self._whisper_module.load_audio = patched_func
                logger.info(f"Patched {self._whisper_module.__name__}.load_audio")

        # Also patch whisper.audio for good measure
        try:
            import whisper.audio as whisper_audio
            if not hasattr(whisper_audio, '_original_load_audio'):
                whisper_audio._original_load_audio = whisper_audio.load_audio
                whisper_audio.load_audio = patched_func
                logger.info(f"Patched whisper.audio.load_audio to use: {ffmpeg_path}")
        except Exception as e:
            logger.warning(f"Could not patch whisper.audio module: {e}")

    def extract_lyrics(
        self,
        audio_path: Path,
        language: str = None,
        progress_callback: Callable[[str, float], None] = None
    ) -> TranscriptionResult:
        """
        Extract lyrics and word-level timestamps from audio.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en') or None for auto-detect
            progress_callback: Optional callback(message, progress_0_to_1)

        Returns:
            TranscriptionResult with full text and word timings
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if progress_callback:
            progress_callback("Loading Whisper model...", 0.1)

        self._ensure_model_loaded()

        if progress_callback:
            progress_callback("Transcribing audio...", 0.2)

        logger.info(f"Transcribing audio: {audio_path}")

        # Ensure FFmpeg is available (whisper uses it to load audio)
        self._ensure_ffmpeg_available()

        # Load and transcribe
        audio = self._whisper_module.load_audio(str(audio_path))

        # Get audio duration
        duration = len(audio) / 16000  # Whisper uses 16kHz

        # Build transcribe options based on which module we're using
        transcribe_options = {"verbose": False}
        if language:
            transcribe_options["language"] = language

        # whisper_timestamped uses transcribe_timestamped() and always provides word timestamps
        # standard whisper uses transcribe() and needs word_timestamps=True
        is_timestamped = self._whisper_module.__name__ == "whisper_timestamped"

        if is_timestamped:
            # whisper_timestamped.transcribe_timestamped() - no word_timestamps arg needed
            result = self._whisper_module.transcribe_timestamped(
                self._model,
                audio,
                **transcribe_options
            )
        else:
            # standard whisper.transcribe() - needs word_timestamps=True
            transcribe_options["word_timestamps"] = True
            result = self._whisper_module.transcribe(
                self._model,
                audio,
                **transcribe_options
            )

        if progress_callback:
            progress_callback("Processing timestamps...", 0.8)

        # Extract word timings
        words = self._extract_word_timings(result)

        detected_language = result.get("language", language or "en")

        if progress_callback:
            progress_callback("Complete", 1.0)

        logger.info(f"Transcribed {len(words)} words from {duration:.1f}s audio")

        return TranscriptionResult(
            full_text=result["text"].strip(),
            words=words,
            language=detected_language,
            duration=duration,
            model_used=self.model_size
        )

    def _extract_word_timings(self, result: dict) -> List[WordTiming]:
        """Extract word-level timings from Whisper result."""
        words = []

        for segment in result.get("segments", []):
            # whisper-timestamped provides words directly
            segment_words = segment.get("words", [])

            if segment_words:
                for word_data in segment_words:
                    # Handle both whisper-timestamped and standard whisper formats
                    text = word_data.get("text", word_data.get("word", "")).strip()
                    if not text:
                        continue

                    words.append(WordTiming(
                        text=text,
                        start_time=word_data.get("start", 0.0),
                        end_time=word_data.get("end", 0.0),
                        confidence=word_data.get("confidence", word_data.get("probability", 1.0))
                    ))
            else:
                # Standard whisper without word timestamps - estimate from segment
                segment_text = segment.get("text", "").strip()
                segment_words_list = segment_text.split()
                if not segment_words_list:
                    continue

                segment_start = segment.get("start", 0.0)
                segment_end = segment.get("end", 0.0)
                segment_duration = segment_end - segment_start
                word_duration = segment_duration / len(segment_words_list)

                for i, word_text in enumerate(segment_words_list):
                    words.append(WordTiming(
                        text=word_text,
                        start_time=segment_start + (i * word_duration),
                        end_time=segment_start + ((i + 1) * word_duration),
                        confidence=0.5  # Lower confidence for estimated timing
                    ))

        return words

    def verify_lyrics(
        self,
        audio_path: Path,
        provided_lyrics: str,
        language: str = None,
        progress_callback: Callable[[str, float], None] = None
    ) -> AlignmentResult:
        """
        Compare provided lyrics with extracted transcription.

        Args:
            audio_path: Path to audio file
            provided_lyrics: User-provided lyrics text
            language: Language code or None for auto-detect
            progress_callback: Optional progress callback

        Returns:
            AlignmentResult with matched words and similarity score
        """
        # First, extract from audio
        transcription = self.extract_lyrics(audio_path, language, progress_callback)

        # Normalize texts for comparison
        provided_words = self._normalize_text(provided_lyrics).split()
        extracted_words = [self._normalize_text(w.text) for w in transcription.words]

        # Find matching sequences
        matcher = SequenceMatcher(None, provided_words, extracted_words)
        matches = matcher.get_matching_blocks()

        # Build matched word list with timings
        matched_words = []
        matched_provided_indices = set()
        matched_extracted_indices = set()

        for match in matches:
            if match.size == 0:
                continue

            for i in range(match.size):
                provided_idx = match.a + i
                extracted_idx = match.b + i

                matched_provided_indices.add(provided_idx)
                matched_extracted_indices.add(extracted_idx)

                # Use timing from extracted, text from provided
                if extracted_idx < len(transcription.words):
                    word_timing = transcription.words[extracted_idx]
                    matched_words.append(WordTiming(
                        text=provided_words[provided_idx],
                        start_time=word_timing.start_time,
                        end_time=word_timing.end_time,
                        confidence=word_timing.confidence
                    ))

        # Find unmatched words
        unmatched_provided = [
            provided_words[i] for i in range(len(provided_words))
            if i not in matched_provided_indices
        ]
        unmatched_extracted = [
            extracted_words[i] for i in range(len(extracted_words))
            if i not in matched_extracted_indices
        ]

        # Calculate similarity score
        similarity = matcher.ratio()

        # Reconstruct aligned text
        aligned_text = self._build_aligned_text(provided_lyrics, matched_words)

        logger.info(
            f"Lyrics alignment: {len(matched_words)} matched, "
            f"{len(unmatched_provided)} unmatched provided, "
            f"{len(unmatched_extracted)} unmatched extracted, "
            f"similarity: {similarity:.2%}"
        )

        return AlignmentResult(
            matched_words=matched_words,
            unmatched_provided=unmatched_provided,
            unmatched_extracted=unmatched_extracted,
            similarity_score=similarity,
            aligned_text=aligned_text
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (lowercase, remove punctuation)."""
        import re
        # Remove special tags like [Verse 1], [Chorus], etc.
        text = re.sub(r'\[.*?\]', '', text)
        # Remove punctuation except apostrophes
        text = re.sub(r"[^\w\s']", '', text)
        # Normalize whitespace
        text = ' '.join(text.lower().split())
        return text

    def _build_aligned_text(
        self,
        original_lyrics: str,
        matched_words: List[WordTiming]
    ) -> str:
        """Reconstruct lyrics with timing annotations."""
        # Simple implementation - return original with timing summary
        if not matched_words:
            return original_lyrics

        first_word = matched_words[0]
        last_word = matched_words[-1]

        return (
            f"[{first_word.start_time:.2f}s - {last_word.end_time:.2f}s]\n"
            f"{original_lyrics}"
        )

    def get_timing_for_text_segment(
        self,
        transcription: TranscriptionResult,
        segment_text: str
    ) -> Tuple[float, float]:
        """
        Find the start and end time for a text segment within the transcription.

        Args:
            transcription: Full transcription result
            segment_text: Text segment to find (e.g., a verse or chorus)

        Returns:
            Tuple of (start_time, end_time) or (0.0, 0.0) if not found
        """
        segment_words = self._normalize_text(segment_text).split()
        if not segment_words:
            return (0.0, 0.0)

        all_words = transcription.words
        if not all_words:
            return (0.0, 0.0)

        # Find the first word of the segment
        first_word_normalized = segment_words[0]

        for i, word in enumerate(all_words):
            if self._normalize_text(word.text) == first_word_normalized:
                # Check if subsequent words match
                match_count = 1
                for j, seg_word in enumerate(segment_words[1:], 1):
                    if i + j < len(all_words):
                        if self._normalize_text(all_words[i + j].text) == seg_word:
                            match_count += 1
                        else:
                            break

                # If we matched enough words, use this as the segment
                if match_count >= min(3, len(segment_words)):
                    start_time = word.start_time
                    end_idx = min(i + len(segment_words) - 1, len(all_words) - 1)
                    end_time = all_words[end_idx].end_time
                    return (start_time, end_time)

        return (0.0, 0.0)


def check_whisper_installed() -> Tuple[bool, str]:
    """
    Check if Whisper is installed and available.

    Returns:
        Tuple of (is_installed, status_message)
    """
    try:
        import whisper_timestamped
        return True, "whisper-timestamped is installed"
    except ImportError:
        pass

    try:
        import whisper
        return True, "openai-whisper is installed (consider whisper-timestamped for better timing)"
    except ImportError:
        pass

    return False, "Whisper not installed. Run: pip install whisper-timestamped"


def get_recommended_model(available_vram_mb: int = None) -> str:
    """
    Get the recommended Whisper model based on available VRAM.

    Args:
        available_vram_mb: Available VRAM in MB, or None for auto-detect

    Returns:
        Recommended model name
    """
    if available_vram_mb is None:
        try:
            import torch
            if torch.cuda.is_available():
                available_vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
            else:
                available_vram_mb = 0
        except Exception:
            available_vram_mb = 0

    if available_vram_mb >= 10000:
        return "large"
    elif available_vram_mb >= 5000:
        return "medium"
    elif available_vram_mb >= 2000:
        return "small"
    elif available_vram_mb >= 1000:
        return "base"
    else:
        return "tiny"
