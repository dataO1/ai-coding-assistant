import os
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from uvicorn import run as uvicorn_run

from langchain.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_mcp import MCPToolkit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration Loading
# ============================================================================

class PipelineConfig(BaseModel):
    name: str
    description: str
    model: str
    tools: List[str]
    systemPrompt: str

class MCPServerConfig(BaseModel):
    name: str
    enabled: bool
    command: str
    args: List[str]

class Config:
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.agent_port = int(os.getenv("AGENT_SERVER_PORT", "8080"))

        # Load pipeline configs from Nix
        models_json = os.getenv("MODELS_CONFIG", "{}")
        self.models = json.loads(models_json)

        mcp_json = os.getenv("MCP_SERVERS_CONFIG", "{}")
        self.mcp_servers = json.loads(mcp_json)

        logger.info(f"Loaded {len(self.models)} models")
        logger.info(f"Loaded {len(self.mcp_servers)} MCP servers")

config = Config()

# ============================================================================
# MCP Toolkit Management
# ============================================================================

class MCPRegistry:
    def __init__(self):
        self.toolkits: Dict[str, MCPToolkit] = {}
        self._init_mcp_servers()

    def _init_mcp_servers(self):
        """Initialize MCP servers from config"""
        mcp_configs = {}

        for name, server_config in config.mcp_servers.items():
            if server_config.get("enabled", True):
                cmd = server_config["command"]
                args = server_config.get("args", [])
                full_cmd = f"{cmd} {' '.join(args)}"
                mcp_configs[name] = full_cmd
                logger.info(f"Registered MCP server: {name}")

        # Initialize toolkit with all servers
        try:
            self.toolkit = MCPToolkit(servers=mcp_configs)
            logger.info("MCPToolkit initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize MCPToolkit: {e}")
            self.toolkit = None

    def get_tools(self, tool_names: List[str]):
        """Get specific tools from toolkit"""
        if not self.toolkit:
            logger.warning("MCPToolkit not available")
            return []

        try:
            all_tools = self.toolkit.get_tools()
            filtered_tools = [t for t in all_tools if any(name in t.name.lower() for name in tool_names)]
            return filtered_tools
        except Exception as e:
            logger.warning(f"Could not get tools: {e}")
            return []

mcp_registry = MCPRegistry()

# ============================================================================
# Pipeline Management
# ============================================================================

class PipelineFactory:
    def __init__(self):
        self.pipelines: Dict[str, AgentExecutor] = {}
        self._build_pipelines()

    def _build_pipelines(self):
        """Build all pipelines from config"""
        for pipeline_name, pipeline_config in config.models.items():
            try:
                self.pipelines[pipeline_name] = self._create_pipeline(
                    pipeline_name, pipeline_config
                )
                logger.info(f"Built pipeline: {pipeline_name}")
            except Exception as e:
                logger.error(f"Failed to build pipeline {pipeline_name}: {e}")

    def _create_pipeline(self, name: str, pipeline_config: Dict[str, Any]) -> AgentExecutor:
        """Create a single pipeline"""
        model_name = pipeline_config.get("model", config.models.get("supervisor", "qwen2.5-coder:7b"))
        tools = pipeline_config.get("tools", [])
        system_prompt = pipeline_config.get("systemPrompt", "You are a helpful AI assistant.")

        # Initialize LLM
        llm = ChatOllama(
            model=model_name,
            base_url=config.ollama_url,
            temperature=0.2,
            top_p=0.9,
        )

        # Get tools
        agent_tools = mcp_registry.get_tools(tools)

        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

        # Create agent
        agent = create_openai_functions_agent(llm, agent_tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=agent_tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10,
        )

        return executor

    def get_pipeline(self, name: str) -> Optional[AgentExecutor]:
        return self.pipelines.get(name)

pipeline_factory = PipelineFactory()

# ============================================================================
# FastAPI Application
# ============================================================================

class QueryRequest(BaseModel):
    pipeline: str = "coding"
    query: str

class QueryResponse(BaseModel):
    pipeline: str
    query: str
    response: str
    model: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting AI Agent Server on port {config.agent_port}")
    yield
    logger.info("Shutting down AI Agent Server")

app = FastAPI(
    title="AI Agent Server",
    description="LangChain-based AI agent with MCP support",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "pipelines": list(pipeline_factory.pipelines.keys()),
        "mcp_servers": list(config.mcp_servers.keys()),
    }

@app.get("/api/pipelines")
async def list_pipelines():
    """List all available pipelines"""
    return [
        {
            "name": name,
            "model": config.models.get(name, {}).get("model", "unknown"),
        }
        for name in pipeline_factory.pipelines.keys()
    ]

@app.post("/api/query")
async def query(request: QueryRequest):
    """Query an agent pipeline"""
    pipeline_name = request.pipeline
    query_text = request.query

    # Get pipeline
    pipeline = pipeline_factory.get_pipeline(pipeline_name)
    if not pipeline:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline '{pipeline_name}' not found"
        )

    try:
        logger.info(f"Processing query on pipeline '{pipeline_name}'")

        # Run agent
        result = await asyncio.to_thread(
            pipeline.invoke,
            {"input": query_text}
        )

        response_text = result.get("output", "No response generated")
        model_name = config.models.get(pipeline_name, {}).get("model", "unknown")

        return QueryResponse(
            pipeline=pipeline_name,
            query=query_text,
            response=response_text,
            model=model_name,
        )
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint (for Continue.dev, Avante)"""
    return {
        "object": "list",
        "data": [
            {
                "id": name,
                "object": "model",
                "created": 0,
                "owned_by": "local",
            }
            for name in pipeline_factory.pipelines.keys()
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    """OpenAI-compatible chat endpoint"""
    pipeline = request.get("model", "coding")
    messages = request.get("messages", [])

    # Extract query from messages
    query_text = messages[-1]["content"] if messages else "Help me"

    # Get pipeline
    agent_pipeline = pipeline_factory.get_pipeline(pipeline)
    if not agent_pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline}' not found")

    try:
        result = await asyncio.to_thread(
            agent_pipeline.invoke,
            {"input": query_text}
        )

        response_text = result.get("output", "No response generated")

        return {
            "id": "local",
            "object": "chat.completion",
            "created": 0,
            "model": pipeline,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        }
    except Exception as e:
        logger.error(f"Error in chat completions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn_run(
        app,
        host="0.0.0.0",
        port=config.agent_port,
        log_level="info",
    )
