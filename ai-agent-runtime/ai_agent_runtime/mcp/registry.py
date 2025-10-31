import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..utils import get_logger

logger = get_logger(__name__)

@dataclass
class MCPTool:
    """Represents a single MCP tool"""
    name: str
    description: str
    available_in_contexts: List[str]  # ["nvim", "vscode", "shell", "web"]

    def is_available(self, context: str) -> bool:
        """Check if tool is available in given context"""
        return context in self.available_in_contexts

class MCPRegistry:
    """
    Registry of available MCP tools and their context availability.

    This maps MCP servers to the contexts where they're available:
    - nvim: LSP, tree-sitter, nvim-mcp, filesystem, git
    - vscode: continue-mcp, LSP, filesystem, git
    - shell: filesystem, git, web-search
    - web: web-search, filesystem (remote)
    """

    # Define tools and their availability per context
    AVAILABLE_TOOLS = {
        "lsp": MCPTool(
            name="lsp",
            description="Language Server Protocol for type info and diagnostics",
            available_in_contexts=["nvim", "vscode"],
        ),
        "tree-sitter": MCPTool(
            name="tree-sitter",
            description="AST parsing and code structure analysis",
            available_in_contexts=["nvim", "vscode"],
        ),
        "nvim-mcp": MCPTool(
            name="nvim-mcp",
            description="Neovim buffer and editor context",
            available_in_contexts=["nvim"],
        ),
        "continue-mcp": MCPTool(
            name="continue-mcp",
            description="VS Code Continue.dev integration",
            available_in_contexts=["vscode"],
        ),
        "filesystem": MCPTool(
            name="filesystem",
            description="File system operations and access",
            available_in_contexts=["nvim", "vscode", "shell", "web"],
        ),
        "git": MCPTool(
            name="git",
            description="Git history, blame, and operations",
            available_in_contexts=["nvim", "vscode", "shell"],
        ),
        "web-search": MCPTool(
            name="web-search",
            description="Web search and information retrieval",
            available_in_contexts=["shell", "web"],
        ),
    }

    def __init__(self):
        self.tools = self.AVAILABLE_TOOLS.copy()
        logger.info(f"Initialized MCPRegistry with {len(self.tools)} tools")

    def get_available_tools(self, context: str) -> List[MCPTool]:
        """Get all tools available in a context"""
        available = [
            tool for tool in self.tools.values()
            if tool.is_available(context)
        ]
        logger.debug(f"Available tools in context '{context}': {[t.name for t in available]}")
        return available

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a specific tool"""
        return self.tools.get(name)

    def resolve_tools(
        self,
        required: List[str],
        optional: List[str],
        context: str,
        fallback_mode: str = "degrade",
    ) -> Dict[str, Any]:
        """
        Resolve tools based on requirements and context.

        Args:
            required: Tools that MUST be available
            optional: Tools that improve quality if available
            context: The context (nvim, vscode, shell, web)
            fallback_mode: "degrade" (skip missing) or "fail" (error)

        Returns:
            {
                "resolved": List[str],  # Available tools
                "missing_required": List[str],  # Required but unavailable
                "missing_optional": List[str],  # Optional and unavailable
                "available_in_context": List[str],  # All available in context
            }
        """
        available_in_context = {
            t.name for t in self.get_available_tools(context)
        }

        resolved = []
        missing_required = []
        missing_optional = []

        # Check required tools
        for tool_name in required:
            if tool_name in available_in_context:
                resolved.append(tool_name)
            else:
                missing_required.append(tool_name)

        # Check optional tools
        for tool_name in optional:
            if tool_name in available_in_context:
                resolved.append(tool_name)
            else:
                missing_optional.append(tool_name)

        # Handle missing required tools
        if missing_required:
            msg = f"Missing required tools: {missing_required}"
            if fallback_mode == "fail":
                logger.error(msg)
                raise ValueError(msg)
            else:
                logger.warning(f"{msg} (degrading)")

        if missing_optional:
            logger.info(f"Optional tools unavailable: {missing_optional} (continuing without them)")

        result = {
            "resolved": resolved,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "available_in_context": list(available_in_context),
        }

        logger.debug(f"Tool resolution result: {result}")
        return result

# Global registry instance
_registry: Optional[MCPRegistry] = None

def get_mcp_registry() -> MCPRegistry:
    """Get or create global MCP registry"""
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry
