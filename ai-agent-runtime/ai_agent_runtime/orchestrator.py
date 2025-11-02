from pydantic import BaseModel, Field
from typing import Dict, Any
from dataclasses import dataclass, fields
from langgraph.graph import StateGraph, START, END
from ai_agent_runtime.agents import AgentManifest, SupervisorAgent, CodeExpertAgent, KnowledgeScoutAgent
from ai_agent_runtime.utils import get_logger
from ai_agent_runtime.agents import AgentOutput
from ai_agent_runtime.context import AgentContext

logger = get_logger(__name__)


class OrchestratorState(BaseModel):
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

    class Config:
        frozen = False

    def update(self,source: AgentOutput ):
        # Update only common fields
        target = self
        common_fields = set(source.model_fields) & set(target.model_fields)
        updates = {field: getattr(source, field) for field in common_fields}
        target = target.model_copy(update=updates)


class MultiAgentOrchestrator:
    def __init__(self, ollamaurl: str, pipelinemanifests: Dict[str, Dict[str, Any]]):
        self.ollamaurl = ollamaurl
        self.pipelinemanifests = pipelinemanifests
        self.agents = self.initializeagents()
        self.graph = self.buildgraph()
        logger.info(f"Initialized orchestrator with agents: {list(self.agents.keys())}")

    def initializeagents(self) -> Dict[str, Any]:
        agents = {}
        supervisormanifest = self.pipelinemanifests.get("supervisor")
        if supervisormanifest:
            agents["supervisor"] = SupervisorAgent(
                manifest=AgentManifest(**supervisormanifest),
                ollama_url=self.ollamaurl
            )
        codemanifest = self.pipelinemanifests.get("code-expert")
        if codemanifest:
            agents["codeexpert"] = CodeExpertAgent(
                manifest=AgentManifest(**codemanifest),
                ollama_url=self.ollamaurl
            )
        knowledgemanifest = self.pipelinemanifests.get("knowledge-scout")
        if knowledgemanifest:
            agents["knowledgescout"] = KnowledgeScoutAgent(
                manifest=AgentManifest(**knowledgemanifest),
                ollama_url=self.ollamaurl
            )
        if not agents:
            logger.warning("No agents initialized from manifests")
        return agents

    async def classifytask(self, state: OrchestratorState) -> OrchestratorState:
        try:
            supervisor: SupervisorAgent = self.agents["supervisor"]
            output = await supervisor.process(state.query, state.context)

            state.classification = output.content
            state.classificationreasoning = output.reasoning
            state.update(output)
            state.executionpath.append("classify")

            logger.info(f"Classification: {state.classification}")
            return state
        except Exception as e:
            logger.error(f"Classification error: {e}", exc_info=True)
            return state

    async def executecodeexpert(self,state: OrchestratorState) -> OrchestratorState:
        try:
            agent: CodeExpertAgent = self.agents["codeexpert"]
            output = await agent.process(state.query, state.context)

            state.codeexpertresult = output.content
            state.update(output)
            state.executionpath.append("codeexpert")

            return state
        except Exception as e:
            logger.error(f"Code expert error: {e}", exc_info=True)
            return state

    async def executeknowledgescout(self, state: OrchestratorState) -> OrchestratorState:
        try:
            agent: KnowledgeScoutAgent = self.agents["knowledgescout"]
            output = await agent.process(state.query, state.context)

            state.knowledgeresult = output.content
            state.update(output)
            state.executionpath.append("knowledgescout")

            return state
        except Exception as e:
            logger.error(f"Knowledge scout error: {e}", exc_info=True)
            return state

    def composeresponse(self, state: OrchestratorState) -> OrchestratorState:
        response_parts = []
        if state.classification:
            response_parts.append(f"Classification: {state.classification}")
        if state.codeexpertresult:
            response_parts.append(f"Code Expert: {state.codeexpertresult}")
        if state.knowledgeresult:
            response_parts.append(f"Knowledge Scout: {state.knowledgeresult}")

        state.finalresponse = "\n".join(response_parts) if response_parts else "No response generated."
        state.executionpath.append("compose")

        return state

    def route_on_classification(self, state: OrchestratorState) -> str:
        """Route based on classification in executionpath logic."""
        classification = state.classification.lower()

        if "code" in classification:
            return "codeexpert"
        elif "research" in classification or "knowledge" in classification:
            return "knowledgescout"
        else:
            return "compose"

    def buildgraph(self):
        """Build fixed state graph."""
        graphbuilder = StateGraph(OrchestratorState)

        graphbuilder.add_node("classify", self.classifytask)
        graphbuilder.add_node("codeexpert", self.executecodeexpert)
        graphbuilder.add_node("knowledgescout", self.executeknowledgescout)
        graphbuilder.add_node("compose", self.composeresponse)

        graphbuilder.add_edge(START, "classify")
        graphbuilder.add_conditional_edges(
            "classify",
            self.route_on_classification,
            {
                "codeexpert": "codeexpert",
                "knowledgescout": "knowledgescout",
                "compose": "compose",
            }
        )
        graphbuilder.add_edge("codeexpert", "compose")
        graphbuilder.add_edge("knowledgescout", "compose")
        graphbuilder.add_edge("compose", END)

        return graphbuilder.compile()

    async def execute(
        self,
        query: str,
        context: AgentContext  # Changed from str to AgentContext
    ) -> Dict[str, Any]:
        """Execute query through multi-agent pipeline with context awareness."""

        logger.info(
            f"Starting orchestration for query={query[:60]}, "
            f"context={context.source.value if isinstance(context, AgentContext) else context}"
        )

        state = OrchestratorState(
            query=query,
            context=context.source.value if isinstance(context, AgentContext) else str(context),
        )

        # Supervisor classification
        supervisor_result = await self.supervisor.process(query, context)
        classification = supervisor_result.content

        state.update(AgentOutput(
            content=classification,
            reasoning=supervisor_result.reasoning,
        ))
        state.executionpath.append("classify")

        # Route to specialist agent based on classification
        specialist_agent = self._route_to_specialist(classification)

        if specialist_agent:
            specialist_result = await specialist_agent.process(query, context)  # Pass context
            state.update(specialist_result)
            state.executionpath.append(specialist_agent.manifest.name)

        logger.info(f"Orchestration complete. Path: {state.executionpath}")

        return {
            "response": state.finalresponse,
            "classification": state.classification,
            "tools_used": state.toolsused,
            "execution_path": state.executionpath,
        }
