"""REST API endpoints for Flow Player"""

import os
import sys
import platform
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from functools import wraps

from flask import Blueprint, jsonify, request, current_app, send_file

if TYPE_CHECKING:
    from ..flow_player import FlowPlayer

logger = logging.getLogger(__name__)

# Track startup time for uptime calculation
_startup_time = time.time()
API_VERSION = "1.1.0"
APP_VERSION = "0.9.0"


def _format_time_until(ms: int) -> str:
    """Format milliseconds as human-readable time until"""
    seconds = ms // 1000
    minutes = seconds // 60
    hours = minutes // 60

    if hours > 0:
        return f"{hours}h {minutes % 60}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{seconds}s"


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


def require_api_key(f):
    """Decorator to require API key authentication via X-API-Key header"""
    @wraps(f)
    def decorated(*args, **kwargs):
        player = get_player()
        if not player:
            return api_response(False, error="Player not initialized", status_code=503)

        # Check if API key auth is required
        config_key = player.config.monitoring.api_key if player.config else ""

        if config_key:
            # API key is configured, require it
            provided_key = request.headers.get('X-API-Key', '')

            if not provided_key:
                return jsonify({
                    "error": "API key required",
                    "code": "API_KEY_REQUIRED",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }), 401

            if provided_key != config_key:
                return jsonify({
                    "error": "Invalid API key",
                    "code": "INVALID_API_KEY",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }), 401

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

    # ==================== MONITORING ====================

    @api.route('/health', methods=['GET'])
    def get_health():
        """Health check endpoint (no auth required)

        Returns application status, uptime, and version info.
        """
        player = get_player()
        uptime = int(time.time() - _startup_time)

        status = "running"
        if not player:
            status = "error"
        elif player.video_player and player.video_player.is_playing():
            status = "playing"
        elif player.current_project is None:
            status = "idle"

        return jsonify({
            "status": status,
            "uptime": uptime,
            "version": APP_VERSION,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "apiVersion": API_VERSION
        })

    @api.route('/displays', methods=['GET'])
    @require_api_key
    @require_player
    def get_displays():
        """Get all displays/outputs and their status"""
        player = get_player()

        try:
            displays = []

            # Get display info from current scene/project
            current_scene = player.current_scene
            project_info = player.get_project_info() if player.current_project else None

            # Create main display entry (RPi typically has one output)
            display = {
                "id": "display-main",
                "screenId": "1",
                "name": "Écran Principal",
                "enabled": True,
                "resolution": {
                    "width": project_info.get("canvas_width", 1920) if project_info else 1920,
                    "height": project_info.get("canvas_height", 1080) if project_info else 1080
                },
                "position": {"x": 0, "y": 0},
                "currentScene": None,
                "windowStatus": "open" if player.video_player else "closed",
                "lastUpdate": datetime.utcnow().isoformat() + "Z"
            }

            # Add current scene info if playing
            if current_scene:
                elapsed = 0
                duration = None

                if player.video_player:
                    elapsed = int(player.video_player.get_position() * 1000)
                    duration = player.video_player.get_duration()
                    if duration:
                        duration = int(duration * 1000)

                display["currentScene"] = {
                    "id": current_scene.id,
                    "name": current_scene.name,
                    "startedAt": datetime.utcnow().isoformat() + "Z",
                    "duration": duration,
                    "elapsedTime": elapsed
                }

            displays.append(display)

            return jsonify({
                "displays": displays,
                "total": len(displays),
                "activeCount": 1 if current_scene else 0
            })
        except Exception as e:
            logger.error(f"Get displays error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/displays/<display_id>', methods=['GET'])
    @require_api_key
    @require_player
    def get_display_detail(display_id):
        """Get detailed info for a specific display"""
        player = get_player()

        try:
            if display_id != "display-main":
                return api_response(False, error="Display not found", status_code=404)

            current_scene = player.current_scene
            project_info = player.get_project_info() if player.current_project else None

            display = {
                "id": "display-main",
                "screenId": "1",
                "name": "Écran Principal",
                "enabled": True,
                "resolution": {
                    "width": project_info.get("canvas_width", 1920) if project_info else 1920,
                    "height": project_info.get("canvas_height", 1080) if project_info else 1080
                },
                "position": {"x": 0, "y": 0},
                "currentScene": None,
                "windowStatus": "open" if player.video_player else "closed",
                "lastUpdate": datetime.utcnow().isoformat() + "Z"
            }

            # Add current scene with elements
            if current_scene:
                elapsed = 0
                duration = None

                if player.video_player:
                    elapsed = int(player.video_player.get_position() * 1000)
                    duration = player.video_player.get_duration()
                    if duration:
                        duration = int(duration * 1000)

                elements = []
                if player.current_project:
                    scene_data = player.current_project.get_scene(current_scene.id)
                    if scene_data and hasattr(scene_data, 'elements'):
                        for elem in scene_data.elements:
                            elements.append({
                                "id": elem.id,
                                "type": elem.type,
                                "name": elem.name,
                                "visible": elem.visible,
                                "position": {"x": elem.x, "y": elem.y},
                                "size": {"width": elem.width, "height": elem.height}
                            })

                display["currentScene"] = {
                    "id": current_scene.id,
                    "name": current_scene.name,
                    "startedAt": datetime.utcnow().isoformat() + "Z",
                    "duration": duration,
                    "elapsedTime": elapsed,
                    "elements": elements
                }

            return jsonify(display)
        except Exception as e:
            logger.error(f"Get display detail error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/displays/<display_id>/scene', methods=['GET'])
    @require_api_key
    @require_player
    def get_display_scene(display_id):
        """Get current scene for a display"""
        player = get_player()

        try:
            if display_id != "display-main":
                return api_response(False, error="Display not found", status_code=404)

            current_scene = player.current_scene

            result = {
                "displayId": "display-main",
                "displayName": "Écran Principal",
                "scene": None
            }

            if current_scene:
                elapsed = 0
                duration = None
                progress = 0

                if player.video_player:
                    elapsed = int(player.video_player.get_position() * 1000)
                    duration = player.video_player.get_duration()
                    if duration:
                        duration_ms = int(duration * 1000)
                        progress = (elapsed / duration_ms * 100) if duration_ms > 0 else 0
                        duration = duration_ms

                # Count elements
                elements_count = 0
                if player.current_project:
                    scene_data = player.current_project.get_scene(current_scene.id)
                    if scene_data and hasattr(scene_data, 'elements'):
                        elements_count = len(scene_data.elements)

                result["scene"] = {
                    "id": current_scene.id,
                    "name": current_scene.name,
                    "startedAt": datetime.utcnow().isoformat() + "Z",
                    "duration": duration,
                    "elapsedTime": elapsed,
                    "elementsCount": elements_count,
                    "progress": round(progress, 2)
                }

            return jsonify(result)
        except Exception as e:
            logger.error(f"Get display scene error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/schedules', methods=['GET'])
    @require_api_key
    @require_player
    def get_schedules():
        """Get all scheduled events (monitoring API format)"""
        player = get_player()

        try:
            enabled_only = request.args.get('enabled', type=lambda x: x.lower() == 'true')
            today_only = request.args.get('today', type=lambda x: x.lower() == 'true')

            schedules = []

            # Get schedule from player if available
            if hasattr(player, 'scheduler') and player.scheduler:
                schedule = player.get_schedule()

                if schedule and hasattr(schedule, 'entries'):
                    from datetime import timedelta
                    now = datetime.now()
                    day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

                    for entry in schedule.entries:
                        if hasattr(entry, 'scene_id'):
                            # Find scene name
                            scene_name = entry.scene_id
                            if player.current_project:
                                scene = player.current_project.get_scene(entry.scene_id)
                                if scene:
                                    scene_name = scene.name

                            # Calculate next execution
                            exec_time = now.replace(
                                hour=entry.hour if hasattr(entry, 'hour') else 0,
                                minute=entry.minute if hasattr(entry, 'minute') else 0,
                                second=0, microsecond=0
                            )
                            if exec_time < now:
                                exec_time += timedelta(days=1)

                            days = getattr(entry, 'days', [1, 2, 3, 4, 5, 6, 7])
                            days_text = [day_names[d-1] for d in days if 1 <= d <= 7]

                            schedule_entry = {
                                "id": entry.id if hasattr(entry, 'id') else f"schedule-{len(schedules)}",
                                "name": getattr(entry, 'name', f"Schedule {len(schedules)+1}"),
                                "groupId": "group-main",
                                "groupName": "Écran Principal",
                                "sceneId": entry.scene_id,
                                "sceneName": scene_name,
                                "time": f"{getattr(entry, 'hour', 0):02d}:{getattr(entry, 'minute', 0):02d}",
                                "days": days,
                                "daysText": days_text if days_text else ["Tous les jours"],
                                "enabled": getattr(entry, 'enabled', True),
                                "nextExecution": exec_time.isoformat() + "Z",
                                "lastExecution": None
                            }

                            # Apply filters
                            if enabled_only is not None and not schedule_entry["enabled"]:
                                continue

                            schedules.append(schedule_entry)

            enabled_count = sum(1 for s in schedules if s.get("enabled", True))

            return jsonify({
                "schedules": schedules,
                "total": len(schedules),
                "enabledCount": enabled_count
            })
        except Exception as e:
            logger.error(f"Get schedules error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/schedules/upcoming', methods=['GET'])
    @require_api_key
    @require_player
    def get_schedules_upcoming():
        """Get upcoming scheduled events"""
        player = get_player()

        try:
            limit = request.args.get('limit', 10, type=int)
            hours = request.args.get('hours', 24, type=int)

            upcoming = []

            # Get schedule from player if available
            if hasattr(player, 'scheduler') and player.scheduler:
                schedule = player.get_schedule()

                # Get upcoming entries from schedule
                if schedule and hasattr(schedule, 'entries'):
                    from datetime import timedelta
                    now = datetime.now()
                    window_end = now + timedelta(hours=hours)

                    for entry in schedule.entries[:limit]:
                        if hasattr(entry, 'scene_id'):
                            # Find scene name
                            scene_name = entry.scene_id
                            if player.current_project:
                                scene = player.current_project.get_scene(entry.scene_id)
                                if scene:
                                    scene_name = scene.name

                            # Calculate next execution time
                            exec_time = now.replace(
                                hour=entry.hour if hasattr(entry, 'hour') else 0,
                                minute=entry.minute if hasattr(entry, 'minute') else 0,
                                second=0, microsecond=0
                            )
                            if exec_time < now:
                                exec_time += timedelta(days=1)

                            time_until = int((exec_time - now).total_seconds() * 1000)
                            time_until_text = _format_time_until(time_until)

                            upcoming.append({
                                "scheduleId": entry.id if hasattr(entry, 'id') else f"schedule-{len(upcoming)}",
                                "scheduleName": getattr(entry, 'name', f"Schedule {len(upcoming)+1}"),
                                "executionTime": exec_time.isoformat() + "Z",
                                "timeUntil": time_until,
                                "timeUntilText": time_until_text,
                                "sceneId": entry.scene_id,
                                "sceneName": scene_name,
                                "groupId": "group-main",
                                "groupName": "Écran Principal",
                                "day": exec_time.strftime("%A")
                            })

            return jsonify({
                "upcoming": upcoming[:limit],
                "total": len(upcoming),
                "windowHours": hours
            })
        except Exception as e:
            logger.error(f"Get upcoming schedules error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/sequences', methods=['GET'])
    @require_api_key
    @require_player
    def get_sequences():
        """Get all DMX sequences"""
        player = get_player()

        try:
            sequences = []

            # Get DMX sequences from current project
            if player.current_project and hasattr(player.current_project, 'dmx_sequences'):
                for seq in player.current_project.dmx_sequences:
                    sequences.append({
                        "id": seq.id if hasattr(seq, 'id') else str(len(sequences)),
                        "name": seq.name if hasattr(seq, 'name') else f"Sequence {len(sequences)+1}",
                        "duration": seq.duration if hasattr(seq, 'duration') else 0,
                        "stepsCount": len(seq.steps) if hasattr(seq, 'steps') else 0,
                        "loop": seq.loop if hasattr(seq, 'loop') else False,
                        "enabled": True,
                        "fixtures": []
                    })

            return jsonify({
                "sequences": sequences,
                "total": len(sequences)
            })
        except Exception as e:
            logger.error(f"Get sequences error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/sequences/running', methods=['GET'])
    @require_api_key
    @require_player
    def get_sequences_running():
        """Get currently running DMX sequences"""
        player = get_player()

        try:
            running = []

            # Check if DMX player is running a sequence
            if player.dmx_player and player.dmx_player.is_playing():
                current_seq = getattr(player.dmx_player, 'current_sequence', None)
                if current_seq:
                    position = player.dmx_player.get_position()
                    duration = getattr(current_seq, 'duration', 0)
                    progress = (position / duration * 100) if duration > 0 else 0

                    running.append({
                        "sequenceId": getattr(current_seq, 'id', 'seq-current'),
                        "sequenceName": getattr(current_seq, 'name', 'Current Sequence'),
                        "startedAt": datetime.utcnow().isoformat() + "Z",
                        "duration": int(duration * 1000),
                        "elapsedTime": int(position * 1000),
                        "progress": round(progress, 2),
                        "currentStep": getattr(player.dmx_player, 'current_step', 0),
                        "totalSteps": len(current_seq.steps) if hasattr(current_seq, 'steps') else 0,
                        "loop": getattr(current_seq, 'loop', False),
                        "loopCount": getattr(player.dmx_player, 'loop_count', 0)
                    })

            return jsonify({
                "running": running,
                "total": len(running)
            })
        except Exception as e:
            logger.error(f"Get running sequences error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/stats', methods=['GET'])
    @require_api_key
    @require_player
    def get_stats():
        """Get system statistics"""
        player = get_player()

        try:
            import psutil

            # Process info
            process = psutil.Process()
            memory = process.memory_info()
            cpu_times = process.cpu_times()

            # Count active elements
            active_displays = 1 if player.current_scene else 0
            active_scenes = 1 if player.current_scene else 0
            running_sequences = 1 if (player.dmx_player and player.dmx_player.is_playing()) else 0

            return jsonify({
                "system": {
                    "platform": sys.platform,
                    "arch": platform.machine(),
                    "pythonVersion": platform.python_version(),
                    "hostname": platform.node()
                },
                "process": {
                    "uptime": int(time.time() - _startup_time),
                    "memoryUsage": {
                        "rss": memory.rss,
                        "vms": memory.vms,
                        "percent": process.memory_percent()
                    },
                    "cpu": {
                        "user": cpu_times.user,
                        "system": cpu_times.system,
                        "percent": process.cpu_percent()
                    }
                },
                "application": {
                    "projectOpened": player.current_project is not None,
                    "activeDisplays": active_displays,
                    "activeScenes": active_scenes,
                    "runningSequences": running_sequences,
                    "runningEffects": 0
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
        except ImportError:
            # psutil not available - return basic stats
            return jsonify({
                "system": {
                    "platform": sys.platform,
                    "arch": platform.machine(),
                    "pythonVersion": platform.python_version(),
                    "hostname": platform.node()
                },
                "process": {
                    "uptime": int(time.time() - _startup_time)
                },
                "application": {
                    "projectOpened": player.current_project is not None,
                    "activeDisplays": 1 if player.current_scene else 0,
                    "activeScenes": 1 if player.current_scene else 0,
                    "runningSequences": 0,
                    "runningEffects": 0
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return api_response(False, error=str(e), status_code=500)

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
    @require_api_key
    @require_player
    def get_project():
        """Get current project info (monitoring API)"""
        player = get_player()

        try:
            project_info = player.get_project_info()

            # Format response according to monitoring API spec
            if not project_info or not project_info.get("id"):
                return jsonify({
                    "error": "No project currently opened",
                    "code": "NO_PROJECT"
                }), 404

            # Get scenes count and elements count
            scenes_count = len(player.get_scenes()) if player.current_project else 0
            elements_count = 0
            media_count = 0

            if player.current_project:
                # scenes is a list, not a dict
                for scene in player.current_project.scenes:
                    if hasattr(scene, 'elements'):
                        elements_count += len(scene.elements)
                if hasattr(player.current_project, 'media'):
                    media_count = len(player.current_project.media)

            return jsonify({
                "id": project_info.get("id", ""),
                "name": project_info.get("name", "Unknown"),
                "path": str(player.current_project.base_path) if player.current_project else "",
                "createdAt": project_info.get("created_at", datetime.utcnow().isoformat() + "Z"),
                "lastModified": project_info.get("modified_at", datetime.utcnow().isoformat() + "Z"),
                "scenesCount": scenes_count,
                "elementsCount": elements_count,
                "mediaCount": media_count,
                "autoStart": {
                    "enabled": player.config.autoplay if player.config else False,
                    "displayMappingsCount": 1
                }
            })
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

    # ==================== DMX RECORDER ====================

    @api.route('/dmx-recorder/status', methods=['GET'])
    @require_player
    def dmx_recorder_status():
        """Get DMX recorder status"""
        player = get_player()

        try:
            if not hasattr(player, 'dmx_recorder') or not player.dmx_recorder:
                return jsonify({
                    "available": False,
                    "listening": False,
                    "recording": False
                })

            status = player.dmx_recorder.get_recording_status()
            status["available"] = True
            return jsonify(status)
        except Exception as e:
            logger.error(f"DMX recorder status error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/listen/start', methods=['POST'])
    @require_player
    def dmx_recorder_start_listening():
        """Start listening for Art-Net DMX packets"""
        player = get_player()

        try:
            # Initialize recorder if needed
            if not hasattr(player, 'dmx_recorder') or not player.dmx_recorder:
                from ..core.dmx_recorder import DMXRecorder
                recordings_path = player.config.shows_path / "_recordings"
                player.dmx_recorder = DMXRecorder(recordings_path)

            bind_ip = request.json.get('bind_ip', '0.0.0.0') if request.is_json else '0.0.0.0'
            port = request.json.get('port', 6454) if request.is_json else 6454

            success = player.dmx_recorder.start_listening(bind_ip, port)
            if success:
                return api_response(True, {"message": f"Listening on {bind_ip}:{port}"})
            else:
                return api_response(False, error="Failed to start listening", status_code=500)
        except Exception as e:
            logger.error(f"DMX recorder start listening error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/listen/stop', methods=['POST'])
    @require_player
    def dmx_recorder_stop_listening():
        """Stop listening for Art-Net DMX packets"""
        player = get_player()

        try:
            if hasattr(player, 'dmx_recorder') and player.dmx_recorder:
                player.dmx_recorder.stop_listening()
            return api_response(True, {"message": "Stopped listening"})
        except Exception as e:
            logger.error(f"DMX recorder stop listening error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/record/start', methods=['POST'])
    @require_player
    def dmx_recorder_start_recording():
        """Start recording DMX data"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        name = request.json.get('name', 'Untitled Recording')
        universe = request.json.get('universe', 0)

        try:
            if not hasattr(player, 'dmx_recorder') or not player.dmx_recorder:
                return api_response(False, error="Recorder not initialized. Start listening first.", status_code=400)

            success = player.dmx_recorder.start_recording(name, universe)
            if success:
                return api_response(True, {
                    "message": f"Recording '{name}' on universe {universe}",
                    "name": name,
                    "universe": universe
                })
            else:
                return api_response(False, error="Failed to start recording", status_code=500)
        except Exception as e:
            logger.error(f"DMX recorder start recording error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/record/stop', methods=['POST'])
    @require_player
    def dmx_recorder_stop_recording():
        """Stop recording and optionally save"""
        player = get_player()

        save = request.json.get('save', True) if request.is_json else True
        filename = request.json.get('filename') if request.is_json else None

        try:
            if not hasattr(player, 'dmx_recorder') or not player.dmx_recorder:
                return api_response(False, error="Recorder not initialized", status_code=400)

            recording = player.dmx_recorder.stop_recording()

            if not recording:
                return api_response(False, error="No active recording", status_code=400)

            result = {
                "name": recording.name,
                "duration_ms": recording.duration_ms,
                "frame_count": len(recording.frames),
                "saved": False
            }

            if save and len(recording.frames) > 0:
                if not filename:
                    # Generate filename from name
                    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in recording.name)
                    filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dmxr"

                recordings_path = player.config.shows_path / "_recordings"
                save_path = recordings_path / filename
                recording.save(save_path)
                result["saved"] = True
                result["file_path"] = str(save_path)

            return api_response(True, result)
        except Exception as e:
            logger.error(f"DMX recorder stop recording error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/recordings', methods=['GET'])
    @require_player
    def dmx_recorder_list_recordings():
        """List all saved DMX recordings"""
        player = get_player()

        try:
            if not hasattr(player, 'dmx_recorder') or not player.dmx_recorder:
                # Initialize recorder just to list files
                from ..core.dmx_recorder import DMXRecorder
                recordings_path = player.config.shows_path / "_recordings"
                recorder = DMXRecorder(recordings_path)
                recordings = recorder.list_recordings()
            else:
                recordings = player.dmx_recorder.list_recordings()

            return jsonify({
                "recordings": recordings,
                "total": len(recordings)
            })
        except Exception as e:
            logger.error(f"DMX recorder list recordings error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/recordings/<recording_name>', methods=['GET'])
    @require_player
    def dmx_recorder_get_recording(recording_name):
        """Get details of a specific recording"""
        player = get_player()

        try:
            from ..core.dmx_recorder import DMXRecording
            recordings_path = player.config.shows_path / "_recordings"
            path = recordings_path / f"{recording_name}.dmxr"

            if not path.exists():
                return api_response(False, error="Recording not found", status_code=404)

            recording = DMXRecording.load(path)
            if recording:
                return jsonify(recording.to_info_dict())
            else:
                return api_response(False, error="Failed to load recording", status_code=500)
        except Exception as e:
            logger.error(f"DMX recorder get recording error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/recordings/<recording_name>', methods=['DELETE'])
    @require_player
    def dmx_recorder_delete_recording(recording_name):
        """Delete a recording"""
        player = get_player()

        try:
            recordings_path = player.config.shows_path / "_recordings"
            path = recordings_path / f"{recording_name}.dmxr"

            if not path.exists():
                return api_response(False, error="Recording not found", status_code=404)

            path.unlink()
            return api_response(True, {"message": f"Recording '{recording_name}' deleted"})
        except Exception as e:
            logger.error(f"DMX recorder delete recording error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/recordings/<recording_name>/trim', methods=['POST'])
    @require_player
    def dmx_recorder_trim_recording(recording_name):
        """Trim a recording (set start/end points)"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        trim_start_ms = request.json.get('trim_start_ms')
        trim_end_ms = request.json.get('trim_end_ms')

        try:
            from ..core.dmx_recorder import DMXRecording
            recordings_path = player.config.shows_path / "_recordings"
            path = recordings_path / f"{recording_name}.dmxr"

            if not path.exists():
                return api_response(False, error="Recording not found", status_code=404)

            recording = DMXRecording.load(path)
            if not recording:
                return api_response(False, error="Failed to load recording", status_code=500)

            # Update trim points
            if trim_start_ms is not None:
                recording.trim_start_ms = max(0, min(trim_start_ms, recording.duration_ms))
            if trim_end_ms is not None:
                recording.trim_end_ms = max(recording.trim_start_ms, min(trim_end_ms, recording.duration_ms))

            # Save updated recording
            recording.save(path)

            return api_response(True, {
                "trim_start_ms": recording.trim_start_ms,
                "trim_end_ms": recording.trim_end_ms,
                "trimmed_duration_ms": recording.get_trimmed_duration()
            })
        except Exception as e:
            logger.error(f"DMX recorder trim error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/recordings/<recording_name>/play', methods=['POST'])
    @require_player
    def dmx_recorder_play_recording(recording_name):
        """Play a DMX recording"""
        player = get_player()

        loop = request.json.get('loop', False) if request.is_json else False

        try:
            from ..core.dmx_recorder import DMXRecording, DMXRecordingPlayer
            recordings_path = player.config.shows_path / "_recordings"
            path = recordings_path / f"{recording_name}.dmxr"

            if not path.exists():
                return api_response(False, error="Recording not found", status_code=404)

            recording = DMXRecording.load(path)
            if not recording:
                return api_response(False, error="Failed to load recording", status_code=500)

            # Create or get recording player
            if not hasattr(player, 'dmx_recording_player') or not player.dmx_recording_player:
                def output_dmx(channels):
                    if player.dmx_player:
                        player.dmx_player.send_frame(channels)

                player.dmx_recording_player = DMXRecordingPlayer(output_dmx)

            player.dmx_recording_player.load(recording)
            player.dmx_recording_player.play(loop=loop)

            return api_response(True, {
                "message": f"Playing '{recording.name}'",
                "duration_ms": recording.get_trimmed_duration(),
                "loop": loop
            })
        except Exception as e:
            logger.error(f"DMX recorder play error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-recorder/playback/stop', methods=['POST'])
    @require_player
    def dmx_recorder_stop_playback():
        """Stop DMX recording playback"""
        player = get_player()

        try:
            if hasattr(player, 'dmx_recording_player') and player.dmx_recording_player:
                player.dmx_recording_player.stop()
            return api_response(True, {"message": "Playback stopped"})
        except Exception as e:
            logger.error(f"DMX recorder stop playback error: {e}")
            return api_response(False, error=str(e), status_code=500)

    # ==================== DMX SCENE LINKS ====================

    @api.route('/dmx-links', methods=['GET'])
    @require_player
    def get_dmx_links():
        """Get all DMX scene-recording links"""
        player = get_player()

        try:
            # Initialize link manager if needed
            if not hasattr(player, 'dmx_link_manager') or not player.dmx_link_manager:
                from ..core.dmx_scene_link import DMXSceneLinkManager
                player.dmx_link_manager = DMXSceneLinkManager(player.config.config_path)

            links = player.dmx_link_manager.get_all_links()

            # Enrich with scene names
            for link in links:
                if player.current_project:
                    scene = player.current_project.get_scene(link['scene_id'])
                    link['scene_name'] = scene.name if scene else 'Unknown'
                else:
                    link['scene_name'] = 'Unknown'

            return jsonify({
                "links": links,
                "total": len(links),
                "modes": [
                    {"value": "project_only", "label": "Séquence projet uniquement"},
                    {"value": "recording_only", "label": "Enregistrement uniquement"},
                    {"value": "recording_priority", "label": "Enregistrement prioritaire"},
                    {"value": "blend", "label": "Fusion (HTP)"}
                ]
            })
        except Exception as e:
            logger.error(f"Get DMX links error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-links', methods=['POST'])
    @require_player
    def create_dmx_link():
        """Create a link between a scene and a DMX recording"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        scene_id = request.json.get('scene_id')
        recording_name = request.json.get('recording_name')
        mode = request.json.get('mode', 'recording_priority')
        offset_ms = request.json.get('offset_ms', 0)

        if not scene_id or not recording_name:
            return api_response(False, error="scene_id and recording_name required", status_code=400)

        try:
            # Initialize link manager if needed
            if not hasattr(player, 'dmx_link_manager') or not player.dmx_link_manager:
                from ..core.dmx_scene_link import DMXSceneLinkManager
                player.dmx_link_manager = DMXSceneLinkManager(player.config.config_path)

            # Verify recording exists
            recordings_path = player.config.shows_path / "_recordings"
            recording_path = recordings_path / f"{recording_name}.dmxr"
            if not recording_path.exists():
                return api_response(False, error=f"Recording '{recording_name}' not found", status_code=404)

            success = player.dmx_link_manager.link_scene(scene_id, recording_name, mode, offset_ms)

            if success:
                # Get scene name for response
                scene_name = scene_id
                if player.current_project:
                    scene = player.current_project.get_scene(scene_id)
                    if scene:
                        scene_name = scene.name

                return api_response(True, {
                    "message": f"Linked '{recording_name}' to scene '{scene_name}'",
                    "scene_id": scene_id,
                    "recording_name": recording_name,
                    "mode": mode
                })
            else:
                return api_response(False, error="Failed to create link", status_code=500)
        except Exception as e:
            logger.error(f"Create DMX link error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-links/<scene_id>', methods=['GET'])
    @require_player
    def get_dmx_link(scene_id):
        """Get the DMX link for a specific scene"""
        player = get_player()

        try:
            if not hasattr(player, 'dmx_link_manager') or not player.dmx_link_manager:
                from ..core.dmx_scene_link import DMXSceneLinkManager
                player.dmx_link_manager = DMXSceneLinkManager(player.config.config_path)

            link = player.dmx_link_manager.get_link(scene_id)

            if link:
                result = link.to_dict()
                if player.current_project:
                    scene = player.current_project.get_scene(scene_id)
                    result['scene_name'] = scene.name if scene else 'Unknown'
                return jsonify(result)
            else:
                return jsonify({"linked": False, "scene_id": scene_id})
        except Exception as e:
            logger.error(f"Get DMX link error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-links/<scene_id>', methods=['PUT'])
    @require_player
    def update_dmx_link(scene_id):
        """Update a DMX scene link"""
        player = get_player()

        if not request.is_json:
            return api_response(False, error="JSON body required", status_code=400)

        try:
            if not hasattr(player, 'dmx_link_manager') or not player.dmx_link_manager:
                from ..core.dmx_scene_link import DMXSceneLinkManager
                player.dmx_link_manager = DMXSceneLinkManager(player.config.config_path)

            # Update fields
            if 'mode' in request.json:
                player.dmx_link_manager.set_mode(scene_id, request.json['mode'])
            if 'enabled' in request.json:
                player.dmx_link_manager.set_enabled(scene_id, request.json['enabled'])
            if 'offset_ms' in request.json:
                player.dmx_link_manager.set_offset(scene_id, request.json['offset_ms'])

            return api_response(True, {"message": "Link updated"})
        except Exception as e:
            logger.error(f"Update DMX link error: {e}")
            return api_response(False, error=str(e), status_code=500)

    @api.route('/dmx-links/<scene_id>', methods=['DELETE'])
    @require_player
    def delete_dmx_link(scene_id):
        """Delete a DMX scene link"""
        player = get_player()

        try:
            if not hasattr(player, 'dmx_link_manager') or not player.dmx_link_manager:
                from ..core.dmx_scene_link import DMXSceneLinkManager
                player.dmx_link_manager = DMXSceneLinkManager(player.config.config_path)

            success = player.dmx_link_manager.unlink_scene(scene_id)

            if success:
                return api_response(True, {"message": "Link removed"})
            else:
                return api_response(False, error="Link not found", status_code=404)
        except Exception as e:
            logger.error(f"Delete DMX link error: {e}")
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
