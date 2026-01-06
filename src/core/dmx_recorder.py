"""DMX Recorder - Record Art-Net DMX data from network

Records incoming Art-Net DMX frames for later playback.
Useful for capturing complex sequences from a lighting console.
"""

import json
import time
import socket
import struct
import threading
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Art-Net constants
ARTNET_PORT = 6454
ARTNET_HEADER = b'Art-Net\x00'
ARTNET_OPCODE_DMX = 0x5000


@dataclass
class DMXFrame:
    """Single DMX frame with timestamp"""
    timestamp_ms: int  # Milliseconds from recording start
    channels: List[int]  # 512 channel values (0-255)

    def to_dict(self) -> Dict:
        return {
            "t": self.timestamp_ms,
            "d": self.channels
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DMXFrame":
        return cls(
            timestamp_ms=data["t"],
            channels=data["d"]
        )


@dataclass
class DMXRecording:
    """Complete DMX recording"""
    name: str = "Untitled Recording"
    version: str = "1.0"
    recorded_at: str = ""
    duration_ms: int = 0
    fps: int = 40
    universe: int = 0
    source_ip: str = ""

    # Trim points (for editing)
    trim_start_ms: int = 0
    trim_end_ms: int = 0

    # Frames data
    frames: List[DMXFrame] = field(default_factory=list)

    # File path (when loaded from file)
    file_path: Optional[Path] = None

    def __post_init__(self):
        if not self.recorded_at:
            self.recorded_at = datetime.utcnow().isoformat() + "Z"
        if self.trim_end_ms == 0 and self.duration_ms > 0:
            self.trim_end_ms = self.duration_ms

    def add_frame(self, timestamp_ms: int, channels: List[int]):
        """Add a frame to the recording"""
        self.frames.append(DMXFrame(timestamp_ms, channels))
        self.duration_ms = max(self.duration_ms, timestamp_ms)
        if self.trim_end_ms == 0:
            self.trim_end_ms = self.duration_ms

    def get_trimmed_frames(self) -> List[DMXFrame]:
        """Get frames within trim range"""
        return [
            f for f in self.frames
            if self.trim_start_ms <= f.timestamp_ms <= self.trim_end_ms
        ]

    def get_frame_at(self, time_ms: int) -> Optional[DMXFrame]:
        """Get the frame at or before the given time"""
        # Adjust for trim
        adjusted_time = time_ms + self.trim_start_ms

        # Find the frame at or just before this time
        result = None
        for frame in self.frames:
            if frame.timestamp_ms <= adjusted_time:
                result = frame
            else:
                break
        return result

    def get_frame_at_time(self, time_ms: int) -> Optional[List[int]]:
        """Get channel values at the given time (respecting trim)

        This method is optimized for use by ScenePlayer for DMX sync.

        Args:
            time_ms: Time in milliseconds from playback start

        Returns:
            List of 512 channel values, or None if no frame available
        """
        # Check if past end of recording
        trimmed_duration = self.get_trimmed_duration()
        if time_ms > trimmed_duration:
            # Return last frame
            if self.frames:
                return self.frames[-1].channels
            return None

        frame = self.get_frame_at(time_ms)
        if frame:
            return frame.channels
        return None

    def get_trimmed_duration(self) -> int:
        """Get duration considering trim points"""
        return self.trim_end_ms - self.trim_start_ms

    def save(self, path: Path) -> bool:
        """Save recording to file"""
        try:
            data = {
                "version": self.version,
                "name": self.name,
                "recorded_at": self.recorded_at,
                "duration_ms": self.duration_ms,
                "fps": self.fps,
                "universe": self.universe,
                "source_ip": self.source_ip,
                "trim_start_ms": self.trim_start_ms,
                "trim_end_ms": self.trim_end_ms,
                "frames": [f.to_dict() for f in self.frames]
            }

            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(data, f)

            self.file_path = path
            logger.info(f"Recording saved to {path} ({len(self.frames)} frames)")
            return True
        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return False

    @classmethod
    def load(cls, path: Path) -> Optional["DMXRecording"]:
        """Load recording from file"""
        try:
            with open(path, 'r') as f:
                data = json.load(f)

            recording = cls(
                name=data.get("name", path.stem),
                version=data.get("version", "1.0"),
                recorded_at=data.get("recorded_at", ""),
                duration_ms=data.get("duration_ms", 0),
                fps=data.get("fps", 40),
                universe=data.get("universe", 0),
                source_ip=data.get("source_ip", ""),
                trim_start_ms=data.get("trim_start_ms", 0),
                trim_end_ms=data.get("trim_end_ms", 0),
            )

            # Load frames
            for frame_data in data.get("frames", []):
                recording.frames.append(DMXFrame.from_dict(frame_data))

            recording.file_path = path
            logger.info(f"Recording loaded from {path} ({len(recording.frames)} frames)")
            return recording
        except Exception as e:
            logger.error(f"Failed to load recording from {path}: {e}")
            return None

    def to_info_dict(self) -> Dict:
        """Get recording info (without frames data)"""
        return {
            "name": self.name,
            "recorded_at": self.recorded_at,
            "duration_ms": self.duration_ms,
            "trimmed_duration_ms": self.get_trimmed_duration(),
            "fps": self.fps,
            "universe": self.universe,
            "source_ip": self.source_ip,
            "trim_start_ms": self.trim_start_ms,
            "trim_end_ms": self.trim_end_ms,
            "frame_count": len(self.frames),
            "file_path": str(self.file_path) if self.file_path else None
        }


class DMXRecorder:
    """Art-Net DMX Recorder

    Listens for incoming Art-Net packets and records DMX frames.

    Usage:
        recorder = DMXRecorder(recordings_path)
        recorder.start_recording("My Sequence", universe=0)
        # ... wait for Art-Net data ...
        recording = recorder.stop_recording()
        recording.save(path)
    """

    def __init__(self, recordings_path: Path):
        self.recordings_path = Path(recordings_path)
        self.recordings_path.mkdir(parents=True, exist_ok=True)

        self._socket: Optional[socket.socket] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._running = False

        # Recording state
        self._recording = False
        self._current_recording: Optional[DMXRecording] = None
        self._record_start_time: float = 0
        self._record_universe: int = 0

        # Callbacks
        self._on_frame_callback: Optional[Callable[[DMXFrame], None]] = None
        self._on_recording_complete: Optional[Callable[[DMXRecording], None]] = None

        # Stats
        self._frames_received = 0
        self._last_frame_time: float = 0

    def set_on_frame(self, callback: Callable[[DMXFrame], None]):
        """Set callback for each received frame (for live preview)"""
        self._on_frame_callback = callback

    def set_on_recording_complete(self, callback: Callable[[DMXRecording], None]):
        """Set callback when recording stops"""
        self._on_recording_complete = callback

    def start_listening(self, bind_ip: str = "0.0.0.0", port: int = ARTNET_PORT) -> bool:
        """Start listening for Art-Net packets"""
        if self._running:
            logger.warning("Already listening")
            return True

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((bind_ip, port))
            self._socket.settimeout(0.5)

            self._running = True
            self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listen_thread.start()

            logger.info(f"DMX Recorder listening on {bind_ip}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start listening: {e}")
            return False

    def stop_listening(self):
        """Stop listening for Art-Net packets"""
        self._running = False

        if self._recording:
            self.stop_recording()

        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
            self._listen_thread = None

        if self._socket:
            self._socket.close()
            self._socket = None

        logger.info("DMX Recorder stopped listening")

    def start_recording(self, name: str = "Untitled", universe: int = 0) -> bool:
        """Start recording DMX frames"""
        if self._recording:
            logger.warning("Already recording")
            return False

        if not self._running:
            logger.warning("Not listening - call start_listening() first")
            return False

        self._current_recording = DMXRecording(
            name=name,
            universe=universe,
            fps=40
        )
        self._record_universe = universe
        self._record_start_time = time.time()
        self._recording = True
        self._frames_received = 0

        logger.info(f"Started recording '{name}' on universe {universe}")
        return True

    def stop_recording(self) -> Optional[DMXRecording]:
        """Stop recording and return the recording"""
        if not self._recording:
            return None

        self._recording = False
        recording = self._current_recording
        self._current_recording = None

        if recording:
            recording.trim_end_ms = recording.duration_ms
            logger.info(f"Stopped recording '{recording.name}': {len(recording.frames)} frames, {recording.duration_ms}ms")

            if self._on_recording_complete:
                self._on_recording_complete(recording)

        return recording

    def is_recording(self) -> bool:
        return self._recording

    def is_listening(self) -> bool:
        return self._running

    def get_recording_status(self) -> Dict:
        """Get current recording status"""
        return {
            "listening": self._running,
            "recording": self._recording,
            "universe": self._record_universe if self._recording else None,
            "name": self._current_recording.name if self._current_recording else None,
            "duration_ms": self._current_recording.duration_ms if self._current_recording else 0,
            "frame_count": len(self._current_recording.frames) if self._current_recording else 0,
            "frames_received": self._frames_received,
            "last_frame_age_ms": int((time.time() - self._last_frame_time) * 1000) if self._last_frame_time else None
        }

    def list_recordings(self) -> List[Dict]:
        """List all saved recordings"""
        recordings = []
        for path in self.recordings_path.glob("*.dmxr"):
            try:
                recording = DMXRecording.load(path)
                if recording:
                    recordings.append(recording.to_info_dict())
            except Exception as e:
                logger.warning(f"Failed to load recording {path}: {e}")
        return recordings

    def load_recording(self, name_or_path: str) -> Optional[DMXRecording]:
        """Load a recording by name or path"""
        # Try as direct path
        path = Path(name_or_path)
        if path.exists():
            return DMXRecording.load(path)

        # Try in recordings directory
        path = self.recordings_path / f"{name_or_path}.dmxr"
        if path.exists():
            return DMXRecording.load(path)

        return None

    def delete_recording(self, name_or_path: str) -> bool:
        """Delete a recording"""
        path = Path(name_or_path)
        if not path.exists():
            path = self.recordings_path / f"{name_or_path}.dmxr"

        if path.exists():
            path.unlink()
            logger.info(f"Deleted recording: {path}")
            return True
        return False

    def _listen_loop(self):
        """Main loop for receiving Art-Net packets"""
        while self._running:
            try:
                data, addr = self._socket.recvfrom(1024)
                self._process_packet(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Error receiving packet: {e}")

    def _process_packet(self, data: bytes, addr: tuple):
        """Process an incoming Art-Net packet"""
        # Verify Art-Net header
        if len(data) < 18 or data[:8] != ARTNET_HEADER:
            return

        # Get opcode (little-endian)
        opcode = struct.unpack('<H', data[8:10])[0]

        if opcode != ARTNET_OPCODE_DMX:
            return  # Not a DMX packet

        # Parse Art-Net DMX packet
        # Bytes 10-11: Protocol version (ignored)
        # Byte 12: Sequence (ignored)
        # Byte 13: Physical (ignored)
        # Bytes 14-15: Universe (little-endian)
        # Bytes 16-17: Length (big-endian)
        # Bytes 18+: DMX data

        universe = struct.unpack('<H', data[14:16])[0]
        length = struct.unpack('>H', data[16:18])[0]
        dmx_data = list(data[18:18 + length])

        # Pad to 512 channels if needed
        while len(dmx_data) < 512:
            dmx_data.append(0)

        self._last_frame_time = time.time()
        self._frames_received += 1

        # If recording and matching universe
        if self._recording and universe == self._record_universe:
            timestamp_ms = int((time.time() - self._record_start_time) * 1000)
            self._current_recording.add_frame(timestamp_ms, dmx_data)

            # Store source IP on first frame
            if not self._current_recording.source_ip:
                self._current_recording.source_ip = addr[0]

        # Callback for live preview
        if self._on_frame_callback:
            frame = DMXFrame(
                timestamp_ms=int(time.time() * 1000),
                channels=dmx_data
            )
            try:
                self._on_frame_callback(frame)
            except Exception as e:
                logger.warning(f"Frame callback error: {e}")


class DMXRecordingPlayer:
    """Plays back a DMX recording

    Can be used standalone or integrated with ScenePlayer for sync.
    """

    def __init__(self, dmx_output_callback: Callable[[List[int]], None]):
        """
        Args:
            dmx_output_callback: Function to call with DMX channel values
        """
        self._output_callback = dmx_output_callback
        self._recording: Optional[DMXRecording] = None
        self._playing = False
        self._paused = False
        self._loop = False

        self._play_thread: Optional[threading.Thread] = None
        self._start_time: float = 0
        self._pause_time: float = 0
        self._current_position_ms: int = 0

    def load(self, recording: DMXRecording):
        """Load a recording for playback"""
        self.stop()
        self._recording = recording
        self._current_position_ms = 0

    def play(self, loop: bool = False):
        """Start playback"""
        if not self._recording:
            logger.warning("No recording loaded")
            return

        if self._playing and not self._paused:
            return

        self._loop = loop

        if self._paused:
            # Resume from pause
            pause_duration = time.time() - self._pause_time
            self._start_time += pause_duration
            self._paused = False
        else:
            # Start fresh
            self._start_time = time.time()
            self._current_position_ms = 0
            self._playing = True
            self._play_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self._play_thread.start()

        logger.info(f"Playing recording '{self._recording.name}'")

    def pause(self):
        """Pause playback"""
        if self._playing and not self._paused:
            self._paused = True
            self._pause_time = time.time()
            logger.info("Playback paused")

    def stop(self):
        """Stop playback"""
        self._playing = False
        self._paused = False
        if self._play_thread:
            self._play_thread.join(timeout=1.0)
            self._play_thread = None
        self._current_position_ms = 0
        logger.info("Playback stopped")

    def seek(self, position_ms: int):
        """Seek to position"""
        if self._recording:
            self._current_position_ms = max(0, min(position_ms, self._recording.get_trimmed_duration()))
            self._start_time = time.time() - (self._current_position_ms / 1000.0)

    def get_position(self) -> int:
        """Get current playback position in ms"""
        return self._current_position_ms

    def get_duration(self) -> int:
        """Get recording duration in ms"""
        return self._recording.get_trimmed_duration() if self._recording else 0

    def is_playing(self) -> bool:
        return self._playing and not self._paused

    def _playback_loop(self):
        """Main playback loop"""
        fps = self._recording.fps if self._recording else 40
        frame_time = 1.0 / fps

        while self._playing:
            if self._paused:
                time.sleep(0.05)
                continue

            # Calculate current position
            elapsed = time.time() - self._start_time
            self._current_position_ms = int(elapsed * 1000)

            # Check if finished
            duration = self._recording.get_trimmed_duration()
            if self._current_position_ms >= duration:
                if self._loop:
                    self._start_time = time.time()
                    self._current_position_ms = 0
                else:
                    self._playing = False
                    logger.info("Playback finished")
                    break

            # Get frame at current position
            frame = self._recording.get_frame_at(self._current_position_ms)
            if frame:
                try:
                    self._output_callback(frame.channels)
                except Exception as e:
                    logger.error(f"Output callback error: {e}")

            # Sleep until next frame
            time.sleep(frame_time)
