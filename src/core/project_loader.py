"""Project Loader - Load and parse Flow project packages"""

import os
import json
import shutil
import zipfile
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from .exceptions import (
    ProjectError,
    ProjectNotFoundError,
    InvalidProjectError,
    MediaNotFoundError
)

logger = logging.getLogger(__name__)


@dataclass
class MediaItem:
    """Represents a media item in the project"""
    id: str
    name: str
    type: str  # video, image, audio
    path: Path
    file_size: int = 0
    duration: float = 0.0
    dimensions: Optional[Dict[str, int]] = None


@dataclass
class SceneElement:
    """Represents an element in a scene"""
    id: str
    type: str  # video, image, audio, text
    name: str
    position: Dict[str, Any]
    size: Dict[str, Any]
    properties: Dict[str, Any]
    visible: bool = True
    opacity: float = 1.0
    z_index: int = 0


@dataclass
class Scene:
    """Represents a scene in the project"""
    id: str
    name: str
    duration_ms: int
    elements: List[SceneElement] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    transitions: Dict[str, Any] = field(default_factory=dict)
    # DMX sequence linking
    linked_lighting_sequence_id: Optional[str] = None
    linked_lighting_sequence_start_time: float = 0.0
    # NodeGraph reference (for complex Flow logic)
    node_graph_id: Optional[str] = None


@dataclass
class MeshGrid:
    """Mesh grid for advanced warping"""
    rows: int = 1
    cols: int = 1
    points: List[List[Dict[str, float]]] = field(default_factory=list)

    def get_point(self, row: int, col: int) -> Dict[str, float]:
        """Get a specific grid point"""
        if 0 <= row < len(self.points) and 0 <= col < len(self.points[row]):
            return self.points[row][col]
        return {"x": col / self.cols, "y": row / self.rows}

    def is_deformed(self) -> bool:
        """Check if the mesh has any deformation"""
        for row_idx, row in enumerate(self.points):
            for col_idx, point in enumerate(row):
                expected_x = col_idx / self.cols if self.cols > 0 else 0
                expected_y = row_idx / self.rows if self.rows > 0 else 0
                if abs(point.get("x", 0) - expected_x) > 0.001 or abs(point.get("y", 0) - expected_y) > 0.001:
                    return True
        return False


@dataclass
class VideoMappingConfig:
    """Video mapping configuration - supports perspective and mesh warping"""
    enabled: bool = False
    mode: str = "perspective"  # "perspective" or "mesh"

    # Perspective mode (4 corners)
    top_left: tuple = (0.0, 0.0)
    top_right: tuple = (1.0, 0.0)
    bottom_left: tuple = (0.0, 1.0)
    bottom_right: tuple = (1.0, 1.0)

    # Mesh mode (grid warping)
    mesh_grid: Optional[MeshGrid] = None

    # Common settings
    background_color: str = "#000000"
    target_resolution: Optional[Dict[str, int]] = None
    source_resolution: Optional[Dict[str, int]] = None

    # Linked scene (from displayConfig)
    scene_id: Optional[str] = None

    def is_deformed(self) -> bool:
        """Check if mapping has any actual deformation"""
        if not self.enabled:
            return False

        if self.mode == "mesh" and self.mesh_grid:
            return self.mesh_grid.is_deformed()

        # Check perspective deformation
        default_corners = [(0, 0), (1, 0), (0, 1), (1, 1)]
        actual_corners = [self.top_left, self.top_right, self.bottom_left, self.bottom_right]
        for default, actual in zip(default_corners, actual_corners):
            if abs(default[0] - actual[0]) > 0.001 or abs(default[1] - actual[1]) > 0.001:
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = {
            "enabled": self.enabled,
            "mode": self.mode,
            "background_color": self.background_color,
            "is_deformed": self.is_deformed(),
            "scene_id": self.scene_id,
        }

        if self.mode == "perspective":
            result["perspective_points"] = {
                "top_left": {"x": self.top_left[0], "y": self.top_left[1]},
                "top_right": {"x": self.top_right[0], "y": self.top_right[1]},
                "bottom_left": {"x": self.bottom_left[0], "y": self.bottom_left[1]},
                "bottom_right": {"x": self.bottom_right[0], "y": self.bottom_right[1]},
            }
        elif self.mode == "mesh" and self.mesh_grid:
            result["mesh_grid"] = {
                "rows": self.mesh_grid.rows,
                "cols": self.mesh_grid.cols,
                "points": self.mesh_grid.points,
            }

        if self.target_resolution:
            result["target_resolution"] = self.target_resolution
        if self.source_resolution:
            result["source_resolution"] = self.source_resolution

        return result


