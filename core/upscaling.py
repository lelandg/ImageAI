"""Image upscaling utilities for ImageAI."""

import logging
from typing import Tuple, Optional, Dict, Any
from PIL import Image
import io
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Check for optional AI upscaling libraries
try:
    # Patch the torchvision import issue before importing Real-ESRGAN
    import sys
    if 'torchvision.transforms.functional_tensor' not in sys.modules:
        try:
            from torchvision.transforms import functional
            sys.modules['torchvision.transforms.functional_tensor'] = functional
        except ImportError:
            pass  # torchvision not installed

    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer
    import numpy as np
    import cv2
    REALESRGAN_AVAILABLE = True
except ImportError:
    REALESRGAN_AVAILABLE = False

class UpscalingMethod:
    """Enum for upscaling methods."""
    NONE = "none"
    LANCZOS = "lanczos"
    REALESRGAN = "realesrgan"
    STABILITY_API = "stability_api"


def upscale_image(
    image_data: bytes,
    target_width: int,
    target_height: int,
    method: str = UpscalingMethod.LANCZOS,
    **kwargs
) -> bytes:
    """
    Upscale an image to target dimensions using specified method.

    Args:
        image_data: Raw image bytes
        target_width: Target width
        target_height: Target height
        method: Upscaling method to use
        **kwargs: Additional method-specific parameters

    Returns:
        Upscaled image as bytes
    """
    try:
        if method == UpscalingMethod.NONE:
            return image_data

        elif method == UpscalingMethod.LANCZOS:
            return upscale_lanczos(image_data, target_width, target_height)

        elif method == UpscalingMethod.REALESRGAN:
            if not REALESRGAN_AVAILABLE:
                logger.warning("RealESRGAN not available, falling back to Lanczos")
                return upscale_lanczos(image_data, target_width, target_height)
            return upscale_realesrgan(image_data, target_width, target_height, **kwargs)

        elif method == UpscalingMethod.STABILITY_API:
            return upscale_stability_api(image_data, target_width, target_height, **kwargs)

        else:
            logger.error(f"Unknown upscaling method: {method}")
            return image_data

    except Exception as e:
        logger.error(f"Upscaling failed: {e}")
        return image_data


def upscale_lanczos(image_data: bytes, target_width: int, target_height: int) -> bytes:
    """
    Upscale image using Lanczos resampling (traditional method).

    Good quality for moderate upscaling (up to 2x).
    Fast and doesn't require additional dependencies.
    """
    try:
        # Load image
        img = Image.open(io.BytesIO(image_data))

        # Check if upscaling is needed
        if img.width >= target_width and img.height >= target_height:
            logger.debug("Image already meets target size, no upscaling needed")
            return image_data

        # Upscale using Lanczos filter
        upscaled = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        logger.info(f"Upscaled image from {img.width}x{img.height} to {target_width}x{target_height} using Lanczos")

        # Convert back to bytes
        output = io.BytesIO()
        # Preserve format or use PNG for quality
        format = img.format if img.format else 'PNG'
        upscaled.save(output, format=format, quality=95 if format == 'JPEG' else None)

        return output.getvalue()

    except Exception as e:
        logger.error(f"Lanczos upscaling failed: {e}")
        return image_data


def upscale_realesrgan(
    image_data: bytes,
    target_width: int,
    target_height: int,
    model_name: str = "RealESRGAN_x4plus",
    **kwargs
) -> bytes:
    """
    Upscale image using Real-ESRGAN AI model.

    Excellent quality for significant upscaling (4x or more).
    Requires realesrgan package and model weights.
    """
    if not REALESRGAN_AVAILABLE:
        logger.error("Real-ESRGAN not installed")
        return upscale_lanczos(image_data, target_width, target_height)

    try:
        # Load image
        img = Image.open(io.BytesIO(image_data))

        # Convert to numpy array
        img_array = np.array(img)

        # Initialize Real-ESRGAN model
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)

        # Get model path (you'll need to download the model weights)
        model_path = kwargs.get('model_path', 'weights/RealESRGAN_x4plus.pth')

        upsampler = RealESRGANer(
            scale=4,
            model_path=model_path,
            model=model,
            tile=0,
            tile_pad=10,
            pre_pad=0,
            half=False
        )

        # Upscale
        output, _ = upsampler.enhance(img_array, outscale=4)

        # Convert back to PIL Image
        upscaled_img = Image.fromarray(output)

        # Resize to exact target dimensions if needed
        if upscaled_img.width != target_width or upscaled_img.height != target_height:
            upscaled_img = upscaled_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        logger.info(f"Upscaled image to {target_width}x{target_height} using Real-ESRGAN")

        # Convert to bytes
        output_buffer = io.BytesIO()
        upscaled_img.save(output_buffer, format='PNG')

        return output_buffer.getvalue()

    except Exception as e:
        logger.error(f"Real-ESRGAN upscaling failed: {e}, falling back to Lanczos")
        return upscale_lanczos(image_data, target_width, target_height)


def upscale_stability_api(
    image_data: bytes,
    target_width: int,
    target_height: int,
    api_key: str = None,
    **kwargs
) -> bytes:
    """
    Upscale image using Stability AI's upscaling API.

    Professional quality upscaling via cloud API.
    Requires Stability AI API key and credits.
    """
    if not api_key:
        logger.error("Stability AI API key required for upscaling")
        return upscale_lanczos(image_data, target_width, target_height)

    try:
        import requests

        # Stability AI upscaling endpoint
        url = "https://api.stability.ai/v1/generation/esrgan-v1-x2plus/image-to-image/upscale"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }

        # Prepare the image file
        files = {
            "image": ("image.png", image_data, "image/png")
        }

        # Make the request
        response = requests.post(url, headers=headers, files=files)

        if response.status_code == 200:
            result = response.json()

            # Get the upscaled image
            if result.get("artifacts"):
                import base64
                upscaled_b64 = result["artifacts"][0]["base64"]
                upscaled_data = base64.b64decode(upscaled_b64)

                # If we need to resize to exact dimensions
                img = Image.open(io.BytesIO(upscaled_data))
                if img.width != target_width or img.height != target_height:
                    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    img.save(output, format='PNG')
                    upscaled_data = output.getvalue()

                logger.info(f"Upscaled image using Stability AI API")
                return upscaled_data
            else:
                logger.error("No image returned from Stability AI")
                return upscale_lanczos(image_data, target_width, target_height)
        else:
            logger.error(f"Stability AI API error: {response.status_code}")
            return upscale_lanczos(image_data, target_width, target_height)

    except Exception as e:
        logger.error(f"Stability AI upscaling failed: {e}, falling back to Lanczos")
        return upscale_lanczos(image_data, target_width, target_height)


def needs_upscaling(
    current_width: int,
    current_height: int,
    target_width: int,
    target_height: int
) -> bool:
    """
    Check if image needs upscaling to reach target dimensions.

    Returns True if either dimension is smaller than target.
    """
    return current_width < target_width or current_height < target_height


def get_upscaling_factor(
    current_width: int,
    current_height: int,
    target_width: int,
    target_height: int
) -> float:
    """
    Calculate the upscaling factor needed.

    Returns the maximum scaling factor needed for either dimension.
    """
    width_factor = target_width / current_width if current_width > 0 else 1.0
    height_factor = target_height / current_height if current_height > 0 else 1.0
    return max(width_factor, height_factor)