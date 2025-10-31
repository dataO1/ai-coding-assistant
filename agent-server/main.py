# /etc/ai-agent/runtime/server.py

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from langchain_community.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain_mcp import MCPToolkit
from langgraph.graph import StateGraph, START, END
from langgraph.types import StateSnapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Pipeline Definition
# ============================================================================

class ToolRequirement(BaseModel):
    """Define tool requirements for a pipeline"""
    required: List[str] = Field(default_factory=list, description="Must be available")
    optional: List[str] = Field(default_factory=list, description="Nice-to-have")
    fallback_mode: str = Field(default="degrade", description="degrade|fail")

class PipelineManifest(BaseModel):
    """Runtime pipeline definition"""
    name: str
    description: str
    model: str
    tools: ToolRequirement
    systemPrompt: str
    contexts: List[str] = Field(default=["nvim", "vscode", "shell"])

class PipelineDiscovery:
    """Discover and load pipelines from user config"""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.pipelines: Dict[str, PipelineManifest] = {}
        self._load_pipelines()

    def _load_pipelines(self):
        """Load pipeline definitions from manifests.json"""
        manifest_file = self.config_dir / "manifests.json"

        if not manifest_file.exists():
            logger.warning(f"No manifests found at {manifest_file}")
            return

        try:
            with open(manifest_file) as f:
                data = json.load(f)

            for name, pipeline_data in data.get("pipelines", {}).items():
                manifest = PipelineManifest(
                    name=name,
                    description=pipeline_data.get("description", ""),
                    model=pipeline_data.get("model", ""),
                    systemPrompt=pipeline_data.get("systemPrompt", ""),
                    contexts=pipeline_data.get("contexts", ["nvim", "vscode", "shell"]),
                    tools=ToolRequirement(
                        required=pipeline_data.get("requiredTools", []),
                        optional=pipeline_data.get("optionalTools", []),
                        fallback_mode=pipeline_data.get("fallbackMode", "degrade"),
                    )
                )
                self.pipelines[name] = manifest
                logger.info(f"Discovered pipeline: {name}")
        except Exception as e:
            logger.error(f"Failed to load pipelines: {e}")

    def get_pipeline(self, name: str) -> Optional[PipelineManifest]:
        return self.pipelines.get(name)

    def list_pipelines(self) -> List[PipelineManifest]:
        return list(self.pipelines.values())

# ============================================================================
# Context-Aware Tool Resolution
# ============================================================================

class ContextAwareMCPRegistry:
    """MCP tools with context awareness"""

    def __init__(self, mcp_config: Dict[str, Dict]):
        self.mcp_config = mcp_config
        self.toolkits: Dict[str, MCPToolkit] = {}
        self._init_toolkits()

    def _init_toolkits(self):
        """Initialize MCP toolkits for each context"""
        # TODO: Implement context-specific toolkit initialization
        pass

    def get_tools(
        self,
        tool_names: List[str],
        context: str,  # "nvim", "vscode", "shell"
        required: bool = False
    ) -> List:
        """Get tools, respecting context availability"""
        available_tools = []

        # Determine which tools are available in this context
        context_mcp_map = {
            "nvim": ["nvim-mcp", "lsp", "tree-sitter", "filesystem", "git"],
            "vscode": ["continue-mcp", "lsp", "filesystem", "git"],
            "shell": ["filesystem", "git", "web-search"],
        }

        available = context_mcp_map.get(context, [])

        for tool in tool_names:
            if tool in available:
                available_tools.append(tool)
            elif required:
                raise ValueError(f"Required tool '{tool}' not available in context '{context}'")

        return available_tools

    def resolve_tools(
        self,
        manifest: PipelineManifest,
        context: str
    ) -> List:
        """Resolve tools with fallback support"""
        try:
            # Try to get required tools
            required = self.get_tools(manifest.tools.required, context, required=True)
            logger.info(f"Resolved required tools: {required}")
        except ValueError as e:
            if manifest.tools.fallback_mode == "fail":
                raise
            logger.warning(f"Required tools missing, degrading: {e}")
            required = []

        # Try to get optional tools (non-fatal if missing)
        optional = []
        try:
            optional = self.get_tools(manifest.tools.optional, context, required=False)
        except:
            pass

        logger.info(f"Resolved optional tools: {optional}")
        return required + optional

