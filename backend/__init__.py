# backend/__init__.py - Backend Package

__version__ = "0.1.0"
__title__ = "Agentic IDE Backend"
__description__ = "LLM-orchestrated multi-agent code generation system"

from backend.config.settings import settings
from backend.config.logging_config import setup_logging, get_logger

__all__ = [
    "settings",
    "setup_logging",
    "get_logger",
]
