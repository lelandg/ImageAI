"""
Image generation system for video projects.

This module handles batch image generation for video scenes using the existing
ImageAI providers with concurrency control and caching.
"""

import asyncio
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import time

from providers import get_provider
from .project import Scene
from .event_store import EventStore, ProjectEvent, EventType


class ImageGenerationResult:
    """Result of an image generation operation"""
    
    def __init__(self, scene_id: str, success: bool = True):
        self.scene_id = scene_id
        self.success = success
        self.images: List[bytes] = []
        self.paths: List[Path] = []
        self.error: Optional[str] = None
        self.cost: float = 0.0
        self.duration: float = 0.0
        self.metadata: Dict[str, Any] = {}


class ImageGenerator:
    """Handles batch image generation for video projects"""
    
    def __init__(self, 
                 config: Dict[str, Any],
                 cache_dir: Optional[Path] = None,
                 event_store: Optional[EventStore] = None):
        """
        Initialize image generator.
        
        Args:
            config: Configuration with provider settings
            cache_dir: Directory for caching generated images
            event_store: Event store for tracking generation history
        """
        self.config = config
        self.cache_dir = cache_dir or Path.home() / ".imageai" / "cache" / "video"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.event_store = event_store
        self.logger = logging.getLogger(__name__)
        
        # Concurrency settings
        self.max_concurrent = config.get('concurrent_images', 3)
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent)
    
    def generate_batch(self,
                       scenes: List[Scene],
                       provider: str,
                       model: str,
                       variants_per_scene: int = 3,
                       **generation_kwargs) -> List[ImageGenerationResult]:
        """
        Generate images for multiple scenes in batch.
        
        Args:
            scenes: List of scenes to generate images for
            provider: Provider name (google, openai, stability, local_sd)
            model: Model to use for generation
            variants_per_scene: Number of image variants per scene
            **generation_kwargs: Additional provider-specific arguments
            
        Returns:
            List of generation results
        """
        results = []
        futures = []
        
        # Submit generation tasks
        for scene in scenes:
            if not scene.prompt:
                self.logger.warning(f"Scene {scene.id} has no prompt, skipping")
                continue
            
            future = self.executor.submit(
                self._generate_scene_images,
                scene,
                provider,
                model,
                variants_per_scene,
                **generation_kwargs
            )
            futures.append((scene.id, future))
        
        # Collect results as they complete
        for scene_id, future in futures:
            try:
                result = future.result(timeout=120)  # 2 minute timeout per scene
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to generate images for scene {scene_id}: {e}")
                error_result = ImageGenerationResult(scene_id, success=False)
                error_result.error = str(e)
                results.append(error_result)
        
        return results

    @staticmethod
    def _clean_prompt_for_generation(prompt: str) -> str:
        """
        Clean prompt for image generation by removing scene numbers and lyrics.

        Handles formats like:
        - "**1.** *lyrics* — description" -> "description"
        - "1. lyrics - description" -> "description"

        Args:
            prompt: Original prompt possibly containing scene number and lyrics

        Returns:
            Cleaned prompt with only the visual description
        """
        if not prompt:
            return prompt

        # Pattern: optional bold/italic markdown, number, dot, optional space,
        # optional italic lyrics, em dash or regular dash, then the description
        # Examples:
        # "**1.** *lyrics* — description"
        # "1. lyrics - description"
        # "**5.** *some text here* — A wide shot of..."

        # Try to find em dash (—) or regular dash (-) after potential lyric content
        # Look for: number + dot + (anything) + dash + description
        pattern = r'^(?:\*\*)?(?:\d+)\.(?:\*\*)?\s*(?:\*[^*]*\*)?\s*[—\-]\s*(.+)$'
        match = re.match(pattern, prompt, re.DOTALL)

        if match:
            # Return everything after the dash
            return match.group(1).strip()

        # If no match, return original prompt (backward compatibility)
        return prompt

    def _generate_scene_images(self,
                               scene: Scene,
                               provider: str,
                               model: str,
                               variants: int,
                               **kwargs) -> ImageGenerationResult:
        """
        Generate images for a single scene.
        
        Args:
            scene: Scene to generate images for
            provider: Provider name
            model: Model name
            variants: Number of variants to generate
            **kwargs: Provider-specific arguments
            
        Returns:
            Generation result
        """
        result = ImageGenerationResult(scene.id)
        start_time = time.time()

        try:
            # Clean the prompt before generation (remove scene numbers and lyrics)
            clean_prompt = self._clean_prompt_for_generation(scene.prompt)

            # Check cache first (use clean prompt for cache key)
            cache_key = self._get_cache_key(clean_prompt, provider, model, kwargs)
            cached_images = self._get_cached_images(cache_key, variants)
            
            if cached_images and len(cached_images) >= variants:
                self.logger.info(f"Using cached images for scene {scene.id}")
                result.images = cached_images
                result.paths = self._save_images(scene.id, cached_images)
                result.metadata['from_cache'] = True
                return result
            
            # Get provider instance
            provider_config = {
                'api_key': self._get_api_key(provider),
                'auth_mode': kwargs.get('auth_mode', 'api-key')
            }
            
            provider_instance = get_provider(provider, provider_config)
            
            # Prepare generation parameters
            gen_params = self._prepare_generation_params(provider, model, scene, kwargs)

            # Generate images
            self.logger.info(f"Generating {variants} images for scene {scene.id}")
            self.logger.debug(f"Original prompt: {scene.prompt[:100]}...")
            self.logger.debug(f"Cleaned prompt: {clean_prompt[:100]}...")

            if variants == 1:
                # Single generation
                texts, images = provider_instance.generate(
                    prompt=clean_prompt,
                    model=model,
                    **gen_params
                )
                result.images = images
            else:
                # Multiple generations (some providers don't support n > 1)
                all_images = []
                for i in range(variants):
                    try:
                        # Add variation to prompt for diversity
                        varied_prompt = self._add_prompt_variation(clean_prompt, i)
                        texts, images = provider_instance.generate(
                            prompt=varied_prompt,
                            model=model,
                            **gen_params
                        )
                        all_images.extend(images)
                    except Exception as e:
                        self.logger.warning(f"Failed variant {i+1} for scene {scene.id}: {e}")
                        if not all_images:
                            raise  # Re-raise if no images generated
                
                result.images = all_images[:variants]  # Limit to requested count
            
            # Save images
            result.paths = self._save_images(scene.id, result.images)
            
            # Cache the results
            self._cache_images(cache_key, result.images)
            
            # Track event
            if self.event_store:
                event = ProjectEvent(
                    project_id=scene.project_id if hasattr(scene, 'project_id') else '',
                    event_type=EventType.IMAGE_GENERATED,
                    data={
                        'scene_id': scene.id,
                        'provider': provider,
                        'model': model,
                        'count': len(result.images),
                        'prompt': scene.prompt
                    }
                )
                self.event_store.append(event)
            
            # Calculate cost estimate
            result.cost = self._estimate_cost(provider, model, len(result.images))
            
        except Exception as e:
            self.logger.error(f"Image generation failed for scene {scene.id}: {e}")
            result.success = False
            result.error = str(e)
        
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    def regenerate_scene(self,
                        scene: Scene,
                        provider: str,
                        model: str,
                        preserve_approved: bool = True,
                        **kwargs) -> ImageGenerationResult:
        """
        Regenerate images for a specific scene.
        
        Args:
            scene: Scene to regenerate
            provider: Provider name
            model: Model name
            preserve_approved: Keep approved images
            **kwargs: Generation parameters
            
        Returns:
            Generation result
        """
        # Get current approved images if preserving
        approved_images = []
        if preserve_approved and hasattr(scene, 'approved_images'):
            approved_images = scene.approved_images
        
        # Generate new images
        variants = kwargs.pop('variants', 3)
        result = self._generate_scene_images(scene, provider, model, variants, **kwargs)
        
        # Merge with approved if needed
        if approved_images and result.success:
            result.images = approved_images + result.images
            result.paths = self._save_images(scene.id, result.images)
        
        # Track regeneration event
        if self.event_store and result.success:
            event = ProjectEvent(
                project_id=scene.project_id if hasattr(scene, 'project_id') else '',
                event_type=EventType.IMAGE_REGENERATED,
                data={
                    'scene_id': scene.id,
                    'provider': provider,
                    'model': model,
                    'preserved_count': len(approved_images)
                }
            )
            self.event_store.append(event)
        
        return result
    
    def _get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for provider from config"""
        key_mappings = {
            'google': 'google_api_key',
            'openai': 'openai_api_key',
            'stability': 'stability_api_key',
            'local_sd': None  # No API key needed
        }

        key_field = key_mappings.get(provider)
        if key_field:
            api_key = self.config.get(key_field)
            self.logger.debug(f"Getting API key for provider '{provider}': field='{key_field}', has_key={api_key is not None}, config_keys={list(self.config.keys())}")
            return api_key
        return None
    
    def _prepare_generation_params(self,
                                   provider: str,
                                   model: str,
                                   scene: Scene,
                                   kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare provider-specific generation parameters.
        
        Args:
            provider: Provider name
            model: Model name
            scene: Scene being generated
            kwargs: User-provided parameters
            
        Returns:
            Provider-specific parameters
        """
        params = kwargs.copy()
        
        # Remove our custom parameters
        params.pop('auth_mode', None)
        params.pop('variants', None)
        
        # Add provider-specific defaults
        if provider == 'openai':
            params.setdefault('size', '1024x1024')
            params.setdefault('quality', 'standard')
            params.setdefault('style', 'vivid')
        
        elif provider == 'google':
            params.setdefault('num_images', 1)
            params.setdefault('aspect_ratio', '16:9')
        
        elif provider == 'stability':
            params.setdefault('width', 1024)
            params.setdefault('height', 576)  # 16:9 aspect
            params.setdefault('steps', 30)
            params.setdefault('cfg_scale', 7.0)
        
        elif provider == 'local_sd':
            params.setdefault('width', 1024)
            params.setdefault('height', 576)
            params.setdefault('num_inference_steps', 20)
            params.setdefault('guidance_scale', 7.5)
        
        # Add negative prompt if available
        if hasattr(scene, 'negative_prompt') and scene.negative_prompt:
            params['negative_prompt'] = scene.negative_prompt
        
        return params
    
    def _add_prompt_variation(self, prompt: str, index: int) -> str:
        """Add subtle variation to prompt for diversity"""
        variations = [
            "",  # Original
            ", slight variation",
            ", different angle",
            ", alternative perspective",
            ", unique composition"
        ]
        
        if index < len(variations):
            return prompt + variations[index]
        return prompt
    
    def _get_cache_key(self, prompt: str, provider: str, model: str, params: Dict) -> str:
        """Generate cache key for image lookup"""
        cache_data = {
            'prompt': prompt,
            'provider': provider,
            'model': model,
            'params': {k: v for k, v in params.items() if k not in ['api_key', 'auth_mode']}
        }
        
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()
    
    def _get_cached_images(self, cache_key: str, count: int) -> List[bytes]:
        """Retrieve cached images if available"""
        cache_path = self.cache_dir / cache_key
        if not cache_path.exists():
            return []
        
        images = []
        for i in range(count):
            image_path = cache_path / f"image_{i}.png"
            if image_path.exists():
                images.append(image_path.read_bytes())
            else:
                break
        
        return images
    
    def _cache_images(self, cache_key: str, images: List[bytes]):
        """Cache generated images"""
        cache_path = self.cache_dir / cache_key
        cache_path.mkdir(parents=True, exist_ok=True)
        
        for i, image_data in enumerate(images):
            image_path = cache_path / f"image_{i}.png"
            image_path.write_bytes(image_data)
    
    def _save_images(self, scene_id: str, images: List[bytes]) -> List[Path]:
        """Save images to project directory"""
        paths = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, image_data in enumerate(images):
            filename = f"scene_{scene_id}_{timestamp}_{i}.png"
            # This would normally save to project directory
            # For now, save to cache
            path = self.cache_dir / filename
            path.write_bytes(image_data)
            paths.append(path)
        
        return paths
    
    def _estimate_cost(self, provider: str, model: str, count: int) -> float:
        """Estimate generation cost"""
        # Cost per image in USD (approximate)
        costs = {
            'openai': {
                'dall-e-3': 0.040,
                'dall-e-2': 0.020
            },
            'google': {
                'default': 0.002  # Gemini pricing
            },
            'stability': {
                'default': 0.002  # Stability AI pricing
            },
            'local_sd': {
                'default': 0.0  # Local generation
            }
        }
        
        provider_costs = costs.get(provider, {})
        cost_per_image = provider_costs.get(model, provider_costs.get('default', 0.0))
        
        return cost_per_image * count
    
    def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)