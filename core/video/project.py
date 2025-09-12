"""
Video Project data models and persistence for ImageAI.
Handles project state, scenes, and metadata management.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum


class VideoProvider(Enum):
    """Available video generation providers"""
    VEO = "veo"
    SLIDESHOW = "slideshow"


class SceneStatus(Enum):
    """Status of a scene in the generation pipeline"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AudioTrack:
    """Audio track configuration for video projects"""
    track_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: Optional[Path] = None  # Absolute path to audio file (not copied)
    track_type: str = "music"  # 'music', 'narration', 'sfx'
    volume: float = 1.0  # 0.0 to 1.0
    fade_in_duration: float = 0.0  # seconds
    fade_out_duration: float = 0.0  # seconds
    start_offset: float = 0.0  # trim from beginning
    end_offset: float = 0.0  # trim from end
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "track_id": self.track_id,
            "file_path": str(self.file_path) if self.file_path else None,
            "track_type": self.track_type,
            "volume": self.volume,
            "fade_in": self.fade_in_duration,
            "fade_out": self.fade_out_duration,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioTrack":
        """Create from dictionary"""
        return cls(
            track_id=data.get("track_id", str(uuid.uuid4())),
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            track_type=data.get("track_type", "music"),
            volume=data.get("volume", 1.0),
            fade_in_duration=data.get("fade_in", 0.0),
            fade_out_duration=data.get("fade_out", 0.0),
            start_offset=data.get("start_offset", 0.0),
            end_offset=data.get("end_offset", 0.0)
        )


@dataclass
class ImageVariant:
    """A single generated image variant for a scene"""
    path: Path
    provider: str
    model: str
    seed: Optional[int] = None
    cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "path": str(self.path),
            "provider": self.provider,
            "model": self.model,
            "seed": self.seed,
            "cost": self.cost,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageVariant":
        """Create from dictionary"""
        return cls(
            path=Path(data["path"]),
            provider=data["provider"],
            model=data["model"],
            seed=data.get("seed"),
            cost=data.get("cost", 0.0),
            metadata=data.get("metadata", {}),
            generated_at=datetime.fromisoformat(data.get("generated_at", datetime.now().isoformat()))
        )


@dataclass
class Scene:
    """A single scene in the video project"""
    id: str = field(default_factory=lambda: f"scene-{uuid.uuid4().hex[:8]}")
    source: str = ""  # Original text/lyric line
    prompt: str = ""  # AI-enhanced or user-edited prompt
    prompt_history: List[str] = field(default_factory=list)  # All previous prompt versions
    duration_sec: float = 4.0  # Scene duration in seconds
    images: List[ImageVariant] = field(default_factory=list)  # Generated image variants
    approved_image: Optional[Path] = None  # Selected image for final video
    caption: Optional[str] = None  # Optional caption overlay
    status: SceneStatus = SceneStatus.PENDING
    order: int = 0  # Scene order in timeline
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "source": self.source,
            "prompt": self.prompt,
            "prompt_history": self.prompt_history,
            "duration_sec": self.duration_sec,
            "images": [img.to_dict() for img in self.images],
            "approved_image": str(self.approved_image) if self.approved_image else None,
            "caption": self.caption,
            "status": self.status.value,
            "order": self.order,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        """Create from dictionary"""
        return cls(
            id=data.get("id", f"scene-{uuid.uuid4().hex[:8]}"),
            source=data.get("source", ""),
            prompt=data.get("prompt", ""),
            prompt_history=data.get("prompt_history", []),
            duration_sec=data.get("duration_sec", 4.0),
            images=[ImageVariant.from_dict(img) for img in data.get("images", [])],
            approved_image=Path(data["approved_image"]) if data.get("approved_image") else None,
            caption=data.get("caption"),
            status=SceneStatus(data.get("status", "pending")),
            order=data.get("order", 0),
            metadata=data.get("metadata", {})
        )
    
    def add_prompt_to_history(self, prompt: str):
        """Add a prompt to the history if it's different from current"""
        if prompt != self.prompt and prompt not in self.prompt_history:
            if self.prompt:  # Save current prompt to history before updating
                self.prompt_history.append(self.prompt)
            self.prompt = prompt


