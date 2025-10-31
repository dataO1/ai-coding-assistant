import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, START, END
from langgraph.types import StateSnapshot

# ai-agent-runtime/ai_agent_runtime/orchestrator.py

from ai_agent_runtime.agents import (
    AgentManifest,
    AgentOutput,
    SupervisorAgent,
    CodeExpertAgent,
    KnowledgeScoutAgent,
)
from ai_agent_runtime.utils import get_logger

logger = get_logger(__name__)

# ============================================================================
# State Management
# ============================================================================

@dataclass
class OrchestratorState:
    """State maintained throughout orchestration"""

    # Input
    query: str
    context: str  # "nvim", "vscode", "shell", "web"

    # Routing
    classification: Optional[str] = None
    classification_reasoning: str = ""

    # Execution
    code_expert_result: str = ""
    knowledge_result: str = ""

    # Metadata
    final_response: str = ""
    tools_used: List[str] = field(default_factory=list)
    execution_path: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

# ============================================================================
# Multi-Agent Orchestrator
# ============================================================================

class MultiAgentOrchestrator:
    """
    Orchestrates multiple specialized agents using LangGraph state machine.

    Flow:
    1. Supervisor classifies the task
    2. Routes to appropriate agent(s):
       - CODE_TASK → CodeExpert
       - RESEARCH_TASK → KnowledgeScout
       - HYBRID_TASK → Both (sequential)
    3. Composes final response from agent outputs
    """

    def __init__(
        self,
        ollama_url: str,
        pipeline_manifests: Dict[str, Dict[str, Any]],
    ):
        self.ollama_url = ollama_url
        self.pipeline_manifests = pipeline_manifests

        # Initialize agents
        self.agents = self._initialize_agents()

        logger.info(f"Initialized orchestrator with {len(self.agents)} agents")

    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize all specialized agents from manifests"""
        agents = {}

        # Supervisor (always needed)
        supervisor_manifest = self.pipeline_manifests.get("supervisor")
        if supervisor_manifest:
            agents["supervisor"] = SupervisorAgent(
                manifest=AgentManifest(**supervisor_manifest),
                ollama_url=self.ollama_url,
            )

        # Code Expert
        code_manifest = self.pipeline_manifests.get("code-expert")
        if code_manifest:
            agents["code_expert"] = CodeExpertAgent(
                manifest=AgentManifest(**code_manifest),
                ollama_url=self.ollama_url,
            )

        # Knowledge Scout
        knowledge_manifest = self.pipeline_manifests.get("knowledge-scout")
        if knowledge_manifest:
            agents["knowledge_scout"] = KnowledgeScoutAgent(
                manifest=AgentManifest(**knowledge_manifest),
                ollama_url=self.ollama_url,
            )

        if not agents:
            logger.warning("No agents initialized from manifests")

        return agents

    # ========================================================================
    # Graph Nodes
    # ========================================================================

    async def classify_task(self, state: OrchestratorState) -> OrchestratorState:
        """Node: Classify task using supervisor"""
        logger.info(f"Classifying: {state.query[:50]}...")

        try:
            supervisor = self.agents.get("supervisor")
            if not supervisor:
                logger.error("Supervisor agent not initialized")
                state.errors.append("Supervisor agent not available")
                state.execution_path.append("classify_task (failed)")
                return state

            result = await supervisor.process(state.query, state.context)

            state.classification = result.metadata.get("classification", "CODE_TASK")
            state.classification_reasoning = result.reasoning
            state.tools_used.extend(result.tools_used)
            state.execution_path.append("classify_task")

            logger.info(f"Classification: {state.classification}")

        except Exception as e:
            logger.error(f"Classification error: {e}", exc_info=True)
            state.errors.append(f"Classification error: {str(e)}")
            state.classification = "CODE_TASK"  # Default fallback

        return state

    async def execute_code_expert(self, state: OrchestratorState) -> OrchestratorState:
        """Node: Execute code expert"""
        logger.info("Executing code expert...")

        try:
            agent = self.agents.get("code_expert")
            if not agent:
                logger.warning("Code expert agent not initialized")
                return state

            result = await agent.process(state.query, state.context)
            state.code_expert_result = result.content
            state.tools_used.extend(result.tools_used)
            state.execution_path.append("code_expert")

        except Exception as e:
            logger.error(f"Code expert error: {e}", exc_info=True)
            state.errors.append(f"Code expert error: {str(e)}")

        return state

    async def execute_knowledge_scout(self, state: OrchestratorState) -> OrchestratorState:
        """Node: Execute knowledge scout"""
        logger.info("Executing knowledge scout...")

        try:
            agent = self.agents.get("knowledge_scout")
            if not agent:
                logger.warning("Knowledge scout agent not initialized")
                return state

            result = await agent.process(state.query, state.context)
            state.knowledge_result = result.content
            state.tools_used.extend(result.tools_used)
            state.execution_path.append("knowledge_scout")

        except Exception as e:
            logger.error(f"Knowledge scout error: {e}", exc_info=True)
            state.errors.append(f"Knowledge scout error: {str(e)}")

        return state

    def compose_response(self, state: OrchestratorState) -> OrchestratorState:
        """Node: Compose final response"""
        logger.info("Composing response...")

        # Determine what we have
        has_code = bool(state.code_expert_result)
        has_knowledge = bool(state.knowledge_result)

        if has_code and has_knowledge:
            # Hybrid response
            state.final_response = f"""**CODE SOLUTION:**

