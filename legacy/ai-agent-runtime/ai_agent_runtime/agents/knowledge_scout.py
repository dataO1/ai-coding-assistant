# ai_agent_runtime/agents/knowledge_scout.py
from typing import Dict, Any
from .base import BaseAgent, AgentOutput
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)


class KnowledgeScoutAgent(BaseAgent):
    """Research and knowledge retrieval specialist."""

    def get_temperature(self) -> float:
        """Knowledge scout is exploratory."""
        return 0.7

    async def execute(
        self,
        query: str,
        context: str,
        resolved_tools: Dict[str, Any],
        agent_response: str = ""
    ) -> AgentOutput:
        """Execute knowledge scout logic."""
        try:
            logger.info(f"Knowledge Scout processing: {query[:60]}...")

            response = await self.process_with_tools(query)
            tools_used = [t.name for t in self.tools] if self.tools else []

            return AgentOutput(
                content=response,
                toolsused=tools_used,
                metadata={"context": context},
            )
        except Exception as e:
            logger.error(f"Knowledge Scout error: {e}", exc_info=True)
            return AgentOutput(
                content=f"Error: {str(e)}",
                reasoning=str(e),
            )
