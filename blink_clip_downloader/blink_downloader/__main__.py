"""Entry point: `python3 -m blink_downloader`."""

from __future__ import annotations

import asyncio
import logging
import sys

from .app import BlinkClipDownloaderApp
from .config import load_config


def _setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=numeric,
        stream=sys.stdout,
        force=True,
    )
    # Suppress chatty third-party loggers at INFO level.
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.client").setLevel(logging.WARNING)
    logging.getLogger("blinkpy.helpers.util").setLevel(logging.WARNING)


def main() -> None:
    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as exc:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger(__name__).error("Configuration error: %s", exc)
        sys.exit(1)

    _setup_logging(config.log_level)
    app = BlinkClipDownloaderApp(config)

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
