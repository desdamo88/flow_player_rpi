"""REST API endpoints for Flow Player"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from functools import wraps

from flask import Blueprint, jsonify, request, current_app, send_file

if TYPE_CHECKING:
    from ..flow_player import FlowPlayer

logger = logging.getLogger(__name__)


def get_player() -> "FlowPlayer":
    """Get the FlowPlayer instance from app context"""
    return current_app.config.get("player")


def api_response(success: bool, data: dict = None, error: str = None, status_code: int = 200):
    """Create a standardized API response"""
    response = {"success": success}
    if data:
        response.update(data)
    if error:
        response["error"] = error
    return jsonify(response), status_code


def require_player(f):
    """Decorator to ensure player is available"""
    @wraps(f)
    def decorated(*args, **kwargs):
        player = get_player()
        if not player:
            return api_response(False, error="Player not initialized", status_code=503)
        return f(*args, **kwargs)
    return decorated


def create_api_blueprint() -> Blueprint:
    """Create the API blueprint"""
    api = Blueprint('api', __name__, url_prefix='/api')

    # ==================== STATUS ====================

    @api.route('/status', methods=['GET'])
    @require_player
    def get_status():
        """Get complete player status"""
        player = get_player()
        return jsonify(player.get_status())

    # ==================== CONTROL ====================

    @api.route('/control/play', methods=['POST'])
    @require_player
    def control_play():
        """Start playback"""
        player = get_player()
        loop = request.json.get('loop', True) if request.is_json else True

        try:
            player.play(loop=loop)
            return api_response(True, {"state": "playing"})
        except Exception as e:
            logger.error(f"Play error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/control/stop', methods=['POST'])
    @require_player
    def control_stop():
        """Stop playback"""
        player = get_player()

        try:
            player.stop()
            return api_response(True, {"state": "stopped"})
        except Exception as e:
            logger.error(f"Stop error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/control/pause', methods=['POST'])
    @require_player
    def control_pause():
        """Pause playback"""
        player = get_player()

        try:
            player.pause()
            return api_response(True, {"state": "paused"})
        except Exception as e:
            logger.error(f"Pause error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/control/resume', methods=['POST'])
    @require_player
    def control_resume():
        """Resume playback"""
        player = get_player()

        try:
            player.resume()
            return api_response(True, {"state": "playing"})
        except Exception as e:
            logger.error(f"Resume error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/control/restart', methods=['POST'])
    @require_player
    def control_restart():
        """Restart current show"""
        player = get_player()

        try:
            player.restart()
            return api_response(True, {"state": "playing"})
        except Exception as e:
            logger.error(f"Restart error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/control/seek', methods=['POST'])
    @require_player
    def control_seek():
        """Seek to position"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        position_ms = request.json.get('position_ms', 0)

        try:
            player.seek(position_ms)
            return api_response(True, {"position_ms": position_ms})
        except Exception as e:
            logger.error(f"Seek error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== SHOWS ====================

    @api.route('/shows', methods=['GET'])
    @require_player
    def get_shows():
        """List all available shows"""
        player = get_player()

        try:
            shows = player.list_shows()
            active_show = player.get_active_show_id()
            return jsonify({
                "shows": shows,
                "active_show": active_show
            })
        except Exception as e:
            logger.error(f"List shows error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/shows/upload', methods=['POST'])
    @require_player
    def upload_show():
        """Upload a new show package"""
        player = get_player()

        if 'file' not in request.files:
            return api_response(False, error="No file provided", status_code=400)

        file = request.files['file']
        if file.filename == '':
            return api_response(False, error="No file selected", status_code=400)

        if not file.filename.endswith('.zip'):
            return api_response(False, error="File must be a .zip", status_code=400)

        try:
            # Save uploaded file temporarily
            temp_path = Path(f"/tmp/{file.filename}")
            file.save(temp_path)

            # Import the show
            show_id = player.import_show(temp_path)

            # Clean up temp file
            temp_path.unlink()

            return api_response(True, {"show_id": show_id})
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/shows/<show_id>/activate', methods=['POST'])
    @require_player
    def activate_show(show_id):
        """Activate a show"""
        player = get_player()

        try:
            player.load_show(show_id)
            return api_response(True, {"active_show": show_id})
        except Exception as e:
            logger.error(f"Activate show error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/shows/<show_id>', methods=['DELETE'])
    @require_player
    def delete_show(show_id):
        """Delete a show"""
        player = get_player()

        try:
            success = player.delete_show(show_id)
            if success:
                return api_response(True)
            else:
                return api_response(False, error="Show not found", status_code=404)
        except Exception as e:
            logger.error(f"Delete show error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== SCENES ====================

    @api.route('/scenes', methods=['GET'])
    @require_player
    def get_scenes():
        """Get all scenes from current project"""
        player = get_player()

        try:
            scenes = player.get_scenes()
            current_scene = player.current_scene
            project_info = player.get_project_info()
            return jsonify({
                "scenes": scenes,
                "current_scene_id": current_scene.id if current_scene else None,
                "project": project_info
            })
        except Exception as e:
            logger.error(f"Get scenes error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/project', methods=['GET'])
    @require_player
    def get_project():
        """Get current project info"""
        player = get_player()

        try:
            return jsonify(player.get_project_info())
        except Exception as e:
            logger.error(f"Get project error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/scenes/<scene_id>/play', methods=['POST'])
    @require_player
    def play_scene(scene_id):
        """Play a specific scene"""
        player = get_player()

        loop = request.json.get('loop', True) if request.is_json else True

        try:
            success = player.play_scene(scene_id, loop=loop)
            if success:
                return api_response(True, {"scene_id": scene_id, "state": "playing"})
            else:
                return api_response(False, error="Scene not found", status_code=404)
        except Exception as e:
            logger.error(f"Play scene error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/scenes/<scene_id>/video', methods=['GET'])
    @require_player
    def get_scene_video_info(scene_id):
        """Get video info for a scene"""
        player = get_player()

        try:
            if not player.current_project:
                return api_response(False, error="No project loaded", status_code=404)

            scene = player.current_project.get_scene(scene_id)
            if not scene:
                return api_response(False, error="Scene not found", status_code=404)

            # Get video media for this scene
            media_list = player.current_project.get_scene_media(scene)
            videos = [m for m in media_list if m['element_type'] == 'video']

            if not videos:
                return api_response(False, error="No video in scene", status_code=404)

            video = videos[0]
            return jsonify({
                "scene_id": scene_id,
                "media_id": video['media_id'],
                "file_name": video['file_path'].name if hasattr(video['file_path'], 'name') else str(video['file_path']),
                "video_url": f"/api/media/{video['media_id']}"
            })
        except Exception as e:
            logger.error(f"Get scene video error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== MEDIA ====================

    @api.route('/media/<path:media_id>', methods=['GET'])
    @require_player
    def serve_media(media_id):
        """Serve a media file by ID or path

        Handles both:
        - Media ID: e.g., "f4233c8c-e41e-4c9b-b2b7-3436d2c784de"
        - Direct path: e.g., "media/videos/xxx.mp4"
        """
        player = get_player()

        try:
            if not player.current_project:
                return api_response(False, error="No project loaded", status_code=404)

            file_path = None

            # Check if media_id is a path (contains / or starts with media)
            if '/' in media_id or media_id.startswith('media'):
                # Direct path - resolve from project base
                file_path = player.current_project.base_path / media_id
            else:
                # Media ID - look up in media list
                media = player.current_project.get_media(media_id)
                if media:
                    file_path = media.path

            if not file_path:
                return api_response(False, error="Media not found", status_code=404)

            if not file_path.exists():
                logger.error(f"Media file not found: {file_path}")
                return api_response(False, error=f"Media file not found: {file_path}", status_code=404)

            # Determine mime type
            mime_types = {
                '.mp4': 'video/mp4',
                '.webm': 'video/webm',
                '.mov': 'video/quicktime',
                '.avi': 'video/x-msvideo',
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.ogg': 'audio/ogg',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
            }
            ext = file_path.suffix.lower()
            mime_type = mime_types.get(ext, 'application/octet-stream')

            return send_file(file_path, mimetype=mime_type)
        except Exception as e:
            logger.error(f"Serve media error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== SCHEDULE ====================

    @api.route('/schedule', methods=['GET'])
    @require_player
    def get_schedule():
        """Get current schedule"""
        player = get_player()

        try:
            schedule = player.get_schedule()
            return jsonify(schedule.to_dict())
        except Exception as e:
            logger.error(f"Get schedule error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/schedule', methods=['PUT'])
    @require_player
    def update_schedule():
        """Update schedule configuration"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        try:
            from ..core.scheduler import Schedule
            schedule = Schedule.from_dict(request.json)
            player.set_schedule(schedule)
            return api_response(True)
        except Exception as e:
            logger.error(f"Update schedule error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/schedule/mode', methods=['PUT'])
    @require_player
    def set_schedule_mode():
        """Set schedule mode"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        mode = request.json.get('mode')
        if not mode:
            return api_response(False, error="Mode required", status_code=400)

        try:
            from ..core.scheduler import ScheduleMode
            player.scheduler.set_mode(ScheduleMode(mode))
            return api_response(True, {"mode": mode})
        except Exception as e:
            logger.error(f"Set schedule mode error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== CONFIG ====================

    @api.route('/config', methods=['GET'])
    @require_player
    def get_config():
        """Get current configuration"""
        player = get_player()
        return jsonify(player.config.to_dict())

    @api.route('/config', methods=['PUT'])
    @require_player
    def update_config():
        """Update configuration"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        try:
            player.update_config(request.json)
            return api_response(True)
        except Exception as e:
            logger.error(f"Update config error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== SYSTEM ====================

    @api.route('/system/info', methods=['GET'])
    @require_player
    def get_system_info():
        """Get system information"""
        from ..core.utils import get_system_info, get_device_id, get_hostname, get_ip_address, get_mac_address

        hostname = get_hostname()
        ip = get_ip_address()

        return jsonify({
            "device_id": get_device_id(),
            "hostname": hostname,
            "hostname_local": f"{hostname}.local" if hostname else None,
            "ip": ip,
            "mac": get_mac_address(),
            "access_urls": [
                f"http://{ip}:5000" if ip else None,
                f"http://{hostname}.local:5000" if hostname else None,
            ],
            **get_system_info()
        })

    @api.route('/system/reboot', methods=['POST'])
    @require_player
    def system_reboot():
        """Reboot the system"""
        try:
            os.system('sudo reboot')
            return api_response(True, {"message": "Rebooting..."})
        except Exception as e:
            return api_response(False, error=str(e), status_code=500)

    @api.route('/system/shutdown', methods=['POST'])
    @require_player
    def system_shutdown():
        """Shutdown the system"""
        try:
            os.system('sudo shutdown -h now')
            return api_response(True, {"message": "Shutting down..."})
        except Exception as e:
            return api_response(False, error=str(e), status_code=500)

    @api.route('/logs', methods=['GET'])
    def get_logs():
        """Get recent logs"""
        lines = request.args.get('lines', 100, type=int)
        level = request.args.get('level', 'all')

        try:
            # Try multiple log file locations
            log_locations = [
                Path(__file__).parent.parent.parent / "logs" / "flow-player.log",
                Path("/opt/flow-player/logs/flow-player.log"),
                Path.home() / ".flow-player" / "logs" / "flow-player.log",
            ]

            log_file = None
            for loc in log_locations:
                if loc.exists():
                    log_file = loc
                    break

            if not log_file or not log_file.exists():
                # Return in-memory logs from logging handler if no file
                return jsonify({
                    "logs": ["Logs disponibles uniquement dans la console en mode développement.",
                             "Consultez le terminal où run_dev.py est lancé."],
                    "source": "memory"
                })

            with open(log_file, 'r') as f:
                all_lines = f.readlines()

            # Filter by level if specified
            if level != 'all':
                level_upper = level.upper()
                all_lines = [l for l in all_lines if level_upper in l]

            # Get last N lines
            recent_lines = all_lines[-lines:]

            return jsonify({"logs": recent_lines, "source": str(log_file)})
        except Exception as e:
            logger.error(f"Get logs error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== DMX ====================

    @api.route('/dmx/status', methods=['GET'])
    @require_player
    def get_dmx_status():
        """Get DMX status"""
        player = get_player()

        try:
            dmx_player = player.dmx_player
            if dmx_player:
                return jsonify({
                    "connected": dmx_player.is_connected(),
                    "playing": dmx_player.is_playing(),
                    "position": dmx_player.get_position(),
                    "mode": player.config.dmx.mode,
                    "universe": player.config.dmx.universe,
                })
            return jsonify({"connected": False})
        except Exception as e:
            logger.error(f"Get DMX status error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx/blackout', methods=['POST'])
    @require_player
    def dmx_blackout():
        """Send DMX blackout"""
        player = get_player()

        try:
            if player.dmx_player:
                player.dmx_player.blackout()
            return api_response(True)
        except Exception as e:
            logger.error(f"DMX blackout error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx/test', methods=['POST'])
    @require_player
    def dmx_test():
        """Test DMX output"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        channel = request.json.get('channel', 1)
        value = request.json.get('value', 255)

        try:
            if player.dmx_player:
                player.dmx_player.set_channel(channel, value)
            return api_response(True, {"channel": channel, "value": value})
        except Exception as e:
            logger.error(f"DMX test error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== VIDEO MAPPING ====================

    @api.route('/mapping', methods=['GET'])
    @require_player
    def get_mapping():
        """Get current video mapping configuration and status"""
        player = get_player()

        try:
            result = {
                "enabled": False,
                "mode": None,
                "is_deformed": False,
                "using_shader": False,
                "project_mapping": None,
                "scene_mapping": None,
            }

            # Get project-level mapping info
            if player.current_project:
                project_info = player.get_project_info()
                result["project_mapping"] = project_info.get("video_mapping")
                result["all_mappings"] = project_info.get("video_mappings", [])

            # Get current scene mapping
            if player.current_scene and player.current_project:
                scene_mapping = player.current_project.get_scene_mapping(player.current_scene.id)
                if scene_mapping:
                    result["scene_mapping"] = scene_mapping.to_dict()
                    result["enabled"] = scene_mapping.enabled
                    result["mode"] = scene_mapping.mode
                    result["is_deformed"] = scene_mapping.is_deformed()

            # Get video player mapping status
            if player.video_player:
                mapping_info = player.video_player.get_mapping_info()
                result.update({
                    "player_enabled": mapping_info.get("enabled", False),
                    "using_shader": mapping_info.get("using_shader", False),
                })

            return jsonify(result)
        except Exception as e:
            logger.error(f"Get mapping error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/scenes/<scene_id>/mapping', methods=['GET'])
    @require_player
    def get_scene_mapping(scene_id):
        """Get video mapping configuration for a specific scene"""
        player = get_player()

        try:
            if not player.current_project:
                return api_response(False, error="No project loaded", status_code=404)

            scene = player.current_project.get_scene(scene_id)
            if not scene:
                return api_response(False, error="Scene not found", status_code=404)

            # Get mapping for this scene
            mapping = player.current_project.get_scene_mapping(scene_id)

            if mapping:
                return jsonify({
                    "scene_id": scene_id,
                    "mapping": mapping.to_dict()
                })
            else:
                return jsonify({
                    "scene_id": scene_id,
                    "mapping": None
                })
        except Exception as e:
            logger.error(f"Get scene mapping error: {e}")
            return api_response(False, error=str(e), status_code=500)

    return api
