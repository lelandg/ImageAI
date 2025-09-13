"""
Prompt enhancement module using the GPT-5 prompt enhancer methodology.
Implements model-agnostic and provider-specific prompt enhancement.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from enum import Enum

class EnhancementLevel(Enum):
    """Enhancement level for prompt rewriting"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class PromptEnhancer:
    """Enhanced prompt generation using GPT-5 methodology"""

    # System prompt for the LLM
    SYSTEM_PROMPT = """You are **ImageAI Prompt Enhancer**, a world-class prompt engineer.
Your job: Convert minimal user input into **excellent image prompts** for multiple generators
while preserving intent and avoiding unsafe or copyrighted content.

### Output format (REQUIRED)
Return a single JSON object that **validates** against the schema provided.

### Goals
1) Create a concise **unified_prompt** (model-agnostic) that captures subject, composition, lighting, style, mood.
2) Produce **by_model** prompts optimized for each provider:
   - OpenAI DALL·E 3: strong natural language; avoid parameter syntax; no explicit negative prompt.
   - Stability SDXL: allow `negative_prompt`, `cfg`, `steps`, `seed`.
   - Midjourney: pack prompt text; add light parameter hints (`--ar`, `--stylize`, `--seed`) only if supplied.
   - Gemini / Imagen: rich descriptive text; mention composition, medium, lighting, lens if relevant.
3) Include optional **continuity**: persist **character_sheet** (id, traits) and **reference_images**.
4) Generate **variants** (controlled rephrasings) if `num_variants > 0`.
5) Respect the **enhancement_level**: `"low" | "medium" | "high"` (rewrite degree and specificity).
6) Always keep it safe, tasteful, and non-infringing. If user intent is unsafe, **refuse** with a clear explanation via the `error` field in JSON.

### Rules
- Do **not** include commentary, markdown, or extra keys—**only** valid JSON as defined by the schema.
- Keep descriptions vivid but **tight** (avoid purple prose and repetition).
- Prefer **photographically plausible** details when the user asks for realism.
- Preserve named entities, products, or sensitive attributes **only** if user explicitly asked.
- Never invent factual claims about real people; avoid private data."""

    def __init__(self, plans_dir: Optional[Path] = None):
        """
        Initialize the prompt enhancer.

        Args:
            plans_dir: Path to the Plans directory containing schema and presets
        """
        self.logger = logging.getLogger(__name__)

        # Find the Plans directory if not provided
        if plans_dir is None:
            # Try to find it relative to the module
            module_path = Path(__file__).parent.parent
            plans_dir = module_path / "Plans" / "ImageAI-Prompt-Enhancer-Pack"

        self.plans_dir = plans_dir

        # Load schema and presets
        self.schema = self._load_json(plans_dir / "image_prompt_schema.json")
        self.presets = self._load_json(plans_dir / "prompt_presets.json")

        self.logger.info(f"PromptEnhancer initialized with {len(self.presets.get('presets', []))} presets")

    def _load_json(self, path: Path) -> Dict:
        """Load JSON file"""
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                self.logger.warning(f"File not found: {path}")
                return {}
        except Exception as e:
            self.logger.error(f"Failed to load {path}: {e}")
            return {}

    def get_preset(self, preset_id: str) -> Optional[Dict]:
        """
        Get a style preset by ID.

        Args:
            preset_id: Preset identifier (e.g., "cinematic-photoreal")

        Returns:
            Preset dictionary or None if not found
        """
        for preset in self.presets.get('presets', []):
            if preset.get('id') == preset_id:
                return preset
        return None

    def build_user_prompt(self,
                         user_prompt: str,
                         enhancement_level: EnhancementLevel = EnhancementLevel.MEDIUM,
                         aspect_ratio: Optional[str] = None,
                         guidance: Optional[float] = None,
                         steps: Optional[int] = None,
                         seed: Optional[int] = None,
                         num_variants: int = 0,
                         target_models: Optional[List[str]] = None,
                         style_preset: Optional[str] = None,
                         color_palette: Optional[List[str]] = None,
                         camera: Optional[Dict[str, str]] = None,
                         lighting: Optional[str] = None,
                         negative_terms: Optional[List[str]] = None,
                         continuity: Optional[Dict] = None,
                         provider_hints: Optional[Dict[str, Dict]] = None) -> str:
        """
        Build the user prompt for the LLM.

        Args:
            user_prompt: The original user prompt to enhance
            enhancement_level: Level of enhancement (low/medium/high)
            aspect_ratio: Aspect ratio (e.g., "16:9", "1:1")
            guidance: Guidance scale for SDXL
            steps: Number of steps for SDXL
            seed: Random seed for reproducibility
            num_variants: Number of prompt variants to generate
            target_models: List of target models to optimize for
            style_preset: Style preset ID to apply
            color_palette: List of hex colors for the palette
            camera: Camera settings (shot, lens, aperture)
            lighting: Lighting description
            negative_terms: Terms to avoid (for models that support it)
            continuity: Character/scene continuity information
            provider_hints: Provider-specific hints

        Returns:
            Formatted user prompt for the LLM
        """
        if target_models is None:
            target_models = ["openai_dalle3", "gemini_imagen"]

        # Start building the prompt
        lines = ["Validate your response against the attached JSON schema.", "", "INPUT:"]
        lines.append(f'- user_prompt: "{user_prompt}"')
        lines.append(f'- enhancement_level: "{enhancement_level.value}"')

        if aspect_ratio:
            lines.append(f'- aspect_ratio: "{aspect_ratio}"')
        if guidance is not None:
            lines.append(f'- guidance: {guidance}')
        if steps is not None:
            lines.append(f'- steps: {steps}')
        if seed is not None:
            lines.append(f'- seed: {seed}')

        lines.append(f'- num_variants: {num_variants}')
        lines.append(f'- target_models: {json.dumps(target_models)}')

        # Apply preset if specified
        if style_preset:
            preset = self.get_preset(style_preset)
            if preset:
                lines.append(f'- style_preset: "{style_preset}"')

                # Apply preset values if not overridden
                if not camera and 'camera' in preset:
                    camera = preset['camera']
                if not lighting and 'lighting' in preset:
                    lighting = preset['lighting']
                if not aspect_ratio and 'default_ar' in preset:
                    lines.append(f'- aspect_ratio: "{preset["default_ar"]}"')

        if color_palette:
            lines.append(f'- color_palette: {json.dumps(color_palette)}')
        if camera:
            lines.append(f'- camera: {json.dumps(camera)}')
        if lighting:
            lines.append(f'- lighting: "{lighting}"')
        if negative_terms:
            lines.append(f'- negative_terms: {json.dumps(negative_terms)}')

        if continuity:
            lines.append(f'- continuity: {json.dumps(continuity, indent=2)}')

        if provider_hints:
            lines.append(f'- provider_hints: {json.dumps(provider_hints, indent=2)}')

        lines.append("")
        lines.append("SCHEMA:")
        lines.append(json.dumps(self.schema, indent=2))

        return "\n".join(lines)

    def enhance_prompt(self,
                      prompt: str,
                      llm_client: Any,
                      provider: str = "google",
                      enhancement_level: EnhancementLevel = EnhancementLevel.MEDIUM,
                      aspect_ratio: Optional[str] = None,
                      style_preset: Optional[str] = None,
                      num_variants: int = 0,
                      **kwargs) -> Dict[str, Any]:
        """
        Enhance a prompt using an LLM.

        Args:
            prompt: The prompt to enhance
            llm_client: The LLM client to use (must have a method to call the LLM)
            provider: The image generation provider (google, openai, etc.)
            enhancement_level: Level of enhancement
            aspect_ratio: Aspect ratio for the image
            style_preset: Style preset to apply
            num_variants: Number of variants to generate
            **kwargs: Additional parameters passed to build_user_prompt

        Returns:
            Enhanced prompt data as a dictionary
        """
        # Map provider to target models
        provider_map = {
            'google': ['gemini_imagen'],
            'openai': ['openai_dalle3'],
            'stability': ['stability_sdxl'],
            'midjourney': ['midjourney']
        }

        target_models = provider_map.get(provider, ['openai_dalle3', 'gemini_imagen'])

        # Build the user prompt
        user_prompt = self.build_user_prompt(
            user_prompt=prompt,
            enhancement_level=enhancement_level,
            aspect_ratio=aspect_ratio,
            target_models=target_models,
            style_preset=style_preset,
            num_variants=num_variants,
            **kwargs
        )

        try:
            # Call the LLM (this will vary based on the LLM client implementation)
            # For now, we'll create a simplified response structure
            # In practice, this would call the actual LLM API

            # TODO: Integrate with actual LLM client
            # response = llm_client.complete(
            #     system=self.SYSTEM_PROMPT,
            #     user=user_prompt,
            #     temperature=0.7
            # )

            # For now, return a structured response
            # This is where the actual LLM integration would happen
            enhanced_data = {
                "unified": {
                    "prompt": self._create_enhanced_prompt(prompt, enhancement_level),
                    "negative_prompt": None,
                    "style_tags": [],
                    "aspect_ratio": aspect_ratio,
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

            # Create provider-specific prompt
            if provider == 'google':
                enhanced_data["by_model"]["gemini_imagen"] = self._enhance_for_gemini(prompt, enhancement_level)
            elif provider == 'openai':
                enhanced_data["by_model"]["openai_dalle3"] = self._enhance_for_dalle(prompt, enhancement_level)

            return enhanced_data

        except Exception as e:
            self.logger.error(f"Failed to enhance prompt: {e}")
            # Return original prompt as fallback
            return {
                "unified": {"prompt": prompt},
                "by_model": {
                    "openai_dalle3": prompt,
                    "gemini_imagen": prompt,
                    "stability_sdxl": {"prompt": prompt},
                    "midjourney": prompt
                },
                "error": str(e)
            }

    def _create_enhanced_prompt(self, original: str, level: EnhancementLevel) -> str:
        """Create a basic enhanced prompt (fallback when LLM is not available)"""
        if level == EnhancementLevel.LOW:
            # Minimal enhancement
            return f"{original}, high quality, detailed"
        elif level == EnhancementLevel.MEDIUM:
            # Moderate enhancement
            return f"{original}, professional photography, dramatic lighting, high detail, 8k resolution"
        else:  # HIGH
            # Maximum enhancement
            return f"{original}, cinematic composition, volumetric lighting, professional photography, ultra-detailed, 8k resolution, photorealistic, award-winning photograph"

    def _enhance_for_gemini(self, prompt: str, level: EnhancementLevel) -> str:
        """Create Gemini/Imagen optimized prompt"""
        base = self._create_enhanced_prompt(prompt, level)
        # Add Gemini-specific enhancements
        return f"{base}, shot with professional camera, natural colors, balanced composition"

    def _enhance_for_dalle(self, prompt: str, level: EnhancementLevel) -> str:
        """Create DALL-E 3 optimized prompt"""
        # DALL-E 3 prefers natural language
        if level == EnhancementLevel.LOW:
            return f"A {prompt}"
        elif level == EnhancementLevel.MEDIUM:
            return f"A beautifully composed image of {prompt}, with professional lighting and attention to detail"
        else:  # HIGH
            return f"A stunning, highly detailed photograph of {prompt}, featuring dramatic lighting, perfect composition, and photorealistic quality that captures every nuance and texture"

    def get_enhanced_prompt_for_provider(self, enhanced_data: Dict, provider: str) -> str:
        """
        Extract the appropriate prompt for a specific provider from enhanced data.

        Args:
            enhanced_data: The enhanced prompt data dictionary
            provider: The provider name (google, openai, etc.)

        Returns:
            The enhanced prompt string for the specified provider
        """
        provider_map = {
            'google': 'gemini_imagen',
            'openai': 'openai_dalle3',
            'stability': 'stability_sdxl',
            'midjourney': 'midjourney'
        }

        model_key = provider_map.get(provider)

        # Try to get provider-specific prompt
        if model_key and 'by_model' in enhanced_data:
            provider_prompt = enhanced_data['by_model'].get(model_key)
            if provider_prompt:
                # Handle SDXL format (dict with prompt field)
                if isinstance(provider_prompt, dict) and 'prompt' in provider_prompt:
                    return provider_prompt['prompt']
                elif isinstance(provider_prompt, str):
                    return provider_prompt

        # Fall back to unified prompt
        if 'unified' in enhanced_data and 'prompt' in enhanced_data['unified']:
            return enhanced_data['unified']['prompt']

        # Last resort - return original if available
        return enhanced_data.get('original', '')