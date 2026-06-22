# Shared logger factory used across every module in the project.
# Each module calls get_logger(__name__) to get a logger tagged with its own name,
# so log lines always show which module they came from.

import logging
import sys
from utils.config import LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    # Returns a configured logger for the given module name.
    # Adds a StreamHandler on first call; subsequent calls reuse the same logger.
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL)
    return logger
