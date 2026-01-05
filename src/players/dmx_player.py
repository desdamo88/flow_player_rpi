"""DMX Player - Art-Net, sACN, and USB DMX output"""

import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from ..core.config import DMXConfig
from ..core.exceptions import DMXError, DMXConnectionError
from ..core.utils import interpolate_dmx_frame

logger = logging.getLogger(__name__)

# DMX constants
DMX_CHANNELS = 512
DMX_MIN_VALUE = 0
DMX_MAX_VALUE = 255


@dataclass
class DMXKeyframe:
    """Represents a DMX keyframe"""
    time: float  # Time in seconds
    fixture_id: str
    values: List[int]


class DMXOutput(ABC):
    """Abstract base class for DMX output devices"""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the DMX output device"""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the DMX output device"""
        pass

    @abstractmethod
    def send(self, data: bytes):
        """Send DMX data (512 bytes)"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected"""
        pass


class ArtNetOutput(DMXOutput):
    """Art-Net DMX output over network"""

    def __init__(self, ip: str = "255.255.255.255", port: int = 6454, universe: int = 0):
        self.ip = ip
        self.port = port
        self.universe = universe
        self._artnet = None
        self._connected = False

    def connect(self) -> bool:
        try:
            from stupidArtnet import StupidArtnet

            self._artnet = StupidArtnet(
                target_ip=self.ip,
                universe=self.universe,
                packet_size=DMX_CHANNELS,
                fps=40,
                even_packet_size=True,
                broadcast=self.ip == "255.255.255.255"
            )
            self._artnet.start()
            self._connected = True
            logger.info(f"Art-Net connected: {self.ip}:{self.port} universe {self.universe}")
            return True
        except Exception as e:
            logger.error(f"Art-Net connection failed: {e}")
            raise DMXConnectionError(f"Art-Net connection failed: {e}")

    def disconnect(self):
        if self._artnet:
            try:
                self._artnet.stop()
            except Exception:
                pass
            self._artnet = None
        self._connected = False
        logger.info("Art-Net disconnected")

    def send(self, data: bytes):
        if self._artnet and self._connected:
            # StupidArtnet expects a list or bytearray
            self._artnet.set(bytearray(data))

    def is_connected(self) -> bool:
        return self._connected


class SACNOutput(DMXOutput):
    """sACN / E1.31 DMX output over network"""

    def __init__(self, universe: int = 1, multicast: bool = True):
        self.universe = universe
        self.multicast = multicast
        self._sender = None
        self._connected = False

    def connect(self) -> bool:
        try:
            import sacn

            self._sender = sacn.sACNsender()
            self._sender.start()
            self._sender.activate_output(self.universe)
            self._sender[self.universe].multicast = self.multicast
            self._connected = True
            logger.info(f"sACN connected: universe {self.universe}, multicast={self.multicast}")
            return True
        except Exception as e:
            logger.error(f"sACN connection failed: {e}")
            raise DMXConnectionError(f"sACN connection failed: {e}")

    def disconnect(self):
        if self._sender:
            try:
                self._sender.stop()
            except Exception:
                pass
            self._sender = None
        self._connected = False
        logger.info("sACN disconnected")

    def send(self, data: bytes):
        if self._sender and self._connected:
            # sACN expects tuple of integers
            self._sender[self.universe].dmx_data = tuple(data)

    def is_connected(self) -> bool:
        return self._connected


