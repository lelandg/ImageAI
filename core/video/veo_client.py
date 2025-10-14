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
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None


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
    image: Optional[Path] = None  # Seed image for image-to-video generation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls (excludes image, handled separately)"""
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

        # Note: image is handled separately in generate_video_async
        # as it requires special loading/preparation

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

            # Load seed image if provided
            seed_image = None
            if config.image and config.image.exists():
                try:
                    # Load image bytes
                    with open(config.image, 'rb') as f:
                        image_bytes = f.read()

                    # Create Image object for Veo API
                    # Must be a dict with imageBytes and mimeType
                    seed_image = {
                        'imageBytes': image_bytes,
                        'mimeType': 'image/png'
                    }
                    self.logger.info(f"Loaded seed image: {config.image} ({len(image_bytes)} bytes)")
                except Exception as e:
                    self.logger.warning(f"Failed to load seed image: {e}, proceeding without it")

            # Create GenerateVideosConfig for additional parameters
            # Note: Only include parameters that are supported by the API
            video_config = types.GenerateVideosConfig(
                aspect_ratio=config.aspect_ratio,
                resolution=config.resolution
            )

            # Add duration to prompt since Veo doesn't have a direct duration parameter
            # Format: "X-second video of [original prompt]"
            enhanced_prompt = f"{config.duration}-second video of {config.prompt}"

            # Start generation (returns operation ID for polling)
            self.logger.info(f"Starting Veo generation with {config.model.value}")
            self.logger.info(f"Config: {config.aspect_ratio} @ {config.resolution}, duration={config.duration}s")
            self.logger.info(f"Enhanced prompt with duration: {enhanced_prompt[:100]}...")

            if seed_image:
                self.logger.info("Using seed image for image-to-video generation")
                response = self.client.models.generate_videos(
                    model=config.model.value,
                    prompt=enhanced_prompt,
                    config=video_config,
                    image=seed_image
                )
            else:
                response = self.client.models.generate_videos(
                    model=config.model.value,
                    prompt=enhanced_prompt,
                    config=video_config
                )
            
            # Store operation ID for polling
            result.operation_id = response.name
            result.metadata["model"] = config.model.value
            result.metadata["prompt"] = config.prompt
            result.metadata["started_at"] = datetime.now().isoformat()
            
            # Poll for completion
            # Documentation states 1-6 minutes typical, using 8 minutes for buffer
            constraints = self.MODEL_CONSTRAINTS[config.model]
            max_wait = 480  # 8 minutes
            
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
        Poll for video generation completion using official Google API pattern.

        Args:
            operation: Generation operation (LRO - Long Running Operation)
            max_wait: Maximum wait time in seconds

        Returns:
            Video URL if successful, None otherwise
        """
        start_time = time.time()
        poll_interval = 10  # Google docs recommend 10 second intervals
        poll_count = 0

        self.logger.info(f"Starting to poll for completion (max wait: {max_wait}s)")
        self.logger.info(f"Operation ID: {operation.name}")

        while time.time() - start_time < max_wait:
            try:
                elapsed = time.time() - start_time
                poll_count += 1

                # Log every poll attempt for first 5, then every 4th attempt
                if poll_count <= 5 or poll_count % 4 == 0:
                    self.logger.info(f"Poll #{poll_count}: Checking operation.done... ({elapsed:.0f}s elapsed, {max_wait - elapsed:.0f}s remaining)")

                # Check if operation is done (official Google pattern)
                if operation.done:
                    # Operation completed
                    elapsed_total = time.time() - start_time
                    self.logger.info(f"✅ Operation completed after {elapsed_total:.1f} seconds ({poll_count} polls)")

                    # Extract video from response (official structure from docs)
                    try:
                        if hasattr(operation, 'response') and hasattr(operation.response, 'generated_videos'):
                            generated_videos = operation.response.generated_videos
                            if generated_videos and len(generated_videos) > 0:
                                video = generated_videos[0].video
                                if hasattr(video, 'uri'):
                                    video_url = video.uri
                                    self.logger.info(f"Retrieved video URL: {video_url[:80]}...")

                                    # Parse and log video metadata if available (VEO3_FIXES enhancement)
                                    if hasattr(video, 'metadata'):
                                        metadata = video.metadata
                                        self.logger.info(f"Video metadata: {metadata}")

                                    return video_url
                                else:
                                    self.logger.error(f"Video object has no 'uri' attribute. Attributes: {dir(video)}")
                                    return None
                            else:
                                self.logger.error("No generated_videos in response")
                                return None
                        else:
                            self.logger.error(f"Unexpected response structure. Operation attributes: {dir(operation)}")
                            if hasattr(operation, 'response'):
                                self.logger.error(f"Response attributes: {dir(operation.response)}")
                            return None
                    except Exception as e:
                        self.logger.error(f"Error extracting video URL from completed operation: {e}", exc_info=True)
                        return None

                # Not done yet - wait and refresh operation status
                self.logger.debug(f"Poll #{poll_count}: Operation not done yet, waiting {poll_interval}s...")
                await asyncio.sleep(poll_interval)

                # Refresh operation status (official Google pattern)
                operation = self.client.operations.get(operation)

            except Exception as e:
                self.logger.error(f"Error polling for completion: {e}", exc_info=True)
                return None

        total_elapsed = time.time() - start_time
        self.logger.warning(f"❌ Generation timed out after {total_elapsed:.1f} seconds ({poll_count} polls, max: {max_wait}s)")
        return None
    
    async def _download_video(self, video_url: str) -> Optional[Path]:
        """
        Download video from URL to local storage with authentication.

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

            # Download video with API key authentication
            # For Google API keys (not OAuth), use key parameter instead of Bearer token
            # Remove any existing query parameters from URL and add our own
            base_url = video_url.split('?')[0]
            params = {
                "key": self.api_key,
                "alt": "media"  # Request media content
            }

            self.logger.info(f"Downloading video from {base_url[:80]}...")
            self.logger.info(f"Using API key authentication with key parameter")
            response = requests.get(base_url, params=params, stream=True, timeout=30, allow_redirects=True)
            response.raise_for_status()

            # Save to file
            file_size = 0
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    file_size += len(chunk)

            # Validate downloaded file (VEO3_FIXES enhancement)
            if file_size == 0:
                self.logger.error(f"Downloaded file is empty (0 bytes)")
                video_path.unlink(missing_ok=True)  # Delete empty file
                return None

            if not video_path.exists():
                self.logger.error(f"Video file was not created at {video_path}")
                return None

            actual_size = video_path.stat().st_size
            if actual_size != file_size:
                self.logger.warning(f"File size mismatch: wrote {file_size} bytes, file is {actual_size} bytes")

            self.logger.info(f"Video downloaded successfully to {video_path} ({file_size / (1024*1024):.2f} MB)")
            return video_path

        except requests.HTTPError as e:
            # Enhanced error logging for HTTP errors
            status_code = e.response.status_code if e.response else "unknown"
            error_body = e.response.text[:500] if e.response else "no response body"
            self.logger.error(f"HTTP error {status_code} downloading video: {error_body}")
            self.logger.error(f"Full exception: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Failed to download video: {e}", exc_info=True)
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