"""
LLM integration for the prompt enhancer module.
Bridges the PromptEnhancer with actual LLM providers.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from core.prompt_enhancer import PromptEnhancer, EnhancementLevel
from gui.llm_utils import LLMResponseParser


class PromptEnhancerLLM:
    """LLM-powered prompt enhancement using GPT-5 methodology"""

    def __init__(self, llm_provider=None):
        """
        Initialize the LLM-powered prompt enhancer.

        Args:
            llm_provider: UnifiedLLMProvider instance or similar LLM client
        """
        self.logger = logging.getLogger(__name__)
        self.llm_provider = llm_provider
        self.enhancer = PromptEnhancer()

    def enhance_with_llm(self,
                        prompt: str,
                        provider: str = "google",
                        model: Optional[str] = None,
                        enhancement_level: EnhancementLevel = EnhancementLevel.MEDIUM,
                        aspect_ratio: Optional[str] = None,
                        style_preset: Optional[str] = None,
                        num_variants: int = 0,
                        temperature: float = 0.7,
                        llm_provider: Optional[str] = None,
                        **kwargs) -> Dict[str, Any]:
        """
        Enhance a prompt using an actual LLM.

        Args:
            prompt: The prompt to enhance
            provider: The target image generation provider (google, openai, stability)
            model: The LLM model to use for enhancement
            enhancement_level: Level of enhancement
            aspect_ratio: Aspect ratio for the image
            style_preset: Style preset to apply
            num_variants: Number of variants to generate
            temperature: LLM temperature parameter
            llm_provider: The LLM provider to use (if different from image provider)
            **kwargs: Additional parameters

        Returns:
            Enhanced prompt data as a dictionary
        """
        if not self.llm_provider:
            self.logger.warning("No LLM provider available, using fallback enhancement")
            return self.enhancer.enhance_prompt(
                prompt, None, provider, enhancement_level,
                aspect_ratio, style_preset, num_variants, **kwargs
            )

        # Map image provider to target models
        provider_map = {
            'google': ['gemini_imagen'],
            'openai': ['openai_dalle3'],
            'stability': ['stability_sdxl'],
            'midjourney': ['midjourney']
        }

        target_models = provider_map.get(provider, ['openai_dalle3', 'gemini_imagen'])

        # Extract max_tokens from kwargs BEFORE passing to build_user_prompt
        # (build_user_prompt doesn't accept max_tokens)
        max_tokens = kwargs.pop('max_tokens', 4000)

        # Build the user prompt
        user_prompt = self.enhancer.build_user_prompt(
            user_prompt=prompt,
            enhancement_level=enhancement_level,
            aspect_ratio=aspect_ratio,
            target_models=target_models,
            style_preset=style_preset,
            num_variants=num_variants,
            **kwargs
        )

        response = None  # Initialize response

        try:
            # Use llm_provider if specified, otherwise use the image provider
            actual_llm_provider = llm_provider or provider

            self.logger.info(f"Enhancing prompt with LLM provider: {actual_llm_provider}, model: {model}")
            self.logger.debug(f"Original prompt: {prompt}")
            self.logger.debug(f"Enhancement level: {enhancement_level}, style: {style_preset}")

            # Check if we're using litellm or need direct API calls
            if hasattr(self.llm_provider, 'litellm') and self.llm_provider.litellm:
                self.logger.info("Using litellm for enhancement")
                # Use litellm for the call
                response = self._call_with_litellm(
                    actual_llm_provider, model, user_prompt, temperature, max_tokens
                )
            elif hasattr(self.llm_provider, 'enhance_prompt'):
                self.logger.info("Using UnifiedLLMProvider.enhance_prompt as fallback")
                # Use the existing enhance_prompt method as a fallback
                enhanced_text = self.llm_provider.enhance_prompt(
                    prompt, provider, model or "default",
                    style="Photorealistic", temperature=temperature
                )
                self.logger.debug(f"enhance_prompt returned: {type(enhanced_text)}: {enhanced_text}")
                # Convert simple text response to structured format
                if enhanced_text:
                    response = self._text_to_structured(enhanced_text, prompt, provider)
                    self.logger.debug(f"Structured response: {response}")
                else:
                    # If enhance_prompt returns None, use fallback
                    self.logger.warning("LLM enhance_prompt returned None, using fallback")
                    return self._create_fallback_response(prompt, provider, enhancement_level)
            else:
                # No suitable method available
                self.logger.warning("LLM provider doesn't support required methods")
                return self._create_fallback_response(prompt, provider, enhancement_level)

            if response is None:
                self.logger.warning("Response is None after processing, using fallback")
                return self._create_fallback_response(prompt, provider, enhancement_level)

            return response

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            return self._create_fallback_response(prompt, provider, enhancement_level)
        except Exception as e:
            self.logger.error(f"Failed to enhance prompt with LLM: {e}")
            return self._create_fallback_response(prompt, provider, enhancement_level)

    def _call_with_litellm(self, provider: str, model: Optional[str],
                          user_prompt: str, temperature: float, max_tokens: int = 4000) -> Dict[str, Any]:
        """
        Call LLM using litellm library.

        Args:
            provider: LLM provider name
            model: Model name
            user_prompt: The formatted user prompt
            temperature: Temperature parameter
            max_tokens: Maximum tokens for response (default 4000)

        Returns:
            Parsed JSON response from LLM
        """
        # Prepare model identifier
        if provider == 'google':
            model_id = model or 'gemini-2.0-flash-exp'
        elif provider == 'openai':
            model_id = model or 'gpt-4o-mini'
        elif provider == 'anthropic':
            model_id = model or 'claude-3-haiku-20240307'
        else:
            model_id = model or 'gpt-4o-mini'

        # Add provider prefix if needed
        provider_prefixes = {
            'google': 'gemini/',
            'anthropic': 'claude-3-haiku-20240307',
        }

        if provider in provider_prefixes and not model_id.startswith(provider_prefixes[provider]):
            if provider == 'google':
                model_id = f"gemini/{model_id}"

        # Determine which token parameter to use
        # Use max_completion_tokens for newer OpenAI models (GPT-4+, GPT-5), max_tokens for GPT-3.5 and other providers
        if provider == "openai":
            if "gpt-3.5" in model_id.lower():
                token_param = "max_tokens"
            else:
                # GPT-4, GPT-5, and newer models use max_completion_tokens
                token_param = "max_completion_tokens"
        else:
            token_param = "max_tokens"

        kwargs = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": self.enhancer.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            token_param: max_tokens
        }

        # Check if LLM logging is enabled
        from core.config import ConfigManager
        config = ConfigManager()
        log_llm = config.get("log_llm_interactions", False)

        # Always log to both file and console for debugging
        import logging
        console = logging.getLogger("console")

        self.logger.info(f"LLM Request to {model_id} (Provider: {provider}):")
        console.info(f"LLM Request to {model_id} (Provider: {provider}):")

        self.logger.info(f"  Token parameter: {token_param} = {kwargs[token_param]}")
        console.info(f"  Token parameter: {token_param} = {kwargs[token_param]}")

        self.logger.info(f"  Temperature: {temperature}")
        console.info(f"  Temperature: {temperature}")

        # Clean up multi-line strings for logging
        clean_system = self.enhancer.SYSTEM_PROMPT.replace('\n', ' ').strip()
        clean_user = user_prompt.replace('\n', ' ').strip()

        self.logger.info(f"  System prompt: {clean_system}")
        console.info(f"  System prompt: {clean_system}")

        self.logger.info(f"  User prompt: {clean_user}")
        console.info(f"  User prompt: {clean_user}")

        # Call litellm
        try:
            response = self.llm_provider.litellm.completion(**kwargs)
        except Exception as e:
            self.logger.error(f"LiteLLM call failed: {e}")
            console.error(f"LiteLLM call failed: {e}")
            raise

        # Always log response for debugging
        if response:
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content if response.choices[0].message else "No content"
                self.logger.info(f"LLM Response received - Length: {len(content)} chars")
                console.info(f"LLM Response received - Length: {len(content)} chars")

                # Log first part of response for debugging
                preview = content[:500] if len(content) > 500 else content
                self.logger.info(f"LLM Response preview: {preview}")
                console.info(f"LLM Response preview: {preview}")

        # Extract and parse response
        if (response and response.choices and len(response.choices) > 0
            and response.choices[0].message
            and response.choices[0].message.content):

            content = response.choices[0].message.content.strip()

            # Use robust parser that handles markdown code fences
            parsed = LLMResponseParser.parse_json_response(content, expected_type=dict)

            if parsed:
                self.logger.debug(f"Successfully parsed JSON response: {type(parsed)}")
                return parsed
            else:
                self.logger.error("Failed to parse JSON from LLM response")
                self.logger.error(f"Content was: {content}")
                raise ValueError("Failed to parse JSON from LLM response")

        else:
            self.logger.error("Empty response from LLM - no choices or content")
            raise ValueError("Empty response from LLM")

    def _text_to_structured(self, enhanced_text: str, original: str, provider: str) -> Dict[str, Any]:
        """
        Convert a simple text enhancement to structured format.

        Args:
            enhanced_text: The enhanced prompt text
            original: The original prompt
            provider: The target provider

        Returns:
            Structured enhancement data
        """
        result = {
            "unified": {
                "prompt": enhanced_text,
                "negative_prompt": None,
                "style_tags": [],
                "aspect_ratio": None,
                "guidance": 7.5,
                "steps": 30,
                "seed": None
            },
            "by_model": {
                "openai_dalle3": None,
                "stability_sdxl": None,
                "midjourney": None,
                "gemini_imagen": None
            },
            "continuity": None,
            "variants": []
        }

        # Set provider-specific prompt
        if provider == 'google':
            result["by_model"]["gemini_imagen"] = enhanced_text
        elif provider == 'openai':
            result["by_model"]["openai_dalle3"] = enhanced_text
        elif provider == 'stability':
            result["by_model"]["stability_sdxl"] = {
                "prompt": enhanced_text,
                "negative_prompt": None,
                "cfg": 7.5,
                "steps": 30,
                "seed": None
            }

        return result

    def _create_fallback_response(self, prompt: str, provider: str,
                                 level: EnhancementLevel) -> Dict[str, Any]:
        """
        Create a fallback response when LLM is unavailable.

        Args:
            prompt: Original prompt
            provider: Target provider
            level: Enhancement level

        Returns:
            Fallback structured response
        """
        # Use the basic enhancer's fallback methods
        return self.enhancer.enhance_prompt(
            prompt, None, provider, level
        )

    def get_enhanced_prompt_for_provider(self, enhanced_data: Optional[Dict], provider: str) -> Optional[str]:
        """
        Extract the appropriate prompt for a specific provider.

        Args:
            enhanced_data: The enhanced prompt data
            provider: The provider name

        Returns:
            The enhanced prompt string
        """
        if not enhanced_data:
            self.logger.warning("get_enhanced_prompt_for_provider: enhanced_data is None or empty")
            return None
        if isinstance(enhanced_data, str):
            # If enhanced_data is already a string, return it
            self.logger.debug(f"get_enhanced_prompt_for_provider: returning string directly: {enhanced_data}")
            return enhanced_data

        result = self.enhancer.get_enhanced_prompt_for_provider(enhanced_data, provider)
        self.logger.debug(f"get_enhanced_prompt_for_provider: returning {type(result)}: {result}")
        return result