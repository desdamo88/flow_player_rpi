"""Video Player - MPV-based video playback with mapping support"""

import logging
import threading
import tempfile
from typing import Optional, Callable, Dict, Any, List, Union
from pathlib import Path
from dataclasses import dataclass

from ..core.config import VideoConfig, AudioConfig
from ..core.exceptions import VideoPlayerError, MediaNotFoundError
from ..core.video_mapping import (
    VideoMappingEngine,
    create_mapping_from_project_config,
    PerspectivePoints,
    MeshGridData,
    SoftEdgeConfig,
    Point2D,
)

logger = logging.getLogger(__name__)


@dataclass
class VideoMapping:
    """Video mapping configuration (corner pin) - Legacy format"""
    enabled: bool = False
    mode: str = "perspective"  # perspective, mesh
    top_left: tuple = (0.0, 0.0)
    top_right: tuple = (1.0, 0.0)
    bottom_left: tuple = (0.0, 1.0)
    bottom_right: tuple = (1.0, 1.0)
    background_color: str = "#000000"


class VideoPlayer:
    """MPV-based video player with mapping support

    Supports both perspective (4-corner homography) and mesh (grid warping)
    modes for video projection mapping. Uses GPU acceleration via
    OpenGL shaders when available.
    """

    def __init__(self, video_config: VideoConfig, audio_config: AudioConfig):
        self.video_config = video_config
        self.audio_config = audio_config

        self._mpv = None
        self._initialized = False
        self._playing = False
        self._paused = False
        self._loop = False
        self._current_file: Optional[Path] = None

        # Mapping - supports both legacy VideoMapping and new VideoMappingEngine
        self._mapping: Optional[VideoMapping] = None
        self._mapping_engine: Optional[VideoMappingEngine] = None
        self._shader_dir: Optional[Path] = None  # Temp dir for shader files

        # Callbacks
        self._on_end_file: Optional[Callable] = None
        self._on_position_update: Optional[Callable[[float], None]] = None

        # State
        self._position = 0.0
        self._duration = 0.0
        self._loop_count = 0

    def initialize(self) -> bool:
        """Initialize MPV player"""
        try:
            import mpv

            # MPV options for Raspberry Pi hardware decoding
            self._mpv = mpv.MPV(
                # Video output
                vo='gpu',  # Use GPU for rendering
                hwdec='auto-safe',  # Hardware decoding
                gpu_context='drm',  # DRM/KMS for headless

                # Fullscreen on specific output
                fs=True,
                fs_screen=0,

                # Audio
                audio_device='auto',
                volume=self.audio_config.volume,

                # Performance
                video_sync='display-resample',
                interpolation=True,

                # Other
                input_default_bindings=False,
                input_vo_keyboard=False,
                osc=False,
                osd_level=0,

                # Logging
                log_handler=self._mpv_log_handler,
                loglevel='warn',
            )

            # Set up event handlers
            @self._mpv.property_observer('time-pos')
            def time_observer(_name, value):
                if value is not None:
                    self._position = value
                    if self._on_position_update:
                        self._on_position_update(value)

            @self._mpv.property_observer('duration')
            def duration_observer(_name, value):
                if value is not None:
                    self._duration = value

            @self._mpv.property_observer('pause')
            def pause_observer(_name, value):
                self._paused = value

            @self._mpv.on_key_press('q')
            def quit_handler():
                pass  # Disable quit on 'q'

            # File end handler
            @self._mpv.event_callback('end-file')
            def end_file_handler(event):
                reason = event.get('reason', 'unknown')
                if reason == 'eof':
                    self._loop_count += 1
                    if self._on_end_file:
                        self._on_end_file()
                elif reason == 'error':
                    logger.error(f"Video playback error: {event}")

            self._initialized = True
            logger.info("Video player initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize video player: {e}")
            raise VideoPlayerError(f"Failed to initialize MPV: {e}")

    def _mpv_log_handler(self, loglevel: str, component: str, message: str):
        """Handle MPV log messages"""
        if loglevel in ('error', 'fatal'):
            logger.error(f"MPV [{component}]: {message}")
        elif loglevel == 'warn':
            logger.warning(f"MPV [{component}]: {message}")
        else:
            logger.debug(f"MPV [{component}]: {message}")

    def load(self, file_path: Path, mapping: Optional[Union[VideoMapping, Any]] = None) -> bool:
        """Load a video file

        Args:
            file_path: Path to the video file
            mapping: Optional video mapping configuration
                     Can be VideoMapping (legacy) or VideoMappingConfig from project_loader

        Returns:
            True if loaded successfully
        """
        if not self._initialized:
            raise VideoPlayerError("Video player not initialized")

        file_path = Path(file_path)
        if not file_path.exists():
            raise MediaNotFoundError(f"Video file not found: {file_path}")

        self._current_file = file_path
        self._loop_count = 0

        # Handle mapping configuration
        if mapping:
            if isinstance(mapping, VideoMapping):
                # Legacy VideoMapping format
                self._mapping = mapping
                self._mapping_engine = None
                if mapping.enabled:
                    self._apply_mapping(mapping)
            else:
                # New VideoMappingConfig from project_loader
                self._mapping = None
                self._mapping_engine = create_mapping_from_project_config(mapping)
                if self._mapping_engine and self._mapping_engine.is_deformed():
                    self._apply_mapping_engine()
        else:
            self._mapping = None
            self._mapping_engine = None
            # Clear any previous video filters
            if self._mpv:
                try:
                    self._mpv.vf = ""
                except Exception:
                    pass

        logger.info(f"Video loaded: {file_path}")
        return True

    def _apply_mapping(self, mapping: VideoMapping):
        """Apply video mapping transformation using MPV's video filters (legacy)"""
        if not self._mpv:
            return

        if mapping.mode == "perspective":
            # Use perspective transformation via lavfi filter
            tl = mapping.top_left
            tr = mapping.top_right
            bl = mapping.bottom_left
            br = mapping.bottom_right

            # lavfi perspective filter format:
            # perspective=x0:y0:x1:y1:x2:y2:x3:y3
            # where points are: top-left, top-right, bottom-left, bottom-right
            vf_str = (
                f"lavfi=[perspective="
                f"{tl[0]}*W:{tl[1]}*H:"
                f"{tr[0]}*W:{tr[1]}*H:"
                f"{bl[0]}*W:{bl[1]}*H:"
                f"{br[0]}*W:{br[1]}*H:interpolation=linear]"
            )

            try:
                self._mpv.vf = vf_str
                logger.info(f"Applied video mapping: {mapping.mode}")
            except Exception as e:
                logger.warning(f"Failed to apply video mapping: {e}")

    def _apply_mapping_engine(self):
        """Apply video mapping using VideoMappingEngine

        Supports both perspective and mesh modes with GPU acceleration.
        Falls back to FFmpeg filters if shaders aren't supported.
        """
        if not self._mpv or not self._mapping_engine:
            return

        engine = self._mapping_engine
        mode = engine.mode

        # Try to use shaders first for better quality and performance
        if self._try_apply_shader_mapping():
            logger.info(f"Applied {mode} mapping via GPU shader")
            return

        # Fallback to FFmpeg filter
        try:
            # Get video dimensions (estimate from target resolution or default)
            width = engine.target_resolution.get('width', 1920)
            height = engine.target_resolution.get('height', 1080)

            vf_str = engine.generate_mpv_vf(width, height)
            if vf_str:
                self._mpv.vf = vf_str
                logger.info(f"Applied {mode} mapping via FFmpeg filter")
            else:
                logger.warning("No mapping filter generated")
        except Exception as e:
            logger.warning(f"Failed to apply video mapping: {e}")

    def _try_apply_shader_mapping(self) -> bool:
        """Try to apply mapping via custom GLSL shader

        Returns:
            True if shader was applied successfully
        """
        if not self._mapping_engine:
            return False

        try:
            # Create temporary directory for shader files
            import tempfile
            import os

            if not self._shader_dir:
                self._shader_dir = Path(tempfile.mkdtemp(prefix='flow_shaders_'))

            # Generate and write warp shader
            shader_content = self._mapping_engine.generate_glsl_shader()
            if not shader_content:
                return False

            warp_shader_path = self._shader_dir / 'warp.glsl'
            with open(warp_shader_path, 'w') as f:
                f.write(shader_content)

            # Generate and write soft edge shader if enabled
            soft_edge_shader = self._mapping_engine.generate_soft_edge_shader()
            shader_files = [str(warp_shader_path)]

            if soft_edge_shader:
                soft_edge_path = self._shader_dir / 'soft_edge.glsl'
                with open(soft_edge_path, 'w') as f:
                    f.write(soft_edge_shader)
                shader_files.append(str(soft_edge_path))

            # Apply shaders to MPV
            # Note: This requires MPV compiled with gpu-next or gpu vo
            glsl_shaders = ':'.join(shader_files)
            self._mpv['glsl-shaders'] = glsl_shaders

            logger.debug(f"Applied custom shaders: {shader_files}")
            return True

        except Exception as e:
            logger.debug(f"Shader mapping not available: {e}")
            return False

    def set_mapping(self, mapping_config) -> bool:
        """Update video mapping at runtime

        Args:
            mapping_config: VideoMappingConfig from project_loader

        Returns:
            True if mapping was applied
        """
        if not mapping_config:
            # Clear mapping
            self._mapping_engine = None
            if self._mpv:
                try:
                    self._mpv.vf = ""
                    self._mpv['glsl-shaders'] = ""
                except Exception:
                    pass
            return True

        self._mapping_engine = create_mapping_from_project_config(mapping_config)

        if self._mapping_engine and self._mapping_engine.is_deformed():
            self._apply_mapping_engine()
            return True

        return False

    def get_mapping_info(self) -> Dict[str, Any]:
        """Get current mapping information

        Returns:
            Dict with mapping mode, deformation status, etc.
        """
        if self._mapping_engine:
            return {
                'enabled': True,
                'mode': self._mapping_engine.mode,
                'is_deformed': self._mapping_engine.is_deformed(),
                'using_shader': self._shader_dir is not None,
            }
        elif self._mapping:
            return {
                'enabled': self._mapping.enabled,
                'mode': self._mapping.mode,
                'is_deformed': True,  # Legacy always assumes deformed if enabled
                'using_shader': False,
            }
        return {
            'enabled': False,
            'mode': None,
            'is_deformed': False,
            'using_shader': False,
        }

    def play(self, loop: bool = False):
        """Start or resume video playback

        Args:
            loop: Whether to loop the video
        """
        if not self._initialized:
            raise VideoPlayerError("Video player not initialized")

        self._loop = loop

        if self._paused:
            self._mpv.pause = False
        elif self._current_file:
            self._mpv.loop_file = 'inf' if loop else 'no'
            self._mpv.play(str(self._current_file))

        self._playing = True
        logger.info(f"Video playback started (loop={loop})")

    def stop(self):
        """Stop video playback"""
        if self._mpv:
            self._mpv.stop()
        self._playing = False
        self._position = 0.0
        logger.info("Video playback stopped")

    def pause(self):
        """Pause video playback"""
        if self._mpv and self._playing:
            self._mpv.pause = True
            logger.info("Video paused")

    def resume(self):
        """Resume video playback"""
        if self._mpv and self._paused:
            self._mpv.pause = False
            logger.info("Video resumed")

    def seek(self, position: float, absolute: bool = True):
        """Seek to position

        Args:
            position: Position in seconds
            absolute: If True, seek to absolute position; if False, seek relative
        """
        if self._mpv:
            if absolute:
                self._mpv.seek(position, reference='absolute')
            else:
                self._mpv.seek(position, reference='relative')

    def set_volume(self, volume: int):
        """Set audio volume (0-100)"""
        if self._mpv:
            self._mpv.volume = max(0, min(100, volume))

    def set_speed(self, speed: float):
        """Set playback speed"""
        if self._mpv:
            self._mpv.speed = max(0.1, min(4.0, speed))

    def get_position(self) -> float:
        """Get current playback position in seconds"""
        return self._position

    def get_duration(self) -> float:
        """Get video duration in seconds"""
        return self._duration

    def get_position_ms(self) -> int:
        """Get current playback position in milliseconds"""
        return int(self._position * 1000)

    def get_duration_ms(self) -> int:
        """Get video duration in milliseconds"""
        return int(self._duration * 1000)

    def get_loop_count(self) -> int:
        """Get number of completed loops"""
        return self._loop_count

    def is_playing(self) -> bool:
        """Check if video is playing"""
        return self._playing and not self._paused

    def is_paused(self) -> bool:
        """Check if video is paused"""
        return self._paused

    def is_loaded(self) -> bool:
        """Check if a video is loaded"""
        return self._current_file is not None

    def set_on_end_file(self, callback: Callable):
        """Set callback for when video ends"""
        self._on_end_file = callback

    def set_on_position_update(self, callback: Callable[[float], None]):
        """Set callback for position updates"""
        self._on_position_update = callback

    def get_state(self) -> Dict[str, Any]:
        """Get current player state"""
        return {
            "playing": self._playing,
            "paused": self._paused,
            "position": self._position,
            "duration": self._duration,
            "position_ms": self.get_position_ms(),
            "duration_ms": self.get_duration_ms(),
            "loop": self._loop,
            "loop_count": self._loop_count,
            "current_file": str(self._current_file) if self._current_file else None,
        }

    def screenshot(self, path: Optional[Path] = None) -> Optional[Path]:
        """Take a screenshot of current frame

        Args:
            path: Optional path to save screenshot

        Returns:
            Path to saved screenshot or None if failed
        """
        if not self._mpv:
            return None

        try:
            if path:
                self._mpv.screenshot_to_file(str(path))
            else:
                self._mpv.screenshot()
            return path
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    def shutdown(self):
        """Shutdown video player and cleanup resources"""
        if self._mpv:
            try:
                self._mpv.stop()
                self._mpv.terminate()
            except Exception as e:
                logger.error(f"Error shutting down MPV: {e}")
            self._mpv = None

        # Cleanup shader temporary directory
        if self._shader_dir and self._shader_dir.exists():
            try:
                import shutil
                shutil.rmtree(self._shader_dir)
                logger.debug(f"Cleaned up shader dir: {self._shader_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup shader dir: {e}")
            self._shader_dir = None

        self._mapping_engine = None
        self._initialized = False
        self._playing = False
        logger.info("Video player shutdown complete")