@dataclass
class DMXSequence:
    """DMX lighting sequence"""
    id: str
    name: str
    duration: float
    keyframes: List[Dict[str, Any]]
    fixtures: List[str] = field(default_factory=list)
    loop: bool = False
    speed: float = 1.0
    interpolation: str = "linear"


@dataclass
class StandaloneSceneSlot:
    """Represents a standalone scene slot from Flow export"""
    id: str
    name: str
    scene_id: str
    auto_start: bool = False
    enabled: bool = True


@dataclass
class Project:
    """Represents a loaded Flow project"""
    id: str
    name: str
    version: str
    description: str
    author: str
    created: datetime
    modified: datetime

    # Settings
    resolution: Dict[str, int]
    framerate: int

    # Content
    scenes: List[Scene] = field(default_factory=list)
    media: List[MediaItem] = field(default_factory=list)
    dmx_sequences: List[DMXSequence] = field(default_factory=list)
    node_graphs: List[Dict[str, Any]] = field(default_factory=list)

    # Configuration
    artnet_config: Dict[str, Any] = field(default_factory=dict)
    video_mapping: Optional[VideoMappingConfig] = None  # Default/global mapping
    video_mappings: List[VideoMappingConfig] = field(default_factory=list)  # Per-scene mappings
    standalone_scenes: List[StandaloneSceneSlot] = field(default_factory=list)
    display_config: List[Dict[str, Any]] = field(default_factory=list)

    # Paths
    base_path: Optional[Path] = None
    start_scene_id: Optional[str] = None

    # Export info
    exported_for_player: bool = False
    player_export_version: str = ""

    @property
    def total_duration_ms(self) -> int:
        """Get total project duration in milliseconds"""
        if self.scenes:
            return max(s.duration_ms for s in self.scenes)
        return 0

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """Get scene by ID"""
        for scene in self.scenes:
            if scene.id == scene_id:
                return scene
        return None

    def get_start_scene(self) -> Optional[Scene]:
        """Get the starting scene"""
        if self.start_scene_id:
            return self.get_scene(self.start_scene_id)
        if self.scenes:
            return self.scenes[0]
        return None

    def get_media(self, media_id: str) -> Optional[MediaItem]:
        """Get media item by ID"""
        for item in self.media:
            if item.id == media_id:
                return item
        return None

    def get_video_elements(self) -> List[SceneElement]:
        """Get all video elements across all scenes"""
        elements = []
        for scene in self.scenes:
            for elem in scene.elements:
                if elem.type == "video":
                    elements.append(elem)
        return elements

    def get_dmx_sequence(self, sequence_id: str) -> Optional[DMXSequence]:
        """Get DMX sequence by ID"""
        for seq in self.dmx_sequences:
            if seq.id == sequence_id:
                return seq
        return None

    def get_scene_dmx_sequence(self, scene: Scene) -> Optional[DMXSequence]:
        """Get the DMX sequence linked to a scene

        Uses linkedLightingSequenceId if available,
        otherwise attempts to parse nodeGraph (not implemented yet)
        """
        if scene.linked_lighting_sequence_id:
            return self.get_dmx_sequence(scene.linked_lighting_sequence_id)
        return None

    def get_scene_mapping(self, scene_id: str) -> Optional[VideoMappingConfig]:
        """Get the video mapping configuration for a specific scene

        Looks up mapping by scene_id in video_mappings list,
        falls back to global video_mapping if no scene-specific mapping.
        """
        # First check scene-specific mappings
        for mapping in self.video_mappings:
            if mapping.scene_id == scene_id and mapping.enabled:
                return mapping

        # Fall back to global mapping
        if self.video_mapping and self.video_mapping.enabled:
            return self.video_mapping

        return None

    def get_scene_media(self, scene: Scene) -> List[Dict[str, Any]]:
        """Get all media items for a scene with their element properties

        Returns list of dicts with element info and resolved media paths.
        Handles both media ID references and direct path references.
        """
        media_list = []

        for element in scene.elements:
            if element.type in ['video', 'audio', 'image']:
                src = element.properties.get('src')
                if src:
                    file_path = None
                    media_id = None

                    # Check if src is a path (contains / or starts with media/)
                    if '/' in src or src.startswith('media'):
                        # Direct path reference
                        file_path = self.base_path / src if self.base_path else Path(src)
                        media_id = src
                    else:
                        # Media ID reference - look up in media list
                        media = self.get_media(src)
                        if media:
                            file_path = media.path
                            media_id = src

                    if file_path:
                        media_list.append({
                            'element_id': element.id,
                            'element_type': element.type,
                            'element_name': element.name,
                            'media_id': media_id,
                            'file_path': file_path,
                            'autoplay': element.properties.get('autoplay', False),
                            'loop': element.properties.get('loop', False),
                            'volume': element.properties.get('volume', 1.0),
                            'muted': element.properties.get('muted', False),
                            'position': element.position,
                            'size': element.size,
                            'z_index': element.z_index,
                            'visible': element.visible,
                            'opacity': element.opacity,
                        })

        return sorted(media_list, key=lambda x: x['z_index'])


