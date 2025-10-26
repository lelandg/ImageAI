#!/usr/bin/env python3
"""
LTX-Video Local Installation Script

This script automates the setup of LTX-Video for local GPU deployment.
It checks GPU compatibility, installs dependencies, and downloads models.
"""

import sys
import subprocess
import platform
import logging
from pathlib import Path
from typing import Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LTXVideoInstaller:
    """Handles LTX-Video local installation and setup"""

    def __init__(self, install_dir: Optional[Path] = None):
        """
        Initialize the installer

        Args:
            install_dir: Directory to install LTX-Video (default: ~/.cache/ltx-video)
        """
        if install_dir is None:
            install_dir = Path.home() / ".cache" / "ltx-video"

        self.install_dir = install_dir
        self.models_dir = self.install_dir / "models"
        self.venv_dir = self.install_dir / "venv"

    def check_gpu(self) -> Tuple[bool, str]:
        """
        Check for NVIDIA GPU and CUDA support

        Returns:
            Tuple of (has_gpu, gpu_info)
        """
        logger.info("Checking for NVIDIA GPU...")

        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                cuda_version = torch.version.cuda

                logger.info(f"✓ GPU detected: {gpu_name}")
                logger.info(f"  VRAM: {gpu_memory:.1f} GB")
                logger.info(f"  CUDA: {cuda_version}")

                if gpu_memory < 20:
                    logger.warning(f"⚠ GPU has {gpu_memory:.1f}GB VRAM. LTX-Video recommends 24GB+ (RTX 4090)")
                    logger.warning("  You may experience issues with Ultra model or longer videos")

                return True, gpu_name
            else:
                logger.error("✗ No CUDA-compatible GPU detected")
                logger.error("  LTX-Video requires an NVIDIA GPU with CUDA support")
                return False, "No GPU"

        except ImportError:
            logger.error("✗ PyTorch not installed. Run: pip install torch torchvision")
            return False, "PyTorch not installed"

    def check_dependencies(self) -> bool:
        """
        Check if required dependencies are installed

        Returns:
            True if all dependencies are available
        """
        logger.info("Checking dependencies...")

        required = [
            ("torch", "PyTorch with CUDA"),
            ("diffusers", "Hugging Face Diffusers"),
            ("transformers", "Hugging Face Transformers"),
            ("accelerate", "Accelerate"),
            ("safetensors", "SafeTensors"),
        ]

        missing = []
        for package, name in required:
            try:
                __import__(package)
                logger.info(f"✓ {name}")
            except ImportError:
                logger.error(f"✗ {name}")
                missing.append(package)

        if missing:
            logger.error(f"\nMissing dependencies: {', '.join(missing)}")
            logger.error("Install with: pip install -r requirements-ltx.txt")
            return False

        return True

    def create_directories(self):
        """Create necessary directories"""
        logger.info("Creating directories...")

        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"✓ Install directory: {self.install_dir}")
        logger.info(f"✓ Models directory: {self.models_dir}")

    def download_models(self, model: str = "ltx-video-2b") -> bool:
        """
        Download LTX-Video models from Hugging Face

        Args:
            model: Model to download (ltx-video-2b, ltx-video-13b)

        Returns:
            True if successful
        """
        logger.info(f"Downloading {model} model from Hugging Face...")
        logger.info("This may take several minutes depending on your connection...")

        try:
            from huggingface_hub import snapshot_download

            model_path = self.models_dir / model

            if model_path.exists():
                logger.info(f"✓ Model already exists: {model_path}")
                return True

            # Download model
            repo_id = f"Lightricks/{model}"
            logger.info(f"Downloading from {repo_id}...")

            snapshot_download(
                repo_id=repo_id,
                local_dir=model_path,
                local_dir_use_symlinks=False
            )

            logger.info(f"✓ Model downloaded: {model_path}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to download model: {e}")
            logger.error("  Make sure you have accepted the model license on Hugging Face")
            logger.error(f"  Visit: https://huggingface.co/Lightricks/{model}")
            return False

    def verify_installation(self) -> bool:
        """
        Verify the installation is complete

        Returns:
            True if installation is valid
        """
        logger.info("Verifying installation...")

        # Check directories
        if not self.install_dir.exists():
            logger.error("✗ Install directory not found")
            return False

        # Check for at least one model
        if not any(self.models_dir.iterdir()):
            logger.error("✗ No models found")
            return False

        logger.info("✓ Installation verified")
        return True

    def run_test_generation(self) -> bool:
        """
        Run a test video generation to verify everything works

        Returns:
            True if test successful
        """
        logger.info("\nRunning test generation...")
        logger.info("Generating a 2-second test video...")

        try:
            from providers.ltx_video import LTXVideoClient, LTXGenerationConfig, LTXDeploymentMode

            client = LTXVideoClient(deployment=LTXDeploymentMode.LOCAL_GPU)
            config = LTXGenerationConfig(
                prompt="A cat playing with a ball of yarn",
                duration=2,  # Short test
                resolution="720p"  # Lower resolution for testing
            )

            result = client.generate_video_sync(config)

            if result.success:
                logger.info(f"✓ Test generation successful!")
                logger.info(f"  Output: {result.video_path}")
                return True
            else:
                logger.error(f"✗ Test generation failed: {result.error}")
                return False

        except Exception as e:
            logger.error(f"✗ Test generation error: {e}")
            return False

    def install(self, skip_test: bool = False) -> bool:
        """
        Run the full installation process

        Args:
            skip_test: Skip the test generation

        Returns:
            True if installation successful
        """
        logger.info("=" * 60)
        logger.info("LTX-Video Local Installation")
        logger.info("=" * 60)

        # Step 1: Check GPU
        has_gpu, gpu_info = self.check_gpu()
        if not has_gpu:
            logger.error("\n✗ Installation failed: No compatible GPU")
            return False

        # Step 2: Check dependencies
        if not self.check_dependencies():
            logger.error("\n✗ Installation failed: Missing dependencies")
            return False

        # Step 3: Create directories
        self.create_directories()

        # Step 4: Download models
        if not self.download_models("ltx-video-2b"):
            logger.error("\n✗ Installation failed: Could not download models")
            return False

        # Step 5: Verify installation
        if not self.verify_installation():
            logger.error("\n✗ Installation failed: Verification failed")
            return False

        # Step 6: Test generation (optional)
        if not skip_test:
            if not self.run_test_generation():
                logger.warning("\n⚠ Installation complete but test generation failed")
                logger.warning("  You may need to troubleshoot before using LTX-Video")
                return False

        logger.info("\n" + "=" * 60)
        logger.info("✓ LTX-Video installation complete!")
        logger.info("=" * 60)
        logger.info(f"\nInstallation directory: {self.install_dir}")
        logger.info(f"Models directory: {self.models_dir}")
        logger.info("\nYou can now use LTX-Video in ImageAI:")
        logger.info("  python main.py --provider ltx-video -p \"Your prompt\"")

        return True


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Install LTX-Video for local GPU deployment"
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        help="Installation directory (default: ~/.cache/ltx-video)"
    )
    parser.add_argument(
        "--model",
        choices=["ltx-video-2b", "ltx-video-13b"],
        default="ltx-video-2b",
        help="Model to download (default: ltx-video-2b)"
    )
    parser.add_argument(
        "--skip-test",
        action="store_true",
        help="Skip test generation"
    )

    args = parser.parse_args()

    installer = LTXVideoInstaller(install_dir=args.install_dir)
    success = installer.install(skip_test=args.skip_test)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
