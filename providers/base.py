"""Base provider interface for image generation."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


class ImageProvider(ABC):
    """Abstract base class for image generation providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider.
        
        Args:
            config: Provider configuration including API keys and settings
        """
        self.config = config
        self.api_key = config.get("api_key")
        self.auth_mode = config.get("auth_mode", "api-key")
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Generate content from a text prompt.
        
        Args:
            prompt: Text prompt for generation
            model: Model to use (provider-specific)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Tuple of (text_outputs, image_bytes_list)
        """
        pass
    
    @abstractmethod
    def validate_auth(self) -> Tuple[bool, str]:
        """
        Validate authentication credentials.
        
        Returns:
            Tuple of (is_valid, status_message)
        """
        pass
    
    @abstractmethod
    def get_models(self) -> Dict[str, str]:
        """
        Get available models for this provider.
        
        Returns:
            Dictionary mapping model IDs to display names
        """
        pass
    
    @abstractmethod
    def get_default_model(self) -> str:
        """
        Get the default model for this provider.
        
        Returns:
            Default model ID
        """
        pass
    
    def supports_feature(self, feature: str) -> bool:
        """
        Check if provider supports a specific feature.
        
        Args:
            feature: Feature name (e.g., "edit", "inpaint", "upscale")
        
        Returns:
            True if feature is supported
        """
        return feature in self.get_supported_features()
    
    def get_supported_features(self) -> List[str]:
        """
        Get list of supported features.
        
        Returns:
            List of feature names
        """
        # Override in subclasses to specify features
        return ["generate"]
    
    def get_api_key_url(self) -> str:
        """
        Get URL for obtaining API keys for this provider.
        
        Returns:
            URL string
        """
        return ""
    
    def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Edit an existing image with a text prompt.
        
        Args:
            image: Original image bytes
            prompt: Edit instructions
            model: Model to use
            **kwargs: Additional parameters
        
        Returns:
            Tuple of (text_outputs, edited_image_bytes_list)
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support image editing")
    
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
        raise NotImplementedError(f"{self.__class__.__name__} does not support inpainting")