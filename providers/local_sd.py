"""Local Stable Diffusion provider using Hugging Face Diffusers."""

import io
import gc
import logging
import warnings
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from PIL import Image
from .base import ImageProvider
from .model_info import ModelInfo

logger = logging.getLogger(__name__)

# Try to import ML dependencies
try:
    import torch
    import psutil
    from diffusers import (
        StableDiffusionPipeline,
        StableDiffusionXLPipeline,
        DiffusionPipeline,
        AutoencoderKL,
    )
    from diffusers.utils import logging as diffusers_logging
    from huggingface_hub import snapshot_download
    
    # Suppress diffusers warnings by default
    diffusers_logging.set_verbosity_error()
    warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
    
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    torch = None
    psutil = None


class DeviceManager:
    """Manages device detection and memory optimization."""
    
    def __init__(self):
        if not ML_AVAILABLE:
            self.device = "cpu"
            self.dtype = None
            self.memory_info = {}
            return
            
        self.device = self._detect_best_device()
        self.dtype = self._get_optimal_dtype()
        self.memory_info = self._get_memory_info()
        
    def _detect_best_device(self) -> str:
        """Detect the best available device for inference."""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"  # Apple Silicon
        else:
            return "cpu"
    
    def _get_optimal_dtype(self):
        """Get optimal data type based on device."""
        if self.device == "cuda":
            return torch.float16  # Use half precision on GPU
        elif self.device == "mps":
            return torch.float32  # MPS doesn't support float16 well
        else:
            return torch.float32  # Use full precision on CPU
    
    def _get_memory_info(self) -> Dict[str, float]:
        """Get available memory information."""
        info = {}
        
        # System RAM
        if psutil:
            system_memory = psutil.virtual_memory()
            info['system_total_gb'] = system_memory.total / (1024**3)
            info['system_available_gb'] = system_memory.available / (1024**3)
        else:
            info['system_total_gb'] = 0
            info['system_available_gb'] = 0
        
        # GPU memory
        if self.device == "cuda" and torch:
            gpu_memory = torch.cuda.get_device_properties(0).total_memory
            info['gpu_total_gb'] = gpu_memory / (1024**3)
            info['gpu_allocated_gb'] = torch.cuda.memory_allocated(0) / (1024**3)
        else:
            info['gpu_total_gb'] = 0
            info['gpu_allocated_gb'] = 0
            
        return info
    
    def should_use_cpu_offload(self) -> bool:
        """Determine if CPU offloading should be used."""
        if self.device == "cuda":
            return self.memory_info.get('gpu_total_gb', 0) < 8.0
        return False
    
    def should_use_attention_slicing(self) -> bool:
        """Determine if attention slicing should be used."""
        if self.device == "cuda":
            return self.memory_info.get('gpu_total_gb', 0) < 6.0
        return self.device == "cpu"


