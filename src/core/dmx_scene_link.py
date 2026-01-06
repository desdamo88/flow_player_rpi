"""DMX Scene Link - Links DMX recordings to scenes

Manages the association between DMX recordings and project scenes,
allowing recordings to override or supplement project DMX sequences.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class DMXPlaybackMode(Enum):
    """DMX playback mode when a scene has both a project sequence and a recording"""
    PROJECT_ONLY = "project_only"      # Use only the project's DMX sequence
    RECORDING_ONLY = "recording_only"  # Use only the linked recording
    RECORDING_PRIORITY = "recording_priority"  # Recording overrides project (default)
    BLEND = "blend"  # Blend both (HTP - Highest Takes Precedence)


@dataclass
class SceneRecordingLink:
    """Link between a scene and a DMX recording"""
    scene_id: str
    recording_name: str  # Name of the .dmxr file (without extension)
    mode: str = "recording_priority"  # DMXPlaybackMode value
    enabled: bool = True
    offset_ms: int = 0  # Offset to apply when starting the recording

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SceneRecordingLink":
        return cls(
            scene_id=data.get("scene_id", ""),
            recording_name=data.get("recording_name", ""),
            mode=data.get("mode", "recording_priority"),
            enabled=data.get("enabled", True),
            offset_ms=data.get("offset_ms", 0)
        )


class DMXSceneLinkManager:
    """Manages links between scenes and DMX recordings"""

    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.links_file = self.config_path / "dmx_scene_links.json"
        self._links: Dict[str, SceneRecordingLink] = {}  # scene_id -> link
        self._load()

    def _load(self):
        """Load links from file"""
        if self.links_file.exists():
            try:
                with open(self.links_file, 'r') as f:
                    data = json.load(f)

                for link_data in data.get("links", []):
                    link = SceneRecordingLink.from_dict(link_data)
                    self._links[link.scene_id] = link

                logger.info(f"Loaded {len(self._links)} DMX scene links")
            except Exception as e:
                logger.error(f"Failed to load DMX scene links: {e}")

    def _save(self):
        """Save links to file"""
        try:
            self.config_path.mkdir(parents=True, exist_ok=True)

            data = {
                "version": "1.0",
                "links": [link.to_dict() for link in self._links.values()]
            }

            with open(self.links_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self._links)} DMX scene links")
        except Exception as e:
            logger.error(f"Failed to save DMX scene links: {e}")

    def link_scene(self, scene_id: str, recording_name: str,
                   mode: str = "recording_priority", offset_ms: int = 0) -> bool:
        """Link a recording to a scene"""
        try:
            link = SceneRecordingLink(
                scene_id=scene_id,
                recording_name=recording_name,
                mode=mode,
                enabled=True,
                offset_ms=offset_ms
            )
            self._links[scene_id] = link
            self._save()
            logger.info(f"Linked scene {scene_id} to recording {recording_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to link scene: {e}")
            return False

    def unlink_scene(self, scene_id: str) -> bool:
        """Remove link from a scene"""
        if scene_id in self._links:
            del self._links[scene_id]
            self._save()
            logger.info(f"Unlinked scene {scene_id}")
            return True
        return False

    def get_link(self, scene_id: str) -> Optional[SceneRecordingLink]:
        """Get the link for a scene"""
        link = self._links.get(scene_id)
        if link and link.enabled:
            return link
        return None

    def get_all_links(self) -> List[Dict]:
        """Get all links as dictionaries"""
        return [link.to_dict() for link in self._links.values()]

    def set_mode(self, scene_id: str, mode: str) -> bool:
        """Set the playback mode for a scene link"""
        if scene_id in self._links:
            self._links[scene_id].mode = mode
            self._save()
            return True
        return False

    def set_enabled(self, scene_id: str, enabled: bool) -> bool:
        """Enable or disable a scene link"""
        if scene_id in self._links:
            self._links[scene_id].enabled = enabled
            self._save()
            return True
        return False

    def set_offset(self, scene_id: str, offset_ms: int) -> bool:
        """Set the offset for a scene link"""
        if scene_id in self._links:
            self._links[scene_id].offset_ms = offset_ms
            self._save()
            return True
        return False


def blend_dmx_frames(project_channels: List[int], recording_channels: List[int],
                     mode: str = "recording_priority") -> List[int]:
    """Blend two DMX frames according to the specified mode

    Args:
        project_channels: DMX channels from project sequence (512 values)
        recording_channels: DMX channels from recording (512 values)
        mode: Blend mode

    Returns:
        Blended DMX channels (512 values)
    """
    if mode == DMXPlaybackMode.PROJECT_ONLY.value:
        return project_channels

    if mode == DMXPlaybackMode.RECORDING_ONLY.value:
        return recording_channels

    if mode == DMXPlaybackMode.RECORDING_PRIORITY.value:
        # Recording takes priority - use recording values where non-zero
        result = list(project_channels)
        for i, val in enumerate(recording_channels):
            if val > 0:
                result[i] = val
        return result

    if mode == DMXPlaybackMode.BLEND.value:
        # HTP (Highest Takes Precedence)
        return [max(p, r) for p, r in zip(project_channels, recording_channels)]

    # Default: recording priority
    return recording_channels
