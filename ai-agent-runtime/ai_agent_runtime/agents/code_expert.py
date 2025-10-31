import asyncio
from typing import Dict, Any

from .base import BaseAgent, AgentOutput
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)

class CodeExpertAgent(BaseAgent):
    """
    Expert code generation and modification agent.

    Specializes in:
    - Code generation from specifications
    - Code refactoring and optimization
    - Bug fixing and debugging
    - Code review and suggestions

    Uses available tools (LSP, tree-sitter, git) for context-aware suggestions.
    """

    def _get_temperature(self) -> float:
        """Slightly creative for code generation"""
        return 0.2

    async def _execute(
        self,
        query: str,
        context: str,
        resolved_tools: Dict[str, Any],
    ) -> AgentOutput:
        """Execute code expert agent"""

        tools_info = self.format_tools_info(resolved_tools)

        # Enhance system prompt with available tools
        system_prompt = f"""{self.manifest.systemPrompt}

AVAILABLE TOOLS:
{tools_info}

CONTEXT: {context}

Use the available tools intelligently to provide better code suggestions.
If LSP is available, use it for type information.
If tree-sitter is available, use it for code structure analysis.
If git is available, check history for patterns.
"""

        prompt = self.create_prompt(system_prompt)
        chain = prompt | self.llm

        logger.info(f"Code expert processing: {query[:60]}...")

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: chain.invoke({"input": query})
        )

        logger.debug(f"Code expert response length: {len(response.content)}")

        return AgentOutput(
            content=response.content,
            tools_used=resolved_tools["resolved"],
            metadata={
                "agent_type": "code_expert",
                "context": context,
            }
        )