class LocalSDProvider(ImageProvider):
    """Local Stable Diffusion provider using Hugging Face Diffusers."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Local SD provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        
        self.model_id = config.get("model", "stabilityai/stable-diffusion-2-1")
        self.cache_dir = config.get("cache_dir", Path.home() / ".cache" / "huggingface")
        self.device_manager = DeviceManager() if ML_AVAILABLE else None
        self.pipeline = None
        self.current_model = None
        
        # Memory optimization settings
        self.use_cpu_offload = config.get("cpu_offload", 
                                         self.device_manager.should_use_cpu_offload() if self.device_manager else False)
        self.use_attention_slicing = config.get("attention_slicing",
                                               self.device_manager.should_use_attention_slicing() if self.device_manager else True)
    
    def get_models(self) -> Dict[str, str]:
        """
        Get available models for this provider.
        
        Returns:
            Dictionary mapping model IDs to display names
        """
        models = {}
        
        # Add installed models first
        installed = ModelInfo.get_installed_models(self.cache_dir)
        for model_id in installed:
            # Check if it's a known model
            if model_id in ModelInfo.POPULAR_MODELS:
                name = ModelInfo.POPULAR_MODELS[model_id]["name"]
                models[model_id] = f"✓ {name}"
            else:
                # Unknown/custom model
                models[model_id] = f"✓ {model_id}"
        
        # Add popular models that aren't installed
        for model_id, info in ModelInfo.POPULAR_MODELS.items():
            if model_id not in models:
                models[model_id] = info["name"]
        
        # Add custom option
        models["custom"] = "Custom Model (specify in settings)"
        
        return models
    
    def get_default_model(self) -> str:
        """
        Get the default model for this provider.
        
        Returns:
            Default model ID
        """
        return "stabilityai/stable-diffusion-2-1"
    
    def get_supported_features(self) -> List[str]:
        """
        Get list of supported features.
        
        Returns:
            List of feature names
        """
        return ["generate", "edit", "inpaint"]
    
    def get_api_key_url(self) -> str:
        """
        Get URL for obtaining API keys for this provider.
        
        Returns:
            URL string (empty for local provider)
        """
        return ""  # No API key needed for local models
    
    def validate_auth(self) -> Tuple[bool, str]:
        """
        Validate that ML dependencies are installed.
        
        Returns:
            Tuple of (is_valid, status_message)
        """
        if not ML_AVAILABLE:
            return False, ("Local SD dependencies not installed. Install with:\n"
                         "pip install -r requirements-local-sd.txt")
        
        device_info = f"Device: {self.device_manager.device}"
        if self.device_manager.device == "cuda":
            device_info += f" (GPU: {self.device_manager.memory_info['gpu_total_gb']:.1f}GB)"
        elif self.device_manager.device == "mps":
            device_info += " (Apple Silicon)"
        
        return True, f"Local SD ready. {device_info}"
    
    def _load_pipeline(self, model_id: str = None):
        """Load or switch the diffusion pipeline."""
        if not ML_AVAILABLE:
            raise RuntimeError("Local SD dependencies not installed")
        
        model_to_load = model_id or self.model_id
        
        # Skip if already loaded
        if self.pipeline and self.current_model == model_to_load:
            return
        
        # Clear previous pipeline
        if self.pipeline:
            del self.pipeline
            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
        
        logger.info(f"Loading model: {model_to_load}")
        
        try:
            # Determine pipeline class based on model
            if "xl" in model_to_load.lower() or "sdxl" in model_to_load.lower():
                pipeline_class = StableDiffusionXLPipeline
            else:
                pipeline_class = StableDiffusionPipeline
            
            # Load pipeline
            self.pipeline = pipeline_class.from_pretrained(
                model_to_load,
                torch_dtype=self.device_manager.dtype,
                cache_dir=self.cache_dir,
                use_safetensors=True,
                safety_checker=None,  # Disable safety checker for performance
                requires_safety_checker=False,
            )
            
            # Move to device
            if self.use_cpu_offload and self.device_manager.device == "cuda":
                self.pipeline.enable_model_cpu_offload()
            else:
                self.pipeline = self.pipeline.to(self.device_manager.device)
            
            # Enable memory optimizations
            if self.use_attention_slicing:
                self.pipeline.enable_attention_slicing()
            
            # Enable xformers if available
            if hasattr(self.pipeline, 'enable_xformers_memory_efficient_attention'):
                try:
                    self.pipeline.enable_xformers_memory_efficient_attention()
                except Exception:
                    pass  # xformers not available
            
            self.current_model = model_to_load
            logger.info(f"Model loaded successfully on {self.device_manager.device}")
            
        except Exception as e:
            logger.error(f"Failed to load model {model_to_load}: {e}")
            raise RuntimeError(f"Failed to load model: {e}")
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Generate images from a text prompt.
        
        Args:
            prompt: Text prompt for generation
            model: Model to use (provider-specific)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Tuple of (text_outputs, image_bytes_list)
        """
        if not ML_AVAILABLE:
            raise RuntimeError("Local SD dependencies not installed")
        
        # Load pipeline if needed
        self._load_pipeline(model)
        
        # Check if this is a Turbo model for optimizations
        is_turbo = 'turbo' in self.current_model.lower()
        
        # Extract parameters with Turbo-specific defaults
        width = kwargs.get("width", 512)
        height = kwargs.get("height", 512)
        num_images = kwargs.get("count", 1)
        
        # Turbo models use very few steps and no CFG
        if is_turbo:
            num_inference_steps = kwargs.get("steps", 2)  # 1-4 steps for turbo
            guidance_scale = kwargs.get("cfg_scale", 0.0)  # No CFG for turbo
        else:
            num_inference_steps = kwargs.get("steps", 20)  # Reduced from 50 for better speed
            guidance_scale = kwargs.get("cfg_scale", 7.5)
        
        negative_prompt = kwargs.get("negative_prompt", None)
        seed = kwargs.get("seed", None)
        
        # Adjust sizes based on model (only if not explicitly set)
        if width == 512 and height == 512:  # Default value, can auto-adjust
            if "xl" in self.current_model.lower():
                # SDXL models prefer 1024x1024
                width = height = 1024
            elif "2." in self.current_model or "2-" in self.current_model:
                # SD 2.x can handle 768x768 well
                width = height = 768
        
        # Set seed if provided
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device_manager.device).manual_seed(seed)
        
        try:
            if is_turbo:
                logger.info(f"Generating with TURBO model: {num_images} image(s) at {width}x{height}, steps={num_inference_steps}, cfg={guidance_scale}")
            else:
                logger.info(f"Generating {num_images} image(s) at {width}x{height}, steps={num_inference_steps}, cfg={guidance_scale}")
            
            # Generate images
            result = self.pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                num_images_per_prompt=num_images,
                generator=generator,
            )
            
            # Convert images to bytes
            image_bytes_list = []
            text_outputs = []
            
            for i, image in enumerate(result.images):
                # Convert PIL image to bytes
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='PNG')
                image_bytes_list.append(img_buffer.getvalue())
                text_outputs.append(f"Generated image {i+1} ({width}x{height})")
            
            logger.info(f"Successfully generated {len(image_bytes_list)} image(s)")
            return text_outputs, image_bytes_list
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise RuntimeError(f"Generation failed: {e}")
    
    def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Edit an existing image with a text prompt (img2img).
        
        Args:
            image: Original image bytes
            prompt: Edit instructions
            model: Model to use
            **kwargs: Additional parameters
        
        Returns:
            Tuple of (text_outputs, edited_image_bytes_list)
        """
        if not ML_AVAILABLE:
            raise RuntimeError("Local SD dependencies not installed")
        
        # For img2img, we need to use a different pipeline
        # For simplicity, we'll use the same pipeline with init_image
        self._load_pipeline(model)
        
        # Load input image
        init_image = Image.open(io.BytesIO(image))
        if init_image.mode != 'RGB':
            init_image = init_image.convert('RGB')
        
        # Extract parameters
        strength = kwargs.get("strength", 0.75)
        num_inference_steps = kwargs.get("steps", 50)
        guidance_scale = kwargs.get("cfg_scale", 7.5)
        negative_prompt = kwargs.get("negative_prompt", None)
        seed = kwargs.get("seed", None)
        
        # Resize image if needed
        width, height = init_image.size
        if "xl" in self.current_model.lower():
            max_size = 1024
        else:
            max_size = 768
        
        if max(width, height) > max_size:
            ratio = max_size / max(width, height)
            width = int(width * ratio)
            height = int(height * ratio)
            init_image = init_image.resize((width, height), Image.Resampling.LANCZOS)
        
        # Set seed if provided
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device_manager.device).manual_seed(seed)
        
        try:
            # Use img2img if available
            if hasattr(self.pipeline, 'img2img'):
                result = self.pipeline.img2img(
                    prompt=prompt,
                    image=init_image,
                    strength=strength,
                    negative_prompt=negative_prompt,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    generator=generator,
                )
            else:
                # Fallback to regular generation with init image
                result = self.pipeline(
                    prompt=prompt,
                    image=init_image,
                    strength=strength,
                    negative_prompt=negative_prompt,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    generator=generator,
                )
            
            # Convert result to bytes
            img_buffer = io.BytesIO()
            result.images[0].save(img_buffer, format='PNG')
            
            return [f"Edited image ({width}x{height})"], [img_buffer.getvalue()]
            
        except Exception as e:
            logger.error(f"Image editing failed: {e}")
            raise RuntimeError(f"Image editing failed: {e}")
    
    def inpaint(
        self,
        image: bytes,
        mask: bytes,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Inpaint masked regions of an image.
        
        Args:
            image: Original image bytes
            mask: Mask image bytes (white = inpaint region)
            prompt: Description of what to inpaint
            model: Model to use
            **kwargs: Additional parameters
        
        Returns:
            Tuple of (text_outputs, inpainted_image_bytes_list)
        """
        if not ML_AVAILABLE:
            raise RuntimeError("Local SD dependencies not installed")
        
        # Note: Proper inpainting requires a specialized pipeline
        # For now, we'll use img2img with the mask as a guide
        # This is a simplified implementation
        
        # Load images
        init_image = Image.open(io.BytesIO(image))
        mask_image = Image.open(io.BytesIO(mask))
        
        if init_image.mode != 'RGB':
            init_image = init_image.convert('RGB')
        if mask_image.mode != 'L':
            mask_image = mask_image.convert('L')
        
        # For basic inpainting simulation, blend the prompt-generated content
        # This is a placeholder - proper inpainting needs StableDiffusionInpaintPipeline
        return self.edit_image(image, prompt, model, **kwargs)