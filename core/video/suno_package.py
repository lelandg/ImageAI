"""
Suno Package Support for ImageAI Video Projects

Handles detection, extraction, and merging of Suno multi-file packages (zips containing
audio stems and MIDI files).

IMPORTANT: Volume mixing should be done in Suno before export. This module merges stems
at equal volume (1.0). If you need different stem volumes, adjust them in Suno and
re-export the package.
"""

import logging
import zipfile
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set
import tempfile
import shutil

logger = logging.getLogger(__name__)

# Register permissive MIDI key signature handler for Suno files
# This must happen before any MIDI files are loaded
_PERMISSIVE_MIDI_REGISTERED = False

def _register_permissive_midi_loader():
    """
    Register a custom key signature handler that tolerates invalid values.

    Suno generates MIDI files with invalid key signatures (e.g., 19 sharps).
    This custom handler allows mido to load these files by setting invalid
    key signatures to None instead of crashing.

    This is registered globally once, affecting all subsequent MIDI loads.
    """
    global _PERMISSIVE_MIDI_REGISTERED

    if _PERMISSIVE_MIDI_REGISTERED:
        return

    try:
        import mido.midifiles.meta
        from mido.midifiles.meta import KeySignatureError

        # Save reference to original class
        OriginalKeySignatureSpec = mido.midifiles.meta.MetaSpec_key_signature

        class PermissiveKeySignatureSpec(OriginalKeySignatureSpec):
            """Custom key signature handler that tolerates invalid values."""

            def decode(self, message, data):
                """Decode key signature, setting to None if invalid."""
                try:
                    super().decode(message, data)
                except (KeySignatureError, KeyError) as e:
                    logger.debug(f"Skipping invalid key signature during decode: {e}")
                    message.key = None

            def check(self, name, value):
                """Skip validation if key is None."""
                if value is not None:
                    super().check(name, value)

        # Register the permissive handler
        mido.midifiles.meta.add_meta_spec(PermissiveKeySignatureSpec)

        _PERMISSIVE_MIDI_REGISTERED = True
        logger.info("Registered permissive MIDI key signature handler for Suno compatibility")

    except ImportError:
        logger.warning("mido library not available - MIDI support disabled")
    except Exception as e:
        logger.warning(f"Could not register permissive MIDI handler: {e}")

# Common Suno stem names (case-insensitive matching)
KNOWN_STEM_NAMES = {
    'vocals', 'drums', 'bass', 'guitar', 'synth', 'piano',
    'strings', 'brass', 'fx', 'backing vocals', 'backing_vocals',
    'lead', 'rhythm', 'percussion', 'keys'
}


@dataclass
class SunoPackage:
    """Represents extracted Suno multi-file package"""
    source_zip: Path
    extract_dir: Path  # Temporary directory for extraction
    audio_stems: Dict[str, Path] = field(default_factory=dict)  # {"Vocals": Path("vocals.wav"), ...}
    midi_files: Dict[str, Path] = field(default_factory=dict)   # {"Vocals": Path("vocals.mid"), ...}
    merged_audio: Optional[Path] = None  # Path to merged WAV (after preprocessing)
    merged_midi: Optional[Path] = None   # Path to merged MIDI (after preprocessing)

    def cleanup(self):
        """Clean up temporary extraction directory"""
        if self.extract_dir and self.extract_dir.exists():
            try:
                shutil.rmtree(self.extract_dir)
                logger.debug(f"Cleaned up temp directory: {self.extract_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up {self.extract_dir}: {e}")

    def __del__(self):
        """Ensure cleanup on deletion"""
        self.cleanup()


def _extract_stem_name(filename: str) -> Optional[str]:
    """
    Extract stem name from Suno filename.

    Examples:
        "Ice Ice Baby (Heavy Metal) v2-2 (Vocals).wav" -> "Vocals"
        "Ice Ice Baby (Heavy Metal) v2-2 (Drums).mid" -> "Drums"
        "My Song (Bass).wav" -> "Bass"

    Returns stem name or None if not recognized.
    """
    # Look for pattern: (StemName).ext
    import re
    match = re.search(r'\(([^)]+)\)\.(wav|mid|midi)$', filename, re.IGNORECASE)
    if match:
        stem_name = match.group(1).strip()
        # Validate it's a known stem type
        if stem_name.lower() in KNOWN_STEM_NAMES:
            return stem_name
    return None


