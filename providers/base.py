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
                     Common kwargs:
                     - reference_image: bytes or Path - Reference image for style/composition
                     - reference_strength: float (0.0-1.0) - How much to follow reference
                     - Other provider-specific parameters

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

    def get_model_auth_requirements(self, model: str) -> Dict[str, Any]:
        """
        Get authentication requirements for a specific model.

        Override in subclasses to specify model-specific auth requirements.
        This is the SINGLE SOURCE OF TRUTH for model auth requirements.

        Args:
            model: Model ID to check

        Returns:
            Dict with:
            - requires_api_key: bool - True if model ONLY works with API key (not gcloud)
            - requires_gcloud: bool - True if model ONLY works with gcloud (not API key)
            - display_name: str - Human-readable model name for error messages
            - error_message: str - Message to show if requirements not met
        """
        # Default: models support both auth methods
        return {
            'requires_api_key': False,
            'requires_gcloud': False,
            'display_name': model,
            'error_message': ''
        }

    def check_model_auth(self, model: str) -> Tuple[bool, str]:
        """
        Check if current auth mode supports the given model.

        This method should be called at the start of generate() to enforce
        model-specific auth requirements consistently across GUI and CLI.

        Args:
            model: Model ID to check

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if current auth mode supports the model
            - error_message: Empty string if valid, otherwise describes the issue
        """
        requirements = self.get_model_auth_requirements(model)

        # If model requires API key but we're in gcloud mode
        if requirements.get('requires_api_key') and self.auth_mode == "gcloud":
            return False, requirements.get('error_message', f"Model {model} requires API key authentication")

        # If model requires gcloud but we're in api-key mode
        if requirements.get('requires_gcloud') and self.auth_mode != "gcloud":
            return False, requirements.get('error_message', f"Model {model} requires Google Cloud authentication")

        return True, ""

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

    def _load_reference_image(self, reference_image) -> Optional[bytes]:
        """
        Load reference image from path or bytes.

        Args:
            reference_image: Path, str, or bytes of reference image

        Returns:
            Image bytes or None if not provided
        """
        if reference_image is None:
            return None

        if isinstance(reference_image, bytes):
            return reference_image

        # Handle Path or str
        ref_path = Path(reference_image) if not isinstance(reference_image, Path) else reference_image
        if ref_path.exists():
            with open(ref_path, 'rb') as f:
                return f.read()

        return None