class MultiVideoPlayer:
    """Manages multiple video elements for complex scenes"""

    def __init__(self, video_config: VideoConfig, audio_config: AudioConfig):
        self.video_config = video_config
        self.audio_config = audio_config
        self._players: Dict[str, VideoPlayer] = {}
        self._main_player_id: Optional[str] = None

    def create_player(self, element_id: str) -> VideoPlayer:
        """Create a new video player for an element"""
        player = VideoPlayer(self.video_config, self.audio_config)
        player.initialize()
        self._players[element_id] = player

        if self._main_player_id is None:
            self._main_player_id = element_id

        return player

    def get_player(self, element_id: str) -> Optional[VideoPlayer]:
        """Get player by element ID"""
        return self._players.get(element_id)

    def get_main_player(self) -> Optional[VideoPlayer]:
        """Get the main (first) player"""
        if self._main_player_id:
            return self._players.get(self._main_player_id)
        return None

    def play_all(self, loop: bool = False):
        """Start all video players"""
        for player in self._players.values():
            player.play(loop=loop)

    def stop_all(self):
        """Stop all video players"""
        for player in self._players.values():
            player.stop()

    def pause_all(self):
        """Pause all video players"""
        for player in self._players.values():
            player.pause()

    def resume_all(self):
        """Resume all video players"""
        for player in self._players.values():
            player.resume()

    def seek_all(self, position: float):
        """Seek all players to same position"""
        for player in self._players.values():
            player.seek(position)

    def shutdown_all(self):
        """Shutdown all video players"""
        for player in self._players.values():
            player.shutdown()
        self._players.clear()
        self._main_player_id = None
