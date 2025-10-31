# /etc/ai-agent/runtime/orchestrator.py
"""
Multi-agent orchestration system using LangGraph for routing and composition
"""

import json
import logging
from typing import Dict, List, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field

from langchain.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain_mcp import MCPToolkit
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

logger = logging.getLogger(__name__)

# ============================================================================
# Types and Enums
# ============================================================================

class TaskClassification(str, Enum):
    CODE_TASK = "CODE_TASK"
    RESEARCH_TASK = "RESEARCH_TASK"
    HYBRID_TASK = "HYBRID_TASK"

class OrchestratorState(BaseModel):
    """State maintained across the orchestration pipeline"""

    # Input
    query: str
    context: str  # "nvim", "vscode", "shell", "web"

    # Routing
    classification: TaskClassification | None = None
    classification_reasoning: str = ""

    # Execution
    code_expert_result: str = ""
    knowledge_result: str = ""

    # Final output
    final_response: str = ""
    tools_used: List[str] = Field(default_factory=list)
    execution_path: List[str] = Field(default_factory=list)

class MultiAgentOrchestrator:
    """Orchestrates multiple specialized agents"""

    def __init__(
        self,
        ollama_url: str,
        mcp_registry,
        pipeline_manifests: Dict[str, Any],
    ):
        self.ollama_url = ollama_url
        self.mcp_registry = mcp_registry
        self.pipeline_manifests = pipeline_manifests

        # Initialize individual agents
        self.supervisor = self._create_supervisor()
        self.code_expert = self._create_code_expert()
        self.knowledge_scout = self._create_knowledge_scout()
        self.refactoring_agent = self._create_refactoring_agent()
        self.debug_agent = self._create_debug_agent()

    # ========================================================================
    # Agent Factories
    # ========================================================================

    def _create_supervisor(self) -> ChatOllama:
        """Create the routing/classification agent"""
        return ChatOllama(
            model="qwen2.5-coder:7b",  # Small model for fast routing
            base_url=self.ollama_url,
            temperature=0.0,  # Deterministic routing
        )

    def _create_code_expert(self) -> ChatOllama:
        """Create code generation/modification agent"""
        return ChatOllama(
            model="qwen2.5-coder:14b",
            base_url=self.ollama_url,
            temperature=0.2,
        )

    def _create_knowledge_scout(self) -> ChatOllama:
        """Create research/learning agent"""
        return ChatOllama(
            model="qwen2.5-coder:70b",  # Larger model for nuanced explanations
            base_url=self.ollama_url,
            temperature=0.3,
        )

    def _create_refactoring_agent(self) -> ChatOllama:
        """Create refactoring specialist"""
        return ChatOllama(
            model="qwen2.5-coder:70b",
            base_url=self.ollama_url,
            temperature=0.2,
        )

    def _create_debug_agent(self) -> ChatOllama:
        """Create debugging specialist"""
        return ChatOllama(
            model="qwen2.5-coder:14b",
            base_url=self.ollama_url,
            temperature=0.1,  # Deterministic for debugging
        )

    # ========================================================================
    # Pipeline Nodes
    # ========================================================================

    def classify_task(self, state: OrchestratorState) -> OrchestratorState:
        """Node: Classify task using supervisor"""
        logger.info(f"Classifying task: {state.query[:50]}...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.pipeline_manifests["supervisor"]["systemPrompt"]),
            ("human", "{query}"),
        ])

        chain = prompt | self.supervisor
        response = chain.invoke({"query": state.query})

        # Parse classification
        response_text = response.content
        lines = response_text.split("\n")

        classification = TaskClassification.CODE_TASK  # Default
        reasoning = ""

        for line in lines:
            if "CLASSIFICATION:" in line:
                try:
                    class_str = line.split("CLASSIFICATION:")[1].strip().split()[0]
                    classification = TaskClassification(class_str)
                except:
                    pass
            elif "REASONING:" in line:
                reasoning = line.split("REASONING:")[1].strip()

        logger.info(f"Classification: {classification.value}")
        logger.info(f"Reasoning: {reasoning}")

        state.classification = classification
        state.classification_reasoning = reasoning
        state.execution_path.append("classify_task")

        return state

    def execute_code_expert(self, state: OrchestratorState) -> OrchestratorState:
        """Node: Execute code expert agent"""
        logger.info("Executing code expert...")

        tools = self.mcp_registry.resolve_tools(
            self.pipeline_manifests["code-expert"],
            state.context
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.pipeline_manifests["code-expert"]["systemPrompt"]),
            ("human", "Query: {query}\n\nContext: {context}\n\nAvailable tools: {tools}"),
        ])

        chain = prompt | self.code_expert
        response = chain.invoke({
            "query": state.query,
            "context": state.context,
            "tools": ", ".join([t.name if hasattr(t, 'name') else str(t) for t in tools]),
        })

        state.code_expert_result = response.content
        state.tools_used.extend([t.name if hasattr(t, 'name') else str(t) for t in tools])
        state.execution_path.append("code_expert")

        return state

    def execute_knowledge_scout(self, state: OrchestratorState) -> OrchestratorState:
        """Node: Execute knowledge scout agent"""
        logger.info("Executing knowledge scout...")

        tools = self.mcp_registry.resolve_tools(
            self.pipeline_manifests["knowledge-scout"],
            state.context
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.pipeline_manifests["knowledge-scout"]["systemPrompt"]),
            ("human", "Query: {query}"),
        ])

        chain = prompt | self.knowledge_scout
        response = chain.invoke({"query": state.query})

        state.knowledge_result = response.content
        state.tools_used.extend([t.name if hasattr(t, 'name') else str(t) for t in tools])
        state.execution_path.append("knowledge_scout")

        return state

    def route_execution(self, state: OrchestratorState) -> Literal["code_only", "research_only", "hybrid", "end"]:
        """Routing logic based on classification"""
        if state.classification == TaskClassification.CODE_TASK:
            return "code_only"
        elif state.classification == TaskClassification.RESEARCH_TASK:
            return "research_only"
        elif state.classification == TaskClassification.HYBRID_TASK:
            return "hybrid"
        else:
            return "end"

    def compose_response(self, state: OrchestratorState) -> OrchestratorState:
        """Node: Compose final response from agent outputs"""
        logger.info("Composing final response...")

        if state.code_expert_result and state.knowledge_result:
            # Hybrid response
            state.final_response = f"""
Based on your query, I've provided both code solutions and context:

**CODE SOLUTION:**
{state.code_expert_result}

**CONTEXT & EXPLANATION:**
{state.knowledge_result}

---
Classification: {state.classification.value}
Tools used: {', '.join(set(state.tools_used))}
Execution path: {' → '.join(state.execution_path)}
            """.strip()
        elif state.code_expert_result:
            state.final_response = state.code_expert_result
        elif state.knowledge_result:
            state.final_response = state.knowledge_result
        else:
            state.final_response = "No response generated"

        state.execution_path.append("compose_response")

        return state

    # ========================================================================
    # Graph Construction
    # ========================================================================

    def build_graph(self):
        """Build the LangGraph state machine"""
        graph_builder = StateGraph(OrchestratorState)

        # Add nodes
        graph_builder.add_node("classify_task", self.classify_task)
        graph_builder.add_node("code_expert", self.execute_code_expert)
        graph_builder.add_node("knowledge_scout", self.execute_knowledge_scout)
        graph_builder.add_node("compose_response", self.compose_response)

        # Add edges with conditional routing
        graph_builder.add_edge(START, "classify_task")

        graph_builder.add_conditional_edges(
            "classify_task",
            self.route_execution,
            {
                "code_only": "code_expert",
                "research_only": "knowledge_scout",
                "hybrid": "code_expert",  # Code expert goes first
                "end": "compose_response",
            },
        )

        # After code expert in hybrid mode, go to knowledge scout
        graph_builder.add_edge("code_expert", "compose_response")

        # Knowledge scout goes directly to compose
        graph_builder.add_edge("knowledge_scout", "compose_response")

        # Compose response goes to end
        graph_builder.add_edge("compose_response", END)

        return graph_builder.compile()

    async def execute(
        self,
        query: str,
        context: str = "shell"
    ) -> Dict[str, Any]:
        """Execute the orchestration pipeline"""
        import asyncio

        logger.info(f"Starting orchestration: query='{query}', context='{context}'")

        initial_state = OrchestratorState(query=query, context=context)
        graph = self.build_graph()

        # Run graph
        result = await asyncio.to_thread(
            graph.invoke,
            initial_state.dict()
        )

        return {
            "query": query,
            "context": context,
            "response": result.get("final_response", ""),
            "classification": result.get("classification", ""),
            "tools_used": result.get("tools_used", []),
            "execution_path": result.get("execution_path", []),
        }
