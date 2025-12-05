"""
OpenAI Sora 2 API client for AI video generation.

This module handles video generation using OpenAI's Sora models
with support for text-to-video and image-to-video generation.

Improvements over base plan:
- Retry logic with exponential backoff for rate limiting
- Progress callback support for GUI integration
- Cancellation support for long-running operations
- Better error categorization (rate limits vs content policy vs auth)
- HTTP fallback if SDK doesn't have .videos namespace
"""

import asyncio
import hashlib
import json
import logging
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import requests

# Check if openai is available but don't import yet
try:
    import importlib.util
    OPENAI_AVAILABLE = importlib.util.find_spec("openai") is not None
except ImportError:
    OPENAI_AVAILABLE = False

# This will be populated on first use
OpenAIClient = None


class SoraModel(Enum):
    """Available Sora models"""
    SORA_2 = "sora-2"
    SORA_2_PRO = "sora-2-pro"


class SoraErrorType(Enum):
    """Types of errors that can occur during Sora generation"""
    RATE_LIMIT = "rate_limit"
    CONTENT_POLICY = "content_policy"
    AUTH_ERROR = "auth_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class SoraGenerationConfig:
    """Configuration for Sora video generation"""
    model: SoraModel = SoraModel.SORA_2
    prompt: str = ""
    aspect_ratio: str = "16:9"  # 16:9, 9:16
    resolution: str = "720p"  # 720p, 1080p (1080p only for pro)
    duration: int = 8  # 4, 8, or 12 seconds
    image: Optional[Path] = None  # Input reference for image-to-video
    seed: Optional[int] = None  # May not be supported by all models

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Validate duration
        if self.duration not in [4, 8, 12]:
            raise ValueError(
                f"Sora duration must be 4, 8, or 12 seconds, got {self.duration}"
            )

        # Validate resolution for model
        if self.resolution == "1080p" and self.model == SoraModel.SORA_2:
            raise ValueError(
                "1080p resolution requires Sora 2 Pro model. "
                "Use SoraModel.SORA_2_PRO or reduce to 720p."
            )

        # Validate aspect ratio
        if self.aspect_ratio not in ["16:9", "9:16"]:
            raise ValueError(
                f"Sora aspect ratio must be 16:9 or 9:16, got {self.aspect_ratio}"
            )

    def get_size_string(self) -> str:
        """Convert aspect_ratio and resolution to size string for API"""
        size_map = {
            ("16:9", "720p"): "1280x720",
            ("9:16", "720p"): "720x1280",
            ("16:9", "1080p"): "1792x1024",
            ("9:16", "1080p"): "1024x1792",
        }
        return size_map.get((self.aspect_ratio, self.resolution), "1280x720")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return {
            "model": self.model.value,
            "prompt": self.prompt,
            "size": self.get_size_string(),
            "seconds": str(self.duration),
        }


@dataclass
class SoraGenerationResult:
    """Result of a Sora generation operation"""
    success: bool = False
    video_url: Optional[str] = None
    video_path: Optional[Path] = None
    video_id: Optional[str] = None
    error: Optional[str] = None
    error_type: SoraErrorType = SoraErrorType.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)
    generation_time: float = 0.0
    retry_count: int = 0