# ============================================================================
# LangGraph-Based Pipeline Executor
# ============================================================================

class PipelineExecutor:
    """Execute pipelines with LangGraph for state management"""

    def __init__(
        self,
        manifest: PipelineManifest,
        mcp_registry: ContextAwareMCPRegistry,
        ollama_url: str,
    ):
        self.manifest = manifest
        self.mcp_registry = mcp_registry
        self.ollama_url = ollama_url
        self.llm = ChatOllama(
            model=manifest.model,
            base_url=ollama_url,
            temperature=0.2,
        )

    def create_graph(self, context: str):
        """Create a LangGraph state machine for this pipeline"""

        # Resolve tools based on context
        tools = self.mcp_registry.resolve_tools(self.manifest, context)

        # Create graph
        graph_builder = StateGraph(dict)

        # Define processing node
        def process(state: dict) -> dict:
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.manifest.systemPrompt),
                ("human", "{input}"),
            ])

            chain = prompt | self.llm
            result = chain.invoke({"input": state["input"]})

            return {
                **state,
                "output": result.content,
                "tools_used": [t.name for t in tools],
            }

        graph_builder.add_node("process", process)
        graph_builder.add_edge(START, "process")
        graph_builder.add_edge("process", END)

        return graph_builder.compile()

    async def execute(self, query: str, context: str) -> Dict[str, Any]:
        """Execute pipeline with given query and context"""
        logger.info(f"Executing pipeline '{self.manifest.name}' in context '{context}'")

        graph = self.create_graph(context)

        result = await asyncio.to_thread(
            graph.invoke,
            {"input": query}
        )

        return result

# ============================================================================
# FastAPI Server
# ============================================================================

config_dir = Path.home() / ".config" / "ai-agent"
pipeline_discovery = PipelineDiscovery(config_dir)
mcp_registry = ContextAwareMCPRegistry({})

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Agent Server with runtime pipeline discovery")
    yield
    logger.info("Shutting down")

app = FastAPI(
    title="AI Agent Runtime",
    description="LangChain + LangGraph + MCP with context awareness",
    lifespan=lifespan,
)

class QueryRequest(BaseModel):
    pipeline: str
    query: str
    context: str = "shell"

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "pipelines": len(pipeline_discovery.list_pipelines()),
    }

@app.get("/api/pipelines")
async def list_pipelines():
    """List all available pipelines"""
    return [
        {
            "name": p.name,
            "description": p.description,
            "model": p.model,
            "contexts": p.contexts,
        }
        for p in pipeline_discovery.list_pipelines()
    ]

@app.post("/api/query")
async def query(request: QueryRequest):
    """Query a pipeline with context awareness"""
    manifest = pipeline_discovery.get_pipeline(request.pipeline)

    if not manifest:
        raise HTTPException(status_code=404, detail=f"Pipeline '{request.pipeline}' not found")

    # Check if pipeline supports this context
    if request.context not in manifest.contexts:
        raise HTTPException(
            status_code=400,
            detail=f"Pipeline '{request.pipeline}' doesn't support context '{request.context}'"
        )

    try:
        executor = PipelineExecutor(
            manifest,
            mcp_registry,
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

        result = await executor.execute(request.query, request.context)

        return {
            "pipeline": request.pipeline,
            "context": request.context,
            "query": request.query,
            "response": result.get("output"),
            "tools_used": result.get("tools_used", []),
        }
    except Exception as e:
        logger.error(f"Error executing pipeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("AGENT_SERVER_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
