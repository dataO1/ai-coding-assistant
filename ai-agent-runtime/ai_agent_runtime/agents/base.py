from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from langchain_community.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate

from ai_agent_runtime.utils import get_logger
from ai_agent_runtime.mcp import get_mcp_registry

logger = get_logger(__name__)

class AgentContext(str, Enum):
    """Available execution contexts"""
    NVIM = "nvim"
    VSCODE = "vscode"
    SHELL = "shell"
    WEB = "web"

@dataclass
class AgentManifest:
    """Pipeline manifest defining agent capabilities"""
    name: str
    description: str
    model: str
    systemPrompt: str
    requiredTools: List[str] = field(default_factory=list)
    optionalTools: List[str] = field(default_factory=list)
    fallbackMode: str = "degrade"
    contexts: List[str] = field(default_factory=lambda: ["nvim", "vscode", "shell"])

@dataclass
class AgentOutput:
    """Output from an agent"""
    content: str
    tools_used: List[str]
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseAgent(ABC):
    """
    Base class for all specialized agents.

    Agents process queries and return structured responses.
    Each agent has specific expertise and tool requirements.
    """

    def __init__(
        self,
        manifest: AgentManifest,
        ollama_url: str,
    ):
        self.manifest = manifest
        self.ollama_url = ollama_url
        self.mcp_registry = get_mcp_registry()
        self.llm = self._create_llm()

        logger.info(f"Initialized {manifest.name} agent with model {manifest.model}")

    def _create_llm(self) -> ChatOllama:
        """Create LLM instance"""
        return ChatOllama(
            model=self.manifest.model,
            base_url=self.ollama_url,
            temperature=self._get_temperature(),
            top_p=0.9,
        )

    def _get_temperature(self) -> float:
        """Get appropriate temperature for this agent"""
        # Override in subclasses for different temperatures
        return 0.2

    def resolve_tools(self, context: str) -> Dict[str, Any]:
        """Resolve available tools for this context"""
        return self.mcp_registry.resolve_tools(
            required=self.manifest.requiredTools,
            optional=self.manifest.optionalTools,
            context=context,
            fallback_mode=self.manifest.fallbackMode,
        )

    def format_tools_info(self, resolved_tools: Dict[str, Any]) -> str:
        """Format tool information for LLM context"""
        if not resolved_tools["resolved"]:
            return "No tools available in this context."

        tools_list = ", ".join(resolved_tools["resolved"])
        info = f"Available tools: {tools_list}"

        if resolved_tools["missing_optional"]:
            info += f"\n(Optional tools unavailable: {', '.join(resolved_tools['missing_optional'])})"

        return info

    async def process(
        self,
        query: str,
        context: str = "shell",
    ) -> AgentOutput:
        """
        Process a query and return structured output.

        Must be implemented by subclasses.
        """
        resolved_tools = self.resolve_tools(context)

        # Log tool resolution
        logger.info(f"Agent '{self.manifest.name}' using tools: {resolved_tools['resolved']}")

        # Call subclass implementation
        result = await self._execute(query, context, resolved_tools)

        # Ensure tools_used is populated
        result.tools_used = resolved_tools["resolved"]

        return result

    @abstractmethod
    async def _execute(
        self,
        query: str,
        context: str,
        resolved_tools: Dict[str, Any],
    ) -> AgentOutput:
        """Execute the agent. Must be implemented by subclasses."""
        pass

    def create_prompt(self, system_prompt: str) -> ChatPromptTemplate:
        """Create a standardized prompt template"""
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
