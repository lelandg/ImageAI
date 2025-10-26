"""
LTX-Video provider for local GPU and cloud API video generation.

This module handles video generation using Lightricks' LTX-Video models
with support for local GPU deployment (free, unlimited) and optional
cloud APIs (Fal.ai, Replicate) as fallback.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import hashlib

# Check if PyTorch is available
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

# Check if diffusers is available
try:
    from diffusers import DiffusionPipeline
    DIFFUSERS_AVAILABLE = True
except ImportError:
    DIFFUSERS_AVAILABLE = False
    DiffusionPipeline = None

from PIL import Image
import numpy as np


class LTXDeploymentMode(Enum):
    """LTX-Video deployment modes"""
    LOCAL_GPU = "local"          # Local GPU deployment (DEFAULT, free)
    FAL_API = "fal"             # Fal.ai cloud API (optional, $0.04-$0.16/s)
    REPLICATE_API = "replicate" # Replicate cloud API (optional)
    COMFYUI = "comfyui"         # ComfyUI integration (optional)


class LTXModel(Enum):
    """Available LTX models"""
    LTX_VIDEO_2B = "ltx-video-2b"     # 2B parameter model
    LTX_VIDEO_13B = "ltx-video-13b"   # 13B parameter model (higher quality)
    # Future LTX-2 models (when released)
    LTX_2_FAST = "ltx-2-fast"         # Optimized for speed
    LTX_2_PRO = "ltx-2-pro"           # Balanced quality/speed
    LTX_2_ULTRA = "ltx-2-ultra"       # 4K, 50fps, 10s, audio


@dataclass
class LTXGenerationConfig:
    """Configuration for LTX video generation"""
    model: LTXModel = LTXModel.LTX_VIDEO_2B
    deployment: LTXDeploymentMode = LTXDeploymentMode.LOCAL_GPU
    prompt: str = ""

    # Resolution and format
    resolution: str = "1080p"  # 720p, 1080p, 4K (4K for Ultra only)
    aspect_ratio: str = "16:9"  # 16:9, 9:16, 1:1, 21:9
    fps: int = 30              # 24, 30, 50 (50 for Pro/Ultra)
    duration: int = 5          # 1-10 seconds (10 for LTX-2)

    # Audio
    include_audio: bool = True
    audio_prompt: Optional[str] = None  # Separate audio description

    # Image inputs
    image: Optional[Path] = None  # Start frame (image-to-video)
    keyframes: Optional[List[Tuple[float, Path]]] = None  # (time, image) pairs
    reference_images: Optional[List[Path]] = None  # Up to 3 style references

    # Video inputs
    source_video: Optional[Path] = None  # For video-to-video transformation
    extend_video: Optional[Path] = None  # For forward/backward extension
    extend_direction: str = "forward"    # forward, backward, both

    # Advanced controls
    camera_motion: Optional[str] = None  # pan_left, zoom_in, orbit, etc.
    camera_speed: float = 1.0            # 0.5-2.0
    lora_weights: Optional[Path] = None  # Custom LoRA for style
    lora_scale: float = 1.0              # 0.0-2.0

    # Generation parameters
    seed: Optional[int] = None
    guidance_scale: float = 7.5          # CFG scale
    num_inference_steps: int = 50

    # API-specific (for cloud deployments)
    api_key: Optional[str] = None
    webhook_url: Optional[str] = None

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Validate resolution for model
        if self.resolution == "4K" and self.model not in [LTXModel.LTX_2_ULTRA]:
            raise ValueError(
                f"4K resolution is only supported by LTX-2 Ultra, got {self.model.value}"
            )

        # Validate FPS
        if self.fps == 50 and self.model not in [LTXModel.LTX_2_PRO, LTXModel.LTX_2_ULTRA]:
            raise ValueError(
                f"50fps is only supported by LTX-2 Pro/Ultra, got {self.model.value}"
            )

        # Validate duration
        if self.duration < 1 or self.duration > 10:
            raise ValueError(
                f"Duration must be 1-10 seconds, got {self.duration}"
            )

        # Validate reference images
        if self.reference_images and len(self.reference_images) > 3:
            raise ValueError(
                f"Maximum 3 reference images supported, got {len(self.reference_images)}"
            )

        # Validate aspect ratio
        valid_aspects = ["16:9", "9:16", "1:1", "21:9"]
        if self.aspect_ratio not in valid_aspects:
            raise ValueError(
                f"Aspect ratio must be one of {valid_aspects}, got {self.aspect_ratio}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return {
            "model": self.model.value,
            "prompt": self.prompt,
            "resolution": self.resolution,
            "aspect_ratio": self.aspect_ratio,
            "fps": self.fps,
            "duration": self.duration,
            "include_audio": self.include_audio,
            "audio_prompt": self.audio_prompt,
            "camera_motion": self.camera_motion,
            "camera_speed": self.camera_speed,
            "guidance_scale": self.guidance_scale,
            "num_inference_steps": self.num_inference_steps,
            "seed": self.seed,
        }


@dataclass
class LTXGenerationResult:
    """Result from LTX video generation"""
    success: bool
    video_path: Optional[Path] = None
    duration: float = 0.0
    resolution: Tuple[int, int] = (0, 0)
    fps: int = 0
    file_size: int = 0
    generation_time: float = 0.0
    cost: float = 0.0  # For API deployments
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LTXVideoClient:
    """Client for LTX-Video generation (all deployment modes)"""

    def __init__(
        self,
        deployment: LTXDeploymentMode = LTXDeploymentMode.LOCAL_GPU,
        api_key: Optional[str] = None,
        models_dir: Optional[Path] = None
    ):
        """
        Initialize LTX-Video client

        Args:
            deployment: Deployment mode (local, fal, replicate, comfyui)
            api_key: API key for cloud deployments
            models_dir: Directory containing local models
        """
        self.deployment = deployment
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

        # Set models directory
        if models_dir is None:
            models_dir = Path.home() / ".cache" / "ltx-video" / "models"
        self.models_dir = models_dir

        # Initialize appropriate backend
        self.pipeline = None
        self._init_backend()

    def _init_backend(self):
        """Initialize the appropriate backend based on deployment mode"""
        if self.deployment == LTXDeploymentMode.LOCAL_GPU:
            self._init_local_gpu()
        elif self.deployment == LTXDeploymentMode.FAL_API:
            self._init_fal_client()
        elif self.deployment == LTXDeploymentMode.REPLICATE_API:
            self._init_replicate_client()
        elif self.deployment == LTXDeploymentMode.COMFYUI:
            self._init_comfyui()

    def _init_local_gpu(self):
        """Initialize local GPU pipeline"""
        if not TORCH_AVAILABLE:
            raise RuntimeError(
                "PyTorch not available. Install with: pip install torch torchvision"
            )

        if not DIFFUSERS_AVAILABLE:
            raise RuntimeError(
                "Diffusers not available. Install with: pip install diffusers"
            )

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA not available. LTX-Video requires an NVIDIA GPU with CUDA support."
            )

        self.logger.info("Initializing LTX-Video local GPU pipeline...")

        # GPU info
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        self.logger.info(f"GPU: {gpu_name} ({gpu_memory:.1f}GB VRAM)")

        # Check VRAM requirements
        if gpu_memory < 20:
            self.logger.warning(
                f"GPU has {gpu_memory:.1f}GB VRAM. LTX-Video recommends 24GB+ (RTX 4090)"
            )

        # Pipeline will be loaded on first generation to save memory
        self.logger.info("Local GPU backend initialized (pipeline will load on first use)")

    def _init_fal_client(self):
        """Initialize Fal.ai API client"""
        if not self.api_key:
            raise ValueError("API key required for Fal.ai deployment")

        try:
            import fal_client
            self.fal_client = fal_client
            self.logger.info("Fal.ai client initialized")
        except ImportError:
            raise RuntimeError(
                "Fal client not available. Install with: pip install fal-client"
            )

    def _init_replicate_client(self):
        """Initialize Replicate API client"""
        if not self.api_key:
            raise ValueError("API key required for Replicate deployment")

        try:
            import replicate
            self.replicate_client = replicate
            self.replicate_client.api_token = self.api_key
            self.logger.info("Replicate client initialized")
        except ImportError:
            raise RuntimeError(
                "Replicate client not available. Install with: pip install replicate"
            )

    def _init_comfyui(self):
        """Initialize ComfyUI integration"""
        self.logger.info("ComfyUI integration initialized")
        # TODO: Implement ComfyUI workflow integration

    def _load_pipeline(self, model: LTXModel):
        """
        Load the diffusion pipeline (lazy loading to save memory)

        Args:
            model: Model to load
        """
        if self.pipeline is not None:
            return  # Already loaded

        model_path = self.models_dir / model.value

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {model_path}\n"
                f"Run: python scripts/setup_ltx_video.py to download models"
            )

        self.logger.info(f"Loading pipeline: {model.value}...")

        try:
            self.pipeline = DiffusionPipeline.from_pretrained(
                str(model_path),
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True
            )
            self.pipeline.to("cuda")
            self.pipeline.enable_attention_slicing()

            self.logger.info("Pipeline loaded successfully")

        except Exception as e:
            self.logger.error(f"Failed to load pipeline: {e}")
            raise

    def generate_video_sync(self, config: LTXGenerationConfig) -> LTXGenerationResult:
        """
        Generate video synchronously

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        start_time = time.time()

        try:
            if self.deployment == LTXDeploymentMode.LOCAL_GPU:
                result = self._generate_local(config)
            elif self.deployment == LTXDeploymentMode.FAL_API:
                result = self._generate_fal(config)
            elif self.deployment == LTXDeploymentMode.REPLICATE_API:
                result = self._generate_replicate(config)
            elif self.deployment == LTXDeploymentMode.COMFYUI:
                result = self._generate_comfyui(config)
            else:
                raise ValueError(f"Unsupported deployment mode: {self.deployment}")

            result.generation_time = time.time() - start_time
            return result

        except Exception as e:
            self.logger.error(f"Generation failed: {e}")
            return LTXGenerationResult(
                success=False,
                error=str(e),
                generation_time=time.time() - start_time
            )

    async def generate_video_async(self, config: LTXGenerationConfig) -> LTXGenerationResult:
        """
        Generate video asynchronously

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_video_sync, config)

    def _generate_local(self, config: LTXGenerationConfig) -> LTXGenerationResult:
        """
        Generate video using local GPU

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        self.logger.info(f"Generating video with LTX-Video (local GPU)...")
        self.logger.info(f"  Model: {config.model.value}")
        self.logger.info(f"  Resolution: {config.resolution} {config.aspect_ratio}")
        self.logger.info(f"  Duration: {config.duration}s @ {config.fps}fps")
        self.logger.info(f"  Prompt: {config.prompt[:100]}...")

        # Load pipeline
        self._load_pipeline(config.model)

        # Prepare generation parameters
        generator = None
        if config.seed is not None:
            generator = torch.Generator(device="cuda").manual_seed(config.seed)

        # Convert resolution to dimensions
        width, height = self._resolution_to_dimensions(
            config.resolution,
            config.aspect_ratio
        )

        # Calculate number of frames
        num_frames = int(config.duration * config.fps)

        # Prepare input image if provided
        image = None
        if config.image:
            image = Image.open(config.image).convert("RGB")
            image = image.resize((width, height))

        # Generate video
        try:
            output = self.pipeline(
                prompt=config.prompt,
                image=image,
                width=width,
                height=height,
                num_frames=num_frames,
                num_inference_steps=config.num_inference_steps,
                guidance_scale=config.guidance_scale,
                generator=generator,
            )

            # Save video
            output_path = self._get_output_path(config)
            self._save_video(output.frames[0], output_path, config.fps)

            # Calculate file size
            file_size = output_path.stat().st_size

            return LTXGenerationResult(
                success=True,
                video_path=output_path,
                duration=config.duration,
                resolution=(width, height),
                fps=config.fps,
                file_size=file_size,
                cost=0.0,  # Free for local deployment
                metadata={
                    "model": config.model.value,
                    "prompt": config.prompt,
                    "seed": config.seed,
                    "guidance_scale": config.guidance_scale,
                    "num_inference_steps": config.num_inference_steps,
                }
            )

        except Exception as e:
            self.logger.error(f"Local generation failed: {e}")
            raise

    def _generate_fal(self, config: LTXGenerationConfig) -> LTXGenerationResult:
        """
        Generate video using Fal.ai API

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        raise NotImplementedError("Fal.ai API integration not yet implemented")

    def _generate_replicate(self, config: LTXGenerationConfig) -> LTXGenerationResult:
        """
        Generate video using Replicate API

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        raise NotImplementedError("Replicate API integration not yet implemented")

    def _generate_comfyui(self, config: LTXGenerationConfig) -> LTXGenerationResult:
        """
        Generate video using ComfyUI

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        raise NotImplementedError("ComfyUI integration not yet implemented")

    def _resolution_to_dimensions(
        self,
        resolution: str,
        aspect_ratio: str
    ) -> Tuple[int, int]:
        """
        Convert resolution and aspect ratio to width/height

        Args:
            resolution: Resolution string (720p, 1080p, 4K)
            aspect_ratio: Aspect ratio string (16:9, 9:16, 1:1, 21:9)

        Returns:
            Tuple of (width, height)
        """
        # Base heights
        heights = {
            "720p": 720,
            "1080p": 1080,
            "4K": 2160
        }

        height = heights.get(resolution, 1080)

        # Calculate width based on aspect ratio
        aspect_ratios = {
            "16:9": 16/9,
            "9:16": 9/16,
            "1:1": 1/1,
            "21:9": 21/9
        }

        ratio = aspect_ratios.get(aspect_ratio, 16/9)
        width = int(height * ratio)

        # Round to multiples of 8 (required by model)
        width = (width // 8) * 8
        height = (height // 8) * 8

        return width, height

    def _get_output_path(self, config: LTXGenerationConfig) -> Path:
        """
        Generate output path for video

        Args:
            config: Generation configuration

        Returns:
            Path object for output video
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_hash = hashlib.md5(config.prompt.encode()).hexdigest()[:8]
        filename = f"ltx_{timestamp}_{prompt_hash}.mp4"

        output_dir = Path.cwd() / "generated_videos"
        output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir / filename

    def _save_video(
        self,
        frames: Union[List[Image.Image], np.ndarray],
        output_path: Path,
        fps: int
    ):
        """
        Save video frames to file

        Args:
            frames: List of PIL Images or numpy array
            output_path: Path to save video
            fps: Frames per second
        """
        try:
            import cv2

            # Convert frames to numpy array if needed
            if isinstance(frames[0], Image.Image):
                frames = [np.array(frame) for frame in frames]

            # Get video dimensions
            height, width = frames[0].shape[:2]

            # Initialize video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(
                str(output_path),
                fourcc,
                fps,
                (width, height)
            )

            # Write frames
            for frame in frames:
                # Convert RGB to BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                out.write(frame_bgr)

            out.release()

            self.logger.info(f"Video saved: {output_path}")

        except Exception as e:
            self.logger.error(f"Failed to save video: {e}")
            raise

    # Advanced features (Phase 3)

    def generate_with_keyframes(
        self,
        config: LTXGenerationConfig
    ) -> LTXGenerationResult:
        """
        Multi-keyframe generation (LTX-2 exclusive feature)

        Args:
            config: Generation configuration with keyframes

        Returns:
            Generation result
        """
        raise NotImplementedError("Multi-keyframe generation not yet implemented")

    def extend_video(
        self,
        video_path: Path,
        config: LTXGenerationConfig
    ) -> LTXGenerationResult:
        """
        Extend video forward or backward (LTX-2 exclusive)

        Args:
            video_path: Path to video to extend
            config: Generation configuration

        Returns:
            Generation result
        """
        raise NotImplementedError("Video extension not yet implemented")

    def transform_video(
        self,
        video_path: Path,
        config: LTXGenerationConfig
    ) -> LTXGenerationResult:
        """
        Video-to-video transformation (LTX-2 exclusive)

        Args:
            video_path: Path to source video
            config: Generation configuration

        Returns:
            Generation result
        """
        raise NotImplementedError("Video transformation not yet implemented")

    def fine_tune_lora(
        self,
        training_data: List[Path],
        output_path: Path,
        **kwargs
    ) -> Path:
        """
        Fine-tune LoRA for style consistency (local deployment only)

        Args:
            training_data: List of training images/videos
            output_path: Path to save LoRA weights
            **kwargs: Additional training parameters

        Returns:
            Path to trained LoRA weights
        """
        if self.deployment != LTXDeploymentMode.LOCAL_GPU:
            raise RuntimeError("LoRA training only available for local deployment")

        raise NotImplementedError("LoRA fine-tuning not yet implemented")