{state.code_expert_result}

---

**CONTEXT & EXPLANATION:**

{state.knowledge_result}

---

**Metadata:**
- Classification: {state.classification}
- Tools used: {', '.join(set(state.tools_used)) or 'none'}
- Execution path: {' → '.join(state.execution_path)}
""".strip()
        elif has_code:
            state.final_response = state.code_expert_result
        elif has_knowledge:
            state.final_response = state.knowledge_result
        else:
            state.final_response = "Unable to generate response. Please try again."

        state.execution_path.append("compose_response")

        return state

    # ========================================================================
    # Routing Logic
    # ========================================================================

    def route_after_classification(self, state: OrchestratorState) -> str:
        """Determine which agents to execute based on classification"""
        classification = state.classification or "CODE_TASK"

        if classification == "HYBRID_TASK":
            return "hybrid"
        elif classification == "RESEARCH_TASK":
            return "research"
        else:  # CODE_TASK or default
            return "code"

    # ========================================================================
    # Graph Construction
    # ========================================================================

    def build_graph(self):
        """Build the LangGraph state machine"""

        # Create async versions of nodes for use with executor
        async def classify_node_wrapper(state_dict):
            state = OrchestratorState(**state_dict)
            result = await self.classify_task(state)
            return result.__dict__

        async def code_node_wrapper(state_dict):
            state = OrchestratorState(**state_dict)
            result = await self.execute_code_expert(state)
            return result.__dict__

        async def knowledge_node_wrapper(state_dict):
            state = OrchestratorState(**state_dict)
            result = await self.execute_knowledge_scout(state)
            return result.__dict__

        def compose_node_wrapper(state_dict):
            state = OrchestratorState(**state_dict)
            result = self.compose_response(state)
            return result.__dict__

        # Build graph
        graph_builder = StateGraph(dict)

        # Add nodes
        graph_builder.add_node("classify", classify_node_wrapper)
        graph_builder.add_node("code_expert", code_node_wrapper)
        graph_builder.add_node("knowledge_scout", knowledge_node_wrapper)
        graph_builder.add_node("compose", compose_node_wrapper)

        # Add edges
        graph_builder.add_edge(START, "classify")

        # Route based on classification
        graph_builder.add_conditional_edges(
            "classify",
            lambda state: self.route_after_classification(OrchestratorState(**state)),
            {
                "code": "code_expert",
                "research": "knowledge_scout",
                "hybrid": "code_expert",
            },
        )

        # From code_expert
        graph_builder.add_edge("code_expert", "compose")

        # From knowledge_scout
        graph_builder.add_edge("knowledge_scout", "compose")

        # Compose to end
        graph_builder.add_edge("compose", END)

        return graph_builder.compile()

    # ========================================================================
    # Execution
    # ========================================================================

    async def execute(
        self,
        query: str,
        context: str = "shell",
    ) -> Dict[str, Any]:
        """Execute the multi-agent orchestration pipeline"""

        logger.info(f"Starting orchestration: query='{query[:50]}...', context='{context}'")

        initial_state = OrchestratorState(query=query, context=context)
        graph = self.build_graph()

        try:
            # Run graph in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: graph.invoke(initial_state.__dict__)
            )

            logger.info(f"Orchestration complete. Path: {result.get('execution_path', [])}")

            return {
                "query": query,
                "context": context,
                "response": result.get("final_response", "No response generated"),
                "classification": result.get("classification", ""),
                "tools_used": list(set(result.get("tools_used", []))),
                "execution_path": result.get("execution_path", []),
                "errors": result.get("errors", []),
            }

        except Exception as e:
            logger.error(f"Orchestration error: {e}", exc_info=True)

            return {
                "query": query,
                "context": context,
                "response": f"Error: {str(e)}",
                "classification": "",
                "tools_used": [],
                "execution_path": [],
                "errors": [str(e)],
            }
