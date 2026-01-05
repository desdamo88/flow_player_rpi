"""Flow Player - Main orchestration class"""

import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from .core.config import Config
from .core.exceptions import ProjectError, ProjectNotFoundError
from .core.utils import get_device_id, get_hostname, get_ip_address, get_mac_address, get_system_info
from .core.project_loader import ProjectLoader, Project, Scene
from .core.scene_player import ScenePlayer, SceneState
from .core.scheduler import PlaybackScheduler, Schedule, ScheduleMode
from .players.dmx_player import DMXPlayer
from .players.video_player import VideoPlayer, VideoMapping

logger = logging.getLogger(__name__)


class FlowPlayer:
    """Main Flow Player orchestration class

    Coordinates video playback, DMX output, scheduling, and web interface.
    Uses ScenePlayer for synchronized scene playback.
    """

    def __init__(self, config: Config):
        self.config = config

        # Core components
        self.project_loader = ProjectLoader(config.shows_path)
        self.scheduler = PlaybackScheduler(config.config_path)

        # Players
        self.video_player: Optional[VideoPlayer] = None
        self.dmx_player: Optional[DMXPlayer] = None

        # Scene player (handles sync)
        self._scene_player: Optional[ScenePlayer] = None

        # Current state
        self.current_project: Optional[Project] = None
        self.current_scene: Optional[Scene] = None
        self._active_show_id: Optional[str] = None
        self._loop_count = 0

        # Monitoring
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_running = False

    def initialize(self) -> bool:
        """Initialize all components"""
        logger.info("Initializing Flow Player...")

        try:
            # Create directories
            self.config.shows_path.mkdir(parents=True, exist_ok=True)
            self.config.config_path.mkdir(parents=True, exist_ok=True)
            self.config.logs_path.mkdir(parents=True, exist_ok=True)

            # Initialize video player
            self.video_player = VideoPlayer(self.config.video, self.config.audio)
            try:
                self.video_player.initialize()
            except Exception as e:
                logger.warning(f"Video player init failed (may work in dev mode): {e}")

            # Initialize DMX player
            self.dmx_player = DMXPlayer(self.config.dmx)
            if self.config.dmx.enabled:
                try:
                    self.dmx_player.initialize()
                except Exception as e:
                    logger.warning(f"DMX player init failed: {e}")

            # Initialize scheduler
            self.scheduler.set_on_trigger(self._on_schedule_trigger)
            self.scheduler.start()

            # Load active show if configured
            if self.config.active_show_id:
                try:
                    # Also restore last active scene if available
                    self.load_show(
                        self.config.active_show_id,
                        scene_id=self.config.active_scene_id
                    )
                    logger.info(f"Restored show: {self.config.active_show_id}, scene: {self.config.active_scene_id}")
                except ProjectNotFoundError:
                    logger.warning(f"Active show not found: {self.config.active_show_id}")
                    # Clear invalid config
                    self.config.active_show_id = None
                    self.config.active_scene_id = None
                    self.config.save()

            # Start heartbeat if enabled
            if self.config.monitoring.heartbeat_enabled:
                self._start_heartbeat()

            # Auto-play if configured
            if self.config.autoplay and self.current_project:
                self.play(loop=self.config.loop)

            logger.info("Flow Player initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Flow Player: {e}")
            return False

    def load_show(self, show_id: str, scene_id: str = None) -> bool:
        """Load a show by ID

        Args:
            show_id: Show ID to load
            scene_id: Optional scene ID to load (otherwise uses start scene)

        Returns:
            True if loaded successfully
        """
        # Stop current playback
        self.stop()

        try:
            # Load project
            project = self.project_loader.load_project(show_id)
            self.current_project = project
            self._active_show_id = show_id

            # Update config
            self.config.active_show_id = show_id
            self.config.save()

            # Get scene to load
            target_scene = None
            if scene_id:
                target_scene = project.get_scene(scene_id)
            if not target_scene:
                target_scene = project.get_start_scene()

            if target_scene:
                self._load_scene(target_scene)
                # Save current scene
                self.config.active_scene_id = target_scene.id
                self.config.save()

            logger.info(f"Show loaded: {project.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load show {show_id}: {e}")
            raise

    def _load_scene(self, scene: Scene) -> bool:
        """Load a scene for playback

        Args:
            scene: Scene to load

        Returns:
            True if loaded successfully
        """
        if not self.current_project:
            return False

        self.current_scene = scene

        # Create scene player
        self._scene_player = ScenePlayer(self.current_project, scene)
        self._scene_player.set_video_player(self.video_player)
        self._scene_player.set_dmx_player(self.dmx_player)

        # Set up callbacks
        self._scene_player.set_on_complete(self._on_playback_complete)
        self._scene_player.set_on_loop(self._on_playback_loop)

        # Load scene resources
        return self._scene_player.load()

    def play(self, loop: bool = True):
        """Start playback

        Args:
            loop: Whether to loop the playback
        """
        if not self.current_project:
            logger.warning("No show loaded, cannot play")
            return

        if not self._scene_player:
            start_scene = self.current_project.get_start_scene()
            if start_scene:
                self._load_scene(start_scene)
            else:
                logger.warning("No scene to play")
                return

        # Override loop setting in scene
        if self.current_scene:
            self.current_scene.settings['loop'] = loop

        self._loop_count = 0
        self._scene_player.play()
        logger.info(f"Playback started (loop={loop})")

    def stop(self):
        """Stop playback"""
        if self._scene_player:
            self._scene_player.stop()
        self._loop_count = 0
        logger.info("Playback stopped")

    def pause(self):
        """Pause playback"""
        if self._scene_player:
            self._scene_player.pause()
        logger.info("Playback paused")

    def resume(self):
        """Resume playback"""
        if self._scene_player:
            self._scene_player.resume()
        logger.info("Playback resumed")

    def restart(self):
        """Restart current show"""
        if self.current_project:
            self.stop()
            self.play(loop=self.config.loop)
            logger.info("Playback restarted")

    def seek(self, position_ms: int):
        """Seek to position

        Args:
            position_ms: Position in milliseconds
        """
        if self._scene_player:
            self._scene_player.seek(position_ms)

    def _on_schedule_trigger(self):
        """Called when scheduler triggers playback"""
        logger.info("Schedule triggered playback")
        if self.current_project:
            self.play(loop=False)

    def _on_playback_complete(self):
        """Called when playback completes (non-loop mode)"""
        logger.info("Playback completed")

    def _on_playback_loop(self, loop_count: int):
        """Called when playback loops"""
        self._loop_count = loop_count
        logger.debug(f"Playback loop #{loop_count}")

    def list_shows(self) -> List[Dict[str, Any]]:
        """List all available shows"""
        return self.project_loader.list_shows()

    def get_scenes(self) -> List[Dict[str, Any]]:
        """Get all scenes from current project"""
        if not self.current_project:
            return []

        # Supported element types for playback
        SUPPORTED_TYPES = {'video', 'audio', 'image'}
        # Interactive element types that need to be flagged
        INTERACTIVE_TYPES = {'button', 'input', 'slider', 'checkbox', 'dropdown',
                            'hotspot', 'trigger', 'interactive', 'form', 'link'}

        scenes = []
        for scene in self.current_project.scenes:
            # Check if this scene has linked DMX
            has_dmx = scene.linked_lighting_sequence_id is not None
            dmx_seq = None
            if has_dmx:
                dmx_seq = self.current_project.get_dmx_sequence(scene.linked_lighting_sequence_id)

            # Analyze elements
            unsupported_elements = []
            interactive_elements = []
            video_count = 0
            audio_count = 0
            image_count = 0

            for elem in scene.elements:
                elem_type = elem.type.lower()
                if elem_type == 'video':
                    video_count += 1
                elif elem_type == 'audio':
                    audio_count += 1
                elif elem_type == 'image':
                    image_count += 1
                elif elem_type in INTERACTIVE_TYPES:
                    interactive_elements.append({
                        'type': elem.type,
                        'name': elem.name
                    })
                elif elem_type not in SUPPORTED_TYPES:
                    unsupported_elements.append({
                        'type': elem.type,
                        'name': elem.name
                    })

            # Check for video mapping
            has_mapping = (self.current_project.video_mapping is not None and
                          self.current_project.video_mapping.enabled)

            scenes.append({
                "id": scene.id,
                "name": scene.name,
                "duration_ms": scene.duration_ms,
                "has_dmx": has_dmx,
                "dmx_sequence_name": dmx_seq.name if dmx_seq else None,
                "element_count": len(scene.elements),
                "video_count": video_count,
                "audio_count": audio_count,
                "image_count": image_count,
                "interactive_elements": interactive_elements,
                "unsupported_elements": unsupported_elements,
                "has_warnings": len(interactive_elements) > 0 or len(unsupported_elements) > 0,
                "has_mapping": has_mapping,
                "is_current": self.current_scene and self.current_scene.id == scene.id,
            })

        return scenes

    def get_project_info(self) -> Dict[str, Any]:
        """Get current project info including mapping"""
        if not self.current_project:
            return {}

        mapping_info = None
        if self.current_project.video_mapping and self.current_project.video_mapping.enabled:
            vm = self.current_project.video_mapping
            mapping_info = {
                "enabled": True,
                "mode": vm.mode,
                "top_left": vm.top_left,
                "top_right": vm.top_right,
                "bottom_left": vm.bottom_left,
                "bottom_right": vm.bottom_right,
            }

        return {
            "id": self.current_project.id,
            "name": self.current_project.name,
            "resolution": self.current_project.resolution,
            "framerate": self.current_project.framerate,
            "scene_count": len(self.current_project.scenes),
            "media_count": len(self.current_project.media),
            "dmx_sequence_count": len(self.current_project.dmx_sequences),
            "video_mapping": mapping_info,
            "artnet_config": self.current_project.artnet_config,
        }

    def play_scene(self, scene_id: str, loop: bool = True) -> bool:
        """Play a specific scene by ID

        Args:
            scene_id: Scene ID to play
            loop: Whether to loop the playback

        Returns:
            True if scene was found and started playing
        """
        if not self.current_project:
            logger.warning("No project loaded")
            return False

        # Find the scene
        scene = self.current_project.get_scene(scene_id)
        if not scene:
            logger.warning(f"Scene not found: {scene_id}")
            return False

        # Stop current playback
        self.stop()

        # Load and play the scene
        if self._load_scene(scene):
            # Save current scene to config for persistence
            self.config.active_scene_id = scene_id
            self.config.save()

            self.play(loop=loop)
            logger.info(f"Playing scene: {scene.name}")
            return True

        return False

    def import_show(self, zip_path: Path) -> str:
        """Import a show from zip file"""
        return self.project_loader.import_show(zip_path)

    def delete_show(self, show_id: str) -> bool:
        """Delete a show"""
        # Stop if currently playing this show
        if show_id == self._active_show_id:
            self.stop()
            self.current_project = None
            self.current_scene = None
            self._scene_player = None
            self._active_show_id = None

        return self.project_loader.delete_show(show_id)

    def get_active_show_id(self) -> Optional[str]:
        """Get active show ID"""
        return self._active_show_id

    def get_schedule(self) -> Schedule:
        """Get current schedule"""
        return self.scheduler.get_schedule()

    def set_schedule(self, schedule: Schedule):
        """Set schedule configuration"""
        self.scheduler.set_schedule(schedule)

    def update_config(self, config_data: dict):
        """Update configuration

        Args:
            config_data: Dictionary with config updates
        """
        self.config._update_from_dict(config_data)
        self.config.save()

        # Apply changes that can be applied at runtime
        if "audio" in config_data:
            if self.video_player:
                self.video_player.set_volume(self.config.audio.volume)

    def get_status(self) -> Dict[str, Any]:
        """Get complete player status for API"""
        # Get scene player status if available
        if self._scene_player:
            scene_status = self._scene_player.get_status()
            state = scene_status["state"]
            position_ms = scene_status["position_ms"]
            duration_ms = scene_status["duration_ms"]
            loop_count = scene_status["loop_count"]
        else:
            state = "stopped"
            position_ms = 0
            duration_ms = self.current_project.total_duration_ms if self.current_project else 0
            loop_count = 0

        return {
            "device": {
                "id": get_device_id(),
                "hostname": get_hostname(),
                "ip": get_ip_address(),
                "mac": get_mac_address(),
            },
            "system": get_system_info(),
            "player": {
                "state": state,
                "current_show": self.current_project.name if self.current_project else None,
                "current_scene": self.current_scene.name if self.current_scene else None,
                "position_ms": position_ms,
                "duration_ms": duration_ms,
                "loop_count": loop_count,
            },
            "schedule": self.scheduler.get_status(),
            "dmx": {
                "protocol": self.config.dmx.mode,
                "universe": self.config.dmx.universe,
                "target_ip": self.config.dmx.ip,
                "fps": self.config.dmx.fps,
                "connected": self.dmx_player.is_connected() if self.dmx_player else False,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def _start_heartbeat(self):
        """Start heartbeat monitoring thread"""
        if self._heartbeat_running:
            return

        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        logger.info("Heartbeat monitoring started")

    def _heartbeat_loop(self):
        """Heartbeat sending loop"""
        import time
        import requests

        while self._heartbeat_running:
            try:
                if self.config.monitoring.heartbeat_url:
                    status = self.get_status()
                    payload = {
                        "device_id": status["device"]["id"],
                        "hostname": status["device"]["hostname"],
                        "ip": status["device"]["ip"],
                        "timestamp": status["timestamp"],
                        "player": status["player"],
                        "system": status["system"],
                        "errors": [],
                    }

                    response = requests.post(
                        self.config.monitoring.heartbeat_url,
                        json=payload,
                        timeout=10
                    )
                    if response.status_code != 200:
                        logger.warning(f"Heartbeat failed: HTTP {response.status_code}")

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            time.sleep(self.config.monitoring.heartbeat_interval_sec)

    def _stop_heartbeat(self):
        """Stop heartbeat monitoring"""
        self._heartbeat_running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)

    def shutdown(self):
        """Shutdown Flow Player"""
        logger.info("Shutting down Flow Player...")

        # Stop heartbeat
        self._stop_heartbeat()

        # Stop playback
        self.stop()

        # Shutdown components
        self.scheduler.shutdown()

        if self.video_player:
            self.video_player.shutdown()

        if self.dmx_player:
            self.dmx_player.shutdown()

        logger.info("Flow Player shutdown complete")
