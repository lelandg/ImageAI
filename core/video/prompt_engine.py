"""
Prompt generation and enhancement engine for video projects.
Uses LLMs to transform simple text into cinematic image prompts.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from jinja2 import Template, Environment, FileSystemLoader

from .project import Scene
from core.llm_models import get_provider_models, get_provider_prefix


class PromptStyle(Enum):
    """Available prompt enhancement styles"""
    CINEMATIC = "cinematic"
    ARTISTIC = "artistic"
    PHOTOREALISTIC = "photorealistic"
    ANIMATED = "animated"
    DOCUMENTARY = "documentary"
    ABSTRACT = "abstract"
    NOIR = "noir"
    FANTASY = "fantasy"
    SCIFI = "scifi"
    VINTAGE = "vintage"
    MINIMALIST = "minimalist"
    DRAMATIC = "dramatic"


@dataclass
class PromptTemplate:
    """A prompt template configuration"""
    name: str
    template_path: Optional[Path] = None
    template_string: Optional[str] = None
    variables: Dict[str, Any] = None
    
    def render(self, **kwargs) -> str:
        """Render the template with given variables"""
        if self.template_string:
            template = Template(self.template_string)
        elif self.template_path and self.template_path.exists():
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template = Template(f.read())
        else:
            raise ValueError(f"No valid template found for {self.name}")
        
        # Merge default variables with provided kwargs
        context = self.variables.copy() if self.variables else {}
        context.update(kwargs)
        
        return template.render(**context)


class UnifiedLLMProvider:
    """
    Unified interface for all LLM providers using LiteLLM.
    Supports OpenAI, Anthropic, Google Gemini, Ollama, and LM Studio.

    Note: Provider/model lists now centralized in core.llm_models
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the unified LLM provider.
        
        Args:
            config: Configuration dictionary with API keys and endpoints
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Try to import litellm
        try:
            import litellm
            import os
            self.litellm = litellm
            self.litellm.drop_params = True  # Drop unsupported params
            # Use environment variable instead of deprecated set_verbose
            os.environ['LITELLM_LOG'] = 'ERROR'  # Only show errors, not verbose info
        except ImportError:
            self.logger.warning("LiteLLM not installed. Install with: pip install litellm")
            self.litellm = None
        
        # Set up API keys and endpoints
        self._setup_providers()
    
    def _setup_providers(self):
        """Set up API keys and endpoints for each provider"""
        if not self.litellm:
            return

        import os

        # Log what API keys are available
        self.logger.debug(f"Setting up LLM providers with config keys: {list(self.config.keys())}")

        # OpenAI
        if 'openai_api_key' in self.config and self.config['openai_api_key']:
            os.environ['OPENAI_API_KEY'] = self.config['openai_api_key']
            self.logger.info("OpenAI API key configured")
        else:
            self.logger.debug("No OpenAI API key available")

        # Anthropic
        if 'anthropic_api_key' in self.config and self.config['anthropic_api_key']:
            os.environ['ANTHROPIC_API_KEY'] = self.config['anthropic_api_key']
            self.logger.info("Anthropic API key configured")
        else:
            self.logger.debug("No Anthropic API key available")

        # Google Gemini
        if 'google_api_key' in self.config and self.config['google_api_key']:
            os.environ['GEMINI_API_KEY'] = self.config['google_api_key']
            self.logger.info("Google Gemini API key configured")
        else:
            self.logger.debug("No Google API key available")
        
        # Ollama endpoint
        if 'ollama_endpoint' in self.config and self.config['ollama_endpoint']:
            os.environ['OLLAMA_API_BASE'] = self.config['ollama_endpoint']
        else:
            os.environ['OLLAMA_API_BASE'] = 'http://localhost:11434'

        # LM Studio endpoint (OpenAI-compatible)
        if 'lmstudio_endpoint' in self.config and self.config['lmstudio_endpoint']:
            self.lmstudio_base = self.config['lmstudio_endpoint']
        else:
            self.lmstudio_base = 'http://localhost:1234/v1'
    
    def is_available(self) -> bool:
        """Check if LiteLLM is available"""
        return self.litellm is not None
    
    def list_models(self, provider: str) -> List[str]:
        """
        List available models for a provider.

        Args:
            provider: Provider name

        Returns:
            List of model names
        """
        return get_provider_models(provider)

    def _strip_markdown_headers(self, text: str) -> str:
        """
        Strip markdown headers and formatting from LLM responses.
        Removes lines starting with # and removes ** bold markers and * bullet points.
        """
        import re

        # Remove lines that start with # (markdown headers)
        lines = text.split('\n')
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip lines that are just markdown headers (e.g., "# Cinematic visual prompt")
            # Also skip lines that are just bullet points with no substantial content
            if not stripped.startswith('#') and not (stripped.startswith('* ') and len(stripped) < 5):
                filtered_lines.append(line)

        result = '\n'.join(filtered_lines).strip()

        # Remove ** bold markers (e.g., "**Visual Scene Description:**")
        result = re.sub(r'\*\*([^*]+)\*\*:?\s*', '', result)

        # Remove standalone * bullet points at start of lines
        result = re.sub(r'^\*\s+', '', result, flags=re.MULTILINE)

        # Remove any remaining asterisks that aren't part of text (isolated *)
        result = re.sub(r'(?<!\w)\*(?!\w)', '', result)

        return result.strip()

    def _create_smart_fallback(self, text: str, style: PromptStyle) -> str:
        """
        Create a context-aware fallback prompt when LLM fails.
        Analyzes the text to detect scene type and generates appropriate visual description.
        """
        text_lower = text.lower()

        # Detect scene type from keywords
        action_keywords = ['run', 'jump', 'fight', 'dance', 'walk', 'fly', 'swim', 'chase', 'move', 'swing']
        emotion_keywords = ['love', 'sad', 'happy', 'angry', 'fear', 'joy', 'cry', 'smile', 'laugh', 'weep']
        setting_keywords = ['night', 'day', 'morning', 'evening', 'sunset', 'sunrise', 'dark', 'light', 'city', 'forest']
        nature_keywords = ['rain', 'snow', 'wind', 'storm', 'cloud', 'sun', 'moon', 'star', 'ocean', 'mountain']

        is_action = any(kw in text_lower for kw in action_keywords)
        is_emotion = any(kw in text_lower for kw in emotion_keywords)
        is_setting = any(kw in text_lower for kw in setting_keywords)
        is_nature = any(kw in text_lower for kw in nature_keywords)

        # Style-specific prefixes
        style_prefixes = {
            PromptStyle.CINEMATIC: "Cinematic wide shot of",
            PromptStyle.ARTISTIC: "Artistic interpretation showing",
            PromptStyle.PHOTOREALISTIC: "Photorealistic scene depicting",
            PromptStyle.ANIMATED: "Vibrant animated scene with",
            PromptStyle.DOCUMENTARY: "Candid documentary-style image of",
            PromptStyle.ABSTRACT: "Abstract visual representation of",
            PromptStyle.NOIR: "Film noir scene with",
            PromptStyle.FANTASY: "Epic fantasy scene showing",
            PromptStyle.SCIFI: "Futuristic sci-fi scene featuring",
            PromptStyle.VINTAGE: "Vintage photograph of",
            PromptStyle.MINIMALIST: "Minimalist composition with",
            PromptStyle.DRAMATIC: "Dramatic scene depicting"
        }

        # Build context-aware description
        prefix = style_prefixes.get(style, "Cinematic scene showing")

        if is_action:
            return f"{prefix} {text}. Dynamic movement, motion blur, energetic composition. Professional photography, dramatic lighting, high detail."
        elif is_emotion:
            return f"{prefix} {text}. Expressive faces, emotional depth, intimate framing. Soft lighting, shallow depth of field, evocative mood."
        elif is_setting:
            return f"{prefix} {text}. Atmospheric environment, rich ambiance, detailed background. Environmental storytelling, cinematic lighting."
        elif is_nature:
            return f"{prefix} {text}. Natural beauty, organic textures, environmental drama. Golden hour lighting, epic scale, breathtaking vista."
        else:
            return f"{prefix} {text}. Dramatic lighting, professional photography, high detail, cinematic composition."

    def enhance_prompt(self,
                      text: str,
                      provider: str,
                      model: str,
                      style: PromptStyle = PromptStyle.CINEMATIC,
                      temperature: float = 0.7,
                      max_tokens: int = 500,
                      console_callback=None) -> str:
        """
        Enhance a text prompt using an LLM.

        Args:
            text: Original text to enhance
            provider: LLM provider (openai, anthropic, gemini, etc.)
            model: Model name
            style: Style of enhancement
            temperature: Creativity parameter (0-1)
            max_tokens: Maximum tokens in response
            console_callback: Optional callback function(message, level) for console logging

        Returns:
            Enhanced prompt text
        """
        if not self.is_available():
            self.logger.warning("LiteLLM not available, returning original text")
            return text

        # Check if LLM logging is enabled
        from core.config import ConfigManager
        config = ConfigManager()
        log_llm = config.get("log_llm_interactions", False)
        
        # Build system prompt based on style
        system_prompt = self._get_system_prompt(style)
        
        # Check if this looks like a lyric line (short, no visual descriptions)
        is_lyric = len(text.split()) < 15 and not any(word in text.lower() for word in 
                   ['shot', 'camera', 'lighting', 'scene', 'image', 'visual', 'color'])
        
        # Adjust user prompt based on whether it's a lyric
        if is_lyric:
            user_prompt = f"""Create a detailed visual scene description that represents the themes and emotions from this text: {text}

Describe what we should see in the image. Include specific details about:
- The main subject or action
- The setting and environment
- Lighting and mood
- Visual style and composition

IMPORTANT: Do NOT include any quoted text in your response. Only provide pure visual descriptions without any text overlays.

Be highly descriptive and detailed. Aim for 75-150 words."""
        else:
            user_prompt = f"Transform this into an image generation prompt: {text}"
        
        # Prepare model identifier for LiteLLM
        if provider == 'lmstudio':
            # LM Studio uses OpenAI-compatible API
            model_id = model
            api_base = self.lmstudio_base
        else:
            # Use provider prefix if needed
            prefix = get_provider_prefix(provider)
            model_id = f"{prefix}{model}" if prefix else model
            api_base = None
        
        try:
            # Build kwargs for litellm
            kwargs = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # Add api_base for LM Studio
            if api_base:
                kwargs["api_base"] = api_base

            # Log LLM request if enabled
            if log_llm:
                self.logger.info(f"=== LLM Request to {provider}/{model_id} ===")
                self.logger.info(f"System: {system_prompt}")
                self.logger.info(f"User: {user_prompt}")
                self.logger.info(f"Temperature: {temperature}, Max tokens: {max_tokens}")

            # Also log to console if callback provided
            if console_callback:
                console_callback(f"=== LLM Request to {provider}/{model_id} ===", "INFO")
                console_callback(f"System: {system_prompt[:200]}..." if len(system_prompt) > 200 else f"System: {system_prompt}", "INFO")
                console_callback(f"User: {user_prompt}", "INFO")

            # Call LiteLLM
            response = self.litellm.completion(**kwargs)

            # Log LLM response if enabled
            if log_llm:
                if response and response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content if response.choices[0].message else "No content"
                    self.logger.info(f"=== LLM Response from {provider}/{model_id} ===")
                    self.logger.info(f"Response: {content}")
                else:
                    self.logger.info(f"=== LLM Response from {provider}/{model_id} ===")
                    self.logger.info("Response: Empty or no choices")

            # Also log to console if callback provided
            if console_callback:
                if response and response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content if response.choices[0].message else "No content"
                    console_callback(f"=== LLM Response from {provider}/{model_id} ===", "SUCCESS")
                    console_callback(f"Response: {content}", "INFO")
                else:
                    console_callback(f"=== LLM Response from {provider}/{model_id} ===", "WARNING")
                    console_callback("Response: Empty or no choices", "WARNING")
            
            # Check if response has content
            if (response and response.choices and len(response.choices) > 0
                and response.choices[0].message
                and response.choices[0].message.content):
                enhanced = response.choices[0].message.content.strip()

                # Strip markdown headers and formatting
                enhanced = self._strip_markdown_headers(enhanced)

                # If we still got an empty or very short response for a lyric, create a basic visual
                if is_lyric and len(enhanced) < 20:
                    self.logger.warning(f"Got minimal response for lyric, creating basic visual")
                    enhanced = f"A cinematic scene visualizing: {text}. Dramatic lighting, professional photography, high detail."

                self.logger.info(f"Enhanced prompt using {provider}/{model}")
                return enhanced
            else:
                self.logger.warning(f"Empty response from {provider}/{model}, creating fallback")
                # For lyrics, use smart fallback
                if is_lyric:
                    return self._create_smart_fallback(text, style)
                return text
            
        except Exception as e:
            self.logger.error(f"Failed to enhance prompt with {provider}/{model}: {e}")
            # Use smart fallback for lyrics
            if is_lyric:
                return self._create_smart_fallback(text, style)
            return text
    
    def batch_enhance(self,
                     texts: List[str],
                     provider: str,
                     model: str,
                     style: PromptStyle = PromptStyle.CINEMATIC,
                     temperature: float = 0.7) -> List[str]:
        """
        Enhance multiple prompts in batch.

        Args:
            texts: List of texts to enhance
            provider: LLM provider
            model: Model name
            style: Style of enhancement
            temperature: Creativity parameter

        Returns:
            List of enhanced prompts
        """
        if not self.is_available():
            return texts

        # Anthropic has issues with large batches - split into smaller chunks
        if provider.lower() == 'anthropic' and len(texts) > 5:
            self.logger.info(f"Splitting {len(texts)} texts into batches of 5 for Anthropic")
            all_enhanced = []
            batch_size = 5

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                self.logger.info(f"Processing Anthropic batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size} ({len(batch)} items)")
                enhanced_batch = self._batch_enhance_single(batch, provider, model, style, temperature)
                all_enhanced.extend(enhanced_batch)

            return all_enhanced

        # For other providers or small batches, process in one call
        return self._batch_enhance_single(texts, provider, model, style, temperature)

    def _parse_batch_response(self, response: str, expected_count: int) -> list:
        """Parse numbered responses from LLM, handling various formats."""
        import re

        # Split by numbered markers
        parts = re.split(r'\n(?=\*{0,2}\d+\.)', response)
        results = []

        # Common header/preamble phrases to skip
        skip_phrases = [
            'here are', "i'd be happy", 'i appreciate', "instead,",
            'option 1', 'option 2', 'option 3',
            'cinematic visual scene', 'visual scene description',
            'image generation prompt', 'scene description',
            'music video', 'enhanced prompt'
        ]

        # Minimum viable prompt length
        MIN_PROMPT_LENGTH = 80

        for part in parts:
            # Remove number prefix and markdown
            cleaned = re.sub(r'^\*{0,2}\d+[\.\)]\s*\*{0,2}', '', part)
            cleaned = re.sub(r'^#+\s*', '', cleaned)
            cleaned = re.sub(r'^\*\*.*?\*\*\s*', '', cleaned)
            cleaned = cleaned.strip()

            # Skip empty or too-short results
            if not cleaned or len(cleaned) < MIN_PROMPT_LENGTH:
                continue

            # Skip preambles and headers
            cleaned_lower = cleaned.lower()
            if any(phrase in cleaned_lower for phrase in skip_phrases):
                # Double-check: if it's long and contains visual keywords, keep it
                visual_keywords = ['camera', 'shot', 'lighting', 'lens', 'frame', 'depth']
                if len(cleaned) > 150 and any(kw in cleaned_lower for kw in visual_keywords):
                    results.append(cleaned)
                continue

            results.append(cleaned)

        # Log parsing results
        if len(results) != expected_count:
            self.logger.warning(
                f"Expected {expected_count} results, got {len(results)}. "
                f"Will pad with smart fallbacks."
            )

        return results

    def _batch_enhance_single(self,
                              texts: List[str],
                              provider: str,
                              model: str,
                              style: PromptStyle,
                              temperature: float) -> List[str]:
        """
        Enhance a single batch of prompts (internal method).
        """
        # For efficiency, try to batch in a single call if provider supports it
        system_prompt = self._get_system_prompt(style)

        # Check if these look like lyrics
        avg_words = sum(len(text.split()) for text in texts) / len(texts) if texts else 0
        likely_lyrics = avg_words < 15

        # Create a batch prompt with strict formatting for Anthropic
        if provider.lower() == 'anthropic':
            batch_prompt = (
                f"Transform these {len(texts)} texts into {style.value} image generation prompts.\n\n"
                f"CRITICAL FORMATTING RULES:\n"
                f"- Return EXACTLY {len(texts)} prompts\n"
                f"- Number them 1-{len(texts)}\n"
                f"- NO headers, titles, or section markers\n"
                f"- NO introductory text or explanations\n"
                f"- Start immediately with: 1. [prompt]\n"
                f"- Each prompt must be at least 100 characters\n\n"
                f"Texts to transform:\n\n"
            )
            for i, text in enumerate(texts, 1):
                batch_prompt += f"{i}. {text}\n"

            batch_prompt += (
                f"\n\nNow return {len(texts)} numbered prompts ONLY. "
                f"No headers, no explanations, just numbered visual descriptions."
            )
        else:
            # Create a batch prompt for other providers
            if likely_lyrics:
                batch_prompt = """Create detailed visual scene descriptions that represent the themes and emotions from each text below.
For each text, describe what we should see in the image.
Include specific details about the main subject, setting, lighting, and visual style.

IMPORTANT: Do NOT include any quoted text or lyrics in your responses. Only provide pure visual descriptions without any text overlays.

Return one enhanced visual description per line, numbered:

"""
            else:
                batch_prompt = "Transform each of these lines into cinematic image generation prompts. Return one enhanced prompt per line:\n\n"

            for i, text in enumerate(texts, 1):
                batch_prompt += f"{i}. {text}\n"
        
        try:
            # Prepare model identifier
            if provider == 'lmstudio':
                model_id = model
                api_base = self.lmstudio_base
            else:
                prefix = get_provider_prefix(provider)
                model_id = f"{prefix}{model}" if prefix else model
                api_base = None
            
            # Adjust max_tokens based on provider and batch size
            if provider.lower() == 'anthropic':
                # Increase token allocation for Anthropic (was too conservative)
                max_tokens = min(150 * len(texts), 4000)
            else:
                max_tokens = 150 * len(texts)

            kwargs = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": batch_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": 120  # 2 minute timeout to prevent hanging
            }

            if api_base:
                kwargs["api_base"] = api_base

            self.logger.debug(f"Batch enhancing {len(texts)} texts with max_tokens={max_tokens}")
            response = self.litellm.completion(**kwargs)

            # Parse the response
            enhanced_text = response.choices[0].message.content.strip()

            # Use the new enhanced parser
            results = self._parse_batch_response(enhanced_text, len(texts))

            # Ensure we have the right number of results with smart fallbacks
            while len(results) < len(texts):
                missing_idx = len(results)
                self.logger.warning(f"Missing result {missing_idx + 1}, using smart fallback")
                # Use smart fallback instead of original text
                fallback = self._create_smart_fallback(texts[missing_idx], style)
                results.append(fallback)

            return results[:len(texts)]
            
        except Exception as e:
            self.logger.error(f"Batch enhancement failed: {e}")
            # Fall back to individual enhancement
            return [self.enhance_prompt(text, provider, model, style, temperature)
                   for text in texts]

    def batch_enhance_for_video(self,
                                texts: List[str],
                                provider: str,
                                model: str,
                                style: PromptStyle = PromptStyle.CINEMATIC,
                                temperature: float = 0.7,
                                console_callback=None,
                                source_lyrics: Optional[List[str]] = None,
                                lyric_timings: Optional[List[Optional[List[Dict]]]] = None,
                                scene_durations: Optional[List[float]] = None,
                                enable_camera_movements: bool = True,
                                enable_prompt_flow: bool = True) -> List[str]:
        """
        Batch enhance multiple prompts for video generation in ONE API call.
        Adds camera movements, motion, and temporal progression with scene continuity.

        Args:
            texts: List of texts (image prompts) to enhance for video
            provider: LLM provider
            model: Model name
            style: Style of enhancement
            temperature: Creativity parameter
            console_callback: Optional callback for logging
            source_lyrics: Optional list of source lyrics for each scene (provides context)
            lyric_timings: Optional list of timing dicts for each lyric line within batched scenes
            scene_durations: Optional list of total scene durations in seconds
            enable_camera_movements: If True, add camera movements; if False, focus on static shots
            enable_prompt_flow: If True, make prompts flow into each other with section breaks

        Returns:
            List of video-enhanced prompts with camera movements and continuity
        """
        if not self.is_available():
            # Fallback: add basic motion to all prompts
            return [f"{text}. Camera movement: gentle pan and subtle motion." for text in texts]

        # Build system prompt for video enhancement
        camera_guidance = ""
        if enable_camera_movements:
            camera_guidance = """
For each scene, add:
1. **Camera Movements**: Pans (left/right), tilts (up/down), zooms, dolly moves, tracking shots
2. **Subject Motion**: Character actions, environmental movement (wind, water, clouds)
3. **Temporal Progression**: Light changes, emotional progression, scene development"""
        else:
            camera_guidance = """
For each scene, focus on:
1. **Subject Motion**: Character actions, environmental movement (wind, water, clouds)
2. **Temporal Progression**: Light changes, emotional progression, scene development
3. **Static/Minimal Camera**: Keep camera mostly static, use subtle movements only when essential"""

        flow_guidance = ""
        if enable_prompt_flow:
            flow_guidance = """
PROMPT FLOW & CONTINUITY:
- Make scenes flow into each other with smooth visual and narrative continuity
- Each scene should reference or build upon the previous scene's ending
- IMPORTANT: Break flow between song sections (verse/chorus/bridge boundaries)
- Detect section changes from lyrics context and start fresh visual themes at section boundaries
- Within a section, maintain visual coherence and progressive storytelling
- Use natural transitions without explicit phrases like "continuing from" or "building on"
"""
        else:
            flow_guidance = """
SCENE INDEPENDENCE:
- Each scene is independent with its own visual theme
- No need to reference previous or next scenes
- Focus on making each scene compelling on its own
"""

        system_prompt = f"""You are a video prompt engineer. Transform image descriptions into dynamic video prompts for continuous single-shot video generation.
{camera_guidance}

Style: {style.value}
{flow_guidance}
CRITICAL REQUIREMENTS:
- Each scene MUST be a SINGLE CONTINUOUS SHOT with NO HARD CUTS between scenes
- NEVER use editing terminology like "cut to," "next shot," "smash cut," or "jump cut"
- NEVER include quoted text or lyrics in prompts (they will render as text in the video)
- DO describe smooth visual evolution, gradual transformations, and temporal progression
- DO use natural transition phrases like "transitions to," "evolves into," "gradually reveals," "morphs from," "shifts focus to"
- Keep camera movement continuous (pans, tilts, zooms, tracking) within one unified shot
- The scene can smoothly evolve over time - it doesn't have to be static

DURATION CONSTRAINT:
- IMPORTANT: Each scene MUST be 8.0 seconds or less
- If the provided scene duration exceeds 8.0 seconds, you MUST fit the visual content within 8.0 seconds maximum
- Compress or adjust the timing to stay within the 8-second limit

CRITICAL FORMATTING:
- Return EXACTLY {len(texts)} enhanced video prompts
- Number them 1-{len(texts)}
- NO headers, NO markdown, NO preamble
- Each prompt: keep core description + add 2-3 motion elements
- Make camera work subtle and cinematic
- NO quoted text or lyrics in any prompt"""

        # Create batch prompt with context about scene flow and lyrics
        motion_description = "camera movement and motion" if enable_camera_movements else "motion and temporal progression"
        batch_prompt = f"""Transform these {len(texts)} image descriptions into video prompts with {motion_description} for continuous single-shot videos.

"""

        # Add context with frame-accurate timing if available
        # IMPORTANT: We provide timing structure but NOT the actual lyric text to avoid text rendering in videos
        if source_lyrics and lyric_timings and scene_durations:
            batch_prompt += "FRAME-ACCURATE TIMING (Veo 3 generates at 24 FPS):\n\n"
            for i, (lyrics, text, timings, duration) in enumerate(zip(source_lyrics, texts, lyric_timings, scene_durations), 1):
                # Check if this is an instrumental scene
                is_instrumental = (lyrics == "[Instrumental]" or text == "[Instrumental]")

                batch_prompt += f"{i}. SCENE DURATION: {duration:.1f}s\n"

                if is_instrumental:
                    # Provide context from adjacent scenes for instrumental sections
                    batch_prompt += f"   TYPE: INSTRUMENTAL SECTION\n"
                    batch_prompt += f"   INSTRUCTIONS: Create a cinematic visual that:\n"
                    batch_prompt += f"     • Maintains visual continuity with surrounding scenes\n"
                    batch_prompt += f"     • Uses establishing shots, ambient details, or scene transitions\n"
                    batch_prompt += f"     • Provides breathing room and visual variety\n"
                    batch_prompt += f"     • Examples: camera pans across setting, environmental details, character reactions, atmospheric moments\n"
                else:
                    batch_prompt += f"   IMAGE DESCRIPTION: {text}\n"

                if timings and not is_instrumental:
                    # Scene has batched lyrics with timing info - provide timing structure WITH context
                    batch_prompt += f"   TIMING STRUCTURE (describe visual evolution at these timestamps):\n"
                    for timing in timings:
                        # Include lyric text for context so LLM knows what's happening at each timestamp
                        # The LLM won't render text - it uses this to understand the emotional/thematic content
                        lyric_text = timing.get('text', '')
                        batch_prompt += f"     • {timing['start_sec']:.1f}s-{timing['end_sec']:.1f}s: \"{lyric_text}\" ({timing['duration_sec']:.1f}s)\n"

                batch_prompt += "\n"
        elif source_lyrics:
            batch_prompt += "SCENE CONTEXT:\n\n"
            for i, (lyrics, text) in enumerate(zip(source_lyrics, texts), 1):
                is_instrumental = (lyrics == "[Instrumental]" or text == "[Instrumental]")

                if is_instrumental:
                    batch_prompt += f"{i}. TYPE: INSTRUMENTAL SECTION\n"
                    batch_prompt += f"   Create a cinematic visual for a music break.\n"
                    batch_prompt += f"   Use establishing shots, ambient details, or atmospheric moments.\n"
                else:
                    batch_prompt += f"{i}. IMAGE DESCRIPTION: {text}\n"
                batch_prompt += "\n"
        else:
            batch_prompt += "Image descriptions:\n\n"
            for i, text in enumerate(texts, 1):
                batch_prompt += f"{i}. {text}\n"

        camera_instruction = "- Camera movements appropriate to each scene (single continuous shot)\n" if enable_camera_movements else "- Minimal camera movement (mostly static shots with subtle movements only when necessary)\n"

        batch_prompt += f"""
Return {len(texts)} numbered video prompts with:
{camera_instruction}- Natural subject/environmental motion within the same scene
- Visualize the themes and emotions from the content
- For INSTRUMENTAL SECTIONS: Create atmospheric, establishing, or transitional visuals that maintain continuity
- For batched scenes: Use explicit time markers (e.g., "0-3s: ..., 3-5s: ..., 5-8s: ...") to describe visual evolution at the provided timestamps
- Describe smooth visual transitions at timestamps using phrases like:
  * "transitions to," "evolves into," "gradually reveals," "shifts to"
  * "morphs from X to Y," "transforms into," "the scene shifts focus to"
  * "During seconds 0-3..., then at 3s transitions to..., by 5s evolves into..."
- NO hard cuts or abrupt scene changes - describe ONE continuous camera movement with smoothly evolving visuals
- Each prompt describes ONE continuous unified shot with smooth internal visual progression

CRITICAL: Do NOT include any quoted text or lyrics in the prompts. Only provide pure visual descriptions. Text in quotes will be rendered as actual text in the video.

GOOD EXAMPLES:
  ✓ "...the camera slowly pans right, transitioning focus from the forest to the ocean shore"
  ✓ "...as the sun sets (0-3s), the scene gradually reveals stars appearing (3-5s), evolving into a full night sky (5-8s)"
  ✓ "...the character walks forward as the background morphs from city to countryside"
  ✓ "INSTRUMENTAL: Wide establishing shot, camera slowly dollying forward through the misty forest, revealing shafts of morning light filtering through the trees, gentle wind rustling leaves"

BAD EXAMPLES:
  ✗ "Cut to a new location" (hard cut)
  ✗ "Next shot shows..." (editing terminology)
  ✗ "Scene changes to..." (discontinuous)
  ✗ Any quoted text or lyrics in the prompt

Format: Just return numbered prompts (1. ... 2. ... etc.), no other text."""

        try:
            # Prepare model identifier
            if provider == 'lmstudio':
                model_id = model
                api_base = self.lmstudio_base
            else:
                from core.llm_models import get_provider_prefix
                prefix = get_provider_prefix(provider)
                model_id = f"{prefix}{model}" if prefix else model
                api_base = None

            # Adjust max_tokens for video prompts (slightly longer than image prompts)
            max_tokens = 200 * len(texts)  # ~200 tokens per video prompt

            kwargs = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": batch_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": 120
            }

            if api_base:
                kwargs["api_base"] = api_base

            if console_callback:
                console_callback(f"🎬 Batch enhancing {len(texts)} prompts for video in ONE API call...", "INFO")

            self.logger.info(f"Batch enhancing {len(texts)} prompts for video with {provider}/{model}")

            # Log the full request
            self.logger.info("=== VIDEO PROMPT ENHANCEMENT REQUEST ===")
            self.logger.info(f"System prompt (FULL, {len(system_prompt)} chars):")
            self.logger.info(system_prompt)
            self.logger.info(f"User prompt (FULL, {len(batch_prompt)} chars):")
            self.logger.info(batch_prompt)
            self.logger.info("=== END VIDEO PROMPT REQUEST ===")

            response = self.litellm.completion(**kwargs)

            # Parse the response
            enhanced_text = response.choices[0].message.content.strip()

            # Log the full response
            self.logger.info("=== VIDEO PROMPT ENHANCEMENT RESPONSE ===")
            self.logger.info(f"Response (FULL, {len(enhanced_text)} chars):")
            self.logger.info(enhanced_text)
            self.logger.info("=== END VIDEO PROMPT RESPONSE ===")

            # Use the batch parser
            results = self._parse_batch_response(enhanced_text, len(texts))

            # Fallback for missing results
            while len(results) < len(texts):
                missing_idx = len(results)
                self.logger.warning(f"Missing video result {missing_idx + 1}, using fallback with motion")
                fallback = f"{texts[missing_idx]}. Camera movement: gentle pan and subtle motion, natural environmental dynamics."
                results.append(fallback)

            if console_callback:
                console_callback(f"✅ Batch video enhancement complete: {len(results)} prompts", "SUCCESS")

            return results[:len(texts)]

        except Exception as e:
            self.logger.error(f"Batch video enhancement failed: {e}")
            # Fallback: add basic motion to all prompts
            return [f"{text}. Camera movement: gentle pan and subtle motion." for text in texts]

    def analyze_image(self,
                     messages: List[Dict[str, Any]],
                     model: str = None,
                     temperature: float = 0.7,
                     max_tokens: int = 1000,
                     reasoning_effort: str = None,
                     response_format: Dict[str, str] = None) -> str:
        """
        Analyze an image using vision-capable models.

        Args:
            messages: List of message dicts with text and image content
            model: Model name to use
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            reasoning_effort: For GPT-5 models
            response_format: Response format specification

        Returns:
            Generated text description
        """
        try:
            # Set up the model if not specified
            if not model:
                model = 'gpt-4o'  # Default vision-capable model

            # Prepare kwargs for litellm
            kwargs = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens
            }

            # Handle GPT-5 specific parameters
            if 'gpt-5' in model.lower():
                # GPT-5 requires temperature=1
                kwargs['temperature'] = 1.0
                # Note: reasoning_effort is not yet supported by the API
                # It's a UI-only parameter for now

            if response_format:
                kwargs['response_format'] = response_format

            # Get appropriate API configuration
            if 'gpt' in model.lower() or 'openai' in model.lower():
                if 'openai_api_key' in self.config:
                    kwargs['api_key'] = self.config['openai_api_key']
            elif 'claude' in model.lower():
                if 'anthropic_api_key' in self.config:
                    kwargs['api_key'] = self.config['anthropic_api_key']
            elif 'gemini' in model.lower():
                if 'google_api_key' in self.config:
                    kwargs['api_key'] = self.config['google_api_key']

            # Call litellm for vision analysis
            response = self.litellm.completion(**kwargs)

            # Extract and return the response
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                raise ValueError("No response from LLM")

        except Exception as e:
            self.logger.error(f"Image analysis failed: {str(e)}")
            raise

    # Alias for backward compatibility
    def generate(self, *args, **kwargs):
        """Alias for analyze_image for backward compatibility."""
        return self.analyze_image(*args, **kwargs)

    def _get_system_prompt(self, style: PromptStyle) -> str:
        """Get system prompt for a given style"""
        prompts = {
            PromptStyle.CINEMATIC: """You are a cinematic prompt engineer creating visual scene descriptions for a personal music video project. Transform the provided text into detailed image generation prompts with:
- Specific camera angles (wide shot, close-up, aerial, etc.)
- Lighting descriptions (golden hour, dramatic shadows, soft lighting)
- Cinematic elements (depth of field, lens type, film grain)
- Mood and atmosphere
- Visual composition

Important: You are creating original visual descriptions inspired by the text's themes and emotions, not reproducing copyrighted content. Focus on the visual storytelling. Be highly descriptive and detailed.""",
            
            PromptStyle.ARTISTIC: """You are an artistic prompt engineer. Transform text into artistic image generation prompts with:
- Art style references (impressionist, surreal, abstract, etc.)
- Color palette descriptions
- Artistic techniques and textures
- Emotional and symbolic elements
- Composition and balance
Keep prompts creative and evocative.""",
            
            PromptStyle.PHOTOREALISTIC: """You are a photorealistic prompt engineer. Transform text into detailed photography prompts with:
- Camera specifications (lens, aperture, ISO)
- Realistic lighting conditions
- Authentic textures and materials
- Environmental details
- Professional photography techniques
Keep prompts technically accurate and detailed.""",
            
            PromptStyle.ANIMATED: """You are an animation prompt engineer. Transform text into animated/cartoon style prompts with:
- Animation style (Pixar, anime, 2D cartoon, etc.)
- Character expressions and poses
- Vibrant colors and stylization
- Dynamic action and movement
- Whimsical or exaggerated elements
Keep prompts fun and expressive.""",
            
            PromptStyle.DOCUMENTARY: """You are a documentary prompt engineer. Transform text into documentary-style prompts with:
- Authentic, candid moments
- Natural lighting and settings
- Real-world contexts
- Human stories and emotions
- Journalistic framing
Keep prompts grounded and authentic.""",
            
            PromptStyle.ABSTRACT: """You are an abstract prompt engineer. Transform text into abstract visual prompts with:
- Conceptual interpretations
- Color, shape, and form focus
- Symbolic representations
- Emotional essence over literal depiction
- Experimental visual techniques
Keep prompts open to interpretation and artistic.""",

            PromptStyle.NOIR: """You are a film noir prompt engineer. Transform text into noir-style prompts with:
- High contrast black and white aesthetics
- Dramatic shadows and venetian blind effects
- Moody, atmospheric lighting
- Urban decay and rain-slicked streets
- Mystery and suspense elements
Keep prompts dark and atmospheric.""",

            PromptStyle.FANTASY: """You are a fantasy prompt engineer. Transform text into epic fantasy prompts with:
- Magical and mystical elements
- Epic landscapes and grand vistas
- Mythical creatures and enchanted settings
- Rich, saturated colors and ethereal lighting
- Sense of wonder and adventure
Keep prompts imaginative and otherworldly.""",

            PromptStyle.SCIFI: """You are a science fiction prompt engineer. Transform text into sci-fi prompts with:
- Futuristic technology and advanced machinery
- Sleek, modern designs and neon lighting
- Space settings or cyberpunk cities
- Holographic displays and high-tech elements
- Clean lines and technological sophistication
Keep prompts forward-thinking and innovative.""",

            PromptStyle.VINTAGE: """You are a vintage photography prompt engineer. Transform text into retro-style prompts with:
- Classic film photography aesthetics
- Warm, faded colors or sepia tones
- Grain and texture of old photographs
- Period-appropriate clothing and settings
- Nostalgic, timeless quality
Keep prompts evocative of past eras.""",

            PromptStyle.MINIMALIST: """You are a minimalist prompt engineer. Transform text into minimal prompts with:
- Clean, simple compositions
- Limited color palettes
- Negative space and balance
- Essential elements only
- Modern, uncluttered aesthetics
Keep prompts refined and elegant.""",

            PromptStyle.DRAMATIC: """You are a dramatic prompt engineer. Transform text into high-impact prompts with:
- High contrast and bold lighting
- Intense emotions and expressions
- Theatrical staging and composition
- Dynamic angles and perspectives
- Powerful visual impact
Keep prompts emotionally charged and striking."""
        }

        return prompts.get(style, prompts[PromptStyle.CINEMATIC])


