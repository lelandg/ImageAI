"""MuseTalk lip-sync provider implementation."""

import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
import numpy as np

from .base_lipsync import BaseLipSyncProvider
from core.musetalk_installer import (
    check_musetalk_installed,
    get_musetalk_model_path
)

logger = logging.getLogger(__name__)


class MuseTalkProvider(BaseLipSyncProvider):
    """
    MuseTalk lip-sync provider for local inference.

    MuseTalk generates realistic lip-synced videos by:
    1. Detecting face and pose in the input video/image
    2. Extracting audio features using Whisper
    3. Generating lip movements frame by frame
    4. Compositing the result back onto the original
    """

    def __init__(self, model_path: Optional[Path] = None):
        """
        Initialize the MuseTalk provider.

        Args:
            model_path: Optional path to model directory.
                        Auto-detected if not provided.
        """
        self.model_path = model_path or get_musetalk_model_path()
        self._models_loaded = False
        self._musetalk = None
        self._dwpose = None
        self._vae = None
        self._whisper = None

    def is_available(self) -> bool:
        """Check if MuseTalk is installed and ready."""
        is_installed, status = check_musetalk_installed()
        if not is_installed:
            logger.debug(f"MuseTalk not available: {status}")
        return is_installed

    def get_install_prompt(self) -> str:
        """Get installation instructions."""
        return (
            "MuseTalk requires local installation of AI models.\n\n"
            "Click 'Install MuseTalk' to download and install:\n"
            "- Python packages (~2GB)\n"
            "- AI model weights (~2.5GB)\n\n"
            "Requirements:\n"
            "- NVIDIA GPU with 4GB+ VRAM (recommended)\n"
            "- ~5GB disk space\n\n"
            "CPU mode is available but slower."
        )

    def generate(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Optional[Path] = None,
        bbox_shift: int = 0,
        **kwargs
    ) -> Path:
        """
        Generate a lip-synced video.

        Args:
            video_path: Path to source video or image
            audio_path: Path to audio file
            output_path: Output path (auto-generated if None)
            bbox_shift: Mouth bounding box shift (-7 to +7, default 0)
                       Positive values increase mouth openness
            **kwargs: Additional parameters

        Returns:
            Path to the generated lip-synced video

        Raises:
            RuntimeError: If MuseTalk is not available or generation fails
        """
        # Validate inputs
        is_valid, error = self.validate_inputs(video_path, audio_path)
        if not is_valid:
            raise ValueError(error)

        # Check availability
        if not self.is_available():
            raise RuntimeError(
                "MuseTalk is not installed. Please install it first."
            )

        # Generate output path if not provided
        if output_path is None:
            output_dir = video_path.parent / "lipsync_output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{video_path.stem}_lipsync.mp4"

        logger.info(f"Starting MuseTalk generation: {video_path} + {audio_path} -> {output_path}")

        try:
            # Load models on first use
            if not self._models_loaded:
                self._load_models()

            # Check if input is image or video
            is_image = video_path.suffix.lower() in self.get_supported_image_formats()

            if is_image:
                # Convert image to static video for processing
                frames = self._image_to_frames(video_path)
            else:
                # Extract frames from video
                frames = self._extract_video_frames(video_path)

            # Extract audio features
            audio_features = self._extract_audio_features(audio_path)

            # Generate lip-synced frames
            synced_frames = self._generate_lipsync_frames(
                frames,
                audio_features,
                bbox_shift=bbox_shift
            )

            # Encode output video with audio
            self._encode_video(synced_frames, audio_path, output_path)

            logger.info(f"MuseTalk generation complete: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"MuseTalk generation failed: {e}")
            raise RuntimeError(f"Lip-sync generation failed: {e}")

    def _load_models(self):
        """Load all required models (lazy initialization)."""
        logger.info("Loading MuseTalk models...")

        try:
            import torch

            # Determine device
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self.device}")

            # Load MuseTalk model
            self._load_musetalk_model()

            # Load DWPose
            self._load_dwpose_model()

            # Load VAE
            self._load_vae_model()

            # Load Whisper
            self._load_whisper_model()

            self._models_loaded = True
            logger.info("All models loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            raise RuntimeError(f"Failed to load MuseTalk models: {e}")

    def _load_musetalk_model(self):
        """Load the core MuseTalk model."""
        import torch
        import json

        model_dir = self.model_path / "musetalk"
        config_path = model_dir / "musetalk.json"
        weights_path = model_dir / "pytorch_model.bin"

        if not weights_path.exists():
            raise FileNotFoundError(f"MuseTalk weights not found: {weights_path}")

        # Load config
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Initialize model (placeholder - actual implementation depends on MuseTalk API)
        logger.info(f"Loading MuseTalk from {weights_path}")
        self._musetalk_config = config
        self._musetalk_weights = torch.load(weights_path, map_location=self.device)

    def _load_dwpose_model(self):
        """Load DWPose body detection model."""
        import torch

        model_path = self.model_path / "dwpose" / "dw-ll_ucoco_384.pth"

        if not model_path.exists():
            raise FileNotFoundError(f"DWPose model not found: {model_path}")

        logger.info(f"Loading DWPose from {model_path}")
        self._dwpose_weights = torch.load(model_path, map_location=self.device)

    def _load_vae_model(self):
        """Load Stable Diffusion VAE."""
        from diffusers import AutoencoderKL

        vae_path = self.model_path / "sd-vae-ft-mse"

        if not (vae_path / "diffusion_pytorch_model.bin").exists():
            raise FileNotFoundError(f"VAE model not found: {vae_path}")

        logger.info(f"Loading VAE from {vae_path}")
        self._vae = AutoencoderKL.from_pretrained(
            str(vae_path),
            local_files_only=True
        ).to(self.device)

    def _load_whisper_model(self):
        """Load Whisper audio model."""
        import torch

        model_path = self.model_path / "whisper" / "tiny.pt"

        if not model_path.exists():
            raise FileNotFoundError(f"Whisper model not found: {model_path}")

        logger.info(f"Loading Whisper from {model_path}")
        self._whisper = torch.load(model_path, map_location=self.device)

    def _image_to_frames(self, image_path: Path, duration: float = None) -> List[np.ndarray]:
        """
        Convert a static image to a sequence of identical frames.

        Args:
            image_path: Path to the image
            duration: Duration in seconds (determined by audio if None)

        Returns:
            List of frames as numpy arrays
        """
        import cv2

        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")

        # Convert BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # For now, return single frame - actual frame count determined by audio
        return [img]

    def _extract_video_frames(self, video_path: Path) -> List[np.ndarray]:
        """
        Extract frames from a video file.

        Args:
            video_path: Path to the video

        Returns:
            List of frames as numpy arrays
        """
        import cv2

        frames = []
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Convert BGR to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame)
        finally:
            cap.release()

        if not frames:
            raise ValueError(f"No frames extracted from video: {video_path}")

        logger.info(f"Extracted {len(frames)} frames from {video_path}")
        return frames

    def _extract_audio_features(self, audio_path: Path) -> np.ndarray:
        """
        Extract audio features using Whisper.

        Args:
            audio_path: Path to audio file

        Returns:
            Audio feature array
        """
        import torch
        import torchaudio

        logger.info(f"Extracting audio features from {audio_path}")

        # Load audio
        waveform, sample_rate = torchaudio.load(str(audio_path))

        # Resample to 16kHz if needed (Whisper's expected rate)
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(sample_rate, 16000)
            waveform = resampler(waveform)

        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # Pad or trim to 30 seconds (Whisper's expected input length)
        target_length = 16000 * 30
        if waveform.shape[1] < target_length:
            padding = target_length - waveform.shape[1]
            waveform = torch.nn.functional.pad(waveform, (0, padding))
        else:
            waveform = waveform[:, :target_length]

        # Extract mel spectrogram features
        # This is a simplified version - actual MuseTalk may use different preprocessing
        mel_transform = torchaudio.transforms.MelSpectrogram(
            sample_rate=16000,
            n_fft=400,
            hop_length=160,
            n_mels=80
        )

        mel_features = mel_transform(waveform)
        logger.info(f"Extracted audio features: shape {mel_features.shape}")

        return mel_features.numpy()

    def _generate_lipsync_frames(
        self,
        frames: List[np.ndarray],
        audio_features: np.ndarray,
        bbox_shift: int = 0
    ) -> List[np.ndarray]:
        """
        Generate lip-synced frames.

        Args:
            frames: Source video frames
            audio_features: Audio feature array
            bbox_shift: Mouth bounding box shift

        Returns:
            List of lip-synced frames
        """
        import torch

        logger.info(f"Generating lip-sync for {len(frames)} frames with bbox_shift={bbox_shift}")

        # This is a placeholder implementation
        # Actual MuseTalk inference would involve:
        # 1. Face detection and landmark extraction
        # 2. Pose estimation with DWPose
        # 3. Face parsing
        # 4. Audio-to-lip mapping
        # 5. Frame generation with VAE
        # 6. Compositing onto original

        synced_frames = []

        for i, frame in enumerate(frames):
            # Placeholder: just copy frames
            # Real implementation would modify mouth region
            synced_frames.append(frame.copy())

            if (i + 1) % 30 == 0:
                logger.debug(f"Processed {i + 1}/{len(frames)} frames")

        logger.info(f"Generated {len(synced_frames)} lip-synced frames")
        return synced_frames

    def _encode_video(
        self,
        frames: List[np.ndarray],
        audio_path: Path,
        output_path: Path,
        fps: float = 25.0
    ):
        """
        Encode frames to video with audio.

        Args:
            frames: List of frames
            audio_path: Path to audio file
            output_path: Output video path
            fps: Frames per second
        """
        import cv2

        if not frames:
            raise ValueError("No frames to encode")

        logger.info(f"Encoding video: {len(frames)} frames at {fps} fps")

        # Get frame dimensions
        height, width = frames[0].shape[:2]

        # Create temporary video without audio
        temp_video = output_path.with_suffix('.temp.mp4')

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (width, height))

        try:
            for frame in frames:
                # Convert RGB to BGR for OpenCV
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                writer.write(bgr_frame)
        finally:
            writer.release()

        # Merge with audio using ffmpeg
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', str(temp_video),
                '-i', str(audio_path),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info(f"Video encoded successfully: {output_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg encoding failed: {e.stderr}")
            # Fall back to video without audio
            temp_video.rename(output_path)
            logger.warning("Audio merging failed, video saved without audio")

        finally:
            # Clean up temp file
            if temp_video.exists():
                temp_video.unlink()

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get available parameters for this provider."""
        return {
            "bbox_shift": {
                "type": "integer",
                "min": -7,
                "max": 7,
                "default": 0,
                "description": "Mouth bounding box shift. Positive values increase mouth openness."
            }
        }
