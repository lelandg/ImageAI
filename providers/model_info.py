"""Model information utilities for Local SD provider."""

import os
from pathlib import Path
from typing import Dict, List


class ModelInfo:
    """Information about Stable Diffusion models."""
    
    POPULAR_MODELS = {
        "runwayml/stable-diffusion-v1-5": {
            "name": "Stable Diffusion 1.5",
            "description": "The classic SD 1.5 model. Balanced quality and speed.",
            "size_gb": 4.2,
            "recommended": True,
            "tags": ["general", "fast", "768x768"],
            "url": "https://huggingface.co/runwayml/stable-diffusion-v1-5"
        },
        "stabilityai/stable-diffusion-2-1": {
            "name": "Stable Diffusion 2.1",
            "description": "Improved version with better faces and hands.",
            "size_gb": 5.2,
            "recommended": True,
            "tags": ["general", "quality", "768x768"],
            "url": "https://huggingface.co/stabilityai/stable-diffusion-2-1"
        },
        "stabilityai/stable-diffusion-xl-base-1.0": {
            "name": "SDXL Base 1.0",
            "description": "High quality 1024x1024 images. Requires more VRAM.",
            "size_gb": 6.9,
            "recommended": False,
            "tags": ["quality", "1024x1024", "high-vram"],
            "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0"
        },
        "segmind/SSD-1B": {
            "name": "SSD-1B (Fast SDXL)",
            "description": "50% smaller and 60% faster than SDXL with similar quality.",
            "size_gb": 3.5,
            "recommended": True,
            "tags": ["fast", "1024x1024", "efficient"],
            "url": "https://huggingface.co/segmind/SSD-1B"
        },
        "CompVis/stable-diffusion-v1-4": {
            "name": "Stable Diffusion 1.4",
            "description": "Original stable diffusion model. Good for older GPUs.",
            "size_gb": 4.0,
            "recommended": False,
            "tags": ["classic", "512x512", "low-vram"],
            "url": "https://huggingface.co/CompVis/stable-diffusion-v1-4"
        },
        "dreamlike-art/dreamlike-diffusion-1.0": {
            "name": "Dreamlike Diffusion 1.0",
            "description": "Fine-tuned for artistic and dreamlike images.",
            "size_gb": 4.2,
            "recommended": False,
            "tags": ["artistic", "stylized", "512x512"],
            "url": "https://huggingface.co/dreamlike-art/dreamlike-diffusion-1.0"
        },
        "prompthero/openjourney": {
            "name": "OpenJourney",
            "description": "Fine-tuned on Midjourney v4 style images.",
            "size_gb": 4.2,
            "recommended": False,
            "tags": ["artistic", "midjourney-style", "512x512"],
            "url": "https://huggingface.co/prompthero/openjourney"
        },
        "stabilityai/stable-diffusion-xl-refiner-1.0": {
            "name": "SDXL Refiner 1.0",
            "description": "Refiner model for SDXL. Use with SDXL Base for best results.",
            "size_gb": 6.9,
            "recommended": False,
            "tags": ["refiner", "1024x1024", "high-vram"],
            "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-refiner-1.0"
        },
        "stabilityai/sdxl-turbo": {
            "name": "SDXL Turbo",
            "description": "Ultra-fast SDXL model. Generates high-quality images in 1-4 steps.",
            "size_gb": 6.9,
            "recommended": True,
            "tags": ["ultra-fast", "1024x1024", "1-4-steps"],
            "url": "https://huggingface.co/stabilityai/sdxl-turbo"
        }
    }
    
    @classmethod
    def get_installed_models(cls, cache_dir: Path) -> List[str]:
        """Get list of installed model IDs (only image generation models)."""
        installed = []
        models_dir = cache_dir / "hub"
        
        # Keywords that indicate non-image-generation models
        exclude_keywords = [
            'depth', 'segmentation', 'detection', 'classification',
            'recognition', 'parsing', 'pose', 'tracking', 'inpainting-only',
            'super-resolution', 'upscale', 'restore', 'enhance'
        ]
        
        if models_dir.exists():
            for item in models_dir.iterdir():
                if item.is_dir() and "models--" in item.name:
                    # Extract model ID from cache folder name
                    model_id = item.name.replace("models--", "").replace("--", "/")
                    
                    # Filter out non-generation models
                    model_lower = model_id.lower()
                    if any(keyword in model_lower for keyword in exclude_keywords):
                        continue
                    
                    # Check if it's a known SD/diffusion model or contains relevant keywords
                    if ('stable-diffusion' in model_lower or 
                        'sdxl' in model_lower or
                        'diffusion' in model_lower or
                        'dreamlike' in model_lower or
                        'openjourney' in model_lower or
                        'midjourney' in model_lower or
                        model_id in cls.POPULAR_MODELS):
                        installed.append(model_id)
        
        return installed
    
    @classmethod
    def is_model_installed(cls, model_id: str, cache_dir: Path) -> bool:
        """Check if a model is installed."""
        # Check if model folder exists in cache
        safe_model_id = model_id.replace("/", "--")
        model_path = cache_dir / "hub" / f"models--{safe_model_id}"
        return model_path.exists()
    
    @classmethod
    def get_model_size(cls, model_id: str, cache_dir: Path) -> float:
        """Get the size of an installed model in GB."""
        safe_model_id = model_id.replace("/", "--")
        model_path = cache_dir / "hub" / f"models--{safe_model_id}"
        
        if not model_path.exists():
            return 0.0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(model_path):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if filepath.exists():
                    total_size += filepath.stat().st_size
        
        return total_size / (1024**3)  # Convert to GB