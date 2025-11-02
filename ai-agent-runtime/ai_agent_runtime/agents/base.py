# ai_agent_runtime/agents/base.py
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from langchain.agents import create_agent
from langchain.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama  # ✅ Use this instead

from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)
from ai_agent_runtime.middleware import FileAccessMiddleware
from ai_agent_runtime.context import AgentContext

class AgentContext(str, Enum):
    """Available execution contexts."""
    NVIM = "nvim"
    VSCODE = "vscode"
    SHELL = "shell"
    WEB = "web"


class AgentManifest(BaseModel):
    """Pipeline manifest defining agent capabilities."""
    name: str
    description: str
    model: str
    systemPrompt: str
    requiredTools: List[str] = Field(default_factory=list)
    optionalTools: List[str] = Field(default_factory=list)
    contexts: List[str] = Field(default_factory=lambda: ["shell"])


class AgentOutput(BaseModel):
    """Output from an agent."""
    content: str
    toolsused: List[str] = Field(default_factory=list)
    reasoning: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for specialized agents with LangChain MCP integration.

    Uses LangChain v1 create_agent with ChatOllama (no experimental deps).
    """

    # Class-level MCP client - shared across all agents
    _mcp_client: Optional[MultiServerMCPClient] = None
    _mcp_tools_cache: Optional[List[BaseTool]] = None
    _mcp_servers_config: Optional[Dict] = None

    def __init__(self, manifest: AgentManifest, ollama_url: str):
        self.manifest = manifest
        self.ollama_url = ollama_url
        self.llm = self.create_llm()
        self.tools: List[BaseTool] = []
        self.agent = None
        self.agent_context: Optional[AgentContext] = None  # NEW
        logger.info(
            f"Initialized {manifest.name} agent with model {manifest.model}"
        )

    @classmethod
    async def initialize_mcp_servers(cls, mcp_servers_config: Optional[Dict] = None):
        """Initialize MCP servers from user-provided config."""
        if cls._mcp_client is not None:
            return

        cls._mcp_servers_config = mcp_servers_config or {}

        if not cls._mcp_servers_config:
            logger.warning("No MCP servers configured in manifests.json")
            cls._mcp_tools_cache = []
            return

        try:
            logger.info(f"Connecting to {len(cls._mcp_servers_config)} MCP servers...")
            cls._mcp_client = MultiServerMCPClient(cls._mcp_servers_config)
            cls._mcp_tools_cache = await cls._mcp_client.get_tools()

            logger.info(
                f"✓ MCP: Connected successfully\n"
                f"✓ Available tools: {len(cls._mcp_tools_cache)}"
            )

            # Log tool breakdown
            tool_groups = {}
            for tool in cls._mcp_tools_cache:
                prefix = tool.name.split("_")[0]
                tool_groups[prefix] = tool_groups.get(prefix, 0) + 1

            for prefix, count in tool_groups.items():
                logger.info(f"  - {prefix}: {count} tools")

        except Exception as e:
            logger.error(f"Failed to initialize MCP servers: {e}", exc_info=True)
            cls._mcp_tools_cache = []

    def setup_agent(self, context: Optional[AgentContext] = None):
        """Setup agent with optional context for file access control.

        Args:
            context: AgentContext specifying working directory and source
        """
        # Store context for later use
        self.agent_context = context or AgentContext()

        all_tool_names = (
            self.manifest.requiredTools + self.manifest.optionalTools
        )

        logger.info(f"Requested tool names: {all_tool_names}")

        if not all_tool_names or not self._mcp_tools_cache:
            logger.warning(
                f"{self.manifest.name}: No tools requested or available."
            )
            self.tools = []
        else:
            # Filter tools by exact name match
            self.tools = [
                tool
                for tool in self._mcp_tools_cache
                if tool.name in all_tool_names
            ]

            logger.info(
                f"{self.manifest.name}: Selected {len(self.tools)} tools: "
                f"{[t.name for t in self.tools]}"
            )

        # Create middleware for file access control
        middleware = [FileAccessMiddleware(self.agent_context)]

        # Create agent with create_agent - now with middleware!
        self.agent = create_agent(
            model=self.llm,
            system_prompt=self.manifest.systemPrompt,
            tools=self.tools,
            middleware=middleware,  # NEW: Add middleware
        )

    async def process_with_tools(
        self,
        query: str,
        context: Optional[AgentContext] = None
    ) -> str:
        """Process query using LangChain v1 agent with context-aware file access."""
        # Setup agent if needed
        if self.agent is None:
            await self.initialize_mcp_servers(self._mcp_servers_config)
            self.setup_agent(context)

        try:
            logger.info(f"{self.manifest.name}: Processing query")

            # Use native async invoke
            result = await self.agent.ainvoke({
                "messages": [{"role": "user", "content": query}]
            })

            # Extract output
            if isinstance(result, dict) and "messages" in result:
                messages = result["messages"]
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, "content"):
                        return last_message.content
                    elif isinstance(last_message, dict) and "content" in last_message:
                        return last_message["content"]

            return str(result)

        except Exception as e:
            logger.error(f"{self.manifest.name} error: {e}", exc_info=True)
            return f"Error: {str(e)}"

    def create_llm(self):
        """Create ChatOllama LLM."""
        return ChatOllama(
            model=self.manifest.model,
            base_url=self.ollama_url,
            temperature=self.get_temperature(),
            top_p=0.9,
        )

    def get_temperature(self) -> float:
        """Get appropriate temperature for this agent."""
        return 0.2

    async def process(
        self,
        query: str,
        context: Optional[AgentContext] = None
    ) -> AgentOutput:
        """Process a query with context-aware file access."""
        content = await self.process_with_tools(query, context)
        return await self.execute(query, context, {}, content)

    @abstractmethod
    async def execute(
        self,
        query: str,
        context: str,
        resolved_tools: Dict[str, Any],
        agent_response: str = ""
    ) -> AgentOutput:
        """Execute agent-specific logic."""
        pass
