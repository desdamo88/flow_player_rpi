"""Flask application for Flow Player web interface"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS

from .api import create_api_blueprint

if TYPE_CHECKING:
    from ..flow_player import FlowPlayer

logger = logging.getLogger(__name__)


def create_app(player: "FlowPlayer" = None) -> Flask:
    """Create and configure the Flask application

    Args:
        player: FlowPlayer instance to use

    Returns:
        Configured Flask app
    """
    # Determine template and static folders
    web_dir = Path(__file__).parent
    template_dir = web_dir / "templates"
    static_dir = web_dir / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir)
    )

    # Enable CORS for API access
    CORS(app)

    # Store player reference
    app.config["player"] = player

    # Register API blueprint
    api_bp = create_api_blueprint()
    app.register_blueprint(api_bp)

    # ==================== WEB ROUTES ====================

    @app.route('/')
    def dashboard():
        """Dashboard page"""
        return render_template('dashboard.html')

    @app.route('/shows')
    def shows():
        """Shows management page"""
        return render_template('shows.html')

    @app.route('/schedule')
    def schedule():
        """Schedule configuration page"""
        return render_template('schedule.html')

    @app.route('/settings')
    def settings():
        """Settings page"""
        return render_template('settings.html')

    @app.route('/logs')
    def logs():
        """Logs page"""
        return render_template('logs.html')

    @app.route('/dmx-recorder')
    def dmx_recorder():
        """DMX Recorder page"""
        return render_template('dmx_recorder.html')

    # Serve media thumbnails
    @app.route('/thumbnails/<path:filename>')
    def serve_thumbnail(filename):
        """Serve thumbnail images"""
        if player and player.current_project:
            thumb_dir = player.current_project.base_path / "thumbnails"
            return send_from_directory(str(thumb_dir), filename)
        return "", 404

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        if '/api/' in str(e):
            return {"success": False, "error": "Not found"}, 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        if '/api/' in str(e):
            return {"success": False, "error": "Internal server error"}, 500
        return render_template('500.html'), 500

    return app
