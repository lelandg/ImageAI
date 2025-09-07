"""Google Gemini provider for image generation."""

import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from base64 import b64decode

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False

from .base import ImageProvider


# Optional Google Cloud imports
try:
    from google.cloud import aiplatform
    from google.auth import default as google_auth_default
    from google.auth.exceptions import DefaultCredentialsError
    GCLOUD_AVAILABLE = True
except ImportError:
    aiplatform = None
    google_auth_default = None
    DefaultCredentialsError = Exception
    GCLOUD_AVAILABLE = False


class GoogleProvider(ImageProvider):
    """Google Gemini provider for AI image generation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Google provider."""
        super().__init__(config)
        self.client = None
        self.project_id = None
        
        # Initialize client based on auth mode
        if self.auth_mode == "gcloud":
            self._init_gcloud_client()
        elif self.api_key:
            self._init_api_key_client()
    
    def _init_api_key_client(self):
        """Initialize client with API key."""
        if not GENAI_AVAILABLE:
            raise ImportError(
                "Google GenAI library not installed. "
                "Run: pip install google-generativeai"
            )
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
    
    def _init_gcloud_client(self):
        """Initialize client with Google Cloud authentication."""
        if not GCLOUD_AVAILABLE:
            raise ImportError(
                "Google Cloud AI Platform not installed. "
                "Run: pip install google-cloud-aiplatform"
            )
        
        try:
            # Get Application Default Credentials
            credentials, project = google_auth_default()
            if not project:
                project = self._get_gcloud_project_id()
            if not project:
                raise ValueError(
                    "No Google Cloud project found. "
                    "Set a project with: gcloud config set project YOUR_PROJECT_ID"
                )
            
            self.project_id = project
            # Initialize aiplatform
            aiplatform.init(project=project, location="us-central1")
            
            # Create genai client that will use ADC
            self.client = genai.Client()
            
        except DefaultCredentialsError as e:
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
    
    def _get_gcloud_project_id(self) -> Optional[str]:
        """Get the current Google Cloud project ID."""
        try:
            # Try to get project ID from gcloud config
            gcloud_cmd = "gcloud.cmd" if platform.system() == "Windows" else "gcloud"
            result = subprocess.run(
                [gcloud_cmd, "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=(platform.system() == "Windows")
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Generate images using Google Gemini/Imagen 3."""
        if not self.client:
            if self.auth_mode == "gcloud":
                self._init_gcloud_client()
            else:
                raise ValueError("No API key configured for Google provider")
        
        model = model or self.get_default_model()
        texts: List[str] = []
        images: List[bytes] = []
        
        # Build generation config with Imagen 3 parameters
        config = {}
        
        # Handle aspect ratio (Imagen 3 supports: 1:1, 3:4, 4:3, 9:16, 16:9)
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')
        if aspect_ratio in ['1:1', '3:4', '4:3', '9:16', '16:9']:
            config['aspect_ratio'] = aspect_ratio
        
        # Handle resolution (1K or 2K for Imagen 3)
        resolution = kwargs.get('resolution', '1024x1024')
        if '2048' in str(resolution) or '2K' in str(resolution).upper():
            config['sample_image_size'] = '2K'
        else:
            config['sample_image_size'] = '1K'
        
        # Number of images (1-4 for Imagen 3)
        num_images = kwargs.get('num_images', 1)
        if 1 <= num_images <= 4:
            config['number_of_images'] = num_images
        
        # Advanced settings
        if kwargs.get('enable_prompt_rewriting') is not None:
            config['enable_prompt_rewriting'] = kwargs['enable_prompt_rewriting']
        
        if kwargs.get('safety_filter'):
            config['safety_filter_level'] = kwargs['safety_filter']
        
        if kwargs.get('person_generation') is not None:
            config['person_generation'] = 'allow' if kwargs['person_generation'] else 'dont_allow'
        
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
        try:
            gcloud_cmd = "gcloud.cmd" if platform.system() == "Windows" else "gcloud"
            
            # Check if gcloud is installed
            which_cmd = "where" if platform.system() == "Windows" else "which"
            result = subprocess.run(
                [which_cmd, gcloud_cmd],
                capture_output=True,
                timeout=5,
                shell=(platform.system() == "Windows")
            )
            
            if result.returncode != 0:
                return False, "Google Cloud CLI not installed"
            
            # Check authentication
            result = subprocess.run(
                [gcloud_cmd, "auth", "application-default", "print-access-token"],
                capture_output=True,
                text=True,
                timeout=10,
                shell=(platform.system() == "Windows")
            )
            
            if result.returncode == 0:
                project_id = self._get_gcloud_project_id()
                if project_id:
                    return True, f"Authenticated (Project: {project_id})"
                else:
                    return True, "Authenticated (No project set)"
            else:
                return False, "Not authenticated. Run: gcloud auth application-default login"
                
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