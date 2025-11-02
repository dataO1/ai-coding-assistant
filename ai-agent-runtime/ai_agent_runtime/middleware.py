# ai_agent_runtime/middleware.py
from typing import Callable, Any, Dict
from pathlib import Path
from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools.base import ToolException
import logging

from ai_agent_runtime.context import AgentContext

logger = logging.getLogger(__name__)


class FileAccessMiddleware(AgentMiddleware):
    """Middleware that enforces context-based file access control.

    This middleware intercepts tool calls and validates file paths
    against the current AgentContext's allowed roots.
    """

    def __init__(self, context: AgentContext):
        """Initialize middleware with agent context.

        Args:
            context: AgentContext specifying source and working directory
        """
        self.context = context
        logger.info(
            f"FileAccessMiddleware initialized for {context.source.value} "
            f"context with roots: {context.allowed_roots}"
        )

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        """Intercept tool calls and validate file access.

        Args:
            request: Tool call request
            handler: Original tool handler

        Returns:
            Tool result or error message
        """
        tool_name = request.tool_call.get("name", "unknown")
        tool_input = request.tool_call.get("args", {})

        # File access tools to check
        filesystem_tools = {
            "read_file": ["path"],
            "write_file": ["path"],
            "edit_file": ["path"],
            "create_directory": ["path"],
            "list_directory": ["path"],
            "move_file": ["source", "destination"],
            "search_files": ["path"],
            "get_file_info": ["path"],
        }

        if tool_name in filesystem_tools:
            # Get paths to validate
            path_fields = filesystem_tools[tool_name]

            for field in path_fields:
                if field in tool_input:
                    path = tool_input[field]

                    # Validate path
                    if not self._is_path_allowed(path):
                        logger.warning(
                            f"Access denied for {tool_name}: "
                            f"path '{path}' not in allowed roots {self.context.allowed_roots}"
                        )

                        # Return error message to agent
                        return {
                            "type": "error",
                            "content": f"Access denied: Path '{path}' is not accessible in {self.context.source.value} context. "
                                     f"Allowed directories: {', '.join(self.context.allowed_roots)}",
                        }

        # Tool call is allowed, proceed
        logger.debug(f"Tool call allowed: {tool_name}({tool_input})")
        return handler(request)

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a path is allowed."""
        try:
            target_path = Path(path).resolve()

            # Check against all allowed roots
            for root in self.context.allowed_roots:
                allowed_root = Path(root).resolve()
                try:
                    target_path.relative_to(allowed_root)
                    return True
                except ValueError:
                    continue

            return False
        except Exception as e:
            logger.error(f"Error validating path '{path}': {e}")
            return False
