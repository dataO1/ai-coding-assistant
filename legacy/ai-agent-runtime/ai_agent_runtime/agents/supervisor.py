# ai_agent_runtime/agents/supervisor.py
from typing import Dict, Any
from .base import BaseAgent, AgentOutput
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)


class SupervisorAgent(BaseAgent):
    """Task classifier - routes queries to specialist agents."""

    def get_temperature(self) -> float:
        """Supervisor should be deterministic."""
        return 0.0

    async def execute(
        self,
        query: str,
        context: str,
        resolved_tools: Dict[str, Any],
        agent_response: str = ""
    ) -> AgentOutput:
        """Classify the task."""
        try:
            logger.info(f"Classifying query: {query[:60]}...")

            response = await self.process_with_tools(query)

            # Extract classification
            if "CODE_TASK" in response:
                classification = "CODE_TASK"
            elif "RESEARCH_TASK" in response:
                classification = "RESEARCH_TASK"
            elif "HYBRID_TASK" in response:
                classification = "HYBRID_TASK"
            else:
                classification = "CODE_TASK"

            logger.info(f"Classification: {classification}")

            return AgentOutput(
                content=classification,
                reasoning=response,
                metadata={"context": context},
            )

        except Exception as e:
            logger.error(f"Supervisor error: {e}", exc_info=True)
            return AgentOutput(
                content="CODE_TASK",
                reasoning=f"Error: {str(e)}",
            )
