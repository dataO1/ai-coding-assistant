# ai_agent_runtime/orchestrator.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from ai_agent_runtime.agents import (
    AgentManifest,
    SupervisorAgent,
    CodeExpertAgent,
    KnowledgeScoutAgent,
    AgentOutput
)
from ai_agent_runtime.utils import get_logger
from ai_agent_runtime.context import AgentContext

logger = get_logger(__name__)


class OrchestratorState(BaseModel):
    """State passed through the orchestration graph."""
    query: str = ""
    context: str = "shell"
    classification: str = ""
    classificationreasoning: str = ""
    codeexpertresult: str = ""
    knowledgeresult: str = ""
    finalresponse: str = ""
    toolsused: list = Field(default_factory=list)
    executionpath: list = Field(default_factory=list)
    errors: list = Field(default_factory=list)
    agent_context: Optional[AgentContext] = None  # NEW: Store AgentContext in state

    class Config:
        frozen = False
        arbitrary_types_allowed = True  # Allow AgentContext

    def update(self, source: AgentOutput):
        """Update state with AgentOutput fields."""
        # Update common fields
        common_fields = {"content", "toolsused", "reasoning"}

        if "content" in common_fields and source.content:
            # Don't overwrite finalresponse yet, let compose handle it
            pass

        if source.toolsused:
            self.toolsused.extend(source.toolsused)

        if source.reasoning and not self.classificationreasoning:
            self.classificationreasoning = source.reasoning


