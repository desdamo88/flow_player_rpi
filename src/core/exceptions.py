"""Custom exceptions for Flow Player"""


class FlowPlayerError(Exception):
    """Base exception for Flow Player"""
    pass


class ProjectError(FlowPlayerError):
    """Error related to project loading/parsing"""
    pass


class ProjectNotFoundError(ProjectError):
    """Project file not found"""
    pass


class InvalidProjectError(ProjectError):
    """Invalid project format or structure"""
    pass


class MediaError(FlowPlayerError):
    """Error related to media files"""
    pass


class MediaNotFoundError(MediaError):
    """Media file not found"""
    pass


class VideoPlayerError(FlowPlayerError):
    """Error related to video playback"""
    pass


class DMXError(FlowPlayerError):
    """Error related to DMX output"""
    pass


class DMXConnectionError(DMXError):
    """Cannot connect to DMX device/network"""
    pass


class SchedulerError(FlowPlayerError):
    """Error related to scheduling"""
    pass


class ConfigError(FlowPlayerError):
    """Error related to configuration"""
    pass
