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
5. Image prompts should be still-friendly (clean composition, texture details).
6. Use NEGATIVES to avoid undesirable elements."""

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
                          negatives: str = "low quality, blurry") -> Tuple[Optional[StyleGuide], List[Scene]]:
        """
        Generate storyboard using provider-specific approach.
        
        Returns:
            Tuple of (StyleGuide, List[Scene])
        """
        approach = self.get_approach(provider)
        
        if approach == StoryboardApproach.STRUCTURED_JSON:
            return self._generate_structured_json(
                lyrics, title, duration, provider, model, style, negatives
            )
        elif approach == StoryboardApproach.DIRECTORS_TREATMENT:
            return self._generate_directors_treatment(
                lyrics, title, duration, provider, model, style, negatives
            )
        else:
            return self._generate_hybrid(
                lyrics, title, duration, provider, model, style, negatives
            )
    
    def _generate_structured_json(self,
                                 lyrics: str,
                                 title: str,
                                 duration: int,
                                 provider: str,
                                 model: str,
                                 style: str,
                                 negatives: str) -> Tuple[Optional[StyleGuide], List[Scene]]:
        """Generate using OpenAI's structured JSON approach"""
        
        prompt = self.OPENAI_SCENE_PROMPT.format(
            title=title,
            lyrics=lyrics,
            duration=duration,
            style=style,
            negatives=negatives
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
                                     negatives: str) -> Tuple[Optional[StyleGuide], List[Scene]]:
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
                        negatives: str) -> Tuple[Optional[StyleGuide], List[Scene]]:
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