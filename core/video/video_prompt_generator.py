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
    tempo_bpm: Optional[float] = None  # Song tempo in BPM for energy/pacing hints


class VideoPromptGenerator:
    """Generate video motion prompts using LLM for Veo video generation"""

    # System prompt for LLM with camera movements
    SYSTEM_PROMPT_WITH_CAMERA = """You are a video motion specialist for Google Veo 3, which generates exactly 8-second clips.

The video prompt should:
- Include EXPLICIT TIME MARKERS for all scenes, especially short ones (e.g., "0-2s:", "2-2.5s:", "2.5-8s:")
- For ultra-brief moments (<0.5s): use "flash", "flicker", "blink", "glimpse"
- For brief moments (0.5-1s): use "quick", "brief", "momentary"
- Add camera movement (pan, zoom, dolly, tilt, etc.)
- Add subtle motion or changes over time
- Match the energy/pacing to the song's tempo (if provided)
- Be optimized for Google Veo 3 8-second generation
- NEVER include quoted text or lyrics (they will render as text in the video)
- AVOID phrases like "same character", "same room", "previous scene" (visual continuity is automatic)

Format for single scene: [Duration/timing], [Scene description], [camera movement], [motion/changes]
Format for batched scenes: Use time segments like "0-2s: action1, 2-4s: action2, 4-8s: action3" """

    # System prompt for LLM without camera movements
    SYSTEM_PROMPT_NO_CAMERA = """You are a video motion specialist for Google Veo 3, which generates exactly 8-second clips.

The video prompt should:
- Include EXPLICIT TIME MARKERS for all scenes, especially short ones (e.g., "0-2s:", "2-2.5s:", "2.5-8s:")
- For ultra-brief moments (<0.5s): use "flash", "flicker", "blink", "glimpse"
- For brief moments (0.5-1s): use "quick", "brief", "momentary"
- Focus on subject/character actions and environmental motion
- Keep camera mostly static (minimal camera movement only when essential)
- Add subtle motion or changes over time
- Match the energy/pacing to the song's tempo (if provided)
- Be optimized for Google Veo 3 8-second generation
- NEVER include quoted text or lyrics (they will render as text in the video)
- AVOID phrases like "same character", "same room", "previous scene" (visual continuity is automatic)

Format for single scene: [Duration/timing], [Scene description], [subject motion], [temporal progression]
Format for batched scenes: Use time segments like "0-2s: action1, 2-4s: action2, 4-8s: action3" """

    # System prompt for prompt flow (text continuity between scenes)
    SYSTEM_PROMPT_WITH_FLOW = """You are a video motion specialist for Google Veo 3, which generates exactly 8-second clips.

The video prompt should:
- Include EXPLICIT TIME MARKERS for all scenes, especially short ones (e.g., "0-2s:", "2-2.5s:", "2.5-8s:")
- For ultra-brief moments (<0.5s): use "flash", "flicker", "blink", "glimpse"
- For brief moments (0.5-1s): use "quick", "brief", "momentary"
- Continue the motion/energy from the previous scene smoothly
- Maintain visual and temporal continuity through motion progression
- Add camera movement (pan, zoom, dolly, tilt, etc.)
- Add subtle motion or changes over time
- Match the energy/pacing to the song's tempo (if provided)
- Be optimized for Google Veo 3 8-second generation
- NEVER include quoted text or lyrics (they will render as text in the video)
- AVOID redundant phrases like "same character", "same room" (visual continuity is handled by reference images)

Format for single scene: [Duration/timing], [Scene description with flowing motion], [camera movement], [motion/changes]
Format for batched scenes: Use time segments like "0-2s: action1, 2-2.5s: brief moment, 2.5-8s: action3" """

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

        # Detect instrumental sections
        is_instrumental = context.start_prompt.strip().lower() in ['[instrumental]', 'instrumental', '[instrumental section]']

        # Build user prompt based on context - ALWAYS include duration info
        # Format duration string based on length
        if context.duration < 1.0:
            duration_str = f"{context.duration:.1f} seconds (ultra-brief moment)"
        elif context.duration < 2.0:
            duration_str = f"{context.duration:.1f} seconds (quick moment)"
        else:
            duration_str = f"{context.duration:.1f} seconds"

        timing_info = ""
        if context.lyric_timings and len(context.lyric_timings) > 1:
            timing_info = "\n\nTiming breakdown for this scene (within 8-second Veo clip):\n"
            for timing in context.lyric_timings:
                # Add descriptors for very short segments
                duration_sec = timing['end_sec'] - timing['start_sec']
                if duration_sec < 0.5:
                    duration_desc = " [ultra-brief flash]"
                elif duration_sec < 1.0:
                    duration_desc = " [brief moment]"
                else:
                    duration_desc = ""
                timing_info += f"  {timing['start_sec']:.1f}-{timing['end_sec']:.1f}s: {timing['text']}{duration_desc}\n"
            timing_info += "\nDescribe how the visuals evolve through these timing segments."

        # Add tempo guidance if available
        tempo_guidance = ""
        if context.tempo_bpm:
            if context.tempo_bpm >= 140:
                tempo_guidance = f"\nTempo: {context.tempo_bpm:.0f} BPM (Fast/Energetic - use quick camera movements, dynamic action, energetic pacing)"
            elif context.tempo_bpm >= 100:
                tempo_guidance = f"\nTempo: {context.tempo_bpm:.0f} BPM (Medium - balanced pacing and energy)"
            elif context.tempo_bpm >= 80:
                tempo_guidance = f"\nTempo: {context.tempo_bpm:.0f} BPM (Moderate - smooth movements, contemplative pacing)"
            else:
                tempo_guidance = f"\nTempo: {context.tempo_bpm:.0f} BPM (Slow/Ballad - gentle movements, emotional depth)"

        if is_instrumental:
            # Special prompt for instrumental sections
            motion_desc = "camera movement and scene evolution" if context.enable_camera_movements else "subject motion and temporal progression"
            user_prompt = f"""Create a video motion prompt for an INSTRUMENTAL section (music break with no lyrics):

Duration: {duration_str}{tempo_guidance}
Note: This will be part of an 8-second Veo generation

Generate a prompt with {motion_desc} that:
• Maintains visual continuity with surrounding scenes
• Uses establishing shots, ambient details, or atmospheric moments
• Provides visual breathing room and variety
• Examples: camera pans across setting, environmental details, character reactions, scenic transitions
• For short durations (<1s), describe as brief flashes or quick moments

IMPORTANT: Do NOT include any quoted text or lyrics. Only describe pure visual elements."""
        elif context.enable_prompt_flow and context.previous_video_prompt:
            user_prompt = f"""Create a video motion prompt:

Previous scene's video prompt: {context.previous_video_prompt}

Current start frame description: {context.start_prompt}
Duration: {duration_str}{tempo_guidance}{timing_info}
Note: This will be part of an 8-second Veo generation

Generate a prompt describing camera movement and scene evolution that flows naturally from the previous scene.

IMPORTANT:
- If timing breakdown is provided, use explicit time markers (e.g., "0-2.5s: ..., 2.5-5s: ...") to describe visual evolution
- For ultra-brief moments (<0.5s), use terms like "flash", "blink", "flicker"
- Do NOT include any quoted text or lyrics. Only describe pure visual elements."""
        elif context.enable_camera_movements:
            user_prompt = f"""Create a video motion prompt:

Start frame description: {context.start_prompt}
Duration: {duration_str}{tempo_guidance}{timing_info}
Note: This will be part of an 8-second Veo generation

Generate a prompt describing camera movement and scene evolution for Veo video generation.

IMPORTANT:
- If timing breakdown is provided, use explicit time markers (e.g., "0-2.5s: ..., 2.5-5s: ...") to describe visual evolution
- For ultra-brief moments (<0.5s), use terms like "flash", "blink", "flicker"
- Do NOT include any quoted text or lyrics. Only describe pure visual elements."""
        else:
            user_prompt = f"""Create a video motion prompt:

Start frame description: {context.start_prompt}
Duration: {duration_str}{tempo_guidance}{timing_info}
Note: This will be part of an 8-second Veo generation

Generate a prompt describing subject motion and scene evolution for Veo video generation (minimal camera movement).

IMPORTANT:
- If timing breakdown is provided, use explicit time markers (e.g., "0-2.5s: ..., 2.5-5s: ...") to describe visual evolution
- For ultra-brief moments (<0.5s), use terms like "flash", "blink", "flicker"
- Do NOT include any quoted text or lyrics. Only describe pure visual elements."""

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
        Generate multiple video prompts in ONE API call (true batching).

        Args:
            contexts: List of context objects
            provider: LLM provider to use (overrides instance default)
            model: Model name (overrides instance default)
            temperature: Temperature for generation

        Returns:
            List of generated prompts (same length as contexts)
        """
        if not contexts:
            return []

        # Use provided or instance defaults
        provider = provider or self.llm_provider
        model = model or self.llm_model

        if not provider or not model:
            self.logger.error("LLM provider and model must be specified")
            return [self._fallback_prompt(ctx) for ctx in contexts]

        # Check if any context requires prompt flow - if so, must generate sequentially
        has_flow = any(ctx.enable_prompt_flow and ctx.previous_video_prompt for ctx in contexts)
        if has_flow:
            self.logger.info("Prompt flow enabled - generating sequentially")
            results = []
            for i, context in enumerate(contexts):
                self.logger.info(f"Generating video prompt {i+1}/{len(contexts)} (sequential for flow)")
                prompt = self.generate_video_prompt(context, provider, model, temperature)
                results.append(prompt)
            return results

        # TRUE BATCHING: Single API call for all prompts
        self.logger.info(f"🚀 TRUE BATCH: Generating {len(contexts)} video prompts in ONE API call")

        # Select system prompt based on first context (assume all similar settings)
        first_ctx = contexts[0]
        if first_ctx.enable_camera_movements:
            system_prompt = self.SYSTEM_PROMPT_WITH_CAMERA
            motion_type = "camera movement and scene evolution"
        else:
            system_prompt = self.SYSTEM_PROMPT_NO_CAMERA
            motion_type = "subject motion and scene evolution"

        # Build batch user prompt
        batch_prompt = f"""Generate video motion prompts for {len(contexts)} scenes.

