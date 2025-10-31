import logging
import sys
from typing import Optional

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get configured logger instance"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        # Only configure if not already configured
        handler = logging.StreamHandler(sys.stdout)

        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if level:
        logger.setLevel(level)
    else:
        logger.setLevel(logging.INFO)

    return logger
