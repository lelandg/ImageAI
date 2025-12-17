"""
Enhanced storyboard generation with provider-specific scene splitting approaches.
Implements OpenAI and Gemini's distinct methods for lyric-to-scene conversion.
Includes support for Veo 3 reference images (up to 3) for visual continuity.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from core.video.project import Scene, ReferenceImage
from core.video.prompt_engine import UnifiedLLMProvider, PromptStyle
import re
import uuid


def parse_scene_markers(lyrics: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Parse scene markers from lyrics text.

    Supports two formats:
    - New format: {scene: bedroom}, {camera: slow pan}, etc.
    - Legacy format: === NEW SCENE: bedroom === (deprecated, converted to new format)

    Returns:
        Tuple of (cleaned_lyrics, list of scene_markers)
        where scene_markers contains {'line_index': int, 'environment': str, 'group_id': str}
        plus any additional metadata from other tag types
    """
    from core.video.tag_parser import TagParser, TagType, extract_scene_metadata

    logger = logging.getLogger(__name__)
    tag_parser = TagParser()

    # Parse all tags (handles both new {scene:} and legacy === formats)
    parse_result = tag_parser.parse(lyrics, convert_legacy=True)

    if parse_result.legacy_markers_found:
        logger.warning(
            "Legacy '=== NEW SCENE ===' format detected. "
            "Consider using {scene: environment} format instead."
        )

    # Build scene markers list from parsed tags
    scene_markers = []
    current_group_id = None
    lines = parse_result.clean_text.split('\n')

    # Track which lines have scene tags applied
    scene_tag_lines = {}
    for tag in parse_result.tags:
        if tag.tag_type == TagType.SCENE:
            # Create a new group for each scene tag
            current_group_id = f"group-{uuid.uuid4().hex[:8]}"
            scene_tag_lines[tag.line_number] = {
                'environment': tag.value,
                'group_id': current_group_id
            }

    # Convert parsed tags to scene markers format
    current_environment = None
    current_group = None
    clean_line_index = 0

    for orig_line_num, line_tags in sorted(parse_result.tags_by_line.items()):
        for tag in line_tags:
            if tag.tag_type == TagType.SCENE:
                current_environment = tag.value
                current_group = f"group-{uuid.uuid4().hex[:8]}"

                # Add marker at this position
                scene_markers.append({
                    'line_index': clean_line_index,
                    'environment': current_environment,
                    'group_id': current_group,
                    'is_marker': True,
                    # Include other metadata from tags on this line
                    'metadata': extract_scene_metadata(line_tags)
                })

    # Also track lines that fall under each scene's scope
    # (lines between scene markers inherit the environment)
    if scene_markers:
        for i, marker in enumerate(scene_markers):
            # Lines from this marker to the next (or end) belong to this scene
            start_idx = marker['line_index']
            end_idx = scene_markers[i + 1]['line_index'] if i + 1 < len(scene_markers) else len(lines)

            for line_idx in range(start_idx, end_idx):
                if line_idx != marker['line_index']:  # Don't duplicate the marker line
                    scene_markers.append({
                        'line_index': line_idx,
                        'environment': marker['environment'],
                        'group_id': marker['group_id'],
                        'is_marker': False
                    })

    # Filter to only keep actual scene break markers for return
    scene_break_markers = [m for m in scene_markers if m.get('is_marker', True)]

    return parse_result.clean_text, scene_break_markers


class StoryboardApproach(Enum):
    """Different approaches to storyboard generation"""
    STRUCTURED_JSON = "structured_json"  # OpenAI's approach
    DIRECTORS_TREATMENT = "directors_treatment"  # Gemini's approach
    HYBRID = "hybrid"  # Best of both


@dataclass
class SceneSpec:
    """Detailed scene specification based on OpenAI's schema"""
    scene_id: str
    section: str  # Intro|Verse|Pre-chorus|Chorus|Bridge|Outro|Instrumental
    start_sec: float
    duration_sec: float
    summary: str
    rationale: str
    continuity: Dict[str, List[str]]  # characters, locations, props
    veo_prompt: str
    image_prompts: Dict[str, Any]
    negatives: List[str]


@dataclass
class StyleGuide:
    """Visual style guide based on Gemini's approach"""
    character: str
    setting: str
    mood: str
    cinematic_style: str


