import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from contextlib import AsyncExitStack
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model, BaseChatModel
from langchain_ollama import ChatOllama
# from langchain_community.chat_models import ChatOllama

from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)


mcp_hub_url = os.getenv("MCP_HUB_URL", "http://localhost:37373/mcp")



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

    def __init__(self, manifest: AgentManifest, ollama_url: str):
        self.manifest = manifest
        self.ollama_url = ollama_url
        self.llm = self.create_llm()
        self.llm_with_tools = None
        logger.info(
            f"Initialized {manifest.name} agent with model {manifest.model}"
        )

    @classmethod
    async def initialize_mcp_servers(
        cls,
    ):
        """Initialize MCP servers via mcp-hub centralized endpoint.

        Instead of connecting to individual MCP servers, connect to mcp-hub's
        single HTTP endpoint (streamable-http) which aggregates all servers.

        Args:
            mcp_hub_url: URL to mcp-hub's /mcp endpoint (streamable-http)
        """

        if cls._mcp_client is not None:
            return  # Already initialized

        try:
            logger.info(f"Connecting to mcp-hub at {mcp_hub_url}...")

            # Connect to mcp-hub via streamable-http (SSE)
            # mcp-hub aggregates all configured servers into one endpoint

            cls._mcp_client = MultiServerMCPClient({
                "filesystem": {
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-filesystem", "/home"],
                    "transport": "stdio",
                }
                # "mcp-hub": {
                #     "url": mcp_hub_url,
                #     "transport": "streamable_http",
                # }
            })

            # Get all tools from mcp-hub (which has aggregated all servers)
            cls._mcp_tools_cache = await cls._mcp_client.get_tools()

            logger.info(
                f"✓ MCP Hub: Connected successfully"
                f"\n✓ Available tools: {len(cls._mcp_tools_cache)}"
            )

            # Log tool breakdown by server
            tool_groups = {}
            for tool in cls._mcp_tools_cache:
                server = tool.name.split("_")[0]  # Tools are prefixed with server name
                tool_groups[server] = tool_groups.get(server, 0) + 1

            for server, count in tool_groups.items():
                logger.info(f"  - {server}: {count} tools")

        except Exception as e:
            logger.error(f"Failed to initialize MCP Hub: {e}", exc_info=True)
            cls._mcp_tools_cache = []

    async def setup_tools(self):
        """Setup tools for this agent based on manifest."""
        await self.initialize_mcp_servers()

        all_tool_capabilities = (
            self.manifest.requiredTools + self.manifest.optionalTools
        )
        logger.info( f"All Tool Capabilities: {all_tool_capabilities}")
        # logger.info( f"Tools Cache: {self._mcp_tools_cache}")

        if not all_tool_capabilities or not self._mcp_tools_cache:
            self.llm_with_tools = self.llm
            logger.info("No tool capabilities, invoke LLM without tools")
            return

        # Filter tools by capability match
        available_tools = [
            tool
            for tool in self._mcp_tools_cache
            if any(cap in tool.name.lower() for cap in all_tool_capabilities)
        ]
        logger.info( f"Available tools: {available_tools}")

        if available_tools:
            self.llm_with_tools = self.llm.bind_tools(available_tools)
            logger.info(
                f"{self.manifest.name}: Bound {len(available_tools)} tools"
            )
        else:
            self.llm_with_tools = self.llm
            if self.manifest.requiredTools:
                logger.warning(
                    f"{self.manifest.name}: No tools matched required capabilities"
                )

    def create_llm(self) -> BaseChatModel:
        """Create LLM instance."""
        return ChatOllama(
            model=self.manifest.model,
            base_url=self.ollama_url,
            temperature=self.get_temperature(),
            top_p=0.9,)

    def get_temperature(self) -> float:
        """Get appropriate temperature for this agent."""
        return 0.2

    async def process(self, query: str, context: str = "shell") -> AgentOutput:
        """Process a query with automatic MCP tool integration."""
        # Setup tools if not already done
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