For each scene, add {motion_type} to the static image description.
Return EXACTLY {len(contexts)} numbered prompts (1., 2., 3., etc.) with NO headers or preamble.

Scenes:\n\n"""

        for i, ctx in enumerate(contexts, 1):
            # Detect instrumental sections
            is_instrumental = ctx.start_prompt.strip().lower() in ['[instrumental]', 'instrumental', '[instrumental section]']

            # Add tempo guidance if available
            tempo_hint = ""
            if ctx.tempo_bpm:
                if ctx.tempo_bpm >= 140:
                    tempo_hint = f" [{ctx.tempo_bpm:.0f} BPM - Fast/Energetic]"
                elif ctx.tempo_bpm >= 100:
                    tempo_hint = f" [{ctx.tempo_bpm:.0f} BPM - Medium]"
                elif ctx.tempo_bpm >= 80:
                    tempo_hint = f" [{ctx.tempo_bpm:.0f} BPM - Moderate]"
                else:
                    tempo_hint = f" [{ctx.tempo_bpm:.0f} BPM - Slow/Ballad]"

            # Format duration with descriptors for very short scenes
            if ctx.duration < 0.5:
                duration_desc = f"{ctx.duration:.1f}s (ultra-brief flash)"
            elif ctx.duration < 1.0:
                duration_desc = f"{ctx.duration:.1f}s (brief moment)"
            elif ctx.duration < 2.0:
                duration_desc = f"{ctx.duration:.1f}s (quick moment)"
            else:
                duration_desc = f"{ctx.duration:.1f}s"

            if is_instrumental:
                # Special handling for instrumental sections
                batch_prompt += f"{i}. TYPE: INSTRUMENTAL SECTION\n"
                batch_prompt += f"   Duration: {duration_desc}{tempo_hint}\n"
                batch_prompt += f"   Part of 8-second Veo generation\n"
                batch_prompt += f"   INSTRUCTIONS: Create a video prompt with {motion_type} that:\n"
                batch_prompt += f"     • Maintains visual continuity with surrounding scenes\n"
                batch_prompt += f"     • Uses establishing shots, ambient details, or atmospheric moments\n"
                batch_prompt += f"     • Provides visual breathing room and variety\n"
                batch_prompt += f"     • Examples: camera pans across setting, environmental details, character reactions\n"
            else:
                # Regular scene
                batch_prompt += f"{i}. Start frame: {ctx.start_prompt}\n"
                batch_prompt += f"   Duration: {duration_desc}{tempo_hint}\n"
                batch_prompt += f"   Part of 8-second Veo generation\n"

                # Add timing breakdown for batched scenes WITH lyric context
                if ctx.lyric_timings and len(ctx.lyric_timings) > 1:
                    batch_prompt += f"   Timing breakdown (within 8-second clip):\n"
                    for t in ctx.lyric_timings:
                        # Include lyric text so LLM knows what's happening at each timestamp
                        lyric_text = t.get('text', '')
                        segment_duration = t['end_sec'] - t['start_sec']
                        if segment_duration < 0.5:
                            seg_desc = " [ultra-brief]"
                        elif segment_duration < 1.0:
                            seg_desc = " [brief]"
                        else:
                            seg_desc = ""
                        batch_prompt += f"     • {t['start_sec']:.1f}-{t['end_sec']:.1f}s: \"{lyric_text}\"{seg_desc}\n"

            batch_prompt += "\n"

        batch_prompt += f"""Return {len(contexts)} numbered video prompts.