class SoraClient:
    """Client for OpenAI Sora video generation API

    Features:
    - Async generation with polling
    - Model constraints validation
    - Text-to-video and image-to-video support
    - Cost estimation
    - Batch generation with concurrency control
    - Retry logic with exponential backoff
    - Progress callbacks for GUI integration
    - Cancellation support
    """

    # Model constraints
    MODEL_CONSTRAINTS = {
        SoraModel.SORA_2: {
            "max_duration": 12,
            "durations": [4, 8, 12],
            "resolutions": ["720p"],
            "aspect_ratios": ["16:9", "9:16"],
            "supports_image_input": True,
            "generation_time": (60, 120),  # 1-2 minutes typical
            "cost_per_second": {
                "720p": 0.10,
            }
        },
        SoraModel.SORA_2_PRO: {
            "max_duration": 12,
            "durations": [4, 8, 12],
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16"],
            "supports_image_input": True,
            "generation_time": (90, 180),  # 1.5-3 minutes typical
            "cost_per_second": {
                "720p": 0.30,
                "1080p": 0.50,
            }
        }
    }

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 5  # seconds
    MAX_RETRY_DELAY = 60  # seconds

    def __init__(
        self,
        api_key: str,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize Sora client.

        Args:
            api_key: OpenAI API key
            progress_callback: Optional callback for progress updates (percent, message)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        global OpenAIClient
        if OpenAIClient is None:
            from openai import OpenAI as OpenAIClient

        self.api_key = api_key
        self.client = OpenAIClient(api_key=api_key)
        self.logger = logging.getLogger(__name__)
        self.progress_callback = progress_callback
        self._cancelled = False

        # Check if SDK has videos namespace (it may not yet)
        self._use_http = not hasattr(self.client, 'videos')
        if self._use_http:
            self.logger.info("OpenAI SDK does not have .videos namespace, using HTTP API")
            self._api_base = "https://api.openai.com/v1"

    def cancel(self):
        """Cancel ongoing generation"""
        self._cancelled = True
        self.logger.info("Cancellation requested")

    def reset_cancellation(self):
        """Reset cancellation flag for new generation"""
        self._cancelled = False

    def _report_progress(self, percent: int, message: str):
        """Report progress if callback is set"""
        self.logger.info(f"Progress {percent}%: {message}")
        if self.progress_callback:
            try:
                self.progress_callback(percent, message)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")

    def _classify_error(self, error: Exception) -> SoraErrorType:
        """Classify an exception into an error type"""
        error_str = str(error).lower()

        if "rate" in error_str and "limit" in error_str:
            return SoraErrorType.RATE_LIMIT
        elif "content" in error_str and "policy" in error_str:
            return SoraErrorType.CONTENT_POLICY
        elif "auth" in error_str or "api key" in error_str or "unauthorized" in error_str:
            return SoraErrorType.AUTH_ERROR
        elif "quota" in error_str or "billing" in error_str:
            return SoraErrorType.QUOTA_EXCEEDED
        elif "timeout" in error_str:
            return SoraErrorType.TIMEOUT
        elif "connection" in error_str or "network" in error_str:
            return SoraErrorType.NETWORK_ERROR
        else:
            return SoraErrorType.API_ERROR

    def _should_retry(self, error_type: SoraErrorType) -> bool:
        """Determine if an error type should be retried"""
        # Only retry rate limits and network errors
        return error_type in [SoraErrorType.RATE_LIMIT, SoraErrorType.NETWORK_ERROR]

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter"""
        delay = min(
            self.BASE_RETRY_DELAY * (2 ** attempt),
            self.MAX_RETRY_DELAY
        )
        # Add jitter (0-25% of delay)
        jitter = delay * random.uniform(0, 0.25)
        return delay + jitter

    def validate_config(self, config: SoraGenerationConfig) -> Tuple[bool, Optional[str]]:
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
        if config.duration not in constraints["durations"]:
            return False, f"Duration {config.duration}s not supported. Use: {constraints['durations']}"

        # Check resolution
        if config.resolution not in constraints["resolutions"]:
            return False, f"Resolution {config.resolution} not supported for {config.model.value}. Use: {constraints['resolutions']}"

        # Check aspect ratio
        if config.aspect_ratio not in constraints["aspect_ratios"]:
            return False, f"Aspect ratio {config.aspect_ratio} not supported. Use: {constraints['aspect_ratios']}"

        return True, None

    async def generate_video_async(self, config: SoraGenerationConfig) -> SoraGenerationResult:
        """
        Generate video asynchronously using Sora API.

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        self.reset_cancellation()
        result = SoraGenerationResult()

        # Validate configuration
        is_valid, error = self.validate_config(config)
        if not is_valid:
            result.success = False
            result.error = error
            result.error_type = SoraErrorType.API_ERROR
            return result

        attempt = 0
        while attempt <= self.MAX_RETRIES:
            if self._cancelled:
                result.success = False
                result.error = "Generation cancelled by user"
                return result

            try:
                result = await self._generate_video_internal(config, attempt)
                if result.success:
                    return result

                # Check if we should retry
                if self._should_retry(result.error_type) and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    self._report_progress(
                        0,
                        f"Rate limited, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                else:
                    return result

            except Exception as e:
                self.logger.error(f"Sora generation attempt {attempt + 1} failed: {e}")
                error_type = self._classify_error(e)
                result.error = str(e)
                result.error_type = error_type

                if self._should_retry(error_type) and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    self._report_progress(
                        0,
                        f"Error occurred, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                else:
                    result.success = False
                    return result

        return result

    async def _generate_video_internal(
        self,
        config: SoraGenerationConfig,
        attempt: int
    ) -> SoraGenerationResult:
        """Internal video generation implementation"""
        result = SoraGenerationResult()
        result.retry_count = attempt

        try:
            start_time = time.time()
            self._report_progress(5, f"Starting Sora generation with {config.model.value}")

            # Build request parameters
            create_params = config.to_dict()

            self.logger.info(f"Starting Sora generation with {config.model.value}")
            self.logger.info(f"Config: {config.aspect_ratio}, {config.resolution}, {config.duration}s")
            self.logger.info(f"Size string: {config.get_size_string()}")
            self.logger.info(f"Prompt: {config.prompt[:100]}...")

            # Determine generation mode
            if config.image and config.image.exists():
                self._report_progress(10, "Loading input reference image...")
                self.logger.info(f"Using input reference image: {config.image}")
                video_id = await self._create_video_with_image(create_params, config.image)
            else:
                self._report_progress(10, "Creating text-to-video generation...")
                video_id = await self._create_video(create_params)

            if self._cancelled:
                result.error = "Generation cancelled by user"
                return result

            # Store video ID
            result.video_id = video_id
            result.metadata["model"] = config.model.value
            result.metadata["prompt"] = config.prompt
            result.metadata["started_at"] = datetime.now().isoformat()

            self.logger.info(f"Video creation initiated, ID: {video_id}")
            self._report_progress(15, f"Video queued (ID: {video_id[:8]}...)")

            # Poll for completion
            max_wait = 480  # 8 minutes max
            video_result = await self._poll_for_completion(video_id, max_wait)

            if self._cancelled:
                result.error = "Generation cancelled by user"
                return result

            if video_result:
                result.success = True
                self._report_progress(90, "Downloading video...")

                # Download video to local storage
                result.video_path = await self._download_video(video_id)
                result.metadata["completed_at"] = datetime.now().isoformat()

                self._report_progress(100, "Video generation complete!")
            else:
                result.success = False
                result.error = "Generation timed out or failed"
                result.error_type = SoraErrorType.TIMEOUT

            result.generation_time = time.time() - start_time
            self.logger.info(f"Generation completed in {result.generation_time:.1f} seconds")

        except Exception as e:
            self.logger.error(f"Sora generation failed: {e}")
            result.success = False
            result.error = str(e)
            result.error_type = self._classify_error(e)

        return result

    async def _create_video(self, params: Dict[str, Any]) -> str:
        """Create video generation request (text-to-video)"""
        if self._use_http:
            return await self._create_video_http(params)
        else:
            response = self.client.videos.create(**params)
            return response.id

    async def _create_video_with_image(
        self,
        params: Dict[str, Any],
        image_path: Path
    ) -> str:
        """Create video generation request with image reference (image-to-video)"""
        if self._use_http:
            return await self._create_video_with_image_http(params, image_path)
        else:
            with open(image_path, 'rb') as f:
                response = self.client.videos.create(
                    **params,
                    input_reference=f
                )
            return response.id

    async def _create_video_http(self, params: Dict[str, Any]) -> str:
        """Create video using HTTP API (fallback)"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            f"{self._api_base}/videos",
            headers=headers,
            json=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data.get("id", "")

    async def _create_video_with_image_http(
        self,
        params: Dict[str, Any],
        image_path: Path
    ) -> str:
        """Create video with image using HTTP API (fallback, multipart)"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        with open(image_path, 'rb') as f:
            files = {
                'input_reference': (image_path.name, f, 'image/png')
            }
            data = params

            response = requests.post(
                f"{self._api_base}/videos",
                headers=headers,
                data=data,
                files=files,
                timeout=60
            )
        response.raise_for_status()
        result = response.json()
        return result.get("id", "")

    async def _poll_for_completion(
        self,
        video_id: str,
        max_wait: int
    ) -> Optional[Dict[str, Any]]:
        """
        Poll for video generation completion.

        Args:
            video_id: Video generation ID
            max_wait: Maximum wait time in seconds

        Returns:
            Video info dict if successful, None otherwise
        """
        start_time = time.time()
        poll_interval = 10  # 10 second intervals as recommended
        poll_count = 0

        self.logger.info(f"Polling for completion (max wait: {max_wait}s)")

        while time.time() - start_time < max_wait:
            if self._cancelled:
                self.logger.info("Polling cancelled by user")
                return None

            try:
                elapsed = time.time() - start_time
                poll_count += 1

                # Report progress (15% to 90%)
                progress = 15 + int((elapsed / max_wait) * 75)
                progress = min(progress, 90)

                if poll_count <= 5 or poll_count % 4 == 0:
                    self.logger.info(f"Poll #{poll_count}: Checking status... ({elapsed:.0f}s elapsed)")
                    self._report_progress(progress, f"Generating video... ({elapsed:.0f}s elapsed)")

                # Retrieve video status
                if self._use_http:
                    status_data = await self._get_video_status_http(video_id)
                else:
                    status_response = self.client.videos.retrieve(video_id)
                    status_data = {
                        "status": status_response.status,
                        "url": getattr(status_response, "url", None),
                        "error": getattr(status_response, "error", None)
                    }

                status = status_data.get("status", "unknown")
                self.logger.debug(f"Status: {status}")

                if status == "completed":
                    self.logger.info(f"Video completed after {elapsed:.1f}s ({poll_count} polls)")
                    return status_data
                elif status == "failed":
                    error = status_data.get("error", "Unknown error")
                    self.logger.error(f"Video generation failed: {error}")
                    return None
                elif status == "cancelled":
                    self.logger.info("Video generation was cancelled on the server")
                    return None
                elif status in ["queued", "in_progress", "processing", "preprocessing", "running"]:
                    # Still processing, continue polling
                    await asyncio.sleep(poll_interval)
                else:
                    self.logger.warning(f"Unknown status: {status}")
                    await asyncio.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"Error polling for completion: {e}")
                # Don't return None immediately, retry polling
                await asyncio.sleep(poll_interval)

        self.logger.warning(f"Generation timed out after {max_wait}s")
        return None

    async def _get_video_status_http(self, video_id: str) -> Dict[str, Any]:
        """Get video status using HTTP API (fallback)"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        response = requests.get(
            f"{self._api_base}/videos/{video_id}",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    async def _download_video(self, video_id: str) -> Optional[Path]:
        """
        Download video content to local storage.

        Args:
            video_id: Video ID

        Returns:
            Local path to downloaded video
        """
        try:
            # Create cache directory
            cache_dir = Path.home() / ".imageai" / "cache" / "sora_videos"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sora_{timestamp}_{video_id[:8]}.mp4"
            video_path = cache_dir / filename

            self.logger.info(f"Downloading video {video_id}...")

            # Download video content using the API
            if self._use_http:
                content = await self._download_video_http(video_id)
                # Write to file
                with open(video_path, 'wb') as f:
                    f.write(content)
            else:
                # Use SDK's download_content method which writes directly to file
                content_response = self.client.videos.download_content(
                    video_id,
                    variant="video"
                )
                content_response.write_to_file(str(video_path))

            file_size = video_path.stat().st_size
            self.logger.info(f"Video downloaded to {video_path} ({file_size / (1024*1024):.2f} MB)")

            return video_path

        except Exception as e:
            self.logger.error(f"Failed to download video: {e}")
            return None

    async def _download_video_http(self, video_id: str) -> bytes:
        """Download video using HTTP API (fallback)"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        response = requests.get(
            f"{self._api_base}/videos/{video_id}/content",
            headers=headers,
            timeout=120,
            stream=True
        )
        response.raise_for_status()
        return response.content

    def generate_video(self, config: SoraGenerationConfig) -> SoraGenerationResult:
        """
        Generate video synchronously (blocking).

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.generate_video_async(config))
        finally:
            loop.close()

    def estimate_cost(self, config: SoraGenerationConfig) -> float:
        """
        Estimate generation cost in USD.

        Args:
            config: Generation configuration

        Returns:
            Estimated cost
        """
        constraints = self.MODEL_CONSTRAINTS.get(config.model, {})
        cost_map = constraints.get("cost_per_second", {})
        cost_per_second = cost_map.get(config.resolution, 0.10)
        return config.duration * cost_per_second

    def get_model_info(self, model: SoraModel) -> Dict[str, Any]:
        """Get information about a Sora model"""
        constraints = self.MODEL_CONSTRAINTS.get(model, {})
        return {
            "name": model.value,
            "max_duration": constraints.get("max_duration", 12),
            "durations": constraints.get("durations", [4, 8, 12]),
            "resolutions": constraints.get("resolutions", []),
            "aspect_ratios": constraints.get("aspect_ratios", []),
            "supports_image_input": constraints.get("supports_image_input", False),
            "generation_time": constraints.get("generation_time", (60, 180)),
        }

    def generate_batch(
        self,
        configs: List[SoraGenerationConfig],
        max_concurrent: int = 2
    ) -> List[SoraGenerationResult]:
        """
        Generate multiple videos in batch with concurrency control.

        Args:
            configs: List of generation configurations
            max_concurrent: Maximum concurrent generations (default 2 for rate limits)

        Returns:
            List of generation results
        """
        results = []

        for i in range(0, len(configs), max_concurrent):
            if self._cancelled:
                # Fill remaining with cancelled results
                for _ in configs[i:]:
                    result = SoraGenerationResult()
                    result.error = "Batch generation cancelled"
                    results.append(result)
                break

            batch = configs[i:i + max_concurrent]

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                tasks = [self.generate_video_async(config) for config in batch]
                batch_results = loop.run_until_complete(asyncio.gather(*tasks))
                results.extend(batch_results)
            finally:
                loop.close()

        return results

    def create_and_poll(
        self,
        config: SoraGenerationConfig,
        poll_interval: int = 10
    ) -> SoraGenerationResult:
        """
        Create video and poll until completion (convenience method matching SDK).

        This mirrors the official OpenAI SDK's `client.videos.create_and_poll()` method.

        Args:
            config: Generation configuration
            poll_interval: Seconds between status checks (default 10)

        Returns:
            Generation result with video path on success
        """
        return self.generate_video(config)

    async def create_and_poll_async(
        self,
        config: SoraGenerationConfig,
        poll_interval: int = 10
    ) -> SoraGenerationResult:
        """
        Async version of create_and_poll.

        This mirrors the official OpenAI SDK's `client.videos.create_and_poll()` method.

        Args:
            config: Generation configuration
            poll_interval: Seconds between status checks (default 10)

        Returns:
            Generation result with video path on success
        """
        return await self.generate_video_async(config)

    def list_videos(
        self,
        limit: int = 20,
        after: Optional[str] = None,
        order: str = "desc"
    ) -> Dict[str, Any]:
        """
        List videos in your library with pagination.

        Args:
            limit: Maximum number of videos to return (default 20)
            after: Cursor for pagination (video ID to start after)
            order: Sort order - "asc" or "desc" (default "desc")

        Returns:
            Dictionary with 'data' list and pagination info
        """
        try:
            if self._use_http:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }
                params = {"limit": limit, "order": order}
                if after:
                    params["after"] = after

                response = requests.get(
                    f"{self._api_base}/videos",
                    headers=headers,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
            else:
                # Use SDK method
                response = self.client.videos.list(limit=limit, after=after, order=order)
                return {
                    "data": [v.model_dump() for v in response.data],
                    "has_more": response.has_more,
                }
        except Exception as e:
            self.logger.error(f"Failed to list videos: {e}")
            return {"data": [], "error": str(e)}

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific video.

        Args:
            video_id: Video ID to retrieve

        Returns:
            Video details dictionary or None on error
        """
        try:
            if self._use_http:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }
                response = requests.get(
                    f"{self._api_base}/videos/{video_id}",
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
            else:
                video = self.client.videos.retrieve(video_id)
                return video.model_dump()
        except Exception as e:
            self.logger.error(f"Failed to get video {video_id}: {e}")
            return None

    def delete_video(self, video_id: str) -> bool:
        """
        Delete a video from OpenAI's servers.

        Args:
            video_id: Video ID to delete

        Returns:
            True if successful
        """
        try:
            if self._use_http:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }
                response = requests.delete(
                    f"{self._api_base}/videos/{video_id}",
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
            else:
                self.client.videos.delete(video_id)
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete video {video_id}: {e}")
            return False

    def download_thumbnail(self, video_id: str, output_path: Path) -> bool:
        """
        Download thumbnail image for a video.

        Args:
            video_id: Video ID
            output_path: Path to save thumbnail

        Returns:
            True if successful
        """
        try:
            if self._use_http:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }
                response = requests.get(
                    f"{self._api_base}/videos/{video_id}/content",
                    headers=headers,
                    params={"variant": "thumbnail"},
                    timeout=60
                )
                response.raise_for_status()
                with open(output_path, 'wb') as f:
                    f.write(response.content)
            else:
                content = self.client.videos.download_content(video_id, variant="thumbnail")
                content.write_to_file(str(output_path))
            return True
        except Exception as e:
            self.logger.error(f"Failed to download thumbnail for {video_id}: {e}")
            return False

    def download_spritesheet(self, video_id: str, output_path: Path) -> bool:
        """
        Download spritesheet (preview frames) for a video.

        Args:
            video_id: Video ID
            output_path: Path to save spritesheet

        Returns:
            True if successful
        """
        try:
            if self._use_http:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }
                response = requests.get(
                    f"{self._api_base}/videos/{video_id}/content",
                    headers=headers,
                    params={"variant": "spritesheet"},
                    timeout=60
                )
                response.raise_for_status()
                with open(output_path, 'wb') as f:
                    f.write(response.content)
            else:
                content = self.client.videos.download_content(video_id, variant="spritesheet")
                content.write_to_file(str(output_path))
            return True
        except Exception as e:
            self.logger.error(f"Failed to download spritesheet for {video_id}: {e}")
            return False
