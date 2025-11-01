import asyncio
from typing import Dict, Any

from .base import BaseAgent, AgentOutput
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)

class CodeExpertAgent(BaseAgent):
    """Expert code generator and refactorer with MCP tool support."""

    async def execute(
        self, query: str, context: str, resolved_tools: Dict[str, Any]
    ) -> AgentOutput:
        """Execute code expert agent with automatic tool calling."""
        try:
            prompt = self.create_prompt(self.manifest.systemPrompt)

            logger.info(f"Code Expert processing: {query[:60]}...")

            # LangChain handles tool calling automatically
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.llm_with_tools.invoke(
                    prompt.format_messages(input=query)
                ),
            )

            # Extract tool calls if any
            tool_calls = getattr(response, "tool_calls", [])
            if tool_calls:
                logger.info(f"Code Expert used {len(tool_calls)} tools")

            return AgentOutput(
                content=response.content,
                toolsused=[tc.get("name", "") for tc in tool_calls],
                metadata={"context": context},
            )
        except Exception as e:
            logger.error(f"Code Expert error: {e}", exc_info=True)
            return AgentOutput(
                content=f"Error: {str(e)}",
                reasoning=str(e),
            )
