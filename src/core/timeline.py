"""Timeline - Master synchronization for video/audio/DMX"""

import time
import logging
import threading
from enum import Enum
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PlaybackState(Enum):
    """Playback state enumeration"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"
    ERROR = "error"


@dataclass
class TimelineEvent:
    """Event triggered at a specific time"""
    time_ms: int
    event_type: str
    data: Dict[str, Any]
    callback: Optional[Callable] = None


class Timeline:
    """Master timeline for synchronized playback

    Synchronizes video, DMX, and audio playback to a common timeline.
    Video is the master clock source.
    """

    def __init__(self):
        self._state = PlaybackState.STOPPED
        self._duration_ms = 0
        self._position_ms = 0
        self._loop = False
        self._loop_count = 0
        self._speed = 1.0

        # Timing
        self._start_time: Optional[float] = None
        self._pause_time: Optional[float] = None
        self._accumulated_time = 0.0

        # Components
        self._video_player = None
        self._dmx_player = None

        # Events
        self._events: List[TimelineEvent] = []
        self._triggered_events: set = set()

        # Callbacks
        self._on_state_change: Optional[Callable[[PlaybackState], None]] = None
        self._on_position_change: Optional[Callable[[int], None]] = None
        self._on_loop: Optional[Callable[[int], None]] = None
        self._on_complete: Optional[Callable] = None

        # Update thread
        self._running = False
        self._update_thread: Optional[threading.Thread] = None
        self._update_interval = 1.0 / 60.0  # 60 FPS update rate

    def set_video_player(self, player):
        """Set the video player reference"""
        self._video_player = player

        # Subscribe to video position updates
        if player:
            player.set_on_position_update(self._on_video_position_update)
            player.set_on_end_file(self._on_video_end)

    def set_dmx_player(self, player):
        """Set the DMX player reference"""
        self._dmx_player = player

    def _on_video_position_update(self, position: float):
        """Called when video position changes (video is master clock)"""
        self._position_ms = int(position * 1000)
        self._check_events()

        if self._on_position_change:
            self._on_position_change(self._position_ms)

    def _on_video_end(self):
        """Called when video reaches end"""
        self._loop_count += 1

        if self._loop:
            self._triggered_events.clear()
            if self._on_loop:
                self._on_loop(self._loop_count)
        else:
            self.stop()
            if self._on_complete:
                self._on_complete()

    def set_duration(self, duration_ms: int):
        """Set timeline duration in milliseconds"""
        self._duration_ms = duration_ms

    def add_event(self, event: TimelineEvent):
        """Add a timed event to the timeline"""
        self._events.append(event)
        self._events.sort(key=lambda e: e.time_ms)

    def clear_events(self):
        """Clear all timeline events"""
        self._events.clear()
        self._triggered_events.clear()

    def _check_events(self):
        """Check and trigger events at current position"""
        for event in self._events:
            event_id = id(event)
            if event_id in self._triggered_events:
                continue

            if self._position_ms >= event.time_ms:
                self._triggered_events.add(event_id)
                if event.callback:
                    try:
                        event.callback(event)
                    except Exception as e:
                        logger.error(f"Event callback error: {e}")

    def play(self, loop: bool = False):
        """Start playback"""
        if self._state == PlaybackState.PLAYING:
            return

        self._loop = loop
        self._loop_count = 0
        self._triggered_events.clear()

        # Start video player
        if self._video_player:
            self._video_player.play(loop=loop)

        # Start DMX player
        if self._dmx_player:
            self._dmx_player.play(loop=loop)

        self._start_time = time.time()
        self._set_state(PlaybackState.PLAYING)
        self._start_update_thread()

        logger.info(f"Timeline playback started (loop={loop})")

    def stop(self):
        """Stop playback"""
        self._stop_update_thread()

        if self._video_player:
            self._video_player.stop()

        if self._dmx_player:
            self._dmx_player.stop()
            self._dmx_player.blackout()

        self._position_ms = 0
        self._start_time = None
        self._pause_time = None
        self._accumulated_time = 0.0
        self._triggered_events.clear()

        self._set_state(PlaybackState.STOPPED)
        logger.info("Timeline playback stopped")

    def pause(self):
        """Pause playback"""
        if self._state != PlaybackState.PLAYING:
            return

        self._pause_time = time.time()

        if self._video_player:
            self._video_player.pause()

        if self._dmx_player:
            self._dmx_player.pause()

        self._set_state(PlaybackState.PAUSED)
        logger.info("Timeline paused")

    def resume(self):
        """Resume playback"""
        if self._state != PlaybackState.PAUSED:
            return

        if self._pause_time:
            self._accumulated_time += time.time() - self._pause_time
        self._pause_time = None

        if self._video_player:
            self._video_player.resume()

        if self._dmx_player:
            self._dmx_player.resume()

        self._set_state(PlaybackState.PLAYING)
        logger.info("Timeline resumed")

    def seek(self, position_ms: int):
        """Seek to position in milliseconds"""
        position_ms = max(0, min(position_ms, self._duration_ms))

        if self._video_player:
            self._video_player.seek(position_ms / 1000.0)

        if self._dmx_player:
            self._dmx_player.seek(position_ms / 1000.0)

        self._position_ms = position_ms

        # Reset events past this point
        self._triggered_events = {
            id(e) for e in self._events if e.time_ms < position_ms
        }

        logger.info(f"Timeline seek to {position_ms}ms")

    def set_speed(self, speed: float):
        """Set playback speed"""
        self._speed = max(0.1, min(4.0, speed))

        if self._video_player:
            self._video_player.set_speed(speed)

    def _set_state(self, state: PlaybackState):
        """Set playback state and trigger callback"""
        if self._state != state:
            self._state = state
            if self._on_state_change:
                self._on_state_change(state)

    def _start_update_thread(self):
        """Start the update thread"""
        if self._running:
            return

        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

    def _stop_update_thread(self):
        """Stop the update thread"""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=1.0)
            self._update_thread = None

    def _update_loop(self):
        """Main update loop"""
        last_update = time.time()

        while self._running:
            now = time.time()
            dt = now - last_update
            last_update = now

            if self._state == PlaybackState.PLAYING:
                # Update DMX player
                if self._dmx_player:
                    self._dmx_player.update(dt * self._speed)

            time.sleep(self._update_interval)

    # Callbacks setters
    def set_on_state_change(self, callback: Callable[[PlaybackState], None]):
        """Set callback for state changes"""
        self._on_state_change = callback

    def set_on_position_change(self, callback: Callable[[int], None]):
        """Set callback for position changes"""
        self._on_position_change = callback

    def set_on_loop(self, callback: Callable[[int], None]):
        """Set callback for loop events"""
        self._on_loop = callback

    def set_on_complete(self, callback: Callable):
        """Set callback for playback completion"""
        self._on_complete = callback

    # Getters
    def get_state(self) -> PlaybackState:
        """Get current playback state"""
        return self._state

    def get_position_ms(self) -> int:
        """Get current position in milliseconds"""
        return self._position_ms

    def get_duration_ms(self) -> int:
        """Get duration in milliseconds"""
        return self._duration_ms

    def get_loop_count(self) -> int:
        """Get number of completed loops"""
        return self._loop_count

    def is_playing(self) -> bool:
        """Check if playing"""
        return self._state == PlaybackState.PLAYING

    def is_paused(self) -> bool:
        """Check if paused"""
        return self._state == PlaybackState.PAUSED

    def is_stopped(self) -> bool:
        """Check if stopped"""
        return self._state == PlaybackState.STOPPED

    def get_status(self) -> Dict[str, Any]:
        """Get timeline status for API"""
        return {
            "state": self._state.value,
            "position_ms": self._position_ms,
            "duration_ms": self._duration_ms,
            "loop": self._loop,
            "loop_count": self._loop_count,
            "speed": self._speed,
        }

    def shutdown(self):
        """Shutdown timeline"""
        self.stop()
        logger.info("Timeline shutdown complete")
