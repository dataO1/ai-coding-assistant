# backend/config/logging_config.py - Structured Logging Setup

import sys
import logging
from typing import Any
import structlog


def setup_logging(log_level: str = "info") -> None:
    """
    Configure structured logging with structlog + stdlib
    
    Outputs JSON logs for production, colored output for development
    """
    
    # Convert string level to logging level
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecimalEncoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Handler for stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    formatter = logging.Formatter(
        "%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger instance"""
    return structlog.get_logger(name)
