"""Package installer for MuseTalk lip-sync installation."""

import subprocess
import sys
import logging
import requests
import time
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from PySide6.QtCore import QThread, Signal

from core.package_installer import detect_nvidia_gpu, check_disk_space

logger = logging.getLogger(__name__)


# Model definitions for MuseTalk
MUSETALK_MODELS = {
    "musetalk": {
        "repo": "TMElyralab/MuseTalk",
        "files": ["musetalk/musetalk.json", "musetalk/pytorch_model.bin"],
        "size_mb": 1500,
        "description": "MuseTalk core model"
    },
    "dwpose": {
        "repo": "yzd-v/DWPose",
        "files": ["dw-ll_ucoco_384.pth"],
        "size_mb": 300,
        "description": "DWPose body detection"
    },
    "face-parse-bisent": {
        "url": "https://github.com/zllrunning/face-parsing.PyTorch/releases/download/79999_iter.pth/79999_iter.pth",
        "files": ["79999_iter.pth"],
        "size_mb": 95,
        "description": "Face parsing model"
    },
    "resnet18": {
        "url": "https://download.pytorch.org/models/resnet18-5c106cde.pth",
        "files": ["resnet18-5c106cde.pth"],
        "size_mb": 45,
        "description": "ResNet18 backbone"
    },
    "sd-vae-ft-mse": {
        "repo": "stabilityai/sd-vae-ft-mse",
        "files": ["config.json", "diffusion_pytorch_model.bin"],
        "size_mb": 335,
        "description": "Stable Diffusion VAE"
    },
    "whisper": {
        "url": "https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt",
        "files": ["tiny.pt"],
        "size_mb": 75,
        "description": "Whisper tiny model"
    }
}


def get_musetalk_model_path() -> Path:
    """
    Get the platform-specific model storage path for MuseTalk.

    Returns:
        Path to the MuseTalk model directory
    """
    import platform

    system = platform.system()

    if system == "Windows":
        base = Path.home() / "AppData" / "Roaming" / "ImageAI" / "musetalk"
    elif system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support" / "ImageAI" / "musetalk"
    else:  # Linux and others
        base = Path.home() / ".cache" / "imageai" / "musetalk"

    return base


def check_musetalk_installed() -> Tuple[bool, str]:
    """
    Check if MuseTalk is fully installed.

    Returns:
        Tuple of (is_installed, status_message)
    """
    # Check pip packages
    required_packages = [
        "torch", "torchvision", "torchaudio", "soundfile",
        "mmengine", "mmcv", "mmdet", "mmpose",
        "diffusers", "transformers", "accelerate", "av"
    ]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True
        )

        installed = {line.split("==")[0].lower() for line in result.stdout.splitlines() if "==" in line}

        missing_packages = [pkg for pkg in required_packages if pkg.lower() not in installed]

        if missing_packages:
            return False, f"Missing packages: {', '.join(missing_packages)}"

    except Exception as e:
        logger.error(f"Failed to check packages: {e}")
        return False, f"Failed to check packages: {e}"

    # Check model files
    model_path = get_musetalk_model_path()

    required_files = [
        model_path / "musetalk" / "pytorch_model.bin",
        model_path / "dwpose" / "dw-ll_ucoco_384.pth",
        model_path / "face-parse-bisent" / "79999_iter.pth",
        model_path / "sd-vae-ft-mse" / "diffusion_pytorch_model.bin",
        model_path / "whisper" / "tiny.pt"
    ]

    missing_models = [str(f) for f in required_files if not f.exists()]

    if missing_models:
        return False, f"Missing model files: {len(missing_models)} files"

    return True, "MuseTalk is fully installed"


