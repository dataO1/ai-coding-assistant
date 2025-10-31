import asyncio
from typing import Dict, Any

from .base import BaseAgent, AgentOutput
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)

class KnowledgeScoutAgent(BaseAgent):
    """Research and learning specialist agent..."""

    # ... rest of code

class KnowledgeScoutAgent(BaseAgent):
    """
    Research and learning specialist agent.

    Specializes in:
    - Explaining concepts and patterns
    - Documentation and best practices
    - Technology research and recommendations
    - Learning resources and tutorials

    Provides nuanced, well-structured explanations with examples.
    """

    def _get_temperature(self) -> float:
        """Slightly higher temperature for nuanced explanations"""
        return 0.3

    async def _execute(
        self,
        query: str,
        context: str,
        resolved_tools: Dict[str, Any],
    ) -> AgentOutput:
        """Execute knowledge scout agent"""

        tools_info = self.format_tools_info(resolved_tools)

        system_prompt = f"""{self.manifest.systemPrompt}

AVAILABLE TOOLS:
{tools_info}

CONTEXT: {context}

Structure your response as:
1. Definition/Overview
2. Key concepts
3. Practical examples (if relevant)
4. Best practices
5. Resources for deeper learning

Be thorough but concise.
"""

        prompt = self.create_prompt(system_prompt)
        chain = prompt | self.llm

        logger.info(f"Knowledge scout processing: {query[:60]}...")

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: chain.invoke({"input": query})
        )

        logger.debug(f"Knowledge scout response length: {len(response.content)}")

        return AgentOutput(
            content=response.content,
            tools_used=resolved_tools["resolved"],
            metadata={
                "agent_type": "knowledge_scout",
                "context": context,
            }
        )
