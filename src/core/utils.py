"""Utility functions for Flow Player"""

import os
import socket
import logging
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import psutil

logger = logging.getLogger(__name__)


def get_device_id() -> str:
    """Get unique device ID based on Raspberry Pi serial number or MAC address"""
    # Try to get Raspberry Pi serial number
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    return line.split(':')[1].strip()
    except Exception:
        pass

    # Fallback to MAC address hash
    try:
        mac = get_mac_address()
        if mac:
            return hashlib.md5(mac.encode()).hexdigest()[:16]
    except Exception:
        pass

    # Last resort: hostname hash
    return hashlib.md5(socket.gethostname().encode()).hexdigest()[:16]


def get_hostname() -> str:
    """Get system hostname"""
    return socket.gethostname()


def get_ip_address() -> str:
    """Get primary IP address"""
    try:
        # Create a socket to determine the outgoing IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_mac_address() -> Optional[str]:
    """Get MAC address of primary network interface"""
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            if iface == 'lo':
                continue
            for addr in addrs:
                if addr.family == psutil.AF_LINK:
                    return addr.address
    except Exception:
        pass
    return None


def get_system_info() -> Dict[str, Any]:
    """Get system metrics (CPU, RAM, temperature, etc.)"""
    info = {
        "uptime": get_uptime(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "temperature": get_cpu_temperature(),
        "disk_free_gb": get_disk_free_gb(),
    }
    return info


def get_uptime() -> int:
    """Get system uptime in seconds"""
    return int(datetime.now().timestamp() - psutil.boot_time())


def get_cpu_temperature() -> Optional[float]:
    """Get CPU temperature (Raspberry Pi specific)"""
    # Method 1: Read from thermal zone (Linux)
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000.0
            return round(temp, 1)
    except Exception:
        pass

    # Method 2: Use vcgencmd (Raspberry Pi)
    try:
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            # Output: temp=45.0'C
            temp_str = result.stdout.strip()
            temp = float(temp_str.split('=')[1].replace("'C", ""))
            return round(temp, 1)
    except Exception:
        pass

    return None


def get_disk_free_gb(path: str = "/") -> float:
    """Get free disk space in GB"""
    try:
        usage = psutil.disk_usage(path)
        return round(usage.free / (1024**3), 2)
    except Exception:
        return 0.0


def format_duration(ms: int) -> str:
    """Format milliseconds to MM:SS or HH:MM:SS"""
    seconds = ms // 1000
    minutes = seconds // 60
    hours = minutes // 60

    if hours > 0:
        return f"{hours}:{minutes % 60:02d}:{seconds % 60:02d}"
    return f"{minutes}:{seconds % 60:02d}"


def ensure_directory(path: Path) -> Path:
    """Ensure directory exists, create if necessary"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_raspberry_pi() -> bool:
    """Check if running on Raspberry Pi"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            content = f.read()
            return 'Raspberry Pi' in content or 'BCM' in content
    except Exception:
        return False


def scan_usb_dmx_devices() -> list:
    """Scan for USB DMX devices"""
    devices = []

    # Common USB serial device paths
    paths = [
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/serial/by-id/*"
    ]

    import glob
    for pattern in paths:
        for device_path in glob.glob(pattern):
            device_info = {
                "path": device_path,
                "name": os.path.basename(device_path),
            }

            # Try to identify the device
            if "ENTTEC" in device_path.upper():
                device_info["type"] = "enttec"
            elif "DMX" in device_path.upper():
                device_info["type"] = "dmx"
            else:
                device_info["type"] = "unknown"

            devices.append(device_info)

    return devices


def interpolate_value(start: int, end: int, progress: float, easing: str = "linear") -> int:
    """Interpolate between two values with easing

    Args:
        start: Start value (0-255)
        end: End value (0-255)
        progress: Progress from 0.0 to 1.0
        easing: Easing type (linear, ease-in, ease-out, ease-in-out)

    Returns:
        Interpolated value
    """
    import math

    # Clamp progress
    progress = max(0.0, min(1.0, progress))

    # Apply easing
    if easing == "linear":
        t = progress
    elif easing == "ease-in":
        t = progress * progress
    elif easing == "ease-out":
        t = 1 - (1 - progress) * (1 - progress)
    elif easing == "ease-in-out":
        if progress < 0.5:
            t = 2 * progress * progress
        else:
            t = 1 - pow(-2 * progress + 2, 2) / 2
    else:
        t = progress

    # Interpolate
    value = start + (end - start) * t
    return int(round(value))


def interpolate_dmx_frame(
    keyframe1: dict,
    keyframe2: dict,
    current_time: float,
    interpolation: str = "linear"
) -> list:
    """Interpolate DMX values between two keyframes

    Args:
        keyframe1: First keyframe with 'time' and 'values'
        keyframe2: Second keyframe with 'time' and 'values'
        current_time: Current time in seconds
        interpolation: Interpolation mode

    Returns:
        List of interpolated DMX values
    """
    time1 = keyframe1["time"]
    time2 = keyframe2["time"]
    values1 = keyframe1["values"]
    values2 = keyframe2["values"]

    # Calculate progress
    if time2 == time1:
        progress = 1.0
    else:
        progress = (current_time - time1) / (time2 - time1)

    # Interpolate each channel
    result = []
    for i in range(max(len(values1), len(values2))):
        v1 = values1[i] if i < len(values1) else 0
        v2 = values2[i] if i < len(values2) else 0
        result.append(interpolate_value(v1, v2, progress, interpolation))

    return result
