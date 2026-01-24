"""
Availability checks for Character Animator dependencies.

Provides lazy-loaded flags indicating which AI modules are available.
Follows the pattern from core/upscaling.py for REALESRGAN_AVAILABLE.
"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# Availability Flags
# =============================================================================

# These flags are set at import time via try/except
# They allow the rest of the code to check availability without triggering imports

SEGMENTATION_AVAILABLE = False
POSE_DETECTION_AVAILABLE = False
PSD_EXPORT_AVAILABLE = False
SVG_EXPORT_AVAILABLE = False
AI_EDITING_AVAILABLE = False  # Cloud AI for viseme generation (Gemini/OpenAI)

# Check SAM 2 (Segment Anything)
try:
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    SEGMENTATION_AVAILABLE = True
    logger.debug("SAM 2 segmentation available")
except ImportError:
    logger.debug("SAM 2 not installed - segmentation unavailable")

# Check MediaPipe for pose/face detection
try:
    import mediapipe as mp
    POSE_DETECTION_AVAILABLE = True
    logger.debug("MediaPipe pose detection available")
except ImportError:
    logger.debug("MediaPipe not installed - pose detection unavailable")

# Check for cloud AI image editing availability (Gemini or OpenAI)
# This requires API keys to be configured, checked at runtime
try:
    # Check if we have the google.genai or openai packages installed
    _has_google = False
    _has_openai = False
    try:
        import google.genai
        _has_google = True
    except ImportError:
        pass
    try:
        import openai
        _has_openai = True
    except ImportError:
        pass
    AI_EDITING_AVAILABLE = _has_google or _has_openai
    if AI_EDITING_AVAILABLE:
        providers = []
        if _has_google:
            providers.append("Gemini")
        if _has_openai:
            providers.append("OpenAI")
        logger.debug(f"Cloud AI editing available via: {', '.join(providers)}")
    else:
        logger.debug("No cloud AI providers installed for image editing")
except Exception as e:
    logger.debug(f"Error checking AI editing availability: {e}")

# Check PSD export
try:
    from psd_tools import PSDImage
    PSD_EXPORT_AVAILABLE = True
    logger.debug("PSD export available")
except ImportError:
    logger.debug("psd-tools not installed - PSD export unavailable")

# Check SVG export
try:
    import svgwrite
    SVG_EXPORT_AVAILABLE = True
    logger.debug("SVG export available")
except ImportError:
    logger.debug("svgwrite not installed - SVG export unavailable")


# =============================================================================
# Utility Functions
# =============================================================================

def check_all_dependencies() -> Dict[str, bool]:
    """
    Check all Character Animator dependencies.

    Returns:
        Dictionary mapping dependency name to availability status
    """
    status = {
        "segmentation": SEGMENTATION_AVAILABLE,
        "pose_detection": POSE_DETECTION_AVAILABLE,
        "ai_editing": AI_EDITING_AVAILABLE,
        "psd_export": PSD_EXPORT_AVAILABLE,
        "svg_export": SVG_EXPORT_AVAILABLE,
    }

    # Additional detailed checks
    status["torch"] = False
    status["torch_cuda"] = False
    try:
        import torch
        status["torch"] = True
        status["torch_cuda"] = torch.cuda.is_available()
    except ImportError:
        pass

    return status


def get_missing_dependencies() -> List[str]:
    """
    Get list of missing dependencies.

    Returns:
        List of human-readable dependency names that are not installed
    """
    missing = []
    status = check_all_dependencies()

    dependency_names = {
        "torch": "PyTorch",
        "segmentation": "SAM 2 (Segment Anything)",
        "pose_detection": "MediaPipe",
        "ai_editing": "Cloud AI (Gemini or OpenAI)",
        "psd_export": "PSD Tools",
        "svg_export": "SVG Writer",
    }

    for key, name in dependency_names.items():
        if not status.get(key, False):
            missing.append(name)

    return missing


def get_install_status_message() -> str:
    """
    Get a human-readable status message for the current installation state.

    Returns:
        Status message suitable for UI display
    """
    status = check_all_dependencies()
    missing = get_missing_dependencies()

    if len(missing) == 0:
        return "All Character Animator dependencies are installed and ready."

    # Check if partially installed
    installed_count = sum(1 for v in status.values() if v)
    total_count = len(status)

    if installed_count == 0:
        return (
            "Character Animator AI components are not installed.\n"
            "Click 'Install AI Components' to download and set up:\n"
            f"  - {', '.join(missing)}"
        )

    return (
        f"Partially installed ({installed_count}/{total_count} components).\n"
        f"Missing: {', '.join(missing)}\n"
        "Click 'Install AI Components' to complete setup."
    )


def can_create_puppet() -> Tuple[bool, str]:
    """
    Check if the system can create puppets with current installation.

    Returns:
        Tuple of (can_create, reason_if_not)
    """
    # Minimum requirements for basic puppet creation
    if not POSE_DETECTION_AVAILABLE:
        return False, "MediaPipe is required for pose and face detection"

    if not PSD_EXPORT_AVAILABLE and not SVG_EXPORT_AVAILABLE:
        return False, "Either PSD or SVG export capability is required"

    # Check if we can do full features
    warnings = []
    if not SEGMENTATION_AVAILABLE:
        warnings.append("SAM 2 not available - using basic segmentation")
    if not AI_EDITING_AVAILABLE:
        warnings.append("Cloud AI not available - cannot generate visemes automatically (configure Gemini or OpenAI API)")

    if warnings:
        return True, f"Limited mode: {'; '.join(warnings)}"

    return True, "Full functionality available"


def is_full_installation() -> bool:
    """
    Check if all features are available (full installation).

    Returns:
        True if all AI features are available
    """
    return all([
        SEGMENTATION_AVAILABLE,
        POSE_DETECTION_AVAILABLE,
        AI_EDITING_AVAILABLE,
        PSD_EXPORT_AVAILABLE,
    ])


def get_feature_availability() -> Dict[str, Dict]:
    """
    Get detailed feature availability for UI display.

    Returns:
        Dictionary with feature information including name, available status, and description
    """
    return {
        "segmentation": {
            "name": "Advanced Segmentation",
            "available": SEGMENTATION_AVAILABLE,
            "description": "SAM 2 for precise body part separation",
            "package": "sam2",
        },
        "pose_detection": {
            "name": "Pose & Face Detection",
            "available": POSE_DETECTION_AVAILABLE,
            "description": "MediaPipe for pose landmarks and face mesh",
            "package": "mediapipe>=0.10.0,<0.10.15",  # Requires legacy mp.solutions API
        },
        "ai_editing": {
            "name": "Cloud AI Editing",
            "available": AI_EDITING_AVAILABLE,
            "description": "Gemini/OpenAI for viseme and expression generation",
            "package": "google-genai or openai",
        },
        "psd_export": {
            "name": "PSD Export",
            "available": PSD_EXPORT_AVAILABLE,
            "description": "Export to Photoshop format",
            "package": "psd-tools>=1.9.0",
        },
        "svg_export": {
            "name": "SVG Export",
            "available": SVG_EXPORT_AVAILABLE,
            "description": "Export to vector SVG format",
            "package": "svgwrite>=1.4.0",
        },
    }


def get_gpu_info() -> Dict:
    """
    Get GPU information for installation decisions.

    Returns:
        Dictionary with GPU detection results
    """
    info = {
        "available": False,
        "name": None,
        "cuda_version": None,
        "memory_gb": None,
    }

    try:
        import torch
        if torch.cuda.is_available():
            info["available"] = True
            info["name"] = torch.cuda.get_device_name(0)
            info["cuda_version"] = torch.version.cuda

            # Get memory
            props = torch.cuda.get_device_properties(0)
            info["memory_gb"] = props.total_memory / (1024**3)
    except ImportError:
        # Try nvidia-smi fallback
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(',')
                info["available"] = True
                info["name"] = parts[0].strip()
                if len(parts) > 1:
                    info["memory_gb"] = float(parts[1].strip()) / 1024
        except Exception:
            pass

    return info
