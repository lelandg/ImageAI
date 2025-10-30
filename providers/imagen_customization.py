"""
Google Imagen 3 Customization API provider.

This provider implements support for Google's Imagen 3 Customization API,
which enables generation with multiple reference images (up to 4).

Key features:
- Multiple reference images (1-4 per generation)
- Reference types: SUBJECT, STYLE, CONTROL
- Subject types: PERSON, ANIMAL, PRODUCT
- Prompt syntax with [1], [2], [3], [4] tags
"""

import base64
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Check if Google Cloud libraries are available
try:
    import importlib.util
    GCLOUD_AVAILABLE = importlib.util.find_spec("google.cloud.aiplatform") is not None
except ImportError:
    GCLOUD_AVAILABLE = False

# These will be imported lazily
aiplatform = None
aiplatform_v1 = None
google_auth_default = None
DefaultCredentialsError = Exception

from .base import ImageProvider

# Import reference models
try:
    from ..core.reference import ImagenReference, ImagenReferenceType, validate_references
except ImportError:
    from core.reference import ImagenReference, ImagenReferenceType, validate_references


class ImagenCustomizationProvider(ImageProvider):
    """
    Provider for Google Imagen 3 Customization API with multiple reference images.

    This provider extends the base ImageProvider to support Google's Imagen 3
    Customization API, which allows using 1-4 reference images to guide generation.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Imagen Customization provider.

        Args:
            config: Configuration dictionary with authentication details
        """
        super().__init__(config)
        self.client = None
        self.project_id = None
        self.location = config.get('gcloud_location', 'us-central1')

        # Get config manager for auth state
        try:
            from ..core.config import ConfigManager
        except ImportError:
            from core.config import ConfigManager
        self.config_manager = ConfigManager()

        # Initialize client if possible
        self._init_client()

    def _init_client(self):
        """Initialize Google Cloud AI Platform client for Imagen 3."""
        global aiplatform, aiplatform_v1, google_auth_default, DefaultCredentialsError

        if not GCLOUD_AVAILABLE:
            logger.warning(
                "Google Cloud AI Platform not available. "
                "Install with: pip install google-cloud-aiplatform"
            )
            return

        try:
            # Lazy import Google Cloud libraries
            if aiplatform is None:
                print("Loading Google Cloud AI Platform for Imagen 3...")
                from google.cloud import aiplatform
                from google.cloud import aiplatform_v1
                from google.auth import default as google_auth_default
                from google.auth.exceptions import DefaultCredentialsError

            # Get Application Default Credentials
            credentials, project = google_auth_default()

            # Get project ID
            if not project:
                project = self._get_gcloud_project_id()

            if not project:
                logger.warning(
                    "No Google Cloud project found. "
                    "Set a project with: gcloud config set project YOUR_PROJECT_ID"
                )
                return

            self.project_id = project

            # Initialize aiplatform
            aiplatform.init(project=project, location=self.location)

            logger.info(f"Initialized Imagen 3 client for project: {project}")

        except DefaultCredentialsError as e:
            logger.warning(
                f"Google Cloud authentication not configured. "
                f"Run: gcloud auth application-default login"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Imagen 3 client: {e}")

    def _get_gcloud_project_id(self) -> Optional[str]:
        """
        Get the current Google Cloud project ID.

        Returns:
            Project ID string or None if not found
        """
        try:
            import subprocess
            import platform

            gcloud_cmd = "gcloud.cmd" if platform.system() == "Windows" else "gcloud"
            result = subprocess.run(
                [gcloud_cmd, "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=2,
                shell=False
            )

            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()

        except Exception as e:
            logger.debug(f"Could not get gcloud project ID: {e}")

        return None

    def generate_with_references(
        self,
        prompt: str,
        references: List[ImagenReference],
        aspect_ratio: str = "16:9",
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        person_generation: str = "allow_all",
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Generate image with multiple reference images.

        Args:
            prompt: Text prompt with [1], [2], etc. for references
            references: List of ImagenReference objects (1-4)
            aspect_ratio: Output aspect ratio (e.g., "16:9", "1:1")
            negative_prompt: Things to avoid in the image
            seed: Random seed for reproducibility
            person_generation: Control person generation - "dont_allow", "allow_adult", or "allow_all"
            **kwargs: Additional parameters

        Returns:
            Tuple of (texts, images) where:
                - texts: List of text responses (usually empty)
                - images: List of generated image bytes

        Raises:
            ValueError: If references are invalid or missing
            RuntimeError: If API call fails
        """
        # Validate inputs
        if not self.client and not self.project_id:
            raise RuntimeError(
                "Imagen 3 client not initialized. "
                "Ensure Google Cloud authentication is configured."
            )

        # Validate references
        is_valid, errors = validate_references(references)
        if not is_valid:
            raise ValueError(f"Invalid references: {'; '.join(errors)}")

        # Validate prompt has reference tags
        self._validate_prompt_references(prompt, len(references))

        logger.info("=" * 60)
        logger.info("GOOGLE IMAGEN 3 CUSTOMIZATION API REQUEST")
        logger.info(f"Model: imagen-3.0-capability-001")
        logger.info(f"Project: {self.project_id}")
        logger.info(f"Prompt: {prompt}")
        logger.info(f"References: {len(references)}")
        for ref in references:
            logger.info(f"  [{ref.reference_id}] {ref.reference_type.value} - {ref.path.name}")
            if ref.subject_description:
                logger.info(f"      Description: {ref.subject_description}")
        logger.info(f"Aspect ratio: {aspect_ratio}")
        if negative_prompt:
            logger.info(f"Negative prompt: {negative_prompt}")
        if seed is not None:
            logger.info(f"Seed: {seed}")
        logger.info(f"Person generation: {person_generation}")
        logger.info("=" * 60)

        # Build reference images array
        reference_images = []
        for ref in references:
            ref_dict = self._build_reference_dict(ref)
            reference_images.append(ref_dict)

        # Log the exact API structure being sent (without image data)
        logger.info("Reference images API structure:")
        for i, ref_dict in enumerate(reference_images, start=1):
            # Create a copy without the base64 data for logging
            ref_log = {k: v for k, v in ref_dict.items() if k != "referenceImage"}
            logger.info(f"  Reference {i}: {ref_log}")

        # Build request
        instance = {
            "prompt": prompt,
            "referenceImages": reference_images
        }

        parameters = {
            "sampleCount": 1,
            "aspectRatio": aspect_ratio,
            # Enable safety filter reason codes for better error messages
            "includeRaiReason": True,
            "includeSafetyAttributes": True,
            # Use less restrictive safety setting
            "safetyFilterLevel": "block_only_high",
            # Control person generation (dont_allow, allow_adult, allow_all)
            "personGeneration": person_generation
        }

        if negative_prompt:
            parameters["negativePrompt"] = negative_prompt

        if seed is not None:
            parameters["seed"] = seed

        try:
            # Call Imagen 3 Customization API
            response = self._predict(
                instances=[instance],
                parameters=parameters
            )

            # Extract images from response
            texts = []
            images = []

            # Check for safety filter blocks (initialize outside if block)
            safety_blocked = False
            safety_reason = None

            # Log response structure for debugging
            logger.info("=" * 60)
            logger.info("RESPONSE ANALYSIS")
            logger.info(f"Response type: {type(response)}")
            logger.info(f"Has predictions attr: {hasattr(response, 'predictions')}")

            if response and hasattr(response, 'predictions'):
                logger.info(f"Number of predictions: {len(response.predictions)}")

                for idx, prediction in enumerate(response.predictions):
                    logger.info(f"Prediction {idx+1}:")
                    logger.info(f"  Type: {type(prediction)}")
                    logger.info(f"  Type name: {type(prediction).__name__}")

                    # Convert to dict for consistent handling
                    prediction_dict = None

                    # Check if it's a MapComposite (proto.marshal)
                    if type(prediction).__name__ == 'MapComposite':
                        logger.info(f"  MapComposite detected - converting to dict")
                        # MapComposite can be converted to dict
                        prediction_dict = dict(prediction)
                        logger.info(f"  Converted to dict: {list(prediction_dict.keys())}")

                    # Check if it's a protobuf message
                    elif hasattr(prediction, 'DESCRIPTOR'):
                        logger.info(f"  Protobuf message type: {prediction.DESCRIPTOR.full_name}")
                        # Convert protobuf to dict
                        from google.protobuf import json_format
                        prediction_dict = json_format.MessageToDict(prediction)
                        logger.info(f"  Converted to dict: {list(prediction_dict.keys())}")

                    # Already a dict
                    elif isinstance(prediction, dict):
                        logger.info(f"  Already a dict")
                        prediction_dict = prediction

                    else:
                        logger.warning(f"  ✗ Unknown prediction type: {type(prediction)}")
                        logger.warning(f"  Trying to convert to dict anyway...")
                        try:
                            prediction_dict = dict(prediction)
                            logger.info(f"  Successfully converted: {list(prediction_dict.keys())}")
                        except Exception as e:
                            logger.error(f"  Failed to convert: {e}")

                    # Response format: {"bytesBase64Encoded": "...", "mimeType": "..."}
                    if prediction_dict:
                        logger.info(f"  Dict keys: {list(prediction_dict.keys())}")

                        # Check for safety filter information
                        if "raiFilteredReason" in prediction_dict:
                            safety_blocked = True
                            safety_reason = prediction_dict.get("raiFilteredReason")
                            logger.warning(f"  ⚠ Safety filter triggered: {safety_reason}")

                        if "safetyAttributes" in prediction_dict:
                            logger.info(f"  Safety attributes: {prediction_dict['safetyAttributes']}")

                        if "bytesBase64Encoded" in prediction_dict:
                            image_base64 = prediction_dict["bytesBase64Encoded"]
                            image_bytes = base64.b64decode(image_base64)
                            images.append(image_bytes)
                            logger.info(f"  ✓ Successfully extracted image: {len(image_bytes)} bytes")
                        else:
                            logger.warning(f"  ✗ No 'bytesBase64Encoded' field found")
                            if not safety_blocked:
                                logger.warning(f"  Available fields: {prediction_dict}")
                    else:
                        logger.error(f"  ✗ Could not convert prediction to dict")
            else:
                logger.error("Response has no predictions attribute!")
                logger.error(f"Response attributes: {dir(response)}")

            logger.info("=" * 60)

            if not images:
                # Provide user-friendly error messages based on the failure reason
                if safety_blocked:
                    error_msg = (
                        "Image generation was blocked by Google's safety filters.\n\n"
                        f"Reason: {safety_reason if safety_reason else 'Content policy violation'}\n\n"
                        "Tips to resolve:\n"
                        "• Avoid references to real people, political figures, or celebrities\n"
                        "• Ensure reference images don't contain sensitive content\n"
                        "• Try rewording your prompt to be more general\n"
                        "• Check that your reference images are appropriate\n\n"
                        "The safety filter is designed to prevent generation of potentially harmful content."
                    )
                elif response and hasattr(response, 'predictions') and len(response.predictions) > 0:
                    error_msg = (
                        "API returned predictions but they don't contain image data.\n\n"
                        "This could indicate:\n"
                        "• Safety filters blocked the generation (check logs for details)\n"
                        "• API format mismatch (check logs for response structure)\n"
                        "• Invalid reference image format\n\n"
                        "Please check the application logs for detailed information."
                    )
                else:
                    error_msg = (
                        "No predictions returned from the API.\n\n"
                        "This could indicate:\n"
                        "• Invalid API request format\n"
                        "• Authentication issues\n"
                        "• Model endpoint unavailable\n\n"
                        "Please check the application logs for detailed error information."
                    )
                raise RuntimeError(error_msg)

            logger.info(f"Successfully generated {len(images)} image(s)")
            return texts, images

        except Exception as e:
            logger.error(f"Imagen 3 generation failed: {e}", exc_info=True)
            raise RuntimeError(f"Imagen 3 generation failed: {e}")

    def _predict(
        self,
        instances: List[Dict[str, Any]],
        parameters: Dict[str, Any]
    ) -> Any:
        """
        Call Imagen 3 Customization API predict endpoint.

        Args:
            instances: List of instance dictionaries
            parameters: Parameter dictionary

        Returns:
            Prediction response
        """
        from google.cloud import aiplatform_v1
        from google.protobuf import json_format
        from google.protobuf.struct_pb2 import Value

        # Convert to protobuf Value objects
        instances_proto = [json_format.ParseDict(inst, Value()) for inst in instances]
        parameters_proto = json_format.ParseDict(parameters, Value())

        # Build endpoint path
        endpoint = (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"publishers/google/models/imagen-3.0-capability-001"
        )

        logger.info(f"Calling API endpoint: {endpoint}")
        logger.info(f"Request instances: {len(instances)}")
        logger.info(f"Request parameters: {parameters}")

        # Create prediction client
        prediction_client = aiplatform_v1.PredictionServiceClient()

        # Make prediction request
        try:
            response = prediction_client.predict(
                endpoint=endpoint,
                instances=instances_proto,
                parameters=parameters_proto
            )
            logger.info(f"API call successful, response type: {type(response)}")
            return response
        except Exception as e:
            logger.error(f"API predict call failed: {e}", exc_info=True)
            raise

    def _build_reference_dict(self, ref: ImagenReference) -> Dict[str, Any]:
        """
        Build API reference dictionary from ImagenReference object.

        Args:
            ref: ImagenReference object

        Returns:
            Dictionary formatted for Imagen 3 API
        """
        # Load image data if not already loaded
        image_data = ref.load_image_data()

        # Encode to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Build reference dictionary with REFERENCE_TYPE_ prefix
        ref_dict = {
            "referenceType": f"REFERENCE_TYPE_{ref.reference_type.value.upper()}",
            "referenceId": ref.reference_id,
            "referenceImage": {
                "bytesBase64Encoded": image_base64
            }
        }

        # Add type-specific configuration using correct config field names
        if ref.reference_type == ImagenReferenceType.SUBJECT:
            config = {}
            if ref.subject_type:
                # Add SUBJECT_TYPE_ prefix
                config["subjectType"] = f"SUBJECT_TYPE_{ref.subject_type.value.upper()}"

            if ref.subject_description:
                config["subjectDescription"] = ref.subject_description

            # Use subjectImageConfig (not referenceConfig)
            ref_dict["subjectImageConfig"] = config

        elif ref.reference_type == ImagenReferenceType.STYLE:
            config = {}
            if ref.subject_description:  # Used as style description
                config["styleDescription"] = ref.subject_description

            # Use styleImageConfig
            ref_dict["styleImageConfig"] = config

        elif ref.reference_type == ImagenReferenceType.CONTROL:
            config = {}
            if ref.control_type:
                # Add CONTROL_TYPE_ prefix
                config["controlType"] = f"CONTROL_TYPE_{ref.control_type.value.upper()}"

            # Use controlImageConfig
            ref_dict["controlImageConfig"] = config

        return ref_dict

    def _validate_prompt_references(self, prompt: str, num_references: int):
        """
        Validate that prompt references match available references.

        Args:
            prompt: Text prompt
            num_references: Number of available references

        Raises:
            ValueError: If prompt references invalid reference IDs
        """
        # Find all [N] tags in prompt
        tags = re.findall(r'\[(\d+)\]', prompt)

        if not tags:
            logger.warning(
                f"Prompt does not contain reference tags [1]-[{num_references}]. "
                f"References may not be used."
            )
            return

        # Check if any tag exceeds available references
        tag_nums = [int(t) for t in tags]
        max_tag = max(tag_nums)

        if max_tag > num_references:
            raise ValueError(
                f"Prompt references [{max_tag}] but only {num_references} "
                f"reference image(s) provided"
            )

        # Check if all references are used
        used_refs = set(tag_nums)
        expected_refs = set(range(1, num_references + 1))

        if used_refs != expected_refs:
            unused = expected_refs - used_refs
            logger.warning(
                f"Not all references used in prompt. "
                f"Unused reference IDs: {sorted(unused)}"
            )

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """
        Generate image (compatibility with base provider).

        This method provides compatibility with the base ImageProvider interface.
        For multi-reference generation, use generate_with_references() instead.

        Args:
            prompt: Text prompt
            model: Model name (ignored, always uses imagen-3.0-capability-001)
            **kwargs: Additional parameters

        Returns:
            Tuple of (texts, images)
        """
        # Check if references provided in kwargs
        references = kwargs.get('references', [])

        if not references:
            raise ValueError(
                "ImagenCustomizationProvider requires at least 1 reference image. "
                "Use generate_with_references() method or pass 'references' parameter."
            )

        # Remove references from kwargs to avoid duplicate parameter
        kwargs_without_refs = {k: v for k, v in kwargs.items() if k != 'references'}

        # Route to multi-reference generation
        return self.generate_with_references(
            prompt=prompt,
            references=references,
            **kwargs_without_refs
        )

    def get_models(self) -> Dict[str, str]:
        """Get available models."""
        return {
            "imagen-3.0-capability-001": "Imagen 3 Customization (Multi-reference)"
        }

    def get_default_model(self) -> str:
        """Get default model."""
        return "imagen-3.0-capability-001"

    def get_supported_features(self) -> List[str]:
        """Get supported features."""
        return ["generate", "multi_reference", "subject_customization", "style_transfer"]

    def validate_auth(self) -> Tuple[bool, str]:
        """
        Validate Google Cloud authentication.

        Returns:
            Tuple of (is_valid, message)
        """
        if not self.project_id:
            return False, "Not authenticated. Run: gcloud auth application-default login"

        try:
            # Test API access with a simple call
            # Note: This is a placeholder - actual validation would require a test prediction
            return True, f"Authenticated (Project: {self.project_id})"

        except Exception as e:
            return False, f"Authentication error: {e}"

    def get_api_key_url(self) -> str:
        """Get Google Cloud console URL."""
        return "https://console.cloud.google.com/apis/credentials"
