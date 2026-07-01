"""
Google Gemini Omni client for AI video generation via the Interactions API.

Gemini Omni (``gemini-omni-flash-preview``) is a fast, conversational
video-generation model driven through Google's **Interactions API**
(``client.interactions.create``), *not* the Veo ``generate_videos`` endpoint.
It supports text-to-video, image-to-video, and stateful conversational editing
(via ``previous_interaction_id``) with audio in the output.

Implementation notes (verified against ``google-genai`` 2.9.0, the GeminiNextGen
``client.interactions`` surface — the older 2.8.0 ``_interactions`` surface lacked
``output_video`` and is NOT compatible, hence the >=2.9.0 floor):
- Video + aspect ratio are requested with ``response_format={"type": "video",
  "aspect_ratio": "16:9"|"9:16"}`` (a dict), per the Omni docs. The aspect ratio
  is never embedded in the prompt text (AGENTS.md §9).
- The generated video is read from ``interaction.output_video`` (a ``VideoContent``
  with base64 ``data`` and/or a ``uri``); we keep a defensive fallback that walks
  ``interaction.steps`` for a video content item.
- ``gemini-omni-flash-preview`` is resolved via ``resolve_model`` so the ID is not
  hard-coded (AGENTS.md §8).
"""

import asyncio
import base64
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.llm_models import resolve_model

# Check if google.genai (with the Interactions API) is available.
try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None


# Terminal Interaction statuses (from google.genai interactions.Interaction).
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "incomplete", "budget_exceeded"}
_FAILED_STATUSES = {"failed", "cancelled", "incomplete", "budget_exceeded"}

# Reference-image MIME types by file suffix (for image-to-video input).
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class OmniModel(Enum):
    """Available Gemini Omni models.

    The ID is resolved through the model registry at access time so it tracks
    the published registry and is never hard-coded (AGENTS.md §8). The preview
    string is the offline fallback.
    """

    OMNI_FLASH = "gemini-omni-flash-preview"

    @classmethod
    def default_id(cls) -> str:
        """Resolve the current Omni model ID (registry-first, static fallback)."""
        return resolve_model("google", "omni", static_default=cls.OMNI_FLASH.value)


