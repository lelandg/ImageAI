"""
Package installer for Character Animator puppet automation.

Handles lazy installation of heavy AI dependencies:
- SAM 2 (Segment Anything Model)
- MediaPipe (Pose and Face detection)
- Depth-Anything (Depth estimation)
- Diffusers (Stable Diffusion inpainting)

Follows the pattern established by core/package_installer.py for Real-ESRGAN.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.constants import get_user_data_dir

logger = logging.getLogger(__name__)

# =============================================================================
# Package Definitions
# =============================================================================

# Grouped packages for installation progress tracking
PUPPET_PACKAGES: Dict[str, List[str]] = {
    "core": [
        "psd-tools>=1.9.0",
        "svgwrite>=1.4.0",
        "scipy>=1.10.0",
    ],
    "segmentation": [
        "sam2",  # Official Meta SAM 2 package from PyPI
    ],
    "pose_detection": [
        "mediapipe>=0.10.0,<0.10.15",  # Pin to version with mp.solutions API (removed in 0.10.15+)
    ],
    "depth_estimation": [
        # Depth-Anything is used via transformers + HuggingFace model
        # (LiheYoung/depth-anything-large-hf) - no separate package needed
        "transformers>=4.35.0",
    ],
    "inpainting": [
        "diffusers>=0.25.0",
        "accelerate>=0.25.0",
        "controlnet-aux>=0.0.7",
    ],
}

# Packages always required (should be in requirements.txt)
LIGHTWEIGHT_PACKAGES = PUPPET_PACKAGES["core"]

# Heavy AI packages (install on first use)
HEAVY_AI_PACKAGES = (
    PUPPET_PACKAGES["segmentation"] +
    PUPPET_PACKAGES["pose_detection"] +
    PUPPET_PACKAGES["depth_estimation"] +
    PUPPET_PACKAGES["inpainting"]
)

# Model information for downloads
PUPPET_MODELS: Dict[str, Dict] = {
    "sam2_hiera_large": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt",
        "size_mb": 897,
        "description": "SAM 2 Large model for precise segmentation",
        "filename": "sam2_hiera_large.pt",
    },
    "sam2_hiera_base": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_base_plus.pt",
        "size_mb": 323,
        "description": "SAM 2 Base model (faster, smaller)",
        "filename": "sam2_hiera_base_plus.pt",
    },
    "depth_anything_large": {
        "url": "https://huggingface.co/LiheYoung/depth-anything-large-hf",
        "size_mb": 1400,
        "description": "Depth-Anything Large model",
        "filename": "depth_anything_large",  # HuggingFace repo
        "is_hf_repo": True,
    },
    "controlnet_openpose": {
        "url": "https://huggingface.co/lllyasviel/control_v11p_sd15_openpose",
        "size_mb": 1400,
        "description": "ControlNet OpenPose for pose-guided inpainting",
        "filename": "control_v11p_sd15_openpose",
        "is_hf_repo": True,
    },
    "sdxl_inpainting": {
        "url": "https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
        "size_mb": 6500,
        "description": "SDXL Inpainting model (best quality)",
        "filename": "stable-diffusion-xl-1.0-inpainting-0.1",
        "is_hf_repo": True,
    },
}


def get_puppet_packages(include_torch: bool = True) -> Tuple[List[str], str]:
    """
    Get the list of packages needed for puppet automation with GPU detection.

    Args:
        include_torch: Whether to include PyTorch (skip if already installed)

    Returns:
        Tuple of (packages_list, index_url_for_torch)
    """
    from core.package_installer import detect_nvidia_gpu

    has_gpu, gpu_name = detect_nvidia_gpu()
    packages = []
    index_url = ""

    if include_torch:
        if has_gpu:
            # CUDA 12.8 version for NVIDIA GPUs (RTX 40-series compatible)
            index_url = "https://download.pytorch.org/whl/cu128"
            logger.info(f"Will install CUDA-accelerated PyTorch for {gpu_name}")
            packages.extend([
                "torch>=2.5.1",  # Required by sam2
                "torchvision>=0.20.1",  # Required by sam2
            ])
        else:
            # CPU-only version
            index_url = "https://download.pytorch.org/whl/cpu"
            logger.info("Will install CPU-only PyTorch")
            packages.extend([
                "torch>=2.5.1",  # Required by sam2
                "torchvision>=0.20.1",  # Required by sam2
            ])

    # Add all AI packages
    packages.extend(HEAVY_AI_PACKAGES)

    return packages, index_url


def check_dependencies() -> Dict[str, bool]:
    """
    Check which AI modules are installed.

    Returns:
        Dictionary mapping component name to installation status
    """
    status = {}

    # Check PyTorch
    try:
        import torch
        status["torch"] = True
        status["torch_cuda"] = torch.cuda.is_available()
    except ImportError:
        status["torch"] = False
        status["torch_cuda"] = False

    # Check SAM 2
    try:
        from sam2.build_sam import build_sam2
        status["sam2"] = True
    except ImportError:
        status["sam2"] = False

    # Check MediaPipe
    try:
        import mediapipe
        status["mediapipe"] = True
    except ImportError:
        status["mediapipe"] = False

    # Check Depth-Anything
    try:
        from transformers import AutoModelForDepthEstimation
        status["depth_anything"] = True
    except ImportError:
        status["depth_anything"] = False

    # Check Diffusers (for inpainting)
    try:
        from diffusers import StableDiffusionInpaintPipeline
        status["diffusers"] = True
    except ImportError:
        status["diffusers"] = False

    # Check ControlNet
    try:
        from diffusers import ControlNetModel
        status["controlnet"] = True
    except ImportError:
        status["controlnet"] = False

    # Check PSD tools
    try:
        from psd_tools import PSDImage
        status["psd_tools"] = True
    except ImportError:
        status["psd_tools"] = False

    # Check SVG tools
    try:
        import svgwrite
        status["svgwrite"] = True
    except ImportError:
        status["svgwrite"] = False

    return status


def get_missing_packages() -> List[str]:
    """
    Get list of missing packages that need to be installed.

    Returns:
        List of package names that are not installed
    """
    missing = []
    status = check_dependencies()

    # Map status keys to package names
    package_map = {
        "torch": "torch>=2.5.1",  # Required by sam2
        "sam2": "sam2",  # Official Meta SAM 2 package from PyPI
        "mediapipe": "mediapipe>=0.10.0,<0.10.15",
        "depth_anything": "transformers>=4.35.0",  # For Depth-Anything via HuggingFace
        "diffusers": "diffusers>=0.25.0",
        "controlnet": "controlnet-aux>=0.0.7",
        "psd_tools": "psd-tools>=1.9.0",
        "svgwrite": "svgwrite>=1.4.0",
    }

    for key, package in package_map.items():
        if not status.get(key, False):
            missing.append(package)

    return missing


def get_model_paths() -> Dict[str, Path]:
    """
    Get paths where models should be stored.

    Returns:
        Dictionary mapping model name to file path
    """
    # Use a weights directory in the user data folder
    weights_dir = get_user_data_dir() / "weights" / "character_animator"

    paths = {}
    for model_name, model_info in PUPPET_MODELS.items():
        if model_info.get("is_hf_repo"):
            # HuggingFace models are cached in ~/.cache/huggingface
            paths[model_name] = Path.home() / ".cache" / "huggingface" / "hub" / model_info["filename"]
        else:
            paths[model_name] = weights_dir / model_info["filename"]

    return paths


def get_missing_models() -> List[str]:
    """
    Get list of models that haven't been downloaded.

    Returns:
        List of model names that need downloading
    """
    missing = []
    paths = get_model_paths()

    for model_name, path in paths.items():
        if not path.exists():
            missing.append(model_name)

    return missing


def get_install_info() -> Dict:
    """
    Get comprehensive installation information for UI display.

    Returns:
        Dictionary with installation details
    """
    from core.package_installer import detect_nvidia_gpu, check_disk_space

    has_gpu, gpu_name = detect_nvidia_gpu()
    has_space, space_msg = check_disk_space(12.0)  # Need ~12GB for all components

    packages, _ = get_puppet_packages()
    missing_packages = get_missing_packages()
    missing_models = get_missing_models()

    # Calculate total download size
    total_model_size = sum(
        PUPPET_MODELS[m]["size_mb"] for m in missing_models
    )

    return {
        "has_gpu": has_gpu,
        "gpu_name": gpu_name,
        "has_disk_space": has_space,
        "disk_space_message": space_msg,
        "packages_to_install": missing_packages,
        "models_to_download": missing_models,
        "total_package_count": len(packages),
        "missing_package_count": len(missing_packages),
        "missing_model_count": len(missing_models),
        "total_model_size_mb": total_model_size,
        "estimated_download_gb": (total_model_size / 1024) + 3.0,  # Add ~3GB for packages
    }


def is_fully_installed() -> bool:
    """
    Check if all dependencies and models are installed.

    Returns:
        True if everything is ready to use
    """
    missing_packages = get_missing_packages()
    missing_models = get_missing_models()
    return len(missing_packages) == 0 and len(missing_models) == 0


def get_pytorch_install_command(use_cuda: bool = True) -> List[str]:
    """
    Get the pip command for installing PyTorch.

    Args:
        use_cuda: Whether to install CUDA version

    Returns:
        List of command arguments
    """
    if use_cuda:
        return [
            sys.executable, "-m", "pip", "install",
            "torch>=2.4.1", "torchvision>=0.19.1",
            "--index-url", "https://download.pytorch.org/whl/cu121"
        ]
    else:
        return [
            sys.executable, "-m", "pip", "install",
            "torch>=2.4.1", "torchvision>=0.19.1",
            "--index-url", "https://download.pytorch.org/whl/cpu"
        ]


def estimate_install_time(missing_packages: List[str], missing_models: List[str]) -> str:
    """
    Estimate installation time based on what needs to be installed.

    Returns:
        Human-readable time estimate string
    """
    # Base estimates in minutes
    time_min = 0

    # Package install times (rough estimates)
    if "torch" in str(missing_packages):
        time_min += 5  # PyTorch is large

    if any("sam" in p.lower() for p in missing_packages):
        time_min += 2

    if any("diffusers" in p.lower() for p in missing_packages):
        time_min += 3

    time_min += len(missing_packages) * 0.5  # Half minute per other package

    # Model download times (at ~10MB/s assumed)
    for model in missing_models:
        if model in PUPPET_MODELS:
            size_mb = PUPPET_MODELS[model]["size_mb"]
            time_min += size_mb / 600  # 10MB/s = 600MB/min

    if time_min < 1:
        return "Less than 1 minute"
    elif time_min < 60:
        return f"About {int(time_min)} minutes"
    else:
        hours = time_min / 60
        return f"About {hours:.1f} hours"