def get_musetalk_packages() -> Tuple[List[str], str]:
    """
    Get the list of packages needed for MuseTalk with GPU support detection.

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

    # PyTorch and torchvision - compatible versions
    packages.extend([
        "torch==2.4.1",
        "torchvision==0.19.1",
        "torchaudio==2.4.1",  # For audio loading in lip-sync
        "soundfile",  # Backend for torchaudio on Windows
    ])

    # MMLab stack - required for pose detection
    packages.extend([
        "mmengine",
        "mmcv>=2.0.1",
        "mmdet>=3.1.0",
        "mmpose>=1.1.0",
    ])

    # MuseTalk specific dependencies
    packages.extend([
        "diffusers>=0.21.0",
        "transformers>=4.30.0",
        "accelerate",
        "av",  # Video processing
        "opencv-python",
        "numpy",
        "tqdm",
        "einops",
        "omegaconf",
    ])

    return packages, index_url


class MuseTalkPackageInstaller(QThread):
    """Thread for installing MuseTalk Python packages."""

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

            self.progress.emit(f"Starting MuseTalk package installation at {start_time_str}")
            logger.info(f"MuseTalk installation started at {start_time_str}")
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
            logger.info(f"Package installation completed in {duration_str}")

            self.finished.emit(True, f"Package installation complete in {duration_str}")

        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self.finished.emit(False, f"Installation error: {str(e)}")

    def _install_package(self, package: str) -> Tuple[bool, str]:
        """Install a single package using pip."""
        try:
            # Special handling for mmpose - it has dependencies with broken build systems:
            # - chumpy: tries to import pip directly in setup.py
            # - xtcocotools: tries to import numpy in setup.py before it's installed
            #   AND has no prebuilt wheel for Python 3.12+ on Windows
            # We handle these specially to avoid build failures
            if package.startswith("mmpose"):
                # Ensure setuptools is available for --no-build-isolation to work
                self.progress.emit("  Ensuring setuptools is available for build...")
                setup_success, setup_msg = self._ensure_setuptools()
                if not setup_success:
                    return False, f"Failed to install setuptools: {setup_msg}"

                problematic_deps = [
                    ("chumpy", "tries to import pip in setup.py"),
                    ("xtcocotools", "no prebuilt wheel for Python 3.12+ on Windows"),
                ]
                for dep_name, reason in problematic_deps:
                    self.progress.emit(f"  Pre-installing {dep_name} ({reason})...")
                    dep_success, dep_msg = self._install_with_no_isolation(dep_name)
                    if not dep_success:
                        return False, f"Failed to install {dep_name} dependency: {dep_msg}"
                    if "Skipped" in dep_msg:
                        self.progress.emit(f"  {dep_name}: {dep_msg}")
                    else:
                        self.progress.emit(f"  {dep_name} installed successfully")

            cmd = [sys.executable, "-m", "pip", "install"]

            # Use index-url for torch packages only
            if self.index_url and package.startswith(("torch==", "torchvision==")):
                cmd.extend(["--index-url", self.index_url])

            # For mmpose on Windows with Python 3.12+, use --no-deps to avoid xtcocotools
            # then install the other dependencies manually
            import platform
            import sys as sys_module
            if (package.startswith("mmpose") and
                platform.system() == "Windows" and
                sys_module.version_info >= (3, 12)):
                self.progress.emit("  Installing mmpose without xtcocotools dependency...")
                cmd.extend(["--no-deps"])
                cmd.append(package)

                # Run the no-deps install first
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode != 0:
                    error_msg = result.stderr if result.stderr else "Unknown error"
                    return False, error_msg

                # Now install mmpose's other dependencies (excluding xtcocotools)
                mmpose_deps = [
                    "matplotlib", "munkres", "json-tricks", "scipy", "numpy",
                    "pillow", "opencv-python", "tqdm"
                ]
                self.progress.emit("  Installing mmpose dependencies (excluding xtcocotools)...")
                for dep in mmpose_deps:
                    dep_result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", dep, "--quiet"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    # Ignore failures for already-installed packages
                    if dep_result.returncode != 0 and "already satisfied" not in dep_result.stdout.lower():
                        self.progress.emit(f"    Warning: {dep} may not have installed correctly")

                return True, "Success"

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

    def _ensure_setuptools(self) -> Tuple[bool, str]:
        """Ensure setuptools and wheel are installed for --no-build-isolation builds."""
        try:
            cmd = [
                sys.executable, "-m", "pip", "install",
                "setuptools", "wheel", "--quiet"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                return True, "Success"
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                return False, error_msg

        except Exception as e:
            return False, str(e)

    def _install_with_no_isolation(self, package_name: str) -> Tuple[bool, str]:
        """
        Install a package with --no-build-isolation to work around broken setup.py files.

        Some packages have setup.py files that try to import modules (like pip or numpy)
        that aren't available in pip's isolated build environments. Using --no-build-isolation
        allows them to use the existing environment's installed packages.
        """
        import platform

        # Special handling for xtcocotools on Windows - use prebuilt wheel
        if package_name == "xtcocotools" and platform.system() == "Windows":
            return self._install_xtcocotools_windows()

        try:
            cmd = [
                sys.executable, "-m", "pip", "install",
                package_name,
                "--no-build-isolation"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                return True, "Success"
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                return False, error_msg

        except Exception as e:
            return False, str(e)

    def _install_xtcocotools_windows(self) -> Tuple[bool, str]:
        """
        Install xtcocotools on Windows using prebuilt wheel.

        xtcocotools has a broken build system that fails on Windows because:
        1. It tries to compile C extensions but the source tarball is missing _mask.c
        2. Even with Visual C++ installed, the build fails
        3. No prebuilt wheel for Python 3.12+ exists on PyPI (only up to 3.11)

        Solution: Install mmpose without the xtcocotools dependency since:
        - xtcocotools is only needed for COCO dataset evaluation metrics
        - MuseTalk lip-sync doesn't use COCO evaluation, only pose detection
        """
        import sys

        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        self.progress.emit(f"  xtcocotools has no prebuilt wheel for Python {python_version} on Windows")
        self.progress.emit("  xtcocotools is only needed for COCO evaluation (not used by MuseTalk)")

        # Check if we're on Python 3.11 or older where wheels exist
        if sys.version_info >= (3, 12):
            self.progress.emit("  Skipping xtcocotools - mmpose will work without it for inference")
            logger.info("Skipping xtcocotools on Python 3.12+ Windows - not available as prebuilt wheel")
            return True, "Skipped (Python 3.12+ not supported)"

        # For Python 3.11 and older, try the normal install
        try:
            cmd = [
                sys.executable, "-m", "pip", "install",
                "xtcocotools"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                return True, "Success"
            else:
                # Fallback: skip it, mmpose inference still works
                self.progress.emit("  xtcocotools install failed, but mmpose will work for inference")
                return True, "Skipped (build failed)"

        except Exception as e:
            logger.warning(f"xtcocotools install error: {e}")
            return True, "Skipped (error)"

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


class MuseTalkModelDownloader(QThread):
    """Thread for downloading MuseTalk model weights."""

    progress = Signal(str)  # Progress message
    finished = Signal(bool, str)  # Success, message
    percentage = Signal(int)  # Download percentage

    def __init__(self):
        super().__init__()
        self.should_stop = False
        self.model_path = get_musetalk_model_path()

    def run(self):
        """Download all required models."""
        try:
            start_time = time.time()
            self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Starting model downloads...")
            logger.info("Starting MuseTalk model downloads")

            # Create base directory
            self.model_path.mkdir(parents=True, exist_ok=True)

            # Download each model
            models_to_download = [
                ("musetalk", self._download_musetalk_model),
                ("dwpose", self._download_dwpose_model),
                ("face-parse", self._download_face_parse_model),
                ("sd-vae", self._download_vae_model),
                ("whisper", self._download_whisper_model),
            ]

            total_models = len(models_to_download)

            for i, (name, download_func) in enumerate(models_to_download):
                if self.should_stop:
                    self.finished.emit(False, "Download cancelled by user")
                    return

                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Downloading {name}...")

                try:
                    success = download_func()
                    if not success:
                        self.finished.emit(False, f"Failed to download {name}")
                        return
                except Exception as e:
                    logger.error(f"Error downloading {name}: {e}")
                    self.finished.emit(False, f"Error downloading {name}: {e}")
                    return

                percentage = int(((i + 1) / total_models) * 100)
                self.percentage.emit(percentage)
                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] Downloaded {name}")

            duration = time.time() - start_time
            duration_str = self._format_duration(duration)

            self.progress.emit(f"All models downloaded in {duration_str}")
            logger.info(f"Model downloads completed in {duration_str}")
            self.finished.emit(True, f"Model download complete in {duration_str}")

        except Exception as e:
            logger.error(f"Model download failed: {e}")
            self.finished.emit(False, f"Download error: {str(e)}")

    def _download_musetalk_model(self) -> bool:
        """Download MuseTalk core model from HuggingFace with direct URL fallback."""
        model_dir = self.model_path / "musetalk"
        model_dir.mkdir(parents=True, exist_ok=True)

        model_bin = model_dir / "pytorch_model.bin"
        model_json = model_dir / "musetalk.json"

        # Check if already exists
        if model_bin.exists() and model_json.exists():
            self.progress.emit("  MuseTalk model already exists, skipping")
            return True

        # Direct URLs (HuggingFace CDN - works without auth for public repos)
        files_to_download = [
            (
                "https://huggingface.co/TMElyralab/MuseTalk/resolve/main/musetalk/pytorch_model.bin",
                model_bin,
                "pytorch_model.bin"
            ),
            (
                "https://huggingface.co/TMElyralab/MuseTalk/resolve/main/musetalk/musetalk.json",
                model_json,
                "musetalk.json"
            ),
        ]

        for url, dest, name in files_to_download:
            if dest.exists():
                self.progress.emit(f"  {name} already exists, skipping")
                continue

            self.progress.emit(f"  Downloading {name}...")
            if not self._download_file(url, dest):
                # Try HuggingFace Hub as fallback
                self.progress.emit(f"  Direct download failed, trying HuggingFace Hub...")
                if not self._download_via_hf_hub("TMElyralab/MuseTalk", f"musetalk/{name}", dest):
                    logger.error(f"Failed to download {name}")
                    return False

        return True

    def _download_via_hf_hub(self, repo_id: str, filename: str, dest: Path) -> bool:
        """Download a file using HuggingFace Hub library as fallback."""
        try:
            from huggingface_hub import hf_hub_download

            # Download to a temp location then move
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=dest.parent.parent,
                local_dir_use_symlinks=False
            )

            # hf_hub_download creates nested dirs, move file to expected location
            downloaded_path = Path(downloaded)
            if downloaded_path.exists() and downloaded_path != dest:
                import shutil
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(downloaded_path), str(dest))

            return dest.exists()

        except ImportError:
            self.progress.emit("  Installing huggingface_hub...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "huggingface_hub"],
                    check=True, capture_output=True
                )
                return self._download_via_hf_hub(repo_id, filename, dest)
            except Exception as e:
                logger.error(f"Failed to install huggingface_hub: {e}")
                return False
        except Exception as e:
            logger.error(f"HuggingFace Hub download failed for {filename}: {e}")
            return False

    def _download_dwpose_model(self) -> bool:
        """Download DWPose model with direct URL fallback."""
        model_dir = self.model_path / "dwpose"
        model_dir.mkdir(parents=True, exist_ok=True)

        model_file = model_dir / "dw-ll_ucoco_384.pth"

        if model_file.exists():
            self.progress.emit("  DWPose model already exists, skipping")
            return True

        # Direct URL (HuggingFace CDN)
        url = "https://huggingface.co/yzd-v/DWPose/resolve/main/dw-ll_ucoco_384.pth"

        self.progress.emit("  Downloading dw-ll_ucoco_384.pth...")
        if not self._download_file(url, model_file):
            # Try HuggingFace Hub as fallback
            self.progress.emit("  Direct download failed, trying HuggingFace Hub...")
            if not self._download_via_hf_hub("yzd-v/DWPose", "dw-ll_ucoco_384.pth", model_file):
                logger.error("Failed to download DWPose model")
                return False

        return True

    def _download_face_parse_model(self) -> bool:
        """Download face parsing model."""
        model_dir = self.model_path / "face-parse-bisent"
        model_dir.mkdir(parents=True, exist_ok=True)

        # Main face parsing model - from HuggingFace (GitHub releases URL is broken)
        model_file = model_dir / "79999_iter.pth"
        if not model_file.exists():
            # Primary: HuggingFace CDN
            url = "https://huggingface.co/vivym/face-parsing-bisenet/resolve/main/79999_iter.pth"
            self.progress.emit("  Downloading 79999_iter.pth...")
            if not self._download_file(url, model_file):
                # Fallback: Try huggingface_hub
                self.progress.emit("  Direct download failed, trying HuggingFace Hub...")
                if not self._download_via_hf_hub("vivym/face-parsing-bisenet", "79999_iter.pth", model_file):
                    logger.error("Failed to download face parsing model")
                    return False

        # ResNet18 backbone
        resnet_file = model_dir / "resnet18-5c106cde.pth"
        if not resnet_file.exists():
            self.progress.emit("  Downloading resnet18-5c106cde.pth...")
            url = "https://download.pytorch.org/models/resnet18-5c106cde.pth"
            if not self._download_file(url, resnet_file):
                return False

        return True

    def _download_vae_model(self) -> bool:
        """Download Stable Diffusion VAE model with direct URL fallback."""
        model_dir = self.model_path / "sd-vae-ft-mse"
        model_dir.mkdir(parents=True, exist_ok=True)

        config_file = model_dir / "config.json"
        model_file = model_dir / "diffusion_pytorch_model.bin"

        if config_file.exists() and model_file.exists():
            self.progress.emit("  VAE model already exists, skipping")
            return True

        # Direct URLs (HuggingFace CDN)
        files_to_download = [
            (
                "https://huggingface.co/stabilityai/sd-vae-ft-mse/resolve/main/config.json",
                config_file,
                "config.json"
            ),
            (
                "https://huggingface.co/stabilityai/sd-vae-ft-mse/resolve/main/diffusion_pytorch_model.bin",
                model_file,
                "diffusion_pytorch_model.bin"
            ),
        ]

        for url, dest, name in files_to_download:
            if dest.exists():
                self.progress.emit(f"  {name} already exists, skipping")
                continue

            self.progress.emit(f"  Downloading {name}...")
            if not self._download_file(url, dest):
                # Try HuggingFace Hub as fallback
                self.progress.emit(f"  Direct download failed, trying HuggingFace Hub...")
                if not self._download_via_hf_hub("stabilityai/sd-vae-ft-mse", name, dest):
                    logger.error(f"Failed to download VAE {name}")
                    return False

        return True

    def _download_whisper_model(self) -> bool:
        """Download Whisper tiny model."""
        model_dir = self.model_path / "whisper"
        model_dir.mkdir(parents=True, exist_ok=True)

        model_file = model_dir / "tiny.pt"
        if model_file.exists():
            self.progress.emit("  Whisper model already exists, skipping")
            return True

        url = "https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt"
        return self._download_file(url, model_file)

    def _download_file(self, url: str, dest: Path) -> bool:
        """Download a file with progress tracking."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_progress_time = time.time()
            start_time = time.time()

            with open(dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.should_stop:
                        f.close()
                        dest.unlink()
                        return False

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            current_time = time.time()
                            if current_time - last_progress_time >= 1.0:
                                elapsed = current_time - start_time
                                speed_mbps = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                                downloaded_mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024)

                                self.progress.emit(
                                    f"  {downloaded_mb:.1f}MB / {total_mb:.1f}MB ({speed_mbps:.1f} MB/s)"
                                )
                                last_progress_time = current_time

            return True

        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return False

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


def get_musetalk_disk_space_required() -> float:
    """Get total disk space required for MuseTalk installation in GB."""
    # Packages: ~2GB (PyTorch + dependencies)
    # Models: ~2.5GB
    # Buffer: 0.5GB
    return 5.0