class USBDMXOutput(DMXOutput):
    """USB DMX output (ENTTEC, DMXKing, etc.)"""

    # ENTTEC Pro protocol constants
    ENTTEC_PRO_START_MSG = 0x7E
    ENTTEC_PRO_END_MSG = 0xE7
    ENTTEC_PRO_SEND_DMX_RQ = 6
    ENTTEC_PRO_RECV_DMX_PKT = 5

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        driver: str = "enttec_pro",
        baudrate: int = 250000
    ):
        self.port = port
        self.driver = driver
        self.baudrate = baudrate
        self._serial = None
        self._connected = False

    def connect(self) -> bool:
        try:
            import serial

            # Different baud rates for different devices
            if self.driver == "enttec_open":
                # ENTTEC Open DMX uses break timing, not standard serial
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=250000,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_TWO,
                    timeout=1
                )
            else:
                # ENTTEC Pro and DMXKing use standard serial
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1
                )

            self._connected = True
            logger.info(f"USB DMX connected: {self.port} (driver: {self.driver})")
            return True
        except Exception as e:
            logger.error(f"USB DMX connection failed: {e}")
            raise DMXConnectionError(f"USB DMX connection failed: {e}")

    def disconnect(self):
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._connected = False
        logger.info("USB DMX disconnected")

    def send(self, data: bytes):
        if not self._serial or not self._connected:
            return

        if self.driver == "enttec_open":
            self._send_enttec_open(data)
        elif self.driver == "enttec_pro":
            self._send_enttec_pro(data)
        elif self.driver == "dmxking":
            # DMXKing uses same protocol as ENTTEC Pro
            self._send_enttec_pro(data)
        else:
            self._send_enttec_pro(data)

    def _send_enttec_open(self, data: bytes):
        """Send DMX using ENTTEC Open DMX protocol (bit-banging break)"""
        import serial

        try:
            # Send break (low for 88us minimum)
            self._serial.break_condition = True
            time.sleep(0.000092)  # 92us break
            self._serial.break_condition = False
            time.sleep(0.000012)  # 12us mark after break (MAB)

            # Send start code (0x00) followed by DMX data
            packet = bytes([0x00]) + data
            self._serial.write(packet)
        except Exception as e:
            logger.error(f"ENTTEC Open send error: {e}")

    def _send_enttec_pro(self, data: bytes):
        """Send DMX using ENTTEC Pro protocol"""
        try:
            # Build ENTTEC Pro packet
            # Start code (0x00) is prepended to data
            dmx_data = bytes([0x00]) + data
            data_length = len(dmx_data)

            packet = bytes([
                self.ENTTEC_PRO_START_MSG,  # Start byte
                self.ENTTEC_PRO_SEND_DMX_RQ,  # Send DMX command
                data_length & 0xFF,  # Length LSB
                (data_length >> 8) & 0xFF,  # Length MSB
            ]) + dmx_data + bytes([self.ENTTEC_PRO_END_MSG])  # End byte

            self._serial.write(packet)
        except Exception as e:
            logger.error(f"ENTTEC Pro send error: {e}")

    def is_connected(self) -> bool:
        return self._connected


