"""Worker threads for GUI operations."""

from typing import Optional, Tuple, List
from PySide6.QtCore import QObject, Signal

from core import ConfigManager
from providers import get_provider


class GenWorker(QObject):
    """Worker thread for image generation."""

    progress = Signal(str)
    error = Signal(str)
    finished = Signal(list, list)  # (texts, images)
    
    def __init__(self, provider: str, model: str, prompt: str, auth_mode: str = "api-key", **kwargs):
        super().__init__()
        self.provider = provider
        self.model = model
        self.prompt = prompt
        self.auth_mode = auth_mode
        self.kwargs = kwargs  # Additional parameters like width, height, steps, etc.
    
    def run(self):
        """Run image generation in worker thread."""
        try:
            self.progress.emit(f"Generating with {self.provider} ({self.model})...")
            
            # Get configuration
            config = ConfigManager()
            api_key = config.get_api_key(self.provider) if self.auth_mode == "api-key" else None
            
            # Create provider config
            provider_config = {
                "api_key": api_key,
                "auth_mode": self.auth_mode,
            }
            
            # Get provider and generate
            provider_instance = get_provider(self.provider, provider_config)
            texts, images = provider_instance.generate(
                prompt=self.prompt,
                model=self.model,
                **self.kwargs  # Pass additional parameters
            )

            self.finished.emit(texts, images)
            
        except Exception as e:
            self.error.emit(str(e))