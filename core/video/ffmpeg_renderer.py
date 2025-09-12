"""
FFmpeg-based video renderer for creating slideshow videos.

This module handles video generation using FFmpeg with Ken Burns effects,
transitions, captions, and audio track integration.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import re

from .project import Scene, AudioTrack, VideoProject


@dataclass
class RenderSettings:
    """Settings for video rendering"""
    resolution: str = "1920x1080"  # 1080p
    fps: int = 24
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    preset: str = "medium"  # ultrafast, fast, medium, slow, veryslow
    crf: int = 23  # Quality (0-51, lower is better)
    aspect_ratio: str = "16:9"
    transition_duration: float = 0.5
    enable_ken_burns: bool = True
    ken_burns_scale: float = 1.1  # 10% zoom
    output_format: str = "mp4"
    
    def get_dimensions(self) -> Tuple[int, int]:
        """Get width and height from resolution string"""
        width, height = self.resolution.split('x')
        return int(width), int(height)


class FFmpegRenderer:
    """Renders videos using FFmpeg with various effects"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        """
        Initialize FFmpeg renderer.
        
        Args:
            ffmpeg_path: Path to ffmpeg executable
        """
        self.ffmpeg_path = ffmpeg_path
        self.logger = logging.getLogger(__name__)
        
        # Check if FFmpeg is available
        if not self._check_ffmpeg():
            raise RuntimeError(f"FFmpeg not found at {ffmpeg_path}")
    
    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def render_slideshow(self,
                        project: VideoProject,
                        output_path: Path,
                        settings: Optional[RenderSettings] = None,
                        progress_callback: Optional[callable] = None,
                        add_karaoke: bool = False) -> Path:
        """
        Render a slideshow video from project scenes.
        
        Args:
            project: Video project with scenes and settings
            output_path: Output video file path
            settings: Render settings (uses defaults if None)
            progress_callback: Callback for progress updates
            add_karaoke: Whether to add karaoke overlay
            
        Returns:
            Path to rendered video
        """
        if not settings:
            settings = RenderSettings()
        
        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Prepare images with Ken Burns effect if enabled
            if settings.enable_ken_burns:
                image_paths = self._prepare_ken_burns_images(
                    project.scenes, temp_path, settings
                )
            else:
                image_paths = self._prepare_static_images(
                    project.scenes, temp_path, settings
                )
            
            # Create video from images
            video_path = temp_path / "video.mp4"
            self._create_video_from_images(
                image_paths, video_path, project, settings, progress_callback
            )
            
            # Add audio if available
            if project.audio_tracks and project.audio_tracks[0].file_path:
                audio_video_path = temp_path / "audio_video.mp4"
                self._add_audio_track(
                    video_path, project.audio_tracks[0], audio_video_path, settings
                )
                video_path = audio_video_path
            
            # Add karaoke overlay if requested
            if add_karaoke and project.karaoke_config and project.midi_timing_data:
                final_path = temp_path / "karaoke_final.mp4"
                self._add_karaoke_overlay(
                    video_path, project, final_path, settings
                )
            else:
                final_path = video_path
            
            # Copy to output location
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_path, output_path)
            
        return output_path
    
    def _prepare_ken_burns_images(self,
                                  scenes: List[Scene],
                                  temp_dir: Path,
                                  settings: RenderSettings) -> List[Path]:
        """
        Prepare images with Ken Burns effect.
        
        Args:
            scenes: List of scenes with images
            temp_dir: Temporary directory for processing
            settings: Render settings
            
        Returns:
            List of prepared image paths
        """
        prepared_paths = []
        width, height = settings.get_dimensions()
        
        for i, scene in enumerate(scenes):
            if not scene.images:
                self.logger.warning(f"Scene {scene.id} has no images")
                continue
            
            # Use first approved image or first available
            image_path = scene.get_approved_image() if hasattr(scene, 'get_approved_image') else scene.images[0]
            
            # Create Ken Burns effect using zoompan filter
            output_path = temp_dir / f"scene_{i:04d}.mp4"
            
            # Calculate zoom parameters
            zoom_in = i % 2 == 0  # Alternate between zoom in and out
            if zoom_in:
                zoom_expr = f"min(zoom+0.0015,{settings.ken_burns_scale})"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            else:
                zoom_expr = f"if(lte(zoom,1.0),{settings.ken_burns_scale},max(1.001,zoom-0.0015))"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            
            # Build FFmpeg command for Ken Burns effect
            duration = scene.duration
            fps = settings.fps
            total_frames = int(duration * fps)
            
            cmd = [
                self.ffmpeg_path,
                "-loop", "1",
                "-i", str(image_path),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                       f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                       f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
                       f"d={total_frames}:s={width}x{height}:fps={fps}",
                "-c:v", settings.video_codec,
                "-t", str(duration),
                "-pix_fmt", "yuv420p",
                "-y",
                str(output_path)
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    self.logger.error(f"FFmpeg error: {result.stderr}")
                    # Fall back to static image
                    self._create_static_video(image_path, output_path, duration, settings)
                
                prepared_paths.append(output_path)
                
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Ken Burns effect timed out for scene {i}")
                self._create_static_video(image_path, output_path, duration, settings)
                prepared_paths.append(output_path)
            
        return prepared_paths
    
    def _prepare_static_images(self,
                               scenes: List[Scene],
                               temp_dir: Path,
                               settings: RenderSettings) -> List[Path]:
        """
        Prepare static images without effects.
        
        Args:
            scenes: List of scenes
            temp_dir: Temporary directory
            settings: Render settings
            
        Returns:
            List of prepared image paths
        """
        prepared_paths = []
        width, height = settings.get_dimensions()
        
        for i, scene in enumerate(scenes):
            if not scene.images:
                continue
            
            image_path = scene.images[0]
            output_path = temp_dir / f"scene_{i:04d}.mp4"
            
            self._create_static_video(image_path, output_path, scene.duration, settings)
            prepared_paths.append(output_path)
        
        return prepared_paths
    
    def _create_static_video(self,
                            image_path: Path,
                            output_path: Path,
                            duration: float,
                            settings: RenderSettings):
        """Create a static video from an image"""
        width, height = settings.get_dimensions()
        
        cmd = [
            self.ffmpeg_path,
            "-loop", "1",
            "-i", str(image_path),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", settings.video_codec,
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-r", str(settings.fps),
            "-y",
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
    
    def _create_video_from_images(self,
                                  image_paths: List[Path],
                                  output_path: Path,
                                  project: VideoProject,
                                  settings: RenderSettings,
                                  progress_callback: Optional[callable] = None):
        """
        Create video from prepared image clips.
        
        Args:
            image_paths: List of video clip paths
            output_path: Output video path
            project: Video project
            settings: Render settings
            progress_callback: Progress callback
        """
        if not image_paths:
            raise ValueError("No images to create video from")
        
        # Create concat file for FFmpeg
        concat_file = output_path.parent / "concat.txt"
        with open(concat_file, 'w') as f:
            for path in image_paths:
                f.write(f"file '{path.absolute()}'\n")
        
        # Build FFmpeg command
        cmd = [
            self.ffmpeg_path,
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", settings.video_codec,
            "-preset", settings.preset,
            "-crf", str(settings.crf),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",  # Optimize for streaming
            "-y",
            str(output_path)
        ]
        
        # Add crossfade transitions if enabled
        if settings.transition_duration > 0 and len(image_paths) > 1:
            # This would require a more complex filter graph
            # For now, using simple concatenation
            pass
        
        # Execute FFmpeg with progress monitoring
        if progress_callback:
            self._run_with_progress(cmd, progress_callback, total_duration=project.total_duration)
        else:
            subprocess.run(cmd, capture_output=True, check=True)
    
    def _add_audio_track(self,
                        video_path: Path,
                        audio_track: AudioTrack,
                        output_path: Path,
                        settings: RenderSettings):
        """
        Add audio track to video.
        
        Args:
            video_path: Input video path
            audio_track: Audio track configuration
            output_path: Output video path
            settings: Render settings
        """
        # Resolve audio file path
        audio_path = Path(audio_track.file_path)
        if not audio_path.exists():
            self.logger.warning(f"Audio file not found: {audio_path}")
            shutil.copy2(video_path, output_path)
            return
        
        # Build FFmpeg command
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",  # Copy video stream
            "-c:a", settings.audio_codec,
            "-map", "0:v:0",  # Video from first input
            "-map", "1:a:0",  # Audio from second input
            "-shortest",  # End when shortest stream ends
        ]
        
        # Apply volume adjustment
        if audio_track.volume != 1.0:
            cmd.extend(["-af", f"volume={audio_track.volume}"])
        
        # Apply fade effects
        audio_filters = []
        if audio_track.fade_in > 0:
            audio_filters.append(f"afade=t=in:st=0:d={audio_track.fade_in}")
        if audio_track.fade_out > 0:
            audio_filters.append(f"afade=t=out:st=-{audio_track.fade_out}:d={audio_track.fade_out}")
        
        if audio_filters:
            cmd.extend(["-af", ",".join(audio_filters)])
        
        cmd.extend(["-y", str(output_path)])
        
        subprocess.run(cmd, capture_output=True, check=True)
    
    def _run_with_progress(self,
                          cmd: List[str],
                          progress_callback: callable,
                          total_duration: float):
        """
        Run FFmpeg command with progress monitoring.
        
        Args:
            cmd: FFmpeg command
            progress_callback: Callback function(progress_percent, status_text)
            total_duration: Total duration for progress calculation
        """
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Parse FFmpeg output for progress
        duration_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
        
        for line in process.stderr:
            match = duration_pattern.search(line)
            if match:
                hours, minutes, seconds = match.groups()
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                progress = min(100, (current_time / total_duration) * 100)
                progress_callback(progress, f"Rendering: {progress:.1f}%")
        
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)
    
    def create_preview(self,
                      video_path: Path,
                      output_path: Path,
                      max_size: int = 720,
                      max_duration: int = 30) -> Path:
        """
        Create a preview version of the video.
        
        Args:
            video_path: Input video path
            output_path: Output preview path
            max_size: Maximum dimension (width or height)
            max_duration: Maximum duration in seconds
            
        Returns:
            Path to preview video
        """
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),
            "-vf", f"scale='min({max_size},iw)':'min({max_size},ih)':force_original_aspect_ratio=decrease",
            "-t", str(max_duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",  # Lower quality for preview
            "-c:a", "aac",
            "-b:a", "96k",  # Lower audio bitrate
            "-y",
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    
    def extract_thumbnail(self,
                         video_path: Path,
                         output_path: Path,
                         timestamp: float = 0.0,
                         size: Tuple[int, int] = (320, 180)) -> Path:
        """
        Extract a thumbnail from a video.
        
        Args:
            video_path: Input video path
            output_path: Output thumbnail path
            timestamp: Time position to extract from
            size: Thumbnail dimensions
            
        Returns:
            Path to thumbnail
        """
        cmd = [
            self.ffmpeg_path,
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,"
                   f"pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
            "-y",
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    
    def _add_karaoke_overlay(self,
                            video_path: Path,
                            project: VideoProject,
                            output_path: Path,
                            settings: RenderSettings) -> Path:
        """
        Add karaoke overlay to video.
        
        Args:
            video_path: Input video path
            project: Video project with karaoke settings
            output_path: Output video path
            settings: Render settings
            
        Returns:
            Path to video with karaoke
        """
        try:
            from ..karaoke_renderer import KaraokeRenderer
            from ..midi_processor import MidiProcessor
            
            renderer = KaraokeRenderer(self.ffmpeg_path)
            processor = MidiProcessor()
            
            # Extract lyrics with timing
            if project.midi_timing_data and project.input_text:
                lyrics_timing = processor.extract_lyrics_with_timing(
                    project.midi_file_path,
                    project.input_text
                )
                
                # Add karaoke overlay
                result = renderer.add_bouncing_ball_overlay(
                    video_path,
                    lyrics_timing,
                    output_path,
                    project.karaoke_config
                )
                
                # Export lyrics files if requested
                if project.karaoke_export_formats:
                    export_dir = output_path.parent / "lyrics"
                    export_dir.mkdir(exist_ok=True)
                    
                    if "lrc" in project.karaoke_export_formats:
                        lrc_path = export_dir / f"{output_path.stem}.lrc"
                        renderer.generate_lrc(lyrics_timing, lrc_path)
                        project.karaoke_generated_files["lrc"] = lrc_path
                    
                    if "srt" in project.karaoke_export_formats:
                        srt_path = export_dir / f"{output_path.stem}.srt"
                        renderer.generate_srt(lyrics_timing, srt_path)
                        project.karaoke_generated_files["srt"] = srt_path
                    
                    if "ass" in project.karaoke_export_formats:
                        ass_path = export_dir / f"{output_path.stem}.ass"
                        renderer.generate_ass(lyrics_timing, ass_path, project.karaoke_config)
                        project.karaoke_generated_files["ass"] = ass_path
                
                return result
            else:
                # No karaoke data, just copy
                shutil.copy2(video_path, output_path)
                return output_path
                
        except ImportError as e:
            self.logger.warning(f"Karaoke modules not available: {e}")
            shutil.copy2(video_path, output_path)
            return output_path
        except Exception as e:
            self.logger.error(f"Failed to add karaoke overlay: {e}")
            shutil.copy2(video_path, output_path)
            return output_path
    
    def get_video_info(self, video_path: Path) -> Dict[str, Any]:
        """
        Get information about a video file.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video information
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to get video info: {e}")
            return {}