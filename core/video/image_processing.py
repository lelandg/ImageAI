"""
Image processing utilities for video projects.

Handles cropping, aspect ratio adjustments, and Ken Burns calculations.
"""

import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List
from PIL import Image, ImageFilter
import numpy as np

from .project_enhancements import CropMode, CropSettings, KenBurnsSettings


class ImageProcessor:
    """Handles image cropping and processing for video projects"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_image_dimensions(self, image_path: Path) -> Tuple[int, int]:
        """Get image dimensions without loading full image"""
        with Image.open(image_path) as img:
            return img.size
    
    def calculate_crop_box(self, image_size: Tuple[int, int], 
                          target_aspect: float,
                          crop_settings: CropSettings) -> Tuple[int, int, int, int]:
        """
        Calculate crop box coordinates.
        
        Args:
            image_size: Original image (width, height)
            target_aspect: Target aspect ratio (width/height)
            crop_settings: Crop settings with mode and position
            
        Returns:
            Crop box (left, top, right, bottom)
        """
        width, height = image_size
        current_aspect = width / height
        
        if abs(current_aspect - target_aspect) < 0.01:
            # Already correct aspect ratio
            return (0, 0, width, height)
        
        if current_aspect > target_aspect:
            # Image is wider - crop width
            new_width = int(height * target_aspect)
            new_height = height
        else:
            # Image is taller - crop height
            new_width = width
            new_height = int(width / target_aspect)
        
        # Calculate position based on mode
        if crop_settings.mode == CropMode.CENTER:
            left = (width - new_width) // 2
            top = (height - new_height) // 2
            
        elif crop_settings.mode == CropMode.TOP:
            left = (width - new_width) // 2
            top = 0
            
        elif crop_settings.mode == CropMode.BOTTOM:
            left = (width - new_width) // 2
            top = height - new_height
            
        elif crop_settings.mode == CropMode.MANUAL:
            # Use manual position (0-1 normalized)
            left = int((width - new_width) * crop_settings.position["x"])
            top = int((height - new_height) * crop_settings.position["y"])
            
        elif crop_settings.mode == CropMode.RULE_OF_THIRDS:
            # Position at rule of thirds intersection
            left = int((width - new_width) * 0.33)
            top = int((height - new_height) * 0.33)
            
        elif crop_settings.mode == CropMode.SMART:
            # Would use face detection or saliency detection here
            # For now, fallback to center
            left = (width - new_width) // 2
            top = (height - new_height) // 2
        
        else:
            # Default to center
            left = (width - new_width) // 2
            top = (height - new_height) // 2
        
        # Ensure within bounds
        left = max(0, min(left, width - new_width))
        top = max(0, min(top, height - new_height))
        
        right = left + new_width
        bottom = top + new_height
        
        return (left, top, right, bottom)
    
    def crop_image(self, input_path: Path, output_path: Path,
                  target_aspect: float, crop_settings: CropSettings) -> Path:
        """
        Crop image to target aspect ratio.
        
        Args:
            input_path: Path to input image
            output_path: Path for output image
            target_aspect: Target aspect ratio
            crop_settings: Crop settings
            
        Returns:
            Path to cropped image
        """
        with Image.open(input_path) as img:
            crop_box = self.calculate_crop_box(img.size, target_aspect, crop_settings)
            cropped = img.crop(crop_box)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save with high quality
            cropped.save(output_path, quality=95, optimize=True)
            
        self.logger.info(f"Cropped {input_path.name} to {crop_box}")
        return output_path
    
    def create_blurred_background(self, image_path: Path, output_size: Tuple[int, int],
                                 blur_radius: int = 20) -> Image.Image:
        """
        Create a blurred background for letterboxing.
        
        Args:
            image_path: Path to image
            output_size: Target size (width, height)
            blur_radius: Blur radius for background
            
        Returns:
            Blurred background image
        """
        with Image.open(image_path) as img:
            # Scale to fill entire frame
            img_aspect = img.width / img.height
            out_aspect = output_size[0] / output_size[1]
            
            if img_aspect > out_aspect:
                # Scale by height
                scale = output_size[1] / img.height
            else:
                # Scale by width
                scale = output_size[0] / img.width
            
            new_size = (int(img.width * scale * 1.2), int(img.height * scale * 1.2))
            scaled = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Crop to output size
            left = (scaled.width - output_size[0]) // 2
            top = (scaled.height - output_size[1]) // 2
            background = scaled.crop((left, top, left + output_size[0], top + output_size[1]))
            
            # Apply blur
            background = background.filter(ImageFilter.GaussianBlur(blur_radius))
            
            return background
    
    def calculate_ken_burns_path(self, image_size: Tuple[int, int],
                               output_size: Tuple[int, int],
                               ken_burns: KenBurnsSettings,
                               duration: float) -> List[Dict[str, float]]:
        """
        Calculate Ken Burns animation path.
        
        Args:
            image_size: Original image size
            output_size: Output video size
            ken_burns: Ken Burns settings
            duration: Scene duration in seconds
            
        Returns:
            List of keyframes with position and scale
        """
        if not ken_burns.enabled:
            return []
        
        width, height = image_size
        out_width, out_height = output_size
        
        # Calculate keyframes
        keyframes = []
        
        # Start position
        start_x = ken_burns.start["x"] * width
        start_y = ken_burns.start["y"] * height
        start_scale = ken_burns.start["scale"]
        
        # End position
        end_x = ken_burns.end["x"] * width
        end_y = ken_burns.end["y"] * height
        end_scale = ken_burns.end["scale"]
        
        # Generate interpolated keyframes
        num_frames = int(duration * 30)  # Assuming 30 fps
        
        for i in range(num_frames):
            t = i / (num_frames - 1) if num_frames > 1 else 0
            
            # Apply easing
            if ken_burns.easing == "ease-in":
                t = t * t
            elif ken_burns.easing == "ease-out":
                t = 1 - (1 - t) * (1 - t)
            elif ken_burns.easing == "ease-in-out":
                t = t * t * (3 - 2 * t)
            # else linear (no change to t)
            
            # Interpolate position and scale
            x = start_x + (end_x - start_x) * t
            y = start_y + (end_y - start_y) * t
            scale = start_scale + (end_scale - start_scale) * t
            
            keyframes.append({
                "time": i / 30.0,
                "x": x,
                "y": y,
                "scale": scale
            })
        
        return keyframes
    
    def detect_faces(self, image_path: Path) -> List[Tuple[int, int, int, int]]:
        """
        Detect faces in image for smart cropping.
        
        Args:
            image_path: Path to image
            
        Returns:
            List of face bounding boxes (x, y, width, height)
        """
        # This would use OpenCV or similar for face detection
        # For now, return empty list
        return []
    
    def calculate_saliency_map(self, image_path: Path) -> np.ndarray:
        """
        Calculate saliency map for smart cropping.
        
        Args:
            image_path: Path to image
            
        Returns:
            Saliency map as numpy array
        """
        # This would use computer vision techniques
        # For now, return center-weighted map
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Create simple center-weighted map
            y, x = np.ogrid[:height, :width]
            center_x, center_y = width / 2, height / 2
            
            # Gaussian-like weight centered on image
            sigma = min(width, height) / 3
            saliency = np.exp(-((x - center_x)**2 + (y - center_y)**2) / (2 * sigma**2))
            
            return saliency
    
    def find_optimal_crop_position(self, image_path: Path, 
                                  target_aspect: float) -> Dict[str, float]:
        """
        Find optimal crop position using smart detection.
        
        Args:
            image_path: Path to image
            target_aspect: Target aspect ratio
            
        Returns:
            Optimal position as {"x": 0-1, "y": 0-1}
        """
        # Try face detection first
        faces = self.detect_faces(image_path)
        if faces:
            # Center on faces
            avg_x = sum(f[0] + f[2]/2 for f in faces) / len(faces)
            avg_y = sum(f[1] + f[3]/2 for f in faces) / len(faces)
            
            with Image.open(image_path) as img:
                return {
                    "x": avg_x / img.width,
                    "y": avg_y / img.height
                }
        
        # Fall back to saliency
        saliency = self.calculate_saliency_map(image_path)
        
        # Find center of mass of saliency
        total = np.sum(saliency)
        if total > 0:
            y_coords, x_coords = np.meshgrid(
                np.arange(saliency.shape[0]),
                np.arange(saliency.shape[1]),
                indexing='ij'
            )
            
            center_x = np.sum(x_coords * saliency) / total
            center_y = np.sum(y_coords * saliency) / total
            
            return {
                "x": center_x / saliency.shape[1],
                "y": center_y / saliency.shape[0]
            }
        
        # Default to center
        return {"x": 0.5, "y": 0.5}
    
    def generate_crop_preview(self, image_path: Path, 
                            target_aspect: float,
                            crop_settings: CropSettings,
                            preview_size: Tuple[int, int] = (400, 300)) -> Image.Image:
        """
        Generate a preview of the crop.
        
        Args:
            image_path: Path to image
            target_aspect: Target aspect ratio
            crop_settings: Crop settings
            preview_size: Size for preview image
            
        Returns:
            Preview image showing crop area
        """
        with Image.open(image_path) as img:
            # Calculate crop box
            crop_box = self.calculate_crop_box(img.size, target_aspect, crop_settings)
            
            # Create preview with overlay
            preview = img.copy()
            preview.thumbnail(preview_size, Image.Resampling.LANCZOS)
            
            # Scale crop box to preview size
            scale = preview.width / img.width
            scaled_box = tuple(int(c * scale) for c in crop_box)
            
            # Draw crop area (would use ImageDraw here)
            # For now, just return the thumbnail
            return preview