class ProjectLoader:
    """Loads and manages Flow project packages"""

    def __init__(self, shows_path: Path):
        self.shows_path = Path(shows_path)
        self.shows_path.mkdir(parents=True, exist_ok=True)

        self._loaded_projects: Dict[str, Project] = {}

    def list_shows(self) -> List[Dict[str, Any]]:
        """List all available shows with import timestamps"""
        shows = []

        for item in self.shows_path.iterdir():
            if item.is_dir():
                project_file = item / "project.json"
                if project_file.exists():
                    try:
                        with open(project_file, 'r') as f:
                            data = json.load(f)

                        # Get import timestamp from metadata file or folder mtime
                        imported_at = self._get_import_timestamp(item)

                        shows.append({
                            "id": self._generate_show_id(item.name),
                            "name": data.get("name", item.name),
                            "description": data.get("description", ""),
                            "author": data.get("author", ""),
                            "path": str(item),
                            "folder_name": item.name,
                            "duration_ms": self._get_project_duration(data),
                            "size_mb": self._get_folder_size_mb(item),
                            "created": data.get("created", ""),
                            "modified": data.get("modified", ""),
                            "imported_at": imported_at,
                        })
                    except Exception as e:
                        logger.warning(f"Error reading project {item.name}: {e}")

            elif item.suffix == ".zip":
                # Unextracted zip file
                stat = item.stat()
                shows.append({
                    "id": self._generate_show_id(item.stem),
                    "name": item.stem,
                    "description": "",
                    "path": str(item),
                    "folder_name": item.stem,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "is_zip": True,
                    "imported_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        # Sort by import date (most recent first)
        shows.sort(key=lambda x: x.get("imported_at", ""), reverse=True)

        return shows

    def _get_import_timestamp(self, project_path: Path) -> str:
        """Get import timestamp for a project

        First checks for .import_meta file, then falls back to folder mtime.
        """
        meta_file = project_path / ".import_meta"
        if meta_file.exists():
            try:
                with open(meta_file, 'r') as f:
                    meta = json.load(f)
                    return meta.get("imported_at", "")
            except Exception:
                pass

        # Fallback to folder modification time
        stat = project_path.stat()
        return datetime.fromtimestamp(stat.st_mtime).isoformat()

    def _save_import_metadata(self, project_path: Path, source_zip: Optional[Path] = None):
        """Save import metadata for a project"""
        meta_file = project_path / ".import_meta"
        meta = {
            "imported_at": datetime.now().isoformat(),
            "source_zip": str(source_zip) if source_zip else None,
        }
        try:
            with open(meta_file, 'w') as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save import metadata: {e}")

    def _generate_show_id(self, name: str) -> str:
        """Generate a unique show ID from name"""
        return hashlib.md5(name.encode()).hexdigest()[:12]

    def _get_project_duration(self, data: dict) -> int:
        """Get project duration from project data"""
        scenes = data.get("scenes", [])
        if scenes:
            return max(s.get("duration", 0) for s in scenes)
        return 0

    def _get_folder_size_mb(self, path: Path) -> float:
        """Get folder size in MB"""
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return round(total / (1024 * 1024), 2)

    def import_show(self, zip_path: Path, show_name: Optional[str] = None,
                    delete_zip_after: bool = False) -> str:
        """Import a show from a zip file

        Args:
            zip_path: Path to the zip file
            show_name: Optional name for the show folder
            delete_zip_after: If True, delete the zip file after successful import

        Returns:
            Show ID
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise ProjectNotFoundError(f"Zip file not found: {zip_path}")

        # Determine extraction folder name
        if show_name:
            folder_name = show_name
        else:
            folder_name = zip_path.stem

        # Clean folder name
        folder_name = "".join(c for c in folder_name if c.isalnum() or c in "._- ")
        extract_path = self.shows_path / folder_name

        # Remove existing folder if exists
        if extract_path.exists():
            shutil.rmtree(extract_path)

        # Extract zip
        logger.info(f"Extracting {zip_path} to {extract_path}")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_path)

        # Verify project.json exists
        project_file = extract_path / "project.json"
        if not project_file.exists():
            # Check if extracted to subfolder
            subdirs = [d for d in extract_path.iterdir() if d.is_dir()]
            if len(subdirs) == 1:
                # Move contents up one level
                for item in subdirs[0].iterdir():
                    shutil.move(str(item), str(extract_path))
                subdirs[0].rmdir()

        if not project_file.exists():
            shutil.rmtree(extract_path)
            raise InvalidProjectError("No project.json found in package")

        # Save import metadata (timestamp and source zip path)
        self._save_import_metadata(extract_path, zip_path)

        show_id = self._generate_show_id(folder_name)
        logger.info(f"Show imported: {folder_name} (ID: {show_id})")

        # Optionally delete source zip
        if delete_zip_after:
            try:
                zip_path.unlink()
                logger.info(f"Deleted source zip: {zip_path}")
            except Exception as e:
                logger.warning(f"Failed to delete source zip: {e}")

        return show_id

    def load_project(self, show_id_or_path: str) -> Project:
        """Load a project from disk

        Args:
            show_id_or_path: Show ID or direct path to project folder

        Returns:
            Loaded Project object
        """
        # Find project path
        if os.path.isdir(show_id_or_path):
            project_path = Path(show_id_or_path)
        else:
            # Search by ID
            project_path = None
            for item in self.shows_path.iterdir():
                if item.is_dir():
                    if self._generate_show_id(item.name) == show_id_or_path:
                        project_path = item
                        break

            if not project_path:
                raise ProjectNotFoundError(f"Show not found: {show_id_or_path}")

        project_file = project_path / "project.json"
        if not project_file.exists():
            raise InvalidProjectError(f"No project.json in {project_path}")

        # Load project data
        with open(project_file, 'r') as f:
            data = json.load(f)

        project = self._parse_project(data, project_path)
        self._loaded_projects[project.id] = project

        logger.info(f"Project loaded: {project.name}")
        return project

    def _parse_project(self, data: dict, base_path: Path) -> Project:
        """Parse project data into Project object"""
        # Parse basic info
        project = Project(
            id=data.get("id", "unknown"),
            name=data.get("name", "Unnamed Project"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            created=self._parse_datetime(data.get("created", "")),
            modified=self._parse_datetime(data.get("modified", "")),
            resolution=data.get("settings", {}).get("resolution", {"width": 1920, "height": 1080}),
            framerate=data.get("settings", {}).get("framerate", 60),
            base_path=base_path,
            start_scene_id=data.get("startSceneId"),
        )

        # Parse media
        for media_data in data.get("media", []):
            media_path = base_path / media_data.get("path", "")
            project.media.append(MediaItem(
                id=media_data.get("id", ""),
                name=media_data.get("name", ""),
                type=media_data.get("type", "unknown"),
                path=media_path,
                file_size=media_data.get("fileSize", 0),
                duration=media_data.get("duration", 0),
                dimensions=media_data.get("dimensions"),
            ))

        # Parse scenes
        for scene_data in data.get("scenes", []):
            scene = self._load_scene(scene_data, base_path)
            if scene:
                project.scenes.append(scene)

        # Parse Art-Net config
        project.artnet_config = data.get("artnetConfig", {})

        # Parse DMX sequences
        for seq_data in data.get("lightingSequences", []):
            project.dmx_sequences.append(DMXSequence(
                id=seq_data.get("id", ""),
                name=seq_data.get("name", ""),
                duration=seq_data.get("duration", 0),
                keyframes=seq_data.get("keyframes", []),
                fixtures=seq_data.get("fixtures", []),
                loop=seq_data.get("loop", False),
                speed=seq_data.get("speed", 1.0),
                interpolation=seq_data.get("interpolation", "linear"),
            ))

        # Parse nodeGraphs references (for future Flow parsing)
        project.node_graphs = data.get("nodeGraphs", [])

        # Parse export info
        project.exported_for_player = data.get("exportedForPlayer", False)
        project.player_export_version = data.get("playerExportVersion", "")

        # Parse display config
        project.display_config = data.get("displayConfig", [])

        # Parse standalone scenes
        standalone_data = data.get("standaloneScenes", {})
        for slot in standalone_data.get("slots", []):
            project.standalone_scenes.append(StandaloneSceneSlot(
                id=slot.get("id", ""),
                name=slot.get("name", ""),
                scene_id=slot.get("sceneId", ""),
                auto_start=slot.get("autoStart", False),
                enabled=slot.get("enabled", True),
            ))

        # If no scenes loaded but we have media, create a default scene
        if not project.scenes:
            project.scenes = self._create_default_scenes(project, data)

        # Determine start scene from various sources
        if not project.start_scene_id:
            # Try displayConfig first
            if project.display_config:
                for dc in project.display_config:
                    if dc.get("isActive") and dc.get("sceneId"):
                        project.start_scene_id = dc.get("sceneId")
                        break

            # Then try standalone scenes with autoStart
            if not project.start_scene_id:
                for slot in project.standalone_scenes:
                    if slot.auto_start and slot.enabled:
                        project.start_scene_id = slot.scene_id
                        break

            # Fallback to first scene
            if not project.start_scene_id and project.scenes:
                project.start_scene_id = project.scenes[0].id

        # Parse video mappings from displayConfig (new format)
        for dc in project.display_config:
            vm = dc.get("videoMapping", {})
            if vm.get("enabled"):
                mapping = self._parse_video_mapping(vm, dc.get("sceneId"))
                if mapping:
                    project.video_mappings.append(mapping)
                    # Also set as default if first one
                    if not project.video_mapping:
                        project.video_mapping = mapping

        # Also check displayGroups (legacy format)
        display_groups = data.get("displayGroups", [])
        for group in display_groups:
            screens = group.get("screens", [])
            for screen in screens:
                vm = screen.get("videoMapping", {})
                if vm.get("enabled"):
                    mapping = self._parse_video_mapping(vm, screen.get("sceneId"))
                    if mapping:
                        project.video_mappings.append(mapping)
                        if not project.video_mapping:
                            project.video_mapping = mapping

        return project

    def _parse_video_mapping(self, vm: dict, scene_id: str = None) -> Optional[VideoMappingConfig]:
        """Parse video mapping configuration from JSON data"""
        if not vm.get("enabled"):
            return None

        mode = vm.get("mode", "perspective")
        pp = vm.get("perspectivePoints", {})

        # Parse mesh grid if present
        mesh_grid = None
        mesh_data = vm.get("meshGrid", {})
        if mesh_data and mesh_data.get("points"):
            mesh_grid = MeshGrid(
                rows=mesh_data.get("rows", 1),
                cols=mesh_data.get("cols", 1),
                points=mesh_data.get("points", [])
            )

        # Parse target resolution
        target_res = vm.get("targetResolution")
        source_res = vm.get("sourceResolution")

        return VideoMappingConfig(
            enabled=True,
            mode=mode,
            top_left=(
                pp.get("topLeft", {}).get("x", 0),
                pp.get("topLeft", {}).get("y", 0)
            ),
            top_right=(
                pp.get("topRight", {}).get("x", 1),
                pp.get("topRight", {}).get("y", 0)
            ),
            bottom_left=(
                pp.get("bottomLeft", {}).get("x", 0),
                pp.get("bottomLeft", {}).get("y", 1)
            ),
            bottom_right=(
                pp.get("bottomRight", {}).get("x", 1),
                pp.get("bottomRight", {}).get("y", 1)
            ),
            mesh_grid=mesh_grid,
            background_color=vm.get("backgroundColor", "#000000"),
            target_resolution=target_res,
            source_resolution=source_res,
            scene_id=scene_id,
        )

    def _load_scene(self, scene_ref: dict, base_path: Path) -> Optional[Scene]:
        """Load scene from file reference"""
        scene_file = scene_ref.get("file")
        if scene_file:
            scene_path = base_path / scene_file
            if scene_path.exists():
                try:
                    with open(scene_path, 'r') as f:
                        scene_data = json.load(f)
                    return self._parse_scene(scene_data)
                except Exception as e:
                    logger.error(f"Error loading scene {scene_file}: {e}")

        # Fallback: parse inline scene data
        return self._parse_scene(scene_ref)

    def _parse_scene(self, data: dict) -> Scene:
        """Parse scene data"""
        scene = Scene(
            id=data.get("id", ""),
            name=data.get("name", "Unnamed Scene"),
            duration_ms=data.get("settings", {}).get("duration", 0),
            settings=data.get("settings", {}),
            transitions=data.get("transitions", {}),
            # DMX linking - direct field (Option B from spec)
            linked_lighting_sequence_id=data.get("linkedLightingSequenceId"),
            linked_lighting_sequence_start_time=data.get("linkedLightingSequenceStartTime", 0.0),
            # NodeGraph reference (Option A from spec)
            node_graph_id=data.get("nodeGraphId"),
        )

        # Parse elements
        for elem_data in data.get("elements", []):
            scene.elements.append(SceneElement(
                id=elem_data.get("id", ""),
                type=elem_data.get("type", "unknown"),
                name=elem_data.get("name", ""),
                position=elem_data.get("position", {"x": 0, "y": 0}),
                size=elem_data.get("size", {"width": 100, "height": 100}),
                properties=elem_data.get("properties", {}),
                visible=elem_data.get("visible", True),
                opacity=elem_data.get("opacity", 1.0),
                z_index=elem_data.get("zIndex", 0),
            ))

        return scene

    def _parse_datetime(self, date_str: str) -> datetime:
        """Parse ISO datetime string"""
        if not date_str:
            return datetime.now()
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            return datetime.now()

    def _create_default_scenes(self, project: Project, data: dict) -> List[Scene]:
        """Create default scenes from media when no scenes are defined

        This handles exports where scenes array is empty but media exists.
        Creates one scene per video with DMX sequences distributed.
        """
        scenes = []

        # Get video media
        videos = [m for m in project.media if m.type == 'video']
        if not videos:
            logger.warning("No scenes or videos found in project")
            return scenes

        # Get DMX sequences
        dmx_sequences = project.dmx_sequences

        # Create one scene per video
        for i, video in enumerate(videos):
            # Calculate duration from video metadata or use default
            duration_ms = int(video.duration * 1000) if video.duration else 30000

            scene_id = f"auto-scene-{i+1}"

            # Assign DMX sequence (rotate through available sequences)
            linked_dmx_id = None
            if dmx_sequences:
                linked_dmx_id = dmx_sequences[i % len(dmx_sequences)].id

            # Simple scene name
            scene = Scene(
                id=scene_id,
                name=f"Scène {i+1}",
                duration_ms=duration_ms,
                settings={
                    'duration': duration_ms,
                    'loop': True,
                    'backgroundColor': '#000000',
                },
                linked_lighting_sequence_id=linked_dmx_id,
            )

            # Add video element to scene
            scene.elements.append(SceneElement(
                id=f"video-elem-{video.id}",
                type='video',
                name=video.name,
                position={'x': 0, 'y': 0},
                size={
                    'width': video.dimensions.get('width', 1920) if video.dimensions else 1920,
                    'height': video.dimensions.get('height', 1080) if video.dimensions else 1080,
                },
                properties={
                    'src': video.id,
                    'autoplay': True,
                    'loop': True,
                    'volume': 1.0,
                    'muted': False,
                },
                visible=True,
                opacity=1.0,
                z_index=0,
            ))

            scenes.append(scene)
            logger.info(f"Created scene '{scene.name}' with video '{video.name}'" +
                       (f" + DMX '{dmx_sequences[i % len(dmx_sequences)].name}'" if linked_dmx_id else ""))

        return scenes

    def delete_show(self, show_id: str, delete_source_zip: bool = True) -> bool:
        """Delete a show and optionally its source zip file

        Args:
            show_id: Show ID to delete
            delete_source_zip: If True, also delete the source zip file

        Returns:
            True if deleted successfully
        """
        deleted = False
        folder_name = None

        # Find and delete the project folder
        for item in self.shows_path.iterdir():
            if item.is_dir():
                if self._generate_show_id(item.name) == show_id:
                    folder_name = item.name

                    # Try to get source zip path from metadata
                    source_zip = None
                    if delete_source_zip:
                        meta_file = item / ".import_meta"
                        if meta_file.exists():
                            try:
                                with open(meta_file, 'r') as f:
                                    meta = json.load(f)
                                    source_zip = meta.get("source_zip")
                            except Exception:
                                pass

                    # Delete the project folder
                    shutil.rmtree(item)
                    logger.info(f"Show deleted: {item.name}")
                    deleted = True

                    # Delete source zip if found
                    if source_zip:
                        source_zip_path = Path(source_zip)
                        if source_zip_path.exists():
                            try:
                                source_zip_path.unlink()
                                logger.info(f"Source zip deleted: {source_zip_path}")
                            except Exception as e:
                                logger.warning(f"Failed to delete source zip: {e}")
                    break

        # Also look for zip files with matching name in shows folder and common locations
        if folder_name:
            zip_locations = [
                self.shows_path / f"{folder_name}.zip",
                self.shows_path.parent / "datas" / f"{folder_name}.zip",
                Path("/tmp") / f"{folder_name}.zip",
            ]

            for zip_path in zip_locations:
                if zip_path.exists():
                    try:
                        zip_path.unlink()
                        logger.info(f"Associated zip deleted: {zip_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete zip {zip_path}: {e}")

        # Also check for unextracted zip files in shows folder
        if not deleted:
            for item in self.shows_path.iterdir():
                if item.suffix == ".zip":
                    if self._generate_show_id(item.stem) == show_id:
                        item.unlink()
                        logger.info(f"Show zip deleted: {item.name}")
                        return True

        return deleted

    def get_loaded_project(self, project_id: str) -> Optional[Project]:
        """Get a loaded project by ID"""
        return self._loaded_projects.get(project_id)