class EnhancedStoryboardGenerator:
    """Enhanced storyboard generator with provider-specific methods"""
    
    # OpenAI's structured JSON prompt
    OPENAI_SCENE_PROMPT = """You are a senior film editor and story artist. From input song lyrics, divide the music video into scenes that maximize emotional clarity and visual continuity. Your output MUST be valid JSON that conforms to the provided schema exactly—no extra keys, no commentary. Use clean language. Prefer realistic, cinematic imagery. Avoid fantasy/sci‑fi unless present in the lyrics. Keep scenes coherent and minimize unnecessary cuts.

Task: Create a scene plan from these lyrics.
Inputs:
- SONG_TITLE: {title}
- LYRICS:
{lyrics}
- TARGET_DURATION_SEC: {duration}
- GLOBAL_STYLE: {style}
- NEGATIVES: {negatives}
- TEMPO: {tempo} BPM{tempo_guidance}

Schema (must match exactly):
{{
  "scenes": [
    {{
      "scene_id": "S1",
      "section": "Intro|Verse|Pre-chorus|Chorus|Bridge|Outro|Instrumental",
      "start_sec": 0,
      "duration_sec": 8,
      "summary": "string, ≤140 chars",
      "rationale": "string, why cut here",
      "continuity": {{
        "characters": ["names or roles"],
        "locations": ["kitchen", "rural church", "..."],
        "props": ["Bible", "banner", "loaf of bread"]
      }},
      "veo_prompt": "One paragraph: subject → context → action → camera → light → ambience → style. Include subtle audio cues if helpful.",
      "image_prompts": {{
        "dalle3": "concise cinematic still description",
        "sd_style": {{
          "positive": "strong descriptive tokens",
          "negative": "artifact avoiders",
          "params": {{"ar": "16:9", "cfg": 7, "steps": 30}}
        }}
      }},
      "negatives": ["list of discouraged elements"]
    }}
  ]
}}

Rules:
1. If sections are labeled in the lyrics ([Verse], etc.), use them to guide scenes. Otherwise infer natural breaks by imagery/POV/time.
2. Assign duration_sec so total ≈ TARGET_DURATION_SEC. If missing, assume ~8s per scene.
3. Keep continuity tight: repeat characters/locations/props across scenes when the lyrics suggest.
4. Veo prompt must be single-paragraph, filmic, concrete, and avoid brand names unless explicitly in lyrics.
5. MATCH VIDEO ENERGY TO TEMPO: Use the tempo to guide camera movement, action intensity, and visual rhythm. Fast tempos (>140 BPM) need quick cuts, dynamic camera moves, energetic action. Slow tempos (<80 BPM) need smooth moves, longer holds, contemplative pacing. Medium tempos use balanced energy.
6. Image prompts should be still-friendly (clean composition, texture details).
7. Use NEGATIVES to avoid undesirable elements."""

    # Gemini's director's treatment prompt
    GEMINI_TREATMENT_PROMPT = """You are an expert music video director and cinematic prompt writer for Google's Veo 3 text-to-video model. Your task is to transform the provided song lyrics into a complete, scene-by-scene shot list that forms a continuous and coherent music video.

Follow these steps precisely:

1. **Create a "Style Guide"**: First, define the core visual elements for the entire video. This guide will ensure consistency. It must include:
   * `character`: A detailed description of the main character
   * `setting`: The primary location or environment
   * `mood`: The overall emotional tone
   * `cinematic_style`: The camera work and visual effects

2. **Segment Lyrics into Scenes**: Read through the entire lyrics and break them down into logical scenes. A scene break should occur at a natural shift in the song's narrative, emotion, or theme.

3. **Write Continuous Veo Prompts**: For each scene, write a specific and detailed prompt for Veo 3. Adhere to these rules for continuity:
   * **The First Prompt**: The prompt for Scene 1 should be very descriptive, fully establishing the character and setting based on your Style Guide.
   * **Subsequent Prompts**: For Scene 2 and onwards, DO NOT repeat the full description. Instead, describe the evolution from the previous scene. Use transitional phrases to ensure a seamless flow.

4. **Output Format**: Your entire response MUST be a single, valid JSON object with two top-level keys: `style_guide` and `scenes`. Each scene object must contain:
   * `scene_number` (integer)
   * `lyrics` (string of the lyrics for that scene)
   * `veo_prompt` (the detailed, continuous prompt for Veo 3)

Here are the lyrics:
\"\"\"{lyrics}\"\"\"

Song Title: {title}
Target Duration: {duration} seconds
Visual Style: {style}

Now, generate the complete JSON output."""

    def __init__(self, llm_provider: Optional[UnifiedLLMProvider] = None):
        self.logger = logging.getLogger(__name__)
        self.llm_provider = llm_provider or UnifiedLLMProvider()
        self.enable_auto_link_references = True  # Auto-link previous scene's last frame as reference

    def _batch_scenes_for_veo(self, scenes: List[Scene], max_duration: float = 8.0) -> List[Dict[str, Any]]:
        """
        Batch consecutive scenes into groups that fit within max_duration for Veo 3.1.

        Args:
            scenes: List of Scene objects with duration_sec
            max_duration: Maximum duration per batch (default 8.0 for Veo 3.1)

        Returns:
            List of batch dictionaries with structure:
            {
                'batch_id': int,
                'scene_ids': List[int],
                'total_duration': float,
                'scenes': List[{scene_id, lyrics, duration}]
            }
        """
        batches = []
        current_batch = []
        current_duration = 0.0
        batch_id = 0

        for i, scene in enumerate(scenes):
            scene_duration = scene.duration_sec

            # If adding this scene would exceed max_duration, finalize current batch
            if current_batch and current_duration + scene_duration > max_duration:
                batches.append({
                    'batch_id': batch_id,
                    'scene_ids': [s['scene_id'] for s in current_batch],
                    'total_duration': current_duration,
                    'scenes': current_batch
                })
                batch_id += 1
                current_batch = []
                current_duration = 0.0

            # Add scene to current batch
            current_batch.append({
                'scene_id': i,
                'lyrics': scene.source,
                'duration': scene_duration
            })
            current_duration += scene_duration

        # Add final batch
        if current_batch:
            batches.append({
                'batch_id': batch_id,
                'scene_ids': [s['scene_id'] for s in current_batch],
                'total_duration': current_duration,
                'scenes': current_batch
            })

        self.logger.info(f"Batched {len(scenes)} scenes into {len(batches)} Veo batches (max {max_duration}s each)")
        return batches

    def _generate_veo_batches(self,
                             scenes: List[Scene],
                             lyrics: str,
                             title: str,
                             style: str,
                             provider: str,
                             model: str) -> Optional[List[Dict]]:
        """
        Generate batched video prompts for Veo 3.1 using LLM with frame-accurate timing.

        Args:
            scenes: List of Scene objects with individual duration_sec values
            lyrics: Full lyrics text
            title: Song title
            style: Visual style guide
            provider: LLM provider
            model: LLM model

        Returns:
            List of batch dictionaries with video_prompt for each batch
        """
        # First, batch the scenes
        batches = self._batch_scenes_for_veo(scenes)

        # Create prompt for LLM to generate combined prompts WITH TIMING
        prompt = f"""You are an expert music video director creating prompts for Google's Veo 3.1 AI video generator.

Veo 3.1 generates 8-second video clips at 24 FPS. You need to create cohesive video prompts for batched lyric segments that RESPECT THE SPECIFIC TIMING of each lyric line.

Song: {title}
Visual Style: {style}
Full Lyrics:
{lyrics}

CRITICAL: Each lyric line below has a specific duration. Your video prompt MUST describe how the scene evolves frame-accurately to match these timings.

For each batch, create a SINGLE unified video prompt that:
1. Specifies what happens during EACH lyric's time window (e.g., "0-3s: [...], 3-5s: [...], 5-8s: [...]")
2. Describes smooth transitions at the exact timestamps where lyrics change
3. Uses temporal markers (e.g., "During the first 3 seconds...", "At the 3-second mark, transitioning to...")
4. Maintains visual continuity with smooth camera movements and lighting changes

Batches with EXACT TIMING:
"""

        for batch in batches:
            prompt += f"\nBatch {batch['batch_id']} (Total: {batch['total_duration']:.1f}s):\n"
            cumulative_time = 0.0
            for scene in batch['scenes']:
                end_time = cumulative_time + scene['duration']
                prompt += f"  - {cumulative_time:.1f}s-{end_time:.1f}s ({scene['duration']:.1f}s): \"{scene['lyrics']}\"\n"
                cumulative_time = end_time

        prompt += """
Output Format (MUST be valid JSON):
{
  "combined_prompts": [
    {
      "batch_id": 0,
      "scene_ids": [0, 1],
      "duration": 5.0,
      "video_prompt": "A time-aware prompt with explicit temporal markers (e.g., '0-3s: wide shot of character..., 3-5s: camera pushes in as character...')",
      "reasoning": "How the timing enhances the narrative flow"
    }
  ]
}

CRITICAL: The video_prompt MUST include explicit time ranges (e.g., "0-3s:", "3-5s:") matching the lyric timings above. This ensures the visual narrative syncs with the lyrics frame-accurately."""

        try:
            # Call LLM
            if not self.llm_provider.is_available():
                self.logger.error("LLM provider not available for Veo batch generation")
                return None

            import litellm

            # Prepare the model string
            if provider == 'gemini':
                model_id = f"gemini/{model}"
            elif provider == 'openai':
                model_id = model
            elif provider == 'claude':
                model_id = model
            else:
                model_id = model

            self.logger.info(f"Generating Veo batched prompts with {provider}/{model}...")
            self.logger.info(f"Prompt sent to LLM:\n{'-'*80}\n{prompt}\n{'-'*80}")

            response = litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are a music video director. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )

            # Extract response text
            response_text = response.choices[0].message.content
            self.logger.info(f"LLM Response:\n{'-'*80}\n{response_text}\n{'-'*80}")

            # Parse JSON response
            result = self._parse_json_response(response_text)

            if not result or 'combined_prompts' not in result:
                self.logger.error("Failed to parse Veo batch response")
                return None

            self.logger.info(f"Generated {len(result['combined_prompts'])} Veo batched prompts")

            # Log the generated prompts for verification (FULL, not truncated)
            for i, batch_prompt in enumerate(result['combined_prompts']):
                self.logger.info(f"Batch {i} (FULL prompt, {len(batch_prompt.get('video_prompt', ''))} chars):")
                self.logger.info(batch_prompt.get('video_prompt', ''))

            return result['combined_prompts']

        except Exception as e:
            self.logger.error(f"Failed to generate Veo batches: {e}")
            return None

    def get_approach(self, provider: str) -> StoryboardApproach:
        """Determine the best approach for a provider"""
        approach_map = {
            'openai': StoryboardApproach.STRUCTURED_JSON,
            'gemini': StoryboardApproach.DIRECTORS_TREATMENT,
            'claude': StoryboardApproach.STRUCTURED_JSON,  # Claude handles structured output well
            'anthropic': StoryboardApproach.STRUCTURED_JSON,
            'ollama': StoryboardApproach.HYBRID,  # Simpler for local models
            'lmstudio': StoryboardApproach.HYBRID
        }
        return approach_map.get(provider.lower(), StoryboardApproach.HYBRID)
    
    def generate_storyboard(self,
                          lyrics: str,
                          title: str = "Untitled",
                          duration: int = 120,
                          provider: str = "gemini",
                          model: str = "gemini-2.5-pro",
                          style: str = "cinematic, high quality",
                          negatives: str = "low quality, blurry",
                          render_method: Optional[str] = None,
                          tempo: Optional[float] = None,
                          word_timestamps: Optional[List[Dict[str, Any]]] = None) -> Tuple[Optional[StyleGuide], List[Scene], Optional[List[Dict]]]:
        """
        Generate storyboard using provider-specific approach.

        Args:
            lyrics: Input text/lyrics to generate scenes from
            title: Video title
            duration: Target duration in seconds
            provider: LLM provider to use (gemini, openai, claude, etc.)
            model: LLM model name
            style: Visual style description
            negatives: Elements to avoid
            render_method: If set to "veo_3.1" or similar, also generates batched prompts for 8s clips
            tempo: Song tempo in BPM (beats per minute) for matching video energy to music
            word_timestamps: Optional Whisper word timestamps for precise scene timing.
                             List of dicts with 'text', 'start_time', 'end_time'.
                             When provided, scene durations are calculated from actual audio timing.

        Returns:
            Tuple of (StyleGuide, List[Scene], Optional[List[VeoBatch]])
            VeoBatch structure: {batch_id, scene_ids, duration, video_prompt}
        """
        # Parse scene markers from lyrics (=== NEW SCENE: <environment> ===)
        cleaned_lyrics, scene_markers = parse_scene_markers(lyrics)

        # Store scene markers for later application to scenes
        self._scene_markers = scene_markers

        # Use cleaned lyrics (without marker lines) for generation
        lyrics_for_llm = cleaned_lyrics

        # Format tempo guidance for LLM
        if tempo:
            if tempo >= 140:
                tempo_guidance = " (Fast/Energetic - use quick cuts, dynamic camera moves, energetic action)"
            elif tempo >= 100:
                tempo_guidance = " (Medium - balanced pacing and energy)"
            elif tempo >= 80:
                tempo_guidance = " (Moderate - smooth movements, contemplative pacing)"
            else:
                tempo_guidance = " (Slow/Ballad - long holds, minimal cuts, emotional depth)"
        else:
            tempo = 120  # Default if not provided
            tempo_guidance = " (Default - adjust based on lyrical content)"

        approach = self.get_approach(provider)

        if approach == StoryboardApproach.STRUCTURED_JSON:
            style_guide, scenes = self._generate_structured_json(
                lyrics_for_llm, title, duration, provider, model, style, negatives, tempo, tempo_guidance
            )
        elif approach == StoryboardApproach.DIRECTORS_TREATMENT:
            style_guide, scenes = self._generate_directors_treatment(
                lyrics_for_llm, title, duration, provider, model, style, negatives, tempo, tempo_guidance
            )
        else:
            style_guide, scenes = self._generate_hybrid(
                lyrics_for_llm, title, duration, provider, model, style, negatives, tempo, tempo_guidance
            )

        # Apply environment and scene_group_id from markers to generated scenes
        scenes = self._apply_scene_markers(scenes, scene_markers)

        # Apply Whisper timing if available
        if word_timestamps:
            scenes = self._apply_whisper_timing(scenes, lyrics, word_timestamps)
            self.logger.info(f"Applied Whisper timing to {len(scenes)} scenes")
        else:
            # Also check for time tags in lyrics and use those
            scenes = self._apply_time_tags(scenes, lyrics)

        # Generate batched prompts if render_method requires it
        veo_batches = None
        if render_method and "veo" in render_method.lower() and "3.1" in render_method:
            veo_batches = self._generate_veo_batches(
                scenes, lyrics, title, style, provider, model
            )

        return style_guide, scenes, veo_batches
    
    def _generate_structured_json(self,
                                 lyrics: str,
                                 title: str,
                                 duration: int,
                                 provider: str,
                                 model: str,
                                 style: str,
                                 negatives: str,
                                 tempo: float = 120,
                                 tempo_guidance: str = "") -> Tuple[Optional[StyleGuide], List[Scene]]:
        """Generate using OpenAI's structured JSON approach"""

        prompt = self.OPENAI_SCENE_PROMPT.format(
            title=title,
            lyrics=lyrics,
            duration=duration,
            style=style,
            negatives=negatives,
            tempo=tempo,
            tempo_guidance=tempo_guidance
        )
        
        try:
            # Use direct LLM call for structured generation, not enhance_prompt
            if not self.llm_provider.is_available():
                self.logger.error("LLM provider not available")
                return None, []
            
            # Call the LLM directly for structured output
            import litellm
            
            # Prepare the model string
            if provider == 'openai':
                model_id = model
            elif provider == 'claude':
                model_id = model
            elif provider == 'gemini':
                model_id = f"gemini/{model}"
            else:
                model_id = model
            
            response = litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are a senior film editor. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            result = self._parse_json_response(response_text)
            
            if not result:
                return None, []
            
            # Extract style guide from first scene's continuity
            style_guide = None
            if result.get('scenes'):
                first_scene = result['scenes'][0]
                continuity = first_scene.get('continuity', {})
                
                # Build style guide from continuity data
                character_desc = ", ".join(continuity.get('characters', ['the main character']))
                location_desc = ", ".join(continuity.get('locations', ['the setting']))
                
                style_guide = StyleGuide(
                    character=character_desc,
                    setting=location_desc,
                    mood=style.split(',')[0] if style else 'cinematic',
                    cinematic_style=style
                )
            
            # Convert to Scene objects
            scenes = self._convert_json_to_scenes(result.get('scenes', []))
            
            return style_guide, scenes
            
        except Exception as e:
            self.logger.error(f"Failed to generate structured storyboard: {e}")
            return None, []
    
    def _generate_directors_treatment(self,
                                     lyrics: str,
                                     title: str,
                                     duration: int,
                                     provider: str,
                                     model: str,
                                     style: str,
                                     negatives: str,
                                     tempo: float = 120,
                                     tempo_guidance: str = "") -> Tuple[Optional[StyleGuide], List[Scene]]:
        """Generate using Gemini's director's treatment approach"""
        
        prompt = self.GEMINI_TREATMENT_PROMPT.format(
            title=title,
            lyrics=lyrics,
            duration=duration,
            style=style
        )
        
        try:
            # Use direct LLM call for structured generation
            if not self.llm_provider.is_available():
                self.logger.error("LLM provider not available")
                return None, []
            
            import litellm
            
            # Prepare the model string
            if provider == 'gemini':
                model_id = f"gemini/{model}"
            elif provider == 'openai':
                model_id = model
            elif provider == 'claude':
                model_id = model
            else:
                model_id = model
            
            response = litellm.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are a music video director. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            result = self._parse_json_response(response_text)
            
            if not result:
                return None, []
            
            # Extract style guide
            style_guide_data = result.get('style_guide', {})
            style_guide = StyleGuide(
                character=style_guide_data.get('character', 'the main character'),
                setting=style_guide_data.get('setting', 'the scene'),
                mood=style_guide_data.get('mood', 'cinematic'),
                cinematic_style=style_guide_data.get('cinematic_style', style)
            )
            
            # Convert to Scene objects
            scenes = []
            for scene_data in result.get('scenes', []):
                scene = Scene(
                    source=scene_data.get('lyrics', ''),
                    prompt=scene_data.get('veo_prompt', ''),
                    duration_sec=duration / len(result.get('scenes', [1])),  # Distribute evenly
                    metadata={
                        'scene_number': scene_data.get('scene_number', len(scenes) + 1),
                        'approach': 'directors_treatment'
                    }
                )
                scenes.append(scene)
            
            return style_guide, scenes
            
        except Exception as e:
            self.logger.error(f"Failed to generate director's treatment: {e}")
            return None, []
    
    def _generate_hybrid(self,
                        lyrics: str,
                        title: str,
                        duration: int,
                        provider: str,
                        model: str,
                        style: str,
                        negatives: str,
                        tempo: float = 120,
                        tempo_guidance: str = "") -> Tuple[Optional[StyleGuide], List[Scene]]:
        """Generate using a simplified hybrid approach for local models"""
        
        # Simplified prompt for local models
        prompt = f"""Create a video storyboard from these lyrics:

Title: {title}
Duration: {duration} seconds
Style: {style}

Lyrics:
{lyrics}

Break the lyrics into 4-8 scenes. For each scene provide:
1. The lyric text for that scene
2. A visual description (one paragraph)
3. Approximate duration in seconds

Format as JSON with 'scenes' array containing objects with 'lyrics', 'description', and 'duration' fields."""

        try:
            response = self.llm_provider.enhance_prompt(
                prompt,
                provider=provider,
                model=model,
                style=PromptStyle.CINEMATIC,
                max_tokens=2000
            )
            
            # Parse response
            result = self._parse_json_response(response)
            
            if not result:
                # Fallback to simple scene splitting
                return None, self._fallback_scene_split(lyrics, duration)
            
            # Convert to scenes
            scenes = []
            for scene_data in result.get('scenes', []):
                scene = Scene(
                    source=scene_data.get('lyrics', ''),
                    prompt=scene_data.get('description', ''),
                    duration_sec=scene_data.get('duration', duration / 4),
                    metadata={'approach': 'hybrid'}
                )
                scenes.append(scene)
            
            # Create basic style guide
            style_guide = StyleGuide(
                character='the performer',
                setting='performance space',
                mood='expressive',
                cinematic_style=style
            )
            
            return style_guide, scenes
            
        except Exception as e:
            self.logger.error(f"Hybrid generation failed, using fallback: {e}")
            return None, self._fallback_scene_split(lyrics, duration)
    
    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response"""
        try:
            # Clean response
            cleaned = response.strip()
            
            # Remove markdown code blocks if present
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            
            return json.loads(cleaned.strip())
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse JSON: {e}")
            
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return None
    
    def _convert_json_to_scenes(self, scenes_data: List[Dict]) -> List[Scene]:
        """Convert JSON scene data to Scene objects"""
        scenes = []
        
        for scene_data in scenes_data:
            # Extract prompts
            image_prompts = scene_data.get('image_prompts', {})
            dalle_prompt = image_prompts.get('dalle3', '')
            veo_prompt = scene_data.get('veo_prompt', '')
            
            # Use veo_prompt as main prompt, dalle as fallback
            prompt = veo_prompt or dalle_prompt or scene_data.get('summary', '')
            
            scene = Scene(
                source=scene_data.get('summary', ''),
                prompt=prompt,
                duration_sec=scene_data.get('duration_sec', 8),
                metadata={
                    'scene_id': scene_data.get('scene_id'),
                    'section': scene_data.get('section'),
                    'continuity': scene_data.get('continuity', {}),
                    'negatives': scene_data.get('negatives', []),
                    'start_sec': scene_data.get('start_sec', 0),
                    'rationale': scene_data.get('rationale', ''),
                    'image_prompts': image_prompts
                }
            )
            scenes.append(scene)
        
        return scenes
    
    def _fallback_scene_split(self, lyrics: str, duration: int) -> List[Scene]:
        """Simple fallback scene splitting when LLM fails"""
        lines = [l.strip() for l in lyrics.split('\n') if l.strip()]

        # Group into sections
        sections = []
        current_section = []

        for line in lines:
            if line.startswith('[') and line.endswith(']'):
                # Section marker
                if current_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
            else:
                current_section.append(line)

        if current_section:
            sections.append('\n'.join(current_section))

        # Create scenes from sections
        scenes = []
        scene_duration = duration / max(len(sections), 1)

        for i, section in enumerate(sections):
            scene = Scene(
                source=section,
                prompt=f"Scene {i+1}: {section[:100]}",
                duration_sec=scene_duration,
                metadata={'approach': 'fallback'}
            )
            scenes.append(scene)

        return scenes

    def _apply_scene_markers(self, scenes: List[Scene], scene_markers: List[Dict[str, str]]) -> List[Scene]:
        """
        Apply environment and scene_group_id from parsed scene markers to generated scenes.

        This matches scene markers (by line content) to generated scenes and assigns
        environment descriptions and group IDs for continuity tracking.

        Args:
            scenes: Generated scenes from LLM
            scene_markers: Parsed scene markers with environment and group_id

        Returns:
            Scenes with environment and scene_group_id fields populated
        """
        if not scene_markers:
            return scenes

        # Build a map of environment by line index or content matching
        # Since LLM may rearrange/combine lines, we need fuzzy matching
        environment_map = {}
        for marker in scene_markers:
            environment_map[marker['line_index']] = {
                'environment': marker['environment'],
                'group_id': marker['group_id']
            }

        # Apply to scenes (simple approach: sequential matching)
        # More sophisticated: match by scene.source content
        current_environment = None
        current_group_id = None

        for i, scene in enumerate(scenes):
            # Check if this scene index has a marker
            if i in environment_map:
                current_environment = environment_map[i]['environment']
                current_group_id = environment_map[i]['group_id']

            # Apply current environment to this scene
            if current_environment:
                scene.environment = current_environment
                scene.scene_group_id = current_group_id

                self.logger.info(f"Scene {i}: Applied environment '{current_environment}' (group: {current_group_id})")

        return scenes

    def _apply_whisper_timing(self,
                              scenes: List[Scene],
                              lyrics: str,
                              word_timestamps: List[Dict[str, Any]]) -> List[Scene]:
        """
        Apply precise timing from Whisper word timestamps to scenes.

        This method matches scene source text to Whisper word timings to determine
        accurate start/end times for each scene based on actual audio.

        Args:
            scenes: Generated scenes
            lyrics: Original lyrics text
            word_timestamps: Whisper word timestamps with 'text', 'start_time', 'end_time'

        Returns:
            Scenes with updated duration_sec and start_sec in metadata
        """
        if not word_timestamps or not scenes:
            return scenes

        # Build word timing map from Whisper data
        # Use sequential word matching to find scene boundaries
        words = [wt.get('text', '').strip().lower() for wt in word_timestamps]
        word_times = [(wt.get('start_time', 0.0), wt.get('end_time', 0.0)) for wt in word_timestamps]

        # Total audio duration
        total_duration = max(wt.get('end_time', 0.0) for wt in word_timestamps) if word_timestamps else 0

        # For each scene, find the words it contains and determine timing
        word_index = 0
        for scene in scenes:
            scene_text = scene.source.lower() if scene.source else ""
            scene_words = [w.strip() for w in scene_text.split() if w.strip()]

            if not scene_words:
                continue

            # Find start word
            start_time = None
            end_time = None

            # Try to find the first word of this scene in the remaining word sequence
            for i in range(word_index, len(words)):
                # Check if this word matches the start of our scene
                first_scene_word = ''.join(c for c in scene_words[0] if c.isalnum())
                word_clean = ''.join(c for c in words[i] if c.isalnum())

                if first_scene_word == word_clean:
                    start_time = word_times[i][0]

                    # Find the last word of this scene
                    last_scene_word = ''.join(c for c in scene_words[-1] if c.isalnum())

                    # Search forward for the last word
                    for j in range(i, min(i + len(scene_words) + 10, len(words))):
                        word_j_clean = ''.join(c for c in words[j] if c.isalnum())
                        if last_scene_word == word_j_clean:
                            end_time = word_times[j][1]
                            word_index = j + 1
                            break

                    if end_time is None and start_time is not None:
                        # Estimate end time based on scene word count
                        estimated_words = min(i + len(scene_words), len(words) - 1)
                        end_time = word_times[estimated_words][1]
                        word_index = estimated_words + 1

                    break

            # Apply timing to scene
            if start_time is not None and end_time is not None:
                scene.duration_sec = end_time - start_time
                if not scene.metadata:
                    scene.metadata = {}
                scene.metadata['start_sec'] = start_time
                scene.metadata['end_sec'] = end_time
                scene.metadata['timing_source'] = 'whisper'

                self.logger.debug(f"Scene timing: {start_time:.2f}s - {end_time:.2f}s ({scene.duration_sec:.2f}s)")

        return scenes

    def _apply_time_tags(self, scenes: List[Scene], lyrics: str) -> List[Scene]:
        """
        Apply timing from {time: MM:SS} tags in lyrics to scenes.

        This method extracts time tags from the input text and uses them
        to set scene start/end times when Whisper data is not available.

        Args:
            scenes: Generated scenes
            lyrics: Original lyrics text with potential time tags

        Returns:
            Scenes with updated timing based on time tags
        """
        from core.video.tag_parser import TagParser, TagType, parse_time_value

        parser = TagParser()
        result = parser.parse(lyrics)

        # Get time tags sorted by line number
        time_tags = [(t.line_number, t.value) for t in result.tags if t.tag_type == TagType.TIME]
        time_tags.sort(key=lambda x: x[0])

        if not time_tags:
            return scenes

        # Parse time values
        parsed_times = []
        for line_num, time_str in time_tags:
            seconds = parse_time_value(time_str)
            if seconds is not None:
                parsed_times.append((line_num, seconds))

        if not parsed_times:
            return scenes

        # Apply times to scenes
        # Simple approach: distribute time tags across scenes based on position
        for i, scene in enumerate(scenes):
            # Find the time tag closest to this scene's position
            scene_position = i / max(len(scenes) - 1, 1)  # 0.0 to 1.0

            # Find corresponding time tag
            tag_index = min(int(scene_position * len(parsed_times)), len(parsed_times) - 1)

            start_time = parsed_times[tag_index][1]

            # End time is the next tag's time, or estimated
            if tag_index + 1 < len(parsed_times):
                end_time = parsed_times[tag_index + 1][1]
            else:
                # Last scene - estimate duration
                end_time = start_time + scene.duration_sec

            scene.duration_sec = end_time - start_time
            if not scene.metadata:
                scene.metadata = {}
            scene.metadata['start_sec'] = start_time
            scene.metadata['end_sec'] = end_time
            scene.metadata['timing_source'] = 'time_tags'

        self.logger.info(f"Applied {len(parsed_times)} time tags to {len(scenes)} scenes")
        return scenes

    def apply_reference_image_auto_linking(self, scenes: List[Scene]) -> List[Scene]:
        """
        Auto-link reference images for visual continuity.
        Uses previous scene's last_frame as first reference image for next scene.

        Args:
            scenes: List of scenes to process

        Returns:
            List of scenes with reference images auto-linked
        """
        if not self.enable_auto_link_references or len(scenes) < 2:
            return scenes

        for i in range(1, len(scenes)):
            prev_scene = scenes[i - 1]
            current_scene = scenes[i]

            # If previous scene has a last_frame, use it as reference for current scene
            if prev_scene.last_frame and prev_scene.last_frame.exists():
                # Create auto-linked reference image
                ref_image = ReferenceImage(
                    path=prev_scene.last_frame,
                    label="continuity",
                    description=f"Last frame from Scene {i} for visual continuity",
                    auto_linked=True,
                    metadata={
                        'source_scene_id': prev_scene.id,
                        'source_scene_order': prev_scene.order
                    }
                )

                # Add as first reference (if scene accepts it)
                if current_scene.add_reference_image(ref_image):
                    self.logger.info(
                        f"Auto-linked Scene {i-1} last frame as reference for Scene {i}"
                    )

        return scenes