"""Google Gemini provider for image generation."""

import os
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from base64 import b64decode

# Check if google.genai is available but don't import yet
try:
    import importlib.util
    GENAI_AVAILABLE = importlib.util.find_spec("google.genai") is not None
except ImportError:
    GENAI_AVAILABLE = False

# These will be populated on first use
genai = None
types = None

from .base import ImageProvider

# Import rate_limiter with fallback for different import contexts
try:
    from ..core.security import rate_limiter
except ImportError:
    from core.security import rate_limiter


# Check if Google Cloud is available but don't import yet
try:
    import importlib.util
    GCLOUD_AVAILABLE = importlib.util.find_spec("google.cloud.aiplatform") is not None
except ImportError:
    GCLOUD_AVAILABLE = False

# These will be populated on first use
aiplatform = None
google_auth_default = None
DefaultCredentialsError = Exception


class GoogleProvider(ImageProvider):
    """Google Gemini provider for AI image generation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Google provider."""
        super().__init__(config)
        self.client = None
        self.project_id = None
        
        # Get config manager for auth state
        try:
            from ..core.config import ConfigManager
        except ImportError:
            from core.config import ConfigManager
        self.config_manager = ConfigManager()
        
        # Initialize client based on auth mode
        if self.auth_mode == "gcloud":
            # Check if we have cached auth validation
            if self.config_manager.get_auth_validated("google"):
                self.project_id = self.config_manager.get_gcloud_project_id()
            # Don't initialize gcloud client here - do it lazily in generate()
            # This allows auth checking without failing
        elif self.api_key:
            self._init_api_key_client()
    
    def _init_api_key_client(self):
        """Initialize client with API key."""
        global genai, types
        
        if not GENAI_AVAILABLE:
            raise ImportError(
                "Google GenAI library not installed. "
                "Run: pip install google-generativeai"
            )
        
        # Lazy import on first use
        if genai is None:
            print("Loading Google AI provider...")
            from google import genai
            from google.genai import types
        
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
    
    def _init_gcloud_client(self, raise_on_error=True):
        """Initialize client with Google Cloud authentication.
        
        Args:
            raise_on_error: If True, raise exception on auth failure. If False, return False.
        """
        global aiplatform, google_auth_default, DefaultCredentialsError, genai, types
        
        if not GCLOUD_AVAILABLE:
            if raise_on_error:
                raise ImportError(
                    "Google Cloud AI Platform not installed. "
                    "Run: pip install google-cloud-aiplatform"
                )
            return False
        
        # Lazy import Google Cloud on first use
        if aiplatform is None:
            print("Loading Google Cloud AI provider...")
            from google.cloud import aiplatform
            from google.auth import default as google_auth_default
            from google.auth.exceptions import DefaultCredentialsError
        
        # Also ensure genai is imported for gcloud mode
        if genai is None:
            from google import genai
            from google.genai import types
        
        try:
            # Get Application Default Credentials
            credentials, project = google_auth_default()
            if not project:
                project = self._get_gcloud_project_id()
            if not project:
                if raise_on_error:
                    raise ValueError(
                        "No Google Cloud project found. "
                        "Set a project with: gcloud config set project YOUR_PROJECT_ID"
                    )
                return False
            
            self.project_id = project
            # Initialize aiplatform
            aiplatform.init(project=project, location="us-central1")
            
            # Create genai client that will use ADC
            self.client = genai.Client()
            return True
            
        except DefaultCredentialsError as e:
            if raise_on_error:
                raise RuntimeError(
                f"Google Cloud authentication failed.\n\n"
                f"Please complete the setup:\n"
                f"1. Install Google Cloud CLI from:\n"
                f"   https://cloud.google.com/sdk/docs/install\n"
                f"2. Run in terminal/PowerShell:\n"
                f"   gcloud auth application-default login\n"
                f"3. Set your project:\n"
                f"   gcloud config set project YOUR_PROJECT_ID\n"
                f"4. Enable required APIs at:\n"
                f"   https://console.cloud.google.com/apis/library\n"
                f"   - Vertex AI API\n"
                f"   - Cloud Resource Manager API\n\n"
                f"Error details: {e}"
            )
            return False
    
    def _get_gcloud_project_id(self) -> Optional[str]:
        """Get the current Google Cloud project ID."""
        try:
            # Fast path: Read directly from gcloud config file
            from pathlib import Path
            import configparser
            
            # Check gcloud config locations
            config_paths = [
                Path.home() / ".config" / "gcloud" / "configurations" / "config_default",  # Linux/WSL
                Path.home() / "AppData" / "Roaming" / "gcloud" / "configurations" / "config_default",  # Windows
            ]
            
            for config_path in config_paths:
                if config_path.exists():
                    try:
                        config = configparser.ConfigParser()
                        config.read(config_path)
                        if 'core' in config and 'project' in config['core']:
                            return config['core']['project']
                    except Exception:
                        continue
            
            # Fallback: Try subprocess if config file not found
            gcloud_cmd = "gcloud.cmd" if platform.system() == "Windows" else "gcloud"
            result = subprocess.run(
                [gcloud_cmd, "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=2,  # Reduced timeout
                shell=False
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        except Exception:
            # Broader exception handling for various subprocess issues
            pass
        return None
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Generate images using Google Gemini models."""
        if not self.client:
            if self.auth_mode == "gcloud":
                # Try to initialize gcloud client, raise error if it fails
                self._init_gcloud_client(raise_on_error=True)
            else:
                raise ValueError("No API key configured for Google provider")
        
        model = model or self.get_default_model()
        
        # Only apply rate limiting for API key mode (Google Cloud has its own quotas)
        if self.auth_mode != "gcloud":
            rate_limiter.check_rate_limit('google', wait=True)
        
        texts: List[str] = []
        images: List[bytes] = []
        
        # Build generation config for Gemini models
        # Note: Gemini 2.5 Flash (Nano Banana) supports aspect ratios via prompt specification
        # While the API doesn't have direct aspect ratio parameters, specifying it in the prompt works
        config = {}
        
        # Add aspect ratio to prompt for Gemini (Nano Banana) support
        # According to the Nano Banana guide, we should specify the aspect ratio in the prompt
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')
        width = kwargs.get('width', 1024)
        height = kwargs.get('height', 1024)

        # Calculate aspect ratio from dimensions if not provided
        if width and height and width != height:
            # Determine the actual aspect ratio from dimensions
            ratio = width / height
            if abs(ratio - 16/9) < 0.1:
                aspect_ratio = '16:9'
            elif abs(ratio - 9/16) < 0.1:
                aspect_ratio = '9:16'
            elif abs(ratio - 4/3) < 0.1:
                aspect_ratio = '4:3'
            elif abs(ratio - 3/4) < 0.1:
                aspect_ratio = '3:4'
            elif abs(ratio - 21/9) < 0.1:
                aspect_ratio = '21:9'
            elif abs(ratio - 1.0) < 0.1:
                aspect_ratio = '1:1'

        # Add aspect ratio specification to prompt as recommended in Nano Banana guide
        if aspect_ratio and aspect_ratio != '1:1':
            # Add explicit format request as per the guide
            prompt = f"{prompt}. The image should be in a {aspect_ratio} format."
        
        # Note: These generation_config parameters may not be supported by all Gemini models
        # Most are placeholders for potential future support
        
        # Number of images - may work with some models
        num_images = kwargs.get('num_images', 1)
        if num_images > 1:
            # Try to request multiple images (may not be supported)
            config['candidate_count'] = num_images
        
        # Safety settings (these generally work)
        if kwargs.get('safety_filter'):
            config['safety_settings'] = kwargs['safety_filter']
        
        # Seed for reproducibility (if supported)
        if kwargs.get('seed') is not None:
            config['seed'] = kwargs['seed']
        
        try:
            # Try to use generation_config parameter if supported
            if config:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    generation_config=config
                )
            else:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
            
            if response and response.candidates:
                # Process all candidates (for multiple images)
                for cand in response.candidates:
                    if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                        for part in cand.content.parts:
                            if getattr(part, "text", None):
                                texts.append(part.text)
                            elif getattr(part, "inline_data", None) is not None:
                                data = getattr(part.inline_data, "data", None)
                                if isinstance(data, (bytes, bytearray)):
                                    images.append(bytes(data))
        except Exception as e:
            # Fallback to basic generation if advanced config fails
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                
                if response and response.candidates:
                    cand = response.candidates[0]
                    if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                        for part in cand.content.parts:
                            if getattr(part, "text", None):
                                texts.append(part.text)
                            elif getattr(part, "inline_data", None) is not None:
                                data = getattr(part.inline_data, "data", None)
                                if isinstance(data, (bytes, bytearray)):
                                    images.append(bytes(data))
            except Exception as e2:
                raise RuntimeError(f"Google generation failed: {e2}")
        
        return texts, images
    
    def validate_auth(self) -> Tuple[bool, str]:
        """Validate Google authentication."""
        if self.auth_mode == "gcloud":
            return self._check_gcloud_auth()
        else:
            # Test API key
            if not self.api_key:
                return False, "No API key configured"
            
            try:
                # Try a minimal generation
                if not self.client:
                    self._init_api_key_client()
                
                response = self.client.models.generate_content(
                    model=self.get_default_model(),
                    contents="Test",
                )
                return True, "API key is valid"
            except Exception as e:
                return False, f"API key validation failed: {e}"
    
    def _check_gcloud_auth(self) -> Tuple[bool, str]:
        """Check Google Cloud authentication status."""
        # First check if we have cached validation
        if self.config_manager.get_auth_validated("google"):
            project_id = self.config_manager.get_gcloud_project_id()
            if project_id:
                return True, f"Authenticated (Project: {project_id}) [cached]"
            return True, "Authenticated [cached]"
        
        try:
            # Fast path: Check if credentials file exists first
            from pathlib import Path
            import json
            
            # Check standard ADC locations
            adc_paths = [
                Path.home() / ".config" / "gcloud" / "application_default_credentials.json",  # Linux/WSL
                Path.home() / "AppData" / "Roaming" / "gcloud" / "application_default_credentials.json",  # Windows
            ]
            
            creds_file = None
            for path in adc_paths:
                if path.exists():
                    creds_file = path
                    break
            
            if not creds_file:
                # Clear cached auth if no credentials file
                self.config_manager.set_auth_validated("google", False)
                self.config_manager.save()
                return False, "Not authenticated. Run: gcloud auth application-default login"
            
            # Quick validation: check if file is valid JSON and not expired
            try:
                with open(creds_file, 'r') as f:
                    creds_data = json.load(f)
                
                # Basic validation - check if it has expected fields
                if 'client_id' in creds_data or 'type' in creds_data:
                    # Get project ID quickly
                    project = self._get_gcloud_project_id()
                    
                    # Cache the successful auth validation
                    self.config_manager.set_auth_validated("google", True)
                    if project:
                        self.config_manager.set_gcloud_project_id(project)
                    self.config_manager.save()
                    
                    if project:
                        return True, f"Authenticated (Project: {project})"
                    else:
                        return True, "Authenticated (No project set)"
                else:
                    return False, "Invalid credentials file"
                    
            except (json.JSONDecodeError, KeyError):
                return False, "Corrupted credentials file. Re-authenticate with: gcloud auth application-default login"
                
        except Exception as e:
            return False, f"Error checking authentication: {e}"
    
    def get_models(self) -> Dict[str, str]:
        """Get available Google models."""
        return {
            "gemini-2.5-flash-image-preview": "Gemini 2.5 Flash (Image Preview)",
            "gemini-2.5-flash": "Gemini 2.5 Flash",
            "gemini-2.5-pro": "Gemini 2.5 Pro",
            "gemini-1.5-flash": "Gemini 1.5 Flash",
            "gemini-1.5-pro": "Gemini 1.5 Pro",
        }
    
    def get_models_with_details(self) -> Dict[str, Dict[str, str]]:
        """Get available Google models with detailed display information.
        
        Returns:
            Dictionary mapping model IDs to display information including:
            - name: Short display name
            - nickname: Optional nickname/codename
            - description: Optional brief description
        """
        return {
            "gemini-2.5-flash-image-preview": {
                "name": "Gemini 2.5 Flash Image",
                "nickname": "Nano Banana",
                "description": "Advanced image generation and editing"
            },
            "gemini-2.5-flash": {
                "name": "Gemini 2.5 Flash",
                "description": "Fast performance on everyday tasks"
            },
            "gemini-2.5-pro": {
                "name": "Gemini 2.5 Pro",
                "description": "Advanced reasoning and complex problems"
            },
            "gemini-1.5-flash": {
                "name": "Gemini 1.5 Flash",
                "description": "Balanced speed and capability"
            },
            "gemini-1.5-pro": {
                "name": "Gemini 1.5 Pro",
                "description": "Wide-range reasoning tasks"
            },
        }
    
    def get_default_model(self) -> str:
        """Get default Google model."""
        return "gemini-2.5-flash-image-preview"
    
    def get_api_key_url(self) -> str:
        """Get Google API key URL."""
        return "https://aistudio.google.com/apikey"
    
    def get_supported_features(self) -> List[str]:
        """Get supported features."""
        return ["generate", "edit", "compose"]
    
    def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Edit image with Google Gemini."""
        if not self.client:
            raise ValueError("No client configured")
        
        model = model or self.get_default_model()
        texts: List[str] = []
        images: List[bytes] = []
        
        try:
            # Gemini can process images as input
            response = self.client.models.generate_content(
                model=model,
                contents=[prompt, {"inline_data": {"data": image, "mime_type": "image/png"}}],
            )
            
            if response and response.candidates:
                cand = response.candidates[0]
                if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                    for part in cand.content.parts:
                        if getattr(part, "text", None):
                            texts.append(part.text)
                        elif getattr(part, "inline_data", None) is not None:
                            data = getattr(part.inline_data, "data", None)
                            if isinstance(data, (bytes, bytearray)):
                                images.append(bytes(data))
        except Exception as e:
            raise RuntimeError(f"Google image editing failed: {e}")
        
        return texts, images