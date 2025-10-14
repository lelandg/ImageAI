"""
Google Veo API client for AI video generation.

This module handles video generation using Google's Veo models through
the Gemini API with support for various configurations and regional restrictions.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib
import requests

# Check if google.genai is available
try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None


class VeoModel(Enum):
    """Available Veo models"""
    VEO_3_GENERATE = "veo-3.0-generate-001"
    VEO_3_FAST = "veo-3.0-fast-generate-001"
    VEO_2_GENERATE = "veo-2.0-generate-001"


@dataclass
class VeoGenerationConfig:
    """Configuration for Veo video generation"""
    model: VeoModel = VeoModel.VEO_3_GENERATE
    prompt: str = ""
    aspect_ratio: str = "16:9"  # 16:9, 9:16, 1:1
    resolution: str = "1080p"  # 720p, 1080p
    duration: int = 8  # seconds (model-specific limits)
    fps: int = 24  # frames per second
    include_audio: bool = True  # Veo 3 can generate audio
    person_generation: bool = False  # May be restricted by region
    seed: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        config = {
            "prompt": self.prompt,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "duration": self.duration,
            "fps": self.fps,
        }
        
        if self.model == VeoModel.VEO_3_GENERATE:
            config["include_audio"] = self.include_audio
        
        if self.person_generation:
            config["person_generation"] = True
        
        if self.seed is not None:
            config["seed"] = self.seed
        
        return config


@dataclass
class VeoGenerationResult:
    """Result of a Veo generation operation"""
    success: bool = True
    video_url: Optional[str] = None
    video_path: Optional[Path] = None
    operation_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    generation_time: float = 0.0
    has_synthid: bool = True  # Veo videos include SynthID watermark
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VeoClient:
    """Client for Google Veo API video generation"""
    
    # Model constraints
    MODEL_CONSTRAINTS = {
        VeoModel.VEO_3_GENERATE: {
            "max_duration": 8,
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16", "1:1"],
            "supports_audio": True,
            "generation_time": (60, 360)  # 1-6 minutes
        },
        VeoModel.VEO_3_FAST: {
            "max_duration": 5,
            "resolutions": ["720p"],
            "aspect_ratios": ["16:9", "9:16"],
            "supports_audio": False,
            "generation_time": (11, 60)  # 11-60 seconds
        },
        VeoModel.VEO_2_GENERATE: {
            "max_duration": 8,
            "resolutions": ["720p"],
            "aspect_ratios": ["16:9"],
            "supports_audio": False,
            "generation_time": (60, 180)  # 1-3 minutes
        }
    }
    
    def __init__(self, api_key: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize Veo client.

        Args:
            api_key: Google API key
            region: User's region for restriction checking
        """
        if not GENAI_AVAILABLE:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")

        self.api_key = api_key
        self.region = region or self._detect_region()
        self.logger = logging.getLogger(__name__)
        self.client = None

        if api_key:
            # Use the new google.genai Client API instead of configure
            self.client = genai.Client(api_key=api_key)

        # Check regional restrictions
        self.person_generation_allowed = self._check_person_generation()
    
    def _detect_region(self) -> str:
        """Detect user's region from IP"""
        try:
            response = requests.get("https://ipapi.co/json/", timeout=5)
            data = response.json()
            return data.get("country_code", "US")
        except:
            return "US"  # Default to US
    
    def _check_person_generation(self) -> bool:
        """Check if person generation is allowed in region"""
        # MENA and some EU countries have restrictions
        restricted_regions = [
            "AE", "SA", "EG", "JO", "KW", "QA", "BH", "OM", "LB", "IQ",  # MENA
            "DE", "FR", "IT", "ES"  # Some EU countries
        ]
        return self.region not in restricted_regions
    
    def validate_config(self, config: VeoGenerationConfig) -> Tuple[bool, Optional[str]]:
        """
        Validate generation configuration against model constraints.
        
        Args:
            config: Generation configuration
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        constraints = self.MODEL_CONSTRAINTS.get(config.model)
        if not constraints:
            return False, f"Unknown model: {config.model.value}"
        
        # Check duration
        if config.duration > constraints["max_duration"]:
            return False, f"Duration {config.duration}s exceeds max {constraints['max_duration']}s for {config.model.value}"
        
        # Check resolution
        if config.resolution not in constraints["resolutions"]:
            return False, f"Resolution {config.resolution} not supported. Use: {constraints['resolutions']}"
        
        # Check aspect ratio
        if config.aspect_ratio not in constraints["aspect_ratios"]:
            return False, f"Aspect ratio {config.aspect_ratio} not supported. Use: {constraints['aspect_ratios']}"
        
        # Check audio support
        if config.include_audio and not constraints["supports_audio"]:
            return False, f"Model {config.model.value} does not support audio generation"
        
        # Check person generation
        if config.person_generation and not self.person_generation_allowed:
            return False, f"Person generation is not available in your region ({self.region})"
        
        return True, None
    
    async def generate_video_async(self, config: VeoGenerationConfig) -> VeoGenerationResult:
        """
        Generate video asynchronously using Veo API.
        
        Args:
            config: Generation configuration
            
        Returns:
            Generation result
        """
        result = VeoGenerationResult()
        
        # Validate configuration
        is_valid, error = self.validate_config(config)
        if not is_valid:
            result.success = False
            result.error = error
            return result
        
        try:
            start_time = time.time()

            if not self.client:
                raise ValueError("No client configured. API key required for video generation.")

            # Prepare generation parameters
            gen_params = config.to_dict()

            # Start generation (returns operation ID for polling)
            self.logger.info(f"Starting Veo generation with {config.model.value}")
            response = await self.client.models.generate_video_async(
                model=config.model.value,
                **gen_params
            )
            
            # Store operation ID for polling
            result.operation_id = response.name
            result.metadata["model"] = config.model.value
            result.metadata["prompt"] = config.prompt
            result.metadata["started_at"] = datetime.now().isoformat()
            
            # Poll for completion
            constraints = self.MODEL_CONSTRAINTS[config.model]
            max_wait = constraints["generation_time"][1] + 60  # Add buffer
            
            video_url = await self._poll_for_completion(response, max_wait)
            
            if video_url:
                result.video_url = video_url
                result.success = True
                
                # Download video to local storage
                result.video_path = await self._download_video(video_url)
                
                # Note about retention
                result.metadata["retention_warning"] = "Video URLs expire after 2 days. Local copy saved."
                result.metadata["expires_at"] = (datetime.now() + timedelta(days=2)).isoformat()
            else:
                result.success = False
                result.error = "Generation timed out or failed"
            
            result.generation_time = time.time() - start_time
            self.logger.info(f"Generation completed in {result.generation_time:.1f} seconds")
            
        except Exception as e:
            self.logger.error(f"Veo generation failed: {e}")
            result.success = False
            result.error = str(e)
        
        return result
    
    def generate_video(self, config: VeoGenerationConfig) -> VeoGenerationResult:
        """
        Generate video synchronously (blocking).
        
        Args:
            config: Generation configuration
            
        Returns:
            Generation result
        """
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.generate_video_async(config))
        finally:
            loop.close()
    
    async def _poll_for_completion(self, operation: Any, max_wait: int) -> Optional[str]:
        """
        Poll for video generation completion.
        
        Args:
            operation: Generation operation
            max_wait: Maximum wait time in seconds
            
        Returns:
            Video URL if successful, None otherwise
        """
        start_time = time.time()
        poll_interval = 10  # Start with 10 second intervals
        
        while time.time() - start_time < max_wait:
            try:
                # Check operation status
                if operation.done():
                    # Get the result
                    result = operation.result()
                    if hasattr(result, 'video_url'):
                        return result.video_url
                    elif hasattr(result, 'uri'):
                        return result.uri
                    else:
                        self.logger.warning("Operation completed but no video URL found")
                        return None
                
                # Wait before next poll
                await asyncio.sleep(poll_interval)
                
                # Increase poll interval over time (backoff)
                if time.time() - start_time > 60:
                    poll_interval = min(30, poll_interval + 5)
                
            except Exception as e:
                self.logger.error(f"Error polling for completion: {e}")
                return None
        
        self.logger.warning(f"Generation timed out after {max_wait} seconds")
        return None
    
    async def _download_video(self, video_url: str) -> Optional[Path]:
        """
        Download video from URL to local storage.
        
        Args:
            video_url: URL of generated video
            
        Returns:
            Local path to downloaded video
        """
        try:
            # Create cache directory
            cache_dir = Path.home() / ".imageai" / "cache" / "veo_videos"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename from URL hash
            url_hash = hashlib.sha256(video_url.encode()).hexdigest()[:16]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"veo_{timestamp}_{url_hash}.mp4"
            video_path = cache_dir / filename
            
            # Download video
            response = requests.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Save to file
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.info(f"Video downloaded to {video_path}")
            return video_path
            
        except Exception as e:
            self.logger.error(f"Failed to download video: {e}")
            return None
    
    def generate_batch(self,
                      configs: List[VeoGenerationConfig],
                      max_concurrent: int = 3) -> List[VeoGenerationResult]:
        """
        Generate multiple videos in batch with concurrency control.
        
        Args:
            configs: List of generation configurations
            max_concurrent: Maximum concurrent generations
            
        Returns:
            List of generation results
        """
        results = []
        
        # Process in batches to respect concurrency limit
        for i in range(0, len(configs), max_concurrent):
            batch = configs[i:i + max_concurrent]
            
            # Create async tasks for batch
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                tasks = [self.generate_video_async(config) for config in batch]
                batch_results = loop.run_until_complete(asyncio.gather(*tasks))
                results.extend(batch_results)
            finally:
                loop.close()
        
        return results
    
    def concatenate_clips(self,
                         video_paths: List[Path],
                         output_path: Path,
                         remove_audio: bool = True) -> bool:
        """
        Concatenate multiple Veo clips into a single video.
        
        Args:
            video_paths: List of video file paths
            output_path: Output video path
            remove_audio: Remove audio from Veo 3 clips
            
        Returns:
            Success status
        """
        try:
            # This would use FFmpeg to concatenate
            # Implementation would import ffmpeg_renderer
            from .ffmpeg_renderer import FFmpegRenderer
            
            renderer = FFmpegRenderer()
            
            # Create concat file
            concat_file = output_path.parent / "veo_concat.txt"
            with open(concat_file, 'w') as f:
                for path in video_paths:
                    f.write(f"file '{path.absolute()}'\n")
            
            # Build FFmpeg command
            import subprocess
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
            ]
            
            if remove_audio:
                cmd.extend(["-an"])  # Remove audio stream
            
            cmd.extend(["-y", str(output_path)])
            
            subprocess.run(cmd, capture_output=True, check=True)
            concat_file.unlink()  # Clean up
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to concatenate videos: {e}")
            return False
    
    def estimate_cost(self, config: VeoGenerationConfig) -> float:
        """
        Estimate generation cost in USD.
        
        Args:
            config: Generation configuration
            
        Returns:
            Estimated cost
        """
        # Veo pricing (approximate per second of video)
        pricing = {
            VeoModel.VEO_3_GENERATE: 0.10,  # $0.10 per second
            VeoModel.VEO_3_FAST: 0.05,  # $0.05 per second
            VeoModel.VEO_2_GENERATE: 0.08,  # $0.08 per second
        }
        
        cost_per_second = pricing.get(config.model, 0.10)
        return config.duration * cost_per_second
    
    def get_model_info(self, model: VeoModel) -> Dict[str, Any]:
        """Get information about a Veo model"""
        constraints = self.MODEL_CONSTRAINTS.get(model, {})
        return {
            "name": model.value,
            "max_duration": constraints.get("max_duration", 8),
            "resolutions": constraints.get("resolutions", []),
            "aspect_ratios": constraints.get("aspect_ratios", []),
            "supports_audio": constraints.get("supports_audio", False),
            "generation_time": constraints.get("generation_time", (60, 360)),
            "person_generation_allowed": self.person_generation_allowed
        }