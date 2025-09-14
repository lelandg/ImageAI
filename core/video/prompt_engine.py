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


class PromptStyle(Enum):
    """Available prompt enhancement styles"""
    CINEMATIC = "cinematic"
    ARTISTIC = "artistic"
    PHOTOREALISTIC = "photorealistic"
    ANIMATED = "animated"
    DOCUMENTARY = "documentary"
    ABSTRACT = "abstract"


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
    """
    
    PROVIDER_MODELS = {
        'openai': ['gpt-5-chat-latest', 'gpt-4o', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano'],
        'anthropic': ['claude-opus-4.1', 'claude-opus-4', 'claude-sonnet-4', 'claude-3.7-sonnet', 'claude-3.5-sonnet', 'claude-3.5-haiku'],
        'gemini': ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash', 'gemini-2.0-pro'],
        'ollama': ['llama3.2:latest', 'llama3.1:8b', 'mistral:7b', 'mixtral:8x7b', 'phi3:medium'],
        'lmstudio': ['local-model']  # Uses OpenAI-compatible endpoint
    }
    
    PROVIDER_PREFIXES = {
        'openai': '',  # No prefix needed for OpenAI
        'anthropic': 'claude-opus-4.1',  # Use full model name for default
        'gemini': 'gemini/',
        'ollama': 'ollama/',
        'lmstudio': 'openai/'  # LM Studio uses OpenAI-compatible API
    }
    
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
            self.litellm = litellm
            self.litellm.drop_params = True  # Drop unsupported params
            self.litellm.set_verbose = False  # Reduce logging noise
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
        return self.PROVIDER_MODELS.get(provider, [])
    
    def enhance_prompt(self, 
                      text: str,
                      provider: str,
                      model: str,
                      style: PromptStyle = PromptStyle.CINEMATIC,
                      temperature: float = 0.7,
                      max_tokens: int = 150) -> str:
        """
        Enhance a text prompt using an LLM.
        
        Args:
            text: Original text to enhance
            provider: LLM provider (openai, anthropic, gemini, etc.)
            model: Model name
            style: Style of enhancement
            temperature: Creativity parameter (0-1)
            max_tokens: Maximum tokens in response
            
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
            user_prompt = f"""Create a detailed visual scene description for this lyric line: "{text}"
            
Describe what we should see in the image that represents this lyric visually. Include specific details about:
- The main subject or action
- The setting and environment
- Lighting and mood
- Visual style and composition

Keep it under 100 words but highly descriptive."""
        else:
            user_prompt = f"Transform this into an image generation prompt: {text}"
        
        # Prepare model identifier for LiteLLM
        if provider == 'lmstudio':
            # LM Studio uses OpenAI-compatible API
            model_id = model
            api_base = self.lmstudio_base
        else:
            # Use provider prefix if needed
            prefix = self.PROVIDER_PREFIXES.get(provider, '')
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
            
            # Check if response has content
            if (response and response.choices and len(response.choices) > 0 
                and response.choices[0].message 
                and response.choices[0].message.content):
                enhanced = response.choices[0].message.content.strip()
                
                # If we still got an empty or very short response for a lyric, create a basic visual
                if is_lyric and len(enhanced) < 20:
                    self.logger.warning(f"Got minimal response for lyric, creating basic visual")
                    enhanced = f"A cinematic scene visualizing: {text}. Dramatic lighting, professional photography, high detail."
                
                self.logger.info(f"Enhanced prompt using {provider}/{model}")
                return enhanced
            else:
                self.logger.warning(f"Empty response from {provider}/{model}, creating fallback")
                # For lyrics, create a basic visual description
                if is_lyric:
                    return f"A cinematic scene visualizing: {text}. Dramatic lighting, professional photography, high detail."
                return text
            
        except Exception as e:
            self.logger.error(f"Failed to enhance prompt with {provider}/{model}: {e}")
            # For lyrics, still try to create something visual
            if is_lyric:
                return f"A cinematic scene visualizing: {text}. Dramatic lighting, professional photography, high detail."
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
        
        # For efficiency, try to batch in a single call if provider supports it
        system_prompt = self._get_system_prompt(style)
        
        # Check if these look like lyrics
        avg_words = sum(len(text.split()) for text in texts) / len(texts) if texts else 0
        likely_lyrics = avg_words < 15
        
        # Create a batch prompt
        if likely_lyrics:
            batch_prompt = """Create detailed visual scene descriptions for each lyric line below.
For each line, describe what we should see in the image that represents the lyric visually.
Include specific details about the main subject, setting, lighting, and visual style.
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
                prefix = self.PROVIDER_PREFIXES.get(provider, '')
                model_id = f"{prefix}{model}" if prefix else model
                api_base = None
            
            kwargs = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": batch_prompt}
                ],
                "temperature": temperature,
                "max_tokens": 150 * len(texts)  # Scale max tokens
            }
            
            if api_base:
                kwargs["api_base"] = api_base
            
            response = self.litellm.completion(**kwargs)
            
            # Parse the response
            enhanced_text = response.choices[0].message.content.strip()
            enhanced_lines = enhanced_text.split('\n')
            
            # Extract prompts (skip numbering)
            results = []
            for line in enhanced_lines:
                # Remove numbering like "1. " or "1) "
                import re
                cleaned = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
                if cleaned:
                    results.append(cleaned)
            
            # Ensure we have the right number of results
            while len(results) < len(texts):
                results.append(texts[len(results)])  # Fallback to original
            
            return results[:len(texts)]
            
        except Exception as e:
            self.logger.error(f"Batch enhancement failed: {e}")
            # Fall back to individual enhancement
            return [self.enhance_prompt(text, provider, model, style, temperature) 
                   for text in texts]
    
    def _get_system_prompt(self, style: PromptStyle) -> str:
        """Get system prompt for a given style"""
        prompts = {
            PromptStyle.CINEMATIC: """You are a cinematic prompt engineer. Transform text into detailed image generation prompts with:
- Specific camera angles (wide shot, close-up, aerial, etc.)
- Lighting descriptions (golden hour, dramatic shadows, soft lighting)
- Cinematic elements (depth of field, lens type, film grain)
- Mood and atmosphere
- Visual composition
Keep prompts under 100 words but highly descriptive.""",
            
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
Keep prompts open to interpretation and artistic."""
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