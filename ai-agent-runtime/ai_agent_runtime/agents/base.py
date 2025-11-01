from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from contextlib import AsyncExitStack
from pydantic import BaseModel, Field
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from ai_agent_runtime.utils import getlogger

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

    def __init__(self, manifest: AgentManifest, ollama_url: str):
        self.manifest = manifest
        self.ollama_url = ollama_url
        self.llm = self.create_llm()
        self.llm_with_tools = None
        logger.info(
            f"Initialized {manifest.name} agent with model {manifest.model}"
        )

    @classmethod
    async def initialize_mcp_servers(cls):
        """Initialize MCP servers once for all agents (class method).

        This connects to all available MCP servers via LangChain's
        MultiServerMCPClient and caches the tools.
        """
        if cls._mcp_client is not None:
            return  # Already initialized

        try:
            # LangChain handles all MCP server connections automatically
            cls._mcp_client = MultiServerMCPClient({
                "filesystem": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "mcp_server_filesystem"],
                },
                "git": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "mcp_server_git"],
                },
            })

            # Get all tools from all MCP servers (one line!)
            cls._mcp_tools_cache = await cls._mcp_client.get_tools()
            logger.info(
                f"MCP: Connected to servers with {len(cls._mcp_tools_cache)} tools"
            )
        except Exception as e:
            logger.error(f"Failed to initialize MCP servers: {e}", exc_info=True)
            cls._mcp_tools_cache = []

    async def setup_tools(self):
        """Setup tools for this agent based on manifest.

        Filters tools based on requiredTools and optionalTools,
        then binds them to the LLM for native tool calling.
        """
        # Ensure MCP servers initialized
        await self.initialize_mcp_servers()

        all_tool_capabilities = self.manifest.requiredTools + self.manifest.optionalTools

        if not all_tool_capabilities or not self._mcp_tools_cache:
            # No tools needed or none available
            self.llm_with_tools = self.llm
            return

        # Filter tools by capability match
        # Tool names include their server prefix (e.g., "filesystem_list_files")
        available_tools = [
            tool
            for tool in self._mcp_tools_cache
            if any(cap in tool.name.lower() for cap in all_tool_capabilities)
        ]

        if available_tools:
            # Bind tools to LLM for native tool calling
            self.llm_with_tools = self.llm.bind_tools(available_tools)
            logger.info(
                f"{self.manifest.name}: Bound {len(available_tools)} tools "
                f"from capabilities {all_tool_capabilities}"
            )
        else:
            self.llm_with_tools = self.llm
            if self.manifest.requiredTools:
                logger.warning(
                    f"{self.manifest.name}: No tools matched required capabilities: "
                    f"{self.manifest.requiredTools}"
                )

    def create_llm(self) -> ChatOllama:
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
