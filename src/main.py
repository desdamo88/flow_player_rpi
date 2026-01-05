#!/usr/bin/env python3
"""Flow Player - Entry point"""

import os
import sys
import signal
import logging
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import Config
from src.flow_player import FlowPlayer
from src.web.app import create_app


def setup_logging(log_path: Path, debug: bool = False):
    """Configure logging"""
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "flow-player.log"

    level = logging.DEBUG if debug else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce noise from libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Flow Player - Video/Audio/DMX Player for Raspberry Pi')
    parser.add_argument('--config', '-c', type=str, help='Path to config file')
    parser.add_argument('--port', '-p', type=int, default=5000, help='Web server port')
    parser.add_argument('--host', '-H', type=str, default='0.0.0.0', help='Web server host')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-web', action='store_true', help='Disable web interface')
    args = parser.parse_args()

    # Load configuration
    if args.config:
        config = Config.load(Path(args.config))
    else:
        config = Config.load()

    # Override with command line args
    if args.port:
        config.web_port = args.port
    if args.host:
        config.web_host = args.host

    # Setup logging
    setup_logging(config.logs_path, args.debug)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Flow Player starting...")
    logger.info("=" * 60)

    # Create player
    player = FlowPlayer(config)

    # Signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        player.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize player
    if not player.initialize():
        logger.error("Failed to initialize player")
        sys.exit(1)

    # Start web interface
    if not args.no_web:
        app = create_app(player)

        logger.info(f"Starting web interface on http://{config.web_host}:{config.web_port}")

        # Run Flask (in production, use gunicorn or similar)
        app.run(
            host=config.web_host,
            port=config.web_port,
            debug=args.debug,
            use_reloader=False,  # Disable reloader in production
            threaded=True
        )
    else:
        # Run without web interface (headless mode)
        logger.info("Running in headless mode (no web interface)")
        signal.pause()


if __name__ == '__main__':
    main()
