"""Ollama provider for image generation using local models."""

import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple, List
from .base import ImageProvider

logger = logging.getLogger(__name__)


class OllamaProvider(ImageProvider):
    """Provider for Ollama local image generation models."""

    # Vision/multimodal models that support image generation
    VISION_MODELS = {
        'llava', 'llava-llama3', 'llava-phi3', 'llava-v1.6',
        'bakllava', 'moondream', 'dolphin-llama3',
        'dolphin-mixtral', 'dolphin-phi', 'dolphin'
    }

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Ollama provider.

        Args:
            config: Provider configuration (endpoint optional)
        """
        super().__init__(config)
        self.endpoint = config.get("endpoint", "http://localhost:11434")
        self.api_key = None  # Ollama doesn't require API keys
        self._cached_models = None
        logger.info(f"Initialized Ollama provider with endpoint: {self.endpoint}")

    def _is_vision_model(self, model_name: str) -> bool:
        """
        Check if a model supports vision/image generation.

        Args:
            model_name: Model name to check

        Returns:
            True if model supports vision tasks
        """
        model_lower = model_name.lower()
        return any(vision_model in model_lower for vision_model in self.VISION_MODELS)

    def _fetch_installed_models(self) -> Dict[str, str]:
        """
        Fetch installed models from Ollama server.

        Returns:
            Dictionary mapping model IDs to display names
        """
        try:
            response = requests.get(f"{self.endpoint}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()

            models = {}
            if "models" in data:
                for model_info in data["models"]:
                    model_name = model_info.get("name", "")
                    if model_name:
                        # Create display name with size info if available
                        size_info = ""
                        if "details" in model_info:
                            param_size = model_info["details"].get("parameter_size", "")
                            if param_size:
                                size_info = f" ({param_size})"

                        display_name = f"{model_name}{size_info}"
                        models[model_name] = display_name

                        logger.debug(f"Found Ollama model: {model_name} - {display_name}")

            logger.info(f"Detected {len(models)} Ollama models")
            return models

        except requests.exceptions.ConnectionError:
            logger.warning(f"Could not connect to Ollama at {self.endpoint}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching Ollama models: {e}")
            return {}

    def get_models(self) -> Dict[str, str]:
        """
        Get available models for this provider.

        Returns:
            Dictionary mapping model IDs to display names
        """
        if self._cached_models is None:
            self._cached_models = self._fetch_installed_models()

        # If no models detected, return empty dict
        if not self._cached_models:
            logger.warning("No Ollama models detected. Make sure Ollama is running.")
            return {}

        return self._cached_models

    def get_default_model(self) -> str:
        """
        Get the default model for this provider.

        Returns:
            Default model ID
        """
        models = self.get_models()

        if not models:
            return "llava:latest"  # Fallback

        # Prefer vision models
        for model_id in models.keys():
            if self._is_vision_model(model_id):
                return model_id

        # Return first available model
        return list(models.keys())[0]

    def validate_auth(self) -> Tuple[bool, str]:
        """
        Validate connection to Ollama server.

        Returns:
            Tuple of (is_valid, status_message)
        """
        try:
            response = requests.get(f"{self.endpoint}/api/tags", timeout=5)
            response.raise_for_status()

            models = self.get_models()
            if not models:
                return False, "Ollama is running but no models are installed"

            model_count = len(models)
            vision_count = sum(1 for m in models.keys() if self._is_vision_model(m))

            return True, (f"Connected to Ollama - {model_count} models available "
                         f"({vision_count} vision-capable)")

        except requests.exceptions.ConnectionError:
            return False, f"Could not connect to Ollama at {self.endpoint}"
        except Exception as e:
            return False, f"Error connecting to Ollama: {str(e)}"

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Generate image from text prompt using Ollama.

        Note: Ollama models typically generate descriptions rather than images.
        This method sends the prompt to the model and returns the text response.
        For actual image generation, you would need to use image generation models
        like Stable Diffusion through Ollama's API.

        Args:
            prompt: Text prompt for generation
            model: Model to use (defaults to default_model)
            **kwargs: Additional parameters (temperature, etc.)

        Returns:
            Tuple of (text_outputs, empty_image_list)
        """
        if model is None:
            model = self.get_default_model()

        # Check if model is available
        available_models = self.get_models()
        if not available_models:
            raise ValueError("No Ollama models available. Please install models with 'ollama pull <model>'")

        if model not in available_models:
            raise ValueError(f"Model '{model}' not found. Available: {', '.join(available_models.keys())}")

        logger.info(f"Generating with Ollama model: {model}")
        logger.debug(f"Prompt: {prompt[:100]}...")

        # Prepare request
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }

        # Add optional parameters
        options = {}
        if "temperature" in kwargs:
            options["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            options["num_predict"] = kwargs["max_tokens"]

        if options:
            payload["options"] = options

        try:
            response = requests.post(
                f"{self.endpoint}/api/generate",
                json=payload,
                timeout=120  # Longer timeout for generation
            )
            response.raise_for_status()

            result = response.json()
            text_output = result.get("response", "")

            if not text_output:
                raise ValueError("Empty response from Ollama")

            logger.info(f"Generated response: {len(text_output)} characters")
            logger.debug(f"Response preview: {text_output[:200]}...")

            # Ollama text models don't generate images, return text only
            # For actual image generation, you'd need a different endpoint/model
            return [text_output], []

        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Could not connect to Ollama at {self.endpoint}")
        except requests.exceptions.Timeout:
            raise TimeoutError("Ollama generation timed out")
        except Exception as e:
            logger.error(f"Error generating with Ollama: {e}")
            raise

    def get_supported_features(self) -> List[str]:
        """
        Get list of supported features.

        Returns:
            List of feature names
        """
        return ["generate", "text-generation"]

    def get_api_key_url(self) -> str:
        """
        Get URL for Ollama documentation.

        Returns:
            Documentation URL
        """
        return "https://ollama.ai/library"

    def refresh_models(self):
        """Refresh the cached model list."""
        self._cached_models = None
        return self.get_models()