class PromptEngine:
    """Main prompt generation and management engine"""
    
    def __init__(self, 
                 llm_provider: Optional[UnifiedLLMProvider] = None,
                 template_dir: Optional[Path] = None):
        """
        Initialize prompt engine.
        
        Args:
            llm_provider: UnifiedLLMProvider instance
            template_dir: Directory containing Jinja2 templates
        """
        self.llm_provider = llm_provider or UnifiedLLMProvider()
        self.logger = logging.getLogger(__name__)
        
        # Set up Jinja2 environment
        if template_dir and template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir))
            )
        else:
            # Use default templates directory
            default_dir = Path(__file__).parent.parent.parent / "templates" / "video"
            if default_dir.exists():
                self.jinja_env = Environment(
                    loader=FileSystemLoader(str(default_dir))
                )
            else:
                self.jinja_env = None
                self.logger.warning("No template directory found")
    
    def enhance_scene_prompts(self,
                             scenes: List[Scene],
                             provider: str,
                             model: str,
                             style: PromptStyle = PromptStyle.CINEMATIC,
                             batch_size: int = 10) -> List[Scene]:
        """
        Enhance prompts for a list of scenes.
        
        Args:
            scenes: List of Scene objects
            provider: LLM provider
            model: Model name
            style: Enhancement style
            batch_size: Number of prompts to process at once
            
        Returns:
            List of scenes with enhanced prompts
        """
        if not self.llm_provider.is_available():
            self.logger.warning("LLM provider not available")
            return scenes
        
        # Process in batches for efficiency
        for i in range(0, len(scenes), batch_size):
            batch_scenes = scenes[i:i + batch_size]
            batch_texts = [scene.source for scene in batch_scenes]
            
            # Enhance the batch
            enhanced_prompts = self.llm_provider.batch_enhance(
                batch_texts, provider, model, style
            )
            
            # Update scenes with enhanced prompts
            for scene, enhanced in zip(batch_scenes, enhanced_prompts):
                # Save original to history
                scene.add_prompt_to_history(scene.prompt)
                # Set new enhanced prompt
                scene.prompt = enhanced
                scene.metadata["prompt_enhanced"] = True
                scene.metadata["prompt_provider"] = provider
                scene.metadata["prompt_model"] = model
                scene.metadata["prompt_style"] = style.value
        
        return scenes
    
    def apply_template(self,
                      scene: Scene,
                      template_name: str,
                      variables: Optional[Dict[str, Any]] = None) -> str:
        """
        Apply a Jinja2 template to generate a prompt.
        
        Args:
            scene: Scene object
            template_name: Name of the template file
            variables: Additional variables for the template
            
        Returns:
            Generated prompt text
        """
        if not self.jinja_env:
            self.logger.warning("No template environment available")
            return scene.source
        
        try:
            template = self.jinja_env.get_template(template_name)
            
            # Build context
            context = {
                "scene_text": scene.source,
                "scene_number": scene.order + 1,
                "duration_seconds": scene.duration_sec,
                "style": "cinematic"  # Default style
            }
            
            # Add scene metadata
            if scene.metadata:
                context.update(scene.metadata)
            
            # Add custom variables
            if variables:
                context.update(variables)
            
            # Render template
            prompt = template.render(**context)
            
            return prompt.strip()
            
        except Exception as e:
            self.logger.error(f"Failed to apply template {template_name}: {e}")
            return scene.source
    
    def enhance_prompt(self,
                      text: str,
                      provider: str,
                      model: str,
                      style: PromptStyle = PromptStyle.CINEMATIC,
                      temperature: float = 0.7,
                      max_tokens: int = 150,
                      console_callback=None) -> str:
        """
        Enhance a text prompt using an LLM.

        Args:
            text: Original text to enhance
            provider: LLM provider
            model: Model name
            style: Style of enhancement
            temperature: Creativity parameter (0-1)
            max_tokens: Maximum tokens in response
            console_callback: Optional callback function(message, level) for console logging

        Returns:
            Enhanced prompt text
        """
        return self.llm_provider.enhance_prompt(
            text, provider, model, style, temperature, max_tokens, console_callback
        )

    def regenerate_prompt(self,
                         scene: Scene,
                         provider: str,
                         model: str,
                         style: Optional[PromptStyle] = None) -> str:
        """
        Regenerate a single scene's prompt.

        Args:
            scene: Scene to regenerate prompt for
            provider: LLM provider
            model: Model name
            style: Optional style override

        Returns:
            New prompt text
        """
        # Use existing style if not specified
        if style is None and "prompt_style" in scene.metadata:
            style = PromptStyle(scene.metadata["prompt_style"])
        else:
            style = style or PromptStyle.CINEMATIC

        # Generate new prompt
        new_prompt = self.llm_provider.enhance_prompt(
            scene.source, provider, model, style
        )

        # Update scene
        scene.add_prompt_to_history(scene.prompt)
        scene.prompt = new_prompt
        scene.metadata["prompt_regenerated"] = True

        return new_prompt

    def enhance_for_video(self,
                         text: str,
                         provider: str,
                         model: str,
                         style: PromptStyle = PromptStyle.CINEMATIC,
                         previous_scene_context: str = None,
                         console_callback=None) -> str:
        """
        Enhance a text prompt specifically for video generation.
        Adds camera movements, motion, and temporal progression.

        Args:
            text: Original text (can be an image prompt)
            provider: LLM provider
            model: Model name
            style: Style of enhancement
            previous_scene_context: Context from previous scene for continuity
            console_callback: Optional callback for logging

        Returns:
            Enhanced video prompt with motion and camera work
        """
        if not self.llm_provider.is_available():
            # Fallback: add basic motion to the prompt
            return f"{text}. Camera movement: gentle pan and subtle motion."

        # Build system prompt for video enhancement
        system_prompt = f"""You are a video prompt engineer. Transform image descriptions into dynamic video prompts for continuous single-shot video generation by adding:

1. **Camera Movements**:
   - Pans (left/right), tilts (up/down), zooms (in/out), dolly moves
   - Orbiting, tracking shots, crane movements
   - Keep movements smooth and purposeful within ONE continuous shot

2. **Subject Motion**:
   - Character actions (walking, gesturing, turning)
   - Environmental movement (wind, water, clouds)
   - Object interactions within the same scene

3. **Temporal Progression**:
   - Light changes within the shot
   - Emotional progression
   - Scene development over time

Style: {style.value}

CRITICAL REQUIREMENTS:
- The video MUST be a SINGLE CONTINUOUS SHOT with NO HARD CUTS between scenes
- NEVER use editing terminology like "cut to," "next shot," "smash cut," or "jump cut"
- NEVER include quoted text or lyrics in the prompt (they will render as text in the video)
- DO describe smooth visual evolution, gradual transformations, and temporal progression
- DO use natural transition phrases like "transitions to," "evolves into," "gradually reveals," "morphs from"
- Keep camera movement continuous (pans, tilts, zooms, tracking) within one unified shot
- The scene can smoothly evolve over time - it doesn't have to be static

FORMATTING:
- Return ONLY the enhanced video prompt, no preamble
- Keep the core scene description intact
- Add 2-3 motion elements maximum
- Make camera work subtle and cinematic
- DO NOT use markdown formatting
- DO NOT include any quoted text"""

        # Build user prompt
        if previous_scene_context:
            user_prompt = f"""Previous scene: {previous_scene_context}

Current scene description: {text}

Transform this into a single continuous shot video prompt that:
1. Adds appropriate camera movement (no hard cuts, one continuous shot)
2. Includes natural motion and action within the same scene
3. Creates smooth temporal flow and visual evolution within one unified space
4. Uses transition phrases to describe how the scene smoothly evolves over time

CRITICAL:
- This must be ONE CONTINUOUS SHOT with NO hard cuts or scene changes
- Do NOT include any quoted text or lyrics in the prompt
- Describe smooth visual transitions and evolution (e.g., "transitions to," "evolves into," "gradually reveals")

Return only the enhanced video prompt."""
        else:
            user_prompt = f"""Scene description: {text}

Transform this into a dynamic video prompt by adding:
1. Appropriate camera movement (pan, tilt, zoom, etc.) within ONE continuous shot
2. Subject or environmental motion within the same scene
3. Temporal progression and visual evolution within the same unified space
4. Transition phrases to describe smooth visual development over time

CRITICAL:
- This must be ONE CONTINUOUS SHOT with NO hard cuts or scene changes
- Do NOT include any quoted text or lyrics in the prompt
- Describe smooth visual transitions and evolution (e.g., "transitions to," "evolves into," "gradually reveals")

Return only the enhanced video prompt."""

        try:
            # Prepare model identifier
            if provider == 'lmstudio':
                model_id = model
                api_base = self.llm_provider.lmstudio_base
            else:
                from core.llm_models import get_provider_prefix
                prefix = get_provider_prefix(provider)
                model_id = f"{prefix}{model}" if prefix else model
                api_base = None

            kwargs = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 300
            }

            if api_base:
                kwargs["api_base"] = api_base

            # Log to console if callback provided
            if console_callback:
                console_callback(f"=== Video Prompt Enhancement ({provider}/{model}) ===", "INFO")
                console_callback(f"Original: {text[:100]}...", "INFO")

            # Call LiteLLM
            response = self.llm_provider.litellm.completion(**kwargs)

            if response and response.choices and len(response.choices) > 0:
                enhanced = response.choices[0].message.content.strip()

                # Strip markdown headers and formatting
                enhanced = self.llm_provider._strip_markdown_headers(enhanced)

                if console_callback:
                    console_callback(f"Video Enhanced: {enhanced[:100]}...", "SUCCESS")

                self.logger.info(f"Enhanced for video using {provider}/{model}")
                return enhanced
            else:
                # Fallback
                return f"{text}. Camera movement: gentle pan and subtle motion."

        except Exception as e:
            self.logger.error(f"Video enhancement failed: {e}")
            # Fallback
            return f"{text}. Camera movement: gentle pan and subtle motion."