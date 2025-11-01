import asyncio
from typing import Dict, Any, List

from langchain.prompts import ChatPromptTemplate

from .base import BaseAgent, AgentOutput, AgentManifest
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)


class SupervisorAgent(BaseAgent):
    """Task classifier - routes queries to appropriate specialist agents.

    Supervisors typically don't need external tools for classification.
    """

    def get_temperature(self) -> float:
        """Supervisor should be deterministic."""
        return 0.0

    async def execute(
        self, query: str, context: str, resolved_tools: Dict[str, Any]
    ) -> AgentOutput:
        """Classify the task."""
        try:
            prompt = self.create_prompt(self.manifest.systemPrompt)

            logger.info(f"Classifying query: {query[:60]}...")

            # No tools needed for supervisor - use LLM directly
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.llm.invoke(
                    prompt.format_messages(input=query)
                ),
            )

            response_text = response.content
            classification = self.parse_classification(response_text)
            reasoning = self.parse_reasoning(response_text)

            logger.info(f"Classification: {classification}")

            return AgentOutput(
                content=classification,
                reasoning=reasoning,
                metadata={"raw_response": response_text},
            )
        except Exception as e:
            logger.error(f"Supervisor error: {e}", exc_info=True)
            return AgentOutput(
                content="ERROR",
                reasoning=str(e),
            )

    def parse_classification(self, response: str) -> str:
        """Parse classification from response."""
        if "CODE_TASK" in response.upper():
            return "CODE_TASK"
        elif "RESEARCH_TASK" in response.upper():
            return "RESEARCH_TASK"
        elif "HYBRID_TASK" in response.upper():
            return "HYBRID_TASK"
        return response.split("\n")[0][:50]

    def parse_reasoning(self, response: str) -> str:
        """Parse reasoning from response."""
        lines = response.split("\n")
        return "\n".join(lines[1:]) if len(lines) > 1 else response
