#!/usr/bin/env python3
"""
Flow Player - Development runner for Ubuntu

Use this script to run Flow Player in development mode on a non-Raspberry Pi system.
- Video playback works with MPV (install: sudo apt install mpv)
- DMX output is disabled (no hardware)
- Web interface is fully functional

Usage:
    python run_dev.py              # Normal mode
    python run_dev.py --web-only   # Web interface only, no player
    python run_dev.py --import-zip # Import zip from datas/ folder
"""

import os
import sys
import argparse
import zipfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set development environment
os.environ.setdefault('FLOW_PLAYER_DEV', '1')

# Override paths for development
os.environ.setdefault('FLOW_PLAYER_BASE_PATH', str(project_root))
os.environ.setdefault('FLOW_PLAYER_SHOWS_PATH', str(project_root / 'shows'))
os.environ.setdefault('FLOW_PLAYER_CONFIG_PATH', str(project_root / 'config'))
os.environ.setdefault('FLOW_PLAYER_LOGS_PATH', str(project_root / 'logs'))

import logging


def setup_logging(log_level: str = "INFO"):
    """Setup logging for development with file output

    Args:
        log_level: DEBUG, INFO, WARNING, ERROR (default INFO for dev)
    """
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'flow-player.log'

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Setup root logger
    logging.basicConfig(
        level=level,
        handlers=[console_handler, file_handler]
    )

    # Reduce noise from libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return logging.getLogger(__name__)


def import_zip_shows(logger):
    """Import any zip files from datas/ folder to shows/"""
    datas_path = project_root / 'datas'
    shows_path = project_root / 'shows'

    if not datas_path.exists():
        logger.info("No datas/ folder found")
        return

    shows_path.mkdir(exist_ok=True)

    zip_files = list(datas_path.glob('*.zip'))
    if not zip_files:
        logger.info("No zip files found in datas/")
        return

    for zip_path in zip_files:
        folder_name = zip_path.stem
        extract_path = shows_path / folder_name

        # Skip if already extracted
        if extract_path.exists() and (extract_path / 'project.json').exists():
            logger.info(f"Show already exists: {folder_name}")
            continue

        # Remove incomplete extraction
        if extract_path.exists():
            shutil.rmtree(extract_path)

        logger.info(f"Extracting {zip_path.name} to shows/{folder_name}")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_path)

            # Verify project.json exists
            if (extract_path / 'project.json').exists():
                logger.info(f"Successfully imported: {folder_name}")
            else:
                logger.warning(f"No project.json found in {folder_name}")
        except Exception as e:
            logger.error(f"Failed to extract {zip_path.name}: {e}")


def check_mpv():
    """Check if MPV is available"""
    try:
        import mpv
        return True
    except ImportError:
        return False


def main():
    parser = argparse.ArgumentParser(description='Flow Player Development Runner')
    parser.add_argument('--web-only', action='store_true',
                        help='Run web interface only, no player initialization')
    parser.add_argument('--import-zip', action='store_true',
                        help='Import zip files from datas/ folder')
    parser.add_argument('--port', type=int, default=5000,
                        help='Web server port (default: 5000)')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='Web server host (default: 127.0.0.1)')
    parser.add_argument('--no-reload', action='store_true',
                        help='Disable auto-reload (useful for debugging)')
    parser.add_argument('--log-level', '-l', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Log level (default: INFO for dev)')
    args = parser.parse_args()

    logger = setup_logging(args.log_level)

    logger.info("=" * 60)
    logger.info("Flow Player - Development Mode (Ubuntu)")
    logger.info("=" * 60)

    # Import from local modules after logging is set up
    from src.core.config import Config
    from src.flow_player import FlowPlayer
    from src.web.app import create_app

    # Create directories
    (project_root / 'shows').mkdir(exist_ok=True)
    (project_root / 'config').mkdir(exist_ok=True)
    (project_root / 'logs').mkdir(exist_ok=True)

    # Always import zip files from datas/
    import_zip_shows(logger)

    # Check MPV availability
    mpv_available = check_mpv()
    if mpv_available:
        logger.info("MPV is available - video playback will work")
    else:
        logger.warning("MPV not available - install with: pip install python-mpv")
        logger.warning("Also install mpv: sudo apt install mpv libmpv-dev")

    # Create config directory
    config_path = project_root / 'config'
    config_path.mkdir(exist_ok=True)

    # Load existing config or create new one
    config_file = config_path / 'config.json'
    if config_file.exists():
        logger.info(f"Loading existing config from {config_file}")
        config = Config.load(config_file)
    else:
        logger.info("Creating new config")
        config = Config()

    # Override paths for development
    config.base_path = project_root
    config.shows_path = project_root / 'shows'
    config.config_path = config_path
    config.logs_path = project_root / 'logs'
    config._config_file = config_file
    config._state_file = config_path / 'state.json'

    # Disable DMX in dev mode (no hardware)
    config.dmx.enabled = False
    logger.info("DMX output disabled (development mode)")

    # Disable heartbeat monitoring
    config.monitoring.heartbeat_enabled = False

    # Save config to ensure it exists
    config.save()
    logger.info(f"Config saved to {config_file}")

    # Player initialization
    player = None

    if not args.web_only:
        try:
            logger.info("Initializing Flow Player...")
            player = FlowPlayer(config)
            player.initialize()
            logger.info("Flow Player initialized successfully")

            # List available shows
            shows = player.list_shows()
            if shows:
                logger.info(f"Available shows: {len(shows)}")
                for show in shows:
                    logger.info(f"  - {show.get('name', 'Unknown')} ({show.get('id', '?')})")
            else:
                logger.warning("No shows found in shows/ folder")
                logger.info("Place Flow Studio exports (.zip) in the datas/ folder")

        except Exception as e:
            logger.warning(f"Could not initialize full player: {e}")
            logger.info("Running in web-only mode for interface testing")
    else:
        logger.info("Running in web-only mode (--web-only flag)")

    # Create and run Flask app
    app = create_app(player)

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"Web interface: http://{args.host}:{args.port}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Tips:")
    logger.info("  - Place Flow Studio exports (.zip) in datas/ folder")
    logger.info("  - Use Ctrl+C to stop the server")
    logger.info("  - Access /api/status for player status JSON")
    logger.info("")

    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=True,
            use_reloader=not args.no_reload
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if player:
            player.shutdown()
        logger.info("Flow Player stopped")


if __name__ == '__main__':
    main()