def detect_suno_package(zip_path: Path) -> Optional[SunoPackage]:
    """
    Detect if file is a Suno package zip and extract contents.

    A valid Suno package contains:
    - At least one .wav file with recognizable stem name
    - Optionally matching .mid/.midi files

    Args:
        zip_path: Path to potential Suno package zip file

    Returns:
        SunoPackage if valid, None otherwise
    """
    if not zip_path.exists():
        logger.error(f"Zip file not found: {zip_path}")
        return None

    if zip_path.suffix.lower() != '.zip':
        logger.debug(f"Not a zip file: {zip_path}")
        return None

    try:
        # Create temporary extraction directory
        temp_dir = Path(tempfile.mkdtemp(prefix="suno_package_"))
        logger.info(f"Extracting Suno package to: {temp_dir}")

        # Extract zip contents
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(temp_dir)

        # Scan for audio stems and MIDI files
        audio_stems: Dict[str, Path] = {}
        midi_files: Dict[str, Path] = {}

        for file_path in temp_dir.rglob('*'):
            if not file_path.is_file():
                continue

            stem_name = _extract_stem_name(file_path.name)
            if not stem_name:
                continue

            ext = file_path.suffix.lower()
            if ext in ['.wav', '.mp3', '.m4a', '.ogg']:
                audio_stems[stem_name] = file_path
                logger.debug(f"Found audio stem: {stem_name} -> {file_path.name}")
            elif ext in ['.mid', '.midi']:
                midi_files[stem_name] = file_path
                logger.debug(f"Found MIDI file: {stem_name} -> {file_path.name}")

        # Validate: Must have at least one audio stem to be a valid Suno package
        if not audio_stems:
            logger.debug(f"No recognizable audio stems found in {zip_path}")
            shutil.rmtree(temp_dir)
            return None

        logger.info(f"Detected Suno package: {len(audio_stems)} audio stems, {len(midi_files)} MIDI files")

        return SunoPackage(
            source_zip=zip_path,
            extract_dir=temp_dir,
            audio_stems=audio_stems,
            midi_files=midi_files
        )

    except zipfile.BadZipFile:
        logger.error(f"Invalid zip file: {zip_path}")
        return None
    except Exception as e:
        logger.error(f"Error detecting Suno package: {e}", exc_info=True)
        return None


def merge_audio_stems(stems: Dict[str, Path], output_path: Path,
                     selected_stems: Optional[Set[str]] = None) -> Path:
    """
    Merge multiple audio stems into single file using ffmpeg.

    All stems are merged at equal volume (1.0). For custom volume mixing,
    adjust stem volumes in Suno before exporting the package.

    Args:
        stems: Dictionary of stem_name -> file_path
        output_path: Where to write merged audio file
        selected_stems: Set of stem names to include (None = all)

    Returns:
        Path to merged audio file

    Raises:
        RuntimeError: If ffmpeg command fails
        ValueError: If no stems selected or stems dict empty
    """
    if not stems:
        raise ValueError("No stems provided for merging")

    # Filter to selected stems only
    if selected_stems is None:
        selected_stems = set(stems.keys())

    stems_to_merge = {name: path for name, path in stems.items() if name in selected_stems}

    if not stems_to_merge:
        raise ValueError("No stems selected for merging")

    logger.info(f"Merging {len(stems_to_merge)} audio stems to {output_path}")

    # Build ffmpeg command
    # Example: ffmpeg -i vocals.wav -i drums.wav -i bass.wav \
    #          -filter_complex "[0:a][1:a][2:a]amix=inputs=3:duration=longest" \
    #          -ac 2 merged.wav

    cmd = ['ffmpeg', '-y']  # -y to overwrite output

    # Add input files
    for stem_path in stems_to_merge.values():
        cmd.extend(['-i', str(stem_path)])

    num_inputs = len(stems_to_merge)

    if num_inputs == 1:
        # Single stem, just copy
        cmd.extend(['-c', 'copy', str(output_path)])
    else:
        # Multiple stems, use amix filter
        # Build input labels: [0:a][1:a][2:a]...
        input_labels = ''.join([f'[{i}:a]' for i in range(num_inputs)])
        filter_complex = f'{input_labels}amix=inputs={num_inputs}:duration=longest'

        cmd.extend([
            '-filter_complex', filter_complex,
            '-ac', '2',  # Stereo output
            str(output_path)
        ])

    logger.debug(f"FFmpeg command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Successfully merged audio stems to {output_path}")
        logger.debug(f"FFmpeg output: {result.stderr}")
        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr}")
        raise RuntimeError(f"Failed to merge audio stems: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg to merge audio stems.")


