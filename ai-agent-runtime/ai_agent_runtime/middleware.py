# ai_agent_runtime/middleware.py
from typing import Callable, Any
from pathlib import Path
import asyncio
import logging
from langchain.agents.middleware import AgentMiddleware

from ai_agent_runtime.context import AgentContext

logger = logging.getLogger(__name__)


class FileAccessMiddleware(AgentMiddleware):
    """Middleware that enforces context-based file access control.

    Supports both sync and async contexts for LangChain 1.x agents.
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
        """Synchronous tool call wrapper."""
        return self._validate_and_execute(request, handler)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        """Asynchronous tool call wrapper for async agents.

        This method is called when the agent uses ainvoke().
        """
        return await self._avalidate_and_execute(request, handler)

    def _validate_and_execute(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        """Validate file paths and execute tool."""
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

                        return {
                            "type": "error",
                            "content": f"Access denied: Path '{path}' is not accessible in {self.context.source.value} context. "
                                     f"Allowed directories: {', '.join(self.context.allowed_roots)}",
                        }

        logger.debug(f"Tool call allowed: {tool_name}({tool_input})")
        return handler(request)

    async def _avalidate_and_execute(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        """Async version of validation and execution."""
        # Validation logic is the same, just async-aware handler call
        tool_name = request.tool_call.get("name", "unknown")
        tool_input = request.tool_call.get("args", {})

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
            path_fields = filesystem_tools[tool_name]

            for field in path_fields:
                if field in tool_input:
                    path = tool_input[field]

                    if not self._is_path_allowed(path):
                        logger.warning(
                            f"Access denied for {tool_name}: "
                            f"path '{path}' not in allowed roots {self.context.allowed_roots}"
                        )

                        return {
                            "type": "error",
                            "content": f"Access denied: Path '{path}' is not accessible in {self.context.source.value} context. "
                                     f"Allowed directories: {', '.join(self.context.allowed_roots)}",
                        }

        logger.debug(f"Tool call allowed: {tool_name}({tool_input})")

        # Handle both sync and async handlers
        result = handler(request)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a path is allowed."""
        try:
            target_path = Path(path).resolve()

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