@dataclass
class VideoProject:
    """Main video project data model"""
    schema: str = "imageai.video_project.v1"
    name: str = "Untitled Project"
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    
    # Provider configuration
    llm_provider: Optional[str] = None  # For prompt generation
    llm_model: Optional[str] = None
    image_provider: str = "gemini"
    image_model: str = "gemini-2.5-flash-image-preview"
    video_provider: str = "slideshow"  # 'veo' or 'slideshow'
    video_model: Optional[str] = None  # For Veo: 'veo-3.0-generate-001', etc.
    
    # Template and style
    prompt_template: str = "templates/video/lyric_prompt.j2"
    style: Dict[str, Any] = field(default_factory=lambda: {
        "aspect_ratio": "16:9",
        "negative_prompt": "",
        "seed": None,
        "quality": "high",
        "resolution": "1080p"
    })
    
    # Input configuration
    input_text: str = ""
    input_format: str = "structured"  # 'timestamped' or 'structured'
    timing_preset: str = "medium"  # 'fast', 'medium', 'slow'
    target_duration: Optional[str] = None  # "00:02:45" format
    
    # Audio configuration
    audio_tracks: List[AudioTrack] = field(default_factory=list)
    
    # Scenes
    scenes: List[Scene] = field(default_factory=list)
    
    # Project paths
    project_dir: Optional[Path] = None
    export_path: Optional[Path] = None
    
    # Cost tracking
    total_cost: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "schema": self.schema,
            "name": self.name,
            "project_id": self.project_id,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "provider": {
                "llm": {
                    "provider": self.llm_provider,
                    "model": self.llm_model
                },
                "images": {
                    "provider": self.image_provider,
                    "model": self.image_model
                },
                "video": {
                    "provider": self.video_provider,
                    "model": self.video_model
                }
            },
            "prompt_template": self.prompt_template,
            "style": self.style,
            "input": {
                "raw": self.input_text,
                "format": self.input_format
            },
            "timing": {
                "target": self.target_duration,
                "preset": self.timing_preset
            },
            "audio": {
                "tracks": [track.to_dict() for track in self.audio_tracks]
            },
            "scenes": [scene.to_dict() for scene in self.scenes],
            "export": {
                "path": str(self.export_path) if self.export_path else None
            },
            "total_cost": self.total_cost
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoProject":
        """Create from dictionary"""
        project = cls(
            schema=data.get("schema", "imageai.video_project.v1"),
            name=data.get("name", "Untitled Project"),
            project_id=data.get("project_id", str(uuid.uuid4())),
            created=datetime.fromisoformat(data.get("created", datetime.now().isoformat())),
            modified=datetime.fromisoformat(data.get("modified", datetime.now().isoformat()))
        )
        
        # Load providers
        if "provider" in data:
            providers = data["provider"]
            if "llm" in providers:
                project.llm_provider = providers["llm"].get("provider")
                project.llm_model = providers["llm"].get("model")
            if "images" in providers:
                project.image_provider = providers["images"].get("provider", "gemini")
                project.image_model = providers["images"].get("model", "gemini-2.5-flash-image-preview")
            if "video" in providers:
                project.video_provider = providers["video"].get("provider", "slideshow")
                project.video_model = providers["video"].get("model")
        
        # Load style and templates
        project.prompt_template = data.get("prompt_template", "templates/video/lyric_prompt.j2")
        project.style = data.get("style", project.style)
        
        # Load input configuration
        if "input" in data:
            project.input_text = data["input"].get("raw", "")
            project.input_format = data["input"].get("format", "structured")
        
        if "timing" in data:
            project.target_duration = data["timing"].get("target")
            project.timing_preset = data["timing"].get("preset", "medium")
        
        # Load audio tracks
        if "audio" in data and "tracks" in data["audio"]:
            project.audio_tracks = [AudioTrack.from_dict(track) for track in data["audio"]["tracks"]]
        
        # Load scenes
        project.scenes = [Scene.from_dict(scene) for scene in data.get("scenes", [])]
        
        # Load export path
        if "export" in data and data["export"].get("path"):
            project.export_path = Path(data["export"]["path"])
        
        project.total_cost = data.get("total_cost", 0.0)
        
        return project
    
    def save(self, path: Optional[Path] = None) -> Path:
        """Save project to JSON file"""
        if path is None:
            if self.project_dir:
                path = self.project_dir / "project.iaproj.json"
            else:
                raise ValueError("No save path specified and project_dir not set")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        self.modified = datetime.now()
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        return path
    
    @classmethod
    def load(cls, path: Path) -> "VideoProject":
        """Load project from JSON file"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        project = cls.from_dict(data)
        project.project_dir = path.parent
        
        return project
    
    def add_scene(self, source: str, prompt: str = "", duration: float = 4.0) -> Scene:
        """Add a new scene to the project"""
        scene = Scene(
            source=source,
            prompt=prompt or source,
            duration_sec=duration,
            order=len(self.scenes)
        )
        self.scenes.append(scene)
        return scene
    
    def reorder_scenes(self, new_order: List[str]):
        """Reorder scenes by their IDs"""
        scene_map = {scene.id: scene for scene in self.scenes}
        self.scenes = []
        for i, scene_id in enumerate(new_order):
            if scene_id in scene_map:
                scene = scene_map[scene_id]
                scene.order = i
                self.scenes.append(scene)
    
    def get_total_duration(self) -> float:
        """Calculate total video duration in seconds"""
        return sum(scene.duration_sec for scene in self.scenes)
    
    def add_audio_track(self, audio_file: Path, track_type: str = 'music') -> AudioTrack:
        """Add an audio track to the project"""
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        
        track = AudioTrack(
            file_path=audio_file.absolute(),
            track_type=track_type
        )
        self.audio_tracks.append(track)
        return track