class MultiAgentOrchestrator:
    """Multi-agent orchestrator that routes queries to specialist agents."""

    def __init__(self, ollama_url: str, pipeline_manifests: Dict[str, Dict[str, Any]]):
        self.ollama_url = ollama_url
        self.pipeline_manifests = pipeline_manifests
        self.agents = self._initialize_agents()
        self.graph = self._build_graph()
        logger.info(f"Initialized orchestrator with agents: {list(self.agents.keys())}")

    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize all agents from manifests."""
        agents = {}

        # Supervisor agent
        supervisor_manifest = self.pipeline_manifests.get("supervisor")
        if supervisor_manifest:
            agents["supervisor"] = SupervisorAgent(
                manifest=AgentManifest(**supervisor_manifest),
                ollama_url=self.ollama_url
            )

        # Code expert agent
        code_manifest = self.pipeline_manifests.get("code-expert")
        if code_manifest:
            agents["codeexpert"] = CodeExpertAgent(
                manifest=AgentManifest(**code_manifest),
                ollama_url=self.ollama_url
            )

        # Knowledge scout agent
        knowledge_manifest = self.pipeline_manifests.get("knowledge-scout")
        if knowledge_manifest:
            agents["knowledgescout"] = KnowledgeScoutAgent(
                manifest=AgentManifest(**knowledge_manifest),
                ollama_url=self.ollama_url
            )

        if not agents:
            logger.warning("No agents initialized from manifests")

        return agents

    async def _classify_task(self, state: OrchestratorState) -> OrchestratorState:
        """Classify the task using supervisor agent."""
        try:
            if "supervisor" not in self.agents:
                logger.error("Supervisor agent not initialized")
                state.errors.append("Supervisor agent not found")
                return state

            supervisor: SupervisorAgent = self.agents["supervisor"]
            output = await supervisor.process(
                state.query,
                state.agent_context
            )

            state.classification = output.content
            state.classificationreasoning = output.reasoning
            state.update(output)
            state.executionpath.append("classify")

            logger.info(f"Classification: {state.classification}")
            return state

        except Exception as e:
            logger.error(f"Classification error: {e}", exc_info=True)
            state.errors.append(f"Classification error: {str(e)}")
            return state

    async def _execute_code_expert(self, state: OrchestratorState) -> OrchestratorState:
        """Execute code expert agent."""
        try:
            if "codeexpert" not in self.agents:
                logger.error("Code expert agent not initialized")
                state.errors.append("Code expert agent not found")
                return state

            agent: CodeExpertAgent = self.agents["codeexpert"]
            output = await agent.process(
                state.query,
                state.agent_context
            )

            state.codeexpertresult = output.content
            state.update(output)
            state.executionpath.append("codeexpert")

            return state

        except Exception as e:
            logger.error(f"Code expert error: {e}", exc_info=True)
            state.errors.append(f"Code expert error: {str(e)}")
            return state

    async def _execute_knowledge_scout(self, state: OrchestratorState) -> OrchestratorState:
        """Execute knowledge scout agent."""
        try:
            if "knowledgescout" not in self.agents:
                logger.error("Knowledge scout agent not initialized")
                state.errors.append("Knowledge scout agent not found")
                return state

            agent: KnowledgeScoutAgent = self.agents["knowledgescout"]
            output = await agent.process(
                state.query,
                state.agent_context
            )

            state.knowledgeresult = output.content
            state.update(output)
            state.executionpath.append("knowledgescout")

            return state

        except Exception as e:
            logger.error(f"Knowledge scout error: {e}", exc_info=True)
            state.errors.append(f"Knowledge scout error: {str(e)}")
            return state

    def _compose_response(self, state: OrchestratorState) -> OrchestratorState:
        """Compose final response from agent results."""
        response_parts = []

        if state.classification:
            response_parts.append(f"**Classification**: {state.classification}")

        if state.classificationreasoning:
            response_parts.append(f"**Reasoning**: {state.classificationreasoning}")

        if state.codeexpertresult:
            response_parts.append(f"**Code Solution**:\n{state.codeexpertresult}")

        if state.knowledgeresult:
            response_parts.append(f"**Knowledge**:\n{state.knowledgeresult}")

        if state.errors:
            response_parts.append(f"**Errors**: {'; '.join(state.errors)}")

        state.finalresponse = (
            "\n\n".join(response_parts) if response_parts else "No response generated."
        )
        state.executionpath.append("compose")

        return state

    def _route_on_classification(self, state: OrchestratorState) -> str:
        """Route to specialist agent based on classification."""
        classification = state.classification.lower()

        if "code" in classification:
            return "codeexpert"
        elif "research" in classification or "knowledge" in classification:
            return "knowledgescout"
        else:
            return "compose"

    def _build_graph(self):
        """Build the state graph for orchestration."""
        graph_builder = StateGraph(OrchestratorState)

        # Add nodes for each step
        graph_builder.add_node("classify", self._classify_task)
        graph_builder.add_node("codeexpert", self._execute_code_expert)
        graph_builder.add_node("knowledgescout", self._execute_knowledge_scout)
        graph_builder.add_node("compose", self._compose_response)

        # Add edges
        graph_builder.add_edge(START, "classify")

        # Conditional routing based on classification
        graph_builder.add_conditional_edges(
            "classify",
            self._route_on_classification,
            {
                "codeexpert": "codeexpert",
                "knowledgescout": "knowledgescout",
                "compose": "compose",
            }
        )

        # Both specialist agents route to compose
        graph_builder.add_edge("codeexpert", "compose")
        graph_builder.add_edge("knowledgescout", "compose")

        # Compose routes to end
        graph_builder.add_edge("compose", END)

        return graph_builder.compile()

    async def execute(
        self,
        query: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """Execute query through multi-agent pipeline with context awareness.

        Args:
            query: User query
            context: AgentContext with source and working directory

        Returns:
            Dict with response, classification, tools used, and execution path
        """
        logger.info(
            f"Starting orchestration for query={query[:60]}, "
            f"context={context.source.value}"
        )

        # Initialize state with context
        state = OrchestratorState(
            query=query,
            context=context.source.value,
            agent_context=context,  # Store full context in state
        )

        try:
            # Run the graph
            final_state = await self.graph.ainvoke(state)

            # logger.info(
            #     f"Orchestration complete. Path: {final_state.executionpath}"
            # )

            return final_state

        except Exception as e:
            logger.error(f"Orchestration error: {e}", exc_info=True)
            return final_state