For scenes with timing breakdowns: Use explicit time markers (e.g., "0-2.5s: ..., 2.5-5s: ..., 5-8s: ...") to describe visual evolution at those exact timestamps.
For single-shot scenes: Describe 2-3 sentences of motion and camera work.

IMPORTANT:
- Include time markers when timing breakdown is provided
- Describe smooth transitions between time segments
- ONE continuous shot per scene (no cuts)
- NEVER include quoted text or lyrics in prompts"""

        try:
            import litellm

            model_id = f"{provider}/{model}" if provider else model

            self.logger.info(f"Batch generating {len(contexts)} video prompts with {provider}/{model}")

            response = litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": batch_prompt}
                ],
                temperature=temperature,
                max_tokens=200 * len(contexts)  # ~200 tokens per video prompt
            )

            # Parse numbered response
            response_text = response.choices[0].message.content.strip()

            # Split by numbered markers (1., 2., etc.)
            import re
            parts = re.split(r'\n(?=\d+\.)', response_text)
            results = []

            for part in parts:
                # Remove number prefix and clean up
                cleaned = re.sub(r'^\d+\.\s*', '', part).strip()
                if cleaned:
                    results.append(cleaned)

            # Ensure we have the right number of results
            while len(results) < len(contexts):
                missing_idx = len(results)
                self.logger.warning(f"Missing video result {missing_idx + 1}, using fallback")
                results.append(self._fallback_prompt(contexts[missing_idx]))

            self.logger.info(f"✅ Batch generated {len(results)} video prompts in ONE API call")
            return results[:len(contexts)]

        except Exception as e:
            self.logger.error(f"Batch video generation failed: {e}")
            # Fallback to individual generation
            self.logger.info("Falling back to individual generation")
            results = []
            for i, context in enumerate(contexts):
                self.logger.info(f"Generating video prompt {i+1}/{len(contexts)} (fallback)")
                prompt = self.generate_video_prompt(context, provider, model, temperature)
                results.append(prompt)
            return results
