"""Worker threads for GUI operations."""

from typing import Optional, Tuple, List
from pathlib import Path
from PySide6.QtCore import QObject, Signal

from core import ConfigManager
from core.utils import read_image_sidecar
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

            # Add Midjourney-specific configuration
            if self.provider == "midjourney":
                provider_config.update({
                    "use_discord": config.get("midjourney_use_discord", False),
                    "discord_server_id": config.get("midjourney_discord_server", ""),
                    "discord_channel_id": config.get("midjourney_discord_channel", ""),
                    "open_in_external_browser": config.get("midjourney_external_browser", False),
                })
            
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


class HistoryLoaderWorker(QObject):
    """Worker thread for progressive history loading."""

    progress = Signal(int, int)  # (loaded_count, total_count)
    batch_loaded = Signal(list)  # List of history items
    finished = Signal()
    error = Signal(str)

    def __init__(self, history_paths: List[Path], start_index: int = 0, batch_size: int = 25):
        super().__init__()
        self.history_paths = history_paths
        self.start_index = start_index
        self.batch_size = batch_size
        self._stop_requested = False

    def stop(self):
        """Request the worker to stop loading."""
        self._stop_requested = True

    def run(self):
        """Load history metadata in batches."""
        try:
            total = len(self.history_paths)
            current_index = self.start_index

            while current_index < total and not self._stop_requested:
                # Load next batch
                end_index = min(current_index + self.batch_size, total)
                batch_items = []

                for path in self.history_paths[current_index:end_index]:
                    if self._stop_requested:
                        break

                    try:
                        # Try to read sidecar file for metadata
                        sidecar = read_image_sidecar(path)
                        if sidecar:
                            history_entry = {
                                'path': path,
                                'prompt': sidecar.get('prompt', ''),
                                'timestamp': sidecar.get('timestamp', path.stat().st_mtime),
                                'model': sidecar.get('model', ''),
                                'provider': sidecar.get('provider', ''),
                                'width': sidecar.get('width', ''),
                                'height': sidecar.get('height', ''),
                                'num_images': sidecar.get('num_images', 1),
                                'quality': sidecar.get('quality', ''),
                                'style': sidecar.get('style', ''),
                                'cost': sidecar.get('cost', 0.0)
                            }
                            # Include reference images if present in sidecar
                            if 'imagen_references' in sidecar:
                                history_entry['imagen_references'] = sidecar['imagen_references']
                            elif 'reference_image' in sidecar:
                                history_entry['reference_image'] = sidecar['reference_image']

                            batch_items.append(history_entry)
                        else:
                            # No sidecar, just add path with basic info
                            batch_items.append({
                                'path': path,
                                'prompt': path.stem.replace('_', ' '),
                                'timestamp': path.stat().st_mtime,
                                'model': '',
                                'provider': '',
                                'cost': 0.0
                            })
                    except Exception:
                        pass

                # Emit batch
                if batch_items:
                    self.batch_loaded.emit(batch_items)

                # Update progress
                current_index = end_index
                self.progress.emit(current_index, total)

            # Finished loading all items
            if not self._stop_requested:
                self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))


class OllamaDetectionWorker(QObject):
    """Worker thread for detecting Ollama models without blocking startup."""

    models_detected = Signal(list)  # List of model names
    no_ollama = Signal()  # Emitted when Ollama not available
    finished = Signal()
    error = Signal(str)

    def __init__(self, endpoint: str = "http://localhost:11434"):
        super().__init__()
        self.endpoint = endpoint

    def run(self):
        """Detect Ollama models in background."""
        try:
            from core.llm_models import update_ollama_models, get_provider_models

            # Try to update Ollama models (this will make the HTTP request)
            if update_ollama_models(self.endpoint):
                models = get_provider_models('ollama')
                self.models_detected.emit(models)
            else:
                self.no_ollama.emit()

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit()