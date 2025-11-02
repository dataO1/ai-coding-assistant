# ai_agent_runtime/agents/base.py
import asyncio
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import BaseChatModel
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import create_tool_calling_agent
from langchain_experimental.llms.ollama_functions import OllamaFunctions

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

    Uses OllamaFunctions for native tool calling with Ollama models.
    """

    # Class-level MCP client - shared across all agents
    _mcp_client: Optional[MultiServerMCPClient] = None
    _mcp_tools_cache: Optional[List[Tool]] = None
    _mcp_servers_config: Optional[Dict] = None

    def __init__(self, manifest: AgentManifest, ollama_url: str):
        self.manifest = manifest
        self.ollama_url = ollama_url
        self.llm = self.create_llm()
        self.tools: List[Tool] = []
        self.agent_executor: Optional[AgentExecutor] = None
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

    async def setup_agent_executor(self):
        """Setup agent executor with OllamaFunctions + create_tool_calling_agent."""
        await self.initialize_mcp_servers(self._mcp_servers_config)

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

        if not self.tools:
            # No tools - use LLM directly
            logger.info(f"{self.manifest.name}: No tools, skipping agent executor")
            self.agent_executor = None
            return

        # Create prompt with agent_scratchpad for tool calling
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.manifest.systemPrompt),
            MessagesPlaceholder("agent_scratchpad"),
            ("human", "{input}"),
        ])

        # Create tool calling agent
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)

        # Create agent executor - handles the tool calling loop automatically
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=10,
        )

    async def process_with_tools(self, query: str) -> str:
        """Process query using agent executor.

        The AgentExecutor handles the full tool calling loop:
        1. LLM invocation
        2. Tool call extraction
        3. Tool execution
        4. Result feeding back to LLM
        5. Loop until done
        """
        if self.agent_executor is None:
            await self.setup_agent_executor()

        if self.agent_executor is None:
            # No tools available - use LLM directly
            logger.info(f"{self.manifest.name}: Using LLM without tools")
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.llm.invoke(query),
            )
            return response.content

        try:
            logger.info(f"{self.manifest.name}: Processing with agent executor")

            # Invoke agent executor - it handles the full loop
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.agent_executor.invoke({"input": query}),
            )

            return result.get("output", "")
        except Exception as e:
            logger.error(f"{self.manifest.name} error: {e}", exc_info=True)
            return f"Error: {str(e)}"

    def create_llm(self) -> BaseChatModel:
        """Create OllamaFunctions LLM with JSON mode for tool calling."""
        return OllamaFunctions(
            model=self.manifest.model,
            base_url=self.ollama_url,
            temperature=self.get_temperature(),
            format="json",  # ✅ Enable JSON mode for tool calling
            top_p=0.9,
        )

    def get_temperature(self) -> float:
        """Get appropriate temperature for this agent."""
        return 0.2

    async def process(self, query: str, context: str = "shell") -> AgentOutput:
        """Process a query with automatic MCP tool integration."""
        content = await self.process_with_tools(query)
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

    def create_prompt(self, system_prompt: str) -> ChatPromptTemplate:
        """Create a standardized prompt template."""
        return ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
