"""OpenAI provider for image generation."""

from typing import Dict, Any, Optional, Tuple, List
from base64 import b64decode

from .base import ImageProvider

# Lazy import OpenAI
try:
    import importlib
    OpenAIClient = importlib.import_module("openai").OpenAI
except Exception:
    OpenAIClient = None


class OpenAIProvider(ImageProvider):
    """OpenAI DALL-E provider for AI image generation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize OpenAI provider."""
        super().__init__(config)
        self.client = None
        
        if self.api_key and OpenAIClient:
            self.client = OpenAIClient(api_key=self.api_key)
    
    def _ensure_client(self):
        """Ensure OpenAI client is available."""
        if OpenAIClient is None:
            raise ImportError(
                "The 'openai' package is not installed. "
                "Please run: pip install openai"
            )
        
        if not self.client:
            if not self.api_key:
                raise ValueError("OpenAI requires an API key")
            self.client = OpenAIClient(api_key=self.api_key)
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Generate images using OpenAI DALL-E."""
        self._ensure_client()
        
        model = model or self.get_default_model()
        texts: List[str] = []
        images: List[bytes] = []
        
        try:
            # Request base64 to ensure we can save the image bytes locally
            response = self.client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality=quality,
                n=n,
                response_format="b64_json",
            )
            
            data_items = getattr(response, "data", []) or []
            for item in data_items:
                b64 = getattr(item, "b64_json", None)
                if b64:
                    try:
                        images.append(b64decode(b64))
                    except Exception:
                        pass
            
            if not images:
                raise RuntimeError(
                    "OpenAI returned no images. "
                    "Check model name, content policy, or quota."
                )
                
        except Exception as e:
            raise RuntimeError(f"OpenAI generation failed: {e}")
        
        return texts, images
    
    def validate_auth(self) -> Tuple[bool, str]:
        """Validate OpenAI API key."""
        if not self.api_key:
            return False, "No API key configured"
        
        try:
            self._ensure_client()
            
            # Try to list models as a validation check
            models = self.client.models.list()
            return True, "API key is valid"
        except Exception as e:
            return False, f"API key validation failed: {e}"
    
    def get_models(self) -> Dict[str, str]:
        """Get available OpenAI models."""
        return {
            "dall-e-3": "DALL·E 3",
            "dall-e-2": "DALL·E 2",
        }
    
    def get_default_model(self) -> str:
        """Get default OpenAI model."""
        return "dall-e-3"
    
    def get_api_key_url(self) -> str:
        """Get OpenAI API key URL."""
        return "https://platform.openai.com/api-keys"
    
    def get_supported_features(self) -> List[str]:
        """Get supported features."""
        return ["generate", "edit", "variations"]
    
    def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: Optional[str] = None,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
        n: int = 1,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Edit image with OpenAI DALL-E."""
        self._ensure_client()
        
        # Note: DALL-E 2 supports editing, DALL-E 3 does not yet
        model = "dall-e-2"  # Force DALL-E 2 for editing
        texts: List[str] = []
        images: List[bytes] = []
        
        try:
            # OpenAI expects file-like objects
            from io import BytesIO
            image_file = BytesIO(image)
            image_file.name = "image.png"
            
            edit_kwargs = {
                "image": image_file,
                "prompt": prompt,
                "size": size,
                "n": n,
                "response_format": "b64_json",
            }
            
            if mask:
                mask_file = BytesIO(mask)
                mask_file.name = "mask.png"
                edit_kwargs["mask"] = mask_file
            
            response = self.client.images.edit(**edit_kwargs)
            
            data_items = getattr(response, "data", []) or []
            for item in data_items:
                b64 = getattr(item, "b64_json", None)
                if b64:
                    try:
                        images.append(b64decode(b64))
                    except Exception:
                        pass
            
            if not images:
                raise RuntimeError("OpenAI returned no edited images.")
                
        except Exception as e:
            raise RuntimeError(f"OpenAI image editing failed: {e}")
        
        return texts, images
    
    def create_variations(
        self,
        image: bytes,
        model: Optional[str] = None,
        n: int = 1,
        size: str = "1024x1024",
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Create variations of an image."""
        self._ensure_client()
        
        model = "dall-e-2"  # Only DALL-E 2 supports variations
        texts: List[str] = []
        images: List[bytes] = []
        
        try:
            from io import BytesIO
            image_file = BytesIO(image)
            image_file.name = "image.png"
            
            response = self.client.images.create_variation(
                image=image_file,
                n=n,
                size=size,
                response_format="b64_json",
            )
            
            data_items = getattr(response, "data", []) or []
            for item in data_items:
                b64 = getattr(item, "b64_json", None)
                if b64:
                    try:
                        images.append(b64decode(b64))
                    except Exception:
                        pass
            
            if not images:
                raise RuntimeError("OpenAI returned no image variations.")
                
        except Exception as e:
            raise RuntimeError(f"OpenAI variations failed: {e}")
        
        return texts, images