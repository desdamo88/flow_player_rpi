"""Scene Player - Synchronized playback of video, audio, and DMX for a scene"""

import time
import logging
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .project_loader import Project, Scene, DMXSequence
from .utils import interpolate_value

logger = logging.getLogger(__name__)


class SceneState(Enum):
    """Scene playback state"""
    IDLE = "idle"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class MediaPlaybackInfo:
    """Information about a media being played"""
    element_id: str
    element_type: str
    file_path: Path
    autoplay: bool
    loop: bool
    volume: float
    is_playing: bool = False


class ScenePlayer:
    """Synchronized playback of a single scene

    Handles:
    - Video playback via MPV
    - Audio playback (embedded in video or separate)
    - DMX sequence with interpolation at 40fps
    - Timeline synchronization
    """

    DMX_FPS = 40
    DMX_INTERVAL = 1.0 / DMX_FPS

    def __init__(self, project: Project, scene: Scene):
        self.project = project
        self.scene = scene

        self._state = SceneState.IDLE
        self._start_time: Optional[float] = None
        self._pause_time: Optional[float] = None
        self._elapsed_paused: float = 0.0

        # Media info
        self._media_list: List[Dict[str, Any]] = []
        self._dmx_sequence: Optional[DMXSequence] = None

        # Players (injected externally)
        self._video_player = None
        self._dmx_player = None

        # Sync thread
        self._running = False
        self._sync_thread: Optional[threading.Thread] = None

        # Callbacks
        self._on_state_change: Optional[Callable[[SceneState], None]] = None
        self._on_position_update: Optional[Callable[[float], None]] = None
        self._on_complete: Optional[Callable] = None
        self._on_loop: Optional[Callable[[int], None]] = None

        # Stats
        self._loop_count = 0

    def set_video_player(self, player):
        """Inject video player"""
        self._video_player = player

    def set_dmx_player(self, player):
        """Inject DMX player"""
        self._dmx_player = player

    def load(self) -> bool:
        """Load scene resources"""
        self._set_state(SceneState.LOADING)

        try:
            # Get media for this scene
            self._media_list = self.project.get_scene_media(self.scene)
            logger.info(f"Scene '{self.scene.name}': {len(self._media_list)} media elements")

            # Get DMX sequence for this scene
            self._dmx_sequence = self.project.get_scene_dmx_sequence(self.scene)
            if self._dmx_sequence:
                logger.info(f"Scene '{self.scene.name}': DMX sequence '{self._dmx_sequence.name}'")

            # Load video into player
            video_media = self._get_primary_video()
            if video_media and self._video_player:
                video_path = video_media['file_path']
                if isinstance(video_path, str):
                    video_path = Path(video_path)

                if video_path.exists():
                    # Get video mapping from project
                    mapping = None
                    if self.project.video_mapping and self.project.video_mapping.enabled:
                        from ..players.video_player import VideoMapping
                        mapping = VideoMapping(
                            enabled=True,
                            mode=self.project.video_mapping.mode,
                            top_left=self.project.video_mapping.top_left,
                            top_right=self.project.video_mapping.top_right,
                            bottom_left=self.project.video_mapping.bottom_left,
                            bottom_right=self.project.video_mapping.bottom_right,
                        )
                    self._video_player.load(video_path, mapping)
                    logger.info(f"Video loaded: {video_path}")
                else:
                    logger.warning(f"Video file not found: {video_path}")

            self._set_state(SceneState.IDLE)
            return True

        except Exception as e:
            logger.error(f"Failed to load scene: {e}")
            self._set_state(SceneState.ERROR)
            return False

    def _get_primary_video(self) -> Optional[Dict[str, Any]]:
        """Get the primary video element (first video with autoplay or first video)"""
        videos = [m for m in self._media_list if m['element_type'] == 'video']

        # Prefer autoplay video
        for v in videos:
            if v.get('autoplay'):
                return v

        # Fallback to first video
        return videos[0] if videos else None

    def play(self):
        """Start scene playback"""
        if self._state == SceneState.PLAYING:
            return

        if self._state == SceneState.PAUSED:
            self.resume()
            return

        self._loop_count = 0
        self._start_time = time.time()
        self._elapsed_paused = 0.0

        # Start video
        if self._video_player:
            loop = self.scene.settings.get('loop', False)
            self._video_player.play(loop=loop)

        # Start sync thread
        self._start_sync_thread()

        self._set_state(SceneState.PLAYING)
        logger.info(f"Scene '{self.scene.name}' playback started")

    def stop(self):
        """Stop scene playback"""
        self._stop_sync_thread()

        # Stop video
        if self._video_player:
            self._video_player.stop()

        # DMX blackout
        if self._dmx_player:
            self._dmx_player.blackout()

        self._start_time = None
        self._pause_time = None
        self._elapsed_paused = 0.0

        self._set_state(SceneState.STOPPED)
        logger.info(f"Scene '{self.scene.name}' playback stopped")

    def pause(self):
        """Pause scene playback"""
        if self._state != SceneState.PLAYING:
            return

        self._pause_time = time.time()

        if self._video_player:
            self._video_player.pause()

        self._set_state(SceneState.PAUSED)
        logger.info(f"Scene '{self.scene.name}' paused")

    def resume(self):
        """Resume scene playback"""
        if self._state != SceneState.PAUSED:
            return

        if self._pause_time:
            self._elapsed_paused += time.time() - self._pause_time
        self._pause_time = None

        if self._video_player:
            self._video_player.resume()

        self._set_state(SceneState.PLAYING)
        logger.info(f"Scene '{self.scene.name}' resumed")

    def seek(self, position_ms: int):
        """Seek to position in milliseconds"""
        if self._video_player:
            self._video_player.seek(position_ms / 1000.0)

        # Adjust start time to match seek position
        if self._start_time:
            elapsed_before = self.get_elapsed_ms()
            offset = position_ms - elapsed_before
            self._start_time -= offset / 1000.0

    def get_elapsed_ms(self) -> int:
        """Get elapsed time in milliseconds"""
        if not self._start_time:
            return 0

        if self._pause_time:
            # If paused, calculate up to pause time
            elapsed = (self._pause_time - self._start_time - self._elapsed_paused) * 1000
        else:
            elapsed = (time.time() - self._start_time - self._elapsed_paused) * 1000

        return int(elapsed)

    def get_duration_ms(self) -> int:
        """Get scene duration in milliseconds"""
        return self.scene.duration_ms

    def get_position_ratio(self) -> float:
        """Get position as ratio 0.0 to 1.0"""
        duration = self.get_duration_ms()
        if duration <= 0:
            return 0.0
        return min(1.0, self.get_elapsed_ms() / duration)

    def _start_sync_thread(self):
        """Start the sync/DMX thread"""
        if self._running:
            return

        self._running = True
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()

    def _stop_sync_thread(self):
        """Stop the sync thread"""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=1.0)
            self._sync_thread = None

    def _sync_loop(self):
        """Main synchronization loop at 40fps"""
        last_update = time.time()

        while self._running:
            now = time.time()

            if self._state == SceneState.PLAYING:
                elapsed_ms = self.get_elapsed_ms()
                elapsed_sec = elapsed_ms / 1000.0

                # Update DMX
                if self._dmx_sequence and self._dmx_player:
                    self._update_dmx(elapsed_sec)

                # Notify position update
                if self._on_position_update:
                    self._on_position_update(elapsed_ms)

                # Check for scene end
                duration_ms = self.scene.duration_ms
                if duration_ms > 0 and elapsed_ms >= duration_ms:
                    if self.scene.settings.get('loop', False):
                        self._handle_loop()
                    else:
                        self._handle_complete()

            # Sleep to maintain ~40fps
            sleep_time = self.DMX_INTERVAL - (time.time() - now)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _update_dmx(self, elapsed_sec: float):
        """Update DMX output based on sequence keyframes"""
        seq = self._dmx_sequence
        if not seq or not seq.keyframes:
            return

        # Apply speed multiplier
        elapsed_sec *= seq.speed

        # Handle sequence loop
        if seq.loop and seq.duration > 0 and elapsed_sec > seq.duration:
            elapsed_sec = elapsed_sec % seq.duration

        # Group keyframes by fixture
        fixture_keyframes: Dict[str, List[Dict]] = {}
        for kf in seq.keyframes:
            fixture_id = kf.get('fixtureId', 'default')
            if fixture_id not in fixture_keyframes:
                fixture_keyframes[fixture_id] = []
            fixture_keyframes[fixture_id].append(kf)

        # Sort each fixture's keyframes by time
        for fixture_id in fixture_keyframes:
            fixture_keyframes[fixture_id].sort(key=lambda x: x.get('time', 0))

        # Interpolate and output for each fixture
        for fixture_id, keyframes in fixture_keyframes.items():
            values = self._interpolate_keyframes(keyframes, elapsed_sec, seq.interpolation)
            if values:
                # For now, output directly starting at channel 1
                # TODO: Map fixture to actual DMX channels via fixture config
                self._dmx_player.set_channels(1, values)

    def _interpolate_keyframes(
        self,
        keyframes: List[Dict],
        current_time: float,
        interpolation: str
    ) -> Optional[List[int]]:
        """Interpolate between keyframes to get current values"""
        if not keyframes:
            return None

        # Find surrounding keyframes
        prev_kf = None
        next_kf = None

        for kf in keyframes:
            kf_time = kf.get('time', 0)
            if kf_time <= current_time:
                prev_kf = kf
            elif next_kf is None:
                next_kf = kf
                break

        if prev_kf is None:
            # Before first keyframe, use first values
            return keyframes[0].get('values', [])

        if next_kf is None:
            # After last keyframe, use last values
            return prev_kf.get('values', [])

        # Interpolate between prev and next
        prev_time = prev_kf.get('time', 0)
        next_time = next_kf.get('time', 0)
        prev_values = prev_kf.get('values', [])
        next_values = next_kf.get('values', [])

        if next_time == prev_time:
            return prev_values

        # Calculate progress
        progress = (current_time - prev_time) / (next_time - prev_time)

        # Interpolate each channel
        result = []
        max_channels = max(len(prev_values), len(next_values))
        for i in range(max_channels):
            v1 = prev_values[i] if i < len(prev_values) else 0
            v2 = next_values[i] if i < len(next_values) else 0
            result.append(interpolate_value(v1, v2, progress, interpolation))

        return result

    def _handle_loop(self):
        """Handle scene loop"""
        self._loop_count += 1
        self._start_time = time.time()
        self._elapsed_paused = 0.0

        # Restart video
        if self._video_player:
            self._video_player.seek(0)

        logger.debug(f"Scene '{self.scene.name}' loop #{self._loop_count}")

        if self._on_loop:
            self._on_loop(self._loop_count)

    def _handle_complete(self):
        """Handle scene completion"""
        logger.info(f"Scene '{self.scene.name}' completed")

        self.stop()

        if self._on_complete:
            self._on_complete()

    def _set_state(self, state: SceneState):
        """Set state and notify callback"""
        if self._state != state:
            self._state = state
            if self._on_state_change:
                self._on_state_change(state)

    # Callbacks
    def set_on_state_change(self, callback: Callable[[SceneState], None]):
        self._on_state_change = callback

    def set_on_position_update(self, callback: Callable[[float], None]):
        self._on_position_update = callback

    def set_on_complete(self, callback: Callable):
        self._on_complete = callback

    def set_on_loop(self, callback: Callable[[int], None]):
        self._on_loop = callback

    # Properties
    @property
    def state(self) -> SceneState:
        return self._state

    @property
    def loop_count(self) -> int:
        return self._loop_count

    @property
    def is_playing(self) -> bool:
        return self._state == SceneState.PLAYING

    @property
    def is_paused(self) -> bool:
        return self._state == SceneState.PAUSED

    def get_status(self) -> Dict[str, Any]:
        """Get scene player status"""
        return {
            "scene_id": self.scene.id,
            "scene_name": self.scene.name,
            "state": self._state.value,
            "position_ms": self.get_elapsed_ms(),
            "duration_ms": self.get_duration_ms(),
            "loop_count": self._loop_count,
            "has_dmx": self._dmx_sequence is not None,
            "media_count": len(self._media_list),
        }