@dataclass
class OmniGenerationConfig:
    """Configuration for a Gemini Omni video generation/edit request."""

    prompt: str = ""
    model: str = ""  # Resolved Omni model ID; defaults via __post_init__.
    aspect_ratio: str = "16:9"  # "16:9" (landscape) or "9:16" (portrait).
    reference_image: Optional[Path] = None  # Back-compat single ref; folds into reference_images.
    reference_images: List[Path] = field(default_factory=list)  # Subject/first-frame refs.
    previous_interaction_id: Optional[str] = None  # Chain a conversational edit.
    delivery: Optional[str] = None  # None/"inline" (base64) or "uri" (Files API; big clips).
    # Task sent as generation_config.video_config.task; inferred when left "".
    task: str = ""

    def __post_init__(self):
        if not self.model:
            self.model = OmniModel.default_id()

        if self.reference_image is not None and not self.reference_images:
            self.reference_images = [Path(self.reference_image)]
        self.reference_images = [Path(p) for p in self.reference_images]

        max_refs = OmniClient.MODEL_CONSTRAINTS["max_reference_images"]
        if len(self.reference_images) > max_refs:
            raise ValueError(
                f"Gemini Omni supports at most {max_refs} reference image(s); "
                f"got {len(self.reference_images)}."
            )

        if not self.task:
            self.task = self._infer_task()

        if self.aspect_ratio not in OmniClient.MODEL_CONSTRAINTS["aspect_ratios"]:
            raise ValueError(
                f"aspect_ratio {self.aspect_ratio!r} not supported by Gemini Omni. "
                f"Use one of {OmniClient.MODEL_CONSTRAINTS['aspect_ratios']}."
            )

        valid_tasks = OmniClient.MODEL_CONSTRAINTS["tasks"]
        if self.task not in valid_tasks:
            raise ValueError(f"task {self.task!r} invalid. Use one of {valid_tasks}.")

        # image_to_video / reference_to_video require a reference image.
        if self.task in ("image_to_video", "reference_to_video") and not self.reference_images:
            raise ValueError(
                f"task {self.task!r} requires a reference_image, but none was provided."
            )

        if self.delivery not in (None, "inline", "uri"):
            raise ValueError(
                f"delivery {self.delivery!r} invalid. Use 'inline' or 'uri'."
            )

    def _infer_task(self) -> str:
        """Infer the video_config task from the input shape (docs task enum)."""
        if self.previous_interaction_id:
            return "edit"
        if len(self.reference_images) >= 2:
            return "reference_to_video"
        if self.reference_images:
            return "image_to_video"
        return "text_to_video"

    def to_interaction_kwargs(self) -> Dict[str, Any]:
        """Build the kwargs for ``client.interactions.create(**kwargs)``.

        Matches the documented Gemini Omni request shape: video output and
        aspect ratio are requested via ``response_format={"type": "video",
        "aspect_ratio": ...}`` (a dict). The aspect ratio is never placed in the
        prompt text (AGENTS.md §9). With reference images, ``input`` is a content
        list ``[{image}, ..., {text}]``; otherwise it is the plain prompt string.
        """
        content: List[Dict[str, Any]] = []
        for ref in self.reference_images:
            image_bytes = Path(ref).read_bytes()
            b64 = base64.b64encode(image_bytes).decode("ascii")
            mime = _IMAGE_MIME_BY_SUFFIX.get(Path(ref).suffix.lower(), "image/png")
            content.append({"type": "image", "data": b64, "mime_type": mime})

        if content:
            content.append({"type": "text", "text": self.prompt})
            input_payload: Any = content
        else:
            input_payload = self.prompt

        response_format: Dict[str, Any] = {
            "type": "video", "aspect_ratio": self.aspect_ratio
        }
        if self.delivery == "uri":
            # Docs recommend URI delivery for clips over ~4MB / higher res.
            response_format["delivery"] = "uri"

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "input": input_payload,
            "response_format": response_format,
            "generation_config": {"video_config": {"task": self.task}},
        }
        if self.previous_interaction_id:
            kwargs["previous_interaction_id"] = self.previous_interaction_id
        return kwargs


@dataclass
class OmniGenerationResult:
    """Result of a Gemini Omni generation/edit operation."""

    success: bool = True
    video_path: Optional[Path] = None
    interaction_id: Optional[str] = None  # Feeds previous_interaction_id for edits.
    error: Optional[str] = None
    generation_time: float = 0.0
    has_synthid: bool = True  # Omni outputs carry a SynthID watermark.
    metadata: Dict[str, Any] = field(default_factory=dict)


