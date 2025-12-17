"""
LLM-powered scene suggestion for video storyboards.

Analyzes lyrics/text and suggests scene breaks, camera movements,
mood indicators, and other video production metadata using AI.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

from .tag_parser import TagParser, TagType, Tag
from .prompt_engine import UnifiedLLMProvider
from core.llm_models import get_provider_prefix

logger = logging.getLogger(__name__)


@dataclass
class SuggestionResult:
    """Result of scene suggestion"""
    tagged_text: str           # Lyrics with tags inserted
    tags_added: int            # Number of tags added
    scenes_detected: int       # Number of scene breaks
    original_preserved: bool   # True if original lyrics unchanged
    warnings: List[str]        # Any warnings during processing


class SceneSuggester:
    """
    Uses LLM to analyze lyrics and suggest scene breaks,
    camera movements, mood indicators, etc.
    """

    # LLM prompt template for scene analysis
    SCENE_ANALYSIS_PROMPT = """You are an expert music video storyboard artist and director.

TASK: Analyze these song lyrics and add scene direction tags to guide video production.

CRITICAL RULES:
1. PRESERVE ALL ORIGINAL LYRICS EXACTLY - do not modify, delete, paraphrase, or summarize ANY text
2. INSERT tags on NEW LINES BEFORE the lyrics they apply to
3. Keep ALL existing section markers like [Verse 1], [Chorus], [Bridge] - DO NOT remove them
4. Use ONLY these tag formats (curly braces, lowercase tag names):
   - {{scene: description}} - Environment/setting changes (e.g., {{scene: bedroom at night}})
   - {{camera: movement}} - Camera directions (e.g., {{camera: slow push in}})
   - {{mood: atmosphere}} - Emotional tone (e.g., {{mood: melancholy}})
   - {{focus: subject}} - Visual focus (e.g., {{focus: singer's hands}})
   - {{transition: type}} - Scene transitions (e.g., {{transition: dissolve}})
   - {{lipsync}} - Mark scenes where character should lip-sync (no value needed)

TAG PLACEMENT GUIDELINES:
- Add {{scene:}} tags at natural visual transition points (verse changes, mood shifts, new imagery in lyrics)
- Add {{camera:}} for dynamic moments (energy changes, emotional peaks)
- Add {{mood:}} when emotional tone shifts significantly
- Add {{focus:}} for close-up opportunities or important visual elements mentioned in lyrics
- Add {{lipsync}} for sections where a character sings directly to camera
- Maximum 2-3 tags per lyric section to avoid clutter
- Every output MUST have at least one {{scene:}} tag

AUDIO/TEMPO CONTEXT:
{tempo_context}

STYLE PREFERENCE: {style}

INPUT LYRICS:
---
{lyrics}
---

OUTPUT: Return the COMPLETE lyrics with tags inserted on new lines. Include ALL original text."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the scene suggester.

        Args:
            config: Configuration with API keys for LLM providers
        """
        self.config = config or {}
        self.llm = UnifiedLLMProvider(config)
        self.tag_parser = TagParser()

    def suggest_scenes(
        self,
        lyrics: str,
        provider: str,
        model: str,
        style: str = "cinematic",
        tempo_bpm: Optional[int] = None,
        audio_duration: Optional[float] = None,
        temperature: float = 0.7,
        console_callback: Optional[Callable[[str, str], None]] = None
    ) -> SuggestionResult:
        """
        Analyze lyrics and suggest scene tags using LLM.

        Args:
            lyrics: Input lyrics/text
            provider: LLM provider (openai, anthropic, gemini, etc.)
            model: Model name
            style: Visual style preference
            tempo_bpm: Song tempo in BPM (if known)
            audio_duration: Audio duration in seconds (if known)
            temperature: LLM creativity (0-1)
            console_callback: Optional callback for status messages

        Returns:
            SuggestionResult with tagged text and metadata
        """
        if not self.llm.is_available():
            logger.warning("LiteLLM not available for scene suggestion")
            return SuggestionResult(
                tagged_text=lyrics,
                tags_added=0,
                scenes_detected=0,
                original_preserved=True,
                warnings=["LLM not available - no suggestions added"]
            )

        # Build tempo context
        tempo_context = self._build_tempo_context(tempo_bpm, audio_duration)

        # Build the prompt
        prompt = self.SCENE_ANALYSIS_PROMPT.format(
            lyrics=lyrics,
            style=style,
            tempo_context=tempo_context
        )

        # Log request
        if console_callback:
            console_callback(f"Analyzing lyrics with {provider}/{model}...", "INFO")
            console_callback(f"Style: {style}, Tempo: {tempo_bpm or 'unknown'} BPM", "INFO")

        logger.info(f"Requesting scene suggestions from {provider}/{model}")
        logger.debug(f"Prompt length: {len(prompt)} chars")

        try:
            # Call LLM
            result = self._call_llm(
                prompt=prompt,
                provider=provider,
                model=model,
                temperature=temperature,
                console_callback=console_callback
            )

            if not result:
                logger.warning("Empty response from LLM")
                return SuggestionResult(
                    tagged_text=lyrics,
                    tags_added=0,
                    scenes_detected=0,
                    original_preserved=True,
                    warnings=["LLM returned empty response"]
                )

            # Validate and process result
            return self._process_llm_response(result, lyrics, console_callback)

        except Exception as e:
            logger.error(f"Scene suggestion failed: {e}", exc_info=True)
            if console_callback:
                console_callback(f"Error: {str(e)}", "ERROR")
            return SuggestionResult(
                tagged_text=lyrics,
                tags_added=0,
                scenes_detected=0,
                original_preserved=True,
                warnings=[f"LLM error: {str(e)}"]
            )

    def _build_tempo_context(self, tempo_bpm: Optional[int], duration: Optional[float]) -> str:
        """Build tempo context string for LLM prompt"""
        parts = []

        if tempo_bpm:
            if tempo_bpm < 80:
                energy = "slow, contemplative"
                camera_suggestion = "Use slow, deliberate camera movements. Longer holds on shots."
            elif tempo_bpm < 120:
                energy = "moderate, steady"
                camera_suggestion = "Balance static and moving shots. Medium-paced transitions."
            elif tempo_bpm < 150:
                energy = "upbeat, energetic"
                camera_suggestion = "More dynamic camera work. Quicker cuts possible."
            else:
                energy = "fast, intense"
                camera_suggestion = "High-energy camera movements. Rapid scene changes acceptable."

            parts.append(f"Tempo: {tempo_bpm} BPM ({energy})")
            parts.append(camera_suggestion)

        if duration:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            parts.append(f"Duration: {minutes}:{seconds:02d}")

        if not parts:
            return "No tempo information available. Use your judgment for pacing."

        return "\n".join(parts)

    def _call_llm(
        self,
        prompt: str,
        provider: str,
        model: str,
        temperature: float,
        console_callback: Optional[Callable[[str, str], None]] = None
    ) -> Optional[str]:
        """Call LLM and return response text"""
        if not self.llm.litellm:
            return None

        # Build model identifier
        prefix = get_provider_prefix(provider)
        model_id = f"{prefix}{model}" if prefix else model

        # System message
        system_msg = (
            "You are a professional music video storyboard artist. "
            "Your task is to add scene direction tags to lyrics while "
            "preserving every word of the original text exactly."
        )

        try:
            kwargs = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": 4000  # Allow for longer responses with tags
            }

            logger.info(f"Calling LLM: {model_id}")
            if console_callback:
                console_callback(f"Sending request to {model_id}...", "INFO")

            response = self.llm.litellm.completion(**kwargs)

            if (response and response.choices and len(response.choices) > 0
                and response.choices[0].message
                and response.choices[0].message.content):
                content = response.choices[0].message.content.strip()
                logger.info(f"Received response: {len(content)} chars")
                if console_callback:
                    console_callback(f"Received {len(content)} chars from LLM", "SUCCESS")
                return content

            return None

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _process_llm_response(
        self,
        response: str,
        original_lyrics: str,
        console_callback: Optional[Callable[[str, str], None]] = None
    ) -> SuggestionResult:
        """Process and validate LLM response"""
        warnings = []

        # Clean up response (remove markdown code blocks if present)
        cleaned = self._clean_response(response)

        # Parse tags from response
        parse_result = self.tag_parser.parse(cleaned)

        # Count tags by type
        tags_added = len(parse_result.tags)
        scenes_detected = len(parse_result.get_scene_tags())

        # Verify original lyrics are preserved
        original_preserved = self._verify_lyrics_preserved(
            original_lyrics, parse_result.clean_text
        )

        if not original_preserved:
            warnings.append("Some original lyrics may have been modified - please verify")
            logger.warning("Lyrics verification failed - LLM may have modified text")
            if console_callback:
                console_callback("Warning: Lyrics may have been modified", "WARNING")

        if scenes_detected == 0:
            warnings.append("No scene tags detected - adding default")
            # Add a default scene tag at the start
            cleaned = "{scene: opening}\n" + cleaned
            scenes_detected = 1
            tags_added += 1

        logger.info(f"Processed response: {tags_added} tags, {scenes_detected} scenes")
        if console_callback:
            console_callback(f"Added {tags_added} tags ({scenes_detected} scene breaks)", "SUCCESS")

        return SuggestionResult(
            tagged_text=cleaned,
            tags_added=tags_added,
            scenes_detected=scenes_detected,
            original_preserved=original_preserved,
            warnings=warnings
        )

    def _clean_response(self, response: str) -> str:
        """Clean LLM response of markdown artifacts"""
        # Remove markdown code blocks
        response = re.sub(r'^```\w*\n', '', response)
        response = re.sub(r'\n```$', '', response)
        response = re.sub(r'^```', '', response)
        response = re.sub(r'```$', '', response)

        # Remove any "OUTPUT:" or similar prefixes
        response = re.sub(r'^OUTPUT:\s*\n?', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^TAGGED LYRICS:\s*\n?', '', response, flags=re.IGNORECASE)

        return response.strip()

    def _verify_lyrics_preserved(self, original: str, processed: str) -> bool:
        """
        Verify that original lyrics are preserved in processed text.

        Compares non-tag content to ensure LLM didn't modify lyrics.
        """
        # Normalize both texts for comparison
        def normalize(text: str) -> str:
            # Remove all tags
            text = self.tag_parser.remove_all_tags(text)
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            # Remove leading/trailing whitespace
            text = text.strip().lower()
            return text

        orig_normalized = normalize(original)
        proc_normalized = normalize(processed)

        # Check similarity (allow small differences for formatting)
        if orig_normalized == proc_normalized:
            return True

        # Calculate similarity ratio
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, orig_normalized, proc_normalized).ratio()

        logger.debug(f"Lyrics similarity ratio: {ratio:.2%}")

        # Allow 95% similarity (accounts for minor formatting differences)
        return ratio >= 0.95

    def has_existing_tags(self, text: str) -> bool:
        """Check if text already has scene tags"""
        return self.tag_parser.has_tags(text)

    def count_existing_tags(self, text: str) -> Dict[str, int]:
        """Count existing tags by type"""
        return self.tag_parser.count_tags(text)

    def remove_tags(self, text: str) -> str:
        """Remove all tags from text"""
        return self.tag_parser.remove_all_tags(text)


# Convenience function for quick scene suggestion
def suggest_scenes_for_lyrics(
    lyrics: str,
    config: Dict[str, Any],
    provider: str,
    model: str,
    **kwargs
) -> SuggestionResult:
    """
    Convenience function to suggest scenes for lyrics.

    Args:
        lyrics: Input lyrics
        config: Config with API keys
        provider: LLM provider
        model: Model name
        **kwargs: Additional arguments passed to suggest_scenes

    Returns:
        SuggestionResult
    """
    suggester = SceneSuggester(config)
    return suggester.suggest_scenes(
        lyrics=lyrics,
        provider=provider,
        model=model,
        **kwargs
    )