def merge_midi_files(midi_files: Dict[str, Path], output_path: Path,
                    selected_files: Optional[Set[str]] = None) -> Path:
    """
    Merge multiple MIDI files into single multi-track MIDI file.

    Each input MIDI file becomes a separate track in the output, with the
    original stem name preserved as the track name.

    Args:
        midi_files: Dictionary of stem_name -> midi_file_path
        output_path: Where to write merged MIDI file
        selected_files: Set of stem names to include (None = all)

    Returns:
        Path to merged MIDI file

    Raises:
        RuntimeError: If MIDI merge fails
        ValueError: If no files selected or midi_files dict empty
    """
    if not midi_files:
        raise ValueError("No MIDI files provided for merging")

    # Filter to selected files only
    if selected_files is None:
        selected_files = set(midi_files.keys())

    files_to_merge = {name: path for name, path in midi_files.items() if name in selected_files}

    if not files_to_merge:
        raise ValueError("No MIDI files selected for merging")

    logger.info(f"Merging {len(files_to_merge)} MIDI files to {output_path}")

    try:
        import mido
        from mido import MidiFile, MidiTrack, MetaMessage

        # Register permissive MIDI loader before loading any files
        _register_permissive_midi_loader()

        # Create new MIDI file
        merged = MidiFile()

        # Track 0: Tempo map
        tempo_track = MidiTrack()
        merged.tracks.append(tempo_track)

        # Load first MIDI file to get tempo/time signature
        first_midi = None
        for midi_path in files_to_merge.values():
            try:
                first_midi = MidiFile(str(midi_path))
                logger.debug(f"Loaded tempo track from {midi_path.name}")
                break
            except Exception as e:
                logger.warning(f"Could not load {midi_path.name}: {e}")
                continue

        # Copy tempo and time signature from first valid file
        if first_midi:
            for msg in first_midi.tracks[0]:
                if msg.is_meta and msg.type in ['set_tempo', 'time_signature']:
                    tempo_track.append(msg.copy())
                # Skip key_signature - we handle invalid ones with custom decoder

        # Add each MIDI file as a separate track
        for stem_name, midi_path in sorted(files_to_merge.items()):
            logger.debug(f"Loading MIDI track: {stem_name} from {midi_path.name}")

            try:
                source = MidiFile(str(midi_path))

                # Remove any invalid key signatures that were set to None
                for track in source.tracks:
                    track[:] = [msg for msg in track if not (
                        hasattr(msg, 'type') and
                        msg.type == 'key_signature' and
                        hasattr(msg, 'key') and
                        msg.key is None
                    )]

            except Exception as e:
                logger.warning(f"Could not load {stem_name} track from {midi_path.name}: {e}")
                continue

            # Find the main note track (skip tempo track)
            for track in source.tracks:
                # Skip if it's just meta messages (tempo track)
                has_notes = any(msg.type in ['note_on', 'note_off'] for msg in track)
                if not has_notes:
                    continue

                # Create new track with stem name
                new_track = MidiTrack()
                new_track.append(MetaMessage('track_name', name=stem_name, time=0))

                # Copy all messages from source track (except track_name and invalid key_signature)
                for msg in track:
                    if msg.is_meta and msg.type == 'track_name':
                        continue  # Skip original track name
                    if msg.is_meta and msg.type == 'key_signature' and hasattr(msg, 'key') and msg.key is None:
                        continue  # Skip invalid key signatures
                    new_track.append(msg.copy())

                merged.tracks.append(new_track)
                logger.debug(f"  Added {stem_name} track with {len(new_track)} messages")
                break  # Only take first note track from each file

        # Check if we successfully loaded any tracks
        if len(merged.tracks) <= 1:  # Only tempo track, no note tracks
            raise RuntimeError(
                "No valid MIDI tracks could be loaded. "
                "The MIDI files may be corrupted or in an unsupported format."
            )

        # Save merged MIDI
        merged.save(str(output_path))
        logger.info(f"Successfully merged MIDI files to {output_path} ({len(merged.tracks)-1} note tracks)")
        return output_path

    except ImportError:
        raise RuntimeError("mido library not found. Please install mido to merge MIDI files.")
    except Exception as e:
        logger.error(f"Failed to merge MIDI files: {e}", exc_info=True)
        raise RuntimeError(f"Failed to merge MIDI files: {e}")


def get_package_info(package: SunoPackage) -> Dict[str, any]:
    """
    Get human-readable information about a Suno package.

    Returns:
        Dictionary with package information for display
    """
    return {
        'source_file': package.source_zip.name,
        'num_audio_stems': len(package.audio_stems),
        'num_midi_files': len(package.midi_files),
        'audio_stems': sorted(package.audio_stems.keys()),
        'midi_files': sorted(package.midi_files.keys()),
        'has_audio': bool(package.audio_stems),
        'has_midi': bool(package.midi_files)
    }