class DMXPlayer:
    """Main DMX player class with sequence playback"""

    def __init__(self, config: DMXConfig):
        self.config = config
        self._output: Optional[DMXOutput] = None
        self._running = False
        self._playing = False
        self._thread: Optional[threading.Thread] = None

        # Current DMX state (512 channels)
        self._dmx_data = bytearray(DMX_CHANNELS)

        # Sequence data
        self._sequences: List[Dict] = []
        self._current_time = 0.0
        self._duration = 0.0
        self._loop = False
        self._speed = 1.0

    def initialize(self) -> bool:
        """Initialize DMX output based on config"""
        if not self.config.enabled:
            logger.info("DMX disabled in config")
            return True

        try:
            if self.config.mode == "artnet":
                self._output = ArtNetOutput(
                    ip=self.config.ip,
                    port=self.config.port,
                    universe=self.config.universe
                )
            elif self.config.mode == "sacn":
                self._output = SACNOutput(
                    universe=self.config.universe,
                    multicast=self.config.sacn_multicast
                )
            elif self.config.mode == "usb":
                self._output = USBDMXOutput(
                    port=self.config.usb_port,
                    driver=self.config.usb_driver,
                    baudrate=self.config.usb_baudrate
                )
            else:
                logger.error(f"Unknown DMX mode: {self.config.mode}")
                return False

            self._output.connect()
            self._start_output_thread()
            return True

        except DMXConnectionError as e:
            logger.error(f"DMX initialization failed: {e}")
            return False

    def _start_output_thread(self):
        """Start the DMX output thread"""
        self._running = True
        self._thread = threading.Thread(target=self._output_loop, daemon=True)
        self._thread.start()

    def _output_loop(self):
        """Main DMX output loop"""
        interval = 1.0 / self.config.fps
        last_send = time.time()

        while self._running:
            now = time.time()
            elapsed = now - last_send

            if elapsed >= interval:
                if self._output and self._output.is_connected():
                    self._output.send(bytes(self._dmx_data))
                last_send = now

            # Small sleep to prevent busy-waiting
            time.sleep(0.001)

    def load_sequences(self, sequences: List[Dict]):
        """Load DMX sequences from project data"""
        self._sequences = sequences

        # Calculate total duration
        max_duration = 0.0
        for seq in sequences:
            seq_duration = seq.get("duration", 0)
            max_duration = max(max_duration, seq_duration)
        self._duration = max_duration

        logger.info(f"Loaded {len(sequences)} DMX sequences, duration: {self._duration}s")

    def play(self, loop: bool = False, speed: float = 1.0):
        """Start DMX sequence playback"""
        self._loop = loop
        self._speed = speed
        self._current_time = 0.0
        self._playing = True
        logger.info("DMX playback started")

    def stop(self):
        """Stop DMX playback"""
        self._playing = False
        logger.info("DMX playback stopped")

    def pause(self):
        """Pause DMX playback"""
        self._playing = False

    def resume(self):
        """Resume DMX playback"""
        self._playing = True

    def seek(self, time_seconds: float):
        """Seek to specific time"""
        self._current_time = max(0.0, min(time_seconds, self._duration))

    def update(self, dt: float):
        """Update DMX state based on elapsed time

        Args:
            dt: Delta time in seconds since last update
        """
        if not self._playing:
            return

        self._current_time += dt * self._speed

        # Handle loop or end
        if self._current_time >= self._duration:
            if self._loop:
                self._current_time = 0.0
            else:
                self._playing = False
                self.blackout()
                return

        # Update DMX values from sequences
        self._update_dmx_from_sequences()

    def _update_dmx_from_sequences(self):
        """Calculate current DMX values from all sequences"""
        for sequence in self._sequences:
            if not sequence.get("keyframes"):
                continue

            keyframes = sequence["keyframes"]
            interpolation = sequence.get("interpolation", "linear")
            speed = sequence.get("speed", 1.0)

            seq_time = self._current_time * speed

            # Find surrounding keyframes
            prev_kf = None
            next_kf = None

            for kf in keyframes:
                if kf["time"] <= seq_time:
                    prev_kf = kf
                elif next_kf is None:
                    next_kf = kf
                    break

            if prev_kf is None:
                continue

            # Calculate values
            if next_kf is None:
                # Past last keyframe, use last values
                values = prev_kf["values"]
            else:
                # Interpolate between keyframes
                values = interpolate_dmx_frame(
                    prev_kf, next_kf, seq_time, interpolation
                )

            # Apply values to DMX data
            # TODO: Map fixture channels properly based on fixture definitions
            # For now, assume sequential channel mapping starting at channel 1
            start_channel = 0
            for i, value in enumerate(values):
                if start_channel + i < DMX_CHANNELS:
                    self._dmx_data[start_channel + i] = max(0, min(255, value))

    def set_channel(self, channel: int, value: int):
        """Set a single DMX channel value

        Args:
            channel: Channel number (1-512)
            value: Value (0-255)
        """
        if 1 <= channel <= DMX_CHANNELS:
            self._dmx_data[channel - 1] = max(DMX_MIN_VALUE, min(DMX_MAX_VALUE, value))

    def set_channels(self, start_channel: int, values: List[int]):
        """Set multiple consecutive DMX channel values

        Args:
            start_channel: Starting channel number (1-512)
            values: List of values (0-255)
        """
        for i, value in enumerate(values):
            self.set_channel(start_channel + i, value)

    def blackout(self):
        """Set all channels to 0"""
        self._dmx_data = bytearray(DMX_CHANNELS)
        logger.info("DMX blackout")

    def get_dmx_data(self) -> bytes:
        """Get current DMX data"""
        return bytes(self._dmx_data)

    def get_position(self) -> float:
        """Get current playback position in seconds"""
        return self._current_time

    def get_duration(self) -> float:
        """Get total sequence duration in seconds"""
        return self._duration

    def is_playing(self) -> bool:
        """Check if DMX is currently playing"""
        return self._playing

    def is_connected(self) -> bool:
        """Check if DMX output is connected"""
        return self._output is not None and self._output.is_connected()

    def shutdown(self):
        """Shutdown DMX player"""
        self._playing = False
        self._running = False

        if self._thread:
            self._thread.join(timeout=1.0)

        self.blackout()

        if self._output:
            # Send blackout before disconnecting
            if self._output.is_connected():
                self._output.send(bytes(self._dmx_data))
                time.sleep(0.1)
            self._output.disconnect()

        logger.info("DMX player shutdown complete")
