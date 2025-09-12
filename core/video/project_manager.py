"""
Project Manager for Video Projects.
Handles project lifecycle, persistence, and file management.
"""

import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .project import VideoProject
from core.project_tracker import set_current_project


class ProjectManager:
    """Manages video project storage and retrieval"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize project manager.
        
        Args:
            base_dir: Base directory for storing projects. 
                     Defaults to user config directory.
        """
        if base_dir is None:
            # Use platform-specific user directory
            import platform
            system = platform.system()
            
            if system == "Windows":
                import os
                base_dir = Path(os.environ.get('APPDATA', '')) / 'ImageAI' / 'video_projects'
            elif system == "Darwin":  # macOS
                base_dir = Path.home() / 'Library' / 'Application Support' / 'ImageAI' / 'video_projects'
            else:  # Linux and others
                base_dir = Path.home() / '.config' / 'ImageAI' / 'video_projects'
        
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
    
    def create_project(self, name: str) -> VideoProject:
        """
        Create a new video project.
        
        Args:
            name: Project name
            
        Returns:
            New VideoProject instance
        """
        # Sanitize project name for filesystem
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        
        # Create unique project directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir_name = f"{safe_name}_{timestamp}"
        project_dir = self.base_dir / project_dir_name
        
        # Ensure unique directory
        counter = 1
        while project_dir.exists():
            project_dir = self.base_dir / f"{project_dir_name}_{counter}"
            counter += 1
        
        # Create project structure
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "assets").mkdir(exist_ok=True)
        (project_dir / "exports").mkdir(exist_ok=True)
        (project_dir / "logs").mkdir(exist_ok=True)
        
        # Create project instance
        project = VideoProject(name=name)
        project.project_dir = project_dir
        
        # Save initial project file
        project.save()
        
        self.logger.info(f"Created new project: {name} at {project_dir}")
        
        return project
    
    def load_project(self, project_path: Path) -> VideoProject:
        """
        Load an existing project.
        
        Args:
            project_path: Path to project file or directory
            
        Returns:
            Loaded VideoProject instance
        """
        if project_path.is_dir():
            # Look for project file in directory
            project_file = project_path / "project.iaproj.json"
        else:
            project_file = project_path
        
        if not project_file.exists():
            raise FileNotFoundError(f"Project file not found: {project_file}")
        
        project = VideoProject.load(project_file)
        self.logger.info(f"Loaded project: {project.name} from {project_file}")
        
        # Track this project for debugging
        set_current_project(project_file)
        
        return project
    
    def save_project(self, project: VideoProject) -> Path:
        """
        Save an existing project.
        
        Args:
            project: VideoProject instance to save
            
        Returns:
            Path to saved project file
        """
        if not project.project_dir:
            # If no project directory exists, create one
            safe_name = "".join(c for c in project.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir_name = f"{safe_name}_{timestamp}"
            project.project_dir = self.base_dir / project_dir_name
            project.project_dir.mkdir(parents=True, exist_ok=True)
            (project.project_dir / "assets").mkdir(exist_ok=True)
            (project.project_dir / "exports").mkdir(exist_ok=True)
            (project.project_dir / "logs").mkdir(exist_ok=True)
        
        # Save the project
        saved_path = project.save()
        self.logger.info(f"Saved project: {project.name} to {saved_path}")
        
        # Track this project for debugging
        set_current_project(saved_path)
        
        return saved_path
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        List all available projects.
        
        Returns:
            List of project metadata dictionaries
        """
        projects = []
        
        for project_dir in self.base_dir.iterdir():
            if not project_dir.is_dir():
                continue
            
            project_file = project_dir / "project.iaproj.json"
            if not project_file.exists():
                continue
            
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                projects.append({
                    "name": data.get("name", "Untitled"),
                    "path": project_file,
                    "created": data.get("created"),
                    "modified": data.get("modified"),
                    "scenes": len(data.get("scenes", [])),
                    "duration": sum(s.get("duration_sec", 0) for s in data.get("scenes", []))
                })
            except Exception as e:
                self.logger.warning(f"Failed to read project {project_file}: {e}")
        
        # Sort by modified date (newest first)
        projects.sort(key=lambda p: p.get("modified", ""), reverse=True)
        
        return projects
    
    def delete_project(self, project: VideoProject) -> bool:
        """
        Delete a project and all its files.
        
        Args:
            project: VideoProject to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not project.project_dir or not project.project_dir.exists():
            self.logger.warning(f"Project directory not found: {project.project_dir}")
            return False
        
        try:
            shutil.rmtree(project.project_dir)
            self.logger.info(f"Deleted project: {project.name} at {project.project_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete project: {e}")
            return False
    
    def duplicate_project(self, project: VideoProject, new_name: str) -> VideoProject:
        """
        Create a copy of an existing project.
        
        Args:
            project: Project to duplicate
            new_name: Name for the new project
            
        Returns:
            New VideoProject instance
        """
        # Create new project
        new_project = self.create_project(new_name)
        
        # Copy project data
        new_project_data = project.to_dict()
        new_project_data["name"] = new_name
        new_project_data["project_id"] = new_project.project_id
        new_project_data["created"] = new_project.created.isoformat()
        new_project_data["modified"] = new_project.modified.isoformat()
        
        # Load data into new project
        new_project = VideoProject.from_dict(new_project_data)
        new_project.project_dir = new_project.project_dir
        
        # Copy assets
        if project.project_dir:
            src_assets = project.project_dir / "assets"
            dst_assets = new_project.project_dir / "assets"
            
            if src_assets.exists():
                shutil.copytree(src_assets, dst_assets, dirs_exist_ok=True)
        
        # Update image paths in scenes
        for scene in new_project.scenes:
            for image in scene.images:
                # Update path to point to new project directory
                if project.project_dir and new_project.project_dir:
                    old_path = str(image.path)
                    new_path = old_path.replace(
                        str(project.project_dir),
                        str(new_project.project_dir)
                    )
                    image.path = Path(new_path)
            
            # Update approved image path
            if scene.approved_image and project.project_dir and new_project.project_dir:
                old_path = str(scene.approved_image)
                new_path = old_path.replace(
                    str(project.project_dir),
                    str(new_project.project_dir)
                )
                scene.approved_image = Path(new_path)
        
        # Save the duplicated project
        new_project.save()
        
        self.logger.info(f"Duplicated project {project.name} as {new_name}")
        
        return new_project
    
    def export_project(self, project: VideoProject, export_path: Path) -> Path:
        """
        Export project to a portable archive.
        
        Args:
            project: Project to export
            export_path: Path for the export archive
            
        Returns:
            Path to exported archive
        """
        import zipfile
        
        # Ensure export path has .zip extension
        if not export_path.suffix:
            export_path = export_path.with_suffix('.zip')
        
        # Create zip archive
        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add project file
            project_file = project.project_dir / "project.iaproj.json"
            if project_file.exists():
                zipf.write(project_file, "project.iaproj.json")
            
            # Add all files from project directory
            if project.project_dir:
                for file_path in project.project_dir.rglob('*'):
                    if file_path.is_file():
                        archive_path = file_path.relative_to(project.project_dir)
                        zipf.write(file_path, archive_path)
        
        self.logger.info(f"Exported project {project.name} to {export_path}")
        
        return export_path
    
    def import_project(self, archive_path: Path) -> VideoProject:
        """
        Import a project from an archive.
        
        Args:
            archive_path: Path to project archive
            
        Returns:
            Imported VideoProject instance
        """
        import zipfile
        
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        
        # Extract to temporary location first
        temp_name = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir = self.base_dir / temp_name
        
        # Extract archive
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Load project
        project_file = temp_dir / "project.iaproj.json"
        if not project_file.exists():
            shutil.rmtree(temp_dir)
            raise ValueError("Invalid project archive: missing project.iaproj.json")
        
        project = VideoProject.load(project_file)
        
        # Create proper project directory
        new_project = self.create_project(project.name)
        
        # Copy extracted files to new project directory
        shutil.rmtree(new_project.project_dir)
        shutil.move(str(temp_dir), str(new_project.project_dir))
        
        # Reload project from new location
        project = VideoProject.load(new_project.project_dir / "project.iaproj.json")
        project.project_dir = new_project.project_dir
        
        self.logger.info(f"Imported project {project.name} from {archive_path}")
        
        return project
    
    def get_project_size(self, project: VideoProject) -> int:
        """
        Calculate total size of project directory in bytes.
        
        Args:
            project: Project to measure
            
        Returns:
            Total size in bytes
        """
        if not project.project_dir or not project.project_dir.exists():
            return 0
        
        total_size = 0
        for file_path in project.project_dir.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        return total_size
    
    def cleanup_old_projects(self, days: int = 30) -> int:
        """
        Remove projects older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of projects removed
        """
        from datetime import timedelta
        
        threshold = datetime.now() - timedelta(days=days)
        removed = 0
        
        for project_info in self.list_projects():
            try:
                modified = datetime.fromisoformat(project_info["modified"])
                if modified < threshold:
                    project = self.load_project(project_info["path"])
                    if self.delete_project(project):
                        removed += 1
            except Exception as e:
                self.logger.warning(f"Failed to check/remove old project: {e}")
        
        self.logger.info(f"Cleaned up {removed} old projects")
        
        return removed