"""
End prompt generator using LLM for Veo 3.1 transitions.

This module provides LLM-based generation of end frame descriptions
that create smooth transitions between video scenes.
"""

import logging
from typing import Optional
from dataclasses import dataclass


@dataclass
class EndPromptContext:
    """Context information for end prompt generation"""
    start_prompt: str
    next_start_prompt: Optional[str] = None
    duration: float = 6.0
    style: str = "cinematic"


class EndPromptGenerator:
    """Generate end frame prompts using LLM for smooth video transitions"""

    # System prompt for LLM
    SYSTEM_PROMPT = """You are a video transition specialist. Generate a description for the END FRAME of a video that starts with the given prompt.

The end frame should naturally transition toward the next scene if provided.

Describe what the final frame should look like - focus on the visual elements, not camera movement. The Veo API will handle the transition animation.

Format: 1-2 sentences describing the end state."""

    def __init__(self, llm_provider=None):
        """
        Initialize end prompt generator.

        Args:
            llm_provider: UnifiedLLMProvider instance (optional, will create if not provided)
        """
        self.logger = logging.getLogger(__name__)
        self.llm_provider = llm_provider

    def is_available(self) -> bool:
        """Check if LLM provider is available"""
        if not self.llm_provider:
            return False
        return self.llm_provider.is_available()

    def generate_end_prompt(
        self,
        context: EndPromptContext,
        provider: str = "gemini",
        model: str = "gemini-2.0-flash-exp",
        temperature: float = 0.8
    ) -> Optional[str]:
        """
        Generate end frame description using LLM.

        Args:
            context: Context information for generation
            provider: LLM provider to use
            model: Model name
            temperature: Temperature for generation (0.0-1.0)

        Returns:
            Generated end frame description, or None if generation fails
        """
        if not self.is_available():
            self.logger.error("LLM provider not available")
            return self._fallback_prompt(context)

        # Build user prompt based on context
        if context.next_start_prompt:
            user_prompt = f"""Create an end frame description:

Starting frame: "{context.start_prompt}"
Next scene starts with: "{context.next_start_prompt}"
Duration: {context.duration} seconds

Describe the ending frame that bridges these scenes."""
        else:
            user_prompt = f"""Create an end frame description:

Starting frame: "{context.start_prompt}"
Duration: {context.duration} seconds

Describe a natural ending frame for this scene."""

        try:
            # Call LLM provider
            import litellm

            # Prepare model string
            if provider == 'gemini':
                model_id = f"gemini/{model}"
            elif provider == 'openai':
                model_id = model
            elif provider == 'anthropic' or provider == 'claude':
                model_id = model
            else:
                model_id = model

            self.logger.info(f"Generating end prompt with {provider}/{model}")
            self.logger.debug(f"Context: start='{context.start_prompt[:50]}...', next='{context.next_start_prompt[:50] if context.next_start_prompt else 'None'}...'")

            response = litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=150
            )

            # Extract response text
            response_text = response.choices[0].message.content.strip()

            self.logger.info(f"Generated end prompt: {response_text[:100]}...")
            return response_text

        except Exception as e:
            self.logger.error(f"LLM generation failed: {e}")
            return self._fallback_prompt(context)

    def _fallback_prompt(self, context: EndPromptContext) -> str:
        """
        Generate fallback prompt when LLM fails.

        Args:
            context: Context information

        Returns:
            Simple fallback prompt
        """
        if context.next_start_prompt:
            return f"transitioning from {context.start_prompt} toward {context.next_start_prompt}"
        else:
            return f"{context.start_prompt} with natural conclusion"

    def batch_generate_end_prompts(
        self,
        contexts: list[EndPromptContext],
        provider: str = "gemini",
        model: str = "gemini-2.0-flash-exp",
        temperature: float = 0.8
    ) -> list[Optional[str]]:
        """
        Generate multiple end prompts in batch (for efficiency).

        Args:
            contexts: List of context objects
            provider: LLM provider to use
            model: Model name
            temperature: Temperature for generation

        Returns:
            List of generated prompts (same length as contexts)
        """
        results = []

        for i, context in enumerate(contexts):
            self.logger.info(f"Generating end prompt {i+1}/{len(contexts)}")
            prompt = self.generate_end_prompt(context, provider, model, temperature)
            results.append(prompt)

        return results
