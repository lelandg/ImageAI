"""Package installer for Whisper audio analysis installation."""

import subprocess
import sys
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
from PySide6.QtCore import QThread, Signal

from core.package_installer import detect_nvidia_gpu, check_disk_space

logger = logging.getLogger(__name__)


def check_whisper_installed() -> Tuple[bool, str]:
    """
    Check if Whisper and required audio packages are installed.

    Uses importlib.util.find_spec() to check without importing,
    avoiding conflicts with numba and main.py's print patching.

    Returns:
        Tuple of (is_installed, status_message)
    """
    import importlib.util

    # Check for whisper-timestamped (preferred) or openai-whisper
    whisper_installed = False
    whisper_type = None

    if importlib.util.find_spec("whisper_timestamped") is not None:
        whisper_installed = True
        whisper_type = "whisper-timestamped"
    elif importlib.util.find_spec("whisper") is not None:
        whisper_installed = True
        whisper_type = "openai-whisper"

    if not whisper_installed:
        return False, "Whisper not installed"

    # Check for torchaudio
    if importlib.util.find_spec("torchaudio") is None:
        return False, f"{whisper_type} installed but torchaudio is missing"

    # Check for soundfile (Windows audio backend)
    if importlib.util.find_spec("soundfile") is None:
        return False, f"{whisper_type} installed but soundfile is missing"

    return True, f"{whisper_type} is fully installed with audio support"


def get_whisper_packages() -> Tuple[List[str], str]:
    """
    Get the list of packages needed for Whisper with GPU support detection.

    Returns:
        Tuple of (packages_list, index_url)
    """
    has_gpu, gpu_name = detect_nvidia_gpu()

    packages = []
    index_url = ""

    if has_gpu:
        # CUDA 12.1 version for NVIDIA GPUs
        index_url = "https://download.pytorch.org/whl/cu121"
        logger.info(f"Will install CUDA-accelerated PyTorch for {gpu_name}")
    else:
        # CPU-only version
        index_url = "https://download.pytorch.org/whl/cpu"
        logger.info("Will install CPU-only PyTorch")

    # Check if PyTorch is already installed to avoid reinstalling
    try:
        import torch
        torch_version = torch.__version__
        logger.info(f"PyTorch {torch_version} already installed, skipping")
    except ImportError:
        # PyTorch and torchaudio with compatible versions
        packages.extend([
            "torch==2.4.1",
            "torchaudio==2.4.1",
        ])

    # Check if torchaudio is installed
    try:
        import torchaudio
        logger.info(f"torchaudio already installed, skipping")
    except ImportError:
        if "torchaudio==2.4.1" not in packages:
            packages.append("torchaudio==2.4.1")

    # Audio processing dependencies
    packages.extend([
        "soundfile",  # Backend for torchaudio on Windows
        "ffmpeg-python",  # Audio format handling
    ])

    # Whisper packages (prefer whisper-timestamped for better word timing)
    packages.append("whisper-timestamped")

    return packages, index_url


def get_whisper_disk_space_required() -> float:
    """Get total disk space required for Whisper installation in GB."""
    # PyTorch (if not installed): ~2GB
    # torchaudio: ~50MB
    # Whisper + models: ~500MB for base model
    # Buffer: 0.5GB
    return 3.0


class WhisperPackageInstaller(QThread):
    """Thread for installing Whisper Python packages."""

    progress = Signal(str)  # Progress message
    finished = Signal(bool, str)  # Success, message
    percentage = Signal(int)  # Progress percentage (0-100)

    def __init__(self, packages: List[str], index_url: str = None):
        super().__init__()
        self.packages = packages
        self.index_url = index_url
        self.should_stop = False

    def run(self):
        """Run the installation process."""
        try:
            overall_start = time.time()
            start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.progress.emit(f"Starting Whisper package installation at {start_time_str}")
            logger.info(f"Whisper installation started at {start_time_str}")
            self.percentage.emit(0)

            total_steps = len(self.packages)

            for i, package in enumerate(self.packages):
                if self.should_stop:
                    self.finished.emit(False, "Installation cancelled by user")
                    return

                package_start = time.time()
                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Installing {package}...")
                logger.info(f"Starting installation of {package}")

                success, output = self._install_package(package)

                package_duration = time.time() - package_start
                duration_str = self._format_duration(package_duration)

                if not success:
                    logger.error(f"Failed to install {package} after {duration_str}: {output}")
                    self.finished.emit(False, f"Failed to install {package}: {output}")
                    return

                percentage = int(((i + 1) / total_steps) * 100)
                self.percentage.emit(percentage)

                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Installed {package} ({duration_str})")
                logger.info(f"Installed {package} in {duration_str}")

            overall_duration = time.time() - overall_start
            duration_str = self._format_duration(overall_duration)

            self.percentage.emit(100)
            self.progress.emit(f"All packages installed successfully in {duration_str}")
            logger.info(f"Whisper package installation completed in {duration_str}")

            self.finished.emit(True, f"Installation complete in {duration_str}")

        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self.finished.emit(False, f"Installation error: {str(e)}")

    def _install_package(self, package: str) -> Tuple[bool, str]:
        """Install a single package using pip."""
        try:
            cmd = [sys.executable, "-m", "pip", "install"]

            # Use index-url for torch packages only
            if self.index_url and package.startswith(("torch==", "torchaudio==")):
                cmd.extend(["--index-url", self.index_url])

            cmd.append(package)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.stdout:
                for line in result.stdout.splitlines():
                    if line.strip():
                        self.progress.emit(f"  {line.strip()}")

            if result.returncode == 0:
                return True, "Success"
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                return False, error_msg

        except Exception as e:
            return False, str(e)

    def stop(self):
        """Request the installation to stop."""
        self.should_stop = True

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"
