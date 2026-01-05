"""Configuration management for Flow Player"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_BASE_PATH = Path("/opt/flow-player")
DEFAULT_SHOWS_PATH = DEFAULT_BASE_PATH / "shows"
DEFAULT_CONFIG_PATH = DEFAULT_BASE_PATH / "config"
DEFAULT_LOGS_PATH = DEFAULT_BASE_PATH / "logs"


@dataclass
class NetworkConfig:
    hostname: str = "flowplayer-01"
    dhcp: bool = True
    static_ip: Optional[str] = None


@dataclass
class VideoConfig:
    output: str = "HDMI-1"
    resolution: str = "1920x1080"
    refresh_rate: int = 60


@dataclass
class AudioConfig:
    output: str = "hdmi"  # hdmi, jack, auto
    volume: int = 100


@dataclass
class DMXConfig:
    mode: str = "artnet"  # artnet, sacn, usb
    enabled: bool = True
    # Art-Net settings
    ip: str = "255.255.255.255"
    port: int = 6454
    universe: int = 0
    # sACN settings
    sacn_multicast: bool = True
    # USB settings
    usb_port: str = "/dev/ttyUSB0"
    usb_driver: str = "enttec_pro"  # enttec_open, enttec_pro, dmxking
    usb_baudrate: int = 250000
    # Common
    fps: int = 40


@dataclass
class MonitoringConfig:
    heartbeat_enabled: bool = False
    heartbeat_url: str = ""
    heartbeat_interval_sec: int = 30
    webhook_url: str = ""


@dataclass
class Config:
    """Main configuration class for Flow Player"""

    # Paths
    base_path: Path = field(default_factory=lambda: DEFAULT_BASE_PATH)
    shows_path: Path = field(default_factory=lambda: DEFAULT_SHOWS_PATH)
    config_path: Path = field(default_factory=lambda: DEFAULT_CONFIG_PATH)
    logs_path: Path = field(default_factory=lambda: DEFAULT_LOGS_PATH)

    # Sub-configs
    network: NetworkConfig = field(default_factory=NetworkConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    dmx: DMXConfig = field(default_factory=DMXConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # Player settings
    active_show_id: Optional[str] = None
    active_scene_id: Optional[str] = None
    autoplay: bool = True
    loop: bool = True

    # Web server
    web_host: str = "0.0.0.0"
    web_port: int = 5000

    # Logging - WARNING by default for production (less CPU usage)
    # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_level: str = "WARNING"

    _config_file: Path = field(default=None, repr=False)
    _state_file: Path = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize paths and load config file if exists"""
        if isinstance(self.base_path, str):
            self.base_path = Path(self.base_path)
        if isinstance(self.shows_path, str):
            self.shows_path = Path(self.shows_path)
        if isinstance(self.config_path, str):
            self.config_path = Path(self.config_path)
        if isinstance(self.logs_path, str):
            self.logs_path = Path(self.logs_path)

        self._config_file = self.config_path / "config.json"
        self._state_file = self.config_path / "state.json"

    @classmethod
    def load(cls, config_file: Optional[Path] = None) -> "Config":
        """Load configuration from file"""
        config = cls()

        if config_file:
            config._config_file = Path(config_file)

        if config._config_file and config._config_file.exists():
            try:
                with open(config._config_file, 'r') as f:
                    data = json.load(f)
                config._update_from_dict(data)
                logger.info(f"Configuration loaded from {config._config_file}")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        else:
            logger.info("No config file found, using defaults")

        # Override with environment variables
        config._load_env_overrides()

        return config

    def _update_from_dict(self, data: dict):
        """Update config from dictionary"""
        if "network" in data:
            self.network = NetworkConfig(**data["network"])
        if "video" in data:
            self.video = VideoConfig(**data["video"])
        if "audio" in data:
            self.audio = AudioConfig(**data["audio"])
        if "dmx" in data:
            self.dmx = DMXConfig(**data["dmx"])
        if "monitoring" in data:
            self.monitoring = MonitoringConfig(**data["monitoring"])

        # Simple fields
        for key in ["active_show_id", "active_scene_id", "autoplay", "loop", "web_host", "web_port", "log_level"]:
            if key in data:
                setattr(self, key, data[key])

    def _load_env_overrides(self):
        """Load configuration overrides from environment variables"""
        # FLOW_PLAYER_WEB_PORT, FLOW_PLAYER_DMX_MODE, etc.
        prefix = "FLOW_PLAYER_"

        env_mappings = {
            f"{prefix}WEB_PORT": ("web_port", int),
            f"{prefix}WEB_HOST": ("web_host", str),
            f"{prefix}DMX_MODE": ("dmx.mode", str),
            f"{prefix}DMX_IP": ("dmx.ip", str),
            f"{prefix}DMX_UNIVERSE": ("dmx.universe", int),
            f"{prefix}LOG_LEVEL": ("log_level", str),
        }

        for env_var, (attr_path, type_fn) in env_mappings.items():
            value = os.environ.get(env_var)
            if value:
                try:
                    if "." in attr_path:
                        obj_name, attr_name = attr_path.split(".")
                        obj = getattr(self, obj_name)
                        setattr(obj, attr_name, type_fn(value))
                    else:
                        setattr(self, attr_path, type_fn(value))
                except Exception as e:
                    logger.warning(f"Error setting {env_var}: {e}")

    def save(self):
        """Save configuration to file"""
        self.config_path.mkdir(parents=True, exist_ok=True)

        data = {
            "network": asdict(self.network),
            "video": asdict(self.video),
            "audio": asdict(self.audio),
            "dmx": asdict(self.dmx),
            "monitoring": asdict(self.monitoring),
            "active_show_id": self.active_show_id,
            "active_scene_id": self.active_scene_id,
            "autoplay": self.autoplay,
            "loop": self.loop,
            "web_host": self.web_host,
            "web_port": self.web_port,
        }

        with open(self._config_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Configuration saved to {self._config_file}")

    def save_state(self, state: dict):
        """Save runtime state to state file (for quick persistence)"""
        self.config_path.mkdir(parents=True, exist_ok=True)

        with open(self._state_file, 'w') as f:
            json.dump(state, f, indent=2)

        logger.debug(f"State saved to {self._state_file}")

    def load_state(self) -> dict:
        """Load runtime state from state file"""
        if self._state_file and self._state_file.exists():
            try:
                with open(self._state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading state: {e}")
        return {}

    def to_dict(self) -> dict:
        """Convert config to dictionary for API responses"""
        return {
            "network": asdict(self.network),
            "video": asdict(self.video),
            "audio": asdict(self.audio),
            "dmx": asdict(self.dmx),
            "monitoring": asdict(self.monitoring),
            "active_show_id": self.active_show_id,
            "autoplay": self.autoplay,
            "loop": self.loop,
        }
