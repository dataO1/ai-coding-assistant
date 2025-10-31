import asyncio
from typing import Dict, Any, List

from langchain.prompts import ChatPromptTemplate

from .base import BaseAgent, AgentOutput, AgentManifest

logger_module = __import__('..utils', fromlist=['get_logger'])
logger = logger_module.get_logger(__name__)

class SupervisorAgent(BaseAgent):
    """
    Task classification and routing agent.

    Analyzes queries to determine which specialist agent should handle them.
    Classifies tasks as: CODE_TASK, RESEARCH_TASK, or HYBRID_TASK
    """

    def _get_temperature(self) -> float:
        """Supervisor should be deterministic"""
        return 0.0

    async def _execute(
        self,
        query: str,
        context: str,
        resolved_tools: Dict[str, Any],
    ) -> AgentOutput:
        """Classify the task"""

        prompt = self.create_prompt(self.manifest.systemPrompt)
        chain = prompt | self.llm

        logger.info(f"Classifying query: {query[:60]}...")

        # Run in thread pool to avoid blocking
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: chain.invoke({"input": query})
        )

        response_text = response.content

        # Parse classification
        classification = self._parse_classification(response_text)
        reasoning = self._parse_reasoning(response_text)

        logger.info(f"Classification: {classification}")
        logger.info(f"Reasoning: {reasoning}")

        return AgentOutput(
            content=response_text,
            tools_used=resolved_tools["resolved"],
            reasoning=reasoning,
            metadata={
                "classification": classification,
            }
        )

    def _parse_classification(self, response: str) -> str:
        """Extract classification from response"""
        for line in response.split("\n"):
            if "CLASSIFICATION:" in line:
                try:
                    classification = line.split("CLASSIFICATION:")[1].strip().split()[0]
                    return classification
                except (IndexError, AttributeError):
                    pass
        return "CODE_TASK"  # Default fallback

    def _parse_reasoning(self, response: str) -> str:
        """Extract reasoning from response"""
        for line in response.split("\n"):
            if "REASONING:" in line:
                try:
                    return line.split("REASONING:")[1].strip()
                except IndexError:
                    pass
        return ""
