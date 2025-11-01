import asyncio
import logging
from typing import Dict, Any
from dataclasses import dataclass, field
from langgraph.graph import StateGraph, START, END
from ai_agent_runtime.agents import AgentManifest, SupervisorAgent, CodeExpertAgent, KnowledgeScoutAgent
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)

@dataclass
class OrchestratorState:
    query: str
    context: str = "shell"
    classification: str = ""
    classificationreasoning: str = ""
    codeexpertresult: str = ""
    knowledgeresult: str = ""
    finalresponse: str = ""
    toolsused: list = field(default_factory=list)
    executionpath: list = field(default_factory=list)
    errors: list = field(default_factory=list)

class MultiAgentOrchestrator:
    def __init__(self, ollamaurl: str, pipelinemanifests: Dict[str, Dict[str, Any]]):
        self.ollamaurl = ollamaurl
        self.pipelinemanifests = pipelinemanifests
        self.agents = self.initializeagents()
        logger.info(f"Initialized orchestrator with agents: {list(self.agents.keys())}")

    def initializeagents(self) -> Dict[str, Any]:
        agents = {}
        supervisormanifest = self.pipelinemanifests.get("supervisor")
        if supervisormanifest:
            agents["supervisor"] = SupervisorAgent(manifest=AgentManifest(**supervisormanifest), ollama_url=self.ollamaurl)
        codemanifest = self.pipelinemanifests.get("code-expert")
        if codemanifest:
            agents["codeexpert"] = CodeExpertAgent(manifest=AgentManifest(**codemanifest), ollama_url=self.ollamaurl)
        knowledgemanifest = self.pipelinemanifests.get("knowledge-scout")
        if knowledgemanifest:
            agents["knowledgescout"] = KnowledgeScoutAgent(manifest=AgentManifest(**knowledgemanifest), ollama_url=self.ollamaurl)
        if not agents:
            logger.warning("No agents initialized from manifests")
        return agents

    async def classifytask(self, state: OrchestratorState) -> OrchestratorState:
        # Calls supervisor asynchronously and updates state accordingly
        supervisor: SupervisorAgent = self.agents["supervisor"]
        output = await supervisor._execute(state.query, state.context, {})
        state.classification = output.content
        # Assume reasoning parsing done inside
        state.classificationreasoning = output.reasoning
        return state

    async def executecodeexpert(self, state: OrchestratorState) -> OrchestratorState:
        agent: CodeExpertAgent = self.agents["codeexpert"]
        output = await agent._execute(state.query, state.context, {})
        state.codeexpertresult = output.content
        return state

    async def executeknowledgescout(self, state: OrchestratorState) -> OrchestratorState:
        agent: KnowledgeScoutAgent = self.agents["knowledgescout"]
        output = await agent._execute(state.query, state.context, {})
        state.knowledgeresult = output.content
        return state

    def composeresponse(self, state: OrchestratorState) -> OrchestratorState:
        # Synchronous composition (could be async if needed)
        state.finalresponse = (
            f"Classification: {state.classification}\n"
            f"Code Expert Result: {state.codeexpertresult}\n"
            f"Knowledge Scout Result: {state.knowledgeresult}"
        )
        return state

    async def classifynodewrapper(self, statedict):
        state = OrchestratorState(**statedict)
        result = await self.classifytask(state)
        return result.__dict__

    async def codenodewrapper(self, statedict):
        state = OrchestratorState(**statedict)
        result = await self.executecodeexpert(state)
        return result.__dict__

    async def knowledgenodewrapper(self, statedict):
        state = OrchestratorState(**statedict)
        result = await self.executeknowledgescout(state)
        return result.__dict__

    def composenodewrapper(self, statedict):
        state = OrchestratorState(**statedict)
        result = self.composeresponse(state)
        return result.__dict__

    def routeafterclassification(self, state: OrchestratorState):
        # Simplified routing example
        if state.classification.lower() == "codetask":
            return "codeexpert"
        elif state.classification.lower() == "researtask":
            return "knowledgescout"
        else:
            return "compose"

    def buildgraph(self) -> StateGraph:
        graphbuilder = StateGraph[dict]()
        graphbuilder.add_node("classify", self.classifynodewrapper)
        graphbuilder.add_node("codeexpert", self.codenodewrapper)
        graphbuilder.add_node("knowledgescout", self.knowledgenodewrapper)
        graphbuilder.add_node("compose", self.composenodewrapper)

        graphbuilder.add_edge(START, "classify")

        graphbuilder.add_conditional_edges(
            "classify",
            lambda state: [self.routeafterclassification(OrchestratorState(**state))],
            ["codeexpert", "knowledgescout", "compose"]
         )

        graphbuilder.add_edge("codeexpert", "compose")
        graphbuilder.add_edge("knowledgescout", "compose")
        graphbuilder.add_edge("compose", END)
        return graphbuilder.compile()

    async def execute(self, query: str, context: str = "shell") -> Dict[str, Any]:
        logger.info(f"Starting orchestration query={query[:50]}, context={context}")
        initial_state = OrchestratorState(query=query, context=context)
        graph = self.buildgraph()

        try:
            # Async LangGraph pipeline execution
            result = await graph.ainvoke(initial_state.__dict__)
            logger.info(f"Orchestration complete. Execution path: {result.get_execution_path()}")
            return {
                "query": query,
                "context": context,
                "response": result.get_final_response() or "No response generated.",
                "classification": result.get_classification(),
                "toolsused": list(set(result.get_tools_used())),
                "executionpath": result.get_execution_path(),
                "errors": result.get_errors(),
            }
        except Exception as e:
            logger.error(f"Orchestration error: {e}", exc_info=True)
            return {
                "query": query,
                "context": context,
                "response": f"Error: {str(e)}",
                "classification": "",
                "toolsused": [],
                "executionpath": [],
                "errors": [str(e)],
            }