class OmniClient:
    """Client for Gemini Omni video generation via the Interactions API."""

    MODEL_CONSTRAINTS = {
        "aspect_ratios": ["16:9", "9:16"],
        "tasks": ["text_to_video", "image_to_video", "reference_to_video", "edit"],
        "max_reference_images": 3,  # Docs show multi-subject refs (<IMAGE_REF_N>, N=0..2).
        "deliveries": ["inline", "uri"],
        "duration_range": (3, 10),  # seconds (informational; no SDK duration field)
        "fps": 24,
        "resolution": "720p",
        "supports_audio": True,
        "supports_conversational_edit": True,
    }

    def __init__(self, api_key: Optional[str] = None,
                 polling_interval: int = 10, timeout: int = 600):
        """Initialize the Omni client.

        Args:
            api_key: Google API key. Omni is authenticated with a plain API key
                (same key path as the existing Gemini image provider).
            polling_interval: Seconds between status polls for long generations.
            timeout: Maximum seconds to wait for a generation to finish.
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-genai not installed. Run: pip install 'google-genai>=2.3.0'"
            )

        self.api_key = api_key
        self.polling_interval = polling_interval
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self.client = genai.Client(api_key=api_key) if api_key else None

    def validate_config(self, config: OmniGenerationConfig) -> Tuple[bool, Optional[str]]:
        """Validate a config against model constraints (config also self-validates)."""
        if config.aspect_ratio not in self.MODEL_CONSTRAINTS["aspect_ratios"]:
            return False, (
                f"Aspect ratio {config.aspect_ratio} not supported. "
                f"Use: {self.MODEL_CONSTRAINTS['aspect_ratios']}"
            )
        if config.task not in self.MODEL_CONSTRAINTS["tasks"]:
            return False, f"Task {config.task} not supported."
        for ref in (config.reference_images or []):
            if not Path(ref).exists():
                return False, f"Reference image not found: {ref}"
        return True, None

    async def generate_video_async(self, config: OmniGenerationConfig,
                                   output_path: Path) -> OmniGenerationResult:
        """Generate (or conversationally edit) a video with Gemini Omni.

        Args:
            config: Generation configuration.
            output_path: Where to write the resulting MP4.

        Returns:
            OmniGenerationResult with the saved path and interaction id.
        """
        result = OmniGenerationResult()
        start_time = time.time()

        is_valid, error = self.validate_config(config)
        if not is_valid:
            result.success = False
            result.error = error
            self.logger.error(f"Omni config invalid: {error}")
            return result

        if not self.client:
            result.success = False
            result.error = "No client configured. API key required for Omni generation."
            self.logger.error(result.error)
            return result

        try:
            kwargs = config.to_interaction_kwargs()

            # Log the full request (AGENTS.md §8 — show everything sent to the LLM).
            self.logger.info("=" * 60)
            self.logger.info(f"Gemini Omni request — model={config.model} task={config.task}")
            self.logger.info(f"  aspect_ratio={config.aspect_ratio} "
                             f"reference_image={config.reference_image} "
                             f"previous_interaction_id={config.previous_interaction_id}")
            self.logger.info(f"  Prompt:\n{config.prompt}")
            self.logger.info("=" * 60)

            # Synchronous create; long generations may still come back in_progress,
            # in which case we poll interactions.get() until terminal.
            interaction = await asyncio.to_thread(
                self.client.interactions.create, **kwargs
            )

            interaction = await self._await_terminal(interaction)
            result.interaction_id = getattr(interaction, "id", None)
            status = getattr(interaction, "status", None)
            self.logger.info(f"Omni interaction {result.interaction_id} status={status}")

            if status in _FAILED_STATUSES:
                result.success = False
                result.error = f"Omni generation {status}: {self._error_text(interaction)}"
                self.logger.error(result.error)
                return result

            # Extract the video content from the interaction steps.
            video_data, video_uri, mime = self._extract_video(interaction)
            if video_data is None and video_uri is None:
                result.success = False
                result.error = "Omni response contained no video content."
                self.logger.error(result.error)
                self.logger.error(f"Interaction steps: {getattr(interaction, 'steps', None)}")
                return result

            video_bytes = video_data
            if video_bytes is None and video_uri:
                video_bytes = await self._download_uri(video_uri)

            if not video_bytes:
                result.success = False
                result.error = "Failed to obtain video bytes from Omni response."
                self.logger.error(result.error)
                return result

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_bytes)

            result.success = True
            result.video_path = output_path
            result.metadata.update({
                "model": config.model,
                "task": config.task,
                "aspect_ratio": config.aspect_ratio,
                "mime_type": mime,
                "interaction_id": result.interaction_id,
                "generated_at": datetime.now().isoformat(),
            })
            result.generation_time = time.time() - start_time
            self.logger.info(
                f"Omni video saved to {output_path} "
                f"({len(video_bytes) / (1024 * 1024):.2f} MB) in "
                f"{result.generation_time:.1f}s"
            )

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.generation_time = time.time() - start_time
            self.logger.error(f"Omni generation failed: {e}", exc_info=True)

        return result

    def generate_video(self, config: OmniGenerationConfig,
                        output_path: Path) -> OmniGenerationResult:
        """Synchronous wrapper around :meth:`generate_video_async`."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.generate_video_async(config, output_path))
        finally:
            loop.close()

    async def _await_terminal(self, interaction: Any) -> Any:
        """Poll ``interactions.get`` until the interaction reaches a terminal state."""
        status = getattr(interaction, "status", None)
        if status in _TERMINAL_STATUSES:
            return interaction

        interaction_id = getattr(interaction, "id", None)
        if not interaction_id:
            return interaction

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            await asyncio.sleep(self.polling_interval)
            try:
                interaction = await asyncio.to_thread(
                    self.client.interactions.get, interaction_id
                )
            except Exception as e:
                self.logger.warning(f"Polling interactions.get failed: {e}")
                continue
            status = getattr(interaction, "status", None)
            self.logger.debug(f"Omni interaction {interaction_id} status={status}")
            if status in _TERMINAL_STATUSES:
                return interaction

        self.logger.warning(
            f"Omni interaction {interaction_id} did not finish within {self.timeout}s"
        )
        return interaction

    @classmethod
    def _extract_video(cls, interaction: Any) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        """Return (video_bytes, uri, mime_type) for a completed interaction.

        The documented path is ``interaction.output_video`` (a ``VideoContent``
        with base64 ``data`` and/or a ``uri``). As a defensive fallback we also
        walk ``interaction.steps`` for a ``ModelOutputStep`` containing a video
        content item, in case a delivery variant returns it there.
        """
        # Primary: interaction.output_video (VideoContent) per the Omni docs.
        out = getattr(interaction, "output_video", None)
        if out is not None:
            data, uri, mime = cls._video_content_parts(out)
            if data is not None or uri is not None:
                return data, uri, mime

        # Fallback: walk steps -> ModelOutputStep.content -> video item.
        steps = getattr(interaction, "steps", None) or []
        for step in steps:
            content = getattr(step, "content", None)
            if not content:
                continue
            for item in content:
                item_type = getattr(item, "type", None)
                if item_type is None and isinstance(item, dict):
                    item_type = item.get("type")
                if item_type != "video":
                    continue
                return cls._video_content_parts(item)
        return None, None, None

    @staticmethod
    def _video_content_parts(item: Any) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        """Decode a VideoContent-like item (object or dict) to (bytes, uri, mime)."""
        if isinstance(item, dict):
            data, uri, mime = item.get("data"), item.get("uri"), item.get("mime_type")
        else:
            data = getattr(item, "data", None)
            uri = getattr(item, "uri", None)
            mime = getattr(item, "mime_type", None)
        video_bytes = None
        if data:
            try:
                video_bytes = base64.b64decode(data)
            except Exception:
                video_bytes = None
        return video_bytes, uri, mime

    async def _download_uri(self, uri: str) -> Optional[bytes]:
        """Download video bytes for a Files-API URI, polling until ACTIVE."""
        try:
            file_name = uri.split("/")[-1]
            deadline = time.time() + self.timeout
            became_active = False
            while time.time() < deadline:
                info = await asyncio.to_thread(self.client.files.get, name=f"files/{file_name}")
                state = getattr(getattr(info, "state", None), "name", None) or getattr(info, "state", None)
                if state == "ACTIVE":
                    became_active = True
                    break
                if state == "FAILED":
                    self.logger.error(f"Files API reports FAILED for {uri}")
                    return None
                await asyncio.sleep(self.polling_interval)
            # Only download once the file is ACTIVE; otherwise we'd risk writing a
            # partial/empty MP4 on timeout. Fail cleanly instead.
            if not became_active:
                self.logger.error(
                    f"Files API did not reach ACTIVE for {uri} within {self.timeout}s"
                )
                return None
            data = await asyncio.to_thread(self.client.files.download, file=uri)
            return data
        except Exception as e:
            self.logger.error(f"Failed to download Omni video URI {uri}: {e}", exc_info=True)
            return None

    @staticmethod
    def _error_text(interaction: Any) -> str:
        """Best-effort extraction of an error message from a failed interaction."""
        for attr in ("error", "status_message", "incomplete_details"):
            val = getattr(interaction, attr, None)
            if val:
                return str(val)
        return "no error detail provided"
