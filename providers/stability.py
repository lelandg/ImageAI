"""Stability AI provider for Stable Diffusion image generation using REST API."""

import io
import json
import logging
import base64
from typing import Dict, Any, Optional, Tuple, List
import requests
from PIL import Image

from .base import ImageProvider

logger = logging.getLogger(__name__)


class StabilityProvider(ImageProvider):
    """Stability AI provider using REST API."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Stability AI provider.
        
        Args:
            config: Provider configuration including API key
        """
        super().__init__(config)
        self.api_base = "https://api.stability.ai"
        self.model = config.get("model", "stable-diffusion-xl-1024-v1-0")
    
    def get_models(self) -> Dict[str, str]:
        """
        Get available models for this provider.
        
        Returns:
            Dictionary mapping model IDs to display names
        """
        return {
            "stable-diffusion-xl-1024-v1-0": "Stable Diffusion XL 1.0",
            "stable-diffusion-v1-6": "Stable Diffusion 1.6", 
            "stable-diffusion-512-v2-1": "Stable Diffusion 2.1",
            "stable-diffusion-xl-beta-v2-2-2": "Stable Diffusion XL Beta"
        }
    
    def get_default_model(self) -> str:
        """
        Get the default model for this provider.
        
        Returns:
            Default model ID
        """
        return "stable-diffusion-xl-1024-v1-0"
    
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
            URL string
        """
        return "https://platform.stability.ai/account/keys"
    
    def validate_auth(self) -> Tuple[bool, str]:
        """
        Validate authentication credentials.
        
        Returns:
            Tuple of (is_valid, status_message)
        """
        if not self.api_key:
            return False, "Stability AI API key not provided"
        
        try:
            # Test API key by getting account info
            response = requests.get(
                f"{self.api_base}/v1/user/account",
                headers={
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                credits = data.get("credits", 0)
                return True, f"Stability AI authentication successful (Credits: {credits:.2f})"
            elif response.status_code == 401:
                return False, "Invalid API key"
            else:
                return False, f"Authentication failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Authentication check failed: {e}"
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Generate images from a text prompt using REST API.
        
        Args:
            prompt: Text prompt for generation
            model: Model to use (provider-specific)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Tuple of (text_outputs, image_bytes_list)
        """
        if not self.api_key:
            raise RuntimeError("Stability AI API key not provided")
        
        try:
            # Use specified model or default
            selected_model = model or self.model
            
            # Parse parameters
            # Handle size parameter
            size_str = kwargs.get("size", "1024x1024")
            if isinstance(size_str, str) and 'x' in size_str:
                try:
                    width, height = map(int, size_str.split('x'))
                except:
                    width = height = 1024
            else:
                width = kwargs.get("width", 1024)
                height = kwargs.get("height", 1024)
            
            # Adjust sizes based on model
            if selected_model.startswith("stable-diffusion-xl"):
                # SDXL models support 1024x1024
                if width < 1024 or height < 1024:
                    width = height = 1024
            else:
                # SD 1.x/2.x prefer 512x512 or 768x768
                if width > 768 or height > 768:
                    width = height = 512
            
            # Other parameters
            samples = kwargs.get("n", kwargs.get("count", kwargs.get("samples", 1)))
            steps = kwargs.get("steps", kwargs.get("num_inference_steps", 30))
            cfg_scale = kwargs.get("cfg_scale", kwargs.get("guidance_scale", 7.0))
            seed = kwargs.get("seed", 0)  # 0 means random
            
            # Build request body
            body = {
                "text_prompts": [
                    {
                        "text": prompt,
                        "weight": 1.0
                    }
                ],
                "cfg_scale": cfg_scale,
                "height": height,
                "width": width,
                "samples": min(samples, 10),  # API limit
                "steps": steps,
            }
            
            # Add seed if provided
            if seed and seed > 0:
                body["seed"] = seed
            
            # Add negative prompt if provided
            negative_prompt = kwargs.get("negative_prompt")
            if negative_prompt:
                body["text_prompts"].append({
                    "text": negative_prompt,
                    "weight": -1.0
                })
            
            # Make API request
            logger.info(f"Generating {body['samples']} image(s) with Stability AI {selected_model}")
            
            response = requests.post(
                f"{self.api_base}/v1/generation/{selected_model}/text-to-image",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=body
            )
            
            if response.status_code != 200:
                error_msg = f"Generation failed: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = f"{error_msg} - {error_data.get('message', '')}"
                except:
                    error_msg = f"{error_msg} - {response.text}"
                raise RuntimeError(error_msg)
            
            # Process response
            data = response.json()
            artifacts = data.get("artifacts", [])
            
            image_bytes_list = []
            text_outputs = []
            
            for artifact in artifacts:
                if artifact.get("finishReason") == "CONTENT_FILTERED":
                    text_outputs.append("Image was filtered by safety system")
                    continue
                
                # Decode base64 image
                base64_str = artifact.get("base64")
                if base64_str:
                    image_bytes = base64.b64decode(base64_str)
                    image_bytes_list.append(image_bytes)
                    text_outputs.append(f"Generated image ({width}x{height})")
            
            if not image_bytes_list:
                text_outputs.append("No images generated (possibly filtered)")
            
            return text_outputs, image_bytes_list
            
        except Exception as e:
            logger.error(f"Stability AI generation failed: {e}")
            raise RuntimeError(f"Stability AI generation failed: {e}")
    
    def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Edit an existing image with image-to-image.
        
        Args:
            image: Original image bytes
            prompt: Edit instructions
            model: Model to use
            **kwargs: Additional parameters
        
        Returns:
            Tuple of (text_outputs, edited_image_bytes_list)
        """
        if not self.api_key:
            raise RuntimeError("Stability AI API key not provided")
        
        try:
            # Load and prepare image
            input_image = Image.open(io.BytesIO(image))
            if input_image.mode != 'RGB':
                input_image = input_image.convert('RGB')
            
            # Get model
            selected_model = model or self.model
            
            # Resize if needed
            width, height = input_image.size
            if selected_model.startswith("stable-diffusion-xl"):
                max_size = 1024
            else:
                max_size = 512
            
            if max(width, height) > max_size:
                ratio = max_size / max(width, height)
                width = int(width * ratio)
                height = int(height * ratio)
                input_image = input_image.resize((width, height), Image.Resampling.LANCZOS)
            
            # Convert to base64
            img_buffer = io.BytesIO()
            input_image.save(img_buffer, format='PNG')
            init_image_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            # Parameters
            strength = kwargs.get("strength", 0.5)
            steps = kwargs.get("steps", 30)
            cfg_scale = kwargs.get("cfg_scale", 7.0)
            seed = kwargs.get("seed", 0)
            
            # Build request
            body = {
                "text_prompts": [
                    {
                        "text": prompt,
                        "weight": 1.0
                    }
                ],
                "init_image": init_image_base64,
                "init_image_mode": "IMAGE_STRENGTH",
                "image_strength": 1.0 - strength,  # Stability uses inverse
                "cfg_scale": cfg_scale,
                "steps": steps,
                "samples": 1
            }
            
            if seed and seed > 0:
                body["seed"] = seed
            
            logger.info(f"Editing image with Stability AI {selected_model}")
            
            response = requests.post(
                f"{self.api_base}/v1/generation/{selected_model}/image-to-image",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=body
            )
            
            if response.status_code != 200:
                error_msg = f"Edit failed: {response.status_code} - {response.text}"
                raise RuntimeError(error_msg)
            
            # Process response
            data = response.json()
            artifacts = data.get("artifacts", [])
            
            image_bytes_list = []
            text_outputs = []
            
            for artifact in artifacts:
                base64_str = artifact.get("base64")
                if base64_str:
                    image_bytes = base64.b64decode(base64_str)
                    image_bytes_list.append(image_bytes)
                    text_outputs.append(f"Edited image ({width}x{height})")
            
            return text_outputs, image_bytes_list
            
        except Exception as e:
            logger.error(f"Stability AI image editing failed: {e}")
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
        if not self.api_key:
            raise RuntimeError("Stability AI API key not provided")
        
        try:
            # Load images
            input_image = Image.open(io.BytesIO(image))
            mask_image = Image.open(io.BytesIO(mask))
            
            if input_image.mode != 'RGB':
                input_image = input_image.convert('RGB')
            if mask_image.mode != 'L':
                mask_image = mask_image.convert('L')
            
            # Ensure same size
            if input_image.size != mask_image.size:
                mask_image = mask_image.resize(input_image.size, Image.Resampling.LANCZOS)
            
            # Convert to base64
            img_buffer = io.BytesIO()
            input_image.save(img_buffer, format='PNG')
            init_image_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            mask_buffer = io.BytesIO()
            mask_image.save(mask_buffer, format='PNG')
            mask_base64 = base64.b64encode(mask_buffer.getvalue()).decode('utf-8')
            
            # Parameters
            steps = kwargs.get("steps", 30)
            cfg_scale = kwargs.get("cfg_scale", 7.0)
            seed = kwargs.get("seed", 0)
            
            # Build request
            body = {
                "text_prompts": [
                    {
                        "text": prompt,
                        "weight": 1.0
                    }
                ],
                "init_image": init_image_base64,
                "mask_image": mask_base64,
                "cfg_scale": cfg_scale,
                "steps": steps,
                "samples": 1
            }
            
            if seed and seed > 0:
                body["seed"] = seed
            
            selected_model = model or self.model
            logger.info(f"Inpainting image with Stability AI {selected_model}")
            
            response = requests.post(
                f"{self.api_base}/v1/generation/{selected_model}/image-to-image-masking",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=body
            )
            
            if response.status_code != 200:
                error_msg = f"Inpaint failed: {response.status_code} - {response.text}"
                raise RuntimeError(error_msg)
            
            # Process response
            data = response.json()
            artifacts = data.get("artifacts", [])
            
            image_bytes_list = []
            text_outputs = []
            
            for artifact in artifacts:
                base64_str = artifact.get("base64")
                if base64_str:
                    image_bytes = base64.b64decode(base64_str)
                    image_bytes_list.append(image_bytes)
                    text_outputs.append("Inpainted image")
            
            return text_outputs, image_bytes_list
            
        except Exception as e:
            logger.error(f"Stability AI inpainting failed: {e}")
            raise RuntimeError(f"Inpainting failed: {e}")