"""
Thumbnail management for video project scenes.

This module handles thumbnail generation, caching, and display
for video project scenes and generated images.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont
import io


class ThumbnailManager:
    """Manages thumbnails for video project scenes"""
    
    DEFAULT_THUMB_SIZE = (160, 90)  # 16:9 aspect ratio
    STORYBOARD_THUMB_SIZE = (320, 180)
    CACHE_VERSION = "v1"
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize thumbnail manager.
        
        Args:
            cache_dir: Directory for thumbnail cache
        """
        self.cache_dir = cache_dir or Path.home() / ".imageai" / "cache" / "thumbnails"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def create_thumbnail(self,
                        image_data: bytes,
                        size: Tuple[int, int] = None,
                        maintain_aspect: bool = True) -> bytes:
        """
        Create thumbnail from image data.
        
        Args:
            image_data: Original image bytes
            size: Target thumbnail size (width, height)
            maintain_aspect: Maintain aspect ratio
            
        Returns:
            Thumbnail image bytes
        """
        if size is None:
            size = self.DEFAULT_THUMB_SIZE
        
        try:
            # Open image
            img = Image.open(io.BytesIO(image_data))
            
            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            if maintain_aspect:
                # Calculate aspect-preserving size
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Create centered thumbnail with padding
                thumb = Image.new('RGB', size, (240, 240, 240))
                # Center the image
                x = (size[0] - img.width) // 2
                y = (size[1] - img.height) // 2
                thumb.paste(img, (x, y))
            else:
                # Resize to exact dimensions
                thumb = img.resize(size, Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = io.BytesIO()
            thumb.save(output, format='JPEG', quality=85, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            self.logger.error(f"Failed to create thumbnail: {e}")
            return self._create_error_thumbnail(size)
    
    def create_scene_thumbnail(self,
                              scene_images: List[bytes],
                              scene_title: str = "",
                              size: Tuple[int, int] = None) -> bytes:
        """
        Create composite thumbnail for a scene with multiple images.
        
        Args:
            scene_images: List of image bytes (up to 4 will be shown)
            scene_title: Optional title to overlay
            size: Target size
            
        Returns:
            Composite thumbnail bytes
        """
        if size is None:
            size = self.STORYBOARD_THUMB_SIZE
        
        if not scene_images:
            return self._create_placeholder_thumbnail(size, "No Images")
        
        try:
            # Create composite image
            composite = Image.new('RGB', size, (240, 240, 240))
            
            # Determine layout based on image count
            num_images = min(4, len(scene_images))
            
            if num_images == 1:
                # Single image fills the thumbnail
                thumb = self.create_thumbnail(scene_images[0], size)
                img = Image.open(io.BytesIO(thumb))
                composite.paste(img, (0, 0))
            
            elif num_images == 2:
                # Side by side
                w = size[0] // 2
                h = size[1]
                for i, img_data in enumerate(scene_images[:2]):
                    thumb = self.create_thumbnail(img_data, (w, h))
                    img = Image.open(io.BytesIO(thumb))
                    composite.paste(img, (i * w, 0))
            
            elif num_images == 3:
                # One large on left, two small on right
                w_large = size[0] * 2 // 3
                w_small = size[0] // 3
                h_small = size[1] // 2
                
                # Large image on left
                thumb = self.create_thumbnail(scene_images[0], (w_large, size[1]))
                img = Image.open(io.BytesIO(thumb))
                composite.paste(img, (0, 0))
                
                # Two small on right
                for i, img_data in enumerate(scene_images[1:3]):
                    thumb = self.create_thumbnail(img_data, (w_small, h_small))
                    img = Image.open(io.BytesIO(thumb))
                    composite.paste(img, (w_large, i * h_small))
            
            else:  # 4 images
                # 2x2 grid
                w = size[0] // 2
                h = size[1] // 2
                for i, img_data in enumerate(scene_images[:4]):
                    thumb = self.create_thumbnail(img_data, (w, h))
                    img = Image.open(io.BytesIO(thumb))
                    x = (i % 2) * w
                    y = (i // 2) * h
                    composite.paste(img, (x, y))
            
            # Add title overlay if provided
            if scene_title:
                self._add_title_overlay(composite, scene_title)
            
            # Add image count badge if more than 4
            if len(scene_images) > 4:
                self._add_count_badge(composite, len(scene_images))
            
            # Save to bytes
            output = io.BytesIO()
            composite.save(output, format='JPEG', quality=85)
            return output.getvalue()
            
        except Exception as e:
            self.logger.error(f"Failed to create scene thumbnail: {e}")
            return self._create_error_thumbnail(size)
    
    def get_cached_thumbnail(self, 
                           image_hash: str,
                           size: Tuple[int, int]) -> Optional[bytes]:
        """
        Retrieve cached thumbnail if available.
        
        Args:
            image_hash: Hash of original image
            size: Thumbnail size
            
        Returns:
            Cached thumbnail bytes or None
        """
        cache_key = f"{image_hash}_{size[0]}x{size[1]}_{self.CACHE_VERSION}"
        cache_path = self.cache_dir / f"{cache_key}.jpg"
        
        if cache_path.exists():
            try:
                return cache_path.read_bytes()
            except Exception as e:
                self.logger.warning(f"Failed to read cached thumbnail: {e}")
        
        return None
    
    def cache_thumbnail(self,
                       image_hash: str,
                       thumbnail_data: bytes,
                       size: Tuple[int, int]):
        """
        Cache a thumbnail for future use.
        
        Args:
            image_hash: Hash of original image
            thumbnail_data: Thumbnail bytes
            size: Thumbnail size
        """
        cache_key = f"{image_hash}_{size[0]}x{size[1]}_{self.CACHE_VERSION}"
        cache_path = self.cache_dir / f"{cache_key}.jpg"
        
        try:
            cache_path.write_bytes(thumbnail_data)
        except Exception as e:
            self.logger.warning(f"Failed to cache thumbnail: {e}")
    
    def create_thumbnail_with_cache(self,
                                   image_data: bytes,
                                   size: Tuple[int, int] = None) -> bytes:
        """
        Create thumbnail with caching support.
        
        Args:
            image_data: Original image bytes
            size: Target size
            
        Returns:
            Thumbnail bytes
        """
        if size is None:
            size = self.DEFAULT_THUMB_SIZE
        
        # Calculate hash for cache key
        image_hash = hashlib.sha256(image_data).hexdigest()[:16]
        
        # Check cache
        cached = self.get_cached_thumbnail(image_hash, size)
        if cached:
            return cached
        
        # Create new thumbnail
        thumbnail = self.create_thumbnail(image_data, size)
        
        # Cache it
        self.cache_thumbnail(image_hash, thumbnail, size)
        
        return thumbnail
    
    def _create_placeholder_thumbnail(self, 
                                     size: Tuple[int, int],
                                     text: str = "No Image") -> bytes:
        """Create a placeholder thumbnail with text"""
        img = Image.new('RGB', size, (200, 200, 200))
        draw = ImageDraw.Draw(img)
        
        # Try to use a font, fall back to default if not available
        try:
            font_size = min(size) // 8
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # Calculate text position
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2
        
        draw.text((x, y), text, fill=(100, 100, 100), font=font)
        
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85)
        return output.getvalue()
    
    def _create_error_thumbnail(self, size: Tuple[int, int]) -> bytes:
        """Create an error thumbnail"""
        return self._create_placeholder_thumbnail(size, "Error")
    
    def _add_title_overlay(self, img: Image.Image, title: str):
        """Add title overlay to image"""
        draw = ImageDraw.Draw(img)
        
        # Create semi-transparent overlay at bottom
        overlay_height = 25
        overlay = Image.new('RGBA', (img.width, overlay_height), (0, 0, 0, 180))
        img.paste(overlay, (0, img.height - overlay_height), overlay)
        
        # Add text
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
        
        # Truncate title if too long
        max_chars = img.width // 7
        if len(title) > max_chars:
            title = title[:max_chars-3] + "..."
        
        draw.text((5, img.height - 20), title, fill=(255, 255, 255), font=font)
    
    def _add_count_badge(self, img: Image.Image, count: int):
        """Add count badge to image"""
        draw = ImageDraw.Draw(img)
        
        # Create badge in top-right corner
        badge_text = f"+{count-4}"
        badge_size = (30, 20)
        badge_pos = (img.width - badge_size[0] - 5, 5)
        
        # Draw badge background
        draw.rounded_rectangle(
            [badge_pos, (badge_pos[0] + badge_size[0], badge_pos[1] + badge_size[1])],
            radius=5,
            fill=(255, 100, 100)
        )
        
        # Draw badge text
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), badge_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = badge_pos[0] + (badge_size[0] - text_width) // 2
        text_y = badge_pos[1] + (badge_size[1] - text_height) // 2
        
        draw.text((text_x, text_y), badge_text, fill=(255, 255, 255), font=font)
    
    def clear_cache(self, older_than_days: int = 7):
        """
        Clear old thumbnails from cache.
        
        Args:
            older_than_days: Remove thumbnails older than this
        """
        import time
        current_time = time.time()
        cutoff_time = current_time - (older_than_days * 24 * 3600)
        
        for cache_file in self.cache_dir.glob("*.jpg"):
            try:
                if cache_file.stat().st_mtime < cutoff_time:
                    cache_file.unlink()
                    self.logger.debug(f"Removed old thumbnail: {cache_file.name}")
            except Exception as e:
                self.logger.warning(f"Failed to remove cache file: {e}")
    
    def get_cache_size(self) -> int:
        """Get total size of thumbnail cache in bytes"""
        total_size = 0
        for cache_file in self.cache_dir.glob("*.jpg"):
            try:
                total_size += cache_file.stat().st_size
            except:
                pass
        return total_size