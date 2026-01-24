"""Package installer for GUI-based dependency installation."""

import subprocess
import sys
import logging
import requests
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from PySide6.QtCore import QThread, Signal, QObject

logger = logging.getLogger(__name__)


class PackageInstaller(QThread):
    """Thread for installing Python packages in the background."""

    progress = Signal(str)  # Progress message
    finished = Signal(bool, str)  # Success, message
    percentage = Signal(int)  # Progress percentage (0-100)

    def __init__(self, packages: List[str], update_requirements: bool = True, index_url: str = None):
        super().__init__()
        self.packages = packages
        self.update_requirements = update_requirements
        self.index_url = index_url
        self.should_stop = False

    def run(self):
        """Run the installation process."""
        try:
            # Track overall timing
            overall_start = time.time()
            start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.progress.emit(f"Starting package installation at {start_time_str}")
            logger.info(f"Installation started at {start_time_str}")
            self.percentage.emit(0)

            # Calculate steps for progress
            total_steps = len(self.packages) + (2 if self.update_requirements else 1)
            current_step = 0
            failed_packages = []  # Track packages that failed to install

            # Install each package
            for i, package in enumerate(self.packages):
                if self.should_stop:
                    self.finished.emit(False, "Installation cancelled by user")
                    return

                # Track individual package timing
                package_start = time.time()
                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Installing {package}...")
                logger.info(f"Starting installation of {package}")

                success, output = self._install_package(package)

                package_duration = time.time() - package_start
                duration_str = self._format_duration(package_duration)

                current_step += 1
                percentage = int((current_step / total_steps) * 100)
                self.percentage.emit(percentage)

                if not success:
                    # Check if it's a file locking error - continue with remaining packages
                    if "File is locked" in output or "WinError 5" in output or "Access is denied" in output:
                        logger.warning(f"Skipping {package} due to file lock, will continue with remaining packages")
                        self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Skipped {package} (file locked) - install manually after restart")
                        failed_packages.append((package, "file locked"))
                        continue
                    else:
                        # Other errors are fatal
                        logger.error(f"Failed to install {package} after {duration_str}: {output}")
                        self.finished.emit(False, f"Failed to install {package} after {duration_str}: {output}")
                        return

                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Installed {package} successfully ({duration_str})")
                logger.info(f"Installed {package} in {duration_str}")

            # Update requirements.txt if requested
            if self.update_requirements:
                req_start = time.time()
                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Updating requirements.txt...")
                self._update_requirements_file(self.packages)
                req_duration = time.time() - req_start
                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Updated requirements.txt ({self._format_duration(req_duration)})")
                current_step += 1
                self.percentage.emit(int((current_step / total_steps) * 100))

            # Calculate total duration
            overall_duration = time.time() - overall_start
            duration_str = self._format_duration(overall_duration)
            end_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Final success with timing
            self.percentage.emit(100)

            if failed_packages:
                # Partial success
                failed_names = [pkg for pkg, reason in failed_packages]
                self.progress.emit(f"[{end_time_str}] Installation completed with {len(failed_packages)} skipped package(s)")
                self.progress.emit(f"⚠️ Skipped (install manually after closing app): {', '.join(failed_names)}")
                self.progress.emit(f"Total installation time: {duration_str}")

                logger.warning(f"Installation completed with skipped packages: {failed_names}")
                logger.info(f"Total installation duration: {duration_str}")

                self.finished.emit(
                    True,
                    f"Partial install complete in {duration_str}. "
                    f"Skipped: {', '.join(failed_names)} (close app and install manually). "
                    f"Please restart the application."
                )
            else:
                # Full success
                self.progress.emit(f"[{end_time_str}] All packages installed successfully!")
                self.progress.emit(f"Total installation time: {duration_str}")

                logger.info(f"Installation completed at {end_time_str}")
                logger.info(f"Total installation duration: {duration_str}")

                self.finished.emit(True, f"Installation complete in {duration_str}. Please restart the application.")

        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self.finished.emit(False, f"Installation error: {str(e)}")

    def _install_package(self, package: str) -> Tuple[bool, str]:
        """
        Install a single package using pip.

        Returns:
            Tuple of (success, output_message)
        """
        try:
            # Build the pip install command
            cmd = [sys.executable, "-m", "pip", "install"]

            # Only use index-url for torch and torchvision packages
            # Other packages should use default PyPI
            if self.index_url and package.startswith(("torch==", "torchvision==")):
                cmd.extend(["--index-url", self.index_url])

            cmd.append(package)

            # Run pip install
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            # Log the output
            if result.stdout:
                for line in result.stdout.splitlines():
                    if line.strip():
                        self.progress.emit(f"  {line.strip()}")

            if result.returncode == 0:
                return True, "Success"
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"

                # Check for Windows file locking error (Access denied on .pyd files)
                if "WinError 5" in error_msg or "Access is denied" in error_msg:
                    logger.warning(f"File locked during {package} install, retrying with --ignore-installed")
                    self.progress.emit(f"  File locked, retrying with --ignore-installed...")

                    # Retry with --ignore-installed to skip locked dependencies
                    retry_cmd = [sys.executable, "-m", "pip", "install", "--ignore-installed"]
                    if self.index_url and package.startswith(("torch==", "torchvision==")):
                        retry_cmd.extend(["--index-url", self.index_url])
                    retry_cmd.append(package)

                    retry_result = subprocess.run(
                        retry_cmd,
                        capture_output=True,
                        text=True,
                        check=False
                    )

                    if retry_result.returncode == 0:
                        return True, "Success (with --ignore-installed)"
                    else:
                        # Still failed - provide helpful message
                        error_msg = (
                            f"File is locked by running application. "
                            f"Please restart ImageAI and try again, or install manually:\n"
                            f"  pip install {package}"
                        )

                logger.error(f"Failed to install {package}: {error_msg}")
                return False, error_msg

        except Exception as e:
            logger.error(f"Exception installing {package}: {e}")
            return False, str(e)

    def _update_requirements_file(self, packages: List[str]):
        """Update requirements.txt with newly installed packages."""
        try:
            req_file = Path("requirements.txt")

            # Read existing content
            existing_content = ""
            if req_file.exists():
                with open(req_file, 'r') as f:
                    existing_content = f.read()

            # Check if AI upscaling section already exists
            if "# AI Upscaling" not in existing_content:
                with open(req_file, 'a') as f:
                    f.write("\n# AI Upscaling (installed via GUI)\n")
                    f.write(f"# Installed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

                    # Add GPU info if available
                    has_gpu, gpu_name = detect_nvidia_gpu()
                    if has_gpu and gpu_name:
                        f.write(f"# GPU: {gpu_name} (CUDA accelerated)\n")
                    else:
                        f.write("# CPU-only version\n")

                    # Note about PyTorch index URL
                    if self.index_url:
                        if "cu" in self.index_url:
                            f.write(f"# PyTorch installed with CUDA support from {self.index_url}\n")
                        else:
                            f.write(f"# PyTorch CPU-only version from {self.index_url}\n")

                    for package in packages:
                        f.write(f"{package}\n")

                self.progress.emit("Updated requirements.txt successfully")
            else:
                self.progress.emit("requirements.txt already contains AI upscaling packages")

        except Exception as e:
            logger.error(f"Failed to update requirements.txt: {e}")
            self.progress.emit(f"Warning: Could not update requirements.txt: {str(e)}")

    def stop(self):
        """Request the installation to stop."""
        self.should_stop = True

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"


class ModelDownloader(QThread):
    """Thread for downloading AI model weights."""

    progress = Signal(str)  # Progress message
    finished = Signal(bool, str)  # Success, message
    percentage = Signal(int)  # Download percentage

    def __init__(self, model_url: str, model_path: Path):
        super().__init__()
        self.model_url = model_url
        self.model_path = model_path
        self.should_stop = False

    def run(self):
        """Download the model file."""
        try:
            start_time = time.time()
            start_time_str = datetime.now().strftime("%H:%M:%S")

            self.progress.emit(f"[{start_time_str}] Downloading model to {self.model_path.name}...")
            logger.info(f"Starting model download at {start_time_str}")

            # Create weights directory if it doesn't exist
            self.model_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if already exists
            if self.model_path.exists():
                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Model already downloaded")
                logger.info("Model file already exists, skipping download")
                self.finished.emit(True, "Model file already exists")
                return

            # Download with progress
            response = requests.get(self.model_url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_progress_time = time.time()

            with open(self.model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.should_stop:
                        f.close()
                        self.model_path.unlink()  # Delete partial file
                        self.finished.emit(False, "Download cancelled")
                        return

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percentage = int((downloaded / total_size) * 100)
                            self.percentage.emit(percentage)

                            # Show progress every second to avoid spam
                            current_time = time.time()
                            if current_time - last_progress_time >= 1.0:
                                # Calculate download speed
                                elapsed = current_time - start_time
                                speed_mbps = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0

                                # Estimate remaining time
                                remaining_bytes = total_size - downloaded
                                eta_seconds = remaining_bytes / (downloaded / elapsed) if downloaded > 0 else 0

                                # Show progress in MB with speed and ETA
                                downloaded_mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024)
                                eta_str = self._format_duration(eta_seconds)

                                self.progress.emit(
                                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                                    f"Downloaded {downloaded_mb:.1f}MB / {total_mb:.1f}MB "
                                    f"({speed_mbps:.1f} MB/s, ETA: {eta_str})"
                                )
                                last_progress_time = current_time

            # Calculate total duration
            duration = time.time() - start_time
            duration_str = self._format_duration(duration)
            end_time_str = datetime.now().strftime("%H:%M:%S")

            self.percentage.emit(100)
            self.progress.emit(f"[{end_time_str}] Model downloaded successfully in {duration_str}!")
            logger.info(f"Model download completed in {duration_str}")
            self.finished.emit(True, f"Model download complete ({duration_str})")

        except requests.RequestException as e:
            logger.error(f"Failed to download model: {e}")
            self.finished.emit(False, f"Download failed: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error downloading model: {e}")
            self.finished.emit(False, f"Download error: {str(e)}")

    def stop(self):
        """Request the download to stop."""
        self.should_stop = True

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"


def check_disk_space(required_gb: float = 7.5) -> Tuple[bool, str]:
    """
    Check if there's enough disk space for installation.

    Args:
        required_gb: Required space in gigabytes (default 7.5GB for PyTorch + Real-ESRGAN)

    Returns:
        Tuple of (has_space, message)
    """
    try:
        import shutil

        # Get disk usage for current directory
        stat = shutil.disk_usage(".")
        free_gb = stat.free / (1024 ** 3)

        if free_gb < required_gb:
            return False, f"Insufficient disk space. Need {required_gb:.1f}GB, have {free_gb:.1f}GB"

        return True, f"Sufficient disk space available ({free_gb:.1f}GB free)"

    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True, "Could not verify disk space"


def get_installed_packages() -> List[str]:
    """Get list of installed packages."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True
        )

        packages = []
        for line in result.stdout.splitlines():
            if "==" in line:
                package_name = line.split("==")[0].lower()
                packages.append(package_name)

        return packages

    except Exception as e:
        logger.error(f"Failed to get installed packages: {e}")
        return []


def is_package_installed(package_name: str) -> bool:
    """Check if a package is installed."""
    installed = get_installed_packages()
    return package_name.lower() in installed


def detect_nvidia_gpu() -> Tuple[bool, Optional[str]]:
    """
    Detect if NVIDIA GPU is available.

    Returns:
        Tuple of (has_gpu, gpu_name)
    """
    try:
        # Try nvidia-smi command (works on Windows and Linux)
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip().split('\n')[0]  # Get first GPU
            logger.info(f"Detected NVIDIA GPU: {gpu_name}")
            return True, gpu_name
    except Exception as e:
        logger.debug(f"nvidia-smi not available: {e}")

    # Fallback: check if CUDA runtime is available
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"Detected CUDA GPU via torch: {gpu_name}")
            return True, gpu_name
    except ImportError:
        logger.debug("PyTorch not installed, cannot check CUDA availability")
    except Exception as e:
        logger.debug(f"Error checking CUDA: {e}")

    logger.info("No NVIDIA GPU detected, will use CPU version")
    return False, None


def get_realesrgan_packages() -> Tuple[List[str], str]:
    """
    Get the list of packages needed for Real-ESRGAN with GPU support detection.

    Returns:
        Tuple of (packages_list, index_url)
    """
    has_gpu, gpu_name = detect_nvidia_gpu()

    packages = []
    index_url = ""

    if has_gpu:
        # CUDA 12.1 version for NVIDIA GPUs
        # This works with RTX 40 series and most modern GPUs
        index_url = "https://download.pytorch.org/whl/cu121"
        logger.info(f"Will install CUDA-accelerated PyTorch for {gpu_name}")
    else:
        # CPU-only version (smaller download)
        index_url = "https://download.pytorch.org/whl/cpu"
        logger.info("Will install CPU-only PyTorch")

    # PyTorch and torchvision with compatible versions
    # IMPORTANT: basicsr 1.4.2 requires torchvision < 0.23 due to import changes
    # torchvision 0.23+ moved functional_tensor to functional module
    # Using PyTorch 2.4.1 with torchvision 0.19.1 for compatibility
    packages.extend([
        "torch==2.4.1",
        "torchvision==0.19.1",
    ])

    # Real-ESRGAN packages (install from PyPI, not PyTorch index)
    packages.extend([
        "opencv-python",  # Latest version from PyPI
        "basicsr>=1.4.2",
        "realesrgan>=0.3.0"
    ])

    return packages, index_url


def get_model_info() -> dict:
    """Get information about Real-ESRGAN models."""
    return {
        "RealESRGAN_x4plus": {
            "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            "size_mb": 64,
            "description": "General purpose 4x upscaling"
        },
        "RealESRGAN_x4plus_anime": {
            "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
            "size_mb": 17,
            "description": "Optimized for anime/artwork"
        },
        "RealESRGAN_x2plus": {
            "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
            "size_mb": 64,
            "description": "2x upscaling model"
        }
    }


# =============================================================================
# Character Animator Puppet Automation
# =============================================================================

def get_puppet_ai_packages() -> Tuple[List[str], str]:
    """
    Get the list of packages needed for Character Animator puppet automation.

    Similar to get_realesrgan_packages() but for puppet generation:
    - SAM 2 (Segment Anything Model)
    - MediaPipe (Pose and Face detection)
    - Depth-Anything (Depth estimation)
    - Diffusers (Stable Diffusion inpainting)

    Returns:
        Tuple of (packages_list, index_url_for_torch)
    """
    has_gpu, gpu_name = detect_nvidia_gpu()

    packages = []
    index_url = ""

    if has_gpu:
        # CUDA 12.1 version for NVIDIA GPUs
        index_url = "https://download.pytorch.org/whl/cu121"
        logger.info(f"Will install CUDA-accelerated PyTorch for {gpu_name}")
    else:
        # CPU-only version (smaller download)
        index_url = "https://download.pytorch.org/whl/cpu"
        logger.info("Will install CPU-only PyTorch")

    # PyTorch and torchvision with compatible versions
    packages.extend([
        "torch>=2.5.1",  # Required by sam2
        "torchvision>=0.20.1",  # Required by sam2
    ])

    # Segmentation
    packages.append("sam2")  # Official Meta SAM 2 package from PyPI

    # Pose/Face detection
    packages.append("mediapipe>=0.10.0")

    # Note: Depth estimation and local inpainting removed in favor of cloud AI editing
    # See Plans/AICharacterGenerator.md for details

    # Export tools
    packages.extend([
        "psd-tools>=1.9.0",
        "svgwrite>=1.4.0",
    ])

    return packages, index_url


def get_puppet_model_info() -> dict:
    """
    Get information about Character Animator puppet models.

    Returns:
        Dictionary with model information including URLs and sizes
    """
    return {
        "sam2_hiera_large": {
            "url": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt",
            "size_mb": 897,
            "description": "SAM 2 Large model for precise segmentation",
            "required": True,
        },
        "sam2_hiera_base": {
            "url": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_base_plus.pt",
            "size_mb": 323,
            "description": "SAM 2 Base model (faster, smaller)",
            "required": False,
        },
        # Note: SD Inpainting and ControlNet removed in favor of cloud AI editing
        # Viseme generation now uses Gemini/OpenAI image editing APIs
    }


def check_puppet_disk_space() -> Tuple[bool, str]:
    """
    Check if there's enough disk space for puppet automation installation.

    Puppet automation requires approximately:
    - PyTorch: ~3GB
    - SAM 2: ~900MB
    - MediaPipe + export tools: ~500MB
    Total: ~5GB minimum (reduced after removing local SD inpainting)

    Returns:
        Tuple of (has_space, message)
    """
    return check_disk_space(5.0)  # 5GB recommended (cloud AI for visemes)