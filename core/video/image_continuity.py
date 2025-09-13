"""
Image continuity management for video scene generation.
Implements provider-specific methods for maintaining visual consistency across frames.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import base64
import io
from PIL import Image

from core.video.project import Scene


class ContinuityMethod(Enum):
    """Methods for maintaining visual continuity"""
    ITERATIVE_REFINEMENT = "iterative_refinement"  # Gemini's approach
    REFERENCE_IDS = "reference_ids"  # OpenAI's approach  
    CONSISTENT_DESCRIPTION = "consistent_description"  # Text-only approach
    STYLE_GUIDE = "style_guide"  # Director's treatment approach


@dataclass
class ContinuityContext:
    """Context for maintaining continuity across scenes"""
    style_guide: Optional[Dict[str, str]] = None  # Character, setting, mood, style
    previous_image: Optional[Image.Image] = None
    previous_image_id: Optional[str] = None
    previous_prompt: Optional[str] = None
    scene_history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.scene_history is None:
            self.scene_history = []


class ImageContinuityManager:
    """Manages image continuity across video scenes"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.contexts: Dict[str, ContinuityContext] = {}
    
    def get_continuity_method(self, provider: str) -> ContinuityMethod:
        """Get the best continuity method for a provider"""
        method_map = {
            'gemini': ContinuityMethod.ITERATIVE_REFINEMENT,
            'openai': ContinuityMethod.REFERENCE_IDS,
            'claude': ContinuityMethod.STYLE_GUIDE,  # Best for Claude
            'anthropic': ContinuityMethod.STYLE_GUIDE,
            'ollama': ContinuityMethod.CONSISTENT_DESCRIPTION,  # Best for local
            'lmstudio': ContinuityMethod.CONSISTENT_DESCRIPTION,
            'stability': ContinuityMethod.CONSISTENT_DESCRIPTION
        }
        return method_map.get(provider.lower(), ContinuityMethod.CONSISTENT_DESCRIPTION)
    
    def initialize_project_context(self, project_id: str, style_guide: Optional[Dict[str, str]] = None):
        """Initialize continuity context for a project"""
        self.contexts[project_id] = ContinuityContext(style_guide=style_guide)
        self.logger.info(f"Initialized continuity context for project {project_id}")
    
    def get_context(self, project_id: str) -> ContinuityContext:
        """Get or create continuity context for a project"""
        if project_id not in self.contexts:
            self.contexts[project_id] = ContinuityContext()
        return self.contexts[project_id]
    
    def prepare_gemini_prompt(self, 
                             scene: Scene,
                             project_id: str,
                             is_first: bool = False) -> Tuple[str, Optional[Image.Image]]:
        """
        Prepare prompt for Gemini using iterative refinement approach.
        Based on Gemini Nano Banana Guide.
        """
        context = self.get_context(project_id)
        
        if is_first or not context.previous_image:
            # First scene - establish everything
            if context.style_guide:
                prompt = self._build_establishing_prompt(scene, context.style_guide)
            else:
                prompt = scene.prompt or scene.source
            
            # Add aspect ratio to prompt if needed
            if hasattr(scene, 'aspect_ratio') and scene.aspect_ratio:
                prompt += f" The image should be in {scene.aspect_ratio} format."
            
            return prompt, None
        else:
            # Subsequent scenes - describe changes only
            prompt = self._build_incremental_prompt(scene, context)
            return prompt, context.previous_image
    
    def prepare_openai_prompt(self,
                             scene: Scene,
                             project_id: str,
                             is_first: bool = False) -> Tuple[str, Optional[str]]:
        """
        Prepare prompt for OpenAI using reference IDs approach.
        Based on DALL-E 3 Image Continuity guide.
        """
        context = self.get_context(project_id)
        
        # Build consistent description
        if context.style_guide:
            base_description = self._extract_consistent_elements(context.style_guide)
        else:
            base_description = ""
        
        # Add scene-specific details
        if is_first:
            prompt = f"{base_description} {scene.prompt or scene.source}"
            reference_id = None
        else:
            # Use incremental changes with reference
            prompt = f"The same {base_description}, now {scene.prompt or scene.source}"
            reference_id = context.previous_image_id
        
        return prompt, reference_id
    
    def prepare_claude_prompt(self,
                            scene: Scene,
                            project_id: str,
                            is_first: bool = False) -> str:
        """
        Prepare prompt for Claude using style guide approach.
        Best method for Claude based on analysis.
        """
        context = self.get_context(project_id)
        
        if not context.style_guide:
            # Generate style guide from first scene if not provided
            if is_first:
                context.style_guide = self._infer_style_guide(scene)
        
        if is_first:
            # Establish with full style guide
            prompt = self._build_establishing_prompt(scene, context.style_guide)
        else:
            # Evolution from previous
            prompt = self._build_evolution_prompt(scene, context)
        
        return prompt
    
    def prepare_local_prompt(self,
                           scene: Scene,
                           project_id: str,
                           is_first: bool = False) -> str:
        """
        Prepare prompt for local LLMs using consistent description.
        Best method for Ollama/LM Studio based on analysis.
        """
        context = self.get_context(project_id)
        
        # Build comprehensive, consistent description every time
        consistent_elements = []
        
        if context.style_guide:
            if 'character' in context.style_guide:
                consistent_elements.append(context.style_guide['character'])
            if 'setting' in context.style_guide:
                consistent_elements.append(f"in {context.style_guide['setting']}")
            if 'cinematic_style' in context.style_guide:
                consistent_elements.append(context.style_guide['cinematic_style'])
        
        base = " ".join(consistent_elements)
        scene_action = scene.prompt or scene.source
        
        if base:
            prompt = f"{base}. {scene_action}"
        else:
            prompt = scene_action
        
        # Add style consistency markers
        if not is_first and context.scene_history:
            prompt += " Maintain consistent character appearance and style from previous scenes."
        
        return prompt
    
    def update_context(self,
                      project_id: str,
                      image: Optional[Image.Image] = None,
                      image_id: Optional[str] = None,
                      prompt: Optional[str] = None,
                      scene_data: Optional[Dict[str, Any]] = None):
        """Update continuity context after generating an image"""
        context = self.get_context(project_id)
        
        if image:
            context.previous_image = image
        if image_id:
            context.previous_image_id = image_id
        if prompt:
            context.previous_prompt = prompt
        if scene_data:
            context.scene_history.append(scene_data)
        
        self.logger.debug(f"Updated context for project {project_id}")
    
    def _build_establishing_prompt(self, scene: Scene, style_guide: Dict[str, str]) -> str:
        """Build a detailed establishing prompt from style guide"""
        elements = []
        
        if 'character' in style_guide:
            elements.append(style_guide['character'])
        
        if 'setting' in style_guide:
            elements.append(f"in {style_guide['setting']}")
        
        # Add scene-specific action
        elements.append(scene.prompt or scene.source)
        
        if 'mood' in style_guide:
            elements.append(f"The mood is {style_guide['mood']}")
        
        if 'cinematic_style' in style_guide:
            elements.append(style_guide['cinematic_style'])
        
        return " ".join(elements)
    
    def _build_incremental_prompt(self, scene: Scene, context: ContinuityContext) -> str:
        """Build an incremental prompt focusing on changes"""
        # Focus on what's changing
        action = scene.prompt or scene.source
        
        # Use transitional phrases for smooth continuity
        transitions = [
            "Now", "Next", "Then", "The camera moves to show",
            "The scene shifts to", "Continuing from before"
        ]
        
        import random
        transition = random.choice(transitions)
        
        return f"{transition}, {action}"
    
    def _build_evolution_prompt(self, scene: Scene, context: ContinuityContext) -> str:
        """Build a prompt that describes evolution from previous scene"""
        if not context.previous_prompt:
            return self._build_establishing_prompt(scene, context.style_guide)
        
        # Describe the change/evolution
        evolution_phrases = [
            "The camera slowly pans to reveal",
            "The expression shifts to",
            "The lighting changes to",
            "Moving forward in time",
            "The scene transitions to"
        ]
        
        import random
        phrase = random.choice(evolution_phrases)
        
        return f"{phrase} {scene.prompt or scene.source}"
    
    def _extract_consistent_elements(self, style_guide: Dict[str, str]) -> str:
        """Extract consistent descriptive elements from style guide"""
        elements = []
        
        if 'character' in style_guide:
            # Extract key descriptors
            character = style_guide['character']
            # Simple extraction of key terms
            if "woman" in character.lower():
                elements.append("woman")
            elif "man" in character.lower():
                elements.append("man")
            
            # Extract appearance details
            import re
            colors = re.findall(r'\b(red|blue|green|brown|black|blonde|auburn)\b', character, re.I)
            if colors:
                elements.extend(colors)
            
            clothing = re.findall(r'\b(dress|suit|coat|shirt|jeans)\b', character, re.I)
            if clothing:
                elements.extend(clothing)
        
        return " ".join(elements) if elements else "character"
    
    def _infer_style_guide(self, scene: Scene) -> Dict[str, str]:
        """Infer a basic style guide from the first scene"""
        # This would ideally use an LLM to analyze the scene
        # For now, return a basic template
        return {
            'character': 'the main subject',
            'setting': 'the scene environment',
            'mood': 'cinematic and engaging',
            'cinematic_style': 'high quality, detailed, professional'
        }
    
    def prepare_aspect_ratio_reference(self, aspect_ratio: str) -> Image.Image:
        """
        Create a blank reference image with the desired aspect ratio.
        Useful for Gemini to maintain aspect ratio.
        """
        aspect_map = {
            '16:9': (1920, 1080),
            '9:16': (1080, 1920),
            '4:3': (1024, 768),
            '3:4': (768, 1024),
            '1:1': (1024, 1024)
        }
        
        width, height = aspect_map.get(aspect_ratio, (1024, 1024))
        
        # Create transparent image
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        self.logger.debug(f"Created {aspect_ratio} reference image: {width}x{height}")
        return img