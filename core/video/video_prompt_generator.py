"""
Video prompt generator using LLM for Veo motion/camera instructions.

This module provides LLM-based generation of video prompts that describe
camera movement and scene evolution for video generation.
"""

import logging
from typing import Optional
from dataclasses import dataclass


@dataclass
class VideoPromptContext:
    """Context information for video prompt generation"""
    start_prompt: str
    duration: float = 6.0
    style: str = "cinematic"
    enable_camera_movements: bool = True
    enable_prompt_flow: bool = True
    previous_video_prompt: Optional[str] = None
    lyric_timings: Optional[list] = None  # For batched scenes: [{'text': '...', 'start_sec': 0.0, 'end_sec': 2.5, 'duration_sec': 2.5}, ...]


class VideoPromptGenerator:
    """Generate video motion prompts using LLM for Veo video generation"""

    # System prompt for LLM with camera movements
    SYSTEM_PROMPT_WITH_CAMERA = """You are a video motion specialist. Given a static image description, generate a video prompt that describes camera movement and action.

The video prompt should:
- Start with the static scene description
- Add camera movement (pan, zoom, dolly, tilt, etc.)
- Add subtle motion or changes over time
- Be optimized for Google Veo video generation
- Be 2-3 sentences maximum
- NEVER include quoted text or lyrics (they will render as text in the video)

Format: [Static scene], [camera movement], [motion/changes]"""

    # System prompt for LLM without camera movements
    SYSTEM_PROMPT_NO_CAMERA = """You are a video motion specialist. Given a static image description, generate a video prompt that describes subject motion and temporal progression.

The video prompt should:
- Start with the static scene description
- Focus on subject/character actions and environmental motion
- Keep camera mostly static (minimal camera movement only when essential)
- Add subtle motion or changes over time
- Be optimized for Google Veo video generation
- Be 2-3 sentences maximum
- NEVER include quoted text or lyrics (they will render as text in the video)

Format: [Static scene], [subject motion], [temporal progression]"""

    # System prompt for prompt flow (text continuity between scenes)
    SYSTEM_PROMPT_WITH_FLOW = """You are a video motion specialist. Given a static image description and the previous scene's video prompt, generate a video prompt that flows naturally from the previous scene.

The video prompt should:
- Continue the motion/energy from the previous scene
- Maintain visual and temporal continuity
- Add camera movement (pan, zoom, dolly, tilt, etc.)
- Add subtle motion or changes over time
- Be optimized for Google Veo video generation
- Be 2-3 sentences maximum
- NEVER include quoted text or lyrics (they will render as text in the video)

Format: [Static scene continuing from previous], [camera movement], [motion/changes]"""

    def __init__(self, llm_provider=None, llm_model=None, config=None):
        """
        Initialize video prompt generator.

        Args:
            llm_provider: LLM provider name (e.g., 'openai', 'gemini', 'anthropic')
            llm_model: Model name for the provider
            config: Configuration object (optional, for API keys)
        """
        self.logger = logging.getLogger(__name__)
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.config = config

    def is_available(self) -> bool:
        """Check if LLM provider and model are configured"""
        return bool(self.llm_provider and self.llm_model)

    def generate_video_prompt(
        self,
        context: VideoPromptContext,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Optional[str]:
        """
        Generate video motion prompt using LLM.

        Args:
            context: Context information for generation
            provider: LLM provider to use (overrides instance default)
            model: Model name (overrides instance default)
            temperature: Temperature for generation (0.0-1.0)

        Returns:
            Generated video prompt, or None if generation fails
        """
        # Use provided or instance defaults
        provider = provider or self.llm_provider
        model = model or self.llm_model

        if not provider or not model:
            self.logger.error("LLM provider and model must be specified")
            return self._fallback_prompt(context)

        # Select system prompt based on settings
        if context.enable_prompt_flow and context.previous_video_prompt:
            system_prompt = self.SYSTEM_PROMPT_WITH_FLOW
        elif context.enable_camera_movements:
            system_prompt = self.SYSTEM_PROMPT_WITH_CAMERA
        else:
            system_prompt = self.SYSTEM_PROMPT_NO_CAMERA

        # Build user prompt based on context
        timing_info = ""
        if context.lyric_timings and len(context.lyric_timings) > 1:
            timing_info = "\n\nTiming breakdown for this scene:\n"
            for timing in context.lyric_timings:
                timing_info += f"  {timing['start_sec']:.3f}-{timing['end_sec']:.3f}s: {timing['text']}\n"
            timing_info += "\nDescribe how the visuals evolve through these timing segments."

        if context.enable_prompt_flow and context.previous_video_prompt:
            user_prompt = f"""Create a video motion prompt:

Previous scene's video prompt: {context.previous_video_prompt}

Current start frame description: {context.start_prompt}
Duration: {context.duration} seconds{timing_info}

Generate a prompt describing camera movement and scene evolution that flows naturally from the previous scene.

IMPORTANT: Do NOT include any quoted text or lyrics. Only describe pure visual elements."""
        elif context.enable_camera_movements:
            user_prompt = f"""Create a video motion prompt:

Start frame description: {context.start_prompt}
Duration: {context.duration} seconds{timing_info}

Generate a prompt describing camera movement and scene evolution for Veo video generation.

IMPORTANT: Do NOT include any quoted text or lyrics. Only describe pure visual elements."""
        else:
            user_prompt = f"""Create a video motion prompt:

Start frame description: {context.start_prompt}
Duration: {context.duration} seconds{timing_info}

Generate a prompt describing subject motion and scene evolution for Veo video generation (minimal camera movement).

IMPORTANT: Do NOT include any quoted text or lyrics. Only describe pure visual elements."""

        try:
            # Call LLM provider using LiteLLM
            import litellm

            # Prepare model string for LiteLLM
            model_id = f"{provider}/{model}" if provider else model

            self.logger.info(f"Generating video prompt with {provider}/{model}")
            self.logger.debug(f"Context: start='{context.start_prompt[:50]}...', camera={context.enable_camera_movements}, flow={context.enable_prompt_flow}")

            response = litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=200
            )

            # Extract response text
            response_text = response.choices[0].message.content.strip()

            self.logger.info(f"Generated video prompt:\n{response_text}")
            return response_text

        except Exception as e:
            self.logger.error(f"LLM generation failed: {e}")
            return self._fallback_prompt(context)

    def _fallback_prompt(self, context: VideoPromptContext) -> str:
        """
        Generate fallback prompt when LLM fails.

        Args:
            context: Context information

        Returns:
            Simple fallback prompt based on start prompt
        """
        if context.enable_camera_movements:
            return f"{context.start_prompt}, slow camera zoom, subtle motion"
        else:
            return f"{context.start_prompt}, gentle subject movement, natural progression"

    def batch_generate_video_prompts(
        self,
        contexts: list[VideoPromptContext],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> list[Optional[str]]:
        """
        Generate multiple video prompts in batch.

        Args:
            contexts: List of context objects
            provider: LLM provider to use (overrides instance default)
            model: Model name (overrides instance default)
            temperature: Temperature for generation

        Returns:
            List of generated prompts (same length as contexts)
        """
        results = []

        for i, context in enumerate(contexts):
            self.logger.info(f"Generating video prompt {i+1}/{len(contexts)}")
            prompt = self.generate_video_prompt(context, provider, model, temperature)
            results.append(prompt)

        return results
