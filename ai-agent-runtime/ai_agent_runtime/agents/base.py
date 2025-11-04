# ai_agent_runtime/agents/base.py
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain.agents import create_agent
from langchain.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama

from ai_agent_runtime.utils import get_logger
from ai_agent_runtime.context import AgentContext
from ai_agent_runtime.middleware import FileAccessMiddleware

logger = get_logger(__name__)


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
    """Base class for specialized agents with LangChain MCP integration."""

    # Class-level MCP client
    _mcp_client: Optional[MultiServerMCPClient] = None
    _mcp_tools_cache: Optional[List[BaseTool]] = None
    _mcp_servers_config: Optional[Dict] = None

    def __init__(self, manifest: AgentManifest, ollama_url: str):
        self.manifest = manifest
        self.ollama_url = ollama_url
        self.llm = self.create_llm()
        self.tools: List[BaseTool] = []
        self.agent = None
        self.agent_context: Optional[AgentContext] = None
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
            logger.warning("No MCP servers configured")
            cls._mcp_tools_cache = []
            return

        try:
            logger.info(f"Connecting to {len(cls._mcp_servers_config)} MCP servers...")
            cls._mcp_client = MultiServerMCPClient(cls._mcp_servers_config)
            cls._mcp_tools_cache = await cls._mcp_client.get_tools()

            logger.info(f"✓ MCP: Connected successfully\n✓ Available tools: {len(cls._mcp_tools_cache)}")

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
        """Setup agent with proper tool binding verification."""
        self.agent_context = context or AgentContext()

        all_tool_names = self.manifest.requiredTools + self.manifest.optionalTools

        logger.info(
            f"Setting up {self.manifest.name} with tools: {all_tool_names} "
            f"(context: {self.agent_context.source.value}, wd: {self.agent_context.working_dir})"
        )

        if not all_tool_names or not self._mcp_tools_cache:
            logger.warning(f"{self.manifest.name}: No tools available")
            self.tools = []
        else:
            self.tools = [
                tool for tool in self._mcp_tools_cache
                if tool.name in all_tool_names
            ]

            logger.info(f"{self.manifest.name}: Selected tools: {[t.name for t in self.tools]}")

        # Enhanced system prompt
        enhanced_prompt = self._enhance_system_prompt(
            self.manifest.systemPrompt,
            self.agent_context
        )

        # Create middleware
        middleware = [FileAccessMiddleware(self.agent_context)] if self.tools else []

        # CRITICAL: Verify model supports tools
        if self.tools:
            # Test if model actually supports tool calling
            try:
                # Attempt to bind tools to verify compatibility
                test_llm = self.llm.bind_tools(self.tools)
                logger.info(f"✓ Model {self.manifest.model} successfully bound to {len(self.tools)} tools")
            except Exception as e:
                logger.error(f"❌ Model {self.manifest.model} failed to bind tools: {e}")
                logger.warning("Tools may not work properly - consider using a different model")

        # Create agent
        logger.info(f"Creating agent with {len(self.tools)} tools and {len(middleware)} middleware")
        self.agent = create_agent(
            model=self.llm,
            system_prompt=enhanced_prompt,
            tools=self.tools,
            middleware=middleware,
        )

    def _enhance_system_prompt(self, base_prompt: str, context: AgentContext) -> str:
        """Enhance system prompt with context and tool usage instructions."""
        context_info = f"""
EXECUTION CONTEXT:
- Source: {context.source.value}
- Working Directory: {context.working_dir}
- Allowed Directories: {', '.join(context.allowed_roots)}

IMPORTANT - TOOL USAGE INSTRUCTIONS:
You MUSTluse the available tools to complete tasks. When you need to:
- Create a directory: Use create_directory tool
- Write a file: Use write_file tool
- Read a file: Use read_file tool
- List directory: Use list_directory tool

DO NOT just describe what tools to use - ACTUALLY CALL THEM.
DO NOT output JSON describing tool calls - the system will handle tool invocation.

When using file tools, you can use:
1. Relative paths (e.g., "games/snake.py") - will resolve from working directory
2. Absolute paths within allowed directories


FOR ANY FILE MODIFICATION TASK:
1. read_file(path) — Establish actual content/formatting
2. analyze(content, requirements) — Map feedback to code changes
3. write_file(path, updated_content) OR edit_file(path, old_text, new_text) — Apply changes

"""
        return base_prompt + "\n" + context_info

    async def process_with_tools(self, query: str, context: Optional[AgentContext] = None) -> str:
        """Process query with tool execution tracking."""
        if self.agent is None or (context and context != self.agent_context):
            await self.initialize_mcp_servers(self._mcp_servers_config)
            self.setup_agent(context)

        try:
            logger.info(
                f"{self.manifest.name}: Processing query with {len(self.tools)} tools available"
            )

            result = await self.agent.ainvoke({"messages": [{"role": "user", "content": query}]})

            # Extract output and log tool usage
            if isinstance(result, dict) and "messages" in result:
                messages = result["messages"]

                # Check for actual tool calls in messages
                tool_calls_found = []
                for msg in messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        tool_calls_found.extend([tc.get("name", "unknown") for tc in msg.tool_calls])
                    elif isinstance(msg, dict) and "tool_calls" in msg and msg["tool_calls"]:
                        tool_calls_found.extend([tc.get("name", "unknown") for tc in msg["tool_calls"]])

                if tool_calls_found:
                    logger.info(f"✓ Tools actually invoked: {tool_calls_found}")
                else:
                    logger.warning(f"❌ No tool calls detected - LLM may not be using tools properly")

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
        """Create ChatOllama LLM with explicit tool support configuration."""
        return ChatOllama(
            model=self.manifest.model,
            base_url=self.ollama_url,
            temperature=self.get_temperature(),
            top_p=0.9,
            # Ensure model knows it should use tools
            num_ctx=8192,  # Larger context for tool schemas
        )

    def get_temperature(self) -> float:
        """Get appropriate temperature for this agent."""
        return 0.2

    async def process(self, query: str, context: Optional[AgentContext] = None) -> AgentOutput:
        """Process query with MCP tool integration."""
        content = await self.process_with_tools(query, context)
        return await self.execute(query, context, {}, content)

    @abstractmethod
    async def execute(
        self,
        query: str,
        context: Optional[AgentContext],
        resolved_tools: Dict[str, Any],
        agent_response: str = ""
    ) -> AgentOutput:
        """Execute agent-specific logic."""
        pass
