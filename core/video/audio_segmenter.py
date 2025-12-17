"""Audio segmentation utilities for extracting scene-specific audio clips."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
import shutil

logger = logging.getLogger(__name__)


class AudioSegmenter:
    """
    Extracts audio segments from a full audio file based on timestamps.

    Uses FFmpeg for reliable audio extraction with optional crossfade padding.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize the audio segmenter.

        Args:
            cache_dir: Directory to cache extracted segments. If None, uses temp dir.
        """
        self.cache_dir = cache_dir
        self._ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg executable."""
        # Check if ffmpeg is in PATH
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg

        # Check common Windows locations
        common_paths = [
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
            Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]

        for path in common_paths:
            if path.exists():
                return str(path)

        logger.warning("FFmpeg not found in PATH or common locations")
        return None

    def extract_segment(
        self,
        audio_path: Path,
        start_time: float,
        end_time: float,
        output_path: Optional[Path] = None,
        padding: float = 0.1,
        fade_duration: float = 0.05
    ) -> Optional[Path]:
        """
        Extract an audio segment from the source file.

        Args:
            audio_path: Path to source audio file
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Where to save the segment. If None, auto-generates in cache_dir
            padding: Extra time (seconds) to add before/after for smooth transitions
            fade_duration: Duration of fade in/out (seconds)

        Returns:
            Path to extracted segment, or None if extraction failed
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None

        if not self._ffmpeg_path:
            logger.error("FFmpeg not available for audio extraction")
            return None

        # Calculate padded times (but don't go negative or past end)
        padded_start = max(0, start_time - padding)
        padded_end = end_time + padding  # FFmpeg will handle if past end

        duration = padded_end - padded_start

        # Generate output path if not provided
        if output_path is None:
            if self.cache_dir:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                output_path = self.cache_dir / f"segment_{start_time:.2f}_{end_time:.2f}.wav"
            else:
                output_path = audio_path.parent / f"{audio_path.stem}_segment_{start_time:.2f}_{end_time:.2f}.wav"

        output_path = Path(output_path)

        # Check cache - if file exists and is recent, use it
        if output_path.exists():
            logger.info(f"Using cached audio segment: {output_path}")
            return output_path

        # Build FFmpeg command
        # -ss before -i for fast seeking
        # -t for duration
        # -af for audio filters (fade in/out)
        fade_filter = f"afade=t=in:st=0:d={fade_duration},afade=t=out:st={duration - fade_duration}:d={fade_duration}"

        cmd = [
            self._ffmpeg_path,
            "-y",  # Overwrite output
            "-ss", str(padded_start),  # Seek to start (before -i for speed)
            "-i", str(audio_path),
            "-t", str(duration),
            "-af", fade_filter,
            "-ar", "16000",  # Resample to 16kHz (Whisper/MuseTalk expected rate)
            "-ac", "1",  # Mono
            "-acodec", "pcm_s16le",  # 16-bit PCM WAV
            str(output_path)
        ]

        logger.info(f"Extracting audio segment: {start_time:.2f}s - {end_time:.2f}s -> {output_path.name}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return None

            if output_path.exists():
                logger.info(f"Extracted audio segment: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
                return output_path
            else:
                logger.error("FFmpeg completed but output file not found")
                return None

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out during audio extraction")
            return None
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return None

    def extract_scene_segments(
        self,
        audio_path: Path,
        scenes: List[dict],
        output_dir: Path
    ) -> List[Tuple[int, Optional[Path]]]:
        """
        Extract audio segments for multiple scenes.

        Args:
            audio_path: Path to source audio file
            scenes: List of scene dicts with 'start_time' and 'end_time' keys
            output_dir: Directory to save segments

        Returns:
            List of (scene_index, segment_path) tuples
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []

        for i, scene in enumerate(scenes):
            start_time = scene.get('start_time', 0)
            end_time = scene.get('end_time', 0)

            if end_time <= start_time:
                logger.warning(f"Scene {i} has invalid timing: {start_time} - {end_time}")
                results.append((i, None))
                continue

            output_path = output_dir / f"scene_{i:03d}_audio.wav"

            segment_path = self.extract_segment(
                audio_path,
                start_time,
                end_time,
                output_path
            )

            results.append((i, segment_path))

        return results

    def get_audio_duration(self, audio_path: Path) -> Optional[float]:
        """
        Get the duration of an audio file in seconds.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds, or None if failed
        """
        if not self._ffmpeg_path:
            return None

        # Use ffprobe if available, otherwise ffmpeg
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            ffprobe_path = Path(self._ffmpeg_path).parent / "ffprobe.exe"
            if ffprobe_path.exists():
                ffprobe = str(ffprobe_path)

        if ffprobe:
            cmd = [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ]
        else:
            # Fallback to ffmpeg with null output
            cmd = [
                self._ffmpeg_path,
                "-i", str(audio_path),
                "-f", "null",
                "-"
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if ffprobe and result.returncode == 0:
                return float(result.stdout.strip())
            elif not ffprobe:
                # Parse duration from ffmpeg stderr
                import re
                match = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", result.stderr)
                if match:
                    hours, mins, secs, centisecs = map(int, match.groups())
                    return hours * 3600 + mins * 60 + secs + centisecs / 100

        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")

        return None


def get_scene_audio_path(project_dir: Path, scene_index: int) -> Path:
    """
    Get the expected path for a scene's audio segment.

    Args:
        project_dir: Project directory
        scene_index: Scene index

    Returns:
        Path where the audio segment should be stored
    """
    segments_dir = project_dir / "audio_segments"
    return segments_dir / f"scene_{scene_index:03d}_audio.wav"


def extract_scene_audio_for_lipsync(
    project_dir: Path,
    audio_path: Path,
    scene_index: int,
    start_time: float,
    end_time: float
) -> Optional[Path]:
    """
    Convenience function to extract audio for a single scene's lip-sync.

    Args:
        project_dir: Project directory (for caching)
        audio_path: Path to full audio file
        scene_index: Scene index
        start_time: Scene start time
        end_time: Scene end time

    Returns:
        Path to extracted audio segment
    """
    segments_dir = project_dir / "audio_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    segmenter = AudioSegmenter(cache_dir=segments_dir)

    output_path = segments_dir / f"scene_{scene_index:03d}_audio.wav"

    return segmenter.extract_segment(
        audio_path,
        start_time,
        end_time,
        output_path,
        padding=0.1,  # Small padding for smooth lip-sync
        fade_duration=0.05
    )
