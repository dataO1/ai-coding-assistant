# ai_agent_runtime/agents/base.py
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)


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

    MCP (Model Context Protocol) integration is handled automatically via
    LangChain's official langchain-mcp-adapters package.
    """

    # Class-level MCP client - shared across all agents
    _mcp_client: Optional[MultiServerMCPClient] = None
    _mcp_tools_cache: Optional[List] = None
    _mcp_servers_config: Optional[Dict] = None

    def __init__(self, manifest: AgentManifest, ollama_url: str):
        self.manifest = manifest
        self.ollama_url = ollama_url
        self.llm = self.create_llm()
        self.llm_with_tools = None
        logger.info(
            f"Initialized {manifest.name} agent with model {manifest.model}"
        )

    @classmethod
    async def initialize_mcp_servers(cls, mcp_servers_config: Optional[Dict] = None):
        """Initialize MCP servers from user-provided config.

        Args:
            mcp_servers_config: Dict of MCP server configurations from manifests.json
                Example:
                {
                    "filesystem": {
                        "command": "npx",
                        "args": ["@modelcontextprotocol/server-filesystem", "/home"],
                        "transport": "stdio"
                    },
                    "git": {
                        "command": "npx",
                        "args": ["git-mcp-server"],
                        "transport": "stdio"
                    }
                }
        """
        if cls._mcp_client is not None:
            return  # Already initialized

        # Store config for reference
        cls._mcp_servers_config = mcp_servers_config or {}

        if not cls._mcp_servers_config:
            logger.warning("No MCP servers configured in manifests.json")
            cls._mcp_tools_cache = []
            return

        try:
            logger.info(f"Connecting to {len(cls._mcp_servers_config)} MCP servers...")

            # Initialize MultiServerMCPClient with user-provided config
            cls._mcp_client = MultiServerMCPClient(cls._mcp_servers_config)

            # Get all tools from all configured servers
            cls._mcp_tools_cache = await cls._mcp_client.get_tools()

            logger.info(
                f"✓ MCP: Connected successfully\n"
                f"✓ Available tools: {len(cls._mcp_tools_cache)}"
            )

            # Log tool breakdown by server prefix
            tool_groups = {}
            for tool in cls._mcp_tools_cache:
                # Tools are typically prefixed with action verb
                prefix = tool.name.split("_")[0]
                tool_groups[prefix] = tool_groups.get(prefix, 0) + 1

            for prefix, count in tool_groups.items():
                logger.info(f"  - {prefix}: {count} tools")

        except Exception as e:
            logger.error(f"Failed to initialize MCP servers: {e}", exc_info=True)
            cls._mcp_tools_cache = []

    async def setup_tools(self):
        """Setup tools for this agent based on manifest.

        Uses exact tool name matching - no smart filtering.
        User specifies exact tool names in requiredTools/optionalTools.
        """
        await self.initialize_mcp_servers(self._mcp_servers_config)

        all_tool_names = (
            self.manifest.requiredTools + self.manifest.optionalTools
        )

        logger.info(f"Requested tool names: {all_tool_names}")

        if not all_tool_names or not self._mcp_tools_cache:
            self.llm_with_tools = self.llm
            if not all_tool_names:
                logger.info(f"{self.manifest.name}: No tools requested")
            return

        # Exact tool name matching - no smart filtering
        available_tools = [
            tool
            for tool in self._mcp_tools_cache
            if tool.name in all_tool_names
        ]

        logger.info(
            f"Matched tools: {[t.name for t in available_tools]}"
        )

        if available_tools:
            self.llm_with_tools = self.llm.bind_tools(available_tools)
            logger.info(
                f"{self.manifest.name}: Bound {len(available_tools)} tools"
            )
        else:
            self.llm_with_tools = self.llm
            if self.manifest.requiredTools:
                logger.warning(
                    f"{self.manifest.name}: No tools matched requested names: "
                    f"{all_tool_names}"
                )

    def create_llm(self) -> BaseChatModel:
        """Create LLM instance."""
        return ChatOllama(
            model=self.manifest.model,
            base_url=self.ollama_url,
            temperature=self.get_temperature(),
            top_p=0.9,
        )

    def get_temperature(self) -> float:
        """Get appropriate temperature for this agent."""
        return 0.2

    async def process(self, query: str, context: str = "shell") -> AgentOutput:
        """Process a query with automatic MCP tool integration."""
        if self.llm_with_tools is None:
            await self.setup_tools()

        return await self.execute(query, context, {})

    @abstractmethod
    async def execute(
        self, query: str, context: str, resolved_tools: Dict[str, Any]
    ) -> AgentOutput:
        """Execute the agent. Must be implemented by subclasses."""
        pass

    def create_prompt(self, system_prompt: str) -> ChatPromptTemplate:
        """Create a standardized prompt template."""
        return ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
