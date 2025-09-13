"""
Simple helper to add continuity support to existing image generation.
Works alongside the existing workflow without breaking it.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path


class ContinuityHelper:
    """Helper class to add continuity hints to prompts"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.previous_prompts = {}
        self.style_guides = {}
    
    def enhance_prompt_for_continuity(self, 
                                     prompt: str,
                                     scene_index: int,
                                     project_id: str,
                                     provider: str,
                                     aspect_ratio: Optional[str] = None) -> str:
        """
        Enhance a prompt with continuity hints based on provider.
        
        This is a simple addition that doesn't break existing prompts.
        """
        
        # For Gemini, add aspect ratio to prompt if specified
        if provider.lower() == 'gemini' and aspect_ratio:
            if aspect_ratio not in prompt:
                prompt += f" The image should be in {aspect_ratio} format."
        
        # For subsequent scenes, add continuity hints
        if scene_index > 0 and project_id in self.previous_prompts:
            if provider.lower() == 'openai':
                # DALL-E 3 approach: emphasize consistency
                prompt = f"Continuing from the previous scene, {prompt}"
            elif provider.lower() == 'gemini':
                # Gemini approach: reference previous
                prompt = f"Next in the sequence, {prompt}"
        
        # Store for next scene
        if project_id not in self.previous_prompts:
            self.previous_prompts[project_id] = []
        self.previous_prompts[project_id].append(prompt)
        
        return prompt
    
    def set_style_guide(self, project_id: str, style_guide: Dict[str, str]):
        """Store style guide for a project"""
        self.style_guides[project_id] = style_guide
    
    def get_style_prefix(self, project_id: str) -> str:
        """Get a style prefix based on stored style guide"""
        if project_id not in self.style_guides:
            return ""
        
        guide = self.style_guides[project_id]
        elements = []
        
        if 'character' in guide:
            elements.append(guide['character'])
        if 'cinematic_style' in guide:
            elements.append(guide['cinematic_style'])
        
        return ", ".join(elements) + ". " if elements else ""
    
    def clear_project(self, project_id: str):
        """Clear stored data for a project"""
        if project_id in self.previous_prompts:
            del self.previous_prompts[project_id]
        if project_id in self.style_guides:
            del self.style_guides[project_id]


# Global instance for easy access
_continuity_helper = None


def get_continuity_helper() -> ContinuityHelper:
    """Get the global continuity helper instance"""
    global _continuity_helper
    if _continuity_helper is None:
        _continuity_helper = ContinuityHelper()
    return _continuity_helper